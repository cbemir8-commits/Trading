"""Haengt das Ergebnis an einer Annahme, die die Engine mangels Daten trifft?

Drei Tests tragen diese Datei:

``test_das_ergebnis_haengt_nicht_an_der_annahme`` - Der Kern. Der Bestand,
zweimal gerechnet, ist bitgleich: In neun Jahren hat keine Tageskerze zugleich
Stop und Take-Profit beruehrt, waehrend eine Position offen war.

``test_ohne_abdeckung_traegt_die_probe_nicht`` - Die Wache gegen den stillen
Fehlschlag, vor dem die Engine im eigenen Docstring warnt. Kommen die
Feinkerzen gar nicht an, ist "kein Unterschied" eine Aussage ueber die
Datenpipeline, verkleidet als Aussage ueber die Strategie.

``test_ohne_zwei_ausstiegsarten_ist_gleichheit_trivial`` - Die zweite Wache.
Ohne Take-Profits gibt es keine Reihenfolge, ueber die man streiten koennte.
"""

from __future__ import annotations

import pytest

from research.aufloesung import (
    MEHRDEUTIG,
    MINDESTQUOTE,
    Aufloesung,
    Messung,
)

#: Die gemessenen Laeufe des Bestands auf BTC + ETH, Tageskerzen, 500 EUR,
#: Versuchsstand 177. Nachzurechnen mit ``cli aufloesung``.
PESSIMISTISCH = Messung("pessimistisch", 152, 13.47, 10.64, 1.473, 7, 11)
AUFGELOEST = Messung("aufgeloest", 152, 13.47, 10.64, 1.473, 7, 11)
GRUENDE = {"signal_exit": 74, "stop_loss": 68, "take_profit": 10}


def probe(**abweichung) -> Aufloesung:
    daten = {
        "pessimistisch": PESSIMISTISCH,
        "aufgeloest": AUFGELOEST,
        "feine_balken": 9128,
        "balken": 11300,
        "ausstiegsgruende": dict(GRUENDE),
    }
    daten.update(abweichung)
    return Aufloesung(**daten)


class TestBefund:
    def test_das_ergebnis_haengt_nicht_an_der_annahme(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Nicht "der Unterschied ist klein", sondern: es gibt keinen. Deshalb
        prueft ``haengt_an_der_annahme`` streng gegen null - eine Toleranz
        waere hier die falsche Frage.
        """
        p = probe()

        assert p.belastbar
        assert p.groesster_unterschied == 0.0
        assert not p.haengt_an_der_annahme
        urteil = p.urteil()
        assert "haengt nicht an der Annahme" in urteil
        assert "80.8%" in urteil

    def test_die_probe_gilt_nur_fuer_diesen_kandidaten(self) -> None:
        """Ein Kandidat mit engem Stop und nahem Ziel wuerde beides oft in
        derselben Kerze beruehren. Das Urteil sagt das dazu, statt einen
        allgemeinen Freibrief auszustellen."""
        assert "eine Probe und keine einmalige Feststellung" in probe().urteil()

    def test_ein_unterschied_wird_beziffert_und_eingeordnet(self) -> None:
        """Gegenprobe: Haengt ein Ergebnis doch an der Annahme, nennt das
        Urteil die Betraege - und verbietet, sie einem Kandidaten
        gutzuschreiben, ohne die uebrigen gleich zu behandeln."""
        anders = probe(
            aufgeloest=Messung("aufgeloest", 152, 14.90, 9.80, 1.610, 8, 11)
        )

        assert anders.haengt_an_der_annahme
        assert anders.unterschiede["Rendite"] == pytest.approx(1.43, abs=0.01)
        assert anders.unterschiede["Rueckgang"] == pytest.approx(-0.84, abs=0.01)
        assert anders.unterschiede["Gates"] == 1.0
        urteil = anders.urteil()
        assert "haengt an der Annahme" in urteil
        assert "nur schlechter aussehen lassen, nie besser" in urteil
        assert "ohne die uebrigen Kandidaten gleich zu behandeln" in urteil


class TestWachen:
    def test_ohne_abdeckung_traegt_die_probe_nicht(self) -> None:
        """**Die Wache gegen den stillen Fehlschlag.**

        Die Engine warnt im eigenen Docstring davor: Passen die Zeitstempel
        nicht, findet ``searchsorted`` nichts und die Engine faellt lautlos
        zurueck. Ohne diese Pruefung waere "kein Unterschied" dann eine
        Aussage ueber die Datenpipeline.
        """
        leer = probe(feine_balken=0)

        assert leer.feinquote == 0.0
        assert not leer.abdeckung_reicht
        assert not leer.belastbar
        urteil = leer.urteil()
        assert "traegt nicht" in urteil
        assert "stille Fehlschlag" in urteil
        assert "haengt nicht an der Annahme" not in urteil

    def test_die_grenze_liegt_bei_der_haelfte(self) -> None:
        """Eine gesetzte Grenze, keine hergeleitete - sie steht im Modul,
        damit die Willkuer sichtbar ist."""
        knapp_drunter = probe(feine_balken=int(11300 * MINDESTQUOTE) - 1)
        knapp_drueber = probe(feine_balken=int(11300 * MINDESTQUOTE) + 1)

        assert not knapp_drunter.abdeckung_reicht
        assert knapp_drueber.abdeckung_reicht

    def test_ohne_zwei_ausstiegsarten_ist_gleichheit_trivial(self) -> None:
        """**Die zweite Wache.**

        Ohne Take-Profits kann keine Kerze beide Marken zugleich beruehren.
        Gleichheit ist dann kein Befund, sondern eine Selbstverstaendlichkeit.
        """
        nur_stops = probe(ausstiegsgruende={"signal_exit": 90, "stop_loss": 62})

        assert not nur_stops.gibt_es_zu_ordnen
        assert not nur_stops.belastbar
        assert "nichts zu ordnen" in nur_stops.urteil()

    def test_beide_arten_kommen_beim_bestand_vor(self) -> None:
        """Deshalb ist das Ergebnis informativ: 68 Stops und 10 Take-Profits
        sind reichlich Gelegenheit fuer eine mehrdeutige Kerze."""
        p = probe()

        assert p.gibt_es_zu_ordnen
        assert p.ausstiegsgruende["stop_loss"] == 68
        assert p.ausstiegsgruende["take_profit"] == 10
        assert "signal_exit" not in MEHRDEUTIG, (
            "ein Regelausstieg ist nie mehrdeutig - er hat keine Marke"
        )

    def test_ohne_balken_kippt_nichts(self) -> None:
        leer = probe(feine_balken=0, balken=0)

        assert leer.feinquote == 0.0
        assert not leer.abdeckung_reicht


class TestTabelle:
    def test_die_tabelle_nennt_beide_laeufe_und_die_quote(self) -> None:
        text = probe().tabelle()

        assert "pessimistisch" in text and "aufgeloest" in text
        assert "9128 von 11300" in text
        assert "80.8%" in text
        assert "stop_loss 68" in text

    def test_ohne_gruende_bleibt_die_zeile_weg(self) -> None:
        assert "Ausstiege" not in probe(ausstiegsgruende={}).tabelle()
