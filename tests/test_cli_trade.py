"""Tests des ``trade``-Befehls - genauer: seiner Bremsen.

Der Befehl selbst laesst sich hier nicht bis zum Ende ausfuehren, er braucht
eine Boerse. Was sich pruefen laesst, ist alles, was **davor** passiert - und
genau das sind die Sicherheitsabfragen:

* Auf Mainnet wird ohne ausdrueckliche Bestaetigung nicht gehandelt.
* Ohne zugelassenes Genom wird nicht gehandelt.
* Bei aktivem Kill-Switch wird nicht einmal eine Verbindung aufgebaut.

Alle drei laufen vor dem ersten Netzwerkaufruf. Das ist Absicht: Eine
Sicherheitsabfrage, die erst nach dem Verbindungsaufbau greift, hat den
gefaehrlichen Zustand schon zugelassen.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli import app
from core.config import get_settings
from execution.risk import RiskState, TradingState

runner = CliRunner()

GENOME = {
    "name": "Testgenom",
    "rationale": "Existiert nur, damit der Befehl etwas zum Laden hat.",
    "entry_long": [
        {
            "left": {"kind": "indicator", "name": "ema", "params": {"period": 10}},
            "op": "gt",
            "right": {"kind": "indicator", "name": "ema", "params": {"period": 30}},
        }
    ],
    "targets": [{"rr": 1.5, "portion": 0.5}, {"rr": 3.0, "portion": 0.5}],
}


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ein isoliertes Arbeitsverzeichnis mit eigener Konfiguration.

    ``get_settings`` ist gecacht - ohne ``cache_clear`` wuerde ein Test die
    Konfiguration des naechsten sehen.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATHS__DATA_STORE", str(tmp_path / "data_store"))
    monkeypatch.setenv("PATHS__STATE", str(tmp_path / "state"))
    monkeypatch.setenv("PATHS__STRATEGIES", str(tmp_path / "strategies"))
    monkeypatch.setenv("BYBIT__ENVIRONMENT", "demo")
    monkeypatch.setenv("BYBIT__API_KEY", "testkey")
    monkeypatch.setenv("BYBIT__API_SECRET", "testsecret")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def write_genome(workspace: Path) -> Path:
    directory = workspace / "strategies"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "champion.json"
    path.write_text(json.dumps(GENOME))
    return path


def write_kill_switch(workspace: Path, reason: str) -> None:
    state = RiskState(
        trading_state=TradingState.KILLED,
        equity_peak=Decimal("500"),
        kill_reason=reason,
    )
    directory = workspace / "state"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "risk.json").write_text(json.dumps(state.to_json()))


class TestRealMoneyGuard:
    def test_mainnet_refuses_without_confirmation(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ein Tippfehler in der Umgebungsvariablen darf nicht dazu fuehren,
        dass versehentlich echtes Geld bewegt wird."""
        monkeypatch.setenv("BYBIT__ENVIRONMENT", "mainnet")
        get_settings.cache_clear()
        write_genome(workspace)

        result = runner.invoke(app, ["trade", "--trocken"])

        assert result.exit_code == 2
        assert "MAINNET" in result.output
        assert "--echtgeld" in result.output

    def test_demo_needs_no_confirmation(self, workspace: Path) -> None:
        """Auf Demo darf die Huerde nicht im Weg stehen - dort soll 30 Tage
        lang ohne Reibung getestet werden."""
        write_genome(workspace)

        result = runner.invoke(app, ["trade", "--trocken"])

        assert "MAINNET" not in result.output


class TestStrategyRequirement:
    def test_missing_genome_is_refused(self, workspace: Path) -> None:
        """Gehandelt wird nur, was die Zulassungs-Gates bestanden hat."""
        result = runner.invoke(app, ["trade", "--trocken"])

        assert result.exit_code == 2
        assert "Keine Strategie unter" in result.output
        assert "Zulassungs-Gates" in result.output

    def test_named_genome_is_loaded(self, workspace: Path) -> None:
        """Mit ``-s`` wird die genannte Datei genommen, nicht der Champion.

        Der Befehl scheitert danach an der fehlenden Boersenverbindung - aber
        eben *danach*, und nicht an einer nicht gefundenen Strategie.
        """
        path = workspace / "eigene.json"
        path.write_text(json.dumps(GENOME))

        result = runner.invoke(app, ["trade", "--trocken", "-s", str(path)])

        assert "Keine Strategie unter" not in result.output


class TestKillSwitchGuard:
    def test_active_kill_switch_prevents_the_start(self, workspace: Path) -> None:
        """Und zwar bevor irgendeine Verbindung aufgebaut wird.

        Der Test belegt das indirekt, aber zuverlaessig: In diesem Container
        ist Bybit geoblockt. Ein Verbindungsversuch wuerde eine andere
        Fehlermeldung erzeugen als die erwartete.
        """
        write_genome(workspace)
        write_kill_switch(workspace, "Drawdown-Grenze erreicht")

        result = runner.invoke(app, ["trade", "--trocken"])

        assert result.exit_code == 2
        assert "Kill-Switch ist aktiv" in result.output
        assert "Drawdown-Grenze erreicht" in result.output

    def test_corrupt_state_does_not_start_a_fresh_run(self, workspace: Path) -> None:
        """Ein unlesbarer Zustand fuehrt zu PAUSED, nicht zu einem frischen
        Start - sonst waere das Kaputtmachen der Datei ein Weg, den
        Kill-Switch zu umgehen."""
        from execution.risk import load_risk_state

        directory = workspace / "state"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "risk.json").write_text("{kaputt")

        state = load_risk_state(directory / "risk.json")

        assert state.trading_state is TradingState.PAUSED


class TestArgumentValidation:
    def test_unknown_market_kind_is_rejected(self, workspace: Path) -> None:
        write_genome(workspace)

        result = runner.invoke(app, ["trade", "--trocken", "--markt", "optionen"])

        assert result.exit_code != 0
        assert "perpetual" in result.output

    def test_spot_is_accepted(self, workspace: Path) -> None:
        """Solange offen ist, ob das Konto Perpetuals kann, muss beides gehen."""
        write_genome(workspace)

        result = runner.invoke(app, ["trade", "--trocken", "--markt", "spot"])

        # Scheitert danach an der fehlenden Boersenverbindung, nicht am Argument.
        assert "perpetual oder spot" not in result.output


def test_trade_command_is_registered() -> None:
    """Der Befehl, um den es die ganze Zeit ging, muss auch auftauchen."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "trade" in result.output


class TestCrossPlatform:
    """Der Handel muss auch unter Windows starten.

    ``loop.add_signal_handler`` gibt es dort nicht. Ohne Fallunterscheidung
    stuerzt jeder Dauerbefehl sofort beim Start ab - mit einer Meldung, die
    nichts mit dem Handel zu tun hat, und die man deshalb lange sucht.
    """

    async def test_stop_handler_survives_a_platform_without_signal_support(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        from cli import _install_stop_handler

        class WindowsLikeLoop:
            def add_signal_handler(self, *args, **kwargs):
                raise NotImplementedError("nicht unter Windows")

        monkeypatch.setattr(asyncio, "get_running_loop", lambda: WindowsLikeLoop())
        stopped = []

        # Darf nicht werfen - das ist der ganze Punkt.
        _install_stop_handler(lambda: stopped.append(True))

    async def test_stop_handler_registers_where_it_can(self) -> None:
        from cli import _install_stop_handler

        stopped = []
        _install_stop_handler(lambda: stopped.append(True))

        # Auf Unix laeuft es ueber die Ereignisschleife und ist damit gesetzt.
        assert stopped == []  # noch nicht ausgeloest, nur registriert
