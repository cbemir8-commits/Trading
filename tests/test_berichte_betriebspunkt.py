"""Jeder Bericht nennt seinen Betriebspunkt.

**Befund 242.** Befund 228 hat gefunden, dass Berichte zwei der drei
Dimensionen fuehren: ``intervall`` seit Befund 190, ``versuche`` seit jeher -
das **Instrument** nirgends. Behoben wurde es dort fuer eine von fuenf
Berichtsarten; die anderen vier standen seither unter *gemessen und offen*.

Warum die dritte Dimension nicht optional ist
---------------------------------------------
Der Unterschied zwischen den beiden Punkten sind zwei Dinge - ein Hebel ueber
1,0 und ein Funding ueber null - und er entscheidet ueber zwei Gates: Am
Spot-Punkt besteht der Bestand 9 von 11, am Perpetual-Punkt 7 von 11. Eine
Datei, in der "9 von 11" steht, ohne zu welchem Punkt, ist damit nicht bloss
unvollstaendig, sondern verwechselbar.

Genau diese Verwechslung ist in diesem Projekt elf Mal vorgekommen: eine
Groesse an Punkt A gemessen und an Punkt B verwendet. Befund 228 hat daraus
selbst noch einen falschen Widerspruch abgeleitet (zurueckgenommen in 229).

Was hier gehalten wird
----------------------
Nicht der Wert - der haengt am Lauf. Sondern dass das Feld **geschrieben**
wird, und zwar von jeder Berichtsart, die eine Datei ablegt.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: Berichtsarten, die eine Datei ablegen, und die Stelle, an der sie es tun.
BERICHTE: tuple[str, ...] = (
    "marktkombinationen",
    "machbarkeit",
    "nachpruefung",
    "teststaerke",
)


def _quelltext(name: str) -> str:
    baum = ast.parse(Path("cli.py").read_text())
    for n in ast.walk(baum):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return ast.unparse(n)
    raise AssertionError(f"{name} gibt es nicht mehr")


class TestJedeBerichtsartNenntIhn:
    @pytest.mark.parametrize("befehl", BERICHTE)
    def test_der_betriebspunkt_steht_in_der_nutzlast(self, befehl: str) -> None:
        quelle = _quelltext(befehl)

        assert "betriebspunkt" in quelle, (
            f"'{befehl}' legt eine Datei ab, ohne den Betriebspunkt zu nennen"
        )

    @pytest.mark.parametrize("befehl", BERICHTE)
    def test_er_wird_gelesen_und_nicht_geschrieben(self, befehl: str) -> None:
        """``_betriebspunkt`` liest ihn aus Genom und Konfiguration ab.

        Ein von Hand gesetzter Text waere die Sorte gepflegte Angabe, die in
        diesem Projekt schon mehrfach von der Wirklichkeit weggelaufen ist -
        zuletzt in Befund 235, wo eine ganze Handlungsliste auf dem Stand von
        Befund 108 stand.
        """
        assert "_betriebspunkt(" in _quelltext(befehl)

    def test_teststaerke_zaehlt_mit(self) -> None:
        """Sie schreibt ihre Datei nicht ueber ``write_report``, sondern
        selbst - und ist deshalb bei einer Suche nach ``write_report``
        unsichtbar. Genau so ist sie bis 242 durchgerutscht."""
        quelle = _quelltext("teststaerke")

        assert "write_report" not in quelle
        assert "betriebspunkt" in quelle


class TestDerZulassungsbericht:
    """Er hat eine andere Form - und eine andere Begruendung."""

    def test_die_nutzlast_kennt_das_feld(self) -> None:
        import inspect

        from research.admission import report_payload

        assert "betriebspunkt" in inspect.signature(report_payload).parameters

    def test_es_landet_unter_markt(self) -> None:
        from research.admission import AdmissionReport, report_payload

        nutzlast = report_payload(
            AdmissionReport(),
            symbol="BTCUSDT",
            interval="1d",
            history_from="2020-01-01",
            history_to="2026-01-01",
            candles=100,
            gates_full=True,
            betriebspunkt="Spot (kein Hebel, kein Funding)",
        )

        assert nutzlast["markt"]["betriebspunkt"] == "Spot (kein Hebel, kein Funding)"

    def test_ohne_angabe_bleibt_es_leer(self) -> None:
        """Lieber nichts als eine Angabe, die zu keinem Kandidaten gehoert.

        Ein Zulassungslauf prueft mehrere Genome, und der Hebel steht im
        Genom. Gibt es keinen Champion, gibt es auch keinen Punkt, der fuer
        den Bericht spraeche.
        """
        from research.admission import AdmissionReport, report_payload

        nutzlast = report_payload(
            AdmissionReport(),
            symbol="BTCUSDT",
            interval="1d",
            history_from="2020-01-01",
            history_to="2026-01-01",
            candles=100,
            gates_full=True,
        )

        assert nutzlast["markt"]["betriebspunkt"] == ""

    def test_der_befehl_nimmt_den_des_champions(self) -> None:
        """Geschrieben wird er von ``cli research`` - "zulassung" ist die Art
        des Berichts, nicht der Name des Befehls. Die beiden auseinanderzu-
        halten ist hier keine Spitzfindigkeit: Wer nach einem Befehl dieses
        Namens sucht, findet keinen und schliesst daraus das Falsche.
        """
        quelle = _quelltext("research")

        assert "report.champion.genome" in quelle
        assert "betriebspunkt=" in quelle


class TestWasDerPunktUnterscheidet:
    """``_betriebspunkt`` liest genau die zwei Dinge, die die Punkte trennen."""

    @staticmethod
    def _konfig(funding):
        from decimal import Decimal

        class Funding:
            default_rate = Decimal(funding)

        class Konfig:
            pass

        k = Konfig()
        k.funding = Funding()
        return k

    @staticmethod
    def _genom(hebel):
        class Sizing:
            fraction = hebel

        class Genom:
            sizing = Sizing()

        return Genom()

    def test_ohne_hebel_und_ohne_funding_ist_spot(self) -> None:
        import cli

        punkt = cli._betriebspunkt(self._genom(1.0), [self._konfig("0")])

        assert punkt == "Spot (kein Hebel, kein Funding)"

    def test_hebel_macht_den_unterschied(self) -> None:
        import cli

        punkt = cli._betriebspunkt(self._genom(3.0), [self._konfig("0")])

        assert "Spot" not in punkt
        assert "3" in punkt

    def test_funding_macht_den_unterschied(self) -> None:
        import cli

        punkt = cli._betriebspunkt(self._genom(1.0), [self._konfig("0.0001")])

        assert "Spot" not in punkt
