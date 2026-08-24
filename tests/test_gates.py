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
    gate_benchmark,
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
        # Jedes Fenster bekommt seinen Trade. Fenster ohne Handel zaehlen bei
        # der Bestaendigkeit nicht mit - eine leere Liste wuerde hier also
        # etwas anderes pruefen, als der Test zu pruefen vorgibt.
        report.windows.append(
            WindowResult(  # type: ignore[arg-type]
                window=None,
                metrics=window_metrics,
                trades=[make_trade(str(pnl), index=i)],
                result=None,
            )
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

        # **Jede Stellgroesse einzeln, dazu beide gemeinsamen Verschiebungen.**
        #
        # Hier standen lange zwei Nachbarn - alles langsamer, alles schneller.
        # Das ist eine Gerade durch den Parameterraum, und auf einer Geraden
        # mit zwei Punkten laesst sich kein Plateau von einer Nadelspitze
        # unterscheiden. Vier Stellgroessen (ema 20, ema 60, Stop-ATR,
        # Vola-Fenster) mal zwei Richtungen, plus die gemeinsame Verschiebung.
        from research.gates import stellgroessen

        assert len(stellgroessen(genome)) == 4
        assert len(neighbours) == 10
        for neighbour in neighbours:
            assert neighbour.genome_id != genome.genome_id
        assert len({n.genome_id for n in neighbours}) == len(neighbours)

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


class TestNachbarnSindEchteNachbarn:
    """Ein Nachbar muss dieselbe Strategie mit anderen Zahlen sein.

    Hier wurden lange nur ``entry_long``, ``entry_short`` und ``filters``
    variiert. Beim Spitzenkandidaten - Einstieg ueber dem 50-Tage-Schnitt,
    Ausstieg darunter - erzeugte das einen "Nachbarn" mit Einstieg bei
    SMA(40) und Ausstieg weiterhin bei SMA(50): eine Regel, die sich selbst
    widerspricht und die niemand handeln wuerde.

    Das Gate soll pruefen, ob die Strategie auf einem Plateau steht. Dafuer
    muss der Nachbar die Strategie sein.
    """

    def _kandidat(self):
        from research.seeds import spitzenkandidat

        return spitzenkandidat()

    def _perioden(self, genome, abschnitt: str) -> list[int]:
        return [
            wert
            for bedingung in getattr(genome, abschnitt)
            for seite in (bedingung.left, bedingung.right)
            if seite.kind == "indicator"
            for wert in seite.params.values()
        ]

    def test_ausstieg_wird_mitverschoben(self) -> None:
        genome = self._kandidat()

        for nachbar in _vary_periods(genome, 0.2):
            assert self._perioden(nachbar, "entry_long") == self._perioden(
                nachbar, "exit_long"
            ), (
                "Einstieg und Ausstieg haben dieselbe Periode - ein Nachbar, "
                "der nur eine von beiden verschiebt, ist keine Nachbarschaft"
            )

    def test_konfluenz_wird_mitverschoben(self) -> None:
        """Sie bestimmt die Positionsgroesse und blieb bisher ungeprueft.

        Seit die Nachbarschaft jede Stellgroesse einzeln verschiebt, laesst
        **jeder einzelne** Nachbar den groesseren Teil des Genoms in Ruhe -
        das ist der Zweck. Gefordert ist deshalb nicht mehr, dass jeder
        Nachbar die Konfluenz bewegt, sondern dass die Nachbarschaft sie
        ueberhaupt erreicht.
        """
        genome = self._kandidat()
        vorher = self._perioden(genome, "konfluenz")
        assert vorher, "Der Kandidat muss Konfluenzbedingungen haben"

        beruehrt = [
            n for n in _vary_periods(genome, 0.2)
            if self._perioden(n, "konfluenz") != vorher
        ]

        assert len(beruehrt) >= len(vorher), (
            "Jede Konfluenz-Periode braucht mindestens einen eigenen Nachbarn"
        )

    def test_das_vola_fenster_wird_mitverschoben(self) -> None:
        genome = self._kandidat()

        beruehrt = [
            n for n in _vary_periods(genome, 0.2)
            if n.sizing.vol_period != genome.sizing.vol_period
        ]

        assert len(beruehrt) >= 2, "nach oben und nach unten"

    def test_gleiche_operanden_wandern_gemeinsam(self) -> None:
        """**Die Bedingung, die die Nachbarschaft ueberhaupt zulaessig macht.**

        Frueher hiess die Regel "alle Perioden bewegen sich zugleich". Das war
        strenger als noetig und machte das Gate blind fuer die Nadel in einer
        einzelnen Dimension - dabei ist genau die sein Namensgeber.

        Noetig ist nur: **Derselbe** Operand muss ueberall gleich wandern. Der
        Spitzenkandidat steigt ueber ``sma(50)`` ein und darunter aus; ein
        Nachbar mit Einstieg bei 40 und Ausstieg bei 50 waere keine
        verschobene Regel, sondern eine widerspruechliche.
        """
        genome = self._kandidat()

        for nachbar in _vary_periods(genome, 0.2):
            assert self._perioden(nachbar, "entry_long") == self._perioden(
                nachbar, "exit_long"
            )
            # Und der Einstiegswert kommt auch in der Konfluenz vor:
            assert (
                self._perioden(nachbar, "entry_long")[0]
                in self._perioden(nachbar, "konfluenz")
            )

    def test_verschiedene_operanden_duerfen_einzeln_wandern(self) -> None:
        """Die Gegenprobe. ``sma(50) > sma(200)`` mit 160 statt 200 ist ein
        voellig normaler Trendfilter - und die Frage, ob die 200 eine
        Zauberzahl ist, laesst sich anders gar nicht stellen."""
        genome = self._kandidat()

        nur_die_200 = [
            n for n in _vary_periods(genome, 0.2)
            if self._perioden(n, "entry_long") == self._perioden(genome, "entry_long")
            and self._perioden(n, "konfluenz") != self._perioden(genome, "konfluenz")
        ]

        assert nur_die_200, (
            "Kein Nachbar verschiebt eine Konfluenz-Periode allein - dann "
            "misst das Gate wieder nur eine Gerade durch den Parameterraum"
        )

    def test_grenzen_kommen_aus_dem_genom(self) -> None:
        """Nicht danebengeschrieben - sonst laufen sie auseinander."""
        from research.gates import _feldgrenzen
        from strategy.genome import SizingSpec

        feld = SizingSpec.model_fields["vol_period"]
        unten, oben = _feldgrenzen(feld, standard=(0, 0))

        assert (unten, oben) == (5, 200)
        # Und die Schranken werden auch eingehalten:
        genome = self._kandidat().model_copy(
            update={"sizing": self._kandidat().sizing.model_copy(
                update={"vol_period": 200}
            )}
        )
        for nachbar in _vary_periods(genome, 0.2):
            assert 5 <= nachbar.sizing.vol_period <= 200


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


def test_monte_carlo_drawdown_cannot_exceed_total_loss() -> None:
    """Auch die Simulation kennt keine Verluste ueber 100 %.

    Dieselbe Grenze wie bei der echten Kapitalkurve: Ein aufgebrauchtes Konto
    handelt die restlichen Trades nicht mehr mit. Ohne sie meldete das Gate
    bei einer durchweg verlierenden Strategie 1021 % - eine Zahl, die neben
    korrekten Werten steht und diese mit entwertet.
    """
    from research.gates import gate_monte_carlo

    losers = [make_trade("-40", index=i, hours_offset=i * 4) for i in range(60)]

    result = gate_monte_carlo(losers, Decimal("500"), GateThresholds())

    assert result.value <= 100.0
    assert not result.passed  # inhaltlich unveraendert: faellt trotzdem durch


def _fenster_ergebnis(frame: pd.DataFrame, spanne):
    """Ein WindowResult, das nur sein Zeitfenster tragen muss.

    gate_benchmark liest daraus ausschliesslich Start und Ende - alles
    andere kommt aus report.combined.
    """
    from backtest.walkforward import Window

    start, ende = spanne
    fenster = Window(
        index=0, train_start=start, train_end=start, test_start=start, test_end=ende
    )
    kurve = pd.DataFrame({"time": [start, ende], "equity": [500.0, 550.0]})
    return WindowResult(  # type: ignore[arg-type]
        window=fenster,
        metrics=compute_metrics([], kurve, initial_equity=Decimal("500")),
        trades=[],
        result=None,
    )


def _metrics_mit(*, rendite_pct: float, rueckgang_pct: float, cagr_pct: float):
    """Kennzahlen mit vorgegebener Rendite - fuer Gate-Tests.

    Der Weg ueber ``replace`` statt ueber einen erfundenen Kursverlauf: Wer
    die Zahlen aus einer Kurve erzeugt, prueft am Ende die Kurve.
    """
    kurve = pd.DataFrame({"time": [T0, T0 + timedelta(days=100)], "equity": [500.0, 600.0]})
    basis = compute_metrics([], kurve, initial_equity=Decimal("500"))
    return replace(
        basis,
        total_return_pct=rendite_pct,
        max_drawdown_pct=rueckgang_pct,
        cagr_pct=cagr_pct,
    )


class TestMesslatteSimuliert:
    """Die Messlatte wird nachsimuliert statt linear skaliert.

    **Diese Korrektur senkt die Huerde** - sie ist damit genau die Art
    Aenderung, bei der man sich selbst am leichtesten betruegt. Deshalb steht
    hier nicht nur, dass sie richtig ist, sondern auch der Nachweis, dass sie
    kein Freifahrtschein wurde.

    Der Fehler: ``benchmark_at_equal_risk`` skaliert die Rendite linear mit
    dem Rueckgang. Renditen verzinsen sich aber. Wer 7,4 % seines Geldes in
    BTC haelt, waehrend BTC sich verzehnfacht, bekommt +34 % - nicht 7,4 %
    von +1086 %. Ueber 2018 bis 2026 verlangte die Formel das gut Dreifache
    dessen, was anteiliges Halten tatsaechlich gebracht haette.
    """

    def _steigende_reihe(self, tage: int = 1200, drift: float = 0.003) -> pd.DataFrame:
        """Markt, der sich vervielfacht - mit einem echten Einbruch dazwischen.

        Ohne Rueckgang greift die Skalierung gar nicht: ``scaled_hold`` gibt
        dann volles Halten zurueck, weil nichts heruntergefahren werden muss.
        Genau daran ist dieser Test zuerst gescheitert.
        """
        schritte = np.full(tage, drift)
        schritte[tage // 3 : tage // 3 + 60] = -0.02   # 60 Tage Absturz
        preise = 10_000 * np.cumprod(1.0 + schritte)
        kerzen = [
            Candle(
                open_time=T0 + Interval.D1.duration * i,
                open=Decimal(f"{p:.2f}"),
                high=Decimal(f"{p * 1.01:.2f}"),
                low=Decimal(f"{p * 0.99:.2f}"),
                close=Decimal(f"{p:.2f}"),
                volume=Decimal("10"),
                turnover=Decimal("100000"),
            )
            for i, p in enumerate(preise)
        ]
        return candles_to_frame(kerzen)

    def _fenster(self, frame: pd.DataFrame):
        return [
            (
                frame["open_time"].iloc[0].to_pydatetime(),
                frame["open_time"].iloc[-1].to_pydatetime(),
            )
        ]

    def test_anteiliges_halten_verzinst_sich_nicht_linear(self) -> None:
        """Der Kern des Fehlers, an einem Markt ohne Rueckgang."""
        from research.benchmark import buy_and_hold_over_windows, scaled_hold

        frame = self._steigende_reihe()
        fenster = self._fenster(frame)
        voll, voll_dd = buy_and_hold_over_windows(frame, fenster)

        halb, _ = scaled_hold(frame, fenster, max(voll_dd, 1.0) / 2)

        # Bei einem Markt, der sich vervielfacht, ist die halbe Beteiligung
        # deutlich weniger als die halbe Rendite - Wurzel statt Haelfte.
        assert halb < voll / 2, (
            f"anteiliges Halten muss unterproportional sein: {halb} gegen {voll}"
        )

    def test_die_alte_formel_lag_zu_hoch(self) -> None:
        """Der Nachweis, dass die Korrektur eine Korrektur ist."""
        from research.benchmark import (
            benchmark_at_equal_risk,
            buy_and_hold_over_windows,
            scaled_hold,
        )

        frame = self._steigende_reihe()
        fenster = self._fenster(frame)
        voll, voll_dd = buy_and_hold_over_windows(frame, fenster)
        ziel = max(voll_dd, 1.0) / 4

        echt, _ = scaled_hold(frame, fenster, ziel)
        formel = benchmark_at_equal_risk(voll, voll_dd, ziel)

        assert formel > echt, (
            "die lineare Formel muss ueber dem liegen, was wirklich "
            "erreichbar war - sonst war sie gar nicht der Fehler"
        )

    def test_eine_schlechte_strategie_faellt_weiterhin_durch(self) -> None:
        """Der wichtigste Test hier.

        Wenn die korrigierte Messlatte alles durchwinkt, ist sie kein Gate
        mehr, sondern Dekoration. Eine Strategie, die deutlich weniger
        verdient als anteiliges Halten, muss scheitern.
        """
        from research.benchmark import scaled_hold

        frame = self._steigende_reihe()
        fenster = self._fenster(frame)
        messlatte, _ = scaled_hold(frame, fenster, 10.0)

        report = WalkForwardReport()
        report.windows = [_fenster_ergebnis(frame, fenster[0])]
        report.combined = _metrics_mit(
            rendite_pct=messlatte * 0.3, rueckgang_pct=10.0, cagr_pct=2.0
        )

        ergebnis = gate_benchmark(report, frame, GateThresholds())

        assert ergebnis.status is GateStatus.FAIL

    def test_eine_klar_bessere_strategie_besteht(self) -> None:
        from research.benchmark import scaled_hold

        frame = self._steigende_reihe()
        fenster = self._fenster(frame)
        messlatte, _ = scaled_hold(frame, fenster, 10.0)

        report = WalkForwardReport()
        report.windows = [_fenster_ergebnis(frame, fenster[0])]
        report.combined = _metrics_mit(
            rendite_pct=messlatte * 3.0 + 50.0, rueckgang_pct=10.0, cagr_pct=25.0
        )

        ergebnis = gate_benchmark(report, frame, GateThresholds())

        assert ergebnis.status is GateStatus.PASS


class TestFeldgrenzen:
    def test_gebrochene_schranken_bleiben_gebrochen(self) -> None:
        """**Hier stand ``int(wert)``.**

        Die einzigen Nutzer waren Indikatorperioden, und dort faellt es nicht
        auf. Beim ersten Feld mit einer gebrochenen Schranke - ``TargetSpec.rr``
        mit ``ge=0.3`` - waeren daraus stillschweigend 0 geworden, und die
        Mutation haette Ziele erzeugt, die das Schema anschliessend ablehnt.
        """
        from research.gates import _feldgrenzen
        from strategy.genome import TargetSpec

        unten, oben = _feldgrenzen(TargetSpec.model_fields["rr"], standard=(0.0, 1.0))

        assert unten == pytest.approx(0.3)
        assert oben > 20.0

    def test_ganze_schranken_bleiben_ganz(self) -> None:
        from research.gates import _feldgrenzen
        from strategy.genome import SizingSpec

        assert _feldgrenzen(
            SizingSpec.model_fields["vol_period"], standard=(0, 0)
        ) == (5, 200)

    def test_ohne_schranken_gilt_der_standard(self) -> None:
        from dataclasses import dataclass

        from research.gates import _feldgrenzen

        @dataclass
        class Ohne:
            metadata: tuple = ()

        assert _feldgrenzen(Ohne(), standard=(1.5, 9.5)) == (1.5, 9.5)


class TestQuartalsbloecke:
    """Die dritte Einteilung des Deflated-Sharpe-Gates - Befund 135.

    Gemessen am Spitzenkandidaten (Spot, 198 Versuche, 152 Trades) zeigt die
    Quartalseinteilung einen ICC von 0,257 bei p = 0,0050 - nachgewiesene
    Abhaengigkeit, wo die Walk-Forward-Fenster bei p = 0,0750 stehen. Die
    effektive Stichprobe faellt dadurch von 152 auf 112, der Deflated Sharpe
    von 0,8640 auf 0,6026.
    """

    def _trade(self, jahr, monat, pnl):
        from datetime import UTC, datetime
        from decimal import Decimal

        from core.models import Trade

        zeit = datetime(jahr, monat, 15, tzinfo=UTC)
        return Trade(
            trade_id=f"t{jahr}{monat}", symbol="BTCUSDT", side="Buy",
            strategy_id="x", entry_time=zeit, entry_price=Decimal("100"),
            exit_time=zeit, exit_price=Decimal("101"), qty=Decimal("1"),
            gross_pnl=Decimal(str(pnl)), fees=Decimal("0"),
            funding=Decimal("0"), stop_loss=Decimal("90"),
            exit_reason="signal_exit",
        )

    def test_buendelt_nach_kalenderquartal(self):
        from research.gates import quartalsbloecke

        trades = [
            self._trade(2020, 1, 1), self._trade(2020, 3, 2),
            self._trade(2020, 4, 3),
            self._trade(2020, 12, 4), self._trade(2021, 1, 5),
        ]
        assert quartalsbloecke(trades) == [[1.0, 2.0], [3.0], [4.0], [5.0]]

    def test_reihenfolge_ist_zeitlich(self):
        from research.gates import quartalsbloecke

        trades = [self._trade(2021, 5, 9), self._trade(2020, 2, 1)]
        assert quartalsbloecke(trades) == [[1.0], [9.0]]

    def test_ohne_trades_keine_bloecke(self):
        from research.gates import quartalsbloecke

        assert quartalsbloecke([]) == []

    def test_deckt_alle_trades_ab(self):
        """Eine Einteilung, die Trades verliert, misst etwas anderes."""
        from research.gates import quartalsbloecke

        trades = [self._trade(2020, m, m) for m in range(1, 13)]
        bloecke = quartalsbloecke(trades)
        assert sum(len(b) for b in bloecke) == len(trades)
        assert len(bloecke) == 4

    def test_das_gate_nimmt_die_quartale_mit(self):
        """Die Einteilung muss im Gate ankommen, nicht nur existieren."""
        import inspect

        from research import gates

        quelle = inspect.getsource(gates.gate_deflated_sharpe)
        assert "quartalsbloecke(trades)" in quelle
        assert "weitere=[gleichzeitig, quartalsbloecke(trades)]" in quelle
