"""Was ein Katalogdurchlauf kostet - gemessen, nicht geschaetzt.

Der Anlass
----------
``cli vorratsdecke`` faehrt den ganzen Katalog. Ob das in einen Arbeitsschritt
passt, entscheidet, ob eine Messung gemacht wird oder nicht - und diese
Entscheidung ist in diesem Projekt zweimal hintereinander **geschaetzt**
worden.

    Schaetzung 1   "225.000 Kerzen sind 68-mal so viele wie 3.300, das
                   dauert Stunden"        -> daraufhin zwei Laeufe lang
                   nicht gemessen
    Gemessen       ein Walk-Forward auf 15 Minuten: 61 s
    Schaetzung 2   "39 Genome mal 61 s, also 40 Minuten"
    Gemessen       je Genom 226 s im Median - die Gates kosten mehr als der
                   Walk-Forward, und zwar ein Vielfaches

Beide Schaetzungen lagen daneben, in entgegengesetzte Richtungen. Die erste
hat eine Messung verhindert, die machbar war; die zweite haette einen Lauf
begonnen, dessen Dauer niemand kannte.

*"Jede Behauptung wird gemessen, nicht geschaetzt"* gilt auch fuer
Behauptungen ueber das eigene Vorgehen.

Was hier steht
--------------
Die **gemessenen** Laufzeiten je Genom, mit der Kerzenzahl, auf der sie
entstanden sind. Mehr nicht.

Was hier **nicht** steht
------------------------
Eine Formel. Zwei Punkte (3.277 und 225.341 Kerzen) legen eine Gerade fest,
und genau davor warnt dieses Projekt seit Befund 285: Die Kosten wachsen
sichtlich langsamer als die Kerzenzahl - Faktor 69 an Kerzen, Faktor 38 an
Zeit -, weil der teure Teil an den **Trades** haengt und nicht an den Kerzen.
Eine Gerade durch zwei Punkte waere eine Behauptung ueber alle
Kerzenlaengen dazwischen, gestuetzt auf nichts.

Fuer eine nicht gemessene Kerzenlaenge gibt es deshalb keine Auskunft,
sondern die Aufforderung, sie zu messen.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["MESSUNGEN", "Laufkosten", "auskunft", "dauer"]


@dataclass(frozen=True, slots=True)
class Laufkosten:
    """Was ein Genom bei dieser Kerzenlaenge gekostet hat."""

    kerzen: int
    je_genom: float
    """Sekunden je Genom, **Median** ueber den Lauf.

    Median und nicht Mittel: Ein Genom, das gar nicht handelt, ist in
    Sekunden fertig, eines mit zwoelftausend Trades braucht Minuten. Das
    Mittel haengt dann daran, wie viele Nichthandler im Katalog stehen.
    """

    gemessen_in: int
    """Der Befund, in dem die Messung entstanden ist."""


#: Die gemessenen Laufzeiten, je Kerzenlaenge (Befund 296).
#:
#: Sie veralten mit jeder Aenderung an den Gates und an der Maschine. Das ist
#: hinnehmbar: Eine veraltete **Messung** ist immer noch besser als eine
#: frische Schaetzung, und die Fundstelle steht daneben.
MESSUNGEN: dict[str, Laufkosten] = {
    "1d": Laufkosten(kerzen=3_277, je_genom=6.0, gemessen_in=296),
    "15m": Laufkosten(kerzen=225_341, je_genom=226.0, gemessen_in=296),
}


def dauer(intervall: str, genome: int) -> float | None:
    """Wie lange ein Katalogdurchlauf hier dauert, in Sekunden.

    ``None`` fuer eine Kerzenlaenge, die nicht gemessen ist - **nicht** eine
    hochgerechnete Zahl. Wer eine braucht, misst sie.
    """
    kosten = MESSUNGEN.get(intervall)
    if kosten is None or genome < 0:
        return None
    return kosten.je_genom * genome


def auskunft(intervall: str, genome: int) -> str:
    """Die Zeile, die vor einem langen Lauf dasteht."""
    sekunden = dauer(intervall, genome)
    if sekunden is None:
        gemessen = ", ".join(sorted(MESSUNGEN))
        return (
            f"Laufzeit fuer '{intervall}' nicht gemessen (bekannt: {gemessen}) "
            f"- hier wird nichts hochgerechnet."
        )
    kosten = MESSUNGEN[intervall]
    if sekunden < 90:
        zeit = f"rund {sekunden:.0f} Sekunden"
    elif sekunden < 5400:
        zeit = f"rund {sekunden / 60:.0f} Minuten"
    else:
        zeit = f"rund {sekunden / 3600:.1f} Stunden".replace(".", ",")
    # Der Tausenderpunkt wird auf der **Zahl** gesetzt und nicht auf dem
    # fertigen Satz: Ein pauschales replace(",", ".") traf auch das Komma
    # hinter "Genome" und machte daraus einen Punkt.
    kerzen = f"{kosten.kerzen:,}".replace(",", ".")
    return (
        f"{genome} Genome, {zeit} - gemessen mit {kosten.je_genom:.0f} s je "
        f"Genom auf {kerzen} Kerzen (Befund {kosten.gemessen_in})."
    )
