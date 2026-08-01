"""Marktphasen - und warum nicht *eine* Strategie flexibel sein soll.

Die naheliegende Idee lautet: eine Strategie bauen, die sich anpasst. Die
funktioniert selten, und zwar aus einem strukturellen Grund - eine Strategie,
die in jeder Marktphase gut aussieht, hat meistens genug freie Parameter, um
sich an die Vergangenheit anzuschmiegen. Sie ist nicht flexibel, sie ist
ueberangepasst. Man merkt den Unterschied erst live.

Der Weg, der traegt, ist ein anderer:

    Mehrere **Spezialisten**, jeder gut in *einer* Phase.
    Ein **Einordner**, der sagt, welche Phase gerade herrscht.
    Wer nicht zustaendig ist, handelt nicht.

Das ist ehrlicher, weil jede einzelne Strategie einfach bleiben darf, und es
ist pruefbar: Eine Trendfolgestrategie *muss* im Seitwaertsmarkt schlecht
sein. Ist sie es nicht, stimmt etwas mit der Auswertung nicht.

Vier Phasen aus zwei Achsen
---------------------------
                 ruhig              bewegt
    Trend    |  Trend ruhig    |  Trend bewegt   |
    Seitw.   |  Range ruhig    |  Range bewegt   |

Die Trendachse sagt, ob eine Richtung vorliegt; die Volatilitaetsachse sagt,
wie weit der Preis dabei schwankt. Beide zusammen bestimmen, was ueberhaupt
funktionieren kann: Ausbrueche brauchen Bewegung, Mean Reversion braucht
Seitwaerts, und enge Stops sind bei hoher Volatilitaet Selbstmord.

**Streng rueckwaertsgerichtet.** Die Einordnung darf nur Daten verwenden, die
zu diesem Zeitpunkt vorlagen. Eine Phaseneinteilung, die die Zukunft kennt,
ist die eleganteste Art, sich einen Vorteil einzubilden, den es nicht gibt -
und sie faellt in keinem gewoehnlichen Backtest auf.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd
import structlog

from core.models import Trade

log = structlog.get_logger(__name__)

#: Fenster fuer die Trendmessung. Bei 15-Minuten-Kerzen sind 480 rund fuenf Tage.
TREND_WINDOW = 480

#: Fenster fuer die Volatilitaetsmessung - kuerzer, weil Volatilitaet schneller
#: umschlaegt als ein Trend.
VOL_WINDOW = 96

#: Ab dieser Bewegung ueber das Trendfenster gilt eine Richtung als Trend.
TREND_THRESHOLD_PCT = 5.0


class Regime(StrEnum):
    TREND_CALM = "trend_ruhig"
    TREND_WILD = "trend_bewegt"
    RANGE_CALM = "range_ruhig"
    RANGE_WILD = "range_bewegt"

    @property
    def is_trending(self) -> bool:
        return self in {Regime.TREND_CALM, Regime.TREND_WILD}

    @property
    def is_volatile(self) -> bool:
        return self in {Regime.TREND_WILD, Regime.RANGE_WILD}

    def describe(self) -> str:
        return {
            Regime.TREND_CALM: "Trend bei ruhiger Volatilitaet - der freundlichste Fall",
            Regime.TREND_WILD: "Trend mit starken Schwankungen - Stops brauchen Luft",
            Regime.RANGE_CALM: "Seitwaerts und ruhig - Ausbrueche sind hier meist falsch",
            Regime.RANGE_WILD: "Seitwaerts mit heftigen Ausschlaegen - der teuerste Fall",
        }[self]


def classify(
    frame: pd.DataFrame,
    *,
    trend_window: int = TREND_WINDOW,
    vol_window: int = VOL_WINDOW,
    trend_threshold_pct: float = TREND_THRESHOLD_PCT,
) -> pd.Series:
    """Jeder Kerze eine Marktphase zuordnen - nur aus vergangenen Daten.

    Die Volatilitaetsschwelle ist der **gleitende Median der bisherigen**
    Volatilitaet, nicht der Median der Gesamtreihe. Der Unterschied ist der
    zwischen einer sauberen und einer wertlosen Auswertung: Der Gesamtmedian
    enthaelt die Zukunft, und eine Strategie, die weiss, ob der kommende Monat
    ruhiger wird als der Durchschnitt des ganzen Zeitraums, ist unschlagbar -
    und unrealistisch.
    """
    close = frame["close"].astype(float)

    change_pct = (close / close.shift(trend_window) - 1.0) * 100.0
    trending = change_pct.abs() > trend_threshold_pct

    returns = close.pct_change()
    volatility = returns.rolling(vol_window).std()

    # expanding().median() sieht ausschliesslich zurueck.
    reference = volatility.expanding(min_periods=vol_window * 2).median()
    wild = volatility > reference

    regime = pd.Series(Regime.RANGE_CALM.value, index=frame.index, dtype=object)
    regime[trending & ~wild] = Regime.TREND_CALM.value
    regime[trending & wild] = Regime.TREND_WILD.value
    regime[~trending & wild] = Regime.RANGE_WILD.value

    # Vor dem Einschwingen gibt es keine Einordnung. NaN statt einer Annahme:
    # Eine geratene Phase ist schlimmer als gar keine.
    warmup = max(trend_window, vol_window * 2)
    regime.iloc[:warmup] = None

    return regime


@dataclass(frozen=True, slots=True)
class RegimePerformance:
    """Wie gut lief eine Strategie in einer bestimmten Phase?"""

    regime: Regime
    trades: int
    expectancy_r: float
    win_rate: float
    total_r: float

    @property
    def is_competent(self) -> bool:
        """Darf diese Strategie in dieser Phase handeln?

        Zwei Bedingungen, beide noetig: genug Trades fuer eine Aussage, und
        ein positiver Erwartungswert. Ohne die erste Bedingung wuerde eine
        Strategie mit drei zufaellig guten Trades zur Spezialistin erklaert.
        """
        return self.trades >= 20 and self.expectancy_r > 0

    def describe(self) -> str:
        verdict = "zustaendig" if self.is_competent else "nicht zustaendig"
        return (
            f"{self.regime.value}: {self.trades} Trades, "
            f"{self.expectancy_r:+.3f} R/Trade, {self.win_rate:.0%} Treffer "
            f"- {verdict}"
        )


def performance_by_regime(
    trades: list[Trade], frame: pd.DataFrame, regimes: pd.Series | None = None
) -> dict[Regime, RegimePerformance]:
    """Trades nach Marktphase auswerten.

    Massgeblich ist die Phase **beim Einstieg** - das ist die Information, die
    zum Entscheidungszeitpunkt vorlag. Die Phase beim Ausstieg zu nehmen waere
    Lookahead durch die Hintertuer.
    """
    from research.decay import r_multiples

    if regimes is None:
        regimes = classify(frame)

    times = pd.to_datetime(frame["open_time"])
    buckets: dict[Regime, list[float]] = {r: [] for r in Regime}

    for trade in trades:
        label = _regime_at(times, regimes, trade.entry_time)
        if label is None:
            continue
        values = r_multiples([trade])
        if values:
            buckets[label].append(values[0])

    result: dict[Regime, RegimePerformance] = {}
    for regime, values in buckets.items():
        count = len(values)
        result[regime] = RegimePerformance(
            regime=regime,
            trades=count,
            expectancy_r=float(np.mean(values)) if values else 0.0,
            win_rate=(sum(1 for v in values if v > 0) / count) if count else 0.0,
            total_r=float(np.sum(values)) if values else 0.0,
        )
    return result


def _regime_at(times: pd.Series, regimes: pd.Series, moment) -> Regime | None:
    """Welche Phase galt zu diesem Zeitpunkt?

    Sucht die letzte Kerze, die **vor oder auf** dem Zeitpunkt liegt - nie
    danach.
    """
    stamp = pd.Timestamp(moment)
    if times.dt.tz is None and stamp.tz is not None:
        stamp = stamp.tz_localize(None)
    elif times.dt.tz is not None and stamp.tz is None:
        stamp = stamp.tz_localize(times.dt.tz)

    position = times.searchsorted(stamp, side="right") - 1
    if position < 0 or position >= len(regimes):
        return None
    label = regimes.iloc[position]
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return None
    return Regime(label)


@dataclass(slots=True)
class RegimeRoster:
    """Wer darf in welcher Phase handeln.

    Das Ergebnis der ganzen Uebung: keine Strategie, die alles kann, sondern
    eine Zuordnung. Ist fuer die aktuelle Phase niemand zustaendig, wird
    **nicht gehandelt** - und das ist ein Ergebnis, kein Ausfall. Die teuersten
    Trades sind die, die man macht, weil man etwas machen wollte.
    """

    assignments: dict[Regime, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.assignments is None:
            self.assignments = {}

    def assign(self, regime: Regime, genome_id: str) -> None:
        self.assignments[regime] = genome_id

    def responsible_for(self, regime: Regime | None) -> str | None:
        if regime is None:
            return None
        return self.assignments.get(regime)

    @property
    def covered(self) -> set[Regime]:
        return set(self.assignments)

    @property
    def uncovered(self) -> set[Regime]:
        return set(Regime) - self.covered

    def describe(self) -> str:
        if not self.assignments:
            return "Keine Phase besetzt - es wird nicht gehandelt."
        lines = [f"  {r.value}: {g[:12]}" for r, g in sorted(self.assignments.items())]
        missing = sorted(r.value for r in self.uncovered)
        text = "Zustaendigkeiten:\n" + "\n".join(lines)
        if missing:
            text += f"\nUnbesetzt (kein Handel): {', '.join(missing)}"
        return text


def build_roster(
    performances: dict[str, dict[Regime, RegimePerformance]],
) -> RegimeRoster:
    """Aus den Phasen-Auswertungen mehrerer Strategien eine Zuordnung bauen.

    Je Phase gewinnt die Strategie mit dem hoechsten Erwartungswert - aber nur,
    wenn sie dort ueberhaupt zustaendig ist. Eine Phase ohne kompetente
    Strategie bleibt **unbesetzt**; dort wird dann nicht gehandelt.

    Das ist der Punkt, an dem sich diese Bauweise von "eine Strategie fuer
    alles" unterscheidet: Nichtstun ist eine zulaessige Antwort.
    """
    roster = RegimeRoster()

    for regime in Regime:
        best_id: str | None = None
        best_value = 0.0
        for genome_id, by_regime in performances.items():
            performance = by_regime.get(regime)
            if performance is None or not performance.is_competent:
                continue
            if performance.expectancy_r > best_value:
                best_id, best_value = genome_id, performance.expectancy_r

        if best_id is not None:
            roster.assign(regime, best_id)

    log.info("regime.zuordnung", zuordnung=roster.describe())
    return roster
