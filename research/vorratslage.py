"""Der Abstand ohne Gerade - was Befund 285 offengelassen hat.

Die Frage
---------
``cli vorratsdecke`` nannte bis Befund 285 einen **Preis**: Wie weit eine neue
Idee ueber der Geraden ihrer eigenen Familie liegen muesste, um die Schwelle
zu raeumen - 1,68 Reststreuungen bei n_eff 101. Befund 285 hat ihn verweigert,
weil die Gerade an einer einzigen Regel haengt: Ohne 'Momentum Ruecksetzer'
faellt die Kopplung von t = -2,59 auf -0,97 und traegt nicht mehr.

Damit fehlte das Werkzeug, das die Entscheidung traegt: **Lohnt sich ein
Versuch?** Eine Verweigerung allein beantwortet das nicht, und sie stehen zu
lassen hiesse, die Frage dem Gefuehl zu ueberlassen.

Was hier steht, braucht keine Gerade
------------------------------------
Jede Regel des Katalogs hat zwei gemessene Zahlen: ihre Guete und die Latte,
die bei **ihrer** Stichprobe und **ihrer** Verteilungsform gilt. Der
Unterschied ist ihre Luecke - eine Beobachtung, kein Modell.

Aus achtzehn Luecken laesst sich sagen, was aus einer Geraden nicht folgte:

* Wie nah der Vorrat seiner Latte ueberhaupt kommt (die kleinste Luecke).
* Wie diese Luecke im Verhaeltnis zur Streuung des Vorrats selbst steht -
  eine Einheit, die aus den Daten kommt und nicht aus einer Anpassung.
* Wie oft eine Regel dieses Vorrats ihre Latte raeumt - und was daraus fuer
  die **naechste** Ziehung folgt.

Der letzte Punkt ist der, an dem sich eine Suche budgetieren laesst. Null
Treffer aus achtzehn heisst nicht "die Quote ist null": Bei einer wahren Quote
von 10 % waeren achtzehn Fehlschlaege nichts Besonderes (0,9^18 = 15 %). Was
sich sagen laesst, ist eine **Obergrenze** - und die ist eine Zahl, keine
Vermutung.

BERICHTIGT IN BEFUND 287 - die Obergrenze war zu eng
----------------------------------------------------
Befund 286 hat sie auf **achtzehn** Ziehungen gerechnet und damit unterstellt,
dass achtzehn Regeln achtzehn unabhaengige Einfaelle sind. Sie sind es nicht:
Nach Regellogik heissen zwoelf von achtzehn 'Trend', und strukturell nach dem
Einstiegsindikator zerfallen sie in acht Gruppen, nach der groeberen
Einteilung in sechs.

    unabhaengige Ziehungen    Obergrenze bei 95 %
                        18                 15,3 %
                         8                 31,2 %
                         6                 39,3 %
                         2                 77,6 %

Gemessen wurde auch, ob sich die Abhaengigkeit **beziffern** laesst: Ueber die
acht Einstiegsgruppen betraegt die Intraklassenkorrelation der Luecken
**+0,49** - viel -, aber der Designeffekt uebersteigt die Permutationsnull von
``research/unabhaengigkeit.py`` nicht (Faktor 1,0000 bei p = 0,0885), und die
groebere Einteilung hat mit sechs Bloecken zu wenige fuer eine Messung
(``MIND_BLOECKE`` ist 8).

BERICHTIGT IN BEFUND 289 - die Begruendung war verkehrt herum
-------------------------------------------------------------
Hier stand: *"Dass dort nicht gekuerzt wird, ist fuer Trades die vorsichtige
Seite: Wer die Stichprobe nicht kuerzt, macht das Gate strenger."* **Das ist
falsch, und zwar genau andersherum.** Gemessen am Bestand (SR je Trade
0,2708, Latte auf seinen eigenen Momenten, 203 Versuche):

    n_eff    Guete    Latte   besteht
       115   2,904    3,618   nein
       150   3,317    3,677   nein
       200   3,830    3,745   **ja**

Die Guete waechst mit ``sqrt(n)``, die Latte nur langsam. Eine **groessere**
Stichprobe macht das Gate also **leichter**, eine Kuerzung macht es strenger -
so steht es auch im Docstring von ``effektive_stichprobe``: *"Das kann die
Zulassung nur erschweren, nie erleichtern."*

Damit wird die Aussage nicht schwaecher, sondern schaerfer. Dieselbe Vorgabe
zieht an beiden Stellen **in dieselbe Richtung**:

    beim Gate            nicht kuerzen -> grosses n -> der Bestand sieht
                         besser aus, als belegt ist
    bei dieser Grenze    nicht kuerzen -> grosses n -> die Suche sieht
                         aussichtsloser aus, als belegt ist

Zweimal zugunsten des Vorhandenen und gegen einen neuen Versuch. Deshalb steht
hier eine Spanne und keine Zahl - und deshalb waehlt ``effektive_stichprobe``
beim Gate ausdruecklich die **strengste** gemessene Einteilung.

Was hier **nicht** steht
------------------------
* Kein Ersatz fuer die Gerade. Die Kopplung zwischen Menge und Qualitaet ist
  eine Aussage ueber den Vorrat, die Luecke ist eine Aussage ueber jede Regel
  einzeln. Wo die Gerade traegt, sagt sie mehr; hier traegt sie nicht.
* Keine Aussage ueber den Raum aller Strategien. Gemessen ist ein vorhandener
  Katalog - derselbe Vorbehalt wie in ``vorratsdecke``.
* Keine Empfehlung, eine Latte zu senken. Die Obergrenze der Trefferquote ist
  ein Grund, den Vorrat zu wechseln oder die Suche zu beenden, und keiner,
  die Schwelle zu bewegen.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

#: Ab welchem |t| dieses Modul eine Korrelation als belegt ansieht.
#:
#: Dieselbe Schwelle wie in ``vorratsdecke``, ``rangtreue`` und
#: ``verbund`` (Befund 75). Sie steht hier noch einmal, damit das Urteil
#: keine eigene erfindet.
MINDEST_T: float = 2.0

__all__ = [
    "Abstand",
    "Lage",
    "Rangbild",
    "Rangzug",
    "lage_aus",
    "obergrenze_der_quote",
    "rangbild",
]


def obergrenze_der_quote(
    versuche: int, treffer: int = 0, *, vertrauen: float = 0.95
) -> float | None:
    """Die hoechste Trefferquote, die zu ``treffer`` von ``versuche`` passt.

    Nur fuer ``treffer = 0`` - der Fall, um den es geht, und der einzige, in
    dem die Rechnung in einer Zeile steht: Eine wahre Quote ``p`` liefert
    ``(1 - p)^n`` mal keinen Treffer; die Obergrenze ist das ``p``, bei dem
    das gerade noch ``1 - vertrauen`` betraegt.

    **Sie ersetzt den Satz "keine von achtzehn, also gibt es nichts".** Der
    ist falsch und in diesem Projekt schon einmal teuer gewesen: Befund 75
    hat aus fuenf Punkten geschlossen, und Befund 181 hat gezeigt, dass eine
    zu kleine Aussenmenge als Bestaetigung zaehlte, je feiner man schnitt.
    Abwesenheit von Beleg ist kein Beleg - aber sie ist auch nicht nichts,
    und diese Zahl sagt, wie viel sie ist.
    """
    if treffer != 0:
        raise ValueError(
            "Nur der trefferlose Fall - bei Treffern gehoert eine richtige "
            "Intervallrechnung her und keine Einzeiler-Naeherung."
        )
    if versuche < 1:
        return None
    if not 0.0 < vertrauen < 1.0:
        raise ValueError(f"Vertrauen {vertrauen} liegt nicht zwischen 0 und 1.")
    return 1.0 - (1.0 - vertrauen) ** (1.0 / versuche)


@dataclass(frozen=True, slots=True)
class Abstand:
    """Eine gemessene Regel und die Latte, die fuer **sie** gilt."""

    name: str
    n_eff: int
    guete: float
    noetig: float

    @property
    def luecke(self) -> float:
        """Was fehlt - positiv heisst "darunter"."""
        return self.noetig - self.guete

    @property
    def geraeumt(self) -> bool:
        return self.luecke <= 0

    @property
    def anteil(self) -> float:
        """Die Guete als Anteil ihrer Latte - skalenfrei.

        Zwei Regeln koennen dieselbe Luecke haben und verschieden weit weg
        sein: 2,4 gegen 3,5 ist etwas anderes als 12,4 gegen 13,5.
        """
        return self.guete / self.noetig if self.noetig else 0.0


@dataclass(frozen=True, slots=True)
class Lage:
    """Was achtzehn Luecken sagen - ohne dass eine Gerade dabei waere."""

    abstaende: tuple[Abstand, ...]

    def __post_init__(self) -> None:
        if not self.abstaende:
            raise ValueError("Ohne gemessene Regeln gibt es keine Lage.")

    @property
    def naechster(self) -> Abstand:
        """Die Regel, die ihrer eigenen Latte am naechsten kommt."""
        return min(self.abstaende, key=lambda a: a.luecke)

    @property
    def luecken(self) -> list[float]:
        return [a.luecke for a in self.abstaende]

    @property
    def median(self) -> float:
        return statistics.median(self.luecken)

    @property
    def streuung(self) -> float | None:
        """Wie breit die Gueten dieses Vorrats streuen.

        **Die Einheit, in der eine Luecke lesbar wird** - und sie kommt aus
        den Daten, nicht aus einer Anpassung. Unter zwei Regeln gibt es sie
        nicht.
        """
        if len(self.abstaende) < 2:
            return None
        return statistics.stdev([a.guete for a in self.abstaende])

    @property
    def in_streuungen(self) -> float | None:
        """Die kleinste Luecke, gemessen an der Streuung des Vorrats.

        Das Gegenstueck zum Preis aus Befund 179 - dieselbe Frage, andere
        Grundlage: dort der Abstand zu einer angepassten Geraden, hier zur
        Breite des Vorrats selbst.
        """
        streuung = self.streuung
        if streuung is None or streuung <= 0:
            return None
        return self.naechster.luecke / streuung

    @property
    def geraeumt(self) -> tuple[Abstand, ...]:
        return tuple(a for a in self.abstaende if a.geraeumt)

    def obergrenze(
        self, vertrauen: float = 0.95, *, unabhaengige: int | None = None
    ) -> float | None:
        """Wie hoch die Trefferquote dieses Vorrats hoechstens liegt.

        ``unabhaengige`` ist die Zahl der **unabhaengigen Ziehungen**. Ohne
        Angabe ist das die Zahl der Regeln - und genau darin lag der Fehler
        von Befund 286: Achtzehn Regeln sind keine achtzehn unabhaengigen
        Ziehungen, wenn zwoelf davon 'Trend' heissen.

        ``None``, sobald eine Regel ihre Latte raeumt - dann ist die Quote zu
        schaetzen und nicht nach oben abzugrenzen, und eine Obergrenze waere
        die falsche Auskunft.
        """
        if self.geraeumt:
            return None
        anzahl = len(self.abstaende) if unabhaengige is None else unabhaengige
        return obergrenze_der_quote(anzahl, 0, vertrauen=vertrauen)

    def urteil(self, *, vertrauen: float = 0.95, gruppen: int | None = None) -> str:
        naechster = self.naechster
        zeilen = [
            f"**Am naechsten kommt '{naechster.name}'** bei n_eff "
            f"{naechster.n_eff}: Guete {naechster.guete:.3f} gegen eine Latte "
            f"von {naechster.noetig:.3f}, es fehlen {naechster.luecke:.3f}.",
        ]
        anteile = self.in_streuungen
        if anteile is not None:
            zeilen.append(
                f"Das sind {anteile:.2f} Streuungen dieses Vorrats "
                f"({self.streuung:.3f} Guetepunkte), und der Median aller "
                f"{len(self.abstaende)} Luecken liegt bei {self.median:.3f}."
            )
        if self.geraeumt:
            namen = ", ".join(a.name for a in self.geraeumt)
            zeilen.append(
                f"**{len(self.geraeumt)} von {len(self.abstaende)} raeumen "
                f"ihre Latte** ({namen}) - hier steht keine Obergrenze, hier "
                f"ist zu pruefen."
            )
            return "\n".join(zeilen)
        eng = self.obergrenze(vertrauen)
        if eng is None:
            zeilen.append(f"**Keine von {len(self.abstaende)} raeumt ihre Latte.**")
            return "\n".join(zeilen)
        zeilen.append(
            f"**Keine von {len(self.abstaende)} raeumt ihre Latte.** Das "
            f"heisst nicht, dass die Quote null ist: Bei {vertrauen:.0%} "
            f"Vertrauen liegt sie hoechstens bei {eng:.1%}, **wenn** die "
            f"{len(self.abstaende)} Regeln {len(self.abstaende)} "
            f"unabhaengige Ziehungen sind."
        )
        weit = (
            self.obergrenze(vertrauen, unabhaengige=gruppen)
            if gruppen is not None and 0 < gruppen < len(self.abstaende)
            else None
        )
        if weit is not None:
            zeilen.append(
                f"Sie sind es nicht: Strukturell zerfallen sie in {gruppen} "
                f"Gruppen, und auf denen gerechnet steht dort {weit:.1%}. "
                f"**Die ehrliche Auskunft ist die Spanne** - zwischen "
                f"{eng:.1%} und {weit:.1%}, je nachdem, wie viel Eigenes in "
                f"einer Regel steckt, die eine Abwandlung ihrer Nachbarin ist."
            )
        zeilen.append(
            "**Das ist eine Aussage ueber diesen Vorrat, nicht ueber den Raum "
            "aller Strategien** - und kein Grund, eine Latte zu senken."
        )
        return "\n".join(zeilen)


@dataclass(frozen=True, slots=True)
class Rangzug:
    """Eine Rangkorrelation und was aus ihr wird, wenn eine Regel fehlt.

    **Rang statt Gerade** (Befund 290). Befund 285 hat die angepasste Gerade
    durch denselben Vorrat verworfen, weil ein einziger Punkt sie loescht.
    Eine Rangkorrelation hat diese Schwaeche nicht: Sie sieht nur die
    Reihenfolge, und ein Punkt ganz rechts unten ist dort ein Rang wie jeder
    andere.
    """

    rho: float
    t: float
    schwaechster: str
    t_schwaechster: float
    staerkster: str
    t_staerkster: float
    haltende_auslassungen: int
    auslassungen: int

    @property
    def traegt(self) -> bool:
        return abs(self.t) >= MINDEST_T

    @property
    def fest(self) -> bool:
        """Traegt sie **jede** einzelne Auslassung?"""
        return self.traegt and self.haltende_auslassungen == self.auslassungen

    @property
    def durchweg_leer(self) -> bool:
        """Und die Gegenrichtung: Traegt sie unter **keiner**?

        Das ist etwas anderes als "nicht belegt". Eine Korrelation, die auch
        dann nichts zeigt, wenn man den unguenstigsten Punkt entfernt, ist
        nicht knapp gescheitert - sie ist nicht da.
        """
        return not self.traegt and self.haltende_auslassungen == 0


def _rangzug(namen: Sequence[str], x: Sequence[float], y: Sequence[float]):
    from research.rangtreue import rangkorrelation, t_wert

    rho = rangkorrelation(list(x), list(y))
    if rho is None:
        return None
    t = t_wert(rho, len(x))
    if t is None:
        return None

    ohne: list[tuple[float, str, float]] = []
    for i in range(len(x)):
        xx = [x[j] for j in range(len(x)) if j != i]
        yy = [y[j] for j in range(len(y)) if j != i]
        r = rangkorrelation(xx, yy)
        if r is None:
            continue
        tt = t_wert(r, len(xx))
        if tt is not None:
            ohne.append((abs(tt), namen[i], tt))
    if not ohne:
        return None
    ohne.sort()
    return Rangzug(
        rho=rho,
        t=t,
        schwaechster=ohne[0][1],
        t_schwaechster=ohne[0][2],
        staerkster=ohne[-1][1],
        t_staerkster=ohne[-1][2],
        haltende_auslassungen=sum(1 for k, _, _ in ohne if k >= MINDEST_T),
        auslassungen=len(ohne),
    )


@dataclass(frozen=True, slots=True)
class Rangbild:
    """Haengt die Guete an der Trade-Zahl - oder nur die Qualitaet je Trade?

    **Die Frage, an der das Mengentor haengt** (Befund 178/179). Dort stand:
    Mehr Beobachtungen bei gleicher Qualitaet genuegen ebenso wie bessere
    Qualitaet bei gleicher Zahl - aber *"die Qualitaet haelt in diesem Vorrat
    nicht"*. Belegt war das ueber den Preis in Reststreuungen, also ueber die
    Gerade aus Befund 285.

    Beurteilt wird im Gate aber nicht die Qualitaet je Trade, sondern die
    **Guete**: ``SR * sqrt(n)``. Ob die an der Menge haengt, ist eine eigene
    Frage, und sie ist hier zum ersten Mal einzeln gestellt.
    """

    je_trade: Rangzug
    guete: Rangzug

    def urteil(self) -> str:
        zeilen = []
        if self.je_trade.traegt:
            zeilen.append(
                f"**Die Qualitaet je Trade faellt mit der Menge** "
                f"(rho = {self.je_trade.rho:+.3f}, t = {self.je_trade.t:+.2f})"
                + (
                    f", und zwar unter jeder Auslassung - die schwaechste "
                    f"laesst t = {self.je_trade.t_schwaechster:+.2f} stehen."
                    if self.je_trade.fest
                    else f"; ohne '{self.je_trade.schwaechster}' bleibt "
                    f"t = {self.je_trade.t_schwaechster:+.2f}."
                )
            )
        else:
            zeilen.append(
                f"Die Qualitaet je Trade haengt nicht messbar an der Menge "
                f"(rho = {self.je_trade.rho:+.3f}, t = {self.je_trade.t:+.2f})."
            )
        if self.guete.traegt:
            zeilen.append(
                f"**Und die Guete haengt mit** (rho = {self.guete.rho:+.3f}, "
                f"t = {self.guete.t:+.2f}) - dann ist die Menge selbst ein "
                f"Hebel, in die eine oder andere Richtung."
            )
        else:
            zeilen.append(
                f"**Die Guete haengt nicht daran** (rho = "
                f"{self.guete.rho:+.3f}, t = {self.guete.t:+.2f}; unter "
                f"{self.guete.auslassungen} Auslassungen raeumt "
                f"{self.guete.haltende_auslassungen} die Schwelle). Die "
                f"Wurzel aus der Stichprobe nimmt zurueck, was die Qualitaet "
                f"je Trade verliert."
            )
            zeilen.append(
                "Fuer das Mengentor heisst das: Es ist nicht zu, weil die "
                "Qualitaet zusammenbricht - sie tut es in der Guete nicht -, "
                "sondern weil die **Latte** mit der Stichprobe steigt. Das "
                "ist ein viel kleinerer Effekt, und er ist kein Weg zu einer "
                "Zulassung: Was fehlt, fehlt an der Guete."
            )
        return "\n".join(zeilen)


def rangbild(abstaende: Sequence[Abstand]) -> Rangbild | None:
    """Beide Rangkorrelationen samt Auslassungsprobe.

    ``None``, wenn sich keine rechnen laesst - unter drei Regeln gibt es
    keine Rangfolge, die etwas sagt.
    """
    liste = [a for a in abstaende if a.n_eff > 0]
    if len(liste) < 4:
        return None
    namen = [a.name for a in liste]
    n_eff = [float(a.n_eff) for a in liste]
    guete = [a.guete for a in liste]
    je_trade = [a.guete / a.n_eff**0.5 for a in liste]

    erste = _rangzug(namen, n_eff, je_trade)
    zweite = _rangzug(namen, n_eff, guete)
    if erste is None or zweite is None:
        return None
    return Rangbild(je_trade=erste, guete=zweite)


def lage_aus(abstaende: Sequence[Abstand]) -> Lage | None:
    """Eine Lage, wo es Messungen gibt - sonst nichts.

    **Die Latten kommen von aussen und werden hier nicht gerechnet.** Der
    Bericht stellt sie ohnehin schon Regel fuer Regel auf, mit der
    Verteilungsform **dieser** Regel (Befund 191); sie hier ein zweites Mal
    zu rechnen hiesse, zwei Quellen fuer dieselbe Zahl zu pflegen. Genau
    davon handeln die Befunde 158, 159 und 165 - und bei den Vorgabemomenten
    waere der Unterschied sichtbar: Fuer 'Donchian-Ausbruch 55/20' stuende
    3,524 statt 3,564 da.
    """
    return Lage(tuple(abstaende)) if abstaende else None
