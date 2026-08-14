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

#: Indikatoren mit rekursiver Glaettung - nur sie brauchen den Zuschlag.
#:
#: Der Unterschied steht in ``indicators.py``: ``rolling(period,
#: min_periods=period)`` ist nach genau ``period`` Kerzen **exakt**, die
#: Vorgeschichte davor spielt keine Rolle mehr. ``ewm(adjust=False)`` traegt
#: den Startwert dagegen unbegrenzt mit; dort ist der Zuschlag noetig.
#:
#: Vorher galt der Faktor pauschal fuer alles. Das war nach oben ungefaehrlich,
#: nach unten aber teuer: Ein SMA(200) verlangte damit 600 Kerzen Vorlauf -
#: mehr, als vor dem ersten Testfenster ueberhaupt vorhanden sind.
REKURSIV = frozenset(
    {"ema", "rsi", "atr", "atr_pct", "adx", "macd", "macd_signal"}
)

#: Parameter, die keine Periode sind und deshalb nicht in die Aufwaermphase
#: eingehen duerfen.
KEINE_PERIODE = frozenset({"deviations"})


class CompiledStrategy:
    """Ein Genom als lauffaehige Strategie."""

    def __init__(self, genome: Genome) -> None:
        self.genome = genome
        self.strategy_id = genome.genome_id
        self.warmup_bars = _estimate_warmup(genome)
        self._fractions: np.ndarray | None = None

        self.max_hold_bars = genome.max_hold_bars
        """Zwangsschliessung nach N Kerzen, aus dem Genom. 0 = aus.

        **Diese eine Zeile hat lange gefehlt.** Das Feld gab es im Genom seit
        jeher - validiert, dokumentiert, von ``describe()`` ausgegeben - und
        die Engine las es nie: Ihr Deckel sass allein auf ``BacktestConfig``.
        Jedes Genom mit einer Haltedauer lief also **ohne** sie, und nichts
        deutete darauf hin, weil ein fehlender Zwangsausstieg keinen Fehler
        erzeugt, sondern nur andere Trades.
        """

        self._last_entry_time: pd.Timestamp | None = None
        """Wann zuletzt eingestiegen wurde - als **Zeitpunkt**, nicht als Index.

        Hier stand einmal der Index im aktuellen Rahmen, und das war ein
        Fehler mit Folgen. Im Backtest waechst dieser Index von 0 bis ans
        Ende; im Livebetrieb sieht die Strategie nur die letzten ``BUFFER_BARS``
        Kerzen, und sobald der Puffer voll ist, steht der Index **fest** auf
        ``BUFFER_BARS - 1``.

        Ab dem ersten Trade galt dort also immer ``index - letzter_einstieg
        == 0``, und die Sperrfrist lief nie ab. Gemessen ueber 5331
        BTC-Tageskerzen mit Sperrfrist 5: Backtest 113 Signale, Livebetrieb
        **4**. Der Roboter haette nach seinem ersten Trade praktisch aufgehoert
        zu handeln - ohne Fehlermeldung, ohne dass eine Kennzahl es gezeigt
        haette.

        Ein Zeitpunkt hat dieses Problem nicht: Er bedeutet in jedem Rahmen
        dasselbe. Gefunden hat es ``backtest/replay.py``."""

    def fraction_at(self, index: int) -> Decimal | None:
        """Kapitalanteil fuer diesen Balken.

        Bei fester Quote immer derselbe Wert; bei Vola-Ziel je Balken ein
        anderer. Der Einstieg fragt hier nach, statt einen Wert vom Beginn des
        Laufs zu benutzen - sonst waere die ganze Steuerung wirkungslos.
        """
        if self._fractions is None:
            return self.equity_fraction
        if not 0 <= index < len(self._fractions):
            return self.equity_fraction
        wert = self._fractions[index]
        if not np.isfinite(wert) or wert <= 0:
            return None
        return Decimal(str(round(float(wert), 4)))

    @property
    def equity_fraction(self) -> Decimal | None:
        """Kapitalanteil, falls das Genom danach dimensioniert - sonst ``None``.

        ``None`` heisst ausdruecklich "die bisherige Risikoformel" und nicht
        "kein Wert": Engine und Risk-Officer unterscheiden genau daran, welche
        Betriebsart gilt.
        """
        if self.genome.sizing.kind == "risiko":
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

        self._fractions = self._compute_fractions(frame)

        # Der Stop braucht immer ATR, auch wenn keine Bedingung ihn nutzt.
        if self.genome.stop.kind == "atr":
            key = _atr_key(self.genome.stop.atr_period)
            if key not in series:
                series[key] = indicators.compute(
                    "atr", frame, {"period": self.genome.stop.atr_period}
                )

        return series

    def _compute_fractions(self, frame: pd.DataFrame) -> np.ndarray | None:
        """Kapitalanteil je Balken.

        Zwei Regler wirken hier nacheinander:

        **Vola-Ziel** - Einsatz = Zielschwankung / gemessene Schwankung. In
        ruhigen Phasen steht mehr Kapital im Markt, in stuermischen weniger,
        und das Risiko bleibt ueber die Zeit ungefaehr gleich.

        **Konviktion** - je mehr Zusatzbedingungen zutreffen, desto groesser.
        Der Faktor wirkt multiplikativ, also auch auf das Vola-Ziel: Ein
        starkes Setup in einer stuermischen Phase wird nicht wieder gross.

        Wo die Schwankungsbreite noch nicht messbar ist - zu Beginn der Reihe -
        bleibt der Wert NaN. Dann wird nicht gehandelt, statt auf einer
        Annahme zu handeln.
        """
        sizing = self.genome.sizing
        konviktion = self._compute_konviktion(frame)

        if sizing.kind == "vola_ziel":
            vola = indicators.compute(
                "realized_vol", frame, {"period": sizing.vol_period}
            )
            with np.errstate(divide="ignore", invalid="ignore"):
                anteil = sizing.target_vol_pct / vola
        elif konviktion is not None and sizing.kind == "kapitalanteil":
            anteil = np.full(len(frame), sizing.fraction, dtype=float)
        else:
            return None

        if konviktion is not None:
            anteil = anteil * konviktion

        # Der Deckel steht am Ende, nach der Konviktion.
        #
        # Andersherum koennte ein starkes Setup ueber ``fraction`` hinaus
        # wachsen - und damit ueber die Grenze, die als hartes Risikolimit
        # gedacht ist. Eine Groessensteuerung, die ihre eigene Obergrenze
        # anheben darf, ist keine Obergrenze.
        return np.clip(anteil, 0.0, sizing.fraction)

    def _compute_konviktion(self, frame: pd.DataFrame) -> np.ndarray | None:
        """Faktor je Balken aus der Quote erfuellter Zusatzbedingungen.

        Der Faktor laeuft von ``1/(1+Bonus)`` bis **1,0**, nicht von 1,0 bis
        ``1+Bonus``. Das ist der entscheidende Unterschied:

        **Konviktion verteilt um, sie legt nicht drauf.** Waere der Faktor
        1,0 bis 1+Bonus, wuerde allein das Einschalten dieser Betriebsart den
        durchschnittlichen Einsatz erhoehen - und jeder Vergleich "mit gegen
        ohne" wuerde in Wahrheit "mehr Hebel gegen weniger Hebel" messen. Beim
        ersten Bauen war es genau so herum, und die Zahlen sahen gut aus, weil
        schlicht mehr Kapital im Markt stand.

        So herum ist das volle Setup so gross wie vorher, und alles Schwaechere
        wird kleiner. Wer insgesamt mehr Einsatz will, hebt ``fraction`` oder
        das Vola-Ziel - eine bewusste Entscheidung, keine Nebenwirkung.

        ``None`` heisst "nicht in Betrieb" - dann bleibt die Groessensteuerung
        genau die, die sie vorher war.
        """
        bonus = self.genome.sizing.konviktion_bonus
        if bonus <= 0 or not self.genome.konfluenz:
            return None

        treffer = np.zeros(len(frame), dtype=float)
        for condition in self.genome.konfluenz:
            treffer += self._condition_series(frame, condition)

        quote = treffer / len(self.genome.konfluenz)
        return (1.0 + bonus * quote) / (1.0 + bonus)

    def _condition_series(self, frame: pd.DataFrame, condition: Condition) -> np.ndarray:
        """Eine Bedingung fuer jeden Balken auswerten, als 0/1-Reihe.

        Kreuzungen sind hier bewusst **nicht** erlaubt: Ein Kreuzen ist ein
        Ereignis auf genau einem Balken. Als Groessenregler waere es sinnlos -
        der Einsatz spraenge fuer eine einzige Kerze hoch und faellt sofort
        zurueck. Konfluenz beschreibt einen Zustand, keinen Moment.
        """
        links = self._operand_series(frame, condition.left)
        rechts = self._operand_series(frame, condition.right)

        with np.errstate(invalid="ignore"):
            match condition.op:
                case Operator.GT:
                    treffer = links > rechts
                case Operator.LT:
                    treffer = links < rechts
                case Operator.GTE:
                    treffer = links >= rechts
                case Operator.LTE:
                    treffer = links <= rechts
                case _:
                    # CROSS_ABOVE / CROSS_BELOW: siehe Docstring.
                    treffer = np.zeros(len(frame), dtype=bool)

        # Noch nicht eingeschwungene Indikatoren zaehlen als "nicht erfuellt".
        # Nicht als "erfuellt" - das waere Einsatz auf Basis fehlender Daten.
        gueltig = np.isfinite(links) & np.isfinite(rechts)
        return np.where(gueltig & treffer, 1.0, 0.0)

    def _operand_series(self, frame: pd.DataFrame, operand: Operand) -> np.ndarray:
        if operand.kind == "constant":
            return np.full(len(frame), operand.value, dtype=float)
        return self._compute_operand(frame, operand)

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
        if self._in_cooldown(ctx):
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
            self._last_entry_time = ctx.time
        return signal

    def _in_cooldown(self, ctx: BarContext) -> bool:
        """Laeuft die Sperrfrist nach dem letzten Einstieg noch?

        Gezaehlt wird ueber den **Zeitpunkt** des letzten Einstiegs, nicht
        ueber seinen Index - siehe ``_last_entry_time``. Der Zeitpunkt wird im
        aktuellen Rahmen gesucht; daraus ergibt sich, wie viele Kerzen seither
        vergangen sind.

        Liegt er nicht mehr im Rahmen, ist er aus dem Puffer gerollt. Dann
        sind mindestens ``BUFFER_BARS`` Kerzen vergangen, und die Sperrfrist -
        hoechstens 50 Kerzen lang - ist mit Sicherheit abgelaufen.
        """
        if self.genome.cooldown_bars == 0 or self._last_entry_time is None:
            return False

        zeiten = ctx.times
        position = int(np.searchsorted(zeiten, self._last_entry_time))
        if position >= len(zeiten) or zeiten[position] != self._last_entry_time:
            return False

        return ctx.index - position < self.genome.cooldown_bars

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
    """Aufwaermphase aus den verwendeten Indikatorperioden ableiten.

    Zu kurz angesetzt entscheidet die Strategie auf ``nan``-Werten. Der
    Compiler wertet die dann zwar sicherheitshalber als 'Bedingung nicht
    erfuellt', aber das verschiebt still die ersten Signale - und im
    Walk-Forward, wo jedes Fenster neu anfaengt, faellt das nicht auf.

    **Genau das ist passiert, und zwar ueber Monate.** Diese Funktion sah nur
    ``filters``, ``entry_long`` und ``entry_short`` an. Als ``konfluenz``
    spaeter dazukam - Zusatzbedingungen, die die Positionsgroesse bestimmen -,
    wurde sie hier nie nachgetragen. Der Spitzenkandidat traegt seinen
    laengsten Indikator genau dort:

        entry_long    sma(50)     -> gezaehlt
        konfluenz     sma(200)    -> nicht gezaehlt
        konfluenz     roc(90)     -> nicht gezaehlt

    Ergebnis: 150 Kerzen Vorlauf statt der noetigen 200. Der SMA(200) war
    damit an **56 % aller Testtage** undefiniert - in jedem Fenster die ersten
    50 von 89 Tagen. Die Bedingung ``sma50 > sma200`` galt dort still als nicht
    erfuellt, und die Konviktion dimensionierte jede Position kleiner, als die
    Regel es verlangt.

    Der Ausstieg fehlte aus demselben Grund. Er entscheidet zwar keinen
    Einstieg, aber er entscheidet, wann eine Position endet - was bei einer
    Trendfolge dasselbe Gewicht hat.
    """
    longest = 0
    for condition in [
        *genome.filters,
        *genome.entry_long,
        *genome.entry_short,
        *genome.exit_long,
        *genome.exit_short,
        *genome.konfluenz,
    ]:
        for operand in (condition.left, condition.right):
            if operand.kind != "indicator":
                continue
            perioden = [
                value
                for name, value in operand.params.items()
                if name not in KEINE_PERIODE
            ]
            if not perioden:
                continue
            noetig = max(perioden)
            if operand.name in REKURSIV:
                noetig *= WARMUP_FACTOR
            # Eine Kerze mehr, damit auch ein Kreuzen am ersten Testbalken
            # erkennbar ist - dafuer braucht es den Vorgaengerwert.
            longest = max(longest, noetig + 1)

    if genome.stop.kind == "atr":
        longest = max(longest, genome.stop.atr_period * WARMUP_FACTOR + 1)
    return max(MIN_WARMUP, longest)
