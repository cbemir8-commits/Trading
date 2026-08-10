"""Wo steht das Projekt - auf einem Bildschirm statt in 2400 Zeilen.

Warum es das gibt
-----------------
``strategies/BEFUND.md`` ist ein Laborbuch: chronologisch, vollstaendig, und
fuer jemanden, der wissen will *wo wir stehen*, unbrauchbar. Wer entscheiden
soll, braucht drei Dinge - was gemessen ist, was daraus folgt, und was von ihm
selbst abhaengt.

Was hier steht und was nicht
----------------------------
Die Zahlen werden **gemessen**, nicht gepflegt: Der Kandidat laeuft durch die
Gates, der Abstand kommt aus der Grenzlinie, der Versuchszaehler aus dem
Zustand. Nichts davon ist abgeschrieben, und nichts kann veralten, ohne dass
es auffaellt.

Die Liste der geschlossenen Richtungen ist dagegen **gepflegt** - sie muss es
sein, denn eine Messung, die einmal gelaufen ist, steht nirgends als Zahl
herum. Damit sie nicht zur Behauptung verkommt, traegt jeder Eintrag die
Nummer im BEFUND, unter der die Messung nachzulesen ist. Ein Eintrag ohne
Fundstelle wird abgewiesen.

**Was hier nicht steht: eine Empfehlung.** Zwei der offenen Punkte sind
wirtschaftliche Entscheidungen des Nutzers, keine statistischen. Sie werden
benannt und beziffert, nicht beantwortet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Richtung:
    """Eine untersuchte Richtung und ihr gemessenes Ergebnis."""

    name: str
    ergebnis: str
    befund: int

    def __post_init__(self) -> None:
        if self.befund <= 0:
            raise ValueError(
                f"'{self.name}' ohne Fundstelle im BEFUND - eine geschlossene "
                f"Richtung ohne nachlesbare Messung ist eine Behauptung."
            )

    def __str__(self) -> str:
        return f"{self.name:22} {self.ergebnis:40} Nr. {self.befund}"


#: Die Richtungen, die gemessen und abgeschlossen sind.
#:
#: Reihenfolge: wie sie untersucht wurden. Jede Zeile ist eine Messung, keine
#: Einschaetzung - die Nummer verweist auf die Stelle im BEFUND, an der die
#: Zahlen stehen.
GESCHLOSSEN: tuple[Richtung, ...] = (
    Richtung("Mehr Maerkte", "effektive Stichprobe bleibt bei 150", 27),
    Richtung("Mehr Historie", "Sharpe je Trade faellt, Huerde steigt", 14),
    Richtung("15-Minuten-Kerzen", "alle 14 Kandidaten verlieren brutto", 29),
    Richtung("Vola-Ziel", "bewegt den Deflated Sharpe um 0,011", 21),
    Richtung("Stop-Weite", "4 % ist das Maximum, beide Seiten schlechter", 28),
    Richtung("Konviktions-Bonus", "Risikoregler, kein Qualitaetsregler", 30),
    Richtung("Perioden-Faktor", "mehr Trades, aber Qualitaet faellt schneller", 32),
    Richtung("Termin-Overlay", "2 von 156 Signalen blockiert, kein Gate bewegt", 12),
    Richtung("Shorts", "kein Vorteil in der Gegenrichtung", 13),
    Richtung("Perioden-Ensemble", "mehr Zeilen, keine neue Information", 17),
    Richtung("Abkuehlung", "repariert zwei Gates, verschlechtert die zwei harten", 44),
)


@dataclass(frozen=True, slots=True)
class Entscheidung:
    """Ein offener Punkt, der nicht bei mir liegt."""

    frage: str
    zahl: str
    warum: str


#: Was der Nutzer entscheiden muss - benannt und beziffert, nicht beantwortet.
ENTSCHEIDUNGEN: tuple[Entscheidung, ...] = (
    Entscheidung(
        frage="Mindestrendite von 15 % im Jahr",
        zahl="Der Kandidat schafft 13,5 %. Risikobereinigt schlaegt er das "
             "Halten um das Drei- bis Vierfache.",
        warum="Eine wirtschaftliche Schwelle, kein statistisches Kriterium - "
              "so steht es seit jeher in gates.py. Sie steht im Konflikt mit "
              "der Rueckgangsgrenze: Was die eine verlangt, reisst die andere.",
    ),
    Entscheidung(
        frage="Kontogroesse",
        zahl="Bei 500 Euro laufen 51 % aller Trades auf der Mindestmenge der "
             "Boerse. Ab rund 2000 Euro verschwindet die Beschraenkung.",
        warum="Dort bestimmt nicht mehr die Strategie die Positionsgroesse, "
              "sondern die Boerse - die Risikosteuerung greift bei der Haelfte "
              "der Trades nicht.",
    ),
    Entscheidung(
        frage="Wochenverlustgrenze",
        zahl="Bei -7 % pausiert das System bis zur **manuellen** Freigabe.",
        warum="Richtig so gebaut, aber es wird im Betrieb Telegram-Meldungen "
              "geben, nach denen das System steht, bis jemand es freigibt. "
              "Ob das so bleiben soll, ist eine Betriebsentscheidung.",
    ),
)


#: Was nur auf dem Rechner des Nutzers laufen kann.
#:
#: Der Entwicklungscontainer ist von Bybit aus Regionsgruenden gesperrt. Das
#: ist eine Eigenschaft dieser Sandbox, keine von Bybit und keine des Systems.
BEIM_NUTZER: tuple[tuple[str, str], ...] = (
    (
        "python -m cli healthcheck",
        "Klaert die wichtigste offene Frage: Bietet das Konto ueberhaupt "
        "Perpetuals an? Seit der MiCA-Migration womoeglich nur noch Spot.",
    ),
    (
        "python -m cli abgleich",
        "Erzeugt der Livebetrieb dieselben Signale wie der Backtest? Vor "
        "jedem Livegang auszufuehren.",
    ),
)


@dataclass(slots=True)
class Lage:
    """Der gemessene Stand - alles daran kommt aus einer Messung."""

    kandidat: str
    maerkte: str
    trades: int
    sharpe_je_trade: float
    noetiger_sharpe: float | None
    bestanden: int
    gesamt: int
    offen: tuple[str, ...]
    versuche: int
    cagr_pct: float = 0.0
    rueckgang_pct: float = 0.0

    @property
    def zugelassen(self) -> bool:
        return self.gesamt > 0 and self.bestanden == self.gesamt

    @property
    def faktor(self) -> float | None:
        """Um welchen Faktor die Qualitaet je Trade steigen muesste."""
        if self.noetiger_sharpe is None or self.sharpe_je_trade <= 0:
            return None
        return self.noetiger_sharpe / self.sharpe_je_trade

    def urteil(self) -> str:
        if self.zugelassen:
            return (
                f"'{self.kandidat}' besteht alle {self.gesamt} Gates. Damit ist "
                f"er zugelassen - was noch nicht heisst, dass Geld darauf "
                f"gehoert: Es folgen dreissig Tage Demo."
            )
        fehlend = ", ".join(self.offen) if self.offen else "-"
        text = (
            f"Kein zugelassener Kandidat. '{self.kandidat}' steht bei "
            f"{self.bestanden} von {self.gesamt}; offen: {fehlend}."
        )
        if self.faktor is not None:
            # **Als Zuwachs formuliert, nicht als Verhaeltnis.** Der erste
            # Anlauf schrieb "es fehlen 110 %" fuer einen Faktor von 1,10 -
            # das liest sich, als fehle mehr als alles Vorhandene. Gemeint
            # sind zehn Prozent mehr.
            text += (
                f" Dafuer muesste die Qualitaet je Trade um "
                f"{self.faktor - 1:.0%} steigen: {self.sharpe_je_trade:.4f} "
                f"auf {self.noetiger_sharpe:.4f}."
            )
        return text

    def bericht(self) -> str:
        zeilen = [
            "STAND",
            "=" * 72,
            f"  Kandidat   {self.kandidat}",
            f"  Gemessen   {self.maerkte}",
            f"  Ergebnis   {self.trades} Trades, {self.cagr_pct:.2f} % p.a., "
            f"{self.rueckgang_pct:.2f} % Rueckgang",
            f"  Gates      {self.bestanden} von {self.gesamt}",
            f"  Versuche   {self.versuche}",
            "",
            self.urteil(),
            "",
            "GEMESSEN UND GESCHLOSSEN",
            "-" * 72,
        ]
        zeilen.extend(f"  {r}" for r in GESCHLOSSEN)
        zeilen += ["", "WAS NICHT BEI MIR LIEGT", "-" * 72]
        for e in ENTSCHEIDUNGEN:
            zeilen += [f"  {e.frage}", f"    {e.zahl}", f"    {e.warum}", ""]
        zeilen += ["NUR AUF DEINEM RECHNER", "-" * 72]
        for befehl, warum in BEIM_NUTZER:
            zeilen += [f"  {befehl}", f"    {warum}"]
        return "\n".join(zeilen)
