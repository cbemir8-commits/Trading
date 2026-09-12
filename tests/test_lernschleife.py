"""Der Lernmechanismus war an einem Ende angeschlossen.

**Befund 260.** Am Ende jeder Wettbewerbsrunde steht dieser Kommentar, und er
beschreibt genau, was passieren soll:

    *"Die KI wird **nach** der Runde gefragt, nicht davor: Damit sieht sie im
    Journal, woran die letzten Kandidaten gescheitert sind. Genau das ist der
    Lernmechanismus, den ``analyst.py`` im Kopf beschreibt."*

Der Aufruf steht an der richtigen Stelle. Nur schreibt das Journal dort
niemand: ``write_journal`` wird allein von ``cli research`` gerufen. Jede
Runde fragte die KI also, *damit sie sieht, was gerade gescheitert ist* - und
sie sah eine Datei, die es nicht gibt.

Was hier gehalten wird
----------------------
Beide Enden. Dass geschrieben wird, dass es **vor** dem Fragen geschieht (sonst
sieht die Runde ihre eigene Messung nicht), und dass ein Trockenlauf nichts
hinterlaesst - die Wache, die ``write_journal`` als einziger der drei
schreibenden Stellen fehlte.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from research.admission import AdmissionReport, write_journal
from research.versuche import TROCKENLAUF


def _runde() -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k
        for k in ast.walk(baum)
        if isinstance(k, ast.FunctionDef) and k.name == "wettbewerb"
    )
    return ast.unparse(knoten)


class TestBeideEndenSindAngeschlossen:
    def test_der_wettbewerb_schreibt_das_journal(self) -> None:
        assert "write_journal(report, journal_path)" in _runde()

    def test_er_fragt_die_ki_auch_danach(self) -> None:
        """Das war schon da - nur ohne Gegenstueck."""
        assert "_vorschlaege()" in _runde()

    def test_geschrieben_wird_vor_dem_fragen(self) -> None:
        """Sonst sieht die Runde ihre eigene Messung nicht, und der
        Kommentar am Aufruf stimmt weiter nicht."""
        quelle = _runde()
        schreiben = quelle.index("write_journal(report, journal_path)")
        fragen = quelle.rindex("zusatz = _vorschlaege()")

        assert schreiben < fragen

    def test_geschrieben_wird_je_runde_und_nicht_am_ende(self) -> None:
        """Ein Abbruch mit Strg-C oder ein gefundener Champion soll nicht
        mitnehmen, was schon gemessen ist."""
        quelle = _runde()
        schreiben = quelle.index("write_journal(report, journal_path)")
        abbruch = quelle.index("except KeyboardInterrupt")

        assert schreiben < abbruch


class TestEinTrockenlaufHinterlaesstNichts:
    """Befund 116, hier nachgetragen: ``write_champion`` und
    ``Leaderboard.save`` hatten die Wache, ``write_journal`` nicht."""

    def test_ohne_trockenlauf_wird_geschrieben(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(TROCKENLAUF, raising=False)
        pfad = tmp_path / "journal.json"

        write_journal(AdmissionReport(trials_before=1, trials_after=2), pfad)

        assert pfad.exists()
        assert json.loads(pfad.read_text())[0]["trials_after"] == 2

    def test_im_trockenlauf_entsteht_keine_datei(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(TROCKENLAUF, "1")
        pfad = tmp_path / "journal.json"

        write_journal(AdmissionReport(trials_before=1, trials_after=2), pfad)

        assert not pfad.exists()

    def test_im_trockenlauf_bleibt_ein_vorhandenes_journal_unberuehrt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nicht nur "legt nichts an" - auch "haengt nichts an"."""
        pfad = tmp_path / "journal.json"
        monkeypatch.delenv(TROCKENLAUF, raising=False)
        write_journal(AdmissionReport(trials_before=1, trials_after=2), pfad)
        vorher = pfad.read_text()

        monkeypatch.setenv(TROCKENLAUF, "1")
        write_journal(AdmissionReport(trials_before=2, trials_after=3), pfad)

        assert pfad.read_text() == vorher

    def test_alle_drei_schreibenden_stellen_haben_die_wache(self) -> None:
        quelle = Path("research/admission.py").read_text(encoding="utf-8")
        liste = Path("research/leaderboard.py").read_text(encoding="utf-8")

        assert quelle.count("if trockenlauf():") == 2, "champion und journal"
        assert "trockenlauf()" in liste


class TestWasDasJournalTraegt:
    """Ohne die Begruendung waere es nur eine Liste von Namen - der Kopf von
    ``analyst.py`` nennt die Rueckmeldung den eigentlichen Lernmechanismus."""

    def test_es_haelt_fest_woran_es_gescheitert_ist(self) -> None:
        quelle = Path("research/admission.py").read_text(encoding="utf-8")

        assert '"gate_feedback": c.gates.feedback_for_ai()' in quelle

    def test_es_haelt_die_kennung_fuer_die_ausschlussliste(self) -> None:
        """Woraus ``_ask_the_analyst`` seit Befund 258 mit liest."""
        quelle = Path("research/admission.py").read_text(encoding="utf-8")

        assert '"genome_id": c.genome.genome_id' in quelle

    def test_jeder_lauf_wird_angehaengt(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv(TROCKENLAUF, raising=False)
        pfad = tmp_path / "journal.json"
        write_journal(AdmissionReport(trials_before=1, trials_after=2), pfad)
        write_journal(AdmissionReport(trials_before=2, trials_after=5), pfad)

        eintraege = json.loads(pfad.read_text())

        assert [e["trials_after"] for e in eintraege] == [2, 5]
