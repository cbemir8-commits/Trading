"""Liegen ganze Regelfamilien systematisch anders - und was das kostet.

Woher die Frage kommt
---------------------
Befund 83 hat vier kalibrierte Regeln gemessen, und zwei davon fielen auf:
Die beiden Mean-Reversion-Regeln lagen mit z = -2,17 und -2,32 **deutlich
unter** dem, was die Kopplungsgerade vorhersagt. Der Verdacht lag nahe, dass
nicht die Taktung entscheidet, sondern die Familie.

Ueber alle 22 gemessenen Regeln, nach ihrer Regellogik gruppiert:

    Familie      n   Mittel z   Spanne
    -----------------------------------
    Ausbruch     3     +0,93    +0,56 .. +1,14
    Trend        5     +0,87    +0,43 .. +1,18
    Volumen      3     +0,30    -0,16 .. +0,57
    Struktur     6     -0,16    -0,91 .. +0,64
    Rueckkehr    5     -1,41    -1,89 .. -0,81

**Alle fuenf Rueckkehr-Regeln liegen unter der Geraden, alle acht aus Trend
und Ausbruch darueber.** Kein einziger Ueberschneidungsfall.

Warum das eine Gegenprobe braucht
---------------------------------
Die Familien habe ich zugeordnet, **nachdem** ich die Werte kannte. Das ist
der klassische Weg, ein Muster in Rauschen zu finden: Man gruppiert so lange,
bis die Gruppen sich unterscheiden.

Die Zuordnung folgt zwar der Regellogik - 'Rueckkehr' heisst, dass die Regel
nach einem Rueckgang kauft - und nicht den Zahlen. Aber das behauptet sich
leicht und prueft sich schwer. Deshalb wird gegen eine Permutation getestet:
Dieselben Labels, zufaellig auf die 22 Punkte verteilt, hunderttausendmal.

    Spannweite der Familienmittel, beobachtet   2,34
    Nullverteilung, Mittel                      1,14
    Nullverteilung, 95. Perzentil               1,80
    Anteil der Null darueber                    0,20 %

Die Trennung ist damit echt, und zwar deutlich.

Der Preis, der daran haengt
---------------------------
Und jetzt die unangenehme Haelfte. Ueber die zwanzig Regeln, fuer die die
Fensterkorrelation zum Bestand vorliegt:

    Residuum z gegen |rho| zum Bestand:  r = +0,480  (n = 20, t = 2,32)

**Je aehnlicher eine Regel dem Bestand, desto besser ihre Qualitaet** relativ
zur Kopplung. Genau die Familien, die ueber der Geraden liegen - Trend und
Ausbruch -, sind die, die dem Trendfolge-Signal des Bestands am naechsten
stehen.

Der Auftrag aus Befund 76 verlangt beides: Qualitaet **und** Unabhaengigkeit.
Die Daten sagen, dass sich das widerspricht.

Die Alternativerklaerung, die dazugehoert
-----------------------------------------
Das muss keine Eigenschaft der "Aehnlichkeit zum Bestand" sein. Naheliegender:
Der Markt ist ueber diesen Zeitraum massiv gestiegen. Alles, was dem Trend
folgt, hat davon profitiert; alles, was dagegen laeuft, hat verloren. Dann
misst ``rho`` nur, wie sehr eine Regel long-lastig war, und der Zusammenhang
waere eine Eigenschaft **des Zeitraums** und nicht der Regeln.

Beides fuehrt praktisch zum selben Schluss - die Suche nach "unabhaengig und
gut" laeuft gegen die Daten -, aber die Deutungen sind verschieden, und
welche stimmt, ist hier nicht entschieden.

Kostet keinen Versuch: Gruppiert werden Messungen, die schon vorliegen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Regellogik -> Familie, in **dieser Reihenfolge** geprueft.
#:
#: Das ist eine Einordnung und keine Messung: Welcher Familie eine Regel
#: angehoert, steht in ihrer Logik und nicht in ihren Zahlen. Sie hier
#: abzulegen ist trotzdem noetig, weil sonst nur der Test weiss, wie die 22
#: gemessenen Regeln gruppiert waren - und der Auftrag an den Analysten haengt
#: daran.
#:
#: Die Reihenfolge traegt: 'Rueckkehr zum Volumenschwerpunkt' enthaelt beide
#: Schluesselwoerter und gehoert zu 'Rueckkehr'. Wer die Liste umsortiert,
#: aendert eine Zuordnung.
FAMILIENSCHLUESSEL: tuple[tuple[str, str], ...] = (
    ("Rueckkehr", "Rueckkehr"),
    ("VWAP", "Rueckkehr"),
    ("Bollinger", "Rueckkehr"),
    ("Ueberverkauft", "Rueckkehr"),
    ("Donchian", "Ausbruch"),
    ("Enge", "Ausbruch"),
    ("Volumenschock", "Volumen"),
    ("Kerze", "Volumen"),
    ("Trend", "Trend"),
    ("Momentum", "Trend"),
    ("Vola-Ziel", "Trend"),
    ("Luecke", "Struktur"),
    ("Abfolge", "Struktur"),
    ("Abgriff", "Struktur"),
)


def familie_von(name: str) -> str | None:
    """Die Familie einer Regel aus ihrem Namen - oder ``None``.

    ``None`` statt einer Sammelfamilie: Eine Regel, die sich nicht einordnen
    laesst, faellt aus der Auswertung heraus. Sie in einen Topf "Sonstige" zu
    werfen hiesse, eine Familie zu bilden, die keine ist - und genau darueber
    wuerde dann eine Spannweite gerechnet.
    """
    for schluessel, familie in FAMILIENSCHLUESSEL:
        if schluessel.lower() in name.lower():
            return familie
    return None

@dataclass(frozen=True, slots=True)
class Regel:
    """Eine gemessene Regel mit ihrer Familie."""

    name: str
    trades: int
    sharpe_je_trade: float
    familie: str
    rho: float | None = None
    """Fensterkorrelation zum Bestand - wo gemessen."""


@dataclass(slots=True)
class Familienbild:
    """Die Residuen um die Kopplungsgerade, nach Familie getrennt."""

    regeln: list[Regel] = field(default_factory=list)

    @property
    def genug(self) -> bool:
        return len(self.regeln) >= 6

    def _residuen(self) -> np.ndarray | None:
        if not self.genug:
            return None
        trades = np.array([float(r.trades) for r in self.regeln])
        sharpe = np.array([r.sharpe_je_trade for r in self.regeln])
        steigung, abschnitt = np.polyfit(trades, sharpe, 1)
        rest = sharpe - (steigung * trades + abschnitt)
        streuung = rest.std(ddof=2)
        return rest / streuung if streuung > 0 else None

    def je_familie(self) -> dict[str, tuple[int, float, float, float]]:
        """Anzahl, Mittel, Minimum und Maximum der Residuen je Familie."""
        z = self._residuen()
        if z is None:
            return {}
        nach: dict[str, list[float]] = {}
        for regel, wert in zip(self.regeln, z, strict=True):
            nach.setdefault(regel.familie, []).append(float(wert))
        return {
            f: (len(w), float(np.mean(w)), float(np.min(w)), float(np.max(w)))
            for f, w in nach.items()
        }

    @property
    def spannweite(self) -> float | None:
        """Abstand zwischen bester und schlechtester Familie, in Residuen."""
        bild = self.je_familie()
        if len(bild) < 2:
            return None
        mittel = [w[1] for w in bild.values()]
        return max(mittel) - min(mittel)

    def nullprobe(
        self, *, durchlaeufe: int = 20_000, saat: int = 20260817
    ) -> tuple[float, float]:
        """Wie gross die Spannweite bei zufaelliger Zuordnung waere.

        **Der Test, der die Gruppierung rechtfertigt.** Die Familien wurden
        zugeordnet, nachdem die Werte bekannt waren - ohne Gegenprobe waere
        das der klassische Weg, ein Muster in Rauschen zu finden.
        """
        z = self._residuen()
        if z is None:
            return (float("nan"), float("nan"))
        labels = np.array([r.familie for r in self.regeln])
        zufall = np.random.default_rng(saat)
        eindeutig = list(set(labels))
        werte = []
        for _ in range(durchlaeufe):
            gemischt = zufall.permutation(labels)
            mittel = [
                z[gemischt == f].mean() for f in eindeutig if (gemischt == f).any()
            ]
            if len(mittel) > 1:
                werte.append(max(mittel) - min(mittel))
        return (float(np.mean(werte)), float(np.percentile(werte, 95)))

    @property
    def trennt_echt(self) -> bool:
        """Liegt die beobachtete Spannweite ueber dem 95. Perzentil der Null?"""
        beobachtet = self.spannweite
        _, perzentil = self.nullprobe()
        return (
            beobachtet is not None
            and np.isfinite(perzentil)
            and beobachtet > perzentil
        )

    @property
    def guete_faehrt_auf_aehnlichkeit(self) -> float | None:
        """Korrelation zwischen Residuum und Aehnlichkeit zum Bestand.

        Positiv heisst: Je aehnlicher dem Bestand, desto besser die Qualitaet
        - und damit widersprechen sich die beiden Anforderungen aus dem
        Auftrag. Gemessen +0,480 bei zwanzig Regeln.
        """
        z = self._residuen()
        if z is None:
            return None
        paare = [
            (float(wert), abs(regel.rho))
            for regel, wert in zip(self.regeln, z, strict=True)
            if regel.rho is not None
        ]
        if len(paare) < 6:
            return None
        a = np.array([p[0] for p in paare])
        b = np.array([p[1] for p in paare])
        if a.std() == 0 or b.std() == 0:
            return None
        return float(np.corrcoef(a, b)[0, 1])

    def tabelle(self) -> str:
        zeilen = [f"{'Familie':<12} {'n':>3} {'Mittel z':>10} {'Spanne':>18}", "-" * 46]
        for familie, (anzahl, mittel, tief, hoch) in sorted(
            self.je_familie().items(), key=lambda kv: -kv[1][1]
        ):
            zeilen.append(
                f"{familie:<12} {anzahl:>3} {mittel:>+10.2f} "
                f"{f'{tief:+.2f} .. {hoch:+.2f}':>18}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        beobachtet = self.spannweite
        if beobachtet is None:
            return "Zu wenige Regeln - ueber Familien laesst sich nichts sagen."
        _, perzentil = self.nullprobe()
        if not self.trennt_echt:
            return (
                f"**Die Familien trennen nicht.** Spannweite {beobachtet:.2f} "
                f"gegen ein 95. Perzentil der Zufallszuordnung von "
                f"{perzentil:.2f}. Bei so wenigen Regeln je Familie faellt so "
                f"etwas leicht zufaellig an."
            )
        bild = self.je_familie()
        beste = max(bild.items(), key=lambda kv: kv[1][1])
        schlechteste = min(bild.items(), key=lambda kv: kv[1][1])
        aehnlich = self.guete_faehrt_auf_aehnlichkeit
        preis = ""
        if aehnlich is not None and aehnlich > 0.3:
            preis = (
                f"\n\n**Und das hat einen Preis.** Das Residuum korreliert mit "
                f"{aehnlich:+.3f} mit der Aehnlichkeit zum Bestand: Je naeher "
                f"eine Regel am Trendfolge-Signal liegt, desto besser ihre "
                f"Qualitaet. Der Auftrag verlangt Qualitaet **und** "
                f"Unabhaengigkeit - die Daten sagen, dass sich das "
                f"widerspricht.\n\n"
                f"Das muss keine Eigenschaft der Aehnlichkeit sein. Der Markt "
                f"ist ueber den Zeitraum stark gestiegen; dann misst die "
                f"Korrelation nur, wie long-lastig eine Regel war, und der "
                f"Zusammenhang gehoerte dem **Zeitraum** und nicht den Regeln. "
                f"Welche Deutung stimmt, ist hier nicht entschieden."
            )
        return (
            f"**Ganze Familien liegen systematisch anders.** '{beste[0]}' im "
            f"Mittel {beste[1][1]:+.2f}, '{schlechteste[0]}' {schlechteste[1][1]:+.2f} "
            f"- eine Spannweite von {beobachtet:.2f} gegen ein 95. Perzentil "
            f"der Zufallszuordnung von {perzentil:.2f}.{preis}"
        )
