"""Es gibt **einen** Weg in den Markt, und er liegt hinter dem Officer - 480.

``tests/test_risk_officer`` nennt den Risk-Officer *"das Einzige, was zwischen
einer fehlerhaften Strategie und einem leeren Konto steht"*. Das ist die
folgenreichste Behauptung dieses Projekts - dort haengt echtes Geld dran, und
die Live-Schleife laeuft nachts unbeaufsichtigt.

**Gemessen stimmt sie.** Die Ordergateway-Aufrufe liegen an fuenf Stellen:
vier in ``execution/router.py`` und eine in ``execution/live.py``. Die eine
dort ist ein ``reduce_only``-Notausstieg einer Position **ohne Stop** - die
darf der Officer nicht blockieren, und das steht im Code so. Der Einstieg
selbst geht ueber ``router.open``, und der hat **genau einen** Aufrufer:

    execution/live.py:1696   decision = self.officer.evaluate(...)
    execution/live.py:1702   if isinstance(decision, Vetoed): ... return
    execution/live.py:1716   self.bracket = self.router.open(signal, decision.sized)

**Nichts hat das geprueft.** 42 Teststellen nennen ``router.open``,
``officer.evaluate`` oder ``Vetoed`` - alle pruefen Verhalten. Die
**Struktur** - ein Weg, hinter dem Tor - war ungesichert: Ein Umbau mit einem
zweiten Einstieg, oder einer, der den Officer erst danach fragt, waere durch
die ganze Suite gekommen.

Das ist dieselbe Lage wie in Befund 394 und 477: Das Wissen liegt im System,
nur nicht dort, wo es wirkt. Hier ist es angeschlossen.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Wo nach Ordern gesucht wird. ``tests`` und ``.venv`` bleiben draussen -
#: eine Probe darf Orders stellen, ein Testlauf nicht gemeldet werden.
ORDNER: tuple[str, ...] = ("execution", "web", "core", "live")

#: Die Datei, die den Gateway benutzen **darf**.
ROUTER = "execution/router.py"

#: Die Methoden des Gateways, die Geld bewegen.
STELLT_ORDER: frozenset[str] = frozenset({"place_limit", "place_market"})


@dataclass(frozen=True, slots=True)
class Stelle:
    datei: str
    zeile: int
    methode: str
    reduce_only: bool
    """``True``, wenn der Aufruf ausdruecklich nur verkleinert."""


def _dateien() -> list[Path]:
    aus = [WURZEL / "cli.py"]
    for name in ORDNER:
        ordner = WURZEL / name
        if ordner.is_dir():
            aus += sorted(ordner.rglob("*.py"))
    return [p for p in aus if p.exists()]


def _reduce_only(aufruf: ast.Call) -> bool:
    for kw in aufruf.keywords:
        if kw.arg == "reduce_only":
            return isinstance(kw.value, ast.Constant) and kw.value.value is True
    return False


def orderstellen(text: str, datei: str) -> tuple[Stelle, ...]:
    """Jeder Aufruf, der ueber das Gateway eine Order stellt."""
    gefunden: list[Stelle] = []
    for knoten in ast.walk(ast.parse(text)):
        if not isinstance(knoten, ast.Call):
            continue
        if not isinstance(knoten.func, ast.Attribute):
            continue
        if knoten.func.attr not in STELLT_ORDER:
            continue
        gefunden.append(
            Stelle(
                datei=datei,
                zeile=knoten.lineno,
                methode=knoten.func.attr,
                reduce_only=_reduce_only(knoten),
            )
        )
    return tuple(gefunden)


def einstiege(text: str, datei: str) -> tuple[tuple[str, int], ...]:
    """Jeder Aufruf von ``router.open`` - der eine Weg in den Markt.

    Gesucht wird am Syntaxbaum und ueber die Kette: ``self.router.open`` und
    ``router.open`` zaehlen, ``pfad.open`` nicht. Ein Textmuster auf
    ``.open(`` findet jedes Oeffnen einer Datei - davon gibt es in diesem Baum
    vier, und sie haben mit Orders nichts zu tun.
    """
    gefunden: list[tuple[str, int]] = []
    for knoten in ast.walk(ast.parse(text)):
        if not isinstance(knoten, ast.Call):
            continue
        f = knoten.func
        if not isinstance(f, ast.Attribute) or f.attr != "open":
            continue
        kette = ast.unparse(f.value)
        if kette.split(".")[-1] == "router":
            gefunden.append((datei, knoten.lineno))
    return tuple(gefunden)


def _alle_orderstellen() -> tuple[Stelle, ...]:
    aus: list[Stelle] = []
    for p in _dateien():
        aus += orderstellen(
            p.read_text(encoding="utf-8"), str(p.relative_to(WURZEL))
        )
    return tuple(aus)


def _alle_einstiege() -> tuple[tuple[str, int], ...]:
    aus: list[tuple[str, int]] = []
    for p in _dateien():
        aus += einstiege(p.read_text(encoding="utf-8"), str(p.relative_to(WURZEL)))
    return tuple(aus)


ORDERSTELLEN = _alle_orderstellen()
EINSTIEGE = _alle_einstiege()


class TestDerMelderTaugt:
    """Vor der Regel der Melder - in dieser Sitzung war das sechzehn Mal
    noetig."""

    def test_er_findet_die_echten_stellen(self) -> None:
        assert len(ORDERSTELLEN) >= 5, ORDERSTELLEN
        assert EINSTIEGE, "kein Einstieg gefunden - dann prueft alles darunter nichts"

    def test_er_haelt_ein_dateioeffnen_nicht_fuer_einen_einstieg(self) -> None:
        """Die Gegenprobe: ``pfad.open("a")`` ist kein Markteintritt. Ein
        Textmuster auf ``.open(`` findet im Baum vier solche Stellen."""
        assert einstiege('with (pfad / "trades.jsonl").open("a") as h:\n    pass\n',
                         "probe") == ()

    def test_aber_self_router_open_schon(self) -> None:
        assert einstiege("self.bracket = self.router.open(signal, sized)", "probe") == (
            ("probe", 1),
        )

    def test_er_sieht_reduce_only(self) -> None:
        mit = orderstellen(
            "g.place_market(symbol=s, side=x, qty=q, reduce_only=True)", "probe"
        )
        ohne = orderstellen("g.place_market(symbol=s, side=x, qty=q)", "probe")

        assert mit[0].reduce_only
        assert not ohne[0].reduce_only


class TestEsGibtEinenEinstieg:
    def test_genau_einen(self) -> None:
        """Kommt ein zweiter dazu, faellt er hier auf - und muss sich
        entscheiden, ob er hinter das Tor gehoert."""
        assert len(EINSTIEGE) == 1, EINSTIEGE

    def test_und_er_steht_in_der_live_schleife(self) -> None:
        assert EINSTIEGE[0][0] == "execution/live.py"

    def test_und_der_officer_wird_vorher_gefragt(self) -> None:
        """Dieselbe Reihenfolgepruefung wie in ``test_versuchszaehler_wer``:
        gefragt wird **vor** dem Handeln, nicht danach."""
        datei, _ = EINSTIEGE[0]
        baum = ast.parse((WURZEL / datei).read_text(encoding="utf-8"))
        umgebend = [
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef | ast.AsyncFunctionDef)
            and any(
                isinstance(x, ast.Call)
                and isinstance(x.func, ast.Attribute)
                and x.func.attr == "open"
                and ast.unparse(x.func.value).split(".")[-1] == "router"
                for x in ast.walk(k)
            )
        ]

        assert len(umgebend) == 1, [f.name for f in umgebend]
        quelle = ast.unparse(umgebend[0])
        assert "officer.evaluate(" in quelle
        assert "Vetoed" in quelle
        assert quelle.index("officer.evaluate(") < quelle.index("router.open(")


class TestWerSonstEineOrderStellt:
    def test_nur_der_router_stellt_eroeffnende_orders(self) -> None:
        """**Die Regel.** Ausserhalb des Routers darf eine Order nur
        **verkleinern** - dann ist sie ein Schutz und kein Risiko, und der
        Officer darf sie nicht blockieren.
        """
        fremd = [
            f"{s.datei}:{s.zeile} {s.methode}"
            for s in ORDERSTELLEN
            if s.datei != ROUTER and not s.reduce_only
        ]

        assert fremd == [], (
            f"stellt eine Order ausserhalb von {ROUTER}, ohne reduce_only: "
            f"{fremd}"
        )

    def test_und_es_gibt_wirklich_so_eine_stelle(self) -> None:
        """Sonst bestaende die Regel leer. Gemessen ist es der Notausstieg
        einer Position ohne Stop."""
        ausserhalb = [s for s in ORDERSTELLEN if s.datei != ROUTER]

        assert ausserhalb, ORDERSTELLEN
        assert all(s.reduce_only for s in ausserhalb)
        assert {s.datei for s in ausserhalb} == {"execution/live.py"}

    def test_der_router_traegt_die_mehrzahl(self) -> None:
        im_router = [s for s in ORDERSTELLEN if s.datei == ROUTER]

        assert len(im_router) >= 4, im_router
