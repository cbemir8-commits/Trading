"""Eine Stichprobe, eine Stelle - Befund 139.

Der eigentliche Test dieser Datei ist der letzte: Niemand ausser
``research/gates.py`` darf die Einteilung des Gates selbst zusammenbauen.

Ohne diese Pruefung stand die Rechnung in **acht** Fassungen im Baum, jede an
dem Tag eingefroren, an dem sie kopiert wurde. Fuenf davon trugen einen
Kommentar, der versprach, sie sei "genau wie im Gate" - und keiner davon
stimmte noch. Ein Versprechen im Kommentar ist kein Mechanismus.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: Die Dateien, die den Baum ausmachen. ``research/unabhaengigkeit.py``
#: definiert ``effektive_stichprobe`` und ist damit nicht Aufrufer, sondern
#: Eigentuemer; ``research/gates.py`` ist die eine erlaubte Stelle.
QUELLEN = [Path("cli.py"), *sorted(Path("research").glob("*.py"))]
EIGENTUEMER = {"gates.py", "unabhaengigkeit.py"}


def _aufrufe_mit_weitere(pfad: Path) -> list[int]:
    """Zeilen, in denen ``effektive_stichprobe`` mit ``weitere=`` gerufen wird.

    Gesucht wird im **Syntaxbaum**, nicht im Text: Eine Textsuche haette hier
    genau den Fehler aus Befund 118 wiederholt, und der Aufruf verteilt sich
    ohnehin ueber mehrere Zeilen.
    """
    baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
    treffer = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        ziel = knoten.func
        name = ziel.attr if isinstance(ziel, ast.Attribute) else getattr(ziel, "id", "")
        if name != "effektive_stichprobe":
            continue
        if any(k.arg == "weitere" for k in knoten.keywords):
            treffer.append(knoten.lineno)
    return treffer


# --- Die Funktion selbst ----------------------------------------------------


def test_die_gemeinsame_funktion_nimmt_die_quartale_mit() -> None:
    """Sonst waere die Vereinheitlichung eine Verschlechterung."""
    import inspect

    from research.gates import stichprobe_wie_im_gate

    quelle = inspect.getsource(stichprobe_wie_im_gate)
    assert "quartalsbloecke" in quelle
    assert "concurrent_groups" in quelle


def test_das_gate_benutzt_sie() -> None:
    import inspect

    from research.gates import gate_deflated_sharpe

    assert "stichprobe_wie_im_gate" in inspect.getsource(gate_deflated_sharpe)


def test_ohne_bloecke_wird_nicht_gekuerzt() -> None:
    """Eine Kuerzung ohne Messung waere der Fehler, den das Modul verhindert."""
    from research.gates import stichprobe_wie_im_gate

    assert stichprobe_wie_im_gate([]).effektiv == 0


# --- Die eigentliche Pruefung -----------------------------------------------


def test_es_gibt_ueberhaupt_einen_solchen_aufruf() -> None:
    """Ohne diesen Test liefe die naechste Pruefung leer und waere wertlos."""
    gefunden = {
        p.name: _aufrufe_mit_weitere(p)
        for p in QUELLEN
        if p.name in EIGENTUEMER and _aufrufe_mit_weitere(p)
    }
    assert gefunden, "keine Einteilung gefunden - die Pruefung liefe leer"


@pytest.mark.parametrize("pfad", QUELLEN, ids=lambda p: p.name)
def test_niemand_baut_die_einteilung_des_gates_nach(pfad: Path) -> None:
    """Wer die Stichprobe des Gates braucht, ruft ``stichprobe_wie_im_gate``.

    Der Grund steht im Modulkopf: Acht Nachbauten, jeder zu seiner Zeit
    richtig, alle seit Befund 135 falsch - und keiner davon einem Leser
    anzusehen, weil der Kommentar daneben das Gegenteil behauptete.

    Wer hier anschlaegt, hat entweder einen Nachbau eingefuehrt oder einen
    guten Grund. Der gute Grund gehoert dann in diese Liste, mit Fundstelle.
    """
    if pfad.name in EIGENTUEMER:
        return
    zeilen = _aufrufe_mit_weitere(pfad)
    assert not zeilen, (
        f"{pfad.name} baut die Einteilung des Gates selbst zusammen "
        f"(Zeile {', '.join(str(z) for z in zeilen)}). Das ist die Kopie, an "
        f"der Befund 139 haengt - ``research.gates.stichprobe_wie_im_gate`` "
        f"benutzen."
    )
