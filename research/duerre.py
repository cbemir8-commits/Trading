"""Das schlechteste Jahr - ein Ausreisser oder eine Marktphase?

Die Frage
---------
``gate_worst_year`` meldet beim Bestand **-10,32 %** gegen eine Grenze von
-10,00 %. Eine einzelne Zahl, 0,32 Punkte daneben, und in fuenfzehn Laeufen
nie angesehen.

Sie ist das **Minimum ueber alle rollierenden Zwoelfmonatsfenster**, und
davon gibt es auf 93 Testmonaten 2465 Stueck. Ein Minimum ueber so viele
Ziehungen ist per Konstruktion extrem - dieselbe Lage wie beim
Parameter-Plateau in Befund 92 und beim besten Paar in Befund 86.

Der Fehlschluss, der dabei naheliegt
------------------------------------
Nur **2 von 2465** Fenstern liegen unter -10 %, das 1. Perzentil steht bei
-6,54 %, der Median bei +11,51 %. Das liest sich wie ein Ausreisser, den man
nicht ueberbewerten sollte.

**Das ist falsch, und zwar aus demselben Grund wie in Befund 88.** Die 2465
Fenster sind keine 2465 Beobachtungen: Sie ueberlappen sich zu 99,7 %. Bei 93
Testmonaten gibt es **7,7 unabhaengige Jahresperioden**. Der Fehlschlag
betrifft also eine von acht, nicht eine von 2465.

Dass es ein Ereignis ist und keine Streuung, zeigt die Lage: Alle Fenster
unter -5 % starten zwischen dem 14.10.2021 und dem 08.01.2022, also in einem
zusammenhaengenden Block von knapp drei Monaten.

Was tatsaechlich dort steht
---------------------------
Das schlechteste Fenster laeuft vom **08.11.2021 bis 08.11.2022** - vom
Allzeithoch bis nach dem FTX-Zusammenbruch. Im selben Fenster:

    Bestand      -10,3 %
    BTC halten   -72,5 %
    ETH halten   -72,3 %

Die Strategie hat den Einbruch also um den Faktor sieben gedaempft. Das ist
nicht das Bild einer riskanten Strategie, sondern genau das, wofuer sie
gebaut ist.

Und trotzdem scheitert das Gate zu Recht
----------------------------------------
Es fragt nicht, ob die Strategie besser war als der Markt - das prueft die
Messlatte, und dort ist sie um das 3,8-fache besser. Es fragt: **Wer zum
denkbar unguenstigsten Zeitpunkt eingestiegen waere, wie stuende der nach
zwoelf Monaten da?** Die Antwort lautet -10,3 %, und die Grenze liegt bei
-10,0 %.

Diese Grenze steht bewusst innerhalb des Kill-Switch von 15 %. Wer nach einem
Jahr zweistellig im Minus steht, hoert auf - unabhaengig davon, wie der Markt
gelaufen ist.

Wo das hinfuehrt
----------------
Der Kreis schliesst sich zu Befund 85: Dort wurde gemessen, dass der Bestand
im Abwaertsmarkt nichts verdient (Sharpe je Trade **-0,0450** gegen +0,3473
im Aufwaertsmarkt). Hier steht dieselbe Eigenschaft in einer anderen Einheit.

Das schlechteste Jahr ist damit kein statistisches Artefakt, sondern die
Kehrseite dessen, was der Kandidat ist: eine Aufwaertsmarkt-Strategie. Der
naechste Zyklus bringt dieselbe Phase wieder, und dann wieder rund -10 %.

Kostet keinen Versuch: Zerlegt wird eine Kapitalkurve, die schon gerechnet
ist. Es wird nichts ausgewaehlt und keine Schwelle angefasst.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Monate je Fenster. Dieselbe Zahl, mit der ``gate_worst_year`` rechnet -
#: sie steht hier, damit die Einordnung nicht versehentlich eine andere
#: Periode betrachtet als das Gate.
FENSTERMONATE = 12


@dataclass(frozen=True, slots=True)
class Duerre:
    """Die schlechteste Periode einer Kapitalkurve, mit ihrer Umgebung."""

    schlechteste_pct: float
    grenze_pct: float
    fenster: int
    """Zahl der rollierenden Fenster - **nicht** die Zahl der Beobachtungen."""
    testmonate: float
    beginn: str = ""
    ende: str = ""
    zone_von: str = ""
    zone_bis: str = ""
    markt: dict[str, float] = field(default_factory=dict)
    """Was Halten im selben Fenster gebracht haette, je Markt."""
    unter_grenze: int = 0
    perzentil_1: float = 0.0
    median: float = 0.0

    @property
    def besteht(self) -> bool:
        return self.schlechteste_pct >= self.grenze_pct

    @property
    def fehlt(self) -> float:
        return self.grenze_pct - self.schlechteste_pct

    @property
    def unabhaengige_perioden(self) -> float:
        """Wie viele Jahresperioden wirklich darin stecken.

        Die entscheidende Zahl. 2465 rollierende Fenster ueberlappen sich zu
        99,7 % - sie als Stichprobe zu lesen ist derselbe Fehler wie die
        siebenfach gezaehlte Regel in Befund 88.
        """
        return self.testmonate / FENSTERMONATE

    @property
    def anteil_unter_grenze(self) -> float:
        """Der Anteil, der wie ein Ausreisser aussieht - und keiner ist."""
        return self.unter_grenze / self.fenster if self.fenster else 0.0

    @property
    def daempfung(self) -> float | None:
        """Um welchen Faktor die Strategie den Markteinbruch gedaempft hat.

        ``None``, wenn der Markt im selben Fenster nicht verloren hat - dann
        gibt es nichts zu daempfen, und die Zahl waere eine Ausrede.
        """
        if not self.markt or self.schlechteste_pct >= 0:
            return None
        schlimmster = min(self.markt.values())
        if schlimmster >= 0:
            return None
        return schlimmster / self.schlechteste_pct

    def tabelle(self) -> str:
        zeilen = [
            f"{'schlechtestes Jahr':<26} {self.schlechteste_pct:>+9.2f} %",
            f"{'Grenze':<26} {self.grenze_pct:>+9.2f} %",
            f"{'1. Perzentil':<26} {self.perzentil_1:>+9.2f} %",
            f"{'Median':<26} {self.median:>+9.2f} %",
            "-" * 40,
            f"{'rollierende Fenster':<26} {self.fenster:>9}",
            f"{'unabhaengige Perioden':<26} {self.unabhaengige_perioden:>9.1f}",
        ]
        for name, wert in sorted(self.markt.items()):
            zeilen.append(f"{'Halten ' + name[:18]:<26} {wert:>+9.1f} %")
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if self.besteht:
            return (
                f"Das schlechteste Jahr liegt bei {self.schlechteste_pct:+.2f} % "
                f"und damit innerhalb der Grenze von {self.grenze_pct:+.2f} %."
            )

        teile = [
            f"**Das schlechteste Jahr liegt bei {self.schlechteste_pct:+.2f} %, "
            f"{self.fehlt:.2f} Punkte ueber der Grenze.**"
        ]
        if self.beginn and self.ende:
            teile[-1] += f" Es laeuft vom {self.beginn} bis {self.ende}."

        # Zuerst der Fehlschluss, dann seine Widerlegung - in dieser
        # Reihenfolge, weil die erste Lesart die naheliegende ist.
        teile.append(
            f"Nur {self.unter_grenze} von {self.fenster} rollierenden Fenstern "
            f"liegen darunter ({self.anteil_unter_grenze:.1%}), das 1. Perzentil "
            f"steht bei {self.perzentil_1:+.2f} % und der Median bei "
            f"{self.median:+.2f} %. Das sieht nach einem Ausreisser aus - "
            f"**ist aber keiner.** Die Fenster ueberlappen sich fast "
            f"vollstaendig; in {self.testmonate:.0f} Testmonaten stecken "
            f"{self.unabhaengige_perioden:.1f} unabhaengige Jahresperioden. "
            f"Betroffen ist eine davon."
        )
        if self.zone_von and self.zone_bis:
            teile.append(
                f"Dass es ein Ereignis ist und keine Streuung, zeigt die Lage: "
                f"Die schlechten Fenster starten alle zwischen dem "
                f"{self.zone_von} und dem {self.zone_bis}."
            )

        faktor = self.daempfung
        if faktor is not None:
            markt = ", ".join(
                f"{name} {wert:+.1f} %" for name, wert in sorted(self.markt.items())
            )
            teile.append(
                f"Im selben Fenster hat Halten {markt} gebracht - die Strategie "
                f"hat den Einbruch also um den Faktor {faktor:.1f} gedaempft. "
                f"**Das entlastet sie nicht.** Ob sie besser war als der Markt, "
                f"fragt die Messlatte; dieses Gate fragt, ob jemand das Jahr "
                f"durchgehalten haette."
            )
        return "\n\n".join(teile)


def baue(
    kurve,
    *,
    testmonate: float,
    grenze_pct: float,
    zeiten=None,
    markt: dict[str, float] | None = None,
) -> Duerre | None:
    """Die schlechteste Periode aus einer Kapitalkurve einordnen.

    ``zeiten`` sind die Zeitstempel je Kurvenpunkt; fehlen sie, bleibt die
    Einordnung ohne Datumsangaben - die Zahlen stimmen trotzdem.
    """
    werte = np.asarray(kurve, dtype=float)
    if len(werte) < 3 or testmonate <= FENSTERMONATE:
        return None
    spanne = int(len(werte) * FENSTERMONATE / testmonate)
    if spanne < 2 or spanne >= len(werte):
        return None

    renditen = (werte[spanne:] / werte[:-spanne] - 1.0) * 100.0
    tiefster = int(np.argmin(renditen))
    schlecht = np.where(renditen < grenze_pct)[0]
    # Die Zone wird ueber die Fenster unter der **halben** Grenze bestimmt,
    # nicht unter der Grenze selbst: Sonst besteht sie oft aus einem einzigen
    # Punkt und sagt nichts darueber, ob es ein Ereignis war.
    zone = np.where(renditen < grenze_pct / 2)[0]

    def zeit(i: int) -> str:
        if zeiten is None or i >= len(zeiten):
            return ""
        return str(zeiten[i])[:10]

    return Duerre(
        schlechteste_pct=float(renditen[tiefster]),
        grenze_pct=grenze_pct,
        fenster=len(renditen),
        testmonate=testmonate,
        beginn=zeit(tiefster),
        ende=zeit(tiefster + spanne),
        zone_von=zeit(int(zone.min())) if len(zone) else "",
        zone_bis=zeit(int(zone.max())) if len(zone) else "",
        markt=dict(markt or {}),
        unter_grenze=len(schlecht),
        perzentil_1=float(np.percentile(renditen, 1)),
        median=float(np.median(renditen)),
    )


__all__ = ["FENSTERMONATE", "Duerre", "baue"]
