"""Null Treffer in sieben Jahren - Befund 397.

Die offene Richtung aus 395 fragte nach der Rate; Befund 396 hat sie mit
"rund neun unabhaengigen Jahren" beschrieben, aus der Reihenlaenge
geschlossen. Gezaehlt wird an der **Kurve**: Sie beginnt am 19.08.2018, weil
das erste Jahr der Reihe das erste Trainingsfenster bezahlt, umfasst 2921
Tage (7,9973 Jahre), und das achte disjunkte Fenster verfehlt das Kurvenende
um einen Tag. Es sind **sieben**.

Die Phase ist dabei wichtiger als die Rate. Ueber alle 365 Verschiebungen der
Jahresgrenzen reicht das schlechteste disjunkte Jahr von -9,61 % bis
+7,55 % - 17,16 Punkte, dieselbe Kurve. Bei Phase 0 sieht es harmlos aus:

    2018-08-19 bis 2019-08-19      3,07 %
    2019-08-19 bis 2020-08-19     36,78 %
    2020-08-19 bis 2021-08-19     36,20 %
    2021-08-19 bis 2022-08-19     -1,87 %
    2022-08-19 bis 2023-08-19     12,51 %
    2023-08-19 bis 2024-08-19     14,31 %
    2024-08-19 bis 2025-08-19     25,04 %

Das Gate rechnet nicht so - es nimmt das Minimum ueber alle 2557 gleitenden
Fenster, also die unguenstigste Phase.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from research.jahresbild import Jahresbild
from research.jahresrate import schranke, ueber_horizont, unabhaengige_jahre


def _kurve(tage: int, *, ab: str = "2018-08-19", wachstum: float = 0.0) -> pd.Series:
    index = pd.date_range(ab, periods=tage, freq="D", tz="UTC")
    return pd.Series([100.0 * (1 + wachstum) ** i for i in range(tage)], index=index)


class TestDieUnabhaengigenJahre:
    def test_eine_achtjahreskurve_gibt_sieben_fenster(self) -> None:
        """2921 Tage sind 7,9973 Jahre - das achte Fenster verfehlt das Ende
        um einen Tag. Genau diese Zahl stand in Befund 396 als "neun"."""
        folge = unabhaengige_jahre(_kurve(2922))

        assert folge.anzahl == 7

    def test_die_fenster_stossen_aneinander(self) -> None:
        folge = unabhaengige_jahre(_kurve(2922))

        for (_, ende, _), (start, *_) in zip(
            folge.fenster, folge.fenster[1:], strict=False
        ):
            assert ende == start

    def test_ein_halbes_jahr_am_ende_faellt_weg(self) -> None:
        folge = unabhaengige_jahre(_kurve(550))

        assert folge.anzahl == 1

    def test_eine_zu_kurze_kurve_gibt_nichts(self) -> None:
        folge = unabhaengige_jahre(_kurve(200))

        assert folge.anzahl == 0
        assert math.isnan(folge.schlechtestes)

    def test_der_versatz_verschiebt_die_grenzen(self) -> None:
        kurve = _kurve(2922)

        assert unabhaengige_jahre(kurve, versatz=0).fenster[0][0] != (
            unabhaengige_jahre(kurve, versatz=100).fenster[0][0]
        )

    def test_eine_waschsende_kurve_hat_lauter_gleiche_jahre(self) -> None:
        """Die Gegenprobe gegen einen Rechenfehler: Bei konstantem Tageszins
        sind alle Jahre bis auf Schalttage gleich."""
        folge = unabhaengige_jahre(_kurve(2922, wachstum=0.0005))

        assert folge.anzahl == 7
        assert max(folge.renditen) - min(folge.renditen) < 0.1
        assert folge.schlechtestes == pytest.approx(20.0, abs=0.5)

    def test_unter_zaehlt_die_jahre_unter_der_schwelle(self) -> None:
        folge = unabhaengige_jahre(_kurve(2922, wachstum=-0.0005))

        assert folge.unter(-10.0) == 7
        assert folge.unter(-100.0) == 0


class TestDieSchranke:
    def test_null_treffer_aus_sieben(self) -> None:
        assert schranke(0, 7, irrtum=0.05) == pytest.approx(0.3482, abs=0.0001)
        assert schranke(0, 7, irrtum=0.10) == pytest.approx(0.2803, abs=0.0001)

    def test_sie_stimmt_mit_der_geschlossenen_form(self) -> None:
        """``1 - irrtum**(1/n)`` gilt nur bei null Treffern. Gerechnet wird
        allgemein, damit die Zahl auch mit einem Treffer noch stimmt - und
        dieser Test haelt beide Rechnungen aneinander."""
        for n in (1, 3, 7, 9, 40):
            for irrtum in (0.01, 0.05, 0.10):
                assert schranke(0, n, irrtum=irrtum) == pytest.approx(
                    1 - irrtum ** (1 / n), abs=1e-9
                )

    def test_ein_treffer_hebt_sie(self) -> None:
        assert schranke(1, 7) > schranke(0, 7)
        assert schranke(1, 7) == pytest.approx(0.5207, abs=0.0001)

    def test_mehr_jahre_senken_sie(self) -> None:
        folge = [schranke(0, n) for n in (7, 14, 28, 56)]

        assert folge == sorted(folge, reverse=True)

    def test_alle_treffer_schranken_nichts(self) -> None:
        assert schranke(7, 7) == 1.0

    def test_unsinn_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="keine Schranke"):
            schranke(0, 0)
        with pytest.raises(ValueError, match="keine Zahl"):
            schranke(8, 7)
        with pytest.raises(ValueError, match="zwischen null und eins"):
            schranke(0, 7, irrtum=1.0)


class TestUeberDenHorizont:
    def test_die_jahre_des_deflated_sharpe(self) -> None:
        """5,89 Jahre stehen in ``referenz.AUSSICHT`` am Spot-Punkt."""
        assert ueber_horizont(0.3482, 5.89) == pytest.approx(0.920, abs=0.001)
        assert ueber_horizont(0.2803, 5.89) == pytest.approx(0.856, abs=0.001)

    def test_null_rate_bleibt_null(self) -> None:
        """Der Punktschaetzer aus null Treffern - und er gehoert daneben."""
        assert ueber_horizont(0.0, 100.0) == 0.0

    def test_kein_horizont_kein_treffer(self) -> None:
        assert ueber_horizont(0.5, 0.0) == 0.0

    def test_unsinn_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="zwischen null und eins"):
            ueber_horizont(1.5, 1.0)
        with pytest.raises(ValueError, match="Vergangenheit"):
            ueber_horizont(0.5, -1.0)


class TestDasJahresbildNenntSie:
    @staticmethod
    def _bild(werte: list[float], *, jahre: int = 7) -> Jahresbild:
        """Eine Tafel aus genau ``jahre`` verketteten Fenstern.

        Verkettet, nicht gespannt: ``unabhaengige_jahre`` zaehlt die Kette,
        seit die Division sich um eins verrechnet hat (Befund 397).
        """
        gefuellt = (werte + [5.0] * jahre)[:jahre]
        start = pd.to_datetime(
            [f"{2018 + i}-08-19" for i in range(jahre)], utc=True
        )
        return Jahresbild(
            schwelle_pct=-10.0,
            fenster=pd.DataFrame(
                {
                    "start": start,
                    "ende": start + pd.DateOffset(months=12),
                    "rendite_pct": gefuellt,
                }
            ),
        )

    def test_die_zahl_der_jahre_wird_gezaehlt(self) -> None:
        assert self._bild([-9.61, -5.04], jahre=7).unabhaengige_jahre == 7
        assert self._bild([-9.61, -5.04], jahre=14).unabhaengige_jahre == 14

    def test_eine_leere_tafel_hat_keine(self) -> None:
        assert Jahresbild(schwelle_pct=-10.0).unabhaengige_jahre == 0

    def test_und_die_schranke_daraus(self) -> None:
        bild = self._bild([-9.61, -5.04], jahre=7)

        assert bild.ratenschranke(irrtum=0.05) == pytest.approx(0.3482, abs=0.0001)

    def test_mit_einem_fenster_darunter_gibt_es_keine(self) -> None:
        """Aus der Zahl **ueberlappender** Fenster unter der Schwelle laesst
        sich nicht ablesen, wie viele unabhaengige Jahre betroffen sind."""
        bild = self._bild([-10.32, -5.04], jahre=7)

        assert bild.darunter == 1
        assert math.isnan(bild.ratenschranke())

    def test_das_urteil_nennt_sie(self) -> None:
        urteil = self._bild([-9.61, -5.04], jahre=7).urteil()

        assert "7 unabhaengigen Jahren" in urteil
        assert "34.8%" in urteil

    def test_und_sagt_dass_es_keine_prognose_ist(self) -> None:
        urteil = self._bild([-9.61, -5.04], jahre=7).urteil()

        assert "keine Prognose" in urteil
        assert "Grenze des Wissens" in urteil

    def test_das_gefallene_urteil_bleibt_ohne_schranke(self) -> None:
        """Beide Zweige, weil der Anteil darueber entscheidet: Eines von
        sieben sind 14,3 % und damit eine Hochebene, eines von vierzig sind
        2,5 % und damit eine Spitze."""
        hochebene = self._bild([-10.32], jahre=7).urteil()
        spitze = self._bild([-10.32], jahre=40).urteil()

        assert "**Eine Hochebene.**" in hochebene
        assert "**Eine Spitze.**" in spitze
        for urteil in (hochebene, spitze):
            assert "schrankt die Rate" not in urteil


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    @staticmethod
    def _kurve():
        import cli
        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.datenstand import alle_geschnitten
        from research.jahresbild import verkettete_kurve
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        e = get_settings()
        store = CandleStore(e.paths.data_store)
        frames = common_range(
            alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        )
        genom = cli._ohne_hebel(spitzenkandidat())
        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genom), cli._spotconfigs(symbole, e)
        )
        return verkettete_kurve(bericht)

    def test_die_kurve_beginnt_ein_jahr_nach_der_reihe(self) -> None:
        """Das erste Jahr bezahlt das erste Trainingsfenster - der Grund,
        warum es sieben und nicht neun Jahre sind."""
        kurve = self._kurve()

        assert len(kurve) == 2922
        assert kurve.index[0].date().isoformat() == "2018-08-19"
        assert kurve.index[-1].date().isoformat() == "2026-08-18"

    def test_es_sind_sieben_unabhaengige_jahre(self) -> None:
        folge = unabhaengige_jahre(self._kurve())

        assert folge.anzahl == 7
        assert folge.unter(-10.0) == 0

    def test_bei_phase_null_sieht_es_harmlos_aus(self) -> None:
        folge = unabhaengige_jahre(self._kurve())

        assert folge.schlechtestes == pytest.approx(-1.87, abs=0.01)
        assert sum(1 for w in folge.renditen if w < 0) == 1

    def test_die_phase_bewegt_das_schlechteste_jahr_um_17_punkte(self) -> None:
        """Der Kern des Befundes: Dieselbe Kurve, andere Schnittpunkte."""
        kurve = self._kurve()
        minima = [
            unabhaengige_jahre(kurve, versatz=v).schlechtestes for v in range(365)
        ]

        assert min(minima) == pytest.approx(-9.61, abs=0.01)
        assert max(minima) == pytest.approx(7.55, abs=0.01)
        assert max(minima) - min(minima) == pytest.approx(17.16, abs=0.02)

    def test_keine_phase_reisst_die_schwelle(self) -> None:
        """Deshalb ist die Schranke robust gegen die Phase - null Treffer
        bleibt null Treffer, wie auch geschnitten wird."""
        kurve = self._kurve()
        treffer = {
            unabhaengige_jahre(kurve, versatz=v).unter(-10.0) for v in range(365)
        }

        assert treffer == {0}


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_die_korrektur(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 397)

        assert "rund neun unabhaengige Jahre" in eintrag.ergebnis
        assert "**sieben**" in eintrag.ergebnis
        assert "einen Tag" in eintrag.ergebnis

    def test_und_die_phase(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 397)

        assert "+7,55 %" in eintrag.ergebnis
        assert "17,16" in eintrag.ergebnis
        assert "Feste Schwellen auf laufenden Extrema" in eintrag.ergebnis

    def test_und_die_schranke_mit_ihrer_grenze(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 397)

        assert "34,8 %" in eintrag.ergebnis
        assert "92,0 %" in eintrag.ergebnis
        assert "Schranke, kein Schaetzer" in eintrag.ergebnis
        assert "kann nicht" in eintrag.ergebnis

    def test_die_offene_richtung_traegt_die_zahl(self) -> None:
        from research.stand import OFFEN

        eintrag = next(r for r in OFFEN if r.befund == 395)

        assert "nicht neun" in eintrag.ergebnis
        assert "34,8 %" in eintrag.ergebnis
        assert eintrag.zuletzt == 400, "400 hat den Eintrag weitergezogen"

    def test_und_396_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 396).zuletzt == 397
