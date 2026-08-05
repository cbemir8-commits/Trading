"""Strategie-Genome - die "DNA", die die Research-KI erzeugt.

Der zentrale Sicherheitsgedanke des ganzen Projekts steckt hier:

    **Die KI schreibt keinen Code. Sie fuellt ein Formular aus.**

Ein Genom ist ein JSON-Dokument aus Bedingungen ueber Indikatoren der
Whitelist. Der Compiler macht daraus eine ausfuehrbare Strategie. Die KI kann
damit sehr wohl kreativ sein - sie kombiniert Indikatoren, Schwellen, Filter,
Stop-Verfahren und Zielstaffelungen -, aber sie kann keine Schleife bauen,
keine Datei lesen und keine Order absetzen.

Jedes Feld ist streng validiert. Ein Genom, das die Pruefung nicht besteht,
wird verworfen und der Fehler geht als Rueckmeldung an die KI zurueck - das
ist zugleich der Lernmechanismus.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from strategy.indicators import PRICE_FIELDS, REGISTRY


class Operator(StrEnum):
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"

    @property
    def needs_previous_bar(self) -> bool:
        """Kreuzungen brauchen die Vorkerze - der Compiler muss das wissen."""
        return self in {Operator.CROSS_ABOVE, Operator.CROSS_BELOW}


class Operand(BaseModel):
    """Eine Seite einer Bedingung: Indikator, Kursfeld oder Konstante."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["indicator", "price", "constant"]
    name: str = ""
    params: dict[str, int] = Field(default_factory=dict)
    value: float = 0.0

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.kind == "indicator":
            if self.name not in REGISTRY:
                raise ValueError(
                    f"Indikator '{self.name}' steht nicht auf der Whitelist. "
                    f"Erlaubt: {sorted(REGISTRY)}"
                )
            _, spec = REGISTRY[self.name]
            for key, val in self.params.items():
                bounds = spec.param_bounds.get(key)
                if bounds is None:
                    raise ValueError(f"'{self.name}' kennt keinen Parameter '{key}'")
                if not bounds[0] <= val <= bounds[1]:
                    raise ValueError(
                        f"{self.name}.{key}={val} liegt ausserhalb von "
                        f"{bounds[0]}..{bounds[1]}"
                    )
        elif self.kind == "price" and self.name not in PRICE_FIELDS:
            raise ValueError(
                f"Kursfeld '{self.name}' unbekannt. Erlaubt: {sorted(PRICE_FIELDS)}"
            )
        return self

    @property
    def key(self) -> str:
        """Eindeutiger Schluessel fuer die Indikator-Zwischenspeicherung.

        Zwei Bedingungen, die denselben EMA(50) verwenden, sollen ihn nur
        einmal berechnen - bei Walk-Forward ueber hunderte Genome macht das
        einen spuerbaren Unterschied.
        """
        if self.kind == "constant":
            return f"const:{self.value}"
        suffix = ",".join(f"{k}={v}" for k, v in sorted(self.params.items()))
        return f"{self.kind}:{self.name}({suffix})"

    def describe(self) -> str:
        if self.kind == "constant":
            return f"{self.value:g}"
        if self.kind == "price":
            return self.name
        args = ",".join(str(v) for _, v in sorted(self.params.items()))
        return f"{self.name}({args})" if args else self.name


class Condition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    left: Operand
    op: Operator
    right: Operand

    @model_validator(mode="after")
    def _no_constant_crossing(self) -> Self:
        """Eine Konstante kann nichts kreuzen - sie bewegt sich nicht.

        ``close cross_above 100000`` ist dagegen sinnvoll und erlaubt: Dort
        kreuzt der Preis die Konstante.
        """
        if self.op.needs_previous_bar and self.left.kind == "constant":
            raise ValueError(
                "Die linke Seite einer Kreuzung darf keine Konstante sein - "
                "sie bewegt sich nicht."
            )
        return self

    def describe(self) -> str:
        symbols = {
            Operator.GT: ">",
            Operator.LT: "<",
            Operator.GTE: ">=",
            Operator.LTE: "<=",
            Operator.CROSS_ABOVE: "kreuzt hoch ueber",
            Operator.CROSS_BELOW: "kreuzt runter unter",
        }
        return f"{self.left.describe()} {symbols[self.op]} {self.right.describe()}"


class StopSpec(BaseModel):
    """Wie der Stop-Loss bestimmt wird."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["atr", "percent"] = "atr"
    atr_period: int = Field(14, ge=5, le=50)
    multiple: float = Field(1.5, ge=0.3, le=6.0)

    percent: float = Field(0.6, ge=0.15, le=25.0)
    """Bis 25 %, weil der Stop nicht immer der Ausstieg ist.

    Fuer eine wettende Strategie waere das absurd - dort bestimmt die
    Stop-Distanz die Menge, und ein weiter Stop hiesse eine winzige Position.
    Der Sizer lehnt solche Genome deshalb weiterhin ab
    (``max_stop_distance_pct``); diese Schranke hier muss die Arbeit nicht
    doppelt tun.

    Fuer eine investierte Strategie ist der Stop dagegen **Notbremse und nicht
    Ausstieg**: Ausgestiegen wird ueber eine Bedingung, der Stop faengt nur den
    Fall ab, in dem der Markt ohne Zwischenschritt wegbricht. Er gehoert dann
    weit genug hinaus, dass normales Rauschen ihn nicht erreicht. Die alte
    Obergrenze von 3 % hat genau diese Bauform unmoeglich gemacht - auf
    Stundenkerzen wird eine 3-%-Marke staendig getroffen."""

    def describe(self) -> str:
        if self.kind == "atr":
            return f"{self.multiple:g} x ATR({self.atr_period})"
        return f"{self.percent:g} % fest"


class SizingSpec(BaseModel):
    """Wie gross die Position wird - und das ist keine Nebensache.

    Bisher gab es genau einen Weg: Menge = Risikobetrag / Stop-Distanz. Er ist
    richtig fuer Strategien, die auf ein Ereignis wetten und einen engen Stop
    haben. Fuer eine Strategie, die **investiert bleibt**, ist er es nicht -
    dort ist der Stop weit oder faktisch nicht vorhanden, und die Formel liefert
    dann eine winzige Position oder verweigert den Handel ganz.

    Genau daran sind bisher alle Kandidaten gescheitert, die laenger als ein
    paar Stunden dabeibleiben wollten: nicht an der Idee, sondern an unserer
    eigenen Sperre ``max_stop_distance_pct``. Das war ein blinder Fleck im
    Aufbau, keine Erkenntnis ueber die Maerkte.

    ``kapitalanteil`` macht die Menge stattdessen am Kapital fest: 40 % Anteil
    heisst 40 % des Kontos im Markt, unabhaengig davon, wo der Stop liegt. Der
    Rueckgang wird dann nicht ueber den Stop begrenzt, sondern darueber,
    **nicht investiert zu sein** - und ob das gelingt, misst das Drawdown-Gate
    ohnehin.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["risiko", "kapitalanteil", "vola_ziel"] = "risiko"

    target_vol_pct: float = Field(25.0, ge=5.0, le=200.0)
    """Angestrebte Schwankungsbreite der Position, auf ein Jahr gerechnet.
    Nur bei ``vola_ziel`` wirksam.

    Der Gedanke: Ein fester Kapitalanteil bedeutet in ruhigen Wochen wenig
    Risiko und in stuermischen viel - dieselbe Zahl, voellig verschiedene
    Wirkung. Der Rueckgang entsteht fast immer in den stuermischen Phasen.

    Wird der Einsatz stattdessen gegenlaeufig zur gemessenen Schwankungsbreite
    gesetzt, ist das Risiko ueber die Zeit gleich - in ruhigen Phasen mehr
    Kapital, in wilden weniger. Das ist die einzige bekannte Methode, den
    Rueckgang zu senken, ohne im gleichen Zug Rendite abzugeben; die feste
    Quote skaliert beides gemeinsam, wie unsere eigene Messung gezeigt hat.

    25 % ist etwa die Haelfte dessen, was Bitcoin selbst schwankt."""

    vol_period: int = Field(30, ge=5, le=200)
    """Ueber wie viele Kerzen die Schwankungsbreite gemessen wird."""

    fraction: float = Field(0.4, gt=0, le=1.0)
    """Anteil des Kapitals im Markt. Bei ``kapitalanteil`` der feste Wert,
    bei ``vola_ziel`` die **Obergrenze**.

    Obergrenze 1,0: kein Hebel. Wer investiert bleibt statt zu wetten, soll das
    nicht auf Kredit tun - ein Rueckgang von 50 % im Basiswert waere sonst das
    Ende des Kontos, und in Bitcoin ist das kein hypothetischer Fall."""

    def describe(self) -> str:
        if self.kind == "risiko":
            return "Menge aus Risiko und Stop-Distanz"
        if self.kind == "vola_ziel":
            return (
                f"Vola-Ziel {self.target_vol_pct:g} %, hoechstens "
                f"{self.fraction:.0%} Kapital"
            )
        return f"{self.fraction:.0%} des Kapitals im Markt"


class TargetSpec(BaseModel):
    """Eine Take-Profit-Stufe, gemessen in Vielfachen des Risikos."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rr: float = Field(ge=0.3, le=20.0, description="Chance-Risiko-Verhaeltnis")
    portion: float = Field(gt=0, le=1, description="Anteil der Position, 0..1")


class Genome(BaseModel):
    """Eine vollstaendige Strategie als Datenstruktur.

    ``rationale`` ist kein Zierrat: Es landet im Research-Journal und ist das,
    was die KI im naechsten Zyklus liest. Eine Hypothese ohne Begruendung laesst
    sich nicht widerlegen - und aus einer nicht widerlegbaren Hypothese laesst
    sich auch nichts lernen.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=3, max_length=80)
    rationale: str = Field(min_length=10, max_length=2000)

    entry_long: list[Condition] = Field(default_factory=list)
    entry_short: list[Condition] = Field(default_factory=list)
    filters: list[Condition] = Field(default_factory=list)

    exit_long: list[Condition] = Field(default_factory=list)
    exit_short: list[Condition] = Field(default_factory=list)
    """Ausstieg, sobald **alle** genannten Bedingungen zutreffen - zusaetzlich
    zu Stop und Zielen, nicht an deren Stelle.

    Gebraucht fuer Strategien, die nicht entscheiden, *wann gehandelt* wird,
    sondern *wann investiert* geblieben wird. Dort ist der Ausstieg keine
    Preismarke, sondern das Ende einer Bedingung: "raus, sobald der Kurs unter
    seinen langfristigen Schnitt faellt". Solche Regeln handeln wenige Male im
    Jahr - und genau deshalb kosten sie kaum Gebuehren."""

    stop: StopSpec = Field(default_factory=StopSpec)
    targets: list[TargetSpec] = Field(min_length=1, max_length=4)

    sizing: SizingSpec = Field(default_factory=SizingSpec)
    """Standard bleibt die Risikoformel - bestehende Genome aendern sich nicht."""

    cooldown_bars: int = Field(0, ge=0, le=200)
    """Sperrfrist nach einem Trade. Verhindert, dass dieselbe Bedingung
    unmittelbar erneut ausloest und die Position sofort wieder aufgemacht wird."""

    max_hold_bars: int = Field(0, ge=0, le=2000)
    """Zwangsschliessung nach N Kerzen. 0 = aus."""

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if not self.entry_long and not self.entry_short:
            raise ValueError("Ein Genom braucht mindestens eine Einstiegsbedingung")

        total = sum(t.portion for t in self.targets)
        if total > 1.0001:  # kleine Toleranz fuer Fliesskomma
            raise ValueError(f"Zielanteile summieren sich auf {total:.4f} (maximal 1,0)")

        rr_values = [t.rr for t in self.targets]
        if rr_values != sorted(rr_values):
            raise ValueError(
                f"Ziele muessen nach Chance-Risiko-Verhaeltnis aufsteigen, waren {rr_values}. "
                "Ein naeheres Ziel hinter einem ferneren wuerde nie erreicht."
            )
        if len(set(rr_values)) != len(rr_values):
            raise ValueError(f"Doppelte Ziel-Verhaeltnisse: {rr_values}")

        return self

    @property
    def genome_id(self) -> str:
        """Stabiler Hash ueber den fachlichen Inhalt.

        ``name`` und ``rationale`` fliessen bewusst **nicht** ein: Zwei Genome
        mit identischen Regeln, aber anderer Beschreibung, sind dieselbe
        Strategie. Ohne diese Unterscheidung wuerde die KI dieselbe Idee
        beliebig oft neu 'entdecken' und die Mehrfachtest-Korrektur unterlaufen.
        """
        payload = self.model_dump(mode="json", exclude={"name", "rationale"})
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    @property
    def trades_both_directions(self) -> bool:
        return bool(self.entry_long) and bool(self.entry_short)

    def describe(self) -> str:
        """Lesbare Zusammenfassung - fuer Dashboard und Journal."""
        lines = [f"{self.name} [{self.genome_id}]", f"  Idee: {self.rationale}"]
        if self.filters:
            lines.append("  Filter (immer):")
            lines.extend(f"    - {c.describe()}" for c in self.filters)
        if self.entry_long:
            lines.append("  Long, wenn alles zutrifft:")
            lines.extend(f"    - {c.describe()}" for c in self.entry_long)
        if self.entry_short:
            lines.append("  Short, wenn alles zutrifft:")
            lines.extend(f"    - {c.describe()}" for c in self.entry_short)
        lines.append(f"  Stop: {self.stop.describe()}")
        targets = ", ".join(f"{t.rr:g}R zu {t.portion:.0%}" for t in self.targets)
        lines.append(f"  Ziele: {targets}")
        if self.cooldown_bars:
            lines.append(f"  Sperrfrist: {self.cooldown_bars} Kerzen")
        if self.max_hold_bars:
            lines.append(f"  Maximale Haltedauer: {self.max_hold_bars} Kerzen")
        return "\n".join(lines)

    @property
    def all_conditions(self) -> list[Condition]:
        """Jede Bedingung des Genoms - Einstieg, Filter und Ausstieg.

        Eine Stelle statt vier Aufzaehlungen: Wer eine Sorte vergisst,
        berechnet den zugehoerigen Indikator nicht vor, und die Strategie
        stolpert erst zur Laufzeit darueber.
        """
        return [
            *self.entry_long,
            *self.entry_short,
            *self.filters,
            *self.exit_long,
            *self.exit_short,
        ]

    def required_operands(self) -> set[str]:
        """Alle Indikatoren, die dieses Genom braucht."""
        keys: set[str] = set()
        for condition in self.all_conditions:
            for operand in (condition.left, condition.right):
                if operand.kind != "constant":
                    keys.add(operand.key)
        return keys
