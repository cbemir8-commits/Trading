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

from tests.zaehlerwege import BUCHUNGSWEGE, zaehlende_befehle

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
#: **Steht seit Befund 479 in ``tests/zaehlerwege``**, weil dieselbe Frage
#: auch der Rauchtest stellt - und dort nur nach ``save_trials`` gesucht
#: wurde, also seit der Umstellung nach nichts. Zwei Fassungen einer Regel
#: sind zwei Gelegenheiten, dass sie auseinanderlaufen (464); hier war es
#: passiert. Die Begruendung, warum **beide** Wege dazugehoeren, steht dort.
BUCHUNGEN = BUCHUNGSWEGE


def _schreiber() -> set[str]:
    """Alle Befehle, die den Zaehler fortschreiben - gefunden, nicht gelistet."""
    return zaehlende_befehle()


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
