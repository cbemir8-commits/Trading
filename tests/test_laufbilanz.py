"""Sagt der Wettbewerb am Ende, was er gekostet hat?

**Befund 232.** Die Schlusszeile nannte, wie viele Strategien geprueft
wurden - nicht, wie viele **Versuche** das waren. Die knappe Groesse ist die
zweite: Jeder Versuch hebt die Latte des Deflated Sharpe fuer alle
kuenftigen, dauerhaft, und das Budget aus dem Plan hat eine Grenze.

Beides steht in jedem ``cli stand``. Es stand nur nicht dort, wo die
Versuche gerade ausgegeben worden sind - und das ist der Moment, in dem
jemand entscheidet, ob er noch eine Runde dreht.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import cli
from research.stand import BUDGET


class TestDieBilanz:
    def test_sie_nennt_die_ausgegebenen_versuche(self) -> None:
        text = cli._laufbilanz(198, 205)

        assert "7 Versuche" in text
        assert "198 -> 205" in text

    def test_sie_nennt_den_rest_des_budgets(self) -> None:
        text = cli._laufbilanz(198, 205)

        assert BUDGET.zeile(205) in text

    def test_ohne_versuch_kein_falscher_alarm(self) -> None:
        """Ein Trockenlauf oder ein Abbruch vor der ersten Runde kostet
        nichts - dann soll dort auch nichts von Kosten stehen."""
        text = cli._laufbilanz(198, 198)

        assert "keinen Versuch" in text
        assert "->" not in text

    def test_ein_rueckwaerts_laufender_zaehler_erfindet_nichts(self) -> None:
        """Kommt der Zaehler kleiner zurueck - etwa weil der Behaelter
        zurueckgesetzt wurde -, waere eine negative Zahl eine Behauptung."""
        text = cli._laufbilanz(205, 198)

        assert "keinen Versuch" in text

    def test_ueber_der_grenze_steht_die_antwort_aus_dem_plan(self) -> None:
        text = cli._laufbilanz(BUDGET.grenze - 5, BUDGET.grenze + 2)

        assert "aufgebraucht" in text
        assert "kein Scheitern" in text

    def test_die_grenze_wird_nicht_hier_hingeschrieben(self) -> None:
        """Sie kommt aus ``BUDGET`` - sonst haette das System zwei."""
        quelle = inspect.getsource(cli._laufbilanz)

        assert "BUDGET.zeile" in quelle
        assert "230" not in quelle

    def test_sie_verweist_auf_die_zahlen_der_entscheidung(self) -> None:
        """Preis und Luecke stehen in 'cli stand' (Befund 230) - hier steht
        der Weg dorthin, nicht eine zweite Kopie."""
        text = cli._laufbilanz(198, 205)

        assert "cli stand" in text


class TestDerWettbewerbRuftSieAuf:
    """Gebaut und nicht aufgerufen waere Befund 209 noch einmal."""

    @staticmethod
    def _quelle() -> str:
        baum = ast.parse(Path("cli.py").read_text())
        fn = next(
            n for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "wettbewerb"
        )
        return ast.unparse(fn)

    def test_der_stand_vor_dem_lauf_wird_festgehalten(self) -> None:
        assert "versuche_am_anfang = load_trials(trials_path)" in self._quelle()

    def test_und_am_ende_gegen_den_neuen_gehalten(self) -> None:
        assert "_laufbilanz(versuche_am_anfang" in self._quelle()

    def test_der_stand_wird_vor_der_schleife_gelesen(self) -> None:
        """Sonst zaehlt er die Runden mit und nicht den Lauf."""
        quelle = self._quelle()

        assert quelle.index("versuche_am_anfang =") < quelle.index("while runden ==")

    def test_die_bilanz_kommt_nach_der_bestenliste(self) -> None:
        quelle = self._quelle()

        assert quelle.index("board.save()") < quelle.index("_laufbilanz(")
