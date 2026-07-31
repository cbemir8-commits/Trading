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
) -> AdmissionReport:
    """Alle Kandidaten pruefen und einen Champion bestimmen."""
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
