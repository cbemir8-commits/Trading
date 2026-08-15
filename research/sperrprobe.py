"""Leistet eine Sperre mehr, als es dieselbe Zahl beliebiger Sperren taete?

Warum diese Frage sofort nach Befund 58 kommt
---------------------------------------------
Das Schock-Overlay hat 13 von 165 Einstiegen entfernt, und zwei Gates sind
umgekippt - von 7 auf 9 von 11. Das ist das beste Ergebnis, das dieses Projekt
je hatte, und genau deshalb gehoert es geprueft, bevor es jemand glaubt.

Denn es gibt eine zweite Erklaerung, die dieselben Zahlen erzeugt: **Weniger
Trades sind manchmal einfach besser.** Wer aus 165 Einstiegen irgendwelche 13
streicht, veraendert Rueckgang und schlechtestes Jahr; bei genug Versuchen
findet man immer eine Auswahl, die gut aussieht. Wenn zufaelliges Streichen
genauso oft neun von elf erzeugt, hat das Overlay nichts geleistet - es hat
nur gestrichen.

Die Null, gegen die geprueft wird
---------------------------------
Nicht "irgendwelche Kerzen sperren" - das traefe meist gar kein Signal.
Gezogen werden **Einstiegssignale**, genauso viele wie das Overlay trifft, und
zwar **je Bein einzeln**: Das Overlay sperrt 6 in BTC und 7 in ETH, also tut
die Null das auch. Eine Null, die anders verteilt ist als die Messung, misst
die Verteilung mit.

Was das kostet und was nicht
----------------------------
**Keinen Versuch.** Geprueft wird nicht, ob ein neuer Kandidat besteht,
sondern ob ein bereits gemessener Effekt echt ist. Der Versuchszaehler zaehlt
Hypothesen ueber den Markt, nicht Kontrollrechnungen ueber die eigene Messung.

Die teuren Gates bleiben aussen vor
-----------------------------------
Kosten-Stress und Parameter-Plateau brauchen je Auswertung mehrere komplette
Laeufe; zweihundert Ziehungen davon waeren Stunden. Verglichen wird deshalb
ueber die neun guenstigen Gates und ueber die Kennzahlen, an denen sich der
Effekt zeigt. **Das Parameter-Plateau ist damit ausdruecklich nicht
abgesichert** - es ist eines der beiden Gates, die umgekippt sind, und das
gehoert dazugesagt statt verschwiegen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True, slots=True)
class Ergebnis:
    """Was ein Lauf mit gesperrten Einstiegen erreicht hat."""

    trades: int
    rueckgang_pct: float
    schlechtestes_jahr_pct: float
    sharpe_je_trade: float
    dsr: float
    bestanden: int
    gesamt: int


@dataclass(slots=True)
class Sperrprobe:
    """Der gemessene Fall gegen viele zufaellige Sperren gleicher Groesse."""

    echt: Ergebnis
    zufall: list[Ergebnis] = field(default_factory=list)

    def _anteil_mindestens(self, holen, wert: float) -> float:
        """Anteil der Ziehungen, die mindestens so gut sind wie ``wert``."""
        werte = [holen(z) for z in self.zufall]
        return float(np.mean([w >= wert for w in werte])) if werte else 1.0

    @property
    def p_gates(self) -> float:
        return self._anteil_mindestens(lambda z: z.bestanden, self.echt.bestanden)

    @property
    def p_rueckgang(self) -> float:
        """Kleiner ist besser - deshalb umgedreht."""
        return self._anteil_mindestens(
            lambda z: -z.rueckgang_pct, -self.echt.rueckgang_pct
        )

    @property
    def p_jahr(self) -> float:
        return self._anteil_mindestens(
            lambda z: z.schlechtestes_jahr_pct, self.echt.schlechtestes_jahr_pct
        )

    @property
    def p_qualitaet(self) -> float:
        return self._anteil_mindestens(
            lambda z: z.sharpe_je_trade, self.echt.sharpe_je_trade
        )

    @property
    def besteht(self) -> bool:
        """Hebt sich die gemessene Sperre vom blossen Streichen ab?

        **Das Kriterium steht vor der Messung fest.** Entscheidend ist die
        Zahl bestandener Gates: Wenn hoechstens fuenf Prozent der zufaelligen
        Ziehungen genauso viele Gates halten, war die Auswahl der gesperrten
        Einstiege nicht beliebig.

        Bewusst **nicht** "irgendeine der vier Kennzahlen ist signifikant" -
        wer vier Zahlen prueft und die beste nimmt, findet fast immer eine.
        """
        return bool(self.zufall) and self.p_gates <= 0.05

    def bericht(self) -> str:
        if not self.zufall:
            return "Keine Ziehungen - nichts zu vergleichen."

        def spanne(holen) -> str:
            werte = [holen(z) for z in self.zufall]
            return (
                f"{np.median(werte):.3f} "
                f"[{np.min(werte):.3f} bis {np.max(werte):.3f}]"
            )

        zeilen = [
            f"{len(self.zufall)} zufaellige Sperren derselben Groesse:",
            "",
            f"{'Kennzahl':<20} {'gemessen':>10} {'Zufall (Median, Spanne)':>34} "
            f"{'Anteil':>8}",
            "-" * 76,
            f"{'Gates bestanden':<20} "
            f"{self.echt.bestanden:>7}/{self.echt.gesamt:<2} "
            f"{spanne(lambda z: float(z.bestanden)):>34} {self.p_gates:>7.1%}",
            f"{'Rueckgang %':<20} {self.echt.rueckgang_pct:>10.2f} "
            f"{spanne(lambda z: z.rueckgang_pct):>34} {self.p_rueckgang:>7.1%}",
            f"{'Schlechtestes Jahr':<20} "
            f"{self.echt.schlechtestes_jahr_pct:>10.2f} "
            f"{spanne(lambda z: z.schlechtestes_jahr_pct):>34} {self.p_jahr:>7.1%}",
            f"{'Sharpe je Trade':<20} {self.echt.sharpe_je_trade:>10.4f} "
            f"{spanne(lambda z: z.sharpe_je_trade):>34} {self.p_qualitaet:>7.1%}",
        ]
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.zufall:
            return "Keine Ziehungen - nichts zu sagen."
        if self.besteht:
            return (
                f"**Die Sperre leistet mehr als blosses Streichen.** Nur "
                f"{self.p_gates:.1%} der zufaelligen Sperren derselben Groesse "
                f"halten so viele Gates wie die gemessene. Es lag also an der "
                f"Auswahl der gesperrten Einstiege, nicht an ihrer Zahl."
            )
        return (
            f"**Der Effekt haelt der Kontrolle nicht stand.** "
            f"{self.p_gates:.1%} der zufaelligen Sperren derselben Groesse "
            f"halten genauso viele Gates. Dann war es nicht die Auswahl, "
            f"sondern das Streichen - dieselbe Zahl beliebiger Einstiege "
            f"weniger haette es auch getan."
        )


def ziehe_signale(
    signale: dict[str, np.ndarray], anzahl: dict[str, int], *, saat: int
) -> dict[str, np.ndarray]:
    """Je Bein so viele Signalkerzen zufaellig sperren wie vorgegeben.

    Je Bein einzeln, weil das Overlay ungleich trifft (6 in BTC, 7 in ETH).
    Eine Null, die anders verteilt ist als die Messung, misst die Verteilung
    mit statt den Effekt.
    """
    rng = np.random.default_rng(saat)
    gezogen: dict[str, np.ndarray] = {}
    for name, treffer in signale.items():
        stellen = np.flatnonzero(treffer)
        wie_viele = min(anzahl.get(name, 0), len(stellen))
        wahl = rng.choice(stellen, size=wie_viele, replace=False)
        maske = np.zeros(len(treffer), dtype=bool)
        maske[wahl] = True
        gezogen[name] = maske
    return gezogen
