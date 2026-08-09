"""Sagt die Konfluenz etwas ueber den Ausgang - oder nur ueber die Groesse?

Die Annahme, die nie geprueft wurde
-----------------------------------
Die Konviktions-Groessenlogik ruht auf einem Satz: **Je mehr
Zusatzbedingungen erfuellt sind, desto besser der Trade.** Danach richtet sich
der Einsatz - wer alle erfuellt, handelt gross, wer keine erfuellt, klein.

Gemessen wurde bisher nur die *Wirkung* dieser Logik auf das Gesamtergebnis,
nie die Annahme selbst. Das ist ein Unterschied: Eine Groessenlogik kann
funktionieren, weil sie in schlechten Phasen kleiner handelt, ohne dass die
Reihenfolge stimmt, nach der sie das tut.

Warum das den Deflated Sharpe erklaert
--------------------------------------
Alle drei Groessenregler - Vola-Ziel, Stop, Konviktion - bewegen den Deflated
Sharpe um weniger als 0,02. Bei den ersten beiden ist das einsichtig: Sie
skalieren alles gleich, und ein Verhaeltnis aendert sich davon nicht. Die
Konviktion tut das **nicht** - sie verschiebt Gewichte zwischen Trades. Dass
auch sie nichts bewegt, hat also einen anderen Grund, und der liegt in der
Annahme.

Was hier gemessen wird
----------------------
Je Trade: wie viele Konfluenzbedingungen bei seinem Einstieg erfuellt waren,
und was aus ihm geworden ist. Ausgewertet wird die **Rangkorrelation** gegen
eine Permutationsnull - kein Tabellenwert, und kein Mittelwertvergleich, der
bei stark schiefen R-Verteilungen von einem einzigen Ausreisser lebt.

Bewusst benutzt wird ``CompiledStrategy._condition_series`` - dieselbe
Auswertung, die auch der Backtest fuer die Groesse verwendet. Eine zweite
Umsetzung derselben Bedingung waere die naechste Stelle, an der zwei Zahlen
auseinanderlaufen.

Was daraus **nicht** folgt
--------------------------
Findet sich, dass nur die volle Konfluenz traegt, ist "handle nur bei voller
Konfluenz" **keine** Schlussfolgerung, sondern die Auswahl des besten Eimers
nach Ansicht der Daten. Das ist genau die Ueberanpassung, gegen die die
Zulassungsstrecke gebaut ist - und fuer diese Regelfamilie ist der
Bestaetigungsfilter ohnehin schon gemessen und widerlegt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise

import numpy as np
import pandas as pd

#: Ab wie vielen Trades ein einzelner Eimer ueberhaupt etwas sagt. Darunter
#: wird die Zahl gezeigt, aber nicht gedeutet.
MIND_TRADES = 20

#: Ziehungen fuer die Permutationsnull.
PERMUTATIONEN = 2000


@dataclass(frozen=True, slots=True)
class Eimer:
    """Alle Trades mit derselben Zahl erfuellter Bedingungen."""

    bedingungen: int
    ergebnisse: tuple[float, ...]

    @property
    def anzahl(self) -> int:
        return len(self.ergebnisse)

    @property
    def mittel(self) -> float:
        return float(np.mean(self.ergebnisse)) if self.ergebnisse else 0.0

    @property
    def median(self) -> float:
        return float(np.median(self.ergebnisse)) if self.ergebnisse else 0.0

    @property
    def trefferquote(self) -> float:
        if not self.ergebnisse:
            return 0.0
        return float(np.mean([x > 0 for x in self.ergebnisse]))

    @property
    def aussagekraeftig(self) -> bool:
        return self.anzahl >= MIND_TRADES


@dataclass(slots=True)
class Wirkung:
    """Was die Konfluenz ueber den Ausgang sagt."""

    eimer: list[Eimer] = field(default_factory=list)
    rho: float = 0.0
    p_wert: float = 1.0

    @property
    def trades(self) -> int:
        return sum(e.anzahl for e in self.eimer)

    @property
    def belegt(self) -> bool:
        """Ist der Zusammenhang gegen die Permutationsnull nachgewiesen?"""
        return self.trades > 0 and self.p_wert <= 0.05

    @property
    def monoton(self) -> bool:
        """Steigt das mittlere Ergebnis mit jeder weiteren Bedingung?

        Die Groessenlogik setzt das voraus - sie verteilt den Einsatz entlang
        dieser Reihenfolge. Stimmt sie nicht, verteilt sie ihn entlang einer
        Ordnung, die es so nicht gibt.

        Gewertet werden nur Eimer mit genug Trades: Ein Ausreisser aus vier
        Beobachtungen darf die Reihenfolge weder herstellen noch zerstoeren.
        """
        werte = [e.mittel for e in sorted(self.eimer, key=lambda x: x.bedingungen)
                 if e.aussagekraeftig]
        return len(werte) >= 2 and all(
            b >= a for a, b in pairwise(werte)
        )

    def tabelle(self) -> str:
        if not self.eimer:
            return "Keine Trades - nichts zu pruefen."
        zeilen = [
            f"{'Bedingungen':>12} {'Trades':>7} {'Mittel R':>10} "
            f"{'Median R':>10} {'Treffer':>9}",
            "-" * 52,
        ]
        for e in sorted(self.eimer, key=lambda x: x.bedingungen):
            marke = "" if e.aussagekraeftig else "  (zu wenige)"
            zeilen.append(
                f"{e.bedingungen:>12} {e.anzahl:>7} {e.mittel:>10.3f} "
                f"{e.median:>10.3f} {e.trefferquote:>8.1%}{marke}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.eimer:
            return "Keine Trades - kein Urteil."

        teile = [
            f"Rangkorrelation zwischen Bedingungszahl und Ergebnis: "
            f"rho = {self.rho:+.3f}, p = {self.p_wert:.3f}."
        ]
        if self.belegt:
            teile.append("Der Zusammenhang ist gegen die Permutationsnull belegt.")
        else:
            teile.append(
                "Damit ist der Zusammenhang **nicht** belegt - er kann da sein, "
                "aber aus diesen Trades laesst er sich nicht von Zufall "
                "unterscheiden."
            )

        if not self.monoton:
            teile.append(
                "Und er ist nicht einmal der Reihe nach: Das mittlere Ergebnis "
                "steigt nicht mit jeder weiteren Bedingung. Die Groessenlogik "
                "verteilt den Einsatz also entlang einer Ordnung, die so nicht "
                "gilt."
            )
        else:
            teile.append("Die Reihenfolge stimmt: mehr Bedingungen, besseres Mittel.")

        klein = [e for e in self.eimer if not e.aussagekraeftig]
        if klein:
            teile.append(
                f"{len(klein)} von {len(self.eimer)} Eimern haben weniger als "
                f"{MIND_TRADES} Trades - dort ist auch das Gegenteil nicht "
                f"gezeigt."
            )
        return " ".join(teile)


def zaehle_bedingungen(strategie, frame: pd.DataFrame) -> np.ndarray:
    """Wie viele Konfluenzbedingungen sind je Balken erfuellt?

    Ueber ``_condition_series`` der kompilierten Strategie - dieselbe
    Auswertung, die der Backtest fuer die Groesse benutzt. Eine zweite
    Umsetzung waere die naechste Stelle, an der zwei Zahlen auseinanderlaufen.
    """
    konfluenz = strategie.genome.konfluenz
    if not konfluenz:
        return np.zeros(len(frame), dtype=int)
    reihen = [strategie._condition_series(frame, b) for b in konfluenz]
    return np.sum(reihen, axis=0).astype(int)


def messe(
    trades,
    zaehlung: dict[str, pd.Series],
    *,
    permutationen: int = PERMUTATIONEN,
    saat: int = 20260809,
) -> Wirkung:
    """Trades nach erfuellten Bedingungen aufteilen und den Zusammenhang pruefen.

    ``zaehlung`` bildet den Markt auf eine Reihe ab, die zu jedem
    Kerzenzeitpunkt die Zahl erfuellter Bedingungen enthaelt. Zugeordnet wird
    ueber den Einstiegszeitpunkt: Der Symbolname der Trades ist im
    Portfoliolauf fuer alle Beine derselbe und taugt nicht.
    """
    nach_zahl: dict[int, list[float]] = {}
    for trade in trades:
        ergebnis = trade.r_multiple
        if ergebnis is None:
            continue
        zeit = pd.Timestamp(trade.entry_time)
        for reihe in zaehlung.values():
            if zeit in reihe.index:
                nach_zahl.setdefault(int(reihe.loc[zeit]), []).append(float(ergebnis))
                break

    eimer = [
        Eimer(bedingungen=n, ergebnisse=tuple(werte))
        for n, werte in sorted(nach_zahl.items())
    ]
    if not eimer:
        return Wirkung()

    x = np.array([e.bedingungen for e in eimer for _ in e.ergebnisse], dtype=float)
    y = np.array([w for e in eimer for w in e.ergebnisse], dtype=float)
    if len(np.unique(x)) < 2 or len(y) < 3:
        return Wirkung(eimer=eimer)

    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    rho = float(np.corrcoef(rx, ry)[0, 1])

    rng = np.random.default_rng(saat)
    null = [
        abs(float(np.corrcoef(rx, rng.permutation(ry))[0, 1]))
        for _ in range(permutationen)
    ]
    return Wirkung(
        eimer=eimer,
        rho=rho,
        p_wert=float(np.mean([v >= abs(rho) for v in null])),
    )
