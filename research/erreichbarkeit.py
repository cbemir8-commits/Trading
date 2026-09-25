"""Was fehlt noch - und was kostet jeder weitere Versuch?

Das Deflated-Sharpe-Gate ist die haerteste Huerde im System, und es hat eine
Eigenschaft, die man leicht uebersieht: **Es wird mit jedem Versuch schwerer.**
Die Zahl der getesteten Hypothesen steht im Zaehler der Huerde, nicht nur in
der Buchhaltung. Gemessen am Spitzenkandidaten am Spot-Punkt (115 wirksame
Trades, Guete je Trade 0,2708 - ``referenz.SPOTPUNKT``):

     1 Versuch   -> DSR 1,000
    10 Versuche  -> DSR 0,989
    21 Versuche  -> DSR 0,953   <- hier faellt er unter die Latte
    50 Versuche  -> DSR 0,856
   203 Versuche  -> DSR 0,583   <- der Stand
   500 Versuche  -> DSR 0,390

Derselbe Kandidat, dieselben Daten, dieselbe Rechnung. Nur die Suche davor war
laenger. Wer breit sucht, macht das, was er findet, wertlos - und zwar
rechnerisch, nicht metaphorisch.

Daraus folgt eine Arbeitsweise, die diesem Projekt bisher gefehlt hat: **Vor
jedem weiteren Versuch ausrechnen, was er kostet und was er bringen muesste.**
Ein Einfall, der den Sharpe je Trade um 2 % hebt, aber fuenf Versuche kostet,
ist ein Rueckschritt. Das laesst sich vorher wissen, nicht erst hinterher.

Was die Tabelle **nicht** sagt - Befund 327
-------------------------------------------
Sie laedt dazu ein, sie rueckwaerts zu lesen: "bei 21 Versuchen stuende er
drueber, also bringt jeder gesparte Versuch etwas". Beides ist falsch.

**Der Zaehler faellt nicht.** ``admission.save_trials`` laesst einen
niedrigeren Stand nicht durch, weil ein fallender Zaehler die
Mehrfachtest-Korrektur milder machen wuerde. Die 203 sind ausgegeben; von 203
auf 21 fuehrt kein Weg.

**Und die Betraege sind klein.** Von 203 aus kostet ein weiterer Versuch
0,0011 Punkte, zehn kosten 0,0106 - gegen eine Luecke von 0,3673. Selbst
hundert vermiedene Versuche decken einen Bruchteil davon.

Versuchsdisziplin **haelt** den Abstand also, sie schliesst ihn nicht.
Geschlossen wird er ueber die Stichprobe (190 wirksame Trades noetig, 115 da)
oder ueber die Guete je Trade (0,3374 noetig, 0,2708 da) - und von beidem ist
das erste das, was mehr Historie kauft.

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
    effektiv: int,
    trials: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    ziel: float = 0.95,
    schritte: int = 80,
) -> float | None:
    """Welchen Sharpe je Trade braeuchte es bei **unveraenderter** Stichprobe?

    ``effektiv`` ist die **effektive** Stichprobe, nicht die rohe Trade-Zahl.
    Der Name sagt das, seit der Parameter ``trades`` hiess und genau deshalb
    falsch bedient wurde (Befund 139): Vor Befund 135 waren beide Zahlen fuer
    den Kandidaten gleich - 152 -, und jeder Aufruf mit der rohen Zahl war
    richtig. Befund 135 hat sie getrennt (152 roh, 112 effektiv), und die
    Aufrufe blieben stehen. Die Latte lag danach 14 % zu tief.

    Wer nur die rohe Zahl hat, bekommt mit ihr eine **Untergrenze** der Latte,
    keine Latte: Die effektive Stichprobe ist hoechstens so gross wie die rohe,
    und je kleiner sie ist, desto hoeher liegt die Latte.

    ``None``, wenn auch ein sehr hoher Sharpe nicht genuegt - das passiert bei
    sehr kleinen Stichproben, wo die Wurzel aus ``n-1`` alles erstickt.
    """
    if effektiv < 3:
        return None
    if _dsr(MAX_SHARPE, effektiv, trials, skew, kurtosis) < ziel:
        return None

    tief, hoch = 0.0, MAX_SHARPE
    for _ in range(schritte):
        mitte = (tief + hoch) / 2
        if _dsr(mitte, effektiv, trials, skew, kurtosis) < ziel:
            tief = mitte
        else:
            hoch = mitte
    return hoch


def erlaubter_gueteverlust(
    *,
    effektiv: int,
    guete: float,
    trials: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    ziel: float = 0.95,
) -> float | None:
    """Wie weit die Guete je Trade fallen darf, wenn die Stichprobe waechst.

    **Die Bedingung unter ``AUSSICHT``** (Befund 328). Die Entfernung zur
    Schwelle steht dort in Tagen: 75 fehlende Beobachtungen, mindestens 2152
    Tage. Gerechnet ist sie mit ``noetige_trades``, und dessen Zusage lautet
    ausdruecklich *"bei **unveraenderter** Qualitaet je Trade"*. Wer sie liest,
    liest eine Zeitangabe; die Bedingung daneben steht nirgends.

    Sie ist nicht akademisch. Im einzigen gemessenen Fall, in dem das Projekt
    Beobachtungen tatsaechlich hinzugewonnen hat, ist sie gebrochen
    (``reports/marktkombinationen``, 13.09.):

        BTC+ETH             158 Trades   DSR 0,5881   CAGR 14,34 %
        BTC+ETH+LTC         266 Trades   DSR 0,4855   CAGR 11,50 %
        BTC+ETH+XRP         267 Trades   DSR 0,4609   CAGR 11,32 %
        BTC+ETH+LTC+XRP     375 Trades   DSR 0,4175   CAGR  9,95 %

    Zweieinhalbmal so viele Trades, und der Deflated Sharpe faellt um 29 %.

    Rueckgabe: der Anteil, um den die Guete fallen darf, als Zahl zwischen 0
    und 1. Bei ``effektiv`` gleich ``noetig`` ist er null - dort ist kein
    Verlust mehr erlaubt. ``None``, wenn diese Stichprobe die Schwelle mit
    keiner Guete erreicht.

    Die Faustregel dahinter: Die Pruefgroesse waechst mit ``Guete * Wurzel(n)``,
    also verlangt eine halb so gute Regel rund die vierfache Stichprobe. **Mehr
    Beobachtungen helfen, solange die Guete langsamer faellt als eins durch
    Wurzel n.**
    """
    if guete <= 0:
        return None
    noetig = noetiger_sharpe(
        effektiv=effektiv, trials=trials, skew=skew, kurtosis=kurtosis, ziel=ziel
    )
    if noetig is None:
        return None
    return 1.0 - noetig / guete


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

    #: Die Form der Trade-Verteilung, mit der ``dsr`` gerechnet wurde. Sie
    #: gehoert hierher, seit ``kosten`` dieselbe Rechnung fuer eine andere
    #: Versuchszahl noch einmal anstellt - mit den Vorgaben statt den
    #: gemessenen Werten kaeme eine andere Kurve heraus als die, auf der
    #: ``dsr`` liegt.
    schiefe: float = 0.0
    woelbung: float = 3.0

    @property
    def bestanden(self) -> bool:
        return self.dsr >= self.ziel

    @property
    def fehlende_trades(self) -> int | None:
        if self.trades_noetig is None:
            return None
        return max(0, self.trades_noetig - self.trades)

    def kosten(self, versuche: int) -> float:
        """Was ``versuche`` weitere Versuche an DSR-Punkten kosten - Befund 327.

        ``kosten_naechster_versuch`` und ``kosten_zehn_versuche`` sind die
        Faelle 1 und 10 davon; hier steht die Rechnung dahinter, weil die
        Frage selten genau eins oder zehn lautet.

        **Die Zahl geht nur in eine Richtung.** ``versuche`` kleiner null
        waere die Frage "was braechte es, fuenf Versuche zurueckzunehmen", und
        die hat keine Antwort: ``admission.save_trials`` laesst den Zaehler
        nie fallen, weil ein fallender Zaehler die Mehrfachtest-Korrektur
        milder machen wuerde. Ein ausgegebener Versuch ist ausgegeben.

        Was eine Ersparnis wert ist, steht deshalb hier **als vermiedener
        Verlust**: ``kosten(5)`` ist, was fuenf Regeln kosten, die man kuenftig
        nicht mehr wertet - nicht, was ihr Weglassen zurueckholt.
        """
        if versuche < 0:
            raise ValueError(
                "Der Versuchszaehler faellt nicht - eine Ersparnis ist ein "
                "vermiedener Verlust, keine Rueckgabe. Nach 'kosten(n)' mit "
                "n >= 0 fragen."
            )
        return self.dsr - _dsr(
            self.sharpe,
            self.trades,
            self.trials + versuche,
            self.schiefe,
            self.woelbung,
        )

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
        # **Der Satz, der Befund 326 gefehlt hat.** Dort stand eine Ersparnis
        # von fuenf Versuchen als Fortschritt Richtung Gate. Gemessen sind
        # das 0,0054 Punkte gegen eine Luecke von 0,3673 - und der Zaehler
        # faellt ohnehin nicht, die fuenf waeren nur nie dazugekommen.
        luecke = self.ziel - self.dsr
        wieviel = (
            self.kosten_zehn_versuche / luecke if luecke > 0 else 0.0
        )
        zeilen.append(
            f"Der Zaehler faellt nie - gespart wird nur, was noch nicht "
            f"ausgegeben ist. Selbst zehn vermiedene Versuche decken "
            f"{wieviel:.1%} der Luecke von {luecke:.4f}: Versuchsdisziplin "
            f"haelt den Abstand, sie schliesst ihn nicht."
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
            effektiv=trades, trials=trials, skew=skew, kurtosis=kurtosis, ziel=ziel
        ),
        kosten_naechster_versuch=jetzt
        - _dsr(sharpe, trades, trials + 1, skew, kurtosis),
        kosten_zehn_versuche=jetzt - _dsr(sharpe, trades, trials + 10, skew, kurtosis),
        schiefe=skew,
        woelbung=kurtosis,
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
