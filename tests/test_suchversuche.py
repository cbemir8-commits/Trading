"""Die Suche verzeichnet ihre Versuche jetzt auch - Befund 377.

Die offene Frage aus Befund 234/282 liess drei Befehle aus: ``adaptiv``,
``research`` und ``wettbewerb`` buchten weiter stumm in den Grundstock, mit
dieser Begruendung:

    Suchlaeufe und keine Sweeps am Bestand, bei ihnen war nie strittig, ob sie
    zaehlen

Das beantwortet die Frage *"zaehlt es?"*. Die Frage, an der das haerteste Gate
haengt, ist eine andere. ``research/versuche.py`` sagt sie selbst:

    Befund 68 hat gezeigt, dass die Streuung der Sharpe-Schaetzer ueber die
    Versuche - die einzige geratene Eingabe des Gates - nur deshalb nicht
    messbar ist, weil niemand aufgeschrieben hat, was er probiert hat.

Und damit war es genau verkehrt herum. Verzeichnet waren ``landschaft`` und
``machbarkeit`` - Reglerscans **um den Bestand herum**, die
``research/streuung.py`` ausdruecklich als zu eng verwirft:

    Berichte schreibt man ueber Reglerscans, und ein Reglerscan variiert einen
    Knopf um den Bestand herum. Solche Punkte liegen naturgemaess eng
    beieinander [...] **Die Verlierer fehlen.**

Nicht verzeichnet war die **Suche**, die die Verlierer sieht. Von 192 Versuchen
im Grundstock stand keiner mit seiner Guete da.

Was sich damit nicht aendert
----------------------------
Die Streuung wird **nicht** rueckwirkend messbar. Die 192 bleiben ohne
Herkunft; sie nachtraeglich zu benennen waere eine Umbuchung. Und
``streuung.MINDESTABDECKUNG`` verlangt 90 % - das braucht viele Laeufe.
Dieser Befund macht den Weg offen, er geht ihn nicht.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from core.models import Side, Trade
from research.versuche import anhaengen, laden

T0 = datetime(2026, 1, 1, tzinfo=UTC)

#: Die drei Befehle, die Befund 234 offen liess.
SUCHLAEUFE = ("adaptiv", "research", "wettbewerb")


def _trade(pnl: str, index: int) -> Trade:
    return Trade(
        trade_id=f"t{index}",
        symbol="BTCUSDT",
        side=Side.BUY,
        strategy_id="test",
        entry_time=T0 + timedelta(hours=index),
        entry_price=Decimal("100000"),
        exit_time=T0 + timedelta(hours=index + 4),
        exit_price=Decimal("100000"),
        qty=Decimal("0.006"),
        gross_pnl=Decimal(pnl),
        fees=Decimal("0.24"),
        stop_loss=Decimal("99400"),
    )


class _Bericht:
    """Das Einzige, was ``_versuch`` von einem Bericht braucht."""

    def __init__(self, pnls: list[str]) -> None:
        self.all_trades = [_trade(p, i) for i, p in enumerate(pnls)]


def _quelle(name: str) -> str:
    import cli

    return inspect.getsource(getattr(cli, name))


class TestJederSuchlaufVerzeichnetSeineVersuche:
    """Strukturell geprueft, weil ein echter Lauf Boersenkerzen braucht.

    Nicht ueber die Zeilennummer, sondern ueber den Syntaxbaum des **einzelnen
    Befehls** - genau die Vorsicht aus Befund 362, wo ``inspect.getsource``
    nach einer Bearbeitung die Nachbarfunktion geprueft hat.
    """

    @pytest.mark.parametrize("befehl", SUCHLAEUFE)
    def test_er_ruft_verzeichne(self, befehl: str) -> None:
        assert "_verzeichne(" in _quelle(befehl)

    # Dass **keiner** mehr die reine Summe schreibt, steht in
    # 'test_zaehlerwettlauf.py' - dort gehoert es hin (die Wettlauf-Frage) und
    # dort ist es in 'BEGRUENDET' angemeldet. Hier stand dieselbe Zusicherung
    # ein zweites Mal und entging der Wache aus Befund 242 nur, weil die
    # Zeichenkette eine Klammer trug ('save_trials(' statt 'save_trials').

    @pytest.mark.parametrize("befehl", ("research", "wettbewerb"))
    def test_die_schleifen_verzeichnen_jeden_kandidaten(self, befehl: str) -> None:
        """Nicht nur den Champion - die Verlierer sind der Zweck.

        Sie tragen die Streuung, die dem Gate fehlt; nur die Gewinner zu
        verzeichnen waere dieselbe Auswahl, an der Befund 68 gescheitert ist.
        """
        quelle = _quelle(befehl)
        assert "report.candidates" in quelle
        assert "report.admitted" not in quelle.split("_verzeichne(")[0][-400:]

    @pytest.mark.parametrize("befehl", ("research", "wettbewerb"))
    def test_sie_geben_den_walkforward_bericht_weiter(self, befehl: str) -> None:
        """``_versuch`` holt die Guete aus ``report.all_trades``; ein Candidate
        selbst hat das Feld nicht."""
        assert "k.walkforward" in _quelle(befehl)

    def test_jeder_nennt_eine_herkunft(self) -> None:
        for befehl in SUCHLAEUFE:
            baum = ast.parse(_quelle(befehl).lstrip())
            herkunft = [
                kw
                for knoten in ast.walk(baum)
                if isinstance(knoten, ast.Call)
                for kw in knoten.keywords
                if kw.arg == "herkunft"
            ]
            assert herkunft, f"{befehl} verzeichnet ohne Herkunft"


class TestWasImNachweisSteht:
    """Der Inhalt, nicht die Aufrufstelle."""

    def test_die_guete_je_trade_steht_drin(self) -> None:
        from cli import _versuch

        versuch = _versuch("Testregel", _Bericht(["5", "-3", "8", "-2", "4", "6"]),
                           herkunft="cli wettbewerb Runde 1")

        assert versuch.sharpe_je_trade is not None
        assert versuch.trades == 6
        assert versuch.herkunft == "cli wettbewerb Runde 1"
        assert versuch.kennung == "Testregel"

    def test_und_die_form_dazu(self) -> None:
        """Schiefe und Woelbung gehen mit - Befund 342, sonst ist die Latte
        dieses Versuchs spaeter nicht mehr zu rechnen."""
        from cli import _versuch

        versuch = _versuch("Testregel", _Bericht(["5", "-3", "8", "-2", "4", "40"]),
                           herkunft="cli research")

        assert versuch.schiefe is not None
        assert versuch.woelbung is not None

    def test_ein_verlierer_wird_genauso_verzeichnet(self) -> None:
        """Mit negativer Guete, und sie bleibt drin.

        ``streuung`` nimmt einen negativen Sharpe ausdruecklich mit - er ist
        erhoben. Nur die Null heisst dort 'nicht erhoben' (Befund 372).
        """
        from cli import _versuch

        versuch = _versuch("Verlierer", _Bericht(["-5", "-3", "-8", "2", "-4", "-6"]),
                           herkunft="cli wettbewerb Runde 2")

        assert versuch.sharpe_je_trade is not None
        assert versuch.sharpe_je_trade < 0

    def test_eine_zu_duenne_reihe_meldet_nichts_statt_null(self) -> None:
        """``Kandidat.aus_trades`` gibt unter fuenf Trades ``None`` - und
        ``None`` muss ``None`` bleiben. Eine Null waere dort eine Messung."""
        from cli import _versuch

        versuch = _versuch("Zuduenn", _Bericht(["5", "-3"]), herkunft="cli adaptiv")

        assert versuch.trades == 2
        assert versuch.sharpe_je_trade is None
        assert versuch.schiefe is None


class TestDerGrundstockWaechstNichtMehrMit:
    """Die Messung aus Befund 234, jetzt mit dem anderen Ergebnis."""

    def test_verzeichnete_versuche_lassen_den_grundstock_stehen(
        self, tmp_path: Path
    ) -> None:
        from cli import _versuch

        pfad = tmp_path / "trials.json"
        anhaengen(pfad, [])  # leeres Verzeichnis anlegen
        vorher = laden(pfad)

        neue = [
            _versuch(f"Kandidat {i}", _Bericht(["5", "-3", "8", "-2", "4", "6"]),
                     herkunft="cli wettbewerb Runde 1")
            for i in range(5)
        ]
        nachher = anhaengen(pfad, neue)

        assert nachher.grundstock == vorher.grundstock
        assert len(nachher.eintraege) == len(vorher.eintraege) + 5
        assert nachher.anzahl == vorher.anzahl + 5

    def test_und_jeder_traegt_seine_guete(self, tmp_path: Path) -> None:
        """Der ganze Zweck: Fuenf Versuche, fuenf Guetewerte.

        Vor diesem Befund waren es fuenf im Grundstock und null Guetewerte -
        gemessen in Befund 234 ('5 gemeldet, Grundstock +5, Einzelnachweise
        +0').
        """
        from cli import _versuch

        pfad = tmp_path / "trials.json"
        neue = [
            _versuch(f"Kandidat {i}", _Bericht(["5", "-3", "8", "-2", "4", "6"]),
                     herkunft="cli research")
            for i in range(5)
        ]
        verzeichnis = anhaengen(pfad, neue)

        mit_guete = [e for e in verzeichnis.eintraege if e.sharpe_je_trade is not None]
        assert len(mit_guete) == 5


class TestDieStreuungSiehtSieJetzt:
    """Der Anschluss, um den es geht - ohne zu behaupten, er sei fertig."""

    def test_aus_verzeichnis_liest_die_neuen_punkte(self, tmp_path: Path) -> None:
        from cli import _versuch
        from research.streuung import aus_verzeichnis

        pfad = tmp_path / "trials.json"
        anhaengen(
            pfad,
            [
                _versuch(f"Kandidat {i}", _Bericht(["5", "-3", "8", "-2", "4", "6"]),
                         herkunft="cli wettbewerb Runde 1")
                for i in range(7)
            ],
        )

        punkte = aus_verzeichnis(pfad)

        assert len(punkte) == 7
        assert all(p.sharpe_je_trade is not None for p in punkte)

    def test_aber_die_abdeckung_bleibt_eine_huerde(self) -> None:
        """Keine Zahl schoenreden: Der Grundstock bleibt ohne Herkunft, und
        90 % Abdeckung braucht viele Laeufe. Dieser Befund macht den Weg
        offen, er geht ihn nicht."""
        from research.streuung import MINDESTABDECKUNG

        assert MINDESTABDECKUNG == 0.9
