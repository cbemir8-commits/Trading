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

Kostet keinen Versuch: Derselbe Kandidat, dieselben Daten, unter anderen
Handelsbedingungen. Es wird nichts ausgewaehlt.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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


__all__ = ["Instrumentenwahl", "Lauf"]
