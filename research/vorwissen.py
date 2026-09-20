"""Was das Register zu einer Frage schon sagt - Befund 303.

Der Anlass
----------
Befund 302 hat 106 Minuten lang gemessen, ob die Reibung die Kopplung auf
Viertelstunden traegt. Die Antwort stand bereits im Register, aus Befund 255,
mit denselben Zahlen: ``-0,267`` auf ``-0,186``, die Reibung traegt 30 %.

Der Eintrag widersprach sich selbst - 255 hatte gemessen, 297 hat die
Richtung mit einem **gerechneten** Kippfaktor wieder aufgemacht, obwohl 256
im selben Eintrag festhaelt, dass der keine Messung ist. Weil ``zuletzt`` auf
297 zeigte, stand da "unentschieden".

Ich habe den Eintrag vor dem Lauf nicht gelesen. Schritt 1 meines eigenen
Ablaufs heisst "Was ist der Stand?", und ich habe den Ordner mit den
Berichten angesehen, nicht den Eintrag zu der Frage, die ich messen wollte.

Was dieses Modul tut
--------------------
Vor einem langen Lauf die Registereintraege heraussuchen, die zu den
Stichworten dieses Laufs passen, und sie hinschreiben. Mehr nicht.

Was es **nicht** tut
--------------------
**Es haelt nichts auf.** Eine Messung zu wiederholen ist oft richtig - 302
hat 255 auf einem unabhaengig gebauten Weg bestaetigt, und das ist mehr wert
als eine Wiederholung desselben Codes. Falsch war nicht der Lauf, falsch war,
ihn zu starten, ohne die Antwort zu kennen.

Und es urteilt nicht ueber die Treffer. Ob ein Eintrag die Frage wirklich
beantwortet, steht im Text und ist mit Textsuche nicht zu haben - dieselbe
Regel wie in ``nachmessung``: Eine Suche, die Verdachtsfaelle liefert, ist
nuetzlich; eine Suche, deren Treffer man ungeprueft uebernimmt, ist
schlimmer als keine.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.stand import BEHOBEN, GESCHLOSSEN, OFFEN, Richtung

__all__ = ["STICHWORTE", "Fundstueck", "auskunft", "was_schon_dasteht"]

#: Womit ein langer Befehl das Register fragt, je Befehl.
#:
#: Hier und nicht in ``cli.py``: Stuenden die Worte dort und im Test noch
#: einmal, waere die Wache aus Befund 303 an eine zweite Fassung gebunden und
#: liefe irgendwann daneben - derselbe Fehler, den 130, 286 und 292 schon
#: gekostet haben.
STICHWORTE: dict[str, tuple[str, ...]] = {
    "reibung": ("Reibung", "Kopplung", "Kostenanteil", "Kippfaktor"),
    "vorratsdecke": ("Vorrat", "Kopplung", "Trade-Zahl", "Decke"),
    "freigabe": ("Sperre", "Kill-Switch", "Plateau", "Risk-Officer"),
}

#: Die drei Register, in der Reihenfolge, in der sie zaehlen.
#:
#: ``GESCHLOSSEN`` zuerst: Ein geschlossener Eintrag ist eine Antwort, ein
#: offener eine Zusage, ein behobener ein Werkzeugfehler. Wer vor einem Lauf
#: liest, will die Antworten zuerst sehen.
REGISTER: tuple[tuple[str, tuple[Richtung, ...]], ...] = (
    ("geschlossen", GESCHLOSSEN),
    ("offen", OFFEN),
    ("behoben", BEHOBEN),
)


@dataclass(frozen=True, slots=True)
class Fundstueck:
    """Ein Registereintrag, der zu den Stichworten passt."""

    lage: str
    richtung: Richtung
    treffer: tuple[str, ...]
    """Die Stichworte, die angeschlagen haben - damit sichtbar ist, warum."""

    gewicht: tuple[int, int, int] = (0, 0, 0)
    """Die Reihenfolge: Register, dann Zahl der Treffer, dann Fundstelle.

    Keine Wertung des Inhalts - nur eine Reihenfolge, damit der wichtigste
    Eintrag oben steht, wenn nicht alle hinpassen.
    """

    @property
    def gemessen(self) -> bool:
        """Nennt der Eintrag eine Messung?

        Ein Hinweis und kein Urteil: Das Wort steht auch da, wenn gemessen
        wurde, was die Frage **nicht** beantwortet. Genau diese Unterscheidung
        traegt der Text und nicht die Suche.
        """
        return "gemessen" in self.richtung.ergebnis.lower()

    @property
    def stelle(self) -> str:
        r = self.richtung
        if r.zuletzt is None:
            return f"Nr. {r.befund}"
        return f"Nr. {r.zuletzt}, zuerst {r.befund}"

    def zeile(self, breite: int = 76) -> str:
        """Eine Zeile Kopf, eine Zeile Inhalt.

        Ohne eckige Klammern um die Lage: Die Ausgabe laeuft durch 'rich',
        und '[geschlossen]' waere dort ein Auszeichnungsbefehl - der Text
        verschwaende spurlos. Aufgefallen beim ersten Rauchtest.
        """
        kurz = self.richtung.ergebnis
        if len(kurz) > breite:
            kurz = kurz[: breite - 1].rsplit(" ", 1)[0] + " ..."
        return (
            f"  {self.lage}: {self.richtung.name} ({self.stelle})\n"
            f"      {kurz}"
        )


def was_schon_dasteht(*begriffe: str) -> tuple[Fundstueck, ...]:
    """Die Registereintraege, in denen eines dieser Stichworte vorkommt.

    Gesucht wird in **Name und Ergebnis**, ohne Ruecksicht auf Gross- und
    Kleinschreibung. Ein Eintrag steht hoechstens einmal drin, auch wenn
    mehrere Stichworte passen; welche, sagt ``treffer``.

    Leere Stichworte werden uebergangen: Ein leerer Suchbegriff passt auf
    alles und machte die Auskunft wertlos.
    """
    worte = tuple(b.strip().lower() for b in begriffe if b and b.strip())
    if not worte:
        return ()
    gefunden: list[Fundstueck] = []
    for rang, (lage, liste) in enumerate(REGISTER):
        for r in liste:
            heuhaufen = f"{r.name}\n{r.ergebnis}".lower()
            passend = tuple(w for w in worte if w in heuhaufen)
            if not passend:
                continue
            # **Der Name zaehlt doppelt.** Ein Wort im Namen sagt, dass der
            # Eintrag von dieser Sache handelt; im Text kann es beilaeufig
            # stehen. 'Kopplung' kommt in diesem Projekt ueberall vor.
            im_namen = sum(1 for w in passend if w in r.name.lower())
            gefunden.append(
                Fundstueck(
                    lage=lage,
                    richtung=r,
                    treffer=passend,
                    gewicht=(rang, -(len(passend) + im_namen), -r.massgeblich),
                )
            )
    return tuple(sorted(gefunden, key=lambda f: f.gewicht))


def auskunft(*begriffe: str, kosten: str = "", zeige: int = 5) -> str:
    """Der Block, der vor einem langen Lauf dasteht.

    ``kosten`` ist die gemessene Laufzeit, wenn sie bekannt ist. Sie gehoert
    hierher, weil der Vergleich die eigentliche Aussage ist: Lesen kostet eine
    Minute, der Lauf in Befund 302 hat 106 gekostet.

    ``zeige`` begrenzt die Liste. 'Kopplung' trifft in diesem Projekt
    achtzehn Eintraege, und achtzehn Absaetze vor einem Lauf liest niemand -
    dann waere die Auskunft so wirkungslos wie keine. Was nicht hinpasst,
    wird gezaehlt und nicht verschwiegen.
    """
    treffer = was_schon_dasteht(*begriffe)
    if not treffer:
        return (
            "Das Register sagt zu diesen Stichworten nichts "
            f"({', '.join(begriffe)}) - es ist also wirklich neu, "
            "oder die Stichworte passen nicht."
        )
    gezeigt = treffer[:zeige]
    zeilen = [
        "Bevor gemessen wird - was das Register dazu schon sagt:",
        *(f.zeile() for f in gezeigt),
    ]
    if len(treffer) > len(gezeigt):
        zeilen.append(
            f"  ... und {len(treffer) - len(gezeigt)} weitere; "
            f"'cli register' zeigt alle."
        )
    mit_messung = [f for f in treffer if f.gemessen]
    if mit_messung:
        zeilen.append(
            f"**{len(mit_messung)} davon nennen eine Messung.** Lesen kostet "
            f"eine Minute"
            + (f", dieser Lauf {kosten}" if kosten else "")
            + ". Wiederholen ist oft richtig - es unwissentlich zu tun nicht."
        )
    return "\n".join(zeilen)
