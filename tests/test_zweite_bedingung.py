"""Die Aussicht nannte eine Bedingung, und es sind zwei - Befund 398.

Befund 328 hat den Aussichtszeilen ihre Bedingung gegeben, mit einem Satz, der
auch auf die zweite zutrifft:

    "Wer sie liest, liest eine Zeitangabe; die Bedingung daneben steht
     nirgends."

Die erste: Die 5,9 Jahre gelten **bei unveraenderter Guete je Trade**, denn
``erreichbarkeit.noetige_trades`` verspricht genau das. Die zweite ist seit
Befund 397 gemessen: In denselben 5,9 Jahren muss die **Reserve des
Jahres-Gates** halten, und null Treffer aus sieben unabhaengigen Jahren
schranken die Rate nur auf unter 34,8 % im Jahr - ueber den Horizont bis zu
92,0 % fuer mindestens einen Treffer.

Gerechnet, nicht gepflegt: Aus dem Spot-Lauf kommt **eine** Zahl, die
Jahreszahl. Schranke und Horizontwahrscheinlichkeit rechnet der Bericht
daraus.
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.stand import Lage


def _lage(**kwargs) -> Lage:
    grund = {
        "kandidat": "Trend 50 Tage mit Konfluenz",
        "maerkte": "BTC + ETH, 1d",
        "trades": 156,
        "sharpe_je_trade": 0.2708,
        "noetiger_sharpe": 0.3374,
        "bestanden": 9,
        "gesamt": 11,
        "offen": ("Messlatte", "Deflated Sharpe"),
        "versuche": 203,
    }
    return Lage(**{**grund, "effektiv": 115, **kwargs})


class TestDieZweiteBedingungStehtDaneben:
    def test_sie_steht_im_bericht(self) -> None:
        bericht = _lage(unabhaengige_jahre=7).bericht(kurz=True)

        assert "**Und eine zweite Bedingung**" in bericht
        assert "Reserve des Jahres-Gates" in bericht

    def test_die_erste_steht_weiter_da(self) -> None:
        """Befund 328 wird nicht ersetzt, sondern ergaenzt."""
        bericht = _lage(unabhaengige_jahre=7).bericht(kurz=True)

        assert "unveraenderter Guete je Trade" in bericht

    def test_die_zahlen_sind_gerechnet(self) -> None:
        """Sieben Jahre gehen hinein, die Schranke kommt heraus - die 34,8 %
        stehen nirgends als Text."""
        bericht = _lage(unabhaengige_jahre=7).bericht(kurz=True)

        assert "7 unabhaengigen Jahren" in bericht
        assert "34.8%" in bericht
        assert "92.0%" in bericht

    def test_mehr_jahre_geben_eine_engere_schranke(self) -> None:
        """Der Beweis, dass gerechnet und nicht gepflegt wird."""
        bericht = _lage(unabhaengige_jahre=28).bericht(kurz=True)

        assert "28 unabhaengigen Jahren" in bericht
        assert "34.8%" not in bericht
        assert "10.1%" in bericht

    def test_ohne_messung_steht_nichts(self) -> None:
        """Null heisst 'nicht gemessen'. Eine Schranke aus null Jahren waere
        eine Zahl ohne Beobachtung."""
        bericht = _lage().bericht(kurz=True)

        assert "**Und eine zweite Bedingung**" not in bericht
        assert "unveraenderter Guete je Trade" in bericht

    def test_und_dass_es_eine_schranke_ist(self) -> None:
        bericht = _lage(unabhaengige_jahre=7).bericht(kurz=True)

        assert "Schranke, kein Schaetzer" in bericht
        assert "Punktschaetzer ist null" in bericht

    def test_ein_zugelassener_kandidat_braucht_keine_aussicht(self) -> None:
        """``_aussichtszeilen`` gibt dort nichts zurueck - der ganze
        Abschnitt entfaellt, und mit ihm beide Bedingungen."""
        bericht = _lage(
            bestanden=11, offen=(), unabhaengige_jahre=7
        ).bericht(kurz=True)

        assert "WIE WEIT ES NOCH IST" not in bericht


class TestWoherDieJahreszahlKommt:
    def test_der_spotpunkt_zaehlt_sie_mit(self) -> None:
        quelle = inspect.getsource(cli._spotpunkt)

        assert "unabhaengige_jahre(verkettete_kurve(bericht)).anzahl" in quelle

    def test_und_der_bericht_bekommt_sie(self) -> None:
        quelle = inspect.getsource(cli.stand)

        assert "spotgates, zweitpunkt, spotjahre = _spotpunkt(" in quelle
        assert "unabhaengige_jahre=spotjahre," in quelle

    def test_ohne_einen_zweiten_lauf(self) -> None:
        """Der Spot-Punkt rechnet ohnehin; ein eigener Walk-Forward fuer eine
        Jahreszahl waere Verschwendung."""
        quelle = inspect.getsource(cli._spotpunkt)

        assert quelle.count("run_portfolio_walkforward(") == 1


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_beide_bedingungen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 398)

        assert "unveraenderter Guete je Trade" in eintrag.ergebnis
        assert "Reserve des Jahres-Gates" in eintrag.ergebnis
        assert "328" in eintrag.ergebnis

    def test_und_dass_gerechnet_wird(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 398)

        assert "gerechnet" in eintrag.ergebnis
        assert "101/103/109" in eintrag.ergebnis

    def test_und_was_nicht_behauptet_wird(self) -> None:
        """Die zweite Bedingung hebt die erste nicht auf, und keine von
        beiden sagt, dass der Weg scheitert."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 398)

        assert "Beide koennen halten" in eintrag.ergebnis
        assert "nicht **zeigen** kann" in eintrag.ergebnis

    def test_die_offene_richtung_nennt_die_dritte_stelle(self) -> None:
        from research.stand import OFFEN

        eintrag = next(r for r in OFFEN if r.befund == 395)

        assert "Lagebericht** seit 398" in eintrag.ergebnis

    def test_und_397_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 397).zuletzt == 398


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    def test_der_spotlauf_liefert_sieben_jahre(self) -> None:
        """Dieselbe Zahl, die ``test_jahresrate.py`` an der Kurve messt -
        hier aber auf dem Weg, den der Bericht geht."""
        from pathlib import Path

        from backtest.portfolio_walkforward import common_range
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.admission import load_trials
        from research.datenstand import alle_geschnitten
        from research.seeds import spitzenkandidat

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        e = get_settings()
        store = CandleStore(e.paths.data_store)
        versuche = load_trials(Path(e.paths.state) / "trials.json")
        frames = common_range(
            alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        )

        _, punkt, jahre = cli._spotpunkt(
            frames, symbole, spitzenkandidat(), versuche, e
        )

        assert punkt is not None
        assert jahre == 7
