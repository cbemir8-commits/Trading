"""Der Punkt mit greifenden Grenzen stand in keiner Kopfzeile - Befund 405.

Die Befunde 403 und 404 haben gemessen, dass die Risikogrenzen im Modus der
Zulassung vier von 162 Trades unterdruecken und durchgehend 63, und dass sie je
Fenster am Gate-Bild **nichts** aendern. Damit steht die wichtigste Zahl des
Projekts auf einer Stichprobe, die die eigene Schutzvorrichtung in einem
Betrieb verhindert haette - und das stand in keiner Kopfzeile. Wer es sehen
wollte, musste ``cli aufteilung --durchgehend`` kennen.

Dieselbe Lehre wie Befund 311 (ohne Betriebspunkt ist die Gate-Zahl
unvollstaendig), 370 (ohne Reihe stehen 157 Trades neben 156) und 394 (die elf
Zeilen gab es in keiner Ausgabe).
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.betriebspunkt import Betriebspunkt
from research.stand import Lage


def _punkt(**kwargs) -> Betriebspunkt:
    grund = {
        "name": "Spot durchgehend",
        "trades": 98,
        "cagr_pct": 11.6275,
        "rueckgang_pct": 7.504,
        "guete": 0.26,
        "dsr": 0.3185,
        "bestanden": 8,
        "gesamt": 11,
        "offen": ("Messlatte", "Monte-Carlo", "Deflated Sharpe"),
        "voraussetzung": (
            "Welcher Modus die Zulassung traegt, liegt beim Nutzer (400)"
        ),
    }
    return Betriebspunkt(**{**grund, **kwargs})


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
    return Lage(**{**grund, **kwargs})


class TestDieZeileStehtImKopf:
    def test_sie_nennt_den_punkt_und_seine_gates(self) -> None:
        bericht = _lage(grenzpunkt=_punkt()).bericht(kurz=True)

        assert "mit Grenzen    Spot durchgehend: 8 von 11" in bericht
        assert "Monte-Carlo" in bericht

    def test_und_die_beiden_unterdrueckungszahlen(self) -> None:
        bericht = _lage(grenzpunkt=_punkt()).bericht(kurz=True)

        assert "4 von 162 Trades, durchgehend 63" in bericht

    def test_und_den_grund(self) -> None:
        bericht = _lage(grenzpunkt=_punkt()).bericht(kurz=True)

        assert "ohne Equity-Vorgeschichte" in bericht
        assert "403/404" in bericht

    def test_die_voraussetzung_wird_gedruckt(self) -> None:
        """**Nicht nur gesetzt.** Mein erster Einbau hat sie am Punkt
        gefuehrt und in der Zeile verschwiegen - eine stille Auslassung,
        und die Sorte Zeile, an der Befund 389 haengengeblieben ist."""
        bericht = _lage(grenzpunkt=_punkt()).bericht(kurz=True)

        assert "(Voraussetzung offen:" in bericht
        assert "liegt beim Nutzer (400)" in bericht

    def test_ein_bestaetigter_punkt_braucht_sie_nicht(self) -> None:
        bericht = _lage(grenzpunkt=_punkt(bestaetigt=True)).bericht(kurz=True)

        assert "mit Grenzen" in bericht
        assert "Voraussetzung offen" not in bericht

    def test_ohne_messung_steht_nichts(self) -> None:
        bericht = _lage().bericht(kurz=True)

        assert "mit Grenzen" not in bericht

    def test_und_sie_steht_unter_dem_zweiten_punkt(self) -> None:
        """Die Reihenfolge ist die der Naehe zum Betrieb: berichtet, Spot,
        Spot mit greifenden Grenzen."""
        zweit = Betriebspunkt(
            name="Spot", trades=156, cagr_pct=14.3391, rueckgang_pct=9.869,
            guete=0.2708, dsr=0.5826, bestanden=9, gesamt=11,
            offen=("Messlatte", "Deflated Sharpe"),
        )
        zeilen = _lage(zweitpunkt=zweit, grenzpunkt=_punkt()).bericht(
            kurz=True
        ).splitlines()

        auch = next(i for i, z in enumerate(zeilen) if "Auch gemessen" in z)
        grenze = next(i for i, z in enumerate(zeilen) if "mit Grenzen" in z)

        assert auch < grenze

    def test_ein_punkt_ohne_gates_wird_ausgelassen(self) -> None:
        """Eine Zeile '0 von 0' waere keine Auskunft."""
        bericht = _lage(grenzpunkt=object()).bericht(kurz=True)

        assert "mit Grenzen" not in bericht


class TestWoherDieZahlKommt:
    def test_der_spotpunkt_kann_durchgehend(self) -> None:
        quelle = inspect.getsource(cli._spotpunkt)

        assert "durchgehend: bool = False" in quelle
        assert "durchgehend=durchgehend," in quelle

    def test_und_benennt_sich_danach(self) -> None:
        quelle = inspect.getsource(cli._spotpunkt)

        assert '"Spot durchgehend" if durchgehend else "Spot"' in quelle

    def test_und_traegt_die_offene_voraussetzung(self) -> None:
        quelle = inspect.getsource(cli._spotpunkt)

        assert "liegt beim Nutzer (400)" in quelle

    def test_der_befehl_ruft_ihn_zweimal(self) -> None:
        from tests.quelltext import rumpf

        koerper = rumpf(cli.stand)

        assert koerper.count("_spotpunkt(") == 2
        assert "durchgehend=True" in koerper
        assert "grenzpunkt=grenzpunkt," in koerper


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_lehre(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 405)

        assert "Dieselbe Lehre wie 311" in eintrag.ergebnis
        assert "erreicht niemanden" in eintrag.ergebnis

    def test_und_den_eigenen_fehler(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 405)

        assert "stille Auslassung" in eintrag.ergebnis
        assert "389" in eintrag.ergebnis

    def test_und_404_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 404).zuletzt == 405


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    def test_der_dritte_lauf_gibt_acht_von_elf(self) -> None:
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

        _, punkt, _ = cli._spotpunkt(
            frames,
            symbole,
            spitzenkandidat(),
            versuche,
            e,
            durchgehend=True,
        )

        assert punkt is not None
        assert punkt.name == "Spot durchgehend"
        assert punkt.trades == 98
        assert punkt.bestanden == 8
        assert set(punkt.offen) == {
            "Messlatte",
            "Monte-Carlo",
            "Deflated Sharpe",
        }
        assert punkt.dsr == pytest.approx(0.3185, abs=0.001)
        assert not punkt.bestaetigt

    def test_und_der_zweite_bleibt_wie_er_war(self) -> None:
        """Die Gegenprobe: Der neue Zweig aendert den alten nicht."""
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
        assert punkt.name == "Spot"
        assert punkt.trades == 156
        assert punkt.bestanden == 9
        assert punkt.dsr == pytest.approx(0.5826, abs=0.001)
        assert jahre == 7
