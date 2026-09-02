"""Was der Vorrat hergibt - und ob das je reichen kann.

Die Frage, die Befund 75 offen liess
------------------------------------
Dort wurde ueber 14 Genome **r = -0,533** zwischen Trade-Zahl und Qualitaet
je Trade gemessen und ausdruecklich als Eigenschaft *des Vorrats* bezeichnet,
nicht einer einzelnen Regel. Der Befund endete mit einem Ziel - *"mindestens
120 Trades, positiver Sharpe ueber 0,23"* - und liess die naheliegende Frage
stehen:

    Guete = SR je Trade * Wurzel(n). Faellt SR mit n, hat die Guete ein
    **Maximum**. Liegt es unter dem, was der Deflated Sharpe verlangt, kann
    in diesem Vorrat nichts bestehen - egal wie lange man sucht.

Neunzig Befunde lang ist diese Rechnung nicht gemacht worden.

Was gemessen wurde (Befund 168)
-------------------------------
Alle 39 Genome der auf Tageskerzen vorgesehenen Generationen, am Spot-Punkt.
**23 davon handeln auf Tageskerzen ueberhaupt nicht** - Generation 8 lebt von
Kursluecken, VWAP und der New Yorker Eroeffnung, also von Innertagesbegriffen.
Eines liefert zu wenige Trades, eines faellt mit n_eff 5 unter die Stichprobe,
bei der es ueberhaupt eine Latte gibt, eines ist eine Regel unter zwei Namen.
Uebrig bleiben **14 verschiedene Regeln** mit n_eff 27 bis 121:

    Trend-Beteiligung 50 Tage      n_eff 111   SR 0,2148   Guete 2,263
    Trend-Beteiligung (fair)              45      0,3214         2,156
    Donchian-Ausbruch 55/20               55      0,2674         1,983
    Vola-Ziel, kurzes Messfenster         34      0,3384         1,973
    ...
    Momentum-Beteiligung 90 Tage          39      0,1850         1,155

    r(n_eff, SR) = -0,714 bei t = -3,53

Die Kopplung ist damit an einem **anderen** Vorrat, an einem anderen
Betriebspunkt und mit der Stichprobe des Gates bestaetigt - Befund 75 hatte
-0,533 ueber 14 Genome auf rohen Trade-Zahlen.

Die beiden Enden zeigen sie unmittelbar: Die hoechste Qualitaet (0,3406)
kommt mit n_eff 31, die groesste Stichprobe (121) mit SR 0,1583. Beste Menge
und beste Guete sitzen nie auf derselben Regel.

Die Decke
---------
Auf der angepassten Geraden hat ``SR(n) * sqrt(n)`` ihren Scheitel bei
**n_eff 69 mit Guete 1,931**. Verlangt sind dort 3,522 - es fehlen 1,591. Die
Luecke schliesst sich an keiner Stelle des gemessenen Bereichs, und auch
ausserhalb nicht: Die Gerade sagt SR = 0 bei n_eff 208. Eine Regel, die so oft
handelt wie der Bestand, hat in diesem Vorrat keinen Vorteil mehr.

Wo der Bestand darin steht
--------------------------
Der Spitzenkandidat liegt bei n_eff 115 mit SR 0,2708. Die Gerade sagt dort
0,1554. Der Rest von **+2,41 Reststreuungen** ist sein ganzer Vorsprung vor
dem eigenen Vorrat.

Zum Vergleich: Das erwartete Maximum aus *k* unabhaengigen Ziehungen einer
Standardnormalen liegt bei rund ``sqrt(2 ln k)`` - bei 14 sind das 2,30, bei
198 Versuchen 3,25.

**Der Vorsprung des Bestands ist kleiner als das, was reine Auswahl bei
diesem Versuchsstand ohnehin erzeugt.** Das ist kein Beweis, dass er nichts
kann - aber es ist dieselbe Aussage, die der Deflated Sharpe aus einer
voellig anderen Richtung macht (0,5881 gegen 0,95), und die beiden Wege sind
unabhaengig: Der eine sieht die Verteilung der Trades, der andere die Lage
des Kandidaten in seiner Grundgesamtheit.

Der Messfehler auf dem Weg dorthin
----------------------------------
Der erste Anlauf **setzte** ``fraction`` auf 1,0, statt dort zu deckeln - so
macht ``_spotpunkt`` es fuer den Bestand, dessen 3,0 dadurch faellt. Genome
mit 0,4 wurden davon zweieinhalbmal groesser. Die Zahlen sahen plausibel aus
(13 Regeln, r = -0,601, Decke 1,814) und waren falsch. Aufgefallen ist es
nicht an ihnen, sondern daran, dass Generation 8 durchgehend null Trades
lieferte - was sich als eigene, richtige Beobachtung herausstellte.
``cli.py._ohne_hebel`` deckelt jetzt, an einer Stelle fuer beide Aufrufer.

Worauf die Kopplung steht (Befund 169)
--------------------------------------
Einen Lauf spaeter nachgesehen, wer die Auffaelligkeit traegt. Eingeteilt
nach dem **Einstiegsindikator**, strukturell aus dem Genom gelesen:

    sma 9,  roc 2,  ema 1,  distance_to_ema_pct 1,  swing_high 1

    ganzer Vorrat      14 Regeln   r = -0,714   t = -3,53
    nur 'sma'           9 Regeln   r = -0,778   t = -3,28
    ohne 'sma'          5 Regeln   r = -0,547   t = -1,13  sagt nichts
    Familienmediane     5 Punkte   r = -0,744   t = -1,93  sagt nichts

**Die Kopplung ist innerhalb einer Familie belegt und darueber hinaus
nicht.** Neun von vierzehn Regeln sind derselbe Einstiegsindikator, dreizehn
von vierzehn sind long-only. Damit ist Befund 168 enger zu lesen, als er
geschrieben war: Die Decke beschreibt **diese Familie**, nicht "den Vorrat" -
und faellt insoweit auf Befund 54 zurueck, wo die Kopplung an einem
Kandidaten durch Verstellen seiner Regler entstand.

Die Familienmediane zeigen dasselbe Gefaelle (hoechste Qualitaet bei der
kleinsten Stichprobe) und verfehlen die Schwelle knapp. **Knapp ist nicht
erreicht**; genau dieser Fehler steht in Befund 75 als Scheinbefund.

Was davon **unberuehrt** bleibt: dass keine gemessene Regel in die Naehe der
Latte kommt. Die beste steht bei Guete 2,263 gegen 3,522. Das ist eine
Beobachtung an vierzehn Messungen und haengt an keiner Geraden.

Was hier **nicht** steht
------------------------
* Dass es keine Regel gibt, die reicht. Gemessen ist ein **vorhandener
  Vorrat auf Tageskerzen**, nicht der Raum aller Strategien. Befund 75 hat
  das schon so formuliert, und es gilt hier genauso.
* Ein formaler Test. Der Vergleich "2,41 gegen 3,25" nimmt normalverteilte
  Reste und austauschbare Ziehungen an; die 198 Versuche enthalten Verbunde
  und 15-Minuten-Laeufe, die hier gar nicht vorkommen. Es ist ein Vergleich
  der Groessenordnung, und mehr wird daraus nicht gemacht.
* Eine Empfehlung, irgendetwas zu lockern. Die Decke ist ein Grund, den
  Vorrat zu wechseln, kein Grund, die Latte zu senken.
* Eine Aussage ueber Familien, die hier gar nicht vorkommen. Vier der fuenf
  sind mit einer oder zwei Regeln vertreten - ueber sie sagt diese Messung
  nichts, weder gut noch schlecht.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

#: Ab welchem |t| dieses Modul aus einer Korrelation etwas schliesst.
#:
#: Befund 75 hat den Grund geliefert: Der erste Anlauf dort rechnete die
#: Kopplung auf fuenf Bestenlisten-Eintraegen, bekam **r = +0,359** - das
#: Gegenteil - und zog trotzdem denselben Schluss. Eine Korrelation ohne
#: Deckung darf nicht klingen wie eine mit.
MINDEST_T = 2.0


@dataclass(frozen=True, slots=True)
class Punkt:
    """Eine gemessene Regel: wie oft sie handelt und wie gut."""

    name: str
    n_eff: int
    sharpe_je_trade: float

    @property
    def guete(self) -> float:
        return self.sharpe_je_trade * self.n_eff**0.5


@dataclass(frozen=True, slots=True)
class Decke:
    """Die angepasste Gerade durch einen Vorrat - und was sie zulaesst."""

    punkte: tuple[Punkt, ...]
    achsenabschnitt: float
    steigung: float
    r: float
    t: float
    reststreuung: float

    @property
    def tragfaehig(self) -> bool:
        """Sagt die Kopplung genug, um daraus eine Decke zu lesen?

        Zwei Bedingungen, und beide muessen halten: Die Steigung muss negativ
        sein - ohne fallende Qualitaet gibt es kein Maximum - und die
        Korrelation muss Deckung haben.
        """
        return self.steigung < 0 and abs(self.t) >= MINDEST_T

    @property
    def scheitel_n(self) -> float | None:
        """Bei welcher Stichprobe die Guete ihr Maximum hat.

        ``(a + b n) * sqrt(n)`` ist maximal bei ``n = -a / (3 b)`` - Ableitung
        Null. Ohne tragfaehige Kopplung wird **keine** Zahl geliefert, statt
        eine auszurechnen, die nichts bedeutet.
        """
        if not self.tragfaehig:
            return None
        return -self.achsenabschnitt / (3 * self.steigung)

    @property
    def scheitel_guete(self) -> float | None:
        n = self.scheitel_n
        if n is None or n <= 0:
            return None
        return (self.achsenabschnitt + self.steigung * n) * n**0.5

    @property
    def bereich(self) -> tuple[int, int]:
        """Der gemessene Bereich - alles ausserhalb ist Verlaengerung."""
        werte = [p.n_eff for p in self.punkte]
        return min(werte), max(werte)

    @property
    def nullstelle(self) -> float | None:
        """Ab welcher Stichprobe die Gerade keinen Vorteil mehr sieht."""
        if self.steigung >= 0:
            return None
        return -self.achsenabschnitt / self.steigung

    def vorhersage(self, n_eff: int) -> float:
        return self.achsenabschnitt + self.steigung * n_eff

    def rest(self, n_eff: int, sharpe_je_trade: float) -> float:
        """Wie weit eine Regel ueber ihrem Vorrat liegt, in Reststreuungen.

        **Der Vergleich ist |r| und nicht die Reststreuung selbst.** Liegen
        die Punkte exakt auf der Geraden, ist die Reststreuung in
        Fliesskommazahlen nicht null, sondern etwa 1e-17 - eine Pruefung auf
        ``<= 0`` faellt darauf herein und liefert Reste in der Groessenordnung
        1e15. Genau das ist beim ersten Anlauf passiert. ``1 - r**2`` ist
        skalenfrei und misst dieselbe Entartung.
        """
        if self.reststreuung <= 0 or 1 - self.r**2 <= 1e-12:
            raise ValueError(
                "Reststreuung null - die Punkte liegen auf der Geraden, "
                "eine Einordnung in Reststreuungen ist dann bedeutungslos."
            )
        return (sharpe_je_trade - self.vorhersage(n_eff)) / self.reststreuung

    @staticmethod
    def erwartetes_maximum(ziehungen: int) -> float:
        """Wie hoch das Beste aus *k* Ziehungen allein durch Auswahl liegt.

        ``sqrt(2 ln k)`` fuer die Standardnormale - eine Naeherung, und sie
        steht hier auch nur als solche. Sie beantwortet die Frage, ob ein
        Vorsprung ueberhaupt erklaerungsbeduerftig ist.
        """
        if ziehungen < 2:
            raise ValueError("Unter zwei Ziehungen gibt es kein Maximum.")
        return math.sqrt(2 * math.log(ziehungen))


def baue(punkte: list[Punkt]) -> Decke:
    """Die Gerade durch einen gemessenen Vorrat legen.

    Verlangt mindestens drei Regeln und verschiedene Stichprobengroessen -
    durch zwei Punkte laesst sich immer eine Gerade legen, und ihre
    Reststreuung ist dann null.
    """
    if len(punkte) < 3:
        raise ValueError(
            f"{len(punkte)} Regeln sind zu wenige - durch zwei Punkte geht "
            f"immer eine Gerade."
        )
    n = [float(p.n_eff) for p in punkte]
    sr = [p.sharpe_je_trade for p in punkte]
    if len(set(n)) < 2:
        raise ValueError(
            "Alle Regeln haben dieselbe Stichprobe - dann gibt es keine "
            "Steigung zu messen."
        )
    steigung = statistics.covariance(n, sr) / statistics.variance(n)
    achsenabschnitt = statistics.fmean(sr) - steigung * statistics.fmean(n)
    r = statistics.correlation(n, sr)
    # Bei |r| = 1 ist t unendlich; das ist rechnerisch richtig und hier
    # unerreichbar, weil dann die Reststreuung null waere und ``rest``
    # ohnehin verweigert.
    t = (
        math.inf * (1 if r > 0 else -1)
        if abs(r) >= 1
        else r * math.sqrt((len(punkte) - 2) / (1 - r**2))
    )
    reste = [s - (achsenabschnitt + steigung * x) for x, s in zip(n, sr, strict=True)]
    return Decke(
        punkte=tuple(punkte),
        achsenabschnitt=achsenabschnitt,
        steigung=steigung,
        r=r,
        t=t,
        reststreuung=statistics.stdev(reste),
    )


def urteil(decke: Decke, noetig_bei) -> str:
    """Was die Decke sagt - und was sie nicht sagt.

    ``noetig_bei`` ist eine Funktion ``n_eff -> noetige Guete``; uebergeben
    wird ``research.verbund.noetige_guete`` mit dem Versuchsstand. Sie kommt
    von aussen, damit dieses Modul den Versuchszaehler nicht ein zweites Mal
    liest - vier Befunde dieses Projekts handeln von doppelt gepflegten
    Zahlen (158, 159, 165).
    """
    if not decke.tragfaehig:
        grund = (
            "die Qualitaet faellt nicht mit der Trade-Zahl"
            if decke.steigung >= 0
            else f"|t| = {abs(decke.t):.2f} liegt unter {MINDEST_T:.0f}"
        )
        return (
            f"**Keine Decke ablesbar** ({grund}). Bei {len(decke.punkte)} "
            f"Regeln ist r = {decke.r:+.3f}. Diese Punkte sagen darueber "
            f"nichts - weder das eine noch das andere."
        )
    n = decke.scheitel_n
    g = decke.scheitel_guete
    noetig = noetig_bei(round(n))
    unten, oben = decke.bereich
    zeilen = [
        f"**Die hoechste Guete, die dieser Vorrat hergibt: {g:.3f}** bei "
        f"n_eff {n:.0f}.",
        f"Verlangt sind dort {noetig:.3f} - es fehlen {noetig - g:.3f}.",
        f"Gemessen an {len(decke.punkte)} verschiedenen Regeln, "
        f"r = {decke.r:+.3f} bei t = {decke.t:+.2f}, "
        f"Stichproben von {unten} bis {oben}.",
    ]
    null = decke.nullstelle
    if null is not None:
        zeilen.append(
            f"Die Gerade sieht bei n_eff {null:.0f} keinen Vorteil mehr - eine "
            f"Regel, die so oft handelt, hat in diesem Vorrat nichts uebrig."
        )
    zeilen.append(
        "**Das ist eine Aussage ueber diesen Vorrat, nicht ueber den Raum "
        "aller Strategien** - und kein Grund, eine Latte zu senken."
    )
    return "\n".join(zeilen)


def traegt_eine_familie(
    nach_familie: dict[str, list[Punkt]],
) -> tuple[str, Decke | None, Decke | None] | None:
    """Steht die Kopplung auf **einer** Familie oder auf dem ganzen Vorrat?

    Der Unterschied entscheidet, was die Decke bedeutet. Befund 54 hat die
    Kopplung an *einem* Kandidaten gemessen, durch Verstellen seiner Regler;
    Befund 75 nannte sie eine Eigenschaft *des Vorrats* und grenzte sich
    damit ausdruecklich davon ab. Traegt in Wahrheit eine Familie die ganze
    Auffaelligkeit, sind beide Aussagen wieder dieselbe - nur mit mehr Namen
    (Befund 169).

    Geliefert wird ``(Name der groessten Familie, Gerade darin, Gerade ohne
    sie)``; jede Gerade ist ``None``, wo zu wenige Regeln stehen. ``None``
    fuer das Ganze, wenn keine Familie die Mehrheit haelt - dann stellt sich
    die Frage nicht.
    """
    if not nach_familie:
        return None
    gesamt = sum(len(ps) for ps in nach_familie.values())
    groesste = max(nach_familie, key=lambda f: len(nach_familie[f]))
    if len(nach_familie[groesste]) * 2 <= gesamt:
        return None
    rest = [p for f, ps in nach_familie.items() if f != groesste for p in ps]
    return groesste, _versuche_gerade(nach_familie[groesste]), _versuche_gerade(rest)


def _versuche_gerade(punkte: list[Punkt]) -> Decke | None:
    """Eine Gerade, wo sie sich legen laesst - sonst nichts."""
    try:
        return baue(punkte)
    except ValueError:
        return None


def familienurteil(aufteilung: tuple[str, Decke | None, Decke | None]) -> str:
    """Was die Aufteilung ueber die Tragfaehigkeit der Decke sagt."""
    name, drin, ohne = aufteilung
    zeilen = [
        f"**Die Mehrheit der Regeln ist dieselbe Familie ({name}).** Was die "
        f"Kopplung traegt, entscheidet, worueber die Decke spricht."
    ]
    if drin is not None:
        zeilen.append(
            f"  Nur '{name}': {len(drin.punkte)} Regeln, r = {drin.r:+.3f}, "
            f"t = {drin.t:+.2f}"
        )
    if ohne is None:
        zeilen.append("  Ohne sie bleiben zu wenige Regeln fuer eine Gerade.")
    else:
        zeilen.append(
            f"  Ohne '{name}': {len(ohne.punkte)} Regeln, r = {ohne.r:+.3f}, "
            f"t = {ohne.t:+.2f}"
            + ("" if ohne.tragfaehig else " - **sagt nichts**")
        )
    if drin is not None and drin.tragfaehig and (ohne is None or not ohne.tragfaehig):
        zeilen.append(
            "  Damit ist die Kopplung **innerhalb einer Familie** belegt und "
            "darueber hinaus nicht. Die Decke beschreibt diese Familie; fuer "
            "den Vorrat als Ganzes reicht es nicht."
        )
    return "\n".join(zeilen)


__all__ = [
    "MINDEST_T",
    "Decke",
    "Punkt",
    "baue",
    "familienurteil",
    "traegt_eine_familie",
    "urteil",
]
