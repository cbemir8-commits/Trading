"""Woraus besteht das schlechteste Jahr?

Das Gate "Schlechtestes Jahr" gibt eine einzige Zahl zurueck und laesst damit
zwei voellig verschiedene Lagen gleich aussehen: ein einzelnes ungluecklich
ausgerichtetes Zwoelfmonatsfenster, oder ein Viertel aller Fenster. Diese
Zerlegung trennt sie.

Drei Tests tragen die Datei:

* ``test_dieselbe_kurve_wie_das_gate`` - es gibt jetzt **zwei** Umsetzungen
  derselben Kapitalkurve. Laufen sie auseinander, misst die Zerlegung etwas
  anderes als das Gate, und die Aussage waere wertlos. Genau dieser Fehler ist
  in diesem Projekt schon viermal aufgetreten.
* ``test_das_zweitschlechteste_ueberlappt_nicht`` - ohne diese Bedingung ist
  das zweitschlechteste Fenster derselbe Einbruch, einen Tag versetzt. Es
  saehe dann immer nach Hochebene aus, auch bei einer einzelnen Spitze.
* ``test_spitze_und_hochebene_werden_unterschieden`` - der Zweck des Ganzen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from backtest.walkforward import chained_curve
from research.jahresbild import (
    Jahresbild,
    rollierende_jahre,
    verkettete_kurve,
    zerlege,
)

T0 = datetime(2019, 1, 1, tzinfo=UTC)


@dataclass
class FakeResult:
    equity_curve: pd.DataFrame


@dataclass
class FakeFenster:
    result: FakeResult


@dataclass
class FakeReport:
    windows: list


@dataclass(frozen=True)
class FakeTrade:
    entry_time: datetime
    symbol: str
    r_multiple: float | None


def stueck(start: str, tage: int, faktor: float) -> FakeFenster:
    """Ein Testfenster, dessen Kapital linear auf ``faktor`` laeuft."""
    zeiten = pd.date_range(start, periods=tage, freq="D", tz="UTC")
    werte = np.linspace(500.0, 500.0 * faktor, tage)
    return FakeFenster(
        result=FakeResult(pd.DataFrame({"time": zeiten, "equity": werte}))
    )


def bericht(*stuecke: FakeFenster) -> FakeReport:
    return FakeReport(windows=list(stuecke))


class TestVerketteteKurve:
    def test_dieselbe_kurve_wie_das_gate(self) -> None:
        """**Zwei Umsetzungen derselben Groesse muessen dasselbe liefern.**

        ``chained_curve`` gibt ein nacktes Array, ``verkettete_kurve`` dieselbe
        Kurve mit Zeitstempeln. Laufen die Werte auseinander, zerlegt diese
        Datei eine andere Kurve als die, ueber die das Gate urteilt.
        """
        r = bericht(
            stueck("2019-01-01", 90, 1.10),
            stueck("2019-04-01", 90, 0.95),
            stueck("2019-07-01", 90, 1.20),
        )

        mit_zeit = verkettete_kurve(r)
        ohne = chained_curve(r)

        assert len(mit_zeit) == len(ohne)
        assert np.allclose(mit_zeit.to_numpy(), ohne)

    def test_verkettet_multiplikativ(self) -> None:
        """Zwei Fenster mit je +10 % ergeben +21 %, nicht +20 %."""
        kurve = verkettete_kurve(
            bericht(stueck("2019-01-01", 30, 1.10), stueck("2019-02-01", 30, 1.10))
        )

        assert float(kurve.iloc[-1]) == pytest.approx(1.21, abs=1e-9)

    def test_leere_fenster_werden_uebersprungen(self) -> None:
        leer = FakeFenster(result=FakeResult(pd.DataFrame({"time": [], "equity": []})))

        assert verkettete_kurve(bericht(leer)).empty


class TestRollierendeJahre:
    def test_am_kalender_gerechnet_nicht_an_indizes(self) -> None:
        """**Der Unterschied, um dessentwillen es diese Funktion gibt.**

        Die Kurve hat hier absichtlich ungleiche Punktdichte: erst taeglich,
        dann woechentlich. Eine Rechnung ueber Indizes wuerde im dichten Teil
        zu kurze und im duennen Teil zu lange Zeitraeume vergleichen.
        """
        dicht = pd.date_range("2019-01-01", periods=400, freq="D", tz="UTC")
        duenn = pd.date_range("2020-02-10", periods=60, freq="7D", tz="UTC")
        index = dicht.append(duenn)
        kurve = pd.Series(np.linspace(1.0, 2.0, len(index)), index=index)

        fenster = rollierende_jahre(kurve)

        assert not fenster.empty
        spannen = (fenster["ende"] - fenster["start"]).dt.days
        # Jedes Fenster deckt rund zwoelf Monate ab - keines deutlich weniger.
        assert spannen.min() >= 350
        assert spannen.max() <= 372

    def test_zu_kurze_kurve_gibt_nichts(self) -> None:
        kurz = pd.Series(
            [1.0, 1.1, 1.2],
            index=pd.date_range("2019-01-01", periods=3, freq="D", tz="UTC"),
        )

        assert rollierende_jahre(kurz).empty


class TestUrteil:
    def _bild(self, renditen: list[float], *, schwelle: float = -10.0) -> Jahresbild:
        start = pd.date_range("2019-01-01", periods=len(renditen), freq="D", tz="UTC")
        return Jahresbild(
            schwelle_pct=schwelle,
            fenster=pd.DataFrame(
                {
                    "start": start,
                    "ende": start + pd.DateOffset(months=12),
                    "rendite_pct": renditen,
                }
            ),
            index_wert=min(renditen),
        )

    def test_spitze_und_hochebene_werden_unterschieden(self) -> None:
        """**Der Zweck des Ganzen.** Dieselbe Gate-Zahl, zwei Lagen."""
        spitze = self._bild([-12.0] + [5.0] * 199)
        hochebene = self._bild([-12.0] * 60 + [5.0] * 140)

        assert "Spitze" in spitze.urteil()
        assert "Hochebene" in hochebene.urteil()
        assert spitze.schlechtestes == hochebene.schlechtestes

    def test_keins_darunter_wird_als_bestanden_gemeldet(self) -> None:
        bild = self._bild([1.0, 2.0, 3.0])

        assert bild.darunter == 0
        assert "besteht" in bild.urteil()

    def test_das_zweitschlechteste_ueberlappt_nicht(self) -> None:
        """**Ohne diese Bedingung ist es derselbe Einbruch, einen Tag versetzt.**

        Benachbarte Zwoelfmonatsfenster teilen sich fast alle Tage. Das
        zweitschlechteste waere dann immer knapp neben dem schlechtesten - und
        jede Spitze saehe aus wie eine Hochebene.
        """
        bild = self._bild([-12.0, -11.9, -11.8] + [5.0] * 500)

        assert bild._zweites() == pytest.approx(5.0)

    def test_ohne_getrenntes_fenster_gibt_es_keine_zweite_zahl(self) -> None:
        bild = self._bild([-12.0, -11.0])

        assert not np.isfinite(bild._zweites())


class TestZerlegung:
    def test_die_trades_des_schlechtesten_fensters_kommen_mit(self) -> None:
        r = bericht(
            stueck("2019-01-01", 200, 1.30),
            stueck("2019-07-20", 200, 0.80),
            stueck("2020-02-05", 200, 1.30),
        )
        trades = [
            FakeTrade(datetime(2019, 3, 1, tzinfo=UTC), "BTCUSDT", 2.0),
            FakeTrade(datetime(2019, 10, 1, tzinfo=UTC), "BTCUSDT", -1.4),
            FakeTrade(datetime(2019, 11, 1, tzinfo=UTC), "ETHUSDT", -1.1),
            FakeTrade(datetime(2019, 11, 2, tzinfo=UTC), "ETHUSDT", None),
        ]

        bild = zerlege(r, trades, schwelle_pct=-10.0, index_wert=-9.0)
        wann = bild.zeitraum

        assert wann is not None
        namen = {b.zeit for b in bild.beitraege}
        assert all(wann[0] <= z <= wann[1] for z in namen)
        # Ein Trade ohne Ergebnis traegt nichts bei und darf nicht auftauchen.
        assert len(bild.beitraege) <= 3

    def test_die_abweichung_zur_indexrechnung_wird_ausgewiesen(self) -> None:
        """Die Zahl des Gates und die am Kalender stehen nebeneinander. Sind
        sie gleich, ist auch das ein Ergebnis - und zwar eines, das man sehen
        koennen muss."""
        r = bericht(stueck("2019-01-01", 400, 0.85), stueck("2020-02-05", 200, 1.10))

        bild = zerlege(r, [], schwelle_pct=-10.0, index_wert=-7.5)

        assert np.isfinite(bild.abweichung)
        assert bild.abweichung == pytest.approx(bild.schlechtestes + 7.5)

    def test_ohne_fenster_kein_urteil(self) -> None:
        bild = zerlege(bericht(), [], schwelle_pct=-10.0, index_wert=float("nan"))

        assert "Nicht beurteilbar" in bild.urteil()
        assert "nichts zu zerlegen" in bild.tabelle()
