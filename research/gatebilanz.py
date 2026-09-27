"""Eine Gate-Bilanz, die sagt, was sie wert ist - Befund 350.

Das Problem steht seit Befund 321/322 fest: ``GateResult.passed`` heisst "nicht
durchgefallen", und ein **uebersprungenes** Gate ist nicht durchgefallen. Wer
zu wenig handelt, bekommt Gates gutgeschrieben, die nie geurteilt haben. Befund
332 hat sechzehn Typen aufgelistet, bei denen die Frage offen blieb; 338, 346,
347 und 349 haben fuenf davon einzeln nachgezogen.

**Elf standen noch offen, und einzeln waeren das elf Male dasselbe.** Dieses
Modul macht daraus einen Mechanismus: Wer ``bestanden``, ``gesamt`` und
``trades`` traegt, kann die Frage beantworten, ohne dass jemand ein Feld
nachtraegt.

Gemeldet oder erschlossen
-------------------------
Die Unterscheidung ist die aus Befund 348, und sie bleibt:

**Gemeldet** heisst, der Typ kennt die Zahl der ausgesetzten Gates - weil er sie
beim Bauen aus ``GateResult.status`` mitgenommen hat. Das ist die harte
Auskunft, und sie ist genauer.

**Erschlossen** heisst, sie folgt aus der Trade-Zahl: Unter 30 setzen
Regime-Aufteilung und Deflated Sharpe aus, unter 20 auch Monte-Carlo. Das ist
eine **Untergrenze** - es koennen mehr sein, etwa wenn ``run_expensive`` aus war
oder keine Periode variierbar ist. Fuer den Zweck genuegt sie: Sie sagt
verlaesslich, dass eine Bilanz zu gut ist, nur nicht immer um wie viel.

Was das Modul deshalb **nicht** tut: die gemeldete Zahl ersetzen. Wo ein Typ
sie hat, ist sie besser, und die hier gerechnete bleibt die Ersatzauskunft.
"""

from __future__ import annotations

from research.aussetzer import SCHWELLEN

__all__ = ["Gatebilanz", "erschlossen_bei"]


def erschlossen_bei(trades: int) -> tuple[str, ...]:
    """Die Gates, die bei dieser Trade-Zahl ausgesetzt haben **muessen**.

    Sortiert, damit zwei Aufrufe dasselbe liefern - eine Menge in wechselnder
    Reihenfolge waere in einem Bericht nicht wiederzuerkennen.
    """
    if trades < 0:
        raise ValueError("Eine negative Trade-Zahl ist keine Stichprobe.")
    return tuple(
        name for name, schwelle in sorted(SCHWELLEN.items()) if trades < schwelle
    )


class Gatebilanz:
    """Die ehrliche Lesart einer Gate-Bilanz - als Beimischung.

    Erwartet ``bestanden``, ``gesamt`` und ``trades`` am Typ. Eine Beimischung
    und keine Basisklasse mit Feldern: Die elf Typen sind teils ``frozen``,
    teils ``slots``, und ein geerbtes Feld haette jede ihrer Signaturen
    veraendert. Eigenschaften aendern nichts.

    **Wo ein Typ seine Aussetzer selbst kennt**, traegt er ein eigenes Feld
    ``uebersprungen``; dann gewinnt das - siehe ``uebersprungen_ehrlich``.
    """

    bestanden: int
    gesamt: int
    trades: int

    @property
    def uebersprungen_erschlossen(self) -> tuple[str, ...]:
        """Untergrenze der ausgesetzten Gates, aus der Trade-Zahl."""
        return erschlossen_bei(self.trades)

    @property
    def uebersprungen_ehrlich(self) -> int:
        """Die beste verfuegbare Zahl: gemeldet, sonst erschlossen.

        Das Maximum und nicht "gemeldet, falls vorhanden": Eine gemeldete 0 bei
        acht Trades wuerde sonst die Erschliessung ueberstimmen, und dann waere
        die schlechtere Auskunft die verbindliche.
        """
        gemeldet = getattr(self, "uebersprungen", 0)
        zahl = len(gemeldet) if isinstance(gemeldet, (list, tuple)) else int(gemeldet)
        return min(self.gesamt, max(zahl, len(self.uebersprungen_erschlossen)))

    @property
    def geurteilt_ehrlich(self) -> int:
        """Gates mit einem Urteil - die ehrliche Bezugsgroesse."""
        return max(self.gesamt - self.uebersprungen_ehrlich, 0)

    @property
    def bestanden_ehrlich(self) -> int:
        """Bestandene ohne die, die nie geurteilt haben."""
        return max(self.bestanden - self.uebersprungen_ehrlich, 0)

    @property
    def bilanz_zu_gut(self) -> bool:
        """Zaehlt die rohe Bilanz Gates mit, die nicht geurteilt haben?"""
        return self.uebersprungen_ehrlich > 0

    def bilanzsatz(self) -> str:
        """Die Bilanz als Text - mit dem Vorbehalt, wenn es einen gibt."""
        if not self.bilanz_zu_gut:
            return f"{self.bestanden}/{self.gesamt} Gates"
        namen = ", ".join(self.uebersprungen_erschlossen)
        grund = (
            f" ({namen} setzen bei {self.trades} Trades aus)"
            if namen
            else ""
        )
        return (
            f"{self.bestanden_ehrlich}/{self.geurteilt_ehrlich} Gates"
            f"{grund}; roh {self.bestanden}/{self.gesamt}"
        )
