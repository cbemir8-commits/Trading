"""Tests des Kostenmodells.

Bei einem 500-EUR-Konto entscheiden die Kosten ueber Erfolg oder Misserfolg -
eine Strategie mit 3 % Bruttorendite im Monat ist mit Taker-Orders ein
Verlustgeschaeft und mit Maker-Orders profitabel. Entsprechend genau wird hier
geprueft.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backtest.costs import (
    DEFAULT_MAKER_FEE,
    DEFAULT_TAKER_FEE,
    CostModel,
    FundingSchedule,
    funding_times_between,
)
from core.models import LiquidityRole, Side


class TestFees:
    def test_maker_is_cheaper_than_taker(self) -> None:
        costs = CostModel()
        notional = Decimal("900")

        maker = costs.fee(notional, LiquidityRole.MAKER)
        taker = costs.fee(notional, LiquidityRole.TAKER)

        assert maker == pytest.approx(Decimal("0.18"))  # 900 x 0,0002
        assert taker == pytest.approx(Decimal("0.495"))  # 900 x 0,00055
        assert taker > maker * Decimal("2.7")

    def test_monthly_fee_burden_at_small_account(self) -> None:
        """Die Rechnung, die ueber das Order-Design entscheidet.

        30 Trades im Monat zu je 900 USD Nominalwert, ein Ein- und ein Ausstieg:

            Nur Maker: 60 x 900 x 0,0002  = 10,80 USD =  2,2 % von 500
            Nur Taker: 60 x 900 x 0,00055 = 29,70 USD =  5,9 % von 500

        Der Unterschied von 3,7 Prozentpunkten pro Monat ist groesser als das,
        was viele Strategien ueberhaupt erwirtschaften. Deshalb laufen Einstiege
        und Take-Profits als PostOnly-Limit.
        """
        costs = CostModel()
        notional = Decimal("900")
        sides_per_month = 60

        maker_total = costs.fee(notional, LiquidityRole.MAKER) * sides_per_month
        taker_total = costs.fee(notional, LiquidityRole.TAKER) * sides_per_month

        assert maker_total == pytest.approx(Decimal("10.80"))
        assert taker_total == pytest.approx(Decimal("29.70"))
        assert (taker_total - maker_total) / Decimal("500") * 100 > Decimal("3.7")

    def test_fee_is_always_positive(self) -> None:
        """Auch bei negativem Nominalwert (Short) sind Gebuehren Kosten."""
        costs = CostModel()
        assert costs.fee(Decimal("-900"), LiquidityRole.TAKER) > 0

    def test_defaults_match_bybit_vip0(self) -> None:
        assert DEFAULT_MAKER_FEE == Decimal("0.0002")
        assert DEFAULT_TAKER_FEE == Decimal("0.00055")


class TestSlippage:
    def test_slippage_always_works_against_us(self) -> None:
        costs = CostModel(slippage_bps=Decimal("10"))
        price = Decimal("100000")

        buy = costs.apply_slippage(price, Side.BUY)
        sell = costs.apply_slippage(price, Side.SELL)

        assert buy > price, "Ein Kauf wird teurer"
        assert sell < price, "Ein Verkauf wird billiger"
        assert buy == pytest.approx(Decimal("100100"))  # 10 bps
        assert sell == pytest.approx(Decimal("99900"))

    def test_stops_get_worse_slippage(self) -> None:
        """Ein Stop wird ausgeloest, wenn der Markt schnell gegen uns laeuft -
        genau dann sind die Spreads breiter.

        Ein Backtest, der Stops zum exakten Stop-Preis fuellt, rechnet sich
        systematisch zu gut.
        """
        costs = CostModel(slippage_bps=Decimal("1"), stop_slippage_bps=Decimal("5"))
        price = Decimal("100000")

        normal = costs.apply_slippage(price, Side.SELL, is_stop=False)
        stopped = costs.apply_slippage(price, Side.SELL, is_stop=True)

        assert stopped < normal

    def test_scaled_model_doubles_everything(self) -> None:
        """Fuer den Kosten-Stresstest: Bei doppelten Kosten muss die Strategie
        noch profitabel sein, sonst war der Vorteil nur ein zu optimistisches
        Kostenmodell."""
        doubled = CostModel().scaled(Decimal(2))

        assert doubled.maker_fee_rate == DEFAULT_MAKER_FEE * 2
        assert doubled.taker_fee_rate == DEFAULT_TAKER_FEE * 2
        assert doubled.slippage_bps == Decimal("2.0")
        assert doubled.stop_slippage_bps == Decimal("10.0")


class TestFundingTimes:
    def test_three_times_per_day(self) -> None:
        """Bybit verrechnet um 00:00, 08:00 und 16:00 UTC."""
        moments = funding_times_between(
            datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
        )
        assert [m.hour for m in moments] == [8, 16, 0]

    def test_interval_is_half_open(self) -> None:
        """``(start, end]`` - eine exakt zum Funding-Zeitpunkt eroeffnete
        Position zahlt nicht sofort.

        Bybit belastet nur Positionen, die zum Zeitpunkt bereits bestanden.
        """
        exact = datetime(2026, 1, 1, 8, tzinfo=UTC)

        opened_at_funding = funding_times_between(exact, datetime(2026, 1, 1, 12, tzinfo=UTC))
        assert exact not in opened_at_funding

        held_through = funding_times_between(datetime(2026, 1, 1, 4, tzinfo=UTC), exact)
        assert exact in held_through

    def test_empty_when_end_before_start(self) -> None:
        assert funding_times_between(
            datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)
        ) == []

    def test_short_intraday_span_has_none(self) -> None:
        assert funding_times_between(
            datetime(2026, 1, 1, 9, tzinfo=UTC), datetime(2026, 1, 1, 15, tzinfo=UTC)
        ) == []


class TestFundingPayments:
    def test_longs_pay_when_rate_is_positive(self) -> None:
        """Der Normalfall im Bullenmarkt - und der Grund, warum eine Strategie,
        die Funding ignoriert, ihre Rendite systematisch ueberschaetzt."""
        schedule = FundingSchedule(default_rate=Decimal("0.0001"))

        cost = schedule.payments_between(
            datetime(2026, 1, 1, 4, tzinfo=UTC),
            datetime(2026, 1, 1, 20, tzinfo=UTC),
            position_value=Decimal("900"),
            side=Side.BUY,
        )
        # Zwei Zeitpunkte (08:00, 16:00) x 900 x 0,0001
        assert cost == pytest.approx(Decimal("0.18"))
        assert cost > 0, "Positives Ergebnis = Kosten fuer uns"

    def test_shorts_receive_when_rate_is_positive(self) -> None:
        schedule = FundingSchedule(default_rate=Decimal("0.0001"))
        cost = schedule.payments_between(
            datetime(2026, 1, 1, 4, tzinfo=UTC),
            datetime(2026, 1, 1, 20, tzinfo=UTC),
            position_value=Decimal("900"),
            side=Side.SELL,
        )
        assert cost == pytest.approx(Decimal("-0.18"))

    def test_historical_rates_override_default(self) -> None:
        moment = datetime(2026, 1, 1, 8, tzinfo=UTC)
        schedule = FundingSchedule(
            rates={moment: Decimal("0.0075")},  # Extremwert, kommt real vor
            default_rate=Decimal("0.0001"),
        )
        cost = schedule.payments_between(
            datetime(2026, 1, 1, 4, tzinfo=UTC),
            datetime(2026, 1, 1, 10, tzinfo=UTC),
            position_value=Decimal("900"),
            side=Side.BUY,
        )
        assert cost == pytest.approx(Decimal("6.75"))

    def test_multi_day_hold_accumulates(self) -> None:
        """Ueber eine Woche summiert sich Funding spuerbar.

        900 USD Position, 21 Zeitpunkte a 0,01 % = 1,89 USD. Bei 3,75 USD
        Risiko je Trade ist das die Haelfte eines geplanten Verlusts.
        """
        schedule = FundingSchedule(default_rate=Decimal("0.0001"))
        cost = schedule.payments_between(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 8, tzinfo=UTC),
            position_value=Decimal("900"),
            side=Side.BUY,
        )
        assert cost == pytest.approx(Decimal("1.89"))
