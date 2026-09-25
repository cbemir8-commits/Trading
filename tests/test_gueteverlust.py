"""Die Bedingung unter der Entfernung zur Schwelle - Befund 328.

``cli stand`` sagt, wie weit es noch ist:

    derselbe am Spot  mindestens 2152 Tage (5,9 Jahre) fuer 75 fehlende
                      Beobachtungen

Die Zahl 75 kommt aus ``AUSSICHT.fehlend``, und ``noetig`` dahinter aus
``erreichbarkeit.noetige_trades``. Dessen Zusage steht in seinem eigenen
Kopf:

    Wie viele Trades braeuchte es bei **unveraenderter** Qualitaet je Trade?

Wer die Zeile liest, liest eine Zeitangabe. Die Bedingung daneben stand
nirgends - weder im Bericht noch in ``Aussicht``, das seinen Kopf sonst
ausfuehrlich der anderen Annahme widmet (der Sammelrate ueber sechs Fenster,
Befund 138/158).

Sie ist nicht akademisch. Im einzigen gemessenen Fall, in dem das Projekt
Beobachtungen wirklich hinzugewonnen hat, ist sie gebrochen
(``reports/marktkombinationen``, 13.09.):

    BTC+ETH             158 Trades   DSR 0,5881   CAGR 14,34 %
    BTC+ETH+LTC         266 Trades   DSR 0,4855   CAGR 11,50 %
    BTC+ETH+XRP         267 Trades   DSR 0,4609   CAGR 11,32 %
    BTC+ETH+LTC+XRP     375 Trades   DSR 0,4175   CAGR  9,95 %

Zweieinhalbmal so viele Trades, Deflated Sharpe 29 % niedriger.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.erreichbarkeit import (
    erlaubter_gueteverlust,
    noetige_trades,
    noetiger_sharpe,
)
from research.referenz import AUSSICHT, SPOTPUNKT

BERICHTE = Path("reports/marktkombinationen")


def _verlust(effektiv: int) -> float | None:
    return erlaubter_gueteverlust(
        effektiv=effektiv,
        guete=SPOTPUNKT.guete,
        trials=SPOTPUNKT.versuche,
        skew=SPOTPUNKT.schiefe,
        kurtosis=SPOTPUNKT.woelbung,
    )


class TestDerErlaubteVerlust:
    def test_bei_der_noetigen_stichprobe_ist_er_null(self) -> None:
        """**Die Probe auf die Rechnung.** ``noetig`` ist gerade die Zahl, bei
        der die heutige Guete genuegt - dort darf sie um nichts fallen."""
        assert _verlust(SPOTPUNKT.noetiges_n()) == pytest.approx(0.0, abs=1e-3)

    def test_bei_der_heutigen_stichprobe_ist_er_negativ(self) -> None:
        """Heute fehlt Guete, statt welche uebrig zu haben: 24,6 % mehr
        waeren noetig, nicht weniger erlaubt."""
        assert _verlust(SPOTPUNKT.effektiv) < -0.2

    def test_er_waechst_mit_der_stichprobe(self) -> None:
        werte = [_verlust(n) for n in (150, 190, 250, 375, 500)]

        assert werte == sorted(werte)

    def test_ohne_guete_gibt_es_keine_antwort(self) -> None:
        assert (
            erlaubter_gueteverlust(effektiv=200, guete=0.0, trials=203) is None
        )

    def test_eine_zu_kleine_stichprobe_hat_keine_grenze(self) -> None:
        """``noetiger_sharpe`` liefert dort ``None`` - kein Sharpe genuegt,
        und ein erlaubter Verlust waere eine Zahl ohne Gegenstand."""
        assert erlaubter_gueteverlust(effektiv=3, guete=0.27, trials=203) is None


class TestDasQuadratgesetz:
    """Die Pruefgroesse waechst mit ``Guete * Wurzel(n)``. Also verlangt eine
    halb so gute Regel rund die vierfache Stichprobe - das ist die Faustregel,
    die im Kopf von ``erlaubter_gueteverlust`` steht, und sie gehoert
    nachgerechnet statt behauptet."""

    @pytest.mark.parametrize("anteil", [0.9, 0.8, 0.7])
    def test_die_noetige_zahl_waechst_ungefaehr_quadratisch(
        self, anteil
    ) -> None:
        basis = noetige_trades(
            sharpe=SPOTPUNKT.guete,
            trials=SPOTPUNKT.versuche,
            skew=SPOTPUNKT.schiefe,
            kurtosis=SPOTPUNKT.woelbung,
        )
        schlechter = noetige_trades(
            sharpe=SPOTPUNKT.guete * anteil,
            trials=SPOTPUNKT.versuche,
            skew=SPOTPUNKT.schiefe,
            kurtosis=SPOTPUNKT.woelbung,
        )

        gemessen = schlechter / basis
        erwartet = 1 / anteil**2

        # Die Naeherung ist grob: ``E[max SR]`` und der Nenner haengen
        # ebenfalls an der Guete. Gefragt ist die Groessenordnung, nicht die
        # Stelle hinterm Komma.
        assert 0.75 * erwartet < gemessen < 1.15 * erwartet

    def test_und_bleibt_endlich(self) -> None:
        """Auch ein Drittel der Guete ist mit Daten zu heilen - das Gate ist
        nicht unerreichbar, es ist teuer."""
        n = noetige_trades(
            sharpe=SPOTPUNKT.guete / 3,
            trials=SPOTPUNKT.versuche,
            skew=SPOTPUNKT.schiefe,
            kurtosis=SPOTPUNKT.woelbung,
        )

        assert n is not None
        assert n > 5 * SPOTPUNKT.effektiv


class TestDerGemesseneGegenfall:
    """**Warum die Bedingung nicht akademisch ist.**"""

    @staticmethod
    def _kombinationen() -> dict[str, dict]:
        dateien = sorted(BERICHTE.glob("*.json"))
        if not dateien:
            pytest.skip("keine Marktkombinationen im Berichtsordner")
        roh = json.loads(dateien[-1].read_text(encoding="utf-8"))
        return {e["maerkte"]: e for e in roh["kombinationen"]}

    def test_maerkte_hinzuzunehmen_hat_den_dsr_gesenkt(self) -> None:
        """Der kontrollierte Vergleich: derselbe Kern, nur mehr Maerkte."""
        k = self._kombinationen()
        reihe = ["BTC+ETH", "BTC+ETH+XRP", "BTC+ETH+LTC+XRP"]
        if not all(n in k for n in reihe):
            pytest.skip("die Reihe steht in diesem Bericht nicht")

        trades = [k[n]["trades"] for n in reihe]
        dsr = [k[n]["dsr"] for n in reihe]

        assert trades == sorted(trades), "die Trades steigen"
        assert dsr == sorted(dsr, reverse=True), "und der DSR faellt"

    def test_und_zwar_deutlich(self) -> None:
        k = self._kombinationen()
        if "BTC+ETH" not in k or "BTC+ETH+LTC+XRP" not in k:
            pytest.skip("die beiden Enden stehen in diesem Bericht nicht")

        klein, gross = k["BTC+ETH"], k["BTC+ETH+LTC+XRP"]

        assert gross["trades"] / klein["trades"] > 2.3
        assert 1 - gross["dsr"] / klein["dsr"] > 0.25

    def test_die_guete_ist_schneller_gefallen_als_erlaubt(self) -> None:
        """**Der Kern von Befund 328, als Rechnung.**

        Bei 2,37-facher Stichprobe haette die Guete auf 1/Wurzel(2,37) = 65 %
        fallen duerfen, ohne dass die Pruefgroesse sinkt. Der gefallene DSR
        sagt, dass sie weiter gefallen ist.
        """
        import math

        k = self._kombinationen()
        if "BTC+ETH" not in k or "BTC+ETH+LTC+XRP" not in k:
            pytest.skip("die beiden Enden stehen in diesem Bericht nicht")

        faktor = k["BTC+ETH+LTC+XRP"]["trades"] / k["BTC+ETH"]["trades"]
        erlaubt = 1 / math.sqrt(faktor)

        assert 0.6 < erlaubt < 0.7
        assert k["BTC+ETH+LTC+XRP"]["dsr"] < k["BTC+ETH"]["dsr"], (
            "waere die Guete ueber der Grenze geblieben, haette der DSR "
            "nicht fallen koennen"
        )

    def test_auch_der_ertrag_ist_gefallen(self) -> None:
        """Nicht nur eine Gate-Zahl - die Messlatte reisst mit."""
        k = self._kombinationen()
        if "BTC+ETH" not in k or "BTC+ETH+LTC+XRP" not in k:
            pytest.skip("die beiden Enden stehen in diesem Bericht nicht")

        assert k["BTC+ETH+LTC+XRP"]["cagr_pct"] < k["BTC+ETH"]["cagr_pct"]


class TestDieBedingungStehtDaWoDieZahlSteht:
    """Befund 160 und 208 waren beide dieselbe Bauart: eine gepflegte Zahl,
    die an keiner Stelle angezeigt wurde. Eine gepflegte **Bedingung** ist
    nicht besser dran."""

    def test_aussicht_traegt_sie(self) -> None:
        assert "unveraenderter Guete je Trade" in AUSSICHT.BEDINGUNG
        assert "marktkombinationen" in AUSSICHT.BEDINGUNG

    def test_und_der_bericht_zeigt_sie(self) -> None:
        import ast

        baum = ast.parse(Path("research/stand.py").read_text(encoding="utf-8"))
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "_aussichtszeilen"
        )

        assert "BEDINGUNG" in quelle

    def test_sie_nennt_die_richtung(self) -> None:
        """"Schlechter sammeln" heisst **mehr** noetig, nicht weniger - und
        das muss dastehen, sonst liest es sich als beruhigende Fussnote."""
        assert "waechst" in AUSSICHT.BEDINGUNG


def test_noetiger_sharpe_und_erlaubter_verlust_sagen_dasselbe() -> None:
    """Zwei Wege auf dieselbe Zahl duerfen nicht auseinanderlaufen."""
    for n in (150, 250, 400):
        noetig = noetiger_sharpe(
            effektiv=n,
            trials=SPOTPUNKT.versuche,
            skew=SPOTPUNKT.schiefe,
            kurtosis=SPOTPUNKT.woelbung,
        )

        assert noetig == pytest.approx(SPOTPUNKT.guete * (1 - _verlust(n)))
