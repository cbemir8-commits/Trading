"""Plateau oder Grat - was die Landschaftskarte unterscheiden muss.

Die Karte beantwortet eine Frage, die das Plateau-Gate mit seinen zwei
Messpunkten nicht beantworten kann: Sitzt der Kandidat auf einer Nadelspitze
oder am Rand einer breiten Hochebene? Das sind verschiedene Lagen mit
verschiedenen Konsequenzen.

Die Tests hier pruefen vor allem, dass die Karte **nicht** schmeichelt:
verstreute Treffer duerfen nicht als Plateau durchgehen, und ein Kandidat
neben der Hochebene darf nicht so aussehen, als saesse er darauf.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestConfig
from core.config import RiskSettings
from core.models import Instrument
from research.landschaft import (
    Landschaft,
    Punkt,
    kartieren,
    leitperiode,
)
from research.seeds import spitzenkandidat


def punkt(faktor: float, gewinn: float, *, leit: int = 100) -> Punkt:
    return Punkt(faktor=faktor, leitperiode=leit, gewinn=gewinn, trades=10)


class TestFormDerLandschaft:
    def test_zusammenhaengende_kette_wird_gezaehlt(self):
        karte = Landschaft(punkte=[
            punkt(0.8, -1), punkt(0.9, 5), punkt(1.0, 5), punkt(1.1, 5),
            punkt(1.2, -1),
        ])

        assert karte.zusammenhaengend == 3

    def test_verstreute_treffer_sind_kein_plateau(self):
        """Der wichtigste Fall.

        Vier von sieben Punkten profitabel klingt nach zwei Dritteln - aber
        wenn sie einzeln stehen, ist es Rauschen, das oft genug positiv
        ausgefallen ist. Eine Quote allein wuerde das verschleiern.
        """
        karte = Landschaft(punkte=[
            punkt(0.7, 5), punkt(0.8, -1), punkt(0.9, 5), punkt(1.0, -1),
            punkt(1.1, 5), punkt(1.2, -1), punkt(1.3, 5),
        ])

        assert karte.quote > 0.5, "Die Quote sieht gut aus ..."
        assert karte.zusammenhaengend == 1, "... die Form aber nicht"
        assert "Grat" in karte.urteil()

    def test_kandidat_neben_dem_plateau_faellt_auf(self):
        """Eine breite Hochebene nuetzt nichts, wenn man daneben steht."""
        karte = Landschaft(punkte=[
            punkt(0.5, 5), punkt(0.6, 5), punkt(0.7, 5), punkt(0.8, 5),
            punkt(0.9, -1), punkt(1.0, 5),
        ])

        assert karte.zusammenhaengend == 4
        assert not karte.mitte_liegt_im_plateau
        assert "neben" in karte.urteil()

    def test_kandidat_im_plateau(self):
        karte = Landschaft(punkte=[
            punkt(0.8, 5), punkt(0.9, 5), punkt(1.0, 5), punkt(1.1, 5),
            punkt(1.25, -1),
        ])

        assert karte.mitte_liegt_im_plateau
        assert "Plateau" in karte.urteil()

    def test_leere_landschaft_behauptet_nichts(self):
        karte = Landschaft()

        assert karte.quote == 0.0
        assert karte.zusammenhaengend == 0
        assert "Nichts" in karte.urteil()

    def test_einzelner_treffer_ist_ein_grat(self):
        karte = Landschaft(punkte=[punkt(0.9, -1), punkt(1.0, 5), punkt(1.1, -1)])

        assert karte.zusammenhaengend == 1
        assert "Grat" in karte.urteil()


class TestLeitperiode:
    def test_nimmt_die_laengste_periode(self):
        genome = spitzenkandidat()

        # Der Kandidat traegt SMA(200) in der Konfluenz - das ist die
        # laengste und beschreibt den Punkt am besten.
        assert leitperiode(genome) == 200

    def test_ohne_indikatoren_null(self):
        from strategy.genome import Condition, Genome, Operand, Operator, TargetSpec

        genome = Genome(
            name="ohne", rationale="Nur Kursvergleich.",
            entry_long=[Condition(
                left=Operand(kind="price", name="close"),
                op=Operator.GT,
                right=Operand(kind="constant", value=1.0),
            )],
            targets=[TargetSpec(rr=2.0, portion=1.0)],
        )

        assert leitperiode(genome) == 0


class TestKartieren:
    """Der Durchlauf auf echten Kerzen - klein gehalten, aber echt."""

    @pytest.fixture
    def welt(self):
        rng = np.random.default_rng(11)
        n = 700
        schritte = rng.normal(0.0005, 0.02, n)
        welle = np.sin(np.arange(n) / 60.0) * 0.15
        kurs = 100.0 * np.exp(np.cumsum(schritte) + welle)
        frame = pd.DataFrame({
            "open_time": pd.date_range("2018-01-01", periods=n, freq="1D", tz="UTC"),
            "open": kurs, "high": kurs * 1.02, "low": kurs * 0.98, "close": kurs,
            "volume": np.full(n, 100.0), "turnover": kurs * 100.0,
        })
        instrument = Instrument(
            symbol="BTCUSDT", tick_size=Decimal("0.01"), qty_step=Decimal("0.001"),
            min_order_qty=Decimal("0.001"), max_order_qty=Decimal("1190"),
            min_notional=Decimal("5"), max_leverage=Decimal("100"),
        )
        config = BacktestConfig(
            instrument=instrument, risk=RiskSettings(), initial_equity=Decimal("500")
        )
        return {"M": frame}, {"M": config}

    def test_tastet_mehrere_punkte_ab(self, welt):
        frames, configs = welt

        karte = kartieren(spitzenkandidat(), frames, configs,
                      faktoren=(0.6, 0.8, 1.0, 1.2))

        assert len(karte.punkte) >= 3
        assert all(p.trades >= 0 for p in karte.punkte)

    def test_der_kandidat_ist_dabei_und_markiert(self, welt):
        frames, configs = welt

        karte = kartieren(spitzenkandidat(), frames, configs, faktoren=(0.8, 1.0, 1.2))

        assert any(abs(p.faktor - 1.0) < 1e-9 for p in karte.punkte)
        assert "<== Kandidat" in karte.tabelle()

    def test_punkte_sind_nach_faktor_sortiert(self, welt):
        """Sonst waere die Kettenlaenge Unsinn - sie liest die Reihenfolge."""
        frames, configs = welt

        karte = kartieren(spitzenkandidat(), frames, configs,
                      faktoren=(1.2, 0.6, 1.0, 0.8))

        faktoren = [p.faktor for p in karte.punkte]
        assert faktoren == sorted(faktoren)

    def test_doppelte_perioden_werden_nicht_zweimal_gerechnet(self, welt):
        """Zwei nahe Faktoren runden auf dieselben Perioden.

        Sie als zwei Punkte zu zaehlen wuerde die Kette kuenstlich
        verlaengern - und aus einem Grat ein Plateau machen.
        """
        frames, configs = welt

        karte = kartieren(spitzenkandidat(), frames, configs,
                      faktoren=(1.0, 1.001, 1.002))

        leitperioden = [p.leitperiode for p in karte.punkte]
        assert len(leitperioden) == len(set(leitperioden))

    def test_gewinn_ist_der_mittelwert_ueber_die_maerkte(self, welt):
        """Gleich gewichtet - so, wie der Korb gehandelt wuerde."""
        frames, configs = welt
        frames = {"A": frames["M"], "B": frames["M"]}
        configs = {"A": configs["M"], "B": configs["M"]}

        karte = kartieren(spitzenkandidat(), frames, configs, faktoren=(1.0,))

        p = karte.punkte[0]
        assert set(p.je_markt) == {"A", "B"}
        assert p.gewinn == pytest.approx(sum(p.je_markt.values()) / 2)


class TestDieselbeSkalierungWieDasGate:
    """Karte und Gate muessen dieselben Nachbarn erzeugen.

    Wuerde jedes seine eigene Skalierung mitbringen, verglichen sie
    verschiedene Dinge - der Fehler, der in diesem Projekt schon viermal
    aufgetreten ist.
    """

    def test_beide_nutzen_skaliere_perioden(self):
        import inspect

        from research import gates, landschaft

        assert "skaliere_perioden" in inspect.getsource(landschaft)
        assert "skaliere_perioden(genome, faktor)" in inspect.getsource(
            gates.nachbarschaft
        )

    def test_gate_nachbar_und_kartenpunkt_stimmen_ueberein(self):
        from research.gates import _vary_periods, skaliere_perioden

        genome = spitzenkandidat()
        nachbarn = list(_vary_periods(genome, 0.2))

        # Der langsamere Nachbar des Gates ist derselbe wie Faktor 1,2 der Karte.
        aus_karte = skaliere_perioden(genome, 1.2)
        assert any(n.genome_id == aus_karte.genome_id for n in nachbarn)
