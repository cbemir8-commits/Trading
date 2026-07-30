"""Zulassungs-Gates.

Hier entscheidet sich, ob eine Strategie echtes Geld sehen darf. Das ist der
Teil des Systems, der ueber Erfolg oder Selbstbetrug bestimmt - denn eine
Strategie zu finden, die auf historischen Daten gut aussieht, ist trivial. Man
muss nur genug ausprobieren.

Genau dagegen richten sich die Gates. Jedes einzelne adressiert eine konkrete
Art, sich selbst zu taeuschen:

============================  ==================================================
Gate                          Welche Selbsttaeuschung es verhindert
============================  ==================================================
Stichprobengroesse            "12 Trades, Sharpe 3,0" - reiner Zufall
Out-of-Sample-Sharpe          Auf den Trainingsdaten sieht alles gut aus
Drawdown                      Rendite, die man in der Praxis nie durchhaelt
Bestaendigkeit ueber Fenster  Ein Glueckstreffer traegt das Gesamtergebnis
Parameter-Plateau             EMA(47) gewinnt, EMA(46) und EMA(48) verlieren
Monte-Carlo                   Die Reihenfolge der Trades war guenstig
Regime-Aufteilung             Funktioniert nur im Bullenmarkt von 2021
Kosten-Stress                 Der Vorteil war nur ein zu mildes Kostenmodell
Deflated Sharpe               Nach 500 Versuchen sieht einer immer gut aus
============================  ==================================================

Ein Genom muss **alle** Gates bestehen. Das ist absichtlich hart: Die
teuerste Fehlentscheidung ist nicht, eine gute Strategie abzulehnen, sondern
eine schlechte zuzulassen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

import numpy as np
import pandas as pd
import structlog

from backtest.engine import BacktestConfig, Backtester
from backtest.metrics import compute_metrics
from backtest.walkforward import WalkForwardReport
from core.models import Trade
from strategy.compiler import compile_genome
from strategy.genome import Genome

log = structlog.get_logger(__name__)

#: Euler-Mascheroni-Konstante, gebraucht fuer den Deflated Sharpe Ratio.
EULER_MASCHERONI = 0.5772156649015329


class GateStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    status: GateStatus
    value: float
    threshold: float
    message: str

    @property
    def passed(self) -> bool:
        return self.status is not GateStatus.FAIL

    def describe(self) -> str:
        marker = {"pass": "OK", "fail": "DURCHGEFALLEN", "skip": "uebersprungen"}[
            self.status.value
        ]
        return f"[{marker}] {self.name}: {self.message}"


@dataclass(slots=True)
class GateReport:
    genome_id: str
    results: list[GateResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list[GateResult]:
        return [r for r in self.results if r.status is GateStatus.FAIL]

    def summary(self) -> str:
        if self.passed:
            return f"{self.genome_id}: alle {len(self.results)} Gates bestanden"
        names = ", ".join(r.name for r in self.failures)
        return (
            f"{self.genome_id}: durchgefallen bei {len(self.failures)} von "
            f"{len(self.results)} Gates ({names})"
        )

    def feedback_for_ai(self) -> str:
        """Rueckmeldung an die Research-KI.

        Das ist der Lernmechanismus: Nicht nur *dass* etwas durchgefallen ist,
        sondern mit welchem Wert gegen welche Schwelle. Ohne die Zahlen kann
        die KI nicht gezielt nachbessern und probiert nur blind weiter.
        """
        if self.passed:
            return "Alle Gates bestanden."
        return "\n".join(
            f"- {r.name}: {r.value:.3f} gegen Schwelle {r.threshold:.3f}. {r.message}"
            for r in self.failures
        )


@dataclass(frozen=True, slots=True)
class GateThresholds:
    """Die Zulassungsschwellen.

    Sie stehen bewusst hier im Code und nicht im Prompt der KI - sie sind
    Bedingung, nicht Verhandlungsgegenstand.
    """

    min_oos_trades: int = 100
    min_oos_sharpe: float = 1.0
    max_oos_drawdown_pct: float = 12.0
    min_window_consistency: float = 0.5
    min_plateau_ratio: float = 0.6
    max_monte_carlo_drawdown_pct: float = 15.0
    min_regime_profit_factor: float = 0.9
    cost_stress_factor: float = 2.0
    min_deflated_sharpe: float = 0.95


# ---------------------------------------------------------------------------
#  Einzelne Gates
# ---------------------------------------------------------------------------
def gate_sample_size(report: WalkForwardReport, t: GateThresholds) -> GateResult:
    """Genug Trades fuer eine belastbare Aussage?

    Ein Sharpe von 3,0 aus 12 Trades ist keine Aussage, sondern Rauschen. Erst
    ab rund 100 Trades wird der Standardfehler klein genug, dass ein Unterschied
    zwischen 0,8 und 1,2 ueberhaupt Bedeutung hat.
    """
    count = len(report.all_trades)
    passed = count >= t.min_oos_trades
    return GateResult(
        name="Stichprobengroesse",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=float(count),
        threshold=float(t.min_oos_trades),
        message=(
            f"{count} Trades ausserhalb der Trainingsdaten"
            if passed
            else f"Nur {count} Trades - zu wenig fuer eine belastbare Aussage. "
            "Haeufiger handelnde Bedingungen oder laengerer Zeitraum noetig."
        ),
    )


def gate_oos_sharpe(report: WalkForwardReport, t: GateThresholds) -> GateResult:
    sharpe = report.combined.sharpe if report.combined else 0.0
    passed = sharpe >= t.min_oos_sharpe
    return GateResult(
        name="Out-of-Sample-Sharpe",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=sharpe,
        threshold=t.min_oos_sharpe,
        message=(
            f"Sharpe {sharpe:.2f} ueber alle Testfenster"
            if passed
            else f"Sharpe {sharpe:.2f} unter der Schwelle - das Chance-Risiko-"
            "Verhaeltnis rechtfertigt den Betrieb nicht."
        ),
    )


def gate_drawdown(report: WalkForwardReport, t: GateThresholds) -> GateResult:
    """Bleibt der Rueckgang unter der Schmerzgrenze?

    Die Schwelle liegt bewusst unter dem Kill-Switch (12 % gegen 15 %): Eine
    Strategie, die im Backtest schon an die Abschaltgrenze stoesst, wird sie
    live mit Sicherheit reissen.
    """
    drawdown = report.combined.max_drawdown_pct if report.combined else 100.0
    passed = drawdown <= t.max_oos_drawdown_pct
    return GateResult(
        name="Drawdown",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=drawdown,
        threshold=t.max_oos_drawdown_pct,
        message=(
            f"Groesster Rueckgang {drawdown:.2f} %"
            if passed
            else f"Rueckgang {drawdown:.2f} % liegt zu nah am Kill-Switch von 15 %. "
            "Engere Stops oder frueherer Ausstieg noetig."
        ),
    )


def gate_consistency(report: WalkForwardReport, t: GateThresholds) -> GateResult:
    """Funktioniert die Strategie in der Mehrheit der Zeitfenster?

    Verhindert den haeufigsten Selbstbetrug: Eine Strategie, deren gesamter
    Gewinn aus einem einzigen guenstigen Quartal stammt, sieht ueber den
    Gesamtzeitraum hervorragend aus und ist trotzdem wertlos.
    """
    consistency = report.consistency
    passed = consistency >= t.min_window_consistency
    worst = report.worst_window
    detail = (
        f", schlechtestes Fenster {worst.metrics.net_profit:+.2f}"
        if worst is not None
        else ""
    )
    return GateResult(
        name="Bestaendigkeit",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=consistency,
        threshold=t.min_window_consistency,
        message=(
            f"{report.profitable_windows} von {report.window_count} Fenstern "
            f"profitabel{detail}"
        ),
    )


def gate_monte_carlo(
    trades: list[Trade],
    initial_equity: Decimal,
    t: GateThresholds,
    *,
    simulations: int = 1000,
    seed: int = 42,
) -> GateResult:
    """Wie schlimm haette es kommen koennen?

    Die tatsaechliche Reihenfolge der Trades ist nur eine von unendlich vielen
    moeglichen. Waeren die fuenf Verluste zufaellig hintereinander gefallen
    statt verteilt, waere der Drawdown deutlich groesser gewesen.

    Es wird die Reihenfolge vertauscht (nicht mit Zuruecklegen gezogen) - die
    Trades bleiben also dieselben, nur ihre Abfolge aendert sich. Geprueft wird
    das 95.-Perzentil des Rueckgangs: In 19 von 20 Faellen bleibt es darunter.
    """
    if len(trades) < 20:
        return GateResult(
            name="Monte-Carlo",
            status=GateStatus.SKIP,
            value=0.0,
            threshold=t.max_monte_carlo_drawdown_pct,
            message="Zu wenige Trades fuer eine sinnvolle Simulation",
        )

    pnls = np.array([float(trade.net_pnl) for trade in trades])
    start = float(initial_equity)
    rng = np.random.default_rng(seed)

    drawdowns = np.empty(simulations)
    for i in range(simulations):
        shuffled = rng.permutation(pnls)
        equity = start + np.cumsum(shuffled)
        peak = np.maximum.accumulate(np.concatenate(([start], equity)))
        curve = np.concatenate(([start], equity))
        with np.errstate(divide="ignore", invalid="ignore"):
            relative = np.where(peak > 0, (peak - curve) / peak * 100, 0.0)
        drawdowns[i] = relative.max()

    percentile_95 = float(np.percentile(drawdowns, 95))
    passed = percentile_95 <= t.max_monte_carlo_drawdown_pct

    return GateResult(
        name="Monte-Carlo",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=percentile_95,
        threshold=t.max_monte_carlo_drawdown_pct,
        message=(
            f"95.-Perzentil des Rueckgangs bei {percentile_95:.2f} % "
            f"(Median {np.median(drawdowns):.2f} %)"
            if passed
            else f"Bei unguenstiger Reihenfolge waeren {percentile_95:.2f} % Rueckgang "
            "moeglich - der Kill-Switch wuerde greifen."
        ),
    )


def gate_regime_split(
    trades: list[Trade], frame: pd.DataFrame, t: GateThresholds
) -> GateResult:
    """Funktioniert die Strategie in jedem Marktumfeld?

    Der Zeitraum wird in Aufwaerts-, Abwaerts- und Seitwaertsphasen zerlegt und
    das Ergebnis je Phase getrennt betrachtet. Eine Strategie, die nur im
    Bullenmarkt von 2021 verdient, ist keine Strategie - sie ist eine
    Long-Position mit Zusatzschritten.

    Geprueft wird der Profitfaktor je Umfeld, nicht der absolute Gewinn: In
    einer kurzen Phase sind kleine Betraege normal, ein Faktor unter 1 zeigt
    dagegen einen echten strukturellen Nachteil.
    """
    if len(trades) < 30 or frame.empty:
        return GateResult(
            name="Regime-Aufteilung",
            status=GateStatus.SKIP,
            value=0.0,
            threshold=t.min_regime_profit_factor,
            message="Zu wenige Trades fuer eine Aufteilung nach Marktumfeld",
        )

    regimes = classify_regimes(frame)
    buckets: dict[str, list[float]] = {"aufwaerts": [], "abwaerts": [], "seitwaerts": []}

    for trade in trades:
        regime = _regime_at(regimes, trade.entry_time)
        if regime is not None:
            buckets[regime].append(float(trade.net_pnl))

    worst_name = ""
    worst_factor = math.inf
    details: list[str] = []

    for name, values in buckets.items():
        if len(values) < 10:
            details.append(f"{name}: nur {len(values)} Trades")
            continue
        wins = sum(v for v in values if v > 0)
        losses = abs(sum(v for v in values if v <= 0))
        factor = wins / losses if losses > 0 else math.inf
        details.append(f"{name}: {len(values)} Trades, Faktor {factor:.2f}")
        if factor < worst_factor:
            worst_factor, worst_name = factor, name

    if worst_factor is math.inf:
        return GateResult(
            name="Regime-Aufteilung",
            status=GateStatus.SKIP,
            value=0.0,
            threshold=t.min_regime_profit_factor,
            message="Kein Marktumfeld mit genug Trades - " + "; ".join(details),
        )

    passed = worst_factor >= t.min_regime_profit_factor
    return GateResult(
        name="Regime-Aufteilung",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=worst_factor,
        threshold=t.min_regime_profit_factor,
        message=(
            "; ".join(details)
            if passed
            else f"Schwaechstes Umfeld '{worst_name}' mit Faktor {worst_factor:.2f}. "
            + "; ".join(details)
        ),
    )


def gate_cost_stress(
    genome: Genome,
    frame: pd.DataFrame,
    config: BacktestConfig,
    t: GateThresholds,
    *,
    sub_frame: pd.DataFrame | None = None,
) -> GateResult:
    """Ueberlebt die Strategie doppelte Kosten?

    Der ehrlichste aller Gates. Gebuehren und Slippage sind die einzigen
    Groessen im Backtest, die man garantiert unterschaetzt: Der reale Spread ist
    breiter, die reale Ausfuehrung schlechter, und PostOnly-Limits fuellen
    seltener als angenommen. Wer bei doppelten Kosten in den Verlust rutscht,
    hatte nie einen Vorteil - nur ein mildes Modell.
    """
    stressed_config = BacktestConfig(
        instrument=config.instrument,
        risk=config.risk,
        costs=config.costs.scaled(Decimal(str(t.cost_stress_factor))),
        funding=config.funding,
        initial_equity=config.initial_equity,
        allow_shorts=config.allow_shorts,
        entry_expiry_bars=config.entry_expiry_bars,
        max_hold_bars=config.max_hold_bars,
    )
    result = Backtester(stressed_config).run(frame, compile_genome(genome), sub_frame=sub_frame)
    metrics = compute_metrics(
        result.trades,
        result.equity_curve,
        initial_equity=config.initial_equity,
        total_fees=result.total_fees,
    )
    passed = metrics.net_profit > 0

    return GateResult(
        name="Kosten-Stress",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=metrics.net_profit,
        threshold=0.0,
        message=(
            f"Bei {t.cost_stress_factor:g}-fachen Kosten noch "
            f"{metrics.net_profit:+.2f} Gewinn"
            if passed
            else f"Bei {t.cost_stress_factor:g}-fachen Kosten {metrics.net_profit:+.2f} - "
            "der Vorteil war nur ein zu mildes Kostenmodell."
        ),
    )


def gate_parameter_plateau(
    genome: Genome,
    frame: pd.DataFrame,
    config: BacktestConfig,
    t: GateThresholds,
    *,
    variation: float = 0.2,
    sub_frame: pd.DataFrame | None = None,
) -> GateResult:
    """Steht die Strategie auf einem Plateau oder auf einer Nadelspitze?

    Alle Indikatorperioden werden um plus/minus 20 % variiert. Bleibt die
    Strategie dabei profitabel, hat sie einen echten Vorteil gefunden. Bricht
    sie ein, war der Gewinn nur eine zufaellig guenstige Parameterwahl - und
    live wird der Markt nicht dieselbe Nadelspitze treffen.

    Das ist der wirksamste Einzeltest gegen Ueberanpassung.
    """
    neighbours = list(_vary_periods(genome, variation))
    if not neighbours:
        return GateResult(
            name="Parameter-Plateau",
            status=GateStatus.SKIP,
            value=0.0,
            threshold=t.min_plateau_ratio,
            message="Genom hat keine variierbaren Perioden",
        )

    profitable = 0
    for neighbour in neighbours:
        result = Backtester(config).run(
            frame, compile_genome(neighbour), sub_frame=sub_frame
        )
        if result.net_profit > 0:
            profitable += 1

    ratio = profitable / len(neighbours)
    passed = ratio >= t.min_plateau_ratio

    return GateResult(
        name="Parameter-Plateau",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=ratio,
        threshold=t.min_plateau_ratio,
        message=(
            f"{profitable} von {len(neighbours)} Nachbar-Varianten profitabel"
            if passed
            else f"Nur {profitable} von {len(neighbours)} Nachbarn profitabel - "
            "die Strategie steht auf einer Nadelspitze, nicht auf einem Plateau."
        ),
    )


def gate_deflated_sharpe(
    trades: list[Trade], trials: int, t: GateThresholds
) -> GateResult:
    """Korrektur fuer die Zahl der Versuche.

    Wer 500 Strategien testet, findet mit Sicherheit eine, die gut aussieht -
    auch wenn alle 500 in Wahrheit wertlos sind. Der Deflated Sharpe Ratio
    (Bailey/Lopez de Prado) beziffert die Wahrscheinlichkeit, dass der
    beobachtete Vorteil echt ist und nicht das Ergebnis vieler Versuche.

    Deshalb zaehlt das Research-Journal jede geprueften Hypothese mit: Je mehr
    Versuche, desto hoeher die Huerde. Das ist der eingebaute Schutz davor,
    dass die KI sich durch schiere Menge einen Erfolg erschleicht.

    **Einheiten beachten:** Gerechnet wird mit dem Sharpe **je Trade**, nicht
    mit dem annualisierten. Die Nullverteilung der Formel bezieht sich auf
    Beobachtungen; wer einen annualisierten Wert (Faktor sqrt(365)) einsetzt,
    vergleicht Groessen unterschiedlicher Einheit und bekommt Unsinn heraus.

    Schiefe und Woelbung fliessen aus der tatsaechlichen Trade-Verteilung ein -
    genau dafuer ist die Korrektur gedacht: Eine Strategie mit wenigen sehr
    grossen Gewinnen hat einen aufgeblaehten Sharpe, den die Formel abwertet.
    """
    if len(trades) < 30:
        return GateResult(
            name="Deflated Sharpe",
            status=GateStatus.SKIP,
            value=0.0,
            threshold=t.min_deflated_sharpe,
            message="Zu wenige Trades fuer die Korrektur",
        )

    pnls = np.array([float(trade.net_pnl) for trade in trades])
    spread = float(np.std(pnls, ddof=1))
    if spread <= 0:
        return GateResult(
            name="Deflated Sharpe",
            status=GateStatus.SKIP,
            value=0.0,
            threshold=t.min_deflated_sharpe,
            message="Keine Streuung in den Ergebnissen",
        )

    per_trade_sharpe = float(np.mean(pnls)) / spread
    centred = (pnls - np.mean(pnls)) / spread
    skew = float(np.mean(centred**3))
    kurtosis = float(np.mean(centred**4))

    dsr = deflated_sharpe_ratio(
        observed_sharpe=per_trade_sharpe,
        trials=max(trials, 1),
        sample_size=len(pnls),
        skew=skew,
        kurtosis=kurtosis,
    )
    passed = dsr >= t.min_deflated_sharpe

    return GateResult(
        name="Deflated Sharpe",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=dsr,
        threshold=t.min_deflated_sharpe,
        message=(
            f"Wahrscheinlichkeit {dsr:.1%}, dass der Vorteil nach {trials} "
            f"Versuchen echt ist (Sharpe je Trade {per_trade_sharpe:.3f})"
            if passed
            else f"Nach {trials} getesteten Hypothesen ist der Vorteil nur zu "
            f"{dsr:.1%} echt (Sharpe je Trade {per_trade_sharpe:.3f}, Schiefe "
            f"{skew:+.2f}) - zu wahrscheinlich Zufall."
        ),
    )


def deflated_sharpe_ratio(
    *,
    observed_sharpe: float,
    trials: int,
    sample_size: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    sharpe_variance: float | None = None,
) -> float:
    """Deflated Sharpe Ratio nach Bailey und Lopez de Prado.

    ``observed_sharpe`` ist der Sharpe **je Beobachtung** (hier: je Trade),
    nicht der annualisierte.

    Der erwartete Maximalwert unter der Nullhypothese lautet

        E[max SR] = sqrt(V) * [ (1-gamma) * Phi^-1(1 - 1/N)
                                + gamma  * Phi^-1(1 - 1/(N*e)) ]

    mit ``gamma`` als Euler-Mascheroni-Konstante, ``N`` als Zahl der Versuche
    und ``V`` als Streuung der Sharpe-Schaetzer ueber die Versuche. Ohne den
    Faktor ``sqrt(V)`` stuende dort eine Groesse in Standardabweichungen statt
    in Sharpe-Einheiten - ein haeufiger Umsetzungsfehler, der die Huerde
    absurd hoch setzt.

    Ist ``sharpe_variance`` nicht bekannt, wird die asymptotische Varianz des
    Sharpe-Schaetzers ``1/(n-1)`` verwendet.

    Rueckgabe: Wahrscheinlichkeit zwischen 0 und 1.
    """
    from statistics import NormalDist

    if sample_size < 3 or observed_sharpe <= 0:
        return 0.0

    normal = NormalDist()
    variance = sharpe_variance if sharpe_variance is not None else 1.0 / (sample_size - 1)

    if trials <= 1:
        expected_max = 0.0
    else:
        expected_max = math.sqrt(variance) * (
            (1 - EULER_MASCHERONI) * normal.inv_cdf(1 - 1 / trials)
            + EULER_MASCHERONI * normal.inv_cdf(1 - 1 / (trials * math.e))
        )

    denominator = math.sqrt(
        max(1 - skew * observed_sharpe + (kurtosis - 1) / 4 * observed_sharpe**2, 1e-9)
    )
    statistic = (observed_sharpe - expected_max) * math.sqrt(sample_size - 1) / denominator
    return float(normal.cdf(statistic))


# ---------------------------------------------------------------------------
#  Hilfsfunktionen
# ---------------------------------------------------------------------------
def classify_regimes(
    frame: pd.DataFrame, *, window: int = 480, threshold_pct: float = 5.0
) -> pd.DataFrame:
    """Teilt den Zeitraum in Aufwaerts-, Abwaerts- und Seitwaertsphasen.

    ``window`` ist die Zahl Kerzen, ueber die der Trend gemessen wird - bei
    15-Minuten-Kerzen sind 480 rund fuenf Tage. ``threshold_pct`` ist die
    Bewegung, ab der von einem Trend gesprochen wird.

    Bewusst rueckwaertsgerichtet (``rolling``): Die Einordnung darf nur Daten
    verwenden, die zu diesem Zeitpunkt vorlagen - sonst waere die Aufteilung
    selbst eine Form von Lookahead.
    """
    close = frame["close"]
    change = (close / close.shift(window) - 1) * 100

    regime = pd.Series("seitwaerts", index=frame.index, dtype=object)
    regime[change > threshold_pct] = "aufwaerts"
    regime[change < -threshold_pct] = "abwaerts"

    return pd.DataFrame({"time": frame["open_time"], "regime": regime})


def _regime_at(regimes: pd.DataFrame, moment) -> str | None:
    matches = regimes.loc[regimes["time"] <= pd.Timestamp(moment)]
    if matches.empty:
        return None
    return str(matches["regime"].iloc[-1])


def _vary_periods(genome: Genome, variation: float):
    """Erzeugt Nachbar-Genome mit variierten Indikatorperioden.

    Jede Periode wird einmal nach oben und einmal nach unten verschoben. Werte
    ausserhalb der erlaubten Grenzen werden uebersprungen - dort haette das
    Genom ohnehin nicht validiert.
    """
    from strategy.indicators import REGISTRY

    seen: set[str] = {genome.genome_id}

    for factor in (1 - variation, 1 + variation):
        payload = genome.model_dump(mode="json")
        changed = False

        for section in ("entry_long", "entry_short", "filters"):
            for condition in payload.get(section, []):
                for side in ("left", "right"):
                    operand = condition[side]
                    if operand["kind"] != "indicator":
                        continue
                    _, spec = REGISTRY[operand["name"]]
                    for key, value in list(operand["params"].items()):
                        low, high = spec.param_bounds[key]
                        candidate = max(low, min(high, round(value * factor)))
                        if candidate != value:
                            operand["params"][key] = candidate
                            changed = True

        if payload["stop"]["kind"] == "atr":
            low, high = 5, 50
            candidate = max(low, min(high, round(payload["stop"]["atr_period"] * factor)))
            if candidate != payload["stop"]["atr_period"]:
                payload["stop"]["atr_period"] = candidate
                changed = True

        if not changed:
            continue
        try:
            neighbour = Genome.model_validate(payload)
        except Exception:
            continue
        if neighbour.genome_id not in seen:
            seen.add(neighbour.genome_id)
            yield neighbour


# ---------------------------------------------------------------------------
#  Orchestrierung
# ---------------------------------------------------------------------------
def evaluate_gates(
    genome: Genome,
    walkforward: WalkForwardReport,
    frame: pd.DataFrame,
    config: BacktestConfig,
    *,
    trials_so_far: int,
    thresholds: GateThresholds | None = None,
    sub_frame: pd.DataFrame | None = None,
    run_expensive: bool = True,
) -> GateReport:
    """Alle Gates auf ein Genom anwenden.

    ``run_expensive`` schaltet die Gates ab, die weitere Backtests brauchen
    (Plateau, Kosten-Stress). Sinnvoll fuer eine schnelle Vorauswahl - fuer die
    Zulassung muessen sie laufen.
    """
    thresholds = thresholds or GateThresholds()
    report = GateReport(genome_id=genome.genome_id)

    report.results.append(gate_sample_size(walkforward, thresholds))
    report.results.append(gate_oos_sharpe(walkforward, thresholds))
    report.results.append(gate_drawdown(walkforward, thresholds))
    report.results.append(gate_consistency(walkforward, thresholds))
    report.results.append(
        gate_monte_carlo(walkforward.all_trades, config.initial_equity, thresholds)
    )
    report.results.append(gate_regime_split(walkforward.all_trades, frame, thresholds))

    report.results.append(
        gate_deflated_sharpe(walkforward.all_trades, trials_so_far, thresholds)
    )

    if run_expensive:
        report.results.append(
            gate_cost_stress(genome, frame, config, thresholds, sub_frame=sub_frame)
        )
        report.results.append(
            gate_parameter_plateau(genome, frame, config, thresholds, sub_frame=sub_frame)
        )

    log.info("gates.ausgewertet", zusammenfassung=report.summary())
    return report
