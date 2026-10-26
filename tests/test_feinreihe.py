"""Die Feinreihe ist gepinnt, bevor eine Zahl darauf steht - Befund 426.

Befund 363 musste die Tagesreihe **nachtraeglich** rekonstruieren: Ein neu
aufgesetzter Container hatte den Speicher mitgenommen, frisch nachgeladen
fielen fuenfzehn Tests, und keiner sagte "andere Reihe". Auf
Viertelstundenkerzen steht noch keine Zahl des Projekts - also kostet der
Stempel hier nichts und erspart genau jenen Lauf.

Die Reihe ist **keine Zulassungsreihe**: Zugelassen wird auf Tageskerzen, dort
stehen alle elf Gates (Befund 213).
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from research.datenstand import (
    BALKEN_JE_TAG,
    FEINANFANG,
    FEINBALKEN,
    FEINENDE,
    FEINREIHEN,
    FEINTAGE,
    INTERVALL,
    SERIENENDE,
    fein_geschnitten,
    feinlaenge_stimmt,
    feinzeile,
)
from research.datenstempel import SERIE_15


class TestDieReihenangabenGehenAuf:
    def test_balken_je_tag_sind_sechsundneunzig(self) -> None:
        assert BALKEN_JE_TAG == 24 * 4 == 96

    def test_die_tage_decken_sich_mit_den_grenzen(self) -> None:
        assert (FEINENDE - FEINANFANG).days == FEINTAGE == 2393

    def test_und_die_balkenzahl_geht_ohne_rest_auf(self) -> None:
        """Bei Tageskerzen ist ein fehlender Balken ein fehlender Tag und
        faellt auf. Hier sind es 96 je Tag, und eine Luecke von einer Stunde
        verschwindet in der Summe - diese Gleichung macht sie sichtbar."""
        assert FEINBALKEN == FEINTAGE * BALKEN_JE_TAG == 229_728
        assert feinlaenge_stimmt()

    def test_der_anfang_ist_der_aus_dem_plan(self) -> None:
        """``cli backfill --intervall 15 --von 2020-03-30`` - derselbe Tag."""
        assert date(2020, 3, 30) == FEINANFANG

    def test_beide_beine_sind_gleich_lang(self) -> None:
        """Anders als bei Tageskerzen, wo BTC 2054 Tage weiter zurueckreicht."""
        assert len(FEINREIHEN) == 2
        assert set(FEINREIHEN) == {"BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"}


class TestEsIstKeineZulassungsreihe:
    """Der Satz, ohne den der Stempel etwas Falsches behaupten wuerde."""

    def test_zugelassen_wird_weiter_auf_tageskerzen(self) -> None:
        assert INTERVALL == "D"

    def test_die_feinreihe_hat_ein_eigenes_ende(self) -> None:
        """Sie darf das Serienende der Zulassungsreihe nicht verschieben."""
        assert FEINENDE != SERIENENDE
        assert date(2026, 8, 29) == SERIENENDE

    def test_und_der_kopf_sagt_es(self) -> None:
        import research.datenstand as d

        quelle = inspect.getsource(d)

        assert "**Keine Zulassungsreihe.**" in quelle
        assert "eine Messreihe, kein" in quelle

    def test_und_warum_jetzt_gepinnt_wird(self) -> None:
        import research.datenstand as d

        quelle = inspect.getsource(d)

        assert "bevor die erste Zahl darauf gemessen ist" in quelle
        assert "fuenfzehn Tests" in quelle


class TestDerStempel:
    def test_er_nennt_dieselbe_balkenzahl(self) -> None:
        assert SERIE_15.balken == FEINBALKEN

    def test_und_den_letzten_balken_nicht_die_grenze(self) -> None:
        """``FEINENDE`` ist ausschliessend, der Stempel nennt den letzten
        Balken - ein Tag Unterschied, und er ist Absicht."""
        assert SERIE_15.von == "2020-03-30"
        assert SERIE_15.bis == "2026-10-17"
        assert date(2026, 10, 18) == FEINENDE

    def test_er_hat_fuer_jedes_bein_einen_abdruck(self) -> None:
        assert set(SERIE_15.abdruecke) == set(FEINREIHEN)
        for abdruck in SERIE_15.abdruecke.values():
            assert len(abdruck) == 16
            assert all(z in "0123456789abcdef" for z in abdruck)

    def test_die_beine_haben_verschiedene_abdruecke(self) -> None:
        """Gegenprobe: Zwei gleiche Abdruecke hiessen, dass derselbe Rahmen
        zweimal gehasht wurde."""
        assert len(set(SERIE_15.abdruecke.values())) == 2

    def test_und_er_ist_nicht_der_der_tagesreihe(self) -> None:
        from research.datenstempel import SERIE

        assert SERIE_15.abdruecke != SERIE.abdruecke
        assert SERIE_15.balken != SERIE.balken


class TestDerSchnittIstHalboffen:
    def _rahmen(self, letzte: str):
        import pandas as pd

        zeiten = pd.date_range("2026-10-17 23:00", letzte, freq="15min", tz="UTC")
        return pd.DataFrame(
            {
                "open_time": zeiten,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
            }
        )

    def test_der_grenztag_selbst_fliegt_raus(self) -> None:
        """Wer hier ``<=`` schreibt, nimmt den ersten Balken des Folgetags
        mit und bekommt 229.729 statt 229.728."""
        geschnitten = fein_geschnitten(self._rahmen("2026-10-18 00:15"))
        letzte = geschnitten["open_time"].max()

        assert str(letzte) == "2026-10-17 23:45:00+00:00"
        assert len(geschnitten) == 4

    def test_ein_rahmen_ohne_zeitspalte_bleibt_unberuehrt(self) -> None:
        import pandas as pd

        ohne = pd.DataFrame({"close": [1.0, 2.0]})

        assert fein_geschnitten(ohne) is ohne

    def test_ein_leerer_rahmen_bleibt_leer(self) -> None:
        import pandas as pd

        leer = pd.DataFrame(columns=["open_time", "close"])

        assert fein_geschnitten(leer).empty


class TestDieZeileMeldetDieReihe:
    def test_sie_nennt_beide_beine(self) -> None:
        import pandas as pd

        rahmen = {
            s: pd.DataFrame({"open_time": pd.to_datetime(["2020-03-30", "2026-10-17"], utc=True)})
            for s in FEINREIHEN
        }
        zeile = feinzeile(rahmen)

        assert "Feinreihe 15m:" in zeile
        for s in FEINREIHEN:
            assert s in zeile

    def test_sie_markiert_eine_abweichende_laenge(self) -> None:
        """Der Punkt der Zeile (Befund 370): Eine Zahl auf einer anderen Reihe
        soll nicht stumm neben der gepinnten stehen."""
        import pandas as pd

        rahmen = {
            s: pd.DataFrame({"open_time": pd.to_datetime(["2020-03-30", "2026-10-17"], utc=True)})
            for s in FEINREIHEN
        }

        assert f"gepinnt {FEINBALKEN}" in feinzeile(rahmen)

    def test_und_meldet_ein_fehlendes_bein(self) -> None:
        assert "fehlt" in feinzeile({})


@pytest.fixture(scope="module")
def fein():
    """Die echten Viertelstundenkerzen, auf die Feinreihe geschnitten.

    Einmal je Modul: Zweimal 229.728 Balken zu lesen und zu hashen dauert
    ueber eine Minute, und jeder Test will dieselbe Reihe.
    """
    from core.models import Interval
    from data.store import CandleStore
    from research.datenstand import alle_fein_geschnitten

    speicher = CandleStore("data_store")
    roh = {s: speicher.read(s, Interval.M15) for s in FEINREIHEN}
    if any(r is None or r.empty for r in roh.values()):
        pytest.skip("keine Viertelstundenkerzen im Speicher")
    return alle_fein_geschnitten(roh)


@pytest.mark.daten
class TestGegenDieEchtenKerzen:
    """Die Probe, die den Stempel ueberhaupt rechtfertigt - ohne sie waere er
    eine Behauptung."""

    def test_der_stempel_passt(self, fein) -> None:
        assert SERIE_15.abweichungen(fein) == ()
        assert SERIE_15.passt(fein)

    def test_die_balkenzahl_ist_die_gepinnte(self, fein) -> None:
        for name, rahmen in fein.items():
            assert len(rahmen) == FEINBALKEN, name

    def test_und_die_zeile_meldet_keine_abweichung(self, fein) -> None:
        assert "gepinnt" not in feinzeile(fein)


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_gemessene_reihe(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 426)

        assert "229.728" in eintrag.ergebnis
        assert "2393" in eintrag.ergebnis

    def test_und_dass_der_backfill_hier_erledigt_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 426)

        assert "100,0000 %" in eintrag.ergebnis
        assert "backfill" in eintrag.ergebnis

    def test_und_dass_es_keine_zulassungsreihe_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 426)

        assert "keine Zulassungsreihe" in eintrag.ergebnis

    def test_und_425_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 425).zuletzt == 426
