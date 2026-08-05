"""Tests fuer das Zusammenlegen mehrerer Maerkte.

Der Kern ist eine Eigenschaft, die man leicht falsch implementiert und dann
nicht bemerkt: Zwei Kurven, die zu verschiedenen Zeiten fallen, muessen
zusammen **weniger** Rueckgang haben als jede fuer sich. Wer die Kurven
addiert statt zu normieren, oder wer sie unterschiedlich lang zusammenlegt,
bekommt Zahlen, die plausibel aussehen und falsch sind.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.portfolio import (
    combine_curves,
    diversification_gain,
    max_drawdown,
)


def welle(laenge: int, tief_bei: float, tiefe: float = 0.3) -> np.ndarray:
    """Eine Kurve, die genau an einer Stelle einbricht und sich erholt."""
    kurve = np.ones(laenge)
    mitte = int(laenge * tief_bei)
    breite = max(2, laenge // 10)
    for i in range(laenge):
        abstand = abs(i - mitte)
        if abstand < breite:
            kurve[i] = 1.0 - tiefe * (1 - abstand / breite)
    return kurve


class TestZusammenlegen:
    def test_streuung_senkt_den_rueckgang(self) -> None:
        """Der ganze Zweck der Uebung, an einem gebauten Fall.

        Zwei Kurven brechen an verschiedenen Stellen um je 30 % ein. Zusammen
        darf der Rueckgang deutlich kleiner sein - jeweils traegt nur die
        Haelfte des Kapitals den Einbruch.
        """
        a = welle(400, 0.3)
        b = welle(400, 0.7)

        einzeln_a = max_drawdown(a)
        einzeln_b = max_drawdown(b)
        zusammen = combine_curves({"A": a, "B": b}, years=1.0)

        assert einzeln_a == pytest.approx(30.0, abs=1.0)
        assert einzeln_b == pytest.approx(30.0, abs=1.0)
        assert zusammen.max_drawdown_pct < 20.0, "Streuung hat nichts gebracht"

    def test_gleichlauf_bringt_nichts(self) -> None:
        """Die Gegenprobe - und ein moegliches Ergebnis.

        Brechen beide Maerkte zugleich ein, gibt es nichts zu streuen. Das
        muss sichtbar werden statt weggerechnet: In Krypto fallen die Maerkte
        oft gemeinsam, und ein Verfahren, das dort trotzdem Entwarnung gibt,
        waere gefaehrlich.
        """
        a = welle(400, 0.5)
        b = welle(400, 0.5)

        zusammen = combine_curves({"A": a, "B": b}, years=1.0)

        assert zusammen.max_drawdown_pct == pytest.approx(30.0, abs=1.0)

    def test_jede_kurve_wird_normiert(self) -> None:
        """Sonst bekaeme ein Markt mit hoeherem Startwert mehr Gewicht.

        Der Fehler ist unsichtbar: Das Ergebnis sieht wie ein Portfolio aus
        und ist in Wahrheit fast nur der eine Markt.
        """
        klein = np.linspace(1.0, 1.2, 100)
        gross = np.linspace(1000.0, 1200.0, 100)

        zusammen = combine_curves({"klein": klein, "gross": gross}, years=1.0)

        # Beide steigen um 20 %, also muss das Portfolio um 20 % steigen -
        # unabhaengig von den Startwerten.
        assert zusammen.return_pct == pytest.approx(20.0, abs=0.1)

    def test_kuerzt_auf_die_kuerzeste(self) -> None:
        """Sonst sind gegen Ende weniger Maerkte im Topf.

        Der Rueckgang stiege dort kuenstlich an, und das Ergebnis waere ein
        Vergleich des Portfolios mit sich selbst.
        """
        lang = np.linspace(1.0, 2.0, 300)
        kurz = np.linspace(1.0, 1.5, 100)

        zusammen = combine_curves({"lang": lang, "kurz": kurz}, years=1.0)

        assert len(zusammen.curve) == 100

    def test_gewichte_wirken(self) -> None:
        steigend = np.linspace(1.0, 2.0, 100)
        flach = np.ones(100)

        viel = combine_curves(
            {"a": steigend, "b": flach}, years=1.0, weights={"a": 3.0, "b": 1.0}
        )
        gleich = combine_curves({"a": steigend, "b": flach}, years=1.0)

        assert viel.return_pct > gleich.return_pct

    def test_leere_eingabe_wird_abgelehnt(self) -> None:
        with pytest.raises(ValueError, match="Portfolio"):
            combine_curves({}, years=1.0)

    def test_unbrauchbare_kurven_werden_abgelehnt(self) -> None:
        with pytest.raises(ValueError, match="auswertbar"):
            combine_curves({"a": np.array([1.0])}, years=1.0)

    def test_kennzahlen_stimmen(self) -> None:
        kurve = np.linspace(1.0, 1.5, 365 * 2)

        ergebnis = combine_curves({"a": kurve}, years=2.0)

        assert ergebnis.return_pct == pytest.approx(50.0, abs=0.1)
        assert ergebnis.cagr_pct == pytest.approx(22.5, abs=0.5)
        assert ergebnis.max_drawdown_pct == pytest.approx(0.0, abs=0.01)
        assert ergebnis.markets == ("a",)


class TestStreuungsgewinn:
    def test_positiv_wenn_es_hilft(self) -> None:
        einzeln = {"BTC": 12.5, "ETH": 6.6}

        assert diversification_gain(einzeln, 4.9) == pytest.approx(1.7, abs=0.1)

    def test_negativ_wenn_nicht(self) -> None:
        """Auch das ist ein Ergebnis und soll sichtbar sein."""
        einzeln = {"BTC": 12.5, "ETH": 6.6}

        assert diversification_gain(einzeln, 9.0) < 0
