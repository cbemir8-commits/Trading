"""Wie viel Historie fehlt dem Deflated Sharpe - in Tagen statt in Trades.

Seit Befund 327/328 steht im Register, wie die Luecke zu schliessen waere:
*"Geschlossen wird er ueber die Stichprobe (191 wirksame Trades noetig, 115
da) ... das erste ist das, was mehr Historie kauft, und genau darauf wartet der
Auftrag beim Nutzer."* ``cli abstand`` gibt dazu seit jeher zwei Zeilen aus:
*"Mehr Daten kosten keinen Versuch - eine neue Idee schon. Erst die Datenbasis
ausschoepfen, dann suchen."*

**Wie viel Historie das ist, stand nirgends.** Der Satz liest sich wie eine
Aufgabe, die man erledigen kann. Gerechnet ist es eine Aussage darueber, ob das
ueberhaupt geht.

Die Rechnung
------------
Drei gemessene Groessen, keine geschaetzte:

1. Das Verhaeltnis roher zu wirksamen Trades - beim Bestand 115 von 156, also
   73,7 %. Es entsteht aus der Korrelation innerhalb der Fenster und ist in
   ``stichprobe_wie_im_gate`` gemessen, nicht gesetzt.
2. Die noetige **wirksame** Zahl aus ``erreichbarkeit.noetige_trades`` - bei
   heutiger Guete und heutigem Zaehlerstand 191.
3. Die Trade-Rate auf der vorhandenen Reihe: 156 gewertete Trades auf 3300
   Tagen, also 17,3 im Jahr.

Daraus: 191 wirksame brauchen rund 259 rohe, es fehlen 103, und die kosten bei
dieser Rate **2181 Tage - sechs Jahre**.

Was die Zahl nicht sagt
-----------------------
Sie unterstellt, dass Guete, Verhaeltnis und Rate so bleiben. Das ist die
freundliche Annahme: Befund 75 hat gemessen, dass Trade-Zahl und Guete
**gegeneinander** laufen, allerdings ueber Regeln hinweg und nicht innerhalb
einer. Und sie unterstellt einen stehenden Versuchszaehler - jeder weitere
Versuch hebt die Latte und damit die noetige Zahl (Befund 327).

**Und die Richtung zaehlt.** Rueckwaerts geht nur, soweit **beide** Beine
Kerzen haben: Der gemeinsame Anfang liegt bei 2017-08-16 und ist von ETH
gesetzt; die 2054 zusaetzlichen Tage von BTC kann der Korb nicht nutzen, und
BTC allein steht schlechter (Befund 318). Bleibt die Zeit nach vorn.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

__all__ = ["Datenbedarf", "bedarf"]


@dataclass(frozen=True, slots=True)
class Datenbedarf:
    """Was an Historie fehlt, damit die Stichprobe reicht."""

    roh: int
    """Gewertete Trades - ohne die am Datenende glattgestellten (Befund 152)."""

    effektiv: int
    """Die wirksame Stichprobe, die das Gate der Formel uebergibt."""

    noetig_effektiv: int | None
    """Aus ``erreichbarkeit.noetige_trades``; ``None`` heisst "kein n genuegt"."""

    spanne_tage: int
    """Die gemeinsame Reihe, auf der die Trades entstanden sind."""

    anfang: date | None = None
    """Der Anfang der gemeinsamen Reihe."""

    frueheste: date | None = None
    """Der frueheste Anfang **eines** Beins - meist deutlich davor."""

    gesetzt_von: str = ""
    """Welches Bein den gemeinsamen Anfang setzt, also die Grenze ist."""

    def __post_init__(self) -> None:
        if self.roh < 0 or self.effektiv < 0:
            raise ValueError("Trade-Zahlen sind nicht negativ.")
        if self.effektiv > self.roh:
            raise ValueError(
                f"Die wirksame Stichprobe ({self.effektiv}) kann nicht ueber "
                f"der rohen ({self.roh}) liegen - dann waeren Trades "
                f"unabhaengiger als einzeln."
            )
        if self.spanne_tage < 0:
            raise ValueError("Eine Spanne ist nicht negativ.")

    @property
    def verhaeltnis(self) -> float | None:
        """Wie viel von einem rohen Trade als Beobachtung ankommt."""
        return self.effektiv / self.roh if self.roh else None

    @property
    def reicht(self) -> bool:
        return self.noetig_effektiv is not None and self.effektiv >= self.noetig_effektiv

    @property
    def noetig_roh(self) -> int | None:
        """Rohe Trades fuer die noetige wirksame Zahl - bei gleichem Verhaeltnis.

        Die Umrechnung ist der Kern und gleichzeitig die Annahme: Sie gilt,
        solange die Korrelation innerhalb der Fenster so bleibt.
        """
        anteil = self.verhaeltnis
        if self.noetig_effektiv is None or not anteil:
            return None
        from math import ceil

        return ceil(self.noetig_effektiv / anteil)

    @property
    def fehlende_roh(self) -> int | None:
        noetig = self.noetig_roh
        return None if noetig is None else max(0, noetig - self.roh)

    @property
    def rate_je_tag(self) -> float | None:
        return self.roh / self.spanne_tage if self.spanne_tage else None

    @property
    def rate_je_jahr(self) -> float | None:
        rate = self.rate_je_tag
        return None if rate is None else rate * 365.0

    @property
    def noetige_tage(self) -> int | None:
        """Zusaetzliche Kalendertage bei heutiger Rate."""
        fehlen, rate = self.fehlende_roh, self.rate_je_tag
        if fehlen is None or not rate:
            return None
        from math import ceil

        return ceil(fehlen / rate)

    @property
    def noetige_jahre(self) -> float | None:
        tage = self.noetige_tage
        return None if tage is None else tage / 365.0

    @property
    def rueckwaerts_tage(self) -> int:
        """Tage des laengeren Beins, die der Korb nicht nutzt.

        Nicht "Reserve": Sie liegen vor dem gemeinsamen Anfang, und ein
        Portfolio-Backtest braucht eine gemeinsame Reihe. Dass ein Bein
        allein schlechter steht, ist gemessen (Befund 318).
        """
        if self.anfang is None or self.frueheste is None:
            return 0
        return max(0, (self.anfang - self.frueheste).days)

    def bericht(self) -> str:
        if self.reicht:
            return (
                f"Die Stichprobe reicht: {self.effektiv} wirksame von "
                f"{self.roh} rohen Trades, noetig waren {self.noetig_effektiv}."
            )
        if self.noetig_effektiv is None:
            return (
                "Keine Trade-Zahl genuegt - der Vorteil je Trade ist zu klein. "
                "Mehr Historie hilft hier nicht, und das ist keine Frage der "
                "Menge."
            )

        zeilen = [
            f"**Was an Historie fehlt.** {self.effektiv} wirksame Trades von "
            f"{self.roh} rohen ({self.verhaeltnis:.1%}); noetig sind "
            f"{self.noetig_effektiv} wirksame, also rund {self.noetig_roh} rohe. "
            f"Es fehlen {self.fehlende_roh}."
        ]
        if self.noetige_tage is not None:
            zeilen.append(
                f"Bei der gemessenen Rate von {self.rate_je_jahr:.1f} Trades im "
                f"Jahr ({self.roh} auf {self.spanne_tage} Tagen) kostet das "
                f"**{self.noetige_tage} Tage, {self.noetige_jahre:.1f} Jahre** "
                f"zusaetzliche Historie - bei unveraenderter Guete und "
                f"stehendem Versuchszaehler. Jeder weitere Versuch hebt die "
                f"noetige Zahl (Befund 327)."
            )
        if self.rueckwaerts_tage:
            zeilen.append(
                f"**Rueckwaerts ist sie nicht zu holen.** Der gemeinsame "
                f"Anfang liegt bei {self.anfang}"
                + (f", gesetzt von {self.gesetzt_von}" if self.gesetzt_von else "")
                + f"; das andere Bein reicht {self.rueckwaerts_tage} Tage "
                f"weiter zurueck, und die kann ein Portfolio-Backtest nicht "
                f"nutzen. Ein Bein allein steht schlechter (Befund 318). "
                f"Bleibt die Zeit nach vorn."
            )
        return "\n\n".join(zeilen)


def bedarf(
    *,
    roh: int,
    effektiv: int,
    noetig_effektiv: int | None,
    spanne_tage: int,
    anfaenge: dict[str, date] | None = None,
) -> Datenbedarf:
    """Den Bedarf aus den gemessenen Groessen zusammensetzen.

    ``anfaenge`` sind die ersten Kerzen je Bein - aus ihnen folgt, welches Bein
    den gemeinsamen Anfang setzt und wie viel vom anderen ungenutzt bleibt.
    """
    anfang = frueheste = None
    gesetzt_von = ""
    if anfaenge:
        anfang = max(anfaenge.values())
        frueheste = min(anfaenge.values())
        gesetzt_von = max(anfaenge, key=lambda name: anfaenge[name])
    return Datenbedarf(
        roh=roh,
        effektiv=effektiv,
        noetig_effektiv=noetig_effektiv,
        spanne_tage=spanne_tage,
        anfang=anfang,
        frueheste=frueheste,
        gesetzt_von=gesetzt_von,
    )
