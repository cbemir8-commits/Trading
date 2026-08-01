"""Tests der drei Antworten auf "eine Strategie funktioniert nicht ewig".

* **Verfall** - merken, dass der Vorteil weg ist, bevor der Drawdown es sagt.
* **Marktphasen** - nicht eine flexible Strategie, sondern Spezialisten und
  ein Einordner.
* **Ausstiege** - das Chance-Risiko-Verhaeltnis aus MAE/MFE verbessern statt
  aus dem Bauch.

Der wichtigste Test in dieser Datei ist ``test_says_unknown_when_it_cannot
_know``: Ein Verfallsdetektor, der nach zehn Trades ein Urteil faellt, wechselt
die Strategie bei jedem normalen Verlustlauf. Das ist schlimmer als keiner.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from core.models import Side, Trade
from research.decay import (
    MIN_TRADES_FOR_JUDGEMENT,
    Health,
    assess_decay,
    detectable_drop,
    r_multiples,
)
from research.exits import analyse_exits
from research.regime import (
    Regime,
    RegimePerformance,
    build_roster,
    classify,
    performance_by_regime,
)

RISK_PER_TRADE = Decimal("10")  # 0.001 BTC x 10000 Punkte Stopabstand


def make_trade(
    *,
    r: float,
    index: int = 0,
    mae_r: float = 0.3,
    mfe_r: float = 1.2,
    entry_time: datetime | None = None,
) -> Trade:
    """Ein Trade mit vorgegebenem Ergebnis in R.

    Der Stopabstand ist so gewaehlt, dass 1 R genau 10 Einheiten Gewinn
    entspricht - damit laesst sich jede Erwartung von Hand nachrechnen.
    """
    entry = Decimal("100000")
    stop = Decimal("90000")  # 10000 Punkte
    qty = Decimal("0.001")  # -> Risiko 10
    return Trade(
        trade_id=f"t{index}",
        symbol="BTCUSDT",
        side=Side.BUY,
        strategy_id="test",
        entry_time=entry_time or datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index),
        entry_price=entry,
        exit_time=(entry_time or datetime(2026, 1, 1, tzinfo=UTC)) + timedelta(hours=index + 1),
        exit_price=entry + Decimal(str(r * 10000)),
        qty=qty,
        gross_pnl=RISK_PER_TRADE * Decimal(str(r)),
        fees=Decimal(0),
        stop_loss=stop,
        max_adverse_excursion=RISK_PER_TRADE * Decimal(str(mae_r)),
        max_favourable_excursion=RISK_PER_TRADE * Decimal(str(mfe_r)),
    )


def series(values: list[float], **kwargs) -> list[Trade]:
    return [make_trade(r=v, index=i, **kwargs) for i, v in enumerate(values)]


def r_values(*, mean: float, deviation: float, count: int) -> list[float]:
    """Werte mit **exakt** diesem Mittelwert und dieser Streuung.

    Bewusst kein Zufall: Ein Test, dessen Ergebnis am Startwert des
    Zufallsgenerators haengt, prueft den Generator und nicht den Detektor -
    und faellt irgendwann bei einer harmlosen Aenderung um.
    """
    raw = np.random.default_rng(0).normal(0, 1, count)
    normalised = (raw - raw.mean()) / raw.std(ddof=1)
    return list(normalised * deviation + mean)


# ---------------------------------------------------------------------------
#  Verfallserkennung
# ---------------------------------------------------------------------------
class TestDecay:
    def test_r_multiples_are_independent_of_position_size(self) -> None:
        """Der ganze Sinn von R: Backtest mit 500 EUR und Livebetrieb mit
        2.000 EUR muessen dieselbe Zahl ergeben."""
        small = make_trade(r=2.0)
        big = small.model_copy(
            update={
                "qty": Decimal("0.004"),
                "gross_pnl": Decimal("80"),  # 4x Menge, 4x Gewinn
            }
        )

        assert r_multiples([small]) == pytest.approx([2.0])
        assert r_multiples([big]) == pytest.approx([2.0])

    def test_says_unknown_when_it_cannot_know(self) -> None:
        """Der wichtigste Test hier.

        Mit zehn Trades ist die Streuung groesser als jeder Effekt, den man
        messen wollte. Ein Detektor, der trotzdem urteilt, wechselt die
        Strategie bei jedem normalen Verlustlauf - und Wechseln ist selbst
        eine Form von Ueberanpassung, nur langsamer.
        """
        catastrophic = series([-1.0] * 10)

        report = assess_decay(catastrophic, expected_r=0.15)

        assert report.health is Health.UNKNOWN
        assert not report.should_retire
        assert str(MIN_TRADES_FOR_JUDGEMENT) in report.detail

    def test_healthy_when_live_matches_backtest(self) -> None:
        # Genau die versprochene Erwartung, realistische Streuung
        values = r_values(mean=0.15, deviation=1.0, count=60)

        report = assess_decay(series(values), expected_r=0.15)

        assert report.health is Health.HEALTHY
        assert not report.should_retire

    def test_degraded_when_clearly_worse(self) -> None:
        """Deutlich schlechter als versprochen, und statistisch belegt."""
        values = r_values(mean=-0.35, deviation=0.8, count=120)

        report = assess_decay(series(values), expected_r=0.20)

        assert report.should_retire
        assert report.z_score < -1.645

    def test_dead_when_expectancy_turned_negative(self) -> None:
        values = r_values(mean=-0.30, deviation=0.6, count=150)

        report = assess_decay(series(values), expected_r=0.15)

        assert report.health is Health.DEAD

    def test_watch_is_not_a_retirement(self) -> None:
        """Etwas schlechter, aber nicht belegt - das ist eine Beobachtung,
        keine Entscheidung. Wer hier absetzt, tauscht Strategien im Rauschen."""
        values = r_values(mean=0.05, deviation=1.0, count=40)

        report = assess_decay(series(values), expected_r=0.15)

        assert report.health is Health.WATCH
        assert not report.should_retire
        assert report.trades_needed > report.trades

    def test_reports_how_many_trades_would_be_needed(self) -> None:
        """"Noch nicht signifikant" heisst nicht "unauffaellig" - es kann auch
        heissen, dass man schlicht noch nicht genug gesehen hat. Der
        Unterschied gehoert benannt."""
        values = r_values(mean=0.10, deviation=1.0, count=40)

        report = assess_decay(series(values), expected_r=0.15)

        # Abstand 0,05 R bei Streuung 1,0 - dafuer braeuchte es ueber 1000
        # Trades. Bei 30 Trades im Monat sind das knapp drei Jahre.
        assert report.health is Health.WATCH
        assert report.trades_needed > 1000

    def test_detectable_drop_is_honest_about_small_samples(self) -> None:
        """Die ernuechternde Gegenrechnung: Bei 30 Trades und typischer
        Streuung bliebe selbst ein vollstaendiger Verlust des Vorteils
        unentdeckt."""
        with_30 = detectable_drop(trades=30, deviation=1.0, expected_r=0.15)
        with_300 = detectable_drop(trades=300, deviation=1.0, expected_r=0.15)

        assert with_30 == pytest.approx(1.0)  # nichts erkennbar
        assert with_300 < 0.7  # ab hier wird es aussagekraeftig
        assert with_300 < with_30


# ---------------------------------------------------------------------------
#  Marktphasen
# ---------------------------------------------------------------------------
def make_frame(*, bars: int, pattern: str) -> pd.DataFrame:
    rng = np.random.default_rng(4)
    if pattern == "trend":
        close = 30000 * np.exp(np.cumsum(np.full(bars, 0.0004) + rng.normal(0, 0.0008, bars)))
    else:  # seitwaerts
        close = 30000 + np.cumsum(rng.normal(0, 20, bars))
        close = 30000 + (close - close.mean()) * 0.3
    return pd.DataFrame(
        {
            "open_time": pd.date_range(datetime(2024, 1, 1, tzinfo=UTC), periods=bars, freq="15min"),
            "open": close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "volume": np.full(bars, 10.0),
            "turnover": np.full(bars, 1e6),
        }
    )


class TestRegimeClassification:
    def test_trend_is_recognised(self) -> None:
        frame = make_frame(bars=3000, pattern="trend")

        labels = classify(frame).dropna()

        trending = sum(1 for v in labels if Regime(v).is_trending)
        assert trending / len(labels) > 0.7

    def test_range_is_recognised(self) -> None:
        frame = make_frame(bars=3000, pattern="range")

        labels = classify(frame).dropna()

        ranging = sum(1 for v in labels if not Regime(v).is_trending)
        assert ranging / len(labels) > 0.7

    def test_no_label_before_warmup(self) -> None:
        """Eine geratene Phase ist schlimmer als gar keine."""
        frame = make_frame(bars=2000, pattern="trend")

        labels = classify(frame)

        assert labels.iloc[:480].isna().all()

    def test_classification_is_causal(self) -> None:
        """Der schwerwiegendste denkbare Fehler an dieser Stelle.

        Wird die Einordnung auf einer laengeren Reihe anders, als sie es auf
        dem gemeinsamen Anfangsstueck war, dann fliesst spaeteres Wissen in
        frueheres Urteil ein. Eine Phaseneinteilung, die die Zukunft kennt,
        faellt in keinem gewoehnlichen Backtest auf - und macht jedes Ergebnis
        wertlos.
        """
        full = make_frame(bars=4000, pattern="trend")
        prefix = full.iloc[:2500].reset_index(drop=True)

        labels_full = classify(full).iloc[:2500].reset_index(drop=True)
        labels_prefix = classify(prefix)

        pd.testing.assert_series_equal(labels_full, labels_prefix, check_names=False)


class TestRoster:
    def test_specialists_get_their_regime(self) -> None:
        """Der Kern der Idee: nicht eine Strategie fuer alles, sondern je
        Phase die, die dort nachweislich funktioniert."""
        performances = {
            "trendfolger": {
                Regime.TREND_CALM: RegimePerformance(Regime.TREND_CALM, 50, 0.25, 0.45, 12.5),
                Regime.RANGE_CALM: RegimePerformance(Regime.RANGE_CALM, 40, -0.10, 0.30, -4.0),
            },
            "mean_reverter": {
                Regime.TREND_CALM: RegimePerformance(Regime.TREND_CALM, 30, -0.05, 0.40, -1.5),
                Regime.RANGE_CALM: RegimePerformance(Regime.RANGE_CALM, 60, 0.18, 0.62, 10.8),
            },
        }

        roster = build_roster(performances)

        assert roster.responsible_for(Regime.TREND_CALM) == "trendfolger"
        assert roster.responsible_for(Regime.RANGE_CALM) == "mean_reverter"

    def test_regime_without_a_competent_strategy_stays_empty(self) -> None:
        """Nichtstun ist eine zulaessige Antwort.

        Die teuersten Trades sind die, die man macht, weil man etwas machen
        wollte. Ist fuer eine Phase niemand zustaendig, wird dort nicht
        gehandelt - das ist ein Ergebnis, kein Ausfall.
        """
        performances = {
            "irgendwer": {
                Regime.RANGE_WILD: RegimePerformance(Regime.RANGE_WILD, 80, -0.22, 0.31, -17.6),
            }
        }

        roster = build_roster(performances)

        assert roster.responsible_for(Regime.RANGE_WILD) is None
        assert Regime.RANGE_WILD in roster.uncovered
        assert "nicht gehandelt" in roster.describe()

    def test_lucky_streak_does_not_make_a_specialist(self) -> None:
        """Drei zufaellig gute Trades sind kein Nachweis von Zustaendigkeit."""
        performances = {
            "glueckspilz": {
                Regime.TREND_WILD: RegimePerformance(Regime.TREND_WILD, 3, 1.80, 1.0, 5.4),
            }
        }

        assert build_roster(performances).responsible_for(Regime.TREND_WILD) is None

    def test_performance_uses_the_regime_at_entry(self) -> None:
        """Die Phase beim Ausstieg zu nehmen waere Lookahead durch die
        Hintertuer - beim Einstieg wusste niemand, wie es weitergeht."""
        frame = make_frame(bars=3000, pattern="trend")
        entry = frame["open_time"].iloc[2000].to_pydatetime()
        trades = [make_trade(r=1.0, entry_time=entry)]

        result = performance_by_regime(trades, frame)

        assert sum(p.trades for p in result.values()) == 1


# ---------------------------------------------------------------------------
#  Ausstiege / Chance-Risiko-Verhaeltnis
# ---------------------------------------------------------------------------
class TestExitAnalysis:
    def test_no_advice_from_too_few_trades(self) -> None:
        """Eine MAE-Verteilung aus zwoelf Trades ist eine Anekdote."""
        analysis = analyse_exits(series([1.0] * 12))

        assert "Anekdote" in analysis.suggestions[0]

    def test_detects_a_stop_that_is_too_wide(self) -> None:
        """Der haeufigste stille Verlust: Gewinner laufen kaum gegen uns, der
        Stop sitzt aber weit weg - jeder Verlierer kostet dadurch mehr, ohne
        dass ein einziger Gewinner davon profitiert."""
        trades = series([2.0] * 30, mae_r=0.2, mfe_r=2.5) + series([-1.0] * 20, mae_r=1.0)

        analysis = analyse_exits(trades)

        assert any("Stop zu weit" in s for s in analysis.suggestions)
        assert analysis.mae_p90_r < 0.5

    def test_detects_a_stop_that_is_too_tight(self) -> None:
        """Der umgekehrte Fall: Schon der durchschnittliche Gewinner lief weit
        gegen uns - viele gute Trades duerften knapp ausgestoppt worden sein."""
        trades = series([1.5] * 40, mae_r=0.9, mfe_r=2.0)

        analysis = analyse_exits(trades)

        assert any("knapp bemessen" in s for s in analysis.suggestions)

    def test_detects_money_left_on_the_table(self) -> None:
        trades = series([0.5] * 50, mae_r=0.3, mfe_r=4.0)

        analysis = analyse_exits(trades)

        assert analysis.captured_share < 0.35
        assert any("zu nah" in s for s in analysis.suggestions)

    def test_detects_targets_that_are_never_reached(self) -> None:
        trades = series([0.4] * 50, mae_r=0.4, mfe_r=0.9)

        analysis = analyse_exits(trades)

        assert any("Ziele zu weit" in s for s in analysis.suggestions)

    def test_says_so_when_there_is_nothing_to_improve(self) -> None:
        """Kein Vorschlag ist auch ein Ergebnis - und ehrlicher, als um jeden
        Preis eine Stellschraube zu finden."""
        # Gegenlauf breit um 0,55 gestreut (weder eng noch weit), und die
        # Gewinner liefen kaum weiter als ihr Ergebnis - da ist nichts zu holen.
        spread = r_values(mean=0.55, deviation=0.18, count=60)
        results = r_values(mean=0.35, deviation=1.1, count=60)
        trades = [
            make_trade(
                r=result,
                index=i,
                mae_r=max(0.05, spread[i]),
                mfe_r=max(result, 0.0) + 0.3,
            )
            for i, result in enumerate(results)
        ]

        analysis = analyse_exits(trades)

        assert any("kein klarer Spielraum" in s for s in analysis.suggestions)

    def test_trades_without_a_stop_are_ignored(self) -> None:
        """Ohne Stop gibt es kein R - so ein Trade sagt hier nichts aus und
        darf die Verteilung nicht verschieben."""
        good = series([1.0] * 45)
        without_stop = [good[0].model_copy(update={"stop_loss": None})]

        analysis = analyse_exits(good + without_stop)

        assert analysis.trades == 45


class TestBenchmark:
    """Kaufen und Halten als Messlatte.

    Die Frage ist nicht "verdient die Strategie Geld", sondern "schlaegt sie
    einfaches Halten". Ueber 2020-2026 hat BTC sich vervielfacht; eine
    Strategie mit 30 % Rendite in diesem Zeitraum ist ein Verlustgeschaeft.
    Diese Zahl fehlte in den ersten beiden Zulassungslaeufen.
    """

    def test_hold_return_matches_the_price_move(self) -> None:
        from research.benchmark import buy_and_hold

        frame = _rising_frame(factor=3.0)

        bench = buy_and_hold(frame)

        # Dreifacher Kurs = rund +200 %, abzueglich der einmaligen Kaufgebuehr.
        assert 195 < bench.return_pct < 200

    def test_entry_fee_is_charged_once(self) -> None:
        """Sonst waere die Messlatte guenstiger als die Wirklichkeit - und
        jede Strategie ihr sicher unterlegen."""
        from research.benchmark import buy_and_hold

        bench = buy_and_hold(_rising_frame(factor=1.0))

        assert bench.return_pct < 0  # nur die Gebuehr, kein Kursgewinn
        assert bench.return_pct > -0.2

    def test_verdict_names_the_quiet_win(self) -> None:
        """Weniger Rendite bei deutlich weniger Rueckgang ist fuer ein Konto
        mit 15 %-Kill-Switch der bessere Handel - das muss die Bewertung
        auch so sagen."""
        from types import SimpleNamespace

        from research.benchmark import buy_and_hold

        # Eine Reihe mit echtem Einbruch - sonst hat die Messlatte gar keinen
        # Rueckgang, und "ruhiger als nichts" ist keine sinnvolle Aussage.
        bench = buy_and_hold(_frame_with_crash())
        quieter = SimpleNamespace(
            total_return_pct=bench.return_pct * 0.7,
            max_drawdown_pct=bench.max_drawdown_pct / 3,
        )

        assert "ruhiger" in bench.verdict_for(quieter)

    def test_verdict_is_blunt_about_losing_to_nothing(self) -> None:
        from types import SimpleNamespace

        from research.benchmark import buy_and_hold

        bench = buy_and_hold(_rising_frame(factor=3.0))
        worse = SimpleNamespace(total_return_pct=-20.0, max_drawdown_pct=90.0)

        assert "Nichtstun" in bench.verdict_for(worse)


class TestExitConditions:
    """Ausstieg ueber eine Bedingung statt ueber eine Preismarke.

    Ohne das gibt es keine Strategie, die *wann investiert sein* steuert statt
    *wann handeln* - und genau diese Bauform handelt selten genug, dass die
    Gebuehren nicht mehr entscheiden.
    """

    def test_genome_without_exit_conditions_is_unchanged(self) -> None:
        from research.seeds import ema_cross
        from strategy.compiler import compile_genome

        genome = ema_cross()

        assert genome.exit_long == []
        assert compile_genome(genome).warmup_bars > 0

    def test_exit_indicators_are_precomputed(self) -> None:
        """Wer die Ausstiegsbedingungen beim Vorberechnen vergisst, stolpert
        erst zur Laufzeit darueber - mitten im Backtest."""
        from research.seeds import trend_exposure

        genome = trend_exposure()
        keys = genome.required_operands()

        for condition in genome.exit_long:
            for operand in (condition.left, condition.right):
                if operand.kind != "constant":
                    assert operand.key in keys

    def test_generation_3_all_have_an_exit(self) -> None:
        from research.seeds import load_seeds

        for genome in load_seeds(generation=3):
            assert genome.exit_long, genome.name


def _frame_with_crash() -> pd.DataFrame:
    """Steigt, bricht um die Haelfte ein, erholt sich - wie 2021/22."""
    up = np.linspace(30000.0, 60000.0, 200)
    down = np.linspace(60000.0, 30000.0, 100)
    recover = np.linspace(30000.0, 70000.0, 200)
    close = np.concatenate([up, down, recover])
    return pd.DataFrame(
        {
            "open_time": pd.date_range(
                datetime(2024, 1, 1, tzinfo=UTC), periods=len(close), freq="4h"
            ),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": np.ones(len(close)),
            "turnover": np.ones(len(close)),
        }
    )


def _rising_frame(*, factor: float) -> pd.DataFrame:
    n = 500
    close = np.linspace(30000.0, 30000.0 * factor, n)
    return pd.DataFrame(
        {
            "open_time": pd.date_range(
                datetime(2024, 1, 1, tzinfo=UTC), periods=n, freq="4h"
            ),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": np.ones(n),
            "turnover": np.ones(n),
        }
    )
