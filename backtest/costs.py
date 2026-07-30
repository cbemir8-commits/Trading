"""Kostenmodell: Gebuehren, Slippage, Funding.

Bei einem 500-EUR-Konto entscheiden die Kosten ueber Erfolg oder Misserfolg.
Die Groessenordnung: 30 Trades im Monat zu je 900 USD Nominalwert kosten

* mit Taker-Orders (0,055 % je Seite):  ~30 USD/Monat = 5,5 % des Kontos
* mit Maker-Orders (0,020 % je Seite):  ~11 USD/Monat = 2,0 % des Kontos

Eine Strategie mit 3 % Bruttorendite im Monat ist im ersten Fall ein
Verlustgeschaeft und im zweiten profitabel. Deshalb ist das Kostenmodell hier
kein Detail, sondern eine Kernkomponente - und deshalb laufen Einstiege und
Take-Profits grundsaetzlich als PostOnly-Limit.

Die Voreinstellungen entsprechen Bybit VIP0 fuer USDT-Perpetuals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from core.models import LiquidityRole, Side

#: Bybit VIP0, USDT-Perpetuals.
DEFAULT_MAKER_FEE = Decimal("0.0002")  # 0,020 %
DEFAULT_TAKER_FEE = Decimal("0.00055")  # 0,055 %

#: Funding wird alle acht Stunden verrechnet.
FUNDING_HOURS = (0, 8, 16)


@dataclass(frozen=True, slots=True)
class CostModel:
    """Gebuehren- und Slippage-Annahmen.

    ``slippage_bps`` gilt nur fuer Taker-Orders. Ein Maker-Limit fuellt per
    Definition zum Limitpreis oder gar nicht - dort gibt es keine Slippage,
    dafuer das Risiko, gar nicht gefuellt zu werden.

    ``stop_slippage_bps`` ist bewusst hoeher: Ein Stop wird ausgeloest, wenn der
    Markt sich schnell gegen die Position bewegt - genau dann sind die Spreads
    breiter und die Ausfuehrung schlechter. Ein Backtest, der Stops zum exakten
    Stop-Preis fuellt, rechnet sich systematisch zu gut.
    """

    maker_fee_rate: Decimal = DEFAULT_MAKER_FEE
    taker_fee_rate: Decimal = DEFAULT_TAKER_FEE
    slippage_bps: Decimal = Decimal("1.0")
    stop_slippage_bps: Decimal = Decimal("5.0")

    def fee(self, notional: Decimal, role: LiquidityRole) -> Decimal:
        """Gebuehr auf den Nominalwert. Immer positiv (Kosten)."""
        rate = self.maker_fee_rate if role is LiquidityRole.MAKER else self.taker_fee_rate
        return abs(notional) * rate

    def apply_slippage(
        self, price: Decimal, side: Side, *, is_stop: bool = False
    ) -> Decimal:
        """Verschiebt den Ausfuehrungspreis gegen uns.

        Ein Kauf wird teurer, ein Verkauf billiger - Slippage geht per Definition
        immer zu unseren Lasten.
        """
        bps = self.stop_slippage_bps if is_stop else self.slippage_bps
        factor = bps / Decimal(10_000)
        return price * (Decimal(1) + factor) if side is Side.BUY else price * (Decimal(1) - factor)

    def scaled(self, factor: Decimal) -> CostModel:
        """Alle Kosten skalieren - fuer den Kosten-Stresstest.

        Eine Strategie muss bei doppelten Gebuehren und doppelter Slippage noch
        profitabel sein. Ueberlebt sie das nicht, war der vermeintliche Vorteil
        nur ein zu optimistisches Kostenmodell.
        """
        return CostModel(
            maker_fee_rate=self.maker_fee_rate * factor,
            taker_fee_rate=self.taker_fee_rate * factor,
            slippage_bps=self.slippage_bps * factor,
            stop_slippage_bps=self.stop_slippage_bps * factor,
        )


@dataclass(slots=True)
class FundingSchedule:
    """Funding-Zahlungen fuer Perpetual-Kontrakte.

    Alle acht Stunden (00:00, 08:00, 16:00 UTC) zahlt eine Seite an die andere.
    Bei positiver Rate zahlen Longs an Shorts. Ueber eine mehrtaegige Position
    summiert sich das spuerbar - eine Strategie, die Funding ignoriert, ueber-
    schaetzt ihre Rendite systematisch, und zwar besonders in Bullenmaerkten,
    wo die Rate meist positiv ist und Longs zahlen.

    Ohne historische Raten wird ``default_rate`` verwendet. 0,01 % je Periode
    entspricht dem Bybit-Basiswert - das sind rund 11 % pro Jahr fuer eine
    dauerhaft gehaltene Long-Position.
    """

    rates: dict[datetime, Decimal] = field(default_factory=dict)
    default_rate: Decimal = Decimal("0.0001")

    def rate_at(self, moment: datetime) -> Decimal:
        return self.rates.get(moment, self.default_rate)

    def payments_between(
        self, start: datetime, end: datetime, *, position_value: Decimal, side: Side
    ) -> Decimal:
        """Summe der Funding-Zahlungen im Zeitraum ``(start, end]``.

        Positives Ergebnis = Kosten fuer uns. Bei positiver Rate zahlt die
        Long-Seite, bei negativer die Short-Seite.
        """
        total = Decimal(0)
        for moment in funding_times_between(start, end):
            rate = self.rate_at(moment)
            payment = position_value * rate
            total += payment if side is Side.BUY else -payment
        return total


def funding_times_between(start: datetime, end: datetime) -> list[datetime]:
    """Alle Funding-Zeitpunkte im halboffenen Intervall ``(start, end]``.

    Halboffen, damit eine Position, die exakt zum Funding-Zeitpunkt eroeffnet
    wird, nicht sofort zahlt - Bybit belastet nur Positionen, die zum Zeitpunkt
    bereits bestanden.
    """
    if end <= start:
        return []

    moments: list[datetime] = []
    day = start.astimezone(UTC).date()
    last_day = end.astimezone(UTC).date()

    while day <= last_day:
        for hour in FUNDING_HOURS:
            moment = datetime.combine(day, time(hour), tzinfo=UTC)
            if start < moment <= end:
                moments.append(moment)
        day += timedelta(days=1)

    return moments
