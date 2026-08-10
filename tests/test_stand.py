"""Wo steht das Projekt - und was daran gemessen ist statt behauptet.

Zwei Tests tragen die Datei:

* ``test_geschlossene_richtung_braucht_eine_fundstelle`` - eine Richtung ohne
  Verweis auf die Messung ist eine Behauptung. Der Datentyp laesst sie nicht
  zu.
* ``test_urteil_nennt_den_abstand_statt_zu_beruhigen`` - "7 von 11" klingt nach
  wenig Rest. Der Abstand zum haertesten Gate sagt, wie viel es wirklich ist.
"""

from __future__ import annotations

import pytest

from research.stand import (
    BEIM_NUTZER,
    BUDGET,
    ENTSCHEIDUNGEN,
    GESCHLOSSEN,
    Lage,
    Richtung,
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
