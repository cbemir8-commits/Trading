"""Der Melder auf den Reihenschnitt, selbst geprueft - Befund 491.

Die Lehre aus Befund 479, eine Stufe weiter
-------------------------------------------
479 hat den Versuchszaehler-Melder in ``tests/zaehlerwege`` gelegt und
``test_zaehlerwege`` danebengestellt, mit dem Satz: *"Ohne sie waere er der
dritte ungepruefte Zaehler in dieser Sitzung."*

``tests/schnittwege`` ist in diesem Zyklus entstanden und haette genau so
dagestanden: **neun** Dateien fragen ihn - acht auf Modulebene, eine in einer
Funktion -, und nichts fragte ihn selbst. Gaebe ``schneidet`` eines
Tages immer ``True`` zurueck - ein zu weites Wort in ``SCHNITTWEGE`` genuegt -,
dann waeren neun Dateien voll Wachen auf einen Schlag leer erfuellt, und keine
davon wuerde rot. Das ist dieselbe Bauart wie die leere Teilmenge in 479, nur an der
anderen Ecke.

Die Zahl ist gezaehlt, nicht geschaetzt, und steht als Zusicherung weiter
unten: Der erste Entwurf dieses Kopfes sagte sieben, gemessen waren es acht,
und mit Befund 495 kam ``test_kerzenabdruck`` als neunte dazu.

Was hier geprueft wird
----------------------
* Jeder der drei Wege wird gesehen - einzeln, an kurzen Quellen.
* Und wer **nicht** schneidet, wird nicht gemeldet. Ohne diese Gegenprobe
  saegte die Regel nichts (dieselbe Gegenprobe wie in ``test_zaehlerwege``).
* Am echten ``cli.py``: Es sind welche (Nichtleere, Befund 479), und es sind
  **dieselben** wie in der gepflegten Inventur - bis auf genau einen Befehl,
  und der Unterschied ist gerechnet, nicht behauptet.

Warum der Melder mehr findet als die Inventur
---------------------------------------------
Der Melder zaehlt neun, die Inventur in ``test_abstandsreihe`` acht. Der
Unterschied ist ``korb``: Die Inventur sieht nur Befehle mit
``spitzenkandidat`` im Block, und ``korb`` laedt stattdessen Saaten. Beide
Zahlen sind richtig, sie beantworten verschiedene Fragen - und seit dieser
Datei steht der Unterschied als Messung da, statt zwei Wahrheiten zu sein
(Befund 234).
"""

from __future__ import annotations

from tests.schnittwege import SCHNITTWEGE, schneidende_befehle, schneidet


class TestJederWegWirdGesehen:
    def test_die_tagesfassung(self) -> None:
        assert schneidet("def x():\n    kurz = alle_geschnitten(frames)\n")

    def test_die_feinfassung(self) -> None:
        """Sie war in Befund 490 die richtige und wurde nicht genommen - der
        Melder darf sie nicht uebersehen."""
        assert schneidet("def x():\n    kurz = alle_fein_geschnitten(frames)\n")

    def test_der_verteiler(self) -> None:
        assert schneidet("def x():\n    kurz, zeile = nach_intervall(frames, 'D')\n")

    def test_alle_drei_stehen_in_der_liste(self) -> None:
        assert set(SCHNITTWEGE) == {
            "alle_geschnitten",
            "alle_fein_geschnitten",
            "nach_intervall",
        }


class TestUndWerNichtSchneidetWirdNichtGemeldet:
    """Die Gegenprobe. Faende der Melder immer etwas, saegten die sieben
    Wachen, die ihn fragen, nichts."""

    def test_leerer_text(self) -> None:
        assert not schneidet("")

    def test_wer_nur_den_anfang_schneidet(self) -> None:
        """``common_range`` kuerzt den Anfang aus dem juengeren Bein - das ist
        **kein** Reihenschnitt am oberen Ende (Befund 490)."""
        assert not schneidet("def x():\n    frames = common_range(roh)\n")

    def test_wer_die_reihe_nur_nennt(self) -> None:
        """Ein Vermerk ist keine Kuerzung."""
        assert not schneidet("def x():\n    console.print(reihenzeile(frames))\n")

    def test_und_ein_name_ohne_aufruf_zaehlt_nicht(self) -> None:
        """Die Wege werden mit Klammer gesucht. Ein Wort im Docstring ist
        kein Schnitt - sonst meldete jede Datei, die darueber schreibt."""
        assert not schneidet('def x():\n    """nach_intervall waere hier noetig"""\n')


class TestHilfsfunktionenSindKeineBefehle:
    def test_der_unterstrich_faellt_heraus(self) -> None:
        quelle = "def _reihenvermerk(f):\n    return nach_intervall(f, 'D')\n"

        assert schneidende_befehle(quelle) == set()

    def test_ein_befehl_daneben_wird_gefunden(self) -> None:
        """Die Gegenprobe zur Regel darueber - sonst koennte sie alles
        herausfallen lassen."""
        quelle = (
            "def _reihenvermerk(f):\n"
            "    return nach_intervall(f, 'D')\n"
            "def rennen(f):\n"
            "    kurz, zeile = nach_intervall(f, 'D')\n"
        )

        assert schneidende_befehle(quelle) == {"rennen"}


class TestAmEchtenQuelltext:
    def test_es_sind_welche(self) -> None:
        """Die Zusicherung, die in Befund 479 gefehlt hat."""
        assert schneidende_befehle()

    def test_und_zwar_neun(self) -> None:
        """Faellt einer heraus, hat sich ein Befehl zurueckentschieden, und
        das gehoert gesehen - nicht erst beim naechsten Backfill."""
        assert len(schneidende_befehle()) == 9, sorted(schneidende_befehle())

    def test_die_inventur_ist_darin_enthalten(self) -> None:
        """Eine Wahrheit, zwei Fragen (Befund 234): Die gepflegte Inventur
        steht in ``test_abstandsreihe``; hier wird nur geprueft, dass sie
        nichts sieht, was der gemeinsame Melder nicht sieht."""
        from tests.test_abstandsreihe import TestDieInventurStimmtNoch

        inventur, _nennt, _keins = TestDieInventurStimmtNoch._inventur()

        assert set(inventur) <= schneidende_befehle()

    def test_und_der_unterschied_ist_genau_korb(self) -> None:
        """Gerechnet, nicht begruendet: ``korb`` schneidet, faellt aber aus
        der Inventur, weil die ``spitzenkandidat`` im Block verlangt und
        ``korb`` Saaten laedt."""
        from tests.test_abstandsreihe import TestDieInventurStimmtNoch

        inventur, _nennt, _keins = TestDieInventurStimmtNoch._inventur()

        assert schneidende_befehle() - set(inventur) == {"korb"}

    def test_neun_dateien_haengen_an_ihm(self) -> None:
        """Warum diese Datei existiert, als Zahl - und sie ist gezaehlt, nicht
        geschaetzt (der erste Entwurf des Kopfes sagte sieben).

        Faellt die Zahl, hat eine Wache den gemeinsamen Melder verlassen und
        prueft wieder einen Funktionsnamen. Steigt sie, haengt noch mehr an
        ihm - dann ist diese Datei umso wichtiger.
        """
        import ast
        from pathlib import Path

        frager = {
            p.name
            for p in Path("tests").glob("test_*.py")
            if p.name != "test_schnittwege.py"
            and any(
                isinstance(k, ast.ImportFrom) and k.module == "tests.schnittwege"
                for k in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
            )
        }

        assert len(frager) == 9, sorted(frager)

    def test_niemand_schneidet_mehr_von_hand(self) -> None:
        """Seit 491 geht jeder Schnitt ueber den Verteiler. Die Regel steht
        in ``test_schnittintervall``; hier steht die Gegenprobe, dass die
        beiden Zahlen zusammenpassen."""
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        ueber_verteiler = {
            n.name
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
            and not n.name.startswith("_")
            and "nach_intervall(" in ast.unparse(n)
        }

        assert ueber_verteiler == schneidende_befehle()
