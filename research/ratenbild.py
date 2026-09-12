"""Reicht der Mittelwert? (Befund 266)

Die Frage
---------
Befund 250 hat gemessen, wo jedes Gate kippt, wenn der Funding-Satz steigt:
'Schlechtestes Jahr' haelt bis 5,99 % im Jahr, 'Parameter-Plateau' bis 9,75 %.
Beide Zahlen sind mit einem **flachen** Satz gemessen - jede Achtstundenperiode
traegt denselben Wert.

Echtes Funding ist nicht flach. Und Befund 251 hat gemessen, dass dieser
Kandidat seine Haltezeit nicht gleichmaessig ueber die Jahre verteilt: Er ist
auf BTC 37 % der Zeit im Markt und faengt dabei 93 % des gesamten Anstiegs
ein; 62 % seines Fundings faellt in steigende Phasen.

Zwei Groessen treffen also aufeinander, die beide schwanken - die Rate und die
Haltezeit. Wenn sie zusammen schwanken, zahlt der Kandidat mehr als ein
flacher Satz auf denselben Mittelwert. Dann waere die Zahl "6,0 %" eine
Aussage ueber eine Welt, in der Funding konstant ist.

Die Frage ist damit nicht *"wie hoch ist die Rate"*, sondern **"reicht ihr
Mittelwert, um das Urteil zu faellen"** - und die ist ohne Bybit zu
beantworten: Zwei Zeitplaene, **derselbe Mittelwert**, verschiedene Form.
Bewegt sich etwas?

Was gemessen wurde
------------------
Auf dem Bestand, Tageskerzen, BTC + ETH, gemeinsamer Zeitraum:

    Mittelwert   Form              gezahlt   gegen flach   Schlechtestes Jahr
     5,90 %      flach               36,23        +0,00 %   -9,99   haelt
     5,90 %      wechselnd           36,23        -0,01 %   -9,99   haelt
     5,90 %      gekoppelt 0,5       44,11       +21,76 %  -10,01   faellt
     5,90 %      gekoppelt 1,0       52,00       +43,51 %  -10,03   faellt

**Es liegt an der Kopplung, nicht am Schwanken.** ``wechselnd`` traegt
dieselbe Streuung wie ``gekoppelt 0,5`` und zahlt -0,01 %. Erst wenn die hohe
Rate mit der Haltezeit zusammenfaellt, kostet sie etwas.

**Am Gate kommt wenig davon an.** Der Aufschlag von 21,8 % auf das gesamte
Funding verschiebt das schlechteste Jahr um 0,02 Punkte, der von 43,5 % um
0,04 - sauber proportional, aber winzig. Das zusaetzliche Funding faellt in
die Aufwaertsjahre; das schlechteste Jahr ist ein Abwaertsjahr und bekommt
kaum etwas ab.

**An der Schwelle entscheidet es trotzdem.** Der Kipppunkt je Form, durch
Laeufe eingegrenzt:

    flach            5,99 bis 6,07 %   (Befund 250, hier unabhaengig bestaetigt)
    gekoppelt 0,5    5,70 bis 5,80 %
    gekoppelt 1,0    4,90 bis 5,70 %

Der Spielraum schrumpft also um rund 0,25 Punkte und **nicht** um 21,8 %.
Deshalb gibt es hier keine Umrechnung aus dem Aufschlag: Sie traf fuer
Kopplung 0,5 zufaellig und verfehlte 1,0 um mehr als einen halben Punkt. Der
Kipppunkt je Form ist zu messen.

Was hier nicht gemessen wird
----------------------------
Wie stark echtes Funding tatsaechlich mit der Marktrichtung laeuft. Das ist
die Haelfte, die Bybit braucht, und sie bleibt offen (100, 251). Gemessen wird
die **Empfindlichkeit**: was eine gegebene Kopplung am Urteil aendert.

Der Unterschied ist der zwischen "der Kandidat zahlt X" und "wenn die Kopplung
so aussieht, zahlt er X". Nur das Zweite steht hier.

Warum der Mittelwert exakt stimmen muss
---------------------------------------
Wenn zwei Zeitplaene verschiedene Mittelwerte haetten, waere jeder Unterschied
im Ergebnis wieder eine Messung der **Hoehe** - und die steht seit 250 fest.
Gemessen werden soll die **Form**. Deshalb zieht ``zentriert`` jeden Aufbau auf
den Zielmittelwert zurueck, ``Ratenbild.mittel`` rechnet ihn nach, und
``Ratenvergleich.gleicher_mittelwert`` sagt, ob der Vergleich ueberhaupt
gueltig ist. Ein Vergleich, der das nicht haelt, faellt nicht auf - er sieht
aus wie ein Befund.

Kostet keinen Versuch: derselbe Kandidat, derselbe Zeitraum, veraendert wird
die Form einer Kostenannahme. Ausgewaehlt wird nichts, und insbesondere wird
keine Form gewaehlt, weil unter ihr mehr Gates halten.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from statistics import fmean, pstdev

from backtest.costs import FundingSchedule
from research.finanzierung import FEINHEIT, PERIODEN_JE_JAHR, jahr_pct

#: Wie genau der Mittelwert getroffen sein muss, damit ein Vergleich der Form
#: einer ist. Dieselbe Feinheit wie in ``research.finanzierung``: Sie liegt
#: weit unter jedem Abstand, den ein Gate aufloest.
MITTELFEINHEIT = FEINHEIT


def zentriert(werte: Sequence[float], ziel: float) -> tuple[float, ...]:
    """Einen Aufbau additiv auf den Zielmittelwert schieben.

    **Additiv und nicht multiplikativ.** Ein Faktor wuerde die Streuung
    mitziehen, und dann waere nicht mehr zu trennen, ob die Form oder ihre
    Staerke gewirkt hat. Ein Versatz laesst die Form, wie sie ist.
    """
    if not werte:
        return ()
    versatz = ziel - fmean(werte)
    return tuple(w + versatz for w in werte)


@dataclass(frozen=True, slots=True)
class Ratenbild:
    """Ein Zeitplan mit bekanntem Mittelwert und bekannter Form."""

    name: str
    zeiten: tuple[datetime, ...]
    saetze: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.zeiten) != len(self.saetze):
            raise ValueError("Zu jedem Zeitpunkt gehoert genau ein Satz.")

    @property
    def mittel(self) -> float:
        """Der tatsaechliche Mittelwert je Achtstundenperiode."""
        return fmean(self.saetze) if self.saetze else 0.0

    @property
    def streuung(self) -> float:
        """Wie weit die Saetze um ihren Mittelwert liegen."""
        return pstdev(self.saetze) if len(self.saetze) > 1 else 0.0

    @property
    def mittel_pct(self) -> float:
        """Der Mittelwert als Jahresprozent - die Einheit der Kipppunkte."""
        return jahr_pct(self.mittel)

    @property
    def flach(self) -> bool:
        return self.streuung <= MITTELFEINHEIT

    @property
    def zeitplan(self) -> FundingSchedule:
        """Als Kostenmodell, wie ``data.funding.schedule_from_frame`` es baut.

        ``default_rate`` ist der Mittelwert und nicht der Vorgabewert: Ein
        Zeitpunkt ausserhalb der Liste soll den Vergleich nicht verschieben.
        """
        return FundingSchedule(
            rates={z: Decimal(str(s)) for z, s in zip(self.zeiten, self.saetze, strict=True)},
            default_rate=Decimal(str(self.mittel)),
        )

    def trifft(self, ziel: float) -> bool:
        return abs(self.mittel - ziel) <= MITTELFEINHEIT


def flaches_bild(zeiten: Sequence[datetime], satz: float) -> Ratenbild:
    """Die Kontrolle: jede Periode traegt denselben Satz."""
    return Ratenbild("flach", tuple(zeiten), tuple([satz] * len(zeiten)))


def wechselndes_bild(
    zeiten: Sequence[datetime], satz: float, *, hub: float
) -> Ratenbild:
    """Auf und ab, ohne Bezug zum Markt.

    Die Gegenprobe zur Kopplung: Streuung allein, ohne Zusammenhang mit der
    Haltezeit. Bewegt schon sie das Urteil, liegt es nicht an der Kopplung,
    sondern daran, dass ueberhaupt geschwankt wird.
    """
    roh = [satz * (1 + hub if i % 2 == 0 else 1 - hub) for i in range(len(zeiten))]
    return Ratenbild("wechselnd", tuple(zeiten), zentriert(roh, satz))


def gekoppeltes_bild(
    zeiten: Sequence[datetime],
    satz: float,
    richtung: Sequence[int],
    *,
    hub: float,
) -> Ratenbild:
    """Hoch, wenn der Markt gestiegen ist - die Lage aus Befund 100 und 251.

    ``richtung`` ist je Zeitpunkt +1 (der Markt stand davor hoeher als am
    Fensteranfang) oder -1. Der Aufbau wird danach auf ``satz`` zentriert: Was
    in Aufwaertsphasen dazukommt, fehlt in Abwaertsphasen.
    """
    if len(richtung) != len(zeiten):
        raise ValueError("Zu jedem Zeitpunkt gehoert genau eine Richtung.")
    roh = [satz * (1 + hub * r) for r in richtung]
    return Ratenbild("gekoppelt", tuple(zeiten), zentriert(roh, satz))


def richtungsfolge(
    kurse: Sequence[tuple[datetime, float]],
    zeiten: Sequence[datetime],
    *,
    fenster: int,
) -> tuple[int, ...]:
    """Stand der Markt vor diesem Zeitpunkt hoeher als ``fenster`` Kurse davor?

    +1 fuer ja, -1 fuer nein. Am Anfang der Reihe, wo das Fenster noch nicht
    voll ist, steht -1 und nicht 0: Eine dritte Stufe waere ein dritter
    Zustand, den ``gekoppeltes_bild`` als halbe Kopplung lesen wuerde. Der
    Anfang ist kurz, und ``zentriert`` faengt den Versatz ohnehin ab.
    """
    if fenster < 1:
        raise ValueError("Das Fenster braucht mindestens einen Kurs.")
    geordnet = sorted(kurse)
    stempel = [z for z, _ in geordnet]
    werte = [k for _, k in geordnet]

    folge: list[int] = []
    for zeit in zeiten:
        # Der letzte Kurs **vor** dem Zeitpunkt: Funding faellt an, was bis
        # dahin bekannt ist, nicht auf den Kurs desselben Moments.
        i = _letzter_index(stempel, zeit)
        if i is None or i < fenster:
            folge.append(-1)
            continue
        folge.append(1 if werte[i] > werte[i - fenster] else -1)
    return tuple(folge)


def _letzter_index(stempel: Sequence[datetime], zeit: datetime) -> int | None:
    """Index des letzten Stempels echt vor ``zeit``; ``None``, wenn keiner."""
    from bisect import bisect_left

    i = bisect_left(stempel, zeit)
    return i - 1 if i > 0 else None


@dataclass(frozen=True, slots=True)
class Ratenprobe:
    """Ein Bild, durchgerechnet."""

    bild: Ratenbild
    bestanden: int
    gesamt: int
    gefallen: tuple[str, ...]
    cagr_pct: float
    rueckgang_pct: float
    gezahlt: float

    @property
    def name(self) -> str:
        return self.bild.name


@dataclass(frozen=True, slots=True)
class Ratenvergleich:
    """Mehrere Formen auf demselben Mittelwert nebeneinander."""

    ziel: float
    proben: tuple[Ratenprobe, ...]

    @property
    def gleicher_mittelwert(self) -> bool:
        """Ohne das ist jeder Unterschied wieder eine Messung der Hoehe."""
        return all(p.bild.trifft(self.ziel) for p in self.proben)

    @property
    def kontrolle(self) -> Ratenprobe | None:
        return next((p for p in self.proben if p.bild.flach), None)

    @property
    def abweichende(self) -> tuple[Ratenprobe, ...]:
        """Proben, deren Gates anders stehen als bei der flachen Kontrolle."""
        grund = self.kontrolle
        if grund is None:
            return ()
        return tuple(
            p
            for p in self.proben
            if p is not grund and p.gefallen != grund.gefallen
        )

    @property
    def bewegt_die_gates(self) -> bool:
        return bool(self.abweichende)

    def mehrzahlung(self, name: str) -> float | None:
        """Wie viel mehr diese Form zahlt als die flache - in Prozent.

        Der eigentliche Mechanismus: Gezahlt wird nur waehrend der Haltezeit.
        Liegt sie dort, wo die Rate hoch ist, zahlt derselbe Mittelwert mehr.
        """
        grund = self.kontrolle
        probe = next((p for p in self.proben if p.name == name), None)
        if grund is None or probe is None or not grund.gezahlt:
            return None
        return (probe.gezahlt / grund.gezahlt - 1) * 100

    @property
    def liegt_an_der_kopplung(self) -> bool:
        """Ist es die Kopplung - oder reicht schon blosses Schwanken?

        Die Gegenprobe des Befunds. ``wechselnd`` traegt dieselbe Streuung wie
        ``gekoppelt``, nur ohne Bezug zur Marktrichtung. Stimmt es mit der
        flachen Kontrolle ueberein und ``gekoppelt`` nicht, dann liegt es am
        **Zusammenfallen** von Rate und Haltezeit und nicht daran, dass die
        Rate ueberhaupt schwankt.
        """
        namen = {p.name for p in self.abweichende}
        return "gekoppelt" in namen and not {
            n for n in namen if n.startswith("wechselnd")
        }

    def urteil(self) -> str:
        if not self.gleicher_mittelwert:
            return (
                "Die Bilder liegen nicht auf demselben Mittelwert - der "
                "Vergleich misst die Hoehe und nicht die Form."
            )
        if self.kontrolle is None:
            return "Ohne flache Kontrolle ist nichts zu vergleichen."
        if not self.bewegt_die_gates:
            return (
                f"Auf {jahr_pct(self.ziel):.2f} % im Jahr entscheidet die Form "
                "nicht mit: Alle Bilder lassen dieselben Gates stehen. Der "
                "Mittelwert reicht fuer das Urteil."
            )
        namen = ", ".join(p.name for p in self.abweichende)
        satz = (
            f"Auf {jahr_pct(self.ziel):.2f} % im Jahr entscheidet die Form mit "
            f"({namen}) - der Mittelwert allein traegt das Urteil nicht."
        )
        if self.liegt_an_der_kopplung:
            satz += (
                " Und es liegt an der Kopplung und nicht am Schwanken: "
                "Dieselbe Streuung ohne Bezug zur Marktrichtung laesst alle "
                "Gates stehen."
            )
        return satz


def vergleiche(
    bilder: Iterable[Ratenbild],
    lauf: Callable[[Ratenbild], Ratenprobe],
    *,
    ziel: float,
) -> Ratenvergleich:
    """Jedes Bild durchrechnen und nebeneinanderstellen.

    ``lauf`` bekommt das Bild und liefert die Probe - so bleibt dieses Modul
    ohne Kerzen pruefbar, und der Aufrufer entscheidet, worauf gerechnet wird.
    """
    return Ratenvergleich(ziel, tuple(lauf(b) for b in bilder))


__all__ = [
    "MITTELFEINHEIT",
    "PERIODEN_JE_JAHR",
    "Ratenbild",
    "Ratenprobe",
    "Ratenvergleich",
    "flaches_bild",
    "gekoppeltes_bild",
    "richtungsfolge",
    "vergleiche",
    "wechselndes_bild",
    "zentriert",
]
