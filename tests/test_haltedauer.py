"""Die Haltedauer aus dem Genom - und warum sie jahrelang nichts tat.

``Genome.max_hold_bars`` gab es seit jeher: im Schema, mit Grenzen validiert,
von ``describe()`` ausgegeben. Die Engine sah es nie. Ihr Deckel sass allein
auf ``BacktestConfig``, und niemand reichte den einen Wert an die andere
Stelle weiter.

Das ist die unangenehmste Sorte Fehler: Ein fehlender Zwangsausstieg wirft
keine Ausnahme und schreibt keine Warnung - er erzeugt nur andere Trades.
Jedes Genom mit einer Haltedauer wurde ohne sie gerechnet, und jede Zahl, die
daraus folgte, galt fuer eine Regel, die so nie aufgeschrieben worden war.

Aufgefallen ist es beim Messen: Drei Haltedauern nebeneinander lieferten
**identische** Spalten. Ein Ergebnis, das sich nicht bewegt, wenn man am
Regler dreht, ist kein Ergebnis.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

from backtest.engine import BacktestConfig, Backtester, ExitReason
from core.config import RiskSettings
from strategy.base import hold_limit
from strategy.compiler import compile_genome
from strategy.genome import (
    Condition,
    Genome,
    Operand,
    Operator,
    StopSpec,
    TargetSpec,
)
from tests.factories import make_instrument


def wellige_reihe(n: int = 600) -> pd.DataFrame:
    """Ein steigender Markt, der um seinen Schnitt schwingt.

    **Der erste Anlauf nahm eine nur steigende Reihe** - und die taugt nicht:
    Der Kurs kreuzt seinen Schnitt dort genau einmal, es gibt eine einzige
    Position, und ob ein Deckel greift, laesst sich an einem Trade nicht
    ablesen. Erst mit Schwingung entstehen wiederholte Ein- und Ausstiege,
    und erst dann ist die Frage "handelt ein kuerzerer Deckel oefter"
    ueberhaupt eine Frage.
    """
    i = np.arange(n)
    close = 100 * np.exp(np.cumsum(np.full(n, 0.0004))) * (1 + 0.012 * np.sin(i / 9.5))
    return pd.DataFrame(
        {
            "open_time": [
                datetime(2021, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(n)
            ],
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 50.0),
        }
    )


def genom(*, halten: int) -> Genome:
    return Genome(
        name=f"Halten {halten}",
        rationale="Einstieg ueber dem Schnitt, Ausstieg nur ueber den Deckel.",
        entry_long=[
            Condition(
                left=Operand(kind="price", name="close"),
                op=Operator.CROSS_ABOVE,
                right=Operand(kind="indicator", name="sma", params={"period": 20}),
            )
        ],
        stop=StopSpec(kind="percent", percent=3.0),
        targets=[TargetSpec(rr=50.0, portion=1.0)],
        max_hold_bars=halten,
    )


def lauf(halten: int, *, config_deckel: int = 0):
    frame = wellige_reihe()
    config = BacktestConfig(
        instrument=make_instrument(),
        risk=RiskSettings(),
        initial_equity=Decimal("10000"),
        max_hold_bars=config_deckel,
        enforce_risk_limits=False,
    )
    return Backtester(config).run(frame, compile_genome(genom(halten=halten)))


class TestDerDeckelWirkt:
    def test_ohne_deckel_laeuft_die_position_weiter(self) -> None:
        ohne = lauf(0)

        assert not [t for t in ohne.trades if t.exit_reason == ExitReason.MAX_HOLD.value]

    def test_mit_deckel_wird_zwangsweise_geschlossen(self) -> None:
        """**Der Test, den es haette geben muessen.**

        Er schlaegt gegen die alte Fassung fehl: Dort erreichte
        ``genome.max_hold_bars`` die Engine nicht, und es gab keinen einzigen
        Ausstieg mit diesem Grund.
        """
        mit = lauf(20)
        erzwungen = [t for t in mit.trades if t.exit_reason == ExitReason.MAX_HOLD.value]

        assert erzwungen, "Das Genom setzt einen Deckel - er muss greifen"

    def test_der_deckel_begrenzt_die_haltedauer(self) -> None:
        """Die unmittelbare Wirkung, und sie muss der Zahl im Genom folgen."""
        for deckel in (20, 40, 80):
            trades = lauf(deckel).trades
            laengste = max((t.exit_time - t.entry_time).days for t in trades)

            assert laengste <= deckel + 1, (
                f"Deckel {deckel}, laengste Position {laengste} Kerzen"
            )

    def test_ein_kuerzerer_deckel_erzeugt_mehr_trades(self) -> None:
        """Die Richtung, um die es in der Sache geht: Wer frueher aussteigt,
        handelt oefter - und genau darauf zielt die Frage, ob ein gedeckelter
        Ausstieg die Kopplung aus Befund 54 bricht. Ohne diese Wirkung waere
        der Regler wirkungslos, und genau das war er."""
        kurz = lauf(20)
        lang = lauf(80)

        assert len(kurz.trades) > len(lang.trades)

    def test_verschiedene_deckel_liefern_verschiedene_ergebnisse(self) -> None:
        """Der Befund, der den Fehler aufgedeckt hat, als Test.

        Drei Deckel nebeneinander lieferten identische Zahlen. Ein Ergebnis,
        das sich nicht bewegt, wenn man am Regler dreht, ist keines.
        """
        ergebnisse = {len(lauf(d).trades) for d in (0, 20, 40, 80)}

        assert len(ergebnisse) > 1


class TestVorrang:
    def test_das_genom_schlaegt_die_konfiguration(self) -> None:
        """Wie lange man zu halten bereit ist, gehoert zur Idee - nicht zum
        Maschinenaufbau. Dieselbe Begruendung wie bei der Groessenlogik, und
        dieselbe Reihenfolge."""
        genom_gewinnt = lauf(20, config_deckel=200)
        nur_genom = lauf(20)

        assert len(genom_gewinnt.trades) == len(nur_genom.trades)

    def test_ohne_genomdeckel_gilt_die_konfiguration(self) -> None:
        """Bestehende Laeufe duerfen sich nicht aendern: Wer keinen Deckel
        mitbringt, bekommt weiterhin den aus der Konfiguration."""
        aus_config = lauf(0, config_deckel=20)
        erzwungen = [
            t for t in aus_config.trades if t.exit_reason == ExitReason.MAX_HOLD.value
        ]

        assert erzwungen


class TestHoldLimit:
    def test_die_strategie_hat_vorrang(self) -> None:
        class MitDeckel:
            max_hold_bars = 30

        assert hold_limit(MitDeckel(), 200) == 30

    def test_null_faellt_auf_die_konfiguration_zurueck(self) -> None:
        class OhneDeckel:
            max_hold_bars = 0

        assert hold_limit(OhneDeckel(), 200) == 200

    def test_eine_strategie_ohne_das_feld_verhaelt_sich_unveraendert(self) -> None:
        assert hold_limit(object(), 200) == 200
        assert hold_limit(object()) == 0

    def test_unsinn_im_feld_kippt_keinen_lauf(self) -> None:
        """Lieber der bisherige Wert als ein Absturz mitten im Backtest."""

        class Kaputt:
            max_hold_bars = "zwanzig"

        assert hold_limit(Kaputt(), 200) == 200
