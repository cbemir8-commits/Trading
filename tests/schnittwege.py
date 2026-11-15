"""Woran man sieht, dass ein Befehl auf die Reihe schneidet - Befund 491.

Warum es diese Datei gibt
-------------------------
Die Antwort stand **achtmal** im Baum, jedes Mal als derselbe Funktionsname -
gezaehlt am Stand vor diesem Befund, nicht geschaetzt:

    assert "alle_geschnitten(frames)" in quelle        test_abstandsreihe:69
    g = "alle_geschnitten" in block                    test_abstandsreihe:231
    assert "alle_geschnitten(frames)" in self._quelle()  test_anatomie:304
    assert "alle_geschnitten(roh)" in koerper          test_aufteilungsstr.:175
    assert "spotrahmen = alle_geschnitten(frames)" ... test_elf_zeilen:54
    assert "alle_geschnitten(frames)" in quelle        test_rennengrundlage:46
    assert "spotrahmen = alle_geschnitten(frames)" ... test_wachenaudit:195
    if "alle_geschnitten" not in wf[name]              test_reihenschnitt:121

Als Befund 491 die neun schneidenden Befehle auf den intervallbewussten
Verteiler ``datenstand.nach_intervall`` umgestellt hat, fielen davon **fuenf**
im Lauf; die drei in ``test_abstandsreihe`` und ``test_reihenschnitt`` hatte
ich beim Bauen schon von Hand nachgezogen, und genau daran war zu sehen, dass
die Bauart falsch ist, nicht die einzelne Zeile. Die Inventur in
``test_abstandsreihe`` meldete dabei **einen** Schneider statt neun, also acht
Befehle, die sich zurueckentschieden haetten. Keiner hatte sich entschieden;
sie rufen nur eine andere Funktion.

Das ist die Lehre aus Befund 282 und 479, hier zum **dritten** Mal: Eine
Wache am Namen einer Funktion verliert genau die, die sich aendern. Beim
Versuchszaehler steht sie deshalb in ``tests/zaehlerwege.py``; hier steht sie
fuer den Reihenschnitt.

Was die Wege unterscheidet
--------------------------
* ``alle_geschnitten`` kuerzt auf ``SERIENENDE`` - die **Tagesreihe**.
* ``alle_fein_geschnitten`` kuerzt auf ``FEINENDE`` - die **Feinreihe**,
  halboffen am oberen Ende.
* ``nach_intervall`` waehlt zwischen beiden und sagt, welche. Seit 491 gehen
  alle neun Befehle darueber, weil die Wahl von Hand an neun Stellen genau
  einmal zu oft getroffen wird (Befund 168).

Ein direkter Aufruf der Tagesfassung ist seit 491 verboten - nicht weil sie
falsch waere, sondern weil sie die Kerzenlaenge nicht kennt.
"""

from __future__ import annotations

import ast
from pathlib import Path

__all__ = ["SCHNITTWEGE", "schneidende_befehle", "schneidet"]

#: Die Wege, auf denen ein Befehl auf eine gepflegte Reihe schneidet.
SCHNITTWEGE: tuple[str, ...] = (
    "alle_geschnitten",
    "alle_fein_geschnitten",
    "nach_intervall",
)


def schneidet(quelle: str) -> bool:
    """Schneidet dieser Quelltext auf eine gepflegte Reihe?"""
    return any(f"{weg}(" in quelle for weg in SCHNITTWEGE)


def schneidende_befehle(quelle: str | None = None) -> set[str]:
    """Alle Befehle in ``cli.py``, die auf eine Reihe schneiden.

    Gefunden und nicht gelistet - sonst waeren es wieder zwei Wahrheiten
    (Befund 234). ``quelle`` ist nur fuer die Gegenproben der Tests da.
    """
    text = Path("cli.py").read_text(encoding="utf-8") if quelle is None else quelle
    gefunden: set[str] = set()
    for knoten in ast.walk(ast.parse(text)):
        if not isinstance(knoten, ast.FunctionDef) or knoten.name.startswith("_"):
            continue
        if schneidet(ast.unparse(knoten)):
            gefunden.add(knoten.name)
    return gefunden
