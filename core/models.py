"""Domaenenmodelle.

Konvention zu Zahlentypen - das ist eine bewusste Entscheidung, keine Stilfrage:

* ``Decimal`` fuer alles, was zur Boerse geht (Preise, Mengen, Geld).
  Float-Rundung auf ``qty_step`` erzeugt sonst Mengen wie 0.009000000000000001,
  die Bybit mit einem Fehler ablehnt - oder schlimmer: still auf 0.008 kuerzt.
* ``float`` nur fuer Indikatormathematik (numpy/pandas), konvertiert an der Grenze.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
#  Basistypen
# ---------------------------------------------------------------------------
class Interval(StrEnum):
    """Kerzen-Intervalle. Der Wert ist exakt der Bybit-API-Parameter."""

    M1 = "1"
    M3 = "3"
    M5 = "5"
    M15 = "15"
    M30 = "30"
    H1 = "60"
    H2 = "120"
    H4 = "240"
    H6 = "360"
    H12 = "720"
    D1 = "D"
    W1 = "W"
    MN1 = "M"

    @property
    def duration(self) -> timedelta:
        minutes = {
            Interval.M1: 1,
            Interval.M3: 3,
            Interval.M5: 5,
            Interval.M15: 15,
            Interval.M30: 30,
            Interval.H1: 60,
            Interval.H2: 120,
            Interval.H4: 240,
            Interval.H6: 360,
            Interval.H12: 720,
            Interval.D1: 1440,
            Interval.W1: 10_080,
        }
        if self is Interval.MN1:
            raise ValueError("Monatsintervall hat keine feste Dauer")
        return timedelta(minutes=minutes[self])

    @property
    def label(self) -> str:
        """Menschenlesbar, z.B. '15m' statt '15'."""
        return {
            Interval.M1: "1m",
            Interval.M3: "3m",
            Interval.M5: "5m",
            Interval.M15: "15m",
            Interval.M30: "30m",
            Interval.H1: "1h",
            Interval.H2: "2h",
            Interval.H4: "4h",
            Interval.H6: "6h",
            Interval.H12: "12h",
            Interval.D1: "1d",
            Interval.W1: "1w",
            Interval.MN1: "1M",
        }[self]


class Side(StrEnum):
    BUY = "Buy"
    SELL = "Sell"

    @property
    def opposite(self) -> Side:
        return Side.SELL if self is Side.BUY else Side.BUY

    @property
    def sign(self) -> Decimal:
        """+1 fuer Long, -1 fuer Short - fuer PnL-Rechnungen."""
        return Decimal(1) if self is Side.BUY else Decimal(-1)


class OrderType(StrEnum):
    MARKET = "Market"
    LIMIT = "Limit"


class TimeInForce(StrEnum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "PostOnly"


class OrderStatus(StrEnum):
    NEW = "New"
    PARTIALLY_FILLED = "PartiallyFilled"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"
    TRIGGERED = "Triggered"
    UNTRIGGERED = "Untriggered"

    @property
    def is_terminal(self) -> bool:
        return self in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}


class LiquidityRole(StrEnum):
    """Bestimmt die Gebuehr. Maker ist bei kleinem Konto ueberlebenswichtig."""

    MAKER = "maker"
    TAKER = "taker"


# ---------------------------------------------------------------------------
#  Marktdaten
# ---------------------------------------------------------------------------
class Candle(BaseModel):
    """Eine abgeschlossene Kerze.

    ``open_time`` ist der *Beginn* der Periode - so liefert Bybit es auch.
    Eine Kerze gilt erst als handelbar, wenn ``open_time + interval`` erreicht ist.
    Diese Unterscheidung ist der haeufigste Weg, versehentlich in die Zukunft zu schauen.
    """

    model_config = ConfigDict(frozen=True)

    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal

    @model_validator(mode="after")
    def _check_ohlc(self) -> Self:
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise ValueError(
                f"Inkonsistente OHLC bei {self.open_time}: "
                f"O={self.open} H={self.high} L={self.low} C={self.close}"
            )
        if self.volume < 0 or self.turnover < 0:
            raise ValueError(f"Negatives Volumen bei {self.open_time}")
        return self

    def close_time(self, interval: Interval) -> datetime:
        return self.open_time + interval.duration

    @property
    def typical_price(self) -> Decimal:
        return (self.high + self.low + self.close) / 3

    @property
    def range(self) -> Decimal:
        return self.high - self.low


class Instrument(BaseModel):
    """Kontraktspezifikation. Quelle der Wahrheit fuer alle Rundungen.

    Ohne korrektes Runden auf ``qty_step`` und ``tick_size`` lehnt Bybit Orders ab.
    Bei einem 500-EUR-Konto ist die Granularitaet spuerbar: BTCUSDT hat 0.001 BTC
    Schrittweite, was bei 100k$ rund 100$ Nominalwert pro Schritt bedeutet.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    category: str = "linear"
    base_coin: str = "BTC"
    quote_coin: str = "USDT"

    tick_size: Decimal
    qty_step: Decimal
    min_order_qty: Decimal
    max_order_qty: Decimal
    min_notional: Decimal = Decimal("5")

    max_leverage: Decimal = Decimal("100")
    maintenance_margin_rate: Decimal = Decimal("0.005")

    launch_time: datetime | None = None

    def round_price(self, price: Decimal, *, side: Side | None = None) -> Decimal:
        """Auf ``tick_size`` runden.

        Mit ``side`` wird konservativ gerundet: Ein Kauf-Limit rundet nach unten
        (guenstiger, bleibt sicher Maker), ein Verkauf-Limit nach oben.
        """
        if self.tick_size <= 0:
            return price
        steps = price / self.tick_size
        if side is Side.BUY:
            steps = steps.to_integral_value(rounding=ROUND_DOWN)
        elif side is Side.SELL:
            steps = (steps + Decimal("0.9999999999")).to_integral_value(rounding=ROUND_DOWN)
        else:
            steps = steps.to_integral_value(rounding=ROUND_HALF_UP)
        return (steps * self.tick_size).quantize(self.tick_size)

    def round_qty(self, qty: Decimal) -> Decimal:
        """Immer auf ``qty_step`` ABRUNDEN.

        Abrunden statt kaufmaennisch runden ist Absicht: eine zu grosse Position
        verletzt das Risikolimit, eine minimal zu kleine kostet nur etwas Gewinn.
        """
        if self.qty_step <= 0:
            return qty
        steps = (qty / self.qty_step).to_integral_value(rounding=ROUND_DOWN)
        return (steps * self.qty_step).quantize(self.qty_step)

    def is_tradable_qty(self, qty: Decimal) -> bool:
        return self.min_order_qty <= qty <= self.max_order_qty

    def estimate_liquidation_price(
        self, *, entry: Decimal, side: Side, leverage: Decimal
    ) -> Decimal:
        """Naeherung des Liquidationspreises fuer Isolated Margin.

        Nur als *Vorab-Schutz* gedacht. Sobald die Position offen ist, gilt der
        von Bybit gelieferte ``liqPrice`` als Wahrheit - der beruecksichtigt
        Gebuehren, Funding und die gestaffelte Risikolimit-Tabelle.

        Long : liq ~ entry x (1 - 1/hebel + mmr)
        Short: liq ~ entry x (1 + 1/hebel - mmr)
        """
        if leverage <= 0:
            raise ValueError("Hebel muss positiv sein")
        inv = Decimal(1) / leverage
        if side is Side.BUY:
            factor = Decimal(1) - inv + self.maintenance_margin_rate
        else:
            factor = Decimal(1) + inv - self.maintenance_margin_rate
        return entry * max(factor, Decimal(0))


class FundingRate(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    funding_time: datetime
    funding_rate: Decimal


class Ticker(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    last_price: Decimal
    mark_price: Decimal
    index_price: Decimal
    bid1_price: Decimal
    ask1_price: Decimal
    funding_rate: Decimal
    next_funding_time: datetime | None = None
    turnover_24h: Decimal = Decimal(0)

    @property
    def mid_price(self) -> Decimal:
        return (self.bid1_price + self.ask1_price) / 2

    @property
    def spread_pct(self) -> Decimal:
        if self.mid_price <= 0:
            return Decimal(0)
        return (self.ask1_price - self.bid1_price) / self.mid_price * 100


# ---------------------------------------------------------------------------
#  Handelsobjekte
# ---------------------------------------------------------------------------
class TakeProfitLeg(BaseModel):
    """Eine von mehreren Take-Profit-Stufen."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    portion: Decimal = Field(gt=0, le=1, description="Anteil der Gesamtposition, 0..1")
    move_stop_to_breakeven: bool = False


class Signal(BaseModel):
    """Was eine Strategie ausgibt. Enthaelt bewusst KEINE Positionsgroesse -
    die bestimmt allein der Risk-Officer."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    symbol: str
    side: Side
    entry_price: Decimal
    stop_loss: Decimal
    take_profits: list[TakeProfitLeg] = Field(default_factory=list)
    strategy_id: str
    reason: str = ""
    confidence: Decimal = Decimal("1.0")

    @model_validator(mode="after")
    def _check_geometry(self) -> Self:
        """Stop und Ziele muessen auf der richtigen Seite des Einstiegs liegen."""
        if self.side is Side.BUY:
            if self.stop_loss >= self.entry_price:
                raise ValueError(
                    f"Long-Stop {self.stop_loss} muss unter dem Einstieg {self.entry_price} liegen"
                )
            bad = [tp.price for tp in self.take_profits if tp.price <= self.entry_price]
        else:
            if self.stop_loss <= self.entry_price:
                raise ValueError(
                    f"Short-Stop {self.stop_loss} muss ueber dem Einstieg {self.entry_price} liegen"
                )
            bad = [tp.price for tp in self.take_profits if tp.price >= self.entry_price]
        if bad:
            raise ValueError(f"Take-Profits auf der falschen Seite des Einstiegs: {bad}")

        total = sum((tp.portion for tp in self.take_profits), Decimal(0))
        if total > 1:
            raise ValueError(f"Take-Profit-Anteile summieren sich auf {total} (max. 1)")
        return self

    @property
    def stop_distance(self) -> Decimal:
        return abs(self.entry_price - self.stop_loss)

    @property
    def stop_distance_pct(self) -> Decimal:
        if self.entry_price <= 0:
            return Decimal(0)
        return self.stop_distance / self.entry_price * 100

    def reward_risk_at(self, tp_index: int = 0) -> Decimal:
        """Chance-Risiko-Verhaeltnis der angegebenen Take-Profit-Stufe."""
        if not self.take_profits or self.stop_distance == 0:
            return Decimal(0)
        tp = self.take_profits[tp_index]
        return abs(tp.price - self.entry_price) / self.stop_distance


class Order(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    order_link_id: str
    symbol: str
    side: Side
    order_type: OrderType
    qty: Decimal
    price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False
    status: OrderStatus = OrderStatus.NEW
    filled_qty: Decimal = Decimal(0)
    avg_fill_price: Decimal | None = None
    created_at: datetime | None = None

    @property
    def remaining_qty(self) -> Decimal:
        return self.qty - self.filled_qty


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    side: Side
    size: Decimal
    entry_price: Decimal
    mark_price: Decimal
    leverage: Decimal
    unrealised_pnl: Decimal
    realised_pnl: Decimal = Decimal(0)
    liq_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    position_value: Decimal = Decimal(0)
    opened_at: datetime | None = None

    @property
    def is_flat(self) -> bool:
        return self.size == 0

    def distance_to_liquidation_pct(self) -> Decimal | None:
        """Wie weit ist die Liquidation entfernt, in Prozent des Markpreises."""
        if self.liq_price is None or self.mark_price <= 0:
            return None
        return abs(self.mark_price - self.liq_price) / self.mark_price * 100


class Fill(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    symbol: str
    side: Side
    price: Decimal
    qty: Decimal
    fee: Decimal
    role: LiquidityRole
    timestamp: datetime


class Trade(BaseModel):
    """Ein abgeschlossener Roundtrip - die Einheit, auf der alle Kennzahlen rechnen."""

    model_config = ConfigDict(frozen=True)

    trade_id: str
    symbol: str
    side: Side
    strategy_id: str

    entry_time: datetime
    entry_price: Decimal
    exit_time: datetime
    exit_price: Decimal
    qty: Decimal

    gross_pnl: Decimal
    fees: Decimal
    funding: Decimal = Decimal(0)

    stop_loss: Decimal | None = None
    exit_reason: str = ""
    leverage: Decimal = Decimal(1)
    max_adverse_excursion: Decimal = Decimal(0)
    max_favourable_excursion: Decimal = Decimal(0)

    @property
    def net_pnl(self) -> Decimal:
        """Was wirklich auf dem Konto ankommt. Die einzige Zahl, die zaehlt."""
        return self.gross_pnl - self.fees - self.funding

    @property
    def duration(self) -> timedelta:
        return self.exit_time - self.entry_time

    @property
    def is_win(self) -> bool:
        return self.net_pnl > 0

    @property
    def r_multiple(self) -> Decimal | None:
        """Ergebnis in Vielfachen des riskierten Betrags - die aussagekraeftigste
        Einzelkennzahl, weil sie ueber verschiedene Positionsgroessen vergleichbar ist."""
        if self.stop_loss is None:
            return None
        risk_per_unit = abs(self.entry_price - self.stop_loss)
        if risk_per_unit == 0:
            return None
        return self.net_pnl / (risk_per_unit * self.qty)


class WalletBalance(BaseModel):
    model_config = ConfigDict(frozen=True)

    coin: str
    equity: Decimal
    available_balance: Decimal
    wallet_balance: Decimal
    unrealised_pnl: Decimal = Decimal(0)
