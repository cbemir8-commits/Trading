"""Schreibender Bybit-Zugriff: Orders, Hebel, Stops.

Bewusst getrennt von ``adapter.py``: Der lesende Teil kommt mit einem
Read-Only-Key aus, dieser hier braucht Handelsrechte. Die Trennung macht im
Code sichtbar, welche Stelle tatsaechlich Geld bewegen kann.

Order-Aufbau einer Position - jede Zeile hat einen Grund:

* **Einstieg**: PostOnly-Limit. Maker-Gebuehr (0,020 % statt 0,055 %) und kein
  Slippage-Risiko. Preis dafuer: Die Order fuellt womoeglich gar nicht.
* **Stop-Loss**: ueber ``/v5/position/trading-stop`` **an der Position**, nicht
  als eigene Order. Damit liegt er auf Bybits Servern und greift auch dann,
  wenn unser Prozess abstuerzt, der VPS neu startet oder das Netz ausfaellt.
  Das ist der wichtigste Einzelpunkt dieser Datei.
* **Take-Profits**: mehrere Reduce-Only-PostOnly-Limits. Ebenfalls Maker, und
  gestaffelt, wie es der Plan vorsieht.

Ein Stop als gewoehnliche Order waere ein Fehler: Faellt unser Prozess aus,
bevor er sie platziert hat, laeuft die Position ungeschuetzt.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

import structlog

from core.config import BybitSettings, MarginMode
from core.models import Order, OrderStatus, OrderType, Side, TimeInForce

from .client import BybitHTTPClient
from .errors import BybitAPIError

log = structlog.get_logger(__name__)

#: Bybit-Fehlercodes, die kein echtes Problem sind.
ALREADY_SET_CODES = frozenset(
    {
        110043,  # Hebel unveraendert
        34036,  # Margin-Modus unveraendert
        110025,  # Positionsmodus unveraendert
    }
)

#: Order existiert nicht mehr - beim Stornieren unkritisch.
ORDER_GONE_CODES = frozenset({110001, 20001})


def new_order_link_id(prefix: str = "t") -> str:
    """Eigene Order-Kennung.

    Bybit akzeptiert bis zu 36 Zeichen. Eine selbst vergebene Kennung erlaubt
    es, nach einem Neustart die eigenen Orders wiederzuerkennen - ohne sie
    wuesste der Prozess nach einem Absturz nicht, welche offenen Orders von ihm
    stammen.
    """
    return f"{prefix}-{uuid.uuid4().hex[:20]}"


@runtime_checkable
class TradingGateway(Protocol):
    """Alles, was Geld bewegen kann. Fuer Tests durch ein Double ersetzbar."""

    def set_leverage(self, symbol: str, leverage: Decimal) -> None: ...

    def set_margin_mode(self, symbol: str, mode: MarginMode, leverage: Decimal) -> None: ...

    def place_limit(
        self,
        *,
        symbol: str,
        side: Side,
        qty: Decimal,
        price: Decimal,
        reduce_only: bool = False,
        post_only: bool = True,
        order_link_id: str | None = None,
    ) -> Order: ...

    def place_market(
        self, *, symbol: str, side: Side, qty: Decimal, reduce_only: bool = False
    ) -> Order: ...

    def set_position_stop(
        self, *, symbol: str, stop_loss: Decimal | None, take_profit: Decimal | None = None
    ) -> None: ...

    def cancel_order(self, *, symbol: str, order_id: str) -> None: ...

    def cancel_all(self, symbol: str) -> int: ...

    def open_orders(self, symbol: str) -> list[Order]: ...


@dataclass(slots=True)
class BybitTrading:
    """Schreibende Operationen gegen die V5-API."""

    settings: BybitSettings
    client: BybitHTTPClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = BybitHTTPClient(self.settings)

    @property
    def _http(self) -> BybitHTTPClient:
        assert self.client is not None
        return self.client

    @property
    def category(self) -> str:
        return self.settings.category

    # -- Konto-Einstellungen -------------------------------------------------
    def set_leverage(self, symbol: str, leverage: Decimal) -> None:
        """Hebel am Symbol einstellen.

        Dieser Wert bestimmt bei Isolated Margin den Liquidationspreis - nicht
        die Positionsgroesse. Deshalb prueft der Sizer gegen genau diesen Wert.
        """
        try:
            self._http.post_private(
                "/v5/position/set-leverage",
                {
                    "category": self.category,
                    "symbol": symbol,
                    "buyLeverage": str(leverage),
                    "sellLeverage": str(leverage),
                },
            )
        except BybitAPIError as exc:
            if exc.ret_code in ALREADY_SET_CODES:
                return  # war schon so eingestellt
            raise
        log.info("bybit.hebel_gesetzt", symbol=symbol, hebel=str(leverage))

    def set_margin_mode(self, symbol: str, mode: MarginMode, leverage: Decimal) -> None:
        """Isolated oder Cross Margin.

        Isolated ist die sichere Wahl: Ein Totalverlust bleibt auf die Margin
        dieser einen Position begrenzt, statt das ganze Konto zu erfassen.
        """
        try:
            self._http.post_private(
                "/v5/position/switch-isolated",
                {
                    "category": self.category,
                    "symbol": symbol,
                    "tradeMode": 1 if mode is MarginMode.ISOLATED else 0,
                    "buyLeverage": str(leverage),
                    "sellLeverage": str(leverage),
                },
            )
        except BybitAPIError as exc:
            if exc.ret_code in ALREADY_SET_CODES:
                return
            raise
        log.info("bybit.margin_modus_gesetzt", symbol=symbol, modus=mode.value)

    # -- Orders --------------------------------------------------------------
    def place_limit(
        self,
        *,
        symbol: str,
        side: Side,
        qty: Decimal,
        price: Decimal,
        reduce_only: bool = False,
        post_only: bool = True,
        order_link_id: str | None = None,
    ) -> Order:
        """Limit-Order platzieren, standardmaessig PostOnly.

        PostOnly bedeutet: Wuerde die Order sofort ausgefuehrt, lehnt Bybit sie
        ab, statt sie als Taker auszufuehren. Das garantiert die Maker-Gebuehr -
        und ist der Grund, warum die Gebuehrenlast bei 30 Trades im Monat bei
        2 % statt 5,5 % des Kontos liegt.
        """
        link_id = order_link_id or new_order_link_id("e" if not reduce_only else "tp")
        body: dict[str, Any] = {
            "category": self.category,
            "symbol": symbol,
            "side": side.value,
            "orderType": OrderType.LIMIT.value,
            "qty": str(qty),
            "price": str(price),
            "timeInForce": (TimeInForce.POST_ONLY if post_only else TimeInForce.GTC).value,
            "orderLinkId": link_id,
        }
        if reduce_only:
            body["reduceOnly"] = True

        payload = self._http.post_private("/v5/order/create", body)
        result = payload.get("result", {})
        log.info(
            "bybit.limit_platziert",
            symbol=symbol,
            seite=side.value,
            menge=str(qty),
            preis=str(price),
            reduce_only=reduce_only,
        )
        return Order(
            order_id=str(result.get("orderId", "")),
            order_link_id=link_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            qty=qty,
            price=price,
            time_in_force=TimeInForce.POST_ONLY if post_only else TimeInForce.GTC,
            reduce_only=reduce_only,
            status=OrderStatus.NEW,
        )

    def place_market(
        self, *, symbol: str, side: Side, qty: Decimal, reduce_only: bool = False
    ) -> Order:
        """Market-Order - nur fuer Notausstiege.

        Im Normalbetrieb nie verwendet: Der Stop liegt an der Position, die
        Take-Profits sind Limits. Diese Methode ist fuer den Not-Aus da, wo
        sofortige Ausfuehrung wichtiger ist als die Gebuehr.
        """
        link_id = new_order_link_id("m")
        body: dict[str, Any] = {
            "category": self.category,
            "symbol": symbol,
            "side": side.value,
            "orderType": OrderType.MARKET.value,
            "qty": str(qty),
            "timeInForce": TimeInForce.IOC.value,
            "orderLinkId": link_id,
        }
        if reduce_only:
            body["reduceOnly"] = True

        payload = self._http.post_private("/v5/order/create", body)
        log.warning(
            "bybit.market_platziert",
            symbol=symbol,
            seite=side.value,
            menge=str(qty),
            hinweis="Market-Order zahlt Taker-Gebuehr - nur fuer Notausstiege",
        )
        return Order(
            order_id=str(payload.get("result", {}).get("orderId", "")),
            order_link_id=link_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            qty=qty,
            time_in_force=TimeInForce.IOC,
            reduce_only=reduce_only,
            status=OrderStatus.NEW,
        )

    def set_position_stop(
        self, *, symbol: str, stop_loss: Decimal | None, take_profit: Decimal | None = None
    ) -> None:
        """Stop-Loss an der Position setzen.

        **Der wichtigste Aufruf dieser Datei.** Der Stop liegt danach auf
        Bybits Servern und greift auch dann, wenn unser Prozess abstuerzt, der
        VPS neu startet oder die Leitung ausfaellt. Ein Stop, der nur in
        unserem Speicher existiert, ist bei genau den Ereignissen wertlos, gegen
        die er schuetzen soll.
        """
        body: dict[str, Any] = {
            "category": self.category,
            "symbol": symbol,
            "positionIdx": 0,
            "tpslMode": "Full",
        }
        if stop_loss is not None:
            body["stopLoss"] = str(stop_loss)
            body["slTriggerBy"] = "MarkPrice"
        if take_profit is not None:
            body["takeProfit"] = str(take_profit)
            body["tpTriggerBy"] = "MarkPrice"

        self._http.post_private("/v5/position/trading-stop", body)
        log.info(
            "bybit.stop_an_position_gesetzt",
            symbol=symbol,
            stop=str(stop_loss) if stop_loss else None,
        )

    def cancel_order(self, *, symbol: str, order_id: str) -> None:
        try:
            self._http.post_private(
                "/v5/order/cancel",
                {"category": self.category, "symbol": symbol, "orderId": order_id},
            )
        except BybitAPIError as exc:
            if exc.ret_code in ORDER_GONE_CODES:
                return  # bereits gefuellt oder storniert
            raise

    def cancel_all(self, symbol: str) -> int:
        payload = self._http.post_private(
            "/v5/order/cancel-all", {"category": self.category, "symbol": symbol}
        )
        cancelled = payload.get("result", {}).get("list", [])
        log.info("bybit.alle_storniert", symbol=symbol, anzahl=len(cancelled))
        return len(cancelled)

    def open_orders(self, symbol: str) -> list[Order]:
        payload = self._http.get_private(
            "/v5/order/realtime", {"category": self.category, "symbol": symbol}
        )
        orders: list[Order] = []
        for raw in payload.get("result", {}).get("list", []):
            orders.append(
                Order(
                    order_id=str(raw.get("orderId", "")),
                    order_link_id=str(raw.get("orderLinkId", "")),
                    symbol=raw["symbol"],
                    side=Side(raw["side"]),
                    order_type=OrderType(raw.get("orderType", "Limit")),
                    qty=Decimal(str(raw.get("qty", "0"))),
                    price=Decimal(str(raw["price"])) if raw.get("price") else None,
                    reduce_only=bool(raw.get("reduceOnly", False)),
                    status=OrderStatus(raw.get("orderStatus", "New")),
                    filled_qty=Decimal(str(raw.get("cumExecQty", "0"))),
                )
            )
        return orders
