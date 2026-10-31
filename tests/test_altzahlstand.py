"""Die Ersatzspalte der Altzahlen hatte selbst keinen Stand - Befund 436.

Befund 408 hat diagnostiziert, warum gepflegte Zahlen nicht mehr
reproduzierten:

    keine gepflegte Zahl hat verzeichnet, auf welchem Stand sie gemessen
    wurde

Daraus entstand ``datenstempel`` und mit ihm ``ALTZAHLEN``: je Zahl der
gepflegte Wert und ein ``heute``. **Und diese Ersatzspalte trug denselben
Mangel** - kein Stand, kein Weg, sie nachzurechnen. Solange es keinen
benennbaren Speicher gab, war das auch nicht zu heilen; seit Befund 429 und
435 gibt es einen, der auf dokumentierte Befehle hin entsteht und auf seinen
Fingerabdruecken steht.

Nachgemessen hat jede der sechs ihren ``heute``-Wert gehalten. Vier ueber
eigene Laeufe (``cli streuung``, ``cli finanzierung --stress``), zwei ueber
die Zusicherung in ``tests/test_referenz.py``, die bei jedem Lauf der
Datenauswahl greift.
"""

from __future__ import annotations

import dataclasses

from research.datenstempel import ALTZAHLEN, Altzahl


class TestJedeZahlSagtWieSieNachzurechnenIst:
    def test_keine_steht_ohne_befehl_da(self) -> None:
        """Eine Zahl, zu der niemand den Weg kennt, ist eine Behauptung."""
        ohne = [a.name for a in ALTZAHLEN if not a.befehl.strip()]

        assert ohne == [], ohne

    def test_der_befehl_ist_ein_lauf_oder_eine_zusicherung(self) -> None:
        for a in ALTZAHLEN:
            assert a.befehl.startswith(("python -m cli ", "pytest ")), (
                a.name,
                a.befehl,
            )

    def test_die_momente_nennen_den_test_und_nicht_einen_befehl(self) -> None:
        """**Mein Fehlgriff in diesem Befund** (436): Hier stand zuerst
        'cli nachpruefung'. Der faehrt 26 Katalogkandidaten und rechnet diese
        Zahl nicht - gemessen wird sie von 'test_referenz', bei jedem Lauf
        der Datenauswahl."""
        for name in ("Schiefe ueber alle Trades", "Woelbung ueber alle Trades"):
            a = next(x for x in ALTZAHLEN if x.name == name)

            assert "test_referenz" in a.befehl, (name, a.befehl)
            assert "nachpruefung" not in a.befehl, (name, a.befehl)


class TestNachgepruefftIstEtwasAnderesAlsStimmt:
    def test_alle_sechs_sind_auf_der_gepinnten_reihe_nachgemessen(self) -> None:
        offen = [a.name for a in ALTZAHLEN if a.nachgeprueft is None]

        assert offen == [], offen

    def test_und_zwar_in_befund_436(self) -> None:
        assert {a.nachgeprueft for a in ALTZAHLEN} == {436}

    def test_leer_heisst_nicht_geprueft_und_nicht_falsch(self) -> None:
        """Die Unterscheidung, die Befund 430 an den erwarteten Ausfaellen
        eingezogen hat - eine Vorgabe, die 'bestanden' bedeutet, waere ein
        Freibrief."""
        frisch = Altzahl(name="x", gepflegt=1.0, heute=1.1, befund=1)

        assert frisch.nachgeprueft is None
        assert frisch.befehl == ""


class TestDieGepflegtenZahlenBleibenUnangetastet:
    def test_gepflegt_und_heute_sind_verschieden(self) -> None:
        """Stimmt der alte Wert wieder, gehoert der Eintrag aus ALTZAHLEN -
        nicht die Zahl von damals nachgezogen (Befund 364)."""
        for a in ALTZAHLEN:
            assert a.gepflegt != a.heute, a.name

    def test_die_drift_bleibt_unter_einem_prozent_bis_auf_eine(self) -> None:
        ueber = [a.name for a in ALTZAHLEN if abs(a.prozent) >= 1.0]

        assert ueber == ["Streuungswert, DSR mit der Messung"], ueber

    def test_die_spanne_ist_die_gemessene(self) -> None:
        """Befund 364 nannte 'zwischen 0,2 und 0,6 Prozent'; gemessen sind es
        0,23 bis 1,20 - das steht so im Modulkopf und soll dort stimmen."""
        spanne = sorted(abs(a.prozent) for a in ALTZAHLEN)

        assert round(spanne[0], 2) == 0.23
        assert round(spanne[-1], 2) == 1.20


class TestDieFelderSindDa:
    def test_altzahl_traegt_befehl_und_nachgeprueft(self) -> None:
        namen = {f.name for f in dataclasses.fields(Altzahl)}

        assert {"befehl", "nachgeprueft"} <= namen

    def test_beide_haben_eine_vorgabe(self) -> None:
        """Ein neuer Eintrag soll sich anlegen lassen, ohne dass jemand
        behauptet, er sei geprueft."""
        vorgaben = {
            f.name: f.default
            for f in dataclasses.fields(Altzahl)
            if f.name in ("befehl", "nachgeprueft")
        }

        assert vorgaben == {"befehl": "", "nachgeprueft": None}
