"""Strategien fuer Tests.

Bewusst vollstaendig deterministisch: Nur so laesst sich ein Trade von Hand
nachrechnen und gegen die Engine pruefen. Eine echte Strategie mit Indikatoren
waere als Testgrundlage ungeeignet - ein abweichendes Ergebnis koennte dann
ebenso gut am Indikator wie an der Engine liegen.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from core.models import Side, Signal, TakeProfitLeg
from strategy.base import BarContext


class ScriptedStrategy:
    """Gibt vorgegebene Signale an vorgegebenen Kerzen aus."""

    strategy_id = "scripted"

    def __init__(self, signals: dict[int, Signal], *, warmup_bars: int = 1) -> None:
        self.signals = signals
        self.warmup_bars = warmup_bars
        self.seen_indices: list[int] = []

    def prepare(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        return {}

    def on_bar(self, ctx: BarContext) -> Signal | None:
        self.seen_indices.append(ctx.index)
        return self.signals.get(ctx.index)


class SmaCrossStrategy:
    """Einfacher Durchschnittskreuzer - fuer Lookahead- und Integrationstests.

    Kausal aufgebaut: ``rolling(...).mean()`` schaut ausschliesslich zurueck.
    Genau darauf kommt es an - ein zentrierter Durchschnitt oder ein
    ``shift(-1)`` wuerde Lookahead erzeugen, den der BarContext nicht mehr
    abfangen kann, weil er schon in den vorberechneten Werten steckt.
    """

    strategy_id = "sma_cross"

    def __init__(
        self,
        *,
        fast: int = 10,
        slow: int = 30,
        stop_pct: Decimal = Decimal("0.6"),
        allow_shorts: bool = True,
    ) -> None:
        self.fast = fast
        self.slow = slow
        self.stop_pct = stop_pct
        self.allow_shorts = allow_shorts
        self.warmup_bars = slow + 2

    def prepare(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        close = frame["close"]
        return {
            "sma_fast": close.rolling(self.fast).mean().to_numpy(dtype=np.float64),
            "sma_slow": close.rolling(self.slow).mean().to_numpy(dtype=np.float64),
        }

    def on_bar(self, ctx: BarContext) -> Signal | None:
        if not ctx.is_ready("sma_fast", "sma_slow"):
            return None

        fast_now = ctx.value("sma_fast")
        slow_now = ctx.value("sma_slow")
        fast_prev = ctx.value("sma_fast", 1)
        slow_prev = ctx.value("sma_slow", 1)

        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now

        if crossed_up:
            side = Side.BUY
        elif crossed_down and self.allow_shorts:
            side = Side.SELL
        else:
            return None

        entry = Decimal(str(ctx.close()))
        distance = entry * self.stop_pct / Decimal(100)
        direction = Decimal(1) if side is Side.BUY else Decimal(-1)

        return Signal(
            timestamp=ctx.time.to_pydatetime(),
            symbol="BTCUSDT",
            side=side,
            entry_price=entry,
            stop_loss=entry - direction * distance,
            take_profits=[
                TakeProfitLeg(price=entry + direction * distance * Decimal("1.5"),
                              portion=Decimal("0.5")),
                TakeProfitLeg(price=entry + direction * distance * Decimal("3.0"),
                              portion=Decimal("0.5")),
            ],
            strategy_id=self.strategy_id,
            reason=f"SMA{self.fast} kreuzt SMA{self.slow}",
        )


class PeekingStrategy:
    """Eine Strategie, die absichtlich in die Zukunft schaut.

    Existiert, um zu belegen, dass die Schutzmechanismen greifen. Ein Test, der
    nur zeigt dass korrekter Code funktioniert, sagt nichts darueber aus, ob
    inkorrekter Code auffliegt.
    """

    strategy_id = "peeking"
    warmup_bars = 1

    def prepare(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        return {"close": frame["close"].to_numpy(dtype=np.float64)}

    def on_bar(self, ctx: BarContext) -> Signal | None:
        ctx.value("close", -1)  # muss LookaheadError ausloesen
        return None


class NonCausalStrategy:
    """Berechnet einen Indikator, der in die Zukunft schaut.

    Diese Sorte Fehler kann der BarContext nicht abfangen: Der Lookahead steckt
    bereits in den vorberechneten Werten. Nur der Vergleichstest ueber
    gekuerzte Zeitreihen deckt ihn auf.
    """

    strategy_id = "non_causal"
    warmup_bars = 5

    def prepare(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        # shift(-1) holt den Wert der NAECHSTEN Kerze nach vorn.
        return {"future_close": frame["close"].shift(-1).to_numpy(dtype=np.float64)}

    def on_bar(self, ctx: BarContext) -> Signal | None:
        future = ctx.value("future_close")
        if np.isnan(future):
            return None

        entry = Decimal(str(ctx.close()))
        # Nur kaufen, wenn die naechste Kerze hoeher schliesst - unschlagbar,
        # und genau deshalb ein Alarmsignal.
        if future <= float(entry):
            return None

        distance = entry * Decimal("0.6") / Decimal(100)
        return Signal(
            timestamp=ctx.time.to_pydatetime(),
            symbol="BTCUSDT",
            side=Side.BUY,
            entry_price=entry,
            stop_loss=entry - distance,
            take_profits=[TakeProfitLeg(price=entry + distance, portion=Decimal(1))],
            strategy_id=self.strategy_id,
            reason="schaut in die Zukunft",
        )
