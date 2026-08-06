"""Tests der Backtest-Engine.

Die wichtigsten Tests des ganzen Projekts. Ein Fehler hier fuehrt nicht zu einer
Fehlermeldung, sondern zu einem Backtest, der gut aussieht und live Geld
verliert. Deshalb wird hier gegen **von Hand gerechnete** Ergebnisse geprueft
und nicht gegen das, was die Engine gerade ausgibt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from backtest.costs import CostModel, FundingSchedule
from backtest.engine import BacktestConfig, Backtester, ExitReason
from backtest.metrics import compute_metrics
from core.config import RiskSettings
from core.models import Candle, Instrument, Interval, Side, Signal, TakeProfitLeg
from data.store import candles_to_frame
from strategy.base import LookaheadError
from tests.factories import make_candles, make_signal
from tests.strategies import (
    NonCausalStrategy,
    PeekingStrategy,
    ScriptedStrategy,
    SmaCrossStrategy,
)

T0 = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)  # abseits der Funding-Zeiten


def bar(
    minute_offset: int,
    *,
    o: str,
    h: str,
    low: str,
    c: str,
    interval: Interval = Interval.M15,
) -> Candle:
    return Candle(
        open_time=T0 + interval.duration * minute_offset,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(low),
        close=Decimal(c),
        volume=Decimal("10"),
        turnover=Decimal("1000000"),
    )


def flat_series(count: int, price: str = "100000") -> list[Candle]:
    """Kerzen ohne Bewegung - als neutraler Hintergrund fuer gezielte Szenarien."""
    return [bar(i, o=price, h=price, low=price, c=price) for i in range(count)]


@pytest.fixture
def no_funding() -> FundingSchedule:
    """Funding abschalten, damit sich Trades exakt nachrechnen lassen."""
    return FundingSchedule(default_rate=Decimal(0))


@pytest.fixture
def config(btcusdt: Instrument, risk: RiskSettings, no_funding: FundingSchedule) -> BacktestConfig:
    return BacktestConfig(
        instrument=btcusdt,
        risk=risk,
        costs=CostModel(slippage_bps=Decimal(0), stop_slippage_bps=Decimal(0)),
        funding=no_funding,
        initial_equity=Decimal("500"),
        entry_expiry_bars=3,
    )


def long_signal_at(index: int, *, entry: str = "100000") -> Signal:
    """Long mit 0,6 % Stop und einem einzigen Take-Profit bei 1,5R."""
    price = Decimal(entry)
    distance = price * Decimal("0.006")
    return Signal(
        timestamp=T0 + Interval.M15.duration * index,
        symbol="BTCUSDT",
        side=Side.BUY,
        entry_price=price,
        stop_loss=price - distance,
        take_profits=[
            TakeProfitLeg(price=price + distance * Decimal("1.5"), portion=Decimal(1))
        ],
        strategy_id="scripted",
        reason="test",
    )


# ---------------------------------------------------------------------------
#  Von Hand nachgerechnet
# ---------------------------------------------------------------------------
class TestHandCalculatedTrade:
    """Ein vollstaendig durchgerechneter Gewinntrade.

    Vorgaben: 500 EUR Kapital, 0,75 % Risiko, BTC bei 100.000, Stop 0,6 %.

        Risikobetrag = 500 x 0,0075                 =   3,75
        Stop-Distanz = 100.000 x 0,006              = 600,00
        Rohmenge     = 3,75 / 600                   =   0,00625 BTC
        Menge        = auf 0,001 abgerundet         =   0,006   BTC
        Nominalwert  = 0,006 x 100.000              = 600,00
        Hebel        = 600 / 500                    =   1,20x

        Einstiegsgebuehr (Maker 0,02 %) = 600 x 0,0002        = 0,12
        Take-Profit bei 100.900 (1,5R):
        Bruttogewinn = (100.900 - 100.000) x 0,006            = 5,40
        Ausstiegsgebuehr (Maker) = 0,006 x 100.900 x 0,0002   = 0,121080

        Nettogewinn  = 5,40 - 0,12 - 0,121080                 = 5,158920
        Endkapital   = 505,158920
    """

    def test_winning_trade_matches_manual_calculation(self, config: BacktestConfig) -> None:
        candles = flat_series(5)
        # Kerze 5: Einstiegslimit wird unterschritten -> Fill bei 100.000
        candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        # Kerze 6: Take-Profit bei 100.900 wird erreicht
        candles.append(bar(6, o="100000", h="101000", low="99990", c="100950"))
        candles.extend(bar(i, o="100950", h="100950", low="100950", c="100950") for i in range(7, 10))

        strategy = ScriptedStrategy({4: long_signal_at(4)})
        result = Backtester(config).run(candles_to_frame(candles), strategy)

        assert len(result.trades) == 1
        trade = result.trades[0]

        assert trade.qty == Decimal("0.006")
        assert trade.entry_price == Decimal("100000")
        assert trade.exit_price == Decimal("100900.000")
        assert trade.exit_reason == ExitReason.TAKE_PROFIT.value
        assert trade.gross_pnl == pytest.approx(Decimal("5.400"))
        assert trade.fees == pytest.approx(Decimal("0.241080"))
        assert trade.net_pnl == pytest.approx(Decimal("5.158920"))
        assert result.final_equity == pytest.approx(Decimal("505.158920"))

    def test_losing_trade_costs_more_than_planned_risk(
        self, config: BacktestConfig
    ) -> None:
        """Ein Stop kostet mehr als den geplanten Risikobetrag - wegen der Gebuehren.

        Und zwar spuerbar mehr, weil der Stop eine **Market-Order** ist:

            Bruttoverlust    = (99.400 - 100.000) x 0,006          = -3,600
            Einstiegsgebuehr (Maker 0,020 %)                       =  0,120
            Ausstiegsgebuehr (Taker 0,055 %) = 0,006 x 99.400 x ...=  0,328
            Nettoverlust                                           = -4,048

        Die Ausstiegsgebuehr ist hier **2,7-mal so hoch** wie bei einem
        Take-Profit-Ausstieg (0,121). Das ist der Preis des Sicherheitsnetzes:
        Ein Stop muss sofort ausgefuehrt werden, also zahlt er Taker.

        Praktische Folge fuer die Strategieentwicklung: Eine Strategie mit
        vielen Stops zahlt deutlich mehr Gebuehren als ihre Trefferquote
        vermuten laesst. Das R-Vielfache eines Verlusts liegt bei -1,12 statt -1.
        """
        candles = flat_series(5)
        candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        candles.append(bar(6, o="100000", h="100010", low="99300", c="99350"))  # Stop bei 99.400
        candles.extend(bar(i, o="99350", h="99350", low="99350", c="99350") for i in range(7, 10))

        strategy = ScriptedStrategy({4: long_signal_at(4)})
        result = Backtester(config).run(candles_to_frame(candles), strategy)

        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.STOP_LOSS.value
        assert trade.gross_pnl == pytest.approx(Decimal("-3.600"))
        assert float(trade.fees) == pytest.approx(0.44802, abs=0.0001)
        assert float(trade.net_pnl) == pytest.approx(-4.04802, abs=0.0001)
        # Der Verlust ist 12 % groesser als 1R - allein durch Gebuehren.
        assert float(trade.r_multiple) == pytest.approx(-1.1244, abs=0.001)

    def test_stop_exit_costs_far_more_in_fees_than_target_exit(
        self, config: BacktestConfig
    ) -> None:
        """Direkter Vergleich der Ausstiegsgebuehren.

        Belegt die Entscheidung, Take-Profits als PostOnly-Limit zu fahren:
        Der Maker-Ausstieg kostet ein Drittel des Taker-Ausstiegs.
        """
        win_candles = flat_series(5)
        win_candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        win_candles.append(bar(6, o="100000", h="101000", low="99990", c="100950"))
        win_candles.extend(
            bar(i, o="100950", h="100950", low="100950", c="100950") for i in range(7, 10)
        )

        loss_candles = flat_series(5)
        loss_candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        loss_candles.append(bar(6, o="100000", h="100010", low="99300", c="99350"))
        loss_candles.extend(
            bar(i, o="99350", h="99350", low="99350", c="99350") for i in range(7, 10)
        )

        win = Backtester(config).run(
            candles_to_frame(win_candles), ScriptedStrategy({4: long_signal_at(4)})
        )
        loss = Backtester(config).run(
            candles_to_frame(loss_candles), ScriptedStrategy({4: long_signal_at(4)})
        )

        entry_fee = Decimal("0.12")
        win_exit_fee = win.trades[0].fees - entry_fee
        loss_exit_fee = loss.trades[0].fees - entry_fee

        assert loss_exit_fee > win_exit_fee * Decimal("2.5")

    def test_r_multiple_is_comparable_across_position_sizes(
        self, config: BacktestConfig
    ) -> None:
        """Das R-Vielfache muss unabhaengig vom Kapital sein.

        Genau deshalb ist es die Kennzahl, die sich zwischen Backtest und
        Livebetrieb vergleichen laesst.
        """
        candles = flat_series(5)
        candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        candles.append(bar(6, o="100000", h="101000", low="99990", c="100950"))
        candles.extend(bar(i, o="100950", h="100950", low="100950", c="100950") for i in range(7, 10))

        results = []
        for equity in ["500", "5000", "50000"]:
            cfg = BacktestConfig(
                instrument=config.instrument,
                risk=config.risk,
                costs=config.costs,
                funding=config.funding,
                initial_equity=Decimal(equity),
            )
            result = Backtester(cfg).run(
                candles_to_frame(candles), ScriptedStrategy({4: long_signal_at(4)})
            )
            results.append(float(result.trades[0].r_multiple))

        # Alle drei liegen bei ~1,5R minus Gebuehren.
        assert max(results) - min(results) < 0.05
        assert all(1.3 < r < 1.5 for r in results)


# ---------------------------------------------------------------------------
#  Lookahead
# ---------------------------------------------------------------------------
class TestLookaheadProtection:
    def test_context_rejects_negative_offset(self, config: BacktestConfig) -> None:
        """Der direkte Griff in die Zukunft ist ein Laufzeitfehler."""
        candles = flat_series(20)
        with pytest.raises(LookaheadError, match="zukuenftige Kerzen"):
            Backtester(config).run(candles_to_frame(candles), PeekingStrategy())

    def test_future_perturbation_does_not_change_past_decisions(
        self, config: BacktestConfig
    ) -> None:
        """Der entscheidende Nachweis - und der einzige wirklich scharfe.

        Vorgehen: Ab Kerze K werden alle Preise mit 1,5 multipliziert. Eine
        kausale Strategie muss danach bis Kerze K **exakt dieselben
        Entscheidungen** treffen wie zuvor. Weicht auch nur eine ab, hat sie
        Daten von Kerze K oder spaeter verwendet.

        Verglichen werden bewusst die *Entscheidungen* und nicht die fertigen
        Trades: Eine Entscheidung bei Kerze K-1 fuehrt zu einem Trade, der
        fruehestens bei Kerze K eingeht und noch spaeter schliesst. Ein
        Vergleich abgeschlossener Trades wuerde genau diesen Fall uebersehen -
        siehe ``test_truncation_alone_would_miss_this``.
        """
        frame = candles_to_frame(_wavy_series(600))
        cut = 400
        corrupted = _corrupt_from(frame, cut)

        baseline = _record_decisions(config, frame, SmaCrossStrategy())
        perturbed = _record_decisions(config, corrupted, SmaCrossStrategy())

        before = {i: s for i, s in baseline.items() if i < cut}
        after = {i: s for i, s in perturbed.items() if i < cut}

        assert len(before) > 300, "Testszenario muss genug Entscheidungen erzeugen"
        assert sum(1 for s in before.values() if s is not None) > 3, "und echte Signale"
        assert before == after, (
            "Eine Entscheidung vor Kerze K hat sich geaendert, obwohl nur Daten "
            "ab K veraendert wurden - das ist Lookahead."
        )

    def test_perturbation_test_actually_catches_non_causal_indicator(
        self, config: BacktestConfig
    ) -> None:
        """Belegt, dass der Test oben nicht nur gruen ist, weil er nichts prueft.

        ``shift(-1)`` holt den Schlusskurs der naechsten Kerze nach vorn. Der
        BarContext kann das nicht abfangen - der Lookahead steckt bereits in den
        vorberechneten Werten. Die Entscheidung bei Kerze K-1 liest close[K],
        muss sich also aendern, wenn close[K] veraendert wird.
        """
        frame = candles_to_frame(_wavy_series(600))
        cut = 400
        corrupted = _corrupt_from(frame, cut)

        baseline = _record_decisions(config, frame, NonCausalStrategy())
        perturbed = _record_decisions(config, corrupted, NonCausalStrategy())

        before = {i: s for i, s in baseline.items() if i < cut}
        after = {i: s for i, s in perturbed.items() if i < cut}

        assert before != after, (
            "Der Perturbationstest muss shift(-1) erkennen - sonst prueft er nichts."
        )
        # Konkret ist es die letzte Entscheidung vor dem Schnitt.
        assert before[cut - 1] != after[cut - 1]

    def test_truncation_alone_would_miss_this(self, config: BacktestConfig) -> None:
        """Warum ein Kuerzungstest allein nicht reicht - festgehalten als Test.

        Ein Backtest ueber die ersten K Kerzen liefert bei ``shift(-1)``
        dieselben abgeschlossenen Trades wie der volle Lauf: Der Fehler wirkt
        nur auf der jeweils letzten Kerze, und der daraus entstehende Trade
        schliesst erst nach dem Schnitt. Wer nur so testet, haelt eine
        hellseherische Strategie fuer sauber.
        """
        frame = candles_to_frame(_wavy_series(600))
        cut = 400

        full = Backtester(config).run(frame, NonCausalStrategy())
        partial = Backtester(config).run(frame.iloc[:cut].copy(), NonCausalStrategy())

        cutoff = frame["open_time"].iloc[cut - 1].to_pydatetime()
        full_before = [
            (t.entry_time, t.entry_price, t.exit_price)
            for t in full.trades
            if t.exit_time < cutoff
        ]
        partial_before = [
            (t.entry_time, t.entry_price, t.exit_price)
            for t in partial.trades
            if t.exit_time < cutoff
        ]

        assert full_before == partial_before, (
            "Erwartet: Der Kuerzungstest sieht den Fehler NICHT. Schlaegt dieser "
            "Test fehl, faengt die Kuerzung mehr ab als angenommen - erfreulich, "
            "aber massgeblich bleibt der Perturbationstest."
        )

    def test_indicator_length_mismatch_is_rejected(self, config: BacktestConfig) -> None:
        """Ein Off-by-one in der Indikatorlaenge verschiebt alle Zuordnungen."""

        class BrokenStrategy:
            strategy_id = "broken"
            warmup_bars = 2

            def prepare(self, frame: pd.DataFrame) -> dict:
                import numpy as np

                return {"kaputt": np.zeros(len(frame) - 1)}

            def on_bar(self, ctx) -> None:
                return None

        with pytest.raises(ValueError, match="verschiebt die Zuordnung"):
            Backtester(config).run(candles_to_frame(flat_series(20)), BrokenStrategy())

    def test_strategy_never_sees_bar_before_warmup(self, config: BacktestConfig) -> None:
        strategy = ScriptedStrategy({}, warmup_bars=30)
        Backtester(config).run(candles_to_frame(flat_series(50)), strategy)
        assert min(strategy.seen_indices) >= 30


# ---------------------------------------------------------------------------
#  Fill-Modell
# ---------------------------------------------------------------------------
class TestFillModel:
    def test_postonly_entry_needs_penetration_not_touch(
        self, config: BacktestConfig
    ) -> None:
        """Beruehrt der Preis das Limit nur, stehen wir hinten in der Schlange.

        Ein Backtest, der jede Beruehrung als Fill wertet, erzeugt Trades, die
        live nie zustande kaemen - und zwar systematisch die besten.
        """
        candles = flat_series(5)
        # Tief liegt exakt auf dem Limit: kein Fill.
        candles.append(bar(5, o="100050", h="100100", low="100000", c="100050"))
        candles.extend(bar(i, o="100050", h="100100", low="100000", c="100050") for i in range(6, 12))

        result = Backtester(config).run(
            candles_to_frame(candles), ScriptedStrategy({4: long_signal_at(4)})
        )
        assert result.entries_filled == 0
        assert result.entries_expired == 1

    def test_entry_cannot_fill_on_signal_bar(self, config: BacktestConfig) -> None:
        """Die Order entsteht erst nach dem Schluss der Signalkerze."""
        candles = flat_series(4)
        # Kerze 4 durchlaeuft das Limit - darf aber nicht fuellen.
        candles.append(bar(4, o="100000", h="100100", low="99000", c="100000"))
        candles.extend(flat_series(6)[i] for i in range(5, 6))
        candles.extend(bar(i, o="100000", h="100000", low="100000", c="100000") for i in range(6, 10))

        result = Backtester(config).run(
            candles_to_frame(candles), ScriptedStrategy({4: long_signal_at(4)})
        )
        # Nur die spaeteren, flachen Kerzen erreichen das Limit nicht mehr.
        assert result.entries_filled == 0

    def test_entry_expires_after_configured_bars(self, config: BacktestConfig) -> None:
        candles = flat_series(20, price="105000")  # Limit nie erreicht
        result = Backtester(config).run(
            candles_to_frame(candles), ScriptedStrategy({4: long_signal_at(4)})
        )
        assert result.entries_expired == 1
        assert not result.trades

    def test_stop_wins_over_take_profit_without_subbars(
        self, config: BacktestConfig
    ) -> None:
        """Pessimistische Annahme bei mehrdeutiger Kerze.

        Liegen Stop und Take-Profit in derselben Kerze, verraet OHLC nicht, was
        zuerst kam. Im Zweifel den Verlust annehmen - alles andere rechnet den
        Backtest systematisch schoen.
        """
        candles = flat_series(5)
        candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        # Diese Kerze beruehrt beides: Stop 99.400 und Take-Profit 100.900.
        candles.append(bar(6, o="100000", h="101000", low="99300", c="100000"))
        candles.extend(bar(i, o="100000", h="100000", low="100000", c="100000") for i in range(7, 10))

        result = Backtester(config).run(
            candles_to_frame(candles), ScriptedStrategy({4: long_signal_at(4)})
        )
        assert result.trades[0].exit_reason == ExitReason.STOP_LOSS.value

    def test_subbar_index_actually_finds_segments(self) -> None:
        """Absicherung gegen einen stillen Fehler.

        pandas waehlt die Zeiteinheit je nach Datenquelle (hier Mikrosekunden),
        waehrend ``Timestamp.value`` immer Nanosekunden liefert. Ohne
        ausdrueckliche Normierung liegen beide Seiten um Faktor 1000
        auseinander, ``searchsorted`` findet nichts, und die Engine faellt
        unbemerkt auf die pessimistische Annahme zurueck - ohne jede
        Fehlermeldung, nur mit schlechteren Ergebnissen.
        """
        from backtest.engine import _SubBarIndex

        base = T0 + Interval.M15.duration * 6
        subs = [
            Candle(
                open_time=base + timedelta(minutes=m),
                open=Decimal("100000"),
                high=Decimal("100100"),
                low=Decimal("99900"),
                close=Decimal("100000"),
                volume=Decimal("1"),
                turnover=Decimal("100000"),
            )
            for m in range(15)
        ]
        index = _SubBarIndex(candles_to_frame(subs))
        found = index.between(base, base + Interval.M15.duration)

        assert len(found) == 15, (
            "Alle 15 Minutenkerzen muessen gefunden werden. Null Treffer bedeutet "
            "einen Einheiten-Fehler bei den Zeitstempeln."
        )

    def test_subbars_resolve_ambiguity_correctly(self, config: BacktestConfig) -> None:
        """Mit 1-Minuten-Daten wird die Reihenfolge exakt aufgeloest.

        Hier kommt der Take-Profit nachweislich zuerst - die Engine darf dann
        nicht mehr pessimistisch den Stop nehmen.
        """
        candles = flat_series(5)
        candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        candles.append(bar(6, o="100000", h="101000", low="99300", c="100000"))
        candles.extend(bar(i, o="100000", h="100000", low="100000", c="100000") for i in range(7, 10))

        # 1-Minuten-Kerzen innerhalb von Kerze 6: erst hoch (TP), dann runter.
        base = T0 + Interval.M15.duration * 6
        subs = []
        for minute in range(15):
            if minute < 5:
                high, low = Decimal("101000"), Decimal("99990")  # Take-Profit
            elif minute < 10:
                high, low = Decimal("100100"), Decimal("99300")  # Stop
            else:
                high, low = Decimal("100050"), Decimal("99950")
            subs.append(
                Candle(
                    open_time=base + timedelta(minutes=minute),
                    open=Decimal("100000"),
                    high=high,
                    low=low,
                    close=Decimal("100000"),
                    volume=Decimal("1"),
                    turnover=Decimal("100000"),
                )
            )

        result = Backtester(config).run(
            candles_to_frame(candles),
            ScriptedStrategy({4: long_signal_at(4)}),
            sub_frame=candles_to_frame(subs),
        )
        assert result.trades[0].exit_reason == ExitReason.TAKE_PROFIT.value

    def test_only_one_position_at_a_time(self, config: BacktestConfig) -> None:
        candles = flat_series(3)
        candles.extend(bar(i, o="100000", h="100050", low="99950", c="100000") for i in range(3, 20))

        signals = {i: long_signal_at(i) for i in [2, 4, 6, 8]}
        result = Backtester(config).run(candles_to_frame(candles), ScriptedStrategy(signals))

        assert result.signals_generated == 4
        assert "position_bereits_offen" in result.rejections


# ---------------------------------------------------------------------------
#  Teilausstiege
# ---------------------------------------------------------------------------
class TestPartialExits:
    def test_stop_moves_to_breakeven_after_first_target(
        self, config: BacktestConfig
    ) -> None:
        """Nach der ersten Teilrealisierung darf der Trade nicht mehr ins Minus.

        Bruttoergebnis: TP1 bringt Gewinn, der Rest geht bei Einstand raus.
        """
        price = Decimal("100000")
        distance = price * Decimal("0.006")
        signal = Signal(
            timestamp=T0 + Interval.M15.duration * 4,
            symbol="BTCUSDT",
            side=Side.BUY,
            entry_price=price,
            stop_loss=price - distance,
            take_profits=[
                TakeProfitLeg(price=price + distance, portion=Decimal("0.5")),
                TakeProfitLeg(price=price + distance * 3, portion=Decimal("0.5")),
            ],
            strategy_id="scripted",
            reason="test",
        )

        candles = flat_series(5)
        candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        candles.append(bar(6, o="100000", h="100700", low="99990", c="100650"))  # TP1
        candles.append(bar(7, o="100650", h="100650", low="99500", c="99600"))  # zurueck
        candles.extend(bar(i, o="99600", h="99600", low="99600", c="99600") for i in range(8, 11))

        result = Backtester(config).run(
            candles_to_frame(candles), ScriptedStrategy({4: signal})
        )

        trade = result.trades[0]
        assert trade.gross_pnl > 0, "Nach TP1 darf der Trade brutto nicht ins Minus"
        assert trade.exit_reason == ExitReason.STOP_LOSS.value

    def test_all_targets_hit_closes_position(self, config: BacktestConfig) -> None:
        price = Decimal("100000")
        distance = price * Decimal("0.006")
        signal = Signal(
            timestamp=T0 + Interval.M15.duration * 4,
            symbol="BTCUSDT",
            side=Side.BUY,
            entry_price=price,
            stop_loss=price - distance,
            take_profits=[
                TakeProfitLeg(price=price + distance, portion=Decimal("0.5")),
                TakeProfitLeg(price=price + distance * 2, portion=Decimal("0.5")),
            ],
            strategy_id="scripted",
            reason="test",
        )

        candles = flat_series(5)
        candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        candles.append(bar(6, o="100000", h="102000", low="99990", c="101800"))
        candles.extend(bar(i, o="101800", h="101800", low="101800", c="101800") for i in range(7, 10))

        result = Backtester(config).run(
            candles_to_frame(candles), ScriptedStrategy({4: signal})
        )
        assert len(result.trades) == 1
        assert result.trades[0].exit_reason == ExitReason.TAKE_PROFIT.value
        assert result.trades[0].net_pnl > 0


# ---------------------------------------------------------------------------
#  Short-Seite
# ---------------------------------------------------------------------------
class TestShortSide:
    def test_short_trade_profits_when_price_falls(self, config: BacktestConfig) -> None:
        price = Decimal("100000")
        distance = price * Decimal("0.006")
        signal = Signal(
            timestamp=T0 + Interval.M15.duration * 4,
            symbol="BTCUSDT",
            side=Side.SELL,
            entry_price=price,
            stop_loss=price + distance,
            take_profits=[
                TakeProfitLeg(price=price - distance * Decimal("1.5"), portion=Decimal(1))
            ],
            strategy_id="scripted",
            reason="test",
        )

        candles = flat_series(5)
        candles.append(bar(5, o="100000", h="100050", low="99950", c="100000"))
        candles.append(bar(6, o="100000", h="100010", low="99000", c="99050"))
        candles.extend(bar(i, o="99050", h="99050", low="99050", c="99050") for i in range(7, 10))

        result = Backtester(config).run(
            candles_to_frame(candles), ScriptedStrategy({4: signal})
        )

        trade = result.trades[0]
        assert trade.side is Side.SELL
        assert trade.gross_pnl == pytest.approx(Decimal("5.400"))

    def test_shorts_can_be_disabled(self, config: BacktestConfig) -> None:
        cfg = BacktestConfig(
            instrument=config.instrument,
            risk=config.risk,
            costs=config.costs,
            funding=config.funding,
            initial_equity=config.initial_equity,
            allow_shorts=False,
        )
        price = Decimal("100000")
        distance = price * Decimal("0.006")
        signal = Signal(
            timestamp=T0 + Interval.M15.duration * 4,
            symbol="BTCUSDT",
            side=Side.SELL,
            entry_price=price,
            stop_loss=price + distance,
            take_profits=[TakeProfitLeg(price=price - distance, portion=Decimal(1))],
            strategy_id="scripted",
            reason="test",
        )
        result = Backtester(cfg).run(
            candles_to_frame(flat_series(20)), ScriptedStrategy({4: signal})
        )
        assert result.rejections.get("shorts_deaktiviert") == 1


def _corrupt_from(frame: pd.DataFrame, index: int) -> pd.DataFrame:
    """Verfaelscht alle Preise ab ``index``. OHLC bleibt dabei konsistent,
    weil alle vier Spalten mit demselben Faktor skaliert werden."""
    corrupted = frame.copy()
    for column in ("open", "high", "low", "close"):
        corrupted.loc[index:, column] = corrupted.loc[index:, column] * 1.5
    return corrupted


def _record_decisions(
    config: BacktestConfig, frame: pd.DataFrame, strategy
) -> dict[int, tuple | None]:
    """Fuehrt den Backtest aus und zeichnet jede Strategieentscheidung auf.

    Erfasst wird eine vergleichbare Kurzform des Signals - Zeitstempel und
    Preise reichen, um jede Abweichung zu erkennen.
    """
    recorded: dict[int, tuple | None] = {}

    class Recorder:
        strategy_id = strategy.strategy_id
        warmup_bars = strategy.warmup_bars

        def prepare(self, f: pd.DataFrame) -> dict:
            return strategy.prepare(f)

        def on_bar(self, ctx):
            signal = strategy.on_bar(ctx)
            recorded[ctx.index] = (
                None
                if signal is None
                else (signal.side.value, signal.entry_price, signal.stop_loss)
            )
            return signal

    Backtester(config).run(frame, Recorder())
    return recorded


def _wavy_series(count: int) -> list[Candle]:
    """Schwingende Preisreihe, die Kreuzungen erzeugt.

    Zwei ueberlagerte Sinuskurven, damit die Durchschnitte sich mehrfach
    schneiden und genug Trades entstehen, um Abweichungen sichtbar zu machen.
    """
    import math

    candles: list[Candle] = []
    for i in range(count):
        base = 100_000 + 900 * math.sin(i / 18) + 350 * math.sin(i / 5.5)
        close = base + 120 * math.sin(i / 2.3)
        high = max(base, close) + 90
        low = min(base, close) - 90
        candles.append(
            Candle(
                open_time=T0 + Interval.M15.duration * i,
                open=Decimal(f"{base:.1f}"),
                high=Decimal(f"{high:.1f}"),
                low=Decimal(f"{low:.1f}"),
                close=Decimal(f"{close:.1f}"),
                volume=Decimal("10"),
                turnover=Decimal("1000000"),
            )
        )
    return candles


class TestEquityFloor:
    """Die Kapitalkurve darf nicht unter null.

    Bei Isolated Margin ist die gestellte Margin das Maximum, das verloren
    gehen kann - davor liquidiert die Boerse. Laeuft die Kurve trotzdem ins
    Minus, wird der Drawdown groesser als 100 %, und jede darauf aufbauende
    Schwelle ist wertlos. Der erste echte Zulassungslauf meldete 1005 %.
    """

    def test_equity_curve_never_goes_negative(
        self, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        candles = make_candles(count=600, step=Decimal("-120"), wick=Decimal("40"))
        frame = candles_to_frame(candles)
        signals = {
            i: make_signal(
                entry=str(candles[i].close),
                stop_pct="1.0",
                timestamp=candles[i].open_time,
            )
            for i in range(2, 590)
        }
        config = BacktestConfig(
            instrument=btcusdt,
            risk=risk.model_copy(update={"risk_per_trade_pct": Decimal("5")}),
            initial_equity=Decimal("100"),
        )

        result = Backtester(config).run(frame, ScriptedStrategy(signals))

        assert (result.equity_curve["equity"] >= 0).all()

    def test_drawdown_stays_within_one_hundred_percent(
        self, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        candles = make_candles(count=600, step=Decimal("-120"), wick=Decimal("40"))
        frame = candles_to_frame(candles)
        signals = {
            i: make_signal(
                entry=str(candles[i].close),
                stop_pct="1.0",
                timestamp=candles[i].open_time,
            )
            for i in range(2, 590)
        }
        config = BacktestConfig(
            instrument=btcusdt,
            risk=risk.model_copy(update={"risk_per_trade_pct": Decimal("5")}),
            initial_equity=Decimal("100"),
        )

        result = Backtester(config).run(frame, ScriptedStrategy(signals))
        metrics = compute_metrics(
            result.trades,
            result.equity_curve,
            initial_equity=result.initial_equity,
            total_fees=result.total_fees,
        )

        assert metrics.max_drawdown_pct <= 100.0

    def test_healthy_run_is_not_marked_as_ruined(
        self, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        candles = make_candles(count=200, step=Decimal("50"))
        frame = candles_to_frame(candles)
        signals = {
            5: make_signal(entry=str(candles[5].close), timestamp=candles[5].open_time)
        }
        config = BacktestConfig(
            instrument=btcusdt, risk=risk, initial_equity=Decimal("500")
        )

        result = Backtester(config).run(frame, ScriptedStrategy(signals))

        assert not result.is_ruined


class TestVerlustgrenzenImBacktest:
    """Die vierte Abweichung zwischen Backtest und Betrieb.

    Anders als die drei vorigen war das kein Codefehler, sondern eine
    **fehlende Modellierung**: Der Betrieb sperrt nach 3 % Tagesverlust fuer
    24 Stunden, nach 7 % Wochenverlust bis zur manuellen Freigabe, und bei
    15 % Rueckgang faellt der Kill-Switch. Der Backtest kannte keine dieser
    Grenzen und handelte weiter - er mass damit eine Strategie, die es so
    nicht geben kann.

    Die Grenzen kommen vom **echten** ``RiskOfficer``, nicht von einer
    Nachbildung. Genau daran sind die drei vorigen Fehler entstanden.
    """

    def _fallende_kerzen(self, count: int, *, prozent_je_kerze: float) -> list[Candle]:
        """Eine Reihe, die stetig faellt - damit die Grenzen sicher greifen."""
        kerzen = []
        preis = Decimal("100000")
        for i in range(count):
            naechster = preis * (Decimal(1) - Decimal(str(prozent_je_kerze)) / 100)
            kerzen.append(
                bar(i, o=f"{preis:.2f}", h=f"{preis:.2f}",
                    low=f"{naechster:.2f}", c=f"{naechster:.2f}")
            )
            preis = naechster
        return kerzen

    def test_ohne_grenzen_wird_weitergehandelt(
        self, btcusdt: Instrument, risk: RiskSettings, no_funding: FundingSchedule
    ) -> None:
        """Die Gegenprobe - sonst zeigte der Test unten nichts."""
        kerzen = self._fallende_kerzen(200, prozent_je_kerze=0.5)
        signals = {i: long_signal_at(i, entry=f"{kerzen[i].close:.2f}")
                   for i in range(2, 200, 10)}
        cfg = BacktestConfig(
            instrument=btcusdt, risk=risk, funding=no_funding,
            initial_equity=Decimal("500"), enforce_risk_limits=False,
        )

        ergebnis = Backtester(cfg).run(
            candles_to_frame(kerzen), ScriptedStrategy(signals)
        )

        assert ergebnis.signals_vetoed == 0
        assert not ergebnis.veto_reasons

    def test_mit_grenzen_sperrt_der_officer(
        self, btcusdt: Instrument, risk: RiskSettings, no_funding: FundingSchedule
    ) -> None:
        kerzen = self._fallende_kerzen(200, prozent_je_kerze=0.5)
        signals = {i: long_signal_at(i, entry=f"{kerzen[i].close:.2f}")
                   for i in range(2, 200, 10)}
        cfg = BacktestConfig(
            instrument=btcusdt, risk=risk, funding=no_funding,
            initial_equity=Decimal("500"), enforce_risk_limits=True,
        )

        ergebnis = Backtester(cfg).run(
            candles_to_frame(kerzen), ScriptedStrategy(signals)
        )

        assert ergebnis.signals_vetoed > 0, (
            "In einem stetig fallenden Markt muss der Officer irgendwann "
            "sperren - sonst greifen die Grenzen im Backtest gar nicht"
        )
        assert ergebnis.veto_reasons

    class GrossePosition:
        """Handelt nach Kapitalanteil, mit weitem Stop.

        Noetig, um den Not-Aus ueberhaupt ausloesen zu koennen: Nach der
        Risikoformel ist der Verlust je Trade auf 0,75 % gedeckelt, und der
        Stop greift lange vor jeder Rueckgangsgrenze. Erst eine grosse
        Position mit fernem Stop laesst das Kapital weit genug fallen,
        waehrend sie **offen** ist - und genau darum geht es hier.
        """

        strategy_id = "gross"
        warmup_bars = 1
        equity_fraction = Decimal("2.0")

        def prepare(self, frame):
            return {}

        def fraction_at(self, index):
            return self.equity_fraction

        def on_bar(self, ctx):
            if ctx.index != 2:
                return None
            preis = Decimal(str(ctx.close()))
            return Signal(
                timestamp=ctx.time, symbol="BTCUSDT", side=Side.BUY,
                entry_price=preis,
                # Stop 10 % entfernt. Weiter geht nicht: Der Sizer verlangt
                # einen Mindestabstand der Liquidation zum Stop und lehnt
                # sonst mit ``liquidation_too_close`` ab. Bei 1 % Kursverfall
                # je Kerze und doppeltem Kapital reisst der Rueckgang die
                # 5-%-Grenze nach gut zwei Kerzen - lange bevor der Stop
                # erreicht ist.
                stop_loss=preis * Decimal("0.9"),
                strategy_id="gross", reason="Test",
            )

    def test_der_kill_switch_schliesst_die_offene_position(
        self, btcusdt: Instrument, no_funding: FundingSchedule
    ) -> None:
        """Der Not-Aus wartet nicht auf den Stop.

        Im Betrieb stellt er sofort glatt. Ohne das liefe die Position im
        Backtest weiter, und der gemessene Rueckgang waere kleiner als der
        wirkliche - genau falsch herum.
        """
        eng = RiskSettings(
            risk_per_trade_pct=Decimal("0.75"),
            max_drawdown_pct=Decimal("5"),
            daily_loss_limit_pct=Decimal("2"),
            weekly_loss_limit_pct=Decimal("3"),
            max_leverage=Decimal("10"),
        )
        kerzen = self._fallende_kerzen(60, prozent_je_kerze=1.0)
        cfg = BacktestConfig(
            instrument=btcusdt, risk=eng, funding=no_funding,
            initial_equity=Decimal("500"), enforce_risk_limits=True,
        )

        ergebnis = Backtester(cfg).run(
            candles_to_frame(kerzen), self.GrossePosition()
        )

        gruende = [str(t.exit_reason) for t in ergebnis.trades]
        assert ExitReason.KILL_SWITCH.value in gruende, (
            f"Der Not-Aus hat nicht geschlossen - Ausstiege waren {gruende}"
        )

    def test_ohne_grenzen_laeuft_dieselbe_position_weiter(
        self, btcusdt: Instrument, no_funding: FundingSchedule
    ) -> None:
        """Die Gegenprobe zum Not-Aus."""
        eng = RiskSettings(
            risk_per_trade_pct=Decimal("0.75"),
            max_drawdown_pct=Decimal("5"),
            daily_loss_limit_pct=Decimal("2"),
            weekly_loss_limit_pct=Decimal("3"),
            max_leverage=Decimal("10"),
        )
        kerzen = self._fallende_kerzen(60, prozent_je_kerze=1.0)
        cfg = BacktestConfig(
            instrument=btcusdt, risk=eng, funding=no_funding,
            initial_equity=Decimal("500"), enforce_risk_limits=False,
        )

        ergebnis = Backtester(cfg).run(
            candles_to_frame(kerzen), self.GrossePosition()
        )

        gruende = [str(t.exit_reason) for t in ergebnis.trades]
        assert ExitReason.KILL_SWITCH.value not in gruende

    def test_die_grenzen_kommen_vom_echten_officer(self) -> None:
        """Kein Nachbau - eine Umsetzung, zwei Aufrufer.

        Wuerde die Engine die Regeln nachbauen, waere das genau das Muster,
        aus dem die drei vorigen Abweichungen entstanden sind.
        """
        import inspect

        from backtest import engine
        from execution.risk import RiskOfficer

        quelle = inspect.getsource(engine)
        assert "RiskOfficer(" in quelle, "Die Engine muss den echten Officer bauen"
        assert "blockade(" in quelle, "und seine Sperrpruefung aufrufen"
        assert hasattr(RiskOfficer, "blockade")

    def test_die_uhr_zeigt_auf_die_kerze(
        self, btcusdt: Instrument, risk: RiskSettings, no_funding: FundingSchedule
    ) -> None:
        """Sonst faenden alle Kerzen am selben Tag statt.

        Der Officer misst Tages- und Wochenverluste an seiner Uhr. Zeigte sie
        auf die Wirklichkeit statt auf den Backtest, lagen alle 2830 Kerzen
        an einem Tag - und die Tagesgrenze griffe nie.
        """
        kerzen = self._fallende_kerzen(100, prozent_je_kerze=0.5)
        cfg = BacktestConfig(
            instrument=btcusdt, risk=risk, funding=no_funding,
            initial_equity=Decimal("500"), enforce_risk_limits=True,
        )
        tester = Backtester(cfg)
        tester.run(candles_to_frame(kerzen), ScriptedStrategy({}))

        # Nach dem Lauf steht die Uhr auf der letzten Kerze, nicht auf heute.
        assert tester._jetzt == kerzen[-1].open_time

    def test_vorgabe_ist_eingeschaltet(self, btcusdt: Instrument, risk: RiskSettings) -> None:
        """Der Vorgabewert entscheidet, was gemessen wird.

        Waere er aus, misst jeder Zulassungslauf weiterhin die schoenere Zahl -
        und die Korrektur waere Dekoration.
        """
        cfg = BacktestConfig(instrument=btcusdt, risk=risk)
        assert cfg.enforce_risk_limits is True
