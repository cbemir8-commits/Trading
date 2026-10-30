""""Datenauswahl gruen" war keine pruefbare Aussage mehr - Befund 430.

Nach dem Wiederaufbau (427) und der Wiederherstellung (428/429) meldete die
Datenauswahl **drei** Ausfaelle, und keiner wegen eines Mangels am Code. Damit
heisst "gruen" dort nichts mehr - und die unpruefbare Fassung ist die
gefaehrliche, weil sie jeden echten Ausfall mitdeckt.

Verzeichnet sind die drei jetzt mit Grund, und **bedingt auf den
Speicherstand**: Auf einem Speicher, der ueber die Pins hinausreicht, bestehen
alle drei, und die Liste ist leer. Eine Liste von Entschuldigungen, die immer
gilt, ist ein Freibrief.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from research.datenstand import (
    FEINENDE,
    GLEICHES_ENDE,
    LAENGER_ALS_DIE_REIHE,
    SERIENENDE,
    erwartete_ausfaelle,
    speicher_ist_gepinnt,
    wiederherstellung,
)

WURZEL = Path(__file__).resolve().parents[1]

#: Der Speicherstand, den ``befehle()`` und ``feinbefehle()`` herstellen.
GEPINNT = {
    "BTC D": (date(2012, 1, 1), SERIENENDE, 5355),
    "ETH D": (date(2017, 8, 16), SERIENENDE, 3301),
    "BTC 15": (date(2020, 3, 30), FEINENDE - timedelta(days=1), 229_728),
}


class TestDieDreiSindVerzeichnet:
    def test_es_sind_genau_drei(self) -> None:
        assert len(erwartete_ausfaelle()) == 3

    def test_und_zwar_diese(self) -> None:
        assert set(erwartete_ausfaelle()) == {
            *LAENGER_ALS_DIE_REIHE,
            *GLEICHES_ENDE,
        }

    def test_jede_mit_grund(self) -> None:
        """Ein Eintrag ohne Grund waere eine Entschuldigung, keine Auskunft."""
        for datei, grund in erwartete_ausfaelle().items():
            assert len(grund) > 40, datei

    def test_die_dateien_gibt_es(self) -> None:
        """Ein Eintrag fuer einen Test, den es nicht mehr gibt, ist genau die
        Altlast, gegen die dieses Projekt seine Register prueft."""
        for datei in erwartete_ausfaelle():
            assert (WURZEL / datei).exists(), datei

    def test_der_abstand_ist_gerechnet(self) -> None:
        """49 Tage stehen nicht im Text, sondern kommen aus den Pins."""
        abstand = (FEINENDE - timedelta(days=1) - SERIENENDE).days

        assert abstand == 49
        assert f"{abstand} Tage" in erwartete_ausfaelle()[GLEICHES_ENDE[0]]


class TestDieBedingungIstDerKern:
    """Ohne sie waere die Liste ein Freibrief."""

    def test_der_gepinnte_speicher_wird_erkannt(self) -> None:
        assert speicher_ist_gepinnt(GEPINNT)

    def test_ein_weiterlaufender_nicht(self) -> None:
        laenger = {**GEPINNT, "BTC D": (date(2012, 1, 1), date(2026, 10, 30), 5417)}

        assert not speicher_ist_gepinnt(laenger)

    def test_und_dann_ist_die_liste_leer(self) -> None:
        """Die Gegenprobe, auf die alles ankommt: Auf einem Speicher, der
        ueber die Pins hinausreicht, bestehen die drei - also gibt es dort
        nichts zu entschuldigen."""
        laenger = {**GEPINNT, "BTC D": (date(2012, 1, 1), date(2026, 10, 30), 5417)}

        assert erwartete_ausfaelle(laenger) == {}

    def test_auf_dem_gepinnten_gilt_sie(self) -> None:
        assert len(erwartete_ausfaelle(GEPINNT)) == 3

    def test_ohne_angabe_gilt_sie_auch(self) -> None:
        """Der Vorgabefall - wer nicht sagt, welchen Speicher er hat, bekommt
        die Liste und nicht die leere Menge."""
        assert erwartete_ausfaelle() == erwartete_ausfaelle(GEPINNT)

    def test_ein_leerer_stand_ist_nicht_gepinnt(self) -> None:
        assert not speicher_ist_gepinnt({})


class TestDieGruendeStimmenMitDenTestsUeberein:
    """Eine Begruendung, die niemand gegen den Test prueft, ist eine
    Behauptung ueber fremden Code."""

    def test_die_zwei_fahren_wirklich_ungeschnitten(self) -> None:
        for datei in LAENGER_ALS_DIE_REIHE:
            quelle = (WURZEL / datei).read_text(encoding="utf-8")

            assert "schneiden=False" in quelle, datei

    def test_und_der_dritte_liest_beide_reihen(self) -> None:
        quelle = (WURZEL / GLEICHES_ENDE[0]).read_text(encoding="utf-8")

        assert 'Interval("15")' in quelle
        assert "_letzter_voller_tag" in quelle

    def test_und_uebersprang_vorher_still(self) -> None:
        """Warum es erst jetzt auffiel: Ohne feine Kerzen hat er
        uebersprungen."""
        quelle = (WURZEL / GLEICHES_ENDE[0]).read_text(encoding="utf-8")

        assert "keine feinen Kerzen im Speicher" in quelle


class TestDerWegNenntSie:
    def test_wiederherstellung_zaehlt_die_drei_auf(self) -> None:
        text = "\n".join(wiederherstellung())

        for datei in erwartete_ausfaelle():
            assert datei in text

    def test_und_verweist_auf_die_begruendung(self) -> None:
        text = "\n".join(wiederherstellung())

        assert "erwartete_ausfaelle()" in text
        assert "mit Grund" in text


@pytest.mark.daten
class TestAmEchtenSpeicher:
    def test_er_ist_gepinnt(self) -> None:
        """Der Speicher dieses Containers ist mit den Befehlen aus 429
        hergestellt - also exakt auf den Pins."""
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.datenstand import FEINREIHEN, REIHEN, grenzen

        speicher = CandleStore(get_settings().paths.data_store)
        stand: dict[str, tuple] = {}
        stand |= grenzen(
            {f"{r.symbol} D": speicher.read(r.symbol, Interval("D")) for r in REIHEN}
        )
        stand |= grenzen(
            {f"{x} 15": speicher.read(x, Interval("15")) for x in FEINREIHEN}
        )
        if len(stand) < 4:
            pytest.skip("Speicher unvollstaendig")

        assert speicher_ist_gepinnt(stand)
        assert len(erwartete_ausfaelle(stand)) == 3


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_bedingung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 430)

        assert "Freibrief" in eintrag.ergebnis
        assert "49" in eintrag.ergebnis

    def test_und_dass_ein_vierter_ein_ausfall_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 430)

        assert "vierter Ausfall ist ein Ausfall" in eintrag.ergebnis

    def test_und_429_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 429).zuletzt == 430
