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

#: Alle Befehle, die den Versuchszaehler fortschreiben.
#:
#: **Es waren immer sieben, gelistet waren fuenf** (Befund 282). Diese Wache
#: suchte nach ``save_trials`` und fand damit genau die Befehle, die in den
#: Grundstock buchen. ``korb`` und ``verbund`` erhoehen den Zaehler ueber
#: ``_verzeichne`` - jeder Einzelnachweis hebt ``Verzeichnis.anzahl`` um eins
#: -, und sie standen hier nie, obwohl der Kopf dieser Datei "wer den Zaehler
#: schreibt" verspricht.
#:
#: Aufgefallen ist es, als ``landschaft`` und ``machbarkeit`` auf
#: Einzelnachweise umgestellt wurden und beinahe aus der Aufsicht gefallen
#: waeren. Die Wache haftete am Namen einer Funktion statt an der Wirkung.
ZAEHLER = (
    *SUCHEN,
    "landschaft",
    "machbarkeit",
    "adaptiv",
    "korb",
    "verbund",
)


def _quelle(name: str) -> str:
    baum = ast.parse(Path("cli.py").read_text())
    fn = next(
        n for n in ast.walk(baum)
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.unparse(fn)


#: Die beiden Wege, auf denen der Zaehler steigt.
#:
#: **Beide gehoeren hierher** (Befund 282). Bis dahin suchte diese Wache nur
#: nach ``save_trials``. Als ``landschaft`` und ``machbarkeit`` auf
#: Einzelnachweise umgestellt wurden, waeren sie damit aus der Aufsicht
#: gefallen - nicht weil sie aufgehoert haetten zu zaehlen, sondern weil sie
#: es anders tun. Eine Wache, die am Namen einer Funktion haengt statt an der
#: Wirkung, verliert genau die, die sich aendern.
BUCHUNGEN = ("save_trials", "_verzeichne(")


def _schreiber() -> set[str]:
    """Alle Befehle, die den Zaehler fortschreiben - gefunden, nicht gelistet."""
    baum = ast.parse(Path("cli.py").read_text())
    aus = set()
    for n in ast.walk(baum):
        if not isinstance(n, ast.FunctionDef) or n.name.startswith("_"):
            continue
        quelle = ast.unparse(n)
        if any(weg in quelle for weg in BUCHUNGEN):
            aus.add(n.name)
    return aus


class TestWerDenZaehlerSchreibt:
    def test_es_sind_diese_sieben(self) -> None:
        """Kommt ein achter dazu, faellt er hier auf - und muss sich
        entscheiden, ob er Suche ist oder Messung."""
        assert _schreiber() == set(ZAEHLER)

    def test_beide_buchungswege_werden_gesehen(self) -> None:
        """Der Fehler, den diese Wache selbst beinahe gemacht haette: Sie sah
        nur einen der beiden Wege (Befund 282)."""
        quelle = Path("cli.py").read_text()

        assert all(weg in quelle for weg in BUCHUNGEN)
        assert len(_schreiber()) == len(ZAEHLER)

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
