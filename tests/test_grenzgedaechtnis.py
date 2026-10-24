"""Die Risikogrenzen greifen im Modus der Zulassung fast nicht - Befund 403.

Befund 400 hat aus der Zahlendifferenz (156 je Fenster gegen 98 durchgehend)
eine Erklaerung **geschlossen**: Rund 58 seien Grenzartefakte, Positionen, die
am Fensterende geschlossen und danach neu eroeffnet werden. Nachgemessen ist
sie widerlegt:

* **Kein einziger** Trade steigt an einem Fensterende aus. Die Gruende der 158
  rohen Trades: ``signal_exit`` 78, ``stop_loss`` 68, ``take_profit`` 10,
  ``end_of_data`` 2.
* **Null** zerschnittene Paare.
* Die Einstiege haeufen sich an **keinem** Fensteranfang: am ersten Tag
  beginnt in beiden Modi kein Trade, 150 von 158 am sechsten oder spaeter.
* Die Differenz ist **kumulativ**: Fenster 0 bis 7 liefern in beiden Modi
  dieselben Zahlen (4, 8, 1, 2, 12, 3, 3, 8), ab Fenster 8 laeuft es
  auseinander, im letzten stehen 6 gegen 1.

Was es ist:

    Lauf                        Trades    CAGR   Rueckgang
    je Fenster, mit Limits         158  14,3391      9,869
    durchgehend, mit Limits         99  11,6275      7,504
    durchgehend, ohne Limits       162  19,0053     11,216
    je Fenster, ohne Limits        162  14,1915      9,869

Ohne Risikogrenzen geben beide Modi 162. Die Grenzen unterdruecken durchgehend
63 Trades und je Fenster vier - weil jedes Fenster ein eigener Backtest ist,
der ohne Equity-Vorgeschichte beginnt.
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.grenzgedaechtnis import GEMESSEN, Grenzlauf, Grenzvergleich


class TestWasGemessenIst:
    def test_ohne_limits_sind_es_in_beiden_modi_dieselben(self) -> None:
        """Der Kern: Die ganze Differenz sind die Grenzen."""
        a = GEMESSEN.hole(durchgehend=False, limits=False)
        b = GEMESSEN.hole(durchgehend=True, limits=False)

        assert a.trades == b.trades == 162

    def test_die_grenzen_unterdruecken_vier_gegen_dreiundsechzig(self) -> None:
        assert GEMESSEN.unterdrueckt(durchgehend=False) == 4
        assert GEMESSEN.unterdrueckt(durchgehend=True) == 63

    def test_also_greifen_sie_je_fenster_nicht(self) -> None:
        """Die Schwelle ist bewusst grosszuegig - ein Zehntel waere noch
        Wirkung, und vier von 63 sind darunter."""
        assert not GEMESSEN.greifen_je_fenster

    def test_und_die_aufteilung_allein_macht_fuenf_punkte(self) -> None:
        """Bei gleicher Trade-Zahl: 14,1915 je Fenster gegen 19,0053
        durchgehend - jedes Fenster startet bei der Anfangseinlage."""
        assert GEMESSEN.renditeunterschied_ohne_limits == pytest.approx(
            4.8138, abs=0.0001
        )

    def test_es_schmeichelt_dem_kandidaten(self) -> None:
        """Die Richtung, die zaehlt: Mit greifenden Grenzen ist die Rendite
        niedriger, nicht hoeher."""
        gemeldet = GEMESSEN.hole(durchgehend=False, limits=True)
        greifend = GEMESSEN.hole(durchgehend=True, limits=True)

        assert greifend.cagr_pct < gemeldet.cagr_pct
        assert gemeldet.cagr_pct - greifend.cagr_pct == pytest.approx(
            2.7116, abs=0.0001
        )

    def test_der_name_sagt_den_lauf(self) -> None:
        assert GEMESSEN.hole(durchgehend=True, limits=False).name == (
            "durchgehend, ohne Limits"
        )
        assert GEMESSEN.hole(durchgehend=False, limits=True).name == (
            "je Fenster, mit Limits"
        )

    def test_ein_fehlender_lauf_wird_gemeldet(self) -> None:
        leer = Grenzvergleich(
            laeufe=(
                Grenzlauf(
                    durchgehend=False, limits=True, trades=1,
                    cagr_pct=0.0, rueckgang_pct=0.0,
                ),
            )
        )

        with pytest.raises(KeyError, match="kein Lauf"):
            leer.hole(durchgehend=True, limits=True)


class TestWasDerKopfSagt:
    def test_er_nennt_die_widerlegte_erklaerung(self) -> None:
        from research import grenzgedaechtnis

        kopf = grenzgedaechtnis.__doc__ or ""

        assert "Grenzartefakte" in kopf
        assert "Kein einziger" in kopf
        assert "signal_exit" in kopf

    def test_und_die_kumulative_gestalt(self) -> None:
        from research import grenzgedaechtnis

        kopf = grenzgedaechtnis.__doc__ or ""

        assert "nicht grenzlokal, sondern kumulativ" in kopf
        assert "4, 8, 1, 2, 12, 3," in kopf

    def test_und_den_grund(self) -> None:
        from research import grenzgedaechtnis

        kopf = grenzgedaechtnis.__doc__ or ""

        assert "risk.ohne_vorgeschichte_simuliert" in kopf
        assert "Kill-Switch" in kopf

    def test_und_dass_es_schmeichelt(self) -> None:
        from research import grenzgedaechtnis

        kopf = grenzgedaechtnis.__doc__ or ""

        assert "schmeichelt" in kopf

    def test_und_die_beiden_nicht_schluesse(self) -> None:
        from research import grenzgedaechtnis

        kopf = grenzgedaechtnis.__doc__ or ""

        assert "**Nicht**, dass der Modus zu wechseln ist" in kopf
        assert "**Nicht**, dass die Grenzen falsch gebaut sind" in kopf


class TestDerBefehlHatDieGegenprobe:
    def test_das_schalterchen(self) -> None:
        quelle = inspect.getsource(cli.aufteilung)

        assert '"--ohne-limits"' in quelle
        assert "Befund 403" in quelle

    def test_und_es_wirkt_auf_die_konfiguration(self) -> None:
        from tests.quelltext import rumpf

        koerper = rumpf(cli.aufteilung)

        assert "replace(v, enforce_risk_limits=False)" in koerper

    def test_und_der_kopf_nennt_den_zustand(self) -> None:
        quelle = inspect.getsource(cli.aufteilung)

        assert "Risikogrenzen: " in quelle


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    @staticmethod
    def _lauf(*, durchgehend: bool, limits: bool):
        from dataclasses import replace
        from pathlib import Path

        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.datenstand import alle_geschnitten
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        e = get_settings()
        store = CandleStore(e.paths.data_store)
        frames = common_range(
            alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        )
        genom = cli._ohne_hebel(spitzenkandidat())
        configs = cli._spotconfigs(symbole, e)
        if not limits:
            configs = {
                k: replace(v, enforce_risk_limits=False)
                for k, v in configs.items()
            }
        assert Path(e.paths.data_store).exists()
        return run_portfolio_walkforward(
            frames,
            lambda: compile_genome(genom),
            configs,
            durchgehend=durchgehend,
        )

    def test_kein_trade_steigt_am_fensterende_aus(self) -> None:
        """Die widerlegte Erklaerung aus Befund 400, am Lauf."""
        from collections import Counter

        bericht = self._lauf(durchgehend=False, limits=True)
        gruende = Counter(t.exit_reason for t in bericht.all_trades)

        assert set(gruende) == {
            "signal_exit",
            "stop_loss",
            "take_profit",
            "end_of_data",
        }
        assert gruende["signal_exit"] == 78
        assert gruende["stop_loss"] == 68

    def test_und_keine_einstiege_am_fensteranfang(self) -> None:
        bericht = self._lauf(durchgehend=False, limits=True)
        anfaenge = {w.window.test_start for w in bericht.windows}

        assert not [t for t in bericht.all_trades if t.entry_time in anfaenge]

    def test_die_ersten_acht_fenster_sind_in_beiden_modi_gleich(self) -> None:
        """Der Beweis, dass es nicht grenzlokal ist: Waere es die Grenze,
        waeren schon die ersten Fenster verschieden."""
        je = [len(w.trades) for w in self._lauf(durchgehend=False, limits=True).windows]
        durch = [len(w.trades) for w in self._lauf(durchgehend=True, limits=True).windows]

        assert je[:8] == durch[:8] == [4, 8, 1, 2, 12, 3, 3, 8]
        assert je[-1] != durch[-1]

    def test_ohne_limits_geben_beide_modi_dieselbe_zahl(self) -> None:
        """Der Kern des Befundes."""
        je = self._lauf(durchgehend=False, limits=False)
        durch = self._lauf(durchgehend=True, limits=False)

        assert len(je.all_trades) == len(durch.all_trades) == 162

    def test_und_die_vier_laeufe_stimmen_mit_dem_kopf(self) -> None:
        for lauf in GEMESSEN.laeufe:
            bericht = self._lauf(
                durchgehend=lauf.durchgehend, limits=lauf.limits
            )

            assert len(bericht.all_trades) == lauf.trades, lauf.name
            assert bericht.combined.cagr_pct == pytest.approx(
                lauf.cagr_pct, abs=0.001
            ), lauf.name


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_die_widerlegung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 403)

        assert "geschlossen, nicht gemessen" in eintrag.ergebnis
        assert "Kein einziger" in eintrag.ergebnis
        assert "signal_exit 78" in eintrag.ergebnis

    def test_und_die_vier_laeufe(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 403)

        for zahl in ("162", "63", "14,3391", "11,6275", "19,0053", "14,1915"):
            assert zahl in eintrag.ergebnis, zahl

    def test_und_was_das_heisst(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 403)

        assert "Risikogrenzen praktisch" in eintrag.ergebnis
        assert "schmeichelt" in eintrag.ergebnis

    def test_400_traegt_den_vermerk(self) -> None:
        """Korrigiert wird durch Vermerk, nicht durch Ueberschreiben."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 400)

        assert "falsch, siehe 403" in eintrag.ergebnis
        assert eintrag.zuletzt == 403

    def test_und_das_modul_aus_400_auch(self) -> None:
        from research import aufteilung

        kopf = aufteilung.__doc__ or ""

        assert "Hier stand eine falsche Erklaerung" in kopf
        assert "Befund 403" in kopf
