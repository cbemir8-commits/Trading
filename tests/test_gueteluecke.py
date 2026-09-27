"""Die Luecke kommt vom Betriebspunkt, nicht aus der Hand - Befund 355.

In Befund 354 habe ich beziffert, was fuenf verlorene Versuche an der Latte des
Deflated-Sharpe-Gates aendern. Die Zahl war falsch, und zwar zu klein:

    veroeffentlicht   noetige Guete 0,4220   Luecke 0,1512   Wirkung 0,49 %
    richtig           noetige Guete 0,3389   Luecke 0,0681   Wirkung 0,92 %

Der Grund ist ein Aufruf von ``noetiger_sharpe`` **ohne die Momente**. Die
Vorgaben sind Schiefe 0 und Woelbung 3, der Bestand hat 3,4646 und 15,9173 -
eine andere Verteilung, also eine andere Kurve. Ein Lauf, der 156 Trades mit
wenigen sehr grossen Gewinnern macht, ist nicht normalverteilt, und das Gate
weiss das: ``deflated_sharpe_ratio`` nimmt beide Momente entgegen.

**Die Gegenprobe haette es sofort gezeigt.** Der Bestand hat einen
veroeffentlichten Deflated Sharpe von 0,5827:

    mit den gemessenen Momenten   0,5827   - auf die Stelle
    mit den Vorgaben              0,5473

Wer eine Zahl ueber den Bestand rechnet und dabei nicht auf dessen eigenen DSR
herauskommt, rechnet auf einer anderen Kurve. Dieser Test haelt genau das fest.

Was dagegen gebaut ist
----------------------
``Referenzpunkt.noetige_guete``, ``.gueteluecke`` und ``.gueteanteil`` rechnen
mit den Momenten **des Punkts**. Damit ist die Zahl nur noch auf einem Weg zu
bekommen, und auf dem richtigen. Dasselbe Muster wie ``noetiges_n`` seit Befund
158 - dessen Docstring nennt schon denselben Unfall, nur in der anderen
Richtung.

Die Warnung stand also da, in zwei Docstrings, und hat nicht gereicht. Ein Satz
in Prosa haelt niemanden auf; eine Eigenschaft, die die richtige Zahl liefert,
schon.
"""

from __future__ import annotations

import pytest

from research.erreichbarkeit import noetiger_sharpe
from research.gates import deflated_sharpe_ratio
from research.referenz import PERPETUALPUNKT, SPOTPUNKT, UEBERHOLT


class TestDieMomenteEntscheiden:
    """**Die Gegenprobe.** Nicht "die Momente sind wichtig", sondern: Mit den
    falschen kommt der eigene DSR des Punkts nicht heraus."""

    def test_mit_den_gemessenen_momenten_stimmt_der_eigene_dsr(self) -> None:
        wert = deflated_sharpe_ratio(
            observed_sharpe=SPOTPUNKT.guete,
            trials=SPOTPUNKT.versuche,
            sample_size=SPOTPUNKT.effektiv,
            skew=SPOTPUNKT.schiefe,
            kurtosis=SPOTPUNKT.woelbung,
        )

        assert float(wert) == pytest.approx(SPOTPUNKT.dsr, abs=0.0001)

    def test_mit_den_vorgaben_nicht(self) -> None:
        """Und der Abstand ist gross genug, um beim Hinsehen aufzufallen -
        0,035 DSR-Punkte, bei einer Luecke von 0,367 zur Schwelle."""
        vorgabe = float(
            deflated_sharpe_ratio(
                observed_sharpe=SPOTPUNKT.guete,
                trials=SPOTPUNKT.versuche,
                sample_size=SPOTPUNKT.effektiv,
            )
        )

        assert vorgabe != pytest.approx(SPOTPUNKT.dsr, abs=0.001)
        assert SPOTPUNKT.dsr - vorgabe == pytest.approx(0.035, abs=0.005)

    def test_und_bei_der_noetigen_guete_ist_der_fehler_gross(self) -> None:
        """**Die Zahl, an der Befund 354 gescheitert ist.** Ein Viertel gegen
        ein halbes Mal die Guete - das ist kein Rundungsfehler."""
        richtig = SPOTPUNKT.noetige_guete()
        von_hand = noetiger_sharpe(
            effektiv=SPOTPUNKT.effektiv, trials=SPOTPUNKT.versuche
        )

        assert richtig == pytest.approx(0.3374, abs=0.001)
        assert von_hand == pytest.approx(0.4202, abs=0.001)
        assert von_hand - richtig > 0.08


class TestDerPunktLiefertDieLuecke:
    def test_die_luecke_in_punkten(self) -> None:
        assert SPOTPUNKT.gueteluecke() == pytest.approx(0.0666, abs=0.001)

    def test_und_als_anteil(self) -> None:
        """Die Form, in der das Projekt sie seit Befund 70 nennt - damals
        +13 %, in 222 +24,3 %, heute rund +25 %."""
        anteil = SPOTPUNKT.gueteanteil()

        assert anteil == pytest.approx(0.246, abs=0.01)

    def test_mehr_versuche_heben_die_latte(self) -> None:
        assert SPOTPUNKT.noetige_guete(versuche=215) > SPOTPUNKT.noetige_guete(
            versuche=203
        )

    def test_das_fenster_aus_befund_269_kommt_hier_heraus(self) -> None:
        """**Die staerkere Gegenprobe.** Befund 269 sagt: +25,9 % Guete je
        Trade loesen das Gate, und *"das Fenster schliesst sich bei 231
        Versuchen"*. Beides zusammen heisst: Bei 231 Versuchen verlangt die
        Schwelle genau das, was +25,9 % liefern - danach reicht es nicht mehr.
        Aus dem Betriebspunkt gerechnet kommt das heraus.

        Der erste Anlauf dieses Tests hat 0,3387 bei 231 Versuchen erwartet und
        damit zwei Zahlen des Eintrags verwechselt - 0,3387 ist die Latte bei
        rund 213 Versuchen. Der Test hat es gemeldet, und das ist der Punkt
        dieser Datei.
        """
        erreicht = SPOTPUNKT.guete * 1.259

        assert erreicht == pytest.approx(0.3409, abs=0.001)
        assert SPOTPUNKT.noetige_guete(versuche=231) == pytest.approx(
            erreicht, abs=0.0015
        )
        assert SPOTPUNKT.noetige_guete(versuche=213) == pytest.approx(
            0.3387, abs=0.0015
        )


class TestOhneMomenteWirdNichtGeraten:
    def test_ein_ueberholter_stand_sagt_nichts(self) -> None:
        """``None`` und nicht "ungefaehr": Die alten Staende haben ihre
        Verteilungsform nie festgehalten."""
        ohne = [p for p in UEBERHOLT if p.schiefe is None]

        assert ohne, "es gibt ueberholte Staende ohne Momente - sonst pruefe hier"
        for punkt in ohne:
            assert punkt.noetige_guete() is None, punkt.name
            assert punkt.gueteluecke() is None, punkt.name
            assert punkt.gueteanteil() is None, punkt.name

    def test_der_perpetualpunkt_kann_es_auch(self) -> None:
        """Der zweite gefuehrte Betriebspunkt - damit die Eigenschaft nicht an
        einem einzigen Fall haengt."""
        if PERPETUALPUNKT.schiefe is None:
            pytest.skip("Der Perpetual-Punkt fuehrt keine Momente")

        assert PERPETUALPUNKT.noetige_guete() is not None
        assert PERPETUALPUNKT.gueteluecke() > 0


class TestDasRegisterTraegtDieBerichtigung:
    def test_der_eintrag_zu_354_nennt_die_richtige_zahl(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 354)

        assert "0,92" in eintrag.ergebnis
        assert "berichtigt in 355" in eintrag.ergebnis

    def test_und_der_eigene_eintrag_steht_da(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 355)

        assert "Momente" in eintrag.ergebnis
        assert "0,5827" in eintrag.ergebnis, "die Gegenprobe fehlt"
