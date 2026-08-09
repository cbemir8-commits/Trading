"""Sagt die Konfluenz etwas ueber den Ausgang - oder nur ueber die Groesse?

Die gemessene Lage am Spitzenkandidaten, 152 Trades:

    Bedingungen  Trades   Mittel R   Median R   Trefferquote
              0      14      0,194     -1,030        14,3 %
              1      60      1,534     -0,969        21,7 %
              2      27     -0,427     -1,030         3,7 %
              3      51      2,688     -0,383        35,3 %

    rho = +0,150, p = 0,062

Die volle Konfluenz ist deutlich die beste - aber die Reihenfolge dazwischen
stimmt nicht, und der Zusammenhang ist nicht belegt. Genau das erklaert, warum
der Konviktions-Regler den Deflated Sharpe nicht bewegt.

Zwei Tests tragen die Datei:

* ``test_nicht_monoton_wird_gesagt`` - die gemessene Form. Eine Groessenlogik,
  die den Einsatz entlang einer Ordnung verteilt, die es nicht gibt, muss das
  gesagt bekommen.
* ``test_kleine_eimer_werden_nicht_gedeutet`` - vier Beobachtungen duerfen die
  Reihenfolge weder herstellen noch zerstoeren.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from research.konfluenzwirkung import (
    MIND_TRADES,
    Eimer,
    Wirkung,
    messe,
    zaehle_bedingungen,
)

T0 = datetime(2021, 1, 1, tzinfo=UTC)


class _Trade:
    """Nur was ``messe`` braucht - Einstiegszeit und Ergebnis in R."""

    def __init__(self, tag: int, r: float | None) -> None:
        self.entry_time = T0 + timedelta(days=tag)
        self.r_multiple = r


def _reihe(werte: list[int]) -> pd.Series:
    return pd.Series(
        werte, index=[pd.Timestamp(T0 + timedelta(days=i)) for i in range(len(werte))]
    )


class TestEimer:
    def test_kennzahlen(self) -> None:
        e = Eimer(bedingungen=3, ergebnisse=(2.0, -1.0, 4.0, -1.0))

        assert e.anzahl == 4
        assert e.mittel == 1.0
        assert e.median == 0.5
        assert e.trefferquote == 0.5
        assert not e.aussagekraeftig

    def test_leerer_eimer(self) -> None:
        e = Eimer(bedingungen=0, ergebnisse=())

        assert e.anzahl == 0
        assert e.mittel == 0.0
        assert e.trefferquote == 0.0


class TestWirkung:
    def test_nicht_monoton_wird_gesagt(self) -> None:
        """**Die gemessene Form.**

        Zwei Bedingungen sind schlechter als eine. Wer den Einsatz entlang
        dieser Reihenfolge verteilt, verteilt ihn entlang einer Ordnung, die
        so nicht gilt.
        """
        w = Wirkung(
            eimer=[
                Eimer(0, tuple([0.2] * 30)),
                Eimer(1, tuple([1.5] * 60)),
                Eimer(2, tuple([-0.4] * 27)),
                Eimer(3, tuple([2.7] * 51)),
            ],
            rho=0.15,
            p_wert=0.062,
        )

        assert not w.monoton
        assert not w.belegt
        assert "nicht einmal der Reihe nach" in w.urteil()
        assert "nicht** belegt" in w.urteil()

    def test_monotone_reihenfolge_wird_bestaetigt(self) -> None:
        w = Wirkung(
            eimer=[
                Eimer(0, tuple([-0.5] * 30)),
                Eimer(1, tuple([0.4] * 30)),
                Eimer(2, tuple([1.2] * 30)),
            ],
            rho=0.4,
            p_wert=0.001,
        )

        assert w.monoton
        assert w.belegt
        assert "Die Reihenfolge stimmt" in w.urteil()

    def test_kleine_eimer_werden_nicht_gedeutet(self) -> None:
        """**Vier Beobachtungen duerfen die Reihenfolge nicht kippen.**"""
        w = Wirkung(
            eimer=[
                Eimer(0, tuple([-0.5] * 30)),
                Eimer(1, (9.9, 9.9, 9.9)),  # winzig und hoch
                Eimer(2, tuple([0.4] * 30)),
            ],
            rho=0.3,
            p_wert=0.01,
        )

        assert w.monoton, "Der kleine Eimer haette die Ordnung zerstoert"
        assert "zu wenige" in w.tabelle()
        assert f"weniger als {MIND_TRADES} Trades" in w.urteil()

    def test_ohne_trades(self) -> None:
        leer = Wirkung()

        assert leer.trades == 0
        assert not leer.belegt
        assert "kein Urteil" in leer.urteil()
        assert "nichts zu pruefen" in leer.tabelle()


class TestMessung:
    def test_zuordnung_ueber_die_zeit_nicht_das_symbol(self) -> None:
        """Im Portfoliolauf tragen alle Trades dasselbe Symbol - zugeordnet
        wird deshalb ueber den Einstiegszeitpunkt."""
        trades = [_Trade(0, 1.0), _Trade(1, -1.0), _Trade(2, 3.0)]

        w = messe(trades, {"A": _reihe([3, 0, 3])}, permutationen=200)

        assert w.trades == 3
        assert {e.bedingungen: e.anzahl for e in w.eimer} == {0: 1, 3: 2}

    def test_trades_ohne_r_werden_uebergangen(self) -> None:
        """Ohne Stop gibt es kein R - eine Null waere erfunden."""
        w = messe(
            [_Trade(0, 1.0), _Trade(1, None)],
            {"A": _reihe([3, 3])},
            permutationen=200,
        )

        assert w.trades == 1

    def test_ein_klarer_zusammenhang_wird_belegt(self) -> None:
        rng = np.random.default_rng(4)
        trades, werte = [], []
        for i in range(160):
            n = i % 4
            werte.append(n)
            trades.append(_Trade(i, float(n) + float(rng.normal(0, 0.4))))

        w = messe(trades, {"A": _reihe(werte)}, permutationen=500)

        assert w.rho > 0.5
        assert w.belegt
        assert w.monoton

    def test_reines_rauschen_wird_nicht_belegt(self) -> None:
        """Der Gegenpol - sonst faende die Messung ueberall etwas."""
        rng = np.random.default_rng(9)
        trades, werte = [], []
        for i in range(160):
            werte.append(i % 4)
            trades.append(_Trade(i, float(rng.normal(0, 1.0))))

        w = messe(trades, {"A": _reihe(werte)}, permutationen=500)

        assert not w.belegt

    def test_ergebnis_ist_reproduzierbar(self) -> None:
        trades = [_Trade(i, float(i % 5) - 2) for i in range(60)]
        reihe = _reihe([i % 3 for i in range(60)])

        a = messe(trades, {"A": reihe}, permutationen=300)
        b = messe(trades, {"A": reihe}, permutationen=300)

        assert a.p_wert == b.p_wert
        assert a.rho == b.rho

    def test_ohne_zuordnung(self) -> None:
        w = messe([_Trade(99, 1.0)], {"A": _reihe([3, 3])}, permutationen=100)

        assert w.trades == 0


class TestZaehlung:
    def test_dieselbe_auswertung_wie_der_backtest(self) -> None:
        """Ueber ``_condition_series`` der kompilierten Strategie - eine zweite
        Umsetzung waere die naechste Stelle, an der Zahlen auseinanderlaufen."""
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        strategie = compile_genome(spitzenkandidat())
        n = 400
        rng = np.random.default_rng(3)
        close = 30000 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
        frame = pd.DataFrame(
            {
                "open_time": pd.date_range("2020-01-01", periods=n, freq="1D",
                                           tz="UTC"),
                "open": close * 0.999, "high": close * 1.02,
                "low": close * 0.98, "close": close,
                "volume": np.full(n, 100.0), "turnover": close * 100.0,
            }
        )

        zahl = zaehle_bedingungen(strategie, frame)

        assert len(zahl) == n
        assert zahl.min() >= 0
        assert zahl.max() <= len(spitzenkandidat().konfluenz)

    def test_ohne_konfluenz_immer_null(self) -> None:
        from strategy.compiler import compile_genome
        from strategy.genome import (
            Condition,
            Genome,
            Operand,
            Operator,
            TargetSpec,
        )

        ohne = Genome(
            name="Ohne Konfluenz",
            rationale="Nur ein Einstieg, keine Zusatzbedingungen.",
            entry_long=[
                Condition(
                    left=Operand(kind="price", name="close"),
                    op=Operator.GT,
                    right=Operand(kind="indicator", name="sma", params={"period": 20}),
                )
            ],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )
        frame = pd.DataFrame(
            {
                "open_time": pd.date_range("2020-01-01", periods=50, freq="1D",
                                           tz="UTC"),
                "open": np.full(50, 100.0), "high": np.full(50, 101.0),
                "low": np.full(50, 99.0), "close": np.full(50, 100.0),
                "volume": np.full(50, 10.0), "turnover": np.full(50, 1000.0),
            }
        )

        assert not zaehle_bedingungen(compile_genome(ohne), frame).any()
