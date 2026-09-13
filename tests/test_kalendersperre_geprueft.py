"""Die dritte Sperre bekommt dieselbe Gegenprobe wie die anderen zwei.

**Befund 271.** ``cli sperrprobe`` fragt seit Befund 58: Leistet eine
Trade-Entfernung mehr, als dieselbe Zahl beliebiger Entfernungen taete? Sie
kannte zwei Massnahmen - ``schock`` (58) und ``abkuehlung`` (44).

Das Termin-Overlay entfernt Einstiege nach derselben Bauart, und seine Wirkung
stand seit Befund 59 als **offener Auftragspunkt** im Register: *"beides
gebaut und gemessen; die Wirkung ist nicht belegt"*. Geprueft wurde sie nie
mit der Strenge, die fuer die beiden anderen gilt.

Was hier gehalten wird
----------------------
Dass die Kerzenspanne aus **derselben** Rechnung kommt wie im Lauf. Der
Kalender sperrt relativ zur Kerzenlaenge (``jetzt - spanne - vorlauf``); wer
sie in der Probe anders misst, sperrt dort andere Kerzen als die Engine - und
vergliche dann zwei Auswahlen, die es beide nicht gibt.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from data.termine import Termin, Terminart, Terminkalender


def _quelle() -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k
        for k in ast.walk(baum)
        if isinstance(k, ast.FunctionDef) and k.name == "sperrprobe"
    )
    return ast.unparse(knoten)


@pytest.fixture
def quelle() -> str:
    return _quelle()


class TestDieMassnahmeGibtEs:
    def test_kalender_steht_neben_den_anderen(self, quelle: str) -> None:
        assert "'kalender'" in quelle
        assert "'schock'" in quelle
        assert "'abkuehlung'" in quelle

    def test_die_hilfe_nennt_sie(self) -> None:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "sperrprobe"
        )
        text = ast.unparse(knoten.args)

        assert "kalender" in text

    def test_ohne_kalender_bricht_es_ab(self, quelle: str) -> None:
        """Eine leere Sperre waere keine Messung, sondern ein leerer Lauf -
        und der saehe aus wie 'kein Effekt'."""
        assert "Kein Terminkalender im Speicher" in quelle
        assert "cli termine" in quelle


class TestDieSpanneKommtAusDerEngine:
    """Der Kalender sperrt relativ zur Kerzenlaenge. Eine zweite Rechnung
    dafuer liefe auseinander, und der Unterschied waere nicht zu sehen."""

    def test_die_probe_ruft_die_engine_rechnung(self, quelle: str) -> None:
        assert "Backtester._kerzenspanne" in quelle

    def test_und_rechnet_sie_nicht_selbst(self, quelle: str) -> None:
        """Kein eigener Abstand zweier Zeitstempel - genau das waere die
        zweite Kopie."""
        assert "zeiten[1] - zeiten[0]" not in quelle

    def test_die_engine_misst_sie_aus_den_daten(self) -> None:
        """Gegenprobe an der Quelle: Die Spanne ist gemessen, nicht
        eingestellt."""
        import numpy as np

        from backtest.engine import Backtester

        zeiten = np.array(
            [
                np.datetime64(datetime(2024, 1, 1, tzinfo=UTC).replace(tzinfo=None)),
                np.datetime64(datetime(2024, 1, 2, tzinfo=UTC).replace(tzinfo=None)),
            ]
        )

        assert Backtester._kerzenspanne({"open_time": zeiten}) == timedelta(days=1)


class TestDerKalenderSperrtWieErwartet:
    """Die Eigenschaft, auf der die Maske beruht - damit sie nicht leer ist,
    ohne dass es auffaellt."""

    def _kalender(self) -> Terminkalender:
        return Terminkalender(
            [
                Termin(
                    zeitpunkt=datetime(2024, 3, 20, 18, 0, tzinfo=UTC),
                    art=Terminart.FOMC,
                )
            ]
        )

    def test_ein_termin_in_der_kerze_sperrt(self) -> None:
        """Auf Tageskerzen sperrt eine Entscheidung um 18:00 den Einstieg am
        naechsten Mitternachtsschluss."""
        kal = self._kalender()

        treffer = kal.sperre(
            datetime(2024, 3, 21, tzinfo=UTC), spanne=timedelta(days=1)
        )

        assert treffer is not None

    def test_weit_davon_entfernt_nicht(self) -> None:
        kal = self._kalender()

        assert kal.sperre(
            datetime(2024, 3, 25, tzinfo=UTC), spanne=timedelta(days=1)
        ) is None

    def test_ohne_spanne_greift_dieselbe_kerze_nicht(self) -> None:
        """Der Teil ``- spanne`` ist der wichtige - ohne ihn haenge die Regel
        an der Kerzenlaenge. Der Test haelt fest, dass er wirkt."""
        kal = self._kalender()
        jetzt = datetime(2024, 3, 21, tzinfo=UTC)

        assert kal.sperre(jetzt, spanne=timedelta(days=1)) is not None
        assert kal.sperre(jetzt, spanne=timedelta(0)) is None
