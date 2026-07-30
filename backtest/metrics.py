"""Kennzahlen eines Backtests.

Der Sharpe-Quotient wird aus **taeglichen** Kapitalrenditen berechnet, nicht aus
Trade-Ergebnissen. Grund: Eine Strategie mit 30 Trades im Monat haette sonst
eine Stichprobe, deren Streuung stark von der Haltedauer abhaengt - zwei
Strategien mit gleicher Rendite, aber unterschiedlicher Trade-Frequenz waeren
nicht vergleichbar. Annualisiert wird mit sqrt(365), da Krypto rund um die Uhr
handelt.

Die wichtigste Zahl in diesem Modul ist ``expectancy_r``: das durchschnittliche
Ergebnis je Trade in Vielfachen des riskierten Betrags. Sie ist unabhaengig von
Positionsgroesse und Kontostand und damit die einzige Kennzahl, die sich
zwischen Backtest und Livebetrieb direkt vergleichen laesst.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

from core.models import Trade

#: Krypto handelt durchgehend.
TRADING_DAYS_PER_YEAR = 365


@dataclass(frozen=True, slots=True)
class DrawdownInfo:
    max_drawdown_pct: float
    max_drawdown_abs: float
    peak_time: pd.Timestamp | None
    trough_time: pd.Timestamp | None
    recovery_time: pd.Timestamp | None
    longest_days: float

    @property
    def recovered(self) -> bool:
        return self.recovery_time is not None


@dataclass(frozen=True, slots=True)
class Metrics:
    # Ergebnis
    trades: int
    net_profit: float
    total_return_pct: float
    cagr_pct: float

    # Risiko
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown_pct: float
    drawdown: DrawdownInfo

    # Trade-Qualitaet
    win_rate: float
    profit_factor: float
    expectancy: float
    expectancy_r: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    max_consecutive_losses: int

    # Betrieb
    avg_duration_hours: float
    trades_per_month: float
    total_fees: float
    fees_pct_of_gross: float
    total_funding: float

    exit_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def is_profitable(self) -> bool:
        return self.net_profit > 0

    def summary(self) -> str:
        return (
            f"{self.trades} Trades ({self.trades_per_month:.1f}/Monat), "
            f"Rendite {self.total_return_pct:+.2f} %, "
            f"Sharpe {self.sharpe:.2f}, MaxDD {self.max_drawdown_pct:.2f} %, "
            f"Trefferquote {self.win_rate:.1%}, "
            f"Erwartung {self.expectancy_r:+.3f} R, "
            f"Gebuehren {self.fees_pct_of_gross:.1f} % vom Bruttogewinn"
        )


def compute_metrics(
    trades: list[Trade],
    equity_curve: pd.DataFrame,
    *,
    initial_equity: Decimal,
    total_fees: Decimal = Decimal(0),
    total_funding: Decimal = Decimal(0),
) -> Metrics:
    """Kennzahlen aus Trades und Kapitalkurve berechnen."""
    start_equity = float(initial_equity)
    drawdown = compute_drawdown(equity_curve)

    if equity_curve.empty:
        final_equity = start_equity
        span_days = 0.0
    else:
        final_equity = float(equity_curve["equity"].iloc[-1])
        span = equity_curve["time"].iloc[-1] - equity_curve["time"].iloc[0]
        span_days = max(pd.Timedelta(span).total_seconds() / 86_400, 0.0)

    net_profit = final_equity - start_equity
    total_return_pct = (net_profit / start_equity * 100) if start_equity else 0.0
    cagr = _cagr(start_equity, final_equity, span_days)

    daily = _daily_returns(equity_curve)
    sharpe = _sharpe(daily)
    sortino = _sortino(daily)
    calmar = (
        cagr / drawdown.max_drawdown_pct
        if drawdown.max_drawdown_pct > 0
        else (float("inf") if cagr > 0 else 0.0)
    )

    stats = _trade_stats(trades)
    months = span_days / 30.44 if span_days > 0 else 0.0

    gross_profit = sum(float(t.gross_pnl) for t in trades if t.gross_pnl > 0)
    fees = float(total_fees)

    return Metrics(
        trades=len(trades),
        net_profit=net_profit,
        total_return_pct=total_return_pct,
        cagr_pct=cagr,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown_pct=drawdown.max_drawdown_pct,
        drawdown=drawdown,
        win_rate=stats["win_rate"],
        profit_factor=stats["profit_factor"],
        expectancy=stats["expectancy"],
        expectancy_r=stats["expectancy_r"],
        avg_win=stats["avg_win"],
        avg_loss=stats["avg_loss"],
        largest_win=stats["largest_win"],
        largest_loss=stats["largest_loss"],
        max_consecutive_losses=stats["max_consecutive_losses"],
        avg_duration_hours=stats["avg_duration_hours"],
        trades_per_month=(len(trades) / months) if months > 0 else 0.0,
        total_fees=fees,
        fees_pct_of_gross=(fees / gross_profit * 100) if gross_profit > 0 else 0.0,
        total_funding=float(total_funding),
        exit_reasons=stats["exit_reasons"],
    )


def compute_drawdown(equity_curve: pd.DataFrame) -> DrawdownInfo:
    """Groesster Rueckgang vom Hoechststand.

    Der Drawdown wird auf dem *laufenden Hoch* gemessen, nicht auf dem
    Startkapital - das ist die Zahl, die der Kill-Switch ueberwacht und die
    ein Anleger tatsaechlich erlebt.
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return DrawdownInfo(0.0, 0.0, None, None, None, 0.0)

    equity = equity_curve["equity"].to_numpy(dtype=float)
    times = equity_curve["time"]

    running_peak = np.maximum.accumulate(equity)
    drawdown_abs = running_peak - equity
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdown_pct = np.where(running_peak > 0, drawdown_abs / running_peak * 100, 0.0)

    trough_idx = int(np.argmax(drawdown_pct))
    max_dd_pct = float(drawdown_pct[trough_idx])
    max_dd_abs = float(drawdown_abs[trough_idx])

    if max_dd_pct <= 0:
        return DrawdownInfo(0.0, 0.0, None, None, None, 0.0)

    peak_idx = int(np.argmax(equity[: trough_idx + 1]))
    peak_value = equity[peak_idx]

    recovery_idx = None
    after = np.flatnonzero(equity[trough_idx:] >= peak_value)
    if after.size > 0:
        recovery_idx = trough_idx + int(after[0])

    longest = _longest_underwater_days(equity, times)

    return DrawdownInfo(
        max_drawdown_pct=max_dd_pct,
        max_drawdown_abs=max_dd_abs,
        peak_time=times.iloc[peak_idx],
        trough_time=times.iloc[trough_idx],
        recovery_time=times.iloc[recovery_idx] if recovery_idx is not None else None,
        longest_days=longest,
    )


def _longest_underwater_days(equity: np.ndarray, times: pd.Series) -> float:
    """Laengste Spanne vom Hoechststand bis zur vollstaendigen Erholung.

    Gemessen wird **Hoch zu Erholung**, nicht die Zahl der Tage strikt
    unterhalb. Das ist die uebliche Definition der Drawdown-Dauer, weil genau
    diese Spanne der Anleger als 'es geht nicht voran' erlebt. Erholt sich das
    Kapital nie, laeuft die Uhr bis zum letzten Datenpunkt.

    Psychologisch oft wichtiger als die Tiefe: Ein Drawdown von 8 %, der zwei
    Tage dauert, ist auszuhalten. Dieselben 8 % ueber sieben Monate treiben
    Anleger zum Abschalten des Systems - meist genau vor der Erholung.
    """
    peak = -np.inf
    peak_time = None
    longest = 0.0

    for value, moment in zip(equity, times, strict=True):
        if value >= peak:
            if peak_time is not None:
                span = pd.Timedelta(moment - peak_time).total_seconds() / 86_400
                longest = max(longest, span)
            peak = value
            peak_time = moment

    if peak_time is not None and len(times) > 0:
        span = pd.Timedelta(times.iloc[-1] - peak_time).total_seconds() / 86_400
        longest = max(longest, span)
    return longest


def _daily_returns(equity_curve: pd.DataFrame) -> np.ndarray:
    if equity_curve.empty or len(equity_curve) < 3:
        return np.array([])

    series = equity_curve.set_index("time")["equity"]
    daily = series.resample("1D").last().ffill()
    returns = daily.pct_change().dropna().to_numpy(dtype=float)
    return returns[np.isfinite(returns)]


def _sharpe(daily_returns: np.ndarray) -> float:
    """Annualisierter Sharpe-Quotient, risikofreier Zins auf null gesetzt.

    Bei kurzen Zeitreihen ist er sehr instabil - deshalb verlangt das
    Zulassungs-Gate zusaetzlich eine Mindestzahl an Trades. Ein Sharpe von 3,0
    aus 12 Trades ist keine Aussage, sondern Zufall.
    """
    if daily_returns.size < 2:
        return 0.0
    std = float(np.std(daily_returns, ddof=1))
    if std == 0:
        return 0.0
    return float(np.mean(daily_returns)) / std * math.sqrt(TRADING_DAYS_PER_YEAR)


def _sortino(daily_returns: np.ndarray) -> float:
    """Wie Sharpe, misst aber nur die Abwaertsschwankung.

    Aussagekraeftiger fuer Strategien mit wenigen grossen Gewinnen: Der Sharpe
    bestraft diese als 'Volatilitaet', obwohl sie genau das Gewuenschte sind.
    """
    if daily_returns.size < 2:
        return 0.0
    downside = daily_returns[daily_returns < 0]
    if downside.size == 0:
        return float("inf") if float(np.mean(daily_returns)) > 0 else 0.0
    deviation = float(np.sqrt(np.mean(downside**2)))
    if deviation == 0:
        return 0.0
    return float(np.mean(daily_returns)) / deviation * math.sqrt(TRADING_DAYS_PER_YEAR)


def _cagr(start: float, end: float, days: float) -> float:
    if start <= 0 or end <= 0 or days <= 0:
        return 0.0
    years = days / 365.25
    if years <= 0:
        return 0.0
    return ((end / start) ** (1 / years) - 1) * 100


def _trade_stats(trades: list[Trade]) -> dict:
    if not trades:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "expectancy_r": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "max_consecutive_losses": 0,
            "avg_duration_hours": 0.0,
            "exit_reasons": {},
        }

    pnls = np.array([float(t.net_pnl) for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]

    gross_win = float(wins.sum()) if wins.size else 0.0
    gross_loss = abs(float(losses.sum())) if losses.size else 0.0

    r_values = [float(t.r_multiple) for t in trades if t.r_multiple is not None]

    durations = [t.duration for t in trades]
    avg_duration = (
        sum(durations, timedelta()).total_seconds() / len(durations) / 3600
        if durations
        else 0.0
    )

    exit_reasons: dict[str, int] = {}
    for trade in trades:
        exit_reasons[trade.exit_reason] = exit_reasons.get(trade.exit_reason, 0) + 1

    return {
        "win_rate": float(wins.size / len(trades)),
        "profit_factor": (
            gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
        ),
        "expectancy": float(pnls.mean()),
        "expectancy_r": float(np.mean(r_values)) if r_values else 0.0,
        "avg_win": float(wins.mean()) if wins.size else 0.0,
        "avg_loss": float(losses.mean()) if losses.size else 0.0,
        "largest_win": float(pnls.max()),
        "largest_loss": float(pnls.min()),
        "max_consecutive_losses": _max_consecutive_losses(pnls),
        "avg_duration_hours": avg_duration,
        "exit_reasons": exit_reasons,
    }


def _max_consecutive_losses(pnls: np.ndarray) -> int:
    """Laengste Verlustserie.

    Wichtig fuer die Frage, ob man die Strategie im Livebetrieb durchhaelt:
    Acht Verluste in Folge fuehlen sich wie ein kaputtes System an, sind bei
    45 % Trefferquote aber voellig normal.
    """
    longest = 0
    current = 0
    for value in pnls:
        if value <= 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest
