"""Wie weit die Suche reicht - und warum nicht weiter (Befund 460).

Die Frage
---------
``cli nachgesehen`` existiert, damit dieses Projekt nicht nachbaut, was es
besitzt (Befund 425). Es liest die Docstrings aus ``research/`` und
``cli.py``. Gemessen sind das **1570 von 6114** Docstrings im Projekt - 25,7 %
-, und allein ``tests/`` traegt **4239**, mehr als alles andere zusammen.

Dieses Projekt schreibt seine Befunde ausdruecklich in Test-Docstrings: jede
Wache nennt dort ihren Grund, ihre Messung und ihre Lehre. Der Index zu
erweitern war also die naheliegende Verbesserung.

Die Messung hat sie abgewiesen
------------------------------
    Index      Eintraege   Quote   Raenge der sechs Faelle
    Vorgabe         1570     5/6   3, 2, 7, 2, -, 1
    + tests         5809     4/6   3, 2, -, 2, -, 2

Zwei Maße, dieselbe Richtung. Der Fall aus Befund 418 stand auf **Rang 7 von
8** und faellt heraus. Und die Frage, deren Antwort mir in Befund 459 gefehlt
hat, findet den Quelltext in der Vorgabe auf **Rang 1** - mit ``tests/`` im
Index auf Rang 2, hinter dem Test, den ich hinterher darueber geschrieben
habe.

    Ein Index, der die Aufzeichnung eines Fehlers ueber das Werkzeug stellt,
    das ihn verhindert, sucht schlechter.

Deshalb bleibt die Reichweite erreichbar, aber ausdruecklich: ``--auch-tests``.
Die Vorgabe bleibt die Rangfolge, die abgenommen ist.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.nachgesehen import (
    BAEUME,
    GRENZE,
    PROBEFAELLE,
    ZUSATZBAEUME,
    abnahme,
    bericht,
    bestand,
    quote,
)

WURZEL = Path(__file__).resolve().parent.parent

#: Die Baeume mit Docstrings, die es im Projekt gibt.
ALLE_BAEUME = (
    "research", "tests", "backtest", "strategy", "core", "execution", "web",
)

ERWEITERT = BAEUME + ZUSATZBAEUME


def _docstrings(name: str) -> int:
    ort = WURZEL / name
    dateien = (
        [p for p in sorted(ort.rglob("*.py")) if "__pycache__" not in p.parts]
        if ort.is_dir()
        else [ort]
    )
    traeger = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    gezaehlt = 0
    for p in dateien:
        try:
            baum = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        gezaehlt += 1 if ast.get_docstring(baum) else 0
        gezaehlt += sum(
            1
            for n in ast.walk(baum)
            if isinstance(n, traeger) and ast.get_docstring(n)
        )
    return gezaehlt


class TestWieWeitDieSucheReicht:
    """Gemessen als **Verhaeltnis** und nicht als Zahl: Eine Wache, die an
    einer Docstring-Zahl haengt, wird rot, sobald jemand einen Docstring
    schreibt - genau die Bauart, die Befund 454 verworfen hat."""

    def test_die_tests_tragen_mehr_als_der_ganze_index(self) -> None:
        """**Die tragende Zahl dieses Befundes.** Wer sie nicht kennt, haelt
        den Index fuer vollstaendig."""
        im_index = len(bestand())

        assert _docstrings("tests") > im_index

    def test_der_index_sieht_eine_minderheit_des_projekts(self) -> None:
        gesamt = sum(_docstrings(b) for b in ALLE_BAEUME) + _docstrings("cli.py")
        anteil = len(bestand()) / gesamt

        assert 0.15 < anteil < 0.40, f"gemessen {anteil:.1%}"

    def test_der_erweiterte_index_ist_deutlich_groesser(self) -> None:
        assert len(bestand(ERWEITERT)) > 3 * len(bestand())

    def test_beide_indexe_stehen_nebeneinander(self) -> None:
        """``bestand`` ist zwischengespeichert; mit einer Groesse von 1 wuerde
        jeder Wechsel neu lesen und die Suche unbenutzbar langsam."""
        a, b = bestand(), bestand(ERWEITERT)

        assert a is bestand()
        assert b is bestand(ERWEITERT)
        assert a is not b


class TestWarumNichtWeiter:
    """**Die Entscheidung, als Messung festgehalten.**

    Dieser Test faellt auch dann, wenn die Erweiterung einmal **besser**
    waere. Das ist Absicht: Er ist kein Zahlenschutz, sondern ein
    Entscheidungsvermerk. Wird er rot, heisst das "neu messen und neu
    entscheiden" und nicht "Zahl nachziehen".
    """

    def test_die_vorgabe_sucht_nicht_schlechter_als_der_grosse_index(self) -> None:
        vorgabe, _ = quote()
        erweitert, _ = quote(baeume=ERWEITERT)

        assert vorgabe >= erweitert, (
            f"Vorgabe {vorgabe}, erweitert {erweitert} - wenn die Erweiterung "
            f"nicht mehr kostet, gehoert die Entscheidung aus Befund 460 neu "
            f"gefasst."
        )

    def test_und_zwar_an_einem_konkreten_fall(self) -> None:
        """Nicht nur in der Summe: Der Fall aus Befund 418 steht knapp - Rang
        7 von 8 - und ist der, den die Erweiterung verdraengt."""
        knapp = next(f for f in PROBEFAELLE if f.befund == 418)
        raenge = dict(zip(PROBEFAELLE, [r for _, r in abnahme()], strict=True))
        gross = dict(
            zip(PROBEFAELLE, [r for _, r in abnahme(baeume=ERWEITERT)], strict=True)
        )

        assert raenge[knapp] is not None
        assert raenge[knapp] <= GRENZE
        assert gross[knapp] is None, "sonst ist die Begruendung ueberholt"

    def test_mein_eigener_fall_steht_in_der_vorgabe_oben(self) -> None:
        """Befund 459: Ich habe nicht gesucht, sondern gebaut. Die Antwort
        stand auf Rang 1 - und soll dort stehen bleiben, denn wenn sie es
        nicht tut, ist der naechste Umweg wahrscheinlicher."""
        meiner = next(f for f in PROBEFAELLE if f.befund == 459)
        raenge = dict(zip(PROBEFAELLE, [r for _, r in abnahme()], strict=True))

        assert meiner.erwartet == "versuche.py:trockenlauf"
        assert raenge[meiner] == 1

    def test_und_im_grossen_index_nicht_mehr(self) -> None:
        """Dort steht der Test davor, den ich **hinterher** geschrieben
        habe - die Aufzeichnung des Fehlers vor dem Werkzeug dagegen."""
        meiner = next(f for f in PROBEFAELLE if f.befund == 459)
        gross = dict(
            zip(PROBEFAELLE, [r for _, r in abnahme(baeume=ERWEITERT)], strict=True)
        )

        assert gross[meiner] is not None
        assert gross[meiner] > 1


class TestDerSchalterSagtWasErTut:
    @staticmethod
    def _lauf(*args: str) -> str:
        from typer.testing import CliRunner

        from cli import app

        ergebnis = CliRunner().invoke(app, ["nachgesehen", *args])
        assert ergebnis.exit_code == 0, ergebnis.output[-800:]
        return " ".join(ergebnis.output.split())

    def test_die_vorgabe_schweigt_dazu(self) -> None:
        """Ein Hinweis, der immer dasteht, wird nicht gelesen."""
        aus = self._lauf("Rauchtest der nichts hinterlassen darf")

        assert "Erweiterter Index" not in aus
        assert "versuche.py:trockenlauf" in aus

    def test_mit_dem_schalter_steht_es_dabei(self) -> None:
        """**Und die Quote dazu.** Eine Rangfolge, deren Abnahme niemand
        kennt, liest sich sonst wie die geprueefte."""
        aus = self._lauf("--auch-tests", "Rauchtest der nichts hinterlassen darf")

        assert "Erweiterter Index" in aus
        assert "Das kostet Rangfolge" in aus
        assert "Befund 460" in aus

    def test_der_schalter_findet_wirklich_in_den_tests(self) -> None:
        """Die Gegenprobe: Ohne ihn ist eine Frage, die nur ein Test
        beantwortet, nicht zu finden."""
        frage = "Trockenlauf hinterlaesst nichts Zaehler Bestenliste Berichte"
        ohne = self._lauf(frage)
        mit = self._lauf("--auch-tests", frage)

        assert "test_" not in ohne
        assert "test_" in mit

    def test_die_hilfe_nennt_den_grund(self) -> None:
        import inspect

        import cli as modul

        angabe = inspect.signature(modul.nachgesehen).parameters["auch_tests"]
        hilfe = str(angabe.default.help)

        assert "Befund 460" in hilfe
        assert "kostet messbar Rangfolge" in hilfe


class TestDieAbnahmeBleibtEhrlich:
    def test_der_nicht_gefundene_fall_bleibt_stehen(self) -> None:
        """Dieselbe Regel wie zuvor: Eine Abnahme, aus der man die
        Fehlschlaege entfernt, misst nichts."""
        offen = [f for f in PROBEFAELLE if not f.gefunden_erwartet]

        assert offen, "ohne einen offenen Fall ist die Abnahme geschoent"
        raenge = dict(zip(PROBEFAELLE, [r for _, r in abnahme()], strict=True))
        for fall in offen:
            assert raenge[fall] is None, fall.erwartet

    def test_jeder_fall_nennt_eine_stelle_die_es_gibt(self) -> None:
        namen = {str(s) for s, _ in bestand(ERWEITERT)}

        for fall in PROBEFAELLE:
            assert fall.erwartet in namen, fall.erwartet

    def test_der_bericht_nennt_die_quote_seines_eigenen_index(self) -> None:
        vorgabe = " ".join(bericht("Reibung Kopplung").split())
        gross = " ".join(bericht("Reibung Kopplung", baeume=ERWEITERT).split())
        a, n = quote()
        b, _ = quote(baeume=ERWEITERT)

        assert f"{a} von {n}" in vorgabe
        assert f"{b} von {n}" in gross
        assert a != b, "sonst misst dieser Test nichts"


@pytest.mark.parametrize("baum", ZUSATZBAEUME)
def test_jeder_zusatzbaum_gibt_es_und_traegt_docstrings(baum: str) -> None:
    assert (WURZEL / baum).is_dir()
    assert _docstrings(baum) > 100
