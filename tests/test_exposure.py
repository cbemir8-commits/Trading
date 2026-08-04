"""Tests fuer die zweite Betriebsart der Positionsgroesse und die Messlatte.

Worum es geht
-------------
Drei Generationen sind an derselben Stelle gescheitert, und zwei Zahlen im
eigenen Aufbau haben eine ganze Strategieklasse ausgeschlossen, ohne je etwas
ueber sie auszusagen: ``max_stop_distance_pct`` lehnte weite Stops ab, und
``min_oos_trades = 100`` verlangte eine Handelsfrequenz, die eine investierte
Strategie nie erreicht. Aus 535 Signalen wurden null Trades.

Diese Datei prueft, dass die Lockerung genau dort wirkt, wo sie gemeint ist -
und **nirgends sonst**. Die Gefahr bei so einer Aenderung ist nicht, dass sie
nicht wirkt, sondern dass sie zu viel durchlaesst.

Deshalb steht hier der Test, der zaehlt: Eine Strategie, die nichts weiter tut
als investiert zu bleiben, darf nicht zugelassen werden. Sie ist keine
Strategie, sondern die Messlatte in Verkleidung.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestConfig, Backtester
from core.config import RiskSettings
from execution.sizing import RejectReason, SizedPosition, SizingRejected, size_position
from research.benchmark import (
    benchmark_at_equal_risk,
    buy_and_hold_over_windows,
    risk_adjusted_score,
)
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
from tests.factories import make_candles, make_instrument, make_signal

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _ind(name: str, **params: int) -> Operand:
    return Operand(kind="indicator", name=name, params=params)


def _price(name: str) -> Operand:
    return Operand(kind="price", name=name)


def _const(value: float) -> Operand:
    return Operand(kind="constant", value=value)


# ---------------------------------------------------------------------------
#  Positionsgroesse
# ---------------------------------------------------------------------------
class TestKapitalanteil:
    def test_menge_folgt_dem_kapital_nicht_dem_stop(self) -> None:
        """Der Kern der Betriebsart.

        Zwei Signale mit sehr unterschiedlichem Stop muessen dieselbe Menge
        ergeben - genau das ist der Unterschied zur Risikoformel, wo der Stop
        die Menge bestimmt.
        """
        eng = make_signal(stop_pct="1.0", entry="100000")
        weit = make_signal(stop_pct="10.0", entry="100000")

        a = size_position(
            eng,
            equity=Decimal("1000"),
            instrument=make_instrument(),
            risk=RiskSettings(),
            equity_fraction=Decimal("0.5"),
        )
        b = size_position(
            weit,
            equity=Decimal("1000"),
            instrument=make_instrument(),
            risk=RiskSettings(),
            equity_fraction=Decimal("0.5"),
        )

        assert isinstance(a, SizedPosition)
        assert isinstance(b, SizedPosition)
        assert a.qty == b.qty
        assert a.notional == pytest.approx(Decimal("500"), rel=Decimal("0.01"))

    def test_weiter_stop_wird_nicht_mehr_abgelehnt(self) -> None:
        """Die Sperre, die Generation 3 unmoeglich gemacht hat.

        Ein 10-%-Stop ist fuer eine wettende Strategie unsinnig und wird dort
        weiterhin abgelehnt. Fuer eine investierte ist er die Notbremse.
        """
        signal = make_signal(stop_pct="10.0")

        nach_risiko = size_position(
            signal,
            equity=Decimal("1000"),
            instrument=make_instrument(),
            risk=RiskSettings(),
        )
        nach_anteil = size_position(
            signal,
            equity=Decimal("1000"),
            instrument=make_instrument(),
            risk=RiskSettings(),
            equity_fraction=Decimal("0.5"),
        )

        assert isinstance(nach_risiko, SizingRejected)
        assert nach_risiko.reason is RejectReason.STOP_TOO_WIDE
        assert isinstance(nach_anteil, SizedPosition)

    def test_zu_enger_stop_bleibt_abgelehnt(self) -> None:
        """Die Untergrenze gilt weiter - sie hat einen anderen Grund.

        Ein Stop innerhalb des normalen Rauschens wird ausgeloest, egal wie die
        Menge zustande kommt. Diese Sperre hat mit der Betriebsart nichts zu tun.
        """
        signal = make_signal(stop_pct="0.05")

        result = size_position(
            signal,
            equity=Decimal("1000"),
            instrument=make_instrument(),
            risk=RiskSettings(),
            equity_fraction=Decimal("0.5"),
        )

        assert isinstance(result, SizingRejected)
        assert result.reason is RejectReason.STOP_TOO_TIGHT

    def test_hebel_wird_auf_eins_gestellt(self) -> None:
        """Sonst kehrt sich der Sinn der Betriebsart um.

        Eine Position ueber 50 % des Kontos, bei 3x eingestellt, hinterlegt nur
        17 % als Margin und wird nach einem Rueckgang von rund 33 % liquidiert -
        obwohl die Haelfte des Kontos unberuehrt danebenliegt. Wer investiert
        bleiben will, braucht das ganze Konto als Puffer.
        """
        result = size_position(
            make_signal(stop_pct="10.0"),
            equity=Decimal("1000"),
            instrument=make_instrument(),
            risk=RiskSettings(max_leverage=Decimal("3")),
            equity_fraction=Decimal("0.5"),
        )

        assert isinstance(result, SizedPosition)
        assert result.exchange_leverage == Decimal(1)
        # Mit 1x liegt die Liquidation rund 100 % entfernt - der Stop ist
        # damit tatsaechlich die Notbremse und nicht die Boerse.
        assert result.liquidation_distance_pct > Decimal("90")

    def test_risikoformel_bleibt_unveraendert(self) -> None:
        """Ohne Angabe aendert sich nichts - alle bisherigen Genome laufen weiter."""
        signal = make_signal(stop_pct="1.0")
        risk = RiskSettings()

        # Bewusst grosses Kapital: Bei 1.000 EUR verschiebt schon die
        # Rundung auf 0,001 BTC das Ergebnis um mehrere Prozent, und der Test
        # wuerde die Rundung messen statt die Formel.
        result = size_position(
            signal, equity=Decimal("100000"), instrument=make_instrument(), risk=risk
        )

        assert isinstance(result, SizedPosition)
        assert result.risk_pct_of_equity == pytest.approx(
            risk.risk_per_trade_pct, rel=Decimal("0.05")
        )

    def test_anteil_ueber_dem_hebeldeckel_wird_abgelehnt(self) -> None:
        result = size_position(
            make_signal(stop_pct="5.0"),
            equity=Decimal("1000"),
            instrument=make_instrument(),
            risk=RiskSettings(max_leverage=Decimal("1")),
            equity_fraction=Decimal("2.0"),
        )

        assert isinstance(result, SizingRejected)
        assert result.reason is RejectReason.INVALID_FRACTION


class TestCompilerReichtDieBetriebsartDurch:
    def test_genom_ohne_angabe_meldet_none(self) -> None:
        genome = Genome(
            name="Ohne Angabe",
            rationale="Standardverhalten unveraendert",
            entry_long=[
                Condition(left=_price("close"), op=Operator.GT, right=_const(1.0))
            ],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )

        assert compile_genome(genome).equity_fraction is None

    def test_genom_mit_anteil_meldet_den_wert(self) -> None:
        genome = Genome(
            name="Mit Anteil",
            rationale="Beteiligung statt Wette",
            entry_long=[
                Condition(left=_price("close"), op=Operator.GT, right=_const(1.0))
            ],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
            sizing=SizingSpec(kind="kapitalanteil", fraction=0.4),
        )

        assert compile_genome(genome).equity_fraction == Decimal("0.4")


# ---------------------------------------------------------------------------
#  Die Messlatte
# ---------------------------------------------------------------------------
def _steigender_rahmen(count: int = 500, wachstum: float = 0.002) -> pd.DataFrame:
    preise = 20000 * np.exp(np.arange(count) * wachstum)
    zeiten = pd.date_range(T0, periods=count, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "open_time": zeiten,
            "open": preise,
            "high": preise * 1.001,
            "low": preise * 0.999,
            "close": preise,
            "volume": np.full(count, 100.0),
        }
    )


class TestMesslatte:
    def test_verkettet_multiplikativ(self) -> None:
        """Zwei Fenster mit je +10 % ergeben +21 %, nicht +20 %.

        Derselbe Fehler hat im Walk-Forward einmal einen Rueckgang von 1005 %
        erzeugt - dort war es die Kapitalkurve, hier waere es die Messlatte.
        """
        rahmen = _steigender_rahmen(count=400)
        eins = (T0, T0 + timedelta(hours=200))
        zwei = (T0 + timedelta(hours=200), T0 + timedelta(hours=400))

        r1, _ = buy_and_hold_over_windows(rahmen, [eins])
        r2, _ = buy_and_hold_over_windows(rahmen, [zwei])
        beide, _ = buy_and_hold_over_windows(rahmen, [eins, zwei])

        erwartet = ((1 + r1 / 100) * (1 + r2 / 100) - 1) * 100
        assert beide == pytest.approx(erwartet, rel=1e-6)
        assert beide < r1 + r2 + 1e-6 or beide > r1 + r2  # multiplikativ, nicht additiv

    def test_nur_die_testfenster_zaehlen(self) -> None:
        """Sonst vergleicht man verschiedene Maerkte und nennt es Erkenntnis."""
        rahmen = _steigender_rahmen(count=400)

        ganz, _ = buy_and_hold_over_windows(rahmen, [(T0, T0 + timedelta(hours=400))])
        haelfte, _ = buy_and_hold_over_windows(
            rahmen, [(T0, T0 + timedelta(hours=200))]
        )

        assert haelfte < ganz

    def test_gebuehr_faellt_je_fenster_an(self) -> None:
        """Sonst waere die Messlatte guenstiger als die Wirklichkeit."""
        rahmen = _steigender_rahmen(count=400)
        fenster = [(T0, T0 + timedelta(hours=400))]

        rendite, _ = buy_and_hold_over_windows(rahmen, fenster)
        roh = float(rahmen["close"].iloc[-1] / rahmen["close"].iloc[0] - 1) * 100

        assert rendite < roh

    def test_leere_fenster_ergeben_null(self) -> None:
        rahmen = _steigender_rahmen(count=50)

        rendite, rueckgang = buy_and_hold_over_windows(
            rahmen, [(datetime(2030, 1, 1, tzinfo=UTC), datetime(2030, 2, 1, tzinfo=UTC))]
        )

        assert rendite == 0.0
        assert rueckgang == 0.0


class TestRisikobereinigt:
    def test_haelfte_der_rendite_bei_einem_drittel_rueckgang_ist_besser(self) -> None:
        """Der Kern der Bewertung: Nicht wer mehr verdient, sondern wer besser handelt."""
        halten = risk_adjusted_score(120.0, 70.0)
        ruhig = risk_adjusted_score(60.0, 20.0)

        assert ruhig > halten

    def test_winziger_rueckgang_wird_gedeckelt(self) -> None:
        """Ohne Untergrenze bekaeme fast Nichtstun eine astronomische Note."""
        assert risk_adjusted_score(1.0, 0.01) == pytest.approx(1.0)

    def test_verlust_bleibt_negativ(self) -> None:
        assert risk_adjusted_score(-20.0, 30.0) < 0


# ---------------------------------------------------------------------------
#  Der Test, der zaehlt
# ---------------------------------------------------------------------------
class TestLockerungLaesstNichtsDurch:
    def test_immer_investiert_besteht_die_messlatte_nicht(self) -> None:
        """Eine Strategie, die nur investiert bleibt, ist keine Strategie.

        Sie ist die Messlatte in Verkleidung - mit Gebuehren obendrauf. Genau
        das ist die Gefahr der gelockerten Stichprobenregel, und genau dagegen
        steht das Messlatten-Gate. Faellt dieser Test, ist die Lockerung ein
        Loch.
        """
        from backtest.walkforward import WalkForwardSplitter, run_walkforward
        from research.gates import GateStatus, GateThresholds, gate_benchmark

        rahmen = _steigender_rahmen(count=15_000, wachstum=0.0004)
        immer_long = Genome(
            name="Immer dabei",
            rationale="Kauft beim ersten Balken und bleibt investiert - die "
            "Messlatte mit Gebuehren obendrauf.",
            entry_long=[
                Condition(left=_price("close"), op=Operator.GT, right=_const(1.0))
            ],
            stop=StopSpec(kind="percent", percent=20.0),
            targets=[TargetSpec(rr=20.0, portion=1.0)],
            sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        )

        config = BacktestConfig(
            instrument=make_instrument(),
            risk=RiskSettings(),
            initial_equity=Decimal("10000"),
        )
        report = run_walkforward(
            rahmen,
            lambda: compile_genome(immer_long),
            config,
            WalkForwardSplitter(train_months=6, test_months=3),
        )

        ergebnis = gate_benchmark(report, rahmen, GateThresholds())

        assert ergebnis.status is not GateStatus.PASS, (
            "Eine Strategie, die nur investiert bleibt, hat die Messlatte "
            "bestanden - dann ist das Gate wirkungslos und die gelockerte "
            "Stichprobenregel ein offenes Tor."
        )


class TestEngineNutztDieBetriebsart:
    def test_position_ist_so_gross_wie_der_anteil(self) -> None:
        """Ende zu Ende: Vom Genom bis zur tatsaechlich eroeffneten Position."""
        candles = make_candles(count=300, start=T0)
        rahmen = pd.DataFrame(
            {
                "open_time": [c.open_time for c in candles],
                "open": [float(c.open) for c in candles],
                "high": [float(c.high) for c in candles],
                "low": [float(c.low) for c in candles],
                "close": [float(c.close) for c in candles],
                "volume": [float(c.volume) for c in candles],
            }
        )
        genome = Genome(
            name="Beteiligung Ende zu Ende",
            rationale="Kauft frueh und bleibt drin - zum Messen der Menge.",
            entry_long=[
                Condition(left=_price("close"), op=Operator.GT, right=_const(1.0))
            ],
            stop=StopSpec(kind="percent", percent=20.0),
            targets=[TargetSpec(rr=20.0, portion=1.0)],
            sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        )
        config = BacktestConfig(
            instrument=make_instrument(),
            risk=RiskSettings(),
            initial_equity=Decimal("10000"),
        )

        result = Backtester(config).run(rahmen, compile_genome(genome))

        assert result.trades, "Ohne Trade sagt der Test nichts aus"
        erster = result.trades[0]
        nominal = erster.qty * erster.entry_price
        assert nominal == pytest.approx(Decimal("5000"), rel=Decimal("0.02"))


class TestMesslatteAnDenRaendern:
    """Die beiden Faelle, an denen sich entscheidet, ob das Gate taugt."""

    def test_verlangt_eine_lohnende_rendite(self) -> None:
        """Risikobereinigt hervorragend, wirtschaftlich sinnlos.

        Genau der Fall, den die Vorgabe ausschliessen soll: nicht einmal im
        Monat handeln fuer eine Rendite, die die Kosten nicht deckt. Ohne die
        zweite Bedingung bestuende so etwas allein durch seinen winzigen
        Rueckgang.
        """
        from research.gates import GateStatus, GateThresholds, gate_benchmark

        rahmen = _steigender_rahmen(count=2000, wachstum=0.0005)
        halten, halten_dd = buy_and_hold_over_windows(
            rahmen, [(rahmen["open_time"].iloc[0], rahmen["open_time"].iloc[-1])]
        )
        schwelle = benchmark_at_equal_risk(halten, halten_dd, 1.0)
        report = _report_mit(
            rendite=schwelle + 5.0, rueckgang=1.0, cagr=2.0, rahmen=rahmen
        )

        ergebnis = gate_benchmark(report, rahmen, GateThresholds())

        assert ergebnis.status is GateStatus.FAIL
        assert "im Jahr" in ergebnis.message, (
            "Durchgefallen, aber aus dem falschen Grund - dann prueft der Test "
            "nicht, was er zu pruefen vorgibt."
        )

    def test_laesst_ruhige_ueberlegenheit_durch(self) -> None:
        """Weniger Rendite als Halten, aber viel ruhiger - das soll bestehen.

        Sonst waere das Gate nur eine Renditeschranke, und eine Strategie mit
        zwei Dritteln der Rendite bei einem Zehntel des Rueckgangs faellt durch,
        obwohl sie fuer ein Konto mit 15-%-Kill-Switch die bessere Wahl ist.
        """
        from research.gates import GateStatus, GateThresholds, gate_benchmark

        rahmen = _schwankender_rahmen(count=6000)
        halten, halten_dd = buy_and_hold_over_windows(
            rahmen, [(rahmen["open_time"].iloc[0], rahmen["open_time"].iloc[-1])]
        )
        assert halten > 0, "Der Test braucht eine positive Messlatte"

        report = _report_mit(
            rendite=halten * 0.6,
            rueckgang=max(halten_dd * 0.1, 1.0),
            cagr=30.0,
            rahmen=rahmen,
        )

        ergebnis = gate_benchmark(report, rahmen, GateThresholds())

        assert ergebnis.status is GateStatus.PASS, ergebnis.message


def _schwankender_rahmen(count: int = 3000) -> pd.DataFrame:
    """Steigend, aber mit einem echten Einbruch in der Mitte."""
    schritt = np.full(count, 0.0012)
    schritt[count // 3 : count // 2] = -0.004
    preise = 20000 * np.exp(np.cumsum(schritt))
    return pd.DataFrame(
        {
            "open_time": pd.date_range(T0, periods=count, freq="h", tz="UTC"),
            "open": preise,
            "high": preise * 1.001,
            "low": preise * 0.999,
            "close": preise,
            "volume": np.full(count, 100.0),
        }
    )


def _report_mit(*, rendite: float, rueckgang: float, cagr: float, rahmen: pd.DataFrame):
    """Ein Walk-Forward-Bericht mit vorgegebenen Kennzahlen.

    Bewusst gebaut statt gerechnet: Hier wird das Gate geprueft, nicht die
    Engine. Eine Strategie zu suchen, die zufaellig genau diese Zahlen liefert,
    haette den Test von Dingen abhaengig gemacht, die er nicht misst.
    """
    from dataclasses import replace as _replace

    from backtest.metrics import compute_metrics
    from backtest.walkforward import WalkForwardReport, Window, WindowResult

    leer = compute_metrics(
        [],
        pd.DataFrame({"time": rahmen["open_time"], "equity": 1.0}),
        initial_equity=Decimal("1000"),
        total_fees=Decimal(0),
    )
    kennzahlen = _replace(
        leer, total_return_pct=rendite, max_drawdown_pct=rueckgang, cagr_pct=cagr
    )
    fenster = Window(
        index=0,
        train_start=rahmen["open_time"].iloc[0],
        train_end=rahmen["open_time"].iloc[0],
        test_start=rahmen["open_time"].iloc[0],
        test_end=rahmen["open_time"].iloc[-1],
    )
    return WalkForwardReport(
        windows=[WindowResult(window=fenster, metrics=kennzahlen, trades=[], result=None)],
        combined=kennzahlen,
        all_trades=[],
    )


class TestZeitebene:
    """Die Beschraenkung, die den ersten Entwurf von Generation 5 wertlos machte."""

    def test_halte_strategien_gehoeren_auf_tageskerzen(self) -> None:
        """200 Perioden muessen 200 Tage heissen, nicht 200 Stunden.

        Die Whitelist laesst hoechstens 400 Perioden zu. Auf Stundenkerzen ist
        der laengste ausdrueckbare Durchschnitt damit gut zwei Wochen - ein
        Langfristfilter existiert dort schlicht nicht. Wer eine Halte-Strategie
        auf Stundenkerzen rechnet, misst etwas anderes, als in ihrer
        Begruendung steht.
        """
        from research.seeds import load_seeds
        from strategy.indicators import REGISTRY

        _, spec = REGISTRY["sma"]
        hoechste = spec.param_bounds["period"][1]

        for genome in load_seeds(5):
            for condition in genome.all_conditions:
                for operand in (condition.left, condition.right):
                    if operand.kind != "indicator":
                        continue
                    period = operand.params.get("period", 0)
                    assert period <= hoechste
                    # Auf Tageskerzen ist jede Periode zugleich die Zahl der
                    # Tage - genau das steht in den Begruendungen.
                    assert period <= 400, (
                        f"{genome.name}: Periode {period} ist auch auf "
                        "Tageskerzen nicht ausdrueckbar"
                    )

    def test_alle_kandidaten_der_generation_halten(self) -> None:
        """Sonst greift die Warnung im research-Befehl nicht fuer alle."""
        from research.seeds import load_seeds

        for genome in load_seeds(5):
            assert genome.sizing.kind == "kapitalanteil", (
                f"{genome.name} dimensioniert nach der Wettformel - dann "
                "gehoert der Kandidat nicht in diese Generation."
            )
