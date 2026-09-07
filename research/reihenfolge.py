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
    Bedingung     +75 unabhaengige Beobachtungen          keiner   111
    Bedingung     +24,3 % Guete am Spot-Punkt             Suche    108
    Klaerung      Perpetual oder Spot?                    Nutzer   112
    Klaerung      echte Funding-Raten                     Nutzer   100

**Die beiden Bedingungen werden gerechnet** (Befund 235). Sie standen hier
elf Befunde lang als fester Text - "+30 Beobachtungen", "+8,0 % Guete", "rund
5.951 Versuche" - und trugen damit den Stand von Befund 108/110/111, als die
effektive Stichprobe noch bei 152 lag. Alle drei Zahlen waren zu guenstig; die
Guete-Luecke auf gut das Dreifache.

Die erste ist gemessen aussichtslos: Die Quellen fuer Beobachtungen sind
geschlossen (Maerkte 27, Historie 14).

Bei der zweiten ist der **Punktschaetzer** des Wettrennens von "5.951
Versuche" auf "holt nicht auf" gekippt - die Ideenstreuung liegt inzwischen
unter dem, was Zufall bei 115 Beobachtungen hergibt. Mehr als ein
Punktschaetzer ist es aber nicht (Befund 236): Der 90-%-Bereich der
Ideenstreuung enthaelt die Nullstreuung, heute wie schon bei Befund 110.
Entschieden war dieser Vergleich nie; gekippt ist die Seite, auf die er
faellt.

Bleiben drei Zeilen, und alle drei stehen beim Nutzer. Das ist keine Ausrede,
sondern das Ergebnis: **Aus diesem Container heraus gibt es keinen Schritt
mehr, der den Zustand aendert.** Die Bybit-Regionssperre wird nicht umgangen;
was hier laeuft, bleibt Vorarbeit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from research.wettrennen import Rennen


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


def _beobachtungen() -> Schritt:
    """Wieviele unabhaengige Beobachtungen noch fehlen - **gerechnet.**

    Bis Befund 235 stand hier "30 unabhaengige Beobachtungen ... 152 sind da,
    182 traegt das DSR-Gate": die Zahlen aus Befund 111, festgeschrieben, als
    die effektive Stichprobe noch bei 152 lag. Die Blockkorrekturen haben sie
    gesenkt, und ein kleineres n verlangt ein groesseres Ziel - die Entfernung
    war damit nach beiden Seiten zu kurz.

    Was heute herauskommt, steht im Bericht und nicht hier: Ein Modulkopf wird
    als Stand gelesen, und das war der ganze Fehler.
    """
    from research.referenz import SPOTPUNKT

    noetig = SPOTPUNKT.noetiges_n()
    fehlend = "?" if noetig is None else str(noetig - SPOTPUNKT.effektiv)
    ziel = "?" if noetig is None else str(noetig)
    return Schritt(
        name=f"+{fehlend} unabhaengige Beobachtungen",
        art=Art.BEDINGUNG,
        wer=Wer.NIEMAND,
        befund=111,
        hinweis=(
            f"{SPOTPUNKT.effektiv} sind da, {ziel} traegt das DSR-Gate. Die "
            f"Quellen sind gemessen geschlossen: Maerkte (Nr. 27), Historie "
            f"(Nr. 14)."
        ),
    )


def _laufsatz(
    rennen: Rennen, effektiv: int, komma: Callable[[float], str]
) -> str:
    """Was das Wettrennen sagt - **mit dem Fehlerbalken, nicht ohne** (236).

    Befund 235 hat hier "Die Suche holt sie nach diesem Modell nicht mehr ein"
    hingeschrieben und die Nullstreuung als Begruendung danebengestellt. Das
    ist ein Punktschaetzer im Ton eines Urteils, und ``wettrennen.py`` sagt in
    seinem eigenen Kopf, warum das nicht traegt:

        "Ob Suchen ueberhaupt besser ist als Wuerfeln, war aus diesem Verlauf
         auch vorher nicht zu entscheiden. Gefallen ist der beste Schaetzwert,
         nicht die Bestimmtheit - die gab es nie."

    Die Ideenstreuung wird aus **einem** beobachteten Bestwert zurueckgerechnet
    und streut bei 198 Versuchen um 14,3 %. Der 90-%-Bereich enthaelt die
    Nullstreuung - heute und schon bei Befund 110. Was sich geaendert hat, ist
    die Seite, auf die der Punktschaetzer faellt, nicht die Bestimmtheit.

    ``Rennen.unsicherheit`` haelt genau das fest, seit Befund 124. Sie stand
    da und wurde nicht gerufen - dieselbe Sorte wie "gebaut, richtig, nicht
    verdrahtet", nur diesmal von mir, einen Befund nach dem Einbau.
    """
    from research.wettrennen import kalibrierbereich

    wo = rennen.wo_holt_sie_auf()
    streuung = rennen.streuung
    if streuung is None:
        # Nicht kalibrierbar ist etwas anderes als 'unter dem Zufall', und die
        # Begruendung darf nicht schaerfer sein als die Rechnung.
        return "Der Verlauf laesst sich nicht kalibrieren (Nr. 110)"

    unten, oben = kalibrierbereich(streuung, rennen.versuche, irrtum=0.10)
    kern = (
        f"Die Suche holt auf bei {wo}"
        if wo != "nie"
        else (
            f"Die Suche holt sie nach diesem Modell nicht mehr ein - die "
            f"Ideenstreuung liegt mit {komma(streuung)} unter dem, was Zufall "
            f"bei {effektiv} Beobachtungen hergibt ({komma(rennen.nullstreuung)})"
        )
    )
    if unten <= rennen.nullstreuung <= oben:
        kern += (
            f", aber das ist ein Punktschaetzer: Der 90-%-Bereich der "
            f"Ideenstreuung reicht von {komma(unten)} bis {komma(oben)} und "
            f"enthaelt die Nullstreuung, das Rennen ist also nach beiden "
            f"Seiten offen"
        )
    # **Und es gilt enger, als es klingt** (Befund 238): kalibriert ist die
    # Streuung am Projektverlauf, und der bestand ueberwiegend aus Reglerscans.
    # Die acht gebauten Regeln streuen breiter und erklaeren diesen Verlauf
    # nicht - zwei Populationen, keine Zahl fuer beide.
    return (
        f"{kern} (Nr. 110). Gemessen ist damit das Scannen von Reglern; "
        f"gebaute Regeln streuen breiter, ihr bester blieb aber unter dem "
        f"Bestand (Nr. 237)"
    )


def _guetelucke() -> Schritt:
    """Wieviel Guete am Spot-Punkt fehlt - und ob die Suche sie einholt.

    **Beides gerechnet, und beides stand hier falsch** (Befund 235). Die Zeile
    hiess "+8,0 % Guete am Spot-Punkt" mit dem Hinweis "rund 5.951 Versuche"
    und trug damit den Stand von Befund 108/110 - Guete 0,2765 bei einer
    effektiven Stichprobe von 152.

    Der Bericht hebt genau diese Zeile als das hervor, was hier laufen wuerde.
    Sie ist die letzte, an der eine Untertreibung teuer ist - deshalb stehen
    die heutigen Zahlen nicht in diesem Kopf, sondern kommen aus der Rechnung
    darunter.
    """
    import math

    from research.referenz import PERPETUALPUNKT, SCHUB, SPOTPUNKT
    from research.verbund import noetige_guete
    from research.wettrennen import Rennen

    def komma(x: float) -> str:
        return f"{x:.4f}".replace(".", ",")

    punkt = SPOTPUNKT
    latte = noetige_guete(
        punkt.effektiv, punkt.versuche, schiefe=punkt.schiefe, woelbung=punkt.woelbung
    )
    erreicht = punkt.guete * math.sqrt(punkt.effektiv)
    anteil = (
        f"{latte / erreicht - 1:+.1%}".replace(".", ",").replace("%", " %")
        if latte
        else "?"
    )

    # ``bester`` gehoert das, was die **Suche** hervorgebracht hat, und gesucht
    # wurde unter Perpetual; der Wegfall des Funding kommt als Schub obendrauf.
    # Den Spot-Wert einzusetzen waere die Falle aus Befund 110.
    rennen = Rennen(
        bester=PERPETUALPUNKT.guete,
        versuche=punkt.versuche,
        trades=punkt.effektiv,
        schub=SCHUB,
        schiefe=punkt.schiefe,
        woelbung=punkt.woelbung,
    )
    lauf = _laufsatz(rennen, punkt.effektiv, komma)
    return Schritt(
        name=f"{anteil} Guete am Spot-Punkt",
        art=Art.BEDINGUNG,
        # **Bleibt bei der Suche, auch wenn das Rennen 'nie' sagt.** Sie laeuft,
        # das Budget hat 32 Versuche uebrig, und der Ausgang haengt an
        # 'mittel' - einer Annahme, keiner Messung. Sie hier auf 'niemand' zu
        # setzen hiesse, eine Annahme als Urteil zu buchen.
        wer=Wer.SUCHE,
        befund=108,
        hinweis=(
            f"{lauf}; das Budget endet bei 230, verbraucht sind {punkt.versuche}."
        ),
    )


#: Der Stand, wie er gemessen ist. Jede Zeile mit Fundstelle.
#:
#: Bewusst hier und nicht im Bericht zusammengesetzt: Wer eine Zeile aendert,
#: aendert sie an einer Stelle, und der Test prueft die Fundstellen gegen das
#: Laborbuch.
#:
#: **Die beiden Bedingungen werden gerechnet, nicht geschrieben** (Befund 235).
#: Sie standen elf Befunde lang auf dem Stand von 108/110/111 und haben die
#: verbleibende Aufgabe damit auf ein Drittel verkuerzt.
STAND: tuple[Schritt, ...] = (
    Schritt(
        name="Boersendaten fehlen",
        art=Art.SPERRE,
        wer=Wer.NUTZER,
        befund=102,
        hinweis=(
            "Jede Zahl steht auf Bitstamp-Kassakursen. GateReport.passed "
            "verlangt Boersendaten - ohne sie gibt es keine Zulassung, egal "
            "wie viele Gates halten. 'cli backfill --intervall D --von 2017-08-16'."
        ),
    ),
    _beobachtungen(),
    _guetelucke(),
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
