"""Die Reibungsleiter auf Viertelstunden, Sprosse 2 - Befund 452.

Befund 450 hat eine Frage offen gelassen: Haengt die Kopplung zwischen
Trade-Zahl und Qualitaet auf Viertelstunden an den **Signalen** oder an der
**Reibung**? Die Ruerckrechnung konnte es nicht entscheiden:

    Rechnet man die Gebuehr zurueck, geht die Korrelation von -0,226 auf
    -0,171. Bei 2-facher Gebuehr verschwindet sie - das waeren rund 0,1 % je
    Roundtrip. Das liegt in der Reichweite dessen, was allein die Slippage
    ausmachen kann - und die steckt im Ausfuehrungspreis, laesst sich aus den
    Trades also nicht abziehen.

Die **Leiter** kann, was die Rueckrechnung nicht kann: Sie faehrt den
Backtest neu, mit ``CostModel.scaled(k)``, und skaliert damit Gebuehr **und**
Slippage - Fuellungen, Stops und Risikogrenzen reagieren mit (Befund
254/256).

Gemessen (39 Stuecke, ein Code-Stand, 3,5 Stunden)
--------------------------------------------------
    Faktor   Regeln   r netto
         1       36    -0,226
         2       36    -0,240

**Was das widerlegt**: den Satz *"bei 2-facher Gebuehr verschwindet sie"* als
Aussage ueber gemessene doppelte Reibung. Gemessen wird die Kopplung dort
**staerker**, nicht null - mehr Reibung trifft die haeufig handelnden Regeln
haerter, und genau das ist die Kopplung. Die lineare Rueckrechnung traegt
nicht.

**Was das nicht widerlegt** - und das ist der Punkt, an dem ich beinahe zu
viel behauptet haette: Die Hypothese hinter jenem Satz lautet *"die wahre
Reibung ist etwa doppelt so hoch wie angesetzt, und die Kopplung ist ganz
davon"*. Reibung **aufzuschlagen** prueft die falsche Richtung; dass mehr
Reibung mehr Kopplung macht, ist mit beiden Hypothesen vereinbar.

Entscheidend ist die Sprosse bei **Faktor 0**, und das Modul ist dafuer
gebaut: ``Reibungsleiter.urteil`` hat einen Zweig, der die gemessene
reibungslose Welt gegen ``brutto(f)`` haelt - *"behauptet ueber dieselbe Welt
je nach f etwas anderes"*. Dieser Zweig ist hier **nicht** gelaufen, und
dieser Test sichert, dass das Urteil es auch nicht behauptet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

#: Der Code-Stand dieser Leiter - **das** Auswahlkriterium.
#:
#: Hier stand ein Datums-Glob (``2026-11-01_2*`` und ``2026-11-02_*``), und
#: der war richtig, solange nur diese Leiter im Ordner lag. Am naechsten
#: Morgen hat Befund 453 die Faktor-0-Leiter auf denselben Ordner gefahren,
#: und derselbe Glob lieferte 78 Stuecke aus zwei Staenden - der Test war rot,
#: obwohl beide Messungen stimmten. Siehe ``zwischenstand.stuecke_von``.
ABDRUCK = "bfcaf92e158b4874"

ORDNER = "reports/vorratsdecke"

STUECKE, MIT_LATTE = 39, 36

#: Die gemessene Kopplung: Grundlauf und Sprosse.
GRUND_R, SPROSSE_R, FAKTOR = -0.226, -0.240, 2.0


def _pfade() -> list[str]:
    return _andere_leiter(ABDRUCK)


def _andere_leiter(abdruck: str) -> list[str]:
    from research.zwischenstand import stuecke_von

    return [str(p) for p in stuecke_von(ORDNER, abdruck)]


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


class TestDieLeiterIstGefahrenUndAufEinemStand:
    def test_neununddreissig_protokolle_ein_abdruck(self) -> None:
        """Die Auswahl geht ueber den Abdruck, also ist "ein Stand" keine
        Zusicherung mehr, sondern die Bauart. Gepruefte Eigenschaft ist
        deshalb: Es sind **39** Stuecke, und ``zusammen`` nimmt sie."""
        from research.zwischenstand import zusammen

        pfade = _pfade()
        kopf, _ = zusammen(pfade)

        assert len(pfade) == STUECKE
        assert kopf["code"] == ABDRUCK

    def test_und_die_andere_leiter_ist_nicht_dabei(self) -> None:
        """**Der Fehlgriff aus Befund 454, festgehalten.** Beide Leitern
        liegen im selben Ordner, und die eine lief in der Nachtstunde nach
        der anderen - nach dem Datum ausgewaehlt waeren es 78 Stuecke."""
        from tests.test_reibungslos_feinkerzen import ABDRUCK as ANDERE

        meine, andere = set(_pfade()), set(_andere_leiter(ANDERE))

        assert ABDRUCK != ANDERE
        assert len(andere) == STUECKE
        assert meine & andere == set()

    def test_jedes_handelnde_stueck_traegt_grundlauf_und_sprosse(self) -> None:
        """Die Sprosse allein waere keine Messung - verglichen wird gegen
        den Grundlauf **desselben** Stuecks.

        **Ausser bei den drei Genomen ohne Trades.** Eine Regel, die nicht
        handelt, hat keine Sprosse zu messen; sie steht mit 'kein Kandidat'
        und null Trades da. Mein Test hat sie zuerst mitverlangt - zu streng,
        und der Code hatte recht.
        """
        ohne_sprosse, ohne_kandidat = [], []
        for p in _pfade():
            arten = {
                json.loads(z).get("ergebnis")
                for z in Path(p).read_text().splitlines()
                if json.loads(z).get("art") == "messung"
            }
            if "kein Kandidat" in arten:
                ohne_kandidat.append(Path(p).name)
            elif "sprosse" not in arten:
                ohne_sprosse.append(Path(p).name)

        assert ohne_sprosse == [], ohne_sprosse
        assert len(ohne_kandidat) == STUECKE - MIT_LATTE, ohne_kandidat

    def test_es_ist_genau_eine_sprosse_bei_faktor_zwei(self) -> None:
        faktoren = set()
        for p in _pfade():
            for z in Path(p).read_text().splitlines():
                d = json.loads(z)
                if d.get("ergebnis") == "sprosse":
                    faktoren.add(d["faktor"])

        assert faktoren == {FAKTOR}


class TestMehrReibungMachtDieKopplungStaerker:
    def test_das_urteil_nennt_beide_zahlen(self, urteil) -> None:
        assert f"1 {MIT_LATTE} {GRUND_R:+.3f}" in urteil
        assert f"{FAKTOR:g} {MIT_LATTE} {SPROSSE_R:+.3f}" in urteil

    def test_und_sagt_dass_sie_nicht_zur_null_kommt(self, urteil) -> None:
        assert "bringt die Kopplung bis Faktor 2 nicht zur Null" in urteil

    def test_und_dass_sie_staerker_wird(self, urteil) -> None:
        """Nicht schwaecher - mehr Reibung trifft die haeufig handelnden
        Regeln haerter, und genau das ist die Kopplung."""
        assert "nicht schwaecher, sondern **staerker**" in urteil

    def test_die_sprosse_ist_ein_ganzer_lauf(self, urteil) -> None:
        """Der Unterschied zur Rueckrechnung: Fuellungen, Stops und
        Risikogrenzen reagieren mit (Befund 254/256)."""
        assert "CostModel.scaled(k)" in urteil
        assert "reagieren mit" in urteil


class TestDieFrageIstDamitNichtEntschieden:
    """**Die Zusicherung gegen meine eigene Versuchung.** Das Ergebnis liest
    sich wie eine Widerlegung der Reibungshypothese, und es ist keine:
    Aufschlagen prueft die falsche Richtung."""

    def test_das_urteil_behauptet_keine_entscheidung(self, urteil) -> None:
        assert "nicht entschieden" in urteil
        assert "das Urteil von dort gilt hier nicht" in urteil

    def test_die_reibungslose_welt_ist_nicht_gemessen(self, urteil) -> None:
        """Der Zweig, der entscheiden wuerde, ist nicht gelaufen - also
        steht sein Satz auch nicht da."""
        assert "reibungslose Welt ist eine einzige" not in urteil

    def test_und_die_rueckrechnung_steht_weiter_daneben(self, urteil) -> None:
        """Beide Absaetze bleiben im Bericht: die Rueckrechnung mit ihrem
        Kippfaktor 2 und die gemessene Sprosse. Wer sie nebeneinander liest,
        sieht den Unterschied zwischen Naeherung und Lauf."""
        assert "Hier koennten es die Kosten sein" in urteil
        assert "Bei **2-facher Gebuehr** verschwindet sie" in urteil

    def test_der_entscheidende_faktor_ist_null(self) -> None:
        """``CostModel.scaled(0)`` setzt Gebuehr **und** Slippage auf null -
        das steht so im Modul, und genau das ist die offene Messung."""
        import inspect

        from research import kostenanteil

        quelle = inspect.getsource(kostenanteil)

        assert "CostModel.scaled(0)" in quelle
        assert "setzt Gebuehr **und** Slippage" in quelle
