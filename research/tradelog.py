"""Einzelne Trades und die Kapitalkurve - fuer die Ergebnisseite.

Warum das fehlt, wenn es fehlt
------------------------------
Die Bestenliste zeigt Kennzahlen: 866 Trades, Erwartung ±0,000 R, 48 % der
Fenster profitabel. Das ist verdichtet und richtig - und es beantwortet die
Frage nicht, die man beim Draufschauen zuerst hat: *Was hat das Ding
eigentlich gemacht?*

Eine Strategie mit ausgeglichener Erwartung kann zwei voellig verschiedene
Dinge sein: viele kleine Gewinne und wenige grosse Verluste, oder umgekehrt.
Die Kennzahl ist dieselbe, die Erfahrung damit waere gegensaetzlich - und die
Entscheidung, ob man sie handeln will, auch.

Deshalb werden fuer die Spitzenkandidaten die einzelnen Trades und die
Kapitalkurve mitgeschrieben.

Was hier absichtlich klein bleibt
---------------------------------
Nur eine Handvoll Kandidaten, und je Kandidat hoechstens einige hundert
Trades. Der Zweck ist Anschauung, nicht Vollstaendigkeit: Wer 4.000 Trades in
eine Tabelle schreibt, bekommt eine Datei, die niemand oeffnet, und ein
Diagramm, in dem man nichts erkennt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import structlog

log = structlog.get_logger(__name__)

#: So viele Trades werden je Kandidat festgehalten - die juengsten.
#: Die aelteren stecken in den Kennzahlen; fuer die Anschauung genuegt der
#: jueengste Abschnitt, und er ist der aussagekraeftigste.
MAX_TRADES = 150

#: Stuetzpunkte der Kapitalkurve. Mehr braucht kein Diagramm auf einem
#: Telefonbildschirm, und weniger verwischt die Rueckgaenge.
CURVE_POINTS = 180


@dataclass(slots=True)
class TradeRow:
    """Ein Trade, auf das reduziert, was man ansehen will."""

    zeitpunkt: str
    seite: str
    einstieg: float
    ausstieg: float
    r: float | None
    """Ergebnis in Vielfachen des Risikos. ``None``, wenn kein Stop gesetzt war -
    dann laesst sich das Risiko nicht beziffern und eine Zahl waere geraten."""

    grund: str
    dauer_stunden: float


@dataclass(slots=True)
class TradeLog:
    genome_id: str
    name: str
    trades: list[TradeRow] = field(default_factory=list)
    kurve: list[tuple[str, float]] = field(default_factory=list)
    """Kapitalkurve als (Zeitpunkt, Kapital) - auf wenige Stuetzpunkte gedaunt."""

    gewinner: int = 0
    verlierer: int = 0
    groesster_gewinn_r: float = 0.0
    groesster_verlust_r: float = 0.0
    laengste_verlustserie: int = 0

    def summary(self) -> str:
        gesamt = self.gewinner + self.verlierer
        if not gesamt:
            return "Keine Trades"
        return (
            f"{gesamt} Trades, {self.gewinner / gesamt:.0%} Treffer, "
            f"bester {self.groesster_gewinn_r:+.2f} R, "
            f"schlechtester {self.groesster_verlust_r:+.2f} R, "
            f"laengste Verlustserie {self.laengste_verlustserie}"
        )


def _r_wert(trade) -> float | None:
    wert = trade.r_multiple
    return None if wert is None else float(wert)


def build_log(candidate, *, max_trades: int = MAX_TRADES) -> TradeLog:
    """Trades und Kapitalkurve eines geprueften Kandidaten einsammeln."""
    alle = sorted(candidate.walkforward.all_trades, key=lambda t: t.exit_time)

    gewinner = sum(1 for t in alle if t.is_win)
    r_werte = [r for r in (_r_wert(t) for t in alle) if r is not None]

    # Laengste Verlustserie - die Zahl, an der Strategien im Betrieb scheitern.
    # Nicht am Erwartungswert: Wer zwoelfmal hintereinander verliert, schaltet
    # ab, auch wenn die Rechnung langfristig aufgeht.
    serie = laengste = 0
    for trade in alle:
        if trade.is_win:
            serie = 0
        else:
            serie += 1
            laengste = max(laengste, serie)

    zeilen = [
        TradeRow(
            zeitpunkt=t.entry_time.isoformat(timespec="minutes"),
            seite=t.side.value,
            einstieg=float(t.entry_price),
            ausstieg=float(t.exit_price),
            r=_r_wert(t),
            grund=t.exit_reason or "-",
            dauer_stunden=round(t.duration.total_seconds() / 3600, 1),
        )
        for t in alle[-max_trades:]
    ]

    return TradeLog(
        genome_id=candidate.genome.genome_id,
        name=candidate.genome.name,
        trades=zeilen,
        kurve=_kurve(candidate),
        gewinner=gewinner,
        verlierer=len(alle) - gewinner,
        groesster_gewinn_r=round(max(r_werte, default=0.0), 3),
        groesster_verlust_r=round(min(r_werte, default=0.0), 3),
        laengste_verlustserie=laengste,
    )


def _kurve(candidate) -> list[tuple[str, float]]:
    """Kapitalkurve ueber alle Testfenster, multiplikativ verkettet.

    Verkettet wird wie im Walk-Forward selbst: Zwei Fenster mit je +10 %
    ergeben +21 %, nicht +20 %. Addieren waere derselbe Fehler, der einmal
    einen Rueckgang von 1005 % erzeugt hat.
    """
    punkte: list[tuple[datetime, float]] = []
    faktor = 1.0

    for fenster in candidate.walkforward.windows:
        kurve = getattr(fenster.result, "equity_curve", None)
        if kurve is None or kurve.empty:
            continue
        start = float(kurve["equity"].iloc[0])
        if start <= 0:
            continue
        for zeit, wert in zip(kurve["time"], kurve["equity"], strict=False):
            punkte.append((zeit, faktor * float(wert) / start))
        faktor = punkte[-1][1] if punkte else faktor

    if not punkte:
        return []

    schritt = max(1, len(punkte) // CURVE_POINTS)
    gedaunt = punkte[::schritt]
    if gedaunt[-1] != punkte[-1]:
        gedaunt.append(punkte[-1])

    return [
        (zeit.isoformat(timespec="minutes") if hasattr(zeit, "isoformat") else str(zeit),
         round(wert, 4))
        for zeit, wert in gedaunt
    ]
