"""Die Zulassungsstrecke: von Kandidaten zum Champion.

Jedes Genom durchlaeuft dieselben Stationen:

    Genom -> Compiler -> Walk-Forward -> neun Gates -> zugelassen / abgelehnt

Danach wird unter den Zugelassenen **ein** Champion bestimmt und in
``strategies/champion.json`` geschrieben. Nur dieser wird gehandelt.

Zwei Entscheidungen, die hier getroffen werden und die man leicht falsch trifft:

**Der Versuchszaehler wird dauerhaft gespeichert.** Die Deflated Sharpe Ratio
korrigiert dafuer, dass man bei genug Versuchen irgendwann zufaellig etwas
Gutaussehendes findet. Sie braucht dazu die Zahl **aller je getesteten**
Kandidaten - nicht die des aktuellen Laufs. Wer den Zaehler bei jedem Aufruf
zuruecksetzt, hebelt genau die Korrektur aus, die verhindert, dass Zufall als
Strategie durchgeht. Nach hundert Laeufen mit je fuenf Genomen sind es 500
Versuche, nicht fuenf.

**Der Champion wird nach Bestaendigkeit gewaehlt, nicht nach Rendite.** Unter
Kandidaten, die alle neun Gates bestanden haben, liegen die Renditeunterschiede
im Rauschen - wer danach auswaehlt, waehlt Rauschen aus. Der Anteil profitabler
Fenster sagt mehr darueber, ob eine Strategie naechsten Monat noch funktioniert.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import structlog

from backtest.engine import BacktestConfig
from backtest.portfolio_walkforward import run_portfolio_walkforward
from backtest.walkforward import (
    WalkForwardReport,
    WalkForwardSplitter,
    run_walkforward,
)
from research.gates import GateReport, GateThresholds, evaluate_gates
from strategy.compiler import compile_genome
from strategy.genome import Genome

log = structlog.get_logger(__name__)


@dataclass(slots=True)
class Candidate:
    """Ein geprueftes Genom samt Begruendung des Ergebnisses."""

    genome: Genome
    walkforward: WalkForwardReport
    gates: GateReport

    @property
    def admitted(self) -> bool:
        return self.gates.passed

    @property
    def consistency(self) -> float:
        return self.walkforward.consistency

    @property
    def sharpe(self) -> float:
        combined = self.walkforward.combined
        return combined.sharpe if combined else 0.0

    @property
    def trades(self) -> int:
        return len(self.walkforward.all_trades)

    def describe(self) -> str:
        mark = "ZUGELASSEN" if self.admitted else "abgelehnt"
        return (
            f"{self.genome.name}: {mark} | {self.trades} Trades, "
            f"Sharpe {self.sharpe:.2f}, {self.consistency:.0%} Fenster profitabel"
        )


@dataclass(slots=True)
class AdmissionReport:
    candidates: list[Candidate] = field(default_factory=list)
    champion: Candidate | None = None
    trials_before: int = 0
    trials_after: int = 0

    @property
    def admitted(self) -> list[Candidate]:
        return [c for c in self.candidates if c.admitted]

    def summary(self) -> str:
        if self.champion is None:
            return (
                f"{len(self.candidates)} Kandidaten geprueft, keiner zugelassen "
                f"(Versuche gesamt: {self.trials_after})"
            )
        return (
            f"{len(self.admitted)} von {len(self.candidates)} zugelassen, "
            f"Champion: {self.champion.genome.name} "
            f"(Versuche gesamt: {self.trials_after})"
        )


def load_trials(path: Path | str) -> int:
    """Wie viele Kandidaten wurden insgesamt schon getestet?

    Bewusst fehlertolerant: Eine fehlende oder kaputte Datei liefert 0. Das
    ist die konservative Richtung nur auf den ersten Blick - ein zu niedriger
    Zaehler macht die Deflated Sharpe Ratio **milder**. Deshalb wird ein
    Lesefehler laut protokolliert.
    """
    file = Path(path)
    if not file.exists():
        return 0
    try:
        return int(json.loads(file.read_text())["trials"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        log.error(
            "zulassung.zaehler_unlesbar",
            fehler=str(exc),
            pfad=str(file),
            folge="Zaehler startet bei 0 - die Mehrfachtest-Korrektur faellt "
            "dadurch zu milde aus",
        )
        return 0


def save_trials(path: Path | str, trials: int) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {"trials": trials, "updated_at": datetime.now(UTC).isoformat()}, indent=2
        )
    )
    temporary.replace(file)


def run_admission(
    genomes: list[Genome],
    frame: pd.DataFrame,
    config: BacktestConfig,
    *,
    trials_so_far: int = 0,
    splitter: WalkForwardSplitter | None = None,
    thresholds: GateThresholds | None = None,
    sub_frame: pd.DataFrame | None = None,
    run_expensive: bool = True,
    on_progress=None,
    frames: dict[str, pd.DataFrame] | None = None,
    configs: dict[str, BacktestConfig] | None = None,
) -> AdmissionReport:
    """Alle Kandidaten pruefen und einen Champion bestimmen.

    **``frames`` und ``configs`` sind kein Zusatz, sondern eine Korrektur.**

    Bis hierher nahm diese Funktion genau *einen* Markt. Der Wettbewerb suchte
    damit auf BTC allein, waehrend jede Zulassungszahl des Projekts aus dem
    Portfolio BTC + ETH stammt - und das ist nicht dasselbe Ziel:

        Spitzenkandidat auf BTC allein     5 von 11, Deflated Sharpe 0,190
        Spitzenkandidat auf BTC + ETH      7 von 11, Deflated Sharpe 0,843

    Wer auf dem einen Berg sucht und auf dem anderen prueft, findet
    zuverlaessig das Falsche. Werden ``frames`` uebergeben, laeuft die Pruefung
    ueber dasselbe Portfolio, an dem spaeter geurteilt wird - im Walk-Forward
    **und** in den beiden Gates, die selbst nachrechnen. ``frame`` dient dann
    nur noch als Messlatte fuer Buy-and-Hold und die Regime-Einteilung.
    """
    splitter = splitter or WalkForwardSplitter()
    report = AdmissionReport(trials_before=trials_so_far)
    trials = trials_so_far

    for position, genome in enumerate(genomes, start=1):
        if on_progress is not None:
            on_progress(position, len(genomes), genome)

        # Jeder Kandidat erhoeht den Zaehler - auch ein durchgefallener. Ein
        # Versuch ist ein Versuch; nur die Erfolgreichen zu zaehlen waere
        # genau der Fehler, gegen den die Korrektur gebaut ist.
        trials += 1

        if frames:
            walkforward = run_portfolio_walkforward(
                frames,
                lambda g=genome: compile_genome(g),
                configs or config,
                splitter,
            )
        else:
            walkforward = run_walkforward(
                frame,
                lambda g=genome: compile_genome(g),
                config,
                splitter,
                sub_frame=sub_frame,
            )
        gates = evaluate_gates(
            genome,
            walkforward,
            frame,
            config,
            trials_so_far=trials,
            thresholds=thresholds,
            sub_frame=sub_frame,
            run_expensive=run_expensive,
            frames=frames,
            configs=configs,
        )
        candidate = Candidate(genome=genome, walkforward=walkforward, gates=gates)
        report.candidates.append(candidate)
        log.info("zulassung.kandidat", ergebnis=candidate.describe())

    report.trials_after = trials
    report.champion = pick_champion(report.admitted)
    log.info("zulassung.fertig", zusammenfassung=report.summary())
    return report


def pick_champion(admitted: list[Candidate]) -> Candidate | None:
    """Unter den Zugelassenen einen auswaehlen.

    Sortiert nach **Bestaendigkeit** (Anteil profitabler Fenster), erst bei
    Gleichstand nach Sharpe. Wer stattdessen die hoechste Rendite nimmt, waehlt
    unter lauter zugelassenen Kandidaten faktisch das guenstigste Rauschen -
    die Renditeunterschiede liegen dort innerhalb der Fehlergrenzen, die
    Bestaendigkeitsunterschiede nicht.
    """
    if not admitted:
        return None
    return max(admitted, key=lambda c: (round(c.consistency, 2), c.sharpe))


def ist_zugelassen(genome: Genome, path: Path | str) -> bool:
    """Ist **dieses** Genom der zugelassene Champion?

    Verglichen wird die ``genome_id``, nicht der Dateiname. Das ist der ganze
    Punkt: Eine Datei laesst sich umbenennen und kopieren, die Kennung nicht -
    sie ist der Hash ueber die Regeln. Ein Genom, das die elf Gates nie
    gesehen hat, kann sich damit nicht als Champion ausgeben, indem es an der
    richtigen Stelle liegt.

    Gebraucht wird das, seit es einen Weg gibt, einen **nicht** zugelassenen
    Kandidaten als Datei abzulegen (``cli anlagentest``). Ohne diese Pruefung
    haette ``cli trade --echtgeld --strategie anlagentest.json`` echtes Geld
    auf eine Strategie gesetzt, die vier Gates nicht bestanden hat.

    ``name`` und ``rationale`` fliessen nicht in die Kennung ein - der Warnhinweis
    im Namen aendert also nichts an der Identitaet.
    """
    file = Path(path)
    if not file.exists():
        return False
    try:
        champion = Genome.model_validate(json.loads(file.read_text()))
    except Exception:
        log.warning("zulassung.champion_unlesbar", pfad=str(file))
        return False
    return champion.genome_id == genome.genome_id


def write_champion(candidate: Candidate, path: Path | str) -> Path:
    """Den Champion dorthin schreiben, wo ``cli trade`` ihn sucht."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(candidate.genome.model_dump(mode="json"), indent=2))
    log.info(
        "zulassung.champion_geschrieben",
        pfad=str(file),
        genom=candidate.genome.genome_id,
        name=candidate.genome.name,
    )
    return file


def write_journal(report: AdmissionReport, path: Path | str) -> Path:
    """Das Forschungstagebuch fortschreiben.

    Jeder Lauf wird angehaengt, nichts ueberschrieben. Das ist die Grundlage
    fuer den spaeteren Research-Kreislauf: Die KI liest, was schon versucht
    wurde und woran es scheiterte. Ohne diese Historie probiert sie dieselben
    Ideen immer wieder - und jeder Wiederholungsversuch zaehlt trotzdem als
    Versuch in der Mehrfachtest-Korrektur.
    """
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)

    entries = []
    if file.exists():
        try:
            entries = json.loads(file.read_text())
        except json.JSONDecodeError:
            log.error("zulassung.journal_unlesbar", pfad=str(file))
            entries = []

    entries.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "trials_before": report.trials_before,
            "trials_after": report.trials_after,
            "champion": report.champion.genome.genome_id if report.champion else None,
            "candidates": [
                {
                    "genome_id": c.genome.genome_id,
                    "name": c.genome.name,
                    "rationale": c.genome.rationale,
                    "admitted": c.admitted,
                    "trades": c.trades,
                    "sharpe": round(c.sharpe, 3),
                    "consistency": round(c.consistency, 3),
                    "gate_feedback": c.gates.feedback_for_ai(),
                }
                for c in report.candidates
            ],
        }
    )
    file.write_text(json.dumps(entries, indent=2))
    return file


def report_payload(
    report: AdmissionReport,
    *,
    symbol: str,
    interval: str,
    history_from: str,
    history_to: str,
    candles: int,
    gates_full: bool,
    benchmark: dict | None = None,
    funding_rows: int = 0,
) -> dict:
    """Der vollstaendige Bericht eines Zulassungslaufs, maschinenlesbar.

    Absichtlich ausfuehrlicher als die Bildschirmausgabe. Auf dem Bildschirm
    zaehlt, was ein Mensch in zehn Sekunden erfassen kann; hier zaehlt, was
    eine spaetere Auswertung braucht - jeder Gate-Wert samt Schwelle, jedes
    einzelne Fenster, jede Ausstiegsart.

    Der Unterschied ist nicht kosmetisch. "Durchgefallen bei Sharpe" sagt
    nichts darueber, ob es knapp war oder aussichtslos, und ob es an allen
    Fenstern lag oder an einem einzigen. Genau daran entscheidet sich, ob eine
    Idee nachgebessert oder verworfen wird.
    """
    return {
        "art": "zulassung",
        "zeitpunkt": datetime.now(UTC).isoformat(),
        "markt": {
            "symbol": symbol,
            "intervall": interval,
            "historie_von": history_from,
            "historie_bis": history_to,
            "kerzen": candles,
            "funding_eintraege": funding_rows,
        },
        "lauf": {
            "kandidaten": len(report.candidates),
            "zugelassen": len(report.admitted),
            "versuche_vorher": report.trials_before,
            "versuche_nachher": report.trials_after,
            "gates": "vollstaendig" if gates_full else "schnell",
            "champion": report.champion.genome.name if report.champion else None,
        },
        "messlatte": benchmark,
        "kandidaten": [_candidate_payload(c) for c in report.candidates],
    }


def _candidate_payload(candidate: Candidate) -> dict:
    combined = candidate.walkforward.combined
    return {
        "name": candidate.genome.name,
        "genome_id": candidate.genome.genome_id,
        "hypothese": candidate.genome.rationale,
        "zugelassen": candidate.admitted,
        "genom": candidate.genome.model_dump(mode="json"),
        "gesamt": _metrics_payload(combined),
        "gates": [
            {
                "name": r.name,
                "status": r.status.value,
                "wert": round(r.value, 4),
                "schwelle": round(r.threshold, 4),
                "begruendung": r.message,
            }
            for r in candidate.gates.results
        ],
        "fenster": [
            {
                "nummer": w.window.index,
                "test_von": w.window.test_start.isoformat(),
                "test_bis": w.window.test_end.isoformat(),
                "profitabel": w.is_profitable,
                **(_metrics_payload(w.metrics) or {}),
            }
            for w in candidate.walkforward.windows
        ],
    }


def _metrics_payload(metrics) -> dict | None:
    """Kennzahlen in relativen Groessen.

    Absolute Betraege bleiben draussen - nicht aus Sparsamkeit, sondern weil
    der Bericht in ein oeffentliches Repository geht. Prozent und R sagen alles
    aus, was fuer die Bewertung noetig ist, und nichts ueber das Konto.
    """
    if metrics is None:
        return None
    return {
        "trades": metrics.trades,
        "rendite_pct": round(metrics.total_return_pct, 2),
        "cagr_pct": round(metrics.cagr_pct, 2),
        "sharpe": round(metrics.sharpe, 3),
        "sortino": round(metrics.sortino, 3),
        "max_drawdown_pct": round(metrics.max_drawdown_pct, 2),
        "trefferquote": round(metrics.win_rate, 4),
        "profit_faktor": round(metrics.profit_factor, 3),
        "erwartung_r": round(metrics.expectancy_r, 4),
        "trades_pro_monat": round(metrics.trades_per_month, 2),
        "gebuehren_pct_vom_brutto": round(metrics.fees_pct_of_gross, 2),
        "max_verluste_hintereinander": metrics.max_consecutive_losses,
        "haltedauer_stunden": round(metrics.avg_duration_hours, 1),
        "ausstiegsgruende": dict(metrics.exit_reasons),
    }
