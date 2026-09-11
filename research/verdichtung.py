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

#: Ab wie vielen Haltezeiten eine Verdichtung ueberhaupt etwas sagt.
#:
#: **Eine Konvention, keine Messung.** Darunter haengen die Summen an ein,
#: zwei Zeitraeumen, und ein einziger guter erklaert alles. Weil die Zahl
#: gesetzt und nicht gemessen ist, entscheidet sie nichts allein:
#: ``Familienbild.urteil`` prueft seine Aussage zusaetzlich ohne sie und sagt,
#: ob sie daran haengt.
MINDESTZEITEN = 20


@dataclass(frozen=True, slots=True)
class Haltezeit:
    """Ein Zeitraum, in dem der Kandidat im Markt war und Funding gezahlt hat.

    ``kurs_beginn`` und ``kurs_ende`` sind **Marktkurse** zu den beiden
    Zeitpunkten, nicht die Ein- und Ausstiegskurse des Trades: Gefragt ist,
    was der Markt getan hat, nicht was der Trade daran verdient hat.

    ``long`` sagt, auf welcher Seite die Position stand. Die Rechnung weiter
    unten braucht es nicht - sie zaehlt Drift und Stunden, egal wer sie
    traegt. Aber ihre **Deutung** braucht es: Auf einem Perpetual zahlt die
    Long-Seite bei positiver Rate und die Short-Seite bekommt. Fuer eine
    zweiseitige Regel heisst "der Markt ist gestiegen" also nicht mehr
    "sie hat mehr gezahlt", und die ganze Aussage kippt. Deshalb steht die
    Seite hier, und deshalb macht eine einzige Short-Haltezeit den Markt
    unten ``nicht belastbar`` (Befund 252).
    """

    beginn: datetime
    ende: datetime
    kurs_beginn: float
    kurs_ende: float
    funding: float = 0.0
    long: bool = True

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
    nicht_long: int = 0
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
    def genug(self) -> bool:
        """Genug Haltezeiten, dass die Summen nicht an einer einzigen haengen.

        ``MINDESTZEITEN`` ist eine Konvention und keine Messung. Deshalb
        traegt sie hier keine Entscheidung allein: ``Familienbild`` prueft
        sein Urteil zusaetzlich ohne sie.
        """
        return self.zeiten >= MINDESTZEITEN

    @property
    def grund(self) -> str:
        """Warum dieser Markt nichts traegt - leer, wenn er traegt."""
        if self.ueberlappende:
            viele = self.ueberlappende > 1
            return (
                f"{self.ueberlappende} "
                f"{'Haltezeiten ragen' if viele else 'Haltezeit ragt'} "
                f"ineinander"
            )
        if self.nicht_long:
            viele = self.nicht_long > 1
            return (
                f"{self.nicht_long} "
                f"{'Haltezeiten' if viele else 'Haltezeit'} nicht long"
            )
        if self.drift_gesamt <= 0:
            return "Markt ueber die Spanne nicht gestiegen"
        return ""

    @property
    def belastbar(self) -> bool:
        """Traegt die Verdichtung dieses Marktes ueberhaupt eine Aussage?

        Drei Mal nein, und jedes Mal aus einem anderen Grund:

        * **Ueberlappung** - dann zaehlt derselbe Zeitraum doppelt.
        * **Nicht nur long** - dann heisst "gestiegen" nicht mehr "mehr
          gezahlt", denn auf einem Perpetual bekommt die Short-Seite bei
          positiver Rate (Befund 252).
        * **Gefallener Markt** - dann misst das Verhaeltnis zweier Driften
          kein "steiler", sondern ein Vorzeichen.
        """
        return not self.grund

    def zeile(self) -> str:
        rand = "" if self.belastbar else f"  ({self.grund})"
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
        nicht_long=sum(1 for z in liste if not z.long),
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


# ---------------------------------------------------------------------------
# Eigenschaft des Bestands oder der Bauart?
# ---------------------------------------------------------------------------
#
# Befund 251 hat die Verdichtung am Bestand gemessen. Die naechste Frage
# entscheidet, was sie wert ist: Traegt **jede** Regel dieser Bauart sie, oder
# ist der Bestand ein Einzelfall? Im ersten Fall kann die Suche nicht
# herauswaehlen, was sie nicht hat; im zweiten waere sie ein Weg.
#
# Nachgemessen ueber den Tageskerzen-Katalog (Befund 252).


@dataclass(frozen=True, slots=True)
class Regelverdichtung:
    """Eine Regel des Katalogs, auf ihren schwaechsten Markt eingedampft."""

    name: str
    verdichtung: float
    zeiten: int
    belastbar: bool
    grund: str = ""
    ist_bestand: bool = False

    @property
    def genug(self) -> bool:
        return self.zeiten >= MINDESTZEITEN

    @property
    def brauchbar(self) -> bool:
        return self.belastbar and self.genug

    def zeile(self) -> str:
        marke = "  <- Bestand" if self.ist_bestand else ""
        if not self.zeiten:
            # "unter 20 Haltezeiten" waere hier irrefuehrend - die Regel hat
            # auf diesen Daten ueberhaupt nicht gehandelt.
            return f"{self.name:<40}{0:>8}{'-':>13}   (kein einziger Trade)"
        if not self.belastbar:
            return f"{self.name:<40}{self.zeiten:>8}{'-':>13}   ({self.grund})"
        knapp = "" if self.genug else f"  (unter {MINDESTZEITEN} Haltezeiten)"
        return (
            f"{self.name:<40}{self.zeiten:>8}{self.verdichtung:>12.2f}x"
            f"{marke}{knapp}"
        )


def aus_bild(
    name: str, bild: Verdichtungsbild, *, ist_bestand: bool = False
) -> Regelverdichtung:
    """Ein ``Verdichtungsbild`` als eine Zeile der Familientabelle.

    Genommen wird der **schwaechste** belastbare Markt, wie im Urteil eines
    einzelnen Bildes auch: Er traegt die Aussage gerade noch.
    """
    schwaechste = bild.schwaechste
    zeiten = sum(m.zeiten for m in bild.maerkte)
    if schwaechste is None:
        gruende = [m.grund for m in bild.maerkte if m.grund]
        return Regelverdichtung(
            name=name, verdichtung=0.0, zeiten=zeiten, belastbar=False,
            grund=gruende[0] if gruende else "kein Markt vermessen",
            ist_bestand=ist_bestand,
        )
    return Regelverdichtung(
        name=name, verdichtung=schwaechste.verdichtung, zeiten=zeiten,
        belastbar=True, ist_bestand=ist_bestand,
    )


@dataclass(frozen=True, slots=True)
class Familienbild:
    """Der ganze Katalog - und ob der Bestand darin heraussticht."""

    regeln: tuple[Regelverdichtung, ...] = ()

    @property
    def brauchbare(self) -> tuple[Regelverdichtung, ...]:
        return tuple(r for r in self.regeln if r.brauchbar)

    @property
    def bestand(self) -> Regelverdichtung | None:
        return next((r for r in self.regeln if r.ist_bestand), None)

    @property
    def spanne(self) -> tuple[float, float]:
        werte = [r.verdichtung for r in self.brauchbare]
        return (min(werte), max(werte)) if werte else (0.0, 0.0)

    @property
    def verdichtende(self) -> tuple[Regelverdichtung, ...]:
        return tuple(r for r in self.brauchbare if r.verdichtung > 1.0)

    @property
    def ausnahmen(self) -> tuple[Regelverdichtung, ...]:
        return tuple(r for r in self.brauchbare if r.verdichtung <= 1.0)

    @property
    def bestand_liegt_drin(self) -> bool:
        """Steht der Bestand **innerhalb** der Spanne der uebrigen Regeln?

        Die eigentliche Frage: Ist er ein Einzelfall oder einer von vielen?
        """
        bestand = self.bestand
        andere = [r.verdichtung for r in self.brauchbare if not r.ist_bestand]
        if bestand is None or not bestand.brauchbar or not andere:
            return False
        return min(andere) <= bestand.verdichtung <= max(andere)

    @property
    def haengt_an_der_schwelle(self) -> bool:
        """Aendert ``MINDESTZEITEN`` die Aussage?

        Die Schwelle ist gesetzt und nicht gemessen. Wenn die Aussage ohne
        sie eine andere waere, gehoert das dazugesagt - sonst entscheidet
        eine Konvention ueber einen Befund.
        """
        ohne = [r for r in self.regeln if r.belastbar]
        mit = self.brauchbare
        if not ohne or not mit:
            return True
        return (all(r.verdichtung > 1.0 for r in mit)) != (
            all(r.verdichtung > 1.0 for r in ohne)
        )

    def tabelle(self) -> str:
        if not self.regeln:
            return "Keine Regeln vermessen."
        zeilen = [
            f"{'Regel':<40}{'Zeiten':>8}{'Verdichtung':>13}",
            "-" * 70,
        ]
        zeilen.extend(
            r.zeile()
            for r in sorted(
                self.regeln,
                key=lambda r: (not r.brauchbar, -r.verdichtung),
            )
        )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        teile: list[str] = []
        brauchbar = self.brauchbare
        bestand = self.bestand

        if len(brauchbar) < 2:
            return (
                f"**Zu wenige brauchbare Regeln** ({len(brauchbar)} von "
                f"{len(self.regeln)}), um ueber die Bauart etwas zu sagen."
            )

        tief, hoch = self.spanne
        teile.append(
            f"**{len(self.verdichtende)} von {len(brauchbar)} brauchbaren "
            f"Regeln verdichten**, die Spanne reicht von {tief:.2f}x bis "
            f"{hoch:.2f}x. Vermessen wurden {len(self.regeln)} Regeln des "
            f"Katalogs; der Rest traegt nichts (zu wenige Haltezeiten oder "
            f"ein Grund, der in der Tabelle steht)."
        )

        if bestand is not None and bestand.brauchbar:
            if self.bestand_liegt_drin:
                teile.append(
                    f"**Der Bestand ({bestand.verdichtung:.2f}x) liegt "
                    f"mitten darin**, nicht an einem Rand. Die Verdichtung "
                    f"ist damit keine Eigenschaft dieses Kandidaten, sondern "
                    f"der Bauart - und was die Bauart traegt, kann die Suche "
                    f"innerhalb dieses Katalogs nicht herauswaehlen."
                )
            else:
                teile.append(
                    f"**Der Bestand ({bestand.verdichtung:.2f}x) liegt "
                    f"ausserhalb der Spanne der uebrigen Regeln.** Dann ist "
                    f"die Verdichtung seine Eigenschaft und nicht die der "
                    f"Bauart - und eine andere Regel traegt weniger davon."
                )

        if self.ausnahmen:
            teile.append(
                f"**Ausnahmen, die dazugehoeren:** "
                f"{', '.join(r.name for r in self.ausnahmen)} "
                f"{'verdichten' if len(self.ausnahmen) > 1 else 'verdichtet'} "
                f"nicht. Sie stehen hier und nicht in einer Fussnote - eine "
                f"Aussage ueber die Bauart, die ihre Gegenbeispiele "
                f"verschweigt, ist keine."
            )

        if self.haengt_an_der_schwelle:
            teile.append(
                f"**Achtung:** Ohne die Schwelle von {MINDESTZEITEN} "
                f"Haltezeiten waere die Aussage eine andere. Die Schwelle ist "
                f"gesetzt und nicht gemessen - hier entscheidet sie mit, und "
                f"das ist zu wenig."
            )
        else:
            teile.append(
                f"Die Aussage haengt nicht an der Schwelle von "
                f"{MINDESTZEITEN} Haltezeiten: Ohne sie faellt sie genauso "
                f"aus."
            )

        teile.append(
            "Kostet keinen Versuch: Diese Genome stehen laengst im Katalog "
            "und waren gezaehlt, als sie entstanden - nachgemessen wird ein "
            "vorhandener Vorrat, ausgewaehlt wird nichts. Wer eine davon "
            "weiterverfolgt, hat eine Auswahl getroffen und muss sie zaehlen."
        )
        return "\n\n".join(teile)


__all__ = [
    "MINDESTZEITEN",
    "STUNDEN_JE_JAHR",
    "Familienbild",
    "Haltezeit",
    "Marktverdichtung",
    "Regelverdichtung",
    "Verdichtungsbild",
    "aus_bild",
    "messe",
]
