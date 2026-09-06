"""Wie viel von seiner **eigenen** Latte raeumt ein Betriebspunkt?

Die Frage
---------
Das Projekt hat zwei Betriebspunkte, auf denen gesucht worden ist:
Tageskerzen und Viertelstunden. Auf welchem lohnt die Suche eher?

Direkt vergleichen laesst sich das nicht. Die Latte des Deflated Sharpe
haengt an der effektiven Stichprobe, und die ist auf den beiden Punkten
voellig verschieden - 115 gegen 1830 (Befund 143/218). Wer eine Guete von
hier gegen eine Latte von dort haelt, macht genau den Fehler aus Befund 190:
Dort stand ein auf Tageskerzen gemessener Bestand gegen eine Gerade aus 36
Viertelstunden-Regeln, und es kam ein Vorsprung von "+5,64 Reststreuungen"
heraus, der nichts bedeutet hat.

Was sich vergleichen laesst
---------------------------
Ein **Verhaeltnis**, je Betriebspunkt fuer sich gerechnet:

    Erfuellungsgrad = erreichte Guete / noetige Guete

Beide Zahlen stammen vom selben Punkt, mit dessen eigener Stichprobe und
dessen eigener Verteilungsform. Das Ergebnis ist dimensionslos, und erst
diese Verhaeltnisse duerfen nebeneinanderstehen.

**Es ist trotzdem keine Aussage ueber die Kerzenlaengen**, sondern ueber
das, was auf ihnen **gefunden** wurde. Auf Tageskerzen steht der beste Fund
aus Jahren, auf Viertelstunden der beste aus 36 gemessenen Regeln.

Was gemessen ist
----------------
    Betriebspunkt      beste Regel                   n_eff   Guete   Latte   Anteil
    Tageskerzen        Bestand (Befund 152)            115   2,904   3,611    0,804
    15 Minuten         Trendbeteiligung mit Puffer     584   0,744   3,964    0,188
    15 Minuten         Seltener grosser Ausbruch      1065   0,156   4,065    0,038
    15 Minuten         Starker Trend, Momentum        1818  -0,780   4,138   -0,188

**Die feinere Kerze senkt die Latte je Trade und nicht insgesamt.** Bei
n_eff 1830 verlangt die Schwelle 0,0968 je Trade statt 0,3406 - ein Drittel.
Gefunden wurde dort aber so viel weniger, dass der Abstand groesser ist und
nicht kleiner: 0,188 gegen 0,804, also gut das Vierfache.

Das widerspricht Befund 171 nicht, es beziffert ihn. Dort steht *"die
Vielfalt ist da und sie verliert"* - hier steht, um welchen Faktor.

Kostet keinen Versuch: gerechnet auf veroeffentlichten Zahlen.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["GEMESSEN", "Betriebspunkt", "erfuellungsgrad"]


def erfuellungsgrad(guete: float, latte: float) -> float | None:
    """Welcher Anteil der noetigen Guete ist erreicht?

    ``None`` bei einer Latte von null oder darunter: Ein Anteil an nichts ist
    keine Auskunft, und eine Division waere eine erfundene Zahl.

    Negative Werte bleiben stehen. Eine Regel mit negativer Guete hat nicht
    "null Prozent geschafft", sie laeuft in die falsche Richtung, und das
    gehoert sichtbar.
    """
    if latte <= 0:
        return None
    return guete / latte


@dataclass(frozen=True, slots=True)
class Betriebspunkt:
    """Der beste gemessene Fund auf einer Kerzenlaenge, mit seiner Latte."""

    name: str
    intervall: str
    regel: str
    effektiv: int
    guete: float
    latte: float
    befund: int

    def __post_init__(self) -> None:
        if self.effektiv <= 0:
            raise ValueError(f"{self.regel}: keine Stichprobe, keine Aussage.")
        if self.latte <= 0:
            raise ValueError(
                f"{self.regel}: Latte {self.latte} - eine Schwelle bei null "
                f"oder darunter waere keine."
            )

    @property
    def anteil(self) -> float | None:
        return erfuellungsgrad(self.guete, self.latte)

    @property
    def je_trade(self) -> float:
        """Die erreichte Guete je Trade - ``guete`` ist die Summe ueber n."""
        return self.guete / self.effektiv**0.5

    @property
    def noetig_je_trade(self) -> float:
        """Was die Schwelle hier **je Trade** verlangt.

        Diese Zahl faellt mit wachsender Stichprobe, die Latte insgesamt
        nicht. Genau darin liegt der Reiz der feineren Kerze - und er reicht
        nicht.
        """
        return self.latte / self.effektiv**0.5

    @property
    def luecke(self) -> float | None:
        """Um welchen Anteil muesste die Guete je Trade steigen?

        **Die Zahl, die Befund 70 mit "+13 %" beziffert hat** - gemessen dort
        bei Guete 0,260 und n_eff 152. Beides ist ueberholt; heute sind es
        +24,3 % (Befund 222). Deshalb steht sie hier als Eigenschaft und
        nicht als Text: Sie haengt an drei Groessen, die sich alle bewegt
        haben.

        ``None`` bei einer Guete von null oder darunter - "um wieviel
        Prozent besser als nichts" ist keine Auskunft.
        """
        if self.je_trade <= 0:
            return None
        return self.noetig_je_trade / self.je_trade - 1.0

    def __str__(self) -> str:
        anteil = self.anteil
        return (
            f"{self.regel:30} {self.intervall:>3}  n_eff {self.effektiv:>4}  "
            f"Guete {self.guete:+.3f}  Latte {self.latte:.3f}  "
            f"Anteil {anteil:+.3f}" if anteil is not None else f"{self.regel}: -"
        )


#: Die besten gemessenen Funde je Betriebspunkt.
#:
#: Tageskerzen aus ``referenz.SPOTPUNKT`` (Befund 152), Viertelstunden aus
#: der Tabelle in Befund 171. Beide Latten sind dort veroeffentlicht; die des
#: Bestands ist mit ``verbund.noetige_guete`` auf seiner eigenen Stichprobe
#: und seinen eigenen Momenten nachgerechnet.
GEMESSEN: tuple[Betriebspunkt, ...] = (
    Betriebspunkt(
        name="Tageskerzen",
        intervall="D",
        regel="Bestand (Spot wie gebaut)",
        effektiv=115,
        guete=2.904,
        latte=3.611,
        befund=152,
    ),
    Betriebspunkt(
        name="15 Minuten",
        intervall="15",
        regel="Trendbeteiligung mit Puffer",
        effektiv=584,
        guete=0.744,
        latte=3.964,
        befund=171,
    ),
    Betriebspunkt(
        name="15 Minuten",
        intervall="15",
        regel="Seltener grosser Ausbruch",
        effektiv=1065,
        guete=0.156,
        latte=4.065,
        befund=171,
    ),
    Betriebspunkt(
        name="15 Minuten",
        intervall="15",
        regel="Starker Trend, Momentum",
        effektiv=1818,
        guete=-0.780,
        latte=4.138,
        befund=171,
    ),
)


def bester_je_intervall() -> dict[str, Betriebspunkt]:
    """Der hoechste Erfuellungsgrad je Kerzenlaenge."""
    aus: dict[str, Betriebspunkt] = {}
    for p in GEMESSEN:
        vorher = aus.get(p.intervall)
        if vorher is None or (p.anteil or 0) > (vorher.anteil or 0):
            aus[p.intervall] = p
    return aus


def urteil() -> str:
    """Auf welchem Betriebspunkt steht die Suche naeher am Ziel?"""
    beste = bester_je_intervall()
    if len(beste) < 2:
        return "Nur ein Betriebspunkt gemessen - kein Vergleich."
    geordnet = sorted(beste.values(), key=lambda p: -(p.anteil or 0))
    vorn, hinten = geordnet[0], geordnet[-1]
    faktor = (vorn.anteil or 0) / (hinten.anteil or 1)
    return (
        f"**Naeher am Ziel: {vorn.name}.** Dort raeumt der beste Fund "
        f"{vorn.anteil:.3f} seiner Latte, auf {hinten.name} sind es "
        f"{hinten.anteil:.3f} - das {faktor:.1f}-fache. Die feinere Kerze "
        f"senkt die Latte **je Trade** ({hinten.noetig_je_trade:.4f} gegen "
        f"{vorn.noetig_je_trade:.4f}) und nicht insgesamt; gefunden wurde "
        f"dort so viel weniger, dass der Abstand groesser ist. Verglichen "
        f"werden Verhaeltnisse, jedes auf seiner eigenen Stichprobe "
        f"gerechnet - nicht Guete gegen fremde Latte (Befund 190)."
    )
