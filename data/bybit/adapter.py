"""Typisierte Bybit-Schnittstelle - die einzige Stelle im System mit Boersenkontakt.

Alles darueber (Backtest, Strategie, Execution) kennt nur die Protokolle aus
diesem Modul. Das hat drei Gruende:

1. **Testbarkeit.** Ein ``FakeMarketData`` erfuellt dasselbe Protokoll, also
   laeuft die komplette Testsuite ohne Netzwerk - noetig, weil dieser
   Entwicklungscontainer von Bybit geoblockt ist.
2. **Demo/Live-Umschaltung** ist eine Konfigurationsaenderung, keine Codeaenderung.
3. **Ein Ort fuer Rundung und Rohdaten-Parsing.** Bybit liefert alles als String
   und Klines in umgekehrter Zeitreihenfolge - beides wird genau hier geradegezogen.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

import structlog

from core.config import BybitSettings
from core.models import (
    Candle,
    FundingRate,
    Instrument,
    Interval,
    Position,
    Side,
    Ticker,
    WalletBalance,
)

from .client import BybitHTTPClient

log = structlog.get_logger(__name__)

#: Bybit erlaubt maximal 1000 Kerzen pro Kline-Anfrage.
MAX_KLINE_LIMIT = 1000


def _dec(value: Any, default: str = "0") -> Decimal:
    """Bybit liefert Zahlen als String - und leere Strings fuer 'nicht gesetzt'."""
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def _ts(value: Any) -> datetime | None:
    """Millisekunden-Zeitstempel -> timezone-bewusstes datetime (UTC).

    Naive datetimes sind in einem System, das ueber Zeitzonen und
    Sommerzeitwechsel hinweg handelt, eine Fehlerquelle - deshalb konsequent UTC.
    """
    if value is None or value == "" or value == "0":
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


@runtime_checkable
class MarketDataSource(Protocol):
    """Lesender Zugriff auf Marktdaten. Braucht keine Credentials."""

    def get_server_time(self) -> datetime: ...

    def get_instrument(self, symbol: str) -> Instrument: ...

    def get_klines(
        self,
        symbol: str,
        interval: Interval,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 200,
    ) -> list[Candle]: ...

    def get_ticker(self, symbol: str) -> Ticker: ...

    def get_funding_history(
        self, symbol: str, *, start: datetime | None = None, limit: int = 200
    ) -> list[FundingRate]: ...


@runtime_checkable
class AccountSource(Protocol):
    """Lesender Zugriff auf das Konto. Braucht Credentials mit Read-Recht."""

    def get_wallet_balance(self, coin: str = "USDT") -> WalletBalance: ...

    def get_positions(self, symbol: str | None = None) -> list[Position]: ...


class BybitMarketData:
    """Marktdaten-Implementierung gegen die V5-REST-API."""

    def __init__(self, settings: BybitSettings, *, client: BybitHTTPClient | None = None) -> None:
        self.settings = settings
        self.client = client or BybitHTTPClient(settings)
        self.category = settings.category

    def get_server_time(self) -> datetime:
        payload = self.client.get_public("/v5/market/time")
        nano = int(payload["result"]["timeNano"])
        return datetime.fromtimestamp(nano / 1_000_000_000, tz=UTC)

    def get_instrument(self, symbol: str) -> Instrument:
        payload = self.client.get_public(
            "/v5/market/instruments-info", {"category": self.category, "symbol": symbol}
        )
        entries = payload["result"]["list"]
        if not entries:
            raise ValueError(f"Kontrakt {symbol} nicht gefunden (category={self.category})")
        raw = entries[0]
        lot = raw["lotSizeFilter"]
        price_filter = raw["priceFilter"]
        leverage_filter = raw.get("leverageFilter", {})

        return Instrument(
            symbol=raw["symbol"],
            category=self.category,
            base_coin=raw.get("baseCoin", ""),
            quote_coin=raw.get("quoteCoin", ""),
            tick_size=_dec(price_filter["tickSize"]),
            qty_step=_dec(lot["qtyStep"]),
            min_order_qty=_dec(lot["minOrderQty"]),
            max_order_qty=_dec(lot["maxOrderQty"]),
            min_notional=_dec(lot.get("minNotionalValue"), "5"),
            max_leverage=_dec(leverage_filter.get("maxLeverage"), "100"),
            launch_time=_ts(raw.get("launchTime")),
        )

    def get_klines(
        self,
        symbol: str,
        interval: Interval,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 200,
    ) -> list[Candle]:
        """Kerzen holen, **aufsteigend nach Zeit sortiert**.

        Bybit liefert sie absteigend (neueste zuerst). Diese Umkehr genau hier
        zu machen ist wichtig: eine versehentlich rueckwaerts laufende Zeitreihe
        im Backtest ist ein Lookahead-Bug, der monatelang unentdeckt bleiben kann.
        """
        params: dict[str, Any] = {
            "category": self.category,
            "symbol": symbol,
            "interval": interval.value,
            "limit": min(limit, MAX_KLINE_LIMIT),
        }
        if start is not None:
            params["start"] = int(start.timestamp() * 1000)
        if end is not None:
            params["end"] = int(end.timestamp() * 1000)

        payload = self.client.get_public("/v5/market/kline", params)
        rows: list[list[str]] = payload["result"]["list"]

        candles = [
            Candle(
                open_time=datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
                open=_dec(row[1]),
                high=_dec(row[2]),
                low=_dec(row[3]),
                close=_dec(row[4]),
                volume=_dec(row[5]),
                turnover=_dec(row[6]),
            )
            for row in rows
        ]
        candles.sort(key=lambda c: c.open_time)
        return candles

    def get_ticker(self, symbol: str) -> Ticker:
        payload = self.client.get_public(
            "/v5/market/tickers", {"category": self.category, "symbol": symbol}
        )
        entries = payload["result"]["list"]
        if not entries:
            raise ValueError(f"Kein Ticker fuer {symbol}")
        raw = entries[0]
        return Ticker(
            symbol=raw["symbol"],
            last_price=_dec(raw["lastPrice"]),
            mark_price=_dec(raw.get("markPrice"), raw["lastPrice"]),
            index_price=_dec(raw.get("indexPrice"), raw["lastPrice"]),
            bid1_price=_dec(raw.get("bid1Price"), raw["lastPrice"]),
            ask1_price=_dec(raw.get("ask1Price"), raw["lastPrice"]),
            funding_rate=_dec(raw.get("fundingRate")),
            next_funding_time=_ts(raw.get("nextFundingTime")),
            turnover_24h=_dec(raw.get("turnover24h")),
        )

    def get_funding_history(
        self, symbol: str, *, start: datetime | None = None, limit: int = 200
    ) -> list[FundingRate]:
        params: dict[str, Any] = {
            "category": self.category,
            "symbol": symbol,
            "limit": min(limit, MAX_KLINE_LIMIT),
        }
        if start is not None:
            params["startTime"] = int(start.timestamp() * 1000)

        payload = self.client.get_public("/v5/market/funding/history", params)
        rates = [
            FundingRate(
                symbol=row["symbol"],
                funding_time=datetime.fromtimestamp(int(row["fundingRateTimestamp"]) / 1000, tz=UTC),
                funding_rate=_dec(row["fundingRate"]),
            )
            for row in payload["result"]["list"]
        ]
        rates.sort(key=lambda r: r.funding_time)
        return rates


class BybitAccount:
    """Lesender Kontozugriff. Schreibende Operationen kommen in Phase 4 dazu -
    bewusst getrennt, damit ein Read-Only-Key alles hier Verwendete abdeckt."""

    def __init__(self, settings: BybitSettings, *, client: BybitHTTPClient | None = None) -> None:
        self.settings = settings
        self.client = client or BybitHTTPClient(settings)
        self.category = settings.category

    def get_wallet_balance(self, coin: str = "USDT") -> WalletBalance:
        payload = self.client.get_private(
            "/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": coin}
        )
        accounts = payload["result"]["list"]
        if not accounts:
            raise ValueError("Keine Kontodaten erhalten - ist der Unified Account aktiviert?")

        coins = accounts[0].get("coin", [])
        entry = next((c for c in coins if c.get("coin") == coin), None)
        if entry is None:
            # Frischer Demo-Account ohne Guthaben in dieser Waehrung.
            return WalletBalance(
                coin=coin,
                equity=Decimal(0),
                available_balance=Decimal(0),
                wallet_balance=Decimal(0),
            )

        return WalletBalance(
            coin=coin,
            equity=_dec(entry.get("equity")),
            available_balance=_dec(
                entry.get("availableToWithdraw") or entry.get("walletBalance")
            ),
            wallet_balance=_dec(entry.get("walletBalance")),
            unrealised_pnl=_dec(entry.get("unrealisedPnl")),
        )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        params: dict[str, Any] = {"category": self.category}
        if symbol:
            params["symbol"] = symbol
        else:
            params["settleCoin"] = "USDT"

        payload = self.client.get_private("/v5/position/list", params)
        positions: list[Position] = []
        for raw in payload["result"]["list"]:
            size = _dec(raw.get("size"))
            if size == 0:
                continue  # Bybit liefert auch geschlossene Positionen mit size=0
            positions.append(
                Position(
                    symbol=raw["symbol"],
                    side=Side(raw["side"]),
                    size=size,
                    entry_price=_dec(raw.get("avgPrice")),
                    mark_price=_dec(raw.get("markPrice")),
                    leverage=_dec(raw.get("leverage"), "1"),
                    unrealised_pnl=_dec(raw.get("unrealisedPnl")),
                    realised_pnl=_dec(raw.get("curRealisedPnl")),
                    liq_price=_dec(raw["liqPrice"]) if raw.get("liqPrice") else None,
                    stop_loss=_dec(raw["stopLoss"]) if raw.get("stopLoss") else None,
                    take_profit=_dec(raw["takeProfit"]) if raw.get("takeProfit") else None,
                    position_value=_dec(raw.get("positionValue")),
                    opened_at=_ts(raw.get("createdTime")),
                )
            )
        return positions


def build_market_data(settings: BybitSettings) -> BybitMarketData:
    return BybitMarketData(settings)


def build_account(settings: BybitSettings) -> BybitAccount:
    return BybitAccount(settings)
