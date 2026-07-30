"""Bauer fuer Testdaten.

Bewusst getrennt von ``conftest.py``: Fixtures gehoeren dorthin, aber
Konstruktoren, die Tests mit eigenen Parametern aufrufen, sind normale
Funktionen und werden normal importiert.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from core.models import Candle, Instrument, Interval, Side, Signal, TakeProfitLeg


def make_instrument(
    *,
    symbol: str = "BTCUSDT",
    tick_size: str = "0.1",
    qty_step: str = "0.001",
    min_order_qty: str = "0.001",
    max_order_qty: str = "100",
    maintenance_margin_rate: str = "0.005",
) -> Instrument:
    """BTCUSDT-Perpetual mit den echten Bybit-Spezifikationen."""
    return Instrument(
        symbol=symbol,
        category="linear",
        base_coin="BTC",
        quote_coin="USDT",
        tick_size=Decimal(tick_size),
        qty_step=Decimal(qty_step),
        min_order_qty=Decimal(min_order_qty),
        max_order_qty=Decimal(max_order_qty),
        min_notional=Decimal("5"),
        max_leverage=Decimal("100"),
        maintenance_margin_rate=Decimal(maintenance_margin_rate),
        launch_time=datetime(2020, 3, 30, tzinfo=UTC),
    )


def make_signal(
    *,
    side: Side = Side.BUY,
    entry: str = "100000",
    stop_pct: str = "0.6",
    tp_portions: tuple[str, ...] = ("0.5", "0.3", "0.2"),
    rr_steps: tuple[str, ...] = ("1.5", "2.5", "4.0"),
    timestamp: datetime | None = None,
    strategy_id: str = "test",
) -> Signal:
    """Baut ein geometrisch stimmiges Signal.

    ``stop_pct`` ist die Stop-Distanz in Prozent des Einstiegs, ``rr_steps`` sind
    die Ziele als Vielfache dieser Distanz (also das Chance-Risiko-Verhaeltnis).
    Long und Short werden ueber das Vorzeichen gespiegelt, damit beide Seiten
    exakt symmetrisch getestet werden.
    """
    entry_price = Decimal(entry)
    distance = entry_price * Decimal(stop_pct) / Decimal(100)
    direction = Decimal(1) if side is Side.BUY else Decimal(-1)

    stop = entry_price - direction * distance
    legs = [
        TakeProfitLeg(price=entry_price + direction * distance * Decimal(rr), portion=Decimal(p))
        for rr, p in zip(rr_steps, tp_portions, strict=True)
    ]
    return Signal(
        timestamp=timestamp or datetime(2026, 1, 1, tzinfo=UTC),
        symbol="BTCUSDT",
        side=side,
        entry_price=entry_price,
        stop_loss=stop,
        take_profits=legs,
        strategy_id=strategy_id,
        reason="fixture",
    )


def make_candles(
    *,
    count: int,
    start: datetime | None = None,
    interval: Interval = Interval.M15,
    start_price: Decimal = Decimal("100000"),
    step: Decimal = Decimal("10"),
    wick: Decimal = Decimal("5"),
) -> list[Candle]:
    """Erzeugt eine saubere, aufsteigend sortierte Kerzenreihe.

    ``step`` ist die Preisaenderung je Kerze - positiv fuer Aufwaerts-, negativ
    fuer Abwaertstrend, null fuer Seitwaerts.
    """
    t0 = start or datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    price = start_price
    for i in range(count):
        close = price + step
        candles.append(
            Candle(
                open_time=t0 + interval.duration * i,
                open=price,
                high=max(price, close) + wick,
                low=min(price, close) - wick,
                close=close,
                volume=Decimal("10"),
                turnover=Decimal("1000000"),
            )
        )
        price = close
    return candles


def make_kline_response(candles: list[Candle], *, symbol: str = "BTCUSDT") -> dict:
    """Baut eine Bybit-Kline-Antwort nach.

    Zwei Eigenheiten der echten API werden dabei bewusst nachgebildet, weil
    genau sie Fehler verursachen:

    * Alle Zahlen sind **Strings**.
    * Die Liste ist **absteigend** sortiert (neueste Kerze zuerst).
    """
    rows = [
        [
            str(int(c.open_time.timestamp() * 1000)),
            str(c.open),
            str(c.high),
            str(c.low),
            str(c.close),
            str(c.volume),
            str(c.turnover),
        ]
        for c in reversed(candles)
    ]
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {"category": "linear", "symbol": symbol, "list": rows},
        "retExtInfo": {},
        "time": 1767225600000,
    }
