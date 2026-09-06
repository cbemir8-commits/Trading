"""Auf welchem Betriebspunkt steht die Suche naeher am Ziel?

**Befund 220.** Beide Betriebspunkte sind seit langem gemessen, und der
Vergleich stand nirgends - weil er nicht direkt geht: Die Latte haengt an der
effektiven Stichprobe, und die ist 115 gegen 1830. Guete von hier gegen Latte
von dort waere genau der Fehler aus Befund 190.

Vergleichbar ist erst das **Verhaeltnis**, je Punkt fuer sich gerechnet.
"""

from __future__ import annotations

import math

import pytest

from research.erfuellung import (
    GEMESSEN,
    Betriebspunkt,
    bester_je_intervall,
    erfuellungsgrad,
    urteil,
)
from research.referenz import SPOTPUNKT
from research.verbund import noetige_guete


class TestDerAnteil:
    def test_er_ist_guete_durch_latte(self) -> None:
        assert erfuellungsgrad(2.0, 4.0) == pytest.approx(0.5)

    def test_eine_latte_von_null_gibt_keine_auskunft(self) -> None:
        """Ein Anteil an nichts waere eine erfundene Zahl."""
        assert erfuellungsgrad(1.0, 0.0) is None
        assert erfuellungsgrad(1.0, -1.0) is None

    def test_negative_guete_bleibt_negativ(self) -> None:
        """Wer in die falsche Richtung laeuft, hat nicht null Prozent
        geschafft - das gehoert sichtbar."""
        assert erfuellungsgrad(-0.78, 4.138) < 0

    def test_eine_stichprobe_von_null_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="keine Stichprobe"):
            Betriebspunkt(
                name="x", intervall="D", regel="r", effektiv=0,
                guete=1.0, latte=2.0, befund=1,
            )

    def test_eine_schwelle_bei_null_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="waere keine"):
            Betriebspunkt(
                name="x", intervall="D", regel="r", effektiv=10,
                guete=1.0, latte=0.0, befund=1,
            )


class TestDieGemessenenPunkte:
    def test_der_bestand_stimmt_mit_dem_referenzpunkt_ueberein(self) -> None:
        """Die Guete ist ``SR/Trade * sqrt(n_eff)`` - nachgerechnet, nicht
        abgeschrieben."""
        tag = next(p for p in GEMESSEN if p.intervall == "D")

        assert tag.effektiv == SPOTPUNKT.effektiv
        assert tag.guete == pytest.approx(
            SPOTPUNKT.guete * math.sqrt(SPOTPUNKT.effektiv), abs=5e-3
        )

    def test_die_latte_des_bestands_ist_nachgerechnet(self) -> None:
        """Mit seiner eigenen Stichprobe und seinen eigenen Momenten - so
        rechnet das Gate (Befund 193)."""
        tag = next(p for p in GEMESSEN if p.intervall == "D")
        latte = noetige_guete(
            SPOTPUNKT.effektiv,
            SPOTPUNKT.versuche,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )

        assert latte is not None
        assert tag.latte == pytest.approx(latte, abs=5e-3)

    def test_die_viertelstunden_stammen_aus_befund_171(self) -> None:
        fein = [p for p in GEMESSEN if p.intervall == "15"]

        assert {p.befund for p in fein} == {171}
        assert len(fein) == 3

    def test_der_bestand_raeumt_vier_fuenftel_seiner_latte(self) -> None:
        tag = next(p for p in GEMESSEN if p.intervall == "D")

        assert tag.anteil == pytest.approx(0.804, abs=5e-3)

    def test_der_beste_viertelstundenfund_knapp_ein_fuenftel(self) -> None:
        fein = bester_je_intervall()["15"]

        assert fein.regel == "Trendbeteiligung mit Puffer"
        assert fein.anteil == pytest.approx(0.188, abs=5e-3)


class TestWasDieFeinereKerzeLoest:
    """Sie senkt die Latte **je Trade** - und nicht insgesamt."""

    def test_die_latte_insgesamt_steigt_sogar(self) -> None:
        tag = next(p for p in GEMESSEN if p.intervall == "D")
        fein = bester_je_intervall()["15"]

        assert fein.latte > tag.latte

    def test_je_trade_faellt_sie_deutlich(self) -> None:
        tag = next(p for p in GEMESSEN if p.intervall == "D")
        fein = bester_je_intervall()["15"]

        assert fein.noetig_je_trade < tag.noetig_je_trade / 2

    def test_und_der_abstand_wird_trotzdem_groesser(self) -> None:
        """**Der Befund in einem Satz.**"""
        tag = next(p for p in GEMESSEN if p.intervall == "D")
        fein = bester_je_intervall()["15"]

        assert tag.anteil > fein.anteil * 4


class TestDasUrteil:
    def test_es_nennt_die_tageskerzen(self) -> None:
        text = urteil()

        assert "Naeher am Ziel: Tageskerzen" in text

    def test_es_warnt_vor_dem_fehler_aus_befund_190(self) -> None:
        """Ohne diesen Satz laedt die Tabelle dazu ein, ihn zu machen."""
        text = urteil()

        assert "eigenen Stichprobe" in text
        assert "190" in text

    def test_ohne_zweiten_punkt_kein_vergleich(self) -> None:
        import research.erfuellung as modul

        alt = modul.GEMESSEN
        try:
            modul.GEMESSEN = (alt[0],)
            assert "kein Vergleich" in modul.urteil()
        finally:
            modul.GEMESSEN = alt


def test_der_bericht_zeigt_den_vergleich() -> None:
    """Gebaut und nicht angezeigt waere Befund 208 noch einmal."""
    from research.stand import Lage

    text = Lage(
        kandidat="Trend 50 Tage mit Konfluenz",
        maerkte="BTC + ETH, Tageskerzen",
        trades=152, sharpe_je_trade=0.2597, noetiger_sharpe=0.2857,
        bestanden=7, gesamt=11, offen=("Messlatte", "Deflated Sharpe"),
        versuche=198, cagr_pct=13.47, rueckgang_pct=10.64,
    ).bericht()

    assert "Wovon der beste Fund je Kerzenlaenge steht" in text
    assert "Naeher am Ziel" in text
