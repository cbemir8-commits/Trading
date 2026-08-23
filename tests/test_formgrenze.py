"""Der letzte offene Weg zum Gate - und warum es ihn nicht gibt.

Drei Tests tragen diese Datei:

``test_die_schranke_haelt_fuer_echte_verteilungen`` - Die Ungleichung wird
nicht behauptet, sondern an gezogenen Stichproben nachgerechnet. Waere sie
falsch, waere der ganze Befund falsch.

``test_der_ausgewiesene_zielpunkt_ist_keine_verteilung`` - Genau der Punkt,
den ``cli stand`` seit Wochen als Weg ausweist. Er reisst die Schranke.

``test_die_kurve_ist_nicht_monoton`` - Beim Bauen dieses Moduls hat eine
Bisektion "unerreichbar" gemeldet, wo ein Fenster lag. Der Test haelt fest,
warum abgetastet und nicht bisiziert wird.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.formgrenze import (
    Formlinie,
    Formpunkt,
    Formweg,
    mindestwoelbung,
    moeglich,
    tabelle,
    ueberschuss,
    wege,
)

#: Der Spitzenkandidat, wie ihn ``cli stand`` ausweist.
SPITZE = {"sharpe": 0.2569, "stichprobe": 154, "versuche": 166}
HEUTE_SCHIEFE, HEUTE_WOELBUNG = 3.473, 15.951

#: Die acht Kandidaten dieses Projekts, die beide Formzahlen mittragen -
#: aus fuenf Regelfamilien, von der Rueckkehr zum Mittel bis zum Ausbruch.
GEMESSEN = [
    ("Rueckkehr vom unteren Band", 0.601, 2.888),
    ("Rueckschlag im Aufwaertstrend", 1.753, 4.468),
    ("Neues Hoch im Takt", 2.289, 7.732),
    ("Ausbruch mit Beteiligung", 2.927, 12.057),
    ("Donchian-Ausbruch 50/25", 3.209, 13.982),
    ("Vola-Ziel 20.5", 3.398, 15.482),
    ("Vola-Ziel 21.0", 3.433, 15.870),
    ("Vola-Ziel 21.5", 3.482, 16.249),
]


def linie() -> Formlinie:
    return Formlinie(
        punkte=[
            Formpunkt(quelle="gemessen", kennung=n, schiefe=s, woelbung=w)
            for n, s, w in GEMESSEN
        ]
    )


def form(werte: np.ndarray) -> tuple[float, float]:
    """Schiefe und Woelbung - genau wie ``gates.gate_deflated_sharpe``."""
    zentriert = (werte - werte.mean()) / werte.std(ddof=1)
    return float(np.mean(zentriert**3)), float(np.mean(zentriert**4))


class TestSchranke:
    def test_die_schranke_haelt_fuer_echte_verteilungen(self) -> None:
        """**Der Test, der den ganzen Befund traegt.**

        ``Woelbung >= Schiefe^2 + 1`` folgt aus Cauchy-Schwarz. Hier wird sie
        nicht zitiert, sondern an gezogenen Stichproben nachgerechnet - ueber
        Verteilungen mit sehr verschiedener Form, einschliesslich der
        schiefen, um die es geht.
        """
        zufall = np.random.default_rng(7)
        proben = {
            "normal": zufall.normal(size=20_000),
            "lognormal": zufall.lognormal(sigma=1.0, size=20_000),
            "exponential": zufall.exponential(size=20_000),
            "pareto": zufall.pareto(3.0, size=20_000),
            "gleich": zufall.uniform(size=20_000),
            "trades": np.where(
                zufall.random(20_000) < 0.22, zufall.exponential(6.0, 20_000), -1.0
            ),
        }
        for name, werte in proben.items():
            schiefe, woelbung = form(werte)
            assert woelbung >= mindestwoelbung(schiefe) - 1e-6, (
                f"{name}: Woelbung {woelbung:.3f} unter der Schranke "
                f"{mindestwoelbung(schiefe):.3f}"
            )

    def test_eine_zweipunktverteilung_erreicht_die_schranke(self) -> None:
        """Gleichheit gibt es - und nur dort. Das ist der Grund, warum die
        Schranke als Optimum taugt und nicht als Erwartung."""
        werte = np.array([1.0] * 100 + [-9.0] * 10)
        schiefe, woelbung = form(werte)

        assert woelbung == pytest.approx(mindestwoelbung(schiefe), rel=0.05)

    def test_alle_gemessenen_punkte_liegen_darueber(self) -> None:
        """Muessen sie - sonst waere eine der beiden Zahlen falsch gerechnet,
        und das waere ein Fund ueber den Messcode statt ueber den Markt."""
        assert linie().ueber_der_schranke()

    def test_der_ueberschuss_ist_der_abstand(self) -> None:
        assert ueberschuss(3.0, 12.0) == pytest.approx(2.0)
        assert not moeglich(3.0, 9.0)


class TestZielpunkt:
    def test_der_ausgewiesene_zielpunkt_ist_keine_verteilung(self) -> None:
        """**Der zweite tragende Test.**

        ``cli stand`` weist seit Wochen aus: Schiefe von 3,473 auf 4,530,
        *alles andere unveraendert*. Bei Schiefe 4,53 liegt die kleinste
        moegliche Woelbung ueber 20 - festgehalten wurden 15,95. Diese Form
        gibt es nicht.
        """
        ziel = 4.530

        assert mindestwoelbung(ziel) > HEUTE_WOELBUNG
        assert not moeglich(ziel, HEUTE_WOELBUNG)

    def test_der_heutige_punkt_ist_moeglich(self) -> None:
        """Sonst prueft der Test darueber etwas anderes als gedacht."""
        assert moeglich(HEUTE_SCHIEFE, HEUTE_WOELBUNG)


class TestLinie:
    def test_die_gemessenen_punkte_liegen_eng(self) -> None:
        guete = linie().guete

        assert guete is not None and guete > 0.99

    def test_die_linie_liegt_ueber_der_schranke(self) -> None:
        """Reale Verteilungen halten Abstand - und der Abstand waechst."""
        gerade = linie()
        for schiefe in (2.0, 4.0, 6.0):
            erwartet = gerade.woelbung_bei(schiefe)
            assert erwartet is not None
            assert erwartet > mindestwoelbung(schiefe)

    def test_die_linie_faellt_nie_unter_die_schranke(self) -> None:
        """Eine angepasste Gerade kann rechnerisch darunter geraten, eine
        Verteilung nicht. Dann gilt die Schranke."""
        flach = Formlinie(
            punkte=[
                Formpunkt(quelle="x", kennung="a", schiefe=0.1, woelbung=1.02),
                Formpunkt(quelle="x", kennung="b", schiefe=0.2, woelbung=1.05),
                Formpunkt(quelle="x", kennung="c", schiefe=0.3, woelbung=1.10),
            ]
        )
        wert = flach.woelbung_bei(9.0)

        assert wert is not None and wert >= mindestwoelbung(9.0)

    def test_zu_wenige_punkte_liefern_keine_linie(self) -> None:
        knapp = Formlinie(punkte=linie().punkte[:2])

        assert not knapp.genug
        assert knapp.steigung is None
        assert knapp.woelbung_bei(4.0) is None


class TestWeg:
    def weg(self, kopplung, **rest) -> Formweg:
        return Formweg(**SPITZE, kopplung=kopplung, **rest)

    def test_die_kurve_ist_nicht_monoton(self) -> None:
        """**Der dritte tragende Test.**

        Der Nenner der Formel ist entlang der Schranke
        ``(1 - Schiefe*SR/2)^2 + Ueberschuss*SR^2/4`` und hat sein Minimum bei
        ``Schiefe = 2/SR``. Darueber wird das Gate wieder schwerer.

        Beim Bauen dieses Moduls hat genau hier eine Bisektion "unerreichbar"
        gemeldet, wo ein Fenster lag - sie hatte nur den Endpunkt geprueft.
        """
        weg = self.weg(mindestwoelbung)
        schiefe_max, _ = weg.hoechstwert

        assert weg.dsr_bei(schiefe_max) > weg.dsr_bei(schiefe_max + 5.0)
        assert weg.dsr_bei(schiefe_max) > weg.dsr_bei(schiefe_max - 2.0)
        assert schiefe_max == pytest.approx(weg.wendepunkt, rel=0.35)

    def test_festgehaltene_woelbung_meldet_den_niedrigsten_bedarf(self) -> None:
        """Die bisherige Zerlegung - sie steht nur da, um den Abstand zu den
        ehrlichen Rechnungen zu zeigen."""
        fest = self.weg(lambda _s: HEUTE_WOELBUNG).schwelle
        schranke = self.weg(mindestwoelbung).schwelle

        assert fest is not None and schranke is not None
        assert fest < schranke, "Sonst waere die Korrektur wirkungslos"
        assert schranke / HEUTE_SCHIEFE - 1 > 0.5, "mindestens +50 %"

    def test_auf_der_gemessenen_linie_faellt_das_gate_aus(self) -> None:
        """Der Befund selbst: Auf der Linie, auf der alle bisherigen
        Kandidaten lagen, ist das Gate ueber die Schiefe nicht erreichbar."""
        gerade = linie()
        weg = self.weg(lambda s: gerade.woelbung_bei(s) or mindestwoelbung(s))

        assert weg.schwelle is None
        _, dsr_max = weg.hoechstwert
        assert dsr_max < weg.ziel

    def test_das_urteil_nennt_den_hoechstwert_wenn_nichts_geht(self) -> None:
        gerade = linie()
        weg = self.weg(
            lambda s: gerade.woelbung_bei(s) or mindestwoelbung(s),
            name="gemessene Linie",
        )
        urteil = weg.urteil(HEUTE_SCHIEFE)

        assert "nicht erreichbar" in urteil
        assert "hoechste Wert" in urteil

    def test_das_urteil_nennt_die_schwelle_wenn_es_geht(self) -> None:
        weg = self.weg(mindestwoelbung, name="Schranke")
        urteil = weg.urteil(HEUTE_SCHIEFE)

        assert "ab Schiefe" in urteil
        assert "%" in urteil


class TestZusammenstellung:
    def test_drei_wege_von_falsch_bis_gemessen(self) -> None:
        drei = wege(
            **SPITZE, woelbung_heute=HEUTE_WOELBUNG, linie=linie()
        )

        assert len(drei) == 3
        assert [w.schwelle is None for w in drei] == [False, False, True]

    def test_ohne_linie_bleiben_zwei(self) -> None:
        zwei = wege(**SPITZE, woelbung_heute=HEUTE_WOELBUNG, linie=None)

        assert len(zwei) == 2

    def test_die_tabelle_zeigt_beide_ausgaenge(self) -> None:
        text = tabelle(
            wege(**SPITZE, woelbung_heute=HEUTE_WOELBUNG, linie=linie()),
            HEUTE_SCHIEFE,
        )

        assert "nie erreicht" in text
        assert "ab " in text


class TestDerZweiteBetriebspunkt:
    """Befund 125 - derselbe Weg, die andere Guete.

    ``cli form`` rechnet den Schiefe-Weg am Perpetual-Punkt (Guete 0,2569).
    Seit Befund 108 ist Spot der bessere gemessene Punkt (0,2765), und seit
    Befund 112 zeigt ``cli stand`` beide. Hier stand nur einer.

    Die Aussage *"entlang der gemessenen Linie nie erreichbar"* haelt an
    beiden Punkten - aber der Abstand zur Schwelle betraegt am Spot-Punkt
    **0,0079 statt 0,1086**.
    """

    def _linie(self) -> Formlinie:
        """Die gemessene Kopplung, wie ``cli form`` sie live findet."""
        return Formlinie(
            punkte=[
                Formpunkt(quelle="t", kennung=f"p{i}", schiefe=s, woelbung=1.193 * s * s + 1.689)
                for i, s in enumerate((1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0))
            ]
        )

    def _hoechstwert(self, guete: float) -> tuple[float, float]:
        from research.formgrenze import Formweg, mindestwoelbung

        linie = self._linie()
        weg = Formweg(
            sharpe=guete, stichprobe=154, versuche=198,
            kopplung=lambda s, li=linie: li.woelbung_bei(s) or mindestwoelbung(s),
            name="Linie",
        )
        return weg.hoechstwert

    def test_beide_punkte_bleiben_unter_der_schwelle(self) -> None:
        """Die Aussage haelt - das ist die Hauptsache."""
        for guete in (0.2569, 0.2765):
            _, hoehe = self._hoechstwert(guete)
            assert hoehe < 0.95

    def test_der_spot_punkt_liegt_deutlich_hoeher(self) -> None:
        _, perp = self._hoechstwert(0.2569)
        _, spot = self._hoechstwert(0.2765)

        assert spot > perp
        assert spot - perp > 0.05, (
            "Der Unterschied zwischen den Betriebspunkten ist der ganze Befund"
        )

    def test_die_reserve_schrumpft_um_mehr_als_das_zehnfache(self) -> None:
        """0,1086 gegen 0,0079 - wer nur den ersten Wert sieht, haelt den Weg
        fuer bequem ausgeschlossen."""
        _, perp = self._hoechstwert(0.2569)
        _, spot = self._hoechstwert(0.2765)

        assert (0.95 - perp) / (0.95 - spot) > 10

    def test_hoehere_guete_hebt_den_hoechstwert_monoton(self) -> None:
        """Sonst waere der Vergleich zwischen den Punkten nicht aussagekraeftig."""
        werte = [self._hoechstwert(g)[1] for g in (0.20, 0.25, 0.2765, 0.30)]

        assert werte == sorted(werte)

    def test_das_maximum_liegt_nicht_am_rand(self) -> None:
        """``DSR(Schiefe)`` ist nicht monoton - das Maximum ist ein echtes
        Maximum und kein Abtastende. Genau dieser Fehler ist beim Bau des
        Moduls schon einmal passiert."""
        bei, _ = self._hoechstwert(0.2765)

        assert 4.0 < bei < 9.0
