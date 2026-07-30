"""Tests des Order-Routers gegen die simulierte Boerse.

Der wichtigste Test ist ``test_stop_is_set_before_take_profits``: Zwischen Fill
und gesetztem Stop ist die Position ungeschuetzt. Dieses Fenster muss so klein
wie moeglich sein - die Take-Profits koennen warten, der Stop nicht.

Zweitwichtigster: ``test_failed_stop_closes_position_immediately``. Wenn der
Stop nicht gesetzt werden kann, ist ein unnoetiger Ausstieg das kleinere Uebel
gegenueber einer ungeschuetzten Position.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from core.config import MarginMode, RiskSettings
from core.models import Instrument, Side
from data.bybit.errors import BybitAPIError, BybitTransportError
from execution.risk import RiskOfficer
from execution.router import Bracket, BracketState, MarketKind, OrderRouter
from execution.sizing import SizedPosition, size_position
from tests.factories import make_signal
from tests.fake_exchange import FakeExchange

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def exchange() -> FakeExchange:
    return FakeExchange(mark_price=Decimal("100000"))


@pytest.fixture
def router(
    exchange: FakeExchange, btcusdt: Instrument, risk: RiskSettings
) -> OrderRouter:
    return OrderRouter(exchange, btcusdt, risk, clock=lambda: T0)


def sized_for(signal, btcusdt: Instrument, risk: RiskSettings) -> SizedPosition:
    result = size_position(
        signal, equity=Decimal("500"), instrument=btcusdt, risk=risk
    )
    assert isinstance(result, SizedPosition), f"Signal nicht handelbar: {result}"
    return result


def open_and_fill(
    router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument, risk: RiskSettings
) -> Bracket:
    """Standardablauf: Einstieg platzieren, fuellen, absichern."""
    signal = make_signal(entry="99500", stop_pct="0.6")  # unter Markt -> PostOnly ok
    bracket = router.open(signal, sized_for(signal, btcusdt, risk))
    filled = exchange.fill(bracket.entry_order.order_id)
    router.protect(bracket, filled_qty=filled, fill_price=Decimal("99500"))
    return bracket


class TestAccountPreparation:
    def test_sets_isolated_margin_and_leverage(
        self, router: OrderRouter, exchange: FakeExchange, risk: RiskSettings
    ) -> None:
        router.prepare_account()

        assert exchange.margin_mode is MarginMode.ISOLATED
        assert exchange.leverage == risk.max_leverage

    def test_prepared_only_once(self, router: OrderRouter, exchange: FakeExchange) -> None:
        router.prepare_account()
        router.prepare_account()
        router.prepare_account()

        assert exchange.call_order.count("set_leverage") == 1

    def test_spot_skips_leverage(
        self, exchange: FakeExchange, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        """Auf Spot gibt es keinen Hebel - der Aufruf muss unterbleiben."""
        spot_router = OrderRouter(
            exchange, btcusdt, risk, market_kind=MarketKind.SPOT, clock=lambda: T0
        )
        spot_router.prepare_account()

        assert "set_leverage" not in exchange.call_order
        assert exchange.leverage is None


class TestEntry:
    def test_entry_is_postonly_limit(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Maker-Gebuehr statt Taker - bei 30 Trades im Monat der Unterschied
        zwischen 2 % und 5,5 % Gebuehrenlast."""
        signal = make_signal(entry="99500", stop_pct="0.6")
        router.open(signal, sized_for(signal, btcusdt, risk))

        _, kwargs = next(c for c in exchange.calls if c[0] == "place_limit")
        assert kwargs["post_only"] is True
        assert kwargs["reduce_only"] is False

    def test_postonly_rejected_when_crossing_the_market(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Ein Kauflimit ueber dem Markt wuerde sofort als Taker fuellen.

        Bybit lehnt das bei PostOnly ab. Genau das ist der haeufigste Grund,
        warum ein Einstieg live nicht zustande kommt, obwohl der Backtest ihn
        zeigt - der Router darf das nicht verschlucken.
        """
        signal = make_signal(entry="100500", stop_pct="0.6")  # ueber Markt

        with pytest.raises(BybitAPIError, match="PostOnly"):
            router.open(signal, sized_for(signal, btcusdt, risk))

    def test_expired_entry_is_cancelled(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        signal = make_signal(entry="99500", stop_pct="0.6")
        bracket = router.open(signal, sized_for(signal, btcusdt, risk))
        router.expire_entry(bracket)

        assert bracket.state is BracketState.EXPIRED
        assert exchange.orders[bracket.entry_order.order_id].status.is_terminal

    def test_short_rejected_on_spot(
        self, exchange: FakeExchange, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        """Auf Spot kann man nicht leerverkaufen.

        Lieber hier hart scheitern als eine Order absetzen, die die Boerse
        ablehnt - oder schlimmer, die als Verkauf einer nicht vorhandenen
        Position durchgeht.
        """
        spot_router = OrderRouter(
            exchange, btcusdt, risk, market_kind=MarketKind.SPOT, clock=lambda: T0
        )
        signal = make_signal(side=Side.SELL, entry="100500", stop_pct="0.6")

        with pytest.raises(ValueError, match="keine Shorts"):
            spot_router.open(signal, sized_for(signal, btcusdt, risk))


class TestProtection:
    def test_stop_is_set_before_take_profits(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Der wichtigste Test dieser Datei.

        Zwischen Fill und gesetztem Stop ist die Position ungeschuetzt. Dieses
        Fenster muss so klein wie moeglich sein - die Take-Profits koennen
        warten, der Stop nicht.
        """
        open_and_fill(router, exchange, btcusdt, risk)

        order = exchange.call_order
        stop_index = order.index("set_position_stop")
        first_target_index = next(
            i
            for i, (name, kwargs) in enumerate(exchange.calls)
            if name == "place_limit" and kwargs.get("reduce_only")
        )
        assert stop_index < first_target_index, (
            "Der Stop muss vor den Take-Profits gesetzt werden"
        )

    def test_stop_lands_on_the_position(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Der Stop haengt an der Position, nicht an einer eigenen Order.

        Damit liegt er auf Bybits Servern und greift auch, wenn unser Prozess
        abstuerzt oder das Netz ausfaellt.
        """
        bracket = open_and_fill(router, exchange, btcusdt, risk)

        assert exchange.position is not None
        assert exchange.position.stop_loss == bracket.stop_price
        assert bracket.state is BracketState.PROTECTED

    def test_failed_stop_closes_position_immediately(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Scheitert das Setzen des Stops, wird sofort geschlossen.

        Ein unnoetiger Ausstieg kostet Gebuehren. Eine ungeschuetzte Position
        kann das Konto kosten.
        """
        signal = make_signal(entry="99500", stop_pct="0.6")
        bracket = router.open(signal, sized_for(signal, btcusdt, risk))
        filled = exchange.fill(bracket.entry_order.order_id)

        exchange.fail_next("set_position_stop", BybitTransportError("Netz weg"))

        with pytest.raises(BybitTransportError):
            router.protect(bracket, filled_qty=filled, fill_price=Decimal("99500"))

        assert bracket.state is BracketState.CLOSED
        assert "place_market" in exchange.call_order
        assert exchange.position is None

    def test_targets_are_reduce_only(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Reduce-Only verhindert, dass eine Zielorder versehentlich eine
        Gegenposition eroeffnet."""
        open_and_fill(router, exchange, btcusdt, risk)

        target_calls = [
            kwargs
            for name, kwargs in exchange.calls
            if name == "place_limit" and kwargs.get("reduce_only")
        ]
        assert target_calls
        for kwargs in target_calls:
            assert kwargs["reduce_only"] is True
            assert kwargs["post_only"] is True  # Maker auch beim Ausstieg

    def test_target_quantities_sum_to_position(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Kein Rest darf uebrigbleiben - sonst haengt eine Teilposition ohne Ziel."""
        bracket = open_and_fill(router, exchange, btcusdt, risk)

        total = sum(o.qty for o in bracket.take_profit_orders)
        assert total == bracket.filled_qty


class TestPartialFills:
    def test_protects_only_what_was_filled(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Eine halb gefuellte Order darf nicht zu einem Stop ueber die volle
        Menge fuehren - der Rest wuerde als Gegenposition enden."""
        signal = make_signal(entry="99500", stop_pct="0.6")
        sized = sized_for(signal, btcusdt, risk)
        bracket = router.open(signal, sized)

        half = btcusdt.round_qty(sized.qty / 2)
        filled = exchange.fill(bracket.entry_order.order_id, qty=half)
        router.protect(bracket, filled_qty=filled, fill_price=Decimal("99500"))

        assert bracket.filled_qty == half
        assert bracket.remaining_qty == half
        assert exchange.position.size == half


class TestTargetsAndBreakeven:
    def test_stop_moves_to_breakeven_after_first_target(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Nach dem ersten Ziel kann der Trade nicht mehr ins Minus laufen -
        der wirksamste einzelne Schutz der Kapitalkurve."""
        bracket = open_and_fill(router, exchange, btcusdt, risk)
        first_qty = bracket.take_profit_orders[0].qty

        router.on_target_hit(bracket, qty=first_qty)

        assert bracket.moved_to_breakeven
        assert bracket.stop_price == bracket.entry_price
        assert exchange.position.stop_loss == bracket.entry_price

    def test_breakeven_only_moves_once(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Beim zweiten Ziel darf der Stop nicht erneut auf Einstand zurueck -
        er soll dort bleiben oder spaeter nachgezogen werden, nicht zurueckfallen."""
        bracket = open_and_fill(router, exchange, btcusdt, risk)
        router.on_target_hit(bracket, qty=bracket.take_profit_orders[0].qty)

        before = len([c for c in exchange.call_order if c == "set_position_stop"])
        router.on_target_hit(bracket, qty=bracket.take_profit_orders[1].qty)
        after = len([c for c in exchange.call_order if c == "set_position_stop"])

        assert after == before

    def test_all_targets_close_the_bracket(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        bracket = open_and_fill(router, exchange, btcusdt, risk)
        for order in list(bracket.take_profit_orders):
            router.on_target_hit(bracket, qty=order.qty)

        assert bracket.state is BracketState.CLOSED
        assert bracket.remaining_qty <= 0


class TestEmergencyClose:
    def test_cancels_orders_and_closes_position(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        bracket = open_and_fill(router, exchange, btcusdt, risk)
        router.emergency_close(bracket, reason="Not-Aus vom Dashboard")

        assert bracket.state is BracketState.CLOSED
        assert exchange.position is None
        assert not exchange.open_orders("BTCUSDT")

    def test_closes_even_if_cancelling_fails(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Schliessen ist wichtiger als Aufraeumen.

        Wenn das Stornieren scheitert, darf das nicht verhindern, dass die
        Position geschlossen wird - sonst bleibt genau im Notfall Risiko offen.
        """
        bracket = open_and_fill(router, exchange, btcusdt, risk)
        exchange.fail_next("cancel_all", BybitTransportError("Netz weg"))

        router.emergency_close(bracket, reason="Kill-Switch")

        assert bracket.state is BracketState.CLOSED
        assert "place_market" in exchange.call_order

    def test_emergency_uses_market_order(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings,
    ) -> None:
        """Im Notfall zaehlt Ausfuehrungssicherheit mehr als die Gebuehr."""
        bracket = open_and_fill(router, exchange, btcusdt, risk)
        router.emergency_close(bracket, reason="Test")

        _, kwargs = next(c for c in exchange.calls if c[0] == "place_market")
        assert kwargs["reduce_only"] is True
        assert kwargs["side"] is bracket.signal.side.opposite


class TestSpotMode:
    def test_spot_uses_stop_order_not_position_stop(
        self, exchange: FakeExchange, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        """Auf Spot gibt es keinen boersenseitigen Positions-Stop.

        Der Ersatz ist eine Reduce-Only-Order - schwaecher, weil sie erst
        existiert, nachdem wir sie platziert haben. Der Router muss das
        koennen, aber es muss im Code sichtbar bleiben.
        """
        spot_router = OrderRouter(
            exchange, btcusdt, risk, market_kind=MarketKind.SPOT, clock=lambda: T0
        )
        signal = make_signal(entry="99500", stop_pct="0.6")
        sized = sized_for(signal, btcusdt, risk)

        bracket = spot_router.open(signal, sized)
        filled = exchange.fill(bracket.entry_order.order_id)
        spot_router.protect(bracket, filled_qty=filled, fill_price=Decimal("99500"))

        assert "set_position_stop" not in exchange.call_order
        assert bracket.stop_order_id is not None
        assert bracket.state is BracketState.PROTECTED

    def test_market_kind_capabilities(self) -> None:
        assert MarketKind.PERPETUAL.supports_leverage
        assert MarketKind.PERPETUAL.supports_shorts
        assert MarketKind.PERPETUAL.has_position_stop

        assert not MarketKind.SPOT.supports_leverage
        assert not MarketKind.SPOT.supports_shorts
        assert not MarketKind.SPOT.has_position_stop


class TestRiskOfficerIntegration:
    def test_vetoed_signal_never_reaches_the_exchange(
        self, router: OrderRouter, exchange: FakeExchange, btcusdt: Instrument,
        risk: RiskSettings, tmp_path,
    ) -> None:
        """Der Risk-Officer sitzt vor dem Router, nicht daneben.

        Ein abgelehntes Signal darf die Boerse nie erreichen - deshalb wird
        hier geprueft, dass tatsaechlich kein einziger Aufruf erfolgt.
        """
        officer = RiskOfficer(risk, btcusdt, state_path=tmp_path / "risk.json")
        officer.observe_equity(Decimal("500"))
        officer.trigger_kill_switch("Test")

        signal = make_signal(entry="99500", stop_pct="0.6")
        decision = officer.evaluate(signal, equity=Decimal("500"))

        from execution.risk import Vetoed

        assert isinstance(decision, Vetoed)
        assert exchange.calls == [], "Kein Aufruf an die Boerse bei Veto"
