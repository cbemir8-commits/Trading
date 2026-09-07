"""Grobe Kerzen gegen feine halten - stimmen die beiden Reihen ueberein?

Die Frage, die das beantwortet
------------------------------
Befund 213 hat ``data/resample.py`` als gebaut und unverdrahtet gefunden und
die Frage offen gelassen: **Gehoeren Tageskerzen abgeleitet oder geladen?**
Sie stand seither unter *gemessen und offen*, mit dem Vermerk, sie beruehre
jede Zahl des Projekts.

Beantwortet wird sie nicht durch Nachdenken, sondern indem man beide Reihen
nebeneinanderlegt. Genau das tut dieses Modul.

Was dabei herauskam (Befund 239)
--------------------------------
Auf den 2.344 gemeinsamen Tagen von BTC und ETH:

    open    2.343 von 2.344 bitgleich
    high    2.343 von 2.344
    low     2.344 von 2.344
    close   2.343 von 2.344

**Die beiden Wege stimmen ueberein.** "Abgeleitet oder geladen" ist damit
keine Frage der Richtigkeit - jedenfalls nicht fuer die Daten, die vorliegen.

Die eine Ausnahme ist der Fund
------------------------------
Es ist in beiden Maerkten **dieselbe** Kerze: die letzte. Die gespeicherte
Tageskerze zum 2026-08-29 traegt 419 von 809 Einheiten Volumen - rund die
Haelfte des Tages, abgebrochen gegen 11:00 UTC - und steht in der Reihe wie
eine volle. ``high`` und ``close`` liegen dadurch 0,48 % und 0,76 % zu tief.

Das ist genau der Fallstrick, vor dem ``resample.py`` in seinem Kopf warnt:

    "Sie handelt damit auf einem Schlusskurs, den es zu diesem Zeitpunkt noch
     nicht gab. Das ist Lookahead, und zwar der unauffaellige: Es betrifft nur
     die letzte Kerze, faellt in keiner Stichprobe auf."

Nur sitzt er nicht im Code, sondern in den **gespeicherten Daten**. ``resample``
wirft angefangene Kerzen weg; der Backfill hat eine geschrieben.

**Und er kostet heute nichts.** Mit und ohne die letzte Tageskerze gerechnet
sind Trades, effektive Stichprobe, Guete, Deflated Sharpe, Gates, Rendite und
Rueckgang bis auf vier Stellen gleich. Der Nachlauf aus Befund 151 und der
Randschnitt aus Befund 152 halten den Datenrand aus der Statistik heraus - sie
sind fuer den Fall gebaut worden und tragen ihn.

Dass es heute nichts kostet, ist aber eine Eigenschaft des Nachlaufs und nicht
der Daten. Wird er kuerzer oder ruecken die Testfenster nach, steht der Fehler
im Ergebnis. Deshalb gibt es diese Pruefung, statt es beim Befund zu belassen.

Was hier **nicht** geprueft wird
--------------------------------
Ob die feine Reihe recht hat. Sie ist der Schiedsrichter, weil sie mehr
Bausteine hat und weil ``resample`` angefangene Kerzen verwirft - nicht, weil
sie aus einer besseren Quelle stammt. Beide kommen von derselben Boerse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from core.models import Interval
from data.resample import resample

#: Die Spalten, auf die es ankommt. ``volume`` steht bewusst nicht dabei: Es
#: unterscheidet sich schon dann, wenn eine Boerse nachtraeglich Trades
#: einbucht, und wuerde die Preisfrage zudecken. Fuer die angefangene Kerze
#: wird es eigens herangezogen.
SPALTEN: tuple[str, ...] = ("open", "high", "low", "close")


@dataclass(frozen=True, slots=True)
class Abweichung:
    """Eine Kerze, in der sich die beiden Wege unterscheiden."""

    zeitpunkt: datetime
    spalte: str
    geladen: float
    abgeleitet: float

    @property
    def relativ(self) -> float:
        if self.geladen == 0:
            return float("inf")
        return self.abgeleitet / self.geladen - 1.0

    def __str__(self) -> str:
        return (
            f"{self.zeitpunkt:%Y-%m-%d %H:%M} {self.spalte:<6} "
            f"geladen {self.geladen:.2f}, abgeleitet {self.abgeleitet:.2f} "
            f"({self.relativ:+.3%})"
        )


@dataclass(slots=True)
class Gegenprobe:
    """Was der Vergleich beider Reihen ergeben hat."""

    verglichen: int
    """Zahl der Kerzen, die in beiden Reihen vorkommen."""

    abweichungen: list[Abweichung] = field(default_factory=list)

    volumenanteil: float | None = None
    """Wieviel Volumen die **letzte** geladene Kerze gegenueber der
    abgeleiteten traegt. ``None``, wenn es keine gemeinsame letzte gibt.

    Unter 1 heisst: Die gespeicherte Kerze deckt weniger als ihr Fenster - sie
    wurde mitten im Zeitraum geschrieben und nie nachgezogen.
    """

    @property
    def einig(self) -> bool:
        return not self.abweichungen

    @property
    def angefangene_randkerze(self) -> bool:
        """Ist die letzte geladene Kerze unvollstaendig?

        Die Schwelle liegt bei 99 %: Boersen buchen Trades gelegentlich
        nachtraeglich ein, und ein Promille Unterschied ist das und kein
        halber Tag.
        """
        return self.volumenanteil is not None and self.volumenanteil < 0.99

    @property
    def betroffene_kerzen(self) -> tuple[datetime, ...]:
        return tuple(sorted({a.zeitpunkt for a in self.abweichungen}))

    def urteil(self) -> str:
        if self.verglichen == 0:
            return "Keine gemeinsamen Kerzen - nichts zu vergleichen."
        teile = [
            f"{self.verglichen - len(self.betroffene_kerzen)} von "
            f"{self.verglichen} Kerzen stimmen ueberein."
        ]
        if self.angefangene_randkerze:
            teile.append(
                f"Die letzte geladene Kerze traegt nur "
                f"{self.volumenanteil:.0%} des Volumens ihres Fensters - sie "
                f"ist angefangen und steht wie eine volle in der Reihe."
            )
        elif self.einig:
            teile.append("Ableiten und Laden fuehren zum selben Ergebnis.")
        return " ".join(teile)


def gegenprobe(
    grob: pd.DataFrame,
    fein: pd.DataFrame,
    *,
    quelle: Interval,
    ziel: Interval,
    toleranz: float = 1e-9,
) -> Gegenprobe:
    """Die grobe Reihe gegen die aus der feinen abgeleitete halten.

    Verglichen wird nur, was in **beiden** vorkommt: Die feine Reihe beginnt
    in diesem Projekt Jahre spaeter, und ein fehlender Zeitraum ist keine
    Abweichung, sondern ein fehlender Zeitraum.

    ``toleranz`` ist relativ. Der Vorgabewert prueft auf bitgleich - das ist
    hier erreichbar, weil beide Reihen aus derselben Quelle stammen, und
    alles andere waere eine Schwelle, hinter der sich etwas verstecken kann.
    """
    if grob.empty or fein.empty:
        return Gegenprobe(verglichen=0)

    abgeleitet = resample(fein, quelle, ziel).set_index("open_time")
    geladen = grob.set_index("open_time")
    gemeinsam = abgeleitet.index.intersection(geladen.index)
    if len(gemeinsam) == 0:
        return Gegenprobe(verglichen=0)

    ergebnis = Gegenprobe(verglichen=len(gemeinsam))
    for spalte in SPALTEN:
        a = abgeleitet.loc[gemeinsam, spalte].astype(float)
        g = geladen.loc[gemeinsam, spalte].astype(float)
        weicht = ((a - g).abs() / g.abs().clip(lower=1e-12)) > toleranz
        for zeitpunkt in gemeinsam[weicht.to_numpy()]:
            ergebnis.abweichungen.append(
                Abweichung(
                    zeitpunkt=zeitpunkt.to_pydatetime(),
                    spalte=spalte,
                    geladen=float(g[zeitpunkt]),
                    abgeleitet=float(a[zeitpunkt]),
                )
            )

    letzte = gemeinsam.max()
    volumen_abgeleitet = float(abgeleitet.loc[letzte, "volume"])
    if volumen_abgeleitet > 0:
        ergebnis.volumenanteil = (
            float(geladen.loc[letzte, "volume"]) / volumen_abgeleitet
        )
    return ergebnis
