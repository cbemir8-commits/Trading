"""Was ein Partner koennen muesste - **bevor** man Versuche dafuer ausgibt.

Die Annahme aus Befund 73, die falsch war
-----------------------------------------
Dort stand der Gedanke, der zum Verbund gefuehrt hat:

    *"Es gibt Kandidaten mit hoeherer Qualitaet je Trade, die nur zu selten
    handeln. Was fehlt, ist Menge."*

Gewaehlt wurden danach die beiden hochwertigsten seltenen Kandidaten -
'Trend-Beteiligung 200 Tage' mit 0,3185 je Trade und 'Donchian-Ausbruch 55/20'
mit 0,3074. Beide liegen 19 bis 23 % ueber dem Spitzenkandidaten. Der bessere
Verbund kam auf 3,368 Guete gegen die noetigen 3,629.

**Diese beiden Zahlen sind ueberholt** (Befund 140): Sie stehen auf der
Einteilung von vor Befund 135. Richtig gerechnet sind es 3,073 gegen 3,625 -
die Luecke ist fast doppelt so gross. Der aktuelle Stand steht im Kopf von
``research/verbund.py``. Die Form der Karte aendert sich dadurch nicht, ihre
Eingangsgroessen schon.

Diese Karte sagt, warum - und die Antwort steht quer zur Auswahl:

    Noetiges SR/Trade des Partners fuer Guete 3,629

    Trades       u=0,50    u=0,72    u=0,85    u=1,00
    ------------------------------------------------
    50           0,6680    0,4237    0,3264    0,2386
    100          0,4189    0,2826    0,2283    0,1794
    154          0,3258    0,2283    0,1895    0,1545
    250          0,2530    0,1842    0,1569    0,1322
    400          0,2022    0,1519    0,1319    0,1138

Bei 53 Trades und dem gemessenen Unabhaengigkeitsgrad von 0,72 haette der
Partner **0,4237** gebraucht. Er hatte 0,3185 - eine der besten Zahlen des
Projekts, und trotzdem weit weg.

Bei 154 Trades haetten dagegen **0,2283** genuegt: weniger als der
Spitzenkandidat selbst hat. **Ein Partner muss nicht besser sein. Er muss
genug handeln und unabhaengig genug sein.**

Damit war die Auswahl in Befund 73 nach dem falschen Merkmal getroffen. Nicht
die Qualitaet der seltenen Kandidaten war das Problem, sondern ihre Seltenheit
- und die stand die ganze Zeit in derselben Tabelle.

Der Unabhaengigkeitsgrad
------------------------
``u = n_eff / n_roh``, aus den gemessenen Verbunden zurueckgerechnet:

    Spitze allein    154 roh -> 154 eff   u = 1,000
    + 200 Tage       207 roh -> 149 eff   u = 0,720
    + Donchian       212 roh -> 106 eff   u = 0,500

Er ist **nicht vorhersagbar, nur messbar** - deshalb steht er als Spalte da
und nicht als Zahl. Und er trifft die ganze Stichprobe, nicht nur den Zusatz:
Der Verbund erzeugt Binnenabhaengigkeit, die es einzeln nicht gab, weil in
denselben Fenstern jetzt Trades beider Regeln liegen.

Wie genau die Naeherung ist
---------------------------
Der Sharpe des Verbunds wird als mit der Trade-Zahl gewichtetes Mittel
geschaetzt. An den beiden gemessenen Faellen:

    53 Trades   vorhergesagt 0,2743   gemessen 0,2759   -0,6 %
    58 Trades   vorhergesagt 0,2723   gemessen 0,2569   +6,0 %

Die Abweichung geht in eine Richtung, die zaehlt: Wo die Verteilungen der
beiden Beine verschieden sind, waechst die Streuung der Mischung, und die
Naeherung ist zu **freundlich**. Die Karte nennt also eher zu niedrige
Anforderungen - wenn schon sie nicht erreichbar sind, ist die Sache erledigt.

Kostet keinen Versuch: Gerechnet wird ueber Partner, nicht mit ihnen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Die aus den gemessenen Verbunden zurueckgerechneten Grade. 1,0 heisst
#: "keine Kuerzung" und ist der unerreichbare Bestfall.
GEMESSENE_GRADE: tuple[float, ...] = (0.50, 0.72, 0.85, 1.00)


def verbund_sharpe(*, n1: int, sr1: float, n2: int, sr2: float) -> float:
    """Der Sharpe je Trade des Verbunds - mit der Trade-Zahl gewichtet.

    Eine Naeherung, und eine freundliche: Sie unterstellt, dass die Streuung
    der Mischung gleich bleibt. Wo sich die Verteilungen der beiden Beine
    unterscheiden, waechst sie - dann liegt der wirkliche Wert darunter.
    """
    gesamt = n1 + n2
    return (n1 * sr1 + n2 * sr2) / gesamt if gesamt else 0.0


def verbund_guete(
    *, n1: int, sr1: float, n2: int, sr2: float, unabhaengigkeit: float
) -> float:
    """``SR/Trade * sqrt(n_eff)`` - die Groesse, an der das Gate haengt.

    ``unabhaengigkeit`` wirkt auf die **gesamte** Stichprobe, nicht nur auf den
    Zusatz: Ein Verbund erzeugt Binnenabhaengigkeit, die es einzeln nicht gab,
    weil in denselben Fenstern Trades beider Regeln liegen. Genau so haben sich
    die gemessenen Faelle verhalten - 207 roh zu 149 eff bei einem Bein, das
    allein nicht gekuerzt wurde.
    """
    sharpe = verbund_sharpe(n1=n1, sr1=sr1, n2=n2, sr2=sr2)
    return sharpe * (max(unabhaengigkeit, 0.0) * (n1 + n2)) ** 0.5


def noetiges_sharpe(
    *,
    n1: int,
    sr1: float,
    n2: int,
    unabhaengigkeit: float,
    ziel: float,
    obergrenze: float = 3.0,
) -> float | None:
    """Welches SR/Trade der Partner mitbringen muesste.

    ``None``, wenn selbst ein Jahrhundertwert nicht genuegt - dann liegt es
    nicht am Partner, sondern an der Trade-Zahl oder der Abhaengigkeit.
    """

    def guete(sr2: float) -> float:
        return verbund_guete(
            n1=n1, sr1=sr1, n2=n2, sr2=sr2, unabhaengigkeit=unabhaengigkeit
        )

    if guete(obergrenze) < ziel:
        return None
    tief, hoch = -obergrenze, obergrenze
    for _ in range(90):
        mitte = (tief + hoch) / 2
        if guete(mitte) < ziel:
            tief = mitte
        else:
            hoch = mitte
    return hoch


@dataclass(frozen=True, slots=True)
class Anwaerter:
    """Ein moeglicher Partner mit dem, was von ihm bekannt ist."""

    name: str
    trades: int
    sharpe_je_trade: float
    unabhaengigkeit: float | None = None
    """Gemessen, wenn der Verbund schon gerechnet wurde - sonst unbekannt."""


@dataclass(slots=True)
class Partnerkarte:
    """Die Anforderung an einen Partner, aufgeschluesselt."""

    n1: int
    sr1: float
    ziel: float
    grade: tuple[float, ...] = GEMESSENE_GRADE

    def bedarf(self, trades: int, unabhaengigkeit: float) -> float | None:
        return noetiges_sharpe(
            n1=self.n1,
            sr1=self.sr1,
            n2=trades,
            unabhaengigkeit=unabhaengigkeit,
            ziel=self.ziel,
        )

    def reicht(self, anwaerter: Anwaerter, unabhaengigkeit: float) -> bool:
        noetig = self.bedarf(anwaerter.trades, unabhaengigkeit)
        return noetig is not None and anwaerter.sharpe_je_trade >= noetig

    def tabelle(self, trades: tuple[int, ...] = (50, 100, 154, 250, 400)) -> str:
        kopf = f"{'Trades':<8}" + "".join(f"{f'u={u:.2f}':>10}" for u in self.grade)
        zeilen = [kopf, "-" * len(kopf)]
        for n2 in trades:
            zeile = f"{n2:<8}"
            for u in self.grade:
                wert = self.bedarf(n2, u)
                zeile += f"{wert:>10.4f}" if wert is not None else f"{'-':>10}"
            zeilen.append(zeile)
        return "\n".join(zeilen)

    def einordnung(self, anwaerter: list[Anwaerter]) -> str:
        """Bekannte Kandidaten gegen ihre eigene Anforderung."""
        zeilen = [
            f"{'Kandidat':<30} {'Trades':>7} {'SR':>8} {'noetig':>8} {'fehlt':>8}",
            "-" * 64,
        ]
        for a in sorted(anwaerter, key=lambda x: -x.trades):
            u = a.unabhaengigkeit if a.unabhaengigkeit is not None else 0.72
            noetig = self.bedarf(a.trades, u)
            if noetig is None:
                zeilen.append(
                    f"{a.name[:30]:<30} {a.trades:>7} {a.sharpe_je_trade:>8.4f} "
                    f"{'unerreichbar':>17}"
                )
                continue
            luecke = noetig - a.sharpe_je_trade
            zeilen.append(
                f"{a.name[:30]:<30} {a.trades:>7} {a.sharpe_je_trade:>8.4f} "
                f"{noetig:>8.4f} {luecke:>+8.4f}"
            )
        return "\n".join(zeilen)

    @property
    def wende(self) -> int | None:
        """Ab wie vielen Trades ein Partner mit **der Qualitaet des Bestands**
        genuegen wuerde - beim mittleren gemessenen Grad.

        Die Zahl, die die Suchrichtung dreht: Liegt sie in erreichbarer Naehe,
        ist nicht Qualitaet gefragt, sondern Menge.
        """
        u = 0.72 if 0.72 in self.grade else self.grade[len(self.grade) // 2]
        for n2 in range(10, 2001, 5):
            noetig = self.bedarf(n2, u)
            if noetig is not None and noetig <= self.sr1:
                return n2
        return None

    def urteil(self) -> str:
        wende = self.wende
        if wende is None:
            return (
                "**Kein Partner mit der Qualitaet des Bestands genuegt**, "
                "wie viele Trades er auch mitbraechte. Dann fuehrt ueber den "
                "Verbund kein Weg."
            )
        return (
            f"**Ab {wende} Trades genuegt ein Partner mit der Qualitaet des "
            f"Bestands** ({self.sr1:.4f} je Trade), beim gemessenen "
            f"Unabhaengigkeitsgrad von 0,72.\n\n"
            f"Das dreht die Suchrichtung um. Bisher wurde nach **besseren** "
            f"Regeln gesucht; gebraucht wird eine, die **genug handelt und "
            f"anders ist**. Die Qualitaet darf sogar unter der des Bestands "
            f"liegen - bei 250 Trades reichen "
            f"{self.bedarf(250, 0.72) or 0:.4f}.\n\n"
            f"Die Naeherung ist dabei die freundliche Richtung: Wo sich die "
            f"Verteilungen unterscheiden, waechst die Streuung der Mischung, "
            f"und der wirkliche Wert liegt darunter."
        )


@dataclass(slots=True)
class Katalogkopplung:
    """Gilt die Kopplung aus Befund 54 auch **ueber** die Regeln hinweg?

    Befund 54 hat sie an **einem** Kandidaten gemessen: Wer den
    Spitzenkandidaten oefter handeln laesst, verliert an Qualitaet, was er an
    Menge gewinnt. Ob das eine Eigenschaft jener Regel ist oder des ganzen
    Regelvorrats, war damit nicht entschieden.

    Ueber 14 verschiedene Genome der Tageskerzen-Generationen gemessen:
    **r = -0,533**. Die Kopplung ist keine Eigenschaft des Spitzenkandidaten,
    sondern des Katalogs - und sie erklaert, warum die Partnerkarte leer
    ausgeht: Sie verlangt Menge **und** Qualitaet, und der Vorrat liefert
    immer nur eines von beidem.

    Mit t = -2,18 liegt es knapp ueber der Schwelle, die dieses Projekt
    ueberall verwendet (|t| >= 2). Knapp heisst knapp: Bei 14 Punkten haette
    ein einzelnes anderes Genom das Vorzeichen der Aussage nicht gedreht, wohl
    aber ihre Auffaelligkeit. Es ist ein Befund am Rand, und er steht hier als
    solcher.
    """

    anwaerter: list[Anwaerter] = field(default_factory=list)

    @property
    def genug(self) -> bool:
        return len(self.anwaerter) >= 4

    @property
    def korrelation(self) -> float | None:
        """Zwischen Trade-Zahl und Qualitaet je Trade."""
        if not self.genug:
            return None
        trades = [float(a.trades) for a in self.anwaerter]
        sharpe = [a.sharpe_je_trade for a in self.anwaerter]
        n = len(trades)
        mt, ms = sum(trades) / n, sum(sharpe) / n
        oben = sum((t - mt) * (s - ms) for t, s in zip(trades, sharpe, strict=True))
        unten = (
            sum((t - mt) ** 2 for t in trades) * sum((s - ms) ** 2 for s in sharpe)
        ) ** 0.5
        return oben / unten if unten > 0 else None

    @property
    def t_wert(self) -> float | None:
        """Wie weit die Korrelation von null entfernt ist, in Standardfehlern."""
        r = self.korrelation
        if r is None or abs(r) >= 1.0:
            return None
        n = len(self.anwaerter)
        return r * ((n - 2) / (1 - r**2)) ** 0.5

    @property
    def auffaellig(self) -> bool:
        """``|t| >= 2`` - die uebliche Schwelle dieses Projekts."""
        t = self.t_wert
        return t is not None and abs(t) >= 2.0

    def urteil(self) -> str:
        r = self.korrelation
        if r is None:
            return "Zu wenige Anwaerter - ueber die Kopplung laesst sich nichts sagen."
        t = self.t_wert or 0.0
        if not self.auffaellig:
            # **Ohne Auffaelligkeit keine Schlussfolgerung.** Der erste Anlauf
            # zog sie trotzdem - und lieferte an fuenf Bestenlisten-Eintraegen
            # r = +0,359, also das Gegenteil des Befunds ueber 14 Genome, mit
            # demselben Begleittext. Eine Korrelation ohne Deckung darf nicht
            # klingen wie eine mit.
            return (
                f"**Ueber die Kopplung sagen diese {len(self.anwaerter)} "
                f"Anwaerter nichts.** Gemessen r = {r:+.3f} bei t = {t:+.2f} - "
                f"unter der Schwelle von 2, ab der dieses Projekt von einem "
                f"Befund spricht. Bei so wenigen Punkten dreht ein einzelner "
                f"das Vorzeichen."
            )
        richtung = (
            "Wer viel handelt, handelt schlechter"
            if r < 0
            else "Menge und Qualitaet gehen zusammen"
        )
        return (
            f"**Die Kopplung gilt auch ueber die Regeln hinweg: r = {r:+.3f}.** "
            f"{richtung}, ueber {len(self.anwaerter)} Genome mit "
            f"t = {t:+.2f}.\n\n"
            f"Befund 54 hatte sie an **einem** Kandidaten gemessen, durch "
            f"Verstellen seiner Regler. Sie ist damit keine Eigenschaft jener "
            f"Regel, sondern des Vorrats - und sie erklaert, warum die "
            f"Partnerkarte leer ausgeht: Sie verlangt Menge **und** Qualitaet, "
            f"und der Vorrat liefert immer nur eines."
        )

    def nullprobe(
        self, *, durchlaeufe: int = 20_000, saat: int = 20260816
    ) -> tuple[float, float]:
        """Erzeugt reines Messrauschen die Kopplung von allein?

        **Die Alternativerklaerung, die zuerst zu widerlegen war.** Der Sharpe
        je Trade ist selbst geschaetzt, mit einer Streuung von ``1/sqrt(n-1)``
        je Regel. Seltene Regeln streuen also breiter - 'Enge vor Bewegung'
        mit 18 Trades traegt ein Rauschen von 0,243, und ihr gemessener Wert
        von 0,3405 ist nur 1,4 Standardfehler von null entfernt.

        Bei so ungleichen Trade-Zahlen kann eine Korrelation entstehen, ohne
        dass irgendein Zusammenhang da waere. Deshalb wird gegen eine
        **bekannte Null** gezogen: dieselben Trade-Zahlen, jede Regel mit
        wahrem Vorteil null, nur ihr eigenes Messrauschen.

        Gibt Mittel und Streuung der Nullverteilung zurueck. Gemessen ergab
        sie -0,000 +- 0,193 - der beobachtete Wert von -0,602 liegt weit
        ausserhalb, nur 0,02 % der Durchlaeufe kommen dorthin.
        """
        from research.aussagekraft import messrauschen

        if not self.genug:
            return (float("nan"), float("nan"))
        trades = np.array([float(a.trades) for a in self.anwaerter])
        rauschen = np.array([messrauschen(a.trades) for a in self.anwaerter])
        zufall = np.random.default_rng(saat)
        gezogen = zufall.normal(0.0, 1.0, size=(durchlaeufe, len(trades))) * rauschen
        mittig = trades - trades.mean()
        norm = np.sqrt((mittig**2).sum())
        werte = gezogen - gezogen.mean(axis=1, keepdims=True)
        laenge = np.sqrt((werte**2).sum(axis=1))
        laenge[laenge == 0] = np.nan
        verteilung = (werte @ mittig) / (norm * laenge)
        return (float(np.nanmean(verteilung)), float(np.nanstd(verteilung)))

    @property
    def ueber_dem_rauschen(self) -> bool:
        """Liegt die gemessene Kopplung ausserhalb dessen, was Rauschen
        hergibt? Drei Streuungen der Nullverteilung."""
        r = self.korrelation
        mittel, streuung = self.nullprobe()
        if r is None or not np.isfinite(streuung) or streuung == 0:
            return False
        return abs(r - mittel) > 3 * streuung

    def gerade(self) -> tuple[float, float, float] | None:
        """Steigung, Achsenabschnitt und Reststreuung der Kopplung.

        Damit laesst sich vorhersagen, welche Qualitaet bei einer Trade-Zahl
        zu erwarten ist - und wie weit eine Anforderung darueber liegt.
        """
        if len(self.anwaerter) < 4:
            return None
        trades = np.array([float(a.trades) for a in self.anwaerter])
        sharpe = np.array([a.sharpe_je_trade for a in self.anwaerter])
        steigung, abschnitt = np.polyfit(trades, sharpe, 1)
        rest = sharpe - (steigung * trades + abschnitt)
        return (
            float(steigung),
            float(abschnitt),
            float(np.std(rest, ddof=2)),
        )

    def trefferquote(self, *, trades: int, ziel: float) -> tuple[float, float] | None:
        """Wie oft eine Regel diese Anforderung erreicht - gemessen und echt.

        Der Unterschied ist der Winner's Curse: Die Reststreuung um die Gerade
        enthaelt das Messrauschen mit. Eine Regel, die die Anforderung
        **gemessen** erfuellt, hat sie deshalb oft nur zufaellig erfuellt.
        Bei 120 Trades sind 56 % der Restvarianz Rauschen.
        """
        from statistics import NormalDist

        from research.aussagekraft import messrauschen, zerlege

        angepasst = self.gerade()
        if angepasst is None:
            return None
        steigung, abschnitt, rest = angepasst
        erwartet = steigung * trades + abschnitt
        echt = zerlege(rest, messrauschen(trades))
        normal = NormalDist()
        gemessen = 1 - normal.cdf((ziel - erwartet) / rest) if rest > 0 else 0.0
        wirklich = (
            1 - normal.cdf((ziel - erwartet) / echt)
            if echt is not None and echt > 0
            else 0.0
        )
        return (float(gemessen), float(wirklich))

    def guete_bei(self, trades: int) -> float | None:
        """Welche Guete eine **durchschnittliche** Regel dieser Taktung traegt.

        ``(a + b*n) * sqrt(n)`` entlang der Kopplungsgeraden. Die Kurve hat
        ein Maximum - mehr Trades helfen nur, solange der Qualitaetsverlust
        langsamer waechst als die Wurzel.
        """
        angepasst = self.gerade()
        if angepasst is None or trades < 1:
            return None
        steigung, abschnitt, _ = angepasst
        return (abschnitt + steigung * trades) * trades**0.5

    @property
    def guetedeckel(self) -> tuple[int, float] | None:
        """Die beste Guete, die die Kopplung im Durchschnitt hergibt.

        **Die ernuechterndste Zahl des Projekts.** Gemessen liegt sie bei
        1,281 bei 77 Trades - das Gate verlangt 3,629. Eine durchschnittliche
        Regel erreicht es also nicht annaehernd; jeder Kandidat, der es
        schaffen soll, muss ein Ausreisser sein.
        """
        angepasst = self.gerade()
        if angepasst is None:
            return None
        steigung, abschnitt, _ = angepasst
        if steigung >= 0:
            return None
        beste = -abschnitt / (3 * steigung)
        n = max(1, round(beste))
        wert = self.guete_bei(n)
        return (n, wert) if wert is not None else None

    def noetiger_ausreisser(self, *, trades: int, ziel: float) -> float | None:
        """Wie weit ueber der Geraden ein Kandidat liegen muesste - in
        Reststreuungen."""
        angepasst = self.gerade()
        if angepasst is None or trades < 1:
            return None
        steigung, abschnitt, rest = angepasst
        if rest <= 0:
            return None
        return (ziel / trades**0.5 - abschnitt - steigung * trades) / rest

    def bester_takt(
        self, *, ziel: float, spanne: tuple[int, int] = (40, 800), echt: bool = True
    ) -> tuple[int, float] | None:
        """Bei welcher Trade-Zahl ein Einzelkandidat die beste Chance hat.

        ``echt=True`` rechnet das Messrauschen aus der Reststreuung heraus -
        und verschiebt das Optimum spuerbar: gemessen liegt es bei 153 Trades
        (3,62 %), echt bei 197 (1,12 %). Der Grund ist, dass bei mehr Trades
        weniger von der Reststreuung Rauschen ist, ein Treffer dort also
        haeufiger echt.
        """
        from statistics import NormalDist

        from research.aussagekraft import messrauschen, zerlege

        angepasst = self.gerade()
        if angepasst is None:
            return None
        steigung, abschnitt, rest = angepasst
        normal = NormalDist()
        beste: tuple[int, float] | None = None
        for n in range(max(2, spanne[0]), spanne[1] + 1):
            streuung = zerlege(rest, messrauschen(n)) if echt else rest
            if streuung is None or streuung <= 0:
                continue
            z = (ziel / n**0.5 - abschnitt - steigung * n) / streuung
            p = 1 - normal.cdf(z)
            if beste is None or p > beste[1]:
                beste = (n, float(p))
        return beste

    def rest_bereich(self, *, irrtum: float = 0.10) -> tuple[float, float] | None:
        """Wie unsicher die Reststreuung selbst ist.

        **Der Vorbehalt, der zu allen Trefferquoten gehoert.** Sie ist aus 18
        Punkten geschaetzt, mit zwei Parametern fuer die Gerade - also 16
        Freiheitsgrade. Der 90-Prozent-Bereich reicht von 0,096 bis 0,174,
        und die Trefferquote reagiert darauf extrem empfindlich: Bei 154
        Trades sind es 0,11 % am unteren und 15,5 % am oberen Rand.

        Wer eine Trefferquote auf zwei Stellen nennt, ohne diesen Bereich
        danebenzustellen, behauptet mehr als er weiss - und genau das ist mir
        in Befund 79 und 80 passiert.
        """
        from research.aussagekraft import chi2_quantil

        angepasst = self.gerade()
        if angepasst is None:
            return None
        rest = angepasst[2]
        freiheitsgrade = len(self.anwaerter) - 2
        if freiheitsgrade < 1 or rest <= 0:
            return None
        return (
            rest * (freiheitsgrade / chi2_quantil(1 - irrtum / 2, freiheitsgrade)) ** 0.5,
            rest * (freiheitsgrade / chi2_quantil(irrtum / 2, freiheitsgrade)) ** 0.5,
        )

    def takt_bereich(
        self, *, ziel: float, karte, unabhaengigkeit: float = 0.72
    ) -> dict | None:
        """Die beste Partner-Taktung - samt der Bandbreite, die sie hat.

        ``karte`` ist eine ``Partnerkarte``; sie liefert die Anforderung bei
        einer Trade-Zahl, die Kopplung die Erwartung. Wo beide sich am
        wenigsten widersprechen, ist die Suche am aussichtsreichsten.

        Gibt Optimum und Trefferquote fuer die gemessene Reststreuung **und**
        fuer beide Raender ihres Vertrauensbereichs. Das Optimum erweist sich
        dabei als robust (142 bis 202 Trades), die Trefferquote nicht.
        """
        from statistics import NormalDist

        from research.aussagekraft import messrauschen, zerlege

        angepasst = self.gerade()
        bereich = self.rest_bereich()
        if angepasst is None or bereich is None:
            return None
        steigung, abschnitt, rest = angepasst
        normal = NormalDist()

        def optimum(streuung_gesamt: float) -> tuple[int, float] | None:
            beste: tuple[int, float] | None = None
            for n in range(60, 601):
                echt = zerlege(streuung_gesamt, messrauschen(n))
                noetig = karte.bedarf(n, unabhaengigkeit)
                if echt is None or echt <= 0 or noetig is None:
                    continue
                p = 1 - normal.cdf(
                    (noetig - (abschnitt + steigung * n)) / echt
                )
                if beste is None or p > beste[1]:
                    beste = (n, float(p))
            return beste

        gefunden = {
            "gemessen": optimum(rest),
            "unten": optimum(bereich[0]),
            "oben": optimum(bereich[1]),
        }
        if gefunden["gemessen"] is None:
            return None
        takte = [w[0] for w in gefunden.values() if w is not None]
        quoten = [w[1] for w in gefunden.values() if w is not None]
        return {
            **gefunden,
            "takt_spanne": (min(takte), max(takte)),
            "quoten_spanne": (min(quoten), max(quoten)),
        }

    def urteil_takt(self, *, ziel: float, karte) -> str:
        lage = self.takt_bereich(ziel=ziel, karte=karte)
        if lage is None:
            return "Zu wenige Punkte - ueber die beste Taktung laesst sich nichts sagen."
        takt, quote = lage["gemessen"]
        von, bis = lage["takt_spanne"]
        q_von, q_bis = lage["quoten_spanne"]
        return (
            f"**Ein Verbund-Partner sollte rund {takt} Trades bringen.** Ueber "
            f"den ganzen Vertrauensbereich der Reststreuung liegt das Optimum "
            f"zwischen {von} und {bis} - die Aussage ist robust.\n\n"
            f"**Die Trefferquote ist es nicht.** Gemessen {quote:.1%}, aber "
            f"zwischen {q_von:.2%} und {q_bis:.1%}, je nachdem wo die "
            f"Reststreuung wirklich liegt. Das ist ein Faktor "
            f"{q_bis / q_von:.0f}, und wer hier eine Zahl auf zwei Stellen "
            f"nennt, behauptet mehr als er weiss."
        )
