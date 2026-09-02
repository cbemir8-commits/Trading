"""Traegt die Regel dort, wo sie nie ausgewaehlt wurde?

Warum das gefragt gehoert
-------------------------
Befund 168 hat den Bestand in seinen eigenen Katalog eingeordnet: Sein
Vorsprung ist kleiner als das, was Auswahl aus 198 Versuchen ohnehin erzeugt.
Das ist ein Verdacht, und er laesst sich von einer **anderen** Seite pruefen -
mit Maerkten, die bei der Entwicklung keine Rolle gespielt haben.

``data/reference.py`` nennt das selbst *"der schaerfste verfuegbare Test"*.

Was das **nicht** ist
---------------------
Befund 27 und 133 haben LTC und XRP dem Portfolio **hinzugefuegt** und
gemessen, dass die Qualitaet je Trade dabei faellt; die Richtung ist
geschlossen. Hier laeuft jeder Markt **einzeln**, ohne BTC und ETH. Die
Zahlen von damals - "Sharpe 0,42 und 0,38" - sind Jahressharpes von vor 146
Befunden, ohne effektive Stichprobe, ohne Guete, ohne Gate.

Gemessen (Befund 174)
---------------------
Der Bestand unveraendert, Spot-Punkt, Stichprobe wie im Gate:

    Markt   Rolle          Trades  n_eff  SR/Trade   Guete   noetig
    BTC     Entwicklung      117    107    0,2633    2,723    3,593
    ETH     Entwicklung       80     76    0,2907    2,534    3,533
    LTC     Holdout          106    106    0,1154    1,188    3,591
    XRP     Holdout          112    106    0,1095    1,127    3,591

**Der Holdout haelt 41 % des Vorteils je Trade** - positiv, aber weniger als
die Haelfte. Das ist die uebliche Handschrift eines Vorteils, der teils echt
und teils angepasst ist.

Die zwei Einschraenkungen, ohne die die Zahl mehr verspricht als sie haelt
--------------------------------------------------------------------------
**Erstens sind die Maerkte nicht unabhaengig.** Korrelation der
Tagesrenditen ueber 3300 gemeinsame Tage:

           BTC    ETH    LTC    XRP
    BTC   1,000  0,799  0,736  0,572
    ETH   0,799  1,000  0,786  0,647
    LTC   0,736  0,786  1,000  0,631
    XRP   0,572  0,647  0,631  1,000

Holdout gegen Entwicklung im Mittel **0,685**. Rund die Haelfte der Varianz
ist gemeinsam; ein Holdout auf diesen Maerkten ist deutlich schwaecher als
sein Name klingt. Auch die Naehe der beiden Holdout-Werte zueinander (0,1154
und 0,1095) sagt weniger, als sie scheint - LTC und XRP korrelieren
untereinander mit 0,631.

**Zweitens ist der Aufwaertstrend nicht herausgerechnet.** Der Bestand ist
eine Long-Trendfolge, und alle vier Maerkte sind ueber den Messzeitraum
gestiegen. Ein positiver Wert im Holdout kann daher auch nur heissen, dass
dort ebenfalls ein Trend war. Ohne eine Nullprobe mit gleichen Haltedauern
trennt diese Messung **Koennen nicht von Marktrichtung**.

Was daraus folgt - und was nicht
--------------------------------
Es folgt: Der Vorteil ist **nicht restlos** Auswahl. Waere er es, waere im
Holdout eine Null zu erwarten, und es steht dort zweimal etwas Positives.

Es folgt **nicht**, dass der Bestand taugt. Die Holdout-Guete liegt bei 1,19
und 1,13 gegen eine Latte von 3,59 - nicht knapp, sondern um das Dreifache
daneben. Und die beiden Einschraenkungen oben sind nicht gehoben, sondern
benannt.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Wie die Rolle eines Marktes heisst. Zwei Werte, damit niemand einen
#: dritten erfindet und die Auswertung stillschweigend etwas anderes zaehlt.
ENTWICKLUNG = "Entwicklung"
HOLDOUT = "Holdout"


@dataclass(frozen=True, slots=True)
class Marktbefund:
    """Ein Markt, einzeln gemessen."""

    symbol: str
    rolle: str
    trades: int
    n_eff: int
    sharpe_je_trade: float

    def __post_init__(self) -> None:
        if self.rolle not in (ENTWICKLUNG, HOLDOUT):
            raise ValueError(
                f"'{self.rolle}' ist keine Rolle - erlaubt sind "
                f"'{ENTWICKLUNG}' und '{HOLDOUT}'."
            )

    @property
    def guete(self) -> float:
        return self.sharpe_je_trade * self.n_eff**0.5


@dataclass(frozen=True, slots=True)
class Holdoutbild:
    """Was die Holdout-Maerkte vom Vorteil uebrig lassen."""

    befunde: tuple[Marktbefund, ...]
    korrelation: float | None = None
    """Mittlere Korrelation Holdout gegen Entwicklung, falls gemessen."""

    def _mittel(self, rolle: str) -> float | None:
        werte = [b.sharpe_je_trade for b in self.befunde if b.rolle == rolle]
        return sum(werte) / len(werte) if werte else None

    @property
    def entwicklung(self) -> float | None:
        return self._mittel(ENTWICKLUNG)

    @property
    def holdout(self) -> float | None:
        return self._mittel(HOLDOUT)

    @property
    def behalten(self) -> float | None:
        """Welchen Anteil des Vorteils je Trade der Holdout haelt.

        ``None``, wenn eine Seite fehlt oder die Entwicklungsseite nicht
        positiv ist - ein Anteil von etwas Negativem ist keine Auskunft.
        """
        a, b = self.entwicklung, self.holdout
        if a is None or b is None or a <= 0:
            return None
        return b / a

    def urteil(self) -> str:
        """Was die Messung sagt - **samt dem, was sie nicht trennt.**

        Die beiden Einschraenkungen stehen fest im Text und nicht im
        Ermessen des Aufrufers: Ein Holdout-Ergebnis ohne sie liest sich als
        Beleg fuer Koennen, und das gibt es hier nicht her.
        """
        a, b, anteil = self.entwicklung, self.holdout, self.behalten
        if a is None or b is None:
            return (
                "**Kein Vergleich moeglich** - es fehlt eine der beiden "
                "Seiten. Ohne Entwicklungsmaerkte gibt es keinen Massstab, "
                "ohne Holdout keine Probe."
            )
        zeilen = [
            f"SR je Trade: Entwicklung {a:+.4f}, Holdout {b:+.4f}"
            + (f" - der Holdout haelt {anteil:.0%}." if anteil is not None else "."),
        ]
        if b <= 0:
            zeilen.append(
                "**Im Holdout bleibt nichts uebrig.** Das ist mit reiner "
                "Auswahl vereinbar - und die dritte Stimme neben dem "
                "Deflated Sharpe und Befund 168."
            )
        else:
            zeilen.append(
                "**Der Vorteil ist damit nicht restlos Auswahl** - waere er "
                "es, waere im Holdout eine Null zu erwarten."
            )
        if self.korrelation is not None:
            zeilen.append(
                f"Aber: Holdout und Entwicklung korrelieren mit "
                f"{self.korrelation:.3f}. Rund "
                f"{self.korrelation**2:.0%} der Varianz ist gemeinsam - ein "
                f"Holdout auf diesen Maerkten ist schwaecher als sein Name."
            )
        zeilen.append(
            "Und der Aufwaertstrend ist nicht herausgerechnet: Bei einer "
            "Long-Trendfolge auf gestiegenen Maerkten trennt diese Messung "
            "**Koennen nicht von Marktrichtung**."
        )
        return "\n".join(zeilen)


__all__ = ["ENTWICKLUNG", "HOLDOUT", "Holdoutbild", "Marktbefund"]
