"""Schlaegt das Timing der Regel den Zufall mit gleicher Haltedauer?

Befund 174 hat gemessen, dass der Holdout 41 % des Vorteils haelt, und
ausdruecklich offengelassen, ob das Koennen ist oder Marktrichtung. Diese
Probe trennt es.

Die Ziehung wird hier an Reihen geprueft, deren Antwort **vorher feststeht**:
eine Reihe mit konstantem Wachstum kann kein Timing belohnen, und eine mit
einem einzigen Sprung schon.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.zufallseinstieg import (
    MINDEST_Z,
    Marktprobe,
    Zufallsbild,
    zufallsverteilung,
)


def probe(symbol: str, echt: float, null: float, streuung: float) -> Marktprobe:
    return Marktprobe(
        symbol=symbol, rolle="Entwicklung", trades=50,
        echt=echt, null=null, streuung=streuung, perzentil=0.9,
    )


class TestDieZiehung:
    def test_auf_konstantem_wachstum_ist_jeder_einstieg_gleich(self) -> None:
        """**Der Fall, dessen Antwort feststeht.** Waechst die Reihe jeden
        Balken um denselben Faktor, haengt die Rendite nur an der Dauer - alle
        Ziehungen muessen dasselbe liefern."""
        schluss = 100.0 * 1.01 ** np.arange(500)
        dauern = np.full(20, 10)

        werte = zufallsverteilung(
            schluss, dauern, von=0, bis=400, ziehungen=200,
            rng=np.random.default_rng(1),
        )

        assert werte.std() == pytest.approx(0.0, abs=1e-12)
        assert werte.mean() == pytest.approx(1.01**10 - 1.0, rel=1e-9)

    def test_laengere_haltedauer_bringt_mehr_bei_aufwaertsdrift(self) -> None:
        schluss = 100.0 * 1.01 ** np.arange(500)
        kurz = zufallsverteilung(
            schluss, np.full(20, 5), von=0, bis=400, ziehungen=50,
            rng=np.random.default_rng(2),
        )
        lang = zufallsverteilung(
            schluss, np.full(20, 40), von=0, bis=400, ziehungen=50,
            rng=np.random.default_rng(2),
        )

        assert lang.mean() > kurz.mean()

    def test_gezogen_wird_nur_aus_dem_angegebenen_zeitraum(self) -> None:
        """**Sonst verglichen sich verschiedene Marktphasen.**

        Die Reihe steigt in der zweiten Haelfte steil; wer aus der ganzen
        Reihe zieht, bekommt einen anderen Erwartungswert als wer nur aus der
        ersten zieht. Ein Markt, der sich verhundertfacht hat, entscheidet
        darueber alles.
        """
        schluss = np.concatenate(
            [np.full(300, 100.0), 100.0 * 1.02 ** np.arange(200)]
        )
        frueh = zufallsverteilung(
            schluss, np.full(10, 5), von=0, bis=250, ziehungen=100,
            rng=np.random.default_rng(3),
        )
        spaet = zufallsverteilung(
            schluss, np.full(10, 5), von=310, bis=490, ziehungen=100,
            rng=np.random.default_rng(3),
        )

        assert frueh.mean() == pytest.approx(0.0, abs=1e-12)
        assert spaet.mean() > 0.05

    def test_ohne_haltedauern_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="nichts zu ziehen"):
            zufallsverteilung(
                np.ones(10), np.array([]), von=0, bis=5, ziehungen=10,
                rng=np.random.default_rng(4),
            )

    def test_ein_leerer_zeitraum_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="Leerer Zeitraum"):
            zufallsverteilung(
                np.ones(10), np.array([2]), von=5, bis=5, ziehungen=10,
                rng=np.random.default_rng(5),
            )

    def test_eine_haltedauer_unter_einem_balken_ist_keine(self) -> None:
        with pytest.raises(ValueError, match="unter einem Balken"):
            zufallsverteilung(
                np.ones(10), np.array([1, 0]), von=0, bis=8, ziehungen=10,
                rng=np.random.default_rng(6),
            )


class TestDieEinordnung:
    def test_z_ist_der_abstand_in_streuungen(self) -> None:
        assert probe("BTC", 0.09, 0.064, 0.041).z == pytest.approx(0.634, abs=0.001)

    def test_ohne_streuung_gibt_es_kein_z(self) -> None:
        """Auf einer Reihe ohne Struktur ist die Null ein Punkt, kein Band -
        ein Abstand in Streuungen waere dann eine Division durch nichts."""
        p = probe("BTC", 0.09, 0.064, 0.0)

        assert p.z is None
        assert not p.belegt
        assert p.darueber

    def test_belegt_verlangt_die_schwelle(self) -> None:
        assert probe("ETH", 0.136, 0.042, 0.033).belegt
        assert not probe("LTC", 0.039, 0.012, 0.018).belegt
        assert MINDEST_Z == 2.0


class TestDasUrteil:
    #: Der gemessene Fall aus Befund 175.
    GEMESSEN = (
        probe("BTC", 0.08989, 0.06406, 0.04104),
        probe("ETH", 0.13592, 0.04179, 0.03334),
        probe("LTC", 0.03869, 0.01187, 0.01762),
        probe("XRP", 0.03642, 0.01697, 0.02409),
    )

    def test_vier_von_vier_heisst_nicht_bloss_marktrichtung(self) -> None:
        text = Zufallsbild(self.GEMESSEN, korrelation=0.695).urteil()

        assert "4 von 4" in text
        assert "nicht bloss Marktrichtung" in text

    def test_die_schwache_deckung_steht_dabei(self) -> None:
        """**Ohne diesen Satz liest sich "4 von 4" als Beleg.**"""
        text = Zufallsbild(self.GEMESSEN, korrelation=0.695).urteil()

        assert "nur 1 von 4" in text
        assert "die Richtung, nicht der Beleg" in text

    def test_es_wird_kein_gemeinsames_z_gerechnet(self) -> None:
        """**Der Kern der Sache.**

        Vier korrelierte Proben zu einem z zusammenzuziehen gaebe eine Zahl,
        die um einen unbekannten Betrag zu gross ist - und sie saehe
        ueberzeugend aus. Das Modul zaehlt stattdessen.
        """
        text = Zufallsbild(self.GEMESSEN, korrelation=0.695).urteil()

        assert "nicht zu einer zusammenziehen" in text
        assert "0.695" in text

    def test_die_fehlenden_stops_stehen_immer_dabei(self) -> None:
        for korrelation in (None, 0.1, 0.9):
            text = Zufallsbild(self.GEMESSEN, korrelation=korrelation).urteil()

            assert "Obergrenze" in text

    def test_ohne_proben_wird_nichts_behauptet(self) -> None:
        assert "Keine Probe" in Zufallsbild(()).urteil()


def test_die_beiden_nullproben_sind_verschiedene_tests() -> None:
    """**Ich habe sie selbst verwechselt** (Befund 175).

    ``research/nullprobe.py`` mischt die Renditen und prueft die Maschine;
    dieses Modul zieht Einstiege und prueft die Regel. Beim Bauen habe ich das
    erste ueberschrieben und aus dem Index zurueckgeholt. Dieser Test haelt
    fest, dass es beide gibt und dass sie verschiedene Fragen stellen.
    """
    import research.nullprobe as maschine
    import research.zufallseinstieg as regel

    assert hasattr(maschine, "mische_renditen")
    assert hasattr(regel, "zufallsverteilung")
    assert not hasattr(maschine, "zufallsverteilung")
    assert "Maschine" in maschine.__doc__
    assert "Haltedauer" in regel.__doc__
