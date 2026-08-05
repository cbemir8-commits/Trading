"""Die Live-Schleife - hier wird tatsaechlich gehandelt.

Ablauf je abgeschlossener Kerze:

    Kerze (confirm: true)
        -> in den gleitenden Datenpuffer
        -> Strategie fragen
        -> Risk-Officer fragen  (VETO moeglich)
        -> Order-Router
        -> Bybit
        -> Telegram

**Kein LLM in dieser Schleife.** Was hier laeuft, ist derselbe deterministische
Code wie im Backtest - deshalb sind Backtest und Livebetrieb ueberhaupt
vergleichbar.

Drei Eigenschaften, die den Unterschied zwischen Spielzeug und Betrieb machen:

* **Zustandsabgleich beim Start.** Der Prozess kann jederzeit sterben und neu
  starten. Beim Start wird gefragt: Habe ich eine offene Position? Liegen noch
  Orders? Passt der Stop? Ein Prozess, der das nicht tut, eroeffnet nach einem
  Neustart eine zweite Position neben der ersten.
* **Kapitalstand wird laufend gemeldet**, nicht nur bei Signalen. Der
  Kill-Switch muss auch greifen, wenn eine offene Position ins Minus laeuft und
  gerade kein Signal ansteht.
* **Der Stop liegt an der Position**, nicht in diesem Prozess. Faellt die
  Schleife aus, bleibt der Schutz bestehen.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import structlog

from core.config import BybitSettings, RiskSettings
from core.models import Candle, Instrument, Interval, Position, Side, Trade
from data.bybit.adapter import AccountSource, MarketDataSource
from data.bybit.trading import TradingGateway
from data.bybit.ws import KlineStream
from data.store import CandleStore, candles_to_frame
from execution.risk import Approved, RiskOfficer, TradingState, Vetoed
from execution.router import Bracket, BracketState, MarketKind, OrderRouter
from strategy.base import BarContext, Strategy, frame_to_arrays
from web.journal import CommandAction, EventKind, LiveJournal

log = structlog.get_logger(__name__)

#: Wie viele Kerzen im Speicher gehalten werden. Muss die laengste
#: Indikatorperiode deutlich uebersteigen; 2000 deckt auch EMA(400) ab.
BUFFER_BARS = 2000

Notifier = Callable[[str], Awaitable[None]]


@dataclass(slots=True)
class LiveStats:
    """Betriebszahlen - fuer Dashboard und Abschlussbericht."""

    candles_seen: int = 0
    signals_generated: int = 0
    signals_vetoed: int = 0
    entries_placed: int = 0
    entries_filled: int = 0
    entries_expired: int = 0
    veto_reasons: dict[str, int] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def count_veto(self, reason: str) -> None:
        self.signals_vetoed += 1
        self.veto_reasons[reason] = self.veto_reasons.get(reason, 0) + 1

    def describe(self) -> str:
        runtime = datetime.now(UTC) - self.started_at
        return (
            f"{self.candles_seen} Kerzen, {self.signals_generated} Signale, "
            f"{self.entries_filled} Einstiege, {self.signals_vetoed} abgelehnt "
            f"({runtime.total_seconds() / 3600:.1f} h Laufzeit)"
        )


class LiveTrader:
    """Der Handelsroboter."""

    def __init__(
        self,
        *,
        settings: BybitSettings,
        strategy: Strategy,
        instrument: Instrument,
        risk_settings: RiskSettings,
        market: MarketDataSource,
        account: AccountSource,
        gateway: TradingGateway,
        officer: RiskOfficer,
        store: CandleStore,
        interval: Interval = Interval.M15,
        market_kind: MarketKind = MarketKind.PERPETUAL,
        notifier: Notifier | None = None,
        entry_expiry_bars: int = 3,
        journal: LiveJournal | None = None,
    ) -> None:
        self.settings = settings
        self.strategy = strategy
        self.instrument = instrument
        self.market = market
        self.account = account
        self.officer = officer
        self.store = store
        self.interval = interval
        self.entry_expiry_bars = entry_expiry_bars
        self.notifier = notifier
        self.journal = journal
        self.risk_settings = risk_settings

        self.router = OrderRouter(
            gateway, instrument, risk_settings, market_kind=market_kind
        )
        self.stats = LiveStats()
        self.bracket: Bracket | None = None
        self.last_equity: Decimal = Decimal(0)
        self.equity_at_entry: Decimal = Decimal(0)
        self._mae: Decimal = Decimal(0)
        self._mfe: Decimal = Decimal(0)
        self._frame: pd.DataFrame = pd.DataFrame()
        self._bars_since_entry_placed = 0
        self._stream: KlineStream | None = None

    # -- Start ---------------------------------------------------------------
    async def start(self) -> None:
        """Vorbereiten und dann bis zum Stopp handeln."""
        await self._reconcile()
        self._load_history()

        self._stream = KlineStream(
            self.settings, [self.interval], on_candle=self._on_candle
        )
        await self._notify(
            f"Handelsroboter gestartet\n"
            f"{self.instrument.symbol} {self.interval.label}\n"
            f"Strategie: {self.strategy.strategy_id}\n"
            f"Umgebung: {self.settings.environment.value}"
        )
        self._report(
            EventKind.START,
            f"Handelsroboter gestartet - {self.instrument.symbol} "
            f"{self.interval.label}, Strategie {self.strategy.strategy_id}, "
            f"Umgebung {self.settings.environment.value}",
            symbol=self.instrument.symbol,
            environment=self.settings.environment.value,
        )
        log.info(
            "live.gestartet",
            symbol=self.instrument.symbol,
            intervall=self.interval.label,
            strategie=self.strategy.strategy_id,
            umgebung=self.settings.environment.value,
        )
        await self._stream.run()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()

    async def _reconcile(self) -> None:
        """Zustandsabgleich beim Start.

        Ohne diesen Schritt eroeffnet ein neu gestarteter Prozess eine zweite
        Position neben der bestehenden - und die erste laeuft unbeaufsichtigt
        weiter. Das ist der haeufigste Weg, wie ein Handelsroboter ueber Nacht
        aus dem Ruder laeuft.
        """
        position = self._first_position()
        if position is None:
            # Verwaiste Orders aus einem frueheren Lauf entfernen.
            self.router.close_all("Aufraeumen beim Start - keine offene Position")
            return

        log.warning(
            "live.offene_position_gefunden",
            seite=position.side.value,
            groesse=str(position.size),
            einstieg=str(position.entry_price),
            stop=str(position.stop_loss) if position.stop_loss else None,
        )

        if position.stop_loss is None or position.stop_loss == 0:
            # Position ohne Stop ist der gefaehrlichste Zustand ueberhaupt.
            await self._notify(
                "WARNUNG: Offene Position ohne Stop gefunden. "
                "Sie wird sofort geschlossen."
            )
            self._report(
                EventKind.WARNING,
                f"Offene Position ohne Stop gefunden ({position.side.value} "
                f"{position.size}) - wird sofort geschlossen",
            )
            log.critical(
                "live.position_ohne_stop",
                massnahme="Wird geschlossen - ungeschuetzte Position ist nicht tragbar",
            )
            self.router.gateway.place_market(
                symbol=self.instrument.symbol,
                side=position.side.opposite,
                qty=position.size,
                reduce_only=True,
            )
            self.router.close_all("Ungeschuetzte Position geschlossen")
            return

        await self._notify(
            f"Offene Position uebernommen: {position.side.value} {position.size} "
            f"@ {position.entry_price}, Stop {position.stop_loss}"
        )

    def _load_history(self) -> None:
        """Kerzen aus dem Speicher laden, damit Indikatoren sofort greifen.

        Ohne Vorlauf braeuchte die Strategie je nach Periode Stunden bis Tage,
        bis sie das erste Signal geben kann.
        """
        frame = self.store.read(self.instrument.symbol, self.interval)
        if frame.empty:
            log.warning(
                "live.kein_verlauf",
                hinweis="Erst 'python -m cli backfill' ausfuehren, sonst dauert es, "
                "bis die Indikatoren eingeschwungen sind.",
            )
            self._frame = frame
            return

        self._frame = frame.tail(BUFFER_BARS).reset_index(drop=True)
        log.info(
            "live.verlauf_geladen",
            kerzen=len(self._frame),
            bis=str(self._frame["open_time"].iloc[-1]),
        )

    # -- Hauptschleife -------------------------------------------------------
    async def _on_candle(self, candle: Candle, interval: Interval) -> None:
        """Eine bestaetigte Kerze ist eingetroffen."""
        if interval is not self.interval:
            return

        self.stats.candles_seen += 1
        # Ein Schreibfehler im Datenspeicher darf den Handel nicht stoppen -
        # Kerzen lassen sich jederzeit nachladen, eine offene Position nicht.
        with contextlib.suppress(Exception):
            self.store.write(self.instrument.symbol, interval, [candle])
        self._append(candle)

        equity = self._current_equity()
        self.last_equity = equity
        assessment = self.officer.observe_equity(equity)

        # Erst der Befehl vom Dashboard, dann alles andere: Ein Not-Aus vom
        # Telefon soll nicht warten, bis die Strategie ihre Meinung gebildet hat.
        await self._handle_commands()

        if self.officer.state.trading_state is TradingState.KILLED:
            await self._handle_kill_switch()
            self._publish(assessment)
            return

        self._track_excursion(candle)
        await self._manage_open_position()

        # **Nur wenn gar kein Bracket offen ist.** Ein Bracket im Zustand
        # PENDING_ENTRY ist zwar nicht ``is_open`` - es wartet ja noch auf den
        # Fill -, aber es liegt bereits eine Einstiegsorder im Markt. Wer hier
        # auf ``is_open`` prueft, legt bei jedem Signal eine zweite dazu.
        if self.bracket is None:
            await self._look_for_entry()

        self._publish(assessment, candle=candle)

    # -- Dashboard -----------------------------------------------------------
    def _report(self, kind: EventKind, message: str, **data) -> None:
        """Ein Ereignis ans Dashboard melden.

        Wie beim Benachrichtigungsdienst gilt: Ein Fehler beim Berichten darf
        den Handel nie stoppen. Das Dashboard ist Beobachtung, nicht Steuerung.
        """
        if self.journal is None:
            return
        with contextlib.suppress(Exception):
            self.journal.record(kind, message, **data)

    def _publish(self, assessment, candle: Candle | None = None) -> None:
        """Die Momentaufnahme fuer die Website schreiben - inklusive Herzschlag.

        Bei **jeder** Kerze, auch wenn nichts passiert ist. Der Herzschlag ist
        die einzige Art, wie das Dashboard zwischen "nichts zu tun" und
        "Prozess tot" unterscheiden kann.
        """
        if self.journal is None:
            return
        with contextlib.suppress(Exception):
            self.journal.write_snapshot(self._snapshot(assessment, candle))

    def _snapshot(self, assessment, candle: Candle | None = None) -> dict:
        position = None
        if self.bracket is not None and self.bracket.is_open:
            position = {
                "side": self.bracket.signal.side.value,
                "qty": self.bracket.remaining_qty,
                "entry_price": self.bracket.entry_price,
                "stop_price": self.bracket.stop_price,
                "targets_hit": self.bracket.targets_hit,
                "at_breakeven": self.bracket.moved_to_breakeven,
                "description": self.bracket.describe(),
                "opened_at": self.bracket.opened_at,
                "protected": self.bracket.is_protected,
                # Ohne diese beiden ist die Position auf dem Bildschirm eine
                # Zeile ohne Aussage: Man sieht, dass etwas offen ist, aber
                # nicht, wie es steht und wohin es laufen soll.
                "take_profits": self._take_profit_levels(),
                "unrealized": self._unrealized(candle),
            }
        elif self.bracket is not None:
            position = {"pending": self.bracket.describe()}

        return {
            "symbol": self.instrument.symbol,
            "interval": self.interval.label,
            "environment": self.settings.environment.value,
            "real_money": self.settings.environment.is_real_money,
            "strategy_id": self.strategy.strategy_id,
            "equity": assessment.equity,
            "equity_peak": assessment.equity_peak,
            "drawdown_pct": assessment.drawdown_pct,
            "day_pnl_pct": assessment.day_pnl_pct,
            "week_pnl_pct": assessment.week_pnl_pct,
            # Nicht aus der Bewertung: Die entstand vor den Dashboard-Befehlen
            # und wuesste von einer soeben ausgeloesten Pause nichts.
            "trading_state": self.officer.state.trading_state.value,
            "kill_reason": self.officer.state.kill_reason,
            "last_price": candle.close if candle else None,
            "last_candle": candle.open_time if candle else None,
            "position": position,
            "stats": {
                "candles_seen": self.stats.candles_seen,
                "signals_generated": self.stats.signals_generated,
                "signals_vetoed": self.stats.signals_vetoed,
                "entries_placed": self.stats.entries_placed,
                "entries_filled": self.stats.entries_filled,
                "entries_expired": self.stats.entries_expired,
                "veto_reasons": self.stats.veto_reasons,
                "started_at": self.stats.started_at,
                "summary": self.stats.describe(),
            },
        }

    def _take_profit_levels(self) -> list[dict]:
        """Die Ziele der offenen Position - Preis, Anteil, erreicht ja/nein.

        Genommen wird das **Signal**, nicht die Orderliste der Boerse: Eine
        erreichte Teilorder verschwindet dort, und dann fehlte auf dem
        Bildschirm ausgerechnet das Ziel, das gerade gegriffen hat.
        """
        if self.bracket is None:
            return []
        return [
            {
                "price": leg.price,
                "portion": leg.portion,
                "erreicht": nummer <= self.bracket.targets_hit,
            }
            for nummer, leg in enumerate(self.bracket.signal.take_profits, start=1)
        ]

    def _unrealized(self, candle: Candle | None) -> dict | None:
        """Schwebender Gewinn der offenen Position.

        ``None``, solange kein aktueller Preis vorliegt - eine Zahl aus dem
        Einstiegskurs gegen sich selbst waere immer null und damit eine
        Falschaussage statt einer fehlenden Angabe.

        Gerechnet wird brutto: Die Gebuehren des Ausstiegs stehen noch nicht
        fest, weil noch nicht feststeht, wie ausgestiegen wird.
        """
        bracket = self.bracket
        if bracket is None or candle is None or bracket.entry_price is None:
            return None
        if bracket.remaining_qty <= 0:
            return None

        richtung = Decimal(1) if bracket.signal.side is Side.BUY else Decimal(-1)
        pnl = (candle.close - bracket.entry_price) * bracket.remaining_qty * richtung
        einsatz = bracket.entry_price * bracket.remaining_qty
        prozent = (pnl / einsatz * Decimal(100)) if einsatz > 0 else Decimal(0)

        # Abstand zum Stop in Prozent - die Zahl, die im Betrieb zaehlt.
        abstand = None
        if bracket.stop_price is not None and candle.close > 0:
            abstand = abs(candle.close - bracket.stop_price) / candle.close * Decimal(100)

        return {
            "pnl": pnl,
            "pnl_pct": prozent,
            "preis": candle.close,
            "stop_abstand_pct": abstand,
        }

    async def _handle_commands(self) -> None:
        """Anweisungen vom Dashboard ausfuehren.

        Der Rueckkanal vom Telefon. Bewusst als Abholung statt als offene
        Verbindung: Ein abgestuerztes Dashboard soll den Handel nicht
        beruehren, und ein Befehl soll einen Neustart des Handels ueberleben.
        """
        if self.journal is None:
            return

        command = None
        with contextlib.suppress(Exception):
            command = self.journal.take_command()
        if command is None:
            return

        log.warning("live.befehl", befehl=command.action.value, grund=command.reason)
        self._report(
            EventKind.COMMAND,
            f"Anweisung vom Dashboard: {command.action.value}",
            reason=command.reason,
        )

        if command.action is CommandAction.PAUSE:
            self.officer.pause(command.reason or "vom Dashboard pausiert")
            await self._notify("Handel pausiert. Offene Positionen laufen weiter.")

        elif command.action is CommandAction.RESUME:
            self.officer.resume()
            await self._notify("Handel fortgesetzt.")

        elif command.action is CommandAction.CLOSE_ALL:
            await self._close_everything("Vom Dashboard geschlossen")
            self.officer.pause("nach Glattstellung pausiert")
            await self._notify("Alles glattgestellt. Handel pausiert.")

        elif command.action is CommandAction.KILL:
            # Nur den Schalter umlegen. Das Schliessen uebernimmt die Pruefung
            # gleich danach in ``_on_candle`` - sonst laeuft der Notausstieg
            # zweimal.
            self.officer.trigger_kill_switch(
                command.reason or "Not-Aus vom Dashboard"
            )

    async def _close_everything(self, reason: str) -> None:
        if self.bracket is not None and self.bracket.is_open:
            self.router.emergency_close(self.bracket, reason=reason)
        else:
            self.router.close_all(reason)
        self.bracket = None

    def _append(self, candle: Candle) -> None:
        row = candles_to_frame([candle])
        if self._frame.empty:
            self._frame = row
            return
        last = self._frame["open_time"].iloc[-1]
        if row["open_time"].iloc[0] <= last:
            return  # schon vorhanden
        self._frame = (
            pd.concat([self._frame, row], ignore_index=True)
            .tail(BUFFER_BARS)
            .reset_index(drop=True)
        )

    def _current_equity(self) -> Decimal:
        """Kapital, mit dem gerechnet wird - gegebenenfalls gedeckelt.

        Der Deckel ist fuer die Demo gedacht: Bybit haendigt dort gerne 50.000
        USDT Spielgeld aus. Ohne ihn wuerde die Demo Positionen im
        hundertfachen Umfang des geplanten Kontos eroeffnen und ausgerechnet
        die Grenzen nie beruehren, an denen es spaeter scheitern koennte.
        """
        balance = self.account.get_wallet_balance("USDT")
        cap = self.risk_settings.equity_cap
        if cap > 0 and balance.equity > cap:
            return cap
        return balance.equity

    async def _handle_kill_switch(self) -> None:
        if self.bracket is not None and self.bracket.is_open:
            self.router.emergency_close(self.bracket, reason="Kill-Switch")
        else:
            self.router.close_all("Kill-Switch")

        self._report(
            EventKind.KILL,
            f"KILL-SWITCH: {self.officer.state.kill_reason}",
            equity=self.last_equity,
        )
        await self._notify(
            f"KILL-SWITCH AUSGELOEST\n{self.officer.state.kill_reason}\n"
            "Alles glattgestellt. Handel gestoppt bis zur manuellen Freigabe."
        )
        self.stop()

    async def _manage_open_position(self) -> None:
        """Fills gegen die Boerse abgleichen.

        Der Router weiss nicht von sich aus, ob eine Order gefuellt wurde -
        das erfaehrt er nur durch Nachfragen. Ein Abgleich je Kerze reicht,
        weil Stop und Ziele boersenseitig liegen und ohne uns funktionieren.
        """
        if self.bracket is None:
            return

        if self.bracket.state is BracketState.PENDING_ENTRY:
            await self._check_entry_fill()
            return

        if not self.bracket.is_open:
            # CLOSED oder EXPIRED - der Platz ist wieder frei. Wird das
            # vergessen, blockiert ein erledigtes Bracket jeden weiteren Trade.
            self.bracket = None
            return

        position = self._first_position()
        if position is None:
            self._record_trade(
                exit_price=self.bracket.stop_price or self.bracket.entry_price or Decimal(0),
                reason=f"{self.bracket.targets_hit} Ziele erreicht",
            )
            self._report(
                EventKind.EXIT,
                f"Position geschlossen nach {self.bracket.targets_hit} Zielen. "
                f"Ergebnis {self.last_equity - self.equity_at_entry:+.2f}",
                targets_hit=self.bracket.targets_hit,
                pnl=self.last_equity - self.equity_at_entry,
                equity=self.last_equity,
            )
            await self._notify(
                f"Position geschlossen. {self.bracket.targets_hit} Ziele erreicht."
            )
            self.bracket.state = BracketState.CLOSED
            self.bracket = None
            return

        if position.size < self.bracket.remaining_qty:
            filled = self.bracket.remaining_qty - position.size
            self.router.on_target_hit(self.bracket, qty=filled)
            self._report(
                EventKind.TARGET,
                f"Ziel {self.bracket.targets_hit} erreicht, {filled} verkauft. "
                f"Stop steht bei {self.bracket.stop_price}.",
                target=self.bracket.targets_hit,
                qty=filled,
                stop_price=self.bracket.stop_price,
                at_breakeven=self.bracket.moved_to_breakeven,
            )
            await self._notify(
                f"Ziel {self.bracket.targets_hit} erreicht ({filled} verkauft). "
                f"Stop steht bei {self.bracket.stop_price}."
            )

    def _track_excursion(self, candle: Candle) -> None:
        """Groessten Gegen- und Vorlauf mitschreiben, solange die Position lebt.

        MAE und MFE sind die beiden Zahlen, aus denen sich spaeter ablesen
        laesst, ob Stop und Ziele richtig sitzen - siehe research/exits.py.
        Sie lassen sich **nur waehrend** des Trades erheben; im Nachhinein sind
        sie aus der Ausfuehrungshistorie nicht mehr rekonstruierbar.
        """
        bracket = self.bracket
        if bracket is None or not bracket.is_open or bracket.entry_price is None:
            return

        entry = bracket.entry_price
        qty = bracket.filled_qty
        if bracket.signal.side is Side.BUY:
            adverse = (entry - candle.low) * qty
            favourable = (candle.high - entry) * qty
        else:
            adverse = (candle.high - entry) * qty
            favourable = (entry - candle.low) * qty

        self._mae = max(self._mae, max(Decimal(0), adverse))
        self._mfe = max(self._mfe, max(Decimal(0), favourable))

    def _record_trade(self, exit_price: Decimal, reason: str) -> None:
        """Den abgeschlossenen Trade festhalten.

        Grundlage fuer die woechentliche Ueberpruefung (``cli review``): Verfall,
        Marktphasen, Ausstiegsqualitaet. Ohne diese Zeilen gibt es spaeter
        nichts auszuwerten ausser dem Kontostand - und der sagt nicht, *warum*
        etwas nicht mehr funktioniert.

        Das Ergebnis wird aus der **Kapitaldifferenz** bestimmt, nicht aus
        Preisen: Darin stecken Gebuehren und Funding bereits drin, ohne dass
        wir sie einzeln nachschlagen muessen.
        """
        bracket = self.bracket
        if bracket is None or bracket.entry_price is None or self.journal is None:
            return

        net = self.last_equity - self.equity_at_entry
        trade = Trade(
            trade_id=f"{bracket.signal.strategy_id}-{bracket.opened_at:%Y%m%d%H%M%S}"
            if bracket.opened_at
            else f"{bracket.signal.strategy_id}-{datetime.now(UTC):%Y%m%d%H%M%S}",
            symbol=self.instrument.symbol,
            side=bracket.signal.side,
            strategy_id=self.strategy.strategy_id,
            entry_time=bracket.opened_at or datetime.now(UTC),
            entry_price=bracket.entry_price,
            exit_time=datetime.now(UTC),
            exit_price=exit_price,
            qty=bracket.filled_qty,
            gross_pnl=net,
            fees=Decimal(0),  # bereits in der Kapitaldifferenz enthalten
            stop_loss=bracket.signal.stop_loss,
            exit_reason=reason,
            leverage=bracket.sized.leverage,
            max_adverse_excursion=self._mae,
            max_favourable_excursion=self._mfe,
        )
        with contextlib.suppress(Exception):
            self.journal.record_trade(trade)

        self._mae = Decimal(0)
        self._mfe = Decimal(0)

    def _first_position(self) -> Position | None:
        positions = self.account.get_positions(self.instrument.symbol)
        return positions[0] if positions else None

    async def _check_entry_fill(self) -> None:
        assert self.bracket is not None
        self._bars_since_entry_placed += 1

        position = self._first_position()
        if position is not None:
            await self._protect(position)
            return

        if self._bars_since_entry_placed >= self.entry_expiry_bars:
            self.router.expire_entry(self.bracket)
            self._bars_since_entry_placed = 0

            # Zwischen Abfrage und Storno kann die Order noch gefuellt worden
            # sein. Dann steht jetzt eine Position im Markt, von der wir nichts
            # wissen - und ohne Stop. Der einzige Fall, in dem ein Storno
            # gefaehrlich ist, und deshalb wird danach noch einmal nachgesehen.
            late = self._first_position()
            if late is not None:
                log.warning(
                    "live.spaeter_fill",
                    hinweis="Order wurde beim Stornieren doch noch gefuellt",
                    groesse=str(late.size),
                )
                await self._protect(late)
                return

            self.stats.entries_expired += 1
            self.bracket = None

    async def _protect(self, position: Position) -> None:
        """Stop und Ziele setzen - und einen Fehlschlag ueberleben."""
        assert self.bracket is not None
        try:
            self.router.protect(
                self.bracket, filled_qty=position.size, fill_price=position.entry_price
            )
        except Exception as exc:
            # ``protect`` schliesst die Position selbst, bevor es weiterwirft.
            # Hier bleibt nur, es zu melden und den Platz freizugeben - der
            # Fehler darf die Schleife nicht beenden.
            log.error("live.absicherung_fehlgeschlagen", fehler=str(exc))
            await self._notify(
                f"Stop konnte nicht gesetzt werden - Position wurde sofort "
                f"geschlossen: {exc}"
            )
            self.bracket = None
            return

        self.stats.entries_filled += 1
        self._bars_since_entry_placed = 0
        self.equity_at_entry = self.last_equity
        self._mae = Decimal(0)
        self._mfe = Decimal(0)
        self._report(
            EventKind.ENTRY,
            f"Einstieg {self.bracket.signal.side.value} {position.size} @ "
            f"{position.entry_price}, Stop {self.bracket.stop_price}",
            side=self.bracket.signal.side.value,
            qty=position.size,
            entry_price=position.entry_price,
            stop_price=self.bracket.stop_price,
            leverage=self.bracket.sized.leverage,
            risk_amount=self.bracket.sized.risk_amount,
            reason=self.bracket.signal.reason,
        )
        await self._notify(
            f"EINSTIEG {self.bracket.signal.side.value} {position.size} "
            f"@ {position.entry_price}\n"
            f"Stop {self.bracket.stop_price} | "
            f"Hebel {self.bracket.sized.leverage:.2f}x | "
            f"Risiko {self.bracket.sized.risk_amount:.2f}"
        )

    async def _look_for_entry(self) -> None:
        """Strategie fragen, Risk-Officer fragen, gegebenenfalls handeln."""
        if len(self._frame) <= self.strategy.warmup_bars:
            return

        arrays = frame_to_arrays(self._frame)
        indicators = self.strategy.prepare(self._frame)
        context = BarContext(self._frame, arrays, indicators, len(self._frame) - 1)

        signal = self.strategy.on_bar(context)
        if signal is None:
            return

        self.stats.signals_generated += 1
        equity = self._current_equity()
        open_positions = len(self.account.get_positions(self.instrument.symbol))

        decision = self.officer.evaluate(
            signal,
            equity=equity,
            open_positions=open_positions,
            equity_fraction=getattr(self.strategy, "equity_fraction", None),
        )

        if isinstance(decision, Vetoed):
            self.stats.count_veto(decision.reason.value)
            log.info("live.signal_abgelehnt", grund=decision.describe())
            self._report(
                EventKind.VETO,
                f"Signal abgelehnt - {decision.detail}",
                reason=decision.reason.value,
                side=signal.side.value,
            )
            return

        assert isinstance(decision, Approved)
        try:
            self.bracket = self.router.open(signal, decision.sized)
            self.stats.entries_placed += 1
            self._bars_since_entry_placed = 0
            self._report(
                EventKind.SIGNAL,
                f"Einstiegsorder {signal.side.value} {decision.sized.qty} @ "
                f"{signal.entry_price} - {signal.reason}",
                side=signal.side.value,
                qty=decision.sized.qty,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                leverage=decision.sized.leverage,
            )
        except Exception as exc:
            log.error("live.einstieg_fehlgeschlagen", fehler=str(exc))
            self._report(EventKind.WARNING, f"Einstieg fehlgeschlagen: {exc}")
            await self._notify(f"Einstieg fehlgeschlagen: {exc}")
            self.bracket = None

    # -- Benachrichtigung ----------------------------------------------------
    async def _notify(self, message: str) -> None:
        if self.notifier is None:
            return
        with contextlib.suppress(Exception):
            await self.notifier(message)


async def telegram_notifier(bot_token: str, chat_id: str) -> Notifier:
    """Erzeugt eine Telegram-Benachrichtigungsfunktion.

    Bewusst fehlertolerant: Ein Ausfall des Benachrichtigungsdienstes darf den
    Handel niemals stoppen.
    """
    import httpx

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async def send(message: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"chat_id": chat_id, "text": message})

    return send
