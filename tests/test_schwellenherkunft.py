"""Sieben Gate-Schwellen waren nackte Zahlen - Befund 437.

``GateThresholds`` nennt die Bedingungen, an denen dieses Projekt jeden
Kandidaten misst. Ein Dutzend davon tragen lange Ableitungen - warum 15 %
Jahresrendite und nicht "die Haelfte der Messlatte", warum -10 % im
schlechtesten Jahr und nicht -12, warum eine Untergrenze an aktiven Fenstern
ueberhaupt. ``min_deflated_sharpe`` traegt sogar eine gemessene Studie
darueber, was die Zahl **bedeutet**, samt dem ausdruecklichen Satz, dass sie
trotzdem stehen bleibt.

**Sieben standen ohne ein Wort da.** Bei sechs erklaeren die Gate-Funktionen
das Verfahren und nicht die Zahl; bei einer (``max_oos_drawdown_pct``) gab es
eine Ableitung, die nur den Docstring des Gates erreichte - dieselbe Luecke,
die Befund 210 verzeichnet hat.

Und bei einer widersprechen Begruendung und Zahl: ``gate_regime_split``
schreibt *"ein Faktor unter 1 zeigt einen echten strukturellen Nachteil"*,
``min_regime_profit_factor`` laesst 0,9 zu.

**Geaendert wurde keine Zahl.** Eine Schwelle anzufassen, deren Herkunft
niemand kennt, ist in beide Richtungen eine Behauptung - und wo der eigene
Kandidat liegt, ist bekannt.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import pathlib

from research.gates import GateThresholds

#: Die Schwellen, wie sie seit Befund 437 stehen. **Diese Liste ist eine
#: Wache gegen das stille Verschieben**, nicht eine zweite Quelle: Wer eine
#: Zahl aendert, muss hier vorbeikommen und es begruenden.
ERWARTET: dict[str, float | int] = {
    "min_oos_trades": 100,
    "min_oos_days_in_market": 250,
    "min_oos_entries": 10,
    "min_benchmark_edge": 1.0,
    "min_cagr_pct": 15.0,
    "min_oos_sharpe": 1.0,
    "max_oos_drawdown_pct": 12.0,
    "min_window_consistency": 0.5,
    "worst_year_pct": -10.0,
    "min_active_windows": 6,
    "min_plateau_ratio": 0.6,
    "max_monte_carlo_drawdown_pct": 15.0,
    "min_regime_profit_factor": 0.9,
    "cost_stress_factor": 2.0,
    "min_deflated_sharpe": 0.95,
}


def _felder_mit_doc() -> dict[str, str]:
    """Je Feld von ``GateThresholds`` sein Docstring - ueber den Syntaxbaum.

    ``dataclasses`` fuehrt Feld-Docstrings nicht, also wird gelesen, was
    dasteht. Nicht ueber Zeilennummern: Wer waehrend eines Suitenlaufs eine
    Datei editiert, bekommt sonst Phantome (Befund 427).
    """
    quelle = pathlib.Path(inspect.getfile(GateThresholds)).read_text()
    for knoten in ast.walk(ast.parse(quelle)):
        if isinstance(knoten, ast.ClassDef) and knoten.name == "GateThresholds":
            koerper = knoten.body
            gefunden: dict[str, str] = {}
            for i, satz in enumerate(koerper):
                if not (
                    isinstance(satz, ast.AnnAssign)
                    and isinstance(satz.target, ast.Name)
                ):
                    continue
                naechst = koerper[i + 1] if i + 1 < len(koerper) else None
                doc = (
                    naechst.value.value
                    if isinstance(naechst, ast.Expr)
                    and isinstance(naechst.value, ast.Constant)
                    and isinstance(naechst.value.value, str)
                    else ""
                )
                gefunden[satz.target.id] = doc
            return gefunden
    raise AssertionError("GateThresholds nicht gefunden")


class TestJedeSchwelleSagtWoherSieKommt:
    def test_keine_steht_ohne_ein_wort_da(self) -> None:
        ohne = sorted(n for n, d in _felder_mit_doc().items() if not d.strip())

        assert ohne == [], ohne

    def test_die_sieben_aus_437_sind_dabei(self) -> None:
        """Gegenprobe gegen einen Waechter, der nichts prueft: Genau diese
        sieben waren nackt."""
        docs = _felder_mit_doc()
        sieben = (
            "min_oos_sharpe",
            "max_oos_drawdown_pct",
            "min_window_consistency",
            "min_plateau_ratio",
            "max_monte_carlo_drawdown_pct",
            "min_regime_profit_factor",
            "cost_stress_factor",
        )

        for name in sieben:
            assert "437" in docs[name], name

    def test_jedes_feld_der_klasse_ist_erfasst(self) -> None:
        """Ein neues Feld soll hier auffallen und nicht durchrutschen."""
        felder = {f.name for f in dataclasses.fields(GateThresholds)}

        assert set(_felder_mit_doc()) == felder
        assert set(ERWARTET) == felder


class TestWasAbgeleitetIstUndWasNicht:
    def test_der_drawdown_nennt_seine_ableitung(self) -> None:
        """Sie gab es - sie erreichte nur den Docstring des Gates und nicht
        den der Zahl (die Luecke aus Befund 210)."""
        doc = _felder_mit_doc()["max_oos_drawdown_pct"]

        assert "Kill-Switch" in doc
        assert "15" in doc
        assert "gate_drawdown" in doc

    def test_die_ohne_ableitung_sagen_das_ausdruecklich(self) -> None:
        """Eine erfundene Begruendung waere schlimmer als keine."""
        docs = _felder_mit_doc()
        ohne_ableitung = (
            "min_oos_sharpe",
            "min_window_consistency",
            "min_plateau_ratio",
            "cost_stress_factor",
        )

        for name in ohne_ableitung:
            assert "ohne verzeichnete Ableitung" in docs[name], name

    def test_der_widerspruch_steht_dran(self) -> None:
        """``gate_regime_split`` argumentiert fuer 1, die Schwelle laesst 0,9
        zu - und beides bleibt, wie es ist."""
        doc = _felder_mit_doc()["min_regime_profit_factor"]

        assert "widersprechen" in doc
        assert "0,9" in doc
        assert "Geaendert wird hier nichts" in doc

    def test_der_monte_carlo_deckel_nennt_die_beobachtung_als_solche(self) -> None:
        doc = _felder_mit_doc()["max_monte_carlo_drawdown_pct"]

        assert "Beobachtung, keine" in doc
        assert "aufgeschrieben hat es niemand" in doc


class TestKeineZahlHatSichBewegt:
    """Der Befund ist eine Auskunft und keine Aenderung."""

    def test_alle_schwellen_stehen_wie_verzeichnet(self) -> None:
        stand = GateThresholds()

        for name, wert in ERWARTET.items():
            assert getattr(stand, name) == wert, name

    def test_die_zwei_offenen_gates_bleiben_offen(self) -> None:
        """Messlatte 14,339 von 15 und Deflated Sharpe 0,5826 von 0,95 -
        wer eine Schwelle senkt, um das zu aendern, hat das Verfahren
        umgekehrt."""
        stand = GateThresholds()

        assert stand.min_deflated_sharpe == 0.95
        assert stand.min_benchmark_edge == 1.0
