"""Wer liest die Funding-Spalte? - Befund 361.

Die Frage klingt nach Buchhaltung und ist eine Betriebsfrage: Eine Carry-Regel
ohne aktuelle Raten handelt **nie**, und das soll beim Start des Roboters
stehen und nicht nach einer stillen Woche auffallen. Dazu muss der Betrieb vor
dem ersten Balken wissen, ob die Strategie die Spalte ueberhaupt liest.

``indicators.FUNDINGLESER`` ist die Liste, ``Genome.liest_funding`` die Frage
daran. Beides ist von Hand aufgeschrieben, also wird beides gemessen: Jeder
Eintrag der REGISTRY wird hier mit und ohne Spalte gerechnet, und wer sich
unterscheidet, **muss** auf der Liste stehen. Ein vierter Funding-Indikator
faellt damit auf, sobald er dazukommt - und nicht erst, wenn eine Regel mit ihm
live schweigt.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.funding import SPALTE
from strategy import indicators
from strategy.indicators import FUNDINGLESER, REGISTRY


def _kerzen(n: int = 600) -> pd.DataFrame:
    """Kerzen mit einer Funding-Spalte, die sich bewegt.

    Bewegt, nicht konstant: ``funding_zscore`` teilt durch die
    Standardabweichung, und auf einer flachen Reihe ist die null - der
    Indikator gaebe dort mit und ohne Spalte NaN und saehe aus wie einer, der
    die Spalte nicht liest.

    Und lang genug, dass die Reihe nicht an der Fensterbreite scheitert: Der
    groesste Mittelwert einer Parameterspanne liegt bei 210
    (``funding_zscore.period``, Spanne 20..400). Bei 300 Balken blieben davon
    90 gueltige Werte; bei zu kurzer Reihe waere **alles** NaN, mit und ohne
    Spalte, und die Messung saehe aus wie "liest kein Funding" - sie waere nur
    nichtssagend. 600 laesst Luft fuer einen Indikator mit groesserer Periode.
    """
    zeit = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    kurs = 100.0 + np.sin(np.arange(n) / 7.0) * 5.0
    return pd.DataFrame(
        {
            "open_time": zeit,
            "open": kurs,
            "high": kurs + 1.0,
            "low": kurs - 1.0,
            "close": kurs,
            "volume": np.full(n, 10.0),
            "turnover": np.full(n, 1000.0),
            SPALTE: 0.0001 + np.cos(np.arange(n) / 11.0) * 0.00005,
        }
    )


def _standardparameter(name: str) -> dict[str, int]:
    """Die Mitte jeder Parameterspanne - eine Wahl, die ueberall faellt."""
    _, spec = REGISTRY[name]
    return {k: (lo + hi) // 2 for k, (lo, hi) in spec.param_bounds.items()}


def _reagiert_auf_die_spalte(name: str) -> bool:
    """Gemessen: Aendert sich die Reihe, wenn die Spalte fehlt?"""
    frame = _kerzen()
    mit = indicators.compute(name, frame, _standardparameter(name))
    ohne = indicators.compute(name, frame.drop(columns=[SPALTE]), _standardparameter(name))
    return not np.array_equal(mit, ohne, equal_nan=True)


class TestDieListeStimmtMitDerWirklichkeit:
    @pytest.mark.parametrize("name", sorted(REGISTRY))
    def test_jeder_indikator_steht_auf_der_richtigen_seite(self, name: str) -> None:
        """Der eigentliche Test, und er laeuft ueber **alle** Indikatoren.

        Keine Stichprobe: Die Liste darf nicht nur heute stimmen, sondern auch
        nach dem naechsten Indikator, den niemand mehr mit Funding verbindet.
        """
        assert _reagiert_auf_die_spalte(name) is (name in FUNDINGLESER), (
            f"'{name}' reagiert auf die Funding-Spalte, steht aber nicht in "
            f"FUNDINGLESER - oder umgekehrt"
        )

    def test_die_liste_ist_nicht_leer(self) -> None:
        """Eine leere Liste wuerde den Test darueber ebenfalls bestehen - und
        jede Warnung im Betrieb lautlos abschalten.

        Keine Pinnadel auf die Zahl: Heute sind es drei, und ein vierter
        Funding-Indikator ist etwas Erlaubtes. Der Test darueber sagt, dass die
        Liste **stimmt**; hier steht nur, dass sie ueberhaupt etwas enthaelt.
        """
        assert FUNDINGLESER

    def test_alle_eintraege_sind_echte_indikatoren(self) -> None:
        """Ein Tippfehler auf der Liste waere stumm: Der Name traefe dann auf
        kein Genom zu, und die Warnung bliebe aus."""
        assert FUNDINGLESER.issubset(REGISTRY)


class TestDasGenomWeissEsVonSichSelbst:
    def test_die_carry_regel_liest_funding(self) -> None:
        from tests.test_abgleichluecke import _carry_regel

        assert _carry_regel().liest_funding()

    def test_eine_regel_ohne_funding_nicht(self) -> None:
        from tests.test_replay import einfaches_genom

        assert not einfaches_genom().liest_funding()

    def test_gefragt_wird_nach_dem_namen_nicht_nach_dem_schluessel(self) -> None:
        """Der Schluessel fuehrt die Parameter mit
        (``indicator:funding_avg(period=21)``). Eine Zeichenkettensuche darin
        waere eine Vermutung ueber ein Format, das sich aendern darf.
        """
        from tests.test_abgleichluecke import _carry_regel

        genome = _carry_regel()
        schluessel = genome.required_operands()

        assert genome.liest_funding()
        assert any("funding" in s for s in schluessel), (
            "Vorbedingung dieses Tests: die Regel nutzt ueberhaupt Funding"
        )
