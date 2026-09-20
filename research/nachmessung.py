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

__all__ = ["BEGRIFFE", "GELESEN", "Abschnitt", "Spur", "abschnitte", "spuren"]

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


def _nach_wort() -> dict[str, int]:
    """Zahlwort auf Nummer - so weit, wie ``zahlwort`` reicht.

    **Hier stand ``range(1, 200)``** (Befund 272). Seit das Laborbuch die
    Zweihundert ueberschritten hat, war damit **jeder** Abschnitt darueber
    fuer diesen Parser unsichtbar - und mit ihm fuer jede Wache, die auf
    ``abschnitte`` aufbaut. Aufgefallen ist es erst beim ersten geschlossenen
    Suchweg jenseits von 199: Seine Fundstelle zeigte ins Leere, obwohl der
    Abschnitt dasteht.

    Dieselbe Grenze hatte ``test_die_liste_reicht_bis_an_die_gegenwart``
    schon einmal, und dort wurde sie auf 300 hochgesetzt. Die Korrektur ist
    hier nie angekommen - eine Zahl an zwei Stellen, von denen eine gepflegt
    wurde.

    Deshalb jetzt gar keine Zahl: Gezaehlt wird, solange ``zahlwort`` ein
    Wort liefert. Wer die Tabelle dort erweitert, erweitert diesen Parser
    mit - und wer es vergisst, bekommt die Wache in ``test_nachmessung``.
    """
    aus: dict[str, int] = {}
    n = 1
    while wort := zahlwort(n):
        aus[wort.lower()] = n
        n += 1
    return aus


def hoechste_benennbare() -> int:
    """Die groesste Nummer, fuer die es ein Zahlwort gibt.

    Die Grenze, an der das Laborbuch stumm wuerde: Ein Befund darueber
    bekaeme keine Ueberschrift, die dieser Parser lesen kann.
    """
    return max(_nach_wort().values())


def abschnitte(text: str) -> tuple[Abschnitt, ...]:
    """Zerlegt das Laborbuch in seine Befunde.

    Die Ueberschriften tragen deutsche Zahlwoerter (*"## Fuenfundachtzig.
    ..."*), und ``stand.zahlwort`` erzeugt genau diese. Statt eine zweite,
    umgekehrte Tabelle zu pflegen - die dann irgendwann von der ersten
    abweicht - wird sie hier aus derselben Funktion aufgebaut.
    """
    zeilen = text.splitlines()
    nach_wort = _nach_wort()
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
    gelesen: int = 0
    """Bis zu welchem Befund die Erwaehnungen gelesen sind (Befund 295)."""

    @property
    def offen(self) -> tuple[tuple[int, int], ...]:
        """Erwaehnungen **nach** der massgeblichen Fundstelle.

        Nur die sind interessant: Was vor der letzten Messung liegt, ist von
        ihr bereits ueberholt.
        """
        return tuple((n, t) for n, t in self.spaeter if n > self.massgeblich)

    @property
    def neu(self) -> tuple[tuple[int, int], ...]:
        """Erwaehnungen, die noch niemand gelesen hat.

        ``offen`` sagt, was **nach der Messung** kam; das hier sagt, was
        seither auch noch **niemand angesehen** hat. Der Unterschied ist die
        Arbeit, die wirklich offen ist.
        """
        return tuple((n, t) for n, t in self.offen if n > self.gelesen)

    @property
    def durchgesehen(self) -> bool:
        """Sind alle Erwaehnungen dieser Richtung gelesen?"""
        return bool(self.offen) and not self.neu

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


#: Bis zu welchem Befund die Verdachtsfaelle einer Richtung **gelesen** sind.
#:
#: **Ohne dieses Register hat die Suche kein Gedaechtnis** (Befund 295). Sie
#: meldet bei jedem Lauf dieselben dreiundvierzig Eintraege, und niemand
#: sieht, welche davon schon jemand nachgeschlagen hat. Wer sie zweimal
#: liest, hat zweimal gearbeitet; wer sie gar nicht liest, merkt es nicht.
#:
#: Ein Eintrag heisst: "Die Erwaehnungen bis zu diesem Befund sind gelesen
#: und entschieden." Was danach kommt, ist neu. Gesetzt wird er **von Hand**
#: und nur von jemandem, der die Abschnitte wirklich gelesen hat - aus
#: demselben Grund, aus dem kein Code ``Richtung.zuletzt`` setzt.
GELESEN: dict[str, int] = {
    # Befund 295: die sieben Verdachtsfaelle aus 294, gelesen und entschieden.
    # Drei waren Nachmessungen und sind nachgezogen, vier waren Erwaehnungen.
    #
    # **Und die Zahl ist 295 und nicht 294**: Der Abschnitt, der die Lesung
    # festhaelt, nennt jede der sieben Richtungen beim Namen und erzeugt damit
    # selbst einen Treffer. Bei 294 haette jede der sieben sofort wieder als
    # ungelesen dagestanden - der Eintrag haette sich selbst widerlegt. Die
    # volle Suite hat das gefunden; einzeln gelaufen war die Datei gruen, weil
    # der Abschnitt da noch nicht geschrieben war.
    "Bestand + 'Grosser Trendausbruch'": 295,
    "Holdout auf fremden Maerkten": 295,
    "Zaehlt ein Sweep am Bestand als Versuch?": 295,
    "Timing gegen Zufallseinstiege": 295,
    "Der Preis in Reststreuungen": 295,
    # **Befund 305 hat beide erneut angesehen** - und es war zweimal etwas
    # anderes.
    #
    # 'Einstieg, der nicht am Rauschen haengt' ist gelesen und **entschieden
    # worden**: Der Eintrag nennt seit 283 einen strukturellen Bruch als den
    # einzigen bekannten Weg aus der Kopplung und sagt, dass er einen Versuch
    # kostet. Das ist eine Abwaegung mit Preis, also eine Entscheidung; sie
    # steht seit 305 unter ENTSCHEIDUNGEN statt nur unter den Richtungen.
    #
    # 'Zertifizierbarkeit der Bauart' ist nur **erwaehnt**: Der Treffer haengt
    # am Wort "gepflanzt", und 305 zitiert damit Befund 283, statt entlang
    # dieser Achse etwas nachzumessen. Genau der Unterschied, den 'Spur' nicht
    # sehen kann und den dieser Eintrag festhaelt.
    #
    # **Und in 306 noch einmal beide** - zum zweiten Mal in Folge, aus
    # demselben Grund: Ein Befund, der ueber den strukturellen Bruch
    # schreibt, nennt zwangslaeufig "gepflanzt" und "am Rauschen". Der
    # Unterschied bleibt derselbe: 306 hat 'Einstieg, der nicht am Rauschen
    # haengt' wirklich gelesen - und dabei gefunden, dass die
    # Zusammenfassung des Eintrags neben Befund 283 stand -, waehrend
    # 'Zertifizierbarkeit der Bauart' wieder nur zitiert wird.
    # **Befund 321, und zum dritten Mal dieselben beiden** - ein Befund ueber
    # die gepflanzte Leiter nennt zwangslaeufig "gepflanzt", und 321 nennt
    # ausserdem 'Neues Hoch im Takt'.
    #
    # 'Zertifizierbarkeit der Bauart' ist **benutzt, nicht nachgemessen**:
    # Ihr Satz "Pflanzen nimmt die Stichprobe mit" ist die Ursache des
    # Befundes - je staerker gepflanzt, desto weniger Trades, desto eher
    # setzt der Deflated Sharpe aus. Gemessen hat 321 die Buchfuehrung und
    # nicht die Achse; die massgebliche Fundstelle bleibt 178.
    #
    # 'Einstieg, der nicht am Rauschen haengt' ist gelesen und **ausdruecklich
    # nicht nachgezogen**: 321 berichtet, dass 'Neues Hoch im Takt' bei 10,
    # 20 und 35 % gepflanzter Varianz alle elf Gates besteht. Das ist eine
    # Aussage ueber die **gepflanzte** Reihe und keine ueber den
    # strukturellen Bruch - 'cli teststaerke' sagt selbst, ein gepflanztes
    # Regime sei sauberer als jeder Markt. Auf echten Daten steht die Regel
    # in den neun gemessenen Vorschlaegen (ENTSCHEIDUNGEN, Nr. 292), und
    # dort hat keiner die Latte geraeumt. Wer 321 anders liest, haelt einen
    # bestandenen Labortest fuer einen Kandidaten.
    "Zertifizierbarkeit der Bauart": 321,
    "Einstieg, der nicht am Rauschen haengt": 321,
}

#: Suchbegriffe je Richtung - geschlossene **und offene**.
#:
#: Bewusst eng gehalten: Eine Trefferliste, die zu lang ist, wird nicht
#: gelesen, und eine ungelesene Trefferliste ist genau der Zustand, aus dem
#: Befund 130 entstanden ist. Ein Eintrag ohne Begriffe wird uebersprungen und
#: als solcher gemeldet - besser eine sichtbare Luecke als ein stiller
#: Fehlalarm (Befund 118).
#:
#: **Bis Befund 294 standen hier nur die geschlossenen Richtungen.** Genau
#: neununddreissig Namen, und ``cli register`` lief nur ueber ``GESCHLOSSEN``
#: - die sechzehn **offenen** Richtungen und die 153 behobenen hat diese
#: Suche nie angesehen. Das war keine Fehlfunktion: ``spuren`` meldet seit
#: jeher, wo es keine Begriffe gibt. Gefragt hat nur niemand, und die offenen
#: Richtungen sind die, nach denen gearbeitet wird.
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
    "Suchdisziplin als Weg": (
        "Suchdisziplin",
        "hoechster Versuchsstand",
        "sparsamer gesucht",
        "raeumt bis",
    ),
    "Einstiegsseite": (
        "Vorteilsscan",
        "vorteilsscan",
        "cli scan",
        "in der zweiten Haelfte verschwunden",
        "Einstiegsseite",
        "Marktbreite",
        "Verschiebungsprobe",
    ),    # --- Die offenen Richtungen (Befund 294) ---------------------------
    "Holdout auf fremden Maerkten": (
        "fremden Maerkten", "Holdout-Markt", "LTC und XRP",
    ),
    "Timing gegen Zufallseinstiege": ("Zufallseinstieg", "zufaellige Einstiege"),
    "Zertifizierbarkeit der Bauart": ("gepflanzt", "Zertifizierbarkeit"),
    "Gedeckelter Ausstieg": ("gedeckelter Ausstieg", "Haltedauerdeckel", "max_hold"),
    "Menge statt Qualitaet": ("Mengentor", "Menge statt Qualitaet"),
    "Bestand + 'Grosser Trendausbruch'": (
        "Grosser Trendausbruch", "Trendfolge Ausbruch",
    ),
    "Der Preis in Reststreuungen": ("Reststreuung",),
    "Haengt die Familienaussage am Schnitt?": ("Familienaussage", "Mehrheitsfamilie"),
    "Einstieg, der nicht am Rauschen haengt": (
        "Neues Hoch im Takt", "wiederholbare Ausbruch", "am Rauschen",
    ),
    "Traegt die Reibung die Kopplung auf kurzen Kerzen?": (
        "Kostenanteil", "Kippfaktor",
    ),
    "Ordnet die Luecke das Verhalten im Holdout?": ("Rangtreue", "Haltequote"),
    "Tageskerzen ableiten statt laden?": (
        "Tageskerzen ableiten", "ableiten statt laden",
    ),
    "Zaehlt ein Sweep am Bestand als Versuch?": ("Sweep", "Reglerscan"),
    "Der Grundstock nimmt auch das Neue auf": ("Grundstock", "save_trials"),
    "Zugelassen ist der Korb, handelbar ist ein Bein": (
        "Korbhandel", "handelbar ist ein Bein",
    ),
    "Zahlt der Bestand dann, wenn Longs am meisten zahlen?": (
        "Longs am meisten", "Funding-Belastung",
    ),

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
        aus.append(
            Spur(
                r.name, r.befund, r.massgeblich, geordnet,
                gelesen=GELESEN.get(r.name, 0),
            )
        )
    return tuple(aus), tuple(ohne)
