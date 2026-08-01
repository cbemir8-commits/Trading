"""Tests fuer den Health-Check.

Wichtig, weil dieses Skript die erste Beruehrung mit einem neuen Server ist.
Wenn es luegt oder abstuerzt, startet jemand ein Handelssystem auf einem
kaputten Host. Deshalb wird hier auch der Erfolgspfad geprueft - der laesst
sich im geoblockten Entwicklungscontainer sonst nie ausfuehren.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
import respx

from core.config import BybitEnvironment, BybitSettings, Settings
from core.models import Interval
from data.bybit.adapter import BybitMarketData
from scripts.healthcheck import (
    Level,
    Report,
    check_credentials,
    check_history,
    check_instrument,
    check_key_permissions,
    check_leverage_preview,
    check_reachability,
)
from tests.factories import make_candles, make_kline_response

#: Kontoabfragen gehen an den Demo-Host ...
BASE = "https://api-demo.bybit.com"
#: ... Marktdaten dagegen immer ans Mainnet. Siehe BybitEnvironment.public_rest_url:
#: Der Demo-Host ignoriert bei Kerzen den start-Parameter und liefert nur die
#: juengsten rund 1000 Stueck.
PUBLIC = "https://api.bybit.com"


@pytest.fixture
def settings(bybit_settings: BybitSettings) -> Settings:
    return Settings(bybit=bybit_settings)


def _mock_server_time(offset_s: float = 0.0) -> None:
    now_ns = int((datetime.now(UTC).timestamp() + offset_s) * 1_000_000_000)
    respx.get(f"{PUBLIC}/v5/market/time").mock(
        return_value=httpx.Response(
            200, json={"retCode": 0, "retMsg": "OK", "result": {"timeNano": str(now_ns)}}
        )
    )


def _mock_instrument_and_ticker(price: str = "100000") -> None:
    respx.get(f"{PUBLIC}/v5/market/instruments-info").mock(
        return_value=httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "baseCoin": "BTC",
                            "quoteCoin": "USDT",
                            "launchTime": "1585526400000",
                            "lotSizeFilter": {
                                "qtyStep": "0.001",
                                "minOrderQty": "0.001",
                                "maxOrderQty": "100",
                                "minNotionalValue": "5",
                            },
                            "priceFilter": {"tickSize": "0.1"},
                            "leverageFilter": {"maxLeverage": "100"},
                        }
                    ]
                },
            },
        )
    )
    respx.get(f"{PUBLIC}/v5/market/tickers").mock(
        return_value=httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "lastPrice": price,
                            "markPrice": price,
                            "indexPrice": price,
                            "bid1Price": str(Decimal(price) - Decimal("5")),
                            "ask1Price": str(Decimal(price) + Decimal("5")),
                            "fundingRate": "0.0001",
                            "turnover24h": "5000000000",
                        }
                    ]
                },
            },
        )
    )


class TestReachability:
    @respx.mock
    def test_healthy_connection_passes(self, settings: Settings) -> None:
        _mock_server_time()
        report = Report()
        assert check_reachability(report, BybitMarketData(settings.bybit)) is True
        assert report.checks[0].level is Level.OK

    @respx.mock
    def test_clock_drift_fails_with_ntp_hint(self, settings: Settings) -> None:
        """Zu grosse Uhrzeit-Abweichung laesst jede signierte Anfrage scheitern.

        Der Fehler von Bybit lautet dann nur 'invalid timestamp' - ohne diesen
        Check sucht man an der falschen Stelle.
        """
        _mock_server_time(offset_s=30)
        report = Report()
        assert check_reachability(report, BybitMarketData(settings.bybit)) is False
        check = report.checks[0]
        assert check.level is Level.FAIL
        # Der Hinweis richtet sich nach dem System, auf dem der Check laeuft -
        # gemeinsam ist allen, dass sie die Folge benennen.
        assert "Signierte Anfragen" in check.hint

    @respx.mock
    def test_geoblock_gives_actionable_message(self, settings: Settings) -> None:
        respx.get(f"{PUBLIC}/v5/market/time").mock(
            return_value=httpx.Response(
                403, text="{error:The Amazon CloudFront distribution is configured "
                "to block access from your country}"
            )
        )
        report = Report()
        assert check_reachability(report, BybitMarketData(settings.bybit)) is False
        check = report.checks[0]
        assert check.level is Level.FAIL
        assert "Region" in check.hint
        assert report.exit_code == 2


class TestInstrumentAndHistory:
    @respx.mock
    def test_instrument_reports_min_notional_at_current_price(self, settings: Settings) -> None:
        """Die relevante Zahl fuer ein kleines Konto: was kostet die kleinste Order."""
        _mock_instrument_and_ticker(price="100000")
        report = Report()
        price = check_instrument(report, BybitMarketData(settings.bybit), settings)

        assert price == Decimal("100000")
        detail = report.checks[0].detail
        assert "0.001 BTC" in detail
        assert "100 USDT Nominalwert" in detail

    @respx.mock
    def test_short_history_warns(self, settings: Settings) -> None:
        recent = make_candles(count=3, start=datetime(2025, 6, 1, tzinfo=UTC), interval=Interval.D1)
        respx.get(f"{PUBLIC}/v5/market/kline").mock(
            return_value=httpx.Response(200, json=make_kline_response(recent))
        )
        report = Report()
        check_history(report, BybitMarketData(settings.bybit), settings)
        assert report.checks[0].level is Level.WARN
        assert "Walk-Forward" in report.checks[0].hint

    @respx.mock
    def test_long_history_passes(self, settings: Settings) -> None:
        old = make_candles(count=3, start=datetime(2020, 3, 30, tzinfo=UTC), interval=Interval.D1)
        respx.get(f"{PUBLIC}/v5/market/kline").mock(
            return_value=httpx.Response(200, json=make_kline_response(old))
        )
        report = Report()
        check_history(report, BybitMarketData(settings.bybit), settings)
        assert report.checks[0].level is Level.OK
        assert "2020-03-30" in report.checks[0].detail


class TestKeyPermissions:
    """Der sicherheitskritischste Check des Skripts."""

    @respx.mock
    def test_withdrawal_permission_is_a_hard_failure(self, settings: Settings) -> None:
        """Auszahlungsrecht auf einem Handels-Key = potenzieller Totalverlust."""
        respx.get(f"{BASE}/v5/user/query-api").mock(
            return_value=httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "retMsg": "OK",
                    "result": {
                        "isMaster": True,
                        "ips": ["1.2.3.4"],
                        "permissions": {
                            "ContractTrade": ["Order", "Position"],
                            "Wallet": ["AccountTransfer", "Withdraw"],
                        },
                    },
                },
            )
        )
        report = Report()
        check_key_permissions(report, settings)
        check = report.checks[0]
        assert check.level is Level.FAIL
        assert "AUSZAHLUNGSRECHT" in check.detail
        assert report.exit_code == 2

    @respx.mock
    def test_missing_ip_whitelist_warns(self, settings: Settings) -> None:
        respx.get(f"{BASE}/v5/user/query-api").mock(
            return_value=httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "retMsg": "OK",
                    "result": {
                        "isMaster": True,
                        "ips": [],
                        "permissions": {"ContractTrade": ["Order", "Position"]},
                    },
                },
            )
        )
        report = Report()
        check_key_permissions(report, settings)
        assert report.checks[0].level is Level.WARN
        assert "IP-Whitelist" in report.checks[0].hint

    @respx.mock
    def test_correctly_scoped_key_passes(self, settings: Settings) -> None:
        respx.get(f"{BASE}/v5/user/query-api").mock(
            return_value=httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "retMsg": "OK",
                    "result": {
                        "isMaster": True,
                        "ips": ["203.0.113.7"],
                        "permissions": {
                            "ContractTrade": ["Order", "Position"],
                            "Wallet": [],
                        },
                    },
                },
            )
        )
        report = Report()
        check_key_permissions(report, settings)
        assert report.checks[0].level is Level.OK
        assert "Kein Auszahlungsrecht" in report.checks[0].detail

    def test_skipped_without_credentials(self) -> None:
        settings = Settings(bybit=BybitSettings(environment=BybitEnvironment.DEMO))
        report = Report()
        check_key_permissions(report, settings)
        assert report.checks[0].level is Level.SKIP


class TestCredentials:
    @respx.mock
    def test_open_position_warns_before_start(self, settings: Settings) -> None:
        """Eine offene Fremdposition muss auffallen, bevor das System startet."""
        respx.get(f"{BASE}/v5/account/wallet-balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "retMsg": "OK",
                    "result": {
                        "list": [
                            {
                                "coin": [
                                    {
                                        "coin": "USDT",
                                        "equity": "500",
                                        "walletBalance": "500",
                                        "availableToWithdraw": "500",
                                        "unrealisedPnl": "0",
                                    }
                                ]
                            }
                        ]
                    },
                },
            )
        )
        respx.get(f"{BASE}/v5/position/list").mock(
            return_value=httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "retMsg": "OK",
                    "result": {
                        "list": [
                            {
                                "symbol": "BTCUSDT",
                                "side": "Buy",
                                "size": "0.01",
                                "avgPrice": "100000",
                                "markPrice": "100000",
                                "leverage": "3",
                                "unrealisedPnl": "0",
                                "liqPrice": "67000",
                            }
                        ]
                    },
                },
            )
        )
        report = Report()
        check_credentials(report, settings)
        levels = [c.level for c in report.checks]
        assert Level.OK in levels  # Anmeldung erfolgreich
        assert Level.WARN in levels  # aber offene Position
        assert any("bereinigen" in c.hint for c in report.checks)


class TestLeveragePreview:
    def test_preview_shows_leverage_equals_risk_over_stop(self, settings: Settings) -> None:
        """Die Vorschau muss die Kernidentitaet korrekt abbilden.

        Bei 0,75 % Risiko: Stop 0,5 % -> 1,50x; Stop 1,0 % -> 0,75x; Stop 0,2 % -> 3,75x
        (Letzteres liegt ueber dem 3x-Deckel und muss entsprechend markiert sein).
        """
        report = Report()
        check_leverage_preview(report, settings, Decimal("100000"))

        detail = report.checks[0].detail
        assert "1.50x" in detail  # Stop 0,5 %
        assert "0.75x" in detail  # Stop 1,0 %
        assert "3.75x" in detail  # Stop 0,2 %
        assert "3.75 EUR je Trade" in detail
        # Der 0,2-%-Stop ergibt 3,75x und muss als ueber dem Deckel markiert sein.
        assert "ueber Deckel 3x" in detail

    def test_preview_flags_untradable_stops(self, settings: Settings) -> None:
        """Sehr weite Stops fallen bei 500 EUR unter die Mindestmenge - das muss
        sichtbar sein, sonst wundert man sich ueber ausbleibende Trades."""
        report = Report()
        check_leverage_preview(report, settings, Decimal("100000"))
        detail = report.checks[0].detail
        assert "unter Mindestmenge" in detail or "ueber Deckel" in detail

    def test_preview_skipped_without_price(self, settings: Settings) -> None:
        report = Report()
        check_leverage_preview(report, settings, None)
        assert report.checks[0].level is Level.SKIP


class TestReportExitCodes:
    def test_exit_codes(self) -> None:
        clean = Report()
        clean.add("a", Level.OK, "")
        assert clean.exit_code == 0

        warned = Report()
        warned.add("a", Level.OK, "")
        warned.add("b", Level.WARN, "")
        assert warned.exit_code == 1

        failed = Report()
        failed.add("a", Level.WARN, "")
        failed.add("b", Level.FAIL, "")
        assert failed.exit_code == 2


class TestClockFixHint:
    """Ein Linux-Befehl auf einem Windows-Rechner ist schlimmer als kein
    Hinweis: Er sieht nach einer Loesung aus, fuehrt aber nur zu einer zweiten
    Fehlermeldung, die mit der ersten nichts zu tun hat."""

    def test_windows_gets_the_windows_way(self, monkeypatch) -> None:
        import platform

        from scripts.healthcheck import _clock_fix_hint

        monkeypatch.setattr(platform, "system", lambda: "Windows")
        hint = _clock_fix_hint()

        assert "Datum und Uhrzeit" in hint
        assert "timedatectl" not in hint

    def test_mac_gets_the_mac_way(self, monkeypatch) -> None:
        import platform

        from scripts.healthcheck import _clock_fix_hint

        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        hint = _clock_fix_hint()

        assert "Systemeinstellungen" in hint
        assert "timedatectl" not in hint

    def test_linux_gets_the_linux_way(self, monkeypatch) -> None:
        import platform

        from scripts.healthcheck import _clock_fix_hint

        monkeypatch.setattr(platform, "system", lambda: "Linux")

        assert "timedatectl" in _clock_fix_hint()
