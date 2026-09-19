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

__all__ = [
    "MESSUNGEN",
    "Laufkosten",
    "auskunft",
    "auskunft_ohne_gates",
    "dauer",
    "dauer_ohne_gates",
]


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

    je_sprosse: float | None = None
    """Sekunden je Genom und **Sprosse der Reibungsleiter**.

    Eine Sprosse rechnet denselben Walk-Forward noch einmal mit anderer
    Gebuehr, aber **ohne** die Gates - und die sind der teure Teil. Wer die
    Leiter mit dem vollen Genompreis hochrechnet, kommt deutlich zu hoch
    heraus: auf 15 Minuten 226 s gegen tatsaechlich 61 s je Sprosse.

    Das ist derselbe Fehler wie in Befund 296, eine Ebene tiefer - dort war
    der falsche Massstab die Kerzenzahl, hier waere es der Genompreis.
    """

    sprosse_gemessen_in: int | None = None
    """Der Befund zum **Sprossenpreis** - eine eigene Messung.

    Er steht getrennt, weil er es ist: ``je_genom`` stammt aus Befund 296,
    ``je_sprosse`` aus 298. Eine gemeinsame Fundstelle waere bequem und
    falsch, und dieses Projekt hat an genau der Sorte Bequemlichkeit schon
    zweimal verloren (130, 293).
    """


#: Die gemessenen Laufzeiten, je Kerzenlaenge (Befund 296).
#:
#: Sie veralten mit jeder Aenderung an den Gates und an der Maschine. Das ist
#: hinnehmbar: Eine veraltete **Messung** ist immer noch besser als eine
#: frische Schaetzung, und die Fundstelle steht daneben.
MESSUNGEN: dict[str, Laufkosten] = {
    "1d": Laufkosten(
        kerzen=3_277, je_genom=6.0, gemessen_in=296,
        je_sprosse=2.2, sprosse_gemessen_in=298,
    ),
    "15m": Laufkosten(
        kerzen=225_341, je_genom=226.0, gemessen_in=296,
        je_sprosse=61.4, sprosse_gemessen_in=298,
    ),
}


def dauer(intervall: str, genome: int, sprossen: int = 0) -> float | None:
    """Wie lange ein Katalogdurchlauf hier dauert, in Sekunden.

    ``sprossen`` sind die Stufen der Reibungsleiter; jede kostet einen
    weiteren Walk-Forward je Genom, aber keine Gates.

    ``None`` fuer eine Kerzenlaenge, die nicht gemessen ist - **nicht** eine
    hochgerechnete Zahl. Wer eine braucht, misst sie. Ebenso ``None``, wenn
    Sprossen verlangt werden und deren Preis hier nicht gemessen ist.
    """
    kosten = MESSUNGEN.get(intervall)
    if kosten is None or genome < 0 or sprossen < 0:
        return None
    if sprossen and kosten.je_sprosse is None:
        return None
    zusatz = (kosten.je_sprosse or 0.0) * sprossen
    return (kosten.je_genom + zusatz) * genome


def _zeitwort(sekunden: float) -> str:
    """Sekunden so, wie ein Mensch sie vor einem Lauf lesen will."""
    if sekunden < 90:
        return f"rund {sekunden:.0f} Sekunden"
    if sekunden < 5400:
        return f"rund {sekunden / 60:.0f} Minuten"
    return f"rund {sekunden / 3600:.1f} Stunden".replace(".", ",")


def dauer_ohne_gates(intervall: str, genome: int, stufen: int = 1) -> float | None:
    """Ein Lauf, der **nur** Walk-Forwards rechnet, in Sekunden.

    Die Reibungsfrage braucht Taktpunkte und keine Gates (Befund 301). Dann
    kostet jede Stufe eine Sprosse - der Betriebspunkt eingeschlossen -, und
    der Genompreis mit Gates taucht gar nicht auf.

    Das ist derselbe Massstabsfehler wie in 296 und 298, nur ein drittes Mal
    vermieden: Wer hier mit ``je_genom`` rechnete, kaeme auf das Dreifache.
    """
    kosten = MESSUNGEN.get(intervall)
    if kosten is None or kosten.je_sprosse is None or genome < 0 or stufen < 0:
        return None
    return kosten.je_sprosse * stufen * genome


def auskunft_ohne_gates(intervall: str, genome: int, stufen: int = 1) -> str:
    """Die Zeile vor einem Lauf, der nur Walk-Forwards rechnet."""
    sekunden = dauer_ohne_gates(intervall, genome, stufen)
    if sekunden is None:
        gemessen = ", ".join(sorted(MESSUNGEN))
        return (
            f"Laufzeit fuer '{intervall}' nicht gemessen (bekannt: {gemessen}) "
            f"- hier wird nichts hochgerechnet."
        )
    kosten = MESSUNGEN[intervall]
    return (
        f"{genome} Genome mal {stufen} Stufe{'n' if stufen != 1 else ''}, "
        f"{_zeitwort(sekunden)} - gemessen mit {kosten.je_sprosse:.0f} s je "
        f"Walk-Forward (Befund {kosten.sprosse_gemessen_in}), ohne Gates."
    )


def auskunft(intervall: str, genome: int, sprossen: int = 0) -> str:
    """Die Zeile, die vor einem langen Lauf dasteht."""
    sekunden = dauer(intervall, genome, sprossen)
    if sekunden is None:
        gemessen = ", ".join(sorted(MESSUNGEN))
        return (
            f"Laufzeit fuer '{intervall}' nicht gemessen (bekannt: {gemessen}) "
            f"- hier wird nichts hochgerechnet."
        )
    kosten = MESSUNGEN[intervall]
    zeit = _zeitwort(sekunden)
    # Der Tausenderpunkt wird auf der **Zahl** gesetzt und nicht auf dem
    # fertigen Satz: Ein pauschales replace(",", ".") traf auch das Komma
    # hinter "Genome" und machte daraus einen Punkt.
    kerzen = f"{kosten.kerzen:,}".replace(",", ".")
    leiter = (
        f" plus {sprossen} Sprosse{'n' if sprossen != 1 else ''} zu "
        f"{kosten.je_sprosse:.0f} s (Befund {kosten.sprosse_gemessen_in})"
        if sprossen and kosten.je_sprosse is not None
        else ""
    )
    return (
        f"{genome} Genome, {zeit} - gemessen mit {kosten.je_genom:.0f} s je "
        f"Genom{leiter} auf {kerzen} Kerzen (Befund {kosten.gemessen_in})."
    )
