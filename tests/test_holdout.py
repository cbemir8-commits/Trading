"""Traegt die Regel dort, wo sie nie ausgewaehlt wurde?

Befund 168 hat den Verdacht geweckt - der Vorsprung des Bestands vor seinem
eigenen Katalog ist kleiner als das, was Auswahl aus 198 Versuchen ohnehin
erzeugt. Befund 174 prueft ihn von der anderen Seite: dieselbe Regel,
unveraendert, auf Maerkten, die bei ihrer Entwicklung keine Rolle spielten.

Die Tests hier halten zweierlei fest: die Rechnung (was der Holdout haelt) und
- wichtiger - dass das Urteil seine beiden Einschraenkungen **immer**
mitnennt. Ein Holdout-Ergebnis ohne sie liest sich als Beleg fuer Koennen, und
das gibt diese Messung nicht her.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from research.holdout import ENTWICKLUNG, HOLDOUT, Holdoutbild, Marktbefund


def befund(symbol: str, rolle: str, sr: float, n_eff: int = 100) -> Marktbefund:
    return Marktbefund(symbol, rolle, trades=n_eff, n_eff=n_eff, sharpe_je_trade=sr)


#: Der gemessene Fall aus Befund 174.
GEMESSEN = (
    befund("BTC", ENTWICKLUNG, 0.2633, 107),
    befund("ETH", ENTWICKLUNG, 0.2907, 76),
    befund("LTC", HOLDOUT, 0.1154, 106),
    befund("XRP", HOLDOUT, 0.1095, 106),
)


class TestDerMarktbefund:
    def test_die_guete_ist_sr_mal_wurzel_n(self) -> None:
        assert befund("BTC", ENTWICKLUNG, 0.2, 100).guete == pytest.approx(2.0)

    def test_eine_erfundene_rolle_wird_abgewiesen(self) -> None:
        """Zwei Rollen, sonst zaehlt die Auswertung stillschweigend etwas
        anderes - "Validierung" waere weder das eine noch das andere."""
        with pytest.raises(ValueError, match="keine Rolle"):
            befund("BTC", "Validierung", 0.2)


class TestWasDerHoldoutHaelt:
    def test_der_anteil_wird_gerechnet(self) -> None:
        bild = Holdoutbild(GEMESSEN)

        assert bild.entwicklung == pytest.approx((0.2633 + 0.2907) / 2)
        assert bild.holdout == pytest.approx((0.1154 + 0.1095) / 2)
        assert bild.behalten == pytest.approx(0.406, abs=0.005)

    def test_ohne_holdout_gibt_es_keinen_anteil(self) -> None:
        bild = Holdoutbild(tuple(b for b in GEMESSEN if b.rolle == ENTWICKLUNG))

        assert bild.behalten is None
        assert "Kein Vergleich moeglich" in bild.urteil()

    def test_ohne_entwicklung_ebenso(self) -> None:
        bild = Holdoutbild(tuple(b for b in GEMESSEN if b.rolle == HOLDOUT))

        assert bild.behalten is None
        assert "Kein Vergleich moeglich" in bild.urteil()

    def test_ein_anteil_von_etwas_negativem_ist_keine_auskunft(self) -> None:
        """**Sonst kaeme bei zwei negativen Seiten ein huebscher Prozentsatz
        heraus.** Minus durch Minus ist positiv, und "der Holdout haelt 80 %"
        waere dann die Umkehrung dessen, was dasteht.
        """
        bild = Holdoutbild(
            (
                befund("BTC", ENTWICKLUNG, -0.10),
                befund("LTC", HOLDOUT, -0.08),
            )
        )

        assert bild.behalten is None
        # Nicht auf "80" pruefen - das steckt auch in "-0.0800". Geprueft
        # wird, dass ueberhaupt kein Anteil behauptet wird.
        assert "haelt" not in bild.urteil()


class TestDasUrteilNenntSeineGrenzen:
    def test_die_korrelation_steht_dabei(self) -> None:
        text = Holdoutbild(GEMESSEN, korrelation=0.685).urteil()

        assert "0.685" in text
        assert "schwaecher als sein Name" in text

    def test_die_marktrichtung_steht_immer_dabei(self) -> None:
        """**Auch ohne gemessene Korrelation.** Der Aufwaertstrend ist der
        Einwand, der bei einer Long-Trendfolge nie entfaellt."""
        for korrelation in (None, 0.1, 0.9):
            text = Holdoutbild(GEMESSEN, korrelation=korrelation).urteil()

            assert "Koennen nicht von Marktrichtung" in text

    def test_ein_positiver_holdout_heisst_nicht_restlos_auswahl(self) -> None:
        text = Holdoutbild(GEMESSEN, korrelation=0.685).urteil()

        assert "nicht restlos Auswahl" in text
        assert "haelt 41%" in text

    def test_ein_leerer_holdout_ist_die_dritte_stimme(self) -> None:
        """**Beide Ausgaenge sind Ergebnisse.** Bleibt im Holdout nichts, ist
        das mit reiner Auswahl vereinbar - und das gehoert gesagt."""
        bild = Holdoutbild(
            (
                befund("BTC", ENTWICKLUNG, 0.2633),
                befund("LTC", HOLDOUT, -0.01),
            ),
            korrelation=0.685,
        )
        text = bild.urteil()

        assert "Im Holdout bleibt nichts uebrig" in text
        assert "dritte Stimme" in text
        assert "nicht restlos Auswahl" not in text


class TestDieRegelWirdBeimNamenGenannt:
    """**Befund 185.** ``cli holdout`` konnte nur den Bestand pruefen.

    Befund 184 hat den besten gemessenen Stand des Projekts als **Paar**
    gefunden - Bestand + 'Grosser Trendausbruch'. Der neue Partner ist auf
    BTC und ETH ausgewaehlt worden; ob er auf Maerkten traegt, die dabei
    keine Rolle spielten, liess sich mit diesem Befehl nicht messen.
    """

    def test_ein_genauer_name_findet_die_regel(self) -> None:
        from cli import _katalogregel

        assert _katalogregel("Grosser Trendausbruch").name == "Grosser Trendausbruch"

    def test_gross_und_kleinschreibung_spielt_keine_rolle(self) -> None:
        from cli import _katalogregel

        assert _katalogregel("grosser trendausbruch").name == "Grosser Trendausbruch"

    def test_ein_eindeutiger_teilname_genuegt(self) -> None:
        from cli import _katalogregel

        assert "Donchian" in _katalogregel("Donchian").name

    def test_ein_mehrdeutiger_name_wird_abgewiesen_statt_geraten(self) -> None:
        """**Sonst misst man eine andere Regel als gemeint.** Bei elf
        Trend-Regeln im Katalog ist 'Trend' keine Angabe."""
        import typer

        from cli import _katalogregel

        with pytest.raises(typer.Exit):
            _katalogregel("Trend")

    def test_ein_unbekannter_name_wird_abgewiesen(self) -> None:
        import typer

        from cli import _katalogregel

        with pytest.raises(typer.Exit):
            _katalogregel("Gibt es nicht")

    def test_gesucht_wird_ueber_alle_generationen(self) -> None:
        """**Die Lehre aus Befund 184.** Wer nach Intervall filtert, schliesst
        die vier nicht festgelegten Generationen aus - und genau in ihnen
        steht 'Grosser Trendausbruch'."""
        from cli import _katalogregel
        from research.seeds import GENERATIONS, VORGESEHEN

        gefunden = _katalogregel("Grosser Trendausbruch")
        heimat = [
            gen
            for gen, liste in GENERATIONS.items()
            if any(b().name == gefunden.name for b in liste)
        ]

        assert heimat, "die Regel muss in einer Generation stehen"
        assert VORGESEHEN.get(heimat[0]) is None, (
            "dieser Test prueft gerade den None-Fall"
        )


class TestDieSiebenAusBefund184:
    """**Befund 186.** Alle sieben Paare, die besser dastanden als der
    Bestand allein, im Holdout gemessen - als Zahlen festgehalten.

    Die Rangfolge stammt aus `cli paare` auf BTC und ETH; der Holdout steht
    auf LTC und XRP. Was hier gepflegt wird, ist der Vergleich zwischen
    beidem.
    """

    #: (Name, Luecke aus Befund 184, Anteil den der Holdout haelt)
    GEMESSEN: ClassVar[tuple[tuple[str, float, float], ...]] = (
        ("Grosser Trendausbruch", 0.064, -0.70),
        ("Trendfolge Ausbruch", 0.125, +0.07),
        ("Trend-Beteiligung (fair gerechnet)", 0.521, +0.30),
        ("Nur mit der Drift", 0.574, +0.29),
        ("EMA-Kreuzung (Messlatte)", 0.605, -0.34),
        ("Trendbeteiligung EMA200", 0.657, +0.25),
        ("Langsamer Kreuzer (Messlatte 2)", 0.684, -7.89),
    )
    #: Der Bestand allein, aus Befund 174 - der Massstab.
    BESTAND = (0.705, +0.41)

    def test_kein_partner_haelt_mehr_als_der_bestand(self) -> None:
        """**Der Satz, der traegt.** Er braucht keine Korrelation, nur einen
        Vergleich von acht Zahlen."""
        beste = max(anteil for _, _, anteil in self.GEMESSEN)

        assert beste < self.BESTAND[1], (
            f"bester Partner haelt {beste:.0%}, Bestand {self.BESTAND[1]:.0%}"
        )

    def test_die_beiden_bestplatzierten_halten_am_wenigsten(self) -> None:
        """Die Rangfolge aus der Entwicklung findet den Partner nicht, der
        draussen traegt - sie findet an der Spitze zwei, die es nicht tun."""
        nach_rang = sorted(self.GEMESSEN, key=lambda x: x[1])

        assert nach_rang[0][2] < 0, "der Bestplatzierte haelt nichts"
        assert nach_rang[1][2] < 0.10, "der Zweite fast nichts"

    def test_drei_von_sieben_halten_gar_nichts(self) -> None:
        leer = [n for n, _, anteil in self.GEMESSEN if anteil <= 0]

        assert len(leer) == 3, leer

    def test_die_rangkorrelation_traegt_ausdruecklich_nicht(self) -> None:
        """**Und das gehoert dazu.** Ueber acht Punkte ist rho = +0,21 bei
        t = +0,54, ohne den 9-Trade-Ausreisser +0,57 bei t = +1,56.

        Beides liegt unter der Schwelle, die dieses Projekt seit Befund 75
        verlangt. Wer daraus "die Rangfolge ist umgekehrt" liest, macht
        genau den Fehler, den Befund 75 als Scheinbefund festhaelt.
        """
        import statistics

        from research.vorratsdecke import MINDEST_T

        punkte = [(luecke, a) for _, luecke, a in self.GEMESSEN] + [self.BESTAND]

        def raenge(werte):
            ordnung = sorted(range(len(werte)), key=lambda i: werte[i])
            r = [0] * len(werte)
            for platz, i in enumerate(ordnung, 1):
                r[i] = platz
            return r

        rl = raenge([p[0] for p in punkte])
        rh = raenge([p[1] for p in punkte])
        rho = statistics.correlation(rl, rh)
        t = rho * ((len(punkte) - 2) / (1 - rho**2)) ** 0.5

        assert abs(t) < MINDEST_T, (
            f"t = {t:+.2f} - dann waere die Aussage belegt und dieser Test "
            f"muesste umgeschrieben werden"
        )
