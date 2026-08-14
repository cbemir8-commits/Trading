"""Alles, was je gemessen wurde - gegen die Linie, die es haette reissen muessen.

Warum diese Frage jetzt dran ist
--------------------------------
Sechzehn Richtungen sind gemessen und geschlossen, und vier davon zeigen
dasselbe Muster: Jeder Weg, der eine Kennzahl verbessert, verschlechtert den
Deflated Sharpe ueber einen anderen Kanal.

    Abkuehlung        weniger handeln  -> Risiko-Gates ja, DSR nein
    Gewinnziel        laenger laufen   -> Streuung waechst, DSR nein
    Adaptive Periode  oefter handeln   -> Aehnlichkeit waechst, DSR nein
    Groessenregler    alles skalieren  -> Qualitaet je Trade unveraendert

Vier Einzelfaelle sind ein Verdacht, keine Aussage. Die Aussage waere: **Kein
Punkt dieser Regelfamilie liegt ueber seiner eigenen Grenzlinie** - und die
laesst sich pruefen, ohne einen einzigen neuen Backtest zu rechnen. Die Punkte
stehen alle schon in ``reports/machbarkeit/``.

Was verglichen wird
-------------------
Zu jeder Trade-Zahl gehoert ein **noetiger Sharpe je Trade**, damit der
Deflated Sharpe 0,95 erreicht (``research/suchbudget.py``). Jeder gemessene
Punkt hat eine Trade-Zahl und einen Sharpe je Trade. Damit laesst sich jeder
Punkt einordnen - und der kleinste Abstand ueber alle ist die ehrlichste Zahl,
die dieses Projekt ueber sich selbst hat.

Was dabei ehrlich bleiben muss
------------------------------
Die aelteren Berichte tragen die **Form** der Verteilung nicht mit; dort gilt
die Voreinstellung, also die Form des Spitzenkandidaten. Fuer Punkte derselben
Familie ist das eine brauchbare Naeherung, aber eine Naeherung - und beim
Gewinnziel-Regler, wo sich die Form ueber die Stufen drastisch aendert, waere
sie falsch. Solche Punkte werden deshalb **markiert**, nicht stillschweigend
mitgezaehlt.

Und: Das hier ist eine Aussage ueber die gemessenen Punkte, nicht ueber alle
denkbaren. Es sagt "nichts von dem, was wir probiert haben, reicht" - nicht
"es gibt nichts".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from research.suchbudget import ZIEL, Budget, Kandidat

#: Kennzahlen, ohne die ein Punkt sich nicht einordnen laesst.
NOETIG = ("trades", "sharpe_je_trade")


@dataclass(frozen=True, slots=True)
class Messpunkt:
    """Ein Punkt aus einem Machbarkeitsbericht."""

    regler: str
    stellung: float
    kandidat: Kandidat
    genaehert: bool
    """Trug der Bericht die Form der Verteilung nicht mit?"""

    dsr: float | None = None
    """Der **gemessene** Deflated Sharpe dieses Punktes.

    Er ist das Urteil, und er ist exakt: Das Gate hat ihn mit der wirklichen
    Verteilung des Punktes gerechnet. Die Grenzlinie daneben uebersetzt den
    Abstand in Sharpe-Einheiten und ist auf die Form angewiesen - fehlt sie im
    Bericht, ist nur diese Uebersetzung ungenau, nicht das Urteil.
    """

    @property
    def name(self) -> str:
        return f"{self.regler} {self.stellung:g}"


def lade(ordner: Path | str) -> list[Messpunkt]:
    """Alle einordnbaren Punkte aus den Machbarkeitsberichten.

    Beschaedigte oder unvollstaendige Berichte werden uebersprungen, nicht
    geraten: Ein Punkt ohne Sharpe je Trade laesst sich nicht einordnen, und
    eine erfundene Zahl waere schlimmer als ein fehlender Punkt.
    """
    gefunden: list[Messpunkt] = []
    for datei in sorted(Path(ordner).glob("*.json")):
        try:
            daten = json.loads(datei.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        regler = daten.get("regler") or daten.get("analyse", {}).get("regler") or "?"
        punkte = daten.get("punkte") or daten.get("analyse", {}).get("punkte") or []
        for punkt in punkte:
            kennzahlen = punkt.get("kennzahlen") or {}
            if not all(kennzahlen.get(k) for k in NOETIG):
                continue
            schiefe = kennzahlen.get("schiefe")
            woelbung = kennzahlen.get("woelbung")
            gefunden.append(
                Messpunkt(
                    regler=str(regler),
                    stellung=float(punkt.get("stellung", 0.0)),
                    kandidat=Kandidat(
                        name=f"{regler} {punkt.get('stellung', 0.0):g}",
                        trades=int(kennzahlen["trades"]),
                        sharpe_je_trade=float(kennzahlen["sharpe_je_trade"]),
                        schiefe=float(schiefe) if schiefe else None,
                        woelbung=float(woelbung) if woelbung else None,
                    ),
                    genaehert=not (schiefe and woelbung),
                    dsr=_gemessener_dsr(punkt),
                )
            )
    return gefunden


def _gemessener_dsr(punkt: dict) -> float | None:
    """Den Gate-Wert aus dem Bericht holen - ohne ihn nachzurechnen."""
    stand = (punkt.get("gates") or {}).get("Deflated Sharpe")
    if not isinstance(stand, dict) or stand.get("uebersprungen"):
        return None
    wert = stand.get("wert")
    return float(wert) if wert is not None else None


@dataclass(slots=True)
class Front:
    """Die gemessene Familie, gegen ihre Grenzlinie gelegt."""

    punkte: list[Messpunkt]
    versuche: int

    @property
    def budget(self) -> Budget:
        return Budget(
            versuche=self.versuche, kandidaten=[p.kandidat for p in self.punkte]
        )

    @property
    def abstaende(self):
        return self.budget.abstaende()

    @property
    def naechster(self):
        return self.budget.naechster

    @property
    def bestanden(self) -> list[Messpunkt]:
        """Punkte, deren **gemessener** Deflated Sharpe die Schwelle erreicht.

        Das ist das Urteil - exakt, weil das Gate mit der wirklichen Verteilung
        des Punktes gerechnet hat. Die Grenzlinie sagt nur, wie weit es fehlt.
        """
        return [p for p in self.punkte if p.dsr is not None and p.dsr >= ZIEL]

    @property
    def bester(self) -> Messpunkt | None:
        mit = [p for p in self.punkte if p.dsr is not None]
        return max(mit, key=lambda p: p.dsr or 0.0) if mit else None

    def tabelle(self, *, hoechstens: int = 12) -> str:
        zeilen = [
            f"{'Punkt':26} {'Trades':>7} {'hat':>8} {'noetig':>9} {'Faktor':>8} "
            f"{'DSR':>7}  "
        ]
        gemessen = {p.kandidat.name: p.dsr for p in self.punkte}
        geordnet = sorted(
            self.abstaende,
            key=lambda a: a.faktor if a.faktor is not None else float("inf"),
        )
        genaehert = {p.kandidat.name for p in self.punkte if p.genaehert}
        for a in geordnet[:hoechstens]:
            noetig = f"{a.noetig:.4f}" if a.noetig is not None else "unerr."
            faktor = f"{a.faktor:.2f}" if a.faktor is not None else "  --"
            marke = " ~" if a.kandidat.name in genaehert else ""
            wert = gemessen.get(a.kandidat.name)
            dsr = f"{wert:.3f}" if wert is not None else "  -"
            zeilen.append(
                f"{a.kandidat.name[:26]:26} {a.kandidat.trades:>7} "
                f"{a.kandidat.sharpe_je_trade:>8.4f} {noetig:>9} {faktor:>8} "
                f"{dsr:>7}{marke}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.punkte:
            return "Keine einordenbaren Messpunkte gefunden."
        nah = self.naechster
        if nah is None or nah.faktor is None:
            return (
                f"{len(self.punkte)} Punkte gemessen, keiner mit einer "
                f"Trade-Zahl, bei der das Gate ueberhaupt erreichbar waere."
            )
        if self.bestanden:
            namen = ", ".join(p.name for p in self.bestanden[:3])
            return (
                f"{len(self.bestanden)} von {len(self.punkte)} Punkten "
                f"erreichen die Schwelle: {namen}. Das ist ein Befund, keine "
                f"Zulassung - jeder davon muss durch alle elf Gates."
            )
        bester = self.bester
        hoechster = (
            f" Der hoechste gemessene Deflated Sharpe der Familie liegt bei "
            f"{bester.dsr:.3f} ('{bester.name}') gegen eine Schwelle von "
            f"{ZIEL:.2f}."
            if bester is not None
            else ""
        )
        return (
            f"**Kein einziger von {len(self.punkte)} gemessenen Punkten "
            f"erreicht die Schwelle.**{hoechster} Am naechsten an der "
            f"Grenzlinie lag '{nah.kandidat.name}' mit {nah.kandidat.trades} "
            f"Trades zu je {nah.kandidat.sharpe_je_trade:.4f}; noetig waeren "
            f"{nah.noetig:.4f}, also Faktor {nah.faktor:.2f}."
        )
