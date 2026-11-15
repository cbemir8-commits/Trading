"""Zwei Spot-Gueten in benachbarten Saetzen - Befund 488.

Befund 486 hat in das Urteil von ``cli suchbudget`` einen Absatz gesetzt, der
den Abstand **gepaart** rechnet. Damit standen dort zwei Spot-Gueten
unmittelbar nebeneinander:

    ... Unter Spot-Bedingungen (0.2853 statt 0.2682, kein Funding) ...
    ... die Guete dort bei 0.2708 - Faktor 1.25 ...

5,4 % auseinander, beide "Spot", und kein Satz sagte, woran das liegt. **Das
war mein eigener Einbau**, und genau diese Sorte Doppelzahl bekaempft dieses
Projekt sonst (Befund 234: zwei Fassungen einer Groesse laufen auseinander).

Gemessen, nicht geraten
-----------------------
Der Unterschied ist der **Trade-Satz**, und er ist am laufenden Code
nachgemessen:

    _spotguete(fertige=True )  = 0,2708   = SPOTPUNKT.guete
    _spotguete(fertige=False)  = 0,2853
    SPOTPUNKT.guete (Befund 152) = 0,2708

``fertige=True`` heisst: nur die fertig gehandelten Trades. ``False`` nimmt
die ganze Liste, die am Datenende zwangsweise geschlossenen eingeschlossen.

**Und das Gate nimmt die fertigen** - ``research/gates.py`` seit Befund 152:

    # **Nur fertig gehandelte Trades** (Befund 152). Ein am Datenende ...
    gehandelt = ohne_zensierte(walkforward)

Die 0,2853 ist damit genau die Zahl, die Befund 151/152 aus dem Gate
herausgenommen hat; im Kopf von ``research/randschnitt.py`` steht sie als
0,2848 in der Zeile "Ende gekuerzt 0". Dort trugen in Befund 22
fuenfundzwanzig solcher Randtrades den **ganzen** Vorteil.

Beide Stellen sind trotzdem richtig
-----------------------------------
``cli suchbudget`` **muss** die ganze Liste nehmen: Seine Kandidaten tragen
Zahlen der ganzen Liste, und zwei Zahlen nebeneinander muessen auf derselben
Stichprobe stehen - das ist Befund 390, und der Aufruf nennt ihn. Dasselbe in
``cli form``.

Was fehlte, war also keine Rechnung, sondern die **Angabe des Satzes**. Beide
Saetze nennen ihn jetzt, und diese Datei haelt die Zahlen dahinter fest.

Was die Relation aushaelt
-------------------------
Die Aussage "Spot ist besser als Perpetual" haengt nicht am Trade-Satz:

    fertig        0,2708 / 0,2535 = 1,068
    ganze Liste   0,2853 / 0,2682 = 1,064

Die **Niveaus** liegen rund 6 % hoeher, das **Verhaeltnis** haelt. Der Satz
ueber den Betriebspunkt bleibt also gueltig; nur die Latte darf nicht mit der
hoeheren Guete verglichen werden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.referenz import PERPETUALPUNKT, SPOTPUNKT

WURZEL = Path(__file__).resolve().parents[1]

#: Die beiden gemessenen Gueten des Kassa-Punkts - mit ihrem Trade-Satz.
#:
#: Am laufenden Code nachgemessen (Befund 488), nicht aus einem Bericht
#: abgeschrieben. Wandert eine davon, faellt es hier auf.
GUETEN: dict[str, float] = {
    "fertig": 0.2708,
    "ganze Liste": 0.2853,
}


class TestDieZahlenUndIhreSaetze:
    def test_der_gepflegte_punkt_steht_auf_den_fertigen(self) -> None:
        """Der Beleg fuer den ganzen Befund: 0,2708 ist die Guete der fertig
        gehandelten Trades, und genau sie steht in ``SPOTPUNKT``."""
        assert SPOTPUNKT.guete == pytest.approx(GUETEN["fertig"], abs=1e-4)

    def test_die_ganze_liste_liegt_hoeher(self) -> None:
        """Die Richtung, und sie ist die gefaehrliche: Randtrades schmeicheln.
        In Befund 22 trugen fuenfundzwanzig von ihnen den ganzen Vorteil."""
        assert GUETEN["ganze Liste"] > GUETEN["fertig"]
        assert GUETEN["ganze Liste"] / GUETEN["fertig"] == pytest.approx(
            1.054, abs=5e-3
        )

    def test_das_verhaeltnis_zum_perpetual_haelt(self) -> None:
        """Was der Trade-Satz **nicht** umwirft: die Aussage ueber den
        Betriebspunkt."""
        fertig = SPOTPUNKT.guete / PERPETUALPUNKT.guete
        ganz = 0.2853 / 0.2682

        assert fertig == pytest.approx(1.068, abs=5e-3)
        assert ganz == pytest.approx(1.064, abs=5e-3)
        assert abs(fertig - ganz) < 0.01


class TestDasGateNimmtDieFertigen:
    """Nicht Prosa - die Stelle selbst."""

    def test_die_stelle_steht_im_quelltext(self) -> None:
        quelle = (WURZEL / "research/gates.py").read_text(encoding="utf-8")

        assert "ohne_zensierte(walkforward)" in quelle
        assert "Nur fertig gehandelte Trades" in quelle

    def test_und_der_randschnitt_erklaert_warum(self) -> None:
        kopf = (WURZEL / "research/randschnitt.py").read_text(encoding="utf-8")

        assert "Befund 22" in kopf
        assert "0,244" in kopf and "0,021" in kopf


class TestJedeSpotguteNenntIhrenSatz:
    """Die Regel. Eine zweite Zahl derselben Groesse ist erlaubt - **ohne
    Angabe des Satzes** ist sie es nicht."""

    def _aufrufe(self) -> list[tuple[int, bool | None]]:
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        aus: list[tuple[int, bool | None]] = []
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            f = knoten.func
            if not (isinstance(f, ast.Name) and f.id == "_spotguete"):
                continue
            wert: bool | None = None
            for kw in knoten.keywords:
                if kw.arg == "fertige" and isinstance(kw.value, ast.Constant):
                    wert = bool(kw.value.value)
            aus.append((knoten.lineno, wert))
        return aus

    def test_es_gibt_welche(self) -> None:
        """Nichtleere-Zusicherung (Befund 479)."""
        assert len(self._aufrufe()) >= 3, self._aufrufe()

    def test_jeder_nennt_fertige_ausdruecklich(self) -> None:
        """``fertige`` ist seit Befund 390 ein Pflichtargument - hier wird
        nachgehalten, dass es auch **wortlich** dasteht und nicht
        durchgereicht wird. Wer es nicht sieht, kann die Saetze nicht
        auseinanderhalten."""
        ohne = [z for z, wert in self._aufrufe() if wert is None]

        assert ohne == [], f"ruft _spotguete ohne ausdrueckliches fertige: {ohne}"

    def test_beide_einstellungen_kommen_vor(self) -> None:
        """Sonst waere der Schalter eine Attrappe."""
        werte = {wert for _z, wert in self._aufrufe()}

        assert werte == {True, False}, werte


class TestDasUrteilNenntDieSaetze:
    def _text(self) -> str:
        from research.suchbudget import Budget, Kandidat

        kandidat = Kandidat(
            name="Bestand",
            trades=158,
            sharpe_je_trade=0.2682,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )
        return Budget(
            versuche=203,
            kandidaten=[kandidat],
            spotguete=0.2853,
            betriebspunkt=SPOTPUNKT,
        ).urteil()

    def test_die_ganze_liste_wird_benannt(self) -> None:
        text = self._text()

        assert "ganze" in text
        assert "390" in text

    def test_die_fertigen_auch(self) -> None:
        text = self._text()

        assert "fertig gehandelten" in text
        assert "152" in text

    def test_und_es_steht_da_dass_es_keine_abweichung_ist(self) -> None:
        """Der Punkt des Befundes: Zwei Zahlen sind kein Widerspruch, solange
        jede ihren Satz nennt. Ohne diesen Satz haette der naechste Leser
        gesucht, welche der beiden falsch ist."""
        assert "keine Abweichung" in self._text()
