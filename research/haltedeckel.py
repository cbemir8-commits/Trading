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
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "DECKEL",
    "VERSUCHE_GEZAEHLT",
    "VERSUCHE_IM_LAUF",
    "Deckelprobe",
    "bester",
    "ist_mengeneffekt",
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

#: Und mit den sechs probierten Varianten als Versuche (Befund 232). Der
#: Unterschied ist klein; dass er gerechnet wird, ist der Punkt.
VERSUCHE_GEZAEHLT = 0.7858


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
