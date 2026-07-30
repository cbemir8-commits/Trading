"""Datenqualitaetspruefung.

Ein Backtest ist nur so ehrlich wie seine Daten. Die typischen stillen Fehler,
gegen die hier geprueft wird:

* **Luecken.** Fehlt ein halber Tag, springt der Preis im Backtest und eine
  Ausbruchsstrategie meldet einen Traumtrade, den es nie gab.
* **Duplikate.** Doppelte Zeitstempel lassen Indikatoren zweimal ueber dieselbe
  Kerze laufen und verfaelschen jeden gleitenden Durchschnitt.
* **Unsortierte Reihen.** Bybit liefert absteigend. Wird das uebersehen, laeuft
  der Backtest rueckwaerts durch die Zeit - und sieht dabei erstaunlich gut aus.
* **Nullvolumen-Kerzen.** Meist Wartungsfenster der Boerse. Handelbar waren sie
  nicht, also duerfen dort auch keine Signale entstehen.
* **Preissprunge.** Entweder echte Marktereignisse (Flash-Crash) oder kaputte
  Daten. Beides muss man sehen, bevor man einer Kennzahl glaubt.

Die Pruefung loescht nichts. Sie berichtet - die Entscheidung, was mit einer
Auffaelligkeit passiert, gehoert nicht in eine Pruefroutine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

import numpy as np
import pandas as pd

from core.models import Interval


class Severity(StrEnum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Gap:
    """Eine Luecke in der Zeitreihe."""

    start: datetime
    end: datetime
    missing_candles: int

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def describe(self) -> str:
        return (
            f"{self.start:%Y-%m-%d %H:%M} bis {self.end:%Y-%m-%d %H:%M} "
            f"({self.missing_candles} Kerzen fehlen)"
        )


@dataclass(frozen=True, slots=True)
class Finding:
    severity: Severity
    code: str
    message: str


@dataclass(slots=True)
class QualityReport:
    symbol: str
    interval: Interval
    rows: int
    first: datetime | None
    last: datetime | None

    expected_rows: int = 0
    duplicates: int = 0
    unsorted: bool = False
    zero_volume: int = 0
    gaps: list[Gap] = field(default_factory=list)
    extreme_moves: list[tuple[datetime, float]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def completeness(self) -> float:
        """Anteil vorhandener Kerzen, 0..1."""
        if self.expected_rows <= 0:
            return 1.0
        return min(1.0, self.rows / self.expected_rows)

    @property
    def missing_candles(self) -> int:
        return sum(g.missing_candles for g in self.gaps)

    @property
    def worst_severity(self) -> Severity:
        if any(f.severity is Severity.ERROR for f in self.findings):
            return Severity.ERROR
        if any(f.severity is Severity.WARN for f in self.findings):
            return Severity.WARN
        return Severity.INFO

    @property
    def is_usable(self) -> bool:
        """Taugt die Reihe fuer einen Backtest?"""
        return self.worst_severity is not Severity.ERROR

    def summary(self) -> str:
        if self.rows == 0:
            return f"{self.symbol} {self.interval.label}: keine Daten"
        return (
            f"{self.symbol} {self.interval.label}: {self.rows:,} Kerzen, "
            f"{self.first:%Y-%m-%d} bis {self.last:%Y-%m-%d}, "
            f"Vollstaendigkeit {self.completeness:.4%}, "
            f"{len(self.gaps)} Luecken ({self.missing_candles:,} Kerzen)"
        ).replace(",", ".")


def check_candles(
    frame: pd.DataFrame,
    *,
    symbol: str,
    interval: Interval,
    max_gap_tolerance: float = 0.001,
    extreme_move_sigma: float = 12.0,
) -> QualityReport:
    """Zeitreihe pruefen.

    ``max_gap_tolerance`` ist der Anteil fehlender Kerzen, ab dem gewarnt wird
    (Standard 0,1 %). ``extreme_move_sigma`` markiert Preisspruenge jenseits von
    N Standardabweichungen - bei 12 Sigma sind das echte Ausreisser, keine
    normale Volatilitaet.
    """
    if frame.empty:
        report = QualityReport(
            symbol=symbol, interval=interval, rows=0, first=None, last=None
        )
        report.findings.append(
            Finding(Severity.ERROR, "leer", "Keine Kerzen vorhanden - Backfill noetig.")
        )
        return report

    times = frame["open_time"]
    first = times.iloc[0].to_pydatetime()
    last = times.iloc[-1].to_pydatetime()

    report = QualityReport(
        symbol=symbol,
        interval=interval,
        rows=len(frame),
        first=first,
        last=last,
        expected_rows=int((last - first) / interval.duration) + 1,
    )

    _check_ordering(frame, report)
    _check_duplicates(frame, report)
    _check_gaps(frame, interval, report, max_gap_tolerance)
    _check_volume(frame, report)
    _check_extreme_moves(frame, report, extreme_move_sigma)

    if not report.findings:
        report.findings.append(
            Finding(Severity.INFO, "ok", "Keine Auffaelligkeiten gefunden.")
        )
    return report


def _check_ordering(frame: pd.DataFrame, report: QualityReport) -> None:
    times = frame["open_time"]
    if not times.is_monotonic_increasing:
        report.unsorted = True
        report.findings.append(
            Finding(
                Severity.ERROR,
                "unsortiert",
                "Zeitstempel sind nicht aufsteigend. Bybit liefert Kerzen absteigend - "
                "vermutlich wurde die Umkehr im Adapter uebersprungen. Ein Backtest auf "
                "diesen Daten laeuft rueckwaerts durch die Zeit.",
            )
        )


def _check_duplicates(frame: pd.DataFrame, report: QualityReport) -> None:
    duplicates = int(frame["open_time"].duplicated().sum())
    report.duplicates = duplicates
    if duplicates > 0:
        report.findings.append(
            Finding(
                Severity.ERROR,
                "duplikate",
                f"{duplicates} doppelte Zeitstempel. Indikatoren wuerden dieselbe "
                "Kerze mehrfach verarbeiten.",
            )
        )


def _check_gaps(
    frame: pd.DataFrame, interval: Interval, report: QualityReport, tolerance: float
) -> None:
    times = frame["open_time"]
    if len(times) < 2:
        return

    step = pd.Timedelta(interval.duration)
    deltas = times.diff()
    gap_positions = deltas > step

    for idx in np.flatnonzero(gap_positions.to_numpy()):
        gap_start = times.iloc[idx - 1].to_pydatetime() + interval.duration
        gap_end = times.iloc[idx].to_pydatetime()
        missing = int((gap_end - gap_start) / interval.duration)
        if missing > 0:
            report.gaps.append(Gap(gap_start, gap_end, missing))

    if not report.gaps:
        return

    missing_ratio = report.missing_candles / max(report.expected_rows, 1)
    biggest = max(report.gaps, key=lambda g: g.missing_candles)

    # Kurze Luecken in 1-Minuten-Daten sind normal - in Minuten ohne einen
    # einzigen Handel liefert Bybit keine Kerze. Erst Haeufung oder lange
    # Ausfaelle sind ein Problem.
    if missing_ratio > tolerance * 10:
        severity = Severity.ERROR
    elif missing_ratio > tolerance:
        severity = Severity.WARN
    else:
        severity = Severity.INFO

    report.findings.append(
        Finding(
            severity,
            "luecken",
            f"{len(report.gaps)} Luecken, {report.missing_candles} Kerzen fehlen "
            f"({missing_ratio:.4%}). Groesste: {biggest.describe()}.",
        )
    )


def _check_volume(frame: pd.DataFrame, report: QualityReport) -> None:
    zero = int((frame["volume"] <= 0).sum())
    report.zero_volume = zero
    if zero == 0:
        return

    ratio = zero / len(frame)
    severity = Severity.WARN if ratio > 0.001 else Severity.INFO
    report.findings.append(
        Finding(
            severity,
            "nullvolumen",
            f"{zero} Kerzen ohne Volumen ({ratio:.4%}). Meist Wartungsfenster der "
            "Boerse - dort duerfen keine Signale entstehen.",
        )
    )


def _check_extreme_moves(frame: pd.DataFrame, report: QualityReport, sigma: float) -> None:
    """Sucht Preissprunge weit jenseits der normalen Volatilitaet.

    Verwendet die robuste Streuung (Median der absoluten Abweichungen) statt der
    Standardabweichung: Ein einzelner Ausreisser blaeht die Standardabweichung so
    auf, dass er sich selbst versteckt.
    """
    if len(frame) < 100:
        return

    closes = frame["close"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        returns = np.diff(np.log(closes))
    returns = returns[np.isfinite(returns)]
    if returns.size < 100:
        return

    median = float(np.median(returns))
    mad = float(np.median(np.abs(returns - median)))
    if mad <= 0:
        return
    robust_sigma = mad * 1.4826  # Umrechnung MAD -> Standardabweichung

    threshold = sigma * robust_sigma
    outlier_idx = np.flatnonzero(np.abs(returns - median) > threshold)

    for idx in outlier_idx[:20]:  # nur die ersten 20 berichten
        moment = frame["open_time"].iloc[int(idx) + 1].to_pydatetime()
        report.extreme_moves.append((moment, float(returns[idx]) * 100))

    if outlier_idx.size > 0:
        worst = max(report.extreme_moves, key=lambda m: abs(m[1]))
        report.findings.append(
            Finding(
                Severity.INFO,
                "preissprunge",
                f"{outlier_idx.size} Kerzen mit Preissprung ueber {sigma:.0f} Sigma. "
                f"Groesster: {worst[1]:+.2f} % am {worst[0]:%Y-%m-%d %H:%M}. "
                "Entweder echtes Marktereignis oder kaputte Daten - vor "
                "Kennzahlen-Interpretation ansehen.",
            )
        )
