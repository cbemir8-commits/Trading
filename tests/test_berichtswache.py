"""Wer nach ``reports/`` schreibt, geht durch ``write_report``.

**Befund 244.** ``core.report.write_report`` traegt drei Dinge, die man einzeln
nicht sieht:

* die **Trockenlauf-Wache** aus Befund 116 - *"Ein Rauchtest gehoert nicht in
  diesen Verlauf: Er sieht dort aus wie ein Lauf und ist keiner."*
* ``scrub`` gegen Schluessel, die nicht in ein oeffentliches Repository
  gehoeren (``api_key``, ``balance``, ``secret`` und neun weitere)
* den Schutz gegen zwei Laeufe in derselben Sekunde

``cli teststaerke`` schrieb als einziger Befehl direkt nach ``reports/`` und
ging an allen dreien vorbei. Gemessen: Ein Lauf mit ``TRADING_TROCKENLAUF=1``
legte eine Datei von 14 kB ab. Der Versuchszaehler blieb dabei korrekt bei 198
- jene Wache sitzt in ``versuche.speichern`` und greift, diese nicht.

Was das gekostet hat: bisher nichts. Die sechs Dateien vom 2026-09-02 stammen
aus echten Laeufen (Befunde 176 und 178), und keiner der 49 Schluesselpfade
eines Teststaerke-Berichts faellt unter ``VERBOTEN``. Es ist wie in Befund 241
und 243: Es traegt etwas, nur nicht das Bauteil, dem man es zuschreiben wuerde.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

#: Ordner, in den Berichte gehoeren. Wer hierher schreibt, gehoert durch die
#: Wache.
ORDNER = "reports"


def _schreibt(quelle: str) -> bool:
    """Legt dieser Befehl eine Datei an - oder nennt er den Ordner nur?"""
    return bool(re.search(r"\.write_text\(|json\.dump|_json\.dump|mkdir", quelle))


def _befehle() -> dict[str, str]:
    baum = ast.parse(Path("cli.py").read_text())
    return {
        n.name: ast.unparse(n)
        for n in ast.walk(baum)
        if isinstance(n, ast.FunctionDef)
    }


class TestDieAbdeckung:
    def test_niemand_schreibt_an_write_report_vorbei_nach_reports(self) -> None:
        """**Die Wache gegen den naechsten Befehl dieser Art.**

        Gepruefte Bedingung: nennt ``reports``, **schreibt** auch, und geht
        nicht durch ``write_report``. Alle drei Teile sind noetig. Der erste
        Entwurf liess den mittleren weg und meldete fuenf Befehle, die den
        Ordner nur **lesen** oder erwaehnen (``gatemuster``, ``vereinbar``,
        ``front``, ``streuung``, ``_formpunkte``) - dieselbe Sorte Gespenst
        wie in Befund 243, wo nach dem Mantel statt nach der Sache gesucht
        wurde.

        Legitime direkte Schreibvorgaenge gibt es auch: ``setup`` legt die
        ``.env`` an, ``anlagentest`` schreibt ein Genom. Verboten ist nur der
        Weg an der Wache vorbei **in den Berichtsverlauf**.
        """
        vorbei = [
            name
            for name, quelle in _befehle().items()
            if (f'"{ORDNER}"' in quelle or f"'{ORDNER}'" in quelle)
            and _schreibt(quelle)
            and "write_report" not in quelle
        ]

        assert vorbei == [], f"schreibt selbst nach {ORDNER}/: {vorbei}"

    def test_teststaerke_geht_jetzt_durch(self) -> None:
        quelle = _befehle()["teststaerke"]

        assert "write_report" in quelle
        assert "kind='teststaerke'" in quelle

    def test_sie_meldet_im_trockenlauf_keinen_pfad(self) -> None:
        """``write_report`` gibt dort den **Ordner** zurueck und schreibt
        nichts - "Bericht: <Ordner>" waere eine Falschmeldung."""
        quelle = _befehle()["teststaerke"]

        assert "if not trockenlauf():" in quelle


class TestWasDieWacheLeistet:
    def test_sie_schreibt_im_trockenlauf_nicht(self, tmp_path: Path) -> None:
        import os

        from core.report import write_report
        from research.versuche import TROCKENLAUF

        alt = os.environ.get(TROCKENLAUF)
        os.environ[TROCKENLAUF] = "1"
        try:
            ziel = write_report({"a": 1}, root=tmp_path, kind="teststaerke")
        finally:
            if alt is None:
                os.environ.pop(TROCKENLAUF, None)
            else:
                os.environ[TROCKENLAUF] = alt

        assert not ziel.exists() or not any(ziel.glob("*.json"))

    def test_sie_entfernt_verbotene_felder(self, tmp_path: Path) -> None:
        import json

        from core.report import write_report

        datei = write_report(
            {"maerkte": ["BTC"], "api_key": "geheim"},
            root=tmp_path,
            kind="teststaerke",
        )
        inhalt = json.loads(datei.read_text())

        assert "api_key" not in inhalt
        assert inhalt["maerkte"] == ["BTC"]

    def test_zwei_laeufe_in_derselben_sekunde_ueberschreiben_sich_nicht(
        self, tmp_path: Path
    ) -> None:
        from core.report import write_report

        a = write_report({"n": 1}, root=tmp_path, kind="teststaerke")
        b = write_report({"n": 2}, root=tmp_path, kind="teststaerke")

        assert a != b
        assert a.exists() and b.exists()


class TestWasBisherKeinSchadenWar:
    def test_kein_vorhandener_bericht_traegt_ein_verbotenes_feld(self) -> None:
        """Nachgesehen statt angenommen - erst danach steht im Befund, dass
        es nichts gekostet hat."""
        import json

        from core.report import VERBOTEN

        dateien = sorted(Path("reports/teststaerke").glob("*.json"))
        if not dateien:
            pytest.skip("keine Berichte im Baum")

        def schluessel(o, pfad=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield f"{pfad}{k}"
                    yield from schluessel(v, f"{pfad}{k}.")
            elif isinstance(o, list):
                for x in o[:3]:
                    yield from schluessel(x, pfad)

        for datei in dateien:
            alle = set(schluessel(json.loads(datei.read_text())))
            treffer = [k for k in alle if any(w in k.lower() for w in VERBOTEN)]

            assert treffer == [], f"{datei.name}: {treffer}"

    def test_die_dateinamen_folgen_derselben_form(self) -> None:
        """Der Handbau traf das Format - deshalb faellt der Wechsel nicht auf,
        und deshalb war die Luecke so lange unsichtbar."""
        muster = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}(-\d+)?\.json$")
        dateien = list(Path("reports/teststaerke").glob("*.json"))
        if not dateien:
            pytest.skip("keine Berichte im Baum")

        for datei in dateien:
            assert muster.match(datei.name), datei.name
