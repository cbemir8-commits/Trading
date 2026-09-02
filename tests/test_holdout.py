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
