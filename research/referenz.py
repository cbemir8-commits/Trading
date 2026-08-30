"""Der Referenzpunkt des Projekts - an **einer** Stelle.

Warum es das gibt
-----------------
Befund 135 hat das Deflated-Sharpe-Gate strenger gemacht: Die effektive
Stichprobe faellt von 152 auf 112, der Deflated Sharpe von 0,8640 auf 0,6026.

Danach standen **einundzwanzig Stellen in acht Modulen** weiter auf 0,8640.
Jede zitierte korrekt einen Befund; wer sie las, fand trotzdem den Stand von
gestern. Das ist genau die Falle aus Befund 130 - dort hat ein Registereintrag
auf eine ueberholte Tabelle gezeigt und zwei Laeufe hintereinander in die Irre
gefuehrt -, diesmal eine Ebene tiefer, in den Modulkoepfen.

Ein Laborbuch darf alte Zahlen tragen: Es ist ein Protokoll. Ein Modulkopf
nicht: Er wird als Stand gelesen.

Was hier steht
--------------
Die Zahlen des **massgeblichen** Betriebspunkts, mit der Fundstelle, aus der
sie stammen. Wer sie zitiert, zitiert von hier - und findet damit auch, was
sie ueberholt hat.

**Sie werden gepflegt, nicht gemessen.** Gemessen wird im Lauf; hier steht,
was zuletzt herauskam, damit ein Text nicht raten muss. Ein Test vergleicht
die Angabe mit dem, was das Gate heute liefert - laeuft sie weg, faellt es
dort auf.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "AUSSICHT",
    "AUSSICHT_VERBUND",
    "SPOTPUNKT",
    "UEBERHOLT",
    "Aussicht",
    "Referenzpunkt",
    "veraltet",
]


@dataclass(frozen=True, slots=True)
class Referenzpunkt:
    """Ein gemessener Stand mit seiner Fundstelle."""

    name: str
    befund: int
    trades: int
    effektiv: int
    guete: float
    dsr: float
    bestanden: int
    gesamt: int
    versuche: int
    schwelle: float = 0.95

    schiefe: float | None = None
    woelbung: float | None = None
    """Die Verteilungsform der Trades - **damit ``noetiges_n`` rechenbar ist.**

    Ohne sie war die Zahl der noch fehlenden Beobachtungen von Hand gepflegt,
    und genau das ist schiefgegangen: In Befund 152 habe ich ``AUSSICHT.heute``
    nachgezogen und ``noetig`` stehen lassen, obwohl dieselbe Korrektur auch
    ``guete`` gesenkt hatte. Ein niedrigerer Sharpe je Trade verlangt aber ein
    **groesseres** n. Die genannte Entfernung war dadurch sechs Befunde lang
    zu kurz (Befund 158).

    ``None`` bei den ueberholten Staenden: Dort ist die Form nie festgehalten
    worden, und ``noetiges_n`` sagt dann ehrlich nichts.
    """

    def __post_init__(self) -> None:
        if self.effektiv > self.trades:
            raise ValueError(
                f"{self.name}: {self.effektiv} unabhaengige Beobachtungen aus "
                f"{self.trades} Trades - das geht nicht."
            )
        if self.befund <= 0:
            raise ValueError(f"{self.name} ohne Fundstelle ist eine Behauptung.")

    @property
    def luecke(self) -> float:
        """Was zur Schwelle fehlt."""
        return self.schwelle - self.dsr

    def noetiges_n(self, *, hoechstens: int = 3000) -> int | None:
        """Die kleinste effektive Stichprobe, bei der die Schwelle traegt.

        Gerechnet, nicht gepflegt. ``None``, wenn die Verteilungsform fehlt -
        eine Entfernung ohne Verteilungsform waere geraten.
        """
        if self.schiefe is None or self.woelbung is None:
            return None
        from research.gates import deflated_sharpe_ratio

        for n in range(max(self.effektiv, 10), hoechstens):
            wert = deflated_sharpe_ratio(
                observed_sharpe=self.guete,
                trials=self.versuche,
                sample_size=n,
                skew=self.schiefe,
                kurtosis=self.woelbung,
            )
            if float(wert) >= self.schwelle:
                return n
        return None

    def als_zeile(self) -> str:
        return (
            f"{self.name:<24} {self.trades:>4} Trades, n = {self.effektiv:>3}, "
            f"Guete {self.guete:.4f}, DSR {self.dsr:.4f}, "
            f"{self.bestanden}/{self.gesamt}  (Befund {self.befund})"
        )


#: Der massgebliche Punkt: Spot, kein Funding, kein Hebel (Befund 108),
#: Deflated-Sharpe-Gate mit Quartalseinteilung (Befund 135), Nachlauf ueber
#: vier Fensterlaengen und zensierte Trades ausserhalb der Statistik
#: (Befund 151/152).
SPOTPUNKT = Referenzpunkt(
    name="Spot wie gebaut",
    befund=152,
    trades=156,
    effektiv=115,
    guete=0.2708,
    dsr=0.5881,
    bestanden=9,
    gesamt=11,
    versuche=198,
    schiefe=3.4646,
    woelbung=15.9173,
)

#: Staende, die einmal massgeblich waren und es nicht mehr sind. Wer einen
#: dieser Werte in einem Modulkopf liest, liest Geschichte.
UEBERHOLT: tuple[Referenzpunkt, ...] = (
    Referenzpunkt(
        name="Spot, vor Befund 152",
        befund=135,
        trades=152,
        effektiv=112,
        guete=0.2765,
        dsr=0.6026,
        bestanden=9,
        gesamt=11,
        versuche=198,
    ),
    Referenzpunkt(
        name="Spot, vor Befund 135",
        befund=108,
        trades=152,
        effektiv=152,
        guete=0.2765,
        dsr=0.8640,
        bestanden=9,
        gesamt=11,
        versuche=198,
    ),
    Referenzpunkt(
        name="Perpetual, vor Befund 108",
        befund=54,
        trades=152,
        effektiv=152,
        guete=0.2597,
        dsr=0.7641,
        bestanden=7,
        gesamt=11,
        versuche=198,
    ),
)


@dataclass(frozen=True, slots=True)
class Aussicht:
    """Wie weit es bis zur Schwelle ist - in Beobachtungen und in Tagen.

    **Die Tage sind eine Untergrenze, keine Schaetzung.** Gerechnet wird mit
    der effektiven Sammelrate des **laengsten** gemessenen Fensters. Befund 138
    hat sie ueber sechs Fenster vermessen und gefunden, dass der Anteil mit der
    Historie monoton faellt - mehr Quartale, engere Permutationsnull, mehr
    sichtbare Abhaengigkeit.

    Nachgemessen mit der heutigen Rezeptur (Befund 158, acht Einteilungen
    statt zwei):

        Historie    roh   n_eff   Anteil   eff je 1000 Tage
         1451 d      54      54    1,000               37,2
         1816 d      73      73    1,000               40,2
         2320 d     106     106    1,000               45,7
         2547 d     113      95    0,841               37,3
         2912 d     136     125    0,919               42,9
         3300 d     158     114    0,722               34,5

    **Monoton ist das nicht mehr** - bei 2547 Tagen faellt der Anteil auf
    0,841 und steigt danach wieder auf 0,919. Die Begruendung aus 138 traegt
    also schwaecher, als sie dort formuliert war.

    Was bleibt: Das laengste Fenster hat weiter den kleinsten Anteil (0,722),
    und darauf ist gerechnet. Die Zahl ist damit die vorsichtige Wahl unter den
    gemessenen, aber nicht mehr das Ende einer monotonen Reihe. Ein Termin ist
    sie ohnehin nicht.

    Beim Verbund liegt der Anteil ueber die ganze Leiter flacher (0,539 bis
    0,688) und am laengsten Fenster hoeher als beim Bestand - er sammelt
    schneller, siehe ``AUSSICHT_VERBUND``.
    """

    noetig: int
    heute: int
    rate_je_tausend_tage: float
    befund: int

    def __post_init__(self) -> None:
        if self.rate_je_tausend_tage <= 0:
            raise ValueError("Ohne Sammelrate laesst sich keine Zeit rechnen.")
        if self.befund <= 0:
            raise ValueError("Eine Aussicht ohne Fundstelle ist eine Behauptung.")

    @property
    def fehlend(self) -> int:
        return max(self.noetig - self.heute, 0)

    @property
    def tage(self) -> int:
        return round(1000.0 * self.fehlend / self.rate_je_tausend_tage)

    @property
    def jahre(self) -> float:
        return self.tage / 365.25

    def als_zeile(self) -> str:
        return (
            f"mindestens {self.tage} Tage ({self.jahre:.1f} Jahre) fuer "
            f"{self.fehlend} fehlende Beobachtungen  (Befund {self.befund})"
        )


#: Der Abstand zur Schwelle, in Zeit. Untergrenze - siehe ``Aussicht``.
AUSSICHT = Aussicht(
    noetig=190,
    heute=115,
    rate_je_tausend_tage=34.2,
    befund=158,
)

#: Dieselbe Rechnung fuer den **besten gemessenen Kandidaten** - den Verbund
#: aus Bestand und 'Trend-Beteiligung 200 Tage' (Befund 73, zuletzt 154).
#:
#: ``AUSSICHT`` beschreibt den Bestand allein, weil der der massgebliche
#: Betriebspunkt ist. Wer wissen will, wie weit das Projekt **wirklich** noch
#: ist, muss hierher sehen: Der Verbund braucht weniger zusaetzliche
#: Beobachtungen und sammelt sie schneller.
#:
#: Gemessen in Befund 158, Methode wortgleich zu 138: noetiges n aus den
#: eigenen Momenten, Sammelrate am laengsten Fenster.
AUSSICHT_VERBUND = Aussicht(
    noetig=208,
    heute=136,
    rate_je_tausend_tage=41.2,
    befund=158,
)


def veraltet(text: str) -> tuple[str, ...]:
    """Welche ueberholten Kennzahlen stehen in diesem Text?

    Gesucht wird nach den Zahlen selbst, in beiden Schreibweisen - deutsche
    Komma- und englische Punktschreibung stehen im Projekt nebeneinander.

    **Das ist ein Fund und kein Urteil.** Ein Laborbucheintrag darf sie
    nennen, ein Modulkopf sollte dazusagen, dass sie ueberholt sind. Was
    daraus folgt, entscheidet der Test, der diese Funktion aufruft - nicht
    sie selbst.
    """
    treffer = []
    for punkt in UEBERHOLT:
        # **Auch die Luecke** (Befund 156). Der Registereintrag zu Befund 134
        # sagte zwanzig Befunde lang "die Luecke ist 0,0860" - ein Wert aus
        # einem Betriebspunkt, den Befund 135 ueberholt hat. Er stand in vier
        # Modulen. Die Pruefung sah ihn nicht, weil sie nur nach dem Deflated
        # Sharpe selbst suchte; die daraus abgeleitete Zahl veraltet aber
        # genauso still.
        for wert in (punkt.dsr, punkt.luecke):
            for zahl in (f"{wert:.4f}", f"{wert:.4f}".replace(".", ",")):
                if zahl in text and zahl not in treffer:
                    treffer.append(zahl)
    return tuple(treffer)
