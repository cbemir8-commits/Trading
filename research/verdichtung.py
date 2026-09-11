"""Die Haltezeit des Bestands liegt nicht irgendwo - sie liegt im Aufwaerts.

Woher die Frage kommt
---------------------
``research.finanzierung`` haelt seit Befund 100 einen Satz fest, und schreibt
in derselben Zeile dazu, dass er nicht gemessen ist:

    *"Der Bestand ist eine Long-Trendfolge. Er ist im Markt, wenn der Trend
    steigt - also genau dann, wenn Longs am meisten zahlen. [...] **Das ist
    hier nicht gemessen, sondern die Aussage des Engine-Docstrings.**
    Nachpruefen laesst es sich nur mit echten Bybit-Raten."*

Der letzte Satz stimmt fuer die **Rate**. Er stimmt nicht fuer die
**Belastung**. Die Behauptung hat zwei Haelften, und nur eine braucht Bybit:

    1. Liegen die Funding-Stunden des Kandidaten in Aufwaertsphasen?
    2. Sind die Raten in Aufwaertsphasen hoeher?

Haelfte 1 steht in den eigenen Trades und im eigenen Kursspeicher. Sie wird
hier gemessen. Haelfte 2 bleibt offen und braucht echte Raten.

Dringlich wurde das durch Befund 250: Der Spielraum bis zum ersten
Durchfaller ist 6,0 % im Jahr, der Vorgabewert steht bei 10,9 %. Wenn die
Luft so duenn ist, ist die Richtung des Fehlers keine Fussnote mehr.

Was gemessen wird
-----------------
Zwei Zahlen je Markt, beide ohne Modell:

**Verdichtung** - wie schnell der Markt steigt, waehrend der Kandidat drin
ist, geteilt durch seinen Anstieg ueber die ganze Spanne. Beides als
Log-Drift je Stunde, damit sich Zeitraeume unterschiedlicher Laenge
vergleichen lassen. Eine Eins hiesse: Die Haltezeit ist ein beliebiger
Ausschnitt.

**Anteil des Fundings in steigenden Phasen** - jede Haltezeit steigt oder
faellt, und ihr Funding faellt entsprechend. Eine Aufteilung, kein Modell.

Was daraus folgt - und was nicht
--------------------------------
Folgt: Ein **flacher** Satz, der auf den Marktdurchschnitt geeicht ist, setzt
diesen Kandidaten zu niedrig an. Er ist nicht irgendwo im Markt, sondern in
den steilsten Stuecken.

Folgt **nicht**: um wie viel. Dafuer braucht es die zweite Haelfte, also die
Raten selbst. Gemessen ist der Hebel, nicht der Ausschlag.

Und ausdruecklich nicht: dass der Kandidat ueber dem **Vorgabewert** liegt.
Der ist ein Basiswert und kein Durchschnitt; diese Messung vergleicht gegen
den Marktdurchschnitt, nicht gegen ihn.

Kostet keinen Versuch: Gelesen wird das Handelsbuch eines Laufs, der ohnehin
stattfindet. Ausgewaehlt wird nichts.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from math import log

#: Stunden im Jahr - die Drift wird je Stunde gerechnet und je Jahr berichtet.
STUNDEN_JE_JAHR = 24.0 * 365.0


@dataclass(frozen=True, slots=True)
class Haltezeit:
    """Ein Zeitraum, in dem der Kandidat im Markt war und Funding gezahlt hat.

    ``kurs_beginn`` und ``kurs_ende`` sind **Marktkurse** zu den beiden
    Zeitpunkten, nicht die Ein- und Ausstiegskurse des Trades: Gefragt ist,
    was der Markt getan hat, nicht was der Trade daran verdient hat.
    """

    beginn: datetime
    ende: datetime
    kurs_beginn: float
    kurs_ende: float
    funding: float = 0.0

    @property
    def stunden(self) -> float:
        return (self.ende - self.beginn).total_seconds() / 3600.0

    @property
    def drift(self) -> float:
        """Log-Rendite des Marktes ueber die Haltezeit."""
        if self.kurs_beginn <= 0 or self.kurs_ende <= 0:
            return 0.0
        return log(self.kurs_ende / self.kurs_beginn)


def _ueberlappungen(zeiten: Sequence[Haltezeit]) -> int:
    """Wie viele Haltezeiten in eine vorherige hineinragen.

    Die Summen unten zaehlen Stunden und Drift ueber die Haltezeiten. Ragen
    zwei ineinander, zaehlt derselbe Zeitraum doppelt und die Verdichtung
    waere zu gross. Deshalb wird nicht angenommen, dass es keine gibt,
    sondern nachgesehen.
    """
    geordnet = sorted(zeiten, key=lambda z: z.beginn)
    return sum(1 for a, b in pairwise(geordnet) if b.beginn < a.ende)


@dataclass(frozen=True, slots=True)
class Marktverdichtung:
    """Wie stark die Haltezeit eines Marktes im Aufwaerts liegt."""

    symbol: str
    stunden_gesamt: float
    stunden_im_markt: float
    drift_gesamt: float
    drift_im_markt: float
    funding_auf: float = 0.0
    funding_ab: float = 0.0
    funding_flach: float = 0.0
    ueberlappende: int = 0
    zeiten: int = 0

    @property
    def anteil_zeit(self) -> float:
        if not self.stunden_gesamt:
            return 0.0
        return self.stunden_im_markt / self.stunden_gesamt

    @property
    def anteil_drift(self) -> float:
        """Wie viel vom Anstieg der ganzen Spanne in der Haltezeit liegt.

        Kann ueber 1 gehen: Wer die Rueckgaenge aussitzt, faengt mehr
        Anstieg ein, als am Ende netto uebrig ist.
        """
        if not self.drift_gesamt:
            return 0.0
        return self.drift_im_markt / self.drift_gesamt

    @property
    def drift_je_jahr_gesamt(self) -> float:
        if not self.stunden_gesamt:
            return 0.0
        return self.drift_gesamt / self.stunden_gesamt * STUNDEN_JE_JAHR

    @property
    def drift_je_jahr_im_markt(self) -> float:
        if not self.stunden_im_markt:
            return 0.0
        return self.drift_im_markt / self.stunden_im_markt * STUNDEN_JE_JAHR

    @property
    def verdichtung(self) -> float:
        """Drift je Stunde im Markt, geteilt durch die der ganzen Spanne."""
        if not self.drift_je_jahr_gesamt:
            return 0.0
        return self.drift_je_jahr_im_markt / self.drift_je_jahr_gesamt

    @property
    def funding_gesamt(self) -> float:
        return self.funding_auf + self.funding_ab + self.funding_flach

    @property
    def anteil_funding_auf(self) -> float:
        if not self.funding_gesamt:
            return 0.0
        return self.funding_auf / self.funding_gesamt

    @property
    def belastbar(self) -> bool:
        """Traegt die Verdichtung dieses Marktes ueberhaupt eine Aussage?

        Nein bei Ueberlappung (dann zaehlt Zeit doppelt) und nein, wenn der
        Markt ueber die Spanne gefallen ist - dann ist das Verhaeltnis zweier
        Driften kein Mass fuer "steiler", sondern ein Vorzeichenspiel.
        """
        return self.ueberlappende == 0 and self.drift_gesamt > 0

    def zeile(self) -> str:
        rand = "" if self.belastbar else "  (nicht belastbar)"
        return (
            f"{self.symbol:<18}{self.anteil_zeit:>10.1%}"
            f"{self.anteil_drift:>12.1%}{self.verdichtung:>12.2f}x"
            f"{self.anteil_funding_auf:>13.1%}{rand}"
        )


def messe(
    symbol: str,
    zeiten: Iterable[Haltezeit],
    *,
    stunden_gesamt: float,
    drift_gesamt: float,
) -> Marktverdichtung:
    """Ein Markt, seine Haltezeiten, seine Verdichtung."""
    liste = list(zeiten)
    auf = sum(z.funding for z in liste if z.drift > 0)
    ab = sum(z.funding for z in liste if z.drift < 0)
    flach = sum(z.funding for z in liste if z.drift == 0)
    return Marktverdichtung(
        symbol=symbol,
        stunden_gesamt=stunden_gesamt,
        stunden_im_markt=sum(z.stunden for z in liste),
        drift_gesamt=drift_gesamt,
        drift_im_markt=sum(z.drift for z in liste),
        funding_auf=auf,
        funding_ab=ab,
        funding_flach=flach,
        ueberlappende=_ueberlappungen(liste),
        zeiten=len(liste),
    )


@dataclass(frozen=True, slots=True)
class Verdichtungsbild:
    """Alle vermessenen Maerkte zusammen."""

    maerkte: tuple[Marktverdichtung, ...] = ()

    @property
    def belastbare(self) -> tuple[Marktverdichtung, ...]:
        return tuple(m for m in self.maerkte if m.belastbar)

    @property
    def funding_gesamt(self) -> float:
        return sum(m.funding_gesamt for m in self.maerkte)

    @property
    def funding_auf(self) -> float:
        return sum(m.funding_auf for m in self.maerkte)

    @property
    def anteil_funding_auf(self) -> float:
        if not self.funding_gesamt:
            return 0.0
        return self.funding_auf / self.funding_gesamt

    @property
    def schwaechste(self) -> Marktverdichtung | None:
        """Der Markt mit der geringsten Verdichtung - die vorsichtige Zahl.

        Berichtet wird bewusst die kleinste und nicht der Durchschnitt: Sie
        ist die, die die Aussage gerade noch traegt.
        """
        if not self.belastbare:
            return None
        return min(self.belastbare, key=lambda m: m.verdichtung)

    @property
    def einig(self) -> bool:
        """Zeigen alle belastbaren Maerkte in dieselbe Richtung?"""
        return bool(self.belastbare) and all(
            m.verdichtung > 1.0 for m in self.belastbare
        )

    def tabelle(self) -> str:
        if not self.maerkte:
            return "Keine Maerkte vermessen."
        zeilen = [
            f"{'Markt':<18}{'im Markt':>10}{'Drift dort':>12}"
            f"{'Verdichtung':>13}{'Funding auf':>13}",
            "-" * 66,
        ]
        zeilen.extend(m.zeile() for m in self.maerkte)
        return "\n".join(zeilen)

    def urteil(self) -> str:
        teile: list[str] = []
        schwaechste = self.schwaechste

        if schwaechste is None:
            teile.append(
                "**Kein Markt traegt hier eine Aussage.** Entweder ragen "
                "Haltezeiten ineinander - dann zaehlt derselbe Zeitraum "
                "doppelt - oder der Markt ist ueber die Spanne gefallen, und "
                "dann misst das Verhaeltnis zweier Driften kein 'steiler'."
            )
            return "\n\n".join(teile)

        teile.append(
            f"**Die Haltezeit liegt im Aufwaerts.** Auf dem schwaechsten "
            f"belastbaren Markt ({schwaechste.symbol}) ist der Kandidat "
            f"{schwaechste.anteil_zeit:.0%} der Zeit im Markt und faengt "
            f"dabei {schwaechste.anteil_drift:.0%} des gesamten Anstiegs "
            f"ein: {schwaechste.drift_je_jahr_im_markt:+.2f} Log-Drift im "
            f"Jahr gegen {schwaechste.drift_je_jahr_gesamt:+.2f} ueber die "
            f"ganze Spanne, also das "
            f"{schwaechste.verdichtung:.1f}-fache."
        )

        if self.einig and len(self.belastbare) > 1:
            teile.append(
                f"Alle {len(self.belastbare)} belastbaren Maerkte zeigen in "
                f"dieselbe Richtung. Berichtet wird oben trotzdem der "
                f"schwaechste - er ist der, der die Aussage gerade noch "
                f"traegt."
            )

        teile.append(
            f"**Und das Funding faellt entsprechend an:** "
            f"{self.anteil_funding_auf:.0%} davon in Haltezeiten, in denen "
            f"der Markt gestiegen ist ({self.funding_auf:.2f} von "
            f"{self.funding_gesamt:.2f} EUR). Das ist eine Aufteilung und "
            f"kein Modell - jede Haltezeit steigt oder faellt, und ihr "
            f"Funding faellt mit ihr."
        )

        teile.append(
            "**Was daraus folgt.** Der Engine-Docstring haelt fest, dass die "
            "Rate in Aufwaertsphasen meist positiv ist und Longs zahlen. Wenn "
            "das stimmt, setzt ein **flacher** Satz, der auf den "
            "Marktdurchschnitt geeicht ist, genau diesen Kandidaten zu "
            "niedrig an - er ist nicht irgendwo im Markt, sondern in den "
            "steilsten Stuecken."
        )

        teile.append(
            "**Was daraus nicht folgt.** Um wie viel - dafuer braucht es die "
            "Raten selbst, und die gibt es nur von Bybit. Gemessen ist der "
            "Hebel, nicht der Ausschlag. Und ausdruecklich nicht gemessen "
            "ist, ob der Kandidat ueber dem **Vorgabewert** liegt: Der ist "
            "ein Basiswert und kein Durchschnitt; verglichen wird hier gegen "
            "den Marktdurchschnitt."
        )

        nicht = [m for m in self.maerkte if not m.belastbar]
        if nicht:
            teile.append(
                f"Nicht belastbar und daher aus dem Urteil heraus: "
                f"{', '.join(m.symbol for m in nicht)}."
            )

        teile.append(
            "Kostet keinen Versuch: gelesen wird das Handelsbuch eines "
            "Laufs, der ohnehin stattfindet. Ausgewaehlt wird nichts."
        )
        return "\n\n".join(teile)


__all__ = [
    "STUNDEN_JE_JAHR",
    "Haltezeit",
    "Marktverdichtung",
    "Verdichtungsbild",
    "messe",
]
