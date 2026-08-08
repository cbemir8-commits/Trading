"""Der Katalog, noch einmal gemessen - nachdem sich das Messgeraet geaendert hat.

Warum das noetig ist
--------------------
Der Leaderboard traegt Stand vom 05.08.2026 und zaehlt noch **zehn** Gates.
Seither sind zwei Fehler im Messinstrument gefunden worden, und beide haben
jede Zahl verschoben:

* **Der Nachlauf.** Der Backtest stellte offene Positionen am Fensterende
  zwangsweise glatt. Beim Spitzenkandidaten traf das 25 von 154 Trades - und
  diese 25 trugen den gesamten Vorteil. Betroffen ist **jeder** Kandidat, und
  am staerksten die langsamen: Wer zwanzig Tage haelt, verliert in einem
  Fenster von neunzig Tagen einen grossen Teil seiner Trades an den Kalender.

* **Die Aufwaermphase.** Die Konfluenz wurde nicht mitgezaehlt. Nachgemessen
  betrifft das im Katalog fast nur den Spitzenkandidaten (150 statt 201
  Kerzen); vierzehn weitere unterscheiden sich um genau eine Kerze. Diese
  Vermutung - "viele Kandidaten falsch bewertet" - ist damit widerlegt, und
  zwar gemessen statt geraten.

Ein Urteil ueber eine Strategie ist nur so gut wie das Geraet, mit dem es
zustande kam. Aendert sich das Geraet, ist das Urteil neu zu faellen - sonst
steht im Leaderboard eine Rangfolge, die es so nie gab.

Zum Versuchszaehler
-------------------
Eine Nachpruefung kostet **keinen Versuch**. Es sind dieselben Regeln auf
denselben Daten; gesehen wurden sie alle schon, und sie stehen laengst im
Zaehler. Der Deflated Sharpe korrigiert dafuer, dass man bei genug **Einfaellen**
irgendwann etwas findet - nicht dafuer, dass man einen alten Einfall
richtiger misst.

Was daraus **nicht** folgt: Sollte hier ein frueher verworfener Kandidat
ploetzlich weit kommen, ist er damit nicht zugelassen. Er ist einer aus 53,
und genau dafuer steht die Huerde da, wo sie steht.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Ergebnis:
    """Was ein Kandidat mit dem korrigierten Instrument erreicht."""

    genome_id: str
    name: str
    generation: int
    bestanden: int
    gesamt: int
    offen: tuple[str, ...] = ()
    trades: int = 0
    cagr_pct: float = 0.0
    rueckgang_pct: float = 0.0
    dsr: float = 0.0

    @property
    def zugelassen(self) -> bool:
        return self.gesamt > 0 and self.bestanden == self.gesamt


@dataclass(frozen=True, slots=True)
class Veraenderung:
    """Ein Kandidat, dessen Urteil sich geaendert hat."""

    ergebnis: Ergebnis
    vorher: int
    nachher: int

    @property
    def richtung(self) -> str:
        return "besser" if self.nachher > self.vorher else "schlechter"

    def __str__(self) -> str:
        return (
            f"{self.ergebnis.name[:44]:46} {self.vorher} -> {self.nachher} "
            f"({self.richtung})"
        )


@dataclass(slots=True)
class Nachpruefung:
    """Alle Ergebnisse eines Nachpruefungslaufs."""

    ergebnisse: list[Ergebnis] = field(default_factory=list)

    @property
    def rangfolge(self) -> list[Ergebnis]:
        """Bestandene Gates zuerst, bei Gleichstand der Deflated Sharpe.

        Nicht nach Rendite: Die hat in diesem Projekt schon zweimal einen
        Kandidaten nach oben getragen, der an einer Risikogrenze scheiterte.
        """
        return sorted(
            self.ergebnisse, key=lambda e: (e.bestanden, e.dsr), reverse=True
        )

    @property
    def zugelassen(self) -> list[Ergebnis]:
        return [e for e in self.ergebnisse if e.zugelassen]

    @property
    def bester(self) -> Ergebnis | None:
        return self.rangfolge[0] if self.ergebnisse else None

    def veraenderungen(self, vorher: dict[str, int]) -> list[Veraenderung]:
        """Wer steht jetzt anders da als im Leaderboard?

        ``vorher`` bildet ``genome_id`` auf die frueher bestandenen Gates ab.
        Unbekannte Kandidaten bleiben aussen vor - ein Kandidat, der nie
        gemessen wurde, hat sich nicht veraendert.

        **Die Zahl der Gates war frueher eine andere** (zehn statt elf). Ein
        Vergleich der rohen Zahlen ist deshalb nur ein Hinweis, kein Beweis;
        wer aus 8/10 gegen 8/11 einen Fortschritt liest, vergleicht zwei
        verschiedene Messlatten. Genau deshalb steht hier die Rohzahl und
        keine Quote - eine Quote sieht nach Vergleichbarkeit aus, wo keine ist.
        """
        geaendert = []
        for e in self.rangfolge:
            if e.genome_id not in vorher:
                continue
            alt = vorher[e.genome_id]
            if alt != e.bestanden:
                geaendert.append(
                    Veraenderung(ergebnis=e, vorher=alt, nachher=e.bestanden)
                )
        return geaendert

    def tabelle(self, hoechstens: int = 15) -> str:
        if not self.ergebnisse:
            return "Nichts gemessen."
        zeilen = [
            f"{'Kandidat':44} {'Gates':>7} {'Trades':>7} {'p.a.':>8} "
            f"{'DD':>7} {'DSR':>7}",
            "-" * 84,
        ]
        for e in self.rangfolge[:hoechstens]:
            zeilen.append(
                f"{e.name[:44]:44} {e.bestanden:>3}/{e.gesamt:<3} "
                f"{e.trades:>7} {e.cagr_pct:>7.2f}% {e.rueckgang_pct:>6.2f}% "
                f"{e.dsr:>7.3f}"
            )
        if len(self.ergebnisse) > hoechstens:
            zeilen.append(f"... und {len(self.ergebnisse) - hoechstens} weitere")
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.ergebnisse:
            return "Nichts gemessen - kein Urteil."
        if self.zugelassen:
            namen = ", ".join(e.name for e in self.zugelassen)
            return (
                f"{len(self.zugelassen)} Kandidat(en) bestehen alle Gates: {namen}. "
                "Zugelassen ist damit noch keiner - das entscheidet die "
                "Zulassungsstrecke, nicht diese Nachmessung."
            )
        bester = self.bester
        assert bester is not None
        fehlend = ", ".join(bester.offen) if bester.offen else "-"
        text = (
            f"Kein Kandidat besteht alle Gates. Am weitesten kommt "
            f"'{bester.name}' mit {bester.bestanden} von {bester.gesamt}; "
            f"offen bleiben: {fehlend}."
        )

        # **Die Zahl bestandener Gates ist ein schlechtes Mass fuer Naehe.**
        #
        # Gemessen am Katalog: Der Erste steht bei 8 von 11 mit einem Deflated
        # Sharpe von 0,486, der Vierte bei 7 von 11 mit 0,864. Das haerteste
        # Gate verlangt 0,95 - und es ist dasjenige, das sich mit keinem
        # Regler bewegen laesst. Wer nach Gate-Zahl liest, haelt den
        # Aussichtsreicheren fuer den Schwaecheren.
        #
        # Dagegen hilft keine zusammengesetzte Kennzahl - die waere nur ein
        # neuer Ersatzmassstab, an dem man sich wieder vorbeioptimiert.
        # Genannt wird stattdessen beides.
        nach_dsr = max(self.ergebnisse, key=lambda e: e.dsr)
        if nach_dsr.genome_id != bester.genome_id:
            text += (
                f" Den hoechsten Deflated Sharpe hat allerdings ein anderer: "
                f"'{nach_dsr.name}' mit {nach_dsr.dsr:.3f} gegen "
                f"{bester.dsr:.3f} - und das ist das Gate, das sich mit keinem "
                f"Regler bewegen laesst. Die Zahl bestandener Gates sagt "
                f"wenig darueber, wer naeher dran ist."
            )
        return text
