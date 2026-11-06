"""Eine offene Richtung, die ein spaeterer Eintrag nennt (Befund 462).

Was passiert ist
----------------
Befund 416 hat ``Gedeckelter Ausstieg`` (177) auf der echten Zulassungsreihe
durchgemessen - sechs Deckel, elf Gates, ein Modul, ein Laborbuchabschnitt -
und ``Richtung.zuletzt`` nicht gesetzt. Der Modulkopf von
``research.haltedeckel`` nennt die Luecke dabei selbst: *"der einzige dort
ohne Nachmessung"*.

``research.nachmessung`` liest das **Register**, nicht die Modulkoepfe. Also
galt 177 weiter als die einzige nie nachgemessene offene Richtung, und ein
spaeterer Lauf ist genau dorthin geschickt worden. Der Preis war ein Zyklus
Suchen fuer eine Antwort, die seit 46 Befunden im Projekt stand.

Dieselbe Lehre wie Befund 178 - *"Eine Richtung, die nicht im Register steht,
wird ein zweites Mal gegangen"* -, nur eine Stufe spaeter: Hier stand die
Richtung drin und ihre **Antwort** nicht.

Warum die Wache so eng ist
--------------------------
Gemessen, nicht geschaetzt - drei Fassungen, zwei verworfen:

    Kriterium                                      Treffer
    Eintrag nennt aelteren ohne 'zuletzt'           99 von 351 Eintraegen
    Nackte Zahl nennt offene Richtung               13 von 19 Richtungen
    "Befund N" nennt offene Richtung                 4 von 19 Richtungen

Die erste Fassung ist Rauschen: Fast jeder Befund zitiert seine Vorgaenger,
und Zitieren ist nicht Nachmessen. Das ist der Fehler aus Befund 118, wo eine
Textsuche elf Befehle als fehlend gemeldet hat, die es gab.

Die zweite ist **belegbar falsch**: ``56.000 Versuchen`` trifft Befund 56,
``100 % der zufaelligen Sperren`` trifft Befund 100. Darauf eine Wache zu
setzen verlangt Buchhaltung fuer Richtungen, die niemand gemeint hat.

Die dritte traf vier Richtungen, drei davon verzeichnet (395 auf 416, 332 auf
352, 213 auf 239). Unverzeichnet war genau eine - die, um die es hier geht.

Was die Wache verlangt
----------------------
Nicht ``zuletzt``, sondern **eine verzeichnete Entscheidung**: ``zuletzt``
*oder* einen Eintrag in ``GELESEN``. Beides kann nur setzen, wer den Befund
gelesen hat - der Grundsatz des Moduls (*"Es entscheidet nichts"*) bleibt
damit unberuehrt. Eine Richtung darf offen bleiben, nachdem jemand sie
gelesen hat; sie darf nur nicht **stillschweigend** offen bleiben, nachdem
ein anderer Eintrag sie beim Namen genannt hat.

Was sie nicht kann
------------------
Sie haengt an einer Textstelle und ist zu umgehen, indem man die Nummer
weglaesst. Sie faengt die **ehrliche** Nennung - und genau die erzeugt den
veralteten Zeiger, denn wer eine Richtung nachmisst, nennt sie.
"""
from __future__ import annotations

import re

import pytest

from research.nachmessung import GELESEN
from research.stand import BEHOBEN, GESCHLOSSEN, OFFEN, Richtung

ALLE: tuple[Richtung, ...] = (*GESCHLOSSEN, *OFFEN, *BEHOBEN)

#: Die ausdrueckliche Form: "Befund 177". Siehe den Modulkopf, warum nicht
#: nackte Zahlen.
VERWEIS = re.compile(r"Befund (\d+)")

#: Nur zur Gegenprobe im Modulkopf - **nicht** das Kriterium der Wache.
NACKT = re.compile(r"\b(\d{2,3})\b")


def _genannt_in(r: Richtung, muster: re.Pattern[str]) -> tuple[int, ...]:
    """Die spaeteren Eintraege, die ``r`` nennen - nach der Nachmessung."""
    return tuple(
        sorted(
            {
                q.befund
                for q in ALLE
                if q.befund > r.massgeblich
                and str(r.befund) in set(muster.findall(q.ergebnis))
            }
        )
    )


def _verzeichnet(r: Richtung) -> bool:
    """Traegt die Richtung eine Entscheidung, die jemand gefasst hat?"""
    return r.zuletzt is not None or r.name in GELESEN


class TestEineGenannteRichtungTraegtEineEntscheidung:
    """**Die tragende Wache dieses Befundes.**

    Sie verlangt keine Nachmessung - nur, dass eine Nennung nicht
    unbeantwortet liegen bleibt.
    """

    def test_jede_genannte_offene_richtung_ist_verzeichnet(self) -> None:
        offen = [
            (r, _genannt_in(r, VERWEIS))
            for r in OFFEN
            if _genannt_in(r, VERWEIS) and not _verzeichnet(r)
        ]

        assert not offen, "\n".join(
            f"Befund {r.befund} '{r.name}' wird in {wo} genannt, traegt aber "
            f"weder 'zuletzt' noch einen Eintrag in GELESEN - lesen und eines "
            f"von beiden setzen (Befund 462)."
            for r, wo in offen
        )

    def test_die_wache_sieht_ueberhaupt_etwas(self) -> None:
        """Eine Wache ohne Grundgesamtheit prueft nichts. Waere keine offene
        Richtung je genannt, ginge sie gruen durch und waere wertlos."""
        genannt = [r for r in OFFEN if _genannt_in(r, VERWEIS)]

        assert genannt, "keine offene Richtung wird spaeter genannt"

    def test_und_der_fall_aus_462_ist_darunter(self) -> None:
        """Der Deckel ist die Richtung, an der das aufgefallen ist - sie muss
        in der Grundgesamtheit stehen, sonst misst die Wache daneben."""
        deckel = next(r for r in OFFEN if r.name == "Gedeckelter Ausstieg")

        assert deckel.zuletzt == 416
        assert _genannt_in(deckel, VERWEIS), "sonst prueft die Wache ihn nicht"
        assert _verzeichnet(deckel)

    def test_nachziehen_loescht_den_hinweis(self) -> None:
        """**Die Wache nervt nicht.** Gezaehlt werden nur Nennungen **nach**
        der massgeblichen Fundstelle, also verschwindet genau die Nennung,
        die zum Nachziehen gefuehrt hat - der erste Anlauf dieses Tests hat
        noch 416 in der Liste erwartet und ist daran gefallen.

        Der Unterschied ist der Zweck des Feldes: ``zuletzt`` sagt nicht
        "gesehen", sondern "ab hier gilt etwas Neues".
        """
        deckel = next(r for r in OFFEN if r.name == "Gedeckelter Ausstieg")

        assert deckel.massgeblich == 416
        assert 416 not in _genannt_in(deckel, VERWEIS)
        assert all(n > 416 for n in _genannt_in(deckel, VERWEIS))


class TestWarumNichtWeiterGefasst:
    """**Die verworfenen Fassungen, als Messung festgehalten.**

    Diese Tests fallen auch dann, wenn eine weitere Fassung einmal brauchbar
    waere. Das ist Absicht: Sie sind kein Zahlenschutz, sondern ein
    Entscheidungsvermerk. Werden sie rot, heisst das "neu messen und neu
    entscheiden" und nicht "Zahl nachziehen".

    Gemessen als **Verhaeltnis** und nicht als Zahl - eine Wache an einer
    absoluten Trefferzahl wird rot, sobald jemand einen Befund schreibt, und
    genau die Bauart hat Befund 454 verworfen.
    """

    def test_jeder_eintrag_nennt_seine_vorgaenger(self) -> None:
        """Die erste Fassung, und warum sie Rauschen ist: Zitieren ist nicht
        Nachmessen (Befund 118).

        **Gezaehlt werden Eintraege, nicht Nennungen.** Mein erster Anlauf hat
        die Paare gezaehlt und als Eintraege gemeldet - 157 statt 99.
        """
        betroffen = {
            q.befund
            for q in ALLE
            for roh in set(VERWEIS.findall(q.ergebnis))
            if int(roh) < q.befund
            and any(z.befund == int(roh) and z.massgeblich < q.befund for z in ALLE)
        }

        assert len(betroffen) / len(ALLE) > 0.25, (
            f"{len(betroffen)} von {len(ALLE)} - wenn Verweise auf aeltere "
            f"Eintraege selten geworden sind, lohnt die weite Fassung neu "
            f"gemessen zu werden."
        )

    def test_nackte_zahlen_treffen_mehr_richtungen(self) -> None:
        weit = {r.befund for r in OFFEN if _genannt_in(r, NACKT)}
        eng = {r.befund for r in OFFEN if _genannt_in(r, VERWEIS)}

        assert eng < weit, "sonst misst dieser Test nichts"

    def test_und_zwar_belegbar_falsch(self) -> None:
        """Der Grund, die weite Fassung zu lassen: Mindestens eine ihrer
        zusaetzlichen Richtungen wird von **keinem** Eintrag ausdruecklich
        genannt - die Zahl stand dort als Menge, nicht als Verweis."""
        nur_nackt = [
            r
            for r in OFFEN
            if _genannt_in(r, NACKT) and not _genannt_in(r, VERWEIS)
        ]

        assert nur_nackt, "keine Richtung haengt allein an einer nackten Zahl"
        assert len(nur_nackt) > 1, (
            "nur ein einziger Fall - dann waere die weite Fassung fast so "
            "scharf wie die enge und gehoerte neu gemessen."
        )


class TestGelesenIstNichtNachgemessen:
    """Die zweite Haelfte der Wache: ``GELESEN`` darf kein stilles
    ``zuletzt`` werden."""

    def test_die_nutzerentscheidung_ist_gelesen_und_nicht_nachgemessen(
        self,
    ) -> None:
        """Befund 446 liegt beim Nutzer. Gelesen ist seine Erwaehnung in 458,
        nachgemessen ist nichts - und so muss es im Register stehen."""
        frage = next(
            r
            for r in OFFEN
            if r.name.startswith("Darf ein strukturell uebersprungenes Gate")
        )

        assert frage.zuletzt is None, "eine Nutzerentscheidung misst niemand"
        assert frage.name in GELESEN
        assert _verzeichnet(frage)

    @pytest.mark.parametrize("name", sorted(GELESEN))
    def test_jeder_gelesen_eintrag_nennt_eine_richtung_die_es_gibt(
        self, name: str
    ) -> None:
        """Dieselbe Regel wie in ``test_nachmessung``, hier je Eintrag - ein
        verwaister Schluessel ist eine Entscheidung ueber nichts."""
        assert any(r.name == name for r in (*GESCHLOSSEN, *OFFEN)), name
