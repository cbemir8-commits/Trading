"""Was ein Versuch beweisen kann - und was er trotzdem kostet.

Woher die Frage kommt
---------------------
Befund 71 hat den einzigen verbliebenen Hebel benannt: **die Guete der Ideen,
nicht ihre Zahl.** Die Suche gewinnt genau dann, wenn die Streuung echter
Regelideen ueber ``1/sqrt(n-1)`` liegt - der Streuung des reinen Zufalls.

Damit wird eine Frage stellbar, die dieses Projekt nie gestellt hat: **Taugt
eine bestimmte Ideenquelle?** Nicht "war dieser eine Vorschlag gut", sondern:
Streuen die Vorschlaege dieser Quelle breiter, als Rauschen allein hergibt?

Die Falle, die dabei sofort zuschlaegt
--------------------------------------
Der Sharpe je Trade ist selbst **geschaetzt**, mit einer Varianz von rund
``1/(n-1)`` je Kandidat. Wer die Streuung ueber mehrere Kandidaten misst,
misst deshalb zwei Dinge auf einmal:

    beobachtet^2 = Ideenstreuung^2 + Messrauschen^2

Und das Messrauschen ist gross. Bei den fuenf Analyst-Vorschlaegen, den
einzigen Versuchen dieses Projekts mit belegtem Sharpe je Trade:

    Neues Hoch im Takt              123 Trades -> Rauschen 0,0905
    Ausbruch mit Beteiligung         68 Trades -> Rauschen 0,1222
    Donchian-Ausbruch                89 Trades -> Rauschen 0,1066
    Rueckkehr vom unteren Band      118 Trades -> Rauschen 0,0925
    Rueckschlag im Aufwaertstrend     8 Trades -> Rauschen 0,3780

Beobachtete Streuung ueber die fuenf: **0,1031**. Erwartetes Messrauschen:
**0,1928**. Die beobachtete Streuung liegt also **unter** dem Rauschen - die
fuenf Vorschlaege sind vollstaendig damit vertraeglich, dass sie alle gleich
gut sind und der Unterschied zwischen ihnen reine Messungenauigkeit ist.

Auch ohne den 8-Trade-Fall bleibt es dabei: 0,0899 beobachtet gegen 0,1037
Rauschen. **Eine Ideenstreuung ist nicht nachweisbar** - was nicht heisst,
dass es keine gibt, sondern dass fuenf Punkte sie nicht zeigen koennen.

Der Versuch, der nichts beweisen konnte
---------------------------------------
"Rueckschlag im Aufwaertstrend" hat **8 Trades**. Sein Sharpe je Trade traegt
ein Rauschen von 0,378 - das Siebenfache des Abstands, um den es beim Gate
geht. Sein Deflated Sharpe wurde uebersprungen (unter 30 Trades gibt das Gate
``SKIP``), und **der Versuchszaehler ging trotzdem hoch.**

Er hat damit die Huerde fuer jeden anderen Kandidaten gehoben, ohne selbst je
eine Chance gehabt zu haben. Das ist kein Fehler in der Buchhaltung - gezaehlt
gehoert er -, aber es ist ein Preis, den bisher niemand beziffert hat.

**Am Zaehler wird deshalb nicht gedreht.** Er ist die Kernabsicherung gegen
Selbstbetrug; wer anfaengt, Versuche nachtraeglich nicht zu zaehlen, oeffnet
genau die Tuer, die der Zaehler zuhalten soll. Was hier gebaut wird, ist die
**Auskunft**: Vor dem Messen sichtbar machen, was ein Kandidat bei dieser
Trade-Zahl ueberhaupt zeigen kann.

Was das fuer Befund 71 heisst
-----------------------------
Dort wurde die Ideenstreuung aus dem beobachteten Bestwert kalibriert: 0,0950.
Auch darin steckt das Messrauschen. Zerlegt:

    beobachtet   0,0950
    Rauschen     0,0808   (72 % der Varianz)
    Ideen        0,0499

Das widerspricht Befund 71 nicht - die beobachtete Streuung liegt immer ueber
dem Rauschen, solange ueberhaupt eine Ideenstreuung da ist. Aber die Zahl, die
zaehlt, wenn man fragt *"wie gut ist der wahre beste Fund"*, ist 0,0499 und
nicht 0,0950. Knapp drei Viertel dessen, was wie ein Vorsprung der Suche
aussah, ist Messrauschen.

Kostet keinen Versuch: Zerlegt werden Zahlen, die schon dastehen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist, stdev

#: Ab so vielen Trades urteilt ``gate_deflated_sharpe`` ueberhaupt. Darunter
#: gibt es ``SKIP`` - der Versuch zaehlt trotzdem.
MINDESTTRADES = 30


def messrauschen(trades: int) -> float:
    """Wie ungenau der Sharpe je Trade bei so vielen Trades geschaetzt ist.

    ``1/sqrt(n-1)`` - dieselbe Groesse, die im Deflated Sharpe die Huerde
    treibt. Das ist kein Zufall: Das Gate fragt, ob ein Vorteil groesser ist
    als das, was diese Ungenauigkeit bei so vielen Versuchen hergibt.
    """
    return (1.0 / (trades - 1)) ** 0.5 if trades > 1 else float("inf")


def chi2_quantil(p: float, freiheitsgrade: int) -> float:
    """Chi-Quadrat-Quantil nach Wilson-Hilferty.

    Ohne ``scipy``, das hier nicht installiert ist. Die Naeherung wurde gegen
    Tabellenwerte geprueft: bei 4 Freiheitsgraden 9,456 gegen 9,488, bei 19
    schon 30,134 gegen 30,144. Fuer die Frage "reichen die Punkte?" ist das
    genau genug - und ein Test haelt die Genauigkeit fest.
    """
    if freiheitsgrade < 1:
        return float("nan")
    z = NormalDist().inv_cdf(p)
    k = freiheitsgrade
    return k * (1 - 2 / (9 * k) + z * math.sqrt(2 / (9 * k))) ** 3


@dataclass(frozen=True, slots=True)
class Beleg:
    """Ein gemessener Kandidat als Beleg ueber seine Quelle."""

    kennung: str
    sharpe_je_trade: float
    trades: int

    @property
    def rauschen(self) -> float:
        return messrauschen(self.trades)

    @property
    def beurteilbar(self) -> bool:
        """Konnte dieser Versuch ueberhaupt ein Urteil hervorbringen?

        Unter ``MINDESTTRADES`` ueberspringt das Gate die Korrektur - der
        Kandidat kann nicht bestehen und nicht durchfallen, hebt aber die
        Huerde fuer alle anderen.
        """
        return self.trades >= MINDESTTRADES


@dataclass(slots=True)
class Ideenquelle:
    """Eine Herkunft von Vorschlaegen, an ihrer Streuung gemessen."""

    name: str
    belege: list[Beleg] = field(default_factory=list)
    stichprobe: int = 154
    """Trade-Zahl, gegen deren Nullstreuung verglichen wird - die des
    Spitzenkandidaten, weil dort die Huerde entschieden wird."""

    @property
    def genug(self) -> bool:
        return len(self.belege) >= 2

    @property
    def beobachtet(self) -> float | None:
        """Die Streuung der Sharpe-Werte, wie sie dasteht."""
        if not self.genug:
            return None
        return stdev(b.sharpe_je_trade for b in self.belege)

    @property
    def rauschen(self) -> float | None:
        """Wie viel Streuung allein aus der Messungenauigkeit zu erwarten ist.

        Gemittelt wird ueber die **Varianzen**, nicht die Streuungen - sie
        addieren sich, nicht ihre Wurzeln.
        """
        if not self.belege:
            return None
        return (sum(b.rauschen**2 for b in self.belege) / len(self.belege)) ** 0.5

    @property
    def ideenstreuung(self) -> float | None:
        """Was nach Abzug des Messrauschens uebrig bleibt.

        ``None`` heisst **nicht nachweisbar**: Die beobachtete Streuung liegt
        unter dem, was Rauschen allein erzeugt. Das ist keine Aussage darueber,
        dass es keine gibt - nur darueber, dass diese Punkte sie nicht zeigen.
        """
        beobachtet, rauschen = self.beobachtet, self.rauschen
        if beobachtet is None or rauschen is None:
            return None
        rest = beobachtet**2 - rauschen**2
        return rest**0.5 if rest > 0 else None

    @property
    def nullstreuung(self) -> float:
        return messrauschen(self.stichprobe)

    @property
    def schlaegt_den_zufall(self) -> bool:
        """Liegt die **nachgewiesene** Ideenstreuung ueber dem Zufall?"""
        ideen = self.ideenstreuung
        return ideen is not None and ideen > self.nullstreuung

    def vertrauensbereich(self, *, irrtum: float = 0.10) -> tuple[float, float] | None:
        """Wie unsicher die beobachtete Streuung ist.

        Bei fuenf Punkten reicht der Bereich von 0,067 bis 0,248 - er
        enthaelt die Nullstreuung, und damit ist die Frage unbeantwortet.
        """
        beobachtet = self.beobachtet
        if beobachtet is None:
            return None
        k = len(self.belege) - 1
        unten = beobachtet * (k / chi2_quantil(1 - irrtum / 2, k)) ** 0.5
        oben = beobachtet * (k / chi2_quantil(irrtum / 2, k)) ** 0.5
        return unten, oben

    def noetige_belege(self, *, hoechstens: int = 500, irrtum: float = 0.05) -> int | None:
        """Wie viele Punkte es braeuchte, um das beobachtete Verhaeltnis
        abzusichern.

        ``None``, wenn die beobachtete Streuung nicht einmal ueber der
        Nullstreuung liegt - dann ist es keine Frage der Zahl.
        """
        beobachtet = self.beobachtet
        if beobachtet is None or beobachtet <= self.nullstreuung:
            return None
        verhaeltnis = beobachtet / self.nullstreuung
        for n in range(3, hoechstens + 1):
            if (chi2_quantil(1 - irrtum, n - 1) / (n - 1)) ** 0.5 < verhaeltnis:
                return n
        return None

    @property
    def unbeurteilbare(self) -> list[Beleg]:
        """Versuche, die die Huerde gehoben haben, ohne etwas zeigen zu
        koennen."""
        return [b for b in self.belege if not b.beurteilbar]

    def tabelle(self) -> str:
        zeilen = [
            f"{'Kandidat':<32} {'Trades':>7} {'SR/Trade':>9} {'Rauschen':>9}",
            "-" * 60,
        ]
        for b in sorted(self.belege, key=lambda x: -x.trades):
            marke = "" if b.beurteilbar else "  <- unbeurteilbar"
            zeilen.append(
                f"{b.kennung[:32]:<32} {b.trades:>7} {b.sharpe_je_trade:>9.4f} "
                f"{b.rauschen:>9.4f}{marke}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        beobachtet, rauschen = self.beobachtet, self.rauschen
        if beobachtet is None or rauschen is None:
            return (
                f"'{self.name}': zu wenige Belege - ueber die Quelle laesst "
                f"sich nichts sagen."
            )

        teuer = self.unbeurteilbare
        nachsatz = ""
        if teuer:
            namen = ", ".join(f"'{b.kennung}' ({b.trades} Trades)" for b in teuer)
            nachsatz = (
                f"\n\nUnd {len(teuer)} davon konnte nichts zeigen: {namen}. "
                f"Unter {MINDESTTRADES} Trades ueberspringt das Gate die "
                f"Korrektur - der Kandidat kann weder bestehen noch "
                f"durchfallen, **hebt aber die Huerde fuer alle anderen**. "
                f"Gezaehlt gehoert er trotzdem; am Zaehler wird nicht gedreht."
            )

        ideen = self.ideenstreuung
        if ideen is None:
            bereich = self.vertrauensbereich()
            spanne = (
                f" Der 90-Prozent-Bereich fuer die beobachtete Streuung reicht "
                f"von {bereich[0]:.4f} bis {bereich[1]:.4f}."
                if bereich
                else ""
            )
            noetig = self.noetige_belege()
            wieviele = (
                f" Um das beobachtete Verhaeltnis abzusichern, braeuchte es "
                f"rund {noetig} Belege statt {len(self.belege)}."
                if noetig
                else ""
            )
            return (
                f"**'{self.name}': keine Ideenstreuung nachweisbar.** "
                f"Beobachtet {beobachtet:.4f}, erwartetes Messrauschen "
                f"{rauschen:.4f} - die Vorschlaege sind vollstaendig damit "
                f"vertraeglich, dass sie alle gleich gut sind und der "
                f"Unterschied Messungenauigkeit ist.{spanne}{wieviele}\n\n"
                f"Das heisst nicht, dass die Quelle nichts taugt. Es heisst, "
                f"dass {len(self.belege)} Punkte es nicht zeigen koennen."
                f"{nachsatz}"
            )

        vergleich = (
            f"ueber der Nullstreuung von {self.nullstreuung:.4f} - die Quelle "
            f"streut breiter als Zufall"
            if self.schlaegt_den_zufall
            else f"unter der Nullstreuung von {self.nullstreuung:.4f} - das "
            f"reicht nicht, um die Huerde einzuholen"
        )
        return (
            f"**'{self.name}': Ideenstreuung {ideen:.4f}**, {vergleich}. "
            f"Beobachtet {beobachtet:.4f}, davon {rauschen:.4f} "
            f"Messrauschen.{nachsatz}"
        )


def zerlege(beobachtet: float, rauschen: float) -> float | None:
    """Die Ideenstreuung hinter einer beobachteten Streuung.

    Auch fuer Zahlen brauchbar, die nicht aus einer Belegliste stammen - etwa
    fuer die kalibrierte Streuung aus Befund 71.
    """
    rest = beobachtet**2 - rauschen**2
    return rest**0.5 if rest > 0 else None
