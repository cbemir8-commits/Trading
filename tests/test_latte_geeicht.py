"""Die Latte war nur fuer Mehrfachtests korrigiert - Befund 434.

``schwelle_fuer`` korrigiert nach Bonferroni, also fuer die **Zahl** der
geprueften Zellen, und setzt dabei voraus, dass der t-Wert einer einzelnen
Zelle normalverteilt ist. ``Rotationsprobe.perzentil_99`` misst, dass das
nicht stimmt, und ihr eigener Docstring zieht seit Befund 276 den Schluss:
*"Steht diese Zahl weit darueber, ist die Latte zu niedrig."*

Seit 277 wird sie in jedem Lauf **berichtet**. Angewandt wurde sie nie.

Gemessen ueber die acht Reihen aus Befund 433 reicht sie von 2,52 bis 6,58,
waehrend die Latte durchweg bei 3,5 bis 3,7 steht.
"""

from __future__ import annotations

import pytest

from research.vorteilsscan import (
    MIND_T,
    latte_geeicht,
    normal_99,
    schwelle_fuer,
)

#: Die acht Reihen aus Befund 433: Name, Zellen, Eichung, gemessener t.
#:
#: **Jede Zellenzahl ist aus einer Laufausgabe abgelesen**, keine uebernommen.
#: Zwei standen zuerst falsch hier: BTC 1d mit 122 und BTC 15m mit 243 - beide
#: hatte ich von der ETH-Zeile desselben Intervalls genommen, weil ihr eigenes
#: Urteil ("Ueber der Schwelle ..." und "Fund: ...") die Zahl nicht ausgibt.
#: BTC 1d hat 131. Dieselbe Sorte Fehler wie die Latte selbst: eine Zahl, die
#: danebensteht, fuer die gemessene halten.
REIHEN = (
    ("BTC 1d", 131, 4.14, 3.69),
    ("ETH 1d", 122, 2.82, 2.88),
    ("BTC 4h", 180, 6.16, 2.57),
    ("ETH 4h", 181, 6.58, 3.08),
    ("BTC 1h", 214, 6.30, 2.76),
    ("ETH 1h", 215, 2.87, 2.61),
    ("BTC 15m", 243, 2.52, 3.94),
    ("ETH 15m", 243, 2.79, 3.08),
)


class TestEineQuelleFuerDasReferenzquantil:
    def test_normal_99_ist_gerechnet(self) -> None:
        from statistics import NormalDist

        assert normal_99() == float(NormalDist().inv_cdf(0.995))
        assert abs(normal_99() - 2.5758) < 0.001

    def test_tageszeit_gibt_dieselbe_funktion_weiter(self) -> None:
        """Zwei Stellen, an denen dieselbe Zahl steht, laufen auseinander -
        das sagt ihr eigener Docstring, und seit 434 gilt es auch fuer sie."""
        from research.tageszeit import normal_99 as weitergegeben

        assert weitergegeben is normal_99


class TestOhneEichungBleibtEsWieBisher:
    def test_keine_eichung_heisst_bonferroni(self) -> None:
        """Nicht geeicht ist etwas anderes als geeicht und bestanden."""
        for zellen in (1, 81, 122, 243):
            assert latte_geeicht(zellen) == schwelle_fuer(zellen)

    def test_eine_zelle_ohne_eichung_bleibt_bei_der_mindestschwelle(self) -> None:
        assert latte_geeicht(1) == MIND_T

    def test_aber_die_eichung_hebt_auch_eine_einzelne_zelle(self) -> None:
        """**Mein eigener Fehlgriff, und er ist der Befund selbst.** Hier
        stand ``latte_geeicht(1, 6.0) == MIND_T`` - die Annahme, bei einer
        Zelle sei nichts zu korrigieren. Das verwechselt genau die zwei
        Korrekturen, die 434 trennt: Ohne Mehrfachtest gibt es keine
        Bonferroni-Korrektur, aber wenn verschobene Teiler auf dieser Zelle
        6,0 erreichen, ist eine Latte von 2,0 bedeutungslos. Die Eichung
        betrifft das Lineal, nicht die Zahl der Versuche."""
        assert latte_geeicht(1, 6.0) == pytest.approx(MIND_T * 6.0 / normal_99())
        assert latte_geeicht(1, 6.0) > MIND_T

    def test_unsinnige_eichung_wird_nicht_angewandt(self) -> None:
        assert latte_geeicht(243, 0.0) == schwelle_fuer(243)
        assert latte_geeicht(243, -1.0) == schwelle_fuer(243)


class TestDieEichungHebtDieLatte:
    def test_eine_dickere_nullverteilung_hebt_sie(self) -> None:
        roh = schwelle_fuer(181)

        assert latte_geeicht(181, 6.58) == pytest.approx(roh * 6.58 / normal_99())
        assert latte_geeicht(181, 6.58) > roh * 2.5

    def test_auf_sieben_der_acht_reihen_hebt_sie(self) -> None:
        gehoben = [
            name
            for name, zellen, p99, _ in REIHEN
            if latte_geeicht(zellen, p99) > schwelle_fuer(zellen) + 0.005
        ]

        assert len(gehoben) == 7, gehoben
        assert "BTC 15m" not in gehoben

    def test_und_zwar_dort_wo_der_rueckblick_lang_ist(self) -> None:
        """Die vier Eichungen ueber 4 stehen samt und sonders auf Zellen mit
        Rueckblick 48 oder mehr (Befund 433) - 4h und 1h sind die Laengen,
        auf denen die beste Zelle L192 beziehungsweise L960 hatte."""
        stark = [
            name
            for name, zellen, p99, _ in REIHEN
            if latte_geeicht(zellen, p99) > 2 * schwelle_fuer(zellen)
        ]

        assert sorted(stark) == ["BTC 1h", "BTC 4h", "ETH 4h"], stark


class TestDieUntergrenzeIstGemessenNoetig:
    def test_eine_duennere_nullverteilung_senkt_sie_nicht(self) -> None:
        assert latte_geeicht(243, 2.52) == schwelle_fuer(243)

    def test_ohne_untergrenze_waere_es_eine_lockerung(self) -> None:
        """Und zwar auf genau der Reihe, auf der ein Treffer steht - BTC 15m
        mit |t| = 3,94. Ohne Untergrenze faellt die Latte von 3,71 auf 3,63."""
        roh = schwelle_fuer(243)
        ohne_grenze = roh * 2.52 / normal_99()

        assert ohne_grenze < roh
        assert latte_geeicht(243, 2.52) == roh > ohne_grenze

    def test_der_treffer_auf_15m_bleibt_ein_treffer(self) -> None:
        """Die Eichung darf ihn nicht wegrechnen - verworfen wird er von der
        Randprobe (Befund 431), und das ist eine andere Huerde."""
        assert latte_geeicht(243, 2.52) < 3.94


class TestWasSichAmUrteilAendert:
    def test_btc_tageskerzen_nimmt_die_latte_nicht_mehr(self) -> None:
        """Die einzige Verdikt-Aenderung ueber die acht Reihen: t = +3,69
        gegen eine Latte von 3,53, geeicht 5,68. Verworfen wurde die Zelle
        schon vorher - von der Verschiebungsprobe -, aber erst jetzt traegt
        die erste Huerde sich selbst."""
        zellen, p99, t = 122, 4.14, 3.69

        assert t > schwelle_fuer(zellen)
        assert t < latte_geeicht(zellen, p99)

    def test_und_sonst_kippt_nichts(self) -> None:
        """Eine Aenderung, die alle Urteile umwirft, waere verdaechtig."""
        anders = [
            name
            for name, zellen, p99, t in REIHEN
            if (t > schwelle_fuer(zellen)) != (t > latte_geeicht(zellen, p99))
        ]

        assert anders == ["BTC 1d"], anders


class TestDasUrteilNimmtSieUndSagtEs:
    def _zelle(self, t: float):
        from research.vorteilsscan import Zelle

        return Zelle(
            rueckblick=48, halten=4, beobachtungen=1326,
            spanne_pct=1.5573, t_wert=t,
        )

    def _stabil(self):
        from research.vorteilsscan import Stabilitaet

        return Stabilitaet(erste=self._zelle(3.0), zweite=self._zelle(3.0))

    def test_mit_eichung_faellt_das_urteil_anders_aus(self) -> None:
        from research.vorteilsscan import urteil

        ohne = urteil(self._zelle(3.69), self._stabil(), gepruefte_zellen=122)
        mit = urteil(
            self._zelle(3.69), self._stabil(), gepruefte_zellen=122, eichung=4.14
        )

        assert not ohne.startswith("Nicht auffaellig genug")
        assert mit.startswith("Nicht auffaellig genug")

    def test_und_es_nennt_beide_latten(self) -> None:
        """Wer eine Schwelle liest, die nicht aus der Zellenzahl folgt, muss
        erfahren, woher sie kommt."""
        from research.vorteilsscan import urteil

        text = urteil(
            self._zelle(3.69), self._stabil(), gepruefte_zellen=122, eichung=4.14
        )

        assert "geeicht" in text
        assert "4.14" in text
        assert "verschobene Teiler" in text

    def test_ohne_hebung_steht_kein_eichungssatz_da(self) -> None:
        """Bei einer duenneren Nullverteilung aendert die Eichung nichts -
        dann waere der Satz Rauschen."""
        from research.vorteilsscan import urteil

        text = urteil(
            self._zelle(2.0), self._stabil(), gepruefte_zellen=243, eichung=2.52
        )

        assert "geeicht" not in text


class TestDerScanWendetSieAn:
    """Seit 277 berichtet, nie angewandt - das ist der ganze Befund."""

    def _quelle(self) -> str:
        import inspect

        import cli

        return inspect.getsource(cli.scan)

    def test_das_urteil_bekommt_die_eichung(self) -> None:
        assert "eichung=beste_probe.perzentil_99" in self._quelle()

    def test_und_die_zeile_zeigt_beide_latten(self) -> None:
        quelle = self._quelle()

        assert "latte_geeicht(gesamt, beste_probe.perzentil_99)" in quelle
        assert "geeicht {geeicht:.2f}" in quelle
