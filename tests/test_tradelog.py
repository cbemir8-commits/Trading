"""Tests fuer das Mitschreiben einzelner Trades.

Der Punkt dieser Datei: Eine Kennzahl verdichtet, und beim Verdichten geht
genau das verloren, was man beim Draufschauen wissen will. Ausgeglichene
Erwartung kann viele kleine Gewinne mit wenigen grossen Verlusten heissen -
oder umgekehrt. Dieselbe Zahl, gegensaetzliche Erfahrung.

Zwei Dinge muessen deshalb stimmen: Die Kapitalkurve wird **multiplikativ**
verkettet (additiv hat hier schon einmal einen Rueckgang von 1005 % erzeugt),
und ein Trade ohne Stop bekommt **kein** R zugewiesen - eine geratene Zahl
waere schlimmer als eine fehlende.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from core.models import Side, Trade
from research.tradelog import CURVE_POINTS, build_log

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def make_trade(
    *,
    index: int = 0,
    gewinn: str = "10",
    stop: str | None = "99",
    einstieg: str = "100",
) -> Trade:
    return Trade(
        trade_id=f"t{index}",
        symbol="BTCUSDT",
        side=Side.BUY,
        strategy_id="test",
        entry_time=T0 + timedelta(hours=index),
        entry_price=Decimal(einstieg),
        exit_time=T0 + timedelta(hours=index, minutes=90),
        exit_price=Decimal(einstieg) + Decimal(gewinn),
        qty=Decimal("1"),
        gross_pnl=Decimal(gewinn),
        fees=Decimal("0"),
        stop_loss=Decimal(stop) if stop is not None else None,
        exit_reason="take_profit" if Decimal(gewinn) > 0 else "stop_loss",
    )


@dataclass
class FakeWindow:
    result: object


@dataclass
class FakeWalk:
    all_trades: list
    windows: list


@dataclass
class FakeGenome:
    genome_id: str = "abc123"
    name: str = "Testkandidat"


@dataclass
class FakeCandidate:
    genome: FakeGenome
    walkforward: FakeWalk


class FakeResult:
    def __init__(self, werte: list[float], start: datetime | None = None) -> None:
        t0 = start or T0
        self.equity_curve = pd.DataFrame(
            {
                "time": [t0 + timedelta(hours=i) for i in range(len(werte))],
                "equity": werte,
            }
        )


def kandidat(trades: list[Trade], fenster: list[FakeWindow] | None = None):
    return FakeCandidate(
        genome=FakeGenome(),
        walkforward=FakeWalk(all_trades=trades, windows=fenster or []),
    )


class TestTrades:
    def test_zaehlt_gewinner_und_verlierer(self) -> None:
        trades = [make_trade(index=i, gewinn="10") for i in range(3)]
        trades += [make_trade(index=i + 3, gewinn="-5") for i in range(2)]

        log = build_log(kandidat(trades))

        assert log.gewinner == 3
        assert log.verlierer == 2

    def test_findet_die_laengste_verlustserie(self) -> None:
        """Die Zahl, an der Strategien im Betrieb scheitern.

        Nicht am Erwartungswert - wer zwoelfmal hintereinander verliert,
        schaltet ab, auch wenn die Rechnung langfristig aufginge.
        """
        muster = ["10", "-5", "-5", "-5", "10", "-5", "-5"]
        trades = [make_trade(index=i, gewinn=g) for i, g in enumerate(muster)]

        log = build_log(kandidat(trades))

        assert log.laengste_verlustserie == 3

    def test_ohne_stop_kein_r_wert(self) -> None:
        """Eine geratene Zahl waere schlimmer als eine fehlende.

        Ohne Stop laesst sich das eingegangene Risiko nicht beziffern, und
        jedes R waere frei erfunden - aber es saehe aus wie eine Messung.
        """
        log = build_log(kandidat([make_trade(stop=None)]))

        assert log.trades[0].r is None

    def test_mit_stop_wird_r_gerechnet(self) -> None:
        # Einstieg 100, Stop 99 -> Risiko 1. Gewinn 10 -> 10 R.
        log = build_log(kandidat([make_trade(einstieg="100", stop="99", gewinn="10")]))

        assert log.trades[0].r == pytest.approx(10.0, rel=0.01)

    def test_behaelt_die_juengsten(self) -> None:
        trades = [make_trade(index=i) for i in range(50)]

        log = build_log(kandidat(trades), max_trades=10)

        assert len(log.trades) == 10
        # Die juengsten, nicht die aeltesten: Der letzte Abschnitt ist der
        # aussagekraeftigste, die aelteren stecken in den Kennzahlen.
        assert log.trades[-1].zeitpunkt == trades[-1].entry_time.isoformat(
            timespec="minutes"
        )

    def test_ohne_trades_kein_absturz(self) -> None:
        log = build_log(kandidat([]))

        assert log.trades == []
        assert "Keine Trades" in log.summary()


class TestKapitalkurve:
    def test_verkettet_multiplikativ(self) -> None:
        """Zwei Fenster mit je +10 % ergeben +21 %, nicht +20 %.

        Additiv zu verketten hat im Walk-Forward einmal einen Rueckgang von
        1005 % erzeugt - dieselbe Rechnung, dieselbe Falle.
        """
        eins = FakeWindow(result=FakeResult([100.0, 110.0]))
        zwei = FakeWindow(result=FakeResult([200.0, 220.0], start=T0 + timedelta(days=1)))

        log = build_log(kandidat([], [eins, zwei]))

        assert log.kurve[-1][1] == pytest.approx(1.21, rel=1e-6)

    def test_daunt_auf_wenige_stuetzpunkte(self) -> None:
        """Ein Diagramm auf einem Telefon braucht keine 20.000 Punkte."""
        lang = FakeWindow(result=FakeResult([100.0 + i for i in range(20_000)]))

        log = build_log(kandidat([], [lang]))

        assert len(log.kurve) <= CURVE_POINTS + 2

    def test_letzter_punkt_bleibt_erhalten(self) -> None:
        """Sonst fehlt beim Daunen ausgerechnet der Endstand."""
        lang = FakeWindow(result=FakeResult([100.0 + i for i in range(1000)]))

        log = build_log(kandidat([], [lang]))

        assert log.kurve[-1][1] == pytest.approx(1099.0 / 100.0, rel=1e-6)

    def test_leeres_fenster_wird_uebersprungen(self) -> None:
        leer = FakeWindow(result=FakeResult([]))
        voll = FakeWindow(result=FakeResult([100.0, 105.0]))

        log = build_log(kandidat([], [leer, voll]))

        assert log.kurve[-1][1] == pytest.approx(1.05, rel=1e-6)
