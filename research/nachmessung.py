"""Welche geschlossene Richtung wurde spaeter noch einmal angefasst?

Befund 130 hat einen Fehler aufgedeckt, den dieses Register selbst ermoeglicht
hat: Der Eintrag *"Vola-Ziel ... Befund 21"* zeigte auf eine Tabelle, die
Befund 23 zwei Befunde spaeter ersetzt hatte. Zwei Laeufe haben dort
nachgeschlagen, die alte Tabelle gefunden und den Unterschied zum heutigen
Stand falschen Ursachen zugeschrieben - beide Male, ohne dass etwas auffaellig
gewesen waere, denn die Fundstelle stimmte ja.

``Richtung.zuletzt`` behebt das fuer die Eintraege, bei denen jemand die
Nachmessung kennt. Dieses Modul beantwortet die andere Haelfte der Frage:
**Bei welchen Eintraegen koennte noch eine Nachmessung stehen, von der niemand
weiss?**

Was dieses Modul nicht tut
--------------------------
**Es entscheidet nichts.** Erwaehnt zu werden ist nicht dasselbe wie
nachgemessen zu werden: Ein Befund, der eine geschlossene Richtung nur zitiert,
taucht hier genauso auf wie einer, der sie neu vermisst. Der Unterschied ist
mit Textsuche nicht zu haben - er steht im Text.

Deshalb heisst das Ergebnis ``Spur`` und nicht ``Nachmessung``, und deshalb
gibt es keine Funktion, die ``Richtung.zuletzt`` selbst setzt. Wer einen
Eintrag nachzieht, hat den Befund gelesen.

Das ist dieselbe Regel wie in Befund 118: Dort hatte eine Textsuche elf
Befehle als fehlend gemeldet, die es gab. Eine Suche, die Verdachtsfaelle
liefert, ist nuetzlich; eine Suche, deren Treffer man ungeprueft uebernimmt,
ist schlimmer als keine.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from research.stand import Richtung, zahlwort

__all__ = ["BEGRIFFE", "Abschnitt", "Spur", "abschnitte", "spuren"]

_UEBERSCHRIFT = re.compile(r"^## ([A-Za-zaeoeueAEOEUEäöüÄÖÜ]+)\.\s*(.*)$")


@dataclass(frozen=True, slots=True)
class Abschnitt:
    """Ein Befund im Laborbuch, mit den Zeilen, die zu ihm gehoeren."""

    nummer: int
    titel: str
    von: int
    bis: int

    def __post_init__(self) -> None:
        if self.bis < self.von:
            raise ValueError(
                f"Befund {self.nummer} endet vor seinem Anfang "
                f"({self.von} bis {self.bis})."
            )

    def enthaelt(self, zeile: int) -> bool:
        return self.von <= zeile <= self.bis


def abschnitte(text: str) -> tuple[Abschnitt, ...]:
    """Zerlegt das Laborbuch in seine Befunde.

    Die Ueberschriften tragen deutsche Zahlwoerter (*"## Fuenfundachtzig.
    ..."*), und ``stand.zahlwort`` erzeugt genau diese. Statt eine zweite,
    umgekehrte Tabelle zu pflegen - die dann irgendwann von der ersten
    abweicht - wird sie hier aus derselben Funktion aufgebaut.
    """
    zeilen = text.splitlines()
    nach_wort = {zahlwort(n).lower(): n for n in range(1, 200) if zahlwort(n)}
    roh: list[tuple[int, int, str]] = []
    for i, zeile in enumerate(zeilen):
        treffer = _UEBERSCHRIFT.match(zeile)
        if treffer and (n := nach_wort.get(treffer.group(1).lower())):
            roh.append((i, n, treffer.group(2).strip()))
    aus = []
    for k, (start, nummer, titel) in enumerate(roh):
        ende = roh[k + 1][0] - 1 if k + 1 < len(roh) else len(zeilen) - 1
        aus.append(Abschnitt(nummer, titel, start, ende))
    return tuple(aus)


@dataclass(frozen=True, slots=True)
class Spur:
    """Eine geschlossene Richtung und die Befunde, die sie spaeter erwaehnen.

    ``spaeter`` sind Paare aus Befundnummer und Trefferzahl, absteigend nach
    Treffern. Sie sind **Verdachtsfaelle** - siehe den Modulkopf.
    """

    name: str
    fundstelle: int
    massgeblich: int
    spaeter: tuple[tuple[int, int], ...] = ()

    @property
    def offen(self) -> tuple[tuple[int, int], ...]:
        """Erwaehnungen **nach** der massgeblichen Fundstelle.

        Nur die sind interessant: Was vor der letzten Messung liegt, ist von
        ihr bereits ueberholt.
        """
        return tuple((n, t) for n, t in self.spaeter if n > self.massgeblich)

    @property
    def nachgezogen(self) -> bool:
        """Traegt der Eintrag schon eine bekannte Nachmessung?"""
        return self.massgeblich != self.fundstelle

    def urteil(self) -> str:
        offen = self.offen
        if not offen:
            return (
                f"{self.name}: keine Erwaehnung nach Befund {self.massgeblich}."
            )
        namen = ", ".join(f"{n} ({t}x)" for n, t in offen[:6])
        return (
            f"{self.name}: nach Befund {self.massgeblich} noch erwaehnt in "
            f"{namen} - zu lesen, nicht zu glauben."
        )


#: Suchbegriffe je geschlossener Richtung.
#:
#: Bewusst eng gehalten: Eine Trefferliste, die zu lang ist, wird nicht
#: gelesen, und eine ungelesene Trefferliste ist genau der Zustand, aus dem
#: Befund 130 entstanden ist. Ein Eintrag ohne Begriffe wird uebersprungen und
#: als solcher gemeldet - besser eine sichtbare Luecke als ein stiller
#: Fehlalarm (Befund 118).
BEGRIFFE: dict[str, tuple[str, ...]] = {
    "Mehr Maerkte": ("effektive Stichprobe", "mehr Maerkte", "weitere Maerkte"),
    "Dreierverbund": ("Dreierverbund", "Dreier", "drittes Bein", "Beinsumme"),
    "Mehr Historie": ("mehr Historie", "laengere Historie"),
    "15-Minuten-Kerzen": ("15-Minuten", "Feinkerzen"),
    "Vola-Ziel": ("Vola-Ziel", "target_vol"),
    "Stop-Weite": ("Stop-Weite", "Stopweite"),
    "Konviktions-Bonus": ("Konviktion",),
    "Perioden-Faktor": ("Perioden-Faktor", "Periodenfaktor"),
    "Termin-Overlay": ("Terminkalender", "Termin-Overlay"),
    "Shorts": ("Shorts", "Short-Seite"),
    "Perioden-Ensemble": ("Ensemble",),
    "Abkuehlung": ("Abkuehlung", "cooldown"),
    "Trades streichen": ("Trades streichen", "gestrichene Trades"),
    "Gewinnziel": ("Gewinnziel", "TargetSpec"),
    "Adaptive Periode": ("adaptive Periode", "Adaptive Periode"),
    "Kanalausbruch": ("Kanalausbruch", "Donchian"),
    "Umsatzfilter": ("Umsatzfilter", "Volumenfilter"),
    "Rueckkehr zum Mittel": ("Rueckkehr zum Mittel",),
    "Schiefe erhoehen": ("Schiefe erhoehen", "Pearson"),
    "Woelbung senken": ("Woelbung senken", "Woelbung unter"),
    "Trade-Zahl heben": ("Trade-Zahl", "Kopplung"),
    "Katalog als Partner": ("Katalog als Partner", "Katalog-Partner"),
    "Eigenbau-Partner": ("Eigenbau",),
    "Familie Rueckkehr": ("Familie Rueckkehr",),
    "Phasen-Partner": ("Phasen-Partner", "gegenlaeufig"),
    "Verbund aus dem Katalog": ("Verbund aus dem Katalog", "bestes Paar"),
    "Sperrfrist": ("Sperrfrist",),
    "Verbund fuer die Risikogates": ("Risikogates", "231 Kombination"),
    "Groessenregler zum Rechteck": ("Groessenregler", "Mengenrundung"),
    "Koernung zum Deflated Sharpe": ("Koernung", "Kontoleiter"),
    "Feinere Kerzen im Fuellmodell": ("Fuellmodell", "feinere Kerzen"),
    "Zulassung auf Referenzkerzen": ("Referenzkerzen",),
    "Hebel als Reserve": ("Hebel als Reserve", "Hebeldeckel"),
    "Kostenannahmen": ("Kostendecke", "Kosten null"),
    "Schwacher Vorteil (5 %)": ("schwacher Vorteil", "Schwacher Vorteil"),
    "Belege als Kalibrierung": ("Belege als Kalibrierung", "Abdeckung"),
    "Schnittpunkt als Prognose": ("Schnittpunkt", "Fehlerbalken"),
}


def spuren(
    text: str,
    richtungen: tuple[Richtung, ...],
    begriffe: dict[str, tuple[str, ...]] | None = None,
) -> tuple[tuple[Spur, ...], tuple[str, ...]]:
    """Sucht zu jeder Richtung die spaeteren Erwaehnungen.

    Gibt die Spuren zurueck **und** die Namen, fuer die keine Suchbegriffe
    hinterlegt sind. Die zweite Liste ist der wichtigere Teil: Sie sagt, wo
    diese Suche gar nicht erst hingesehen hat.
    """
    wortliste = BEGRIFFE if begriffe is None else begriffe
    teile = abschnitte(text)
    zeilen = text.splitlines()
    aus: list[Spur] = []
    ohne: list[str] = []
    for r in richtungen:
        worte = wortliste.get(r.name)
        if not worte:
            ohne.append(r.name)
            continue
        gezaehlt: dict[int, int] = {}
        for a in teile:
            if a.nummer <= r.befund:
                continue
            treffer = sum(
                1 for z in zeilen[a.von : a.bis + 1] if any(w in z for w in worte)
            )
            if treffer:
                gezaehlt[a.nummer] = treffer
        geordnet = tuple(
            sorted(gezaehlt.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        aus.append(Spur(r.name, r.befund, r.massgeblich, geordnet))
    return tuple(aus), tuple(ohne)
