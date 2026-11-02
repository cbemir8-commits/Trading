"""Die reibungslose Welt auf Viertelstunden - Befund 453.

Befund 450 hat gefragt, ob die Kopplung zwischen Trade-Zahl und Qualitaet
auf Viertelstunden an den **Signalen** oder an der **Reibung** haengt. Befund
452 hat die Sprosse bei Faktor 2 gefahren und genau gesagt, was sie nicht
entscheidet: Reibung **aufzuschlagen** prueft die falsche Richtung.

Entscheidend ist die Sprosse bei **Faktor 0**. ``CostModel.scaled(0)`` setzt
Gebuehr **und** Slippage auf null - beide sind Parameter der Engine -, und
der Lauf wird neu gefahren, sodass Fuellungen, Stops und Risikogrenzen
mitreagieren (Befund 254/256). Das kann die Rueckrechnung nicht: Sie haelt
die Trades fest und kann die Slippage ohnehin nicht abziehen, weil die im
Ausfuehrungspreis steckt.

Gemessen (39 Stuecke, ein Code-Stand)
--------------------------------------
    Faktor   Regeln   r netto
         0       36    -0,127
         1       36    -0,226

**Die Antwort ist "teils".** Die Reibung hebt **44 %** des Weges zur Null
auf - sie traegt einen sichtbaren Teil. Aber ohne jede Reibung bleibt die
Kopplung bei -0,127, und was uebrig bleibt, haengt an den Signalen.

Und ein zweiter Fund, der die Methode betrifft
-----------------------------------------------
**Der Kippfaktor ist keine Messung.** ``Kostenfrage`` meldet 2,1 - den
Punkt, an dem die Naeherung die Null erreicht. Die Welt, ueber die sie dort
redet, ist jetzt nachgemessen und steht bei -0,127. Schlimmer: Die Naeherung
behauptet ueber **dieselbe** reibungslose Welt je nach f etwas anderes - bei
f = 1 sind es -0,171, bei f = 0 schon -0,226. Vom gemessenen Wert liegt die
erste 0,044 daneben, die zweite **0,099**: Je weiter die Rechnung hinaus
reicht, desto weniger traegt sie.

    Was der Faktor angibt, ist die Reichweite der Rechnung und nicht die der
    Reibung.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

#: Der Code-Stand dieser Leiter - **das** Auswahlkriterium.
#:
#: Nicht das Datum: Ein Glob auf ``2026-11-02_0[2345]*`` haette heute
#: gestimmt und beim naechsten Lauf in derselben Nachtstunde zwei Staende
#: gemischt. Genau so ist der Test zu Befund 452 rot geworden, als diese
#: Leiter neben seiner lag. Siehe ``zwischenstand.stuecke_von``.
ABDRUCK = "b963512ffae9c28e"

ORDNER = "reports/vorratsdecke"

STUECKE, MIT_LATTE = 39, 36

#: Die Kopplung ohne jede Reibung und mit der angesetzten.
OHNE_R, MIT_R, FAKTOR = -0.127, -0.226, 0.0

#: Wie viel Weg zur Null die Reibung aufhebt.
ANTEIL_REIBUNG = 0.44

#: Was die Naeherung ueber dieselbe Welt behauptet - je nach f.
NAEHERUNG_F1, NAEHERUNG_F0 = -0.171, -0.226

#: Wie weit die **schlechteste** Naeherung vom gemessenen Wert liegt.
#:
#: Das ist die Zahl, die das Urteil als "daneben" meldet - nicht der Abstand
#: der beiden Naeherungswerte voneinander. Den hatte ich zuerst gerechnet
#: (0,055) und mein eigener Test hat es gefunden.
ABSTAND = 0.099

#: Und wie weit die mildere Naeherung danebenliegt.
ABSTAND_F1 = 0.044

#: Der Kippfaktor, den die Naeherung meldet.
KIPPFAKTOR = 2.1


def _pfade() -> list[str]:
    from research.zwischenstand import stuecke_von

    return [str(p) for p in stuecke_von(ORDNER, ABDRUCK)]


@pytest.fixture(scope="module")
def urteil() -> str:
    from typer.testing import CliRunner

    from cli import app

    pfade = _pfade()
    if len(pfade) != STUECKE:
        pytest.fail(f"{len(pfade)} Protokolle statt {STUECKE}")
    ergebnis = CliRunner().invoke(
        app, ["vorratsdecke", "-i", "15", "--aus", ",".join(pfade)]
    )
    assert ergebnis.exit_code == 0, ergebnis.output[-1500:]
    return " ".join(ergebnis.output.split())


class TestDieSprosseIstGefahren:
    def test_neununddreissig_protokolle_ein_abdruck(self) -> None:
        """Ausgewaehlt wird ueber den Abdruck - gepruefte Eigenschaft ist
        deshalb die Zahl der Stuecke und dass ``zusammen`` sie nimmt."""
        from research.zwischenstand import zusammen

        pfade = _pfade()
        kopf, _ = zusammen(pfade)

        assert len(pfade) == STUECKE
        assert kopf["code"] == ABDRUCK

    def test_und_zwar_bei_faktor_null(self) -> None:
        faktoren = set()
        for p in _pfade():
            for z in Path(p).read_text().splitlines():
                d = json.loads(z)
                if d.get("ergebnis") == "sprosse":
                    faktoren.add(d["faktor"])

        assert faktoren == {FAKTOR}

    def test_die_sprosse_setzt_gebuehr_und_slippage_auf_null(self) -> None:
        """Der Grund, warum sie entscheidet und die Rueckrechnung nicht."""
        import inspect

        from research import kostenanteil

        quelle = inspect.getsource(kostenanteil)

        assert "CostModel.scaled(0)" in quelle
        assert "setzt Gebuehr **und** Slippage" in quelle


class TestDieKopplungUeberlebtOhneJedeReibung:
    """**Die Antwort auf die offene Frage aus Befund 450.**"""

    def test_das_urteil_nennt_beide_zahlen(self, urteil) -> None:
        assert f"0 {MIT_LATTE} {OHNE_R:+.3f}" in urteil
        assert f"1 {MIT_LATTE} {MIT_R:+.3f}" in urteil

    def test_die_antwort_ist_teils(self, urteil) -> None:
        assert "**Teils.**" in urteil
        assert "ohne sie bleibt die Kopplung negativ" in urteil

    def test_die_reibung_traegt_vierundvierzig_prozent(self, urteil) -> None:
        """Ein sichtbarer Teil - und nicht alles."""
        assert f"hebt {ANTEIL_REIBUNG:.0%} des Weges zur Null auf" in urteil
        gemessen = 1 - OHNE_R / MIT_R

        assert gemessen == pytest.approx(ANTEIL_REIBUNG, abs=0.01)

    def test_was_uebrig_bleibt_haengt_an_den_signalen(self, urteil) -> None:
        assert "Was uebrig bleibt, haengt an den Signalen" in urteil

    def test_ohne_reibung_bleibt_sie_negativ_aber_schwaecher(self) -> None:
        assert OHNE_R < 0
        assert abs(OHNE_R) < abs(MIT_R)


class TestDerKippfaktorIstKeineMessung:
    """**Der zweite Fund, und er betrifft die Methode.** Die Naeherung
    behauptet ueber dieselbe Welt je nach f etwas anderes."""

    def test_das_urteil_sagt_es(self, urteil) -> None:
        assert "Damit ist der Kippfaktor keine Messung" in urteil
        assert f"meldet {KIPPFAKTOR:g}" in urteil

    def test_die_naeherung_widerspricht_sich_selbst(self, urteil) -> None:
        """Ueber **dieselbe** reibungslose Welt: -0,171 bei f = 1, -0,226 bei
        f = 0 - und gemessen steht sie bei -0,127."""
        assert "reibungslose Welt ist eine einzige" in urteil
        assert f"bei f = 1 {NAEHERUNG_F1:+.3f}" in urteil
        assert f"bei f = 0 schon {NAEHERUNG_F0:+.3f}" in urteil
        assert f"{ABSTAND:.3f} daneben" in urteil

    def test_der_abstand_ist_gerechnet_und_nicht_behauptet(self) -> None:
        """**Und zwar der richtige Abstand.** Das Urteil meldet, wie weit die
        schlechteste Naeherung vom **gemessenen** Wert liegt - nicht, wie
        weit die beiden Naeherungen voneinander entfernt sind. Letzteres sind
        0,055, und das hatte ich zuerst gerechnet."""
        assert abs(NAEHERUNG_F0 - OHNE_R) == pytest.approx(ABSTAND, abs=0.001)
        assert abs(NAEHERUNG_F1 - OHNE_R) == pytest.approx(ABSTAND_F1, abs=0.001)
        assert abs(NAEHERUNG_F0 - NAEHERUNG_F1) == pytest.approx(0.055, abs=0.001)
        assert ABSTAND > ABSTAND_F1, "je weiter hinaus, desto schlechter"

    def test_und_die_gemessene_welt_liegt_noch_woanders(self) -> None:
        """Beide Naeherungswerte liegen **unter** dem gemessenen - die
        Rechnung ueberschaetzt die Kopplung der reibungslosen Welt."""
        assert NAEHERUNG_F1 < OHNE_R
        assert NAEHERUNG_F0 < OHNE_R

    def test_was_der_faktor_angibt(self, urteil) -> None:
        assert (
            "Reichweite der Rechnung und nicht die der Reibung" in urteil
        )


class TestDieQuoteWirdAlsSpanneGenannt:
    """Ein Nebenbefund desselben Laufs, und ein sauberer: Die Quote haengt
    daran, wie unabhaengig die 36 Regeln sind - und das Urteil nennt deshalb
    eine Spanne statt einer Zahl."""

    def test_keine_von_sechsunddreissig_raeumt_ihre_latte(self, urteil) -> None:
        assert f"Keine von {MIT_LATTE} raeumt ihre Latte" in urteil

    def test_die_spanne_statt_einer_zahl(self, urteil) -> None:
        assert "Die ehrliche Auskunft ist die Spanne" in urteil
        assert "zwischen 8.0% und 13.9%" in urteil

    def test_und_der_grund_steht_dabei(self, urteil) -> None:
        """36 Regeln sind keine 36 unabhaengigen Ziehungen - strukturell
        zerfallen sie in 20 Gruppen."""
        assert "20 Gruppen" in urteil
        assert "Abwandlung ihrer Nachbarin" in urteil
