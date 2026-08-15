"""Welche der elf Gates messen eigentlich verschiedene Dinge?

Die Frage, die aus Befund 60 folgt
----------------------------------
Zwei Massnahmen - Abkuehlung und Schock-Overlay - haben dieselben zwei Gates
gekippt, und beide Male war es nachweislich das blosse Streichen von Trades.
*Schlechtestes Jahr* und *Parameter-Plateau* reagieren also auf die Anzahl der
Trades, nicht auf ihre Auswahl.

Daraus folgt eine unangenehmere Frage: **Wenn zwei Gates auf dieselbe Weise
umkippen, messen sie dann ueberhaupt Verschiedenes?** "Sieben von elf" liest
sich wie sieben von elf unabhaengigen Huerden. Ob es das ist, stand nie fest.

Was hier ausdruecklich nicht vorbereitet wird
---------------------------------------------
**Das Streichen von Gates.** Der Grundsatz des Projekts ist eindeutig: Gates
werden nicht gelockert, damit etwas besteht - und ein Gate zu entfernen, weil
es "ohnehin dasselbe misst", waere die eleganteste Art, genau das zu tun.

Der Nutzen liegt woanders: Wer weiss, welche Huerden zusammenfallen, weiss,
**wo eine Verbesserung ueberhaupt etwas bewirken kann**. Wenn drei Gates
gemeinsam kippen, ist eine Anstrengung, die sie alle drei bewegt, eine
Anstrengung und nicht drei - und der Fortschritt sieht dann groesser aus, als
er ist. Genau dieser Selbstbetrug ist in Befund 58 passiert.

Was die Zahlen sind - und was sie nicht sind
--------------------------------------------
Gerechnet wird ueber die Messpunkte, die in ``reports/`` liegen: Reglerfahrten
und gepflanzte Reihen, ueberwiegend Varianten **eines** Kandidaten. Das ist
eine Aussage ueber diese Punktwolke, nicht ueber die Gates an sich. In einer
breiteren Familie koennten dieselben Gates sehr wohl auseinanderlaufen.

Zwei Kennzahlen je Paar:

* **Uebereinstimmung** - wie oft beide dasselbe sagen. Leicht zu lesen und
  leicht misszuverstehen: Zwei Gates, die praktisch immer bestehen, stimmen zu
  99 % ueberein, ohne etwas miteinander zu tun zu haben.
* **Phi** - die Korrelation zweier Ja-Nein-Groessen. Sie ist gegen genau
  diesen Fall robust und deshalb die Zahl, an der entschieden wird.

Und ein Gate, das ueber alle Punkte hinweg **immer** dasselbe sagt, taucht
gesondert auf: Es unterscheidet in dieser Wolke nichts - was nichts darueber
sagt, ob es woanders unterscheidet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

import numpy as np

#: Ab welchem Phi zwei Gates als "laufen zusammen" gelten.
#:
#: **Vorab festgelegt.** 0,8 ist die Groessenordnung, ab der zwei Ja-Nein-
#: Groessen praktisch dasselbe Urteil faellen. Eine Schranke, die man
#: hinterher so legt, dass die gewuenschten Paare herauskommen, misst nichts.
STARK = 0.8


@dataclass(frozen=True, slots=True)
class Gatelage:
    """Wie oft ein Gate in dieser Punktwolke bestanden wurde."""

    name: str
    bestanden: int
    gesamt: int

    @property
    def quote(self) -> float:
        return self.bestanden / self.gesamt if self.gesamt else 0.0

    @property
    def stumm(self) -> bool:
        """Sagt es ueber alle Punkte hinweg dasselbe?

        Dann unterscheidet es **in dieser Wolke** nichts. Das ist kein Mangel
        des Gates - ein Gate, das jeder Kandidat besteht, hat seine Arbeit
        getan, indem es die schlechten frueher aussortiert hat, die hier gar
        nicht mehr auftauchen.
        """
        return self.gesamt > 0 and self.bestanden in (0, self.gesamt)


@dataclass(frozen=True, slots=True)
class Paar:
    """Zwei Gates und wie eng sie zusammenlaufen."""

    a: str
    b: str
    phi: float
    uebereinstimmung: float

    @property
    def stark(self) -> bool:
        return abs(self.phi) >= STARK


def lade(*ordner: Path | str) -> list[dict[str, bool]]:
    """Je Messpunkt: welches Gate bestanden wurde und welches nicht.

    Uebersprungene Gates werden **weggelassen**, nicht als "durchgefallen"
    gezaehlt. Uebersprungen heisst "nicht beurteilbar"; es als Nein zu
    verbuchen erfaende ein Urteil, das nie gefaellt wurde.
    """
    punkte: list[dict[str, bool]] = []
    for verzeichnis in ordner:
        for datei in sorted(Path(verzeichnis).glob("*.json")):
            try:
                daten = json.loads(datei.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            roh = daten.get("punkte") or daten.get("analyse", {}).get("punkte") or []
            if "varianten" in daten:
                roh = [s for liste in daten["varianten"].values() for s in liste]
            for eintrag in roh:
                gates = eintrag.get("gates") or {}
                gemessen = {
                    name: bool(stand.get("bestanden"))
                    for name, stand in gates.items()
                    if isinstance(stand, dict) and not stand.get("uebersprungen")
                }
                if gemessen:
                    punkte.append(gemessen)
    return punkte


def _phi(x: np.ndarray, y: np.ndarray) -> float:
    """Korrelation zweier Ja-Nein-Reihen. 0, wo sie nicht definiert ist."""
    if len(x) < 2:
        return 0.0
    sx, sy = float(np.std(x)), float(np.std(y))
    if sx == 0.0 or sy == 0.0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


@dataclass(slots=True)
class Gatemuster:
    """Die Gates ueber viele Messpunkte - wer sagt was, und wer dasselbe."""

    punkte: list[dict[str, bool]] = field(default_factory=list)

    @property
    def namen(self) -> list[str]:
        """Gates, die auf **allen** Punkten beurteilt wurden.

        Nur diese lassen sich paarweise vergleichen: Wer zwei Gates ueber
        verschieden viele Punkte gegeneinanderlegt, vergleicht Teilmengen.
        """
        if not self.punkte:
            return []
        gemeinsam = set(self.punkte[0])
        for p in self.punkte[1:]:
            gemeinsam &= set(p)
        return sorted(gemeinsam)

    @property
    def lagen(self) -> list[Gatelage]:
        return [
            Gatelage(
                name=name,
                bestanden=sum(1 for p in self.punkte if p[name]),
                gesamt=len(self.punkte),
            )
            for name in self.namen
        ]

    @property
    def stumme(self) -> list[Gatelage]:
        return [lage for lage in self.lagen if lage.stumm]

    def paare(self) -> list[Paar]:
        """Alle Gatepaare, nach Enge geordnet."""
        spalten = {
            name: np.array([p[name] for p in self.punkte], dtype=float)
            for name in self.namen
        }
        gefunden = [
            Paar(
                a=a,
                b=b,
                phi=_phi(spalten[a], spalten[b]),
                uebereinstimmung=float(np.mean(spalten[a] == spalten[b])),
            )
            for a, b in combinations(self.namen, 2)
        ]
        return sorted(gefunden, key=lambda p: -abs(p.phi))

    @property
    def gruppen(self) -> list[set[str]]:
        """Gates, die ueber starke Paare zusammenhaengen.

        Bewusst als **Zusammenhangskomponente** und nicht als "alle mit allen
        stark": Wer A mit B und B mit C findet, hat einen Strang, auch wenn A
        und C sich nicht direkt beruehren - und ein Strang bewegt sich
        gemeinsam.
        """
        eltern = {name: name for name in self.namen}

        def wurzel(x: str) -> str:
            while eltern[x] != x:
                eltern[x] = eltern[eltern[x]]
                x = eltern[x]
            return x

        for paar in self.paare():
            if paar.stark:
                eltern[wurzel(paar.a)] = wurzel(paar.b)

        gebunden: dict[str, set[str]] = {}
        for name in self.namen:
            gebunden.setdefault(wurzel(name), set()).add(name)
        return [g for g in gebunden.values() if len(g) > 1]

    def tabelle(self, *, hoechstens: int = 10) -> str:
        zeilen = [
            f"{'Gate':<24} {'bestanden':>10} {'Quote':>7}",
            "-" * 44,
        ]
        for lage in sorted(self.lagen, key=lambda x: x.quote):
            marke = "  (sagt immer dasselbe)" if lage.stumm else ""
            zeilen.append(
                f"{lage.name:<24} {lage.bestanden:>4}/{lage.gesamt:<5} "
                f"{lage.quote:>6.0%}{marke}"
            )

        beweglich = [p for p in self.paare() if p.phi != 0.0]
        if beweglich:
            zeilen += [
                "",
                f"{'Paar':<48} {'Phi':>6} {'gleich':>8}",
                "-" * 64,
            ]
            for paar in beweglich[:hoechstens]:
                zeilen.append(
                    f"{paar.a + ' / ' + paar.b:<48} {paar.phi:>6.2f} "
                    f"{paar.uebereinstimmung:>7.0%}"
                )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.punkte:
            return "Keine Messpunkte - nichts zu vergleichen."

        teile = [
            f"{len(self.punkte)} Messpunkte, {len(self.namen)} auf allen "
            f"beurteilte Gates."
        ]
        # **Die beiden stummen Faelle bedeuten das Gegenteil voneinander.**
        # Der erste Anlauf warf sie in einen Satz - "sagen ueber alle Punkte
        # dasselbe" - und erklaerte beide damit, dass die Vorauswahl schon
        # gewirkt habe. Fuer ein nie bestandenes Gate ist das genau falsch
        # herum: Dort ist nichts aussortiert worden, dort steht die Wand.
        immer = [lage for lage in self.stumme if lage.quote == 1.0]
        nie = [lage for lage in self.stumme if lage.quote == 0.0]
        if immer:
            teile.append(
                f"**Immer bestanden: {', '.join(s.name for s in immer)}.** Sie "
                f"unterscheiden hier nichts - was nicht heisst, dass sie "
                f"ueberfluessig waeren: Ein Gate, das jeder dieser Kandidaten "
                f"besteht, hat die schlechteren frueher aussortiert."
            )
        if nie:
            teile.append(
                f"**Nie bestanden: {', '.join(s.name for s in nie)}.** Auch "
                f"das unterscheidet nichts, aber aus dem entgegengesetzten "
                f"Grund: Ueber alle {len(self.punkte)} Messpunkte hinweg ist "
                f"kein einziger daran vorbeigekommen. Das ist keine Huerde "
                f"mehr, an der man Fortschritt ablesen koennte - das ist die "
                f"Wand."
            )
        gruppen = self.gruppen
        if gruppen:
            beschrieben = "; ".join(
                " + ".join(sorted(g)) for g in sorted(gruppen, key=len, reverse=True)
            )
            teile.append(
                f"**{len(gruppen)} Straenge laufen zusammen** (Phi ab "
                f"{STARK:.1f}): {beschrieben}. Wer einen davon bewegt, bewegt "
                f"den ganzen Strang - der Fortschritt sieht dann groesser aus, "
                f"als er ist."
            )
        else:
            teile.append(
                f"Kein Paar erreicht ein Phi von {STARK:.1f} - die "
                f"beweglichen Gates laufen hier getrennt."
            )
        teile.append(
            "Das ist eine Aussage ueber diese Punktwolke, nicht ueber die "
            "Gates an sich - und ausdruecklich keine Vorbereitung darauf, "
            "eines davon zu streichen."
        )
        return "\n\n".join(teile)
