"""Die Befehle fuer den Nutzer, gegen die echte Kommandozeile - Befund 307.

``BEIM_NUTZER`` ist die einzige Stelle, an der dieses Projekt jemanden bittet,
etwas auf seinem eigenen Rechner zu tun. Was dort steht, wird kopiert und
eingefuegt - und zweimal ist genau daran etwas schiefgegangen:

    Befund 167   ', dann wettbewerb' stand als Prosa hinter dem Backfill.
                 Wer die Zeile kopierte, bekam
                 'Got unexpected extra argument(s)'.
    Befund 214   'cli wettbewerb' ohne '--generation' nimmt die Vorgabe 8,
                 einen Viertelstunden-Katalog. Nach einem Tages-Backfill
                 braeche der Lauf mit leerem Speicher ab.

Beide Male war der Text richtig gemeint und falsch benutzbar. Diese Tests
fahren die Zeilen nicht aus - sie **parsen** sie gegen die echte
Befehlsstruktur, was ohne Boerse, Schluessel und Daten geht.
"""

from __future__ import annotations

import shlex

import click
import pytest
import typer

from cli import app
from research.seeds import VORGESEHEN
from research.stand import BEIM_NUTZER


def _zerlegt(befehl: str) -> tuple[str, list[str]]:
    teile = shlex.split(befehl)
    return teile[3], teile[4:]


@pytest.fixture(scope="module")
def gruppe() -> click.Group:
    return typer.main.get_command(app)


class TestJedeZeileIstEineBefehlszeile:
    @pytest.mark.parametrize("befehl", [b for b, _ in BEIM_NUTZER])
    def test_sie_beginnt_mit_dem_aufruf(self, befehl: str) -> None:
        """**Befund 167.** Eine Zeile, die nicht so anfaengt, ist Prosa - und
        Prosa wird trotzdem kopiert."""
        assert shlex.split(befehl)[:3] == ["python", "-m", "cli"], befehl

    @pytest.mark.parametrize("befehl", [b for b, _ in BEIM_NUTZER])
    def test_den_befehl_gibt_es(self, befehl: str, gruppe: click.Group) -> None:
        name, _ = _zerlegt(befehl)
        assert gruppe.get_command(click.Context(gruppe), name) is not None, name

    @pytest.mark.parametrize("befehl", [b for b, _ in BEIM_NUTZER])
    def test_die_argumente_lassen_sich_lesen(
        self, befehl: str, gruppe: click.Group
    ) -> None:
        """**Der eigentliche Test.** Unbekannte Optionen, fehlende Werte und
        Werte vom falschen Typ fallen hier auf - ohne Boerse, ohne
        Schluessel, ohne Daten.
        """
        name, argumente = _zerlegt(befehl)
        oben = click.Context(gruppe)
        cmd = gruppe.get_command(oben, name)
        unten = click.Context(cmd, info_name=name, parent=oben)

        cmd.parse_args(unten, list(argumente))

    def test_keine_zeile_steht_zweimal_da(self) -> None:
        zeilen = [b for b, _ in BEIM_NUTZER]
        assert len(zeilen) == len(set(zeilen))

    def test_jede_zeile_sagt_auch_warum(self) -> None:
        for befehl, warum in BEIM_NUTZER:
            assert warum.strip(), befehl


class TestDieZeilenPassenZueinander:
    """Parsen allein haette Befund 214 nicht gefunden: Dort war jede Option
    gueltig, nur zog der Befehl seine Vorgabe aus einer anderen Kerzenlaenge
    als der Backfill darueber.
    """

    def _wert(self, argumente: list[str], name: str) -> str | None:
        return (
            argumente[argumente.index(name) + 1]
            if name in argumente and argumente.index(name) + 1 < len(argumente)
            else None
        )

    def test_der_backfill_laedt_tageskerzen(self) -> None:
        """**Befund 213**: Alle elf Gates stehen auf Tageskerzen. Ein
        Backfill auf 15 Minuten laedt Forschungsmaterial und keine
        Zulassungsgrundlage - der 15-Minuten-Vorrat ist gemessen (297:
        1 von 36 Regeln mit positiver Guete).
        """
        zeilen = [b for b, _ in BEIM_NUTZER if " backfill " in f" {b} "]
        assert zeilen, "kein Backfill unter den Befehlen"
        for zeile in zeilen:
            _, argumente = _zerlegt(zeile)
            assert self._wert(argumente, "--intervall") == "D", zeile

    def test_der_wettbewerb_nennt_seine_generation(self) -> None:
        """**Befund 214**: Ohne '--generation' gilt die Vorgabe, und die ist
        ein Viertelstunden-Katalog."""
        zeilen = [b for b, _ in BEIM_NUTZER if " wettbewerb " in f" {b} "]
        assert zeilen, "kein Wettbewerb unter den Befehlen"
        for zeile in zeilen:
            _, argumente = _zerlegt(zeile)
            assert self._wert(argumente, "--generation") is not None, zeile

    def test_und_zwar_eine_zu_den_geladenen_kerzen(self) -> None:
        """Der Kern von Befund 214, als Rechnung: Die genannte Generation
        muss zu der Kerzenlaenge gehoeren, die der Backfill daneben laedt.

        Beides steht in ``BEIM_NUTZER`` nebeneinander, und keiner der beiden
        Texte kann den anderen pruefen - dieser Test kann es.
        """
        backfills = {
            self._wert(_zerlegt(b)[1], "--intervall")
            for b, _ in BEIM_NUTZER
            if " backfill " in f" {b} "
        }
        assert len(backfills) == 1, f"mehrere Kerzenlaengen geladen: {backfills}"
        geladen = backfills.pop()

        for zeile in [b for b, _ in BEIM_NUTZER if " wettbewerb " in f" {b} "]:
            gen = int(self._wert(_zerlegt(zeile)[1], "--generation"))
            vorgesehen = VORGESEHEN.get(gen)
            assert vorgesehen in (None, geladen), (
                f"{zeile}: Generation {gen} gehoert auf {vorgesehen}, "
                f"geladen wird {geladen}"
            )
