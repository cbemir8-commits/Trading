"""Der letzte Schritt vor dem Geld war fuer Carry-Regeln blind - Befund 360.

``cli abgleich`` legt Backtest und Livebetrieb nebeneinander und ist laut
Register *"vor jedem Livegang auszufuehren"*. Gefahren, mit der Carry-Regel aus
Generation 5:

    Einig ueber 5355 Balken - 0 Signale, identisch.

**Gruen, und ohne Aussage.** Die Kette dahinter, jedes Glied gemessen:

1. Der Wettbewerb haengt die Funding-Raten an die Kerzen - jede Zulassungszahl
   entsteht mit ihnen (``schedule_from_frame`` und ``attach_funding``).
2. ``execution/`` erwaehnt Funding an **keiner** Stelle. Der Livepuffer kommt
   aus ``candles_to_frame``, also den sieben Spalten aus ``store.SCHEMA``.
   ``strategy.indicators._funding_column`` gibt ohne Spalte NaN zurueck, und
   die Regel handelt dann nicht.
3. ``cli abgleich`` hing die Raten ebenfalls nicht an - also fehlten sie
   **beiden** Seiten, beide taten nichts, und das las sich als Einigkeit.

Ein Carry-Champion haette damit die Zulassung bestanden, den Abgleich bestanden
und live **nie** gehandelt.

Was daran geaendert ist
-----------------------
Die Backtest-Seite bekommt die Raten (wie im Wettbewerb), die Live-Seite
bekommt die Spalten, die der Puffer wirklich hat (``_wie_der_puffer``). Damit
faellt der Unterschied auf, gemessen:

    vorher:  Einig ueber 5355 Balken - 0 Signale, identisch.
    nachher: 200 Abweichungen ueber 5355 Balken.
             Backtest 5325 Signale, Betrieb 0.

Und "einig bei null Signalen" ist kein Urteil mehr, sondern eine benannte
Leerstelle. Der Gedanke stand schon in ``test_replay.py`` - *"Ohne Signale
prueft der Vergleich nichts"* -, aber nur als Zusicherung in einem einzigen
Test. Jetzt sagt der Bericht es selbst.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from backtest.replay import _wie_der_puffer, vergleiche
from data.funding import FundingRate, attach_funding, funding_to_frame
from strategy.compiler import compile_genome
from tests.test_replay import kerzen

#: Eine Rate **unter** der Schwelle der Carry-Regel (0,01 %).
#:
#: Auf der Schwelle handelt auch die Backtest-Seite nicht, und dann sehen beide
#: Seiten gleich aus - der Fehler, der in Befund 359 einen Anlauf gekostet hat.
RATE = Decimal("0.00005")


def _mit_funding(n: int = 500):
    """Kerzen mit einer durchgehenden Funding-Spalte."""
    frame = kerzen(n)
    beginn = frame["open_time"].iloc[0] - timedelta(days=1)
    raten = funding_to_frame(
        [
            FundingRate(
                symbol="BTCUSDT",
                funding_time=beginn + timedelta(hours=8 * i),
                funding_rate=RATE,
            )
            for i in range(n * 3 + 9)
        ]
    )
    return attach_funding(frame, raten)


def _carry_regel():
    from research.seeds import GENERATIONS

    for eintrag in GENERATIONS[5]:
        genome = eintrag() if callable(eintrag) else eintrag
        if "arry" in genome.name:
            return genome
    pytest.skip("keine Carry-Regel in Generation 5")


class TestDieLiveSeiteBekommtNurDenEchtenPuffer:
    def test_fremde_spalten_fallen_weg(self) -> None:
        frame = _mit_funding(60)

        gekuerzt = _wie_der_puffer(frame)

        assert "funding_rate" in frame.columns
        assert "funding_rate" not in gekuerzt.columns

    def test_die_sieben_echten_bleiben(self) -> None:
        from data.store import SCHEMA

        gekuerzt = _wie_der_puffer(_mit_funding(60))

        assert list(gekuerzt.columns) == [s for s in SCHEMA if s in gekuerzt.columns]
        assert len(gekuerzt.columns) == 7

    def test_ohne_fremde_spalte_bleibt_der_rahmen_derselbe(self) -> None:
        """Kein Kopieren, wo nichts zu kuerzen ist - der Vergleich rechnet je
        Balken neu und ist ohnehin langsam."""
        frame = kerzen(60)

        assert _wie_der_puffer(frame) is frame

    def test_die_liste_kommt_aus_dem_schema(self) -> None:
        """**Nicht hier aufgeschrieben** (Befund 360): Bekommt der Livepuffer
        eine Spalte dazu, folgt dieser Vergleich von selbst."""
        import inspect

        quelle = inspect.getsource(_wie_der_puffer)

        assert "SCHEMA" in quelle


class TestDerUnterschiedFaelltJetztAuf:
    """**Der Fund**, und die Gegenprobe dazu."""

    def test_die_carry_regel_handelt_nur_im_backtest(self) -> None:
        ergebnis = vergleiche(
            _mit_funding(500), lambda: compile_genome(_carry_regel()),
            buffer_bars=200,
        )

        assert not ergebnis.einig, "der Unterschied muss auffallen"
        assert ergebnis.signale_backtest > 0
        assert ergebnis.signale_livebetrieb == 0

    def test_der_bericht_nennt_beide_zahlen(self) -> None:
        ergebnis = vergleiche(
            _mit_funding(500), lambda: compile_genome(_carry_regel()),
            buffer_bars=200,
        )
        text = ergebnis.bericht()

        assert "Abweichungen" in text
        assert "Betrieb 0" in text

    def test_eine_regel_ohne_funding_bleibt_einig(self) -> None:
        """Die Gegenprobe: Gekuerzt wird eine Spalte, die der Betrieb nicht
        hat - wer sie nicht liest, merkt davon nichts."""
        from tests.test_replay import einfaches_genom

        ergebnis = vergleiche(
            _mit_funding(600), lambda: compile_genome(einfaches_genom()),
            buffer_bars=200,
        )

        assert ergebnis.einig, ergebnis.bericht()
        assert ergebnis.signale_backtest > 5


class TestEinigBeiNullSignalenIstKeinUrteil:
    def test_ohne_funding_sagt_der_bericht_es_deutlich(self) -> None:
        ergebnis = vergleiche(
            kerzen(500), lambda: compile_genome(_carry_regel()), buffer_bars=200
        )

        assert ergebnis.einig, "ohne Eingabe tun beide Seiten nichts"
        assert ergebnis.nichts_zu_vergleichen
        assert "Nichts zu vergleichen" in ergebnis.bericht()

    def test_und_nennt_die_haeufigste_ursache(self) -> None:
        """Eine Leerstelle ohne Hinweis schickt den Leser auf die Suche."""
        ergebnis = vergleiche(
            kerzen(500), lambda: compile_genome(_carry_regel()), buffer_bars=200
        )

        assert "Funding" in ergebnis.bericht()

    def test_mit_signalen_bleibt_es_beim_alten_satz(self) -> None:
        from tests.test_replay import einfaches_genom

        ergebnis = vergleiche(
            kerzen(600), lambda: compile_genome(einfaches_genom()), buffer_bars=200
        )

        assert not ergebnis.nichts_zu_vergleichen
        assert "Einig ueber" in ergebnis.bericht()

    def test_der_gedanke_stand_schon_in_einem_test(self) -> None:
        """Er stand als Zusicherung in **einem** Test von zwanzig; jetzt steht
        er im Bericht. Der Satz dort bleibt richtig und bleibt stehen."""
        quelle = Path("tests/test_replay.py").read_text(encoding="utf-8")

        assert "Ohne Signale prueft der Vergleich nichts" in quelle


class TestDerBefehlHaengtDieRatenAn:
    @staticmethod
    def _quelle() -> str:
        import ast

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.FunctionDef) and knoten.name == "abgleich":
                return ast.unparse(knoten)
        raise AssertionError("'abgleich' steht nicht mehr in cli.py")

    def test_attach_funding_wird_gerufen(self) -> None:
        quelle = self._quelle()

        assert "attach_funding(frame" in quelle

    def test_mit_den_raten_des_kontrakts(self) -> None:
        """Nicht mit denen des Kursdatensymbols - der Fehler aus Befund 265."""
        quelle = self._quelle()

        assert "_bybit_kontrakt(symbol)" in quelle

    def test_und_der_kopf_nennt_die_zahl(self) -> None:
        """Eine stille Ladung ist von einer leeren nicht zu unterscheiden
        (Befund 265)."""
        quelle = self._quelle()

        assert "Raten fuer" in quelle


class TestDasRegisterHaeltDenFund:
    def test_er_steht_unter_behoben(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 360)

        assert "0 Signale" in eintrag.ergebnis
        assert "5325" in eintrag.ergebnis

    def test_die_offene_folge_ist_benannt(self) -> None:
        """Der Abgleich sieht es jetzt - **behoben ist der Livebetrieb damit
        nicht.** Er hat weiter keine Funding-Spalte, und das gehoert als offene
        Folge ins Register und nicht in eine Fussnote.
        """
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 360)

        assert "Livebetrieb" in eintrag.ergebnis
        assert "offen" in eintrag.ergebnis.lower()
