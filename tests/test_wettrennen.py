"""Suchen hebt die Huerde - und der Vergleich zweier Vorfaktoren entscheidet.

Drei Tests tragen diese Datei:

``test_die_schaetzung_aus_der_bestenliste_ist_widerlegt`` - Der erste Anlauf
schaetzte Mittel und Streuung aus den Kandidaten der Bestenliste und kam zu
"Suchen lohnt sich sofort". Mit jenen Zahlen waere der Bestwert nach 166
Versuchen bei 0,444 zu erwarten gewesen statt bei 0,257. Die Schaetzung
erklaert den eigenen Verlauf nicht.

``test_die_suche_gewinnt_nur_ueber_der_nullstreuung`` - Beide Groessen wachsen
mit derselben Extremwertkonstante. Es entscheidet allein, welcher Vorfaktor
groesser ist, und die Huerde steigt mit genau der Streuung des reinen Zufalls.

``test_der_gewinn_ist_logarithmisch`` - Warum "mehr suchen" der schwache Hebel
ist: Eine Verdopplung der Versuche bringt jedes Mal weniger.
"""

from __future__ import annotations

import math

import pytest

from research.wettrennen import (
    Rennen,
    extremwert,
    kalibriere,
    nullstreuung,
    spanne,
)

#: Der gemessene Stand, an dem kalibriert wird.
STAND = {"bester": 0.2569, "versuche": 166, "trades": 154}

#: Die Schaetzung aus den sechs Regelfamilien der Bestenliste - die naive,
#: die sich selbst widerlegt.
AUS_DER_BESTENLISTE = {"mittel": 0.1685, "streuung": 0.1019}


def rennen(**rest) -> Rennen:
    return Rennen(**STAND, **rest)


class TestExtremwert:
    def test_mehr_ziehungen_heben_das_erwartete_maximum(self) -> None:
        assert extremwert(1000) > extremwert(100) > extremwert(10)

    def test_eine_einzige_ziehung_hat_keinen_vorsprung(self) -> None:
        assert extremwert(1) == 0.0

    def test_der_gewinn_ist_logarithmisch(self) -> None:
        """**Der dritte tragende Test.**

        ``c(N)`` waechst wie ``sqrt(2 ln N)``. Jede Verdopplung bringt weniger
        als die vorige - deshalb ist "mehr Versuche" ein schwacher Hebel, und
        zwar unabhaengig davon, wie gut die Ideen sind.
        """
        zuwaechse = [
            extremwert(n * 2) - extremwert(n) for n in (100, 1_000, 10_000, 100_000)
        ]

        assert zuwaechse == sorted(zuwaechse, reverse=True)
        assert all(z > 0 for z in zuwaechse)
        # Die Gumbel-Naeherung liegt unter sqrt(2 ln N) und kommt ihr nur
        # asymptotisch nahe - bei 10.000 sind es 3,86 gegen 4,29. Geprueft
        # wird deshalb die Groessenordnung und die Richtung, nicht Gleichheit.
        for n in (10_000, 1_000_000):
            grenze = math.sqrt(2 * math.log(n))
            assert 0.8 * grenze < extremwert(n) < grenze

    def test_die_nullstreuung_faellt_mit_der_stichprobe(self) -> None:
        """Mehr Trades machen den Schaetzer genauer - und damit die Huerde
        flacher. Das ist der andere Grund, warum Trade-Zahl zaehlt."""
        assert nullstreuung(1000) < nullstreuung(154)
        assert nullstreuung(154) == pytest.approx((1 / 153) ** 0.5)


class TestKalibrierung:
    def test_die_streuung_kommt_aus_dem_verlauf(self) -> None:
        """Rueckwaerts gerechnet: Was muss sie gewesen sein, damit 166
        Versuche genau diesen Bestwert hervorbringen?"""
        streuung = kalibriere(bester=0.2569, versuche=166, mittel=0.0)

        assert streuung is not None
        assert streuung * extremwert(166) == pytest.approx(0.2569)

    def test_ein_mittel_ueber_dem_bestwert_ist_unvereinbar(self) -> None:
        """Eine negative Streuung waere keine Antwort, sondern ein
        Rechenfehler mit Vorzeichen."""
        assert kalibriere(bester=0.2569, versuche=166, mittel=0.30) is None

    def test_ein_niedrigeres_mittel_verlangt_mehr_streuung(self) -> None:
        """Und ist damit die **guenstigere** Annahme - sie laesst die Suche
        schneller aufholen. Das gehoert dazu, wenn man die Annahme waehlt."""
        tief = kalibriere(bester=0.2569, versuche=166, mittel=-0.05)
        null = kalibriere(bester=0.2569, versuche=166, mittel=0.0)

        assert tief is not None and null is not None
        assert tief > null

    def test_die_schaetzung_aus_der_bestenliste_ist_widerlegt(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Die sechs Kandidaten der Bestenliste sind die Ueberlebenden aus 166
        Versuchen, nicht sechs Ziehungen. Ihre Streuung ist die der Elite, ihr
        Mittel viel zu hoch - und mit ihnen waere der Bestwert bei 0,444 zu
        erwarten gewesen.

        Genau diese Schaetzung hatte im ersten Anlauf ergeben, dass sich schon
        zehn weitere Versuche lohnen. Der Konsistenztest verwirft sie.
        """
        r = rennen()
        erwartet = AUS_DER_BESTENLISTE["mittel"] + AUS_DER_BESTENLISTE[
            "streuung"
        ] * extremwert(166)

        assert erwartet > 0.44, f"gemessen {erwartet:.4f}"
        assert not r.erklaert_den_verlauf(**AUS_DER_BESTENLISTE)
        assert r.erklaert_den_verlauf(mittel=0.0, streuung=r.streuung or 0.0)


class TestRennen:
    def test_die_suche_gewinnt_nur_ueber_der_nullstreuung(self) -> None:
        """**Der zweite tragende Test.**

        Huerde und bester Fund wachsen beide mit ``c(N)``. Es entscheidet
        allein der Vorfaktor - und die Huerde steigt mit genau der Streuung
        des reinen Zufalls, ``1/sqrt(n-1)``.
        """
        knapp_darueber = rennen(mittel=0.0)
        knapp_darunter = rennen(mittel=0.05)

        assert knapp_darueber.streuung > knapp_darueber.nullstreuung
        assert knapp_darunter.streuung < knapp_darunter.nullstreuung
        assert knapp_darueber.schneller_als_die_huerde
        assert not knapp_darunter.schneller_als_die_huerde
        assert knapp_darunter.schnittpunkt() is None

    def test_beide_groessen_steigen_mit_den_versuchen(self) -> None:
        r = rennen()

        assert r.huerde(1000) > r.huerde(166)
        assert r.erwartet(1000) > r.erwartet(166)

    def test_der_schnittpunkt_liegt_jenseits_jedes_budgets(self) -> None:
        """Der Befund selbst: Die Suche gewinnt - aber nicht in diesem
        Jahrhundert. Das Suchbudget bricht bei 230 Versuchen ab."""
        r = rennen(mittel=0.0)
        schnitt = r.schnittpunkt()

        assert schnitt is not None
        assert schnitt > 10_000
        assert r.abstand(230) < 0, "Beim Budgetabbruch fehlt noch etwas"

    def test_der_abstand_schliesst_sich_monoton(self) -> None:
        r = rennen(mittel=0.0)
        abstaende = [r.abstand(v) for v in (166, 500, 5_000, 50_000)]

        assert abstaende == sorted(abstaende)
        assert all(a < 0 for a in abstaende[:3])

    def test_heute_reicht_es_nicht(self) -> None:
        """Sonst prueft die ganze Datei etwas Gegenstandsloses."""
        r = rennen()

        assert r.abstand(166) < 0
        assert r.huerde(166) == pytest.approx(0.292, abs=0.01)


class TestUrteil:
    def test_ohne_aussicht_wird_es_benannt(self) -> None:
        urteil = rennen(mittel=0.05).urteil()

        assert "nie ein" in urteil
        assert "neutralisiert die Zufallssuche" in urteil

    def test_mit_aussicht_stehen_stelle_und_preis_dabei(self) -> None:
        urteil = rennen(mittel=0.0).urteil(budget=230)

        assert "holt auf" in urteil
        assert "Suchbudgets bei 230 Versuchen" in urteil
        assert "schwache Hebel" in urteil

    def test_eine_unvereinbare_annahme_wird_gemeldet(self) -> None:
        assert "nicht erklaeren" in rennen(mittel=0.30).urteil()

    def test_die_tabelle_zeigt_den_abstand(self) -> None:
        text = rennen(mittel=0.0).tabelle((0, 64, 1000))

        assert "Abstand" in text
        assert "-0.0" in text, "Der Abstand ist negativ und muss es zeigen"


class TestSpanne:
    def test_jenseits_der_grenze_ist_nicht_dasselbe_wie_nie(self) -> None:
        """**Ein Ehrlichkeitsfehler, der in der ersten Fassung drinstand.**

        Bei Mittel +0,02 liegt die Ideenstreuung 8 % ueber dem Zufall - die
        Suche kommt also an, nur spaeter als bis 10^9 gerechnet. Die Tabelle
        schrieb dafuer "nie", und das ist schaerfer als die Rechnung hergibt.
        """
        knapp = rennen(mittel=0.02)
        gar_nicht = rennen(mittel=0.05)

        assert knapp.schneller_als_die_huerde
        assert not gar_nicht.schneller_als_die_huerde
        assert "jenseits" in knapp.wo_holt_sie_auf()
        assert gar_nicht.wo_holt_sie_auf() == "nie"

    def test_eine_erreichbare_stelle_wird_beziffert(self) -> None:
        assert "Versuche" in rennen(mittel=0.0).wo_holt_sie_auf()

    def test_die_annahme_entscheidet_ueber_das_ergebnis(self) -> None:
        """Die einzige freie Groesse bekommt eine eigene Tabelle, statt dass
        eine Zahl im Text so dasteht, als waere sie gemessen."""
        text = spanne(**STAND, mittelwerte=(-0.05, 0.0, 0.05))

        assert "Versuche" in text
        assert "nie" in text

    def test_unvereinbare_annahmen_stehen_als_solche_da(self) -> None:
        text = spanne(**STAND, mittelwerte=(0.30,))

        assert "unvereinbar" in text
