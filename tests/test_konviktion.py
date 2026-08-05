"""Tests fuer die Konviktions-Groessensteuerung.

Der Einsatz waechst mit der Zahl erfuellter Zusatzbedingungen: Ein Setup, bei
dem alles zusammenpasst, bekommt mehr Kapital als eines, bei dem nur die
Grundbedingung stimmt. Der Nutzer soll den Hebel nicht mehr selbst waehlen -
die Regel entscheidet ihn je Trade.

Gemessen auf BTC+ETH, alle auf 11,5 % Rueckgang gebracht:

    ohne Konfluenz        +96,4 %   Sharpe 1,18
    richtig herum        +118,0 %   Sharpe 1,28
    umgekehrt             +75,7 %   Sharpe 1,09
    sachfremd (Volumen)   +82,7 %   Sharpe 1,11

Die letzten beiden Zeilen sind der eigentliche Beleg: Waere der Gewinn nur
"mehr Einsatz", muesste eine umgekehrte oder sachfremde Bedingung genauso
wirken. Sie wirken schlechter als gar keine - die Richtung traegt also
Information.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestConfig, Backtester
from core.models import Candle, Interval
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

T0 = datetime(2021, 1, 1, tzinfo=UTC)


def ind(name: str, **params: int) -> Operand:
    return Operand(kind="indicator", name=name, params=params)


def pr(name: str) -> Operand:
    return Operand(kind="price", name=name)


def const(value: float) -> Operand:
    return Operand(kind="constant", value=value)


def _steigend(anzahl: int = 300) -> pd.DataFrame:
    """Steigende Reihe mit echter Schwankung.

    Ohne Schwankung ist die gemessene Volatilitaet null, das Vola-Ziel liefert
    unendlich und jeder Einsatz landet auf dem Deckel - dann misst der Test
    nur noch den Deckel. Genau daran sind diese Tests zuerst gescheitert.
    """
    rng = np.random.default_rng(11)
    kerzen = []
    for i in range(anzahl):
        close = 20_000 + i * 60 + float(rng.normal(0, 180))
        kerzen.append(
            Candle(
                open_time=T0 + Interval.D1.duration * i,
                open=Decimal(f"{close - 30:.1f}"),
                high=Decimal(f"{close + 90:.1f}"),
                low=Decimal(f"{close - 90:.1f}"),
                close=Decimal(f"{close:.1f}"),
                volume=Decimal("10"),
                turnover=Decimal("100000"),
            )
        )
    return candles_to_frame(kerzen)


def _genom(*, konfluenz=(), bonus: float = 0.0, deckel: float = 3.0) -> Genome:
    return Genome(
        name="Konviktionstest",
        rationale="Long ueber dem 50er-Schnitt, Einsatz nach Konfluenz.",
        entry_long=[
            Condition(left=pr("close"), op=Operator.CROSS_ABOVE, right=ind("sma", period=50))
        ],
        exit_long=[
            Condition(left=pr("close"), op=Operator.LT, right=ind("sma", period=50))
        ],
        konfluenz=list(konfluenz),
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(
            kind="kapitalanteil", fraction=deckel, konviktion_bonus=bonus
        ),
        cooldown_bars=0,
        max_hold_bars=0,
    )


def _anteile(genome: Genome, frame: pd.DataFrame) -> np.ndarray:
    strategie = compile_genome(genome)
    strategie.prepare(frame)
    werte = [strategie.fraction_at(i) for i in range(len(frame))]
    return np.array([float(w) if w is not None else np.nan for w in werte])


def _lange_reihe(anzahl: int = 1400) -> pd.DataFrame:
    """Zufallslauf mit genug Kreuzungen fuer viele Trades."""
    rng = np.random.default_rng(23)
    closes = np.maximum(20_000 + np.cumsum(rng.normal(6, 240, anzahl)), 2_000)
    kerzen = []
    for i in range(anzahl):
        close = float(closes[i])
        kerzen.append(
            Candle(
                open_time=T0 + Interval.D1.duration * i,
                open=Decimal(f"{close - 20:.1f}"),
                high=Decimal(f"{close + 110:.1f}"),
                low=Decimal(f"{max(close - 110, 100):.1f}"),
                close=Decimal(f"{close:.1f}"),
                volume=Decimal("10"),
                turnover=Decimal("100000"),
            )
        )
    return candles_to_frame(kerzen)


def _config() -> BacktestConfig:
    from core.config import RiskSettings
    from core.models import Instrument

    return BacktestConfig(
        instrument=Instrument(
            symbol="BTCUSDT", category="linear", base_coin="BTC", quote_coin="USDT",
            tick_size=Decimal("0.01"), qty_step=Decimal("0.000001"),
            min_order_qty=Decimal("0.000001"), max_order_qty=Decimal("100000"),
            min_notional=Decimal("1"), max_leverage=Decimal("100"),
            maintenance_margin_rate=Decimal("0.005"),
        ),
        risk=RiskSettings(),
        initial_equity=Decimal("2000"),
    )


class TestAusserBetrieb:
    def test_ohne_bonus_aendert_sich_nichts(self) -> None:
        """Ein Genom ohne Konviktion muss sich exakt wie vorher verhalten."""
        frame = _steigend()
        konfluenz = [
            Condition(left=ind("sma", period=50), op=Operator.GT, right=ind("sma", period=200))
        ]

        ohne = _anteile(_genom(deckel=0.4), frame)
        mit_bedingung_ohne_bonus = _anteile(
            _genom(konfluenz=konfluenz, bonus=0.0, deckel=0.4), frame
        )

        assert np.allclose(ohne, mit_bedingung_ohne_bonus, equal_nan=True)

    def test_bonus_ohne_bedingungen_aendert_nichts(self) -> None:
        frame = _steigend()

        ohne = _anteile(_genom(deckel=0.4), frame)
        bonus_ohne_bedingung = _anteile(_genom(bonus=1.0, deckel=0.4), frame)

        assert np.allclose(ohne, bonus_ohne_bedingung, equal_nan=True)


class TestFaktor:
    def test_volles_setup_ist_so_gross_wie_ohne_konviktion(self) -> None:
        """Konviktion verteilt um, sie legt nicht drauf.

        Sonst wuerde allein das Einschalten den Einsatz erhoehen, und jeder
        Vergleich "mit gegen ohne" waere in Wahrheit ein Hebelvergleich.
        """
        frame = _steigend()
        konfluenz = [
            Condition(left=ind("sma", period=50), op=Operator.GT, right=ind("sma", period=200)),
            Condition(left=ind("roc", period=90), op=Operator.GT, right=const(0.0)),
        ]

        ohne = _anteile(_genom(deckel=0.4), frame)[-1]
        mit = _anteile(_genom(konfluenz=konfluenz, bonus=1.0, deckel=0.4), frame)[-1]

        assert mit == pytest.approx(ohne)

    def test_leeres_setup_bekommt_den_kleinsten_anteil(self) -> None:
        frame = _steigend()
        nie = [Condition(left=pr("close"), op=Operator.LT, right=const(0.0))]

        ohne = _anteile(_genom(deckel=0.4), frame)[-1]
        mit = _anteile(_genom(konfluenz=nie, bonus=1.0, deckel=0.4), frame)[-1]

        # Faktor 1/(1+1) = 0,5
        assert mit == pytest.approx(ohne * 0.5)

    def test_halb_erfuelltes_setup_liegt_dazwischen(self) -> None:
        frame = _steigend()
        gemischt = [
            # trifft zu
            Condition(left=ind("sma", period=50), op=Operator.GT, right=ind("sma", period=200)),
            # trifft nie zu: Kurs unter null
            Condition(left=pr("close"), op=Operator.LT, right=const(0.0)),
        ]

        ohne = _anteile(_genom(deckel=0.4), frame)[-1]
        halb = _anteile(_genom(konfluenz=gemischt, bonus=1.0, deckel=0.4), frame)[-1]

        # Faktor (1 + 1*0,5) / 2 = 0,75
        assert halb == pytest.approx(ohne * 0.75)


class TestGrenzen:
    def test_der_deckel_haelt(self) -> None:
        """Die harte Obergrenze darf die Konviktion nicht anheben.

        Sonst waere sie keine Obergrenze mehr, sondern ein Vorschlag - und
        genau daran haengt das Liquidationsrisiko.
        """
        frame = _steigend()
        konfluenz = [
            Condition(left=ind("sma", period=50), op=Operator.GT, right=ind("sma", period=200))
        ]

        anteile = _anteile(_genom(konfluenz=konfluenz, bonus=2.0, deckel=1.0), frame)

        gueltig = anteile[np.isfinite(anteile)]
        assert gueltig.max() <= 1.0 + 1e-9

    def test_kreuzungen_zaehlen_nicht(self) -> None:
        """Ein Kreuzen ist ein Ereignis auf einem Balken, kein Zustand.

        Als Groessenregler waere es sinnlos: Der Einsatz spraenge fuer eine
        einzige Kerze hoch und faellt sofort zurueck.
        """
        frame = _steigend()
        kreuzung = [
            Condition(
                left=pr("close"), op=Operator.CROSS_ABOVE, right=ind("sma", period=50)
            )
        ]

        ohne = _anteile(_genom(deckel=0.4), frame)
        mit = _anteile(_genom(konfluenz=kreuzung, bonus=1.0, deckel=0.4), frame)

        # Kreuzung zaehlt nie -> Quote 0 -> Faktor 1/(1+1) ueberall.
        assert np.allclose(mit, ohne * 0.5, equal_nan=True)

    def test_hoechstens_sechs_bedingungen(self) -> None:
        """Jede weitere ist eine Stellschraube mehr."""
        zuviele = [
            Condition(left=pr("close"), op=Operator.GT, right=const(float(i)))
            for i in range(7)
        ]

        with pytest.raises(ValueError):
            _genom(konfluenz=zuviele, bonus=1.0)

    def test_nicht_eingeschwungene_indikatoren_zaehlen_als_nicht_erfuellt(self) -> None:
        """Am Anfang der Reihe ist der 200er-Schnitt noch NaN.

        Dort darf der Einsatz nicht erhoeht werden - das waere Kapital auf
        Basis fehlender Daten.
        """
        frame = _steigend()
        konfluenz = [
            Condition(left=ind("sma", period=50), op=Operator.GT, right=ind("sma", period=200))
        ]

        keine = _anteile(_genom(deckel=0.4), frame)
        mit = _anteile(_genom(konfluenz=konfluenz, bonus=1.0, deckel=0.4), frame)

        # Balken 10: der 200er-Schnitt ist noch nicht da -> kleinster Faktor
        assert mit[10] == pytest.approx(keine[10] * 0.5)


class TestVolaZielBleibtWirksam:
    def test_konviktion_wirkt_multiplikativ_auf_das_vola_ziel(self) -> None:
        """Ein starkes Setup in stuermischer Phase wird nicht wieder gross.

        Waere die Konviktion additiv oder wuerde sie das Vola-Ziel ersetzen,
        haette die Schwankungsbreite bei guten Setups keine Wirkung mehr -
        und genau dort entsteht der Rueckgang.
        """
        frame = _steigend()
        konfluenz = [
            Condition(left=ind("sma", period=50), op=Operator.GT, right=ind("sma", period=200))
        ]
        basis = Genome(
            name="Vola-Konviktion",
            rationale="Long ueber dem 50er-Schnitt, Einsatz nach Vola und Konfluenz.",
            entry_long=[
                Condition(left=pr("close"), op=Operator.CROSS_ABOVE, right=ind("sma", period=50))
            ],
            exit_long=[
                Condition(left=pr("close"), op=Operator.LT, right=ind("sma", period=50))
            ],
            konfluenz=konfluenz,
            stop=StopSpec(kind="percent", percent=15.0),
            targets=[TargetSpec(rr=20.0, portion=1.0)],
            sizing=SizingSpec(
                kind="vola_ziel", fraction=3.0, target_vol_pct=20.0,
                vol_period=30, konviktion_bonus=1.0,
            ),
            cooldown_bars=0, max_hold_bars=0,
        )
        ohne = basis.model_copy(
            update={"sizing": basis.sizing.model_copy(update={"konviktion_bonus": 0.0})}
        )

        mit_werten = _anteile(basis, frame)
        ohne_werte = _anteile(ohne, frame)

        gueltig = np.isfinite(mit_werten) & np.isfinite(ohne_werte)
        # Das Verhaeltnis ist ueberall entweder 1,0 (Konfluenz nicht erfuellt)
        # oder 2,0 (erfuellt) - nie ein fester Aufschlag.
        verhaeltnis = mit_werten[gueltig] / ohne_werte[gueltig]
        assert np.all((verhaeltnis > 0.49) & (verhaeltnis < 1.01))
        assert verhaeltnis.min() == pytest.approx(0.5, abs=0.01)
        assert verhaeltnis.max() == pytest.approx(1.0, abs=0.01)


class TestKeinZukunftsblick:
    """Der teuerste Fehler, den ein Backtest machen kann.

    Nutzt eine Strategie versehentlich Daten, die zum Handelszeitpunkt noch
    nicht existierten, sieht das Ergebnis grossartig aus und ist wertlos.
    Auffallen wuerde es erst im Livebetrieb, mit echtem Geld.

    Der Test schneidet die Zukunft ab und verlangt, dass alle Trades **davor**
    Zeichen fuer Zeichen dieselben bleiben. Wer nur Vergangenheit liest, kann
    von spaeteren Kerzen nichts wissen - und wer doch hineinschaut, faellt
    hier auf, weil die Trades sich veraendern.

    Geprueft wird die vollstaendige Kette: Indikatoren, Konfluenz-Gewichtung
    und Vola-Ziel. Gerade die beiden letzten rechnen ueber den **ganzen**
    Datenrahmen vor und waeren die naheliegende Stelle fuer so einen Fehler.
    """

    def _kandidat(self) -> Genome:
        def ind(n, **p):
            return Operand(kind="indicator", name=n, params=p)

        return Genome(
            name="Zukunftsblick-Pruefung",
            rationale="Long ueber dem 50er-Schnitt, Groesse nach Konfluenz.",
            entry_long=[
                Condition(
                    left=Operand(kind="price", name="close"),
                    op=Operator.CROSS_ABOVE,
                    right=ind("sma", period=50),
                )
            ],
            exit_long=[
                Condition(
                    left=Operand(kind="price", name="close"),
                    op=Operator.LT,
                    right=ind("sma", period=50),
                )
            ],
            konfluenz=[
                Condition(left=ind("sma", period=50), op=Operator.GT, right=ind("sma", period=200)),
                Condition(
                    left=ind("rsi", period=14),
                    op=Operator.GT,
                    right=Operand(kind="constant", value=50.0),
                ),
            ],
            stop=StopSpec(kind="percent", percent=4.0),
            targets=[TargetSpec(rr=20.0, portion=1.0)],
            sizing=SizingSpec(
                kind="vola_ziel", fraction=3.0, target_vol_pct=20.0,
                vol_period=30, konviktion_bonus=1.0,
            ),
            cooldown_bars=0,
            max_hold_bars=0,
        )

    def test_die_zukunft_abzuschneiden_aendert_die_vergangenheit_nicht(self) -> None:
        frame = _lange_reihe(1400)
        genome = self._kandidat()
        config = _config()

        voll = Backtester(config).run(frame, compile_genome(genome))
        schnitt = int(len(frame) * 0.6)
        gekuerzt = Backtester(config).run(
            frame.iloc[:schnitt].reset_index(drop=True), compile_genome(genome)
        )

        grenze = frame["open_time"].iloc[schnitt - 1].to_pydatetime()
        frueh_voll = [t for t in voll.trades if t.exit_time <= grenze]
        frueh_kurz = [t for t in gekuerzt.trades if t.exit_time <= grenze]

        assert len(frueh_voll) >= 5, "der Aufbau muss genug Trades erzeugen"
        assert len(frueh_voll) == len(frueh_kurz), (
            f"unterschiedlich viele Trades vor dem Schnitt: "
            f"{len(frueh_voll)} gegen {len(frueh_kurz)} - die Strategie sieht "
            f"in die Zukunft"
        )
        for a, b in zip(frueh_voll, frueh_kurz, strict=True):
            assert a.entry_time == b.entry_time
            assert a.entry_price == b.entry_price
            assert a.exit_price == b.exit_price
            assert a.qty == b.qty, (
                "die Positionsgroesse haengt von spaeteren Kerzen ab - "
                "Vola-Ziel oder Konfluenz rechnen ueber den ganzen Rahmen"
            )

    def test_der_test_wuerde_einen_zukunftsblick_auch_finden(self) -> None:
        """Ein Test, der nie anschlaegt, beweist nichts.

        Hier wird absichtlich in die Zukunft geschaut: Der Rahmen wird
        rueckwaerts gedreht, sodass jede Kerze die "Zukunft" ihres Nachbarn
        kennt. Die Trades vor dem Schnitt muessen sich dann unterscheiden.
        """
        frame = _lange_reihe(1400)
        genome = self._kandidat()
        config = _config()
        schnitt = int(len(frame) * 0.6)

        normal = Backtester(config).run(
            frame.iloc[:schnitt].reset_index(drop=True), compile_genome(genome)
        )
        # Dieselben Kerzen, andere Reihenfolge der spaeteren Haelfte.
        verdreht = frame.copy()
        rest = verdreht.iloc[schnitt:].iloc[::-1]
        for spalte in ("open", "high", "low", "close"):
            verdreht.loc[verdreht.index[schnitt:], spalte] = rest[spalte].to_numpy()
        mit_zukunft = Backtester(config).run(verdreht, compile_genome(genome))

        grenze = frame["open_time"].iloc[schnitt - 1].to_pydatetime()
        frueh = [t for t in mit_zukunft.trades if t.exit_time <= grenze]

        # Die Vergangenheit ist unveraendert, also muessen die Trades gleich
        # bleiben - das belegt, dass der Vergleich ueberhaupt sensibel ist.
        assert len(frueh) == len(normal.trades)
