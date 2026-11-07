"""Eine Verbotsregel an einer Datei zu pruefen ist eine Entscheidung (Befund 464).

Woher das kommt
---------------
Befund 463 hat dreimal dasselbe gefunden: eine richtige Regel, deren Wache in
zu wenige Dateien sieht.

* Befund 213 - *"wer ein Intervall nennt, nennt das Datum mit"* - sah in vier
  Dateien; zwei Verletzungen standen in zwei anderen.
* Befund 357/359 - *"jede Ladezeile nennt den Zulassungskorb"* - galt fuer
  ``BEIM_NUTZER``; acht kopierbare Vorschriften daneben nannten ihn nicht.
* Befund 210 - *"das System hat elf Gates, nicht neun"* - sah in **eine**
  Datei; die falsche Zahl lebte an sieben Stellen in fuenf Dateien weiter.

Dreimal derselbe Bauplan: Die Wache steht dort, wo der Fehler gefunden wurde,
und nicht dort, wo die Regel gilt. Also die Frage an die ganze Suite: **Wo
steht noch so eine?**

Was gemessen ist
----------------
Eine *Verbotsregel* ist ein Test, der behauptet, etwas komme **nicht** vor -
``assert ... not in ...``, ``assert not ...``, ``assert ... == []``. Genau
diese Form ist von Natur aus projektweit: "nirgends" ist keine Eigenschaft
einer Datei.

    Verbotsregeln mit weiter Reichweite (Glob, abgeleitete Liste)      7
    Verbotsregeln an genau einer Datei                                 7

Und alle sieben sind berechtigt - jede steht unten mit ihrem Grund. **Die
Klasse ist leer**, und dieser Test haelt sie leer: Eine neue Verbotsregel an
einer einzelnen Datei faellt hier auf und verlangt entweder die Reichweite
oder einen Satz dazu.

**Sieben und nicht sechs**, und der Unterschied ist wieder mein Erkenner: Der
erste kannte als leere Sammlung nur ``[]``. ``test_die_offenen_werden_wirklich
_durchsucht`` prueft ``ohne == ()`` und fiel damit aus der Grundgesamtheit -
lautlos, denn eine zu kleine Grundgesamtheit sieht aus wie ein gutes Ergebnis.
Deshalb kennt ``_ist_leer`` jetzt alle drei Formen, und drei Zusicherungen
unten pruefen den Erkenner selbst.

Mein eigener Messfehler dabei
-----------------------------
Der erste Lauf meldete **13** statt 6, und einer der Treffer war
``test_jeder_aufruf_im_projekt_nennt_seine_herkunft`` - die Wache, die
sicherstellt, dass kein ``evaluate_gates`` ohne Herkunftsangabe laeuft. An der
haengt die Sperre selbst (``GateReport.passed`` verlangt ``not
referenzdaten``), und es sah aus wie ein Loch an der folgenreichsten Stelle.

Es war keines. Der Test liest ``[*Path("research").glob("*.py"), Path("cli.py")]``
- mein Erkenner sah nur woertliche Dateinamen und den Glob nicht. Nachgezaehlt
hat ``evaluate_gates`` **26** Aufrufstellen, alle in ``cli.py`` und
``research/admission.py``, also beide in der Reichweite dieser Wache.

Dieselbe Lehre wie Befund 118, diesmal an meinem eigenen Werkzeug: Eine Suche,
deren Treffer man ungeprueft uebernimmt, ist schlimmer als keine.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
TESTS = sorted((WURZEL / "tests").glob("test_*.py"))

#: Aufrufe, die eine Regel ueber **mehr** als die genannten Dateien fuehren.
#:
#: ``behauptungsquellen`` steht hier, weil Befund 463 die Liste ausdruecklich
#: abgeleitet statt gepflegt hat - wer sie benutzt, hat weite Reichweite.
WEITE_REICHWEITE = frozenset(
    {"glob", "rglob", "iterdir", "walk", "behauptungsquellen", "vorschriften"}
)

#: Verbotsregeln, die mit Absicht auf **eine** Datei sehen, mit Grund.
#:
#: Ein Eintrag heisst: "Diese Regel gilt wirklich nur fuer diese Datei." Wer
#: einen hinzufuegt, schreibt den Grund dazu - genauso wie bei
#: ``ENTSCHEIDUNGSGATES`` (Befund 461): Wer eine Stelle der Pruefung entzieht,
#: nennt sie, statt sie zu erraten.
ABSICHTLICH_ENG: dict[tuple[str, str], str] = {
    (
        "test_ideenstreuung.py",
        "test_der_modulkopf_von_wettrennen_behauptet_es_nicht_mehr",
    ): (
        "Die Regel handelt von diesem Modulkopf. 'Mehr gibt es nicht' war "
        "seine Aussage, Befund 237 hat sie widerlegt - an einer anderen Datei "
        "waere nichts zu pruefen."
    ),
    ("test_reihenfolge.py", "test_jede_fundstelle_steht_im_laborbuch"): (
        "Das Laborbuch **ist** die eine Datei, von der die Regel spricht. "
        "Seit Befund 464 fuehrt sie 'nachmessung.ohne_abschnitt' aus, also "
        "denselben Parser wie die Suche, die das Laborbuch durchsucht."
    ),
    ("test_stand.py", "test_jede_fundstelle_gibt_es_wirklich"): (
        "Dieselbe Regel am Laborbuch, fuer GESCHLOSSEN und fuer OFFEN - zwei "
        "Tests gleichen Namens in zwei Klassen."
    ),
    ("test_stand.py", "test_jede_behobene_fundstelle_steht_im_laborbuch"): (
        "Dieselbe Regel am Laborbuch, fuer BEHOBEN - und seit Befund 464 "
        "auch fuer die 91 'zuletzt' dieser Liste, die vorher niemand "
        "geprueft hat."
    ),
    ("test_nachmessung.py", "test_die_offenen_werden_wirklich_durchsucht"): (
        "Das Laborbuch ist hier nicht eine Datei unter vielen, sondern der "
        "**Korpus**, ueber den die Suche laeuft. Geprueft wird, dass keine "
        "offene Richtung ohne Suchbegriffe dasteht (Befund 294)."
    ),
    ("test_stand.py", "test_keine_stelle_nennt_mehr_neun_gates"): (
        "Seit Befund 463 ausdruecklich die Gegenprobe an 'cli.py'. Die weite "
        "Pruefung derselben Regel steht in 'test_ladehinweise' und fuehrt "
        "ueber jede Datei, die etwas behauptet."
    ),
}


def _literale_dateien(fn: ast.AST) -> set[str]:
    """Quelldateien, die dieser Test namentlich liest."""
    aus = set()
    for n in ast.walk(fn):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "Path"
            and n.args
            and isinstance(n.args[0], ast.Constant)
            and isinstance(n.args[0].value, str)
            and n.args[0].value.endswith((".py", ".md"))
        ):
            aus.add(n.args[0].value)
    return aus


def _hat_weite_reichweite(fn: ast.AST) -> bool:
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute) and f.attr in WEITE_REICHWEITE:
            return True
        if isinstance(f, ast.Name) and f.id in WEITE_REICHWEITE:
            return True
    return False


def _ist_leer(knoten: ast.AST) -> bool:
    """Ist das eine leere Sammlung - ``[]``, ``()``, ``set()``?

    **Alle drei Formen**, und das ist kein Zierrat: Befund 464 hat vier
    Pruefungen auf ``nachmessung.ohne_abschnitt`` umgestellt, das ein Tupel
    liefert. Wer hier nur ``[]`` kennt, verliert sie lautlos aus der
    Grundgesamtheit - eine Wache, die nichts mehr findet, ist gruen und leer
    (Befund 209).
    """
    if isinstance(knoten, ast.List | ast.Tuple):
        return not knoten.elts
    return (
        isinstance(knoten, ast.Call)
        and isinstance(knoten.func, ast.Name)
        and knoten.func.id == "set"
        and not knoten.args
    )


def _ist_verbot(fn: ast.AST) -> bool:
    """Behauptet dieser Test, dass etwas **nicht** vorkommt?"""
    for n in ast.walk(fn):
        if not isinstance(n, ast.Assert):
            continue
        t = n.test
        if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
            return True
        if isinstance(t, ast.Compare):
            if any(isinstance(o, ast.NotIn) for o in t.ops):
                return True
            if (
                isinstance(t.ops[0], ast.Eq)
                and len(t.comparators) == 1
                and _ist_leer(t.comparators[0])
            ):
                return True
    return False


def _verbotsregeln() -> tuple[list[tuple[str, str, str]], int]:
    """Die engen Verbotsregeln, und wie viele weite es gibt."""
    eng: list[tuple[str, str, str]] = []
    weit = 0
    for datei in TESTS:
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for fn in ast.walk(baum):
            if not isinstance(fn, ast.FunctionDef):
                continue
            if not fn.name.startswith("test_") or not _ist_verbot(fn):
                continue
            dateien = _literale_dateien(fn)
            if _hat_weite_reichweite(fn):
                weit += 1 if dateien else 0
                continue
            if len(dateien) == 1:
                eng.append((datei.name, fn.name, next(iter(dateien))))
    return eng, weit


class TestJedeEngeVerbotsregelIstBegruendet:
    """**Die tragende Wache.** Sie verbietet nichts - sie verlangt einen Satz."""

    def test_keine_unbegruendete_enge_regel(self) -> None:
        eng, _ = _verbotsregeln()
        ohne_grund = [
            (d, f, z) for d, f, z in eng if (d, f) not in ABSICHTLICH_ENG
        ]

        assert ohne_grund == [], "\n".join(
            f"{d}::{f} prueft nur {z}, aber 'nicht vorkommen' ist keine "
            f"Eigenschaft einer Datei - entweder die Reichweite erweitern "
            f"oder den Grund in ABSICHTLICH_ENG schreiben (Befund 464)."
            for d, f, z in ohne_grund
        )

    def test_die_abnahme_hat_keine_leichen(self) -> None:
        """Eine Ausnahme fuer einen Test, den es nicht mehr gibt, ist eine
        Erlaubnis ins Leere - und die naechste Regel rutscht darunter hinweg."""
        eng, _ = _verbotsregeln()
        vorhanden = {(d, f) for d, f, _ in eng}
        verwaist = sorted(set(ABSICHTLICH_ENG) - vorhanden)

        assert verwaist == [], f"begruendet, aber nicht mehr da: {verwaist}"

    def test_jeder_grund_ist_einer(self) -> None:
        """Ein Platzhalter waere schlimmer als keine Liste."""
        for schluessel, grund in ABSICHTLICH_ENG.items():
            assert len(grund) > 60, schluessel
            assert any(c.isdigit() for c in grund) or "Laborbuch" in grund, (
                f"{schluessel}: ein Grund nennt eine Fundstelle oder die "
                f"Sache, um die es geht"
            )


class TestDieMessungSelbst:
    """Die Zahlen aus dem Modulkopf, als Zusicherung - sonst sind sie Prosa."""

    def test_beide_bauarten_kommen_wirklich_vor(self) -> None:
        """**Hier stand erst "es gibt mehr weite als enge Regeln".** Gemessen
        sind es sieben und sieben - die Behauptung war falsch, und sie war
        meine. Was zutrifft und etwas sichert: Beide Bauarten gibt es, also
        ist die enge keine Eigenart einer einzelnen Datei."""
        eng, weit = _verbotsregeln()
        dateien = {d for d, _, _ in eng}

        assert weit and eng
        assert len(dateien) >= 3, f"enge Regeln nur in {dateien}"

    def test_die_grundgesamtheit_ist_nicht_leer(self) -> None:
        """Eine Wache, die nichts mehr findet, sichert nichts zu (Befund 209)."""
        eng, weit = _verbotsregeln()

        assert eng, "keine enge Verbotsregel gefunden - Erkenner pruefen"
        assert weit >= 5, f"nur {weit} weite Regeln - Erkenner pruefen"

    @pytest.mark.parametrize(
        "quelle",
        [
            "assert x not in text",
            "assert not treffer",
            "assert fehlend == []",
            "assert fehlend == ()",
            "assert doppelt == set()",
        ],
    )
    def test_der_erkenner_kennt_jede_form_eines_verbots(self, quelle: str) -> None:
        baum = ast.parse(f"def test_x():\n    {quelle}\n")

        assert _ist_verbot(baum.body[0])

    @pytest.mark.parametrize(
        "quelle",
        ["assert x in text", "assert len(y) == 3", "assert fehlend == [1]"],
    )
    def test_und_keine_zusicherung_die_keines_ist(self, quelle: str) -> None:
        baum = ast.parse(f"def test_x():\n    {quelle}\n")

        assert not _ist_verbot(baum.body[0])


class TestDieSperreWirdUeberallGeprueft:
    """**Der Fall, den ich zuerst falsch gelesen habe.**

    ``GateReport.passed`` verlangt ``not referenzdaten``, und die Herkunft
    kommt aus den Namen der Kursreihen. Ein ``evaluate_gates`` ohne
    Herkunftsangabe waere damit die folgenreichste Luecke, die dieses Projekt
    haben kann - Befund 283 hatte sie schon einmal.
    """

    @staticmethod
    def _aufrufstellen() -> list[str]:
        aus = []
        for p in sorted(WURZEL.rglob("*.py")):
            teile = p.relative_to(WURZEL).parts
            if "tests" in teile or ".venv" in teile or "__pycache__" in teile:
                continue
            baum = ast.parse(p.read_text(encoding="utf-8"))
            for n in ast.walk(baum):
                if (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "evaluate_gates"
                ):
                    aus.append(f"{p.relative_to(WURZEL)}:{n.lineno}")
        return aus

    def test_alle_aufrufe_liegen_in_der_reichweite_der_wache(self) -> None:
        """Gemessen, nicht angenommen: Die Wache sieht in ``research/*.py``
        und ``cli.py`` - also muessen alle Aufrufe dort liegen."""
        draussen = [
            s
            for s in self._aufrufstellen()
            if not (s.startswith("cli.py:") or s.startswith("research/"))
        ]

        assert draussen == [], (
            f"evaluate_gates ausserhalb der Reichweite von "
            f"'test_jeder_aufruf_im_projekt_nennt_seine_herkunft': {draussen}"
        )

    def test_und_es_gibt_sie_wirklich(self) -> None:
        stellen = self._aufrufstellen()

        assert len(stellen) > 20, f"nur {len(stellen)}: {stellen}"
