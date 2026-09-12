"""Schreiber und Leser des Journals, einmal im Kreis gefahren.

**Befund 261.** Seit Befund 260 ist die Lernschleife an beiden Enden
angeschlossen: ``cli wettbewerb`` schreibt das Journal, und die naechste Runde
laesst die KI daraus lesen. Geprueft war jedes Ende **fuer sich**, mit einem
eigenen Pruefstueck - ``write_journal`` gegen einen erfundenen Bericht,
``build_prompt`` gegen ein von Hand gebautes Journal.

So bleiben beide Tests gruen, wenn die Schluessel auseinanderlaufen. Der
Schreiber legt ``gate_feedback`` ab, der Leser holt ``gate_feedback`` - wuerde
einer von beiden umbenannt, faellt kein Test, und die Schleife liefe leer
weiter. Genau dieselbe Bauart, die dieses Projekt schon in 168, 250 und 258
gefunden hat: zwei Stellen, eine Wahrheit.

Dieser Test faehrt die Strecke am Stueck: echter ``AdmissionReport`` ->
``write_journal`` -> von der Platte gelesen -> beides, was der Wettbewerb
daraus zieht.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backtest.walkforward import WalkForwardReport
from research.admission import AdmissionReport, Candidate, write_journal
from research.analyst import build_prompt
from research.gates import GateReport, GateResult, GateStatus, GateThresholds
from research.seeds import spitzenkandidat
from research.versuche import TROCKENLAUF


@pytest.fixture
def geschrieben(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ein echter Bericht, durch ``write_journal`` auf die Platte und zurueck."""
    monkeypatch.delenv(TROCKENLAUF, raising=False)
    genom = spitzenkandidat()
    gates = GateReport(
        genome_id=genom.genome_id,
        results=[
            GateResult(
                name="Kosten-Stress",
                status=GateStatus.FAIL,
                value=1.08,
                threshold=1.20,
                message="Zu wenig Marge.",
            )
        ],
    )
    bericht = AdmissionReport(
        trials_before=198,
        trials_after=199,
        candidates=[
            Candidate(genome=genom, walkforward=WalkForwardReport(), gates=gates)
        ],
    )
    pfad = tmp_path / "journal.json"
    write_journal(bericht, pfad)
    return genom, json.loads(pfad.read_text())


class TestDieAusschlusslisteKommtAn:
    """So liest ``_ask_the_analyst`` (Befund 258)."""

    def test_die_kennung_steht_im_geschriebenen_journal(self, geschrieben) -> None:
        genom, journal = geschrieben

        gefunden = {
            c["genome_id"]
            for e in journal
            for c in e.get("candidates", [])
            if c.get("genome_id")
        }

        assert gefunden == {genom.genome_id}


class TestDieRueckmeldungKommtAn:
    """So liest ``build_prompt`` (Befund 260)."""

    def test_der_name_steht_im_prompt(self, geschrieben) -> None:
        genom, journal = geschrieben

        assert genom.name in build_prompt(
            journal=journal, thresholds=GateThresholds()
        )

    def test_wert_schwelle_und_meldung_stehen_im_prompt(self, geschrieben) -> None:
        """Der eigentliche Lernmechanismus: nicht *dass* es gescheitert ist,
        sondern mit welchem Wert gegen welche Schwelle."""
        _genom, journal = geschrieben
        prompt = build_prompt(journal=journal, thresholds=GateThresholds())

        assert "1.080" in prompt
        assert "1.200" in prompt
        assert "Zu wenig Marge" in prompt

    def test_der_leer_satz_faellt_weg(self, geschrieben) -> None:
        """Ohne Journal sagt der Prompt "Das Research-Journal ist leer" - genau
        das las die KI vor Befund 260 in jeder Runde."""
        _genom, journal = geschrieben
        prompt = build_prompt(journal=journal, thresholds=GateThresholds())

        assert "Research-Journal ist leer" not in prompt

    def test_ohne_journal_steht_er_da(self) -> None:
        """Die Gegenprobe - sonst prueft der Test darueber nichts."""
        prompt = build_prompt(journal=[], thresholds=GateThresholds())

        assert "erste Generation" in prompt or "Journal ist leer" in prompt


class TestDasFensterHatSeineBedeutungGeaendert:
    """``journal[-6:]`` stammt aus der Zeit, als ein Eintrag ein ganzer Lauf
    war. Seit Befund 260 ist einer eine Runde."""

    def test_die_zahl_steht_kommentiert_da(self) -> None:
        quelle = Path("research/analyst.py").read_text(encoding="utf-8")
        stelle = quelle.index("for entry in journal[-6:]")
        davor = quelle[max(0, stelle - 900):stelle]

        # Auf Wendungen ankern, die der Zeilenumbruch nicht zerschneidet -
        # "Befund 261" und "je **Runde**" tun es beide.
        assert "ein Eintrag je Lauf" in davor
        assert "aufeinanderfolgende Runden sind Varianten" in davor

    def test_nur_die_letzten_sechs_eintraege_zaehlen(self) -> None:
        journal = [
            {"candidates": [{"name": f"Regel {i}", "gate_feedback": "-"}]}
            for i in range(10)
        ]

        prompt = build_prompt(journal=journal, thresholds=GateThresholds())

        assert "Regel 9" in prompt
        assert "Regel 3" not in prompt
