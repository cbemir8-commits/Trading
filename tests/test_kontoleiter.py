"""Die Kontoleiter und ihr Deflated Sharpe - Befund 338.

Dritter Verdachtsfall aus der Wache von Befund 335: **'Kontogroesse'**,
Fundstelle Befund 95/96, spaeter in 98, 100, 102 und 126 erwaehnt.

Fuenf Zahlen des Eintrags stimmen auf die Stelle:

    Rueckgang bei    300 Euro     9,92 %
    Rueckgang bei 100.000 Euro   12,95 %
    Kippgrenze des Gates         rund 1150 Euro
    Bilanz unten                 8 von 11
    Bilanz ab 1500 Euro          6 von 11

Die **Aussage** ueber den Deflated Sharpe stimmt auch: Er wandert ueber einen
333-fachen Kontobereich nur um 0,0224 und ist damit einer der neun, die
stillstehen, waehrend Rueckgang und schlechtestes Jahr wandern.

Sein **Wert** ist ueberholt. Der Eintrag nennt 0,772 bis 0,786; gemessen sind es
**0,4579 bis 0,4803**. Die alten Zahlen stammen von vor Befund 135 - die
Quartalseinteilung senkte die wirksame Stichprobe von 152 auf 112 - und von
einem niedrigeren Versuchsstand; heute sind es 203.

Dazu eine der Fragen aus Befund 332: ``koernung.Gatewert`` konnte nicht sagen, ob
ein Gate geurteilt hat. Hier ist das naherliegend, denn diese Leiter bewegt die
Trade-Zahl wirklich - auf der untersten Sprosse sind es 152 statt 158, weil die
Mindestmenge der Boerse Einstiege verhindert. **Gemessen bleibt es ueber alle
Sprossen bei elf Urteilen**: 152 liegt weit ueber der Aussetzschwelle von 30.
"""

from __future__ import annotations

import pytest

from research.koernung import Gatelauf, Gatewert

#: Der Kontobereich und was er liefert (Befund 338, Perpetual-Punkt).
GEMESSEN: tuple[tuple[int, int, float, float, int], ...] = (
    # Konto, Trades, DSR, Rueckgang, bestandene Gates
    (300, 152, 0.4803, 9.92, 8),
    (500, 158, 0.4579, 10.64, 7),
    (1500, 158, 0.4729, 12.36, 6),
    (10000, 158, 0.4730, 12.84, 6),
    (100000, 158, 0.4723, 12.95, 6),
)


class TestGatelaufZaehltJetztEhrlich:
    def test_ein_ausgesetztes_gate_zaehlt_nicht_als_bestanden(self) -> None:
        lauf = Gatelauf(
            kapital=300.0,
            gates=(
                Gatewert(name="A", bestanden=True, wert=1.0),
                Gatewert(name="B", bestanden=True, wert=1.0, geurteilt=False),
            ),
        )

        assert lauf.bestanden == 1
        assert lauf.gesamt == 1
        assert lauf.ausgesetzt == ("B",)

    def test_ohne_aussetzer_bleibt_alles_wie_vorher(self) -> None:
        lauf = Gatelauf(
            kapital=500.0,
            gates=(
                Gatewert(name="A", bestanden=True, wert=1.0),
                Gatewert(name="B", bestanden=False, wert=0.0),
            ),
        )

        assert (lauf.bestanden, lauf.gesamt) == (1, 2)
        assert lauf.ausgesetzt == ()

    def test_der_vorgabewert_ist_geurteilt(self) -> None:
        """Die sichere Richtung: Wer das Feld nicht setzt, bekommt "hat
        geurteilt" - dann stimmt die Zahl mit der alten ueberein, und ein
        Aussetzer muss ausdruecklich gemeldet werden."""
        assert Gatewert(name="A", bestanden=True, wert=1.0).geurteilt


class TestDerBefehlFuelltEs:
    """Befund 152, 154, 155, 160, 325, 330 und 337 waren dieselbe Bauart:
    gebaut, gerechnet, nicht angeschlossen."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "koernung"
        )

    def test_gatewert_bekommt_geurteilt(self) -> None:
        quelle = self._quelle()

        assert "geurteilt=r.status is not GateStatus.SKIP" in quelle


class TestDerEintragIstNachgemessen:
    @staticmethod
    def _eintrag():
        from research.stand import ENTSCHEIDUNGEN

        return next(e for e in ENTSCHEIDUNGEN if e.frage == "Kontogroesse")

    def test_der_alte_dsr_bereich_ist_als_ueberholt_benannt(self) -> None:
        zahl = self._eintrag().zahl

        assert "0,4579 bis 0,4803" in zahl
        assert "statt 0,772 bis 0,786" in zahl

    def test_der_grund_steht_dabei(self) -> None:
        """Nicht "war falsch", sondern warum er hoeher war: andere Stichprobe,
        weniger Versuche."""
        zahl = self._eintrag().zahl

        assert "Befund 135" in zahl
        assert "203" in zahl

    def test_die_aussage_bleibt_bestehen(self) -> None:
        """Der Deflated Sharpe wandert nicht mit dem Konto - das war der Punkt
        des Eintrags, und er stimmt. Ein Eintrag, der jetzt alles umwuerfe,
        waere die Gegenuebertreibung."""
        zahl = self._eintrag().zahl

        assert "einer der neun stillstehenden" in zahl
        assert "0,0224" in zahl

    def test_die_fuenf_bestaetigten_zahlen_stehen_dabei(self) -> None:
        """Gepruefte Zahlen, die stimmen, gehoeren genauso berichtet wie die
        eine, die nicht stimmte."""
        zahl = self._eintrag().zahl

        assert "Fuenf Zahlen dieses Eintrags stimmen" in zahl

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 95
        assert eintrag.massgeblich == 338


@pytest.mark.daten
@pytest.mark.langsam
def test_die_leiter_stimmt_und_setzt_nirgends_aus() -> None:
    """**Die Bindung.** Der Deflated Sharpe stand zweihundertvierzig Befunde
    lang auf einem Wert von vor Befund 135. Ein Test haette das gefunden.
    """
    from decimal import Decimal
    from pathlib import Path

    import cli
    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import (
        common_range,
        run_portfolio_walkforward,
    )
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.admission import load_trials
    from research.gates import GateStatus, GateThresholds, evaluate_gates
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    e = get_settings()
    frames = common_range(
        {x: CandleStore(e.paths.data_store).read(x, Interval("D")) for x in symbole}
    )
    versuche = load_trials(Path(e.paths.state) / "trials.json")
    genom = spitzenkandidat()
    dsr_werte = []

    for konto, trades, dsr, rueckgang, bestanden in GEMESSEN:
        configs = {
            x: BacktestConfig(
                instrument=cli._fallback_instrument(cli._bybit_kontrakt(x)),
                risk=e.risk,
                initial_equity=Decimal(str(konto)),
                enforce_risk_limits=True,
                kalender=cli._terminkalender(e) or None,
            )
            for x in symbole
        }
        lauf = run_portfolio_walkforward(
            frames, lambda g=genom: compile_genome(g), configs
        )
        gates = evaluate_gates(
            genom,
            lauf,
            frames[symbole[0]],
            configs[symbole[0]],
            trials_so_far=versuche,
            thresholds=GateThresholds(),
            frames=frames,
            configs=configs,
        )
        aus = [r.name for r in gates.results if r.status is GateStatus.SKIP]
        gemessen_dsr = next(
            r.value for r in gates.results if r.name == "Deflated Sharpe"
        )
        dsr_werte.append(gemessen_dsr)

        assert aus == [], f"{konto} EUR: {aus} setzen aus"
        assert len(list(lauf.all_trades)) == trades, konto
        assert gemessen_dsr == pytest.approx(dsr, abs=0.001), konto
        assert next(
            r.value for r in gates.results if r.name == "Drawdown"
        ) == pytest.approx(rueckgang, abs=0.01), konto
        assert sum(1 for r in gates.results if r.passed) == bestanden, konto

    spanne = max(dsr_werte) - min(dsr_werte)

    assert spanne < 0.03, "der Deflated Sharpe soll nicht mit dem Konto wandern"
    assert max(dsr_werte) < 0.6, "und er liegt weit unter den alten 0,77"
