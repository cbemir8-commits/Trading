"""Das Stueck von P7, das sich ohne Lookahead ueberhaupt bauen laesst.

Warum es kein Nachrichten-Overlay gibt
--------------------------------------
``data/termine.py`` deckt die planbare Haelfte ab: FOMC-Entscheidungen und
Halbierungen stehen vorher fest, also darf ein Backtest sie vorher kennen. Die
andere Haelfte - "Nachrichten" - hat eine Eigenschaft, die sie von Terminen
grundsaetzlich trennt: **Man weiss sie erst, wenn sie da sind.**

Ein Overlay, das eine Schlagzeile vom 12. Maerz 2020 kennt und deshalb am
11. Maerz nicht einsteigt, misst nicht Vorsicht, sondern Hellsicht. Es wuerde
den Backtest verbessern und im Betrieb nichts leisten - die teuerste Sorte
Fehler, weil sie wie ein Erfolg aussieht.

Deshalb wird hier **nicht** gebaut, was P7 dem Namen nach verspricht. Gebaut
wird, was davon kausal zulaessig ist: die Reaktion auf den **Abdruck** eines
Schocks, der bereits in den abgeschlossenen Kerzen steht.

Was ein Schock hier ist
-----------------------
Eine Kerze, deren wahre Spanne die juengste Norm um ein Vielfaches
uebersteigt. Verglichen wird gegen den **Median** der vorangegangenen Kerzen,
nicht gegen den Mittelwert: Der Mittelwert wird von grossen Ausschlaegen
selbst hochgezogen, und ein Mass, das der Schock mitverschiebt, erkennt den
naechsten schlechter.

Die Sperre wirkt danach, nicht davor
------------------------------------
Das ist der sichtbare Unterschied zum Termin-Overlay. Dort gibt es einen
Vorlauf, weil der Termin bekannt ist. Hier gibt es nur einen **Nachlauf**:
Nach einem Schock reissen die Spannen, Stops werden schlechter ausgefuehrt,
und Ausbrueche sind haeufiger Fehlsignale. Wer in diesen Kerzen neu einsteigt,
zahlt Aufschlag.

Gehalten wird trotzdem weiter - genau wie beim Termin-Overlay hindert es am
*Einstieg*, nicht am Halten. Eine laufende Position wegen eines Schocks zu
schliessen waere eine andere Strategie und muesste als solche gemessen werden.

Was das voraussichtlich bringt
------------------------------
Wenig. Befund 12 hat das Termin-Overlay gemessen: 2 von 156 Signalen
blockiert, kein Gate bewegt. Ein Schock-Overlay trifft mehr Kerzen, aber
dieselbe Logik gilt - bei sechs Wochen Haltedauer sind einzelne gesperrte
Einstiegstage kaum zu spueren. Deshalb wird hier **zuerst ausgezaehlt** und
erst danach entschieden, ob ein voller Gate-Lauf den Versuch wert ist.

Was gemessen wurde - und was die Kontrolle davon uebrig liess
-------------------------------------------------------------
Der Gate-Lauf ergab neun von elf statt sieben (Befund 58). Das war der beste
Stand, den dieses Projekt je hatte, und er hat **einen Tag gehalten**.

Die Kontrolle in ``research/sperrprobe.py`` zieht zweihundert Mal genauso
viele Einstiegssignale zufaellig und sperrt die: **66,5 % dieser Ziehungen
halten genauso viele Gates.** Der Gewinn kam also nicht daher, dass die
*richtigen* Einstiege gesperrt wurden, sondern daher, dass ueberhaupt welche
gesperrt wurden. Dieselbe Zahl beliebiger Einstiege weniger haette es auch
getan (Befund 59).

**Damit ist dieses Overlay als Verbesserung nicht belegt.** Der Code bleibt -
er ist richtig, getestet und geht denselben Weg wie der Terminkalender -, aber
wer ihn einschaltet, tut das ohne Nachweis, dass die Auswahl der gesperrten
Kerzen etwas leistet.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

#: Wie viele vorangegangene Kerzen die Norm bilden.
FENSTER = 30

#: Ab welchem Vielfachen der Norm eine Kerze als Schock gilt.
#:
#: **Vorab festgelegt und nicht aus den Daten gewaehlt.** Drei wahre Spannen
#: sind an Tageskerzen ein Ereignis, das man im Chart sieht - und das ist die
#: Groessenordnung, um die es geht. Eine Schwelle, die man hinterher so legt,
#: dass die Trefferzahl gut aussieht, misst nichts.
FAKTOR = 3.0

#: Wie viele Kerzen nach einem Schock nicht neu eingestiegen wird.
NACHLAUF = 2


def wahre_spanne(frame: pd.DataFrame) -> np.ndarray:
    """Die wahre Spanne je Kerze - Luecken zum Vortag eingeschlossen.

    Ohne den Vortagsschluss waere eine Kerze, die zehn Prozent tiefer
    **eroeffnet** und sich dann kaum bewegt, eine ruhige Kerze. Sie ist das
    Gegenteil.
    """
    hoch = frame["high"].to_numpy(dtype=float)
    tief = frame["low"].to_numpy(dtype=float)
    schluss = frame["close"].to_numpy(dtype=float)
    vortag = np.concatenate(([schluss[0]], schluss[:-1]))
    return np.maximum.reduce(
        [hoch - tief, np.abs(hoch - vortag), np.abs(tief - vortag)]
    )


def schocks(
    frame: pd.DataFrame, *, fenster: int = FENSTER, faktor: float = FAKTOR
) -> np.ndarray:
    """Welche Kerzen einen Schock zeigen. Kausal - ohne die Kerze selbst.

    **Der Punkt, an dem so etwas ueblicherweise falsch wird.** Nimmt man den
    Median einschliesslich der aktuellen Kerze, kennt die Norm den Schock
    bereits; nimmt man ein zentriertes Fenster, kennt sie die Zukunft. Beides
    laeuft durch und liefert bessere Zahlen, als der Betrieb je erreicht.

    Die Norm bildet sich deshalb aus den ``fenster`` Kerzen **davor**, und die
    ersten ``fenster`` Kerzen zaehlen nie als Schock: Wo keine Norm ist, ist
    auch kein Vielfaches davon.
    """
    spanne = wahre_spanne(frame)
    treffer = np.zeros(len(spanne), dtype=bool)
    if len(spanne) <= fenster or fenster < 1:
        return treffer

    # Rollender Median ueber die *vorangegangenen* Kerzen. ``shift`` waere
    # ueber pandas kuerzer, aber die Verschiebung ist genau die Stelle, an der
    # ein Lookahead entstuende - sie steht deshalb ausgeschrieben da.
    reihe = pd.Series(spanne)
    norm = reihe.rolling(fenster).median().shift(1).to_numpy()

    gueltig = ~np.isnan(norm) & (norm > 0)
    treffer[gueltig] = spanne[gueltig] > faktor * norm[gueltig]
    return treffer


def gesperrt(
    frame: pd.DataFrame,
    *,
    fenster: int = FENSTER,
    faktor: float = FAKTOR,
    nachlauf: int = NACHLAUF,
) -> np.ndarray:
    """Welche Kerzen fuer einen **Einstieg** gesperrt sind.

    Die Schockkerze selbst und die ``nachlauf`` Kerzen danach. Kein Vorlauf -
    vorher war der Schock nicht bekannt, und so zu tun, als waere er es
    gewesen, ist genau der Fehler, um den es in diesem Modul geht.
    """
    treffer = schocks(frame, fenster=fenster, faktor=faktor)
    sperre = treffer.copy()
    for versatz in range(1, max(nachlauf, 0) + 1):
        sperre[versatz:] |= treffer[:-versatz] if versatz else treffer
    return sperre


@dataclass(frozen=True, slots=True)
class Auszaehlung:
    """Wie viele Einstiege ein Schock-Overlay betraefe - und ob sich das lohnt."""

    kerzen: int
    schocks: int
    gesperrte_kerzen: int
    signale: int
    betroffene_signale: int

    #: Ab welchem Anteil betroffener Signale ein voller Gate-Lauf lohnt.
    #:
    #: **Vor der Auszaehlung festgelegt.** Befund 12 hat das Termin-Overlay
    #: mit 2 von 156 Signalen gemessen und kein Gate bewegt; unter einem
    #: Zwanzigstel ist mit einer Wirkung nicht zu rechnen, und ein Versuch
    #: kostet die Huerde fuer alle kuenftigen Kandidaten.
    SCHWELLE: float = 0.05

    @property
    def anteil(self) -> float:
        return self.betroffene_signale / self.signale if self.signale else 0.0

    @property
    def lohnt_messung(self) -> bool:
        return self.anteil >= self.SCHWELLE

    def bericht(self) -> str:
        zeilen = [
            f"  Kerzen           {self.kerzen}",
            f"  Schockkerzen     {self.schocks} "
            f"({self.schocks / self.kerzen:.2%} der Reihe)"
            if self.kerzen
            else "  Schockkerzen     0",
            f"  gesperrte Kerzen {self.gesperrte_kerzen}",
            f"  Einstiegssignale {self.signale}",
            f"  davon gesperrt   {self.betroffene_signale} ({self.anteil:.1%})",
        ]
        if self.lohnt_messung:
            zeilen.append(
                f"\n{self.anteil:.1%} der Einstiege sind betroffen - ueber der "
                f"vorab gesetzten Schwelle von {self.SCHWELLE:.0%}. Ein voller "
                f"Gate-Lauf ist den Versuch wert."
            )
        else:
            zeilen.append(
                f"\n{self.anteil:.1%} der Einstiege sind betroffen - unter der "
                f"vorab gesetzten Schwelle von {self.SCHWELLE:.0%}. Ein voller "
                f"Gate-Lauf wuerde einen Versuch kosten und mit hoher "
                f"Wahrscheinlichkeit nichts bewegen; er unterbleibt. Das ist "
                f"dasselbe Ergebnis wie beim Termin-Overlay (Befund 12)."
            )
        return "\n".join(zeilen)


@dataclass(frozen=True, slots=True)
class Schocksperre:
    """Gesperrte Einstiegszeitpunkte, vorab aus den Kerzen berechnet.

    **Warum sie dieselbe Stelle benutzt wie der Terminkalender.** In
    ``RiskOfficer.blockade`` steht dazu der teuerste Satz dieses Projekts:
    *"Jede Regel, die es zweimal gibt, laeuft irgendwann auseinander."* Eine
    Schocksperre, die nur im Backtest greift oder nur im Betrieb, waere genau
    so eine Regel - und die unangenehmste Sorte, weil sie an wenigen Tagen im
    Jahr wirkt und deshalb lange unauffaellig bliebe.

    Die Zeitpunkte kommen aus abgeschlossenen Kerzen; im Backtest werden sie
    einmal vorab gerechnet, im Betrieb aus dem laufenden Puffer. Verschiedene
    Erzeugung, **eine** Pruefstelle.
    """

    zeitpunkte: frozenset

    @classmethod
    def aus_kerzen(
        cls,
        frame: pd.DataFrame,
        *,
        fenster: int = FENSTER,
        faktor: float = FAKTOR,
        nachlauf: int = NACHLAUF,
    ) -> Schocksperre:
        sperre = gesperrt(frame, fenster=fenster, faktor=faktor, nachlauf=nachlauf)
        zeiten = frame["open_time"].to_numpy()
        return cls(zeitpunkte=frozenset(pd.Timestamp(t) for t in zeiten[sperre]))

    def gilt(self, jetzt) -> bool:
        """Ist der Einstieg zu dieser Kerze gesperrt?

        Verglichen wird ueber die **Eroeffnungszeit** der Kerze, nicht ueber
        einen Zeitraum. Ein Zeitraum waere ungenauer und liefe Gefahr, bei
        einer anderen Kerzenlaenge zu viel oder zu wenig zu sperren.
        """
        marke = pd.Timestamp(jetzt)
        if marke.tzinfo is None and any(
            t.tzinfo is not None for t in self.zeitpunkte
        ):
            marke = marke.tz_localize("UTC")
        elif marke.tzinfo is not None and all(
            t.tzinfo is None for t in self.zeitpunkte
        ):
            marke = marke.tz_localize(None)
        return marke in self.zeitpunkte

    def __len__(self) -> int:
        return len(self.zeitpunkte)
