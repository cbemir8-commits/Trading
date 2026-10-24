"""Neun der elf Urteile sind entschieden - Befund 401.

Befund 400 hat gemessen, dass die Gate-Zahl zwischen 9 und 10 schwankt, wenn
ein Balken am Reihenanfang fehlt, und daraus den Satz gezogen: Ein Abstand
kleiner als die Streuung des Verfahrens ist kein Urteil. Als **Zahl** stand
der Satz nur fuer die Jahresrendite.

Je Gate gerechnet, elf Aufteilungen, Spot-Punkt:

    Gate                       Abstand    Spanne   Urteil
    Stichprobengroesse       2000,0000   21,0000   entschieden
    Messlatte                        -         -   zwei Groessen (395)
    Out-of-Sample-Sharpe        0,5762    0,1947   entschieden
    Drawdown                    2,1313    0,7022   entschieden
    Schlechtestes Jahr          0,3900    0,9500   offen
    Bestaendigkeit              0,0806    0,0645   entschieden
    Monte-Carlo                 6,6735    0,4963   entschieden
    Regime-Aufteilung           4,3751    0,1746   entschieden
    Deflated Sharpe             0,3674    0,0763   entschieden
    Kosten-Stress            1863,7259    0,0000   entschieden
    Parameter-Plateau           0,4000    0,0000   entschieden

**Der Deflated Sharpe ist entschieden**, mit dem Viereinhalbfachen der
Spanne. Der Hauptblocker ist keine Aufteilungsfrage, und die Sorge aus 400 ist
damit begrenzt statt bestaetigt.

Offen sind zwei - 'Schlechtestes Jahr' (genau das Gate der Befunde 395 bis
397) und die Messlatte, die sich ueber ihre Jahresrendite beurteilen laesst:
0,661 gegen 3,1130, also auch offen.
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.aufteilung import ENTSCHIEDEN, OFFEN, ZWEI_GROESSEN, beurteile

#: Die Deflated-Sharpe-Werte aus Befund 400/401, elf Aufteilungen.
DSR = (
    0.5826,
    0.6040,
    0.6125,
    0.5810,
    0.6091,
    0.6305,
    0.5784,
    0.6261,
    0.6002,
    0.6410,
    0.6547,
)


class TestBeurteile:
    def test_der_deflated_sharpe_ist_entschieden(self) -> None:
        """0,3674 Abstand gegen 0,0763 Spanne - das Viereinhalbfache."""
        spruch = beurteile(
            name="Deflated Sharpe", wert=0.5826, schwelle=0.95, werte=DSR
        )

        assert spruch == ENTSCHIEDEN

    def test_das_schlechteste_jahr_nicht(self) -> None:
        spruch = beurteile(
            name="Schlechtestes Jahr",
            wert=-9.61,
            schwelle=-10.0,
            werte=(-9.61, -9.71, -9.51, -9.77, -10.02, -9.69, -10.17, -9.22),
        )

        assert spruch == OFFEN

    def test_zwei_bedingungen_geben_kein_urteil(self) -> None:
        """Eine Spanne aus Jahres- und Gesamtrendite waere eine Zahl ohne
        Bedeutung (Befund 395)."""
        spruch = beurteile(
            name="Messlatte",
            wert=14.339,
            schwelle=15.0,
            werte=(14.339, 241.867),
            bedingungen=(
                "Jahresrendite gegen Betriebsschwelle",
                "Rendite gegen heruntergefahrene Messlatte",
            ),
        )

        assert spruch == ZWEI_GROESSEN

    def test_eine_bedingung_stoert_nicht(self) -> None:
        spruch = beurteile(
            name="Stichprobengroesse",
            wert=2250.0,
            schwelle=250.0,
            werte=(2250.0, 2249.0, 2271.0),
            bedingungen=("Tage im Markt",) * 3,
        )

        assert spruch == ENTSCHIEDEN

    def test_das_vorzeichen_des_abstands_entscheidet_nichts(self) -> None:
        """Ein gefallenes und ein bestandenes Gate werden gleich behandelt -
        die Frage ist in beide Richtungen dieselbe."""
        unten = beurteile(name="x", wert=1.0, schwelle=2.0, werte=(1.0, 1.1))
        oben = beurteile(name="x", wert=3.0, schwelle=2.0, werte=(1.0, 1.1))

        assert unten == oben == ENTSCHIEDEN

    def test_ein_lauf_gibt_kein_urteil(self) -> None:
        with pytest.raises(ValueError, match="keine Streuung"):
            beurteile(name="x", wert=1.0, schwelle=2.0, werte=(1.0,))

    def test_aber_zwei_groessen_gehen_vor(self) -> None:
        """Erst wird gefragt, **ob** die Groesse eine ist - sonst waere die
        Fehlermeldung ueber die Streuung die falsche Auskunft."""
        spruch = beurteile(
            name="Messlatte",
            wert=1.0,
            schwelle=2.0,
            werte=(1.0,),
            bedingungen=("a", "b"),
        )

        assert spruch == ZWEI_GROESSEN


class TestWasDerKopfSagt:
    def test_er_nennt_den_hauptblocker(self) -> None:
        text = beurteile.__doc__ or ""

        assert "Hauptblocker ist also keine Aufteilungsfrage" in text
        assert "0,3674" in text
        assert "0,0763" in text

    def test_und_die_knappste_entscheidung(self) -> None:
        text = beurteile.__doc__ or ""

        assert "Bestaendigkeit" in text
        assert "1,25-fache" in text


class TestDerBefehlZeigtDieTafel:
    def test_er_sammelt_alle_elf(self) -> None:
        from tests.quelltext import rumpf

        koerper = rumpf(cli.aufteilung)

        assert "jegate.setdefault(r.name, []).append" in koerper
        assert "jezweig.setdefault(r.name, []).append" in koerper

    def test_und_beurteilt_jedes(self) -> None:
        from tests.quelltext import rumpf

        koerper = rumpf(cli.aufteilung)

        assert "spruch = beurteile(" in koerper
        assert "bedingungen=jezweig[name]," in koerper

    def test_und_nennt_die_tafel_nach_der_frage(self) -> None:
        quelle = inspect.getsource(cli.aufteilung)

        assert "Ist das Urteil eines?" in quelle

    def test_und_sagt_wie_die_messlatte_doch_zu_beurteilen_ist(self) -> None:
        quelle = inspect.getsource(cli.aufteilung)

        assert "ueber ihre Jahresrendite" in quelle


@pytest.fixture(scope="module")
def tafel():
    """**Einmal** fuer alle Tests, die sie brauchen: Jeder Aufruf kostet elf
    Walk-Forwards, und vier Tests waeren vierundvierzig.

    Auf Modulebene und nicht in der Klasse - klassenweit bricht hier eine
    Zusicherung in pytests Fixture-Verwaltung.
    """
    return TestAnDenEchtenDatenGemessen._messe()


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    """Die Tafel aus dem Kopf, am Lauf nachgeprueft."""

    @staticmethod
    def _messe():
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
        from research.gates import evaluate_gates
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        e = get_settings()
        store = CandleStore(e.paths.data_store)
        versuche = load_trials(Path(e.paths.state) / "trials.json")
        roh = alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        genom = cli._ohne_hebel(spitzenkandidat())
        configs = cli._spotconfigs(symbole, e)

        werte: dict[str, list[float]] = {}
        zweige: dict[str, list[str]] = {}
        gemeldet: dict[str, tuple[float, float]] = {}
        for weg in range(11):
            frames = common_range(
                {s: f.iloc[weg:].reset_index(drop=True) for s, f in roh.items()}
            )
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
            for r in gates.results:
                werte.setdefault(r.name, []).append(float(r.value))
                zweige.setdefault(r.name, []).append(r.bedingung)
                if weg == 0:
                    gemeldet[r.name] = (float(r.value), float(r.threshold))
        return werte, zweige, gemeldet

    def test_neun_sind_entschieden_zwei_nicht(self, tafel) -> None:
        werte, zweige, gemeldet = tafel
        spruch = {
            name: beurteile(
                name=name,
                wert=wert,
                schwelle=schwelle,
                werte=werte[name],
                bedingungen=zweige[name],
            )
            for name, (wert, schwelle) in gemeldet.items()
        }

        assert sum(1 for s in spruch.values() if s == ENTSCHIEDEN) == 9
        assert spruch["Schlechtestes Jahr"] == OFFEN
        assert spruch["Messlatte"] == ZWEI_GROESSEN

    def test_der_deflated_sharpe_gehoert_zu_den_entschiedenen(self, tafel) -> None:
        """Das Wichtigste daran: Der Hauptblocker ist keine
        Aufteilungsfrage."""
        werte, zweige, gemeldet = tafel
        wert, schwelle = gemeldet["Deflated Sharpe"]

        assert (
            beurteile(
                name="Deflated Sharpe",
                wert=wert,
                schwelle=schwelle,
                werte=werte["Deflated Sharpe"],
                bedingungen=zweige["Deflated Sharpe"],
            )
            == ENTSCHIEDEN
        )
        assert abs(wert - schwelle) == pytest.approx(0.3674, abs=0.001)

    def test_und_bestaendigkeit_ist_die_knappste(self, tafel) -> None:
        from research.aufteilung import streuung

        werte, _, gemeldet = tafel
        wert, schwelle = gemeldet["Bestaendigkeit"]
        s = streuung("Bestaendigkeit", werte["Bestaendigkeit"])

        assert abs(wert - schwelle) == pytest.approx(0.0806, abs=0.001)
        assert s.spanne == pytest.approx(0.0645, abs=0.001)
        assert 1.0 < abs(wert - schwelle) / s.spanne < 1.5

    def test_zwei_gates_bewegen_sich_gar_nicht(self, tafel) -> None:
        from research.aufteilung import streuung

        werte, _, _ = tafel

        for name in ("Kosten-Stress", "Parameter-Plateau"):
            assert streuung(name, werte[name]).spanne == 0.0, name


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_neun(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 401)

        assert "Neun der elf sind" in eintrag.ergebnis
        assert "Viereinhalbfache" in eintrag.ergebnis

    def test_und_dass_die_sorge_begrenzt_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 401)

        assert "begrenzt statt bestaetigt" in eintrag.ergebnis

    def test_und_die_beiden_offenen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 401)

        assert "0,3900" in eintrag.ergebnis
        assert "0,9500" in eintrag.ergebnis
        assert "395 bis 397" in eintrag.ergebnis

    def test_und_die_naechste_stelle(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 401)

        assert "1,25-fache" in eintrag.ergebnis
        assert "als naechstes nachzusehen" in eintrag.ergebnis

    def test_und_400_zeigt_nach_vorn(self) -> None:
        """Auf 401 zunaechst, seit Befund 403 auf diesen - derselbe Eintrag,
        zweimal weitergezogen."""
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 400).zuletzt == 403
