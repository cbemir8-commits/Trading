"""Schlaegt das Timing der Regel den Zufall mit gleicher Haltedauer?

Nicht zu verwechseln mit ``research/nullprobe.py``
--------------------------------------------------
Das ist ein anderer Test, und die Verwechslung ist mir beim Bauen selbst
passiert - ich habe die Datei dort ueberschrieben und aus dem Index
zurueckgeholt (Befund 175).

* ``nullprobe`` mischt die **Renditen** und fragt: Findet die Maschine einen
  Vorteil, wo garantiert keiner ist? Das prueft die Zulassungsstrecke.
* Dieses Modul laesst die Reihe **unangetastet** und zieht zufaellige
  **Einstiege** mit denselben Haltedauern. Das prueft die Regel.

Die Frage, die Befund 174 offengelassen hat
-------------------------------------------
Dort hielt der Holdout 41 % des Vorteils je Trade - und der Befund sagte
ausdruecklich dazu, dass er **Koennen nicht von Marktrichtung trennt**: Alle
vier Maerkte sind ueber den Messzeitraum gestiegen, und eine Long-Trendfolge
ist dort schon deshalb im Plus.

Gemessen (Befund 175)
---------------------
Prozentuale Rendite je Trade, 2000 Ziehungen des ganzen Trade-Satzes:

    Markt  Rolle          Trades   echt %   Null %  Streuung  Perzentil     z
    BTC    Entwicklung        78    8,989    6,406     4,104     78,6%   0,63
    ETH    Entwicklung        50   13,592    4,179     3,334     99,5%   2,82
    LTC    Holdout            70    3,869    1,187     1,762     93,8%   1,52
    XRP    Holdout            75    3,642    1,697     2,409     81,5%   0,81

**Vier von vier liegen ueber ihrer Null**, beide Holdout-Maerkte
eingeschlossen. Der Vorteil ist damit nicht bloss Marktrichtung: Bei BTC
verdient schon der Zufall 6,4 %, die Regel 9,0 %.

Was daran **nicht** stark ist
-----------------------------
Nur ETH raeumt die uebliche Schwelle von |z| = 2. Die uebrigen drei liegen
zwischen 0,6 und 1,5 Streuungen ueber ihrer Null - das ist die Richtung, nicht
der Beleg.

Und die vier Zahlen lassen sich **nicht** zu einer zusammenziehen. Die
Maerkte korrelieren mit rund 0,70 (Befund 174); ein gemeinsames z aus vier
korrelierten Proben waere zu gross, und zwar um einen Betrag, den man nicht
kennt. Dieses Modul rechnet es deshalb nicht aus - es zaehlt, wie viele oben
liegen, und nennt die Korrelation dazu.

Die Huerde ist zu niedrig, nicht zu hoch
----------------------------------------
**Die Nullprobe hat keine Stops, die Regel schon.** Stops schneiden Verluste
ab; das begoenstigt die Regel in diesem Vergleich. Wer diese Huerde nicht
nimmt, scheitert also deutlich - wer sie nimmt, hat sie moeglicherweise mit
den Stops genommen und nicht mit dem Einstiegszeitpunkt.

Damit ist das Ergebnis eine **Obergrenze** des Timing-Vorteils, keine
Untergrenze.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Ab welchem |z| dieses Modul von einem Beleg spricht - dieselbe Schwelle
#: wie in ``research/vorratsdecke.py`` und aus demselben Grund (Befund 75).
MINDEST_Z = 2.0


def zufallsverteilung(
    schluss: np.ndarray,
    dauern: np.ndarray,
    *,
    von: int,
    bis: int,
    ziehungen: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Die Verteilung der mittleren Rendite bei zufaelligen Einstiegen.

    Fuer jeden echten Trade wird ein Einstieg gezogen und **dieselbe Dauer in
    Balken** gehalten. Gezogen wird nur aus ``[von, bis]`` - dem Zeitraum, den
    die echten Trades abdecken. Ueber die ganze Reihe zu ziehen verglichen
    verschiedene Marktphasen, und bei einem Markt, der sich verhundertfacht
    hat, entscheidet das alles.

    Geliefert wird ein Wert je Ziehung: das **Mittel ueber den ganzen
    Trade-Satz**, nicht ueber einzelne Trades. Verglichen wird schliesslich
    ein Mittel mit einem Mittel.
    """
    if len(dauern) == 0:
        raise ValueError("Ohne Haltedauern gibt es nichts zu ziehen.")
    if bis <= von:
        raise ValueError(f"Leerer Zeitraum: von={von}, bis={bis}.")
    if int(np.min(dauern)) < 1:
        raise ValueError("Eine Haltedauer unter einem Balken ist keine.")

    hoechster = np.maximum(bis - dauern, von + 1)
    mittel = np.empty(ziehungen)
    for k in range(ziehungen):
        start = rng.integers(von, hoechster)
        ende = np.minimum(start + dauern, bis)
        mittel[k] = np.mean(schluss[ende] / schluss[start] - 1.0)
    return mittel


@dataclass(frozen=True, slots=True)
class Marktprobe:
    """Ein Markt gegen seine eigene Null."""

    symbol: str
    rolle: str
    trades: int
    echt: float
    null: float
    streuung: float
    perzentil: float

    @property
    def z(self) -> float | None:
        """Wie viele Streuungen die Regel ueber ihrer Null liegt."""
        if self.streuung <= 0:
            return None
        return (self.echt - self.null) / self.streuung

    @property
    def darueber(self) -> bool:
        return self.echt > self.null

    @property
    def belegt(self) -> bool:
        z = self.z
        return z is not None and z >= MINDEST_Z


@dataclass(frozen=True, slots=True)
class Zufallsbild:
    """Alle Maerkte zusammen - **ohne sie zusammenzurechnen.**"""

    proben: tuple[Marktprobe, ...]
    korrelation: float | None = None

    @property
    def darueber(self) -> int:
        return sum(1 for p in self.proben if p.darueber)

    @property
    def belegt(self) -> int:
        return sum(1 for p in self.proben if p.belegt)

    def urteil(self) -> str:
        if not self.proben:
            return "**Keine Probe** - ohne Maerkte gibt es nichts zu vergleichen."
        n = len(self.proben)
        zeilen = [
            f"**{self.darueber} von {n} Maerkten liegen ueber ihrer Null.** "
            f"Der Vorteil ist damit nicht bloss Marktrichtung."
            if self.darueber == n
            else f"{self.darueber} von {n} Maerkten liegen ueber ihrer Null."
        ]
        if self.belegt < n:
            zeilen.append(
                f"Aber nur {self.belegt} von {n} raeumen |z| = "
                f"{MINDEST_Z:.0f}. Bei den uebrigen ist es die Richtung, "
                f"nicht der Beleg."
            )
        if self.korrelation is not None:
            zeilen.append(
                f"**Die Zahlen lassen sich nicht zu einer zusammenziehen.** "
                f"Die Maerkte korrelieren mit {self.korrelation:.3f}; ein "
                f"gemeinsames z waere zu gross, und zwar um einen Betrag, den "
                f"man nicht kennt. Deshalb steht hier eine Anzahl und keine "
                f"Gesamtstatistik."
            )
        zeilen.append(
            "Und die Huerde ist zu niedrig, nicht zu hoch: Die Ziehung hat "
            "keine Stops, die Regel schon. Das Ergebnis ist eine "
            "**Obergrenze** des Timing-Vorteils, keine Untergrenze."
        )
        return "\n".join(zeilen)


__all__ = ["MINDEST_Z", "Marktprobe", "Zufallsbild", "zufallsverteilung"]
