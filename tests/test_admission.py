"""Tests der Zulassungsstrecke.

Der wichtigste Test hier ist ``test_nothing_passes_on_pure_noise``: Auf einer
Zufallsreihe gibt es nichts zu verdienen. Laesst die Strecke dort eine
Strategie durch, ist sie wertlos - dann misst sie Zufall und nennt es Edge.
Ein Test, der nur zeigt dass eine gute Strategie besteht, sagt darueber nichts
aus.

Der zweitwichtigste ist der Versuchszaehler: Die Deflated Sharpe Ratio
korrigiert dafuer, dass man bei genug Versuchen irgendwann zufaellig etwas
Gutaussehendes findet. Wird der Zaehler bei jedem Lauf zurueckgesetzt, ist
die Korrektur wirkungslos - und genau das faellt sonst niemandem auf.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestConfig
from backtest.walkforward import WalkForwardReport, WalkForwardSplitter
from core.config import RiskSettings
from core.models import Instrument
from research.admission import (
    AdmissionReport,
    Candidate,
    load_trials,
    pick_champion,
    run_admission,
    save_trials,
    write_champion,
    write_journal,
)
from research.gates import GateReport, GateResult, GateStatus
from research.seeds import ema_cross, load_seeds, trend_following
from research.versuche import ZaehlerUnlesbarError
from strategy.compiler import compile_genome
from strategy.genome import Genome


def noise_frame(*, months: int = 20, seed: int = 7) -> pd.DataFrame:
    """Ein reiner Zufallspfad ohne ausnutzbare Struktur.

    Geometrische Brownsche Bewegung ohne Drift: Jede Kerze ist von der
    vorherigen unabhaengig. Es *gibt* hier keine Strategie, die verdient -
    was durchkommt, ist Ueberanpassung.
    """
    rng = np.random.default_rng(seed)
    bars = int(months * 30 * 24 * 4)  # 15-Minuten-Kerzen
    close = 30000 * np.exp(np.cumsum(rng.normal(0, 0.0025, bars)))
    high = close * (1 + np.abs(rng.normal(0, 0.0012, bars)))
    low = close * (1 - np.abs(rng.normal(0, 0.0012, bars)))
    return pd.DataFrame(
        {
            "open_time": pd.date_range(
                datetime(2023, 1, 1, tzinfo=UTC), periods=bars, freq="15min"
            ),
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": np.maximum(high, close),
            "low": np.minimum(low, close),
            "close": close,
            "volume": rng.lognormal(2, 0.5, bars),
            "turnover": rng.lognormal(12, 0.5, bars),
        }
    )


@pytest.fixture
def config(btcusdt: Instrument, risk: RiskSettings) -> BacktestConfig:
    return BacktestConfig(instrument=btcusdt, risk=risk, initial_equity=Decimal("500"))


# ---------------------------------------------------------------------------
#  Der Kerntest
# ---------------------------------------------------------------------------
def test_nothing_passes_on_pure_noise(config: BacktestConfig) -> None:
    """Auf einem Zufallspfad darf keine Strategie zugelassen werden.

    Das ist der Beleg, dass die Gates ueberhaupt etwas leisten. Eine
    Zulassungsstrecke, die auf Rauschen einen Champion findet, wuerde live
    genau das handeln: Rauschen.
    """
    frame = noise_frame()

    report = run_admission(
        [trend_following(), ema_cross()],
        frame,
        config,
        trials_so_far=0,
        run_expensive=False,  # die teuren Gates wuerden nur noch mehr ablehnen
    )

    assert report.champion is None
    assert report.admitted == []
    # Und es lag nicht daran, dass gar nicht gehandelt wurde:
    assert sum(c.trades for c in report.candidates) > 0, (
        "Kein einziger Trade - dann sagt der Test nichts ueber die Gates aus"
    )


def test_seed_genomes_all_compile() -> None:
    """Jeder Kandidat muss uebersetzbar sein.

    Ein Genom, das die Validierung passiert aber nicht kompiliert, wuerde erst
    mitten im Zulassungslauf auffallen - nach Minuten Rechenzeit.
    """
    for genome in load_seeds():
        strategy = compile_genome(genome)
        assert strategy.warmup_bars > 0
        assert strategy.strategy_id == genome.genome_id


def test_seed_genomes_are_distinct() -> None:
    """Zwei Kandidaten mit identischen Regeln waeren derselbe Versuch -
    wuerden aber zweimal gezaehlt und die Korrektur unnoetig verschaerfen."""
    ids = [g.genome_id for g in load_seeds()]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
#  Versuchszaehler
# ---------------------------------------------------------------------------
class TestTrialCounter:
    def test_every_candidate_counts_even_the_rejected(
        self, config: BacktestConfig
    ) -> None:
        """Ein Versuch ist ein Versuch.

        Nur die Erfolgreichen zu zaehlen waere genau der Fehler, gegen den die
        Mehrfachtest-Korrektur gebaut ist: Wer zwanzig Ideen probiert und nur
        die eine zaehlt, die funktioniert hat, haelt Zufall fuer Koennen.
        """
        report = run_admission(
            [trend_following(), ema_cross()],
            noise_frame(),
            config,
            trials_so_far=17,
            run_expensive=False,
        )

        assert report.admitted == []  # keiner bestanden
        assert report.trials_after == 19  # trotzdem beide gezaehlt

    def test_counter_survives_a_restart(self, tmp_path: Path) -> None:
        path = tmp_path / "trials.json"
        save_trials(path, 42)

        assert load_trials(path) == 42

    def test_missing_file_starts_at_zero(self, tmp_path: Path) -> None:
        assert load_trials(tmp_path / "gibtsnicht.json") == 0

    def test_corrupt_file_stops_the_run(self, tmp_path: Path) -> None:
        """**Frueher lieferte das hier 0**, und der Test hielt es fest.

        Der Kommentar daneben benannte die Gefahr sogar - ein zu niedriger
        Zaehler macht die Korrektur milder - und ein Protokolleintrag sollte
        genuegen. Er genuegt nicht: Der Lauf rechnete weiter und schrieb den
        falschen Stand danach fest.

        Am Spitzenkandidaten sind es 0,79 bei 166 Versuchen und 0,996 bei elf.
        Ein Dateifehler, gefolgt von einem Wettbewerb mit elf Genomen, haette
        das strengste Gate des Projekts umgedreht - ohne dass jemand etwas
        gelockert haette.
        """
        path = tmp_path / "trials.json"
        path.write_text("{kaputt")

        with pytest.raises(ZaehlerUnlesbarError):
            load_trials(path)

    def test_the_counter_never_falls(self, tmp_path: Path) -> None:
        """Ein Lauf, der weniger meldet als der vorige, hat sich verzaehlt
        oder mit einem Ersatzwert gerechnet. Der hoehere Stand bleibt."""
        path = tmp_path / "trials.json"
        save_trials(path, 166)
        save_trials(path, 11)

        assert load_trials(path) == 166

    def test_counter_is_written_atomically(self, tmp_path: Path) -> None:
        path = tmp_path / "trials.json"
        save_trials(path, 5)
        save_trials(path, 6)

        assert load_trials(path) == 6
        assert [p.name for p in tmp_path.iterdir()] == ["trials.json"]


# ---------------------------------------------------------------------------
#  Champion-Auswahl
# ---------------------------------------------------------------------------
def make_candidate(
    *, windows: int, profitable: int, sharpe: float, name: str
) -> Candidate:
    """Ein Kandidat mit vorgegebenen Fensterergebnissen - ohne Backtest.

    ``consistency`` wird nicht gesetzt, sondern ergibt sich wie im Betrieb aus
    den Fenstern. Sonst pruefte der Test seine eigene Hilfsfunktion statt der
    Auswahllogik.
    """
    report = WalkForwardReport()
    for index in range(windows):
        net = 100.0 if index < profitable else -50.0
        # ``trades`` muss belegt sein: Fenster ohne Handel zaehlen bei der
        # Bestaendigkeit nicht mit, und ein Kandidat, der in keinem Fenster
        # handelt, haette hier eine Quote von null statt der gemeinten.
        report.windows.append(
            SimpleNamespace(  # type: ignore[arg-type]
                metrics=SimpleNamespace(net_profit=net),
                is_profitable=net > 0,
                trades=[object()],
            )
        )
    report.combined = SimpleNamespace(sharpe=sharpe)  # type: ignore[assignment]

    genome = trend_following().model_copy(update={"name": name})
    return Candidate(
        genome=genome,
        walkforward=report,
        gates=GateReport(genome_id=genome.genome_id, results=[]),
    )


class TestChampionSelection:
    def test_no_candidates_gives_no_champion(self) -> None:
        assert pick_champion([]) is None

    def test_consistency_beats_sharpe(self) -> None:
        """Unter lauter zugelassenen Kandidaten liegen die Renditeunterschiede
        im Rauschen. Wer danach auswaehlt, waehlt Rauschen aus.

        Der Anteil profitabler Fenster sagt mehr darueber, ob eine Strategie
        naechsten Monat noch funktioniert.
        """
        steady = make_candidate(windows=10, profitable=8, sharpe=1.1, name="Bestaendig")
        spiky = make_candidate(windows=10, profitable=5, sharpe=2.4, name="Ausreisser")

        assert pick_champion([spiky, steady]) is steady

    def test_sharpe_breaks_the_tie(self) -> None:
        weaker = make_candidate(windows=10, profitable=7, sharpe=1.0, name="Schwaecher")
        stronger = make_candidate(windows=10, profitable=7, sharpe=1.8, name="Staerker")

        assert pick_champion([weaker, stronger]) is stronger


# ---------------------------------------------------------------------------
#  Ausgabedateien
# ---------------------------------------------------------------------------
class TestOutputFiles:
    def test_champion_can_be_read_back_by_the_trader(self, tmp_path: Path) -> None:
        """Die geschriebene Datei muss genau das sein, was ``cli trade``
        laedt - sonst faellt der Bruch erst beim Handelsstart auf."""
        genome = trend_following()
        candidate = Candidate(
            genome=genome,
            walkforward=WalkForwardReport(),
            gates=GateReport(genome_id=genome.genome_id, results=[]),
        )
        path = write_champion(candidate, tmp_path / "champion.json")

        restored = Genome.model_validate(json.loads(path.read_text()))

        assert restored.genome_id == genome.genome_id
        assert compile_genome(restored).warmup_bars == compile_genome(genome).warmup_bars

    def test_journal_appends_instead_of_overwriting(self, tmp_path: Path) -> None:
        """Das Forschungstagebuch ist die Grundlage des Lernens: Was wurde
        schon versucht, und woran ist es gescheitert? Ueberschreiben wuerde
        die KI dieselben Ideen endlos wiederholen lassen."""
        from research.admission import AdmissionReport

        path = tmp_path / "journal.json"
        first = AdmissionReport(trials_before=0, trials_after=2)
        second = AdmissionReport(trials_before=2, trials_after=4)

        write_journal(first, path)
        write_journal(second, path)

        entries = json.loads(path.read_text())
        assert len(entries) == 2
        assert entries[0]["trials_after"] == 2
        assert entries[1]["trials_before"] == 2

    def test_journal_records_why_a_candidate_failed(self, tmp_path: Path) -> None:
        """Nicht nur *dass* etwas durchfiel, sondern mit welchem Wert gegen
        welche Schwelle - sonst kann die naechste Generation nicht gezielt
        nachbessern und probiert blind weiter."""
        from research.admission import AdmissionReport

        genome = ema_cross()
        failing = GateReport(
            genome_id=genome.genome_id,
            results=[
                GateResult(
                    name="Out-of-Sample-Sharpe",
                    status=GateStatus.FAIL,
                    value=0.42,
                    threshold=1.0,
                    message="zu niedrig",
                )
            ],
        )
        report = AdmissionReport(
            candidates=[
                Candidate(
                    genome=genome, walkforward=WalkForwardReport(), gates=failing
                )
            ]
        )

        path = write_journal(report, tmp_path / "journal.json")
        entry = json.loads(path.read_text())[0]["candidates"][0]

        assert entry["admitted"] is False
        assert "0.420" in entry["gate_feedback"]
        assert "1.000" in entry["gate_feedback"]
        assert entry["rationale"]  # die Hypothese steht mit im Journal


def test_walkforward_needs_enough_history(config: BacktestConfig) -> None:
    """Zu kurze Historie ergibt kein einziges Fenster - und dann sagt ein
    leeres Ergebnis faelschlich 'nichts gefunden' statt 'nicht pruefbar'."""
    short = noise_frame(months=6)

    report = run_admission(
        [ema_cross()],
        short,
        config,
        splitter=WalkForwardSplitter(train_months=12, test_months=3),
        run_expensive=False,
    )

    assert report.candidates[0].walkforward.window_count == 0
    assert report.champion is None


class TestGeneration2:
    """Die zweite Generation - gebaut gegen die Befunde der ersten.

    Die erste Generation handelte 30 bis 95 Mal im Monat und verlor je Trade
    zwischen 0,09 und 0,50 R. Bei 16,7 % Gebuehrenanteil am Bruttogewinn ist
    das kein Zufall, sondern Arithmetik: Wer so oft handelt, zahlt seinen
    Vorteil an die Boerse, bevor er entsteht.
    """

    def test_targets_are_wider_than_in_the_first_generation(self) -> None:
        """Wenn 16 % des Bruttogewinns an Gebuehren gehen, muss ein Gewinner
        mehr tragen als 1,5 R."""
        from research.seeds import load_seeds

        for genome in load_seeds(generation=2):
            assert max(t.rr for t in genome.targets) >= 6.0, genome.name

    def test_cooldowns_are_longer(self) -> None:
        """Die direkteste Bremse gegen zu haeufiges Handeln."""
        from research.seeds import load_seeds

        first = {g.name: g.cooldown_bars for g in load_seeds(generation=1)}
        second = [g.cooldown_bars for g in load_seeds(generation=2)]

        assert min(second) > max(first.values())

    def test_at_most_two_conditions_each(self) -> None:
        """Die klarste Aussage des ersten Laufs: Der einfachste Kandidat war
        der beste. Jeder zusaetzliche Filter machte es schlechter."""
        from research.seeds import load_seeds

        for genome in load_seeds(generation=2):
            per_side = max(len(genome.entry_long), len(genome.entry_short))
            assert per_side + len(genome.filters) <= 2, genome.name

    def test_both_generations_stay_available(self) -> None:
        """Die widerlegte Generation bleibt abrufbar - das Journal verweist
        auf sie, und Nachvollziehbarkeit ist der halbe Wert der Uebung."""
        from research.seeds import load_seeds

        assert len(load_seeds(generation=1)) == 5
        assert len(load_seeds(generation=2)) == 5

    def test_unknown_generation_is_refused(self) -> None:
        import pytest as _pytest

        from research.seeds import load_seeds

        # Bewusst eine Zahl weit jenseits des Vorhandenen: Frueher stand hier
        # 7, und als Generation 7 dazukam, pruefte der Test nichts mehr - er
        # schlug fehl, weil das Erwartete eingetreten war.
        with _pytest.raises(ValueError, match="Generation 99"):
            load_seeds(generation=99)

    def test_generations_do_not_overlap(self) -> None:
        """Ein wiederholter Kandidat zaehlt in der Mehrfachtest-Korrektur,
        traegt aber nichts bei."""
        from research.seeds import load_seeds

        first = {g.genome_id for g in load_seeds(generation=1)}
        second = {g.genome_id for g in load_seeds(generation=2)}

        assert not (first & second)


# ---------------------------------------------------------------------------
#  Ein Champion entsteht nie aus einer Vorauswahl
# ---------------------------------------------------------------------------
class TestVorauswahlIstKeineZulassung:
    """**Der gefaehrlichste Fehler, den dieses Projekt hatte.**

    ``cli wettbewerb`` laeuft im Standardfall schnell, also ohne Kosten-Stress
    und Parameter-Plateau. ``GateReport.passed`` hiess bis hierher schlicht
    "alle Ergebnisse in der Liste sind gut" - bei neun Eintraegen also neun von
    neun. Ein Kandidat konnte damit Champion werden und in ``champion.json``
    landen, ohne die beiden teuersten Gates je gesehen zu haben.

    An genau dieser Datei haengt seit kurzem das echte Geld: ``cli trade``
    gibt Mainnet nur frei, wenn die Kennung mit ``champion.json``
    uebereinstimmt. Eine Sperre, die eine Datei schuetzt, die selbst nicht
    vollstaendig geprueft wurde, schuetzt nichts.
    """

    def _bericht(self, *, vorauswahl: bool, anzahl: int = 9) -> GateReport:
        return GateReport(
            genome_id="abc",
            vorauswahl=vorauswahl,
            results=[
                GateResult(
                    name=f"Gate {i}",
                    status=GateStatus.PASS,
                    value=1.0,
                    threshold=0.0,
                    message="gut",
                )
                for i in range(anzahl)
            ],
        )

    def test_alles_bestanden_ist_in_der_vorauswahl_keine_zulassung(self) -> None:
        bericht = self._bericht(vorauswahl=True)

        assert bericht.geprueftes_bestanden
        assert not bericht.passed

    def test_ohne_vorauswahl_gilt_alles_bestanden(self) -> None:
        assert self._bericht(vorauswahl=False, anzahl=11).passed

    def test_die_zusammenfassung_nennt_die_vorauswahl_beim_namen(self) -> None:
        """"Durchgefallen" waere falsch und "alle bestanden" waere
        gefaehrlich. Es ist weder das eine noch das andere."""
        text = self._bericht(vorauswahl=True).summary()

        assert "Vorauswahl" in text
        assert "durchgefallen" not in text

    def test_ein_vorauswahl_kandidat_wird_nicht_champion(
        self, config: BacktestConfig
    ) -> None:
        report = AdmissionReport()
        genome = trend_following()
        report.candidates.append(
            Candidate(
                genome=genome,
                walkforward=WalkForwardReport(),
                gates=self._bericht(vorauswahl=True),
            )
        )

        assert report.admitted == []
        assert pick_champion(report.admitted) is None

    def test_wer_die_vorauswahl_besteht_bekommt_den_nachschlag(
        self, config: BacktestConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**Die Zusage aus dem Hilfetext, jetzt eingeloest.**

        Dort stand seit jeher "die Zulassung laeuft am Ende mit allen" - und
        es lief nie etwas mit allen. Wer die schnellen Gates besteht, wird
        jetzt sofort mit allen elf nachgeprueft.
        """
        from research import admission as modul

        aufrufe: list[bool] = []

        def falsches_gate(genome, walkforward, frame, config, **kw):
            aufrufe.append(kw["run_expensive"])
            return GateReport(
                genome_id=genome.genome_id,
                vorauswahl=not kw["run_expensive"],
                results=[
                    GateResult(
                        name="Alles gut", status=GateStatus.PASS,
                        value=1.0, threshold=0.0, message="",
                    )
                ],
            )

        monkeypatch.setattr(modul, "evaluate_gates", falsches_gate)

        report = run_admission(
            [trend_following()], noise_frame(months=20), config,
            trials_so_far=0, run_expensive=False,
        )

        assert aufrufe == [False, True], (
            "Erst die Vorauswahl, dann der Nachschlag mit allen Gates"
        )
        assert report.champion is not None
        assert not report.champion.gates.vorauswahl

    def test_der_nachschlag_zaehlt_nicht_als_neuer_versuch(
        self, config: BacktestConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dasselbe Genom genauer zu messen ist keine zweite Hypothese - sonst
        wuerde ausgerechnet der aussichtsreichste Kandidat seine eigene
        Huerde anheben."""
        from research import admission as modul

        def immer_gut(genome, walkforward, frame, config, **kw):
            return GateReport(
                genome_id=genome.genome_id,
                vorauswahl=not kw["run_expensive"],
                results=[
                    GateResult(
                        name="Alles gut", status=GateStatus.PASS,
                        value=1.0, threshold=0.0, message="",
                    )
                ],
            )

        monkeypatch.setattr(modul, "evaluate_gates", immer_gut)

        report = run_admission(
            [trend_following()], noise_frame(months=20), config,
            trials_so_far=7, run_expensive=False,
        )

        assert report.trials_after == 8

    def test_wer_die_vorauswahl_reisst_bekommt_keinen_nachschlag(
        self, config: BacktestConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sonst waere die Vorauswahl sinnlos: Sie soll Rechenzeit sparen,
        indem die teuren Gates nur laufen, wo sie etwas entscheiden."""
        from research import admission as modul

        aufrufe: list[bool] = []

        def durchgefallen(genome, walkforward, frame, config, **kw):
            aufrufe.append(kw["run_expensive"])
            return GateReport(
                genome_id=genome.genome_id,
                vorauswahl=not kw["run_expensive"],
                results=[
                    GateResult(
                        name="Zu wenig", status=GateStatus.FAIL,
                        value=0.0, threshold=1.0, message="",
                    )
                ],
            )

        monkeypatch.setattr(modul, "evaluate_gates", durchgefallen)

        run_admission(
            [trend_following()], noise_frame(months=20), config,
            trials_so_far=0, run_expensive=False,
        )

        assert aufrufe == [False]
