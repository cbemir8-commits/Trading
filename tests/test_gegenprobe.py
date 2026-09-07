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


class TestDiePruefungWirdGerufen:
    """**Befund 240.** Ein Bauteil, das niemand ruft, ist in diesem Projekt
    schon mehrfach aufgefallen - zuletzt ``resample.py`` selbst (Befund 213),
    das dieser Pruefung zugrunde liegt. ``gegenprobe`` waere das naechste
    gewesen: gebaut in 239, gerufen von nichts ausser seinen Tests.
    """

    @staticmethod
    def _paar() -> tuple[pd.DataFrame, pd.DataFrame]:
        voll = _viertelstunden(5)
        halb = _viertelstunden(5, kappen=48)
        from data.resample import resample

        return resample(halb, Interval("15"), Interval.D1, vollstaendig=False), voll

    def test_check_candles_meldet_die_angefangene_randkerze(self) -> None:
        from data.quality import Severity, check_candles

        grob, fein = self._paar()

        bericht = check_candles(
            grob,
            symbol="TEST",
            interval=Interval.D1,
            feiner=fein,
            feiner_intervall=Interval("15"),
        )
        codes = {f.code: f for f in bericht.findings}

        assert "randkerze" in codes
        assert codes["randkerze"].severity is Severity.WARN

    def test_sie_macht_die_reihe_nicht_unbrauchbar(self) -> None:
        """Gemessen kostet sie am Bestand nichts (Befund 239). Die Reihe
        deshalb zu sperren waere schaerfer als die Messung hergibt."""
        from data.quality import check_candles

        grob, fein = self._paar()

        bericht = check_candles(
            grob,
            symbol="TEST",
            interval=Interval.D1,
            feiner=fein,
            feiner_intervall=Interval("15"),
        )

        assert bericht.is_usable

    def test_ohne_feinere_reihe_entfaellt_sie(self) -> None:
        """Keine Heuristik: An den Preisen allein sieht ein halber Tag aus wie
        ein ruhiger."""
        from data.quality import check_candles

        grob, _ = self._paar()

        bericht = check_candles(grob, symbol="TEST", interval=Interval.D1)

        assert "randkerze" not in {f.code for f in bericht.findings}

    def test_eine_unteilbare_reihe_wird_nicht_verglichen(self) -> None:
        """Aus Tageskerzen entstehen keine Tageskerzen."""
        from data.quality import check_candles

        fein = _viertelstunden(5)
        grob = _tage_aus(fein)

        bericht = check_candles(
            grob,
            symbol="TEST",
            interval=Interval.D1,
            feiner=grob,
            feiner_intervall=Interval.D1,
        )

        assert "gegenprobe" not in {f.code for f in bericht.findings}

    def test_der_befehl_uebergibt_die_feinere_reihe(self) -> None:
        """Ohne diese Zeile bliebe die Pruefung ein Modul ohne Aufrufer."""
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text())
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "quality"
        )

        assert "feiner=" in quelle
        assert "_feinste_teilbare" in quelle


class TestDerSchiedsrichterWirdGewaehlt:
    def test_die_feinste_teilbare_gewinnt(self) -> None:
        """Mehr Bausteine beziffern eine angefangene Kerze genauer."""
        import cli

        vorhanden = [
            ("BTC", Interval("15")),
            ("BTC", Interval("240")),
            ("BTC", Interval.D1),
        ]

        assert cli._feinste_teilbare(vorhanden, "BTC", Interval.D1) is Interval("15")

    def test_andere_maerkte_zaehlen_nicht(self) -> None:
        import cli

        vorhanden = [("ETH", Interval("15")), ("BTC", Interval.D1)]

        assert cli._feinste_teilbare(vorhanden, "BTC", Interval.D1) is None

    def test_ohne_feinere_reihe_gibt_es_keinen(self) -> None:
        import cli

        vorhanden = [("BTC", Interval.D1)]

        assert cli._feinste_teilbare(vorhanden, "BTC", Interval.D1) is None
