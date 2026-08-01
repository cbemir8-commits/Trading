"""Besseres Chance-Risiko-Verhaeltnis - aus den Trades statt aus dem Bauch.

"Wir nehmen einfach ein weiteres Ziel" ist keine Verbesserung. Wer das Ziel
verdoppelt, halbiert ungefaehr die Trefferquote; der Erwartungswert bleibt
gleich oder wird schlechter, weil unterwegs mehr Gebuehren anfallen. Dasselbe
umgekehrt: Ein engerer Stop bringt mehr R je Bewegung, wird aber oefter
getroffen.

Das Chance-Risiko-Verhaeltnis ist deshalb **keine Stellschraube**, sondern ein
Ergebnis. Verbessern laesst es sich nur, wenn man den Trades ansieht, wo
tatsaechlich etwas verschenkt wird. Dafuer gibt es genau zwei Messgroessen,
und die Handelsengine schreibt beide bei jedem Trade mit:

**MAE - maximaler Gegenlauf.** Wie weit ist der Trade gegen uns gelaufen,
bevor er aufging? Wenn Gewinner im Mittel nur 0,4 R gegen uns liefen, der Stop
aber bei 1,0 R sitzt, ist er zu weit: Man koennte ihn enger setzen, dieselben
Gewinner behalten und bei jedem Verlierer weniger verlieren. Das erhoeht das
Chance-Risiko-Verhaeltnis, ohne an der Strategie etwas zu aendern.

**MFE - maximaler Vorlauf.** Wie weit lief der Trade zu unseren Gunsten,
bevor er endete? Wenn Trades regelmaessig 4 R erreichten und bei 2 R
geschlossen wurden, bleibt Geld liegen.

Beide Zahlen sagen etwas ueber die **schon gehandelten** Trades. Das ist ihre
Staerke und ihre Grenze zugleich: Sie zeigen, wo Spielraum ist - aber jeder
Vorschlag daraus ist eine Hypothese, die durch dieselben neun Gates muss wie
jede andere. Wer die MAE-Verteilung direkt in Parameter uebersetzt, hat nichts
gelernt, sondern nur auf einem Umweg ueberangepasst.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import structlog

from core.models import Trade

log = structlog.get_logger(__name__)

#: Unter so vielen Trades wird kein Vorschlag gemacht. Eine MAE-Verteilung aus
#: zwoelf Trades ist eine Anekdote.
MIN_TRADES = 40

#: An welchem Punkt der Verteilung der Stop sitzen soll: Bei 90 % bleiben
#: neun von zehn Gewinnern erhalten. Die uebrigen zehn Prozent zu opfern ist
#: der Preis fuer einen deutlich engeren Stop - und meist ein guter Handel.
STOP_PERCENTILE = 90


@dataclass(frozen=True, slots=True)
class ExitAnalysis:
    trades: int
    winners: int

    mae_median_r: float
    """Wie weit lief ein durchschnittlicher **Gewinner** gegen uns."""

    mae_p90_r: float
    """Der Gegenlauf, den 90 % der Gewinner nicht ueberschritten."""

    mfe_median_r: float
    mfe_p90_r: float

    captured_share: float
    """Welcher Anteil des maximal moeglichen Gewinns wurde realisiert.

    Nahe 1 heisst: Es wird nahe am Hoch ausgestiegen (unrealistisch gut -
    dann stimmt eher die Messung nicht). Unter 0,4 heisst: Es bleibt viel
    liegen."""

    suggestions: list[str]

    def describe(self) -> str:
        return (
            f"{self.trades} Trades ({self.winners} Gewinner) | "
            f"Gegenlauf der Gewinner: Median {self.mae_median_r:.2f} R, "
            f"90 % unter {self.mae_p90_r:.2f} R | "
            f"Vorlauf: Median {self.mfe_median_r:.2f} R | "
            f"realisiert {self.captured_share:.0%} des Moeglichen"
        )


def analyse_exits(trades: list[Trade], *, min_trades: int = MIN_TRADES) -> ExitAnalysis:
    """MAE und MFE auswerten und konkrete Vorschlaege ableiten."""
    rows = [_to_r(t) for t in trades]
    rows = [r for r in rows if r is not None]

    if len(rows) < min_trades:
        return ExitAnalysis(
            trades=len(rows),
            winners=0,
            mae_median_r=0.0,
            mae_p90_r=0.0,
            mfe_median_r=0.0,
            mfe_p90_r=0.0,
            captured_share=0.0,
            suggestions=[
                f"Nur {len(rows)} auswertbare Trades (noetig: {min_trades}). "
                "Eine Verteilung aus so wenigen Trades ist eine Anekdote."
            ],
        )

    winners = [r for r in rows if r.result_r > 0]
    mae_winners = [r.mae_r for r in winners] or [0.0]
    mfe_all = [r.mfe_r for r in rows]

    analysis = ExitAnalysis(
        trades=len(rows),
        winners=len(winners),
        mae_median_r=float(np.median(mae_winners)),
        mae_p90_r=float(np.percentile(mae_winners, STOP_PERCENTILE)),
        mfe_median_r=float(np.median(mfe_all)),
        mfe_p90_r=float(np.percentile(mfe_all, 90)),
        captured_share=_captured_share(rows),
        suggestions=[],
    )
    return _with_suggestions(analysis)


@dataclass(frozen=True, slots=True)
class _TradeInR:
    result_r: float
    mae_r: float
    """Gegenlauf in R - positiv gemessen (0,4 heisst: 40 % des Stops)."""
    mfe_r: float


def _to_r(trade: Trade) -> _TradeInR | None:
    """Einen Trade in R umrechnen. Ohne Stop gibt es kein R."""
    if trade.stop_loss is None:
        return None
    distance = abs(Decimal(trade.entry_price) - Decimal(trade.stop_loss))
    risk = float(distance * trade.qty)
    if risk <= 0:
        return None
    return _TradeInR(
        result_r=float(trade.net_pnl) / risk,
        mae_r=abs(float(trade.max_adverse_excursion)) / risk,
        mfe_r=abs(float(trade.max_favourable_excursion)) / risk,
    )


def _captured_share(rows: list[_TradeInR]) -> float:
    """Realisierter Gewinn im Verhaeltnis zum maximal moeglichen."""
    possible = sum(r.mfe_r for r in rows)
    if possible <= 0:
        return 0.0
    realised = sum(max(0.0, r.result_r) for r in rows)
    return realised / possible


def _with_suggestions(a: ExitAnalysis) -> ExitAnalysis:
    """Aus den Verteilungen konkrete, begruendete Hypothesen machen.

    Jede davon ist ein **Vorschlag**, kein Befund. Sie geht als neues Genom in
    dieselbe Zulassungsstrecke wie jede andere Idee - inklusive
    Mehrfachtest-Korrektur. Sonst waere das hier nur eine elegantere Art,
    dieselben Daten zweimal zu benutzen.
    """
    suggestions: list[str] = []

    # 1. Ist der Stop zu weit? Die haeufigste stille Verschwendung.
    if a.winners >= 15 and a.mae_p90_r < 0.7:
        factor = max(0.5, round(a.mae_p90_r + 0.1, 2))
        suggestions.append(
            f"Stop zu weit: 90 % der Gewinner liefen nie weiter als "
            f"{a.mae_p90_r:.2f} R gegen uns. Ein Stop bei {factor:.2f} R "
            f"haette fast alle behalten und jeden Verlierer um "
            f"{(1 - factor) * 100:.0f} % verbilligt. Das hebt das "
            f"Chance-Risiko-Verhaeltnis um rund {1 / factor:.1f}x - ohne eine "
            f"einzige Regel zu aendern."
        )

    # 2. Ist der Stop zu eng? Der umgekehrte Fall, teurer als er aussieht.
    if a.winners >= 15 and a.mae_median_r > 0.75:
        suggestions.append(
            f"Stop knapp bemessen: Schon der durchschnittliche Gewinner lief "
            f"{a.mae_median_r:.2f} R gegen uns. Viele gute Trades duerften "
            f"knapp ausgestoppt worden sein - ein weiterer Stop bei kleinerer "
            f"Position haelt das Risiko in Euro gleich."
        )

    # 3. Bleibt Gewinn liegen?
    if a.captured_share < 0.35 and a.mfe_median_r > 1.5:
        suggestions.append(
            f"Ziele moeglicherweise zu nah: Realisiert werden "
            f"{a.captured_share:.0%} des maximal Moeglichen, bei einem "
            f"typischen Vorlauf von {a.mfe_median_r:.2f} R. Ein nachgezogener "
            f"Stop auf dem Rest statt eines festen letzten Ziels waere die "
            f"naheliegende Hypothese."
        )

    # 4. Oder sind die Ziele zu weit?
    if a.mfe_p90_r < 2.0:
        suggestions.append(
            f"Ziele zu weit: Selbst die besten 10 % der Trades kamen nur auf "
            f"{a.mfe_p90_r:.2f} R Vorlauf. Ziele oberhalb davon werden nie "
            f"erreicht und binden nur Position, die frueher haette "
            f"mitgenommen werden koennen."
        )

    if not suggestions:
        suggestions.append(
            "Aus MAE und MFE ergibt sich kein klarer Spielraum. Stops und "
            "Ziele passen zu dem, was der Markt in diesen Trades hergegeben "
            "hat - eine Verbesserung muesste an den Einstiegen ansetzen, "
            "nicht an den Ausstiegen."
        )

    log.info("ausstiege.analysiert", befund=a.describe(), vorschlaege=len(suggestions))
    return ExitAnalysis(
        trades=a.trades,
        winners=a.winners,
        mae_median_r=a.mae_median_r,
        mae_p90_r=a.mae_p90_r,
        mfe_median_r=a.mfe_median_r,
        mfe_p90_r=a.mfe_p90_r,
        captured_share=a.captured_share,
        suggestions=suggestions,
    )
