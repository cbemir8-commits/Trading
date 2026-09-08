"""Zusicherungen ueber **Abwesenheit** - wann sie richtig sind.

**Befund 245.** In Befund 244 ist ein eigener Test gefallen, und zwar zu Recht.
``test_teststaerke_zaehlt_mit`` aus Befund 242 enthielt:

    assert "write_report" not in quelle

Gemeint war *"sie ist leicht zu uebersehen, also pruefe, dass sie mitzaehlt"*.
Dagestanden hat *"sie schreibt selbst, und dabei bleibt es"* - der **Mangel als
Zusicherung festgeschrieben**. Beim Beheben ist der Test gefallen; genau da
merkt man es.

Wann eine negative Zusicherung richtig ist
------------------------------------------
Wenn sie eine **Entscheidung** haelt, die bewusst nicht gefallen ist - nicht,
wenn sie einen Zustand beschreibt.

Der Unterschied am lebenden Beispiel. ``test_die_sweeps_brechen_nicht_ab``
sichert zu, dass ``landschaft`` und ``machbarkeit`` die Budgetgrenze **nicht**
kennen. Das ist richtig: Ob ein Sweep am Bestand als Versuch zaehlt, ist die
offene Frage aus Befund 233/234, und wer die Grenze dort einbaut, beantwortet
sie im Vorbeigehen. Die Zusicherung haelt eine Grenze, keinen Mangel.

Was diese Wache leistet - und was nicht
---------------------------------------
Sie findet negative Zusicherungen ueber die Namen, die im Projekt fuer eine
Wache stehen, und verlangt, dass jede davon **eingetragen und begruendet**
ist. Ein neuer Fall zwingt damit zu der Frage, die in 242 nicht gestellt
wurde: Halte ich hier eine Entscheidung oder einen Zustand?

**Sie findet nicht alles.** Ein Test, der einen falschen *Wert* festschreibt
(``assert x == 0.2765``, als das schon ueberholt war), sieht wie jeder andere
aus. Gegen den hilft nur, was ``referenz.py`` tut: die Zahl an eine Messung
binden. Diese Wache deckt die Bauart ab, nicht die Absicht.
"""

from __future__ import annotations

import ast
from pathlib import Path

#: Namen, die fuer eine Wache oder ein richtiges Bauteil stehen. Eine
#: Zusicherung, dass eines davon **fehlt**, ist erklaerungsbeduerftig.
WACHEN: tuple[str, ...] = (
    "TROCKENLAUF",
    "_betriebspunkt",
    "_budget_erschoepft",
    "_pruefe_generation",
    "_verzeichne",
    "betriebspunkt",
    "erklaert_den_verlauf",
    "kalibrierbereich",
    "noetige_guete",
    "ohne_zensierte",
    "passt_zum_intervall",
    "randtrades",
    "save_trials",
    "scrub",
    "trockenlauf",
    "write_report",
)

#: Die eingetragenen Faelle: Testname -> warum die Abwesenheit gewollt ist.
#:
#: Wer hier etwas eintraegt, behauptet: **Das ist eine Entscheidung, kein
#: Mangel.** Der Satz muss die Entscheidung nennen, nicht den Zustand
#: beschreiben.
BEGRUENDET: dict[str, str] = {
    "test_die_sweeps_brechen_nicht_ab": (
        "Ob ein Sweep am Bestand als Versuch zaehlt, ist offen (Befund "
        "233/234). Wer die Budgetgrenze in 'landschaft' und 'machbarkeit' "
        "einbaut, beantwortet die Frage im Vorbeigehen - die Zusicherung "
        "haelt diese Grenze."
    ),
}


def _negative_zusicherungen() -> dict[str, tuple[str, int, str]]:
    """Jeder Test, der die Abwesenheit einer Wache zusichert."""
    gefunden: dict[str, tuple[str, int, str]] = {}
    for datei in sorted(Path("tests").glob("test_*.py")):
        baum = ast.parse(datei.read_text())
        for funktion in ast.walk(baum):
            if not isinstance(funktion, ast.FunctionDef):
                continue
            if not funktion.name.startswith("test_"):
                continue
            for knoten in ast.walk(funktion):
                if not isinstance(knoten, ast.Assert):
                    continue
                text = ast.unparse(knoten.test)
                if " not in " not in text:
                    continue
                for wache in WACHEN:
                    if f"'{wache}'" in text or f'"{wache}"' in text:
                        gefunden[funktion.name] = (datei.name, knoten.lineno, wache)
                        break
    return gefunden


class TestJedeAbwesenheitIstBegruendet:
    def test_keine_unerklaerte_negative_zusicherung(self) -> None:
        """**Die Wache gegen den naechsten Fall wie Befund 242.**

        Faellt hier ein neuer Name auf, ist die Frage zu beantworten: Halte
        ich eine Entscheidung, die bewusst nicht gefallen ist - oder schreibe
        ich einen Mangel fest, den jemand spaeter behebt?

        Im ersten Fall gehoert er nach ``BEGRUENDET``, im zweiten gehoert die
        Zusicherung weg.
        """
        offen = sorted(set(_negative_zusicherungen()) - set(BEGRUENDET))

        assert offen == [], (
            f"sichern die Abwesenheit einer Wache zu, ohne Eintrag in "
            f"BEGRUENDET: {offen}"
        )

    def test_der_eingetragene_fall_gibt_es_noch(self) -> None:
        """Ein Eintrag fuer einen Test, den es nicht mehr gibt, ist genau die
        Sorte Altlast, gegen die dieses Projekt seine Register prueft."""
        vorhanden = set(_negative_zusicherungen())
        verwaist = sorted(set(BEGRUENDET) - vorhanden)

        assert verwaist == [], f"steht in BEGRUENDET, gibt es nicht mehr: {verwaist}"

    def test_jede_begruendung_nennt_eine_fundstelle(self) -> None:
        """Eine Entscheidung ohne Befund waere eine Meinung - dieselbe Regel
        wie fuer ``Richtung`` und ``Schritt``."""
        for name, grund in BEGRUENDET.items():
            assert "Befund" in grund, name


class TestWasDerFallVonBefund244War:
    def test_teststaerke_sichert_die_abwesenheit_nicht_mehr_zu(self) -> None:
        """Der behobene Fall - er darf nicht zurueckkommen."""
        gefunden = _negative_zusicherungen()

        assert "test_teststaerke_zaehlt_mit" not in gefunden

    def test_sie_geht_inzwischen_durch_die_wache(self) -> None:
        import ast as _ast

        baum = _ast.parse(Path("cli.py").read_text())
        quelle = next(
            _ast.unparse(n)
            for n in _ast.walk(baum)
            if isinstance(n, _ast.FunctionDef) and n.name == "teststaerke"
        )

        assert "write_report" in quelle
