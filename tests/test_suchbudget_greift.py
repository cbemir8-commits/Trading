"""Das Abbruchkriterium aus dem Plan - greift es, oder steht es nur da?

**Befund 216.** Der Docstring von ``Suchbudget`` sagt seit seiner Anlage:
*"Das Abbruchkriterium aus dem Plan - endlich im System statt nur im Text."*

Es stand nur im Text. ``BUDGET`` kam in ``cli rennen`` und ``cli suchbudget``
vor - beides Befehle, die **berichten**. ``cli wettbewerb``, der einzige, der
Versuche in einer Schleife ausgibt, hat es nie gelesen, und ``--runden`` steht
auf 0, also "bis Strg-C". Der Bericht verspricht "Abbruch bei 230";
abgebrochen hat nichts.

Ein Versuch laesst sich nicht zuruecknehmen: Jeder hebt die Huerde des
Deflated Sharpe um 0,00021 fuer alle kuenftigen, dauerhaft.
"""

from __future__ import annotations

import inspect

import pytest
import typer
import typer.main

import cli
from research.stand import BUDGET


class TestDieGrenzeBrichtAb:
    def test_unter_der_grenze_laeuft_es_weiter(self) -> None:
        assert not cli._budget_erschoepft(BUDGET.grenze - 1, ueber_budget=False)

    def test_auf_der_grenze_bricht_es_ab(self) -> None:
        assert cli._budget_erschoepft(BUDGET.grenze, ueber_budget=False)

    def test_darueber_bleibt_es_dabei(self) -> None:
        assert cli._budget_erschoepft(BUDGET.grenze + 50, ueber_budget=False)

    def test_die_grenze_ist_nicht_hier_hingeschrieben(self) -> None:
        """Sie kommt aus ``BUDGET``. Sonst haette das System zwei Grenzen,
        und die im Bericht waere die falsche.

        Geprueft wird der **Rumpf** ohne Docstring: Die Zahl dort zu nennen,
        wo erklaert wird, was im Bericht steht, ist Erinnerung; sie in die
        Logik zu schreiben waere die zweite Grenze. Derselbe Unterschied wie
        bei der Gatezahl-Wache aus Befund 210.
        """
        quelle = inspect.getsource(cli._budget_erschoepft)
        rumpf = quelle.replace(cli._budget_erschoepft.__doc__ or "", "")

        assert "BUDGET.erschoepft" in rumpf
        assert "230" not in rumpf

    def test_die_gegenprobe_zur_rumpfpruefung(self) -> None:
        """Ohne sie prueft der Test darueber vielleicht einen leeren Rumpf."""
        quelle = inspect.getsource(cli._budget_erschoepft)
        rumpf = quelle.replace(cli._budget_erschoepft.__doc__ or "", "")

        assert "230" in quelle, "die Zahl steht im Docstring - sonst zeigt der Test nichts"
        assert len(rumpf.splitlines()) > 10


class TestWeitersuchenBleibtMoeglich:
    """Der Plan ist eine Abmachung des Nutzers, keine Naturkonstante.

    Was nicht bleiben durfte, ist das **unbemerkte** Weiterlaufen.
    """

    def test_mit_dem_flag_laeuft_es_weiter(self) -> None:
        assert not cli._budget_erschoepft(BUDGET.grenze + 1, ueber_budget=True)

    def test_es_sagt_dabei_was_es_kostet(self, capsys: pytest.CaptureFixture) -> None:
        cli._budget_erschoepft(BUDGET.grenze + 1, ueber_budget=True)
        text = capsys.readouterr().out

        assert "0,00021" in text
        assert "aufgebraucht" in text

    def test_der_abbruch_nennt_den_weg_darum_herum(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Eine Schranke, die ihren eigenen Schalter verschweigt, ist keine
        Abmachung, sondern eine Sperre."""
        cli._budget_erschoepft(BUDGET.grenze, ueber_budget=False)
        text = capsys.readouterr().out

        assert "--ueber-das-budget" in text

    def test_das_flag_gibt_es_am_befehl(self) -> None:
        kommando = typer.main.get_command(cli.app).commands["wettbewerb"]
        opts = {o for p in kommando.params for o in getattr(p, "opts", [])}

        assert "--ueber-das-budget" in opts

    def test_ohne_flag_ist_die_vorgabe_abbrechen(self) -> None:
        """Die Vorgabe muss die Abmachung sein, nicht ihre Ausnahme."""
        kommando = typer.main.get_command(cli.app).commands["wettbewerb"]
        p = next(
            p for p in kommando.params if "--ueber-das-budget" in getattr(p, "opts", [])
        )

        assert p.default is False


class TestDieSchleifeFragtAuchWirklich:
    """Die Wache zu bauen und nicht aufzurufen waere Befund 209 noch einmal."""

    def test_der_wettbewerb_prueft_vor_jeder_runde(self) -> None:
        quelle = inspect.getsource(cli.wettbewerb)

        assert "_budget_erschoepft(trials_before" in quelle

    def test_geprueft_wird_vor_dem_hochzaehlen(self) -> None:
        """Sonst begaenne die Runde, die abgebrochen werden soll - und eine
        begonnene Runde gibt ihre Versuche aus."""
        quelle = inspect.getsource(cli.wettbewerb)
        schleife = quelle.split("while runden == 0")[1]
        vor_pruefung = schleife.split("_budget_erschoepft")[0]

        assert "runde += 1" not in vor_pruefung

    def test_es_wird_abgebrochen_und_nicht_nur_gewarnt(self) -> None:
        quelle = inspect.getsource(cli.wettbewerb)
        nach = quelle.split("_budget_erschoepft(trials_before")[1][:200]

        assert "break" in nach


def test_die_zeile_im_bericht_verspricht_einen_abbruch() -> None:
    """Der Satz, der die Deckung brauchte - und sie jetzt hat."""
    assert "Abbruch bei" in BUDGET.zeile(BUDGET.grenze - 1)
