"""Ein neu aufgesetzter Container, und die Suite startet nicht mehr - 427.

Befund 363 hat die **Datenreihe** gepinnt, weil ein neu aufgesetzter Container
den Kerzenspeicher mitnahm und fuenfzehn Tests fielen, ohne dass einer "andere
Reihe" sagte. Dieselbe Sorte Bruch, eine Schicht weiter aussen: Diesmal nahm
der Container die **Werkzeuge** mit.

``pyproject.toml`` erklaert die Entwicklungswerkzeuge nur mit Untergrenzen
(``pytest-asyncio>=0.23``). pip hat beim Wiederaufbau 1.4.1 geholt, und das
warnt, wenn ``asyncio_default_fixture_loop_scope`` fehlt. ``filterwarnings =
["error::DeprecationWarning"]`` macht daraus einen Fehler - geworfen in
``pytest_configure``, also **vor** dem ersten Test:

    INTERNALERROR> pytest.PytestDeprecationWarning: The configuration option
    "asyncio_default_fixture_loop_scope" is unset.

Nicht ein Test ist gelaufen. Kein Testergebnis war falsch - es gab keines.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pytest_konfiguration() -> dict:
    with (WURZEL / "pyproject.toml").open("rb") as datei:
        return tomllib.load(datei)["tool"]["pytest"]["ini_options"]


class TestDieOptionIstGesetzt:
    """Die Wache. Faellt sie weg, startet die Suite beim naechsten
    Wiederaufbau wieder nicht - und zwar ohne ein einziges Testergebnis."""

    def test_der_schleifenbereich_steht_in_der_konfiguration(
        self, pytest_konfiguration
    ) -> None:
        assert "asyncio_default_fixture_loop_scope" in pytest_konfiguration

    def test_und_zwar_auf_function(self, pytest_konfiguration) -> None:
        """Der Wert, auf den kuenftige Fassungen von sich aus gehen."""
        assert pytest_konfiguration["asyncio_default_fixture_loop_scope"] == "function"

    def test_die_warnungen_sind_weiter_fehler(self, pytest_konfiguration) -> None:
        """**Nicht die Gegenrichtung.** Der bequeme Ausweg waere gewesen,
        'filterwarnings' zu lockern - dann waere die Suite still gruen und
        jede kuenftige Verwerfungswarnung unsichtbar. Das waere ein Gate
        gelockert, damit etwas besteht."""
        assert "error::DeprecationWarning" in pytest_konfiguration["filterwarnings"]

    def test_der_grund_steht_daneben(self) -> None:
        text = (WURZEL / "pyproject.toml").read_text(encoding="utf-8")

        assert "Befund 427" in text
        assert "INTERNALERROR" in text
        assert "null Tests" in text


class TestWarumDerWertNichtsAendert:
    """Die Messung, die den Wert rechtfertigt - ohne sie waere 'function'
    geraten."""

    def _testquellen(self) -> list[Path]:
        return sorted((WURZEL / "tests").glob("test_*.py"))

    def test_es_gibt_async_tests(self) -> None:
        """Gegenprobe: Ohne async-Tests waere die ganze Frage gegenstandslos
        und diese Wache leer."""
        treffer = sum(
            quelle.read_text(encoding="utf-8").count("async def test")
            for quelle in self._testquellen()
        )

        assert treffer > 50, f"nur {treffer} async-Tests gefunden"

    def test_aber_keine_async_fixtures(self) -> None:
        """Der Schleifenbereich dieser Option steuert **async-Fixtures**. Die
        Suite hat keine, also aendert der Wert nichts."""
        import ast

        gefunden: list[str] = []
        for quelle in self._testquellen():
            baum = ast.parse(quelle.read_text(encoding="utf-8"))
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.AsyncFunctionDef):
                    continue
                schmuck = " ".join(ast.unparse(d) for d in knoten.decorator_list)
                if "fixture" in schmuck:
                    gefunden.append(f"{quelle.name}:{knoten.name}")

        assert gefunden == [], (
            "async-Fixtures gefunden - dann ist der Schleifenbereich keine "
            f"Formalie mehr und gehoert nachgemessen: {gefunden}"
        )


class TestDieUntergrenzenSindDerGrund:
    def test_die_werkzeuge_sind_nur_nach_unten_begrenzt(self) -> None:
        """Was den Bruch moeglich gemacht hat, und es steht hier als Befund,
        nicht als Behebung: Ob dieses Projekt seine Werkzeuge festnagelt, ist
        eine Entscheidung mit Folgen fuer jede kuenftige Umgebung."""
        with (WURZEL / "pyproject.toml").open("rb") as datei:
            daten = tomllib.load(datei)
        dev = daten["project"]["optional-dependencies"]["dev"]

        ohne_obergrenze = [e for e in dev if "<" not in e]

        assert "pytest-asyncio>=0.23" in dev
        assert len(ohne_obergrenze) == len(dev), "jetzt gibt es Obergrenzen"

    def test_der_eintrag_nennt_die_entscheidung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 427)

        assert "Untergrenzen" in eintrag.ergebnis
        assert "beim Nutzer" in eintrag.ergebnis


class TestDieSuiteLaeuftWieder:
    def test_pytest_kommt_durch_die_konfiguration(self) -> None:
        """Der eigentliche Beleg: ein Sammellauf, der nichts ausfuehrt. Er
        faellt genau dann, wenn 'pytest_configure' wieder abbricht."""
        lauf = subprocess.run(
            [
                str(WURZEL / ".venv/bin/python"),
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-p",
                "no:randomly",
                "tests/test_werkzeugstand.py",
            ],
            capture_output=True,
            text=True,
            cwd=WURZEL,
        )

        assert "INTERNALERROR" not in lauf.stdout + lauf.stderr
        assert lauf.returncode == 0, lauf.stdout[-400:] + lauf.stderr[-400:]


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_den_abbruch(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 427)

        assert "INTERNALERROR" in eintrag.ergebnis
        assert "kein Testergebnis war falsch" in eintrag.ergebnis

    def test_und_den_verlust_der_unkommittierten_arbeit(self) -> None:
        """Der eigene Fehler dazu - zwei Befunde lagen fertig im Baum und
        sind mit dem Container gegangen."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 427)

        assert "unkommittiert" in eintrag.ergebnis

    def test_und_426_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 426).zuletzt == 427


def _eigener_scope(schmuck: str) -> bool:
    """Ist dieser Dekorator eine Fixture mit eigenem Scope?

    Eigene Funktion, damit die Gegenprobe die **Entscheidung** pruefen kann
    und nicht die Zitierweise von ``ast.unparse`` - mein erster Anlauf
    verglich gegen 'scope="module"' und fiel, weil ``unparse`` auf einfache
    Anfuehrungszeichen normalisiert.
    """
    if "fixture" not in schmuck or "scope=" not in schmuck:
        return False
    return not any(f"scope={z}function{z}" in schmuck for z in ("'", '"'))


class TestKeineFixtureMitEigenemScopeInEinerKlasse:
    """Befund 429, und es ist das dritte Mal.

    Eine Fixture mit eigenem Scope, die als Instanzmethode in einer Klasse
    steht, laeuft hier nicht: pytest bricht mit einem Fixture-Fehler ab, und
    die Tests, die sie benutzen, laufen **gar nicht** - sie erscheinen als
    ERROR, nicht als FAILED. In 426 und 428 hat mich das je einen Anlauf
    gekostet, in 429 ist es in einen gepushten Commit gelangt, weil die
    betroffenen Tests die Marke ``daten`` tragen und in der Auswahl
    ``-m "not daten"`` gar nicht vorkommen.

    Ein Registereintrag hat es dreimal nicht verhindert. Also eine Wache.
    """

    def _gefunden(self) -> list[str]:
        import ast

        treffer: list[str] = []
        for pfad in sorted((WURZEL / "tests").glob("test_*.py")):
            baum = ast.parse(pfad.read_text(encoding="utf-8"))
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.ClassDef):
                    continue
                for glied in knoten.body:
                    if not isinstance(
                        glied, ast.FunctionDef | ast.AsyncFunctionDef
                    ):
                        continue
                    for schmuck in glied.decorator_list:
                        text = ast.unparse(schmuck)
                        if _eigener_scope(text):
                            treffer.append(
                                f"{pfad.name}:{knoten.name}.{glied.name} {text}"
                            )
        return treffer

    def test_es_gibt_keine(self) -> None:
        offen = self._gefunden()

        assert offen == [], (
            "Fixture mit eigenem Scope als Instanzmethode - gehoert auf "
            f"Modulebene, sonst laufen die Tests daran nicht: {offen}"
        )

    def test_die_wache_erkennt_den_eigenen_scope(self) -> None:
        """Gegenprobe. Eine Wache, die nichts mehr findet, ist gruen und
        leer - dieselbe Pruefung wie in ``test_wachenaudit``. Geprueft wird
        die Entscheidung, in **beiden** Zitierweisen."""
        assert _eigener_scope('pytest.fixture(scope="module")')
        assert _eigener_scope("pytest.fixture(scope='module')")
        assert _eigener_scope("pytest.fixture(scope='class')")

    def test_und_laesst_das_richtige_stehen(self) -> None:
        """Ohne Scope ist es die Vorgabe 'function' und in einer Klasse
        erlaubt - dieses Projekt hat Dutzende davon."""
        assert not _eigener_scope("pytest.fixture")
        assert not _eigener_scope("pytest.fixture()")
        assert not _eigener_scope('pytest.fixture(scope="function")')
        assert not _eigener_scope("pytest.fixture(scope='function')")
        assert not _eigener_scope("staticmethod")

    def test_und_laesst_eine_auf_modulebene_stehen(self) -> None:
        """``rohreihen`` und ``feinreihe`` stehen genau so da und sind
        richtig - die Wache darf sie nicht treffen."""
        offen = " ".join(self._gefunden())

        assert "rohreihen" not in offen
        assert "feinreihe" not in offen
