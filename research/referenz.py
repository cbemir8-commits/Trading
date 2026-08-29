"""Der Referenzpunkt des Projekts - an **einer** Stelle.

Warum es das gibt
-----------------
Befund 135 hat das Deflated-Sharpe-Gate strenger gemacht: Die effektive
Stichprobe faellt von 152 auf 112, der Deflated Sharpe von 0,8640 auf 0,6026.

Danach standen **einundzwanzig Stellen in acht Modulen** weiter auf 0,8640.
Jede zitierte korrekt einen Befund; wer sie las, fand trotzdem den Stand von
gestern. Das ist genau die Falle aus Befund 130 - dort hat ein Registereintrag
auf eine ueberholte Tabelle gezeigt und zwei Laeufe hintereinander in die Irre
gefuehrt -, diesmal eine Ebene tiefer, in den Modulkoepfen.

Ein Laborbuch darf alte Zahlen tragen: Es ist ein Protokoll. Ein Modulkopf
nicht: Er wird als Stand gelesen.

Was hier steht
--------------
Die Zahlen des **massgeblichen** Betriebspunkts, mit der Fundstelle, aus der
sie stammen. Wer sie zitiert, zitiert von hier - und findet damit auch, was
sie ueberholt hat.

**Sie werden gepflegt, nicht gemessen.** Gemessen wird im Lauf; hier steht,
was zuletzt herauskam, damit ein Text nicht raten muss. Ein Test vergleicht
die Angabe mit dem, was das Gate heute liefert - laeuft sie weg, faellt es
dort auf.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["AUSSICHT", "SPOTPUNKT", "UEBERHOLT", "Aussicht", "Referenzpunkt", "veraltet"]


@dataclass(frozen=True, slots=True)
class Referenzpunkt:
    """Ein gemessener Stand mit seiner Fundstelle."""

    name: str
    befund: int
    trades: int
    effektiv: int
    guete: float
    dsr: float
    bestanden: int
    gesamt: int
    versuche: int
    schwelle: float = 0.95

    def __post_init__(self) -> None:
        if self.effektiv > self.trades:
            raise ValueError(
                f"{self.name}: {self.effektiv} unabhaengige Beobachtungen aus "
                f"{self.trades} Trades - das geht nicht."
            )
        if self.befund <= 0:
            raise ValueError(f"{self.name} ohne Fundstelle ist eine Behauptung.")

    @property
    def luecke(self) -> float:
        """Was zur Schwelle fehlt."""
        return self.schwelle - self.dsr

    def als_zeile(self) -> str:
        return (
            f"{self.name:<24} {self.trades:>4} Trades, n = {self.effektiv:>3}, "
            f"Guete {self.guete:.4f}, DSR {self.dsr:.4f}, "
            f"{self.bestanden}/{self.gesamt}  (Befund {self.befund})"
        )


#: Der massgebliche Punkt: Spot, kein Funding, kein Hebel (Befund 108),
#: Deflated-Sharpe-Gate mit Quartalseinteilung (Befund 135), Nachlauf ueber
#: vier Fensterlaengen und zensierte Trades ausserhalb der Statistik
#: (Befund 151/152).
SPOTPUNKT = Referenzpunkt(
    name="Spot wie gebaut",
    befund=152,
    trades=156,
    effektiv=115,
    guete=0.2708,
    dsr=0.5881,
    bestanden=9,
    gesamt=11,
    versuche=198,
)

#: Staende, die einmal massgeblich waren und es nicht mehr sind. Wer einen
#: dieser Werte in einem Modulkopf liest, liest Geschichte.
UEBERHOLT: tuple[Referenzpunkt, ...] = (
    Referenzpunkt(
        name="Spot, vor Befund 152",
        befund=135,
        trades=152,
        effektiv=112,
        guete=0.2765,
        dsr=0.6026,
        bestanden=9,
        gesamt=11,
        versuche=198,
    ),
    Referenzpunkt(
        name="Spot, vor Befund 135",
        befund=108,
        trades=152,
        effektiv=152,
        guete=0.2765,
        dsr=0.8640,
        bestanden=9,
        gesamt=11,
        versuche=198,
    ),
    Referenzpunkt(
        name="Perpetual, vor Befund 108",
        befund=54,
        trades=152,
        effektiv=152,
        guete=0.2597,
        dsr=0.7641,
        bestanden=7,
        gesamt=11,
        versuche=198,
    ),
)


@dataclass(frozen=True, slots=True)
class Aussicht:
    """Wie weit es bis zur Schwelle ist - in Beobachtungen und in Tagen.

    **Die Tage sind eine Untergrenze, keine Schaetzung.** Gerechnet wird mit
    der effektiven Sammelrate des laengsten gemessenen Fensters, und die
    faellt, je laenger die Historie wird (Befund 138):

        Historie   Quartale      p   Anteil   eff je 1000 Tage
         1451 d          12  1,0000    1,000               35,8
         1816 d          16  0,2110    1,000               39,6
         2320 d          21  0,0645    1,000               44,4
         2547 d          24  0,0255    0,901               39,3
         2912 d          28  0,0200    0,876               41,2
         3277 d          32  0,0050    0,737               34,2

    Mehr Historie heisst mehr Quartale, mehr Quartale heisst eine engere
    Permutationsnull, und eine engere Null sieht mehr Abhaengigkeit. Der
    Anteil sinkt also weiter, waehrend man wartet - und die noetige Zeit
    waechst mit. Wie stark, ist von hier aus nicht messbar; deshalb steht hier
    eine Untergrenze und kein Termin.
    """

    noetig: int
    heute: int
    rate_je_tausend_tage: float
    befund: int

    def __post_init__(self) -> None:
        if self.rate_je_tausend_tage <= 0:
            raise ValueError("Ohne Sammelrate laesst sich keine Zeit rechnen.")
        if self.befund <= 0:
            raise ValueError("Eine Aussicht ohne Fundstelle ist eine Behauptung.")

    @property
    def fehlend(self) -> int:
        return max(self.noetig - self.heute, 0)

    @property
    def tage(self) -> int:
        return round(1000.0 * self.fehlend / self.rate_je_tausend_tage)

    @property
    def jahre(self) -> float:
        return self.tage / 365.25

    def als_zeile(self) -> str:
        return (
            f"mindestens {self.tage} Tage ({self.jahre:.1f} Jahre) fuer "
            f"{self.fehlend} fehlende Beobachtungen  (Befund {self.befund})"
        )


#: Der Abstand zur Schwelle, in Zeit. Untergrenze - siehe ``Aussicht``.
AUSSICHT = Aussicht(
    noetig=182,
    heute=115,
    rate_je_tausend_tage=34.2,
    befund=138,
)


def veraltet(text: str) -> tuple[str, ...]:
    """Welche ueberholten Kennzahlen stehen in diesem Text?

    Gesucht wird nach den Zahlen selbst, in beiden Schreibweisen - deutsche
    Komma- und englische Punktschreibung stehen im Projekt nebeneinander.

    **Das ist ein Fund und kein Urteil.** Ein Laborbucheintrag darf sie
    nennen, ein Modulkopf sollte dazusagen, dass sie ueberholt sind. Was
    daraus folgt, entscheidet der Test, der diese Funktion aufruft - nicht
    sie selbst.
    """
    treffer = []
    for punkt in UEBERHOLT:
        for zahl in (f"{punkt.dsr:.4f}", f"{punkt.dsr:.4f}".replace(".", ",")):
            if zahl in text and zahl not in treffer:
                treffer.append(zahl)
    return tuple(treffer)
