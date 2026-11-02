"""Was die Reibung an der **Decke** aendert - Befund 456.

Warum die Reibungsleiter die Frage nicht beantwortet
----------------------------------------------------
``kostenanteil.Reibungsleiter`` faehrt denselben Katalog bei anderer Reibung
und berichtet die **Kopplung** zwischen Trade-Zahl und Qualitaet. Auf
Viertelstunden war das die richtige Zahl: Dort haengt die Guete an der
Kopplung, und Befund 453 hat gemessen, dass die Reibung 44 % davon traegt.

Auf Tageskerzen ist es die falsche. Befund 290 hat dort gemessen:

    Die Qualitaet je Trade faellt mit der Menge (rho = -0,679, t = -3,70) -
    aber die **Guete** haengt nicht daran (rho = +0,072, t = +0,29). Was
    fehlt, fehlt an der Guete.

Die Leiter berichtet also eine Zahl, die auf Tageskerzen nichts entscheidet,
und schweigt zu der, die alles entscheidet: Wie weit ist die naechste Regel
von ihrer Latte, und bewegt sich das, wenn die Reibung verschwindet?

Was dieses Modul tut
--------------------
Dieselben Sprossen, aber mit der Decke statt der Kopplung: je Sprosse die
**kleinste Luecke** zur Latte, und was sich zwischen den Sprossen daran
aendert.

Die kleinste Luecke und nicht die hoechste Guete: Die Latte gehoert der Regel
und nicht der Trade-Zahl - sie rechnet mit deren Schiefe und Woelbung (Befund
191). Zwei Regeln mit derselben Guete haben verschiedene Latten, und was
zaehlt, ist der Abstand zur eigenen.

Verglichen wird nur bei **gleicher Regelmenge** (Befund 301): Ohne Reibung
fallen Fuellungen anders aus, und eine Regel kann im einen Lauf genug Trades
haben und im anderen nicht. Waere die Menge verschieden, verglichen sich zwei
Populationen - der Fehler, den dieses Projekt oefter gemacht hat als jeden
anderen.

Was es nicht tut
----------------
**Es rechnet keine Guete aus einer Trade-Zahl.** Die Guete ist ``SR je Trade``
mal Wurzel aus ``n_eff``, und ``n_eff`` ist nicht die Trade-Zahl - am
Spot-Punkt stehen 156 Trades und 115 wirksame. Eine Sprosse, die ``n_eff``
nicht gemessen hat, traegt hier keine Decke, und das wird gesagt statt
geschaetzt. Protokolle von vor Befund 456 sind genau dieser Fall.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.vorratsdecke import Punkt

__all__ = ["Deckenleiter", "Deckensprosse", "Luecke"]


@dataclass(frozen=True, slots=True)
class Luecke:
    """Eine Regel, ihre eigene Latte und der Abstand dazu."""

    punkt: Punkt
    latte: float

    @property
    def fehlt(self) -> float:
        return self.latte - self.punkt.guete

    @property
    def raeumt(self) -> bool:
        return self.fehlt <= 0

    def als_abstand(self) -> str:
        """"es fehlen 1,061" oder "sie raeumt ihre Latte um 0,012".

        Zwei Formulierungen und nicht eine mit Vorzeichen: *"es fehlen
        -0,012"* stand hier zuerst, und das ist der folgenreichste Satz, den
        dieser Bericht drucken kann - er meldet eine Regel, die ihre Latte
        raeumt. Dort darf nicht gerechnet werden muessen.
        """
        if self.raeumt:
            return f"sie raeumt ihre Latte um {-self.fehlt:.3f}"
        return f"es fehlen {self.fehlt:.3f}"

    def als_wort(self) -> str:
        """Dasselbe als Satzglied - nach "mit ..." statt als Hauptsatz."""
        if self.raeumt:
            return f"{-self.fehlt:.3f} Luft ueber ihrer Latte"
        return f"einer Luecke von {self.fehlt:.3f}"


@dataclass(frozen=True, slots=True)
class Deckensprosse:
    """Ein voller Katalogdurchlauf bei einer Reibung - mit Decke."""

    faktor: float
    punkte: tuple[Punkt, ...] = ()

    @property
    def regeln(self) -> frozenset[str]:
        return frozenset(p.name for p in self.punkte)

    def luecken(self, versuche: int) -> tuple[Luecke, ...]:
        """Je Regel ihre eigene Latte - nur die, fuer die es eine gibt.

        Wo ``noetige_guete`` nichts liefert, urteilt das Gate bei dieser
        Stichprobe nicht; eine solche Regel kann zu der Frage "reicht das je?"
        nichts beitragen.
        """
        from research.verbund import noetige_guete

        aus: list[Luecke] = []
        for p in self.punkte:
            latte = noetige_guete(
                p.n_eff, versuche, schiefe=p.schiefe, woelbung=p.woelbung
            )
            if latte is not None:
                aus.append(Luecke(punkt=p, latte=latte))
        return tuple(aus)

    def naechste(self, versuche: int) -> Luecke | None:
        """Die Regel, die ihrer Latte am naechsten steht."""
        luecken = self.luecken(versuche)
        return min(luecken, key=lambda x: x.fehlt) if luecken else None


@dataclass(frozen=True, slots=True)
class Deckenleiter:
    """Dieselben Regeln bei anderer Reibung - gemessen an ihren Latten."""

    sprossen: tuple[Deckensprosse, ...] = ()
    versuche: int = 0

    @property
    def geordnet(self) -> list[Deckensprosse]:
        return sorted(self.sprossen, key=lambda s: s.faktor)

    @property
    def mit_decke(self) -> list[Deckensprosse]:
        """Die Sprossen, die ueberhaupt Punkte tragen.

        Ein Protokoll von vor Befund 456 hat ``n_eff`` je Sprosse nicht
        gemessen; dort steht hier eine leere Sprosse, und das ist kein Fehler,
        sondern eine fehlende Messung.
        """
        return [s for s in self.geordnet if s.punkte]

    @property
    def gleiche_regeln(self) -> bool:
        decken = self.mit_decke
        if len(decken) < 2:
            return False
        erste = decken[0].regeln
        return all(s.regeln == erste for s in decken[1:])

    @property
    def belastbar(self) -> bool:
        return (
            len(self.mit_decke) >= 2
            and self.gleiche_regeln
            and all(s.naechste(self.versuche) is not None for s in self.mit_decke)
        )

    @property
    def anteil_an_der_luecke(self) -> float | None:
        """Wie viel der Luecke die Reibung traegt.

        Gerechnet als Weg zur Null vom **Betriebspunkt** (Faktor 1) aus: 0
        heisst, die Reibung traegt nichts davon, 1 heisst, ohne sie waere die
        Luecke geschlossen.

        ``None``, wenn Faktor 1 oder Faktor 0 nicht gefahren wurden - ein
        Anteil ohne diese beiden Enden waere eine Zahl ohne Bezug.
        """
        if not self.belastbar:
            return None
        betrieb, frei = self.bei(1.0), self.bei(0.0)
        if betrieb is None or frei is None:
            return None
        a, b = betrieb.naechste(self.versuche), frei.naechste(self.versuche)
        if a is None or b is None or a.fehlt <= 0:
            return None
        return (a.fehlt - b.fehlt) / a.fehlt

    def bei(self, faktor: float) -> Deckensprosse | None:
        for s in self.mit_decke:
            if s.faktor == faktor:
                return s
        return None

    def tabelle(self) -> str:
        zeilen = [
            f"{'Faktor':>8}{'Regeln':>8}{'beste Guete':>13}{'Latte':>9}"
            f"{'fehlt':>8}",
            "-" * 46,
        ]
        for s in self.geordnet:
            naechste = s.naechste(self.versuche)
            if naechste is None:
                zeilen.append(
                    f"{s.faktor:>8g}{len(s.punkte):>8}{'-':>13}{'-':>9}{'-':>8}"
                )
                continue
            zeilen.append(
                f"{s.faktor:>8g}{len(s.luecken(self.versuche)):>8}"
                f"{naechste.punkt.guete:>13.3f}{naechste.latte:>9.3f}"
                f"{naechste.fehlt:>8.3f}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.mit_decke:
            return (
                "**Keine Decke je Sprosse gemessen.** Diese Protokolle "
                "stammen von vor Befund 456 und halten je Sprosse nur den "
                "Sharpe je Trade fest. Die Guete braucht 'n_eff', und das ist "
                "nicht die Trade-Zahl - geschaetzt wuerde hier nichts."
            )
        if len(self.mit_decke) < 2:
            # **Vor der Regelmengen-Pruefung** (und das war erst falsch
            # herum): ``gleiche_regeln`` ist bei einer einzigen Sprosse schon
            # ``False``, und dann stand hier "verschiedene Regeln (0 nur in
            # einem Teil der Laeufe)" - eine Meldung, die den Grund verdeckt.
            ohne = [
                f"{s.faktor:g}" for s in self.geordnet if not s.punkte
            ]
            fehlend = (
                f" Ohne Decke: Faktor {', '.join(ohne)} - diese Sprossen "
                f"stammen aus Protokollen von vor Befund 456 und haben "
                f"'n_eff' nicht festgehalten. Neu messen, dann steht sie da."
                if ohne
                else ""
            )
            return (
                f"**Nur eine Sprosse mit Decke** (Faktor "
                f"{self.mit_decke[0].faktor:g}). Ein Vergleich braucht zwei; "
                f"eine einzelne Zahl sagt ueber die Wirkung der Reibung "
                f"nichts.{fehlend}"
            )
        if not self.gleiche_regeln:
            mengen = [s.regeln for s in self.mit_decke]
            unterschied = set().union(*mengen) - set.intersection(
                *(set(m) for m in mengen)
            )
            return (
                f"**Nicht vergleichbar.** Die Sprossen tragen verschiedene "
                f"Regeln ({len(unterschied)} nur in einem Teil der Laeufe). "
                f"Ohne Reibung fallen Fuellungen anders aus, und eine Regel "
                f"kann im einen Lauf genug Trades haben und im anderen nicht - "
                f"verglichen wuerden dann zwei Populationen."
            )
        if not self.belastbar:
            ohne_latte = [
                f"{s.faktor:g}"
                for s in self.mit_decke
                if s.naechste(self.versuche) is None
            ]
            return (
                f"**Keine Latte auf Faktor {', '.join(ohne_latte)}.** Dort "
                f"urteilt das Gate bei dieser Stichprobe nicht, und eine "
                f"Luecke zu einer Latte, die es nicht gibt, ist keine Zahl."
            )

        teile: list[str] = []
        erste, letzte = self.mit_decke[0], self.mit_decke[-1]
        a = erste.naechste(self.versuche)
        b = letzte.naechste(self.versuche)
        assert a is not None and b is not None  # von 'belastbar' zugesichert

        teile.append(
            f"**Am naechsten kommt bei Faktor {erste.faktor:g} "
            f"'{a.punkt.name}'**: Guete {a.punkt.guete:.3f} gegen eine Latte "
            f"von {a.latte:.3f}, {a.als_abstand()}. Bei Faktor "
            f"{letzte.faktor:g} ist es '{b.punkt.name}' mit {b.als_wort()}."
        )
        if a.punkt.name != b.punkt.name:
            # **Die naechste Regel wechselt** - und das ist kein Nebensatz.
            # Ohne Reibung handelt jede Regel dieselbe Zahl von Trades, aber
            # 'n_eff' bewegt sich (gemessen: 3 von 13), und mit ihm die Latte.
            # Wer nur die Guete einer Regel verfolgt, sieht das nicht.
            teile.append(
                f"**Es ist nicht dieselbe Regel.** Ohne Reibung steht "
                f"'{b.punkt.name}' ihrer Latte am naechsten, mit Reibung "
                f"'{a.punkt.name}'. Beide Seiten der Luecke bewegen sich: Die "
                f"Guete steigt, und die Latte aendert sich mit 'n_eff' und den "
                f"Momenten. Deshalb ist die kleinste Luecke die Zahl und nicht "
                f"die hoechste Guete."
            )

        # **Rollen und nicht Positionen.** ``erste``/``letzte`` sind die
        # aeussersten Sprossen; der Betriebspunkt ist Faktor 1 und die
        # reibungslose Welt Faktor 0. Bei einer Leiter {1, 2} gibt es die
        # zweite gar nicht, und die Urteile darunter haengen an ihr - erst
        # verwechselt und vom eigenen Test gefunden.
        betrieb = self.bei(1.0)
        frei = self.bei(0.0)
        freie_luecke = None if frei is None else frei.naechste(self.versuche)

        anteil = self.anteil_an_der_luecke
        if anteil is None:
            teile.append(
                "**Kein Anteil ablesbar** - dafuer braucht es den "
                "Betriebspunkt (Faktor 1) und die reibungslose Welt (Faktor "
                "0). Ohne beide Enden waere der Anteil eine Zahl ohne Bezug."
            )
        elif anteil <= 0.02:
            teile.append(
                f"**Die Reibung traegt die Luecke nicht** - sie hebt "
                f"{anteil:.1%} davon auf. Billiger zu handeln bewegt diese "
                f"Decke nicht; was fehlt, fehlt an den Signalen."
            )
        elif freie_luecke is not None and freie_luecke.raeumt:
            # Ueber 100 % des Weges sind arithmetisch richtig und lesen sich
            # wie ein Rechenfehler. Was zaehlt, ist, dass die Latte fiele.
            am_punkt = None if betrieb is None else betrieb.naechste(self.versuche)
            teile.append(
                f"**Ohne Reibung ist die Luecke zu** - "
                f"'{freie_luecke.punkt.name}' raeumt dort ihre Latte um "
                f"{-freie_luecke.fehlt:.3f}. Das ist keine Zulassung: "
                f"Gehandelt wird mit Reibung, und am Betriebspunkt "
                + (
                    f"{am_punkt.als_abstand()}"
                    if am_punkt is not None
                    else "steht keine Messung"
                )
                + ". Es sagt, dass die Reibung und nicht das Signal der "
                "Anschlag ist."
            )
        elif anteil >= 0.98:
            teile.append(
                f"**Die Luecke ist fast ganz Reibung** - ohne sie sind es "
                f"{anteil:.1%} des Weges. Dann entscheidet die Frage, wie nah "
                f"an die reibungslose Welt ein echter Lauf kommt."
            )
        else:
            teile.append(
                f"**Teils.** Die Reibung hebt {anteil:.1%} der Luecke auf - "
                f"ein sichtbarer Teil, aber die Luecke bleibt ohne sie "
                f"offen. Der Rest haengt an den Signalen."
            )

        teile.append(
            f"Die Latte gehoert dabei der Regel und nicht der Trade-Zahl: Sie "
            f"rechnet mit deren Schiefe und Woelbung (Befund 191). Gemessen "
            f"auf {len(self.mit_decke)} Sprossen bei Versuchsstand "
            f"{self.versuche}, je ein voller Katalogdurchlauf."
        )
        return "\n\n".join(teile)
