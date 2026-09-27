"""Die Bestenliste zaehlte uebersprungene Gates mit - Befund 349.

Befund 332 hat ein Verzeichnis der Typen angelegt, die eine Gate-Bilanz tragen
und nicht sagen koennen, ob jedes Gate geurteilt hat. Gesucht wurde nach einem
Feld namens ``bestanden``.

**Sechs Typen tragen dieselbe Bilanz unter anderem Namen** und standen damit nie
im Verzeichnis:

    research.leaderboard.Entry        gates_bestanden / gates_gesamt
    research.rangprobe.Doppel         grob_bestanden / fein_bestanden
    research.admission.Candidate      gates (GateReport)
    research.machbarkeit.Punkt        gates (dict[str, Stand])
    research.koernung.Gatelauf        bestanden als Eigenschaft
    research.aussetzer.Punktlage      zaehlt selbst

Das ist derselbe Stellvertreter-Fehler wie in Befund 333 - eingeteilt nach dem
Namen statt nach der Sache -, nur eine Ebene hoeher: nicht in der Einordnung,
sondern in der **Suche**.

Fuenf der sechs sind gedeckt: ``Doppel.handelt`` nimmt Genome ohne Trades aus
dem Vergleich, ``Stand`` traegt ``uebersprungen``, ``Gatelauf`` ist seit 338
skipbewusst, ``Punktlage`` zaehlt selbst, ``Candidate`` haelt den Bericht.

**Der sechste ist die Bestenliste** - die Liste, auf der das ganze Projekt
rangiert. In ``reports/zulassung`` stehen 141 Eintraege, 22 davon unter 30
Trades und 8 mit null.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from research.leaderboard import Entry

#: Was die gespeicherten Bestenlisten hergeben (Befund 348/349).
EINTRAEGE = 141
UNTER_SCHWELLE = 22
OHNE_HANDEL = 8


def _eintrag(**rest) -> Entry:
    daten = {
        "genome_id": "abc", "name": "Regel", "generation": 9,
        "gates_bestanden": 8, "gates_gesamt": 11,
    }
    daten.update(rest)
    return Entry(**daten)


class TestDerEintragSagtEsJetzt:
    def test_geurteilt_ist_gesamt_ohne_aussetzer(self) -> None:
        assert _eintrag().gates_geurteilt == 11
        assert _eintrag(gates_uebersprungen=3).gates_geurteilt == 8

    def test_ein_aussetzer_zaehlt_nicht_als_bestanden(self) -> None:
        e = _eintrag(gates_uebersprungen=3)

        assert e.gates_bestanden_echt == 5
        assert e.gates_bestanden == 8, "das rohe Paar bleibt erhalten"

    def test_der_vorgabewert_laesst_alte_eintraege_wie_sie_waren(self) -> None:
        """0 heisst "keiner" und bei alten Eintraegen "nicht erhoben" - beides
        ist hier dasselbe, weil eine 0 den Rang nicht veraendert."""
        e = _eintrag()

        assert e.gates_uebersprungen == 0
        assert e.gates_bestanden_echt == e.gates_bestanden
        assert e.gates_geurteilt == e.gates_gesamt

    def test_keine_negativen_zahlen(self) -> None:
        e = _eintrag(gates_bestanden=1, gates_uebersprungen=5)

        assert e.gates_bestanden_echt == 0
        assert _eintrag(gates_gesamt=2, gates_uebersprungen=5).gates_geurteilt == 0


class TestDerRangSchluessel:
    def test_er_rechnet_mit_den_geurteilten(self) -> None:
        """**Die Stelle, an der es zaehlt.** Bei Gleichstand im Deflated Sharpe
        entscheidet die Gate-Zahl."""
        mit = _eintrag(gates_uebersprungen=3)

        assert mit.rang_schluessel[2] == 5

    def test_ohne_aussetzer_bleibt_der_schluessel_wie_vorher(self) -> None:
        assert _eintrag().rang_schluessel[2] == 8

    def test_der_deflated_sharpe_steht_davor(self) -> None:
        """Deshalb ist die Wirkung begrenzt: Wer zu wenige Trades hat, verliert
        den Deflated Sharpe zuerst - und der ist der erste Schluessel nach der
        Zulassung."""
        schluessel = _eintrag(deflated_sharpe=0.5).rang_schluessel

        assert schluessel[1] == 0.5
        assert schluessel.index(0.5) < 2

    def test_eine_regel_ohne_handel_faellt_zurueck(self) -> None:
        """Der Fall aus Befund 322, hier in der Bestenliste: fuenf Gates
        gutgeschrieben, weil nichts schiefgehen kann, wo nichts passiert."""
        ohne = _eintrag(trades=0, gates_bestanden=5, gates_uebersprungen=5)
        echt = _eintrag(trades=302, gates_bestanden=4, gates_uebersprungen=0)

        assert ohne.gates_bestanden > echt.gates_bestanden
        assert ohne.gates_bestanden_echt < echt.gates_bestanden_echt
        assert echt.rang_schluessel > ohne.rang_schluessel


class TestDasFeldWirdGefuellt:
    def test_der_bauer_liest_den_status(self) -> None:
        import ast

        quelle = pathlib.Path("research/leaderboard.py").read_text(encoding="utf-8")
        baum = ast.parse(quelle)
        aus = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "_aus_kandidat"
        )

        assert "gates_uebersprungen=sum(" in aus
        assert "r.status is GateStatus.SKIP" in aus

    def test_die_zusammenfassung_zeigt_das_ehrliche_paar(self) -> None:
        quelle = pathlib.Path("research/leaderboard.py").read_text(encoding="utf-8")

        assert "spitze.gates_bestanden_echt" in quelle
        assert "spitze.gates_geurteilt" in quelle

    def test_das_feld_ueberlebt_speichern_und_laden(self, tmp_path) -> None:
        from dataclasses import asdict

        roh = asdict(_eintrag(gates_uebersprungen=2))
        zurueck = Entry(**roh)

        assert zurueck.gates_uebersprungen == 2
        assert zurueck.gates_bestanden_echt == 6

    def test_alte_dateien_ohne_das_feld_bleiben_lesbar(self) -> None:
        """``Entry(**daten)`` liest die gespeicherte Liste. Ein Pflichtfeld
        haette jeden alten Stand unlesbar gemacht."""
        roh = {
            "genome_id": "abc", "name": "Regel", "generation": 9,
            "gates_bestanden": 8, "gates_gesamt": 11, "trades": 51,
        }

        assert Entry(**roh).gates_uebersprungen == 0


class TestDieSucheFindetJetztAlle:
    def test_bilanzfelder_stehen_als_muster_da(self) -> None:
        from tests.test_gatezahlen import BILANZFELDER

        assert "gates_bestanden" in BILANZFELDER
        assert "grob_bestanden" in BILANZFELDER

    def test_die_bestenliste_ist_eingeordnet(self) -> None:
        from tests.test_gatezahlen import MIT_SKIPINFO

        assert "research.leaderboard.Entry" in MIT_SKIPINFO

    def test_die_rangprobe_ist_vorgelagert(self) -> None:
        """``Doppel.handelt`` nimmt Genome ohne Trades heraus, und ``rangprobe``
        benutzt es auch - also eine Schicht vor der Bilanz."""
        from research.rangprobe import Doppel
        from tests.test_gatezahlen import VORGELAGERT

        assert "research.rangprobe.Doppel" in VORGELAGERT
        assert not Doppel(
            name="x", trades=0, grob_bestanden=5, fein_bestanden=5,
            grob_rueckgang=0.0, fein_rueckgang=0.0,
        ).handelt

    def test_die_vier_ohne_bilanzfeld_sind_benannt(self) -> None:
        from tests.test_gatezahlen import OHNE_BILANZFELD, _traeger

        assert len(OHNE_BILANZFELD) == 4
        assert set(OHNE_BILANZFELD) & set(_traeger()) == set()


class TestDieGespeichertenListen:
    @staticmethod
    def _eintraege() -> list[dict]:
        aus: list[dict] = []
        for f in sorted(pathlib.Path("reports/zulassung").glob("*.json")):
            aus.extend(json.loads(f.read_text()).get("bestenliste") or [])
        return aus

    def test_die_zahlen_stimmen(self) -> None:
        eintraege = self._eintraege()

        assert len(eintraege) == EINTRAEGE
        assert sum(1 for e in eintraege if e.get("trades", 0) < 30) == UNTER_SCHWELLE
        assert sum(1 for e in eintraege if e.get("trades", 0) == 0) == OHNE_HANDEL

    def test_und_keiner_traegt_das_feld(self) -> None:
        """Deshalb war es nicht zu sehen - und deshalb werden die alten
        Dateien nicht angefasst: Ein nachtraeglich eingesetztes Feld waere
        erfunden."""
        assert all("gates_uebersprungen" not in e for e in self._eintraege())


class TestDerRegistereintrag:
    @staticmethod
    def _eintrag():
        from research.stand import OFFEN

        return next(r for r in OFFEN if "Gate-Zahlen" in r.name)

    def test_die_zu_enge_suche_ist_benannt(self) -> None:
        ergebnis = self._eintrag().ergebnis

        assert "Suche selbst war zu eng" in ergebnis
        assert "sechs Typen" in ergebnis

    def test_die_zahlen_der_bestenliste_stehen_drin(self) -> None:
        ergebnis = self._eintrag().ergebnis

        assert "141 Eintraege, 22 unter 30 Trades, 8 mit null" in ergebnis

    def test_die_begrenzte_wirkung_steht_dabei(self) -> None:
        """Nicht groesser gemacht als sie ist: Der Deflated Sharpe steht vor
        der Gate-Zahl."""
        ergebnis = self._eintrag().ergebnis

        assert "Wirkung auf die Rangfolge ist begrenzt" in ergebnis

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 332
        assert eintrag.massgeblich >= 349


@pytest.mark.parametrize(
    "name",
    [
        "research.leaderboard.Entry",
        "research.rangprobe.Doppel",
        "research.admission.Candidate",
        "research.machbarkeit.Punkt",
        "research.koernung.Gatelauf",
        "research.aussetzer.Punktlage",
    ],
)
def test_jeder_der_sechs_ist_irgendwo_eingeordnet(name: str) -> None:
    """**Die Wache ueber die Berichtigung.** Sechs Typen waren unsichtbar;
    keiner darf still bleiben."""
    from tests.test_gatezahlen import (
        MIT_SKIPINFO,
        OFFEN,
        OHNE_BILANZFELD,
        VERZEICHNET,
        VORGELAGERT,
    )

    bekannt = (
        MIT_SKIPINFO
        | set(VERZEICHNET)
        | set(VORGELAGERT)
        | set(OHNE_BILANZFELD)
        | OFFEN
    )

    assert name in bekannt
