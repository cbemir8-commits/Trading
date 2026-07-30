"""Walk-Forward-Auswertung.

Ein einzelner Backtest ueber sechs Jahre sagt wenig: Er zeigt, ob eine
Strategie *irgendwann* funktioniert hat, nicht ob sie *durchgehend*
funktioniert. Der Walk-Forward zerlegt den Zeitraum in aufeinanderfolgende
Fenster und wertet jedes einzeln aus. Eine Strategie, die in zwei von acht
Fenstern glaenzt und in sechs verliert, faellt hier auf - im Gesamtergebnis
wuerde sie moeglicherweise profitabel aussehen.

Zwei Feinheiten, die ueber die Aussagekraft entscheiden:

**Aufwaermdaten aus der Vergangenheit.** Jedes Testfenster braucht Kerzen
*vor* seinem Beginn, damit die Indikatoren eingeschwungen sind. Ohne sie waeren
die ersten 50 bis 600 Kerzen jedes Fensters signallos - die Strategie wuerde
systematisch zu wenige Trades machen, und zwar genau am Fensteranfang. Die
Aufwaermdaten kommen aus dem Zeitraum davor, aber es werden **nur Trades
gezaehlt, die im Testfenster eroeffnet wurden**.

**Sperrzone (Embargo).** Zwischen Trainings- und Testzeitraum bleibt eine
Luecke. Ein Trade, der kurz vor dem Schnitt eroeffnet wurde, laeuft sonst in
den Testzeitraum hinein und verbindet beide - genau die Vermischung, die der
Walk-Forward verhindern soll.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd
import structlog

from backtest.engine import BacktestConfig, Backtester, BacktestResult
from backtest.metrics import Metrics, compute_metrics
from core.models import Trade
from strategy.base import Strategy

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Window:
    """Ein Walk-Forward-Fenster."""

    index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime

    def describe(self) -> str:
        return (
            f"Fenster {self.index}: Training {self.train_start:%Y-%m} bis "
            f"{self.train_end:%Y-%m}, Test {self.test_start:%Y-%m-%d} bis "
            f"{self.test_end:%Y-%m-%d}"
        )


@dataclass(slots=True)
class WindowResult:
    window: Window
    metrics: Metrics
    trades: list[Trade]
    result: BacktestResult

    @property
    def is_profitable(self) -> bool:
        return self.metrics.net_profit > 0


@dataclass(slots=True)
class WalkForwardReport:
    """Gesamtergebnis ueber alle Fenster."""

    windows: list[WindowResult] = field(default_factory=list)
    combined: Metrics | None = None
    all_trades: list[Trade] = field(default_factory=list)

    @property
    def window_count(self) -> int:
        return len(self.windows)

    @property
    def profitable_windows(self) -> int:
        return sum(1 for w in self.windows if w.is_profitable)

    @property
    def consistency(self) -> float:
        """Anteil profitabler Fenster.

        Aussagekraeftiger als die Gesamtrendite: Eine Strategie mit 60 %
        profitablen Fenstern ist belastbarer als eine, die ihren gesamten
        Gewinn aus einem einzigen Ausreisser zieht.
        """
        if not self.windows:
            return 0.0
        return self.profitable_windows / len(self.windows)

    @property
    def worst_window(self) -> WindowResult | None:
        if not self.windows:
            return None
        return min(self.windows, key=lambda w: w.metrics.net_profit)

    def summary(self) -> str:
        if not self.windows or self.combined is None:
            return "Walk-Forward ohne Ergebnis"
        return (
            f"{self.window_count} Fenster, davon {self.profitable_windows} profitabel "
            f"({self.consistency:.0%}) | {self.combined.summary()}"
        )


class WalkForwardSplitter:
    """Erzeugt rollierende Trainings-/Testfenster.

    Beispiel bei 12 Monaten Training, 3 Monaten Test und 3 Tagen Sperrzone
    ueber den Zeitraum 2020-2026: rund 21 Fenster, die jeweils drei Monate
    weiterruecken.
    """

    def __init__(
        self,
        *,
        train_months: int = 12,
        test_months: int = 3,
        embargo: timedelta = timedelta(days=3),
        anchored: bool = False,
    ) -> None:
        self.train_months = train_months
        self.test_months = test_months
        self.embargo = embargo
        self.anchored = anchored
        """``True`` laesst den Trainingsbeginn fest und verlaengert das Fenster
        nur nach vorn. Realistischer, wenn die Strategie im Betrieb auf der
        gesamten Historie neu bewertet wird; ``False`` (rollierend) prueft
        haerter auf Anpassungsfaehigkeit."""

    def split(self, start: datetime, end: datetime) -> list[Window]:
        windows: list[Window] = []
        train_start = start
        train_end = _add_months(start, self.train_months)

        index = 0
        while True:
            test_start = train_end + self.embargo
            test_end = _add_months(test_start, self.test_months)
            if test_end > end:
                break

            windows.append(
                Window(
                    index=index,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )
            index += 1
            train_end = _add_months(train_end, self.test_months)
            if not self.anchored:
                train_start = _add_months(train_start, self.test_months)

        return windows


def run_walkforward(
    frame: pd.DataFrame,
    build_strategy,  # noqa: ANN001 - Callable[[], Strategy]
    config: BacktestConfig,
    splitter: WalkForwardSplitter,
    *,
    sub_frame: pd.DataFrame | None = None,
) -> WalkForwardReport:
    """Strategie ueber alle Testfenster auswerten.

    ``build_strategy`` erzeugt fuer jedes Fenster eine **frische** Instanz.
    Das ist notwendig, weil eine Strategie internen Zustand halten darf
    (Sperrfrist, letzter Einstieg) - eine wiederverwendete Instanz wuerde
    Zustand ueber Fenstergrenzen hinweg schleppen.
    """
    if frame.empty:
        return WalkForwardReport()

    start = frame["open_time"].iloc[0].to_pydatetime()
    end = frame["open_time"].iloc[-1].to_pydatetime()
    windows = splitter.split(start, end)

    if not windows:
        log.warning(
            "walkforward.zu_wenig_daten",
            von=start.isoformat(),
            bis=end.isoformat(),
            benoetigt_monate=splitter.train_months + splitter.test_months,
        )
        return WalkForwardReport()

    report = WalkForwardReport()

    for window in windows:
        strategy: Strategy = build_strategy()
        window_result = _run_window(frame, strategy, config, window, sub_frame)
        if window_result is not None:
            report.windows.append(window_result)
            report.all_trades.extend(window_result.trades)

    if report.windows:
        report.combined = _combine(report.windows, config.initial_equity)

    log.info("walkforward.fertig", zusammenfassung=report.summary())
    return report


def _run_window(
    frame: pd.DataFrame,
    strategy: Strategy,
    config: BacktestConfig,
    window: Window,
    sub_frame: pd.DataFrame | None,
) -> WindowResult | None:
    """Ein Fenster auswerten.

    Der Backtest laeuft ueber [Testbeginn - Aufwaermphase, Testende], gezaehlt
    werden aber nur Trades, die **im Testfenster** eroeffnet wurden. Ohne die
    Aufwaermdaten waere der Anfang jedes Fensters signallos.
    """
    warmup_bars = getattr(strategy, "warmup_bars", 30)
    bar_step = _infer_step(frame)
    run_start = window.test_start - bar_step * warmup_bars

    mask = (frame["open_time"] >= pd.Timestamp(run_start)) & (
        frame["open_time"] < pd.Timestamp(window.test_end)
    )
    window_frame = frame.loc[mask].reset_index(drop=True)

    if len(window_frame) <= warmup_bars + 10:
        return None

    window_subs = None
    if sub_frame is not None:
        sub_mask = (sub_frame["open_time"] >= pd.Timestamp(run_start)) & (
            sub_frame["open_time"] < pd.Timestamp(window.test_end)
        )
        window_subs = sub_frame.loc[sub_mask].reset_index(drop=True)

    result = Backtester(config).run(window_frame, strategy, sub_frame=window_subs)

    # Nur Trades zaehlen, die im eigentlichen Testfenster eroeffnet wurden.
    in_window = [t for t in result.trades if t.entry_time >= window.test_start]
    equity = result.equity_curve
    if not equity.empty:
        equity = equity.loc[equity["time"] >= pd.Timestamp(window.test_start)].reset_index(
            drop=True
        )

    metrics = compute_metrics(
        in_window,
        equity,
        initial_equity=config.initial_equity,
        total_fees=sum((t.fees for t in in_window), Decimal(0)),
        total_funding=sum((t.funding for t in in_window), Decimal(0)),
    )
    return WindowResult(window=window, metrics=metrics, trades=in_window, result=result)


def _combine(windows: list[WindowResult], initial_equity: Decimal) -> Metrics:
    """Alle Fenster zu einer Gesamtsicht zusammenfassen.

    Die Kapitalkurven werden aneinandergehaengt und auf einen durchgehenden
    Verlauf normiert. So ergibt sich ein Drawdown ueber alle Fenster hinweg -
    also die Zahl, die der Kill-Switch im Livebetrieb sehen wuerde.
    """
    trades: list[Trade] = []
    pieces: list[pd.DataFrame] = []
    offset = float(initial_equity)

    for window in windows:
        trades.extend(window.trades)
        curve = window.result.equity_curve
        if curve.empty:
            continue
        curve = curve.loc[
            curve["time"] >= pd.Timestamp(window.window.test_start)
        ].reset_index(drop=True)
        if curve.empty:
            continue
        shifted = curve.copy()
        shifted["equity"] = curve["equity"] - float(initial_equity) + offset
        pieces.append(shifted)
        offset = float(shifted["equity"].iloc[-1])

    combined_curve = (
        pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame({"time": [], "equity": []})
    )

    return compute_metrics(
        trades,
        combined_curve,
        initial_equity=initial_equity,
        total_fees=sum((t.fees for t in trades), Decimal(0)),
        total_funding=sum((t.funding for t in trades), Decimal(0)),
    )


def _infer_step(frame: pd.DataFrame) -> timedelta:
    """Kerzenabstand aus den Daten ableiten - robust gegen einzelne Luecken."""
    if len(frame) < 3:
        return timedelta(minutes=15)
    deltas = frame["open_time"].diff().dropna()
    return pd.Timedelta(deltas.median()).to_pytimedelta()


def _add_months(moment: datetime, months: int) -> datetime:
    """Monate addieren, ohne externe Abhaengigkeit.

    Ueberlaufende Tage werden auf den Monatsletzten begrenzt - der 31. Januar
    plus einen Monat ist der 28. bzw. 29. Februar.
    """
    total = moment.month - 1 + months
    year = moment.year + total // 12
    month = total % 12 + 1
    day = min(moment.day, _days_in_month(year, month))
    return moment.replace(year=year, month=month, day=day)


def _days_in_month(year: int, month: int) -> int:
    import calendar

    return calendar.monthrange(year, month)[1]
