"""Zufaellige Ereignisfolgen gegen feste Sicherheitsinvarianten.

**Warum dieser Test existiert.**

Sechs Abweichungen zwischen Backtest und Betrieb sind in diesem Projekt bisher
gefunden worden. Fuenf davon hatten dieselbe Form: nicht ein falscher Pfad,
sondern eine *Kombination* - Teilfuellung und dann Nachfuellung, Storno und
gleichzeitiger Fill, Kill-Switch mitten in einer gewachsenen Position. Jeder
Pfad einzeln war getestet.

Gefunden wurden sie durch Nachdenken, nicht durch die Suite. Das ist kein
Verfahren: Beim letzten Fund stand hinter dem geratenen Fehler ein anderer, den
ich erst beim Nachpruefen sah. Was gebraucht wird, ist die Umkehrung - nicht
jeden Ablauf einzeln pruefen, sondern eine Handvoll Aussagen formulieren, die in
**jedem** Zustand gelten muessen (``execution/invarianten.py``), und zufaellige
Ablaeufe dagegen laufen lassen.

**Warum das billig ist.** Der Fuzzer ist keine Strategiehypothese. Er kostet
keinen Versuch im Zaehler (``state/trials.json`` bleibt unberuehrt) und kann
deshalb beliebig oft laufen.

**Was er nicht kann.** Er prueft die Ausfuehrung gegen eine *simulierte* Boerse.
Ob Bybit sich so verhaelt wie ``FakeExchange``, prueft er nicht - das kann nur
der Demobetrieb. Wo ich mir des Verhaltens nicht sicher bin, ist die
Simulation absichtlich die unfreundlichere Variante: Reduce-Only-Orders
verschwinden dort **nicht** von selbst, wenn die Position schliesst. Verlaesst
sich das System darauf, faellt es hier auf.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from core.config import BybitSettings, RiskSettings
from core.models import Instrument, Side, Signal
from data.bybit.errors import BybitAPIError, BybitTransportError
from execution.invarianten import Verletzung, pruefe
from execution.router import MarketKind
from tests.factories import make_signal
from tests.test_live import Rig, build_rig

#: Wie viele Kerzen je Lauf. Hoch genug, dass mehrere Trades hintereinander
#: entstehen - die interessanten Zustaende hinterlaesst meist der vorige Trade.
KERZEN = 45

#: Wie viele verschiedene Ereignisfolgen. Jede Saat ist reproduzierbar: Schlaegt
#: eine an, laesst sich genau dieser Lauf einzeln wiederholen.
#:
#: 25 in der Suite, damit sie schnell bleibt. Fuer eine gruendliche Runde:
#: ``FUZZ_SAATEN=500 pytest tests/test_fuzz_ausfuehrung.py``. Die Saaten sind
#: fortlaufend, eine groessere Zahl umfasst also alle kleineren - was bisher
#: gehalten hat, haelt weiter.
SAATEN = int(os.environ.get("FUZZ_SAATEN", "25"))


class FuzzStrategie:
    """Handelt auf Zuruf und steigt auf Zuruf aus.

    Beides wird vom Fuzzer gesteuert, nicht von Kursen: Was geprueft wird, ist
    die Ausfuehrung, nicht die Signalgebung.
    """

    strategy_id = "fuzz"
    warmup_bars = 5

    def __init__(self) -> None:
        self.queue: list[Signal] = []
        self.ausstieg = False

    def prepare(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        return {}

    def on_bar(self, ctx) -> Signal | None:
        return self.queue.pop(0) if self.queue else None

    def should_exit(self, ctx, side: Side) -> bool:
        if not self.ausstieg:
            return False
        self.ausstieg = False
        return True


@dataclass
class Welt:
    """Der Handelsroboter und alles, was ihm zustossen kann."""

    rig: Rig
    rng: np.random.Generator
    strategie: FuzzStrategie
    protokoll: list[str] = field(default_factory=list)
    #: Ausnahmen, die eine Kerzenverarbeitung abgebrochen haben.
    ausnahmen: list[str] = field(default_factory=list)

    def notiz(self, text: str) -> None:
        self.protokoll.append(text)

    # -- Ereignisse ----------------------------------------------------------
    def signal_einreihen(self) -> None:
        """Ein Einstiegssignal vormerken.

        Der Einstiegspreis wandert absichtlich um den Marktpreis: oberhalb wird
        die PostOnly-Order abgelehnt. Diese Ablehnung ist der haeufigste Grund,
        warum ein Einstieg live nicht zustande kommt - sie gehoert in die
        Folge.
        """
        markt = self.rig.exchange.mark_price
        versatz = Decimal(str(round(float(self.rng.uniform(-0.01, 0.004)), 4)))
        entry = markt * (Decimal(1) + versatz)
        signal = make_signal(
            entry=str(entry.quantize(Decimal("0.1"))),
            stop_pct=str(round(float(self.rng.uniform(0.4, 2.5)), 2)),
        )
        self.strategie.queue.append(signal)
        self.notiz(f"signal {signal.entry_price}")

    def ausstieg_ausloesen(self) -> None:
        self.strategie.ausstieg = True
        self.notiz("ausstiegsbedingung")

    def einstieg_fuellen(self, *, anteil: float) -> None:
        """Die wartende Einstiegsorder ganz oder teilweise fuellen."""
        bracket = self.rig.trader.bracket
        if bracket is None or bracket.entry_order is None:
            return
        order = self.rig.exchange.orders.get(bracket.entry_order.order_id)
        if order is None or order.status.is_terminal or order.remaining_qty <= 0:
            return
        menge = order.remaining_qty
        if anteil < 1:
            menge = (menge * Decimal(str(anteil))).quantize(Decimal("0.001"))
        if menge <= 0:
            return
        self.rig.exchange.fill(order.order_id, qty=menge)
        self.notiz(f"einstieg gefuellt {menge}")

    def ziel_fuellen(self) -> None:
        """Eine Reduce-Only-Order an der Boerse ausfuehren."""
        ziele = [
            o
            for o in self.rig.exchange.open_orders("BTCUSDT")
            if o.reduce_only and o.remaining_qty > 0
        ]
        if not ziele or self.rig.exchange.position is None:
            return
        order = ziele[int(self.rng.integers(0, len(ziele)))]
        menge = min(order.remaining_qty, self.rig.exchange.position.size)
        if menge <= 0:
            return
        self.rig.exchange.fill(order.order_id, qty=menge)
        self.notiz(f"ziel gefuellt {menge}")

    def stop_ausgeloest(self) -> None:
        """Die Boerse schliesst die Position - der Stop hat gegriffen.

        Die Reduce-Only-Orders bleiben dabei liegen. Ob Bybit sie von selbst
        raeumt, laesst sich aus diesem Container nicht pruefen; sich darauf zu
        verlassen waere eine Annahme, und Annahmen sind in diesem Projekt
        bereits dreimal teuer geworden.
        """
        if self.rig.exchange.position is None:
            return
        self.rig.exchange.position = None
        self.notiz("stop an der Boerse ausgeloest")

    def preis_bewegt(self) -> None:
        faktor = Decimal(str(round(float(self.rng.uniform(0.95, 1.05)), 4)))
        self.rig.exchange.set_mark_price(
            (self.rig.exchange.mark_price * faktor).quantize(Decimal("0.1"))
        )
        self.notiz(f"preis {self.rig.exchange.mark_price}")

    def fehler_einschleusen(self) -> None:
        """Den naechsten Aufruf einer Boersenmethode scheitern lassen."""
        methoden = (
            "place_limit",
            "place_market",
            "set_position_stop",
            "cancel_order",
            "cancel_all",
        )
        methode = methoden[int(self.rng.integers(0, len(methoden)))]
        fehler = (
            BybitAPIError(10001, "fuzz", endpoint="/v5/order/create")
            if self.rng.random() < 0.5
            else BybitTransportError("fuzz: Verbindung weg")
        )
        self.rig.exchange.fail_next(methode, fehler)
        self.notiz(f"fehler auf {methode}")

    def kapital_aendern(self) -> None:
        faktor = Decimal(str(round(float(self.rng.uniform(0.88, 1.06)), 4)))
        neu = (self.rig.account.equity * faktor).quantize(Decimal("0.01"))
        self.rig.account.set_equity(max(Decimal("50"), neu))
        self.notiz(f"kapital {self.rig.account.equity}")

    def kill_zuruecksetzen(self) -> None:
        """Der Mensch hat nachgesehen und gibt wieder frei.

        Ohne diesen Schritt endet jeder Lauf, der einmal den Not-Aus erreicht,
        in einem Zustand, in dem nichts mehr passiert - und der Rest der Folge
        prueft nichts mehr.
        """
        officer = self.rig.officer
        if officer.state.kill_reason:
            officer.reset_kill_switch(confirm="ICH HABE DIE URSACHE GEPRUEFT")
            self.rig.account.set_equity(Decimal("500"))
            self.notiz("not-aus zurueckgesetzt")

    async def neustart(self) -> None:
        """Der Prozess stirbt und startet neu - der Pflichttest aus dem Plan.

        Alles, was nur im Arbeitsspeicher stand, ist weg: Bracket, Zaehler,
        offene Nacharbeit. Was bleibt, ist der Zustand an der Boerse. Genau
        daraus muss sich der Abgleich neu aufbauen.
        """
        trader = self.rig.trader
        trader.bracket = None
        trader._aufraeumen_offen = None
        trader._bars_since_entry_placed = 0
        await trader._reconcile()
        self.notiz("NEUSTART")

    async def ereignis(self) -> None:
        gewichte = {
            self.signal_einreihen: 0.19,
            lambda: self.einstieg_fuellen(anteil=1.0): 0.13,
            lambda: self.einstieg_fuellen(anteil=0.5): 0.12,
            self.ziel_fuellen: 0.12,
            self.preis_bewegt: 0.11,
            self.stop_ausgeloest: 0.08,
            self.fehler_einschleusen: 0.08,
            self.kapital_aendern: 0.08,
            self.ausstieg_ausloesen: 0.04,
            self.neustart: 0.03,
            self.kill_zuruecksetzen: 0.02,
        }
        aktionen = list(gewichte)
        wahl = self.rng.choice(len(aktionen), p=list(gewichte.values()))
        ergebnis = aktionen[int(wahl)]()
        if ergebnis is not None:
            await ergebnis

    # -- Ablauf --------------------------------------------------------------
    async def kerze(self) -> None:
        await self.rig.feed(close=self.rig.exchange.mark_price)
        self.notiz("--- kerze ---")

    def verletzungen(self) -> list[Verletzung]:
        return pruefe(
            bracket=self.rig.trader.bracket,
            position=self.rig.account.get_positions("BTCUSDT")[0]
            if self.rig.account.get_positions("BTCUSDT")
            else None,
            orders=self.rig.exchange.open_orders("BTCUSDT"),
            market_kind=MarketKind.PERPETUAL,
        )


def baue_welt(tmp_path, btcusdt, risk, settings, saat: int) -> Welt:
    strategie = FuzzStrategie()
    rig = build_rig(tmp_path, btcusdt, risk, settings, strategy=strategie)  # type: ignore[arg-type]
    welt = Welt(rig=rig, rng=np.random.default_rng(saat), strategie=strategie)

    # Jede Ausnahme mitschreiben, die die Kerzenverarbeitung abbricht. Die
    # Huelle in ``_on_candle`` faengt sie ab, damit der Kerzenstrom nicht
    # abreisst - fuer den Fuzzer waere sie damit unsichtbar, und ein
    # ``AttributeError`` im eigenen Code saehe aus wie ein ruhiger Lauf.
    original = rig.trader._kerze_fehlgeschlagen

    async def mitschreiben(exc: Exception) -> None:
        welt.ausnahmen.append(f"{type(exc).__name__}: {exc}")
        await original(exc)

    rig.trader._kerze_fehlgeschlagen = mitschreiben  # type: ignore[method-assign]
    return welt


@pytest.mark.parametrize("saat", range(SAATEN))
async def test_invarianten_halten_in_zufallsfolgen(
    tmp_path,
    btcusdt: Instrument,
    risk: RiskSettings,
    bybit_settings: BybitSettings,
    saat: int,
) -> None:
    """Der eigentliche Test.

    Faellt er, steht die verletzte Aussage im Fehlertext - zusammen mit der
    Ereignisfolge, die dorthin gefuehrt hat. Die Saat macht den Lauf
    wiederholbar; ein Fehler, der sich nicht reproduzieren laesst, ist kein
    Befund, sondern eine Anekdote.
    """
    welt = baue_welt(tmp_path, btcusdt, risk, bybit_settings, saat)
    geprueft = 0

    for _ in range(KERZEN):
        for _ in range(int(welt.rng.integers(0, 3))):
            await welt.ereignis()

        vorher = len(welt.ausnahmen)
        await welt.kerze()

        # **Nur Kerzen pruefen, die durchgelaufen sind.**
        #
        # Bricht die Verarbeitung mit einer Ausnahme ab - etwa weil der
        # Notausstieg mitten im Abgleich auf einen simulierten Ausfall trifft -,
        # dann *hat der Abgleich nicht stattgefunden*. Die Invarianten gelten
        # nach dem Abgleich, nicht waehrend eines abgebrochenen.
        #
        # Das ist keine Lockerung, sondern die richtige Formulierung: Der
        # Anspruch bleibt, dass die naechste **vollstaendige** Kerze den Zustand
        # wieder geradezieht. Genau das prueft die Schleife, denn sie laeuft
        # weiter - eine Verletzung, die bestehen bleibt, faellt beim naechsten
        # sauberen Durchlauf auf. Gemessen an Saat 272: Ein Ausfall des
        # Marktausstiegs liess die Position auf 0,004 wachsen, waehrend das
        # Bracket 0,002 vermerkt hatte; die Folgekerze schloss sie.
        if len(welt.ausnahmen) != vorher:
            continue

        geprueft += 1
        verletzt = welt.verletzungen()
        if verletzt:
            verlauf = "\n  ".join(welt.protokoll[-25:])
            pytest.fail(
                f"Saat {saat}: "
                + "; ".join(str(v) for v in verletzt)
                + f"\n\nLetzte Ereignisse:\n  {verlauf}"
            )

    assert welt.rig.trader.stats.candles_seen == KERZEN
    # Sonst koennte ein Lauf, in dem jede Kerze abbricht, leer durchgehen.
    assert geprueft >= KERZEN // 2, (
        f"Saat {saat}: nur {geprueft} von {KERZEN} Kerzen liefen durch"
    )

    # **Injizierte Boersenfehler sind gewollt, alles andere nicht.** Ein
    # ``AttributeError`` oder ``TypeError`` aus dem eigenen Code faellt sonst
    # nicht auf: Die Huelle in ``_on_candle`` faengt ihn ab, damit der
    # Kerzenstrom nicht abreisst - der Lauf saehe danach ruhig aus.
    fremd = [
        f for f in welt.ausnahmen
        if not f.startswith(("BybitAPIError", "BybitTransportError"))
    ]
    assert not fremd, f"Saat {saat}: unerwartete Ausnahmen {fremd}"
