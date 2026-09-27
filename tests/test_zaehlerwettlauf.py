"""Zwei Forschungslaeufe verlieren Versuche - Befund 354.

Der Versuchszaehler steuert die Haerte des Deflated-Sharpe-Gates. Er liegt in
**einer** Datei, ``state/trials.json``, und ein Wettbewerb liest ihn am Anfang
und schreibt ihn am Ende - dazwischen liegen Stunden. Zwei Laeufe, die beide bei
203 anfangen, melden 208 und 210.

Gemessen, in beiden Reihenfolgen:

    A (5) vor B (7)   Zaehler 210, richtig waeren 215   -> 5 Versuche weg
    B (7) vor A (5)   Zaehler 210, richtig waeren 215   -> 5 Versuche weg

Und bei den Einzelnachweisen ist es schlimmer als eine Zahl: Die zwei
Nachweise des ersten Laufs sind **weg**, samt Herkunft. Genau die Herkunft, die
in Befund 234 offen steht (192 von 203 Versuchen ohne).

Was fuenf verlorene Versuche wert sind
--------------------------------------
Gerechnet mit den Zahlen des Bestands (n_eff 115, Guete je Trade 0,2708) **und
seinen gemessenen Momenten** - mit den Vorgaben kommt eine andere Kurve heraus,
und daran ist die erste Fassung dieser Zahlen gescheitert (Befund 355):

    203 Versuche   noetige Guete 0,3374
    210 Versuche   noetige Guete 0,3383
    215 Versuche   noetige Guete 0,3389

Die Latte liegt also 0,0006 Guetepunkte tiefer - **0,92 % der Luecke**. Klein,
und trotzdem in die eine Richtung, die dieses Projekt nicht geht: Ein zu tiefer
Zaehler macht die Mehrfachtest-Korrektur milder. ``save_trials`` wusste das
schon, seine eigene Meldung sagt es beim abgewiesenen fallenden Zaehler.

Warum die Tests nicht um einen Wettlauf herumgebaut sind
--------------------------------------------------------
Acht Prozesse gleichzeitig starten und hoffen, dass sie sich treffen, war der
erste Versuch: Ohne Sperre gingen **keine** Nachweise verloren, weil der
Startaufwand von Python groesser ist als das Lesen und Schreiben von wenigen
Kilobyte. Ein Test, der den Fehler nicht zeigt, prueft nichts.

Deshalb steht hier beides deterministisch: das Verschraenken von Hand - das
genau die echte Zeitfolge nachbildet, Lesen am Anfang, Schreiben Stunden
spaeter - und die Eigenschaft der Sperre, dass der Griff **nicht** aufgeteilt
werden kann, gegen einen echten zweiten Prozess.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.dateisperre import NichtZuSperren, gesperrt
from research.admission import load_trials, save_trials
from research.versuche import Versuch, anhaengen, laden, speichern

#: Wie lange auf einen Kindprozess gewartet wird, in Sekunden.
GEDULD = 30.0

#: Eine leere Zaehlerdatei im Format von ``research.versuche``.
LEER: dict = {"format": 1, "trials": 0, "grundstock": 0, "versuche": []}


def _datei(pfad: Path, trials: int = 203) -> Path:
    pfad.write_text(
        json.dumps({**LEER, "trials": trials, "grundstock": trials})
    )
    return pfad


def _versuch(kennung: str) -> Versuch:
    return Versuch(kennung=kennung, herkunft="wettlauf", zeitpunkt="2026-09-27")


class TestDerFundSelbst:
    """**Die Messung.** Ohne Sperre, von Hand verschraenkt - so, wie die echte
    Zeitfolge es tut."""

    @pytest.mark.parametrize(("erst", "zweit"), [(5, 7), (7, 5)])
    def test_der_zaehler_verliert_die_versuche_des_einen(
        self, tmp_path: Path, erst: int, zweit: int
    ) -> None:
        pfad = _datei(tmp_path / "trials.json")
        stand = load_trials(pfad)

        # Beide Laeufe lesen denselben Stand - so faengt ein Wettbewerb an.
        a, b = stand, stand
        save_trials(pfad, a + erst)
        save_trials(pfad, b + zweit)

        assert load_trials(pfad) == stand + max(erst, zweit)
        assert load_trials(pfad) < stand + erst + zweit

    def test_und_die_einzelnachweise_sind_ganz_weg(self, tmp_path: Path) -> None:
        """Nicht nur die Zahl - die Herkunft. Und die ist das, was in Befund 234
        offen steht."""
        pfad = _datei(tmp_path / "trials.json", trials=0)

        a = laden(pfad).erweitert([_versuch("A1"), _versuch("A2")])
        b = laden(pfad).erweitert([_versuch("B1"), _versuch("B2"), _versuch("B3")])
        speichern(pfad, a)
        speichern(pfad, b)

        namen = {e.kennung for e in laden(pfad).eintraege}
        assert namen == {"B1", "B2", "B3"}
        assert "A1" not in namen

    def test_was_fuenf_verlorene_versuche_an_der_latte_aendern(self) -> None:
        """**Die Zahl zum Fund**, und sie kommt vom Betriebspunkt.

        Hier stand sie zuerst von Hand gerechnet, mit den Vorgabemomenten -
        und war dadurch falsch (Befund 355). ``SPOTPUNKT.noetige_guete``
        nimmt die gemessenen.
        """
        from research.referenz import SPOTPUNKT

        richtig = SPOTPUNKT.noetige_guete(versuche=215)
        zu_tief = SPOTPUNKT.noetige_guete(versuche=210)

        assert zu_tief < richtig, "ein zu tiefer Zaehler senkt die Latte"
        assert (richtig - zu_tief) == pytest.approx(0.0006, abs=0.0002)
        assert (richtig - zu_tief) / SPOTPUNKT.gueteluecke(versuche=215) == (
            pytest.approx(0.0092, abs=0.002)
        )


class TestDerGriffLaesstSichNichtTeilen:
    """Die Eigenschaft, auf die es ankommt: ``anhaengen`` und ``save_trials``
    halten die Sperre ueber **Lesen und Schreiben**, nicht nur ueber das
    Schreiben."""

    def test_anhaengen_kommt_nicht_dazwischen(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("core.dateisperre.GEDULD", 0.2)
        pfad = _datei(tmp_path / "trials.json", trials=0)

        with gesperrt(pfad), pytest.raises(NichtZuSperren):
            anhaengen(pfad, [_versuch("A1")])

    def test_save_trials_auch_nicht(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("core.dateisperre.GEDULD", 0.2)
        pfad = _datei(tmp_path / "trials.json")

        with gesperrt(pfad), pytest.raises(NichtZuSperren):
            save_trials(pfad, 208)

    def test_und_danach_geht_es_wieder(self, tmp_path: Path) -> None:
        pfad = _datei(tmp_path / "trials.json", trials=0)

        with gesperrt(pfad):
            pass
        verzeichnis = anhaengen(pfad, [_versuch("A1")])

        assert verzeichnis.anzahl == 1

    def test_gegen_einen_echten_zweiten_prozess(self, tmp_path: Path) -> None:
        """**Im selben Prozess bewiesen ist nicht bewiesen.** Die Sperre kommt
        vom Kern, und der unterscheidet Prozesse."""
        pfad = _datei(tmp_path / "trials.json", trials=0)
        quelle = (
            "import sys, time;"
            f"sys.path.insert(0, {str(Path.cwd())!r});"
            "from core.dateisperre import gesperrt;"
            f"ctx = gesperrt({str(pfad)!r});"
            "ctx.__enter__();"
            "print('gehalten', flush=True);"
            "time.sleep(300)"
        )
        halter = subprocess.Popen(
            [sys.executable, "-c", quelle], stdout=subprocess.PIPE, text=True
        )
        try:
            frist = time.monotonic() + GEDULD
            while time.monotonic() < frist:
                if halter.stdout.readline().strip() == "gehalten":
                    break
            else:  # pragma: no cover - der Halter ist nicht hochgekommen
                raise AssertionError("Der haltende Prozess hat sich nicht gemeldet")

            with pytest.raises(NichtZuSperren):
                anhaengen(pfad, [_versuch("A1")])
        finally:
            halter.kill()
            halter.wait(timeout=GEDULD)

        # Und nach seinem Ende - ohne Aufraeumen, wie nach einem Absturz.
        frist = time.monotonic() + GEDULD
        while time.monotonic() < frist:
            try:
                anhaengen(pfad, [_versuch("A1")])
            except NichtZuSperren:  # pragma: no cover - Zeitfenster
                time.sleep(0.05)
                continue
            assert laden(pfad).anzahl == 1
            return
        raise AssertionError("Nach dem Absturz blieb der Zaehler gesperrt")


class TestDieEigenenVersucheGehenNichtVerloren:
    """``neue`` mitgeben heisst: umbuchen statt verwerfen."""

    def test_der_vorgefundene_stand_bekommt_sie_obendrauf(
        self, tmp_path: Path
    ) -> None:
        pfad = _datei(tmp_path / "trials.json")

        # Ein anderer Lauf war schneller und hat sieben gebucht.
        save_trials(pfad, 210)
        # Unser Lauf hatte bei 203 angefangen und fuenf geprueft.
        save_trials(pfad, 208, neue=5)

        assert load_trials(pfad) == 215

    def test_ohne_neue_bleibt_es_beim_alten_verhalten(self, tmp_path: Path) -> None:
        """Die Abweisung ist die Vorgabe: Ein Aufrufer, der seine Zahl nicht
        kennt, soll keine erfinden."""
        pfad = _datei(tmp_path / "trials.json")
        save_trials(pfad, 210)

        save_trials(pfad, 208)

        assert load_trials(pfad) == 210

    def test_ein_steigender_stand_wird_normal_geschrieben(
        self, tmp_path: Path
    ) -> None:
        """Der Normalfall darf durch ``neue`` nicht anders werden: Kein anderer
        Lauf war da, also gilt die gemeldete Summe."""
        pfad = _datei(tmp_path / "trials.json")

        save_trials(pfad, 208, neue=5)

        assert load_trials(pfad) == 208

    def test_dasselbe_zweimal_zaehlt_nicht_doppelt(self, tmp_path: Path) -> None:
        """Ohne fremde Bewegung ist die Buchung wiederholungsfest."""
        pfad = _datei(tmp_path / "trials.json")

        save_trials(pfad, 208, neue=5)
        save_trials(pfad, 208, neue=5)

        assert load_trials(pfad) == 208

    def test_die_einzelnachweise_bleiben_unberuehrt(self, tmp_path: Path) -> None:
        """``save_trials`` schreibt die Summe; die Nachweise kommen aus
        ``anhaengen`` und duerfen dabei nicht verschwinden."""
        pfad = _datei(tmp_path / "trials.json", trials=0)
        anhaengen(pfad, [_versuch("A1"), _versuch("A2")])

        save_trials(pfad, 9, neue=7)

        assert load_trials(pfad) == 9
        assert {e.kennung for e in laden(pfad).eintraege} == {"A1", "A2"}


class TestDerWettbewerbGibtSeineZahlMit:
    """Gebaut **und** angeschlossen - die Bauart aus Befund 351."""

    @staticmethod
    def _quelle() -> str:
        return Path("cli.py").read_text(encoding="utf-8")

    def test_jeder_aufruf_nennt_neue(self) -> None:
        import ast

        quelle = self._quelle()
        baum = ast.parse(quelle)
        ohne = []
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            name = getattr(knoten.func, "id", None) or getattr(
                knoten.func, "attr", None
            )
            if name != "save_trials":
                continue
            if not any(w.arg == "neue" for w in knoten.keywords):
                ohne.append(ast.unparse(knoten))

        assert ohne == [], f"save_trials ohne 'neue': {ohne}"

    def test_und_die_zahl_ist_der_zuwachs_des_laufs(self) -> None:
        quelle = self._quelle()

        assert "neue=report.trials_after - trials_before" in quelle
        assert "neue=1" in quelle


class TestDasRegisterHaeltDenFund:
    def test_er_steht_unter_behoben(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 354)

        assert "0,92" in eintrag.ergebnis, "die gemessene Groesse fehlt"
        assert "Einzelnachweise" in eintrag.ergebnis or (
            "Nachweise" in eintrag.ergebnis
        ), "der schlimmere Teil fehlt"
