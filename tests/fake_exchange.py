"""Eine simulierte Boerse fuer Tests.

Erfuellt dasselbe ``TradingGateway``-Protokoll wie der echte Bybit-Adapter.
Damit laesst sich die komplette Ausfuehrungslogik pruefen, ohne eine Order zu
riskieren - und ohne Netzwerk, was in diesem geoblockten Container die einzige
Moeglichkeit ist.

Bewusst nachgebildet werden die Eigenheiten, die in der Praxis Fehler
verursachen:

* **PostOnly-Ablehnung**, wenn die Order sofort ausfuehrbar waere. Der haeufigste
  Grund, warum ein Einstieg live nicht zustande kommt, obwohl der Backtest ihn
  zeigt.
* **Teil-Fills** - eine Order fuellt nicht immer vollstaendig.
* **"Order existiert nicht mehr"** beim Stornieren. Tritt auf, wenn die Order
  zwischen Abfrage und Storno gefuellt wurde.
* **Gezielte Fehlerinjektion**, um die unangenehmen Pfade zu pruefen: Was
  passiert, wenn das Setzen des Stops fehlschlaegt?
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.config import MarginMode
from core.models import (
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    TimeInForce,
    WalletBalance,
)
from data.bybit.errors import BybitAPIError


@dataclass(slots=True)
class FakePosition:
    side: Side
    size: Decimal
    entry_price: Decimal
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None


class FakeExchange:
    """Simulierte Boerse mit Orderbuch, Position und Fehlerinjektion."""

    def __init__(self, *, mark_price: Decimal = Decimal("100000")) -> None:
        self.mark_price = mark_price
        self.orders: dict[str, Order] = {}
        self.position: FakePosition | None = None
        self.leverage: Decimal | None = None
        self.margin_mode: MarginMode | None = None

        #: Protokoll aller Aufrufe - fuer Tests, die die Reihenfolge pruefen.
        self.calls: list[tuple[str, dict]] = []

        #: Fehlerinjektion: Methodenname -> Ausnahme, die geworfen wird.
        self.fail_on: dict[str, Exception] = {}

        #: Wenn gesetzt, fuellen Limit-Orders nur zu diesem Anteil.
        self.partial_fill_ratio: Decimal | None = None

        self._next_id = 1

    # -- Steuerung fuer Tests ------------------------------------------------
    def set_mark_price(self, price: Decimal) -> None:
        self.mark_price = price

    def fail_next(self, method: str, error: Exception) -> None:
        self.fail_on[method] = error

    def _check_failure(self, method: str) -> None:
        error = self.fail_on.pop(method, None)
        if error is not None:
            raise error

    def _record(self, method: str, **kwargs) -> None:
        self.calls.append((method, kwargs))

    @property
    def call_order(self) -> list[str]:
        """Nur die Methodennamen, in Aufrufreihenfolge.

        Damit laesst sich pruefen, dass der Stop **vor** den Take-Profits
        gesetzt wird - die sicherheitsrelevante Reihenfolge.
        """
        return [name for name, _ in self.calls]

    def _new_id(self) -> str:
        self._next_id += 1
        return f"fake-{self._next_id:06d}"

    # -- TradingGateway ------------------------------------------------------
    def set_leverage(self, symbol: str, leverage: Decimal) -> None:
        self._record("set_leverage", symbol=symbol, leverage=leverage)
        self._check_failure("set_leverage")
        self.leverage = leverage

    def set_margin_mode(self, symbol: str, mode: MarginMode, leverage: Decimal) -> None:
        self._record("set_margin_mode", symbol=symbol, mode=mode)
        self._check_failure("set_margin_mode")
        self.margin_mode = mode
        self.leverage = leverage

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
        self._record(
            "place_limit",
            side=side,
            qty=qty,
            price=price,
            reduce_only=reduce_only,
            post_only=post_only,
        )
        self._check_failure("place_limit")

        # PostOnly wird abgelehnt, wenn die Order sofort ausfuehrbar waere.
        # Ein Kauflimit oberhalb des Marktes wuerde sofort als Taker fuellen -
        # genau das soll PostOnly verhindern.
        if post_only and self._would_execute_immediately(side, price):
            raise BybitAPIError(
                110001,
                "Order would immediately match and take liquidity (PostOnly)",
                endpoint="/v5/order/create",
            )

        order = Order(
            order_id=self._new_id(),
            order_link_id=order_link_id or "",
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            qty=qty,
            price=price,
            time_in_force=TimeInForce.POST_ONLY if post_only else TimeInForce.GTC,
            reduce_only=reduce_only,
            status=OrderStatus.NEW,
        )
        self.orders[order.order_id] = order
        return order

    def _would_execute_immediately(self, side: Side, price: Decimal) -> bool:
        if side is Side.BUY:
            return price >= self.mark_price
        return price <= self.mark_price

    def place_market(
        self, *, symbol: str, side: Side, qty: Decimal, reduce_only: bool = False
    ) -> Order:
        self._record("place_market", side=side, qty=qty, reduce_only=reduce_only)
        self._check_failure("place_market")

        order = Order(
            order_id=self._new_id(),
            order_link_id="",
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            qty=qty,
            price=self.mark_price,
            time_in_force=TimeInForce.IOC,
            reduce_only=reduce_only,
            status=OrderStatus.FILLED,
            filled_qty=qty,
            avg_fill_price=self.mark_price,
        )
        self.orders[order.order_id] = order

        if reduce_only and self.position is not None:
            self.position.size -= qty
            if self.position.size <= 0:
                self.position = None
        return order

    def set_position_stop(
        self, *, symbol: str, stop_loss: Decimal | None, take_profit: Decimal | None = None
    ) -> None:
        self._record("set_position_stop", stop_loss=stop_loss, take_profit=take_profit)
        self._check_failure("set_position_stop")

        if self.position is None:
            raise BybitAPIError(110017, "position not found", endpoint="/v5/position/trading-stop")
        if stop_loss is not None:
            self.position.stop_loss = stop_loss
        if take_profit is not None:
            self.position.take_profit = take_profit

    def cancel_order(self, *, symbol: str, order_id: str) -> None:
        self._record("cancel_order", order_id=order_id)
        self._check_failure("cancel_order")

        order = self.orders.get(order_id)
        if order is None or order.status.is_terminal:
            # Der echte Adapter schluckt diesen Fall - die Order war schon weg.
            return
        self.orders[order_id] = order.model_copy(update={"status": OrderStatus.CANCELLED})

    def cancel_all(self, symbol: str) -> int:
        self._record("cancel_all", symbol=symbol)
        self._check_failure("cancel_all")

        cancelled = 0
        for order_id, order in list(self.orders.items()):
            if not order.status.is_terminal:
                self.orders[order_id] = order.model_copy(
                    update={"status": OrderStatus.CANCELLED}
                )
                cancelled += 1
        return cancelled

    def open_orders(self, symbol: str) -> list[Order]:
        return [o for o in self.orders.values() if not o.status.is_terminal]

    # -- Simulation der Ausfuehrung ------------------------------------------
    def fill(self, order_id: str, *, qty: Decimal | None = None) -> Decimal:
        """Eine offene Order (teilweise) fuellen und die Position fortschreiben."""
        order = self.orders[order_id]
        fill_qty = qty or order.remaining_qty
        if self.partial_fill_ratio is not None and qty is None:
            fill_qty = order.qty * self.partial_fill_ratio

        price = order.price or self.mark_price
        filled_total = order.filled_qty + fill_qty
        status = OrderStatus.FILLED if filled_total >= order.qty else OrderStatus.PARTIALLY_FILLED

        self.orders[order_id] = order.model_copy(
            update={"filled_qty": filled_total, "avg_fill_price": price, "status": status}
        )

        if order.reduce_only:
            if self.position is not None:
                self.position.size -= fill_qty
                if self.position.size <= 0:
                    self.position = None
        elif self.position is None:
            self.position = FakePosition(side=order.side, size=fill_qty, entry_price=price)
        else:
            self.position.size += fill_qty

        return fill_qty


class FakeAccount:
    """Kontosicht auf **dieselbe** simulierte Boerse.

    Bewusst abgeleitet statt separat gepflegt: Ein Test, in dem Kontostand und
    Orderbuch auseinanderlaufen koennen, prueft am Ende die Testdoubles statt
    des Systems. Was der Router an der Boerse tut, sieht das Konto sofort.
    """

    def __init__(
        self,
        exchange: FakeExchange,
        *,
        equity: Decimal = Decimal("500"),
        symbol: str = "BTCUSDT",
        leverage: Decimal = Decimal("3"),
    ) -> None:
        self.exchange = exchange
        self.equity = equity
        self.symbol = symbol
        self.leverage = leverage

    def set_equity(self, equity: Decimal) -> None:
        """Kapitalstand setzen - fuer Drawdown- und Kill-Switch-Tests."""
        self.equity = equity

    # -- AccountSource -------------------------------------------------------
    def get_wallet_balance(self, coin: str = "USDT") -> WalletBalance:
        return WalletBalance(
            coin=coin,
            equity=self.equity,
            available_balance=self.equity,
            wallet_balance=self.equity,
        )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        position = self.exchange.position
        if position is None or position.size <= 0:
            return []  # wie der echte Adapter: size==0 wird herausgefiltert
        return [
            Position(
                symbol=symbol or self.symbol,
                side=position.side,
                size=position.size,
                entry_price=position.entry_price,
                mark_price=self.exchange.mark_price,
                leverage=self.leverage,
                unrealised_pnl=Decimal(0),
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                position_value=position.size * position.entry_price,
            )
        ]
