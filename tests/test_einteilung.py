"""Die Kuerzung nannte nicht, welche Einteilung sie bindet - Befund 410.

``effektive_stichprobe`` laesst acht Einteilungen laufen und nimmt die
strengste. Welche das war, hat sie weggeworfen - und an dieser Kuerzung haengt
der bindende Engpass des Projekts: Dem Deflated Sharpe fehlen 75 wirksame
Beobachtungen, und 41 davon kostet sie.

Ob mehr Quartale, mehr Beine oder weniger gleichzeitige Positionen helfen,
sind drei verschiedene Antworten. Ohne die bindende Einteilung ist keine davon
zu begruenden.

Dieselbe Lehre wie ``GateResult.bedingung`` (Befund 395): Der Wert allein sagt
nicht, woran er haengt.
"""

from __future__ import annotations

import pytest

from research.grenzgedaechtnis import LEITER, REICHWEITEN, bindend
from research.unabhaengigkeit import Effektivwert, effektive_stichprobe


def _bloecke(
    anzahl: int, je: int, versatz: float = 0.0, *, saat: int = 7
) -> list[list[float]]:
    """Bloecke mit einem Blockmittel - 'versatz' erzeugt die Abhaengigkeit."""
    import random

    wuerfel = random.Random(saat)
    gebaut = []
    for i in range(anzahl):
        mitte = versatz * (i - anzahl / 2)
        gebaut.append([mitte + wuerfel.gauss(0, 1) for _ in range(je)])
    return gebaut


class TestDieZahlNenntIhreUrsache:
    def test_die_bindende_einteilung_steht_im_ergebnis(self) -> None:
        locker = _bloecke(12, 6, 0.0, saat=1)
        streng = _bloecke(12, 6, 1.5, saat=2)

        ergebnis = effektive_stichprobe(
            72, None, locker, weitere=[streng], namen=["Streng"]
        )

        assert ergebnis.effektiv < 72
        assert ergebnis.einteilung == "Streng"

    def test_bindet_das_fenster_heisst_es_so(self) -> None:
        """'bloecke' ist die Fenstereinteilung und heisst immer so - auch
        wenn der Aufrufer keine Namen uebergibt."""
        streng = _bloecke(12, 6, 1.5, saat=3)
        locker = _bloecke(12, 6, 0.0, saat=4)

        ergebnis = effektive_stichprobe(
            72, None, streng, weitere=[locker], namen=["Locker"]
        )

        assert ergebnis.einteilung == "Walk-Forward-Fenster"

    def test_ohne_namen_gibt_es_gezaehlte(self) -> None:
        """Die alten Aufrufer uebergeben keine Namen. Sie sollen weiter
        rechnen - nur die Auskunft ist dann durchnummeriert."""
        locker = _bloecke(12, 6, 0.0, saat=5)
        streng = _bloecke(12, 6, 1.5, saat=6)

        ergebnis = effektive_stichprobe(72, None, locker, weitere=[streng])

        assert ergebnis.einteilung == "Einteilung 1"

    def test_ohne_kuerzung_bleibt_das_feld_leer_oder_nennt_die_lockere(
        self,
    ) -> None:
        """Ohne Blockdaten gibt es keine Einteilung zu nennen."""
        assert effektive_stichprobe(100).einteilung == ""
        assert effektive_stichprobe(100, None, []).einteilung == ""

    def test_die_rechnung_aendert_sich_nicht(self) -> None:
        """Die Gegenprobe zum Einbau: Benannt oder nicht, es kommt dasselbe
        heraus. Eine Auskunft, die das Ergebnis verschiebt, waere keine."""
        locker = _bloecke(14, 5, 0.0, saat=11)
        streng = _bloecke(14, 5, 1.2, saat=12)

        ohne = effektive_stichprobe(70, None, locker, weitere=[streng])
        mit = effektive_stichprobe(
            70, None, locker, weitere=[streng], namen=["Streng"]
        )

        assert (ohne.effektiv, ohne.icc, ohne.p_wert) == (
            mit.effektiv,
            mit.icc,
            mit.p_wert,
        )


class TestDerBerichtSagtEsAuch:
    def test_er_nennt_die_einteilung(self) -> None:
        wert = Effektivwert(
            roh=156, effektiv=115, icc=0.258, p_wert=0.005, bloecke=33,
            einteilung="Kalenderquartal",
        )

        assert "Gebunden am Kalenderquartal." in wert.bericht()

    def test_und_ohne_sie_bleibt_der_satz_weg(self) -> None:
        wert = Effektivwert(
            roh=156, effektiv=115, icc=0.258, p_wert=0.005, bloecke=33
        )

        assert "Gebunden am" not in wert.bericht()


class TestWasGemessenIst:
    """Die Leiter je Zelle, gegengeprueft gegen 'referenz'."""

    def test_drei_zellen_mit_acht_sprossen(self) -> None:
        assert set(LEITER) == {
            "gemeldet",
            "durchgehend mit Beingrenzen",
            "kontogeschuetzt",
        }
        for name, zeilen in LEITER.items():
            assert len(zeilen) == 8, name

    def test_am_gemeldeten_punkt_bindet_das_quartal(self) -> None:
        name, bloecke, icc, p, faktor, n = bindend("gemeldet")

        assert name == "Kalenderquartal"
        assert (bloecke, n) == (33, 115)
        assert icc == pytest.approx(0.2580)
        assert p == pytest.approx(0.0050)
        assert faktor == pytest.approx(0.7372)

    def test_am_kontogeschuetzten_der_kalendertag(self) -> None:
        name, _, _, _, _, n = bindend("kontogeschuetzt")

        assert name == "Kalendertag"
        assert n == 159

    def test_und_je_zelle_eine_andere(self) -> None:
        """Der Fund: Welche Abhaengigkeit das Gate findet, haengt am
        Messaufbau."""
        namen = {zelle: bindend(zelle)[0] for zelle in LEITER}

        assert len(set(namen.values())) == 3

    def test_die_zellen_treffen_die_referenzpunkte(self) -> None:
        """Die Gegenprobe, die beim Messen einen falschen Aufbau gefunden
        hat: Mein durchgehender Lauf gab zuerst 98 Trades statt 160 - das ist
        die Zelle **mit** Beingrenzen, nicht der kontogeschuetzte Punkt."""
        from research.referenz import KONTOPUNKT, SPOTPUNKT

        assert bindend("gemeldet")[5] == SPOTPUNKT.effektiv
        assert bindend("kontogeschuetzt")[5] == KONTOPUNKT.effektiv
        assert bindend("durchgehend mit Beingrenzen")[5] == 92

    def test_die_reichweiten_tragen_dieselbe_angabe(self) -> None:
        je_name = {r.name: r for r in REICHWEITEN}

        assert je_name["gemeldet"].einteilung == "Kalenderquartal"
        assert je_name["kontogeschuetzt"].einteilung == "Kalendertag"

    def test_und_widersprechen_der_leiter_nicht(self) -> None:
        """Zwei gepflegte Listen zur selben Sache laufen auseinander
        (Befund 408). Hier wird die eine aus der anderen geprueft."""
        for reichweite in REICHWEITEN:
            name, _, icc, p, _, n = bindend(reichweite.name)

            assert reichweite.einteilung == name
            assert reichweite.icc == pytest.approx(icc)
            assert reichweite.p_wert == pytest.approx(p)
            assert reichweite.effektiv == n


class TestDerIccIstNichtDieAuskunft:
    """Die Falle in der Tabelle, und sie ist gemessen: Der Kalendertag fuehrt
    die ICC-Spalte und kuerzt fast nichts."""

    def test_der_hoechste_icc_bindet_nicht_am_gemeldeten_punkt(self) -> None:
        zeilen = LEITER["gemeldet"]
        hoechster = max(zeilen, key=lambda z: z[2])

        assert hoechster[0] == "Kalendertag"
        assert hoechster[2] == pytest.approx(0.9548)
        assert hoechster[4] == pytest.approx(1.0)
        assert bindend("gemeldet")[0] != hoechster[0]

    def test_weil_die_bloecke_fast_einzelstuecke_sind(self) -> None:
        tag = next(z for z in LEITER["gemeldet"] if z[0] == "Kalendertag")

        assert tag[1] == 143
        assert tag[1] / 156 > 0.9

    def test_der_kopf_warnt_davor(self) -> None:
        import inspect

        import research.grenzgedaechtnis as g
        from tests.quelltext import nur_prosa

        text = (g.__doc__ or "") + nur_prosa(inspect.getsource(g))

        assert "nach dem Faktor, nicht nach dem ICC" in text


class TestWasOffenBleibt:
    def test_warum_die_quartalskorrelation_faellt_ist_nicht_gemessen(
        self,
    ) -> None:
        """Dort liegen die 40 Beobachtungen Unterschied, und eine Vermutung
        waere hier das Falsche."""
        import inspect

        import research.grenzgedaechtnis as g
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(g))

        assert "Warum sie faellt, ist nicht gemessen" in text

    def test_die_zahlen_dazu_stehen_da(self) -> None:
        gemeldet = next(
            z for z in LEITER["gemeldet"] if z[0] == "Kalenderquartal"
        )
        konto = next(
            z for z in LEITER["kontogeschuetzt"] if z[0] == "Kalenderquartal"
        )

        assert gemeldet[3] < 0.05 < konto[3]
        assert gemeldet[2] > konto[2]


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_bindende_einteilung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 410)

        assert "Kalenderquartal" in eintrag.ergebnis
        assert "41 von 156" in eintrag.ergebnis

    def test_und_den_eigenen_fehlgriff(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 410)

        assert "98 Trades statt 160" in eintrag.ergebnis

    def test_und_was_offen_bleibt(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 410)

        assert "nicht gemessen" in eintrag.ergebnis

    def test_und_409_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 409).zuletzt == 410
