"""Tests fuer Walk-Forward und Zulassungs-Gates.

Der wichtigste Test hier ist ``test_overfitted_genome_is_rejected``: Er baut
absichtlich eine ueberangepasste Strategie und verlangt, dass die Gates sie
ablehnen. Ein Gate-System, das nur bestaetigt was ohnehin gut ist, waere
wertlos - es muss beweisen, dass es auch ablehnt.
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.costs import CostModel, FundingSchedule
from backtest.engine import BacktestConfig
from backtest.metrics import compute_metrics
from backtest.walkforward import (
    WalkForwardReport,
    WalkForwardSplitter,
    WindowResult,
    _add_months,
    run_walkforward,
)
from core.config import RiskSettings
from core.models import Candle, Instrument, Interval, Side, Trade
from data.store import candles_to_frame
from research.gates import (
    GateStatus,
    GateThresholds,
    _vary_periods,
    classify_regimes,
    deflated_sharpe_ratio,
    evaluate_gates,
    gate_consistency,
    gate_drawdown,
    gate_monte_carlo,
    gate_oos_sharpe,
    gate_regime_split,
    gate_sample_size,
)
from strategy.compiler import compile_genome
from strategy.genome import Condition, Genome, Operand, Operator, StopSpec, TargetSpec

T0 = datetime(2021, 1, 1, tzinfo=UTC)


def ind(name: str, **params: int) -> Operand:
    return Operand(kind="indicator", name=name, params=params)


def price(name: str) -> Operand:
    return Operand(kind="price", name=name)


@pytest.fixture
def config(btcusdt: Instrument, risk: RiskSettings) -> BacktestConfig:
    return BacktestConfig(
        instrument=btcusdt,
        risk=risk,
        costs=CostModel(),
        funding=FundingSchedule(default_rate=Decimal(0)),
        initial_equity=Decimal("500"),
    )


def make_trade(pnl: str, *, hours_offset: int = 0, index: int = 0) -> Trade:
    return Trade(
        trade_id=f"t{index}",
        symbol="BTCUSDT",
        side=Side.BUY,
        strategy_id="test",
        entry_time=T0 + timedelta(hours=hours_offset),
        entry_price=Decimal("100000"),
        exit_time=T0 + timedelta(hours=hours_offset + 4),
        exit_price=Decimal("100000"),
        qty=Decimal("0.006"),
        gross_pnl=Decimal(pnl),
        fees=Decimal("0.24"),
        stop_loss=Decimal("99400"),
    )


def long_series(count: int, *, seed: int = 7) -> pd.DataFrame:
    """Realistisch schwankende Reihe ueber mehrere Jahre.

    Zufaellige Schritte mit leichtem Aufwaertsdrift - so entsteht kein
    kuenstliches Muster, das jede Strategie profitabel machen wuerde.
    """
    rng = np.random.default_rng(seed)
    steps = rng.normal(loc=0.6, scale=110, size=count)
    closes = 30_000 + np.cumsum(steps)
    closes = np.maximum(closes, 5_000)

    candles = []
    for i in range(count):
        close = closes[i]
        open_price = closes[i - 1] if i > 0 else close
        spread = abs(rng.normal(0, 90))
        candles.append(
            Candle(
                open_time=T0 + Interval.M15.duration * i,
                open=Decimal(f"{open_price:.1f}"),
                high=Decimal(f"{max(open_price, close) + spread:.1f}"),
                low=Decimal(f"{min(open_price, close) - spread:.1f}"),
                close=Decimal(f"{close:.1f}"),
                volume=Decimal(f"{abs(rng.normal(12, 4)) + 1:.3f}"),
                turnover=Decimal("1000000"),
            )
        )
    return candles_to_frame(candles)


# ---------------------------------------------------------------------------
#  Walk-Forward
# ---------------------------------------------------------------------------
class TestSplitter:
    def test_windows_do_not_overlap_in_test_period(self) -> None:
        """Testfenster muessen disjunkt sein - sonst wird derselbe Zeitraum
        mehrfach gezaehlt und die Stichprobe kuenstlich vergroessert."""
        windows = WalkForwardSplitter(train_months=12, test_months=3).split(
            datetime(2020, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)
        )
        assert len(windows) > 5
        for earlier, later in itertools.pairwise(windows):
            assert earlier.test_end <= later.test_start

    def test_embargo_separates_train_and_test(self) -> None:
        """Die Sperrzone verhindert, dass ein Trade beide Zeitraeume verbindet."""
        embargo = timedelta(days=5)
        windows = WalkForwardSplitter(
            train_months=12, test_months=3, embargo=embargo
        ).split(datetime(2020, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC))

        for window in windows:
            assert window.test_start - window.train_end == embargo

    def test_anchored_keeps_training_start_fixed(self) -> None:
        windows = WalkForwardSplitter(
            train_months=12, test_months=3, anchored=True
        ).split(datetime(2020, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC))

        starts = {w.train_start for w in windows}
        assert len(starts) == 1, "Verankert heisst: Trainingsbeginn bleibt fest"

    def test_rolling_moves_training_start(self) -> None:
        windows = WalkForwardSplitter(
            train_months=12, test_months=3, anchored=False
        ).split(datetime(2020, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC))

        starts = {w.train_start for w in windows}
        assert len(starts) == len(windows)

    def test_too_short_period_yields_no_windows(self) -> None:
        windows = WalkForwardSplitter(train_months=12, test_months=3).split(
            datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 6, 1, tzinfo=UTC)
        )
        assert windows == []

    def test_month_arithmetic_handles_month_ends(self) -> None:
        """31. Januar plus einen Monat ist der 28./29. Februar, nicht der 3. Maerz."""
        assert _add_months(datetime(2026, 1, 31, tzinfo=UTC), 1).day == 28
        assert _add_months(datetime(2024, 1, 31, tzinfo=UTC), 1).day == 29  # Schaltjahr


class TestWalkForwardRun:
    def test_only_counts_trades_opened_in_test_window(
        self, config: BacktestConfig
    ) -> None:
        """Aufwaermdaten stammen aus der Vergangenheit, zaehlen aber nicht mit.

        Ohne die Aufwaermdaten waeren die ersten Kerzen jedes Fensters
        signallos - die Strategie wuerde systematisch zu wenige Trades machen,
        und zwar genau am Fensteranfang.
        """
        frame = long_series(60_000)
        genome = Genome(
            name="Kreuzung",
            rationale="Einfache Durchschnittskreuzung fuer den Walk-Forward-Test.",
            entry_long=[
                Condition(left=ind("ema", period=10), op=Operator.CROSS_ABOVE,
                          right=ind("ema", period=40))
            ],
            stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
            targets=[TargetSpec(rr=2.0, portion=1.0)],
            cooldown_bars=8,
        )
        report = run_walkforward(
            frame,
            lambda: compile_genome(genome),
            config,
            WalkForwardSplitter(train_months=6, test_months=3),
        )

        assert report.window_count >= 2
        for window in report.windows:
            for trade in window.trades:
                assert trade.entry_time >= window.window.test_start

    def test_fresh_strategy_per_window(self, config: BacktestConfig) -> None:
        """Jedes Fenster braucht eine neue Instanz.

        Sonst schleppt die Sperrfrist Zustand ueber Fenstergrenzen - das
        Ergebnis haenge dann davon ab, in welcher Reihenfolge ausgewertet wurde.
        """
        built: list[int] = []
        frame = long_series(40_000)
        genome = Genome(
            name="Zaehler",
            rationale="Zaehlt, wie oft eine Strategie-Instanz erzeugt wird.",
            entry_long=[Condition(left=price("close"), op=Operator.GT,
                                  right=ind("ema", period=20))],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
            cooldown_bars=50,
        )

        def build():
            built.append(1)
            return compile_genome(genome)

        report = run_walkforward(
            frame, build, config, WalkForwardSplitter(train_months=6, test_months=3)
        )
        assert len(built) == report.window_count

    def test_empty_frame_yields_empty_report(self, config: BacktestConfig) -> None:
        from data.store import empty_frame

        report = run_walkforward(
            empty_frame(), lambda: None, config, WalkForwardSplitter()
        )
        assert report.window_count == 0


# ---------------------------------------------------------------------------
#  Einzelne Gates
# ---------------------------------------------------------------------------
def make_report(
    *, trades: list[Trade], sharpe: float, drawdown: float, profitable_windows: int,
    total_windows: int,
) -> WalkForwardReport:
    """Baut einen Walk-Forward-Bericht mit vorgegebenen Kennzahlen."""
    report = WalkForwardReport(all_trades=trades)
    curve = pd.DataFrame(
        {
            "time": [T0 + timedelta(days=i) for i in range(10)],
            "equity": [500.0] * 10,
        }
    )
    base = compute_metrics(trades, curve, initial_equity=Decimal("500"))
    # Metrics ist ein frozen dataclass mit slots - kein __dict__, also replace().
    report.combined = replace(base, sharpe=sharpe, max_drawdown_pct=drawdown)

    for i in range(total_windows):
        pnl = Decimal("10") if i < profitable_windows else Decimal("-10")
        # Die Kapitalkurve muss das Fensterergebnis abbilden - is_profitable
        # liest den Kurvenverlauf, nicht die Trades.
        window_curve = pd.DataFrame(
            {
                "time": [T0 + timedelta(days=i * 10), T0 + timedelta(days=i * 10 + 5)],
                "equity": [500.0, 500.0 + float(pnl)],
            }
        )
        window_metrics = compute_metrics(
            [make_trade(str(pnl), index=i)], window_curve, initial_equity=Decimal("500")
        )
        report.windows.append(
            WindowResult(window=None, metrics=window_metrics, trades=[], result=None)  # type: ignore[arg-type]
        )
    return report


class TestIndividualGates:
    def test_sample_size_rejects_too_few_trades(self) -> None:
        report = make_report(
            trades=[make_trade("5", index=i) for i in range(20)],
            sharpe=3.0, drawdown=5.0, profitable_windows=8, total_windows=8,
        )
        result = gate_sample_size(report, GateThresholds())

        assert result.status is GateStatus.FAIL
        assert "zu wenig" in result.message.lower()

    def test_sample_size_accepts_enough_trades(self) -> None:
        report = make_report(
            trades=[make_trade("5", index=i) for i in range(150)],
            sharpe=1.5, drawdown=8.0, profitable_windows=6, total_windows=8,
        )
        assert gate_sample_size(report, GateThresholds()).status is GateStatus.PASS

    def test_sharpe_gate(self) -> None:
        weak = make_report(trades=[make_trade("1", index=i) for i in range(150)],
                           sharpe=0.4, drawdown=5.0, profitable_windows=5, total_windows=8)
        strong = make_report(trades=[make_trade("1", index=i) for i in range(150)],
                             sharpe=1.6, drawdown=5.0, profitable_windows=5, total_windows=8)

        assert gate_oos_sharpe(weak, GateThresholds()).status is GateStatus.FAIL
        assert gate_oos_sharpe(strong, GateThresholds()).status is GateStatus.PASS

    def test_drawdown_gate_is_stricter_than_kill_switch(self) -> None:
        """12 % Schwelle gegen 15 % Kill-Switch.

        Eine Strategie, die im Backtest schon an die Abschaltgrenze stoesst,
        reisst sie live mit Sicherheit.
        """
        thresholds = GateThresholds()
        assert thresholds.max_oos_drawdown_pct < 15.0

        report = make_report(trades=[make_trade("1", index=i) for i in range(150)],
                             sharpe=2.0, drawdown=14.0, profitable_windows=6,
                             total_windows=8)
        assert gate_drawdown(report, thresholds).status is GateStatus.FAIL

    def test_consistency_rejects_one_lucky_window(self) -> None:
        """Der haeufigste Selbstbetrug: ein Quartal traegt alles."""
        report = make_report(trades=[make_trade("1", index=i) for i in range(150)],
                             sharpe=1.5, drawdown=8.0, profitable_windows=2,
                             total_windows=10)
        result = gate_consistency(report, GateThresholds())

        assert result.status is GateStatus.FAIL
        assert result.value == pytest.approx(0.2)

    def test_monte_carlo_detects_lucky_ordering(self) -> None:
        """Dieselben Trades in unguenstiger Reihenfolge ergeben mehr Drawdown.

        Hier: viele kleine Gewinne und wenige grosse Verluste. Fallen die
        Verluste zufaellig hintereinander, wird es deutlich schlimmer als im
        tatsaechlichen Verlauf.
        """
        trades = [make_trade("3", index=i) for i in range(40)]
        trades += [make_trade("-25", index=100 + i) for i in range(8)]

        result = gate_monte_carlo(trades, Decimal("500"), GateThresholds())
        assert result.status in {GateStatus.PASS, GateStatus.FAIL}
        assert result.value > 0, "Es muss ein Rueckgang gemessen werden"

    def test_monte_carlo_skips_tiny_samples(self) -> None:
        result = gate_monte_carlo(
            [make_trade("1", index=i) for i in range(5)], Decimal("500"), GateThresholds()
        )
        assert result.status is GateStatus.SKIP

    def test_regime_split_needs_enough_trades(self) -> None:
        frame = long_series(2000)
        result = gate_regime_split(
            [make_trade("1", index=i) for i in range(5)], frame, GateThresholds()
        )
        assert result.status is GateStatus.SKIP


class TestRegimeClassification:
    def test_regimes_are_backward_looking(self) -> None:
        """Die Einordnung darf nur Vergangenheitsdaten nutzen.

        Sonst waere die Regime-Aufteilung selbst eine Form von Lookahead - man
        wuerde Trades in ein Umfeld einsortieren, das erst spaeter erkennbar war.
        """
        frame = long_series(3000)
        cut = 2000

        corrupted = frame.copy()
        for column in ("open", "high", "low", "close"):
            corrupted.loc[cut:, column] = corrupted.loc[cut:, column] * 1.5

        original = classify_regimes(frame)["regime"].to_numpy()[:cut]
        perturbed = classify_regimes(corrupted)["regime"].to_numpy()[:cut]

        assert list(original) == list(perturbed)

    def test_uptrend_is_detected(self) -> None:
        candles = [
            Candle(
                open_time=T0 + Interval.M15.duration * i,
                open=Decimal(str(30000 + i * 20)),
                high=Decimal(str(30050 + i * 20)),
                low=Decimal(str(29950 + i * 20)),
                close=Decimal(str(30000 + i * 20)),
                volume=Decimal("10"),
                turnover=Decimal("1000000"),
            )
            for i in range(1000)
        ]
        regimes = classify_regimes(candles_to_frame(candles), window=480)
        assert (regimes["regime"].iloc[600:] == "aufwaerts").all()


class TestDeflatedSharpe:
    def test_more_trials_means_higher_hurdle(self) -> None:
        """Der Kern des Gates: Je mehr Versuche, desto weniger zaehlt ein
        guter Sharpe.

        Die Werte sind Sharpe **je Trade** - realistisch sind 0,05 bis 0,25.
        Ein Wert von 1,0 hiesse, der Durchschnittstrade liegt eine volle
        Standardabweichung im Plus; das gibt es nicht.
        """
        few = deflated_sharpe_ratio(observed_sharpe=0.15, trials=5, sample_size=200)
        many = deflated_sharpe_ratio(observed_sharpe=0.15, trials=1000, sample_size=200)

        assert few > many
        assert 0 <= many <= 1

    def test_larger_sample_increases_confidence(self) -> None:
        small = deflated_sharpe_ratio(observed_sharpe=0.15, trials=100, sample_size=50)
        large = deflated_sharpe_ratio(observed_sharpe=0.15, trials=100, sample_size=1000)

        assert large > small

    def test_negative_sharpe_is_worthless(self) -> None:
        assert deflated_sharpe_ratio(
            observed_sharpe=-0.5, trials=10, sample_size=200
        ) == 0.0

    def test_after_many_trials_mediocre_sharpe_fails(self) -> None:
        """Nach 500 getesteten Hypothesen reicht ein mittelmaessiger Vorteil nicht.

        Sharpe je Trade von 0,08 bei 150 Trades ist fuer sich genommen ein
        Ergebnis - nach 500 Versuchen ist es Rauschen. Genau dafuer zaehlt das
        Research-Journal jede Hypothese mit: der eingebaute Schutz davor, dass
        die KI sich durch schiere Menge einen Erfolg erschleicht.
        """
        alone = deflated_sharpe_ratio(observed_sharpe=0.08, trials=1, sample_size=150)
        after_many = deflated_sharpe_ratio(observed_sharpe=0.08, trials=500, sample_size=150)

        assert alone > after_many
        assert after_many < GateThresholds().min_deflated_sharpe


class TestParameterVariation:
    def test_neighbours_differ_from_original(self) -> None:
        genome = Genome(
            name="Basis",
            rationale="Ausgangsgenom fuer die Nachbarschaftssuche.",
            entry_long=[Condition(left=ind("ema", period=20), op=Operator.CROSS_ABOVE,
                                  right=ind("ema", period=60))],
            stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        neighbours = list(_vary_periods(genome, 0.2))

        assert len(neighbours) == 2  # einmal nach oben, einmal nach unten
        for neighbour in neighbours:
            assert neighbour.genome_id != genome.genome_id

    def test_neighbours_stay_within_bounds(self) -> None:
        """Perioden am Rand des erlaubten Bereichs duerfen nicht darueber hinaus."""
        genome = Genome(
            name="Randlage",
            rationale="Periode liegt am oberen Ende des erlaubten Bereichs.",
            entry_long=[Condition(left=price("close"), op=Operator.GT,
                                  right=ind("ema", period=400))],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        for neighbour in _vary_periods(genome, 0.2):
            for condition in neighbour.entry_long:
                if condition.right.kind == "indicator":
                    assert condition.right.params["period"] <= 400


# ---------------------------------------------------------------------------
#  Der entscheidende Test
# ---------------------------------------------------------------------------
class TestGateSystemRejectsOverfitting:
    def test_overfitted_genome_is_rejected(self, config: BacktestConfig) -> None:
        """Eine absichtlich ueberangepasste Strategie muss durchfallen.

        Konstruktion: extrem seltene, hochspezifische Bedingungen mit exotischen
        Perioden. So etwas erzeugt sehr wenige Trades und - falls es zufaellig
        gut aussieht - keinerlei Bestaendigkeit ueber die Fenster.

        Ein Gate-System, das nur bestaetigt was ohnehin gut ist, waere wertlos.
        Es muss beweisen, dass es ablehnt.
        """
        frame = long_series(50_000)
        overfitted = Genome(
            name="Ueberangepasst",
            rationale=(
                "Sehr enge, willkuerlich gewaehlte Schwellen mit exotischen "
                "Perioden - typisches Ergebnis einer Rasteroptimierung."
            ),
            filters=[
                Condition(left=ind("adx", period=17), op=Operator.GT,
                          right=Operand(kind="constant", value=41.3)),
                Condition(left=ind("rsi", period=23), op=Operator.LT,
                          right=Operand(kind="constant", value=31.7)),
                Condition(left=ind("volume_zscore", period=37), op=Operator.GT,
                          right=Operand(kind="constant", value=2.4)),
            ],
            entry_long=[
                Condition(left=ind("ema", period=13), op=Operator.CROSS_ABOVE,
                          right=ind("ema", period=47))
            ],
            stop=StopSpec(kind="atr", atr_period=19, multiple=2.3),
            targets=[TargetSpec(rr=3.7, portion=1.0)],
        )

        report = run_walkforward(
            frame,
            lambda: compile_genome(overfitted),
            config,
            WalkForwardSplitter(train_months=6, test_months=3),
        )
        gates = evaluate_gates(
            overfitted, report, frame, config, trials_so_far=200, run_expensive=False
        )

        assert not gates.passed, (
            "Die ueberangepasste Strategie hat alle Gates bestanden - "
            "dann pruefen die Gates nichts."
        )
        assert gates.failures
        assert gates.feedback_for_ai()

    def test_feedback_names_values_and_thresholds(self) -> None:
        """Die Rueckmeldung an die KI muss Zahlen enthalten.

        Ohne konkrete Werte kann die KI nicht gezielt nachbessern und probiert
        nur blind weiter - das ist der Unterschied zwischen Lernen und Raten.
        """
        report = make_report(
            trades=[make_trade("1", index=i) for i in range(10)],
            sharpe=0.2, drawdown=25.0, profitable_windows=1, total_windows=10,
        )
        gates = evaluate_gates(
            Genome(
                name="Schwach",
                rationale="Bewusst schwache Strategie fuer den Rueckmeldungstest.",
                entry_long=[Condition(left=price("close"), op=Operator.GT,
                                      right=ind("ema", period=20))],
                targets=[TargetSpec(rr=2.0, portion=1.0)],
            ),
            report,
            pd.DataFrame({"open_time": [], "close": []}),
            BacktestConfig(
                instrument=None, risk=RiskSettings(), initial_equity=Decimal("500")  # type: ignore[arg-type]
            ),
            trials_so_far=50,
            run_expensive=False,
        )
        feedback = gates.feedback_for_ai()

        assert "Schwelle" in feedback
        assert not gates.passed


class TestWindowChaining:
    """Wie die Fenster zu einer Kapitalkurve verkettet werden.

    Der Fehler, der im ersten echten Zulassungslauf einen Drawdown von 1005 %
    erzeugt hat: Die absoluten Fensterergebnisse wurden addiert. Jedes Fenster
    startet im Backtest aber mit dem vollen Anfangskapital und bemisst seine
    Positionen daran - wer die Ergebnisse aneinanderhaengt, addiert Verluste,
    die sich auf jeweils 500 EUR bezogen, auch wenn das verkettete Konto
    laengst leer waere.
    """

    def test_losing_windows_cannot_exceed_total_loss(self) -> None:
        """Zwanzig Fenster mit je -50 % ergeben -100 %, nicht -1000 %."""
        from backtest.walkforward import _combine

        initial = Decimal("500")
        windows = [_halving_window(index) for index in range(20)]

        combined = _combine(windows, initial)

        assert combined.max_drawdown_pct <= 100.0

    def test_gains_compound(self) -> None:
        """Die Gegenprobe: Zwei Fenster mit je +50 % ergeben +125 %, nicht +100 %."""
        from backtest.walkforward import _combine

        windows = [_doubling_window(0, factor=1.5), _doubling_window(1, factor=1.5)]

        combined = _combine(windows, Decimal("500"))

        assert combined.total_return_pct == pytest.approx(125.0, abs=1.0)


def _window_curve(index: int, end_factor: float) -> pd.DataFrame:
    start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=index * 30)
    times = pd.date_range(start, periods=30, freq="D")
    equity = np.linspace(500.0, 500.0 * end_factor, 30)
    return pd.DataFrame({"time": times, "equity": equity})


def _fake_window(index: int, end_factor: float):
    from types import SimpleNamespace

    start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=index * 30)
    curve = _window_curve(index, end_factor)
    return SimpleNamespace(
        window=SimpleNamespace(test_start=start),
        trades=[],
        result=SimpleNamespace(equity_curve=curve),
    )


def _halving_window(index: int):
    return _fake_window(index, 0.5)


def _doubling_window(index: int, *, factor: float):
    return _fake_window(index, factor)
