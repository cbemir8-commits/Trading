"""Historische Kerzen von Bybit nachladen.

Der Backfill ueber sechs Jahre 1-Minuten-Daten laeuft Stunden und rund 3300
Anfragen. Entsprechend muss er drei Dinge koennen:

* **Resumierbar sein.** Der Fortschritt wird nach jeder Seite in Parquet
  geschrieben. Ein Abbruch kostet hoechstens eine Seite.
* **Luecken ueberspringen.** Gibt es in einer Minute keinen einzigen Handel,
  liefert Bybit fuer diese Minute keine Kerze. Das ist keine Stoerung, sondern
  normal - der Cursor muss darueber hinweggehen, statt haengenzubleiben.
* **Unfertige Kerzen weglassen.** Die zuletzt gelieferte Kerze ist meist noch
  in Bildung. Landet sie im Speicher, enthaelt der Backtest eine Kerze, deren
  Hoch/Tief/Schluss zum Signalzeitpunkt noch gar nicht feststanden - ein
  Lookahead-Fehler, der die Ergebnisse still schoenrechnet.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import structlog

from core.models import Candle, Interval
from data.bybit.adapter import MarketDataSource
from data.store import CandleStore

log = structlog.get_logger(__name__)

#: Bybit erlaubt 1000 Kerzen je Anfrage.
PAGE_SIZE = 1000

#: Bybits IP-Limit liegt bei 600 Anfragen / 5 s. Wir bleiben deutlich darunter -
#: ein Backfill ist nicht eilig, und ein 403 mit 10 Minuten Sperre waere teuer.
DEFAULT_REQUESTS_PER_SECOND = 8.0


@dataclass(slots=True)
class BackfillProgress:
    symbol: str
    interval: Interval
    requests: int = 0
    candles_written: int = 0
    pages_empty: int = 0
    cursor: datetime | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def elapsed(self) -> timedelta:
        return datetime.now(UTC) - self.started_at

    def describe(self) -> str:
        return (
            f"{self.symbol} {self.interval.label}: {self.candles_written} Kerzen, "
            f"{self.requests} Anfragen, Stand {self.cursor:%Y-%m-%d %H:%M} "
            f"({self.elapsed.total_seconds():.0f}s)"
            if self.cursor
            else f"{self.symbol} {self.interval.label}: nichts geladen"
        )


class RateLimiter:
    """Einfacher Durchsatzbegrenzer.

    Bewusst simpel gehalten: ein Mindestabstand zwischen Anfragen. Ein
    Token-Bucket waere kaum genauer, denn der Backfill ist ohnehin ein
    gleichmaessiger, serieller Strom.
    """

    def __init__(self, requests_per_second: float = DEFAULT_REQUESTS_PER_SECOND) -> None:
        self.min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._last_call = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


def drop_unfinished(
    candles: list[Candle], interval: Interval, *, now: datetime | None = None
) -> list[Candle]:
    """Entfernt Kerzen, deren Periode noch nicht abgelaufen ist.

    Das ist die wichtigste Zeile Vorsichtsmassnahme im ganzen Modul. Eine noch
    laufende Kerze hat ein Hoch, Tief und einen Schlusskurs, die sich noch
    aendern werden. Im Backtest sieht eine Strategie dadurch Informationen aus
    der Zukunft - und liefert Ergebnisse, die live nicht reproduzierbar sind.
    """
    reference = now or datetime.now(UTC)
    return [c for c in candles if c.open_time + interval.duration <= reference]


class Backfiller:
    """Laedt Kerzen seitenweise und schreibt sie in den Speicher."""

    def __init__(
        self,
        market: MarketDataSource,
        store: CandleStore,
        *,
        rate_limiter: RateLimiter | None = None,
        page_size: int = PAGE_SIZE,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.market = market
        self.store = store
        self.rate_limiter = rate_limiter or RateLimiter()
        self.page_size = page_size
        #: Injizierbare Zeitquelle. Nur damit laesst sich "die letzte Kerze
        #: bildet sich gerade noch" ueberhaupt testen, ohne echte Zeit abzuwarten.
        self.clock = clock or (lambda: datetime.now(UTC))

    def run(
        self,
        symbol: str,
        interval: Interval,
        *,
        start: datetime,
        end: datetime | None = None,
        resume: bool = True,
        on_progress: Callable[[BackfillProgress], None] | None = None,
        max_pages: int | None = None,
    ) -> BackfillProgress:
        """Zeitraum nachladen.

        ``resume=True`` setzt hinter der letzten bereits gespeicherten Kerze an.
        ``max_pages`` begrenzt den Lauf - nuetzlich fuer Tests und erste Stichproben.
        """
        end = end or self.clock()
        progress = BackfillProgress(symbol=symbol, interval=interval)

        cursor = start
        if resume:
            last = self.store.last_candle_time(symbol, interval)
            if last is not None and last >= start:
                # Hinter der letzten vollstaendigen Kerze weitermachen.
                cursor = last + interval.duration
                log.info(
                    "backfill.fortsetzen",
                    symbol=symbol,
                    interval=interval.label,
                    ab=cursor.isoformat(),
                )

        if cursor >= end:
            log.info("backfill.aktuell", symbol=symbol, interval=interval.label)
            progress.cursor = cursor
            return progress

        pages = 0
        while cursor < end:
            if max_pages is not None and pages >= max_pages:
                log.info("backfill.seitenlimit", symbol=symbol, seiten=pages)
                break

            self.rate_limiter.wait()
            candles = self.market.get_klines(
                symbol, interval, start=cursor, end=end, limit=self.page_size
            )
            progress.requests += 1
            pages += 1

            if not candles:
                progress.pages_empty += 1
                log.info(
                    "backfill.leere_seite",
                    symbol=symbol,
                    interval=interval.label,
                    cursor=cursor.isoformat(),
                )
                break

            complete = drop_unfinished(candles, interval, now=self.clock())
            if complete:
                written = self.store.write(symbol, interval, complete)
                progress.candles_written += written

            newest = candles[-1].open_time
            next_cursor = newest + interval.duration

            # Sicherung gegen Endlosschleifen: Wenn der Cursor nicht vorankommt,
            # liefert die API dieselbe Seite erneut. Ohne diese Pruefung liefe
            # der Backfill unbemerkt bis zum Rate-Limit.
            if next_cursor <= cursor:
                log.warning(
                    "backfill.cursor_steht",
                    symbol=symbol,
                    interval=interval.label,
                    cursor=cursor.isoformat(),
                    neueste=newest.isoformat(),
                )
                break

            cursor = next_cursor
            progress.cursor = cursor

            if on_progress is not None:
                on_progress(progress)

            # Weniger als eine volle Seite und keine unfertigen Kerzen entfernt:
            # wir sind am aktuellen Rand angekommen.
            if len(candles) < self.page_size and len(complete) == len(candles):
                break

        log.info(
            "backfill.fertig",
            symbol=symbol,
            interval=interval.label,
            kerzen=progress.candles_written,
            anfragen=progress.requests,
            sekunden=round(progress.elapsed.total_seconds(), 1),
        )
        return progress

    def run_many(
        self,
        symbol: str,
        intervals: list[Interval],
        *,
        start: datetime,
        end: datetime | None = None,
        resume: bool = True,
        on_progress: Callable[[BackfillProgress], None] | None = None,
    ) -> dict[Interval, BackfillProgress]:
        """Mehrere Zeitreihen nacheinander laden.

        Reihenfolge: grobe Intervalle zuerst. Die sind schnell fertig und geben
        sofort eine brauchbare Datenbasis, waehrend die 1-Minuten-Reihe noch laeuft.
        """
        ordered = sorted(intervals, key=lambda i: i.duration, reverse=True)
        results: dict[Interval, BackfillProgress] = {}
        for interval in ordered:
            results[interval] = self.run(
                symbol,
                interval,
                start=start,
                end=end,
                resume=resume,
                on_progress=on_progress,
            )
        return results


def estimate_requests(interval: Interval, start: datetime, end: datetime) -> int:
    """Wie viele Anfragen wird ein Backfill grob brauchen?

    Fuer die Planung: 1-Minuten-Daten ab 2020 sind rund 3300 Anfragen, bei
    8 Anfragen/s also etwa sieben Minuten. Die groberen Intervalle sind
    vernachlaessigbar.
    """
    if end <= start:
        return 0
    total_candles = (end - start) / interval.duration
    return max(1, int(total_candles / PAGE_SIZE) + 1)
