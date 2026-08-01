"""Kaufen und Liegenlassen - die Messlatte, die bisher gefehlt hat.

Die Frage lautet nicht "verdient die Strategie Geld". Sie lautet: **schlaegt
sie einfaches Halten?**

Das ist ein Unterschied, der ueber Sinn oder Unsinn des ganzen Vorhabens
entscheidet. Ueber 2020 bis 2026 hat BTC sich vervielfacht. Eine Strategie,
die in diesem Zeitraum 30 % Rendite macht, klingt gut - und ist trotzdem ein
Verlustgeschaeft, weil Nichtstun mehr gebracht haette, ohne Gebuehren, ohne
Nachtschichten und ohne Liquidationsrisiko.

Diese Zahl fehlte in den ersten beiden Zulassungslaeufen. Sie haette sie zwar
nicht gerettet - alle Kandidaten waren negativ, und die Messlatte lag klar
darueber -, aber sie haette die Ergebnisse einordnen koennen.

Zwei Groessen, nicht eine
-------------------------
Halten schlaegt fast jede aktive Strategie in der Rendite. Der Preis dafuer
sind Drawdowns von 70 bis 80 %. Wer zwischendurch 75 % im Minus liegt, haelt
selten durch - und ein Kill-Switch bei 15 % haette laengst ausgeloest.

Deshalb wird beides gemessen: Rendite **und** groesster Rueckgang. Eine
Strategie, die zwei Drittel der Rendite bei einem Drittel des Drawdowns
liefert, ist der Messlatte ueberlegen, obwohl sie weniger verdient.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
import structlog

from backtest.costs import CostModel
from backtest.metrics import Metrics, compute_metrics

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Benchmark:
    """Was einfaches Halten im selben Zeitraum gebracht haette."""

    metrics: Metrics
    start_price: float
    end_price: float

    @property
    def return_pct(self) -> float:
        return self.metrics.total_return_pct

    @property
    def max_drawdown_pct(self) -> float:
        return self.metrics.max_drawdown_pct

    def describe(self) -> str:
        return (
            f"Kaufen und Halten: {self.return_pct:+.1f} % Rendite, "
            f"{self.max_drawdown_pct:.1f} % groesster Rueckgang, "
            f"Sharpe {self.metrics.sharpe:.2f}"
        )

    def verdict_for(self, strategy: Metrics) -> str:
        """Ein Satz dazu, ob sich der Aufwand gelohnt haette."""
        better_return = strategy.total_return_pct > self.return_pct
        better_drawdown = strategy.max_drawdown_pct < self.max_drawdown_pct

        if better_return and better_drawdown:
            return "Schlaegt die Messlatte in beidem - Rendite und Rueckgang."
        if better_drawdown and strategy.total_return_pct > self.return_pct * 0.6:
            return (
                "Weniger Rendite, aber deutlich ruhiger - fuer ein Konto mit "
                "15 %-Kill-Switch der bessere Handel."
            )
        if better_return:
            return "Mehr Rendite, aber nicht ruhiger."
        return (
            "Schlechter als Nichtstun. Halten haette mehr gebracht, "
            "ohne Gebuehren und ohne Liquidationsrisiko."
        )


def buy_and_hold(
    frame: pd.DataFrame,
    *,
    initial_equity: Decimal = Decimal("500"),
    costs: CostModel | None = None,
) -> Benchmark:
    """Die Messlatte: einmal kaufen, bis zum Ende halten.

    Ohne Hebel, ohne Stop, ohne Ausstieg. Genau ein Kauf am Anfang, und die
    zugehoerige Gebuehr wird abgezogen - sonst waere die Messlatte guenstiger
    als die Wirklichkeit und jede Strategie sicher unterlegen.
    """
    if frame.empty or len(frame) < 2:
        raise ValueError("Fuer eine Messlatte braucht es mindestens zwei Kerzen")

    costs = costs or CostModel()
    prices = frame["close"].astype(float)
    start_price = float(prices.iloc[0])
    end_price = float(prices.iloc[-1])

    # Einmal kaufen: Die Gebuehr dafuer faellt einmal an, als Taker.
    fee_rate = float(costs.taker_fee_rate)
    units = float(initial_equity) * (1.0 - fee_rate) / start_price

    curve = pd.DataFrame(
        {
            "time": pd.to_datetime(frame["open_time"]),
            "equity": prices.to_numpy() * units,
        }
    )

    metrics = compute_metrics(
        [],  # keine Trades - die Kennzahlen kommen allein aus der Kurve
        curve,
        initial_equity=initial_equity,
        total_fees=Decimal(str(float(initial_equity) * fee_rate)),
    )

    benchmark = Benchmark(
        metrics=metrics, start_price=start_price, end_price=end_price
    )
    log.info("messlatte.berechnet", befund=benchmark.describe())
    return benchmark
