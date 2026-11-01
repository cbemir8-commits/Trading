"""Welchen Urteilssatz hat nie ein Test gelesen? - Befund 444.

Befund 443 hat in ``Reibungsprobe.urteil`` einen Satz gefunden, der eine
Groesse **behauptete**, die er nicht gemessen hat: *"es gibt eine Bremse, die
mehr wert ist als alle Kosten zusammen"*. Er stand als Zeichenkette im Code,
und er war falsch - die Bremse trug +0,0222, die Kosten zusammen +0,0253.

**Gefunden habe ich ihn durch Zufall**, beim Nachrechnen einer anderen Zahl.
Das ist der eigentliche Mangel: Die Stelle war nicht schwer zu sehen, nur
hatte niemand hingesehen. Und sie war auch nicht schwer zu *finden* - der
Zweig stand in keinem Test.

Die Fehlerklasse
----------------
Eine Funktion, die je nach Ausgang etwas anderes behauptet, hat mehrere
Textrueckgaben. Jede davon ist eine Aussage. Eine, die kein Test erreicht,
ist eine **ungelesene** Aussage: Sie kann falsch sein, ohne dass etwas rot
wird.

Dieses Modul findet sie in zwei Haelften, und beide Haelften sind getrennt,
weil nur die zweite einen Lauf braucht:

**Statisch** (``urteilsfunktionen``) - alle Funktionen in ``research/`` mit
mindestens zwei Textrueckgaben, per AST. Braucht nichts weiter als die
Dateien.

**Dynamisch** (``ungelesene``) - welche dieser Zeilen eine Messung nie
erreicht hat. Die Messung kommt **von aussen** als Abbildung Datei ->
erreichte Zeilen, damit dieses Modul nicht von ``coverage`` abhaengt und in
der normalen Auswahl pruefbar bleibt.

Beide Haelften gehoeren zu **derselben Quelle**
-----------------------------------------------
Die statische Analyse liest die Dateien, wie sie **jetzt** sind; die Messung
sagt, welche Zeilennummern ein Lauf erreicht hat. Stehen die beiden auf
verschiedenen Staenden, ist das Ergebnis Unsinn.

**Genau das ist mir beim ersten Auswerten passiert**: Die Coverage-Daten
stammten von vor einer Aenderung an ``benchmark.py``, die Zeilennummern
hatten sich dadurch verschoben, und zwei Eintraege der Fahndungsliste waren
Artefakte - gemeldet wurde ein Zweig, den es in dieser Form nicht mehr gab.
Wer hier auswertet, faehrt die Auswahl **nach** der letzten Aenderung.

Was es nicht ist
----------------
**Kein Gate.** Eine ungelesene Rueckgabe ist ein Verdacht, keine Schuld: Der
Zweig fuer "keine Stufen gemessen" gehoert in jedes ordentliche Urteil und
wird zu Recht selten gefahren. Dieses Modul liefert die Reihenfolge, in der
hinzusehen ist - entschieden wird beim Lesen (Befund 118).

Der erste Lauf
--------------
Gemessen an der Nicht-Daten-Auswahl (Befund 444):

    Urteilsfunktionen (>= 2 Textrueckgaben)    157
    davon mit mindestens einer ungelesenen      29
    ganz ungelesen                               2

Nachgesehen habe ich die ganz ungelesenen und die, deren Zweig etwas
**vergleicht** - dort sitzt die Fehlerklasse aus 443.

**Ein echter Fund**: ``benchmark.verdict_for`` nannte eine Strategie mit
74,9 % Rueckgang gegen eine Messlatte von 75,0 % "deutlich ruhiger" und
empfahl sie einem Konto, das bei 15 % abschaltet. Der Massstab stand im Kopf
desselben Moduls und wurde nicht gerechnet.

**Ein Verdacht, der sich beim Lesen aufloeste**:
``vorratsdecke._deckentext`` behauptet "die Kopplung traegt" - und
``tragfaehig`` ist vorher geprueft, der Kontrollfluss deckt den Satz.
Nachsehen heisst nicht finden.

**Der Rest sind Entartungsfaelle**, die "" oder "zu wenige Bloecke fuer eine
Aussage" zurueckgeben. Sie gehoeren dort hin und sind zu Recht selten
gefahren - deshalb ist diese Liste eine Reihenfolge und kein Mangel.
"""

from __future__ import annotations

import ast
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

#: Ab wie vielen Textrueckgaben eine Funktion als Urteil gilt.
#:
#: Eine einzige Rueckgabe behauptet immer dasselbe - sie kann falsch sein,
#: aber nicht *je nach Ausgang* falsch, und genau das war der Fall in 443.
MINDESTZWEIGE: int = 2


@dataclass(frozen=True, slots=True)
class Urteil:
    """Eine Funktion, die je nach Ausgang etwas anderes behauptet."""

    modul: str
    funktion: str
    zeilen: tuple[int, ...]
    """Die Zeilen, in denen sie Text zurueckgibt."""

    ab: int
    """Zeile der ``def`` - zum Nachschlagen."""

    @property
    def name(self) -> str:
        return f"{self.modul}:{self.funktion}"

    @property
    def zweige(self) -> int:
        return len(self.zeilen)


def _ist_text(knoten: ast.expr) -> bool:
    """Gibt dieser Ausdruck einen Text?

    Erkannt werden f-Strings, Zeichenketten, ``+``/``%`` darauf und
    Methodenaufrufe auf einem Text (``"...".format``, ``" ".join``). Nicht
    erkannt wird ein Name, der einen Text haelt - dafuer braeuchte es eine
    Typpruefung, und ein Modul, das Typen raet, waere selbst eine
    Behauptung.
    """
    if isinstance(knoten, ast.JoinedStr):
        return True
    if isinstance(knoten, ast.Constant):
        return isinstance(knoten.value, str)
    if isinstance(knoten, ast.BinOp):
        return _ist_text(knoten.left) or _ist_text(knoten.right)
    if isinstance(knoten, ast.Call):
        ziel = knoten.func
        return isinstance(ziel, ast.Attribute) and _ist_text(ziel.value)
    return False


def textrueckgaben(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, ...]:
    """Die Zeilen, in denen **diese** Funktion Text zurueckgibt.

    **Verschachtelte Geltungsbereiche gehoeren nicht dazu.** ``ast.walk``
    steigt in innere ``def`` ab, und mein erster Entwurf hat deren ``return``
    mitgezaehlt - die Zahl war dadurch zu hoch (140 statt 135), bevor sie
    gepinnt war. Ein Modul, das ungemessene Behauptungen findet, darf nicht
    mit einer falschen Zahl anfangen.
    """
    zeilen: list[int] = []

    def gehe(knoten: ast.AST) -> None:
        for kind in ast.iter_child_nodes(knoten):
            if isinstance(
                kind,
                ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef,
            ):
                continue
            if (
                isinstance(kind, ast.Return)
                and kind.value is not None
                and _ist_text(kind.value)
            ):
                zeilen.append(kind.lineno)
            gehe(kind)

    gehe(fn)
    return tuple(sorted(set(zeilen)))


def urteilsfunktionen(
    wurzel: Path | None = None, *, mindestens: int = MINDESTZWEIGE
) -> tuple[Urteil, ...]:
    """Alle Urteilsfunktionen unter ``wurzel`` - nach Name geordnet."""
    ordner = wurzel or Path(__file__).resolve().parent
    gefunden: list[Urteil] = []
    for pfad in sorted(ordner.glob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            zeilen = textrueckgaben(knoten)
            if len(zeilen) < mindestens:
                continue
            gefunden.append(
                Urteil(
                    modul=pfad.name,
                    funktion=knoten.name,
                    zeilen=zeilen,
                    ab=knoten.lineno,
                )
            )
    return tuple(sorted(gefunden, key=lambda u: u.name))


def ungelesene(
    urteile: tuple[Urteil, ...],
    gemessen: Mapping[str, Collection[int]],
    *,
    wurzel: Path | None = None,
) -> tuple[tuple[Urteil, tuple[int, ...]], ...]:
    """Welche Textrueckgaben die Messung nie erreicht hat.

    ``gemessen`` bildet Dateipfade auf erreichte Zeilen ab - so, wie
    ``coverage`` es hergibt. Eine Datei, die gar nicht gemessen wurde, zaehlt
    **vollstaendig** als ungelesen: "nicht gemessen" ist nicht dasselbe wie
    "gelesen", und das zu verwechseln waere der Freibrief aus Befund 430.
    """
    ordner = wurzel or Path(__file__).resolve().parent
    nach_name = {Path(p).name: set(z) for p, z in gemessen.items()}
    aus: list[tuple[Urteil, tuple[int, ...]]] = []
    for u in urteile:
        erreicht = nach_name.get(u.modul)
        if erreicht is None:
            # Auch der Vollstaendigkeit halber: nur, wenn die Datei
            # ueberhaupt existiert - sonst ist die Messung zur Quelle
            # verschoben und die Aussage waere ueber nichts.
            if (ordner / u.modul).exists():
                aus.append((u, u.zeilen))
            continue
        offen = tuple(z for z in u.zeilen if z not in erreicht)
        if offen:
            aus.append((u, offen))
    return tuple(aus)


def bericht(
    urteile: tuple[Urteil, ...],
    offen: tuple[tuple[Urteil, tuple[int, ...]], ...],
) -> str:
    """Die Fahndungsliste - ganz ungelesene zuerst."""
    if not urteile:
        return "Keine Urteilsfunktionen gefunden - dazu ist nichts zu sagen."
    if not offen:
        return (
            f"{len(urteile)} Urteilsfunktionen, und jede Textrueckgabe ist "
            f"gelesen. Das heisst nicht, dass jede **geprueft** ist - nur, "
            f"dass kein Zweig unbetreten blieb."
        )
    sortiert = sorted(
        offen, key=lambda p: (-len(p[1]) / p[0].zweige, p[0].name)
    )
    zeilen = [
        f"Urteilsfunktionen (>= {MINDESTZWEIGE} Textrueckgaben): {len(urteile)}",
        f"davon mit ungelesener Rueckgabe:{' ' * 23}{len(offen)}",
        "",
        "Ganz ungelesen zuerst - dort hat kein Test je einen Satz gesehen:",
        "",
    ]
    for u, zs in sortiert:
        ganz = " <- ganz ungelesen" if len(zs) == u.zweige else ""
        zeilen.append(
            f"  {u.name:46s} {len(zs)} von {u.zweige:<3d} Zeilen "
            f"{list(zs)}{ganz}"
        )
    zeilen += [
        "",
        "**Ein Verdacht, keine Schuld** (Befund 118): Der Zweig fuer 'nichts "
        "gemessen' gehoert in jedes ordentliche Urteil und wird zu Recht "
        "selten gefahren. Zuerst hinzusehen ist dort, wo ein Zweig etwas "
        "**vergleicht** - das war die Stelle in Befund 443.",
    ]
    return "\n".join(zeilen)
