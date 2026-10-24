"""Eine Spalte, zwei Groessen - Befund 395.

Befund 267 hat entschieden, dass ein Gate mit zwei Bedingungen die Zahlen der
Bedingung meldet, an der es **haengt**. Damit ist das Paar richtig und nicht
mehr selbstauskunftsfaehig: Welche Groesse darin steht, haengt am Ausgang des
Laufs.

Gemessen am Spitzenkandidaten, Spot-Punkt, dieselbe Regel auf zwei
Reihenanfaengen:

    ab            Status       Wert   Schwelle  Bedingung
    2017-08-16    gefallen   14,339     15,000  Jahresrendite gegen Schwelle
    2018-08-16    bestanden 183,318     29,751  Rendite gegen Messlatte

Faktor elf, eine Spalte. ``cli anatomie`` hat davor gewarnt - im Konjunktiv,
"die beiden Spalten koennen verschiedene Bedingungen zeigen". Der Spot-Abstand
aus Befund 394 in ``cli stand`` hat es nicht getan und haette dort **153,567
Reserve** neben "14,339 gegen 15,000" gedruckt. Ausgeloest wird dieser Fall
genau dann, wenn der Spot-Punkt die Messlatte **besteht** - also im
Erfolgsfall.
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.gates import GateResult, GateStatus, vergleichbar


def _ergebnis(
    *,
    name: str = "Messlatte",
    status: GateStatus = GateStatus.FAIL,
    wert: float = 14.339,
    schwelle: float = 15.0,
    bedingung: str = "Jahresrendite gegen Betriebsschwelle",
) -> GateResult:
    return GateResult(
        name=name,
        status=status,
        value=wert,
        threshold=schwelle,
        message="",
        bedingung=bedingung,
    )


class TestDasErgebnisSagtWoranEsHaengt:
    def test_die_bedingung_ist_leer_wenn_nicht_gesetzt(self) -> None:
        """Leer heisst: eine Formel, und der Name sagt, welche. Nur die zwei
        Gates mit zwei Bedingungen fuellen das Feld."""
        r = GateResult(
            name="Drawdown",
            status=GateStatus.PASS,
            value=9.87,
            threshold=12.0,
            message="",
        )

        assert r.bedingung == ""

    def test_die_messlatte_fuellt_beide_zweige(self) -> None:
        from research import gates

        text = inspect.getsource(gates.gate_benchmark)

        assert "bedingung=(" in text
        assert '"Jahresrendite gegen Betriebsschwelle"' in text
        assert '"Rendite gegen heruntergefahrene Messlatte"' in text

    def test_und_die_stichprobengroesse_auch(self) -> None:
        """Ihre beiden Zweige sind Trades gegen 100 und Tage im Markt gegen
        250 - Befund 394 hat die zweite Zahl eigens nachgeprueft."""
        from research import gates

        text = inspect.getsource(gates.gate_sample_size)

        assert 'bedingung="Trades"' in text
        assert 'bedingung="Tage im Markt"' in text

    def test_der_kopf_nennt_die_gemessene_leiter(self) -> None:
        """Am Quelltext gelesen, nicht an ``__doc__``: Ein Feldkommentar ist
        ein Ausdruck ohne Wirkung, und bei ``slots=True`` ist das Attribut ein
        Deskriptor, dessen ``__doc__`` None bleibt. Wer das pruefen will,
        liest die Klasse."""
        text = inspect.getsource(GateResult)

        assert "183,318" in text
        assert "14,339" in text
        assert "Befund 395" in text


class TestVergleichbar:
    """Die eine Regel, die jede Oberflaeche fragt, bevor sie zwei Zahlen
    nebeneinander stellt."""

    def test_gleiche_bedingung_ist_vergleichbar(self) -> None:
        a = _ergebnis(wert=12.951)
        b = _ergebnis(wert=14.339)

        assert vergleichbar(a, b)

    def test_auch_ueber_den_status_hinweg(self) -> None:
        """Ein gefallenes gegen ein bestandenes Ergebnis ist der interessante
        Fall - und vergleichbar, solange die Groesse dieselbe ist."""
        a = _ergebnis(status=GateStatus.FAIL, wert=14.339)
        b = _ergebnis(status=GateStatus.PASS, wert=16.5)

        assert vergleichbar(a, b)

    def test_verschiedene_bedingung_nicht(self) -> None:
        a = _ergebnis(wert=14.339, schwelle=15.0)
        b = _ergebnis(
            status=GateStatus.PASS,
            wert=183.318,
            schwelle=29.751,
            bedingung="Rendite gegen heruntergefahrene Messlatte",
        )

        assert not vergleichbar(a, b)
        assert abs(b.value - b.threshold) == pytest.approx(153.567, abs=0.001)

    def test_verschiedene_gates_nicht(self) -> None:
        a = _ergebnis()
        b = _ergebnis(name="Drawdown", bedingung="")

        assert not vergleichbar(a, b)

    def test_ein_uebersprungenes_mit_nichts(self) -> None:
        """Es hat nicht gerechnet; sein Wert ist eine Null ohne Bedeutung -
        auch gegen ein zweites uebersprungenes."""
        a = _ergebnis(status=GateStatus.SKIP, wert=0.0, schwelle=0.0)
        b = _ergebnis(status=GateStatus.SKIP, wert=0.0, schwelle=0.0)

        assert not vergleichbar(a, b)
        assert not vergleichbar(a, _ergebnis())


class TestDerStatusschirm:
    """Der Spot-Abstand aus Befund 394, jetzt mit der Frage davor."""

    def test_er_fragt_vor_dem_abstand(self) -> None:
        quelle = inspect.getsource(cli.stand)

        assert "elif not vergleichbar(r, s):" in quelle

    def test_und_nennt_sonst_die_bedingung_statt_einer_zahl(self) -> None:
        quelle = inspect.getsource(cli.stand)
        zweig = quelle.split("elif not vergleichbar(r, s):")[1].split("else:")[0]

        assert "s.bedingung" in zweig
        assert "weite" not in zweig, "im nicht vergleichbaren Zweig keine Zahl"

    def test_die_zahl_steht_nur_im_vergleichbaren_zweig(self) -> None:
        quelle = inspect.getsource(cli.stand)

        assert quelle.count("weite = abs(s.value - s.threshold)") == 1
        vorher = quelle.split("weite = abs(s.value - s.threshold)")[0]
        assert "vergleichbar(r, s)" in vorher


class TestDieKipptafel:
    """``cli anatomie`` hat gewarnt; jetzt sagt es, welcher Fall vorliegt."""

    def test_sie_traegt_das_ergebnis_mit(self) -> None:
        quelle = inspect.getsource(cli.anatomie)

        assert "float(r.threshold), r) for r in gates.results" in quelle

    def test_und_markiert_die_zeile(self) -> None:
        quelle = inspect.getsource(cli.anatomie)

        assert "vergleichbar(a[2], b[2])" in quelle
        assert "(andere Groesse)" in quelle

    def test_der_konjunktiv_ist_weg(self) -> None:
        """Vorher: 'Die beiden Spalten koennen damit verschiedene Bedingungen
        zeigen.' Welcher Fall vorlag, musste der Leser aus den Gate-Meldungen
        zusammensuchen."""
        quelle = inspect.getsource(cli.anatomie)

        assert "koennen damit" not in quelle
        assert "tragen die beiden Spalten verschiedene Groessen" in quelle
        assert "Hier tragen beide Spalten je Gate dieselbe Groesse" in quelle


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    """Der Ausloeser, am Lauf. Dieselbe Regel, derselbe Punkt, zwei
    Reihenanfaenge - und zwei verschiedene Groessen in einer Spalte."""

    @staticmethod
    def _messlatte(ab: str):
        from pathlib import Path

        import pandas as pd

        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.admission import load_trials
        from research.datenstand import alle_geschnitten
        from research.gates import evaluate_gates
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        e = get_settings()
        store = CandleStore(e.paths.data_store)
        versuche = load_trials(Path(e.paths.state) / "trials.json")
        roh = alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        grenze = pd.Timestamp(ab, tz="UTC")
        frames = common_range(
            {
                s: f[pd.to_datetime(f["open_time"], utc=True) >= grenze].reset_index(
                    drop=True
                )
                for s, f in roh.items()
            }
        )
        genom = cli._ohne_hebel(spitzenkandidat())
        configs = cli._spotconfigs(symbole, e)
        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genom), configs
        )
        gates = evaluate_gates(
            genom,
            bericht,
            next(iter(frames.values())),
            configs[symbole[0]],
            trials_so_far=versuche,
            frames=frames,
            configs=configs,
        )
        return next(r for r in gates.results if r.name == "Messlatte")

    def test_die_volle_reihe_meldet_die_jahresrendite(self) -> None:
        r = self._messlatte("2017-08-16")

        assert r.status is GateStatus.FAIL
        assert r.value == pytest.approx(14.339, abs=0.001)
        assert r.threshold == pytest.approx(15.0, abs=0.001)
        assert r.bedingung == "Jahresrendite gegen Betriebsschwelle"

    def test_eine_sprosse_hoeher_die_gesamtrendite(self) -> None:
        """Und sie **besteht** dort - der Fall, in dem der alte Abstand
        zugeschlagen haette."""
        r = self._messlatte("2018-08-16")

        assert r.status is GateStatus.PASS
        assert r.value == pytest.approx(183.318, abs=0.001)
        assert r.threshold == pytest.approx(29.751, abs=0.001)
        assert r.bedingung == "Rendite gegen heruntergefahrene Messlatte"

    def test_und_die_beiden_sind_nicht_vergleichbar(self) -> None:
        voll = self._messlatte("2017-08-16")
        kurz = self._messlatte("2018-08-16")

        assert not vergleichbar(voll, kurz)
        assert abs(kurz.value - kurz.threshold) == pytest.approx(153.567, abs=0.001)


class TestWasImRegisterSteht:
    def test_die_zuordnung_aus_dem_kreuz(self) -> None:
        """Das schlechteste Jahr haengt am Betriebspunkt, nicht an der Reihe -
        das ist die Zuordnung, die Befund 394 offen liess."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 395)

        assert "-10,3200" in eintrag.ergebnis
        assert "-9,6100" in eintrag.ergebnis
        assert "nicht an der " in eintrag.ergebnis

    def test_die_leiter_an_beiden_punkten(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 395)

        assert "2571" in eintrag.ergebnis
        assert "**allen sechs**" in eintrag.ergebnis
        assert "161" in eintrag.ergebnis

    def test_und_der_eigene_fehler(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 395)

        assert "153,567" in eintrag.ergebnis
        assert "meiner eigenen" in eintrag.ergebnis
        assert "Konjunktiv" in eintrag.ergebnis

    def test_das_guthaben_steht_als_offene_richtung(self) -> None:
        """Zweimal ist dieser Test an seinem dritten ``assert`` gefallen, und
        zweimal zu Recht: Erst stand dort 'geraten wird sie hier nicht' (die
        Verteilung, gemessen in 396), dann 'hineingelesen' (die Rate,
        geschrankt in 397). Geprueft wird jetzt der Satz, der die Art der
        Zahl festhaelt - eine Schranke ist kein Schaetzer -, denn der bleibt,
        solange die Zahl eine Schranke ist.
        """
        from research.stand import OFFEN

        eintrag = next(r for r in OFFEN if r.befund == 395)

        assert "0,3900" in eintrag.ergebnis
        assert "Minimum" in eintrag.ergebnis
        assert "Punktschaetzer ist null" in eintrag.ergebnis

    def test_und_394_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 394).zuletzt == 395
