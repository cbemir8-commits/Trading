"""Ein Uebersprung, der nichts mehr prueft - Befund 470.

Die Suite war gruen: 6679 bestanden, **2 uebersprungen**. Die zwei sassen in
Tests, die sich selbst als den eigentlichen Beweis bezeichnen:

* ``test_der_verbund_stimmt_mit_dem_lauf_ueberein`` ist der einzige Test, der
  die drei Verbundzahlen gegen den echten Walk-Forward nachrechnet; sein
  Docstring sagt, er existiere, "damit Befund 140 nicht dasselbe Schicksal
  erleidet wie Befund 73". Er uebersprang an ``versuche != 198``. Gemessen
  haengt keine seiner Zahlen am Zaehler - bei 203 bestehen alle drei Paare.
* ``test_der_deckel_greift_und_kuerzt`` nennt sich "**Der eigentliche Test**"
  und uebersprang, weil sein Aufbau die Deckelwirkung nie erzeugte: beide
  Beine 48, die Vereinigung 96, nichts zu deckeln.

Diese Datei verzeichnet die Bauart, die das moeglich gemacht hat, und
verbietet sie: **Kein Uebersprung haengt an einer eingetragenen Zahl.** Eine
Schwelle ("weniger als vier Reihen im Speicher") ist erlaubt; ein
Gleichheitsvergleich gegen einen gemessenen Stand ist es nicht, denn der
Stand laeuft weiter und der Test verstummt.

**Was hier absichtlich nicht steht.** Die naheliegende breitere Regel - ein
Uebersprung darf nicht an denselben Namen haengen, die der Test zusichert -
traefe gemessen auch sechs voellig richtige Stellen ("keine Kerzen im
Speicher", "kein Vorrat", "Schiefe nicht messbar"). Sie waere eine
Ausnahmeliste und keine Regel; ``test_die_breitere_regel_waere_eine_
ausnahmeliste`` haelt die Zahl fest, statt die Regel zu behaupten.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
TESTDATEIEN = tuple(sorted((WURZEL / "tests").glob("*.py")))


@dataclass(frozen=True, slots=True)
class Stelle:
    """Ein ``pytest.skip`` im Testbaum, mit seiner Bedingung."""

    datei: str
    zeile: int
    funktion: str
    bedingung: str | None
    """``None``, wenn der Uebersprung nicht in einem ``if`` steht - dann ist er
    der Durchfall einer Suche (siehe ``_carry_regel``)."""
    grund: str | None
    hat_schleife: bool
    """Ob die umgebende Funktion eine Schleife enthaelt - das macht einen
    Uebersprung ohne ``if`` zum Durchfall einer Suche und nicht zu einem Test,
    der niemals laeuft."""


def _ist_skip(knoten: ast.AST) -> bool:
    return (
        isinstance(knoten, ast.Call)
        and isinstance(knoten.func, ast.Attribute)
        and knoten.func.attr == "skip"
        and isinstance(knoten.func.value, ast.Name)
        and knoten.func.value.id == "pytest"
    )


def _grund(aufruf: ast.Call) -> str | None:
    args = list(aufruf.args) + [k.value for k in aufruf.keywords if k.arg == "reason"]
    if not args:
        return None
    quelle = args[0]
    if isinstance(quelle, ast.Constant) and isinstance(quelle.value, str):
        return quelle.value
    if isinstance(quelle, ast.JoinedStr):
        return "".join(
            t.value
            for t in quelle.values
            if isinstance(t, ast.Constant) and isinstance(t.value, str)
        )
    return ast.unparse(quelle)


def stellen(baum: ast.AST, datei: str) -> list[Stelle]:
    """Jede Uebersprungsstelle im Baum, der Funktion zugeordnet.

    Gesammelt wird am Syntaxbaum und nicht an Textmustern: Ein Kommentar, der
    ``pytest.skip`` erwaehnt, ist kein Uebersprung, und eine Begruendung in
    Prosa kann keine Zusicherung erfuellen (Befund 399).
    """
    gefunden: list[Stelle] = []
    for funktion in ast.walk(baum):
        if not isinstance(funktion, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        hat_schleife = any(
            isinstance(k, ast.For | ast.AsyncFor | ast.While) for k in ast.walk(funktion)
        )
        bedingt: dict[int, str] = {}
        for knoten in ast.walk(funktion):
            if not isinstance(knoten, ast.If):
                continue
            for k in ast.walk(knoten):
                if _ist_skip(k):
                    bedingt.setdefault(k.lineno, ast.unparse(knoten.test))
        for knoten in ast.walk(funktion):
            if not _ist_skip(knoten):
                continue
            gefunden.append(
                Stelle(
                    datei=datei,
                    zeile=knoten.lineno,
                    funktion=funktion.name,
                    bedingung=bedingt.get(knoten.lineno),
                    grund=_grund(knoten),
                    hat_schleife=hat_schleife,
                )
            )
    return gefunden


def _alle() -> tuple[Stelle, ...]:
    gefunden: list[Stelle] = []
    for datei in TESTDATEIEN:
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        gefunden += stellen(baum, datei.name)
    return tuple(gefunden)


#: Einmal am Modulkopf gerechnet. **Nicht** als Fixture mit Klassenbindung -
#: eine Fixture als Klassenmethode mit anderer Geltung als ``function`` faellt
#: in ``assert not self._finalizers`` (Befund 426/429, dreimal passiert).
ALLE = _alle()


def an_eingetragener_zahl(bedingung: str) -> list[str]:
    """Haengt die Bedingung an einem **Gleichheits**vergleich mit einer Zahl?

    Das ist die Bauart aus Befund 470: ``versuche != 198``. Eine Schwelle
    (``len(stand) < 4``) ist ausdruecklich erlaubt - sie sagt "zu wenig zum
    Messen" und nicht "ein anderer Stand als damals".
    """
    treffer: list[str] = []
    for knoten in ast.walk(ast.parse(bedingung, mode="eval")):
        if not isinstance(knoten, ast.Compare):
            continue
        for op, rechts in zip(knoten.ops, knoten.comparators, strict=True):
            if not isinstance(op, ast.Eq | ast.NotEq):
                continue
            for seite in (knoten.left, rechts):
                if (
                    isinstance(seite, ast.Constant)
                    and isinstance(seite.value, int | float)
                    and not isinstance(seite.value, bool)
                ):
                    treffer.append(ast.unparse(knoten))
    return treffer


class TestDerSpuerhundTaugt:
    """Zuerst der Melder selbst. Eine Zaehlung ohne Gegenprobe hat in diesem
    Projekt schon vier Mal zu viel gemeldet - zuletzt drei Durchfallstellen
    als "unbedingt", obwohl sie das Ende einer Suchschleife sind."""

    def test_er_findet_die_alte_fassung(self) -> None:
        """Genau die Zeile, die zwei Monate lang nichts geprueft hat."""
        assert an_eingetragener_zahl("versuche != 198")

    def test_auch_mit_der_zahl_links(self) -> None:
        assert an_eingetragener_zahl("198 != versuche")

    def test_und_in_einer_zusammengesetzten_bedingung(self) -> None:
        assert an_eingetragener_zahl("not dateien or versuche == 198")

    def test_aber_nicht_bei_einer_schwelle(self) -> None:
        """Die Gegenprobe, auf die es ankommt: Waere sie rot, verbote die
        Regel die richtigen Uebersprungsstellen mit."""
        assert not an_eingetragener_zahl("len(stand) < 4")
        assert not an_eingetragener_zahl("any((f.empty for f in frames.values()))")

    def test_und_nicht_bei_einem_vergleich_ohne_zahl(self) -> None:
        assert not an_eingetragener_zahl("ungedeckelt <= verbund.beinsumme")

    def test_wahrheitswerte_sind_keine_eingetragenen_zahlen(self) -> None:
        """``is True`` ist eine Form und kein gemessener Stand - und ``True``
        ist in Python ein ``int``, also muss die Regel es ausnehmen."""
        assert not an_eingetragener_zahl("gesperrt == True")


class TestDerBestand:
    def test_es_gibt_ueberhaupt_stellen_zu_pruefen(self) -> None:
        """Sonst bestaende alles darunter, weil nichts gefunden wurde - die
        0-von-0-Falle."""
        assert len(ALLE) > 20

    def test_keine_haengt_an_einer_eingetragenen_zahl(self) -> None:
        """**Die Regel.** Gemessen ohne Ausnahme erfuellbar."""
        schuldig = [
            f"{s.datei}:{s.zeile} ({s.bedingung})"
            for s in ALLE
            if s.bedingung and an_eingetragener_zahl(s.bedingung)
        ]

        assert schuldig == [], f"Uebersprung an eingetragener Zahl: {schuldig}"

    def test_jede_sagt_was_fehlt(self) -> None:
        """Ein Uebersprung ohne Grund ist eine Luecke mit gutem Gewissen."""
        stumm = [
            f"{s.datei}:{s.zeile}"
            for s in ALLE
            if not s.grund or len(s.grund.strip()) < 15
        ]

        assert stumm == [], f"Uebersprung ohne Grund: {stumm}"

    def test_eine_stelle_ohne_bedingung_ist_der_durchfall_einer_suche(self) -> None:
        """Ein ``pytest.skip`` ohne ``if`` und ohne Schleife waere ein Test,
        der niemals laeuft. Gemessen sind alle drei solchen Stellen das Ende
        einer Suche ("keine Carry-Regel in Generation 5")."""
        haltlos = [
            f"{s.datei}:{s.zeile} in {s.funktion}"
            for s in ALLE
            if s.bedingung is None and not s.hat_schleife
        ]

        assert haltlos == [], f"Uebersprung ohne Bedingung und ohne Suche: {haltlos}"


class TestDieZweiRepariertenStellen:
    """Dieselben Zusicherungen am Syntaxbaum, damit die Begruendung im
    Kommentar nicht genuegt (Befund 399)."""

    def _funktion(self, datei: str, name: str) -> ast.FunctionDef:
        baum = ast.parse((WURZEL / "tests" / datei).read_text(encoding="utf-8"))
        return next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == name
        )

    def test_der_verbundvergleich_kann_nicht_am_zaehler_ueberspringen(self) -> None:
        eigene = [
            s
            for s in ALLE
            if s.funktion == "test_der_verbund_stimmt_mit_dem_lauf_ueberein"
        ]

        assert eigene, "den Test gibt es nicht mehr - dann gilt diese Wache nichts"
        for s in eigene:
            assert s.bedingung is not None
            assert "versuche" not in s.bedingung, s.bedingung
            assert "empty" in s.bedingung, (
                "der einzige erlaubte Uebersprung dort ist 'keine Kerzen im "
                f"Speicher', gefunden: {s.bedingung}"
            )

    def test_und_rechnet_den_zaehler_trotzdem_mit(self) -> None:
        """Der Zaehler wird weiter gelesen und an ``baue`` gegeben - er geht
        in ``dsr`` und in die Latten. Nur **ueberspringen** darf er nicht."""
        funktion = self._funktion(
            "test_verbund.py", "test_der_verbund_stimmt_mit_dem_lauf_ueberein"
        )
        quelle = ast.unparse(funktion)

        assert "load_trials" in quelle
        assert "versuche=versuche" in quelle

    def test_der_deckeltest_sichert_zu_statt_zu_ueberspringen(self) -> None:
        funktion = self._funktion("test_verbund.py", "test_der_deckel_greift_und_kuerzt")

        assert not [k for k in ast.walk(funktion) if _ist_skip(k)]
        zusicherungen = [
            ast.unparse(k.test) for k in ast.walk(funktion) if isinstance(k, ast.Assert)
        ]
        assert any(
            "ungedeckelt > verbund.beinsumme" in z for z in zusicherungen
        ), zusicherungen


class TestDieGrenzeDerRegel:
    def test_die_breitere_regel_waere_eine_ausnahmeliste(self) -> None:
        """Gemessen, nicht geschaetzt: Wie viele **richtige** Stellen haetten
        dieselbe Bauart wie die falsche?

        "Der Uebersprung haengt an denselben Namen, die der Test zusichert" -
        das trifft die Deckelstelle, aber auch jedes "keine Kerzen im
        Speicher". Darum steht diese Regel nicht in dieser Datei.
        """
        betroffen: list[str] = []
        for datei in TESTDATEIEN:
            baum = ast.parse(datei.read_text(encoding="utf-8"))
            for funktion in ast.walk(baum):
                if not isinstance(funktion, ast.FunctionDef):
                    continue
                zugesichert: set[str] = set()
                for k in ast.walk(funktion):
                    if isinstance(k, ast.Assert):
                        zugesichert |= {
                            n.id for n in ast.walk(k.test) if isinstance(n, ast.Name)
                        }
                for k in ast.walk(funktion):
                    if not isinstance(k, ast.If):
                        continue
                    if not any(_ist_skip(x) for x in ast.walk(k)):
                        continue
                    namen = {
                        n.id for n in ast.walk(k.test) if isinstance(n, ast.Name)
                    }
                    if namen & zugesichert:
                        betroffen.append(f"{datei.name}:{k.lineno} {funktion.name}")

        assert len(betroffen) > 1, (
            "Traefe die breitere Regel nur noch eine Stelle, waere sie keine "
            f"Ausnahmeliste mehr und gehoerte hierher: {betroffen}"
        )
