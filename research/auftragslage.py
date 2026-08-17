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

    bestes_ziel: int = 0
    """Die Trade-Zahl mit der besten Trefferaussicht - das **Optimum**.

    ``partner_trades`` ist die Wende und damit eine **Untergrenze**: ab dort
    genuegt ein Partner mit der Qualitaet des Bestands. Der Auftrag hat sie
    bis Befund 82 als Ziel genannt, und mein eigener Vorschlagszyklus in
    Befund 77 hat danach gezielt - mit Vorschlaegen zwischen 18 und 406
    Trades, von denen keiner in der Naehe des Optimums lag.

    Zwei gegenlaeufige Kurven treffen sich hier: Die Anforderung faellt mit
    der Wurzel der Trade-Zahl, die Erwartung aus der Kopplung faellt linear.
    """

    ziel_spanne: tuple[int, int] = (0, 0)
    """Wie weit das Optimum wandert, wenn die Reststreuung anders liegt.

    Sie ist aus 18 Punkten geschaetzt; ueber ihren Vertrauensbereich liegt
    das Optimum zwischen 142 und 202 Trades. Die Spanne gehoert in den
    Auftrag, weil eine einzelne Zahl dort genauer klaenge als sie ist.
    """

    quoten_spanne: tuple[float, float] = (0.0, 0.0)
    """Die Trefferquote - und warum sie als Bereich dasteht.

    Ueber denselben Vertrauensbereich schwankt sie um Faktor 48. Wer sie als
    einzelne Zahl nennt, behauptet mehr als er weiss (Befund 81). Im Auftrag
    steht sie trotzdem: Ein Vorschlagender, der sie nicht kennt, haelt den
    ersten Treffer fuer einen Fund.
    """

    bedarf_am_ziel: float = 0.0
    """Der noetige Sharpe je Trade **am Optimum**.

    Punkt 2 des Auftrags nannte bis Befund 82 die Anforderung an der Wende,
    waehrend Punkt 1 inzwischen das Optimum nennt. Zwei Zahlen aus zwei
    verschiedenen Trade-Zahlen nebeneinander lesen sich wie ein Widerspruch.
    """

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
            f"1. **Mindestens {self.partner_trades} Trades** im selben Zeitraum,",
            f"   am besten rund **{self.bestes_ziel}**. Darunter genuegt selbst ein",
            "   sehr hoher Sharpe je Trade nicht; darueber faellt die Erwartung",
            "   schneller, als die Anforderung nachgibt.",
            f"2. **Sharpe je Trade ueber {self.bedarf_am_ziel:.2f}** bei der "
            f"Zahl aus Punkt 1.",
            f"   An der Untergrenze von {self.partner_trades} waeren es "
            f"{self.partner_sharpe:.2f}, bei {self.partner_trades * 2} nur",
            f"   noch {self.bedarf_bei_doppelt:.2f} - mehr Trades sind der "
            f"wirksamere Hebel als",
            "   mehr Qualitaet, aber nur bis zum Optimum.",
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

        if self.quoten_spanne[1] > 0:
            von, bis = self.ziel_spanne
            q_von, q_bis = self.quoten_spanne
            zeilen += [
                "## Wie oft so ein Vorschlag trifft\n",
                f"Zwischen {q_von:.1%} und {q_bis:.1%} - und das ist die "
                f"ehrliche Auskunft.",
                "Die Erwartung stammt aus einer Geraden durch 18 Punkte, und",
                "ihre Reststreuung ist selbst unsicher; ueber deren",
                f"Vertrauensbereich schwankt die Quote um Faktor "
                f"{q_bis / q_von:.0f}.",
                "",
                "Robust ist dagegen, **wohin** zu zielen ist: Das Optimum "
                "liegt ueber",
                f"denselben Bereich zwischen {von} und {bis} Trades.",
                "",
                "Praktisch heisst das: Ein Vorschlag, der die drei Punkte",
                "erfuellt, ist ein **Verdacht** und kein Fund. Erst der",
                "gerechnete Verbund entscheidet.",
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
    lage = _optimum(
        versuche=versuche,
        bestand_trades=bestand_trades,
        bestand_sharpe=bestand_sharpe,
        karte=karte,
    )
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
        bestes_ziel=lage[0],
        bedarf_am_ziel=(karte.bedarf(lage[0], 0.72) or bedarf) if lage[0] else bedarf,
        ziel_spanne=lage[1],
        quoten_spanne=lage[2],
    )


def _optimum(
    *, versuche: int, bestand_trades: int, bestand_sharpe: float, karte
) -> tuple[int, tuple[int, int], tuple[float, float]]:
    """Das Trefferoptimum aus der gemessenen Kopplung - samt Bandbreite.

    Die 18 Punkte stehen fest verdrahtet, weil sie eine **Messung** sind und
    keine Konfiguration: Sie stammen aus Befund 75 (Katalog) und 77 (vier
    eigens gebaute Regeln). Wer sie aendert, aendert einen Befund und soll das
    an dieser Stelle merken.

    Faellt die Rechnung aus, bleibt es beim alten Verhalten - dann nennt der
    Auftrag nur die Untergrenze, und das ist schlechter, aber nicht falsch.
    """
    from research.partnerkarte import Anwaerter, Katalogkopplung

    punkte = [
        (258, -0.0368), (185, -0.1113), (156, 0.1894), (124, -0.0469),
        (109, 0.2231), (106, 0.2160), (101, 0.1649), (67, 0.0833),
        (58, 0.3074), (56, 0.1067), (53, 0.3185), (51, 0.1342),
        (50, 0.1377), (36, 0.0576), (18, 0.340522), (114, 0.158416),
        (92, -0.120133), (406, -0.120146),
        # Befund 83: vier auf die Ziel-Taktung kalibrierte Regeln.
        (145, 0.138702), (130, -0.170385), (133, -0.191948), (61, 0.223766),
    ]
    kopplung = Katalogkopplung(
        anwaerter=[
            Anwaerter(name=f"p{i}", trades=n, sharpe_je_trade=s)
            for i, (n, s) in enumerate(punkte)
        ]
    )
    bereich = kopplung.takt_bereich(ziel=karte.ziel, karte=karte)
    if bereich is None or bereich["gemessen"] is None:
        return (0, (0, 0), (0.0, 0.0))
    return (bereich["gemessen"][0], bereich["takt_spanne"], bereich["quoten_spanne"])
