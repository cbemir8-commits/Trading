"""Die reibungslose Welt auf Tageskerzen - Befund 456.

Die Frage
---------
Befund 453 hat die Sprosse bei Faktor 0 auf **Viertelstunden** gefahren und
gemessen, dass die Reibung 44 % der Kopplung traegt. Auf Tageskerzen ist die
Kopplung aber nicht die Zahl, an der etwas haengt - Befund 290:

    Die Qualitaet je Trade faellt mit der Menge (rho = -0,679, t = -3,70),
    aber die **Guete** haengt nicht daran (rho = +0,072, t = +0,29). Was
    fehlt, fehlt an der Guete.

Gefragt ist also nicht die Kopplung, sondern die **Luecke**: Wie weit ist die
naechste Regel von ihrer Latte, und bewegt sich das ohne jede Reibung? Und
zwar auf der Kerzenlaenge, die den Spot-Punkt traegt.

Gemessen (25 Genome, ein Code-Stand)
------------------------------------
    Faktor   Regeln   beste Guete   Latte   fehlt
         0       13         2,297   3,358   1,061
         1       13         2,484   3,564   1,080

**Nein: 1,8 %.** Billiger zu handeln bewegt diese Decke nicht. Damit ist eine
weitere Erklaerung fuer die Luecke ausgeschlossen, und zwar durch einen Lauf
statt durch eine Rechnung.

Und warum die Guete nicht zu rechnen war
----------------------------------------
Die Sprosse hielt bisher nur ``sr_je_trade`` fest. Die Guete ist ``SR`` mal
Wurzel aus ``n_eff``, und ``n_eff`` ist nicht die Trade-Zahl. Gemessen:
**alle 13** Regeln handeln ohne Reibung dieselbe Zahl von Trades, aber **3
von 13** haben ein anderes ``n_eff`` (59 -> 60, 86 -> 91, 45 -> 46). Wer die
Guete aus der Trade-Zahl gerechnet haette, haette fuer drei Regeln die
falsche Latte benutzt - deshalb wird ``n_eff`` je Sprosse jetzt **gemessen**.

Dass die naechste Regel wechselt, haengt genau daran: Mit Reibung ist es
'Donchian-Ausbruch 55/20', ohne sie 'Trend-Beteiligung 50 Tage'. Beide Seiten
der Luecke bewegen sich.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

#: Der Code-Stand dieser Messung - **das** Auswahlkriterium (Befund 454).
ABDRUCK = "edd44cf339a95ce8"

ORDNER = "reports/vorratsdecke"

#: Die Zahlen des Berichts.
MIT_LATTE = 13
LUECKE_FREI, LUECKE_BETRIEB = 1.061, 1.080
ANTEIL = 0.018

#: Die naechste Regel - und sie ist nicht dieselbe.
NAH_FREI = "Trend-Beteiligung 50 Tage"
NAH_BETRIEB = "Donchian-Ausbruch 55/20"

#: Trade-Zahl und n_eff ohne Reibung: gleich viele Trades, nicht gleiches
#: n_eff. Der Grund, warum die Guete gemessen und nicht gerechnet wird.
GLEICHE_TRADES, GLEICHES_NEFF = 13, 10


def _pfade() -> list[str]:
    from research.zwischenstand import stuecke_von

    return [str(p) for p in stuecke_von(ORDNER, ABDRUCK)]


@pytest.fixture(scope="module")
def urteil() -> str:
    from typer.testing import CliRunner

    from cli import app

    pfade = _pfade()
    if len(pfade) != 1:
        pytest.fail(f"{len(pfade)} Protokolle mit Abdruck {ABDRUCK}, erwartet 1")
    ergebnis = CliRunner().invoke(app, ["vorratsdecke", "-i", "D", "--aus", pfade[0]])
    assert ergebnis.exit_code == 0, ergebnis.output[-2000:]
    return " ".join(ergebnis.output.split())


@pytest.fixture(scope="module")
def zeilen() -> tuple[dict, dict]:
    """Grundlauf und Sprosse je Regel, aus dem Protokoll."""
    pfade = _pfade()
    if len(pfade) != 1:
        pytest.fail(f"{len(pfade)} Protokolle mit Abdruck {ABDRUCK}, erwartet 1")
    basis: dict[str, dict] = {}
    sprosse: dict[str, dict] = {}
    for s in Path(pfade[0]).read_text(encoding="utf-8").splitlines()[1:]:
        d = json.loads(s)
        if d.get("ergebnis") == "gemessen":
            basis[d["regel"]] = d
        elif d.get("ergebnis") == "sprosse" and d.get("n_eff") is not None:
            sprosse[d["regel"]] = d
    return basis, sprosse


class TestDieSprosseTraegtJetztEineDecke:
    def test_jede_sprosse_hat_n_eff_und_guete(self, zeilen) -> None:
        """Das ist die Messung, die 456 hinzufuegt. Ohne sie steht in der
        Leiter nur die Kopplung."""
        _, sprosse = zeilen

        assert len(sprosse) == MIT_LATTE
        for d in sprosse.values():
            assert d["n_eff"] > 0
            assert d["guete"] is not None
            assert d["faktor"] == 0.0

    def test_die_guete_der_sprosse_ist_sr_mal_wurzel_n_eff(self, zeilen) -> None:
        """Und zwar mit **ihrem eigenen** n_eff, nicht dem des Grundlaufs."""
        _, sprosse = zeilen

        for d in sprosse.values():
            erwartet = d["sr_je_trade"] * d["n_eff"] ** 0.5
            assert d["guete"] == pytest.approx(erwartet, rel=1e-9)

    def test_gleiche_trades_aber_nicht_gleiches_n_eff(self, zeilen) -> None:
        """**Der Grund, warum sie gemessen werden musste.** Haette man die
        Guete aus der Trade-Zahl gerechnet, stuende fuer drei Regeln die
        falsche Latte da."""
        basis, sprosse = zeilen
        gleiche_trades = sum(
            1 for n, d in sprosse.items() if basis[n]["trades"] == d["trades"]
        )
        gleiches_neff = sum(
            1 for n, d in sprosse.items() if basis[n]["n_eff"] == d["n_eff"]
        )

        assert gleiche_trades == GLEICHE_TRADES
        assert gleiches_neff == GLEICHES_NEFF
        assert gleiches_neff < gleiche_trades, "sonst waere die Sorge unbegruendet"

    def test_ohne_reibung_steigt_jede_einzelne_guete(self, zeilen) -> None:
        """Jede - und trotzdem bewegt sich die Luecke kaum. Das ist der
        Punkt: Die Latte steigt mit."""
        basis, sprosse = zeilen

        schlechter = [
            n for n, d in sprosse.items() if d["guete"] < basis[n]["guete"]
        ]
        assert schlechter == []


class TestDieReibungTraegtDieLueckeNicht:
    """**Die Antwort, und sie ist auf der Kerzenlaenge gemessen, die den
    Spot-Punkt traegt.**"""

    def test_die_tafel_nennt_beide_sprossen(self, urteil) -> None:
        assert f"0 {MIT_LATTE} 2.297 3.358 {LUECKE_FREI:.3f}" in urteil
        assert f"1 {MIT_LATTE} 2.484 3.564 {LUECKE_BETRIEB:.3f}" in urteil

    def test_der_anteil_steht_da_und_ist_klein(self, urteil) -> None:
        assert "Die Reibung traegt die Luecke nicht" in urteil
        assert f"hebt {ANTEIL:.1%} davon auf" in urteil

    def test_und_woran_es_dann_liegt(self, urteil) -> None:
        assert "was fehlt, fehlt an den Signalen" in urteil
        assert "Billiger zu handeln bewegt diese Decke nicht" in urteil

    def test_der_anteil_ist_gerechnet_und_nicht_behauptet(self) -> None:
        gemessen = (LUECKE_BETRIEB - LUECKE_FREI) / LUECKE_BETRIEB

        assert gemessen == pytest.approx(ANTEIL, abs=0.001)

    def test_die_luecke_bleibt_offen(self) -> None:
        assert LUECKE_FREI > 0
        assert LUECKE_FREI < LUECKE_BETRIEB


class TestDieNaechsteRegelWechselt:
    """Nicht dieselbe Regel - und das Urteil sagt es, weil es sonst wie eine
    Guete-Steigerung derselben Zeile aussieht."""

    def test_beide_namen_stehen_da(self, urteil) -> None:
        assert NAH_FREI in urteil
        assert NAH_BETRIEB in urteil

    def test_das_urteil_nennt_den_wechsel(self, urteil) -> None:
        assert "Es ist nicht dieselbe Regel" in urteil
        assert "Beide Seiten der Luecke bewegen sich" in urteil

    def test_und_warum_die_kleinste_luecke_zaehlt(self, urteil) -> None:
        assert "kleinste Luecke die Zahl und nicht die hoechste Guete" in urteil

    def test_die_hoechste_guete_gehoert_einer_anderen_regel(self, zeilen) -> None:
        """Die Begruendung, nachgerechnet: Bei Faktor 0 hat nicht die Regel
        mit der hoechsten Guete die kleinste Luecke."""
        _, sprosse = zeilen
        beste = max(sprosse.values(), key=lambda d: d["guete"])

        assert beste["regel"] != NAH_FREI
