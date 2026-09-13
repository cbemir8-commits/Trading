"""Ziehen die offenen Gates gegeneinander - und wie lange traegt das Budget?

**Befund 269.** Der Bestand haelt 9 von 11. Die beiden offenen Gates fordern
Verschiedenes von denselben Trades: die Betriebsschwelle eine **Summe**, der
Deflated Sharpe ein **Verhaeltnis**. Seit Befund 104 steht die Sorge im Raum,
dass eines das andere ausschliesst.

Was hier gehalten wird
----------------------
Die beiden Wege duerfen nicht verwechselt werden. **Skalieren** hebt Zaehler
und Nenner gleich - der Sharpe je Trade ruehrt sich nicht, der Rueckgang
waechst. **Verbessern** laesst den Nenner stehen. Nur der zweite loest beide
Gates, und ein Werkzeug, das das vermischt, wuerde einen Weg melden, den es
nicht gibt.

Und die Budgetgrenze: Jeder Versuch hebt die Latte dauerhaft. Ab einer
bestimmten Versuchszahl traegt auch der richtige Kandidat nicht mehr - diese
Zahl ist die eigentliche Grenze der Suche und liegt unter dem Plan.
"""

from __future__ import annotations

import pytest

from research.zielfenster import (
    Handelsbuch,
    noetige_summe,
    skalieren,
    verbessern,
    vermesse,
)

#: Der Bestand am Spot-Punkt, gemessen in Befund 269.
BESTAND = Handelsbuch(
    trades_gesamt=158,
    effektiv=115,
    mittel=4.9124,
    streuung=18.1418,
    summe=818.01,
    rueckgang_pct=9.8687,
    jahre=8.0,
)
#: Schiefe und Woelbung **der gehandelten Trades** - nicht aller. Hier
#: standen zuerst die Werte ueber alle 158, uebernommen aus einem
#: frueheren Anlauf; die Budgetgrenze fiel damit auf 214 statt 231. Ein
#: Unterschied von 0,09 in der Schiefe verschiebt sie um siebzehn
#: Versuche - die Zahl ist empfindlich, und das gehoert dazu.
MOMENTE = {"schiefe": 3.464568, "woelbung": 15.917262}
GATES = {"schwelle_pct": 15.0, "dsr_ziel": 0.95, "drawdown_grenze": 12.0}


class TestDieSchwelleIstEineSumme:
    def test_die_noetige_summe_verzinst_sich(self) -> None:
        """15 % ueber 8 Jahre sind nicht 120 % - sie verzinsen sich. Genau
        dieser Fehler stand einmal im Messlatten-Gate (siehe 'scaled_hold')."""
        acht = noetige_summe(8.0, 15.0, kapital=500.0)

        assert acht == pytest.approx(500.0 * (1.15**8 - 1))
        assert acht > 500.0 * 1.20 * 8 * 0  # nicht linear

    def test_ohne_zeitraum_gibt_es_keine_schwelle(self) -> None:
        assert noetige_summe(0.0, 15.0) == 0.0


class TestSkalierenLoestNichts:
    """Groessere Positionen bei gleicher Regel."""

    def test_der_sharpe_je_trade_bleibt(self) -> None:
        """Zaehler und Nenner wachsen gleich - das ist der ganze Punkt."""
        weg = skalieren(BESTAND, versuche=198, **GATES, **MOMENTE)

        assert weg.sharpe_danach == pytest.approx(BESTAND.sharpe_je_trade)

    def test_und_damit_bleibt_der_deflated_sharpe_gerissen(self) -> None:
        weg = skalieren(BESTAND, versuche=198, **GATES, **MOMENTE)

        assert not weg.haelt_dsr

    def test_der_rueckgang_waechst_mit(self) -> None:
        """9,87 % mal 1,2586 sind 12,42 % - ueber der Grenze von 12,0."""
        weg = skalieren(BESTAND, versuche=198, **GATES, **MOMENTE)

        assert weg.rueckgang_danach == pytest.approx(
            BESTAND.rueckgang_pct * weg.faktor
        )
        assert not weg.haelt_rueckgang

    def test_der_weg_traegt_also_nicht(self) -> None:
        assert not skalieren(BESTAND, versuche=198, **GATES, **MOMENTE).traegt


class TestVerbessernLoestBeide:
    """Mehr Ertrag je Trade bei gleicher Streuung."""

    def test_der_sharpe_steigt_mit_dem_ertrag(self) -> None:
        weg = verbessern(BESTAND, versuche=198, **GATES, **MOMENTE)

        assert weg.sharpe_danach == pytest.approx(
            BESTAND.mittel * weg.faktor / BESTAND.streuung
        )
        assert weg.sharpe_danach > BESTAND.sharpe_je_trade

    def test_der_rueckgang_bleibt_stehen(self) -> None:
        """Er haengt an der Streuung, und die ruehrt sich hier nicht."""
        weg = verbessern(BESTAND, versuche=198, **GATES, **MOMENTE)

        assert weg.rueckgang_danach == pytest.approx(BESTAND.rueckgang_pct)
        assert weg.haelt_rueckgang

    def test_beide_gates_halten(self) -> None:
        weg = verbessern(BESTAND, versuche=198, **GATES, **MOMENTE)

        assert weg.haelt_dsr
        assert weg.traegt

    def test_beide_wege_brauchen_denselben_ertrag(self) -> None:
        """Der Faktor kommt aus der Schwelle und haengt nicht am Weg - was
        sich unterscheidet, ist der Preis an den anderen Gates."""
        a = skalieren(BESTAND, versuche=198, **GATES, **MOMENTE)
        b = verbessern(BESTAND, versuche=198, **GATES, **MOMENTE)

        assert a.faktor == pytest.approx(b.faktor)


class TestDasFensterUndSeinUrteil:
    def _fenster(self, versuche: int = 198):
        return vermesse(BESTAND, versuche=versuche, **GATES, **MOMENTE)

    def test_nur_ein_weg_traegt(self) -> None:
        f = self._fenster()

        assert [w.name for w in f.tragende] == ["verbessern"]
        assert not f.leer

    def test_das_urteil_nennt_den_noetigen_ertrag(self) -> None:
        urteil = self._fenster().urteil()

        assert "verbessern" in urteil
        assert "%" in urteil
        assert "ziehen nicht" in urteil

    def test_ein_leeres_fenster_sagt_es(self) -> None:
        """Ein Buch, dessen Streuung so gross ist, dass auch der noetige
        Ertrag den Deflated Sharpe nicht ueber die Huerde bringt."""
        wild = Handelsbuch(
            trades_gesamt=158, effektiv=115, mittel=4.9124,
            streuung=180.0, summe=818.01, rueckgang_pct=9.8687, jahre=8.0,
        )

        f = vermesse(wild, versuche=198, **GATES, **MOMENTE)

        assert f.leer
        assert "Fenster zu" in f.urteil()


class TestDieBudgetgrenze:
    """Die Zahl, die die Suche begrenzt - schaerfer als der Plan."""

    def test_sie_liegt_unter_dem_plan(self) -> None:
        """Der Plan sieht 230 Versuche vor, das Fenster schliesst bei 231.
        Der Puffer ist also **null** - was hier gehalten wird, ist nicht die
        genaue Zahl (sie haengt empfindlich an den Momenten), sondern dass
        Grenze und Plan in derselben Gegend liegen."""
        f = vermesse(BESTAND, versuche=198, **GATES, **MOMENTE)

        grenze = f.budgetgrenze(**MOMENTE)

        assert grenze is not None
        assert not grenze.gedeckelt
        assert 198 < grenze.versuche < 300

    def test_an_der_grenze_kippt_es(self) -> None:
        """Die eigentliche Zusage: Eins darunter traegt, an der Grenze
        nicht mehr."""
        f = vermesse(BESTAND, versuche=198, **GATES, **MOMENTE)
        grenze = f.budgetgrenze(**MOMENTE).versuche

        assert verbessern(BESTAND, versuche=grenze - 1, **GATES, **MOMENTE).traegt
        assert not verbessern(BESTAND, versuche=grenze, **GATES, **MOMENTE).traegt

    def test_ohne_tragenden_weg_gibt_es_keine_grenze(self) -> None:
        wild = Handelsbuch(
            trades_gesamt=158, effektiv=115, mittel=4.9124,
            streuung=180.0, summe=818.01, rueckgang_pct=9.8687, jahre=8.0,
        )

        f = vermesse(wild, versuche=198, **GATES, **MOMENTE)

        assert f.budgetgrenze(**MOMENTE) is None

    def test_eine_groessere_stichprobe_schiebt_sie_hinaus(self) -> None:
        """**Der konstruktive Teil.** Die Latte haengt an der effektiven
        Stichprobe. Mehr Trades bei gleichem Ertrag je Trade geben Luft -
        nicht mehr Suche."""
        # **Nur die effektive Stichprobe**, alles andere gleich. Ein Buch
        # mit doppelter Summe waere eine andere Strategie und wuerde die
        # Aussage vermischen - so stand es hier zuerst, und dann brauchte es
        # gar keine Verbesserung mehr.
        breiter = Handelsbuch(
            trades_gesamt=BESTAND.trades_gesamt, effektiv=230,
            mittel=BESTAND.mittel, streuung=BESTAND.streuung,
            summe=BESTAND.summe, rueckgang_pct=BESTAND.rueckgang_pct,
            jahre=BESTAND.jahre,
        )

        eng = vermesse(BESTAND, versuche=198, **GATES, **MOMENTE)
        weit = vermesse(breiter, versuche=198, **GATES, **MOMENTE)

        assert weit.budgetgrenze(**MOMENTE).versuche > (
            eng.budgetgrenze(**MOMENTE).versuche
        )

    def test_ein_gedeckeltes_ergebnis_sagt_es(self) -> None:
        """**Die Mehrdeutigkeit, die es hier nicht geben darf.** 'Grenze
        jenseits des Suchbereichs' ist der guenstigste Fall, 'kein Weg traegt'
        der schlechteste. Beide auf None abzubilden waere genau die Sorte
        Verwechslung, die dieses Projekt sonst aufspuert."""
        eng = vermesse(BESTAND, versuche=198, **GATES, **MOMENTE)

        gedeckelt = eng.budgetgrenze(hoechstens=200, **MOMENTE)

        assert gedeckelt is not None
        assert gedeckelt.gedeckelt
        assert "hinaus" in str(gedeckelt)

    def test_die_budgetkosten_steigen_monoton(self) -> None:
        f = vermesse(BESTAND, versuche=198, **GATES, **MOMENTE)

        jetzt, spaeter = f.budgetkosten(bis=230, **MOMENTE)

        assert spaeter > jetzt
