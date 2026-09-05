"""Laufen die Schritte, die dem Nutzer gegeben werden, auf denselben Kerzen?

**Befund 214.** Zwei Luecken derselben Art.

Erstens: ``_pruefe_generation`` bewacht seit Befund 64 den Katalogzweig des
Wettbewerbs. ``--von-spitze`` geht am Katalog vorbei - und damit an der
Pruefung. Das Intervall steht dann auf dem der Vorgabegeneration, und die ist
ein Viertelstunden-Katalog. Varianten von 'Trend 50 Tage mit Konfluenz' auf
15-Minuten-Kerzen sind eine andere Regel unter demselben Namen, und jeder
Lauf kostet Versuche.

Zweitens: Befund 213 hat die Ladezeile auf ``-i D`` gestellt, damit sie die
Kerzen holt, auf denen die Gates stehen. Der Schritt danach lief weiter auf
der Vorgabegeneration 8 - Viertelstunden. Die beiden Schritte, die
nacheinander auszufuehren sind, passten also nicht mehr zusammen. Das war
meine eigene Aenderung einen Befund zuvor.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest
import typer
import typer.main

import cli
from core.models import Interval
from research.referenz import SPOTPUNKT
from research.stand import BEIM_NUTZER


def _zerlegt(befehl: str) -> tuple[str, list[str]]:
    teile = shlex.split(befehl)
    assert teile[:3] == ["python", "-m", "cli"], befehl
    return teile[3], teile[4:]


class TestDieSpitzeWirdNichtAufFremdenKerzenGezuechtet:
    def test_ein_fremdes_intervall_bricht_ab(self) -> None:
        """Abgebrochen und nicht gewarnt - wie im Katalogzweig, aus dem
        gleichen Grund: Ein solcher Lauf kostet Versuche."""
        with pytest.raises(typer.Exit):
            cli._pruefe_spitze(Interval.M15)

    def test_das_gemessene_intervall_laeuft_durch(self) -> None:
        cli._pruefe_spitze(Interval(SPOTPUNKT.intervall))

    def test_die_pruefung_haengt_am_referenzpunkt(self) -> None:
        """Nicht an einer hier hingeschriebenen Konstante: Wandert der
        Bestand je auf eine andere Kerzenlaenge, wandert die Pruefung mit."""
        import inspect

        quelle = inspect.getsource(cli._pruefe_spitze)

        assert "SPOTPUNKT.intervall" in quelle
        assert '"D"' not in quelle

    def test_der_zweig_ruft_sie_auch_auf(self) -> None:
        """Die Pruefung zu bauen und nicht aufzurufen waere derselbe Fehler
        noch einmal (Befund 209)."""
        import inspect

        quelle = inspect.getsource(cli.wettbewerb)
        vor_spitze = quelle.split("if von_spitze:")[1].split("else:")[0]

        assert "_pruefe_spitze(interval_obj)" in vor_spitze


class TestDieSchritteFuerDenNutzerPassenZusammen:
    """**Die allgemeine Wache.** Sie haette Befund 213 auffallen lassen."""

    @staticmethod
    def _geladene_intervalle(register=BEIM_NUTZER) -> set[str]:
        """Welche Kerzenlaengen die Ladezeile wirklich holt."""
        for befehl, _ in register:
            name, argumente = _zerlegt(befehl)
            if name != "backfill":
                continue
            codes = [
                argumente[i + 1]
                for i, a in enumerate(argumente)
                if a in ("--intervall", "-i")
            ]
            return set(codes) if codes else {i.value for i in cli.DEFAULT_INTERVALS}
        raise AssertionError("keine backfill-Zeile in BEIM_NUTZER")

    @staticmethod
    def _gebrauchte_intervalle(register=BEIM_NUTZER) -> dict[str, str]:
        """Auf welcher Kerzenlaenge jede Wettbewerbszeile laufen wuerde."""
        aus: dict[str, str] = {}
        for befehl, _ in register:
            name, argumente = _zerlegt(befehl)
            if name != "wettbewerb":
                continue
            ausdruecklich = [
                argumente[i + 1]
                for i, a in enumerate(argumente)
                if a in ("--intervall", "-i")
            ]
            if ausdruecklich:
                aus[befehl] = ausdruecklich[0]
                continue
            generation = next(
                (
                    int(argumente[i + 1])
                    for i, a in enumerate(argumente)
                    if a in ("--generation", "-g")
                ),
                _vorgabe_generation(),
            )
            aus[befehl] = cli._standardintervall(generation)
        return aus

    def test_der_wettbewerb_laeuft_auf_geladenen_kerzen(self) -> None:
        geladen = self._geladene_intervalle()

        for befehl, gebraucht in self._gebrauchte_intervalle().items():
            assert gebraucht in geladen, (
                f"'{befehl}' laeuft auf {gebraucht}-Kerzen, geladen werden "
                f"aber {sorted(geladen)} - der Lauf braeche mit leerem "
                f"Speicher ab."
            )

    def test_es_gibt_ueberhaupt_eine_wettbewerbszeile(self) -> None:
        """Sonst prueft der Test darueber eine leere Menge."""
        assert self._gebrauchte_intervalle()

    def test_die_regel_faende_den_stand_von_befund_213(self) -> None:
        """**Die Gegenprobe.** Genau der Stand, den Befund 213 hinterliess:
        Tageskerzen laden, dann die Vorgabegeneration laufen lassen.

        Eine Wache, die den Fall nicht mehr erzeugen kann, gegen den sie
        gebaut ist, sichert nichts zu (Befund 209).
        """
        damals = (
            ("python -m cli backfill --intervall D --von 2017-08-16", ""),
            ("python -m cli wettbewerb", ""),
        )
        geladen = self._geladene_intervalle(damals)
        gebraucht = self._gebrauchte_intervalle(damals)

        assert geladen == {"D"}
        assert set(gebraucht.values()) == {"15"}
        assert not set(gebraucht.values()) <= geladen


class TestDieAnleitungPasstAuchZusammen:
    """**Befund 215.** Dieselbe Pruefung fuer die README.

    Befund 214 hat das Paar in ``BEIM_NUTZER`` geradegezogen und die README
    nicht angesehen - obwohl dort dieselben zwei Schritte stehen und sie das
    erste sind, was jemand liest. Die Wache gehoert also nicht an ein
    Register, sondern an jede Stelle, die eine Folge von Befehlen vorgibt.
    """

    #: Codeblöcke der README, in denen Laden und Suchen zusammen stehen.
    @staticmethod
    def _bloecke() -> list[list[str]]:
        text = Path("README.md").read_text()
        aus = []
        for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
            zeilen = [
                z.strip()
                for z in block.splitlines()
                if "-m cli" in z and not z.lstrip().startswith("#")
            ]
            if any("backfill" in z for z in zeilen) and any(
                _sucht(z) for z in zeilen
            ):
                aus.append(zeilen)
        return aus

    def test_es_gibt_solche_bloecke(self) -> None:
        """Sonst prueft der Test darunter nichts."""
        assert self._bloecke()

    def test_die_regel_faende_beide_alten_faelle(self) -> None:
        """**Die Gegenprobe** - genau die zwei Stellen, die es gab.

        Oben: Tageskerzen laden, dann ``wettbewerb`` ohne Generation, also
        Vorgabe 8 und damit Viertelstunden. Unten die Windows-Kurzfassung:
        ``backfill`` ohne Intervall, also 1m/15m/1h/4h, dann ``research``,
        das auf Vorgabe 5 und damit auf Tageskerzen laeuft.
        """
        oben_geladen = _geladen_aus("python -m cli backfill --intervall D --von 2017-08-16")
        assert _gebraucht_aus("python -m cli wettbewerb") not in oben_geladen

        unten_geladen = _geladen_aus(r".venv\Scripts\python -m cli backfill")
        assert _gebraucht_aus(r".venv\Scripts\python -m cli research") not in unten_geladen

    def test_die_beiden_suchbefehle_haben_verschiedene_vorgaben(self) -> None:
        """Der Grund, warum eine Wache das nicht raten darf."""
        assert _vorgabe_generation("wettbewerb") != _vorgabe_generation("research")
        assert cli._standardintervall(_vorgabe_generation("research")) == "D"

    def test_laden_und_suchen_treffen_sich(self) -> None:
        for zeilen in self._bloecke():
            geladen = _geladen_aus(next(z for z in zeilen if "backfill" in z))
            for zeile in (z for z in zeilen if _sucht(z)):
                gebraucht = _gebraucht_aus(zeile)

                assert gebraucht in geladen, (
                    f"'{zeile}' laeuft auf {gebraucht}-Kerzen, der Ladebefehl "
                    f"im selben Block holt {sorted(geladen)}."
                )


def _sucht(zeile: str) -> bool:
    """Sucht diese Zeile Strategien - laeuft also auf Kerzen?"""
    return any(f"cli {b}" in zeile for b in ("wettbewerb", "research"))


def _argumente(zeile: str) -> list[str]:
    """Die Argumente hinter dem Befehlsnamen, ohne Kommentar."""
    ohne = zeile.split("#")[0]
    teile = ohne.split("-m cli", 1)[1].split()
    return teile[1:]


def _geladen_aus(zeile: str) -> set[str]:
    args = _argumente(zeile)
    codes = [args[i + 1] for i, a in enumerate(args) if a in ("--intervall", "-i")]
    return set(codes) if codes else {i.value for i in cli.DEFAULT_INTERVALS}


def _gebraucht_aus(zeile: str) -> str:
    args = _argumente(zeile)
    ausdruecklich = [
        args[i + 1] for i, a in enumerate(args) if a in ("--intervall", "-i")
    ]
    if ausdruecklich:
        return ausdruecklich[0]
    befehl = "wettbewerb" if "cli wettbewerb" in zeile else "research"
    generation = next(
        (int(args[i + 1]) for i, a in enumerate(args) if a in ("--generation", "-g")),
        _vorgabe_generation(befehl),
    )
    return cli._standardintervall(generation)


def _vorgabe_generation(befehl: str = "wettbewerb") -> int:
    """Die Vorgabe von ``--generation``, aus dem Befehl gelesen.

    Sie ist **nicht** fuer alle gleich: ``wettbewerb`` steht auf 8 (15
    Minuten), ``research`` auf 5 (Tageskerzen).
    """
    kommando = typer.main.get_command(cli.app).commands[befehl]
    for p in kommando.params:
        if "--generation" in getattr(p, "opts", []):
            return int(p.default)
    raise AssertionError("--generation nicht gefunden")


def test_die_vorgabegeneration_ist_wirklich_viertelstunden() -> None:
    """Der Ausgangspunkt des Befunds - gemessen, nicht behauptet."""
    assert cli._standardintervall(_vorgabe_generation()) == "15"
    assert re.fullmatch(r"\d+", cli._standardintervall(_vorgabe_generation()))
