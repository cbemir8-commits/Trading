"""Order-Router: baut aus einem genehmigten Signal eine Position an der Boerse.

Die Reihenfolge der Schritte ist sicherheitsrelevant, nicht beliebig:

1. Hebel und Margin-Modus setzen (einmalig, danach steht es)
2. **Einstieg** als PostOnly-Limit
3. Auf Fill warten (begrenzt; sonst stornieren)
4. **Sofort nach Fill: Stop an die Position setzen**
5. Danach die Take-Profits als Reduce-Only-Limits
6. Nach dem ersten Ziel: Stop auf Einstand nachziehen

Schritt 4 kommt **vor** Schritt 5. Zwischen Fill und gesetztem Stop ist die
Position ungeschuetzt - dieses Fenster muss so klein wie moeglich sein. Die
Take-Profits koennen warten, der Stop nicht.

Der Router bedient zwei Marktarten:

* **Perpetual** - mit Hebel, Stop an der Position, Funding.
* **Spot** - ohne Hebel, ohne Liquidation, ohne Funding. Der Stop kann dort
  nicht an einer Position haengen (es gibt keine), sondern laeuft als
  Stop-Market-Order. Das ist schwaecher: Faellt unser Prozess aus, bevor er
  sie platziert hat, ist die Position ungeschuetzt.

Die Unterscheidung sitzt an genau einer Stelle (``MarketKind``), damit ein
Wechsel keine Umbauten quer durchs System bedeutet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

import structlog

from core.config import MarginMode, RiskSettings
from core.models import Instrument, Order, Side, Signal
from data.bybit.trading import TradingGateway, new_order_link_id
from execution.sizing import SizedPosition

log = structlog.get_logger(__name__)


class MarketKind(StrEnum):
    """Welche Art Markt gehandelt wird.

    Der Unterschied ist nicht kosmetisch: Auf Spot gibt es keinen Hebel, keine
    Liquidation und keinen boersenseitigen Positions-Stop. Wer das vermischt,
    baut ein System, das im Backtest Hebel annimmt, den es live nicht gibt.
    """

    PERPETUAL = "perpetual"
    SPOT = "spot"

    @property
    def supports_leverage(self) -> bool:
        return self is MarketKind.PERPETUAL

    @property
    def supports_shorts(self) -> bool:
        return self is MarketKind.PERPETUAL

    @property
    def has_position_stop(self) -> bool:
        """Kann der Stop boersenseitig an der Position haengen?

        Nur bei Perpetuals. Auf Spot bleibt nur eine Stop-Order - die ist
        schwaecher, weil sie erst existiert, nachdem unser Prozess sie
        platziert hat.
        """
        return self is MarketKind.PERPETUAL


class BracketState(StrEnum):
    PENDING_ENTRY = "pending_entry"
    PROTECTED = "protected"
    """Position offen, Stop gesetzt - der Normalzustand."""

    UNPROTECTED = "unprotected"
    """Position offen, Stop NICHT gesetzt. Gefahrenzustand, muss sofort
    behoben oder die Position geschlossen werden."""

    CLOSED = "closed"
    EXPIRED = "expired"


@dataclass(slots=True)
class Bracket:
    """Eine Position samt ihrer Schutz-Orders."""

    signal: Signal
    sized: SizedPosition
    state: BracketState = BracketState.PENDING_ENTRY

    entry_order: Order | None = None
    entry_price: Decimal | None = None
    filled_qty: Decimal = Decimal(0)
    remaining_qty: Decimal = Decimal(0)

    stop_price: Decimal | None = None
    stop_order_id: str | None = None
    take_profit_orders: list[Order] = field(default_factory=list)
    targets_hit: int = 0
    moved_to_breakeven: bool = False

    opened_at: datetime | None = None
    placed_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.state in {BracketState.PROTECTED, BracketState.UNPROTECTED}

    @property
    def is_protected(self) -> bool:
        return self.state is BracketState.PROTECTED

    def describe(self) -> str:
        if self.state is BracketState.PENDING_ENTRY:
            return (
                f"Warte auf Einstieg {self.signal.side.value} "
                f"{self.sized.qty} @ {self.signal.entry_price}"
            )
        if self.is_open:
            marker = "" if self.is_protected else " [OHNE STOP]"
            return (
                f"{self.signal.side.value} {self.remaining_qty} @ {self.entry_price}, "
                f"Stop {self.stop_price}, {self.targets_hit} Ziele erreicht{marker}"
            )
        return f"Geschlossen ({self.state.value})"


class OrderRouter:
    """Setzt genehmigte Signale in Orders um."""

    def __init__(
        self,
        gateway: TradingGateway,
        instrument: Instrument,
        risk: RiskSettings,
        *,
        market_kind: MarketKind = MarketKind.PERPETUAL,
        clock=None,
    ) -> None:
        self.gateway = gateway
        self.instrument = instrument
        self.risk = risk
        self.market_kind = market_kind
        self.clock = clock or (lambda: __import__("datetime").datetime.now(
            __import__("datetime").UTC
        ))
        self._account_prepared = False

    # -- Einmalige Kontovorbereitung -----------------------------------------
    def prepare_account(self) -> None:
        """Margin-Modus und Hebel setzen.

        Muss vor der ersten Order laufen. Der eingestellte Hebel bestimmt bei
        Isolated Margin den Liquidationspreis - deshalb prueft der Sizer gegen
        genau diesen Wert und nicht gegen das Verhaeltnis Nominalwert/Kapital.

        Auf Spot entfaellt beides.
        """
        if self._account_prepared or not self.market_kind.supports_leverage:
            self._account_prepared = True
            return

        self.gateway.set_margin_mode(
            self.instrument.symbol, MarginMode.ISOLATED, self.risk.max_leverage
        )
        self.gateway.set_leverage(self.instrument.symbol, self.risk.max_leverage)
        self._account_prepared = True
        log.info(
            "router.konto_vorbereitet",
            symbol=self.instrument.symbol,
            hebel=str(self.risk.max_leverage),
            modus="isolated",
        )

    # -- Einstieg ------------------------------------------------------------
    def open(self, signal: Signal, sized: SizedPosition) -> Bracket:
        """Einstiegsorder platzieren.

        Als PostOnly-Limit: Wuerde sie sofort ausgefuehrt, lehnt Bybit sie ab,
        statt sie als Taker auszufuehren. Das garantiert die Maker-Gebuehr - bei
        30 Trades im Monat der Unterschied zwischen 2 % und 5,5 % Gebuehrenlast.
        """
        if signal.side is Side.SELL and not self.market_kind.supports_shorts:
            raise ValueError(
                f"Short-Signal, aber {self.market_kind.value} kennt keine Shorts. "
                "Auf Spot kann nur gekauft werden."
            )

        self.prepare_account()

        entry_price = self.instrument.round_price(signal.entry_price, side=signal.side)
        order = self.gateway.place_limit(
            symbol=self.instrument.symbol,
            side=signal.side,
            qty=sized.qty,
            price=entry_price,
            post_only=self.risk.require_maker_entry,
            order_link_id=new_order_link_id("entry"),
        )

        log.info(
            "router.einstieg_platziert",
            seite=signal.side.value,
            menge=str(sized.qty),
            preis=str(entry_price),
            hebel=f"{sized.leverage:.2f}x",
            risiko=f"{sized.risk_amount:.2f}",
        )
        return Bracket(
            signal=signal,
            sized=sized,
            entry_order=order,
            remaining_qty=sized.qty,
            placed_at=self.clock(),
        )

    # -- Absicherung ---------------------------------------------------------
    def protect(self, bracket: Bracket, *, filled_qty: Decimal, fill_price: Decimal) -> None:
        """Nach dem Fill: Stop setzen, dann Take-Profits.

        Diese Reihenfolge ist der Kern der Sicherheit. Zwischen Fill und
        gesetztem Stop ist die Position ungeschuetzt; das Fenster muss so klein
        wie moeglich sein. Scheitert das Setzen des Stops, wird die Position
        sofort geschlossen - lieber ein unnoetiger Ausstieg als eine
        ungeschuetzte Position.
        """
        bracket.filled_qty = filled_qty
        bracket.remaining_qty = filled_qty
        bracket.entry_price = fill_price
        bracket.opened_at = self.clock()
        bracket.state = BracketState.UNPROTECTED

        stop_price = self.instrument.round_price(
            bracket.signal.stop_loss, side=bracket.signal.side.opposite
        )

        try:
            self._place_stop(bracket, stop_price)
        except Exception as exc:
            log.critical(
                "router.stop_fehlgeschlagen",
                fehler=str(exc),
                massnahme="Position wird sofort geschlossen",
            )
            self.emergency_close(bracket, reason="Stop konnte nicht gesetzt werden")
            raise

        bracket.stop_price = stop_price
        bracket.state = BracketState.PROTECTED

        self._place_targets(bracket)

        log.info(
            "router.position_abgesichert",
            einstieg=str(fill_price),
            stop=str(stop_price),
            ziele=len(bracket.take_profit_orders),
        )

    def _place_stop(self, bracket: Bracket, stop_price: Decimal) -> None:
        if self.market_kind.has_position_stop:
            # Der gute Fall: Der Stop liegt an der Position auf Bybits Servern
            # und ueberlebt einen Absturz unseres Prozesses.
            self.gateway.set_position_stop(
                symbol=self.instrument.symbol, stop_loss=stop_price
            )
            return

        # Spot: kein Positions-Stop moeglich. Eine Stop-Order ist der beste
        # verfuegbare Ersatz - aber schwaecher, weil sie erst existiert,
        # nachdem wir sie platziert haben.
        log.warning(
            "router.spot_stop",
            hinweis="Auf Spot gibt es keinen boersenseitigen Positions-Stop. "
            "Der Schutz haengt an einer Order, die wir selbst platzieren.",
        )
        order = self.gateway.place_limit(
            symbol=self.instrument.symbol,
            side=bracket.signal.side.opposite,
            qty=bracket.remaining_qty,
            price=stop_price,
            reduce_only=True,
            post_only=False,
            order_link_id=new_order_link_id("stop"),
        )
        bracket.stop_order_id = order.order_id

    def _place_targets(self, bracket: Bracket) -> None:
        """Take-Profits als Reduce-Only-PostOnly-Limits.

        Reduce-Only stellt sicher, dass eine Zielorder die Position nur
        verkleinern und niemals versehentlich eine Gegenposition eroeffnen kann.
        """
        for price, qty in bracket.sized.take_profit_legs:
            if qty <= 0:
                continue
            rounded = self.instrument.round_price(price, side=bracket.signal.side)
            order = self.gateway.place_limit(
                symbol=self.instrument.symbol,
                side=bracket.signal.side.opposite,
                qty=qty,
                price=rounded,
                reduce_only=True,
                post_only=True,
                order_link_id=new_order_link_id("tp"),
            )
            bracket.take_profit_orders.append(order)

    # -- Verwaltung waehrend der Haltedauer ----------------------------------
    def on_target_hit(self, bracket: Bracket, *, qty: Decimal) -> None:
        """Ein Take-Profit wurde gefuellt.

        Nach dem ersten Ziel wandert der Stop auf den Einstand. Ab da kann der
        Trade nicht mehr ins Minus laufen - der wirksamste einzelne Schutz der
        Kapitalkurve.
        """
        bracket.targets_hit += 1
        bracket.remaining_qty -= qty

        if bracket.remaining_qty <= 0:
            bracket.state = BracketState.CLOSED
            log.info("router.position_geschlossen", grund="alle Ziele erreicht")
            return

        if not bracket.moved_to_breakeven and bracket.entry_price is not None:
            self.move_stop(bracket, bracket.entry_price)
            bracket.moved_to_breakeven = True
            log.info("router.stop_auf_einstand", einstand=str(bracket.entry_price))

    def move_stop(self, bracket: Bracket, new_stop: Decimal) -> None:
        rounded = self.instrument.round_price(
            new_stop, side=bracket.signal.side.opposite
        )
        if self.market_kind.has_position_stop:
            self.gateway.set_position_stop(
                symbol=self.instrument.symbol, stop_loss=rounded
            )
        else:
            if bracket.stop_order_id:
                self.gateway.cancel_order(
                    symbol=self.instrument.symbol, order_id=bracket.stop_order_id
                )
            self._place_stop(bracket, rounded)
        bracket.stop_price = rounded

    def expire_entry(self, bracket: Bracket) -> None:
        """Nicht gefuellte Einstiegsorder stornieren.

        Ein Setup, das nach mehreren Kerzen nicht erreicht wurde, ist meist
        nicht mehr gueltig - der Markt ist ohne uns weitergelaufen.
        """
        if bracket.entry_order is not None:
            self.gateway.cancel_order(
                symbol=self.instrument.symbol, order_id=bracket.entry_order.order_id
            )
        bracket.state = BracketState.EXPIRED
        log.info("router.einstieg_abgelaufen", preis=str(bracket.signal.entry_price))

    # -- Notausstieg ---------------------------------------------------------
    def emergency_close(self, bracket: Bracket, *, reason: str) -> None:
        """Alles glattstellen. Market-Order, Taker-Gebuehr, sofort.

        Hier zaehlt Ausfuehrungssicherheit mehr als die Gebuehr. Wird vom
        Not-Aus im Dashboard und vom Kill-Switch aufgerufen - und wenn das
        Setzen des Stops fehlgeschlagen ist.
        """
        log.critical("router.notausstieg", grund=reason, menge=str(bracket.remaining_qty))

        try:
            self.gateway.cancel_all(self.instrument.symbol)
        except Exception as exc:
            log.error("router.stornieren_fehlgeschlagen", fehler=str(exc))

        if bracket.remaining_qty > 0:
            self.gateway.place_market(
                symbol=self.instrument.symbol,
                side=bracket.signal.side.opposite,
                qty=bracket.remaining_qty,
                reduce_only=True,
            )
        bracket.state = BracketState.CLOSED
        bracket.remaining_qty = Decimal(0)

    def close_all(self, reason: str) -> None:
        """Alle Orders stornieren - ohne bekannte Position.

        Fuer den Fall, dass der Prozess ohne Kenntnis offener Brackets startet
        und aufraeumen soll.
        """
        cancelled = self.gateway.cancel_all(self.instrument.symbol)
        log.warning("router.alles_storniert", grund=reason, orders=cancelled)
