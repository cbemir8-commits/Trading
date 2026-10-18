"""Was traegt ein Bauteil des Kandidaten? - Befund 366.

Die Frage, die die Sperrprobe nicht stellen kann
------------------------------------------------
``cli sperrprobe`` fragt: *Leistet eine Sperre mehr, als es dieselbe Zahl
beliebiger Sperren taete?* Sie prueft damit **Trade-Entfernungen** - Schock,
Abkuehlung, Terminkalender -, und sie prueft sie streng: gezogen werden
genauso viele Einstiegssignale, je Bein einzeln.

Dem Spitzenkandidaten sieht man am Namen an, dass er noch ein Bauteil hat, das
Einstiege wegnimmt: *"Trend 50 Tage mit Konfluenz"*. Gemessen entfernen seine
drei Konfluenz-Bedingungen **9 Signale** (1 in BTC, 8 in ETH) - und **keinen
einzigen Trade**: 156 hier, 156 dort. Die Signale, die sie streichen, haetten
ohnehin nicht zu einem Einstieg gefuehrt, weil an jenen Balken schon eine
Position offen war.

Damit kann die Sperrprobe das Bauteil nicht beurteilen. Ihre Null zieht aus den
Signalen des Kandidaten, und die gestrichenen liegen gar nicht darin; eine
Sperre auf sie bleibt folgenlos. Gemessen, bevor dieses Modul entstand:

    ohne Konfluenz                 156 Trades, Guete 0,269308
    ohne Konfluenz + ihre 9 Signale gesperrt
                                   156 Trades, Guete 0,269308

Bitgleich. Eine Sperrprobe haette hier eine selbstbewusste Null gemeldet.

Was dieses Modul stattdessen tut
--------------------------------
Es laesst das Bauteil **weg** und laeuft denselben Zulassungspfad noch einmal -
eine Ablation. Nicht gegen eine Zufallsnull, sondern gegen den Kandidaten
selbst, und die Gegenprobe ist, dass der Lauf *mit* Bauteil den dokumentierten
Punkt exakt wiederholt.

Am Spot-Punkt gemessen (Reihe bis 2026-08-29, 203 Versuche):

    mit Konfluenz    156 Trades  Guete 0,2708  DSR 0,5826  **9 von 11**
                     gefallen: Messlatte, Deflated Sharpe
    ohne Konfluenz   156 Trades  Guete 0,2720  DSR 0,5470  **7 von 11**
                     gefallen: Drawdown, Schlechtestes Jahr, Deflated Sharpe,
                               Parameter-Plateau

**Die Konfluenz traegt**, und zwar anders als man erwartet: Die Guete je Trade
wird ohne sie sogar winzig besser (+0,0012). Was sie haelt, ist das Risiko -
Rueckgang 9,87 % statt 12,54 %, und damit zwei Gates. Sie ist kein Filter auf
Qualitaet, sondern einer auf Ruhe.

Das ist auch der Unterschied zum Terminkalender (Befund 271): Der entfernte
sechs Einstiege, und 100 % der zufaelligen Sperren derselben Groesse hielten
genauso viele Gates - *"es war nicht die Auswahl, sondern das Streichen"*. Bei
der Konfluenz ist es die Auswahl.

Was das kostet und was nicht
----------------------------
**Keinen Versuch.** Gemessen wird ein Bauteil, das der Kandidat schon hat,
nicht ein neuer Kandidat. Der Versuchszaehler zaehlt Hypothesen ueber den
Markt, nicht Kontrollrechnungen ueber die eigene Messung - dieselbe
Begruendung wie bei der Sperrprobe.

**Zugelassen wird dadurch nichts.** Fiele eine Ablation einmal zugunsten der
abgespeckten Fassung aus, waere das ein **Vorschlag** und kein Ergebnis: Sie
als Kandidaten zu fuehren kostet einen Versuch und ist eine Entscheidung des
Nutzers, nicht die Folge einer Kontrollrechnung.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from research.gatebilanz import Gatebilanz

if TYPE_CHECKING:
    from strategy.genome import Genome

#: Die Bauteile, die weggelassen werden koennen, und wie.
#:
#: Eine Whitelist und kein freier Feldname: Ein vertippter Name wuerde sonst
#: ein Genom unveraendert lassen, die Ablation waere bitgleich mit dem
#: Kandidaten, und das saehe aus wie "das Bauteil traegt nichts".
BAUTEILE: dict[str, dict[str, object]] = {
    "konfluenz": {"konfluenz": []},
    "filter": {"filters": []},
}


def ohne_bauteil(genome: Genome, bauteil: str) -> Genome:
    """Dasselbe Genom ohne ein Bauteil.

    ``model_copy`` und keine neue Konstruktion: Alles andere - Perioden,
    Stop-Art, Sizing, Sperrfrist - muss bitgleich bleiben, sonst misst die
    Ablation zwei Unterschiede und schreibt sie einem zu.
    """
    if bauteil not in BAUTEILE:
        raise ValueError(
            f"Unbekanntes Bauteil '{bauteil}'. Bekannt: {sorted(BAUTEILE)}"
        )
    return genome.model_copy(update=dict(BAUTEILE[bauteil]))


def traegt_das_bauteil(genome: Genome, bauteil: str) -> bool:
    """Hat dieses Genom das Bauteil ueberhaupt?

    Sonst ist die Ablation ein Vergleich eines Genoms mit sich selbst, und
    "kein Unterschied" liest sich wie ein Ergebnis.
    """
    ohne = ohne_bauteil(genome, bauteil)
    return ohne.model_dump() != genome.model_dump()


@dataclass(frozen=True, slots=True)
class Lage(Gatebilanz):
    """Was ein Lauf erreicht hat - mit oder ohne Bauteil.

    ``uebersprungen`` steht hier, weil ``GateResult.passed`` ein ausgesetztes
    Gate als bestanden zaehlt (Befunde 321/322). Eine Ablation, die "9 von 11"
    gegen "7 von 11" stellt, muss sagen koennen, ob in einer der beiden Zahlen
    ein geschenktes Urteil steckt - sonst vergleicht sie zwei verschieden
    zusammengesetzte Neunen.

    Am Spot-Punkt ist die Zahl null: 156 Trades liegen weit ueber jeder
    Aussetzschwelle (30, fuer Monte-Carlo 20). Bei einem Bauteil, das viele
    Trades kostet, waere sie es nicht.
    """

    trades: int
    guete: float
    dsr: float
    rueckgang_pct: float
    bestanden: int
    gesamt: int
    gefallen: tuple[str, ...] = ()
    uebersprungen: int = 0


@dataclass(slots=True)
class Anatomie:
    """Der Kandidat gegen sich selbst ohne ein Bauteil."""

    bauteil: str
    mit: Lage
    ohne: Lage
    #: Wie viele Einstiegssignale das Bauteil streicht, je Bein.
    signale: dict[str, int] = field(default_factory=dict)

    @property
    def gates_differenz(self) -> int:
        """Gates, die das Bauteil haelt. Negativ heisst: es kostet welche."""
        return self.mit.bestanden - self.ohne.bestanden

    @property
    def guete_differenz(self) -> float:
        return self.mit.guete - self.ohne.guete

    @property
    def traegt(self) -> bool:
        """Haelt das Bauteil Gates?

        **Gates und nicht Guete.** Die Konfluenz macht die Guete je Trade
        minimal schlechter und haelt trotzdem zwei Gates; wer nach der Guete
        urteilte, haette sie gestrichen.
        """
        return self.gates_differenz > 0

    @property
    def gates_nur_ohne(self) -> tuple[str, ...]:
        """Gates, die erst ohne das Bauteil fallen - das, was es haelt."""
        return tuple(g for g in self.ohne.gefallen if g not in self.mit.gefallen)

    @property
    def gates_nur_mit(self) -> tuple[str, ...]:
        """Gates, die nur **mit** dem Bauteil fallen - das, was es kostet.

        **Befund 367, und es war eine Luecke in diesem Modul.** Gestern stand
        hier nur die Gegenrichtung, und das Urteil lautete *"Das Bauteil
        traegt: Ohne es fallen Drawdown, Schlechtestes Jahr,
        Parameter-Plateau"*. Richtig, und einseitig: Dieselbe Messung zeigt,
        dass die **Messlatte** umgekehrt kippt - sie faellt nur *mit* der
        Konfluenz. Wer das Urteil las, hielt das Bauteil fuer umsonst zu
        haben.

        Ein Bauteil kann Gates halten **und** Gates kosten. Die Netto-Zahl
        (9 gegen 7) sagt nicht, woraus sie besteht.
        """
        return tuple(g for g in self.mit.gefallen if g not in self.ohne.gefallen)

    @property
    def tauscht(self) -> bool:
        """Haelt das Bauteil Gates und kostet gleichzeitig welche?"""
        return bool(self.gates_nur_ohne and self.gates_nur_mit)

    @property
    def uebersprungen_irgendwo(self) -> bool:
        """Steckt in einer der beiden Zahlen ein ausgesetztes Gate?"""
        return bool(self.mit.uebersprungen or self.ohne.uebersprungen)

    def urteil(self) -> str:
        gestrichen = sum(self.signale.values())
        kopf = (
            f"{self.bauteil}: {gestrichen} Signale gestrichen, "
            f"{self.mit.trades - self.ohne.trades:+d} Trades, "
            f"Guete {self.guete_differenz:+.4f}, "
            f"Gates {self.mit.bestanden}/{self.mit.gesamt} gegen "
            f"{self.ohne.bestanden}/{self.ohne.gesamt}"
        )
        if self.uebersprungen_irgendwo:
            kopf += (
                f"\n**Vorsicht**: ausgesetzte Gates "
                f"(mit {self.mit.uebersprungen}, ohne {self.ohne.uebersprungen}) "
                f"- ein ausgesetztes Gate zaehlt als bestanden."
            )
        # **Beide Richtungen, immer** (Befund 367). Ein Urteil, das nur die
        # gehaltenen Gates nennt, laesst das Bauteil umsonst erscheinen.
        zeilen = [kopf]
        if self.gates_nur_ohne:
            zeilen.append(
                f"Es **haelt**: ohne es fallen {', '.join(self.gates_nur_ohne)}."
            )
        if self.gates_nur_mit:
            zeilen.append(
                f"Es **kostet**: nur mit ihm faellt "
                f"{', '.join(self.gates_nur_mit)}."
            )
        if self.tauscht:
            zeilen.append(
                f"Das Bauteil **tauscht** also - "
                f"{len(self.gates_nur_ohne)} gehalten gegen "
                f"{len(self.gates_nur_mit)} gekostet, netto "
                f"{self.gates_differenz:+d}."
            )
        elif not self.gates_nur_ohne and not self.gates_nur_mit:
            zeilen.append(
                "Kein Gate kippt in eine der beiden Richtungen. Das Bauteil "
                "ist zu klein, um zu zaehlen - wie das Termin-Overlay in "
                "Befund 271."
            )
        elif self.gates_differenz < 0:
            zeilen.append("Unterm Strich **kostet** es Gates.")
        return "\n".join(zeilen)


def vergleiche(
    genome: Genome, bauteil: str, messe: Callable[[Genome], Lage],
    *, signale: dict[str, int] | None = None,
) -> Anatomie:
    """Den Kandidaten mit und ohne ein Bauteil messen.

    ``messe`` kommt von aussen, weil der Zulassungspfad in ``cli`` steht und
    dieses Modul nichts laden soll. Dieselbe Teilung wie bei der Sperrprobe:
    Hier die Aussage, dort der Lauf.
    """
    if not traegt_das_bauteil(genome, bauteil):
        raise ValueError(
            f"Dieses Genom hat kein Bauteil '{bauteil}' - eine Ablation "
            f"waere ein Vergleich mit sich selbst."
        )
    return Anatomie(
        bauteil=bauteil,
        mit=messe(genome),
        ohne=messe(ohne_bauteil(genome, bauteil)),
        signale=dict(signale or {}),
    )
