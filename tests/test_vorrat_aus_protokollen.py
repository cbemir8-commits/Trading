"""Urteilen ueber Stuecke, als waeren sie ein Lauf - Befund 300.

``cli vorratsdecke --aus a.jsonl,b.jsonl`` rechnet nichts nach: Was in den
Protokollen steht, ist gemessen worden. Die Frage, die diese Tests stellen,
ist, ob dabei genau dasselbe herauskommt wie bei einem Lauf am Stueck - und
ob die Faelle, in denen es das nicht tut, **auffallen** statt durchzugehen.

Der Probelauf, der diesen Code ausgeloest hat: Sechs Stuecke des
Tageskatalogs ergaben 19 Regeln mit Latte, der Lauf am Stueck 18. Zwei Regeln
mit identischer Stichprobe und identischem Sharpe je Trade lagen in
verschiedenen Stuecken, und die Pruefung auf Doppelgaenger sieht innerhalb
eines Prozesses nur, was in diesem Prozess war.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from cli import _vorrat_aus_protokollen
from core.models import Interval
from research.zwischenstand import Zwischenstand

KOPF = {
    "maerkte": ["BTCUSD_BITSTAMP"],
    "intervall": "1d",
    "versuchsstand": 203,
    "betriebspunkt": "Spot",
    "code": "abc123",
    "reibungsleiter": [],
}

#: Zwei Regeln aus dem echten Tageskatalog - die **Namen** muessen es sein,
#: denn die Familien werden aus dem Katalog gelesen und nicht mitgeschrieben.
#:
#: Die **Zahlen** hier sind dagegen frei erfunden, und das mit Absicht: Die
#: Wache in 'test_referenz' schlaegt an, wenn eine Katalogzahl ein zweites Mal
#: irgendwo steht. Sie hat das hier getan, als die echten 0,3274 dienten - zu
#: Recht, denn zwei Fassungen derselben Zahl laufen frueher oder spaeter
#: auseinander (Befund 292). Fuer diese Tests taete jede Zahl es.
ERSTE = "Donchian-Ausbruch 55/20"
ZWEITE = "Grosser Trendausbruch"
DRITTE = "Trendfolge Ausbruch"


def _gemessen(name: str, n_eff: int = 58, sr: float = 0.2000) -> dict:
    return {
        "regel": name,
        "ergebnis": "gemessen",
        "trades": 60,
        "n_eff": n_eff,
        "sr_je_trade": sr,
        "guete": sr * n_eff**0.5,
        "schiefe": 0.7,
        "woelbung": 2.0,
        "haltedauer_tage": 12.0,
        "kostenanteil": 0.004,
    }


def _stueck(pfad: Path, *messungen: dict, **kopf: object) -> Path:
    stand = Zwischenstand(pfad=pfad, bedingungen={**KOPF, **kopf})
    stand.beginne()
    for messung in messungen:
        stand.halte_fest(**messung)
    return pfad


def _lies(*pfade: Path, versuche: int = 203):
    return _vorrat_aus_protokollen(
        ",".join(str(p) for p in pfade),
        interval_obj=Interval("D"),
        versuche=versuche,
    )


class TestWasGelesenWird:
    def test_zwei_stuecke_ergeben_einen_vorrat(self, tmp_path: Path) -> None:
        a = _stueck(tmp_path / "a.jsonl", _gemessen(ERSTE), stueck="1/2")
        b = _stueck(
            tmp_path / "b.jsonl", _gemessen(ZWEITE, 57, 0.1800), stueck="2/2"
        )

        vorrat = _lies(a, b)
        assert [p.name for p in vorrat.punkte] == [ERSTE, ZWEITE]
        assert vorrat.punkte[0].n_eff == 58
        assert vorrat.punkte[0].schiefe == 0.7

    def test_die_guete_wird_gerechnet_und_nicht_gelesen(self, tmp_path: Path) -> None:
        """``Punkt.guete`` ist SR mal Wurzel n. Sie steht zwar auch im
        Protokoll, aber aus zwei Quellen dieselbe Zahl zu fuehren ist genau
        das, was Befund 286 abgestellt hat."""
        a = _stueck(tmp_path / "a.jsonl", {**_gemessen(ERSTE), "guete": 999.0})
        vorrat = _lies(a)
        assert vorrat.punkte[0].guete == pytest.approx(0.2000 * 58**0.5)

    def test_stumme_regeln_werden_gezaehlt(self, tmp_path: Path) -> None:
        a = _stueck(
            tmp_path / "a.jsonl",
            _gemessen(ERSTE),
            {"regel": "Funding-Carry Long", "ergebnis": "kein Kandidat", "trades": 0},
        )
        vorrat = _lies(a)
        assert vorrat.stumm == 1
        assert len(vorrat.punkte) == 1

    def test_regeln_ohne_latte_stehen_getrennt(self, tmp_path: Path) -> None:
        a = _stueck(
            tmp_path / "a.jsonl",
            _gemessen(ERSTE),
            {"regel": ZWEITE, "ergebnis": "keine Latte", "n_eff": 4, "trades": 5},
        )
        vorrat = _lies(a)
        assert vorrat.ohne_latte == [(ZWEITE, 4)]
        assert len(vorrat.punkte) == 1

    def test_die_familien_kommen_aus_dem_katalog(self, tmp_path: Path) -> None:
        """Sie stehen im Genom und nicht im Protokoll - eine Quelle, nicht
        zwei."""
        a = _stueck(tmp_path / "a.jsonl", _gemessen(ERSTE))
        vorrat = _lies(a)
        assert sum(len(v) for v in vorrat.nach_familie.values()) == 1
        assert sum(len(v) for v in vorrat.grob_familie.values()) == 1

    def test_die_sprossen_der_reibungsleiter(self, tmp_path: Path) -> None:
        a = _stueck(
            tmp_path / "a.jsonl",
            _gemessen(ERSTE),
            {
                "regel": ERSTE, "ergebnis": "sprosse", "faktor": 0.0,
                "trades": 60, "sr_je_trade": 0.4, "kostenanteil": 0.0,
                "haltedauer_tage": 12.0,
            },
            reibungsleiter=[0.0],
        )
        vorrat = _lies(a)
        assert vorrat.faktoren == [0.0]
        assert [p.sharpe_je_trade for p in vorrat.leiter[0.0]] == [0.4]

    def test_eine_sprosse_ohne_trades_faellt_heraus(self, tmp_path: Path) -> None:
        """Ohne Trades gibt es keinen Taktpunkt - so wie im Lauf auch."""
        a = _stueck(
            tmp_path / "a.jsonl",
            _gemessen(ERSTE),
            {
                "regel": ERSTE, "ergebnis": "sprosse", "faktor": 0.0,
                "trades": 0, "sr_je_trade": None, "kostenanteil": None,
                "haltedauer_tage": None,
            },
            reibungsleiter=[0.0],
        )
        assert _lies(a).leiter[0.0] == []


class TestDoppelgaenger:
    def test_dieselbe_regel_unter_zwei_namen_zaehlt_einmal(
        self, tmp_path: Path
    ) -> None:
        """**Der Fund aus dem Probelauf.** Gleiche Stichprobe, gleicher
        Sharpe je Trade - das ist dieselbe Regel, und zwei Belege daraus zu
        machen hiesse, ihre Zahl zu erfinden.

        Der Lauf prueft das je Prozess und sieht ueber Stueckgrenzen hinweg
        nichts. Hier liegen alle Stuecke beieinander.
        """
        a = _stueck(tmp_path / "a.jsonl", _gemessen(ERSTE, 29, 0.1500), stueck="1/2")
        b = _stueck(tmp_path / "b.jsonl", _gemessen(ZWEITE, 29, 0.1500), stueck="2/2")

        vorrat = _lies(a, b)
        assert [p.name for p in vorrat.punkte] == [ERSTE]

    def test_ein_winziger_unterschied_sind_zwei_regeln(self, tmp_path: Path) -> None:
        """Die Kennung steht auf sechs Nachkommastellen, wie im Lauf."""
        a = _stueck(tmp_path / "a.jsonl", _gemessen(ERSTE, 29, 0.150000))
        b = _stueck(tmp_path / "b.jsonl", _gemessen(ZWEITE, 29, 0.150001))
        assert len(_lies(a, b).punkte) == 2

    def test_ueberschneidende_stuecke_werden_abgewiesen(self, tmp_path: Path) -> None:
        """Dieselbe Zeile zweimal ist kein Doppelgaenger, sondern ein
        Fehler beim Stueckeln - und der gehoert laut gemeldet."""
        a = _stueck(tmp_path / "a.jsonl", _gemessen(ERSTE), stueck="1/2")
        b = _stueck(tmp_path / "b.jsonl", _gemessen(ERSTE), stueck="2/2")
        with pytest.raises(typer.Exit):
            _lies(a, b)


class TestWorueberGeurteiltWird:
    def test_die_falsche_kerzenlaenge_wird_abgewiesen(self, tmp_path: Path) -> None:
        """Ein Vorrat gehoert an seine eigene Kerzenlaenge (Befund 190)."""
        a = _stueck(tmp_path / "a.jsonl", _gemessen(ERSTE), intervall="15m")
        with pytest.raises(typer.Exit):
            _lies(a)

    def test_geurteilt_wird_auf_dem_stand_des_protokolls(
        self, tmp_path: Path
    ) -> None:
        """Schon im Lauf entschied der Zaehler, welche Regel eine Latte
        bekommt. Ein anderer Zaehler hier liesse Ausschluesse und Urteile
        auseinanderlaufen."""
        a = _stueck(tmp_path / "a.jsonl", _gemessen(ERSTE))
        vorrat = _lies(a, versuche=250)
        assert vorrat.versuchsstand == 203

    def test_die_quelle_nennt_alle_stuecke(self, tmp_path: Path) -> None:
        a = _stueck(tmp_path / "a.jsonl", _gemessen(ERSTE), stueck="1/2")
        b = _stueck(tmp_path / "b.jsonl", _gemessen(ZWEITE, 57), stueck="2/2")
        quelle = _lies(a, b).quelle
        assert str(a) in quelle and str(b) in quelle

    def test_uneinige_stuecke_brechen_ab(self, tmp_path: Path) -> None:
        a = _stueck(tmp_path / "a.jsonl", _gemessen(ERSTE))
        b = _stueck(tmp_path / "b.jsonl", _gemessen(DRITTE, 130), code="anders")
        with pytest.raises(typer.Exit):
            _lies(a, b)
