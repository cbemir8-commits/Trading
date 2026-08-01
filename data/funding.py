"""Funding-Raten - die Datenquelle, die wir hatten und nie benutzt haben.

Warum das etwas anderes ist als alles bisher
---------------------------------------------
Zehn widerlegte Hypothesen hatten eine Gemeinsamkeit, die uns lange nicht
aufgefallen ist: Sie benutzten **alle dieselbe Datenquelle**. Kerzen. Also
genau die Zahlen, die weltweit am gruendlichsten durchsucht sind - von
Menschen, von Firmen mit eigenen Rechenzentren, seit Jahrzehnten. Dass dort
mit gleitenden Durchschnitten nichts mehr liegt, ist keine Ueberraschung,
sondern die Erwartung.

Die Funding-Rate ist etwas anderes, in drei Hinsichten:

**Sie ist keine Kursbewegung, sondern Positionierung.** Sie sagt, wer gerade
gedraengt steht. Bei stark positiver Rate zahlen die Longs den Shorts - das
passiert, wenn zu viele long sind. Diese Information steckt in keiner Kerze.

**Sie ist ein Zahlungsstrom, keine Prognose.** Alle acht Stunden fliesst
tatsaechlich Geld. Wer short ist, waehrend die Rate positiv ist, bekommt
etwas - unabhaengig davon, wohin der Kurs laeuft. Das ist ein anderer
Mechanismus als "ich glaube, es geht hoch".

**Es gibt sie nur bei Perpetuals.** Aktien, Anleihen und Devisen haben nichts
Vergleichbares. Die grosse quantitative Industrie hat ihre Werkzeuge an diesen
Maerkten entwickelt; Funding faellt dort schlicht nicht an. Der Kreis derer,
die hier suchen, ist um Groessenordnungen kleiner.

Das ist keine Garantie fuer einen Vorteil. Es ist aber der erste Ort, an dem
zu suchen ueberhaupt Sinn ergibt.

Aufloesung
----------
Bybit zahlt alle acht Stunden. Auf Stundenkerzen bedeutet das: Derselbe Wert
gilt fuer acht Kerzen. Er wird deshalb **vorwaerts fortgeschrieben** - jede
Kerze bekommt die zuletzt festgestellte Rate. Rueckwaerts fuellen waere
Lookahead: Die Rate von 16 Uhr stand um 12 Uhr noch nicht fest.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import structlog

from core.models import FundingRate
from data.bybit.adapter import MarketDataSource

log = structlog.get_logger(__name__)

#: Bybit liefert maximal 200 Funding-Eintraege je Anfrage.
PAGE_SIZE = 200

#: Alle acht Stunden - der uebliche Rhythmus bei Bybit.
FUNDING_INTERVAL = timedelta(hours=8)

#: So viele leere Seiten hintereinander gelten als Ende der Historie.
MAX_EMPTY_PAGES = 5


def funding_to_frame(rates: list[FundingRate]) -> pd.DataFrame:
    if not rates:
        return pd.DataFrame({"time": pd.Series(dtype="datetime64[ns, UTC]"),
                             "funding_rate": pd.Series(dtype="float64")})
    frame = pd.DataFrame(
        {
            "time": [r.funding_time for r in rates],
            "funding_rate": [float(r.funding_rate) for r in rates],
        }
    )
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").drop_duplicates("time").reset_index(drop=True)


class FundingStore:
    """Funding-Historie auf der Platte - eine Parquet-Datei je Symbol.

    Viel kleiner als Kerzen: Drei Werte am Tag ergeben ueber sechs Jahre rund
    6.500 Zeilen. Eine Datei genuegt, Monatspartitionen waeren Aufwand ohne
    Gegenwert.
    """

    def __init__(self, root: Path | str = "data_store") -> None:
        self.root = Path(root) / "funding"
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, symbol: str) -> Path:
        return self.root / f"{symbol}.parquet"

    def read(self, symbol: str) -> pd.DataFrame:
        file = self.path(symbol)
        if not file.exists():
            return funding_to_frame([])
        return pd.read_parquet(file)

    def write(self, symbol: str, rates: list[FundingRate]) -> int:
        if not rates:
            return 0
        incoming = funding_to_frame(rates)
        existing = self.read(symbol)

        before = len(existing)
        combined = (
            pd.concat([existing, incoming], ignore_index=True)
            .drop_duplicates(subset="time", keep="last")
            .sort_values("time")
            .reset_index(drop=True)
        )
        combined.to_parquet(self.path(symbol), index=False)
        return len(combined) - before

    def last_time(self, symbol: str) -> datetime | None:
        frame = self.read(symbol)
        if frame.empty:
            return None
        return frame["time"].iloc[-1].to_pydatetime()


def backfill_funding(
    market: MarketDataSource,
    store: FundingStore,
    symbol: str,
    *,
    start: datetime,
    end: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
    max_pages: int = 200,
    on_progress: Callable[[int, datetime], None] | None = None,
) -> int:
    """Funding-Historie nachladen.

    Dieselbe Vorsichtsmassnahme wie beim Kerzen-Backfill: Jede Anfrage bekommt
    ein Fenster mit **beiden** Grenzen, hoechstens eine Seite lang. Bybit
    liefert sonst die juengsten Eintraege, die Schleife haelt sich nach einer
    Anfrage fuer fertig - der Fehler, der aus sechs Jahren Kerzen zehn Tage
    gemacht hat.

    Die Fensterbreite folgt der Annahme "alle acht Stunden". Sollte ein Symbol
    haeufiger zahlen, passt mehr als eine Seite ins Fenster, und Bybit laesst
    die aeltesten Eintraege weg - lautlos. Deshalb wird nach jeder vollen Seite
    geprueft, ob der erste gelieferte Eintrag wirklich am Fensteranfang liegt.
    Tut er das nicht, wird das Fenster halbiert und dieselbe Stelle erneut
    angefragt, statt die Luecke zu uebernehmen.
    """
    now = (clock or (lambda: datetime.now(UTC)))()
    end = end or now

    cursor = start
    last = store.last_time(symbol)
    if last is not None and last >= start:
        cursor = last + FUNDING_INTERVAL

    window = FUNDING_INTERVAL * PAGE_SIZE
    written = 0
    empty_pages = 0

    for _ in range(max_pages):
        if cursor >= end:
            break

        page_end = min(end, cursor + window)
        rates = market.get_funding_history(
            symbol, start=cursor, end=page_end, limit=PAGE_SIZE
        )

        if not rates:
            # Eine leere Seite heisst nicht "fertig", sondern "in diesem
            # Fenster war nichts". Erst mehrere hintereinander sind ein Ende.
            empty_pages += 1
            if empty_pages >= MAX_EMPTY_PAGES:
                break
            cursor = page_end
            continue
        empty_pages = 0

        zu_viel_im_fenster = (
            len(rates) >= PAGE_SIZE
            and rates[0].funding_time > cursor + FUNDING_INTERVAL
        )
        if zu_viel_im_fenster and window > FUNDING_INTERVAL:
            window = max(window // 2, FUNDING_INTERVAL)
            log.info(
                "funding.fenster_verkleinert",
                symbol=symbol,
                stunden=window / timedelta(hours=1),
            )
            continue

        written += store.write(symbol, rates)
        newest = rates[-1].funding_time

        # Einen Wimpernschlag hinter den juengsten Eintrag, nicht einen ganzen
        # Zahlungsrhythmus. ``FUNDING_INTERVAL`` ist eine Annahme; zahlt das
        # Symbol haeufiger, uebersprungen genau diese Annahme die Eintraege
        # dazwischen - lautlos und gleichmaessig ueber die ganze Historie.
        next_cursor = newest + timedelta(milliseconds=1)

        # Kam die Seite nicht voll zurueck, ist das Fenster erschoepft - dann
        # bis ans Fensterende springen, statt es Eintrag fuer Eintrag abzugehen.
        if len(rates) < PAGE_SIZE:
            next_cursor = max(next_cursor, page_end)

        if next_cursor <= cursor:
            log.warning("funding.cursor_steht", symbol=symbol, stand=cursor.isoformat())
            break
        cursor = next_cursor

        if on_progress is not None:
            on_progress(written, cursor)

    log.info("funding.geladen", symbol=symbol, neu=written, bis=cursor.isoformat())
    return written


def attach_funding(frame: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    """Die Funding-Rate an jede Kerze schreiben.

    **Vorwaerts fortgeschrieben, niemals rueckwaerts.** Jede Kerze bekommt die
    zuletzt *festgestellte* Rate. Rueckwaerts zu fuellen waere der klassische
    Lookahead: Die Rate von 16 Uhr stand um 12 Uhr noch nicht fest, und eine
    Strategie, die sie dort schon kennt, weiss etwas ueber die Zukunft.

    Kerzen vor dem ersten bekannten Funding-Zeitpunkt bekommen ``NaN`` - kein
    geratener Wert. Die Indikatoren geben dort ebenfalls NaN zurueck, und die
    Strategie handelt nicht.
    """
    result = frame.copy()
    if funding.empty:
        result["funding_rate"] = float("nan")
        return result

    # Beide Seiten auf dieselbe Zeitaufloesung bringen.
    #
    # Klingt nach Kleinkram, ist aber ein harter Abbruch: Der Umweg ueber
    # Parquet macht aus Nanosekunden Mikrosekunden, und ``merge_asof``
    # verweigert die Arbeit bei ungleichen Typen. In den Unit-Tests faellt das
    # nie auf, weil dort beide Rahmen im Speicher entstehen - erst der echte
    # Durchlauf mit gespeicherten Dateien bringt es zum Vorschein.
    times = pd.to_datetime(result["open_time"], utc=True).astype("datetime64[ns, UTC]")
    known = funding.sort_values("time").copy()
    known["time"] = pd.to_datetime(known["time"], utc=True).astype("datetime64[ns, UTC]")

    merged = pd.merge_asof(
        pd.DataFrame({"time": times}).sort_values("time"),
        known,
        on="time",
        direction="backward",  # nur was schon feststand
    )
    result["funding_rate"] = merged["funding_rate"].to_numpy()
    return result
