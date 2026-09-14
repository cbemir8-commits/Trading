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
**+0,49** - viel -, aber die Permutationsnull von
``research/unabhaengigkeit.py`` weist sie mit p = 0,0885 nicht nach, und die
groebere Einteilung hat mit sechs Bloecken zu wenige fuer eine Messung
(``MIND_BLOECKE`` ist 8).

Dass dort dann **nicht** gekuerzt wird, ist fuer Trades die vorsichtige Seite:
Wer die Stichprobe nicht kuerzt, macht das Gate strenger. Hier ist es die
andere: Nicht kuerzen heisst kleinere Obergrenze heisst *"die Suche ist
aussichtsloser, als belegt ist"*. **Dieselbe Vorsicht schneidet in die andere
Richtung**, und deshalb steht hier eine Spanne und keine Zahl.

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

__all__ = ["Abstand", "Lage", "lage_aus", "obergrenze_der_quote"]


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
