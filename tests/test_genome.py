"""Tests fuer Genome, Indikatoren und Compiler.

Der wichtigste Test der Datei ist ``test_all_indicators_are_causal``: Er prueft
jeden Eintrag der Whitelist automatisch darauf, dass er nicht in die Zukunft
schaut. Ein nicht-kausaler Indikator ist der einzige Lookahead-Weg, den weder
der BarContext noch der Perturbationstest im Nachhinein abfangen koennen -
er steckt dann bereits in den vorberechneten Daten.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from backtest.costs import CostModel, FundingSchedule
from backtest.engine import BacktestConfig, Backtester
from core.config import RiskSettings
from core.models import Instrument, Interval, Side
from data.store import candles_to_frame
from strategy import indicators
from strategy.compiler import compile_genome
from strategy.genome import (
    Condition,
    Genome,
    Operand,
    Operator,
    StopSpec,
    TargetSpec,
)

from tests.factories import make_candles


@pytest.fixture
def frame() -> pd.DataFrame:
    """Schwingende Reihe, damit Indikatoren echte Werte liefern."""
    import math

    from core.models import Candle

    candles = []
    from datetime import UTC, datetime

    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(500):
        base = 100_000 + 1200 * math.sin(i / 22) + 400 * math.sin(i / 6)
        close = base + 150 * math.sin(i / 2.7)
        candles.append(
            Candle(
                open_time=t0 + Interval.M15.duration * i,
                open=Decimal(f"{base:.1f}"),
                high=Decimal(f"{max(base, close) + 110:.1f}"),
                low=Decimal(f"{min(base, close) - 110:.1f}"),
                close=Decimal(f"{close:.1f}"),
                volume=Decimal(f"{10 + 5 * abs(math.sin(i / 4)):.3f}"),
                turnover=Decimal("1000000"),
            )
        )
    return candles_to_frame(candles)


def ind(name: str, **params: int) -> Operand:
    return Operand(kind="indicator", name=name, params=params)


def price(name: str) -> Operand:
    return Operand(kind="price", name=name)


def const(value: float) -> Operand:
    return Operand(kind="constant", value=value)


# ---------------------------------------------------------------------------
#  Kausalitaet - der wichtigste Test
# ---------------------------------------------------------------------------
class TestIndicatorCausality:
    @pytest.mark.parametrize("name", sorted(indicators.REGISTRY))
    def test_all_indicators_are_causal(self, name: str, frame: pd.DataFrame) -> None:
        """Kein Indikator darf auf zukuenftige Kerzen reagieren.

        Vorgehen: Alle Preise ab Kerze K verfaelschen und pruefen, dass die
        Indikatorwerte **vor** K unveraendert bleiben. Ein zentrierter
        Durchschnitt, ein ``shift(-1)`` oder ein ``bfill()`` faellt hier sofort
        auf.

        Automatisch ueber die gesamte Whitelist parametriert: Ein neu
        hinzugefuegter Indikator wird ohne Zutun mitgeprueft.
        """
        _, spec = indicators.REGISTRY[name]
        # Sinnvoller Wert innerhalb der Grenzen: 14, aber nie ueber dem Maximum
        # (Bollinger-'deviations' geht z.B. nur bis 4).
        params = {
            key: min(max(bounds[0], 14), bounds[1])
            for key, bounds in spec.param_bounds.items()
        }
        # MACD braucht fast < slow, sonst ist das Ergebnis unsinnig.
        if "fast" in params and "slow" in params:
            params["fast"], params["slow"] = 12, 26

        cut = 300
        corrupted = frame.copy()
        for column in ("open", "high", "low", "close", "volume"):
            corrupted.loc[cut:, column] = corrupted.loc[cut:, column] * 1.5

        original = indicators.compute(name, frame, params)
        perturbed = indicators.compute(name, corrupted, params)

        before_original = original[:cut]
        before_perturbed = perturbed[:cut]

        np.testing.assert_allclose(
            before_original,
            before_perturbed,
            equal_nan=True,
            err_msg=(
                f"Indikator '{name}' aendert sich vor Kerze {cut}, obwohl nur "
                f"Daten ab {cut} veraendert wurden - er ist nicht kausal."
            ),
        )

    def test_donchian_excludes_current_bar(self, frame: pd.DataFrame) -> None:
        """Der Kanal darf die aktuelle Kerze nicht enthalten.

        Sonst liegt er per Konstruktion immer mindestens auf dem aktuellen
        Hoch, ein Ausbruch darueber kann nie stattfinden - und die
        Ausbruchsstrategie handelt nie, ohne dass jemand merkt warum.
        """
        upper = indicators.donchian_upper(frame, period=20)
        highs = frame["high"].to_numpy(dtype=np.float64)

        breakouts = np.sum(highs[25:] > upper[25:])
        assert breakouts > 0, "Ohne Ausbrueche waere der Kanal falsch berechnet"

    def test_ema_uses_recursive_form(self, frame: pd.DataFrame) -> None:
        """``adjust=False`` - sonst haengt jeder Wert vom Beginn der Reihe ab.

        Mit ``adjust=True`` bekaeme der Livebetrieb, der irgendwann mittendrin
        startet, andere Werte als der Backtest.
        """
        full = indicators.ema(frame, period=20)
        # Ein spaeter Start muss praktisch denselben Wert liefern.
        tail = indicators.ema(frame.iloc[200:].reset_index(drop=True), period=20)

        assert abs(full[-1] - tail[-1]) < abs(full[-1]) * 1e-6

    def test_unknown_indicator_is_rejected(self, frame: pd.DataFrame) -> None:
        with pytest.raises(KeyError, match="Whitelist"):
            indicators.compute("magisches_orakel", frame, {})

    def test_out_of_bounds_parameter_is_rejected(self, frame: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="ausserhalb"):
            indicators.compute("ema", frame, {"period": 9999})

    def test_rsi_stays_in_range(self, frame: pd.DataFrame) -> None:
        values = indicators.rsi(frame, 14)
        finite = values[np.isfinite(values)]
        assert finite.min() >= 0
        assert finite.max() <= 100


# ---------------------------------------------------------------------------
#  Genom-Validierung
# ---------------------------------------------------------------------------
class TestGenomeValidation:
    def test_minimal_genome_is_valid(self) -> None:
        genome = Genome(
            name="EMA-Kreuzung",
            rationale="Schneller EMA kreuzt langsamen, klassischer Trendeinstieg.",
            entry_long=[Condition(left=ind("ema", period=10), op=Operator.CROSS_ABOVE,
                                  right=ind("ema", period=30))],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        assert genome.genome_id
        assert not genome.trades_both_directions

    def test_rejects_unknown_indicator(self) -> None:
        """Die KI kann keine Indikatoren erfinden - genau das ist der Sinn."""
        with pytest.raises(ValidationError, match="Whitelist"):
            Operand(kind="indicator", name="kristallkugel", params={"period": 10})

    def test_rejects_out_of_bounds_parameter(self) -> None:
        with pytest.raises(ValidationError, match="ausserhalb"):
            Operand(kind="indicator", name="ema", params={"period": 5000})

    def test_rejects_unknown_parameter(self) -> None:
        with pytest.raises(ValidationError, match="kennt keinen Parameter"):
            Operand(kind="indicator", name="ema", params={"laenge": 20})

    def test_rejects_extra_fields(self) -> None:
        """``extra='forbid'`` - ein Tippfehler der KI wird zum Fehler, nicht
        zu einem still ignorierten Feld."""
        with pytest.raises(ValidationError):
            TargetSpec(rr=2.0, portion=0.5, anteil=0.5)  # type: ignore[call-arg]

    def test_rejects_genome_without_entry(self) -> None:
        with pytest.raises(ValidationError, match="mindestens eine Einstiegsbedingung"):
            Genome(
                name="Leer",
                rationale="Diese Strategie hat keine Einstiegsbedingung.",
                targets=[TargetSpec(rr=2.0, portion=1.0)],
            )

    def test_rejects_oversized_target_portions(self) -> None:
        with pytest.raises(ValidationError, match="summieren sich"):
            Genome(
                name="Zuviel",
                rationale="Die Anteile summieren sich auf mehr als die Position.",
                entry_long=[Condition(left=price("close"), op=Operator.GT,
                                      right=ind("ema", period=20))],
                targets=[TargetSpec(rr=1.0, portion=0.7), TargetSpec(rr=2.0, portion=0.7)],
            )

    def test_rejects_unsorted_targets(self) -> None:
        """Ein naeheres Ziel hinter einem ferneren wuerde nie erreicht."""
        with pytest.raises(ValidationError, match="aufsteigen"):
            Genome(
                name="Verdreht",
                rationale="Die Ziele stehen in der falschen Reihenfolge.",
                entry_long=[Condition(left=price("close"), op=Operator.GT,
                                      right=ind("ema", period=20))],
                targets=[TargetSpec(rr=3.0, portion=0.5), TargetSpec(rr=1.0, portion=0.5)],
            )

    def test_rejects_constant_on_left_of_crossing(self) -> None:
        """Eine Konstante bewegt sich nicht, kann also nichts kreuzen."""
        with pytest.raises(ValidationError, match="bewegt sich nicht"):
            Condition(left=const(50), op=Operator.CROSS_ABOVE, right=ind("rsi", period=14))

    def test_constant_on_right_of_crossing_is_fine(self) -> None:
        """``rsi kreuzt hoch ueber 50`` ist sinnvoll und erlaubt."""
        condition = Condition(
            left=ind("rsi", period=14), op=Operator.CROSS_ABOVE, right=const(50)
        )
        assert "kreuzt hoch ueber 50" in condition.describe()


class TestGenomeIdentity:
    def test_id_ignores_name_and_rationale(self) -> None:
        """Zwei Genome mit identischen Regeln sind dieselbe Strategie.

        Ohne diese Unterscheidung koennte die KI dieselbe Idee beliebig oft neu
        'entdecken' und damit die Mehrfachtest-Korrektur unterlaufen - jede
        Wiederholung erhoeht die Chance auf ein zufaellig gutes Ergebnis.
        """
        rules = {
            "entry_long": [
                Condition(left=ind("ema", period=10), op=Operator.CROSS_ABOVE,
                          right=ind("ema", period=30))
            ],
            "targets": [TargetSpec(rr=2.0, portion=1.0)],
        }
        a = Genome(name="Version A", rationale="Erste Formulierung der Idee.", **rules)
        b = Genome(name="Voellig anders", rationale="Zweite Formulierung derselben Idee.",
                   **rules)

        assert a.genome_id == b.genome_id

    def test_id_changes_with_parameters(self) -> None:
        def build(period: int) -> Genome:
            return Genome(
                name="Test",
                rationale="Parameter variiert zwischen den Varianten.",
                entry_long=[Condition(left=ind("ema", period=period), op=Operator.GT,
                                      right=ind("ema", period=50))],
                targets=[TargetSpec(rr=2.0, portion=1.0)],
            )

        assert build(10).genome_id != build(11).genome_id


# ---------------------------------------------------------------------------
#  Compiler
# ---------------------------------------------------------------------------
class TestCompiler:
    def test_warmup_derives_from_longest_period(self) -> None:
        """Zu kurze Aufwaermphase laesst die Strategie auf nan entscheiden."""
        genome = Genome(
            name="Langsam",
            rationale="Nutzt einen sehr langen Durchschnitt als Trendfilter.",
            entry_long=[Condition(left=price("close"), op=Operator.GT,
                                  right=ind("ema", period=200))],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        assert compile_genome(genome).warmup_bars >= 600

    def test_shared_indicators_are_computed_once(self, frame: pd.DataFrame) -> None:
        """Zwei Bedingungen auf demselben EMA(50) teilen sich eine Reihe."""
        genome = Genome(
            name="Doppelt",
            rationale="Verwendet denselben Durchschnitt in zwei Bedingungen.",
            filters=[Condition(left=price("close"), op=Operator.GT,
                               right=ind("ema", period=50))],
            entry_long=[Condition(left=ind("ema", period=50), op=Operator.GT,
                                  right=ind("ema", period=200))],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        series = compile_genome(genome).prepare(frame)

        ema50_keys = [k for k in series if "ema(period=50)" in k]
        assert len(ema50_keys) == 1

    def test_atr_stop_produces_volatility_adjusted_distance(
        self, frame: pd.DataFrame
    ) -> None:
        """Ein ATR-Stop passt sich der Volatilitaet an - das ist sein Zweck."""
        genome = Genome(
            name="ATR-Stop",
            rationale="Stop richtet sich nach der aktuellen Schwankungsbreite.",
            entry_long=[Condition(left=price("close"), op=Operator.GT,
                                  right=ind("ema", period=20))],
            stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        strategy = compile_genome(genome)
        signals = _collect_signals(strategy, frame)

        assert signals, "Testszenario muss Signale erzeugen"
        distances = {s.stop_distance_pct for s in signals}
        assert len(distances) > 3, "ATR-Stop muss ueber die Zeit variieren"

    def test_percent_stop_is_constant(self, frame: pd.DataFrame) -> None:
        genome = Genome(
            name="Fester Stop",
            rationale="Fester prozentualer Stop, unabhaengig von der Volatilitaet.",
            entry_long=[Condition(left=price("close"), op=Operator.GT,
                                  right=ind("ema", period=20))],
            stop=StopSpec(kind="percent", percent=0.8),
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        signals = _collect_signals(compile_genome(genome), frame)

        assert signals
        for signal in signals:
            assert float(signal.stop_distance_pct) == pytest.approx(0.8, abs=0.001)

    def test_cooldown_suppresses_immediate_reentry(self, frame: pd.DataFrame) -> None:
        """Ohne Sperrfrist loest eine dauerhaft erfuellte Bedingung jede Kerze aus."""
        rules = {
            "entry_long": [
                Condition(left=price("close"), op=Operator.GT, right=ind("ema", period=20))
            ],
            "targets": [TargetSpec(rr=2.0, portion=1.0)],
        }
        without = _collect_signals(
            compile_genome(Genome(name="Ohne", rationale="Keine Sperrfrist gesetzt.",
                                  cooldown_bars=0, **rules)),
            frame,
        )
        with_cooldown = _collect_signals(
            compile_genome(Genome(name="Mit", rationale="Sperrfrist von 20 Kerzen.",
                                  cooldown_bars=20, **rules)),
            frame,
        )
        assert len(with_cooldown) < len(without) / 2

    def test_filters_gate_all_entries(self, frame: pd.DataFrame) -> None:
        """Ein unerfuellbarer Filter muss jeden Einstieg verhindern."""
        genome = Genome(
            name="Blockiert",
            rationale="Der Filter ist niemals erfuellbar, es darf nichts passieren.",
            filters=[Condition(left=ind("adx", period=14), op=Operator.GT,
                               right=const(999))],
            entry_long=[Condition(left=price("close"), op=Operator.GT,
                                  right=ind("ema", period=20))],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        assert _collect_signals(compile_genome(genome), frame) == []

    def test_compiled_strategy_runs_in_backtester(
        self, frame: pd.DataFrame, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        """Ende-zu-Ende: Genom -> Compiler -> Backtest."""
        genome = Genome(
            name="Trendfolge",
            rationale="Einstieg bei Kreuzung, Filter auf Trendstaerke via ADX.",
            filters=[Condition(left=ind("adx", period=14), op=Operator.GT, right=const(20))],
            entry_long=[Condition(left=ind("ema", period=10), op=Operator.CROSS_ABOVE,
                                  right=ind("ema", period=30))],
            entry_short=[Condition(left=ind("ema", period=10), op=Operator.CROSS_BELOW,
                                   right=ind("ema", period=30))],
            stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
            targets=[TargetSpec(rr=1.5, portion=0.5), TargetSpec(rr=3.0, portion=0.5)],
            cooldown_bars=5,
        )
        config = BacktestConfig(
            instrument=btcusdt,
            risk=risk,
            costs=CostModel(),
            funding=FundingSchedule(default_rate=Decimal(0)),
            initial_equity=Decimal("500"),
        )
        result = Backtester(config).run(frame, compile_genome(genome))

        assert result.signals_generated > 0
        assert genome.describe()  # Beschreibung muss lesbar erzeugbar sein

    def test_long_and_short_are_symmetric(self, frame: pd.DataFrame) -> None:
        genome = Genome(
            name="Beidseitig",
            rationale="Handelt in beide Richtungen, gespiegelte Bedingungen.",
            entry_long=[Condition(left=ind("rsi", period=14), op=Operator.CROSS_ABOVE,
                                  right=const(50))],
            entry_short=[Condition(left=ind("rsi", period=14), op=Operator.CROSS_BELOW,
                                   right=const(50))],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        signals = _collect_signals(compile_genome(genome), frame)
        sides = {s.side for s in signals}

        assert sides == {Side.BUY, Side.SELL}
        for signal in signals:
            if signal.side is Side.BUY:
                assert signal.stop_loss < signal.entry_price
            else:
                assert signal.stop_loss > signal.entry_price


def _collect_signals(strategy, frame: pd.DataFrame) -> list:  # noqa: ANN001
    """Laesst die Strategie ueber die Reihe laufen und sammelt alle Signale."""
    from strategy.base import BarContext, frame_to_arrays

    arrays = frame_to_arrays(frame)
    series = strategy.prepare(frame)
    signals = []
    for i in range(strategy.warmup_bars, len(frame)):
        signal = strategy.on_bar(BarContext(frame, arrays, series, i))
        if signal is not None:
            signals.append(signal)
    return signals
