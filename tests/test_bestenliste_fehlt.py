"""Eine fehlende Bestenliste ist etwas anderes als eine leere.

``state/`` ist maschinenspezifisch und liegt bis auf ``trials.json`` nicht im
Repository (Befund 73). Nach einem Behaelterwechsel ist ``leaderboard.json``
also **regulaer** weg - so wie die Kerzen in Befund 151.

Drei Stellen lasen die Datei bis Befund 166 mit je eigenem ``try/except``,
und keine konnte die beiden Faelle auseinanderhalten. ``cli partner`` meldete
deshalb auf einem frischen Behaelter:

    Kein Bestenlisten-Eintrag traegt seinen Sharpe je Trade. Seit Befund 69
    schreibt jeder neue Lauf ihn mit.

Das ist die Diagnose eines fehlenden **Feldes**, und es fehlte die ganze
Datei. Wer dem Hinweis folgt, sucht nach Eintraegen, die es nicht gibt -
derselbe Fehler wie die "Nadelspitze" in Befund 163: eine Botschaft, die
konkreter ist als die Messung dahinter.
"""

from __future__ import annotations

import json
from pathlib import Path

from cli import _bestenliste, _bestenliste_hinweis


class TestBestenlisteLesen:
    def test_vorhandene_liste_wird_gelesen_und_gemeldet(self, tmp_path: Path) -> None:
        (tmp_path / "leaderboard.json").write_text(
            json.dumps({"eintraege": [{"name": "A", "sharpe_je_trade": 0.3}]})
        )

        daten, vorhanden = _bestenliste(tmp_path)

        assert vorhanden is True
        assert daten["eintraege"][0]["name"] == "A"

    def test_fehlende_datei_meldet_sich_als_fehlend(self, tmp_path: Path) -> None:
        daten, vorhanden = _bestenliste(tmp_path)

        assert vorhanden is False
        assert daten == {}

    def test_kaputte_datei_gilt_ebenfalls_als_nicht_vorhanden(
        self, tmp_path: Path
    ) -> None:
        """Unlesbar ist fuer den Aufrufer dasselbe wie nicht da - beides
        liefert keine Anwaerter. Der Hinweis darf nur nicht behaupten, es
        laegen Eintraege ohne Feld vor."""
        (tmp_path / "leaderboard.json").write_text("{kaputt")

        daten, vorhanden = _bestenliste(tmp_path)

        assert vorhanden is False
        assert daten == {}

    def test_eine_leere_aber_vorhandene_liste_gilt_als_vorhanden(
        self, tmp_path: Path
    ) -> None:
        """**Der Fall, der die beiden Botschaften trennt.**

        Die Datei ist da, nur traegt kein Eintrag seinen Sharpe je Trade -
        genau die Lage, die der alte Text beschrieb.
        """
        (tmp_path / "leaderboard.json").write_text(json.dumps({"eintraege": []}))

        daten, vorhanden = _bestenliste(tmp_path)

        assert vorhanden is True
        assert daten == {"eintraege": []}


class TestDerHinweisTrifftDenFall:
    def test_ohne_datei_wird_die_datei_genannt(self) -> None:
        text = _bestenliste_hinweis(False)

        assert "Keine Bestenliste vorhanden" in text
        assert "Behaelterwechsel" in text
        assert "cli wettbewerb" in text, "ohne den Weg zurueck ist es nur eine Klage"
        assert "Befund 69" not in text, (
            "Befund 69 erklaert fehlende Felder, nicht fehlende Dateien."
        )

    def test_mit_datei_bleibt_die_alte_erklaerung(self) -> None:
        """Sie war nie falsch - nur am falschen Fall angebracht."""
        text = _bestenliste_hinweis(True)

        assert "Sharpe je Trade" in text
        assert "Befund 69" in text
        assert "Behaelterwechsel" not in text

    def test_die_beiden_hinweise_sind_verschieden(self) -> None:
        """Waeren sie gleich, haette sich nichts geaendert."""
        assert _bestenliste_hinweis(True) != _bestenliste_hinweis(False)
