"""Halten die Quelltext-Wachen, was sie behaupten? - Befund 399.

``assert "..." in inspect.getsource(x)`` ist der haeufigste Wachentyp dieses
Projekts: 1051 Stellen. Er ist erfuellt, sobald die Zeichenkette irgendwo
vorkommt - **auch in einem Kommentar oder Docstring**. Dieses Projekt schreibt
lange Kommentare, die den Code zitieren; eine Wache, die nur das Zitat trifft,
haelt nichts fest.

Dieser Waechter zaehlt an der Suite nach. Er loest jede Zusicherung auf, deren
Quelle aus einem einfachen ``inspect.getsource(modul.name)`` kommt, und
verlangt, dass das Literal im **Code** vorkommt - nicht nur in der Prosa.

Gemessen beim Bau: 81 aufloesbar, **4 trafen nur Prosa**, und alle vier waren
Absicht (eine Begruendung, die dastehen soll). Keine Wache war kaputt; was
fehlte, war die Unterscheidung. Sie steht jetzt im Test selbst - wer Prosa
pruefen will, schreibt ``nur_prosa(...)`` davor, und die Zusicherung wird
dadurch strenger: Sie faellt auch, wenn der Satz in den Code wandert.

**Was dieser Waechter nicht kann.** 970 der 1051 Stellen loest er nicht auf,
weil die Quelle aus einem Ausdruck kommt, den er nicht nachvollzieht. Die
Abdeckung steht deshalb als eigene Zusicherung daneben - ein Audit, das
nichts mehr aufloest, waere sonst gruen und leer (dieselbe Gegenprobe wie in
``test_suchbudget_greift``).

**Und sein Urteil haengt am Importstand** (Vermerk aus Befund 409).
``_quelle_von`` importiert nur das oberste Paket und greift dann per
``getattr``. Ein Untermodul, das noch niemand importiert hat, loest damit
nicht auf und zaehlt als "offen". Dieselbe Datei ist deshalb **allein gruen
und in der vollen Suite rot**: Genau das ist in Befund 409 passiert, mit einer
Zusicherung, die einen Kommentar traf und es nicht hingeschrieben hatte.

Nachgemessen, was daran haengt: Mit dem laengsten importierbaren Praefix
statt des obersten Pakets loest das Audit **92 statt 91** Stellen auf, und es
findet genau **eine** weitere - die aus 409, und die ist versorgt. Der Mangel
ist also echt und seine Wirkung heute eine Stelle. Er steht hier, statt dass
jemand ihn fuer eine Lappalie haelt: Eine Wache, deren Urteil davon abhaengt,
was sonst gelaufen ist, kann jederzeit wieder etwas durchlassen.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib

import pytest

from tests.quelltext import nur_code

#: Variablennamen, die in diesem Projekt einen Quelltext tragen.
TRAEGER = ("quelle", "src", "code", "text", "kopf", "rumpf", "koerper")

#: So viele Stellen muss das Audit mindestens aufloesen. Beim Bau waren es
#: 81; die Schranke liegt darunter, damit ein geloeschter Test nicht den
#: Waechter faellt - aber nicht so tief, dass er leerlaufen kann.
MINDESTENS_AUFGELOEST = 60


def _quelle_von(ausdruck: str) -> str | None:
    """``inspect.getsource(cli.stand)`` -> der Quelltext, oder ``None``.

    Bewusst nur dieser eine Fall. Wer mehr aufloesen will, baut hier eine
    kleine Auswertung ein - und jede davon kann irren, waehrend dieser Fall
    eindeutig ist.
    """
    if not (
        ausdruck.startswith("inspect.getsource(") and ausdruck.endswith(")")
    ):
        return None
    ziel = ausdruck[len("inspect.getsource(") : -1].strip()
    if not ziel or not all(t.isidentifier() for t in ziel.split(".")):
        return None
    teile = ziel.split(".")
    try:
        objekt: object = importlib.import_module(teile[0])
    except Exception:
        return None
    for t in teile[1:]:
        objekt = getattr(objekt, t, None)
        if objekt is None:
            return None
    try:
        return inspect.getsource(objekt)  # type: ignore[arg-type]
    except (OSError, TypeError):
        return None


def _audit() -> tuple[list[tuple[str, int, str, str]], int, int]:
    """(nur Prosa getroffen, aufgeloest, nicht aufloesbar)."""
    nur_prosa_treffer: list[tuple[str, int, str, str]] = []
    aufgeloest = offen = 0
    for pfad in sorted(pathlib.Path("tests").glob("test_*.py")):
        try:
            baum = ast.parse(pfad.read_text())
        except SyntaxError:  # pragma: no cover - waere ein kaputter Test
            continue
        for funktion in ast.walk(baum):
            if not isinstance(funktion, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            traeger: dict[str, str] = {}
            for knoten in ast.walk(funktion):
                if (
                    isinstance(knoten, ast.Assign)
                    and len(knoten.targets) == 1
                    and isinstance(knoten.targets[0], ast.Name)
                ):
                    traeger[knoten.targets[0].id] = ast.unparse(knoten.value)
            for knoten in ast.walk(funktion):
                if not isinstance(knoten, ast.Assert):
                    continue
                pruefung = knoten.test
                if not (
                    isinstance(pruefung, ast.Compare)
                    and len(pruefung.ops) == 1
                    and isinstance(pruefung.ops[0], ast.In)
                    and isinstance(pruefung.left, ast.Constant)
                    and isinstance(pruefung.left.value, str)
                ):
                    continue
                ziel = pruefung.comparators[0]
                if not isinstance(ziel, ast.Name):
                    continue
                if not any(w in ziel.id for w in TRAEGER):
                    continue
                ausdruck = traeger.get(ziel.id)
                quelle = None if ausdruck is None else _quelle_von(ausdruck)
                if quelle is None:
                    offen += 1
                    continue
                aufgeloest += 1
                literal = pruefung.left.value
                if literal in quelle and literal not in nur_code(quelle):
                    nur_prosa_treffer.append(
                        (pfad.name, knoten.lineno, ausdruck, literal)
                    )
    return nur_prosa_treffer, aufgeloest, offen


@pytest.fixture(scope="module")
def audit():
    return _audit()


class TestKeineWacheTrifftNurProsa:
    def test_jede_zusicherung_trifft_den_code(self, audit) -> None:
        treffer, _, _ = audit

        assert treffer == [], (
            "Diese Zusicherungen treffen nur Kommentar oder Docstring - der "
            "Code kann weg, und sie bleiben gruen. Wer eine Begruendung "
            "pruefen will, schreibt 'nur_prosa(...)' davor (Befund 399): "
            + "; ".join(
                f"{d}:{z} {lit!r} in {a}" for d, z, a, lit in treffer
            )
        )

    def test_und_das_audit_loest_ueberhaupt_etwas_auf(self, audit) -> None:
        """Die Gegenprobe. Ohne sie waere ein Audit, das nichts mehr
        aufloest, gruen und leer - dieselbe Falle wie bei der Rumpfpruefung
        in ``test_suchbudget_greift``."""
        _, aufgeloest, _ = audit

        assert aufgeloest >= MINDESTENS_AUFGELOEST, (
            f"nur {aufgeloest} Stellen aufgeloest, erwartet mindestens "
            f"{MINDESTENS_AUFGELOEST} - loest '_quelle_von' noch auf, was es soll?"
        )

    def test_die_abdeckung_wird_genannt_und_nicht_behauptet(self, audit) -> None:
        """**Die Zahl deckt nicht alles ab**, und das gehoert dazu: Die
        meisten Stellen holen ihre Quelle aus einem Ausdruck, den dieses
        Audit nicht nachvollzieht. Beim Bau waren es 81 von 1051."""
        _, aufgeloest, offen = audit

        assert offen > aufgeloest, (
            "Wenn das Audit die Mehrheit aufloest, ist der Kopf dieser Datei "
            "veraltet - dann steht dort eine zu vorsichtige Einschraenkung."
        )


class TestDieWerkzeugeDahinter:
    """Gegenproben an bekannten Stellen - sonst prueft das Audit mit einem
    Werkzeug, das selbst nicht stimmt. Mein erster Entwurf hat die Token
    wieder zusammengefuegt und Leerzeichen dazwischengesetzt; aus ``a = f(b)``
    wurde ``a  =  f ( b )``, und es kamen 142 Fehlalarme heraus.
    """

    @staticmethod
    def _quelle():
        import cli

        return inspect.getsource(cli.stand)

    def test_code_bleibt_stehen(self) -> None:
        assert "spotrahmen = alle_geschnitten(frames)" in nur_code(self._quelle())

    def test_eine_gedruckte_zeichenkette_auch(self) -> None:
        """Was ein Befehl druckt, ist eine Zusicherung wert - ausgeblendet
        wird nur, was **blosser** Zeichenketten-Ausdruck ist."""
        assert "DIE GATES IM EINZELNEN" in nur_code(self._quelle())

    def test_ein_kommentar_nicht(self) -> None:
        from tests.quelltext import nur_prosa

        satz = "Jahresrendite von einer Gesamtrendite abzuziehen"

        assert satz in self._quelle()
        assert satz not in nur_code(self._quelle())
        assert satz in nur_prosa(self._quelle())

    def test_ein_feldkommentar_auch_nicht(self) -> None:
        """Die Bauart aus ``GateResult.bedingung``: eine Zeichenkette als
        blosser Ausdruck hinter einem Feld (Befund 395)."""
        from research.gates import GateResult

        quelle = inspect.getsource(GateResult)

        assert "bedingung: str" in nur_code(quelle)
        assert "Eine Spalte, zwei Groessen, Faktor elf" not in nur_code(quelle)

    def test_die_laenge_bleibt_gleich(self) -> None:
        """Positionsgetreu: Sonst verschieben sich die Zeilen, und ein
        mehrteiliges Literal trifft nicht mehr."""
        quelle = self._quelle()

        assert len(nur_code(quelle)) == len(quelle)
        assert nur_code(quelle).count("\n") == quelle.count("\n")

    def test_code_und_prosa_ergaenzen_sich(self) -> None:
        from tests.quelltext import nur_prosa

        quelle = self._quelle()
        code, prosa = nur_code(quelle), nur_prosa(quelle)

        for i, zeichen in enumerate(quelle):
            if zeichen in " \n":
                continue
            assert (code[i] == zeichen) != (prosa[i] == zeichen), i

    def test_rumpf_ist_die_kurzform(self) -> None:
        import cli
        from tests.quelltext import rumpf

        assert rumpf(cli.stand) == nur_code(inspect.getsource(cli.stand))

    def test_eine_eingerueckte_methode_geht_auch(self) -> None:
        """``getsource`` einer Methode ist eingerueckt und als Modul nicht
        parsebar - deshalb der ``cleandoc``-Versuch in ``_bereiche``."""
        from research.jahresbild import Jahresbild
        from tests.quelltext import nur_prosa

        quelle = inspect.getsource(Jahresbild.urteil)
        code, prosa = nur_code(quelle), nur_prosa(quelle)

        assert quelle.startswith("    def urteil("), "sonst prueft dies nichts"
        assert "Auch das bestandene Gate wird zerlegt" in prosa
        assert "Auch das bestandene Gate wird zerlegt" not in code
        assert "Das Gate nimmt das Minimum" in code, "gedruckte Zeichenkette"

    def test_ungueltige_syntax_bleibt_unangetastet(self) -> None:
        """Die gemessene Grenze des Werkzeugs, und sie wird genannt statt
        behauptet: Bei nicht tokenisierbarem Text blendet ``nur_code`` nichts
        aus - ein Kommentar ueberlebt also.

        Das ist die unangenehme Richtung, aber es trifft nichts: Eine Quelle
        aus ``inspect.getsource`` ist immer gueltiger Python-Text. Von Hand
        gebaute Schnipsel sind der einzige Fall, und fuer die ist dieser Test
        die Warnung.
        """
        schnipsel = "def f(:\n    # ein Kommentar\n    pass\n"

        ergebnis = nur_code(schnipsel)

        assert len(ergebnis) == len(schnipsel)
        assert "ein Kommentar" in ergebnis


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_die_zahlen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 399)

        assert "1051" in eintrag.ergebnis
        assert "81" in eintrag.ergebnis
        assert "142" in eintrag.ergebnis

    def test_und_dass_keine_wache_kaputt_war(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 399)

        assert "war keine Wache kaputt" in eintrag.ergebnis
        assert "Absicht" in eintrag.ergebnis

    def test_und_398_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 398).zuletzt == 399
