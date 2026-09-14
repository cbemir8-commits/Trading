"""Der Abstand ohne Gerade - Befund 286.

Befund 285 hat den Preis in Reststreuungen verweigert, weil die Gerade, auf
der er stand, an einer einzigen Regel haengt. Verweigert war damit das
Werkzeug, das die Entscheidung traegt: **Lohnt sich ein Versuch?**

Diese Tests pruefen die Antwort, die keine Anpassung braucht - die Luecke
jeder Regel zu ihrer eigenen Latte - und die beiden Verweigerungen, ohne die
das Modul eine Zahl liefern wuerde, wo keine steht.

Die Faelle sind so gebaut, dass die Antwort **vorher feststeht**: 0 von 20
ohne Treffer ergibt bei 95 % Vertrauen genau ``1 - 0,05^(1/20)``, und das
laesst sich von Hand nachrechnen.

**Befund 287 hat die Obergrenze berichtigt**: Sie stand auf der Zahl der
Regeln, und achtzehn Regeln sind keine achtzehn unabhaengigen Einfaelle. Die
Tests dazu stehen unten in ``TestAchtzehnRegelnSindKeineAchtzehnEinfaelle``.
"""

from __future__ import annotations

import pytest

from research.vorratslage import Abstand, Lage, lage_aus, obergrenze_der_quote


def abstaende(*paare: tuple[float, float]) -> list[Abstand]:
    """``(Guete, Latte)`` je Regel - n_eff spielt fuer die Luecke keine Rolle."""
    return [
        Abstand(name=f"R{i}", n_eff=50 + i, guete=g, noetig=n)
        for i, (g, n) in enumerate(paare)
    ]


class TestDieLuecke:
    def test_sie_ist_der_unterschied_zur_eigenen_latte(self) -> None:
        a = Abstand(name="X", n_eff=58, guete=2.484, noetig=3.564)

        assert a.luecke == pytest.approx(1.080)
        assert not a.geraeumt

    def test_geraeumt_heisst_darueber_oder_gleichauf(self) -> None:
        assert Abstand(name="X", n_eff=50, guete=3.6, noetig=3.5).geraeumt
        assert Abstand(name="X", n_eff=50, guete=3.5, noetig=3.5).geraeumt
        assert not Abstand(name="X", n_eff=50, guete=3.4, noetig=3.5).geraeumt

    def test_der_anteil_ist_skalenfrei(self) -> None:
        """Dieselbe Luecke ist bei hohen Latten weniger weit weg.

        2,4 gegen 3,5 fehlt genauso viel wie 12,4 gegen 13,5 - und ist etwas
        ganz anderes.
        """
        nah = Abstand(name="A", n_eff=50, guete=12.4, noetig=13.5)
        fern = Abstand(name="B", n_eff=50, guete=2.4, noetig=3.5)

        assert nah.luecke == pytest.approx(fern.luecke)
        assert nah.anteil > fern.anteil


class TestDieLage:
    def test_am_naechsten_kommt_die_kleinste_luecke(self) -> None:
        lage = Lage(tuple(abstaende((2.0, 3.5), (2.9, 3.5), (1.0, 3.5))))

        assert lage.naechster.guete == pytest.approx(2.9)
        assert lage.naechster.luecke == pytest.approx(0.6)

    def test_die_streuung_kommt_aus_dem_vorrat_und_nicht_aus_einer_geraden(
        self,
    ) -> None:
        """**Der Unterschied zu Befund 179.** Dort war die Einheit die
        Reststreuung um eine angepasste Gerade - eine Groesse, die mit der
        Anpassung steht und faellt. Hier ist es die Breite der gemessenen
        Gueten selbst.
        """
        import statistics

        lage = Lage(tuple(abstaende((1.0, 3.5), (2.0, 3.5), (3.0, 3.5))))

        assert lage.streuung == pytest.approx(statistics.stdev([1.0, 2.0, 3.0]))
        assert lage.in_streuungen == pytest.approx(0.5 / lage.streuung)

    def test_eine_einzelne_regel_hat_keine_streuung(self) -> None:
        """Und dann gibt es die Einheit nicht - statt sie auf null zu setzen
        und durch null zu teilen."""
        lage = Lage(tuple(abstaende((2.0, 3.5))))

        assert lage.streuung is None
        assert lage.in_streuungen is None

    def test_ohne_regeln_gibt_es_keine_lage(self) -> None:
        with pytest.raises(ValueError, match="keine Lage"):
            Lage(())
        assert lage_aus([]) is None

    def test_der_median_steht_neben_dem_besten(self) -> None:
        """Sonst liest sich "am naechsten kommt X" wie eine Aussage ueber den
        Vorrat, und es ist eine ueber seine beste Zeile."""
        lage = Lage(tuple(abstaende((2.9, 3.5), (1.0, 3.5), (0.5, 3.5))))

        assert lage.naechster.luecke == pytest.approx(0.6)
        assert lage.median == pytest.approx(2.5)


class TestDieObergrenzeDerQuote:
    """**Der Kern von Befund 286.**

    "Keine von achtzehn raeumt ihre Latte" ist keine Null. Bei einer wahren
    Quote von 10 % waeren achtzehn Fehlschlaege mit 15 % Wahrscheinlichkeit
    genau das, was man sieht.
    """

    def test_sie_ist_von_hand_nachrechenbar(self) -> None:
        assert obergrenze_der_quote(20) == pytest.approx(1 - 0.05 ** (1 / 20))
        assert obergrenze_der_quote(18) == pytest.approx(0.1532, abs=0.001)

    def test_mehr_messungen_druecken_sie(self) -> None:
        reihe = [obergrenze_der_quote(n) for n in (5, 10, 18, 50, 100)]

        assert reihe == sorted(reihe, reverse=True)
        assert reihe[0] > 0.4, "fuenf Messungen schliessen fast nichts aus"
        assert reihe[-1] < 0.05

    def test_sie_wird_nie_null(self) -> None:
        """**Das ist die ganze Aussage.** Keine endliche Zahl von
        Fehlschlaegen belegt, dass nichts da ist."""
        assert obergrenze_der_quote(10_000) > 0

    def test_ein_strengeres_vertrauen_hebt_sie(self) -> None:
        assert obergrenze_der_quote(18, vertrauen=0.99) > obergrenze_der_quote(18)

    def test_mit_treffern_wird_die_naeherung_verweigert(self) -> None:
        """Sie gilt fuer den trefferlosen Fall. Bei Treffern gehoerte eine
        richtige Intervallrechnung her, und eine Einzeiler-Formel, die
        trotzdem antwortet, waere eine erfundene Zahl."""
        with pytest.raises(ValueError, match="trefferlose"):
            obergrenze_der_quote(18, 1)

    def test_ohne_messungen_gibt_es_keine_grenze(self) -> None:
        assert obergrenze_der_quote(0) is None

    def test_ein_unmoegliches_vertrauen_ist_ein_fehler(self) -> None:
        with pytest.raises(ValueError, match="zwischen 0 und 1"):
            obergrenze_der_quote(18, vertrauen=1.0)


class TestWasDasUrteilSagt:
    def vorrat(self) -> Lage:
        return Lage(tuple(abstaende((2.9, 3.5), (1.0, 3.5), (0.5, 3.6))))

    def test_es_nennt_die_naechste_regel_mit_zahlen(self) -> None:
        text = self.vorrat().urteil()

        assert "Am naechsten kommt" in text
        assert "2.900" in text and "3.500" in text
        assert "0.600" in text

    def test_es_nennt_die_obergrenze_statt_einer_null(self) -> None:
        text = self.vorrat().urteil()

        assert "Keine von 3 raeumt ihre Latte" in text
        assert "nicht, dass die Quote null ist" in text
        assert "hoechstens" in text

    def test_es_sagt_worueber_es_nicht_spricht(self) -> None:
        """Derselbe Vorbehalt wie in ``vorratsdecke`` - ohne ihn liest sich
        das als Aussage ueber alle Strategien."""
        text = self.vorrat().urteil()

        assert "nicht ueber den Raum aller Strategien" in text
        assert "kein Grund, eine Latte zu senken" in text

    def test_raeumt_eine_regel_steht_dort_keine_obergrenze(self) -> None:
        """**Die Verweigerung in die andere Richtung.** Mit einem Treffer ist
        die Quote zu schaetzen und nicht nach oben abzugrenzen - eine
        Obergrenze waere dort die falsche Auskunft.
        """
        lage = Lage(tuple(abstaende((3.6, 3.5), (1.0, 3.5), (0.5, 3.5))))
        text = lage.urteil()

        assert lage.obergrenze() is None
        assert lage.geraeumt and len(lage.geraeumt) == 1
        assert "1 von 3 raeumen ihre Latte" in text
        assert "hoechstens" not in text
        assert "hier ist zu pruefen" in text


class TestDerGemesseneVorrat:
    """Der Katalog, auf dem Befund 286 steht - 18 Regeln, Tageskerzen,
    Spot-Punkt, Versuchsstand 203.

    Die Latten stehen hier als **gemessene Zahlen eines Tages**, mit den
    Momenten der jeweiligen Regel gerechnet, wie der Bericht sie druckt. Wer
    eine Regel hinzufuegt oder den Zaehler weiterschreibt, aendert sie - das
    ist kein Fehler. Geprueft wird an ihnen die Rechnung.
    """

    #: ``(Name, n_eff, Guete, Latte)`` aus ``cli vorratsdecke``.
    VORRAT = (
        ("Donchian-Ausbruch 55/20", 58, 2.484, 3.564),
        ("Grosser Trendausbruch", 57, 2.428, 3.980),
        ("Trend-Beteiligung 50 Tage", 127, 2.278, 3.361),
        ("Trendfolge Ausbruch", 130, 2.157, 4.235),
        ("Trend-Beteiligung 100 Tage", 76, 1.911, 3.379),
        ("Momentum-Beteiligung", 57, 1.795, 3.439),
        ("Trend-Beteiligung (fair gerechnet)", 29, 1.763, 3.460),
        ("Nur mit der Drift", 41, 1.739, 3.883),
        ("EMA-Kreuzung (Messlatte)", 59, 1.682, 4.166),
        ("Trendbeteiligung EMA200", 63, 1.573, 3.472),
        ("Trendbeteiligung mit Puffer", 86, 1.551, 3.533),
        ("Seltener grosser Ausbruch", 40, 1.508, 3.689),
        ("Trend beide Richtungen", 45, 1.482, 3.563),
        ("Momentum-Beteiligung 90 Tage", 45, 1.266, 3.756),
        ("Langsamer Kreuzer (Messlatte 2)", 16, 1.234, 3.777),
        ("Volatilitaets-Ausbruch", 85, 0.279, 4.130),
        ("Starker Trend, Momentum", 58, -1.891, 3.617),
        ("Momentum Ruecksetzer", 254, -2.164, 4.209),
    )

    def lage(self) -> Lage:
        return Lage(
            tuple(
                Abstand(name=name, n_eff=n, guete=g, noetig=latte)
                for name, n, g, latte in self.VORRAT
            )
        )

    def test_am_naechsten_kommt_der_donchian_ausbruch(self) -> None:
        naechster = self.lage().naechster

        assert naechster.name == "Donchian-Ausbruch 55/20"
        assert naechster.luecke == pytest.approx(1.080, abs=0.001)

    def test_und_keine_einzige_raeumt(self) -> None:
        lage = self.lage()

        assert lage.geraeumt == ()
        assert lage.obergrenze() == pytest.approx(0.1532, abs=0.001)

    def test_die_beste_luecke_ist_kleiner_als_eine_streuung(self) -> None:
        """**Und genau das macht sie lesbar.** Ohne Einheit ist "es fehlen
        1,08" eine Zahl ohne Massstab; gemessen an der Breite des Vorrats
        selbst ist es weniger als ein Schritt von der Mitte nach oben.
        """
        lage = self.lage()

        assert lage.in_streuungen is not None
        assert lage.in_streuungen < 1.0
        assert lage.median > lage.naechster.luecke

    def test_die_obergrenze_ist_kein_freibrief(self) -> None:
        """Sie sagt "hoechstens 15 %", nicht "15 %".

        Bei 203 gezaehlten Versuchen und einer Quote in dieser Groessenordnung
        waere laengst etwas dabei gewesen - der Test haelt fest, dass die
        Grenze weit ueber dem liegt, was die bisherige Suche gezeigt hat.
        """
        lage = self.lage()
        grenze = lage.obergrenze()

        assert grenze is not None
        assert grenze > 1 / len(self.VORRAT) * 0.5
        assert grenze < 0.5, "aus 18 Messungen bleibt trotzdem eine Schranke"


class TestAchtzehnRegelnSindKeineAchtzehnEinfaelle:
    """**Befund 287 - die Berichtigung von 286.**

    Die Obergrenze stand auf ``1 - 0,05^(1/n)``, und ``n`` war die Zahl der
    **Regeln**. Das unterstellt, dass jede Regel ein eigener Einfall ist.
    Nach Regellogik heissen zwoelf von achtzehn 'Trend'.

    Gemessen wurde auch, ob sich die Abhaengigkeit beziffern laesst: Ueber die
    acht Einstiegsgruppen liegt die Intraklassenkorrelation der Luecken bei
    +0,49, die Permutationsnull weist sie mit p = 0,0885 aber nicht nach - und
    die groebere Einteilung hat mit sechs Bloecken zu wenige (``MIND_BLOECKE``
    ist 8). Beziffern laesst es sich also nicht; eingrenzen schon.
    """

    def lage(self) -> Lage:
        return TestDerGemesseneVorrat().lage()

    def test_weniger_ziehungen_heben_die_grenze(self) -> None:
        lage = self.lage()

        assert lage.obergrenze(unabhaengige=18) == pytest.approx(0.1532, abs=0.001)
        assert lage.obergrenze(unabhaengige=8) == pytest.approx(0.3120, abs=0.001)
        assert lage.obergrenze(unabhaengige=6) == pytest.approx(0.3930, abs=0.001)

    def test_ohne_angabe_bleibt_es_die_regelzahl(self) -> None:
        """Der Vorgabewert aendert sich nicht - er wird nur benannt."""
        lage = self.lage()

        assert lage.obergrenze() == lage.obergrenze(unabhaengige=len(lage.abstaende))

    def test_die_zahl_wird_nie_mehr_unbedingt_genannt(self) -> None:
        """**Der eigentliche Umbau.** Auch ohne Gruppenangabe steht die
        Bedingung im Satz - sonst liest sich 15,3 % wieder als Messung."""
        text = self.lage().urteil()

        assert "unabhaengige Ziehungen sind" in text
        assert "**wenn**" in text

    def test_mit_gruppen_steht_dort_eine_spanne(self) -> None:
        text = self.lage().urteil(gruppen=6)

        assert "6 Gruppen" in text
        assert "39.3%" in text and "15.3%" in text
        assert "ehrliche Auskunft ist die Spanne" in text

    def test_eine_unsinnige_gruppenzahl_verengt_nichts(self) -> None:
        """Mehr Gruppen als Regeln waere eine engere Grenze aus dem Nichts -
        und null Gruppen eine Division durch die Behauptung."""
        lage = self.lage()

        for unsinn in (0, -3, len(lage.abstaende), len(lage.abstaende) + 5):
            text = lage.urteil(gruppen=unsinn)
            assert "Spanne" not in text, unsinn

    def test_die_regeln_zerfallen_wirklich_in_weniger_gruppen(self) -> None:
        """Die Messung hinter dem Befund - am Katalog, nicht an einer Zahl.

        Geprueft wird die **Richtung** und nicht die Gruppenzahl: Wer ein
        Genom hinzufuegt, aendert sie, und das ist kein Fehler.
        """
        import cli
        from research.familien import familie_von
        from research.seeds import GENERATIONS, load_seeds

        katalog = {g.name: g for gen in GENERATIONS for g in load_seeds(gen)}
        namen = [n for n, _, _, _ in TestDerGemesseneVorrat.VORRAT]
        assert all(n in katalog for n in namen), "Vorrat nicht im Katalog"

        fein = {cli._familie(katalog[n]) for n in namen}
        grob = {cli._familie_grob(katalog[n]) for n in namen}
        logisch = [familie_von(n) for n in namen]

        assert len(fein) < len(namen)
        assert len(grob) <= len(fein)
        assert logisch.count("Trend") * 2 > len(namen), (
            "die Mehrheit derselben Regellogik ist der Grund fuer diesen Befund"
        )


def test_der_modulkopf_traegt_die_berichtigung() -> None:
    """**Befund 287.** Der Kopf nannte 15,3 % ohne Bedingung.

    Dieselbe Pflicht wie in ``vorratsdecke``: Eine ueberholte Zahl stehen zu
    lassen, ist der Fehler aus Befund 130 - zwei Laeufe haben dort an einer
    veralteten Fundstelle nachgeschlagen.
    """
    import research.vorratslage as modul

    kopf = modul.__doc__ or ""
    assert "BERICHTIGT IN BEFUND 287" in kopf
    assert "0,49" in kopf, "die gemessene Intraklassenkorrelation"
    assert "0,0885" in kopf, "und dass sie nicht nachgewiesen ist"
    # Auf die Aussage geprueft und nicht auf den Zeilenumbruch: "schneidet
    # in die andere Richtung" bricht im Fliesstext zwischen den beiden
    # Woertern um, und ein Test, der daran haengt, prueft die Formatierung.
    assert "Dieselbe Vorsicht schneidet" in kopf, "die Asymmetrie der Vorsicht"
    assert "aussichtsloser, als belegt ist" in kopf
