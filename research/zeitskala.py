"""Auf welcher Zeitskala sitzt die Abhaengigkeit - und ist sie ausgemessen?

Warum es das gibt
-----------------
Das Gate teilt die Trades in drei Einteilungen und nimmt die strengste
(Befund 135): Walk-Forward-Fenster, Gleichzeitigkeit, Kalenderquartal. Welche
gewinnt, haengt davon ab, auf welcher **Zeitskala** die Abhaengigkeit sitzt -
und die ist nie vermessen worden, sondern geraten.

Beim Nachmessen (Befund 143) kam heraus, dass sie nicht an der Kerzenlaenge
haengt, sondern an der **Handelsdichte**:

    Tageskerzen, 152 Trades in 9 Jahren
        Kalendertag        1,1 je Block   ICC 0,956   Quote 1,000
        Kalenderwoche      1,4            ICC 0,718   Quote 0,954
        Kalendermonat      2,4            ICC 0,515   Quote 0,816
        Kalenderquartal    4,8            ICC 0,257   Quote 0,737   <-- streng
        Halbjahr           9,5            ICC 0,087   Quote 0,921
        Kalenderjahr      16,9            ICC 0,052   Quote 1,000

    15-Minuten-Kerzen, 1985 Trades in 6,3 Jahren
        Gleichzeitigkeit   1,2 je Block   ICC 0,601   Quote 0,922   <-- streng
        Kalendertag        2,2            ICC 0,105   Quote 0,935
        Kalenderwoche      7,8            ICC 0,013   Quote 1,000
        Kalendermonat     32,5            ICC 0,006   Quote 1,000
        Kalenderquartal   94,5            ICC 0,006   Quote 0,968

Auf Tageskerzen sitzt sie beim Quartal, auf Fuenfzehnminutenkerzen bei der
Gleichzeitigkeit - **gegenlaeufige Enden derselben Leiter.** Wer selten
handelt, traegt Abhaengigkeit ueber Monate; wer oft handelt, ueber Stunden.

Ueber alle vierzehn Genome der Generationen 6 und 7 liegt die Behaltequote auf
Fuenfzehnminutenkerzen zwischen 0,699 und 0,992, **Median 0,903** - gegen
0,737 auf Tageskerzen. Nur eines der vierzehn liegt darunter.

Wozu die Leiter taugt
---------------------
Zu einer Pruefung, die es vorher nicht gab: **Liegt die strengste Einteilung
am Rand des Gemessenen?** Dann ist die Zahl kein Minimum, sondern das Ende
des Massbands - jenseits davon koennte es weiter fallen, und niemand wuesste
es.

Genau diese Sorge gab es fuer das Quartal, und sie war unbegruendet: Halbjahr
(0,921) und Jahr (1,000) liegen wieder hoeher, das Quartal ist ein echtes
Minimum. Aber das musste man messen, und ``am_rand`` sagt es beim naechsten
Mal von selbst.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

__all__ = ["STUFEN", "Skalenleiter", "Skalenstufe", "nach_kalender"]

#: Die Leiter, von fein nach grob. Der Schluessel bildet einen Zeitpunkt auf
#: den Abschnitt ab, zu dem er gehoert.
STUFEN: tuple[tuple[str, object], ...] = (
    ("Kalendertag", lambda z: (z.year, z.month, z.day)),
    ("Kalenderwoche", lambda z: z.isocalendar()[:2]),
    ("Kalendermonat", lambda z: (z.year, z.month)),
    ("Kalenderquartal", lambda z: (z.year, (z.month - 1) // 3)),
    ("Halbjahr", lambda z: (z.year, (z.month - 1) // 6)),
    ("Kalenderjahr", lambda z: (z.year,)),
)


def nach_kalender(trades: list, schluessel) -> list[list[float]]:
    """Trade-Ergebnisse nach einem Kalenderabschnitt des **Ausstiegs** buendeln.

    Wie ``gates.quartalsbloecke``, nur mit frei waehlbarer Skala. Gebuendelt
    wird nach dem Ausstieg: Dort steht das Ergebnis fest.
    """
    eimer: dict[tuple, list[float]] = {}
    for t in trades:
        zeit: datetime = t.exit_time
        eimer.setdefault(tuple(schluessel(zeit)), []).append(float(t.net_pnl))
    return [eimer[k] for k in sorted(eimer)]


@dataclass(frozen=True, slots=True)
class Skalenstufe:
    """Eine Sprosse: eine Zeitskala und was die Einteilung dort uebrig laesst."""

    name: str
    bloecke: int
    roh: int
    effektiv: int
    icc: float

    def __post_init__(self) -> None:
        if self.effektiv > self.roh:
            raise ValueError(
                f"{self.name}: {self.effektiv} unabhaengige aus {self.roh} "
                f"Trades - das geht nicht."
            )

    @property
    def quote(self) -> float:
        return self.effektiv / self.roh if self.roh else 1.0

    @property
    def je_block(self) -> float:
        return self.roh / self.bloecke if self.bloecke else 0.0


@dataclass(frozen=True, slots=True)
class Skalenleiter:
    """Die Sprossen in der Reihenfolge, in der sie gemessen wurden."""

    stufen: tuple[Skalenstufe, ...]

    @property
    def strengste(self) -> Skalenstufe | None:
        """Die Sprosse mit der kleinsten Stichprobe - die das Gate naehme."""
        return min(self.stufen, key=lambda s: s.effektiv, default=None)

    @property
    def am_rand(self) -> bool | None:
        """Liegt die strengste Sprosse am Ende der gemessenen Leiter?

        **Dann ist die Zahl kein Minimum, sondern das Ende des Massbands.**
        Jenseits davon koennte die Stichprobe weiter fallen, und die
        Zulassung stuende auf einer Groesse, die noch nicht ausgemessen ist.

        ``None`` bei weniger als drei Sprossen - mit zweien ist jede am Rand,
        und das waere eine Warnung ohne Inhalt.
        """
        if len(self.stufen) < 3:
            return None
        streng = self.strengste
        return streng is self.stufen[0] or streng is self.stufen[-1]

    def als_tabelle(self) -> str:
        kopf = (
            f"  {'Einteilung':<18} {'Bloecke':>7} {'je Block':>9} "
            f"{'ICC':>7} {'n_eff':>6} {'Quote':>6}"
        )
        zeilen = [kopf, "  " + "-" * (len(kopf) - 2)]
        streng = self.strengste
        for s in self.stufen:
            marke = "  <-- streng" if s is streng else ""
            zeilen.append(
                f"  {s.name:<18} {s.bloecke:>7} {s.je_block:>9.1f} "
                f"{s.icc:>7.3f} {s.effektiv:>6} {s.quote:>6.3f}{marke}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        streng = self.strengste
        if streng is None:
            return "Keine Sprosse gemessen - kein Urteil."
        satz = (
            f"Die Abhaengigkeit sitzt bei '{streng.name}' "
            f"({streng.je_block:.1f} Trades je Block): {streng.effektiv} von "
            f"{streng.roh} bleiben uebrig, Quote {streng.quote:.3f}."
        )
        if self.am_rand:
            satz += (
                " **Diese Sprosse liegt am Rand der gemessenen Leiter** - die "
                "Zahl ist damit kein Minimum, sondern das Ende des Massbands. "
                "Eine Sprosse weiter koennte weniger uebrig bleiben."
            )
        elif self.am_rand is False:
            satz += (
                " Sie liegt zwischen zwei milderen Sprossen, ist also ein "
                "echtes Minimum und kein Randeffekt."
            )
        return satz
