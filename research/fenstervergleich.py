"""Zwei Varianten fensterweise vergleichen - nicht nur im Aggregat.

**Warum es diese Datei gibt.**

Eine Messung sah so aus:

    Variante          Trades    p.a.      DD      Sharpe   DSR    Gates
    long-only            154   11,28 %   9,74 %    1,51   0,804   8/11
    long + short         302   12,50 %   8,74 %    1,51   0,852   9/11

Mehr Rendite, weniger Rueckgang, ein Gate mehr. Auf jeder Achse besser. Ich
war eine Zeile davon entfernt, das als Fortschritt zu melden.

Fensterweise nachgerechnet:

    31 Fenster: 12 besser, 18 schlechter, 1 unveraendert
    Vorzeichentest: p = 0,90

Die **Mehrheit** der Fenster wurde schlechter. Die guten Aggregatzahlen kamen
aus wenigen guenstigen Fenstern - genau die Sorte Pfadabhaengigkeit, gegen die
der ganze Walk-Forward eigentlich gebaut ist. Im Gesamtergebnis verschwindet
sie trotzdem, weil ein einziges starkes Fenster achtzehn schwache ueberdecken
kann.

**Die Regel, die daraus folgt:** Eine Verbesserung, die sich nicht in der
Mehrzahl der Fenster zeigt, ist keine. Das Aggregat darf sie bestaetigen, aber
nicht begruenden.

Der Vorzeichentest ist bewusst das schwaechste denkbare Verfahren - er benutzt
nur die Richtung, nicht die Groesse. Damit kann ein einzelnes Ausreisserfenster
das Urteil nicht kippen, und genau darum geht es hier.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb

from backtest.walkforward import WalkForwardReport

#: Ab wann gilt ein Unterschied je Fenster als Unterschied? Ergebnisse in Euro
#: sind nie exakt gleich, wenn irgendetwas anders lief.
GLEICHHEITSSCHWELLE = 0.01

#: Wie klein muss der Vorzeichentest ausfallen, damit eine Verbesserung als
#: belastbar gilt. 0,05 ist die uebliche Schwelle und steht hier fest, bevor
#: irgendetwas gemessen wurde.
SIGNIFIKANZ = 0.05


def vorzeichentest(besser: int, schlechter: int) -> float:
    """Einseitiger exakter Binomialtest gegen "reiner Zufall".

    Nullhypothese: Die Variante ist gleich gut, jedes Fenster faellt mit
    Wahrscheinlichkeit 1/2 in die eine oder andere Richtung. Zurueckgegeben
    wird die Wahrscheinlichkeit, mindestens so viele bessere Fenster zu sehen,
    wenn nichts dahintersteckt.

    Ohne ``scipy`` - die exakte Summe ist bei 31 Fenstern eine Zeile.
    """
    n = besser + schlechter
    if n == 0:
        return 1.0
    schwanz = sum(comb(n, i) for i in range(besser, n + 1))
    return schwanz / 2**n


@dataclass(frozen=True, slots=True)
class Fenstervergleich:
    """Wie oft war B besser als A - und war das mehr als Zufall?"""

    fenster: int
    besser: int
    schlechter: int
    unveraendert: int
    rueckgang_besser: int
    mittlere_differenz: float
    streuung: float
    p_wert: float

    @property
    def belastbar(self) -> bool:
        """Zeigt sich die Verbesserung in der Mehrzahl der Fenster?

        Bewusst streng: Ein besseres Aggregat allein genuegt nicht. Wer nur
        aufs Gesamtergebnis sieht, haelt ein einzelnes gutes Fenster fuer einen
        Vorteil.
        """
        return self.besser > self.schlechter and self.p_wert <= SIGNIFIKANZ

    @property
    def mehrheit_schlechter(self) -> bool:
        return self.schlechter > self.besser

    def bericht(self) -> str:
        zeilen = [
            f"{self.fenster} Fenster: {self.besser} besser, "
            f"{self.schlechter} schlechter, {self.unveraendert} unveraendert",
            f"Geringerer Rueckgang in {self.rueckgang_besser} Fenstern",
            f"Mittlere Differenz {self.mittlere_differenz:+.2f} "
            f"(Streuung {self.streuung:.2f})",
            f"Vorzeichentest: p = {self.p_wert:.3f}",
        ]
        if self.belastbar:
            zeilen.append("Urteil: belastbar - die Mehrzahl der Fenster wird besser.")
        elif self.mehrheit_schlechter:
            zeilen.append(
                "Urteil: NICHT belastbar - die Mehrzahl der Fenster wird "
                "SCHLECHTER. Ein besseres Gesamtergebnis kommt dann aus "
                "wenigen guenstigen Fenstern, nicht aus einem Vorteil."
            )
        else:
            zeilen.append(
                "Urteil: nicht belastbar - der Unterschied ist mit reinem "
                "Zufall vereinbar."
            )
        return "\n".join(zeilen)


def vergleiche(a: WalkForwardReport, b: WalkForwardReport) -> Fenstervergleich:
    """B gegen A, Fenster fuer Fenster.

    Beide Berichte muessen aus demselben Fensterschnitt stammen - sonst
    vergleicht man verschiedene Zeitraeume und das Ergebnis bedeutet nichts.
    Deshalb wird es geprueft und nicht angenommen.
    """
    if len(a.windows) != len(b.windows):
        raise ValueError(
            f"Verschiedene Fensterzahl ({len(a.windows)} gegen "
            f"{len(b.windows)}) - die Laeufe sind nicht vergleichbar."
        )
    if not a.windows:
        return Fenstervergleich(0, 0, 0, 0, 0, 0.0, 0.0, 1.0)

    besser = schlechter = unveraendert = rueckgang_besser = 0
    differenzen: list[float] = []

    for fa, fb in zip(a.windows, b.windows, strict=True):
        if fa.window.test_start != fb.window.test_start:
            raise ValueError(
                f"Fenster passen nicht zueinander: {fa.window.test_start} "
                f"gegen {fb.window.test_start}"
            )
        differenz = float(fb.metrics.net_profit) - float(fa.metrics.net_profit)
        differenzen.append(differenz)
        if abs(differenz) < GLEICHHEITSSCHWELLE:
            unveraendert += 1
        elif differenz > 0:
            besser += 1
        else:
            schlechter += 1
        if float(fb.metrics.max_drawdown_pct) < float(fa.metrics.max_drawdown_pct):
            rueckgang_besser += 1

    mittel = sum(differenzen) / len(differenzen)
    if len(differenzen) > 1:
        varianz = sum((d - mittel) ** 2 for d in differenzen) / (len(differenzen) - 1)
    else:
        varianz = 0.0

    return Fenstervergleich(
        fenster=len(differenzen),
        besser=besser,
        schlechter=schlechter,
        unveraendert=unveraendert,
        rueckgang_besser=rueckgang_besser,
        mittlere_differenz=mittel,
        streuung=varianz**0.5,
        p_wert=vorzeichentest(besser, schlechter),
    )


def vergleiche_je_trade(
    a: list[list[float]], b: list[list[float]]
) -> Fenstervergleich:
    """Dieselbe Regel, aber auf das **Ergebnis je Trade** angewandt.

    ``vergleiche`` nimmt den Fenstergewinn. Fuer einen Verbund taugt der
    nicht: Zwei Regeln parallel teilen das Kapital, der Gewinn haengt also an
    der Positionsgroesse und nicht an der Guete. Verglichen wird deshalb der
    **Mittelwert je Trade** im Fenster.

    Beide Seiten sind Listen von Fenstern, je Fenster die Trade-Ergebnisse.
    Fenster, in denen eine Seite gar nicht handelt, tragen keine Auskunft und
    zaehlen als ``unveraendert`` - nicht als Verbesserung.

    Was der Test **nicht** kann: Er sieht die effektive Stichprobe nicht. Die
    ist keine Groesse je Fenster, und beim Verbund steckt der groessere Teil
    des Gewinns genau dort (Befund 155). Er prueft die Qualitaet je Trade,
    nicht die Evidenz.
    """
    if len(a) != len(b):
        raise ValueError(
            f"Verschiedene Fensterzahl ({len(a)} gegen {len(b)}) - die Laeufe "
            f"sind nicht vergleichbar."
        )

    besser = schlechter = unveraendert = 0
    differenzen: list[float] = []
    for fa, fb in zip(a, b, strict=True):
        if not fa or not fb:
            unveraendert += 1
            continue
        differenz = sum(fb) / len(fb) - sum(fa) / len(fa)
        differenzen.append(differenz)
        if abs(differenz) < GLEICHHEITSSCHWELLE:
            unveraendert += 1
        elif differenz > 0:
            besser += 1
        else:
            schlechter += 1

    mittel = sum(differenzen) / len(differenzen) if differenzen else 0.0
    if len(differenzen) > 1:
        varianz = sum((d - mittel) ** 2 for d in differenzen) / (len(differenzen) - 1)
    else:
        varianz = 0.0

    return Fenstervergleich(
        fenster=len(a),
        besser=besser,
        schlechter=schlechter,
        unveraendert=unveraendert,
        rueckgang_besser=0,
        mittlere_differenz=mittel,
        streuung=varianz**0.5,
        p_wert=vorzeichentest(besser, schlechter),
    )
