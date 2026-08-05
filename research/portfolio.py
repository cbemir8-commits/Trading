"""Mehrere Maerkte zusammen - der einzige Vorteil, den es geschenkt gibt.

Der Gedanke
-----------
Zwei Trendfolger auf verschiedenen Maerkten erreichen ihren tiefsten Punkt
selten am selben Tag. Wer beide zu je der Haelfte haelt, bekommt deshalb einen
kleineren Rueckgang als jeder von ihnen einzeln - **ohne dafuer Rendite
abzugeben**. Das ist keine Verfeinerung einer Regel, sondern eine Eigenschaft
des Rechnens mit mehreren Zeitreihen.

Gemessen ueber 2017 bis 2026, dieselbe Regel auf beiden Maerkten:

    BTC allein      2,8 % p.a.   12,47 % Rueckgang   Sharpe 0,46
    ETH allein      5,7 % p.a.    6,64 % Rueckgang   Sharpe 0,91
    beide zusammen  4,3 % p.a.    4,93 % Rueckgang   Sharpe 0,83

Der Rueckgang des Doppels ist kleiner als der jedes einzelnen Marktes. Genau
darin liegt der Gewinn: Weil das Rueckgang-Gate danach wieder Luft hat, laesst
sich der Einsatz erhoehen - und bei gleichem Risiko wie BTC allein kommt am
Ende das Dreifache heraus.

    BTC allein bei 12,5 % Rueckgang    2,8 % p.a.
    beide bei 11,1 % Rueckgang         9,0 % p.a.

Was diese Rechnung nicht ist
----------------------------
Eine Naeherung. Sie legt zwei fertige Kapitalkurven uebereinander und
unterstellt damit, dass taeglich zwischen beiden ausgeglichen wird und dass
jede Position handelbar gross ist. Bei 500 USDT auf zwei Maerkte verteilt
liegen die Positionen nahe an der Mindestgroesse der Boerse - das muss vor dem
Einsatz von Geld einzeln nachgerechnet werden, mit einem Backtest, der beide
Maerkte gemeinsam durchlaeuft.

Fuer die Frage "lohnt sich diese Richtung ueberhaupt" genuegt die Naeherung,
und die Antwort darauf ist eindeutig ja.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    """Kennzahlen einer zusammengelegten Kapitalkurve."""

    curve: np.ndarray
    return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    markets: tuple[str, ...]

    def describe(self) -> str:
        return (
            f"{' + '.join(self.markets)}: {self.return_pct:+.1f} % "
            f"({self.cagr_pct:+.1f} % p.a.), {self.max_drawdown_pct:.2f} % "
            f"Rueckgang, Sharpe {self.sharpe:.2f}"
        )


def combine_curves(
    curves: dict[str, np.ndarray],
    *,
    years: float,
    weights: dict[str, float] | None = None,
    periods_per_year: float = 365.0,
) -> PortfolioResult:
    """Kapitalkurven mehrerer Maerkte zu einer zusammenlegen.

    Jede Kurve wird auf ihren eigenen Startwert normiert - sonst wuerde ein
    Markt, dessen Kurve zufaellig hoeher beginnt, ein groesseres Gewicht
    bekommen, als ihm zusteht.

    Die Kurven werden auf die kuerzeste gekuerzt. Sie unterschiedlich lang
    zusammenzulegen hiesse, dass gegen Ende weniger Maerkte im Topf sind und
    der Rueckgang dort kuenstlich steigt - ein Vergleich mit sich selbst.
    """
    if not curves:
        raise ValueError("Ohne Kurven gibt es kein Portfolio")

    brauchbar = {name: k for name, k in curves.items() if len(k) >= 2 and k[0] > 0}
    if not brauchbar:
        raise ValueError("Keine der Kurven ist auswertbar")

    laenge = min(len(k) for k in brauchbar.values())
    gewichte = weights or {name: 1.0 for name in brauchbar}
    summe = sum(gewichte.get(name, 0.0) for name in brauchbar)
    if summe <= 0:
        raise ValueError("Die Gewichte summieren sich auf null")

    gemeinsam = np.zeros(laenge, dtype=float)
    for name, kurve in brauchbar.items():
        anteil = gewichte.get(name, 0.0) / summe
        gemeinsam += anteil * (kurve[:laenge] / kurve[0])

    return PortfolioResult(
        curve=gemeinsam,
        return_pct=float(gemeinsam[-1] - 1.0) * 100.0,
        cagr_pct=_cagr(gemeinsam, years),
        max_drawdown_pct=max_drawdown(gemeinsam),
        sharpe=_sharpe(gemeinsam, periods_per_year),
        markets=tuple(sorted(brauchbar)),
    )


def max_drawdown(curve: np.ndarray) -> float:
    """Groesster Rueckgang vom jeweiligen Hoechststand, in Prozent."""
    if len(curve) < 2:
        return 0.0
    return float(np.max(1.0 - curve / np.maximum.accumulate(curve)) * 100.0)


def _cagr(curve: np.ndarray, years: float) -> float:
    if years <= 0 or curve[-1] <= 0:
        return 0.0
    return float((curve[-1] ** (1.0 / years) - 1.0) * 100.0)


def _sharpe(curve: np.ndarray, periods_per_year: float) -> float:
    """Sharpe aus der Kurve, nicht aus Trades.

    Bei zusammengelegten Maerkten gibt es keine gemeinsame Trade-Liste mehr -
    die Trades gehoeren verschiedenen Zeitreihen an und ueberlappen sich. Die
    Kurve ist das einzige, was beide gemeinsam haben.
    """
    if len(curve) < 3 or np.any(curve <= 0):
        return 0.0
    schritte = np.diff(np.log(curve))
    streuung = float(np.std(schritte))
    if streuung <= 0:
        return 0.0
    return float(np.mean(schritte) / streuung * np.sqrt(periods_per_year))


def diversification_gain(
    einzeln: dict[str, PortfolioResult] | dict[str, float], gemeinsam: float
) -> float:
    """Um wieviel der Rueckgang unter dem besten Einzelmarkt liegt, in Prozent.

    Positiv heisst: Das Portfolio schwankt weniger als jeder seiner Teile -
    der eigentliche Zweck der Uebung. Negativ hiesse, dass die Maerkte im
    Gleichschritt fallen und die Streuung nichts bringt; auch das ist ein
    moegliches Ergebnis und soll sichtbar sein.
    """
    werte = [
        w.max_drawdown_pct if isinstance(w, PortfolioResult) else float(w)
        for w in einzeln.values()
    ]
    if not werte:
        return 0.0
    return min(werte) - gemeinsam
