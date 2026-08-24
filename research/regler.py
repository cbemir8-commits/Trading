"""Ein Regler, ueber mehrere Stellungen abgefahren - und was das beweist.

Befund 21 hat den Vola-Ziel-Regler ueber sieben Stellungen gefahren und keinen
Wert gefunden, an dem alles haelt. Das Ergebnis war kein *knapp daneben*,
sondern ein **Konflikt**: drei Gates, die sich gegenseitig ausschliessen.

    Messlatte            haelt erst ab 25 %
    Drawdown             haelt nur bis 22 %
    Schlechtestes Jahr   haelt nur bis 19,3 %

Gemessen wurde das am **Perpetual**-Punkt. Befund 108 hat den Betriebspunkt
gewechselt, und am Spot-Punkt wandern beide Grenzen in dieselbe Richtung: die
Rendite steigt, der Rueckgang faellt. Ob sich das Fenster dabei oeffnet, war
eine Messfrage. Nachgemessen (Befund 128, dieselben sieben Stellungen, BTC +
ETH, Tageskerzen, 198 Versuche):

      Ziel  Trades    p.a.   MaxDD   Perpetual        Spot
      14,0     149   10,4 %   7,2 %      9/11        9/11
      16,0     154   12,1 %   7,8 %      9/11        9/11
      19,3     152   14,8 %   9,9 %      7/11        9/11   <- verschoben
      22,0     152   16,7 %  11,9 %      7/11        9/11   <- verschoben
      25,0     152   19,2 %  13,7 %      7/11        7/11
      28,0     152   21,1 %  15,5 %      7/11        7/11
      32,0     152   24,7 %  16,9 %      5/11        7/11   <- verschoben

(Rendite und Rueckgang sind die Spot-Werte; am Perpetual-Punkt liegen sie
niedriger bzw. hoeher.) **Das Fenster oeffnet sich nicht.** Der Schluss aus
Befund 21 haelt, die Tabelle darunter ist an drei von sieben Stellungen eine
andere - und der Konflikt ist von "16,0 gegen 22,0 mit 19,3 mittendrin" auf
"19,3 gegen 22,0, nichts dazwischen" zusammengeschrumpft.

Dieses Modul haelt fest, was aus einer solchen Messung folgen darf und was
nicht.

Welche Regler hier stehen
-------------------------
``ARTEN`` fuehrt die Regler, die ein Befund schon einmal abgefahren hat -
jeweils mit **genau** seiner Stellungsreihe:

    vola   Vola-Ziel in Prozent            Befund 21   7 Stellungen
    ziel   Gewinnziel in Vielfachen von R  Befund 46   6 Stellungen

Beide wurden am Perpetual-Punkt gemessen. Dass die Stellungsreihe mit im
Register steht, ist kein Detail: Sie ist seit damals im Versuchszaehler und
kostet deshalb nichts mehr. Jede Stellung daneben ist ein neuer Kandidat.

Was hier absichtlich fehlt
--------------------------
**Es gibt keine Methode, die die beste Stellung zurueckgibt.** Dieselbe Regel
wie in ``decke.Fensterlage``: Wer sich nach den Zahlen eine Stellung aussucht,
hat gesucht und nicht geprueft, und bekommt eine Zahl, die besteht, ohne dass
sich an der Strategie etwas geaendert haette.

Zulaessig ist nur die Frage nach dem **Fenster**: Gibt es eine Stellung, an der
*alles* haelt? Gibt es keine, ist der Regler zu - unabhaengig davon, wie nah
einzelne Stellungen an einzelnen Schwellen liegen.

Was eine Leiter beweisen kann - und was nicht
---------------------------------------------
Eine Leiter ist nur an ihren Sprossen gemessen. Ein stetiger Regler laesst
sich damit **nie** vollstaendig ausschliessen: Zwischen 19,3 und 22,0 kann man
20,0 messen, und zwischen 19,3 und 20,0 wieder 19,6. "Die Sprossen liegen
nebeneinander" heisst deshalb nur *so eng, wie diese Leiter gemessen hat*, und
nicht *dazwischen liegt nichts*.

Was eine Leiter sehr wohl beweist, ist ein Gate, das an **jeder** Sprosse
offen steht. Und beim Deflated Sharpe kommt etwas dazu, das die Frage
endgueltig erledigt: Er haengt am Zaehlerstand. Jede neue Reglerstellung ist
ein gerechneter Kandidat und zaehlt (``research/machbarkeit.py``) - wer
nachmisst, hebt also die Huerde, **bevor** ein Ergebnis vorliegt. Gemessen am
eigenen Fall (Befund 128), Spot-Punkt, 152 Trades:

       Versuche       DSR    Luecke zu 0,95
            198    0,8640           0,0860   Stand jetzt
            203    0,8609           0,0891   +5 Halbschritte
            230    0,8448           0,1052   das ganze Restbudget

Ein zaehlerabhaengiges Gate, das ueberall offen steht, ist damit
**selbstsperrend**: Feiner messen macht es nicht besser, sondern messbar
schlechter. Deshalb gibt es hier ``klaerung_lohnt``.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ARTEN",
    "Klaerungskosten",
    "Konflikt",
    "Reglerart",
    "Reglerleiter",
    "Reglervergleich",
    "Stellung",
]


@dataclass(frozen=True, slots=True)
class Reglerart:
    """Ein Regler, den ein Befund schon einmal abgefahren hat.

    ``leiter`` ist genau die Stellungsreihe aus jenem Befund - sie steht seit
    damals im Versuchszaehler und kostet deshalb nichts mehr. Wer davon
    abweicht, rechnet neue Kandidaten.
    """

    schluessel: str
    name: str
    einheit: str
    leiter: str
    befund: int

    def stellungen(self) -> tuple[float, ...]:
        return tuple(sorted(float(x) for x in self.leiter.split(",")))

    def lesen(self, genom) -> float:
        """Auf welcher Stellung dieser Bauplan gerade steht.

        Das Gegenstueck zu ``setzen`` - und die einzige zulaessige Referenz
        fuer ``Reglerleiter.schlaegt_referenz``: Sie stand fest, bevor die
        Leiter gemessen wurde.
        """
        if self.schluessel == "vola":
            return float(genom.sizing.target_vol_pct)
        if self.schluessel == "ziel":
            if not genom.targets:
                raise ValueError(
                    f"'{genom.name}' hat kein Gewinnziel - es gibt keine "
                    "Stellung abzulesen."
                )
            return float(genom.targets[0].rr)
        raise ValueError(f"Unbekannter Regler: {self.schluessel}")

    def setzen(self, genom, wert: float):
        """Denselben Bauplan mit einer anderen Reglerstellung.

        Absichtlich hier und nicht im Aufrufer: Welches Feld ein Regler
        bewegt, gehoert zu seiner Beschreibung. Steht es im Bericht, driftet
        es von der Beschreibung ab.
        """
        if self.schluessel == "vola":
            return genom.model_copy(
                update={
                    "sizing": genom.sizing.model_copy(
                        update={"target_vol_pct": wert}
                    )
                }
            )
        if self.schluessel == "ziel":
            if not genom.targets:
                raise ValueError(
                    f"'{genom.name}' hat kein Gewinnziel - an dem Regler ist "
                    "bei diesem Bauplan nichts zu drehen."
                )
            kopf = genom.targets[0].model_copy(update={"rr": wert})
            return genom.model_copy(update={"targets": [kopf, *genom.targets[1:]]})
        raise ValueError(f"Unbekannter Regler: {self.schluessel}")


#: Die Regler, die ein Befund schon einmal abgefahren hat - mit genau seiner
#: Stellungsreihe. Beide wurden am Perpetual-Punkt gemessen, den Befund 108
#: ueberholt hat.
ARTEN: dict[str, Reglerart] = {
    "vola": Reglerart(
        "vola", "Vola-Ziel", "%", "14,16,19.3,22,25,28,32", 21
    ),
    "ziel": Reglerart(
        "ziel", "Gewinnziel", "R", "10,20,30,50,100,200", 46
    ),
}


@dataclass(frozen=True, slots=True)
class Stellung:
    """Eine gemessene Reglerstellung.

    ``offen`` sind die Namen der Gates, die an dieser Stellung durchfallen -
    das ist die eigentliche Information. ``rendite`` und ``rueckgang`` stehen
    daneben, weil sie erklaeren, *warum* ein Gate faellt; entschieden wird
    nach Gates, nie nach Rendite.
    """

    wert: float
    trades: int
    rendite: float
    rueckgang: float
    bestanden: int
    gesamt: int
    offen: tuple[str, ...] = ()
    dsr: float | None = None

    def __post_init__(self) -> None:
        if self.gesamt <= 0:
            raise ValueError("Eine Stellung ohne Gates ist keine Messung.")
        if not 0 <= self.bestanden <= self.gesamt:
            raise ValueError(
                f"{self.bestanden} von {self.gesamt} bestandenen Gates ergibt "
                "keinen Sinn."
            )
        if len(self.offen) > self.gesamt - self.bestanden:
            raise ValueError(
                f"{len(self.offen)} offene Gates passen nicht zu "
                f"{self.bestanden} von {self.gesamt} bestandenen."
            )

    @property
    def alles_haelt(self) -> bool:
        return self.bestanden == self.gesamt

    def haelt(self, gate: str) -> bool:
        """Haelt dieses Gate an dieser Stellung?"""
        return gate not in self.offen

    def als_zeile(self) -> str:
        return (
            f"{self.wert:>6.1f} {self.trades:>6} {self.rendite:>7.2f}% "
            f"{self.rueckgang:>7.2f}% "
            + (f"{self.dsr:>7.4f} " if self.dsr is not None else "")
            + f"{self.bestanden:>3}/{self.gesamt}"
            + (f"  {', '.join(self.offen)}" if self.offen else "")
        )


@dataclass(frozen=True, slots=True)
class Konflikt:
    """Zwei Gates, die sich ueber den Regler ausschliessen.

    ``unten`` haelt nur bei kleinen Werten, ``oben`` erst bei grossen. Zwischen
    ``letzte_unten`` und ``erste_oben`` faellt mindestens eines von beiden.

    ``dazwischen`` sind die Sprossen, die in diesem Bereich tatsaechlich
    gemessen wurden - an ihnen fallen beide. Ist die Liste leer, sind die
    beiden Sprossen Nachbarn, und ueber den Bereich dazwischen ist nichts
    bekannt ausser seiner Breite.
    """

    unten: str
    oben: str
    letzte_unten: float
    erste_oben: float
    dazwischen: tuple[float, ...] = ()

    @property
    def luecke(self) -> float:
        """Die Breite des Bereichs, in dem eines von beiden faellt."""
        return self.erste_oben - self.letzte_unten

    @property
    def benachbart(self) -> bool:
        """Liegen die beiden Sprossen direkt nebeneinander?

        Das heisst *so eng, wie diese Leiter gemessen hat* - und nicht, dass
        dazwischen nichts liegt. Ein stetiger Regler laesst sich immer weiter
        unterteilen.
        """
        return not self.dazwischen

    def als_zeile(self) -> str:
        kopf = (
            f"{self.unten} haelt bis {self.letzte_unten:.1f}, {self.oben} ab "
            f"{self.erste_oben:.1f}"
        )
        if self.benachbart:
            return (
                f"{kopf} - benachbarte Sprossen, dazwischen ist nichts gemessen "
                f"({self.luecke:.1f} breit)."
            )
        werte = ", ".join(f"{w:.1f}" for w in self.dazwischen)
        return f"{kopf} - dazwischen gemessen: {werte}, dort faellt beides."


@dataclass(frozen=True, slots=True)
class Klaerungskosten:
    """Was es kostet, eine Luecke zwischen zwei Sprossen zu schliessen.

    Gemessen, nicht geschaetzt: ``dsr_danach`` ist der Deflated Sharpe des
    **bestehenden** Kandidaten bei erhoehtem Zaehlerstand - also das, was die
    zusaetzlichen Hypothesen an der Huerde anrichten, bevor ueberhaupt ein
    Ergebnis vorliegt.
    """

    stellungen: int
    versuche_jetzt: int
    dsr_jetzt: float
    dsr_danach: float
    schwelle: float = 0.95

    @property
    def preis(self) -> float:
        """Was die Klaerung am Deflated Sharpe kostet. Negativ = sie kostet."""
        return self.dsr_danach - self.dsr_jetzt

    @property
    def versuche_danach(self) -> int:
        return self.versuche_jetzt + self.stellungen

    @property
    def luecke_danach(self) -> float:
        return self.schwelle - self.dsr_danach

    def als_zeile(self) -> str:
        return (
            f"{self.stellungen} Stellungen kosten {self.stellungen} Versuche "
            f"({self.versuche_jetzt} -> {self.versuche_danach}) und den "
            f"Deflated Sharpe {self.dsr_jetzt:.4f} -> {self.dsr_danach:.4f} "
            f"({self.preis:+.4f})."
        )


@dataclass(frozen=True, slots=True)
class Reglerleiter:
    """Ein Regler, ueber mehrere Stellungen abgefahren.

    Siehe den Modulkopf: **absichtlich ohne** eine Methode, die die beste
    Stellung zurueckgibt.
    """

    name: str
    stellungen: tuple[Stellung, ...] = ()

    @property
    def sortiert(self) -> tuple[Stellung, ...]:
        return tuple(sorted(self.stellungen, key=lambda s: s.wert))

    def fenster(self) -> tuple[Stellung, ...]:
        """Stellungen, an denen **alles** haelt. Leer heisst: der Regler ist zu."""
        return tuple(s for s in self.sortiert if s.alles_haelt)

    def je_offen(self) -> tuple[str, ...]:
        """Jedes Gate, das an irgendeiner Stellung offen stand."""
        gesehen: list[str] = []
        for s in self.sortiert:
            for g in s.offen:
                if g not in gesehen:
                    gesehen.append(g)
        return tuple(gesehen)

    def immer_offen(self) -> tuple[str, ...]:
        """Gates, die an **jeder** Stellung offen stehen.

        Das ist die entscheidende Groesse: Ein solches Gate kann der Regler
        nicht schliessen, und keine Zwischenstellung aendert daran etwas.
        """
        if not self.stellungen:
            return ()
        return tuple(
            g for g in self.je_offen() if all(not s.haelt(g) for s in self.stellungen)
        )

    def haltebereich(self, gate: str) -> tuple[float, float] | None:
        """Kleinste und groesste Stellung, an der ein Gate haelt.

        Das ist eine Spanne, keine Aussage ueber die Sprossen dazwischen -
        dafuer gibt es ``haelt_durchgehend``. ``None``, wenn es nirgends haelt.
        """
        werte = [s.wert for s in self.sortiert if s.haelt(gate)]
        return (min(werte), max(werte)) if werte else None

    def haelt_durchgehend(self, gate: str) -> bool:
        """Haelt das Gate an jeder Sprosse seiner Spanne - oder mit Loechern?

        Ein Gate mit Loechern taugt nicht fuer die Konfliktrechnung: Seine
        Spanne sagt dann mehr, als gemessen wurde.
        """
        bereich = self.haltebereich(gate)
        if bereich is None:
            return False
        lo, hi = bereich
        return all(s.haelt(gate) for s in self.sortiert if lo <= s.wert <= hi)

    def konflikte(self) -> tuple[Konflikt, ...]:
        """Paare von Gates, deren Haltespannen sich nicht ueberschneiden.

        Beide muessen irgendwo halten - ein Gate, das nirgends haelt, steht in
        ``immer_offen`` und ist kein Konflikt, sondern eine Sperre. Gates mit
        Loechern in der Spanne bleiben aussen vor; bei ihnen waere der
        Vergleich der Spannengrenzen eine Behauptung ueber Ungemessenes.
        """
        werte = [s.wert for s in self.sortiert]
        bereiche = {
            g: b
            for g in self.je_offen()
            if self.haelt_durchgehend(g) and (b := self.haltebereich(g)) is not None
        }
        aus: list[Konflikt] = []
        namen = list(bereiche)
        for i, a in enumerate(namen):
            for b in namen[i + 1 :]:
                (a_min, a_max), (b_min, b_max) = bereiche[a], bereiche[b]
                if a_max < b_min:
                    unten, oben, lo, hi = a, b, a_max, b_min
                elif b_max < a_min:
                    unten, oben, lo, hi = b, a, b_max, a_min
                else:
                    continue
                mitte = tuple(w for w in werte if lo < w < hi)
                aus.append(Konflikt(unten, oben, lo, hi, mitte))
        return tuple(aus)

    def hub(self) -> float | None:
        """Wie weit der Regler den Deflated Sharpe ueber die ganze Leiter bewegt.

        Das ist die Groesse, die Befund 21 als *"Grund eins"* ausgerechnet hat
        und die dort nur im Text stand: Ein Regler, der den Wert um 0,024
        bewegt, waehrend 0,159 fehlen, ist keine knappe Sache, sondern eine
        Schranke. ``None``, solange keine Sprosse ihren Wert mitbringt.
        """
        werte = [s.dsr for s in self.stellungen if s.dsr is not None]
        return max(werte) - min(werte) if len(werte) >= 2 else None

    def reserve(self, schwelle: float = 0.95) -> float | None:
        """Was der besten gemessenen Sprosse zur Schwelle fehlt.

        **Das ist keine Stellungswahl.** Die Sprosse mit dem hoechsten Wert
        auszurechnen sagt, wie weit der Regler ueberhaupt traegt; sie
        auszuwaehlen waere Suche. Deshalb kommt hier eine Zahl zurueck und
        keine ``Stellung``.
        """
        werte = [s.dsr for s in self.stellungen if s.dsr is not None]
        return schwelle - max(werte) if werte else None

    def schlaegt_referenz(self, referenz: float) -> tuple[Stellung, ...]:
        """Sprossen, die die Referenzstellung in **jeder** Hinsicht schlagen.

        Dieselbe Form wie ``decke.Fensterlage.wechsel_begruendbar`` und aus
        demselben Grund: Sich die hoechste Sprosse auszusuchen waere Suche.
        Zulaessig ist nur der Vergleich gegen eine Stellung, die vorher schon
        feststand - hier die, auf der der Kandidat ohnehin sitzt.

        *In jeder Hinsicht* heisst: kein Gate weniger und kein kleinerer
        Deflated Sharpe, und mindestens eines davon echt besser. Ein Tausch -
        ein Gate mehr, dafuer weniger Deflated Sharpe - zaehlt nicht, sonst
        waere die Wahl wieder Geschmackssache.
        """
        anker = next((s for s in self.stellungen if s.wert == referenz), None)
        if anker is None or anker.dsr is None:
            return ()
        aus = []
        for s in self.sortiert:
            if s is anker or s.dsr is None:
                continue
            nicht_schlechter = s.bestanden >= anker.bestanden and s.dsr >= anker.dsr
            echt_besser = s.bestanden > anker.bestanden or s.dsr > anker.dsr
            if nicht_schlechter and echt_besser:
                aus.append(s)
        return tuple(aus)

    def traegt_der_regler(self, schwelle: float = 0.95) -> bool | None:
        """Reicht der ganze Regelweg ueberhaupt bis zur Schwelle?

        Nein, wenn der Hub kleiner ist als die Reserve: Dann muesste der
        Regler den Wert weiter bewegen, als er ihn ueber seine ganze Spanne
        ueberhaupt bewegt. ``None``, wenn nichts gemessen ist.
        """
        hub, rest = self.hub(), self.reserve(schwelle)
        if hub is None or rest is None:
            return None
        return hub >= rest

    def selbstsperrend(
        self, zaehlerabhaengig: tuple[str, ...] = ("Deflated Sharpe",)
    ) -> tuple[str, ...]:
        """Gates, die ueberall offen stehen **und** am Versuchszaehler haengen.

        Bei ihnen ist feiner Messen kein Weg zur Klaerung, sondern ein Weg nach
        unten: Jede zusaetzliche Stellung erhoeht den Zaehler und senkt damit
        den Wert, unabhaengig davon, was sie ergibt.
        """
        return tuple(g for g in self.immer_offen() if g in zaehlerabhaengig)

    def klaerung_lohnt(self) -> bool:
        """Kann das Messen der Zwischenstellungen das Ergebnis noch aendern?

        Nein in zwei Faellen: Es gibt schon ein Fenster - dann ist die Frage
        beantwortet. Oder ein Gate steht an jeder Sprosse offen - dann kann
        keine Zwischenstellung eines oeffnen, und wer trotzdem misst, zahlt
        Versuche fuer ein Ergebnis, das schon feststeht.

        Sonst ja: Ein Fenster zwischen zwei Sprossen ist nicht ausgeschlossen,
        solange jedes Gate irgendwo haelt.
        """
        if not self.stellungen:
            return False
        return not self.fenster() and not self.immer_offen()

    def urteil(self) -> str:
        if not self.stellungen:
            return f"'{self.name}' ist nicht gemessen - dazu ist nichts zu sagen."
        offen = self.fenster()
        if offen:
            werte = ", ".join(f"{s.wert:.1f}" for s in offen)
            return (
                f"**'{self.name}' hat ein Fenster**: bei {werte} halten alle "
                f"{offen[0].gesamt} Gates. Das ist zu pruefen und nicht zu "
                f"glauben - eine einzelne Stellung, die besteht, ist noch kein "
                f"Kandidat."
            )
        sperren = self.immer_offen()
        if sperren:
            selbst = self.selbstsperrend()
            zusatz = (
                f" {', '.join(selbst)} haengt zudem am Versuchszaehler: "
                f"Nachmessen senkt den Wert, statt ihn zu heben."
                if selbst
                else ""
            )
            hub, rest = self.hub(), self.reserve()
            if hub is not None and rest is not None and not self.traegt_der_regler():
                zusatz += (
                    f" Und der Regler traegt nicht so weit: Er bewegt den "
                    f"Deflated Sharpe ueber den ganzen Weg um {hub:.4f}, "
                    f"waehrend {rest:.4f} fehlen."
                )
            return (
                f"**'{self.name}' ist zu.** {', '.join(sperren)} steht an jeder "
                f"der {len(self.stellungen)} Stellungen offen - daran kann keine "
                f"Zwischenstellung etwas aendern.{zusatz}"
            )
        streit = self.konflikte()
        if streit:
            return (
                f"**'{self.name}' ist ungeklaert.** "
                f"{' '.join(k.als_zeile() for k in streit)} Ein stetiger Regler "
                f"laesst sich immer feiner unterteilen; jede Unterteilung kostet "
                f"Versuche und hebt die Huerde, bevor ein Ergebnis vorliegt."
            )
        return (
            f"'{self.name}' hat kein Fenster, aber auch keinen Konflikt - jedes "
            f"Gate haelt irgendwo, nur nie alle zugleich. Das ist kein "
            f"geschlossener Weg, sondern eine unvollstaendige Messung."
        )


@dataclass(frozen=True, slots=True)
class Reglervergleich:
    """Derselbe Regler an zwei Betriebspunkten.

    Der wiederkehrende Fall seit Befund 112: Eine Aussage wurde am
    Perpetual-Punkt gemessen, der massgebliche Punkt ist seit Befund 108 der
    Spot-Punkt, und die Zahlen dahinter sind andere. Die Frage ist dann nicht
    "welche Tabelle stimmt", sondern: **haelt der Schluss trotzdem?**
    """

    alt: Reglerleiter
    neu: Reglerleiter

    def schluss_haelt(self) -> bool:
        """Kommen beide Punkte zum selben Ergebnis - Fenster oder keins?"""
        return bool(self.alt.fenster()) == bool(self.neu.fenster())

    def verschoben(self) -> tuple[tuple[float, int, int], ...]:
        """Stellungen, an denen sich die Zahl bestandener Gates geaendert hat."""
        vorher = {s.wert: s for s in self.alt.stellungen}
        return tuple(
            (s.wert, vorher[s.wert].bestanden, s.bestanden)
            for s in self.neu.sortiert
            if s.wert in vorher and vorher[s.wert].bestanden != s.bestanden
        )

    def urteil(self) -> str:
        if not self.alt.stellungen or not self.neu.stellungen:
            return "Ein Betriebspunkt ist nicht gemessen - der Vergleich fehlt."
        bewegt = self.verschoben()
        tabelle = (
            f"{len(bewegt)} von {len(self.neu.stellungen)} Stellungen stehen "
            f"anders da"
            if bewegt
            else "keine Stellung steht anders da"
        )
        if not self.schluss_haelt():
            reicher = self.neu if self.neu.fenster() else self.alt
            return (
                f"**Der Schluss haelt nicht.** '{reicher.name}' hat ein "
                f"Fenster, der andere Punkt nicht - {tabelle}. Der aeltere "
                f"Befund gehoert korrigiert."
            )
        return (
            "**Der Schluss haelt** - an beiden Punkten "
            + ("gibt es ein Fenster" if self.neu.fenster() else "gibt es keins")
            + f". Die Tabelle darunter ist aber eine andere: {tabelle}."
        )
