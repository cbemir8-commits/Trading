"""Das Gate hat zwei Bedingungen und einen Namen.

**Befund 267.** ``gate_benchmark`` prueft zweierlei: risikobereinigt besser als
Halten, und eine Jahresrendite ueber der Betriebsschwelle. Faellt es allein an
der zweiten, standen in ``value`` und ``threshold`` bis hierher trotzdem
Rendite und Messlatte - also die Bedingung, die **bestanden** ist.

Am Bestand gemessen: Wert 192,012 gegen Schwelle 38,031, Status
DURCHGEFALLEN. Wer die Zahlen liest, sieht das Fuenffache der Huerde und ein
rotes Gate. Sie gehen in die Bestenliste, das Journal, ``gatelage`` und jede
Gate-Tabelle, und sie sind die einzige Zahl, die sagt, **wie weit** ein Gate
offen ist.

Was hier gehalten wird
----------------------
Der bindende Fall meldet die bindende Bedingung - und die anderen Faelle
melden weiter, was sie immer gemeldet haben. Ein Gate, das besteht, hat an
beiden Bedingungen bestanden; dort gibt es nichts zu waehlen.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from research.gates import GateStatus, GateThresholds, gate_benchmark


@dataclass
class _Fenster:
    test_start: object
    test_end: object


@dataclass
class _Scheibe:
    window: _Fenster


@dataclass
class _Kennzahlen:
    total_return_pct: float
    max_drawdown_pct: float
    cagr_pct: float


@dataclass
class _Bericht:
    windows: list
    combined: _Kennzahlen


def _bericht(*, rendite: float, cagr: float, rueckgang: float = 10.0) -> _Bericht:
    import pandas as pd

    start = pd.Timestamp("2020-01-01", tz="UTC")
    ende = pd.Timestamp("2021-01-01", tz="UTC")
    return _Bericht(
        windows=[_Scheibe(_Fenster(start, ende))],
        combined=_Kennzahlen(rendite, rueckgang, cagr),
    )


@pytest.fixture
def kerzen():
    """Ein ruhiger Markt: Halten bringt wenig und faellt kaum.

    Damit liegt die Messlatte niedrig und der Fall "risikobereinigt besser,
    aber zu wenig im Jahr" ist ueberhaupt herstellbar.
    """
    import numpy as np
    import pandas as pd

    zeiten = pd.date_range("2020-01-01", periods=360, freq="D", tz="UTC")
    return pd.DataFrame(
        {"open_time": zeiten, "close": 100.0 * np.exp(np.arange(360) * 0.0002)}
    )


class TestDerBindendeFallMeldetDieBindendeBedingung:
    def test_nur_die_betriebsschwelle_faellt(self, kerzen) -> None:
        """Der Fall des Bestands: weit ueber der Messlatte, unter der
        Schwelle."""
        t = GateThresholds()
        ergebnis = gate_benchmark(_bericht(rendite=190.0, cagr=14.34), kerzen, t)

        assert ergebnis.status is GateStatus.FAIL
        assert ergebnis.value == pytest.approx(14.34)
        assert ergebnis.threshold == pytest.approx(t.min_cagr_pct)

    def test_und_der_abstand_zeigt_in_die_richtige_richtung(self, kerzen) -> None:
        """Die eine Zahl, die sagt, wie weit ein Gate offen ist. Vor Befund
        267 war sie hier positiv - bei einem Durchfaller."""
        ergebnis = gate_benchmark(_bericht(rendite=190.0, cagr=14.34), kerzen,
                                  GateThresholds())

        assert ergebnis.value < ergebnis.threshold

    def test_die_meldung_nennt_beides(self, kerzen) -> None:
        """Die Begruendung war schon immer richtig - nur die Zahlen nicht."""
        ergebnis = gate_benchmark(_bericht(rendite=190.0, cagr=14.34), kerzen,
                                  GateThresholds())

        assert "risikobereinigt besser" in ergebnis.message
        assert "lohnt der Betrieb nicht" in ergebnis.message


class TestDieAnderenFaelleBleibenWieSieWaren:
    """Bestehende Eintraege duerfen sich nicht verschieben - 45 Zeilen
    Bestenliste und jedes Journal haengen an diesen Zahlen."""

    def test_wer_die_messlatte_reisst_meldet_die_messlatte(self, kerzen) -> None:
        ergebnis = gate_benchmark(_bericht(rendite=-5.0, cagr=-5.0), kerzen,
                                  GateThresholds())

        assert ergebnis.status is GateStatus.FAIL
        assert ergebnis.value == pytest.approx(-5.0)
        # Die Latte, nicht die Betriebsschwelle.
        assert ergebnis.threshold != pytest.approx(GateThresholds().min_cagr_pct)
        assert "schlechter als Nichtstun" in ergebnis.message

    def test_wer_beides_reisst_meldet_auch_die_messlatte(self, kerzen) -> None:
        """Faellt die Messlatte-Bedingung, ist sie die bindende - auch wenn
        die Betriebsschwelle ebenfalls gerissen ist."""
        ergebnis = gate_benchmark(_bericht(rendite=-20.0, cagr=-3.0), kerzen,
                                  GateThresholds())

        assert ergebnis.value == pytest.approx(-20.0)
        assert ergebnis.threshold != pytest.approx(GateThresholds().min_cagr_pct)

    def test_wer_besteht_meldet_die_messlatte(self, kerzen) -> None:
        """Ein bestandenes Gate hat an beiden Bedingungen bestanden - dort
        gibt es nichts zu waehlen, und die Zahl bleibt, wie sie war."""
        ergebnis = gate_benchmark(_bericht(rendite=190.0, cagr=25.0), kerzen,
                                  GateThresholds())

        assert ergebnis.status is GateStatus.PASS
        assert ergebnis.value == pytest.approx(190.0)
        assert ergebnis.threshold != pytest.approx(GateThresholds().min_cagr_pct)

    def test_ohne_fenster_wird_uebersprungen(self, kerzen) -> None:
        leer = _Bericht(windows=[], combined=_Kennzahlen(0.0, 0.0, 0.0))

        assert gate_benchmark(leer, kerzen, GateThresholds()).status is GateStatus.SKIP
