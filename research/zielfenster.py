"""Was die offenen Gates von denselben Trades fordern (Befund 269).

Die Frage
---------
Der Bestand haelt am Spot-Punkt 9 von 11 Gates. Offen sind zwei, und sie
fordern Verschiedenes von **denselben** Trades:

    Betriebsschwelle   >= 15 % im Jahr    eine Forderung an die **Summe**
    Deflated Sharpe    >= 0,95            eine Forderung an das **Verhaeltnis**
                                          aus Mittelwert und Streuung

Seit Befund 104 steht im Docstring von ``cli marktkombinationen`` die Sorge,
die daraus folgt: *"Steigt der Deflated Sharpe ueber die Schwelle, faellt
womoeglich die Messlatte darunter - beide Gates zugleich zu halten ist die
eigentliche Frage."* Beantwortet hat sie niemand.

Zwei Wege, und nur einer traegt
-------------------------------
**Skalieren** heisst groessere Positionen bei gleicher Regel. Summe und
Streuung wachsen um denselben Faktor, das Verhaeltnis bleibt - der Sharpe je
Trade und mit ihm der Deflated Sharpe ruehren sich nicht. Der Rueckgang
waechst mit. Gemessen am Bestand: Faktor 1,2586 fuer die Schwelle, Rueckgang
von 9,87 auf 12,42 % und damit **ueber** die Drawdown-Grenze von 12,0.
Skalieren loest kein Gate und reisst ein drittes.

**Verbessern** heisst mehr Ertrag je Trade bei gleicher Streuung. Das hebt
den Sharpe mit, und beide Gates fallen zusammen. Gemessen am Bestand:

    noetig    +25,9 % Ertrag je Trade
    dann      Sharpe je Trade 0,3408 gegen noetige 0,3387
    dann      Deflated Sharpe 0,9595 - haelt, mit 0,01 Luft
    Rueckgang bleibt 9,87 %

**Die beiden Gates ziehen nicht gegeneinander.** Ein einziger Fortschritt
loest beide - vorausgesetzt, er kommt aus der Regel und nicht aus der
Positionsgroesse.

Und das Budget ist knapper als der Plan
---------------------------------------
Die 0,01 Luft sind der ganze Spielraum, und jeder Versuch hebt die Latte.
**Das Fenster schliesst sich bei 231 Versuchen** - der Plan sieht 230 vor.
Der Puffer ist also null: Was noch bleibt, sind rund dreissig Versuche, und
danach verfehlt auch der richtige Fund das Ziel.

Der Ausweg ist dann nicht mehr Suche, sondern **mehr effektive Stichprobe**:
Die Latte haengt an ihr und sinkt mit ihr. Befund 268 hat gezeigt, dass
Verbreiterung die Trade-Zahl hebt und den Ertrag je Trade senkt - gesucht ist
das eine ohne das andere.

Wie belastbar ist die 231?
--------------------------
**Maessig, und das gehoert dazu.** Sie haengt empfindlich an Schiefe und
Woelbung: Mit 3,376/15,415 statt der gemessenen 3,4646/15,9173 faellt sie auf
214 - siebzehn Versuche Unterschied bei 0,09 in der Schiefe. Belastbar ist
die Groessenordnung, nicht die Stelle: Grenze und Planbudget liegen
beieinander, und das heisst kein Puffer.

Zwei Rechenfehler auf dem Weg hierher, beide meine:
Der erste Anlauf verglich den ueber 158 Trades noetigen Mittelwert mit dem
Ist-Mittelwert der 156 gehandelten und kam auf +32,6 % statt +25,9 % - der
Faktor gehoert auf die **Summe**. Der zweite uebernahm Schiefe und Woelbung
aus einem Lauf ueber alle Trades statt ueber die gehandelten und kam auf 214
statt 231.

Was diese Rechnung nicht ist
----------------------------
**Kein Versprechen.** Sie sagt, was noetig waere, nicht dass es zu finden
ist. Sie haelt Streuung, Schiefe, Woelbung und Trade-Zahl fest; eine bessere
Regel haette andere Momente, und dann verschiebt sich die Latte. Es ist eine
**Richtungsangabe**: Gesucht wird Ertrag je Trade, nicht Ruhe - der Bestand
ist an der Streuung nicht knapp.

Kostet keinen Versuch: gerechnet wird auf einem vorhandenen Handelsbuch.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.erreichbarkeit import bewerte, noetiger_sharpe

#: Anfangskapital jedes Backtests - die Bezugsgroesse der Jahresrendite.
KAPITAL = 500.0


@dataclass(frozen=True, slots=True)
class Handelsbuch:
    """Was ein Lauf hinterlaesst, in den Groessen, die die Gates lesen."""

    trades_gesamt: int
    """Alle Trades - sie tragen Rendite und Rueckgang."""

    effektiv: int
    """Die effektive Stichprobe, wie das Gate sie sieht (Befund 135/139).

    **Nicht die rohe Zahl.** Mit ihr faellt der Deflated Sharpe um ein
    Vielfaches zu guenstig aus - beim Bestand 0,92 statt 0,59. Der Fehler ist
    in Befund 139 schon einmal gefunden worden und mir beim ersten Anlauf zu
    269 noch einmal unterlaufen.
    """

    mittel: float
    """Mittelwert je Trade, in Euro, auf den gehandelten Trades."""

    streuung: float
    """Streuung je Trade, in Euro, auf den gehandelten Trades."""

    summe: float
    """Summe aller Trades, in Euro - auch der am Datenende glattgestellten."""

    rueckgang_pct: float
    jahre: float

    @property
    def sharpe_je_trade(self) -> float:
        return self.mittel / self.streuung if self.streuung else 0.0


@dataclass(frozen=True, slots=True)
class Weg:
    """Ein Weg zur Schwelle und was er an den anderen Gates anrichtet."""

    name: str
    faktor: float
    """Um wie viel der Ertrag je Trade steigen muesste."""

    sharpe_danach: float
    dsr_danach: float
    rueckgang_danach: float
    haelt_dsr: bool
    haelt_rueckgang: bool

    @property
    def traegt(self) -> bool:
        return self.haelt_dsr and self.haelt_rueckgang


def noetige_summe(jahre: float, schwelle_pct: float, kapital: float = KAPITAL) -> float:
    """Welche Summe aller Trades die Jahresrendite-Schwelle traegt."""
    if jahre <= 0:
        return 0.0
    return kapital * ((1 + schwelle_pct / 100) ** jahre - 1)


def skalieren(
    buch: Handelsbuch,
    *,
    schwelle_pct: float,
    dsr_ziel: float,
    drawdown_grenze: float,
    versuche: int,
    schiefe: float = 0.0,
    woelbung: float = 3.0,
) -> Weg:
    """Groessere Positionen bei gleicher Regel.

    Zaehler und Nenner wachsen gleich: Der Sharpe je Trade bleibt, wo er ist,
    und der Deflated Sharpe mit ihm. Was sich bewegt, ist der Rueckgang.
    """
    faktor = _faktor(buch, schwelle_pct)
    dsr = bewerte(
        trades=buch.effektiv, sharpe=buch.sharpe_je_trade, trials=versuche,
        skew=schiefe, kurtosis=woelbung,
    ).dsr
    rueckgang = buch.rueckgang_pct * faktor
    return Weg(
        name="skalieren",
        faktor=faktor,
        sharpe_danach=buch.sharpe_je_trade,
        dsr_danach=dsr,
        rueckgang_danach=rueckgang,
        haelt_dsr=dsr >= dsr_ziel,
        haelt_rueckgang=rueckgang <= drawdown_grenze,
    )


def verbessern(
    buch: Handelsbuch,
    *,
    schwelle_pct: float,
    dsr_ziel: float,
    drawdown_grenze: float,
    versuche: int,
    schiefe: float = 0.0,
    woelbung: float = 3.0,
) -> Weg:
    """Mehr Ertrag je Trade bei **gleicher** Streuung.

    Der Nenner bleibt stehen, also hebt jeder zusaetzliche Euro den Sharpe
    mit. Der Rueckgang bleibt, wo er ist - er haengt an der Streuung.
    """
    faktor = _faktor(buch, schwelle_pct)
    sharpe = (buch.mittel * faktor) / buch.streuung if buch.streuung else 0.0
    dsr = bewerte(
        trades=buch.effektiv, sharpe=sharpe, trials=versuche,
        skew=schiefe, kurtosis=woelbung,
    ).dsr
    return Weg(
        name="verbessern",
        faktor=faktor,
        sharpe_danach=sharpe,
        dsr_danach=dsr,
        rueckgang_danach=buch.rueckgang_pct,
        haelt_dsr=dsr >= dsr_ziel,
        haelt_rueckgang=buch.rueckgang_pct <= drawdown_grenze,
    )


def _faktor(buch: Handelsbuch, schwelle_pct: float) -> float:
    """Um wie viel der Ertrag steigen muss, damit die Schwelle haelt."""
    ziel = noetige_summe(buch.jahre, schwelle_pct)
    return ziel / buch.summe if buch.summe else float("inf")


@dataclass(frozen=True, slots=True)
class Budgetgrenze:
    """Ab wann die Suche rechnerisch nicht mehr ans Ziel kommt."""

    versuche: int

    gedeckelt: bool
    """Die Suche hat den Deckel erreicht, ohne dass das Fenster zuging.

    Dann ist ``versuche`` **keine** Grenze, sondern die Untergrenze einer:
    Bis dahin traegt es noch. Ohne dieses Feld saehe der guenstigste Fall
    genauso aus wie der schlechteste.
    """

    def __str__(self) -> str:
        return (
            f"traegt ueber {self.versuche} Versuche hinaus"
            if self.gedeckelt
            else f"{self.versuche}"
        )


@dataclass(frozen=True, slots=True)
class Zielfenster:
    """Beide Wege nebeneinander, mit dem Schluss daraus."""

    buch: Handelsbuch
    versuche: int
    schwelle_pct: float
    dsr_ziel: float
    drawdown_grenze: float
    wege: tuple[Weg, ...]

    @property
    def tragende(self) -> tuple[Weg, ...]:
        return tuple(w for w in self.wege if w.traegt)

    @property
    def leer(self) -> bool:
        """Kein Weg traegt - dann ist das Fenster in diesen Groessen zu."""
        return not self.tragende

    def budgetkosten(self, *, bis: int, schiefe: float = 0.0,
                     woelbung: float = 3.0) -> tuple[float, float] | None:
        """Wie stark die Latte bis ``bis`` Versuche steigt.

        Die Zahl, die sagt, ob das restliche Suchbudget der Engpass ist.
        ``None``, wenn die Latte an dieser Stichprobe gar nicht erreichbar
        ist.
        """
        jetzt = noetiger_sharpe(
            effektiv=self.buch.effektiv, trials=self.versuche,
            skew=schiefe, kurtosis=woelbung, ziel=self.dsr_ziel,
        )
        spaeter = noetiger_sharpe(
            effektiv=self.buch.effektiv, trials=bis,
            skew=schiefe, kurtosis=woelbung, ziel=self.dsr_ziel,
        )
        if jetzt is None or spaeter is None:
            return None
        return jetzt, spaeter

    def budgetgrenze(
        self, *, hoechstens: int = 1000, schiefe: float = 0.0, woelbung: float = 3.0
    ) -> Budgetgrenze | None:
        """Ab welcher Versuchszahl auch der tragende Weg nicht mehr traegt.

        **Die Zahl, die das Suchbudget begrenzt - und zwar schaerfer als der
        Plan.** Jeder Versuch hebt die Latte des Deflated Sharpe dauerhaft.
        Wer genau den Kandidaten faende, der die Betriebsschwelle gerade
        traegt, bekaeme ihn ab hier trotzdem nicht mehr durch.

        Gemessen am Bestand liegt sie bei 214, waehrend der Plan 230 Versuche
        vorsieht: Die letzten sechzehn sind rechnerisch schon vergeben.

        ``None`` heisst **eins**: Es traegt schon jetzt kein Weg. Dass die
        Grenze jenseits von ``hoechstens`` liegt, ist der gegenteilige Fall
        und sagt ``Budgetgrenze.gedeckelt`` - beide auf ``None`` abzubilden
        waere genau die Mehrdeutigkeit, die dieses Projekt sonst aufspuert.

        Gesucht wird mit Bisektion: Die Latte steigt monoton mit der
        Versuchszahl.
        """
        args = {
            "schwelle_pct": self.schwelle_pct,
            "dsr_ziel": self.dsr_ziel,
            "drawdown_grenze": self.drawdown_grenze,
            "schiefe": schiefe,
            "woelbung": woelbung,
        }
        if not verbessern(self.buch, versuche=self.versuche, **args).traegt:
            return None
        if verbessern(self.buch, versuche=hoechstens, **args).traegt:
            return Budgetgrenze(versuche=hoechstens, gedeckelt=True)

        tief, hoch = self.versuche, hoechstens
        while hoch - tief > 1:
            mitte = (tief + hoch) // 2
            if verbessern(self.buch, versuche=mitte, **args).traegt:
                tief = mitte
            else:
                hoch = mitte
        return Budgetgrenze(versuche=hoch, gedeckelt=False)

    def urteil(self) -> str:
        if self.leer:
            return (
                "Kein Weg zur Schwelle haelt die uebrigen Gates - in diesen "
                "Groessen ist das Fenster zu."
            )
        namen = ", ".join(w.name for w in self.tragende)
        traegt = self.tragende[0]
        return (
            f"Zur Schwelle fuehrt: {namen}. Noetig sind "
            f"{(traegt.faktor - 1) * 100:+.1f} % Ertrag je Trade; der "
            f"Deflated Sharpe stuende dann bei {traegt.dsr_danach:.4f} "
            f"(Huerde {self.dsr_ziel}) und der Rueckgang bei "
            f"{traegt.rueckgang_danach:.2f} % (Grenze "
            f"{self.drawdown_grenze}). **Die Gates ziehen nicht "
            f"gegeneinander** - gesucht wird Ertrag je Trade, nicht Ruhe."
        )


def vermesse(
    buch: Handelsbuch,
    *,
    versuche: int,
    schwelle_pct: float,
    dsr_ziel: float,
    drawdown_grenze: float,
    schiefe: float = 0.0,
    woelbung: float = 3.0,
) -> Zielfenster:
    """Beide Wege rechnen und nebeneinanderstellen."""
    args = {
        "schwelle_pct": schwelle_pct,
        "dsr_ziel": dsr_ziel,
        "drawdown_grenze": drawdown_grenze,
        "versuche": versuche,
        "schiefe": schiefe,
        "woelbung": woelbung,
    }
    return Zielfenster(
        buch=buch,
        versuche=versuche,
        schwelle_pct=schwelle_pct,
        dsr_ziel=dsr_ziel,
        drawdown_grenze=drawdown_grenze,
        wege=(skalieren(buch, **args), verbessern(buch, **args)),
    )


__all__ = [
    "KAPITAL",
    "Budgetgrenze",
    "Handelsbuch",
    "Weg",
    "Zielfenster",
    "noetige_summe",
    "skalieren",
    "verbessern",
    "vermesse",
]
