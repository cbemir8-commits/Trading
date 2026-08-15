"""Ein Zaehler, der nicht fallen darf - und ein Verzeichnis dahinter.

Zwei Tests tragen diese Datei:

``test_eine_kaputte_datei_bricht_ab`` - Frueher lieferte sie 0, und der Test
dazu hielt genau das fest. Die Gefahr war benannt und wurde trotzdem in Kauf
genommen, weil ein Protokolleintrag ausreichend schien. Er reicht nicht: Der
Lauf rechnet weiter und schreibt den falschen Stand danach fest.

``test_der_grundstock_wird_nicht_erfunden`` - Die 166 bisherigen Versuche
haben keinen Einzelnachweis, und sie bekommen auch keinen. Eine erfundene
Herkunft an der Stelle, an der es um die Messbarkeit einer Groesse geht, waere
schlimmer als die sichtbare Luecke.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.versuche import (
    FORMAT,
    Versuch,
    Verzeichnis,
    ZaehlerUnlesbarError,
    anhaengen,
    laden,
    speichern,
)


def alt(pfad: Path, trials: int) -> Path:
    """Das Format, wie es bis heute auf der Platte liegt."""
    pfad.write_text(json.dumps({"trials": trials, "updated_at": "2026-08-15"}))
    return pfad


class TestLaden:
    def test_eine_fehlende_datei_ist_der_erste_lauf(self, tmp_path: Path) -> None:
        """Hier stimmt die 0 - es wurde noch nichts probiert."""
        assert laden(tmp_path / "gibtsnicht.json").anzahl == 0

    def test_eine_kaputte_datei_bricht_ab(self, tmp_path: Path) -> None:
        """**Der Test, der diese Datei traegt.**

        Am Spitzenkandidaten: 0,79 bei 166 Versuchen, 0,996 bei elf. Ein
        Ersatzwert an dieser Stelle dreht das strengste Gate des Projekts,
        ohne dass jemand etwas gelockert haette.
        """
        datei = tmp_path / "trials.json"
        datei.write_text("{kaputt")

        with pytest.raises(ZaehlerUnlesbarError, match="nicht lesbar"):
            laden(datei)

    def test_auch_ein_falscher_typ_bricht_ab(self, tmp_path: Path) -> None:
        datei = tmp_path / "trials.json"
        datei.write_text(json.dumps([1, 2, 3]))

        with pytest.raises(ZaehlerUnlesbarError):
            laden(datei)

    def test_das_alte_format_wird_zum_grundstock(self, tmp_path: Path) -> None:
        """Die nackte Zahl von heute ist genau das: eine Summe ohne Belege."""
        verzeichnis = laden(alt(tmp_path / "trials.json", 166))

        assert verzeichnis.anzahl == 166
        assert verzeichnis.grundstock == 166
        assert verzeichnis.eintraege == []


class TestSchreiben:
    def test_ein_umlauf_erhaelt_alles(self, tmp_path: Path) -> None:
        datei = tmp_path / "trials.json"
        speichern(
            datei,
            Verzeichnis(
                grundstock=166,
                eintraege=[Versuch.jetzt("A", trades=120, sharpe_je_trade=0.21)],
            ),
        )
        wieder = laden(datei)

        assert wieder.anzahl == 167
        assert wieder.grundstock == 166
        assert wieder.eintraege[0].kennung == "A"
        assert wieder.eintraege[0].sharpe_je_trade == 0.21

    def test_die_summe_steht_fuer_alte_leser_mit_drin(self, tmp_path: Path) -> None:
        """``trials`` bleibt im Format - sonst liest ein aelterer Leser eine
        Datei ohne die Zahl, auf die er wartet, und faengt bei 0 an."""
        datei = tmp_path / "trials.json"
        speichern(datei, Verzeichnis(grundstock=166, eintraege=[Versuch("A")]))
        roh = json.loads(datei.read_text())

        assert roh["trials"] == 167
        assert roh["format"] == FORMAT

    def test_atomar_ohne_reste(self, tmp_path: Path) -> None:
        datei = tmp_path / "trials.json"
        speichern(datei, Verzeichnis(grundstock=5))
        speichern(datei, Verzeichnis(grundstock=6))

        assert laden(datei).anzahl == 6
        assert [p.name for p in tmp_path.iterdir()] == ["trials.json"]

    def test_anhaengen_verliert_die_alten_nicht(self, tmp_path: Path) -> None:
        datei = alt(tmp_path / "trials.json", 166)
        anhaengen(datei, [Versuch.jetzt("A", sharpe_je_trade=0.2)])
        verzeichnis = anhaengen(datei, [Versuch.jetzt("B", sharpe_je_trade=0.1)])

        assert verzeichnis.anzahl == 168
        assert [v.kennung for v in verzeichnis.eintraege] == ["A", "B"]


class TestNachweise:
    def test_der_grundstock_wird_nicht_erfunden(self, tmp_path: Path) -> None:
        """**Der zweite tragende Test.**

        166 Versuche ohne Einzelnachweis bleiben 166 Versuche ohne
        Einzelnachweis. Sie mit Platzhaltern aufzufuellen wuerde eine Luecke
        unsichtbar machen, die genau an der Stelle sitzt, an der es um die
        Messbarkeit der Streuung geht.
        """
        verzeichnis = laden(alt(tmp_path / "trials.json", 166))

        assert verzeichnis.anzahl == 166
        assert verzeichnis.belegt == 0
        assert verzeichnis.sharpes() == []

    def test_nicht_erhoben_ist_nicht_null(self, tmp_path: Path) -> None:
        """``None`` heisst "nicht gemessen" und nicht "kein Vorteil". Wer das
        verwechselt, zieht die Streuung nach unten - und genau dort haengt das
        Urteil des Gates."""
        verzeichnis = Verzeichnis(
            eintraege=[
                Versuch("A", sharpe_je_trade=0.2),
                Versuch("B", sharpe_je_trade=None),
            ]
        )

        assert verzeichnis.anzahl == 2
        assert verzeichnis.sharpes() == [0.2]

    def test_erweitert_laesst_das_original_stehen(self) -> None:
        original = Verzeichnis(grundstock=166, eintraege=[Versuch("A")])
        neu = original.erweitert([Versuch("B")])

        assert len(original.eintraege) == 1
        assert len(neu.eintraege) == 2
