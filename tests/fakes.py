"""Test-Doubles fuer die Boersenanbindung.

Diese erfuellen dieselben Protokolle wie die echten Adapter. Genau dafuer wurde
die Adapterschicht eingezogen: Die komplette Pipeline - Backfill, Qualitaets-
pruefung, spaeter Backtest und Execution - laesst sich damit ohne Netzwerk
testen. Im geoblockten Entwicklungscontainer ist das nicht Komfort, sondern
Voraussetzung.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from core.models import Candle, FundingRate, Instrument, Interval, Ticker

from .factories import make_candles, make_instrument


class FakeMarketData:
    """Marktdatenquelle, die aus einer vorgegebenen Kerzenreihe bedient.

    Bildet die Eigenheiten der echten API nach, die in der Praxis Fehler
    verursachen:

    * ``limit`` begrenzt die Rueckgabe (Standard 1000 bei Bybit).
    * Ist eine Kerze nicht vorhanden (Luecke), wird sie stillschweigend
      uebersprungen - die naechste vorhandene kommt zurueck.
    * Kerzen kommen aufsteigend zurueck, wie vom Adapter garantiert.
    """

    def __init__(
        self,
        candles: list[Candle] | None = None,
        *,
        interval: Interval = Interval.M15,
        instrument: Instrument | None = None,
        now: datetime | None = None,
    ) -> None:
        self.candles = sorted(candles or [], key=lambda c: c.open_time)
        self.interval = interval
        self.instrument = instrument or make_instrument()
        self.now = now or datetime.now(UTC)
        #: Aufgezeichnete Aufrufe - fuer Tests, die das Paging pruefen.
        self.calls: list[dict] = []

    # -- MarketDataSource ----------------------------------------------------
    def get_server_time(self) -> datetime:
        return self.now

    def get_instrument(self, symbol: str) -> Instrument:
        return self.instrument

    def get_klines(
        self,
        symbol: str,
        interval: Interval,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 200,
    ) -> list[Candle]:
        self.calls.append(
            {"symbol": symbol, "interval": interval, "start": start, "end": end, "limit": limit}
        )
        selected = self.candles
        if start is not None:
            selected = [c for c in selected if c.open_time >= start]
        if end is not None:
            selected = [c for c in selected if c.open_time < end]

        # **Die neuesten, nicht die aeltesten.** Genau so verhaelt sich Bybit:
        # Passt man ein weites Zeitfenster, kommen die juengsten ``limit``
        # Kerzen daraus zurueck - nicht die ersten.
        #
        # Diese Zeile stand frueher als ``selected[:limit]`` hier, und weil das
        # Double damit freundlicher war als die Wirklichkeit, bestaetigten die
        # Tests einen Backfill, der live nach einer Seite aufhoerte. Ein
        # Test-Double, das sich gutmuetiger verhaelt als das Original, prueft
        # nichts - es beruhigt nur.
        return selected[-limit:] if limit else selected

    def get_ticker(self, symbol: str) -> Ticker:
        last = self.candles[-1].close if self.candles else Decimal("100000")
        return Ticker(
            symbol=symbol,
            last_price=last,
            mark_price=last,
            index_price=last,
            bid1_price=last - Decimal("5"),
            ask1_price=last + Decimal("5"),
            funding_rate=Decimal("0.0001"),
        )

    def get_funding_history(
        self, symbol: str, *, start: datetime | None = None, limit: int = 200
    ) -> list[FundingRate]:
        return []


def make_series_with_gap(
    *,
    before: int = 100,
    gap_candles: int = 20,
    after: int = 100,
    interval: Interval = Interval.M15,
    start: datetime | None = None,
) -> list[Candle]:
    """Erzeugt eine Reihe mit einer echten Luecke in der Mitte.

    Bildet den realistischen Fall nach: Boersenwartung oder eine Phase ohne
    Handel. Der Backfill muss darueber hinweggehen, die Qualitaetspruefung muss
    sie melden.
    """
    t0 = start or datetime(2026, 1, 1, tzinfo=UTC)
    first_block = make_candles(count=before, start=t0, interval=interval)

    resume_at = t0 + interval.duration * (before + gap_candles)
    last_price = first_block[-1].close if first_block else Decimal("100000")
    second_block = make_candles(
        count=after, start=resume_at, interval=interval, start_price=last_price
    )
    return first_block + second_block
