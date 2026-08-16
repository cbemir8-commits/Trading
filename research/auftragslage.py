"""Was dem Analysten nie gesagt wurde.

Der Auftrag, den die Research-KI bisher bekam
---------------------------------------------
``analyst.build_prompt`` nennt die erlaubten Indikatoren, das Journal der
gescheiterten Versuche und fuenf Zulassungsschwellen:

    - mindestens 100 Out-of-Sample-Trades
    - Sharpe mindestens ...
    - Drawdown hoechstens ...
    - mindestens ... profitable Fenster
    - ueberlebt ...-fache Gebuehren

**Der Deflated Sharpe kommt darin nicht vor.** Das ist genau das Gate, an dem
seit Befund 61 alles haengt, und das einzige, das von den elf noch wirklich
ungeloest ist. Der Analyst hat nie erfahren, dass es existiert - geschweige
denn, dass die Huerde mit jedem seiner Vorschlaege steigt.

Was er dadurch falsch optimiert hat
-----------------------------------
Er zielt auf **100 Trades**, weil das die einzige Trade-Schwelle im Auftrag
ist. Die gemessene Anforderung aus Befund 74/75 lautet aber: **mindestens 120
Trades bei einem Sharpe je Trade ueber 0,23** - und zwar moeglichst
unabhaengig vom Trendfolge-Signal des Bestands.

Ein Vorschlag mit 105 Trades und Sharpe je Trade 0,15 erfuellt den alten
Auftrag und ist fuer das, was fehlt, wertlos. Genau solche Vorschlaege sind
gekommen: Von fuenf belegten Analyst-Kandidaten haben vier zwischen 68 und 123
Trades und keiner einen Sharpe je Trade ueber 0,25.

Das ist derselbe Fehler, der mir in Befund 73 unterlaufen ist - Auswahl nach
dem falschen Merkmal -, nur eine Ebene hoeher: Nicht die Auswahl war falsch,
sondern der Auftrag.

Was hier dazukommt
------------------
Kein gelockertes Kriterium, sondern ein **schaerferes**: Der Analyst bekommt
die Zahl, die tatsaechlich zaehlt (Guete = Sharpe je Trade mal Wurzel aus der
effektiven Trade-Zahl), den heutigen Versuchsstand samt seiner Wirkung auf die
Huerde, und die Kopplung, die erklaert, warum das schwer ist.

Und die Warnung, die aus Befund 71 folgt: Jeder Vorschlag hebt die Huerde fuer
alle folgenden. Das stand schon im Systemtext, aber ohne Zahl.

Kostet keinen Versuch: Gebaut wird ein Auftragstext, nicht ein Kandidat.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Die Fensterkorrelation, ab der ein Vorschlag als "dasselbe Signal" gilt.
#: Beim Perioden-Ensemble aus Befund 27 waren es 0,884 - drei Beine, eine
#: Information. Die gemessenen Verbunde lagen bei 0,53 bis 0,81.
AEHNLICH = 0.8


@dataclass(frozen=True, slots=True)
class Auftragslage:
    """Der gemessene Stand, in der Form, in der ein Vorschlag ihn braucht."""

    versuche: int
    bestand_trades: int
    bestand_sharpe: float
    noetige_guete: float
    partner_trades: int
    """Ab wie vielen Trades ein Partner mit der Qualitaet des Bestands
    genuegt - die Wende aus der Partnerkarte."""

    partner_sharpe: float
    """Welchen Sharpe je Trade ein Partner bei dieser Trade-Zahl braucht."""

    kopplung: float | None = None
    """Korrelation zwischen Trade-Zahl und Qualitaet ueber den Katalog."""

    kosten_je_versuch: float = 0.0
    """Um wie viel die Huerde durch **einen** weiteren Versuch steigt."""
    bedarf_bei_doppelt: float = 0.0
    """Die Anforderung bei doppelter Trade-Zahl.

    Steht daneben, weil die Zahl an der Wende irrefuehrt: Dort ist der noetige
    Sharpe je Trade per Definition **gleich** dem des Bestands, und ein Satz
    wie "weniger als der Bestand hat" ist dann schlicht falsch. Der Hebel wird
    erst am zweiten Punkt sichtbar."""

    @property
    def bestand_guete(self) -> float:
        return self.bestand_sharpe * self.bestand_trades**0.5

    @property
    def fehlt(self) -> float:
        return self.noetige_guete - self.bestand_guete

    def als_auftrag(self) -> str:
        """Der Abschnitt, der in den Prompt gehoert.

        Bewusst mit Zahlen und nicht mit Adjektiven: "moeglichst viele Trades"
        laesst sich nicht pruefen, "mindestens 120" schon.
        """
        zeilen = [
            "## Was tatsaechlich fehlt\n",
            "Von elf Zulassungspruefungen ist genau eine noch ungeloest: der",
            "**Deflated Sharpe**. Er korrigiert dafuer, dass man bei genug",
            "Versuchen irgendwann zufaellig etwas Gutaussehendes findet.",
            "",
            "Die Groesse, an der er haengt, ist die **Guete**:",
            "",
            "    Guete = (Sharpe je Trade) * Wurzel(unabhaengige Trades)",
            "",
            f"- Der beste Kandidat steht bei {self.bestand_guete:.3f} "
            f"({self.bestand_trades} Trades zu je {self.bestand_sharpe:.4f}).",
            f"- Noetig sind {self.noetige_guete:.3f} bei "
            f"{self.versuche} bisherigen Versuchen.",
            f"- Es fehlen {self.fehlt:.3f}.",
            "",
            "**Beide Faktoren zaehlen, und der zweite wird unterschaetzt.** Ein",
            "Vorschlag mit doppelt so vielen Trades braucht nur das",
            "0,71-fache an Qualitaet je Trade fuer dieselbe Guete.",
            "",
            "## Wonach konkret gesucht wird\n",
            "Der beste Kandidat kommt allein nicht ueber die Huerde. Was ihm",
            "fehlt, ist ein **zweites, unabhaengiges Signal**, das parallel",
            "gehandelt wird. Ein Vorschlag ist dafuer brauchbar, wenn er alle",
            "drei Punkte erfuellt:",
            "",
            f"1. **Mindestens {self.partner_trades} Trades** im selben Zeitraum.",
            "   Darunter genuegt selbst ein sehr hoher Sharpe je Trade nicht.",
            f"2. **Sharpe je Trade ueber {self.partner_sharpe:.2f}** bei genau",
            "   dieser Trade-Zahl. Die Anforderung faellt schnell: bei",
            f"   {self.partner_trades * 2} Trades genuegen {self.bedarf_bei_doppelt:.2f}.",
            "   Mehr Trades sind der wirksamere Hebel als mehr Qualitaet.",
            "3. **Ein anderes Marktverhalten als Trendfolge.** Der Bestand ist",
            "   long ueber dem 50-Tage-Schnitt. Ein Vorschlag, dessen Gewinne",
            "   in denselben Phasen anfallen, bringt Trades ohne Information",
            f"   (Fensterkorrelation ueber {AEHNLICH:.1f} zaehlt als dasselbe",
            "   Signal).",
            "",
        ]

        if self.kopplung is not None:
            zeilen += [
                "## Warum das schwer ist\n",
                "Ueber alle bisher gemessenen Regeln betraegt die Korrelation",
                f"zwischen Trade-Zahl und Qualitaet je Trade **{self.kopplung:+.3f}**:",
                "Wer oefter handelt, handelt schlechter. Jede Regel im",
                "vorhandenen Vorrat erfuellt entweder Punkt 1 oder Punkt 2,",
                "keine beide.",
                "",
                "Es geht also nicht darum, eine bekannte Regel zu verfeinern.",
                "Gebraucht wird ein Ausloeser, der **oft** zutrifft und dabei",
                "trotzdem Vorteil traegt - etwa weil er auf eine andere",
                "Ursache zielt als ein Trend.",
                "",
            ]

        if self.kosten_je_versuch > 0:
            zeilen += [
                "## Was ein Vorschlag kostet\n",
                "Jeder gepruefte Kandidat hebt die noetige Qualitaet je Trade",
                f"um {self.kosten_je_versuch:.5f} - fuer alle folgenden, dauerhaft.",
                f"Bei {self.versuche} Versuchen ist das der Grund, warum die",
                "Huerde heute dort liegt, wo sie liegt. Ein Vorschlag, der die",
                "drei Punkte oben nicht erfuellen kann, macht die Lage",
                "schlechter statt besser.",
                "",
            ]
        return "\n".join(zeilen)


def aus_messungen(
    *,
    versuche: int,
    bestand_trades: int,
    bestand_sharpe: float,
    kopplung: float | None = None,
) -> Auftragslage:
    """Die Lage aus den vorhandenen Rechnungen zusammensetzen.

    Alle Zahlen kommen aus Modulen, die sie ohnehin liefern - nichts wird
    hier zweitgerechnet. Wer die Schwelle in ``gates.py`` aendert, aendert
    diesen Auftragstext mit.
    """
    from research.partnerkarte import Partnerkarte
    from research.suchbudget import Budget
    from research.verbund import noetige_guete

    ziel = noetige_guete(bestand_trades, versuche) or 0.0
    karte = Partnerkarte(n1=bestand_trades, sr1=bestand_sharpe, ziel=ziel)
    wende = karte.wende or bestand_trades
    bedarf = karte.bedarf(wende, 0.72) or bestand_sharpe
    preis = Budget(versuche=versuche).kosten_je_versuch(bestand_trades) or 0.0
    return Auftragslage(
        versuche=versuche,
        bestand_trades=bestand_trades,
        bestand_sharpe=bestand_sharpe,
        noetige_guete=ziel,
        partner_trades=wende,
        partner_sharpe=bedarf,
        bedarf_bei_doppelt=karte.bedarf(wende * 2, 0.72) or 0.0,
        kopplung=kopplung,
        kosten_je_versuch=preis,
    )
