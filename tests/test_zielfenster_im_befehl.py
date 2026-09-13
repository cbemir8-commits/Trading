"""Das Zielfenster haengt an derselben Kette wie der Abstand.

**Befund 269.** Die Rechnung braucht dieselben Groessen, die ``cli abstand``
schon ermittelt: Randtrades raus (152), Kennzahlen darauf, **effektive**
Stichprobe wie im Gate (135/139). Eine zweite Kopie davon wuerde auseinander-
laufen, und der Unterschied waere nicht zu sehen - genau die Begruendung, mit
der ``cli finanzierung`` seinen ``lauf``-Helfer traegt.

Wie ernst das ist, zeigt dieser Befund an sich selbst: Mit der **rohen**
Trade-Zahl statt der effektiven meldet die Rechnung einen Deflated Sharpe von
0,92, waehrend das Gate 0,59 sagt. Das ist kein Rundungsfehler, sondern der
Unterschied zwischen "fast geschafft" und "weit weg".
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _abstand() -> ast.FunctionDef:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    return next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == "abstand"
    )


@pytest.fixture
def quelle() -> str:
    return ast.unparse(_abstand())


class TestDieFlaggenGibtEs:
    def test_zielfenster(self) -> None:
        assert "zielfenster" in [a.arg for a in _abstand().args.args]

    def test_und_spot(self) -> None:
        """Die beiden offenen Gates stehen am Spot-Punkt (Befund 268)."""
        assert "spot" in [a.arg for a in _abstand().args.args]

    def test_spot_nimmt_hebel_und_funding(self, quelle: str) -> None:
        assert "_ohne_hebel(genome)" in quelle
        assert "FundingSchedule(default_rate=Decimal('0'))" in quelle


class TestEsRechnetMitDerEffektivenStichprobe:
    """Die Wache, an der dieser Befund selbst gescheitert waere."""

    def test_das_handelsbuch_bekommt_die_effektive_zahl(self, quelle: str) -> None:
        """``n`` ist an dieser Stelle bereits ``stichprobe.effektiv`` - der
        Befehl setzt es vorher um. Wer hier ``len(...)`` schriebe, bekaeme die
        rohe Zahl und einen um 0,33 zu guenstigen Deflated Sharpe."""
        assert "effektiv=n" in quelle

    def test_und_die_summe_alle_trades(self, quelle: str) -> None:
        """Rendite und Rueckgang tragen auch die am Datenende glattgestellten
        Trades (Befund 152) - die Statistik nicht. Beides ist richtig, und
        beides muss an die richtige Stelle."""
        assert "report.all_trades" in quelle

    def test_die_momente_kommen_aus_den_gehandelten(self, quelle: str) -> None:
        """Schiefe und Woelbung aus einem Lauf ueber **alle** Trades haben in
        diesem Befund die Budgetgrenze von 231 auf 214 verschoben."""
        assert "gehandelt.all_trades" in quelle
        assert "schiefe=schiefe" in quelle


class TestDieAusgabeSagtDasNoetige:
    def test_beide_wege_stehen_nebeneinander(self, quelle: str) -> None:
        """Nur im Vergleich ist zu sehen, dass es am *Wie* haengt."""
        assert "ergebnis.wege" in quelle

    def test_die_budgetgrenze_wird_genannt(self, quelle: str) -> None:
        assert "budgetgrenze" in quelle
        assert "Fenster schliesst sich" in quelle

    def test_der_gedeckelte_fall_wird_unterschieden(self, quelle: str) -> None:
        """'Grenze jenseits des Suchbereichs' ist der guenstigste Fall, 'kein
        Weg traegt' der schlechteste. Sie duerfen nicht gleich aussehen."""
        assert "gedeckelt" in quelle
        assert "traegt schon jetzt nicht mehr" in quelle

    def test_und_wohin_es_dann_geht(self, quelle: str) -> None:
        """Die konstruktive Haelfte: Die Latte haengt an der effektiven
        Stichprobe, nicht am Suchbudget."""
        assert "effektiven Stichprobe" in quelle
        assert "mehr Suche nicht" in quelle
