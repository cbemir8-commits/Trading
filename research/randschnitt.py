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

Die Regel
---------
**Dreissig Tage Abstand zum Serienende**, und dann aendert sich bis neunzig
nichts mehr - dieselbe Plateau-Signatur wie beim Nachlauf in Befund 22. Der
Puffer ist gemessen und nicht gewaehlt.

Er wirkt in die **strenge** Richtung: Er entfernt Trades, die guenstig
aussehen, weil sie nicht zu Ende gehandelt wurden. Wer ihn weglaesst, bekommt
eine freundlichere Zahl - und genau deshalb steht er hier.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["RANDPUFFER_TAGE", "Randbefund", "beurteile", "randtrades"]

#: Abstand zum Serienende, gemessen (siehe Tabelle oben). Auf Tageskerzen.
#: Bei kuerzeren Kerzen gehoert er an die Haltedauer gebunden, nicht an Tage -
#: dieselbe Ueberlegung wie beim Nachlauf, der an der Fensterlaenge haengt.
RANDPUFFER_TAGE = 30

#: Der Ausstiegsgrund, den der Backtest setzt, wenn die Daten aufhoeren.
RANDGRUND = "end_of_data"


def randtrades(trades: list) -> list:
    """Die Trades, die nicht nach Regel ausgestiegen sind, sondern am Rand."""
    return [t for t in trades if str(getattr(t, "exit_reason", "")) == RANDGRUND]


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
                f" Der Rand macht die Zahl **freundlicher**. Am Fensterende "
                f"hilft ein laengerer Nachlauf, am Serienende nur, "
                f"{RANDPUFFER_TAGE} Tage frueher zu enden."
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
