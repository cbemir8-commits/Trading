"""Vorauswahl auf gepflanzten Reihen - und warum sie die Realitaet nicht sehen darf.

Befund 55 endet mit einer Vorgabe: Wer die Kopplung aus Qualitaet und Menge
brechen will, muss an einer **Einstiegsbedingung** ansetzen, die in starken
Trends haeufiger ausloest. Welche das tut, laesst sich auf gepflanzten Reihen
vorab pruefen - dort ist der Vorteil per Konstruktion da, und es kostet keinen
Versuch.

**Der Fallstrick, um den es hier geht.** Die 0-%-Sprosse der Leiter ist nicht
"fast" die echte Reihe, sie **ist** sie: ``pflanze_trend`` gibt den Rahmen bei
Anteil 0 unveraendert zurueck. Wer Regeln danach auswaehlt, hat auf echten
Daten getestet - und genau das zaehlt die Mehrfachtest-Korrektur. Eine
Vorauswahl, die sie mitnaehme und trotzdem "kostet keinen Versuch" meldete,
waere eine stille Umgehung des Versuchszaehlers.

Deshalb faellt die 0-%-Sprosse weg, sobald Regeln verglichen werden. Der Test
dafuer ist ``test_die_null_sprosse_faellt_weg`` - er ist der Grund, warum es
diese Datei gibt.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import typer
from typer.testing import CliRunner

from cli import _regeln_aus_datei, app
from research.teststaerke import pflanze_trend, regimefolge

runner = CliRunner()


REGEL = {
    "name": "Kurzer Rueckkehrtakt",
    "rationale": (
        "These aus Befund 55: Ein kurzer Schnitt wird auch im starken Trend "
        "laufend gekreuzt, ein langer immer seltener."
    ),
    "entry_long": [
        {
            "left": {"kind": "price", "name": "close"},
            "op": "cross_above",
            "right": {"kind": "indicator", "name": "sma", "params": {"period": 10}},
        }
    ],
    "stop": {"kind": "percent", "percent": 4.0},
    "targets": [{"rr": 20.0, "portion": 1.0}],
    "max_hold_bars": 20,
}


def datei(tmp_path: Path, inhalt) -> Path:
    pfad = tmp_path / "regeln.json"
    pfad.write_text(json.dumps(inhalt))
    return pfad


class TestDieNullSprosseIstDieWirklichkeit:
    """Die Tatsache, aus der die ganze Absicherung folgt."""

    def test_anteil_null_gibt_die_reihe_unveraendert_zurueck(self) -> None:
        rng = np.random.default_rng(3)
        close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.03, 500)))
        roh = pd.DataFrame(
            {
                "open_time": pd.date_range("2020-01-01", periods=500, freq="D"),
                "open": close * 0.999,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.full(500, 10.0),
            }
        )

        gleich = pflanze_trend(roh, anteil=0.0, regime=regimefolge(500))

        pd.testing.assert_frame_equal(
            gleich.reset_index(drop=True), roh.reset_index(drop=True)
        )


class TestVorauswahl:
    def test_die_null_sprosse_faellt_weg(self, tmp_path: Path) -> None:
        """**Der Test, der diese Datei traegt.**

        Wird mit ``--regeln`` verglichen, darf die unveraenderte echte Reihe
        nicht unter den Sprossen sein. Sonst waehlte die Vorauswahl auf echten
        Daten aus und meldete trotzdem, sie koste keinen Versuch.
        """
        ergebnis = runner.invoke(
            app,
            [
                "teststaerke",
                "--regeln", str(datei(tmp_path, [REGEL])),
                "--stufen", "0",
            ],
        )

        assert ergebnis.exit_code == 2
        assert "Keine gepflanzte Stufe uebrig" in ergebnis.stdout

    def test_der_grund_steht_im_klartext_dabei(self, tmp_path: Path) -> None:
        """Eine Absicherung, die niemand erklaert bekommt, wird beim naechsten
        Umbau wegoptimiert."""
        ergebnis = runner.invoke(
            app,
            ["teststaerke", "--regeln", str(datei(tmp_path, [REGEL])), "--stufen", "0"],
        )

        assert "Versuchszaehler" in ergebnis.stdout


class TestRegelnAusDatei:
    def test_gueltige_regeln_kommen_mit_namen_durch(self, tmp_path: Path) -> None:
        geladen = _regeln_aus_datei(datei(tmp_path, [REGEL]))

        assert len(geladen) == 1
        name, genom = geladen[0]
        assert name.startswith("Kurzer")
        assert genom.max_hold_bars == 20, (
            "Der Haltedeckel muss ankommen - seit Befund 55 wirkt er"
        )

    def test_eine_ungueltige_regel_wird_abgelehnt_nicht_repariert(
        self, tmp_path: Path
    ) -> None:
        kaputt = json.loads(json.dumps(REGEL))
        kaputt["entry_long"][0]["right"]["name"] = "kristallkugel"

        with pytest.raises(typer.Exit):
            _regeln_aus_datei(datei(tmp_path, [kaputt]))

    def test_eine_fehlende_datei_faellt_auf(self, tmp_path: Path) -> None:
        with pytest.raises(typer.Exit):
            _regeln_aus_datei(tmp_path / "gibtsnicht.json")

    def test_eine_gueltige_regel_ueberlebt_neben_einer_kaputten(
        self, tmp_path: Path
    ) -> None:
        kaputt = json.loads(json.dumps(REGEL))
        kaputt["name"] = "Unbekannter Indikator"
        kaputt["entry_long"][0]["right"]["name"] = "kristallkugel"

        geladen = _regeln_aus_datei(datei(tmp_path, [REGEL, kaputt]))

        assert [n for n, _ in geladen] == [REGEL["name"][:14]]


class TestGroessenlogik:
    """Verglichen werden Einstiegsstrukturen - nicht Groessenlogiken.

    Der erste Anlauf liess die Vorschlaege mit ihrer Voreinstellung laufen.
    Die bemisst am Stop-Abstand und lehnt einen 4-%-Stop als zu weit ab:
    **null Trades in jeder Spalte**, auch beim Bestand, der dort 48 haben
    muss. Ein Vergleich, in dem jede Variante null liefert, sieht nach einem
    Ergebnis aus und ist keines.

    Dass hier gleichgestellt wird und in Befund 54 nicht, ist kein
    Widerspruch: Dort lief ein einziges Genom durch die Leiter, hier laufen
    mehrere gegeneinander.
    """

    def test_alle_regeln_bekommen_die_groessenlogik_des_bestands(
        self, tmp_path: Path
    ) -> None:
        from research.seeds import spitzenkandidat

        zweite = json.loads(json.dumps(REGEL))
        zweite["name"] = "Zweite Regel"
        geladen = _regeln_aus_datei(datei(tmp_path, [REGEL, zweite]))

        for _, genom in geladen:
            assert genom.sizing == spitzenkandidat().sizing

    def test_die_einstiegsstruktur_bleibt_unangetastet(self, tmp_path: Path) -> None:
        """Gleichgestellt wird die Groesse - und sonst nichts. Wer dabei die
        Regel selbst veraendert, vergleicht wieder etwas anderes."""
        _, genom = _regeln_aus_datei(datei(tmp_path, [REGEL]))[0]

        assert genom.entry_long[0].right.params == {"period": 10}
        assert genom.stop.percent == 4.0
        assert genom.max_hold_bars == 20
