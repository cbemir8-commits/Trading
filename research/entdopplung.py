"""Dieselbe Regel unter mehreren Namen - und was sie in einer Statistik anrichtet.

Der Anlass
----------
Der Katalog enthaelt Genome, die verschieden heissen und identische Trades
liefern. Auf Tageskerzen sind es sechs von 21:

    Trend-Beteiligung 200 Tage        Trend mit Vola-Ziel 20 %
    Trend-Beteiligung voller Einsatz  Trend mit Vola-Ziel 22 %
    Vola-Ziel, kurzes Messfenster     Vola-Ziel, langes Messfenster

Sie unterscheiden sich in Feldern, die auf diesen Daten nichts aendern - etwa
einem Vola-Messfenster, das bei dieser Signalhaeufigkeit nie greift. Alle
sieben Namen (mit 'Trend-Beteiligung (fair gerechnet)') stehen fuer **eine**
Regel mit 53 Trades.

Was das anrichtet
-----------------
In Befund 86 und 87 habe ich ueber den Katalog gemittelt, ohne zu entdoppeln.
Die Folge, beide Male nachgerechnet:

    Befund 87, Zeitachse
      mittlere Luecke        20,2 %  ->  11,7 %
      Deckung durch das Gate   15 %  ->    32 %
      r(Gate, Zeit)          -0,470  ->  -0,261   (t = -0,86: faellt weg)

    Befund 86, Verbundmodell
      Kartenfehler           +0,238  ->  -0,029   (Vorzeichen dreht sich)
      r(rho, Fehler)         +0,752  ->  +0,440   (t = +4,97: haelt)

Ausgerechnet die siebenfach gezaehlte Regel ist die mit der groessten
Zeit-Luecke (37 %) und ohne jede Gate-Kuerzung. Sie hat den Befund also nicht
bloss verstaerkt, sondern erzeugt.

Warum das kein Detail ist
-------------------------
Ein Duplikat ist keine zweite Beobachtung. Es liefert dieselbe Zahl noch
einmal, senkt damit die Streuung der Stichprobe und hebt jeden t-Wert - also
genau das, was ueber "nachweisbar" entscheidet. Bei sieben Kopien in 21
Punkten ist das kein Randeffekt.

``anwaerter`` und ``phasen`` entdoppeln laengst, jeweils mit eigener,
handgeschriebener Logik. Genau daran ist es hier gescheitert: Zwei neue
Befehle wurden gebaut, und die Entdopplung fehlte in beiden, weil sie nirgends
als Baustein stand.

Die Signatur
------------
Verglichen werden nicht Namen und nicht Kennzahlen, sondern die Trades selbst:
Zeitpunkt und Ergebnis, gerundet. Zwei Genome, die exakt dieselben Geschaefte
zur exakt selben Zeit machen, **sind** auf diesen Daten dieselbe Regel - egal,
wie verschieden ihre Felder aussehen.

Gerundet wird auf sechs Stellen, weil Fliesskomma sonst zwei identische Laeufe
auseinanderhaelt. Wer feiner rundet, entdoppelt nicht mehr; wer groeber
rundet, wirft verschiedene Regeln zusammen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Stellen, auf die Trade-Ergebnisse fuer den Vergleich gerundet werden.
STELLEN = 6


def signatur(trades) -> tuple:
    """Was eine Regel auf diesen Daten **tut** - unabhaengig von ihrem Namen.

    Bewusst nicht ueber Kennzahlen: Zwei verschiedene Regeln koennen zufaellig
    denselben Sharpe haben, und dann wuerde eine davon verschwinden. Zwei
    Regeln mit denselben Trades zur selben Zeit sind dagegen dieselbe Regel.
    """
    return tuple(
        (t.exit_time.isoformat(), round(float(t.net_pnl), STELLEN))
        for t in sorted(trades, key=lambda x: (x.exit_time, x.net_pnl))
    )


@dataclass(slots=True)
class Entdoppelt:
    """Was uebrig bleibt - und was weggefallen ist."""

    laeufe: dict[str, list] = field(default_factory=dict)
    doppel: dict[str, str] = field(default_factory=dict)
    """Weggefallener Name -> der Name, unter dem die Regel bleibt."""

    @property
    def entfernt(self) -> int:
        return len(self.doppel)

    @property
    def gruppen(self) -> dict[str, list[str]]:
        """Je bleibender Regel die Namen, die auf sie zeigen."""
        aus: dict[str, list[str]] = {}
        for weg, bleibt in self.doppel.items():
            aus.setdefault(bleibt, []).append(weg)
        return aus

    def hinweis(self) -> str:
        if not self.doppel:
            return ""
        teile = [
            f"'{bleibt}' steht auch fuer {len(namen)} weitere"
            for bleibt, namen in sorted(
                self.gruppen.items(), key=lambda x: -len(x[1])
            )
        ]
        return (
            f"{self.entfernt} von {self.entfernt + len(self.laeufe)} Genomen "
            f"liefern identische Trades und zaehlen einfach: "
            f"{'; '.join(teile)}."
        )


def entdoppele(laeufe: dict[str, list]) -> Entdoppelt:
    """Genome mit identischen Trades auf eines zusammenziehen.

    Es bleibt jeweils der **erste** Name in der Eingabereihenfolge. Wer den
    Bestand zuerst uebergibt, behaelt also seinen Namen - das ist gewollt, denn
    unter dem steht er in jedem anderen Bericht.
    """
    bleibt: dict[str, list] = {}
    doppel: dict[str, str] = {}
    gesehen: dict[tuple, str] = {}
    for name, trades in laeufe.items():
        s = signatur(trades)
        vorher = gesehen.get(s)
        if vorher is None:
            gesehen[s] = name
            bleibt[name] = trades
        else:
            doppel[name] = vorher
    return Entdoppelt(laeufe=bleibt, doppel=doppel)


__all__ = ["STELLEN", "Entdoppelt", "entdoppele", "signatur"]
