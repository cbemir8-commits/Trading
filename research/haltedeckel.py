"""Was ein Haltedauer-Deckel am massgeblichen Punkt tut - Befund 416.

Befund 177 hat vier Deckel auf **gepflanzten** Trends gemessen und eine klare
Antwort bekommen: Keiner entkoppelt die Trade-Zahl von der Trendstaerke, die
beste Steigung lag bei 0,36 gegen die geforderten 0,5. Der Eintrag dazu steht
seit 238 Befunden in ``OFFEN``, und er ist der einzige dort ohne Nachmessung -
zu Recht, denn das Ergebnis war eindeutig.

Nie gemessen war, was ein Deckel auf der **echten** Zulassungsreihe mit dem
massgeblichen Kandidaten tut. Daran haengt die Mengen-Route zum Deflated
Sharpe: Dem Gate fehlen rund 75 wirksame Beobachtungen, und der Lagebericht
sagt dazu seit Befund 179, Qualitaet und Menge seien gekoppelt.

Was gemessen ist
----------------
Sechs Deckel, dieselbe Reihe, derselbe Kandidat, dieselben elf Gates. Deckel 0
trifft ``research.referenz``.SPOTPUNKT auf die Stelle - 156 fertige Trades,
n_eff 115, DSR 0,5826, neun von elf -, und das ist die Gegenprobe, ohne die
die Tabelle nichts wert waere.

**Es ist kein Mengeneffekt.** Die Zahl der fertigen Trades bleibt zwischen 156
und 158, bei jedem Deckel. Die Vorstellung, ein frueherer Ausstieg bringe mehr
Beobachtungen, ist am massgeblichen Punkt widerlegt - er bringt **andere**
Beobachtungen, nicht mehr.

**Es ist ein Gueteeffekt**, und ein grosser: Beim 40er-Deckel steigt die Guete
je Trade von 0,2708 auf 0,2951 und die wirksame Stichprobe von 115 auf 123;
der Deflated Sharpe springt von 0,5826 auf **0,7903**. Das ist der groesste
Sprung, den dieses Gate in der Kette 403 bis 415 gesehen hat.

Und trotzdem besteht nichts
--------------------------
Es bleiben **neun von elf** mit denselben zwei offenen Gates. Der Deflated
Sharpe fehlt weiter 0,164 auf die Latte. Und die Messlatte, das Gate, das am
naechsten dran war, wird **schlechter**: 14,1220 statt 14,3391 gegen 15.

Dafuer wird fast alles andere besser - 'Schlechtestes Jahr' von -9,6100 auf
-6,9400, Drawdown von 9,869 auf 7,9961, Monte-Carlo auf 8,3702 gegen 15.

Warum das ein **Kandidat** ist und kein Ergebnis
------------------------------------------------
Der Gipfel liegt nicht-monoton in der Mitte von sechs probierten Werten: 10
gibt 0,3556, 20 gibt 0,4288, 40 gibt 0,7903, 60 gibt 0,6234, 90 gibt 0,6033.
Wer aus einer solchen Reihe den besten Wert nimmt und einbaut, hat einen
Parameter nach dem Ergebnis gewaehlt - genau das, wovor der Deflated Sharpe
schuetzen soll.

Die Regel des Projekts dafuer steht in Befund 232: Jeder Versuch hebt die
Latte fuer alle kuenftigen. Also mitgerechnet: Mit 203 Versuchen steht der
40er-Deckel bei 0,7903, mit 209 - den sechs probierten dazu - bei **0,7858**.
Der Abzug ist klein, weil 203 Versuche schon viel sind; die Richtung ist das
Entscheidende.

**Dieser Deckel wird daher nicht eingebaut.** Er gehoert in den Wettbewerb, wo
Versuche gezaehlt werden und ein Vorschlag durch dieselben elf Gates laeuft
wie jeder andere. Eine Konfiguration still zu aendern, weil eine Zahl dann
besser aussieht, waere die Umgehung des eigenen Verfahrens.

Und was der Gipfel wirklich ist (Befund 417)
--------------------------------------------
Befund 416 hat den Bereich mit plus/minus 50 Prozent abgetastet - 20, 40, 60.
Das Plateau-Gate dieses Projekts setzt fuer eine Stellgroesse **plus/minus 20
Prozent** an, fuer vierzig Kerzen also 32 und 48. Nachgemessen:

    Deckel    n_eff    Guete      DSR
         0      115   0,2708   0,5826
        32      114   0,2890   0,6838
        40      123   0,2951   0,7903
        48      110   0,2930   0,6804

**Die Guete ist ein Plateau, der Gipfel ist eine Spitze - und zwar in der
Stichprobe.** Ueber 32/40/48 liegt die Guete zwischen 0,2890 und 0,2951, eine
Spanne von zwei Prozent; die wirksame Stichprobe zwischen 110 und 123, eine
Spanne von zwoelf. Der Sprung des Deflated Sharpe auf 0,7903 ist also die
**guenstigste Stichprobenkorrektur** unter sieben probierten Werten, nicht die
bessere Strategie.

Was ein Deckel in dieser Gegend ueblicherweise liefert, steht in
``ehrlicher_dsr``: das Mittel der beiden Nachbarn, **0,6821**. Dorthin fehlen
0,268 auf die Latte, nicht 0,160.

Der Gueteeffekt bleibt echt - plus 0,018 bis 0,024 gegen den ungedeckelten
Lauf, und das in jeder Sprosse des Bereichs. Was faellt, ist die Schlagzeile.

**Nebenbei gemessen**: Zwischen Deckeln, die den Trade-Satz kaum veraendern
(157 fertige in allen drei), wandert die wirksame Stichprobe um dreizehn
Beobachtungen - ein Sechstel der 75, die dem Gate fehlen, erzeugt von einem
Regler, der am Handeln fast nichts aendert.

**Und was daraus nicht folgt** (Befund 418). Hier stand, die
Stichprobenkorrektur habe damit "ihr eigenes Rauschen", und es sei nicht klein
gegen die Luecke, die sie misst. **Das ist gemessen und falsch.** Elf
Aufteilungen mit einem Balken Versatz - gleiche Strategie, gleiche Daten -
bewegen die Groesse um **vier** Beobachtungen bei einer Streuung von 1,33, und
die bindende Einteilung bleibt in allen elf das Kalenderquartal. Die dreizehn
sind also das Dreifache der Messstreuung und damit eine **echte** Wirkung des
Deckels.

Der Satz war in der bequemen Richtung falsch: Er haette kuenftig jeden
Unterschied in der wirksamen Stichprobe als Rauschen abtun lassen. Richtig
herum ist die Zahl brauchbar, und sie steht jetzt in
``aufteilung.STICHPROBE_JE_AUFTEILUNG``.

**Der Schluss oben bleibt**: Der Gipfel bei vierzig Kerzen ist ein
ausgewaehlter Extremwert unter sieben probierten Werten, und die beiden
Nachbarn bei 0,68 bleiben die bessere Schaetzung. Das tragende Argument ist
die **Auswahl**, nicht das Rauschen - was 417 daneben auf das Rauschen
gestuetzt hat, faellt weg.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "DECKEL",
    "PLATEAUBEREICH",
    "VARIANTEN",
    "VERSUCHE_GEZAEHLT",
    "VERSUCHE_IM_LAUF",
    "Deckelprobe",
    "bester",
    "ehrlicher_dsr",
    "guetespanne",
    "ist_mengeneffekt",
    "ist_spitze_in_der_stichprobe",
    "stichprobenspanne",
]


@dataclass(frozen=True, slots=True)
class Deckelprobe:
    """Ein Deckel und was er am massgeblichen Punkt liefert."""

    kerzen: int
    fertig: int
    n_eff: int
    bindend: str
    guete: float
    dsr: float
    bestanden: int
    gesamt: int
    laengster_halt: int
    #: Wie viele Trades der Deckel selbst beendet hat. Die Gegenprobe dafuer,
    #: dass er ueberhaupt greift - Befund 177 hat dieselbe Probe gemacht, weil
    #: gleiche Trade-Zahlen aussehen, als taete er nichts.
    deckel_ausstiege: int

    @property
    def designfaktor(self) -> float:
        return self.n_eff / self.fertig


#: Gemessen auf der Zulassungsreihe, BTC + ETH, Tageskerzen, 203 Versuche
#: (Befund 416). Deckel 0 ist der massgebliche Punkt selbst.
DECKEL: tuple[Deckelprobe, ...] = (
    Deckelprobe(
        kerzen=0, fertig=156, n_eff=115, bindend="Kalenderquartal",
        guete=0.2708, dsr=0.5826, bestanden=9, gesamt=11,
        laengster_halt=104, deckel_ausstiege=0,
    ),
    Deckelprobe(
        kerzen=10, fertig=158, n_eff=124, bindend="Kalendermonat",
        guete=0.2288, dsr=0.3556, bestanden=9, gesamt=11,
        laengster_halt=10, deckel_ausstiege=51,
    ),
    Deckelprobe(
        kerzen=20, fertig=157, n_eff=115, bindend="Kalendermonat",
        guete=0.2481, dsr=0.4288, bestanden=9, gesamt=11,
        laengster_halt=20, deckel_ausstiege=39,
    ),
    Deckelprobe(
        kerzen=40, fertig=157, n_eff=123, bindend="Kalendermonat",
        guete=0.2951, dsr=0.7903, bestanden=9, gesamt=11,
        laengster_halt=40, deckel_ausstiege=25,
    ),
    # Die plus/minus-20-Prozent-Nachbarn des Gipfels, nachgemessen in
    # Befund 417 - der Bereich, den das Plateau-Gate des Projekts fuer eine
    # Stellgroesse ansetzt. Befund 416 hatte nur plus/minus 50 Prozent.
    Deckelprobe(
        kerzen=32, fertig=157, n_eff=114, bindend="Kalendermonat",
        guete=0.2890, dsr=0.6838, bestanden=9, gesamt=11,
        laengster_halt=32, deckel_ausstiege=31,
    ),
    Deckelprobe(
        kerzen=48, fertig=157, n_eff=110, bindend="Kalendermonat",
        guete=0.2930, dsr=0.6804, bestanden=9, gesamt=11,
        laengster_halt=48, deckel_ausstiege=18,
    ),
    Deckelprobe(
        kerzen=60, fertig=156, n_eff=121, bindend="Kalendermonat",
        guete=0.2698, dsr=0.6234, bestanden=9, gesamt=11,
        laengster_halt=60, deckel_ausstiege=8,
    ),
    Deckelprobe(
        kerzen=90, fertig=156, n_eff=116, bindend="Kalendermonat",
        guete=0.2727, dsr=0.6033, bestanden=9, gesamt=11,
        laengster_halt=90, deckel_ausstiege=2,
    ),
)

#: Der DSR des besten Deckels, wie im Lauf gerechnet - mit dem Zaehlerstand,
#: der zum Messzeitpunkt galt.
VERSUCHE_IM_LAUF = 0.7903

#: Und mit allen probierten Varianten als Versuche (Befund 232). Der
#: Unterschied ist klein; dass er gerechnet wird, ist der Punkt.
#:
#: **Die Zahl ist in Befund 417 berichtigt.** Befund 416 hat "sechs probierte
#: Varianten" gezaehlt und 209 Versuche gerechnet - darunter war aber Deckel
#: 0, und der ist der bestehende Punkt, nicht ein neuer Versuch. Es waren
#: fuenf neue (208 Versuche, DSR 0,7865); mit den beiden Nachbarn aus 417
#: sind es sieben (210, DSR 0,7850). Die Richtung stimmte, die Zahl war
#: eine zu hoch - und in der strengen Richtung, was sie nicht besser macht.
VERSUCHE_GEZAEHLT = 0.7850

#: Wie viele **neue** Varianten probiert sind. Deckel 0 zaehlt nicht mit.
VARIANTEN = 7


def bester() -> Deckelprobe:
    """Der Deckel mit dem hoechsten Deflated Sharpe.

    **Eine Auswahl, kein Urteil.** Er steht hier, damit die Zahl nachzulesen
    ist, nicht damit sie eingebaut wird; der Modulkopf sagt, warum.
    """
    return max(DECKEL, key=lambda d: d.dsr)


def ist_mengeneffekt(toleranz: int = 5) -> bool:
    """Bringt ein Deckel mehr Beobachtungen? Gemessen: nein.

    Die Spanne der fertigen Trades ueber alle Deckel liegt unter ``toleranz``.
    Die Funktion rechnet das aus der Tabelle, statt es zu behaupten.
    """
    zahlen = [d.fertig for d in DECKEL]
    return max(zahlen) - min(zahlen) > toleranz


#: Die Nachbarschaft, die das Plateau-Gate fuer eine Stellgroesse ansetzt:
#: plus/minus 20 Prozent. Fuer vierzig Kerzen also zweiunddreissig und
#: achtundvierzig (Befund 417).
PLATEAUBEREICH = (32, 40, 48)


def _je_kerzen(kerzen: int) -> Deckelprobe:
    return next(d for d in DECKEL if d.kerzen == kerzen)


def guetespanne() -> tuple[float, float]:
    """Kleinste und groesste Guete im Plateaubereich - **gerechnet**."""
    werte = [_je_kerzen(k).guete for k in PLATEAUBEREICH]
    return min(werte), max(werte)


def stichprobenspanne() -> tuple[int, int]:
    """Dasselbe fuer die wirksame Stichprobe."""
    werte = [_je_kerzen(k).n_eff for k in PLATEAUBEREICH]
    return min(werte), max(werte)


def ist_spitze_in_der_stichprobe() -> bool:
    """Steht der DSR-Gipfel auf der Stichprobe und nicht auf der Guete?

    Gerechnet aus der Tabelle: Die Guete ist im Plateaubereich praktisch
    gleich (0,2890 bis 0,2951, eine Spanne von 0,006), die wirksame
    Stichprobe nicht (110 bis 123, dreizehn Beobachtungen). Faellt die
    Antwort einmal anders aus, ist der Satz im Kopf falsch und faellt mit.
    """
    guete_unten, guete_oben = guetespanne()
    n_unten, n_oben = stichprobenspanne()
    guete_relativ = (guete_oben - guete_unten) / guete_unten
    n_relativ = (n_oben - n_unten) / n_unten
    return n_relativ > 3 * guete_relativ


def ehrlicher_dsr() -> float:
    """Der DSR eines gedeckelten Laufs, ohne den Gipfel auszuwaehlen.

    Das Mittel der beiden Nachbarn - nicht der Gipfel selbst. Wer den Gipfel
    nennt, nennt die guenstigste Stichprobenkorrektur von sieben probierten
    Werten; wer die Nachbarn nimmt, nennt, was ein Deckel in dieser Gegend
    **ueblicherweise** liefert.
    """
    nachbarn = [_je_kerzen(k).dsr for k in (32, 48)]
    return sum(nachbarn) / len(nachbarn)
