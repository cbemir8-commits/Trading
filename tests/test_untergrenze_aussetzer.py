"""Setzt mehr aus, als die Trade-Zahl verraet? - Befund 477.

Der Registereintrag 332 traegt seit Befund 352 die Zeile *"Kein Typ steht mehr
offen"* und darunter, was offen bleibt - woertlich:

    Acht der sechzehn erschliessen nur eine **Untergrenze** - 'run_expensive'
    aus oder eine feste Periode setzt mehr aus, als die Trade-Zahl verraet.

Beide genannten Ursachen sind hier gemessen, und beide treffen auf dem
heutigen Stand **nicht** zu.

``run_expensive`` aus
---------------------
Gemessen am Spitzenkandidaten, Spot-Punkt, 158 Trades, 203 Versuche:

    run_expensive=True    11 Urteile   9 bestanden   0 uebersprungen   9/11
    run_expensive=False    9 Urteile   7 bestanden   0 uebersprungen   7/9

Die teuren Gates werden also nicht **uebersprungen**, sondern **weggelassen**:
Der Nenner faellt von elf auf neun, und der Bericht traegt ``vorauswahl``,
womit ``passed`` schon durch die Bauart falsch ist. Es wird damit kein Gate
mitgezaehlt, das nicht geurteilt hat - die Untergrenze liegt hier nicht zu
tief, weil es nichts zu tief zu liegen gibt.

Keine variierbare Periode
-------------------------
Das ist die zweite genannte Ursache, und sie ist eine Eigenschaft des Genoms,
nicht des Laufs: ``gate_parameter_plateau`` setzt aus, wenn
``nachbarschaft(genome, variation)`` leer ist. Gemessen ueber **53**
verschiedene Genome aller Generationen: **keines** ist leer, und der
Spitzenkandidat hat zwoelf Nachbarn.

Damit ist die Lage eine **Bedingung** und kein Fund - genau die Form, in der
Befund 332 seine eigenen Teilergebnisse fuehrt. Die zwei Tests unten halten
sie: Kommt ein Genom ohne variierbare Periode in den Katalog, oder faengt
``run_expensive=False`` an, Gates als uebersprungen zu fuehren statt sie
weglassen, dann wird die Untergrenze wirklich zu tief - und das faellt hier
auf.

**Offen bleibt die andere Haelfte** und zwar unberuehrt: die 554 Berichte, die
vor Befund 348 geschrieben wurden und ihre rohen Paare weitertragen, darunter
109 mit null Trades. Daran aendert diese Messung nichts.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

#: Die Variation, mit der das Gate seine Nachbarschaft bildet (``gates.py``).
#:
#: Steht hier als Zahl, weil ``GateThresholds`` sie nicht traegt - sie ist ein
#: Vorgabewert der Gate-Funktion. Ein Test, der sie selbst setzt, wuerde etwas
#: anderes messen als der Lauf; deshalb prueft
#: ``test_die_variation_ist_die_des_gates`` sie gegen die Signatur.
VARIATION = 0.2


def _genome() -> list:
    """Jedes Genom aller Generationen, einmal je Name."""
    from research.seeds import GENERATIONS

    gesehen: dict[str, object] = {}
    for eintraege in GENERATIONS.values():
        for eintrag in eintraege:
            genom = eintrag() if callable(eintrag) else eintrag
            gesehen.setdefault(genom.name, genom)
    return list(gesehen.values())


class TestKeinGenomOhneVariierbarePeriode:
    """Die eine Ursache - und sie ist am Katalog messbar, ohne Backtest."""

    def test_die_variation_ist_die_des_gates(self) -> None:
        """Sonst messe ich eine andere Nachbarschaft als der Lauf."""
        import inspect

        from research.gates import gate_parameter_plateau

        vorgabe = inspect.signature(gate_parameter_plateau).parameters["variation"]

        assert vorgabe.default == VARIATION

    def test_jedes_katalog_genom_hat_nachbarn(self) -> None:
        from research.gates import nachbarschaft

        genome = _genome()
        ohne = [
            g.name for g in genome if not list(nachbarschaft(g, VARIATION))
        ]

        assert len(genome) >= 50, f"nur {len(genome)} Genome - zu wenig geprueft"
        assert ohne == [], (
            f"diese Genome setzen 'Parameter-Plateau' aus, ohne dass die "
            f"Trade-Zahl es verraet: {ohne}"
        )

    def test_der_spitzenkandidat_auch(self) -> None:
        from research.gates import nachbarschaft
        from research.seeds import spitzenkandidat

        assert len(list(nachbarschaft(spitzenkandidat(), VARIATION))) == 12

    def test_der_aussetzzweig_ist_erreichbar(self) -> None:
        """Die Gegenprobe: Waere der Zweig toter Code, sagte der Test darueber
        nichts. Geprueft wird er an der echten Gate-Funktion, mit leerer
        Nachbarschaft - alles davor und danach bleibt, wie es ist.
        """
        from research.gates import GateStatus, GateThresholds, gate_parameter_plateau
        from research.seeds import spitzenkandidat

        with patch("research.gates.nachbarschaft", return_value=iter(())):
            ergebnis = gate_parameter_plateau(
                spitzenkandidat(), None, None, GateThresholds()
            )

        assert ergebnis.status is GateStatus.SKIP
        assert "keine variierbaren Perioden" in ergebnis.message

    def test_und_die_untergrenze_kennt_diesen_grund_nicht(self) -> None:
        """Der Kern der offenen Zeile: ``erschlossen_bei`` sieht nur die
        Trade-Zahl, also kann sie diesen Aussetzer nicht nennen."""
        from research.gatebilanz import erschlossen_bei

        assert "Parameter-Plateau" not in erschlossen_bei(5)
        assert "Parameter-Plateau" not in erschlossen_bei(158)


@pytest.mark.daten
@pytest.mark.langsam
class TestRunExpensiveLaesstWegStattZuUeberspringen:
    """Die andere Ursache, am echten Lauf - und sie trifft nicht zu."""

    def test_ohne_die_teuren_gates_faellt_der_nenner(self) -> None:
        from research.gatebilanz import erschlossen_bei
        from research.gates import GateStatus

        mit, ohne = _laeufe()

        assert len(mit.results) == 11
        assert len(ohne.results) == 9, [r.name for r in ohne.results]
        for bericht in (mit, ohne):
            ausgesetzt = [
                r.name for r in bericht.results if r.status is GateStatus.SKIP
            ]
            assert ausgesetzt == [], ausgesetzt
        assert _trades() >= 30, "unter 30 waere die Untergrenze selbst nicht leer"
        assert erschlossen_bei(_trades()) == ()

    def test_und_der_kurze_bericht_ist_als_vorauswahl_markiert(self) -> None:
        """Ohne diese Flagge waere '7 von 9' eine Bilanz wie jede andere."""
        mit, ohne = _laeufe()

        assert not mit.vorauswahl
        assert ohne.vorauswahl
        assert not ohne.passed


_LAUF: dict[str, object] = {}


def _trades() -> int:
    _laeufe()
    return int(_LAUF["trades"])  # type: ignore[call-overload]


def _laeufe():
    """Beide Gate-Berichte, einmal gerechnet.

    Als Modulfunktion mit Zwischenspeicher und **nicht** als Fixture mit
    Klassenbindung - eine solche faellt hier in ``assert not
    self._finalizers`` (Befund 426/429, in dieser Sitzung dreimal gesehen).
    """
    if "mit" in _LAUF:
        return _LAUF["mit"], _LAUF["ohne"]

    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
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
    if any(f.empty for f in frames.values()):
        pytest.skip("keine Tageskerzen im Speicher")
    configs = cli._spotconfigs(symbole, e)
    genom = cli._ohne_hebel(spitzenkandidat())
    lauf = run_portfolio_walkforward(frames, lambda g=genom: compile_genome(g), configs)
    versuche = load_trials(Path(e.paths.state) / "trials.json")

    def gates(*, teuer: bool):
        return evaluate_gates(
            genom, lauf, frames[symbole[0]], configs[symbole[0]],
            trials_so_far=versuche, thresholds=GateThresholds(),
            frames=frames, configs=configs, run_expensive=teuer,
        )

    _LAUF["trades"] = len(lauf.all_trades)
    _LAUF["mit"] = gates(teuer=True)
    _LAUF["ohne"] = gates(teuer=False)
    return _LAUF["mit"], _LAUF["ohne"]
