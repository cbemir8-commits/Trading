"""Die teuerste Annahme des Systems steht auf einem Vorgabewert.

Was hier gefunden wurde
-----------------------
Der Backtest belastet Perpetual-Positionen mit Funding - alle acht Stunden,
auf den Nominalwert. Die Rate dafuer kommt aus ``FundingSchedule``, und ohne
historische Daten setzt sie ``default_rate = 0,0001`` ein: den Bybit-Basiswert,
rund 11 % im Jahr fuer eine dauerhaft gehaltene Long-Position.

**``data_store/funding/`` ist leer.** Es gibt keine historischen Raten. Jede
Zahl dieses Projekts rechnet also mit dem Vorgabewert.

Wie viel daran haengt
---------------------
Der Bestand ueber eine Leiter von Saetzen, sonst alles gleich:

    Satz p.a.   Funding    Anteil    Rendite   Rueckgang   Gates
     0,0 %       0,00 EUR    0,0 %    14,83 %      9,87 %    9/11
     5,5 %      31,90 EUR    4,1 %    14,15 %     10,25 %    9/11
    11,0 %      63,79 EUR    8,2 %    13,47 %     10,64 %    7/11   <- Vorgabe
    21,9 %     127,57 EUR   16,4 %    12,13 %     11,41 %    7/11
    32,9 %     191,35 EUR   24,6 %    10,80 %     12,17 %    6/11
    54,8 %     318,46 EUR   40,9 %     8,22 %     13,68 %    3/11

Zwischen 5,5 % und 11 % kippen **zwei Gates** (Schlechtestes Jahr,
Parameter-Plateau), zwischen 21,9 % und 32,9 % ein drittes (Drawdown).

Die Zahl, die das Verhaeltnis zeigt
-----------------------------------
    Handelsgebuehren     7,17 EUR
    Funding             63,79 EUR

**Funding ist das 8,9-fache der Handelsgebuehren.** Das Projekt hat ein
Kosten-Stress-Gate, ein Kostenanteil-Modul und mehrere Befunde ueber
Gebuehrenmodelle - und der groesste Kostenblock steht die ganze Zeit auf einem
Vorgabewert, den niemand geprueft hat.

In welche Richtung der Fehler zeigt
-----------------------------------
``FundingSchedule`` sagt es im eigenen Docstring:

    *"Eine Strategie, die Funding ignoriert, ueberschaetzt ihre Rendite
    systematisch, und zwar besonders in Bullenmaerkten, wo die Rate meist
    positiv ist und Longs zahlen."*

Der Bestand ist eine **Long-Trendfolge**. Er ist im Markt, wenn der Trend
steigt - also genau dann, wenn Longs am meisten zahlen. Der Vorgabewert ist
der **Basiswert**, nicht der Durchschnitt; die tatsaechliche Rate liegt in
Aufwaertsphasen regelmaessig darueber.

**Das ist hier nicht gemessen, sondern die Aussage des Engine-Docstrings.**
Nachpruefen laesst es sich nur mit echten Bybit-Raten, und die sind aus diesem
Container nicht erreichbar. Deshalb steht hier keine Korrektur, sondern eine
Groessenordnung: Liegt die wahre Rate ueber der Vorgabe, steht der Bestand
schlechter da als 7 von 11 - nicht besser.

Warum die Nullzeile keine Hoffnung ist
--------------------------------------
Bei 0 % stuende der Bestand auf 9 von 11. Diese Zeile ist eine
Empfindlichkeit, **kein Szenario**. Funding entfaellt nur im Spot-Handel, und
dort entfaellt auch der Hebel: Die Position waere durch das Kapital gedeckelt,
und die gemessenen Groessen kaemen gar nicht zustande. Die Zeile sagt, wie
viel die Annahme wiegt, nicht, was erreichbar waere.

Kostet keinen Versuch: Derselbe Kandidat auf jeder Sprosse, veraendert wird
eine Kostenannahme, ausgewaehlt wird nichts. Insbesondere wird der Satz
**nicht** auf den Wert gesetzt, bei dem mehr Gates halten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise

#: Der Vorgabewert aus ``backtest.costs.FundingSchedule`` - je Achtstunden-
#: periode. Er steht hier, damit die Leiter ihn markieren kann, ohne ihn zu
#: erraten.
BASISSATZ = 0.0001

#: Funding faellt alle acht Stunden an: dreimal am Tag.
PERIODEN_JE_JAHR = 3 * 365


@dataclass(frozen=True, slots=True)
class Stufe:
    """Ein Lauf bei einem angenommenen Funding-Satz."""

    satz: float
    """Je Achtstundenperiode, als Anteil - 0,0001 sind 0,01 %."""
    cagr: float
    rueckgang: float
    bestanden: int
    gesamt: int
    funding: float = 0.0
    gebuehren: float = 0.0
    brutto: float = 0.0
    gescheitert: tuple[str, ...] = ()

    @property
    def jahr_pct(self) -> float:
        return self.satz * PERIODEN_JE_JAHR * 100.0

    @property
    def anteil_am_brutto(self) -> float:
        return self.funding / self.brutto if self.brutto else 0.0

    @property
    def vielfaches_der_gebuehren(self) -> float:
        """Wie oft das Funding in die Handelsgebuehren passt.

        Die Zahl, die die Groessenordnung sofort klarmacht: Ist sie gross,
        misst jede Sorgfalt am Gebuehrenmodell den kleineren Posten.
        """
        return self.funding / self.gebuehren if self.gebuehren else 0.0


@dataclass(slots=True)
class Finanzierung:
    """Wie stark das Urteil an einer nie gemessenen Kostenannahme haengt."""

    stufen: list[Stufe] = field(default_factory=list)
    angenommen: float = BASISSATZ
    """Der Satz, mit dem alle uebrigen Messungen des Projekts gerechnet sind."""
    historie_vorhanden: bool = False
    """Gibt es echte Raten? Ohne sie ist die ganze Leiter eine Annahme."""

    @property
    def geordnet(self) -> list[Stufe]:
        return sorted(self.stufen, key=lambda s: s.satz)

    @property
    def genug(self) -> bool:
        return len(self.stufen) >= 3

    @property
    def betriebspunkt(self) -> Stufe | None:
        """Die Sprosse, auf der alle uebrigen Messungen stehen."""
        return next((s for s in self.stufen if s.satz == self.angenommen), None)

    @property
    def kipppunkte(self) -> list[tuple[Stufe, Stufe]]:
        """Zwischen welchen Sprossen sich die Zahl bestandener Gates aendert."""
        return [
            (links, rechts)
            for links, rechts in pairwise(self.geordnet)
            if links.bestanden != rechts.bestanden
        ]

    @property
    def spanne_gates(self) -> tuple[int, int]:
        if not self.stufen:
            return (0, 0)
        werte = [s.bestanden for s in self.stufen]
        return (min(werte), max(werte))

    @property
    def haengt_daran(self) -> bool:
        tief, hoch = self.spanne_gates
        return hoch > tief

    @property
    def groesster_kostenblock(self) -> str:
        """Funding oder Gebuehren - welcher Posten am Betriebspunkt fuehrt."""
        punkt = self.betriebspunkt
        if punkt is None or not punkt.gebuehren:
            return ""
        return "Funding" if punkt.funding > punkt.gebuehren else "Gebuehren"

    def tabelle(self) -> str:
        if not self.stufen:
            return "Keine Saetze gemessen."
        zeilen = [
            f"{'Satz p.a.':>10}{'Funding':>11}{'Anteil':>9}{'Rendite':>10}"
            f"{'Rueckgang':>11}{'Gates':>8}",
            "-" * 60,
        ]
        for s in self.geordnet:
            marke = "  <- Vorgabe" if s.satz == self.angenommen else ""
            zeilen.append(
                f"{s.jahr_pct:>9.1f} %{s.funding:>9.2f} E"
                f"{s.anteil_am_brutto:>9.1%}{s.cagr:>9.2f} %"
                f"{s.rueckgang:>10.2f} %{f'{s.bestanden}/{s.gesamt}':>8}{marke}"
            )
        punkt = self.betriebspunkt
        if punkt is not None and punkt.gebuehren:
            zeilen.append("-" * 60)
            zeilen.append(
                f"Am Betriebspunkt: Gebuehren {punkt.gebuehren:.2f} EUR, "
                f"Funding {punkt.funding:.2f} EUR "
                f"({punkt.vielfaches_der_gebuehren:.1f}-faches)"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.genug:
            return (
                "Weniger als drei Saetze - daraus laesst sich ueber die "
                "Empfindlichkeit nichts sagen."
            )

        teile = []
        punkt = self.betriebspunkt
        if not self.historie_vorhanden:
            teile.append(
                f"**Der Funding-Satz ist nie gemessen worden.** Es gibt keine "
                f"historischen Raten; der Backtest setzt den Vorgabewert von "
                f"{self.angenommen * 100:.3f} % je Achtstundenperiode ein, also "
                f"rund {self.angenommen * PERIODEN_JE_JAHR * 100:.0f} % im Jahr "
                f"fuer eine dauerhaft gehaltene Long-Position."
            )

        if punkt is not None and punkt.vielfaches_der_gebuehren > 1:
            teile.append(
                f"**Und es ist der groesste Kostenblock.** Am Betriebspunkt "
                f"stehen {punkt.gebuehren:.2f} EUR Handelsgebuehren gegen "
                f"{punkt.funding:.2f} EUR Funding - das "
                f"{punkt.vielfaches_der_gebuehren:.1f}-fache, und "
                f"{punkt.anteil_am_brutto:.1%} des Bruttogewinns."
            )

        if self.haengt_daran:
            tief, hoch = self.spanne_gates
            uebergaenge = ", ".join(
                f"zwischen {a.jahr_pct:.1f} % und {b.jahr_pct:.1f} % "
                f"({a.bestanden} -> {b.bestanden})"
                for a, b in self.kipppunkte[:3]
            )
            teile.append(
                f"**Das Urteil haengt daran.** Ueber die gemessene Leiter "
                f"reicht die Bilanz von {hoch} bis {tief} von "
                f"{self.geordnet[0].gesamt} Gates: {uebergaenge}."
            )
        else:
            teile.append(
                "Die Bilanz aendert sich ueber die ganze Leiter nicht - der "
                "Satz traegt hier kein Urteil."
            )

        teile.append(
            "**In welche Richtung der Fehler zeigt, ist hier nicht gemessen.** "
            "Der Engine-Docstring haelt fest, dass die Rate in Aufwaertsphasen "
            "meist positiv ist und Longs zahlen; der Bestand ist eine "
            "Long-Trendfolge und im Markt, wenn der Trend steigt. Der "
            "Vorgabewert ist der Basiswert, nicht der Durchschnitt. Liegt die "
            "wahre Rate darueber, steht der Kandidat **schlechter** da als "
            "gemeldet - nicht besser. Nachpruefen laesst sich das nur mit "
            "echten Raten."
        )

        null = next((s for s in self.geordnet if s.satz == 0), None)
        if null is not None:
            teile.append(
                f"**Die Nullzeile ({null.bestanden} von {null.gesamt}) ist "
                f"keine Hoffnung.** Sie ist eine Empfindlichkeit, kein "
                f"Szenario: Funding entfaellt nur im Spot-Handel, und dort "
                f"entfaellt auch der Hebel - die gemessenen Positionsgroessen "
                f"kaemen gar nicht zustande. Der Satz wird auch nicht auf den "
                f"Wert gestellt, bei dem mehr Gates halten."
            )
        return "\n\n".join(teile)


__all__ = ["BASISSATZ", "PERIODEN_JE_JAHR", "Finanzierung", "Stufe"]
