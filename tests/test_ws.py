"""Tests fuer den Live-Kerzen-Stream.

Der Schwerpunkt liegt auf der Unterscheidung bestaetigt/unbestaetigt. Bybit
sendet waehrend einer laufenden Periode mehrfach Aktualisierungen; nur die
Nachricht mit ``confirm: true`` beschreibt die abgeschlossene Kerze. Wer darauf
nicht achtet, handelt auf Hochs, die gleich wieder verschwinden.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from core.config import BybitEnvironment, BybitSettings
from core.models import Interval
from data.bybit.ws import GapFiller, KlineStream, StreamStats, parse_kline_message
from data.store import CandleStore
from tests.factories import make_candles
from tests.fakes import FakeMarketData


def kline_message(
    *,
    interval: str = "15",
    confirm: bool,
    start_ms: int = 1767225600000,
    close: str = "100500",
    symbol: str = "BTCUSDT",
) -> dict:
    """Baut eine Bybit-Kline-Nachricht nach (Zahlen als Strings, wie im Original)."""
    return {
        "topic": f"kline.{interval}.{symbol}",
        "type": "snapshot",
        "ts": start_ms + 900_000,
        "data": [
            {
                "start": start_ms,
                "end": start_ms + 899_999,
                "interval": interval,
                "open": "100000",
                "close": close,
                "high": "100800",
                "low": "99900",
                "volume": "12.5",
                "turnover": "1250000",
                "confirm": confirm,
                "timestamp": start_ms + 900_000,
            }
        ],
    }


class TestParseKlineMessage:
    def test_parses_confirmed_candle(self) -> None:
        parsed = parse_kline_message(kline_message(confirm=True))

        assert len(parsed) == 1
        candle, interval, confirmed = parsed[0]
        assert confirmed is True
        assert interval is Interval.M15
        assert candle.close == Decimal("100500")
        assert candle.open_time == datetime(2026, 1, 1, tzinfo=UTC)

    def test_flags_unconfirmed_candle(self) -> None:
        """Die laufende Kerze - darf angezeigt, aber nicht gespeichert werden."""
        _, _, confirmed = parse_kline_message(kline_message(confirm=False))[0]
        assert confirmed is False

    def test_missing_confirm_defaults_to_unconfirmed(self) -> None:
        """Im Zweifel unbestaetigt. Die sichere Richtung: lieber eine Kerze zu
        wenig speichern als eine, die sich noch aendert."""
        message = kline_message(confirm=True)
        del message["data"][0]["confirm"]
        _, _, confirmed = parse_kline_message(message)[0]
        assert confirmed is False

    def test_ignores_foreign_topics(self) -> None:
        assert parse_kline_message({"topic": "orderbook.1.BTCUSDT", "data": []}) == []
        assert parse_kline_message({"op": "pong", "success": True}) == []

    def test_broken_entry_is_skipped_not_fatal(self) -> None:
        """Eine kaputte Kerze darf den Stream nicht toeten.

        Nachts um drei einen Absturz wegen eines Feldes zu riskieren, das Bybit
        einmalig anders geliefert hat, waere die schlechteste Variante.
        """
        message = kline_message(confirm=True)
        message["data"].append({"start": "kaputt", "interval": "15"})
        parsed = parse_kline_message(message)
        assert len(parsed) == 1  # die gute Kerze kommt trotzdem durch

    def test_ohlc_violation_is_rejected(self) -> None:
        """Ein Schluss ausserhalb von Hoch/Tief ist kaputt - die Kerze faellt raus."""
        message = kline_message(confirm=True)
        message["data"][0]["close"] = "200000"  # weit ueber dem Hoch
        assert parse_kline_message(message) == []


class TestStreamTopics:
    def test_topic_format(self) -> None:
        settings = BybitSettings(environment=BybitEnvironment.DEMO, symbol="BTCUSDT")
        stream = KlineStream(
            settings,
            [Interval.M15, Interval.H1],
            on_candle=_noop,
        )
        assert stream.topics == ["kline.15.BTCUSDT", "kline.60.BTCUSDT"]

    def test_demo_uses_mainnet_market_data(self) -> None:
        """Demo-Trading hat keinen eigenen oeffentlichen Stream - echte Preise,
        Spielgeld. Genau das wollen wir fuer eine aussagekraeftige Testphase."""
        settings = BybitSettings(environment=BybitEnvironment.DEMO)
        stream = KlineStream(settings, [Interval.M15], on_candle=_noop)
        assert stream.url == "wss://stream.bybit.com/v5/public/linear"


class TestStreamStats:
    def test_fresh_stats_are_unhealthy(self) -> None:
        """Ohne empfangene Nachricht gilt der Stream als nicht gesund -
        wichtig, damit das Dashboard einen toten Stream nicht als 'ok' zeigt."""
        assert not StreamStats().is_healthy

    def test_recent_message_is_healthy(self) -> None:
        stats = StreamStats(last_message_at=datetime.now(UTC))
        assert stats.is_healthy

    def test_stale_message_is_unhealthy(self) -> None:
        stats = StreamStats(last_message_at=datetime.now(UTC) - timedelta(minutes=5))
        assert not stats.is_healthy


class TestGapFiller:
    def test_fills_short_outage_completely(self, tmp_path: Path) -> None:
        """Kurze Unterbrechung: die Luecke wird vollstaendig geschlossen."""
        candles = make_candles(count=100, interval=Interval.M15)
        now = candles[-1].open_time + timedelta(minutes=15)
        market = FakeMarketData(candles, now=now)
        store = CandleStore(tmp_path / "store")

        # Die ersten 90 Kerzen sind da, dann waren 2,5 Stunden Verbindung weg.
        store.write("BTCUSDT", Interval.M15, candles[:90])

        filler = GapFiller(market=market, store=store, symbol="BTCUSDT")
        result = filler.fill(Interval.M15, since=candles[90].open_time, now=now)

        assert result.written == 10
        assert not result.truncated
        assert len(store.read("BTCUSDT", Interval.M15)) == 100

    def test_long_outage_is_flagged_as_truncated(self, tmp_path: Path) -> None:
        """Der gefaehrliche Fall.

        Ein 10-Stunden-Ausfall uebersteigt das 6-Stunden-Fenster. Die Luecke
        wird nur teilweise geschlossen - bliebe das unbemerkt, wuerden
        Indikatoren ueber ein Loch hinwegrechnen. Das Ergebnis muss das melden,
        damit der Aufrufer einen richtigen Backfill anstoesst.
        """
        candles = make_candles(count=100, interval=Interval.M15)
        now = candles[-1].open_time + timedelta(minutes=15)
        market = FakeMarketData(candles, now=now)
        store = CandleStore(tmp_path / "store")

        store.write("BTCUSDT", Interval.M15, candles[:60])  # 10 h Luecke

        filler = GapFiller(market=market, store=store, symbol="BTCUSDT")
        result = filler.fill(Interval.M15, since=candles[60].open_time, now=now)

        assert result.truncated, "Zu alte Luecke muss als unvollstaendig gemeldet werden"
        assert result.actual_from > result.requested_from
        assert result.written < 40  # nur das 6-Stunden-Fenster

    def test_does_not_write_unfinished_candle(self, tmp_path: Path) -> None:
        candles = make_candles(count=10, interval=Interval.M15)
        now = candles[-1].open_time + timedelta(minutes=5)  # letzte laeuft noch
        market = FakeMarketData(candles, now=now)
        store = CandleStore(tmp_path / "store")

        filler = GapFiller(market=market, store=store, symbol="BTCUSDT")
        result = filler.fill(Interval.M15, since=candles[0].open_time, now=now)

        assert result.written == 9

    def test_lookback_is_bounded(self, tmp_path: Path) -> None:
        """Nach tagelangem Ausfall soll nicht der Live-Prozess die halbe
        Historie nachladen - dafuer ist der Backfill zustaendig."""
        candles = make_candles(count=500, interval=Interval.M15)
        now = candles[-1].open_time + timedelta(minutes=15)
        market = FakeMarketData(candles, now=now)
        store = CandleStore(tmp_path / "store")

        filler = GapFiller(
            market=market, store=store, symbol="BTCUSDT", max_lookback=timedelta(hours=2)
        )
        result = filler.fill(Interval.M15, since=candles[0].open_time, now=now)

        requested_start = market.calls[0]["start"]
        assert requested_start >= now - timedelta(hours=2, minutes=1)
        assert result.truncated

    def test_nothing_to_fill_returns_zero(self, tmp_path: Path) -> None:
        market = FakeMarketData([], now=datetime(2026, 1, 1, tzinfo=UTC))
        store = CandleStore(tmp_path / "store")
        filler = GapFiller(market=market, store=store, symbol="BTCUSDT")

        result = filler.fill(Interval.M15, since=datetime(2026, 1, 2, tzinfo=UTC))
        assert result.written == 0
        assert not result


async def _noop(candle: object, interval: object) -> None:
    return None
