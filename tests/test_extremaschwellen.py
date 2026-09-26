"""Die drei Gates auf laufenden Extrema, an beiden Betriebspunkten - Befund 336.

Befund 335 hat die Wache auf die Entscheidungen ausgeweitet. Ihr staerkster
Verdachtsfall war 'Feste Schwellen auf laufenden Extrema' (Fundstelle Befund
162, spaeter achtmal in Befund 310 erwaehnt). Nachgesehen - und der Verdacht
trifft zu.

Der Eintrag nennt drei Zahlen und sagt, 'Schlechtestes Jahr' sei gerissen:

    Drawdown            8,29 -> 10,64   Schwelle 12,00
    Schlechtestes Jahr  5,97 -> -10,32  Schwelle -10,00
    Monte-Carlo         7,83 ->   9,69  Schwelle 15,00

Gemessen an beiden Punkten:

                          Spot        Perpetual   Schwelle
    Drawdown             9,87  PASS   10,64  PASS   12,00
    Schlechtestes Jahr  -9,61  PASS  -10,32  FAIL  -10,00
    Monte-Carlo          8,33  PASS    9,69  PASS   15,00

**Die drei Zahlen des Eintrags sind die Perpetual-Zahlen** - auf die zweite
Stelle genau. Befund 162 liegt vor Befund 311, der den Betriebspunkt eingefuehrt
hat, und der Eintrag nannte keinen. Am **Spot**-Punkt, den ``referenz`` den
massgeblichen nennt, ist keines der drei gerissen.

Dieselbe Bauart wie Befund 316/317: eine Zahl unter einem Kopf, der ihren
Betriebspunkt nicht nennt. Nur diesmal in einer offenen Entscheidung, und
gefunden von der Wache aus 335 - einen Zyklus nachdem sie gebaut wurde.

Was **nicht** falsch war: die Richtung. Alle drei Werte wachsen mit der
Historie, und ein Maximum kann nicht fallen. Was am Betriebspunkt haengt, ist
die Dringlichkeit - 'Schlechtestes Jahr' hat am Spot-Punkt 0,39 Reserve statt
gar keiner, der Rueckgang 2,13 statt 1,36.
"""

from __future__ import annotations

import pytest

#: Die drei Gates, die ein laufendes Extrem messen - und was sie an welchem
#: Punkt liefern. Gemessen in Befund 336, zwei Stellen nach dem Komma.
GEMESSEN: dict[str, tuple[float, float, float]] = {
    # Gate: (Spot, Perpetual, Schwelle)
    "Drawdown": (9.87, 10.64, 12.00),
    "Schlechtestes Jahr": (-9.61, -10.32, -10.00),
    "Monte-Carlo": (8.33, 9.69, 15.00),
}


def _gates(punkt: str):
    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import (
        common_range,
        run_portfolio_walkforward,
    )
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.admission import load_trials
    from research.gates import GateThresholds, evaluate_gates
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    e = get_settings()
    frames = common_range(
        {x: CandleStore(e.paths.data_store).read(x, Interval("D")) for x in symbole}
    )
    if punkt == "Spot":
        configs = cli._spotconfigs(symbole, e)
        genom = cli._ohne_hebel(spitzenkandidat())
    else:
        from decimal import Decimal

        from backtest.engine import BacktestConfig

        configs = {
            x: BacktestConfig(
                instrument=cli._fallback_instrument(cli._bybit_kontrakt(x)),
                risk=e.risk,
                initial_equity=Decimal("500"),
                enforce_risk_limits=True,
                kalender=cli._terminkalender(e) or None,
            )
            for x in symbole
        }
        genom = spitzenkandidat()
    lauf = run_portfolio_walkforward(
        frames, lambda g=genom: compile_genome(g), configs
    )
    return evaluate_gates(
        genom,
        lauf,
        frames[symbole[0]],
        configs[symbole[0]],
        trials_so_far=load_trials(Path(e.paths.state) / "trials.json"),
        thresholds=GateThresholds(),
        frames=frames,
        configs=configs,
    )


@pytest.fixture(scope="module")
def spot():
    return _gates("Spot")


@pytest.fixture(scope="module")
def perpetual():
    return _gates("Perpetual")


def _wert(gates, name: str) -> float:
    return next(r.value for r in gates.results if r.name == name)


def _status(gates, name: str) -> str:
    return next(r.status.name for r in gates.results if r.name == name)


@pytest.mark.daten
@pytest.mark.langsam
@pytest.mark.parametrize("gate", sorted(GEMESSEN))
def test_der_spot_wert_steht(spot, gate) -> None:
    assert _wert(spot, gate) == pytest.approx(GEMESSEN[gate][0], abs=0.01)


@pytest.mark.daten
@pytest.mark.langsam
@pytest.mark.parametrize("gate", sorted(GEMESSEN))
def test_der_perpetual_wert_steht(perpetual, gate) -> None:
    assert _wert(perpetual, gate) == pytest.approx(GEMESSEN[gate][1], abs=0.01)


@pytest.mark.daten
@pytest.mark.langsam
def test_am_spot_punkt_ist_keines_der_drei_gerissen(spot) -> None:
    """**Der Kern von Befund 336.** Der Eintrag sagte "gerissen", und das gilt
    nur am anderen Punkt."""
    for gate in GEMESSEN:
        assert _status(spot, gate) == "PASS", gate


@pytest.mark.daten
@pytest.mark.langsam
def test_am_perpetual_punkt_reisst_das_schlechteste_jahr(perpetual) -> None:
    """Und dort stimmt der Satz - deshalb ist der Eintrag nicht falsch, sondern
    ohne Betriebspunkt."""
    assert _status(perpetual, "Schlechtestes Jahr") == "FAIL"
    assert _status(perpetual, "Drawdown") == "PASS"
    assert _status(perpetual, "Monte-Carlo") == "PASS"


@pytest.mark.daten
@pytest.mark.langsam
def test_die_reserve_des_rueckgangs_unterscheidet_sich(spot, perpetual) -> None:
    """Der Eintrag argumentiert mit "noch 1,36 Reserve". Am Spot-Punkt sind es
    2,13 - 57 % mehr, und damit traegt das Argument dort schwaecher."""
    schwelle = GEMESSEN["Drawdown"][2]

    reserve_spot = schwelle - _wert(spot, "Drawdown")
    reserve_perp = schwelle - _wert(perpetual, "Drawdown")

    assert reserve_perp == pytest.approx(1.36, abs=0.01)
    assert reserve_spot == pytest.approx(2.13, abs=0.01)
    assert reserve_spot / reserve_perp > 1.5


class TestDerEintragNenntJetztBeidePunkte:
    @staticmethod
    def _eintrag() -> str:
        from research.stand import ENTSCHEIDUNGEN

        return next(
            e.zahl for e in ENTSCHEIDUNGEN
            if e.frage == "Feste Schwellen auf laufenden Extrema"
        )

    def test_er_sagt_welche_zahlen_die_alten_sind(self) -> None:
        assert "Perpetual-Zahlen" in self._eintrag()

    def test_und_zeigt_beide_spalten(self) -> None:
        eintrag = self._eintrag()

        assert "Spot" in eintrag and "Perpetual" in eintrag
        for zahl in ("9,87", "-9,61", "8,33"):
            assert zahl in eintrag, zahl

    def test_er_berichtigt_die_aussage_ueber_das_reissen(self) -> None:
        assert "keines der drei gerissen" in self._eintrag()

    def test_und_haelt_die_richtung_aufrecht(self) -> None:
        """Nicht der Befund war falsch, nur die fehlende Angabe. Ein Eintrag,
        der jetzt "alles in Ordnung" sagte, waere die Gegenuebertreibung."""
        eintrag = self._eintrag()

        assert "Richtung des Befundes steht unveraendert" in eintrag
        assert "wachsen mit der Historie" in eintrag

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        from research.stand import ENTSCHEIDUNGEN

        e = next(
            x for x in ENTSCHEIDUNGEN
            if x.frage == "Feste Schwellen auf laufenden Extrema"
        )

        assert e.befund == 162
        assert e.massgeblich == 336
