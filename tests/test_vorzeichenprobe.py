"""Steht die Latte richtig - und zwar in beiden Scans?

**Befund 277.** Befund 276 hat im Vorteilsscan gefunden, dass ``schwelle_fuer``
zu niedrig steht: Die Latte rechnet mit einer Normalverteilung, die die Daten
dort nicht haben. Dieselbe Funktion traegt den zweiten Scan dieses Projekts,
``research/tageszeit``. Ob der Befund dorthin traegt, war eine offene Frage -
und offene Fragen werden hier gemessen, nicht vermutet.

Was hier gehalten wird
----------------------
**Die Probe passt zur Bauart.** Im Vorteilsscan wird der Teiler verschoben,
weil es einen gibt, der stehenbleiben kann. Hier ist der Vergleich gepaart -
innen gegen aussen am selben Tag -, also wird die **Richtung** jedes
Tagesunterschieds gewuerfelt und der Betrag in Ruhe gelassen.

**Die Eichung laeuft in jedem Lauf**, nicht nur bei einem Treffer. Wer sie nur
rechnet, wenn etwas anschlaegt, erfaehrt nie, ob die Latte ueberhaupt richtig
steht - genau die Luecke, aus der Befund 276 entstanden ist.

**Und die Korrektur an 276.** Dort stand, die Latte werde von "der Form der
Renditen selbst" gehoben. Das war zu schnell geschlossen. Gemessen ist es die
**Bauart** des Vorteilsscans: Teiler und Folgerendite stammen aus derselben
wandernden Reihe, und ein traeger Teiler schiebt sich beim Verschieben durch
die Phasen dieser Wanderung. Ein reiner Irrweg ohne jede Besonderheit reicht,
um die Latte zu ueberschreiten.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd

from research.tageszeit import (
    Fenster,
    Stabilitaet,
    Tagesreihe,
    normal_99,
    t_wert,
    urteil,
    vorzeichenprobe,
)
from research.vorteilsscan import paar, zweiteilung


def _reihe(werte: np.ndarray) -> Tagesreihe:
    return Tagesreihe(unterschied=np.asarray(werte, dtype=float), kerzen_im_fenster=4.0)


class TestDieTagesreiheIstDieEineQuelle:
    def test_messe_rechnet_nicht_selbst(self) -> None:
        """Sonst pruefte die Probe am Ende ein anderes Fenster als das
        Urteil - derselbe Grund wie bei ``paar`` im Vorteilsscan."""
        import inspect

        from research import tageszeit

        assert "tagesreihe(" in inspect.getsource(tageszeit.messe)
        assert "t_wert(" in inspect.getsource(tageszeit.messe)

    def test_der_t_wert_steht_an_einer_stelle(self) -> None:
        import inspect

        from research import tageszeit

        assert "t_wert(" in inspect.getsource(tageszeit.vorzeichenprobe)

    def test_die_autokorrelation_wird_gemessen(self) -> None:
        """Eine Reihe, in der jeder Tag zu 0,6 dem vorigen folgt."""
        rng = np.random.default_rng(277)
        stoss = rng.standard_normal(4000)
        werte = np.zeros(4000)
        for i in range(1, 4000):
            werte[i] = 0.6 * werte[i - 1] + stoss[i]

        assert abs(_reihe(werte).autokorrelation - 0.6) < 0.05

    def test_ohne_streuung_gibt_es_keine_abhaengigkeit(self) -> None:
        assert _reihe(np.zeros(50)).autokorrelation == 0.0


class TestDieVorzeichenprobe:
    def test_ein_echter_unterschied_haelt(self) -> None:
        rng = np.random.default_rng(277)
        werte = rng.standard_normal(300) * 0.5 + 1.0

        probe = vorzeichenprobe(_reihe(werte), zuege=2000)

        assert probe.haeufiger == 0
        assert probe.traegt(0.05 / 31)

    def test_reines_rauschen_haelt_nicht(self) -> None:
        rng = np.random.default_rng(9)
        probe = vorzeichenprobe(_reihe(rng.standard_normal(300)), zuege=2000)

        assert not probe.traegt(0.05 / 31)

    def test_dieselbe_saat_gibt_dasselbe_ergebnis(self) -> None:
        """Eine Probe, deren Ergebnis vom Tag abhaengt, ist keine."""
        rng = np.random.default_rng(3)
        reihe = _reihe(rng.standard_normal(400) * 0.3 + 0.05)

        erst = vorzeichenprobe(reihe, zuege=1000, saat=1)
        nochmal = vorzeichenprobe(reihe, zuege=1000, saat=1)
        andere = vorzeichenprobe(reihe, zuege=1000, saat=2)

        assert erst.haeufiger == nochmal.haeufiger
        assert erst.perzentil_99 == nochmal.perzentil_99
        assert andere.zuege == erst.zuege

    def test_mehr_zuege_machen_den_anteil_genauer(self) -> None:
        rng = np.random.default_rng(4)
        reihe = _reihe(rng.standard_normal(300))

        wenig = vorzeichenprobe(reihe, zuege=500)
        viel = vorzeichenprobe(reihe, zuege=8000)

        assert viel.streuung < wenig.streuung

    def test_ein_knappes_urteil_sagt_dass_es_knapp_ist(self) -> None:
        """Sonst sieht eine Entscheidung fest aus, die eine andere Saat
        gedreht haette - der Fall aus Befund 277 bei 5.000 Zuegen."""
        rng = np.random.default_rng(11)
        probe = vorzeichenprobe(_reihe(rng.standard_normal(300)), zuege=2000)

        # Eine Schranke einen Fehlerbalken entfernt ist knapp ...
        assert probe.knapp(probe.anteil + probe.streuung)
        assert "Knapp" in probe.beschreibe(probe.anteil + probe.streuung)
        # ... eine zehn Fehlerbalken entfernt nicht mehr.
        assert not probe.knapp(probe.anteil + 10 * probe.streuung)
        assert "Knapp" not in probe.beschreibe(
            probe.anteil + 10 * probe.streuung
        )

    def test_die_reihe_wird_in_stuecken_gewuerfelt(self) -> None:
        """20.000 mal 2350 Werte auf einmal waeren 376 MB. Der Test haelt
        fest, dass die Probe auch in dieser Groesse laeuft."""
        rng = np.random.default_rng(6)
        probe = vorzeichenprobe(_reihe(rng.standard_normal(2350)), zuege=20_000)

        assert probe.zuege == 20_000
        assert 0.0 <= probe.anteil <= 1.0


class TestDieEichungDerLatte:
    def test_bei_vielen_unabhaengigen_tagen_stimmt_die_normalverteilung(self) -> None:
        """Der Befund von 277: Im Tageszeit-Scan haelt die Latte."""
        rng = np.random.default_rng(277)
        probe = vorzeichenprobe(_reihe(rng.standard_normal(2350)), zuege=20_000)

        assert abs(probe.perzentil_99 - normal_99()) < 0.1

    def test_normal_99_ist_gerechnet_und_nicht_hingeschrieben(self) -> None:
        from statistics import NormalDist

        assert normal_99() == float(NormalDist().inv_cdf(0.995))
        assert abs(normal_99() - 2.5758) < 0.001


class TestWasDieLatteImVorteilsscanHebt:
    """Die Korrektur an Befund 276 - nachgebaut statt behauptet.

    Dort stand, es sei "die Form der Renditen selbst". Gemessen ist es die
    Bauart: Teiler und Folgerendite kommen aus **derselben** wandernden
    Reihe. Ein reiner Irrweg - keine dicken Raender, keine Regimewechsel,
    kein Trend - reicht schon.
    """

    LAENGE = 3000
    RUECKBLICK = 48
    HALTEN = 4

    def _null_verschoben(self, v: np.ndarray, t: np.ndarray) -> float:
        werte = [
            abs(z.t_wert)
            for k in range(1, len(t))
            if (
                z := zweiteilung(
                    v, np.roll(t, k), rueckblick=self.RUECKBLICK, halten=self.HALTEN
                )
            )
            is not None
        ]
        return float(np.percentile(werte, 99))

    def _null_gewuerfelt(self, v: np.ndarray, t: np.ndarray, saat: int = 277) -> float:
        rng = np.random.default_rng(saat)
        anteil = float(np.mean(t > 0))
        werte = [
            abs(z.t_wert)
            for _ in range(400)
            if (
                z := zweiteilung(
                    v,
                    np.where(rng.random(len(t)) < anteil, 1.0, -1.0),
                    rueckblick=self.RUECKBLICK,
                    halten=self.HALTEN,
                )
            )
            is not None
        ]
        return float(np.percentile(werte, 99))

    def _irrweg(self, saat: int, zyklus: float = 0.0) -> np.ndarray:
        rng = np.random.default_rng(saat)
        schritte = rng.normal(0, 0.04, self.LAENGE)
        if zyklus:
            schritte = schritte + zyklus * np.sin(np.arange(self.LAENGE) / 300.0)
        return np.cumsum(schritte)

    def test_ein_reiner_irrweg_hebt_die_latte_schon(self) -> None:
        v, t = paar(self._irrweg(277), self.RUECKBLICK, self.HALTEN)

        verschoben = self._null_verschoben(v, t)
        gewuerfelt = self._null_gewuerfelt(v, t)

        # Ein Teiler ohne Gedaechtnis liegt bei der Normalverteilung, der
        # traege deutlich darueber - auf **denselben** Renditen.
        assert gewuerfelt < normal_99() + 0.4
        assert verschoben > gewuerfelt

    def test_und_lange_zyklen_heben_sie_weiter(self) -> None:
        ohne = paar(self._irrweg(277), self.RUECKBLICK, self.HALTEN)
        mit = paar(self._irrweg(277, zyklus=0.01), self.RUECKBLICK, self.HALTEN)

        assert self._null_verschoben(*mit) > self._null_verschoben(*ohne)


class TestDasUrteilKenntDieProbe:
    def _fenster(self, t: float = 5.0, spanne: float = 0.2) -> Fenster:
        return Fenster(
            name="21 Uhr", von=21, bis=22, tage=2353, spanne_pct=spanne, t_wert=t
        )

    def _stabil(self) -> Stabilitaet:
        return Stabilitaet(erste=self._fenster(t=4.0), zweite=self._fenster(t=3.0))

    def test_ohne_probe_bleibt_es_bei_drei_huerden(self) -> None:
        text = urteil(self._fenster(), self._stabil(), geprueft=7)

        assert "Alle drei Huerden gehalten" in text

    def test_mit_probe_sind_es_vier(self) -> None:
        rng = np.random.default_rng(277)
        probe = vorzeichenprobe(
            _reihe(rng.standard_normal(300) * 0.5 + 1.0), zuege=2000
        )

        text = urteil(self._fenster(), self._stabil(), geprueft=7, probe=probe)

        assert "**Fund:" in text
        assert "Alle vier Huerden gehalten" in text

    def test_eine_probe_die_nicht_traegt_verhindert_den_fund(self) -> None:
        rng = np.random.default_rng(9)
        probe = vorzeichenprobe(_reihe(rng.standard_normal(300)), zuege=2000)

        text = urteil(self._fenster(), self._stabil(), geprueft=7, probe=probe)

        assert "Fund" not in text
        assert "Vorzeichenprobe" in text

    def test_unter_der_schwelle_bleibt_die_schwelle_der_grund(self) -> None:
        rng = np.random.default_rng(9)
        probe = vorzeichenprobe(_reihe(rng.standard_normal(300)), zuege=1000)

        text = urteil(self._fenster(t=1.0), self._stabil(), geprueft=31, probe=probe)

        assert "Nicht auffaellig genug" in text


class TestBeideBefehleEichenImmer:
    """Die Eichung darf nicht davon abhaengen, ob etwas anschlaegt."""

    def _quelle(self, name: str) -> str:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == name
        )
        return ast.unparse(knoten)

    def test_der_vorteilsscan_meldet_sie(self) -> None:
        assert "Eichung der Latte" in self._quelle("scan")

    def test_der_tageszeit_scan_auch(self) -> None:
        assert "Eichung der Latte" in self._quelle("tageszeit")

    def test_sie_steht_im_tageszeit_lauf(self, tmp_path, monkeypatch) -> None:
        """Auf einem Speicher, in dem nichts ueber die Schwelle kommt -
        gerade dann muss die Eichung dastehen."""
        from typer.testing import CliRunner

        from cli import app
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore

        rng = np.random.default_rng(277)
        tage = 300
        n = tage * 96
        kurs = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
        store = CandleStore(tmp_path)
        store.write_frame(
            "BTCUSD_BITSTAMP",
            Interval("15"),
            pd.DataFrame(
                {
                    "open_time": pd.date_range(
                        "2023-01-01", periods=n, freq="15min", tz="UTC"
                    ),
                    "open": kurs,
                    "high": kurs * 1.001,
                    "low": kurs * 0.999,
                    "close": kurs,
                    "volume": np.full(n, 5.0),
                    "turnover": kurs * 5.0,
                }
            ),
        )

        monkeypatch.setenv("PATHS__DATA_STORE", str(tmp_path))
        get_settings.cache_clear()
        try:
            ergebnis = CliRunner().invoke(
                app, ["tageszeit", "--maerkte", "BTCUSD_BITSTAMP"]
            )
        finally:
            get_settings.cache_clear()

        assert ergebnis.exit_code == 0, ergebnis.output
        assert "Eichung der Latte" in ergebnis.output
        assert "Normalverteilung" in ergebnis.output


def test_der_t_wert_stimmt_mit_der_handrechnung() -> None:
    """Eine Zahl, die man nachrechnen kann - sonst prueft nichts die Formel."""
    werte = np.array([1.0, 2.0, 3.0, 4.0])
    erwartet = np.mean(werte) / (np.std(werte, ddof=1) / 2.0)

    assert t_wert(werte) == erwartet
