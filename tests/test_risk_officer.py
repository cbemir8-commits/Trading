"""Tests des Risk-Officers.

Die sicherheitskritischste Komponente: Sie ist das Einzige, was zwischen einer
fehlerhaften Strategie und einem leeren Konto steht. Entsprechend wird hier
besonders auf die unangenehmen Faelle geprueft - Neustart mitten im Verlust,
kaputte Zustandsdatei, Kill-Switch.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from core.config import RiskSettings
from core.models import Instrument
from execution.risk import (
    Approved,
    RiskOfficer,
    TradingState,
    Vetoed,
    VetoReason,
)
from tests.factories import make_signal

T0 = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)  # ein Montag


class Clock:
    """Steuerbare Zeit - sonst liessen sich Tages- und Wochengrenzen nicht testen."""

    def __init__(self, now: datetime = T0) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def officer(
    risk: RiskSettings, btcusdt: Instrument, tmp_path: Path, clock: Clock
) -> RiskOfficer:
    return RiskOfficer(risk, btcusdt, state_path=tmp_path / "risk.json", clock=clock)


class TestNormalOperation:
    def test_approves_valid_signal(self, officer: RiskOfficer) -> None:
        officer.observe_equity(Decimal("500"))
        decision = officer.evaluate(make_signal(), equity=Decimal("500"))

        assert isinstance(decision, Approved)
        assert decision.sized.qty > 0
        assert decision.sized.leverage <= officer.settings.max_leverage

    def test_vetoes_when_position_already_open(self, officer: RiskOfficer) -> None:
        officer.observe_equity(Decimal("500"))
        decision = officer.evaluate(make_signal(), equity=Decimal("500"), open_positions=1)

        assert isinstance(decision, Vetoed)
        assert decision.reason is VetoReason.POSITION_ALREADY_OPEN

    def test_vetoes_unsizable_signal(self, officer: RiskOfficer) -> None:
        """Ein zu enger Stop wird abgelehnt, nicht notduerftig gerundet."""
        officer.observe_equity(Decimal("500"))
        decision = officer.evaluate(make_signal(stop_pct="0.02"), equity=Decimal("500"))

        assert isinstance(decision, Vetoed)
        assert decision.reason is VetoReason.SIZING_REJECTED


class TestLossLimits:
    def test_daily_limit_pauses_for_24h(self, officer: RiskOfficer, clock: Clock) -> None:
        officer.observe_equity(Decimal("500"))
        officer.observe_equity(Decimal("483"))  # -3,4 % am Tag

        decision = officer.evaluate(make_signal(), equity=Decimal("483"))
        assert isinstance(decision, Vetoed)
        assert decision.reason is VetoReason.DAILY_LOSS_LIMIT

        clock.advance(hours=25)
        officer.observe_equity(Decimal("483"))
        assert isinstance(officer.evaluate(make_signal(), equity=Decimal("483")), Approved)

    def test_new_day_resets_daily_reference(
        self, officer: RiskOfficer, clock: Clock
    ) -> None:
        """Der Tagesbezug wird um Mitternacht UTC neu gesetzt."""
        officer.observe_equity(Decimal("500"))
        clock.advance(days=1)
        officer.observe_equity(Decimal("490"))

        assert officer.state.day_start_equity == Decimal("490")

    def test_weekly_limit_needs_manual_release(self, officer: RiskOfficer, clock: Clock) -> None:
        """Das Wochenlimit pausiert bis zur manuellen Freigabe - anders als das
        Tageslimit. Wer eine Woche lang verliert, sollte hinsehen."""
        officer.observe_equity(Decimal("500"))
        officer.observe_equity(Decimal("460"))  # -8 % in der Woche

        assert officer.state.trading_state is TradingState.PAUSED

        clock.advance(days=3)
        officer.observe_equity(Decimal("460"))
        decision = officer.evaluate(make_signal(), equity=Decimal("460"))
        assert isinstance(decision, Vetoed)
        assert decision.reason is VetoReason.TRADING_PAUSED

        officer.resume()
        assert isinstance(officer.evaluate(make_signal(), equity=Decimal("460")), Approved)


class TestKillSwitch:
    def test_triggers_at_max_drawdown(self, officer: RiskOfficer) -> None:
        """15 % Rueckgang vom Hoechststand - deine Vorgabe."""
        officer.observe_equity(Decimal("500"))
        officer.observe_equity(Decimal("600"))  # neuer Hoechststand
        assessment = officer.observe_equity(Decimal("508"))  # -15,3 % vom Hoch

        assert assessment.trading_state is TradingState.KILLED
        assert assessment.drawdown_pct > Decimal("15")

    def test_measured_from_peak_not_start(self, officer: RiskOfficer) -> None:
        """Der Drawdown zaehlt ab dem Hoechststand, nicht ab dem Startkapital.

        Ein Konto, das von 500 auf 700 gestiegen und dann auf 600 gefallen ist,
        liegt im Plus - aber 14 % unter seinem Hoch. Das ist die Zahl, die
        zaehlt.
        """
        officer.observe_equity(Decimal("500"))
        officer.observe_equity(Decimal("700"))
        assessment = officer.observe_equity(Decimal("600"))

        assert assessment.drawdown_pct == pytest.approx(Decimal("14.2857"), abs=Decimal("0.01"))
        assert assessment.equity > Decimal("500"), "trotzdem im Plus gegenueber Start"

    def test_resume_does_not_clear_kill_switch(self, officer: RiskOfficer) -> None:
        """``resume()`` darf einen Kill-Switch nicht aufheben.

        Wer ihn ausgeloest hat, soll erst nachsehen was passiert ist - nicht
        versehentlich weiterhandeln.
        """
        officer.trigger_kill_switch("Test")
        officer.resume()

        assert officer.state.trading_state is TradingState.KILLED

    def test_reset_requires_exact_confirmation(self, officer: RiskOfficer) -> None:
        officer.trigger_kill_switch("Test")

        assert not officer.reset_kill_switch(confirm="ja")
        assert officer.state.trading_state is TradingState.KILLED

        assert officer.reset_kill_switch(confirm="ICH HABE DIE URSACHE GEPRUEFT")
        assert officer.state.trading_state is TradingState.ACTIVE

    def test_killed_state_vetoes_everything(self, officer: RiskOfficer) -> None:
        officer.observe_equity(Decimal("500"))
        officer.trigger_kill_switch("Not-Aus vom Dashboard")

        decision = officer.evaluate(make_signal(), equity=Decimal("500"))
        assert isinstance(decision, Vetoed)
        assert decision.reason is VetoReason.KILL_SWITCH
        assert "Not-Aus" in decision.detail


class TestStatePersistence:
    """Der Zustand muss einen Neustart ueberleben.

    Ein Prozess, der nach einem Absturz vergessen hat, dass er heute schon
    3 % verloren hat, handelt munter weiter - genau in dem Moment, in dem
    etwas schiefgelaufen ist.
    """

    def test_daily_limit_survives_restart(
        self, risk: RiskSettings, btcusdt: Instrument, tmp_path: Path, clock: Clock
    ) -> None:
        path = tmp_path / "risk.json"

        first = RiskOfficer(risk, btcusdt, state_path=path, clock=clock)
        first.observe_equity(Decimal("500"))
        first.observe_equity(Decimal("483"))  # Tageslimit gerissen

        # Prozess stirbt, neuer startet.
        second = RiskOfficer(risk, btcusdt, state_path=path, clock=clock)
        decision = second.evaluate(make_signal(), equity=Decimal("483"))

        assert isinstance(decision, Vetoed)
        assert decision.reason is VetoReason.DAILY_LOSS_LIMIT

    def test_kill_switch_survives_restart(
        self, risk: RiskSettings, btcusdt: Instrument, tmp_path: Path, clock: Clock
    ) -> None:
        path = tmp_path / "risk.json"

        first = RiskOfficer(risk, btcusdt, state_path=path, clock=clock)
        first.trigger_kill_switch("Drawdown-Grenze")

        second = RiskOfficer(risk, btcusdt, state_path=path, clock=clock)
        assert second.state.trading_state is TradingState.KILLED

    def test_equity_peak_survives_restart(
        self, risk: RiskSettings, btcusdt: Instrument, tmp_path: Path, clock: Clock
    ) -> None:
        """Ohne den Hoechststand wuerde der Drawdown nach jedem Neustart bei
        null beginnen - der Kill-Switch waere praktisch abgeschaltet."""
        path = tmp_path / "risk.json"

        first = RiskOfficer(risk, btcusdt, state_path=path, clock=clock)
        first.observe_equity(Decimal("500"))
        first.observe_equity(Decimal("700"))

        second = RiskOfficer(risk, btcusdt, state_path=path, clock=clock)
        assert second.state.equity_peak == Decimal("700")

        assessment = second.observe_equity(Decimal("600"))
        assert assessment.drawdown_pct > Decimal("14")

    def test_corrupt_state_pauses_instead_of_trading(
        self, risk: RiskSettings, btcusdt: Instrument, tmp_path: Path
    ) -> None:
        """Ein kaputter Zustand darf nicht zu unbegrenztem Handeln fuehren.

        Im Zweifel stillstehen und den Menschen entscheiden lassen - die
        Alternative waere ein System, das mit zurueckgesetzten Verlustgrenzen
        weiterhandelt.
        """
        path = tmp_path / "risk.json"
        path.write_text("{ das ist kein gueltiges JSON")

        officer = RiskOfficer(risk, btcusdt, state_path=path)
        assert officer.state.trading_state is TradingState.PAUSED

        decision = officer.evaluate(make_signal(), equity=Decimal("500"))
        assert isinstance(decision, Vetoed)

    def test_write_is_atomic(
        self, risk: RiskSettings, btcusdt: Instrument, tmp_path: Path
    ) -> None:
        """Erst Nebendatei, dann umbenennen - ein Absturz mitten im Schreiben
        darf keine halbe Datei hinterlassen."""
        path = tmp_path / "risk.json"
        officer = RiskOfficer(risk, btcusdt, state_path=path)
        officer.observe_equity(Decimal("500"))

        assert path.exists()
        assert not path.with_suffix(".tmp").exists()
        assert json.loads(path.read_text())["equity_peak"] == "500"


class TestManualControls:
    def test_pause_and_resume(self, officer: RiskOfficer) -> None:
        officer.observe_equity(Decimal("500"))
        officer.pause("Wartung")

        assert isinstance(officer.evaluate(make_signal(), equity=Decimal("500")), Vetoed)
        officer.resume()
        assert isinstance(officer.evaluate(make_signal(), equity=Decimal("500")), Approved)

    def test_close_only_blocks_new_positions(self, officer: RiskOfficer) -> None:
        officer.observe_equity(Decimal("500"))
        officer.close_only()

        decision = officer.evaluate(make_signal(), equity=Decimal("500"))
        assert isinstance(decision, Vetoed)
        assert decision.reason is VetoReason.CLOSE_ONLY_MODE

    def test_news_blackout_blocks_entries(self, officer: RiskOfficer, clock: Clock) -> None:
        """Vor einem wichtigen Termin keine neuen Positionen."""
        officer.observe_equity(Decimal("500"))
        officer.set_news_blackout(clock.now + timedelta(minutes=45), reason="FOMC")

        decision = officer.evaluate(make_signal(), equity=Decimal("500"))
        assert isinstance(decision, Vetoed)
        assert decision.reason is VetoReason.NEWS_BLACKOUT

        clock.advance(minutes=50)
        assert isinstance(officer.evaluate(make_signal(), equity=Decimal("500")), Approved)


class TestRiskAssessment:
    def test_headroom_to_kill_switch(self, officer: RiskOfficer) -> None:
        """Wie viel Luft bleibt bis zur Abschaltung - fuers Dashboard."""
        officer.observe_equity(Decimal("500"))
        assessment = officer.observe_equity(Decimal("475"))  # -5 %

        assert assessment.drawdown_pct == pytest.approx(Decimal("5"))
        assert assessment.drawdown_headroom_pct == pytest.approx(Decimal("10"))
