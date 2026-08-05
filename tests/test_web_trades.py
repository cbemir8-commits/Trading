"""Tests fuer die Trade-Ansicht der Website.

Der Nutzer will waehrend der Demo jeden Trade einzeln sehen: Einstieg, Stop,
Ergebnis, Haltedauer. Zwei Dinge muessen dabei stimmen, und beide sind hier
festgeschrieben:

1. **Die Liste liegt hinter der Anmeldung.** Aus Einstiegen, Mengen und
   Gewinnen laesst sich die Kontogroesse zurueckrechnen. Backtest-Zahlen darf
   jeder sehen, den Verlauf eines echten Kontos nicht.
2. **Die Kennzahlen beziehen sich auf alle Trades, nicht auf die angezeigten.**
   Sonst aendert sich die Trefferquote, sobald jemand weniger Zeilen anfordert.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from core.config import PathSettings, Settings, WebSettings
from web.api import create_app
from web.trades import read_trades

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _zeile(
    *,
    stunde: int,
    brutto: float,
    stop: float | None = 19_000.0,
    einstieg: float = 20_000.0,
    menge: float = 0.05,
    symbol: str = "BTCUSDT",
    grund: str = "take_profit",
) -> dict:
    ein = T0 + timedelta(hours=stunde)
    return {
        "trade_id": f"t{stunde}",
        "symbol": symbol,
        "side": "Buy",
        "strategy_id": "test",
        "entry_time": ein.isoformat(),
        "entry_price": einstieg,
        "exit_time": (ein + timedelta(hours=4)).isoformat(),
        "exit_price": einstieg + brutto / menge,
        "qty": menge,
        "gross_pnl": brutto,
        "fees": 0.5,
        "funding": 0.0,
        "stop_loss": stop,
        "exit_reason": grund,
        "leverage": 1.5,
    }


def _schreiben(verzeichnis: Path, zeilen: list[dict]) -> None:
    verzeichnis.mkdir(parents=True, exist_ok=True)
    with (verzeichnis / "trades.jsonl").open("w") as handle:
        for zeile in zeilen:
            handle.write(json.dumps(zeile) + "\n")


class TestLesen:
    def test_ohne_datei_kommt_eine_leere_uebersicht(self, tmp_path: Path) -> None:
        uebersicht = read_trades(tmp_path)

        assert uebersicht.anzahl == 0
        assert uebersicht.trades == []
        assert uebersicht.trefferquote is None, (
            "null Prozent bei null Trades waere eine Behauptung ueber eine "
            "Strategie, die noch nichts getan hat"
        )

    def test_gewinn_ist_netto_nach_gebuehren(self, tmp_path: Path) -> None:
        _schreiben(tmp_path, [_zeile(stunde=0, brutto=100.0)])

        trade = read_trades(tmp_path).trades[0]

        assert trade.gewinn == pytest.approx(99.5)  # 100 brutto - 0,5 Gebuehr
        assert trade.gebuehren == pytest.approx(0.5)

    def test_r_wert_misst_am_riskierten_betrag(self, tmp_path: Path) -> None:
        # Einstieg 20.000, Stop 19.000, Menge 0,05 -> 50 riskiert.
        _schreiben(tmp_path, [_zeile(stunde=0, brutto=100.0)])

        trade = read_trades(tmp_path).trades[0]

        assert trade.r == pytest.approx(99.5 / 50.0, abs=0.01)

    def test_ohne_stop_gibt_es_kein_r(self, tmp_path: Path) -> None:
        """Eine Null waere eine Aussage, die niemand gemacht hat."""
        _schreiben(tmp_path, [_zeile(stunde=0, brutto=100.0, stop=None)])

        assert read_trades(tmp_path).trades[0].r is None

    def test_neueste_zuerst(self, tmp_path: Path) -> None:
        _schreiben(
            tmp_path,
            [_zeile(stunde=0, brutto=10.0), _zeile(stunde=48, brutto=20.0)],
        )

        trades = read_trades(tmp_path).trades

        assert trades[0].zeitpunkt > trades[1].zeitpunkt

    def test_kaputte_zeile_beendet_nicht_das_ganze(self, tmp_path: Path) -> None:
        """Der Livebetrieb schreibt zeilenweise.

        Wird er mitten im Schreiben beendet, ist die letzte Zeile
        unvollstaendig. Das ist normal und darf die Seite nicht leer lassen.
        """
        tmp_path.mkdir(parents=True, exist_ok=True)
        with (tmp_path / "trades.jsonl").open("w") as handle:
            handle.write(json.dumps(_zeile(stunde=0, brutto=10.0)) + "\n")
            handle.write('{"symbol": "BTCUSDT", "entry_pr')  # abgeschnitten

        uebersicht = read_trades(tmp_path)

        assert uebersicht.anzahl == 1

    def test_zeile_ohne_pflichtfelder_wird_ausgelassen(self, tmp_path: Path) -> None:
        _schreiben(tmp_path, [{"symbol": "BTCUSDT", "side": "Buy"}])

        assert read_trades(tmp_path).anzahl == 0


class TestKennzahlen:
    def test_trefferquote_und_summen(self, tmp_path: Path) -> None:
        _schreiben(
            tmp_path,
            [
                _zeile(stunde=0, brutto=100.0),
                _zeile(stunde=24, brutto=-40.0),
                _zeile(stunde=48, brutto=60.0),
            ],
        )

        u = read_trades(tmp_path)

        assert u.anzahl == 3
        assert u.gewinner == 2
        assert u.verlierer == 1
        assert u.trefferquote == pytest.approx(2 / 3)
        assert u.gewinn_gesamt == pytest.approx(100 - 40 + 60 - 1.5)
        assert u.gebuehren_gesamt == pytest.approx(1.5)

    def test_laengste_verlustserie(self, tmp_path: Path) -> None:
        """Die Zahl, an der Strategien im Betrieb scheitern - nicht der
        Erwartungswert."""
        _schreiben(
            tmp_path,
            [
                _zeile(stunde=0, brutto=50.0),
                _zeile(stunde=8, brutto=-10.0),
                _zeile(stunde=16, brutto=-10.0),
                _zeile(stunde=24, brutto=-10.0),
                _zeile(stunde=32, brutto=50.0),
                _zeile(stunde=40, brutto=-10.0),
            ],
        )

        assert read_trades(tmp_path).laengste_verlustserie == 3

    def test_kennzahlen_gelten_fuer_alle_trades_nicht_nur_die_gezeigten(
        self, tmp_path: Path
    ) -> None:
        """Sonst aendert sich die Trefferquote, wenn jemand die Liste kuerzt."""
        zeilen = [_zeile(stunde=i, brutto=100.0) for i in range(0, 40, 8)]
        zeilen += [_zeile(stunde=i, brutto=-50.0) for i in range(40, 80, 8)]
        _schreiben(tmp_path, zeilen)

        alle = read_trades(tmp_path, limit=100)
        gekuerzt = read_trades(tmp_path, limit=2)

        assert len(gekuerzt.trades) == 2
        assert gekuerzt.anzahl == alle.anzahl == 10
        assert gekuerzt.trefferquote == alle.trefferquote == pytest.approx(0.5)


class TestRoute:
    @pytest.fixture
    def settings(self, tmp_path: Path) -> Settings:
        return Settings(
            paths=PathSettings(state=str(tmp_path), data_store=str(tmp_path / "d")),
            web=WebSettings(password=SecretStr("geheim")),
        )

    def test_ohne_anmeldung_gesperrt(self, settings: Settings) -> None:
        """Aus Einstiegen, Mengen und Gewinnen laesst sich die Kontogroesse
        zurueckrechnen. Das ist kein Forschungsergebnis, das ist ein Konto."""
        _schreiben(Path(settings.paths.state), [_zeile(stunde=0, brutto=10.0)])
        client = TestClient(create_app(settings))

        antwort = client.get("/api/trades")

        assert antwort.status_code == 401

    def test_mit_anmeldung_kommen_die_trades(self, settings: Settings) -> None:
        _schreiben(
            Path(settings.paths.state),
            [_zeile(stunde=0, brutto=100.0), _zeile(stunde=24, brutto=-40.0)],
        )
        client = TestClient(create_app(settings))
        client.post("/api/login", json={"password": "geheim"})

        daten = client.get("/api/trades").json()

        assert daten["anzahl"] == 2
        assert daten["gewinner"] == 1
        assert len(daten["trades"]) == 2
        erster = daten["trades"][0]
        for feld in ("einstieg", "ausstieg", "stop", "gewinn", "r", "grund", "hebel"):
            assert feld in erster, f"{feld} fehlt - der Trade ist nicht nachvollziehbar"

    def test_keine_order_ids_und_schluessel_in_der_antwort(
        self, settings: Settings
    ) -> None:
        """Die Seite kann geteilt werden. Alles darauf kann jemand anders lesen."""
        _schreiben(Path(settings.paths.state), [_zeile(stunde=0, brutto=10.0)])
        client = TestClient(create_app(settings))
        client.post("/api/login", json={"password": "geheim"})

        roh = client.get("/api/trades").text.lower()

        for verboten in ("order_id", "orderid", "api_key", "secret", "trade_id"):
            assert verboten not in roh, f"{verboten} steht in der Antwort"

    def test_grenze_wird_gedeckelt(self, settings: Settings) -> None:
        """Eine unbegrenzte Anfrage waere ein billiger Weg, den Dienst
        lahmzulegen."""
        _schreiben(
            Path(settings.paths.state),
            [_zeile(stunde=i, brutto=1.0) for i in range(5)],
        )
        client = TestClient(create_app(settings))
        client.post("/api/login", json={"password": "geheim"})

        assert client.get("/api/trades?limit=999999").status_code == 200
        assert client.get("/api/trades?limit=0").status_code == 200
