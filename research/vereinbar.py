"""Sind zwei Schwellen ueberhaupt gleichzeitig erfuellbar?

Die Behauptung, die nie gemessen wurde
--------------------------------------
In ``research/stand.py`` steht seit langem ein Satz ueber die Mindestrendite
von 15 % im Jahr:

    *"Sie steht im Konflikt mit der Rueckgangsgrenze: Was die eine verlangt,
    reisst die andere."*

Das ist eine **Behauptung**. Sie klingt plausibel, und genau deshalb hat sie
monatelang unbeanstandet dort gestanden. Zwei Messpunkte stuetzen sie
inzwischen - der Spitzenkandidat schafft 13,5 % bei 10,6 % Rueckgang, der
Ausbruch aus Befund 56 schafft 16,5 % bei 21,8 % -, aber zwei Punkte sind
kein Beleg, sondern zwei Punkte.

**Und sie gilt nur am Perpetual-Punkt** (Befund 281). Dort haelt ueber zehn
Stellungen keine beide Schwellen; am Spot-Punkt, wo das Funding wegfaellt,
halten drei von sechs beide zugleich. Der Konflikt ist damit eine Eigenschaft
der Finanzierungskosten und nicht der Strategie - gegen die Gates gewonnen
ist damit nichts, denn dort uebernimmt das schlechteste Jahr die Rolle, die
vorher der Rueckgang hatte.

Was hier gefragt wird - und was ausdruecklich nicht
---------------------------------------------------
Gefragt wird: **Existiert eine Einstellung, in der beide Schwellen zugleich
gelten?** Ja oder nein, und wenn nein, wie weit es fehlt.

**Nicht** gefragt wird, welche Einstellung die meisten Gates besteht. Der
Unterschied ist der ganze Sinn dieses Moduls. ``research/seeds.py`` haelt zum
Vola-Ziel des Spitzenkandidaten ausdruecklich fest:

    *"Der Wert wird trotzdem nicht nachgezogen. Die 19,3 auf 16 zu senken,
    weil dort wieder 8 von 11 stehen, waere eine Anpassung an die Gates - und
    genau die Sorte Entscheidung, gegen die die ganze Zulassungsstrecke
    gebaut ist."*

Das gilt hier weiter. Ein Treffer waere ein Befund ueber die **Schwellen**,
nicht eine Empfehlung fuer den Kandidaten - deshalb nennt ``urteil`` bei einem
Treffer zwar die Zahl, aber nie einen Betriebspunkt zum Uebernehmen. Wem die
Antwort gehoert, steht auch schon fest: Die Mindestrendite ist laut
``stand.py`` eine wirtschaftliche Entscheidung des Nutzers, keine
statistische.

Warum ein Groessenregler die saubere Achse ist
----------------------------------------------
Er skaliert jede Position mit demselben Faktor und laesst die Qualitaet je
Trade unveraendert (Befund 30). Rendite und Rueckgang wachsen also beide mit
ihm, und die Frage wird zu einer geometrischen: Geht die Kurve durch das
erlaubte Rechteck, oder laeuft sie daran vorbei?
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from itertools import pairwise
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Schwelle:
    """Eine Bedingung an eine gemessene Kennzahl."""

    name: str
    kennzahl: str
    grenze: float
    mindestens: bool
    """``True``: der Wert muss die Grenze erreichen. ``False``: er darf sie
    nicht ueberschreiten."""

    def erfuellt(self, wert: float | None) -> bool:
        if wert is None:
            return False
        return wert >= self.grenze if self.mindestens else wert <= self.grenze

    def abstand(self, wert: float | None) -> float | None:
        """Wie weit der Wert von der Grenze entfernt ist. Negativ = gerissen."""
        if wert is None:
            return None
        return wert - self.grenze if self.mindestens else self.grenze - wert

    def beurteile(self, wert: float | None) -> str | None:
        """Was zu dieser Schwelle zu sagen ist - ``None``, wenn erfuellt.

        **Befund 309.** ``erfuellt(None)`` ist ``False``, und das ist richtig:
        Ein Wert, den es nicht gibt, erfuellt nichts. Falsch war, daraus in
        der Tabelle *"Schlechtestes Jahr fehlt"* zu machen - als waere
        gemessen worden und die Schwelle gerissen. Am Spot-Punkt stand das
        an **allen sechs** Stellungen, und keine davon hatte den Wert.

        "Nicht gemessen" und "gerissen" sind zwei verschiedene Auskuenfte.
        Die eine sagt etwas ueber den Kandidaten, die andere ueber die Akte.
        """
        if wert is None:
            return f"{self.name} nicht gemessen"
        if self.erfuellt(wert):
            return None
        return f"{self.name} " + ("fehlt" if self.mindestens else "reisst")

    def __str__(self) -> str:
        zeichen = ">=" if self.mindestens else "<="
        return f"{self.name} {zeichen} {self.grenze:g}"


#: Die beiden Schwellen aus ``stand.py``, ueber die der Satz dort geht.
RENDITE = Schwelle("Rendite", "cagr", 15.0, mindestens=True)
RUECKGANG = Schwelle("Rueckgang", "rueckgang", 12.0, mindestens=False)

#: Die dritte, seit Befund 93. Sie gehoert dazu, sobald ueber Mischungen
#: gerechnet wird: Eine Beimischung senkt Rendite **und** Risiko, und ob
#: dabei etwas uebrig bleibt, entscheidet sich an allen drei Grenzen
#: zugleich - nicht an zweien.
SCHLECHTESTES_JAHR = Schwelle(
    "Schlechtestes Jahr", "schlechtestes_jahr", -10.0, mindestens=True
)


@dataclass(frozen=True, slots=True)
class Messpunkt:
    stellung: float
    werte: dict[str, float]

    betriebspunkt: str | None = None
    """Mit Hebel und Funding gemessen, oder ohne - ``None`` heisst **nicht
    vermerkt**.

    Seit Befund 242 schreibt ``cli machbarkeit`` den Punkt in den Bericht.
    Aeltere Berichte haben das Feld nicht, und dort ist er nicht zu erraten:
    Der Vorgabewert war der Perpetual-Punkt, aber eine Vorgabe ist keine
    Messung (Befund 280).
    """

    gemessen: str = ""
    """Der Dateiname des Berichts ohne Endung, aus dem dieser Punkt stammt -
    Befund 334.

    Bei allen Schreibern ein Zeitstempel, deshalb sortiert er wie ein Datum.
    Leer heisst "nicht zu ermitteln", und dann steht auch kein Alter da: eine
    geratene Angabe waere schlimmer als keine (wie in ``berichtslage``).
    """

    def wert(self, kennzahl: str) -> float | None:
        roh = self.werte.get(kennzahl)
        return float(roh) if roh is not None else None

    def alter(self, heute: date | None = None) -> int | None:
        """Wie viele Tage alt die Messung dieses Punktes ist."""
        try:
            gemacht = date.fromisoformat(self.gemessen[:10])
        except ValueError:
            return None
        return ((heute or date.today()) - gemacht).days


#: Ergebnis von ``lade``: die Punkte und die, die ausgelassen wurden.
@dataclass(frozen=True, slots=True)
class Vorrat:
    """Was an Punkten dasteht - und was aus welchem Grund fehlt.

    Eine stille Auswahl waere hier besonders teuer: ``Vereinbarkeit`` faellt
    ein Ja-Nein-Urteil ueber *alle* gemessenen Stellungen, und wenn welche
    fehlen, gilt es fuer weniger als es behauptet.
    """

    punkte: list[Messpunkt] = field(default_factory=list)
    ohne_vermerk: int = 0
    """Punkte aus Berichten ohne Betriebspunkt - ausgelassen, wenn nach einem
    bestimmten gefragt wurde."""

    fremder_punkt: dict[str, int] = field(default_factory=dict)
    """Punkte anderer Betriebspunkte, je Punkt gezaehlt."""

    def altersatz(self, heute: date | None = None) -> str:
        """Wie alt die Messungen sind, auf denen das Urteil steht - Befund 334.

        **Warum das hier hingehoert und nicht nur in die Berichtslage.** Befund
        324 hat das Alter in ``berichtslage`` nachgetragen, weil ein Datum unter
        sieben anderen sich nicht wie eine Warnung liest. Diese Tabelle ist der
        engere Fall: An ihr haengt eine offene **Geschaeftsentscheidung** - die
        Mindestrendite von 15 % -, und sie stand ohne jede Altersangabe da.

        Was der Satz nicht sagt, ist "die Zahlen sind falsch". Er sagt, wie weit
        der Schluss traegt. Nachgesehen (334): Der juengste Machbarkeitsbericht
        ist vom 14.09., und ``_combine`` hat sich am 20.09. geaendert (Befund
        315) - die Funktion, aus deren Kurve Rendite und Rueckgang gelesen
        werden. 315 hat gegengerechnet, dass **keine Zahl sich bewegt**; ohne
        diesen Satz waere die Tabelle nicht zu benutzen gewesen, und dass er
        existiert, konnte man ihr nicht ansehen.
        """
        alter = [a for p in self.punkte if (a := p.alter(heute)) is not None]
        if not alter:
            return ""
        jung, alt = min(alter), max(alter)
        spanne = (
            f"{jung} Tage alt"
            if jung == alt
            else f"{jung} bis {alt} Tage alt"
        )
        return (
            f"Die Stellungen sind {spanne}. Jede Messung beschreibt den Code "
            f"**von ihrem Datum** - was seither an der Kapitalkurve geaendert "
            f"wurde, steht nicht darin (Befund 315/324/334).{self._quellsatz()}"
        )

    @property
    def quellen(self) -> tuple[str, ...]:
        """Aus wie vielen Berichten die Leiter zusammengesetzt ist - Befund 341.

        Das Alter allein verschweigt das Entscheidende: Sechs Stellungen, alle
        gleich alt, sehen nach sechs Messungen aus. Am Spot-Punkt sind es
        **eine** Datei - der einzige Machbarkeitsbericht, der einen
        Betriebspunkt vermerkt.
        """
        return tuple(
            sorted({p.gemessen for p in self.punkte if p.gemessen})
        )

    @property
    def einzelquelle(self) -> bool:
        """Haengt die ganze Leiter an einem einzigen Bericht?"""
        return len(self.quellen) == 1 and len(self.punkte) > 1

    def _quellsatz(self) -> str:
        """Und woraus die Leiter besteht - Befund 341."""
        if not self.einzelquelle:
            return ""
        return (
            f"\n\n**Und sie stehen alle in einer Datei.** Die {len(self.punkte)} "
            f"Stellungen kommen aus '{self.quellen[0]}' - dem einzigen Bericht "
            f"dieses Betriebspunkts. Gleiches Alter heisst hier also nicht "
            f"'gleich frisch gemessen', sondern 'einmal gemessen'. Faellt "
            f"diese Datei weg, meldet die Tabelle nichts, und die offene "
            f"Entscheidung steht ohne ihre Zahlen da."
        )

    def hinweis(self) -> str:
        teile = []
        if self.ohne_vermerk:
            teile.append(
                f"{self.ohne_vermerk} Stellungen stammen aus Berichten **ohne "
                f"vermerkten Betriebspunkt** und sind ausgelassen - vor Befund "
                f"242 wurde er nicht geschrieben, und die Vorgabe von damals "
                f"ist keine Messung"
            )
        for punkt, zahl in sorted(self.fremder_punkt.items()):
            teile.append(f"{zahl} Stellungen gehoeren zu '{punkt}'")
        return "; ".join(teile)


def _passt(vermerkt: str, gefragt: str) -> bool:
    """Gehoert ein vermerkter Punkt zu dem, nach dem gefragt wurde?

    ``_betriebspunkt`` in ``cli`` schreibt *"Spot (kein Hebel, kein
    Funding)"* oder *"Perpetual (Hebel 3, mit Funding)"* - das erste Wort ist
    der Punkt, die Klammer seine Einzelheiten. Verglichen wird deshalb das
    erste Wort: Wer nach "Spot" fragt, will nicht wissen, wie die Klammer
    formuliert war, und ein Aufrufer soll die Zeichenkette nicht nachbauen
    muessen (Befund 280).
    """
    return vermerkt.split(" ", 1)[0].casefold() == gefragt.split(" ", 1)[0].casefold()


#: Kennzahlen, die der Bericht nur im **Gate** fuehrt, nicht in ``kennzahlen``.
#:
#: **Befund 310.** ``kennzahlen`` traegt trades, cagr, rueckgang,
#: sharpe_je_trade, schiefe, woelbung - und kein schlechtestes Jahr. Der Wert
#: steht trotzdem in derselben Datei, unter ``gates['Schlechtestes Jahr']``,
#: mit Schwelle und Urteil daneben. ``vereinbar`` hat an der falschen Stelle
#: gesucht und ``nan`` gemeldet; Befund 309 hat daraufhin die Auskunft
#: berichtigt und die **Ursache** geraten - die Kurve sei zu kurz fuer ein
#: Jahresfenster. Sie ist es nicht.
AUS_DEM_GATE: dict[str, str] = {"schlechtestes_jahr": "Schlechtestes Jahr"}


def _werte_des_punktes(punkt: dict) -> dict[str, float]:
    """Die Kennzahlen eines Berichtspunkts - aus beiden Stellen.

    Zuerst ``kennzahlen``; was dort fehlt und im Gate steht, kommt von dort.
    Die Reihenfolge ist Absicht: ``kennzahlen`` ist die Quelle, das Gate die
    Ergaenzung, und wo beide etwas sagen, gewinnt die Quelle.
    """
    werte = {
        k: float(v)
        for k, v in (punkt.get("kennzahlen") or {}).items()
        if v is not None
    }
    gates = punkt.get("gates") or {}
    for kennzahl, gate in AUS_DEM_GATE.items():
        if kennzahl in werte:
            continue
        roh = (gates.get(gate) or {}).get("wert")
        if roh is not None:
            werte[kennzahl] = float(roh)
    return werte


def lade(
    ordner: Path | str,
    *,
    regler: str = "Vola-Ziel",
    betriebspunkt: str | None = None,
) -> Vorrat:
    """Die Punkte eines Reglers aus den Machbarkeitsberichten.

    Mehrere Berichte desselben Reglers koennen aus verschiedenen Staenden
    stammen - die Aufwaermphase des Compilers wurde einmal korrigiert, und
    Berichte davor tragen andere Zahlen. Deshalb wird **nicht** stumpf
    zusammengelegt: Bei gleicher Stellung gewinnt der juengste Bericht.
    Aeltere stillschweigend mitzumitteln hiesse, zwei Messstaende zu einer
    Kurve zu verruehren.

    **Derselbe Satz gilt fuer den Betriebspunkt** (Befund 280). Eine Leiter
    aus Spot- und Perpetual-Stellungen ist keine Leiter: Bei gleicher
    Stellung ueberschreibt die eine die andere, und das Urteil stuende dann
    auf einer Mischung. ``betriebspunkt`` waehlt deshalb aus, und was dabei
    wegfaellt, steht in ``Vorrat.hinweis``.
    """
    gefunden: dict[float, Messpunkt] = {}
    ohne_vermerk = 0
    fremd: dict[str, int] = {}
    for datei in sorted(Path(ordner).glob("*.json")):
        try:
            daten = json.loads(datei.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        gemessen = daten.get("regler") or daten.get("analyse", {}).get("regler")
        if gemessen != regler:
            continue
        punkt_der_datei = daten.get("betriebspunkt")
        punkte = daten.get("punkte") or daten.get("analyse", {}).get("punkte") or []
        gueltig = [p for p in punkte if p.get("kennzahlen")]
        if betriebspunkt is not None:
            if punkt_der_datei is None:
                ohne_vermerk += len(gueltig)
                continue
            if not _passt(punkt_der_datei, betriebspunkt):
                fremd[punkt_der_datei] = fremd.get(punkt_der_datei, 0) + len(gueltig)
                continue
        for punkt in gueltig:
            stellung = float(punkt.get("stellung", 0.0))
            gefunden[stellung] = Messpunkt(
                stellung=stellung,
                werte=_werte_des_punktes(punkt),
                betriebspunkt=punkt_der_datei,
                gemessen=datei.stem,
            )
    return Vorrat(
        punkte=sorted(gefunden.values(), key=lambda p: p.stellung),
        ohne_vermerk=ohne_vermerk,
        fremder_punkt=fremd,
    )


def kennzahlen_der_kurve(kurve, *, monate: float) -> dict[str, float]:
    """Rendite, Rueckgang und schlechtestes Jahr einer Kapitalkurve.

    An **einer** Stelle, weil sonst der Reglerpfad und der Mischpfad zwei
    Umsetzungen derselben drei Groessen haetten - genau die Sorte Abweichung,
    die in diesem Projekt schon fuenfmal aufgetreten ist.
    """
    import numpy as np

    werte = np.asarray(kurve, dtype=float)
    if len(werte) < 3 or monate <= 0 or werte[0] <= 0:
        return {}
    hoch = np.maximum.accumulate(werte)
    aus = {
        "cagr": (float(werte[-1] / werte[0]) ** (12.0 / monate) - 1.0) * 100.0,
        "rueckgang": float(np.max((hoch - werte) / hoch) * 100.0),
    }
    spanne = int(len(werte) * 12.0 / monate)
    if 2 <= spanne < len(werte):
        aus["schlechtestes_jahr"] = float(
            np.min(werte[spanne:] / werte[:-spanne] - 1.0) * 100.0
        )
    return aus


def mischpunkte(
    basis, partner, *, monate: float, gewichte=None
) -> list[Messpunkt]:
    """Die Kennzahlen einer Mischung aus zwei Kapitalkurven, je Gewicht.

    Das Gewicht ist hier die **Stellung** - dieselbe Achse wie beim
    Groessenregler, nur mit anderer Bedeutung: 0,0 ist der reine Bestand,
    1,0 der reine Partner.

    Gemischt werden die **Periodenrenditen**, nicht die Kurven. Zwei Kurven
    zu mitteln hiesse, den Zinseszins zweimal zu zaehlen; ein Portfolio
    verteilt dagegen das Kapital und teilt sich damit die Renditen.
    """
    import numpy as np

    a = np.asarray(basis, dtype=float)
    b = np.asarray(partner, dtype=float)
    if len(a) != len(b) or len(a) < 3:
        return []
    ra = np.diff(a) / a[:-1]
    rb = np.diff(b) / b[:-1]
    stufen = [0.0, 0.25, 0.5, 0.75, 1.0] if gewichte is None else list(gewichte)

    punkte = []
    for w in stufen:
        gemischt = np.concatenate([[1.0], np.cumprod(1.0 + (1 - w) * ra + w * rb)])
        werte = kennzahlen_der_kurve(gemischt, monate=monate)
        if werte:
            punkte.append(Messpunkt(stellung=float(w), werte=werte))
    return punkte


@dataclass(slots=True)
class Vereinbarkeit:
    """Zwei Schwellen, eine Reglerkurve, eine Ja-Nein-Frage."""

    regler: str
    punkte: list[Messpunkt] = field(default_factory=list)
    a: Schwelle = RENDITE
    b: Schwelle = RUECKGANG
    weitere: list[Schwelle] = field(default_factory=list)
    """Zusaetzliche Schwellen, seit Befund 93. ``a`` und ``b`` bleiben, wo
    sie sind - der Reglerfall hat zwei, und eine Umstellung haette jede
    vorhandene Auswertung angefasst, um nichts zu gewinnen."""

    betriebspunkt: str | None = None
    """Unter welchen Handelsbedingungen die Punkte gemessen wurden.

    **Ohne diese Angabe ist das Urteil unvollstaendig** (Befund 280): Befund
    112 hat gemessen, dass der Betriebspunkt entscheidet, welche Gates halten,
    und dieselben zwei Schwellen koennen an einem Punkt vereinbar sein und am
    anderen nicht. ``None`` heisst, dass die Berichte ihn nicht vermerken -
    dann sagt ``urteil`` das, statt einen zu unterstellen.
    """

    @property
    def punkt_name(self) -> str:
        return self.betriebspunkt or "nicht vermerkt"

    @property
    def schwellen(self) -> tuple[Schwelle, ...]:
        return (self.a, self.b, *self.weitere)

    @property
    def ungemessen(self) -> tuple[Schwelle, ...]:
        """Schwellen, zu denen **kein einziger** Punkt einen Wert traegt.

        **Befund 309.** Eine solche Schwelle macht jedes "nicht zugleich
        erfuellbar" unhaltbar: Die Aussage stuende dann auf einer Zahl, die
        es nirgends gibt. Am Spot-Punkt betraf das 'Schlechtestes Jahr' - die
        Kapitalkurven der sechs Berichte sind zu kurz fuer ein Jahresfenster,
        und ``kennzahlen_der_kurve`` laesst den Schluessel dann weg.
        """
        return tuple(
            s
            for s in self.schwellen
            if all(p.wert(s.kennzahl) is None for p in self.punkte)
        )

    @property
    def treffer(self) -> list[Messpunkt]:
        """Punkte, die **alle** Schwellen zugleich erfuellen."""
        return [
            p
            for p in self.punkte
            if all(s.erfuellt(p.wert(s.kennzahl)) for s in self.schwellen)
        ]

    def _fehlbetrag(self, punkt: Messpunkt) -> float | None:
        """Wie viel an allen Schwellen zusammen fehlt. 0 = erfuellt."""
        fehlt = 0.0
        for schwelle in self.schwellen:
            abstand = schwelle.abstand(punkt.wert(schwelle.kennzahl))
            if abstand is None:
                return None
            fehlt += max(0.0, -abstand)
        return fehlt

    @property
    def engste(self) -> Messpunkt | None:
        """Der Punkt, an dem am wenigsten zu beiden Schwellen fehlt."""
        bewertet = [(self._fehlbetrag(p), p) for p in self.punkte]
        moeglich = [(f, p) for f, p in bewertet if f is not None]
        return min(moeglich, key=lambda fp: fp[0])[1] if moeglich else None

    @property
    def luecke(self) -> tuple[Messpunkt, Messpunkt] | None:
        """Das Stellungspaar, zwischen dem der Uebergang liegt.

        Also: der letzte Punkt, der die eine Schwelle noch haelt, und der
        erste, der sie reisst. Dazwischen ist nichts gemessen - und dort
        entscheidet sich die Frage, wenn sie sich ueberhaupt entscheidet.
        """
        geordnet = sorted(self.punkte, key=lambda p: p.stellung)
        for links, rechts in pairwise(geordnet):
            a_links = self.a.erfuellt(links.wert(self.a.kennzahl))
            a_rechts = self.a.erfuellt(rechts.wert(self.a.kennzahl))
            b_links = self.b.erfuellt(links.wert(self.b.kennzahl))
            b_rechts = self.b.erfuellt(rechts.wert(self.b.kennzahl))
            if (not a_links and a_rechts) or (b_links and not b_rechts):
                return links, rechts
        return None

    def tabelle(self) -> str:
        kopf = "".join(f"{s.name[:10]:>11}" for s in self.schwellen)
        zeilen = [f"{'Stellung':>9}{kopf}  Urteil", "-" * (24 + 11 * len(self.schwellen))]
        for p in sorted(self.punkte, key=lambda x: x.stellung):
            werte = ""
            marken = []
            for schwelle in self.schwellen:
                wert = p.wert(schwelle.kennzahl)
                werte += f"{wert if wert is not None else float('nan'):>10.2f}%"
                marke = schwelle.beurteile(wert)
                if marke is not None:
                    marken.append(marke)
            zeilen.append(
                f"{p.stellung:>9g}{werte}  "
                f"{', '.join(marken) or 'alle erfuellt'}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.punkte:
            return "Keine Messpunkte - nichts zu entscheiden."

        benannt = " und ".join(str(s) for s in self.schwellen)
        # **Der Betriebspunkt gehoert in den Satz** (Befund 280). Ohne ihn
        # gilt das Urteil scheinbar immer - gemessen ist es aber unter
        # bestimmten Handelsbedingungen, und die entscheiden mit (Befund 112).
        unter = f" Gemessen am Betriebspunkt '{self.punkt_name}'."
        if self.betriebspunkt is None:
            unter = (
                " **Unter welchen Handelsbedingungen, steht nicht dabei**: "
                "Die Berichte vermerken keinen Betriebspunkt, und die Vorgabe "
                "von damals ist keine Messung."
            )
        if self.treffer:
            stellungen = ", ".join(f"{p.stellung:g}" for p in self.treffer[:4])
            return (
                f"**{benannt} sind vereinbar.** Auf dem Regler "
                f"'{self.regler}' erfuellen {len(self.treffer)} von "
                f"{len(self.punkte)} gemessenen Stellungen beide zugleich "
                f"({stellungen}).\n\n"
                f"Das ist ein Befund ueber die **Schwellen**, keine Empfehlung "
                f"fuer den Kandidaten: Sein Betriebspunkt wird nicht "
                f"nachgezogen, weil dort mehr Gates bestuenden. Genau diese "
                f"Sorte Anpassung ist das, wogegen die Zulassungsstrecke "
                f"gebaut ist - und die uebrigen Gates bleiben ohnehin offen."
                f"{unter}"
            )

        # **Ein Nein ueber eine ungemessene Schwelle ist keins** (Befund 309).
        # Vorher stand hier "nicht zugleich erfuellbar", waehrend der Grund
        # war, dass 'Schlechtestes Jahr' in keinem der sechs Berichte steht.
        if self.ungemessen:
            fehlen = ", ".join(s.name for s in self.ungemessen)
            uebrig = [s for s in self.schwellen if s not in self.ungemessen]
            rest = Vereinbarkeit(
                regler=self.regler, punkte=self.punkte,
                a=uebrig[0], b=uebrig[1] if len(uebrig) > 1 else uebrig[0],
                weitere=uebrig[2:], betriebspunkt=self.betriebspunkt,
            ).urteil() if len(uebrig) >= 2 else ""
            return (
                f"**Kein Urteil ueber {fehlen}.** Keiner der "
                f"{len(self.punkte)} Berichte traegt diesen Wert - das ist "
                f"eine Luecke in der Akte und kein Befund ueber den "
                f"Kandidaten. Wer daraus 'nicht erfuellbar' liest, liest "
                f"eine Zahl, die es nirgends gibt.{unter}"
                + (f"\n\nUeber die uebrigen Schwellen:\n\n{rest}" if rest else "")
            )

        eng = self.engste
        luecke = self.luecke
        wo = ""
        if luecke is not None:
            links, rechts = luecke
            wo = (
                f" Der Uebergang liegt zwischen {links.stellung:g} und "
                f"{rechts.stellung:g}."
            )
        naeher = ""
        if eng is not None:
            fehlt = self._fehlbetrag(eng)
            gemessen = ", ".join(
                f"{s.name} {eng.wert(s.kennzahl):.2f} %" for s in self.schwellen
            )
            naeher = (
                f" Am wenigsten fehlt bei {eng.stellung:g}: {gemessen} - "
                f"zusammen {fehlt:.2f} Punkte zu wenig."
            )
        return (
            f"**{benannt} sind auf diesem Regler nicht zugleich "
            f"erfuellbar.** Keine der {len(self.punkte)} gemessenen Stellungen "
            f"haelt alle.{wo}{naeher}\n\n"
            f"Damit ist der Satz aus stand.py beziffert statt behauptet. Was "
            f"daraus folgt, ist eine wirtschaftliche Entscheidung und keine "
            f"statistische - sie liegt beim Nutzer.{unter}"
        )
