"""Wer bucht einen Versuch - gefunden, nicht gelistet. Befund 479.

Warum es diese Datei gibt
-------------------------
Die Antwort stand **zweimal** im Baum, und die zwei Fassungen sind
auseinandergelaufen:

``tests/test_versuchszaehler_wer`` sucht nach beiden Buchungswegen. Das ist
die Lehre aus Befund 282, und sie steht dort mit Begruendung - eine Wache am
Namen einer Funktion statt an der Wirkung verliert genau die, die sich
aendern.

``tests/test_rauchtest`` sucht nach **einem**: ``save_trials``. Heute bucht
kein einziger Befehl mehr so - alle sieben gehen ueber ``_verzeichne(`` -,
und damit fand diese Wache die **leere Menge** und verglich sie gegen alles:

    assert zaehlend <= set(WIRKT_NACH_AUSSEN)

Leer ist Teilmenge von allem. Die Wache, die haette melden sollen, wenn ein
Befehl den Versuchszaehler schreibt, ohne als wirkend eingeteilt zu sein,
prueft seit der Umstellung nichts. Und das ist die teuerste Ecke des
Projekts: Jeder gebuchte Versuch hebt die Huerde des Deflated Sharpe
dauerhaft und ist nicht zurueckzuholen.

Die Lehre ist die aus Befund 464: Zwei Fassungen einer Regel sind zwei
Gelegenheiten, dass sie auseinanderlaufen. Deshalb steht sie jetzt einmal
hier, und beide Wachen fragen sie.
"""

from __future__ import annotations

import ast
from pathlib import Path

__all__ = ["BUCHUNGSWEGE", "zaehlende_befehle"]

#: Die beiden Wege, auf denen der Zaehler steigt.
#:
#: **Beide gehoeren hierher** (Befund 282). Bis dahin suchte die Wache nur
#: nach ``save_trials``. Als ``landschaft`` und ``machbarkeit`` auf
#: Einzelnachweise umgestellt wurden, waeren sie damit aus der Aufsicht
#: gefallen - nicht weil sie aufgehoert haetten zu zaehlen, sondern weil sie
#: es anders tun. Eine Wache, die am Namen einer Funktion haengt statt an der
#: Wirkung, verliert genau die, die sich aendern.
#:
#: **Und genau das ist dann passiert** (479), nur eine Datei weiter: Heute
#: kommt ``save_trials`` in keinem Befehlsrumpf mehr vor.
BUCHUNGSWEGE: tuple[str, ...] = ("save_trials", "_verzeichne(")


def zaehlende_befehle(quelle: str | None = None) -> set[str]:
    """Alle Befehle in ``cli.py``, die den Zaehler fortschreiben.

    Gefunden und nicht gelistet - sonst waeren es wieder zwei Wahrheiten
    (Befund 234). ``quelle`` ist nur fuer die Gegenproben der Tests da; ohne
    sie wird ``cli.py`` gelesen.
    """
    text = Path("cli.py").read_text(encoding="utf-8") if quelle is None else quelle
    gefunden: set[str] = set()
    for knoten in ast.walk(ast.parse(text)):
        if not isinstance(knoten, ast.FunctionDef) or knoten.name.startswith("_"):
            continue
        rumpf = ast.unparse(knoten)
        if any(weg in rumpf for weg in BUCHUNGSWEGE):
            gefunden.add(knoten.name)
    return gefunden
