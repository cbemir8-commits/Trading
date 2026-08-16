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
        assert f"{aktuell.partner_trades * 2} Trades" in aktuell.als_auftrag()

    def test_die_unabhaengigkeit_wird_beziffert(self) -> None:
        """'Anders sein' ist kein pruefbares Kriterium - eine Korrelation
        schon."""
        text = lage().als_auftrag()

        assert f"{AEHNLICH:.1f}" in text
        assert "Trendfolge" in text

    def test_der_preis_eines_versuchs_steht_dabei(self) -> None:
        text = lage().als_auftrag()

        assert "Was ein Vorschlag kostet" in text
        assert "dauerhaft" in text

    def test_ohne_kopplung_faellt_der_abschnitt_weg(self) -> None:
        """Er ist ein Befund, keine Ausschmueckung."""
        ohne = aus_messungen(**{**STAND, "kopplung": None})

        assert "Warum das schwer ist" not in ohne.als_auftrag()


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
