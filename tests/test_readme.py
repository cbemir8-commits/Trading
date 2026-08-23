"""Die README ist das Erste, was jemand sieht - Befund 118.

Sie stand auf dem Stand vom 1. August: *"Status: Phase 0 (Fundament) ...
Handelt noch nicht"*, *"der aktuellen 62 Tests"*, *"die acht Zulassungs-Gates
(P3)"*. Dazwischen lagen 57 Befunde.

Das ist dieselbe Klasse wie die Befunde 111 bis 117 - Wissen liegt im System
und steuert nichts - nur an der aeussersten Stelle: Wer das Repository oeffnet,
liest hier zuerst.

Diese Tests halten die drei Aussagen fest, die maschinell pruefbar sind. Sie
koennen nicht verhindern, dass ein Text veraltet; sie verhindern, dass die
**Zahlen** darin still falsch werden.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

README = Path("README.md")


@pytest.fixture(scope="module")
def text() -> str:
    return README.read_text(encoding="utf-8")


class TestGenannteBefehle:
    def test_jeder_genannte_cli_befehl_existiert(self, text: str) -> None:
        """Ein Befehl, den es nicht gibt, ist die teuerste Zeile einer
        Anleitung: Wer ihr folgt, steht vor einem Fehler und weiss nicht,
        ob er selbst schuld ist."""
        import cli

        vorhanden = {
            c.name or c.callback.__name__ for c in cli.app.registered_commands
        }
        genannt = set(re.findall(r"python -m cli ([a-z][a-z_-]*)", text))
        genannt |= set(
            re.findall(r"\.venv[\\/]\S*python -m cli ([a-z][a-z_-]*)", text)
        )

        fehlend = sorted(genannt - vorhanden)
        assert fehlend == [], f"README nennt Befehle, die es nicht gibt: {fehlend}"

    def test_die_wichtigsten_stehen_drin(self, text: str) -> None:
        """``stand`` ist der Befehl, der den Stand misst, ``wettbewerb`` der,
        den der Nutzer nach dem Backfill braucht. Fehlt einer, findet er den
        naechsten Schritt nicht."""
        for befehl in ("stand", "wettbewerb", "backfill", "healthcheck"):
            assert f"cli {befehl}" in text, f"'{befehl}' fehlt in der README"


class TestGenannteZahlen:
    def test_die_gate_zahl_stimmt(self, text: str) -> None:
        """Stand bis Befund 118 auf "acht Zulassungs-Gates". Es sind elf."""
        import inspect

        import research.gates as gates

        tatsaechlich = inspect.getsource(gates.evaluate_gates).count("gate_")
        woerter = {
            8: "acht", 9: "neun", 10: "zehn", 11: "elf", 12: "zwoelf",
        }
        richtig = woerter.get(tatsaechlich)
        assert richtig, f"Zahlwort fuer {tatsaechlich} Gates fehlt in diesem Test"

        treffer = re.findall(r"(\w+) Zulassungs-Gates", text)
        assert treffer, "Die README nennt die Gates gar nicht mehr"
        falsch = [t for t in treffer if t.lower() != richtig]
        assert falsch == [], (
            f"README nennt '{falsch[0]} Zulassungs-Gates', tatsaechlich sind "
            f"es {tatsaechlich} ({richtig})"
        )

    def test_keine_feste_testzahl(self, text: str) -> None:
        """``pytest -q`` sagt die Zahl selbst - eine zweite Quelle veraltet.

        In der README stand "der aktuellen 62 Tests", waehrend die Suite auf
        ueber zweitausend gewachsen war.
        """
        treffer = re.findall(r"(\d[\d.\s]*)\s*Tests\b", text)
        assert treffer == [], (
            f"README nennt eine feste Testzahl: {treffer}. Sie ist am Tag "
            "nach dem Schreiben falsch."
        )

    def test_keine_feste_laufzeit_der_suite(self, text: str) -> None:
        """Stand auf "~3 s". Die Suite laeuft inzwischen Minuten."""
        assert "~3 s" not in text


class TestStandUndSperre:
    def test_der_status_behauptet_nicht_phase_null(self, text: str) -> None:
        """P0 bis P7 sind abgeschlossen."""
        assert "Phase 0 (Fundament)" not in text

    def test_die_sperre_wird_genannt(self, text: str) -> None:
        """Der wichtigste Satz fuer den Nutzer: Ohne Boersendaten gibt es
        keine Zulassung, egal wie viele Gates halten (Befund 102/114)."""
        assert "Börsendaten" in text or "Boersendaten" in text
        assert "backfill" in text

    def test_der_stand_wird_nicht_hier_gepflegt(self, text: str) -> None:
        """Eine Quelle, nicht zwei - die Lehre aus Befund 112."""
        assert "cli stand" in text

    def test_der_trockenlauf_ist_dokumentiert(self, text: str) -> None:
        """Wer ihn nicht kennt, verbrennt Versuche (Befund 104) - wer ihn
        falsch versteht, hinterlaesst Spuren (Befund 116/117)."""
        from research.versuche import TROCKENLAUF

        assert TROCKENLAUF in text
