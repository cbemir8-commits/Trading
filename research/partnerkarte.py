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
