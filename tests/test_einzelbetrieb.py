"""Zwei Handelslaeufe auf einem Konto loeschen den Kill-Switch - Befund 353.

``cli trade`` legt seinen Risikozustand unter ``state/risk.json`` ab, und der
Pfad haengt **nicht** am Symbol. Zwei Laeufe teilen sich die Datei; jeder haelt
seinen eigenen Zustand im Speicher und schreibt ihn beim Speichern ganz.

Der erste Test dieser Datei ist die Messung dazu - mit zwei echten
``RiskOfficer`` und ohne Nachhilfe: Der Kill-Switch springt beim einen und ist
nach dem naechsten Speichern des anderen weg. Das ist die Sperre, die laut
ihrer eigenen Meldung "nur manuell zurueckholbar" ist.

Warum das kein erfundener Fall ist
----------------------------------
Zwei Wege fuehren dorthin. Der eine ist ein zweites Fenster. Der andere ist die
offene Frage aus Befund 263/318: Zugelassen ist der Korb aus BTC und ETH,
``LiveTrader`` handelt ein Symbol, und ``Zulassungsbedingungen.unterdeckung``
sagt dem Nutzer genau das. Zwei Laeufe sind die naheliegende Antwort darauf.

Was die Sperre koennen muss
---------------------------
Sie darf den Neustart nach einem Absturz **nicht** verhindern. ``LiveTrader``
ist darauf gebaut, dass der Prozess jederzeit sterben und wiederkommen darf -
sein Docstring nennt das den Unterschied zwischen Spielzeug und Betrieb. Eine
Sperre, die einen Stromausfall ueberlebt, nimmt genau das.

Deshalb kommt die Aussage vom Kern und nicht von einer gespeicherten PID, und
deshalb steht der Absturz hier als Test mit einem **echten zweiten Prozess**:
Eine Sperre, die nur im selben Prozess geprueft wird, ist nicht geprueft.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from execution.einzelbetrieb import (
    Belegung,
    BereitsInBetrieb,
    belege,
    belegung,
    sperrpfad,
)
from execution.risk import RiskOfficer, TradingState, load_risk_state

#: Wie lange auf einen Kindprozess gewartet wird, in Sekunden.
#:
#: Grosszuegig: Ein Test, der auf einer langsamen Maschine zufaellig
#: fehlschlaegt, wird abgeschaltet und schuetzt dann nichts mehr.
GEDULD = 30.0


def _instrument(symbol: str):
    import cli

    return cli._fallback_instrument(symbol)


def _officer(pfad: Path, symbol: str) -> RiskOfficer:
    from core.config import RiskSettings

    return RiskOfficer(RiskSettings(), _instrument(symbol), state_path=pfad)


class TestDerFundSelbst:
    """**Die Messung**, nicht die Behauptung."""

    def test_der_zweite_lauf_loescht_den_kill_switch(self, tmp_path: Path) -> None:
        pfad = tmp_path / "risk.json"
        btc = _officer(pfad, "BTCUSDT")
        eth = _officer(pfad, "ETHUSDT")
        for officer in (btc, eth):
            officer.observe_equity(Decimal("500"))
            officer.save()

        # Das BTC-Bein faehrt das Konto 20 % unter den Hoechststand.
        btc.observe_equity(Decimal("400"))
        btc.save()
        assert btc.state.trading_state is TradingState.KILLED
        assert json.loads(pfad.read_text())["trading_state"] == "killed"

        # Das ETH-Bein hat seinen Zustand beim Start gelesen und weiss nichts.
        assert eth.state.trading_state is TradingState.ACTIVE
        eth.observe_equity(Decimal("500"))
        eth.save()

        assert json.loads(pfad.read_text())["trading_state"] == "active"
        assert load_risk_state(pfad).trading_state is TradingState.ACTIVE

    def test_und_der_grund_steht_danach_leer_da(self, tmp_path: Path) -> None:
        """Nicht nur der Zustand geht verloren, auch die Begruendung - es bleibt
        keine Spur, an der jemand es merken koennte."""
        pfad = tmp_path / "risk.json"
        btc = _officer(pfad, "BTCUSDT")
        eth = _officer(pfad, "ETHUSDT")
        btc.observe_equity(Decimal("500"))
        btc.observe_equity(Decimal("400"))
        btc.save()
        assert json.loads(pfad.read_text())["kill_reason"]

        eth.observe_equity(Decimal("500"))
        eth.save()

        assert json.loads(pfad.read_text())["kill_reason"] == ""


class TestDieSperreHaelt:
    def test_ein_zweiter_lauf_wird_abgelehnt(self, tmp_path: Path) -> None:
        pfad = tmp_path / "risk.json"

        with belege(pfad, symbol="BTCUSDT"), pytest.raises(BereitsInBetrieb):
            belege(pfad, symbol="ETHUSDT")

    def test_die_meldung_nennt_die_gemessene_folge(self, tmp_path: Path) -> None:
        """**Ein Verbot ohne Begruendung wird umgangen.** Wer liest, dass der
        Kill-Switch dabei verschwindet, tut es nicht."""
        pfad = tmp_path / "risk.json"

        with belege(pfad, symbol="BTCUSDT"), pytest.raises(BereitsInBetrieb) as fehler:
            belege(pfad, symbol="ETHUSDT")

        text = str(fehler.value)
        assert "Kill-Switch" in text
        assert "ueberschrieben" in text
        assert "BTCUSDT" in text, "sagt nicht, wer laeuft"
        assert "PATHS__STATE" in text, "nennt den Ausweg nicht"
        assert "je Bein" in text, "nennt den Preis des Auswegs nicht"

    def test_nach_der_freigabe_geht_es_wieder(self, tmp_path: Path) -> None:
        pfad = tmp_path / "risk.json"

        erst = belege(pfad, symbol="BTCUSDT")
        erst.gib_frei()
        zweit = belege(pfad, symbol="ETHUSDT")

        assert belegung(pfad).symbol == "ETHUSDT"
        zweit.gib_frei()

    def test_freigeben_ist_mehrfach_erlaubt(self, tmp_path: Path) -> None:
        """Ein ``finally`` neben einem ``with`` soll nicht davon abhaengen, wer
        zuerst dran war."""
        betrieb = belege(tmp_path / "risk.json", symbol="BTCUSDT")

        betrieb.gib_frei()
        betrieb.gib_frei()

    def test_zwei_konten_stoeren_sich_nicht(self, tmp_path: Path) -> None:
        """Der Ausweg aus der Meldung muss funktionieren: eigene Ablage, eigene
        Sperre."""
        eins = belege(tmp_path / "a" / "risk.json", symbol="BTCUSDT")
        zwei = belege(tmp_path / "b" / "risk.json", symbol="ETHUSDT")

        assert eins.eigen.symbol == "BTCUSDT"
        assert zwei.eigen.symbol == "ETHUSDT"
        eins.gib_frei()
        zwei.gib_frei()


class TestDerNeustartNachDemAbsturz:
    """**Mit einem echten zweiten Prozess.** Eine Sperre, die nur im selben
    Prozess geprueft wird, ist nicht geprueft: Sie kommt vom Kern, und der
    unterscheidet Prozesse, keine Objekte.
    """

    @staticmethod
    def _halter(pfad: Path) -> subprocess.Popen:
        """Ein Prozess, der die Sperre haelt und dann wartet."""
        quelle = (
            "import sys, time;"
            f"sys.path.insert(0, {str(Path.cwd())!r});"
            "from execution.einzelbetrieb import belege;"
            f"belege({str(pfad)!r}, symbol='BTCUSDT');"
            "print('gehalten', flush=True);"
            "time.sleep(300)"
        )
        prozess = subprocess.Popen(
            [sys.executable, "-c", quelle], stdout=subprocess.PIPE, text=True
        )
        frist = time.monotonic() + GEDULD
        while time.monotonic() < frist:
            zeile = prozess.stdout.readline()
            if zeile.strip() == "gehalten":
                return prozess
            if not zeile:  # pragma: no cover - der Prozess ist gestorben
                break
        prozess.kill()
        raise AssertionError("Der haltende Prozess hat sich nicht gemeldet")

    def test_solange_er_lebt_kommt_keiner_dazu(self, tmp_path: Path) -> None:
        pfad = tmp_path / "risk.json"
        halter = self._halter(pfad)
        try:
            with pytest.raises(BereitsInBetrieb):
                belege(pfad, symbol="ETHUSDT")
        finally:
            halter.kill()
            halter.wait(timeout=GEDULD)

    def test_und_danach_laesst_sich_neu_starten(self, tmp_path: Path) -> None:
        """**Der wichtigere Teil.** Ein Handelslauf, der nach einem
        Stromausfall nicht mehr startet, ist schlimmer als zwei Laeufe."""
        pfad = tmp_path / "risk.json"
        halter = self._halter(pfad)
        halter.kill()
        halter.wait(timeout=GEDULD)

        frist = time.monotonic() + GEDULD
        letzter: BereitsInBetrieb | None = None
        while time.monotonic() < frist:
            try:
                neu = belege(pfad, symbol="BTCUSDT")
            except BereitsInBetrieb as fehler:  # pragma: no cover - Zeitfenster
                letzter = fehler
                time.sleep(0.05)
                continue
            neu.gib_frei()
            return
        raise AssertionError(f"Neustart blieb gesperrt: {letzter}")

    def test_die_auskunft_bleibt_liegen_und_das_ist_kein_urteil(
        self, tmp_path: Path
    ) -> None:
        """Die Datei sagt nach einem Absturz weiter, wer lief. Sie ist Auskunft
        fuer die Meldung - ob der Lauf lebt, sagt allein der Kern."""
        pfad = tmp_path / "risk.json"
        halter = self._halter(pfad)
        halter.kill()
        halter.wait(timeout=GEDULD)

        assert sperrpfad(pfad).exists()
        assert belegung(pfad).symbol == "BTCUSDT"


class TestDieSperreGehoertDemProzess:
    """**Ein Fund beim Messen** (Befund 353). Ohne ein Verzeichnis der
    gehaltenen Sperren haengt die Sperre daran, dass der Aufrufer das Ergebnis
    festhaelt: Wird es weggeworfen, schliesst das Aufraeumen die Datei, und der
    Kern loest mit dem letzten Dateideskriptor die Sperre. Gemessen mit zwei
    echten Prozessen - der zweite Lauf kam durch, waehrend der erste lief.
    """

    def test_auch_ein_weggeworfenes_ergebnis_haelt(self, tmp_path: Path) -> None:
        import gc

        pfad = tmp_path / "risk.json"
        belege(pfad, symbol="BTCUSDT")  # Rueckgabe absichtlich verworfen.
        gc.collect()

        with pytest.raises(BereitsInBetrieb):
            belege(pfad, symbol="ETHUSDT")

    def test_das_verzeichnis_traegt_die_sperre_aus(self, tmp_path: Path) -> None:
        from execution.einzelbetrieb import _GEHALTEN

        betrieb = belege(tmp_path / "risk.json", symbol="BTCUSDT")
        assert betrieb in _GEHALTEN

        betrieb.gib_frei()

        assert betrieb not in _GEHALTEN


class TestDasRegisterHaeltBeides:
    """Der Fund **und** der Preis, den er der offenen Entscheidung gibt."""

    def test_der_fund_steht_unter_behoben(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 353)

        assert "Kill-Switch" in eintrag.name
        assert "kill_reason" in eintrag.ergebnis, "die gemessene Folge fehlt"
        assert "500 auf 400" in eintrag.ergebnis, "die Messung fehlt"

    def test_die_offene_entscheidung_kennt_den_preis(self) -> None:
        """**Das ist der Nutzen fuer die Frage aus 263/318.** Der Weg "je Bein
        zulassen" ist nicht verboten, sondern bepreist: zwei Ablagen, und die
        Verlustgrenzen gelten dann je Bein.
        """
        from research.stand import OFFEN

        eintrag = next(r for r in OFFEN if r.befund == 263)

        assert "PATHS__STATE" in eintrag.ergebnis
        assert "je Bein statt je Konto" in eintrag.ergebnis
        assert eintrag.massgeblich >= 353


class TestDieAuskunft:
    def test_ohne_datei_gibt_es_keine(self, tmp_path: Path) -> None:
        assert belegung(tmp_path / "risk.json") is None

    def test_unlesbares_gilt_als_keine(self, tmp_path: Path) -> None:
        """Nicht abbrechen: Die Auskunft steht in einer Meldung, und eine
        kaputte Meldung darf den Handel nicht verhindern."""
        pfad = tmp_path / "risk.json"
        sperrpfad(pfad).write_text("{kein json")

        assert belegung(pfad) is None

    def test_der_satz_nennt_symbol_pid_und_zeit(self) -> None:
        satz = Belegung(
            pid=4711, symbol="BTCUSDT", seit=datetime(2026, 9, 27, 15, 3, tzinfo=UTC)
        ).satz()

        assert "BTCUSDT" in satz
        assert "4711" in satz
        assert "2026-09-27 15:03" in satz

    def test_sie_ueberlebt_den_weg_durch_die_datei(self, tmp_path: Path) -> None:
        pfad = tmp_path / "risk.json"
        betrieb = belege(pfad, symbol="ETHUSDT", pid=4711)
        try:
            gelesen = belegung(pfad)
        finally:
            betrieb.gib_frei()

        assert gelesen.pid == 4711
        assert gelesen.symbol == "ETHUSDT"
        assert gelesen.seit is not None

    def test_sie_liegt_neben_dem_zustand_und_nicht_darin(self, tmp_path: Path) -> None:
        """**Sonst haelt sie nichts.** ``RiskOfficer.save`` schreibt in eine
        Nebendatei und ersetzt den Zustand damit; eine Sperre in einer Datei,
        die ersetzt wird, ist nach dem ersten Speichern eine Sperre auf einer
        Datei, die es nicht mehr gibt.
        """
        pfad = tmp_path / "risk.json"

        assert sperrpfad(pfad) != pfad
        assert sperrpfad(pfad).parent == pfad.parent

        betrieb = belege(pfad, symbol="BTCUSDT")
        try:
            officer = _officer(pfad, "BTCUSDT")
            officer.observe_equity(Decimal("500"))
            officer.save()

            assert sperrpfad(pfad).exists(), "das Speichern hat die Sperre verdraengt"
            assert belegung(pfad).symbol == "BTCUSDT"
        finally:
            betrieb.gib_frei()


class TestDerHandelsbefehlNutztSie:
    """Gebaut **und** angeschlossen - die Bauart aus Befund 351."""

    @staticmethod
    def _quelle() -> str:
        import ast

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.FunctionDef) and knoten.name == "trade":
                return ast.unparse(knoten)
        raise AssertionError("'trade' steht nicht mehr in cli.py")

    def test_der_handel_belegt_den_zustand(self) -> None:
        quelle = self._quelle()

        assert "belege(state_path" in quelle
        assert "BereitsInBetrieb" in quelle

    def test_und_gibt_ihn_am_ende_frei(self) -> None:
        quelle = self._quelle()

        assert "gib_frei()" in quelle

    def test_der_trockenlauf_sperrt_nicht(self) -> None:
        """Ein Trockenlauf liest und schreibt nicht. Ihn zu sperren hiesse:
        niemand darf den Plan nachsehen, waehrend das System handelt."""
        quelle = self._quelle()
        stelle = quelle.index("belege(state_path")
        davor = quelle[:stelle]

        assert "if not trocken" in davor

    def test_gesperrt_wird_vor_der_boersenanbindung(self) -> None:
        """Wie beim Kill-Switch darueber: Wer nicht handeln darf, soll sich
        nicht erst anmelden."""
        quelle = self._quelle()

        assert quelle.index("belege(state_path") < quelle.index("get_instrument")
