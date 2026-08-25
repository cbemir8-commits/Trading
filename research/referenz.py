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

__all__ = ["SPOTPUNKT", "UEBERHOLT", "Referenzpunkt", "veraltet"]


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
#: Deflated-Sharpe-Gate mit Quartalseinteilung (Befund 135).
SPOTPUNKT = Referenzpunkt(
    name="Spot wie gebaut",
    befund=135,
    trades=152,
    effektiv=112,
    guete=0.2765,
    dsr=0.6026,
    bestanden=9,
    gesamt=11,
    versuche=198,
)

#: Staende, die einmal massgeblich waren und es nicht mehr sind. Wer einen
#: dieser Werte in einem Modulkopf liest, liest Geschichte.
UEBERHOLT: tuple[Referenzpunkt, ...] = (
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
