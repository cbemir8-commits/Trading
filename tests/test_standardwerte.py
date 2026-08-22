"""Ein Befehl, der mit seinen eigenen Voreinstellungen abbricht.

``cli wettbewerb`` stand auf Generation 8 und Intervall 15. Generation 8 ist
der Tageskerzen-Katalog, und ``_pruefe_generation`` lehnt die Paarung
ausdruecklich ab:

    *"Generation 8 ist fuer D-Kerzen gedacht, nicht fuer 15m. Dieselben
    Periodenzahlen bedeuten hier andere Zeitraeume - das waere eine andere
    Regel unter demselben Namen, und sie wuerde Versuche kosten."*

Der Befehl, den der Auftrag dem Nutzer seit Wochen nennt, brach also mit
Exit 2 ab, sobald man ihn ohne Argumente aufrief. Dieselbe Zuordnung stand an
zwei Stellen - in ``VORGESEHEN`` und im Standardwert -, und beim Umstellen des
Katalogs wurde die zweite vergessen.

Zwei Tests tragen diese Datei:

``test_kein_befehl_widerspricht_sich_selbst`` - Der Kern. Er geht **alle**
Befehle durch, statt die zwei bekannten zu reparieren. Ein Test, der nur die
gefundenen Faelle prueft, findet den dritten nicht.

``test_das_intervall_kommt_aus_der_generation`` - Die Ursache. Der Standard
liest die Zuordnung, statt sie zu wiederholen.
"""

from __future__ import annotations

import click
import pytest
import typer

from cli import app
from research.seeds import VORGESEHEN, passt_zum_intervall


def standardwerte(befehl) -> dict:
    """Die Voreinstellungen eines Typer-Befehls als einfaches Wortverzeichnis."""
    import inspect

    aus = {}
    for name, parameter in inspect.signature(befehl.callback).parameters.items():
        vorgabe = parameter.default
        if isinstance(vorgabe, typer.models.OptionInfo | typer.models.ArgumentInfo):
            aus[name] = vorgabe.default
        elif vorgabe is not inspect.Parameter.empty:
            aus[name] = vorgabe
    return aus


def paare() -> list[tuple[str, int, str]]:
    """Befehle, die **beides** haben: eine Generation und ein Intervall."""
    gefunden = []
    for befehl in app.registered_commands:
        werte = standardwerte(befehl)
        generation, intervall = werte.get("generation"), werte.get("intervall")
        if isinstance(generation, int) and isinstance(intervall, str):
            name = befehl.name or befehl.callback.__name__
            gefunden.append((name, generation, intervall))
    return gefunden


class TestVoreinstellungen:
    def test_es_gibt_ueberhaupt_solche_befehle(self) -> None:
        """Ohne diese Pruefung koennte der Test gruen sein, weil er nichts
        findet - die unangenehmste Art, gruen zu sein."""
        assert len(paare()) >= 2, [n for n, _, _ in paare()]

    def test_kein_befehl_widerspricht_sich_selbst(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Ein leeres Intervall heisst "aus der Generation" und ist damit immer
        stimmig. Steht dort ein fester Wert, muss er zur Generation passen -
        sonst bricht der Befehl mit seinen eigenen Voreinstellungen ab.
        """
        widersprueche = [
            (name, generation, intervall)
            for name, generation, intervall in paare()
            if intervall and not passt_zum_intervall(generation, intervall)
        ]

        assert not widersprueche, (
            "Diese Befehle brechen mit ihren eigenen Voreinstellungen ab: "
            f"{widersprueche}"
        )

    def test_die_beiden_bekannten_faelle_sind_behoben(self) -> None:
        """``wettbewerb`` (Generation 8, Intervall 15) und ``research``
        (Generation 5, Intervall 60) waren die gefundenen."""
        nach_namen = {name: (g, i) for name, g, i in paare()}

        assert nach_namen["wettbewerb"][1] == "", "leer = aus der Generation"
        assert nach_namen["research"][1] == ""


class TestHerleitung:
    def test_das_intervall_kommt_aus_der_generation(self) -> None:
        """**Die Ursache, nicht das Symptom.**

        ``VORGESEHEN`` ist die Zuordnung, seit Befund 64 als Daten. Ein
        zweiter Standardwert daneben ist die Stelle, an der beides
        auseinanderlaeuft.
        """
        from cli import _standardintervall

        assert _standardintervall(5) == "D"
        assert _standardintervall(8) == "D"
        assert _standardintervall(6) == "15"
        assert _standardintervall(7) == "15"

    def test_generationen_ohne_vorgabe_bekommen_tageskerzen(self) -> None:
        """1 bis 4 haben keine Vorgabe. Tageskerzen, weil dort der Kandidat
        steht und dort die Kataloge liegen, die eine Vorgabe haben."""
        from cli import _standardintervall

        for generation in (1, 2, 3, 4):
            assert VORGESEHEN[generation] is None
            assert _standardintervall(generation) == "D"

    def test_eine_unbekannte_generation_kippt_nicht(self) -> None:
        from cli import _standardintervall

        assert _standardintervall(99) == "D"

    def test_das_ergebnis_besteht_die_eigene_pruefung(self) -> None:
        """Der Kreis schliesst sich: Was ``_standardintervall`` liefert, muss
        ``_pruefe_generation`` durchlassen."""
        from cli import _pruefe_generation, _standardintervall
        from core.models import Interval

        for generation in sorted(VORGESEHEN):
            _pruefe_generation(
                generation, Interval(_standardintervall(generation))
            )

    def test_ein_ausdruecklicher_widerspruch_wird_weiter_abgelehnt(self) -> None:
        """Der Standard ist jetzt stimmig - die Wache bleibt trotzdem, fuer
        den Fall, dass jemand die Paarung von Hand setzt."""
        from cli import _pruefe_generation
        from core.models import Interval

        with pytest.raises((typer.Exit, click.exceptions.Exit)):
            _pruefe_generation(8, Interval("15"))
