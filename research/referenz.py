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
    "AUSSICHT_ERSTPUNKT",
    "AUSSICHT_VERBUND",
    "BILD_15_MINUTEN",
    "BILD_TAGESKERZEN",
    "PERPETUALPUNKT",
    "SCHUB",
    "SPOTPUNKT",
    "UEBERHOLT",
    "VORRATSZIEL",
    "VORRAT_TAGESKERZEN",
    "Aussicht",
    "Referenzpunkt",
    "Vorratsbild",
    "Vorratsregel",
    "Vorratsziel",
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

    intervall: str = "D"
    """Auf welcher Kerzenlaenge dieser Stand gemessen wurde.

    **Das Feld fehlte bis Befund 190**, und ohne es hat ``cli vorratsdecke``
    den Bestand auf jede Gerade gelegt, die es gerade gefittet hatte - auch
    auf die des Viertelstunden-Vorrats. Dort kam ein Vorsprung von +5,64
    Reststreuungen heraus, gruen gedruckt und als bester Stand der
    Projektgeschichte zu lesen. Er bedeutet nichts: Ein auf Tageskerzen
    gemessener Kandidat steht dort gegen eine Gerade aus 36 Regeln, die er
    nie gehandelt hat.

    Ein Ausschlag nach oben ist schwerer zu bemerken als ein Absturz. Der
    Abbruch aus Befund 188 hat sich gemeldet; diese Zahl haette man geglaubt.
    """

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
    dsr=0.5827,
    bestanden=9,
    gesamt=11,
    versuche=203,
    schiefe=3.4646,
    woelbung=15.9173,
)

#: Der **zweite** Betriebspunkt: Perpetual, mit Hebel und Funding.
#:
#: Kein ueberholter Stand und kein zweiter Anwaerter auf "massgeblich" -
#: derselbe Kandidat auf denselben Daten unter anderen Handelsbedingungen.
#: ``cli stand`` rechnet ihn primaer, weil die Voraussetzung offen ist
#: (Befund 112); die Analyse bezieht sich auf ``SPOTPUNKT``.
#:
#: **Warum er hier steht** (Befund 235): Ohne ihn liess sich der Verlauf des
#: Wettrennens nicht rechnen. ``Rennen.bester`` gehoert das, was die **Suche**
#: hervorgebracht hat - und gesucht wurde unter Perpetual. Wer stattdessen den
#: Spot-Wert einsetzt, schreibt der Suche einen Gewinn gut, den der Wegfall
#: des Funding gebracht hat: genau die Falle, die Befund 110 beschreibt und
#: die die Suche 2,4-mal produktiver aussehen liess. Solange nur ein Punkt
#: verzeichnet war, blieb dieser Wert eine gepflegte Zahl in einem Prosatext.
PERPETUALPUNKT = Referenzpunkt(
    name="Perpetual wie gebaut",
    befund=235,
    trades=156,
    effektiv=115,
    guete=0.2535,
    dsr=0.4576,
    bestanden=7,
    gesamt=11,
    versuche=203,
    schiefe=3.4934,
    woelbung=16.1849,
)

#: Was der Wegfall des Funding an Guete je Trade bringt - **gerechnet, nicht
#: gepflegt.** In Befund 108 stand dafuer 0,0168 als feste Zahl; heute sind es
#: 0,0173, und niemand haette es bemerkt.
SCHUB = round(SPOTPUNKT.guete - PERPETUALPUNKT.guete, 4)

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
    historie_tage: int
    befund: int

    betriebspunkt: str = ""
    """Auf welchem Betriebspunkt ``noetig`` gerechnet ist - Befund 316.

    ``noetig`` haengt an der Guete je Trade, und die haengt am Funding:
    Am Spot-Punkt sind es 190 Beobachtungen, am Perpetual-Punkt 221. Die
    Entfernung, die daraus wird, unterscheidet sich um zweieinhalb Jahre.

    Leer heisst "nicht angegeben", und dann steht im Bericht auch keiner -
    eine geratene Angabe waere schlimmer als keine.
    """

    def __post_init__(self) -> None:
        if self.historie_tage <= 0:
            raise ValueError("Ohne Historie laesst sich keine Sammelrate rechnen.")
        if self.heute <= 0:
            raise ValueError("Ohne Beobachtungen gibt es keine Rate.")
        if self.befund <= 0:
            raise ValueError("Eine Aussicht ohne Fundstelle ist eine Behauptung.")

    @property
    def rate_je_tausend_tage(self) -> float:
        """Effektive Beobachtungen je 1000 Tage - **gerechnet, nicht gepflegt.**

        Das ist genau die Rate am laengsten gemessenen Fenster, denn dort ist
        die Historie die ganze Reihe: ``heute`` Beobachtungen auf
        ``historie_tage`` Tagen. Befund 138 hat sie so gebildet (112 auf 3277
        Tagen = 34,2), nur stand sie danach als Zahl da.

        **Warum sie jetzt eine Rechnung ist.** Befund 158 hat ``noetig`` und
        ``heute`` nachgezogen und diese dritte Zahl stehen lassen - im selben
        Lauf, in dem der Satz stand, dass eine Wache ueber die eine Haelfte
        einer Rechnung die andere nicht sichert. Drei gepflegte Felder,
        zwei nachgezogen. Jetzt sind es zwei gepflegte, und eines davon
        (``historie_tage``) haengt an den Daten und wird geprueft.
        """
        return 1000.0 * self.heute / self.historie_tage

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
        herkunft = (
            f"({self.betriebspunkt}, Befund {self.befund})"
            if self.betriebspunkt
            else f"(Befund {self.befund})"
        )
        return (
            f"mindestens {self.tage} Tage ({self.jahre:.1f} Jahre) fuer "
            f"{self.fehlend} fehlende Beobachtungen  {herkunft}"
        )


#: Der Abstand zur Schwelle, in Zeit. Untergrenze - siehe ``Aussicht``.
#:
#: **Auf dem Spot-Punkt gerechnet** (``SPOTPUNKT.noetiges_n()``, gehalten von
#: einem Test). Das war bis Befund 316 nirgends angeschrieben, und der
#: Bericht setzt diese Zeile unter einen Kopf, der 'Perpetual' sagt.
AUSSICHT = Aussicht(
    noetig=190,
    heute=115,
    historie_tage=3300,
    befund=159,
    betriebspunkt="Spot",
)

#: Dieselbe Rechnung am **Erstpunkt** - dem, den der Bericht meldet.
#:
#: Ohne Funding ist die Guete je Trade hoeher (0,2708 gegen 0,2535), und ein
#: besserer Sharpe je Trade verlangt weniger Beobachtungen: 190 statt 221.
#: Die Entfernung wird damit am gemeldeten Punkt **zweieinhalb Jahre
#: groesser** als die Zeile darueber - dieselbe Sammelrate, dieselbe
#: Historie, nur der andere Betriebspunkt.
#:
#: Dass beide dieselben ``heute`` und ``historie_tage`` tragen, ist kein
#: Versehen: Es ist derselbe Kandidat auf denselben Kerzen. Verschieden ist
#: allein, wie viel Evidenz die Schwelle bei dieser Guete verlangt.
AUSSICHT_ERSTPUNKT = Aussicht(
    noetig=221,
    heute=115,
    historie_tage=3300,
    befund=159,
    betriebspunkt="Perpetual",
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
    historie_tage=3300,
    befund=159,
)


@dataclass(frozen=True, slots=True)
class Vorratsregel:
    """Eine Regel des Katalogs, wie ``cli vorratsdecke`` sie druckt."""

    name: str
    n_eff: int
    je_trade: float
    guete: float
    noetig: float

    @property
    def luecke(self) -> float:
        return self.noetig - self.guete


#: Der gemessene Tageskatalog - 18 Regeln, Spot-Punkt, Versuchsstand 203.
#:
#: **Warum er hier steht und nicht in einem Test** (Befund 292): Er stand in
#: zwei Testdateien nebeneinander, einmal mit und einmal ohne Lattenspalte.
#: Zwei Quellen fuer dieselbe Messung laufen frueher oder spaeter auseinander
#: - davon handeln die Befunde 158, 159 und 165, und der Modulkopf hier ist
#: die Antwort darauf. Wer den Katalog neu misst, aendert ihn an dieser
#: **einen** Stelle.
#:
#: ``noetig`` steht auf den Momenten **dieser** Regel, wie im Gate (Befund
#: 191), und haengt damit am Versuchsstand. Es sind Zahlen eines Tages, kein
#: Vertrag: Wer ein Genom hinzufuegt oder weitersucht, aendert sie.
VORRAT_TAGESKERZEN: tuple[Vorratsregel, ...] = (
    Vorratsregel("Donchian-Ausbruch 55/20", 58, 0.3262, 2.484, 3.564),
    Vorratsregel("Grosser Trendausbruch", 57, 0.3215, 2.428, 3.980),
    Vorratsregel("Trend-Beteiligung 50 Tage", 127, 0.2021, 2.278, 3.361),
    Vorratsregel("Trendfolge Ausbruch", 130, 0.1892, 2.157, 4.235),
    Vorratsregel("Trend-Beteiligung 100 Tage", 76, 0.2192, 1.911, 3.379),
    Vorratsregel("Momentum-Beteiligung", 57, 0.2377, 1.795, 3.439),
    Vorratsregel("Trend-Beteiligung (fair gerechnet)", 29, 0.3274, 1.763, 3.460),
    Vorratsregel("Nur mit der Drift", 41, 0.2716, 1.739, 3.883),
    Vorratsregel("EMA-Kreuzung (Messlatte)", 59, 0.2190, 1.682, 4.166),
    Vorratsregel("Trendbeteiligung EMA200", 63, 0.1981, 1.573, 3.472),
    Vorratsregel("Trendbeteiligung mit Puffer", 86, 0.1672, 1.551, 3.533),
    Vorratsregel("Seltener grosser Ausbruch", 40, 0.2384, 1.508, 3.689),
    Vorratsregel("Trend beide Richtungen", 45, 0.2210, 1.482, 3.563),
    Vorratsregel("Momentum-Beteiligung 90 Tage", 45, 0.1887, 1.266, 3.756),
    Vorratsregel("Langsamer Kreuzer (Messlatte 2)", 16, 0.3085, 1.234, 3.777),
    Vorratsregel("Volatilitaets-Ausbruch", 85, 0.0303, 0.279, 4.130),
    Vorratsregel("Starker Trend, Momentum", 58, -0.2483, -1.891, 3.617),
    Vorratsregel("Momentum Ruecksetzer", 254, -0.1358, -2.164, 4.209),
)


@dataclass(frozen=True, slots=True)
class Vorratsziel:
    """Was der Katalog verlangt - und was er je gezeigt hat.

    **Der Befund 291 in Zahlen.** Die Latte steht in Guete; geteilt durch
    ``sqrt(n_eff)`` wird daraus eine Anforderung an die Qualitaet je Trade,
    und die faellt steil mit der Stichprobe. An der groessten gemessenen
    Stichprobe liegt sie **innerhalb** dessen, was andere Regeln desselben
    Katalogs gezeigt haben - nur eben bei kleinen Stichproben.
    """

    regeln: int
    geraeumt: int
    beste_je_trade: float
    beste_bei: int
    billigste_noetig: float
    billigste_bei: int
    erreicht_von: int
    aber_hoechstens_bei: int

    @property
    def nie_zusammen(self) -> bool:
        """Gibt es beide Haelften, aber nie an derselben Regel?

        **Und keine Regel, die ihre Latte schon raeumt.** Sonst behauptete
        der Satz "beide Haelften gibt es, nur nie zusammen" etwas Falsches:
        Wo eine Regel raeumt, gibt es sie sehr wohl zusammen, und dann ist
        nicht die Verbindung die Frage, sondern jene Regel.
        """
        return (
            self.geraeumt == 0
            and self.erreicht_von > 0
            and self.aber_hoechstens_bei < self.billigste_bei
        )

    @property
    def faktor(self) -> float:
        """Um wie viel die Stichprobe wachsen muesste, bei gleicher Qualitaet."""
        return self.billigste_bei / self.aber_hoechstens_bei if self.aber_hoechstens_bei else 0.0

    def als_ziel(self) -> str:
        return (
            f"Qualitaet je Trade mindestens {self.billigste_noetig:.4f} bei "
            f"n_eff {self.billigste_bei} - dieselbe Qualitaet, die "
            f"{self.erreicht_von} von {self.regeln} Regeln zeigen, bei der "
            f"{self.faktor:.0f}-fachen Stichprobe"
        )


def _vorratsziel(regeln: tuple[Vorratsregel, ...]) -> Vorratsziel:
    """**Gerechnet, nicht gepflegt** - wie ``SCHUB``.

    Stuende das Ziel als Zahlenliste daneben, waere es eine zweite Quelle zum
    Katalog darueber, und genau die will dieses Modul verhindern.
    """
    offen = [r for r in regeln if r.luecke > 0] or list(regeln)
    billigste = min(offen, key=lambda r: r.noetig / r.n_eff**0.5)
    schwelle = billigste.noetig / billigste.n_eff**0.5
    koennen = [r for r in regeln if r.je_trade >= schwelle]
    beste = max(regeln, key=lambda r: r.je_trade)
    return Vorratsziel(
        regeln=len(regeln),
        geraeumt=sum(1 for r in regeln if r.luecke <= 0),
        beste_je_trade=beste.je_trade,
        beste_bei=beste.n_eff,
        billigste_noetig=schwelle,
        billigste_bei=billigste.n_eff,
        erreicht_von=len(koennen),
        aber_hoechstens_bei=max((r.n_eff for r in koennen), default=0),
    )


#: Was ein Vorschlag bringen muss, damit er nicht eine schon gemessene Regel
#: wiederholt (Befund 291/292).
VORRATSZIEL = _vorratsziel(VORRAT_TAGESKERZEN)


@dataclass(frozen=True, slots=True)
class Vorratsbild:
    """Die Kurzfassung eines gemessenen Katalogs - fuer den Vergleich.

    **Warum nur die Kurzfassung** (Befund 297): Die 36 Regeln des
    15-Minuten-Katalogs stehen nicht als Tabelle hier, weil niemand sie
    einzeln braucht - anders als beim Tageskatalog, aus dem ``VORRATSZIEL``
    gerechnet wird. Was gebraucht wird, ist der Vergleich der beiden Bilder,
    und dafuer genuegen diese Zahlen. Die vollstaendige Messung steht im
    Laborbuch.
    """

    befund: int
    kerzenlaenge: str
    regeln: int
    mit_vorteil: int
    """Regeln mit positiver Guete."""

    beste_guete: float
    beste_je_trade: float
    billigste_noetig: float
    rho_je_trade: float
    rho_guete: float
    """Rangkorrelation von n_eff mit der Qualitaet je Trade und mit der Guete.

    **Auf den beiden Katalogen genau gegenlaeufig** - das ist der Befund.
    """

    @property
    def in_reichweite(self) -> bool:
        """Hat der Katalog die noetige Qualitaet je Trade je gezeigt?"""
        return self.beste_je_trade >= self.billigste_noetig


#: Der Tageskatalog, wie Befund 290/291 ihn gemessen hat.
BILD_TAGESKERZEN = Vorratsbild(
    befund=291,
    kerzenlaenge="1d",
    regeln=18,
    mit_vorteil=16,
    beste_guete=2.484,
    beste_je_trade=0.3274,
    billigste_noetig=0.2641,
    rho_je_trade=-0.679,
    rho_guete=+0.072,
)

#: Der 15-Minuten-Katalog, gemessen in Befund 297.
BILD_15_MINUTEN = Vorratsbild(
    befund=297,
    kerzenlaenge="15m",
    regeln=36,
    mit_vorteil=1,
    beste_guete=0.703,
    beste_je_trade=0.0304,
    billigste_noetig=0.0494,
    rho_je_trade=-0.260,
    rho_guete=-0.701,
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
