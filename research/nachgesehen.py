"""Wo ist diese Groesse im Projekt schon gemessen? - Befund 425.

Die Lage, aus der das entsteht
------------------------------
Das Register verzeichnet **acht** Faelle, in denen dieses Projekt etwas
nachgebaut hat, das es schon besass (268, 359, 388, 396, 407, 418, 423, 424).
Zwei davon liegen unmittelbar hintereinander und haben je einen ganzen
Arbeitsgang gekostet:

* **423** hat die Tafel "Deflated Sharpe je Versuchsstand" gemessen, samt
  Kreuzungspunkt und Grenzkosten - sie stand im Kopf von ``erreichbarkeit``.
* **424** hat festgestellt, dass auch der **Schluss** schon zweimal dastand:
  ``verbund.versuchskosten`` misst die Groesse seit Befund 221, und der Kopf
  von ``stand.Suchbudget`` zieht woertlich dieselbe Folgerung.

Der Grund ist nicht Unachtsamkeit, sondern Groesse. Der durchsuchbare Bestand
sind **104 Forschungsmodule und 72 Befehle** mit rund 1500 Docstrings. Wer von
Hand grept, sucht am Ort der **Frage**, die er gerade stellt - und nicht am Ort
der **Groesse**, die er messen will. Genau daran sind 423 und 424 gescheitert:
gesucht in ``erreichbarkeit``, gelegen in ``verbund`` und ``stand``.

Was dieses Modul tut
--------------------
Es durchsucht die Docstrings von ``research/*.py`` und ``cli.py`` - Modulkoepfe,
Klassen und Funktionen - und nennt die Stellen, an denen eine Groesse schon
beschrieben ist. Die Rangfolge ist eine Summe von ``log(N/df)`` ueber die
Suchbegriffe: Ein seltenes Wort wiegt mehr als ein haeufiges.

**Es entscheidet nichts.** Dieselbe Regel wie in ``nachmessung`` und
ausdruecklich die Lehre aus Befund 118, wo eine Textsuche elf Befehle als
fehlend gemeldet hat, die es gab: *Eine Suche, die Verdachtsfaelle liefert, ist
nuetzlich; eine Suche, deren Treffer man ungeprueft uebernimmt, ist schlimmer
als keine.* Die Treffer sind zu lesen, nicht zu zaehlen.

Wie gut es ist - gemessen an den eigenen Fehlgriffen
----------------------------------------------------
Die Abnahme laeuft nicht gegen erfundene Fragen, sondern gegen die Faelle, in
denen die Handsuche tatsaechlich versagt hat (``PROBEFAELLE``). Gemessen,
**vier von fuenf** in den ersten acht Treffern - darunter beide, die die
letzten zwei Arbeitsgaenge gekostet haben.

Der fuenfte wird **nicht** gefunden: ``gates.stichprobe_wie_im_gate`` (der
Fehlgriff aus Befund 407). Seine Frage besteht aus den haeufigsten Woertern des
Projekts - "effektive Stichprobe", "Gate", "messen" -, und lange Modulkoepfe,
die alle vier enthalten, stehen davor. Das ist die Grenze des Verfahrens und
steht hier, statt dass jemand sich auf Vollstaendigkeit verlaesst.

**Und warum die Rangfolge nicht nachgestellt ist.** Ein Bonus auf die Kopfzeile
erreicht 5 von 5 - aber nur bei genau dem Gewicht 1,5, mit 4 von 5 bei 1,0 und
2,0 und 3 von 5 bei 3,0. Eine Spitze zwischen zwei schlechteren Nachbarn auf
fuenf selbst gewaehlten Faellen ist das Muster, das Befund 417/418 als
ausgewaehltes Rauschen entlarvt hat; eingebaut wird es deshalb nicht. Es bleibt
bei der ungestellten Regel und bei vier von fuenf.
"""

from __future__ import annotations

import ast
import math
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

#: Wie viele Treffer die Abnahme betrachtet. Acht, weil ein Mensch acht Zeilen
#: liest und dreissig ueberfliegt.
GRENZE = 8

#: Begriffe unter dieser Laenge taugen nicht als Suchwort ("der", "je", "und").
MINDESTLAENGE = 4


def flach(text: str) -> str:
    """Kleinschreibung ohne Umlautschreibweisen.

    Das Projekt schreibt "noetig" und "nötig", "Guete" und "Güte". Ohne diese
    Angleichung findet eine Suche nach dem einen das andere nicht - und genau
    die Modulkoepfe, die am meisten wissen, sind die aeltesten.
    """
    gesenkt = text.lower()
    for von, nach in (("ae", "a"), ("oe", "o"), ("ue", "u"), ("ss", "s")):
        gesenkt = gesenkt.replace(von, nach)
    zerlegt = unicodedata.normalize("NFKD", gesenkt)
    return zerlegt.encode("ascii", "ignore").decode()


@dataclass(frozen=True, slots=True)
class Stelle:
    """Eine Stelle im Bestand, an der etwas beschrieben ist."""

    datei: str
    name: str
    zeile: str
    """Die erste Zeile des Docstrings - in diesem Projekt die Frage."""

    def __str__(self) -> str:
        return f"{self.datei}:{self.name}"


@dataclass(frozen=True, slots=True)
class Treffer:
    stelle: Stelle
    punkte: float
    worte: tuple[str, ...]
    """Welche Suchbegriffe hier vorkommen - damit ein Treffer pruefbar ist."""


@lru_cache(maxsize=1)
def bestand() -> tuple[tuple[Stelle, str], ...]:
    """Alle Docstrings aus ``research/`` und ``cli.py``, flach gelegt.

    Gelesen wird der Quelltext, nicht der Importstand: Ein Modul, das in
    diesem Lauf niemand importiert hat, muss gefunden werden. Genau daran
    haengt das Urteil von ``test_wachenaudit`` (Vermerk aus Befund 409), und
    hier waere es ein stiller Ausfall statt einer Meldung.
    """
    wurzel = Path(__file__).resolve().parent.parent
    dateien = [*sorted((wurzel / "research").glob("*.py")), wurzel / "cli.py"]
    gesammelt: list[tuple[Stelle, str]] = []
    for pfad in dateien:
        if not pfad.exists():
            continue
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        gefunden: list[tuple[str, str]] = []
        if kopf := ast.get_docstring(baum):
            gefunden.append(("<Modulkopf>", kopf))
        traeger = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        for knoten in ast.walk(baum):
            if isinstance(knoten, traeger) and (doc := ast.get_docstring(knoten)):
                gefunden.append((knoten.name, doc))
        for name, doc in gefunden:
            stelle = Stelle(pfad.name, name, doc.splitlines()[0].strip())
            gesammelt.append((stelle, flach(f"{pfad.stem} {name} {doc}")))
    return tuple(gesammelt)


@lru_cache(maxsize=1)
def _haeufigkeit() -> tuple[Counter[str], int]:
    zaehler: Counter[str] = Counter()
    eintraege = bestand()
    for _, text in eintraege:
        for wort in set(text.split()):
            zaehler[wort] += 1
    return zaehler, len(eintraege)


def gewicht(wort: str) -> float:
    """``log(N/df)`` - ein seltenes Wort wiegt mehr als ein haeufiges."""
    df, anzahl = _haeufigkeit()
    return math.log(anzahl / (1 + df.get(wort, 0)))


def suchworte(frage: str) -> tuple[str, ...]:
    worte = {flach(w).strip(".,;:!?()[]'\"-") for w in frage.split()}
    return tuple(sorted(w for w in worte if len(w) >= MINDESTLAENGE))


def durchsuche(frage: str, *, grenze: int = GRENZE) -> tuple[Treffer, ...]:
    """Die Stellen, an denen diese Groesse schon beschrieben sein koennte.

    **Verdachtsfaelle, keine Antworten** (Befund 118). Wer einen Treffer
    uebernimmt, hat ihn gelesen.
    """
    worte = suchworte(frage)
    if not worte:
        return ()
    treffer: list[Treffer] = []
    for stelle, text in bestand():
        dabei = tuple(w for w in worte if w in text)
        if not dabei:
            continue
        treffer.append(Treffer(stelle, sum(gewicht(w) for w in dabei), dabei))
    treffer.sort(key=lambda t: (-t.punkte, str(t.stelle)))
    return tuple(treffer[:grenze])


@dataclass(frozen=True, slots=True)
class Probefall:
    """Ein Fehlgriff, bei dem die Handsuche versagt hat - als Abnahme.

    ``befund`` ist der Registereintrag, der ihn verzeichnet; ``None`` fuer den
    Fall aus dem Lauf zu Befund 425 selbst, der noch keinen eigenen hat.
    """

    frage: str
    erwartet: str
    befund: int | None
    gefunden_erwartet: bool
    """Ob diese Stelle gefunden **wird**. Ein Fall, der nicht gefunden wird,
    bleibt stehen: Eine Abnahme, aus der man die Fehlschlaege entfernt, misst
    nichts (dieselbe Regel wie in ``test_suchbudget_greift``)."""


#: Die Faelle, gegen die dieses Werkzeug abgenommen wird.
#:
#: Keine erfundenen Fragen, sondern die, bei denen von Hand gesucht und nichts
#: gefunden wurde. Die Formulierung ist jeweils die, in der die Groesse damals
#: gesucht worden ist - nachtraeglich zu schaerfen waere, die Pruefung auf das
#: Ergebnis zu stellen.
PROBEFAELLE: tuple[Probefall, ...] = (
    Probefall(
        "was kostet ein weiterer Versuch Preis des Suchens Budget",
        "stand.py:Suchbudget",
        424,
        True,
    ),
    Probefall(
        "Deflated Sharpe je Versuchsstand Tafel Grenzkosten",
        "erreichbarkeit.py:<Modulkopf>",
        423,
        True,
    ),
    Probefall(
        "jede Gate-Groesse ueber elf Aufteilungen Versatz messen",
        "cli.py:aufteilung",
        418,
        True,
    ),
    Probefall(
        "bis zu welchem Versuchsstand raeumt diese Guete die Schwelle",
        "verbund.py:hoechster_versuchsstand",
        None,
        True,
    ),
    Probefall(
        "wirksame effektive Stichprobe wie im Gate messen",
        "gates.py:stichprobe_wie_im_gate",
        407,
        False,
    ),
)


def rang(fall: Probefall, *, grenze: int = GRENZE) -> int | None:
    """Auf welchem Platz die erwartete Stelle steht - ``None``, wenn nicht."""
    namen = [str(t.stelle) for t in durchsuche(fall.frage, grenze=grenze)]
    return namen.index(fall.erwartet) + 1 if fall.erwartet in namen else None


def abnahme(*, grenze: int = GRENZE) -> tuple[tuple[Probefall, int | None], ...]:
    """Jeder Probefall mit seinem gemessenen Rang.

    **Gerechnet, nicht gepflegt** (Befund 408): Wer die Rangfolge aendert,
    sieht es hier, statt eine alte Zahl weiterzutragen.
    """
    return tuple((fall, rang(fall, grenze=grenze)) for fall in PROBEFAELLE)


def quote(*, grenze: int = GRENZE) -> tuple[int, int]:
    """Wie viele der Probefaelle gefunden werden, von wie vielen."""
    gemessen = abnahme(grenze=grenze)
    return sum(1 for _, platz in gemessen if platz is not None), len(gemessen)


#: Der Satz, der zu jedem Ergebnis gehoert - Befund 118.
VORBEHALT = (
    "Verdachtsfaelle, keine Antworten: Erwaehnt zu werden ist nicht dasselbe "
    "wie gemessen zu werden. Wer einen Treffer uebernimmt, hat ihn gelesen."
)


def bericht(frage: str, *, grenze: int = GRENZE) -> str:
    """Die Treffer als Text - mit dem Vorbehalt, nicht ohne."""
    treffer = durchsuche(frage, grenze=grenze)
    zeilen = [f"Gesucht: {frage}", ""]
    if not treffer:
        zeilen.append("  Keine Stelle gefunden.")
    for platz, t in enumerate(treffer, start=1):
        zeilen.append(f"  {platz}. {t.stelle}")
        zeilen.append(f"     {t.stelle.zeile[:88]}")
        zeilen.append(f"     Worte: {', '.join(t.worte)}")
    gefunden, von = quote(grenze=grenze)
    zeilen += [
        "",
        f"  {VORBEHALT}",
        "",
        f"  Abnahme an den eigenen Fehlgriffen: {gefunden} von {von} "
        f"in den ersten {grenze} Treffern.",
    ]
    return "\n".join(zeilen)
