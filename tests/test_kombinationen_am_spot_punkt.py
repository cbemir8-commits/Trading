"""Die Aufstellung wird an dem Punkt gewaehlt, an dem gehandelt wird.

**Befund 268.** ``cli marktkombinationen`` faehrt jede Marktkombination durch
die volle Zulassungsstrecke - und rechnete dabei ausschliesslich den
Perpetual-Punkt. Sein eigener Docstring nennt die Frage, um die es geht:
*"Steigt der Deflated Sharpe ueber die Schwelle, faellt womoeglich die
Messlatte darunter - beide Gates zugleich zu halten ist die eigentliche
Frage."*

Am Perpetual-Punkt sind vier Gates offen, am Spot-Punkt zwei. Die Frage stellt
sich dort also anders, und sie wurde am falschen Punkt gestellt.

Der Befehl **sagte** das sogar - eine Zeile ueber dem Bericht steht, dass
'cli stand' den Spot-Punkt daneben zeigt. Rechnen konnte er ihn nicht.

Was hier gehalten wird
----------------------
Dass ``--spot`` beides umstellt - Hebel **und** Funding. Nur eines davon waere
ein halber Spot-Punkt, und ``_betriebspunkt`` haette den Lauf dann zu Recht
weiter 'perpetual' genannt, ohne dass es jemandem auffiele.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _quelle(name: str) -> ast.FunctionDef:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    return next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == name
    )


@pytest.fixture
def quelle() -> str:
    return ast.unparse(_quelle("marktkombinationen"))


class TestDerSpotPunktIstRechenbar:
    def test_es_gibt_das_flag(self) -> None:
        knoten = _quelle("marktkombinationen")
        namen = [a.arg for a in knoten.args.args]

        assert "spot" in namen

    def test_es_nimmt_den_hebel_weg(self, quelle: str) -> None:
        """Spot kennt keinen Hebel."""
        assert "_ohne_hebel(genome)" in quelle

    def test_und_das_funding(self, quelle: str) -> None:
        """Spot kennt kein Funding. Ohne diese Haelfte rechnete '--spot' den
        Vorgabesatz weiter - ein halber Spot-Punkt, den niemand bemerkt."""
        assert "FundingSchedule(default_rate=Decimal('0'))" in quelle

    def test_beide_haengen_am_selben_flag(self) -> None:
        """Die eigentliche Wache: Hebel und Funding duerfen nicht
        auseinanderlaufen. Beide Umstellungen stehen unter einer Bedingung auf
        ``spot`` - eine ohne die andere waere der halbe Punkt."""
        quelle = ast.unparse(_quelle("marktkombinationen"))
        vor_hebel = quelle.split("_ohne_hebel(genome)")[0]

        # Die Zuweisung steht in einem 'if spot:'-Block ...
        assert vor_hebel.rstrip().endswith("if spot:") or "if spot:" in vor_hebel
        # ... und das Funding haengt an derselben Bedingung.
        assert "if spot else {}" in quelle


class TestDerBerichtSagtWelcherPunkt:
    def test_der_betriebspunkt_steht_im_bericht(self, quelle: str) -> None:
        """Sonst saehen zwei Laeufe an verschiedenen Punkten gleich aus."""
        assert "'betriebspunkt': punkt" in quelle

    def test_er_wird_gemessen_und_nicht_gesetzt(self, quelle: str) -> None:
        """``_betriebspunkt`` liest die Konfigurationen. Ein aus dem Flag
        abgeleiteter Text wuerde luegen, sobald das Flag und die Rechnung
        auseinanderlaufen - genau der Fall, den 'test_beide_haengen_am_selben_
        flag' verhindert."""
        assert "_betriebspunkt(genome, configs)" in quelle

    def test_der_hinweis_passt_zum_punkt(self, quelle: str) -> None:
        """Bis Befund 268 stand unter einem Spot-Lauf 'den Spot-Punkt zeigt
        jener daneben'. Der Satz war fuer den einen Fall geschrieben, den es
        gab."""
        assert "if spot else" in quelle
        assert "den Perpetual-Punkt rechnet dieser Befehl" in quelle


class TestDerDocstringNenntDieMessung:
    """Die Messung gehoert dorthin, wo der Befehl aufgerufen wird - sonst
    laeuft jemand fuenfzehn Kombinationen, um sie noch einmal zu finden.

    **Hier stand zuerst das Gegenteil.** Ich hatte 'die Rangfolge aendert sich
    nicht' geschrieben - richtig fuer die vier Aufstellungen, die ich zuerst
    gemessen hatte, und falsch fuer die fuenfzehn des Befehls. Der volle Lauf
    hat es widerlegt, bevor es committet war.
    """

    def test_die_verschiebung_steht_da(self) -> None:
        text = ast.get_docstring(_quelle("marktkombinationen")) or ""

        assert "Rangfolge" in text
        assert "268" in text
        # Die vier, die am gehandelten Punkt ganz anders dastehen.
        assert "ETH+XRP" in text

    def test_und_dass_keine_besteht(self) -> None:
        """Das Ergebnis fuer das Ziel: Breiter zu werden hilft nicht."""
        text = ast.get_docstring(_quelle("marktkombinationen")) or ""

        assert "keine" in text.lower()
        assert "Deflated Sharpe" in text
