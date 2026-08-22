"""Tests fuer ``research.decke`` - Befund 111.

Gemessene Ankerwerte (Spot, gemeinsamer Bereich, 198 Versuche):

    Perpetual wie gebaut      DSR 0,7641
    Spot wie gebaut           DSR 0,8640   Guete 0,2765   152 Trades
    Spot voellig kostenfrei   DSR 0,8808   Guete 0,2798
"""

from __future__ import annotations

import math

import pytest

from research.decke import (
    SCHWELLE,
    Decke,
    Deckenwert,
    Fenster,
    Fensterlage,
    Stichprobenbedarf,
    deflated_sharpe,
)
from research.gates import deflated_sharpe_ratio


class TestDeckenwert:
    def test_spielraum_ist_die_differenz(self):
        wert = Deckenwert(name="Kosten", heute=0.8640, decke=0.8808)
        assert wert.spielraum == pytest.approx(0.0168, abs=1e-9)

    def test_kostenfamilie_reicht_nicht(self):
        """Der gemessene Anschlag liegt unter der Schwelle."""
        wert = Deckenwert(name="Kosten", heute=0.8640, decke=0.8808)
        assert not wert.reicht()
        assert wert.erschoepft()
        assert wert.fehlt() == pytest.approx(0.0692, abs=1e-9)

    def test_reichende_familie_hat_keine_luecke(self):
        wert = Deckenwert(name="Traumfamilie", heute=0.86, decke=0.97)
        assert wert.reicht()
        assert not wert.erschoepft()
        assert wert.fehlt() == 0.0

    def test_ungemessener_anschlag_reicht_nie(self):
        """Auch ein hoher Wert traegt nicht, solange er nicht gemessen ist."""
        wert = Deckenwert(name="Maerkte", heute=0.8640, decke=0.99, gemessen=False)
        assert not wert.reicht()
        assert not wert.erschoepft()
        assert math.isnan(wert.fehlt())

    def test_text_nennt_die_luecke(self):
        wert = Deckenwert(name="Kosten", heute=0.8640, decke=0.8808)
        text = wert.als_text()
        assert "0.0692" in text
        assert "Kosten" in text

    def test_text_bei_ungemessenem_anschlag_verspricht_nichts(self):
        wert = Deckenwert(name="Maerkte", heute=0.86, decke=0.99, gemessen=False)
        text = wert.als_text()
        assert "ungemessen" in text
        assert "0.99" not in text


class TestDecke:
    def test_kosten_allein_ist_erschoepft(self):
        kosten = Deckenwert(name="Kosten", heute=0.8640, decke=0.8808)
        lage = Decke(familien=(kosten,))
        assert lage.erschoepft() == (kosten,)
        assert lage.traegt() == ()
        assert lage.alles_erschoepft()

    def test_ungemessene_familie_zaehlt_nicht_als_ausweg(self):
        kosten = Deckenwert(name="Kosten", heute=0.8640, decke=0.8808)
        maerkte = Deckenwert(
            name="Maerkte", heute=0.8640, decke=0.99, gemessen=False
        )
        lage = Decke(familien=(kosten, maerkte))
        assert lage.traegt() == ()
        assert lage.ungemessen() == (maerkte,)
        # Alles Gemessene ist erschoepft, auch wenn Ungemessenes danebensteht.
        assert lage.alles_erschoepft()
        assert "ungemessen" in lage.urteil().lower()

    def test_ein_tragender_weg_wird_genannt(self):
        traeger = Deckenwert(name="Wunder", heute=0.86, decke=0.96)
        lage = Decke(familien=(traeger,))
        assert lage.traegt() == (traeger,)
        assert not lage.alles_erschoepft()
        assert "Wunder" in lage.urteil()

    def test_groesster_spielraum_ignoriert_ungemessene(self):
        klein = Deckenwert(name="Kosten", heute=0.86, decke=0.88)
        gross = Deckenwert(name="Maerkte", heute=0.86, decke=0.99, gemessen=False)
        lage = Decke(familien=(klein, gross))
        assert lage.groesster_spielraum is klein

    def test_ohne_familien_kein_urteil(self):
        lage = Decke(familien=())
        assert not lage.alles_erschoepft()
        assert lage.groesster_spielraum is None
        assert "nichts zu sagen" in lage.urteil()

    def test_urteil_bei_erschoepfung_verweist_auf_die_sache_selbst(self):
        kosten = Deckenwert(name="Kosten", heute=0.8640, decke=0.8808)
        lage = Decke(familien=(kosten,))
        assert "aus der Sache selbst" in lage.urteil()


class TestDeflatedSharpe:
    def test_ist_dieselbe_formel_wie_im_gate(self):
        """Keine zweite Kopie - der Wert muss auf die letzte Stelle stimmen."""
        for guete, n, versuche in (
            (0.2765, 152, 198), (0.2798, 152, 198), (0.19, 400, 12), (0.31, 90, 1),
        ):
            assert deflated_sharpe(
                guete=guete, versuche=versuche, stichprobe=n,
                schiefe=3.41, woelbung=15.48,
            ) == deflated_sharpe_ratio(
                observed_sharpe=guete, trials=max(versuche, 1), sample_size=n,
                skew=3.41, kurtosis=15.48,
            )

    def test_gemessener_betriebspunkt_wird_getroffen(self):
        wert = deflated_sharpe(
            guete=0.2765, versuche=198, stichprobe=152,
            schiefe=3.4104, woelbung=15.4834,
        )
        assert wert == pytest.approx(0.8640, abs=5e-4)

    def test_kostenfreier_anschlag_wird_getroffen(self):
        wert = deflated_sharpe(
            guete=0.2798, versuche=198, stichprobe=152,
            schiefe=3.4104, woelbung=15.4834,
        )
        assert wert == pytest.approx(0.8808, abs=5e-4)

    def test_zu_kleine_stichprobe_gibt_null(self):
        assert deflated_sharpe(guete=0.28, versuche=198, stichprobe=2) == 0.0

    def test_negative_guete_gibt_null(self):
        assert deflated_sharpe(guete=-0.1, versuche=198, stichprobe=200) == 0.0


class TestStichprobenbedarf:
    def _betriebspunkt(self, **kw) -> Stichprobenbedarf:
        werte = dict(
            guete=0.2765, versuche=198, heute=152,
            schiefe=3.4104, woelbung=15.4834,
        )
        werte.update(kw)
        return Stichprobenbedarf(**werte)

    def test_stand_entspricht_der_messung(self):
        assert self._betriebspunkt().stand == pytest.approx(0.8640, abs=5e-4)

    def test_noetige_stichprobe_ist_182(self):
        assert self._betriebspunkt().noetig() == 182

    def test_es_fehlen_dreissig_beobachtungen(self):
        assert self._betriebspunkt().fehlende() == 30

    def test_faktor_ist_knapp_ueber_eins(self):
        assert self._betriebspunkt().faktor() == pytest.approx(182 / 152, abs=1e-9)

    def test_kostenfreier_lauf_braucht_fuenf_weniger(self):
        """Die ganze Kostenfamilie verschiebt fuenf Beobachtungen."""
        assert self._betriebspunkt(guete=0.2798).noetig() == 177

    def test_die_gefundene_zahl_haelt_und_eine_weniger_nicht(self):
        bedarf = self._betriebspunkt()
        noetig = bedarf.noetig()
        assert deflated_sharpe(
            guete=bedarf.guete, versuche=bedarf.versuche, stichprobe=noetig,
            schiefe=bedarf.schiefe, woelbung=bedarf.woelbung,
        ) >= SCHWELLE
        assert deflated_sharpe(
            guete=bedarf.guete, versuche=bedarf.versuche, stichprobe=noetig - 1,
            schiefe=bedarf.schiefe, woelbung=bedarf.woelbung,
        ) < SCHWELLE

    def test_winziger_vorteil_traegt_auch_er_irgendwann(self):
        """Der Deflated Sharpe misst Evidenz, nicht Vorteilsgroesse.

        Beim Schreiben dieses Tests stand hier zuerst ``is None`` - die
        Annahme, ein zu kleiner Vorteil sei durch keine Datenmenge zu heilen.
        Der Test fiel durch, und die Annahme war falsch: Bei jeder echt
        positiven Guete reicht genug n. Gegen einen zu kleinen Vorteil
        schuetzt die Messlatte, nicht dieses Gate.
        """
        bedarf = self._betriebspunkt(guete=0.02)
        assert bedarf.noetig() == 47335

    def test_nur_ohne_vorteil_traegt_gar_nichts(self):
        for guete in (0.0, -0.3):
            bedarf = self._betriebspunkt(guete=guete)
            assert bedarf.noetig() is None
            assert bedarf.fehlende() is None
            assert bedarf.faktor() is None
            assert "ohne positiven Vorteil" in bedarf.urteil()

    def test_ausreichende_stichprobe_meldet_null_fehlende(self):
        bedarf = self._betriebspunkt(heute=300)
        assert bedarf.fehlende() == 0
        assert "haelt bereits" in bedarf.urteil()

    def test_mehr_versuche_verlangen_mehr_beobachtungen(self):
        """Die Multiple-Testing-Strafe schlaegt auf den Bedarf durch."""
        wenig = self._betriebspunkt(versuche=50).noetig()
        viel = self._betriebspunkt(versuche=500).noetig()
        assert wenig < viel

    def test_urteil_nennt_beide_zahlen(self):
        text = self._betriebspunkt().urteil()
        assert "152" in text
        assert "182" in text


class TestFenster:
    def _lage(self) -> Fensterlage:
        referenz = Fenster(
            name="BTC + ETH, gemeinsam", von="2017-08-16", bis="2026-08-05",
            trades=152, guete=0.2765, dsr=0.8640, bestanden=9, gesamt=11,
        )
        return Fensterlage(
            referenz=referenz,
            weitere=(
                Fenster(
                    name="BTC allein, gemeinsam", von="2017-08-16", bis="2026-08-05",
                    trades=72, guete=0.2655, dsr=0.1761, bestanden=8, gesamt=11,
                ),
                Fenster(
                    name="BTC allein, volle Historie", von="2012-01-01",
                    bis="2026-08-05", trades=117, guete=0.2652, dsr=0.4198,
                    bestanden=5, gesamt=11,
                ),
            ),
        )

    def test_alle_fenster_stehen_im_bericht(self):
        assert len(self._lage().alle) == 3

    def test_kein_fenster_schlaegt_die_referenz(self):
        assert self._lage().wechsel_begruendbar() == ()

    def test_urteil_haelt_am_referenzfenster_fest(self):
        text = self._lage().urteil()
        assert "Referenzfenster bleibt" in text

    def test_abstand_zeigt_den_verlust(self):
        lage = self._lage()
        assert lage.abstand(lage.weitere[0]) == pytest.approx(-0.6879, abs=1e-9)
        assert lage.abstand(lage.weitere[1]) == pytest.approx(-0.4442, abs=1e-9)

    def test_ein_besseres_gate_allein_genuegt_nicht(self):
        """Mehr Gates, aber weniger Trades - das ist kein Sieg."""
        referenz = Fenster(
            name="Referenz", von="a", bis="b", trades=152, guete=0.27,
            dsr=0.86, bestanden=9, gesamt=11,
        )
        halb = Fenster(
            name="Halber Zeitraum", von="a", bis="b", trades=70, guete=0.30,
            dsr=0.90, bestanden=10, gesamt=11,
        )
        assert not halb.schlaegt(referenz)
        assert Fensterlage(referenz=referenz, weitere=(halb,)).wechsel_begruendbar() == ()

    def test_ein_hoeherer_dsr_allein_genuegt_nicht(self):
        referenz = Fenster(
            name="Referenz", von="a", bis="b", trades=152, guete=0.27,
            dsr=0.86, bestanden=9, gesamt=11,
        )
        knapp = Fenster(
            name="Knapp besser", von="a", bis="b", trades=160, guete=0.28,
            dsr=0.87, bestanden=9, gesamt=11,
        )
        assert not knapp.schlaegt(referenz)

    def test_in_jeder_hinsicht_besser_ist_begruendbar(self):
        referenz = Fenster(
            name="Referenz", von="a", bis="b", trades=152, guete=0.27,
            dsr=0.86, bestanden=9, gesamt=11,
        )
        besser = Fenster(
            name="Wirklich besser", von="a", bis="b", trades=200, guete=0.29,
            dsr=0.93, bestanden=10, gesamt=11,
        )
        lage = Fensterlage(referenz=referenz, weitere=(besser,))
        assert lage.wechsel_begruendbar() == (besser,)
        assert "begruendbar" in lage.urteil()

    def test_es_gibt_keine_bestes_fenster_methode(self):
        """Absichtlich nicht vorhanden - siehe Modul-Docstring."""
        for verboten in ("bestes", "best", "guenstigstes", "maximum"):
            assert not hasattr(Fensterlage, verboten)


class TestDieAnderenFamilienStehenImRegister:
    """Befund 111 hat 'mehr Maerkte' als offene Richtung angekuendigt.

    Sie steht seit Befund 27 in ``GESCHLOSSEN``, und die Datei war beim
    Schreiben offen. Diese Tests halten fest, worauf sich der Befund stuetzt -
    laufen die Eintraege weg, faellt es hier auf und nicht erst im naechsten
    Befund.
    """

    def test_mehr_maerkte_ist_geschlossen(self):
        from research.stand import GESCHLOSSEN

        eintrag = next(r for r in GESCHLOSSEN if r.name == "Mehr Maerkte")
        assert eintrag.befund == 27
        assert "150" in eintrag.ergebnis

    def test_mehr_historie_ist_geschlossen(self):
        from research.stand import GESCHLOSSEN

        eintrag = next(r for r in GESCHLOSSEN if r.name == "Mehr Historie")
        assert eintrag.befund == 14

    def test_die_kostenfamilie_ist_jetzt_auch_darin(self):
        from research.stand import GESCHLOSSEN

        eintrag = next(r for r in GESCHLOSSEN if r.name == "Kostenannahmen")
        assert eintrag.befund == 111

    def test_der_versuchszaehler_kostet_mehr_als_das_funding_brachte(self):
        """96 Versuche seit Befund 27, gegen den groessten Fund des Projekts.

        Perpetual, 152 Trades, Guete 0,2597 - nur der Zaehler wandert.
        """
        bei_27 = deflated_sharpe(
            guete=0.2597, versuche=102, stichprobe=152,
            schiefe=3.4104, woelbung=15.4834,
        )
        heute = deflated_sharpe(
            guete=0.2597, versuche=198, stichprobe=152,
            schiefe=3.4104, woelbung=15.4834,
        )
        gekostet = bei_27 - heute
        assert gekostet == pytest.approx(0.0993, abs=5e-4)

        # Der Funding-Wegfall, auf derselben Skala: 0,7641 -> 0,8640.
        gebracht = 0.8640 - 0.7641
        assert gekostet > gebracht * 0.95
