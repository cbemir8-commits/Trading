"""Was den Zustand aendern kann - und was hinter einer Sperre liegt.

Was hier gefunden wurde
-----------------------
Seit Befund 102 gilt im System eine Sperre, und sie ist scharf formuliert:

    ``GateReport.passed`` = ``not vorauswahl and not referenzdaten and
    all(...)``

**Solange auf Forschungskerzen gerechnet wird, gibt es keine Zulassung - egal
wie viele Gates halten.** Bitstamp-Kassakurse sind nicht das gehandelte
Instrument: andere Boerse, andere Dochte, USD statt USDT, Kassa statt
Perpetual, und keine Funding-Zahlungen.

Das ist richtig so, und es war eine bewusste Entscheidung. Nur hat seither
niemand die Folge ausgesprochen: **Elf Befunde Arbeit liegen hinter dieser
Sperre.** Die Befunde 103 bis 113 haben gemessen, geschlossen, korrigiert und
beziffert - und keiner von ihnen konnte den Zustand *"kein zugelassener
Kandidat"* aendern, weil kein Ergebnis auf diesen Daten ihn aendern kann.

Warum es niemandem auffiel
--------------------------
``GateReport.summary`` nennt die Sperre - aber nur im Zweig
``geprueftes_bestanden``, also erst, wenn **alle** Gates halten. Der Bestand
steht bei 7 von 11 (Perpetual) beziehungsweise 9 von 11 (Spot). Der Zweig ist
nie gelaufen.

Die Sperre wird also genau dann sichtbar, wenn man sie erreicht - und dann ist
die Reihenfolge der Arbeit laengst festgelegt. Dieselbe Klasse wie die drei
Befunde davor: Das Wissen liegt im System, aber nicht dort, wo es die Arbeit
steuern wuerde (111: Register ungelesen, 112: ueberholter Bezugspunkt, 113:
eine einzelne Ziehung).

Was daraus **nicht** folgt
--------------------------
Dass die Arbeit wertlos war. Befund 111 hat die Kostenfamilie geschlossen,
Befund 113 hat Befund 54 belegt, Befund 112 den Bericht geradegerueckt - das
gilt weiter, und es gilt der Sache nach auch auf Boersendaten. Was nicht gilt:
dass irgendeine dieser Messungen den Bestand naeher an eine Zulassung gebracht
haette. Sie konnten es nicht.

Der Unterschied ist der ganze Zweck dieses Moduls. Eine Arbeit kann nuetzlich
sein und trotzdem den Zustand nicht aendern; wer beides verwechselt, arbeitet
mit gutem Gewissen an der falschen Stelle weiter.

Was den Zustand aendern kann
----------------------------
Gemessen, mit Fundstelle, und danach geordnet, wer es tun kann:

    Sperre        Boersendaten fehlen                     Nutzer   102
    Bedingung     +30 unabhaengige Beobachtungen          keiner   111
    Bedingung     +8,0 % Guete am Spot-Punkt              Suche    108
    Klaerung      Perpetual oder Spot?                    Nutzer   112
    Klaerung      echte Funding-Raten                     Nutzer   100

Die beiden Bedingungen sind gemessen aussichtslos: Die Quellen fuer
Beobachtungen sind geschlossen (Maerkte 27, Historie 14), und die Suche
braeuchte rund 5.951 Versuche bei einem Budget, das bei 230 endet (110).

Bleiben drei Zeilen, und alle drei stehen beim Nutzer. Das ist keine Ausrede,
sondern das Ergebnis: **Aus diesem Container heraus gibt es keinen Schritt
mehr, der den Zustand aendert.** Die Bybit-Regionssperre wird nicht umgangen;
was hier laeuft, bleibt Vorarbeit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Art(Enum):
    """Wie eine Zeile auf den Zustand wirkt."""

    SPERRE = "Sperre"
    """Verhindert die Zulassung unabhaengig von allen Gates."""

    BEDINGUNG = "Bedingung"
    """Fehlt noch, laesst sich aber im Grundsatz erarbeiten."""

    KLAERUNG = "Klaerung"
    """Eine offene Tatsache; ihre Antwort verschiebt den Betriebspunkt."""


class Wer(Enum):
    """Wer den Schritt tun kann."""

    NUTZER = "Nutzer"
    CONTAINER = "Container"
    SUCHE = "Suche"
    NIEMAND = "niemand"
    """Gemessen geschlossen - keine bekannte Quelle."""


@dataclass(frozen=True, slots=True)
class Schritt:
    """Eine Sache, die zwischen dem Bestand und einer Zulassung steht."""

    name: str
    art: Art
    wer: Wer
    befund: int
    hinweis: str = ""

    def __post_init__(self) -> None:
        if self.befund <= 0:
            raise ValueError(
                f"'{self.name}' ohne Fundstelle - ein Schritt ohne nachlesbare "
                "Messung ist eine Meinung."
            )

    @property
    def machbar(self) -> bool:
        """Gibt es ueberhaupt jemanden, der ihn tun kann?"""
        return self.wer is not Wer.NIEMAND

    @property
    def hier_machbar(self) -> bool:
        """Laesst er sich aus diesem Container heraus tun?

        **Die Suche zaehlt dazu.** Sie laeuft hier, sie kostet Versuche, und
        das Budget hat noch welche uebrig - im ersten Entwurf stand sie
        ausserhalb, und dann sagte der Bericht, es gebe hier gar nichts mehr
        zu tun. Das war zu viel behauptet: Es gibt etwas, es ist nur gemessen
        aussichtslos, und das ist ein anderer Satz.
        """
        return self.wer in (Wer.CONTAINER, Wer.SUCHE)

    def als_zeile(self) -> str:
        return (
            f"{self.art.value:<10} {self.name:<38} {self.wer.value:<10} "
            f"Nr. {self.befund}"
        )


@dataclass(frozen=True, slots=True)
class Lage:
    """Alle Schritte zusammen - und was sie ueber die Reihenfolge sagen.

    Die Frage, die dieses Objekt beantwortet, ist nicht "was koennte man
    tun", sondern "was davon aendert den Zustand". Eine Arbeit hinter einer
    offenen Sperre aendert ihn nicht, egal wie gut sie ist.
    """

    schritte: tuple[Schritt, ...]

    @property
    def sperren(self) -> tuple[Schritt, ...]:
        return tuple(s for s in self.schritte if s.art is Art.SPERRE)

    @property
    def gesperrt(self) -> bool:
        """Steht mindestens eine Sperre offen?"""
        return bool(self.sperren)

    @property
    def bedingungen(self) -> tuple[Schritt, ...]:
        return tuple(s for s in self.schritte if s.art is Art.BEDINGUNG)

    @property
    def aussichtslos(self) -> tuple[Schritt, ...]:
        """Schritte, fuer die es gemessen keine Quelle gibt."""
        return tuple(s for s in self.schritte if not s.machbar)

    @property
    def beim_nutzer(self) -> tuple[Schritt, ...]:
        return tuple(s for s in self.schritte if s.wer is Wer.NUTZER)

    @property
    def hier(self) -> tuple[Schritt, ...]:
        """Was sich aus diesem Container heraus tun laesst."""
        return tuple(s for s in self.schritte if s.hier_machbar)

    def wirkt(self, schritt: Schritt) -> bool:
        """Aendert dieser Schritt den Zustand - jetzt, nicht irgendwann?

        Eine Sperre wirkt immer: Sie aufzuheben ist die Voraussetzung fuer
        alles andere. Alles andere wirkt nur, wenn **keine** Sperre mehr
        offen ist - sonst laeuft es gegen eine Wand, die keine Messung
        verschiebt.
        """
        if schritt.art is Art.SPERRE:
            return True
        return not self.gesperrt and schritt.machbar

    def wirksame(self) -> tuple[Schritt, ...]:
        return tuple(s for s in self.schritte if self.wirkt(s))

    def vergeblich(self) -> tuple[Schritt, ...]:
        """Schritte, die bei offener Sperre nichts am Zustand aendern."""
        return tuple(s for s in self.schritte if not self.wirkt(s))

    def urteil(self) -> str:
        if not self.schritte:
            return "Keine Schritte erfasst - dazu ist nichts zu sagen."
        if not self.gesperrt:
            machbar = [s for s in self.schritte if s.machbar]
            if not machbar:
                return (
                    "Keine Sperre offen, aber auch kein machbarer Schritt - "
                    "jede Bedingung ist gemessen ohne Quelle."
                )
            namen = ", ".join(s.name for s in machbar)
            return f"Keine Sperre offen. Wirksam waeren: {namen}."
        namen = ", ".join(f"{s.name} (Nr. {s.befund})" for s in self.sperren)
        wer = {s.wer.value for s in self.sperren}
        return (
            f"Gesperrt: {namen}. Solange sie steht, aendert keine Messung auf "
            f"diesen Daten den Zustand - auch elf von elf Gates waeren keine "
            f"Zulassung. Aufheben kann sie: {', '.join(sorted(wer))}."
        )


#: Der Stand, wie er gemessen ist. Jede Zeile mit Fundstelle.
#:
#: Bewusst hier und nicht im Bericht zusammengesetzt: Wer eine Zeile aendert,
#: aendert sie an einer Stelle, und der Test prueft die Fundstellen gegen das
#: Laborbuch.
STAND: tuple[Schritt, ...] = (
    Schritt(
        name="Boersendaten fehlen",
        art=Art.SPERRE,
        wer=Wer.NUTZER,
        befund=102,
        hinweis=(
            "Jede Zahl steht auf Bitstamp-Kassakursen. GateReport.passed "
            "verlangt Boersendaten - ohne sie gibt es keine Zulassung, egal "
            "wie viele Gates halten. 'cli backfill --von 2017-08-16'."
        ),
    ),
    Schritt(
        name="30 unabhaengige Beobachtungen",
        art=Art.BEDINGUNG,
        wer=Wer.NIEMAND,
        befund=111,
        hinweis=(
            "152 sind da, 182 traegt das DSR-Gate. Die Quellen sind gemessen "
            "geschlossen: Maerkte (Nr. 27), Historie (Nr. 14)."
        ),
    ),
    Schritt(
        name="+8,0 % Guete am Spot-Punkt",
        art=Art.BEDINGUNG,
        wer=Wer.SUCHE,
        befund=108,
        hinweis=(
            "Die Suche braeuchte rund 5.951 Versuche (Nr. 110); das Budget "
            "endet bei 230, verbraucht sind 198."
        ),
    ),
    Schritt(
        name="Perpetual oder Spot?",
        art=Art.KLAERUNG,
        wer=Wer.NUTZER,
        befund=112,
        hinweis=(
            "Zwei Gates haengen daran. Zwei Minuten im Bybit-Handelsmenue."
        ),
    ),
    Schritt(
        name="Echte Funding-Raten",
        art=Art.KLAERUNG,
        wer=Wer.NUTZER,
        befund=100,
        hinweis=(
            "data_store/funding/ ist leer; jede Zahl rechnet mit dem "
            "Vorgabewert, dem groessten Kostenblock des Systems."
        ),
    ),
)
