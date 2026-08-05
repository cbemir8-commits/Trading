"""Kerzen zusammenfassen - und die angefangene Kerze wegwerfen.

Der Test, auf den es ankommt, ist ``TestAngefangeneKerzen``. Alles andere
ist Buchhaltung; dort sitzt der Fehler, der einen Backtest still schoenrechnen
wuerde.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.models import Interval
from data.resample import resample, teilbar

SPALTEN = ["open_time", "open", "high", "low", "close", "volume", "turnover"]


def kerzen(n: int, *, start: str = "2024-01-01", minuten: int = 15) -> pd.DataFrame:
    """``n`` Viertelstundenkerzen mit nachvollziehbaren Kursen.

    Der Kurs steigt um 1 je Kerze, das Hoch liegt 2 darueber, das Tief 3
    darunter. So laesst sich jede zusammengefasste Kerze von Hand nachrechnen.
    """
    zeit = pd.date_range(start, periods=n, freq=f"{minuten}min", tz="UTC")
    basis = pd.Series(range(n), dtype=float) + 100.0
    return pd.DataFrame(
        {
            "open_time": zeit,
            "open": basis,
            "high": basis + 2.0,
            "low": basis - 3.0,
            "close": basis + 0.5,
            "volume": pd.Series([1.0] * n),
            "turnover": basis * 1.0,
        }
    )


class TestZusammenfassen:
    def test_vier_viertelstunden_ergeben_eine_stunde(self):
        grob = resample(kerzen(8), Interval.M15, Interval.H1)

        assert len(grob) == 2
        erste = grob.iloc[0]
        assert erste["open"] == 100.0  # erster Kurs des Fensters
        assert erste["close"] == 103.5  # letzter Kurs des Fensters
        assert erste["high"] == 105.0  # hoechstes Hoch: 103 + 2
        assert erste["low"] == 97.0  # tiefstes Tief: 100 - 3
        assert erste["volume"] == 4.0

    def test_zeitstempel_ist_der_beginn_der_kerze(self):
        """Die Kerze traegt die Zeit ihres **Anfangs**.

        Traeger sie das Ende, waere jede Kerze im Backtest eine Stunde zu
        frueh sichtbar - und damit jede Regel darauf ein Lookahead.
        """
        grob = resample(kerzen(8), Interval.M15, Interval.H1)

        assert grob["open_time"].iloc[0] == pd.Timestamp("2024-01-01 00:00", tz="UTC")
        assert grob["open_time"].iloc[1] == pd.Timestamp("2024-01-01 01:00", tz="UTC")

    def test_spalten_bleiben_wie_sie_waren(self):
        grob = resample(kerzen(96), Interval.M15, Interval.H4)
        assert list(grob.columns) == SPALTEN

    def test_leere_reihe_bleibt_leer(self):
        leer = pd.DataFrame(columns=SPALTEN)
        assert resample(leer, Interval.M15, Interval.H1).empty


class TestAngefangeneKerzen:
    """Der eigentliche Zweck des Moduls."""

    def test_letzte_unvollstaendige_kerze_faellt_weg(self):
        """Sechs Viertelstunden sind eine Stunde und eine halbe.

        Die halbe darf nicht als Stundenkerze erscheinen: Ihr ``close`` waere
        der Kurs nach 30 Minuten, ausgegeben als Schlusskurs der vollen
        Stunde. Eine Regel darauf handelte auf einem Kurs, den es zu diesem
        Zeitpunkt noch nicht gab.
        """
        grob = resample(kerzen(6), Interval.M15, Interval.H1)

        assert len(grob) == 1
        assert grob["open_time"].iloc[0] == pd.Timestamp("2024-01-01 00:00", tz="UTC")

    def test_erste_unvollstaendige_kerze_faellt_auch_weg(self):
        """Beginnt die Reihe mitten im Fenster, fehlt der wahre Eroeffnungskurs."""
        angeschnitten = kerzen(8).iloc[2:].reset_index(drop=True)

        grob = resample(angeschnitten, Interval.M15, Interval.H1)

        assert len(grob) == 1
        assert grob["open_time"].iloc[0] == pd.Timestamp("2024-01-01 01:00", tz="UTC")

    def test_kerze_mit_datenluecke_faellt_weg(self):
        """Der Fall, der am Rand-Abschneiden vorbeikaeme.

        Eine Vier-Stunden-Kerze aus zwei Viertelstunden sieht in der Tabelle
        aus wie jede andere - nur ist ihr Hoch nicht das Hoch dieser vier
        Stunden. Deshalb wird gezaehlt und nicht nur der Rand geschnitten.
        """
        fein = kerzen(8)
        loechrig = fein.drop(index=[5, 6]).reset_index(drop=True)

        grob = resample(loechrig, Interval.M15, Interval.H1)

        assert len(grob) == 1  # nur die erste Stunde ist vollstaendig
        assert grob["open_time"].iloc[0] == pd.Timestamp("2024-01-01 00:00", tz="UTC")

    def test_ohne_pruefung_kaeme_die_angefangene_kerze_durch(self):
        """Haelt fest, dass die Pruefung wirklich etwas tut.

        Ohne diesen Test koennte ``vollstaendig`` versehentlich wirkungslos
        werden, und alle anderen Tests blieben gruen.
        """
        grob = resample(kerzen(6), Interval.M15, Interval.H1, vollstaendig=False)

        assert len(grob) == 2
        # Und das ist genau der falsche Schlusskurs: der von 01:15 Uhr,
        # ausgegeben als Schlusskurs der Stunde ab 01:00.
        assert grob["close"].iloc[1] == 105.5

    def test_ganz_fehlende_kerze_wird_nicht_aufgefuellt(self):
        """Wo nicht gehandelt wurde, entsteht keine Kerze.

        Ein ``ffill`` waere hier verlockend und falsch: Der Backtest duerfte
        dann in einem Zeitraum handeln, in dem es keinen Markt gab.
        """
        fein = pd.concat(
            [kerzen(4), kerzen(4, start="2024-01-01 02:00")], ignore_index=True
        )

        grob = resample(fein, Interval.M15, Interval.H1)

        assert len(grob) == 2
        zeiten = list(grob["open_time"])
        assert pd.Timestamp("2024-01-01 01:00", tz="UTC") not in zeiten


class TestTeilbarkeit:
    def test_stunde_geht_aus_viertelstunden(self):
        assert teilbar(Interval.M15, Interval.H1)
        assert teilbar(Interval.M15, Interval.H4)
        assert teilbar(Interval.M15, Interval.D1)

    def test_rueckwaerts_geht_nicht(self):
        """Aus Stunden lassen sich keine Viertelstunden machen.

        Klingt selbstverstaendlich, ist es im Code aber nicht: Ohne die
        Pruefung erzeugte ``pandas`` klaglos vier identische Kerzen je Stunde.
        """
        assert not teilbar(Interval.H1, Interval.M15)

    def test_gleiches_intervall_ist_kein_zusammenfassen(self):
        assert not teilbar(Interval.H1, Interval.H1)

    def test_krumme_verhaeltnisse_gehen_nicht(self):
        assert teilbar(Interval.H2, Interval.H6)  # 6 = 3 x 2
        assert not teilbar(Interval.H4, Interval.H6)  # 6 ist kein Vielfaches von 4

    def test_resample_lehnt_krumme_verhaeltnisse_ab(self):
        with pytest.raises(ValueError, match="Vielfaches"):
            resample(kerzen(8, minuten=240), Interval.H4, Interval.H6)


class TestTagesKerzenStimmenMitDenGeholtenUeberein:
    """Die Probe aufs Ganze - gegen echte Daten, nicht gegen ein Konstrukt."""

    def test_aus_viertelstunden_gebaute_tage_gleichen_den_geholten(self):
        from core.config import get_settings
        from data.store import CandleStore

        store = CandleStore(get_settings().paths.data_store)
        fein = store.read("BTCUSD_BITSTAMP", Interval.M15)
        tage = store.read("BTCUSD_BITSTAMP", Interval.D1)
        if fein.empty or tage.empty:
            pytest.skip("Keine Kerzen im Speicher - nur auf dem Entwicklungsrechner")

        gebaut = resample(fein, Interval.M15, Interval.D1)
        zusammen = gebaut.merge(
            tage, on="open_time", suffixes=("_gebaut", "_geholt")
        )
        assert len(zusammen) > 300, "zu wenig Ueberschneidung zum Vergleichen"

        # Bitstamp liefert Tageskerzen aus derselben Quelle wie die
        # Viertelstunden; kleine Abweichungen bleiben trotzdem moeglich, weil
        # die Aggregation dort auf dem Rohhandel sitzt und nicht auf den
        # gerundeten Kerzen. Ein Promille Abstand ist das, was uebrig ist.
        for spalte in ("open", "high", "low", "close"):
            abstand = (
                zusammen[f"{spalte}_gebaut"] - zusammen[f"{spalte}_geholt"]
            ).abs() / zusammen[f"{spalte}_geholt"]
            assert abstand.median() < 0.001, f"{spalte} weicht ab"
