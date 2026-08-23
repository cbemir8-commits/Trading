"""Was der Analyst nicht weiss - und deshalb immer wieder vorschlaegt.

Der Anlass
----------
In Befund 83 habe ich vier Regeln gebaut, deren Einstiegstakt auf die
gebrauchte Trade-Zahl kalibriert war. Alle vier sind gescheitert, und zwei
davon waren Rueckkehr-zum-Mittel-Regeln - eine Familie, die Befund 84
geschlossen hat: Alle fuenf liegen unter der Regressionsgeraden, und die
Trennung haelt einer Permutation stand.

Dieselbe Sackgasse steht dem Analysten offen. ``build_prompt`` gibt ihm die
Zulassungsschwellen, die letzten Journaleintraege und seit kurzem den
Auftrag aus ``auftragslage``. Was fehlt, ist die andere Haelfte: **was
gemessen und geschlossen ist.**

Ein Auftrag, der nur sagt "finde etwas Gutes", laesst denselben Fehlschlag
beliebig oft zu. Einer, der sagt "diese fuenf Regeln dieser Familie liegen
geschlossen unter der Geraden, Permutationsprobe bestanden", schliesst ihn
aus.

Der unangenehme Teil
--------------------
Der Auftrag verlangt zwei Dinge zugleich: hohe Qualitaet je Trade **und**
Unabhaengigkeit vom Trendfolge-Signal des Bestands. Befund 84 hat gemessen,
dass die beiden gegeneinander laufen - ueber 22 Regeln korreliert das
Guete-Residuum mit der Aehnlichkeit zum Bestand mit **+0,48**.

Das gehoert in den Auftrag, und zwar nicht als Verbot. Ein Vorschlag, der
beides erfuellt, ist eine Ausnahme von einem gemessenen Muster - und genau
danach wird gesucht. Wer das weiss, sucht anders, als wer es nicht weiss.

Warum das nicht gepflegt wird
-----------------------------
Eine handgeschriebene Liste "diese Wege sind zu" veraltet ab dem Tag, an dem
sie geschrieben wird - und niemand merkt es, weil sie plausibel bleibt. Die
Ausschluesse hier werden deshalb aus denselben Messungen abgeleitet, die auch
``cli familien`` und ``cli anwaerter`` zeigen. Aendert sich die Messung,
aendert sich der Auftrag.

Was hier **nicht** hineingehoert, sind die strukturellen Befunde, die nicht
am Regelvorrat haengen (Groessenregler aus Befund 30, die Pearson-Grenze aus
Befund 70). Die betreffen nicht, was ein Analyst vorschlagen kann.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: Ab dieser Korrelation zwischen Aehnlichkeit und Qualitaet gilt der
#: Zielkonflikt als gemessen und gehoert benannt.
SPUERBARER_WIDERSPRUCH = 0.3

#: Unter so vielen Regeln in einer Familie wird sie nicht ausgeschlossen -
#: zwei schlechte Regeln sind kein Urteil ueber eine Regelart.
MINDESTBELEG = 4


#: Die 22 Regeln aus Befund 75, 77 und 83: Name, Trades, Sharpe je Trade,
#: Fensterkorrelation zum Bestand. Gemessen auf Tageskerzen ueber BTC und ETH.
#:
#: Sie stehen hier als Zahlen und werden nicht neu gerechnet - ein
#: Walk-Forward ueber 22 Genome nur fuer einen Auftragstext waere Rechenzeit
#: fuer nichts. Nachzurechnen sind sie mit ``cli anwaerter`` und ``cli
#: partner``; weicht etwas ab, ist diese Liste falsch und nicht die Messung.
GEMESSENE_REGELN: tuple[tuple[str, int, float, float | None], ...] = (
    ("Luecke", 258, -0.0368, None),
    ("VWAP-short", 185, -0.1113, -0.536),
    ("Trend 50", 156, 0.1894, 0.813),
    ("Abfolge o.Str", 124, -0.0469, 0.456),
    ("Trend 100", 109, 0.2231, 0.787),
    ("Trend beide", 106, 0.2160, 0.473),
    ("Momentum 90", 101, 0.1649, 0.712),
    ("Abfolge short", 67, 0.0833, -0.407),
    ("Donchian 55", 58, 0.3074, 0.534),
    ("Abfolge-Modell", 56, 0.1067, 0.391),
    ("Vola-Ziel lang", 53, 0.3185, 0.555),
    ("Gr.Kerze short", 51, 0.1342, -0.080),
    ("Abfolge o.Lue", 50, 0.1377, 0.499),
    ("Bollinger short", 36, 0.0576, None),
    ("Enge", 18, 0.340522, 0.417),
    ("Volumenschock", 114, 0.158416, 0.396),
    ("Rueckkehr VWAP", 92, -0.120133, 0.063),
    ("Abgriff", 406, -0.120146, 0.129),
    ("Volumenschock breit", 145, 0.138702, 0.587),
    ("Rueckkehr VWAP breit", 130, -0.170385, 0.311),
    ("Ueberverkauft", 133, -0.191948, 0.375),
    ("Enge breit", 61, 0.223766, 0.437),
)

#: Die acht selbst gebauten Regeln aus Befund 77 und 83, alle gescheitert.
#:
#: Sie stehen **nicht** im Journal des Research-Loops, weil sie ausserhalb
#: davon entstanden sind - und fehlten dem Analysten deshalb vollstaendig.
#: Genau diese Luecke hat in Befund 83 dazu gefuehrt, dass zwei von vier
#: Vorschlaegen aus einer Familie kamen, die schon durchgemessen war.
GESCHEITERTE_EIGENBAUTEN: tuple[tuple[str, int, float], ...] = (
    ("Enge vor Bewegung", 18, 0.340522),
    ("Volumenschock mit Fortsetzung", 114, 0.158416),
    ("Rueckkehr zum Volumenschwerpunkt", 92, -0.120133),
    ("Abgriff des Vortagestiefs", 406, -0.120146),
    ("Volumenschock breit", 145, 0.138702),
    ("Rueckkehr zum Volumenschwerpunkt breit", 130, -0.170385),
    ("Ueberverkauft ohne Trendfilter", 133, -0.191948),
    ("Enge vor Bewegung breit", 61, 0.223766),
)


@dataclass(frozen=True, slots=True)
class Sackgasse:
    """Ein Weg, der gemessen zu ist - mit der Zahl, die ihn schliesst."""

    familie: str
    regeln: int
    bestes_residuum: float
    """Auch die **beste** Regel der Familie liegt so weit unter der Geraden.
    Der Wert traegt den Ausschluss: Ein Familienmittel unter null sagt wenig,
    wenn eine einzelne Regel darin gut ist."""

    @property
    def geschlossen(self) -> bool:
        return self.regeln >= MINDESTBELEG and self.bestes_residuum < 0

    def als_zeile(self) -> str:
        return (
            f"- **{self.familie}**: {self.regeln} Regeln gemessen, auch die "
            f"beste liegt {abs(self.bestes_residuum):.3f} unter der Geraden."
        )


@dataclass(slots=True)
class Ausschluesse:
    """Was der Analyst wissen muss, bevor er vorschlaegt."""

    sackgassen: list[Sackgasse] = field(default_factory=list)
    widerspruch: float | None = None
    """Korrelation zwischen Aehnlichkeit zum Bestand und Qualitaet. Positiv
    heisst: Der Auftrag verlangt zwei Dinge, die gegeneinander laufen."""
    permutation_haelt: bool = False
    """Ob die Familientrennung einer Zufallszuordnung standhaelt. Ohne diese
    Gegenprobe ist eine Gruppierung ueber 22 Punkte wertlos - bei fuenf
    Familien faellt eine Spannweite von 1,1 rein zufaellig an."""
    gescheiterte: list[tuple[str, int, float]] = field(default_factory=list)
    """Selbstgebaute Regeln aus Befund 77 und 83: Name, Trades, Sharpe je
    Trade. Sie stehen nicht im Journal des Research-Loops, weil sie nicht
    dort entstanden sind - und fehlten dem Analysten deshalb."""

    @property
    def geschlossene(self) -> list[Sackgasse]:
        return [s for s in self.sackgassen if s.geschlossen]

    @property
    def traegt(self) -> bool:
        """Gibt es ueberhaupt etwas zu sagen?

        Ohne bestandene Permutationsprobe wird **keine** Familie
        ausgeschlossen. Eine Gruppierung, die dem Zufall nicht standhaelt,
        darf keine Vorschlaege verhindern.
        """
        return self.permutation_haelt and bool(self.geschlossene)

    def als_auftrag(self) -> str:
        """Der Abschnitt, der in den Prompt gehoert - oder nichts."""
        zeilen: list[str] = []

        if self.traegt:
            zeilen += [
                "## Was gemessen und geschlossen ist\n",
                "Diese Regelarten sind durchgemessen. Ein Vorschlag daraus",
                "kostet einen Versuch und hebt damit die Huerde fuer alle",
                "anderen - ohne Aussicht:",
                "",
            ]
            zeilen += [s.als_zeile() for s in self.geschlossene]
            zeilen += [
                "",
                "Die Zuordnung wurde **nach** dem Blick auf die Zahlen",
                "gemacht und gegen eine Zufallszuordnung geprueft; sie haelt.",
                "",
            ]

        if self.gescheiterte:
            # **"Gescheitert" war die falsche Einordnung** (Befund 122). Seit
            # die Liste aus dem Versuchsverzeichnis kommt, stehen auch die
            # drei Verbuende darin - mit Guete 0,26 bis 0,30, also auf Hoehe
            # des Bestands oder darueber. Sie sind nicht schlecht; sie haben
            # nicht gereicht. Das ist die schaerfere Auskunft, und fuer einen
            # Auftrag, der auf Verbuende zielt, die entscheidende.
            zeilen += [
                "## Bereits gemessen - und es hat nicht gereicht\n",
                "Diese Regeln stehen nicht im Journal, weil sie ausserhalb",
                "des Research-Loops entstanden sind. Jede hat einen Versuch",
                "gekostet. Eine hohe Guete in dieser Liste heisst nicht, dass",
                "die Regel taugt - sie heisst, dass selbst diese Guete nicht",
                "gereicht hat:",
                "",
            ]
            zeilen += [
                f"- {name}: {trades} Trades zu je {sharpe:+.4f}"
                for name, trades, sharpe in self.gescheiterte
            ]
            zeilen.append("")

        if (
            self.widerspruch is not None
            and self.widerspruch > SPUERBARER_WIDERSPRUCH
        ):
            zeilen += [
                "## Der Zielkonflikt im Auftrag\n",
                "Der Auftrag verlangt hohe Qualitaet je Trade **und**",
                "Unabhaengigkeit vom Trendfolge-Signal des Bestands. Ueber",
                "alle bisher gemessenen Regeln laufen die beiden",
                f"gegeneinander: Die Korrelation betraegt **{self.widerspruch:+.3f}**.",
                "Je unabhaengiger eine Regel bisher war, desto schlechter war",
                "sie.",
                "",
                "Das ist **kein Verbot**, sondern der Grund, warum die Aufgabe",
                "schwer ist. Ein Vorschlag, der beides erfuellt, waere eine",
                "Ausnahme von einem gemessenen Muster - und genau danach wird",
                "gesucht. Naheliegende Varianten des Bestands erfuellen",
                "Punkt 2 und scheitern an Punkt 3; weit entfernte Regeln",
                "umgekehrt.",
                "",
            ]

        return "\n".join(zeilen)


def aus_familienbild(bild, *, gescheiterte=None) -> Ausschluesse:
    """Die Ausschluesse aus einer fertigen Familienmessung ableiten.

    Nimmt ``research.familien.Familienbild`` entgegen - dieselbe Messung, die
    ``cli familien`` zeigt. Damit gibt es keine zweite Wahrheit ueber die
    Frage, welche Familie geschlossen ist.
    """
    if not bild.genug:
        return Ausschluesse(gescheiterte=list(gescheiterte or []))

    sackgassen = [
        # ``je_familie`` liefert je Familie (Anzahl, Mittel, schlechtestes,
        # bestes Residuum). Massgeblich ist das **beste**: Solange eine Regel
        # der Familie ueber der Geraden liegt, ist die Familie nicht zu.
        Sackgasse(familie=name, regeln=int(werte[0]), bestes_residuum=float(werte[3]))
        for name, werte in bild.je_familie().items()
    ]
    return Ausschluesse(
        sackgassen=sackgassen,
        widerspruch=bild.guete_faehrt_auf_aehnlichkeit,
        permutation_haelt=bild.trennt_echt,
        gescheiterte=list(gescheiterte or []),
    )


__all__ = [
    "GEMESSENE_REGELN",
    "GESCHEITERTE_EIGENBAUTEN",
    "MINDESTBELEG",
    "SPUERBARER_WIDERSPRUCH",
    "Ausschluesse",
    "Sackgasse",
    "aus_familienbild",
]


def aus_versuchsverzeichnis(
    pfad: Path | str,
) -> tuple[tuple[str, int, float], ...]:
    """Die gemessenen Versuche aus ``trials.json`` - statt einer zweiten Liste.

    Warum das noetig war
    --------------------
    ``GESCHEITERTE_EIGENBAUTEN`` ist eine **Abschrift** von ``trials.json``:
    dieselben acht Namen, dieselben Zahlen auf sechs Stellen gerundet, von
    Hand gepflegt. Befund 122 hat gemessen, was dabei herauskommt - das
    Verzeichnis hat **elf** Eintraege, die Abschrift acht.

    Die drei fehlenden sind die **Verbuende**:

        Verbund Spitze + Trend-Beteiligung 200    207 Trades   +0,2759
        Verbund Spitze + Donchian-Ausbruch 55/20  212 Trades   +0,2569
        Verbund Trend-Beteiligung 200 + Donchian  111 Trades   +0,2956

    Und das ist die unguenstigste Auslassung, die denkbar war: Der Auftrag
    lenkt den Analysten ausdruecklich auf ein *"zweites, unabhaengiges
    Signal, das parallel gehandelt wird"* - also auf einen Verbund - und
    verschwieg ihm genau die drei, die dazu schon gemessen sind.

    Was diese drei sagen
    --------------------
    Nicht "Verbuende sind schlecht". Ihre Guete liegt bei 0,26 bis 0,30, also
    auf Hoehe des Bestands oder darueber. Sie sagen: **Auch ein Verbund mit
    dieser Guete reicht nicht.** Das ist die schaerfere Auskunft, und sie
    stand dem Analysten nicht zur Verfuegung.

    Wer weiter fuehrt
    -----------------
    Ab hier das Verzeichnis. Es wird ohnehin bei jedem Versuch fortgeschrieben,
    und eine Liste, die jemand daneben pflegen muss, laeuft frueher oder
    spaeter auseinander - hier war es nach drei Eintraegen so weit.
    """
    from research.versuche import ZaehlerUnlesbarError
    from research.versuche import laden as verzeichnis_laden

    try:
        verzeichnis = verzeichnis_laden(pfad)
    except (ZaehlerUnlesbarError, OSError):
        return ()

    return tuple(
        (e.kennung, e.trades, float(e.sharpe_je_trade))
        for e in verzeichnis.eintraege
        if e.sharpe_je_trade is not None
    )
