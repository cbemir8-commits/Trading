"""Die Zahlen, auf denen die Entscheidungen stehen - Befund 380.

Der Stand des Projekts ist: Alles Messbare ist gemessen, was bleibt, sind
Entscheidungen. Damit ist das Entscheidungsmaterial selbst das teuerste Stueck
Text im Register - eine veraltete Zahl dort kostet eine echte Wahl.

Die Waechter daneben pruefen **Form**: dass jede Entscheidung eine Fundstelle
im Laborbuch hat (``test_entscheidung.py``), dass sie Suchbegriffe traegt
(``test_entscheidungswache.py``), dass alle drei Texte da sind. Die **Zahlen**
waren bis auf eine ungeprueft, und zwei waren ueberholt:

* Entscheidung 69/340 schloss mit *"zu entscheiden ist also nicht 'Messung
  statt Annahme', sondern nur, ob das Verzeichnis kuenftig jeden Versuch
  mitschreibt."* Seit Befund 377 schreibt **jeder** zaehlende Befehl mit. Die
  Frage war beantwortet und stand weiter als offen da.
* Entscheidung 96/339 stuetzt ihr Gegenargument auf *"alle 45 Eintraege der
  Bestenliste"*. Befund 349 hat die Liste gezaehlt: **141**. Das Gegenargument
  ist damit schwerer, nicht leichter.

Was diese Datei tut
-------------------
Sie bindet die beiden Stellen an eine Messung statt an gute Absicht. Die
Verzeichnis-Frage wird **gegen den Quelltext** geprueft, nicht gegen einen
Wortlaut: Sagen die Befehle das eine und das Register das andere, faellt der
Test - in beide Richtungen. Wer Befund 377 zurueckdreht, bekommt hier gesagt,
dass das Register dann auch wieder falsch ist.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest

from research.stand import BEHOBEN, ENTSCHEIDUNGEN, GESCHLOSSEN, OFFEN

#: Befehle, die den Versuchszaehler fortschreiben. Dieselbe Liste wie in
#: ``test_grundstock_waechst.py``, hier aber fuer die Frage, ob das Register
#: die Wahrheit ueber sie sagt.
ZAEHLENDE = (
    "adaptiv",
    "korb",
    "landschaft",
    "machbarkeit",
    "research",
    "verbund",
    "wettbewerb",
)

#: Die gemessene Laenge der Bestenliste (Befund 349). **Nicht** in diesem Klon
#: nachmessbar: ``state/leaderboard.json`` ist maschinenspezifisch und nicht
#: eingecheckt (nur ``state/trials.json`` ist ausgenommen, Befund 73).
BESTENLISTE = 141


def _entscheidung(befund: int):
    return next(e for e in ENTSCHEIDUNGEN if e.befund == befund)


def _schreibt_nachweise(befehl: str) -> bool:
    import cli

    quelle = inspect.getsource(getattr(cli, befehl))
    rufe = {
        getattr(k.func, "id", None) or getattr(k.func, "attr", None)
        for k in ast.walk(ast.parse(quelle.lstrip()))
        if isinstance(k, ast.Call)
    }
    return "_verzeichne" in rufe


class TestDieVerzeichnisFrageIstBeantwortet:
    """**Gegen den Quelltext geprueft**, nicht gegen einen Wortlaut."""

    def test_jeder_zaehlende_befehl_schreibt_nachweise(self) -> None:
        ohne = [b for b in ZAEHLENDE if not _schreibt_nachweise(b)]

        assert ohne == [], f"bucht ohne Einzelnachweis: {ohne}"

    def test_und_das_register_sagt_es(self) -> None:
        """Die Kopplung. Faellt dieser Test, ist eines von beiden falsch - und
        welches, sagt der Test darueber.
        """
        text = _entscheidung(69).warum

        if all(_schreibt_nachweise(b) for b in ZAEHLENDE):
            assert "seit 377 erledigt" in text, (
                "alle Befehle schreiben mit, das Register nennt die Frage aber "
                "noch offen"
            )
        else:
            assert "seit 377 erledigt" not in text

    def test_die_offene_haelfte_steht_mit_ihren_zahlen_da(self) -> None:
        """Beantwortet heisst nicht erledigt: Offen ist, ob das Budget steigt,
        und das ist seit Befund 378/379 gerechnet."""
        text = _entscheidung(69).warum

        assert "1.217" in text
        assert "2.814" in text
        assert "27" in text
        assert "ob das Budget dafuer steigt" in text


class TestDieBestenlisteWirdNurEinmalGezaehlt:
    """Zwei Zahlen fuer dieselbe Liste sind eine zu viel."""

    @staticmethod
    def _stellen() -> list[tuple[str, str]]:
        muster = re.compile(r"(\d+)\s+Eintraege(?:n)?\s+der\s+Bestenliste")
        gefunden: list[tuple[str, str]] = []
        for menge in (BEHOBEN, GESCHLOSSEN, OFFEN):
            for r in menge:
                for m in muster.finditer(r.ergebnis):
                    gefunden.append((f"Befund {r.befund}", m.group(1)))
        for e in ENTSCHEIDUNGEN:
            for feld in (e.zahl, e.warum):
                for m in muster.finditer(feld):
                    gefunden.append((f"Entscheidung {e.befund}", m.group(1)))
        return gefunden

    def test_eine_alte_zahl_steht_nie_allein(self) -> None:
        """Die 45 darf bleiben - sie war einmal richtig. Sie darf nur nicht
        ohne die gemessene 141 dastehen, sonst entscheidet jemand auf einem
        Drittel des Gegenarguments.
        """
        for ort, zahl in self._stellen():
            if int(zahl) == BESTENLISTE:
                continue
            quelle = (
                _entscheidung(96).warum
                if ort.startswith("Entscheidung")
                else next(
                    r.ergebnis
                    for menge in (BEHOBEN, GESCHLOSSEN, OFFEN)
                    for r in menge
                    if f"Befund {r.befund}" == ort
                )
            )
            assert str(BESTENLISTE) in quelle, (
                f"{ort} nennt {zahl} Eintraege ohne die gemessenen "
                f"{BESTENLISTE} daneben"
            )

    def test_die_berichtigung_sagt_woher_die_zahl_kommt(self) -> None:
        """Nicht hier nachgemessen, sondern aus Befund 349 uebernommen - und
        das gehoert dazu, weil 'state/' nicht eingecheckt ist."""
        text = _entscheidung(96).warum

        assert "141" in text
        assert "349" in text
        assert "nicht eingecheckt" in text

    def test_und_die_datei_fehlt_hier_wirklich(self) -> None:
        """Die Begruendung fuer 'nicht nachgemessen' ist selbst geprueft.

        Steht die Datei eines Tages im Klon, soll dieser Test auffallen -
        dann ist die Zahl nachmessbar und der Vermerk ueberholt.
        """
        assert not (Path("state") / "leaderboard.json").exists()
        assert (Path("state") / "trials.json").exists()


class TestDerZaehlerstandDerEntscheidung:
    """Die Kopfzahl von Entscheidung 69, an die Akte gebunden."""

    def test_versuche_und_punkte_stimmen(self) -> None:
        from research.admission import load_trials
        from research.streuung import sammle

        versuche = load_trials(Path("state/trials.json"))
        punkte = sammle(
            berichte=Path("reports"),
            bestenliste=Path("state/leaderboard.json"),
            verzeichnis=Path("state/trials.json"),
        )

        assert versuche == 203
        assert len(punkte) == 61
        assert f"Von {versuche} Versuchen liegen {len(punkte)} vor" in (
            _entscheidung(69).zahl
        )

    def test_die_abdeckung_wird_auf_dreissig_prozent_gerundet(self) -> None:
        from research.admission import load_trials
        from research.streuung import Streuung, sammle

        lage = Streuung(
            punkte=sammle(
                berichte=Path("reports"),
                bestenliste=Path("state/leaderboard.json"),
                verzeichnis=Path("state/trials.json"),
            ),
            versuche=load_trials(Path("state/trials.json")),
            stichprobe=115,
        )

        assert f"{lage.abdeckung:.0%}" == "30%"
        assert "(30 %)" in _entscheidung(69).zahl


class TestWarumDieseDateiUeberhauptNoetigIst:
    def test_die_formwaechter_pruefen_keine_zahlen(self) -> None:
        """Belegt statt behauptet: Die beiden Nachbardateien kennen die
        Register-Zahlen nicht, sonst waere diese hier doppelt.

        Eine Ausnahme ist benannt und bleibt dort - die KI-Entscheidung nennt
        die heutige Latte, und ein Test dort prueft sie.
        """
        nachbarn = (
            Path("tests/test_entscheidung.py").read_text(encoding="utf-8"),
            Path("tests/test_entscheidungswache.py").read_text(encoding="utf-8"),
        )

        for text in nachbarn:
            assert "load_trials" not in text
            assert "sammle(" not in text

    @pytest.mark.parametrize("befund", [69, 96])
    def test_beide_stellen_tragen_ihre_fundstelle(self, befund: int) -> None:
        """Eine Berichtigung ohne Fundstelle waere wieder gepflegte Prosa."""
        assert "380" in _entscheidung(befund).warum

    def test_nur_eine_der_beiden_wurde_hier_nachgemessen(self) -> None:
        """``zuletzt`` heisst "wo zuletzt **gemessen**" (Befund 130) - und das
        trifft nur auf eine der beiden zu.

        Bei 69 ist es gemessen: Der Quelltext sagt, dass jeder zaehlende
        Befehl mitschreibt, und die 1.217 gegen 27 sind in 378/379 gerechnet.
        Bei 96 ist es **uebernommen**: Die 141 stehen seit Befund 349 da, die
        Datei fehlt in diesem Klon, und ich habe sie nicht nachgezaehlt.
        ``zuletzt`` auf 380 zu heben waere dort eine Messung behauptet, die
        nicht stattgefunden hat.
        """
        assert _entscheidung(69).zuletzt == 380
        assert _entscheidung(96).zuletzt == 339
        assert "aus 349 uebernommen" in _entscheidung(96).warum
