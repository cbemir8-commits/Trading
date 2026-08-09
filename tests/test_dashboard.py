"""Tests des Dashboards - Journal, API und Fernsteuerung.

Das Dashboard darf zwei Dinge nicht:

* **Den Handel stoeren.** Ein Fehler beim Berichten, eine volle Platte, ein
  abgestuerztes Dashboard - nichts davon darf eine Order verhindern oder eine
  Position ungeschuetzt lassen.
* **Ohne Passwort steuern.** Ein Not-Aus-Knopf, den jeder im Netz druecken
  kann, ist schlimmer als keiner.

Und eines muss es koennen: **erkennen, dass der Handel tot ist.** Genau dafuer
sind Handel und Website getrennte Prozesse. Ein Dashboard, das mit dem Handel
zusammen abstuerzt, ist in dem Moment nutzlos, in dem man es braucht.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from core.config import PathSettings, Settings, WebSettings
from web.api import create_app
from web.journal import (
    HEARTBEAT_TIMEOUT,
    CommandAction,
    EventKind,
    LiveJournal,
    read_view,
    send_command,
)

PASSWORD = "geheim-und-lang-genug"


# ---------------------------------------------------------------------------
#  Journal - der Kanal zwischen den Prozessen
# ---------------------------------------------------------------------------
class TestJournal:
    def test_snapshot_round_trip(self, tmp_path: Path) -> None:
        journal = LiveJournal(tmp_path)
        journal.write_snapshot({"equity": Decimal("512.34"), "symbol": "BTCUSDT"})

        view = read_view(tmp_path)

        assert view.snapshot["equity"] == "512.34"
        assert view.alive

    def test_decimals_stay_exact(self, tmp_path: Path) -> None:
        """Als Zeichenkette, nicht als Fliesskomma.

        Ein Kontostand, der ueber float laeuft, zeigt frueher oder spaeter
        499.99999999998 an - und das untergraebt das Vertrauen in jede
        andere Zahl auf der Seite.
        """
        journal = LiveJournal(tmp_path)
        journal.write_snapshot({"equity": Decimal("0.1") + Decimal("0.2")})

        raw = json.loads((tmp_path / "live.json").read_text())

        assert raw["equity"] == "0.3"

    def test_snapshot_is_written_atomically(self, tmp_path: Path) -> None:
        """Das Dashboard liest jederzeit - eine halb geschriebene Datei
        wuerde es als Fehler anzeigen statt als Kontostand."""
        journal = LiveJournal(tmp_path)
        journal.write_snapshot({"equity": Decimal("500")})
        journal.write_snapshot({"equity": Decimal("501")})

        files = sorted(p.name for p in tmp_path.iterdir())

        assert files == ["live.json"]

    def test_events_are_newest_first(self, tmp_path: Path) -> None:
        journal = LiveJournal(tmp_path)
        journal.record(EventKind.START, "erstes")
        journal.record(EventKind.SIGNAL, "zweites")

        view = read_view(tmp_path)

        assert [e["message"] for e in view.events] == ["zweites", "erstes"]

    def test_truncated_last_line_is_skipped(self, tmp_path: Path) -> None:
        """Wird der Prozess mitten im Schreiben getoetet, steht eine halbe
        Zeile in der Datei. Das Dashboard muss den Rest trotzdem zeigen."""
        journal = LiveJournal(tmp_path)
        journal.record(EventKind.START, "vollstaendig")
        with (tmp_path / "events.jsonl").open("a") as handle:
            handle.write('{"kind": "signal", "mess')

        view = read_view(tmp_path)

        assert [e["message"] for e in view.events] == ["vollstaendig"]


class TestHeartbeat:
    def test_missing_files_mean_never_started(self, tmp_path: Path) -> None:
        view = read_view(tmp_path)

        assert not view.alive
        assert view.status_text == "nie gestartet"
        assert view.snapshot == {}

    def test_fresh_heartbeat_means_alive(self, tmp_path: Path) -> None:
        LiveJournal(tmp_path).write_snapshot({})

        assert read_view(tmp_path).alive

    def test_stale_heartbeat_means_dead(self, tmp_path: Path) -> None:
        """Der eigentliche Zweck der Prozesstrennung.

        Ein Dashboard, das im selben Prozess wie der Handel laeuft, kann diesen
        Zustand gar nicht anzeigen - es waere selbst weg.
        """
        old = datetime.now(UTC) - HEARTBEAT_TIMEOUT - timedelta(minutes=5)
        (tmp_path / "live.json").write_text(
            json.dumps({"heartbeat": old.isoformat(), "equity": "500"})
        )

        view = read_view(tmp_path)

        assert not view.alive
        assert "kein Lebenszeichen" in view.status_text

    def test_corrupt_snapshot_does_not_crash(self, tmp_path: Path) -> None:
        (tmp_path / "live.json").write_text("{kaputt")

        view = read_view(tmp_path)

        assert not view.alive
        assert view.snapshot == {}


class TestCommands:
    def test_command_round_trip(self, tmp_path: Path) -> None:
        send_command(tmp_path, CommandAction.PAUSE, "Test")

        command = LiveJournal(tmp_path).take_command()

        assert command is not None
        assert command.action is CommandAction.PAUSE
        assert command.reason == "Test"

    def test_command_is_consumed_exactly_once(self, tmp_path: Path) -> None:
        """Sonst wuerde ein 'alles schliessen' bei jeder Kerze erneut laufen."""
        send_command(tmp_path, CommandAction.CLOSE_ALL)
        journal = LiveJournal(tmp_path)

        assert journal.take_command() is not None
        assert journal.take_command() is None

    def test_newer_command_replaces_the_waiting_one(self, tmp_path: Path) -> None:
        """Wer zweimal auf Not-Aus drueckt, meint nicht zweimal schliessen."""
        send_command(tmp_path, CommandAction.PAUSE)
        send_command(tmp_path, CommandAction.KILL)

        journal = LiveJournal(tmp_path)

        assert journal.take_command().action is CommandAction.KILL
        assert journal.take_command() is None

    def test_corrupt_command_is_discarded(self, tmp_path: Path) -> None:
        """Und nicht endlos erneut versucht - sonst blockiert eine kaputte
        Datei jeden weiteren Befehl."""
        (tmp_path / "command.json").write_text("{kaputt")
        journal = LiveJournal(tmp_path)

        assert journal.take_command() is None
        assert not (tmp_path / "command.json").exists()


# ---------------------------------------------------------------------------
#  Weboberflaeche
# ---------------------------------------------------------------------------
def make_settings(tmp_path: Path, *, password: str = PASSWORD) -> Settings:
    return Settings(
        paths=PathSettings(state=str(tmp_path)),
        web=WebSettings(password=SecretStr(password)),
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(make_settings(tmp_path)))


@pytest.fixture
def open_client(tmp_path: Path) -> TestClient:
    """Ohne gesetztes Passwort - Nur-Lese-Betrieb."""
    return TestClient(create_app(make_settings(tmp_path, password="")))


class TestReading:
    def test_status_without_login(self, client: TestClient) -> None:
        """Zuschauen darf man auch ohne Anmeldung - steuern nicht."""
        response = client.get("/api/status")

        assert response.status_code == 200
        assert response.json()["authenticated"] is False

    def test_status_works_before_the_bot_ever_ran(self, client: TestClient) -> None:
        body = client.get("/api/status").json()

        assert body["alive"] is False
        assert body["status_text"] == "nie gestartet"

    def test_status_shows_the_snapshot(self, client: TestClient, tmp_path: Path) -> None:
        LiveJournal(tmp_path).write_snapshot({"equity": Decimal("487.20")})
        LiveJournal(tmp_path).record(EventKind.ENTRY, "Einstieg Long")

        body = client.get("/api/status").json()

        assert body["alive"] is True
        assert body["snapshot"]["equity"] == "487.20"
        assert body["events"][0]["message"] == "Einstieg Long"

    def test_page_loads(self, client: TestClient) -> None:
        response = client.get("/")

        assert response.status_code == 200
        assert "Trading" in response.text


class TestAuthentication:
    def test_control_without_login_is_refused(self, client: TestClient) -> None:
        response = client.post("/api/control/kill")

        assert response.status_code == 401

    def test_wrong_password_is_refused(self, client: TestClient) -> None:
        response = client.post("/api/login", json={"password": "falsch"})

        assert response.status_code == 401

    def test_login_then_control(self, client: TestClient, tmp_path: Path) -> None:
        assert client.post("/api/login", json={"password": PASSWORD}).status_code == 200

        response = client.post("/api/control/pause")

        assert response.status_code == 200
        assert LiveJournal(tmp_path).take_command().action is CommandAction.PAUSE

    def test_logout_ends_the_session(self, client: TestClient) -> None:
        client.post("/api/login", json={"password": PASSWORD})
        client.post("/api/logout")

        assert client.post("/api/control/pause").status_code == 401

    def test_without_password_control_is_locked(self, open_client: TestClient) -> None:
        """Ein Not-Aus-Knopf ohne Passwort waere schlimmer als keiner:
        Jeder im Netz koennte die Position schliessen."""
        assert open_client.get("/api/status").json()["read_only"] is True
        assert open_client.post("/api/control/kill").status_code == 403
        assert open_client.post("/api/login", json={"password": ""}).status_code == 403

    def test_unknown_action_is_refused(self, client: TestClient) -> None:
        client.post("/api/login", json={"password": PASSWORD})

        response = client.post("/api/control/alles_verkaufen_und_nach_hause")

        assert response.status_code == 400


class TestControlEndpoints:
    @pytest.mark.parametrize(
        "action",
        [CommandAction.PAUSE, CommandAction.RESUME, CommandAction.CLOSE_ALL, CommandAction.KILL],
    )
    def test_every_action_reaches_the_trader(
        self, client: TestClient, tmp_path: Path, action: CommandAction
    ) -> None:
        client.post("/api/login", json={"password": PASSWORD})

        response = client.post(f"/api/control/{action.value}")

        assert response.status_code == 200
        assert LiveJournal(tmp_path).take_command().action is action

    def test_response_says_it_is_not_immediate(
        self, client: TestClient
    ) -> None:
        """Der Befehl wird abgelegt, nicht ausgefuehrt - das muss dranstehen,
        sonst haelt man einen Not-Aus faelschlich fuer erledigt."""
        client.post("/api/login", json={"password": PASSWORD})

        body = client.post("/api/control/kill").json()

        assert "naechsten Kerze" in body["hinweis"]


def test_die_meldung_nennt_den_schluessel_den_es_wirklich_gibt(
    open_client: TestClient,
) -> None:
    """**Eine Fehlermeldung, die im Kreis schickt, ist schlimmer als keine.**

    Hier stand zweimal ``WEB__PASSWORD_HASH``. Der Schluessel heisst aber
    ``WEB__PASSWORD``. Wer der Meldung folgte, trug den falschen Namen in die
    ``.env`` ein, startete neu - und bekam dieselbe Meldung wieder. Genau auf
    diesem Weg liegt der Not-Aus.

    Geprueft wird, was der Nutzer zu sehen bekommt, und der erwartete Name
    kommt aus dem Einstellungsmodell: Wer das Feld umbenennt, faellt hier auf.
    """
    assert "password" in WebSettings.model_fields
    schluessel = f"WEB__{'password'.upper()}"

    antwort = open_client.post("/api/control/kill")

    assert antwort.status_code == 403
    text = antwort.json()["detail"]
    assert schluessel in text
    assert f"{schluessel}_HASH" not in text
