"""Der Rand der Datenreihe - und warum dort nicht gemessen werden darf.

Was Befund 22 geloest hat und was offen blieb
---------------------------------------------
Befund 22 hat einen Messfehler gefunden: Der Backtest lief in jedem
Walk-Forward-Fenster exakt bis zum Fensterende, und eine dort offene Position
wurde zwangsweise glattgestellt. **Fuenfundzwanzig solcher Trades trugen den
gesamten Vorteil** - ohne sie fiel der Sharpe je Trade von 0,244 auf 0,021.

Die Korrektur war ein **Nachlauf**: Der Backtest laeuft ueber das Fensterende
hinaus, bis die im Fenster eroeffneten Trades ihren Ausstieg nach Regel
gefunden haben.

Am **Serienende** gibt es keinen Nachlauf. Dort hoeren die Daten auf, und eine
offene Position wird zum letzten Kurs geschlossen - ``end_of_data``.

Warum das erst jetzt auffiel (Befund 151)
-----------------------------------------
Solange der Datenstand einige Wochen alt war, hatten die letzten Positionen
Zeit, nach Regel auszusteigen. Nach einem frischen Abzug bis **heute** ist das
anders: Je naeher das Datenende an der Gegenwart liegt, desto wahrscheinlicher
faengt es eine offene Position.

Gemessen am Spitzenkandidaten, Spot, 198 Versuche:

    Ende gekuerzt   Tage   Trades   am Ende   n_eff   SR/Trade      DSR
              0     3301      158         2     120     0,2848   0,7255
             30     3271      152         0     112     0,2765   0,6026
             60     3241      152         0     112     0,2765   0,6026
             90     3211      152         0     112     0,2765   0,6026
            120     3181      146         0     114     0,2828   0,6636

**Die beiden Randtrades trugen +0,123 Deflated Sharpe.** Ihr Ergebnis: +26,19
und +25,48 - die zwei groessten Gewinner des Laufs. Ohne sie faellt die
Qualitaet je Trade auf 0,2506, also **unter** den Wert mit dreissig Tagen
Abstand.

Der Wert bei 120 Tagen ist kein Widerspruch: Dort fehlen 6 Trades, das ist
schlicht weniger Historie und eine andere Messung.

Der zweite Rand: das Fensterende
-------------------------------
Beim Nachmessen mit demselben Werkzeug fiel auf, dass es nicht nur um das
Serienende geht. Der Nachlauf aus Befund 22 war an **eine** Fensterlaenge
gebunden und am Spitzenkandidaten kalibriert, der im Mittel sechs Tage haelt.
Eine Regel, die laenger haelt, sprengt ihn:

    Regel                          Trades   am Rand   Guete mit   Guete ohne
    Trend 50 Tage mit Konfluenz       154         0      0,2591       0,2591
    Trend-Beteiligung 200 Tage         53        10      0,3185      -0,3874
    Donchian-Ausbruch 55/20            58         2      0,3074       0,2787

Bei ``Trend-Beteiligung 200 Tage`` waren es 19 % der Trades, und es waren die
groessten Gewinner: ihre zehn Ergebnisse mitteln +50,34, die uebrigen 43
mitteln -1,80. Das ist wortwoertlich Befund 22, eine Regel weiter - und es
traf den Partner, auf dem der groesste je gemessene Sprung des Projekts steht
(Befund 73, nachgemessen in Befund 140).

Es traf nicht nur diese eine Regel. Ueber den ganzen Tageskerzen-Katalog
gemessen waren bei einer Fensterlaenge **12 von 24 Regeln** betroffen, 103
Trades zusammen. Behoben ist es dort, wo es herkam: Der Nachlauf ist auf
**vier** Fensterlaengen verlaengert (``backtest.walkforward``). Danach steht
in der Spalte "am Rand" ueberall null - ausser bei zwei Trades einer Regel,
die am Serienende offen bleiben. Dort hilft kein Nachlauf, sondern nur
Abstand; siehe unten.

Was 'Guete ohne' sagt - und was nicht
--------------------------------------
**Beim ersten Mal falsch gelesen, deshalb steht es hier.** Aus
``Guete ohne`` = -0,3874 folgt **nicht**, dass die Regel ohne den Fehler
negativ waere. Die Trades wegzulassen und sie zu Ende zu handeln sind zwei
verschiedene Gegenproben:

    Trend-Beteiligung 200 Tage             Guete je Trade
    mit Randtrades, Nachlauf 1 x                 0,3185
    Randtrades weggelassen                      -0,3874   <- die falsche Frage
    zu Ende gehandelt, Nachlauf 4 x              0,2952   <- die richtige

``guete_ohne`` beziffert, **wie viel an dem Rand haengt** - ein Alarm, kein
Ergebnis. Es ist derselbe Alarm, mit dem Befund 22 ein Sechstel der Trades
entlarvt hat, und er soll wehtun. Die Zahl, die danach gilt, kommt aus einem
neuen Lauf mit laengerem Nachlauf, nicht aus dieser Spalte.

Am **Serienende** gibt es diesen zweiten Lauf nicht - dort sind die Daten
schlicht zu Ende. Nur deshalb ist Weglassen dort die richtige Antwort.

Die Regel - und warum die erste falsch war (Befund 152)
-------------------------------------------------------
Befund 151 hat hier **dreissig Tage Abstand zum Serienende** hingeschrieben,
mit der Plateau-Tabelle oben als Begruendung. Das war falsch. Die drei
moeglichen Behandlungen, am Spitzenkandidaten gemessen (Spot, 198 Versuche):

    Behandlung                     Trades   n_eff   SR/Trade      DSR    fehlt
    (a) zensierte mitzaehlen          160     117     0,2688   0,5868    0,705
    (b) 30 Tage kuerzen               154     111     0,2591   0,4707    0,870
    (c) zensierte weglassen           158     114     0,2520   0,4452    0,916

**(b) wirft vier fertig gehandelte Trades mit weg** - 160 auf 154, davon nur
zwei zensiert. Und weil die vier Verlierer waren, hebt das die Qualitaet je
Trade: (b) liegt ueber (c). Der Puffer war also nicht die strenge Behandlung,
fuer die ich ihn gehalten habe, sondern die mittlere.

Dazu kommt: Ein Puffer muss **gewaehlt** werden, und das Plateau 30/60/90 ist
keine Struktureigenschaft, sondern heisst nur, dass dieser eine Kandidat in
dieser Strecke gerade flach war. Fuer eine andere Regel liegt es anderswo. Das
Kuerzen verschiebt den Schnitt ausserdem bloss - am neuen Ende steht wieder
eine offene Position.

Es gilt **(c)**: Ein Trade, der am Datenende glattgestellt wurde, ist keine
fertige Beobachtung und zaehlt in der Statistik nicht mit. Kein Parameter,
keine Wahl, und kein fertiger Trade wird weggeworfen. Rechtszensierung, wie
sie in der Lebensdaueranalyse behandelt wird.

**Nur in der Statistik.** In der Kapitalkurve bleibt die offene Position
stehen - sie ist zum letzten Kurs bewertet, und das ist der Kontostand.
Rendite, Rueckgang und schlechtestes Jahr rechnen weiter mit ihr; Deflated
Sharpe, Qualitaet je Trade und effektive Stichprobe nicht.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "RANDGRUND",
    "Randbefund",
    "beurteile",
    "fertige",
    "ohne_zensierte",
    "randtrades",
]

#: Der Ausstiegsgrund, den der Backtest setzt, wenn die Daten aufhoeren.
RANDGRUND = "end_of_data"


def randtrades(trades: list) -> list:
    """Die zensierten Trades: am Kalender glattgestellt, nicht nach Regel."""
    return [t for t in trades if str(getattr(t, "exit_reason", "")) == RANDGRUND]


def fertige(trades: list) -> list:
    """Die Gegenmenge - **die Stichprobe, mit der gerechnet werden darf.**

    Ein Trade, dessen Ausstieg die Regel bestimmt hat, ist eine fertige
    Beobachtung. Einer, den das Datenende glattgestellt hat, ist es nicht: Sein
    Ergebnis haengt daran, wann zuletzt Kerzen geholt wurden.
    """
    return [t for t in trades if str(getattr(t, "exit_reason", "")) != RANDGRUND]


def ohne_zensierte(bericht):
    """Eine flache Kopie des Walk-Forward-Berichts ohne zensierte Trades.

    Kopiert und aendert nicht am Original: Der Aufrufer braucht **beide**
    Sichten. Die Kapitalkurve bleibt unangetastet - dort gehoert die offene
    Position hin, sie ist zum letzten Kurs bewertet und damit der Kontostand.
    Gefiltert wird nur, woraus Trade-Statistik entsteht.
    """
    import copy

    neu = copy.copy(bericht)
    neu.all_trades = fertige(bericht.all_trades)
    fenster = []
    for w in bericht.windows:
        kopie = copy.copy(w)
        kopie.trades = fertige(w.trades)
        fenster.append(kopie)
    neu.windows = fenster
    return neu


@dataclass(frozen=True, slots=True)
class Randbefund:
    """Wie stark der Rand der Reihe die Kennzahl traegt."""

    gesamt: int
    am_rand: int
    guete_mit: float
    guete_ohne: float

    def __post_init__(self) -> None:
        if self.am_rand > self.gesamt:
            raise ValueError(
                f"{self.am_rand} Randtrades aus {self.gesamt} - das geht nicht."
            )

    @property
    def sauber(self) -> bool:
        """Keine Randtrades - die Messung haengt nicht am Datenende."""
        return self.am_rand == 0

    @property
    def anteil(self) -> float:
        return self.am_rand / self.gesamt if self.gesamt else 0.0

    @property
    def hub(self) -> float:
        """Wie viel Qualitaet je Trade allein am Rand haengt."""
        return self.guete_mit - self.guete_ohne

    def urteil(self) -> str:
        if self.sauber:
            return (
                f"Alle {self.gesamt} Trades sind nach Regel ausgestiegen - die "
                f"Messung haengt nicht am Datenende."
            )
        satz = (
            f"{self.am_rand} von {self.gesamt} Trades ({self.anteil:.1%}) wurden "
            f"am Kalender glattgestellt, nicht nach Regel. Sie tragen "
            f"{self.hub:+.4f} an Qualitaet je Trade "
            f"({self.guete_mit:.4f} mit, {self.guete_ohne:.4f} ohne)."
        )
        # **Der Hinweis gehoert dazu, nicht in eine Fussnote.** Genau so hat
        # Befund 22 ein Sechstel der Trades gefunden, die den ganzen Vorteil
        # trugen.
        if self.hub > 0:
            satz += (
                " Der Rand macht die Zahl **freundlicher**. Am Fensterende "
                "hilft ein laengerer Nachlauf; am Serienende zaehlen sie in "
                "der Statistik nicht mit."
            )
        # Der Wert ohne die Randtrades ist ein **Alarm, kein Ergebnis** - er
        # sagt, wie viel daran haengt, nicht was ohne den Fehler herauskaeme.
        # Siehe den Modulkopf; genau hier wurde es einmal verwechselt.
        return satz


def beurteile(trades: list) -> Randbefund | None:
    """Wie viel Qualitaet je Trade am Kalender haengt statt an der Regel.

    Ein **Alarm**, kein Ergebnis: ``guete_ohne`` beantwortet die Frage "wie
    viel haengt daran", nicht "was kaeme ohne den Fehler heraus". Wer die
    beiden verwechselt, liest aus zehn abgeschnittenen Gewinnern eine negative
    Regel heraus, die es nicht gibt - siehe Modulkopf.

    ``None`` bei zu wenigen Trades - unter fuenf ist eine Streuung keine
    Auskunft, und ein Quotient daraus erst recht nicht.
    """
    import numpy as np

    if len(trades) < 5:
        return None
    rand = {id(t) for t in randtrades(trades)}
    alle = np.array([float(t.net_pnl) for t in trades], dtype=float)
    ohne = np.array(
        [float(t.net_pnl) for t in trades if id(t) not in rand], dtype=float
    )

    def guete(werte) -> float:
        if len(werte) < 2:
            return 0.0
        streuung = float(werte.std(ddof=1))
        return float(werte.mean() / streuung) if streuung > 0 else 0.0

    return Randbefund(
        gesamt=len(trades),
        am_rand=len(rand),
        guete_mit=guete(alle),
        guete_ohne=guete(ohne),
    )
