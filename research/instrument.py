"""Fuer welches Instrument ist der Kandidat eigentlich gebaut?

Die Frage stammt aus dem Plan des Nutzers
-----------------------------------------
*"Bybit EU bietet keine Perpetual Futures an ... Wenn dein Account migriert
wurde, kannst du keine Perpetuals handeln - und damit auch nicht die
Hebel-Mechanik, die ich gebaut und getestet habe."*

Der ganze Backtest rechnet Perpetuals: Hebel bis 3x, Funding alle acht
Stunden. Ob der Kandidat das ueberhaupt **braucht**, hat nie jemand gemessen.

Was gemessen ist
----------------
Der Kapitalanteil der Groessensteuerung, ueber die Balken des **gemeinsamen
Zeitraums** von BTC und ETH - also genau die, die der Backtest sieht:

    Median                   0,35
    Maximum                  1,28
    ueber 1,0                0,2 % der Balken

(Auf der vollen BTC-Historie ab 2012 waeren es 1,3 %. Eine richtige Zahl ueber
einen Zeitraum, den die Messung nicht kennt - der Test dazu ist dem ersten
Anlauf genau darauf hereingefallen.)

Und der Kandidat ist **long-only**: ``entry_short`` und ``exit_short`` sind
leer. Er braucht also weder Hebel noch Leerverkauf - beides Voraussetzungen,
die nur ein Perpetual erfuellt.

Der Deckel kostet nichts, und das ist gemessen
----------------------------------------------
``fraction`` von 3,0 auf 1,0 gesenkt, sonst alles gleich:

    fraction 3,0   152 Trades   13,47 % p.a.   Rueckgang 10,64 %   Brutto 776,97
    fraction 1,0   152 Trades   13,47 % p.a.   Rueckgang 10,64 %   Brutto 776,97

**Bitgleich.** Keine Schwelle, keine Abwaegung - dieselben Zahlen bis auf die
letzte Stelle. Damit ist der ganze Unterschied zwischen Perpetual und Spot das
**Funding**, und sonst nichts.

Was daraus wird
---------------
    Lauf                       Trades   Rendite   Rueckgang   Gates
    Perpetual                     152   13,47 %     10,64 %    7/11
    Spot                          152   14,83 %      9,87 %    9/11
    Spot, doppelte Gebuehren      152   14,59 %     10,10 %    9/11

Im Spot-Handel gibt es kein Funding. Es faellt weg, und mit ihm die beiden
Gates, die in Befund 100 daran gekippt sind: Schlechtestes Jahr und
Parameter-Plateau. Offen bleiben **Messlatte und Deflated Sharpe**.

Eine Korrektur an Befund 100
----------------------------
Dort steht ueber die Nullzeile beim Funding:

    *"Sie ist eine Empfindlichkeit, kein Szenario: Funding entfaellt nur im
    Spot-Handel, und dort entfaellt auch der Hebel - die gemessenen
    Positionsgroessen kaemen gar nicht zustande."*

**Der zweite Halbsatz ist widerlegt.** Die Positionsgroessen kommen zustande;
der Deckel kostet bitgleich nichts. Ich habe angenommen, die Strategie
brauche ihren Hebel, ohne nachzusehen - und die Annahme in einen Befund
geschrieben. Die Nullzeile ist ein Szenario.

Was dabei ehrlich bleiben muss
------------------------------
1. **Die Messlatte ist knapp, nicht erfuellt.** 14,83 % gegen geforderte
   15,00 % - es fehlen 0,17 Punkte. Knapp daneben ist nicht bestanden, und
   die Schwelle wird nicht gesenkt.
2. **Der Deflated Sharpe bewegt sich nicht.** Er war und bleibt das Gate, an
   dem alles haengt.
3. **Spot-Gebuehren sind hier nicht gemessen.** Bybits Spot-Tarif liegt ueber
   dem der Perpetuals; die Zeile "doppelte Gebuehren" ist ein **Stresstest**
   und keine Messung. Dass sie 9 von 11 haelt, sagt, dass es an den Gebuehren
   nicht scheitern duerfte - nicht, wie hoch sie sind.
4. **Befund 102 gilt weiter**, aber sein groesster Einwand faellt: Bitstamp
   BTC/USD ist ein **Kassamarkt**. Fuer eine Spot-Strategie ist das nicht
   mehr das falsche Instrument, sondern das richtige - es bleiben andere
   Boerse, andere Liquiditaet und USD statt USDT. Der Einwand "keine
   Funding-Zahlungen" verschwindet, weil Spot keine hat.

Was das mit dem Deflated Sharpe macht (Befund 108)
--------------------------------------------------
Oben stehen Gate-**Zahlen**. Der Wert des einen Gates, an dem alles haengt,
fehlte - und er ist der eigentliche Fund:

    Perpetual   DSR 0,7641   Guete je Trade 0,2597
    Spot        DSR 0,8640   Guete je Trade 0,2765   (+6,5 %)

**Der Deflated Sharpe steigt um 0,0999.** Es fehlen noch 0,0860 auf die
Schwelle von 0,95. In Gueteeinheiten: noetig sind 0,2987 statt der erreichten
0,2765, also **+8,0 %**. Vor dem Wegfall des Funding waren es +14 %.

Funding ist ein Abzug je Positionstag auf den Nominalwert - ein
gleichmaessiger Zug an jedem Trade. Faellt er weg, steigt der mittlere Ertrag
je Trade, waehrend die Streuung fast gleich bleibt. Genau daraus ist die Guete
gebaut.

**Und das kostet keinen Versuch:** Es ist eine Kostenaenderung, keine Suche.
Die Haelfte des Abstands, der seit Befund 61 als "durchgemessen" galt, faellt
weg, ohne dass die Huerde steigt.

Traegt der Vorteil den Spot-Tarif?
----------------------------------
Der Spot-Lauf rechnet mit dem Gebuehrentarif der **Perpetuals** (Maker
0,020 %, Taker 0,055 %). Bybits Spot-Tarif liegt darueber, und wie hoch, ist
aus diesem Container nicht nachzuschlagen. Also gestresst statt geraten:

    Gebuehren   DSR      Guete    Rendite   Gates   dann offen
    x1          0,8640   0,2765   14,83 %    9/11   Messlatte, DSR
    x2          0,8458   0,2731   14,59 %    9/11   Messlatte, DSR
    x2,75       0,8314   0,2705   14,42 %    9/11   Messlatte, DSR
    x3          0,8265   0,2697   14,36 %    8/11   + Schlechtestes Jahr

**Der Vorteil traegt bis zum 2,75-fachen des Perpetual-Tarifs.** Darueber
kippt das schlechteste Jahr - dasselbe Gate, das schon in Befund 100 am
empfindlichsten war.

Welcher Faktor gilt, entscheidet der **Fuellmix**: Einstiege und Take-Profits
laufen als PostOnly-Limit (Maker), Stops als Taker. Ein Spot-Tarif von 0,1 %
waere gegenueber dem Maker-Satz das Fuenffache, gegenueber dem Taker-Satz
knapp das Doppelte. Ohne den echten Tarif und den echten Mix ist das keine
Zahl, sondern eine Spanne - und sie schliesst die Bruchstelle ein.

Kostet keinen Versuch: Derselbe Kandidat, dieselben Daten, unter anderen
Handelsbedingungen. Es wird nichts ausgewaehlt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise


@dataclass(frozen=True, slots=True)
class Lauf:
    """Ein Durchlauf unter bestimmten Handelsbedingungen."""

    name: str
    trades: int
    cagr: float
    rueckgang: float
    bestanden: int
    gesamt: int
    gescheitert: tuple[str, ...] = ()
    funding: float = 0.0
    gebuehren: float = 0.0
    brutto: float = 0.0
    sharpe: float = 0.0

    def gleiche_zahlen(self, andere: Lauf) -> bool:
        """Liefern zwei Laeufe dieselben Kennzahlen?

        Auf zwei Nachkommastellen, weil so berichtet wird. Eine Toleranz
        darueber hinaus waere hier falsch: Die Frage ist, ob der Deckel
        ueberhaupt etwas veraendert, nicht ob die Veraenderung klein ist.
        """
        return (
            self.trades == andere.trades
            and round(self.cagr, 2) == round(andere.cagr, 2)
            and round(self.rueckgang, 2) == round(andere.rueckgang, 2)
            and round(self.brutto, 2) == round(andere.brutto, 2)
        )


@dataclass(slots=True)
class Instrumentenwahl:
    """Braucht der Kandidat ein Perpetual - oder genuegt Spot?"""

    mit_hebel: Lauf
    """Der Lauf, wie das Projekt ihn seit jeher rechnet."""
    ohne_hebel: Lauf
    """Derselbe Lauf mit ``fraction`` auf 1,0, Funding unveraendert."""
    spot: Lauf | None = None
    """Ohne Hebel **und** ohne Funding - der Spot-Fall."""
    spot_gestresst: Lauf | None = None
    """Spot mit doppelten Gebuehren, als Ersatz fuer den unbekannten
    Spot-Tarif. Ein Stresstest, keine Messung."""

    short_regeln: int = 0
    """Zahl der Leerverkaufsregeln im Genom. Spot kann keine."""
    anteil_ueber_eins: float = 0.0
    """Anteil der Balken, an denen die Groessensteuerung ueber 1,0 will."""
    weitere: list[Lauf] = field(default_factory=list)

    @property
    def deckel_kostet_nichts(self) -> bool:
        """**Gemessen, nicht geschaetzt.**

        Nicht "der Anteil ueber 1,0 ist klein" - das waere eine Schwelle, die
        ich mir aussuche. Sondern: Der gedeckelte Lauf liefert dieselben
        Zahlen. Wenn ja, ist der Hebel nachweislich ungenutzt.
        """
        return self.ohne_hebel.gleiche_zahlen(self.mit_hebel)

    @property
    def braucht_shorts(self) -> bool:
        return self.short_regeln > 0

    @property
    def spot_moeglich(self) -> bool:
        """Beides muss stimmen: kein Leerverkauf und kein genutzter Hebel."""
        return self.deckel_kostet_nichts and not self.braucht_shorts

    @property
    def gewinn_an_gates(self) -> int:
        if self.spot is None:
            return 0
        return self.spot.bestanden - self.mit_hebel.bestanden

    @property
    def haelt_den_stress(self) -> bool | None:
        """Bleibt die Spot-Bilanz auch bei doppelten Gebuehren stehen?"""
        if self.spot is None or self.spot_gestresst is None:
            return None
        return self.spot_gestresst.bestanden >= self.spot.bestanden

    def tabelle(self) -> str:
        zeilen = [
            f"{'Lauf':<26}{'Trades':>8}{'Rendite':>10}{'Rueckgang':>11}{'Gates':>8}",
            "-" * 63,
        ]
        for lauf in (
            self.mit_hebel, self.ohne_hebel, self.spot, self.spot_gestresst,
            *self.weitere,
        ):
            if lauf is None:
                continue
            zeilen.append(
                f"{lauf.name[:25]:<26}{lauf.trades:>8}{lauf.cagr:>9.2f} %"
                f"{lauf.rueckgang:>10.2f} %"
                f"{f'{lauf.bestanden}/{lauf.gesamt}':>8}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        teile = []

        if self.deckel_kostet_nichts:
            teile.append(
                f"**Der Kandidat nutzt seinen Hebel nicht.** Mit dem Deckel "
                f"auf 1,0 statt 3,0 liefert er dieselben Zahlen bis auf die "
                f"letzte Stelle - {self.ohne_hebel.trades} Trades, "
                f"{self.ohne_hebel.cagr:.2f} % im Jahr, "
                f"{self.ohne_hebel.rueckgang:.2f} % Rueckgang. Die "
                f"Groessensteuerung will nur an "
                f"{self.anteil_ueber_eins:.1%} der Balken ueber das eigene "
                f"Kapital hinaus."
            )
        else:
            teile.append(
                f"**Der Kandidat braucht seinen Hebel.** Gedeckelt auf 1,0 "
                f"stehen {self.ohne_hebel.cagr:.2f} % gegen "
                f"{self.mit_hebel.cagr:.2f} % im Jahr."
            )

        if self.braucht_shorts:
            teile.append(
                f"**Und er handelt die Gegenrichtung:** {self.short_regeln} "
                f"Leerverkaufsregeln. Spot kann das nicht."
            )

        if self.spot is not None and self.spot_moeglich:
            teile.append(
                f"**Damit ist Spot ein Szenario und keine Notloesung.** Ohne "
                f"Funding steht der Kandidat bei {self.spot.cagr:.2f} % im "
                f"Jahr und {self.spot.rueckgang:.2f} % Rueckgang - "
                f"{self.spot.bestanden} von {self.spot.gesamt} Gates statt "
                f"{self.mit_hebel.bestanden}. Offen bleiben: "
                + ", ".join(self.spot.gescheitert)
                + "."
            )
        elif self.spot is not None:
            teile.append(
                "Der Spot-Lauf steht hier zum Vergleich, ist aber **kein "
                "Szenario**: Der Kandidat braucht, was Spot nicht bietet."
            )

        stress = self.haelt_den_stress
        if stress is not None and self.spot_gestresst is not None:
            teile.append(
                f"Bybits Spot-Tarif ist hier **nicht gemessen**. Mit "
                f"verdoppelten Gebuehren als Ersatz haelt der Kandidat "
                f"{self.spot_gestresst.bestanden} von "
                f"{self.spot_gestresst.gesamt} Gates - "
                + (
                    "an den Gebuehren duerfte es also nicht scheitern. Wie "
                    "hoch sie sind, sagt das nicht."
                    if stress
                    else "die Gebuehren tragen den Unterschied also mit, und "
                    "der Tarif gehoert nachgeschlagen, bevor jemand darauf "
                    "baut."
                )
            )

        teile.append(
            "**Knapp daneben ist nicht bestanden.** Keine Schwelle wurde "
            "gesenkt, und der Deflated Sharpe bewegt sich in keinem dieser "
            "Laeufe. Gerechnet ist ausserdem weiterhin auf Bitstamp-Kerzen - "
            "fuer eine Spot-Strategie ist das immerhin dieselbe Art Markt, "
            "aber nicht dieselbe Boerse (Befund 102)."
        )
        return "\n\n".join(teile)


@dataclass(frozen=True, slots=True)
class Gebuehrenstufe:
    """Ein Spot-Lauf bei einem Vielfachen des Perpetual-Tarifs."""

    faktor: float
    dsr: float
    guete: float
    cagr: float
    bestanden: int
    gesamt: int
    gescheitert: tuple[str, ...] = ()
    gebuehren: float = 0.0


@dataclass(slots=True)
class Tragfaehigkeit:
    """Traegt der Spot-Vorteil auch den hoeheren Spot-Tarif?

    Und was der eigentliche Fund ist: was der Wegfall des Funding mit dem
    Deflated Sharpe macht - dem einen Gate, an dem alles haengt.
    """

    stufen: list[Gebuehrenstufe] = field(default_factory=list)
    schwelle: float = 0.95
    """Die Schwelle des Deflated-Sharpe-Gates."""
    dsr_perpetual: float = 0.0
    guete_perpetual: float = 0.0
    noetige_guete: float = 0.0
    """Welche Guete je Trade das Gate beim aktuellen Versuchsstand verlangt."""
    versuche: int = 0

    @property
    def geordnet(self) -> list[Gebuehrenstufe]:
        return sorted(self.stufen, key=lambda s: s.faktor)

    @property
    def genug(self) -> bool:
        return len(self.stufen) >= 2

    @property
    def grundstufe(self) -> Gebuehrenstufe | None:
        """Der Lauf mit dem unveraenderten Tarif."""
        return next((s for s in self.geordnet if s.faktor == 1.0), None)

    @property
    def gewinn_am_dsr(self) -> float:
        grund = self.grundstufe
        if grund is None or not self.dsr_perpetual:
            return 0.0
        return grund.dsr - self.dsr_perpetual

    @property
    def fehlt_am_dsr(self) -> float:
        grund = self.grundstufe
        return self.schwelle - grund.dsr if grund else 0.0

    @property
    def noetige_steigerung(self) -> float | None:
        """Um wie viel die Guete je Trade noch steigen muesste - als Anteil."""
        grund = self.grundstufe
        if grund is None or not self.noetige_guete or not grund.guete:
            return None
        return self.noetige_guete / grund.guete - 1.0

    @property
    def bruchstelle(self) -> tuple[Gebuehrenstufe, Gebuehrenstufe] | None:
        """Zwischen welchen Faktoren die Gate-Zahl faellt."""
        for links, rechts in pairwise(self.geordnet):
            if rechts.bestanden < links.bestanden:
                return links, rechts
        return None

    @property
    def haelt_bis(self) -> float | None:
        """Der hoechste Faktor, bei dem die Bilanz noch steht."""
        bruch = self.bruchstelle
        if bruch is not None:
            return bruch[0].faktor
        return self.geordnet[-1].faktor if self.stufen else None

    def tabelle(self) -> str:
        if not self.stufen:
            return "Keine Gebuehrenstufen gemessen."
        zeilen = [
            f"{'Gebuehren':>10}{'DSR':>9}{'Guete':>9}{'Rendite':>10}{'Gates':>8}"
            "  dann offen",
            "-" * 74,
        ]
        for s in self.geordnet:
            zeilen.append(
                f"{'x' + format(s.faktor, 'g'):>10}{s.dsr:>9.4f}{s.guete:>9.4f}"
                f"{s.cagr:>9.2f} %{f'{s.bestanden}/{s.gesamt}':>8}  "
                + ", ".join(s.gescheitert)
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.genug:
            return (
                "Weniger als zwei Gebuehrenstufen - daraus laesst sich ueber "
                "die Tragfaehigkeit nichts sagen."
            )

        grund = self.grundstufe
        teile = []
        if grund is not None and self.dsr_perpetual:
            teile.append(
                f"**Der Deflated Sharpe steigt um {self.gewinn_am_dsr:+.4f}** - "
                f"von {self.dsr_perpetual:.4f} auf {grund.dsr:.4f}. Es fehlen "
                f"noch {self.fehlt_am_dsr:.4f} auf {self.schwelle:.2f}."
            )
            steigerung = self.noetige_steigerung
            if steigerung is not None:
                teile.append(
                    f"In Gueteeinheiten: noetig sind {self.noetige_guete:.4f} "
                    f"statt der erreichten {grund.guete:.4f}, also "
                    f"**+{steigerung:.1%}** bei {self.versuche} Versuchen. "
                    f"Und das ohne einen einzigen neuen Versuch - es ist eine "
                    f"Kostenaenderung, keine Suche."
                )

        bruch = self.bruchstelle
        if bruch is not None:
            links, rechts = bruch
            neu = set(rechts.gescheitert) - set(links.gescheitert)
            teile.append(
                f"**Der Vorteil traegt bis zum {links.faktor:g}-fachen des "
                f"Perpetual-Tarifs.** Beim {rechts.faktor:g}-fachen faellt die "
                f"Bilanz von {links.bestanden} auf {rechts.bestanden} von "
                f"{rechts.gesamt}"
                + (f" - es kippt: {', '.join(sorted(neu))}." if neu else ".")
            )
        else:
            teile.append(
                f"Ueber alle gemessenen Stufen bis zum "
                f"{self.geordnet[-1].faktor:g}-fachen bleibt die Bilanz stehen."
            )

        teile.append(
            "**Welcher Faktor gilt, ist hier nicht gemessen.** Er haengt am "
            "Spot-Tarif und am Fuellmix: Einstiege und Take-Profits laufen als "
            "PostOnly-Limit, Stops als Taker. Ohne beides ist es eine Spanne "
            "und keine Zahl - und die Spanne schliesst die Bruchstelle ein."
        )
        return "\n\n".join(teile)


__all__ = ["Gebuehrenstufe", "Instrumentenwahl", "Lauf", "Tragfaehigkeit"]
