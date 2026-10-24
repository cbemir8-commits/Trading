"""Ein Balken weniger am Anfang bewegt drei Punkte - Befund 400.

``run_walkforward`` verankert die Fenster am Reihenanfang::

    start = frame["open_time"].iloc[0].to_pydatetime()
    windows = splitter.split(start, end)

Ein Balken weniger dort verschiebt deshalb **jede** Fenstergrenze um einen
Tag. Und ohne ``durchgehend=True`` ueberlebt keine Position eine
Fenstergrenze - der Kopf dort sagt selbst, dass erst der durchgehende Modus
sie *"so wie im Betrieb"* tragen laesst. Die Zulassung laeuft im anderen.

Gemessen, Spot-Punkt, Zulassungsreihe, alle elf Laeufe mit 32 Fenstern:

    weg   fertig     CAGR
      0      156   14,3391   <- der gemeldete Lauf, der niedrigste von allen
      5      153   17,3779
     10      152   17,4522

3,1130 Punkte Spanne gegen 0,661 Punkte Abstand zur Betriebsschwelle. Die
weggelassenen Balken liegen im ersten **Trainings**fenster und werden nie
gehandelt.

Hinten abgeschnitten bewegt sich **nichts** - das ist die Gegenprobe zur
Bauart. Und im durchgehenden Modus sind es 98 fertige Trades bei jedem
Versatz statt 152 bis 156: rund 58 der gemeldeten Trades sind Grenzartefakte.
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.aufteilung import VERSATZ, Aufteilungsstreuung, streuung

#: Die Jahresrenditen aus Befund 400, Versatz 0 bis 10.
GEMESSENE_RENDITE = (
    14.3391,
    15.1845,
    16.6152,
    16.8168,
    16.9336,
    17.3779,
    16.8754,
    16.5358,
    15.9289,
    16.6103,
    17.4522,
)


class TestDieStreuung:
    def test_spanne_und_streuung(self) -> None:
        s = streuung("Jahresrendite", GEMESSENE_RENDITE)

        assert s.spanne == pytest.approx(3.1131, abs=0.0001)
        assert s.streuung == pytest.approx(0.9379, abs=0.0001)

    def test_der_gemeldete_lauf_ist_der_niedrigste(self) -> None:
        """Nicht nebenbei: Wer sich einen Versatz aussucht, bekommt einen
        besseren - und genau deshalb darf er es nicht."""
        assert min(GEMESSENE_RENDITE) == GEMESSENE_RENDITE[0]

    def test_und_der_einzige_unter_der_schwelle(self) -> None:
        assert GEMESSENE_RENDITE[0] < 15.0
        assert all(w >= 15.0 for w in GEMESSENE_RENDITE[1:])

    def test_versatz_deckt_elf_laeufe(self) -> None:
        assert len(VERSATZ) == len(GEMESSENE_RENDITE)
        assert VERSATZ[0] == 0

    def test_mittel(self) -> None:
        s = streuung("Jahresrendite", GEMESSENE_RENDITE)

        assert s.mittel == pytest.approx(16.4245, abs=0.0001)

    def test_eine_aufteilung_ist_keine_streuung(self) -> None:
        with pytest.raises(ValueError, match="keine Streuung"):
            Aufteilungsstreuung(name="x", werte=(1.0,))

    def test_die_zeile_nennt_alle_vier_zahlen(self) -> None:
        zeile = streuung("Jahresrendite", GEMESSENE_RENDITE).zeile()

        for zahl in ("14.3391", "17.4522", "3.1131", "0.9379"):
            assert zahl in zeile, zahl


class TestDeckt:
    """Die Frage, um die es geht: Entscheidet dieser Lauf den Abstand?"""

    def test_der_abstand_zur_betriebsschwelle_ist_gedeckt(self) -> None:
        s = streuung("Jahresrendite", GEMESSENE_RENDITE)

        assert s.deckt(15.0 - GEMESSENE_RENDITE[0])

    def test_und_die_reserve_des_jahresgates_auch(self) -> None:
        """Rueckwirkend auf die eigene Arbeit: 0,39 Punkte aus den Befunden
        395 bis 397 liegen innerhalb der Streuung von 1,38."""
        s = streuung(
            "Schlechtestes Jahr",
            (-9.61, -9.71, -9.51, -9.77, -10.02, -9.69, -10.17, -8.96, -10.34),
        )

        assert s.spanne == pytest.approx(1.38, abs=0.01)
        assert s.deckt(0.39)

    def test_ein_grosser_abstand_nicht(self) -> None:
        """Die Luecke des Deflated Sharpe ist 0,3674 - und die Streuung des
        DSR ueber die Aufteilungen betraegt 0,098."""
        s = streuung(
            "Deflated Sharpe",
            (0.5826, 0.6040, 0.6125, 0.5810, 0.6091, 0.6305, 0.5784, 0.6678),
        )

        assert not s.deckt(0.3674)

    def test_das_vorzeichen_entscheidet_nichts(self) -> None:
        s = streuung("Jahresrendite", GEMESSENE_RENDITE)

        assert s.deckt(-0.661) == s.deckt(0.661)

    def test_genau_auf_der_spanne_gilt_als_gedeckt(self) -> None:
        s = streuung("x", (1.0, 2.0))

        assert s.deckt(1.0)
        assert not s.deckt(1.0001)


class TestWasDerKopfSagtUndWasNicht:
    def test_er_nennt_die_bauart(self) -> None:
        from research import aufteilung

        kopf = aufteilung.__doc__ or ""

        assert 'start = frame["open_time"].iloc[0]' in kopf
        assert "durchgehend=True" in kopf

    def test_und_die_gegenprobe_hinten(self) -> None:
        from research import aufteilung

        kopf = aufteilung.__doc__ or ""

        assert "hinten" in kopf
        assert "14,3391 auf vier" in kopf

    def test_und_die_beiden_nicht_schluesse(self) -> None:
        """Das Wichtigste am Kopf: Er verbietet die zwei Schluesse, zu denen
        die Zahl einlaedt."""
        from research import aufteilung

        kopf = aufteilung.__doc__ or ""

        assert "**Nicht**, dass der Kandidat besteht" in kopf
        assert "**Nicht**, dass der Modus zu wechseln ist" in kopf

    def test_und_den_rueckblick_auf_die_eigene_arbeit(self) -> None:
        from research import aufteilung

        kopf = aufteilung.__doc__ or ""

        assert "0,39 Punkte Reserve" in kopf
        assert "395 bis 397" in kopf


class TestDerBefehl:
    def test_er_schneidet_und_nennt_die_reihe(self) -> None:
        """Die Inventur-Regel aus Befund 387/390: Wer eine Zahl neben
        'referenz.py' setzt, entscheidet sich fuer eine Reihe."""
        from tests.quelltext import rumpf

        koerper = rumpf(cli.aufteilung)

        assert "alle_geschnitten(roh)" in koerper
        assert "reihenzeile(geschnitten)" in koerper

    def test_er_laesst_die_messlatte_aus_der_tafel(self) -> None:
        """Sie traegt zwei Groessen (Befund 395) - in einer Streuungstafel
        waere das eine Spanne aus Jahres- und Gesamtrendite."""
        from tests.quelltext import nur_prosa, rumpf

        koerper = rumpf(cli.aufteilung)

        assert '"Messlatte"' in koerper, "ihre Zweige werden gesammelt"
        assert "lattenzweige" in koerper
        assert "Befund 395" in nur_prosa(inspect.getsource(cli.aufteilung))

    def test_er_fragt_deckt(self) -> None:
        from tests.quelltext import rumpf

        koerper = rumpf(cli.aufteilung)

        assert "latte.deckt(fehlt)" in koerper

    def test_und_sagt_dass_kein_versatz_der_richtige_ist(self) -> None:
        quelle = inspect.getsource(cli.aufteilung)

        assert "Kein Versatz ist der richtige" in quelle
        assert "lockert das Gate" in quelle

    def test_der_docstring_nennt_die_gemessene_zahl(self) -> None:
        text = cli.aufteilung.__doc__ or ""

        assert "3,1130" in text
        assert "0,661" in text
        assert "keine Erlaubnis" in text


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    @staticmethod
    def _lauf(*, weg: int, hinten: bool = False, durchgehend: bool = False):
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
        from research.randschnitt import ohne_zensierte
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        e = get_settings()
        store = CandleStore(e.paths.data_store)
        versuche = load_trials(Path(e.paths.state) / "trials.json")
        roh = alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        if hinten:
            teile = {
                s: (f.iloc[: len(f) - weg] if weg else f).reset_index(drop=True)
                for s, f in roh.items()
            }
        else:
            teile = {s: f.iloc[weg:].reset_index(drop=True) for s, f in roh.items()}
        frames = common_range(teile)
        genom = cli._ohne_hebel(spitzenkandidat())
        configs = cli._spotconfigs(symbole, e)
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
            trials_so_far=versuche,
            frames=frames,
            configs=configs,
        )
        return (
            len(bericht.windows),
            len(ohne_zensierte(bericht).all_trades),
            float(bericht.combined.cagr_pct),
            sum(1 for r in gates.results if r.status is GateStatus.PASS),
        )

    def test_der_gemeldete_lauf_stimmt_mit_referenz(self) -> None:
        fenster, fertig, cagr, gates = self._lauf(weg=0)

        assert (fenster, fertig, gates) == (32, 156, 9)
        assert cagr == pytest.approx(14.3391, abs=0.001)

    def test_ein_balken_weniger_hebt_sie_ueber_die_schwelle(self) -> None:
        """**Ein** Balken, aus dem ersten Trainingsfenster."""
        fenster, _, cagr, gates = self._lauf(weg=1)

        assert fenster == 32, "dieselbe Fensterzahl - es ist die Aufteilung"
        assert cagr == pytest.approx(15.1845, abs=0.001)
        assert gates == 10

    def test_zehn_balken_weniger_geben_drei_punkte_mehr(self) -> None:
        _, _, cagr, _ = self._lauf(weg=10)

        assert cagr == pytest.approx(17.4522, abs=0.001)
        assert cagr - 14.3391 == pytest.approx(3.1131, abs=0.002)

    def test_hinten_abgeschnitten_bewegt_nichts(self) -> None:
        """Die Gegenprobe zur Bauart: Die Fenster haengen am Anfang."""
        for weg in (1, 5, 10):
            fenster, fertig, cagr, gates = self._lauf(weg=weg, hinten=True)

            assert (fenster, fertig, gates) == (32, 156, 9), weg
            assert cagr == pytest.approx(14.3391, abs=0.001), weg

    def test_durchgehend_haelt_die_tradezahl_fest(self) -> None:
        """Der Mechanismus: Ohne Grenzschnitt sind es 98 Trades, und zwar
        bei jedem Versatz - rund 58 der gemeldeten 156 sind Artefakte."""
        zahlen = {self._lauf(weg=w, durchgehend=True)[1] for w in (0, 1, 5, 10)}

        assert zahlen == {98}

    def test_und_ist_auf_den_blockierenden_gates_schlechter(self) -> None:
        """Die unbequeme Haelfte - kein Schlupfloch in irgendeine Richtung."""
        _, fertig, cagr, gates = self._lauf(weg=0, durchgehend=True)

        assert fertig == 98
        assert cagr == pytest.approx(11.6275, abs=0.001)
        assert gates == 8


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_die_bauart(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 400)

        assert 'frame["open_time"].iloc[0]' in eintrag.ergebnis
        assert "durchgehend=True" in eintrag.ergebnis

    def test_und_die_zahlen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 400)

        for zahl in ("14,3391", "17,4522", "3,1130", "0,661", "98", "1,5189"):
            assert zahl in eintrag.ergebnis, zahl

    def test_und_die_beiden_nicht_schluesse(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 400)

        assert "dass der Kandidat besteht" in eintrag.ergebnis
        assert "dass der Modus zu wechseln ist" in eintrag.ergebnis

    def test_und_der_rueckblick(self) -> None:
        from research.stand import BEHOBEN, OFFEN

        eintrag = next(r for r in BEHOBEN if r.befund == 400)
        offen = next(r for r in OFFEN if r.befund == 395)

        assert "395 bis 397" in eintrag.ergebnis
        assert "kleiner als das Rauschen des Verfahrens" in offen.ergebnis
        assert offen.zuletzt == 400

    def test_und_399_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 399).zuletzt == 400
