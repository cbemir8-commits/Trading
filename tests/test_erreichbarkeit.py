"""Was fehlt noch zum Deflated-Sharpe-Gate - und was kostet Weitersuchen?

Der wichtigste Test ist ``test_jeder_versuch_macht_es_schwerer``. Er haelt die
Eigenschaft fest, die dieses Projekt am meisten kostet und die man am
leichtesten uebersieht: Die Huerde waechst mit der Zahl der getesteten
Hypothesen. Wer breit sucht, entwertet rechnerisch, was er findet.
"""

from __future__ import annotations

import pytest

from research.erreichbarkeit import (
    MAX_SHARPE,
    bewerte,
    kennzahlen_aus_pnl,
    noetige_trades,
    noetiger_sharpe,
)

# Am Spitzenkandidaten gemessen (Euro-Ergebnisse, wie im Gate).
KANDIDAT = {"sharpe": 0.251, "skew": 3.57, "kurtosis": 17.4}


class TestNoetigeTrades:
    def test_mehr_trades_reichen_beim_kandidaten(self) -> None:
        n = noetige_trades(trials=95, **KANDIDAT)

        assert n is not None
        assert 154 < n < 400, "Der Abstand ist klein - eine Datenfrage, keine Ideenfrage"

    def test_ohne_vorteil_hilft_keine_menge(self) -> None:
        """Bei Sharpe 0 je Trade ist die Stichprobe nicht das Problem."""
        assert noetige_trades(sharpe=0.0, trials=95) is None
        assert noetige_trades(sharpe=-0.1, trials=95) is None

    def test_mehr_versuche_verlangen_mehr_trades(self) -> None:
        wenig = noetige_trades(trials=10, **KANDIDAT)
        viel = noetige_trades(trials=200, **KANDIDAT)

        assert wenig is not None and viel is not None
        assert viel > wenig

    def test_das_ergebnis_besteht_wirklich(self) -> None:
        """Die Bisektion muss den ersten bestehenden Wert liefern, nicht irgendeinen."""
        n = noetige_trades(trials=95, ziel=0.95, **KANDIDAT)
        assert n is not None

        davor = bewerte(trades=n - 1, trials=95, ziel=0.95, **KANDIDAT)
        genau = bewerte(trades=n, trials=95, ziel=0.95, **KANDIDAT)

        assert not davor.bestanden
        assert genau.bestanden


class TestNoetigerSharpe:
    def test_kandidat_braucht_etwas_mehr(self) -> None:
        s = noetiger_sharpe(trades=154, trials=95, skew=3.57, kurtosis=17.4)

        assert s is not None
        assert 0.251 < s < 0.4

    def test_winzige_stichprobe_ist_nicht_zu_retten(self) -> None:
        """Bei drei Trades hilft auch ein Sharpe von 3 nicht."""
        assert noetiger_sharpe(trades=3, trials=95) is None

    def test_zu_wenige_trades_geben_none(self) -> None:
        assert noetiger_sharpe(trades=2, trials=95) is None

    def test_grenze_wird_eingehalten(self) -> None:
        s = noetiger_sharpe(trades=200, trials=95)
        assert s is None or s <= MAX_SHARPE


class TestKostenDerSuche:
    def test_jeder_versuch_macht_es_schwerer(self) -> None:
        """**Die Eigenschaft, um die es geht.**

        Derselbe Kandidat, dieselben Daten, dieselbe Rechnung - nur die Suche
        davor war laenger. Gemessen am Spitzenkandidaten faellt der DSR von
        0,994 bei zehn Versuchen auf 0,535 bei fuenfhundert.
        """
        werte = [bewerte(trades=154, trials=t, **KANDIDAT).dsr for t in (10, 50, 95, 200, 500)]

        assert werte == sorted(werte, reverse=True), "Muss monoton fallen"
        assert werte[0] > 0.98
        assert werte[-1] < 0.6

    def test_kosten_sind_positiv_und_zehn_kosten_mehr(self) -> None:
        e = bewerte(trades=154, trials=95, **KANDIDAT)

        assert e.kosten_naechster_versuch > 0
        assert e.kosten_zehn_versuche > e.kosten_naechster_versuch

    def test_kosten_passen_zur_differenz(self) -> None:
        a = bewerte(trades=154, trials=95, **KANDIDAT)
        b = bewerte(trades=154, trials=105, **KANDIDAT)

        assert a.kosten_zehn_versuche == pytest.approx(a.dsr - b.dsr, abs=1e-9)


class TestBericht:
    def test_offener_fall_nennt_beide_wege(self) -> None:
        text = bewerte(trades=154, trials=95, **KANDIDAT).bericht()

        assert "Trades noetig" in text
        assert "Sharpe je Trade" in text
        assert "kostet" in text

    def test_bestandener_fall_sagt_es_kurz(self) -> None:
        text = bewerte(trades=5000, trials=5, **KANDIDAT).bericht()

        assert "Bestanden" in text

    def test_hinweis_auf_daten_vor_ideen(self) -> None:
        """Mehr Daten kosten keinen Versuch, eine neue Idee schon."""
        text = bewerte(trades=154, trials=95, **KANDIDAT).bericht()

        assert "kosten keinen Versuch" in text

    def test_aussichtsloser_fall_wird_benannt(self) -> None:
        text = bewerte(trades=154, sharpe=0.0, trials=95).bericht()

        assert "Mehr Daten helfen hier nicht" in text


class TestKennzahlen:
    def test_rechnet_wie_das_gate(self) -> None:
        """Gegenprobe gegen die Formel in ``research/gates.py``."""
        import numpy as np

        rng = np.random.default_rng(3)
        pnls = rng.normal(2.0, 10.0, 500)

        n, sharpe, schiefe, woelbung = kennzahlen_aus_pnl(pnls)

        spread = float(np.std(pnls, ddof=1))
        z = (pnls - np.mean(pnls)) / spread
        assert n == 500
        assert sharpe == pytest.approx(float(np.mean(pnls)) / spread)
        assert schiefe == pytest.approx(float(np.mean(z**3)))
        assert woelbung == pytest.approx(float(np.mean(z**4)))

    def test_zu_wenige_werte(self) -> None:
        assert kennzahlen_aus_pnl([1.0, 2.0]) == (2, 0.0, 0.0, 3.0)

    def test_ohne_streuung(self) -> None:
        """Alle Trades gleich - kein Sharpe, aber auch kein Absturz."""
        assert kennzahlen_aus_pnl([5.0] * 10)[1] == 0.0
