"""Tests fuer den Walk-Forward ueber mehrere Maerkte.

Zwei Fehler sind hier schon passiert und duerfen nicht wiederkommen:

1. Alle Trades trugen dasselbe Symbol, weil der Genome-Compiler fest
   "BTCUSDT" ins Signal schreibt. Die Marktzuordnung war damit weg, ohne
   dass irgendetwas fehlschlug.
2. ``_combine`` liest die Kapitalkurve aus ``window.result``. Wer dort die
   Kurve des ersten Marktes stehen laesst, bekommt das Ergebnis eines
   Einzelmarktes mit den Trades von zweien - plausibel aussehend und falsch.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestConfig, Backtester
from backtest.portfolio_walkforward import (
    _kurven_summieren,
    common_range,
    run_portfolio_walkforward,
)
from backtest.walkforward import WalkForwardSplitter
from core.config import RiskSettings
from core.models import Candle, Instrument, Interval, Side, Trade
from data.store import candles_to_frame
from research.gates import concurrent_groups, gate_monte_carlo
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


def _tage(anzahl: int, *, start: datetime = T0, seed: int = 3) -> pd.DataFrame:
    """Tageskerzen mit leichtem Aufwaertsdrift."""
    rng = np.random.default_rng(seed)
    closes = np.maximum(20_000 + np.cumsum(rng.normal(8, 260, anzahl)), 2_000)
    kerzen = []
    for i in range(anzahl):
        close = closes[i]
        offen = closes[i - 1] if i else close
        spanne = abs(rng.normal(0, 120))
        kerzen.append(
            Candle(
                open_time=start + Interval.D1.duration * i,
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
    return Genome(
        name="Trend 50",
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
        # Groesse als Kapitalanteil, nicht aus der Stop-Distanz.
        #
        # Sonst lehnt der Risk-Officer jedes Signal mit "stop_too_wide" ab:
        # Ein 12-%-Stop bei 0,75 % Risiko je Trade ergibt eine Position, die
        # unter der Mindestmenge liegt. Genau daran ist dieser Test zuerst
        # gescheitert - sieben Signale, null Trades. Die echten Kandidaten
        # arbeiten aus demselben Grund mit Kapitalanteil.
        sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        cooldown_bars=0,
        max_hold_bars=0,
    )


def _instrument(symbol: str) -> Instrument:
    return Instrument(
        symbol=symbol, category="linear", base_coin=symbol[:3], quote_coin="USDT",
        tick_size=Decimal("0.01"), qty_step=Decimal("0.001"),
        min_order_qty=Decimal("0.001"), max_order_qty=Decimal("100000"),
        min_notional=Decimal("5"), max_leverage=Decimal("100"),
        maintenance_margin_rate=Decimal("0.005"),
    )


def _trade(symbol: str, pnl: str, *, tag: int, dauer: int = 3) -> Trade:
    return Trade(
        trade_id=f"{symbol}-{tag}",
        symbol=symbol,
        side=Side.BUY,
        strategy_id="test",
        entry_time=T0 + timedelta(days=tag),
        entry_price=Decimal("20000"),
        exit_time=T0 + timedelta(days=tag + dauer),
        exit_price=Decimal("20000"),
        qty=Decimal("0.01"),
        gross_pnl=Decimal(pnl),
        fees=Decimal("0.1"),
        stop_loss=Decimal("19000"),
    )


class TestGemeinsamerZeitraum:
    def test_schneidet_auf_die_ueberschneidung(self) -> None:
        frames = {
            "lang": _tage(900, start=T0),
            "kurz": _tage(400, start=T0 + timedelta(days=200)),
        }

        geschnitten = common_range(frames)

        assert len({len(f) for f in geschnitten.values()}) == 1
        for f in geschnitten.values():
            assert f["open_time"].iloc[0] == pd.Timestamp(T0 + timedelta(days=200))


class TestZusammenlegen:
    def test_die_kurve_ist_die_summe_nicht_die_erste(self) -> None:
        """Der Fehler, der am leichtesten unbemerkt bleibt.

        Wuerde die Kurve des ersten Marktes durchgereicht, saehe alles normal
        aus - nur waere es das Ergebnis eines Einzelmarktes.
        """
        zeit = pd.date_range(T0, periods=5, freq="D", tz="UTC")
        steigt = pd.DataFrame({"time": zeit, "equity": [500.0, 550, 600, 650, 700]})
        faellt = pd.DataFrame({"time": zeit, "equity": [500.0, 450, 400, 350, 300]})

        summe = _kurven_summieren(
            {"a": steigt, "b": faellt},
            gewichte={"a": 1.0, "b": 1.0}, summe=2.0,
            initial_equity=Decimal("500"),
        )

        # Halbe/halbe aus +40 % und -40 % ergibt am Ende wieder 500.
        assert summe["equity"].iloc[0] == pytest.approx(500.0)
        assert summe["equity"].iloc[-1] == pytest.approx(500.0)

    def test_gewichte_wirken(self) -> None:
        zeit = pd.date_range(T0, periods=3, freq="D", tz="UTC")
        steigt = pd.DataFrame({"time": zeit, "equity": [500.0, 600, 700]})
        flach = pd.DataFrame({"time": zeit, "equity": [500.0, 500, 500]})

        viel = _kurven_summieren(
            {"a": steigt, "b": flach}, gewichte={"a": 3.0, "b": 1.0}, summe=4.0,
            initial_equity=Decimal("500"),
        )
        gleich = _kurven_summieren(
            {"a": steigt, "b": flach}, gewichte={"a": 1.0, "b": 1.0}, summe=2.0,
            initial_equity=Decimal("500"),
        )

        assert viel["equity"].iloc[-1] > gleich["equity"].iloc[-1]

    def test_verschiedene_zeitpunkte_werden_vorwaerts_gefuellt(self) -> None:
        """Ein Markt ohne neue Kerze hat nicht null Kapital, sondern dasselbe."""
        a = pd.DataFrame({
            "time": pd.to_datetime(["2020-01-01", "2020-01-03"], utc=True),
            "equity": [500.0, 600.0],
        })
        b = pd.DataFrame({
            "time": pd.to_datetime(["2020-01-02", "2020-01-03"], utc=True),
            "equity": [500.0, 500.0],
        })

        summe = _kurven_summieren(
            {"a": a, "b": b}, gewichte={"a": 1.0, "b": 1.0}, summe=2.0,
            initial_equity=Decimal("500"),
        )

        assert len(summe) == 3
        assert (summe["equity"] > 0).all()


class TestEchterLauf:
    @pytest.fixture
    def risk(self) -> RiskSettings:
        return RiskSettings()

    def test_beide_maerkte_liefern_trades_mit_eigenem_symbol(
        self, risk: RiskSettings
    ) -> None:
        """Der Fehler, der lange unsichtbar war.

        Der Genome-Compiler schreibt fest "BTCUSDT" ins Signal. Kommt das
        Symbol des Trades von dort, tragen alle Trades beider Maerkte
        dasselbe - und jede Auswertung je Markt ist stillschweigend falsch.
        """
        frames = {"A": _tage(1100, seed=3), "B": _tage(1100, seed=11)}
        configs = {
            "A": BacktestConfig(instrument=_instrument("AAAUSDT"), risk=risk,
                                initial_equity=Decimal("500")),
            "B": BacktestConfig(instrument=_instrument("BBBUSDT"), risk=risk,
                                initial_equity=Decimal("500")),
        }
        genome = _trendfolger()

        report = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs,
            WalkForwardSplitter(train_months=12, test_months=3),
        )

        symbole = {t.symbol for t in report.all_trades}
        assert symbole == {"AAAUSDT", "BBBUSDT"}, (
            f"Marktzuordnung verloren: {symbole}"
        )

    def test_mehr_trades_als_jeder_markt_allein(self, risk: RiskSettings) -> None:
        from backtest.walkforward import run_walkforward

        frames = {"A": _tage(1100, seed=3), "B": _tage(1100, seed=11)}
        configs = {
            "A": BacktestConfig(instrument=_instrument("AAAUSDT"), risk=risk,
                                initial_equity=Decimal("500")),
            "B": BacktestConfig(instrument=_instrument("BBBUSDT"), risk=risk,
                                initial_equity=Decimal("500")),
        }
        genome = _trendfolger()
        splitter = WalkForwardSplitter(train_months=12, test_months=3)

        zusammen = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs, splitter
        )
        einzeln = [
            len(run_walkforward(f, lambda: compile_genome(genome),
                                configs[n], splitter).all_trades)
            for n, f in frames.items()
        ]

        assert len(zusammen.all_trades) == sum(einzeln)

    def test_ohne_maerkte_kommt_ein_leerer_bericht(self) -> None:
        assert run_portfolio_walkforward({}, lambda: None, {}).windows == []


class TestGleichzeitigeTrades:
    def test_ueberlappende_trades_bilden_eine_gruppe(self) -> None:
        trades = [_trade("A", "10", tag=0), _trade("B", "-10", tag=1)]

        assert len(concurrent_groups(trades)) == 1

    def test_getrennte_trades_bleiben_getrennt(self) -> None:
        trades = [_trade("A", "10", tag=0), _trade("B", "-10", tag=20)]

        assert len(concurrent_groups(trades)) == 2

    def test_ueberlappung_ist_transitiv(self) -> None:
        """A ueberlappt B, B ueberlappt C - alle drei waren zusammen offen."""
        trades = [
            _trade("A", "10", tag=0, dauer=4),
            _trade("B", "10", tag=3, dauer=4),
            _trade("C", "10", tag=6, dauer=4),
        ]

        assert len(concurrent_groups(trades)) == 1

    def test_gruppierung_macht_monte_carlo_strenger_nie_milder(self) -> None:
        """Der eigentliche Grund fuer die Gruppierung.

        Zwei gleichzeitige Verluste sind ein Ereignis, kein zweifaches Glueck
        im Ungluecke. Wer sie einzeln vertauscht, zieht sie auseinander und
        bekommt einen zu freundlichen Rueckgang. Diese Richtung muss
        garantiert sein - sonst waere die Gruppierung eine Lockerung.
        """
        from research.gates import GateThresholds

        # Paarweise gleichzeitige Verluste, dazwischen einzelne Gewinne.
        trades: list[Trade] = []
        for i in range(15):
            trades.append(_trade("A", "-30", tag=i * 10, dauer=2))
            trades.append(_trade("B", "-30", tag=i * 10, dauer=2))
            trades.append(_trade("A", "70", tag=i * 10 + 5, dauer=2))

        t = GateThresholds()
        ohne = gate_monte_carlo(trades, Decimal("500"), t, group_concurrent=False)
        mit = gate_monte_carlo(trades, Decimal("500"), t, group_concurrent=True)

        assert mit.value >= ohne.value, (
            f"Gruppierung darf nicht milder sein: {mit.value} < {ohne.value}"
        )

    def test_zu_wenige_zeitraeume_werden_uebersprungen(self) -> None:
        """Lieber "nicht messbar" als eine Zahl aus fuenf Beobachtungen."""
        from research.gates import GateStatus, GateThresholds

        # 30 Trades, die alle ineinandergreifen - also ein einziger Zeitraum.
        trades = [_trade("A", "10", tag=i, dauer=5) for i in range(30)]

        ergebnis = gate_monte_carlo(
            trades, Decimal("500"), GateThresholds(), group_concurrent=True
        )

        assert ergebnis.status is GateStatus.SKIP
        assert "unabhaengige" in ergebnis.message


class TestSymbolKommtVomKontrakt:
    def test_der_trade_traegt_das_symbol_des_instruments(self) -> None:
        """Nicht das aus dem Signal - der Compiler setzt dort fest BTCUSDT."""
        config = BacktestConfig(
            instrument=_instrument("ETHUSDT"),
            risk=RiskSettings(),
            initial_equity=Decimal("500"),
        )
        frame = _tage(400, seed=5)
        genome = _trendfolger()

        result = Backtester(config).run(frame, compile_genome(genome))

        assert result.trades, "der Testaufbau muss Trades erzeugen"
        assert {t.symbol for t in result.trades} == {"ETHUSDT"}


class TestTradesTragenIhrGewicht:
    """Jedes Bein laeuft mit vollem Startkapital, hat im Portfolio aber nur
    seinen Anteil. Die Trades muessen das abbilden.

    **Dieser Fehler hat eine Kennzahl um das Doppelte verfaelscht.** Die
    Kapitalkurve war richtig gewichtet, die Trades nicht - und die
    Monte-Carlo-Simulation liest die Trades. Sie meldete 15,70 % Rueckgang,
    waehrend die Kurve aus denselben Fenstern 8,72 % zeigte. Bei sechs Beinen
    stieg die Meldung auf 62 %, und erst diese unmoegliche Zahl hat den
    Fehler sichtbar gemacht.

    **Die Korrektur macht ein Gate milder.** Deshalb steht hier die Probe,
    dass sie sauber ist: Das R-Vielfache darf sich nicht aendern. Es ist
    Gewinn geteilt durch (Stopabstand mal Menge) - skaliert man beide mit
    demselben Faktor, bleibt es gleich. Waere das nicht so, wuerde die
    Skalierung Kennzahlen verschieben, die sie nicht anfassen darf.
    """

    @pytest.fixture
    def risk(self) -> RiskSettings:
        return RiskSettings()

    def _lauf(self, risk: RiskSettings, beine: int):
        frames = {f"M{i}": _tage(1100, seed=3 + i * 7) for i in range(beine)}
        configs = {
            name: BacktestConfig(
                instrument=_instrument(f"M{i}USDT"), risk=risk,
                initial_equity=Decimal("500"),
            )
            for i, name in enumerate(frames)
        }
        genome = _trendfolger()
        return run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs,
            WalkForwardSplitter(train_months=12, test_months=3),
        )

    def test_bei_einem_bein_bleiben_die_trades_unveraendert(
        self, risk: RiskSettings
    ) -> None:
        """Der Einzelmarktfall darf sich durch die Korrektur nicht aendern."""
        from backtest.walkforward import run_walkforward

        frame = _tage(1100, seed=3)
        config = BacktestConfig(
            instrument=_instrument("M0USDT"), risk=risk, initial_equity=Decimal("500")
        )
        genome = _trendfolger()
        splitter = WalkForwardSplitter(train_months=12, test_months=3)

        allein = run_walkforward(frame, lambda: compile_genome(genome), config, splitter)
        als_portfolio = run_portfolio_walkforward(
            {"M0": frame}, lambda: compile_genome(genome), {"M0": config}, splitter
        )

        assert len(allein.all_trades) == len(als_portfolio.all_trades)
        for a, b in zip(allein.all_trades, als_portfolio.all_trades, strict=True):
            assert a.qty == b.qty
            assert a.net_pnl == b.net_pnl

    def test_zwei_beine_halbieren_die_trades(self, risk: RiskSettings) -> None:
        from backtest.walkforward import run_walkforward

        frames = {f"M{i}": _tage(1100, seed=3 + i * 7) for i in range(2)}
        configs = {
            name: BacktestConfig(
                instrument=_instrument(f"M{i}USDT"), risk=risk,
                initial_equity=Decimal("500"),
            )
            for i, name in enumerate(frames)
        }
        genome = _trendfolger()
        splitter = WalkForwardSplitter(train_months=12, test_months=3)

        einzeln = sum(
            float(t.net_pnl)
            for name, frame in frames.items()
            for t in run_walkforward(
                frame, lambda: compile_genome(genome), configs[name], splitter
            ).all_trades
        )
        portfolio = sum(
            float(t.net_pnl)
            for t in run_portfolio_walkforward(
                frames, lambda: compile_genome(genome), configs, splitter
            ).all_trades
        )

        assert portfolio == pytest.approx(einzeln / 2, rel=0.01), (
            "bei zwei gleich gewichteten Beinen muss jeder Trade halb zaehlen"
        )

    def test_das_r_vielfache_bleibt_unveraendert(self) -> None:
        """Die entscheidende Probe, direkt an der Skalierung.

        R misst am riskierten Betrag: Gewinn geteilt durch (Stopabstand mal
        Menge). Werden Gewinn und Menge mit demselben Faktor skaliert, kuerzt
        er sich heraus. Waere das nicht so, wuerde die Gewichtung Kennzahlen
        verschieben, die sie nicht anfassen darf - allen voran den
        Erwartungswert, an dem der Livebetrieb gegen den Backtest gemessen
        wird.
        """
        from backtest.portfolio_walkforward import _trade_skalieren

        original = _trade('BTCUSDT', '50', tag=0)

        def r_wert(t) -> float:
            risiko = abs(float(t.entry_price) - float(t.stop_loss)) * float(t.qty)
            return float(t.net_pnl) / risiko

        for anteil in (0.5, 0.25, 0.1):
            skaliert = _trade_skalieren(original, anteil)
            assert r_wert(skaliert) == pytest.approx(r_wert(original)), (
                f"R haengt am Gewicht {anteil}"
            )
            assert float(skaliert.net_pnl) == pytest.approx(
                float(original.net_pnl) * anteil
            )
            assert float(skaliert.qty) == pytest.approx(float(original.qty) * anteil)

    def test_voller_anteil_gibt_den_trade_unveraendert_zurueck(self) -> None:
        """Der Einzelmarktfall darf nicht durch eine Rechnung laufen."""
        from backtest.portfolio_walkforward import _trade_skalieren

        original = _trade("BTCUSDT", "50", tag=0)

        assert _trade_skalieren(original, 1.0) is original

    def test_preise_und_zeiten_bleiben(self) -> None:
        """Skaliert wird nur, was von der Kontogroesse abhaengt."""
        from backtest.portfolio_walkforward import _trade_skalieren

        original = _trade("BTCUSDT", "50", tag=0)
        skaliert = _trade_skalieren(original, 0.5)

        assert skaliert.entry_price == original.entry_price
        assert skaliert.exit_price == original.exit_price
        assert skaliert.stop_loss == original.stop_loss
        assert skaliert.entry_time == original.entry_time
        assert skaliert.symbol == original.symbol


# ---------------------------------------------------------------------------
#  Kapital je Bein - die Mindestmenge laesst sich nicht halbieren
# ---------------------------------------------------------------------------
class TestKapitalTeilen:
    """Jedes Bein rechnet normalerweise mit dem **vollen** Startkapital, und
    erst das Ergebnis wird gewichtet.

    Fuer Gewinne ist das richtig - sie kuerzen sich heraus. Fuer die
    **Mindestmenge der Boerse** ist es falsch, denn die laesst sich nicht
    halbieren. Gemessen am Spitzenkandidaten, 500 EUR auf zwei Maerkte ueber
    den gemeinsamen Zeitraum:

        je Bein 500 EUR   154 Trades,  18 auf der Mindestmenge,   11,01 % p.a.
        je Bein 250 EUR   136 Trades,  45 auf der Mindestmenge,   10,11 % p.a.
                                       18 gar nicht handelbar

    Das ist kein Strategieproblem, sondern ein Kontogroessenproblem - aber es
    gehoert gemessen, bevor echtes Geld darauf gesetzt wird.
    """

    @pytest.fixture
    def risk(self) -> RiskSettings:
        return RiskSettings()

    def _konfiguration(self, symbol: str, risk: RiskSettings) -> BacktestConfig:
        return BacktestConfig(
            instrument=_instrument(symbol), risk=risk,
            initial_equity=Decimal("500"),
        )

    def test_geteiltes_kapital_handelt_kleiner(self, risk: RiskSettings) -> None:
        """Halbes Kapital, halbe Positionen - und damit stoesst die
        Mindestmenge oefter an."""
        frames = {"A": _tage(1100, seed=3), "B": _tage(1100, seed=11)}
        configs = {
            "A": self._konfiguration("AAAUSDT", risk),
            "B": self._konfiguration("BBBUSDT", risk),
        }
        genome = _trendfolger()
        splitter = WalkForwardSplitter(train_months=12, test_months=3)

        ohne = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs, splitter
        )
        mit = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs, splitter,
            kapital_teilen=True,
        )

        assert ohne.all_trades and mit.all_trades
        groesse_ohne = sum(t.qty for t in ohne.all_trades) / len(ohne.all_trades)
        groesse_mit = sum(t.qty for t in mit.all_trades) / len(mit.all_trades)
        assert groesse_mit < groesse_ohne, (
            "Mit geteiltem Kapital muessen die Positionen kleiner sein"
        )

    def test_nie_mehr_trades_als_ohne_teilen(self, risk: RiskSettings) -> None:
        """Weniger Kapital kann Trades unmoeglich machen, nie zusaetzliche
        ermoeglichen."""
        frames = {"A": _tage(1100, seed=3), "B": _tage(1100, seed=11)}
        configs = {
            "A": self._konfiguration("AAAUSDT", risk),
            "B": self._konfiguration("BBBUSDT", risk),
        }
        genome = _trendfolger()
        splitter = WalkForwardSplitter(train_months=12, test_months=3)

        ohne = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs, splitter
        )
        mit = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs, splitter,
            kapital_teilen=True,
        )

        assert len(mit.all_trades) <= len(ohne.all_trades)

    def test_ein_einzelnes_bein_bekommt_alles(self, risk: RiskSettings) -> None:
        """Bei einem Bein gibt es nichts zu teilen - das Ergebnis muss
        identisch bleiben."""
        frames = {"A": _tage(1100, seed=3)}
        configs = {"A": self._konfiguration("AAAUSDT", risk)}
        genome = _trendfolger()
        splitter = WalkForwardSplitter(train_months=12, test_months=3)

        ohne = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs, splitter
        )
        mit = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs, splitter,
            kapital_teilen=True,
        )

        assert len(mit.all_trades) == len(ohne.all_trades)

    def test_gewichte_bestimmen_den_anteil(self, risk: RiskSettings) -> None:
        """Dreifaches Gewicht heisst dreifaches Kapital - nicht die Haelfte."""
        frames = {"A": _tage(1100, seed=3), "B": _tage(1100, seed=11)}
        configs = {
            "A": self._konfiguration("AAAUSDT", risk),
            "B": self._konfiguration("BBBUSDT", risk),
        }
        genome = _trendfolger()
        splitter = WalkForwardSplitter(train_months=12, test_months=3)

        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs, splitter,
            weights={"A": 3.0, "B": 1.0}, kapital_teilen=True,
        )

        a = [t for t in bericht.all_trades if t.symbol == "AAAUSDT"]
        b = [t for t in bericht.all_trades if t.symbol == "BBBUSDT"]
        assert a and b, "Beide Beine muessen handeln"


class TestFeinereKerzen:
    """**Jede Zulassungszahl dieses Projekts lief auf der pessimistischen Annahme.**

    Liegen in einer Kerze sowohl Stop als auch Take-Profit, verraet OHLC nicht,
    was zuerst kam. Ohne feinere Kerzen nimmt die Engine den schlechteren Fall -
    die richtige Richtung fuer eine Naeherung, aber eine Naeherung. Der
    Einzelmarkt-Weg konnte sie schon lange aufloesen; der Portfolioweg reichte
    die Daten nicht durch, und gemessen wird das Portfolio.

    Die Tests hier pruefen die **Verdrahtung**: Dass die Aufloesung selbst
    stimmt, steht in ``test_backtest_engine.py``.
    """

    def _configs(self, frames, risk) -> dict:
        return {
            name: BacktestConfig(
                instrument=_instrument(f"{name}USDT"),
                risk=risk,
                initial_equity=Decimal("500"),
            )
            for name in frames
        }

    def _mitschrift(self, monkeypatch) -> dict[str, object]:
        """Faengt ab, welches Bein welche Feinkerzen bekommt."""
        from backtest import portfolio_walkforward as modul

        gesehen: dict[str, object] = {}
        echt = modul.run_walkforward

        def merken(frame, bauplan, konfiguration, splitter=None, **kw):
            # Das Bein steckt nicht im Aufruf, wohl aber sein Instrument -
            # und **nicht** die Kerzenzahl: ``common_range`` schneidet alle
            # Beine auf denselben Zeitraum, danach sind sie gleich lang.
            gesehen[konfiguration.instrument.symbol] = kw.get("sub_frame")
            return echt(frame, bauplan, konfiguration, splitter, **kw)

        monkeypatch.setattr(modul, "run_walkforward", merken)
        return gesehen

    def test_jedes_bein_bekommt_seine_eigenen(self, monkeypatch, risk) -> None:
        """Nicht die des anderen und nicht zweimal dieselben - sonst waere die
        Aufloesung schlimmer als keine."""
        frames = {
            "A": _tage(600, seed=1),
            "B": _tage(700, seed=2),
        }
        fein = {"A": _tage(600, seed=3), "B": _tage(700, seed=4)}
        gesehen = self._mitschrift(monkeypatch)

        run_portfolio_walkforward(
            frames, lambda: compile_genome(_trendfolger()), self._configs(frames, risk),
            WalkForwardSplitter(train_months=6, test_months=3),
            sub_frames=fein,
        )

        assert set(gesehen) == {"AUSDT", "BUSDT"}
        for bein, uebergeben in gesehen.items():
            assert uebergeben is not None, f"Bein {bein} bekam nichts"
        # Und nicht zweimal dieselben: Die Reihen unterscheiden sich in ihren
        # Kursen, also duerfen die uebergebenen Rahmen es auch.
        a, b = gesehen["AUSDT"], gesehen["BUSDT"]
        assert not a["close"].equals(b["close"])

    def test_ohne_angabe_bleibt_es_bei_der_annahme(self, monkeypatch, risk) -> None:
        """Der alte Weg muss unveraendert bleiben - jede bisherige Zahl haengt
        daran."""
        frames = {"A": _tage(600, seed=1)}
        gesehen = self._mitschrift(monkeypatch)

        run_portfolio_walkforward(
            frames, lambda: compile_genome(_trendfolger()), self._configs(frames, risk),
            WalkForwardSplitter(train_months=6, test_months=3),
        )

        assert all(wert is None for wert in gesehen.values())

    def test_ein_bein_ohne_feinkerzen_faellt_zurueck(self, monkeypatch, risk) -> None:
        """Teilweise vorhandene Feindaten sind der Normalfall - hier gibt es
        sie erst ab 2020, die Tageskerzen ab 2017."""
        frames = {"A": _tage(600, seed=1), "B": _tage(700, seed=2)}
        gesehen = self._mitschrift(monkeypatch)

        run_portfolio_walkforward(
            frames, lambda: compile_genome(_trendfolger()), self._configs(frames, risk),
            WalkForwardSplitter(train_months=6, test_months=3),
            sub_frames={"A": _tage(600, seed=3)},
        )

        assert gesehen["AUSDT"] is not None
        assert gesehen["BUSDT"] is None
