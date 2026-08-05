"""Tests fuer die Referenzkerzen.

Der eine Punkt, der hier wirklich zaehlt: Diese Kerzen duerfen sich **niemals**
mit den Handelsdaten vermischen. Bitstamp BTC/USD ist ein Kassamarkt ohne
Funding, an einer anderen Boerse, mit anderer Liquiditaet. Als Forschungsdaten
sind sie gut genug; als Grundlage fuer eine Order waeren sie falsch.

Deshalb liegen sie unter einem eigenen Symbol, und ein Test haelt das fest.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from core.models import Interval
from data.reference import (
    PAGE_SIZE,
    REFERENCE_SYMBOL,
    BitstampReference,
    backfill_reference,
    estimate_pages,
)
from data.store import CandleStore

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def bitstamp_antwort(*, start: datetime, count: int, step: int = 900) -> dict:
    """Eine Antwort im Format von Bitstamp - aufsteigend ab ``start``."""
    return {
        "data": {
            "pair": "BTC/USD",
            "ohlc": [
                {
                    "timestamp": str(int((start + timedelta(seconds=step * i)).timestamp())),
                    # Der Schlusskurs muss innerhalb von Hoch und Tief
                    # liegen - das Candle-Modell prueft das, und beim ersten
                    # Entwurf dieser Testdaten lief er nach hundert Kerzen
                    # aus dem Hoch heraus.
                    "open": "40000.0",
                    "high": "40100.0",
                    "low": "39900.0",
                    "close": f"{40000 + i % 100}.0",
                    "volume": "12.5",
                }
                for i in range(count)
            ],
        }
    }


def quelle_mit(seiten: list[int]) -> BitstampReference:
    """Eine Quelle, die der Reihe nach Seiten der angegebenen Laenge liefert."""
    aufrufe: list[dict] = []
    rest = list(seiten)

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        aufrufe.append(params)
        start = datetime.fromtimestamp(int(params["start"]), tz=UTC)
        count = rest.pop(0) if rest else 0
        return httpx.Response(200, json=bitstamp_antwort(start=start, count=count))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    quelle = BitstampReference(client=client, pause=0.0)
    quelle.aufrufe = aufrufe  # type: ignore[attr-defined]
    return quelle


@pytest.fixture
def store(tmp_path: Path) -> CandleStore:
    return CandleStore(tmp_path / "data_store")


class TestBitstampReference:
    def test_uebersetzt_in_unser_format(self) -> None:
        quelle = quelle_mit([3])

        kerzen = quelle.get_klines(Interval.M15, start=T0)

        assert len(kerzen) == 3
        assert kerzen[0].open_time == T0
        assert kerzen[0].open == Decimal("40000.0")
        # Der Umsatz steht bei Bitstamp nicht drin und wird abgeleitet.
        assert kerzen[0].turnover > 0
        # Symbol und Intervall gehoeren nicht zur Kerze, sondern zum
        # Speicherort - siehe TestTrennung.
        assert not hasattr(kerzen[0], "symbol")

    def test_unbekanntes_intervall_wird_abgelehnt(self) -> None:
        """Lieber ein Fehler als stillschweigend eine falsche Schrittweite."""
        quelle = quelle_mit([1])

        with pytest.raises(ValueError, match="Intervall"):
            quelle.get_klines(Interval.W1, start=T0)

    def test_schrittweite_passt_zum_intervall(self) -> None:
        quelle = quelle_mit([1, 1])

        quelle.get_klines(Interval.M15, start=T0)
        quelle.get_klines(Interval.H1, start=T0)

        assert quelle.aufrufe[0]["step"] == "900"
        assert quelle.aufrufe[1]["step"] == "3600"


class TestBackfill:
    def test_laedt_ueber_mehrere_seiten(self, store: CandleStore) -> None:
        quelle = quelle_mit([PAGE_SIZE, PAGE_SIZE, 500])

        geschrieben = backfill_reference(
            quelle,
            store,
            Interval.M15,
            start=T0,
            end=T0 + timedelta(minutes=15) * 2500,
        )

        assert geschrieben == PAGE_SIZE * 2 + 500
        assert len(quelle.aufrufe) >= 3

    def test_setzt_hinter_dem_speicher_fort(self, store: CandleStore) -> None:
        quelle = quelle_mit([100, 100])
        backfill_reference(
            quelle, store, Interval.M15,
            start=T0, end=T0 + timedelta(minutes=15) * 100,
        )
        vorher = store.coverage(REFERENCE_SYMBOL, Interval.M15).rows

        zweite = quelle_mit([50])
        backfill_reference(
            zweite, store, Interval.M15,
            start=T0, end=T0 + timedelta(minutes=15) * 150,
        )

        # Die zweite Anfrage darf nicht wieder bei T0 anfangen.
        assert zweite.aufrufe[0]["start"] != str(int(T0.timestamp()))
        assert store.coverage(REFERENCE_SYMBOL, Interval.M15).rows > vorher

    def test_respektiert_das_ende(self, store: CandleStore) -> None:
        quelle = quelle_mit([PAGE_SIZE])
        ende = T0 + timedelta(minutes=15) * 10

        backfill_reference(quelle, store, Interval.M15, start=T0, end=ende)

        frame = store.read(REFERENCE_SYMBOL, Interval.M15)
        assert frame["open_time"].max() < ende

    def test_leere_antwort_beendet_sauber(self, store: CandleStore) -> None:
        quelle = quelle_mit([0])

        geschrieben = backfill_reference(
            quelle, store, Interval.M15, start=T0, end=T0 + timedelta(days=30)
        )

        assert geschrieben == 0

    def test_stehender_cursor_bricht_ab(self, store: CandleStore) -> None:
        """Eine Quelle, die immer dieselbe Kerze liefert, darf nicht haengen."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=bitstamp_antwort(start=T0, count=1))

        quelle = BitstampReference(
            client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0.0
        )

        geschrieben = backfill_reference(
            quelle, store, Interval.M15,
            start=T0 + timedelta(days=1), end=T0 + timedelta(days=30),
        )

        assert geschrieben <= 1


class TestTrennung:
    def test_referenzkerzen_haben_ein_eigenes_symbol(self, store: CandleStore) -> None:
        """Der wichtigste Test der Datei.

        Bitstamp BTC/USD ist ein Kassamarkt ohne Funding, an einer anderen
        Boerse. Als Forschungsdaten taugt das; als Grundlage fuer eine Order
        waere es falsch. Landeten beide unter demselben Symbol, wuerde der
        Unterschied irgendwann niemandem mehr auffallen.
        """
        quelle = quelle_mit([10])
        backfill_reference(
            quelle, store, Interval.M15,
            start=T0, end=T0 + timedelta(minutes=15) * 10,
        )

        assert REFERENCE_SYMBOL != "BTCUSDT"
        assert store.read("BTCUSDT", Interval.M15).empty
        assert not store.read(REFERENCE_SYMBOL, Interval.M15).empty


def test_seitenschaetzung_ist_grob_richtig() -> None:
    seiten = estimate_pages(
        Interval.M15, datetime(2020, 3, 30, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC)
    )

    # Rund 222.000 Kerzen zu je 1000 pro Seite.
    assert 200 <= seiten <= 250


class TestMehrereMaerkte:
    """Die Gegenprobe auf anderen Maerkten - der schaerfste verfuegbare Test.

    Eine Regel, die auf sechs Jahren BTC gut aussieht, kann an genau diese
    sechs Jahre angepasst sein, ohne dass es jemandem auffaellt. Dieselbe
    Regel **ungeaendert** auf einem Markt zu pruefen, der bei der Entwicklung
    keine Rolle gespielt hat, benutzt Daten, die nicht mitgesucht wurden.

    Gehandelt wird weiterhin ausschliesslich BTC - deshalb liegt jeder Markt
    unter eigenem Symbol.
    """

    def test_jeder_markt_hat_ein_eigenes_symbol(self) -> None:
        from data.reference import PAIRS

        assert len(set(PAIRS)) == len(PAIRS)
        assert len(set(PAIRS.values())) == len(PAIRS)
        assert PAIRS[REFERENCE_SYMBOL] == "btcusd"

    def test_unbekanntes_symbol_wird_abgelehnt(self) -> None:
        """Lieber ein Fehler als stillschweigend die falschen Kerzen."""
        quelle = quelle_mit([1])

        with pytest.raises(ValueError, match="Bitstamp-Paar"):
            quelle.get_klines(Interval.D1, start=T0, symbol="DOGEUSD_BITSTAMP")

    def test_das_paar_landet_in_der_adresse(self) -> None:
        aufgerufen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            aufgerufen.append(str(request.url.path))
            return httpx.Response(200, json=bitstamp_antwort(start=T0, count=1))

        quelle = BitstampReference(
            client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0.0
        )

        quelle.get_klines(Interval.D1, start=T0, symbol="ETHUSD_BITSTAMP")

        assert "ethusd" in aufgerufen[0]
        assert "btcusd" not in aufgerufen[0]

    def test_maerkte_vermischen_sich_nicht(self, store: CandleStore) -> None:
        """Der Punkt, an dem eine Gegenprobe wertlos waere.

        Landeten ETH-Kerzen unter dem BTC-Symbol, saehe die Gegenprobe
        bestanden aus und haette in Wahrheit zweimal dieselben Daten geprueft.
        """
        for symbol in ("BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"):
            backfill_reference(
                quelle_mit([10]), store, Interval.D1,
                start=T0, end=T0 + timedelta(days=10), symbol=symbol,
            )

        btc = store.coverage("BTCUSD_BITSTAMP", Interval.D1)
        eth = store.coverage("ETHUSD_BITSTAMP", Interval.D1)

        assert btc.rows == 10
        assert eth.rows == 10
        assert store.read("LTCUSD_BITSTAMP", Interval.D1).empty
