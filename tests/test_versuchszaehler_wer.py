"""Wer schreibt den Versuchszaehler fort - und wer sagt es?

**Befund 233.** Befund 216 hat die Budgetgrenze in ``cli wettbewerb`` gebaut
und dabei geschrieben, das sei *"der einzige Befehl, der Versuche in einer
Schleife ausgibt"*. Das stimmte nicht.

**Fuenf** Befehle schreiben ``trials.json`` fort:

    wettbewerb    Suche, unbegrenzt            Wache seit 216, Bilanz seit 232
    research      Suche, ein ganzer Katalog    hatte keine Wache
    landschaft    Sweep um den Kandidaten      zaehlte stumm
    machbarkeit   Sweep ueber Vola-Stellungen  meldete von selbst
    adaptiv       genau ein Versuch            meldete von selbst

``research`` prueft einen ganzen Katalog auf einmal und hat die Grenze nie
angesehen; ``landschaft`` hat gezaehlt, ohne es zu sagen. Beides behoben.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SUCHEN = ("wettbewerb", "research")
ZAEHLER = (*SUCHEN, "landschaft", "machbarkeit", "adaptiv")


def _quelle(name: str) -> str:
    baum = ast.parse(Path("cli.py").read_text())
    fn = next(
        n for n in ast.walk(baum)
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.unparse(fn)


def _schreiber() -> set[str]:
    """Alle Befehle, die ``save_trials`` aufrufen - gefunden, nicht gelistet."""
    baum = ast.parse(Path("cli.py").read_text())
    aus = set()
    for n in ast.walk(baum):
        if isinstance(n, ast.FunctionDef) and "save_trials" in ast.unparse(n):
            aus.add(n.name)
    return aus


class TestWerDenZaehlerSchreibt:
    def test_es_sind_diese_fuenf(self) -> None:
        """Kommt ein sechster dazu, faellt er hier auf - und muss sich
        entscheiden, ob er Suche ist oder Messung."""
        assert _schreiber() == set(ZAEHLER)

    def test_befund_216_hat_sich_geirrt(self) -> None:
        """Der Anlass dieses Befunds, als Zahl."""
        assert len(_schreiber()) > 1


class TestDieSuchenPruefenDasBudget:
    """Eine Suche gibt Versuche fuer neue Hypothesen aus - fuer sie gilt die
    Abmachung aus dem Plan."""

    @pytest.mark.parametrize("name", SUCHEN)
    def test_sie_fragt_vor_dem_ausgeben(self, name: str) -> None:
        assert "_budget_erschoepft" in _quelle(name)

    @pytest.mark.parametrize("name", SUCHEN)
    def test_und_bietet_den_bewussten_weg_darueber_hinaus(self, name: str) -> None:
        assert "ueber_budget" in _quelle(name)

    def test_research_fragt_vor_dem_lauf(self) -> None:
        """Er prueft einen ganzen Katalog auf einmal - danach zu fragen
        waere zu spaet."""
        quelle = _quelle("research")

        assert quelle.index("_budget_erschoepft") < quelle.index("run_admission(")


class TestJederSagtWasErKostet:
    @pytest.mark.parametrize("name", ZAEHLER)
    def test_der_zaehler_wird_nicht_stumm_fortgeschrieben(self, name: str) -> None:
        quelle = _quelle(name)

        assert "_laufbilanz" in quelle or "Versuchszaehler" in quelle, name

    def test_landschaft_sagt_es_seit_diesem_befund(self) -> None:
        assert "_laufbilanz" in _quelle("landschaft")

    def test_die_sweeps_brechen_nicht_ab(self) -> None:
        """**Was ich nicht getan habe.** ``landschaft`` und ``machbarkeit``
        vermessen die Umgebung des vorhandenen Kandidaten; ob so ein Sweep
        eine Hypothese ueber den Markt ist oder eine Messung am Bestand, ist
        eine offene Frage. Sie mitten in ihrer Antwort abzubrechen waere eine
        Entscheidung, die hier nicht faellt.
        """
        for name in ("landschaft", "machbarkeit"):
            assert "_budget_erschoepft" not in _quelle(name), name
