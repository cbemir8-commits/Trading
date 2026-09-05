"""Wo steht das Projekt - und was daran gemessen ist statt behauptet.

Zwei Tests tragen die Datei:

* ``test_geschlossene_richtung_braucht_eine_fundstelle`` - eine Richtung ohne
  Verweis auf die Messung ist eine Behauptung. Der Datentyp laesst sie nicht
  zu.
* ``test_urteil_nennt_den_abstand_statt_zu_beruhigen`` - "7 von 11" klingt nach
  wenig Rest. Der Abstand zum haertesten Gate sagt, wie viel es wirklich ist.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from research import stand
from research.stand import (
    BEHOBEN,
    BEIM_NUTZER,
    BUDGET,
    ENTSCHEIDUNGEN,
    GESCHLOSSEN,
    OFFEN,
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
        # Bis 299, seit das Laborbuch die Zweihundert erreicht hat. Bliebe
        # der Bereich bei 199 stehen, waere ``neuester`` fuer immer 199 und
        # der Test schluege nie wieder an.
        nummern = [
            n for n in range(1, 300)
            if re.search(rf"^## {zahlwort(n)}\.", text, re.M)
        ]
        neuester = max(nummern)
        # **Beide Listen zusammen** (Befund 123). Seit die Werkzeugbefunde in
        # ``BEHOBEN`` stehen, waere die Pruefung auf ``GESCHLOSSEN`` allein zu
        # streng: Ein Lauf, der nur Werkzeuge repariert hat, liesse sie
        # anschlagen, obwohl das Register vollstaendig ist. Der Zweck war nie
        # "eine bestimmte Liste waechst", sondern "nichts hinkt hinterher".
        juengste_fundstelle = max(
            r.befund for r in (*GESCHLOSSEN, *BEHOBEN)
        )

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

    def test_der_hunderterbereich_kam_mit_befund_100(self) -> None:
        """Er wurde gebaut, als er gebraucht wurde - vorher fiel die Suche
        dort ausdruecklich aus."""
        assert zahlwort(100) == "Hundert"
        assert zahlwort(101) == "Hunderteins"
        assert zahlwort(113) == "Hundertdreizehn"
        assert zahlwort(121) == "Hunderteinundzwanzig"
        assert zahlwort(130) == "Hundertdreissig"

    def test_der_zweihunderterbereich_kam_mit_befund_200(self) -> None:
        """Dieselbe Regel wie beim Hunderter: gebaut, als er gebraucht wurde."""
        assert zahlwort(200) == "Zweihundert"
        assert zahlwort(201) == "Zweihunderteins"
        assert zahlwort(213) == "Zweihundertdreizehn"
        assert zahlwort(221) == "Zweihunderteinundzwanzig"

    def test_jenseits_der_grenze_faellt_die_suche_sichtbar_aus(self) -> None:
        """Ein leerer String findet keine Ueberschrift - dann schlaegt der
        Fundstellen-Test an, statt still nichts zu pruefen. Die Grenze ist nur
        weitergerueckt, nicht verschwunden."""
        assert zahlwort(300) == ""
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
        #
        # Die Vorlage hat keine gemessene Stichprobe, deshalb "mindestens"
        # (Befund 148). Geprueft wird hier weiter die Form des Zuwachses.
        assert "um mindestens 10% steigen" in text

    def test_ohne_grenzlinie_kein_faktor(self) -> None:
        """Wo das Gate bei dieser Trade-Zahl unerreichbar ist, gibt es keinen
        Faktor - und es wird auch keiner erfunden."""
        lage = _lage(noetiger_sharpe=None)

        assert lage.faktor is None
        assert "steigen" not in lage.urteil()

    def test_das_zweite_tor_steht_daneben(self) -> None:
        """**Befund 178.** Der Bericht nannte nur den noetigen Zuwachs an
        Qualitaet - und der gemessene Wert ist das Beste aus 198 Versuchen.

        Die Latte steigt oberhalb von rund 60 wirksamen Beobachtungen viel
        langsamer als die Wurzel; dieselbe Regel oefter fuehrt deshalb ebenso
        an die Schwelle wie eine bessere.

        **Ebenso, nicht billiger** - der Zusatz kam mit Befund 179 dazu, und
        er gehoert in denselben Satz: Der Weg zu mehr Trades kostet in diesem
        Vorrat mehr Vorsprung, als die fallende Latte spart.
        """
        lage = _lage(effektiv=121, sharpe_je_trade=0.2649, versuche=198)

        assert lage.menge == 199
        text = lage.urteil()
        assert "199 wirksame Beobachtungen" in text
        assert "Faktor 1.64" in text
        assert "bei unveraenderter Qualitaet" in text
        assert "gekoppelt" in text

    def test_ohne_gemessene_stichprobe_kein_mengentor(self) -> None:
        """Ohne ``effektiv`` gaebe es keine Zahl, gegen die ein Faktor
        rechnen koennte - dann steht dort nichts statt etwas Erfundenem."""
        lage = _lage(effektiv=None)

        assert lage.menge is None
        assert "ueber die Menge" not in lage.urteil()

    def test_wo_die_menge_nicht_genuegt_wird_es_gesagt(self) -> None:
        lage = _lage(effektiv=121, sharpe_je_trade=0.02, versuche=198)

        assert lage.menge is None
        assert "nicht zu holen" in lage.urteil()

    def test_wer_genug_beobachtungen_hat_bekommt_kein_mengenziel(self) -> None:
        """Sonst staende dort eine Zahl **unter** der vorhandenen - eine
        Aufforderung, weniger zu handeln."""
        lage = _lage(effektiv=400, sharpe_je_trade=0.2649, versuche=198)

        assert lage.menge is not None and lage.menge < 400
        assert "wirksame Beobachtungen" not in lage.urteil()

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


class TestDieTrennung:
    """Befund 123 - zwei Fragen, zwei Listen.

    Ich habe neun Werkzeugbefunde in ``GESCHLOSSEN`` eingetragen. Die Liste
    beantwortet die Frage *"welche Suchwege sind gemessen zu"* - und wer sie
    las, fand zwischen "Mehr Maerkte: effektive Stichprobe bleibt bei 150" auf
    einmal "README auf dem Stand vom 1. August".

    Beides Messungen mit Fundstelle. Aber ein geschlossener Suchweg heisst:
    dort ist nichts zu holen. Ein behobener Werkzeugfehler heisst: etwas war
    kaputt und ist repariert - das sagt ueber die Aussichten gar nichts.
    """

    def test_keine_fundstelle_steht_in_beiden(self) -> None:
        doppelt = {r.befund for r in GESCHLOSSEN} & {r.befund for r in BEHOBEN}
        assert doppelt == set(), f"Fundstellen in beiden Listen: {doppelt}"

    def test_jede_behobene_fundstelle_steht_im_laborbuch(self) -> None:
        """Dieselbe Pruefung wie fuer ``GESCHLOSSEN`` - ein Eintrag ohne
        nachlesbare Messung ist auch hier eine Behauptung."""
        import re
        from pathlib import Path

        text = Path("strategies/BEFUND.md").read_text()
        ueberschriften = set(
            re.findall(r"^## ([A-Za-zaeoeueAEOEUEss]+)\.", text, re.M)
        )
        fehlend = sorted(
            {r.befund for r in BEHOBEN if zahlwort(r.befund) not in ueberschriften}
        )
        assert fehlend == [], f"Fundstellen ohne Abschnitt: {fehlend}"

    def test_die_richtungen_stehen_in_der_reihenfolge_der_untersuchung(self) -> None:
        """Der Docstring sagt "wie sie untersucht wurden".

        Bis Befund 123 stand dort 111, 113, 119, dann 95, 96, 99, 102, 106 -
        weil ich meine Eintraege vor die mehrzeiligen gesetzt habe statt ans
        Ende. Geprueft wird nur der Schwanz ab Befund 90: Davor liegt die
        historisch gewachsene Reihenfolge, die bewusst nicht sortiert ist.
        """
        schwanz = [r.befund for r in GESCHLOSSEN if r.befund >= 90]
        assert schwanz == sorted(schwanz), (
            f"Reihenfolge ab Befund 90 zerfallen: {schwanz}"
        )

    def test_die_behobenen_stehen_aufsteigend(self) -> None:
        nummern = [r.befund for r in BEHOBEN]
        assert nummern == sorted(nummern)

    def test_werkzeugbefunde_stehen_nicht_unter_den_richtungen(self) -> None:
        """Die Namen, die den Fehler ausgeloest haben - als Wache."""
        namen = {r.name for r in GESCHLOSSEN}
        for verirrt in (
            "README auf dem Stand vom 1. August",
            "git status als Pruefmass",
            "Trockenlauf nur fuer den Zaehler",
            "Gate-Zahl abschreiben",
        ):
            assert verirrt not in namen

    def test_der_bericht_trennt_die_beiden_abschnitte(self) -> None:
        text = _lage().bericht()
        assert "GEMESSEN UND GESCHLOSSEN" in text
        assert "BEHOBEN AN DEN WERKZEUGEN" in text
        assert text.index("GEMESSEN UND GESCHLOSSEN") < text.index(
            "BEHOBEN AN DEN WERKZEUGEN"
        ), "Die Suchrichtungen gehoeren zuerst - sie sind die wichtigere Frage."

    def test_der_werkzeugabschnitt_sagt_was_er_nicht_bedeutet(self) -> None:
        """Sonst liest er sich wie Fortschritt."""
        assert "sagt nichts ueber die Aussichten" in _lage().bericht()


class TestLetzteFundstelle:
    """Befund 130: Ein Eintrag muss auf die **letzte** Messung zeigen.

    Der Eintrag *"Vola-Ziel ... Befund 21"* zeigte auf eine Tabelle, die
    Befund 23 zwei Befunde spaeter ersetzt hatte. Zwei Laeufe haben dort
    nachgeschlagen und den Unterschied zum heutigen Stand falschen Ursachen
    zugeschrieben.
    """

    def test_massgeblich_ist_die_nachmessung(self) -> None:
        from research.stand import Richtung

        ohne = Richtung("Etwas", "gemessen", 21)
        assert ohne.massgeblich == 21
        mit = Richtung("Etwas", "gemessen", 21, zuletzt=129)
        assert mit.massgeblich == 129

    def test_nachmessung_muss_nach_der_erstmessung_liegen(self) -> None:
        from research.stand import Richtung

        with pytest.raises(ValueError, match="keine Nachmessung"):
            Richtung("Etwas", "gemessen", 129, zuletzt=21)
        with pytest.raises(ValueError, match="keine Nachmessung"):
            Richtung("Etwas", "gemessen", 21, zuletzt=21)

    def test_zeile_nennt_beide_stellen(self) -> None:
        from research.stand import Richtung

        text = str(Richtung("Vola-Ziel", "Hub 0,009", 21, zuletzt=129))
        assert "Nr. 129" in text
        assert "zuerst 21" in text

    def test_nachgemessene_richtungen_zeigen_auf_ihre_nachmessung(self) -> None:
        """Die drei, die seit Befund 127 nachgemessen wurden."""
        from research.stand import GESCHLOSSEN

        nach = {r.name: r.zuletzt for r in GESCHLOSSEN}
        assert nach["Vola-Ziel"] == 129
        assert nach["Gewinnziel"] == 129
        assert nach["Termin-Overlay"] == 127


class TestDieStichprobeImUrteil:
    """Befund 148: Die Latte gilt fuer die Stichprobe, die das Gate nimmt.

    ``cli stand`` baute den Kandidaten mit ``Kandidat.aus_trades`` und liess
    ``effektiv`` leer. Die Latte fiel damit auf die rohe Trade-Zahl zurueck
    und meldete 15 % noetigen Zuwachs, wo das Gate 31 % verlangt - in dem
    Befehl, den ein Leser zuerst aufschlaegt.
    """

    def test_ohne_gemessene_stichprobe_steht_dort_mindestens(self) -> None:
        text = _lage(effektiv=None).urteil()

        assert "mindestens" in text
        assert "nicht gemessen" in text
        assert "152 rohen Trades" in text

    def test_mit_gemessener_stichprobe_faellt_das_mindestens_weg(self) -> None:
        text = _lage(effektiv=112).urteil()

        assert "mindestens" not in text
        assert "112 unabhaengigen Beobachtungen" in text
        assert "nicht gemessen" not in text

    def test_die_stichprobe_steht_immer_dabei(self) -> None:
        """Ein Zuwachs ohne seine Bezugsgroesse ist keine pruefbare Aussage."""
        for effektiv in (None, 112):
            text = _lage(effektiv=effektiv).urteil()
            assert "Beobachtungen" in text or "rohen Trades" in text

    def test_der_gemessene_unterschied(self) -> None:
        """**Die Zahl, um die es geht.**

        Bei 198 Versuchen verlangt das Gate am Spitzenkandidaten 0,3412 statt
        0,2984 - aus 15 % noetigem Zuwachs werden 31 %.
        """
        from research.suchbudget import Budget

        budget = Budget(versuche=198)
        roh, effektiv = budget.noetig_bei(152), budget.noetig_bei(112)

        assert roh is not None and effektiv is not None
        assert roh / 0.2597 - 1 == pytest.approx(0.15, abs=0.01)
        assert effektiv / 0.2597 - 1 == pytest.approx(0.31, abs=0.01)

    def test_ohne_latte_bleibt_das_urteil_knapp(self) -> None:
        """``None`` heisst "nicht gerechnet" - dann steht dort kein Satz dazu."""
        text = _lage(noetiger_sharpe=None).urteil()

        assert "Qualitaet je Trade um" not in text
        assert "Kein zugelassener Kandidat" in text


class TestUeberholteZahlenImRegister:
    """**Befund 156.** Ein Zeiger im Modulkopf deckt die ganze Datei.

    ``test_wer_eine_ueberholte_zahl_nennt_sagt_es_dazu`` prueft je **Datei**:
    Steht irgendwo "research.referenz", darf die Datei ueberholte Werte
    nennen. Fuer ``stand.py`` ist das zu grob - dort liegen vierzig
    unabhaengige Registereintraege unter einem einzigen Zeiger.

    Genau so hat *"Kalibrierung bewegt 0,3247, die Luecke ist 0,0860"*
    zwanzig Befunde ueberdauert: ein Betriebspunkt, den schon Befund 135
    ueberholt hatte, unter einem Kopf, der korrekt auf ``referenz.py``
    verweist.

    Ein Eintrag **darf** eine alte Zahl nennen, wenn er sie als Geschichte
    nennt - *"21 Stellen auf 0,8640"* ist richtig. Was ein Test nicht
    unterscheiden kann, ist Geschichte von Behauptung. Deshalb steht die
    Liste hier ausgeschrieben: Jeder neue Eintrag mit einer ueberholten Zahl
    faellt auf, bis jemand hingesehen hat.
    """

    def test_nur_bekannte_eintraege_nennen_ueberholte_zahlen(self) -> None:
        from research.referenz import veraltet

        gefunden = {
            r.name: veraltet(r.ergebnis)
            for r in (*GESCHLOSSEN, *BEHOBEN)
            if veraltet(r.ergebnis)
        }

        assert gefunden == {
            # Nennt, was Befund 135 gemessen hat - Geschichte, kein Stand.
            "Einteilung ohne Quartale": ("0,6026",),
            # Der Befund handelt davon, dass 21 Stellen auf 0,8640 standen.
            "Ueberholte Kennzahl im Modulkopf": ("0,8640",),
            # Nennt den Ausgangswert und daneben den heutigen (0,5881).
            "Frischer Datenabzug hob den Referenzpunkt": ("0,6026",),
        }, (
            "Ein Registereintrag nennt eine ueberholte Kennzahl. Ist sie als "
            "Geschichte gemeint, gehoert der Eintrag in diese Liste; ist sie "
            "als Stand gemeint, gehoert sie nachgemessen."
        )

    def test_die_fehlerbalken_sind_nachgemessen(self) -> None:
        """Der Eintrag, der den Test ausgeloest hat."""
        eintrag = next(r for r in BEHOBEN if r.name == "Stichprobe ohne Fehlerbalken")

        assert eintrag.zuletzt == 156
        assert "0,0860" not in eintrag.ergebnis
        assert "0,52x" in eintrag.ergebnis


class TestDerKerzenbestand:
    """**Befund 157.** Ein Auftragspunkt sagte fuenf Befunde lang "Daten
    liegen hier vor", nachdem ein Behaelterwechsel sie geloescht hatte.

    ``data_store`` liegt nicht im Repository. Der Fall wiederholt sich also
    bei jedem frischen Klon, und gepflegte Prosa merkt es nie.
    """

    def test_der_bestand_steht_im_bericht(self) -> None:
        lage = _lage(kerzenbestand="BTCUSD_BITSTAMP (1d 5355)")

        assert "Im Speicher: BTCUSD_BITSTAMP (1d 5355)" in lage.bericht()

    def test_ohne_messung_steht_keine_zeile(self) -> None:
        """Leer heisst "nicht gemessen" - und dann wird nichts behauptet."""
        assert "Im Speicher" not in _lage().bericht()

    def test_der_auftragspunkt_behauptet_keine_daten_mehr(self) -> None:
        from research.stand import AUFTRAG

        punkt = next(p for p in AUFTRAG if "backfill" in p.frage)

        assert not punkt.erledigt
        assert "Daten liegen hier vor" not in punkt.stand, (
            "genau dieser Satz war fuenf Befunde lang falsch"
        )
        assert "15-Minuten" in punkt.stand


class TestDieAussichtImBericht:
    """**Befund 160.** ``AUSSICHT`` rechnet die Entfernung seit Befund 132 und
    war an keiner Stelle angezeigt.

    Gepflegt, getestet, unsichtbar - die meistzitierte vorausschauende Zahl
    des Projekts stand nur im Modul. Dieselbe Bauart wie 152 (Randpuffer nur
    in Tests), 154 (Zeitskala) und 155 (Fenstervergleich): gebaut und nicht
    angeschlossen.
    """

    def test_beide_kandidaten_stehen_im_bericht(self) -> None:
        from research.referenz import AUSSICHT, AUSSICHT_VERBUND

        bericht = _lage(bestanden=7, gesamt=11, offen=("Deflated Sharpe",)).bericht()

        assert "WIE WEIT ES NOCH IST" in bericht
        assert AUSSICHT.als_zeile() in bericht
        assert AUSSICHT_VERBUND.als_zeile() in bericht

    def test_die_zahl_steht_nur_dort_und_nicht_in_der_prosa(self) -> None:
        """**Die Lehre aus 156 bis 159.** Eine gerechnete Zahl gehoert nicht
        als Text in einen Registereintrag - dort veraltet sie."""
        from research.referenz import AUSSICHT

        jahre = f"{AUSSICHT.jahre:.1f}"
        for r in (*GESCHLOSSEN, *BEHOBEN):
            assert jahre not in r.ergebnis, (
                f"'{r.name}' nennt die Jahreszahl im Text - sie wird "
                f"gerechnet und veraltet dort still"
            )

    def test_ein_zugelassener_kandidat_braucht_keine_entfernung(self) -> None:
        fertig = _lage(bestanden=11, gesamt=11, offen=())

        assert "WIE WEIT ES NOCH IST" not in fertig.bericht()

    def test_die_einordnung_nennt_was_die_zeit_nicht_loest(self) -> None:
        """**Die unbequeme Haelfte.** Von vier offenen Gates haengt eines an
        der Stichprobe; wer wartet, loest genau dieses."""
        bericht = _lage(
            bestanden=7,
            gesamt=11,
            offen=(
                "Messlatte",
                "Schlechtestes Jahr",
                "Deflated Sharpe",
                "Parameter-Plateau",
            ),
        ).bericht()

        assert "Die Zeit loest 1 von 4 offenen Gates" in bericht
        assert "bricht ein weiteres" in bericht
        assert "Messlatte" in bericht and "Parameter-Plateau" in bericht

    def test_ohne_das_stichprobengate_wird_nichts_eingeordnet(self) -> None:
        """Ist der Deflated Sharpe bestanden, sagt die Einordnung nichts -
        dann loest die Zeit gar nichts mehr."""
        bericht = _lage(bestanden=9, gesamt=11, offen=("Messlatte",)).bericht()

        assert "Die Zeit loest" not in bericht


class TestWasDieZeitBricht:
    """**Befund 161.** Befund 160 hat in den Bericht geschrieben, dass
    'Schlechtestes Jahr' mit jedem Jahr eine Gelegenheit mehr bekommt
    durchzufallen - als **Ueberlegung**, ausdruecklich nicht gemessen.

    Gemessen ist es jetzt, ueber sechs Historienlaengen, und es ist schaerfer
    als die Ueberlegung: Das Gate hat bei 2547 Tagen die Schwelle gerissen und
    liegt seither bei -10,3 gegen -10,00.

        1451 d  +5,97      2547 d  -10,30   <- ab hier durchgefallen
        1816 d  +5,44      2912 d  -10,30
        2320 d  -8,82      3300 d  -10,32
    """

    def test_die_gemessene_leiter_steht_im_bericht(self) -> None:
        bericht = _lage(
            bestanden=7,
            gesamt=11,
            offen=(
                "Messlatte",
                "Schlechtestes Jahr",
                "Deflated Sharpe",
                "Parameter-Plateau",
            ),
        ).bericht()

        for wert in ("+5,97", "-8,82", "-10,30", "-10,32"):
            assert wert in bericht, f"{wert} fehlt in der Leiter"
        assert "ab hier durchgefallen" in bericht
        assert "Befund 161" in bericht

    def test_der_mechanismus_steht_dabei(self) -> None:
        """Die Zahlen allein liessen offen, ob das Zufall ist. Der Grund ist
        mechanisch: ein Minimum ueber Zwoelfmonatsfenster."""
        bericht = _lage(
            bestanden=7, gesamt=11,
            offen=("Schlechtestes Jahr", "Deflated Sharpe"),
        ).bericht()

        assert "Minimum" in bericht
        assert "geht nicht wieder heraus" in bericht

    def test_ohne_das_gate_steht_die_leiter_nicht_da(self) -> None:
        """Sie gehoert zu diesem einen Gate - wo es nicht offen ist, waere sie
        nur Beiwerk."""
        bericht = _lage(
            bestanden=9, gesamt=11, offen=("Messlatte", "Deflated Sharpe")
        ).bericht()

        assert "Die Zeit loest" in bericht
        assert "ab hier durchgefallen" not in bericht


class TestGatesAufLaufendenExtrema:
    """**Befund 162.** Drei der elf Gates messen ein Extrem ueber die ganze
    Historie: Drawdown (laufendes Maximum), Schlechtestes Jahr (Minimum ueber
    Zwoelfmonatsfenster) und Monte-Carlo.

    Ein Maximum kann nicht fallen und ein Minimum nicht steigen. Wer laenger
    misst, misst ein groesseres Extrem - unabhaengig davon, ob die Strategie
    besser geworden ist. Gleichzeitig **braucht** der Deflated Sharpe mehr
    Historie. Die Gates ziehen gegeneinander.

    Das ist keine Lockerung und kein Vorschlag: Die Frage steht in
    ``ENTSCHEIDUNGEN``, wo die Entscheidungen des Nutzers stehen.
    """

    def test_die_frage_steht_unter_den_entscheidungen(self) -> None:
        frage = next(
            (e for e in ENTSCHEIDUNGEN if "laufenden Extrema" in e.frage), None
        )

        assert frage is not None, (
            "die Frage gehoert dorthin, wo die Entscheidungen des Nutzers "
            "stehen - nicht in eine geschlossene Richtung"
        )
        assert "Befund 162" in frage.zahl

    def test_alle_drei_gemessenen_werte_stehen_da(self) -> None:
        frage = next(e for e in ENTSCHEIDUNGEN if "laufenden Extrema" in e.frage)

        for wert in ("8,29", "10,64", "5,97", "-10,32", "7,83", "9,69"):
            assert wert in frage.zahl, f"{wert} fehlt in der Leiter"
        for schwelle in ("12,00", "-10,00", "15,00"):
            assert schwelle in frage.zahl, f"Schwelle {schwelle} fehlt"

    def test_es_wird_nichts_vorgeschlagen(self) -> None:
        """**Der Kern der Trennung.** Beide Lesarten sind vertretbar, und die
        Wahl faellt nicht hier - so steht es seit jeher im Modulkopf."""
        frage = next(e for e in ENTSCHEIDUNGEN if "laufenden Extrema" in e.frage)

        assert "Gelockert wird nichts" in frage.warum
        assert "faellt nicht hier" in frage.warum

    def test_die_gegenlaeufigkeit_ist_benannt(self) -> None:
        """Ohne sie liest sich der Eintrag wie eine Kleinigkeit."""
        frage = next(e for e in ENTSCHEIDUNGEN if "laufenden Extrema" in e.frage)

        assert "gegeneinander" in frage.warum
        assert "Deflated Sharpe" in frage.warum


class TestDerVergleichIstGemessen:
    """Die Zahlen beider Betriebspunkte stehen nur noch an einer Stelle.

    Der Auftragstext zum ``healthcheck`` trug sie bis Befund 165 als Prosa -
    eine zweite Kopie neben der gemessenen Gegenueberstellung im selben
    Bericht. Sie ist stehengeblieben, waehrend die Messung weiterlief:

        behauptet   14,83 % statt 13,47 %, Messlatte 0,17 Punkte
        gemessen    14,34 % statt 12,95 %, Messlatte 0,66 Punkte

    Die Gate-Zahlen (9 von 11 statt 7) stimmten noch - deshalb fiel es nicht
    auf. Wer nur die Haelfte prueft, die stimmt, prueft nichts.
    """

    @staticmethod
    def _punkt(**abweichung):
        from research.betriebspunkt import Betriebspunkt

        daten = {
            "name": "Spot", "trades": 158, "cagr_pct": 14.34,
            "rueckgang_pct": 9.87, "guete": 0.2708, "dsr": 0.5881,
            "bestanden": 9, "gesamt": 11,
            "offen": ("Messlatte", "Deflated Sharpe"),
        }
        daten.update(abweichung)
        return Betriebspunkt(**daten)

    def test_die_zahlen_kommen_aus_der_messung(self) -> None:
        text = _lage(cagr_pct=12.95, bestanden=7, zweitpunkt=self._punkt()).bericht()

        assert "14.34 % statt 12.95 %" in text
        assert "9 von 11 Gates statt 7" in text

    def test_die_messlatten_luecke_wird_gerechnet(self) -> None:
        """**Die Zahl, die am weitesten abgewichen ist.**

        15,00 - 14,34 = 0,66. Der alte Text sagte 0,17 - viermal naeher, als
        es gemessen ist, und ausgerechnet beim Gate, das dem Bestehen am
        naechsten steht.

        Geprueft wird der **Auftragsteil**, nicht der ganze Bericht: Im
        Register steht 0,17 weiterhin, und dort gehoert die Zahl auch hin -
        als Geschichte des Eintrags, nicht als Stand.
        """
        text = _lage(cagr_pct=12.95, zweitpunkt=self._punkt()).bericht()
        auftrag = text.split("NUR AUF DEINEM RECHNER")[1]

        assert "die Messlatte um 0.66 Punkte" in auftrag
        assert "0,17" not in auftrag

    def test_andere_zahlen_ergeben_andere_saetze(self) -> None:
        """Sonst koennte der Satz fest verdrahtet sein und der Test es nicht
        merken."""
        text = _lage(
            cagr_pct=11.00, bestanden=6, zweitpunkt=self._punkt(cagr_pct=16.50,
                                                                bestanden=10),
        ).bericht()

        assert "16.50 % statt 11.00 %" in text
        assert "10 von 11 Gates statt 6" in text
        # Ueber der Schwelle: die Luecke ist negativ und wird trotzdem genannt,
        # weil 'Messlatte' offen gemeldet ist.
        assert "die Messlatte um -1.50 Punkte" in text

    def test_ohne_messung_wird_nichts_erfunden(self) -> None:
        """**Der Fall, der aus einer Luecke eine Behauptung machen wuerde.**

        Kommt der zweite Punkt nicht zustande, steht dort ein Verweis - keine
        Naeherung und keine gepflegte Zahl.
        """
        text = _lage(zweitpunkt=None).bericht()

        assert "DIE BEIDEN BETRIEBSPUNKTE" in text
        assert "statt" not in text.split("NUR AUF DEINEM RECHNER")[1]
        assert "{vergleich}" not in text

    def test_ohne_offene_gates_faellt_der_zusatz_weg(self) -> None:
        text = _lage(zweitpunkt=self._punkt(bestanden=11, offen=())).bericht()

        assert "11 von 11 Gates" in text
        assert "Offen bleiben dort" not in text

    def test_der_platzhalter_bleibt_nirgends_stehen(self) -> None:
        for punkt in (None, self._punkt()):
            assert "{vergleich}" not in _lage(zweitpunkt=punkt).bericht()

    def test_keine_gepflegten_betriebspunkt_zahlen_mehr_im_auftragstext(
        self,
    ) -> None:
        """**Die Wache gegen den Rueckfall.**

        Ein Satz der Form "14,83 % statt 13,47 %" im Auftragstext waere wieder
        eine zweite Kopie - und die naechste, die stehenbleibt.
        """
        import re

        for _, warum in BEIM_NUTZER:
            assert not re.search(r"\d+,\d+ %\s*statt", warum), warum


class TestNutzerbefehleSindAusfuehrbar:
    """Die vier Zeilen, an denen das Projekt haengt - laufen sie ueberhaupt?

    Unter 'NUR AUF DEINEM RECHNER' steht alles, was aus diesem Behaelter
    heraus nicht geht: Die Bybit-Sperre ist regional, und ohne die Kerzen
    kann nichts zugelassen werden (Befund 102). Es ist der einzige Abschnitt
    des Berichts, dem jemand **folgen** soll.

    Geprueft wurde daran bis Befund 167 nur, dass die Zeile mit
    ``python -m cli`` beginnt und eine Begruendung hat. Ob der Befehl
    existiert, ob die Optionen existieren, ob die Zeile ueberhaupt eine
    Befehlszeile ist - nichts davon. Fuer die README gibt es diese Wache
    seit Befund 118; fuer die Anleitung, der der Nutzer wirklich folgt,
    gab es sie nicht.

    Wie berechtigt die Sorge ist, zeigt dieser Lauf selbst: Ich habe
    ``cli partnerkarte`` aufgerufen - den Befehl gibt es nicht, er heisst
    ``partner``. Ein Name aus dem Gedaechtnis ist eine Vermutung.
    """

    @staticmethod
    def _zerlegt(befehl: str) -> tuple[str, list[str]]:
        import shlex

        teile = shlex.split(befehl)
        assert teile[:3] == ["python", "-m", "cli"], befehl
        return teile[3], teile[4:]

    @staticmethod
    def _parst(name: str, argumente: list[str]) -> bool:
        """Laesst sich diese Befehlszeile ueberhaupt einlesen?

        Geprueft wird das **Ergebnis**, nicht der Ausnahmetyp: Typer bringt
        seit 0.12 eigene ``click``-Klassen mit, und ``click.UsageError``
        faengt sie nicht. Ein Test, der auf den Typ zeigt, prueft dann die
        Bibliotheksversion statt die Befehlszeile - das war mein erster
        Anlauf hier, und er ging gruen durch, wo er es nicht durfte.
        """
        import typer.main

        import cli

        kommando = typer.main.get_command(cli.app).commands.get(name)
        if kommando is None:
            return False
        try:
            ctx = kommando.make_context(name, list(argumente), resilient_parsing=False)
        except Exception:
            return False
        ctx.close()
        return True

    def test_jede_zeile_ist_eine_befehlszeile(self) -> None:
        """**Der Fall, den es hier wirklich gab.**

        ``backfill --von 2017-08-16, dann wettbewerb`` stand als Befehl da und
        ist keiner: Wer ihn kopiert, bekommt "Got unexpected extra
        argument(s) (dann wettbewerb)". Zwei Schritte gehoeren in zwei Zeilen -
        auch damit der zweite eine eigene Begruendung traegt und von dieser
        Wache erfasst wird.
        """
        for befehl, _ in BEIM_NUTZER:
            name, argumente = self._zerlegt(befehl)

            assert self._parst(name, argumente), befehl

    def test_die_wache_bemerkt_falsche_namen_und_optionen(self) -> None:
        """Sonst prueft der Test oben nur, dass nichts kaputt ist.

        ``partnerkarte`` ist kein erfundenes Beispiel: Ich habe den Befehl in
        diesem Lauf aufgerufen. Er heisst ``partner``.
        """
        assert not self._parst("partnerkarte", [])
        assert not self._parst("backfill", ["--gibtsnicht", "1"])
        assert not self._parst("backfill", ["--von", "2017-08-16", "dann"])
        assert self._parst("backfill", ["--von", "2017-08-16"])

    def test_wettbewerb_steht_als_eigener_schritt(self) -> None:
        """Ohne ihn endet die Anleitung beim Laden der Daten - und der
        Wettbewerb ist der Schritt, der daraus einen Kandidaten macht."""
        namen = [self._zerlegt(b)[0] for b, _ in BEIM_NUTZER]

        assert "wettbewerb" in namen
        assert "backfill" in namen
        assert namen.index("backfill") < namen.index("wettbewerb"), (
            "Erst laden, dann suchen."
        )


class TestDerZweiteWeg:
    """**Befund 172.** Die folgenreichste Messung der letzten fuenf Laeufe
    stand in einem Befehl, den niemand von sich aus aufruft.

    Befund 168 hat den Bestand in seine eigene Grundgesamtheit eingeordnet -
    sein Vorsprung ist kleiner als das, was Auswahl aus 198 Versuchen ohnehin
    erzeugt. Wer ``cli stand`` las, sah "es fehlen 0,66 Guete" und hielt das
    fuer knapp. Dieselbe Bauart wie Befund 160 (Entfernung nirgends
    angezeigt), nur mit dem wichtigeren Ergebnis.
    """

    def test_der_bericht_nennt_die_zweite_frage(self) -> None:
        text = _lage().bericht()

        assert "OB DER VORSPRUNG ECHT IST" in text
        assert "Katalog, aus dem er ausgewaehlt" in text
        assert "cli vorratsdecke" in text

    def test_er_nennt_die_fundstellen(self) -> None:
        """Ohne sie ist es eine Behauptung - die Regel dieses Registers."""
        text = _lage().bericht()

        for nummer in ("168", "169", "171"):
            assert nummer in text

    def test_die_zurueckgenommenen_stehen_nicht_unmarkiert_da(self) -> None:
        """**Befund 197.** Der Abschnitt nannte drei Befunde als seinen Beleg.

        Befund 183 hat 168 und 169 zurueckgenommen - der Katalog dieser
        Messungen war nach der Groessenlogik gefiltert (Befund 182) -, und
        Befund 188 hat die Viertelstunden aus 171 ersetzt. Der Abschnitt
        schickte den Leser also an drei Stellen, von denen zwei
        zurueckgenommen und eine ueberholt sind.

        Das ist dieselbe Bauart wie Befund 157: ein Text, der stehenblieb,
        waehrend die Messung weiterlief. Die Fundstellen duerfen bleiben -
        sie sind die Geschichte der Frage -, aber nicht unmarkiert.
        """
        abschnitt = "\n".join(_lage()._zweiter_weg())

        assert "183" in abschnitt, "die berichtigende Messung fehlt"
        assert "188" in abschnitt, "die ersetzende Messung fehlt"
        assert "zurueckgenommen" in abschnitt

    def test_er_traegt_keine_gepflegte_zahl(self) -> None:
        """**Die Bedingung, unter der dieser Abschnitt ueberhaupt dastehen
        darf.**

        Vier Befunde handeln von Zahlen, die an zwei Stellen standen und
        auseinanderliefen (158, 159, 165, 166). Der Vorsprung wird gerechnet,
        nicht hier gepflegt - sonst waere dieser Abschnitt die fuenfte
        Stelle.
        """
        import re

        # Geprueft werden die Zeilen, die **diese Methode** liefert - nicht
        # ein Ausschnitt des Berichts. Der erste Anlauf schnitt am naechsten
        # Absatz und erwischte das halbe Register mit.
        abschnitt = "\n".join(_lage()._zweiter_weg())
        zahlen = [z for z in re.findall(r"\d+[,.]\d+", abschnitt)]

        assert zahlen == [], f"gepflegte Zahl im Abschnitt: {zahlen}"
        assert "OB DER VORSPRUNG ECHT IST" in abschnitt

    def test_ein_zugelassener_kandidat_braucht_ihn_nicht(self) -> None:
        """Steht die Zulassung, ist die Frage beantwortet - dann ist der
        Abschnitt eine Warnung ohne Anlass."""
        text = _lage(bestanden=11, gesamt=11, offen=()).bericht()

        assert "OB DER VORSPRUNG ECHT IST" not in text


class TestWasDerWettbewerbKostet:
    """**Befund 198.** Das zweite Artefakt mit derselben Luecke.

    Befund 196 hat gefunden, dass der Auftrag an die Research-KI drei
    Kriterien nannte und verschwieg, wie es den sieben Vorgaengern ergangen
    ist. ``BEIM_NUTZER`` ist das andere Artefakt, das kuenftige Versuche
    steuert - es sagt dem Nutzer, welche Befehle er auf seinem Rechner
    ausfuehren soll.

    Es sagte, **wie** man den Wettbewerb startet, und nicht, **was** er
    kostet: Jeder geprueft Kandidat hebt die Latte des Deflated Sharpe fuer
    alle folgenden, dauerhaft.
    """

    def test_der_wettbewerb_nennt_seinen_preis(self) -> None:
        text = _lage().bericht()
        i = text.index("python -m cli wettbewerb")
        abschnitt = text[i : i + 900]

        assert "kostet einen Versuch" in abschnitt
        assert "dauerhaft" in abschnitt

    def test_er_nennt_die_gemessenen_belege(self) -> None:
        """Ohne sie waere die Warnung eine Meinung."""
        satz = _lage()._kostensatz()

        assert "137" in satz and "119" in satz, "der Stand aus Befund 194 fehlt"
        assert "sieben Partner" in satz, "das Holdout-Ergebnis fehlt"

    def test_der_versuchsstand_wird_gerechnet_und_nicht_gepflegt(self) -> None:
        """**Die Bedingung, unter der die Zahl dort stehen darf.**

        Vier Befunde handeln von Zahlen, die an zwei Stellen standen und
        auseinanderliefen (158, 159, 165, 166). Der Versuchsstand kommt aus
        derselben Quelle wie oben im Kopf des Berichts.
        """
        assert "198" in _lage(versuche=198)._kostensatz()
        assert "250" in _lage(versuche=250)._kostensatz()

    def test_die_warnung_verbietet_nichts(self) -> None:
        """Sie nennt den Preis - die Entscheidung faellt woanders."""
        satz = _lage()._kostensatz()

        assert "kein Grund, es nicht zu tun" in satz

    def test_ohne_platzhalter_bleibt_der_text_unveraendert(self) -> None:
        """Die uebrigen Eintraege duerfen keine Klammern verlieren."""
        text = _lage().bericht()

        assert "{versuchskosten}" not in text
        assert "{vergleich}" not in text


class TestDasOffeneRegisterWirdAuchGezeigt:
    """**Befund 208.** Elf Eintraege, gepflegt ueber Dutzende Befunde, unsichtbar.

    ``OFFEN`` stand seit seiner Anlage in ``research/stand.py`` und war an
    **keiner** Stelle referenziert - nicht im Bericht, nicht in ``cli.py``,
    nicht in einem Test. Ich habe es durch die Befunde 188, 190, 195 und 202
    bis 205 hindurch nachgezogen, ohne zu bemerken, dass es niemand zu sehen
    bekommt.

    Dieselbe Bauart wie Befund 160: Dort rechnete ``AUSSICHT`` seit Befund
    132 die Entfernung zur Schwelle - die meistzitierte vorausschauende Zahl
    des Projekts - und stand in keinem Bericht.

    Und der Unterschied zu ``GESCHLOSSEN`` ist der wichtigere von beiden: Wer
    wissen will, was als naechstes zu tun ist, liest die offenen Richtungen
    und nicht die zugemachten.
    """

    def test_der_bericht_zeigt_die_offenen_richtungen(self) -> None:
        text = _lage().bericht()

        assert "GEMESSEN UND OFFEN" in text
        for r in OFFEN:
            assert r.name in text, f"'{r.name}' fehlt im Bericht"

    def test_jede_offene_richtung_hat_eine_fundstelle(self) -> None:
        """Dieselbe Regel wie fuer die geschlossenen - der Datentyp erzwingt
        sie, aber gemessen hat es hier nie jemand."""
        assert OFFEN
        for r in OFFEN:
            assert r.befund > 0, r.name
            assert r.ergebnis, r.name

    def test_keine_richtung_steht_offen_und_geschlossen(self) -> None:
        """**Der Test, der einen Widerspruch faende.**

        Eine Richtung kann nicht zugleich gemessen-zu und offen sein. Ohne
        Pruefung koennte ein Eintrag beim Schliessen in der einen Liste
        landen und in der anderen stehenbleiben - und der Bericht wuerde
        beides behaupten.
        """
        for register, name in ((GESCHLOSSEN, "GESCHLOSSEN"), (BEHOBEN, "BEHOBEN")):
            doppelt = {r.name for r in OFFEN} & {r.name for r in register}
            assert doppelt == set(), f"in OFFEN und {name}: {doppelt}"

    def test_keine_offene_richtung_doppelt(self) -> None:
        namen = [r.name for r in OFFEN]

        assert len(namen) == len(set(namen))

    def test_jede_fundstelle_gibt_es_wirklich(self) -> None:
        """Wie fuer ``GESCHLOSSEN`` seit Befund 90 - hier war es nie geprueft."""
        import re

        text = Path("strategies/BEFUND.md").read_text()
        ueberschriften = set(re.findall(r"^## ([A-Za-zaeoeueAEOEUEss]+)\.", text, re.M))
        nummern = {r.befund for r in OFFEN} | {r.zuletzt for r in OFFEN if r.zuletzt}
        fehlend = sorted(n for n in nummern if zahlwort(n) not in ueberschriften)

        assert fehlend == [], f"Fundstellen ohne Abschnitt im Laborbuch: {fehlend}"

    def test_es_steht_vor_den_werkzeugbefunden(self) -> None:
        """Die Reihenfolge sagt, was wichtiger ist: erst zu, dann offen, dann
        die Werkzeuge - und die zuletzt, weil sie ueber die Aussichten nichts
        sagen (Befund 123)."""
        text = _lage().bericht()

        assert text.index("GEMESSEN UND GESCHLOSSEN") < text.index("GEMESSEN UND OFFEN")
        assert text.index("GEMESSEN UND OFFEN") < text.index("BEHOBEN AN DEN")


#: Ab welcher Laenge ein Feldtext im Bericht wiedergefunden werden muss.
#:
#: Kurze Felder (``"offen"``, ``"OK"``) sagen nichts darueber, ob ein Eintrag
#: angezeigt wird - sie stehen in jedem Bericht irgendwo.
_AUSSAGEKRAEFTIG = 12


def _register() -> dict[str, tuple]:
    """Die Register in ``research.stand``, gefunden statt aufgezaehlt.

    Ein Register ist ein oeffentlicher, nicht leerer Tupel auf Modulebene,
    dessen Eintraege entweder alle Dataclasses sind (``GESCHLOSSEN``,
    ``OFFEN``, ``BEHOBEN``, ``AUFTRAG``, ``ENTSCHEIDUNGEN``) oder alle
    Zeichenketten-Tupel (``BEIM_NUTZER``).

    **Gefunden, nicht aufgezaehlt** - das ist der ganze Punkt. Eine Liste von
    Hand haette Befund 208 nicht verhindert: Wer ein Register anlegt und
    vergisst, es anzuzeigen, vergisst genauso, es in die Liste einzutragen.
    """
    aus: dict[str, tuple] = {}
    for name, wert in vars(stand).items():
        if name.startswith("_") or not isinstance(wert, tuple) or not wert:
            continue
        dataclassen = all(dataclasses.is_dataclass(e) for e in wert)
        strtupel = all(
            isinstance(e, tuple) and all(isinstance(x, str) for x in e) for e in wert
        )
        if dataclassen or strtupel:
            aus[name] = wert
    return aus


def _feldtexte(eintrag) -> list[str]:
    """Die aussagekraeftigen Zeichenketten eines Registereintrags.

    Texte mit ``{`` fallen heraus: ``BEIM_NUTZER`` traegt Platzhalter, die
    der Bericht vor der Ausgabe ersetzt (Befund 196). Ihr Rohtext steht dort
    also zu Recht nicht.
    """
    if dataclasses.is_dataclass(eintrag):
        werte = [getattr(eintrag, f.name) for f in dataclasses.fields(eintrag)]
    else:
        werte = list(eintrag)
    return [
        w
        for w in werte
        if isinstance(w, str) and "{" not in w and len(w) >= _AUSSAGEKRAEFTIG
    ]


def _fehlstellen(text: str) -> list[tuple[str, str]]:
    """Welche Registertexte im Bericht **nicht** vorkommen."""
    return [
        (name, t)
        for name, wert in sorted(_register().items())
        for e in wert
        for t in _feldtexte(e)
        if t not in text
    ]


class TestJedesRegisterWirdAuchGezeigt:
    """**Befund 209.** Aus Befund 208 eine Zusicherung machen statt einer Zeile.

    Befund 208 hat ``OFFEN`` angezeigt - elf Eintraege, die dutzende Befunde
    lang gepflegt und nie ausgegeben wurden. Damit war *dieser* Fall behoben
    und der *Fall* offen: Jedes Register hier hat seinen eigenen, von Hand
    geschriebenen Test, der es beim Namen nennt. Ein siebtes Register bekaeme
    keinen, ausser jemand denkt daran - und genau daran hat acht Befunde lang
    niemand gedacht.

    Deshalb zaehlt dieser Test die Register nicht auf, sondern **sucht sie**.
    Was aussieht wie ein Register, muss im Bericht ankommen.

    ``test_die_regel_ist_nicht_blind`` traegt die Klasse: Eine Pruefung, die
    nichts finden kann, besteht immer.
    """

    def test_die_bekannten_register_werden_gefunden(self) -> None:
        """Ohne das koennte die Suche stillschweigend leerlaufen."""
        gefunden = _register()

        assert set(gefunden) == {
            "AUFTRAG",
            "BEHOBEN",
            "BEIM_NUTZER",
            "ENTSCHEIDUNGEN",
            "GESCHLOSSEN",
            "OFFEN",
        }

    def test_jedes_register_erreicht_den_bericht(self) -> None:
        fehlt = _fehlstellen(_lage().bericht())

        assert fehlt == [], f"gepflegt, aber nirgends angezeigt: {fehlt}"

    def test_die_regel_ist_nicht_blind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Die Gegenprobe: ein siebtes Register, das der Bericht nicht kennt.

        Genau die Lage von Befund 208 - angelegt, gepflegt, unsichtbar. Wenn
        die Pruefung sie nicht meldet, sichert sie nichts zu.
        """
        monkeypatch.setattr(
            stand,
            "SPAETERES_REGISTER",
            (
                Richtung(
                    name="Etwas Ungezeigtes",
                    ergebnis="gemessen und nirgends sichtbar",
                    befund=42,
                ),
            ),
            raising=False,
        )

        fehlt = _fehlstellen(_lage().bericht())

        assert [n for n, _ in fehlt] == ["SPAETERES_REGISTER"] * 2

    def test_kurze_felder_zaehlen_nicht_als_beleg(self) -> None:
        """Warum es die Laengenschwelle gibt.

        ``Auftragspunkt.stand`` kann "offen" sein - das steht in jedem
        Bericht und wuerde eine Anzeige vortaeuschen, die es nicht gibt.
        """
        assert _feldtexte(("ok", "cli backfill --intervall 15")) == [
            "cli backfill --intervall 15"
        ]


class TestBeideWegeDesWettbewerbsStehenDa:
    """**Befund 210.** Behoben laut Register, unerreichbar in der Anleitung.

    Befund 146 hat die Research-KI an den Wettbewerb gehaengt und den Eintrag
    "Research-KI nicht am Wettbewerb" auf behoben gesetzt. Das stimmt - als
    Schalter. ``--ki`` steht auf aus, und die Zeile, der der Nutzer folgt,
    hat ihn nie genannt.

    Die Sweep-Gegenprobe aus Befund 209 konnte das nicht finden: Sie hat
    Importe gemessen, und der Import war da. Unerreichbar war der Weg nicht
    mangels Verdrahtung, sondern wegen einer Vorgabe.
    """

    @staticmethod
    def _wettbewerbszeilen() -> list[str]:
        return [b for b, _ in BEIM_NUTZER if "wettbewerb" in b]

    def test_beide_wege_stehen_als_befehlszeile(self) -> None:
        """Nicht als Prosa - das war der Fehler aus Befund 167."""
        zeilen = self._wettbewerbszeilen()

        assert "python -m cli wettbewerb" in zeilen
        assert "python -m cli wettbewerb --ki" in zeilen

    def test_der_schalter_wird_nicht_stillschweigend_verschwiegen(self) -> None:
        """Wer nur die erste Zeile liest, muss erfahren, was ihm entgeht."""
        ohne = next(
            w for b, w in BEIM_NUTZER if b == "python -m cli wettbewerb"
        )

        assert "Research-KI" in ohne
        assert "ohne" in ohne.lower()

    def test_die_entscheidung_ist_beziffert_und_nicht_beantwortet(self) -> None:
        """``ENTSCHEIDUNGEN`` benennt und beziffert - es empfiehlt nicht.

        Die Bilanz der KI ist null von fuenf, und diese fuenf sind vor der
        Korrektur aus Befund 76 entstanden. Beides muss dastehen: die Zahl
        allein waere ein Urteil ueber ein Werkzeug, das es so nicht mehr gibt.
        """
        eintrag = next(
            e for e in ENTSCHEIDUNGEN if "Research-KI" in e.frage
        )

        assert "fuenf" in eintrag.zahl and "0,25" in eintrag.zahl
        assert "76" in eintrag.zahl, "die Korrektur des Auftrags fehlt"
        assert "Grundstock" in eintrag.zahl, "der Beleg-Vorbehalt fehlt"
        assert "hebt die Huerde" in eintrag.warum, "der Preis fehlt"

    def test_der_preis_steht_neben_der_chance(self) -> None:
        """Ein Vorschlag ist ein Versuch, und jeder Versuch hebt die Huerde
        des Deflated Sharpe fuer alle folgenden (Befund 71). Wer die KI
        empfiehlt, ohne das zu sagen, empfiehlt einen sicheren Aufschlag
        gegen eine unbelegte Chance."""
        text = _lage().bericht()

        assert "Soll die Research-KI mitlaufen" in text
        assert "python -m cli wettbewerb --ki" in text


class TestDieFalscheGatezahlKommtNichtWieder:
    """**Befund 210, Nebenfund.** "Neun Gates" hat 21 Versuche gekostet.

    Befund 104 hat einundzwanzig Versuche fuer eine Suche ausgegeben, deren
    Docstring neun statt elf Gates nannte; Befund 120 hat die Stelle
    berichtigt. In ``_ask_the_analyst`` stand die Zahl weiter - und
    ausgerechnet dort, wo die Vorschlaege der KI durch die Gates gehen.

    Eine berichtigte Zahl an einer Stelle ist keine berichtigte Zahl.
    """

    @staticmethod
    def _fundstellen(text: str) -> list[str]:
        """Zeilen, die neun Gates **behaupten**.

        Erlaubt ist, ueber den Fehler zu reden - "neun Gates statt elf" oder
        die Zahl in Anfuehrungszeichen. Nicht erlaubt ist, sie zu behaupten.
        Der Unterschied ist der zwischen Erinnerung und Wiederholung.

        Nimmt den Text als Argument, damit die Regel selbst pruefbar ist:
        Eine Wache, die nur gegen die eigene Datei laeuft, kann nicht zeigen,
        dass sie etwas faende (Befund 209).
        """
        import re

        return [
            z
            for z in re.findall(r"[^\n]*neun Gates[^\n]*", text)
            if "statt elf" not in z and '"neun Gates"' not in z
        ]

    def test_keine_stelle_nennt_mehr_neun_gates(self) -> None:
        assert self._fundstellen(Path("cli.py").read_text()) == []

    def test_die_regel_faende_einen_rueckfall(self) -> None:
        """Die Gegenprobe: genau der Satz, der bis heute dort stand."""
        rueckfall = "    danach dieselben neun Gates wie ein Genom.\n"

        assert len(self._fundstellen(rueckfall)) == 1

    def test_ueber_den_fehler_reden_bleibt_erlaubt(self) -> None:
        assert self._fundstellen("er nannte neun Gates statt elf\n") == []
        assert self._fundstellen('bis 210 stand hier "neun Gates"\n') == []

    def test_die_geschichte_darf_stehenbleiben(self) -> None:
        """Sonst loescht der Test oben die Erinnerung mit dem Fehler."""
        text = Path("cli.py").read_text()

        assert "neun Gates statt elf" in text
