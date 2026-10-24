"""Wie oft faellt ein Zwoelfmonatsfenster unter die Schwelle - und was sagt das?

Die Frage, die 395 offen liess
------------------------------
Am massgeblichen Punkt haelt "Schlechtestes Jahr" mit 0,39 Punkten Reserve,
und diese Reserve ist ein Guthaben: Das Gate nimmt das Minimum ueber alle
Fenster, sie kann also nur kleiner werden (Befund 395/396). Ob 0,39 Punkte
viel oder wenig sind, haengt an der **Rate** - und die stand nirgends.

Hier steht sie, als das, was sie ist: eine **Schranke**.

Zwei Zahlen, und beide sind kleiner als sie aussehen
----------------------------------------------------
**Erstens: Es sind sieben unabhaengige Jahre, nicht neun.** Die
Zulassungsreihe hat 3301 Balken, aber die Kurve des Walk-Forward beginnt erst
am 19.08.2018 - das erste Jahr bezahlt das erste Trainingsfenster. Von
2018-08-19 bis 2026-08-18 sind 2921 Tage, also 7,9973 Jahre; das achte
disjunkte Fenster wuerde am 19.08.2026 enden und verfehlt das Kurvenende um
**einen Tag**. In Befund 396 habe ich "rund neun unabhaengige Jahre"
geschrieben, aus der Reihenlaenge geschlossen statt aus der Kurve gezaehlt.

**Zweitens: Die Phase verschiebt das schlechteste Jahr um 17 Punkte.** Ueber
alle 365 Verschiebungen der Jahresgrenzen reicht das schlechteste disjunkte
Jahr von **-9,61 %** bis **+7,55 %** - dieselbe Kurve, dieselbe Strategie, nur
andere Schnittpunkte. Bei Phase 0 (ab Kurvenbeginn) sieht es harmlos aus:

    2018-08-19 bis 2019-08-19      3,07 %
    2019-08-19 bis 2020-08-19     36,78 %
    2020-08-19 bis 2021-08-19     36,20 %
    2021-08-19 bis 2022-08-19     -1,87 %
    2022-08-19 bis 2023-08-19     12,51 %
    2023-08-19 bis 2024-08-19     14,31 %
    2024-08-19 bis 2025-08-19     25,04 %

Ein einziges negatives Jahr, und das mit -1,87 %. Das Gate rechnet **nicht**
so: Es nimmt das Minimum ueber alle 2557 gleitenden Fenster, also die
unguenstigste Phase, und das sind -9,61 %. Die Entscheidung dahinter steht
unter "Feste Schwellen auf laufenden Extrema"; was sie kostet, sind diese
17,16 Punkte.

Was sich daraus schranken laesst
--------------------------------
In keinem der sieben Jahre ist ein Zwoelfmonatsfenster unter -10 % gefallen -
null von sieben. Die exakte einseitige Schranke dazu:

    Irrtum 5 %    Rate < 34,8 % im Jahr
    Irrtum 10 %   Rate < 28,0 % im Jahr

Und ueber den Horizont, den der Deflated Sharpe braucht (5,89 Jahre,
``referenz.AUSSICHT``):

    bei der 5-%-Schranke    92,0 % Wahrscheinlichkeit mindestens eines Treffers
    bei der 10-%-Schranke   85,6 %

**Das ist keine Prognose.** Eine Schranke sagt, was die Daten nicht
ausschliessen, nicht was zu erwarten ist; der Punktschaetzer aus null Treffern
ist null. Beides gehoert hierher, und der Satz, der daraus folgt, ist
unbequem: Das Projekt kann **nicht zeigen**, dass sein einziger offener Weg -
Evidenz sammeln, bis der Deflated Sharpe traegt - das eigene
Jahres-Gate uebersteht. Sieben saubere Jahre schranken die Rate auf gut ein
Drittel, und ein einziges Jahr wie 2022, nur um 0,4 Punkte schlechter, nimmt
die Reserve.

Dass das schlechteste Jahr **allein** steht - 4,57 Punkte bis zum naechsten
getrennten Fenster (Befund 396) -, macht es nicht besser und nicht
schlimmer: Eine Spitze sagt, dass es an einer Ausrichtung haengt, nicht wie
oft so eine Ausrichtung vorkommt. Genau diese Luecke schliesst die Schranke,
so weit sie sich schliessen laesst.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

__all__ = [
    "MONATE",
    "Jahresfolge",
    "schranke",
    "ueber_horizont",
    "unabhaengige_jahre",
]

#: Die Fensterbreite des Gates.
MONATE: int = 12


@dataclass(frozen=True, slots=True)
class Jahresfolge:
    """Disjunkte Zwoelfmonatsfenster einer Kurve, zu einer Phase."""

    versatz: int
    fenster: tuple[tuple[pd.Timestamp, pd.Timestamp, float], ...]

    @property
    def anzahl(self) -> int:
        return len(self.fenster)

    @property
    def renditen(self) -> tuple[float, ...]:
        return tuple(w for *_, w in self.fenster)

    @property
    def schlechtestes(self) -> float:
        return min(self.renditen) if self.fenster else float("nan")

    def unter(self, schwelle_pct: float) -> int:
        """Wie viele dieser Jahre unter der Schwelle liegen."""
        return sum(1 for w in self.renditen if w < schwelle_pct)


def unabhaengige_jahre(
    kurve: pd.Series, *, versatz: int = 0, monate: int = MONATE
) -> Jahresfolge:
    """Aufeinanderfolgende Fenster, die sich **nicht** ueberlappen.

    Das Ende eines Fensters ist der Anfang des naechsten. Angefangen wird am
    ``versatz``-ten Kurvenpunkt; unvollstaendige Fenster am Ende fallen weg,
    denn ein halbes Jahr ist keine Beobachtung dieser Art.

    Gezaehlt wird an der **Kurve**, nicht an der Kerzenreihe: Das erste Jahr
    der Reihe bezahlt das erste Trainingsfenster und steht nicht in der Kurve
    (Befund 397 - in 396 stand "rund neun", gemeint waren sieben).
    """
    if len(kurve) < 2 or versatz >= len(kurve) - 1:
        return Jahresfolge(versatz=versatz, fenster=())

    werte = kurve.to_numpy(dtype=float)
    index = kurve.index
    aus: list[tuple[pd.Timestamp, pd.Timestamp, float]] = []
    i = versatz
    start = index[versatz]
    while True:
        ziel = start + pd.DateOffset(months=monate)
        if ziel > index[-1]:
            break
        j = int(index.searchsorted(ziel, side="right")) - 1
        if j <= i or werte[i] <= 0:
            break
        aus.append((index[i], index[j], (werte[j] / werte[i] - 1.0) * 100.0))
        i, start = j, index[j]
    return Jahresfolge(versatz=versatz, fenster=tuple(aus))


def schranke(treffer: int, beobachtungen: int, *, irrtum: float = 0.05) -> float:
    """Die einseitige obere Schranke der Rate - exakte Binomialinversion.

    Gesucht ist das groesste ``p``, bei dem ``P(X <= treffer)`` noch
    mindestens ``irrtum`` betraegt. Fuer ``treffer = 0`` gibt es die
    geschlossene Form ``1 - irrtum**(1/n)``; gerechnet wird trotzdem
    allgemein, damit die Zahl auch dann noch stimmt, wenn irgendwann ein
    Treffer dasteht.

    **Es ist eine Schranke, kein Schaetzer.** Bei null Treffern ist der
    Punktschaetzer null, und die Schranke sagt nur, was die Beobachtungen
    nicht ausschliessen.
    """
    if beobachtungen <= 0:
        raise ValueError("Ohne Beobachtungen gibt es keine Schranke.")
    if not 0 <= treffer <= beobachtungen:
        raise ValueError(
            f"{treffer} Treffer aus {beobachtungen} Beobachtungen ist keine Zahl."
        )
    if not 0 < irrtum < 1:
        raise ValueError("Der Irrtum liegt zwischen null und eins.")
    if treffer == beobachtungen:
        return 1.0

    def cdf(p: float) -> float:
        return math.fsum(
            math.comb(beobachtungen, k) * p**k * (1 - p) ** (beobachtungen - k)
            for k in range(treffer + 1)
        )

    tief, hoch = 0.0, 1.0
    for _ in range(200):
        mitte = (tief + hoch) / 2
        if cdf(mitte) >= irrtum:
            tief = mitte
        else:
            hoch = mitte
    return tief


def ueber_horizont(rate: float, jahre: float) -> float:
    """Wahrscheinlichkeit mindestens eines Treffers in ``jahre`` Jahren.

    Unabhaengige Jahre mit gleicher Rate - genau die Annahme, unter der auch
    die Schranke gerechnet ist. Mehr steckt nicht darin, und weniger wuerde
    ohne eine zweite Annahme nicht gehen.
    """
    if not 0 <= rate <= 1:
        raise ValueError("Eine Rate liegt zwischen null und eins.")
    if jahre < 0:
        raise ValueError("Ein Horizont liegt nicht in der Vergangenheit.")
    return 1.0 - (1.0 - rate) ** jahre
