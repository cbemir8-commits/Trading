"""Ein bestandenes Gate, das am Kontostand haengt.

Die Beobachtung, aus der das kam
--------------------------------
Befund 94 legte eine Reglertabelle vor, und beim Nachrechnen fiel etwas auf:
Das Verhaeltnis Rendite/Rueckgang sprang zwischen den Stufen hin und her -
1,223 bei Vola-Ziel 14, dann 1,298, dann 1,266, und bei 21 faellt es auf
1,152. Ein Groessenregler skaliert jede Position mit demselben Faktor. So
etwas darf nicht ruckeln.

Die Ursache
-----------
Bybit handelt BTC in Schritten von **0,001** und ETH in Schritten von
**0,01**. Die berechnete Menge wird darauf **abgerundet**. Bei 500 EUR Konto
und rund 38 % Kapitalanteil steht auf BTC eine Position von etwa 190 EUR -
bei 60.000 USD je BTC sind das drei Mengenschritte. Der Regler hat dort also
eine Aufloesung von einem Drittel der Position.

Gemessen wird die Verstuemmelung so: mittlere Umsetzung, also gerundete
Menge geteilt durch berechnete, ueber alle Balken des Testzeitraums.

    BTC bei    500 EUR    0,893
    BTC bei 50.000 EUR    0,999
    ETH bei    500 EUR    0,936
    ETH bei 50.000 EUR    0,999

Elf Prozent der geplanten BTC-Position kommen bei 500 EUR gar nicht zustande.

Was das mit dem Gate macht
--------------------------
Am Betriebspunkt des Bestands (Vola-Ziel 19,3), sonst unveraendert:

    Konto        Rendite   Rueckgang   Verhaeltnis   Gate (<= 12 %)
       300 EUR    12,61 %      9,92 %        1,271   haelt
       500 EUR    13,47 %     10,64 %        1,266   haelt
     1.000 EUR    13,50 %     11,84 %        1,140   haelt
     1.500 EUR    13,79 %     12,36 %        1,116   **reisst**
    10.000 EUR    13,86 %     12,84 %        1,080   reisst
   100.000 EUR    13,89 %     12,95 %        1,072   reisst

Die Rendite bewegt sich ueber den ganzen Bereich um 1,3 Punkte, der Rueckgang
um 3,0. **Es ist kein "kleinere Positionen, also kleinere Zahlen".** Der
Rueckgang haengt am Konto, die Rendite fast nicht.

Zwei Gegenproben, zwei Wege, dasselbe Ergebnis
----------------------------------------------
Die Rundung laesst sich auf zwei voellig verschiedene Arten aus dem Weg
raeumen:

1. **Feiner Mengenschritt** - dieselben 500 EUR, aber 1e-8 statt 0,001 BTC.
2. **Groesseres Konto** - Bybits echter Schritt, aber 50.000 EUR.

Ergebnis: **12,96 %** und **12,94 %**. Zwei unabhaengige Eingriffe, 0,02
Punkte auseinander - und beide 2,3 Punkte von der Ausgangsmessung entfernt.
Damit ist die Mengenrundung nicht eine plausible Erklaerung, sondern die
gemessene.

Warum die Rundung ausgerechnet den Rueckgang trifft
---------------------------------------------------
Die Groessensteuerung ist ein Vola-Ziel: In stuermischen Phasen faellt der
Kapitalanteil, die Position wird klein - und kleine Positionen sind genau
die, die das Abrunden am staerksten verstuemmelt. Die mittlere Umsetzung
liegt in der stuermischen Haelfte der Balken um 1,5 Punkte unter der ruhigen.

Das kleine Konto bekommt damit **einen zweiten, unbeabsichtigten Vola-Filter
geschenkt**, und der wirkt genau im Baerenmarkt 2022, aus dem der Rueckgang
stammt (Befund 93).

Was daraus folgt - und was ausdruecklich nicht
----------------------------------------------
**Nicht:** dass mit 500 EUR gestartet werden soll, weil dort mehr Gates
halten. Das waere dieselbe Sorte Anpassung, gegen die die ganze
Zulassungsstrecke gebaut ist.

**Sondern:** Das Rueckgang-Gate steht beim Bestand auf 8 von 11, und es haelt
nur, solange das Konto klein bleibt. Wer es von 500 auf 2.000 EUR vergroessert,
aendert an der Strategie nichts und reisst das Gate trotzdem. Der Uebergang
liegt bei rund **1.150 EUR**.

Und was die uebrigen neun Gates dazu sagen (Befund 96)
------------------------------------------------------
Zwei Kennzahlen ueber die Leiter zu fahren und die anderen neun Gates nicht
anzusehen waere eine Annahme gewesen. Alle elf, derselbe Versuchsstand in
jeder Zeile:

    Gate                     300 EUR   500 EUR   2.000 EUR   100.000 EUR
    Drawdown                 + 9,92    +10,64    -12,56      -12,95
    Schlechtestes Jahr       - 9,60    -10,32    -12,23      -12,61
    Deflated Sharpe          - 0,772   - 0,783   - 0,782     - 0,778
    (acht weitere)             fest      fest      fest        fest
    ------------------------------------------------------------------
    bestanden                  8/11      7/11      6/11        6/11

**Genau zwei Gates wandern**, und es sind die beiden Risikomasse auf der
Kapitalkurve. Neun stehen still, darunter das haerteste: Der Deflated Sharpe
bewegt sich ueber den ganzen Bereich um 0,011 - die Koernung ist kein Weg
dorthin.

Die 8 von 11 bei 300 EUR sind **keine bessere Bilanz.** Es ist dieselbe
Strategie mit einer groeberen Treppe. Die Zahl, die nicht am Kontostand
haengt, ist die am oberen Ende: **6 von 11.**

Kostet keinen Versuch: Der Versuchszaehler korrigiert das Testen vieler
**Strategie**-Hypothesen. Hier ist die Strategie in jeder Zeile dieselbe;
veraendert wird der Kontostand, und ausgewaehlt wird nichts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise

#: Unterschiede unterhalb dieser Schwelle koennen kein Gate-Urteil drehen.
#: Die Gates entscheiden gegen runde Grenzen (12,00 %) und werden auf zwei
#: Nachkommastellen berichtet; 0,05 Punkte sind darunter. Die Zahl ist damit
#: an die Entscheidung gebunden, die getroffen wird, und nicht gegriffen.
UNERHEBLICH = 0.05

#: Bybits Mengenschritte, wie ``cli._KONTRAKTE`` sie fuehrt.
SCHRITTE: dict[str, float] = {"BTCUSDT": 0.001, "ETHUSDT": 0.01}


@dataclass(frozen=True, slots=True)
class Kontostufe:
    """Eine Sprosse der Leiter: derselbe Kandidat, anderes Startkapital."""

    kapital: float
    cagr: float
    rueckgang: float
    trades: int = 0

    @property
    def verhaeltnis(self) -> float:
        return self.cagr / self.rueckgang if self.rueckgang else 0.0

    def haelt(self, grenze: float) -> bool:
        return self.rueckgang <= grenze


#: Die gemessene Leiter am Betriebspunkt des Bestands (Vola-Ziel 19,3,
#: BTC + ETH, Tageskerzen). Nachzurechnen mit ``cli koernung``.
GEMESSEN: tuple[Kontostufe, ...] = (
    Kontostufe(300.0, 12.61, 9.92, 146),
    Kontostufe(400.0, 13.21, 10.29, 152),
    Kontostufe(500.0, 13.47, 10.64, 152),
    Kontostufe(600.0, 13.40, 11.23, 152),
    Kontostufe(750.0, 13.78, 11.61, 152),
    Kontostufe(1000.0, 13.50, 11.84, 152),
    Kontostufe(1500.0, 13.79, 12.36, 152),
    Kontostufe(2000.0, 13.75, 12.56, 152),
    Kontostufe(3000.0, 13.83, 12.60, 152),
    Kontostufe(5000.0, 13.81, 12.70, 152),
    Kontostufe(10000.0, 13.86, 12.84, 152),
    Kontostufe(25000.0, 13.88, 12.92, 152),
    Kontostufe(50000.0, 13.88, 12.94, 152),
    Kontostufe(100000.0, 13.89, 12.95, 152),
)

#: Dieselbe Rechnung mit 500 EUR, aber einem Mengenschritt von 1e-8. Die
#: Gegenprobe, die nur die Rundung entfernt und sonst nichts.
FEINMESSUNG = Kontostufe(500.0, 13.89, 12.96, 152)


@dataclass(slots=True)
class Koernung:
    """Wie stark eine Gate-Zahl am Kontostand haengt - und woran das liegt."""

    stufen: list[Kontostufe] = field(default_factory=list)
    grenze_pct: float = 12.0
    """Die Schwelle des Rueckgang-Gates."""
    feinmessung: Kontostufe | None = None
    """Dasselbe Konto wie die kleinste Sprosse, aber ohne Mengenrundung."""

    @property
    def geordnet(self) -> list[Kontostufe]:
        return sorted(self.stufen, key=lambda s: s.kapital)

    @property
    def genug(self) -> bool:
        return len(self.stufen) >= 3

    @property
    def spanne(self) -> float:
        """Wie weit der Rueckgang ueber die Leiter wandert, in Punkten."""
        if not self.stufen:
            return 0.0
        werte = [s.rueckgang for s in self.stufen]
        return max(werte) - min(werte)

    @property
    def renditespanne(self) -> float:
        """Dasselbe fuer die Rendite - der Vergleichsmassstab.

        Wandern beide gleich weit, sind die Positionen einfach kleiner und
        es gibt nichts zu erklaeren. Nur wenn der Rueckgang deutlich weiter
        wandert als die Rendite, trifft die Rundung etwas Bestimmtes.
        """
        if not self.stufen:
            return 0.0
        werte = [s.cagr for s in self.stufen]
        return max(werte) - min(werte)

    @property
    def steigt_durchgehend(self) -> bool:
        """Waechst der Rueckgang mit jedem Schritt? Dann ist es kein Rauschen."""
        return self.genug and all(
            b.rueckgang >= a.rueckgang for a, b in pairwise(self.geordnet)
        )

    @property
    def grenzkapital(self) -> float | None:
        """Ab welchem Konto das Gate reisst - zwischen zwei Sprossen linear.

        ``None``, wenn die Leiter den Uebergang nicht einschliesst; dann ist
        er nicht gemessen und wird auch nicht behauptet.
        """
        for links, rechts in pairwise(self.geordnet):
            if links.haelt(self.grenze_pct) and not rechts.haelt(self.grenze_pct):
                weite = rechts.rueckgang - links.rueckgang
                if weite <= 0:
                    return rechts.kapital
                anteil = (self.grenze_pct - links.rueckgang) / weite
                return links.kapital + anteil * (rechts.kapital - links.kapital)
        return None

    @property
    def grenzwert(self) -> float | None:
        """Der Wert, gegen den der Rueckgang bei grossem Konto laeuft."""
        return self.geordnet[-1].rueckgang if self.stufen else None

    @property
    def gegenstueck(self) -> Kontostufe | None:
        """Die Sprosse mit **demselben** Kontostand wie die Feinmessung.

        Sie und nicht die kleinste: Die Feinmessung aendert nur die
        Mengenrundung, und verglichen werden darf sie deshalb nur mit dem
        Lauf, der sich sonst in nichts von ihr unterscheidet. Gegen eine
        andere Sprosse gerechnet stuende im Zaehler zusaetzlich der
        Kontounterschied.
        """
        if self.feinmessung is None:
            return None
        ziel = self.feinmessung.kapital
        passend = [s for s in self.stufen if s.kapital == ziel]
        return passend[0] if passend else None

    @property
    def anteil_erklaert(self) -> float | None:
        """Welchen Teil des Abstands die Feinmessung allein schon erklaert.

        Die Feinmessung aendert **nur** die Mengenrundung: gleicher
        Kontostand, gleiche Strategie, gleiche Daten. Landet sie dort, wo das
        grosse Konto landet, ist die Rundung nicht eine plausible Erklaerung,
        sondern die gemessene.
        """
        gross = self.grenzwert
        basis = self.gegenstueck
        if self.feinmessung is None or gross is None or basis is None:
            return None
        if abs(gross - basis.rueckgang) < UNERHEBLICH:
            return None
        return (self.feinmessung.rueckgang - basis.rueckgang) / (
            gross - basis.rueckgang
        )

    @property
    def koernung_erklaert_es(self) -> bool:
        """Treffen sich die beiden Gegenproben naeher, als ein Gate merkt?

        Zwei voellig verschiedene Eingriffe - feiner Schritt bei kleinem
        Konto, grober Schritt bei grossem - muessen dieselbe Zahl liefern,
        wenn die Rundung die Ursache ist. Tun sie es nicht, wirkt noch etwas
        anderes mit, und dann wird hier auch nichts behauptet.
        """
        gross = self.grenzwert
        if self.feinmessung is None or gross is None:
            return False
        return abs(self.feinmessung.rueckgang - gross) < UNERHEBLICH

    def tabelle(self) -> str:
        zeilen = [
            f"{'Konto':>12}{'Rendite':>10}{'Rueckgang':>12}{'Verh.':>8}  Gate",
            "-" * 54,
        ]
        for s in self.geordnet:
            zeichen = "haelt" if s.haelt(self.grenze_pct) else "reisst"
            zeilen.append(
                f"{s.kapital:>10,.0f} E{s.cagr:>9.2f} %{s.rueckgang:>10.2f} %"
                f"{s.verhaeltnis:>8.3f}  {zeichen}"
            )
        if self.feinmessung is not None:
            zeilen.append("-" * 54)
            zeilen.append(
                f"{'feiner Schritt':>12}{self.feinmessung.cagr:>9.2f} %"
                f"{self.feinmessung.rueckgang:>10.2f} %"
                f"{self.feinmessung.verhaeltnis:>8.3f}  "
                f"{'haelt' if self.feinmessung.haelt(self.grenze_pct) else 'reisst'}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.genug:
            return (
                "Weniger als drei Sprossen - daraus laesst sich ueber die "
                "Abhaengigkeit vom Konto nichts sagen."
            )

        klein, gross = self.geordnet[0], self.geordnet[-1]
        if self.spanne < UNERHEBLICH:
            return (
                f"**Der Rueckgang haengt nicht am Konto.** Ueber {len(self.stufen)} "
                f"Sprossen von {klein.kapital:,.0f} bis {gross.kapital:,.0f} EUR "
                f"bewegt er sich um {self.spanne:.2f} Punkte - unterhalb dessen, "
                f"was ein Gate unterscheidet."
            )

        teile = [
            f"**Der Rueckgang haengt am Kontostand.** Bei "
            f"{klein.kapital:,.0f} EUR misst er {klein.rueckgang:.2f} %, bei "
            f"{gross.kapital:,.0f} EUR {gross.rueckgang:.2f} % - "
            f"{self.spanne:.2f} Punkte Unterschied bei unveraenderter Strategie."
        ]

        # Der Vergleichsmassstab zuerst: Ohne ihn liesse sich das Ganze als
        # "kleineres Konto, kleinere Zahlen" abtun.
        teile.append(
            f"Die Rendite wandert dabei nur um {self.renditespanne:.2f} Punkte. "
            f"Es sind also nicht einfach kleinere Positionen - die Rundung "
            f"trifft den Rueckgang und die Rendite fast nicht."
            + (
                " Der Rueckgang waechst dabei mit jeder Sprosse, ist also kein "
                "Rauschen."
                if self.steigt_durchgehend
                else ""
            )
        )

        grenze = self.grenzkapital
        if grenze is not None:
            teile.append(
                f"**Das Gate ({self.grenze_pct:.0f} %) haelt nur unterhalb von "
                f"rund {grenze:,.0f} EUR.** Wer das Konto darueber hinaus "
                f"vergroessert, aendert an der Strategie nichts und reisst es "
                f"trotzdem."
            )

        if self.feinmessung is not None:
            anteil = self.anteil_erklaert
            belegt = self.koernung_erklaert_es
            vorher = self.gegenstueck
            satz = (
                f"Dieselben {self.feinmessung.kapital:,.0f} EUR mit einem feinen "
                f"Mengenschritt statt Bybits 0,001 BTC ergeben "
                f"{self.feinmessung.rueckgang:.2f} % - gegen "
                f"{gross.rueckgang:.2f} % beim grossen Konto"
                + (
                    f" und {vorher.rueckgang:.2f} % bei demselben Konto mit "
                    f"Bybits Schritt."
                    if vorher is not None
                    else "."
                )
            )
            if belegt:
                satz += (
                    " Zwei voellig verschiedene Eingriffe, dieselbe Zahl: "
                    "**Die Mengenrundung ist die Ursache**, nicht eine "
                    "plausible Erklaerung."
                )
            else:
                satz += (
                    " Die beiden Gegenproben treffen einander nicht - dann "
                    "wirkt neben der Rundung noch etwas anderes mit, und "
                    "welcher Teil worauf entfaellt, ist hier nicht gemessen."
                )
            if anteil is not None:
                satz += f" (Erklaerter Anteil {anteil:.0%}.)"
            teile.append(satz)

        teile.append(
            "**Das ist keine Empfehlung, klein zu bleiben, damit das Gate "
            "haelt.** Das Gate soll messen, ob die Strategie ihr Risiko im "
            "Griff hat; zu einem Teil misst es, ob Bybits Mengenschritt "
            "zufaellig guenstig zum Kontostand liegt."
        )
        return "\n\n".join(teile)


@dataclass(frozen=True, slots=True)
class Gatewert:
    """Ein Gate-Ergebnis auf einer Sprosse der Kontoleiter."""

    name: str
    bestanden: bool
    wert: float
    schwelle: float = 0.0


@dataclass(frozen=True, slots=True)
class Gatelauf:
    """Alle elf Gates bei einem Kontostand."""

    kapital: float
    gates: tuple[Gatewert, ...] = ()

    @property
    def bestanden(self) -> int:
        return sum(1 for g in self.gates if g.bestanden)

    @property
    def gesamt(self) -> int:
        return len(self.gates)

    def gate(self, name: str) -> Gatewert | None:
        return next((g for g in self.gates if g.name == name), None)


@dataclass(slots=True)
class Gateleiter:
    """Welche Gates ihr Urteil aendern, wenn nur der Kontostand sich aendert.

    Ein Gate soll eine Eigenschaft der **Strategie** messen. Aendert sein
    Urteil sich, ohne dass an der Strategie etwas anders ist, misst es zu
    einem Teil etwas anderes - und dann gehoert das benannt.
    """

    laeufe: list[Gatelauf] = field(default_factory=list)

    @property
    def geordnet(self) -> list[Gatelauf]:
        return sorted(self.laeufe, key=lambda x: x.kapital)

    @property
    def genug(self) -> bool:
        return len(self.laeufe) >= 2 and all(x.gates for x in self.laeufe)

    @property
    def namen(self) -> tuple[str, ...]:
        """Nur Gates, die auf **jeder** Sprosse vorkommen.

        Ein Gate, das nur auf einem Teil der Leiter gelaufen ist, laesst sich
        nicht auf Bestaendigkeit pruefen - es faellt heraus, statt als
        "fest" durchzugehen.
        """
        if not self.laeufe:
            return ()
        gemeinsam = set.intersection(
            *({g.name for g in lauf.gates} for lauf in self.laeufe)
        )
        return tuple(g.name for g in self.geordnet[0].gates if g.name in gemeinsam)

    def _urteile(self, name: str) -> set[bool]:
        return {
            g.bestanden
            for lauf in self.laeufe
            if (g := lauf.gate(name)) is not None
        }

    @property
    def wandernde(self) -> tuple[str, ...]:
        """Gates, deren Urteil ueber die Leiter kippt."""
        if not self.genug:
            return ()
        return tuple(n for n in self.namen if len(self._urteile(n)) > 1)

    @property
    def feste(self) -> tuple[str, ...]:
        if not self.genug:
            return ()
        return tuple(n for n in self.namen if len(self._urteile(n)) == 1)

    def spanne(self, name: str) -> float:
        """Wie weit der **Wert** eines Gates wandert - auch ohne Urteilswechsel."""
        werte = [
            g.wert for lauf in self.laeufe if (g := lauf.gate(name)) is not None
        ]
        return max(werte) - min(werte) if werte else 0.0

    @property
    def stand_ohne_koernung(self) -> int | None:
        """Die Bilanz am oberen Ende - die Zahl, die nicht am Konto haengt."""
        return self.geordnet[-1].bestanden if self.laeufe else None

    @property
    def hoechster_stand(self) -> Gatelauf | None:
        """Die Sprosse mit den meisten bestandenen Gates.

        Heisst so und nicht ``bester``: Sie ist eine **Warnung**, kein Ziel.
        Wer sie als Betriebspunkt liest, waehlt einen Kontostand danach aus,
        wie viele Gates dort halten - genau die Anpassung, gegen die die
        Zulassungsstrecke gebaut ist.
        """
        if not self.laeufe:
            return None
        return max(self.geordnet, key=lambda x: x.bestanden)

    def tabelle(self) -> str:
        if not self.laeufe:
            return "Keine Gate-Laeufe."
        kopf = "".join(f"{lauf.kapital:>11,.0f}" for lauf in self.geordnet)
        breite = 22 + 11 * len(self.laeufe)
        zeilen = [f"{'Gate':<22}{kopf}", "-" * breite]
        for name in self.namen:
            spalten = ""
            for lauf in self.geordnet:
                g = lauf.gate(name)
                spalten += (
                    f"{'+' if g.bestanden else '-'}{g.wert:>10.3f}"
                    if g is not None
                    else f"{'?':>11}"
                )
            marke = "  wandert" if name in self.wandernde else ""
            zeilen.append(f"{name[:21]:<22}{spalten}{marke}")
        zeilen.append("-" * breite)
        zeilen.append(
            f"{'bestanden':<22}"
            + "".join(f"{lauf.bestanden:>11}" for lauf in self.geordnet)
        )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.genug:
            return (
                "Weniger als zwei vollstaendige Gate-Laeufe - daraus laesst "
                "sich ueber die Abhaengigkeit vom Konto nichts sagen."
            )

        klein, gross = self.geordnet[0], self.geordnet[-1]
        wandernd = self.wandernde
        if not wandernd:
            return (
                f"**Kein Gate aendert sein Urteil.** Ueber {len(self.laeufe)} "
                f"Kontostaende von {klein.kapital:,.0f} bis "
                f"{gross.kapital:,.0f} EUR bleibt die Bilanz bei "
                f"{gross.bestanden} von {gross.gesamt}."
            )

        teile = [
            f"**{len(wandernd)} von {len(self.namen)} Gates aendern ihr "
            f"Urteil, ohne dass sich an der Strategie etwas aendert:** "
            + ", ".join(wandernd)
            + f". Die Bilanz faellt von {klein.bestanden} von {klein.gesamt} "
            f"bei {klein.kapital:,.0f} EUR auf {gross.bestanden} bei "
            f"{gross.kapital:,.0f} EUR."
        ]

        spitze = self.hoechster_stand
        if spitze is not None and spitze.bestanden > gross.bestanden:
            teile.append(
                f"**Die {spitze.bestanden} von {spitze.gesamt} bei "
                f"{spitze.kapital:,.0f} EUR sind keine bessere Bilanz.** Es ist "
                f"dieselbe Strategie mit einer groeberen Treppe. Einen "
                f"Kontostand danach auszuwaehlen, wie viele Gates dort halten, "
                f"waere genau die Anpassung, gegen die die Zulassungsstrecke "
                f"gebaut ist. Die Zahl, die nicht am Konto haengt, steht am "
                f"oberen Ende: **{gross.bestanden} von {gross.gesamt}.**"
            )

        fest = self.feste
        if fest:
            teile.append(
                f"{len(fest)} Gates stehen still: " + ", ".join(fest) + "."
            )
        return "\n\n".join(teile)


def umsetzung(anteile, preise, *, kapital: float, schritt: float) -> float:
    """Welcher Anteil der berechneten Menge nach dem Abrunden uebrig bleibt.

    Braucht keinen Backtest: Menge ist Kapitalanteil mal Kapital durch Preis,
    und der Mengenschritt schneidet davon ab. 1,0 heisst "die Rundung kostet
    nichts".
    """
    import numpy as np

    a = np.asarray(anteile, dtype=float)
    p = np.asarray(preise, dtype=float)
    if len(a) != len(p) or len(a) == 0 or schritt <= 0 or kapital <= 0:
        return 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        roh = a * kapital / p
        anteil = np.floor(roh / schritt) * schritt / roh
    gut = np.isfinite(anteil) & (roh > 0)
    return float(np.mean(anteil[gut])) if gut.any() else 0.0


def baue_gemessen() -> Koernung:
    """Die Leiter aus ``GEMESSEN``, mit ihrer Gegenprobe."""
    return Koernung(stufen=list(GEMESSEN), feinmessung=FEINMESSUNG)


__all__ = [
    "FEINMESSUNG",
    "GEMESSEN",
    "SCHRITTE",
    "UNERHEBLICH",
    "Gatelauf",
    "Gateleiter",
    "Gatewert",
    "Koernung",
    "Kontostufe",
    "baue_gemessen",
    "umsetzung",
]
