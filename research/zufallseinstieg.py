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

BERICHTIGT IN BEFUND 200 - die Richtung stimmt nicht
-----------------------------------------------------
Der Absatz darueber ist eine Ueberlegung, keine Messung, und sie geht in die
falsche Richtung. Gemessen, mit denselben Deckeln fuer die Null
(``zufallsverteilung_mit_deckeln``, Stop 4 %, Ziel 80 %):

    Markt  Rolle          echt %   Null ohne   z ohne   Null mit   z mit
    BTC    Entwicklung     8,989       6,406     0,63      2,659    3,94
    ETH    Entwicklung    13,592       4,099     2,95      1,729    6,34
    LTC    Holdout         3,869       1,086     1,57      0,320    3,32
    XRP    Holdout         3,642       1,628     0,85      0,457    2,71

**Mit Deckeln raeumen vier von vier die Schwelle statt einem von vier.** Die
Null wird durch den Stop nicht besser, sondern schlechter - und zwar deutlich.

Der Grund ist die Asymmetrie der Deckel. Bei -4 % gegen +80 % schneidet der
Stop staendig, das Ziel so gut wie nie. Ein zufaelliger Einstieg, zehn Balken
gehalten, laeuft in **54,2 %** der Faelle irgendwann 4 % ins Minus; die echten
Trades tun das in **41,9 %**. Wer ohne Stop zieht, gibt der Null eine Freiheit,
die die Regel nie hatte: einen Einbruch aussitzen und danach wieder steigen.

Der ungedeckelte Vergleich ist damit keine Obergrenze, sondern eine
**Untergrenze**.

Was er nicht ist
----------------
Kein Beweis. Die vier Maerkte korrelieren mit 0,695 (Befund 174) - vier
Treffer sind hier keine vier unabhaengigen Bestaetigungen, und die z-Werte
lassen sich weiterhin nicht zusammenziehen.

Und die Haltedauern stammen aus den Trades der Regel, sind also von ihren
eigenen Ausstiegen geformt. Das gilt fuer beide Fassungen gleichermassen und
war schon in Befund 175 so.
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


def zufallsverteilung_mit_deckeln(
    schluss: np.ndarray,
    tief: np.ndarray,
    hoch: np.ndarray,
    dauern: np.ndarray,
    *,
    von: int,
    bis: int,
    ziehungen: int,
    rng: np.random.Generator,
    stop: float,
    ziel: float,
) -> np.ndarray:
    """Dieselbe Ziehung - aber mit **denselben Deckeln wie die Regel**.

    Warum es die zweite Fassung braucht
    -----------------------------------
    ``zufallsverteilung`` haelt stur bis zum Ende der Dauer und steigt zum
    Schlusskurs aus. Die Regel tut das nicht: Sie schneidet bei -4 % ab und
    nimmt bei +80 % mit. Gemessen am Bestand (Befund 200):

        stop_loss      49 von 117 Trades   -4,05 %
        take_profit     6 von 117          +80,0 %
        signal_exit    62 von 117          -3,2 % bis +50,8 %

    **Zweiundvierzig Prozent der echten Trades enden am Stop.** Die Null
    dagegen faehrt jeden Einbruch bis zum Schluss mit.

    Befund 175 hat daraus geschlossen, der Vergleich begoenstige die Regel.
    Gemessen ist das Gegenteil: Ein zufaelliger Einstieg reisst den Stop
    **oefter** als ein gewaehlter (54,2 % gegen 41,9 %), und die Freiheit,
    einen Einbruch auszusitzen, hat nur die Null. Mit Deckeln faellt sie
    deutlich, und aus einem von vier Maerkten ueber |z| = 2 werden vier.

    Hier bekommt die Null dieselben zwei Deckel, bar fuer bar geprueft.

    Wenn beide in denselben Balken fallen
    -------------------------------------
    Dann gilt der **Stop**. Das ist die vorsichtige Auslegung und die des
    Backtests; bei -4 % gegen +80 % auf Tageskerzen kommt der Fall ohnehin
    praktisch nicht vor.

    Gezogen wird je Trade ueber alle Ziehungen zugleich - statistisch
    dasselbe wie die Schleife in ``zufallsverteilung``, nur schneller.
    """
    if len(dauern) == 0:
        raise ValueError("Ohne Haltedauern gibt es nichts zu ziehen.")
    if bis <= von:
        raise ValueError(f"Leerer Zeitraum: von={von}, bis={bis}.")
    if int(np.min(dauern)) < 1:
        raise ValueError("Eine Haltedauer unter einem Balken ist keine.")
    if stop <= 0 or ziel <= 0:
        raise ValueError("Stop und Ziel sind Abstaende und deshalb positiv.")

    ergebnis = np.empty((ziehungen, len(dauern)))
    for i, dauer in enumerate(dauern):
        d = int(dauer)
        hoechster = max(int(bis) - d, int(von) + 1)
        start = rng.integers(von, hoechster, size=ziehungen)
        # Balken 1..d nach dem Einstieg, am Rand der Reihe abgeschnitten.
        felder = np.minimum(start[:, None] + np.arange(1, d + 1)[None, :], bis)
        einstieg = schluss[start]
        stopniveau = einstieg * (1.0 - stop)
        zielniveau = einstieg * (1.0 + ziel)

        traf_stop = tief[felder] <= stopniveau[:, None]
        traf_ziel = hoch[felder] >= zielniveau[:, None]
        # ``argmax`` liefert 0, wenn nichts zutrifft - deshalb die Maske.
        wann_stop = np.where(traf_stop.any(axis=1), traf_stop.argmax(axis=1), d)
        wann_ziel = np.where(traf_ziel.any(axis=1), traf_ziel.argmax(axis=1), d)

        # Drei Faelle, ausgeschrieben statt uebereinandergelegt: Der erste
        # Entwurf stapelte drei ``np.where`` und kam nur durch die
        # Reihenfolge auf das richtige Ergebnis - lesbar war das nicht.
        am_schluss = schluss[felder[:, -1]] / einstieg - 1.0
        stop_zuerst = (wann_stop < d) & (wann_stop <= wann_ziel)
        ziel_zuerst = (wann_ziel < d) & (wann_ziel < wann_stop)
        ergebnis[:, i] = np.where(
            stop_zuerst, -stop, np.where(ziel_zuerst, ziel, am_schluss)
        )
    return ergebnis.mean(axis=1)


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
            "Und die Ziehung hat keine Stops, die Regel schon. Bis Befund 200 "
            "stand hier, das mache das Ergebnis zu einer **Obergrenze** - "
            "gemessen ist das Gegenteil: Mit denselben Deckeln faellt die "
            "Null deutlich, weil ein zufaelliger Einstieg oefter am Stop "
            "endet als ein gewaehlter. Diese Zeilen sind damit eine "
            "**Untergrenze**."
        )
        return "\n".join(zeilen)


__all__ = [
    "MINDEST_Z",
    "Marktprobe",
    "Zufallsbild",
    "zufallsverteilung",
    "zufallsverteilung_mit_deckeln",
]
