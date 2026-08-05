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
Schlechtestes Jahr            Kurzer Einbruch oder zwei Jahre Duerre - gleicher DD
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

from backtest.costs import CostModel
from backtest.engine import BacktestConfig, Backtester
from backtest.metrics import compute_metrics
from backtest.walkforward import (
    WalkForwardReport,
    chained_curve,
    worst_rolling_return,
)
from core.models import Trade
from research.benchmark import benchmark_at_equal_risk, buy_and_hold_over_windows
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
    """Fuer wettende Strategien: Jeder Trade ist eine Beobachtung."""

    min_oos_days_in_market: int = 250
    """Fuer investierte Strategien: Ein Handelsjahr gemeinsame Zeit mit dem
    Markt. Dort ist nicht der Trade die Beobachtung, sondern der Tag."""

    min_oos_entries: int = 10
    """Auch eine investierte Strategie braucht mehr als eine Entscheidung -
    sonst haengt das Ergebnis an einem einzigen gluecklichen Einstieg."""

    min_benchmark_edge: float = 1.0
    """Vielfaches der risikobereinigten Messlatte. 1,0 heisst: mindestens
    gleichauf mit Kaufen-und-Halten. Weniger zu fordern hiesse, Aufwand,
    Gebuehren und Liquidationsrisiko fuer nichts in Kauf zu nehmen."""

    min_cagr_pct: float = 15.0
    """Jahresrendite, unter der sich der Betrieb nicht lohnt.

    Diese Schwelle ist **kein statistisches Kriterium**, sondern eine
    wirtschaftliche Entscheidung, und sie soll auch so gelesen werden: Ein
    System, das 3 % im Jahr macht, ist vielleicht sauber gerechnet, deckt aber
    weder die laufenden Kosten noch den Aufwand.

    Sie steht hier statt der naheliegenden Forderung "mindestens die Haelfte
    der Rendite der Messlatte". Die waere unerfuellbar gewesen: BTC hat sich
    von 2020 bis 2026 vervielfacht, aber mit rund 77 % Rueckgang. Die Haelfte
    dieser Rendite bei den geforderten hoechstens 12 % Rueckgang gibt es nicht -
    die Bedingung haette jede denkbare Strategie ausgeschlossen und dabei so
    ausgesehen, als sei keine gut genug.

    Die risikobereinigte Bedingung darueber macht die eigentliche Arbeit: Sie
    fragt, ob dieselbe Rendite mit weniger Rueckgang erkauft wurde."""

    min_oos_sharpe: float = 1.0
    max_oos_drawdown_pct: float = 12.0
    min_window_consistency: float = 0.5

    worst_year_pct: float = -10.0
    """Die schlechteste Zwoelfmonatsperiode darf nicht schlimmer sein als das.

    Beantwortet, was der maximale Rueckgang offenlaesst: Ein kurzer tiefer
    Einbruch und eine zwei Jahre lange Duerre koennen denselben Wert haben -
    auszuhalten sind sie voellig verschieden. Wer nach zwoelf Monaten noch
    12 % im Minus steht, hoert auf, egal was die Rechnung sagt.

    -10 % liegt bewusst innerhalb des Kill-Switch von 15 %."""

    min_active_windows: int = 6
    """So viele Fenster muessen ueberhaupt einen Trade enthalten, bevor die
    Bestaendigkeitsquote etwas bedeutet.

    Ohne diese Schranke waere die Quote ein Schlupfloch: Wer in einem einzigen
    Fenster handelt und gewinnt, haette 100 % Bestaendigkeit."""
    min_plateau_ratio: float = 0.6
    max_monte_carlo_drawdown_pct: float = 15.0
    min_regime_profit_factor: float = 0.9
    cost_stress_factor: float = 2.0
    min_deflated_sharpe: float = 0.95


# ---------------------------------------------------------------------------
#  Einzelne Gates
# ---------------------------------------------------------------------------
def gate_sample_size(
    report: WalkForwardReport, t: GateThresholds, *, genome: Genome | None = None
) -> GateResult:
    """Genug Beobachtungen fuer eine belastbare Aussage?

    Ein Sharpe von 3,0 aus 12 Trades ist keine Aussage, sondern Rauschen. Erst
    ab rund 100 Trades wird der Standardfehler klein genug, dass ein Unterschied
    zwischen 0,8 und 1,2 ueberhaupt Bedeutung hat.

    **Was fuer eine wettende Strategie gilt, gilt nicht fuer eine investierte.**
    Diese Schwelle war lange die einzige, und sie hat eine ganze Klasse von
    Strategien ausgeschlossen, ohne je etwas ueber sie auszusagen: Wer
    monatelang investiert bleibt, kommt in sechs Jahren nie auf 100 Trades -
    sammelt dabei aber Tausende von Tagesergebnissen. Das ist mehr Information,
    nicht weniger, nur in anderer Form.

    Fuer Genome, die nach Kapitalanteil dimensionieren, zaehlt deshalb die
    **Zeit im Markt**, dazu eine Untergrenze an Ein- und Ausstiegen, damit das
    Ergebnis nicht an einer einzigen gluecklichen Entscheidung haengt.

    Diese Lockerung wird nicht verschenkt: Genau diese Klasse muss zusaetzlich
    das Messlatten-Gate bestehen - sie muss also Kaufen-und-Halten schlagen.
    Ohne diesen Zusatz waere "immer long" ein Kandidat, der hier durchspaziert.
    """
    count = len(report.all_trades)

    # **Jede** Bauform, die nach Kapital dimensioniert, ist eine investierte -
    # feste Quote wie Vola-Ziel. Hier stand einmal nur ``kapitalanteil``, und
    # als die dritte Betriebsart dazukam, fiel der beste Kandidat des Projekts
    # ploetzlich an der Stichprobengroesse durch: 17 Trades gegen 100. Der
    # Grund war nicht die Strategie, sondern dieser Vergleich.
    investiert = genome is not None and genome.sizing.kind != "risiko"

    if not investiert:
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

    stunden = report.combined.avg_duration_hours * count if report.combined else 0.0
    tage = stunden / 24.0
    passed = tage >= t.min_oos_days_in_market and count >= t.min_oos_entries
    return GateResult(
        name="Stichprobengroesse",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=round(tage, 1),
        threshold=float(t.min_oos_days_in_market),
        message=(
            f"{tage:.0f} Tage im Markt aus {count} Ein- und Ausstiegen"
            if passed
            else f"Nur {tage:.0f} Tage im Markt aus {count} Ein- und Ausstiegen "
            f"(noetig: {t.min_oos_days_in_market} Tage und "
            f"{t.min_oos_entries} Einstiege). Zu wenig gemeinsame Zeit mit dem "
            "Markt fuer eine belastbare Aussage."
        ),
    )


def gate_benchmark(
    report: WalkForwardReport,
    frame: pd.DataFrame,
    t: GateThresholds,
    *,
    costs: CostModel | None = None,
) -> GateResult:
    """Schlaegt die Strategie einfaches Halten - im selben Zeitraum?

    Die Frage, die zwei Generationen lang gefehlt hat. Sie ist nicht dieselbe
    wie "verdient die Strategie Geld": Ueber 2020 bis 2026 hat BTC sich
    vervielfacht. Eine Strategie mit 30 % Rendite in diesem Zeitraum klingt gut
    und ist trotzdem ein Verlustgeschaeft - Nichtstun haette mehr gebracht, ohne
    Gebuehren, ohne Nachtschichten, ohne Liquidationsrisiko.

    Gemessen wird auf **denselben Testfenstern**, nicht auf der ganzen
    Historie, und an zwei Bedingungen zugleich:

    * **risikobereinigt mindestens gleichauf** - die Messlatte wird auf den
      Rueckgang der Strategie skaliert. Zwei Drittel der Rendite bei einem
      Drittel des Rueckgangs ist der Messlatte ueberlegen, obwohl weniger
      verdient wird.
    * **kein Feigenblatt** - die Jahresrendite muss ueber der Schwelle liegen,
      unter der sich der Betrieb nicht lohnt. Sonst besteht eine Strategie, die
      fast nie investiert ist, allein durch ihren winzigen Rueckgang - und
      verdient nichts.
    """
    windows = [
        (w.window.test_start, w.window.test_end)
        for w in report.windows
        if w.window is not None
    ]
    if not windows or report.combined is None:
        return GateResult(
            name="Messlatte",
            status=GateStatus.SKIP,
            value=0.0,
            threshold=t.min_benchmark_edge,
            message="Keine Testfenster - nichts zu vergleichen",
        )

    halten_rendite, halten_rueckgang = buy_and_hold_over_windows(
        frame, windows, costs=costs
    )
    eigen = report.combined.total_return_pct
    messlatte = benchmark_at_equal_risk(
        halten_rendite, halten_rueckgang, report.combined.max_drawdown_pct
    )

    besser = eigen >= messlatte * t.min_benchmark_edge
    lohnend = report.combined.cagr_pct >= t.min_cagr_pct

    if besser and lohnend:
        zusatz = ""
    elif not besser:
        zusatz = " - risikobereinigt schlechter als Nichtstun."
    else:
        zusatz = (
            f" - risikobereinigt besser, aber nur {report.combined.cagr_pct:.1f} % "
            f"im Jahr. Unter {t.min_cagr_pct:.0f} % lohnt der Betrieb nicht."
        )

    return GateResult(
        name="Messlatte",
        status=GateStatus.PASS if besser and lohnend else GateStatus.FAIL,
        value=round(eigen, 3),
        threshold=round(messlatte * t.min_benchmark_edge, 3),
        message=(
            f"Strategie {report.combined.total_return_pct:+.1f} % bei "
            f"{report.combined.max_drawdown_pct:.1f} % Rueckgang "
            f"({report.combined.cagr_pct:+.1f} % p.a.), "
            f"Halten {halten_rendite:+.1f} % bei {halten_rueckgang:.1f} % "
            f"(auf gleiches Risiko gebracht: {messlatte:+.1f} %)"
            + zusatz
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
    aktiv = report.active_windows
    worst = report.worst_window
    detail = (
        f", schlechtestes Fenster {worst.metrics.net_profit:+.2f}"
        if worst is not None
        else ""
    )

    # Gezaehlt wird nur, wo gehandelt wurde - ein Fenster ohne Trade sagt
    # nichts darueber aus, ob die Strategie funktioniert. Damit daraus kein
    # Schlupfloch wird ("einmal handeln, gewinnen, 100 %"), braucht es genug
    # aktive Fenster, bevor die Quote ueberhaupt etwas bedeutet.
    if aktiv < t.min_active_windows:
        return GateResult(
            name="Bestaendigkeit",
            status=GateStatus.FAIL,
            value=float(aktiv),
            threshold=float(t.min_active_windows),
            message=(
                f"Nur {aktiv} von {report.window_count} Fenstern mit Handel - "
                f"zu wenige, um Bestaendigkeit zu beurteilen. Noetig sind "
                f"{t.min_active_windows}."
            ),
        )

    passed = consistency >= t.min_window_consistency
    ruhig = report.window_count - aktiv
    return GateResult(
        name="Bestaendigkeit",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=consistency,
        threshold=t.min_window_consistency,
        message=(
            f"{report.profitable_windows} von {aktiv} gehandelten Fenstern "
            f"profitabel{detail}"
            + (f" ({ruhig} Fenster ohne Handel, zaehlen nicht mit)" if ruhig else "")
        ),
    )


def gate_worst_year(report: WalkForwardReport, t: GateThresholds) -> GateResult:
    """Wie stuende jemand da, der zum unguenstigsten Zeitpunkt eingestiegen ist?

    Der maximale Rueckgang misst die Tiefe, aber nicht die Dauer. Eine
    Strategie, die binnen zwei Wochen 10 % verliert und sie in einem Monat
    zurueckholt, und eine, die zwei Jahre lang 10 % im Minus liegt, haben
    dieselbe Kennzahl - und sind voellig verschiedene Erfahrungen.

    Diese Pruefung nimmt die Kapitalkurve statt der Trades. Das ist bei
    langsamen Strategien der einzige Weg: Wer drei Mal im Jahr handelt, hat zu
    wenige Trades fuer eine Aussage, aber jeden Tag einen Kurvenpunkt.

    Ausdruecklich **zusaetzlich** zu den bestehenden Pruefungen und nicht an
    ihrer Stelle - es wird nichts weicher, es kommt eine Huerde dazu.
    """
    kurve = chained_curve(report)
    monate = _test_monate(report)
    schlechteste = worst_rolling_return(kurve, months=12, total_months=monate)

    if not math.isfinite(schlechteste):
        return GateResult(
            name="Schlechtestes Jahr",
            status=GateStatus.SKIP,
            value=0.0,
            threshold=t.worst_year_pct,
            message="Testzeitraum kuerzer als zwoelf Monate - nicht beurteilbar",
        )

    passed = schlechteste >= t.worst_year_pct
    return GateResult(
        name="Schlechtestes Jahr",
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=round(schlechteste, 2),
        threshold=t.worst_year_pct,
        message=(
            f"Wer zum unguenstigsten Zeitpunkt eingestiegen waere, stuende nach "
            f"zwoelf Monaten bei {schlechteste:+.1f} %"
            + ("" if passed else " - das haelt niemand durch.")
        ),
    )


def _test_monate(report: WalkForwardReport) -> float:
    """Laenge des gesamten Testzeitraums in Monaten."""
    fenster = [w.window for w in report.windows if w.window is not None]
    if not fenster:
        return 0.0
    tage = (max(w.test_end for w in fenster) - min(w.test_start for w in fenster)).days
    return tage / 30.44


def concurrent_groups(trades: list[Trade]) -> list[list[Trade]]:
    """Trades zusammenfassen, die sich zeitlich ueberschneiden.

    Zwei Positionen, die gleichzeitig offen sind, sind **keine zwei
    unabhaengigen Beobachtungen**. Faellt der Markt, treffen sie das Konto
    zusammen. Wer sie einzeln vertauscht, zieht genau die Verluste
    auseinander, die in Wirklichkeit gemeinsam kamen - und bekommt einen zu
    freundlichen Rueckgang heraus.

    Ueberschneidung wird transitiv behandelt: A ueberlappt B, B ueberlappt C,
    also gehoeren alle drei zusammen. Sie waren nacheinander gemeinsam offen
    und lassen sich nicht sinnvoll trennen.
    """
    if not trades:
        return []

    sortiert = sorted(trades, key=lambda x: x.entry_time)
    gruppen: list[list[Trade]] = [[sortiert[0]]]
    ende = sortiert[0].exit_time

    for trade in sortiert[1:]:
        if trade.entry_time < ende:
            gruppen[-1].append(trade)
            ende = max(ende, trade.exit_time)
        else:
            gruppen.append([trade])
            ende = trade.exit_time
    return gruppen


def gate_monte_carlo(
    trades: list[Trade],
    initial_equity: Decimal,
    t: GateThresholds,
    *,
    simulations: int = 1000,
    seed: int = 42,
    group_concurrent: bool = False,
) -> GateResult:
    """Wie schlimm haette es kommen koennen?

    Die tatsaechliche Reihenfolge der Trades ist nur eine von unendlich vielen
    moeglichen. Waeren die fuenf Verluste zufaellig hintereinander gefallen
    statt verteilt, waere der Drawdown deutlich groesser gewesen.

    Es wird die Reihenfolge vertauscht (nicht mit Zuruecklegen gezogen) - die
    Trades bleiben also dieselben, nur ihre Abfolge aendert sich. Geprueft wird
    das 95.-Perzentil des Rueckgangs: In 19 von 20 Faellen bleibt es darunter.

    ``group_concurrent`` fasst vorher zeitgleich offene Positionen zusammen.
    Bei mehreren Maerkten ist das noetig: Sonst wuerde die Simulation
    unterstellen, dass ein BTC- und ein ETH-Verlust vom selben Tag unabhaengig
    voneinander eintreten konnten. **Das Ergebnis wird dadurch strenger, nie
    milder** - gemessen an BTC+ETH stieg das 95.-Perzentil von 28,46 % auf
    33,25 % (51 Trades, 43 unabhaengige Zeitraeume). Bei einem einzelnen Markt
    aendert sich nichts, weil dort nie zwei Positionen gleichzeitig offen sind:
    BTC 51,52 % vor und nach der Gruppierung, ETH 13,35 %.

    Wer die Gruppierung weglaesst, bekommt die freundlichere Zahl; genau
    deshalb ist sie bei Portfolios eingeschaltet.
    """
    if len(trades) < 20:
        return GateResult(
            name="Monte-Carlo",
            status=GateStatus.SKIP,
            value=0.0,
            threshold=t.max_monte_carlo_drawdown_pct,
            message="Zu wenige Trades fuer eine sinnvolle Simulation",
        )

    if group_concurrent:
        gruppen = concurrent_groups(trades)
        pnls = np.array(
            [float(sum(x.net_pnl for x in gruppe)) for gruppe in gruppen]
        )
        if len(pnls) < 20:
            return GateResult(
                name="Monte-Carlo",
                status=GateStatus.SKIP,
                value=0.0,
                threshold=t.max_monte_carlo_drawdown_pct,
                message=(
                    f"{len(trades)} Trades bilden nur {len(pnls)} unabhaengige "
                    "Zeitraeume - zu wenige fuer eine sinnvolle Simulation"
                ),
            )
    else:
        pnls = np.array([float(trade.net_pnl) for trade in trades])
    start = float(initial_equity)
    rng = np.random.default_rng(seed)

    drawdowns = np.empty(simulations)
    for i in range(simulations):
        shuffled = rng.permutation(pnls)
        # Bei null ist Schluss - auch in der Simulation. Ohne diese Grenze
        # laeuft die Kurve ins Minus und meldet Drawdowns jenseits von 100 %,
        # so wie es die Kapitalkurve vor der Korrektur tat. Ein Konto, das
        # aufgebraucht ist, handelt die restlichen Trades nicht mehr mit.
        equity = np.maximum(start + np.cumsum(shuffled), 0.0)
        curve = np.concatenate(([start], equity))
        peak = np.maximum.accumulate(curve)
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

    report.results.append(gate_sample_size(walkforward, thresholds, genome=genome))
    report.results.append(gate_benchmark(walkforward, frame, thresholds))
    report.results.append(gate_oos_sharpe(walkforward, thresholds))
    report.results.append(gate_drawdown(walkforward, thresholds))
    report.results.append(gate_worst_year(walkforward, thresholds))
    report.results.append(gate_consistency(walkforward, thresholds))
    # Bei mehreren Maerkten muessen zeitgleiche Positionen zusammenbleiben.
    # Erkannt wird das an den Symbolen der Trades, nicht an einem Schalter -
    # ein Schalter waere etwas, das man vergisst.
    maerkte = {trade.symbol for trade in walkforward.all_trades}
    report.results.append(
        gate_monte_carlo(
            walkforward.all_trades,
            config.initial_equity,
            thresholds,
            group_concurrent=len(maerkte) > 1,
        )
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
