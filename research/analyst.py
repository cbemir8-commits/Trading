"""Die Research-KI: schlaegt Strategien vor, entscheidet aber nichts.

Das ist die Stelle, an der ein Sprachmodell im System vorkommt - und die
Bauweise ist bewusst eng:

    KI  ->  JSON-Genom  ->  Pydantic-Validierung  ->  Compiler  ->  neun Gates

**Die KI schreibt niemals ausfuehrbaren Code.** Sie fuellt eine Datenstruktur
aus, deren Felder, Wertebereiche und erlaubte Indikatoren vorher feststehen.
Ein Vorschlag ausserhalb dieser Grenzen wird nicht "repariert", sondern
abgelehnt. Der Unterschied ist nicht Vorsicht, sondern Statik: Wenn ein Modell
Code erzeugen darf, der mit echtem Geld handelt, ist jede Aussage ueber das
Systemverhalten nur noch so gut wie das Modell an diesem Tag.

Was die KI also tatsaechlich tut: Sie liest, was schon versucht wurde und
**woran es gescheitert ist**, und formuliert daraus die naechste Hypothese.
Das ist echte Arbeit - aber es ist Vorschlagsarbeit. Zugelassen wird nichts
davon durch die KI; das entscheiden dieselben neun Gates wie bei einem von
Hand geschriebenen Genom, inklusive Mehrfachtest-Korrektur.

Warum das Journal so wichtig ist
--------------------------------
Ohne die Historie schlaegt ein Modell in jedem Zyklus ungefaehr dasselbe vor -
es kennt ja nur den Prompt. Jeder Wiederholungsversuch zaehlt trotzdem als
Versuch in der Mehrfachtest-Korrektur, macht die Huerde also fuer alle
folgenden hoeher, ohne etwas beizutragen. Die Rueckmeldung "RSI(14)<25 ist am
Kosten-Stresstest gescheitert, Profitfaktor 1,08 gegen Schwelle 1,20" ist der
eigentliche Lernmechanismus.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import structlog

from research.gates import GateThresholds
from strategy.genome import Genome
from strategy.indicators import PRICE_FIELDS, REGISTRY

log = structlog.get_logger(__name__)

#: Wie viele Vorschlaege je Zyklus. Mehr waere nicht besser: Jeder Kandidat
#: erhoeht den Versuchszaehler und damit die Huerde fuer alle folgenden.
PROPOSALS_PER_CYCLE = 4


class LLMClient(Protocol):
    """Was das System von einem Sprachmodell braucht - mehr nicht.

    Als Protokoll formuliert, damit die Tests ohne Netz und ohne Kosten laufen.
    Ein Test, der echte Modellaufrufe braucht, wird nie oft genug ausgefuehrt,
    um etwas zu merken.
    """

    def complete(self, *, system: str, prompt: str, max_tokens: int) -> LLMResponse: ...


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class Budget:
    """Kostenbremse.

    Ohne sie kann ein Fehler in einer Schleife an einem Wochenende ein
    Monatsbudget verbrauchen. Die Bremse sitzt deshalb **vor** dem Aufruf,
    nicht in einer Auswertung danach.
    """

    monthly_usd: Decimal
    spent_usd: Decimal = Decimal(0)
    month: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m"))

    #: Preise je Million Token (Opus 5, Stand der Konfiguration).
    input_price_per_mtok: Decimal = Decimal("15")
    output_price_per_mtok: Decimal = Decimal("75")

    @property
    def remaining_usd(self) -> Decimal:
        return max(Decimal(0), self.monthly_usd - self.spent_usd)

    @property
    def exhausted(self) -> bool:
        return self.remaining_usd <= 0

    def roll_over(self) -> None:
        """Zum Monatswechsel zuruecksetzen."""
        current = datetime.now(UTC).strftime("%Y-%m")
        if current != self.month:
            log.info("budget.neuer_monat", vorher=self.month, jetzt=current)
            self.month = current
            self.spent_usd = Decimal(0)

    def charge(self, response: LLMResponse) -> Decimal:
        cost = (
            Decimal(response.input_tokens) / Decimal(1_000_000) * self.input_price_per_mtok
            + Decimal(response.output_tokens) / Decimal(1_000_000) * self.output_price_per_mtok
        )
        self.spent_usd += cost
        return cost

    def to_json(self) -> dict:
        return {
            "monthly_usd": str(self.monthly_usd),
            "spent_usd": str(self.spent_usd),
            "month": self.month,
        }

    @classmethod
    def from_json(cls, data: dict, *, monthly_usd: Decimal) -> Budget:
        return cls(
            monthly_usd=monthly_usd,
            spent_usd=Decimal(data.get("spent_usd", "0")),
            month=data.get("month", datetime.now(UTC).strftime("%Y-%m")),
        )


def load_budget(path: Path | str, *, monthly_usd: Decimal) -> Budget:
    file = Path(path)
    if not file.exists():
        return Budget(monthly_usd=monthly_usd)
    try:
        budget = Budget.from_json(json.loads(file.read_text()), monthly_usd=monthly_usd)
    except (json.JSONDecodeError, ValueError, KeyError):
        # Im Zweifel als ausgeschoepft behandeln: Ein unlesbarer Zaehler darf
        # nicht dazu fuehren, dass unbegrenzt weiterbezahlt wird.
        log.error("budget.unlesbar", pfad=str(file), massnahme="gilt als ausgeschoepft")
        return Budget(monthly_usd=monthly_usd, spent_usd=monthly_usd)
    budget.roll_over()
    return budget


def save_budget(path: Path | str, budget: Budget) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_suffix(".tmp")
    temporary.write_text(json.dumps(budget.to_json(), indent=2))
    temporary.replace(file)


@dataclass(slots=True)
class Proposal:
    genome: Genome
    accepted: bool
    reason: str = ""


@dataclass(slots=True)
class AnalystResult:
    proposals: list[Proposal] = field(default_factory=list)
    cost_usd: Decimal = Decimal(0)
    raw_response: str = ""

    @property
    def genomes(self) -> list[Genome]:
        return [p.genome for p in self.proposals if p.accepted]

    def summary(self) -> str:
        accepted = len(self.genomes)
        return (
            f"{accepted} von {len(self.proposals)} Vorschlaegen brauchbar "
            f"({self.cost_usd:.3f} USD)"
        )


def anzahl_gates() -> int:
    """Wie viele Zulassungspruefungen es wirklich gibt.

    **Abgeleitet und nicht hingeschrieben** (Befund 121). Die Zahl stand als
    "neun" im Systemauftrag, waehrend derselbe Auftrag weiter unten "Von elf
    Zulassungspruefungen" rechnete - und die README nannte acht, ``cli
    research`` neun. Vier Stellen, drei Zahlen, eine Wahrheit.

    Gezaehlt wird an der Stelle, die es entscheidet: den ``gate_``-Aufrufen in
    ``evaluate_gates``.
    """
    import inspect

    from research import gates

    return inspect.getsource(gates.evaluate_gates).count("gate_")


SYSTEM_PROMPT = f"""Du bist Analyst in einem systematischen Handelssystem fuer BTCUSDT.

Deine Aufgabe: neue Strategie-Hypothesen als JSON vorschlagen. Du schreibst
keinen Code und triffst keine Entscheidungen - jeder Vorschlag durchlaeuft
danach Walk-Forward und {anzahl_gates()} Zulassungspruefungen, die du nicht
beeinflussen kannst.

Grundsaetze:

1. EINFACH SCHLAEGT KOMPLEX. Eine Strategie mit sieben Filtern und Perioden
   wie 17, 23, 37 sieht im Backtest fast immer besser aus und faellt live
   auseinander. Zwei bis drei Bedingungen, runde Perioden.

2. JEDE HYPOTHESE BRAUCHT EINE BEGRUENDUNG, die falsch sein KANN. "RSI unter
   25 markiert Uebertreibungen, die sich zurueckbilden" ist widerlegbar.
   "Diese Kombination hat gut abgeschnitten" ist es nicht.

3. LERNE AUS DEM JOURNAL. Wiederhole keine Idee, die schon gescheitert ist -
   ausser du aenderst genau das, woran sie gescheitert ist, und sagst das.

4. JEDER VERSUCH KOSTET. Die Zulassungshuerde steigt mit der Zahl aller je
   getesteten Kandidaten (Mehrfachtest-Korrektur). Vier durchdachte
   Vorschlaege sind besser als zwanzig Variationen.

Antworte ausschliesslich mit einem JSON-Array von Genomen. Kein Fliesstext,
keine Erklaerung ausserhalb des JSON, keine Markdown-Umrandung."""


def build_prompt(
    *,
    journal: list[dict],
    thresholds: GateThresholds,
    exit_findings: list[str] | None = None,
    regime_findings: str = "",
    count: int = PROPOSALS_PER_CYCLE,
    lage=None,
    ausschluesse=None,
) -> str:
    """Den Auftrag zusammenstellen.

    Enthaelt bewusst **die Fehlschlaege mit Zahlen**, nicht nur die Namen der
    gescheiterten Kandidaten. "Am Kosten-Stresstest gescheitert, Profitfaktor
    1,08 gegen Schwelle 1,20" laesst sich gezielt angehen; "hat nicht
    bestanden" nicht.

    ``lage`` ist eine ``auftragslage.Auftragslage`` und traegt nach, was hier
    jahrelang fehlte: **das Gate, an dem tatsaechlich alles haengt.** Der
    Auftrag nannte fuenf Schwellen, aber nicht den Deflated Sharpe - und die
    Trade-Schwelle darin (100) liegt unter dem, was gebraucht wird. Der
    Analyst hat also auf das falsche Ziel optimiert, und niemand hat es ihm
    gesagt. Ohne ``lage`` bleibt der Auftrag, wie er war.

    ``ausschluesse`` ist eine ``ausschluss.Ausschluesse`` und traegt die
    andere Haelfte nach: **was gemessen und geschlossen ist.** Ohne sie
    schlaegt der Analyst weiter Regelarten vor, die durchgemessen sind - in
    Befund 83 waren zwei von vier eigenen Vorschlaegen aus einer Familie, die
    Befund 84 dann geschlossen hat.
    """
    parts: list[str] = []

    parts.append("## Erlaubte Indikatoren\n")
    for name, (_, spec) in sorted(REGISTRY.items()):
        bounds = ", ".join(f"{k}: {v[0]}..{v[1]}" for k, v in spec.param_bounds.items())
        parts.append(f"- {name}({bounds})" if bounds else f"- {name}")
    parts.append(f"\nKursfelder: {', '.join(sorted(PRICE_FIELDS))}")
    parts.append("Operatoren: gt, lt, gte, lte, cross_above, cross_below\n")

    # **Fuenf von elf, und das gehoert dazugesagt** (Befund 121). Die
    # Ueberschrift las sich wie eine vollstaendige Liste; wer danach plant,
    # plant gegen sechs Huerden, die er nicht kennt. Die wichtigste davon -
    # der Deflated Sharpe - steht weiter unten unter "Was tatsaechlich fehlt",
    # aber die Messlatte, das schlechteste Jahr und das Parameter-Plateau
    # standen nirgends.
    parts.append(f"## Zulassungsschwellen (5 der {anzahl_gates()})\n")
    parts.append(f"- mindestens {thresholds.min_oos_trades} Out-of-Sample-Trades")
    parts.append(f"- Sharpe mindestens {thresholds.min_oos_sharpe}")
    parts.append(f"- Drawdown hoechstens {thresholds.max_oos_drawdown_pct} %")
    parts.append(
        f"- mindestens {thresholds.min_window_consistency:.0%} profitable Fenster"
    )
    parts.append(
        f"- ueberlebt {thresholds.cost_stress_factor}-fache Gebuehren"
    )
    # Kein Verweis auf einen anderen Abschnitt: Den gibt es nur mit ``lage``,
    # und ein Verweis ins Leere ist schlechter als keiner. Die Gates werden
    # deshalb hier benannt.
    parts.append(
        f"\nDie uebrigen {anzahl_gates() - 5} sind hier nicht als Schwelle "
        "aufgezaehlt. Der haerteste davon ist der **Deflated Sharpe**, der "
        "dafuer korrigiert, dass man bei genug Versuchen zufaellig etwas "
        "Gutaussehendes findet. Die anderen betreffen Rendite gegen "
        "Kaufen-und-Halten, das schlechteste Jahr, die Stichprobengroesse und "
        "die Frage, ob die Parameter auf einem Plateau stehen oder auf einer "
        "Nadelspitze.\n"
    )

    parts.append("## Was bereits versucht wurde\n")
    if not journal:
        # **"Erste Generation" ist eine Behauptung ueber den Zaehlerstand**
        # (Befund 121). Sie stand hier unbedingt, und im selben Auftrag
        # standen darunter acht namentlich gescheiterte Regeln - ein
        # Widerspruch auf zwei Bildschirmseiten.
        #
        # ``state/journal.json`` existiert nicht; die 198 Versuche liegen in
        # ``trials.json``. Wer das Journal leer vorfindet, hat deshalb kein
        # leeres Projekt vor sich, sondern ein anderes Verzeichnis.
        versuche = getattr(lage, "versuche", 0) or 0
        if versuche > 0:
            parts.append(
                f"Das Research-Journal ist leer, aber **{versuche} Versuche "
                f"sind gezaehlt.** Dies ist nicht die erste Generation - die "
                f"Nachweise liegen in einem anderen Verzeichnis und stehen "
                f"nicht vollstaendig hier. Was bekannt ist, folgt weiter "
                f"unten unter den geschlossenen Richtungen und den bereits "
                f"gescheiterten Regeln.\n"
            )
        else:
            parts.append("Nichts. Dies ist die erste Generation.\n")
    else:
        for entry in journal[-6:]:
            for candidate in entry.get("candidates", []):
                verdict = "ZUGELASSEN" if candidate.get("admitted") else "abgelehnt"
                parts.append(f"### {candidate.get('name')} - {verdict}")
                parts.append(f"Hypothese: {candidate.get('rationale', '')}")
                parts.append(
                    f"Ergebnis: {candidate.get('trades')} Trades, "
                    f"Sharpe {candidate.get('sharpe')}, "
                    f"{candidate.get('consistency')} Fenster profitabel"
                )
                feedback = candidate.get("gate_feedback", "").strip()
                if feedback and feedback != "Alle Gates bestanden.":
                    parts.append(f"Gescheitert an:\n{feedback}")
                parts.append("")

    if exit_findings:
        parts.append("## Befunde aus den Ausstiegen (MAE/MFE)\n")
        parts.extend(f"- {finding}" for finding in exit_findings)
        parts.append("")

    if regime_findings:
        parts.append("## Befunde nach Marktphase\n")
        parts.append(regime_findings + "\n")

    if lage is not None:
        parts.append(lage.als_auftrag())

    # Nach dem Auftrag und vor der Aufgabe: Erst was gebraucht wird, dann was
    # dafuer ausscheidet. Umgekehrt liest sich der Prompt als Verbotsliste mit
    # angehaengtem Ziel.
    if ausschluesse is not None:
        text = ausschluesse.als_auftrag()
        if text:
            parts.append(text)

    parts.append(f"## Auftrag\n\nSchlage {count} neue Genome vor.")
    parts.append(
        "Antworte mit einem JSON-Array. Schema je Eintrag:\n"
        '{"name": str, "rationale": str, "entry_long": [Bedingung], '
        '"entry_short": [Bedingung], "filters": [Bedingung], '
        '"stop": {"kind": "atr"|"percent", "atr_period": int, "multiple": float, '
        '"percent": float}, '
        '"targets": [{"rr": float, "portion": float}], '
        '"cooldown_bars": int, "max_hold_bars": int}\n'
        'Bedingung: {"left": Operand, "op": str, "right": Operand}\n'
        'Operand: {"kind": "indicator"|"price"|"constant", "name": str, '
        '"params": {...}, "value": float}'
    )
    return "\n".join(parts)


def parse_proposals(text: str, *, already_tried: set[str] | None = None) -> list[Proposal]:
    """Die Antwort in gepruefte Genome verwandeln.

    Jeder Vorschlag wird einzeln validiert. Ein fehlerhafter Eintrag laesst die
    uebrigen unberuehrt - ein Modell, das drei brauchbare und einen kaputten
    Vorschlag liefert, hat drei brauchbare geliefert.

    Wird **nicht** repariert: Ein Genom mit einem unbekannten Indikator oder
    einer Periode ausserhalb der Grenzen wird abgelehnt. Wer solche Vorschlaege
    zurechtbiegt, verschiebt die Grenzen faktisch dorthin, wo das Modell sie
    haben wollte.
    """
    already_tried = already_tried or set()
    payload = _extract_json_array(text)
    if payload is None:
        log.error("analyst.keine_gueltige_antwort", laenge=len(text))
        return []

    proposals: list[Proposal] = []
    seen: set[str] = set()

    for raw in payload:
        try:
            genome = Genome.model_validate(raw)
        except Exception as exc:
            log.warning("analyst.vorschlag_ungueltig", fehler=str(exc)[:200])
            continue

        if genome.genome_id in already_tried:
            proposals.append(
                Proposal(
                    genome=genome,
                    accepted=False,
                    reason="schon einmal getestet - zaehlt trotzdem als Versuch, "
                    "traegt aber nichts bei",
                )
            )
            continue

        if genome.genome_id in seen:
            proposals.append(
                Proposal(genome=genome, accepted=False, reason="doppelt in dieser Antwort")
            )
            continue

        seen.add(genome.genome_id)
        proposals.append(Proposal(genome=genome, accepted=True))

    return proposals


def _extract_json_array(text: str) -> list | None:
    """Das JSON-Array aus der Antwort holen.

    Modelle umranden ihre Antwort gelegentlich mit ```json trotz gegenteiliger
    Anweisung. Das ist kein Grund, einen sonst brauchbaren Vorschlag
    wegzuwerfen.
    """
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()

    start = stripped.find("[")
    end = stripped.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None

    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, list) else None


def propose(
    client: LLMClient,
    *,
    journal: list[dict],
    budget: Budget,
    thresholds: GateThresholds | None = None,
    already_tried: set[str] | None = None,
    exit_findings: list[str] | None = None,
    regime_findings: str = "",
    count: int = PROPOSALS_PER_CYCLE,
    max_tokens: int = 4000,
    lage=None,
    ausschluesse=None,
) -> AnalystResult:
    """Einen Forschungszyklus durchfuehren.

    Die Budgetpruefung steht **vor** dem Aufruf. Ein Fehler in einer Schleife
    kann sonst an einem Wochenende ein Monatsbudget verbrauchen.
    """
    budget.roll_over()
    if budget.exhausted:
        log.warning(
            "analyst.budget_erschoepft",
            monat=budget.month,
            ausgegeben=str(budget.spent_usd),
            hinweis="Kein Modellaufruf. Der Handel laeuft davon unberuehrt weiter.",
        )
        return AnalystResult()

    prompt = build_prompt(
        journal=journal,
        thresholds=thresholds or GateThresholds(),
        exit_findings=exit_findings,
        regime_findings=regime_findings,
        count=count,
        lage=lage,
        ausschluesse=ausschluesse,
    )

    response = client.complete(system=SYSTEM_PROMPT, prompt=prompt, max_tokens=max_tokens)
    cost = budget.charge(response)

    proposals = parse_proposals(response.text, already_tried=already_tried)
    result = AnalystResult(proposals=proposals, cost_usd=cost, raw_response=response.text)
    log.info("analyst.zyklus", zusammenfassung=result.summary())
    return result


class DateiClient:
    """Ein ``LLMClient``, der seine Antwort aus einer Datei liest.

    **Warum es das gibt.** Der Analyst war gebaut, getestet und nie benutzt -
    weil er einen bezahlten API-Schluessel braucht, den dieses Projekt nicht
    gesetzt hat. Damit lag der einzige Weg zu *strukturell* neuen Regeln
    brach, waehrend die Mutation nur Zahlen variierte und alle Zahlenwege
    ausgemessen wurden.

    ``LLMClient`` ist ein Protokoll, also eine vorgesehene Erweiterungsstelle.
    Wer den Auftrag aus ``build_prompt`` selbst beantwortet - von Hand, aus
    einem anderen Modell, aus einem Gespraech - legt die Antwort hier ab und
    bekommt **denselben** Weg: dieselbe Pruefung durch ``parse_proposals``,
    dieselben elf Gates, denselben Versuchszaehler.

    Was das ausdruecklich **nicht** ist: eine Abkuerzung. Ein Vorschlag von
    Hand ist keinen Deut glaubwuerdiger als einer aus dem Modell - er kostet
    genauso einen Versuch und muss genauso bestehen. Der einzige Unterschied
    ist, dass er nichts kostet und dass dransteht, woher er kommt.
    """

    def __init__(self, pfad: Path | str) -> None:
        self.pfad = Path(pfad)

    def complete(self, *, system: str, prompt: str, max_tokens: int) -> LLMResponse:
        text = self.pfad.read_text()
        log.info(
            "analyst.aus_datei",
            pfad=str(self.pfad),
            zeichen=len(text),
            hinweis="Kein Modellaufruf - die Antwort kam aus einer Datei.",
        )
        # Keine Kosten, keine Token: Was nicht gerufen wurde, wird nicht
        # abgerechnet. Das Budget bleibt unberuehrt.
        return LLMResponse(text=text, input_tokens=0, output_tokens=0)


class AnthropicClient:
    """Anbindung an die echte API.

    Bewusst duenn: Alles, was diese Klasse tut, ist einen Text schicken und
    einen Text zurueckgeben. Die gesamte Logik - Prompt, Validierung, Budget -
    liegt darueber und ist ohne Netz testbar.
    """

    def __init__(self, api_key: str, *, model: str = "claude-opus-5") -> None:
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete(self, *, system: str, prompt: str, max_tokens: int) -> LLMResponse:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        )
        return LLMResponse(
            text=text,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
