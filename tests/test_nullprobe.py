"""Die Nullprobe - findet die Maschine Vorteile, wo keine sind?

Der wichtigste Test dieser Datei ist ``test_mischen_erhaelt_die_gesamtrendite``.
Er haelt die Eigenschaft fest, in die ich beim Bauen hineingelaufen bin: Das
Mischen der Renditen laesst die Gesamtrendite **exakt** unveraendert, weil ihr
Produkt nicht von der Reihenfolge abhaengt. Wer Kaufen-und-Halten als
Vergleichsgroesse zwischen den Laeufen benutzt, vergleicht mit einer Konstanten
und bekommt eine Fehlwarnung.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.nullprobe import (
    Nullergebnis,
    Nullverteilung,
    kaufen_und_halten_pct,
    mische_renditen,
)


def kerzen(n: int = 400, saat: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(saat)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2020-01-01", periods=n, freq="1D", tz="UTC"),
            "open": close * 0.999,
            "high": close * 1.015,
            "low": close * 0.985,
            "close": close,
            "volume": np.full(n, 100.0),
            "turnover": close * 100.0,
        }
    )


class TestMischen:
    def test_mischen_erhaelt_die_gesamtrendite(self) -> None:
        """**Die Eigenschaft, die mir eine Fehlwarnung eingebracht hat.**

        Das Produkt der Renditen haengt nicht von ihrer Reihenfolge ab. Also
        ist Kaufen-und-Halten auf jeder gemischten Reihe dieselbe Zahl - und
        als Vergleichsgroesse zwischen Laeufen untauglich.
        """
        original = kerzen()

        for saat in (1, 2, 3):
            gemischt = mische_renditen(original, saat=saat)
            assert kaufen_und_halten_pct(gemischt) == pytest.approx(
                kaufen_und_halten_pct(original), rel=1e-9
            )

    def test_die_renditen_selbst_bleiben_dieselben(self) -> None:
        """Nur die Reihenfolge aendert sich - nicht die Verteilung."""
        original = kerzen()
        gemischt = mische_renditen(original, saat=5)

        a = np.sort(np.diff(np.log(original["close"].to_numpy(dtype=float))))
        b = np.sort(np.diff(np.log(gemischt["close"].to_numpy(dtype=float))))

        assert np.allclose(a, b)

    def test_die_reihenfolge_aendert_sich_wirklich(self) -> None:
        original = kerzen()
        gemischt = mische_renditen(original, saat=5)

        assert not np.allclose(
            original["close"].to_numpy(dtype=float),
            gemischt["close"].to_numpy(dtype=float),
        )

    def test_kerzen_bleiben_stimmig(self) -> None:
        """Hoch muss den Bereich umschliessen, tief ebenso.

        Sonst greifen Stops an Preisen, die es in keiner Kerze gab - und die
        Nullprobe misst einen Fehler, den sie selbst erzeugt hat.
        """
        gemischt = mische_renditen(kerzen(), saat=7)

        assert (gemischt["high"] >= gemischt[["open", "close"]].max(axis=1)).all()
        assert (gemischt["low"] <= gemischt[["open", "close"]].min(axis=1)).all()
        assert (gemischt["high"] >= gemischt["low"]).all()
        assert (gemischt["close"] > 0).all()

    def test_dieselbe_saat_dasselbe_ergebnis(self) -> None:
        a = mische_renditen(kerzen(), saat=9)
        b = mische_renditen(kerzen(), saat=9)

        assert np.allclose(a["close"], b["close"])

    def test_zu_kurze_reihe_bleibt_unveraendert(self) -> None:
        kurz = kerzen(2)

        assert np.allclose(mische_renditen(kurz, saat=1)["close"], kurz["close"])


def ergebnis(ertrag: float, *, trades: int = 150) -> Nullergebnis:
    return Nullergebnis(
        trades=trades, erwartung_r=0.0, ertrag_pct=ertrag, kaufen_halten_pct=945.8
    )


class TestNullverteilung:
    def test_gemessene_lage_wird_richtig_beurteilt(self) -> None:
        """Die echten Zahlen: gemischt im Median -22 %, echt +160,7 %."""
        rng = np.random.default_rng(3)
        v = Nullverteilung(
            echt=ergebnis(160.7, trades=154),
            gemischt=[ergebnis(float(x)) for x in rng.normal(-22.0, 15.0, 40)],
        )

        assert v.maschine_sauber
        assert v.hebt_sich_ab
        assert v.p_ertrag == 0.0
        assert "Beides noetig, beides erfuellt" in v.bericht()

    def test_verdienen_auf_rauschen_ist_ein_maschinenfehler(self) -> None:
        """**Der Fall, fuer den die Probe gebaut ist.**

        Wenn eine Trendfolge auf gemischten Renditen verdient, gibt es dort
        nichts zu verdienen - also kommt es aus der Maschine.
        """
        rng = np.random.default_rng(4)
        v = Nullverteilung(
            echt=ergebnis(160.7),
            gemischt=[ergebnis(float(x)) for x in rng.normal(+30.0, 15.0, 40)],
        )

        assert not v.maschine_sauber
        assert "WARNUNG" in v.bericht()
        assert "Lookahead" in v.bericht()

    def test_echte_reihe_ohne_abstand(self) -> None:
        rng = np.random.default_rng(5)
        v = Nullverteilung(
            echt=ergebnis(-10.0),
            gemischt=[ergebnis(float(x)) for x in rng.normal(-12.0, 30.0, 40)],
        )

        assert v.maschine_sauber
        assert not v.hebt_sich_ab
        assert "leistet der Zufall auch" in v.bericht()

    def test_ohne_gemischte_laeufe(self) -> None:
        v = Nullverteilung(echt=ergebnis(160.7))

        assert not v.maschine_sauber
        assert not v.hebt_sich_ab
        assert "Keine gemischten Laeufe" in v.bericht()

    def test_bericht_warnt_vor_der_konstanten(self) -> None:
        """Damit niemand denselben Fehler noch einmal macht."""
        v = Nullverteilung(echt=ergebnis(160.7), gemischt=[ergebnis(-22.0)])

        assert "Mischen die Gesamtrendite erhaelt" in v.bericht()

    def test_ueberschuss_bleibt_als_einordnung(self) -> None:
        e = ergebnis(160.7)

        assert e.ueberschuss_pct == pytest.approx(160.7 - 945.8)


def test_kaufen_und_halten() -> None:
    frame = kerzen()
    close = frame["close"].to_numpy(dtype=float)

    assert kaufen_und_halten_pct(frame) == pytest.approx(
        (close[-1] / close[0] - 1) * 100
    )
    assert kaufen_und_halten_pct(frame.head(1)) == 0.0
