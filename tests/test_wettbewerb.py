"""Tests fuer Bestenliste, Variantenbildung und die Anzeige davon.

Der Dauerlauf hat eine Eigenschaft, die ihn gefaehrlich macht: Er hoert nicht
von selbst auf, und er findet garantiert **irgendwann** etwas, das im Rueckblick
gut aussieht. Genau dagegen ist die Mehrfachtest-Korrektur gebaut, und deshalb
steht hier ein Test, der prueft, dass jede Variante als Versuch zaehlt.

Der zweite wichtige Punkt: Die Bestenliste darf ein gutes Ergebnis nie durch ein
spaeteres schlechteres ersetzen. Sonst haengt es an der Reihenfolge der Laeufe,
was oben steht - und die Liste waere wertlos.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

import pytest

from research.leaderboard import Leaderboard
from research.mutation import breed, mutate
from research.seeds import load_seeds
from strategy.compiler import compile_genome
from strategy.genome import Genome


# ---------------------------------------------------------------------------
#  Ein schlanker Ersatz fuer Candidate - hier wird die Liste geprueft,
#  nicht die Zulassungsstrecke.
# ---------------------------------------------------------------------------
@dataclass
class FakeMetrics:
    expectancy_r: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0


@dataclass
class FakeWalk:
    combined: FakeMetrics | None = None
    all_trades: list = None  # type: ignore[assignment]


@dataclass
class FakeGate:
    name: str
    passed: bool
    wert: float = 0.0

    @property
    def value(self) -> float:
        return self.wert


@dataclass
class FakeGates:
    results: list

    @property
    def failures(self):
        return [r for r in self.results if not r.passed]


@dataclass
class FakeCandidate:
    genome: Genome
    walkforward: FakeWalk
    gates: FakeGates
    admitted: bool
    trades: int = 0
    sharpe: float = 0.0
    consistency: float = 0.0


def kandidat(
    genome: Genome,
    *,
    bestanden: int = 3,
    gesamt: int = 9,
    erwartung: float = 0.0,
    zugelassen: bool = False,
    trades: int = 120,
    deflated: float = 0.0,
) -> FakeCandidate:
    gates = [FakeGate(f"Gate {i}", i < bestanden) for i in range(gesamt)]
    # Der Deflated Sharpe steht als eigenes Gate in der Liste - genau dort
    # liest ihn die Bestenliste ab.
    gates.append(FakeGate("Deflated Sharpe", deflated >= 0.95, wert=deflated))
    return FakeCandidate(
        genome=genome,
        walkforward=FakeWalk(combined=FakeMetrics(expectancy_r=erwartung)),
        gates=FakeGates(results=gates),
        admitted=zugelassen,
        trades=trades,
    )


@pytest.fixture
def genome() -> Genome:
    return load_seeds(7)[0]


@pytest.fixture
def board(tmp_path: Path) -> Leaderboard:
    return Leaderboard(tmp_path / "leaderboard.json")


# ---------------------------------------------------------------------------
#  Bestenliste
# ---------------------------------------------------------------------------
class TestBestenliste:
    def test_traegt_ein_und_sortiert(self, board: Leaderboard) -> None:
        seeds = load_seeds(7)
        board.record(
            [
                kandidat(seeds[0], bestanden=3, erwartung=-0.2),
                kandidat(seeds[1], bestanden=7, erwartung=-0.1),
                kandidat(seeds[2], bestanden=5, erwartung=0.3),
            ],
            generation=7,
        )

        rang = board.ranked()
        assert [e.gates_bestanden for e in rang] == [7, 5, 3]

    def test_zugelassen_steht_immer_oben(self, board: Leaderboard) -> None:
        """Auch wenn ein anderer mehr Gates bestanden haette.

        Zugelassen heisst: alle Gates. Ein Kandidat mit acht von neun ist nicht
        "fast zugelassen", sondern abgelehnt - und gehoert darunter.
        """
        seeds = load_seeds(7)
        board.record(
            [
                kandidat(seeds[0], bestanden=8, gesamt=9, erwartung=0.9),
                kandidat(seeds[1], bestanden=9, gesamt=9, erwartung=0.1,
                         zugelassen=True),
            ],
            generation=7,
        )

        assert board.ranked()[0].zugelassen

    def test_schlechteres_ergebnis_ueberschreibt_nicht(
        self, board: Leaderboard, genome: Genome
    ) -> None:
        """Sonst haengt es an der Reihenfolge der Laeufe, was oben steht.

        Dieselbe Strategie liefert je nach Zeitraum unterschiedliche Zahlen.
        Die Liste soll festhalten, was eine Idee **kann** - nicht, was sie
        beim letzten Mal zufaellig gemacht hat.
        """
        board.record([kandidat(genome, bestanden=7, erwartung=0.4)], generation=7)
        board.record([kandidat(genome, bestanden=2, erwartung=-0.9)], generation=7)

        eintrag = board.ranked()[0]
        assert eintrag.gates_bestanden == 7
        assert eintrag.erwartung_r == pytest.approx(0.4)
        assert eintrag.geprueft == 2, "Der Zaehler muss trotzdem hochgehen"

    def test_besseres_ergebnis_ersetzt(
        self, board: Leaderboard, genome: Genome
    ) -> None:
        board.record([kandidat(genome, bestanden=2, erwartung=-0.5)], generation=7)
        board.record([kandidat(genome, bestanden=6, erwartung=0.2)], generation=7)

        assert board.ranked()[0].gates_bestanden == 6

    def test_ueberlebt_den_neustart(self, tmp_path: Path, genome: Genome) -> None:
        pfad = tmp_path / "leaderboard.json"
        erste = Leaderboard(pfad)
        erste.record([kandidat(genome, bestanden=5, erwartung=0.1)], generation=7)
        erste.save()

        zweite = Leaderboard(pfad)

        assert len(zweite.entries) == 1
        assert zweite.laeufe == 1
        assert zweite.ranked()[0].gates_bestanden == 5

    def test_kaputte_datei_faengt_neu_an_statt_abzustuerzen(
        self, tmp_path: Path
    ) -> None:
        """Ein abgebrochener Schreibvorgang darf den Dauerlauf nicht beenden."""
        pfad = tmp_path / "leaderboard.json"
        pfad.write_text("{kaputt")

        board = Leaderboard(pfad)

        assert board.entries == {}

    def test_altes_format_wird_nicht_falsch_gedeutet(self, tmp_path: Path) -> None:
        pfad = tmp_path / "leaderboard.json"
        pfad.write_text(json.dumps({"format": 1, "eintraege": [{"name": "alt"}]}))

        board = Leaderboard(pfad)

        assert board.entries == {}

    def test_zusammenfassung_nennt_die_spitze(
        self, board: Leaderboard, genome: Genome
    ) -> None:
        board.record([kandidat(genome, bestanden=6, erwartung=0.15)], generation=7)

        text = board.summary()
        assert genome.name in text
        assert "6/10" in text  # neun Gates plus Deflated Sharpe


# ---------------------------------------------------------------------------
#  Varianten
# ---------------------------------------------------------------------------
class TestVarianten:
    def test_variante_ist_gueltig_und_anders(self, genome: Genome) -> None:
        variante = mutate(genome, random.Random(1))

        assert variante is not None
        assert variante.genome_id != genome.genome_id
        # Muss uebersetzbar sein - sonst faellt es erst mitten im Lauf auf.
        assert compile_genome(variante).warmup_bars > 0

    def test_aendert_nur_eine_sache(self, genome: Genome) -> None:
        """Sonst laesst sich aus einem besseren Ergebnis nichts ablesen.

        Wer fuenf Dinge gleichzeitig verstellt und danach ein besseres Bild
        bekommt, weiss nicht welches davon gewirkt hat - und hat meistens nur
        das Rauschen besser getroffen.
        """
        for seed in range(25):
            variante = mutate(genome, random.Random(seed))
            if variante is None:
                continue

            unterschiede = sum(
                1
                for feld in (
                    "entry_long", "entry_short", "filters", "exit_long",
                    "exit_short", "stop", "targets", "cooldown_bars",
                    "max_hold_bars",
                )
                if getattr(variante, feld) != getattr(genome, feld)
            )
            assert unterschiede == 1, (
                f"Saat {seed}: {unterschiede} Aenderungen statt einer"
            )

    def test_breed_liefert_lauter_verschiedene(self, genome: Genome) -> None:
        """Zwei identische Regelwerke waeren derselbe Versuch.

        Sie wuerden aber zweimal gezaehlt und die Huerde fuer alle anderen
        unnoetig anheben - die Mehrfachtest-Korrektur bestraft dann fuer
        Arbeit, die gar nicht stattgefunden hat.
        """
        basis = load_seeds(7)
        varianten = breed(basis, 15, seed=3)

        ids = [g.genome_id for g in varianten]
        assert len(ids) == len(set(ids))
        assert not set(ids) & {g.genome_id for g in basis}

    def test_breed_ist_reproduzierbar(self) -> None:
        basis = load_seeds(7)

        a = [g.genome_id for g in breed(basis, 6, seed=42)]
        b = [g.genome_id for g in breed(basis, 6, seed=42)]

        assert a == b

    def test_alle_varianten_kompilieren(self) -> None:
        for variante in breed(load_seeds(7), 30, seed=11):
            assert compile_genome(variante).warmup_bars > 0

    def test_ohne_grundlage_keine_varianten(self) -> None:
        assert breed([], 5) == []


# ---------------------------------------------------------------------------
#  Anzeige
# ---------------------------------------------------------------------------
class TestWebAnzeige:
    def test_endpunkt_liefert_die_rangfolge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi.testclient import TestClient

        from core.config import Settings
        from web.api import create_app

        state = tmp_path / "state"
        state.mkdir()
        board = Leaderboard(state / "leaderboard.json")
        seeds = load_seeds(7)
        board.record(
            [
                kandidat(seeds[0], bestanden=3, erwartung=-0.2),
                kandidat(seeds[1], bestanden=7, erwartung=-0.05),
            ],
            generation=7,
        )
        board.save()

        settings = Settings()
        settings.paths.state = str(state)
        client = TestClient(create_app(settings))

        daten = client.get("/api/wettbewerb").json()

        assert daten["geprueft"] == 2
        assert [e["platz"] for e in daten["eintraege"]] == [1, 2]
        assert daten["eintraege"][0]["gates_bestanden"] == 7

    def test_leere_liste_ist_kein_fehler(self, tmp_path: Path) -> None:
        from fastapi.testclient import TestClient

        from core.config import Settings
        from web.api import create_app

        settings = Settings()
        settings.paths.state = str(tmp_path)
        client = TestClient(create_app(settings))

        antwort = client.get("/api/wettbewerb")

        assert antwort.status_code == 200
        assert antwort.json()["eintraege"] == []


class TestHistorienSchranke:
    """Der Fehler, der drei Runden Rechenzeit in eine leere Tabelle steckte."""

    def test_zu_kurze_historie_bricht_ab(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lieber ein Abbruch als eine Bestenliste voller Nullen.

        Bei 416 Tagen Historie ergibt der Walk-Forward mit 12 Monaten Training
        und 3 Monaten Test kein einziges Fenster. Der Lauf lief trotzdem
        fehlerfrei durch, bildete Varianten und fuellte die Rangliste - jeder
        Eintrag mit null Trades. Das sah nach Ergebnis aus und war keins.
        """
        from datetime import UTC, datetime, timedelta
        from decimal import Decimal

        from typer.testing import CliRunner

        import cli as cli_module
        from core.config import get_settings
        from core.models import Candle, Interval
        from data.store import CandleStore

        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()

        t0 = datetime(2025, 1, 1, tzinfo=UTC)
        candles = [
            Candle(
                symbol="BTCUSDT",
                interval=Interval.M15,
                open_time=t0 + timedelta(minutes=15 * i),
                open=Decimal("30000"),
                high=Decimal("30010"),
                low=Decimal("29990"),
                close=Decimal("30000"),
                volume=Decimal("100"),
                turnover=Decimal("100"),
            )
            # 100 Tage - deutlich zu wenig fuer ein Fenster.
            for i in range(100 * 96)
        ]
        CandleStore(get_settings().paths.data_store).write(
            "BTCUSDT", Interval.M15, candles
        )

        result = CliRunner().invoke(cli_module.app, ["wettbewerb", "--runden", "1"])
        get_settings.cache_clear()

        assert result.exit_code == 2
        assert "Tage Historie" in result.output


# ---------------------------------------------------------------------------
#  Die Bausteine des Abfolge-Modells
# ---------------------------------------------------------------------------
class TestAbfolgeBausteine:
    """Ein von Hand gebauter Fall, in dem jedes Ereignis an bekannter Stelle sitzt.

    Auf zufaelligen Testkerzen kommen Preisluecken kaum vor - ein Test darauf
    wuerde gruen sein, ohne etwas geprueft zu haben. Deshalb steht hier eine
    Reihe, in der Luecke, Abgriff und Strukturbruch bewusst platziert sind.
    """

    @staticmethod
    def _reihe():
        import pandas as pd

        zeilen = [
            (100.0, 101.0, 99.0, 100.0),
            (100.0, 101.0, 99.0, 100.0),
            (100.0, 102.0, 99.5, 101.5),
            (102.0, 106.0, 101.5, 105.5),   # Luecke: 101.5 ueber Hoch 101.0
            (105.0, 106.0, 104.0, 105.0),
            (105.0, 106.0, 104.0, 105.0),
            (104.0, 105.0, 98.0, 104.5),    # Abgriff unter das Tief
            (104.0, 108.0, 104.0, 107.5),   # Bruch nach oben
        ]
        frame = pd.DataFrame(zeilen, columns=["open", "high", "low", "close"])
        frame["volume"] = 100.0
        frame["open_time"] = pd.date_range(
            "2026-01-01", periods=len(frame), freq="15min", tz="UTC"
        )
        return frame

    def test_preisluecke_wird_erkannt(self) -> None:
        from strategy.indicators import fvg_up_pct

        werte = fvg_up_pct(self._reihe())

        # 101.5 - 101.0 = 0.5 auf einen Schluss von 105.5
        assert werte[3] == pytest.approx(0.5 / 105.5 * 100, rel=1e-6)
        assert werte[0] == 0.0
        assert werte[2] == 0.0

    def test_luecke_hat_ein_ablaufdatum(self) -> None:
        """Eine Luecke von vor hundert Balken ist kein Einstiegsniveau mehr."""
        import numpy as np

        from strategy.indicators import fvg_up_level

        frisch = fvg_up_level(self._reihe(), lookback=10)
        # Die juengste Luecke liegt bei Index 4, der letzte Balken ist 7 -
        # also drei Balken her. Bei lookback=2 ist sie damit abgelaufen.
        alt = fvg_up_level(self._reihe(), lookback=2)

        assert frisch[3] == pytest.approx(101.5)
        assert np.isnan(alt[-1]), "Nach Ablauf darf kein Niveau mehr kommen"

    def test_abgriff_braucht_den_rueckschluss(self) -> None:
        """Unter das Tief **und** wieder darueber schliessen.

        Ohne den Rueckschluss ist es kein Abgriff, sondern schlicht ein Bruch
        nach unten - das Gegenteil dessen, was das Modell meint.
        """
        from strategy.indicators import bars_since_sweep_low

        werte = bars_since_sweep_low(self._reihe(), period=4)

        assert werte[6] == 0.0, "Balken 6 ist der Abgriff"
        assert werte[7] == 1.0
        assert werte[5] > 1000, "Davor gab es keinen"

    def test_strukturbruch_zaehlt_nur_schlusskurse(self) -> None:
        """Ein kurz ueberschossenes Hoch ist ein Abgriff, kein Bruch.

        Wuerde hier das Hoch statt des Schlusskurses zaehlen, waeren beide
        Ereignisse dasselbe - und das Modell haette keinen Inhalt mehr.
        """
        from strategy.indicators import bars_since_bos_up

        werte = bars_since_bos_up(self._reihe(), period=3)

        assert werte[7] == 0.0
        assert werte[0] > 1000

    def test_koerper_wird_an_der_atr_gemessen(self) -> None:
        """Eine feste Prozentschwelle misst die Volatilitaet, nicht die Kerze.

        Beim Pruefen loeste der Kandidat mit fester 0,5-%-Schwelle auf 5.000
        Kerzen genau einmal aus. Dasselbe Verhaeltnis zur ATR ist von der
        Marktphase unabhaengig.
        """
        import numpy as np
        import pandas as pd

        from strategy.indicators import body_atr_ratio

        def reihe(spanne: float) -> pd.DataFrame:
            n = 200
            close = np.full(n, 100.0)
            close[-1] = 100.0 + spanne
            offen = np.full(n, 100.0)
            frame = pd.DataFrame(
                {
                    "open": offen,
                    "high": np.maximum(offen, close) + spanne * 0.1,
                    "low": np.minimum(offen, close) - spanne * 0.1,
                    "close": close,
                    "volume": np.full(n, 100.0),
                }
            )
            frame["high"] = frame[["high", "close"]].max(axis=1)
            frame["low"] = frame[["low", "close"]].min(axis=1)
            frame["open_time"] = pd.date_range(
                "2026-01-01", periods=n, freq="15min", tz="UTC"
            )
            return frame

        ruhig = body_atr_ratio(reihe(0.5), period=14)[-1]
        bewegt = body_atr_ratio(reihe(5.0), period=14)[-1]

        # Beide Male ist die letzte Kerze gleich auffaellig im Verhaeltnis zu
        # ihrer Umgebung - das Verhaeltnis muss das zeigen, die Prozentzahl
        # wuerde sich verzehnfachen.
        assert bewegt == pytest.approx(ruhig, rel=0.05)


class TestGeneration8:
    def test_alle_kandidaten_kompilieren(self) -> None:
        for genome in load_seeds(8):
            assert compile_genome(genome).warmup_bars > 0

    def test_die_short_seite_ist_vertreten(self) -> None:
        """Von 24 frueher geprueften Regeln waren 23 long.

        Ueber den geprueften Zeitraum ist BTC gestiegen; eine Long-Regel kann
        allein davon leben. Ohne Gegenproben nach unten laesst sich nicht
        trennen, was Mechanismus war und was Trend.
        """
        shorts = [g for g in load_seeds(8) if g.entry_short]

        assert len(shorts) >= 4, "Zu wenige Gegenproben nach unten"

    def test_das_modell_liegt_zerlegt_vor(self) -> None:
        """Vollstaendig, ohne Luecke, ohne Bruch.

        Nur so laesst sich sagen, ob die Reihenfolge etwas beitraegt oder ob
        einer der Bestandteile allein die Arbeit macht.
        """
        namen = {g.name for g in load_seeds(8)}

        assert "Abfolge-Modell (Abgriff, Bruch, Rueckkehr)" in namen
        assert "Abfolge ohne Luecke" in namen
        assert "Abfolge ohne Strukturbruch" in namen


class TestRangfolgeBelohntKeineRisikoreduktion:
    """Mehr bestandene Gates heisst nicht besserer Kandidat.

    **Der Fall ist gemessen, nicht ausgedacht.** Derselbe Kandidat mit
    engerem Stop bestand 9 von 11 Gates statt 8 - aber nur, weil er schlicht
    weniger riskierte. Rueckgang, schlechtestes Jahr und Monte-Carlo
    bestanden dort durch kleinere Positionen, waehrend der Deflated Sharpe
    von 0,901 auf 0,619 fiel.

    Nach der alten Reihenfolge waere die schlechtere Strategie auf Platz eins
    gelandet, und die Bestenliste haette einen Rueckschritt als Fortschritt
    ausgewiesen. Der Deflated Sharpe steht deshalb vor der Gate-Zahl: Er
    laesst sich nicht durch kleinere Positionen verbessern.
    """

    def test_belastbarer_vorteil_schlaegt_mehr_gates(
        self, board: Leaderboard
    ) -> None:
        seeds = load_seeds(7)
        board.record(
            [
                # Weniger Gates, aber der Vorteil ist belastbarer.
                kandidat(seeds[0], bestanden=8, deflated=0.90, erwartung=0.30),
                # Mehr Gates - erkauft mit kleineren Positionen.
                kandidat(seeds[1], bestanden=9, deflated=0.62, erwartung=0.10),
            ],
            generation=7,
        )

        rang = board.ranked()

        assert rang[0].name == seeds[0].name, (
            "die Bestenliste bevorzugt mehr bestandene Gates, obwohl der "
            "Vorteil dort deutlich unsicherer ist"
        )
        assert rang[0].deflated_sharpe > rang[1].deflated_sharpe

    def test_bei_gleichem_deflated_sharpe_entscheiden_die_gates(
        self, board: Leaderboard
    ) -> None:
        """Die Gate-Zahl bleibt im Schluessel - nur eine Stufe tiefer."""
        seeds = load_seeds(7)
        board.record(
            [
                kandidat(seeds[0], bestanden=5, deflated=0.80),
                kandidat(seeds[1], bestanden=8, deflated=0.80),
            ],
            generation=7,
        )

        assert board.ranked()[0].name == seeds[1].name

    def test_zugelassen_steht_weiterhin_ganz_oben(self, board: Leaderboard) -> None:
        """Wer alle Gates besteht, ist fertig - egal welche Kennzahl."""
        seeds = load_seeds(7)
        board.record(
            [
                kandidat(seeds[0], bestanden=9, deflated=0.99, erwartung=0.50),
                kandidat(seeds[1], bestanden=9, deflated=0.96, zugelassen=True),
            ],
            generation=7,
        )

        assert board.ranked()[0].zugelassen

    def test_uebersprungenes_gate_zaehlt_als_null(self, board: Leaderboard) -> None:
        """Ein Kandidat, ueber dessen Belastbarkeit sich nichts sagen laesst,
        steht nicht vor einem, ueber den etwas bekannt ist."""
        seeds = load_seeds(7)
        board.record(
            [kandidat(seeds[0], bestanden=9, deflated=0.0, trades=8)],
            generation=7,
        )

        assert board.ranked()[0].deflated_sharpe == 0.0
