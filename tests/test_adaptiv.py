"""Die Periode aus dem Trainingsfenster waehlen - ohne ins Testfenster zu sehen.

Der wichtigste Test steht in ``TestKeinBlickInsTestfenster``. Wuerde die
Auswahl auch nur eine Kerze des Testfensters sehen, waere der ganze
Walk-Forward wertlos - und das Ergebnis saehe **besser** aus, nicht
schlechter. Genau solche Fehler fallen nicht von selbst auf.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestConfig
from backtest.walkforward import Window
from core.config import RiskSettings
from core.models import Instrument
from research.adaptiv import (
    MINDESTBREITE,
    FensterWahl,
    mitte_des_plateaus,
    waehle,
)
from research.landschaft import Landschaft, Punkt
from research.seeds import spitzenkandidat


def punkt(faktor: float, gewinn: float) -> Punkt:
    return Punkt(faktor=faktor, leitperiode=int(200 * faktor),
                 gewinn=gewinn, trades=10)


class TestDieMitteWirdGewaehlt:
    """Nicht der beste Punkt - die Mitte des tragfaehigen Bereichs.

    Die Regel steht **vor** der Messung fest. Haette ich sie hinterher
    gewaehlt, weil sie besser aussieht, waere das dieselbe Ueberanpassung
    eine Ebene hoeher.
    """

    def test_mitte_statt_maximum(self):
        # Der hoechste Gewinn liegt am linken Rand des Bereichs.
        karte = Landschaft(punkte=[
            punkt(0.6, 900), punkt(0.7, 100), punkt(0.8, 100),
            punkt(0.9, 100), punkt(1.0, -5),
        ])

        faktor, breite = mitte_des_plateaus(karte)

        assert breite == 4
        assert faktor == 0.7, "Die Mitte von 0,6-0,9, nicht der Spitzenwert 0,6"

    def test_grat_wird_verworfen(self):
        """Ein einzelner Treffer ohne Nachbarn ist keine Grundlage."""
        karte = Landschaft(punkte=[punkt(0.8, -1), punkt(0.9, 500), punkt(1.0, -1)])

        assert mitte_des_plateaus(karte) is None

    def test_mindestbreite_wird_eingehalten(self):
        karte = Landschaft(punkte=[punkt(0.9, 5), punkt(1.0, 5), punkt(1.1, -1)])

        faktor, breite = mitte_des_plateaus(karte)

        assert breite >= MINDESTBREITE
        assert faktor == 0.9

    def test_bei_gerader_breite_der_langsamere(self):
        """Festgelegt, damit nicht die Rundung entscheidet.

        Ohne Regel lieferte dieselbe Karte je nach Implementierung zwei
        verschiedene Antworten - und der Vergleich zweier Laeufe waere
        wertlos.
        """
        karte = Landschaft(punkte=[punkt(0.8, 5), punkt(0.9, 5)])

        faktor, _ = mitte_des_plateaus(karte)

        assert faktor == 0.8

    def test_laengster_bereich_gewinnt_nicht_der_beste(self):
        """Zwei Bereiche: ein kurzer mit hohem Gewinn, ein langer mit wenig."""
        karte = Landschaft(punkte=[
            punkt(0.5, 5000), punkt(0.6, 5000), punkt(0.7, -1),
            punkt(0.8, 10), punkt(0.9, 10), punkt(1.0, 10), punkt(1.1, 10),
        ])

        faktor, breite = mitte_des_plateaus(karte)

        assert breite == 4, "Der laengere Bereich, nicht der ertragreichere"
        assert faktor == 0.9

    def test_leere_karte(self):
        assert mitte_des_plateaus(Landschaft()) is None


class TestKeinBlickInsTestfenster:
    """Der Test, auf den es ankommt.

    Eine Auswahl, die Testdaten sieht, hebelt den Walk-Forward aus - und das
    Ergebnis sieht danach **besser** aus. Solche Fehler melden sich nicht.
    """

    @pytest.fixture
    def welt(self):
        n = 900
        rng = np.random.default_rng(5)
        kurs = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
        frame = pd.DataFrame({
            "open_time": pd.date_range("2018-01-01", periods=n, freq="1D", tz="UTC"),
            "open": kurs, "high": kurs * 1.02, "low": kurs * 0.98, "close": kurs,
            "volume": np.full(n, 100.0), "turnover": kurs * 100.0,
        })
        instrument = Instrument(
            symbol="BTCUSDT", tick_size=Decimal("0.01"), qty_step=Decimal("0.001"),
            min_order_qty=Decimal("0.001"), max_order_qty=Decimal("1190"),
            min_notional=Decimal("5"), max_leverage=Decimal("100"),
        )
        config = BacktestConfig(
            instrument=instrument, risk=RiskSettings(), initial_equity=Decimal("500")
        )
        return {"M": frame}, {"M": config}

    def test_trainingsdaten_enden_vor_dem_testfenster(self, welt):
        frames, configs = welt
        wahl = FensterWahl(spitzenkandidat(), frames, configs)
        fenster = Window(
            index=0,
            train_start=datetime(2018, 1, 1, tzinfo=UTC),
            train_end=datetime(2019, 1, 1, tzinfo=UTC),
            test_start=datetime(2019, 1, 1, tzinfo=UTC),
            test_end=datetime(2019, 4, 1, tzinfo=UTC),
        )

        daten = wahl._trainingsdaten(fenster)

        letzte = daten["M"]["open_time"].max()
        assert letzte < fenster.train_end
        assert letzte < fenster.test_start, (
            "Auch nur eine Kerze des Testfensters waere Lookahead"
        )

    def test_obere_grenze_ist_ausschliessend(self, welt):
        """Die Kerze **auf** train_end ist schon die erste des Tests."""
        frames, configs = welt
        wahl = FensterWahl(spitzenkandidat(), frames, configs)
        grenze = datetime(2019, 1, 1, tzinfo=UTC)
        fenster = Window(
            index=0, train_start=datetime(2018, 1, 1, tzinfo=UTC),
            train_end=grenze, test_start=grenze,
            test_end=datetime(2019, 4, 1, tzinfo=UTC),
        )

        daten = wahl._trainingsdaten(fenster)

        assert not (daten["M"]["open_time"] >= grenze).any()

    def test_verschiedene_fenster_sehen_verschiedene_daten(self, welt):
        frames, configs = welt
        wahl = FensterWahl(spitzenkandidat(), frames, configs)

        def f(index, jahr):
            return Window(
                index=index,
                train_start=datetime(jahr, 1, 1, tzinfo=UTC),
                train_end=datetime(jahr + 1, 1, 1, tzinfo=UTC),
                test_start=datetime(jahr + 1, 1, 1, tzinfo=UTC),
                test_end=datetime(jahr + 1, 4, 1, tzinfo=UTC),
            )

        a = wahl._trainingsdaten(f(0, 2018))["M"]
        b = wahl._trainingsdaten(f(1, 2019))["M"]

        assert a["open_time"].max() < b["open_time"].max()


class TestFensterWahl:
    @pytest.fixture
    def welt(self):
        n = 500
        rng = np.random.default_rng(9)
        kurs = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
        frame = pd.DataFrame({
            "open_time": pd.date_range("2020-01-01", periods=n, freq="1D", tz="UTC"),
            "open": kurs, "high": kurs * 1.02, "low": kurs * 0.98, "close": kurs,
            "volume": np.full(n, 100.0), "turnover": kurs * 100.0,
        })
        instrument = Instrument(
            symbol="X", tick_size=Decimal("0.01"), qty_step=Decimal("0.001"),
            min_order_qty=Decimal("0.001"), max_order_qty=Decimal("1190"),
            min_notional=Decimal("5"), max_leverage=Decimal("100"),
        )
        config = BacktestConfig(
            instrument=instrument, risk=RiskSettings(), initial_equity=Decimal("500")
        )
        return {"A": frame, "B": frame}, {"A": config, "B": config}

    def _fenster(self, index=0):
        return Window(
            index=index,
            train_start=datetime(2020, 1, 1, tzinfo=UTC),
            train_end=datetime(2021, 1, 1, tzinfo=UTC),
            test_start=datetime(2021, 1, 1, tzinfo=UTC),
            test_end=datetime(2021, 4, 1, tzinfo=UTC),
        )

    def test_pro_fenster_wird_nur_einmal_gewaehlt(self, welt):
        """Dieselbe Funktion wird je Markt gerufen - die Karte darf nicht
        je Markt neu entstehen.

        Sonst waere es nicht nur langsam: Jeder Markt bekaeme womoeglich
        seine eigene Periode, und aus einer Strategie wuerden zwei.
        """
        frames, configs = welt
        wahl = FensterWahl(spitzenkandidat(), frames, configs,
                           faktoren=(0.8, 1.0, 1.2))

        erste = wahl(self._fenster())
        zweite = wahl(self._fenster())

        assert len(wahl.wahlen) == 1
        assert erste.strategy_id == zweite.strategy_id

    def test_ohne_tragfaehigen_bereich_bleibt_das_genom(self, welt):
        """Konservativ: Wer im Training nichts findet, verstellt nichts."""
        frames, configs = welt
        genome = spitzenkandidat()
        # Nur ein Faktor - damit kann kein Bereich der Mindestbreite entstehen.
        wahl = FensterWahl(genome, frames, configs, faktoren=(1.0,))

        wahl(self._fenster())

        assert wahl.wahlen[0].faktor == 1.0
        assert not wahl.wahlen[0].gefunden

    def test_bericht_nennt_die_spanne(self, welt):
        frames, configs = welt
        wahl = FensterWahl(spitzenkandidat(), frames, configs,
                           faktoren=(0.8, 1.0, 1.2))
        wahl(self._fenster(0))

        text = wahl.bericht()

        assert "Fenster" in text
        assert "Faktor" in text

    def test_leerer_bericht_behauptet_nichts(self, welt):
        frames, configs = welt
        wahl = FensterWahl(spitzenkandidat(), frames, configs)

        assert "Noch nichts" in wahl.bericht()


class TestWaehle:
    def test_gibt_das_skalierte_genom_zurueck(self):
        genome = spitzenkandidat()
        karte = Landschaft(punkte=[
            punkt(0.6, 5), punkt(0.7, 5), punkt(0.8, 5),
        ])

        faktor, _ = mitte_des_plateaus(karte)

        from research.gates import skaliere_perioden

        skaliert = skaliere_perioden(genome, faktor)
        assert skaliert is not None
        assert skaliert.genome_id != genome.genome_id

    def test_waehle_reicht_das_original_durch_wenn_nichts_gefunden(self):
        """``waehle`` auf einer Reihe ohne profitable Nachbarschaft."""
        genome = spitzenkandidat()
        n = 300
        kurs = np.linspace(100.0, 50.0, n)  # stetig fallend, nichts geht
        frame = pd.DataFrame({
            "open_time": pd.date_range("2020-01-01", periods=n, freq="1D", tz="UTC"),
            "open": kurs, "high": kurs * 1.001, "low": kurs * 0.999, "close": kurs,
            "volume": np.full(n, 100.0), "turnover": kurs * 100.0,
        })
        instrument = Instrument(
            symbol="X", tick_size=Decimal("0.01"), qty_step=Decimal("0.001"),
            min_order_qty=Decimal("0.001"), max_order_qty=Decimal("1190"),
            min_notional=Decimal("5"), max_leverage=Decimal("100"),
        )
        config = BacktestConfig(
            instrument=instrument, risk=RiskSettings(), initial_equity=Decimal("500")
        )

        ergebnis = waehle(genome, {"X": frame}, {"X": config},
                          faktoren=(0.8, 1.0, 1.2))

        assert ergebnis.genome.genome_id == genome.genome_id
        assert not ergebnis.gefunden
