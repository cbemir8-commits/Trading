"""Lange Messungen in Stuecken - Befund 300.

Zwei Laeufe von ``cli vorratsdecke -i 15`` sind an einem Neustart gestorben,
beide wenige Minuten nach dem Ende des Arbeitszugs. Ein dreistuendiger Lauf
ist hier damit nicht riskant, sondern unmoeglich; er muss in Stuecke.

Die Stuecke duerfen aber nur dann ein Lauf sein, wenn sie es sind. Befund 299
hat ein Wiederaufsetzen abgelehnt, weil es die Gleichheit der Bedingungen
**behauptet**. Diese Tests halten fest, dass sie hier **geprueft** wird - und
dass eine Stueckelung kein einziges Urteil verschiebt.
"""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

import pytest

from research.zwischenstand import (
    WECHSELND,
    Uneinig,
    Zwischenstand,
    scheibe,
    zusammen,
)


def _schreibe(pfad: Path, kopf: dict, *messungen: dict) -> Path:
    stand = Zwischenstand(pfad=pfad, bedingungen=dict(kopf))
    stand.beginne()
    for messung in messungen:
        stand.halte_fest(**messung)
    return pfad


BEDINGUNGEN = {
    "maerkte": ["BTCUSD_BITSTAMP"],
    "intervall": "15m",
    "versuchsstand": 203,
    "betriebspunkt": "Spot",
    "code": "abc123",
    "katalog": "def456",
}


class TestStueckeZusammenlegen:
    def test_zwei_stuecke_derselben_messung(self, tmp_path: Path) -> None:
        a = _schreibe(
            tmp_path / "a.jsonl",
            {**BEDINGUNGEN, "stueck": "1/2", "genome": 2},
            {"regel": "Erste"},
            {"regel": "Zweite"},
        )
        b = _schreibe(
            tmp_path / "b.jsonl",
            {**BEDINGUNGEN, "stueck": "2/2", "genome": 1},
            {"regel": "Dritte"},
        )

        kopf, messungen = zusammen([a, b])
        assert [m["regel"] for m in messungen] == ["Erste", "Zweite", "Dritte"]
        assert kopf["intervall"] == "15m"
        assert kopf["code"] == "abc123"

    def test_die_reihenfolge_folgt_den_pfaden(self, tmp_path: Path) -> None:
        a = _schreibe(
            tmp_path / "a.jsonl", {**BEDINGUNGEN, "stueck": "1/2"}, {"regel": "A"}
        )
        b = _schreibe(
            tmp_path / "b.jsonl", {**BEDINGUNGEN, "stueck": "2/2"}, {"regel": "B"}
        )

        _, vorwaerts = zusammen([a, b])
        _, rueckwaerts = zusammen([b, a])
        assert [m["regel"] for m in vorwaerts] == ["A", "B"]
        assert [m["regel"] for m in rueckwaerts] == ["B", "A"]

    def test_ein_einzelnes_stueck_ist_auch_eine_messung(self, tmp_path: Path) -> None:
        a = _schreibe(tmp_path / "a.jsonl", BEDINGUNGEN, {"regel": "Einzeln"})
        kopf, messungen = zusammen([a])
        assert kopf["intervall"] == "15m"
        assert len(messungen) == 1

    def test_die_wechselnden_felder_duerfen_sich_unterscheiden(
        self, tmp_path: Path
    ) -> None:
        """``begonnen``, ``stueck`` und ``genome`` sind je Stueck andere -
        alles andere beschreibt die Bedingungen."""
        assert set(WECHSELND) == {"begonnen", "stueck", "genome"}
        a = _schreibe(tmp_path / "a.jsonl", {**BEDINGUNGEN, "stueck": "1/9", "genome": 4})
        b = _schreibe(tmp_path / "b.jsonl", {**BEDINGUNGEN, "stueck": "7/9", "genome": 5})
        kopf, _ = zusammen([a, b])
        assert "stueck" not in kopf and "genome" not in kopf


class TestWasAbgewiesenWird:
    def test_ein_anderer_codestand(self, tmp_path: Path) -> None:
        """**Der Kern von Befund 300.** Zwei Stuecke, zwischen denen der
        rechnende Code sich geaendert hat, sind zwei Messungen."""
        a = _schreibe(tmp_path / "a.jsonl", {**BEDINGUNGEN, "stueck": "1/2"})
        b = _schreibe(
            tmp_path / "b.jsonl", {**BEDINGUNGEN, "code": "anders", "stueck": "2/2"}
        )
        with pytest.raises(Uneinig, match="code"):
            zusammen([a, b])

    def test_andere_kerzen(self, tmp_path: Path) -> None:
        a = _schreibe(tmp_path / "a.jsonl", {**BEDINGUNGEN, "kerzen": {"n": "100"}})
        b = _schreibe(tmp_path / "b.jsonl", {**BEDINGUNGEN, "kerzen": {"n": "101"}})
        with pytest.raises(Uneinig, match="kerzen"):
            zusammen([a, b])

    def test_ein_anderer_versuchsstand(self, tmp_path: Path) -> None:
        """Der Zaehler entscheidet schon im Lauf, welche Regel ueberhaupt
        eine Latte bekommt - zwei Staende sind zwei Ausschlusslisten."""
        a = _schreibe(tmp_path / "a.jsonl", BEDINGUNGEN)
        b = _schreibe(tmp_path / "b.jsonl", {**BEDINGUNGEN, "versuchsstand": 204})
        with pytest.raises(Uneinig, match="versuchsstand"):
            zusammen([a, b])

    def test_der_fehler_nennt_beide_werte(self, tmp_path: Path) -> None:
        """Eine Absage, die nicht sagt woran, kostet die naechste halbe
        Stunde mit Suchen."""
        a = _schreibe(tmp_path / "a.jsonl", BEDINGUNGEN)
        b = _schreibe(tmp_path / "b.jsonl", {**BEDINGUNGEN, "intervall": "1d"})
        with pytest.raises(Uneinig) as fehler:
            zusammen([a, b])
        assert "'15m'" in str(fehler.value) and "'1d'" in str(fehler.value)

    def test_ein_feld_das_nur_einer_traegt(self, tmp_path: Path) -> None:
        """Ein fehlendes Feld ist ein Unterschied und kein 'None' - sonst
        liesse ein Kopf ohne Codeabdruck jeden anderen zu."""
        a = _schreibe(tmp_path / "a.jsonl", BEDINGUNGEN)
        ohne = {k: v for k, v in BEDINGUNGEN.items() if k != "code"}
        b = _schreibe(tmp_path / "b.jsonl", ohne)
        with pytest.raises(Uneinig, match="code"):
            zusammen([a, b])

    def test_ein_stueck_ohne_kopf(self, tmp_path: Path) -> None:
        a = _schreibe(tmp_path / "a.jsonl", BEDINGUNGEN)
        kopflos = tmp_path / "b.jsonl"
        kopflos.write_text(
            json.dumps({"art": "messung", "regel": "Ohne Herkunft"}) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(Uneinig, match="keinen Kopf"):
            zusammen([a, kopflos])

    def test_gar_keine_pfade(self) -> None:
        with pytest.raises(Uneinig):
            zusammen([])

    def test_eine_datei_die_es_nicht_gibt(self, tmp_path: Path) -> None:
        with pytest.raises(Uneinig, match="keinen Kopf"):
            zusammen([tmp_path / "gibtsnicht.jsonl"])


class TestDieStueckgrenzen:
    @pytest.mark.parametrize("wieviele", [0, 1, 5, 30, 39, 100])
    @pytest.mark.parametrize("teile", [1, 2, 3, 4, 7, 39])
    def test_luecken_und_ueberschneidungsfrei(self, wieviele: int, teile: int) -> None:
        """**Die Eigenschaft, auf die es ankommt.** Eine Luecke laesst eine
        Regel ungemessen, eine Ueberschneidung zaehlt eine doppelt."""
        grenzen = [scheibe(wieviele, f"{i}/{teile}") for i in range(1, teile + 1)]
        assert grenzen[0][0] == 0
        assert grenzen[-1][1] == wieviele
        for (_, ende), (anfang, _) in pairwise(grenzen):
            assert ende == anfang
        assert sum(b - a for a, b in grenzen) == wieviele

    def test_ungleiche_teilung_vorne_schwerer(self) -> None:
        """39 auf 4 Stuecke: 10, 10, 10, 9 - und nicht 9, 10, 10, 10 oder
        gar 10, 10, 10, 10."""
        laengen = [b - a for a, b in (scheibe(39, f"{i}/4") for i in range(1, 5))]
        assert laengen == [10, 10, 10, 9]

    def test_ein_stueck_ist_der_ganze_lauf(self) -> None:
        assert scheibe(39, "1/1") == (0, 39)

    @pytest.mark.parametrize(
        "text", ["", "2", "2/", "/2", "zwei/fuenf", "2/0", "0/5", "6/5", "-1/5"]
    )
    def test_unsinn_wird_abgewiesen(self, text: str) -> None:
        """Nicht gerundet, nicht geraten: Ein stillschweigend verschobenes
        Stueck waere ein Lauf, der nie fertig wird."""
        with pytest.raises(ValueError):
            scheibe(39, text)

    def test_leerzeichen_stoeren_nicht(self) -> None:
        assert scheibe(39, " 2/4 ") == scheibe(39, "2/4")

    def test_mehr_stuecke_als_genome(self) -> None:
        """Erlaubt, und die hinteren bleiben leer - das ist ehrlicher als
        eine Absage, die zum Nachrechnen der Katalogzahl zwingt."""
        leer = [scheibe(3, f"{i}/5") for i in range(4, 6)]
        assert all(a == b for a, b in leer)
