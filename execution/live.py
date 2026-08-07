"""Die Live-Schleife - hier wird tatsaechlich gehandelt.

Ablauf je abgeschlossener Kerze:

    Kerze (confirm: true)
        -> in den gleitenden Datenpuffer
        -> Strategie fragen
        -> Risk-Officer fragen  (VETO moeglich)
        -> Order-Router
        -> Bybit
        -> Telegram

**Kein LLM in dieser Schleife.** Was hier laeuft, ist derselbe deterministische
Code wie im Backtest - deshalb sind Backtest und Livebetrieb ueberhaupt
vergleichbar.

Drei Eigenschaften, die den Unterschied zwischen Spielzeug und Betrieb machen:

* **Zustandsabgleich beim Start.** Der Prozess kann jederzeit sterben und neu
  starten. Beim Start wird gefragt: Habe ich eine offene Position? Liegen noch
  Orders? Passt der Stop? Ein Prozess, der das nicht tut, eroeffnet nach einem
  Neustart eine zweite Position neben der ersten.
* **Kapitalstand wird laufend gemeldet**, nicht nur bei Signalen. Der
  Kill-Switch muss auch greifen, wenn eine offene Position ins Minus laeuft und
  gerade kein Signal ansteht.
* **Der Stop liegt an der Position**, nicht in diesem Prozess. Faellt die
  Schleife aus, bleibt der Schutz bestehen.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import structlog

from core.config import BybitSettings, RiskSettings
from core.models import Candle, Instrument, Interval, Position, Side, Signal, Trade
from data.bybit.adapter import AccountSource, MarketDataSource
from data.bybit.trading import TradingGateway
from data.bybit.ws import KlineStream
from data.store import CandleStore, candles_to_frame
from execution.invarianten import pruefe
from execution.risk import Approved, RiskOfficer, TradingState, Vetoed
from execution.router import Bracket, BracketState, MarketKind, OrderRouter
from execution.sizing import SizedPosition
from strategy.base import BarContext, Strategy, frame_to_arrays, wants_exit
from web.journal import CommandAction, EventKind, LiveJournal

log = structlog.get_logger(__name__)

#: Wie viele Kerzen im Speicher gehalten werden. Muss die laengste
#: Indikatorperiode deutlich uebersteigen; 2000 deckt auch EMA(400) ab.
BUFFER_BARS = 2000

#: Rueckgabe von ``_equity_fraction``, wenn auf diesem Balken nicht gehandelt
#: werden soll. Ein eigener Wert, weil ``None`` an dieser Stelle bereits
#: "nimm die Risikoformel" bedeutet - zwei verschiedene Dinge, die sich mit
#: ``None`` allein nicht auseinanderhalten liessen.
_KEIN_HANDEL = object()

#: Wie oft der Not-Aus das Stornieren wiederholt, bevor er aufgibt. Drei, weil
#: gleich danach ``stop()`` kommt - eine spaetere Gelegenheit gibt es nicht.
STORNO_VERSUCHE = 3

Notifier = Callable[[str], Awaitable[None]]


@dataclass(slots=True)
class LiveStats:
    """Betriebszahlen - fuer Dashboard und Abschlussbericht."""

    candles_seen: int = 0
    signals_generated: int = 0
    signals_vetoed: int = 0
    entries_placed: int = 0
    entries_filled: int = 0
    entries_expired: int = 0
    veto_reasons: dict[str, int] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    #: Kerzen, deren Verarbeitung mit einer Ausnahme endete. Steht bewusst im
    #: Dashboard: Ein System, das leise Fehler frisst, sieht von aussen aus wie
    #: eines, das nichts zu tun hat.
    candle_errors: int = 0
    last_error: str = ""
    #: Verletzte Sicherheitsinvarianten (siehe ``execution/invarianten.py``).
    invariant_breaches: int = 0
    last_breach: str = ""

    def count_veto(self, reason: str) -> None:
        self.signals_vetoed += 1
        self.veto_reasons[reason] = self.veto_reasons.get(reason, 0) + 1

    def describe(self) -> str:
        runtime = datetime.now(UTC) - self.started_at
        text = (
            f"{self.candles_seen} Kerzen, {self.signals_generated} Signale, "
            f"{self.entries_filled} Einstiege, {self.signals_vetoed} abgelehnt "
            f"({runtime.total_seconds() / 3600:.1f} h Laufzeit)"
        )
        if self.candle_errors:
            text += f", {self.candle_errors} Fehler"
        if self.invariant_breaches:
            text += f", {self.invariant_breaches} Invariantenbrueche"
        return text


class LiveTrader:
    """Der Handelsroboter."""

    def __init__(
        self,
        *,
        settings: BybitSettings,
        strategy: Strategy,
        instrument: Instrument,
        risk_settings: RiskSettings,
        market: MarketDataSource,
        account: AccountSource,
        gateway: TradingGateway,
        officer: RiskOfficer,
        store: CandleStore,
        interval: Interval = Interval.M15,
        market_kind: MarketKind = MarketKind.PERPETUAL,
        notifier: Notifier | None = None,
        entry_expiry_bars: int = 3,
        journal: LiveJournal | None = None,
    ) -> None:
        self.settings = settings
        self.strategy = strategy
        self.instrument = instrument
        self.market = market
        self.account = account
        self.officer = officer
        self.store = store
        self.interval = interval
        self.entry_expiry_bars = entry_expiry_bars
        self.notifier = notifier
        self.journal = journal
        self.risk_settings = risk_settings

        self.router = OrderRouter(
            gateway, instrument, risk_settings, market_kind=market_kind
        )
        self.stats = LiveStats()
        self.bracket: Bracket | None = None
        self.last_equity: Decimal = Decimal(0)
        self.equity_at_entry: Decimal = Decimal(0)
        self._mae: Decimal = Decimal(0)
        self._mfe: Decimal = Decimal(0)
        self._frame: pd.DataFrame = pd.DataFrame()
        self._bars_since_entry_placed = 0
        self._stream: KlineStream | None = None
        #: Grund eines fehlgeschlagenen Stornos. Solange gesetzt, koennen noch
        #: Restorders im Buch stehen - dann wird nicht neu eroeffnet.
        self._aufraeumen_offen: str | None = None

    # -- Start ---------------------------------------------------------------
    async def start(self) -> None:
        """Vorbereiten und dann bis zum Stopp handeln."""
        await self._reconcile()
        self._load_history()

        self._stream = KlineStream(
            self.settings, [self.interval], on_candle=self._on_candle
        )
        await self._notify(
            f"Handelsroboter gestartet\n"
            f"{self.instrument.symbol} {self.interval.label}\n"
            f"Strategie: {self.strategy.strategy_id}\n"
            f"Umgebung: {self.settings.environment.value}"
        )
        self._report(
            EventKind.START,
            f"Handelsroboter gestartet - {self.instrument.symbol} "
            f"{self.interval.label}, Strategie {self.strategy.strategy_id}, "
            f"Umgebung {self.settings.environment.value}",
            symbol=self.instrument.symbol,
            environment=self.settings.environment.value,
        )
        log.info(
            "live.gestartet",
            symbol=self.instrument.symbol,
            intervall=self.interval.label,
            strategie=self.strategy.strategy_id,
            umgebung=self.settings.environment.value,
        )
        await self._stream.run()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()

    async def _reconcile(self) -> None:
        """Zustandsabgleich beim Start.

        Ohne diesen Schritt eroeffnet ein neu gestarteter Prozess eine zweite
        Position neben der bestehenden - und die erste laeuft unbeaufsichtigt
        weiter. Das ist der haeufigste Weg, wie ein Handelsroboter ueber Nacht
        aus dem Ruder laeuft.
        """
        position = self._first_position()
        if position is None:
            # Verwaiste Orders aus einem frueheren Lauf entfernen. Geht das
            # schief, wird vor dem ersten Einstieg erneut aufgeraeumt statt in
            # ein moeglicherweise volles Buch hinein zu handeln.
            if not self.router.close_all("Aufraeumen beim Start - keine offene Position"):
                self._aufraeumen_offen = "Aufraeumen beim Start"
            return

        log.warning(
            "live.offene_position_gefunden",
            seite=position.side.value,
            groesse=str(position.size),
            einstieg=str(position.entry_price),
            stop=str(position.stop_loss) if position.stop_loss else None,
        )

        if position.stop_loss is None or position.stop_loss == 0:
            # Position ohne Stop ist der gefaehrlichste Zustand ueberhaupt.
            await self._notify(
                "WARNUNG: Offene Position ohne Stop gefunden. "
                "Sie wird sofort geschlossen."
            )
            self._report(
                EventKind.WARNING,
                f"Offene Position ohne Stop gefunden ({position.side.value} "
                f"{position.size}) - wird sofort geschlossen",
            )
            log.critical(
                "live.position_ohne_stop",
                massnahme="Wird geschlossen - ungeschuetzte Position ist nicht tragbar",
            )
            try:
                self.router.gateway.place_market(
                    symbol=self.instrument.symbol,
                    side=position.side.opposite,
                    qty=position.size,
                    reduce_only=True,
                )
            except Exception as exc:
                # **Hier flog die Ausnahme frueher aus ``start()`` heraus.**
                #
                # Der Prozess startete also gar nicht - und liess ausgerechnet
                # eine Position ohne Stop zurueck. Der gefaehrlichste Zustand
                # ueberhaupt, kombiniert mit einem System, das nicht mehr
                # hinsieht. Zwei Zufallsfolgen des Fuzzers sind genau darauf
                # gelaufen.
                #
                # Schliessen ist die erste Wahl, aber nicht die einzige.
                await self._notfallabsicherung(position, exc)
                return
            self.router.close_all("Ungeschuetzte Position geschlossen")
            return

        self.bracket = self._bracket_aus_position(position)
        self.equity_at_entry = self._current_equity()
        await self._notify(
            f"Offene Position uebernommen: {position.side.value} {position.size} "
            f"@ {position.entry_price}, Stop {position.stop_loss}\n"
            "Die urspruenglichen Ziele sind nicht wiederherstellbar - sie laeuft "
            "bis zum Stop oder bis die Ausstiegsbedingung greift."
        )
        self._report(
            EventKind.WARNING,
            f"Position uebernommen: {position.side.value} {position.size} @ "
            f"{position.entry_price}, Stop {position.stop_loss}. Ohne Ziele - "
            f"die urspruenglichen Stufen sind nach einem Neustart nicht bekannt.",
            side=position.side.value,
            qty=position.size,
            entry_price=position.entry_price,
            stop_price=position.stop_loss,
        )

    async def _notfallabsicherung(self, position: Position, exc: Exception) -> None:
        """Die Position ohne Stop liess sich nicht schliessen. Was jetzt?

        Nicht: aufgeben. Frueher flog die Ausnahme aus ``start()`` heraus - der
        Prozess startete nicht und liess die ungeschuetzte Position stehen.
        Schlechter geht es kaum: der gefaehrlichste Zustand ueberhaupt, und
        niemand mehr, der hinsieht.

        Zweitbeste Wahl ist deshalb, sie wenigstens **abzusichern**: ein Stop
        im maximal zulaessigen Abstand. Der ist nicht der, den eine Strategie
        gewaehlt haette - ihre Begruendung ist nach einem Neustart nicht mehr
        bekannt -, aber er begrenzt den Schaden auf einen bekannten Betrag.

        Klappt auch das nicht, wird die Position trotzdem uebernommen. Ein
        Bracket ohne Stop ist ein schlechter Zustand, aber ein **gesehener**:
        Die Schleife kennt sie dann, die Ausstiegsbedingung greift, der Not-Aus
        greift, und die Invariantenpruefung meldet sie bei jeder Kerze.
        """
        log.critical(
            "live.notschliessung_fehlgeschlagen",
            fehler=str(exc),
            massnahme="Versuche stattdessen einen Stop zu setzen",
        )

        abstand = self.risk_settings.max_stop_distance_pct / Decimal(100)
        richtung = Decimal(-1) if position.side is Side.BUY else Decimal(1)
        notstop = self.instrument.round_price(
            position.entry_price * (Decimal(1) + richtung * abstand),
            side=position.side.opposite,
        )

        gesetzt = False
        if self.router.market_kind.has_position_stop:
            try:
                self.router.gateway.set_position_stop(
                    symbol=self.instrument.symbol, stop_loss=notstop
                )
                gesetzt = True
            except Exception as zweiter:
                log.critical("live.notstop_fehlgeschlagen", fehler=str(zweiter))

        ersatz = position.model_copy(
            update={"stop_loss": notstop if gesetzt else None}
        )
        self.bracket = self._bracket_aus_position(ersatz)
        self.equity_at_entry = self._current_equity()

        if gesetzt:
            text = (
                f"WARNUNG: Position ohne Stop gefunden ({position.side.value} "
                f"{position.size}). Sie liess sich nicht schliessen ({exc}), "
                f"deshalb wurde ein Notstop bei {notstop} gesetzt - der maximal "
                f"zulaessige Abstand, nicht der einer Strategie. Bitte "
                f"nachsehen."
            )
        else:
            text = (
                f"DRINGEND: Position ohne Stop gefunden ({position.side.value} "
                f"{position.size}). Sie liess sich weder schliessen ({exc}) "
                f"noch absichern. Sie wird ueberwacht, ist aber ungeschuetzt - "
                f"bitte sofort bei Bybit eingreifen."
            )
        self._report(EventKind.WARNING, text, qty=position.size)
        await self._notify(text)

    def _bracket_aus_position(self, position: Position) -> Bracket:
        """Aus einer uebernommenen Position ein Bracket bauen.

        Vorher passierte hier nichts: Die Position wurde uebernommen, aber kein
        Bracket angelegt. Damit lief sie **ohne jede Verwaltung** weiter -
        ``_manage_open_position`` steigt bei ``bracket is None`` sofort aus,
        ``_check_signal_exit`` ebenso. Die Ausstiegsbedingung, ueber die 38,5 %
        aller Trades enden, galt fuer sie nicht mehr; sie lief bis zum Stop.

        Ein Neustart mitten in einer Position ist kein Randfall - er steht als
        Pflichttest im Plan, und genau der Test haette die Luecke nicht gezeigt:
        Der Stop haengt an der Position und ueberlebt, es sieht also alles
        richtig aus. Aufgefallen ist es erst, als die Invariantenpruefung
        anfing, diese Lage als "unbeaufsichtigte Position" zu melden.

        **Was sich nicht wiederherstellen laesst, sind die Ziele.** Welche
        Stufen das Signal hatte, steht nirgends mehr. Die Position laeuft
        deshalb bis zum Stop oder bis die Ausstiegsbedingung greift - das wird
        gemeldet, nicht stillschweigend hingenommen.
        """
        stop = position.stop_loss or Decimal(0)
        # Der Signal-Bauplan verlangt einen Stop **echt** unterhalb (Long) bzw.
        # oberhalb (Short) des Einstiegs. Nach einem Nachzug auf Einstand liegt
        # er aber genau darauf. Fuer den Bauplan wird er dann um einen Tick
        # verschoben; die Bremse an der Boerse bleibt davon unberuehrt, und
        # ``bracket.stop_price`` traegt weiterhin den echten Wert.
        tick = self.instrument.tick_size
        if position.side is Side.BUY:
            plausibel = min(stop, position.entry_price - tick)
        else:
            plausibel = max(stop, position.entry_price + tick)

        signal = Signal(
            timestamp=datetime.now(UTC),
            symbol=self.instrument.symbol,
            side=position.side,
            entry_price=position.entry_price,
            stop_loss=plausibel,
            take_profits=[],
            strategy_id=self.strategy.strategy_id,
            reason="nach Neustart uebernommen",
        )
        sized = SizedPosition(
            qty=position.size,
            notional=position.size * position.entry_price,
            leverage=position.leverage,
            exchange_leverage=position.leverage,
            risk_amount=abs(position.entry_price - plausibel) * position.size,
            risk_pct_of_equity=Decimal(0),
            stop_distance=abs(position.entry_price - plausibel),
            stop_distance_pct=Decimal(0),
            liquidation_price=Decimal(0),
            liquidation_distance_pct=Decimal(0),
            take_profit_legs=[],
        )
        return Bracket(
            signal=signal,
            sized=sized,
            state=BracketState.PROTECTED,
            entry_price=position.entry_price,
            filled_qty=position.size,
            remaining_qty=position.size,
            # Der echte Wert, nicht der fuer den Bauplan verschobene - und
            # ``None``, wenn wirklich keiner gesetzt ist. Eine 0 saehe auf dem
            # Bildschirm aus wie ein Stop bei null statt wie gar keiner.
            stop_price=position.stop_loss,
            opened_at=datetime.now(UTC),
        )

    def _load_history(self) -> None:
        """Kerzen aus dem Speicher laden, damit Indikatoren sofort greifen.

        Ohne Vorlauf braeuchte die Strategie je nach Periode Stunden bis Tage,
        bis sie das erste Signal geben kann.
        """
        frame = self.store.read(self.instrument.symbol, self.interval)
        if frame.empty:
            log.warning(
                "live.kein_verlauf",
                hinweis="Erst 'python -m cli backfill' ausfuehren, sonst dauert es, "
                "bis die Indikatoren eingeschwungen sind.",
            )
            self._frame = frame
            return

        self._frame = frame.tail(BUFFER_BARS).reset_index(drop=True)
        log.info(
            "live.verlauf_geladen",
            kerzen=len(self._frame),
            bis=str(self._frame["open_time"].iloc[-1]),
        )

    # -- Hauptschleife -------------------------------------------------------
    async def _on_candle(self, candle: Candle, interval: Interval) -> None:
        """Eine bestaetigte Kerze ist eingetroffen.

        Diese Huelle laesst **keine** Ausnahme nach aussen. Der Grund ist der
        Aufrufer: ``KlineStream.run`` faengt alles, was aus dem Kerzen-Handler
        kommt, als ``ws.verbindung_verloren`` und baut die Verbindung neu auf.
        Ein fehlgeschlagener Orderaufruf sah damit aus wie ein Netzproblem -
        falsche Diagnose im Protokoll, und waehrend des Backoffs fehlen Kerzen.

        Gefressen wird der Fehler trotzdem nicht: Er wird gezaehlt, gemeldet und
        beim ersten Auftreten aufs Telefon geschickt. Ein System, das leise
        Fehler verschluckt, sieht von aussen aus wie eines, das nichts zu tun
        hat - das ist der Unterschied, den der Zaehler sichtbar macht.
        """
        if interval is not self.interval:
            return
        try:
            await self._verarbeite_kerze(candle, interval)
        except Exception as exc:
            await self._kerze_fehlgeschlagen(exc)

    async def _kerze_fehlgeschlagen(self, exc: Exception) -> None:
        text = f"{type(exc).__name__}: {exc}"
        erstmalig = text != self.stats.last_error
        self.stats.candle_errors += 1
        self.stats.last_error = text

        log.critical("live.kerze_fehlgeschlagen", fehler=text, anzahl=self.stats.candle_errors)
        self._report(EventKind.WARNING, f"Fehler bei der Kerzenverarbeitung: {text}")
        # Nur beim ersten Mal aufs Telefon. Ein dauerhaft kaputter Aufruf wuerde
        # sonst alle 15 Minuten klingeln, bis niemand mehr hinsieht.
        if erstmalig:
            await self._notify(
                f"Fehler bei der Kerzenverarbeitung: {text}\n"
                "Der Handel laeuft weiter, aber diese Kerze wurde nicht "
                "vollstaendig verarbeitet."
            )

    async def _verarbeite_kerze(self, candle: Candle, interval: Interval) -> None:
        self.stats.candles_seen += 1
        # Ein Schreibfehler im Datenspeicher darf den Handel nicht stoppen -
        # Kerzen lassen sich jederzeit nachladen, eine offene Position nicht.
        with contextlib.suppress(Exception):
            self.store.write(self.instrument.symbol, interval, [candle])
        self._append(candle)

        equity = self._current_equity()
        self.last_equity = equity
        assessment = self.officer.observe_equity(equity)

        # Erst der Befehl vom Dashboard, dann alles andere: Ein Not-Aus vom
        # Telefon soll nicht warten, bis die Strategie ihre Meinung gebildet hat.
        await self._handle_commands()

        if self.officer.state.trading_state is TradingState.KILLED:
            await self._handle_kill_switch()
            self._publish(assessment)
            return

        self._track_excursion(candle)
        await self._manage_open_position()

        # Der Kontext wird **einmal** gebaut und geteilt. Ausstieg und
        # Einstieg muessen denselben Balken sehen; zweimal rechnen waere
        # ausserdem doppelte Indikatorarbeit je Kerze.
        context = self._context()

        # Ausstiegsbedingung der Strategie - **nach** Stop und Zielen, genau
        # wie in der Engine (siehe ``backtest/engine.py``). Stop und Ziele
        # haetten innerhalb der Kerze zuerst gegriffen; diese Bedingung steht
        # erst am Kerzenschluss fest.
        if context is not None:
            await self._check_signal_exit(context, candle)

        # **Nur wenn gar kein Bracket offen ist.** Ein Bracket im Zustand
        # PENDING_ENTRY ist zwar nicht ``is_open`` - es wartet ja noch auf den
        # Fill -, aber es liegt bereits eine Einstiegsorder im Markt. Wer hier
        # auf ``is_open`` prueft, legt bei jedem Signal eine zweite dazu.
        if self.bracket is None and context is not None and self._nacharbeit_erledigt():
            await self._look_for_entry(context)

        await self._pruefe_invarianten()
        self._publish(assessment, candle=candle)

    async def _pruefe_invarianten(self) -> None:
        """Die Sicherheitsaussagen gegen die Boerse pruefen - einmal je Kerze.

        Geprueft wird **hier am Ende**, nicht zwischendurch: Zwischen zwei
        Kerzen darf unsere Sicht von der Boerse abweichen; eine Order kann in
        genau diesem Moment fuellen. Der Abgleich ist gerade gelaufen, ab jetzt
        muessen die Aussagen halten.

        Gemeldet wird, nicht gehandelt. Die Stellen, die eingreifen, kennen
        ihren Fall genau; eine Pruefung, die im Betrieb noch nie angeschlagen
        hat, automatisch Positionen schliessen zu lassen, hiesse einem
        Fehlalarm Geld anzuvertrauen. Der Weg aufs Telefon ist der richtige.
        """
        try:
            verletzungen = pruefe(
                bracket=self.bracket,
                position=self._first_position(),
                orders=self.router.gateway.open_orders(self.instrument.symbol),
                market_kind=self.router.market_kind,
            )
        except Exception as exc:
            # Die Pruefung ist Beobachtung. Scheitert sie, ist das eine Notiz
            # wert - aber sie darf den Handel nicht anhalten.
            log.warning("live.invariantenpruefung_fehlgeschlagen", fehler=str(exc))
            return

        if not verletzungen:
            return

        text = "; ".join(str(v) for v in verletzungen)
        erstmalig = text != self.stats.last_breach
        self.stats.invariant_breaches += len(verletzungen)
        self.stats.last_breach = text
        log.critical("live.invariante_verletzt", verletzungen=text)
        self._report(EventKind.WARNING, f"Sicherheitsinvariante verletzt: {text}")
        if erstmalig:
            await self._notify(
                f"WARNUNG: Der Zustand an der Boerse passt nicht zum "
                f"Handelssystem.\n{text}\n"
                "Bitte bei Bybit nachsehen. Der Handel laeuft weiter."
            )

    # -- Dashboard -----------------------------------------------------------
    def _report(self, kind: EventKind, message: str, **data) -> None:
        """Ein Ereignis ans Dashboard melden.

        Wie beim Benachrichtigungsdienst gilt: Ein Fehler beim Berichten darf
        den Handel nie stoppen. Das Dashboard ist Beobachtung, nicht Steuerung.
        """
        if self.journal is None:
            return
        with contextlib.suppress(Exception):
            self.journal.record(kind, message, **data)

    def _publish(self, assessment, candle: Candle | None = None) -> None:
        """Die Momentaufnahme fuer die Website schreiben - inklusive Herzschlag.

        Bei **jeder** Kerze, auch wenn nichts passiert ist. Der Herzschlag ist
        die einzige Art, wie das Dashboard zwischen "nichts zu tun" und
        "Prozess tot" unterscheiden kann.
        """
        if self.journal is None:
            return
        with contextlib.suppress(Exception):
            self.journal.write_snapshot(self._snapshot(assessment, candle))

    def _snapshot(self, assessment, candle: Candle | None = None) -> dict:
        position = None
        if self.bracket is not None and self.bracket.is_open:
            position = {
                "side": self.bracket.signal.side.value,
                "qty": self.bracket.remaining_qty,
                "entry_price": self.bracket.entry_price,
                "stop_price": self.bracket.stop_price,
                "targets_hit": self.bracket.targets_hit,
                "at_breakeven": self.bracket.moved_to_breakeven,
                "description": self.bracket.describe(),
                "opened_at": self.bracket.opened_at,
                "protected": self.bracket.is_protected,
                # Ohne diese beiden ist die Position auf dem Bildschirm eine
                # Zeile ohne Aussage: Man sieht, dass etwas offen ist, aber
                # nicht, wie es steht und wohin es laufen soll.
                "take_profits": self._take_profit_levels(),
                "unrealized": self._unrealized(candle),
            }
        elif self.bracket is not None:
            position = {"pending": self.bracket.describe()}

        return {
            "symbol": self.instrument.symbol,
            "interval": self.interval.label,
            "environment": self.settings.environment.value,
            "real_money": self.settings.environment.is_real_money,
            "strategy_id": self.strategy.strategy_id,
            "equity": assessment.equity,
            "equity_peak": assessment.equity_peak,
            "drawdown_pct": assessment.drawdown_pct,
            "day_pnl_pct": assessment.day_pnl_pct,
            "week_pnl_pct": assessment.week_pnl_pct,
            # Nicht aus der Bewertung: Die entstand vor den Dashboard-Befehlen
            # und wuesste von einer soeben ausgeloesten Pause nichts.
            "trading_state": self.officer.state.trading_state.value,
            "kill_reason": self.officer.state.kill_reason,
            "last_price": candle.close if candle else None,
            "last_candle": candle.open_time if candle else None,
            "position": position,
            "stats": {
                "candles_seen": self.stats.candles_seen,
                "signals_generated": self.stats.signals_generated,
                "signals_vetoed": self.stats.signals_vetoed,
                "entries_placed": self.stats.entries_placed,
                "entries_filled": self.stats.entries_filled,
                "entries_expired": self.stats.entries_expired,
                "veto_reasons": self.stats.veto_reasons,
                "started_at": self.stats.started_at,
                "candle_errors": self.stats.candle_errors,
                "last_error": self.stats.last_error,
                "invariant_breaches": self.stats.invariant_breaches,
                "last_breach": self.stats.last_breach,
                "summary": self.stats.describe(),
            },
        }

    def _take_profit_levels(self) -> list[dict]:
        """Die Ziele der offenen Position - Preis, Anteil, erreicht ja/nein.

        Genommen wird das **Signal**, nicht die Orderliste der Boerse: Eine
        erreichte Teilorder verschwindet dort, und dann fehlte auf dem
        Bildschirm ausgerechnet das Ziel, das gerade gegriffen hat.
        """
        if self.bracket is None:
            return []
        return [
            {
                "price": leg.price,
                "portion": leg.portion,
                "erreicht": nummer <= self.bracket.targets_hit,
            }
            for nummer, leg in enumerate(self.bracket.signal.take_profits, start=1)
        ]

    def _unrealized(self, candle: Candle | None) -> dict | None:
        """Schwebender Gewinn der offenen Position.

        ``None``, solange kein aktueller Preis vorliegt - eine Zahl aus dem
        Einstiegskurs gegen sich selbst waere immer null und damit eine
        Falschaussage statt einer fehlenden Angabe.

        Gerechnet wird brutto: Die Gebuehren des Ausstiegs stehen noch nicht
        fest, weil noch nicht feststeht, wie ausgestiegen wird.
        """
        bracket = self.bracket
        if bracket is None or candle is None or bracket.entry_price is None:
            return None
        if bracket.remaining_qty <= 0:
            return None

        richtung = Decimal(1) if bracket.signal.side is Side.BUY else Decimal(-1)
        pnl = (candle.close - bracket.entry_price) * bracket.remaining_qty * richtung
        einsatz = bracket.entry_price * bracket.remaining_qty
        prozent = (pnl / einsatz * Decimal(100)) if einsatz > 0 else Decimal(0)

        # Abstand zum Stop in Prozent - die Zahl, die im Betrieb zaehlt.
        abstand = None
        if bracket.stop_price is not None and candle.close > 0:
            abstand = abs(candle.close - bracket.stop_price) / candle.close * Decimal(100)

        return {
            "pnl": pnl,
            "pnl_pct": prozent,
            "preis": candle.close,
            "stop_abstand_pct": abstand,
        }

    async def _handle_commands(self) -> None:
        """Anweisungen vom Dashboard ausfuehren.

        Der Rueckkanal vom Telefon. Bewusst als Abholung statt als offene
        Verbindung: Ein abgestuerztes Dashboard soll den Handel nicht
        beruehren, und ein Befehl soll einen Neustart des Handels ueberleben.
        """
        if self.journal is None:
            return

        command = None
        with contextlib.suppress(Exception):
            command = self.journal.take_command()
        if command is None:
            return

        log.warning("live.befehl", befehl=command.action.value, grund=command.reason)
        self._report(
            EventKind.COMMAND,
            f"Anweisung vom Dashboard: {command.action.value}",
            reason=command.reason,
        )

        if command.action is CommandAction.PAUSE:
            self.officer.pause(command.reason or "vom Dashboard pausiert")
            await self._notify("Handel pausiert. Offene Positionen laufen weiter.")

        elif command.action is CommandAction.RESUME:
            self.officer.resume()
            await self._notify("Handel fortgesetzt.")

        elif command.action is CommandAction.CLOSE_ALL:
            await self._close_everything("Vom Dashboard geschlossen")
            self.officer.pause("nach Glattstellung pausiert")
            await self._notify("Alles glattgestellt. Handel pausiert.")

        elif command.action is CommandAction.KILL:
            # Nur den Schalter umlegen. Das Schliessen uebernimmt die Pruefung
            # gleich danach in ``_on_candle`` - sonst laeuft der Notausstieg
            # zweimal.
            self.officer.trigger_kill_switch(
                command.reason or "Not-Aus vom Dashboard"
            )

    async def _close_everything(self, reason: str) -> None:
        storniert = self._alles_glattstellen(reason)
        self._bracket_abschliessen(reason, storniert=storniert)

    def _alles_glattstellen(self, grund: str) -> bool:
        """Schliessen, was **an der Boerse** steht - nicht, was wir glauben.

        Der Unterschied ist der Fund aus einer Zufallsfolge: Fuellt die
        Einstiegsorder, waehrend das Bracket noch auf sie wartet, ist die
        Position da, aber ``bracket.is_open`` ist ``False``. Der Not-Aus
        stornierte dann nur die Orders und meldete Vollzug - die Position lief
        weiter. Dasselbe gilt fuer eine nach einem Neustart uebernommene
        Position, die gar kein Bracket hat.

        Rueckgabe: ob das Stornieren durchging.
        """
        position = self._first_position()
        if position is None:
            return self.router.close_all(grund)

        storniert = self.router.flatten(
            side=position.side, qty=position.size, reason=grund
        )
        if self.bracket is not None:
            self.bracket.state = BracketState.CLOSED
            self.bracket.remaining_qty = Decimal(0)
        return storniert

    def _append(self, candle: Candle) -> None:
        row = candles_to_frame([candle])
        if self._frame.empty:
            self._frame = row
            return
        last = self._frame["open_time"].iloc[-1]
        if row["open_time"].iloc[0] <= last:
            return  # schon vorhanden
        self._frame = (
            pd.concat([self._frame, row], ignore_index=True)
            .tail(BUFFER_BARS)
            .reset_index(drop=True)
        )

    def _current_equity(self) -> Decimal:
        """Kapital, mit dem gerechnet wird - gegebenenfalls gedeckelt.

        Der Deckel ist fuer die Demo gedacht: Bybit haendigt dort gerne 50.000
        USDT Spielgeld aus. Ohne ihn wuerde die Demo Positionen im
        hundertfachen Umfang des geplanten Kontos eroeffnen und ausgerechnet
        die Grenzen nie beruehren, an denen es spaeter scheitern koennte.
        """
        balance = self.account.get_wallet_balance("USDT")
        cap = self.risk_settings.equity_cap
        if cap > 0 and balance.equity > cap:
            return cap
        return balance.equity

    async def _handle_kill_switch(self) -> None:
        """Not-Aus: alles glattstellen, melden, anhalten.

        **Die Meldung geht raus, auch wenn das Glattstellen scheitert.** Vorher
        stand das Schliessen ungeschuetzt am Anfang; ein zufaelliger Lauf des
        Ausfuehrungs-Fuzzers hat einen Fehler auf ``cancel_all`` gelegt, und
        damit fiel der ganze Rest aus: keine Nachricht, kein ``stop()``, und der
        Kerzenstrom deutete die Ausnahme als Verbindungsabbruch. Der Kill-Switch
        hatte ausgeloest, und das Telefon blieb still.

        Wenn ueberhaupt eine Nachricht wichtig ist, dann diese - und sie ist
        genau dann am wichtigsten, wenn gerade etwas nicht funktioniert.
        """
        fehlschlag: str | None = None
        geschlossen = True
        storniert = False
        try:
            storniert = self._alles_glattstellen("Kill-Switch")
        except Exception as exc:
            fehlschlag = str(exc)
            geschlossen = False
            log.critical(
                "live.notausstieg_fehlgeschlagen",
                fehler=str(exc),
                hinweis="Position kann noch offen sein - von Hand bei Bybit pruefen",
            )

        # **Wiederholen, solange noch jemand da ist.** Der Not-Aus ist die
        # letzte Handlung dieses Prozesses - gleich danach haelt er an. Ein
        # einmal misslungenes Storno bekaeme also nie eine zweite Gelegenheit,
        # und die Restorders lagen im Buch, bis jemand von Hand nachsieht.
        for _ in range(STORNO_VERSUCHE - 1):
            if storniert:
                break
            storniert = self.router.close_all("Kill-Switch (Wiederholung)")
        if not storniert and fehlschlag is None:
            fehlschlag = "Orders liessen sich nicht stornieren"

        if geschlossen:
            self._bracket_abschliessen("Kill-Switch", storniert=storniert)
        # Sonst bleibt das Bracket stehen: Die Position ist womoeglich noch
        # offen, und ein weggeworfenes Bracket hiesse, dass niemand mehr
        # hinsieht.

        nachsatz = (
            "Alles glattgestellt. Handel gestoppt bis zur manuellen Freigabe."
            if fehlschlag is None
            else f"ACHTUNG: Glattstellen fehlgeschlagen ({fehlschlag}). "
            "Position kann noch offen sein - bitte sofort bei Bybit nachsehen."
        )
        self._report(
            EventKind.KILL,
            f"KILL-SWITCH: {self.officer.state.kill_reason}. {nachsatz}",
            equity=self.last_equity,
            glattstellen_ok=fehlschlag is None,
        )
        await self._notify(
            f"KILL-SWITCH AUSGELOEST\n{self.officer.state.kill_reason}\n{nachsatz}"
        )
        self.stop()

    async def _manage_open_position(self) -> None:
        """Fills gegen die Boerse abgleichen.

        Der Router weiss nicht von sich aus, ob eine Order gefuellt wurde -
        das erfaehrt er nur durch Nachfragen. Ein Abgleich je Kerze reicht,
        weil Stop und Ziele boersenseitig liegen und ohne uns funktionieren.
        """
        if self.bracket is None:
            return

        if self.bracket.state is BracketState.PENDING_ENTRY:
            await self._check_entry_fill()
            return

        if not self.bracket.is_open:
            # CLOSED oder EXPIRED - der Platz ist wieder frei. Wird das
            # vergessen, blockiert ein erledigtes Bracket jeden weiteren Trade.
            self._bracket_abschliessen("Bracket erledigt")
            return

        position = self._first_position()
        if position is None:
            self._record_trade(
                exit_price=self.bracket.stop_price or self.bracket.entry_price or Decimal(0),
                reason=f"{self.bracket.targets_hit} Ziele erreicht",
            )
            self._report(
                EventKind.EXIT,
                f"Position geschlossen nach {self.bracket.targets_hit} Zielen. "
                f"Ergebnis {self.last_equity - self.equity_at_entry:+.2f}",
                targets_hit=self.bracket.targets_hit,
                pnl=self.last_equity - self.equity_at_entry,
                equity=self.last_equity,
            )
            await self._notify(
                f"Position geschlossen. {self.bracket.targets_hit} Ziele erreicht."
            )
            self.bracket.state = BracketState.CLOSED
            self._bracket_abschliessen("Position an der Boerse geschlossen")
            return

        if position.size > self.bracket.remaining_qty:
            # Die Position ist **gewachsen**, obwohl wir nichts gekauft haben.
            #
            # Das passiert, wenn ein Rest der Einstiegsorder doch noch gefuellt
            # wurde - ``OrderRouter.protect`` nimmt ihn zwar aus dem Markt,
            # aber das kann fehlschlagen. Der Stop deckt dann nur die alte
            # Menge, und der Rest laeuft ungeschuetzt.
            #
            # Eine Position ohne vollen Stop ist der gefaehrlichste Zustand
            # ueberhaupt. Deshalb wird hier nicht nachgebessert, sondern
            # sofort geschlossen: Ein unnoetiger Ausstieg kostet Gebuehren,
            # ein ungeschuetzter Rest kann das Konto kosten.
            ueberzaehlig = position.size - self.bracket.remaining_qty
            log.critical(
                "live.position_gewachsen",
                erwartet=str(self.bracket.remaining_qty),
                gefunden=str(position.size),
                ueberzaehlig=str(ueberzaehlig),
            )
            # Die **tatsaechliche** Menge schliessen, nicht die vermerkte -
            # sonst bliebe genau der ungeschuetzte Rest stehen.
            storniert = self.router.emergency_close(
                self.bracket,
                reason="Position groesser als abgesichert",
                qty=position.size,
            )
            self._report(
                EventKind.WARNING,
                f"Position war {position.size} statt {self.bracket.remaining_qty} - "
                f"{ueberzaehlig} lief ohne Stop. Alles sofort geschlossen.",
                erwartet=self.bracket.remaining_qty,
                gefunden=position.size,
            )
            await self._notify(
                f"WARNUNG: Position groesser als abgesichert "
                f"({position.size} statt {self.bracket.remaining_qty}). "
                "Sofort geschlossen."
            )
            self.bracket.state = BracketState.CLOSED
            self._bracket_abschliessen(
                "Position groesser als abgesichert", storniert=storniert
            )
            return

        if position.size < self.bracket.remaining_qty:
            filled = self.bracket.remaining_qty - position.size
            self.router.on_target_hit(self.bracket, qty=filled)
            self._report(
                EventKind.TARGET,
                f"Ziel {self.bracket.targets_hit} erreicht, {filled} verkauft. "
                f"Stop steht bei {self.bracket.stop_price}.",
                target=self.bracket.targets_hit,
                qty=filled,
                stop_price=self.bracket.stop_price,
                at_breakeven=self.bracket.moved_to_breakeven,
            )
            await self._notify(
                f"Ziel {self.bracket.targets_hit} erreicht ({filled} verkauft). "
                f"Stop steht bei {self.bracket.stop_price}."
            )

    def _nacharbeit_erledigt(self) -> bool:
        """Ein fehlgeschlagenes Aufraeumen wiederholen. ``True`` heisst: frei.

        Der Fuzzer hat die Luecke gezeigt: Schlaegt das Storno beim Abschluss
        eines Trades fehl - ein Netzwackler genuegt -, bleiben die Restziele im
        Buch, und **niemand kommt je darauf zurueck**. Der naechste Einstieg
        laeuft dann in die alten Verkaufslimits.

        Solange das Aufraeumen nicht durchgegangen ist, wird kein neuer Trade
        eroeffnet. Das ist die richtige Richtung: Ein verpasster Einstieg
        kostet eine Gelegenheit, ein Einstieg in ein unaufgeraeumtes Buch
        kostet Geld.
        """
        if self._aufraeumen_offen is None:
            return True
        if self.router.close_all(f"Nachholen: {self._aufraeumen_offen}"):
            log.info("live.aufraeumen_nachgeholt", grund=self._aufraeumen_offen)
            self._aufraeumen_offen = None
            return True
        log.warning(
            "live.aufraeumen_offen",
            grund=self._aufraeumen_offen,
            hinweis="Keine neuen Einstiege, solange Restorders im Buch stehen koennen",
        )
        return False

    def _bracket_abschliessen(self, grund: str, *, storniert: bool | None = None) -> None:
        """Bracket ablegen - und die uebrigen Orders aus dem Buch nehmen.

        ``storniert`` sagt, ob die Orders schon weg sind: ``None`` heisst
        "bitte selbst stornieren", ein Wahrheitswert ist das Ergebnis eines
        Stornos, das der Aufrufer bereits ausgeloest hat (``emergency_close``
        storniert selbst). So laeuft jeder Abschluss durch **eine** Stelle, und
        ein misslungenes Storno bleibt an genau einem Ort vermerkt.

        Der zweite Teil fehlte, und der Ausfuehrungs-Fuzzer hat gezeigt, was
        das bedeutet: Greift der Stop an der Boerse oder faellt das erste Ziel,
        ist die Position weg - die **restlichen** Ziele bleiben aber als
        Reduce-Only-Limits liegen. Gemessen in einer Zufallsfolge: 0,002 an
        Zielen im Buch bei 0 Position.

        Reduce-Only verhindert, dass daraus eine Gegenposition wird. Es
        verhindert nicht, dass sie den **naechsten** Trade sofort anschneiden:
        Ein neuer Long laeuft in genau die alten Verkaufslimits, die noch ueber
        dem Markt haengen - und wird verkleinert, bevor er ueberhaupt angefangen
        hat. Der Backtest kennt so etwas nicht, also waere die Abweichung als
        schwaechere Rendite erschienen, nicht als Fehler.

        Ob Bybit Reduce-Only-Orders beim Schliessen einer Position von selbst
        raeumt, laesst sich aus diesem Container nicht pruefen. Darauf zu
        vertrauen waere eine Annahme, und Annahmen sind in diesem Projekt
        bereits mehrfach teuer geworden. Ein Storno kostet einen API-Aufruf je
        beendetem Trade.
        """
        self.bracket = None
        if storniert is None:
            storniert = self.router.close_all(grund)
        self._aufraeumen_offen = None if storniert else grund

    def _track_excursion(self, candle: Candle) -> None:
        """Groessten Gegen- und Vorlauf mitschreiben, solange die Position lebt.

        MAE und MFE sind die beiden Zahlen, aus denen sich spaeter ablesen
        laesst, ob Stop und Ziele richtig sitzen - siehe research/exits.py.
        Sie lassen sich **nur waehrend** des Trades erheben; im Nachhinein sind
        sie aus der Ausfuehrungshistorie nicht mehr rekonstruierbar.
        """
        bracket = self.bracket
        if bracket is None or not bracket.is_open or bracket.entry_price is None:
            return

        entry = bracket.entry_price
        qty = bracket.filled_qty
        if bracket.signal.side is Side.BUY:
            adverse = (entry - candle.low) * qty
            favourable = (candle.high - entry) * qty
        else:
            adverse = (candle.high - entry) * qty
            favourable = (entry - candle.low) * qty

        self._mae = max(self._mae, max(Decimal(0), adverse))
        self._mfe = max(self._mfe, max(Decimal(0), favourable))

    def _record_trade(self, exit_price: Decimal, reason: str) -> None:
        """Den abgeschlossenen Trade festhalten.

        Grundlage fuer die woechentliche Ueberpruefung (``cli review``): Verfall,
        Marktphasen, Ausstiegsqualitaet. Ohne diese Zeilen gibt es spaeter
        nichts auszuwerten ausser dem Kontostand - und der sagt nicht, *warum*
        etwas nicht mehr funktioniert.

        Das Ergebnis wird aus der **Kapitaldifferenz** bestimmt, nicht aus
        Preisen: Darin stecken Gebuehren und Funding bereits drin, ohne dass
        wir sie einzeln nachschlagen muessen.
        """
        bracket = self.bracket
        if bracket is None or bracket.entry_price is None or self.journal is None:
            return

        net = self.last_equity - self.equity_at_entry
        trade = Trade(
            trade_id=f"{bracket.signal.strategy_id}-{bracket.opened_at:%Y%m%d%H%M%S}"
            if bracket.opened_at
            else f"{bracket.signal.strategy_id}-{datetime.now(UTC):%Y%m%d%H%M%S}",
            symbol=self.instrument.symbol,
            side=bracket.signal.side,
            strategy_id=self.strategy.strategy_id,
            entry_time=bracket.opened_at or datetime.now(UTC),
            entry_price=bracket.entry_price,
            exit_time=datetime.now(UTC),
            exit_price=exit_price,
            qty=bracket.filled_qty,
            gross_pnl=net,
            fees=Decimal(0),  # bereits in der Kapitaldifferenz enthalten
            stop_loss=bracket.signal.stop_loss,
            exit_reason=reason,
            leverage=bracket.sized.leverage,
            max_adverse_excursion=self._mae,
            max_favourable_excursion=self._mfe,
        )
        with contextlib.suppress(Exception):
            self.journal.record_trade(trade)

        self._mae = Decimal(0)
        self._mfe = Decimal(0)

    def _first_position(self) -> Position | None:
        positions = self.account.get_positions(self.instrument.symbol)
        return positions[0] if positions else None

    async def _check_entry_fill(self) -> None:
        assert self.bracket is not None
        self._bars_since_entry_placed += 1

        position = self._first_position()
        if position is not None:
            await self._protect(position)
            return

        if self._bars_since_entry_placed >= self.entry_expiry_bars:
            self.router.expire_entry(self.bracket)
            self._bars_since_entry_placed = 0

            # Zwischen Abfrage und Storno kann die Order noch gefuellt worden
            # sein. Dann steht jetzt eine Position im Markt, von der wir nichts
            # wissen - und ohne Stop. Der einzige Fall, in dem ein Storno
            # gefaehrlich ist, und deshalb wird danach noch einmal nachgesehen.
            late = self._first_position()
            if late is not None:
                log.warning(
                    "live.spaeter_fill",
                    hinweis="Order wurde beim Stornieren doch noch gefuellt",
                    groesse=str(late.size),
                )
                await self._protect(late)
                return

            self.stats.entries_expired += 1
            self.bracket = None

    async def _protect(self, position: Position) -> None:
        """Stop und Ziele setzen - und einen Fehlschlag ueberleben."""
        assert self.bracket is not None
        try:
            self.router.protect(
                self.bracket, filled_qty=position.size, fill_price=position.entry_price
            )
        except Exception as exc:
            # Hier stand "``protect`` schliesst die Position selbst" - und
            # daraufhin wurde das Bracket weggeworfen. Der Fuzzer hat gezeigt,
            # dass die Annahme nicht traegt: Wenn ein **Ziel** nicht platziert
            # werden konnte, war der Stop laengst gesetzt und die Position lief
            # weiter - ohne Bracket, also ohne Ziele, ohne Nachzug auf Einstand
            # und ohne Ausstiegsbedingung.
            #
            # Deshalb wird jetzt nachgesehen statt angenommen. Nachsehen kostet
            # einen Aufruf; die Annahme kostete die Kontrolle ueber eine offene
            # Position.
            log.error("live.absicherung_fehlgeschlagen", fehler=str(exc))
            await self._handle_protect_failure(exc)
            return

        if self.bracket.failed_targets:
            self._report(
                EventKind.WARNING,
                f"{self.bracket.failed_targets} von "
                f"{len(self.bracket.signal.take_profits)} Zielen liessen sich "
                f"nicht platzieren. Stop steht, aber die Position hat weniger "
                f"Ausstiege als geplant.",
                failed_targets=self.bracket.failed_targets,
            )
            await self._notify(
                f"Hinweis: {self.bracket.failed_targets} Ziel(e) konnten nicht "
                f"platziert werden (meist, weil der Kurs schon daran vorbei "
                f"ist). Stop steht."
            )

        self.stats.entries_filled += 1
        self._bars_since_entry_placed = 0
        self.equity_at_entry = self.last_equity
        self._mae = Decimal(0)
        self._mfe = Decimal(0)
        self._report(
            EventKind.ENTRY,
            f"Einstieg {self.bracket.signal.side.value} {position.size} @ "
            f"{position.entry_price}, Stop {self.bracket.stop_price}",
            side=self.bracket.signal.side.value,
            qty=position.size,
            entry_price=position.entry_price,
            stop_price=self.bracket.stop_price,
            leverage=self.bracket.sized.leverage,
            risk_amount=self.bracket.sized.risk_amount,
            reason=self.bracket.signal.reason,
        )
        await self._notify(
            f"EINSTIEG {self.bracket.signal.side.value} {position.size} "
            f"@ {position.entry_price}\n"
            f"Stop {self.bracket.stop_price} | "
            f"Hebel {self.bracket.sized.leverage:.2f}x | "
            f"Risiko {self.bracket.sized.risk_amount:.2f}"
        )

    async def _handle_protect_failure(self, exc: Exception) -> None:
        """Die Absicherung ist gescheitert - was steht jetzt wirklich im Markt?

        Drei Faelle, und sie brauchen drei verschiedene Antworten:

        1. **Keine Position mehr.** ``protect`` hat sie beim fehlgeschlagenen
           Stop selbst geschlossen. Aufraeumen, Platz freigeben, fertig.
        2. **Position da, Schliessen geht.** Der gefaehrliche Fall: Sie hat
           womoeglich keinen Stop. Sofort glattstellen - ein unnoetiger
           Ausstieg kostet Gebuehren, eine ungeschuetzte Position das Konto.
        3. **Position da, Schliessen geht auch nicht.** Dann bleibt das Bracket
           **stehen**. Es wegzuwerfen waere das Schlimmste: Die Position liefe
           weiter, und niemand sieht mehr hin. So versucht es die naechste
           Kerze erneut, und die Invariantenpruefung meldet den Zustand aufs
           Telefon.
        """
        assert self.bracket is not None
        rest = self._first_position()

        if rest is None:
            await self._notify(
                f"Stop konnte nicht gesetzt werden - Position wurde sofort "
                f"geschlossen: {exc}"
            )
            self._bracket_abschliessen("Absicherung fehlgeschlagen")
            return

        log.critical(
            "live.absicherung_unvollstaendig",
            groesse=str(rest.size),
            stop=str(rest.stop_loss) if rest.stop_loss else None,
            massnahme="Position wird geschlossen",
        )
        try:
            storniert = self.router.emergency_close(
                self.bracket, reason="Absicherung fehlgeschlagen", qty=rest.size
            )
        except Exception as zweiter:
            log.critical(
                "live.notausstieg_fehlgeschlagen",
                fehler=str(zweiter),
                hinweis="Bracket bleibt stehen - naechste Kerze versucht es erneut",
            )
            self._report(
                EventKind.WARNING,
                f"Position {rest.size} liess sich weder absichern noch "
                f"schliessen ({zweiter}). Bitte sofort bei Bybit nachsehen.",
            )
            await self._notify(
                f"DRINGEND: Position {rest.size} konnte weder abgesichert noch "
                f"geschlossen werden.\n{exc}\n{zweiter}\n"
                "Bitte sofort bei Bybit nachsehen."
            )
            return

        await self._notify(
            f"Absicherung fehlgeschlagen ({exc}) - Position {rest.size} wurde "
            "sofort geschlossen."
        )
        self._bracket_abschliessen("Absicherung fehlgeschlagen", storniert=storniert)

    def _equity_fraction(self, index: int):
        """Kapitalanteil fuer **diesen** Balken - so, wie die Engine ihn holt.

        Hier stand ``getattr(self.strategy, "equity_fraction", None)``, und das
        war der teuerste Fehler im Projekt bisher.

        ``equity_fraction`` ist bei Vola-Ziel-Genomen nicht der zu handelnde
        Anteil, sondern die **Obergrenze** (``sizing.fraction``). Der wirkliche
        Anteil kommt aus ``fraction_at(index)`` und aendert sich mit der
        gemessenen Schwankungsbreite. Gemessen am Spitzenkandidaten ueber 5301
        BTC-Tageskerzen:

            Backtest, Median   0,264 vom Kapital
            Backtest, Hoechst  1,595
            Livebetrieb        3,0  - immer, auf jedem Balken

        Der Betrieb haette also im Mittel **zehnmal** so grosse Positionen
        eroeffnet wie der Backtest - und die Obergrenze 3,0 wird im Backtest
        kein einziges Mal erreicht. Bei 4 % Stop und dreifachem Kapital
        genuegen wenige Prozent Gegenbewegung fuer den 15-%-Not-Aus.

        Der Backtest haette davon nie etwas gezeigt: Er rechnet richtig. Und
        ``research/live_evidenz.py`` hat ausgerechnet, dass auch der
        Demobetrieb es nicht gezeigt haette - bei 17 Trades im Jahr braeuchte
        es Jahre, um eine Abweichung von einer Pechstraehne zu unterscheiden.

        Gefunden wurde es durch Nebeneinanderlegen, nicht durch Zuschauen.
        """
        hole_anteil = getattr(self.strategy, "fraction_at", None)
        if hole_anteil is None:
            return getattr(self.strategy, "equity_fraction", None)

        anteil = hole_anteil(index)
        if anteil is None and getattr(self.strategy, "equity_fraction", None) is not None:
            # ``None`` bei einem Genom, das nach Kapitalanteil dimensioniert,
            # heisst "auf diesem Balken nicht handeln" - nicht "nimm die
            # Risikoformel". Der Unterschied ist der zwischen keiner Position
            # und einer nach ganz anderer Logik bemessenen.
            return _KEIN_HANDEL
        return anteil

    def _context(self) -> BarContext | None:
        """Die Sicht der Strategie auf den gerade geschlossenen Balken.

        ``None``, solange der Verlauf fuer die Indikatoren nicht reicht.
        """
        if len(self._frame) <= self.strategy.warmup_bars:
            return None
        arrays = frame_to_arrays(self._frame)
        indicators = self.strategy.prepare(self._frame)
        return BarContext(self._frame, arrays, indicators, len(self._frame) - 1)

    async def _check_signal_exit(self, context: BarContext, candle: Candle) -> None:
        """Raus, wenn die Strategie es sagt - nicht erst am Stop.

        Diese Pruefung fehlte, und ihr Fehlen war kein Detail: Die Engine
        schliesst 38,5 % aller Trades ueber diese Bedingung. Ohne sie laeuft
        jede Position bis zum Stop oder ins Ziel, und aus "dem Trend folgen,
        raus wenn er bricht" wird "wetten und den Stop abwarten".

        Gemessen ueber August 2017 bis August 2026 auf BTC + ETH, derselbe
        Kandidat, einmal mit und einmal ohne diese Bedingung:

                              Trades    p.a.      DD     Sharpe    DSR
            mit Ausstieg         156   11,22 %   9,74 %   1,50    0,820
            ohne (der Betrieb)   124    8,96 %  10,33 %   1,32    0,712

        Ohne sie enden 72,6 % der Trades am Stop statt 42,9 %. Der Betrieb
        haette also ein Fuenftel weniger Rendite bei groesserem Rueckgang
        geliefert - und das haette wie eine schwache Phase ausgesehen, nicht
        wie eine fehlende Funktion.

        Geschlossen wird als **Market-Order**: Die Bedingung steht erst am
        Kerzenschluss fest, und dann zaehlt, dass die Position wirklich zugeht.
        Die Engine rechnet an dieser Stelle ebenfalls mit Taker-Gebuehren.
        """
        bracket = self.bracket
        if bracket is None or not bracket.is_open:
            return
        if not wants_exit(self.strategy, context, bracket.signal.side):
            return

        log.info(
            "live.signalausstieg",
            seite=bracket.signal.side.value,
            preis=str(candle.close),
        )
        storniert = self.router.emergency_close(
            bracket, reason="Ausstiegsbedingung erfuellt"
        )
        self._record_trade(exit_price=candle.close, reason="signal_exit")
        self._report(
            EventKind.EXIT,
            f"Ausstiegsbedingung erfuellt - Position geschlossen bei "
            f"{candle.close}. Ergebnis {self.last_equity - self.equity_at_entry:+.2f}",
            pnl=self.last_equity - self.equity_at_entry,
            equity=self.last_equity,
            exit_price=candle.close,
        )
        await self._notify(
            f"Ausstiegsbedingung erfuellt. Position geschlossen bei {candle.close}."
        )
        bracket.state = BracketState.CLOSED
        self._bracket_abschliessen("Ausstiegsbedingung", storniert=storniert)

    async def _look_for_entry(self, context: BarContext) -> None:
        """Strategie fragen, Risk-Officer fragen, gegebenenfalls handeln."""
        signal = self.strategy.on_bar(context)
        if signal is None:
            return

        self.stats.signals_generated += 1
        equity = self._current_equity()
        open_positions = len(self.account.get_positions(self.instrument.symbol))

        anteil = self._equity_fraction(context.index)
        if anteil is _KEIN_HANDEL:
            # Die Groessenlogik sagt fuer diesen Balken "nicht handeln" - etwa
            # weil die gemessene Schwankungsbreite noch fehlt. Das ist kein
            # Fehler und kein Veto, sondern schlicht kein Trade.
            log.info("live.kein_anteil", grund="Groessenlogik liefert keinen Anteil")
            return

        decision = self.officer.evaluate(
            signal,
            equity=equity,
            open_positions=open_positions,
            equity_fraction=anteil,
        )

        if isinstance(decision, Vetoed):
            self.stats.count_veto(decision.reason.value)
            log.info("live.signal_abgelehnt", grund=decision.describe())
            self._report(
                EventKind.VETO,
                f"Signal abgelehnt - {decision.detail}",
                reason=decision.reason.value,
                side=signal.side.value,
            )
            return

        assert isinstance(decision, Approved)
        try:
            self.bracket = self.router.open(signal, decision.sized)
            self.stats.entries_placed += 1
            self._bars_since_entry_placed = 0
            self._report(
                EventKind.SIGNAL,
                f"Einstiegsorder {signal.side.value} {decision.sized.qty} @ "
                f"{signal.entry_price} - {signal.reason}",
                side=signal.side.value,
                qty=decision.sized.qty,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                leverage=decision.sized.leverage,
            )
        except Exception as exc:
            log.error("live.einstieg_fehlgeschlagen", fehler=str(exc))
            self._report(EventKind.WARNING, f"Einstieg fehlgeschlagen: {exc}")
            await self._notify(f"Einstieg fehlgeschlagen: {exc}")
            self.bracket = None

    # -- Benachrichtigung ----------------------------------------------------
    async def _notify(self, message: str) -> None:
        if self.notifier is None:
            return
        with contextlib.suppress(Exception):
            await self.notifier(message)


async def telegram_notifier(bot_token: str, chat_id: str) -> Notifier:
    """Erzeugt eine Telegram-Benachrichtigungsfunktion.

    Bewusst fehlertolerant: Ein Ausfall des Benachrichtigungsdienstes darf den
    Handel niemals stoppen.
    """
    import httpx

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async def send(message: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"chat_id": chat_id, "text": message})

    return send
