"""Die offene Entscheidung aus Befund 313, gegen einen Lauf - Befund 447.

``cli stand`` nennt zwei Stellen, an denen die Arbeit liegt, und eine davon
ist das **Parameter-Plateau**. Sein Wert ist dort kein Mass der Gebietsform:

    Das Gate faehrt seine zwoelf Nachbarn als **durchgehenden** Backtest je
    Bein - acht Jahre, ein Risk-Officer, keine Fenstergrenze. Eine dauerhafte
    Sperre (Not-Aus oder Wochenlimit) laeuft bis zur manuellen Freigabe, die
    in einem durchgehenden Lauf nie kommt.

Befund 313 hat das gemessen und als **Entscheidung** verzeichnet: Welche der
beiden Messarten das Gate meint, ist eine Geschaeftsfrage - sie verschiebt
ein Gate von "durchgefallen" auf "bestanden" und entsteht, waehrend der
eigene Kandidat genau daran haengt. *"Messen, hinschreiben, nicht selbst
entscheiden."*

**Was fehlte, war der Lauf.** Die Zahlen der Entscheidung standen gegen eine
Abschrift - dieselbe Luecke, die Befund 442 geschlossen hat. Eine
Entscheidung, die beim Nutzer liegt, soll auf Zahlen stehen, die heute noch
stimmen.

Gemessen (Befund 447, 'cli freigabe', kostet keinen Versuch)
------------------------------------------------------------
Die durchgehende Spalte reproduziert Befund 313 **auf den Cent**, die
Walk-Forward-Spalte ist gewandert:

    Nachbar                  durchgehend     Walk-Forward (313 -> heute)
    alle gemeinsam x1,2          -103,63     +233,04 -> +233,92
    sma(period=50) x1,2          -103,90     +239,08 -> +240,26

Das passt zur Bauart: Der durchgehende Lauf faehrt die ganze Reihe und
aendert sich nicht, solange die Reihe am Anfang gleich bleibt; die
Walk-Forward-Aufteilung haengt am **Ende** der Reihe, und das ist seit 313
gewachsen. Die Zahl, die das Gate benutzt - das **Vorzeichen** -, ist
unveraendert, ebenso die 1020 verhinderten Einstiege und die Gate-Werte
0,500 gegen 1,000.
"""

from __future__ import annotations

import re

import pytest

#: Die zwoelf Nachbarn: Name, durchgehend, Walk-Forward, gesperrte Einstiege.
#:
#: **Gemessen** (Befund 447), nicht abgeschrieben - der Datentest unten
#: faehrt 'cli freigabe' und vergleicht Zeile fuer Zeile.
NACHBARN: tuple[tuple[str, float, float, int], ...] = (
    ("alle gemeinsam x0.8", 1093.21, 661.38, 79),
    ("alle gemeinsam x1.2", -103.63, 233.92, 110),
    ("sma(period=50) x0.8", 867.56, 621.72, 79),
    ("sma(period=50) x1.2", -103.90, 240.26, 109),
    ("sma(period=200) x0.8", 932.16, 750.46, 75),
    ("sma(period=200) x1.2", 939.43, 731.80, 75),
    ("roc(period=90) x0.8", 957.29, 726.99, 75),
    ("roc(period=90) x1.2", 956.73, 750.02, 75),
    ("rsi(period=14) x0.8", 964.11, 751.75, 75),
    ("rsi(period=14) x1.2", 1025.25, 747.88, 75),
    ("Vola-Fenster x0.8", 801.89, 861.92, 117),
    ("Vola-Fenster x1.2", 964.22, 671.76, 76),
)

#: Die beiden, bei denen die Messart ueber das **Vorzeichen** entscheidet.
VERSCHIEDEN = ("alle gemeinsam x1.2", "sma(period=50) x1.2")

#: Gate-Wert durchgehend, im Walk-Forward, und die Schwelle.
DURCHGEHEND, WALKFORWARD, SCHWELLE = 0.500, 1.000, 0.600

#: Verhinderte Einstiege ueber alle zwoelf - so verzeichnet in Befund 313.
GESPERRT_GESAMT = 1020

#: Die Walk-Forward-Werte, wie Befund 313 sie nennt.
DREIZEHN: dict[str, float] = {
    "alle gemeinsam x1.2": 233.04,
    "sma(period=50) x1.2": 239.08,
}


def _glatt(text: str) -> str:
    """Ueber die Umbrueche hinweg (Befund 420/430) - die Konsole bricht
    Zeilen nach Terminalbreite."""
    return " ".join(text.split())


@pytest.fixture(scope="module")
def lauf() -> str:
    from typer.testing import CliRunner

    from cli import app

    ergebnis = CliRunner().invoke(app, ["freigabe"])
    if ergebnis.exit_code != 0:
        pytest.fail(
            f"'cli freigabe' endete mit {ergebnis.exit_code}:\n"
            f"{ergebnis.output[-2000:]}"
        )
    return _glatt(ergebnis.output)


def _zeilen(text: str) -> dict[str, tuple[float, float, int, str, str]]:
    aus = {}
    for name, *_ in NACHBARN:
        treffer = re.search(
            re.escape(name)
            + r" ([+-]\d+\.\d+) ([+-]\d+\.\d+) (\d+) ([+-]) / ([+-])",
            text,
        )
        if treffer:
            aus[name] = (
                float(treffer.group(1)),
                float(treffer.group(2)),
                int(treffer.group(3)),
                treffer.group(4),
                treffer.group(5),
            )
    return aus


@pytest.mark.daten
@pytest.mark.langsam
class TestDieZahlenDerEntscheidungStehenNoch:
    def test_alle_zwoelf_nachbarn_stehen_da(self, lauf) -> None:
        gemessen = _zeilen(lauf)

        assert set(gemessen) == {n for n, *_ in NACHBARN}, sorted(gemessen)

    def test_die_durchgehende_spalte_trifft(self, lauf) -> None:
        """Die Spalte, die das Gate benutzt."""
        gemessen = _zeilen(lauf)

        for name, durch, _, _ in NACHBARN:
            assert gemessen[name][0] == pytest.approx(durch, abs=0.02), name

    def test_die_walk_forward_spalte_auch(self, lauf) -> None:
        gemessen = _zeilen(lauf)

        for name, _, wf, _ in NACHBARN:
            assert gemessen[name][1] == pytest.approx(wf, abs=0.02), name

    def test_und_die_gesperrten_einstiege(self, lauf) -> None:
        gemessen = _zeilen(lauf)

        for name, _, _, gesperrt in NACHBARN:
            assert gemessen[name][2] == gesperrt, name

    def test_die_summe_ist_die_aus_313(self, lauf) -> None:
        treffer = re.search(r"zusammen (\d+) Einstiege verhindert", lauf)

        assert treffer, lauf[-700:]
        assert int(treffer.group(1)) == GESPERRT_GESAMT
        assert sum(g for *_, g in NACHBARN) == GESPERRT_GESAMT

    def test_die_gate_werte_stehen_unveraendert(self, lauf) -> None:
        treffer = re.search(
            r"Gate-Wert durchgehend \(so misst das Gate heute\) (\d\.\d+), "
            r"im Walk-Forward (\d\.\d+) - Schwelle (\d\.\d+)",
            lauf,
        )

        assert treffer, lauf[-900:]
        assert float(treffer.group(1)) == pytest.approx(DURCHGEHEND, abs=0.001)
        assert float(treffer.group(2)) == pytest.approx(WALKFORWARD, abs=0.001)
        assert float(treffer.group(3)) == pytest.approx(SCHWELLE, abs=0.001)


@pytest.mark.daten
@pytest.mark.langsam
class TestWasSichSeit313GeaendertHat:
    """**Und was nicht.** Der Unterschied ist die Aussage dieses Befundes."""

    def test_die_durchgehende_spalte_reproduziert_auf_den_cent(self, lauf) -> None:
        """Sie faehrt die ganze Reihe, und die aendert sich am Anfang nicht."""
        gemessen = _zeilen(lauf)

        assert gemessen["alle gemeinsam x1.2"][0] == pytest.approx(-103.63, abs=0.005)
        assert gemessen["sma(period=50) x1.2"][0] == pytest.approx(-103.90, abs=0.005)

    def test_die_walk_forward_spalte_ist_gewandert(self, lauf) -> None:
        """Sie haengt am **Ende** der Reihe, und das ist seit 313 gewachsen.

        Geprueft wird die Richtung und die Groessenordnung, nicht die
        Ungleichheit selbst: Eine Zusicherung 'ungleich' waere erfuellt, wenn
        der Wert um das Zehnfache abweicht, und das waere kein Wachsen mehr.
        """
        gemessen = _zeilen(lauf)

        for name, damals in DREIZEHN.items():
            heute = gemessen[name][1]
            assert heute > damals, (name, heute, damals)
            assert heute - damals < 5.0, (name, heute, damals)

    def test_das_vorzeichen_entscheidet_bei_genau_zwei(self, lauf) -> None:
        """Die Zahl, die das Gate benutzt - und sie ist unveraendert."""
        gemessen = _zeilen(lauf)
        uneinig = {n for n, (_, _, _, d, w) in gemessen.items() if d != w}

        assert uneinig == set(VERSCHIEDEN), sorted(uneinig)

    def test_beide_sind_durchgehend_negativ_und_im_fenster_positiv(
        self, lauf
    ) -> None:
        gemessen = _zeilen(lauf)

        for name in VERSCHIEDEN:
            durch, wf, *_ = gemessen[name]
            assert durch < 0, name
            assert wf > 0, name


@pytest.mark.daten
@pytest.mark.langsam
class TestDerBefehlEntscheidetNichts:
    def test_er_sagt_dass_die_frage_beim_nutzer_liegt(self, lauf) -> None:
        """Befund 313: *messen, hinschreiben, nicht selbst entscheiden.*"""
        assert "Die Frage gehoert zum Nutzer" in lauf
        assert "Geaendert wird deshalb nichts" in lauf

    def test_und_warnt_vor_dem_falschen_vergleich(self, lauf) -> None:
        """Die beiden Spalten messen verschiedene Zeitraeume - sie
        gegeneinander aufzurechnen waere der Fehler aus Befund 428, eine
        Ebene tiefer."""
        assert "nicht gegeneinander aufzurechnen" in lauf
        assert "Verglichen wird das Vorzeichen" in lauf

    def test_er_kostet_keinen_versuch(self) -> None:
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_buchung import _bucht

        assert not _bucht("freigabe")
