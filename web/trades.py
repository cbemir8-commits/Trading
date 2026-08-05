"""Einzelne Trades fuer die Website - so, wie eine Handelsseite sie zeigt.

Warum eigenes Modul
-------------------
``research.tradelog`` baut dasselbe fuer **Backtest**-Kandidaten: Was waere
gewesen. Hier geht es um das, was tatsaechlich passiert ist - der Strom aus
``trades.jsonl``, den der Livebetrieb schreibt. Beide Quellen sehen aehnlich
aus und duerfen trotzdem nicht vermischt werden: Wer eine Backtest-Zeile neben
einer echten sieht und den Unterschied nicht erkennt, zieht falsche Schluesse
ueber sein Konto.

Was hier steht und was nicht
----------------------------
Gezeigt wird je Trade: Richtung, Ein- und Ausstieg, Stop, Menge, Hebel,
Gewinn in Geld **und** in R, Haltedauer und der Grund des Ausstiegs. Das ist
alles, was man braucht, um einen Trade nachzuvollziehen.

Nicht gezeigt wird der Kontostand in absoluten Zahlen, wo er vermeidbar ist -
und **nie** Order-IDs oder Schluessel. Die Seite kann geteilt werden; alles,
was darauf steht, kann jemand anders lesen.

Das R-Vielfache
---------------
``r`` ist der Gewinn gemessen am Risiko, das beim Einstieg auf dem Tisch lag:
Abstand zum Stop mal Menge. +2 R heisst "das Doppelte dessen gewonnen, was
riskiert war" - unabhaengig von Kontogroesse und Positionsgroesse. Das ist die
einzige Zahl, mit der sich ein Live-Ergebnis direkt gegen die Backtest-
Erwartung halten laesst.

Ohne Stop gibt es kein bezifferbares Risiko und damit kein R. Dann steht dort
``None`` und nicht etwa eine Null - eine Null waere eine Aussage, die niemand
gemacht hat.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

#: Mehr Zeilen liest niemand, und die Seite soll auf dem Handy schnell sein.
MAX_ZEILEN = 200


@dataclass(frozen=True, slots=True)
class LiveTrade:
    """Ein abgeschlossener Trade, aufbereitet fuer die Anzeige."""

    zeitpunkt: str
    symbol: str
    seite: str
    einstieg: float
    ausstieg: float
    stop: float | None
    menge: float
    hebel: float
    gewinn: float
    """Netto, nach Gebuehren und Funding - was auf dem Konto ankommt."""

    gebuehren: float
    r: float | None
    dauer_stunden: float
    grund: str

    @property
    def gewonnen(self) -> bool:
        return self.gewinn > 0

    def to_json(self) -> dict:
        return {
            "zeitpunkt": self.zeitpunkt,
            "symbol": self.symbol,
            "seite": self.seite,
            "einstieg": self.einstieg,
            "ausstieg": self.ausstieg,
            "stop": self.stop,
            "menge": self.menge,
            "hebel": self.hebel,
            "gewinn": self.gewinn,
            "gebuehren": self.gebuehren,
            "r": self.r,
            "dauer_stunden": self.dauer_stunden,
            "grund": self.grund,
            "gewonnen": self.gewonnen,
        }


@dataclass(slots=True)
class TradeUebersicht:
    """Alle Trades plus die Kennzahlen, die darueber stehen."""

    trades: list[LiveTrade] = field(default_factory=list)
    anzahl: int = 0
    gewinner: int = 0
    verlierer: int = 0
    gewinn_gesamt: float = 0.0
    gebuehren_gesamt: float = 0.0
    erwartung_r: float | None = None
    bester_r: float | None = None
    schlechtester_r: float | None = None
    laengste_verlustserie: int = 0
    kurve: list[tuple[str, float]] = field(default_factory=list)
    """Kapitalverlauf als (Zeitpunkt, Stand) - aufsummierte Gewinne.

    Nur **realisierte** Trades. Der schwebende Gewinn einer offenen Position
    steht bewusst nicht darin: Er aendert sich mit jedem Tick, und eine Kurve,
    deren letzter Punkt staendig springt, laedt dazu ein, den Verlauf mit dem
    Kontostand zu verwechseln. Der aktuelle Stand steht daneben.
    """

    @property
    def trefferquote(self) -> float | None:
        """``None`` statt 0 %, solange nichts gehandelt wurde.

        Eine Trefferquote von null Prozent bei null Trades waere eine
        Behauptung ueber eine Strategie, die noch nichts getan hat.
        """
        if not self.anzahl:
            return None
        return self.gewinner / self.anzahl

    def to_json(self) -> dict:
        return {
            "trades": [t.to_json() for t in self.trades],
            "anzahl": self.anzahl,
            "gewinner": self.gewinner,
            "verlierer": self.verlierer,
            "trefferquote": self.trefferquote,
            "gewinn_gesamt": round(self.gewinn_gesamt, 2),
            "gebuehren_gesamt": round(self.gebuehren_gesamt, 2),
            "erwartung_r": self.erwartung_r,
            "bester_r": self.bester_r,
            "schlechtester_r": self.schlechtester_r,
            "laengste_verlustserie": self.laengste_verlustserie,
            "kurve": [[zeit, wert] for zeit, wert in self.kurve],
        }


def read_trades(
    directory: Path | str,
    *,
    limit: int = MAX_ZEILEN,
    startkapital: float = 0.0,
) -> TradeUebersicht:
    """Den Live-Trade-Strom lesen und aufbereiten.

    Die Datei waechst nur - sie wird nie gekuerzt. Gelesen wird deshalb alles,
    gezeigt werden die letzten ``limit`` Zeilen; die Kennzahlen darueber
    beziehen sich aber auf **alle** Trades. Sonst aendert sich die
    Trefferquote, sobald jemand die Anzeige verkuerzt, und das waere Unsinn.

    Eine kaputte Zeile beendet nicht das Ganze. Der Livebetrieb schreibt
    zeilenweise; wird er mitten im Schreiben beendet, ist die letzte Zeile
    unvollstaendig. Das ist normal und darf die Seite nicht leer lassen.
    """
    pfad = Path(directory) / "trades.jsonl"
    if not pfad.exists():
        return TradeUebersicht()

    roh: list[dict] = []
    kaputt = 0
    for zeile in pfad.read_text().splitlines():
        zeile = zeile.strip()
        if not zeile:
            continue
        try:
            roh.append(json.loads(zeile))
        except json.JSONDecodeError:
            kaputt += 1

    if kaputt:
        log.warning("trades.zeile_unlesbar", anzahl=kaputt, datei=str(pfad))

    alle = [_aufbereiten(eintrag) for eintrag in roh]
    alle = [t for t in alle if t is not None]
    alle.sort(key=lambda t: t.zeitpunkt)

    uebersicht = _kennzahlen(alle)
    uebersicht.kurve = _kurve(alle, startkapital)
    # Neueste zuerst - so steht oben, was gerade passiert ist.
    uebersicht.trades = list(reversed(alle[-limit:]))
    return uebersicht


def _kurve(alle: list[LiveTrade], startkapital: float) -> list[tuple[str, float]]:
    """Aufsummierte Gewinne als Verlauf.

    Beginnt mit dem Startkapital vor dem ersten Trade - ohne diesen Punkt
    faengt die Grafik beim Ergebnis des ersten Trades an, und der sieht dann
    aus wie der Ausgangspunkt.

    Ist kein Startkapital bekannt, wird bei null begonnen und die Kurve zeigt
    den **Gewinn** statt des Kontostands. Das ist ehrlicher, als eine
    Kontogroesse zu erfinden.
    """
    if not alle:
        return []
    stand = startkapital
    punkte = [(alle[0].zeitpunkt, round(stand, 2))]
    for trade in alle:
        stand += trade.gewinn
        punkte.append((trade.zeitpunkt, round(stand, 2)))
    return punkte


def _kennzahlen(alle: list[LiveTrade]) -> TradeUebersicht:
    uebersicht = TradeUebersicht()
    uebersicht.anzahl = len(alle)
    uebersicht.gewinner = sum(1 for t in alle if t.gewonnen)
    uebersicht.verlierer = uebersicht.anzahl - uebersicht.gewinner
    uebersicht.gewinn_gesamt = sum(t.gewinn for t in alle)
    uebersicht.gebuehren_gesamt = sum(t.gebuehren for t in alle)

    r_werte = [t.r for t in alle if t.r is not None]
    if r_werte:
        uebersicht.erwartung_r = round(sum(r_werte) / len(r_werte), 3)
        uebersicht.bester_r = round(max(r_werte), 2)
        uebersicht.schlechtester_r = round(min(r_werte), 2)

    # Laengste Verlustserie - die Zahl, an der Strategien im Betrieb
    # scheitern. Nicht am Erwartungswert: Wer achtmal hintereinander
    # verliert, schaltet ab, auch wenn die Rechnung langfristig aufgeht.
    serie = laengste = 0
    for trade in alle:
        serie = 0 if trade.gewonnen else serie + 1
        laengste = max(laengste, serie)
    uebersicht.laengste_verlustserie = laengste
    return uebersicht


def _aufbereiten(eintrag: dict) -> LiveTrade | None:
    """Eine Journalzeile in eine Anzeigezeile verwandeln.

    Gibt ``None`` zurueck, wenn Pflichtfelder fehlen - eine halbe Zeile
    anzuzeigen waere schlimmer als sie wegzulassen.
    """
    try:
        einstieg = float(eintrag["entry_price"])
        ausstieg = float(eintrag["exit_price"])
        menge = float(eintrag["qty"])
        eintritt = _zeit(eintrag["entry_time"])
        austritt = _zeit(eintrag["exit_time"])
    except (KeyError, TypeError, ValueError):
        log.warning("trades.zeile_unvollstaendig", felder=sorted(eintrag)[:8])
        return None

    brutto = float(eintrag.get("gross_pnl", 0.0))
    gebuehren = float(eintrag.get("fees", 0.0))
    funding = float(eintrag.get("funding", 0.0))
    netto = brutto - gebuehren - funding

    stop = eintrag.get("stop_loss")
    stop_wert = float(stop) if stop is not None else None

    return LiveTrade(
        zeitpunkt=austritt.isoformat(),
        symbol=str(eintrag.get("symbol", "")),
        seite=str(eintrag.get("side", "")),
        einstieg=einstieg,
        ausstieg=ausstieg,
        stop=stop_wert,
        menge=menge,
        hebel=float(eintrag.get("leverage", 1.0)),
        gewinn=round(netto, 2),
        gebuehren=round(gebuehren + funding, 4),
        r=_r_wert(einstieg, stop_wert, menge, netto),
        dauer_stunden=round((austritt - eintritt).total_seconds() / 3600.0, 2),
        grund=str(eintrag.get("exit_reason", "")),
    )


def _r_wert(
    einstieg: float, stop: float | None, menge: float, netto: float
) -> float | None:
    """Gewinn in Vielfachen des riskierten Betrags.

    ``None`` ohne Stop - dann gibt es kein bezifferbares Risiko. Eine Null
    waere eine Aussage, die niemand gemacht hat.
    """
    if stop is None or menge <= 0:
        return None
    risiko = abs(einstieg - stop) * menge
    if risiko <= 0:
        return None
    return round(netto / risiko, 3)


def _zeit(wert) -> datetime:
    if isinstance(wert, datetime):
        return wert
    return datetime.fromisoformat(str(wert))


def append_trade(directory: Path | str, trade) -> None:
    """Einen Trade anhaengen - dieselbe Datei, die der Livebetrieb schreibt.

    Nur fuer Tests und den Demo-Import gedacht; im Betrieb schreibt
    ``LiveJournal.record_trade``.
    """
    pfad = Path(directory)
    pfad.mkdir(parents=True, exist_ok=True)
    with (pfad / "trades.jsonl").open("a") as handle:
        handle.write(
            trade.model_dump_json()
            if hasattr(trade, "model_dump_json")
            else json.dumps(trade, default=_json_default)
        )
        handle.write("\n")


def _json_default(wert):
    if isinstance(wert, Decimal):
        return str(wert)
    if isinstance(wert, datetime):
        return wert.isoformat()
    raise TypeError(f"nicht serialisierbar: {type(wert).__name__}")
