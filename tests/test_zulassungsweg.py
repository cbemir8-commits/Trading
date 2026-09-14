"""Der Erfolgsweg der Zulassung, einmal durch die Maschine gefahren - Befund 284.

Seit Befund 102 sperrt ``GateReport.passed`` Forschungskerzen. Geprueft war
seither die **Sperre**: ``test_forschungskerzen_lassen_nicht_zu`` haelt fest,
dass elf von elf auf Bitstamp keine Zulassung sind. Die Gegenprobe
``test_boersendaten_lassen_zu`` baut ihren Bericht **von Hand**, und
``tests/test_uebergang.py`` verweist im Docstring ausdruecklich dorthin, statt
es selbst zu fahren.

Damit war die Strecke, auf der es darauf ankommt, nie gelaufen:

    Boersenkerzen -> Walk-Forward -> ``evaluate_gates`` -> ``referenzdaten``
    -> ``passed``

Zwischen dem Namen im Kerzenspeicher und dem Schalter im Bericht liegen zwei
Uebergaben - ``frames`` muss in den Aufruf, ``ist_referenz`` muss ueber die
Beine laufen. Beide sind richtig; keine davon hatte bisher eine Wache, die
anschlaegt, wenn jemand sie verliert. Genau so eine Uebergabe war Befund 265
(Funding unter dem falschen Schluessel gelesen, lautlos NaN) und genau so eine
war Befund 283.

Gefahren wird auf zwei synthetischen Zufallsreihen ueber 900 Tage - einmal
unter Boersennamen, einmal unter Forschungsnamen, sonst Zeichen fuer Zeichen
derselbe Lauf. Gemessen: 5 Fenster, 33 Trades, 4 von 11 Gates, in beiden
Faellen dieselben Werte.

**Was hier nicht behauptet wird:** dass eine Strategie besteht. Eine
Zufallsreihe besteht nicht und soll es nicht. Geprueft wird die Maschinerie:
dass die Herkunftsfelder aus dem Lauf kommen und dass sie das Urteil tragen.
Im letzten Test sind die Gate-Ergebnisse gesetzt und als gesetzt
gekennzeichnet - eine Zulassung auf einer erfundenen Strategie waere genau
das, wogegen diese Datei steht.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from research.gates import GateReport, GateResult, GateStatus

TAGE = 900
"""Kurz genug fuer die Suite, lang genug fuer einen echten Walk-Forward.

Gemessen: 900 Tage geben 5 Fenster und 33 Trades in rund 7 Sekunden, 1400
Tage geben 11 Fenster und 78 Trades in rund 16. Der Schalter faellt in beiden
Faellen gleich; bezahlt wird die laengere Reihe allein mit Laufzeit.
"""

BOERSE = ("BTCUSDT", "ETHUSDT")
FORSCHUNG = ("BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP")


def _reihe(n: int, saat: int) -> pd.DataFrame:
    """Ein reiner Zufallslauf - kein Vorteil, und keiner vorgetaeuscht."""
    rng = np.random.default_rng(saat)
    kurs = 100 * np.exp(np.cumsum(rng.normal(0.0006, 0.012, n)))
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2019-01-01", periods=n, freq="D", tz="UTC"),
            "open": kurs,
            "high": kurs * 1.01,
            "low": kurs * 0.99,
            "close": kurs,
            "volume": np.full(n, 100.0),
            "turnover": kurs * 100.0,
        }
    )


def _aufstellung(namen: tuple[str, str]) -> tuple[dict, dict]:
    """Beine und Konfigurationen wie ``cli wettbewerb`` sie baut.

    Derselbe Weg ueber ``_bybit_kontrakt``: Ein Bitstamp-Symbol wird auf
    seinen Kontrakt aufgeloest, ein Kontraktname bleibt er selbst. Die
    Kontraktdaten sind in beiden Faellen dieselben - **nur der Schluessel
    unterscheidet sich**, und genau der entscheidet ueber die Zulassung.
    """
    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range
    from cli import _bybit_kontrakt, _fallback_instrument
    from core.config import get_settings

    settings = get_settings()
    frames = common_range(
        {name: _reihe(TAGE, saat) for saat, name in enumerate(namen, start=1)}
    )
    configs = {
        name: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(name)),
            risk=settings.risk,
            initial_equity=Decimal("500"),
            enforce_risk_limits=True,
        )
        for name in frames
    }
    return frames, configs


@dataclass(frozen=True)
class Strecke:
    """Ein vollstaendiger Durchlauf, so wie ``cli wettbewerb`` ihn fuehrt."""

    bericht: GateReport
    fenster: int
    trades: int


def _fahre(namen: tuple[str, str]) -> Strecke:
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.gates import evaluate_gates
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    frames, configs = _aufstellung(namen)
    genom = spitzenkandidat()
    lauf = run_portfolio_walkforward(
        frames, lambda: compile_genome(genom), configs
    )
    gates = evaluate_gates(
        genom,
        lauf,
        next(iter(frames.values())),
        next(iter(configs.values())),
        trials_so_far=1,
        frames=frames,
        configs=configs,
    )
    return Strecke(gates, len(lauf.windows), len(lauf.all_trades))


@pytest.fixture(scope="module")
def an_der_boerse() -> Strecke:
    return _fahre(BOERSE)


@pytest.fixture(scope="module")
def auf_forschungskerzen() -> Strecke:
    return _fahre(FORSCHUNG)


def _alles_bestanden(bericht: GateReport) -> GateReport:
    """Derselbe Bericht, aber mit bestandenen Gates.

    **Gesetzt, nicht gemessen** - und nur das. Die Herkunftsfelder bleiben,
    wie der Lauf sie hinterlassen hat; allein daran entscheidet sich hier die
    Zulassung.
    """
    return dataclasses.replace(
        bericht,
        results=[
            GateResult(
                name=r.name,
                status=GateStatus.PASS,
                value=1.0,
                threshold=0.0,
                message="gesetzt",
            )
            for r in bericht.results
        ],
    )


class TestDerLaufSetztDieHerkunft:
    """Die beiden Uebergaben zwischen Kerzenname und Bericht."""

    def test_die_strecke_traegt_ueberhaupt(self, an_der_boerse: Strecke) -> None:
        """Ohne Fenster und ohne Trades saehe alles Weitere gleich aus.

        Ein Lauf, der nichts gerechnet hat, liefert dieselben Schalterwerte
        wie einer, der gerechnet hat - und der Test waere leer, ohne rot zu
        werden.
        """
        assert an_der_boerse.fenster >= 3
        assert an_der_boerse.trades >= 20
        assert len(an_der_boerse.bericht.results) == 11

    def test_boersennamen_lassen_den_schalter_unten(
        self, an_der_boerse: Strecke
    ) -> None:
        """**Der Fund von Befund 284.** Gelaufen war das nie.

        ``referenzdaten=False`` aus einem echten Lauf heisst: Diese Pruefung
        war vollstaendig und lag auf Kerzen der Boerse, auf der gehandelt
        wird. Mehr braucht die Zulassung nicht.
        """
        gates = an_der_boerse.bericht

        assert gates.referenzdaten is False
        assert gates.vorauswahl is False
        assert gates.passed == gates.geprueftes_bestanden, (
            "ohne Vorauswahl und ohne Forschungskerzen entscheiden allein die "
            "Gates - alles andere waere eine dritte, ungenannte Sperre"
        )

    def test_forschungsnamen_setzen_ihn(
        self, auf_forschungskerzen: Strecke
    ) -> None:
        """Die Gegenrichtung, ebenfalls aus dem Lauf und nicht von Hand."""
        gates = auf_forschungskerzen.bericht

        assert gates.referenzdaten is True
        assert gates.vorauswahl is False
        assert not gates.passed


class TestDerNameAendertNurDieZulassung:
    def test_beide_laeufe_messen_dasselbe(
        self, an_der_boerse: Strecke, auf_forschungskerzen: Strecke
    ) -> None:
        """Dieselben Kerzen unter zwei Namen - dieselben Zahlen.

        Waere das je anders, haette die Herkunft ein Gate beeinflusst, statt
        nur die Zulassung zu sperren. Dann liesse sich aus zwei Berichten
        nicht mehr ablesen, was die Sperre kostet.
        """
        boerse = an_der_boerse.bericht
        forschung = auf_forschungskerzen.bericht

        assert [r.name for r in boerse.results] == [
            r.name for r in forschung.results
        ]
        assert [r.status for r in boerse.results] == [
            r.status for r in forschung.results
        ]
        assert [r.value for r in boerse.results] == [
            r.value for r in forschung.results
        ]
        assert boerse.geprueftes_bestanden == forschung.geprueftes_bestanden

    def test_eine_zufallsreihe_besteht_nicht(
        self, an_der_boerse: Strecke
    ) -> None:
        """Das gehoert hierher, damit niemand die Datei fuer einen Beleg
        haelt.

        Der Spitzenkandidat auf zwei Zufallslaeufen scheitert - gemessen an
        7 von 11 Gates. Diese Datei prueft die Maschinerie und sagt ueber
        eine Strategie nichts aus.
        """
        assert not an_der_boerse.bericht.geprueftes_bestanden
        assert an_der_boerse.bericht.failures


class TestDieZulassungHaengtAmLauf:
    """Was der Lauf hinterlaesst, reicht bis ins Urteil durch.

    Die Gate-Ergebnisse sind hier gesetzt - siehe ``_alles_bestanden``. Was
    aus dem Lauf stammt, sind ``referenzdaten`` und ``vorauswahl``, und das
    ist die Haelfte, die nie gefahren wurde: Bis Befund 284 kam der
    Erfolgsfall allein aus einem handgebauten ``GateReport``.
    """

    def test_mit_boersennamen_wird_es_eine_zulassung(
        self, an_der_boerse: Strecke
    ) -> None:
        voll = _alles_bestanden(an_der_boerse.bericht)

        assert voll.passed is True
        assert "alle 11 Gates bestanden" in voll.summary()

    def test_mit_forschungsnamen_nicht(
        self, auf_forschungskerzen: Strecke
    ) -> None:
        """Derselbe Schritt auf der anderen Strecke - und es bleibt dabei."""
        voll = _alles_bestanden(auf_forschungskerzen.bericht)

        assert voll.geprueftes_bestanden is True
        assert voll.passed is False
        assert "Forschungskerzen" in voll.summary()
        assert "Daten der Boerse" in voll.summary()

    def test_der_unterschied_ist_allein_der_name(
        self, an_der_boerse: Strecke, auf_forschungskerzen: Strecke
    ) -> None:
        """Beide Berichte, nebeneinander: ein Feld trennt sie."""
        a = _alles_bestanden(an_der_boerse.bericht)
        b = _alles_bestanden(auf_forschungskerzen.bericht)

        unterschiede = {
            feld.name
            for feld in dataclasses.fields(GateReport)
            if getattr(a, feld.name) != getattr(b, feld.name)
        }

        assert unterschiede == {"referenzdaten"}
        assert a.passed is not b.passed
