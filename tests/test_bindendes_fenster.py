"""Das bindende Fenster war geraten - Befund 396.

Die offene Richtung aus Befund 395 nannte das bindende Zwoelfmonatsfenster
"das mit dem Absturz im Maerz 2020". Geschlossen hatte ich das aus der Leiter:
Der Wert springt, sobald die Reihe nach dem 2020-03-30 beginnt.

Gemessen, am Spot-Punkt, je Reihenanfang:

    ab            Fenster  unter -10  schlecht.  zweit*  bindendes Fenster
    2017-08-16       2557          0      -9,61   -5,04  2021-11-08..2022-11-08
    2018-08-16       2192          0      -9,61   -5,04  2021-11-08..2022-11-08
    2019-08-16       1826          0      -9,61   -5,04  2021-11-08..2022-11-08
    2020-03-30       1548          0      -5,60   +0,23  2021-09-06..2022-09-06
    2021-08-16       1096          0      -5,04   +3,13  2025-08-13..2026-08-13

    * das schlechteste Fenster, das sich mit dem schlechtesten nicht ueberlappt

Es ist der **Baerenmarkt 2022**, und er liegt in beiden Reihen drin. Der
Sprung kommt daher, dass der Schnitt am Anfang die Walk-Forward-Aufteilung
verschiebt: Die Strategie macht im selben Fenster andere Trades.

Daraus folgt die Abgrenzung, die dieser Befund festhaelt: **Die Leiter ist
kein Beleg fuer die Einwegaussage.** Was sie traegt, ist die Bauart des
Walk-Forward - angehaengte Daten lassen die frueheren Fenster unberuehrt
(Kreuz aus 395: 50 Tage mehr Speicher, dieselbe Zahl auf vier Stellen). Beim
Schneiden am Anfang gilt es nicht.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from research.jahresbild import Jahresbild


def _bild(werte: list[float], *, schwelle: float = -10.0) -> Jahresbild:
    """Ein Jahresbild aus Fensterrenditen, Fenster je zwei Jahre versetzt.

    **Zwei** Jahre, nicht eins: Bei einem Jahr Versatz stossen Ende und
    Anfang genau aneinander, und ``_zweites`` zaehlt ein beruehrendes Fenster
    als ueberlappend (``start > ende`` ist dort echt). Mit einem Jahr Versatz
    hat dieser Test die Luft falsch gemessen - 22,53 statt 4,57.
    """
    start = pd.to_datetime(
        [f"{2017 + 2 * i}-01-01" for i in range(len(werte))], utc=True
    )
    return Jahresbild(
        schwelle_pct=schwelle,
        fenster=pd.DataFrame(
            {
                "start": start,
                "ende": start + pd.DateOffset(months=12),
                "rendite_pct": werte,
            }
        ),
    )


class TestDieReserve:
    def test_sie_ist_der_abstand_zur_schwelle(self) -> None:
        bild = _bild([-9.61, -5.04, 12.92])

        assert bild.reserve == pytest.approx(0.39, abs=0.001)

    def test_negativ_heisst_durchgefallen(self) -> None:
        bild = _bild([-10.32, -5.04])

        assert bild.reserve == pytest.approx(-0.32, abs=0.001)
        assert bild.darunter == 1

    def test_ohne_fenster_keine_zahl(self) -> None:
        bild = Jahresbild(schwelle_pct=-10.0)

        assert math.isnan(bild.reserve)


class TestDieLuft:
    def test_sie_misst_bis_zum_naechsten_getrennten(self) -> None:
        """4,57 Punkte am Spot-Punkt: -9,61 gegen -5,04."""
        bild = _bild([-9.61, -5.04, 12.92, 71.50])

        assert bild.luft == pytest.approx(4.57, abs=0.001)

    def test_ueberlappende_fenster_zaehlen_nicht(self) -> None:
        """Sonst waere es derselbe Einbruch, einen Tag versetzt - die Regel
        steckt schon in ``_zweites``, und ``luft`` erbt sie."""
        start = pd.to_datetime(["2021-11-08", "2021-11-09"], utc=True)
        bild = Jahresbild(
            schwelle_pct=-10.0,
            fenster=pd.DataFrame(
                {
                    "start": start,
                    "ende": start + pd.DateOffset(months=12),
                    "rendite_pct": [-9.61, -9.60],
                }
            ),
        )

        assert math.isnan(bild.luft)

    def test_ohne_getrenntes_fenster_keine_zahl(self) -> None:
        bild = _bild([-9.61])

        assert math.isnan(bild.luft)


class TestDasUrteilBeimBestandenenGate:
    """Hier stand ein Satz, der mit "besteht die Strategie hier" endete - und
    die Frage, um die es diesem Modul geht, blieb unbeantwortet."""

    def test_es_nennt_die_reserve(self) -> None:
        bild = _bild([-9.61, -5.04, 12.92])
        urteil = bild.urteil()

        assert "0.39 Punkten Reserve" in urteil

    def test_und_dass_das_schlechteste_fenster_allein_steht(self) -> None:
        bild = _bild([-9.61, -5.04, 12.92])
        urteil = bild.urteil()

        assert "steht allein" in urteil
        assert "4.57 Punkte" in urteil

    def test_und_dass_die_reserve_ein_guthaben_ist(self) -> None:
        """Die unbequeme Haelfte, und sie gilt unabhaengig vom Urteil."""
        bild = _bild([-9.61, -5.04, 12.92])
        urteil = bild.urteil()

        assert "Guthaben" in urteil
        assert "Minimum ueber alle Fenster" in urteil
        assert "nur kleiner werden" in urteil

    def test_ohne_getrenntes_fenster_bleibt_die_reserve_stehen(self) -> None:
        """Die Luft fehlt, das Urteil nicht - eine Reihe von knapp zwei
        Jahren hat kein getrenntes Fenster."""
        bild = _bild([-9.61])
        urteil = bild.urteil()

        assert "0.39 Punkten Reserve" in urteil
        assert "steht allein" not in urteil
        assert "Guthaben" in urteil

    def test_das_gefallene_urteil_bleibt_wie_es_war(self) -> None:
        """Spitze und Hochebene sind Befund 161/der Modulzweck - daran
        aendert dieser Befund nichts."""
        spitze = _bild([-10.32] + [5.0] * 99)
        hochebene = _bild([-10.32] * 30 + [5.0] * 70)

        assert "**Eine Spitze.**" in spitze.urteil()
        assert "**Eine Hochebene.**" in hochebene.urteil()


class TestDerModulkopfNenntDenPunkt:
    def test_die_vier_gates_sind_die_des_berichteten_punkts(self) -> None:
        """Im Kreuz aus Befund 395 gemessen: Perpetual auf dem Speicher faellt
        bei vier Gates, Spot auf der Reihe bei zwei."""
        from research import jahresbild

        kopf = jahresbild.__doc__ or ""

        assert "am **berichteten** Punkt" in kopf

    def test_und_die_zahl_des_massgeblichen_steht_daneben(self) -> None:
        from research import jahresbild

        kopf = jahresbild.__doc__ or ""

        assert "-9,61 % gegen -10,00 %" in kopf
        assert "0,39 Punkte Reserve" in kopf
        assert "das Funding, nicht die Reihe" in kopf


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    """Welches Fenster bindet, und wie es sich beim Schneiden verhaelt."""

    @staticmethod
    def _zerlegung(ab: str | None):
        from pathlib import Path

        import cli
        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.datenstand import alle_geschnitten
        from research.jahresbild import rollierende_jahre, verkettete_kurve
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        e = get_settings()
        store = CandleStore(e.paths.data_store)
        assert Path(e.paths.data_store).exists()
        roh = alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        if ab is not None:
            grenze = pd.Timestamp(ab, tz="UTC")
            roh = {
                s: f[pd.to_datetime(f["open_time"], utc=True) >= grenze].reset_index(
                    drop=True
                )
                for s, f in roh.items()
            }
        frames = common_range(roh)
        genom = cli._ohne_hebel(spitzenkandidat())
        bericht = run_portfolio_walkforward(
            frames,
            lambda: compile_genome(genom),
            cli._spotconfigs(symbole, e),
        )
        tafel = rollierende_jahre(verkettete_kurve(bericht))
        return Jahresbild(schwelle_pct=-10.0, fenster=tafel)

    def test_es_ist_der_baerenmarkt_2022(self) -> None:
        bild = self._zerlegung(None)
        von, bis = bild.zeitraum

        assert (von.year, von.month) == (2021, 11)
        assert (bis.year, bis.month) == (2022, 11)

    def test_null_fenster_unter_der_schwelle_und_4_57_luft(self) -> None:
        bild = self._zerlegung(None)

        assert len(bild.fenster) == 2557
        assert bild.darunter == 0
        assert bild.reserve == pytest.approx(0.39, abs=0.01)
        assert bild.luft == pytest.approx(4.57, abs=0.01)

    def test_das_bindende_fenster_liegt_auch_in_der_kurzen_reihe(self) -> None:
        """Der Kern der Gegenprobe: Es faellt nicht heraus, es aendert sich -
        und deshalb ist die Leiter kein Beleg fuer die Einwegaussage."""
        lang = self._zerlegung(None)
        kurz = self._zerlegung("2020-03-30")
        von, bis = lang.zeitraum

        assert kurz.fenster["start"].min() < von, "das Fenster beginnt spaeter"
        assert np.isfinite(
            float(
                kurz.fenster.loc[
                    (kurz.fenster["start"] <= von) & (kurz.fenster["ende"] >= bis),
                    "rendite_pct",
                ].min()
            )
        ), "es gibt dort ein Fenster, das das bindende umschliesst"

    def test_und_die_strategie_macht_dort_andere_trades(self) -> None:
        lang = self._zerlegung(None)
        kurz = self._zerlegung("2020-03-30")

        assert lang.schlechtestes == pytest.approx(-9.61, abs=0.01)
        assert kurz.schlechtestes == pytest.approx(-5.60, abs=0.01)
        assert kurz.zeitraum[0] != lang.zeitraum[0]


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_die_korrektur(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 396)

        assert "Mein Fehler" in eintrag.ergebnis
        assert "2021-11-08 bis 2022-11-08" in eintrag.ergebnis
        assert "Maerz 2020" in eintrag.ergebnis

    def test_und_die_abgrenzung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 396)

        assert "kein Beleg fuer die Einwegaussage" in eintrag.ergebnis
        assert "unberuehrt" in eintrag.ergebnis

    def test_und_die_verteilung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 396)

        assert "2557" in eintrag.ergebnis
        assert "4,57" in eintrag.ergebnis
        assert "Spitze" in eintrag.ergebnis

    def test_die_offene_richtung_traegt_den_vermerk(self) -> None:
        """Korrigiert wird durch Vermerk, nicht durch Ueberschreiben."""
        from research.stand import OFFEN

        eintrag = next(r for r in OFFEN if r.befund == 395)

        assert "zuerst geraten" in eintrag.ergebnis
        assert "2021-11-08 bis 2022-11-08" in eintrag.ergebnis
        assert eintrag.zuletzt == 400, "400 hat denselben Eintrag weitergezogen"

    def test_und_die_rate_ist_inzwischen_geschrankt(self) -> None:
        """Hier stand 'rund **neun** unabhaengige Jahre' - aus der
        Reihenlaenge geschlossen. Befund 397 hat an der Kurve gezaehlt: Es
        sind sieben, weil das erste Jahr das erste Trainingsfenster bezahlt.
        Dieser Test ist dabei gefallen, wie er soll.
        """
        from research.stand import OFFEN

        eintrag = next(r for r in OFFEN if r.befund == 395)

        assert "nicht neun" in eintrag.ergebnis
        assert "**sieben**" in eintrag.ergebnis
        assert "34,8 %" in eintrag.ergebnis

    def test_und_395_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 395).zuletzt == 396
