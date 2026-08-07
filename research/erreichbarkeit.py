"""Was fehlt noch - und was kostet jeder weitere Versuch?

Das Deflated-Sharpe-Gate ist die haerteste Huerde im System, und es hat eine
Eigenschaft, die man leicht uebersieht: **Es wird mit jedem Versuch schwerer.**
Die Zahl der getesteten Hypothesen steht im Zaehler der Huerde, nicht nur in
der Buchhaltung. Gemessen am aktuellen Kandidaten (154 Trades, Sharpe je Trade
0,251):

    10 Versuche  -> DSR 0,994
    50 Versuche  -> DSR 0,916
    95 Versuche  -> DSR 0,837
   200 Versuche  -> DSR 0,713
   500 Versuche  -> DSR 0,535

Derselbe Kandidat, dieselben Daten, dieselbe Rechnung. Nur die Suche davor war
laenger. Wer breit sucht, macht das, was er findet, wertlos - und zwar
rechnerisch, nicht metaphorisch.

Daraus folgt eine Arbeitsweise, die diesem Projekt bisher gefehlt hat: **Vor
jedem weiteren Versuch ausrechnen, was er kostet und was er bringen muesste.**
Ein Einfall, der den Sharpe je Trade um 2 % hebt, aber fuenf Versuche kostet,
ist ein Rueckschritt. Das laesst sich vorher wissen, nicht erst hinterher.

Dieses Modul beantwortet drei Fragen:

* Wie viele Trades braeuchte es bei unveraenderter Qualitaet?
* Welchen Sharpe je Trade braeuchte es bei unveraenderter Trade-Zahl?
* Was kostet ein weiterer Versuch in DSR-Punkten?
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from research.gates import deflated_sharpe_ratio

#: Obergrenze fuer die Suche nach der noetigen Trade-Zahl. Wer hier anschlaegt,
#: hat kein Datenproblem, sondern kein Vorteil.
MAX_TRADES = 100_000

#: Obergrenze fuer den noetigen Sharpe je Trade. 3,0 je Trade waere ein
#: Jahrhundertfund; darueber zu suchen hat keinen Sinn.
MAX_SHARPE = 3.0


def _dsr(sharpe: float, trades: int, trials: int, skew: float, kurtosis: float) -> float:
    return deflated_sharpe_ratio(
        observed_sharpe=sharpe,
        trials=max(trials, 1),
        sample_size=trades,
        skew=skew,
        kurtosis=kurtosis,
    )


def noetige_trades(
    *,
    sharpe: float,
    trials: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    ziel: float = 0.95,
) -> int | None:
    """Wie viele Trades braeuchte es bei **unveraenderter** Qualitaet je Trade?

    ``None``, wenn auch sehr viele Trades nicht genuegen - dann liegt es nicht
    an der Stichprobe.

    Gesucht wird mit Bisektion statt schrittweise: Der Wert waechst monoton in
    der Trade-Zahl, und bei einem Kandidaten mit schwachem Vorteil kann die
    Antwort im Zehntausenderbereich liegen.
    """
    if sharpe <= 0:
        return None
    if _dsr(sharpe, MAX_TRADES, trials, skew, kurtosis) < ziel:
        return None

    tief, hoch = 3, MAX_TRADES
    while tief < hoch:
        mitte = (tief + hoch) // 2
        if _dsr(sharpe, mitte, trials, skew, kurtosis) < ziel:
            tief = mitte + 1
        else:
            hoch = mitte
    return tief


def noetiger_sharpe(
    *,
    trades: int,
    trials: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    ziel: float = 0.95,
    schritte: int = 80,
) -> float | None:
    """Welchen Sharpe je Trade braeuchte es bei **unveraenderter** Trade-Zahl?

    ``None``, wenn auch ein sehr hoher Sharpe nicht genuegt - das passiert bei
    sehr kleinen Stichproben, wo die Wurzel aus ``n-1`` alles erstickt.
    """
    if trades < 3:
        return None
    if _dsr(MAX_SHARPE, trades, trials, skew, kurtosis) < ziel:
        return None

    tief, hoch = 0.0, MAX_SHARPE
    for _ in range(schritte):
        mitte = (tief + hoch) / 2
        if _dsr(mitte, trades, trials, skew, kurtosis) < ziel:
            tief = mitte
        else:
            hoch = mitte
    return hoch


@dataclass(frozen=True, slots=True)
class Erreichbarkeit:
    """Der Abstand zum Deflated-Sharpe-Gate, in beide Richtungen aufgeloest."""

    trades: int
    sharpe: float
    trials: int
    dsr: float
    ziel: float
    trades_noetig: int | None
    sharpe_noetig: float | None
    kosten_naechster_versuch: float
    kosten_zehn_versuche: float

    @property
    def bestanden(self) -> bool:
        return self.dsr >= self.ziel

    @property
    def fehlende_trades(self) -> int | None:
        if self.trades_noetig is None:
            return None
        return max(0, self.trades_noetig - self.trades)

    def bericht(self) -> str:
        zeilen = [
            f"Deflated Sharpe {self.dsr:.3f} (noetig {self.ziel:.2f}) bei "
            f"{self.trades} Trades, Sharpe je Trade {self.sharpe:.3f}, "
            f"{self.trials} Versuchen",
        ]
        if self.bestanden:
            zeilen.append("Bestanden.")
            return "\n".join(zeilen)

        if self.trades_noetig is None:
            zeilen.append(
                "Auch beliebig viele Trades genuegen nicht - der Vorteil je "
                "Trade ist zu klein. Mehr Daten helfen hier nicht."
            )
        else:
            zeilen.append(
                f"Bei gleicher Qualitaet je Trade: {self.trades_noetig} Trades "
                f"noetig, es fehlen {self.fehlende_trades}."
            )
        if self.sharpe_noetig is None:
            zeilen.append(
                "Bei dieser Trade-Zahl genuegt kein Sharpe je Trade - die "
                "Stichprobe ist zu klein."
            )
        else:
            zeilen.append(
                f"Bei gleicher Trade-Zahl: Sharpe je Trade {self.sharpe_noetig:.3f} "
                f"noetig (heute {self.sharpe:.3f}, Faktor "
                f"{self.sharpe_noetig / self.sharpe:.2f})."
                if self.sharpe > 0
                else f"Bei gleicher Trade-Zahl: Sharpe je Trade "
                f"{self.sharpe_noetig:.3f} noetig."
            )
        zeilen.append(
            f"Ein weiterer Versuch kostet {self.kosten_naechster_versuch:.4f} "
            f"DSR-Punkte, zehn kosten {self.kosten_zehn_versuche:.4f}."
        )
        if self.fehlende_trades:
            zeilen.append(
                "Mehr Daten kosten keinen Versuch - eine neue Idee schon. "
                "Erst die Datenbasis ausschoepfen, dann suchen."
            )
        return "\n".join(zeilen)


def bewerte(
    *,
    trades: int,
    sharpe: float,
    trials: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    ziel: float = 0.95,
) -> Erreichbarkeit:
    """Den Abstand zum Gate in allen drei Richtungen ausrechnen."""
    jetzt = _dsr(sharpe, trades, trials, skew, kurtosis)
    return Erreichbarkeit(
        trades=trades,
        sharpe=sharpe,
        trials=trials,
        dsr=jetzt,
        ziel=ziel,
        trades_noetig=noetige_trades(
            sharpe=sharpe, trials=trials, skew=skew, kurtosis=kurtosis, ziel=ziel
        ),
        sharpe_noetig=noetiger_sharpe(
            trades=trades, trials=trials, skew=skew, kurtosis=kurtosis, ziel=ziel
        ),
        kosten_naechster_versuch=jetzt
        - _dsr(sharpe, trades, trials + 1, skew, kurtosis),
        kosten_zehn_versuche=jetzt - _dsr(sharpe, trades, trials + 10, skew, kurtosis),
    )


def kennzahlen_aus_pnl(pnls) -> tuple[int, float, float, float]:
    """Trade-Zahl, Sharpe je Trade, Schiefe und Woelbung - wie im Gate.

    Genau dieselbe Rechnung wie in ``research/gates.py``: auf den Euro-Ergebnissen,
    nicht auf R-Vielfachen. Der Unterschied ist nicht kosmetisch - halb
    dimensionierte Trades wirken in Euro anders als in R, und wer die beiden
    verwechselt, rechnet an der Huerde vorbei.
    """
    import numpy as np

    werte = np.asarray([float(p) for p in pnls], dtype=float)
    if len(werte) < 3:
        return len(werte), 0.0, 0.0, 3.0
    spread = float(np.std(werte, ddof=1))
    if spread <= 0 or math.isnan(spread):
        return len(werte), 0.0, 0.0, 3.0
    zentriert = (werte - float(np.mean(werte))) / spread
    return (
        len(werte),
        float(np.mean(werte)) / spread,
        float(np.mean(zentriert**3)),
        float(np.mean(zentriert**4)),
    )
