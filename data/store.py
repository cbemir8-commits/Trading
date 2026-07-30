"""Speicher fuer historische Kerzen.

Aufteilung der Persistenz - bewusst zweigleisig:

* **Parquet** ist die Wahrheit fuer historische Kerzen. Ein Walk-Forward-Lauf
  scannt Millionen Zeilen spaltenweise; dafuer ist ein spaltenorientiertes
  Dateiformat um Groessenordnungen schneller als eine relationale Datenbank,
  und es braucht keinen laufenden Dienst.
* **Postgres** haelt den Betriebszustand: Trades, Positionen, Research-Journal,
  Kostenzaehler. Also alles, was transaktional und gleichzeitig les-/schreibbar
  sein muss.

Zahlentypen: Im Speicher liegen ``float64``. Das ist eine bewusste Abweichung
von der ``Decimal``-Regel des restlichen Systems:

* Der Rundungsfehler von float64 liegt bei BTC-Preisen um 100.000 bei etwa
  1e-11 - rund neun Groessenordnungen unter der Tick-Groesse von 0,1.
* Ein Backtest ueber 3,3 Mio. Kerzen mit ``Decimal`` waere zwei Groessenordnungen
  langsamer, und die Modellierungsunschaerfe des Fill-Modells ist um ein
  Vielfaches groesser als jeder float-Fehler.

``Decimal`` bleibt zwingend fuer alles, was tatsaechlich zur Boerse geht -
die Umwandlung passiert an der Grenze in ``execution/``.

Verzeichnisstruktur::

    data_store/candles/BTCUSDT/15/2026-01.parquet
                              ^      ^
                              |      Monatsdatei (macht Backfill resumierbar)
                              Bybit-Intervall-Code
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import structlog

from core.models import Candle, Interval

log = structlog.get_logger(__name__)

#: Spalten und Typen der Parquet-Dateien. Reihenfolge ist stabil.
SCHEMA: dict[str, str] = {
    "open_time": "datetime64[ns, UTC]",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "float64",
    "turnover": "float64",
}


@dataclass(frozen=True, slots=True)
class Coverage:
    """Welcher Zeitraum liegt fuer eine Zeitreihe vor."""

    start: datetime | None
    end: datetime | None
    rows: int

    @property
    def is_empty(self) -> bool:
        return self.rows == 0


def candles_to_frame(candles: list[Candle]) -> pd.DataFrame:
    """Kerzen in einen DataFrame umwandeln - inklusive Sortierung und Typisierung."""
    if not candles:
        return empty_frame()

    frame = pd.DataFrame(
        {
            "open_time": [c.open_time for c in candles],
            "open": [float(c.open) for c in candles],
            "high": [float(c.high) for c in candles],
            "low": [float(c.low) for c in candles],
            "close": [float(c.close) for c in candles],
            "volume": [float(c.volume) for c in candles],
            "turnover": [float(c.turnover) for c in candles],
        }
    )
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    return frame.sort_values("open_time").reset_index(drop=True)


def empty_frame() -> pd.DataFrame:
    """Leerer DataFrame mit korrektem Schema.

    Wichtig, damit nachgelagerter Code nicht zwischen 'leer' und 'vorhanden'
    unterscheiden muss - ein leerer Frame mit falschen Spaltentypen fuehrt sonst
    zu schwer auffindbaren Fehlern beim Zusammenfuehren.
    """
    frame = pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in SCHEMA.items()})
    return frame


def frame_to_candles(frame: pd.DataFrame) -> list[Candle]:
    """Zurueck zu Domaenenobjekten. Nur fuer kleine Mengen gedacht -
    der Backtest arbeitet direkt auf dem DataFrame."""
    from decimal import Decimal

    return [
        Candle(
            open_time=row.open_time.to_pydatetime(),
            open=Decimal(str(row.open)),
            high=Decimal(str(row.high)),
            low=Decimal(str(row.low)),
            close=Decimal(str(row.close)),
            volume=Decimal(str(row.volume)),
            turnover=Decimal(str(row.turnover)),
        )
        for row in frame.itertuples(index=False)
    ]


class CandleStore:
    """Parquet-basierter Kerzenspeicher, partitioniert nach Monat.

    Die Monatspartitionierung hat einen praktischen Grund: Ein Backfill ueber
    sechs Jahre laeuft Stunden. Wird er unterbrochen, sind die bereits
    geschriebenen Monate vollstaendig und der naechste Lauf setzt genau dort an.
    """

    def __init__(self, root: Path | str = "data_store") -> None:
        self.root = Path(root)
        self.candles_dir = self.root / "candles"

    # -- Pfade ---------------------------------------------------------------
    def _series_dir(self, symbol: str, interval: Interval) -> Path:
        return self.candles_dir / symbol / interval.value

    def _partition_path(self, symbol: str, interval: Interval, moment: datetime) -> Path:
        return self._series_dir(symbol, interval) / f"{moment:%Y-%m}.parquet"

    def partitions(self, symbol: str, interval: Interval) -> list[Path]:
        directory = self._series_dir(symbol, interval)
        if not directory.exists():
            return []
        return sorted(directory.glob("*.parquet"))

    # -- Schreiben -----------------------------------------------------------
    def write(self, symbol: str, interval: Interval, candles: list[Candle]) -> int:
        """Kerzen speichern. Bestehende Zeitstempel werden ueberschrieben.

        Gibt die Anzahl **neu hinzugekommener** Zeilen zurueck (nicht die Anzahl
        geschriebener) - so sieht ein Backfill sofort, ob er noch Fortschritt macht
        oder im Kreis laeuft.
        """
        if not candles:
            return 0
        return self.write_frame(symbol, interval, candles_to_frame(candles))

    def write_frame(self, symbol: str, interval: Interval, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0

        frame = frame.sort_values("open_time").reset_index(drop=True)
        added = 0

        # Nach Monat gruppieren und je Partition zusammenfuehren.
        for (year, month), chunk in frame.groupby(
            [frame["open_time"].dt.year, frame["open_time"].dt.month], sort=True
        ):
            moment = datetime(int(year), int(month), 1, tzinfo=UTC)
            path = self._partition_path(symbol, interval, moment)
            path.parent.mkdir(parents=True, exist_ok=True)

            if path.exists():
                existing = pd.read_parquet(path)
                before = len(existing)
                merged = pd.concat([existing, chunk], ignore_index=True)
            else:
                before = 0
                merged = chunk

            # Neuere Daten gewinnen: bei doppelten Zeitstempeln bleibt der
            # zuletzt geschriebene Eintrag stehen. Relevant, wenn eine noch
            # nicht abgeschlossene Kerze spaeter korrigiert nachgeliefert wird.
            merged = (
                merged.drop_duplicates(subset="open_time", keep="last")
                .sort_values("open_time")
                .reset_index(drop=True)
            )
            merged.to_parquet(path, index=False, compression="zstd")
            added += len(merged) - before

        return added

    # -- Lesen ---------------------------------------------------------------
    def read(
        self,
        symbol: str,
        interval: Interval,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Zeitreihe lesen, aufsteigend sortiert.

        ``start`` ist inklusiv, ``end`` exklusiv - die uebliche Halboffenheit,
        damit sich aufeinanderfolgende Fenster nahtlos aneinanderfuegen ohne
        die Randkerze doppelt zu zaehlen.
        """
        paths = self._relevant_partitions(symbol, interval, start, end)
        if not paths:
            return empty_frame()

        frames = [pd.read_parquet(p) for p in paths]
        combined = pd.concat(frames, ignore_index=True)
        combined = (
            combined.drop_duplicates(subset="open_time", keep="last")
            .sort_values("open_time")
            .reset_index(drop=True)
        )

        if start is not None:
            combined = combined[combined["open_time"] >= pd.Timestamp(start)]
        if end is not None:
            combined = combined[combined["open_time"] < pd.Timestamp(end)]

        return combined.reset_index(drop=True)

    def _relevant_partitions(
        self, symbol: str, interval: Interval, start: datetime | None, end: datetime | None
    ) -> list[Path]:
        """Nur die Monatsdateien oeffnen, die den Zeitraum beruehren.

        Bei sechs Jahren 1-Minuten-Daten macht das den Unterschied zwischen
        'Sekundenbruchteil' und 'mehrere Sekunden' pro Backtest-Fenster.
        """
        all_paths = self.partitions(symbol, interval)
        if start is None and end is None:
            return all_paths

        selected: list[Path] = []
        for path in all_paths:
            try:
                month = datetime.strptime(path.stem, "%Y-%m").replace(tzinfo=UTC)
            except ValueError:
                log.warning("store.unerwartete_datei", path=str(path))
                continue
            month_end = (month + timedelta(days=32)).replace(day=1)
            if start is not None and month_end <= start:
                continue
            if end is not None and month >= end:
                continue
            selected.append(path)
        return selected

    # -- Metadaten -----------------------------------------------------------
    def coverage(self, symbol: str, interval: Interval) -> Coverage:
        """Welcher Zeitraum liegt vor? Liest nur die Randpartitionen."""
        paths = self.partitions(symbol, interval)
        if not paths:
            return Coverage(None, None, 0)

        rows = 0
        for path in paths:
            rows += pd.read_parquet(path, columns=["open_time"]).shape[0]

        first = pd.read_parquet(paths[0], columns=["open_time"])["open_time"].min()
        last = pd.read_parquet(paths[-1], columns=["open_time"])["open_time"].max()
        return Coverage(first.to_pydatetime(), last.to_pydatetime(), rows)

    def last_candle_time(self, symbol: str, interval: Interval) -> datetime | None:
        paths = self.partitions(symbol, interval)
        if not paths:
            return None
        last = pd.read_parquet(paths[-1], columns=["open_time"])["open_time"].max()
        return last.to_pydatetime()

    def size_on_disk(self) -> int:
        if not self.candles_dir.exists():
            return 0
        return sum(p.stat().st_size for p in self.candles_dir.rglob("*.parquet"))

    def series(self) -> list[tuple[str, Interval]]:
        """Alle gespeicherten Zeitreihen auflisten."""
        if not self.candles_dir.exists():
            return []
        found: list[tuple[str, Interval]] = []
        for symbol_dir in sorted(self.candles_dir.iterdir()):
            if not symbol_dir.is_dir():
                continue
            for interval_dir in sorted(symbol_dir.iterdir()):
                if not interval_dir.is_dir():
                    continue
                try:
                    interval = Interval(interval_dir.name)
                except ValueError:
                    continue
                found.append((symbol_dir.name, interval))
        return found
