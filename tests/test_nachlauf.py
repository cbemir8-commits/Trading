"""Der Nachlauf am Fensterende - und warum ohne ihn der Kalender mitmisst.

Der teuerste Befund dieser Datei steht nicht im Code, sondern in der Messung,
die ihn ausgeloest hat. Auf dem Spitzenkandidaten (BTC + ETH, Tageskerzen):

    am Kalender beendet    25 Trades   +19,62 EUR im Mittel   26 Tage gehalten
    nach Regel beendet    129 Trades   -0,59 bis -2,11 EUR     6 Tage gehalten

**Die 25 kalenderbeendeten Trades trugen den gesamten Vorteil.** Ohne sie
faellt der Sharpe je Trade von 0,244 auf 0,021. Gemessen wurde also zu einem
Sechstel der Kalender - und zwar genau an der Stelle, an der eine Trendfolge
ihr Geld verdient: beim Ausstieg aus den Gewinnern. Im Betrieb gibt es keinen
Kalender, der eine Position schliesst.

Zwei Tests tragen die Datei:

* ``test_ohne_nachlauf_beendet_der_kalender`` - der Umkehr-Nachweis. Wer den
  Nachlauf entfernt, bekommt die kalenderbeendeten Trades zurueck.
* ``test_nachlauf_verschiebt_keinen_einstieg`` - die Unbedenklichkeit. Mehr
  Daten hinter dem Fenster duerfen keine einzige Einstiegsentscheidung
  aendern, sonst waere der Nachlauf ein Blick in die Zukunft.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestConfig
from backtest.walkforward import (
    NACHLAUF_FENSTER,
    WalkForwardReport,
    WalkForwardSplitter,
    _run_window,
    nachlauf_fuer,
    run_walkforward,
)
from core.config import RiskSettings
from core.models import Candle, Instrument, Interval, Side, Trade
from data.store import candles_to_frame
from strategy.compiler import compile_genome
from strategy.genome import (
    Condition,
    Genome,
    Operand,
    Operator,
    SizingSpec,
    StopSpec,
    TargetSpec,
)

T0 = datetime(2020, 1, 1, tzinfo=UTC)


def _kerzen(anzahl: int = 1000, *, seed: int = 11) -> pd.DataFrame:
    """Tageskerzen mit langsam wechselnder Drift.

    Die wechselnde Drift ist der Punkt: Sie erzeugt Phasen, in denen eine
    Trendfolge wochenlang investiert bleibt. Auf reinem Rauschen liefe jede
    Position sofort in den Stop, und der Nachlauf haette nichts zu tun - der
    Test waere gruen und wertlos.
    """
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
                open_time=T0 + Interval.D1.duration * i,
                open=Decimal(f"{offen:.1f}"),
                high=Decimal(f"{max(offen, close) + spanne:.1f}"),
                low=Decimal(f"{min(offen, close) - spanne:.1f}"),
                close=Decimal(f"{close:.1f}"),
                volume=Decimal("10"),
                turnover=Decimal("100000"),
            )
        )
    return candles_to_frame(kerzen)


def _trendfolger() -> Genome:
    """Rein ueber dem 50er-Schnitt, raus darunter.

    Weiter Stop und weit entferntes Ziel, damit eine Position ueberwiegend
    durch das Ausstiegssignal endet - oder eben durch das Datenende. Genau
    dieser Unterschied wird hier gemessen.
    """
    return Genome(
        name="Trend 50 fuer den Nachlauf",
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


@pytest.fixture
def konfig() -> BacktestConfig:
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


def _fenster(frame: pd.DataFrame):
    return WalkForwardSplitter(train_months=12, test_months=3).split(
        frame["open_time"].iloc[0].to_pydatetime(),
        frame["open_time"].iloc[-1].to_pydatetime(),
    )


def _lauf(nachlauf: timedelta, frame: pd.DataFrame, config: BacktestConfig):
    genome = _trendfolger()
    trades: list[Trade] = []
    for w in _fenster(frame):
        ergebnis = _run_window(
            frame, compile_genome(genome), config, w, None, nachlauf=nachlauf
        )
        if ergebnis is not None:
            trades.extend(ergebnis.trades)
    return trades


class TestNachlaufLaenge:
    def test_vier_testfensterlaengen(self) -> None:
        """An die Fensterlaenge gebunden, nicht an feste Tage.

        Auf 15-Minuten-Kerzen waere ein Jahr Nachlauf je Fenster ein
        Vielfaches der Testdaten selbst.
        """
        for w in WalkForwardSplitter(train_months=12, test_months=3).split(
            datetime(2020, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)
        ):
            assert nachlauf_fuer(w) == (w.test_end - w.test_start) * 4
            assert timedelta(days=352) <= nachlauf_fuer(w) <= timedelta(days=372)

    def test_kurze_testfenster_bekommen_kurzen_nachlauf(self) -> None:
        fenster = WalkForwardSplitter(train_months=6, test_months=1).split(
            datetime(2020, 1, 1, tzinfo=UTC), datetime(2022, 1, 1, tzinfo=UTC)
        )

        assert fenster
        assert all(nachlauf_fuer(w) <= timedelta(days=124) for w in fenster)

    def test_eine_fensterlaenge_genuegte_nur_der_einen_regel(self) -> None:
        """**Der Grund fuer die 4** (Befund 151).

        Befund 22 hat die Laenge an einer Regel kalibriert, die im Mittel
        sechs Tage haelt. Ueber den ganzen Tageskerzen-Katalog gemessen waren
        bei einer Fensterlaenge **12 von 24 Regeln** betroffen, zusammen 103
        Trades; am schwersten ``Trend-Beteiligung 200 Tage`` mit 10 von 53.

        Faellt dieser Test um, ist die Verlaengerung verlorengegangen und der
        Fehler aus Befund 22 fuer lang haltende Regeln zurueck.
        """
        assert NACHLAUF_FENSTER == 4

        w = WalkForwardSplitter(train_months=12, test_months=3).split(
            datetime(2020, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)
        )[0]
        assert nachlauf_fuer(w) > w.test_end - w.test_start

    def test_die_leiter_steht_im_kopf(self) -> None:
        """Die Katalog-Leiter ist die Begruendung - sie gehoert dokumentiert,
        sonst sieht die 4 wie eine gewaehlte Zahl aus."""
        kopf = nachlauf_fuer.__doc__ or ""

        assert "12 von 24" in kopf, "wie viele Regeln bei 1x betroffen waren"
        assert "103" in kopf, "und wie viele Trades"
        assert "Serienende" in kopf, "der Boden von 2 und woher er kommt"


def _trade(kennung: str, grund: str) -> Trade:
    return Trade(
        trade_id=kennung,
        symbol="BTCUSDT",
        side=Side.BUY,
        strategy_id="t",
        entry_time=datetime(2021, 1, 1, tzinfo=UTC),
        entry_price=Decimal("30000"),
        exit_time=datetime(2021, 2, 1, tzinfo=UTC),
        exit_price=Decimal("31000"),
        qty=Decimal("0.01"),
        gross_pnl=Decimal("10"),
        fees=Decimal("1"),
        stop_loss=Decimal("29000"),
        exit_reason=grund,
    )


class TestKalenderausstiege:
    def test_bericht_zaehlt_sie(self) -> None:
        """Damit sie nie wieder unbemerkt bleiben."""
        report = WalkForwardReport()
        report.all_trades = [
            _trade("a", "signal_exit"),
            _trade("b", "end_of_data"),
            _trade("c", "stop_loss"),
            _trade("d", "end_of_data"),
        ]

        assert report.kalender_ausstiege == 2

    def test_sauberer_bericht_zaehlt_null(self) -> None:
        report = WalkForwardReport()
        report.all_trades = [_trade("a", "signal_exit"), _trade("b", "stop_loss")]

        assert report.kalender_ausstiege == 0

    def test_leerer_bericht(self) -> None:
        assert "Walk-Forward ohne Ergebnis" in WalkForwardReport().summary()


class TestWirkung:
    """Die eigentliche Sache - gemessen auf durchgerechneten Kerzen."""

    def test_ohne_nachlauf_beendet_der_kalender(self, konfig: BacktestConfig) -> None:
        """**Der Umkehr-Nachweis.**

        Wer den Nachlauf herausnimmt, bekommt die kalenderbeendeten Trades
        zurueck. Faellt dieser Test um, ist die Korrektur verlorengegangen.
        """
        ohne = _lauf(timedelta(0), _kerzen(), konfig)

        assert ohne, "Ohne Trades sagt der Test nichts"
        assert sum(1 for t in ohne if t.exit_reason == "end_of_data") > 0

    def test_mit_nachlauf_beendet_die_regel(self, konfig: BacktestConfig) -> None:
        mit = _lauf(timedelta(days=91), _kerzen(), konfig)

        assert mit, "Ohne Trades sagt der Test nichts"
        assert all(t.exit_reason != "end_of_data" for t in mit)

    def test_nachlauf_verschiebt_keinen_einstieg(self, konfig: BacktestConfig) -> None:
        """**Die Unbedenklichkeit - und der Grund, warum das kein Blick nach
        vorn ist.**

        Mehr Daten hinter dem Fenster duerfen keine einzige
        Einstiegsentscheidung aendern. Waere es anders, entschiede die Regel
        aus Daten, die es zum Zeitpunkt der Entscheidung noch nicht gab.
        """
        frame = _kerzen()

        ohne = _lauf(timedelta(0), frame, konfig)
        mit = _lauf(timedelta(days=91), frame, konfig)

        assert [t.entry_time for t in ohne] == [t.entry_time for t in mit]
        assert [t.entry_price for t in ohne] == [t.entry_price for t in mit]

    def test_laengerer_nachlauf_aendert_nichts_mehr(
        self, konfig: BacktestConfig
    ) -> None:
        """Konvergenz - die Signatur einer Groesse, die lang genug ist."""
        frame = _kerzen()

        kurz = _lauf(timedelta(days=91), frame, konfig)
        lang = _lauf(timedelta(days=365), frame, konfig)

        assert [t.exit_time for t in kurz] == [t.exit_time for t in lang]
        assert [t.net_pnl for t in kurz] == [t.net_pnl for t in lang]

    def test_keine_trades_aus_dem_nachlauf(self, konfig: BacktestConfig) -> None:
        """**Die obere Schranke, die es vorher nicht brauchte.**

        Ohne Nachlauf endeten die Daten am Fensterende, ein Einstieg danach
        war unmoeglich. Mit Nachlauf ist er es nicht - fehlte die Schranke,
        zaehlten benachbarte Fenster dieselben Trades doppelt.
        """
        frame = _kerzen()
        genome = _trendfolger()

        for w in _fenster(frame):
            ergebnis = _run_window(
                frame, compile_genome(genome), konfig, w, None,
                nachlauf=timedelta(days=91),
            )
            if ergebnis is None:
                continue
            for t in ergebnis.trades:
                assert w.test_start <= t.entry_time < w.test_end

    def test_kapitalkurve_bleibt_im_fenster(self, konfig: BacktestConfig) -> None:
        """Sonst ueberlappten sich die Kurven benachbarter Fenster, und die
        Verkettung zaehlte dieselbe Bewegung zweimal."""
        frame = _kerzen()
        genome = _trendfolger()

        for w in _fenster(frame):
            ergebnis = _run_window(
                frame, compile_genome(genome), konfig, w, None,
                nachlauf=timedelta(days=91),
            )
            if ergebnis is None or ergebnis.result.equity_curve.empty:
                continue
            assert ergebnis.result.equity_curve["time"].max() < pd.Timestamp(w.test_end)


def test_gesamtlauf_bleibt_ohne_kalenderausstiege(konfig: BacktestConfig) -> None:
    """Der ganze Weg durch ``run_walkforward``, so wie ihn die Gates gehen."""
    genome = _trendfolger()

    bericht = run_walkforward(
        _kerzen(),
        lambda: compile_genome(genome),
        konfig,
        WalkForwardSplitter(train_months=12, test_months=3),
    )

    assert bericht.all_trades, "Ohne Trades sagt der Test nichts"
    assert bericht.kalender_ausstiege == 0
