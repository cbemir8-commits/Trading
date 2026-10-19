"""Ein Offizier ohne Vorgeschichte vergibt eine neue Erlaubnis - Befund 376.

Die offene Frage aus Befund 263/318/353 endet mit diesem Satz:

    wer trotzdem zwei Beine will, braucht zwei Ablagen ('PATHS__STATE') - und
    dann gelten die Verlustgrenzen je Bein statt je Konto, also **zweimal die
    Tagesgrenze auf einem Konto**

Nachgemessen stimmt die Richtung und der Mechanismus nicht. ``observe_equity``
rechnet alles aus dem **uebergebenen** Kapitalstand, und beide Beine lesen die
Konto-Equity. Gleichzeitig gestartet greifen sie daher **identisch**:

    Versatz   Bein   Tagespause   Wochenpause       Kill
      0 %      A       -3,00 %      -7,00 %     -15,00 %
      0 %      B       -3,00 %      -7,00 %     -15,00 %

Nicht zweimal die Grenze. Was die Grenze oeffnet, ist der **Versatz**: Ein
Offizier ohne frueheren Zustand setzt Hoechststand, Tages- und Wochenstart auf
den ersten Stand, den er sieht.

    Versatz   Bein   Tagespause   Wochenpause       Kill
      2 %      B       -4,95 %      -8,90 %     -16,70 %
      5 %      B       -7,85 %     -11,65 %     -19,25 %
     10 %      B      -12,70 %     -16,30 %     -23,50 %

Alle Prozente vom echten Ausgangsstand. Bei zehn Prozent Versatz darf das
Konto 23,50 % verlieren, bevor der Kill-Switch des zweiten Beins greift -
gegen eine Grenze von 15 %.

Und es sind nicht die zwei Beine
--------------------------------
Derselbe Mechanismus trifft **einen** Lauf mit frischer Ablage: neues
``PATHS__STATE``, geloeschte oder unlesbare ``risk.json``, oder ein erster
Start auf einem Konto, das schon verloren hat. Nicht die Zahl der Beine
oeffnet die Grenze, sondern der fehlende Hoechststand.

Was gebaut wurde
----------------
Keine Sperre - ein Satz. Der Offizier kann den frueheren Hoechststand nicht
wissen; die Boerse liefert ihn nicht, und erfinden waere schlimmer als die
Luecke. Also sagt er beim ersten Kapitalstand einmal, dass er ohne
Vorgeschichte anfaengt und was das heisst. Ueber ``_melden``, damit
Forschungslaeufe still bleiben (Befund 369).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import structlog
from structlog.testing import capture_logs

from execution.risk import RiskOfficer, TradingState
from tests.factories import make_instrument

JETZT = datetime(2026, 6, 1, 12, tzinfo=UTC)
START = Decimal("500")


@pytest.fixture(autouse=True)
def _alle_stufen():
    """Stufe auf 'debug' und danach zurueck - wie in Befund 369.

    ``cli._configure_logging`` stellt die Stufe global ein; ohne das haengt das
    Ergebnis an der Reihenfolge der Tests.
    """
    vorher = structlog.get_config()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
    )
    yield
    structlog.configure(**vorher)


def _offizier(risk, tmp_path, name: str, *, simulation: bool = False) -> RiskOfficer:
    return RiskOfficer(
        risk,
        make_instrument(),
        state_path=tmp_path / f"{name}.json",
        clock=lambda: JETZT,
        simulation=simulation,
    )


def _schwellen(offizier: RiskOfficer, ab: Decimal) -> dict[str, Decimal | None]:
    """Wo Tagespause, Wochenpause und Kill-Switch greifen.

    Die Tagesgrenze setzt **nur** ``paused_until`` und nicht
    ``trading_state`` - wer auf den Zustand prueft, findet sie nie und haelt
    die Wochengrenze fuer sie. (Genau das ist mir beim Messen passiert.)
    """
    gefunden: dict[str, Decimal | None] = {"tag": None, "woche": None, "kill": None}
    stand = ab
    while stand > START / 3 and gefunden["kill"] is None:
        offizier.observe_equity(stand)
        if gefunden["tag"] is None and offizier.state.paused_until is not None:
            gefunden["tag"] = stand
        if (
            gefunden["woche"] is None
            and offizier.state.trading_state is TradingState.PAUSED
        ):
            gefunden["woche"] = stand
        if offizier.state.trading_state is TradingState.KILLED:
            gefunden["kill"] = stand
        stand -= Decimal("0.25")
    return gefunden


def _prozent(stand: Decimal | None) -> float | None:
    return None if stand is None else float((stand / START - 1) * 100)


class TestZweiBeineGleichzeitigSindNichtDasProblem:
    """**Die Berichtigung.** Das Register nannte den falschen Mechanismus."""

    def test_beide_greifen_an_derselben_stelle(self, risk, tmp_path) -> None:
        a = _offizier(risk, tmp_path, "a")
        b = _offizier(risk, tmp_path, "b")
        a.observe_equity(START)
        b.observe_equity(START)

        sa = _schwellen(a, START)
        sb = _schwellen(b, START)

        assert _prozent(sa["kill"]) == pytest.approx(-15.0, abs=0.1)
        assert sa == sb

    def test_weil_beide_die_konto_equity_lesen(self, risk, tmp_path) -> None:
        """Der Grund, nicht nur die Folge: Die Grenzen haengen am uebergebenen
        Stand, nicht an einer Buchhaltung je Bein."""
        a = _offizier(risk, tmp_path, "a")
        b = _offizier(risk, tmp_path, "b")
        a.observe_equity(START)
        b.observe_equity(START)

        lage_a = a.observe_equity(Decimal("480"))
        lage_b = b.observe_equity(Decimal("480"))

        assert lage_a.drawdown_pct == lage_b.drawdown_pct
        assert lage_a.day_pnl_pct == lage_b.day_pnl_pct
        assert lage_a.equity_peak == lage_b.equity_peak == START


class TestDerVersatzOeffnetDieGrenze:
    """Was wirklich bricht - gemessen, mit Zahlen aus dem Kopf dieser Datei."""

    @pytest.mark.parametrize(
        ("versatz_pct", "kill_pct"),
        [(2, -16.70), (5, -19.25), (10, -23.50)],
    )
    def test_das_spaeter_gestartete_bein_greift_zu_spaet(
        self, risk, tmp_path, versatz_pct: int, kill_pct: float
    ) -> None:
        spaeter = START * (1 - Decimal(versatz_pct) / 100)
        a = _offizier(risk, tmp_path, "a")
        a.observe_equity(START)
        a.observe_equity(spaeter)

        b = _offizier(risk, tmp_path, "b")
        b.observe_equity(spaeter)

        assert _prozent(_schwellen(a, spaeter)["kill"]) == pytest.approx(
            -15.0, abs=0.1
        )
        assert _prozent(_schwellen(b, spaeter)["kill"]) == pytest.approx(
            kill_pct, abs=0.1
        )

    def test_auch_ein_einzelner_lauf_mit_frischer_ablage(
        self, risk, tmp_path
    ) -> None:
        """Nicht die Zahl der Beine oeffnet die Grenze.

        Ein Lauf, der mit neuem 'PATHS__STATE' startet - oder nach einer
        geloeschten 'risk.json' -, bekommt dieselbe neue Erlaubnis.
        """
        erst = _offizier(risk, tmp_path, "lauf1")
        erst.observe_equity(START)
        erst.observe_equity(START * Decimal("0.9"))

        neu = _offizier(risk, tmp_path, "lauf2")
        neu.observe_equity(START * Decimal("0.9"))

        assert _prozent(_schwellen(neu, START * Decimal("0.9"))["kill"]) == (
            pytest.approx(-23.50, abs=0.1)
        )

    def test_mit_vorgeschichte_bleibt_die_grenze_wo_sie_hingehoert(
        self, risk, tmp_path
    ) -> None:
        """Die Gegenprobe: Derselbe Pfad, also derselbe Hoechststand."""
        erst = _offizier(risk, tmp_path, "gleich")
        erst.observe_equity(START)
        erst.observe_equity(START * Decimal("0.9"))

        wieder = _offizier(risk, tmp_path, "gleich")
        wieder.observe_equity(START * Decimal("0.9"))

        assert wieder.state.equity_peak == START
        assert _prozent(_schwellen(wieder, START * Decimal("0.9"))["kill"]) == (
            pytest.approx(-15.0, abs=0.1)
        )


class TestErSagtEsEinmal:
    def test_beim_ersten_kapitalstand(self, risk, tmp_path) -> None:
        offizier = _offizier(risk, tmp_path, "neu")

        with capture_logs() as zeilen:
            offizier.observe_equity(START)

        gemeldet = [z for z in zeilen if z["event"] == "risk.ohne_vorgeschichte"]
        assert len(gemeldet) == 1
        assert gemeldet[0]["kapital"] == str(START)
        assert "greifen spaeter" in gemeldet[0]["hinweis"]

    def test_und_danach_nicht_mehr(self, risk, tmp_path) -> None:
        """Eine Zeile je Kerze waere so gut wie keine."""
        offizier = _offizier(risk, tmp_path, "neu")
        offizier.observe_equity(START)

        with capture_logs() as zeilen:
            for stand in (Decimal("499"), Decimal("498"), Decimal("497")):
                offizier.observe_equity(stand)

        assert [z for z in zeilen if z["event"] == "risk.ohne_vorgeschichte"] == []

    def test_nicht_wenn_ein_zustand_geladen_wurde(self, risk, tmp_path) -> None:
        erst = _offizier(risk, tmp_path, "vorhanden")
        erst.observe_equity(START)

        wieder = _offizier(risk, tmp_path, "vorhanden")
        with capture_logs() as zeilen:
            wieder.observe_equity(START)

        assert [z for z in zeilen if z["event"] == "risk.ohne_vorgeschichte"] == []

    def test_im_backtest_bleibt_er_still(self, risk, tmp_path) -> None:
        """Befund 369: Ein Forschungsbefehl hat 51 Grenzzeilen ausgegeben, 14
        davon CRITICAL. Eine neue Meldung geht denselben Weg."""
        offizier = _offizier(risk, tmp_path, "sim", simulation=True)

        with capture_logs() as zeilen:
            offizier.observe_equity(START)

        laut = [z for z in zeilen if z["event"] == "risk.ohne_vorgeschichte"]
        assert laut == []
        leise = [
            z for z in zeilen if z["event"] == "risk.ohne_vorgeschichte_simuliert"
        ]
        assert len(leise) == 1
        assert leise[0]["log_level"] == "debug"
        assert "hinweis" not in leise[0]

    def test_ein_kapitalstand_von_null_meldet_nichts(self, risk, tmp_path) -> None:
        """Vor dem ersten echten Stand gibt es nichts zu sagen - und ein
        Hoechststand von null wuerde die Meldung sofort entwerten."""
        offizier = _offizier(risk, tmp_path, "null")

        with capture_logs() as zeilen:
            offizier.observe_equity(Decimal(0))

        assert [z for z in zeilen if "ohne_vorgeschichte" in z["event"]] == []


class TestDieGrenzenSelbstSindUnberuehrt:
    """Eine Meldung ist keine Aenderung am Urteil."""

    def test_die_drei_schwellen_stehen_wo_sie_standen(self, risk, tmp_path) -> None:
        offizier = _offizier(risk, tmp_path, "unberuehrt")
        offizier.observe_equity(START)

        schwellen = _schwellen(offizier, START)

        assert _prozent(schwellen["tag"]) == pytest.approx(-3.0, abs=0.1)
        assert _prozent(schwellen["woche"]) == pytest.approx(-7.0, abs=0.1)
        assert _prozent(schwellen["kill"]) == pytest.approx(-15.0, abs=0.1)
