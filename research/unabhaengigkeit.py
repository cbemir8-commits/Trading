"""Wie viele der gezaehlten Trades sind wirklich unabhaengige Beobachtungen?

**Ein Loch im Deflated-Sharpe-Gate, gefunden beim Ausmessen eines Hebels, den
ich eigentlich nutzen wollte.**

Die Engine kann dieselbe Regel mit mehreren Perioden gleichzeitig handeln, je
Bein ein Anteil - gebaut genau gegen die Abhaengigkeit von wenigen Trades.
Gemessen am Spitzenkandidaten mit den Faktoren 0,7 / 1,0 / 1,3:

    einzeln    154 Trades   DSR 0,802
    Ensemble   481 Trades   DSR 0,999

Das Gate waere bestanden. Nur zaehlt es **rohe Trades**, und die Formel von
Bailey und Lopez de Prado setzt unabhaengige Beobachtungen voraus. Nachgemessen
an den Fenstergewinnen:

    BTC@0,7 / BTC@1,0    Korrelation 0,069
    BTC@1,0 / BTC@1,3    Korrelation 0,007
    ETH@0,7 / ETH@1,0    Korrelation 0,884
    ETH@0,7 / ETH@1,3    Korrelation 0,585

Auf BTC liefern verschiedene Perioden tatsaechlich verschiedene Trades. Auf ETH
sind es fast dieselben - drei Beine, aber kaum mehr Information als eines.

Damit laesst sich das haerteste Gate des Systems umgehen, ohne die Strategie zu
verbessern: Man teilt eine Position in drei fast gleiche Teile und zaehlt
dreimal. Wer die Perioden noch enger waehlt (0,9 / 1,0 / 1,1), treibt die Zahl
weiter hoch und den Informationsgehalt gegen null.

**Deshalb wird hier korrigiert statt ausgenutzt.** Bei ``k`` Beinen mit
mittlerer Korrelation ``rho`` faellt die Varianz des Mittelwerts nur um
``1 / (1 + (k-1) * rho)`` statt um ``1/k``. Das entspricht

    k_effektiv = k / (1 + (k - 1) * rho)

unabhaengigen Beinen. Bei rho = 0 bleibt es bei ``k``, bei rho = 1 wird es 1.

**Negative Korrelation gibt keinen Bonus.** ``rho`` wird bei null abgeschnitten.
Sonst liesse sich die effektive Zahl ueber die rohe heben, indem man
gegenlaeufige Beine dazunimmt - dieselbe Umgehung von der anderen Seite. Die
Korrektur darf nur strenger machen, nie milder.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

#: Mindestzahl gemeinsamer Fenster, um eine Korrelation zu schaetzen. Darunter
#: ist der Schaetzwert so unsicher, dass die Korrektur mehr schadet als nutzt -
#: dann wird konservativ mit voller Korrelation gerechnet.
MIND_FENSTER = 8


@dataclass(frozen=True, slots=True)
class Effektivwert:
    """Rohe und effektive Zahl der Beobachtungen."""

    roh: int
    effektiv: int
    beine: int
    korrelation: float

    @property
    def faktor(self) -> float:
        return self.effektiv / self.roh if self.roh else 1.0

    def bericht(self) -> str:
        if self.beine < 2:
            return f"{self.roh} Trades, ein Bein - keine Korrektur noetig."
        import math

        if math.isnan(self.korrelation):
            return (
                f"{self.roh} rohe Trades entsprechen {self.effektiv} "
                f"unabhaengigen ({self.faktor:.0%}), per Block-Bootstrap "
                f"ueber die Fenster gemessen."
            )
        return (
            f"{self.roh} rohe Trades aus {self.beine} Beinen mit mittlerer "
            f"Korrelation {self.korrelation:.3f} entsprechen {self.effektiv} "
            f"unabhaengigen ({self.faktor:.0%})."
        )


def mittlere_korrelation(beine: dict[str, list[float]]) -> float:
    """Mittlere paarweise Korrelation der Fenstergewinne, bei null gekappt.

    Gerechnet auf den **Fenstergewinnen**, nicht auf einzelnen Trades: Zwei
    Beine handeln zu verschiedenen Zeitpunkten, ihre Trades lassen sich nicht
    paaren. Das Fenster ist die kleinste Einheit, in der beide etwas
    beigetragen haben.
    """
    namen = [n for n, werte in beine.items() if len(werte) >= MIND_FENSTER]
    if len(namen) < 2:
        return 0.0

    laenge = min(len(beine[n]) for n in namen)
    reihen = {n: np.asarray(beine[n][:laenge], dtype=float) for n in namen}

    werte = []
    for a, b in combinations(namen, 2):
        x, y = reihen[a], reihen[b]
        if np.std(x) == 0 or np.std(y) == 0:
            # Ein Bein ohne jede Streuung traegt keine eigene Information.
            werte.append(1.0)
            continue
        werte.append(float(np.corrcoef(x, y)[0, 1]))

    return max(0.0, float(np.mean(werte))) if werte else 0.0


def bootstrap_stichprobe(
    bloecke: list[list[float]], *, ziehungen: int = 2000, saat: int = 20260808
) -> int | None:
    """Effektive Stichprobe per Block-Bootstrap - ohne Annahme ueber die Form.

    ``bloecke`` sind die Trade-Ergebnisse je Fenster. Ein Fenster ist der
    richtige Block, weil innerhalb eines Fensters dieselbe Marktphase auf alle
    Beine wirkt - genau die Abhaengigkeit, um die es geht.

    Verglichen wird die Streuung des Mittelwerts bei blockweisem Ziehen mit der
    bei einzelnem Ziehen. Ist sie 1,32-mal so gross, stecken in ``n`` Trades nur
    ``n / 1,32`` unabhaengige Beobachtungen.

    Das ist der Grund, warum diese Funktion der Korrelationsformel vorgezogen
    wird: Sie setzt nichts voraus. Die Formel unterstellt gleich gewichtete
    Beine und eine einheitliche Korrelation; gemessen am Spitzenkandidaten kam
    sie auf 107 von 154, der Bootstrap auf 117. Nah beieinander, aber die
    Messung ist die Messung.

    ``None``, wenn zu wenige Bloecke fuer eine belastbare Schaetzung da sind.
    """
    verwendbar = [b for b in bloecke if b]
    if len(verwendbar) < MIND_FENSTER:
        return None

    alle = np.asarray([x for b in verwendbar for x in b], dtype=float)
    n = len(alle)
    if n < 3 or float(np.std(alle, ddof=1)) == 0:
        return None

    rng = np.random.default_rng(saat)
    einzeln = np.array([
        float(np.mean(rng.choice(alle, size=n, replace=True)))
        for _ in range(ziehungen)
    ])
    blockweise = np.empty(ziehungen)
    for i in range(ziehungen):
        wahl = rng.integers(0, len(verwendbar), size=len(verwendbar))
        blockweise[i] = float(np.mean(np.concatenate([verwendbar[j] for j in wahl])))

    var_iid = float(np.var(einzeln, ddof=1))
    var_block = float(np.var(blockweise, ddof=1))
    if var_block <= 0 or var_iid <= 0:
        return None

    # Nur nach unten korrigieren: Weniger Streuung als bei Unabhaengigkeit
    # waere kein Grund, mehr Evidenz zu behaupten.
    return max(1, min(n, round(n * var_iid / var_block)))


def effektive_stichprobe(
    roh_trades: int,
    beine: dict[str, list[float]] | None,
    bloecke: list[list[float]] | None = None,
) -> Effektivwert:
    """Wie viele unabhaengige Beobachtungen stecken in ``roh_trades``?

    ``beine`` bildet Bein-Name auf die Fenstergewinne dieses Beins ab. Fehlt
    es oder gibt es nur ein Bein, bleibt alles, wie es war - der heutige
    Spitzenkandidat wird von dieser Korrektur nicht beruehrt.
    """
    # Der Bootstrap misst, die Formel schaetzt - also zuerst messen.
    if bloecke:
        gemessen = bootstrap_stichprobe(bloecke)
        if gemessen is not None:
            return Effektivwert(
                roh=roh_trades,
                effektiv=min(roh_trades, gemessen),
                beine=len(beine or {}),
                korrelation=float("nan"),
            )

    if not beine or len(beine) < 2:
        return Effektivwert(
            roh=roh_trades, effektiv=roh_trades, beine=len(beine or {}),
            korrelation=0.0,
        )

    k = len(beine)
    zu_wenig = any(len(w) < MIND_FENSTER for w in beine.values())
    if zu_wenig:
        # Ohne belastbare Schaetzung im Zweifel gegen die Strategie: volle
        # Korrelation, also so viele unabhaengige Beobachtungen wie ein Bein.
        return Effektivwert(
            roh=roh_trades, effektiv=max(1, roh_trades // k), beine=k,
            korrelation=1.0,
        )

    rho = mittlere_korrelation(beine)
    k_effektiv = k / (1 + (k - 1) * rho)
    return Effektivwert(
        roh=roh_trades,
        effektiv=max(1, round(roh_trades * k_effektiv / k)),
        beine=k,
        korrelation=rho,
    )
