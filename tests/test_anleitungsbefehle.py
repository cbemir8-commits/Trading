"""Auch die Anleitungen bitten jemanden, etwas zu tun - Befund 478.

``tests/test_nutzerbefehle`` parst ``BEIM_NUTZER`` gegen die echte
Kommandozeile und sagt in seinem Kopf:

    ``BEIM_NUTZER`` ist die **einzige** Stelle, an der dieses Projekt
    jemanden bittet, etwas auf seinem eigenen Rechner zu tun.

Das ist nicht so. ``README.md``, ``install.py``, ``deploy/README.md`` und
``deploy/WINDOWS.md`` tun es auch - gemessen **37** Befehlszeilen -, und keine
davon wurde geparst. Drei waren nicht benutzbar:

    .venv\\Scripts\\python -m cli setup       Bybit verbinden
    .venv\\Scripts\\python -m cli backfill -m ... --von 2017-08-16    Kurse laden
    .venv\\Scripts\\python -m cli research    Strategie suchen

Sie stehen in einem Codeblock unter der Zeile *"Kurzfassung - nach jedem
Befehl kurz schauen, ob etwas Rotes dabei war"*, also als etwas, das man
eintippt. Ihre Erlaeuterung trug kein ``#``. Wer die erste Zeile einfuegt,
bekommt

    Got unexpected extra argument(s) (Bybit verbinden)

und das ist woertlich die Meldung aus **Befund 167** - derselbe Fehler, neun
Jahre Projektzeit spaeter in der Datei, die die Haustuer ist. Die anderen
Anleitungen machen es richtig: ``deploy/README.md`` setzt ``#`` vor die
Erlaeuterung, ``deploy/WINDOWS.md`` laesst den Befehl allein stehen.

Geparst und nicht gefahren, wie in 307: Das geht ohne Boerse, Schluessel und
Daten, und es findet genau diese Klasse.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

import click
import pytest
import typer

from cli import app

WURZEL = Path(__file__).resolve().parents[1]

#: Die Dateien, die jemanden bitten, etwas auf seinem Rechner zu tun.
#:
#: Dieselbe Liste wie die Markdown- und Skriptquellen in
#: ``test_ladehinweise.QUELLEN`` - dort wird geprueft, **was** die Zeilen
#: laden, hier, ob sie sich **aufrufen** lassen. Zwei Fragen, zwei Wachen.
DATEIEN: tuple[str, ...] = (
    "README.md",
    "install.py",
    "deploy/README.md",
    "deploy/WINDOWS.md",
)

#: ``python -m cli ...`` in jeder Schreibweise, die in diesen Dateien vorkommt:
#: nackt, ``.venv/bin/python``, ``.venv\Scripts\python`` - und ``{python}``,
#: weil ``install.py`` seine drei Zeilen als f-String druckt.
AUFRUF = re.compile(
    r"(?:\{python\}|[\w./\\$-]*python(?:\.exe)?)\s+-m\s+cli\s+(.*)"
)

#: Woran der Befehl endet, wenn er **nicht** die ganze Zeile ist.
#:
#: **Drei Anlaeufe hat dieser Melder gebraucht** (Befund 478), und die zwei
#: falschen sind der Grund, warum das hier steht. Am Zeilenanfang verankert
#: fand er 'install.py' nicht, weil dort ``say(f"  1.  {python} -m cli
#: setup")`` steht. Unverankert fand er eine **Tabellenzeile** des README und
#: hielt die halbe Prosa dahinter fuer Argumente. Ein Melder, der das falsche
#: Ding findet, ist schlimmer als keiner - also wird der Treffer begrenzt.
GRENZEN = ("`", '"', "'")

#: Zeichen, die eine Zeile als Zeichnung ausweisen und nicht als Befehl.
KASTEN = frozenset("\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524"
                   "\u252c\u2534\u253c\u25b6\u25c0\u2190\u2192")


@dataclass(frozen=True, slots=True)
class Zeile:
    datei: str
    nummer: int
    rest: str
    """Alles nach ``cli``, begrenzt und ohne Shell-Kommentar."""

    gezeichnet: bool
    """Eine Zeile einer Zeichnung - kein Aufruf, den jemand eintippt."""


def _begrenzt(rest: str) -> str:
    """Bis zum ersten schliessenden Zeichen - oder bis zum Zeilenende."""
    enden = [rest.index(z) for z in GRENZEN if z in rest]
    if enden:
        rest = rest[: min(enden)]
    return rest.strip()


def zeilen(text: str, datei: str) -> tuple[Zeile, ...]:
    """Jede Befehlszeile dieser Datei, begrenzt und ohne Kommentar.

    **Der Shell-Kommentar gehoert abgestreift und nicht beanstandet**: ``cli
    quality # Luecken`` ist eine richtige Zeile, in PowerShell wie in der
    Shell. Mein erster Melder hat sechzehn solche Zeilen gemeldet.
    """
    aus: list[Zeile] = []
    for i, roh in enumerate(text.splitlines(), 1):
        treffer = AUFRUF.search(roh)
        if treffer is None:
            continue
        rest = _begrenzt(treffer.group(1))
        gezeichnet = bool(KASTEN & set(rest))
        if not gezeichnet:
            rest = re.split(r"\s+#", rest, maxsplit=1)[0].strip()
        if not rest:
            continue
        aus.append(
            Zeile(datei=datei, nummer=i, rest=rest, gezeichnet=gezeichnet)
        )
    return tuple(aus)


def _alle() -> tuple[Zeile, ...]:
    gefunden: list[Zeile] = []
    for name in DATEIEN:
        gefunden += zeilen((WURZEL / name).read_text(encoding="utf-8"), name)
    return tuple(gefunden)


ALLE = _alle()
AUFRUFBAR = tuple(z for z in ALLE if not z.gezeichnet)


@pytest.fixture(scope="module")
def gruppe() -> click.Group:
    return typer.main.get_command(app)


class TestDerMelderTaugt:
    """In dieser Sitzung haben meine Melder sechzehn Mal zu viel gemeldet -
    dieser auch, beim ersten Anlauf."""

    def test_er_findet_genug_zeilen(self) -> None:
        assert len(ALLE) >= 30, len(ALLE)
        assert len(AUFRUFBAR) >= 30, len(AUFRUFBAR)

    def test_er_beanstandet_keinen_shell_kommentar(self) -> None:
        """Die Gegenprobe gegen den eigenen ersten Anlauf."""
        gefunden = zeilen("python -m cli quality   # Luecken, Duplikate", "probe")

        assert len(gefunden) == 1
        assert gefunden[0].rest == "quality"

    def test_er_findet_die_alte_fassung_der_kurzfassung(self) -> None:
        """Genau die Zeile, die nicht benutzbar war."""
        gefunden = zeilen(
            r".venv\Scripts\python -m cli setup       Bybit verbinden", "probe"
        )

        assert len(gefunden) == 1
        assert gefunden[0].rest == "setup       Bybit verbinden"

    def test_er_nimmt_zeichnungen_heraus(self) -> None:
        gefunden = zeilen(
            "python -m cli trade       ──schreibt──▶  "
            "state/live.json",
            "probe",
        )

        assert len(gefunden) == 1
        assert gefunden[0].gezeichnet


#: Zeilen, die die **Gruppe** selbst aufrufen und keinen Befehl.
#:
#: ``python -m cli --help`` ist eine richtige Zeile - nur ist ``--help`` eine
#: Option der Gruppe und kein Befehl, und meine Wache hat sie deshalb als
#: fehlenden Befehl gemeldet. Vierter Anlauf, derselbe Grund wie die drei
#: davor: Die Form war nicht so einfach, wie ich sie gern haette.
def _ist_gruppenaufruf(rest: str) -> bool:
    return shlex.split(rest)[0].startswith("-")


class TestJedeZeileLaesstSichAufrufen:
    def test_den_befehl_gibt_es(self, gruppe: click.Group) -> None:
        oben = click.Context(gruppe)
        fehlend = [
            f"{z.datei}:{z.nummer} ({shlex.split(z.rest)[0]})"
            for z in AUFRUFBAR
            if not _ist_gruppenaufruf(z.rest)
            and gruppe.get_command(oben, shlex.split(z.rest)[0]) is None
        ]

        assert fehlend == [], fehlend

    def test_und_die_gruppenaufrufe_kennt_die_gruppe(self, gruppe: click.Group) -> None:
        """``python -m cli --help`` ruft die Gruppe und keinen Befehl."""
        gruppenzeilen = [z for z in AUFRUFBAR if _ist_gruppenaufruf(z.rest)]

        assert gruppenzeilen, "ohne eine solche Zeile prueft dieser Test nichts"
        namen = {o.name for p in gruppe.params for o in (p,)}
        for z in gruppenzeilen:
            for stueck in shlex.split(z.rest):
                if not stueck.startswith("-"):
                    continue
                assert stueck in {"--help"} or stueck.lstrip("-") in namen, (
                    f"{z.datei}:{z.nummer}: '{stueck}' kennt die Gruppe nicht"
                )

    def test_und_die_argumente_lassen_sich_lesen(self, gruppe: click.Group) -> None:
        """**Die Zusicherung von Befund 478.** Unbekannte Optionen, fehlende
        Werte, Prosa hinter dem Befehl - alles faellt hier auf, ohne Boerse,
        Schluessel oder Daten.
        """
        oben = click.Context(gruppe)
        kaputt: list[str] = []
        for z in AUFRUFBAR:
            if _ist_gruppenaufruf(z.rest):
                continue
            teile = shlex.split(z.rest)
            cmd = gruppe.get_command(oben, teile[0])
            if cmd is None:
                continue
            unten = click.Context(cmd, info_name=teile[0], parent=oben)
            try:
                cmd.parse_args(unten, teile[1:])
            except Exception as e:
                kaputt.append(f"{z.datei}:{z.nummer} '{z.rest}' -> {e}")

        assert kaputt == [], kaputt

    def test_jede_datei_traegt_wirklich_zeilen(self) -> None:
        """Sonst koennte eine Datei aus der Liste fallen und niemand merkte
        es - die Wache bestaende weiter."""
        je_datei = {name: 0 for name in DATEIEN}
        for z in ALLE:
            je_datei[z.datei] += 1

        leer = [name for name, anzahl in je_datei.items() if anzahl == 0]
        assert leer == [], f"keine Befehlszeile gefunden in: {leer}"


class TestDieZeichnungenSindBenannt:
    """Eine Ausnahme, die niemand nachrechnet, ist ein Loch."""

    def test_jede_ausgenommene_zeile_ist_wirklich_eine_zeichnung(self) -> None:
        for z in ALLE:
            if not z.gezeichnet:
                continue
            assert KASTEN & set(z.rest), f"{z.datei}:{z.nummer}"

    def test_es_sind_wenige_und_sie_stehen_in_der_uebersicht(self) -> None:
        gezeichnet = [z for z in ALLE if z.gezeichnet]

        assert len(gezeichnet) == 2, [(z.datei, z.nummer) for z in gezeichnet]
        assert {z.datei for z in gezeichnet} == {"README.md"}


class TestDerFremdeKopfBehauptetEsNichtMehr:
    def test_test_nutzerbefehle_nennt_die_anderen_stellen(self) -> None:
        """Die Aussage *"die einzige Stelle"* war der Grund, warum niemand
        weitergesucht hat."""
        kopf = (WURZEL / "tests" / "test_nutzerbefehle.py").read_text(
            encoding="utf-8"
        )

        assert "ist die **einzige** Stelle" not in kopf
        assert "test_anleitungsbefehle" in kopf
