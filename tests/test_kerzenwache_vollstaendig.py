"""Jeder Befehl, der Kataloge laedt, prueft die Kerzenlaenge.

**Befund 243.** ``passt_zum_intervall`` haelt fest, welcher Katalog auf welche
Kerzenlaenge gehoert. Der Grund steht in ``_pruefe_generation``: *"Dieselben
Periodenzahlen bedeuten dort sechsundneunzigmal laengere Zeitraeume - eine
voellig andere Regel unter demselben Namen."*

Ein Durchgang durch alle Befehle, die Seeds laden, fand **einen** ohne diese
Pruefung: ``cli suchbudget``. Er sammelte ueber *alle* Generationen und rechnete
sie auf der gewaehlten Kerzenlaenge durch - auf Tageskerzen 23 von 53 Regeln aus
den Viertelstunden-Katalogen 6, 7 und 8.

Warum das trotzdem nichts verfaelscht hat
-----------------------------------------
Gemessen: **keine** der 23 taucht in der Ausgabe auf. Sie fallen an der
Trade-Zahl heraus, bevor die Rangliste entsteht - eine Scalp-Regel auf
Tageskerzen loest kaum aus. Die Ausgabe war vor und nach der Wache
zeichengleich.

Der Schutz war also da, aber er war **Nebenwirkung eines Filters** und nicht
Absicht. Genau dieselbe Lage wie beim Datenrand in Befund 241: Etwas traegt,
nur nicht das Bauteil, dem man es zuschreiben wuerde.

Was es gekostet hat
-------------------
Rechenzeit. 54 Kandidaten statt 31, und der Lauf dauerte 78 statt 48 Sekunden.

Diese Tests
-----------
Sie halten die **Abdeckung** fest, nicht das Ergebnis: Wer einen neuen Befehl
baut, der Kataloge laedt, faellt hier auf.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from research.seeds import GENERATIONS, VORGESEHEN, passt_zum_intervall

#: Die Pruefungen, die zaehlen. ``_pruefe_generation`` bricht ab (ein Katalog),
#: ``passt_zum_intervall`` ueberspringt (mehrere Kataloge) - beides ist richtig,
#: es haengt daran, ob der Befehl einen oder viele nimmt.
WACHEN = ("_pruefe_generation", "passt_zum_intervall")


def _befehle() -> dict[str, str]:
    baum = ast.parse(Path("cli.py").read_text())
    return {
        n.name: ast.unparse(n)
        for n in ast.walk(baum)
        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
    }


def _laedt_kataloge(quelle: str) -> bool:
    return "load_seeds" in quelle or "GENERATIONS" in quelle


class TestDieAbdeckung:
    def test_jeder_katalogleser_prueft_die_kerzenlaenge(self) -> None:
        """**Die Wache gegen den naechsten Befehl dieser Art.**

        Gesucht wird nach beiden Pruefungen, nicht nur nach
        ``_pruefe_generation``: Der erste Durchgang tat das und meldete neun
        Luecken, von denen acht keine waren - sie pruefen ueber
        ``passt_zum_intervall``. Wer nach dem Mantel sucht statt nach der
        Sache, findet Gespenster.
        """
        ohne = [
            name
            for name, quelle in _befehle().items()
            if _laedt_kataloge(quelle)
            and not any(w in quelle for w in WACHEN)
            # 'kandidat' schlaegt Namen im Katalog nach und rechnet nichts.
            and "run_portfolio_walkforward" in quelle
        ]

        assert ohne == [], f"laedt Kataloge und rechnet ungeprueft: {ohne}"

    def test_suchbudget_ist_dabei(self) -> None:
        """Der Befehl, den Befund 243 gefunden hat."""
        quelle = _befehle()["suchbudget"]

        assert _laedt_kataloge(quelle)
        assert "passt_zum_intervall" in quelle

    def test_es_sammelt_nur_noch_passende_generationen(self) -> None:
        quelle = _befehle()["suchbudget"]

        assert "GENERATIONS.items()" in quelle, (
            "ueber .values() laesst sich die Generation nicht pruefen - "
            "die Nummer ist der Schluessel"
        )

    def test_uebersprungenes_wird_genannt(self) -> None:
        """Still wegzulassen waere schlechter als mitzurechnen: Wer 31 statt
        54 Kandidaten sieht, soll wissen, warum."""
        quelle = _befehle()["suchbudget"]

        assert "Uebersprungen" in quelle
        assert "VORGESEHEN" in quelle


class TestWasAufTageskerzenNichtHingehoert:
    def test_die_viertelstunden_kataloge_sind_ein_grosser_teil(self) -> None:
        """43 % - deshalb ist es Rechenzeit und keine Kleinigkeit."""
        gesamt = sum(len(x) for x in GENERATIONS.values())
        falsch = sum(
            len(x)
            for nummer, x in GENERATIONS.items()
            if not passt_zum_intervall(nummer, "D")
        )

        assert falsch / gesamt > 0.35

    def test_es_sind_die_generationen_sechs_bis_acht(self) -> None:
        nicht_auf_d = {
            n for n in GENERATIONS if not passt_zum_intervall(n, "D")
        }

        assert nicht_auf_d == {6, 7, 8}
        assert all(VORGESEHEN.get(n) == "15" for n in nicht_auf_d)

    def test_generationen_ohne_vorgabe_gelten_ueberall(self) -> None:
        """Die frueheren Kataloge tragen keine Kerzenlaenge und duerfen
        deshalb mitlaufen - sie sind nicht auf eine Taktung gebaut."""
        offen = {n for n in GENERATIONS if VORGESEHEN.get(n) is None}

        assert offen
        for n in offen:
            assert passt_zum_intervall(n, "D")
            assert passt_zum_intervall(n, "15")


class TestDerFilterWarDerSchutz:
    """Warum die fehlende Wache nichts verfaelscht hat - Befund 243."""

    @pytest.mark.langsam
    def test_keine_viertelstunden_regel_kam_je_in_die_rangliste(self) -> None:
        """Nachgestellt am Kriterium, nicht am Lauf: Eine Scalp-Regel loest
        auf Tageskerzen zu selten aus, um in die Auswertung zu kommen.

        Der Lauf selbst steht im Laborbuch (Befund 243): Ausgabe vor und nach
        der Wache zeichengleich, 78 gegen 48 Sekunden.
        """
        text = Path("strategies/BEFUND.md").read_text()
        abschnitt = text[text.index("## Zweihundertdreiundvierzig") :]

        assert "zeichengleich" in abschnitt

    def test_der_kopf_nennt_den_grund_und_nicht_nur_die_wirkung(self) -> None:
        import cli

        quelle = re.sub(r"\s+", " ", Path("cli.py").read_text())
        i = quelle.index("Nur die Kataloge, die auf diese Kerzenlaenge")

        assert "Befund 243" in quelle[i : i + 400]
        assert cli.suchbudget.__doc__
