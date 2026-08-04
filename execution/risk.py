"""Der Risk-Officer.

Die einzige Stelle im System mit Vetorecht. Kein Signal wird ausgefuehrt, ohne
hier durchzugehen - und die Grenzen stehen in der Konfiguration, nicht im
Prompt der KI. Die Research-KI sieht sie als Kontext, kann sie aber nicht
aendern.

**Der Zustand wird auf die Platte geschrieben.** Das ist kein Komfort, sondern
notwendig: Ein Prozess, der nach einem Absturz neu startet und vergessen hat,
dass er heute schon 3 % verloren hat, handelt munter weiter und reisst das
Tageslimit. Genau in dem Moment, in dem etwas schiefgelaeuft ist, muss die
Bremse noch wissen, dass sie schon getreten wurde.

Reihenfolge der Pruefungen - von der haertesten zur mildesten:

1. Kill-Switch (maximaler Drawdown)   -> System aus, nur manuell zurueckholbar
2. Wochenverlustlimit                 -> aus bis zur manuellen Freigabe
3. Tagesverlustlimit                  -> 24 Stunden Pause
4. Handel manuell pausiert            -> bis zur Freigabe
5. Position bereits offen             -> ein Signal zur Zeit
6. Positionsgroesse berechenbar       -> siehe execution.sizing
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import structlog

from core.config import RiskSettings
from core.models import Instrument, Signal
from execution.sizing import SizedPosition, SizingRejected, size_position

log = structlog.get_logger(__name__)


class TradingState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    """Manuell pausiert - bestehende Positionen laufen weiter, keine neuen."""

    CLOSE_ONLY = "close_only"
    """Nur noch schliessen - fuer geordneten Rueckzug."""

    KILLED = "killed"
    """Kill-Switch ausgeloest. Nur manuell zurueckholbar, absichtlich."""


class VetoReason(StrEnum):
    KILL_SWITCH = "kill_switch"
    WEEKLY_LOSS_LIMIT = "weekly_loss_limit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    TRADING_PAUSED = "trading_paused"
    CLOSE_ONLY_MODE = "close_only"
    POSITION_ALREADY_OPEN = "position_already_open"
    MAX_POSITIONS = "max_positions"
    SIZING_REJECTED = "sizing_rejected"
    NEWS_BLACKOUT = "news_blackout"


@dataclass(frozen=True, slots=True)
class Approved:
    sized: SizedPosition


@dataclass(frozen=True, slots=True)
class Vetoed:
    reason: VetoReason
    detail: str

    def describe(self) -> str:
        return f"{self.reason.value}: {self.detail}"


Decision = Approved | Vetoed


@dataclass(slots=True)
class RiskState:
    """Der Zustand, der einen Neustart ueberleben muss."""

    trading_state: TradingState = TradingState.ACTIVE
    equity_peak: Decimal = Decimal(0)
    day: date | None = None
    day_start_equity: Decimal = Decimal(0)
    week_start: date | None = None
    week_start_equity: Decimal = Decimal(0)
    paused_until: datetime | None = None
    killed_at: datetime | None = None
    kill_reason: str = ""
    news_blackout_until: datetime | None = None

    def to_json(self) -> dict:
        return {
            "trading_state": self.trading_state.value,
            "equity_peak": str(self.equity_peak),
            "day": self.day.isoformat() if self.day else None,
            "day_start_equity": str(self.day_start_equity),
            "week_start": self.week_start.isoformat() if self.week_start else None,
            "week_start_equity": str(self.week_start_equity),
            "paused_until": self.paused_until.isoformat() if self.paused_until else None,
            "killed_at": self.killed_at.isoformat() if self.killed_at else None,
            "kill_reason": self.kill_reason,
            "news_blackout_until": (
                self.news_blackout_until.isoformat() if self.news_blackout_until else None
            ),
        }

    @classmethod
    def from_json(cls, data: dict) -> RiskState:
        def parse_dt(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value else None

        def parse_date(value: str | None) -> date | None:
            return date.fromisoformat(value) if value else None

        return cls(
            trading_state=TradingState(data.get("trading_state", "active")),
            equity_peak=Decimal(data.get("equity_peak", "0")),
            day=parse_date(data.get("day")),
            day_start_equity=Decimal(data.get("day_start_equity", "0")),
            week_start=parse_date(data.get("week_start")),
            week_start_equity=Decimal(data.get("week_start_equity", "0")),
            paused_until=parse_dt(data.get("paused_until")),
            killed_at=parse_dt(data.get("killed_at")),
            kill_reason=data.get("kill_reason", ""),
            news_blackout_until=parse_dt(data.get("news_blackout_until")),
        )


def load_risk_state(path: Path | str | None) -> RiskState:
    """Zustand von der Platte lesen, ohne einen Risk-Officer zu bauen.

    Wird von der Kommandozeile gebraucht: Ob der Kill-Switch aktiv ist, muss
    feststehen, **bevor** eine Verbindung zur Boerse aufgebaut wird. Ein
    abgeschaltetes System soll sich nicht erst noch anmelden.

    Ein unlesbarer Zustand fuehrt zu PAUSED, nicht zu einem frischen Start:
    Im Zweifel stillstehen, der Mensch entscheidet.
    """
    if path is None:
        return RiskState()
    file = Path(path)
    if not file.exists():
        return RiskState()
    try:
        return RiskState.from_json(json.loads(file.read_text()))
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        log.error(
            "risk.zustand_unlesbar",
            fehler=str(exc),
            pfad=str(file),
            massnahme="Handel pausiert, bis der Zustand geprueft wurde",
        )
        return RiskState(trading_state=TradingState.PAUSED)


@dataclass(slots=True)
class RiskAssessment:
    """Momentaufnahme der Risikolage - fuer Dashboard und Protokoll."""

    equity: Decimal
    equity_peak: Decimal
    drawdown_pct: Decimal
    day_pnl_pct: Decimal
    week_pnl_pct: Decimal
    trading_state: TradingState
    open_positions: int

    @property
    def drawdown_headroom_pct(self) -> Decimal:
        """Wie viel Prozentpunkte bis zum Kill-Switch."""
        return max(Decimal(0), Decimal(15) - self.drawdown_pct)


class RiskOfficer:
    """Prueft jedes Signal und ueberwacht die Verlustgrenzen."""

    def __init__(
        self,
        settings: RiskSettings,
        instrument: Instrument,
        *,
        state_path: Path | str | None = None,
        clock=None,
    ) -> None:
        self.settings = settings
        self.instrument = instrument
        self.state_path = Path(state_path) if state_path else None
        self.clock = clock or (lambda: datetime.now(UTC))
        self.state = self._load_state()

    # -- Zustandshaltung -----------------------------------------------------
    def _load_state(self) -> RiskState:
        state = load_risk_state(self.state_path)
        if self.state_path is not None and self.state_path.exists():
            log.info(
                "risk.zustand_geladen",
                zustand=state.trading_state.value,
                hoechststand=str(state.equity_peak),
            )
        return state

    def save(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        # Erst in eine Nebendatei schreiben, dann umbenennen: Ein Absturz
        # mitten im Schreiben hinterlaesst sonst eine halbe Datei - und die
        # waere beim naechsten Start unlesbar.
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state.to_json(), indent=2))
        temporary.replace(self.state_path)

    # -- Buchfuehrung --------------------------------------------------------
    def observe_equity(self, equity: Decimal) -> RiskAssessment:
        """Kapitalstand melden und die Verlustgrenzen pruefen.

        Muss regelmaessig aufgerufen werden, nicht nur bei Signalen: Der
        Kill-Switch soll auch dann greifen, wenn eine offene Position ins Minus
        laeuft und gerade kein neues Signal ansteht.
        """
        now = self.clock()
        today = now.date()

        if self.state.day != today:
            self.state.day = today
            self.state.day_start_equity = equity

        monday = today - timedelta(days=today.weekday())
        if self.state.week_start != monday:
            self.state.week_start = monday
            self.state.week_start_equity = equity

        if equity > self.state.equity_peak:
            self.state.equity_peak = equity

        drawdown = self._pct_change(self.state.equity_peak, equity, negative_only=True)
        day_pnl = self._pct_change(self.state.day_start_equity, equity)
        week_pnl = self._pct_change(self.state.week_start_equity, equity)

        self._enforce_limits(equity, drawdown, day_pnl, week_pnl, now)
        self.save()

        return RiskAssessment(
            equity=equity,
            equity_peak=self.state.equity_peak,
            drawdown_pct=drawdown,
            day_pnl_pct=day_pnl,
            week_pnl_pct=week_pnl,
            trading_state=self.state.trading_state,
            open_positions=0,
        )

    def _enforce_limits(
        self,
        equity: Decimal,
        drawdown: Decimal,
        day_pnl: Decimal,
        week_pnl: Decimal,
        now: datetime,
    ) -> None:
        if self.state.trading_state is TradingState.KILLED:
            return

        if drawdown >= self.settings.max_drawdown_pct:
            self.state.trading_state = TradingState.KILLED
            self.state.killed_at = now
            self.state.kill_reason = (
                f"Drawdown {drawdown:.2f} % hat die Grenze von "
                f"{self.settings.max_drawdown_pct} % erreicht"
            )
            log.critical(
                "risk.kill_switch",
                drawdown_pct=float(drawdown),
                kapital=str(equity),
                hoechststand=str(self.state.equity_peak),
                hinweis="Alles glattstellen. Nur manuell zurueckholbar.",
            )
            return

        if week_pnl <= -self.settings.weekly_loss_limit_pct:
            if self.state.trading_state is not TradingState.PAUSED:
                self.state.trading_state = TradingState.PAUSED
                self.state.paused_until = None  # bis zur manuellen Freigabe
                log.error("risk.wochenlimit", verlust_pct=float(week_pnl))
            return

        # Nur eine neue Pause setzen, wenn keine laufende besteht - sonst
        # wuerde sich die Sperre bei jeder Kerze um weitere 24 Stunden
        # verlaengern und nie ablaufen.
        already_paused = (
            self.state.paused_until is not None and self.state.paused_until >= now
        )
        if day_pnl <= -self.settings.daily_loss_limit_pct and not already_paused:
            self.state.paused_until = now + timedelta(hours=24)
            log.warning(
                "risk.tageslimit",
                verlust_pct=float(day_pnl),
                pause_bis=self.state.paused_until.isoformat(),
            )

    @staticmethod
    def _pct_change(
        reference: Decimal, current: Decimal, *, negative_only: bool = False
    ) -> Decimal:
        if reference <= 0:
            return Decimal(0)
        change = (current - reference) / reference * Decimal(100)
        return -change if negative_only else change

    # -- Signalpruefung ------------------------------------------------------
    def evaluate(
        self,
        signal: Signal,
        *,
        equity: Decimal,
        open_positions: int = 0,
        equity_fraction: Decimal | None = None,
    ) -> Decision:
        """Darf dieses Signal gehandelt werden - und wenn ja, wie gross?

        ``equity_fraction`` reicht die Betriebsart der Strategie durch. Sie muss
        hier ankommen und nicht nur im Backtest: Rechnete der Betrieb nach der
        Risikoformel, waehrend die Zulassung nach Kapitalanteil gerechnet hat,
        haette die gehandelte Strategie mit der geprueften nichts mehr zu tun."""
        now = self.clock()

        if self.state.trading_state is TradingState.KILLED:
            return Vetoed(
                VetoReason.KILL_SWITCH,
                self.state.kill_reason or "Kill-Switch aktiv - nur manuell zurueckholbar",
            )

        if self.state.trading_state is TradingState.CLOSE_ONLY:
            return Vetoed(
                VetoReason.CLOSE_ONLY_MODE,
                "Nur-Schliessen-Modus - keine neuen Positionen",
            )

        if self.state.trading_state is TradingState.PAUSED:
            return Vetoed(VetoReason.TRADING_PAUSED, "Handel manuell pausiert")

        if self.state.paused_until is not None and now < self.state.paused_until:
            remaining = self.state.paused_until - now
            return Vetoed(
                VetoReason.DAILY_LOSS_LIMIT,
                f"Tageslimit erreicht, Pause noch {remaining.total_seconds() / 3600:.1f} h",
            )

        if (
            self.state.news_blackout_until is not None
            and now < self.state.news_blackout_until
        ):
            remaining = self.state.news_blackout_until - now
            return Vetoed(
                VetoReason.NEWS_BLACKOUT,
                f"Wichtiges Ereignis steht bevor, Sperre noch "
                f"{remaining.total_seconds() / 60:.0f} min",
            )

        if open_positions >= self.settings.max_concurrent_positions:
            return Vetoed(
                VetoReason.POSITION_ALREADY_OPEN,
                f"{open_positions} von maximal "
                f"{self.settings.max_concurrent_positions} Positionen offen",
            )

        sized = size_position(
            signal,
            equity=equity,
            instrument=self.instrument,
            risk=self.settings,
            equity_fraction=equity_fraction,
        )
        if isinstance(sized, SizingRejected):
            return Vetoed(VetoReason.SIZING_REJECTED, sized.detail)

        return Approved(sized)

    # -- Manuelle Steuerung --------------------------------------------------
    def pause(self, reason: str = "") -> None:
        self.state.trading_state = TradingState.PAUSED
        self.save()
        log.warning("risk.pausiert", grund=reason)

    def resume(self) -> None:
        """Handel wieder freigeben.

        Setzt den Kill-Switch bewusst **nicht** zurueck: Wer ihn ausgeloest hat,
        soll erst nachsehen, was passiert ist. Dafuer gibt es ``reset_kill_switch``.
        """
        if self.state.trading_state is TradingState.KILLED:
            log.error(
                "risk.fortsetzen_abgelehnt",
                hinweis="Kill-Switch ist aktiv. Erst pruefen, dann reset_kill_switch().",
            )
            return
        self.state.trading_state = TradingState.ACTIVE
        self.state.paused_until = None
        self.save()
        log.info("risk.fortgesetzt")

    def close_only(self) -> None:
        self.state.trading_state = TradingState.CLOSE_ONLY
        self.save()

    def trigger_kill_switch(self, reason: str) -> None:
        """Not-Aus, auch manuell vom Dashboard aus."""
        self.state.trading_state = TradingState.KILLED
        self.state.killed_at = self.clock()
        self.state.kill_reason = reason
        self.save()
        log.critical("risk.kill_switch_manuell", grund=reason)

    def reset_kill_switch(self, *, confirm: str) -> bool:
        """Kill-Switch zuruecksetzen - nur mit ausdruecklicher Bestaetigung.

        Die Bestaetigungszeichenkette ist Absicht: Ein versehentlicher Klick
        soll ein System nicht wieder scharf schalten, das sich gerade selbst
        abgeschaltet hat.
        """
        if confirm != "ICH HABE DIE URSACHE GEPRUEFT":
            log.error("risk.reset_abgelehnt", hinweis="Bestaetigung stimmt nicht")
            return False
        self.state.trading_state = TradingState.ACTIVE
        self.state.killed_at = None
        self.state.kill_reason = ""
        self.state.equity_peak = Decimal(0)  # Hoechststand neu setzen
        self.save()
        log.warning("risk.kill_switch_zurueckgesetzt")
        return True

    def set_news_blackout(self, until: datetime, reason: str = "") -> None:
        """Sperre vor einem wichtigen Termin setzen."""
        self.state.news_blackout_until = until
        self.save()
        log.info("risk.nachrichtensperre", bis=until.isoformat(), grund=reason)
