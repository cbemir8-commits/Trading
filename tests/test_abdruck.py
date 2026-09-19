"""Woran ein Stueck zum anderen passt - Befund 300.

``zusammen`` prueft die Koepfe Feld fuer Feld. Diese Pruefung ist nur so gut
wie der Abdruck, der im Kopf steht: Was er nicht traegt, kann er nicht
vergleichen.

Diese Tests halten fest, was der Abdruck sieht - und, genauso wichtig, was er
**nicht** sehen darf: Zwischen zwei Stuecken wird committet, und ein Abdruck,
den ein abgelegtes Protokoll veraendert, macht die Stueckelung unbrauchbar.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cli import ABDRUCKBAEUME, _codeabdruck, _katalogabdruck, _kerzenabdruck


def _baum(wurzel: Path, inhalt: str = "x = 1\n") -> Path:
    for name in ("backtest", "strategy", "research"):
        (wurzel / name).mkdir(parents=True, exist_ok=True)
        (wurzel / name / "modul.py").write_text(inhalt, encoding="utf-8")
    (wurzel / "cli.py").write_text(inhalt, encoding="utf-8")
    return wurzel


class TestDerCodeabdruck:
    def test_derselbe_baum_gibt_denselben_abdruck(self, tmp_path: Path) -> None:
        _baum(tmp_path)
        assert _codeabdruck(tmp_path) == _codeabdruck(tmp_path)

    def test_eine_geaenderte_zeile_aendert_ihn(self, tmp_path: Path) -> None:
        """**Der Punkt der Uebung.** Wer waehrend einer Messreihe am
        rechnenden Code etwas aendert, bekommt beim Zusammenlegen eine
        Absage."""
        _baum(tmp_path)
        vorher = _codeabdruck(tmp_path)
        (tmp_path / "research" / "modul.py").write_text("x = 2\n", encoding="utf-8")
        assert _codeabdruck(tmp_path) != vorher

    def test_eine_neue_datei_aendert_ihn(self, tmp_path: Path) -> None:
        _baum(tmp_path)
        vorher = _codeabdruck(tmp_path)
        (tmp_path / "research" / "noch_eins.py").write_text("y = 1\n", encoding="utf-8")
        assert _codeabdruck(tmp_path) != vorher

    def test_ein_abgelegtes_protokoll_aendert_ihn_nicht(self, tmp_path: Path) -> None:
        """**Genauso wichtig wie das Gegenteil.** Zwischen zwei Stuecken
        wird committet - Protokolle, Befunde. Zaehlte das mit, waere kein
        Stueck je mit dem naechsten vereinbar, und die Stueckelung waere
        gebaut und unbenutzbar.

        Deshalb der Inhalt der rechnenden Baeume und **nicht** 'git HEAD'.
        """
        _baum(tmp_path)
        vorher = _codeabdruck(tmp_path)
        (tmp_path / "reports").mkdir()
        (tmp_path / "reports" / "lauf.jsonl").write_text("{}\n", encoding="utf-8")
        (tmp_path / "BEFUND.md").write_text("## Ein Befund\n", encoding="utf-8")
        assert _codeabdruck(tmp_path) == vorher

    def test_uebersetzte_dateien_zaehlen_nicht(self, tmp_path: Path) -> None:
        """``__pycache__`` fuellt sich beim Laufen selbst - zaehlte es mit,
        aenderte sich der Abdruck durch das Messen."""
        _baum(tmp_path)
        vorher = _codeabdruck(tmp_path)
        (tmp_path / "research" / "__pycache__").mkdir()
        (tmp_path / "research" / "__pycache__" / "modul.py").write_text(
            "egal\n", encoding="utf-8"
        )
        assert _codeabdruck(tmp_path) == vorher

    def test_ein_leerer_baum_wirft_nicht(self, tmp_path: Path) -> None:
        """Ein fehlender Ordner ist kein Grund, einen Lauf abzubrechen -
        aber er faellt dann eben auch nicht auf."""
        assert _codeabdruck(tmp_path)

    def test_die_baeume_stehen_an_einer_stelle(self) -> None:
        assert "cli.py" in ABDRUCKBAEUME
        assert "reports" not in ABDRUCKBAEUME
        assert "strategies" not in ABDRUCKBAEUME

    def test_das_echte_projekt_hat_einen_abdruck(self) -> None:
        abdruck = _codeabdruck()
        assert len(abdruck) == 16 and abdruck == _codeabdruck()


class TestDerKerzenabdruck:
    def _rahmen(self, n: int, start: str = "2020-01-01") -> pd.DataFrame:
        index = pd.date_range(start, periods=n, freq="D", tz="UTC")
        return pd.DataFrame({"close": range(n)}, index=index)

    def test_zeilen_und_raender(self) -> None:
        abdruck = _kerzenabdruck({"BTC": self._rahmen(10)})
        assert abdruck["BTC"]["zeilen"] == "10"
        assert "2020-01-01" in abdruck["BTC"]["von"]
        assert "2020-01-10" in abdruck["BTC"]["bis"]

    def test_eine_kerze_mehr_faellt_auf(self) -> None:
        assert _kerzenabdruck({"BTC": self._rahmen(10)}) != _kerzenabdruck(
            {"BTC": self._rahmen(11)}
        )

    def test_ein_anderer_anfang_faellt_auf(self) -> None:
        """Gleich viele Kerzen, andere Zeit - das waere sonst dieselbe
        Messung auf einem anderen Stueck Geschichte."""
        assert _kerzenabdruck({"BTC": self._rahmen(10)}) != _kerzenabdruck(
            {"BTC": self._rahmen(10, start="2021-01-01")}
        )

    def test_die_reihenfolge_der_maerkte_spielt_keine_rolle(self) -> None:
        a = {"BTC": self._rahmen(5), "ETH": self._rahmen(5)}
        b = {"ETH": self._rahmen(5), "BTC": self._rahmen(5)}
        assert _kerzenabdruck(a) == _kerzenabdruck(b)

    def test_ein_markt_mehr_faellt_auf(self) -> None:
        a = {"BTC": self._rahmen(5)}
        b = {"BTC": self._rahmen(5), "ETH": self._rahmen(5)}
        assert _kerzenabdruck(a) != _kerzenabdruck(b)


class TestDerKatalogabdruck:
    def test_er_ist_stabil(self) -> None:
        assert _katalogabdruck() == _katalogabdruck()

    def test_er_ist_kurz_genug_fuer_einen_kopf(self) -> None:
        assert len(_katalogabdruck()) == 16
