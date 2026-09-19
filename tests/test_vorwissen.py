"""Was das Register schon sagt - Befund 303.

Befund 302 hat 106 Minuten gemessen, um eine Zahl zu bestaetigen, die seit
Befund 255 im Register stand. Der Eintrag war da, gelesen hat ihn niemand -
das Nachsehen war ein Vorsatz und keine Zeile im Ablauf.

Der erste dieser Tests ist die Wache dagegen: Mit den Stichworten, die ``cli
reibung`` vor dem Lauf anmeldet, muss genau dieser Eintrag gefunden werden -
und zwar an erster Stelle.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from research.stand import BEHOBEN, GESCHLOSSEN, OFFEN
from research.vorwissen import (
    STICHWORTE,
    Fundstueck,
    auskunft,
    was_schon_dasteht,
)

#: Die Stichworte, mit denen die Befehle fragen - **aus derselben Quelle**,
#: aus der ``cli.py`` sie nimmt. Stuenden sie hier noch einmal, pruefte dieser
#: Test eine zweite Fassung und ginge irgendwann an der echten vorbei.
REIBUNG = STICHWORTE["reibung"]
VORRAT = STICHWORTE["vorratsdecke"]


class TestDieWacheGegenBefund302:
    def test_die_reibungsfrage_wird_gefunden(self) -> None:
        """**Der Test, den es ohne 302 nicht gaebe.** Diese Stichworte
        stehen so in ``cli reibung``; findet die Suche den Eintrag nicht
        mehr, liefe der naechste Lauf wieder blind los."""
        namen = [f.richtung.name for f in was_schon_dasteht(*REIBUNG)]
        assert "Traegt die Reibung die Kopplung auf kurzen Kerzen?" in namen

    def test_und_zwar_ganz_oben(self) -> None:
        """Achtzehn Treffer nuetzen nichts, wenn der richtige an Platz
        zwoelf steht - vor einem Lauf liest man die ersten Zeilen."""
        erste = was_schon_dasteht(*REIBUNG)[0]
        assert erste.richtung.name == "Traegt die Reibung die Kopplung auf kurzen Kerzen?"

    def test_der_eintrag_ist_als_gemessen_erkennbar(self) -> None:
        treffer = was_schon_dasteht(*REIBUNG)
        assert any(f.gemessen for f in treffer)

    def test_die_auskunft_nennt_die_messungen_und_die_kosten(self) -> None:
        text = auskunft(*REIBUNG, kosten="rund 106 Minuten")
        assert "nennen eine Messung" in text
        assert "rund 106 Minuten" in text

    def test_auch_die_vorratsfrage_findet_etwas(self) -> None:
        assert was_schon_dasteht(*VORRAT)


class TestWieGesuchtWird:
    def test_gross_und_kleinschreibung_egal(self) -> None:
        assert was_schon_dasteht("reibung") == was_schon_dasteht("REIBUNG")

    def test_der_name_zaehlt_wie_der_text(self) -> None:
        """Gesucht wird in beidem - ein Eintrag, dessen Name das Wort
        traegt, handelt davon; im Text kann es beilaeufig stehen."""
        nur_im_namen = [
            f for f in was_schon_dasteht("Historie")
            if "historie" in f.richtung.name.lower()
        ]
        assert nur_im_namen

    def test_ohne_stichworte_gibt_es_nichts(self) -> None:
        """Ein leerer Begriff passt auf alles und machte die Auskunft
        wertlos - dann lieber nichts."""
        assert was_schon_dasteht() == ()
        assert was_schon_dasteht("", "   ") == ()

    def test_ein_eintrag_steht_hoechstens_einmal_da(self) -> None:
        treffer = was_schon_dasteht("Kopplung", "Reibung", "Kostenanteil")
        namen = [f.richtung.name for f in treffer]
        assert len(namen) == len(set(namen))

    def test_alle_drei_register_werden_angesehen(self) -> None:
        """``GESCHLOSSEN`` allein waere genau der Fehler aus Befund 294:
        Die Suche sah ein Fuenftel des Registers an."""
        lagen = {f.lage for f in was_schon_dasteht("Kopplung", "Gate", "Vorrat")}
        assert lagen == {"geschlossen", "offen", "behoben"}

    def test_die_treffer_sagen_warum(self) -> None:
        for f in was_schon_dasteht("Reibung"):
            assert f.treffer == ("reibung",)

    def test_ein_wort_das_nirgends_steht(self) -> None:
        assert was_schon_dasteht("Zitronenfalter") == ()
        assert "nichts" in auskunft("Zitronenfalter")


class TestWasDieAuskunftLeistet:
    def test_sie_haelt_nichts_auf(self) -> None:
        """**Absicht.** Eine Messung zu wiederholen ist oft richtig - 302 hat
        255 auf einem unabhaengigen Weg bestaetigt. Falsch war nicht der
        Lauf, falsch war, ihn ohne die Antwort zu starten.

        Deshalb gibt es hier nichts, was wirft oder abbricht.
        """
        import research.vorwissen as modul

        namen = {n.lower() for n in dir(modul) if not n.startswith("_")}
        assert not {n for n in namen if "abbruch" in n or "verbiet" in n}
        assert isinstance(auskunft(*REIBUNG), str)

    def test_lange_listen_werden_gekuerzt_und_gezaehlt(self) -> None:
        """Achtzehn Absaetze vor einem Lauf liest niemand - dann waere die
        Auskunft so wirkungslos wie keine. Verschwiegen wird nichts."""
        alle = was_schon_dasteht(*REIBUNG)
        text = auskunft(*REIBUNG, zeige=3)
        assert f"und {len(alle) - 3} weitere" in text
        assert text.count("geschlossen:") + text.count("offen:") + text.count(
            "behoben:"
        ) == 3

    def test_ohne_kuerzung_keine_weiteren(self) -> None:
        text = auskunft("Zitronenfalter", "Historie", zeige=50)
        assert "weitere" not in text

    def test_keine_eckigen_klammern(self) -> None:
        """Die Ausgabe laeuft durch 'rich'. '[geschlossen]' waere dort ein
        Auszeichnungsbefehl, und der Text verschwaende spurlos - beim ersten
        Rauchtest genau so passiert."""
        assert "[" not in auskunft(*REIBUNG)

    @pytest.mark.parametrize("liste", [GESCHLOSSEN, OFFEN, BEHOBEN])
    def test_jeder_eintrag_laesst_sich_darstellen(self, liste) -> None:
        for r in liste:
            stueck = Fundstueck(lage="offen", richtung=r, treffer=("x",))
            zeile = stueck.zeile()
            assert r.name in zeile
            assert str(r.massgeblich) in zeile

    def test_die_stelle_nennt_die_letzte_fundstelle(self) -> None:
        """Wer eine Fundstelle nennt, muss die letzte nennen (Befund 130)."""
        nachgemessen = next(r for r in GESCHLOSSEN if r.zuletzt)
        stueck = Fundstueck(lage="geschlossen", richtung=nachgemessen, treffer=("x",))
        assert stueck.stelle == f"Nr. {nachgemessen.zuletzt}, zuerst {nachgemessen.befund}"


class TestDieBefehleUndIhreStichworte:
    """Die Stichworte stehen an einer Stelle - und muessen dort auch
    ankommen. Ein Eintrag, den kein Befehl abruft, waere eine Wache, die
    niemand aufstellt."""

    def _cli(self) -> str:
        return Path("cli.py").read_text(encoding="utf-8")

    def _befehle(self) -> set[str]:
        baum = ast.parse(self._cli())
        namen = set()
        for n in ast.walk(baum):
            if isinstance(n, ast.FunctionDef):
                for d in n.decorator_list:
                    if "app.command" in ast.unparse(d):
                        treffer = re.search(r'"([^"]+)"', ast.unparse(d))
                        namen.add(treffer.group(1) if treffer else n.name)
        return namen

    def test_jeder_eintrag_gehoert_zu_einem_befehl(self) -> None:
        verwaist = sorted(set(STICHWORTE) - self._befehle())
        assert verwaist == [], f"Stichworte ohne Befehl: {verwaist}"

    def test_jeder_eintrag_wird_auch_abgerufen(self) -> None:
        text = self._cli()
        fehlend = [
            name for name in STICHWORTE
            if f'_zeige_vorwissen("{name}"' not in text
        ]
        assert fehlend == [], f"Stichworte, die niemand abruft: {fehlend}"

    def test_kein_eintrag_ist_leer(self) -> None:
        for name, worte in STICHWORTE.items():
            assert worte, name
            assert all(w.strip() for w in worte), name
