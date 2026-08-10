"""Gibt es ueberhaupt eine Reglerstellung, bei der alle Gates zugleich halten?

Wozu
----
Der Spitzenkandidat steht bei 8 von 11. Zehn Richtungen sind inzwischen
gemessen und widerlegt - mehr Maerkte, mehr Historie, feinere Kerzen, ATR-Stops,
Shorts, Ensemble, News-Overlay. Uebrig bleibt der eine freie Regler, den die
Regel noch hat: das Vola-Ziel.

Bevor man daran dreht, lohnt die Frage eine Stufe darueber: **Kann dieser
Regler das Ergebnis ueberhaupt erreichen?** Sie ist nicht dieselbe wie "welche
Stellung ist die beste", und sie ist billiger zu beantworten - eine einzige
Abtastung mit vollstaendiger Gate-Auswertung genuegt.

Drei Ausgaenge, und sie bedeuten voellig Verschiedenes
------------------------------------------------------
* **Fenster.** Es gibt Stellungen, an denen alle Gates halten. Dann ist die
  Frage beantwortet und die Arbeit geht dort weiter.
* **Konflikt.** Jedes Gate haelt irgendwo, aber nie zwei zugleich. Der Regler
  ist das falsche Werkzeug: Was das eine Gate braucht, reisst das andere. Ein
  Konflikt ist nicht "knapp daneben" - er ist ein Beweis, dass diese Achse
  keine Loesung enthaelt.
* **Ausser Reichweite.** Ein Gate haelt an keiner Stellung. Dann sagt der
  Regler ueber dieses Gate gar nichts, und keine noch so feine Abtastung
  aendert daran etwas.

Der Unterschied ist wichtig, weil er verschiedene naechste Schritte nach sich
zieht. Ein Konflikt schliesst die Regelfamilie in ihrer jetzigen Form ab. Ein
Gate ausser Reichweite verlangt eine Aenderung an einer **anderen** Stelle -
und sagt gleich mit, welche Groesse sich bewegen muesste.

Was zwischen den Stufen liegt, ist nicht gemessen
--------------------------------------------------
Eine Abtastung misst Punkte, keine Strecken. Ein leeres Fenster heisst deshalb
zunaechst nur: *an den gemessenen Stellungen* haelt nicht alles. Zwischen zwei
Stufen kann ein schmaler Bereich liegen, den niemand gesehen hat.

Dieses Modul behauptet das Gegenteil nicht, sondern rechnet die Unsicherheit
aus: Es benennt die Zwischenraeume, die eine Loesung noch verbergen koennten,
und liefert die Stellungen, mit denen man sie schliesst. Ein Urteil
"nicht machbar" traegt genau so weit, wie die Aufloesung reicht - und die
Aufloesung steht im Urteil.

Fuer ein Gate ausser Reichweite gibt es zusaetzlich eine harte Schranke: Wenn
die **Spanne**, ueber die der Regler den Gate-Wert bewegt, kleiner ist als der
kleinste **Abstand** zur Schwelle, dann reicht der Regler nicht - egal, wie
fein man ihn abtastet. Das gilt unter der Annahme, dass der Wert zwischen den
Stufen nicht aus der gemessenen Spanne ausbricht; bei glatten Kennzahlen wie
dem Sharpe je Trade ist das eine milde Annahme, und sie wird hier ausgesprochen
statt stillschweigend benutzt.

Zum Versuchszaehler
-------------------
Jede ausgewertete Stellung ist ein gerechneter Kandidat und zaehlt. Dass am
Ende womoeglich keiner uebernommen wird, aendert daran nichts: Gesehen hat man
sie alle. Der Aufrufer addiert die Zahl der neuen Stellungen auf den Zaehler;
``cli machbarkeit`` tut das.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import combinations, pairwise

import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Stand:
    """Was ein einzelnes Gate an einer Reglerstellung gesagt hat."""

    bestanden: bool
    wert: float
    schwelle: float
    uebersprungen: bool = False

    @property
    def zeichen(self) -> str:
        if self.uebersprungen:
            return "o"
        return "+" if self.bestanden else "-"


@dataclass(frozen=True, slots=True)
class Punkt:
    """Eine Reglerstellung mit dem vollstaendigen Gate-Ergebnis."""

    stellung: float
    gates: dict[str, Stand]
    kennzahlen: dict[str, float] = field(default_factory=dict)

    @property
    def alle_halten(self) -> bool:
        return bool(self.gates) and all(g.bestanden for g in self.gates.values())

    @property
    def offen(self) -> list[str]:
        return [name for name, g in self.gates.items() if not g.bestanden]

    @property
    def bestanden(self) -> int:
        return sum(1 for g in self.gates.values() if g.bestanden)


@dataclass(frozen=True, slots=True)
class Hebelwirkung:
    """Wie weit der Regler ein Gate bewegt - und wie weit es trotzdem fehlt.

    ``spanne`` ist der Abstand zwischen groesstem und kleinstem gemessenen
    Wert, ``abstand`` der kleinste Abstand zur Schwelle ueber alle Stellungen.
    Beide sind direkt vergleichbar, weil sie in derselben Einheit stehen wie
    der Gate-Wert selbst - egal, ob gross oder klein besser ist.
    """

    gate: str
    spanne: float
    abstand: float
    naechste_stellung: float
    haelt_irgendwo: bool = False
    stellungen: int = 0

    @property
    def aussichtslos(self) -> bool:
        """Reicht der ganze Regelweg nicht bis zur Schwelle?

        Notwendige Bedingung, keine hinreichende: Um zu bestehen, muss der
        Wert die Schwelle erreichen; weiter als ``spanne`` bewegt der Regler
        ihn im gemessenen Bereich nicht. Vorausgesetzt ist dabei, dass der
        Wert zwischen den Stufen nicht aus dieser Spanne ausbricht.

        Zwei Klauseln, beide aus einem falschen Bericht gelernt:

        **Wer irgendwo haelt, ist nie ausser Reichweite.** Sonst stand dort
        ``Stichprobengroesse: aussichtslos`` - ein Gate, das an jeder Stellung
        mit grossem Abstand bestand. Der Abstand zur Schwelle ist eben in beide
        Richtungen gross, und ``spanne < abstand`` allein unterscheidet nicht,
        auf welcher Seite man steht.

        **Eine einzige Stellung belegt gar nichts.** Bei einem Messpunkt ist
        die Spanne null, und damit waere jedes gerissene Gate automatisch
        "ausser Reichweite" - eine Aussage ueber einen Regler, an dem nie
        gedreht wurde. Ein Werkzeug, das aus einem Punkt eine Schranke
        ableitet, sagt mehr, als es weiss.
        """
        if self.stellungen < 2 or self.haelt_irgendwo:
            return False
        return self.spanne < self.abstand

    def beschreibung(self) -> str:
        return (
            f"{self.gate}: der Regler bewegt den Wert um {self.spanne:.3f}, "
            f"zur Schwelle fehlen bei {self.naechste_stellung:g} noch "
            f"{self.abstand:.3f}"
            + (" - mit diesem Regler nicht erreichbar." if self.aussichtslos else ".")
        )


@dataclass(frozen=True, slots=True)
class Konflikt:
    """Zwei Gates, die je fuer sich halten, aber nie an derselben Stellung."""

    a: str
    b: str
    a_bei: float
    b_bei: float
    luecken: tuple[tuple[float, float], ...] = ()

    @property
    def uebergang(self) -> tuple[float, float]:
        return (min(self.a_bei, self.b_bei), max(self.a_bei, self.b_bei))

    @property
    def breiteste_luecke(self) -> float:
        return max((oben - unten for unten, oben in self.luecken), default=0.0)

    @property
    def mitten(self) -> list[float]:
        """Die Stellungen, die den Zweifel am schnellsten verkleinern."""
        return [round((unten + oben) / 2, 6) for unten, oben in self.luecken]

    @property
    def unteres(self) -> tuple[str, float]:
        """Das Gate, das auf der kleineren Reglerstellung haelt."""
        return (self.a, self.a_bei) if self.a_bei <= self.b_bei else (self.b, self.b_bei)

    @property
    def oberes(self) -> tuple[str, float]:
        return (self.b, self.b_bei) if self.a_bei <= self.b_bei else (self.a, self.a_bei)

    def beschreibung(self) -> str:
        # Nach Reglerstellung geordnet, nicht nach Gate-Name: "haelt bis" und
        # "erst ab" sind sonst vertauscht und der Satz sagt das Gegenteil.
        (unten_name, unten_bei), (oben_name, oben_bei) = self.unteres, self.oberes
        text = (
            f"{unten_name} haelt bis {unten_bei:g}, {oben_name} erst ab "
            f"{oben_bei:g} - dazwischen keines von beiden"
        )
        if self.luecken:
            anzahl = len(self.luecken)
            wort = "Zwischenraum" if anzahl == 1 else "Zwischenraeume"
            return (
                f"{text}. Ungeprueft bleibt der Bereich {unten_bei:g} bis "
                f"{oben_bei:g} ({anzahl} {wort}, breitester "
                f"{self.breiteste_luecke:g})."
            )
        return f"{text}."


@dataclass(slots=True)
class Machbarkeit:
    """Die Auswertung einer Abtastung entlang eines Reglers."""

    regler: str
    punkte: list[Punkt]
    einheit: str = ""

    # -- Grundlagen ---------------------------------------------------------
    @property
    def gatenamen(self) -> list[str]:
        """Alle Gate-Namen in der Reihenfolge ihres ersten Auftretens."""
        namen: list[str] = []
        for punkt in self.punkte:
            for name in punkt.gates:
                if name not in namen:
                    namen.append(name)
        return namen

    @property
    def stellungen(self) -> list[float]:
        return sorted(p.stellung for p in self.punkte)

    def haelt_bei(self, gate: str) -> list[float]:
        """An welchen Stellungen dieses Gate haelt."""
        return sorted(
            p.stellung
            for p in self.punkte
            if gate in p.gates and p.gates[gate].bestanden
        )

    # -- Die drei Ausgaenge -------------------------------------------------
    @property
    def fenster(self) -> list[Punkt]:
        """Stellungen, an denen alle Gates zugleich halten."""
        return sorted(
            (p for p in self.punkte if p.alle_halten), key=lambda p: p.stellung
        )

    @property
    def nie_erfuellt(self) -> list[str]:
        """Gates, die an keiner gemessenen Stellung halten."""
        return [name for name in self.gatenamen if not self.haelt_bei(name)]

    @property
    def konflikte(self) -> list[Konflikt]:
        """Paare, die je fuer sich halten, aber nie gemeinsam.

        Nur Gates, die ueberhaupt irgendwo halten, koennen in Konflikt stehen.
        Ein Gate ausser Reichweite steht mit keinem in Konflikt - es fehlt
        einfach ueberall, und das ist eine andere Aussage.
        """
        erreichbar = [n for n in self.gatenamen if self.haelt_bei(n)]
        gefunden: list[Konflikt] = []
        for a, b in combinations(erreichbar, 2):
            menge_a, menge_b = set(self.haelt_bei(a)), set(self.haelt_bei(b))
            if menge_a & menge_b:
                continue
            a_bei, b_bei = min(
                ((x, y) for x in menge_a for y in menge_b),
                key=lambda paar: abs(paar[0] - paar[1]),
            )
            gefunden.append(
                Konflikt(
                    a=a, b=b, a_bei=a_bei, b_bei=b_bei,
                    luecken=self._luecken(min(a_bei, b_bei), max(a_bei, b_bei)),
                )
            )
        return gefunden

    def _luecken(self, unten: float, oben: float) -> tuple[tuple[float, float], ...]:
        """Die ungemessenen Zwischenraeume innerhalb einer Spanne."""
        innen = [s for s in self.stellungen if unten <= s <= oben]
        return tuple((a, b) for a, b in pairwise(innen) if b > a)

    def hebelwirkung(self, gate: str) -> Hebelwirkung | None:
        """Wie weit der Regler dieses Gate bewegt, verglichen mit dem Rest.

        Uebersprungene Gates zaehlen nicht mit: Ihr Wert ist keiner, und er
        wuerde die Spanne verfaelschen.
        """
        staende = [
            (p.stellung, p.gates[gate])
            for p in self.punkte
            if gate in p.gates and not p.gates[gate].uebersprungen
        ]
        if not staende:
            return None
        werte = [g.wert for _, g in staende]
        stellung, naechster = min(
            staende, key=lambda paar: abs(paar[1].wert - paar[1].schwelle)
        )
        return Hebelwirkung(
            gate=gate,
            spanne=max(werte) - min(werte),
            abstand=abs(naechster.wert - naechster.schwelle),
            naechste_stellung=stellung,
            haelt_irgendwo=bool(self.haelt_bei(gate)),
            stellungen=len({s for s, _ in staende}),
        )

    # -- Was als naechstes zu messen waere ----------------------------------
    def verfeinerung(self, *, hoechstens: int = 6) -> list[float]:
        """Stellungen, die den verbliebenen Zweifel verkleinern.

        Leer heisst: Kein Zwischenraum kann noch eine Loesung verbergen -
        entweder weil ein Gate nachweislich ausser Reichweite ist, oder weil
        es nichts mehr zu ueberbruecken gibt.
        """
        for name in self.nie_erfuellt:
            wirkung = self.hebelwirkung(name)
            if wirkung is not None and wirkung.aussichtslos:
                # Ein Gate, das der Regler nicht erreicht, macht jede feinere
                # Abtastung sinnlos. Erst diese Schranke, dann der Rest.
                return []

        kandidaten: list[float] = []
        for konflikt in sorted(
            self.konflikte, key=lambda k: -k.breiteste_luecke
        ):
            kandidaten.extend(konflikt.mitten)
        for name in self.nie_erfuellt:
            wirkung = self.hebelwirkung(name)
            if wirkung is None:
                continue
            kandidaten.extend(self._nachbarmitten(wirkung.naechste_stellung))

        bekannt = set(self.stellungen)
        eindeutig: list[float] = []
        for wert in kandidaten:
            if wert not in bekannt and wert not in eindeutig:
                eindeutig.append(wert)
        return eindeutig[:hoechstens]

    def _nachbarmitten(self, stellung: float) -> list[float]:
        """Die Mitten links und rechts einer Stellung."""
        alle = self.stellungen
        mitten = []
        for a, b in pairwise(alle):
            if stellung in (a, b):
                mitten.append(round((a + b) / 2, 6))
        return mitten

    @property
    def aufloesung(self) -> float:
        """Der breiteste ungemessene Zwischenraum ueber alle Konflikte."""
        return max((k.breiteste_luecke for k in self.konflikte), default=0.0)

    # -- Ausgabe ------------------------------------------------------------
    def tabelle(self) -> str:
        """Gates als Zeilen, Reglerstellungen als Spalten.

        Diese Richtung herum, weil es elf Gates und wenige Stellungen gibt -
        und weil sich so je Gate auf einen Blick ablesen laesst, ob es dem
        Regler ueberhaupt folgt.
        """
        if not self.punkte:
            return "Nichts gemessen."
        geordnet = sorted(self.punkte, key=lambda p: p.stellung)
        breite = max(len(n) for n in self.gatenamen) if self.gatenamen else 4
        kopf = f"{self.regler:<{breite}}" + "".join(
            f"{p.stellung:>8g}" for p in geordnet
        )
        zeilen = [kopf, "-" * len(kopf)]
        for name in self.gatenamen:
            felder = "".join(
                f"{(p.gates[name].zeichen if name in p.gates else '?'):>8}"
                for p in geordnet
            )
            zeilen.append(f"{name:<{breite}}{felder}")
        zeilen.append("-" * len(kopf))
        zeilen.append(
            f"{'bestanden':<{breite}}"
            + "".join(f"{p.bestanden:>5}/{len(p.gates):<2}" for p in geordnet)
        )
        return "\n".join(zeilen)

    def als_payload(self) -> dict:
        """Die Messung als Datensatz - fuer Bericht, Website und Nachlesen.

        Ohne das muesste man die Abtastung wiederholen, um an die Werte hinter
        den Zeichen zu kommen - und jede Wiederholung kostet wieder Rechenzeit
        und verleitet dazu, die Stufen erneut auf den Versuchszaehler zu
        addieren, obwohl nichts Neues gesehen wurde.
        """
        return {
            "regler": self.regler,
            "einheit": self.einheit,
            "fenster": [p.stellung for p in self.fenster],
            "nie_erfuellt": self.nie_erfuellt,
            "aufloesung": self.aufloesung,
            "urteil": self.urteil(),
            "hebelwirkung": {
                name: {
                    "spanne": round(w.spanne, 6),
                    "abstand": round(w.abstand, 6),
                    "naechste_stellung": w.naechste_stellung,
                    "aussichtslos": w.aussichtslos,
                }
                for name in self.gatenamen
                if (w := self.hebelwirkung(name)) is not None
            },
            "konflikte": [
                {
                    "gates": [k.a, k.b],
                    "uebergang": list(k.uebergang),
                    "breiteste_luecke": k.breiteste_luecke,
                }
                for k in self.konflikte
            ],
            "punkte": [
                {
                    "stellung": p.stellung,
                    "bestanden": p.bestanden,
                    "kennzahlen": {k: round(v, 4) for k, v in p.kennzahlen.items()},
                    "gates": {
                        name: {
                            "bestanden": s.bestanden,
                            "wert": round(s.wert, 6),
                            "schwelle": round(s.schwelle, 6),
                            "uebersprungen": s.uebersprungen,
                        }
                        for name, s in p.gates.items()
                    },
                }
                for p in sorted(self.punkte, key=lambda p: p.stellung)
            ],
        }

    def urteil(self) -> str:
        if not self.punkte:
            return "Nichts gemessen - kein Urteil."

        offen = self.fenster
        if offen:
            stellungen = ", ".join(f"{p.stellung:g}" for p in offen)
            return (
                f"Fenster gefunden: bei {stellungen} {self.einheit} halten alle "
                f"{len(offen[0].gates)} Gates."
            ).strip()

        teile: list[str] = []
        harte = [
            w
            for w in (self.hebelwirkung(n) for n in self.nie_erfuellt)
            if w is not None and w.aussichtslos
        ]
        if harte:
            teile.append(
                "Ausser Reichweite des Reglers: "
                + " ".join(w.beschreibung() for w in harte)
            )
        weiche = [n for n in self.nie_erfuellt if n not in {w.gate for w in harte}]
        if weiche:
            teile.append(
                "Haelt an keiner gemessenen Stellung, ohne harte Schranke: "
                + ", ".join(weiche)
                + "."
            )
        for konflikt in self.konflikte:
            teile.append("Konflikt: " + konflikt.beschreibung())

        if not teile:
            teile.append(
                "Kein Gate faellt ueberall durch und keines steht im Konflikt - "
                "die offenen Gates verteilen sich anders."
            )

        naechste = self.verfeinerung()
        if naechste:
            teile.append(
                "Kein Fenster an den gemessenen Stellungen. Ungeprueft bleiben "
                f"Zwischenraeume bis {self.aufloesung:g} {self.einheit} Breite; "
                "zu messen waere als naechstes "
                + ", ".join(f"{w:g}" for w in naechste)
                + "."
            )
        else:
            teile.append(
                "Kein Fenster - und feiner abzutasten hilft nicht, weil der "
                "Regler mindestens ein Gate gar nicht erreicht."
            )
        return " ".join(t.strip() for t in teile)


@dataclass(frozen=True, slots=True)
class Regler:
    """Eine Stellschraube, an der sich abtasten laesst.

    Der Sinn dieser Liste ist nicht Bequemlichkeit, sondern Vergleichbarkeit:
    Solange jede Abtastung ihre eigenen Stufen mitbringt, misst jede etwas
    anderes, und zwei Ergebnisse lassen sich nicht nebeneinanderlegen.
    """

    name: str
    einheit: str
    pfad: tuple[str | int, ...]
    stufen: tuple[float, ...]
    begruendung: str = ""

    wandler: Callable[[object, float], object] | None = None
    """Statt eines Pfades eine Umformung des ganzen Genoms.

    Gebraucht fuer Groessen, die an vielen Stellen zugleich stehen - die
    Indikatorperiode etwa steckt in Einstieg, Ausstieg, Konfluenz und im
    Messfenster der Vola-Steuerung. Nur eine davon zu verschieben ergaebe eine
    Regel, die sich selbst widerspricht; ``research/gates.skaliere_perioden``
    beschreibt genau diesen Fehler und hat ihn behoben.

    Wo ein Wandler steht, ist ``pfad`` nur noch fuer ``ausgangswert`` da und
    zeigt auf nichts.
    """


#: Die bekannten Regler. Wer einen neuen aufnimmt, legt seine Stufen **hier**
#: fest und nicht im Aufruf - sonst waehlt am Ende die Auswertung ihre eigenen
#: Messpunkte, und das ist der kurze Weg zur Ueberanpassung.
REGLER: dict[str, Regler] = {
    "vola": Regler(
        name="Vola-Ziel",
        einheit="%",
        pfad=("sizing", "target_vol_pct"),
        stufen=(14.0, 16.0, 19.3, 22.0, 25.0, 28.0, 32.0),
        begruendung=(
            "Skaliert jede Position mit demselben Faktor. Gemessen: bewegt "
            "den Deflated Sharpe um 0,011 - also gar nicht."
        ),
    ),
    "stop": Regler(
        name="Stop",
        einheit="%",
        pfad=("stop", "percent"),
        stufen=(2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0),
        begruendung=(
            "Beim Spitzenkandidaten steht er auf 4 % und faengt 43,5 % aller "
            "Trades ab. Der Docstring von StopSpec verlangt fuer eine "
            "investierte Strategie das Gegenteil: 'Notbremse und nicht "
            "Ausstieg ... weit genug hinaus, dass normales Rauschen ihn nicht "
            "erreicht.' Ein Stop, der jeden zweiten Trade beendet, ist der "
            "Ausstieg - und dann entscheidet nicht mehr die Regel."
        ),
    ),
    "periode": Regler(
        name="Perioden-Faktor",
        einheit="x",
        pfad=(),
        stufen=(0.4, 0.5, 0.6, 0.8, 1.0, 1.25, 1.6, 2.0),
        wandler=lambda genome, faktor: _skaliere(genome, faktor),
        begruendung=(
            "Die einzige verbliebene Richtung aus Nummer einunddreissig: mehr "
            "**Entscheidungen** auf demselben Markt. Ein schnellerer Schnitt "
            "kreuzt oefter - die Frage ist, ob die Qualitaet je Trade das "
            "aushaelt. Skaliert werden **alle** Perioden zugleich, sonst "
            "entstuende eine Regel, die bei 40 einsteigt und bei 50 aussteigt."
        ),
    ),
    "abkuehlung": Regler(
        name="Abkuehlung",
        einheit="Kerzen",
        pfad=("cooldown_bars",),
        stufen=(0.0, 3.0, 5.0, 10.0, 20.0, 40.0),
        begruendung=(
            "Aus der Zerlegung des schlechtesten Jahres (Nummer "
            "dreiundvierzig): Der Verlust dort besteht nicht aus einem "
            "Ausreisser, sondern aus 24 Trades mit zusammen -21,45 R und "
            "keinem einzigen groesser als -1,45 R. Das ist eine Trendfolge, "
            "die im Abwaertsmarkt einsteigt, ausgestoppt wird und sofort "
            "wieder einsteigt.\n\n"
            "Die Abkuehlung ist die einzige Stellschraube, die genau daran "
            "ansetzt - und der Wettbewerbslauf davor hat gezeigt, dass eine "
            "Variante mit anderer Abkuehlung das Gate 'Schlechtestes Jahr' "
            "besteht, dafuer aber von 152 auf 136 Trades faellt und am "
            "Deflated Sharpe verliert.\n\n"
            "**Gesucht wird deshalb keine gute Stellung, sondern eine "
            "Antwort:** Gibt es eine, an der beide Gates zugleich halten, "
            "oder ziehen sie ueber den ganzen Bereich gegeneinander? Das "
            "Zweite waere ein Ergebnis - und ein Grund, diese Regelfamilie "
            "abzuschliessen."
        ),
    ),
    "ziel": Regler(
        name="Gewinnziel",
        einheit="R",
        pfad=("targets", 0, "rr"),
        stufen=(10.0, 20.0, 30.0, 50.0, 100.0, 200.0),
        begruendung=(
            "Der letzte unbetretene Weg innerhalb dieser Regelfamilie. Aus "
            "Nummer fuenfundvierzig: Der Deflated Sharpe haengt an vier "
            "Groessen, und drei davon sind ausgemessen oder unerreichbar. Die "
            "vierte ist die **Schiefe** - die Form der Verteilung.\n\n"
            "Sie haengt am rechten Rand, und der ist beim Spitzenkandidaten "
            "nicht gewachsen, sondern abgeschnitten: Zehn von 154 Trades enden "
            "am Ziel mit im Mittel +19,6 R, und die fuenf groessten Ergebnisse "
            "des ganzen Laufs liegen alle zwischen 19,69 und 19,81 R.\n\n"
            "Die Stufe 200 entspricht bei einem Vier-Prozent-Stop einer "
            "Bewegung von 800 % - praktisch 'kein Ziel'. Damit ist zum ersten "
            "Mal die uebliche Bauform einer Trendfolge ausdrueckbar: Ausstieg "
            "nur nach Regel oder Stop.\n\n"
            "**Und es ist der erste Regler, der die Trade-Zahl nicht "
            "antastet.** Alle bisherigen reparierten die Risiko-Gates, indem "
            "sie weniger handelten - und bezahlten mit dem Deflated Sharpe. "
            "Hier bleiben die Einstiege, wo sie sind; nur zehn Ausstiege "
            "aendern sich."
        ),
    ),
    "konviktion": Regler(
        name="Konviktions-Bonus",
        einheit="",
        pfad=("sizing", "konviktion_bonus"),
        stufen=(0.0, 0.5, 1.0, 1.5, 2.0),
        begruendung=(
            "Wie stark der Einsatz zwischen schwachen und starken Setups "
            "spreizt. Bei 0 ist die Konfluenz wirkungslos."
        ),
    ),
}


def _skaliere(genome, faktor: float):
    """Alle Perioden mit demselben Faktor - ueber die Funktion des Gates.

    Bewusst dieselbe wie im Plateau-Gate und in der Landschaftskarte. Wuerde
    jeder Aufrufer seine eigene Skalierung mitbringen, verglichen sie
    verschiedene Dinge - der Fehler, der in diesem Projekt schon viermal
    aufgetreten ist.
    """
    from research.gates import skaliere_perioden

    if faktor == 1.0:
        return genome
    skaliert = skaliere_perioden(genome, faktor)
    if skaliert is None:
        raise ValueError(
            f"Faktor {faktor} aendert nichts - alle Perioden stehen bereits an "
            f"ihren Grenzen."
        )
    return skaliert


def stelle_ein(genome, regler: Regler, wert: float):
    """Eine Kopie des Genoms mit veraenderter Stellschraube.

    Ueber ``model_dump`` und erneute Validierung, nicht ueber ein Setzen am
    Objekt: Das Genom ist eingefroren, und die Pruefungen des Schemas sollen
    auch fuer die Abtastung gelten. Wer eine Stufe ausserhalb der erlaubten
    Spanne verlangt, bekommt einen Fehler statt eines stillen Ergebnisses.

    Die Kennung faellt weg und wird neu gebildet - sonst traegt eine andere
    Regel dieselbe Kennung, und der Versuchszaehler zaehlt sie als dieselbe.
    """
    if regler.wandler is not None:
        return regler.wandler(genome, wert)

    daten = genome.model_dump()
    ziel = daten
    for teil in regler.pfad[:-1]:
        ziel = ziel[teil]
    ziel[regler.pfad[-1]] = wert
    daten.pop("genome_id", None)
    return type(genome).model_validate(daten)


def ausgangswert(genome, regler: Regler) -> float:
    """Wo die Stellschraube beim uebergebenen Genom gerade steht.

    Bei einem Wandler ist der Ausgangswert per Bauart **1,0**: Der Regler
    beschreibt dort keine Groesse, sondern eine Verschiebung gegenueber dem
    Genom, das hereingegeben wird.
    """
    if regler.wandler is not None:
        return 1.0
    wert = genome
    for teil in regler.pfad:
        # Ein Pfad kann in eine Liste zeigen - ``targets`` etwa ist eine, und
        # das Gewinnziel steht in ihrem ersten Eintrag. ``stelle_ein`` geht
        # denselben Weg ueber das Dict und kennt beide Faelle laengst.
        wert = wert[teil] if isinstance(teil, int) else getattr(wert, teil)
    return float(wert)


def aus_gate_report(stellung: float, report, kennzahlen=None) -> Punkt:
    """Einen ``GateReport`` in einen Punkt uebersetzen.

    Bewusst hier und nicht in ``gates.py``: Die Gates sollen nichts davon
    wissen, dass jemand sie entlang eines Reglers abtastet.
    """
    from research.gates import GateStatus

    return Punkt(
        stellung=stellung,
        gates={
            r.name: Stand(
                bestanden=r.passed,
                wert=float(r.value),
                schwelle=float(r.threshold),
                uebersprungen=r.status is GateStatus.SKIP,
            )
            for r in report.results
        },
        kennzahlen=dict(kennzahlen or {}),
    )
