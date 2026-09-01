"""Woran ein Gate wirklich scheitert - und wer es beheben kann.

Der Anlass
----------
``cli stand`` zeigt die Gates als Zahlenpaar:

    - Messlatte                   166.143 gegen     43.639

Das liest sich als "um das 3,8-fache verfehlt". Tatsaechlich ist es das
Gegenteil: 166,1 ist die Rendite der Strategie, 43,6 die des auf ihren
Rueckgang heruntergefahrenen Haltens. **Risikobereinigt ist das Gate um das
3,8-fache uebererfuellt.** Es scheitert an einer zweiten Bedingung, die in der
Zeile gar nicht vorkommt: 13,5 % Jahresrendite gegen die geforderten 15 %.

Ich bin darauf hereingefallen - beim Lesen der eigenen Tabelle, in Befund 91,
und habe daraus zuerst geschlossen, die Messlatte sei das am weitesten
entfernte Gate. Sie ist das am wenigsten entfernte.

Warum das mehr ist als ein Anzeigefehler
----------------------------------------
Ein Gate mit zwei Bedingungen laesst sich nicht auf ein Zahlenpaar
zusammenziehen. Wer es doch tut, bekommt eine Zeile, die plausibel aussieht
und in die falsche Richtung zeigt - und das ist schlimmer als gar keine Zahl,
weil niemand nachfragt.

``GateResult.message`` enthaelt die Erklaerung seit jeher. Sie wurde nur nie
angezeigt.

Die zweite Sache, die dabei auffiel
-----------------------------------
Die vier offenen Gates sind **nicht vier gleichartige Aufgaben**:

    Messlatte           wirtschaftliche Schwelle - liegt beim Nutzer
    Deflated Sharpe     durchgemessen, alle Wege geschlossen (Befund 54-89)
    Schlechtestes Jahr  nie untersucht, fehlen 0,32 Punkte
    Parameter-Plateau   nie untersucht, 1 von 2 Nachbarn in zwei Richtungen

Fuenfzehn Laeufe gingen an den Deflated Sharpe. Zwei Gates daneben sind in
dieser Zeit kein einziges Mal angesehen worden, und eines davon liegt
ueberhaupt nicht in meiner Hand.

Was dieses Modul tut
--------------------
Es ordnet die Gates nach **Art des Hindernisses** statt nach Abstand. Der
Abstand allein sagt nichts: 0,32 Punkte beim Schlechtesten Jahr sind eine
Eigenschaft der Kapitalkurve, 1,5 Punkte Jahresrendite sind eine
Geschaeftsentscheidung, und beide stehen in derselben Spalte.

Was es **nicht** tut: Schwellen bewerten. Ob 15 % Jahresrendite die richtige
Forderung ist, steht hier nicht zur Debatte - nur, dass es eine andere Art von
Forderung ist als "der Vorteil ist zu 78 % echt".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum


class Art(StrEnum):
    """Welcher Art das Hindernis ist - davon haengt ab, wer es angeht."""

    WIRTSCHAFTLICH = "wirtschaftlich"
    """Eine gesetzte Schwelle, keine Messung. Sie zu aendern ist eine
    Geschaeftsentscheidung und faellt nicht hier."""

    DURCHGEMESSEN = "durchgemessen"
    """Untersucht, alle Wege geschlossen. Weitere Laeufe daran kosten Zeit,
    ohne dass eine offene Frage dahintersteht."""

    OFFEN = "offen"
    """Nie untersucht. Hier liegt die Arbeit."""


#: Gates, deren Schwelle eine wirtschaftliche Setzung ist. Steht als Liste da
#: und nicht als Erkennungsregel: Wer eine Schwelle fuer wirtschaftlich
#: erklaert, entzieht sie der Arbeit - das gehoert benannt, nicht geraten.
WIRTSCHAFTLICHE_GATES: frozenset[str] = frozenset({"Messlatte"})

#: Gates, an denen die Untersuchung abgeschlossen ist, mit der Fundstelle im
#: Laborbuch. Ein Eintrag hier heisst nicht "unloesbar", sondern "die
#: naheliegenden Wege sind gemessen und zu".
DURCHGEMESSENE_GATES: dict[str, int] = {"Deflated Sharpe": 89}


@dataclass(frozen=True, slots=True)
class Hindernis:
    """Ein nicht bestandenes Gate, nach Art eingeordnet."""

    name: str
    wert: float
    schwelle: float
    botschaft: str
    art: Art
    fundstelle: int | None = None
    nur_hier: bool = False
    """Faellt dieses Gate **nur** am berichteten Betriebspunkt durch?

    ``cli stand`` rechnet den Kandidaten an zwei Punkten und berichtet
    absichtlich den schlechteren, weil die Voraussetzung offen ist. Ein Gate,
    das am anderen Punkt besteht, ist damit keine Aufgabe, sondern eine Folge
    dieser Wahl - und das gehoert dazugesagt (Befund 164).
    """

    @property
    def zahlen_erklaeren_es(self) -> bool:
        """Sagt das Zahlenpaar, woran es scheitert?

        Bei der Messlatte nicht: Dort liegt der Wert **ueber** der Schwelle,
        und das Gate faellt trotzdem durch. Wo das so ist, ist die Zeile ohne
        die Botschaft nicht bloss unvollstaendig, sondern irrefuehrend.
        """
        return not (self.wert >= self.schwelle and self.art is Art.WIRTSCHAFTLICH)

    def als_zeile(self) -> str:
        kopf = f"{self.name:<20} {self.wert:>10.3f} gegen {self.schwelle:>9.3f}"
        if self.art is Art.DURCHGEMESSEN and self.fundstelle:
            return f"{kopf}   durchgemessen (Nr. {self.fundstelle})"
        return f"{kopf}   {self.art}"


@dataclass(slots=True)
class Gatelage:
    """Alle offenen Gates - geordnet danach, wer sie angehen kann."""

    hindernisse: list[Hindernis] = field(default_factory=list)
    zweitpunkt: str | None = None
    """Name des anderen Betriebspunkts, falls einer gemessen wurde."""

    @property
    def offen(self) -> list[Hindernis]:
        """Die Gates, an denen tatsaechlich Arbeit liegt."""
        return [h for h in self.hindernisse if h.art is Art.OFFEN]

    @property
    def am_punkt(self) -> list[Hindernis]:
        """Offene Gates, die am anderen Betriebspunkt bestehen."""
        return [h for h in self.offen if h.nur_hier]

    @property
    def beim_nutzer(self) -> list[Hindernis]:
        return [h for h in self.hindernisse if h.art is Art.WIRTSCHAFTLICH]

    @property
    def abgeschlossen(self) -> list[Hindernis]:
        return [h for h in self.hindernisse if h.art is Art.DURCHGEMESSEN]

    @property
    def irrefuehrende(self) -> list[Hindernis]:
        """Gates, deren Zahlenpaar in die falsche Richtung zeigt."""
        return [h for h in self.hindernisse if not h.zahlen_erklaeren_es]

    def tabelle(self) -> str:
        if not self.hindernisse:
            return "Alle Gates bestanden."
        zeilen = ["Nicht bestanden:", "-" * 68]
        for h in self.hindernisse:
            zeilen.append(f"  {h.als_zeile()}")
            zeilen.append(f"      {h.botschaft}")
        return "\n".join(zeilen)

    def _punktabsatz(self) -> list[str]:
        """Wieviel der genannten Arbeit an der Wahl des Betriebspunkts haengt.

        ``cli stand`` misst zwei Punkte, berichtet den schlechteren und sagt
        drei Zeilen weiter oben, dass der andere gemessen besser ist. Die
        Aufgabenliste kam bis Befund 164 allein aus dem berichteten Punkt -
        und nannte beim Bestand genau die zwei Gates, die am anderen Punkt
        bestehen. Wer sie las, sah eine Arbeit vor sich, die sich mit der
        Antwort auf eine offene Frage in Luft aufloest.

        **Gemessen wird dadurch nichts besser.** Es ist derselbe Kandidat
        unter anderen Handelsbedingungen; welche gelten, weiss nur der Nutzer.
        Berichtet wird weiter der schlechtere Punkt.
        """
        haengend = self.am_punkt
        if not haengend or self.zweitpunkt is None:
            return []
        namen = ", ".join(h.name for h in haengend)
        alle = len(haengend) == len(self.offen)
        kopf = (
            "**Die ganze Arbeit haengt am Betriebspunkt.**"
            if alle
            else f"**{len(haengend)} davon haengen am Betriebspunkt.**"
        )
        return [
            f"{kopf} Unter '{self.zweitpunkt}' bestanden: {namen}. Berichtet "
            f"wird weiter der schlechtere Punkt, weil die Voraussetzung offen "
            f"ist - klaert sie sich zu '{self.zweitpunkt}', entfaellt diese "
            f"Arbeit. Gemessen wird dadurch nichts besser: derselbe Kandidat, "
            f"andere Handelsbedingungen."
        ]

    def urteil(self) -> str:
        if not self.hindernisse:
            return "Alle Gates bestanden."

        teile = []
        offen, nutzer, fertig = self.offen, self.beim_nutzer, self.abgeschlossen
        teile.append(
            f"**{len(self.hindernisse)} Gates offen - aber nicht "
            f"{len(self.hindernisse)} Aufgaben.**"
        )
        if nutzer:
            namen = ", ".join(h.name for h in nutzer)
            teile.append(
                f"{namen}: eine gesetzte Schwelle, keine Messung. Sie zu "
                f"aendern ist eine Geschaeftsentscheidung und faellt nicht hier."
            )
        if fertig:
            namen = ", ".join(
                f"{h.name} (Nr. {h.fundstelle})" if h.fundstelle else h.name
                for h in fertig
            )
            teile.append(
                f"{namen}: durchgemessen, alle naheliegenden Wege sind zu. "
                f"Weitere Laeufe daran kosten Zeit ohne offene Frage."
            )
        if offen:
            namen = ", ".join(h.name for h in offen)
            teile.append(f"**Hier liegt die Arbeit: {namen}.**")
            teile.extend(self._punktabsatz())
        else:
            teile.append(
                "**Kein Gate mehr, an dem eine offene Frage haengt.** Was "
                "bleibt, liegt beim Nutzer oder ist gemessen."
            )

        irre = self.irrefuehrende
        if irre:
            h = irre[0]
            teile.append(
                f"Und eine Warnung zur Tabelle: Bei '{h.name}' liegt der Wert "
                f"**ueber** der Schwelle ({h.wert:.1f} gegen {h.schwelle:.1f}) "
                f"und das Gate faellt trotzdem durch - es hat eine zweite "
                f"Bedingung, die im Zahlenpaar nicht vorkommt. Ohne die "
                f"Botschaft zeigt die Zeile in die falsche Richtung."
            )
        return "\n\n".join(teile)


def ordne(
    ergebnisse,
    *,
    zweitpunkt: str | None = None,
    dort_offen: Iterable[str] | None = None,
) -> Gatelage:
    """Die nicht bestandenen Gates eines Berichts einordnen.

    Nimmt ``GateResult``-Objekte entgegen. Bestandene fallen heraus - hier
    geht es um Hindernisse, nicht um eine Gesamtschau.

    ``zweitpunkt`` und ``dort_offen`` beschreiben den **anderen**
    Betriebspunkt: seinen Namen und die Gates, die dort offen sind. Damit
    laesst sich sagen, welche der hier genannten Aufgaben an der Wahl des
    Punktes haengen (Befund 164). Ohne beides bleibt es beim alten Verhalten.

    **Beides oder keines.** Ein Name ohne Menge koennte jedes Gate als
    "haengt am Punkt" ausweisen, weil ``dort_offen`` dann leer waere - das
    waere eine Behauptung ueber eine Messung, die nicht stattgefunden hat.
    """
    if (zweitpunkt is None) != (dort_offen is None):
        raise ValueError(
            "zweitpunkt und dort_offen gehoeren zusammen - ein Name ohne "
            "gemessene Gateliste wuerde jedes Gate als punktabhaengig "
            "ausweisen."
        )
    dort = frozenset(dort_offen or ())
    hindernisse = []
    for r in ergebnisse:
        if r.passed:
            continue
        if r.name in WIRTSCHAFTLICHE_GATES:
            art, fundstelle = Art.WIRTSCHAFTLICH, None
        elif r.name in DURCHGEMESSENE_GATES:
            art, fundstelle = Art.DURCHGEMESSEN, DURCHGEMESSENE_GATES[r.name]
        else:
            art, fundstelle = Art.OFFEN, None
        hindernisse.append(
            Hindernis(
                name=r.name, wert=float(r.value), schwelle=float(r.threshold),
                botschaft=r.message, art=art, fundstelle=fundstelle,
                nur_hier=zweitpunkt is not None and r.name not in dort,
            )
        )
    return Gatelage(hindernisse=hindernisse, zweitpunkt=zweitpunkt)


__all__ = [
    "DURCHGEMESSENE_GATES",
    "WIRTSCHAFTLICHE_GATES",
    "Art",
    "Gatelage",
    "Hindernis",
    "ordne",
]
