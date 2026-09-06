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


class TestDieLueckeDesBestands:
    """**Befund 222.** Befund 70 hat den letzten offenen Weg mit "+13 %"
    beziffert - bei Guete 0,260 und n_eff 152. Beides ist ueberholt.

    Die Zahl stand seither als Text im Kopf von ``wettrennen`` und im
    Docstring von ``cli rennen``, also ausgerechnet dort, wo jemand
    entscheidet, ob Weitersuchen lohnt. Heute ist die Luecke fast doppelt so
    gross.
    """

    def test_sie_ist_heute_gut_ein_viertel(self) -> None:
        tag = next(p for p in GEMESSEN if p.intervall == "D")

        assert tag.luecke == pytest.approx(0.243, abs=5e-3)

    def test_sie_stimmt_mit_dem_referenzpunkt_ueberein(self) -> None:
        """Nachgerechnet aus SPOTPUNKT statt aus der Tabelle abgelesen."""
        import math

        latte = noetige_guete(
            SPOTPUNKT.effektiv,
            SPOTPUNKT.versuche,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )
        assert latte is not None
        erwartet = latte / math.sqrt(SPOTPUNKT.effektiv) / SPOTPUNKT.guete - 1

        tag = next(p for p in GEMESSEN if p.intervall == "D")
        assert tag.luecke == pytest.approx(erwartet, abs=5e-3)

    def test_befund_70_war_deutlich_kleiner(self) -> None:
        """Die alte Zahl ist nicht falsch - sie ist von einem anderen Punkt.

        Sie unterschaetzt die heutige Luecke um fast die Haelfte, und zwar in
        der Richtung, die zum Weitersuchen ermutigt.
        """
        tag = next(p for p in GEMESSEN if p.intervall == "D")

        assert tag.luecke > 1.8 * 0.131

    def test_ohne_guete_keine_luecke(self) -> None:
        """"Um wieviel Prozent besser als nichts" ist keine Auskunft."""
        punkt = Betriebspunkt(
            name="x", intervall="D", regel="r", effektiv=100,
            guete=-1.0, latte=2.0, befund=1,
        )

        assert punkt.luecke is None

    def test_die_zahl_steht_nicht_mehr_als_text_da(self) -> None:
        """In ``wettrennen`` und ``cli rennen`` darf ueber die alte Zahl
        geredet werden - sie darf dort nicht mehr als heutiger Stand stehen.
        """
        from pathlib import Path

        for datei in ("research/wettrennen.py", "cli.py"):
            for zeile in Path(datei).read_text().splitlines():
                if "+13 %" not in zeile and "+13 % -" not in zeile:
                    continue
                assert "Befund 70" in zeile, f"{datei}: {zeile.strip()[:70]}"


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
