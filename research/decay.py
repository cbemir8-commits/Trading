"""Verfallserkennung: Merken, dass eine Strategie aufgehoert hat zu funktionieren.

Das ist das Stueck, das fast niemand baut - und der Grund, warum die meisten
Handelssysteme nicht an einem schlechten Einstieg sterben, sondern daran, dass
niemand rechtzeitig gemerkt hat, dass der Vorteil weg war.

Der uebliche Ablauf ohne dieses Modul: Eine Strategie hoert auf zu
funktionieren. Der Drawdown waechst. Man haelt es fuer eine Durststrecke -
die gab es im Backtest schliesslich auch. Man haelt durch. Irgendwann greift
der Kill-Switch, und dann weiss man es. Das ist eine sehr teure Art, etwas zu
erfahren.

Die Alternative: Man legt **vorher** fest, wie eine funktionierende Strategie
aussieht, und prueft laufend dagegen. Vergleichsgroesse ist der
**Erwartungswert in R** - nicht Euro, nicht Prozent. R ist unabhaengig von
Kontostand, Positionsgroesse und Hebel; nur so sind Backtest und Livebetrieb
ueberhaupt vergleichbar.

Ehrlichkeit ueber die Aussagekraft
----------------------------------
Mit 20 Live-Trades laesst sich fast nichts feststellen. Die Streuung einzelner
Trades ist so gross, dass selbst eine halbierte Erwartung im Rauschen
verschwindet. Dieses Modul rechnet deshalb **immer mit aus**, wie viele Trades
noetig waeren - und sagt "noch nicht beurteilbar", statt eine Zahl
vorzutaeuschen, die keine ist.

Ein Verfallsdetektor, der nach zehn Trades "kaputt" ruft, wechselt die
Strategie bei jedem normalen Verlustlauf. Das ist schlimmer als keiner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

import structlog

from core.models import Trade

log = structlog.get_logger(__name__)

#: Unter so vielen Trades wird gar nicht erst geurteilt.
MIN_TRADES_FOR_JUDGEMENT = 30

#: Oberhalb davon ist ein Abfall praktisch nicht mehr feststellbar - bei 30
#: Trades im Monat waeren 100.000 Trades ueber 270 Jahre. Die Zahl wird
#: gedeckelt, weil eine Angabe wie "10^32 Trades" auf dem Dashboard das
#: Vertrauen in jede andere Zahl daneben beschaedigt.
MAX_REPORTABLE_TRADES = 100_000

#: Wie sicher muss der Befund sein, bevor eine Strategie abgesetzt wird.
#: 95 % einseitig - ein Fehlalarm kostet einen unnoetigen Wechsel, ein
#: uebersehener Verfall kostet Geld. Trotzdem nicht lockerer: Zu haeufiges
#: Wechseln ist selbst eine Form von Ueberanpassung, nur langsamer.
CONFIDENCE = 1.645


class Health(StrEnum):
    UNKNOWN = "unknown"
    """Zu wenige Trades fuer eine Aussage. Der ehrlichste Zustand am Anfang."""

    HEALTHY = "healthy"
    """Live-Erwartung deckt sich mit der Erwartung aus dem Backtest."""

    WATCH = "watch"
    """Schlechter als erwartet, aber noch im Rahmen der Streuung."""

    DEGRADED = "degraded"
    """Signifikant schlechter. Kandidat zum Absetzen."""

    DEAD = "dead"
    """Erwartungswert nicht mehr positiv, signifikant. Absetzen."""


@dataclass(frozen=True, slots=True)
class DecayReport:
    health: Health
    trades: int
    live_expectancy_r: float
    expected_r: float
    standard_error: float
    z_score: float
    """Wie viele Standardfehler liegt die Live-Erwartung unter der erwarteten."""

    trades_needed: int
    """Wie viele Trades braeuchte es, um den beobachteten Abfall zu belegen."""

    detail: str

    @property
    def should_retire(self) -> bool:
        return self.health in {Health.DEGRADED, Health.DEAD}

    def describe(self) -> str:
        if self.health is Health.UNKNOWN:
            return (
                f"{self.trades} Trades - noch keine Aussage moeglich "
                f"(ab {MIN_TRADES_FOR_JUDGEMENT})"
            )
        return (
            f"{self.health.value}: {self.live_expectancy_r:+.3f} R live gegen "
            f"{self.expected_r:+.3f} R erwartet ({self.trades} Trades, "
            f"z={self.z_score:+.2f})"
        )


def r_multiples(trades: list[Trade]) -> list[float]:
    """Jeden Trade in Vielfachen des riskierten Betrags ausdruecken.

    Das ist die einzige Groesse, in der ein Backtest mit 500 EUR und ein
    Livebetrieb mit 2.000 EUR direkt vergleichbar sind.
    """
    values: list[float] = []
    for trade in trades:
        risk = _risk_of(trade)
        if risk <= 0:
            continue  # ohne Stop kein R - der Trade sagt hier nichts aus
        values.append(float(trade.net_pnl) / risk)
    return values


def _risk_of(trade: Trade) -> float:
    if trade.stop_loss is None:
        return 0.0
    distance = abs(Decimal(trade.entry_price) - Decimal(trade.stop_loss))
    return float(distance * trade.qty)


def assess_decay(
    live_trades: list[Trade],
    *,
    expected_r: float,
    min_trades: int = MIN_TRADES_FOR_JUDGEMENT,
) -> DecayReport:
    """Laeuft die Strategie noch so, wie der Backtest es versprochen hat?

    ``expected_r`` ist der Erwartungswert je Trade aus dem Walk-Forward - die
    Zahl, gegen die live gemessen wird.
    """
    values = r_multiples(live_trades)
    count = len(values)

    if count < min_trades:
        return DecayReport(
            health=Health.UNKNOWN,
            trades=count,
            live_expectancy_r=_mean(values) if values else 0.0,
            expected_r=expected_r,
            standard_error=0.0,
            z_score=0.0,
            trades_needed=min_trades,
            detail=(
                f"{count} von mindestens {min_trades} Trades. Bei weniger ist "
                "die Streuung groesser als jeder Effekt, den man messen wollte."
            ),
        )

    mean = _mean(values)
    deviation = _stdev(values)
    if deviation == 0:
        deviation = 1e-9

    standard_error = deviation / math.sqrt(count)
    z = (mean - expected_r) / standard_error

    # Wie viele Trades braeuchte es, um genau diesen Abfall zu belegen?
    # Sagt ehrlich, ob "noch nicht signifikant" heisst "alles gut" oder
    # "wir haben schlicht noch nicht genug gesehen".
    #
    # Der Deckel ist nicht Kosmetik: Bei einem winzigen Abstand waechst die
    # Zahl ins Absurde (10^32 Trades). So eine Zahl auf dem Dashboard
    # beschaedigt das Vertrauen in jede andere Zahl daneben.
    gap = expected_r - mean
    if gap > 1e-9:
        needed = min(MAX_REPORTABLE_TRADES, math.ceil((CONFIDENCE * deviation / gap) ** 2))
    else:
        needed = count

    health, detail = _classify(mean, z, count, expected_r, needed)

    report = DecayReport(
        health=health,
        trades=count,
        live_expectancy_r=mean,
        expected_r=expected_r,
        standard_error=standard_error,
        z_score=z,
        trades_needed=needed,
        detail=detail,
    )
    log.info("verfall.geprueft", befund=report.describe())
    return report


def _classify(
    mean: float, z: float, count: int, expected_r: float, needed: int
) -> tuple[Health, str]:
    # Zuerst der harte Fall: Verliert die Strategie im Mittel Geld, und ist
    # das belegt? Dann ist die Frage nach dem Vergleich zum Backtest muessig.
    if mean <= 0 and z < -CONFIDENCE:
        return (
            Health.DEAD,
            f"Erwartungswert {mean:+.3f} R ist nicht mehr positiv und liegt "
            f"{abs(z):.1f} Standardfehler unter der Erwartung. Absetzen.",
        )

    if z < -CONFIDENCE:
        return (
            Health.DEGRADED,
            f"Live {mean:+.3f} R gegen {expected_r:+.3f} R erwartet - der "
            f"Abstand ist bei {count} Trades statistisch belegt. Absetzen.",
        )

    # Fliesskomma: Eine Strategie, die exakt liefert was versprochen war,
    # landet sonst wegen 0.14999999999999994 < 0.15 in der Beobachtung.
    if math.isclose(mean, expected_r, rel_tol=1e-6, abs_tol=1e-9):
        return (
            Health.HEALTHY,
            f"Live {mean:+.3f} R entspricht der Erwartung von {expected_r:+.3f} R.",
        )

    if mean < expected_r:
        limit = (
            f"ueber {MAX_REPORTABLE_TRADES:,} Trades - praktisch nicht feststellbar"
            .replace(",", ".")
            if needed >= MAX_REPORTABLE_TRADES
            else f"rund {needed} Trades"
        )
        return (
            Health.WATCH,
            f"Live {mean:+.3f} R liegt unter den erwarteten {expected_r:+.3f} R, "
            f"aber noch im Rahmen der Streuung. Fuer einen Beleg braeuchte es "
            f"{limit} - bisher {count}.",
        )

    return (
        Health.HEALTHY,
        f"Live {mean:+.3f} R gegen {expected_r:+.3f} R erwartet. Im Rahmen.",
    )


def detectable_drop(trades: int, deviation: float, expected_r: float) -> float:
    """Welchen Abfall koennte man bei dieser Trade-Zahl ueberhaupt erkennen?

    Die ernuechternde Gegenrechnung, und der Grund, warum ein 500-EUR-Konto
    mit 30 Trades im Monat erst nach Monaten eine belastbare Aussage zulaesst.
    Wer das nicht ausrechnet, haelt "nicht signifikant" faelschlich fuer
    "unauffaellig".

    Rueckgabe: Anteil des Erwartungswerts, der wegfallen muesste, damit man es
    merkt. 1.0 bedeutet, dass selbst ein vollstaendiger Verlust des Vorteils
    unentdeckt bliebe.
    """
    if trades <= 1 or expected_r <= 0:
        return 1.0
    minimum_gap = CONFIDENCE * deviation / math.sqrt(trades)
    return min(1.0, minimum_gap / expected_r)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)
