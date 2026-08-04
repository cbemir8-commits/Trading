"""Macht aus einem Genom eine ausfuehrbare Strategie.

Der Compiler ist die Grenze zwischen "was die KI vorschlaegt" und "was
tatsaechlich laeuft". Alles jenseits dieser Grenze ist gewoehnlicher,
getesteter Python-Code - es wird nie etwas ausgefuehrt, das ein Sprachmodell
geschrieben hat.

Aufwaermphase: Der Compiler leitet ``warmup_bars`` selbst aus den verwendeten
Indikatorperioden ab. Das ist wichtiger, als es klingt - eine zu kurz
angesetzte Aufwaermphase laesst die Strategie auf ``nan``-Werten entscheiden,
und je nach Vergleichsoperator ist das Ergebnis dann still ``False`` statt
eines Fehlers.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from core.models import Side, Signal, TakeProfitLeg
from strategy import indicators
from strategy.base import BarContext
from strategy.genome import Condition, Genome, Operand, Operator

#: Sicherheitszuschlag auf die groesste Indikatorperiode. Rekursive Glaettungen
#: (EMA, Wilder) sind nach ``period`` Kerzen zwar definiert, aber noch nicht
#: eingeschwungen - die ersten Werte haengen stark vom Startwert ab.
WARMUP_FACTOR = 3
MIN_WARMUP = 30


class CompiledStrategy:
    """Ein Genom als lauffaehige Strategie."""

    def __init__(self, genome: Genome) -> None:
        self.genome = genome
        self.strategy_id = genome.genome_id
        self.warmup_bars = _estimate_warmup(genome)
        self._last_entry_index: int | None = None

    @property
    def equity_fraction(self) -> Decimal | None:
        """Kapitalanteil, falls das Genom danach dimensioniert - sonst ``None``.

        ``None`` heisst ausdruecklich "die bisherige Risikoformel" und nicht
        "kein Wert": Engine und Risk-Officer unterscheiden genau daran, welche
        Betriebsart gilt.
        """
        if self.genome.sizing.kind != "kapitalanteil":
            return None
        return Decimal(str(self.genome.sizing.fraction))

    # -- Vorberechnung -------------------------------------------------------
    def prepare(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        """Alle benoetigten Reihen einmal berechnen.

        Gleiche Operanden werden ueber ihren Schluessel zusammengefasst - zwei
        Bedingungen auf demselben EMA(50) berechnen ihn nur einmal.
        """
        series: dict[str, np.ndarray] = {}

        for condition in self._all_conditions():
            for operand in (condition.left, condition.right):
                if operand.kind == "constant" or operand.key in series:
                    continue
                series[operand.key] = self._compute_operand(frame, operand)

        # Der Stop braucht immer ATR, auch wenn keine Bedingung ihn nutzt.
        if self.genome.stop.kind == "atr":
            key = _atr_key(self.genome.stop.atr_period)
            if key not in series:
                series[key] = indicators.compute(
                    "atr", frame, {"period": self.genome.stop.atr_period}
                )

        return series

    @staticmethod
    def _compute_operand(frame: pd.DataFrame, operand: Operand) -> np.ndarray:
        if operand.kind == "price":
            return frame[operand.name].to_numpy(dtype=np.float64)
        return indicators.compute(operand.name, frame, operand.params)

    def _all_conditions(self) -> list[Condition]:
        return self.genome.all_conditions

    def should_exit(self, ctx: BarContext, side: Side) -> bool:
        """Ist die Bedingung erfuellt, unter der die Position beendet wird?

        Zusaetzlich zu Stop und Zielen, nicht an deren Stelle. Ein Genom ohne
        Ausstiegsbedingungen verhaelt sich unveraendert.
        """
        conditions = (
            self.genome.exit_long if side is Side.BUY else self.genome.exit_short
        )
        if not conditions:
            return False
        return self._evaluate_all(ctx, conditions)

    # -- Auswertung ----------------------------------------------------------
    def on_bar(self, ctx: BarContext) -> Signal | None:
        if self._in_cooldown(ctx.index):
            return None

        if not self._evaluate_all(ctx, self.genome.filters):
            return None

        if self.genome.entry_long and self._evaluate_all(ctx, self.genome.entry_long):
            side = Side.BUY
        elif self.genome.entry_short and self._evaluate_all(ctx, self.genome.entry_short):
            side = Side.SELL
        else:
            return None

        signal = self._build_signal(ctx, side)
        if signal is not None:
            self._last_entry_index = ctx.index
        return signal

    def _in_cooldown(self, index: int) -> bool:
        if self.genome.cooldown_bars == 0 or self._last_entry_index is None:
            return False
        return index - self._last_entry_index < self.genome.cooldown_bars

    def _evaluate_all(self, ctx: BarContext, conditions: list[Condition]) -> bool:
        """Alle Bedingungen muessen zutreffen (UND-Verknuepfung).

        Bewusst nur UND: Eine ODER-Verknuepfung wuerde den Suchraum
        vervielfachen und macht Strategien schwerer nachvollziehbar. Wer ein
        ODER braucht, formuliert zwei Genome - die sich dann auch einzeln
        gegen die Zulassungs-Gates behaupten muessen.
        """
        return all(self._evaluate(ctx, condition) for condition in conditions)

    def _evaluate(self, ctx: BarContext, condition: Condition) -> bool:
        left_now = self._read(ctx, condition.left, 0)
        right_now = self._read(ctx, condition.right, 0)

        if np.isnan(left_now) or np.isnan(right_now):
            return False  # Indikator noch nicht eingeschwungen

        if not condition.op.needs_previous_bar:
            match condition.op:
                case Operator.GT:
                    return bool(left_now > right_now)
                case Operator.LT:
                    return bool(left_now < right_now)
                case Operator.GTE:
                    return bool(left_now >= right_now)
                case Operator.LTE:
                    return bool(left_now <= right_now)

        if ctx.index < 1:
            return False
        left_prev = self._read(ctx, condition.left, 1)
        right_prev = self._read(ctx, condition.right, 1)
        if np.isnan(left_prev) or np.isnan(right_prev):
            return False

        if condition.op is Operator.CROSS_ABOVE:
            return bool(left_prev <= right_prev and left_now > right_now)
        return bool(left_prev >= right_prev and left_now < right_now)

    @staticmethod
    def _read(ctx: BarContext, operand: Operand, offset: int) -> float:
        if operand.kind == "constant":
            return operand.value
        return ctx.value(operand.key, offset)

    # -- Signalbau -----------------------------------------------------------
    def _build_signal(self, ctx: BarContext, side: Side) -> Signal | None:
        entry = Decimal(str(ctx.close()))
        distance = self._stop_distance(ctx, entry)
        if distance is None or distance <= 0:
            return None

        direction = Decimal(1) if side is Side.BUY else Decimal(-1)
        stop = entry - direction * distance

        if stop <= 0:
            return None  # kann bei absurd weiten Stops auf niedrigen Preisen passieren

        legs = [
            TakeProfitLeg(
                price=entry + direction * distance * Decimal(str(target.rr)),
                portion=Decimal(str(target.portion)),
            )
            for target in self.genome.targets
        ]

        return Signal(
            timestamp=ctx.time.to_pydatetime(),
            symbol="BTCUSDT",
            side=side,
            entry_price=entry,
            stop_loss=stop,
            take_profits=legs,
            strategy_id=self.strategy_id,
            reason=self._reason(side),
        )

    def _stop_distance(self, ctx: BarContext, entry: Decimal) -> Decimal | None:
        spec = self.genome.stop
        if spec.kind == "percent":
            return entry * Decimal(str(spec.percent)) / Decimal(100)

        key = _atr_key(spec.atr_period)
        if not ctx.has(key):
            return None
        atr_value = ctx.value(key)
        if np.isnan(atr_value) or atr_value <= 0:
            return None
        return Decimal(str(atr_value)) * Decimal(str(spec.multiple))

    def _reason(self, side: Side) -> str:
        conditions = self.genome.entry_long if side is Side.BUY else self.genome.entry_short
        return " UND ".join(c.describe() for c in conditions)


def compile_genome(genome: Genome) -> CompiledStrategy:
    """Ein validiertes Genom in eine lauffaehige Strategie uebersetzen."""
    return CompiledStrategy(genome)


def _atr_key(period: int) -> str:
    """Muss exakt dem ``Operand.key`` eines ATR-Operanden entsprechen,
    damit Stop und Bedingungen sich dieselbe Reihe teilen."""
    return f"indicator:atr(period={period})"


def _estimate_warmup(genome: Genome) -> int:
    """Aufwaermphase aus den groessten verwendeten Perioden ableiten.

    Zu kurz angesetzt entscheidet die Strategie auf ``nan``-Werten. Der
    Compiler wertet die dann zwar sicherheitshalber als 'Bedingung nicht
    erfuellt', aber das verschiebt still die ersten Signale - und im
    Walk-Forward, wo jedes Fenster neu anfaengt, faellt das nicht auf.
    """
    longest = 0
    for condition in [*genome.filters, *genome.entry_long, *genome.entry_short]:
        for operand in (condition.left, condition.right):
            if operand.kind != "indicator":
                continue
            for value in operand.params.values():
                longest = max(longest, value)
    if genome.stop.kind == "atr":
        longest = max(longest, genome.stop.atr_period)
    return max(MIN_WARMUP, longest * WARMUP_FACTOR)
