"""Die Reibungsfrage ohne die Gates - Befund 301.

``vorratsdecke --reibungsleiter`` beantwortet dieselbe Frage und rechnet
dabei den ganzen Zulassungsweg mit: effektive Stichprobe, Latte, Decke. Die
Frage braucht davon nichts - sie steht auf Taktpunkten, und die kommen aus
dem Walk-Forward. Auf 15 Minuten sind die Gates zwei Drittel der Zeit
(Befund 298: 226 s je Genom, davon 61 s Walk-Forward).

Diese Tests halten drei Dinge fest: dass die Kosten so gerechnet werden, wie
sie gemessen sind, dass eine Sprosse ohne Streuung als nicht bestimmbar
gemeldet wird statt abzustuerzen, und dass das Lesen aus Stuecken dasselbe
ergibt wie ein Lauf am Stueck.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from cli import _reibung_aus_protokollen
from core.models import Interval
from research.kostenanteil import (
    Kostenfrage,
    Reibungsleiter,
    Reibungsprobe,
    Reibungssprosse,
    Taktpunkt,
)
from research.laufkosten import (
    MESSUNGEN,
    auskunft_ohne_gates,
    dauer,
    dauer_ohne_gates,
)
from research.zwischenstand import Zwischenstand


class TestWasDerLaufOhneGatesKostet:
    def test_jede_stufe_ist_ein_walk_forward(self) -> None:
        """**Der dritte Anlauf auf denselben Massstabsfehler.** 296 hat mit
        Kerzen hochgerechnet, 298 mit dem Genompreis. Hier kostet jede Stufe
        eine Sprosse - der Betriebspunkt eingeschlossen."""
        erwartet = MESSUNGEN["15m"].je_sprosse * 2 * 39
        assert dauer_ohne_gates("15m", 39, 2) == pytest.approx(erwartet)

    def test_es_ist_deutlich_billiger_als_der_katalogdurchlauf(self) -> None:
        """Die Begruendung dieses Befehls - mit der **gemessenen** Zahl.

        Befund 301 hat hier "123 s statt 287" behauptet, auf einem
        Walk-Forward-Preis von 61,4 s aus Befund 298. Gemessen sind 81 s
        (Befund 302), also 162 s statt 307: knapp die Haelfte gespart und
        nicht zwei Drittel. Der Befehl lohnt sich weiter, die Zahl war zu
        schoen.
        """
        mit_gates = dauer("15m", 39, 1)
        ohne = dauer_ohne_gates("15m", 39, 2)
        assert ohne < 0.6 * mit_gates
        assert ohne > 0.4 * mit_gates, "so billig war es nie"

    def test_eine_ungemessene_kerzenlaenge_bekommt_keine_zahl(self) -> None:
        assert dauer_ohne_gates("4h", 39, 2) is None
        assert "nicht gemessen" in auskunft_ohne_gates("4h", 39, 2)

    def test_die_auskunft_nennt_die_fundstelle(self) -> None:
        text = auskunft_ohne_gates("15m", 39, 2)
        assert "39 Genome mal 2 Stufen" in text
        assert f"Befund {MESSUNGEN['15m'].sprosse_gemessen_in}" in text
        assert "ohne Gates" in text

    def test_eine_stufe_heisst_stufe_und_nicht_stufen(self) -> None:
        assert "1 Stufe," in auskunft_ohne_gates("1d", 10, 1)


def _punkte(trades: tuple[int, ...], sharpes: tuple[float, ...]) -> list[Taktpunkt]:
    return [
        Taktpunkt(
            name=f"R{i}", trades=t, sharpe_je_trade=s,
            haltedauer_tage=1.0, kostenanteil=0.01,
        )
        for i, (t, s) in enumerate(zip(trades, sharpes, strict=True))
    ]


class TestOhneStreuungKeineKopplung:
    """**Ein Absturz, den erst die Stueckelung gezeigt hat.**

    ``genug`` zaehlt nur die Regeln. Stehen alle bei derselben Trade-Zahl -
    fuenf Abwandlungen derselben Vola-Ziel-Regel etwa -, ist die Korrelation
    nicht bestimmt, und ``r`` ist ``None``. ``urteil`` hat das formatiert und
    ist mit einem TypeError abgebrochen.

    Aufgefallen ist es nie, weil der einzige Aufrufer immer den ganzen Katalog
    gefahren hat. Das erste Stueck aus fuenf Verwandten hat gereicht.
    """

    def _leiter(self, trades: tuple[int, ...]) -> Reibungsleiter:
        return Reibungsleiter(
            sprossen=(
                Reibungssprosse(
                    faktor=0.0,
                    frage=Kostenfrage(punkte=_punkte(trades, (0.3, 0.2, 0.1, 0.0))),
                ),
                Reibungssprosse(
                    faktor=1.0,
                    frage=Kostenfrage(punkte=_punkte(trades, (0.2, 0.1, 0.0, -0.1))),
                ),
            )
        )

    def test_gleiche_trade_zahl_ist_nicht_belastbar(self) -> None:
        leiter = self._leiter((50, 50, 50, 50))
        assert all(s.frage.genug for s in leiter.sprossen)
        assert leiter.bei(1.0).r is None
        assert not leiter.belastbar

    def test_das_urteil_sagt_es_statt_abzustuerzen(self) -> None:
        text = self._leiter((50, 50, 50, 50)).urteil()
        assert "Keine Kopplung bestimmbar" in text
        assert "Streuung" in text

    def test_mit_streuung_urteilt_sie_wie_bisher(self) -> None:
        leiter = self._leiter((10, 50, 100, 200))
        assert leiter.belastbar
        assert "Keine Kopplung bestimmbar" not in leiter.urteil()

    def test_dieselbe_luecke_in_der_probe(self) -> None:
        """``Reibungsprobe`` hatte sie auch - zwei Stellen, ein Fehler."""
        probe = Reibungsprobe(
            mit=Kostenfrage(punkte=_punkte((50, 50, 50, 50), (0.2, 0.1, 0.0, -0.1))),
            ohne=Kostenfrage(punkte=_punkte((50, 50, 50, 50), (0.3, 0.2, 0.1, 0.0))),
        )
        assert not probe.belastbar
        assert "Keine Kopplung bestimmbar" in probe.urteil()

    def test_zu_wenige_punkte_sagen_weiter_zu_wenige_punkte(self) -> None:
        """Die neue Absage darf die alte nicht verdecken - drei Regeln sind
        etwas anderes als vier ohne Streuung."""
        probe = Reibungsprobe(
            mit=Kostenfrage(punkte=_punkte((10, 50, 100), (0.2, 0.1, 0.0))),
            ohne=Kostenfrage(punkte=_punkte((10, 50, 100), (0.3, 0.2, 0.1))),
        )
        assert "Zu wenige Punkte" in probe.urteil()


KOPF = {
    "maerkte": ["BTCUSD_BITSTAMP"],
    "intervall": "1d",
    "betriebspunkt": "Spot",
    "code": "abc123",
    "leiter": [0.0, 1.0],
}


def _takt(name: str, faktor: float, trades: int, sr: float) -> dict:
    return {
        "regel": name, "ergebnis": "takt", "faktor": faktor,
        "trades": trades, "sr_je_trade": sr,
        "haltedauer_tage": 4.0, "kostenanteil": 0.01,
    }


def _stueck(pfad: Path, *messungen: dict, **kopf: object) -> Path:
    stand = Zwischenstand(pfad=pfad, bedingungen={**KOPF, **kopf})
    stand.beginne()
    for messung in messungen:
        stand.halte_fest(**messung)
    return pfad


def _lies(*pfade: Path) -> dict[float, list]:
    eimer: dict[float, list] = {}
    _reibung_aus_protokollen(
        ",".join(str(p) for p in pfade),
        interval_obj=Interval("D"),
        punkte_je_faktor=eimer,
    )
    return eimer


class TestAusStueckenGelesen:
    def test_beide_stufen_kommen_an(self, tmp_path: Path) -> None:
        a = _stueck(
            tmp_path / "a.jsonl",
            _takt("Erste", 1.0, 100, 0.20),
            _takt("Erste", 0.0, 100, 0.25),
        )
        eimer = _lies(a)
        assert sorted(eimer) == [0.0, 1.0]
        assert [p.sharpe_je_trade for p in eimer[1.0]] == [0.20]
        assert [p.sharpe_je_trade for p in eimer[0.0]] == [0.25]

    def test_zwei_stuecke_werden_eins(self, tmp_path: Path) -> None:
        a = _stueck(
            tmp_path / "a.jsonl",
            _takt("Erste", 1.0, 100, 0.20), _takt("Erste", 0.0, 100, 0.25),
            stueck="1/2",
        )
        b = _stueck(
            tmp_path / "b.jsonl",
            _takt("Zweite", 1.0, 50, 0.30), _takt("Zweite", 0.0, 50, 0.35),
            stueck="2/2",
        )
        eimer = _lies(a, b)
        assert [p.name for p in eimer[1.0]] == ["Erste", "Zweite"]

    def test_eine_regel_ohne_takt_faellt_heraus(self, tmp_path: Path) -> None:
        a = _stueck(
            tmp_path / "a.jsonl",
            _takt("Erste", 1.0, 100, 0.20),
            {"regel": "Stumme", "ergebnis": "kein Takt", "faktor": 1.0, "trades": 0},
        )
        assert [p.name for p in _lies(a)[1.0]] == ["Erste"]

    def test_ein_doppelgaenger_faellt_auf_allen_stufen_heraus(
        self, tmp_path: Path
    ) -> None:
        """**Sonst traegen die Stufen verschiedene Regelmengen**, und die
        Leiter waere nicht mehr belastbar - genau die Falle, gegen die
        ``gleiche_regeln`` steht."""
        a = _stueck(
            tmp_path / "a.jsonl",
            _takt("Erste", 1.0, 100, 0.20), _takt("Erste", 0.0, 100, 0.25),
            stueck="1/2",
        )
        b = _stueck(
            tmp_path / "b.jsonl",
            _takt("Zwilling", 1.0, 100, 0.20), _takt("Zwilling", 0.0, 100, 0.99),
            stueck="2/2",
        )
        eimer = _lies(a, b)
        assert [p.name for p in eimer[1.0]] == ["Erste"]
        assert [p.name for p in eimer[0.0]] == ["Erste"]

    def test_entschieden_wird_am_betriebspunkt(self, tmp_path: Path) -> None:
        """Zwei Regeln, die sich nur **ohne** Reibung gleichen, sind zwei
        Regeln: Gemessen wird der Betriebspunkt, dort steht der Vorrat."""
        a = _stueck(
            tmp_path / "a.jsonl",
            _takt("Erste", 1.0, 100, 0.20), _takt("Erste", 0.0, 100, 0.25),
        )
        b = _stueck(
            tmp_path / "b.jsonl",
            _takt("Andere", 1.0, 100, 0.21), _takt("Andere", 0.0, 100, 0.25),
        )
        assert len(_lies(a, b)[1.0]) == 2

    def test_ueberschneidende_stuecke_werden_abgewiesen(self, tmp_path: Path) -> None:
        a = _stueck(tmp_path / "a.jsonl", _takt("Erste", 1.0, 100, 0.20))
        b = _stueck(tmp_path / "b.jsonl", _takt("Erste", 1.0, 100, 0.20))
        with pytest.raises(typer.Exit):
            _lies(a, b)

    def test_die_falsche_kerzenlaenge_wird_abgewiesen(self, tmp_path: Path) -> None:
        a = _stueck(tmp_path / "a.jsonl", _takt("Erste", 1.0, 100, 0.20),
                    intervall="15m")
        with pytest.raises(typer.Exit):
            _lies(a)

    def test_uneinige_stuecke_brechen_ab(self, tmp_path: Path) -> None:
        a = _stueck(tmp_path / "a.jsonl", _takt("Erste", 1.0, 100, 0.20))
        b = _stueck(tmp_path / "b.jsonl", _takt("Zweite", 1.0, 50, 0.30),
                    code="anders")
        with pytest.raises(typer.Exit):
            _lies(a, b)

    def test_eine_identisch_zeile_bringt_keinen_punkt(self, tmp_path: Path) -> None:
        """Der Lauf haelt einen Doppelgaenger als 'identisch' fest und
        spart sich dessen uebrige Stufen. Gelesen wird daraus nichts."""
        a = _stueck(
            tmp_path / "a.jsonl",
            _takt("Erste", 1.0, 100, 0.20),
            {"regel": "Zwilling", "ergebnis": "identisch", "faktor": 1.0,
             "trades": 100},
        )
        assert [p.name for p in _lies(a)[1.0]] == ["Erste"]
