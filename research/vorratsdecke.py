"""Was der Vorrat hergibt - und ob das je reichen kann.

ACHTUNG: Alle Zahlen unten stehen auf einem gefilterten Vorrat
==============================================================
**Befund 182.** Bis dahin lief jedes Genom mit seiner **eigenen**
Groessenlogik durch diesen Katalog. Neun von dreissig Tagesgenomen lieferten
dadurch null Trades - nicht weil ihr Einstieg nicht ausloest (die Signale
kreuzen 182-mal), sondern weil ihre ``risiko``-Logik am Stop-Abstand bemisst
und ablehnt. Mit der Groessenlogik des Bestands handeln dieselben Regeln 138,
103, 71, 61, 58, 41, 40, 19 und 7 Mal.

Die vierzehn Regeln unten sind damit **die, die diesen Filter ueberlebt
haben**, und der Filter hat mit dem Einstieg nichts zu tun. Betroffen sind
alle Zahlen dieses Modulkopfs sowie die Befunde 168, 169, 179, 180 und 181 -
insbesondere die Familienzaehlung "sma 9, roc 2, ...", auf der sie stehen.
Neu gemessen ist noch nichts; ``cli vorratsdecke`` stellt seit Befund 182
alle auf dieselbe Groessenlogik, und der naechste Lauf liefert die neuen
Zahlen.

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
Alle Genome der auf Tageskerzen vorgesehenen Generationen, am Spot-Punkt.
Zur Zeit der Messung waren das 39; Generation 8 stand damals faelschlich auf
Tageskerzen und ist seit Befund 170 auf Viertelstunden gebucht - **sie hat zu
keiner Zahl hier beigetragen**, weil keines ihrer neun Genome auf Tageskerzen
handelt. Der Vorrat sind damit 30 Genome, von denen 14 nicht handeln.

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

    def noetiger_abstand(
        self, noetig_je_trade, *, von: int = 15, bis: int = 400
    ) -> tuple[int, float] | None:
        """Wie weit ueber der eigenen Geraden eine Regel liegen **muesste**.

        **Die Frage, die Befund 178 offengelassen hat.** Dort standen zwei
        Tore: mehr Qualitaet je Trade, oder dieselbe Qualitaet bei groesserer
        Stichprobe. Das zweite steht dort unter der Bedingung *"bei
        unveraenderter Qualitaet"* - und genau die haelt in diesem Vorrat
        nicht, weil Qualitaet und Menge gekoppelt sind (Befund 168/169).

        Diese Rechnung legt beide Kurven uebereinander: Die Gerade sagt, was
        eine Regel dieser Familie bei ``n`` an Qualitaet **hat**; die Latte
        sagt, was sie dort **braucht**. Der Abstand dazwischen, gemessen in
        Reststreuungen, ist der Preis - und er hat ein Minimum. Wo es liegt,
        ist die guenstigste Stelle der ganzen Strecke.

        ``noetig_je_trade`` ist eine Funktion ``n_eff -> noetiger Sharpe je
        Trade``; sie kommt von aussen, aus demselben Grund wie bei ``urteil``.

        Geliefert wird ``(n_eff, Abstand in Reststreuungen)`` oder ``None``,
        wenn die Decke nichts hergibt oder nirgends eine Latte steht.
        """
        if not self.tragfaehig or 1 - self.r**2 <= 1e-12:
            return None
        beste: tuple[int, float] | None = None
        for n in range(von, bis + 1):
            noetig = noetig_je_trade(n)
            if noetig is None:
                continue
            abstand = (noetig - self.vorhersage(n)) / self.reststreuung
            if beste is None or abstand < beste[1]:
                beste = (n, abstand)
        return beste

    def noetige_regeln(self, schwelle: float = MINDEST_T) -> int:
        """Wie viele Regeln eine Gruppe braucht, um **diese** Kopplung zu
        zeigen.

        ``t = r * sqrt((n - 2) / (1 - r^2))``, nach ``n`` aufgeloest. Die
        Zahl beantwortet die Frage, die ein leeres Ergebnis offenlaesst: Hat
        die Gruppe nichts gefunden, oder konnte sie nichts finden?

        **Ohne sie zaehlt Abwesenheit von Beleg als Beleg** - genau das ist
        beim ersten Anlauf zu Befund 181 passiert. Zwei von drei Einteilungen
        meldeten "die Mehrheitsfamilie traegt es allein", weil ihre
        Aussenmenge drei bzw. eine Regel hatte.
        """
        if self.r == 0:
            return 0
        return math.ceil(2 + schwelle**2 * (1 - self.r**2) / self.r**2)

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


def preisurteil(
    decke: Decke, noetig_je_trade, *, versuche: int, bestand: float | None = None
) -> str:
    """Was die Menge kostet - der zweite Weg zur selben Aussage.

    Befund 178 hat das Mengentor geoeffnet: dieselbe Qualitaet bei groesserer
    Stichprobe genuegt ebenso wie bessere Qualitaet bei gleicher. Es steht
    aber unter *"bei unveraenderter Qualitaet"*, und in einem Vorrat mit
    Kopplung ist das keine freie Wahl. Diese Rechnung sagt, was daraus wird.
    """
    treffer = decke.noetiger_abstand(noetig_je_trade)
    if treffer is None:
        return (
            "**Kein Preis ablesbar** - ohne tragfaehige Decke gibt es keine "
            "Gerade, ueber der etwas liegen koennte."
        )
    n, abstand = treffer
    auswahl = Decke.erwartetes_maximum(versuche)
    zeilen = [
        f"**Die guenstigste Stelle der Strecke liegt bei n_eff {n}.** Dort "
        f"muesste eine Regel {abstand:.2f} Reststreuungen ueber der Geraden "
        f"ihrer eigenen Familie liegen, um die Schwelle zu raeumen.",
        f"Zum Vergleich: Auswahl aus {versuche} Ziehungen erzeugt allein "
        f"schon rund {auswahl:.2f}.",
    ]
    if bestand is not None:
        zeilen.append(
            f"Der Bestand steht bei {bestand:+.2f} - er braeuchte das "
            f"{abstand / bestand:.1f}-fache, wenn er dort stuende."
            if bestand > 0
            else f"Der Bestand steht bei {bestand:+.2f}, also unter seiner "
            f"eigenen Geraden."
        )
    zeilen.append(
        "**Das Mengentor ist damit nicht die billigere Haelfte.** Der noetige "
        "Abstand hat sein Minimum und steigt nach beiden Seiten: Mehr Trades "
        "senken zwar die Latte je Trade, kosten in diesem Vorrat aber mehr "
        "Qualitaet, als sie sparen."
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


#: Die drei Ausgaenge einer Einteilung - und der dritte ist der Punkt.
TRAEGT = "traegt allein"
TRAEGT_NICHT = "traegt nicht allein"
UNGEPRUEFT = "nicht geprueft"


def befund_der_einteilung(
    aufteilung: tuple[str, Decke | None, Decke | None] | None,
) -> str:
    """Was eine Einteilung ueber "eine Familie traegt es" sagt.

    Drei Ausgaenge, und der dritte fehlte im ersten Anlauf:

    * ``TRAEGT`` - drinnen belegt, draussen nicht, **und draussen stehen
      genug Regeln**, um es zu zeigen, wenn es da waere.
    * ``TRAEGT_NICHT`` - draussen faellt die Qualitaet ebenso.
    * ``UNGEPRUEFT`` - draussen stehen zu wenige Regeln. Dann ist nichts
      gefunden worden, weil nichts gesucht werden konnte.

    Ohne den dritten zaehlt eine zu kleine Aussenmenge als Bestaetigung, und
    je feiner man schneidet, desto sicherer wird der Befund. Das ist keine
    Robustheitspruefung, sondern ihr Gegenteil.
    """
    if aufteilung is None:
        return UNGEPRUEFT
    _, drin, ohne = aufteilung
    if drin is None or not drin.tragfaehig:
        return TRAEGT_NICHT
    if ohne is None or len(ohne.punkte) < drin.noetige_regeln():
        return UNGEPRUEFT
    return TRAEGT_NICHT if ohne.tragfaehig else TRAEGT


@dataclass(frozen=True, slots=True)
class Einteilung:
    """Eine Art, dieselben Punkte in Familien zu schneiden."""

    name: str
    aufteilung: tuple[str, Decke | None, Decke | None] | None

    @property
    def befund(self) -> str:
        return befund_der_einteilung(self.aufteilung)

    @property
    def traegt_allein(self) -> bool:
        return self.befund == TRAEGT


def stabilitaetsurteil(einteilungen: list[Einteilung]) -> str:
    """Haengt "eine Familie traegt es" an der Art, Familien zu schneiden?

    **Die Gegenprobe zu Befund 169, und sie hat gefehlt.** Dort wurde nach
    dem Einstiegsindikator eingeteilt - strukturell aus dem Genom gelesen und
    insofern keine Meinung. Aber es ist **eine** Einteilung unter mehreren:
    ``sma``, ``ema`` und ``distance_to_ema_pct`` sind drei Schluessel und ein
    Gedanke. Wer sie zusammenlegt, bekommt eine andere Mehrheit.

    Befund 83 hat unabhaengig davon eine Einteilung nach Regellogik gebaut
    und gegen eine Permutation geprueft. Sie auf dieselben Punkte zu legen
    kostet nichts und beantwortet die Frage, ob der Befund an der Sache haengt
    oder am Schnitt.
    """
    if not einteilungen:
        return "**Keine Einteilung** - ohne Gruppierung gibt es nichts zu vergleichen."
    zeilen = ["Traegt die Mehrheitsfamilie die Kopplung - je nach Schnitt?"]
    for e in einteilungen:
        if e.aufteilung is None:
            zeilen.append(f"  {e.name:<24} keine Mehrheitsfamilie ({UNGEPRUEFT})")
            continue
        name, drin, ohne = e.aufteilung
        teile = [
            "drin -" if drin is None else f"drin {len(drin.punkte)}/t={drin.t:+.2f}",
            "ohne -"
            if ohne is None
            else f"ohne {len(ohne.punkte)}/t={ohne.t:+.2f}",
        ]
        if drin is not None and drin.tragfaehig:
            teile.append(f"noetig aussen {drin.noetige_regeln()}")
        zeilen.append(
            f"  {e.name:<24} '{name}'  {'  '.join(teile)}   **{e.befund}**"
        )
    geprueft = [e for e in einteilungen if e.befund != UNGEPRUEFT]
    dafuer = sum(1 for e in geprueft if e.traegt_allein)
    zeilen.append("")
    if not geprueft:
        zeilen.append(
            f"**Keiner der {len(einteilungen)} Schnitte hat es geprueft.** In "
            f"jedem war die Aussenmenge zu klein, um eine Kopplung dieser "
            f"Staerke zu zeigen - gefunden wurde nichts, weil nichts gesucht "
            f"werden konnte."
        )
    elif dafuer == len(geprueft):
        zeilen.append(
            f"**{dafuer} von {len(geprueft)} pruefbaren Schnitten "
            f"{'sagt' if len(geprueft) == 1 else 'sagen'} dasselbe**"
            + (
                f" ({len(einteilungen) - len(geprueft)} konnten es nicht "
                f"pruefen)."
                if len(geprueft) < len(einteilungen)
                else "."
            )
        )
    elif dafuer == 0:
        zeilen.append(
            f"**Kein pruefbarer Schnitt stuetzt es** ({len(geprueft)} von "
            f"{len(einteilungen)} konnten pruefen). Die Aussage gehoert dann "
            f"nicht in einen Befund."
        )
    else:
        zeilen.append(
            f"**{dafuer} von {len(geprueft)} pruefbaren Schnitten stuetzen "
            f"es.** Damit haengt die Aussage am Schnitt, und wer sie zitiert, "
            f"muss dazusagen, nach welcher Einteilung."
        )
    if len(geprueft) < len(einteilungen):
        zeilen.append(
            "Ein Schnitt mit zu kleiner Aussenmenge zaehlt hier **nicht** als "
            "Bestaetigung. Sonst wuerde der Befund umso sicherer, je feiner "
            "man schneidet - das Gegenteil einer Robustheitspruefung."
        )
    return "\n".join(zeilen)


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
    "TRAEGT",
    "TRAEGT_NICHT",
    "UNGEPRUEFT",
    "Decke",
    "Einteilung",
    "Punkt",
    "baue",
    "befund_der_einteilung",
    "familienurteil",
    "preisurteil",
    "stabilitaetsurteil",
    "traegt_eine_familie",
    "urteil",
]
