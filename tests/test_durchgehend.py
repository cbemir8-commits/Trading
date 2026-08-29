"""Der durchgehende Lauf - Positionen ueberleben die Fenstergrenze.

Der Nachlauf hat das eine Fensterende geheilt. Am anderen blieb der groessere
Schaden: Jedes Fenster ist ein eigener Backtest und beginnt **flach**. Fuer
eine Trendfolge ist das ruinoes, weil ihr Einstieg ein *Kreuzen* verlangt - wer
beim Fensterstart schon im Trend ist, bekommt kein Signal mehr. Gemessen auf
BTC + ETH ueber 62 Fenster:

    Start ueber dem 50-Tage-Schnitt        31 von 62  (50 %)
    Wartezeit bis zum naechsten Kreuzen    Median 44 von 89 Tagen
    Fenster, die komplett aussetzen         4
    Testtage ohne Position, obwohl die
    Regel investiert waere                 26,3 %

**Diese Zahlen sind vor Befund 151 gemessen**, als der Nachlauf eine
Fensterlaenge lang war. Seit er vier lang ist, laufen beide Wege auf den
Reihen dieser Datei **gleich** - der Unterschied, den der aeltere Test hier
zeigte, war ein abgeschnittener Trade und kein verpasster Einstieg. Ob von den
26,3 % etwas uebrig bleibt, ist nicht nachgemessen; solange das offen ist,
traegt der durchgehende Lauf hier nur noch die Ueberlappung.

Drei Tests tragen die Datei:

* ``test_positionen_ueberlappen_sich_nicht_mehr`` - die Sache selbst.
* ``test_kein_fenster_rechnet_den_alten_gewinn_noch_einmal`` - der
  Entwurfsfehler, in den ich beim Bauen hineingelaufen bin. Der Gewinn kommt
  aus der Kapitalkurve; wer als Bezug das Startkapital nimmt statt des
  Kontostands bei Fensterbeginn, schreibt jedem Fenster den gesamten
  bisherigen Gewinn noch einmal gut.
* ``test_der_lange_trend_wird_nicht_mehr_abgeschnitten`` - die Wache ueber die
  Nachlauflaenge. Wird sie wieder kuerzer, laufen die beiden Wege auseinander,
  und zwar genau an den kalenderbeendeten Trades.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from itertools import pairwise

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestConfig
from backtest.walkforward import (
    WalkForwardSplitter,
    run_walkforward,
)
from core.config import RiskSettings
from core.models import Candle, Instrument, Interval
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
    """Tageskerzen mit langsam wechselnder Drift - also mit echten Trends."""
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


def _trendkerzen(anzahl: int = 1000) -> pd.DataFrame:
    """Ein langer, ununterbrochener Aufwaertstrend quer ueber die Fenster.

    **Deterministisch, und das ist der Punkt.** Auf einer Zufallsreihe kommt
    der Fall, um den es geht, vielleicht vor und vielleicht nicht - der erste
    Anlauf dieser Datei lief mit einer Reihe, die ihn gar nicht enthielt, und
    beide Wege lieferten dasselbe Ergebnis. Hier steigt der Kurs ab Tag 380
    ununterbrochen, sodass der 50-Tage-Schnitt genau **einmal** gekreuzt wird
    und die Position danach ueber mehrere Fenstergrenzen laufen muesste.
    """
    werte = np.concatenate(
        [
            # Erst eine ruhige Strecke, damit das Training nichts zu holen hat.
            20_000 + 300 * np.sin(np.arange(380) / 12.0),
            # Dann der Trend, der ueber die Fenstergrenzen laeuft.
            20_000 + np.arange(anzahl - 380) * 60.0,
        ]
    )

    kerzen = []
    for i, close in enumerate(werte):
        offen = werte[i - 1] if i else close
        kerzen.append(
            Candle(
                open_time=T0 + Interval.D1.duration * i,
                open=Decimal(f"{offen:.1f}"),
                high=Decimal(f"{max(offen, close) + 40:.1f}"),
                low=Decimal(f"{min(offen, close) - 40:.1f}"),
                close=Decimal(f"{close:.1f}"),
                volume=Decimal("10"),
                turnover=Decimal("100000"),
            )
        )
    return candles_to_frame(kerzen)


def _trendfolger() -> Genome:
    """Einstieg auf **Kreuzen** - genau die Bauform, die am Fensterstart
    aussetzt, wenn der Trend schon laeuft."""
    return Genome(
        name="Trend 50 durchgehend",
        rationale="Rein beim Kreuzen des 50er-Schnitts, raus darunter.",
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


def _lauf(konfig: BacktestConfig, *, durchgehend: bool, kerzen=None):
    genome = _trendfolger()
    return run_walkforward(
        _kerzen() if kerzen is None else kerzen,
        lambda: compile_genome(genome),
        konfig,
        WalkForwardSplitter(train_months=12, test_months=3),
        durchgehend=durchgehend,
    )


class TestGrundverhalten:
    def test_positionen_ueberlappen_sich_nicht_mehr(
        self, konfig: BacktestConfig
    ) -> None:
        """**Die Sache selbst - und die Reparatur eines selbst gebauten Fehlers.**

        Seit dem Nachlauf darf ein Trade ueber sein Fensterende hinauslaufen.
        Das naechste Fenster ist aber ein eigener Backtest, der davon nichts
        weiss und flach startet - er eroeffnet also womoeglich eine **zweite**
        Position, waehrend die erste noch laeuft. Zwei gleichzeitig offene
        Positionen sind doppelte Marktpraesenz, die es so nie gaebe.

        Der durchgehende Lauf hat zu jedem Zeitpunkt genau eine Position - das
        ist hier die Invariante. Wie oft der fensterweise Lauf sie verletzt,
        haengt von den Daten ab und ist auf BTC + ETH gemessen (siehe BEFUND);
        auf einer glatten Trendreihe tritt der Fall gar nicht auf, weil dort
        nie ein zweites Mal gekreuzt wird.
        """
        for kerzen in (_trendkerzen(), _kerzen()):
            durch = _lauf(konfig, durchgehend=True, kerzen=kerzen)
            trades = sorted(durch.all_trades, key=lambda t: t.entry_time)

            assert trades, "Ohne Trades sagt der Test nichts"
            for a, b in pairwise(trades):
                assert b.entry_time >= a.exit_time, (
                    f"Zwei Positionen gleichzeitig offen: {a.trade_id} bis "
                    f"{a.exit_time}, {b.trade_id} ab {b.entry_time}"
                )

    def test_der_lange_trend_wird_nicht_mehr_abgeschnitten(
        self, konfig: BacktestConfig
    ) -> None:
        """**Umgeschrieben in Befund 151, weil er etwas anderes mass, als
        seine Ueberschrift sagte.**

        Er hiess ``test_fensterweise_verpasst_den_laufenden_trend`` und
        verglich die Tage im Markt beider Wege - 402 gegen weniger. Das klang
        nach verpassten Einstiegen. Nachgemessen war es das nicht: Auf dieser
        Reihe eroeffnen **beide** Wege genau einen Trade, es wird gar nichts
        verpasst. Der ganze Unterschied war, dass der fensterweise Trade mit
        ``end_of_data`` endete, weil der Nachlauf von einer Fensterlaenge ihn
        abschnitt.

            Nachlauf   trendkerzen        zufaellige Reihe
                1 x    verschieden        identisch
                       (1 x end_of_data)
                4 x    identisch          identisch

        Damit ist die Sache hier der **Nachlauf**, nicht der durchgehende
        Lauf. Genau das wird jetzt geprueft.

        Was der durchgehende Lauf loest, steht in
        ``test_positionen_ueberlappen_sich_nicht_mehr``: zwei gleichzeitig
        offene Positionen, weil das naechste Fenster flach startet. Die
        26,3 % positionslosen Testtage aus dem Modulkopf sind auf BTC + ETH
        gemessen worden, und zwar **vor** der Verlaengerung - sie gehoeren
        nachgemessen.
        """
        for kerzen in (_trendkerzen(), _kerzen()):
            fenster = _lauf(konfig, durchgehend=False, kerzen=kerzen)
            durch = _lauf(konfig, durchgehend=True, kerzen=kerzen)

            assert fenster.all_trades, "Ohne Trades sagt der Test nichts"
            assert all(
                t.exit_reason != "end_of_data" for t in fenster.all_trades
            ), "der Nachlauf reicht nicht mehr bis zum Ausstieg nach Regel"

            def schluessel(bericht):
                return sorted(
                    (t.entry_time, t.exit_time, str(t.exit_reason))
                    for t in bericht.all_trades
                )

            assert schluessel(durch) == schluessel(fenster), (
                "mit ausreichendem Nachlauf laufen beide Wege auf diesen "
                "Reihen gleich - weicht das ab, ist der Nachlauf zu kurz"
            )

    def test_beide_wege_liefern_dieselben_fenster(
        self, konfig: BacktestConfig
    ) -> None:
        durch = _lauf(konfig, durchgehend=True)
        fenster = _lauf(konfig, durchgehend=False)

        assert [w.window.index for w in durch.windows] == [
            w.window.index for w in fenster.windows
        ]

    def test_kein_trade_vor_dem_ersten_testfenster(
        self, konfig: BacktestConfig
    ) -> None:
        """Vor dem Testzeitraum hat das Konto keine Geschichte."""
        durch = _lauf(konfig, durchgehend=True)
        erster = min(w.window.test_start for w in durch.windows)

        assert all(t.entry_time >= erster for t in durch.all_trades)

    def test_jeder_trade_gehoert_zu_genau_einem_fenster(
        self, konfig: BacktestConfig
    ) -> None:
        """Sonst zaehlten benachbarte Fenster dieselbe Beobachtung doppelt."""
        durch = _lauf(konfig, durchgehend=True)

        kennungen = [t.trade_id for t in durch.all_trades]

        assert len(kennungen) == len(set(kennungen))
        for w in durch.windows:
            for t in w.trades:
                assert w.window.test_start <= t.entry_time < w.window.test_end


class TestKennzahlen:
    def test_kein_fenster_rechnet_den_alten_gewinn_noch_einmal(
        self, konfig: BacktestConfig
    ) -> None:
        """**Der Entwurfsfehler, in den ich hineingelaufen bin.**

        ``compute_metrics`` bildet den Gewinn aus der Kapitalkurve:
        ``Endstand - Anfangswert``. Als Anfangswert das Startkapital zu nehmen
        waere im fensterweisen Lauf richtig, wo jedes Fenster dort beginnt -
        im durchgehenden Lauf schriebe es jedem Fenster den gesamten bisher
        aufgelaufenen Gewinn noch einmal gut.

        Geprueft wird der Bezug direkt: Der Gewinn eines Fensters muss genau
        die Bewegung **seiner eigenen** Kapitalkurve sein.
        """
        durch = _lauf(konfig, durchgehend=True)

        assert durch.windows, "Ohne Fenster sagt der Test nichts"
        for w in durch.windows:
            kurve = w.result.equity_curve
            eigene = float(kurve["equity"].iloc[-1]) - float(kurve["equity"].iloc[0])

            assert w.metrics.net_profit == pytest.approx(eigene, rel=1e-9)

    def test_fenstergewinne_fuegen_sich_zum_ganzen(
        self, konfig: BacktestConfig
    ) -> None:
        """Die Gegenprobe auf derselben Sache - diesmal ueber alle Fenster.

        Exakt aufgehen kann es nicht: Zwischen dem letzten Punkt eines
        Fensters und dem ersten des naechsten liegt eine Kerze, deren Bewegung
        keinem Fenster zugeordnet ist. Ein **Vielfaches** darf dabei aber nie
        herauskommen - das waere der Fehler oben.
        """
        durch = _lauf(konfig, durchgehend=True)

        assert durch.combined is not None
        summe = sum(w.metrics.net_profit for w in durch.windows)
        ganz = durch.combined.net_profit

        assert abs(summe - ganz) < 0.25 * max(abs(ganz), 1.0)

    def test_gesamtkurve_beginnt_beim_startkapital(
        self, konfig: BacktestConfig
    ) -> None:
        """Vor dem ersten Testfenster wird nicht gehandelt, also steht dort
        noch genau das Startkapital."""
        durch = _lauf(konfig, durchgehend=True)

        assert durch.combined is not None
        anfang = float(konfig.initial_equity)
        ende = anfang + durch.combined.net_profit

        assert durch.combined.total_return_pct == pytest.approx(
            (ende / anfang - 1) * 100, rel=1e-6
        )

    def test_kapitalkurven_der_fenster_ueberlappen_nicht(
        self, konfig: BacktestConfig
    ) -> None:
        """Sonst zaehlte die Verkettung dieselbe Bewegung zweimal."""
        durch = _lauf(konfig, durchgehend=True)

        for w in durch.windows:
            kurve = w.result.equity_curve
            if kurve.empty:
                continue
            assert kurve["time"].min() >= pd.Timestamp(w.window.test_start)
            assert kurve["time"].max() < pd.Timestamp(w.window.test_end)

    def test_keine_kalenderausstiege(self, konfig: BacktestConfig) -> None:
        """Der Nachlauf gilt auch hier - am Ende der ganzen Strecke."""
        durch = _lauf(konfig, durchgehend=True)

        assert durch.kalender_ausstiege == 0


class TestSchutz:
    def test_wechselnde_regel_wird_abgelehnt(self, konfig: BacktestConfig) -> None:
        """**Kein stilles Umgehen.**

        Eine Position ueber die Fenstergrenze zu tragen hiesse, sie unter einer
        Regel zu eroeffnen und unter einer anderen zu schliessen. Das ist keine
        Kleinigkeit, die man im Hintergrund glaettet - der Aufruf ist falsch
        und wird zurueckgewiesen.
        """
        genome = _trendfolger()

        with pytest.raises(ValueError, match="strategie_je_fenster"):
            run_walkforward(
                _kerzen(),
                lambda: compile_genome(genome),
                konfig,
                WalkForwardSplitter(train_months=12, test_months=3),
                strategie_je_fenster=lambda w: compile_genome(genome),
                durchgehend=True,
            )

    def test_leerer_rahmen(self, konfig: BacktestConfig) -> None:
        bericht = run_walkforward(
            pd.DataFrame(),
            lambda: compile_genome(_trendfolger()),
            konfig,
            WalkForwardSplitter(),
            durchgehend=True,
        )

        assert bericht.windows == []


def test_ohne_trendlage_bleibt_alles_beim_alten(konfig: BacktestConfig) -> None:
    """Der Umbau darf nur dort wirken, wo er soll.

    Wo keine Position eine Fenstergrenze ueberspannt, muessen beide Wege
    dieselben Trades liefern. Genau das war beim ersten Anlauf dieser Datei
    der Fall - damals unbemerkt, weil die Zufallsreihe den Mechanismus gar
    nicht ausloeste. Jetzt steht es als Aussage da statt als Zufall.
    """
    durch = _lauf(konfig, durchgehend=True)
    fenster = _lauf(konfig, durchgehend=False)

    starts = [w.window.test_start for w in durch.windows]
    ueberspannt = any(
        t.entry_time < s <= t.exit_time for t in durch.all_trades for s in starts
    )

    if not ueberspannt:
        assert [t.entry_time for t in durch.all_trades] == [
            t.entry_time for t in fenster.all_trades
        ]
