"""Tests fuer Positionsgroesse, Hebel und Liquidationsschutz.

Das ist der sicherheitskritischste reine Rechenteil des Systems: ein Fehler hier
verletzt still das Risikolimit, bis das Konto leer ist. Entsprechend
kleinteilig wird geprueft.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.config import RiskSettings
from core.models import Instrument, Side, TakeProfitLeg
from execution.sizing import (
    RejectReason,
    SizedPosition,
    SizingRejected,
    leverage_for_stop,
    size_position,
    split_take_profits,
)
from tests.factories import make_signal


# ---------------------------------------------------------------------------
#  Der Kern: Risiko bestimmt die Groesse, Hebel ist das Ergebnis
# ---------------------------------------------------------------------------
class TestRiskDrivesSize:
    def test_risk_amount_matches_target_within_rounding(
        self, btcusdt: Instrument, risk: RiskSettings, equity_500: Decimal
    ) -> None:
        """Das riskierte Geld muss dem Ziel entsprechen - nur nach unten abweichen."""
        signal = make_signal(stop_pct="0.6")
        result = size_position(signal, equity=equity_500, instrument=btcusdt, risk=risk)

        assert isinstance(result, SizedPosition)
        target = equity_500 * risk.risk_per_trade_pct / Decimal(100)  # 3.75 EUR

        # Nie mehr riskieren als geplant.
        assert result.risk_amount <= target
        # Durch das Abrunden auf 0,001 BTC gehen maximal 0,001 x Stop-Distanz verloren.
        max_rounding_loss = btcusdt.qty_step * signal.stop_distance
        assert result.risk_amount > target - max_rounding_loss

    @pytest.mark.parametrize(
        ("stop_pct", "expected_leverage_range"),
        [
            ("1.0", (Decimal("0.5"), Decimal("0.8"))),
            ("0.6", (Decimal("1.0"), Decimal("1.3"))),
            ("0.3", (Decimal("2.2"), Decimal("2.6"))),
        ],
    )
    def test_tighter_stop_means_more_leverage(
        self,
        btcusdt: Instrument,
        risk: RiskSettings,
        equity_500: Decimal,
        stop_pct: str,
        expected_leverage_range: tuple[Decimal, Decimal],
    ) -> None:
        """Der Hebel folgt aus der Stop-Distanz - das riskierte Geld bleibt gleich.

        Das ist die zentrale Aussage des Moduls: enge Stops erzwingen Hebel,
        ohne dass dabei mehr Geld auf dem Spiel steht.
        """
        signal = make_signal(stop_pct=stop_pct)
        result = size_position(signal, equity=equity_500, instrument=btcusdt, risk=risk)

        assert isinstance(result, SizedPosition)
        low, high = expected_leverage_range
        assert low <= result.leverage <= high, (
            f"Stop {stop_pct} % -> Hebel {result.leverage:.2f}x, erwartet {low}..{high}"
        )
        # Das riskierte Geld liegt unabhaengig vom Hebel beim Ziel.
        assert result.risk_pct_of_equity <= risk.risk_per_trade_pct

    def test_leverage_never_exceeds_cap(
        self, btcusdt: Instrument, risk: RiskSettings, equity_500: Decimal
    ) -> None:
        """Auch bei sehr engem Stop darf der Hebeldeckel nicht ueberschritten werden."""
        signal = make_signal(stop_pct="0.16")  # knapp ueber dem Minimum
        result = size_position(signal, equity=equity_500, instrument=btcusdt, risk=risk)

        if isinstance(result, SizedPosition):
            assert result.leverage <= risk.max_leverage

    def test_leverage_cap_reduces_risk_not_increases_it(
        self, btcusdt: Instrument, equity_500: Decimal
    ) -> None:
        """Greift der Deckel, wird die Position kleiner - nie groesser."""
        risk = RiskSettings(
            risk_per_trade_pct=Decimal("2.0"),
            max_leverage=Decimal("2"),
            min_liquidation_buffer=Decimal("2.0"),
        )
        signal = make_signal(stop_pct="0.4")
        result = size_position(signal, equity=equity_500, instrument=btcusdt, risk=risk)

        assert isinstance(result, SizedPosition)
        assert result.was_capped_by_leverage
        assert result.leverage <= Decimal("2")
        # Gedeckelt heisst: weniger Risiko als das Ziel, nie mehr.
        assert result.risk_pct_of_equity < risk.risk_per_trade_pct


# ---------------------------------------------------------------------------
#  Liquidationsschutz
# ---------------------------------------------------------------------------
class TestLiquidationGuard:
    def test_rejects_when_liquidation_within_buffer(
        self, btcusdt: Instrument, equity_500: Decimal
    ) -> None:
        """Hoher Hebel bei weitem Stop muss abgelehnt werden.

        Genau diese Kombination toetet Konten: Der Stop wuerde erst *nach* der
        Liquidation greifen, ist also wertlos.
        """
        risk = RiskSettings(
            risk_per_trade_pct=Decimal("5.0"),
            max_leverage=Decimal("25"),
            min_liquidation_buffer=Decimal("4.0"),
            max_stop_distance_pct=Decimal("3.0"),
        )
        signal = make_signal(stop_pct="2.0")
        result = size_position(signal, equity=equity_500, instrument=btcusdt, risk=risk)

        assert isinstance(result, SizingRejected)
        assert result.reason is RejectReason.LIQUIDATION_TOO_CLOSE

    def test_accepts_when_liquidation_far_enough(
        self, btcusdt: Instrument, risk: RiskSettings, equity_500: Decimal
    ) -> None:
        """Bei 3x Deckel liegt die Liquidation ~33 % entfernt - weit genug."""
        signal = make_signal(stop_pct="0.8")
        result = size_position(signal, equity=equity_500, instrument=btcusdt, risk=risk)

        assert isinstance(result, SizedPosition)
        assert result.liquidation_distance_pct > result.stop_distance_pct * risk.min_liquidation_buffer

    def test_long_liquidation_is_below_entry(self, btcusdt: Instrument) -> None:
        liq = btcusdt.estimate_liquidation_price(
            entry=Decimal("100000"), side=Side.BUY, leverage=Decimal("3")
        )
        assert liq < Decimal("100000")
        # 3x -> grob 33 % Puffer (abzueglich Maintenance Margin).
        assert Decimal("66000") < liq < Decimal("68000")

    def test_short_liquidation_is_above_entry(self, btcusdt: Instrument) -> None:
        liq = btcusdt.estimate_liquidation_price(
            entry=Decimal("100000"), side=Side.SELL, leverage=Decimal("3")
        )
        assert liq > Decimal("100000")
        assert Decimal("132000") < liq < Decimal("134000")

    def test_high_leverage_liquidation_is_dangerously_close(self, btcusdt: Instrument) -> None:
        """Belegt, warum der Deckel existiert: bei 20x liegt die Liquidation im Rauschen."""
        liq = btcusdt.estimate_liquidation_price(
            entry=Decimal("100000"), side=Side.BUY, leverage=Decimal("20")
        )
        distance_pct = (Decimal("100000") - liq) / Decimal("100000") * 100
        assert distance_pct < Decimal("5")  # ein normaler BTC-Docht

    def test_liquidation_uses_exchange_setting_not_derived_ratio(
        self, btcusdt: Instrument, equity_500: Decimal
    ) -> None:
        """Regressionstest fuer einen Bug mit Geldrelevanz.

        Bei Isolated Margin hinterlegt Bybit ``Nominalwert / eingestellter Hebel``
        als Margin. Der Rest des Kontos schuetzt die Position nicht. Eine
        Position mit nur 1,2x abgeleitetem Hebel kann also trotzdem 4 % vor der
        Liquidation stehen, wenn am Symbol 25x eingestellt ist.

        Frueher rechnete der Sizer gegen den abgeleiteten Hebel - dabei kam ein
        viel zu optimistischer Abstand heraus und die Pruefung griff nie.
        """
        risky_setting = RiskSettings(
            risk_per_trade_pct=Decimal("0.75"),
            max_leverage=Decimal("25"),  # am Symbol eingestellt
            min_liquidation_buffer=Decimal("4.0"),
            max_stop_distance_pct=Decimal("3.0"),
        )
        safe_setting = risky_setting.model_copy(update={"max_leverage": Decimal("3")})
        signal = make_signal(stop_pct="1.5")

        risky = size_position(
            signal, equity=equity_500, instrument=btcusdt, risk=risky_setting
        )
        safe = size_position(signal, equity=equity_500, instrument=btcusdt, risk=safe_setting)

        # Gleiches Signal, gleiche Positionsgroesse - nur die Hebeleinstellung
        # unterscheidet sich. Trotzdem ist die eine Variante toedlich.
        assert isinstance(risky, SizingRejected)
        assert risky.reason is RejectReason.LIQUIDATION_TOO_CLOSE
        assert isinstance(safe, SizedPosition)
        assert safe.exchange_leverage == Decimal("3")
        # Der abgeleitete Hebel ist in beiden Faellen identisch und harmlos.
        assert safe.leverage < Decimal("1")

    def test_derived_leverage_equals_risk_over_stop(
        self, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        """Die Identitaet ``Hebel = Risiko% / Stop%`` - unabhaengig vom Kapital.

        Nuetzlich fuers Verstaendnis: Mehr Kapital erhoeht den Hebel nicht. Es
        entscheidet nur darueber, ob die Menge ueber die Mindestgroesse kommt.
        """
        stop_pct = Decimal("0.5")
        expected = risk.risk_per_trade_pct / stop_pct  # 0.75 / 0.5 = 1.5x

        for equity in ["2000", "10000", "50000"]:
            result = size_position(
                make_signal(stop_pct=str(stop_pct)),
                equity=Decimal(equity),
                instrument=btcusdt,
                risk=risk,
            )
            assert isinstance(result, SizedPosition)
            # Abweichung nur durch das Abrunden auf qty_step, bei groesserem
            # Kapital entsprechend kleiner.
            assert abs(result.leverage - expected) < Decimal("0.05")


# ---------------------------------------------------------------------------
#  Ablehnungen
# ---------------------------------------------------------------------------
class TestRejections:
    def test_rejects_stop_too_tight(
        self, btcusdt: Instrument, risk: RiskSettings, equity_500: Decimal
    ) -> None:
        signal = make_signal(stop_pct="0.05")
        result = size_position(signal, equity=equity_500, instrument=btcusdt, risk=risk)
        assert isinstance(result, SizingRejected)
        assert result.reason is RejectReason.STOP_TOO_TIGHT

    def test_rejects_stop_too_wide(
        self, btcusdt: Instrument, risk: RiskSettings, equity_500: Decimal
    ) -> None:
        signal = make_signal(stop_pct="5.0")
        result = size_position(signal, equity=equity_500, instrument=btcusdt, risk=risk)
        assert isinstance(result, SizingRejected)
        assert result.reason is RejectReason.STOP_TOO_WIDE

    def test_rejects_when_account_too_small_for_minimum_qty(
        self, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        """Bei 50 EUR Kapital und weitem Stop reicht es nicht fuer 0,001 BTC.

        Lieber gar nicht handeln als eine Position, die das Risikolimit sprengt.
        """
        signal = make_signal(stop_pct="2.0")
        result = size_position(signal, equity=Decimal("50"), instrument=btcusdt, risk=risk)
        assert isinstance(result, SizingRejected)
        assert result.reason in {
            RejectReason.QTY_BELOW_MINIMUM,
            RejectReason.LEVERAGE_CAP_MAKES_QTY_INVALID,
        }

    def test_rejects_zero_equity(
        self, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        signal = make_signal()
        result = size_position(signal, equity=Decimal("0"), instrument=btcusdt, risk=risk)
        assert isinstance(result, SizingRejected)
        assert result.reason is RejectReason.NO_EQUITY

    def test_never_returns_qty_below_exchange_minimum(
        self, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        """Ueber viele Kapitalgroessen hinweg: entweder gueltig oder abgelehnt.

        Nie eine Menge, die Bybit zurueckweisen wuerde.
        """
        for equity in ["50", "100", "250", "500", "1000", "5000", "25000"]:
            for stop_pct in ["0.2", "0.5", "1.0", "2.0"]:
                signal = make_signal(stop_pct=stop_pct)
                result = size_position(
                    signal, equity=Decimal(equity), instrument=btcusdt, risk=risk
                )
                if isinstance(result, SizedPosition):
                    assert result.qty >= btcusdt.min_order_qty
                    assert result.qty % btcusdt.qty_step == 0
                    assert result.leverage <= risk.max_leverage


# ---------------------------------------------------------------------------
#  Take-Profit-Aufteilung
# ---------------------------------------------------------------------------
class TestTakeProfitSplit:
    def test_legs_sum_to_full_position(self, btcusdt: Instrument) -> None:
        """Kein Rest darf uebrigbleiben - sonst haengt eine Teilposition offen."""
        qty = Decimal("0.009")
        legs = [
            TakeProfitLeg(price=Decimal("101000"), portion=Decimal("0.5")),
            TakeProfitLeg(price=Decimal("102000"), portion=Decimal("0.3")),
            TakeProfitLeg(price=Decimal("103000"), portion=Decimal("0.2")),
        ]
        result = split_take_profits(qty=qty, take_profits=legs, instrument=btcusdt)
        assert sum(q for _, q in result) == qty

    def test_remainder_goes_to_furthest_target(self, btcusdt: Instrument) -> None:
        """0,009 BTC auf 50/30/20 ergibt 4,5/2,7/1,8 Schritte.

        Abgerundet: 0,004 / 0,002 / 0,001 = 0,007. Die fehlenden 0,002 gehen
        bewusst auf das *weiteste* Ziel - das laesst Gewinnern mehr Raum.
        """
        qty = Decimal("0.009")
        legs = [
            TakeProfitLeg(price=Decimal("101000"), portion=Decimal("0.5")),
            TakeProfitLeg(price=Decimal("102000"), portion=Decimal("0.3")),
            TakeProfitLeg(price=Decimal("103000"), portion=Decimal("0.2")),
        ]
        result = split_take_profits(qty=qty, take_profits=legs, instrument=btcusdt)
        assert result[0] == (Decimal("101000"), Decimal("0.004"))
        assert result[1] == (Decimal("102000"), Decimal("0.002"))
        assert result[2][1] == Decimal("0.003")  # 0.001 + 0.002 Rest

    def test_tiny_position_collapses_to_single_target(self, btcusdt: Instrument) -> None:
        """Bei 0,001 BTC gibt es nichts zu staffeln - alles auf ein Ziel."""
        legs = [
            TakeProfitLeg(price=Decimal("101000"), portion=Decimal("0.5")),
            TakeProfitLeg(price=Decimal("102000"), portion=Decimal("0.5")),
        ]
        result = split_take_profits(qty=Decimal("0.001"), take_profits=legs, instrument=btcusdt)
        assert len(result) == 1
        assert result[0][1] == Decimal("0.001")

    def test_every_leg_is_a_valid_step_multiple(self, btcusdt: Instrument) -> None:
        legs = [
            TakeProfitLeg(price=Decimal("101000"), portion=Decimal("0.5")),
            TakeProfitLeg(price=Decimal("102000"), portion=Decimal("0.3")),
            TakeProfitLeg(price=Decimal("103000"), portion=Decimal("0.2")),
        ]
        for raw in ["0.001", "0.003", "0.007", "0.009", "0.015", "0.123"]:
            qty = Decimal(raw)
            result = split_take_profits(qty=qty, take_profits=legs, instrument=btcusdt)
            assert sum(q for _, q in result) == qty
            for _, leg_qty in result:
                assert leg_qty % btcusdt.qty_step == 0
                assert leg_qty > 0


# ---------------------------------------------------------------------------
#  Short-Seite
# ---------------------------------------------------------------------------
class TestShortSide:
    def test_short_sizing_mirrors_long(
        self, btcusdt: Instrument, risk: RiskSettings, equity_500: Decimal
    ) -> None:
        long_result = size_position(
            make_signal(side=Side.BUY, stop_pct="0.6"),
            equity=equity_500,
            instrument=btcusdt,
            risk=risk,
        )
        short_result = size_position(
            make_signal(side=Side.SELL, stop_pct="0.6"),
            equity=equity_500,
            instrument=btcusdt,
            risk=risk,
        )
        assert isinstance(long_result, SizedPosition)
        assert isinstance(short_result, SizedPosition)
        assert long_result.qty == short_result.qty
        assert long_result.leverage == short_result.leverage


# ---------------------------------------------------------------------------
#  Hilfsfunktion fuers Dashboard
# ---------------------------------------------------------------------------
def test_leverage_for_stop_matches_sizer(
    btcusdt: Instrument, risk: RiskSettings, equity_500: Decimal
) -> None:
    """Die Vorschau-Funktion darf nicht von der echten Rechnung abweichen."""
    stop_pct = Decimal("0.6")
    preview = leverage_for_stop(
        equity=equity_500,
        entry_price=Decimal("100000"),
        stop_distance_pct=stop_pct,
        risk_per_trade_pct=risk.risk_per_trade_pct,
    )
    actual = size_position(
        make_signal(stop_pct="0.6"), equity=equity_500, instrument=btcusdt, risk=risk
    )
    assert isinstance(actual, SizedPosition)
    # Die Vorschau rundet nicht auf qty_step, liegt also minimal hoeher.
    assert abs(preview - actual.leverage) < Decimal("0.2")
