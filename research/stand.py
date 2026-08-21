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
    Richtung("Abkuehlung", "zwei Gates - aber nur durch Streichen", 60),
    Richtung("Trades streichen", "reicht fuer zwei Gates, egal welche", 60),
    Richtung("Gewinnziel", "laengeres rechtes Ende kostet mehr, als es bringt", 46),
    Richtung("Adaptive Periode", "mehr Trades, aber einander aehnlicher", 48),
    Richtung("Kanalausbruch", "strukturell neu, 5 von 11, Faktor 1,74", 53),
    Richtung("Umsatzfilter", "neue Informationsquelle, DSR 0,162", 53),
    Richtung("Rueckkehr zum Mittel", "Gegenthese gemessen: 1 von 11", 53),
    # Ab hier die Wege, die seit Befund 70 geschlossen wurden. Sie fehlten
    # bis Befund 90 vollstaendig - und damit sah ein Lauf, der hier nachsah,
    # nur den Stand von vor zwanzig Befunden.
    Richtung("Schiefe erhoehen", "Pearson-Grenze: Woelbung >= Schiefe^2 + 1", 70),
    Richtung("Woelbung senken", "unter 1 mathematisch unmoeglich", 70),
    Richtung("Trade-Zahl heben", "Kopplung -0,53 ueber 22 Regeln", 75),
    Richtung("Katalog als Partner", "0 von 15 Genomen taugen", 74),
    Richtung("Eigenbau-Partner", "8 Regeln aus Befund 77 und 83 gescheitert", 83),
    Richtung("Familie Rueckkehr", "alle 5 unter der Geraden, Permutation haelt", 84),
    Richtung("Phasen-Partner", "6 von 22 gegenlaeufig, 5 davon insgesamt wertlos", 85),
    Richtung("Verbund aus dem Katalog", "bestes Paar 3,585 unter Nullmedian 3,683", 86),
    Richtung("Sperrfrist", "Folgetrades schlechter, aber kein t-Wert ueber 2", 88),
    Richtung("Verbund fuer die Risikogates", "231 Kombinationen, kein Treffer", 94),
    Richtung(
        "Groessenregler zum Rechteck",
        "ohne Mengenrundung glatt und monoton, Verhaeltnis 1,07 gegen 1,25",
        95,
    ),
    Richtung(
        "Koernung zum Deflated Sharpe",
        "bewegt ihn ueber die ganze Kontoleiter um 0,014",
        96,
    ),
    Richtung(
        "Feinere Kerzen im Fuellmodell",
        "80,8 % der Balken aufgeloest, Ergebnis bitgleich",
        99,
    ),
)



#: Die deutschen Zahlwoerter, mit denen die Abschnitte im Laborbuch
#: ueberschrieben sind ("## Fuenfundachtzig. ..."). Ohne sie laesst sich eine
#: Fundstelle nicht maschinell nachschlagen - und eine Liste geschlossener
#: Wege, deren Verweise niemand prueft, driftet still von der Wirklichkeit ab.
_EINER = (
    "", "Ein", "Zwei", "Drei", "Vier", "Fuenf", "Sechs", "Sieben", "Acht", "Neun",
)
_ZEHNER = (
    "", "Zehn", "Zwanzig", "Dreissig", "Vierzig", "Fuenfzig", "Sechzig",
    "Siebzig", "Achtzig", "Neunzig",
)
#: Zahlen, die nicht nach dem Muster gebildet werden. Die Teens (13 bis 19)
#: heissen "dreizehn" und nicht "dreiundzehn"; bei den Zwanzigern heisst die
#: Eins "ein" und nicht "eins".
_SONDER = {
    1: "Eins", 11: "Elf", 12: "Zwoelf", 13: "Dreizehn", 14: "Vierzehn",
    15: "Fuenfzehn", 16: "Sechzehn", 17: "Siebzehn", 18: "Achtzehn",
    19: "Neunzehn",
}


def zahlwort(n: int) -> str:
    """Die Ueberschrift, unter der Befund ``n`` im Laborbuch steht.

    Gebraucht wird das nur zum Nachschlagen: Ein Test prueft damit, dass jede
    Fundstelle in ``GESCHLOSSEN`` auf einen Abschnitt zeigt, den es wirklich
    gibt. Der erste Anlauf zu diesem Modul hat eine 15-Minuten-Messung
    wiederholt, die in Befund 29 laengst stand - die Liste war richtig, nur
    ungeprueft und unvollstaendig.
    """
    if not 1 <= n <= 99:
        # Ueber 99 gaebe es "Hundertein" und Aehnliches. Statt das zu bauen,
        # bevor es gebraucht wird, faellt die Suche hier sichtbar aus - ein
        # leerer String findet keine Ueberschrift, und der Test schlaegt an.
        return ""
    if n in _SONDER:
        return _SONDER[n]
    if n < 10:
        return _EINER[n]
    zehner, einer = divmod(n, 10)
    if einer == 0:
        return _ZEHNER[zehner]
    return f"{_EINER[einer]}und{_ZEHNER[zehner].lower()}"


@dataclass(frozen=True, slots=True)
class Suchbudget:
    """Das Abbruchkriterium aus dem Plan - endlich im System statt nur im Text.

    Der Plan vom 9. August legt es fest: *"Erreicht nach 100 weiteren Versuchen
    kein Kandidat 11 von 11, lautet die Antwort 'diese Regelfamilie traegt
    nicht'. Das ist ein Ergebnis, kein Scheitern."*

    **Warum das ueberhaupt aufgeschrieben gehoert.** Eine Suche ohne Ende ist
    keine Suche, sondern Warten - und sie ist hier nicht nur unproduktiv,
    sondern schaedlich: Jeder Versuch hebt die Huerde des Deflated Sharpe um
    0,00021 fuer alle kuenftigen. Wer weitersucht, macht das Ziel schwerer,
    das er sucht.

    **Warum eine Zahl und keine Bedingung.** Ein Kriterium wie "abbrechen, wenn
    sich nichts mehr verbessert" laesst sich nachtraeglich zurechtlegen - man
    findet immer eine Kennzahl, die noch Hoffnung macht. Eine vorab genannte
    Zahl kann das nicht. Sie ist grob, und das ist ihr Vorzug.

    **Und seit Befund 71 ist der Umfang auch beziffert.** Huerde und bester Fund
    wachsen beide mit derselben Extremwertkonstante; es entscheidet allein, ob
    die Streuung echter Regelideen ueber der des reinen Zufalls liegt. Aus dem
    eigenen Verlauf kalibriert sind es 0,0950 gegen 0,0808 - genug, um
    aufzuholen, aber erst bei rund 56.000 Versuchen. Bis zum Abbruch bei 230
    schliesst sich der Abstand von 0,0351 auf 0,0324. **Das Budget ist damit
    nicht zu knapp bemessen, sondern die Groessenordnung, in der Suchen ueber-
    haupt noch etwas aendert.** ``cli rennen`` rechnet es nach.

    Der Zaehler selbst steht in ``state/trials.json`` und wird hier nur
    eingeordnet. Beides auseinanderzuhalten ist Absicht: Das Budget ist eine
    Abmachung, der Zaehler eine Messung.
    """

    beginn: int = 130
    """Der Versuchsstand, als der Plan geschrieben wurde."""

    umfang: int = 100

    @property
    def grenze(self) -> int:
        return self.beginn + self.umfang

    def verbraucht(self, versuche: int) -> int:
        return max(0, versuche - self.beginn)

    def rest(self, versuche: int) -> int:
        return max(0, self.grenze - versuche)

    def erschoepft(self, versuche: int) -> bool:
        return versuche >= self.grenze

    def zeile(self, versuche: int) -> str:
        if self.erschoepft(versuche):
            return (
                f"{self.verbraucht(versuche)} von {self.umfang} - **aufgebraucht**. "
                f"Damit gilt die Antwort aus dem Plan: Diese Regelfamilie traegt "
                f"nicht. Das ist ein Ergebnis, kein Scheitern."
            )
        return (
            f"{self.verbraucht(versuche)} von {self.umfang} verbraucht, "
            f"{self.rest(versuche)} bleiben (Abbruch bei {self.grenze})."
        )


#: Das im Plan festgelegte Budget. Eine Abmachung, keine Messung.
BUDGET = Suchbudget()


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
        zahl="Gemessen ueber zehn Stellungen des Groessenreglers: **keine** "
             "haelt beide Schwellen. Bei 20,5 bleibt der Rueckgang mit "
             "11,29 % unter der Grenze, die Rendite steht bei 14,11 % - es "
             "fehlen 0,89 Punkte. Eine Stufe weiter (21,0) reisst der "
             "Rueckgang mit 12,50 %, und die Rendite fehlt immer noch.",
        warum="Eine wirtschaftliche Schwelle, kein statistisches Kriterium - "
              "so steht es seit jeher in gates.py. Dass sie mit der "
              "Rueckgangsgrenze im Konflikt steht, war lange eine Behauptung "
              "und ist seit Befund 57 beziffert: `cli vereinbar` rechnet es "
              "jederzeit nach. Die Aufloesung ist eine Geschaeftsentscheidung "
              "- den Kandidaten dorthin zu stellen, wo mehr Gates bestehen, "
              "ist ausdruecklich keine.",
    ),
    Entscheidung(
        frage="Die geratene Eingabe im Deflated Sharpe",
        zahl="Das Gate braucht die Streuung der Sharpe-Schaetzer ueber die "
             "Versuche. Gemessen wird sie nicht - es springt die "
             "Ersatzannahme 1/(n-1) ein, hier sqrt(V) = 0,0808. Das Urteil "
             "kippt bei 0,0657, also **23 % darunter**. Aus den 28 Versuchen, "
             "die ihren Sharpe je Trade mittragen, kaemen 0,0608 - und damit "
             "0,97 statt 0,79. `cli streuung` rechnet es nach.",
        warum="Die 0,0608 werden nicht eingesetzt, und zwar nicht aus "
              "Vorsicht: Von 166 Versuchen liegen 28 vor, und was fehlt, "
              "fehlt am unteren Ende - Berichte entstehen ueber Reglerscans "
              "um den Bestand herum, die Verlierer bekommen keinen. Die "
              "Bestenliste allein streut schon mit 0,1030, also breiter als "
              "die Annahme. Aufgeschrieben wird seit Befund 69 jeder neue "
              "Versuch mit seinem Sharpe je Trade; der Grundstock von 166 "
              "bleibt ohne Einzelnachweis. Damit ist die Abdeckung bis zum "
              "Abbruch des Suchbudgets bei 230 Versuchen auf hoechstens 40 % "
              "gedeckelt - ``streuung.MINDESTABDECKUNG`` verlangt 90. Die "
              "Annahme bleibt also stehen, und zwar auf absehbare Zeit. Zu "
              "entscheiden bleibt nur, ob das je anders sein soll.",
    ),
    Entscheidung(
        frage="Kontogroesse",
        zahl="Bei 500 Euro laufen 51 % aller Trades auf der Mindestmenge der "
             "Boerse. Ab rund 2000 Euro verschwindet die Beschraenkung. Und "
             "seit Befund 95 ist beziffert, was daran haengt: Der Rueckgang "
             "des Bestands steigt mit dem Konto von 9,92 % (300 Euro) auf "
             "12,95 % (100.000 Euro) - **dieselbe Strategie**. Das "
             "Rueckgang-Gate haelt nur unterhalb von rund 1150 Euro. Ursache "
             "ist die Mengenrundung, belegt durch zwei unabhaengige "
             "Gegenproben; `cli koernung` rechnet es nach. Befund 96 hat alle "
             "elf Gates ueber dieselbe Leiter gefahren: **Genau zwei wandern** "
             "- Rueckgang und schlechtestes Jahr, beides Risikomasse auf der "
             "Kapitalkurve. Neun stehen still, darunter der Deflated Sharpe "
             "(0,772 bis 0,786 ueber den ganzen Bereich). Die Bilanz laeuft "
             "von 8 von 11 bei 300 Euro auf **6 von 11** ab 1500 Euro; die "
             "hier gemeldeten 7 von 11 gelten fuer 500 Euro.",
        warum="Dort bestimmt nicht mehr die Strategie die Positionsgroesse, "
              "sondern die Boerse - die Risikosteuerung greift bei der Haelfte "
              "der Trades nicht. Es ist damit auch keine reine "
              "Betriebsentscheidung mehr: Eines der acht bestandenen Gates "
              "haelt nur, solange das Konto klein bleibt. Wer auf 2000 Euro "
              "aufstockt, aendert an der Strategie nichts und reisst es "
              "trotzdem.",
    ),
    Entscheidung(
        frage="Wochenverlustgrenze",
        zahl="Bei -7 % pausiert das System bis zur **manuellen** Freigabe.",
        warum="Richtig so gebaut, aber es wird im Betrieb Telegram-Meldungen "
              "geben, nach denen das System steht, bis jemand es freigibt. "
              "Ob das so bleiben soll, ist eine Betriebsentscheidung.",
    ),
)


@dataclass(frozen=True, slots=True)
class Auftragspunkt:
    """Ein Punkt aus dem Auftrag und sein gemessener Stand.

    **Warum es das braucht.** Der Auftrag listet in jeder Runde dieselben
    offenen Punkte. Zwei davon waren zu diesem Zeitpunkt laengst abgearbeitet -
    die 15-Minuten-Generationen seit Befund 29, das Termin-Overlay seit Nummer
    zwoelf -, aber es gab keine Stelle, an der das nachzulesen war. Also
    standen sie weiter da, und ich habe sie weiter als offen gelesen.

    Das ist nicht nur unordentlich, es ist **teuer**: Beinahe waeren vierzehn
    Versuche fuer eine Messung ausgegeben worden, die es schon gab. Genau
    davor warnt ``load_seeds`` seit jeher - jeder Wiederholungsversuch hebt die
    Huerde des Deflated Sharpe fuer alle folgenden, ohne etwas beizutragen.

    ``befund`` ist Pflicht, sobald ein Punkt als erledigt gilt: Erledigt ohne
    Fundstelle ist eine Behauptung.
    """

    frage: str
    stand: str
    befund: int = 0
    erledigt: bool = True

    def __post_init__(self) -> None:
        if self.erledigt and self.befund <= 0:
            raise ValueError(
                f"'{self.frage}' gilt als erledigt, hat aber keine Fundstelle "
                f"im BEFUND - das waere eine Behauptung."
            )

    def __str__(self) -> str:
        marke = f"Nr. {self.befund}" if self.befund else "offen"
        return f"{'OK' if self.erledigt else '--'} {self.frage:34} {self.stand}  ({marke})"


#: Die Punkte aus dem Auftrag, mit ihrem gemessenen Stand.
AUFTRAG: tuple[Auftragspunkt, ...] = (
    Auftragspunkt(
        frage="P7: News- und Termin-Overlay",
        stand="beides gebaut und gemessen; die Wirkung ist nicht belegt",
        befund=59,
    ),
    Auftragspunkt(
        frage="Research-KI im Wettbewerb nutzen",
        stand="genutzt, vier Vorschlaege gemessen - alle schlechter",
        befund=53,
    ),
    Auftragspunkt(
        frage="Generation 6/7 auf 15-Minuten",
        stand="alle 14 gemessen: 1 von 9 Gates, -9 bis -44 % p.a.",
        befund=29,
    ),
    Auftragspunkt(
        frage="Generation 5 auf Tageskerzen",
        stand="Zuordnung liegt jetzt als Daten vor, Fehlpaarung wird gesperrt",
        befund=64,
    ),
    Auftragspunkt(
        frage="backfill 15m + wettbewerb beim Nutzer",
        stand="Daten liegen hier vor; auf dem eigenen Rechner weiter noetig",
        befund=62,
        erledigt=False,
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
            f"  Suchbudget {BUDGET.zeile(self.versuche)}",
            "",
            self.urteil(),
            "",
            "GEMESSEN UND GESCHLOSSEN",
            "-" * 72,
        ]
        zeilen.extend(f"  {r}" for r in GESCHLOSSEN)
        zeilen += ["", "PUNKTE AUS DEM AUFTRAG", "-" * 72]
        zeilen.extend(f"  {p}" for p in AUFTRAG)
        offen = [p for p in AUFTRAG if not p.erledigt]
        zeilen.append(
            f"  -> {len(AUFTRAG) - len(offen)} von {len(AUFTRAG)} abgearbeitet."
            + (
                "  Wer einen davon erneut misst, zahlt Versuche fuer ein "
                "Ergebnis, das schon dasteht."
                if len(offen) < len(AUFTRAG)
                else ""
            )
        )
        zeilen += ["", "WAS NICHT BEI MIR LIEGT", "-" * 72]
        for e in ENTSCHEIDUNGEN:
            zeilen += [f"  {e.frage}", f"    {e.zahl}", f"    {e.warum}", ""]
        zeilen += ["NUR AUF DEINEM RECHNER", "-" * 72]
        for befehl, warum in BEIM_NUTZER:
            zeilen += [f"  {befehl}", f"    {warum}"]
        return "\n".join(zeilen)
