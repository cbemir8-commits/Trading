"""Tests der Kennzahlen.

Gegen von Hand gerechnete Werte geprueft. Eine Kennzahl, die still falsch
rechnet, ist gefaehrlicher als eine fehlende: Sie fuehrt zu einer Strategie,
die auf dem Papier die Zulassungs-Gates besteht.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.metrics import (
    _max_consecutive_losses,
    _sharpe,
    _sortino,
    compute_drawdown,
    compute_metrics,
)
from core.models import Side, Trade

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def equity_curve(values: list[float], *, step: timedelta = timedelta(days=1)) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": [T0 + step * i for i in range(len(values))],
            "equity": values,
        }
    )


def make_trade(
    *,
    pnl: str,
    fees: str = "0",
    entry: str = "100000",
    stop: str = "99400",
    qty: str = "0.006",
    hours: int = 4,
    index: int = 0,
    reason: str = "take_profit",
) -> Trade:
    return Trade(
        trade_id=f"t{index}",
        symbol="BTCUSDT",
        side=Side.BUY,
        strategy_id="test",
        entry_time=T0 + timedelta(hours=index * 24),
        entry_price=Decimal(entry),
        exit_time=T0 + timedelta(hours=index * 24 + hours),
        exit_price=Decimal(entry),
        qty=Decimal(qty),
        gross_pnl=Decimal(pnl),
        fees=Decimal(fees),
        stop_loss=Decimal(stop),
        exit_reason=reason,
    )


class TestDrawdown:
    def test_simple_drawdown(self) -> None:
        """Hoechststand 120, Tief 90 -> Rueckgang 30/120 = 25 %."""
        info = compute_drawdown(equity_curve([100, 120, 90, 110, 130]))

        assert info.max_drawdown_pct == pytest.approx(25.0)
        assert info.max_drawdown_abs == pytest.approx(30.0)
        assert info.recovered

    def test_measured_from_running_peak_not_start(self) -> None:
        """Der Rueckgang wird am laufenden Hoch gemessen, nicht am Startkapital.

        Das ist die Zahl, die der Kill-Switch ueberwacht - und die ein Anleger
        tatsaechlich erlebt.
        """
        info = compute_drawdown(equity_curve([100, 200, 150]))
        assert info.max_drawdown_pct == pytest.approx(25.0)  # 50/200, nicht 50/100

    def test_unrecovered_drawdown(self) -> None:
        info = compute_drawdown(equity_curve([100, 150, 80]))
        assert not info.recovered
        assert info.recovery_time is None

    def test_monotonic_curve_has_no_drawdown(self) -> None:
        info = compute_drawdown(equity_curve([100, 110, 120, 130]))
        assert info.max_drawdown_pct == 0.0

    def test_longest_underwater_period_is_peak_to_recovery(self) -> None:
        """Gemessen wird vom Hoechststand bis zur vollstaendigen Erholung.

        Kurve [100, 90, 85, 88, 95, 101] an den Tagen 0..5: Das Hoch liegt bei
        Tag 0, wiedererreicht wird es an Tag 5 - also 5 Tage. Nicht 4 (die Zahl
        der Tage strikt unterhalb): Die uebliche Definition der Drawdown-Dauer
        laeuft von Hoch zu Erholung, weil genau diese Spanne der Anleger als
        'es geht nicht voran' erlebt.

        Psychologisch oft wichtiger als die Tiefe: 8 % ueber zwei Tage haelt man
        aus, dieselben 8 % ueber sieben Monate fuehren zum Abschalten - meist
        kurz vor der Erholung.
        """
        info = compute_drawdown(equity_curve([100, 90, 85, 88, 95, 101]))
        assert info.longest_days == pytest.approx(5.0)

    def test_unrecovered_drawdown_counts_until_end_of_data(self) -> None:
        """Erholt sich das Kapital nie, laeuft die Uhr bis zum letzten Datenpunkt."""
        info = compute_drawdown(equity_curve([100, 120, 90, 95, 99]))
        assert info.longest_days == pytest.approx(3.0)  # Hoch an Tag 1, Ende Tag 4
        assert not info.recovered

    def test_empty_curve(self) -> None:
        info = compute_drawdown(pd.DataFrame({"time": [], "equity": []}))
        assert info.max_drawdown_pct == 0.0


class TestSharpeAndSortino:
    def test_sharpe_matches_manual_calculation(self) -> None:
        returns = np.array([0.01, -0.005, 0.02, 0.0, 0.015])
        expected = (
            float(np.mean(returns)) / float(np.std(returns, ddof=1)) * math.sqrt(365)
        )
        assert _sharpe(returns) == pytest.approx(expected)

    def test_zero_volatility_gives_zero(self) -> None:
        """Keine Streuung heisst keine Aussage - nicht 'unendlich gut'."""
        assert _sharpe(np.array([0.01, 0.01, 0.01])) == 0.0

    def test_too_few_points_gives_zero(self) -> None:
        assert _sharpe(np.array([0.01])) == 0.0

    def test_sortino_ignores_upside_volatility(self) -> None:
        """Der Sortino bestraft nur Abwaertsbewegungen.

        Wichtig fuer Strategien mit wenigen grossen Gewinnen: Der Sharpe wertet
        diese als 'Volatilitaet', obwohl sie genau das Gewuenschte sind.
        """
        spiky = np.array([0.001, 0.001, 0.10, 0.001, -0.002])
        assert _sortino(spiky) > _sharpe(spiky)

    def test_sortino_without_losses_is_infinite(self) -> None:
        assert _sortino(np.array([0.01, 0.02, 0.03])) == float("inf")


class TestTradeStatistics:
    def test_win_rate_and_profit_factor(self) -> None:
        """3 Gewinne a 10, 2 Verluste a -5 -> 60 % Trefferquote, Faktor 3,0."""
        trades = [
            make_trade(pnl="10", index=0),
            make_trade(pnl="10", index=1),
            make_trade(pnl="10", index=2),
            make_trade(pnl="-5", index=3),
            make_trade(pnl="-5", index=4),
        ]
        metrics = compute_metrics(
            trades, equity_curve([500, 520]), initial_equity=Decimal("500")
        )

        assert metrics.win_rate == pytest.approx(0.6)
        assert metrics.profit_factor == pytest.approx(3.0)
        assert metrics.expectancy == pytest.approx(4.0)  # (30 - 10) / 5

    def test_expectancy_in_r_is_size_independent(self) -> None:
        """Das R-Vielfache ist die einzige Kennzahl, die sich zwischen Backtest
        und Livebetrieb direkt vergleichen laesst.

        Risiko je Trade: |100000 - 99400| x 0,006 = 3,60. Ein Gewinn von 5,40
        entspricht also genau 1,5 R.
        """
        trades = [make_trade(pnl="5.40", index=i) for i in range(4)]
        metrics = compute_metrics(
            trades, equity_curve([500, 521.6]), initial_equity=Decimal("500")
        )
        assert metrics.expectancy_r == pytest.approx(1.5)

    def test_max_consecutive_losses(self) -> None:
        """Wichtig fuer die Frage, ob man die Strategie durchhaelt.

        Acht Verluste in Folge fuehlen sich wie ein defektes System an, sind bei
        45 % Trefferquote aber voellig normal.
        """
        pnls = np.array([1.0, -1, -1, -1, 2.0, -1, -1, 3.0])
        assert _max_consecutive_losses(pnls) == 3

    def test_fees_share_of_gross_profit(self) -> None:
        """Bei kleinem Konto die wichtigste Betriebskennzahl.

        Frisst die Gebuehr die Haelfte des Bruttogewinns, ist die Strategie zu
        handelsintensiv fuer diese Kontogroesse.
        """
        trades = [make_trade(pnl="10", fees="1", index=i) for i in range(5)]
        metrics = compute_metrics(
            trades,
            equity_curve([500, 545]),
            initial_equity=Decimal("500"),
            total_fees=Decimal("5"),
        )
        assert metrics.fees_pct_of_gross == pytest.approx(10.0)  # 5 von 50 brutto

    def test_exit_reasons_are_counted(self) -> None:
        trades = [
            make_trade(pnl="5", index=0, reason="take_profit"),
            make_trade(pnl="-3", index=1, reason="stop_loss"),
            make_trade(pnl="-3", index=2, reason="stop_loss"),
        ]
        metrics = compute_metrics(
            trades, equity_curve([500, 499]), initial_equity=Decimal("500")
        )
        assert metrics.exit_reasons == {"take_profit": 1, "stop_loss": 2}

    def test_no_trades_yields_zeros_not_errors(self) -> None:
        metrics = compute_metrics([], equity_curve([500, 500]), initial_equity=Decimal("500"))
        assert metrics.trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.profit_factor == 0.0
        assert not metrics.is_profitable


class TestAggregateMetrics:
    def test_trades_per_month(self) -> None:
        """Deine Vorgabe war: nicht nur einmal im Monat handeln."""
        trades = [make_trade(pnl="1", index=i) for i in range(30)]
        curve = equity_curve([500 + i for i in range(31)])
        metrics = compute_metrics(trades, curve, initial_equity=Decimal("500"))

        assert metrics.trades_per_month == pytest.approx(30.44, abs=0.5)

    def test_calmar_relates_return_to_drawdown(self) -> None:
        curve = equity_curve([500, 600, 550, 700], step=timedelta(days=120))
        metrics = compute_metrics(
            [make_trade(pnl="200", index=0)], curve, initial_equity=Decimal("500")
        )
        assert metrics.max_drawdown_pct == pytest.approx(50 / 600 * 100)
        assert metrics.calmar > 0

    def test_summary_is_readable(self) -> None:
        trades = [make_trade(pnl="5", index=i) for i in range(10)]
        metrics = compute_metrics(
            trades,
            equity_curve([500 + i * 5 for i in range(11)]),
            initial_equity=Decimal("500"),
            total_fees=Decimal("2.4"),
        )
        summary = metrics.summary()

        assert "Trades" in summary
        assert "Sharpe" in summary
        assert "MaxDD" in summary
        assert "R" in summary
