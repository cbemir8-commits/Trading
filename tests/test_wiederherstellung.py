"""Was ein frischer Container braucht, um messen zu koennen - Befund 429.

``datenstand.befehle()`` stellt die Zulassungsreihe her, und das ist richtig -
nur ist es die **halbe** Messfaehigkeit. Gemessen in dem Container, der in
Befund 427 neu aufgesetzt wurde, nach dem dokumentierten Weg: **sieben**
Datentests rot, kein einziger wegen eines Mangels am Code.

    5 x test_generationszuordnung   es fehlen die Viertelstundenkerzen
    2 x Speicher gleich Reihe       sie messen gerade die Differenz

Und die erste Wand ist die unfreundlichste: Fehlt ein Intervall ganz, brach
``common_range`` mit ``max() arg is an empty sequence`` ab - kein Wort darueber,
dass Kerzen fehlen.
"""

from __future__ import annotations

import pandas as pd
import pytest

from research.datenstand import (
    FEINANFANG,
    FEINBALKEN,
    FEINENDE,
    FEINREIHEN,
    LAENGER_ALS_DIE_REIHE,
    SERIENENDE,
    befehle,
    feinbefehle,
    wiederherstellung,
)


class TestDieFeinreiheHatJetztEinenWegZurueck:
    def test_je_bein_ein_befehl_und_ein_raeumen(self) -> None:
        zeilen = feinbefehle()

        assert len(zeilen) == 1 + len(FEINREIHEN)
        assert zeilen[0].startswith("rm -rf ")
        for symbol in FEINREIHEN:
            assert any(f"--symbol {symbol}" in z for z in zeilen[1:])

    def test_mit_intervall_und_anfang_ausgeschrieben(self) -> None:
        """Beides sind Vorgabewerte von ``cli referenz`` - und ein Befehl,
        der sich darauf verlaesst, sagt nicht, welche Reihe er herstellt."""
        for zeile in feinbefehle()[1:]:
            assert "-i 15" in zeile
            assert f"--von {FEINANFANG.isoformat()}" in zeile

    def test_das_ende_bekommt_keinen_tag_dazu(self) -> None:
        """Der Unterschied zur Tagesreihe, und er ist leicht zu verwechseln:
        ``SERIENENDE`` ist der letzte Balken, ``FEINENDE`` ist schon
        ausschliessend."""
        for zeile in feinbefehle()[1:]:
            assert f"--bis {FEINENDE.isoformat()}" in zeile

        tageszeilen = befehle()[1:]
        assert all(f"--bis {SERIENENDE.isoformat()}" not in z for z in tageszeilen)

    def test_geraeumt_wird_das_feine_verzeichnis(self) -> None:
        """Nicht das der Tagesreihe - sonst loescht der Weg zur Feinreihe die
        Reihe, auf der die gepflegten Zahlen stehen."""
        raeumen = feinbefehle()[0]

        assert "/15" in raeumen
        assert "/D" not in raeumen


class TestDieVollstaendigeAuskunft:
    def test_sie_nennt_beide_reihen(self) -> None:
        text = "\n".join(wiederherstellung())

        for zeile in befehle():
            assert zeile in text
        for zeile in feinbefehle():
            assert zeile in text

    def test_und_sagt_was_sie_nicht_herstellt(self) -> None:
        """Eine Anleitung, die das Fehlende nicht nennt, laesst den Leser die
        zwei roten Tests selbst erklaeren."""
        text = "\n".join(wiederherstellung())

        assert "Nicht hergestellt" in text
        for datei in LAENGER_ALS_DIE_REIHE:
            assert datei in text

    def test_und_warnt_vor_dem_speicher_bis_heute(self) -> None:
        """Weil genau das Befund 363 ausgeloest hat."""
        text = "\n".join(wiederherstellung())

        assert "bei jedem Lauf ein anderer" in text
        assert "363" in text

    def test_die_zwei_dateien_gibt_es(self) -> None:
        """Eine Liste, die auf Tests zeigt, die es nicht mehr gibt, ist genau
        die Altlast, gegen die dieses Projekt seine Register prueft."""
        from pathlib import Path

        wurzel = Path(__file__).resolve().parents[1]
        for datei in LAENGER_ALS_DIE_REIHE:
            assert (wurzel / datei).exists(), datei

    def test_und_sie_messen_wirklich_ungeschnitten(self) -> None:
        """Die Begruendung der Liste, nachgeprueft am Quelltext: Beide fahren
        ihren Lauf mit ``schneiden=False``."""
        from pathlib import Path

        wurzel = Path(__file__).resolve().parents[1]
        for datei in LAENGER_ALS_DIE_REIHE:
            quelle = (wurzel / datei).read_text(encoding="utf-8")
            assert "schneiden=False" in quelle, datei


class TestLeerIstNichtDasselbeWieNichtDa:
    """``common_range`` prueft ``if not frames`` - das faengt ein fehlendes
    Dictionary, nicht ein Dictionary voller leerer Rahmen."""

    def _leer(self) -> pd.DataFrame:
        return pd.DataFrame(columns=["open_time"])

    def _voll(self, von: str = "2020-01-01", n: int = 3) -> pd.DataFrame:
        return pd.DataFrame(
            {"open_time": pd.date_range(von, periods=n, tz="UTC")}
        )

    def test_ohne_rahmen_bleibt_es_leer(self) -> None:
        from backtest.portfolio_walkforward import common_range

        assert common_range({}) == {}

    def test_alle_leer_sagt_was_fehlt(self) -> None:
        from backtest.portfolio_walkforward import common_range

        with pytest.raises(ValueError, match="Keine Kerzen fuer") as fehler:
            common_range({"BTCUSD_BITSTAMP": self._leer(), "X": self._leer()})

        text = str(fehler.value)
        assert "BTCUSD_BITSTAMP" in text and "X" in text
        assert "wiederherstellung()" in text

    def test_und_nicht_mehr_max_arg_is_an_empty_sequence(self) -> None:
        """Die Meldung, die es vorher war - gemessen an
        'test_generationszuordnung', das genau so abbrach."""
        from backtest.portfolio_walkforward import common_range

        with pytest.raises(ValueError) as fehler:
            common_range({"X": self._leer()})

        assert "empty sequence" not in str(fehler.value)

    def test_ein_leeres_bein_neben_vollen_bricht_nicht_ab(self) -> None:
        """Gegenprobe: Der Abbruch gilt nur, wenn **nichts** da ist."""
        from backtest.portfolio_walkforward import common_range

        ergebnis = common_range({"A": self._voll(), "B": self._leer()})

        assert len(ergebnis["A"]) == 3
        assert ergebnis["B"].empty

    def test_aber_es_wird_gemeldet(self) -> None:
        """Sonst rechnet ein Korb stillschweigend mit weniger Beinen."""
        import structlog

        from backtest.portfolio_walkforward import common_range

        with structlog.testing.capture_logs() as protokoll:
            common_range({"A": self._voll(), "B": self._leer()})

        meldungen = [x for x in protokoll if x["event"] == "portfolio.bein_ohne_kerzen"]
        assert len(meldungen) == 1
        assert meldungen[0]["ohne"] == ["B"]
        assert meldungen[0]["mit"] == ["A"]

    def test_und_nicht_wenn_alle_kerzen_haben(self) -> None:
        import structlog

        from backtest.portfolio_walkforward import common_range

        with structlog.testing.capture_logs() as protokoll:
            common_range({"A": self._voll(), "B": self._voll()})

        assert not [x for x in protokoll if x["event"] == "portfolio.bein_ohne_kerzen"]


@pytest.mark.daten
class TestDerWegFuehrtWirklichDahin:
    """Ein Wiederherstellungsweg, den niemand gefahren ist, ist eine
    Vermutung - und bei der Tagesreihe hat das ``--bis`` schon einen Anlauf
    gekostet (Befund 363)."""

    @pytest.fixture(scope="module")
    def feinreihe(self):
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore

        speicher = CandleStore(get_settings().paths.data_store)
        roh = {s: speicher.read(s, Interval("15")) for s in FEINREIHEN}
        if any(x is None or x.empty for x in roh.values()):
            pytest.skip("keine Viertelstundenkerzen im Speicher")
        return roh

    def test_der_schnitt_ergibt_die_gepinnte_balkenzahl(self, feinreihe) -> None:
        from research.datenstand import alle_fein_geschnitten

        fein = alle_fein_geschnitten(feinreihe)

        for name, rahmen in fein.items():
            assert len(rahmen) == FEINBALKEN, name

    def test_und_den_gepinnten_abdruck(self, feinreihe) -> None:
        """Der eigentliche Beweis, dass der Weg zur Reihe von 426 fuehrt."""
        from research.datenstand import alle_fein_geschnitten
        from research.datenstempel import SERIE_15

        fein = alle_fein_geschnitten(feinreihe)

        assert SERIE_15.abweichungen(fein) == ()
        assert SERIE_15.passt(fein)

    def test_das_bis_schneidet_auf_den_vortag(self, feinreihe) -> None:
        """``--bis`` ist ausschliessend: Der letzte Balken liegt am Tag vor
        ``FEINENDE``, und der Stempel nennt genau den."""
        from research.datenstempel import SERIE_15

        for rahmen in feinreihe.values():
            assert str(rahmen["open_time"].max())[:10] <= SERIE_15.bis


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_sieben(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 429)

        assert "sieben" in eintrag.ergebnis
        assert "empty sequence" in eintrag.ergebnis

    def test_und_dass_keiner_einen_mangel_zeigt(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 429)

        assert "kein einziger wegen eines Mangels am Code" in eintrag.ergebnis

    def test_und_428_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 428).zuletzt == 429
