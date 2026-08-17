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

    def wert(self, kennzahl: str) -> float | None:
        roh = self.werte.get(kennzahl)
        return float(roh) if roh is not None else None


def lade(ordner: Path | str, *, regler: str = "Vola-Ziel") -> list[Messpunkt]:
    """Die Punkte eines Reglers aus den Machbarkeitsberichten.

    Mehrere Berichte desselben Reglers koennen aus verschiedenen Staenden
    stammen - die Aufwaermphase des Compilers wurde einmal korrigiert, und
    Berichte davor tragen andere Zahlen. Deshalb wird **nicht** stumpf
    zusammengelegt: Bei gleicher Stellung gewinnt der juengste Bericht.
    Aeltere stillschweigend mitzumitteln hiesse, zwei Messstaende zu einer
    Kurve zu verruehren.
    """
    gefunden: dict[float, Messpunkt] = {}
    for datei in sorted(Path(ordner).glob("*.json")):
        try:
            daten = json.loads(datei.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        gemessen = daten.get("regler") or daten.get("analyse", {}).get("regler")
        if gemessen != regler:
            continue
        punkte = daten.get("punkte") or daten.get("analyse", {}).get("punkte") or []
        for punkt in punkte:
            kennzahlen = punkt.get("kennzahlen") or {}
            if not kennzahlen:
                continue
            stellung = float(punkt.get("stellung", 0.0))
            gefunden[stellung] = Messpunkt(
                stellung=stellung,
                werte={k: float(v) for k, v in kennzahlen.items() if v is not None},
            )
    return sorted(gefunden.values(), key=lambda p: p.stellung)


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

    @property
    def schwellen(self) -> tuple[Schwelle, ...]:
        return (self.a, self.b, *self.weitere)

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
                if not schwelle.erfuellt(wert):
                    marken.append(
                        f"{schwelle.name} "
                        + ("fehlt" if schwelle.mindestens else "reisst")
                    )
            zeilen.append(
                f"{p.stellung:>9g}{werte}  "
                f"{', '.join(marken) or 'alle erfuellt'}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.punkte:
            return "Keine Messpunkte - nichts zu entscheiden."

        benannt = " und ".join(str(s) for s in self.schwellen)
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
            f"statistische - sie liegt beim Nutzer."
        )
