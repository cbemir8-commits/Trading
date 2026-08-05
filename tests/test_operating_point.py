"""Tests fuer die Betriebspunkt-Rechnung.

Der Schwerpunkt liegt auf den beiden Stellen, an denen hier schon einmal ein
falsches Ergebnis entstanden ist: dem Zuschnitt auf den gemeinsamen Zeitraum
und den stillschweigend abgelehnten Orders.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.operating_point import (
    Stufe,
    _ausduennen,
    as_payload,
    common_range,
    highest_safe,
    kill_switch_hits,
    turning_point,
)


def _stufe(ziel: float, endwert: float, kill_switch: int = 0) -> Stufe:
    return Stufe(
        vola_ziel=ziel,
        hebel=ziel / 60.0,
        cagr_pct=ziel / 5.0,
        drawdown_pct=ziel / 6.0,
        sharpe=0.8,
        endwert=endwert,
        kill_switch=kill_switch,
        curve=np.array([500.0, endwert]),
    )


def _frame(von: str, bis: str) -> pd.DataFrame:
    zeiten = pd.date_range(von, bis, freq="D", tz="UTC")
    return pd.DataFrame({"open_time": zeiten, "close": np.arange(len(zeiten), dtype=float)})


class TestGemeinsamerZeitraum:
    def test_schneidet_auf_die_ueberschneidung(self) -> None:
        """BTC ab 2012, ETH ab 2017 - gerechnet wird ab 2017.

        Ohne diesen Schnitt entstehen zwei verschieden lange Kapitalkurven.
        Die punktweise uebereinanderzulegen hiesse, BTCs 2013 neben ETHs 2018
        zu stellen - und genau das hat hier einmal einen Rueckgang von 4,93 %
        erzeugt, der wie ein Streuungsgewinn aussah.
        """
        frames = {
            "BTC": _frame("2012-01-01", "2026-01-01"),
            "ETH": _frame("2017-01-01", "2025-06-01"),
        }

        geschnitten = common_range(frames)

        laengen = {len(f) for f in geschnitten.values()}
        assert len(laengen) == 1, "nach dem Schnitt muessen alle gleich lang sein"
        for f in geschnitten.values():
            assert f["open_time"].iloc[0] == pd.Timestamp("2017-01-01", tz="UTC")
            assert f["open_time"].iloc[-1] == pd.Timestamp("2025-06-01", tz="UTC")

    def test_ein_markt_bleibt_unveraendert(self) -> None:
        frames = {"BTC": _frame("2012-01-01", "2026-01-01")}

        assert len(common_range(frames)["BTC"]) == len(frames["BTC"])

    def test_ohne_maerkte_leer(self) -> None:
        assert common_range({}) == {}


class TestKillSwitch:
    def test_ruhige_kurve_loest_nie_aus(self) -> None:
        assert kill_switch_hits(np.linspace(500.0, 900.0, 200), 15.0) == 0

    def test_tiefer_rueckgang_loest_aus(self) -> None:
        kurve = np.array([500.0, 600.0, 480.0, 500.0])  # -20 % vom Hoch

        assert kill_switch_hits(kurve, 15.0) == 1

    def test_nach_dem_ausloesen_wird_neu_gezaehlt(self) -> None:
        """Sonst zaehlt ein einziger Einbruch endlos weiter mit.

        Im Livebetrieb wird beim Ausloesen gestoppt und spaeter mit dem
        verbliebenen Kapital neu begonnen. Ohne diesen Neustart meldet ein
        tiefer Rueckgang, der lange braucht, hunderte Ausloesungen - eine
        Zahl, die nichts mehr bedeutet.
        """
        # Ein Einbruch, der lange unten bleibt: ohne Neustart waeren es viele.
        kurve = np.array([500.0, 1000.0, *([700.0] * 50)])

        assert kill_switch_hits(kurve, 15.0) == 1

    def test_zwei_getrennte_einbrueche_zaehlen_zweimal(self) -> None:
        kurve = np.array([500.0, 1000.0, 800.0, 1200.0, 950.0])

        assert kill_switch_hits(kurve, 15.0) == 2

    def test_kurze_kurve_ist_kein_fehler(self) -> None:
        assert kill_switch_hits(np.array([500.0]), 15.0) == 0


class TestEmpfehlung:
    def test_hoechste_sichere_stufe(self) -> None:
        stufen = [
            _stufe(30, 800), _stufe(50, 1200), _stufe(60, 1400),
            _stufe(75, 1700, kill_switch=2), _stufe(90, 2000, kill_switch=5),
        ]

        beste = highest_safe(stufen)

        assert beste is not None
        assert beste.vola_ziel == 60

    def test_keine_sichere_stufe(self) -> None:
        """Ehrlicher als die am wenigsten schlimme zu empfehlen."""
        stufen = [_stufe(30, 800, kill_switch=1), _stufe(50, 1200, kill_switch=3)]

        assert highest_safe(stufen) is None

    def test_wendepunkt_wird_gefunden(self) -> None:
        stufen = [_stufe(50, 1200), _stufe(100, 2000), _stufe(150, 1800)]

        wende = turning_point(stufen)

        assert wende is not None
        assert wende.vola_ziel == 150

    def test_ohne_wendepunkt_kommt_nichts(self) -> None:
        """Wichtig, weil ich diesen Punkt einmal gemeldet habe, obwohl es ihn
        nicht gab.

        Er entstand durch abgelehnte ETH-Orders an einer falsch gesetzten
        Hoechstmenge. Mit den richtigen Kontraktdaten steigt der Endwert
        durchgehend - und dann darf hier nichts gemeldet werden.
        """
        stufen = [_stufe(50, 1200), _stufe(100, 2000), _stufe(150, 3200)]

        assert turning_point(stufen) is None


class TestNutzlast:
    def test_enthaelt_jede_stufe(self) -> None:
        stufen = [_stufe(50, 1200), _stufe(100, 2000, kill_switch=6)]

        payload = as_payload(
            stufen, markets=["BTC", "ETH"], kill_switch_pct=15.0, start_capital=500.0
        )

        assert len(payload["stufen"]) == 2
        assert payload["stufen"][1]["kill_switch"] == 6
        assert payload["maerkte"] == ["BTC", "ETH"]

    def test_kurve_endet_auf_dem_endwert(self) -> None:
        """Sonst zeigt die Grafik etwas anderes als die Zahl daneben."""
        kurve = np.concatenate([np.linspace(500.0, 900.0, 500), [1234.0]])

        gekuerzt = _ausduennen(kurve, punkte=90)

        assert gekuerzt[-1] == 1234
        assert len(gekuerzt) <= 91, "nie mehr Stuetzstellen als bestellt"

    def test_kurze_kurve_bleibt_vollstaendig(self) -> None:
        kurve = np.array([500.0, 600.0, 700.0])

        assert _ausduennen(kurve, punkte=90) == [500, 600, 700]


class TestMessung:
    def test_ohne_maerkte_ist_ein_fehler(self) -> None:
        from research.operating_point import measure

        with pytest.raises(ValueError, match="Betriebspunkt"):
            measure({}, lambda z: None, None)
