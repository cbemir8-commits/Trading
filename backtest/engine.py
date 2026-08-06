"""Ereignisgesteuerte Backtest-Engine.

Ablauf je Kerze ``i`` - die Reihenfolge ist die halbe Korrektheit:

1. Offene Orders gegen Kerze ``i`` abarbeiten (Einstieg, Stop, Take-Profits).
   Diese Orders wurden **vor** Kerze ``i`` platziert.
2. Erst danach die Strategie zur abgeschlossenen Kerze ``i`` befragen.
3. Ein daraus entstehendes Signal wirkt fruehestens ab Kerze ``i+1``.

Damit kann eine Strategie nie auf einer Kerze handeln, die sie gerade erst
gesehen hat.

**Intrabar-Aufloesung.** Liegen in einer 15-Minuten-Kerze sowohl Stop als auch
Take-Profit, verraet OHLC nicht, was zuerst kam. Zwei Wege:

* Mit 1-Minuten-Daten (``sub_frame``) wird die Reihenfolge exakt aufgeloest.
  Deshalb laedt der Backfill auch die 1-Minuten-Reihe.
* Ohne sie gilt die pessimistische Annahme: erst Liquidation, dann Stop, dann
  Take-Profit. Ein Backtest, der im Zweifel den Gewinn zuerst nimmt, rechnet
  sich systematisch schoen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

import numpy as np
import pandas as pd
import structlog

from backtest.costs import CostModel, FundingSchedule
from core.config import RiskSettings
from core.models import Instrument, LiquidityRole, Side, Signal, Trade
from execution.risk import RiskOfficer, TradingState
from execution.sizing import SizedPosition, SizingRejected, size_position
from strategy.base import BarContext, Strategy, frame_to_arrays, wants_exit

log = structlog.get_logger(__name__)


class ExitReason(StrEnum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    LIQUIDATION = "liquidation"
    SIGNAL_EXIT = "signal_exit"
    """Die Strategie hat den Ausstieg verlangt - ihre Bedingung gilt nicht mehr."""

    MAX_HOLD = "max_hold"
    END_OF_DATA = "end_of_data"
    KILL_SWITCH = "kill_switch"
    """Der Risk-Officer hat den Not-Aus ausgeloest - Rueckgang ueber der
    Grenze. Im Betrieb ist danach nur noch manuell weiterzumachen; im
    Backtest bleibt das Fenster ab hier ohne neue Einstiege."""


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    instrument: Instrument
    risk: RiskSettings
    costs: CostModel = field(default_factory=CostModel)
    funding: FundingSchedule = field(default_factory=FundingSchedule)

    initial_equity: Decimal = Decimal("500")
    allow_shorts: bool = True

    #: Wie viele Kerzen bleibt eine nicht gefuellte Einstiegsorder aktiv.
    #: Danach wird sie storniert - ein Setup, das nach Stunden noch nicht
    #: erreicht wurde, ist meist nicht mehr gueltig.
    entry_expiry_bars: int = 3

    #: Zwangsschliessung nach N Kerzen. 0 = aus.
    max_hold_bars: int = 0

    #: Nur ein Signal je Kerze und nur eine Position gleichzeitig - das
    #: entspricht dem Risikorahmen bei kleinem Konto.
    reinvest_profits: bool = True
    """Positionsgroesse am aktuellen Kapital bemessen (Zinseszins) statt am
    Startkapital. Realistisch, macht die Equity-Kurve aber exponentiell -
    Kennzahlen wie der maximale Drawdown sind dann in Prozent zu lesen."""

    enforce_risk_limits: bool = True
    """Die Verlustgrenzen des Risk-Officers auch im Backtest durchsetzen.

    Ohne das misst der Backtest eine Strategie, die es so nie geben wird: Im
    Betrieb sperrt der Officer nach 3 % Tagesverlust fuer 24 Stunden, nach
    7 % Wochenverlust bis zur manuellen Freigabe, und bei 15 % Rueckgang
    faellt der Kill-Switch. Der Backtest kannte keine dieser Grenzen und
    handelte munter weiter.

    Gemessen ueber August 2017 bis August 2026 auf BTC + ETH, je Testfenster
    einzeln gerechnet:

        schlimmster Tag                        -3,25 %
        Fenster mit einem Tag unter -3 %        1 von 31
        Wochenlimit ausgeloest in               3 Fenstern
        Kill-Switch ausgeloest                  nie

    Auf den Spitzenkandidaten selbst wirkt sich das **nicht** aus: Kein
    einziges seiner 156 Signale fiel in eine Sperrzeit, die Kennzahlen sind
    auf zwei Nachkommastellen dieselben. Was sich aendert, ist das Gate
    **Parameter-Plateau**: Ein Nachbarparameter, der ohne Grenzen profitabel
    war, ist es mit ihnen nicht mehr. Der Kandidat faellt damit von 9 auf 8
    von 11 - die Strategie steht auf einer schmaleren Kante, als bisher
    gemessen.

    Die Richtung ist eindeutig: Der Backtest war zu **optimistisch**, und das
    Einschalten macht ihn strenger, nicht milder. Deshalb ist der Vorgabewert
    ``True``. Wer ihn ausschaltet, misst wieder die schoenere Zahl - dafuer
    gibt es einen legitimen Grund (den Vergleich mit alten Ergebnissen) und
    keinen guten fuer die Zulassung."""


@dataclass(slots=True)
class _PendingEntry:
    signal: Signal
    sized: SizedPosition
    placed_at: int
    expires_at: int


@dataclass(slots=True)
class _OpenPosition:
    signal: Signal
    side: Side
    entry_price: Decimal
    entry_time: datetime
    entry_index: int
    qty: Decimal
    original_qty: Decimal
    stop_loss: Decimal
    liq_price: Decimal
    leverage: Decimal
    tp_legs: list[tuple[Decimal, Decimal]]
    fees_paid: Decimal = Decimal(0)
    realised_pnl: Decimal = Decimal(0)
    funding_paid: Decimal = Decimal(0)
    mae: Decimal = Decimal(0)
    mfe: Decimal = Decimal(0)
    moved_to_breakeven: bool = False

    def unrealised(self, price: Decimal) -> Decimal:
        return (price - self.entry_price) * self.qty * self.side.sign


@dataclass(slots=True)
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    rejections: dict[str, int] = field(default_factory=dict)
    signals_generated: int = 0
    signals_vetoed: int = 0
    veto_reasons: dict[str, int] = field(default_factory=dict)
    """Womit der Risk-Officer Einstiege verhindert hat, nach Grund gezaehlt.

    Leer, solange ``enforce_risk_limits`` aus ist. Steht hier etwas, ist die
    gehandelte Strategie eine andere als die signalisierte - und zwar
    zulaessigerweise: Die Verlustgrenzen gelten im Betrieb genauso."""

    entries_filled: int = 0
    entries_expired: int = 0
    initial_equity: Decimal = Decimal(0)
    final_equity: Decimal = Decimal(0)
    total_fees: Decimal = Decimal(0)
    total_funding: Decimal = Decimal(0)

    ruined_at: datetime | None = None
    """Zeitpunkt, an dem das Konto aufgebraucht war - ab da wurde nicht mehr
    gehandelt.

    Ohne diese Grenze handelt der Backtest mit negativem Kapital weiter und
    erholt sich davon womoeglich wieder. Das ist nicht bloss unrealistisch,
    es macht die wichtigste Kennzahl unbrauchbar: Ein Drawdown von 1005 %
    kann es nicht geben, mehr als alles kann man nicht verlieren. Wer solche
    Zahlen sieht, misst nicht mehr die Strategie, sondern einen Rechenfehler."""

    @property
    def is_ruined(self) -> bool:
        return self.ruined_at is not None

    @property
    def fill_rate(self) -> float:
        """Anteil der Signale, die tatsaechlich zu einem Trade wurden.

        Eine niedrige Quote bedeutet: Die PostOnly-Limits werden zu selten
        erreicht. Das ist kein Fehler, aber es macht die Strategie in der Praxis
        seltener handelbar, als der Signalzaehler vermuten laesst.
        """
        if self.signals_generated == 0:
            return 0.0
        return self.entries_filled / self.signals_generated

    @property
    def net_profit(self) -> Decimal:
        return self.final_equity - self.initial_equity

    def summary(self) -> str:
        pct = (
            (self.net_profit / self.initial_equity * 100)
            if self.initial_equity
            else Decimal(0)
        )
        return (
            f"{len(self.trades)} Trades, Ergebnis {self.net_profit:+.2f} ({pct:+.2f} %), "
            f"Gebuehren {self.total_fees:.2f}, Funding {self.total_funding:+.2f}, "
            f"Fuellquote {self.fill_rate:.0%}"
        )


class Backtester:
    """Fuehrt eine Strategie ueber eine Zeitreihe aus."""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def _officer(self, arrays) -> RiskOfficer | None:
        """Den Risk-Officer fuer diesen Lauf anlegen - mit der Kerzenuhr.

        Gibt ``None`` zurueck, wenn die Grenzen abgeschaltet sind.

        Die Uhr ist der springende Punkt. Der Officer misst Tages- und
        Wochenverluste an ``datetime.now()``; im Backtest muss sie auf die
        gerade verarbeitete Kerze zeigen, sonst faenden alle 2830 Kerzen am
        selben Tag statt und die Tagesgrenze griffe nie.

        Kein ``state_path``: Jeder Lauf beginnt frei. Im Walk-Forward heisst
        das, dass jedes Testfenster mit einem frischen Officer startet - was
        der Annahme entspricht, dass der Nutzer einen ausgeloesten Not-Aus
        zwischen den Fenstern manuell freigibt. Ohne diese Annahme bliebe
        jedes Fenster nach dem ersten Not-Aus fuer immer stumm, und der
        Backtest waere in der anderen Richtung falsch.
        """
        if not self.config.enforce_risk_limits:
            return None

        self._jetzt = _to_datetime(arrays["open_time"][0])
        return RiskOfficer(
            self.config.risk,
            self.config.instrument,
            state_path=None,
            clock=lambda: self._jetzt,
        )

    def run(
        self,
        frame: pd.DataFrame,
        strategy: Strategy,
        *,
        sub_frame: pd.DataFrame | None = None,
    ) -> BacktestResult:
        """Backtest ausfuehren.

        ``sub_frame`` sind feinere Kerzen (typisch 1 Minute) zur exakten
        Intrabar-Aufloesung. Ohne sie gilt die pessimistische Annahme.
        """
        if frame.empty:
            return BacktestResult(
                initial_equity=self.config.initial_equity,
                final_equity=self.config.initial_equity,
            )

        arrays = frame_to_arrays(frame)
        indicators = strategy.prepare(frame)
        _verify_indicator_lengths(indicators, len(frame))

        # Die Betriebsart der Positionsgroesse gehoert zur Strategie, nicht zur
        # Konfiguration: Ob eine Menge aus dem Stop oder aus dem Kapital folgt,
        # entscheidet die Idee dahinter. Strategien ohne diese Angabe verhalten
        # sich unveraendert - ``None`` ist die bisherige Risikoformel.
        #
        # ``fraction_at`` wird **je Balken** gefragt: Beim Vola-Ziel aendert
        # sich der Anteil mit der gemessenen Schwankungsbreite. Einmal am
        # Anfang zu fragen wuerde die ganze Steuerung wirkungslos machen.
        hole_anteil = getattr(strategy, "fraction_at", None)
        statischer_anteil = getattr(strategy, "equity_fraction", None)

        sub_index = _SubBarIndex(sub_frame) if sub_frame is not None else None

        state = _RunState(
            cash=self.config.initial_equity,
            equity_times=[],
            equity_values=[],
        )
        result = BacktestResult(initial_equity=self.config.initial_equity)

        n = len(frame)
        start = max(strategy.warmup_bars, 1)

        # Der **echte** Risk-Officer, nicht eine Nachbildung seiner Regeln.
        # Die Uhr zeigt auf die Kerze, sonst rechnete er mit der Wirklichkeit
        # statt mit dem Backtest. Kein ``state_path``: Der Lauf soll nichts
        # von einem frueheren erben.
        officer = self._officer(arrays)

        for i in range(start, n):
            bar_time = arrays["open_time"][i]
            bar_end = _bar_end(arrays["open_time"], i)
            if officer is not None:
                self._jetzt = _to_datetime(bar_time)

            # 1. Bestehende Orders gegen diese Kerze abarbeiten.
            self._process_bar(state, result, arrays, i, bar_time, bar_end, sub_index)

            # 2. Strategie zur abgeschlossenen Kerze befragen.
            ctx = BarContext(frame, arrays, indicators, i)
            signal = strategy.on_bar(ctx)

            # Ausstiegsbedingung der Strategie - **nach** Stop und Zielen.
            # Die haetten innerhalb der Kerze zuerst gegriffen; diese Bedingung
            # steht erst am Kerzenschluss fest und wird deshalb auch zu diesem
            # Kurs ausgefuehrt, als Taker.
            if state.position is not None and wants_exit(strategy, ctx, state.position.side):
                self._close_position(
                    state,
                    result,
                    state.position.qty,
                    Decimal(str(arrays["close"][i])),
                    _to_datetime(bar_time),
                    ExitReason.SIGNAL_EXIT,
                    role=LiquidityRole.TAKER,
                )

            if signal is not None:
                result.signals_generated += 1
                # Der Officer entscheidet **vor** der Groessenrechnung, ob
                # ueberhaupt eingestiegen werden darf. Ohne diese Frage misst
                # der Backtest eine Strategie, die im Betrieb an 21 Stellen
                # gesperrt gewesen waere - siehe ``enforce_risk_limits``.
                # ``open_positions=0`` mit Absicht: Ob schon eine Position
                # offen ist, prueft die Engine gleich selbst in
                # ``_consider_entry`` - und sie weiss dabei mehr, naemlich
                # auch von wartenden Einstiegsorders.
                #
                # Wuerde der Officer hier mitpruefen, gaebe es dieselbe Regel
                # zweimal, und die Ablehnung landete je nach Reihenfolge mal
                # in ``rejections``, mal in ``veto_reasons``. Der Officer
                # steuert hier genau das bei, was die Engine **nicht** weiss:
                # die Verlustgrenzen.
                gesperrt = officer.blockade(open_positions=0) if officer else None
                if gesperrt is not None:
                    result.signals_vetoed += 1
                    result.veto_reasons[gesperrt.reason.value] = (
                        result.veto_reasons.get(gesperrt.reason.value, 0) + 1
                    )
                else:
                    anteil = (
                        hole_anteil(i) if hole_anteil is not None else statischer_anteil
                    )
                    self._consider_entry(state, result, signal, i, anteil)

            # 3. Kapitalkurve fortschreiben.
            mark = Decimal(str(arrays["close"][i]))
            equity = state.cash + (
                state.position.unrealised(mark) if state.position else Decimal(0)
            )

            # **Unter null geht es nicht.**
            # Bei Isolated Margin ist die gestellte Margin das Maximum, das
            # verloren gehen kann - davor liquidiert die Boerse. Ohne diese
            # Grenze laeuft die Kapitalkurve ins Minus, und der Drawdown wird
            # groesser als 100 %: eine Zahl, die es nicht geben kann und die
            # jede darauf aufbauende Schwelle wertlos macht. Der erste echte
            # Zulassungslauf meldete 1005 %.
            if equity <= 0:
                equity = Decimal(0)
                if not state.ruined:
                    state.ruined = True
                    result.ruined_at = bar_time
                    log.warning(
                        "backtest.konto_aufgebraucht",
                        zeitpunkt=bar_time.isoformat(),
                        trades_bis_dahin=len(result.trades),
                        hinweis="Ab hier wird nicht mehr gehandelt.",
                    )

            state.equity_times.append(bar_time)
            state.equity_values.append(float(equity))

            # 4. Kapitalstand melden - **nach** dem Fortschreiben, damit der
            # Officer den Stand dieser Kerze sieht. Er fuehrt daraus Tages-,
            # Wochen- und Hoechststand und loest gegebenenfalls den
            # Kill-Switch aus.
            #
            # Bewusst bei **jeder** Kerze, nicht nur bei Signalen: Genau so
            # macht es der Livebetrieb, und der Kill-Switch soll auch dann
            # greifen, wenn eine offene Position ins Minus laeuft und gerade
            # kein Signal ansteht.
            if officer is not None:
                officer.observe_equity(equity)
                if (
                    officer.state.trading_state is TradingState.KILLED
                    and state.position is not None
                ):
                    self._close_position(
                        state, result, state.position.qty, mark,
                        _to_datetime(bar_time), ExitReason.KILL_SWITCH,
                        role=LiquidityRole.TAKER, is_stop=True,
                    )

        # Offene Position am Ende zum letzten Schlusskurs glattstellen.
        if state.position is not None:
            last_close = Decimal(str(arrays["close"][n - 1]))
            self._close_position(
                state, result, state.position.qty, last_close,
                _to_datetime(arrays["open_time"][n - 1]), ExitReason.END_OF_DATA,
                role=LiquidityRole.TAKER,
            )

        result.equity_curve = pd.DataFrame(
            {"time": state.equity_times, "equity": state.equity_values}
        )
        result.final_equity = state.cash
        result.total_fees = state.total_fees
        result.total_funding = state.total_funding
        return result

    # -- Einstieg ------------------------------------------------------------
    def _consider_entry(
        self,
        state: _RunState,
        result: BacktestResult,
        signal: Signal,
        index: int,
        equity_fraction: Decimal | None = None,
    ) -> None:
        if state.position is not None or state.pending is not None:
            state.count_rejection(result, "position_bereits_offen")
            return
        if signal.side is Side.SELL and not self.config.allow_shorts:
            state.count_rejection(result, "shorts_deaktiviert")
            return

        equity = state.cash if self.config.reinvest_profits else self.config.initial_equity

        # **Ein aufgebrauchtes Konto handelt nicht weiter.**
        # In der Wirklichkeit ist dann Schluss: kein Geld mehr fuer Margin,
        # die Boerse liquidiert, und niemand handelt sich aus dem Minus
        # zurueck. Ein Backtest, der das zulaesst, rechnet sich anschliessend
        # wieder hoch - reine Fantasie.
        if state.ruined or equity <= self.config.instrument.min_notional:
            state.count_rejection(result, "konto_aufgebraucht")
            return

        sized = size_position(
            signal,
            equity=equity,
            instrument=self.config.instrument,
            risk=self.config.risk,
            equity_fraction=equity_fraction,
        )
        if isinstance(sized, SizingRejected):
            state.count_rejection(result, sized.reason.value)
            return

        state.pending = _PendingEntry(
            signal=signal,
            sized=sized,
            placed_at=index,
            expires_at=index + self.config.entry_expiry_bars,
        )

    # -- Kerzenverarbeitung --------------------------------------------------
    def _process_bar(
        self,
        state: _RunState,
        result: BacktestResult,
        arrays: dict[str, np.ndarray],
        index: int,
        bar_time: np.datetime64,
        bar_end: datetime,
        sub_index: _SubBarIndex | None,
    ) -> None:
        segments = self._segments(arrays, index, sub_index)

        for seg_time, seg_high, seg_low in segments:
            if state.pending is not None:
                self._try_fill_entry(state, result, seg_time, seg_high, seg_low, index)

            if state.position is not None:
                self._check_exits(state, result, seg_time, seg_high, seg_low)

        # Abgelaufene Einstiegsorder stornieren.
        if state.pending is not None and index >= state.pending.expires_at:
            state.pending = None
            result.entries_expired += 1

        # Funding fuer die gehaltene Position verrechnen.
        if state.position is not None:
            self._apply_funding(state, bar_end)

        # Maximale Haltedauer.
        if (
            state.position is not None
            and self.config.max_hold_bars > 0
            and index - state.position.entry_index >= self.config.max_hold_bars
        ):
            close = Decimal(str(arrays["close"][index]))
            self._close_position(
                state, result, state.position.qty, close,
                _to_datetime(bar_time), ExitReason.MAX_HOLD, role=LiquidityRole.TAKER,
            )

    def _segments(
        self, arrays: dict[str, np.ndarray], index: int, sub_index: _SubBarIndex | None
    ) -> list[tuple[datetime, Decimal, Decimal]]:
        """Zerlegt eine Kerze in Preisabschnitte, die der Reihe nach geprueft werden.

        Mit 1-Minuten-Daten sind das bis zu 15 Abschnitte je 15-Minuten-Kerze -
        damit ist die Reihenfolge von Stop und Take-Profit nahezu eindeutig.
        Ohne sie bleibt die ganze Kerze ein einziger Abschnitt und es gilt die
        pessimistische Annahme.
        """
        bar_time = _to_datetime(arrays["open_time"][index])
        bar_end = _bar_end(arrays["open_time"], index)

        if sub_index is not None:
            subs = sub_index.between(bar_time, bar_end)
            if subs:
                return subs

        return [
            (
                bar_time,
                Decimal(str(arrays["high"][index])),
                Decimal(str(arrays["low"][index])),
            )
        ]

    def _try_fill_entry(
        self,
        state: _RunState,
        result: BacktestResult,
        moment: datetime,
        high: Decimal,
        low: Decimal,
        index: int,
    ) -> None:
        """PostOnly-Limit fuellt nur, wenn der Markt durch das Limit handelt.

        Bewusst streng (``<`` statt ``<=``): Beruehrt der Preis das Limit nur,
        stehen wir hinten in der Warteschlange und werden womoeglich nicht
        bedient. Ein Backtest, der jede Beruehrung als Fill wertet, erzeugt
        Trades, die live nie zustande kaemen.
        """
        pending = state.pending
        assert pending is not None
        if index <= pending.placed_at:
            return  # fruehestens die naechste Kerze

        limit = pending.signal.entry_price
        filled = low < limit if pending.signal.side is Side.BUY else high > limit
        if not filled:
            return

        sized = pending.sized
        notional = sized.qty * limit
        fee = self.config.costs.fee(notional, LiquidityRole.MAKER)

        state.cash -= fee
        state.total_fees += fee

        state.position = _OpenPosition(
            signal=pending.signal,
            side=pending.signal.side,
            entry_price=limit,
            entry_time=moment,
            entry_index=index,
            qty=sized.qty,
            original_qty=sized.qty,
            stop_loss=pending.signal.stop_loss,
            liq_price=sized.liquidation_price,
            leverage=sized.leverage,
            tp_legs=list(sized.take_profit_legs),
            fees_paid=fee,
        )
        state.pending = None
        result.entries_filled += 1

    # -- Ausstiege -----------------------------------------------------------
    def _check_exits(
        self,
        state: _RunState,
        result: BacktestResult,
        moment: datetime,
        high: Decimal,
        low: Decimal,
    ) -> None:
        position = state.position
        assert position is not None

        self._track_excursions(position, high, low)

        # Reihenfolge ist die pessimistische Annahme: erst was uns schadet.
        if self._hit(position.side, position.liq_price, high, low, adverse=True):
            self._close_position(
                state, result, position.qty, position.liq_price, moment,
                ExitReason.LIQUIDATION, role=LiquidityRole.TAKER, is_stop=True,
            )
            return

        if self._hit(position.side, position.stop_loss, high, low, adverse=True):
            self._close_position(
                state, result, position.qty, position.stop_loss, moment,
                ExitReason.STOP_LOSS, role=LiquidityRole.TAKER, is_stop=True,
            )
            return

        while position.tp_legs:
            tp_price, tp_qty = position.tp_legs[0]
            if not self._hit(position.side, tp_price, high, low, adverse=False):
                break

            position.tp_legs.pop(0)
            qty = min(tp_qty, position.qty)
            fully_closed = self._close_position(
                state, result, qty, tp_price, moment,
                ExitReason.TAKE_PROFIT, role=LiquidityRole.MAKER,
            )
            if fully_closed:
                return

            # Nach der ersten Teilrealisierung den Stop auf Einstand ziehen.
            if not position.moved_to_breakeven:
                position.stop_loss = position.entry_price
                position.moved_to_breakeven = True

    @staticmethod
    def _hit(side: Side, level: Decimal, high: Decimal, low: Decimal, *, adverse: bool) -> bool:
        """Wurde ein Preisniveau in diesem Abschnitt erreicht?

        ``adverse`` unterscheidet Stop (Preis bewegt sich gegen uns) von
        Take-Profit (Preis bewegt sich fuer uns).
        """
        if side is Side.BUY:
            return low <= level if adverse else high >= level
        return high >= level if adverse else low <= level

    @staticmethod
    def _track_excursions(position: _OpenPosition, high: Decimal, low: Decimal) -> None:
        """Groesster Buch-Verlust und -Gewinn waehrend der Haltedauer.

        Aussagekraeftig fuer die Stop-Platzierung: Wenn nahezu jeder Gewinntrade
        vorher tief im Minus stand, sitzt der Stop zu weit weg - oder der
        Einstieg ist zu frueh.
        """
        if position.side is Side.BUY:
            adverse = position.entry_price - low
            favourable = high - position.entry_price
        else:
            adverse = high - position.entry_price
            favourable = position.entry_price - low
        position.mae = max(position.mae, adverse)
        position.mfe = max(position.mfe, favourable)

    def _close_position(
        self,
        state: _RunState,
        result: BacktestResult,
        qty: Decimal,
        price: Decimal,
        moment: datetime,
        reason: ExitReason,
        *,
        role: LiquidityRole,
        is_stop: bool = False,
    ) -> bool:
        """Schliesst (einen Teil) der Position. Gibt True zurueck, wenn flach."""
        position = state.position
        assert position is not None

        exit_price = (
            self.config.costs.apply_slippage(price, position.side.opposite, is_stop=is_stop)
            if role is LiquidityRole.TAKER
            else price
        )

        gross = (exit_price - position.entry_price) * qty * position.side.sign
        fee = self.config.costs.fee(qty * exit_price, role)

        state.cash += gross - fee
        state.total_fees += fee
        position.fees_paid += fee
        position.realised_pnl += gross
        position.qty -= qty

        is_flat = position.qty <= 0
        if is_flat:
            result.trades.append(
                Trade(
                    trade_id=f"{position.signal.strategy_id}-{position.entry_index}",
                    # Der Markt kommt vom **Kontrakt**, nicht aus dem Signal.
                    #
                    # Ein Backtester handelt genau ein Instrument - das, gegen
                    # das er auch die Groesse rechnet. Das Signal traegt zwar
                    # ein Symbol, aber der Genome-Compiler setzt dort fest
                    # "BTCUSDT", egal welche Kerzen er sieht. Solange nur ein
                    # Markt lief, war das Kosmetik. Bei mehreren Maerkten
                    # bekamen alle Trades dasselbe Symbol, und die Zuordnung
                    # war stillschweigend weg.
                    symbol=self.config.instrument.symbol,
                    side=position.side,
                    strategy_id=position.signal.strategy_id,
                    entry_time=position.entry_time,
                    entry_price=position.entry_price,
                    exit_time=moment,
                    exit_price=exit_price,
                    qty=position.original_qty,
                    gross_pnl=position.realised_pnl,
                    fees=position.fees_paid,
                    funding=position.funding_paid,
                    stop_loss=position.signal.stop_loss,
                    exit_reason=reason.value,
                    leverage=position.leverage,
                    max_adverse_excursion=position.mae,
                    max_favourable_excursion=position.mfe,
                )
            )
            state.position = None
        return is_flat

    def _apply_funding(self, state: _RunState, until: datetime) -> None:
        position = state.position
        assert position is not None
        payment = self.config.funding.payments_between(
            state.funding_checkpoint or position.entry_time,
            until,
            position_value=position.qty * position.entry_price,
            side=position.side,
        )
        if payment:
            state.cash -= payment
            state.total_funding += payment
            position.funding_paid += payment
        state.funding_checkpoint = until


@dataclass(slots=True)
class _RunState:
    cash: Decimal
    equity_times: list
    equity_values: list
    position: _OpenPosition | None = None
    pending: _PendingEntry | None = None
    total_fees: Decimal = Decimal(0)
    total_funding: Decimal = Decimal(0)
    funding_checkpoint: datetime | None = None
    ruined: bool = False
    """Kapital aufgebraucht. Ab hier keine neuen Positionen mehr."""

    def count_rejection(self, result: BacktestResult, reason: str) -> None:
        result.rejections[reason] = result.rejections.get(reason, 0) + 1


class _SubBarIndex:
    """Schneller Zugriff auf feinere Kerzen innerhalb einer groberen.

    Nutzt ``searchsorted`` statt einer Filterung je Kerze - bei sechs Jahren
    1-Minuten-Daten ist das der Unterschied zwischen Sekunden und Stunden.

    Die Zeitstempel werden als int64 mit **ausdruecklich auf Nanosekunden
    normierter** Einheit gehalten. Beides ist noetig:

    * ``np.datetime64`` kennt keine Zeitzonen; der Vergleich eines
      zeitzonenbehafteten mit einem naiven Zeitstempel wirft in pandas einen
      TypeError.
    * pandas waehlt die Zeiteinheit je nach Datenquelle (hier ``us``), waehrend
      ``Timestamp.value`` **immer** Nanosekunden liefert. Ohne ``as_unit("ns")``
      liegen beide Seiten um Faktor 1000 auseinander - ``searchsorted`` findet
      dann nie etwas, und die Engine faellt still auf die pessimistische
      Annahme zurueck, statt die 1-Minuten-Daten zu nutzen. Ein Fehler ohne
      Fehlermeldung, der den Backtest nur schlechter aussehen laesst - deshalb
      sichert ihn ein eigener Test ab.
    """

    def __init__(self, frame: pd.DataFrame) -> None:
        ordered = frame.sort_values("open_time")
        index = pd.DatetimeIndex(ordered["open_time"])
        self.times_ns = index.as_unit("ns").asi8
        self.times = ordered["open_time"].to_list()
        self.high = ordered["high"].to_numpy(dtype=np.float64)
        self.low = ordered["low"].to_numpy(dtype=np.float64)

    @staticmethod
    def _to_ns(moment: datetime) -> int:
        return pd.Timestamp(moment).as_unit("ns").value

    def between(
        self, start: datetime, end: datetime
    ) -> list[tuple[datetime, Decimal, Decimal]]:
        left = int(np.searchsorted(self.times_ns, self._to_ns(start), side="left"))
        right = int(np.searchsorted(self.times_ns, self._to_ns(end), side="left"))
        if right <= left:
            return []
        return [
            (
                _to_datetime(self.times[k]),
                Decimal(str(self.high[k])),
                Decimal(str(self.low[k])),
            )
            for k in range(left, right)
        ]


def _to_datetime(value) -> datetime:
    return pd.Timestamp(value).to_pydatetime()


def _bar_end(times: np.ndarray, index: int) -> datetime:
    """Ende der Kerze - der Beginn der naechsten.

    Bei der letzten Kerze wird der Abstand der vorherigen fortgeschrieben.
    """
    if index + 1 < len(times):
        return _to_datetime(times[index + 1])
    if index > 0:
        step = pd.Timestamp(times[index]) - pd.Timestamp(times[index - 1])
        return _to_datetime(pd.Timestamp(times[index]) + step)
    return _to_datetime(times[index])


def _verify_indicator_lengths(indicators: dict[str, np.ndarray], expected: int) -> None:
    """Ein Indikator mit falscher Laenge verschiebt alle Werte gegen die Kerzen.

    Das ist der klassische Off-by-one, der aus einer Strategie unbemerkt eine
    Hellseherin macht - lieber hier hart scheitern.
    """
    for name, series in indicators.items():
        if len(series) != expected:
            raise ValueError(
                f"Indikator '{name}' hat {len(series)} Werte, erwartet {expected}. "
                "Eine abweichende Laenge verschiebt die Zuordnung zu den Kerzen."
            )
