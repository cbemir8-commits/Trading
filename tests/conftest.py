"""Gemeinsame Test-Fixtures.

Wichtig: Die gesamte Testsuite laeuft **ohne Netzwerk**. Bybit blockt die Region
dieses Entwicklungscontainers, und selbst ohne diese Einschraenkung waeren
netzabhaengige Tests fuer ein Handelssystem die falsche Wahl - sie waeren
langsam, unzuverlaessig und nicht reproduzierbar. Tests, die zwingend eine echte
Verbindung brauchen, tragen die Markierung ``@pytest.mark.network`` und werden
standardmaessig uebersprungen.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.config import BybitEnvironment, BybitSettings, MarginMode, RiskSettings
from core.models import Candle, Instrument, Signal

from .factories import make_candles, make_instrument, make_signal


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Netzabhaengige Tests ueberspringen, sofern nicht ausdruecklich angefordert.

    Aktivieren mit: ``RUN_NETWORK_TESTS=1 pytest``
    """
    import os

    if os.environ.get("RUN_NETWORK_TESTS") == "1":
        return
    skip = pytest.mark.skip(
        reason="Braucht echte Bybit-Verbindung. Mit RUN_NETWORK_TESTS=1 aktivieren."
    )
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def btcusdt() -> Instrument:
    """BTCUSDT-Perpetual mit den echten Bybit-Spezifikationen.

    0,001 BTC Mindestmenge entspricht bei 100.000 USD Kurs bereits 100 USD
    Nominalwert - genau der Grund, warum ein 500-EUR-Konto Hebel braucht.
    """
    return make_instrument()


@pytest.fixture
def risk() -> RiskSettings:
    """Die Standardgrenzen aus dem Plan: 0,75 % Risiko, 3x Hebel, 15 % Kill-Switch."""
    return RiskSettings(
        risk_per_trade_pct=Decimal("0.75"),
        max_leverage=Decimal("3"),
        margin_mode=MarginMode.ISOLATED,
        min_liquidation_buffer=Decimal("4.0"),
        min_stop_distance_pct=Decimal("0.15"),
        max_stop_distance_pct=Decimal("3.0"),
        daily_loss_limit_pct=Decimal("3.0"),
        weekly_loss_limit_pct=Decimal("7.0"),
        max_drawdown_pct=Decimal("15.0"),
    )


@pytest.fixture
def equity_500() -> Decimal:
    """Das reale Startkapital aus dem Plan."""
    return Decimal("500")


@pytest.fixture
def bybit_settings() -> BybitSettings:
    """Demo-Umgebung mit Platzhalter-Credentials fuer Signaturtests."""
    from pydantic import SecretStr

    return BybitSettings(
        environment=BybitEnvironment.DEMO,
        api_key=SecretStr("testkey"),
        api_secret=SecretStr("testsecret"),
        symbol="BTCUSDT",
        category="linear",
        recv_window_ms=5000,
        max_retries=0,  # Tests sollen sofort scheitern, nicht warten
    )


@pytest.fixture
def long_signal() -> Signal:
    return make_signal()


@pytest.fixture
def candles_15m() -> list[Candle]:
    return make_candles(count=200)
