"""Der Bericht ohne die Archive - was dabei bleiben muss.

**Befund 248.** ``cli stand`` ist auf 1.053 Zeilen gewachsen. Die drei
Abschnitte, die etwas von ihrem Leser verlangen - *WAS NICHT BEI MIR LIEGT*,
*NUR AUF DEINEM RECHNER*, *WAS DEN ZUSTAND AENDERN KANN* - begannen bei Zeile
754. Davor lagen ueber fuenfhundert Zeilen abgeschlossener Wege.

Das ist die Klage aus Befund 114, eine Ebene hoeher: *"Das Wissen liegt im
System, aber nicht dort, wo es die Arbeit steuern wuerde."*

Der Schnitt
-----------
``--kurz`` laesst genau die beiden **Archive** weg, ``GESCHLOSSEN`` und
``BEHOBEN``. Gewaehlt ist das nicht nach Gefuehl: Die Ueberschrift des zweiten
sagt selbst *"sagt nichts ueber die Aussichten"*, und der Kopf von ``OFFEN``
nennt den Unterschied zu ``GESCHLOSSEN`` *"der wichtigere von beiden"*.

Gemessen: 1.053 auf 563 Zeilen, und die Handlungsabschnitte ruecken von Zeile
754 auf 264.

Was dabei **nicht** passieren darf
----------------------------------
Dass etwas ueber den heutigen Stand verschwindet. Gerechnet wird in beiden
Faellen dasselbe; gekuerzt wird die Ausgabe, nicht die Messung. Diese Tests
halten beides fest.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.stand import BEHOBEN, GESCHLOSSEN, Lage

#: Die Abschnitte, die den heutigen Stand tragen. Keiner darf der Kuerzung
#: zum Opfer fallen.
BLEIBT: tuple[str, ...] = (
    "STAND",
    "WIE WEIT ES NOCH IST",
    "PUNKTE AUS DEM AUFTRAG",
    "WAS NICHT BEI MIR LIEGT",
    "NUR AUF DEINEM RECHNER",
)

#: Die beiden Archive - und nur sie.
FAELLT_WEG: tuple[str, ...] = (
    "GEMESSEN UND GESCHLOSSEN",
    "BEHOBEN AN DEN WERKZEUGEN",
)


@pytest.fixture
def lage() -> Lage:
    return Lage(
        kandidat="Trend 50 Tage mit Konfluenz",
        maerkte="BTCUSD_BITSTAMP + ETHUSD_BITSTAMP, 1d",
        trades=156,
        effektiv=115,
        bestanden=7,
        gesamt=11,
        versuche=198,
        sharpe_je_trade=0.2535,
        noetiger_sharpe=0.3364,
        offen=("Messlatte", "Deflated Sharpe"),
    )


class TestWasBleibt:
    @pytest.mark.parametrize("abschnitt", BLEIBT)
    def test_jeder_handelnde_abschnitt_ueberlebt(
        self, lage: Lage, abschnitt: str
    ) -> None:
        assert abschnitt in lage.bericht(kurz=True)

    def test_das_urteil_bleibt(self, lage: Lage) -> None:
        """Der Satz, der sagt, wo wir stehen - ohne ihn ist es kein Bericht."""
        assert lage.urteil() in lage.bericht(kurz=True)

    def test_was_offen_ist_bleibt(self, lage: Lage) -> None:
        """``OFFEN`` nennt sich im eigenen Kopf *"hier liegt die Arbeit"*.
        Es wegzukuerzen waere der Fehler, gegen den die Kuerzung antritt."""
        assert "GEMESSEN UND OFFEN" in lage.bericht(kurz=True)


class TestWasWegfaellt:
    @pytest.mark.parametrize("abschnitt", FAELLT_WEG)
    def test_die_archive_fehlen(self, lage: Lage, abschnitt: str) -> None:
        assert abschnitt not in lage.bericht(kurz=True)

    @pytest.mark.parametrize("abschnitt", FAELLT_WEG)
    def test_im_vollen_bericht_stehen_sie(self, lage: Lage, abschnitt: str) -> None:
        """Die Gegenprobe - eine Kuerzung, die immer kuerzt, ist keine."""
        assert abschnitt in lage.bericht()

    def test_es_sind_genau_die_beiden_archive(self, lage: Lage) -> None:
        """**Der tragende Test.** Was fehlt, sind die Eintraege der beiden
        Register und ihre Ueberschriften - nichts sonst.
        """
        voll = lage.bericht().splitlines()
        kurz = set(lage.bericht(kurz=True).splitlines())
        fehlend = [z for z in voll if z not in kurz]

        archiv = {f"  {r}" for r in (*GESCHLOSSEN, *BEHOBEN)}
        uebrig = [z for z in fehlend if z.strip() and z not in archiv]

        assert all(
            z.startswith(FAELLT_WEG) or set(z) <= {"-"} for z in uebrig
        ), f"mehr als die Archive gekuerzt: {uebrig[:5]}"

    def test_die_kuerzung_lohnt_sich(self, lage: Lage) -> None:
        voll = len(lage.bericht().splitlines())
        kurz = len(lage.bericht(kurz=True).splitlines())

        assert kurz < voll * 0.6, f"{kurz} von {voll} Zeilen"


class TestDerBefehl:
    def test_stand_kennt_die_kurzform(self) -> None:
        baum = ast.parse(Path("cli.py").read_text())
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "stand"
        )

        assert "--kurz" in quelle
        assert "lage.bericht(kurz=kurz)" in quelle

    def test_gerechnet_wird_in_beiden_faellen_dasselbe(self) -> None:
        """**Die Zusicherung, auf die es ankommt.**

        Die Kuerzung darf an der Ausgabe sparen, nicht an der Messung. Stuende
        das ``kurz`` irgendwo vor dem Walk-Forward, waere der kurze Bericht
        ein anderer Bericht - und genau so entstehen zwei Wahrheiten.
        """
        baum = ast.parse(Path("cli.py").read_text())
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "stand"
        )

        assert quelle.index("run_portfolio_walkforward") < quelle.index("kurz=kurz")
        # Ausser in der Signatur und beim Durchreichen kommt es nicht vor.
        assert quelle.count("kurz") <= 6, "die Kuerzung greift zu tief"
