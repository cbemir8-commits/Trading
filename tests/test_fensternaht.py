"""Die Naht zwischen zwei Walk-Forward-Fenstern - Befund 315.

Was hier haengt
---------------
``_combine`` klebt die Fensterkurven zu **einer** Kapitalkurve zusammen, und
drei Gates lesen genau diese Kurve: Drawdown, Schlechtestes Jahr und
Monte-Carlo. Der Drawdown hat davon noch 1,36 Punkte Reserve (Befund 162),
'Schlechtestes Jahr' ist bereits gerissen. Ein Sprung an einer Fenstergrenze
saehe fuer alle drei aus wie eine Kursbewegung.

Die Zusage, die das traegt
--------------------------
``_run_window`` laesst den Backtest bei ``run_start = test_start -
warmup_bars * bar_step`` beginnen, und die Engine faengt bei Zeile
``max(warmup_bars, 1)`` an zu handeln. Der erste handelbare Balken eines
Fensters **ist** damit ``test_start``: Waehrend der Aufwaermphase kann nichts
eroeffnet werden, und die Kurve steht bei Testbeginn noch auf dem
Anfangskapital.

Nachgemessen auf echten Tageskerzen (BTC + ETH, 32 Fenster): **alle 32**
beginnen exakt bei 500,0000. Die Naht ist heute zu.

Warum es trotzdem einen Test braucht
------------------------------------
Die Zusage steht in **zwei** Dateien. ``backtest/walkforward.py`` rechnet den
Zeitversatz, ``backtest/engine.py`` den Zeilenversatz - und beide muessen
dieselbe Aufwaermphase gleich meinen. In diesem Projekt sind zwei Stellen
mit derselben Regel schon mehrfach auseinandergelaufen.

Faellt die Zusage, oeffnet sich der Sprung an **jeder** Grenze zugleich, und
nichts meldet es: Ein Drawdown ist keine Fehlermeldung. Seit Befund 315
normiert ``_combine`` deshalb auf den eigenen Startwert des Fensters statt
auf das Anfangskapital - die Kette ist dann stetig, ohne die Zusage zu
brauchen. **An den Zahlen aendert das nichts**, solange die Zusage gilt; auf
echten Daten sind alle elf Gates bitgleich.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest

from backtest.walkforward import _combine

START = Decimal("500")


def kurve(
    index: int, *, beginnt_bei: float, endet_bei: float, punkte: int = 5
) -> pd.DataFrame:
    """Eine Fensterkurve, die von A nach B laeuft."""
    beginn = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=index * 30)
    schritte = [
        beginnt_bei + (endet_bei - beginnt_bei) * i / (punkte - 1)
        for i in range(punkte)
    ]
    return pd.DataFrame(
        {
            "time": [beginn + timedelta(days=i) for i in range(punkte)],
            "equity": schritte,
        }
    )


def fenster(index: int, *, beginnt_bei: float, endet_bei: float):
    beginn = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=index * 30)
    return SimpleNamespace(
        window=SimpleNamespace(test_start=beginn),
        trades=[],
        result=SimpleNamespace(
            equity_curve=kurve(index, beginnt_bei=beginnt_bei, endet_bei=endet_bei)
        ),
    )


def naehte(kurve_gesamt: pd.DataFrame, *, je_fenster: int) -> list[float]:
    """Die relativen Spruenge an den Fenstergrenzen."""
    werte = kurve_gesamt["equity"].to_numpy(dtype=float)
    ergebnis = []
    for grenze in range(je_fenster, len(werte), je_fenster):
        davor, danach = werte[grenze - 1], werte[grenze]
        ergebnis.append(danach / davor - 1 if davor else 0.0)
    return ergebnis


# ---------------------------------------------------------------------------
#  Die Kette ist stetig - auch wenn die Zusage faellt
# ---------------------------------------------------------------------------
class TestDieNahtBleibtZu:
    def test_bei_gehaltener_zusage_ist_sie_zu(self) -> None:
        """Der Normalfall: Jedes Fenster beginnt auf dem Anfangskapital."""
        fenster_liste = [
            fenster(0, beginnt_bei=500.0, endet_bei=600.0),
            fenster(1, beginnt_bei=500.0, endet_bei=550.0),
        ]

        ergebnis = _combine(fenster_liste, START)

        # 500 -> 600 -> 660: +32 %, und keine Naht dazwischen.
        assert ergebnis.total_return_pct == pytest.approx(32.0, abs=0.01)

    def test_auch_wenn_ein_fenster_nicht_auf_dem_startkapital_beginnt(self) -> None:
        """**Der eigentliche Test.** Faellt die Zusage aus zwei Dateien, darf
        die Kette trotzdem keinen Sprung bekommen.

        Das zweite Fenster beginnt hier bei 560 statt 500 - so, als haette
        die Aufwaermphase schon gehandelt. Mit der alten Normierung auf das
        Anfangskapital saesse an der Grenze ein Sprung von +12 %, den drei
        Gates als Kursbewegung lesen wuerden.
        """
        fenster_liste = [
            fenster(0, beginnt_bei=500.0, endet_bei=600.0),
            fenster(1, beginnt_bei=560.0, endet_bei=560.0),
        ]

        gesamt = _combine(fenster_liste, START)

        # Das zweite Fenster ist in sich flach (560 -> 560), traegt also
        # nichts bei: 500 -> 600, und sonst nichts.
        assert gesamt.total_return_pct == pytest.approx(20.0, abs=0.01)

    def test_die_alte_formel_haette_hier_gesprungen(self) -> None:
        """**Die Gegenprobe, damit der Test oben Zaehne hat.**

        Ohne sie liesse sich nicht sagen, ob er eine Gefahr abwehrt oder nur
        eine Selbstverstaendlichkeit feststellt.
        """
        zweites = kurve(1, beginnt_bei=560.0, endet_bei=560.0)
        alt = 600.0 * (float(zweites["equity"].iloc[0]) / float(START))
        neu = 600.0 * (
            float(zweites["equity"].iloc[0]) / float(zweites["equity"].iloc[0])
        )

        assert alt == pytest.approx(672.0), "die alte Formel sprang auf 672"
        assert neu == pytest.approx(600.0), "die neue bleibt bei 600"

    def test_ein_gefallenes_konto_bleibt_gefallen(self) -> None:
        """Die Eigenschaft aus dem Drawdown-1005-%-Fehler bleibt: Wer auf
        null faellt, erholt sich nicht durch das naechste Fenster."""
        fenster_liste = [
            fenster(0, beginnt_bei=500.0, endet_bei=0.0),
            fenster(1, beginnt_bei=500.0, endet_bei=1000.0),
        ]

        ergebnis = _combine(fenster_liste, START)

        assert ergebnis.total_return_pct == pytest.approx(-100.0, abs=0.01)
        assert ergebnis.max_drawdown_pct <= 100.0


class TestDieZahlenBleibenDieselben:
    """**Die Zeile, die diese Aenderung von einer Aenderung trennt.**

    Solange die Zusage gilt - jedes Fenster beginnt auf dem Anfangskapital -,
    rechnen alte und neue Normierung dasselbe.
    """

    @pytest.mark.parametrize(
        "enden", [(600.0, 550.0), (400.0, 700.0), (500.0, 500.0), (250.0, 250.0)]
    )
    def test_bei_gehaltener_zusage_rechnet_sie_dasselbe(
        self, enden: tuple[float, float]
    ) -> None:
        fenster_liste = [
            fenster(0, beginnt_bei=500.0, endet_bei=enden[0]),
            fenster(1, beginnt_bei=500.0, endet_bei=enden[1]),
        ]

        gesamt = _combine(fenster_liste, START)

        # Von Hand nachgerechnet, ohne ``_combine``: Faktor mal Faktor.
        erwartet = (enden[0] / 500.0) * (enden[1] / 500.0) * 100 - 100
        assert gesamt.total_return_pct == pytest.approx(erwartet, abs=0.01)


# ---------------------------------------------------------------------------
#  Die Zusage selbst
# ---------------------------------------------------------------------------
class TestDieZusageStehtInZweiDateien:
    """Sie gilt heute. Diese Tests halten fest, **woran** sie haengt - damit
    ein Umbau an einer der beiden Stellen auffaellt."""

    def test_die_engine_beginnt_bei_der_aufwaermphase(self) -> None:
        import inspect

        from backtest import engine

        quelle = inspect.getsource(engine.Backtester.run)

        assert "start = max(strategy.warmup_bars, 1)" in quelle

    def test_das_fenster_setzt_denselben_versatz_davor(self) -> None:
        import inspect

        from backtest import walkforward

        quelle = inspect.getsource(walkforward._run_window)

        assert "run_start = window.test_start - bar_step * warmup_bars" in quelle

    def test_der_versatz_trifft_den_testbeginn(self) -> None:
        """Beide zusammen gerechnet: Zeile ``warmup_bars`` des Fensterrahmens
        ist genau ``test_start``.

        Auf einer Reihe **ohne Luecken**; mit Luecken faellt sie spaeter, und
        das ist die harmlose Richtung.
        """
        warmup = 201
        schritt = timedelta(days=1)
        test_start = datetime(2020, 1, 1, tzinfo=UTC)
        run_start = test_start - schritt * warmup

        zeilen = [run_start + schritt * i for i in range(warmup + 5)]

        assert zeilen[warmup] == test_start

    def test_combine_braucht_die_zusage_nicht_mehr(self) -> None:
        """Und der Grund, warum die drei Tests darueber eine Wache sind und
        keine Bedingung: Faellt die Zusage, bleibt die Kette trotzdem
        stetig."""
        import inspect

        from backtest import walkforward

        quelle = inspect.getsource(walkforward._combine)

        assert 'basis = float(curve["equity"].iloc[0])' in quelle
        assert 'factor = curve["equity"] / basis' in quelle


class TestAnEchtenFenstern:
    """Die Zusage nicht am Quelltext, sondern am Lauf - so, wie sie auf
    echten Tageskerzen gemessen wurde (32 von 32 Fenstern bei 500,0000)."""

    def test_jedes_fenster_beginnt_auf_dem_anfangskapital(self) -> None:
        """**Die Zusage in ihrer pruefbaren Form.**

        Kann waehrend der Aufwaermphase eine Position eroeffnet werden,
        steht die Kurve bei Testbeginn nicht mehr auf dem Anfangskapital -
        und genau das faellt hier auf, an welcher der beiden Dateien es
        auch liegt.
        """
        from backtest.walkforward import WalkForwardSplitter, _run_window
        from strategy.compiler import compile_genome

        frame = _tageskerzen(1400)
        config = _konfig()
        genome = _trendfolger()
        fenster_liste = WalkForwardSplitter(train_months=12, test_months=3).split(
            frame["open_time"].iloc[0].to_pydatetime(),
            frame["open_time"].iloc[-1].to_pydatetime(),
        )
        assert len(fenster_liste) >= 3, "zu wenige Fenster, der Test prueft nichts"

        geprueft = 0
        for w in fenster_liste:
            ergebnis = _run_window(frame, compile_genome(genome), config, w, None)
            if ergebnis is None or ergebnis.result.equity_curve.empty:
                continue
            kurve_f = ergebnis.result.equity_curve
            ab_test = kurve_f.loc[kurve_f["time"] >= pd.Timestamp(w.test_start)]
            if ab_test.empty:
                continue
            geprueft += 1
            assert float(ab_test["equity"].iloc[0]) == pytest.approx(
                float(config.initial_equity), abs=1e-9
            ), f"Fenster {w.index} beginnt nicht auf dem Anfangskapital"

        assert geprueft >= 3, "kein Fenster geprueft"


def _tageskerzen(anzahl: int, seed: int = 7) -> pd.DataFrame:
    """Tageskerzen mit wechselnder Drift - dieselbe Bauart wie in
    ``test_nachlauf``: Auf reinem Rauschen liefe jede Position sofort in den
    Stop, und die Aufwaermphase haette nichts zu tun."""
    import numpy as np

    from core.models import Candle, Interval
    from data.store import candles_to_frame

    t0 = datetime(2018, 1, 1, tzinfo=UTC)
    rng = np.random.default_rng(seed)
    drift = np.repeat(rng.normal(0.0, 90.0, anzahl // 90 + 1), 90)[:anzahl]
    closes = np.maximum(20_000 + np.cumsum(drift + rng.normal(0, 240, anzahl)), 2_000)

    kerzen = []
    for i in range(anzahl):
        close = closes[i]
        offen = closes[i - 1] if i else close
        spanne = abs(rng.normal(0, 110))
        kerzen.append(
            Candle(
                open_time=t0 + Interval.D1.duration * i,
                open=Decimal(f"{offen:.1f}"),
                high=Decimal(f"{max(offen, close) + spanne:.1f}"),
                low=Decimal(f"{min(offen, close) - spanne:.1f}"),
                close=Decimal(f"{close:.1f}"),
                volume=Decimal("10"),
                turnover=Decimal("100000"),
            )
        )
    return candles_to_frame(kerzen)


def _konfig():
    from backtest.engine import BacktestConfig
    from core.config import RiskSettings
    from core.models import Instrument

    return BacktestConfig(
        instrument=Instrument(
            symbol="BTCUSDT", category="linear", base_coin="BTC", quote_coin="USDT",
            tick_size=Decimal("0.01"), qty_step=Decimal("0.001"),
            min_order_qty=Decimal("0.001"), max_order_qty=Decimal("100000"),
            min_notional=Decimal("5"), max_leverage=Decimal("100"),
            maintenance_margin_rate=Decimal("0.005"),
        ),
        risk=RiskSettings(),
        initial_equity=Decimal("10000"),
        enforce_risk_limits=False,
    )


def _trendfolger():
    from strategy.genome import (
        Condition,
        Genome,
        Operand,
        Operator,
        SizingSpec,
        StopSpec,
        TargetSpec,
    )

    return Genome(
        name="Trend 50 fuer die Fensternaht",
        rationale="Long ueber dem 50er-Schnitt, raus darunter.",
        entry_long=[
            Condition(
                left=Operand(kind="price", name="close"),
                op=Operator.CROSS_ABOVE,
                right=Operand(kind="indicator", name="sma", params={"period": 50}),
            )
        ],
        exit_long=[
            Condition(
                left=Operand(kind="price", name="close"),
                op=Operator.LT,
                right=Operand(kind="indicator", name="sma", params={"period": 50}),
            )
        ],
        stop=StopSpec(kind="percent", percent=12.0),
        targets=[TargetSpec(rr=10.0, portion=1.0)],
        sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        cooldown_bars=0,
        max_hold_bars=0,
    )
