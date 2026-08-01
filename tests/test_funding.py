"""Tests fuer die zweite Datenquelle.

Zwei Dinge stehen hier im Mittelpunkt, und beide sind Fehler, die still zu
falschen Ergebnissen fuehren statt zu einer Fehlermeldung:

**Lookahead.** Die Rate von 16 Uhr stand um 12 Uhr noch nicht fest. Wer sie der
12-Uhr-Kerze zuordnet, baut eine Strategie, die im Backtest glaenzt und live
nichts kann. Der Unterschied zwischen ``direction="backward"`` und
``direction="nearest"`` ist ein Wort im Quelltext und der ganze Unterschied
zwischen Forschung und Selbstbetrug.

**Abgeschnittene Historie.** Bybit liefert bei weitem Zeitfenster die
*juengsten* Eintraege. Ein Backfill, der das nicht beruecksichtigt, laedt eine
Seite und haelt sich fuer fertig. Genau das ist bei den Kerzen passiert und ist
erst aufgefallen, als der Walk-Forward auf zehn Tagen Historie lief. Die Tests
hier bilden dieses Verhalten nach, statt es freundlich wegzulassen.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.models import FundingRate, Interval
from data.funding import (
    FUNDING_INTERVAL,
    PAGE_SIZE,
    FundingStore,
    attach_funding,
    backfill_funding,
    funding_to_frame,
)
from strategy.indicators import funding_avg, funding_rate, funding_zscore
from tests.factories import make_candles
from tests.fakes import FakeMarketData

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def make_funding(
    *,
    count: int = 100,
    start: datetime | None = None,
    interval: timedelta = FUNDING_INTERVAL,
    rate: str = "0.0001",
    symbol: str = "BTCUSDT",
) -> list[FundingRate]:
    """Eine gleichmaessige Funding-Reihe."""
    t0 = start or T0
    return [
        FundingRate(
            symbol=symbol,
            funding_time=t0 + interval * i,
            funding_rate=Decimal(rate),
        )
        for i in range(count)
    ]


@pytest.fixture
def store(tmp_path: Path) -> FundingStore:
    return FundingStore(tmp_path / "data_store")


# ---------------------------------------------------------------------------
#  Speicher
# ---------------------------------------------------------------------------
class TestFundingStore:
    def test_roundtrip(self, store: FundingStore) -> None:
        store.write("BTCUSDT", make_funding(count=30))
        frame = store.read("BTCUSDT")

        assert len(frame) == 30
        assert frame["time"].is_monotonic_increasing
        assert frame["funding_rate"].iloc[0] == pytest.approx(0.0001)

    def test_leerer_speicher_gibt_leeren_rahmen(self, store: FundingStore) -> None:
        frame = store.read("BTCUSDT")

        assert frame.empty
        # Die Spalten muessen trotzdem stimmen, sonst scheitert attach_funding
        # erst spaeter und an unverstaendlicher Stelle.
        assert list(frame.columns) == ["time", "funding_rate"]

    def test_doppelte_zeitstempel_werden_zusammengefuehrt(self, store: FundingStore) -> None:
        store.write("BTCUSDT", make_funding(count=10))
        neu = store.write("BTCUSDT", make_funding(count=10, rate="0.0005"))

        frame = store.read("BTCUSDT")
        assert len(frame) == 10
        assert neu == 0
        # Der spaetere Schreibvorgang gewinnt - eine Korrektur soll ankommen.
        assert frame["funding_rate"].iloc[0] == pytest.approx(0.0005)

    def test_ueberlappendes_schreiben_zaehlt_nur_das_neue(self, store: FundingStore) -> None:
        store.write("BTCUSDT", make_funding(count=10))
        neu = store.write(
            "BTCUSDT", make_funding(count=10, start=T0 + FUNDING_INTERVAL * 5)
        )

        assert neu == 5
        assert len(store.read("BTCUSDT")) == 15

    def test_last_time_kennt_den_letzten_eintrag(self, store: FundingStore) -> None:
        assert store.last_time("BTCUSDT") is None

        store.write("BTCUSDT", make_funding(count=10))
        assert store.last_time("BTCUSDT") == T0 + FUNDING_INTERVAL * 9

    def test_leere_liste_schreibt_nichts(self, store: FundingStore) -> None:
        assert store.write("BTCUSDT", []) == 0
        assert store.read("BTCUSDT").empty


class TestFundingToFrame:
    def test_sortiert_und_entdoppelt(self) -> None:
        rates = make_funding(count=5)
        frame = funding_to_frame([rates[3], rates[0], rates[3], rates[1]])

        assert len(frame) == 3
        assert frame["time"].is_monotonic_increasing

    def test_leere_eingabe_behaelt_die_spalten(self) -> None:
        frame = funding_to_frame([])

        assert frame.empty
        assert frame["funding_rate"].dtype == "float64"


# ---------------------------------------------------------------------------
#  Backfill - das Paging
# ---------------------------------------------------------------------------
class TestBackfillFunding:
    def test_laedt_mehr_als_eine_seite(self, store: FundingStore) -> None:
        """Der Test, den es bei den Kerzen nicht gab.

        Das Double liefert die *juengsten* Eintraege eines Fensters. Eine
        Schleife ohne Fenstergrenze bekaeme damit sofort das Ende der Historie
        und waere nach einer Anfrage fertig - mit knapp 200 statt 1.000
        Eintraegen.
        """
        rates = make_funding(count=PAGE_SIZE * 5)
        market = FakeMarketData(funding=rates)

        written = backfill_funding(
            market, store, "BTCUSDT", start=T0, end=T0 + FUNDING_INTERVAL * PAGE_SIZE * 5
        )

        assert written == PAGE_SIZE * 5
        assert len(store.read("BTCUSDT")) == PAGE_SIZE * 5
        assert len(market.funding_calls) >= 5

    def test_jede_anfrage_hat_beide_grenzen(self, store: FundingStore) -> None:
        """Ohne ``end`` ignoriert Bybit den Startzeitpunkt."""
        market = FakeMarketData(funding=make_funding(count=PAGE_SIZE * 2))

        backfill_funding(
            market, store, "BTCUSDT", start=T0, end=T0 + FUNDING_INTERVAL * PAGE_SIZE * 2
        )

        assert market.funding_calls
        for call in market.funding_calls:
            assert call["start"] is not None
            assert call["end"] is not None
            assert call["end"] - call["start"] <= FUNDING_INTERVAL * PAGE_SIZE

    def test_setzt_hinter_dem_letzten_eintrag_fort(self, store: FundingStore) -> None:
        rates = make_funding(count=100)
        store.write("BTCUSDT", rates[:60])
        market = FakeMarketData(funding=rates)

        written = backfill_funding(
            market, store, "BTCUSDT", start=T0, end=T0 + FUNDING_INTERVAL * 100
        )

        assert written == 40
        assert market.funding_calls[0]["start"] == rates[59].funding_time + FUNDING_INTERVAL

    def test_luecke_beendet_den_backfill_nicht(self, store: FundingStore) -> None:
        """Eine leere Seite heisst "hier war nichts", nicht "fertig".

        Bybit hatte Wartungsfenster, in denen keine Zahlung stattfand. Wer beim
        ersten leeren Ergebnis abbricht, verliert alles danach.
        """
        vorher = make_funding(count=PAGE_SIZE)
        luecke = FUNDING_INTERVAL * PAGE_SIZE * 2
        nachher = make_funding(
            count=50, start=T0 + FUNDING_INTERVAL * PAGE_SIZE + luecke
        )
        market = FakeMarketData(funding=vorher + nachher)

        written = backfill_funding(
            market,
            store,
            "BTCUSDT",
            start=T0,
            end=T0 + FUNDING_INTERVAL * PAGE_SIZE + luecke + FUNDING_INTERVAL * 50,
        )

        assert written == PAGE_SIZE + 50

    def test_haeufigere_zahlung_verkleinert_das_fenster(self, store: FundingStore) -> None:
        """Wenn mehr als eine Seite ins Fenster passt, laesst Bybit Aeltestes weg.

        Ein Symbol, das stuendlich zahlt, bringt in ein Acht-Stunden-Fenster das
        Achtfache. Ohne Nachsteuerung entstuenden Loecher - und zwar lautlose,
        weil jede einzelne Antwort plausibel aussieht.
        """
        rates = make_funding(count=PAGE_SIZE * 3, interval=timedelta(hours=1))
        market = FakeMarketData(funding=rates)

        written = backfill_funding(
            market,
            store,
            "BTCUSDT",
            start=T0,
            end=T0 + timedelta(hours=1) * PAGE_SIZE * 3,
            max_pages=400,
        )

        frame = store.read("BTCUSDT")
        assert written == PAGE_SIZE * 3
        # Keine Luecke: die Abstaende sind ueberall genau eine Stunde.
        abstaende = frame["time"].diff().dropna().unique()
        assert len(abstaende) == 1

    def test_bricht_ab_wenn_der_cursor_steht(self, store: FundingStore) -> None:
        """Eine Boerse, die immer denselben Eintrag liefert, darf nicht haengen."""

        class Stuck(FakeMarketData):
            def get_funding_history(self, symbol, *, start=None, end=None, limit=200):
                return make_funding(count=1)

        written = backfill_funding(
            Stuck(), store, "BTCUSDT", start=T0 + FUNDING_INTERVAL * 10,
            end=T0 + FUNDING_INTERVAL * 100,
        )

        assert written <= 1

    def test_respektiert_das_ende(self, store: FundingStore) -> None:
        market = FakeMarketData(funding=make_funding(count=500))

        backfill_funding(
            market, store, "BTCUSDT", start=T0, end=T0 + FUNDING_INTERVAL * 50
        )

        frame = store.read("BTCUSDT")
        assert frame["time"].iloc[-1] < pd.Timestamp(T0 + FUNDING_INTERVAL * 50)


# ---------------------------------------------------------------------------
#  Anhaengen - hier sitzt der Lookahead
# ---------------------------------------------------------------------------
class TestAttachFunding:
    def test_traegt_nur_vergangenes_ein(self) -> None:
        """Der wichtigste Test der Datei.

        Kerzen um 08:00, 09:00 ... 15:00 duerfen alle nur die 08:00-Rate
        kennen. Erst die 16:00-Kerze bekommt die 16:00-Rate. Eine Zuordnung
        zum naechstgelegenen Zeitpunkt wuerde ab 12:00 die Zukunft verraten
        und faellt hier durch.
        """
        candles = make_candles(count=24, start=T0, interval=Interval.H1)
        frame = pd.DataFrame(
            {
                "open_time": [c.open_time for c in candles],
                "close": [float(c.close) for c in candles],
            }
        )
        funding = funding_to_frame(
            [
                FundingRate(symbol="BTCUSDT", funding_time=T0, funding_rate=Decimal("0.0001")),
                FundingRate(
                    symbol="BTCUSDT",
                    funding_time=T0 + timedelta(hours=8),
                    funding_rate=Decimal("0.0009"),
                ),
                FundingRate(
                    symbol="BTCUSDT",
                    funding_time=T0 + timedelta(hours=16),
                    funding_rate=Decimal("0.0002"),
                ),
            ]
        )

        result = attach_funding(frame, funding)
        werte = result["funding_rate"].to_numpy()

        assert werte[0] == pytest.approx(0.0001)  # 00:00
        assert werte[7] == pytest.approx(0.0001)  # 07:00 - noch die alte
        assert werte[8] == pytest.approx(0.0009)  # 08:00 - jetzt die neue
        assert werte[15] == pytest.approx(0.0009)  # 15:00 - immer noch
        assert werte[16] == pytest.approx(0.0002)  # 16:00

    def test_vor_dem_ersten_eintrag_bleibt_nan(self) -> None:
        """Kein geratener Wert. NaN heisst: die Strategie handelt nicht."""
        candles = make_candles(count=10, start=T0, interval=Interval.H1)
        frame = pd.DataFrame({"open_time": [c.open_time for c in candles]})
        funding = funding_to_frame(
            [
                FundingRate(
                    symbol="BTCUSDT",
                    funding_time=T0 + timedelta(hours=5),
                    funding_rate=Decimal("0.0003"),
                )
            ]
        )

        result = attach_funding(frame, funding)

        assert result["funding_rate"].iloc[:5].isna().all()
        assert result["funding_rate"].iloc[5:].notna().all()

    def test_ohne_funding_daten_nur_nan(self) -> None:
        candles = make_candles(count=10, start=T0, interval=Interval.H1)
        frame = pd.DataFrame({"open_time": [c.open_time for c in candles]})

        result = attach_funding(frame, funding_to_frame([]))

        assert "funding_rate" in result.columns
        assert result["funding_rate"].isna().all()

    def test_ueberlebt_den_umweg_ueber_die_platte(
        self, store: FundingStore, tmp_path: Path
    ) -> None:
        """Gespeichert und wieder gelesen - nicht nur im Arbeitsspeicher gebaut.

        Parquet schreibt Zeitstempel in Mikrosekunden, Kerzen kommen in
        Nanosekunden. ``merge_asof`` bricht bei ungleichen Typen hart ab. Alle
        Tests darueber bauen beide Rahmen im Speicher und merken davon nichts;
        der erste echte Durchlauf ist auf die Nase gefallen.
        """
        from data.store import CandleStore

        candles = make_candles(count=48, start=T0, interval=Interval.H1)
        candle_store = CandleStore(tmp_path / "kerzen")
        candle_store.write("BTCUSDT", Interval.H1, candles)
        store.write("BTCUSDT", make_funding(count=10))

        result = attach_funding(
            candle_store.read("BTCUSDT", Interval.H1), store.read("BTCUSDT")
        )

        assert result["funding_rate"].notna().any()

    def test_laesst_den_eingabe_rahmen_unveraendert(self) -> None:
        candles = make_candles(count=10, start=T0, interval=Interval.H1)
        frame = pd.DataFrame({"open_time": [c.open_time for c in candles]})

        attach_funding(frame, funding_to_frame(make_funding(count=5)))

        assert "funding_rate" not in frame.columns

    def test_reihenfolge_der_kerzen_bleibt_erhalten(self) -> None:
        """merge_asof sortiert intern - die Zuordnung darf dadurch nicht rutschen."""
        candles = make_candles(count=48, start=T0, interval=Interval.H1)
        frame = pd.DataFrame(
            {
                "open_time": [c.open_time for c in candles],
                "marke": list(range(48)),
            }
        )
        funding = funding_to_frame(make_funding(count=10))

        result = attach_funding(frame, funding)

        assert result["marke"].tolist() == list(range(48))
        assert result["open_time"].is_monotonic_increasing


# ---------------------------------------------------------------------------
#  Indikatoren
# ---------------------------------------------------------------------------
class TestFundingIndicators:
    def _frame(self, rates: list[float]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open_time": pd.date_range(T0, periods=len(rates), freq="h", tz="UTC"),
                "close": np.full(len(rates), 50_000.0),
                "funding_rate": rates,
            }
        )

    def test_ohne_spalte_nur_nan(self) -> None:
        """Fehlende Daten duerfen nicht als 0 durchgehen.

        Eine Null waere ein aussagekraeftiger Wert - "Funding ist neutral" -
        und wuerde Carry-Strategien zum Handeln bringen, ohne dass irgendetwas
        bekannt waere.
        """
        frame = pd.DataFrame({"close": [1.0, 2.0, 3.0]})

        assert np.isnan(funding_rate(frame)).all()
        assert np.isnan(funding_avg(frame, period=3)).all()
        assert np.isnan(funding_zscore(frame, period=3)).all()

    def test_rate_in_prozent(self) -> None:
        frame = self._frame([0.0001, 0.0005, -0.0002])

        werte = funding_rate(frame)

        assert werte[0] == pytest.approx(0.01)
        assert werte[1] == pytest.approx(0.05)
        assert werte[2] == pytest.approx(-0.02)

    def test_durchschnitt_braucht_volle_periode(self) -> None:
        frame = self._frame([0.0001] * 5)

        werte = funding_avg(frame, period=3)

        assert np.isnan(werte[:2]).all()
        assert werte[2] == pytest.approx(0.01)

    def test_zscore_schaut_nur_zurueck(self) -> None:
        """Ein Ausschlag am Ende darf die frueheren Werte nicht veraendern.

        Genau daran scheitert die naheliegende Variante, die gegen Mittelwert
        und Streuung der *ganzen* Reihe misst: Dann weiss jeder Balken, was
        spaeter noch kommt.
        """
        ruhig = [0.0001 + 0.00001 * (i % 5) for i in range(40)]
        frame_a = self._frame([*ruhig, 0.0001])
        frame_b = self._frame([*ruhig, 0.0090])

        a = funding_zscore(frame_a, period=20)
        b = funding_zscore(frame_b, period=20)

        assert np.isfinite(a[19:40]).all(), "Der Test saehe sonst nur NaN an"
        np.testing.assert_allclose(a[:40], b[:40], equal_nan=True)
        assert b[-1] > 3.0

    def test_zscore_ohne_streuung_gibt_nan(self) -> None:
        """Konstante Rate: der z-Wert waere eine Division durch null."""
        frame = self._frame([0.0001] * 40)

        werte = funding_zscore(frame, period=20)

        assert np.isnan(werte[-1])


# ---------------------------------------------------------------------------
#  Zusammenspiel
# ---------------------------------------------------------------------------
class TestVierteGeneration:
    def _frame(self, count: int = 900) -> pd.DataFrame:
        candles = make_candles(count=count, start=T0, interval=Interval.H1)
        return pd.DataFrame(
            {
                "open_time": [c.open_time for c in candles],
                "open": [float(c.open) for c in candles],
                "high": [float(c.high) for c in candles],
                "low": [float(c.low) for c in candles],
                "close": [float(c.close) for c in candles],
                "volume": [float(c.volume) for c in candles],
            }
        )

    def _config(self):
        from backtest.engine import BacktestConfig
        from core.config import RiskSettings
        from tests.factories import make_instrument

        return BacktestConfig(
            instrument=make_instrument(),
            risk=RiskSettings(),
            initial_equity=Decimal("500"),
        )

    def test_ohne_funding_handelt_keiner(self) -> None:
        """Der Grund, warum ``cli funding`` vor ``cli research`` laufen muss.

        Fehlt die Spalte, geben die Indikatoren NaN, jede Bedingung darauf ist
        unerfuellt, und es entsteht kein einziges Signal. Das ist richtig - aber
        es sieht im Zulassungsbericht aus wie ein widerlegter Kandidat. Genau
        deshalb warnt der ``research``-Befehl laut, wenn die Datei fehlt.
        """
        from backtest.engine import Backtester
        from research.seeds import load_seeds
        from strategy.compiler import compile_genome

        genomes = load_seeds(generation=4)
        assert genomes

        frame = self._frame()
        for genome in genomes:
            result = Backtester(self._config()).run(frame, compile_genome(genome))
            assert not result.trades, (
                f"{genome.name} hat ohne Funding-Daten gehandelt - dann beruht "
                "der Kandidat nicht wirklich auf der neuen Datenquelle."
            )

    def test_mit_funding_entstehen_signale(self) -> None:
        """Die Leitung ist angeschlossen - nicht nur gebaut.

        Bei durchgehend negativer Rate zahlen die Shorts, und der Carry-Kandidat
        soll long gehen. Das prueft die gesamte Kette: Speicher, Anhaengen,
        Indikator, Bedingung, Engine.
        """
        from backtest.engine import Backtester
        from research.seeds import funding_carry_long
        from strategy.compiler import compile_genome

        frame = self._frame()
        funding = funding_to_frame(
            make_funding(count=400, rate="-0.0003")
        )
        mit_funding = attach_funding(frame, funding)

        result = Backtester(self._config()).run(
            mit_funding, compile_genome(funding_carry_long())
        )

        assert result.trades, (
            "Bei durchgehend negativer Funding-Rate muss der Carry-Kandidat "
            "long gehen - sonst kommt die Spalte nicht bis zum Indikator durch."
        )


# ---------------------------------------------------------------------------
#  Der Befehl
# ---------------------------------------------------------------------------
class TestFundingBefehl:
    def test_laedt_und_meldet(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``cli funding`` schreibt in den Speicher, aus dem ``research`` liest.

        Der Befehl war der fehlende Teil: Die Anbindung an Bybit gab es seit
        Phase 0, die Indikatoren seit der vierten Generation - nur den Weg von
        der einen zur anderen Seite nicht.
        """
        from typer.testing import CliRunner

        import cli as cli_module
        from core.config import get_settings

        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()
        market = FakeMarketData(funding=make_funding(count=300))
        monkeypatch.setattr(cli_module, "BybitMarketData", lambda settings: market)

        result = CliRunner().invoke(
            cli_module.app,
            ["funding", "--von", "2024-01-01", "--bis", "2024-04-01"],
        )
        get_settings.cache_clear()

        assert result.exit_code == 0, result.output
        gespeichert = FundingStore(
            get_settings().paths.data_store
        ).read("BTCUSDT")
        assert not gespeichert.empty

    def test_meldet_wenn_nichts_kommt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Eine leere Antwort ist ein Fehler, kein stiller Erfolg.

        Sonst laeuft ``research`` danach durch, alle Funding-Kandidaten machen
        null Trades, und der Bericht liest sich wie ein widerlegter Gedanke -
        obwohl nur eine Datei fehlt.
        """
        from typer.testing import CliRunner

        import cli as cli_module
        from core.config import get_settings

        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()
        monkeypatch.setattr(
            cli_module, "BybitMarketData", lambda settings: FakeMarketData()
        )

        result = CliRunner().invoke(cli_module.app, ["funding"])
        get_settings.cache_clear()

        assert result.exit_code == 2
        assert "Nichts geladen" in result.output
