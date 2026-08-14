"""Der Weg vom Vorschlag in die Messung.

Der Analyst war gebaut und getestet, die Gates waren gebaut und getestet -
zwischen beiden lag nichts. Diese Datei prueft die Verbindung, und zwar an
der Stelle, an der sie beim Bauen tatsaechlich falsch war: Der Adapter, der
ein Laufergebnis in die Form der Bestenliste bringt, war im ersten Anlauf mit
den falschen Feldnamen geschrieben. Er lief trotzdem an - bis zum ersten
echten Lauf.

Was hier ausdruecklich **nicht** geprueft wird: ob ein Vorschlag gut ist. Das
entscheiden die elf Gates, und die haben ihre eigenen Tests.
"""

from __future__ import annotations

from cli import _kandidat_aus_lauf
from research.gates import GateReport, GateResult, GateStatus
from research.seeds import spitzenkandidat


class FakeMetrics:
    sharpe = 1.42
    expectancy_r = 0.31
    total_return_pct = 88.0
    max_drawdown_pct = 12.5


class FakeReport:
    """Ein Portfolio-Walk-Forward-Bericht, so weit die Bestenliste ihn liest."""

    def __init__(self, trades: list) -> None:
        self.all_trades = trades
        self.combined = FakeMetrics()
        self.consistency = 0.6


def gate(name: str, *, passed: bool) -> GateResult:
    return GateResult(
        name=name,
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        value=1.0,
        threshold=0.5,
        message="",
    )


class TestDerAdapter:
    def test_das_laufergebnis_kommt_vollstaendig_an(self) -> None:
        """Der Kandidat traegt den Bericht, nicht eine Zusammenfassung davon.

        Die Bestenliste rechnet aus ``walkforward.all_trades`` die Form der
        Verteilung nach - Schiefe und Woelbung gehen in den Deflated Sharpe
        ein. Wer hier nur die Kennzahlen durchreicht, verliert sie stillschweigend.
        """
        genome = spitzenkandidat()
        bericht = FakeReport(trades=[object(), object(), object()])

        kandidat = _kandidat_aus_lauf(
            genome, bericht, GateReport(genome_id=genome.genome_id, results=[])
        )

        assert kandidat.genome is genome
        assert kandidat.walkforward is bericht
        assert kandidat.trades == 3
        assert kandidat.sharpe == 1.42

    def test_ein_gescheiterter_vorschlag_ist_nicht_zugelassen(self) -> None:
        genome = spitzenkandidat()
        gates = GateReport(
            genome_id=genome.genome_id,
            results=[gate("Deflated Sharpe", passed=False), gate("Drawdown", passed=True)],
        )

        kandidat = _kandidat_aus_lauf(genome, FakeReport([]), gates)

        assert not kandidat.admitted
        assert [r.name for r in kandidat.gates.failures] == ["Deflated Sharpe"]

    def test_die_bestenliste_nimmt_ihn_wie_jeden_anderen(self, tmp_path) -> None:
        """**Die Herkunft steht dran, sie wiegt aber nichts.**

        Ein Vorschlag aus einem Modell landet in derselben Liste, nach
        denselben Regeln sortiert, wie eine Variante aus der Mutation. Alles
        andere waere eine Bevorzugung - und zwar der Quelle, nicht des
        Ergebnisses.
        """
        from research.leaderboard import Leaderboard

        genome = spitzenkandidat()
        board = Leaderboard(tmp_path / "board.json")
        gates = GateReport(
            genome_id=genome.genome_id, results=[gate("Drawdown", passed=True)]
        )

        board.record(
            [_kandidat_aus_lauf(genome, FakeReport([]), gates)],
            generation=0,
            herkunft="Vorschlag (antwort.json)",
            versuche=161,
        )

        eintrag = board.entries[genome.genome_id]
        assert eintrag.herkunft == "Vorschlag (antwort.json)"
        assert eintrag.versuche == 161, (
            "Ohne den Versuchsstand ist der Deflated Sharpe des Eintrags mit "
            "keinem anderen vergleichbar"
        )
