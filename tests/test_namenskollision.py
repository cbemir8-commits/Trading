"""Zwei Dinge unter einem Namen - Befund 455.

Was passiert ist
----------------
``cli vorratsdecke -i D --reibungslos`` ist am **Bericht** abgestuerzt, nach
vollstaendiger Messung::

    AttributeError: 'Reibungsprobe' object has no attribute 'haelt'

In ``vorratsdecke()`` hiess eine ``Einflussprobe`` ``probe``. Weiter unten
setzte die Reibungsleiter ``probe = bild.probe`` - eine
``kostenanteil.Reibungsprobe``. Ab dort trug derselbe Name ein anderes Ding,
und ``preisurteil(probe=probe)`` bekam es untergeschoben.

Warum es auf Viertelstunden nicht aufgefallen ist
-------------------------------------------------
``preisurteil`` wird nur bei einer **tragfaehigen** Decke gerufen. Auf 15
Minuten traegt sie nicht (Befund 450), also lief die Zeile nie - mit Leiter
jedenfalls nicht. Auf Tageskerzen traegt sie, und der Absturz kam sofort.

**Der Absturz war das Glueck.** Haette ``Reibungsprobe`` zufaellig ein Feld
``haelt`` gehabt - sie hat ``belastbar``, und ``decke.Reibungsprobe`` hat
``anschlag_haelt`` -, dann waere kein Fehler gekommen, sondern ein **Urteil
aus der falschen Quelle**.

Was diese Tests festhalten
--------------------------
Dass der Bericht auf Tageskerzen mit Leiter durchlaeuft, und dass die drei
Klassen unterscheidbar bleiben: Wer eine von ihnen dort hinschiebt, wo eine
andere erwartet wird, soll es nicht stillschweigend tun koennen.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: Das Protokoll des abgestuerzten Laufs - vollstaendig gemessen, mit Sprosse
#: bei Faktor 0 und **ohne** 'n_eff' je Sprosse (das kam erst mit 456).
PROTOKOLL = "reports/vorratsdecke/2026-11-02_090144.jsonl"


@pytest.fixture(scope="module")
def ausgabe() -> str:
    """**Auf Modulebene und nicht in der Klasse** (Befund 426/429). Eine
    Fixture mit 'scope="module"' als Methode zu schreiben bricht pytest mit
    'assert not self._finalizers' - hier beim ersten Lauf genau so
    passiert."""
    from typer.testing import CliRunner

    from cli import app

    if not Path(PROTOKOLL).exists():
        pytest.fail(f"{PROTOKOLL} fehlt - ohne das Protokoll misst dieser Test nichts")
    ergebnis = CliRunner().invoke(app, ["vorratsdecke", "-i", "D", "--aus", PROTOKOLL])
    assert ergebnis.exit_code == 0, ergebnis.output[-2000:]
    return " ".join(ergebnis.output.split())


class TestDerBerichtLaeuftAufTageskerzenDurch:
    def test_die_stelle_die_abgestuerzt_ist_steht_wieder_da(self, ausgabe) -> None:
        """``preisurteil`` mit der **Einflussprobe**: Auf diesem Vorrat haengt
        die Gerade an einer einzigen Regel, also nennt es keinen Preis - und
        genau diesen Satz hat der Absturz verschluckt."""
        assert "Kein Preis ablesbar" in ausgabe
        assert "Gerade haengt an einer einzigen Regel" in ausgabe

    def test_und_die_leiter_auch(self, ausgabe) -> None:
        assert "Dieselben Regeln bei anderer Reibung" in ausgabe
        assert "0 13 -0.611" in ausgabe
        assert "1 13 -0.614" in ausgabe


class TestDieDreiKlassenSindUnterscheidbar:
    """Drei Klassen, zwei davon gleich benannt in verschiedenen Modulen. Die
    Frage ist nicht, ob das schoen ist, sondern ob eine Verwechslung auffaellt
    - und das tut sie nur, solange ihre Felder verschieden heissen."""

    def test_keine_von_ihnen_traegt_das_feld_einer_anderen(self) -> None:
        from research.decke import Reibungsprobe as AmAnschlag
        from research.kostenanteil import Reibungsprobe as AufDerLeiter
        from research.vorratsdecke import Einflussprobe

        marken = {
            "vorratsdecke.Einflussprobe": "haelt",
            "kostenanteil.Reibungsprobe": "belastbar",
            "decke.Reibungsprobe": "anschlag_haelt",
        }
        klassen = {
            "vorratsdecke.Einflussprobe": Einflussprobe,
            "kostenanteil.Reibungsprobe": AufDerLeiter,
            "decke.Reibungsprobe": AmAnschlag,
        }

        for name, marke in marken.items():
            for anderer, klasse in klassen.items():
                hat = hasattr(klasse, marke)
                assert hat is (anderer == name), f"{anderer} und {marke}"

    def test_preisurteil_verlangt_die_einflussprobe(self) -> None:
        """Die Erwartung steht in der Signatur - und damit faellt eine
        Verwechslung wenigstens auf."""
        import inspect

        from research.vorratsdecke import preisurteil

        angaben = inspect.signature(preisurteil).parameters["probe"]

        assert "Einflussprobe" in str(angaben.annotation)


class TestDerNameWirdNichtZweimalBelegt:
    """Die Wache gegen den Rueckfall: In ``vorratsdecke()`` darf ``probe``
    nicht wieder an zwei verschiedene Dinge gebunden werden."""

    def _rumpf(self) -> ast.FunctionDef:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        for n in ast.walk(baum):
            if isinstance(n, ast.FunctionDef) and n.name == "vorratsdecke":
                return n
        pytest.fail("cli.vorratsdecke nicht gefunden")

    def test_die_beiden_proben_haben_verschiedene_namen(self) -> None:
        namen: list[str] = []
        for knoten in ast.walk(self._rumpf()):
            if not isinstance(knoten, ast.Assign):
                continue
            quelle = ast.unparse(knoten.value)
            if "einflussprobe(" in quelle or ".probe" in quelle:
                namen.extend(
                    z.id for z in knoten.targets if isinstance(z, ast.Name)
                )

        assert len(namen) == len(set(namen)), f"doppelt belegt: {namen}"
        assert "einfluss" in namen
        assert "reibungsprobe" in namen
