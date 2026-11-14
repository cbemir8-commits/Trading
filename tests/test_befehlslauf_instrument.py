""""cli instrument" brach seit 95 Befunden ab - Befund 473.

Der Rauchtest von Befund 247 hat 52 Befehle mit ihren Voreinstellungen
gefahren, keinen mit einem Traceback. Seither wurde die Liste gepflegt, aber
**nie wieder ganz gefahren** - und genau das steht in ihrem Modulkopf.

Nachgeholt. Von 58 harmlosen Befehlen bricht einer ab:

    cli instrument  ->  InvalidOperation: [<class 'decimal.ConversionSyntax'>]

Die Stelle ist der dritte von drei Messlaeufen des Befehls. Sein Helfer
``messe`` rechnet ``grund.costs.scaled(Decimal(gebuehren))`` - und
``gebuehren`` ist nicht sein eigener Parameter, sondern die
**Kommandozeilen-Option** von ``instrument``. Sein eigener heisst
``gebuehrenfaktor``.

Beide Namen kamen in Befund 377 im selben Commit herein, und der Rumpf griff
von Anfang an den falschen. Ohne ``--gebuehren`` ist die Option der
Leerstring, ``Decimal("")`` wirft, und der Lauf stirbt **nach** den ersten
zwei Zeilen - also sah man zwei Messungen und danach einen Traceback statt des
Urteils. Mit ``--gebuehren`` kehrt der Befehl schon vorher zurueck (die
Gebuehrenleiter ist ein eigener Zweig), die Zeile war also nie erreichbar
richtig.

**Warum kein Test das gesehen hat.** ``tests/test_instrument.py`` prueft das
Modul ``research/instrument`` mit von Hand gebauten ``Lauf``-Objekten, bis
hin zu ``test_der_gebuehrenstress_wird_als_stress_gekennzeichnet`` - der
Darstellung einer Messung, die der Befehl nicht herstellen konnte. Genau das
hat der Lauf zu Befund 425 vorhergesagt: *"Ohne den Lauf waere beides durch
die Tests gekommen, die nur das Modul fragen."*

**Was der Fix sichtbar macht**, eine Zahl, die es vorher nicht gab:

    Spot                        158 Trades   14.34 % p.a.  Rueckgang  9.87 %  9/11
    Spot, doppelte Gebuehren    158 Trades   14.10 % p.a.  Rueckgang 10.10 %  9/11

An den Gebuehren scheitert der Kandidat also nicht - was Bybits Spot-Tarif
wirklich ist, sagt das weiter nicht (Befund 108).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
QUELLE = (WURZEL / "cli.py").read_text(encoding="utf-8")

#: Die drei Zeilen, die der Befehl messen soll.
ZEILEN = ("fraction 1.0", "Spot", "Spot, doppelte Gebuehren")


def _hat_tageskerzen() -> bool:
    """Die Datenvoraussetzung - und **nur** sie darf ueberspringen (470)."""
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore

    speicher = CandleStore(get_settings().paths.data_store)
    return not speicher.read("BTCUSD_BITSTAMP", Interval("D")).empty


def _lauf(monkeypatch):
    from typer.testing import CliRunner

    from cli import app

    monkeypatch.setenv("TRADING_TROCKENLAUF", "1")
    return CliRunner().invoke(app, ["instrument"])


def _parameter(fn: ast.FunctionDef) -> set[str]:
    a = fn.args
    return {x.arg for x in (*a.posonlyargs, *a.args, *a.kwonlyargs)} | {
        x.arg for x in (a.vararg, a.kwarg) if x
    }


def verschattete_zugriffe(text: str) -> list[str]:
    """Wo greift ein Helfer an seinem eigenen Parameter vorbei?

    Gesucht wird die Bauart von Befund 473: Eine verschachtelte Funktion liest
    einen Namen, der **Parameter der umgebenden Funktion** ist, obwohl sie
    selbst einen Parameter hat, der mit diesem Namen **anfaengt**. Dann ist
    der aeussere mit grosser Wahrscheinlichkeit versehentlich gegriffen - und
    Python sagt dazu nichts, weil der Name ja existiert.

    Dass ein Helfer die Option seines Befehls liest, ist ueblich und richtig
    (``settings``, ``symbole``, ``intervall``). Erst die Verschattung durch
    einen eigenen, laengeren Parameter macht es zum Verdacht.
    """
    baum = ast.parse(text)
    treffer: list[str] = []
    for aussen in ast.walk(baum):
        if not isinstance(aussen, ast.FunctionDef):
            continue
        aussen_p = _parameter(aussen)
        for innen in ast.walk(aussen):
            if innen is aussen or not isinstance(innen, ast.FunctionDef):
                continue
            innen_p = _parameter(innen)
            gelesen = {
                k.id
                for k in ast.walk(innen)
                if isinstance(k, ast.Name) and isinstance(k.ctx, ast.Load)
            }
            for name in sorted(gelesen & aussen_p - innen_p):
                eigene = sorted(
                    p for p in innen_p if p != name and p.startswith(name)
                )
                if eigene:
                    treffer.append(
                        f"{aussen.name}() > {innen.name}(): liest '{name}', "
                        f"hat aber {eigene}"
                    )
    return treffer


class TestDerMelderTaugt:
    """Erst der Melder - in dieser Sitzung haben meine Zaehlungen vierzehn Mal
    zu viel oder das Falsche gemeldet."""

    def test_er_findet_die_alte_fassung(self) -> None:
        """Die Bauart von Befund 473, nachgebaut."""
        alt = """
def instrument(gebuehren: str = ""):
    def messe(name, *, gebuehrenfaktor: int):
        return skaliere(Decimal(gebuehren)) if gebuehrenfaktor != 1 else None
    return messe
"""

        treffer = verschattete_zugriffe(alt)

        assert len(treffer) == 1, treffer
        assert "liest 'gebuehren'" in treffer[0]
        assert "gebuehrenfaktor" in treffer[0]

    def test_er_meldet_die_berichtigte_fassung_nicht(self) -> None:
        neu = """
def instrument(gebuehren: str = ""):
    def messe(name, *, gebuehrenfaktor: int):
        return skaliere(Decimal(gebuehrenfaktor)) if gebuehrenfaktor != 1 else None
    return messe
"""

        assert verschattete_zugriffe(neu) == []

    def test_ein_gewoehnlicher_abschluss_ist_kein_verdacht(self) -> None:
        """Die Gegenprobe, auf die es ankommt: Ein Helfer, der die Option
        seines Befehls liest, ist der Normalfall. Waere das rot, verbote die
        Regel den halben Befehlssatz."""
        gewoehnlich = """
def befehl(symbole: str = "", settings=None):
    def messe(name, *, faktor: int):
        return lauf(symbole, settings, faktor)
    return messe
"""

        assert verschattete_zugriffe(gewoehnlich) == []


class TestKeinHelferGreiftAnSeinemParameterVorbei:
    def test_in_cli_py_gibt_es_keine_solche_stelle(self) -> None:
        """**Die Regel.** Gemessen ohne Ausnahme erfuellbar - vor dem Fix war
        genau eine Stelle hier, naemlich die aus Befund 473."""
        assert verschattete_zugriffe(QUELLE) == []

    def test_der_befehl_rechnet_mit_seinem_eigenen_faktor(self) -> None:
        """Dieselbe Zusicherung noch einmal an der Stelle selbst, damit ein
        Umbau des Melders sie nicht mitnimmt."""
        baum = ast.parse(QUELLE)
        instrument = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "instrument"
        )
        messe = next(
            k
            for k in ast.walk(instrument)
            if isinstance(k, ast.FunctionDef) and k.name == "messe"
        )
        code = ast.unparse(messe)

        assert "Decimal(gebuehrenfaktor)" in code
        assert "Decimal(gebuehren)" not in code


@pytest.mark.daten
class TestDerBefehlLaeuftWirklichDurch:
    """**Die Wache, die den Fehler gefunden haette.** Sie fragt nicht das
    Modul, sondern faehrt den Befehl: sechs Walk-Forward-Laeufe ueber den
    Korb, gemessen **50 Sekunden** je Aufruf, 100 fuer diese Klasse. Das ist
    der Preis dafuer, dass "laeuft" nicht wieder 95 Befunde lang eine
    Vermutung ist.
    """

    def test_exit_null_und_kein_traceback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        if not _hat_tageskerzen():
            pytest.skip("keine Tageskerzen im Speicher")
        ergebnis = _lauf(monkeypatch)

        assert ergebnis.exception is None, ergebnis.output[-2000:]
        assert ergebnis.exit_code == 0, ergebnis.output[-2000:]
        assert "Traceback" not in ergebnis.output

    def test_alle_drei_messlaeufe_stehen_da(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Der dritte ist der, der nie gerechnet hat.

        **Hier stand ein Uebersprung auf 'exit_code != 0'** - und meine eigene
        Wache aus Befund 470 hat ihn gefunden: Bricht der Befehl wieder ab,
        haette dieser Test geschwiegen statt rot zu werden, also genau der
        Fehler, gegen den diese Datei steht. Uebersprungen wird nur, wenn die
        **Daten** fehlen.
        """
        if not _hat_tageskerzen():
            pytest.skip("keine Tageskerzen im Speicher")
        ergebnis = _lauf(monkeypatch)

        for zeile in ZEILEN:
            assert zeile in ergebnis.output, zeile
