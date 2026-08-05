"""Kerzen zu groesseren Kerzen zusammenfassen.

Wozu
----
Die Zahl der Trades ist keine Nebensache. Der Deflated Sharpe misst, wie
sicher ein Vorteil echt ist, und haengt an ``sqrt(n-1)``: Derselbe Vorteil
wird mit mehr Beobachtungen glaubwuerdiger, ohne dass sich an der Regel
etwas aendert. Gemessen am Spitzenkandidaten:

    156 Trades   Deflated Sharpe 0,848
    200 Trades                   0,957   bestanden
    312 Trades                   0,999

Mehr Trades aus **schlechteren Maerkten** zu holen funktioniert nicht - das
ist gemessen und in ``strategies/BEFUND.md`` festgehalten. Bleibt der Weg
ueber die Zeitachse: dieselbe Regel, dieselben zwei Maerkte, kuerzere Kerzen.

Warum nicht einfach jedes Intervall einzeln holen
-------------------------------------------------
Weil das vier Backfills waeren, die auseinanderlaufen koennen. Aus einer
einzigen 15-Minuten-Reihe abgeleitet, sind alle Intervalle **per
Konstruktion** konsistent: Die Stunden-Kerze enthaelt genau die vier
Viertelstunden, die auch der Backtest auf 15 Minuten sehen wuerde.

Der Fallstrick, um den es hier eigentlich geht
----------------------------------------------
Eine angefangene Kerze. Fasst man 15-Minuten-Kerzen zu Stunden zusammen und
die Reihe endet um 10:30, dann enthaelt die Stundenkerze ab 10:00 nur zwei
statt vier Viertelstunden. Ihr ``close`` ist der Kurs von 10:45 - aber eine
Strategie, die diese Kerze sieht, glaubt, es sei der Schlusskurs um 11:00.

Sie handelt damit auf einem Schlusskurs, den es zu diesem Zeitpunkt noch
nicht gab. Das ist Lookahead, und zwar der unauffaellige: Es betrifft nur
die letzte Kerze, faellt in keiner Stichprobe auf und verschiebt trotzdem
jedes Ergebnis am rechten Rand - also genau dort, wo der Walk-Forward seine
Testfenster hat.

``resample`` wirft angefangene Kerzen deshalb **weg**. Lieber eine Kerze
weniger als eine, die es so nie gab.
"""

from __future__ import annotations

import pandas as pd
import structlog

from core.models import Interval

log = structlog.get_logger(__name__)

#: Wie die sieben Spalten zusammengefasst werden. ``open`` ist der erste
#: Kurs im Fenster, ``close`` der letzte - alles andere waere eine andere
#: Kerze.
AGGREGAT = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
    "turnover": "sum",
}


def teilbar(quelle: Interval, ziel: Interval) -> bool:
    """Ob ``ziel`` ein ganzes Vielfaches von ``quelle`` ist.

    Aus 15-Minuten-Kerzen lassen sich Stunden bilden (4 Stueck), aber keine
    50-Minuten-Kerzen. Wer es doch versucht, bekaeme Kerzen mit wechselnder
    Zahl von Bausteinen - mal drei, mal vier - und damit eine Reihe, die
    nicht ist, was sie zu sein vorgibt.

    Woche und Monat sind ausgenommen: Sie haben keine feste Laenge in
    Minuten, und ``pandas`` bildet sie ohnehin kalendarisch.
    """
    if quelle in (Interval.W1, Interval.MN1):
        return False
    if ziel in (Interval.W1, Interval.MN1):
        return True
    q = quelle.duration.total_seconds()
    z = ziel.duration.total_seconds()
    return z > q and z % q == 0


#: Uebersetzung in die Sprache von ``pandas``. Nur was hier steht, kann
#: erzeugt werden - eine geschlossene Liste statt einer Zeichenkette, die
#: irgendwo zusammengebaut wird.
_REGEL = {
    Interval.M1: "1min",
    Interval.M3: "3min",
    Interval.M5: "5min",
    Interval.M15: "15min",
    Interval.M30: "30min",
    Interval.H1: "1h",
    Interval.H2: "2h",
    Interval.H4: "4h",
    Interval.H6: "6h",
    Interval.H12: "12h",
    Interval.D1: "1D",
    Interval.W1: "1W",
    Interval.MN1: "1MS",
}


def resample(
    frame: pd.DataFrame,
    quelle: Interval,
    ziel: Interval,
    *,
    vollstaendig: bool = True,
) -> pd.DataFrame:
    """Kerzen zu groesseren zusammenfassen.

    ``vollstaendig=True`` behaelt nur Kerzen, die aus der vollen Zahl
    Bausteine bestehen. Das ist der Vorgabewert und sollte es bleiben - siehe
    den Abschnitt zum Lookahead oben im Modul.

    Es entfernt zwei Sorten unvollstaendiger Kerzen:

    * die letzte, wenn die Reihe mitten in einem Fenster endet
    * die erste, wenn die Reihe mitten in einem Fenster beginnt
    * jede, in die wegen einer Datenluecke Kerzen fehlen

    Die dritte ist der Grund, warum hier gezaehlt und nicht nur der Rand
    geschnitten wird: Boersendaten haben Luecken, und eine Vier-Stunden-Kerze
    aus zwei Viertelstunden sieht in der Tabelle aus wie jede andere.

    Fehlt eine Kerze ganz - kein einziger Baustein im Fenster -, entsteht
    auch keine. Sie wird **nicht** mit dem letzten Kurs aufgefuellt: Eine
    Kerze, in der nicht gehandelt wurde, gab es nicht, und der Backtest soll
    dort nichts tun koennen.
    """
    if not teilbar(quelle, ziel):
        raise ValueError(
            f"{ziel.label} laesst sich nicht aus {quelle.label} bilden - "
            "das Ziel muss ein ganzes Vielfaches der Quelle sein."
        )
    if frame.empty:
        return frame.copy()

    fehlend = {"open_time", *AGGREGAT} - set(frame.columns)
    if fehlend:
        raise ValueError(f"Spalten fehlen: {', '.join(sorted(fehlend))}")

    indiziert = frame.set_index("open_time").sort_index()
    gruppen = indiziert.resample(_REGEL[ziel], label="left", closed="left")

    grob = gruppen.agg(AGGREGAT)
    # Leere Fenster entstehen bei Datenluecken. ``agg`` legt dafuer Zeilen
    # mit NaN an - die gehoeren weg, nicht aufgefuellt.
    grob = grob.dropna(subset=["open"])

    if vollstaendig:
        bausteine = gruppen.size().reindex(grob.index)
        erwartet = _bausteine_je_kerze(quelle, ziel, grob.index)
        grob = grob[bausteine.to_numpy() >= erwartet]

    grob = grob.reset_index()
    log.debug(
        "resample.fertig",
        von=quelle.label,
        nach=ziel.label,
        quelle_kerzen=len(frame),
        ziel_kerzen=len(grob),
    )
    return grob[["open_time", *AGGREGAT]]


def _bausteine_je_kerze(quelle: Interval, ziel: Interval, index: pd.DatetimeIndex):
    """Wie viele Quellkerzen in eine Zielkerze gehoeren.

    Bei festen Intervallen ist das eine Zahl. Bei Woche und Monat nicht -
    Monate haben verschieden viele Tage -, deshalb wird dort je Kerze
    gerechnet.
    """
    q = quelle.duration.total_seconds()
    if ziel not in (Interval.W1, Interval.MN1):
        return int(ziel.duration.total_seconds() // q)

    naechster = index.to_series().shift(-1)
    # Die letzte Kerze hat keinen Nachfolger; ihre Laenge kommt aus dem
    # Kalender.
    laenge = (naechster - index.to_series()).dt.total_seconds()
    laenge = laenge.fillna(
        (index + pd.tseries.frequencies.to_offset(_REGEL[ziel])).to_series().to_numpy()
        - index.to_numpy()
    )
    if laenge.dtype.kind == "m":
        laenge = laenge.dt.total_seconds()
    return (laenge // q).to_numpy()
