"""Code von Prosa trennen - fuer Wachen, die am Quelltext pruefen.

Warum es diese Datei gibt
-------------------------
Die Suite prueft an 1051 Stellen, ob eine Zeichenkette im Quelltext einer
Funktion vorkommt. Das ist der haeufigste Wachentyp dieses Projekts, und er
hat eine Eigenschaft, die man leicht uebersieht: **Er trifft auch einen
Kommentar.** Dieses Projekt schreibt lange Kommentare, die den Code zitieren -
eine Wache, die nur das Zitat trifft, haelt nichts fest. Der Code kann weg,
der Kommentar bleibt, und der Test ist gruen.

Die Unterscheidung ist nicht neu. Befund 210 hat sie eingefuehrt und
``test_suchbudget_greift`` hat sie seit Befund 332 von Hand gebaut:

    rumpf = quelle.replace(cli._budget_erschoepft.__doc__ or "", "")

Das streicht den Docstring der Funktion - und nur den. Kommentare im Rumpf
bleiben stehen, und bei ``__doc__ is None`` streicht es gar nichts.

Was gemessen ist
----------------
Ueber die Suite nachgezaehlt (Befund 399): Von **81** Zusicherungen, die sich
aufloesen liessen, treffen **4** nur Prosa. Alle vier sind **Absicht** - sie
pruefen, dass eine Begruendung dasteht:

    test_budgetvergleich      'Dann ist das Fenster zu und nicht weiter ...'
    test_katalogschaetzung    '242/309'
    test_suchbudget_greift    '230'   (und sagt es selbst im Docstring)
    test_ws                   'vierundzwanzig Kerzen'

Es war also keine Wache kaputt. Was fehlte, ist die **Unterscheidung**: Beide
Sorten sahen gleich aus, und bei der naechsten waere nicht aufgefallen, welche
gemeint war. Mit ``nur_prosa`` steht die Absicht im Test, und die Zusicherung
wird dabei strenger - sie faellt jetzt auch, wenn der Satz in den Code wandert.

Seit die vier umgestellt sind, zaehlt das Audit **76 aufgeloest, 0 nur
Prosa**: Eine Zusicherung gegen ``nur_prosa(...)`` ist kein schlichter Name
mehr und faellt aus der Zaehlung heraus. Dass die Zahl sinkt, ist also das
Zeichen der Umstellung, nicht ihr Verlust.

**Die Zahl deckt nicht alles ab.** 970 der 1051 Stellen liessen sich nicht
aufloesen, weil die Quelle nicht aus einem einfachen
``inspect.getsource(modul.name)`` kommt. Die 4 sind also 4 von 81, nicht 4 von
1051; der Waechter in ``test_wachenaudit`` haelt beide Zahlen fest.
"""

from __future__ import annotations

import ast
import inspect
import io
import tokenize

__all__ = ["nur_code", "nur_prosa", "rumpf"]


def _bereiche(quelle: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Wo in ``quelle`` Prosa steht: Kommentare und blosse Zeichenketten.

    Eine Zeichenkette **im Code** ist keine Prosa: Was ein Befehl druckt, ist
    eine Zusicherung wert. Ausgeblendet wird nur, was blosser Ausdruck ist -
    Docstrings und die Feldkommentare dieses Projekts.
    """
    aus: list[tuple[tuple[int, int], tuple[int, int]]] = []
    try:
        aus += [
            (tok.start, tok.end)
            for tok in tokenize.generate_tokens(io.StringIO(quelle).readline)
            if tok.type == tokenize.COMMENT
        ]
    except (tokenize.TokenError, IndentationError):
        return aus

    # ``getsource`` einer Methode ist eingerueckt und allein nicht parsebar.
    for kandidat in (inspect.cleandoc("\n" + quelle), quelle):
        try:
            baum = ast.parse(kandidat)
        except SyntaxError:
            continue
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Expr):
                continue
            wert = knoten.value
            if isinstance(wert, ast.Constant) and isinstance(wert.value, str):
                aus.append(
                    (
                        (wert.lineno, wert.col_offset),
                        (wert.end_lineno or wert.lineno, wert.end_col_offset or 0),
                    )
                )
        break
    return aus


def _ersetze(quelle: str, *, behalte_prosa: bool) -> str:
    """Prosa ausblenden - oder alles andere.

    **Positionsgetreu**, Zeichen fuer Zeichen. Ein erster Entwurf hat die
    Token wieder zusammengefuegt und dabei Leerzeichen dazwischengesetzt; aus
    ``a = f(b)`` wurde ``a  =  f ( b )``, und damit war fast jedes
    mehrteilige Literal "nur Prosa" - 142 Fehlalarme bei 81 pruefbaren
    Stellen (Befund 399).
    """
    felder = [list(z) for z in quelle.splitlines(keepends=True)]
    treffer = [[False] * len(z) for z in felder]
    for (z1, s1), (z2, s2) in _bereiche(quelle):
        for z in range(z1, z2 + 1):
            if not 1 <= z <= len(felder):
                continue
            von = s1 if z == z1 else 0
            bis = s2 if z == z2 else len(felder[z - 1])
            for i in range(von, min(bis, len(felder[z - 1]))):
                treffer[z - 1][i] = True
    for z, reihe in enumerate(felder):
        for i, zeichen in enumerate(reihe):
            if zeichen == "\n":
                continue
            if treffer[z][i] != behalte_prosa:
                reihe[i] = " "
    return "".join("".join(z) for z in felder)


def nur_code(quelle: str) -> str:
    """Derselbe Quelltext, aber Kommentare und Docstrings sind Leerzeichen."""
    return _ersetze(quelle, behalte_prosa=False)


def nur_prosa(quelle: str) -> str:
    """Derselbe Quelltext, aber **nur** Kommentare und Docstrings.

    Damit wird eine Begruendungs-Wache ausdruecklich - und strenger: Sie
    faellt jetzt auch, wenn der Satz aus dem Kommentar in den Code wandert.
    """
    return _ersetze(quelle, behalte_prosa=True)


def rumpf(objekt: object) -> str:
    """``nur_code(inspect.getsource(objekt))`` - was wirklich laeuft."""
    return nur_code(inspect.getsource(objekt))
