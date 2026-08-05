"""Referenzkerzen von oeffentlichen Boersen - damit hier ueberhaupt geforscht
werden kann.

Das Problem
-----------
Bybit ist aus diesem Container gesperrt (HTTP 403, Regionssperre). Alle
Rauchtests liefen deshalb auf **erzeugten Zufallsdaten**, und die haben eine
Eigenschaft, die jedes Ergebnis wertlos macht: Sie enthalten keine Struktur.
Auf einer Irrfahrt verliert jede Strategie nach Gebuehren, unabhaengig davon
wie gut sie ist. Ein Wettbewerb darauf prueft die Verkabelung und sonst nichts.

Bitstamp, Kraken und Coinbase sind erreichbar. Damit laesst sich hier auf
echten Kursen forschen, statt auf jeden Lauf beim Nutzer zu warten.

Was diese Daten sind - und was nicht
------------------------------------
**Bitstamp BTC/USD ist nicht Bybit BTCUSDT-Perpetual.** Der Unterschied ist
klein, aber er ist da:

* Kassamarkt statt Perpetual - **keine Funding-Zahlungen**. Alle Strategien,
  die auf Funding beruhen, koennen hier nicht geprueft werden.
* Andere Boerse, andere Liquiditaet - Dochte und Spitzen weichen ab, besonders
  in schnellen Bewegungen.
* USD statt USDT.

Fuer die **Vorauswahl** ist das gut genug: Ein Trendfilter oder ein
Abfolge-Modell, das auf Bitstamp nichts traegt, wird es auf Bybit auch nicht
tun. Fuer die **Zulassung** nicht: Die endgueltige Pruefung gehoert auf die
Daten der Boerse, auf der gehandelt wird.

Deshalb landen diese Kerzen unter einem eigenen Symbol im Speicher. Wer sie
versehentlich handelt, muesste das Symbol von Hand umstellen - und wuerde es
dabei merken.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import structlog

from core.models import Candle, Interval

log = structlog.get_logger(__name__)

#: Symbolname im Speicher. Bewusst anders als ``BTCUSDT``: Diese Kerzen sind
#: Forschungsmaterial, keine Handelsgrundlage.
REFERENCE_SYMBOL = "BTCUSD_BITSTAMP"

#: Weitere Maerkte - **nur zur Gegenprobe**, nicht zum Handeln.
#:
#: Der Sinn: Eine Regel, die auf sechs Jahren BTC gut aussieht, kann an diese
#: sechs Jahre angepasst sein, ohne dass man es merkt. Dieselbe Regel
#: **ungeaendert** auf einem anderen Markt zu pruefen ist der schaerfste
#: verfuegbare Test - er benutzt Daten, die bei der Entwicklung keine Rolle
#: gespielt haben.
#:
#: Gehandelt wird weiterhin ausschliesslich BTC.
PAIRS: dict[str, str] = {
    "BTCUSD_BITSTAMP": "btcusd",
    "ETHUSD_BITSTAMP": "ethusd",
    "LTCUSD_BITSTAMP": "ltcusd",
    "XRPUSD_BITSTAMP": "xrpusd",
}

#: Bitstamp liefert hoechstens 1000 Kerzen je Anfrage.
PAGE_SIZE = 1000

BASE_URL = "https://www.bitstamp.net/api/v2/ohlc/{pair}/"

#: Bybit-Intervall -> Bitstamp-Schrittweite in Sekunden.
STEPS: dict[Interval, int] = {
    Interval.M1: 60,
    Interval.M3: 180,
    Interval.M5: 300,
    Interval.M15: 900,
    Interval.M30: 1800,
    Interval.H1: 3600,
    Interval.H2: 7200,
    Interval.H4: 14400,
    Interval.H6: 21600,
    Interval.H12: 43200,
    Interval.D1: 86400,
}


class BitstampReference:
    """Kerzen von Bitstamp, in unserem :class:`Candle`-Format.

    Absichtlich kein vollstaendiger ``MarketDataSource``: Hier gibt es keine
    Kontraktdaten, keinen Ticker und keine Funding-Historie. Wer das braucht,
    braucht die Boerse selbst - und soll das nicht versehentlich hier
    bekommen.
    """

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        pause: float = 0.35,
    ) -> None:
        self.client = client or httpx.Client(timeout=30.0)
        #: Bitstamp nennt kein hartes Limit. Ein Drittel einer Sekunde je
        #: Anfrage ist zurueckhaltend genug, dass es keins geben muss.
        self.pause = pause

    def get_klines(
        self,
        interval: Interval,
        *,
        start: datetime,
        limit: int = PAGE_SIZE,
        symbol: str = REFERENCE_SYMBOL,
    ) -> list[Candle]:
        """Kerzen ab ``start``, aufsteigend.

        Anders als Bybit liefert Bitstamp von ``start`` an **vorwaerts**. Die
        Seitenfalle, die uns bei Bybit aus sechs Jahren zehn Tage gemacht hat,
        gibt es hier nicht - der Cursor wird trotzdem geprueft.
        """
        step = STEPS.get(interval)
        if step is None:
            raise ValueError(f"Bitstamp kennt kein Intervall {interval.label}")

        params: dict[str, Any] = {
            "step": step,
            "limit": min(limit, PAGE_SIZE),
            "start": int(start.timestamp()),
        }
        paar = PAIRS.get(symbol)
        if paar is None:
            raise ValueError(f"Kein Bitstamp-Paar fuer {symbol} hinterlegt")

        antwort = self.client.get(BASE_URL.format(pair=paar), params=params)
        antwort.raise_for_status()
        roh = antwort.json()["data"]["ohlc"]

        # ``Candle`` traegt weder Symbol noch Intervall - beides gehoert zum
        # Speicherort, nicht zur Kerze. Sie hier mitzugeben sieht ordentlich
        # aus und wird von Pydantic stillschweigend verworfen; die Trennung
        # der Referenzdaten passiert allein ueber ``store.write``.
        return [
            Candle(
                open_time=datetime.fromtimestamp(int(zeile["timestamp"]), tz=UTC),
                open=Decimal(zeile["open"]),
                high=Decimal(zeile["high"]),
                low=Decimal(zeile["low"]),
                close=Decimal(zeile["close"]),
                volume=Decimal(zeile["volume"]),
                turnover=Decimal(zeile["volume"]) * Decimal(zeile["close"]),
            )
            for zeile in roh
        ]


def backfill_reference(
    source: BitstampReference,
    store,
    interval: Interval,
    *,
    start: datetime,
    end: datetime | None = None,
    max_pages: int = 400,
    on_progress: Callable[[int, datetime], None] | None = None,
    symbol: str = REFERENCE_SYMBOL,
) -> int:
    """Referenzkerzen laden und in den Speicher schreiben.

    Setzt fort, wo der Speicher aufhoert - ein Abbruch kostet hoechstens eine
    Seite.
    """
    end = end or datetime.now(UTC)

    geschrieben = 0
    for luecke_von, luecke_bis in _fehlende_bereiche(
        store, symbol, interval, start=start, end=end
    ):
        geschrieben += _lade_bereich(
            source, store, interval,
            start=luecke_von, end=luecke_bis, symbol=symbol,
            max_pages=max_pages, geschrieben_bisher=geschrieben,
            on_progress=on_progress,
        )
    cursor = end

    log.info(
        "referenz.geladen",
        symbol=symbol,
        intervall=interval.label,
        neu=geschrieben,
        bis=cursor.isoformat(),
    )
    return geschrieben


def _fehlende_bereiche(
    store, symbol: str, interval: Interval, *, start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    """Welche Zeitraeume fehlen im Speicher - **vorne wie hinten**.

    Frueher setzte der Backfill nur vorwaerts fort: Lag im Speicher schon
    etwas, begann er hinter dessen Ende. Wer aeltere Kerzen anforderte, bekam
    stillschweigend nichts - der Lauf meldete "1 neue Kerze" und war fertig.
    Genau das ist passiert, als die Historie von sechs auf vierzehn Jahre
    verlaengert werden sollte.

    Beide Richtungen zu pruefen kostet ein paar Zeilen und macht den Befehl
    zu dem, was sein Name verspricht.
    """
    coverage = store.coverage(symbol, interval)
    if coverage.is_empty or coverage.start is None or coverage.end is None:
        return [(start, end)]

    bereiche: list[tuple[datetime, datetime]] = []
    if start < coverage.start:
        bereiche.append((start, coverage.start))
    naechster = coverage.end + interval.duration
    if naechster < end:
        bereiche.append((naechster, end))
    return bereiche


def _lade_bereich(
    source: BitstampReference,
    store,
    interval: Interval,
    *,
    start: datetime,
    end: datetime,
    symbol: str,
    max_pages: int,
    geschrieben_bisher: int,
    on_progress: Callable[[int, datetime], None] | None,
) -> int:
    """Einen zusammenhaengenden Zeitraum seitenweise laden."""
    cursor = start
    geschrieben = 0

    for _ in range(max_pages):
        if cursor >= end:
            break

        kerzen = source.get_klines(
            interval, start=cursor, limit=PAGE_SIZE, symbol=symbol
        )
        kerzen = [k for k in kerzen if k.open_time < end]
        if not kerzen:
            break

        geschrieben += store.write(symbol, interval, kerzen)
        naechster = kerzen[-1].open_time + interval.duration

        if naechster <= cursor:
            log.warning("referenz.cursor_steht", stand=cursor.isoformat())
            break
        cursor = naechster

        if on_progress is not None:
            on_progress(geschrieben_bisher + geschrieben, cursor)
        time.sleep(source.pause)

    return geschrieben


def estimate_pages(interval: Interval, start: datetime, end: datetime) -> int:
    spanne: timedelta = end - start
    je_seite = interval.duration * PAGE_SIZE
    return max(1, int(spanne / je_seite) + 1)
