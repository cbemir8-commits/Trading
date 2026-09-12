"""Was die KI schon vorgeschlagen hat, muss sie nicht noch einmal vorschlagen.

**Befund 258.** ``admission`` zaehlt **jedes** Genom, das es erreicht - ob es
besteht oder nicht (*"Jeder Kandidat erhoeht den Zaehler"*). Ein Doppelgaenger,
den niemand abfaengt, kostet also einen Versuch und traegt nichts bei; einer,
den ``parse_proposals`` abfaengt, kostet nichts (Befund 259).

Damit das greift, muss ``already_tried`` stimmen. Zwei Aufrufer bauen die
Menge, und sie bauten sie verschieden:

* ``cli vorschlag`` nimmt ``set(board.entries)`` - die Bestenliste. Richtig.
* ``_ask_the_analyst``, ueber das ``cli wettbewerb --ki`` geht, nahm allein
  das Journal.

Und ``cli wettbewerb`` schreibt **kein** Journal. Dort war die Ausschlussliste
also leer, waehrend die Bestenliste danebenlag - bei einem Versuchsstand von
198 von 230 der teuerste Posten im Haus.

Was hier gehalten wird
----------------------
Dass die Liste an **einer** Stelle gebaut wird und beide Quellen enthaelt -
nicht, dass ein Aufrufer daran denkt. Dieselbe Bauart wie ``_spotconfigs``
(Befund 168).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from research.leaderboard import FORMAT, Leaderboard


def _quelle(name: str) -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == name
    )
    return ast.unparse(knoten)


class TestDieListeWirdAnEinerStelleGebaut:
    def test_der_analyst_liest_die_bestenliste_selbst(self) -> None:
        quelle = _quelle("_ask_the_analyst")

        assert "Leaderboard(" in quelle
        assert "leaderboard.json" in quelle

    def test_sie_wird_mit_dem_journal_vereinigt_und_ersetzt_es_nicht(self) -> None:
        """Beide Quellen, nicht die eine statt der anderen: Das Journal kann
        Kandidaten tragen, die nie in die Liste kamen."""
        quelle = _quelle("_ask_the_analyst")

        assert "tried |= gemessen" in quelle
        # ``ast.unparse`` normiert auf einfache Anfuehrungszeichen - dieselbe
        # Falle wie in Befund 244.
        assert "tried.add(candidate['genome_id'])" in quelle

    def test_der_andere_aufrufer_macht_es_weiter_richtig(self) -> None:
        assert "set(board.entries)" in _quelle("vorschlag")

    def test_die_zahl_steht_im_lauf(self) -> None:
        """Eine stille Ausschlussliste ist von einer leeren nicht zu
        unterscheiden - genau daran ist es vorbeigelaufen."""
        quelle = _quelle("_ask_the_analyst")

        assert "Ausgeschlossen:" in quelle
        assert "len(tried)" in quelle


class TestDieBestenlisteLiefertDieKennungen:
    def test_die_schluessel_sind_genome_ids(self, tmp_path: Path) -> None:
        pfad = tmp_path / "leaderboard.json"
        pfad.write_text(
            json.dumps(
                {
                    "format": FORMAT,
                    "laeufe": 1,
                    "eintraege": [
                        {"genome_id": "abc123", "name": "Eine Regel", "generation": 9},
                        {"genome_id": "def456", "name": "Noch eine", "generation": 9},
                    ],
                }
            )
        )

        assert set(Leaderboard(pfad).entries) == {"abc123", "def456"}

    def test_eine_fehlende_datei_gibt_eine_leere_menge(self, tmp_path: Path) -> None:
        """Kein Fehler, nur nichts auszuschliessen - so faellt der Analyst
        nicht aus, wenn die Liste noch nicht existiert."""
        assert set(Leaderboard(tmp_path / "gibtsnicht.json").entries) == set()

    def test_ein_veraltetes_format_schliesst_nichts_aus(self, tmp_path: Path) -> None:
        """Lieber nichts ausschliessen als die falschen - die Liste faellt
        bei fremdem Format bewusst leer aus."""
        pfad = tmp_path / "leaderboard.json"
        pfad.write_text(
            json.dumps({"format": FORMAT - 1, "eintraege": [{"genome_id": "x"}]})
        )

        assert set(Leaderboard(pfad).entries) == set()


class TestWasEinDoppelgaengerKostet:
    """Der Grund, warum das eine Zeile wert ist."""

    def test_der_ablehnungstext_sagt_was_gerade_passiert_ist(self) -> None:
        """Er sagte bis Befund 259 das Gegenteil: "zaehlt trotzdem als
        Versuch" - im Moment, in dem das Abfangen den Versuch gerade spart."""
        import json as _json

        from research.analyst import parse_proposals
        from research.seeds import spitzenkandidat

        genom = spitzenkandidat()
        antwort = _json.dumps([genom.model_dump(mode="json")])
        abgelehnt = parse_proposals(antwort, already_tried={genom.genome_id})

        assert abgelehnt and not abgelehnt[0].accepted
        grund = abgelehnt[0].reason
        assert "bevor er einen Versuch kostet" in grund
        assert "zaehlt trotzdem" not in grund

    def test_der_modulkopf_darf_den_satz_behalten(self) -> None:
        """Dort stimmt er: Ohne Journal schlaegt das Modell dasselbe wieder
        vor, und **ungefiltert** kostet jede Wiederholung einen Versuch."""
        quelle = Path("research/analyst.py").read_text(encoding="utf-8")
        kopf = quelle[: quelle.index("from __future__")]

        assert "zaehlt trotzdem als" in kopf

    def test_ein_bekanntes_genom_wird_abgelehnt(self) -> None:
        from research.analyst import parse_proposals

        antwort = json.dumps(
            [
                {
                    "name": "Testregel",
                    "rationale": "nur zum Pruefen der Ablehnung",
                    "entry_long": [],
                    "exit_long": [],
                }
            ]
        )
        offen = parse_proposals(antwort)
        if not offen:
            return  # Das Genom-Schema verlangt mehr - dann prueft der Test oben.
        kennung = offen[0].genome.genome_id
        gesperrt = parse_proposals(antwort, already_tried={kennung})

        assert gesperrt and not gesperrt[0].accepted
        assert "schon einmal getestet" in gesperrt[0].reason

    def test_ein_abgelehnter_vorschlag_erreicht_die_zulassung_nie(self) -> None:
        """Die Kette, an der alles haengt: ``genomes`` filtert auf
        ``accepted``, und nur ``genomes`` geht weiter. Waere das anders, waere
        das Abfangen wirkungslos."""
        from research.analyst import AnalystResult, Proposal
        from research.seeds import spitzenkandidat

        genom = spitzenkandidat()
        ergebnis = AnalystResult(
            proposals=[
                Proposal(genome=genom, accepted=False, reason="schon getestet")
            ]
        )

        assert ergebnis.genomes == []

    def test_der_wettbewerb_reicht_nur_die_angenommenen_weiter(self) -> None:
        assert "return result.genomes" in _quelle("_ask_the_analyst")

    def test_die_zulassung_zaehlt_jedes_genom_das_sie_erreicht(self) -> None:
        """Der andere Haken derselben Kette - ohne ihn spart das Abfangen
        nichts."""
        quelle = Path("research/admission.py").read_text(encoding="utf-8")

        assert "Jeder Kandidat erhoeht den Zaehler" in quelle
        assert "trials += 1" in quelle
