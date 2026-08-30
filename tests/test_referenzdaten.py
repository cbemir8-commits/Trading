"""Elf von elf auf Bitstamp ist keine Zulassung auf Bybit.

Drei Tests tragen diese Datei:

``test_forschungskerzen_lassen_nicht_zu`` - Der Kern. Ein Bericht, in dem
**jedes** Gate besteht, gilt trotzdem nicht als zugelassen, solange er auf
Forschungskerzen gerechnet wurde.

``test_der_echte_lauf_erkennt_es_von_selbst`` - Die Wache. Erkannt wird es aus
den Symbolen der Beine, nicht ueber einen Schalter. Ein Schalter ist etwas,
das man vergisst - so steht es auch bei der Blockvariante der
Monte-Carlo-Simulation.

``test_ein_bein_genuegt`` - Eine Mischung aus Kassamarkt und Perpetual ist
schlechter als beides fuer sich, nicht besser als eines davon.
"""

from __future__ import annotations

import pytest

from data.reference import PAIRS, ist_referenz
from research.gates import GateReport, GateResult, GateStatus
from research.leaderboard import Entry


def bestanden(name: str) -> GateResult:
    return GateResult(
        name=name, status=GateStatus.PASS, value=1.0, threshold=0.0, message=""
    )


def bericht(**abweichung) -> GateReport:
    daten = {
        "genome_id": "abc",
        "results": [bestanden(f"Gate {i}") for i in range(11)],
    }
    daten.update(abweichung)
    return GateReport(**daten)


class TestZulassung:
    def test_forschungskerzen_lassen_nicht_zu(self) -> None:
        """**Der Test, der diese Datei traegt.**

        ``data/reference.py`` haelt seit jeher fest, dass diese Kerzen fuer
        die Zulassung nicht taugen. Erzwungen hat das nichts - bis hier.
        """
        forschung = bericht(referenzdaten=True)

        assert forschung.geprueftes_bestanden, "alle elf Gates halten"
        assert not forschung.passed, "und trotzdem keine Zulassung"
        assert "Forschungskerzen" in forschung.summary()
        assert "Daten der Boerse" in forschung.summary()

    def test_boersendaten_lassen_zu(self) -> None:
        """Gegenprobe: Ohne das Merkmal aendert sich nichts an der bisherigen
        Bedeutung von elf von elf."""
        echt = bericht()

        assert echt.passed
        assert "alle 11 Gates bestanden" in echt.summary()

    def test_die_vorauswahl_bleibt_unberuehrt(self) -> None:
        """Zwei verschiedene Gruende, nicht zugelassen zu sein - und beide
        muessen einzeln greifen."""
        nur_vorauswahl = bericht(vorauswahl=True)
        beides = bericht(vorauswahl=True, referenzdaten=True)

        assert not nur_vorauswahl.passed
        assert "teuren Gates fehlen noch" in nur_vorauswahl.summary()
        assert not beides.passed
        # Bei beidem gewinnt die Herkunft: Sie laesst sich nicht durch einen
        # zweiten Lauf beheben, die fehlenden Gates schon.
        assert "Forschungskerzen" in beides.summary()

    def test_ein_durchgefallenes_gate_bleibt_durchgefallen(self) -> None:
        gemischt = bericht(
            results=[
                bestanden("A"),
                GateResult(
                    name="B", status=GateStatus.FAIL, value=0.0,
                    threshold=1.0, message="",
                ),
            ],
            referenzdaten=True,
        )

        assert not gemischt.geprueftes_bestanden
        assert not gemischt.passed
        assert "durchgefallen" in gemischt.summary()


class TestErkennung:
    def test_die_referenzsymbole_sind_bekannt(self) -> None:
        assert ist_referenz("BTCUSD_BITSTAMP")
        assert ist_referenz("ETHUSD_BITSTAMP")
        assert not ist_referenz("BTCUSDT")
        assert not ist_referenz("ETHUSDT")
        assert set(PAIRS) == {
            "BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP",
            "LTCUSD_BITSTAMP", "XRPUSD_BITSTAMP",
        }

    def test_der_echte_lauf_erkennt_es_von_selbst(self) -> None:
        """**Die Wache.**

        ``cli wettbewerb`` faehrt im Standardfall auf BTCUSD_BITSTAMP und
        ETHUSD_BITSTAMP. Genau dieser Aufruf muss das Merkmal setzen, ohne
        dass jemand daran denkt.
        """
        from research.gates import evaluate_gates

        erkannt = evaluate_gates.__kwdefaults__["referenzdaten"]
        assert erkannt is None, "ohne Angabe wird erkannt, nicht angenommen"

        # Die Erkennung selbst, ohne einen ganzen Backtest zu fahren.
        beine = {"BTCUSD_BITSTAMP": None, "ETHUSD_BITSTAMP": None}
        assert any(ist_referenz(n) for n in beine)

    def test_ein_bein_genuegt(self) -> None:
        """Eine Mischung aus Kassamarkt und Perpetual ist schlechter als
        beides fuer sich - ``any`` und nicht ``all``."""
        gemischt = {"BTCUSDT": None, "ETHUSD_BITSTAMP": None}

        assert any(ist_referenz(n) for n in gemischt)
        assert not all(ist_referenz(n) for n in gemischt)

    def test_ohne_beine_wird_nichts_angenommen(self) -> None:
        """Ohne ``frames`` laesst es sich nicht erkennen, und dann steht
        ``False`` da. Das heisst "nicht erkannt" und nicht "geprueft und in
        Ordnung" - die Verantwortung liegt beim Aufrufer, der es ausdruecklich
        mitgeben kann."""
        assert not any(ist_referenz(n) for n in ())
        assert GateReport(genome_id="x").referenzdaten is False
        assert GateReport(genome_id="x", referenzdaten=True).referenzdaten


class TestBestenliste:
    def test_zwei_quellen_kollidieren_nicht(self) -> None:
        """Dieselbe Regel auf Bitstamp und auf Bybit hat dieselbe
        ``genome_id``. Ohne dieses Feld haette das bessere Ergebnis das andere
        verdraengt - dieselbe Kollision wie bei Intervall und Kontostand."""
        forschung = Entry(
            genome_id="x", name="Trend", generation=8,
            referenzdaten=True, gates_bestanden=9, gates_gesamt=11,
        )
        boerse = Entry(
            genome_id="x", name="Trend", generation=8,
            referenzdaten=False, gates_bestanden=6, gates_gesamt=11,
        )

        assert not forschung.vergleichbar_mit(boerse)
        assert not forschung.besser_als(boerse)
        assert not boerse.besser_als(forschung)

    def test_auf_derselben_quelle_gilt_der_rang(self) -> None:
        schwach = Entry(
            genome_id="x", name="T", generation=8,
            referenzdaten=True, gates_bestanden=5, gates_gesamt=11,
        )
        stark = Entry(
            genome_id="x", name="T", generation=8,
            referenzdaten=True, gates_bestanden=9, gates_gesamt=11,
        )

        assert stark.vergleichbar_mit(schwach)
        assert stark.besser_als(schwach)

    def test_es_kommt_aus_dem_gate_bericht(self, tmp_path) -> None:
        """Eine zweite Quelle fuer dieselbe Bedingung liefe frueher oder
        spaeter auseinander - deshalb wird sie aus dem Bericht gelesen."""
        from cli import _kandidat_aus_lauf
        from research.leaderboard import Leaderboard
        from research.seeds import spitzenkandidat

        class FakeMetrics:
            sharpe = 1.0
            expectancy_r = 0.3
            total_return_pct = 50.0
            max_drawdown_pct = 10.0

        class FakeReport:
            def __init__(self) -> None:
                self.all_trades: list = []
                self.combined = FakeMetrics()
                self.consistency = 0.5

        genome = spitzenkandidat()
        board = Leaderboard(tmp_path / "board.json")
        board.record(
            [
                _kandidat_aus_lauf(
                    genome,
                    FakeReport(),
                    GateReport(
                        genome_id=genome.genome_id, results=[],
                        referenzdaten=True,
                    ),
                )
            ],
            generation=8,
        )

        assert board.entries[genome.genome_id].referenzdaten is True


@pytest.mark.daten
def test_die_kerzen_dieses_projekts_sind_forschungsmaterial() -> None:
    """Der Satz, um den es geht: **Jede Gate-Zahl dieses Projekts** steht auf
    Bitstamp-Kerzen. Ein Test, der anschlaegt, sobald das nicht mehr stimmt.

    ``daten``-markiert seit Befund 151: Der Kerzenspeicher liegt nicht im
    Repository, in einem frischen Klon fehlt er. Dieser Test prueft dort die
    **Umgebung**, nicht den Code - und ist damit rot, ohne dass am Projekt
    etwas kaputt waere.

    Uebersprungen wird er trotzdem nicht stillschweigend: Wer ihn abwaehlt,
    tut das mit ``-m "not daten"`` und weiss dann, dass er ohne Messgrundlage
    geprueft hat.
    """
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore

    store = CandleStore(get_settings().paths.data_store)
    vorhanden = [
        s for s in PAIRS
        if not isinstance(store.read(s, Interval("D")), type(None))
        and not store.read(s, Interval("D")).empty
    ]

    assert vorhanden, "ohne Referenzkerzen gaebe es hier gar keine Messungen"
    assert all(ist_referenz(s) for s in vorhanden)


@pytest.mark.daten
def test_der_gemeldete_kerzenbestand_stimmt_mit_dem_speicher_ueberein() -> None:
    """**Befund 157.** Die Zeile in ``cli stand`` ist gemessen - hier wird
    geprueft, dass sie es bleibt.

    ``daten``-markiert aus demselben Grund wie der Test darueber: Ohne
    Kerzenspeicher prueft er die Umgebung, nicht den Code.
    """
    from cli import _kerzenbestand
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore

    store = CandleStore(get_settings().paths.data_store)
    zeile = _kerzenbestand(store)

    assert zeile != "keine Kerzen", "ohne Kerzen sagt der Test nichts"
    for symbol in PAIRS:
        frame = store.read(symbol, Interval("D"))
        vorhanden = frame is not None and not frame.empty
        assert (symbol in zeile) == vorhanden, (
            f"{symbol} steht {'nicht ' if vorhanden else ''}in der Zeile, "
            f"liegt aber {'' if vorhanden else 'nicht '}im Speicher"
        )
        if vorhanden:
            assert f"1d {len(frame)}" in zeile, "die Zahl muss die gemessene sein"


@pytest.mark.daten
def test_die_historie_der_aussicht_stimmt_mit_dem_speicher_ueberein() -> None:
    """**Befund 159.** ``historie_tage`` ist das letzte gepflegte Feld der
    Aussichtsrechnung - und das einzige, das an den Daten haengt.

    Waechst die Reihe, waechst die Spanne, und die Sammelrate aendert sich.
    Ohne diese Pruefung faende das niemand, bis jemand nachrechnet.
    """
    from backtest.portfolio_walkforward import common_range
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.referenz import AUSSICHT

    store = CandleStore(get_settings().paths.data_store)
    roh = {
        s: f for s in PAIRS
        if (f := store.read(s, Interval("D"))) is not None and not f.empty
    }
    assert roh, "ohne Kerzen sagt der Test nichts"

    # **Die gemeinsame Spanne, nicht die Vereinigung.** BTC reicht bis 2012
    # zurueck, ETH erst bis 2017; der Walk-Forward schneidet auf die kuerzere
    # (``common_range``), und genau darauf ist die Sammelrate gerechnet. Der
    # erste Anlauf dieses Tests nahm die Vereinigung und kam auf 5354 Tage.
    rahmen = common_range(roh)
    erster = next(iter(rahmen.values()))
    spanne = (erster["open_time"].iloc[-1] - erster["open_time"].iloc[0]).days

    assert AUSSICHT.historie_tage == pytest.approx(spanne, abs=40), (
        f"referenz.py nennt {AUSSICHT.historie_tage} Tage Historie, gemessen "
        f"sind {spanne} - die Sammelrate haengt daran."
    )
