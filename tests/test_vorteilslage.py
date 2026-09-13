"""Der Scan vor der Suche - und was er ueber diese Daten sagt.

**Befund 272.** Nach Befund 270 blieb genau eine Richtung uebrig: die
Einstiege. ``cli scan`` misst dort, ohne einen Versuch zu kosten - und fand
auf keiner der vier Kombinationen aus zwei Maerkten und zwei Kerzenlaengen
etwas Belastbares.

Was hier gehalten wird
----------------------
Dass die Messung dort steht, wo jemand sie braucht: im Befehl selbst und im
Eintrag, der den Nutzer zum Wettbewerb schickt. Ein Befund, der nur im
Laborbuch steht, erreicht niemanden, der gerade Versuche ausgeben will - und
Versuche sind nach Befund 269 knapp.

Und die Grenze des Befunds: Er gilt fuer **eine Familie** von Einstiegen und
fuer **diese** Daten. Beides muss dastehen, sonst liest sich ein Nullbefund
wie ein Urteil ueber alles.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.stand import BEIM_NUTZER, GESCHLOSSEN


def _scan_doc() -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == "scan"
    )
    return ast.get_docstring(knoten) or ""


class TestDerBefehlTraegtDieMessung:
    def test_alle_vier_kombinationen_stehen_da(self) -> None:
        text = _scan_doc()

        assert "272" in text
        for stueck in ("BTC", "ETH", "1d", "15m"):
            assert stueck in text

    def test_und_das_urteil(self) -> None:
        text = _scan_doc()

        assert "Kein belastbarer Fund" in text

    def test_die_grenze_des_befunds_steht_dabei(self) -> None:
        """Ein Nullbefund ohne seine Grenze liest sich wie ein Urteil ueber
        alles. Er gilt fuer eine Familie und fuer diese Daten."""
        text = _scan_doc()

        assert "Familie" in text
        assert "Bybit" in text

    def test_das_intervall_wird_nicht_stillschweigend_gewaehlt(self) -> None:
        """Der Bestand steht auf Tageskerzen, die Vorgabe des Befehls ist 15 -
        wer ihn ohne Nachdenken aufruft, misst die andere Kerzenlaenge."""
        text = _scan_doc()

        assert "intervall" in text.lower()
        assert "Tageskerzen" in text


class TestDerNutzerErfaehrtEsVorDerSuche:
    """Der Eintrag, der zum Wettbewerb schickt - dort werden Versuche
    ausgegeben, und dort gehoert die Messung hin."""

    def _wettbewerb(self) -> str:
        return next(
            warum
            for befehl, warum in BEIM_NUTZER
            if "wettbewerb" in befehl and "--ki" not in befehl
        )

    def test_der_befund_wird_genannt(self) -> None:
        assert "272" in self._wettbewerb()

    def test_mit_dem_schluss_daraus(self) -> None:
        text = self._wettbewerb()

        assert "keinen belastbaren Vorteil" in text
        assert "Huerde" in text

    def test_und_mit_seiner_grenze(self) -> None:
        """Auch hier: Es gilt fuer diese Daten."""
        assert "Bybit-Kerzen" in self._wettbewerb()


class TestDasRegisterFuehrtIhn:
    def test_der_eintrag_steht_unter_den_geschlossenen(self) -> None:
        eintrag = next((r for r in GESCHLOSSEN if r.befund == 272), None)

        assert eintrag is not None

    def test_er_nennt_alle_vier_messungen(self) -> None:
        eintrag = next(r for r in GESCHLOSSEN if r.befund == 272)

        for zahl in ("+3,69", "+2,88", "-3,99", "+3,02"):
            assert zahl in eintrag.ergebnis

    def test_und_was_er_nicht_deckt(self) -> None:
        eintrag = next(r for r in GESCHLOSSEN if r.befund == 272)

        assert "nicht gemessen" in eintrag.ergebnis
        assert "Bybit" in eintrag.ergebnis


@pytest.mark.parametrize("markt,kerze", [("BTC", "1d"), ("ETH", "15m")])
def test_keine_kombination_fehlt_im_docstring(markt: str, kerze: str) -> None:
    """Eine Tabelle, in der eine Zeile fehlt, liest sich wie ein
    vollstaendiges Bild und ist keines."""
    text = _scan_doc()
    zeilen = [z for z in text.splitlines() if markt in z and kerze in z]

    assert zeilen, f"{markt} {kerze} fehlt in der Tabelle."


class TestDasLaborbuchBleibtLesbar:
    """**Die Luecke, die dieser Befund aufgedeckt hat.**

    ``research/nachmessung.abschnitte`` baute seine Wortliste aus
    ``range(1, 200)``. Seit das Laborbuch die Zweihundert ueberschritten hat,
    war damit jeder Abschnitt darueber unsichtbar - und mit ihm jede Wache,
    die darauf aufbaut. Aufgefallen ist es erst am ersten geschlossenen
    Suchweg jenseits von 199, dessen Fundstelle deshalb ins Leere zeigte.

    Dieselbe Grenze war in ``test_stand`` schon einmal hochgesetzt worden -
    eine Zahl an zwei Stellen, von denen eine gepflegt wurde.
    """

    def _nummern(self) -> set[int]:
        from research.nachmessung import abschnitte

        return {a.nummer for a in abschnitte(Path("strategies/BEFUND.md").read_text())}

    def test_der_neueste_abschnitt_wird_gesehen(self) -> None:
        from research.stand import GESCHLOSSEN

        assert max(r.massgeblich for r in GESCHLOSSEN) in self._nummern()

    def test_und_die_abschnitte_jenseits_von_199(self) -> None:
        """Die Zahl, an der es hing - hier ausdruecklich."""
        assert max(self._nummern()) > 199

    def test_die_wortliste_steht_nicht_auf_einer_zahl(self) -> None:
        """Sie waechst mit ``zahlwort`` statt mit einem gepflegten Bereich.

        Geprueft wird der **Rumpf**, nicht die Quelle: Der Docstring erklaert
        den alten ``range(1, 200)`` und darf ihn nennen duerfen, ohne dass
        diese Wache anschlaegt.
        """
        import inspect

        from research import nachmessung

        baum = ast.parse(inspect.getsource(nachmessung._nach_wort))
        fn = next(k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef))
        rumpf = "\n".join(
            ast.unparse(k)
            for k in fn.body
            if not (isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant))
        )

        assert "range(" not in rumpf
        assert "while" in rumpf

    def test_das_laborbuch_waechst_nicht_ueber_seine_benennung_hinaus(self) -> None:
        """**Die Wache mit Vorlauf.** Oberhalb von ``zahlwort`` bekaeme ein
        Befund keine Ueberschrift, die der Parser lesen kann - er waere
        stumm, ohne dass etwas rot wird. Zwanzig Befunde vorher schlaegt es
        an, damit die Tabelle rechtzeitig erweitert wird."""
        from research.nachmessung import hoechste_benennbare

        grenze = hoechste_benennbare()
        neuester = max(self._nummern())

        assert neuester <= grenze - 20, (
            f"Laborbuch bei {neuester}, benennbar nur bis {grenze} - "
            f"'zahlwort' erweitern, bevor die Abschnitte stumm werden."
        )
