"""Ableiten gegen Laden - und die angefangene Randkerze.

**Befund 239.** Befund 213 hat ``data/resample.py`` als gebaut und
unverdrahtet gefunden und die Frage offen gelassen, ob Tageskerzen abgeleitet
oder geladen gehoeren. Sie stand seither unter *gemessen und offen*.

Beantwortet wird sie, indem man beide Reihen nebeneinanderlegt: Auf den 2.344
gemeinsamen Tagen stimmen sie ueberein - bis auf zwei Kerzen, und die eine
davon ist der eigentliche Fund. Die letzte gespeicherte Tageskerze traegt rund
die Haelfte des Volumens ihres Tages und steht in der Reihe wie eine volle.

Das ist der Fallstrick, vor dem ``resample.py`` warnt, nur in den
gespeicherten Daten statt im Code.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.models import Interval
from data.gegenprobe import SPALTEN, Gegenprobe, gegenprobe


def _viertelstunden(
    tage: int, *, ab: str = "2024-01-01", kappen: int = 0
) -> pd.DataFrame:
    """Eine saubere Viertelstundenreihe ueber ``tage`` Tage.

    ``kappen`` schneidet Kerzen am Ende ab - so entsteht ein halber letzter
    Tag, ohne dass dafuer echte Boersendaten noetig waeren.
    """
    n = tage * 96 - kappen
    zeiten = pd.date_range(ab, periods=n, freq="15min", tz="UTC")
    preis = pd.Series(range(n), dtype=float) + 100.0
    return pd.DataFrame(
        {
            "open_time": zeiten,
            "open": preis,
            "high": preis + 1.0,
            "low": preis - 1.0,
            "close": preis + 0.5,
            "volume": pd.Series([1.0] * n),
            "turnover": pd.Series([1.0] * n),
        }
    )


def _tage_aus(fein: pd.DataFrame) -> pd.DataFrame:
    from data.resample import resample

    return resample(fein, Interval("15"), Interval.D1)


class TestWennBeideStimmen:
    def test_eine_abgeleitete_reihe_stimmt_mit_sich_selbst_ueberein(self) -> None:
        fein = _viertelstunden(5)
        grob = _tage_aus(fein)

        g = gegenprobe(grob, fein, quelle=Interval("15"), ziel=Interval.D1)

        assert g.einig
        assert g.verglichen == 5
        assert not g.angefangene_randkerze

    def test_das_urteil_sagt_es(self) -> None:
        fein = _viertelstunden(5)
        g = gegenprobe(
            _tage_aus(fein), fein, quelle=Interval("15"), ziel=Interval.D1
        )

        assert "selben Ergebnis" in g.urteil()


class TestDieAngefangeneRandkerze:
    """**Der Fund aus Befund 239**, an einem gebauten Fall nachgestellt."""

    @staticmethod
    def _mit_halbem_letzten_tag() -> tuple[pd.DataFrame, pd.DataFrame]:
        voll = _viertelstunden(5)
        # Die gespeicherte grobe Reihe entsteht aus einem halben letzten Tag -
        # so, wie ein Backfill sie schreibt, der mittags laeuft.
        halb = _viertelstunden(5, kappen=48)
        from data.resample import resample

        grob = resample(halb, Interval("15"), Interval.D1, vollstaendig=False)
        return grob, voll

    def test_sie_wird_erkannt(self) -> None:
        grob, fein = self._mit_halbem_letzten_tag()

        g = gegenprobe(grob, fein, quelle=Interval("15"), ziel=Interval.D1)

        assert g.angefangene_randkerze
        assert g.volumenanteil == pytest.approx(0.5, abs=0.01)

    def test_high_und_close_liegen_zu_tief(self) -> None:
        """Genau das, was in den echten Daten steht: ``low`` stimmt, weil das
        Tief frueh faellt; ``high`` und ``close`` fehlt der halbe Tag."""
        grob, fein = self._mit_halbem_letzten_tag()

        g = gegenprobe(grob, fein, quelle=Interval("15"), ziel=Interval.D1)
        spalten = {a.spalte for a in g.abweichungen}

        assert "high" in spalten
        assert "close" in spalten
        assert all(a.relativ > 0 for a in g.abweichungen)

    def test_das_urteil_nennt_den_anteil(self) -> None:
        grob, fein = self._mit_halbem_letzten_tag()

        urteil = gegenprobe(
            grob, fein, quelle=Interval("15"), ziel=Interval.D1
        ).urteil()

        assert "angefangen" in urteil
        assert "%" in urteil

    def test_ein_promille_ist_keine_angefangene_kerze(self) -> None:
        """Boersen buchen Trades nachtraeglich ein. Die Schwelle liegt bei
        99 %, damit daraus keine taegliche Warnung wird."""
        assert not Gegenprobe(verglichen=10, volumenanteil=0.995).angefangene_randkerze
        assert Gegenprobe(verglichen=10, volumenanteil=0.52).angefangene_randkerze


class TestWasNichtVerglichenWird:
    def test_fehlende_zeitraeume_sind_keine_abweichung(self) -> None:
        """Die feine Reihe beginnt in diesem Projekt Jahre spaeter.

        Geschnitten wird aus **derselben** Reihe - zwei unabhaengig erzeugte
        haetten auf denselben Tagen verschiedene Kurse, und der Test wuerde
        dann etwas anderes pruefen als das, was er behauptet.
        """
        lang = _viertelstunden(10, ab="2024-01-01")
        grob = _tage_aus(lang)
        fein = lang[lang["open_time"] >= "2024-01-08"].reset_index(drop=True)

        g = gegenprobe(grob, fein, quelle=Interval("15"), ziel=Interval.D1)

        assert g.verglichen == 3
        assert g.einig

    def test_volume_gehoert_nicht_zu_den_preisspalten(self) -> None:
        """Es wuerde schon bei einer Nachbuchung abweichen und die Preisfrage
        zudecken - fuer die Randkerze wird es eigens herangezogen."""
        assert "volume" not in SPALTEN

    def test_leere_reihen_ergeben_nichts(self) -> None:
        leer = pd.DataFrame(columns=["open_time", *SPALTEN, "volume", "turnover"])

        g = gegenprobe(leer, leer, quelle=Interval("15"), ziel=Interval.D1)

        assert g.verglichen == 0
        assert "nichts zu vergleichen" in g.urteil()


class TestAmEchtenVorrat:
    """Was im Speicher liegt - der eigentliche Befund, nicht nachgestellt."""

    @staticmethod
    def _reihen(symbol: str):
        from core.config import get_settings
        from data.store import CandleStore

        speicher = CandleStore(get_settings().paths.data_store)
        return (
            speicher.read(symbol, Interval("D")),
            speicher.read(symbol, Interval("15")),
        )

    @pytest.mark.langsam
    @pytest.mark.parametrize("symbol", ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"])
    def test_beide_wege_stimmen_bis_auf_zwei_kerzen_ueberein(self, symbol) -> None:
        grob, fein = self._reihen(symbol)
        if grob.empty or fein.empty:
            pytest.skip("keine Kerzen im Speicher")

        g = gegenprobe(grob, fein, quelle=Interval("15"), ziel=Interval.D1)

        assert g.verglichen > 2000
        assert len(g.betroffene_kerzen) <= 2, [str(a) for a in g.abweichungen]

    @pytest.mark.langsam
    @pytest.mark.parametrize("symbol", ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"])
    def test_die_letzte_gespeicherte_tageskerze_ist_angefangen(self, symbol) -> None:
        """**Der Fund.** Er kostet heute nichts - Nachlauf (151) und
        Randschnitt (152) halten den Datenrand aus der Statistik heraus, mit
        und ohne diese Kerze sind alle Zahlen des Bestands gleich. Er steht
        hier trotzdem, weil das eine Eigenschaft des Nachlaufs ist und keine
        der Daten.
        """
        grob, fein = self._reihen(symbol)
        if grob.empty or fein.empty:
            pytest.skip("keine Kerzen im Speicher")

        g = gegenprobe(grob, fein, quelle=Interval("15"), ziel=Interval.D1)

        assert g.angefangene_randkerze
        assert g.volumenanteil < 0.6
