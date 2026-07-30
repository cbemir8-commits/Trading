"""Tests fuer Speicher, Backfill und Qualitaetspruefung.

Schwerpunkt liegt auf den Fehlern, die im Backtest still zu falschen Ergebnissen
fuehren statt zu einer Fehlermeldung: unfertige Kerzen, Luecken, doppelte oder
rueckwaerts sortierte Zeitstempel.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from core.models import Candle, Interval
from data.backfill import Backfiller, RateLimiter, drop_unfinished, estimate_requests
from data.quality import Severity, check_candles
from data.store import CandleStore, candles_to_frame, empty_frame, frame_to_candles

from tests.factories import make_candles
from tests.fakes import FakeMarketData, make_series_with_gap


@pytest.fixture
def store(tmp_path: Path) -> CandleStore:
    return CandleStore(tmp_path / "data_store")


# ---------------------------------------------------------------------------
#  Speicher
# ---------------------------------------------------------------------------
class TestCandleStore:
    def test_write_read_roundtrip(self, store: CandleStore) -> None:
        candles = make_candles(count=50)
        store.write("BTCUSDT", Interval.M15, candles)
        frame = store.read("BTCUSDT", Interval.M15)

        assert len(frame) == 50
        assert frame["open_time"].is_monotonic_increasing
        assert frame["close"].iloc[-1] == pytest.approx(float(candles[-1].close))

    def test_write_is_idempotent(self, store: CandleStore) -> None:
        """Denselben Block zweimal schreiben darf keine Duplikate erzeugen.

        Wichtig fuer den Backfill: bei einem Neustart ueberlappen die Seiten
        typischerweise um eine Kerze.
        """
        candles = make_candles(count=50)
        first = store.write("BTCUSDT", Interval.M15, candles)
        second = store.write("BTCUSDT", Interval.M15, candles)

        assert first == 50
        assert second == 0, "Wiederholtes Schreiben darf nichts hinzufuegen"
        assert len(store.read("BTCUSDT", Interval.M15)) == 50

    def test_overlapping_write_only_adds_new(self, store: CandleStore) -> None:
        base = make_candles(count=100)
        store.write("BTCUSDT", Interval.M15, base[:60])
        added = store.write("BTCUSDT", Interval.M15, base[50:])

        assert added == 40  # 10 ueberlappende Kerzen zaehlen nicht
        assert len(store.read("BTCUSDT", Interval.M15)) == 100

    def test_later_write_wins_on_duplicate_timestamp(self, store: CandleStore) -> None:
        """Eine korrigierte Kerze muss die alte ersetzen.

        Relevant, wenn eine zunaechst unfertig gespeicherte Kerze spaeter
        vollstaendig nachgeliefert wird.
        """
        original = make_candles(count=1)[0]
        corrected = Candle(
            open_time=original.open_time,
            open=original.open,
            high=Decimal("999999"),
            low=original.low,
            close=original.close,
            volume=original.volume,
            turnover=original.turnover,
        )
        store.write("BTCUSDT", Interval.M15, [original])
        store.write("BTCUSDT", Interval.M15, [corrected])

        frame = store.read("BTCUSDT", Interval.M15)
        assert len(frame) == 1
        assert frame["high"].iloc[0] == pytest.approx(999999.0)

    def test_partitions_by_month(self, store: CandleStore) -> None:
        """Monatspartitionierung macht den Backfill resumierbar."""
        candles = make_candles(
            count=200, start=datetime(2026, 1, 30, tzinfo=UTC), interval=Interval.H4
        )
        store.write("BTCUSDT", Interval.H4, candles)

        names = {p.stem for p in store.partitions("BTCUSDT", Interval.H4)}
        assert "2026-01" in names
        assert "2026-02" in names

    def test_range_read_is_half_open(self, store: CandleStore) -> None:
        """``start`` inklusiv, ``end`` exklusiv - damit sich Fenster nahtlos
        aneinanderfuegen, ohne die Randkerze doppelt zu zaehlen."""
        candles = make_candles(count=100)
        store.write("BTCUSDT", Interval.M15, candles)

        cut = candles[50].open_time
        left = store.read("BTCUSDT", Interval.M15, end=cut)
        right = store.read("BTCUSDT", Interval.M15, start=cut)

        assert len(left) == 50
        assert len(right) == 50
        assert len(left) + len(right) == 100

    def test_read_only_touches_relevant_partitions(self, store: CandleStore) -> None:
        """Bereichslesen darf nicht alle Monatsdateien oeffnen."""
        candles = make_candles(
            count=3000, start=datetime(2025, 1, 1, tzinfo=UTC), interval=Interval.H4
        )
        store.write("BTCUSDT", Interval.H4, candles)
        assert len(store.partitions("BTCUSDT", Interval.H4)) > 6

        selected = store._relevant_partitions(
            "BTCUSDT",
            Interval.H4,
            datetime(2025, 3, 1, tzinfo=UTC),
            datetime(2025, 5, 1, tzinfo=UTC),
        )
        assert {p.stem for p in selected} == {"2025-03", "2025-04"}

    def test_empty_store_returns_typed_empty_frame(self, store: CandleStore) -> None:
        """Ein leerer Frame muss dieselben Spalten haben wie ein gefuellter -
        sonst kracht es erst beim Zusammenfuehren."""
        frame = store.read("BTCUSDT", Interval.M15)
        assert frame.empty
        assert list(frame.columns) == list(empty_frame().columns)

    def test_coverage(self, store: CandleStore) -> None:
        candles = make_candles(count=100)
        store.write("BTCUSDT", Interval.M15, candles)

        coverage = store.coverage("BTCUSDT", Interval.M15)
        assert coverage.rows == 100
        assert coverage.start == candles[0].open_time
        assert coverage.end == candles[-1].open_time
        assert not coverage.is_empty

    def test_coverage_of_unknown_series_is_empty(self, store: CandleStore) -> None:
        assert store.coverage("ETHUSDT", Interval.M15).is_empty

    def test_series_listing(self, store: CandleStore) -> None:
        store.write("BTCUSDT", Interval.M15, make_candles(count=5))
        store.write("BTCUSDT", Interval.H1, make_candles(count=5))
        assert set(store.series()) == {("BTCUSDT", Interval.M15), ("BTCUSDT", Interval.H1)}

    def test_frame_candle_roundtrip_preserves_values(self) -> None:
        original = make_candles(count=10)
        restored = frame_to_candles(candles_to_frame(original))

        assert len(restored) == 10
        assert restored[0].open_time == original[0].open_time
        assert restored[0].close == original[0].close


# ---------------------------------------------------------------------------
#  Backfill
# ---------------------------------------------------------------------------
class TestDropUnfinished:
    """Die wichtigste Schutzmassnahme gegen Lookahead."""

    def test_drops_candle_still_forming(self) -> None:
        candles = make_candles(count=10, interval=Interval.M15)
        # "Jetzt" liegt mitten in der letzten Kerze.
        now = candles[-1].open_time + timedelta(minutes=7)
        kept = drop_unfinished(candles, Interval.M15, now=now)

        assert len(kept) == 9
        assert kept[-1].open_time == candles[-2].open_time

    def test_keeps_candle_exactly_closed(self) -> None:
        """Genau am Periodenende ist die Kerze fertig und darf bleiben."""
        candles = make_candles(count=10, interval=Interval.M15)
        now = candles[-1].open_time + timedelta(minutes=15)
        assert len(drop_unfinished(candles, Interval.M15, now=now)) == 10

    def test_drops_all_future_candles(self) -> None:
        candles = make_candles(count=10, interval=Interval.M15)
        now = candles[0].open_time
        assert drop_unfinished(candles, Interval.M15, now=now) == []


class TestBackfiller:
    def test_pages_through_full_history(self, store: CandleStore) -> None:
        candles = make_candles(count=2500, interval=Interval.M15)
        market = FakeMarketData(candles, now=candles[-1].open_time + timedelta(minutes=15))
        backfiller = Backfiller(market, store, rate_limiter=RateLimiter(0), page_size=1000)

        progress = backfiller.run(
            "BTCUSDT",
            Interval.M15,
            start=candles[0].open_time,
            end=candles[-1].open_time + timedelta(minutes=15),
        )

        assert progress.candles_written == 2500
        assert progress.requests == 3  # 1000 + 1000 + 500
        assert len(store.read("BTCUSDT", Interval.M15)) == 2500

    def test_resumes_after_interruption(self, store: CandleStore) -> None:
        """Ein abgebrochener Backfill darf nicht von vorn beginnen."""
        candles = make_candles(count=2500, interval=Interval.M15)
        end = candles[-1].open_time + timedelta(minutes=15)
        market = FakeMarketData(candles, now=end)
        backfiller = Backfiller(market, store, rate_limiter=RateLimiter(0), page_size=1000)

        first = backfiller.run(
            "BTCUSDT", Interval.M15, start=candles[0].open_time, end=end, max_pages=1
        )
        assert first.candles_written == 1000

        market.calls.clear()
        second = backfiller.run("BTCUSDT", Interval.M15, start=candles[0].open_time, end=end)

        assert second.candles_written == 1500, "Nur der Rest darf nachgeladen werden"
        assert market.calls[0]["start"] > candles[999].open_time
        assert len(store.read("BTCUSDT", Interval.M15)) == 2500

    def test_skips_gap_without_stalling(self, store: CandleStore) -> None:
        """Bei einer Luecke liefert Bybit keine Kerzen fuer den Zeitraum.

        Der Cursor muss darueber hinwegspringen. Ohne diese Faehigkeit bliebe
        der Backfill an der ersten Wartungspause der Boerse haengen.
        """
        candles = make_series_with_gap(before=100, gap_candles=50, after=100)
        end = candles[-1].open_time + timedelta(minutes=15)
        market = FakeMarketData(candles, now=end)
        backfiller = Backfiller(market, store, rate_limiter=RateLimiter(0), page_size=60)

        progress = backfiller.run(
            "BTCUSDT", Interval.M15, start=candles[0].open_time, end=end
        )

        assert progress.candles_written == 200
        frame = store.read("BTCUSDT", Interval.M15)
        assert len(frame) == 200

    def test_does_not_store_unfinished_candle(self, store: CandleStore) -> None:
        """Der aktuelle Rand: die letzte Kerze bildet sich noch.

        Landet sie im Speicher, sieht der Backtest ein Hoch/Tief/Schluss, das
        zum Signalzeitpunkt noch gar nicht feststand - Lookahead, der die
        Ergebnisse still schoenrechnet.
        """
        candles = make_candles(count=100, interval=Interval.M15)
        now = candles[-1].open_time + timedelta(minutes=3)  # mitten in der letzten
        market = FakeMarketData(candles, now=now)
        backfiller = Backfiller(
            market, store, rate_limiter=RateLimiter(0), page_size=1000, clock=lambda: now
        )

        backfiller.run("BTCUSDT", Interval.M15, start=candles[0].open_time, end=now)

        frame = store.read("BTCUSDT", Interval.M15)
        assert len(frame) == 99
        assert frame["open_time"].iloc[-1].to_pydatetime() == candles[-2].open_time

    def test_stops_when_cursor_does_not_advance(self, store: CandleStore) -> None:
        """Endlosschleifen-Schutz.

        Liefert die API dieselbe Seite erneut, muss der Backfill abbrechen -
        sonst laeuft er unbemerkt ins Rate-Limit.
        """

        class StuckMarket(FakeMarketData):
            def get_klines(self, symbol, interval, *, start=None, end=None, limit=200):  # type: ignore[no-untyped-def]
                super().get_klines(symbol, interval, start=start, end=end, limit=limit)
                return self.candles[:10]  # immer dieselben

        candles = make_candles(count=100, interval=Interval.M15)
        market = StuckMarket(candles, now=candles[-1].open_time + timedelta(minutes=15))
        backfiller = Backfiller(market, store, rate_limiter=RateLimiter(0), page_size=10)

        progress = backfiller.run(
            "BTCUSDT",
            Interval.M15,
            start=candles[50].open_time,
            end=candles[-1].open_time + timedelta(minutes=15),
        )
        assert progress.requests <= 2, "Muss sofort abbrechen, nicht bis zum Limit laufen"

    def test_empty_response_ends_run(self, store: CandleStore) -> None:
        market = FakeMarketData([], now=datetime(2026, 1, 1, tzinfo=UTC))
        backfiller = Backfiller(market, store, rate_limiter=RateLimiter(0))

        progress = backfiller.run(
            "BTCUSDT",
            Interval.M15,
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert progress.requests == 1
        assert progress.candles_written == 0

    def test_run_many_does_coarse_intervals_first(self, store: CandleStore) -> None:
        """Grobe Intervalle zuerst: sie sind schnell fertig und liefern sofort
        eine brauchbare Datenbasis."""
        candles = make_candles(count=100, interval=Interval.M15)
        end = candles[-1].open_time + timedelta(minutes=15)
        market = FakeMarketData(candles, now=end)
        backfiller = Backfiller(market, store, rate_limiter=RateLimiter(0))

        backfiller.run_many(
            "BTCUSDT",
            [Interval.M15, Interval.H4, Interval.H1],
            start=candles[0].open_time,
            end=end,
        )
        order = [call["interval"] for call in market.calls]
        assert order[0] is Interval.H4
        assert Interval.M15 in order

    def test_estimate_requests(self) -> None:
        """Planungshilfe: 1-Minuten-Daten ab 2020 sind rund 3300 Anfragen."""
        requests = estimate_requests(
            Interval.M1, datetime(2020, 3, 30, tzinfo=UTC), datetime(2026, 7, 30, tzinfo=UTC)
        )
        assert 3000 < requests < 3600


class TestRateLimiter:
    def test_enforces_minimum_interval(self) -> None:
        import time

        limiter = RateLimiter(requests_per_second=50)
        start = time.monotonic()
        for _ in range(5):
            limiter.wait()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.06  # 4 Wartezeiten a 20 ms

    def test_zero_disables_limiting(self) -> None:
        limiter = RateLimiter(requests_per_second=0)
        limiter.wait()
        limiter.wait()  # darf nicht blockieren


# ---------------------------------------------------------------------------
#  Qualitaetspruefung
# ---------------------------------------------------------------------------
class TestQuality:
    def test_clean_series_has_no_findings(self) -> None:
        frame = candles_to_frame(make_candles(count=1000))
        report = check_candles(frame, symbol="BTCUSDT", interval=Interval.M15)

        assert report.worst_severity is Severity.INFO
        assert report.is_usable
        assert report.completeness == 1.0
        assert not report.gaps

    def test_empty_series_is_an_error(self) -> None:
        report = check_candles(empty_frame(), symbol="BTCUSDT", interval=Interval.M15)
        assert report.worst_severity is Severity.ERROR
        assert not report.is_usable

    def test_detects_gap_and_measures_it(self) -> None:
        frame = candles_to_frame(make_series_with_gap(before=500, gap_candles=30, after=500))
        report = check_candles(frame, symbol="BTCUSDT", interval=Interval.M15)

        assert len(report.gaps) == 1
        assert report.gaps[0].missing_candles == 30
        assert report.missing_candles == 30
        assert report.completeness < 1.0

    def test_large_gap_ratio_is_an_error(self) -> None:
        """Fehlen ueber 1 % der Kerzen, ist die Reihe nicht backtestfaehig."""
        frame = candles_to_frame(make_series_with_gap(before=100, gap_candles=200, after=100))
        report = check_candles(frame, symbol="BTCUSDT", interval=Interval.M15)

        assert report.worst_severity is Severity.ERROR
        assert not report.is_usable

    def test_detects_unsorted_series(self) -> None:
        """Der Fall, der einen rueckwaerts laufenden Backtest erzeugt."""
        frame = candles_to_frame(make_candles(count=100)).iloc[::-1].reset_index(drop=True)
        report = check_candles(frame, symbol="BTCUSDT", interval=Interval.M15)

        assert report.unsorted
        assert report.worst_severity is Severity.ERROR
        assert any("rueckwaerts" in f.message for f in report.findings)

    def test_detects_duplicates(self) -> None:
        base = candles_to_frame(make_candles(count=100))
        frame = pd.concat([base, base.iloc[40:45]], ignore_index=True).sort_values("open_time")
        report = check_candles(frame, symbol="BTCUSDT", interval=Interval.M15)

        assert report.duplicates == 5
        assert report.worst_severity is Severity.ERROR

    def test_detects_zero_volume(self) -> None:
        frame = candles_to_frame(make_candles(count=1000))
        frame.loc[100:120, "volume"] = 0.0
        report = check_candles(frame, symbol="BTCUSDT", interval=Interval.M15)

        assert report.zero_volume == 21
        assert any(f.code == "nullvolumen" for f in report.findings)

    def test_detects_extreme_price_move(self) -> None:
        """Ein Flash-Crash muss auffallen, bevor jemand den Kennzahlen glaubt."""
        frame = candles_to_frame(make_candles(count=1000, step=Decimal("1")))
        frame.loc[500, "close"] = frame.loc[500, "close"] * 0.7  # -30 % in einer Kerze
        report = check_candles(frame, symbol="BTCUSDT", interval=Interval.M15)

        assert report.extreme_moves
        assert any(f.code == "preissprunge" for f in report.findings)

    def test_summary_is_readable(self) -> None:
        frame = candles_to_frame(make_candles(count=1000))
        report = check_candles(frame, symbol="BTCUSDT", interval=Interval.M15)
        summary = report.summary()

        assert "BTCUSDT" in summary
        assert "15m" in summary
        assert "Vollstaendigkeit" in summary
