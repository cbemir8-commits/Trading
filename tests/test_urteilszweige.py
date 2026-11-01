"""Welchen Urteilssatz hat nie ein Test gelesen? - Befund 444.

Befund 443 hat einen Satz gefunden, der eine Groesse behauptete, die er nicht
gemessen hat - und ich habe ihn **durch Zufall** gefunden, beim Nachrechnen
einer anderen Zahl. Der Zweig stand in keinem Test; er konnte falsch sein,
ohne dass etwas rot wurde.

``research/urteilszweige.py`` macht die Suche wiederholbar. Diese Tests
pruefen die statische Haelfte (sie braucht keinen Lauf) und lesen dabei die
Saetze, die der erste Lauf als ungelesen gemeldet hat - **einschliesslich
der Berichtsfunktion des Werkzeugs selbst**, die in ihrer eigenen
Fahndungsliste stand.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.urteilszweige import (
    MINDESTZWEIGE,
    Urteil,
    bericht,
    textrueckgaben,
    ungelesene,
    urteilsfunktionen,
)

#: Wie viele Urteilsfunktionen ``research/`` hat - **gemessen** (Befund 444).
#:
#: **Wer hier eine Zahl aendert, hat eine Urteilsfunktion hinzugefuegt oder
#: entfernt.** Beides ist in Ordnung; unbemerkt soll es nicht passieren, denn
#: jede neue Textrueckgabe ist eine neue Aussage, und Befund 443 hat gezeigt,
#: was eine ungelesene Aussage kostet. Die dynamische Haelfte steht nicht
#: unter Test - sie braucht einen Lauf unter 'coverage' und gehoert in den
#: Modulkopf, wo sie datiert ist.
URTEILSFUNKTIONEN: int = 157


def _fn(quelle: str) -> ast.FunctionDef:
    baum = ast.parse(quelle)
    return next(k for k in baum.body if isinstance(k, ast.FunctionDef))


class TestWasAlsTextrueckgabeZaehlt:
    def test_eine_zeichenkette(self) -> None:
        zeilen = textrueckgaben(_fn("def f():\n    return 'ja'\n"))

        assert zeilen == (2,)

    def test_ein_f_string(self) -> None:
        zeilen = textrueckgaben(_fn("def f(x):\n    return f'{x} Stueck'\n"))

        assert zeilen == (2,)

    def test_zusammengesetzter_text(self) -> None:
        """``"a" + b`` und ``"a" % b`` sind Text, auch wenn nur eine Seite
        eine Zeichenkette ist."""
        zeilen = textrueckgaben(_fn("def f(x):\n    return 'a' + x\n"))

        assert zeilen == (2,)

    def test_ein_methodenaufruf_auf_text(self) -> None:
        zeilen = textrueckgaben(_fn("def f(xs):\n    return ' '.join(xs)\n"))

        assert zeilen == (2,)

    def test_eine_zahl_nicht(self) -> None:
        zeilen = textrueckgaben(_fn("def f():\n    return 42\n"))

        assert zeilen == ()

    def test_ein_name_nicht(self) -> None:
        """**Mit Absicht nicht erkannt**: Ob ein Name einen Text haelt,
        waere zu raten - und ein Modul, das Typen raet, ist selbst eine
        Behauptung."""
        zeilen = textrueckgaben(_fn("def f():\n    satz = 'ja'\n    return satz\n"))

        assert zeilen == ()

    def test_return_ohne_wert_nicht(self) -> None:
        zeilen = textrueckgaben(_fn("def f(x):\n    if x:\n        return\n"))

        assert zeilen == ()


class TestVerschachtelteFunktionenZaehlenZuSich:
    """**Mein Fehler im ersten Entwurf** (Befund 444).

    ``ast.walk`` steigt in innere ``def`` ab. Die Rueckgaben einer inneren
    Funktion zaehlten dadurch zur aeusseren, und die gemeldete Zahl war
    falsch - *bevor* sie gepinnt war. Ein Werkzeug, das ungemessene
    Behauptungen findet, darf nicht mit einer ungemessenen anfangen.
    """

    QUELLE = (
        "def aussen(x):\n"
        "    def innen(y):\n"
        "        if y:\n"
        "            return 'a'\n"
        "        return 'b'\n"
        "    return innen(x)\n"
    )

    def test_die_aeussere_hat_keine_eigene(self) -> None:
        aussen = _fn(self.QUELLE)

        assert textrueckgaben(aussen) == ()

    def test_die_innere_hat_zwei(self) -> None:
        innen = next(
            k
            for k in ast.walk(ast.parse(self.QUELLE))
            if isinstance(k, ast.FunctionDef) and k.name == "innen"
        )

        assert textrueckgaben(innen) == (4, 5)

    def test_eine_lambda_zaehlt_nicht_mit(self) -> None:
        fn = _fn("def f(xs):\n    g = lambda x: 'ja'\n    return 'nein'\n")

        assert textrueckgaben(fn) == (3,)

    def test_zweige_in_if_und_try_zaehlen_schon(self) -> None:
        """Gegenprobe: Eingerueckt ist nicht verschachtelt - genau diese
        Zweige sind die Aussagen, um die es geht."""
        fn = _fn(
            "def f(x):\n"
            "    if x:\n"
            "        return 'a'\n"
            "    try:\n"
            "        return 'b'\n"
            "    except ValueError:\n"
            "        return 'c'\n"
        )

        assert textrueckgaben(fn) == (3, 5, 7)


class TestDieListeDerUrteilsfunktionen:
    def test_sie_steht_fest(self) -> None:
        """Gemessen, und gepinnt, damit eine neue Aussage auffaellt."""
        gefunden = urteilsfunktionen()

        assert len(gefunden) == URTEILSFUNKTIONEN, len(gefunden)

    def test_jede_hat_mindestens_zwei_zweige(self) -> None:
        for u in urteilsfunktionen():
            assert u.zweige >= MINDESTZWEIGE, u.name

    def test_die_stelle_aus_443_ist_dabei(self) -> None:
        """``Reibungsprobe.urteil`` - dort sass der Satz, der eine Messung
        vortaeuschte."""
        namen = {u.name for u in urteilsfunktionen()}

        assert "decke.py:urteil" in namen

    def test_und_die_stelle_aus_444(self) -> None:
        namen = {u.name for u in urteilsfunktionen()}

        assert "benchmark.py:verdict_for" in namen

    def test_sie_sind_geordnet(self) -> None:
        namen = [u.name for u in urteilsfunktionen()]

        assert namen == sorted(namen)

    def test_eine_einzelne_rueckgabe_zaehlt_nicht(self, tmp_path: Path) -> None:
        (tmp_path / "x.py").write_text("def f():\n    return 'nur eine'\n")

        assert urteilsfunktionen(tmp_path) == ()


class TestWasAlsUngelesenGilt:
    @staticmethod
    def _eins() -> Urteil:
        return Urteil(modul="x.py", funktion="f", zeilen=(3, 5), ab=1)

    def test_eine_erreichte_zeile_fehlt_nicht(self, tmp_path: Path) -> None:
        offen = ungelesene(
            (self._eins(),), {"/wo/auch/x.py": {3, 5}}, wurzel=tmp_path
        )

        assert offen == ()

    def test_eine_nicht_erreichte_wird_gemeldet(self, tmp_path: Path) -> None:
        offen = ungelesene(
            (self._eins(),), {"/wo/auch/x.py": {3}}, wurzel=tmp_path
        )

        assert offen == ((self._eins(), (5,)),)

    def test_eine_ungemessene_datei_zaehlt_ganz_als_ungelesen(
        self, tmp_path: Path
    ) -> None:
        """**Nicht gemessen ist nicht gelesen.** Das zu verwechseln waere
        der Freibrief aus Befund 430."""
        (tmp_path / "x.py").write_text("x = 1\n")

        offen = ungelesene((self._eins(),), {}, wurzel=tmp_path)

        assert offen == ((self._eins(), (3, 5)),)

    def test_eine_datei_die_es_nicht_gibt_wird_nicht_gemeldet(
        self, tmp_path: Path
    ) -> None:
        """Sonst waere die Aussage ueber nichts: Die Messung ist dann zur
        Quelle verschoben, nicht unvollstaendig."""
        offen = ungelesene((self._eins(),), {}, wurzel=tmp_path)

        assert offen == ()

    def test_der_pfad_wird_am_dateinamen_verglichen(self, tmp_path: Path) -> None:
        """'coverage' liefert absolute Pfade, der AST relative Namen."""
        offen = ungelesene(
            (self._eins(),),
            {"/ganz/anderer/ort/x.py": {3, 5}},
            wurzel=tmp_path,
        )

        assert offen == ()


class TestDerBerichtStandInSeinerEigenenListe:
    """**Der erste Lauf hat die Berichtsfunktion selbst gemeldet** - 3 von 3
    Zeilen ungelesen. Ein Werkzeug gegen ungelesene Saetze, dessen eigene
    Saetze niemand gelesen hat. Hier stehen sie."""

    def test_ohne_urteile_sagt_er_das(self) -> None:
        text = bericht((), ())

        assert "Keine Urteilsfunktionen gefunden" in text

    def test_ohne_offene_behauptet_er_nicht_zu_viel(self) -> None:
        """Alle Zweige betreten heisst **nicht** alle geprueft - genau die
        Verwechslung, aus der Befund 443 entstand."""
        u = Urteil(modul="x.py", funktion="f", zeilen=(3, 5), ab=1)

        text = bericht((u,), ())

        assert "jede Textrueckgabe ist gelesen" in text
        assert "nicht, dass jede **geprueft** ist" in text

    def test_mit_offenen_nennt_er_ganz_ungelesene_zuerst(self) -> None:
        ganz = Urteil(modul="a.py", funktion="f", zeilen=(2, 4), ab=1)
        teils = Urteil(modul="b.py", funktion="g", zeilen=(2, 4, 6, 8), ab=1)

        text = bericht((ganz, teils), ((teils, (8,)), (ganz, (2, 4))))

        assert text.index("a.py:f") < text.index("b.py:g")
        assert "<- ganz ungelesen" in text

    def test_und_sagt_dass_es_ein_verdacht_ist(self) -> None:
        """Befund 118: Der Befehl entscheidet nichts."""
        u = Urteil(modul="x.py", funktion="f", zeilen=(3, 5), ab=1)

        text = bericht((u,), ((u, (5,)),))

        assert "Ein Verdacht, keine Schuld" in text
        assert "Befund 443" in text


class TestDieMessungGehoertZurQuelle:
    def test_der_modulkopf_sagt_es(self) -> None:
        """**Die Falle, in die ich beim ersten Auswerten getappt bin.**

        Die Coverage-Daten stammten von *vor* meiner Aenderung an
        ``benchmark.py``. Die Zeilennummern hatten sich verschoben, und zwei
        Eintraege der Fahndungsliste waren dadurch Artefakte - gemeldet wurde
        ein Zweig, den es in dieser Form nicht mehr gab.
        """
        from research import urteilszweige

        doc = " ".join((urteilszweige.__doc__ or "").split())

        assert "derselben Quelle" in doc
        assert "verschoben" in doc


@pytest.mark.daten
@pytest.mark.langsam
class TestDieZahlenAusDemModulkopf:
    """Die dynamische Haelfte braucht einen Lauf - und der liegt nur vor,
    wenn jemand die Auswahl unter ``coverage`` gefahren hat. Ohne Datei wird
    uebersprungen statt geraten."""

    def test_die_fahndungsliste_laesst_sich_rechnen(self) -> None:
        datei = Path("/home/user/Trading/.coverage")
        if not datei.exists():
            pytest.skip("keine Coverage-Daten - 'coverage run' ist nicht gelaufen")
        coverage = pytest.importorskip("coverage")

        daten = coverage.CoverageData(basename=str(datei))
        daten.read()
        gemessen = {f: set(daten.lines(f) or ()) for f in daten.measured_files()}
        u = urteilsfunktionen()
        offen = ungelesene(u, gemessen)

        assert len(u) == URTEILSFUNKTIONEN
        assert len(offen) < len(u), "alles ungelesen - dann passt die Messung nicht"
