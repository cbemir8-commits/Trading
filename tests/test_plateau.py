"""Ein Plateau ist man in jeder Richtung oder gar nicht.

Das Gate hatte bis hierher **zwei** Nachbarn: alles um 20 % langsamer, alles um
20 % schneller. Das ist eine Gerade durch den Parameterraum, und auf einer
Geraden mit zwei Punkten laesst sich kein Plateau von einer Nadelspitze
unterscheiden. Der Anteil konnte nur 0, 0,5 oder 1 sein - bei einer Schwelle
von 0,6 hiess das in Wahrheit: *beide* muessen halten.

Schlimmer noch: Die eigene Begruendung des Gates - "EMA(47) gewinnt, EMA(46)
und EMA(48) verlieren" - beschreibt eine Nadel in **einer** Dimension. Genau
die konnte der Zwei-Punkte-Test nie sehen, weil er immer alle Perioden zugleich
verschob.

Zwei Dinge muessen dabei zusammenpassen, und beide stehen hier als Test:

* ``TestNachbarschaft`` - der Bereich wird groesser, ohne unzulaessige Nachbarn
  zu erzeugen. Derselbe Operand wandert ueberall gleich; verschiedene Operanden
  duerfen einzeln wandern.
* ``TestSchwaechsteRichtung`` - gewertet wird das Minimum ueber die
  Stellgroessen, nicht der Durchschnitt. Ein Durchschnitt ueber viele
  wirkungslose Regler laesst jede Nadel wie ein Plateau aussehen, **und** er
  waere die Sorte Aenderung, die ein Gate stillschweigend lockert.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.costs import CostModel, FundingSchedule
from backtest.engine import BacktestConfig
from core.config import RiskSettings
from core.models import Instrument
from research.gates import (
    GateStatus,
    GateThresholds,
    gate_parameter_plateau,
    nachbarschaft,
    skaliere_perioden,
    stellgroessen,
)
from research.seeds import spitzenkandidat
from strategy.genome import Condition, Genome, Operand, Operator, StopSpec, TargetSpec

T0 = datetime(2019, 1, 1, tzinfo=UTC)


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


def kurs(*, laenge: int, staerke: float, seed: int = 4, tage: int = 1100) -> pd.DataFrame:
    """Ein Kurs mit **Taktung** - und darauf kommt hier alles an.

    Ein reiner Zufallspfad ist fuer diese Frage unbrauchbar: Auf ihm gewinnen
    entweder alle Nachbarn oder keiner, und dann unterscheidet keine Wertung
    etwas von einer anderen. Erst ein Kurs, der in einem festen Takt dreht,
    macht **einzelne** Perioden wichtig und andere gleichgueltig - genau die
    Lage, fuer die das Gate gebaut ist.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(tage)
    drift = staerke * np.sin(2 * np.pi * t / laenge) + 0.0006
    close = 30000 * np.exp(np.cumsum(drift + rng.normal(0, 0.012, tage)))
    high = close * (1 + np.abs(rng.normal(0, 0.003, tage)))
    low = close * (1 - np.abs(rng.normal(0, 0.003, tage)))
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


def verdikte(genome, frame: pd.DataFrame, config: BacktestConfig) -> dict[str, list[bool]]:
    """Je Stellgroesse: Welche ihrer Richtungen bleiben profitabel?"""
    from collections import defaultdict

    from backtest.engine import Backtester
    from strategy.compiler import compile_genome

    je_richtung: dict[str, list[bool]] = defaultdict(list)
    for s, n in nachbarschaft(genome, 0.2):
        gewinn = Backtester(config).run(frame, compile_genome(n)).net_profit
        je_richtung[s.name].append(gewinn > 0)
    return dict(je_richtung)


# ---------------------------------------------------------------------------
#  Der Bereich
# ---------------------------------------------------------------------------
class TestNachbarschaft:
    def test_die_stellgroesse_ist_der_operand_nicht_die_zahl(self) -> None:
        """``sma(50)`` kommt beim Spitzenkandidaten dreimal vor - im Einstieg,
        im Ausstieg und in der Konfluenz - und ist trotzdem **eine**
        Stellgroesse."""
        namen = [s.name for s in stellgroessen(spitzenkandidat())]

        assert namen.count("sma(period=50)") == 1
        assert "sma(period=200)" in namen
        assert "Vola-Fenster" in namen

    def test_derselbe_operand_wandert_ueberall_gleich(self) -> None:
        """**Die Bedingung, ohne die der groessere Bereich unzulaessig waere.**

        Ein Nachbar mit Einstieg bei SMA(40) und Ausstieg weiterhin bei SMA(50)
        ist keine verschobene Regel, sondern eine widerspruechliche - und
        niemand wuerde sie handeln.
        """
        genome = spitzenkandidat()

        for _, nachbar in nachbarschaft(genome, 0.2):
            einstieg = [
                w for b in nachbar.entry_long for s in (b.left, b.right)
                if s.kind == "indicator" for w in s.params.values()
            ]
            ausstieg = [
                w for b in nachbar.exit_long for s in (b.left, b.right)
                if s.kind == "indicator" for w in s.params.values()
            ]

            assert einstieg == ausstieg

    def test_jede_stellgroesse_bekommt_beide_richtungen(self) -> None:
        genome = spitzenkandidat()
        gezaehlt: dict[str, int] = {}
        for s, _ in nachbarschaft(genome, 0.2):
            gezaehlt[s.name] = gezaehlt.get(s.name, 0) + 1

        assert set(gezaehlt) == {s.name for s in stellgroessen(genome)} | {
            "alle gemeinsam"
        }
        assert all(anzahl == 2 for anzahl in gezaehlt.values()), gezaehlt

    def test_die_gemeinsame_verschiebung_bleibt_dabei(self) -> None:
        """Der alte Zwei-Punkte-Test ist nicht ersetzt, sondern eine
        Stellgroesse unter mehreren - und genau deshalb kann das Gate durch
        den groesseren Bereich nirgends milder werden."""
        genome = spitzenkandidat()
        gemeinsam = {
            n.genome_id for s, n in nachbarschaft(genome, 0.2)
            if s.kennung == "*"
        }

        assert skaliere_perioden(genome, 0.8).genome_id in gemeinsam
        assert skaliere_perioden(genome, 1.2).genome_id in gemeinsam

    def test_keine_doppelten_nachbarn(self) -> None:
        """Ein doppelt gerechneter Nachbar kostet Rechenzeit und verschiebt
        das Minimum nicht - aber den Gesamtzaehler in der Meldung schon."""
        alle = [n.genome_id for _, n in nachbarschaft(spitzenkandidat(), 0.2)]

        assert len(alle) == len(set(alle))

    def test_selbst_ein_genom_ohne_indikatoren_hat_eine_stellgroesse(self) -> None:
        """Das Vola-Fenster ist immer da - ``sizing`` ist Pflicht und
        ``vol_period`` hat einen Standardwert.

        Wichtig fuer die Auslegung der SKIP-Meldung im Gate: Sie ist mit
        keinem gueltigen Genom erreichbar. Wer sie loescht, weil "das kommt
        eh nie vor", verlaesst sich darauf, dass ``vol_period`` nie optional
        wird.
        """
        genome = Genome(
            name="Ohne Indikatoren",
            rationale="Nur Preisvergleiche, kein einziger Indikator.",
            entry_long=[
                Condition(left=price("close"), op=Operator.GT, right=price("open"))
            ],
            exit_long=[
                Condition(left=price("close"), op=Operator.LT, right=price("open"))
            ],
            stop=StopSpec(kind="percent", percent=2.0),
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )

        assert [s.name for s in stellgroessen(genome)] == ["Vola-Fenster"]
        assert len(list(nachbarschaft(genome, 0.2))) == 2


# ---------------------------------------------------------------------------
#  Die Wertung
# ---------------------------------------------------------------------------
class TestSchwaechsteRichtung:
    """Ein Kurs mit 180-Tage-Takt - und der Spitzenkandidat darauf.

    Gemessen, nicht ausgedacht:

        alle gemeinsam   1/2      sma(200)       2/2
        sma(50)          0/2      roc(90)        2/2
        rsi(14)          2/2      Vola-Fenster   2/2

    Vier Perioden bewirken hier nichts, eine entscheidet alles. Der
    Durchschnitt sagt 0,75 und liesse das Gate bestehen. Die schwaechste
    Richtung sagt 0,00 - und trifft zu: Die Strategie haengt an der 50 und
    kippt in **beide** Richtungen davon weg.
    """

    def test_wirkungslose_regler_koennen_die_wertung_nicht_heben(
        self, config: BacktestConfig
    ) -> None:
        """**Der Kern der Sache.**

        Wuerde ueber alle Nachbarn gemittelt, koennten vier gleichgueltige
        Regler die eine Dimension niederstimmen, an der die Strategie
        tatsaechlich haengt - und das Gate wuerde milder, je mehr wirkungslose
        Regler ein Genom hat. Der Test rechnet beide Wertungen aus und
        verlangt, dass der Durchschnitt hier freundlicher waere. Sonst pruefte
        er nichts.
        """
        frame = kurs(laenge=180, staerke=0.0025)
        genome = spitzenkandidat()
        je_richtung = verdikte(genome, frame, config)

        durchschnitt = sum(sum(v) for v in je_richtung.values()) / sum(
            len(v) for v in je_richtung.values()
        )
        minimum = min(sum(v) / len(v) for v in je_richtung.values())

        assert minimum < durchschnitt, (
            "Auf diesen Daten wirken alle Regler gleich - dann unterscheidet "
            "der Test die beiden Wertungen nicht."
        )
        assert durchschnitt >= GateThresholds().min_plateau_ratio, (
            "Der Durchschnitt muss hier bestehen, sonst zeigt der Test nicht, "
            "was an ihm falsch ist."
        )

        ergebnis = gate_parameter_plateau(genome, frame, config, GateThresholds())

        assert ergebnis.value == pytest.approx(minimum)
        assert ergebnis.status is GateStatus.FAIL

    def test_die_wertung_liegt_nie_ueber_dem_alten_zwei_punkte_wert(
        self, config: BacktestConfig
    ) -> None:
        """**Die Eigenschaft, die diese Aenderung von einer Lockerung trennt.**

        Die gemeinsame Verschiebung - der komplette alte Test - ist eine der
        Stellgroessen. Ein Minimum ueber eine Menge, die sie enthaelt, kann
        nicht groesser sein als sie. Das Gate kann durch den groesseren
        Bereich also nirgends milder werden, nur strenger.
        """
        genome = spitzenkandidat()

        for laenge, staerke in ((180, 0.0025), (180, 0.004), (130, 0.0025)):
            frame = kurs(laenge=laenge, staerke=staerke)
            je_richtung = verdikte(genome, frame, config)
            alt = sum(je_richtung["alle gemeinsam"]) / len(
                je_richtung["alle gemeinsam"]
            )
            neu = gate_parameter_plateau(genome, frame, config, GateThresholds()).value

            assert neu <= alt, f"Takt {laenge}, Staerke {staerke}"

    def test_und_manchmal_ist_sie_deutlich_strenger(
        self, config: BacktestConfig
    ) -> None:
        """Der Gegenbeweis zur Lockerungs-Sorge, an einem Fall gemessen.

        Bei 180 Tagen Takt und doppelter Staerke besteht die gemeinsame
        Verschiebung **beide** Richtungen - der alte Zwei-Punkte-Test haette
        das Gate durchgewinkt. Vier von fuenf Einzelreglern verlieren dort
        trotzdem in beide Richtungen.
        """
        frame = kurs(laenge=180, staerke=0.004)
        genome = spitzenkandidat()
        je_richtung = verdikte(genome, frame, config)

        alt = sum(je_richtung["alle gemeinsam"]) / 2
        ergebnis = gate_parameter_plateau(genome, frame, config, GateThresholds())

        assert alt >= GateThresholds().min_plateau_ratio, "alt haette bestanden"
        assert ergebnis.status is GateStatus.FAIL, "neu nicht"

    def test_ohne_nachbarn_wird_uebersprungen_statt_abgelehnt(
        self, config: BacktestConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keine Nachbarschaft ist keine Nadelspitze - es ist keine Aussage.

        Mit einem gueltigen Genom ist der Fall nicht herstellbar (das
        Vola-Fenster ist immer da), deshalb hier ueber den Umweg. Der Zweig
        bleibt, weil ``vol_period`` optional werden koennte.
        """
        from research import gates

        monkeypatch.setattr(gates, "nachbarschaft", lambda genome, variation: iter(()))

        ergebnis = gate_parameter_plateau(
            spitzenkandidat(), kurs(laenge=180, staerke=0.0025), config,
            GateThresholds(),
        )

        assert ergebnis.status is GateStatus.SKIP

    def test_die_meldung_nennt_jede_richtung_einzeln(
        self, config: BacktestConfig
    ) -> None:
        """Ein Gate, das nur "0,00" sagt, laesst offen, **welche** Periode die
        Strategie traegt. Genau das ist die Auskunft, die man braucht - und
        beim Spitzenkandidaten war sie der ganze Ertrag dieser Uebung."""
        ergebnis = gate_parameter_plateau(
            spitzenkandidat(), kurs(laenge=180, staerke=0.0025), config,
            GateThresholds(),
        )

        for s in stellgroessen(spitzenkandidat()):
            assert s.name in ergebnis.message
        assert "alle gemeinsam" in ergebnis.message
        assert "sma(period=50)" in ergebnis.message.split(" traegt nur ")[0]
