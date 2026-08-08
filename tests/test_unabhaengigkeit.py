"""Effektive statt roher Stichprobe - das Loch im Deflated-Sharpe-Gate.

Gefunden beim Ausmessen eines Hebels, den ich nutzen wollte: Dieselbe Regel mit
drei Perioden gleichzeitig gehandelt, verdreifacht die Zahl der Trades und hob
den Deflated Sharpe von 0,802 auf 0,999 - ohne dass die Strategie besser
geworden waere. Auf ETH korrelierten die Fenstergewinne zweier Perioden mit
0,884.

``test_drei_gleiche_beine_zaehlen_wie_eines`` ist der Test, um den es geht.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.unabhaengigkeit import (
    MIND_FENSTER,
    effektive_stichprobe,
    mittlere_korrelation,
)


def reihe(n: int = 30, saat: int = 1) -> list[float]:
    return list(np.random.default_rng(saat).normal(5.0, 20.0, n))


def handelsreihe(anzahl: int, *, saat: int = 4) -> list:
    """Trades mit einem echten, aber massvollen Vorteil."""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from core.models import Side, Trade

    rng = np.random.default_rng(saat)
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Trade(
            trade_id=f"t{i}",
            symbol="BTCUSDT",
            side=Side.BUY,
            strategy_id="test",
            entry_time=t0 + timedelta(hours=4 * i),
            entry_price=Decimal("100000"),
            exit_time=t0 + timedelta(hours=4 * i + 2),
            exit_price=Decimal("100000"),
            qty=Decimal("0.006"),
            gross_pnl=Decimal(str(round(float(rng.normal(3.0, 12.0)), 2))),
            fees=Decimal("0.24"),
            stop_loss=Decimal("99400"),
        )
        for i in range(anzahl)
    ]


class TestMittlereKorrelation:
    def test_identische_beine_geben_eins(self) -> None:
        r = reihe()

        assert mittlere_korrelation({"a": r, "b": list(r)}) == pytest.approx(1.0)

    def test_unabhaengige_beine_geben_ungefaehr_null(self) -> None:
        k = mittlere_korrelation({"a": reihe(200, 1), "b": reihe(200, 2)})

        assert abs(k) < 0.2

    def test_negative_korrelation_wird_bei_null_gekappt(self) -> None:
        """**Kein Bonus fuer gegenlaeufige Beine.**

        Sonst liesse sich die effektive Zahl ueber die rohe heben - dieselbe
        Umgehung von der anderen Seite. Die Korrektur darf nur strenger
        machen, nie milder.
        """
        r = reihe(100)
        gegen = [-x for x in r]

        assert mittlere_korrelation({"a": r, "b": gegen}) == 0.0

    def test_ein_bein_ohne_streuung_gilt_als_abhaengig(self) -> None:
        """Ein Bein, das immer dasselbe liefert, traegt keine eigene
        Information - im Zweifel gegen die Strategie."""
        k = mittlere_korrelation({"a": reihe(50), "b": [1.0] * 50})

        assert k == pytest.approx(1.0)

    def test_zu_kurze_reihen_werden_uebergangen(self) -> None:
        assert mittlere_korrelation({"a": [1.0, 2.0], "b": [1.0, 3.0]}) == 0.0


class TestEffektiveStichprobe:
    def test_ein_bein_bleibt_unveraendert(self) -> None:
        """Der heutige Spitzenkandidat darf von der Korrektur nicht beruehrt
        werden - er hat je Markt genau ein Bein."""
        e = effektive_stichprobe(154, {"BTC": reihe(31)})

        assert e.effektiv == 154
        assert e.faktor == 1.0
        assert "keine Korrektur" in e.bericht()

    def test_ohne_angaben_bleibt_alles_wie_es_war(self) -> None:
        assert effektive_stichprobe(154, None).effektiv == 154
        assert effektive_stichprobe(154, {}).effektiv == 154

    def test_drei_gleiche_beine_zaehlen_wie_eines(self) -> None:
        """**Der Test, um den es geht.**

        Wer eine Position in drei fast gleiche Teile zerlegt, verdreifacht die
        Trade-Zahl und weiss keinen Deut mehr.
        """
        r = reihe(31)
        e = effektive_stichprobe(481, {"a": r, "b": list(r), "c": list(r)})

        assert e.korrelation == pytest.approx(1.0)
        assert e.effektiv == pytest.approx(481 / 3, rel=0.02)

    def test_drei_unabhaengige_beine_zaehlen_voll(self) -> None:
        e = effektive_stichprobe(
            481, {"a": reihe(200, 1), "b": reihe(200, 2), "c": reihe(200, 3)}
        )

        assert e.effektiv > 481 * 0.75

    def test_teilweise_korreliert_liegt_dazwischen(self) -> None:
        """Die gemessene Lage: BTC-Beine unkorreliert, ETH-Beine bei 0,88."""
        basis = np.asarray(reihe(60, 7))
        rng = np.random.default_rng(9)
        aehnlich = list(basis + rng.normal(0, 5, 60))
        anders = reihe(60, 11)

        e = effektive_stichprobe(
            481, {"a": list(basis), "b": aehnlich, "c": anders}
        )

        assert 481 / 3 < e.effektiv < 481

    def test_zu_wenige_fenster_rechnen_konservativ(self) -> None:
        """Ohne belastbare Schaetzung im Zweifel gegen die Strategie."""
        kurz = [1.0, 2.0, 3.0]
        e = effektive_stichprobe(300, {"a": kurz, "b": kurz, "c": kurz})

        assert e.korrelation == 1.0
        assert e.effektiv == 100

    def test_effektiv_nie_ueber_roh(self) -> None:
        """Die Korrektur darf nur nach unten wirken."""
        for saat in range(5):
            e = effektive_stichprobe(
                400,
                {
                    "a": reihe(40, saat),
                    "b": [-x for x in reihe(40, saat)],
                    "c": reihe(40, saat + 100),
                },
            )
            assert e.effektiv <= 400

    def test_bericht_nennt_die_zahlen(self) -> None:
        r = reihe(31)
        text = effektive_stichprobe(481, {"a": r, "b": list(r), "c": list(r)}).bericht()

        assert "481 rohe Trades" in text
        assert "3 Beinen" in text


class TestGateNutzung:
    """Das Gate rechnet mit der effektiven Zahl - und sagt es dazu."""

    def test_gate_wertet_korrelierte_beine_ab(self) -> None:
        from backtest.walkforward import WalkForwardReport
        from research.gates import GateThresholds, gate_deflated_sharpe

        trades = handelsreihe(300)
        t = GateThresholds()

        roh = gate_deflated_sharpe(trades, 95, t, None)
        r = reihe(31)
        korreliert = gate_deflated_sharpe(
            trades, 95, t, {"a": r, "b": list(r), "c": list(r)}
        )

        assert korreliert.value < roh.value, (
            "Drei gleiche Beine duerfen den Wert nicht heben"
        )
        assert isinstance(WalkForwardReport().beine, dict)

    def test_ein_bein_aendert_nichts_am_gate(self) -> None:
        from research.gates import GateThresholds, gate_deflated_sharpe

        trades = handelsreihe(300)
        t = GateThresholds()

        assert gate_deflated_sharpe(trades, 95, t, None).value == pytest.approx(
            gate_deflated_sharpe(trades, 95, t, {"nur_eines": reihe(31)}).value
        )


def test_mindestfenster_ist_festgehalten() -> None:
    assert MIND_FENSTER == 8


class TestBootstrap:
    """Der Bootstrap misst, die Formel schaetzt. Deshalb hat er Vorrang."""

    def test_unabhaengige_bloecke_verlieren_kaum_etwas(self) -> None:
        from research.unabhaengigkeit import bootstrap_stichprobe

        rng = np.random.default_rng(3)
        bloecke = [list(rng.normal(3.0, 12.0, 5)) for _ in range(30)]

        n_eff = bootstrap_stichprobe(bloecke, ziehungen=1500)

        assert n_eff is not None
        assert n_eff > 150 * 0.8

    def test_gleichlaufende_bloecke_verlieren_viel(self) -> None:
        """Wenn innerhalb eines Fensters alle Trades dasselbe machen, ist ein
        Fenster eine Beobachtung - nicht fuenf."""
        from research.unabhaengigkeit import bootstrap_stichprobe

        rng = np.random.default_rng(5)
        bloecke = [[float(w)] * 5 for w in rng.normal(3.0, 12.0, 30)]

        n_eff = bootstrap_stichprobe(bloecke, ziehungen=1500)

        assert n_eff is not None
        assert n_eff < 150 * 0.35, f"Erwartet rund 30, gemessen {n_eff}"

    def test_zu_wenige_bloecke_geben_none(self) -> None:
        from research.unabhaengigkeit import bootstrap_stichprobe

        assert bootstrap_stichprobe([[1.0, 2.0]] * 3) is None

    def test_ohne_streuung_gibt_none(self) -> None:
        from research.unabhaengigkeit import bootstrap_stichprobe

        assert bootstrap_stichprobe([[5.0] * 5 for _ in range(20)]) is None

    def test_nie_mehr_als_roh(self) -> None:
        from research.unabhaengigkeit import bootstrap_stichprobe

        rng = np.random.default_rng(11)
        bloecke = [list(rng.normal(0.0, 1.0, 4)) for _ in range(40)]

        n_eff = bootstrap_stichprobe(bloecke, ziehungen=1000)

        assert n_eff is not None and n_eff <= 160

    def test_bootstrap_schlaegt_die_formel(self) -> None:
        """Liegen Bloecke vor, wird gemessen statt geschaetzt."""
        rng = np.random.default_rng(7)
        bloecke = [list(rng.normal(3.0, 12.0, 5)) for _ in range(30)]
        r = reihe(30)

        e = effektive_stichprobe(150, {"a": r, "b": list(r)}, bloecke)

        assert e.effektiv > 150 * 0.7, (
            "Die Formel haette wegen Korrelation 1,0 auf 75 gekuerzt - "
            "der Bootstrap sieht, dass die Trades unabhaengig sind"
        )
        assert "Block-Bootstrap" in e.bericht()
