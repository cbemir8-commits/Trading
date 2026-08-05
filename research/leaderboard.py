"""Die Bestenliste - jede je gepruefte Strategie, ueber alle Laeufe hinweg.

Warum es sie gibt
-----------------
Bisher war jeder Zulassungslauf für sich: eine Tabelle im Terminal, danach
weg. Wer nach zwanzig Laeufen wissen wollte, welche Idee am weitesten kam,
musste Bildschirmfotos vergleichen.

Die Bestenliste haelt fest, was ein Lauf herausgefunden hat: je Genom das
**beste je erreichte** Ergebnis, wie oft es geprueft wurde, und woran es zuletzt
scheiterte. Sie wird fortgeschrieben, nie ueberschrieben.

Warum kein einzelner Punktwert
------------------------------
Eine einzige Zahl waere bequem und falsch. Zwei Strategien mit derselben
Punktzahl koennen voellig verschiedene Dinge sein - die eine hat sechs Gates
bestanden und ist an der Bestaendigkeit gescheitert, die andere hat drei
bestanden und einen hohen Erwartungswert aus zwoelf Trades.

Sortiert wird deshalb der Reihe nach: erst danach, ob zugelassen; dann nach
der Zahl bestandener Gates; dann nach dem Erwartungswert je Trade. Jede Stufe
ist fuer sich verstaendlich, und die Tabelle zeigt alle drei.

Was ein hoher Platz nicht bedeutet
----------------------------------
Platz 1 heisst "kam am weitesten", nicht "ist profitabel". Solange die
Spalte ``zugelassen`` leer bleibt, hat **keine** Strategie die Pruefung
bestanden - egal wie die Rangfolge darunter aussieht. Diese Unterscheidung ist
der Grund, warum die Zulassung nicht am Platz haengt.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

#: Aktuelle Fassung des Dateiformats. Wird sie erhoeht, faengt die Liste neu an,
#: statt alte Eintraege falsch zu deuten.
FORMAT = 2


@dataclass(slots=True)
class Entry:
    """Eine Strategie in der Bestenliste."""

    genome_id: str
    name: str
    generation: int
    herkunft: str = "Katalog"
    """Woher der Kandidat stammt: Katalog, Variante oder KI-Vorschlag."""

    geprueft: int = 0
    zuerst: str = ""
    zuletzt: str = ""

    zugelassen: bool = False
    gates_bestanden: int = 0
    gates_gesamt: int = 0
    gescheitert_an: list[str] = field(default_factory=list)

    trades: int = 0
    erwartung_r: float = 0.0
    sharpe: float = 0.0
    rendite_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    fenster_profitabel: float = 0.0
    hypothese: str = ""

    deflated_sharpe: float = 0.0
    """Wie sicher der Vorteil echt ist, nach Korrektur fuer die Zahl der
    Versuche. Die einzige Kennzahl hier, die sich nicht schoenrechnen laesst,
    indem man weniger riskiert."""

    @property
    def rang_schluessel(self) -> tuple:
        """Reihenfolge der Bestenliste - absteigend zu lesen.

        Bewusst mehrstufig statt als Punktwert: Jede Stufe ist fuer sich
        begruendbar, und die Tabelle kann alle zeigen.

        **Warum die Zahl bestandener Gates nicht mehr an zweiter Stelle
        steht.** Sie ist eine irrefuehrende Rangfolge, und der Fall ist
        gemessen: Derselbe Kandidat mit engerem Stop bestand 9 von 11 Gates
        statt 8 - aber nur, weil er schlicht weniger riskierte. Rueckgang,
        schlechtestes Jahr und Monte-Carlo bestanden dort durch kleinere
        Positionen, waehrend der Deflated Sharpe von 0,901 auf 0,619 fiel.

        Nach der alten Reihenfolge waere die schlechtere Strategie auf Platz
        eins gelandet, und die Bestenliste haette den Rueckschritt als
        Fortschritt ausgewiesen.

        Der Deflated Sharpe steht deshalb vor der Gate-Zahl: Er misst, wie
        sicher der Vorteil ueberhaupt echt ist, und er laesst sich **nicht**
        durch kleinere Positionen verbessern - er ist skaleninvariant. Wer
        weniger riskiert, verbessert seinen Rang damit nicht mehr.

        Die Gate-Zahl bleibt im Schluessel, aber dahinter: Zwischen zwei
        Kandidaten mit gleich belastbarem Vorteil ist der weiter, der mehr
        Pruefungen besteht.
        """
        return (
            self.zugelassen,
            round(self.deflated_sharpe, 3),
            self.gates_bestanden,
            self.erwartung_r,
            self.sharpe,
        )

    def besser_als(self, andere: Entry) -> bool:
        return self.rang_schluessel > andere.rang_schluessel


def _jetzt() -> str:
    return datetime.now(UTC).isoformat()


class Leaderboard:
    """Bestenliste auf der Platte, fortgeschrieben ueber alle Laeufe."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.entries: dict[str, Entry] = {}
        self.laeufe: int = 0
        self._load()

    # -- Zustand -------------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            roh = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            log.error("bestenliste.unlesbar", pfad=str(self.path))
            return

        if roh.get("format") != FORMAT:
            # Lieber neu anfangen als alte Felder falsch deuten. Die Liste ist
            # eine Auswertung, keine Buchhaltung - sie laesst sich nachrechnen.
            log.warning("bestenliste.format_veraltet", gefunden=roh.get("format"))
            return

        self.laeufe = int(roh.get("laeufe", 0))
        for daten in roh.get("eintraege", []):
            try:
                self.entries[daten["genome_id"]] = Entry(**daten)
            except TypeError:
                log.warning("bestenliste.eintrag_uebersprungen", daten=daten.get("name"))

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "format": FORMAT,
                    "stand": _jetzt(),
                    "laeufe": self.laeufe,
                    "eintraege": [asdict(e) for e in self.ranked()],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return self.path

    # -- Fortschreiben -------------------------------------------------------
    def record(self, candidates, *, generation: int, herkunft: str = "Katalog") -> int:
        """Ein Laufergebnis eintragen. Gibt zurueck, wie viele sich verbessert haben.

        Ein schlechteres Ergebnis ueberschreibt kein besseres. Sonst wuerde
        eine Strategie, die einmal gut und einmal schlecht abschnitt, je nach
        Reihenfolge der Laeufe verschieden dastehen - und die Liste haette
        keinen Wert.
        """
        self.laeufe += 1
        verbessert = 0

        for candidate in candidates:
            neu = _aus_kandidat(candidate, generation=generation, herkunft=herkunft)
            alt = self.entries.get(neu.genome_id)

            if alt is None:
                neu.geprueft = 1
                neu.zuerst = neu.zuletzt = _jetzt()
                self.entries[neu.genome_id] = neu
                verbessert += 1
                continue

            alt.geprueft += 1
            alt.zuletzt = _jetzt()
            if neu.besser_als(alt):
                neu.geprueft = alt.geprueft
                neu.zuerst = alt.zuerst
                neu.zuletzt = alt.zuletzt
                self.entries[neu.genome_id] = neu
                verbessert += 1

        return verbessert

    # -- Abfragen ------------------------------------------------------------
    def ranked(self) -> list[Entry]:
        return sorted(self.entries.values(), key=lambda e: e.rang_schluessel, reverse=True)

    def best(self, count: int = 5) -> list[Entry]:
        return self.ranked()[:count]

    @property
    def admitted(self) -> list[Entry]:
        return [e for e in self.entries.values() if e.zugelassen]

    def summary(self) -> str:
        if not self.entries:
            return "Noch nichts geprueft."
        spitze = self.ranked()[0]
        return (
            f"{len(self.entries)} Strategien in {self.laeufe} Laeufen geprueft, "
            f"{len(self.admitted)} zugelassen. "
            f"Vorn: {spitze.name} ({spitze.gates_bestanden}/{spitze.gates_gesamt} Gates, "
            f"Erwartung {spitze.erwartung_r:+.3f} R)"
        )


def _aus_kandidat(candidate, *, generation: int, herkunft: str) -> Entry:
    combined = candidate.walkforward.combined
    return Entry(
        genome_id=candidate.genome.genome_id,
        name=candidate.genome.name,
        generation=generation,
        herkunft=herkunft,
        zugelassen=candidate.admitted,
        gates_bestanden=sum(1 for r in candidate.gates.results if r.passed),
        gates_gesamt=len(candidate.gates.results),
        gescheitert_an=[r.name for r in candidate.gates.failures],
        trades=candidate.trades,
        erwartung_r=round(combined.expectancy_r, 4) if combined else 0.0,
        sharpe=round(candidate.sharpe, 3),
        rendite_pct=round(combined.total_return_pct, 2) if combined else 0.0,
        max_drawdown_pct=round(combined.max_drawdown_pct, 2) if combined else 0.0,
        fenster_profitabel=round(candidate.consistency, 3),
        deflated_sharpe=_deflated_sharpe(candidate),
        hypothese=candidate.genome.rationale,
    )


def _deflated_sharpe(candidate) -> float:
    """Den Deflated Sharpe aus den Gate-Ergebnissen holen.

    Er wird dort ohnehin berechnet - ihn hier ein zweites Mal zu rechnen
    hiesse, zwei Quellen fuer dieselbe Zahl zu haben, die auseinanderlaufen
    koennen.

    Wurde das Gate uebersprungen (zu wenige Trades), bleibt der Wert null.
    Das ist die richtige Richtung: Ein Kandidat, ueber dessen Belastbarkeit
    sich nichts sagen laesst, steht nicht vor einem, ueber den etwas bekannt
    ist.
    """
    for ergebnis in candidate.gates.results:
        if ergebnis.name == "Deflated Sharpe":
            return round(float(ergebnis.value), 4)
    return 0.0
