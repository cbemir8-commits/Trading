"""Tests der Live-Schleife.

Hier wird geprueft, was zwischen Signal und Boerse passiert - und vor allem,
was passiert, wenn etwas schiefgeht. Die Schleife ist der einzige Teil des
Systems, der nachts unbeaufsichtigt laeuft; jeder Pfad, der sie beenden oder
eine ungeschuetzte Position hinterlassen koennte, gehoert getestet.

Die drei wichtigsten Tests:

* ``test_position_without_stop_is_closed_immediately`` - der Zustandsabgleich
  beim Start. Ein Neustart mitten in einer Position ist der Normalfall, nicht
  die Ausnahme.
* ``test_no_second_entry_while_one_is_pending`` - ein Bracket, das auf seinen
  Fill wartet, ist nicht ``is_open``. Wer das verwechselt, legt bei jedem
  Signal eine weitere Einstiegsorder nach.
* ``test_late_fill_during_cancel_is_still_protected`` - zwischen Abfrage und
  Storno kann die Order noch gefuellt werden. Genau dann steht eine Position
  im Markt, von der niemand weiss.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.config import BybitSettings, RiskSettings
from core.models import Candle, Instrument, Interval, Signal
from data.bybit.errors import BybitAPIError, BybitTransportError
from data.store import CandleStore
from execution.live import LiveTrader
from execution.risk import RiskOfficer, VetoReason
from execution.router import BracketState
from tests.factories import make_candles, make_signal
from tests.fake_exchange import FakeAccount, FakeExchange
from tests.fakes import FakeMarketData
from web.journal import CommandAction, EventKind, LiveJournal, read_view, send_command

HISTORY_BARS = 60
MARK_PRICE = Decimal("100000")


class QueuedStrategy:
    """Gibt bei jedem Aufruf das naechste vorgemerkte Signal aus.

    Fuer die Live-Schleife ist eine indexbasierte Strategie unbrauchbar: Der
    Index ist hier immer die letzte Kerze des Puffers. Was zaehlt, ist die
    Reihenfolge der Aufrufe.
    """

    strategy_id = "queued"

    def __init__(self, *signals: Signal, warmup_bars: int = 5) -> None:
        self.queue: list[Signal] = list(signals)
        self.warmup_bars = warmup_bars
        self.calls = 0

    def emit(self, signal: Signal) -> None:
        self.queue.append(signal)

    def prepare(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        return {}

    def on_bar(self, ctx) -> Signal | None:
        self.calls += 1
        return self.queue.pop(0) if self.queue else None


@dataclass
class Rig:
    """Der Handelsroboter samt aller Doubles, die ihn umgeben."""

    trader: LiveTrader
    exchange: FakeExchange
    account: FakeAccount
    officer: RiskOfficer
    strategy: QueuedStrategy
    messages: list[str]
    next_open: datetime
    state_dir: Path

    async def feed(self, *, close: Decimal | None = None) -> Candle:
        """Die naechste abgeschlossene Kerze zustellen."""
        price = close if close is not None else MARK_PRICE
        candle = Candle(
            open_time=self.next_open,
            open=price,
            high=price + Decimal("50"),
            low=price - Decimal("50"),
            close=price,
            volume=Decimal("10"),
            turnover=Decimal("1000000"),
        )
        self.next_open = self.next_open + Interval.M15.duration
        await self.trader._on_candle(candle, Interval.M15)
        return candle

    @property
    def entry_orders(self) -> list[dict]:
        """Nur die Einstiegsorders - Ziele und Spot-Stops sind reduce_only."""
        return [
            kwargs
            for name, kwargs in self.exchange.calls
            if name == "place_limit" and not kwargs.get("reduce_only")
        ]

    def fill_entry(self) -> Decimal:
        assert self.trader.bracket is not None
        assert self.trader.bracket.entry_order is not None
        return self.exchange.fill(self.trader.bracket.entry_order.order_id)


def build_rig(
    tmp_path,
    btcusdt: Instrument,
    risk: RiskSettings,
    settings: BybitSettings,
    *,
    strategy: QueuedStrategy | None = None,
    with_history: bool = True,
    entry_expiry_bars: int = 3,
    equity: Decimal = Decimal("500"),
) -> Rig:
    store = CandleStore(tmp_path / "store")
    start = datetime(2026, 1, 1, tzinfo=UTC)

    if with_history:
        history = make_candles(count=HISTORY_BARS, start=start, step=Decimal(0))
        store.write("BTCUSDT", Interval.M15, history)
        next_open = history[-1].open_time + Interval.M15.duration
    else:
        next_open = start

    exchange = FakeExchange(mark_price=MARK_PRICE)
    account = FakeAccount(exchange, equity=equity)
    officer = RiskOfficer(risk, btcusdt, state_path=tmp_path / "risk.json")
    messages: list[str] = []

    async def notifier(message: str) -> None:
        messages.append(message)

    trader = LiveTrader(
        settings=settings,
        strategy=strategy or QueuedStrategy(),
        instrument=btcusdt,
        risk_settings=risk,
        market=FakeMarketData(),
        account=account,
        gateway=exchange,
        officer=officer,
        store=store,
        interval=Interval.M15,
        notifier=notifier,
        entry_expiry_bars=entry_expiry_bars,
        journal=LiveJournal(tmp_path / "state"),
    )
    trader._load_history()

    return Rig(
        trader=trader,
        exchange=exchange,
        account=account,
        officer=officer,
        strategy=trader.strategy,  # type: ignore[arg-type]
        messages=messages,
        next_open=next_open,
        state_dir=tmp_path / "state",
    )


@pytest.fixture
def rig(tmp_path, btcusdt: Instrument, risk: RiskSettings, bybit_settings: BybitSettings) -> Rig:
    return build_rig(
        tmp_path, btcusdt, risk, bybit_settings, strategy=QueuedStrategy()
    )


def long_below_market() -> Signal:
    """Ein Long-Signal unterhalb des Marktes - PostOnly wird angenommen."""
    return make_signal(entry="99500", stop_pct="0.6")


# ---------------------------------------------------------------------------
#  Zustandsabgleich beim Start
# ---------------------------------------------------------------------------
class TestStartupReconciliation:
    async def test_orphaned_orders_are_cancelled_when_flat(self, rig: Rig) -> None:
        """Ohne Position duerfen keine Orders aus einem frueheren Lauf stehen.

        Eine vergessene Einstiegsorder fuellt irgendwann - und dann steht eine
        Position im Markt, die dieser Prozess nie gesehen hat.
        """
        await rig.trader._reconcile()

        assert "cancel_all" in rig.exchange.call_order

    async def test_position_without_stop_is_closed_immediately(self, rig: Rig) -> None:
        """Der gefaehrlichste Zustand ueberhaupt.

        Eine offene Position ohne Stop kann das Konto kosten. Sie zu schliessen
        kostet eine Taker-Gebuehr. Die Entscheidung faellt nicht schwer.
        """
        rig.exchange.position = _position(rig, stop=None)

        await rig.trader._reconcile()

        assert rig.exchange.position is None
        assert "place_market" in rig.exchange.call_order
        assert any("ohne Stop" in m for m in rig.messages)

    async def test_zero_stop_counts_as_no_stop(self, rig: Rig) -> None:
        """Bybit liefert fuer 'kein Stop gesetzt' eine 0, nicht ``None``.

        Wer nur auf ``None`` prueft, haelt eine ungeschuetzte Position fuer
        abgesichert.
        """
        rig.exchange.position = _position(rig, stop=Decimal(0))

        await rig.trader._reconcile()

        assert rig.exchange.position is None

    async def test_position_with_stop_is_adopted_not_closed(self, rig: Rig) -> None:
        """Ein geschuetzter Trade laeuft weiter.

        Der Stop liegt an der Position auf Bybits Servern - er hat den Neustart
        ueberlebt. Ihn zu schliessen waere ein unnoetiger Verlust.
        """
        rig.exchange.position = _position(rig, stop=Decimal("98900"))

        await rig.trader._reconcile()

        assert rig.exchange.position is not None
        assert "place_market" not in rig.exchange.call_order
        assert any("uebernommen" in m for m in rig.messages)

    async def test_adopted_position_blocks_a_second_entry(self, rig: Rig) -> None:
        """Nach der Uebernahme kennt die Schleife kein Bracket - aber der
        Risk-Officer sieht die Position am Konto und lehnt ab.

        Das ist die zweite Verteidigungslinie: Selbst wenn die Schleife den
        Ueberblick verliert, verhindert die Positionszaehlung eine zweite
        Position.
        """
        rig.exchange.position = _position(rig, stop=Decimal("98900"))
        await rig.trader._reconcile()
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert rig.entry_orders == []
        assert rig.trader.stats.veto_reasons.get(
            VetoReason.POSITION_ALREADY_OPEN.value
        ) == 1


# ---------------------------------------------------------------------------
#  Einstieg
# ---------------------------------------------------------------------------
class TestEntry:
    async def test_signal_becomes_a_postonly_entry_order(self, rig: Rig) -> None:
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert len(rig.entry_orders) == 1
        assert rig.entry_orders[0]["post_only"] is True
        assert rig.trader.bracket is not None
        assert rig.trader.bracket.state is BracketState.PENDING_ENTRY
        assert rig.trader.stats.entries_placed == 1

    async def test_no_second_entry_while_one_is_pending(self, rig: Rig) -> None:
        """Ein wartendes Bracket ist nicht ``is_open`` - aber die Order liegt
        bereits im Markt.

        Genau hier entsteht der Fehler, der aus einem Signal zwei Positionen
        macht: Die Pruefung muss auf 'gibt es ueberhaupt ein Bracket' lauten,
        nicht auf 'ist eine Position offen'.
        """
        rig.strategy.emit(long_below_market())
        rig.strategy.emit(long_below_market())

        await rig.feed()
        await rig.feed()

        assert len(rig.entry_orders) == 1, "Zweite Einstiegsorder bei offener erster"

    async def test_fill_triggers_protection(self, rig: Rig) -> None:
        """Nach dem Fill: erst Stop, dann Ziele - und beides ohne Zutun."""
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()

        await rig.feed()

        bracket = rig.trader.bracket
        assert bracket is not None
        assert bracket.state is BracketState.PROTECTED
        assert rig.exchange.position is not None
        assert rig.exchange.position.stop_loss == bracket.stop_price
        assert rig.trader.stats.entries_filled == 1
        assert any(m.startswith("EINSTIEG") for m in rig.messages)

    async def test_unfilled_entry_expires(
        self, tmp_path, btcusdt: Instrument, risk: RiskSettings,
        bybit_settings: BybitSettings,
    ) -> None:
        """Ein Setup, das nach mehreren Kerzen nicht erreicht wurde, ist meist
        nicht mehr gueltig - der Markt ist ohne uns weitergelaufen."""
        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings,
            strategy=QueuedStrategy(long_below_market()), entry_expiry_bars=2,
        )

        await rig.feed()  # Einstieg platziert
        await rig.feed()  # 1. Kerze ohne Fill
        assert rig.trader.bracket is not None

        await rig.feed()  # 2. Kerze ohne Fill -> Ablauf

        assert rig.trader.bracket is None
        assert rig.trader.stats.entries_expired == 1
        entry_id = next(
            o.order_id for o in rig.exchange.orders.values() if not o.reduce_only
        )
        assert rig.exchange.orders[entry_id].status.is_terminal

    async def test_late_fill_during_cancel_is_still_protected(
        self, tmp_path, btcusdt: Instrument, risk: RiskSettings,
        bybit_settings: BybitSettings,
    ) -> None:
        """Das Rennen zwischen Fill und Storno.

        Wird die Order gefuellt, waehrend wir sie stornieren, steht eine
        Position im Markt, von der wir nichts wissen - und ohne Stop. Deshalb
        wird nach jedem Storno noch einmal nachgesehen.
        """
        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings,
            strategy=QueuedStrategy(long_below_market()), entry_expiry_bars=1,
        )
        exchange = rig.exchange
        original_cancel = exchange.cancel_order

        def cancel_but_fill(*, symbol: str, order_id: str) -> None:
            exchange.fill(order_id)  # der Fill gewinnt das Rennen
            original_cancel(symbol=symbol, order_id=order_id)

        exchange.cancel_order = cancel_but_fill  # type: ignore[method-assign]

        await rig.feed()  # Einstieg platziert
        await rig.feed()  # Ablauf -> Storno, das den Fill ausloest

        assert exchange.position is not None
        assert exchange.position.stop_loss is not None, (
            "Position aus dem Storno-Rennen blieb ungeschuetzt"
        )
        assert rig.trader.bracket is not None
        assert rig.trader.bracket.state is BracketState.PROTECTED
        assert rig.trader.stats.entries_expired == 0

    async def test_order_error_does_not_stop_the_loop(self, rig: Rig) -> None:
        """Eine abgelehnte Order ist Alltag, kein Grund aufzuhoeren.

        PostOnly-Ablehnungen passieren staendig, wenn der Markt beim Platzieren
        durch den Einstiegspreis laeuft. Der Roboter muss die naechste Kerze
        normal weiterarbeiten.
        """
        rig.strategy.emit(long_below_market())
        rig.exchange.fail_next(
            "place_limit", BybitAPIError(110001, "PostOnly", endpoint="/v5/order/create")
        )

        await rig.feed()

        assert rig.trader.bracket is None
        assert any("fehlgeschlagen" in m for m in rig.messages)

        rig.strategy.emit(long_below_market())
        await rig.feed()

        assert rig.trader.bracket is not None, "Roboter hat nach einem Orderfehler aufgegeben"

    async def test_protect_failure_frees_the_slot(self, rig: Rig) -> None:
        """Scheitert der Stop, schliesst der Router die Position - und die
        Schleife muss danach weiterlaufen koennen, nicht mit einem toten
        Bracket dastehen."""
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()
        rig.exchange.fail_next("set_position_stop", BybitTransportError("Netz weg"))

        await rig.feed()

        assert rig.trader.bracket is None
        assert rig.exchange.position is None
        assert any("Stop konnte nicht gesetzt werden" in m for m in rig.messages)


# ---------------------------------------------------------------------------
#  Risk-Officer
# ---------------------------------------------------------------------------
class TestVeto:
    async def test_vetoed_signal_never_reaches_the_exchange(self, rig: Rig) -> None:
        """Der Risk-Officer sitzt vor dem Router, nicht daneben."""
        rig.officer.pause("Test")
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert rig.exchange.calls == [], "Kein Aufruf an die Boerse bei Veto"
        assert rig.trader.bracket is None

    async def test_veto_reasons_are_counted(self, rig: Rig) -> None:
        """Fuer das Dashboard: Warum wurde nicht gehandelt, ist genauso
        wichtig wie was gehandelt wurde."""
        rig.officer.pause("Test")
        rig.strategy.emit(long_below_market())
        rig.strategy.emit(long_below_market())

        await rig.feed()
        await rig.feed()

        assert rig.trader.stats.signals_generated == 2
        assert rig.trader.stats.signals_vetoed == 2
        assert rig.trader.stats.veto_reasons == {VetoReason.TRADING_PAUSED.value: 2}


class TestKillSwitch:
    async def test_drawdown_closes_the_open_position(self, rig: Rig) -> None:
        """Der Kill-Switch greift auch ohne Signal.

        Genau dafuer wird der Kapitalstand bei jeder Kerze gemeldet und nicht
        nur beim Handeln: Eine offene Position kann ins Minus laufen, waehrend
        gar kein neues Signal ansteht.
        """
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()
        await rig.feed()
        assert rig.trader.bracket is not None

        rig.account.set_equity(Decimal("420"))  # 16 % unter dem Hoechststand
        await rig.feed()

        assert rig.exchange.position is None
        assert "place_market" in rig.exchange.call_order
        assert any("KILL-SWITCH" in m for m in rig.messages)

    async def test_kill_switch_blocks_further_entries(self, rig: Rig) -> None:
        rig.officer.observe_equity(Decimal("500"))
        rig.officer.trigger_kill_switch("Test")
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert rig.entry_orders == []
        assert rig.strategy.calls == 0, "Nach dem Kill-Switch wird gar nicht erst gefragt"

    async def test_kill_switch_survives_a_restart(
        self, tmp_path, btcusdt: Instrument, risk: RiskSettings,
        bybit_settings: BybitSettings,
    ) -> None:
        """Der Zustand liegt auf der Platte, nicht im Speicher.

        Ein Prozess, der nach einem Absturz neu startet und vergessen hat, dass
        er sich abgeschaltet hat, handelt munter weiter - und das ausgerechnet
        in dem Moment, in dem etwas schiefgelaufen ist.
        """
        first = build_rig(tmp_path, btcusdt, risk, bybit_settings)
        first.officer.observe_equity(Decimal("500"))
        first.officer.trigger_kill_switch("Drawdown-Grenze erreicht")

        second = build_rig(
            tmp_path, btcusdt, risk, bybit_settings,
            strategy=QueuedStrategy(long_below_market()),
        )
        await second.feed()

        assert second.entry_orders == []
        assert second.officer.state.kill_reason == "Drawdown-Grenze erreicht"


# ---------------------------------------------------------------------------
#  Positionsfuehrung
# ---------------------------------------------------------------------------
class TestPositionManagement:
    async def test_target_fill_moves_stop_to_breakeven(self, rig: Rig) -> None:
        """Nach dem ersten Ziel kann der Trade nicht mehr ins Minus laufen."""
        bracket = await _open_protected(rig)
        entry_price = bracket.entry_price

        rig.exchange.fill(bracket.take_profit_orders[0].order_id)
        await rig.feed()

        assert bracket.targets_hit == 1
        assert bracket.moved_to_breakeven
        assert rig.exchange.position.stop_loss == entry_price
        assert any("Ziel 1 erreicht" in m for m in rig.messages)

    async def test_external_close_frees_the_slot(self, rig: Rig) -> None:
        """Der Stop liegt an der Boerse - er kann greifen, ohne dass wir davon
        etwas mitbekommen. Beim naechsten Abgleich muss der Platz frei sein."""
        await _open_protected(rig)
        rig.exchange.position = None  # Stop hat ausgeloest

        await rig.feed()

        assert rig.trader.bracket is None
        assert any("Position geschlossen" in m for m in rig.messages)

    async def test_next_trade_starts_after_a_close(self, rig: Rig) -> None:
        """Ein erledigtes Bracket darf den naechsten Trade nicht blockieren."""
        await _open_protected(rig)
        rig.exchange.position = None
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert len(rig.entry_orders) == 2
        assert rig.trader.bracket is not None
        assert rig.trader.bracket.state is BracketState.PENDING_ENTRY


# ---------------------------------------------------------------------------
#  Robustheit
# ---------------------------------------------------------------------------
class TestRobustness:
    async def test_notifier_failure_does_not_stop_trading(self, rig: Rig) -> None:
        """Telegram ist Komfort, nicht Infrastruktur.

        Ein Ausfall des Benachrichtigungsdienstes darf den Handel nie stoppen -
        sonst haengt das Handelssystem an der Verfuegbarkeit eines Chatdienstes.
        """
        async def broken(message: str) -> None:
            raise RuntimeError("Telegram nicht erreichbar")

        rig.trader.notifier = broken
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()
        await rig.feed()

        assert rig.trader.bracket is not None
        assert rig.trader.bracket.state is BracketState.PROTECTED

    async def test_store_failure_does_not_stop_trading(self, rig: Rig) -> None:
        """Kerzen lassen sich nachladen, eine offene Position nicht."""
        def broken(*args, **kwargs):
            raise OSError("Platte voll")

        rig.trader.store.write = broken  # type: ignore[method-assign]
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert rig.trader.stats.candles_seen == 1
        assert rig.trader.bracket is not None

    async def test_duplicate_candle_is_ignored(self, rig: Rig) -> None:
        """Nach einem Verbindungsabbruch liefert die Nachfuellung Kerzen, die
        der Stream schon gebracht hat. Doppelte Zeilen im Puffer wuerden jeden
        Indikator verfaelschen."""
        before = len(rig.trader._frame)
        candle = await rig.feed()
        await rig.trader._on_candle(candle, Interval.M15)

        assert len(rig.trader._frame) == before + 1
        assert rig.trader.stats.candles_seen == 2

    async def test_other_intervals_are_ignored(self, rig: Rig) -> None:
        """Der Stream kann mehrere Intervalle fuehren - gehandelt wird eines."""
        candle = make_candles(count=1, start=rig.next_open)[0]

        await rig.trader._on_candle(candle, Interval.H1)

        assert rig.trader.stats.candles_seen == 0

    async def test_warmup_is_respected_without_history(
        self, tmp_path, btcusdt: Instrument, risk: RiskSettings,
        bybit_settings: BybitSettings,
    ) -> None:
        """Ohne Vorlauf wird nicht gehandelt.

        Ein Indikator, der noch nicht eingeschwungen ist, liefert Unsinn - und
        Unsinn mit echtem Geld ist teurer als Warten.
        """
        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings,
            strategy=QueuedStrategy(long_below_market(), warmup_bars=5),
            with_history=False,
        )

        for _ in range(4):
            await rig.feed()

        assert rig.strategy.calls == 0
        assert rig.exchange.calls == []

        for _ in range(3):
            await rig.feed()

        assert rig.strategy.calls > 0

    async def test_stats_describe_is_readable(self, rig: Rig) -> None:
        """Die Betriebszahlen landen im Dashboard - sie muessen ohne
        Nachschlagen verstaendlich sein."""
        rig.strategy.emit(long_below_market())
        await rig.feed()

        text = rig.trader.stats.describe()

        assert "1 Kerzen" in text
        assert "1 Signale" in text


# ---------------------------------------------------------------------------
#  Hilfsfunktionen
# ---------------------------------------------------------------------------
def _position(rig: Rig, *, stop: Decimal | None):
    from core.models import Side
    from tests.fake_exchange import FakePosition

    return FakePosition(
        side=Side.BUY,
        size=Decimal("0.005"),
        entry_price=Decimal("99500"),
        stop_loss=stop,
    )


async def _open_protected(rig: Rig):
    """Standardablauf bis zur abgesicherten Position."""
    rig.strategy.emit(long_below_market())
    await rig.feed()
    rig.fill_entry()
    await rig.feed()
    bracket = rig.trader.bracket
    assert bracket is not None and bracket.state is BracketState.PROTECTED
    return bracket


def test_history_is_loaded_into_the_buffer(
    tmp_path, btcusdt: Instrument, risk: RiskSettings, bybit_settings: BybitSettings
) -> None:
    """Ohne Vorlauf braeuchte die Strategie je nach Periode Stunden bis Tage,
    bis sie das erste Signal geben darf."""
    rig = build_rig(tmp_path, btcusdt, risk, bybit_settings)

    assert len(rig.trader._frame) == HISTORY_BARS
    assert rig.trader._frame["open_time"].is_monotonic_increasing


def test_buffer_is_capped(
    tmp_path, btcusdt: Instrument, risk: RiskSettings, bybit_settings: BybitSettings
) -> None:
    """Der Puffer darf nicht unbegrenzt wachsen - der Prozess laeuft Monate."""
    from execution.live import BUFFER_BARS

    store = CandleStore(tmp_path / "store")
    candles = make_candles(
        count=BUFFER_BARS + 200, start=datetime(2026, 1, 1, tzinfo=UTC), step=Decimal(0)
    )
    store.write("BTCUSDT", Interval.M15, candles)

    rig = build_rig(tmp_path, btcusdt, risk, bybit_settings, with_history=False)
    rig.trader._load_history()

    assert len(rig.trader._frame) == BUFFER_BARS
    # Und zwar die **letzten** - die aeltesten fallen heraus, nicht die neuen.
    assert rig.trader._frame["open_time"].iloc[-1] == pd.Timestamp(candles[-1].open_time)


def test_interval_duration_matches_expectation() -> None:
    """Absicherung gegen eine verrutschte Intervalltabelle - die Testkerzen
    haengen daran."""
    assert Interval.M15.duration == timedelta(minutes=15)


# ---------------------------------------------------------------------------
#  Dashboard-Anbindung
# ---------------------------------------------------------------------------
class TestDashboard:
    async def test_heartbeat_is_written_every_candle(self, rig: Rig) -> None:
        """Auch wenn nichts passiert.

        Der Herzschlag ist die einzige Art, wie die Website zwischen "nichts
        zu tun" und "Prozess tot" unterscheiden kann.
        """
        await rig.feed()

        view = read_view(rig.state_dir)

        assert view.alive
        assert view.snapshot["equity"] == "500"
        assert view.snapshot["symbol"] == "BTCUSDT"

    async def test_entry_shows_up_as_an_event(self, rig: Rig) -> None:
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()
        await rig.feed()

        kinds = [e["kind"] for e in read_view(rig.state_dir).events]

        assert EventKind.ENTRY.value in kinds
        assert EventKind.SIGNAL.value in kinds

    async def test_open_position_appears_in_the_snapshot(self, rig: Rig) -> None:
        await _open_protected(rig)

        position = read_view(rig.state_dir).snapshot["position"]

        assert position["side"] == "Buy"
        assert position["stop_price"] is not None

    async def test_veto_is_visible_too(self, rig: Rig) -> None:
        """Warum *nicht* gehandelt wurde, ist genauso interessant wie was
        gehandelt wurde - sonst wirkt ein ruhiger Tag wie ein Ausfall."""
        rig.officer.pause("Test")
        rig.strategy.emit(long_below_market())
        await rig.feed()

        events = read_view(rig.state_dir).events

        assert any(e["kind"] == EventKind.VETO.value for e in events)

    async def test_journal_failure_does_not_stop_trading(self, rig: Rig) -> None:
        """Das Dashboard ist Beobachtung, nicht Steuerung. Eine volle Platte
        darf keinen Einstieg verhindern."""
        def broken(*args, **kwargs):
            raise OSError("Platte voll")

        rig.trader.journal.write_snapshot = broken
        rig.trader.journal.record = broken
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert rig.trader.bracket is not None


class TestRemoteControl:
    async def test_pause_from_the_dashboard(self, rig: Rig) -> None:
        send_command(rig.state_dir, CommandAction.PAUSE, "vom Telefon")
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert rig.entry_orders == []
        assert rig.officer.state.trading_state.value == "paused"

    async def test_resume_from_the_dashboard(self, rig: Rig) -> None:
        rig.officer.pause("Test")
        send_command(rig.state_dir, CommandAction.RESUME)
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert len(rig.entry_orders) == 1

    async def test_close_all_flattens_and_pauses(self, rig: Rig) -> None:
        await _open_protected(rig)
        send_command(rig.state_dir, CommandAction.CLOSE_ALL, "Not-Ausstieg")

        await rig.feed()

        assert rig.exchange.position is None
        assert rig.trader.bracket is None
        assert rig.officer.state.trading_state.value == "paused"

    async def test_kill_from_the_dashboard(self, rig: Rig) -> None:
        """Der Not-Aus vom Telefon - der Knopf, um den es beim Dashboard
        eigentlich geht."""
        await _open_protected(rig)
        send_command(rig.state_dir, CommandAction.KILL, "Not-Aus vom Dashboard")

        await rig.feed()

        assert rig.exchange.position is None
        assert rig.officer.state.trading_state.value == "killed"
        assert "Not-Aus vom Dashboard" in rig.officer.state.kill_reason

    async def test_kill_closes_the_position_exactly_once(self, rig: Rig) -> None:
        """Der Befehl legt nur den Schalter um; geschlossen wird an einer
        Stelle. Sonst laeuft der Notausstieg zweimal und die zweite
        Market-Order trifft auf eine leere Position."""
        await _open_protected(rig)
        send_command(rig.state_dir, CommandAction.KILL)

        await rig.feed()

        closes = [
            kwargs for name, kwargs in rig.exchange.calls
            if name == "place_market" and kwargs.get("reduce_only")
        ]
        assert len(closes) == 1

    async def test_command_is_executed_only_once(self, rig: Rig) -> None:
        """Ein liegengebliebener Befehl wuerde sich bei jeder Kerze
        wiederholen - ein 'alles schliessen' alle 15 Minuten."""
        send_command(rig.state_dir, CommandAction.PAUSE)
        await rig.feed()
        rig.officer.resume()

        await rig.feed()

        assert rig.officer.state.trading_state.value == "active"

    async def test_command_is_handled_before_the_strategy(self, rig: Rig) -> None:
        """Ein Not-Aus soll nicht warten, bis die Strategie ihre Meinung
        gebildet hat."""
        send_command(rig.state_dir, CommandAction.KILL)
        rig.strategy.emit(long_below_market())

        await rig.feed()

        assert rig.entry_orders == []
        assert rig.strategy.calls == 0


class TestTradeRecording:
    """Ohne diese Zeilen gibt es spaeter nichts auszuwerten ausser dem
    Kontostand - und der sagt nicht, *warum* etwas nicht mehr funktioniert."""

    async def test_closed_trade_is_written(self, rig: Rig) -> None:
        await _open_protected(rig)
        rig.account.set_equity(Decimal("512"))  # Trade lief ins Plus
        rig.exchange.position = None

        await rig.feed()

        trades = _read_trades(rig)
        assert len(trades) == 1
        assert trades[0].strategy_id == "queued"
        assert trades[0].net_pnl > 0

    async def test_result_comes_from_the_equity_change(self, rig: Rig) -> None:
        """Gebuehren und Funding stecken in der Kapitaldifferenz bereits drin.
        Aus Preisen gerechnet muesste man sie einzeln nachschlagen - und jede
        vergessene Position machte das Ergebnis zu optimistisch."""
        await _open_protected(rig)
        entry_equity = rig.trader.equity_at_entry
        rig.account.set_equity(entry_equity - Decimal("4.05"))  # Stop mit Gebuehren
        rig.exchange.position = None

        await rig.feed()

        assert _read_trades(rig)[0].net_pnl == Decimal("-4.05")

    async def test_excursions_are_tracked_while_the_position_lives(
        self, rig: Rig
    ) -> None:
        """MAE und MFE lassen sich nur waehrend des Trades erheben - im
        Nachhinein sind sie aus der Ausfuehrungshistorie nicht mehr
        rekonstruierbar. Aus ihnen leitet sich spaeter ab, ob Stop und Ziele
        richtig sitzen."""
        await _open_protected(rig)

        await rig.feed(close=Decimal("101000"))  # laeuft davon
        await rig.feed(close=Decimal("99000"))  # kommt zurueck
        rig.exchange.position = None
        await rig.feed()

        trade = _read_trades(rig)[0]
        assert trade.max_favourable_excursion > 0
        assert trade.max_adverse_excursion > 0

    async def test_excursions_reset_between_trades(self, rig: Rig) -> None:
        """Sonst schleppt der zweite Trade die Ausschlaege des ersten mit."""
        await _open_protected(rig)
        await rig.feed(close=Decimal("103000"))
        rig.exchange.position = None
        await rig.feed()

        assert rig.trader._mfe == Decimal(0)
        assert rig.trader._mae == Decimal(0)


def _read_trades(rig: Rig):
    import json

    from core.models import Trade

    path = rig.state_dir / "trades.jsonl"
    if not path.exists():
        return []
    return [Trade.model_validate(json.loads(line)) for line in path.read_text().splitlines()]
