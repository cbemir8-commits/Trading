"""Positionsgroesse und Hebel.

Hier entsteht der Hebel - und zwar als *Ergebnis*, nicht als Eingabe:

    Risikobetrag     = Kapital x risk_per_trade_pct / 100
    Rohmenge         = Risikobetrag / Stop-Distanz
    Menge            = auf qty_step abgerundet
    Nominalwert      = Menge x Einstiegspreis
    Hebel            = Nominalwert / Kapital

Beispiel, 500 EUR Kapital, 0,75 % Risiko (3,75 EUR), BTC bei 100.000:

    Stop 1,0 % (1000 Punkte) -> 0,00375 BTC -> abgerundet 0,003 -> 300 EUR -> 0,6x
    Stop 0,5 % ( 500 Punkte) -> 0,00750 BTC -> abgerundet 0,007 -> 700 EUR -> 1,4x
    Stop 0,3 % ( 300 Punkte) -> 0,01250 BTC -> abgerundet 0,012 -> 1200 EUR -> 2,4x

Man sieht sofort dreierlei:

* Enge Stops brauchen zwingend Hebel. Ohne ihn waere die Strategie auf Stops
  jenseits von 1,5 % beschraenkt - und damit auf sehr wenige Setups.
* Das Abrunden auf 0,001 BTC kostet bei kleinem Konto spuerbar Genauigkeit.
  Das tatsaechliche Risiko liegt daher meist etwas *unter* dem Ziel - die
  sichere Richtung.
* Der Hebel steigt, wenn der Stop enger wird, nicht wenn wir mutiger werden.
  Das riskierte Geld bleibt in allen drei Zeilen exakt gleich.

Es gibt hier uebrigens eine huebsche Identitaet, die man sich merken sollte:

    abgeleiteter Hebel = risk_per_trade_pct / stop_distance_pct

Bei 0,75 % Risiko und 0,3 % Stop also exakt 2,5x - unabhaengig vom Kapital.
Das Kapital bestimmt nur, ob die Menge ueberhaupt ueber die Mindestgroesse kommt.

Der zweite Job dieses Moduls ist der Liquidationsschutz - und dort steckt eine
teure Falle:

**Der Liquidationspreis haengt am eingestellten Hebel, nicht an der Positionsgroesse.**

Bei Isolated Margin hinterlegt Bybit fuer eine Position genau
``Nominalwert / eingestellter Hebel`` als Margin. Der Rest des Kontos schuetzt
diese Position *nicht*. Steht am Symbol 25x eingestellt und wir eroeffnen eine
Position, die gemessen am Gesamtkapital nur 1,2x betraegt, liegt die Liquidation
trotzdem rund 4 % entfernt - innerhalb eines gewoehnlichen BTC-Dochts. Bei 3x
sind es rund 33 %, also unerreichbar, wenn der Stop bei 1 % sitzt.

Deshalb rechnet der Liquidationsschutz gegen ``risk.max_leverage`` (den Wert, den
der Router am Symbol einstellt) und nicht gegen den abgeleiteten Hebel. Wuerde
man Letzteres tun, kaeme ein viel zu optimistischer Abstand heraus und die
Pruefung wuerde faktisch nie greifen.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum

from core.config import RiskSettings
from core.models import Instrument, Signal, TakeProfitLeg


class RejectReason(StrEnum):
    """Warum ein Signal nicht handelbar ist. Wird geloggt und im Dashboard gezeigt -
    haeufige Ablehnungsgruende sind ein wertvolles Signal an die Research-KI."""

    STOP_TOO_TIGHT = "stop_too_tight"
    STOP_TOO_WIDE = "stop_too_wide"
    QTY_BELOW_MINIMUM = "qty_below_minimum"
    QTY_ABOVE_MAXIMUM = "qty_above_maximum"
    NOTIONAL_TOO_SMALL = "notional_too_small"
    LEVERAGE_CAP_MAKES_QTY_INVALID = "leverage_cap_makes_qty_invalid"
    LIQUIDATION_TOO_CLOSE = "liquidation_too_close"
    NO_EQUITY = "no_equity"
    INVALID_FRACTION = "invalid_fraction"


@dataclass(frozen=True, slots=True)
class SizedPosition:
    """Ergebnis der Groessenberechnung."""

    qty: Decimal
    notional: Decimal
    leverage: Decimal
    """Abgeleiteter Hebel: Nominalwert / Kapital. Eine Kennzahl, kein Stellrad."""

    exchange_leverage: Decimal
    """Der Hebel, der bei Bybit am Symbol eingestellt sein muss.

    Bewusst getrennt von ``leverage``: Bei Isolated Margin bestimmt *dieser*
    Wert den Liquidationspreis, nicht das Verhaeltnis Nominalwert/Kapital.
    Der Order-Router setzt ihn vor der ersten Order und laesst ihn dann stehen.
    """

    risk_amount: Decimal
    risk_pct_of_equity: Decimal
    stop_distance: Decimal
    stop_distance_pct: Decimal
    liquidation_price: Decimal
    liquidation_distance_pct: Decimal
    take_profit_legs: list[tuple[Decimal, Decimal]]
    """(Preis, Menge) je Take-Profit-Stufe - Mengen bereits auf qty_step gerundet."""

    was_capped_by_leverage: bool = False
    """True, wenn die Position wegen ``max_leverage`` verkleinert wurde. Das
    tatsaechliche Risiko liegt dann unter dem Ziel - unbedenklich, aber gut zu wissen."""


@dataclass(frozen=True, slots=True)
class SizingRejected:
    reason: RejectReason
    detail: str


SizingResult = SizedPosition | SizingRejected


def size_position(
    signal: Signal,
    *,
    equity: Decimal,
    instrument: Instrument,
    risk: RiskSettings,
    equity_fraction: Decimal | None = None,
) -> SizingResult:
    """Berechnet Menge, Hebel und Take-Profit-Aufteilung fuer ein Signal.

    Gibt entweder eine handelbare :class:`SizedPosition` zurueck oder eine
    :class:`SizingRejected` mit Begruendung. Es wird nie geraten und nie
    aufgerundet - im Zweifel handeln wir nicht.

    ``equity_fraction`` schaltet auf die zweite Betriebsart um: Die Menge
    ergibt sich dann aus dem Kapital, nicht aus der Stop-Distanz. Gedacht fuer
    Strategien, die investiert bleiben statt auf ein Ereignis zu wetten - dort
    ist der Stop weit, und die Risikoformel liefert entweder eine winzige
    Position oder verweigert den Handel an ``max_stop_distance_pct``.

    Wichtig und leicht zu uebersehen: In dieser Betriebsart ist der Verlust je
    Trade **nicht** mehr auf ``risk_per_trade_pct`` gedeckelt. Er ist gedeckelt
    auf Anteil x Stop-Distanz, und was dabei herauskommt, steht in
    ``risk_pct_of_equity``. Die Sicherheit kommt hier nicht vom Stop, sondern
    davon, in schlechten Phasen gar nicht investiert zu sein - was das
    Drawdown-Gate misst und der Kill-Switch im Betrieb absichert.
    """
    if equity <= 0:
        return SizingRejected(RejectReason.NO_EQUITY, f"Kapital ist {equity}")

    stop_distance = signal.stop_distance
    stop_pct = signal.stop_distance_pct

    if stop_pct < risk.min_stop_distance_pct:
        return SizingRejected(
            RejectReason.STOP_TOO_TIGHT,
            f"Stop {stop_pct:.3f} % < Minimum {risk.min_stop_distance_pct} %. "
            "Zu enge Stops werden von normalem Marktrauschen ausgeloest.",
        )

    nach_kapitalanteil = equity_fraction is not None

    # Die Obergrenze fuer die Stop-Distanz gilt nur, wenn der Stop die Menge
    # bestimmt. Wo er das nicht tut, ist ein weiter Stop kein Risiko, sondern
    # Absicht - er soll ja gerade nicht bei jedem Ruecksetzer ausloesen.
    if not nach_kapitalanteil and stop_pct > risk.max_stop_distance_pct:
        return SizingRejected(
            RejectReason.STOP_TOO_WIDE,
            f"Stop {stop_pct:.3f} % > Maximum {risk.max_stop_distance_pct} %.",
        )

    # --- Schritt 1: Menge bestimmen -----------------------------------------
    if nach_kapitalanteil:
        anteil = Decimal(str(equity_fraction))
        if anteil <= 0 or anteil > risk.max_leverage:
            return SizingRejected(
                RejectReason.INVALID_FRACTION,
                f"Kapitalanteil {anteil} liegt ausserhalb von 0 bis "
                f"{risk.max_leverage} (Hebeldeckel).",
            )
        raw_qty = equity * anteil / signal.entry_price
    else:
        target_risk = equity * risk.risk_per_trade_pct / Decimal(100)
        raw_qty = target_risk / stop_distance

    # --- Schritt 2: Hebeldeckel anwenden ------------------------------------
    # Der Deckel begrenzt den Nominalwert, nicht das Risiko. Greift er, wird die
    # Position kleiner und damit auch das tatsaechliche Risiko - die sichere Richtung.
    max_notional = equity * risk.max_leverage
    qty_from_leverage = max_notional / signal.entry_price
    was_capped = qty_from_leverage < raw_qty
    effective_raw_qty = min(raw_qty, qty_from_leverage)

    qty = instrument.round_qty(effective_raw_qty)

    if qty < instrument.min_order_qty:
        if was_capped:
            return SizingRejected(
                RejectReason.LEVERAGE_CAP_MAKES_QTY_INVALID,
                f"Hebeldeckel {risk.max_leverage}x erlaubt nur {effective_raw_qty:.6f}, "
                f"Mindestmenge ist {instrument.min_order_qty}. "
                f"Bei {equity} Kapital und diesem Stop nicht handelbar.",
            )
        return SizingRejected(
            RejectReason.QTY_BELOW_MINIMUM,
            f"Berechnete Menge {effective_raw_qty:.6f} < Mindestmenge "
            f"{instrument.min_order_qty}. Kapital oder Risiko zu klein fuer diesen Stop.",
        )
    if qty > instrument.max_order_qty:
        return SizingRejected(
            RejectReason.QTY_ABOVE_MAXIMUM,
            f"Menge {qty} > Maximum {instrument.max_order_qty}",
        )

    notional = qty * signal.entry_price
    if notional < instrument.min_notional:
        return SizingRejected(
            RejectReason.NOTIONAL_TOO_SMALL,
            f"Nominalwert {notional:.2f} < Minimum {instrument.min_notional}",
        )

    leverage = notional / equity
    actual_risk = qty * stop_distance
    actual_risk_pct = actual_risk / equity * Decimal(100)

    # --- Schritt 3: Liquidationsschutz --------------------------------------
    # ACHTUNG, subtil und teuer, wenn man es falsch macht:
    #
    # Der Liquidationspreis haengt bei Isolated Margin am **eingestellten**
    # Hebel des Symbols, nicht an unserem abgeleiteten Verhaeltnis
    # Nominalwert/Kapital. Steht bei Bybit 25x eingestellt, hinterlegt die
    # Boerse fuer die Position nur Nominalwert/25 als Margin - der Rest des
    # Kontos bleibt unangetastet und schuetzt die Position *nicht*. Die
    # Liquidation liegt dann rund 4 % entfernt, selbst wenn unsere Position
    # gemessen am Gesamtkapital nur 1,2x betraegt.
    #
    # Wuerden wir hier mit dem abgeleiteten Hebel rechnen, kaeme ein viel zu
    # optimistischer Abstand heraus und die Pruefung wuerde nie greifen.
    #
    # Beim Kapitalanteil wird der Hebel deshalb auf 1 gestellt - und zwar
    # wirklich, nicht nur in dieser Rechnung: ``exchange_leverage`` wandert in
    # die Order und setzt den Hebel am Symbol. Sonst passiert genau das
    # Gegenteil des Gemeinten: Eine Position ueber 40 % des Kontos, bei 3x
    # eingestellt, hinterlegt nur 13 % als Margin und wird schon nach einem
    # Rueckgang von 33 % liquidiert - obwohl 60 % des Kontos unberuehrt
    # danebenliegen. Wer investiert bleiben will, braucht das ganze Konto als
    # Puffer.
    exchange_leverage = (
        Decimal(1) if nach_kapitalanteil else max(risk.max_leverage, Decimal(1))
    )
    liq_price = instrument.estimate_liquidation_price(
        entry=signal.entry_price, side=signal.side, leverage=exchange_leverage
    )
    liq_distance = abs(signal.entry_price - liq_price)
    liq_distance_pct = liq_distance / signal.entry_price * Decimal(100)

    required_buffer = stop_distance * risk.min_liquidation_buffer
    if liq_distance < required_buffer:
        return SizingRejected(
            RejectReason.LIQUIDATION_TOO_CLOSE,
            f"Liquidation liegt {liq_distance_pct:.2f} % entfernt, gefordert sind "
            f"mindestens das {risk.min_liquidation_buffer}-fache der Stop-Distanz "
            f"({stop_pct * risk.min_liquidation_buffer:.2f} %). "
            f"Ursache ist der am Symbol eingestellte Hebel von {exchange_leverage}x - "
            f"RISK__MAX_LEVERAGE senken, nicht die Position verkleinern.",
        )

    legs = split_take_profits(
        qty=qty, take_profits=signal.take_profits, instrument=instrument
    )

    return SizedPosition(
        qty=qty,
        notional=notional,
        leverage=leverage,
        exchange_leverage=exchange_leverage,
        risk_amount=actual_risk,
        risk_pct_of_equity=actual_risk_pct,
        stop_distance=stop_distance,
        stop_distance_pct=stop_pct,
        liquidation_price=liq_price,
        liquidation_distance_pct=liq_distance_pct,
        take_profit_legs=legs,
        was_capped_by_leverage=was_capped,
    )


def split_take_profits(
    *,
    qty: Decimal,
    take_profits: list[TakeProfitLeg],
    instrument: Instrument,
) -> list[tuple[Decimal, Decimal]]:
    """Teilt die Position auf mehrere Take-Profit-Stufen auf.

    Der schwierige Teil ist die Granularitaet. Bei 0,009 BTC Gesamtmenge und
    0,001 BTC Schrittweite gibt es nur neun Bausteine - eine 50/30/20-Aufteilung
    ergibt rechnerisch 4,5 / 2,7 / 1,8 Schritte. Abrunden allein wuerde
    0,008 BTC ergeben und 0,001 BTC unverkauft zuruecklassen.

    Vorgehen:
    1. Jede Stufe auf ``qty_step`` abrunden.
    2. Stufen, die dabei auf null fallen, entfallen (zu kleine Position fuer
       so viele Ziele).
    3. Der Rest geht auf die **letzte** Stufe - der weiteste Take-Profit
       bekommt also den Rest. Das ist absichtlich so: es laesst der Position
       mehr Raum zu laufen, statt frueh zu viel abzuverkaufen.
    """
    if not take_profits or qty <= 0:
        return []

    legs: list[tuple[Decimal, Decimal]] = []
    assigned = Decimal(0)

    for leg in take_profits:
        portion_qty = instrument.round_qty(qty * leg.portion)
        if portion_qty <= 0:
            continue
        if assigned + portion_qty > qty:
            portion_qty = instrument.round_qty(qty - assigned)
            if portion_qty <= 0:
                continue
        legs.append((leg.price, portion_qty))
        assigned += portion_qty

    if not legs:
        # Position zu klein fuer gestaffelte Ziele: alles auf das erste Ziel.
        return [(take_profits[0].price, qty)]

    remainder = qty - assigned
    if remainder > 0:
        last_price, last_qty = legs[-1]
        legs[-1] = (last_price, last_qty + remainder)

    return legs


def leverage_for_stop(
    *,
    equity: Decimal,
    entry_price: Decimal,
    stop_distance_pct: Decimal,
    risk_per_trade_pct: Decimal,
) -> Decimal:
    """Welcher Hebel ergibt sich bei gegebener Stop-Distanz?

    Hilfsfunktion fuer Dashboard und Research: zeigt, welche Stop-Distanzen bei
    gegebenem Kapital ueberhaupt in den Hebelrahmen passen.
    """
    if stop_distance_pct <= 0 or equity <= 0:
        return Decimal(0)
    risk_amount = equity * risk_per_trade_pct / Decimal(100)
    stop_distance = entry_price * stop_distance_pct / Decimal(100)
    qty = risk_amount / stop_distance
    return (qty * entry_price / equity).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
