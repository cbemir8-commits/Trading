"""Die Klemme im haertesten Gate ist tragend, nicht faul - Befund 375.

Diese Datei haelt einen **Irrweg von mir** fest, damit ihn der naechste
Durchgang nicht wiederholt.

Was wie ein Loch aussah
-----------------------
Beim Rechnen fuer Befund 374 variierte eine Tabelle die Schiefe des Gewinners,
und die Spalte mit dem heutigen Gate zeigte:

    Schiefe 4,5000   DSR 0,6972   durchgefallen
    Schiefe 4,7000   DSR 1,0000   BESTANDEN
    Schiefe 8,0000   DSR 1,0000   BESTANDEN
    Schiefe 20,000   DSR 1,0000   BESTANDEN

Kein Uebergang, ein Sprung, danach besteht alles. Dahinter steht

    denominator = math.sqrt(max(1 - skew*SR + (kurtosis-1)/4 * SR**2, 1e-9))

Die Klammer ist die Streuung des Sharpe-Schaetzers nach Mertens und Lo, also
eine Varianz. Wird sie negativ, klemmt ``max`` sie auf 1e-9, der Nenner wird
3e-5, die Teststatistik explodiert - und das Gate, das Mehrfachtesten und
Glueck bestrafen soll, gibt die Bestnote.

Ich habe daraus ein nicht-bestanden gemacht ("was nicht beurteilt werden kann,
besteht nicht", die Richtung aus Befund 321/322). Die Suite hat es abgelehnt,
mit drei Tests, und sie hatte recht.

Warum die Klemme tragend ist
----------------------------
``suchbudget.Budget.hebel`` zerlegt das Gate in vier Groessen und fragt fuer
jede: *Wo muesste sie stehen, damit es haelt - alles andere unveraendert?* Bei
der Schiefe fuehrt diese Frage **absichtlich** in den unmoeglichen Bereich,
denn Woelbung und Schiefe sind gekoppelt (``formgrenze``, Befund 70/225). Der
Punkt wird dort gefunden und die Unmoeglichkeit danach getrennt benannt:

    mit Klemme     'Schiefe  3.466 -> 4.486   braucht Woelbung >= 21.1, hier 16.0'
    ohne Klemme    'Schiefe  3.466   unerreichbar'

Der Test, der fiel, heisst ``test_die_schiefe_meldet_ihren_grund_statt_einer_
zahl``. Genau diesen Grund hatte meine Aenderung entfernt. Eine Wache, die nur
auf Unmoegliches anspringt, ist hier keine Landmine, sondern das Mittel, mit
dem eine Zerlegung einen fiktiven Punkt findet und als fiktiv ausweist.

Dass der Bereich im Gate selbst nie erreicht wird, ist gemessen (unten) - und
die Mathematik dazu steht seit Befund 70 in ``formgrenze``: ``Woelbung >=
Schiefe^2 + 1`` aus Cauchy-Schwarz.

Was bei der Suche **neu** herauskam
-----------------------------------
Eine Sache, die das Projekt noch nicht hatte: ``evaluate_gates`` normiert
uneinheitlich. ``spread`` nimmt ``ddof=1``, die Momente nehmen ``np.mean``,
also ist das zweite Moment ``(n-1)/n`` und nicht 1. Damit koennen die
**berechneten** Momente die Schranke verfehlen, auf die ``formgrenze.moeglich``
sie prueft - und ``Formlinie.ueber_der_schranke`` sagt in seinem Docstring, was
das heissen wuerde:

    Muessen sie - sonst ist eine der beiden Zahlen falsch gerechnet, und das
    waere ein Fund ueber den Messcode und nicht ueber den Markt.

Gemessen ueber die erschoepfende Zweipunkt-Familie: mit ``ddof=0`` keine
einzige Verletzung, mit der Normierung des Gates bis **0,0656**. Am
verzeichneten Punkt ist der Abstand zur Schranke **+2,9138** - der Fehlalarm
ist also so unerreichbar wie die Klemme. Einheitlich normiert wuerde der DSR
des Spot-Punkts von 0,5827 auf 0,5836 steigen (+0,0009): eine Verschiebung in
die **milde** Richtung an einer verzeichneten Zahl, fuer einen Gewinn in einer
Ecke, die kein Kandidat erreicht. Deshalb bleibt sie stehen und steht hier.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from research.formgrenze import mindestwoelbung, moeglich
from research.gates import deflated_sharpe_ratio
from research.referenz import SPOTPUNKT

#: Kleinste Klammer ueber 36.000 Stichproben gemischter Familien (Zweipunkt,
#: t mit 2,1 bis 6 Freiheitsgraden, lognormal).
GEMESSENER_BODEN = 0.0427

#: Kleinste Klammer ueber die erschoepfende Zweipunkt-Familie allein. Hoeher
#: als der Boden oben, weil dort auch schwere Raender dabei sind.
ZWEIPUNKT_BODEN = 0.3276

#: Hoechste Schiefe in 'reports/' und der Bestenliste.
HOECHSTE_GEMESSENE_SCHIEFE = 3.4815


def _wie_im_gate(pnls) -> tuple[float, float, float]:
    """Sharpe, Schiefe und Woelbung genau so wie ``evaluate_gates`` sie bildet.

    Wichtig, dass es **genau so** gerechnet wird: ``spread`` mit ``ddof=1``,
    die Momente mit ``np.mean``. Wer hier einheitlich normiert, prueft eine
    andere Formel als die, die urteilt.
    """
    pnls = np.asarray(pnls, dtype=float)
    spread = float(np.std(pnls, ddof=1))
    mitte = (pnls - np.mean(pnls)) / spread
    return (
        float(np.mean(pnls)) / spread,
        float(np.mean(mitte**3)),
        float(np.mean(mitte**4)),
    )


def _klammer(sharpe: float, schiefe: float, woelbung: float) -> float:
    return 1 - schiefe * sharpe + (woelbung - 1) / 4 * sharpe**2


class TestDieKlemmeBleibtUndWarum:
    """**Der Kern.** Sie wegzunehmen nimmt einer Zerlegung ihre Begruendung."""

    def test_sie_steht_noch_im_quelltext(self) -> None:
        quelle = inspect.getsource(deflated_sharpe_ratio)
        assert "max(1 - skew * observed_sharpe" in quelle
        assert "1e-9" in quelle

    def test_der_unmoegliche_bereich_gibt_weiter_eine_zahl(self) -> None:
        """Nicht weil 1,0 richtig waere, sondern weil die Zerlegung die Stelle
        finden muss, um sie als unmoeglich auszuweisen."""
        wert = deflated_sharpe_ratio(
            observed_sharpe=SPOTPUNKT.guete,
            trials=SPOTPUNKT.versuche,
            sample_size=SPOTPUNKT.effektiv,
            skew=5.0,
            kurtosis=SPOTPUNKT.woelbung,
        )
        assert _klammer(SPOTPUNKT.guete, 5.0, SPOTPUNKT.woelbung) < 0
        assert wert == 1.0
        assert not moeglich(5.0, SPOTPUNKT.woelbung)

    def test_der_hebel_nennt_seinen_grund_und_nicht_nur_ein_wort(self) -> None:
        """Der Test, der meine Aenderung abgelehnt hat - hier als Zusicherung.

        Mit Klemme steht da, **wohin** der Weg fuehren muesste und **warum**
        es ihn nicht gibt. Ohne sie bleibt 'unerreichbar' uebrig, und wer das
        liest, weiss nicht, ob es eng oder absurd ist.
        """
        from research.suchbudget import WOELBUNG, Budget
        from tests.test_suchbudget import TestHebel

        hebel = next(
            h
            for h in Budget(versuche=151).hebel(TestHebel()._kandidat())
            if h.name == "Schiefe"
        )

        assert hebel.noetig is not None
        assert hebel.noetig > HOECHSTE_GEMESSENE_SCHIEFE
        assert mindestwoelbung(hebel.noetig) > WOELBUNG
        assert not hebel.moeglich
        assert "braucht Woelbung" in str(hebel)


class TestDerBereichIstUnerreichbar:
    """Warum es ohne die Klemme auch keinen Schaden gaebe - und mit ihr keinen."""

    def test_der_verzeichnete_punkt_liegt_weit_ueber_der_schranke(self) -> None:
        abstand = SPOTPUNKT.woelbung - mindestwoelbung(SPOTPUNKT.schiefe)
        assert abstand == pytest.approx(2.9138, abs=1e-3)
        assert moeglich(SPOTPUNKT.schiefe, SPOTPUNKT.woelbung)

    def test_fester_stop_und_festes_ziel_erreichen_sie_nie(self) -> None:
        """Die Zweipunkt-Verteilung ist der Gleichheitsfall der Schranke - und
        die haeufigste Bauart. Wenn **sie** nicht hinkommt, kommt nichts hin.
        """
        boden = float("inf")
        for n in (30, 50, 115, 200, 500):
            for gewinner in range(1, n):
                for ziel in (1.0, 2.0, 5.0, 15.0, 50.0, 200.0):
                    sharpe, schiefe, woelbung = _wie_im_gate(
                        [ziel] * gewinner + [-1.0] * (n - gewinner)
                    )
                    if sharpe <= 0:
                        continue
                    boden = min(boden, _klammer(sharpe, schiefe, woelbung))
        assert boden > 0
        assert boden == pytest.approx(ZWEIPUNKT_BODEN, abs=5e-3)

    def test_auch_schwere_raender_kommen_nicht_hin(self) -> None:
        """t-Verteilung mit 2,1 Freiheitsgraden und Lognormal - was an echten
        Handelsergebnissen schief und spitz ist."""
        rng = np.random.default_rng(375)
        boden = float("inf")
        for _ in range(4000):
            n = int(rng.integers(30, 160))
            if rng.integers(0, 2):
                pnls = rng.standard_t(df=rng.uniform(2.1, 6), size=n) + rng.uniform(0, 1)
            else:
                pnls = rng.lognormal(0, rng.uniform(0.5, 2.5), size=n) - rng.uniform(0.5, 2)
            sharpe, schiefe, woelbung = _wie_im_gate(pnls)
            if sharpe <= 0 or not np.isfinite([sharpe, schiefe, woelbung]).all():
                continue
            boden = min(boden, _klammer(sharpe, schiefe, woelbung))
        assert boden > 0
        assert boden >= GEMESSENER_BODEN

    def test_der_kipppunkt_liegt_ueber_jeder_gemessenen_schiefe(self) -> None:
        """Der Kipppunkt ist ``1/SR + (Woelbung-1)/4*SR`` und wird minimal bei
        ``sqrt(Woelbung-1)``. Bei der gemessenen Woelbung sind das 3,862."""
        untergrenze = float(np.sqrt(SPOTPUNKT.woelbung - 1))
        assert untergrenze == pytest.approx(3.862, abs=1e-3)
        assert untergrenze > HOECHSTE_GEMESSENE_SCHIEFE


class TestDieNormierungIstUneinheitlich:
    """Der einzige **neue** Fund dieser Runde - und seine ehrliche Groesse."""

    def test_sauber_normiert_haelt_die_schranke_ausnahmslos(self) -> None:
        rng = np.random.default_rng(3751)
        for _ in range(2000):
            n = int(rng.integers(30, 160))
            gewinner = int(rng.integers(1, n))
            pnls = np.array([rng.uniform(1, 20)] * gewinner + [-1.0] * (n - gewinner))
            mitte = (pnls - pnls.mean()) / float(np.std(pnls, ddof=0))
            schiefe = float(np.mean(mitte**3))
            woelbung = float(np.mean(mitte**4))
            assert woelbung >= mindestwoelbung(schiefe) - 1e-9

    def test_mit_der_normierung_des_gates_kann_sie_verfehlt_werden(self) -> None:
        """``spread`` mit ``ddof=1``, die Momente mit ``np.mean`` - damit ist
        das zweite Moment ``(n-1)/n``. ``Formlinie.ueber_der_schranke`` nennt
        so etwas 'einen Fund ueber den Messcode und nicht ueber den Markt'.
        """
        schlimmste = 0.0
        for n in (30, 50, 115, 200, 500):
            for gewinner in range(1, n):
                for ziel in (1.0, 2.0, 5.0, 15.0, 50.0, 200.0):
                    _, schiefe, woelbung = _wie_im_gate(
                        [ziel] * gewinner + [-1.0] * (n - gewinner)
                    )
                    schlimmste = max(schlimmste, mindestwoelbung(schiefe) - woelbung)
        assert schlimmste > 0.0
        assert schlimmste == pytest.approx(0.0656, abs=5e-3)

    def test_einheitlich_normiert_stiege_der_dsr_um_neun_zehntausendstel(self) -> None:
        """Die Verschiebung, die eine Behebung kostete - gemessen, nicht
        geschaetzt, und zwar an der verzeichneten Zahl.

        0,5827 auf 0,5836, also in die **milde** Richtung. Fuer einen Gewinn
        in einer Ecke, die kein Kandidat erreicht, eine verzeichnete Zahl zu
        verschieben, ist der schlechtere Tausch; die Entscheidung gehoert
        ausserdem nicht in eine Nebenwirkung.
        """
        n = SPOTPUNKT.effektiv
        faktor = (n - 1) / n
        heute = deflated_sharpe_ratio(
            observed_sharpe=SPOTPUNKT.guete,
            trials=SPOTPUNKT.versuche,
            sample_size=n,
            skew=SPOTPUNKT.schiefe,
            kurtosis=SPOTPUNKT.woelbung,
        )
        einheitlich = deflated_sharpe_ratio(
            observed_sharpe=SPOTPUNKT.guete,
            trials=SPOTPUNKT.versuche,
            sample_size=n,
            skew=SPOTPUNKT.schiefe * faktor**-1.5,
            kurtosis=SPOTPUNKT.woelbung * faktor**-2,
        )
        assert heute == pytest.approx(SPOTPUNKT.dsr, abs=5e-5)
        assert einheitlich - heute == pytest.approx(0.0009, abs=1e-4)
        assert einheitlich < 0.95  # am Urteil aendert sich nichts
