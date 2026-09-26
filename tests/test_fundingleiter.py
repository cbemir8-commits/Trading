"""Die Funding-Leiter, an einen Test gebunden - Befund 337.

Befund 335 hat die Wache auf die Entscheidungen ausgeweitet, 336 den staerksten
Verdacht gelesen. Dies ist der zweite: **'Funding-Satz'**, Fundstelle Befund
250, spaeter viermal in Befund 326.

Der Eintrag nennt die Leiter der Gate-Bilanz ueber sechs Funding-Saetze und sagt,
sie reiche "von 9 von 11 (bei 0 %) bis **3** von 11 (bei 55 %)". ``cli
finanzierung`` rechnet dieselbe Leiter jeden Lauf neu und sagt **2** - ein Gate
schlechter als verzeichnet. Eine Handzahl, die weitergelaufen ist.

    Satz p.a.    Rendite   Rueckgang   Gates
        0.0 %    14.34 %      9.87 %    9/11
        5.5 %    13.64 %     10.25 %    9/11
       10.9 %    12.95 %     10.64 %    7/11   <- Vorgabe
       21.9 %    11.61 %     11.41 %    7/11
       32.8 %    10.25 %     12.17 %    6/11
       54.8 %     7.61 %     13.68 %    2/11

Mitgemessen ist eine der fuenfzehn offenen Fragen aus Befund 332:
``finanzierung.Stufe`` zeigte ``bestanden/gesamt``, und ``passed`` ist wahr,
sobald der Status nicht ``FAIL`` lautet. Hier war das kein Verdacht, sondern der
wahrscheinlichste Fall von allen - die Leiter verschlechtert die Strategie
absichtlich, bis von 14,34 % Rendite 7,61 % bleiben.

**Gemessen setzt auf keiner der sechs Sprossen ein Gate aus.** Funding ist eine
Kosten- und keine Einstiegsgroesse: Die Trade-Zahl bleibt oben, alle elf Gates
urteilen, und ``bestanden_echt/geurteilt`` stimmt mit dem rohen Paar ueberein.
Das Feld ist trotzdem da - damit es auffaellt, wenn sich das aendert.
"""

from __future__ import annotations

import pytest

from research.finanzierung import Stufe

#: Die gemessene Leiter (Befund 337): Satz je Achtstundenperiode -> Gates.
GEMESSEN: tuple[tuple[float, int], ...] = (
    (0.0, 9),
    (0.00005, 9),
    (0.0001, 7),
    (0.0002, 7),
    (0.0003, 6),
    (0.0005, 2),
)


class TestStufeRechnetJetztEhrlich:
    def test_ohne_aussetzer_ist_es_das_alte_paar(self) -> None:
        stufe = Stufe(satz=0.0001, cagr=12.95, rueckgang=10.64, bestanden=7, gesamt=11)

        assert stufe.bestanden_echt == 7
        assert stufe.geurteilt == 11

    def test_ein_aussetzer_zaehlt_auf_beiden_seiten_ab(self) -> None:
        """Er faellt aus dem Zaehler **und** aus dem Nenner: Ein Gate, das nicht
        geurteilt hat, ist weder bestanden noch durchgefallen."""
        stufe = Stufe(
            satz=0.0005,
            cagr=7.61,
            rueckgang=13.68,
            bestanden=4,
            gesamt=11,
            uebersprungen=("Monte-Carlo", "Deflated Sharpe"),
        )

        assert stufe.bestanden_echt == 2
        assert stufe.geurteilt == 9

    def test_mehr_aussetzer_als_bestandene_gibt_nicht_unter_null(self) -> None:
        stufe = Stufe(
            satz=0.0005,
            cagr=0.0,
            rueckgang=0.0,
            bestanden=1,
            gesamt=11,
            uebersprungen=("a", "b", "c"),
        )

        assert stufe.bestanden_echt == 0
        assert stufe.geurteilt == 8

    def test_ohne_angabe_bleibt_das_feld_leer(self) -> None:
        """Ein vorhandenes Feld, das niemand fuellt, waere schlimmer als
        keines - deshalb prueft der Verdrahtungstest unten den Aufrufer."""
        assert Stufe(satz=0.0, cagr=0.0, rueckgang=0.0, bestanden=0, gesamt=11).uebersprungen == ()


class TestDerBefehlFuelltEs:
    """**Die Verdrahtung.** Befund 152, 154, 155, 160, 325 und 330 waren alle
    dieselbe Bauart: gebaut, gerechnet, nicht angeschlossen."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "finanzierung"
        )

    def test_die_stufe_bekommt_uebersprungen(self) -> None:
        assert "uebersprungen=tuple" in self._quelle()

    def test_und_die_anzeige_nennt_die_ehrliche_zahl(self) -> None:
        quelle = self._quelle()

        assert "stufe.bestanden_echt" in quelle
        assert "stufe.geurteilt" in quelle

    def test_das_rohe_paar_steht_nicht_mehr_in_der_zeile(self) -> None:
        quelle = self._quelle()

        assert "{stufe.bestanden}/{stufe.gesamt}" not in quelle
        assert "bestanden=sum(" in quelle, "die Rechnung bleibt"

    def test_ein_aussetzer_wuerde_benannt(self) -> None:
        assert "ohne Urteil" in self._quelle()


class TestDerEintragIstBerichtigt:
    @staticmethod
    def _eintrag():
        from research.stand import ENTSCHEIDUNGEN

        return next(e for e in ENTSCHEIDUNGEN if e.frage == "Funding-Satz")

    def test_die_unterste_sprosse_steht_auf_zwei(self) -> None:
        assert "bis **2** von 11" in self._eintrag().zahl

    def test_und_die_alte_handzahl_ist_weg(self) -> None:
        assert "3 von 11 (bei 55 %)" not in self._eintrag().zahl

    def test_der_eintrag_sagt_dass_nichts_aussetzt(self) -> None:
        assert "keiner** der sechs Sprossen" in self._eintrag().warum

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 250
        assert eintrag.massgeblich == 337


@pytest.mark.daten
@pytest.mark.langsam
def test_die_leiter_stimmt_und_setzt_nirgends_aus() -> None:
    """**Die Bindung.** Wandert eine Sprosse, faellt es hier auf und nicht in
    einer Entscheidung - genau der Fall, der die '3' zwei Befunde lang hat
    ueberleben lassen.
    """
    from decimal import Decimal
    from pathlib import Path

    import cli
    from backtest.costs import FundingSchedule
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

    for satz, erwartet in GEMESSEN:
        # Dieselbe Konfiguration wie 'lauf(satz)' in 'cli finanzierung':
        # Bybit-Kontrakt, 500 EUR, Risikogrenzen an, flacher Funding-Satz.
        configs = {
            x: BacktestConfig(
                instrument=cli._fallback_instrument(cli._bybit_kontrakt(x)),
                risk=e.risk,
                initial_equity=Decimal("500"),
                enforce_risk_limits=True,
                kalender=cli._terminkalender(e) or None,
                funding=FundingSchedule(default_rate=Decimal(str(satz))),
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

        assert aus == [], f"Satz {satz}: {aus} setzen aus"
        assert sum(1 for r in gates.results if r.passed) == erwartet, satz
