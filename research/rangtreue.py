"""Traegt die Rangfolge aus der Entwicklung nach draussen?

Die Frage
---------
Dieses Projekt ordnet Kandidaten nach der **Luecke** zur Latte - so macht es
``cli paare``, und danach entscheidet sich, was als naechstes geprueft wird.
Das ist nur dann eine sinnvolle Reihenfolge, wenn sie etwas ueber das
Verhalten **ausserhalb** der Entwicklungsdaten sagt.

Befund 186 hat das zum ersten Mal gemessen und die Zahl in Prosa
hinterlassen. Sie stand seither in keinem Code, war also nicht
nachzurechnen - genau die Lage, die Befund 187 bei ``kostenanteil``
vorgefunden hat.

Was gemessen ist
----------------
Acht Paare mit Luecke (Entwicklung) und Haltequote (Holdout):

    Rangfolge aus Befund 184    alle acht    rho +0,214   t +0,54
                                ohne Ausreisser  +0,571      +1,56
    Rangfolge aus Befund 193    alle acht    rho -0,024   t -0,06
                                ohne Ausreisser  +0,464      +1,17

**Keine der vier raeumt die Schwelle von |t| = 2.** Die Luecke ordnet die
Entwicklung; ueber das Verhalten draussen sagt sie nach dieser Messung
nichts - weder das eine noch das andere.

Und die Berichtigung hat es nicht besser gemacht
------------------------------------------------
Befund 193 hat die Latte jedes Paares auf seine eigenen Momente gestellt,
so wie das Gate rechnet. Das ist auf seinen eigenen Gruenden richtig. Es
waere naheliegend zu erwarten, dass ein richtigeres Mass auch besser
vorhersagt - **es tut es nicht**, es sagt schwaecher voraus.

Beides zugleich stehenzulassen ist der ehrliche Zustand: Die Korrektur
stimmt, und sie hat die Vorhersagekraft nicht gehoben. Wer daraus ableitet,
die alte Rechnung sei doch besser gewesen, verwechselt einen Messfehler mit
einem Guetekriterium.

Der Ausreisser
--------------
'Langsamer Kreuzer (Messlatte 2)' haelt -789 % - auf **neun** Trades im
Holdout. Das ist keine Messung, das ist eine Zahl (Befund 186). Deshalb
steht jede Rechnung hier zweimal da, mit und ohne ihn, und keine der beiden
wird als die richtige ausgegeben.

Kostet keinen Versuch: Gerechnet wird auf Zahlen, die schon gemessen sind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Ab welchem |t| dieses Projekt eine Korrelation als belegt ansieht.
#:
#: Dieselbe Schwelle wie in ``vorratsdecke`` und ``verbund`` (Befund 75).
#: Sie steht hier noch einmal, weil ``urteil`` sonst eine eigene erfaende.
MINDEST_T: float = 2.0


def raenge(werte) -> np.ndarray:
    """Die Raenge, Bindungen gemittelt.

    Ohne Mittelung der Bindungen haengt das Ergebnis an der Reihenfolge der
    Eingabe - zwei gleiche Werte bekaemen verschiedene Raenge, je nachdem,
    wer zuerst kam.
    """
    x = np.asarray(werte, dtype=float)
    ordnung = x.argsort()
    r = np.empty(len(x), dtype=float)
    r[ordnung] = np.arange(len(x), dtype=float)
    for wert in np.unique(x):
        gleich = x == wert
        if gleich.sum() > 1:
            r[gleich] = r[gleich].mean()
    return r


def rangkorrelation(x, y) -> float | None:
    """Spearman - die Pearson-Korrelation der Raenge.

    ``None``, wenn eine der Reihen keine Streuung hat oder zu kurz ist:
    Dann gibt es keine Rangfolge, die man vergleichen koennte.
    """
    if len(x) != len(y) or len(x) < 3:
        return None
    a, b = raenge(x), raenge(y)
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def t_wert(rho: float, n: int) -> float | None:
    """Der t-Wert zu einer Rangkorrelation bei ``n`` Punkten.

    Bei einer **vollstaendigen** Rangkorrelation ist er unendlich, nicht
    undefiniert. Der erste Entwurf gab dort ``None`` zurueck, und das Urteil
    hat daraus "zu wenige Punkte" gemacht - eine perfekte Uebereinstimmung
    wurde also als fehlende Messung gemeldet. ``None`` heisst hier nur noch:
    zu wenige Punkte.
    """
    if n < 3:
        return None
    if abs(rho) >= 1:
        return float("inf") if rho > 0 else float("-inf")
    return rho * ((n - 2) / (1 - rho**2)) ** 0.5


@dataclass(frozen=True, slots=True)
class Punkt:
    """Ein Kandidat mit seiner Luecke drinnen und seinem Halt draussen."""

    name: str
    luecke: float
    haelt_pct: float


@dataclass(slots=True)
class Rangtreue:
    """Ordnet die Luecke das Verhalten ausserhalb der Entwicklungsdaten?"""

    punkte: list[Punkt] = field(default_factory=list)

    @property
    def genug(self) -> bool:
        return len(self.punkte) >= 3

    def _messung(self, punkte: list[Punkt]) -> tuple[float, float] | None:
        rho = rangkorrelation(
            [p.luecke for p in punkte], [p.haelt_pct for p in punkte]
        )
        if rho is None:
            return None
        t = t_wert(rho, len(punkte))
        return (rho, t) if t is not None else None

    @property
    def alle(self) -> tuple[float, float] | None:
        return self._messung(self.punkte) if self.genug else None

    def ohne(self, name: str) -> tuple[float, float] | None:
        """Dieselbe Rechnung ohne einen benannten Punkt.

        Gedacht fuer Punkte, deren Zahl auf zu wenigen Trades steht. Sie
        werden **nicht** stillschweigend entfernt: Wer sie herausnimmt, sagt
        wen und warum, und beide Zahlen stehen nebeneinander.
        """
        rest = [p for p in self.punkte if p.name != name]
        return self._messung(rest) if len(rest) >= 3 else None

    def urteil(self, *, ausreisser: str | None = None) -> str:
        alle = self.alle
        if alle is None:
            return (
                f"Nur {len(self.punkte)} Punkte - ueber die Rangtreue laesst "
                f"sich nichts sagen."
            )
        rho, t = alle
        zeilen = [f"alle {len(self.punkte)}: rho = {rho:+.3f} bei t = {t:+.2f}"]
        ohne = self.ohne(ausreisser) if ausreisser else None
        if ohne is not None:
            zeilen.append(
                f"ohne '{ausreisser}': rho = {ohne[0]:+.3f} bei t = {ohne[1]:+.2f}"
            )

        geraeumt = [x for x in (alle, ohne) if x and abs(x[1]) >= MINDEST_T]
        if not geraeumt:
            return (
                "**Die Luecke ordnet das Verhalten draussen nicht.** "
                + "; ".join(zeilen)
                + f". Keine der Rechnungen raeumt |t| = {MINDEST_T:.0f}, und "
                f"eine Korrelation ohne Deckung darf nicht klingen wie eine "
                f"mit. Die Rangfolge taugt zum Ordnen der Entwicklung, als "
                f"Vorhersage taugt sie nach dieser Messung nicht."
            )
        richtung = "gleichlaeufig" if geraeumt[0][0] > 0 else "gegenlaeufig"
        return (
            f"**Die Luecke ordnet das Verhalten draussen {richtung}.** "
            + "; ".join(zeilen)
            + f". Mindestens eine Rechnung raeumt |t| = {MINDEST_T:.0f}."
        )


__all__ = [
    "MINDEST_T",
    "Punkt",
    "Rangtreue",
    "raenge",
    "rangkorrelation",
    "t_wert",
]
