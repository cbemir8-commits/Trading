"""Steht im Bericht, auf welchem Betriebspunkt gemessen wurde?

**Befund 228.** Die Berichte fuehren zwei der drei Dimensionen eines
Betriebspunkts: ``intervall`` seit Befund 190, ``versuche`` seit jeher. Das
**Instrument** stand in keinem.

Aufgefallen ist es an ``reports/marktkombinationen``: Dort steht fuer BTC+ETH
"7 von 11" bei einem Deflated Sharpe von 0,7641 - das ist auf drei Stellen
der Perpetual-Punkt aus Befund 54, den Befund 108 verlassen hat. ``cli stand``
sagt 9 von 11 bei 0,5881. Nichts im Bericht sagte, warum.

Der Unterschied zwischen den Punkten sind genau zwei Dinge: ein Hebel ueber
1,0 und ein Funding ueber null. Beide lassen sich ablesen, statt sie
hinzuschreiben.
"""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from pathlib import Path

import cli
from research.referenz import SPOTPUNKT, UEBERHOLT
from research.seeds import spitzenkandidat


class _Konfiguration:
    """Nur so viel, wie ``_betriebspunkt`` liest."""

    def __init__(self, satz: Decimal | None) -> None:
        self.funding = type("F", (), {"default_rate": satz})()


class TestDerPunktWirdAbgelesen:
    def test_spot_heisst_kein_hebel_und_kein_funding(self) -> None:
        punkt = cli._betriebspunkt(
            cli._ohne_hebel(spitzenkandidat()), {"BTC": _Konfiguration(Decimal("0"))}
        )

        assert punkt.startswith("Spot")

    def test_hebel_allein_macht_ihn_zum_perpetual(self) -> None:
        punkt = cli._betriebspunkt(
            spitzenkandidat(), {"BTC": _Konfiguration(Decimal("0"))}
        )

        assert punkt.startswith("Perpetual")
        assert "Hebel 3" in punkt

    def test_funding_allein_ebenfalls(self) -> None:
        punkt = cli._betriebspunkt(
            cli._ohne_hebel(spitzenkandidat()),
            {"BTC": _Konfiguration(Decimal("0.0001"))},
        )

        assert punkt.startswith("Perpetual")
        assert "mit Funding" in punkt

    def test_ein_genom_ohne_groessensteuerung_bricht_nicht(self) -> None:
        class Ohne:
            sizing = None

        assert cli._betriebspunkt(Ohne(), {"BTC": _Konfiguration(Decimal("0"))})

    def test_die_zahl_kommt_aus_dem_genom(self) -> None:
        """Nicht aus einer Konstante - sonst waere es dieselbe gepflegte Zahl
        wie die, vor der dieser Befund warnt."""
        quelle = inspect.getsource(cli._betriebspunkt)

        assert "sizing" in quelle
        assert "default_rate" in quelle
        assert "3.0" not in quelle


class TestMarktkombinationenTraegtIhn:
    @staticmethod
    def _quelle() -> str:
        baum = ast.parse(Path("cli.py").read_text())
        fn = next(
            n for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "marktkombinationen"
        )
        return ast.unparse(fn)

    def test_der_bericht_fuehrt_den_betriebspunkt(self) -> None:
        assert "'betriebspunkt': punkt" in self._quelle()

    def test_er_wird_auch_angezeigt(self) -> None:
        """Ein Vermerk, den nur die Datei traegt, liest niemand, der am
        Bildschirm sitzt."""
        quelle = self._quelle()
        i = quelle.index("_betriebspunkt(genome, configs)")

        assert "console.print" in quelle[i : i + 400]

    def test_der_hinweis_ordnet_ihn_ein(self) -> None:
        """Nicht nur "Perpetual", sondern wozu das im Verhaeltnis steht:
        derselbe Erstpunkt wie bei ``cli stand``, und der Spot-Punkt ist der,
        auf den sich die Lattenrechnungen beziehen (Befund 229)."""
        quelle = self._quelle()

        assert "Erstpunkt" in quelle
        assert "Spot-Punkt" in quelle


class TestDerBefundSelbst:
    """Die Zahlen, auf denen er steht - aus dem Register, nicht behauptet."""

    def test_der_perpetual_punkt_traegt_sieben_von_elf(self) -> None:
        perp = next(p for p in UEBERHOLT if p.name.startswith("Perpetual"))

        assert (perp.bestanden, perp.gesamt) == (7, 11)
        assert round(perp.dsr, 4) == 0.7641

    def test_der_heutige_punkt_traegt_neun_von_elf(self) -> None:
        assert (SPOTPUNKT.bestanden, SPOTPUNKT.gesamt) == (9, 11)
        assert round(SPOTPUNKT.dsr, 4) == 0.5881

    def test_die_beiden_unterscheiden_sich_deutlich(self) -> None:
        """Der Unterschied ist kein Rundungsrest - er ist der Grund, warum
        der Vermerk noetig ist."""
        perp = next(p for p in UEBERHOLT if p.name.startswith("Perpetual"))

        assert perp.dsr - SPOTPUNKT.dsr > 0.15
        assert perp.bestanden != SPOTPUNKT.bestanden


class TestWelcherPunktWoGilt:
    """**Befund 229.** Berichtigung von 228: Anzeige und Analysebezug sind
    verschiedene Punkte, und beide sind gepflegt.

    ``cli stand`` rechnet **primaer** auf Perpetual und zeigt den Spot-Punkt
    als ``zweitpunkt`` daneben ("Ohne Funding steht er bei ... statt ..."),
    seit Befund 108. Die Latten- und Lueckenrechnungen dieses Projekts
    beziehen sich dagegen auf ``SPOTPUNKT``.

    Befund 228 hat aus ``SPOTPUNKT`` abgelesen, ``cli stand`` sage 9 von 11,
    und daraus einen Widerspruch zum Marktkombinationsbericht gemacht. Es
    war keiner: Dessen 7 von 11 sind der Erstpunkt.
    """

    def test_stand_rechnet_primaer_ohne_die_spot_helfer(self) -> None:
        """Der Erstlauf nimmt das rohe Genom und die Vorgabekonfiguration."""
        baum = ast.parse(Path("cli.py").read_text())
        fn = next(
            n for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "stand"
        )
        quelle = ast.unparse(fn)

        assert "_spotpunkt(" in quelle, "der zweite Punkt wird gerechnet"
        i = quelle.index("_spotpunkt(")
        assert "_ohne_hebel" not in quelle[:i], "der erste Lauf ist der Perpetual"

    def test_der_zweite_punkt_wird_gemessen_und_nicht_nachgeschlagen(self) -> None:
        """Sonst waere es eine zweite Kopie neben dem Lauf - der Fehler aus
        den Befunden 101, 103 und 109."""
        quelle = inspect.getsource(cli._spotpunkt)

        assert "run_portfolio_walkforward" in quelle
        assert "0.8640" not in quelle and "0,8640" not in quelle

    def test_der_bericht_stellt_beide_nebeneinander(self) -> None:
        from research.stand import Lage

        def _lage(zweitpunkt):
            return Lage(
                kandidat="Trend 50 Tage mit Konfluenz",
                maerkte="BTC + ETH, Tageskerzen",
                trades=152, sharpe_je_trade=0.2597, noetiger_sharpe=0.2987,
                bestanden=7, gesamt=11, offen=("Messlatte", "Deflated Sharpe"),
                versuche=198, cagr_pct=13.47, rueckgang_pct=10.64,
                zweitpunkt=zweitpunkt,
            )

        assert "DIE BEIDEN BETRIEBSPUNKTE" in _lage(None).bericht()

    def test_die_beiden_punkte_sind_beide_gepflegt(self) -> None:
        """Der Perpetual-Punkt ist nicht verlassen, sondern der Erstpunkt -
        ``UEBERHOLT`` nennt ihn 'vor Befund 108', weil 108 den **Bezug** auf
        Spot gestellt hat, nicht die Anzeige."""
        perp = next(p for p in UEBERHOLT if p.name.startswith("Perpetual"))

        assert perp.bestanden == 7
        assert SPOTPUNKT.bestanden == 9
        assert perp.trades == SPOTPUNKT.trades - 4
