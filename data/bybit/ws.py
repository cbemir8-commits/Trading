"""Live-Kerzen ueber den Bybit-Websocket.

Drei Dinge entscheiden hier ueber Korrektheit:

1. **Nur bestaetigte Kerzen zaehlen.** Bybit sendet waehrend einer laufenden
   Periode mehrfach Aktualisierungen mit ``confirm: false``. Erst die Nachricht
   mit ``confirm: true`` beschreibt die abgeschlossene Kerze. Wer auf
   unbestaetigte Updates handelt, reagiert auf ein Hoch, das gleich wieder
   verschwindet - dieselbe Klasse Fehler wie eine unfertige Kerze im Backfill.

2. **Ping alle 20 Sekunden.** Bybit trennt Verbindungen ohne Ping. Das ist der
   haeufigste Grund fuer einen Stream, der nachts unbemerkt stirbt.

3. **Luecken nach dem Reconnect schliessen.** Ein Websocket, der drei Minuten
   weg war, hat drei Minuten Kerzen verpasst. Diese Luecke muss ueber REST
   nachgeladen werden, sonst rechnet der Indikator auf einer loechrigen Reihe.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog
import websockets

from core.config import BybitSettings
from core.models import Candle, Interval

log = structlog.get_logger(__name__)

#: Bybit trennt die Verbindung ohne Ping. 20 s ist die dokumentierte Vorgabe.
PING_INTERVAL_S = 20.0

#: Kommt so lange keine Nachricht, gilt die Verbindung als tot. Grosszuegig
#: bemessen: in ruhigen Phasen kommen nur die eigenen Pong-Antworten.
STALE_TIMEOUT_S = 60.0

CandleHandler = Callable[[Candle, Interval], Awaitable[None]]


@dataclass(slots=True)
class StreamStats:
    """Betriebszahlen des Streams - landen spaeter im Dashboard."""

    messages: int = 0
    confirmed_candles: int = 0
    unconfirmed_updates: int = 0
    reconnects: int = 0
    last_message_at: datetime | None = None
    connected_since: datetime | None = None
    gaps_filled: int = 0

    @property
    def is_healthy(self) -> bool:
        if self.last_message_at is None:
            return False
        age = (datetime.now(UTC) - self.last_message_at).total_seconds()
        return age < STALE_TIMEOUT_S


def parse_kline_message(payload: dict) -> list[tuple[Candle, Interval, bool]]:
    """Wandelt eine Kline-Nachricht in Kerzen um.

    Gibt Tupel ``(Kerze, Intervall, bestaetigt)`` zurueck. Die Filterung nach
    ``bestaetigt`` passiert bewusst erst beim Aufrufer - so kann das Dashboard
    die laufende Kerze anzeigen, waehrend nur bestaetigte gespeichert werden.
    """
    topic: str = payload.get("topic", "")
    if not topic.startswith("kline."):
        return []

    results: list[tuple[Candle, Interval, bool]] = []
    for entry in payload.get("data", []):
        try:
            interval = Interval(str(entry["interval"]))
            candle = Candle(
                open_time=datetime.fromtimestamp(int(entry["start"]) / 1000, tz=UTC),
                open=Decimal(str(entry["open"])),
                high=Decimal(str(entry["high"])),
                low=Decimal(str(entry["low"])),
                close=Decimal(str(entry["close"])),
                volume=Decimal(str(entry["volume"])),
                turnover=Decimal(str(entry["turnover"])),
            )
        except (KeyError, ValueError, ArithmeticError) as exc:
            log.warning("ws.kerze_unlesbar", fehler=str(exc), rohdaten=entry)
            continue
        results.append((candle, interval, bool(entry.get("confirm", False))))
    return results


class KlineStream:
    """Haelt eine Websocket-Verbindung zu den oeffentlichen Kline-Kanaelen.

    Beachte: Fuer Demo-Trading gibt es keinen eigenen oeffentlichen Stream -
    dort werden die echten Mainnet-Marktdaten verwendet (siehe
    ``BybitEnvironment.public_ws_url``). Genau so soll es sein: echte Preise
    bei Spielgeld.
    """

    def __init__(
        self,
        settings: BybitSettings,
        intervals: list[Interval],
        *,
        on_candle: CandleHandler,
        on_unconfirmed: CandleHandler | None = None,
        max_backoff_s: float = 60.0,
    ) -> None:
        self.settings = settings
        self.intervals = intervals
        self.on_candle = on_candle
        self.on_unconfirmed = on_unconfirmed
        self.max_backoff_s = max_backoff_s
        self.stats = StreamStats()
        self._stop = asyncio.Event()
        self._seen: dict[Interval, datetime] = {}

    @property
    def url(self) -> str:
        return self.settings.environment.public_ws_url(self.settings.category)

    @property
    def topics(self) -> list[str]:
        return [f"kline.{i.value}.{self.settings.symbol}" for i in self.intervals]

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        """Verbindet und liest bis zum Stopp. Reconnect mit Backoff."""
        backoff = 1.0
        while not self._stop.is_set():
            try:
                await self._session()
                backoff = 1.0  # saubere Verbindung -> Backoff zuruecksetzen
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - der Stream muss alles ueberleben
                self.stats.reconnects += 1
                log.warning(
                    "ws.verbindung_verloren",
                    fehler=str(exc),
                    naechster_versuch_in_s=round(backoff, 1),
                    reconnects=self.stats.reconnects,
                )
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                backoff = min(backoff * 2, self.max_backoff_s)

    async def _session(self) -> None:
        async with websockets.connect(self.url, ping_interval=None) as socket:
            self.stats.connected_since = datetime.now(UTC)
            await socket.send(json.dumps({"op": "subscribe", "args": self.topics}))
            log.info("ws.verbunden", url=self.url, topics=self.topics)

            pinger = asyncio.create_task(self._ping_loop(socket))
            try:
                await self._read_loop(socket)
            finally:
                pinger.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pinger

    async def _ping_loop(self, socket: websockets.ClientConnection) -> None:
        """Bybit trennt Verbindungen ohne regelmaessigen Ping."""
        while not self._stop.is_set():
            await asyncio.sleep(PING_INTERVAL_S)
            with contextlib.suppress(Exception):
                await socket.send(json.dumps({"op": "ping"}))

    async def _read_loop(self, socket: websockets.ClientConnection) -> None:
        while not self._stop.is_set():
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=STALE_TIMEOUT_S)
            except TimeoutError as exc:
                raise ConnectionError(
                    f"Keine Nachricht seit {STALE_TIMEOUT_S:.0f}s - Verbindung gilt als tot"
                ) from exc

            self.stats.messages += 1
            self.stats.last_message_at = datetime.now(UTC)

            payload = json.loads(raw)
            if payload.get("op") in {"pong", "subscribe"}:
                continue

            for candle, interval, confirmed in parse_kline_message(payload):
                if confirmed:
                    self.stats.confirmed_candles += 1
                    self._seen[interval] = candle.open_time
                    await self.on_candle(candle, interval)
                else:
                    self.stats.unconfirmed_updates += 1
                    if self.on_unconfirmed is not None:
                        await self.on_unconfirmed(candle, interval)

    def missing_since(self, interval: Interval) -> datetime | None:
        """Ab wann muessen nach einem Reconnect Kerzen nachgeladen werden?

        Gibt den Zeitpunkt der letzten gesehenen Kerze plus ein Intervall
        zurueck - genau dort setzt der REST-Nachlader an.
        """
        last = self._seen.get(interval)
        if last is None:
            return None
        return last + interval.duration


@dataclass(frozen=True, slots=True)
class GapFillResult:
    """Ergebnis eines Lueckenschlusses."""

    written: int
    requested_from: datetime
    actual_from: datetime
    truncated: bool
    """True, wenn die Luecke aelter war als ``max_lookback`` und daher **nicht
    vollstaendig** geschlossen wurde.

    Das ist der gefaehrliche Fall: Es bleibt ein Loch in der Zeitreihe, ueber
    das Indikatoren hinwegrechnen wuerden, ohne es zu merken. Der Aufrufer muss
    dann einen richtigen Backfill anstossen.
    """

    def __bool__(self) -> bool:
        return self.written > 0


@dataclass(slots=True)
class GapFiller:
    """Schliesst Luecken nach einer Websocket-Unterbrechung ueber REST.

    Ohne diesen Schritt hat die Zeitreihe genau dort Loecher, wo die Verbindung
    weg war - und Indikatoren rechnen ueber eine Luecke hinweg, ohne es zu merken.

    ``max_lookback`` begrenzt den Aufwand: Nach einem tagelangen Ausfall soll
    nicht der Live-Prozess die halbe Historie nachladen, dafuer ist der Backfill
    da. Wird die Grenze erreicht, meldet das Ergebnis ``truncated=True`` - dieses
    Signal darf der Aufrufer nicht ignorieren.
    """

    market: object  # MarketDataSource
    store: object  # CandleStore
    symbol: str
    max_lookback: timedelta = field(default_factory=lambda: timedelta(hours=6))

    def fill(
        self, interval: Interval, *, since: datetime, now: datetime | None = None
    ) -> GapFillResult:
        reference = now or datetime.now(UTC)
        earliest = reference - self.max_lookback
        start = max(since, earliest)
        truncated = start > since

        if start >= reference:
            return GapFillResult(0, since, start, truncated)

        candles = self.market.get_klines(  # type: ignore[attr-defined]
            self.symbol, interval, start=start, end=reference, limit=1000
        )
        complete = [c for c in candles if c.open_time + interval.duration <= reference]
        written: int = (
            self.store.write(self.symbol, interval, complete)  # type: ignore[attr-defined]
            if complete
            else 0
        )

        if truncated:
            log.warning(
                "ws.luecke_zu_alt",
                symbol=self.symbol,
                interval=interval.label,
                kerzen=written,
                angefordert_ab=since.isoformat(),
                geladen_ab=start.isoformat(),
                hinweis="Luecke ist aelter als max_lookback und NICHT vollstaendig "
                "geschlossen. Backfill anstossen, bevor gehandelt wird.",
            )
        elif written:
            log.info(
                "ws.luecke_geschlossen",
                symbol=self.symbol,
                interval=interval.label,
                kerzen=written,
                ab=start.isoformat(),
            )

        return GapFillResult(written, since, start, truncated)
