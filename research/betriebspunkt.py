"""Es gibt zwei Staende, und welcher gilt, entscheidet eine offene Tatsache.

Was hier gefunden wurde
-----------------------
``cli stand`` beantwortet die Frage *wo stehen wir* - fuer den Nutzer und fuer
jeden Lauf, der sich orientieren will. Gemessen hat es bis hierher **einen**
Betriebspunkt: Perpetual mit Hebel und Funding.

    Perpetual   152 Trades, 13,47 % p.a., 10,64 % Rueckgang    7/11 Gates
                Guete 0,2597, DSR 0,7641, noetig +15 %

Seit Befund 108 ist gemessen, dass ein zweiter existiert - und dass er besser
ist:

    Spot        152 Trades, 14,83 % p.a.,  9,87 % Rueckgang    9/11 Gates
                Guete 0,2765, DSR 0,8640, noetig +8,0 %

Zwei Gates und sieben Prozentpunkte Aufgabe liegen dazwischen. ``cli stand``
hat drei Befunde lang den schlechteren gezeigt, ohne den besseren zu erwaehnen
- derselbe Fehler wie in den Befunden 101, 103 und 109, nur eine Ebene hoeher:
nicht ein fester Satz neben einer gerechneten Zahl, sondern eine gerechnete
Zahl gegen einen ueberholten Bezugspunkt.

Warum der Wechsel trotzdem keine Lockerung ist
----------------------------------------------
Weil er keiner waere - und weil dieses Modul verhindert, dass er einer wird.

Spot ist **ein anderes Instrument, keine mildere Annahme.** Befund 106 hat
gemessen, dass der Kandidat den Hebel an 0,2 % der Balken nutzt und mit
``fraction = 1,0`` bitgleiche Zahlen liefert; er ist long-only (Befund 13).
Der Wegfall von Funding und Hebel ist also handelbar und nicht herbeigeredet.

Nur haengt daran eine Tatsache, die aus diesem Container nicht zu klaeren ist:
**Was der Nutzer in seinem Bybit-Menue sieht.** Bybit EU bietet unter der
MiCA-Lizenz keine Perpetuals an; ob sein Konto migriert wurde, weiss nur er.
Dazu kommt, dass Bybits Spot-Tarif ungemessen ist - Befund 108 hat die
Bruchstelle bei ``x2,75`` des Perpetual-Tarifs beziffert, mehr nicht.

Daraus folgt die Regel, die dieses Modul durchsetzt:

    **Solange die Voraussetzung offen ist, gilt der unguenstigere Stand.**

Dieselbe Richtung wie bei ``effektive_stichprobe``: Eine Entscheidung unter
Unklarheit darf die Zulassung nur erschweren, nie erleichtern. Der bessere
Stand wird erst maßgeblich, wenn die Tatsache **bestaetigt** ist - nicht, wenn
sie plausibel ist, und schon gar nicht, weil er besser aussieht.

Was der Bericht dadurch aendert
-------------------------------
Beide Staende stehen nebeneinander, mit der Tatsache dazwischen, die
entscheidet. Der Nutzer sieht damit ohne Nachfrage, was seine zwei Minuten im
Bybit-Menue wert sind: zwei Gates und die Haelfte der verbleibenden Aufgabe.

Was sich dadurch **nicht** aendert: Auch der bessere Stand ist keine
Zulassung. 9 von 11 sind nicht 11 von 11, und die zwei offenen - Messlatte und
Deflated Sharpe - sind nach Befund 111 die, hinter denen keine gemessene
Familie mehr steht.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Was den Betriebspunkt festlegt, aber hier nicht zu klaeren ist.
OFFENE_TATSACHE = (
    "Bietet das Bybit-Konto des Nutzers Perpetuals an? Bybit EU fuehrt unter "
    "der MiCA-Lizenz nur Spot. Zwei Minuten im Handelsmenue entscheiden es."
)


@dataclass(frozen=True, slots=True)
class Betriebspunkt:
    """Ein Stand des Kandidaten unter bestimmten Handelsbedingungen."""

    name: str
    trades: int
    cagr_pct: float
    rueckgang_pct: float
    guete: float
    dsr: float
    bestanden: int
    gesamt: int
    offen: tuple[str, ...] = ()
    #: Ist die Voraussetzung dieses Punktes bestaetigt, oder nur moeglich?
    bestaetigt: bool = False
    voraussetzung: str = ""

    @property
    def zugelassen(self) -> bool:
        return self.bestanden == self.gesamt

    def besser_als(self, andere: Betriebspunkt) -> bool:
        """Mehr Gates - und bei Gleichstand der hoehere Deflated Sharpe.

        Bewusst an den Gates aufgehaengt und nicht an der Rendite: Ein Punkt
        mit mehr Rendite und weniger bestandenen Gates ist nicht der bessere,
        sondern der riskantere.
        """
        if self.bestanden != andere.bestanden:
            return self.bestanden > andere.bestanden
        return self.dsr > andere.dsr

    def als_zeile(self) -> str:
        marke = "" if self.bestaetigt else "  (Voraussetzung offen)"
        return (
            f"{self.name:<12} {self.trades:>4} Trades, {self.cagr_pct:>6.2f} % p.a., "
            f"{self.rueckgang_pct:>5.2f} % Rueckgang   "
            f"{self.bestanden}/{self.gesamt} Gates{marke}"
        )


@dataclass(frozen=True, slots=True)
class Betriebslage:
    """Mehrere Betriebspunkte, und die Regel, welcher gilt.

    Die Regel steht in ``massgeblich``: Unter den Punkten, deren Voraussetzung
    **bestaetigt** ist, gilt der beste. Ist keiner bestaetigt, gilt der
    schlechteste ueberhaupt - denn dann ist unbekannt, welcher zutrifft, und
    unter Unklarheit zaehlt der unguenstigere.
    """

    punkte: tuple[Betriebspunkt, ...]
    tatsache: str = OFFENE_TATSACHE

    def __post_init__(self) -> None:
        if not self.punkte:
            raise ValueError(
                "Eine Betriebslage ohne Punkte beschreibt nichts - dann gibt "
                "es keinen Stand, ueber den zu berichten waere."
            )

    @property
    def bestaetigte(self) -> tuple[Betriebspunkt, ...]:
        return tuple(p for p in self.punkte if p.bestaetigt)

    @property
    def offene(self) -> tuple[Betriebspunkt, ...]:
        return tuple(p for p in self.punkte if not p.bestaetigt)

    @property
    def massgeblich(self) -> Betriebspunkt:
        """Der Stand, der berichtet wird - nach der Regel, nicht nach Wunsch."""
        bestaetigt = self.bestaetigte
        if bestaetigt:
            beste = bestaetigt[0]
            for p in bestaetigt[1:]:
                if p.besser_als(beste):
                    beste = p
            return beste
        schlechteste = self.punkte[0]
        for p in self.punkte[1:]:
            if schlechteste.besser_als(p):
                schlechteste = p
        return schlechteste

    @property
    def beste_moegliche(self) -> Betriebspunkt:
        """Der beste Punkt ueberhaupt - bestaetigt oder nicht.

        Nicht der berichtete Stand, sondern das, was die offene Tatsache wert
        ist. Beides zugleich zu zeigen ist der ganze Zweck dieses Moduls.
        """
        beste = self.punkte[0]
        for p in self.punkte[1:]:
            if p.besser_als(beste):
                beste = p
        return beste

    @property
    def haengt_an_der_tatsache(self) -> bool:
        """Wuerde die Klaerung den berichteten Stand veraendern?"""
        return self.beste_moegliche is not self.massgeblich

    def gates_dazwischen(self) -> int:
        """Wie viele Gates an der offenen Tatsache haengen."""
        return self.beste_moegliche.bestanden - self.massgeblich.bestanden

    def urteil(self) -> str:
        massgeblich = self.massgeblich
        if not self.haengt_an_der_tatsache:
            if massgeblich.bestaetigt:
                return (
                    f"Der Stand ist '{massgeblich.name}' und steht fest - "
                    "kein anderer gemessener Punkt ist besser."
                )
            return (
                f"Berichtet wird '{massgeblich.name}', der unguenstigere Punkt: "
                "Unter offener Voraussetzung zaehlt der schlechtere Stand."
            )
        gates = self.gates_dazwischen()
        return (
            f"Berichtet wird '{massgeblich.name}' ({massgeblich.bestanden}/"
            f"{massgeblich.gesamt}), weil die Voraussetzung offen ist. "
            f"Gemessen besser waere '{self.beste_moegliche.name}' "
            f"({self.beste_moegliche.bestanden}/{self.beste_moegliche.gesamt})"
            + (f" - {gates} Gates haengen daran. " if gates else " - ")
            + self.tatsache
        )
