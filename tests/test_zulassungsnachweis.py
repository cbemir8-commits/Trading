"""champion.json sagte, **was** zugelassen ist - nicht **woraufhin**.

Die Datei, an der laut ihrem eigenen Docstring das echte Geld haengt, trug nur
das Genom. Unter welchem Instrument, welchem Kontostand und mit welchen Daten
es bestanden hat, stand nirgends.

Befund 106 hat gezeigt, dass das kein theoretisches Problem ist: Derselbe
Kandidat steht auf einem Perpetual bei 7 von 11 und auf Spot bei 9 von 11. Wer
``cli trade --markt spot`` faehrt, waehrend die Zulassung auf einem Perpetual
gemessen wurde, handelt etwas anderes als das Gepruefte.

Drei Tests tragen diese Datei:

``test_ein_anderes_instrument_wird_abgelehnt`` - Der Kern.

``test_das_alte_format_bleibt_lesbar`` - Die Wache. Ein Formatupdate darf eine
vorhandene Zulassung nicht stillschweigend ungueltig machen.

``test_die_marktart_wird_aus_dem_lauf_abgeleitet`` - Die Ursache. Eine zweite
Quelle waere die Stelle, an der Nachweis und Lauf auseinanderlaufen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.admission import (
    Zulassungsbedingungen,
    ist_zugelassen,
    lade_bedingungen,
    lade_champion,
    write_champion,
)
from research.seeds import spitzenkandidat


class FakeGates:
    def __init__(self, bestanden: int, gesamt: int) -> None:
        self.referenzdaten = True
        self.results = [
            type("R", (), {"passed": i < bestanden})() for i in range(gesamt)
        ]


class FakeKandidat:
    def __init__(self, genome, bestanden: int = 11, gesamt: int = 11) -> None:
        self.genome = genome
        self.gates = FakeGates(bestanden, gesamt)


@pytest.fixture
def genome():
    return spitzenkandidat()


def bedingungen(**abweichung) -> Zulassungsbedingungen:
    daten = {
        "markt": "perpetual", "kapital": 500.0, "intervall": "D",
        "referenzdaten": True, "versuche": 198, "bestanden": 11, "gesamt": 11,
        "funding_satz": 0.0001, "zeitpunkt": "2026-08-22T13:00:00+00:00",
    }
    daten.update(abweichung)
    return Zulassungsbedingungen(**daten)


class TestNachweis:
    def test_ein_anderes_instrument_wird_abgelehnt(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Die Gates gelten fuer das gepruefte Instrument, nicht fuer ein
        anderes - und der Unterschied betraegt zwei Gates.
        """
        b = bedingungen(markt="perpetual")

        assert b.vollstaendig
        assert b.passt_zu("perpetual")
        assert not b.passt_zu("spot")

    def test_ohne_aufzeichnung_ist_die_antwort_unbekannt(self) -> None:
        """Nicht "passt schon". Ein leerer Nachweis heisst, dass nichts
        aufgezeichnet wurde - der Aufrufer muss das getrennt behandeln."""
        leer = Zulassungsbedingungen()

        assert not leer.vollstaendig
        assert not leer.passt_zu("perpetual")
        assert not leer.passt_zu("spot")

    def test_der_text_nennt_die_bedingungen(self) -> None:
        text = bedingungen().als_text()

        assert "perpetual" in text
        assert "11/11 Gates" in text
        assert "500 EUR Konto" in text
        assert "198 Versuche" in text
        assert "Forschungskerzen" in text

    def test_ein_halber_nachweis_gilt_nicht_als_vollstaendig(self) -> None:
        """Ohne Gate-Zahl laesst sich nicht sagen, ob ueberhaupt geprueft
        wurde."""
        halb = Zulassungsbedingungen(markt="spot")

        assert not halb.vollstaendig


class TestDatei:
    def test_der_nachweis_landet_in_der_datei(self, tmp_path: Path, genome) -> None:
        ziel = tmp_path / "champion.json"

        write_champion(
            FakeKandidat(genome), ziel, bedingungen=bedingungen(markt="spot")
        )

        gelesen = lade_bedingungen(ziel)
        assert gelesen.markt == "spot"
        assert gelesen.kapital == 500.0
        assert gelesen.versuche == 198

    def test_das_alte_format_bleibt_lesbar(self, tmp_path: Path, genome) -> None:
        """**Die Wache.**

        Eine Datei aus der Zeit davor ist das Genom selbst. Sie nicht mehr zu
        verstehen hiesse, eine vorhandene Zulassung durch ein Formatupdate
        stillschweigend ungueltig zu machen.
        """
        alt = tmp_path / "champion.json"
        alt.write_text(json.dumps(genome.model_dump(mode="json")))

        assert lade_champion(alt) is not None
        assert lade_champion(alt).genome_id == genome.genome_id
        assert ist_zugelassen(genome, alt)
        assert not lade_bedingungen(alt).vollstaendig

    def test_das_neue_format_wird_auch_von_ist_zugelassen_verstanden(
        self, tmp_path: Path, genome
    ) -> None:
        ziel = tmp_path / "champion.json"

        write_champion(FakeKandidat(genome), ziel, bedingungen=bedingungen())

        assert ist_zugelassen(genome, ziel)

    def test_ohne_bedingungen_bleibt_es_beim_alten_format(
        self, tmp_path: Path, genome
    ) -> None:
        ziel = tmp_path / "champion.json"

        write_champion(FakeKandidat(genome), ziel)

        roh = json.loads(ziel.read_text())
        assert "zulassung" not in roh
        assert ist_zugelassen(genome, ziel)

    def test_eine_kaputte_datei_liefert_keinen_stapelabzug(
        self, tmp_path: Path
    ) -> None:
        """Kein stiller Standardwert, aber auch kein Traceback: ``None``
        fuehrt beim einzigen Aufrufer zu einer Meldung und einem Abbruch."""
        kaputt = tmp_path / "champion.json"
        kaputt.write_text("{kein json")

        assert lade_champion(kaputt) is None
        assert not lade_bedingungen(kaputt).vollstaendig

    def test_eine_datei_ohne_genom_liefert_auch_nichts(self, tmp_path: Path) -> None:
        ohne = tmp_path / "champion.json"
        ohne.write_text(json.dumps({"genom": {"name": "unfertig"}}))

        assert lade_champion(ohne) is None

    def test_eine_fehlende_datei_kippt_nicht(self, tmp_path: Path) -> None:
        assert lade_champion(tmp_path / "gibt-es-nicht.json") is None
        assert not lade_bedingungen(tmp_path / "gibt-es-nicht.json").vollstaendig

    def test_unbekannte_felder_werden_ueberlesen(self, tmp_path: Path, genome) -> None:
        """Ein aelterer oder neuerer Nachweis mit zusaetzlichen Feldern darf
        das Lesen nicht sprengen."""
        ziel = tmp_path / "champion.json"
        ziel.write_text(
            json.dumps(
                {
                    "genom": genome.model_dump(mode="json"),
                    "zulassung": {"markt": "spot", "gesamt": 11, "erfunden": 7},
                }
            )
        )

        assert lade_bedingungen(ziel).markt == "spot"


class TestAbleitung:
    def test_die_marktart_wird_aus_dem_lauf_abgeleitet(self, genome) -> None:
        """**Die Ursache, nicht das Symptom.**

        Der Backtest kennt keinen Schalter fuer das Instrument - er kennt
        Funding und einen Hebeldeckel. Beides wird gelesen.
        """
        from decimal import Decimal

        from cli import _marktart

        class FakeFunding:
            def __init__(self, satz: str) -> None:
                self.default_rate = Decimal(satz)

        class FakeConfig:
            def __init__(self, satz: str) -> None:
                self.funding = FakeFunding(satz)

        ohne_hebel = genome.model_copy(
            update={"sizing": genome.sizing.model_copy(update={"fraction": 1.0})}
        )

        assert _marktart({"a": FakeConfig("0.0001")}, genome) == "perpetual"
        assert _marktart({"a": FakeConfig("0")}, genome) == "perpetual", (
            "fraction 3.0 allein macht es schon zum Perpetual"
        )
        assert _marktart({"a": FakeConfig("0.0001")}, ohne_hebel) == "perpetual"
        assert _marktart({"a": FakeConfig("0")}, ohne_hebel) == "spot"

    def test_eine_einzelne_konfiguration_geht_auch(self, genome) -> None:
        """``cli research`` faehrt einen Markt, ``cli wettbewerb`` mehrere."""
        from decimal import Decimal

        from cli import _marktart

        class FakeConfig:
            class funding:  # noqa: N801
                default_rate = Decimal("0")

        ohne_hebel = genome.model_copy(
            update={"sizing": genome.sizing.model_copy(update={"fraction": 1.0})}
        )

        assert _marktart(FakeConfig(), ohne_hebel) == "spot"


class TestSperre:
    def test_cli_trade_prueft_das_instrument(self) -> None:
        """Die Sperre gehoert vor den ersten Handelsschritt, nicht in eine
        Fussnote."""
        import cli

        quelle = Path(cli.__file__).read_text()
        stelle = quelle[quelle.index("def trade("):]
        stelle = stelle[: stelle.index("@app.command()")]

        assert "lade_bedingungen" in stelle
        assert "passt_zu(markt)" in stelle
        assert "Zulassungsnachweis" in stelle, (
            "und eine Datei ohne Nachweis wird benannt, nicht durchgewinkt"
        )
