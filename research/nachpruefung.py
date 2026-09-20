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
    vorauswahl: bool = False
    """Wurde nur eine **Vorauswahl** gerechnet, ohne die teuren Gates?

    Dann sagt "alle bestanden" nichts: Es sind neun von elf, und die beiden
    fehlenden - Parameter-Plateau und Kosten-Stress - sind ausgerechnet die,
    die zusaetzliche Backtests brauchen und deshalb ausgelassen wurden.
    """

    uebersprungen: tuple[str, ...] = ()
    """Gates, die **nicht geurteilt haben** - Befund 322.

    Dieselbe stille Aufwertung wie bei ``vorauswahl``, nur aus anderer
    Ursache: ``GateResult.passed`` heisst "nicht durchgefallen", und mehrere
    Gates setzen bei zu kleiner Stichprobe aus. Wer **gar nicht handelt**,
    bekommt sie alle gutgeschrieben.

    Gemessen im Katalogdurchlauf (``reports/nachpruefung``): 33 von 54
    Regeln haben **null** Trades, und jede steht dort mit **5 von 11** -
    Deflated Sharpe, Drawdown, Monte-Carlo, Regime-Aufteilung und
    Schlechtestes Jahr sind auf einer leeren Handelsliste nicht zu
    verfehlen.

    Damit rangierten **sechs** Regeln, die wirklich gehandelt haben, unter
    jeder, die es nie versucht hat - darunter 'Trendbeteiligung mit Puffer'
    mit 302 Trades und 4 von 11 -, und drei weitere lagen gleichauf.
    """

    @property
    def geurteilt(self) -> int:
        """Gates, die wirklich ein Urteil gefaellt haben."""
        return max(self.gesamt - len(self.uebersprungen), 0)

    @property
    def bestanden_echt(self) -> int:
        """Bestandene Gates ohne die uebersprungenen.

        Die Zahl, die sich zwischen zwei Regeln vergleichen laesst:
        ``bestanden`` zaehlt Gates mit, die nie geurteilt haben, und wie
        viele das sind, haengt an der Trade-Zahl.
        """
        return max(self.bestanden - len(self.uebersprungen), 0)

    @property
    def zugelassen(self) -> bool:
        """**Eine Vorauswahl kann nichts zulassen.**

        Ohne diese Klausel haette ein Kandidat, der neun von neun besteht, als
        "alle Gates bestanden" im Bericht gestanden - waehrend zwei Gates gar
        nicht gelaufen sind. Das ist genau die Sorte stiller Aufwertung, gegen
        die die ganze Zulassungsstrecke gebaut ist.

        **Und ein ausgesetztes Gate ebenso wenig** (Befund 322): Es ist
        derselbe Satz, nur ist die Ursache nicht die Vorauswahl, sondern eine
        Stichprobe, die fuer das Gate nicht reicht.
        """
        return (
            not self.vorauswahl
            and not self.uebersprungen
            and self.gesamt > 0
            and self.bestanden == self.gesamt
        )


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

        **Gezaehlt werden die Gates, die geurteilt haben** (Befund 322).
        Vorher stand hier ``e.bestanden``, und das schliesst ausgesetzte
        Gates ein: Eine Regel mit null Trades bekam fuenf davon
        gutgeschrieben und rangierte damit ueber sechs Regeln, die wirklich
        gehandelt haben. Verglichen wurden zwei verschiedene Nenner.
        """
        return sorted(
            self.ergebnisse,
            key=lambda e: (e.bestanden_echt, e.dsr),
            reverse=True,
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
            # **Geurteilt, nicht gutgeschrieben** (Befund 322). Stuende hier
            # 'bestanden/gesamt', laese sich eine Regel ohne einen einzigen
            # Trade als '5/11' - die fuenf sind die, die auf einer leeren
            # Handelsliste aussetzen.
            zeilen.append(
                f"{e.name[:44]:44} "
                f"{e.bestanden_echt:>3}/{e.geurteilt:<3} "
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
            f"'{bester.name}' mit {bester.bestanden_echt} von "
            f"{bester.geurteilt}; offen bleiben: {fehlend}."
        )
        # **Wie viele gar nicht geurteilt wurden** (Befund 322). Ohne diese
        # Zeile liest sich eine Rangliste, in der zwei Drittel der Regeln nie
        # gehandelt haben, wie ein Vergleich von Regeln.
        stumm = [e for e in self.ergebnisse if e.uebersprungen]
        if stumm:
            ohne_trade = sum(1 for e in stumm if e.trades == 0)
            text += (
                f" **Bei {len(stumm)} von {len(self.ergebnisse)} Kandidaten "
                f"hat nicht jedes Gate geurteilt**"
                + (
                    f", {ohne_trade} davon ohne einen einzigen Trade"
                    if ohne_trade
                    else ""
                )
                + " - gezaehlt sind hier nur die Gates, die ein Urteil "
                "gefaellt haben."
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
