"""Ein simulierter Not-Aus ist kein Vorfall - Befund 369.

Gemessen an **einem** Forschungsbefehl, ``cli anatomie --bauteil konfluenz``:

    51 Grenzzeilen, davon 14 CRITICAL

Alle aus Walk-Forward-Laeufen, und alle mit demselben Ereignisnamen, derselben
Stufe und demselben Text wie der echte Fall:

    [critical] risk.kill_switch  drawdown_pct=15.1
               hinweis='Alles glattstellen. Nur manuell zurueckholbar.'

Wer Protokolle nach ``risk.kill_switch`` durchsucht - und genau das wuerde man
tun -, konnte den Vorfall nicht vom Backtest unterscheiden. Und der Text ist
eine **Anweisung an einen Menschen**, die in einer Simulation niemand ausfuehren
kann oder sollte.

Im Backtest ist ein erreichtes Limit kein Vorfall, sondern ein **Ergebnis**: Es
steht in den Kennzahlen, und das Gate "Drawdown" misst es. Deshalb traegt der
Officer jetzt ein ``simulation``-Kennzeichen, das **nichts am Verhalten
aendert** und nur die Meldung umstellt - ``debug``, Name mit ``_simuliert``,
ohne den Hinweis. Mit ``-v`` sind alle 51 Zeilen weiter zu sehen.

Dass das Verhalten gleich bleibt, ist die wichtigste Zusicherung hier: Derselbe
Code entscheidet im Backtest und im Betrieb, und das ist in diesem Projekt
mehrfach teuer erkauft worden.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import structlog
from structlog.testing import capture_logs

from execution.risk import RiskOfficer, TradingState


@pytest.fixture(autouse=True)
def _alle_stufen():
    """Protokollstufe auf DEBUG, fuer die Dauer des Tests.

    **Noetig, und das ist eine Lehre fuer sich.** Die simulierte Meldung ist
    'debug', und ``structlog`` filtert nach Stufe, **bevor** ``capture_logs``
    etwas sieht. ``cli._configure_logging`` stellt die Stufe global ein - also
    bestanden diese Tests einzeln und fielen in der vollen Suite, sobald
    vorher ein Test einen Befehl gefahren hatte. Derselbe Fehler wie in Befund
    362: Ein Ergebnis, das von der Reihenfolge abhaengt, ist keins.
    """
    vorher = structlog.get_config()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(10)
    )
    try:
        yield
    finally:
        structlog.configure(**vorher)


@pytest.fixture
def jetzt() -> datetime:
    return datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _officer(risk, btcusdt, *, simulation: bool, jetzt: datetime) -> RiskOfficer:
    return RiskOfficer(
        risk, btcusdt, state_path=None, clock=lambda: jetzt,
        simulation=simulation,
    )


def _bis_zum_notaus(officer: RiskOfficer) -> None:
    """Kapital einbrechen lassen, bis der Not-Aus greift (15 %)."""
    officer.observe_equity(Decimal("1000"))
    officer.observe_equity(Decimal("800"))


class TestDerBetriebMeldetLautWieBisher:
    def test_der_notaus_bleibt_critical(self, risk, btcusdt, jetzt) -> None:
        officer = _officer(risk, btcusdt, simulation=False, jetzt=jetzt)

        with capture_logs() as zeilen:
            _bis_zum_notaus(officer)

        treffer = [z for z in zeilen if z["event"] == "risk.kill_switch"]
        assert treffer, [z["event"] for z in zeilen]
        assert treffer[0]["log_level"] == "critical"

    def test_und_traegt_die_anweisung_an_den_menschen(
        self, risk, btcusdt, jetzt
    ) -> None:
        officer = _officer(risk, btcusdt, simulation=False, jetzt=jetzt)

        with capture_logs() as zeilen:
            _bis_zum_notaus(officer)

        treffer = next(z for z in zeilen if z["event"] == "risk.kill_switch")
        assert "glattstellen" in treffer["hinweis"]


class TestDieSimulationMeldetLeiseUndAnders:
    def test_der_name_sagt_dass_es_simuliert_ist(self, risk, btcusdt, jetzt) -> None:
        """Damit eine Suche nach 'risk.kill_switch' nur echte Faelle findet."""
        officer = _officer(risk, btcusdt, simulation=True, jetzt=jetzt)

        with capture_logs() as zeilen:
            _bis_zum_notaus(officer)

        namen = [z["event"] for z in zeilen]
        assert "risk.kill_switch_simuliert" in namen
        assert "risk.kill_switch" not in namen

    def test_die_stufe_ist_debug(self, risk, btcusdt, jetzt) -> None:
        officer = _officer(risk, btcusdt, simulation=True, jetzt=jetzt)

        with capture_logs() as zeilen:
            _bis_zum_notaus(officer)

        treffer = next(
            z for z in zeilen if z["event"] == "risk.kill_switch_simuliert"
        )
        assert treffer["log_level"] == "debug"

    def test_ohne_anweisung_an_einen_menschen(self, risk, btcusdt, jetzt) -> None:
        """"Alles glattstellen" kann in einem Backtest niemand ausfuehren."""
        officer = _officer(risk, btcusdt, simulation=True, jetzt=jetzt)

        with capture_logs() as zeilen:
            _bis_zum_notaus(officer)

        treffer = next(
            z for z in zeilen if z["event"] == "risk.kill_switch_simuliert"
        )
        assert "hinweis" not in treffer

    def test_die_zahlen_bleiben_in_der_meldung(self, risk, btcusdt, jetzt) -> None:
        """Leiser heisst nicht aermer - mit '-v' soll dieselbe Messung
        dastehen."""
        officer = _officer(risk, btcusdt, simulation=True, jetzt=jetzt)

        with capture_logs() as zeilen:
            _bis_zum_notaus(officer)

        treffer = next(
            z for z in zeilen if z["event"] == "risk.kill_switch_simuliert"
        )
        assert treffer["drawdown_pct"] >= 15.0
        assert treffer["kapital"] == "800"

    def test_auch_das_wochenlimit_und_das_tageslimit(
        self, risk, btcusdt, jetzt
    ) -> None:
        officer = _officer(risk, btcusdt, simulation=True, jetzt=jetzt)

        with capture_logs() as zeilen:
            # Tagesverlust ueber der Grenze, aber unter dem Not-Aus.
            officer.observe_equity(Decimal("1000"))
            officer.observe_equity(Decimal("955"))

        namen = [z["event"] for z in zeilen]
        assert any(n.endswith("_simuliert") for n in namen), namen
        assert not any(
            n in ("risk.tageslimit", "risk.wochenlimit") for n in namen
        )


class TestAmVerhaltenAendertSichNichts:
    """**Die wichtigste Zusicherung.** Derselbe Code entscheidet im Backtest
    und im Betrieb; dass das so bleibt, ist in diesem Projekt mehrfach teuer
    erkauft worden."""

    def test_derselbe_zustand_nach_dem_notaus(self, risk, btcusdt, jetzt) -> None:
        echt = _officer(risk, btcusdt, simulation=False, jetzt=jetzt)
        simuliert = _officer(risk, btcusdt, simulation=True, jetzt=jetzt)

        for officer in (echt, simuliert):
            _bis_zum_notaus(officer)

        assert echt.state.trading_state is TradingState.KILLED
        assert simuliert.state.trading_state is TradingState.KILLED
        assert echt.state.kill_reason == simuliert.state.kill_reason

    def test_dieselbe_pause_beim_tageslimit(self, risk, btcusdt, jetzt) -> None:
        echt = _officer(risk, btcusdt, simulation=False, jetzt=jetzt)
        simuliert = _officer(risk, btcusdt, simulation=True, jetzt=jetzt)

        for officer in (echt, simuliert):
            officer.observe_equity(Decimal("1000"))
            officer.observe_equity(Decimal("955"))

        assert echt.state.paused_until == jetzt + timedelta(hours=24)
        assert simuliert.state.paused_until == echt.state.paused_until

    def test_und_dasselbe_veto(self, risk, btcusdt, jetzt) -> None:
        echt = _officer(risk, btcusdt, simulation=False, jetzt=jetzt)
        simuliert = _officer(risk, btcusdt, simulation=True, jetzt=jetzt)

        for officer in (echt, simuliert):
            _bis_zum_notaus(officer)

        a, b = echt.blockade(), simuliert.blockade()
        assert a is not None and b is not None
        assert a.reason == b.reason

    def test_der_vorgabewert_ist_betrieb(self, risk, btcusdt) -> None:
        """Wer den Officer ohne Angabe baut, bekommt die laute Meldung - die
        sichere Richtung."""
        officer = RiskOfficer(risk, btcusdt, state_path=None)

        assert officer.simulation is False


class TestWerSimuliertSagtEsAuch:
    def test_der_backtest(self) -> None:
        import inspect

        from backtest.engine import Backtester

        quelle = inspect.getsource(Backtester)

        assert "simulation=True" in quelle

    def test_die_kontoleiter(self) -> None:
        from pathlib import Path

        quelle = Path("research/kontorisiko.py").read_text(encoding="utf-8")

        assert "simulation=True" in quelle

    def test_der_livebetrieb_nicht(self) -> None:
        """``cli trade`` baut den Officer fuer echtes Geld."""
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.FunctionDef) and knoten.name == "trade":
                quelle = ast.unparse(knoten)
                break
        else:
            raise AssertionError("'trade' steht nicht mehr in cli.py")

        assert "RiskOfficer(" in quelle
        assert "simulation" not in quelle


class TestDasRegisterHaeltDenFund:
    def test_er_steht_unter_behoben(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 369)

        assert "51" in eintrag.ergebnis
        assert "14" in eintrag.ergebnis
