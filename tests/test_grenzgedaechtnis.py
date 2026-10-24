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


class TestDasKreuzJeGate:
    """Befund 404: dasselbe Kreuz wie 395, nur fuer Modus x Grenzen."""

    def test_elf_gates_auf_zwei_listen(self) -> None:
        from research.grenzgedaechtnis import STANDHAFT, WACKELIG

        assert len(STANDHAFT) == 8
        assert len(WACKELIG) == 3
        assert not set(STANDHAFT) & set(WACKELIG)

    def test_je_fenster_aendern_die_grenzen_am_gate_bild_nichts(self) -> None:
        """Die Inertheit aus 403, von der Gate-Seite."""
        from research.grenzgedaechtnis import GATEKREUZ

        assert GATEKREUZ[(False, True)] == GATEKREUZ[(False, False)]

    def test_durchgehend_aendern_sie_viel(self) -> None:
        from research.grenzgedaechtnis import GATEKREUZ

        assert GATEKREUZ[(True, True)] != GATEKREUZ[(True, False)]
        assert "Schlechtestes Jahr" in GATEKREUZ[(True, False)]
        assert "Schlechtestes Jahr" not in GATEKREUZ[(True, True)]

    def test_der_deflated_sharpe_faellt_in_allen_vier(self) -> None:
        """Die belastbarste Aussage, die das Projekt ueber sich hat."""
        from research.grenzgedaechtnis import GATEKREUZ, haengt_am_aufbau

        assert all("Deflated Sharpe" in gef for gef in GATEKREUZ.values())
        assert not haengt_am_aufbau("Deflated Sharpe")

    def test_monte_carlo_haengt_an_der_aufteilung(self) -> None:
        """Nicht an den Grenzen: Es besteht in beiden Fenster-Zellen und
        faellt in beiden durchgehenden."""
        from research.grenzgedaechtnis import GATEKREUZ, haengt_am_aufbau

        assert "Monte-Carlo" not in GATEKREUZ[(False, True)]
        assert "Monte-Carlo" not in GATEKREUZ[(False, False)]
        assert "Monte-Carlo" in GATEKREUZ[(True, True)]
        assert "Monte-Carlo" in GATEKREUZ[(True, False)]
        assert haengt_am_aufbau("Monte-Carlo")

    def test_der_kopf_warnt_vor_den_zwei_tradezahlen(self) -> None:
        """158/162/99/162 roh gegen 156/160/98/160 fertig - sie zu
        verwechseln ist der Fehler aus Befund 371."""
        from research import grenzgedaechtnis

        quelle = inspect.getsource(grenzgedaechtnis)

        assert "zwei Trade-Zahlen" in quelle
        assert "Befund 371" in quelle

    def test_und_die_tafel_steht_im_kopf(self) -> None:
        from research import grenzgedaechtnis

        kopf = grenzgedaechtnis.__doc__ or ""

        assert "f+L" in kopf and "d-L" in kopf
        assert "-  -10,940" in kopf
        assert "+  302,090" in kopf
        assert "Acht der elf Urteile" in kopf


@pytest.mark.daten
@pytest.mark.langsam
class TestDasKreuzAnDenEchtenDaten:
    """Die vier Fehllisten aus dem Kopf, am Lauf."""

    @staticmethod
    def _gefallen(*, durchgehend: bool, limits: bool) -> tuple[str, ...]:
        from dataclasses import replace
        from pathlib import Path

        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.admission import load_trials
        from research.datenstand import alle_geschnitten
        from research.gates import GateStatus, evaluate_gates
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
        bericht = run_portfolio_walkforward(
            frames,
            lambda: compile_genome(genom),
            configs,
            durchgehend=durchgehend,
        )
        gates = evaluate_gates(
            genom,
            bericht,
            next(iter(frames.values())),
            configs[symbole[0]],
            trials_so_far=load_trials(Path(e.paths.state) / "trials.json"),
            frames=frames,
            configs=configs,
        )
        return tuple(
            r.name for r in gates.results if r.status is GateStatus.FAIL
        )

    def test_die_vier_fehllisten_stimmen(self) -> None:
        from research.grenzgedaechtnis import GATEKREUZ

        for (durchgehend, limits), erwartet in GATEKREUZ.items():
            gefallen = self._gefallen(durchgehend=durchgehend, limits=limits)

            assert gefallen == erwartet, (durchgehend, limits)

    def test_je_fenster_sind_die_listen_gleich(self) -> None:
        """Der Kern von Befund 404, unabhaengig von der gepflegten Tafel."""
        mit = self._gefallen(durchgehend=False, limits=True)
        ohne = self._gefallen(durchgehend=False, limits=False)

        assert mit == ohne == ("Messlatte", "Deflated Sharpe")


class TestDieKontoprobe:
    """Befund 406: die Kontokurve eines Laufs, in dem kein Bein gebremst hat."""

    def test_beide_proben_loesen_nichts_aus(self) -> None:
        from research.grenzgedaechtnis import KONTOPROBEN

        assert len(KONTOPROBEN) == 2
        assert not any(k.haette_ausgeloest for k in KONTOPROBEN)

    def test_die_freie_kurve_ist_die_ohne_vorbehalt(self) -> None:
        """``kontorisiko`` nennt selbst den Vorbehalt: Die Kurve entsteht aus
        gebremsten Beinen. Mit freien Beinen entfaellt er."""
        from research.grenzgedaechtnis import KONTOPROBEN

        frei = next(k for k in KONTOPROBEN if not k.beine_gebremst)

        assert frei.trades == 162
        assert frei.kontorueckgang_pct == pytest.approx(10.77, abs=0.01)
        assert frei.unter_dem_killswitch
        assert frei.unter_dem_gate

    def test_und_die_gebremste_auch_nicht(self) -> None:
        from research.grenzgedaechtnis import KONTOPROBEN

        gebremst = next(k for k in KONTOPROBEN if k.beine_gebremst)

        assert gebremst.trades == 99
        assert gebremst.kontorueckgang_pct == pytest.approx(10.00, abs=0.01)
        assert not gebremst.haette_ausgeloest

    def test_der_kopf_nennt_die_korrektur_und_ihre_grenze(self) -> None:
        from research.grenzgedaechtnis import Kontoprobe

        text = Kontoprobe.__doc__ or ""

        assert "korrigiert die Lesart von 403 bis 405" in text
        assert "zwei getrennte Konten" in text
        assert "Nicht, dass der Kandidat besser dasteht" in text
        assert "0,265" in text


@pytest.mark.daten
@pytest.mark.langsam
class TestDieKontoprobeAnDenEchtenDaten:
    @staticmethod
    def _probe(*, gebremst: bool):
        from dataclasses import replace
        from decimal import Decimal

        import pandas as pd

        from backtest.portfolio_walkforward import common_range
        from backtest.walkforward import WalkForwardSplitter, run_walkforward
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.datenstand import alle_geschnitten
        from research.kontorisiko import kontokurve, pruefe
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        e = get_settings()
        store = CandleStore(e.paths.data_store)
        frames = common_range(
            alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        )
        genom = cli._ohne_hebel(spitzenkandidat())
        spot = cli._spotconfigs(symbole, e)
        je_bein = Decimal("500") / Decimal(len(frames))

        kurven, trades = {}, 0
        for markt, frame in frames.items():
            cfg = replace(
                spot[markt],
                initial_equity=je_bein,
                enforce_risk_limits=gebremst,
            )
            bericht = run_walkforward(
                frame,
                lambda: compile_genome(genom),
                cfg,
                WalkForwardSplitter(),
                durchgehend=True,
            )
            teile = [
                w.result.equity_curve
                for w in bericht.windows
                if not w.result.equity_curve.empty
            ]
            kurven[markt] = (
                pd.concat(teile, ignore_index=True) if teile else pd.DataFrame()
            )
            trades += len(bericht.all_trades)
        konto = pruefe(
            kontokurve(kurven),
            risk=e.risk,
            instrument=spot[symbole[0]].instrument,
        )
        return trades, konto

    def test_die_freie_kurve_loest_nichts_aus(self) -> None:
        """Der Kern von Befund 406 - und die Aussage ohne Vorbehalt."""
        trades, konto = self._probe(gebremst=False)

        assert trades == 162
        assert not konto.haette_ausgeloest
        assert konto.hoechster_rueckgang_pct == pytest.approx(10.77, abs=0.05)

    def test_und_die_gebremste_ebenso(self) -> None:
        trades, konto = self._probe(gebremst=True)

        assert trades == 99
        assert not konto.haette_ausgeloest
        assert konto.hoechster_rueckgang_pct == pytest.approx(10.00, abs=0.05)
