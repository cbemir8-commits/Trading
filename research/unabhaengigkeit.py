"""Wie viele der gezaehlten Trades sind wirklich unabhaengige Beobachtungen?

**Ein Loch im Deflated-Sharpe-Gate - und eine Korrektur an der Korrektur.**

Die Engine kann dieselbe Regel mit mehreren Perioden gleichzeitig handeln, je
Bein ein Anteil. Gemessen am Spitzenkandidaten mit den Faktoren 0,7 / 1,0 / 1,3:

    einzeln    154 Trades   DSR 0,802
    Ensemble   481 Trades   DSR 0,999

Das Gate waere bestanden gewesen - mit einer Regel, die nichts Neues kann. Denn
es zaehlte **rohe Trades**, und die Formel von Bailey und Lopez de Prado setzt
unabhaengige Beobachtungen voraus. Auf ETH korrelierten die Fenstergewinne
zweier Perioden mit 0,884; drei Beine, kaum mehr Information als eines. So
laesst sich das haerteste Gate umgehen, ohne die Strategie zu verbessern:
Position dritteln, dreimal zaehlen.

**Und dann der zweite Teil, der mir fast durchgegangen waere.**

Der erste Anlauf schaetzte die effektive Stichprobe per Block-Bootstrap und kam
am Kandidaten auf 111 von 154. Der Wert wanderte sofort ins Gate, und der
Deflated Sharpe fiel von 0,802 auf 0,534 - die wichtigste Zahl des Projekts,
geaendert auf Grundlage einer einzigen Schaetzung.

Die Gegenprobe gegen eine **bekannte Null** (dieselben Blockgroessen, Werte
durchgemischt, also garantiert unabhaengig) zeigte, dass das nicht traegt:

    echte Messung                     n_eff = 106 von 154
    Null, unabhaengige Werte   Mittel n_eff = 143, Spanne 78 bis 154
    Anteil der Null unter 106                  6,0 %

Bei dreissig Bloecken ungleicher Groesse ist der Schaetzer so verrauscht, dass
er auch ohne jede Abhaengigkeit auf 78 fallen kann. Die beobachtete Kuerzung
liegt im sechsten Perzentil - **nicht von Zufall zu unterscheiden.**

**Daraus die Regel, die dieses Modul umsetzt:** Gekuerzt wird nur, wenn die
Abhaengigkeit gegen die Permutationsnull nachgewiesen ist. Bei drei identischen
Beinen ist sie das mit grossem Abstand - dort greift die Korrektur. Bei zwei
Maerkten mit 154 Trades ist sie es nicht - dort bleibt es bei der rohen Zahl,
und die Unsicherheit wird berichtet statt in eine Zahl gegossen.

Das ist die mildere Richtung, und sie ist trotzdem richtig: Eine Strafe, die
reines Rauschen mit sechsprozentiger Wahrscheinlichkeit erzeugt, ist keine
Strenge, sondern eine Muenze. Wer sie einbaut, misst nicht mehr die Strategie.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

#: Mindestzahl Bloecke fuer eine Schaetzung. Darunter ist jede Aussage ueber
#: Abhaengigkeit haltlos.
MIND_BLOECKE = 8

#: Ab wann gilt die Abhaengigkeit als nachgewiesen. Der Anteil der
#: Permutationsziehungen, die mindestens so stark aussehen wie die Messung.
SIGNIFIKANZ = 0.05

#: Wie viele Permutationen fuer die Null. 200 genuegen fuer eine Schwelle bei
#: 5 % und bleiben schnell genug fuer den Wettbewerb.
PERMUTATIONEN = 200


@dataclass(frozen=True, slots=True)
class Effektivwert:
    """Rohe und effektive Zahl der Beobachtungen."""

    roh: int
    effektiv: int
    icc: float = 0.0
    p_wert: float = 1.0
    nachgewiesen: bool = False
    bloecke: int = 0

    @property
    def faktor(self) -> float:
        return self.effektiv / self.roh if self.roh else 1.0

    def bericht(self) -> str:
        if self.bloecke < MIND_BLOECKE:
            return f"{self.roh} Trades - zu wenige Bloecke fuer eine Aussage."
        if self.nachgewiesen:
            return (
                f"{self.roh} rohe Trades entsprechen {self.effektiv} "
                f"unabhaengigen ({self.faktor:.0%}). Abhaengigkeit "
                f"nachgewiesen: ICC {self.icc:.3f}, p = {self.p_wert:.3f}."
            )
        return (
            f"{self.roh} Trades, keine nachweisbare Abhaengigkeit "
            f"(ICC {self.icc:.3f}, p = {self.p_wert:.3f}) - es bleibt bei der "
            f"rohen Zahl. Das heisst nicht, dass keine da ist: Bei "
            f"{self.bloecke} Bloecken faellt erst eine deutliche auf."
        )


def mittlere_korrelation(beine: dict[str, list[float]]) -> float:
    """Mittlere paarweise Korrelation der Fenstergewinne, bei null gekappt.

    Beschreibend - fuer den Bericht, nicht fuer die Korrektur. Die Korrektur
    laeuft ueber ``designeffekt``, weil die dort gegen eine Null geprueft wird.
    """
    namen = [n for n, werte in beine.items() if len(werte) >= MIND_BLOECKE]
    if len(namen) < 2:
        return 0.0

    laenge = min(len(beine[n]) for n in namen)
    reihen = {n: np.asarray(beine[n][:laenge], dtype=float) for n in namen}

    werte = []
    for a, b in combinations(namen, 2):
        x, y = reihen[a], reihen[b]
        if np.std(x) == 0 or np.std(y) == 0:
            werte.append(1.0)
            continue
        werte.append(float(np.corrcoef(x, y)[0, 1]))

    return max(0.0, float(np.mean(werte))) if werte else 0.0


def _icc(bloecke: list[np.ndarray]) -> tuple[float, float] | None:
    """Intraklassen-Korrelation und Designeffekt, in geschlossener Form.

        m0    = (N - sum(n_i^2)/N) / (k-1)
        ICC   = (MSB - MSW) / (MSB + (m0-1) * MSW)
        deff  = 1 + (N/k - 1) * ICC

    Der uebliche Weg der Stichprobentheorie mit ungleichen Blockgroessen.
    Deterministisch - anders als ein Bootstrap gibt er bei jedem Aufruf
    dasselbe zurueck, und das ist bei einer Groesse, die ueber Zulassung
    entscheidet, keine Nebensaechlichkeit.
    """
    k = len(bloecke)
    n = sum(len(b) for b in bloecke)
    if k < 2 or n <= k:
        return None

    gesamt = np.concatenate(bloecke)
    gesamtmittel = float(gesamt.mean())
    zwischen = sum(len(b) * (float(b.mean()) - gesamtmittel) ** 2 for b in bloecke)
    innen = sum(float(((b - b.mean()) ** 2).sum()) for b in bloecke)

    msb = zwischen / (k - 1)
    msw = innen / (n - k)
    if msw <= 0:
        return None

    m0 = (n - sum(len(b) ** 2 for b in bloecke) / n) / (k - 1)
    nenner = msb + (m0 - 1) * msw
    icc = max(0.0, (msb - msw) / nenner) if nenner > 0 else 0.0
    return icc, 1 + (n / k - 1) * icc


def designeffekt(
    bloecke: list[list[float]],
    *,
    permutationen: int = PERMUTATIONEN,
    saat: int = 20260808,
) -> Effektivwert | None:
    """Effektive Stichprobe - gekuerzt nur bei nachgewiesener Abhaengigkeit.

    Die Permutationsnull ist der Kern: Dieselben Blockgroessen, aber die Werte
    durchgemischt. Damit ist jede Abhaengigkeit zerstoert und trotzdem alles
    andere gleich - insbesondere die ungleichen Blockgroessen, die den
    Schaetzer fuer sich genommen schon nach unten ziehen.

    ``None``, wenn zu wenige Bloecke da sind.
    """
    verwendbar = [np.asarray(b, dtype=float) for b in bloecke if len(b)]
    n = sum(len(b) for b in verwendbar)
    if len(verwendbar) < MIND_BLOECKE or n < 3:
        return None

    gemessen = _icc(verwendbar)
    if gemessen is None:
        return None
    icc, deff = gemessen

    groessen = [len(b) for b in verwendbar]
    alle = np.concatenate(verwendbar)
    rng = np.random.default_rng(saat)
    null = []
    for _ in range(permutationen):
        gemischt = rng.permutation(alle)
        teile, i = [], 0
        for groesse in groessen:
            teile.append(gemischt[i : i + groesse])
            i += groesse
        ergebnis = _icc(teile)
        if ergebnis is not None:
            null.append(ergebnis[1])

    if not null:
        return None

    # Wie oft sieht reines Rauschen mindestens so abhaengig aus?
    p = float(np.mean([x >= deff for x in null]))
    nachgewiesen = p <= SIGNIFIKANZ

    if nachgewiesen:
        # Gegen den Median der Null kalibrieren - der Rest waere der Anteil,
        # den schon die ungleichen Blockgroessen erzeugen.
        deff_korrigiert = max(1.0, deff / float(np.median(null)))
        effektiv = max(1, min(n, round(n / deff_korrigiert)))
    else:
        effektiv = n

    return Effektivwert(
        roh=n, effektiv=effektiv, icc=icc, p_wert=p,
        nachgewiesen=nachgewiesen, bloecke=len(verwendbar),
    )


def effektive_stichprobe(
    roh_trades: int,
    beine: dict[str, list[float]] | None = None,
    bloecke: list[list[float]] | None = None,
) -> Effektivwert:
    """Wie viele unabhaengige Beobachtungen stecken in ``roh_trades``?

    ``bloecke`` sind die Trade-Ergebnisse je Fenster - die eigentliche
    Grundlage. ``beine`` dient nur der Beschreibung.

    Ohne Blockdaten bleibt alles, wie es war. Eine Korrektur ohne Messung waere
    genau der Fehler, den dieses Modul verhindern soll.
    """
    if bloecke:
        ergebnis = designeffekt(bloecke)
        if ergebnis is not None:
            # **Den Faktor uebernehmen, nicht die Blocksumme.**
            #
            # Die Bloecke sollten alle Trades enthalten, aber "sollten" ist
            # keine Zusicherung: Wer Bloecke hereinreicht, die nur einen Teil
            # abdecken, bekaeme sonst still eine ganz andere Stichprobengroesse
            # ins Gate geschoben. Der Faktor ist die Aussage - die absolute
            # Zahl kommt vom Aufrufer.
            return Effektivwert(
                roh=roh_trades,
                effektiv=max(1, min(roh_trades, round(roh_trades * ergebnis.faktor))),
                icc=ergebnis.icc,
                p_wert=ergebnis.p_wert,
                nachgewiesen=ergebnis.nachgewiesen,
                bloecke=ergebnis.bloecke,
            )
    return Effektivwert(roh=roh_trades, effektiv=roh_trades, bloecke=0)
