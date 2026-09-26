"""Die Wache sieht jetzt auch die Entscheidungen an - Befund 335.

Befund 130 hat die Suche gebaut: Wo wird eine Richtung **nach** ihrer
massgeblichen Fundstelle noch erwaehnt? Befund 294 hat gefunden, dass sie nur
``GESCHLOSSEN`` ansah - 39 von 208 Eintraegen - und sie auf ``OFFEN``
erweitert, mit einer Zeile am Schluss, die nennt was sie **nicht** ansieht: die
behobenen.

Nachgesehen (335), was in dieser Rechnung fehlt:

    GESCHLOSSEN         40   durchsucht
    OFFEN               16   durchsucht
    BEHOBEN            184   genannt
    AUFTRAG              5   in der Summe nicht vorgekommen
    ENTSCHEIDUNGEN      10   in der Summe nicht vorgekommen
    BEIM_NUTZER          6   in der Summe nicht vorgekommen

Die **Entscheidungen** sind die Eintraege, auf die der Nutzer handelt, und ihre
Fundstellen reichen bis Befund 69 zurueck - 265 Befunde. Sie standen in keiner
der beiden Listen: nicht bei den durchsuchten, nicht bei den genannten.

Neun der zehn tragen eine Fundstelle und werden seither durchsucht.
'Wochenverlustgrenze' bleibt draussen, und das ist kein Rest: Ohne Erstmessung
gilt **jeder** spaetere Abschnitt als spaeter, und eine Wache, die alles meldet,
meldet nichts.

Was dabei herauskommt, sind Verdachtsfaelle und keine Befunde - so steht es im
Bericht, und so ist es gemeint. Der Wert liegt darin, dass sie ueberhaupt
auftauchen: 'Umfang des Kosten-Stress-Tests' steht auf Befund 96 und wird in
Befund 314 wieder erwaehnt.
"""

from __future__ import annotations

import pytest

from research.nachmessung import BEGRIFFE, ENTSCHEIDUNGSBEGRIFFE, spuren
from research.stand import (
    AUFTRAG,
    BEHOBEN,
    BEIM_NUTZER,
    ENTSCHEIDUNGEN,
    GESCHLOSSEN,
    OFFEN,
)

MIT_FUNDSTELLE = tuple(e for e in ENTSCHEIDUNGEN if e.befund)


class TestEineEntscheidungPasstInDieSuche:
    """``spuren`` braucht ``name``, ``befund`` und ``massgeblich``. Zwei davon
    hatte ``Entscheidung`` schon."""

    def test_name_ist_die_frage(self) -> None:
        for e in ENTSCHEIDUNGEN:
            assert e.name == e.frage

    def test_massgeblich_ist_die_juengste_fundstelle(self) -> None:
        for e in MIT_FUNDSTELLE:
            assert e.massgeblich == (e.zuletzt or e.befund)

    def test_die_suche_laeuft_ohne_anpassung_durch(self) -> None:
        gefunden, ohne = spuren(
            "## Eins. Nichts\n", MIT_FUNDSTELLE,
            {**BEGRIFFE, **ENTSCHEIDUNGSBEGRIFFE},
        )

        assert ohne == ()
        assert len(gefunden) == len(MIT_FUNDSTELLE)


class TestJedeEntscheidungMitFundstelleHatBegriffe:
    """**Die Wache um die Wache.** Eine neue Entscheidung ohne Begriffe waere
    eine Luecke, die niemand sieht - genau die Lage vor Befund 294."""

    def test_keine_bleibt_ohne(self) -> None:
        fehlen = sorted(
            e.frage for e in MIT_FUNDSTELLE
            if not ENTSCHEIDUNGSBEGRIFFE.get(e.frage)
        )

        assert fehlen == [], (
            f"ohne Suchbegriffe: {fehlen} - sie stehen in "
            f"research/nachmessung.ENTSCHEIDUNGSBEGRIFFE"
        )

    def test_und_keine_begriffe_ohne_entscheidung(self) -> None:
        verwaist = sorted(
            set(ENTSCHEIDUNGSBEGRIFFE) - {e.frage for e in ENTSCHEIDUNGEN}
        )

        assert verwaist == []

    def test_die_ohne_fundstelle_bleibt_bewusst_draussen(self) -> None:
        """Ohne Erstmessung gilt jeder Abschnitt als spaeter."""
        ohne = [e for e in ENTSCHEIDUNGEN if not e.befund]

        assert len(ohne) == 1
        assert ohne[0].frage == "Wochenverlustgrenze"
        assert ohne[0].frage not in ENTSCHEIDUNGSBEGRIFFE


class TestDieRechnungGehtAuf:
    """Befund 294 nannte die behobenen als das Unbesehene - und liess drei
    Register aus der Summe fallen."""

    def test_durchsucht_plus_genannt_ist_das_ganze_register(self) -> None:
        durchsucht = len(GESCHLOSSEN) + len(OFFEN) + len(MIT_FUNDSTELLE)
        genannt = (
            len(BEHOBEN)
            + len(AUFTRAG)
            + len(BEIM_NUTZER)
            + len([e for e in ENTSCHEIDUNGEN if not e.befund])
        )
        ganz = (
            len(GESCHLOSSEN)
            + len(OFFEN)
            + len(BEHOBEN)
            + len(AUFTRAG)
            + len(ENTSCHEIDUNGEN)
            + len(BEIM_NUTZER)
        )

        assert durchsucht + genannt == ganz

    def test_der_befehl_nennt_alle_vier_register(self) -> None:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "register"
        )

        for name in ("BEHOBEN", "AUFTRAG", "BEIM_NUTZER", "ENTSCHEIDUNGEN"):
            assert name in quelle, name

    def test_und_durchsucht_die_entscheidungen(self) -> None:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "register"
        )

        assert "ENTSCHEIDUNGSBEGRIFFE" in quelle
        assert "if e.befund" in quelle, "die ohne Fundstelle bleiben draussen"


@pytest.mark.parametrize("eintrag", MIT_FUNDSTELLE, ids=lambda e: e.frage[:28])
def test_die_begriffe_treffen_das_laborbuch(eintrag) -> None:
    """Begriffe, die nirgends vorkommen, sind eine stille Luecke: Die Wache
    laeuft, findet nichts und sieht aus wie ein Freispruch.

    Gefragt ist nicht ein Treffer **nach** der Fundstelle - das waere ein
    Verdachtsfall und muss nicht sein -, sondern dass die Worte im Laborbuch
    ueberhaupt vorkommen.
    """
    from pathlib import Path

    text = Path("strategies/BEFUND.md").read_text(encoding="utf-8")
    worte = ENTSCHEIDUNGSBEGRIFFE[eintrag.frage]

    assert any(w in text for w in worte), (
        f"keiner der Begriffe {worte} steht im Laborbuch - dann prueft die "
        f"Wache fuer '{eintrag.frage}' nichts"
    )
