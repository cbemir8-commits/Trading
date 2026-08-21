"""Steuert die Suche nach einem verfaelschten Signal?

Die Frage
---------
Jeder der 45 Eintraege in der Bestenliste ist bei 500 EUR gemessen - also
durch den Rundungsfilter aus Befund 95 hindurch. Der Filter ist **nicht
neutral**: Er schneidet kleine Positionen staerker ab als grosse, und wie
gross die Positionen sind, ist eine Eigenschaft des jeweiligen Genoms.

Falls die Rangfolge davon abhaengt, hat die Suche bisher nach einem
verfaelschten Signal gesteuert, und jeder Vergleich zweier Kandidaten stand
auf Sand. Das waere schlimmer als alles, was die Befunde 95 bis 97 gefunden
haben.

Die Antwort
-----------
**Sie haengt nicht davon ab.** Alle 23 Tageskerzen-Genome des Katalogs
zweimal gemessen - mit Bybits Mengenschritt und mit einem feinen, sonst
alles gleich, Versuchsstand 177 in jeder Zeile. Von den 13, die ueberhaupt
handeln, aendert **keines** seine Zahl bestandener Gates.

    Genom                            Trades    grob    fein   Luecke  Gates
    Momentum-Beteiligung 90 Tage         94   25,56   27,77    +2,20   2->2
    Trend-Beteiligung 100 Tage          101   18,40   19,91    +1,51   2->2
    Trend-Beteiligung 50 Tage           142   29,16   30,03    +0,87   5->5
    Donchian-Ausbruch 55/20              55   19,45   20,27    +0,82   6->6
    Vola-Ziel, langes Messfenster        51    6,97    7,46    +0,49   7->7
    Trend mit Vola-Ziel 20 %             51    8,03    8,18    +0,15   8->8
    Trend-Beteiligung 200 Tage           46   13,54   13,65    +0,11   5->5
    Trend beide Richtungen               84   27,76   27,43    -0,32   3->3

Die zehn Genome ohne Trades stehen nicht in der Tabelle. Sie bestehen fuenf
Gates, weil sie nicht handeln - ein Rang unter ihnen bedeutet nichts.

Warum der Bestand trotzdem kippt
--------------------------------
Sein Sprung (**+2,32** Punkte) ist kein Ausreisser: Das groesste Katalog-Genom
liegt bei +2,20. Er ist der einzige Kandidat, dessen Rueckgang **nahe an der
Grenze** steht - 10,64 % gegen 12 %. Ueberall sonst verschiebt dieselbe
Rundung eine Zahl, die weit von ihrer Schwelle entfernt liegt, und dann
aendert sich nichts.

Das ist die eigentliche Lehre: Die Koernung dreht kein Urteil, **ausser** die
Zahl liegt ohnehin dicht an der Schwelle. Dort dreht sie es zuverlaessig.

Eine Erklaerung, die ich geraten und widerlegt habe
---------------------------------------------------
Verdacht war der Konviktions-Faktor des Bestands: Er laeuft von 1/(1+Bonus)
bis 1,0, halbiert also die Position in schwachen Setups, und kleine
Positionen trifft das Abrunden am haertesten.

Gegenprobe mit Bonus 0, sonst unveraendert:

    mittlerer Anteil 0,165 -> 0,330   (Position verdoppelt)
    Luecke           +2,32 -> +2,22   (praktisch unveraendert)

**Der Verdacht war falsch.** Die doppelte Position aendert an der Luecke
nichts.

Und was die Streuung erklaert, ist nicht belegt
-----------------------------------------------
Die Luecken reichen von -0,32 bis +2,20 Punkte. Drei Erklaerungen geprueft,
ueber die 13 handelnden Genome:

    Hoehe des Rueckgangs   r = +0,413   t = +1,51
    Zahl der Trades        r = +0,543   t = +2,14
    Sharpe                 r = +0,115   t = +0,38

Die zweite ueberschreitet die uebliche Schwelle |t| >= 2 - und das ist
**kein Beleg**. Bei drei Pruefungen liegt die Schranke nach Bonferroni bei
2,39, nicht bei 2,0. Genau diese Korrektur ist das Thema des ganzen
Projekts; sie in der eigenen Auswertung zu vergessen waere die peinlichste
Stelle, an der man sie vergessen kann.

Die Zahl steht hier, damit jemand sie mit mehr Genomen nachpruefen kann.
Behauptet wird sie nicht.

Kostet keinen Versuch: Jedes Genom ist in beiden Spalten dasselbe, gemessen
wird der Mengenschritt, und ausgewaehlt wird nichts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import NormalDist

#: Die uebliche Schwelle dieses Projekts fuer eine einzelne Pruefung.
GRUNDSCHRANKE = 2.0


def schranke(hypothesen: int) -> float:
    """Ab welchem |t| ein Zusammenhang zaehlt, wenn ``hypothesen`` geprueft wurden.

    Bei einer Pruefung sind es die ueblichen 2,0. Bei dreien reicht das
    nicht: Die Wahrscheinlichkeit, dass **irgendeine** von drei reinen
    Zufallsgroessen die 2,0 reisst, liegt bei rund 14 %. Die Schranke wandert
    deshalb nach Bonferroni auf das Quantil zu ``0,05 / hypothesen``.

    Dieselbe Logik wie beim Versuchszaehler, nur eine Ebene hoeher: Dort
    korrigiert das Projekt das Testen vieler Strategien, hier das Testen
    vieler Erklaerungen fuer dieselbe Beobachtung.
    """
    k = max(1, int(hypothesen))
    if k == 1:
        return GRUNDSCHRANKE
    return float(NormalDist().inv_cdf(1 - 0.025 / k))


@dataclass(frozen=True, slots=True)
class Zusammenhang:
    """Eine gepruefte Erklaerung, mit der Schranke, die fuer sie gilt."""

    name: str
    r: float
    n: int
    hypothesen: int = 1

    @property
    def t_wert(self) -> float | None:
        if self.n < 3 or abs(self.r) >= 1.0:
            return None
        return self.r * ((self.n - 2) / (1 - self.r**2)) ** 0.5

    @property
    def schranke(self) -> float:
        return schranke(self.hypothesen)

    @property
    def belegt(self) -> bool:
        t = self.t_wert
        return t is not None and abs(t) >= self.schranke

    def __str__(self) -> str:
        t = self.t_wert
        wert = f"t = {t:+.2f}" if t is not None else "t nicht bestimmbar"
        return (
            f"{self.name:<22} r = {self.r:+.3f}   {wert}   "
            f"Schranke {self.schranke:.2f}   "
            f"{'belegt' if self.belegt else 'nicht belegt'}"
        )


@dataclass(frozen=True, slots=True)
class Doppel:
    """Ein Genom, zweimal gemessen: mit grobem und mit feinem Mengenschritt."""

    name: str
    trades: int
    grob_bestanden: int
    fein_bestanden: int
    grob_rueckgang: float
    fein_rueckgang: float
    gesamt: int = 11

    @property
    def handelt(self) -> bool:
        """Ohne Trades bedeutet ein Rang nichts.

        Zehn Katalog-Genome handeln auf diesen Daten gar nicht und bestehen
        trotzdem fuenf Gates - weil nichts schiefgehen kann, wo nichts
        passiert. Sie in den Vergleich zu nehmen hiesse, Stillstand als
        Stabilitaet zu zaehlen.
        """
        return self.trades > 0

    @property
    def luecke(self) -> float:
        """Um wie viele Punkte der Rueckgang ohne die Rundung hoeher liegt."""
        return self.fein_rueckgang - self.grob_rueckgang

    @property
    def relativ(self) -> float:
        return self.luecke / self.grob_rueckgang if self.grob_rueckgang else 0.0

    @property
    def urteil_wechselt(self) -> bool:
        return self.grob_bestanden != self.fein_bestanden


@dataclass(slots=True)
class Rangprobe:
    """Haelt die Rangfolge, wenn man die Mengenrundung entfernt?"""

    doppel: list[Doppel] = field(default_factory=list)

    @property
    def handelnde(self) -> list[Doppel]:
        return [d for d in self.doppel if d.handelt]

    @property
    def genug(self) -> bool:
        return len(self.handelnde) >= 3

    @property
    def wechsler(self) -> list[Doppel]:
        return [d for d in self.handelnde if d.urteil_wechselt]

    @property
    def rangfolge_haelt(self) -> bool:
        """Kein handelndes Genom aendert seine Zahl bestandener Gates."""
        return self.genug and not self.wechsler

    @property
    def spitze_wechselt(self) -> bool:
        """Steht vorn ein anderes Genom als vorher?

        Die eigentlich entscheidende Frage. Eine hohe Uebereinstimmung im
        Mittelfeld nuetzt nichts, wenn oben ein anderer steht - die Liste ist
        dafuer da, den besten zu finden.
        """
        if not self.handelnde:
            return False
        vorn_grob = max(self.handelnde, key=lambda d: (d.grob_bestanden, d.trades))
        vorn_fein = max(self.handelnde, key=lambda d: (d.fein_bestanden, d.trades))
        return vorn_grob.name != vorn_fein.name

    @property
    def median_luecke(self) -> float:
        werte = sorted(d.luecke for d in self.handelnde)
        if not werte:
            return 0.0
        mitte = len(werte) // 2
        if len(werte) % 2:
            return werte[mitte]
        return (werte[mitte - 1] + werte[mitte]) / 2

    @property
    def spanne(self) -> tuple[float, float]:
        werte = [d.luecke for d in self.handelnde]
        return (min(werte), max(werte)) if werte else (0.0, 0.0)

    def erklaerung(self, name: str, werte, *, hypothesen: int = 1) -> Zusammenhang:
        """Wie gut eine Groesse die Streuung der Luecken erklaert.

        ``hypothesen`` ist die Zahl der insgesamt geprueften Erklaerungen -
        **nicht** die Nummer dieser einen. Wer drei prueft und bei jeder 1
        eintraegt, bekommt drei Schranken von 2,0 und faellt genau auf die
        Mehrfachtest-Falle herein, gegen die dieses Projekt gebaut ist.
        """
        paare = list(zip(self.handelnde, werte, strict=True))
        n = len(paare)
        if n < 3:
            return Zusammenhang(name=name, r=0.0, n=n, hypothesen=hypothesen)
        xs = [float(w) for _, w in paare]
        ys = [d.luecke for d, _ in paare]
        mx, my = sum(xs) / n, sum(ys) / n
        oben = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
        unten = (
            sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)
        ) ** 0.5
        r = oben / unten if unten > 0 else 0.0
        return Zusammenhang(name=name, r=r, n=n, hypothesen=hypothesen)

    def tabelle(self) -> str:
        if not self.handelnde:
            return "Kein handelndes Genom."
        zeilen = [
            f"{'Genom':<38}{'Trades':>7}{'grob':>8}{'fein':>8}"
            f"{'Luecke':>8}  Gates",
            "-" * 78,
        ]
        for d in sorted(self.handelnde, key=lambda x: -x.luecke):
            zeilen.append(
                f"{d.name[:37]:<38}{d.trades:>7}{d.grob_rueckgang:>8.2f}"
                f"{d.fein_rueckgang:>8.2f}{d.luecke:>+8.2f}  "
                f"{d.grob_bestanden}->{d.fein_bestanden}"
                + ("  WECHSEL" if d.urteil_wechselt else "")
            )
        stumm = len(self.doppel) - len(self.handelnde)
        if stumm:
            zeilen.append(
                f"({stumm} Genome ohne Trades nicht aufgefuehrt - ein Rang "
                f"unter ihnen bedeutet nichts.)"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.genug:
            return (
                "Weniger als drei handelnde Genome - daraus laesst sich ueber "
                "die Rangfolge nichts sagen."
            )

        tief, hoch = self.spanne
        umgebung = (
            f"Die Luecken reichen von {tief:+.2f} bis {hoch:+.2f} Punkten, "
            f"der Median liegt bei {self.median_luecke:+.2f}."
        )

        if self.rangfolge_haelt:
            return (
                f"**Die Rangfolge haelt.** Von {len(self.handelnde)} handelnden "
                f"Genomen aendert keines seine Zahl bestandener Gates, wenn "
                f"die Mengenrundung entfernt wird. Die Suche hat also nicht "
                f"nach einem verfaelschten Signal gesteuert.\n\n"
                f"{umgebung} Die Koernung verschiebt die Zahlen also durchaus - "
                f"sie dreht nur kein Urteil, solange die Zahl nicht ohnehin "
                f"dicht an ihrer Schwelle liegt."
            )

        namen = ", ".join(d.name for d in self.wechsler[:4])
        return (
            f"**{len(self.wechsler)} von {len(self.handelnde)} handelnden "
            f"Genomen aendern ihr Urteil, wenn die Mengenrundung entfernt "
            f"wird:** {namen}."
            + ("\n\n**Und vorn steht ein anderes Genom als vorher.**"
               if self.spitze_wechselt else "")
            + f"\n\n{umgebung}"
        )


__all__ = [
    "GRUNDSCHRANKE",
    "Doppel",
    "Rangprobe",
    "Zusammenhang",
    "schranke",
]
