"""Tests der Research-KI.

Der Kern dieser Datei ist nicht, dass gute Vorschlaege durchkommen - das ist
leicht. Der Kern ist, dass **schlechte nicht durchkommen und nicht repariert
werden**:

* Ein unbekannter Indikator wird abgelehnt, nicht ersetzt.
* Eine Periode ausserhalb der Grenzen wird abgelehnt, nicht zurechtgebogen.
* Ausfuehrbarer Code in der Antwort ist schlicht kein gueltiges Genom.

Wer solche Vorschlaege zurechtbiegt, verschiebt die Grenzen faktisch dorthin,
wo das Modell sie haben wollte - und dann sind sie keine Grenzen mehr.

Dazu die Kostenbremse: Sie sitzt **vor** dem Aufruf. Ein Fehler in einer
Schleife kann sonst an einem Wochenende ein Monatsbudget verbrauchen.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from research.analyst import (
    SYSTEM_PROMPT,
    Budget,
    DateiClient,
    LLMResponse,
    build_prompt,
    load_budget,
    parse_proposals,
    propose,
    save_budget,
)
from research.gates import GateThresholds
from research.seeds import trend_following

VALID_GENOME = {
    "name": "EMA-Ausbruch mit Volumenfilter",
    "rationale": (
        "Ausbruch ueber den 30er-Donchian-Kanal bei ueberdurchschnittlichem "
        "Volumen. Hypothese: Ausbrueche ohne Beteiligung laufen nicht."
    ),
    "entry_long": [
        {
            "left": {"kind": "price", "name": "close"},
            "op": "cross_above",
            "right": {"kind": "indicator", "name": "donchian_upper", "params": {"period": 30}},
        }
    ],
    "filters": [
        {
            "left": {"kind": "indicator", "name": "volume_zscore", "params": {"period": 50}},
            "op": "gt",
            "right": {"kind": "constant", "value": 1.0},
        }
    ],
    "stop": {"kind": "atr", "atr_period": 14, "multiple": 1.5},
    "targets": [{"rr": 1.5, "portion": 0.5}, {"rr": 3.0, "portion": 0.5}],
    "cooldown_bars": 8,
    "max_hold_bars": 200,
}


class FakeLLM:
    """Ein Sprachmodell, das genau das sagt, was der Test braucht."""

    def __init__(self, text: str, *, input_tokens: int = 5000, output_tokens: int = 1500) -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls: list[dict] = []

    def complete(self, *, system: str, prompt: str, max_tokens: int) -> LLMResponse:
        self.calls.append({"system": system, "prompt": prompt, "max_tokens": max_tokens})
        return LLMResponse(
            text=self.text,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


# ---------------------------------------------------------------------------
#  Was NICHT durchkommt
# ---------------------------------------------------------------------------
class TestRejection:
    def test_unknown_indicator_is_rejected_not_replaced(self) -> None:
        """Der wichtigste Test hier.

        Ein Indikator ausserhalb der Whitelist wird abgelehnt - nicht durch
        einen aehnlichen ersetzt. Wer hier zurechtbiegt, verschiebt die Grenze
        dorthin, wo das Modell sie haben wollte.
        """
        genome = json.loads(json.dumps(VALID_GENOME))
        genome["entry_long"][0]["right"]["name"] = "supertrend_ultimate"

        proposals = parse_proposals(json.dumps([genome]))

        assert proposals == []

    def test_out_of_bounds_period_is_rejected(self) -> None:
        """donchian_upper erlaubt 5..200. 5000 ist kein Tippfehler, den man
        stillschweigend korrigiert - es ist eine andere Strategie."""
        genome = json.loads(json.dumps(VALID_GENOME))
        genome["entry_long"][0]["right"]["params"]["period"] = 5000

        assert parse_proposals(json.dumps([genome])) == []

    def test_executable_code_is_simply_not_a_genome(self) -> None:
        """Die Bauweise macht Code-Einschleusung gegenstandslos: Es gibt keinen
        Pfad, auf dem Text zu ausfuehrbarem Code wird. Was kein gueltiges Genom
        ist, ist nichts."""
        response = """[{"name": "x", "rationale": "y",
            "code": "import os; os.system('rm -rf /')"}]"""

        assert parse_proposals(response) == []

    def test_targets_must_ascend(self) -> None:
        """Ein naeheres Ziel hinter einem ferneren wuerde nie erreicht - die
        Genom-Validierung faengt das, nicht erst der Backtest."""
        genome = json.loads(json.dumps(VALID_GENOME))
        genome["targets"] = [{"rr": 3.0, "portion": 0.5}, {"rr": 1.5, "portion": 0.5}]

        assert parse_proposals(json.dumps([genome])) == []

    def test_one_bad_proposal_does_not_spoil_the_others(self) -> None:
        """Ein Modell, das drei brauchbare und einen kaputten Vorschlag
        liefert, hat drei brauchbare geliefert."""
        broken = {"name": "kaputt", "rationale": "zu kurz"}
        second = json.loads(json.dumps(VALID_GENOME))
        second["entry_long"][0]["right"]["params"]["period"] = 40

        proposals = parse_proposals(json.dumps([VALID_GENOME, broken, second]))

        assert sum(1 for p in proposals if p.accepted) == 2

    def test_garbage_response_yields_nothing(self) -> None:
        assert parse_proposals("Tut mir leid, das kann ich nicht.") == []

    def test_repeat_of_a_tried_idea_is_marked(self) -> None:
        """Eine Wiederholung zaehlt trotzdem als Versuch in der
        Mehrfachtest-Korrektur, traegt aber nichts bei - sie gehoert
        aussortiert, bevor sie einen Walk-Forward kostet."""
        tried = {trend_following().genome_id}
        payload = json.dumps([trend_following().model_dump(mode="json")])

        proposals = parse_proposals(payload, already_tried=tried)

        assert len(proposals) == 1
        assert not proposals[0].accepted
        assert "schon einmal getestet" in proposals[0].reason

    def test_duplicates_within_one_answer_are_dropped(self) -> None:
        proposals = parse_proposals(json.dumps([VALID_GENOME, VALID_GENOME]))

        assert sum(1 for p in proposals if p.accepted) == 1


class TestParsing:
    def test_valid_genome_is_accepted(self) -> None:
        proposals = parse_proposals(json.dumps([VALID_GENOME]))

        assert len(proposals) == 1
        assert proposals[0].accepted
        assert proposals[0].genome.name == VALID_GENOME["name"]

    def test_markdown_fence_is_tolerated(self) -> None:
        """Modelle umranden ihre Antwort gelegentlich mit ```json trotz
        gegenteiliger Anweisung. Kein Grund, einen brauchbaren Vorschlag
        wegzuwerfen."""
        wrapped = f"```json\n{json.dumps([VALID_GENOME])}\n```"

        assert len(parse_proposals(wrapped)) == 1

    def test_leading_chatter_is_tolerated(self) -> None:
        chatty = f"Gerne! Hier sind meine Vorschlaege:\n{json.dumps([VALID_GENOME])}"

        assert len(parse_proposals(chatty)) == 1


# ---------------------------------------------------------------------------
#  Der Auftrag ans Modell
# ---------------------------------------------------------------------------
class TestPrompt:
    def test_system_prompt_forbids_code(self) -> None:
        assert "keinen Code" in SYSTEM_PROMPT

    def test_whitelist_is_included(self) -> None:
        """Das Modell muss die erlaubten Indikatoren samt Grenzen kennen -
        sonst schlaegt es welche vor, die abgelehnt werden, und der Zyklus
        verpufft."""
        prompt = build_prompt(journal=[], thresholds=GateThresholds())

        assert "donchian_upper" in prompt
        assert "5..200" in prompt

    def test_failures_carry_their_numbers(self) -> None:
        """"Am Kosten-Stresstest gescheitert, Profitfaktor 1,08 gegen Schwelle
        1,20" laesst sich gezielt angehen. "Hat nicht bestanden" nicht - das
        ist der Unterschied zwischen Lernen und Weiterraten."""
        journal = [
            {
                "candidates": [
                    {
                        "name": "Mean Reversion",
                        "rationale": "RSI unter 25 markiert Uebertreibungen",
                        "admitted": False,
                        "trades": 210,
                        "sharpe": 0.42,
                        "consistency": 0.33,
                        "gate_feedback": "- Kosten-Stress: 1.080 gegen Schwelle 1.200.",
                    }
                ]
            }
        ]

        prompt = build_prompt(journal=journal, thresholds=GateThresholds())

        assert "Mean Reversion" in prompt
        assert "1.080" in prompt
        assert "1.200" in prompt

    def test_first_generation_says_so(self) -> None:
        prompt = build_prompt(journal=[], thresholds=GateThresholds())

        assert "erste Generation" in prompt

    def test_exit_findings_are_passed_along(self) -> None:
        prompt = build_prompt(
            journal=[],
            thresholds=GateThresholds(),
            exit_findings=["Stop zu weit: 90 % der Gewinner blieben unter 0.30 R"],
        )

        assert "Stop zu weit" in prompt


# ---------------------------------------------------------------------------
#  Kostenbremse
# ---------------------------------------------------------------------------
class TestBudget:
    def test_cost_is_charged(self) -> None:
        budget = Budget(monthly_usd=Decimal("45"))
        client = FakeLLM(json.dumps([VALID_GENOME]), input_tokens=10_000, output_tokens=2_000)

        result = propose(client, journal=[], budget=budget)

        # 10k Eingabe * 15/Mio + 2k Ausgabe * 75/Mio = 0.15 + 0.15
        assert result.cost_usd == Decimal("0.30")
        assert budget.spent_usd == Decimal("0.30")

    def test_exhausted_budget_blocks_the_call(self) -> None:
        """Die Bremse sitzt **vor** dem Aufruf. Eine Auswertung danach haette
        das Geld schon ausgegeben."""
        budget = Budget(monthly_usd=Decimal("45"), spent_usd=Decimal("45"))
        client = FakeLLM(json.dumps([VALID_GENOME]))

        result = propose(client, journal=[], budget=budget)

        assert client.calls == []
        assert result.proposals == []

    def test_exhausted_budget_does_not_stop_trading(self) -> None:
        """Kein Geld fuer Forschung heisst nicht: kein Handel. Der Champion
        laeuft weiter, es kommt nur nichts Neues dazu."""
        budget = Budget(monthly_usd=Decimal("1"), spent_usd=Decimal("1"))

        result = propose(FakeLLM("egal"), journal=[], budget=budget)

        assert result.cost_usd == Decimal(0)  # nichts passiert, kein Fehler

    def test_budget_survives_a_restart(self, tmp_path: Path) -> None:
        path = tmp_path / "budget.json"
        budget = Budget(monthly_usd=Decimal("45"), spent_usd=Decimal("12.50"))
        save_budget(path, budget)

        restored = load_budget(path, monthly_usd=Decimal("45"))

        assert restored.spent_usd == Decimal("12.50")

    def test_corrupt_budget_counts_as_exhausted(self, tmp_path: Path) -> None:
        """Die sichere Richtung: Ein unlesbarer Zaehler darf nicht dazu
        fuehren, dass unbegrenzt weiterbezahlt wird."""
        path = tmp_path / "budget.json"
        path.write_text("{kaputt")

        assert load_budget(path, monthly_usd=Decimal("45")).exhausted

    def test_new_month_resets_the_counter(self, tmp_path: Path) -> None:
        path = tmp_path / "budget.json"
        path.write_text(
            json.dumps({"monthly_usd": "45", "spent_usd": "45", "month": "2020-01"})
        )

        budget = load_budget(path, monthly_usd=Decimal("45"))

        assert budget.spent_usd == Decimal(0)
        assert budget.month == datetime.now(UTC).strftime("%Y-%m")


class TestCycle:
    def test_full_cycle_produces_usable_genomes(self) -> None:
        second = json.loads(json.dumps(VALID_GENOME))
        second["entry_long"][0]["right"]["params"]["period"] = 60
        client = FakeLLM(json.dumps([VALID_GENOME, second]))

        result = propose(client, journal=[], budget=Budget(monthly_usd=Decimal("45")))

        assert len(result.genomes) == 2
        # Und sie sind sofort handelbar - nicht nur syntaktisch gueltig:
        from strategy.compiler import compile_genome

        for genome in result.genomes:
            assert compile_genome(genome).warmup_bars > 0

    def test_journal_reaches_the_model(self) -> None:
        client = FakeLLM(json.dumps([VALID_GENOME]))
        journal = [
            {"candidates": [{"name": "Alter Versuch", "gate_feedback": "- Sharpe: 0.3"}]}
        ]

        propose(client, journal=journal, budget=Budget(monthly_usd=Decimal("45")))

        assert "Alter Versuch" in client.calls[0]["prompt"]


# ---------------------------------------------------------------------------
#  Die Antwort aus einer Datei
# ---------------------------------------------------------------------------
class TestDateiClient:
    """Derselbe Weg, nur ohne Modellaufruf.

    Der springende Punkt dieser Klasse ist ``test_der_weg_bleibt_derselbe``:
    Eine Antwort aus einer Datei darf **nichts** ueberspringen. Waere hier
    eine Abkuerzung eingebaut - eine mildere Pruefung, ein nicht gezaehlter
    Versuch -, dann waere der Analyst nicht benutzbar gemacht, sondern
    umgangen.
    """

    def test_der_weg_bleibt_derselbe(self, tmp_path: Path) -> None:
        """Eine Datei mit einem ungueltigen Vorschlag wird genauso abgelehnt
        wie eine Modellantwort mit demselben Fehler."""
        kaputt = json.loads(json.dumps(VALID_GENOME))
        kaputt["entry_long"][0]["right"]["name"] = "kristallkugel"
        datei = tmp_path / "antwort.json"
        datei.write_text(json.dumps([VALID_GENOME, kaputt]))

        ergebnis = propose(
            DateiClient(datei), journal=[], budget=Budget(monthly_usd=Decimal("45"))
        )

        assert len(ergebnis.genomes) == 1, "Der Unbekannte muss durchfallen"
        assert ergebnis.genomes[0].name == VALID_GENOME["name"]
        # Und er faellt durch, ohne repariert zu werden: Der unbekannte
        # Indikator taucht in keinem angenommenen Genom auf.
        assert "kristallkugel" not in ergebnis.genomes[0].model_dump_json()

    def test_kein_aufruf_kostet_nichts(self, tmp_path: Path) -> None:
        """Was nicht gerufen wurde, wird nicht abgerechnet - sonst waere das
        Forschungsbudget nach ein paar Dateilaeufen leer, ohne dass je ein
        Modell gefragt worden waere."""
        datei = tmp_path / "antwort.json"
        datei.write_text(json.dumps([VALID_GENOME]))
        budget = Budget(monthly_usd=Decimal("45"))

        ergebnis = propose(DateiClient(datei), journal=[], budget=budget)

        assert ergebnis.cost_usd == Decimal(0)
        assert budget.spent_usd == Decimal(0)
        assert budget.remaining_usd == Decimal("45")

    def test_ein_leeres_budget_haelt_die_datei_trotzdem_auf(
        self, tmp_path: Path
    ) -> None:
        """Die Bremse sitzt vor dem Aufruf, nicht vor dem Bezahlen.

        Das ist keine Schikane: Ein aufgebrauchtes Budget heisst "dieser Monat
        hat genug gesucht". Wer daran vorbei will, indem er die Antwort selbst
        hinschreibt, umgeht ein Kriterium - und die Versuche zaehlen trotzdem
        gegen alle kuenftigen Kandidaten.
        """
        datei = tmp_path / "antwort.json"
        datei.write_text(json.dumps([VALID_GENOME]))
        leer = Budget(monthly_usd=Decimal("45"), spent_usd=Decimal("45"))

        ergebnis = propose(DateiClient(datei), journal=[], budget=leer)

        assert ergebnis.genomes == []

    def test_eine_fehlende_datei_faellt_auf(self, tmp_path: Path) -> None:
        """Und zwar laut. Stillschweigend "keine Vorschlaege" zu melden waere
        von "nichts Brauchbares dabei" nicht zu unterscheiden."""
        import pytest

        with pytest.raises(OSError):
            propose(
                DateiClient(tmp_path / "gibtsnicht.json"),
                journal=[],
                budget=Budget(monthly_usd=Decimal("45")),
            )

    def test_der_auftrag_erreicht_die_datei_nicht_ungefragt(
        self, tmp_path: Path
    ) -> None:
        """Der Client bekommt denselben Auftrag wie das Modell - er antwortet
        nur schon. Das ist der Grund, warum ``--auftrag`` existiert: Wer die
        Datei schreibt, soll dieselbe Frage vor sich haben."""
        datei = tmp_path / "antwort.json"
        datei.write_text(json.dumps([VALID_GENOME]))
        client = DateiClient(datei)

        antwort = client.complete(system=SYSTEM_PROMPT, prompt="egal", max_tokens=10)

        assert antwort.input_tokens == 0
        assert antwort.output_tokens == 0
        assert json.loads(antwort.text)[0]["name"] == VALID_GENOME["name"]


class TestDerAuftragWidersprichtSichNicht:
    """Befund 121 - drei feste Zahlen neben gerechneten.

    ``cli vorschlag --auftrag`` zeigt, was die Research-KI zu sehen bekommt.
    Darin standen nebeneinander:

    * Kopf: *"neun Zulassungspruefungen"*
    * Rumpf: *"Von elf Zulassungspruefungen ist genau eine ungeloest"*
    * *"Was bereits versucht wurde: Nichts. Dies ist die erste Generation."*
      - zwei Bildschirmseiten ueber acht namentlich gescheiterten Regeln
    * Eine Schwellenliste mit fuenf Eintraegen, die wie eine vollstaendige
      Liste aussah

    Der Auftrag verlangt in Grundsatz 3 ausdruecklich *"LERNE AUS DEM
    JOURNAL"* - und lieferte die Grundlage dafuer nicht mit.
    """

    def test_die_gate_zahl_wird_abgeleitet(self) -> None:
        import inspect

        from research import gates
        from research.analyst import anzahl_gates

        tatsaechlich = inspect.getsource(gates.evaluate_gates).count("gate_")
        assert anzahl_gates() == tatsaechlich

    def test_der_systemauftrag_nennt_keine_falsche_zahl(self) -> None:
        """Er stand auf "neun", waehrend es elf waren."""
        from research.analyst import SYSTEM_PROMPT, anzahl_gates

        assert f"{anzahl_gates()} Zulassungspruefungen" in SYSTEM_PROMPT
        for falsch in ("neun Zulassungspruefungen", "acht Zulassungspruefungen"):
            assert falsch not in SYSTEM_PROMPT

    def test_ohne_journal_aber_mit_versuchen_keine_erste_generation(self) -> None:
        """Der Widerspruch, um den es geht."""
        from research.analyst import build_prompt
        from research.gates import GateThresholds

        class Lage:
            """Nur das, was dieser Abschnitt braucht.

            ``als_auftrag`` liefert absichtlich einen kurzen Text: Geprueft
            wird der Journal-Abschnitt, nicht die Auftragslage.
            """

            versuche = 198

            def als_auftrag(self) -> str:
                return "## Was tatsaechlich fehlt\n\n(hier nicht geprueft)\n"

        text = build_prompt(
            journal=[], thresholds=GateThresholds(), lage=Lage()
        )
        assert "Nichts. Dies ist die erste Generation." not in text
        assert "198 Versuche sind gezaehlt" in text
        assert "nicht die erste Generation" in text

    def test_ohne_versuche_bleibt_es_die_erste_generation(self) -> None:
        """Die Gegenprobe - bei einem wirklich leeren Projekt stimmt der Satz."""
        from research.analyst import build_prompt
        from research.gates import GateThresholds

        text = build_prompt(journal=[], thresholds=GateThresholds(), lage=None)
        assert "erste Generation" in text

    def test_die_schwellenliste_sagt_dass_sie_unvollstaendig_ist(self) -> None:
        """Wer fuenf Huerden kennt und elf nehmen muss, plant falsch."""
        from research.analyst import anzahl_gates, build_prompt
        from research.gates import GateThresholds

        text = build_prompt(journal=[], thresholds=GateThresholds())
        assert f"(5 der {anzahl_gates()})" in text
        assert f"uebrigen {anzahl_gates() - 5}" in text

    def test_die_ausgelassenen_gates_werden_benannt(self) -> None:
        """Nicht nur "es gibt noch welche", sondern welche."""
        from research.analyst import build_prompt
        from research.gates import GateThresholds

        text = build_prompt(journal=[], thresholds=GateThresholds())
        for stichwort in ("Deflated", "schlechteste Jahr", "Plateau"):
            assert stichwort in text
