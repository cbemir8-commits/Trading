"""Wo steht das Projekt - und was daran gemessen ist statt behauptet.

Zwei Tests tragen die Datei:

* ``test_geschlossene_richtung_braucht_eine_fundstelle`` - eine Richtung ohne
  Verweis auf die Messung ist eine Behauptung. Der Datentyp laesst sie nicht
  zu.
* ``test_urteil_nennt_den_abstand_statt_zu_beruhigen`` - "7 von 11" klingt nach
  wenig Rest. Der Abstand zum haertesten Gate sagt, wie viel es wirklich ist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.stand import (
    BEIM_NUTZER,
    BUDGET,
    ENTSCHEIDUNGEN,
    GESCHLOSSEN,
    Lage,
    Richtung,
    zahlwort,
)


def _lage(**abweichung) -> Lage:
    daten = {
        "kandidat": "Trend 50 Tage mit Konfluenz",
        "maerkte": "BTC + ETH, Tageskerzen",
        "trades": 152,
        "sharpe_je_trade": 0.2597,
        "noetiger_sharpe": 0.2857,
        "bestanden": 7,
        "gesamt": 11,
        "offen": ("Messlatte", "Deflated Sharpe"),
        "versuche": 119,
        "cagr_pct": 13.47,
        "rueckgang_pct": 10.64,
    }
    daten.update(abweichung)
    return Lage(**daten)


class TestRichtung:
    def test_geschlossene_richtung_braucht_eine_fundstelle(self) -> None:
        """**Eine Richtung ohne nachlesbare Messung ist eine Behauptung.**

        Die Liste der geschlossenen Wege ist die einzige gepflegte Stelle in
        diesem Bericht. Damit sie nicht zur Erzaehlung wird, laesst der
        Datentyp keinen Eintrag ohne Verweis zu.
        """
        with pytest.raises(ValueError, match="ohne Fundstelle"):
            Richtung("Irgendwas", "hat nicht funktioniert", 0)

    def test_alle_eintraege_tragen_eine_nummer(self) -> None:
        assert GESCHLOSSEN
        for r in GESCHLOSSEN:
            assert r.befund > 0, r.name
            assert r.ergebnis, r.name

    def test_keine_richtung_doppelt(self) -> None:
        namen = [r.name for r in GESCHLOSSEN]

        assert len(namen) == len(set(namen))

    def test_jede_fundstelle_gibt_es_wirklich(self) -> None:
        """**Der Test, der aus Befund 90 kommt.**

        Die Liste behauptet zu jedem geschlossenen Weg eine Fundstelle. Wenn
        eine Nummer ins Leere zeigt, ist der Eintrag eine Behauptung - und
        genau darauf verlaesst sich ein Lauf, der wissen will, ob eine Frage
        schon beantwortet ist. In Befund 90 habe ich eine 15-Minuten-Messung
        wiederholt, die unter Nr. 29 laengst dastand.
        """
        import re

        text = Path("strategies/BEFUND.md").read_text()
        ueberschriften = set(re.findall(r"^## ([A-Za-zaeoeueAEOEUEss]+)\.", text, re.M))
        fehlend = sorted(
            {r.befund for r in GESCHLOSSEN if zahlwort(r.befund) not in ueberschriften}
        )

        assert fehlend == [], (
            f"Fundstellen ohne Abschnitt im Laborbuch: {fehlend} "
            f"(erwartet z.B. '## {zahlwort(fehlend[0])}.')" if fehlend else ""
        )

    def test_die_liste_reicht_bis_an_die_gegenwart(self) -> None:
        """Bis Befund 90 endete sie bei Nr. 60 - und damit sah ein Lauf, der
        hier nachschlug, den Stand von vor zwanzig Befunden. Eine Liste
        geschlossener Wege, die dreissig Befunde hinterherhinkt, verhindert
        genau die Wiederholung nicht, fuer die sie da ist."""
        import re

        text = Path("strategies/BEFUND.md").read_text()
        nummern = [
            n for n in range(1, 100)
            if re.search(rf"^## {zahlwort(n)}\.", text, re.M)
        ]
        neuester = max(nummern)
        juengste_fundstelle = max(r.befund for r in GESCHLOSSEN)

        assert neuester - juengste_fundstelle <= 6, (
            f"Laborbuch bei {neuester}, juengster Ausschluss bei "
            f"{juengste_fundstelle} - die Liste haengt hinterher."
        )


class TestZahlwort:
    """Nur zum Nachschlagen der Fundstellen - aber dann muss es stimmen."""

    def test_die_teens_sind_sonderfaelle(self) -> None:
        """Der erste Anlauf bildete 'Dreiundzehn' statt 'Dreizehn' und fand
        drei Fundstellen nicht, die es gibt."""
        assert zahlwort(13) == "Dreizehn"
        assert zahlwort(14) == "Vierzehn"
        assert zahlwort(17) == "Siebzehn"

    def test_bei_den_zwanzigern_heisst_die_eins_ein(self) -> None:
        assert zahlwort(21) == "Einundzwanzig"
        assert zahlwort(1) == "Eins"

    def test_glatte_zehner_haben_kein_und(self) -> None:
        assert zahlwort(60) == "Sechzig"
        assert zahlwort(70) == "Siebzig"
        assert zahlwort(90) == "Neunzig"

    def test_zusammengesetzte(self) -> None:
        assert zahlwort(29) == "Neunundzwanzig"
        assert zahlwort(53) == "Dreiundfuenfzig"
        assert zahlwort(88) == "Achtundachtzig"

    def test_jenseits_der_neunundneunzig_faellt_die_suche_sichtbar_aus(self) -> None:
        """Ein leerer String findet keine Ueberschrift - dann schlaegt der
        Fundstellen-Test an, statt still nichts zu pruefen."""
        assert zahlwort(100) == ""
        assert zahlwort(0) == ""

    def test_darstellung_nennt_ergebnis_und_fundstelle(self) -> None:
        text = str(Richtung("Mehr Maerkte", "keine neue Information", 27))

        assert "Mehr Maerkte" in text
        assert "keine neue Information" in text
        assert "Nr. 27" in text


class TestLage:
    def test_urteil_nennt_den_abstand_statt_zu_beruhigen(self) -> None:
        """**"7 von 11" klingt nach wenig Rest.**

        Der Abstand zum haertesten Gate sagt, wie viel es wirklich ist - und
        genau der gehoert in denselben Satz.
        """
        text = _lage().urteil()

        assert "7 von 11" in text
        assert "Messlatte" in text and "Deflated Sharpe" in text
        assert "0.2597" in text and "0.2857" in text
        # Als Zuwachs, nicht als Verhaeltnis: Faktor 1,10 heisst zehn Prozent
        # mehr - "es fehlen 110 %" waere das Gegenteil einer Auskunft.
        assert "um 10% steigen" in text

    def test_ohne_grenzlinie_kein_faktor(self) -> None:
        """Wo das Gate bei dieser Trade-Zahl unerreichbar ist, gibt es keinen
        Faktor - und es wird auch keiner erfunden."""
        lage = _lage(noetiger_sharpe=None)

        assert lage.faktor is None
        assert "steigen" not in lage.urteil()

    def test_zugelassen_bleibt_vorsichtig(self) -> None:
        """Alle Gates bestanden heisst nicht, dass Geld darauf gehoert."""
        lage = _lage(bestanden=11, offen=())

        assert lage.zugelassen
        assert "dreissig Tage Demo" in lage.urteil()

    def test_null_gates_gelten_nicht_als_zugelassen(self) -> None:
        assert not _lage(bestanden=0, gesamt=0).zugelassen

    def test_bericht_enthaelt_alle_vier_teile(self) -> None:
        text = _lage().bericht()

        assert "STAND" in text
        assert "GEMESSEN UND GESCHLOSSEN" in text
        assert "WAS NICHT BEI MIR LIEGT" in text
        assert "NUR AUF DEINEM RECHNER" in text

    def test_bericht_zeigt_jede_geschlossene_richtung(self) -> None:
        text = _lage().bericht()

        for r in GESCHLOSSEN:
            assert r.name in text, r.name


class TestEntscheidungen:
    def test_jede_entscheidung_traegt_eine_zahl(self) -> None:
        """**Benannt und beziffert, nicht beantwortet.**

        Ein offener Punkt ohne Zahl ist eine Meinung; mit Zahl ist er eine
        Entscheidungsgrundlage.
        """
        assert ENTSCHEIDUNGEN
        for e in ENTSCHEIDUNGEN:
            assert any(z.isdigit() for z in e.zahl), e.frage
            assert e.warum, e.frage

    def test_keine_empfehlung_im_text(self) -> None:
        """Zwei davon sind wirtschaftliche Entscheidungen, keine
        statistischen - sie gehoeren dem Nutzer."""
        for e in ENTSCHEIDUNGEN:
            zusammen = f"{e.zahl} {e.warum}".lower()
            for wort in ("ich empfehle", "solltest du", "am besten waere"):
                assert wort not in zusammen, f"{e.frage}: {wort}"

    def test_nutzerbefehle_sind_begruendet(self) -> None:
        assert BEIM_NUTZER
        for befehl, warum in BEIM_NUTZER:
            assert befehl.startswith("python -m cli")
            assert len(warum) > 30, befehl


class TestSuchbudget:
    """**Das Abbruchkriterium stand nur im Plan, nicht im System.**

    Eine Suche ohne Ende ist keine Suche, sondern Warten - und hier ist sie
    schaedlich: Jeder Versuch hebt die Huerde des Deflated Sharpe fuer alle
    kuenftigen. Wer weitersucht, macht das Ziel schwerer, das er sucht.
    """

    def test_es_ist_eine_zahl_und_keine_bedingung(self) -> None:
        """**Der Vorzug der groben Zahl.**

        Ein Kriterium wie "abbrechen, wenn sich nichts mehr verbessert" laesst
        sich nachtraeglich zurechtlegen - man findet immer eine Kennzahl, die
        noch Hoffnung macht. Eine vorab genannte Zahl kann das nicht.
        """
        assert BUDGET.beginn == 130
        assert BUDGET.umfang == 100
        assert BUDGET.grenze == 230

    def test_vor_der_grenze_bleibt_es_offen(self) -> None:
        assert not BUDGET.erschoepft(BUDGET.grenze - 1)
        assert BUDGET.rest(BUDGET.grenze - 1) == 1

    def test_auf_der_grenze_gilt_die_antwort(self) -> None:
        """Genau auf der Zahl, nicht erst darueber - sonst waere die Grenze
        eine Verhandlungssache."""
        assert BUDGET.erschoepft(BUDGET.grenze)
        assert "aufgebraucht" in BUDGET.zeile(BUDGET.grenze)
        assert "traegt nicht" in BUDGET.zeile(BUDGET.grenze)

    def test_ueberschritten_bleibt_erschoepft(self) -> None:
        assert BUDGET.erschoepft(BUDGET.grenze + 50)
        assert BUDGET.rest(BUDGET.grenze + 50) == 0

    def test_vor_dem_beginn_ist_nichts_verbraucht(self) -> None:
        """Der Zaehler kann nicht rueckwaerts laufen, aber die Rechnung darf
        auch dann keine negative Zahl ausweisen."""
        assert BUDGET.verbraucht(BUDGET.beginn - 20) == 0

    def test_das_urteil_klingt_nicht_nach_scheitern(self) -> None:
        """So steht es im Plan, und es ist keine Beschoenigung: Eine
        Regelfamilie als untragfaehig zu belegen ist ein Ergebnis."""
        text = BUDGET.zeile(BUDGET.grenze)

        assert "Ergebnis" in text
        assert "kein Scheitern" in text

    def test_der_bericht_zeigt_den_stand(self) -> None:
        text = _lage(versuche=157).bericht()

        assert "Suchbudget" in text
        assert "27 von 100" in text


class TestAuftragspunkte:
    """Der Stand der Auftragspunkte - und warum er in den Code gehoert.

    Der Auftrag listet in jeder Runde dieselben offenen Punkte. Zwei davon
    waren laengst abgearbeitet - die 15-Minuten-Generationen seit Befund 29,
    das Termin-Overlay seit Nummer zwoelf -, aber es gab keine Stelle, an der
    das nachzulesen war. Also standen sie weiter da und wurden weiter als
    offen gelesen.

    Das ist nicht nur unordentlich, es ist **teuer**: Beinahe waeren vierzehn
    Versuche fuer eine Messung ausgegeben worden, die es schon gab.
    """

    def test_erledigt_ohne_fundstelle_wird_abgewiesen(self) -> None:
        """**Der Test, der diese Klasse traegt.**

        "Erledigt" ohne nachlesbare Messung ist eine Behauptung - dieselbe
        Regel wie bei den geschlossenen Richtungen, und aus demselben Grund:
        Wer sich darauf verlaesst, misst nicht nach.
        """
        from research.stand import Auftragspunkt

        with pytest.raises(ValueError, match="Fundstelle"):
            Auftragspunkt(frage="Irgendwas", stand="lief gut")

    def test_ein_offener_punkt_braucht_keine(self) -> None:
        from research.stand import Auftragspunkt

        offen = Auftragspunkt(
            frage="Steht noch aus", stand="noch nicht gemessen", erledigt=False
        )

        assert not offen.erledigt
        assert "offen" in str(offen)

    def test_die_vier_punkte_des_auftrags_sind_erfasst(self) -> None:
        from research.stand import AUFTRAG

        fragen = " ".join(p.frage for p in AUFTRAG)
        assert "P7" in fragen
        assert "Research-KI" in fragen
        assert "15-Minuten" in fragen
        assert "backfill" in fragen

    def test_jeder_erledigte_punkt_traegt_seine_nummer(self) -> None:
        from research.stand import AUFTRAG

        for punkt in AUFTRAG:
            if punkt.erledigt:
                assert punkt.befund > 0, punkt.frage

    def test_der_bericht_warnt_vor_doppelten_messungen(self) -> None:
        """Wer einen abgearbeiteten Punkt erneut misst, zahlt Versuche fuer
        ein Ergebnis, das schon dasteht - und hebt die Huerde fuer alle."""
        from research.stand import Lage

        text = Lage(
            kandidat="X", maerkte="BTC", trades=150, sharpe_je_trade=0.26,
            noetiger_sharpe=0.29, bestanden=7, gesamt=11, offen=("DSR",),
            versuche=166,
        ).bericht()

        assert "PUNKTE AUS DEM AUFTRAG" in text
        assert "zahlt Versuche fuer ein Ergebnis, das schon dasteht" in text
