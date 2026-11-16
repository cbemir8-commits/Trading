"""Eine messgenaue Zahl steht an einer Stelle - Befund 500.

Warum es diese Regel gibt
-------------------------
Zwei Befunde hintereinander waren Abschriften derselben Messungen:

* **498**: ``ausschluss.GESCHEITERTE_EIGENBAUTEN`` war vom
  Versuchsverzeichnis abgedriftet - vier von acht Zahlen, bis 6,7e-5, und
  niemand hat verglichen.
* **499**: Dieselben acht Messungen standen noch zweimal da -
  ``GEMESSENE_REGELN`` unter Kurznamen (mein Namensabgleich aus 498 hat sie
  deshalb nicht gefunden) und ``auftragslage.KATALOGPUNKTE`` als Zahlenpaare.

Die Lehre stand am Ende von 499: **Wer eine Abschrift berichtigt, sucht nach
der Zahl und nicht nach dem Namen.** Diese Datei macht aus der Lehre eine
Regel.

Was gemessen wurde
------------------
Durchsucht sind ``cli.py`` und die Ordner ``research``, ``backtest``,
``strategy``, ``core``, ``data`` und ``execution`` nach Gleitkommazahlen mit
**fuenf oder mehr Dezimalstellen** - der Form, die eine Messung hat und keine
Schwelle. Eine Schwelle ist 0,3 oder 1,2; 0,138701 ist ein Ergebnis.

    messgenaue Zahlen im Baum                     10
    davon in mehr als einem Modul                   1

Die eine war ``0.5772156649015329`` - die **Euler-Mascheroni-Konstante**, in
``gates`` und ``wettrennen``, und keine Messung. Ihr Kommentar in
``wettrennen`` wies sie selbst als Zweitschrift aus: *"Dieselbe Konstante aus
demselben Grund - es ist dieselbe Extremwertrechnung."* Ein Kommentar, der
eine Abschrift benennt, ersetzt den Import nicht; das Modul importiert ohnehin
aus ``gates``, und seit 500 holt es die Zahl von dort.

Damit ist die Menge leer - und genau deshalb steht die Nichtleere-Zusicherung
daneben: Eine Regel ueber eine leere Menge besteht immer (die 0-von-0-Falle
aus Befund 209/479). Geprueft wird also beides: dass es solche Zahlen
**gibt** und dass keine zweimal steht.

Was die Regel nicht ist
-----------------------
Sie ist **keine** Aussage ueber Schwellen, Vorgabewerte oder gepinnte
Vergleichszahlen mit wenigen Stellen. Die duerfen mehrfach vorkommen - eine
Schwelle ist eine Entscheidung und keine Messung, und 0,25 an zwei Stellen ist
kein Abdriften. Wer das verwechselt, verbietet die halbe Konfiguration.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Wo gesucht wird: die rechnenden Ordner und die Befehlsdatei.
#:
#: Nicht ``tests`` - dort stehen Messungen absichtlich mehrfach, weil jede
#: Zusicherung ihre Zahl selbst nennen soll. Und nicht ``strategies``, das
#: ist das Laborbuch.
ORDNER: tuple[str, ...] = (
    "research",
    "backtest",
    "strategy",
    "core",
    "data",
    "execution",
)

#: Ab wie vielen Dezimalstellen eine Zahl als Messung gilt.
#:
#: Vier reichen nicht: 0,2708 ist der gepflegte Spot-Punkt und steht
#: absichtlich an mehreren Stellen im Register. Fuenf ist die Grenze, an der
#: eine Zahl aus einer Rechnung kommt und nicht aus einer Entscheidung.
STELLEN = 5


def _dateien() -> list[Path]:
    dateien = [WURZEL / "cli.py"]
    for ordner in ORDNER:
        dateien.extend(sorted((WURZEL / ordner).glob("*.py")))
    return [p for p in dateien if p.exists()]


def messgenaue_zahlen() -> dict[float, set[str]]:
    """Welche messgenaue Zahl steht in welchen Modulen?

    Gefunden und nicht gelistet (Befund 234/485): Kommt ein Modul dazu, ist
    es dabei.
    """
    vorkommen: dict[float, set[str]] = defaultdict(set)
    for pfad in _dateien():
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Constant):
                continue
            if not isinstance(knoten.value, float):
                continue
            text = repr(knoten.value)
            if "." in text and len(text.split(".")[1]) >= STELLEN:
                vorkommen[knoten.value].add(pfad.relative_to(WURZEL).as_posix())
    return dict(vorkommen)


class TestDieGrundgesamtheitIstNichtLeer:
    """**Die 0-von-0-Falle, und sie ist hier real**: Nach Befund 500 ist die
    Menge der doppelten Zahlen leer. Eine Regel darueber besteht immer -
    also wird zuerst geprueft, dass ueberhaupt gesucht wurde."""

    def test_es_gibt_dateien_zu_durchsuchen(self) -> None:
        assert len(_dateien()) > 50, len(_dateien())

    def test_und_messgenaue_zahlen_darin(self) -> None:
        zahlen = messgenaue_zahlen()

        assert len(zahlen) >= 5, sorted(zahlen)

    def test_der_erkenner_nimmt_keine_schwellen(self) -> None:
        """Die Gegenprobe: Wuerde er 0,25 oder 1,2 mitnehmen, verbote die
        Regel die halbe Konfiguration."""
        zahlen = messgenaue_zahlen()

        for zahl in zahlen:
            stellen = len(repr(zahl).split(".")[1])
            assert stellen >= STELLEN, (zahl, stellen)


class TestKeineMessungStehtZweimal:
    def test_keine_zahl_in_zwei_modulen(self) -> None:
        """**Die Regel.** 498 und 499 waren genau das, und beide Male hat es
        niemand gemeldet."""
        doppelt = {
            zahl: sorted(module)
            for zahl, module in messgenaue_zahlen().items()
            if len(module) > 1
        }

        assert doppelt == {}, (
            "steht in mehr als einem Modul - eine Messung gehoert an eine "
            f"Stelle, der Rest holt sie von dort (Befund 498/499/500): "
            f"{doppelt}"
        )

    def test_die_eulerzahl_kommt_aus_gates(self) -> None:
        """Die eine, die es gab - und die Gegenprobe, dass sie wirklich
        geholt wird und nicht nur verschwunden ist."""
        from research import gates, wettrennen

        assert wettrennen.EULER_MASCHERONI == gates.EULER_MASCHERONI
        assert "0.5772156649015329" not in (
            WURZEL / "research" / "wettrennen.py"
        ).read_text(encoding="utf-8")

    def test_und_sie_steht_noch_an_ihrer_stelle(self) -> None:
        """Sonst waere die Regel darueber auch erfuellt, wenn jemand die Zahl
        ueberall geloescht haette."""
        quelle = (WURZEL / "research" / "gates.py").read_text(encoding="utf-8")

        assert "0.5772156649015329" in quelle
