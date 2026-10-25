"""Wie viel von der Gate-Zahl haengt an der **Aufteilung**?

Woher die Frage kommt
---------------------
Befund 396 hat gemessen, dass ein Schnitt am Reihenanfang die
Walk-Forward-Aufteilung verschiebt und die Strategie **im selben Fenster**
andere Trades macht. Die ganze Zulassungsstrecke steht auf **einer**
Aufteilung - der, die sich aus dem Reihenanfang ergibt. Was daran haengt,
stand nirgends.

Die Bauart, aus der es folgt
----------------------------
``run_walkforward`` verankert die Fenster am Anfang::

    start = frame["open_time"].iloc[0].to_pydatetime()
    windows = splitter.split(start, end)

Ein Balken weniger am Anfang verschiebt also **jede** Fenstergrenze um einen
Tag. Und ohne ``durchgehend=True`` ueberlebt keine Position eine
Fenstergrenze - der Kopf dort sagt es selbst: *"Positionen ueberleben die
Fenstergrenze, so wie im Betrieb"* gilt nur im durchgehenden Modus. Die
Zulassung laeuft im anderen.

Was gemessen ist (Befund 400)
-----------------------------
Spitzenkandidat, Spot-Punkt, Zulassungsreihe, je ein Balken weniger am
Anfang - alle elf Laeufe haben **32 Fenster**, und die weggelassenen Balken
liegen im ersten **Trainings**fenster, werden also nie gehandelt:

    weg   fertig     CAGR   Rueckgang
      0      156   14,3391     9,869
      1      154   15,1845     9,969
      2      154   16,6152     9,768
      3      156   16,8168    10,031
      4      155   16,9336    10,281
      5      153   17,3779     9,952
      6      156   16,8754    10,426
      7      156   16,5358    10,426
      8      155   15,9289    10,426
      9      156   16,6103    10,426
     10      152   17,4522     9,724

**3,1130 Punkte Jahresrendite** zwischen bestem und schlechtestem Lauf
(Streuung 0,9379). Zum Vergleich: Dem Kandidaten fehlen **0,661** Punkte zur
Betriebsschwelle. Der Abstand zum Gate ist ein Fuenftel der Streuung des
Verfahrens.

Dasselbe **hinten** abgeschnitten aendert gar nichts - CAGR 14,3391 auf vier
Stellen, 156 Trades, 9,869 Rueckgang, fuer alle zehn Laeufe. Das ist die
Gegenprobe zur Bauart: Die Fenster haengen am Anfang, nicht am Ende.

Ueber 0 bis 30 Tage, in Zweierschritten gemessen, bewegt sich alles mit:

    Groesse                   min       max    Spanne   Streuung
    fertige Trades          149,0     156,0       7,0        2,6
    Guete je Trade         0,2702    0,2808    0,0105     0,0037
    Deflated Sharpe        0,5698    0,6678    0,0980     0,0317
    Drawdown               9,4623   10,5977    1,1354     0,3775
    Schlechtestes Jahr    -10,3400   -8,9600    1,3800     0,4300
    Out-of-Sample-Sharpe   1,5712    1,7445    0,1733     0,0510
    Bestaendigkeit         0,5161    0,6129    0,0968     0,0233
    Regime-Aufteilung      4,6919    5,3913    0,6994     0,2409
    bestandene Gates         9,00     10,00      1,00       0,50

**Die Gate-Zahl selbst schwankt zwischen 9 und 10.** Die Messlatte-Spalte
fehlt in dieser Tabelle mit Absicht: Sie traegt zwei verschiedene Groessen,
weil das Gate bei Versatz 0 an der Betriebsschwelle haengt und sonst an der
heruntergefahrenen Messlatte (Befund 395). Genau der Fall, den 395
vorhergesagt hat, liegt zwei Tage neben dem gemeldeten Lauf.

Der Mechanismus, gegengeprueft
------------------------------
Im durchgehenden Modus, in dem Positionen die Grenze ueberleben, sind es
**98 fertige Trades bei jedem Versatz** - nicht 152 bis 156 -, und die
Streuung der Jahresrendite faellt von 3,1130 auf 1,5189 Punkte.

**Hier stand eine falsche Erklaerung** (Befund 403): *"Rund 58 der gemeldeten
156 Trades sind Grenzartefakte: Positionen, die am Fensterende geschlossen und
danach neu eroeffnet werden."* Das war aus der Zahlendifferenz geschlossen, und
es ist widerlegt - **kein einziger** Trade steigt an einem Fensterende aus, es
gibt null zerschnittene Paare, und die Einstiege haeufen sich an keinem
Fensteranfang. Die Differenz kommt von den **Risikogrenzen**, die je Fenster
ihre Vorgeschichte verlieren; die Zahlen stehen in Befund 403.

Und die unbequeme Haelfte derselben Messung: Der durchgehende Modus ist auf
jedem blockierenden Gate **schlechter**. Am Spot-Punkt, Versatz 0:

    Groesse                je Fenster   durchgehend
    fertige Trades               156            98
    Guete je Trade            0,2708        0,2600
    Jahresrendite            14,3390       11,6270
    Deflated Sharpe           0,5826        0,3185
    Monte-Carlo                8,3265       15,5363   (Schwelle 15, faellt)
    Schlechtestes Jahr        -9,6100       -5,5800
    Rueckgang                  9,8687        7,5044
    bestandene Gates             9/11          8/11

Was daraus folgt - und was nicht
--------------------------------
**Nicht**, dass der Kandidat besteht. Bei Versatz 0 hat er die niedrigste
Jahresrendite aller elf Laeufe und ist der einzige unter der Schwelle; sich
einen anderen Versatz auszusuchen waere genau das Lockern, gegen das die
Zulassungsstrecke gebaut ist. Die Zahl wird nicht besser, weil man sie anders
ausschneidet.

**Nicht**, dass der Modus zu wechseln ist. Welcher Modus die Zulassung
tragen soll, aendert jede Zahl dieses Projekts und ist eine Entscheidung des
Nutzers, keine Messung.

**Sondern**: Ein Urteil, dessen Abstand zur Schwelle kleiner ist als die
Streuung des Verfahrens, ist kein Urteil. Das gilt in beide Richtungen - es
macht ein gefallenes Gate nicht harmloser und ein bestandenes nicht
sicherer. ``deckt`` ist die Frage dazu, und sie gehoert an jede Stelle, die
einen Abstand zu einer Schwelle meldet.

Rueckwirkend trifft es die eigene Arbeit: Die **0,39 Punkte Reserve** des
Jahres-Gates, um die es in den Befunden 395 bis 397 ging, liegen innerhalb
dieser Streuung (1,38 Punkte Spanne, 0,43 Streuung). Drei Durchgaenge an einer
Groesse, die kleiner ist als das Rauschen des Verfahrens, das sie erzeugt.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

__all__ = [
    "BINDENDE_EINTEILUNG_JE_AUFTEILUNG",
    "RANG_JE_GATE",
    "STICHPROBE_JE_AUFTEILUNG",
    "VERSATZ",
    "Aufteilungsstreuung",
    "beurteile",
    "hoeher_ist_besser",
    "rang_des_gemeldeten",
    "rangzeile",
    "streuung",
]

#: Was ``beurteile`` zurueckgibt.
ENTSCHIEDEN = "entschieden"
OFFEN = "offen"
ZWEI_GROESSEN = "zwei Groessen"

#: Die Versaetze, auf denen Befund 400 gemessen hat - ein Balken je Schritt.
#: Mehr als zehn Tage waeren nicht mehr dieselbe Frage: Dann bewegt sich auch
#: der Reihenanfang merklich, und das ist der Effekt aus ``reichweite``.
VERSATZ: tuple[int, ...] = tuple(range(11))


@dataclass(frozen=True, slots=True)
class Aufteilungsstreuung:
    """Eine Groesse, auf mehreren Aufteilungen gemessen."""

    name: str
    werte: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.werte) < 2:
            raise ValueError(
                f"{self.name}: Streuung aus {len(self.werte)} Wert(en) ist keine "
                f"Streuung - es braucht mindestens zwei Aufteilungen."
            )

    @property
    def spanne(self) -> float:
        return max(self.werte) - min(self.werte)

    @property
    def streuung(self) -> float:
        return statistics.stdev(self.werte)

    @property
    def mittel(self) -> float:
        return statistics.fmean(self.werte)

    def deckt(self, abstand: float) -> bool:
        """Liegt ein Abstand zur Schwelle **innerhalb** dieser Streuung?

        ``abstand`` ist der Betrag; das Vorzeichen entscheidet nichts, weil
        die Frage in beide Richtungen dieselbe ist (Befund 400). Verglichen
        wird mit der **Spanne**, nicht mit der Standardabweichung: Die Spanne
        ist, was tatsaechlich gemessen wurde, und bei elf Laeufen ist sie die
        ehrlichere Zahl.

        Ein gedeckter Abstand heisst **nicht**, dass das Gate anders
        ausfaellt. Er heisst, dass dieser Lauf es nicht entscheidet.
        """
        return abs(abstand) <= self.spanne

    def zeile(self) -> str:
        return (
            f"{self.name:22} {min(self.werte):10.4f} {max(self.werte):10.4f} "
            f"{self.spanne:10.4f} {self.streuung:10.4f}"
        )


def streuung(name: str, werte: Sequence[float]) -> Aufteilungsstreuung:
    """Kurzform fuer ``Aufteilungsstreuung(name, tuple(werte))``."""
    return Aufteilungsstreuung(name=name, werte=tuple(float(w) for w in werte))


def beurteile(
    *,
    name: str,
    wert: float,
    schwelle: float,
    werte: Sequence[float],
    bedingungen: Sequence[str] = (),
) -> str:
    """Ist das Urteil dieses Gates entschieden - oder nur eine Ziehung?

    ``werte`` sind dieselbe Groesse auf mehreren Aufteilungen, ``wert`` und
    ``schwelle`` die des gemeldeten Laufs.

    ``bedingungen`` sind die ``GateResult.bedingung`` derselben Laeufe. Sind
    es mehrere, traegt die Spalte zwei verschiedene Groessen (Befund 395) und
    es gibt hier **kein** Urteil - eine Spanne aus Jahres- und Gesamtrendite
    waere eine Zahl ohne Bedeutung. Wer die Messlatte trotzdem beurteilen
    will, nimmt die Jahresrendite selbst: Sie ist ueber alle Aufteilungen
    dieselbe Groesse.

    Gemessen am Spot-Punkt, elf Aufteilungen (Befund 401): **Neun der elf
    Gates sind entschieden**, darunter der Deflated Sharpe mit 0,3674 Abstand
    gegen 0,0763 Spanne - der Hauptblocker ist also keine Aufteilungsfrage.
    Offen sind zwei: 'Schlechtestes Jahr' (0,3900 gegen 0,9500) und die
    Messlatte, deren Jahresrendite 0,661 unter der Schwelle liegt bei 3,1130
    Spanne. Am knappsten entschieden ist 'Bestaendigkeit' - 0,0806 gegen
    0,0645, das 1,25-fache.

    **Und das "entschieden" ist vorlaeufig** (Befund 402). Eine Spanne ueber
    ``n`` Aufteilungen ist eine **Untergrenze** der Spanne: Mehr Aufteilungen
    koennen sie nur vergroessern. Daraus folgt eine Asymmetrie, die beim
    Lesen zaehlt:

    * **"offen" ist monoton.** Was auf elf Aufteilungen offen ist, bleibt es
      auf hundert.
    * **"entschieden" ist es nicht.** Es heisst "auf diesen ``n``
      Aufteilungen entschieden", nicht mehr.

    Und die Falle dabei: Bei **wenigen** Aufteilungen ist die Spanne winzig,
    also liest sich fast alles als entschieden. Zwei Aufteilungen sagen
    beinahe nichts; sie sind nur die Untergrenze, unter der die Frage keinen
    Sinn hat. Wer wenig misst, bekommt viele Urteile und wenig Wissen.

    Gemessen: Bei 31 Versaetzen kippt 'Bestaendigkeit' nach **offen** - 0,0806
    gegen 0,0968 -, und aus "neun von elf" werden acht. Der Deflated Sharpe
    bleibt entschieden (0,3674 gegen 0,0980). Wer die Zahl nennt, nennt die
    Tiefe mit.
    """
    if len(set(bedingungen)) > 1:
        return ZWEI_GROESSEN
    if len(werte) < 2:
        raise ValueError(
            f"{name}: ein Lauf ist keine Streuung - ohne zweite Aufteilung "
            f"gibt es kein Urteil darueber, ob das Urteil eines ist."
        )
    return OFFEN if streuung(name, werte).deckt(wert - schwelle) else ENTSCHIEDEN


@dataclass(frozen=True, slots=True)
class Bandenbild:
    """Streuung **innerhalb** einer Bande gegen Drift **zwischen** den Banden.

    Wer den Versatz weit genug treibt, verschiebt nicht mehr nur die
    Aufteilung, sondern auch den Reihenanfang - und das ist der Effekt aus
    ``reichweite``, nicht der aus Befund 400. Die Zerlegung trennt beides:
    Die Spanne innerhalb einer Zehnerbande ist Aufteilung, die Drift der
    Bandenmittel ist der Anfang.

    Gemessen ueber 31 Versaetze (Befund 402):

        Groesse               Banden max     Drift
        Bestaendigkeit            0,0839    0,0231
        Deflated Sharpe           0,0871    0,0444
        Stichprobengroesse       97,0000  101,9091   <- hier wandert der Anfang

    Bei 'Stichprobengroesse' ueberwiegt die Drift, und das muss sie: Die Zahl
    sind Tage im Markt, und die Reihe wird kuerzer. Dass die Zerlegung das
    zeigt, ist die Gegenprobe darauf, dass sie ueberhaupt trennt.
    """

    name: str
    bandenspannen: tuple[float, ...]
    drift: float

    @property
    def innen(self) -> float:
        """Die groesste Spanne innerhalb einer Bande."""
        return max(self.bandenspannen)

    @property
    def ueberwiegt_die_aufteilung(self) -> bool:
        return self.innen >= self.drift


def banden(name: str, werte: Sequence[float], *, anzahl: int = 3) -> Bandenbild:
    """Die Werte in ``anzahl`` Banden schneiden und beides messen.

    **Die Anzahl, nicht die Breite** (Befund 402). Mein erster Einbau nahm
    eine feste Breite von elf und liess eine unvollstaendige letzte Bande
    weg. Bei 31 Werten blieben damit zwei Banden und **neun Werte fielen
    heraus** - und zwar genau die mit der groessten Spanne, 0,0839 gegen
    0,0645. Die Zahl, auf die es ankam, war die weggelassene.

    Gefunden hat es der eigene datengestuetzte Test, weil er die Zahl aus
    der Messung gegen die Funktion gehalten hat.

    Jetzt wird alles aufgeteilt, in moeglichst gleich grosse Banden ohne
    Ueberlappung: 31 Werte auf drei Banden sind 11, 10, 10. Jede Bande
    braucht mindestens zwei Werte, sonst ist ihre Spanne keine.
    """
    if anzahl < 2:
        raise ValueError("Weniger als zwei Banden trennen nichts.")
    if len(werte) < 2 * anzahl:
        raise ValueError(
            f"{name}: {len(werte)} Werte reichen nicht fuer {anzahl} Banden - "
            f"jede braucht mindestens zwei."
        )
    grenzen = [len(werte) * i // anzahl for i in range(anzahl + 1)]
    stuecke = [list(werte[a:b]) for a, b in pairwise(grenzen)]
    mittel = [statistics.fmean(s) for s in stuecke]
    return Bandenbild(
        name=name,
        bandenspannen=tuple(max(s) - min(s) for s in stuecke),
        drift=max(mittel) - min(mittel),
    )


#: Was sich an der **wirksamen Stichprobe** bewegt, wenn sich nichts bewegt
#: (Befund 418). Elf Aufteilungen, ein Balken Versatz je Schritt, dieselbe
#: Strategie, dieselben Daten - gemessen mit ``cli aufteilung``, das die
#: Groesse seit diesem Befund mitfuehrt.
#:
#: **Das widerlegt eine Behauptung aus Befund 417.** Dort steht, die
#: Stichprobenkorrektur habe "ihr eigenes Rauschen", und es sei "nicht klein
#: gegen die Luecke, die sie misst" - geschlossen aus dreizehn Beobachtungen
#: Unterschied zwischen drei Haltedeckeln. Gemessen bewegt der Versatz die
#: Groesse um **vier** Beobachtungen bei einer Streuung von 1,33. Die
#: dreizehn sind also dreimal die Messstreuung und damit eine **echte**
#: Wirkung des Deckels, kein Rauschen.
#:
#: Der Satz aus 417 war in der bequemen Richtung falsch: Er haette kuenftig
#: jeden Unterschied in der wirksamen Stichprobe als Rauschen abtun lassen.
#: Richtig herum gelesen ist die Zahl brauchbar - ein Unterschied von vier
#: liegt in der Messstreuung, einer von dreizehn nicht.
#:
#: Was 417 **nicht** verliert: den Schluss. Der Gipfel bei vierzig Kerzen
#: bleibt ein ausgewaehlter Extremwert unter sieben probierten, und die
#: beiden Nachbarn bei 0,68 bleiben die bessere Schaetzung. Das Argument ist
#: die **Auswahl**, nicht das Rauschen.
STICHPROBE_JE_AUFTEILUNG: dict[str, float] = {
    "aufteilungen": 11,
    "unten": 115,
    "oben": 119,
    "spanne": 4,
    "streuung": 1.33,
}

#: Und die bindende Einteilung haelt ueber alle elf (Befund 410/418). Auch
#: **woran** die Kuerzung haengt, ist damit keine Frage der Aufteilung.
BINDENDE_EINTEILUNG_JE_AUFTEILUNG = "Kalenderquartal"


def hoeher_ist_besser(wert: float, schwelle: float, bestanden: bool) -> bool:
    """In welche Richtung ein Gate besser wird - aus seinem eigenen Urteil.

    ``GateResult`` sagt es nicht, und eine gepflegte Liste der Richtungen
    waere die naechste Zahl, die wegdriftet (Befund 408). Abgeleitet geht es
    ohne:

    * Ein **bestandenes** Gate liegt auf der guten Seite seiner Schwelle. Ist
      sein Wert groesser, ist gross gut.
    * Ein **gefallenes** liegt auf der schlechten Seite. Ist sein Wert
      kleiner, ist gross gut.

    Nachgeprueft an den elf Gates des massgeblichen Punkts: Drawdown besteht
    mit 9,87 unter 12 - klein ist gut. 'Schlechtestes Jahr' besteht mit -9,61
    ueber -10 - gross ist gut. Der Deflated Sharpe faellt mit 0,5826 unter
    0,95 - gross ist gut. Die Messlatte faellt mit 14,34 unter 15 - gross ist
    gut.
    """
    return wert >= schwelle if bestanden else wert <= schwelle


def rang_des_gemeldeten(
    werte: Sequence[float], *, gross_ist_gut: bool
) -> tuple[int, int, int]:
    """Wo der gemeldete Wert unter allen Aufteilungen steht, vom strengsten.

    Zurueck kommt ``(von, bis, gesamt)``. ``werte[0]`` ist der gemeldete
    (Versatz null). ``von == 1`` heisst: Keine Aufteilung ist strenger - der
    gemeldete Wert ist der unguenstigste. ``bis == gesamt`` heisst: keine ist
    guenstiger.

    Das ist die Frage, die eine Spanne allein nicht beantwortet. Zwei Gates
    mit derselben Spanne stehen verschieden da, wenn das eine am strengen und
    das andere am guenstigen Rand gemeldet wird (Befund 419).

    **Gleichstaende werden als Bereich gemeldet, und das war ein Fehler der
    ersten Fassung.** Sie gab fuer ein Gate mit Spanne null ``1 von 11``
    zurueck - es stand dann da, als werde der strengste von elf Werten
    berichtet, obwohl alle elf gleich sind. Genau die falsche Richtung: Der
    Eindruck war konservativer als die Lage.
    """
    if not werte:
        raise ValueError("ohne Werte gibt es keinen Rang")
    gemeldet = werte[0]
    # Strenger heisst: weiter auf der schlechten Seite. Bei 'gross ist gut'
    # sind das die kleineren Werte, sonst die groesseren.
    if gross_ist_gut:
        strenger = sum(1 for w in werte if w < gemeldet)
    else:
        strenger = sum(1 for w in werte if w > gemeldet)
    gleich = sum(1 for w in werte if w == gemeldet)
    return strenger + 1, strenger + gleich, len(werte)


def rangzeile(werte: Sequence[float], *, gross_ist_gut: bool) -> str:
    """Der Rang als Text - ein Bereich, wo es Gleichstaende gibt."""
    von, bis, gesamt = rang_des_gemeldeten(werte, gross_ist_gut=gross_ist_gut)
    if von == bis:
        return f"{von}/{gesamt}"
    if von == 1 and bis == gesamt:
        return f"alle {gesamt} gleich"
    return f"{von}-{bis}/{gesamt}"


#: Wo der gemeldete Wert jedes Gates in seiner eigenen Spanne steht
#: (Befund 419). Gemessen mit ``cli aufteilung`` ueber die elf Versaetze;
#: Rang 1 heisst "keine Aufteilung ist strenger", Rang 11 "keine ist
#: guenstiger". Ein Bereich steht fuer Gleichstaende.
#:
#: **Warum das neben der Spanne noetig ist.** Die Befunde 400 bis 402 haben
#: aus der Spanne die Urteile 'entschieden' und 'offen' gebaut. Was die
#: Spanne nicht sagt: ob gerade die strenge oder die guenstige Aufteilung
#: berichtet wird. Zwei Gates mit derselben Spanne stehen verschieden da.
#:
#: **Was gemessen ist:**
#:
#: * **Kein systematischer Vorteil.** Die Raenge streuen von 2 bis 9. Der
#:   massgebliche Lauf ist also nicht die guenstige Aufteilung unter elf -
#:   waere er es, stuende hier ueberall eine hohe Zahl.
#: * **Der Deflated Sharpe wird in der Mitte gemeldet** (5 von 11). Der
#:   Ausfall, der das Projekt traegt, ist damit nicht schoengerechnet - und
#:   auch nicht schlechtgerechnet.
#: * **'Schlechtestes Jahr' und 'Drawdown' stehen guenstig** (9 von 11): In
#:   acht der elf Aufteilungen sehen sie schlechter aus als gemeldet. Fuer
#:   das schlechteste Jahr schaerft das die offene Richtung aus Befund 395 -
#:   sein Guthaben von 0,39 Punkten ist nicht nur klein, es ist am
#:   guenstigen Rand gemessen.
#: * **'Out-of-Sample-Sharpe' steht streng** (2 von 11) - nur eine
#:   Aufteilung ist unguenstiger.
RANG_JE_GATE: dict[str, str] = {
    "Stichprobengroesse": "5-11/11",
    "Messlatte": "-",
    "Out-of-Sample-Sharpe": "2/11",
    "Drawdown": "9/11",
    "Schlechtestes Jahr": "9/11",
    "Bestaendigkeit": "4-9/11",
    "Monte-Carlo": "8/11",
    "Regime-Aufteilung": "6/11",
    "Deflated Sharpe": "5/11",
    "Kosten-Stress": "alle 11 gleich",
    "Parameter-Plateau": "alle 11 gleich",
}
