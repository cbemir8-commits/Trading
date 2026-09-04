"""Der Auftrag an die Research-KI - und was jahrelang darin fehlte.

Zwei Tests tragen diese Datei:

``test_das_bindende_gate_steht_im_auftrag`` - ``build_prompt`` nannte fuenf
Zulassungsschwellen, aber nicht den Deflated Sharpe. Genau der ist das einzige
noch ungeloeste Gate, und die Huerde steigt mit jedem Vorschlag.

``test_die_trade_schwelle_war_zu_niedrig`` - Der Auftrag verlangte 100 Trades,
gebraucht werden mindestens 120. Der Analyst hat auf das falsche Ziel
optimiert, und niemand hat es ihm gesagt.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from research.analyst import build_prompt
from research.auftragslage import AEHNLICH, Auftragslage, aus_messungen
from research.gates import GateThresholds

#: Der gemessene Stand nach Befund 75.
STAND = {
    "versuche": 169,
    "bestand_trades": 154,
    "bestand_sharpe": 0.2591,
    "kopplung": -0.533,
}


def lage() -> Auftragslage:
    return aus_messungen(**STAND)


class TestZahlen:
    def test_die_guete_ist_sharpe_mal_wurzel_trades(self) -> None:
        assert lage().bestand_guete == pytest.approx(0.2591 * 154**0.5)

    def test_die_luecke_ist_der_abstand_zur_schwelle(self) -> None:
        aktuell = lage()

        assert aktuell.fehlt == pytest.approx(
            aktuell.noetige_guete - aktuell.bestand_guete
        )
        assert aktuell.fehlt > 0, "Sonst waere das Gate bestanden"

    def test_alle_zahlen_kommen_aus_den_vorhandenen_modulen(self) -> None:
        """Nichts wird hier zweitgerechnet - wer die Schwelle in ``gates.py``
        aendert, aendert diesen Auftragstext mit."""
        from research.verbund import noetige_guete

        assert lage().noetige_guete == pytest.approx(noetige_guete(154, 169))

    def test_mehr_versuche_heben_die_anforderung(self) -> None:
        frueh = aus_messungen(**{**STAND, "versuche": 100})
        spaet = aus_messungen(**{**STAND, "versuche": 500})

        assert spaet.noetige_guete > frueh.noetige_guete


class TestAuftragstext:
    def test_das_bindende_gate_steht_im_auftrag(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Von elf Gates ist genau eines ungeloest, und es kam im Auftrag nicht
        vor. Ein Analyst, der es nicht kennt, kann nicht darauf zielen.
        """
        text = lage().als_auftrag()

        assert "Deflated Sharpe" in text
        assert "Guete" in text
        assert "169" in text, "Der Versuchsstand gehoert dazu"

    def test_die_trade_schwelle_war_zu_niedrig(self) -> None:
        """**Der zweite tragende Test.**

        ``min_oos_trades`` steht bei 100 - das ist die einzige Trade-Zahl, die
        der Auftrag bisher nannte. Gebraucht werden mindestens 120, und
        darunter genuegt selbst ein sehr hoher Sharpe je Trade nicht.
        """
        aktuell = lage()

        assert aktuell.partner_trades > GateThresholds().min_oos_trades
        assert f"Mindestens {aktuell.partner_trades} Trades" in aktuell.als_auftrag()

    def test_der_hebel_wird_am_zweiten_punkt_sichtbar(self) -> None:
        """**Eine irrefuehrende Zeile, die im ersten Anlauf drinstand.**

        An der Wende ist der noetige Sharpe je Trade per Definition gleich dem
        des Bestands. Der Text behauptete dort trotzdem "das ist weniger als
        der Bestand hat" - schlicht falsch. Jetzt steht die zweite Stuetzstelle
        daneben, an der der Hebel wirklich zu sehen ist.
        """
        aktuell = lage()

        assert aktuell.bedarf_bei_doppelt < aktuell.partner_sharpe
        assert "weniger als der Bestand hat" not in aktuell.als_auftrag()
        # Seit Befund 82 steht die Zahl in einem Satz, der drei Stuetzstellen
        # vergleicht - der Hebel bleibt sichtbar, der Wortlaut hat sich
        # geaendert.
        assert f"bei {aktuell.partner_trades * 2}" in aktuell.als_auftrag()

    def test_die_unabhaengigkeit_wird_beziffert(self) -> None:
        """'Anders sein' ist kein pruefbares Kriterium - eine Zahl schon.

        Die Anforderung bleibt, die Zahl hat gewechselt: Bis Befund 141 stand
        hier die Fensterkorrelation. Ueber vierzehn gemessene Paare ordnet die
        aber nichts (+0,04), und der beste Partner haette sie gerissen. Jetzt
        steht dort, was gemessen zaehlt - und dass die alte Groesse es nicht
        tut.

        **Befund 199 hat den dritten Beleg ersetzt.** Hier stand "+13
        unabhaengige Beobachtungen fuer 53 zusaetzliche Trades" - *der eine*
        gemessene Partner aus Befund 140. Inzwischen sind achtzehn gemessen,
        und ueber die reicht der Zuwachs von -14 bis +236. Die alte Zahl war
        nicht falsch, sie war die einzige.
        """
        text = lage().als_auftrag()

        assert "Trendfolge" in text
        assert "+0,04" in text, "die widerlegte Groesse wird beziffert"
        assert "-0,53" in text, "und die, die einmal Signal trug"
        assert "+236" in text, "was ein Verbund ueber 18 Paare beitraegt"

    def test_die_fensterkorrelation_ist_kein_kriterium_mehr(self) -> None:
        """Sonst suchte die KI nach einer Groesse, die nichts vorhersagt.

        Seit Befund 146 haengt die Research-KI am Wettbewerb. Ein Auftrag, der
        sie auf die Fensterkorrelation ansetzt, richtet damit realen Schaden
        an: Er kostet Versuche und hebt die Huerde fuer alle.
        """
        # Normalisiert, weil der Auftrag umbricht: Ein Test, der ueber einen
        # Zeilenumbruch stolpert, prueft die Formatierung statt der Aussage.
        text = " ".join(lage().als_auftrag().split())

        assert f"ueber {AEHNLICH:.1f} zaehlt" not in text
        assert "nicht danach ausgesucht und nicht danach verworfen" in text

    def test_der_preis_eines_versuchs_steht_dabei(self) -> None:
        text = lage().als_auftrag()

        assert "Was ein Vorschlag kostet" in text
        assert "dauerhaft" in text

    def test_ohne_kopplung_faellt_der_abschnitt_weg(self) -> None:
        """Er ist ein Befund, keine Ausschmueckung."""
        ohne = aus_messungen(**{**STAND, "kopplung": None})

        assert "Warum das schwer ist" not in ohne.als_auftrag()


class TestWoDieKopplungSteht:
    """**Befund 180.** Der Auftrag gab elf Befunde lang Befund 75s Lesart
    weiter: die Kopplung als Eigenschaft *des Vorrats*.

    Befund 169 hat sie eingegrenzt - getragen wird sie von einer Familie. Der
    Unterschied aendert die Suchrichtung: "der Vorrat ist gekoppelt" heisst
    such feiner, "diese Familie ist gekoppelt" heisst such woanders.
    """

    GEMESSEN: ClassVar[dict] = {
        **STAND,
        "kopplung": -0.714,
        "kopplung_traegt": "sma",
        "familien": (("sma", 9), ("roc", 2), ("ema", 1)),
        "familienpreis": 3.70,
        "familienpreis_bei": 97,
    }

    def test_die_familie_wird_benannt_und_die_richtung_daraus(self) -> None:
        text = aus_messungen(**self.GEMESSEN).als_auftrag()

        assert "einer einzigen Familie: 'sma'" in text
        assert "such woanders" in text

    def test_ohne_traeger_bleibt_die_alte_lesart(self) -> None:
        """Wo nicht gemessen ist, wer die Kopplung traegt, wird auch keine
        Familie erfunden - dann steht dort weiter der allgemeine Satz."""
        text = aus_messungen(**{**self.GEMESSEN, "kopplung_traegt": None}).als_auftrag()

        assert "einzigen Familie" not in text
        assert "auf eine andere\nUrsache zielt als ein Trend" in text

    def test_die_zaehlung_sagt_was_schon_vermessen_ist(self) -> None:
        """**Der pruefbare Teil von Punkt 3.** "Ein anderes Marktverhalten"
        laesst sich nicht nachsehen, "sma steht neunmal da" schon."""
        text = aus_messungen(**self.GEMESSEN).als_auftrag()

        assert "nach Einstiegsindikator" in text
        assert "sma 9" in text and "roc 2" in text

    def test_der_preis_steht_als_zahl_da(self) -> None:
        text = aus_messungen(**self.GEMESSEN).als_auftrag()

        assert "3.70 Reststreuungen" in text
        assert "n_eff 97" in text
        assert "raeumt die Schwelle bei **keiner**" in text

    def test_ohne_preis_wird_keiner_behauptet(self) -> None:
        ohne = aus_messungen(**{**self.GEMESSEN, "familienpreis": None})

        assert "Reststreuungen" not in ohne.als_auftrag()

    def test_die_kopplung_ist_die_nachgemessene(self) -> None:
        """**Die Zahl selbst war veraltet.** Befund 75 hat -0,533 auf rohen
        Trade-Zahlen gemessen, Befund 168 dieselbe Kopplung am Spot-Punkt und
        mit der Stichprobe des Gates: -0,714.
        """
        text = aus_messungen(**self.GEMESSEN).als_auftrag()

        assert "-0.714" in text
        assert "-0.533" not in text

    def test_der_echte_auftrag_behauptet_keine_kopplung_mehr(self, tmp_path) -> None:
        """**Befund 183, und es ist eine Ruecknahme.**

        Der Auftrag trug seit Befund 180 die Kopplung -0,714 und die Familie
        'sma'. Beide sind auf dem Katalog gemessen, den Befund 182 als nach
        der Groessenlogik gefiltert nachgewiesen hat. Auf dem berichtigten
        Vorrat hat keine Familie mehr die Mehrheit, und die Kopplung faellt
        auf t = -0,98, sobald ein einziger Punkt fehlt.

        Eine Korrelation, die ein Punkt loeschen kann, gehoert nicht in einen
        Auftrag - das ist der Fehler aus Befund 75.
        """
        import json

        from cli import _auftragslage

        (tmp_path / "trials.json").write_text(
            json.dumps({"format": 2, "trials": 198, "versuche": []})
        )
        echt = _auftragslage(tmp_path)

        assert echt.kopplung is None
        assert echt.kopplung_traegt is None
        assert echt.familien == ()
        assert echt.familienpreis is None
        text = echt.als_auftrag()
        assert "Warum das schwer ist" not in text
        assert "such woanders" not in text
        # Was traegt, steht weiter da: die Luecke selbst.
        assert "Was tatsaechlich fehlt" in text
        assert "Es fehlen" in text


class TestEinbau:
    def test_ohne_lage_bleibt_der_auftrag_wie_er_war(self) -> None:
        """Abwaertskompatibel - ein Aufrufer, der nichts uebergibt, bekommt
        den alten Text."""
        alt = build_prompt(journal=[], thresholds=GateThresholds())

        assert "Was tatsaechlich fehlt" not in alt

    def test_mit_lage_steht_die_anforderung_vor_dem_auftrag(self) -> None:
        """Reihenfolge zaehlt: Erst was fehlt, dann die Bitte um Vorschlaege."""
        neu = build_prompt(journal=[], thresholds=GateThresholds(), lage=lage())

        assert neu.index("Was tatsaechlich fehlt") < neu.index("## Auftrag")

    def test_die_erlaubten_indikatoren_bleiben_erhalten(self) -> None:
        """Der neue Abschnitt darf nichts verdraengen."""
        neu = build_prompt(journal=[], thresholds=GateThresholds(), lage=lage())

        assert "Erlaubte Indikatoren" in neu
        assert "Zulassungsschwellen" in neu


class TestOptimumImAuftrag:
    """Der Auftrag nannte die Untergrenze, wo das Optimum hingehoert."""

    def test_der_auftrag_nennt_das_optimum_nicht_nur_die_untergrenze(self) -> None:
        """**Die Korrektur aus Befund 82.**

        ``partner_trades`` ist die Wende aus der Partnerkarte - ab dort
        genuegt ein Partner mit der Qualitaet des Bestands. Das ist eine
        Untergrenze, und der Auftrag hat sie als Ziel genannt.

        Mein eigener Vorschlagszyklus in Befund 77 hat danach gezielt und
        Regeln zwischen 18 und 406 Trades gebaut - keine in der Naehe des
        Optimums.
        """
        aktuell = lage()

        assert aktuell.bestes_ziel > aktuell.partner_trades
        # Der Wert wandert mit jeder neuen Messung: 165 bei 18 Punkten,
        # 151 bei 22 (Befund 83). Der Test haelt den Bereich fest, nicht die
        # Zahl - sonst muesste er nach jedem Vorschlagszyklus nachgezogen
        # werden und sagte nichts mehr.
        assert 130 <= aktuell.bestes_ziel <= 210, f"gemessen {aktuell.bestes_ziel}"
        assert f"am besten rund **{aktuell.bestes_ziel}**" in aktuell.als_auftrag()

    def test_beide_zahlen_in_punkt_zwei_gehoeren_zusammen(self) -> None:
        """Punkt 1 nennt das Optimum, Punkt 2 nannte die Anforderung an der
        Wende - zwei Zahlen aus zwei Trade-Zahlen lesen sich wie ein
        Widerspruch."""
        aktuell = lage()

        assert aktuell.bedarf_am_ziel < aktuell.partner_sharpe
        assert f"ueber {aktuell.bedarf_am_ziel:.2f}** bei der Zahl aus Punkt 1" in (
            aktuell.als_auftrag()
        )

    def test_die_trefferquote_steht_als_bereich_da(self) -> None:
        """Eine einzelne Zahl waere genauer, als sie ist - ueber den
        Vertrauensbereich der Reststreuung schwankt sie um Faktor 48."""
        aktuell = lage()
        von, bis = aktuell.quoten_spanne

        assert 0 < von < bis
        assert bis / von > 10
        assert "Wie oft so ein Vorschlag trifft" in aktuell.als_auftrag()
        assert "Verdacht" in aktuell.als_auftrag()

    def test_die_zielspanne_ist_enger_als_die_quotenspanne(self) -> None:
        """Der Kern von Befund 81: Wohin zu zielen ist, steht fest - wie oft
        man trifft, nicht."""
        aktuell = lage()
        von, bis = aktuell.ziel_spanne
        q_von, q_bis = aktuell.quoten_spanne

        assert bis / von < 2.0, "Das Optimum wandert wenig"
        assert q_bis / q_von > 10, "Die Quote sehr viel"

    def test_ohne_messbares_optimum_bleibt_der_alte_text(self) -> None:
        """Faellt die Rechnung aus, nennt der Auftrag nur die Untergrenze -
        schlechter, aber nicht falsch."""
        ohne = Auftragslage(
            versuche=173, bestand_trades=154, bestand_sharpe=0.2591,
            noetige_guete=3.6, partner_trades=120, partner_sharpe=0.26,
        )

        assert "Wie oft so ein Vorschlag trifft" not in ohne.als_auftrag()


class TestWasAusDenPartnernWurde:
    """**Befund 196.** Der Auftrag war eine Einladung zur Wiederholung.

    Er nennt drei Kriterien, nach denen ein Partner brauchbar ist, und hat
    verschwiegen, dass **jeder** bisher gefundene Partner, der sie erfuellte,
    ausserhalb der Entwicklungsdaten durchgefallen ist: sieben von sieben,
    der beste 30 % gegen die 41 % des Bestands allein (Befund 186).

    Wer das nicht weiss, schlaegt denselben Kandidatentyp noch einmal vor -
    und jeder Vorschlag hebt die Huerde fuer alle folgenden.

    Dasselbe Muster wie Befund 180: Der Auftrag stand auf einem alten Stand.
    """

    def lage(self, holdout=(7, 0, 30.0, 41.0)):
        return aus_messungen(
            versuche=198, bestand_trades=115, bestand_sharpe=0.2708,
            holdout=holdout,
        )

    def test_der_abschnitt_nennt_die_gemessenen_zahlen(self) -> None:
        text = self.lage().als_auftrag()

        assert "Was aus den bisherigen Partnern geworden ist" in text
        assert "0 von 7" in text
        assert "30 % gegen dessen 41 %" in text

    def test_er_steht_vor_der_trefferquote(self) -> None:
        """Sonst liest man erst, wie oft es klappt, und dann, dass es nicht hat."""
        text = self.lage().als_auftrag()

        assert text.index("bisherigen Partnern") < text.index(
            "Wie oft so ein Vorschlag trifft"
        )

    def test_er_entwertet_die_drei_punkte_nicht(self) -> None:
        """Sie beschreiben, was rechnerisch reichen wuerde - das bleibt wahr."""
        text = self.lage().als_auftrag()

        assert "nicht, dass die drei Punkte falsch sind" in text
        assert "nicht genuegen" in text

    def test_er_verlangt_einen_unterschied_in_der_begruendung(self) -> None:
        text = self.lage().als_auftrag()

        assert "in seine Begruendung" in text

    def test_ohne_messung_wird_keine_entwarnung_erfunden(self) -> None:
        """``None`` heisst 'nicht gemessen', nicht 'nichts gefunden'."""
        text = self.lage(holdout=None).als_auftrag()

        assert "bisherigen Partnern geworden ist" not in text

    def test_der_auftrag_traegt_die_zahl_aus_dem_bericht(self) -> None:
        """Sie darf nicht im Auftragstext zweitgepflegt werden."""
        from pathlib import Path

        quelle = (Path(__file__).resolve().parents[1] / "cli.py").read_text()

        assert "holdout=(7, 0, 30.0, 41.0)" in quelle, (
            "der Auftrag bekommt das Holdout-Ergebnis nicht mehr uebergeben"
        )


class TestPunktZweiIstEineHerleitung:
    """**Befund 199.** Der Auftrag nannte eine Vorhersage, die nicht mehr traegt.

    Er sagte: *"Was gemessen zaehlt, ist Punkt 2: die eigene Qualitaet je
    Trade des Vorschlags (Rangkorrelation -0,53 gegen die Luecke)."* Diese
    Zahl stand auf vierzehn Paaren (Befund 140/141).

    Ueber alle achtzehn gemessenen sind es -0,41 bei t = -1,80 - unter der
    Schwelle von |t| = 2, die dieses Projekt seit Befund 75 verlangt. Die
    Richtung ist geblieben, die Deckung nicht.

    Befund 196 hatte die Neurechnung ausdruecklich aufgeschoben. Der Grund
    damals war, dass eine Zahl durch eine andere ohne Deckung zu ersetzen
    nichts bringt. Das stimmte fuer die **Ersetzung** - nicht dafuer, die
    Behauptung stehenzulassen.
    """

    def lage(self):
        return aus_messungen(
            versuche=198, bestand_trades=115, bestand_sharpe=0.2708,
        )

    def test_punkt_zwei_wird_nicht_mehr_als_vorhersage_verkauft(self) -> None:
        text = self.lage().als_auftrag()

        assert "Herleitung, keine Vorhersage" in text
        assert "Die Richtung ist geblieben, die Deckung nicht" in text

    def test_die_neue_zahl_steht_mit_ihrem_t_wert_da(self) -> None:
        """Ohne ihn liest sich -0,41 wie ein Beleg."""
        text = self.lage().als_auftrag()

        assert "-0,41" in text and "-1,80" in text
        assert "|t| = 2" in text

    def test_die_alte_zahl_wird_nicht_verschwiegen(self) -> None:
        """Sie war richtig, als sie gemessen wurde - das gehoert dazu."""
        text = self.lage().als_auftrag()

        assert "-0,53" in text
        assert "vierzehn Paare" in text

    def test_die_fensterkorrelation_wird_als_ungeprueft_markiert(self) -> None:
        """Sie stuetzt eine Verneinung - dafuer reichen vierzehn Paare."""
        text = self.lage().als_auftrag()

        assert "nicht wiederholt worden" in text
        assert "stuetzt eine Verneinung" in text

    def test_was_ein_partner_beitraegt_steht_aktuell_da(self) -> None:
        """Der alte Satz nannte 'den einen gemessenen Partner' - es sind 18."""
        text = self.lage().als_auftrag()

        assert "-14 bis" in text and "+236" in text
        assert "Zwei Paare stehen im Minus" in text
        assert "der eine gemessene Partner" not in text
