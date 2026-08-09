"""Gesucht wird auf der Aufstellung, auf der geurteilt wird.

Der Wettbewerb suchte auf **einem** Markt, waehrend jede Zulassungszahl des
Projekts aus dem Portfolio BTC + ETH stammt. Derselbe Spitzenkandidat kommt

    auf BTC allein        5 von 11, Deflated Sharpe 0,190
    auf BTC + ETH         7 von 11, Deflated Sharpe 0,843

Wer auf dem einen Berg sucht und auf dem anderen prueft, optimiert am Ziel
vorbei - und merkt es nie, weil beide Zahlen fuer sich stimmen.

Dieselbe Verwechslung sass eine Ebene tiefer noch einmal: Neun der elf Gates
lesen nur den Walk-Forward und sahen das Portfolio damit automatisch. Die
beiden teuren rechnen selbst nach - und rechneten weiter auf dem
Referenzmarkt allein. Deshalb steht hier zu jedem der drei Punkte ein Test:

* ``TestKostenStress``   summiert ueber die Beine, statt eines auszuwaehlen
* ``TestPlateau``        urteilt ueber das Portfolio, nicht je Bein
* ``TestZulassung``      prueft, was gehandelt wird, nicht einen Teil davon
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.costs import CostModel, FundingSchedule
from backtest.engine import BacktestConfig, Backtester
from backtest.walkforward import WalkForwardSplitter
from core.config import RiskSettings
from core.models import Instrument
from research.admission import run_admission
from research.gates import (
    GateStatus,
    GateThresholds,
    _vary_periods,
    evaluate_gates,
    gate_cost_stress,
    gate_parameter_plateau,
)
from research.seeds import trend_following
from strategy.compiler import compile_genome

from .factories import make_instrument

T0 = datetime(2019, 1, 1, tzinfo=UTC)


def kurs(
    *, drift: float, vola: float, seed: int, tage: int = 1000, docht: float = 0.003
) -> pd.DataFrame:
    """Ein Kursverlauf mit vorgegebenem Trend.

    Kein Realismus-Anspruch - gebraucht wird nur ein Bein, auf dem die Regel
    verdient, und eines, auf dem sie verliert. Genau daran entscheidet sich,
    ob ein Gate ueber das Portfolio urteilt oder ueber einen Teil davon.
    """
    rng = np.random.default_rng(seed)
    close = 30000 * np.exp(np.cumsum(rng.normal(drift, vola, tage)))
    high = close * (1 + np.abs(rng.normal(0, docht, tage)))
    low = close * (1 - np.abs(rng.normal(0, docht, tage)))
    return pd.DataFrame(
        {
            "open_time": pd.date_range(T0, periods=tage, freq="D"),
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": np.maximum(high, close),
            "low": np.minimum(low, close),
            "close": close,
            "volume": rng.lognormal(2, 0.5, tage),
            "turnover": rng.lognormal(12, 0.5, tage),
        }
    )


@pytest.fixture
def config(btcusdt: Instrument, risk: RiskSettings) -> BacktestConfig:
    return BacktestConfig(
        instrument=btcusdt,
        risk=risk,
        costs=CostModel(),
        funding=FundingSchedule(default_rate=Decimal(0)),
        initial_equity=Decimal("500"),
    )


@pytest.fixture
def stark() -> pd.DataFrame:
    """Ein Bein, auf dem die Trendfolge verdient."""
    return kurs(drift=0.003, vola=0.010, seed=5)


@pytest.fixture
def schwach() -> pd.DataFrame:
    """Ein Bein, auf dem sie verliert - und das allein durchfallen wuerde."""
    return kurs(drift=-0.0004, vola=0.025, seed=11, docht=0.004)


# ---------------------------------------------------------------------------
#  Kosten-Stress
# ---------------------------------------------------------------------------
class TestKostenStress:
    def test_summiert_ueber_die_beine(
        self, stark: pd.DataFrame, schwach: pd.DataFrame, config: BacktestConfig
    ) -> None:
        """**Ein Bein, das allein durchfaellt, kippt kein Portfolio, das traegt.**

        Gehandelt wird die Summe. Wuerde das Gate stattdessen jedes Bein
        einzeln verlangen, waere es strenger als die Wirklichkeit - und wuerde
        Kandidaten ablehnen, die als Ganzes nie ein Problem hatten.
        """
        genome = trend_following()
        t = GateThresholds()

        allein_stark = gate_cost_stress(genome, stark, config, t)
        allein_schwach = gate_cost_stress(genome, schwach, config, t)
        portfolio = gate_cost_stress(
            genome, stark, config, t,
            frames={"stark": stark, "schwach": schwach},
            configs={"stark": config, "schwach": config},
        )

        # Sonst prueft der Test nichts: Beide Beine muessen sich unterscheiden.
        assert allein_stark.status is GateStatus.PASS
        assert allein_schwach.status is GateStatus.FAIL

        assert portfolio.status is GateStatus.PASS
        assert portfolio.value == pytest.approx(
            allein_stark.value + allein_schwach.value
        )

    def test_meldung_zeigt_die_einzelnen_beine(
        self, stark: pd.DataFrame, schwach: pd.DataFrame, config: BacktestConfig
    ) -> None:
        """Eine Summe allein verbirgt, dass ein Bein zuschiesst und eines
        zehrt. Wer das nicht sieht, haelt ein Portfolio fuer robust, das an
        einem einzigen Markt haengt."""
        ergebnis = gate_cost_stress(
            trend_following(), stark, config, GateThresholds(),
            frames={"stark": stark, "schwach": schwach},
            configs={"stark": config, "schwach": config},
        )

        assert ergebnis.message.count("+") + ergebnis.message.count("-") >= 2

    def test_ohne_beine_bleibt_es_beim_einen_markt(
        self, stark: pd.DataFrame, config: BacktestConfig
    ) -> None:
        """Der alte Weg muss unveraendert bleiben - ``cli research`` und die
        Einzelmarkt-Zulassung haengen daran."""
        ohne = gate_cost_stress(trend_following(), stark, config, GateThresholds())
        leer = gate_cost_stress(
            trend_following(), stark, config, GateThresholds(), frames=None
        )

        assert ohne.value == leer.value


# ---------------------------------------------------------------------------
#  Parameter-Plateau
# ---------------------------------------------------------------------------
class TestPlateau:
    def test_urteilt_ueber_das_portfolio_statt_je_bein(
        self, stark: pd.DataFrame, schwach: pd.DataFrame, config: BacktestConfig
    ) -> None:
        """**Ein Nachbar zaehlt, wenn das Ganze mit ihm verdient.**

        Die naheliegende Alternative - jedes Bein muss profitabel sein - ist
        eine andere Frage und gibt hier eine andere Antwort. Der Test rechnet
        beide aus und verlangt, dass sie sich unterscheiden; sonst wuerde er
        bestehen, ohne zwischen ihnen zu trennen.
        """
        genome = trend_following()
        beine = {"stark": stark, "schwach": schwach}
        configs = {"stark": config, "schwach": config}

        nachbarn = list(_vary_periods(genome, 0.2))
        gewinne = [
            [
                Backtester(configs[name]).run(f, compile_genome(n)).net_profit
                for name, f in beine.items()
            ]
            for n in nachbarn
        ]
        als_summe = sum(1 for g in gewinne if sum(g) > 0) / len(nachbarn)
        als_und = sum(1 for g in gewinne if all(x > 0 for x in g)) / len(nachbarn)

        assert als_summe != als_und, (
            "Auf diesen Daten fallen beide Lesarten zusammen - der Test "
            "unterscheidet dann nichts mehr."
        )

        ergebnis = gate_parameter_plateau(
            genome, stark, config, GateThresholds(), frames=beine, configs=configs
        )

        assert ergebnis.value == pytest.approx(als_summe)

    def test_ein_schwaches_bein_allein_faellt_durch(
        self, stark: pd.DataFrame, schwach: pd.DataFrame, config: BacktestConfig
    ) -> None:
        """Der Beleg, dass die Beine ueberhaupt ankommen: Auf dem schwachen
        Bein allein besteht dasselbe Genom das Gate nicht."""
        genome = trend_following()
        t = GateThresholds()

        allein = gate_parameter_plateau(genome, schwach, config, t)
        zusammen = gate_parameter_plateau(
            genome, stark, config, t,
            frames={"stark": stark, "schwach": schwach},
            configs={"stark": config, "schwach": config},
        )

        assert allein.status is GateStatus.FAIL
        assert zusammen.status is GateStatus.PASS


# ---------------------------------------------------------------------------
#  Die Durchreichung
# ---------------------------------------------------------------------------
class TestDurchreichung:
    def test_evaluate_gates_reicht_die_beine_an_die_teuren_gates(
        self, stark: pd.DataFrame, schwach: pd.DataFrame, config: BacktestConfig
    ) -> None:
        """**Der eigentliche Fehler sass hier.**

        Neun Gates lesen nur den Walk-Forward und sehen das Portfolio damit
        von selbst. Die beiden teuren rechnen nach - und rechneten auf dem
        Referenzmarkt allein weiter. Wer die Durchreichung wieder entfernt,
        bekommt hier den Wert des einzelnen Marktes zurueck.
        """
        from backtest.portfolio_walkforward import run_portfolio_walkforward

        genome = trend_following()
        beine = {"stark": stark, "schwach": schwach}
        configs = {"stark": config, "schwach": config}
        walk = run_portfolio_walkforward(
            beine, lambda: compile_genome(genome), configs, WalkForwardSplitter()
        )

        report = evaluate_gates(
            genome, walk, stark, config, trials_so_far=0,
            frames=beine, configs=configs,
        )

        gemessen = {r.name: r.value for r in report.results}
        einzeln = gate_cost_stress(genome, stark, config, GateThresholds())
        gesamt = gate_cost_stress(
            genome, stark, config, GateThresholds(),
            frames=beine, configs=configs,
        )

        assert gemessen["Kosten-Stress"] == pytest.approx(gesamt.value)
        assert gemessen["Kosten-Stress"] != pytest.approx(einzeln.value)

    def test_zulassung_prueft_das_portfolio_wenn_beine_gegeben_sind(
        self, config: BacktestConfig, risk: RiskSettings
    ) -> None:
        """Ohne ``frames`` misst die Zulassung einen Markt, mit ``frames`` das
        Portfolio - erkennbar daran, dass die Fenstergewinne je Bein
        mitkommen."""
        stark = kurs(drift=0.003, vola=0.010, seed=5, tage=700)
        schwach = kurs(drift=-0.0004, vola=0.025, seed=11, tage=700, docht=0.004)
        eth = BacktestConfig(
            instrument=make_instrument(symbol="ETHUSDT"),
            risk=risk,
            costs=CostModel(),
            funding=FundingSchedule(default_rate=Decimal(0)),
            initial_equity=Decimal("500"),
        )

        einzeln = run_admission(
            [trend_following()], stark, config,
            trials_so_far=0, run_expensive=False,
        )
        portfolio = run_admission(
            [trend_following()], stark, config,
            trials_so_far=0, run_expensive=False,
            frames={"stark": stark, "schwach": schwach},
            configs={"stark": config, "schwach": eth},
        )

        assert not einzeln.candidates[0].walkforward.beine
        assert set(portfolio.candidates[0].walkforward.beine) == {"stark", "schwach"}

    def test_der_wettbewerb_kann_die_beine_ueberhaupt_annehmen(self) -> None:
        """Der schmalste Test hier, und trotzdem noetig.

        Er beweist nichts ueber Zahlen - nur, dass der Weg von der
        Kommandozeile zur Portfolio-Pruefung offen ist. Faellt die Option weg,
        laeuft der Wettbewerb wieder auf einem Markt, ohne dass irgendetwas
        rot wird.
        """
        from typer.testing import CliRunner

        from cli import app

        hilfe = CliRunner().invoke(app, ["wettbewerb", "--help"]).output

        assert "--maerkte" in hilfe

    def test_der_versuchszaehler_laeuft_auch_im_portfolio_weiter(
        self, config: BacktestConfig
    ) -> None:
        """Ein Versuch auf zwei Beinen ist ein Versuch, kein halber - und die
        Mehrfachtest-Korrektur darf davon nichts verlieren."""
        stark = kurs(drift=0.003, vola=0.010, seed=5, tage=700)
        schwach = kurs(drift=-0.0004, vola=0.025, seed=11, tage=700, docht=0.004)

        report = run_admission(
            [trend_following()], stark, config,
            trials_so_far=118, run_expensive=False,
            frames={"stark": stark, "schwach": schwach},
            configs={"stark": config, "schwach": config},
        )

        assert report.trials_after == 119
