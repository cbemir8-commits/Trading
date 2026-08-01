"""Tests fuer den Bybit-HTTP-Client und den Adapter.

Alles laeuft gegen gemockte HTTP-Antworten. Zwei Dinge werden hier besonders
scharf geprueft, weil sie in der Praxis die haeufigsten stillen Fehler sind:

* **Reihenfolge der Kerzen.** Bybit liefert neueste zuerst. Wer das uebersieht,
  baut sich einen Backtest, der rueckwaerts durch die Zeit laeuft.
* **Geoblocking.** CloudFront antwortet mit kaputtem JSON, was sonst als
  unverstaendlicher Parse-Fehler endet statt als klare Diagnose.
"""

from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal

import httpx
import pytest
import respx

from core.config import BybitEnvironment, BybitSettings
from core.models import Interval, Side
from data.bybit.adapter import BybitAccount, BybitMarketData
from data.bybit.client import BybitHTTPClient, encode_query, sign_request
from data.bybit.errors import (
    BybitAPIError,
    BybitAuthError,
    BybitGeoBlockedError,
    BybitRateLimitError,
    BybitTransportError,
)
from tests.factories import make_candles, make_kline_response

#: Kontoabfragen gehen an den Demo-Host ...
BASE = "https://api-demo.bybit.com"
#: ... Marktdaten dagegen immer ans Mainnet. Siehe BybitEnvironment.public_rest_url:
#: Der Demo-Host ignoriert bei Kerzen den start-Parameter und liefert nur die
#: juengsten rund 1000 Stueck.
PUBLIC = "https://api.bybit.com"


# ---------------------------------------------------------------------------
#  Signierung
# ---------------------------------------------------------------------------
class TestSigning:
    def test_signature_matches_bybit_spec(self) -> None:
        """Signatur = HMAC-SHA256(secret, timestamp + key + recv_window + payload)."""
        signature = sign_request(
            api_secret="mysecret",
            api_key="mykey",
            timestamp_ms=1700000000000,
            recv_window_ms=5000,
            payload="category=linear&symbol=BTCUSDT",
        )
        expected = hmac.new(
            b"mysecret",
            b"1700000000000mykey5000category=linear&symbol=BTCUSDT",
            hashlib.sha256,
        ).hexdigest()
        assert signature == expected

    def test_query_encoding_drops_none_and_lowercases_bools(self) -> None:
        encoded = encode_query(
            {"category": "linear", "symbol": "BTCUSDT", "cursor": None, "flag": True}
        )
        assert encoded == "category=linear&symbol=BTCUSDT&flag=true"

    def test_query_order_is_preserved(self) -> None:
        """Signatur und tatsaechliche Anfrage muessen denselben String nutzen -
        deshalb darf die Reihenfolge nicht umsortiert werden."""
        assert encode_query({"b": 1, "a": 2}) == "b=1&a=2"

    def test_signed_call_without_credentials_fails_clearly(self) -> None:
        settings = BybitSettings(environment=BybitEnvironment.DEMO, max_retries=0)
        with BybitHTTPClient(settings) as client, pytest.raises(BybitAuthError, match="BYBIT__API_KEY"):
            client.get_private("/v5/account/wallet-balance")

    @respx.mock
    def test_signed_call_sends_all_auth_headers(self, bybit_settings: BybitSettings) -> None:
        route = respx.get(f"{BASE}/v5/position/list").mock(
            return_value=httpx.Response(200, json={"retCode": 0, "retMsg": "OK", "result": {"list": []}})
        )
        with BybitHTTPClient(bybit_settings) as client:
            client.get_private("/v5/position/list", {"category": "linear"})

        headers = route.calls[0].request.headers
        assert headers["X-BAPI-API-KEY"] == "testkey"
        assert headers["X-BAPI-RECV-WINDOW"] == "5000"
        assert len(headers["X-BAPI-SIGN"]) == 64  # SHA256 als Hex
        assert headers["X-BAPI-TIMESTAMP"].isdigit()


# ---------------------------------------------------------------------------
#  Fehlerklassifikation
# ---------------------------------------------------------------------------
class TestErrorHandling:
    @respx.mock
    def test_geoblock_is_detected_and_explained(self, bybit_settings: BybitSettings) -> None:
        """CloudFront-Blockade darf nicht als Parse-Fehler enden.

        Genau dieser Fall tritt im Entwicklungscontainer auf - die Meldung muss
        sofort sagen, was zu tun ist.
        """
        respx.get(f"{PUBLIC}/v5/market/time").mock(
            return_value=httpx.Response(
                403,
                text="{\n    error:The Amazon CloudFront distribution is configured "
                "to block access from your country\n}",
            )
        )
        with BybitHTTPClient(bybit_settings) as client, pytest.raises(BybitGeoBlockedError, match="Region"):
            client.get_public("/v5/market/time")

    @respx.mock
    def test_geoblock_is_not_retried(self, bybit_settings: BybitSettings) -> None:
        """Geoblocking ist dauerhaft - Wiederholen waere reine Zeitverschwendung."""
        settings = bybit_settings.model_copy(update={"max_retries": 3})
        route = respx.get(f"{PUBLIC}/v5/market/time").mock(
            return_value=httpx.Response(403, text="blocked: not available in your country")
        )
        with BybitHTTPClient(settings) as client, pytest.raises(BybitGeoBlockedError):
            client.get_public("/v5/market/time")
        assert route.call_count == 1

    @respx.mock
    def test_business_error_raises_api_error(self, bybit_settings: BybitSettings) -> None:
        respx.get(f"{PUBLIC}/v5/market/kline").mock(
            return_value=httpx.Response(
                200, json={"retCode": 10001, "retMsg": "params error: symbol invalid", "result": {}}
            )
        )
        with BybitHTTPClient(bybit_settings) as client, pytest.raises(BybitAPIError) as exc_info:
            client.get_public("/v5/market/kline", {"symbol": "NOPE"})
        assert exc_info.value.ret_code == 10001
        assert not exc_info.value.retryable

    @respx.mock
    def test_auth_ret_code_is_not_retryable(self, bybit_settings: BybitSettings) -> None:
        """Falsche Signatur wird nicht wiederholt - sie waere beim naechsten Mal
        genauso falsch."""
        settings = bybit_settings.model_copy(update={"max_retries": 3})
        route = respx.get(f"{BASE}/v5/position/list").mock(
            return_value=httpx.Response(
                200, json={"retCode": 10004, "retMsg": "error sign!", "result": {}}
            )
        )
        with BybitHTTPClient(settings) as client, pytest.raises(BybitAuthError):
            client.get_private("/v5/position/list")
        assert route.call_count == 1

    @respx.mock
    def test_rate_limit_is_retried_then_succeeds(self, bybit_settings: BybitSettings) -> None:
        settings = bybit_settings.model_copy(update={"max_retries": 2})
        respx.get(f"{PUBLIC}/v5/market/time").mock(
            side_effect=[
                httpx.Response(429, text="rate limit"),
                httpx.Response(
                    200,
                    json={
                        "retCode": 0,
                        "retMsg": "OK",
                        "result": {"timeNano": "1767225600000000000"},
                    },
                ),
            ]
        )
        with BybitHTTPClient(settings) as client:
            result = client.get_public("/v5/market/time")
        assert result["retCode"] == 0

    @respx.mock
    def test_rate_limit_exhausts_retries_and_raises(self, bybit_settings: BybitSettings) -> None:
        settings = bybit_settings.model_copy(update={"max_retries": 1})
        respx.get(f"{PUBLIC}/v5/market/time").mock(
            return_value=httpx.Response(429, text="rate limit")
        )
        with BybitHTTPClient(settings) as client, pytest.raises(BybitRateLimitError):
            client.get_public("/v5/market/time")

    @respx.mock
    def test_timeout_becomes_transport_error(self, bybit_settings: BybitSettings) -> None:
        respx.get(f"{PUBLIC}/v5/market/time").mock(side_effect=httpx.ReadTimeout("zu langsam"))
        with BybitHTTPClient(bybit_settings) as client, pytest.raises(BybitTransportError, match="Timeout"):
            client.get_public("/v5/market/time")


# ---------------------------------------------------------------------------
#  Marktdaten
# ---------------------------------------------------------------------------
class TestMarketData:
    @respx.mock
    def test_klines_are_returned_in_chronological_order(
        self, bybit_settings: BybitSettings
    ) -> None:
        """Der wichtigste Test dieser Datei.

        Bybit liefert absteigend. Wird das nicht korrigiert, laeuft der Backtest
        rueckwaerts durch die Zeit - ein Fehler, der monatelang unentdeckt
        bleiben kann, weil die Ergebnisse plausibel aussehen.
        """
        expected = make_candles(count=5)
        respx.get(f"{PUBLIC}/v5/market/kline").mock(
            return_value=httpx.Response(200, json=make_kline_response(expected))
        )
        market = BybitMarketData(bybit_settings)
        candles = market.get_klines("BTCUSDT", Interval.M15)

        assert [c.open_time for c in candles] == [c.open_time for c in expected]
        times = [c.open_time for c in candles]
        assert times == sorted(times), "Kerzen muessen aufsteigend sortiert sein"

    @respx.mock
    def test_kline_values_are_parsed_as_decimal(self, bybit_settings: BybitSettings) -> None:
        """Bybit liefert Strings. Float waere hier ein Rundungsrisiko."""
        respx.get(f"{PUBLIC}/v5/market/kline").mock(
            return_value=httpx.Response(200, json=make_kline_response(make_candles(count=1)))
        )
        market = BybitMarketData(bybit_settings)
        candle = market.get_klines("BTCUSDT", Interval.M15)[0]
        assert isinstance(candle.close, Decimal)
        assert candle.open_time.tzinfo is not None, "Zeitstempel muessen UTC-bewusst sein"

    @respx.mock
    def test_kline_limit_is_capped_at_api_maximum(self, bybit_settings: BybitSettings) -> None:
        route = respx.get(f"{PUBLIC}/v5/market/kline").mock(
            return_value=httpx.Response(200, json=make_kline_response([]))
        )
        market = BybitMarketData(bybit_settings)
        market.get_klines("BTCUSDT", Interval.M15, limit=99_999)
        assert "limit=1000" in str(route.calls[0].request.url)

    @respx.mock
    def test_instrument_parses_lot_and_price_filters(self, bybit_settings: BybitSettings) -> None:
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
                                    "maxOrderQty": "100.000",
                                    "minNotionalValue": "5",
                                },
                                "priceFilter": {"tickSize": "0.10"},
                                "leverageFilter": {"maxLeverage": "100.00"},
                            }
                        ]
                    },
                },
            )
        )
        market = BybitMarketData(bybit_settings)
        instrument = market.get_instrument("BTCUSDT")

        assert instrument.qty_step == Decimal("0.001")
        assert instrument.tick_size == Decimal("0.10")
        assert instrument.min_order_qty == Decimal("0.001")
        assert instrument.launch_time is not None
        assert instrument.launch_time.year == 2020  # BTCUSDT-Perp Start: 30.03.2020

    @respx.mock
    def test_unknown_symbol_raises(self, bybit_settings: BybitSettings) -> None:
        respx.get(f"{PUBLIC}/v5/market/instruments-info").mock(
            return_value=httpx.Response(
                200, json={"retCode": 0, "retMsg": "OK", "result": {"list": []}}
            )
        )
        market = BybitMarketData(bybit_settings)
        with pytest.raises(ValueError, match="nicht gefunden"):
            market.get_instrument("FAKECOIN")


# ---------------------------------------------------------------------------
#  Konto
# ---------------------------------------------------------------------------
class TestAccount:
    @respx.mock
    def test_closed_positions_are_filtered_out(self, bybit_settings: BybitSettings) -> None:
        """Bybit liefert auch geschlossene Positionen mit size=0 zurueck.

        Wer die nicht herausfiltert, glaubt eine Position zu halten, die es
        nicht gibt - und blockiert damit neue Signale.
        """
        respx.get(f"{BASE}/v5/position/list").mock(
            return_value=httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "retMsg": "OK",
                    "result": {
                        "list": [
                            {"symbol": "BTCUSDT", "side": "", "size": "0", "avgPrice": "0"},
                            {
                                "symbol": "BTCUSDT",
                                "side": "Buy",
                                "size": "0.005",
                                "avgPrice": "100000",
                                "markPrice": "100500",
                                "leverage": "3",
                                "unrealisedPnl": "2.5",
                                "liqPrice": "67000",
                                "positionValue": "500",
                            },
                        ]
                    },
                },
            )
        )
        account = BybitAccount(bybit_settings)
        positions = account.get_positions("BTCUSDT")

        assert len(positions) == 1
        assert positions[0].size == Decimal("0.005")
        assert positions[0].side is Side.BUY

    @respx.mock
    def test_liquidation_distance_is_computed(self, bybit_settings: BybitSettings) -> None:
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
                                "size": "0.005",
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
        account = BybitAccount(bybit_settings)
        position = account.get_positions("BTCUSDT")[0]
        distance = position.distance_to_liquidation_pct()
        assert distance is not None
        assert Decimal("32") < distance < Decimal("34")  # 3x -> rund 33 %

    @respx.mock
    def test_empty_wallet_returns_zero_balance(self, bybit_settings: BybitSettings) -> None:
        """Ein frischer Demo-Account ohne USDT darf nicht in einen Fehler laufen."""
        respx.get(f"{BASE}/v5/account/wallet-balance").mock(
            return_value=httpx.Response(
                200,
                json={"retCode": 0, "retMsg": "OK", "result": {"list": [{"coin": []}]}},
            )
        )
        account = BybitAccount(bybit_settings)
        balance = account.get_wallet_balance("USDT")
        assert balance.equity == Decimal(0)


# ---------------------------------------------------------------------------
#  Umgebungen
# ---------------------------------------------------------------------------
class TestEnvironments:
    def test_urls_per_environment(self) -> None:
        assert BybitEnvironment.DEMO.rest_url == "https://api-demo.bybit.com"
        assert BybitEnvironment.TESTNET.rest_url == "https://api-testnet.bybit.com"
        assert BybitEnvironment.MAINNET.rest_url == "https://api.bybit.com"

    def test_only_mainnet_is_real_money(self) -> None:
        assert BybitEnvironment.MAINNET.is_real_money
        assert not BybitEnvironment.DEMO.is_real_money
        assert not BybitEnvironment.TESTNET.is_real_money

    def test_demo_uses_mainnet_public_stream(self) -> None:
        """Demo-Trading hat keinen eigenen oeffentlichen Stream - es nutzt die
        echten Mainnet-Marktdaten. Genau das wollen wir: echte Preise, Spielgeld."""
        assert BybitEnvironment.DEMO.public_ws_url("linear") == (
            "wss://stream.bybit.com/v5/public/linear"
        )
        assert BybitEnvironment.DEMO.private_ws_url == "wss://stream-demo.bybit.com/v5/private"


class TestPublicHostRouting:
    """Marktdaten und Kontodaten gehen an verschiedene Hosts.

    Der Demo-Host liefert zwar Kerzen, ignoriert dabei aber den
    ``start``-Parameter und gibt nur die juengsten rund 1000 Stueck zurueck.
    Ein Backfill laeuft dann scheinbar sauber durch - eine Anfrage, 999
    Kerzen, "fertig" - und hinterlaesst zehn Tage Historie statt sechs Jahren.
    Nichts daran sieht nach einem Fehler aus; der Walk-Forward waere trotzdem
    wertlos.
    """

    def test_demo_reads_market_data_from_mainnet(self) -> None:
        assert BybitEnvironment.DEMO.public_rest_url == "https://api.bybit.com"
        assert BybitEnvironment.DEMO.rest_url == "https://api-demo.bybit.com"

    def test_testnet_stays_on_testnet(self) -> None:
        """Dort gibt es echte Historie, und die Konten sind dieselben."""
        assert BybitEnvironment.TESTNET.public_rest_url == BybitEnvironment.TESTNET.rest_url

    def test_mainnet_uses_one_host_for_everything(self) -> None:
        assert BybitEnvironment.MAINNET.public_rest_url == BybitEnvironment.MAINNET.rest_url

    @respx.mock
    def test_klines_really_go_to_mainnet_in_demo(self, bybit_settings: BybitSettings) -> None:
        """Der Test, der den Fehler gefunden haette.

        Er prueft nicht die Konfiguration, sondern wohin die Anfrage
        tatsaechlich geht - und dass sie eben *nicht* beim Demo-Host landet.
        """
        demo_route = respx.get(f"{BASE}/v5/market/kline").mock(
            return_value=httpx.Response(200, json=make_kline_response([]))
        )
        mainnet_route = respx.get(f"{PUBLIC}/v5/market/kline").mock(
            return_value=httpx.Response(
                200, json=make_kline_response(make_candles(count=3))
            )
        )

        BybitMarketData(bybit_settings).get_klines("BTCUSDT", Interval.M15)

        assert mainnet_route.call_count == 1
        assert demo_route.call_count == 0

    @respx.mock
    def test_account_calls_still_go_to_demo(self, bybit_settings: BybitSettings) -> None:
        """Die Gegenprobe: Das Konto liegt beim Demo-Host, und nur dort."""
        route = respx.get(f"{BASE}/v5/position/list").mock(
            return_value=httpx.Response(
                200, json={"retCode": 0, "retMsg": "OK", "result": {"list": []}}
            )
        )

        BybitAccount(bybit_settings).get_positions("BTCUSDT")

        assert route.call_count == 1
