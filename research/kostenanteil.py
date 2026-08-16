"""Ist die Kopplung eine Eigenschaft der Kosten oder der Signale?

Die Hypothese, die naheliegt
----------------------------
Befund 75 und 77 haben ueber 18 gemessene Regeln eine Kopplung gezeigt:
**r = -0,602 zwischen Trade-Zahl und Qualitaet je Trade** - wer oefter
handelt, handelt schlechter. Sie erklaert, warum die Partnerkarte leer
ausgeht, und sie ist der Grund, warum das haerteste Gate nicht faellt.

Dafuer gibt es eine mechanische Erklaerung, und sie klingt zwingend: Die
Gebuehr ist ein **fester Betrag je Trade**, aber die Streuung eines Trades
waechst mit seiner Haltedauer. Wer oefter handelt, haelt kuerzer, streut
weniger - und derselbe Gebuehrenbetrag frisst einen groesseren Anteil.

Waere das die Ursache, haette es eine Folge: Die Kopplung waere
**verhandelbar**. Bessere Konditionen, Maker-Rebates, ein groesseres Konto -
alles wuerde helfen.

Was gemessen wurde
------------------
Ueber zehn Regeln mit sehr verschiedener Taktung, vom Bestand (154 Trades,
14 Tage Haltedauer) bis zum 'Abgriff des Vortagestiefs' (406 Trades, 0,3
Tage):

    Trades <-> Kostenanteil    +0,831
    Kostenanteil <-> Qualitaet -0,738

Die Mechanik ist also **da**: Mehr Trades heissen kuerzer halten und hoeheren
Kostenanteil. Nur traegt sie nichts, denn der Anteil selbst ist winzig - er
reicht von 0,0013 bis 0,0170 der Trade-Streuung, waehrend die Qualitaeten von
+0,34 bis -0,12 spannen.

Rechnet man die Gebuehr zurueck, bleibt die Kopplung praktisch unveraendert:

    netto    r = -0,673
    brutto   r = -0,663

**Zehn Tausendstel.** Die Hypothese ist damit widerlegt.

Warum die Rechnung trotzdem unvollstaendig ist
----------------------------------------------
``net_pnl = gross_pnl - fees - funding``, und die **Slippage steckt im
Ausfuehrungspreis** - also schon in ``gross_pnl`` und nicht in ``fees``. Was
oben zurueckgerechnet wurde, ist die Gebuehr allein; die wahren Handelskosten
liegen hoeher, und um wie viel, laesst sich aus den Trades nicht trennen.

Deshalb wird die Frage andersherum gestellt, und das ist ihre ehrliche Form:
**Bei welchem Kostenfaktor wuerde die Kopplung kippen?**

    Faktor 1     r = -0,663     (die tatsaechliche Gebuehr, 0,04 %)
    Faktor 5     r = -0,618
    Faktor 10    r = -0,542
    Faktor 25    r = -0,144     (entspraeche 1 % je Trade)
    Faktor 50    r = +0,511

Erst bei rund **29-facher Gebuehr** verschwindet die Kopplung - das waeren
1,2 % je Roundtrip. Kein Handelsplatz verlangt das. Selbst wenn die Slippage die
Kosten verdoppelte oder verfuenffachte, bliebe die Kopplung stehen.

Was daraus folgt
----------------
Die Kopplung ist **keine Eigenschaft der Kosten, sondern der Signale**:
Haeufigere Ausloeser tragen tatsaechlich weniger Vorteil je Ausloesung. Das
ist nicht wegverhandelbar - keine Konditionen, kein groesseres Konto, keine
bessere Ausfuehrung aendert etwas daran.

Fuer die Suche heisst das: Wer eine Regel sucht, die **oft ausloest und dabei
Vorteil behaelt**, sucht gegen ein Muster, das nicht an einer Reibung liegt,
die sich beseitigen liesse.

Kostet keinen Versuch: Zerlegt werden Trades, die schon gerechnet sind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True, slots=True)
class Taktpunkt:
    """Eine Regel mit ihrer Taktung und ihrem Kostenanteil."""

    name: str
    trades: int
    sharpe_je_trade: float
    haltedauer_tage: float
    kostenanteil: float
    """Mittlere Gebuehr je Trade, geteilt durch die Streuung der Trades.

    In denselben Einheiten wie der Sharpe je Trade - deshalb laesst sie sich
    direkt zurueckaddieren.
    """

    def brutto(self, faktor: float = 1.0) -> float:
        """Der Sharpe je Trade, wenn man die Kosten herausrechnet.

        ``faktor`` skaliert die Gebuehr. Er ist noetig, weil die Slippage im
        Ausfuehrungspreis steckt und sich nicht trennen laesst - statt sie zu
        schaetzen, wird gefragt, wie gross sie sein muesste, um etwas zu
        aendern.
        """
        return self.sharpe_je_trade + faktor * self.kostenanteil


@dataclass(slots=True)
class Kostenfrage:
    """Traegt die Gebuehr die gemessene Kopplung?"""

    punkte: list[Taktpunkt] = field(default_factory=list)

    @property
    def genug(self) -> bool:
        return len(self.punkte) >= 4

    def _korrelation(self, werte: list[float]) -> float | None:
        if not self.genug:
            return None
        trades = np.array([float(p.trades) for p in self.punkte])
        andere = np.array(werte)
        if np.std(trades) == 0 or np.std(andere) == 0:
            return None
        return float(np.corrcoef(trades, andere)[0, 1])

    @property
    def netto(self) -> float | None:
        return self._korrelation([p.sharpe_je_trade for p in self.punkte])

    def brutto(self, faktor: float = 1.0) -> float | None:
        return self._korrelation([p.brutto(faktor) for p in self.punkte])

    @property
    def mechanik(self) -> float | None:
        """Trades gegen Kostenanteil - ist der Mechanismus ueberhaupt da?"""
        return self._korrelation([p.kostenanteil for p in self.punkte])

    def kippfaktor(self, *, obergrenze: float = 1000.0) -> float | None:
        """Ab welchem Kostenfaktor die Kopplung verschwindet.

        "Verschwindet" heisst hier: Die Korrelation erreicht null. ``None``,
        wenn das im durchsuchten Bereich nicht passiert - dann traegt die
        Gebuehr die Kopplung unter keinen Umstaenden.
        """
        if not self.genug or (self.netto or 0) >= 0:
            return None
        if (self.brutto(obergrenze) or -1.0) < 0:
            return None
        tief, hoch = 1.0, obergrenze
        for _ in range(80):
            mitte = (tief + hoch) / 2
            if (self.brutto(mitte) or -1.0) < 0:
                tief = mitte
            else:
                hoch = mitte
        return hoch

    def tabelle(self, faktoren: tuple[float, ...] = (1, 5, 10, 25, 50)) -> str:
        zeilen = [f"{'Faktor':>8} {'r brutto':>10} {'Aenderung':>11}", "-" * 31]
        netto = self.netto or 0.0
        for f in faktoren:
            wert = self.brutto(f)
            if wert is None:
                continue
            zeilen.append(f"{f:>8g} {wert:>+10.3f} {wert - netto:>+11.3f}")
        return "\n".join(zeilen)

    def urteil(self) -> str:
        netto, brutto, mechanik = self.netto, self.brutto(1.0), self.mechanik
        if netto is None or brutto is None:
            return "Zu wenige Punkte - ueber die Ursache laesst sich nichts sagen."

        vorhanden = (
            f"Der Mechanismus ist da: Trades und Kostenanteil korrelieren mit "
            f"{mechanik:+.3f}. "
            if mechanik is not None and mechanik > 0.5
            else ""
        )
        kipp = self.kippfaktor()
        wo = (
            f"Erst bei **{kipp:.0f}-facher Gebuehr** verschwindet sie - das "
            f"waeren {0.04 * kipp:.1f} % je Roundtrip, und das verlangt kein "
            f"Handelsplatz."
            if kipp is not None
            else "Auch bei tausendfacher Gebuehr verschwindet sie nicht."
        )
        return (
            f"**Die Kopplung liegt nicht an den Kosten.** {vorhanden}Rechnet "
            f"man die Gebuehr zurueck, geht die Korrelation von {netto:+.3f} "
            f"auf {brutto:+.3f} - {abs(brutto - netto):.3f} Unterschied. "
            f"{wo}\n\n"
            f"Sie ist damit eine Eigenschaft der **Signale**, nicht einer "
            f"Reibung: Haeufigere Ausloeser tragen weniger Vorteil je "
            f"Ausloesung. Das ist nicht wegverhandelbar - keine Konditionen, "
            f"kein groesseres Konto, keine bessere Ausfuehrung aendert daran "
            f"etwas."
        )
