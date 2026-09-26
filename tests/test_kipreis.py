"""Was die Research-KI kostet, gerechnet - Befund 342.

Siebter Verdachtsfall aus der Wache von Befund 335: **'Soll die Research-KI
mitlaufen'**, Fundstelle Befund 74, massgeblich 292 - und der offene Punkt, den
der Auftrag jedes Mal nennt.

Das ``warum`` des Eintrags sagt: *"Dagegen steht der Preis, und er ist keine
Kleinigkeit: Jeder Vorschlag zaehlt als Versuch und hebt die Huerde des
Deflated Sharpe fuer alle folgenden."* Beziffert war das nicht - obwohl
``Erreichbarkeit.kosten`` seit Befund 327 genau dafuer im Haus ist.

Gerechnet vom Spot-Punkt aus, gegen eine Luecke von 0,3673:

    Vorschlaege   Kosten   Anteil Luecke   noetige Trades
              0   0,0000            0,0%              190
              1   0,0011            0,3%              191
              9   0,0095            2,6%              192
             20   0,0207            5,6%              194
             50   0,0484           13,2%              198
            100   0,0878           23,9%              204

**Dieselbe Ueberzeichnung wie in Befund 326, nur in der anderen Richtung.** Dort
war eine Ersparnis als Fortschritt gebucht (1,5 % der Luecke), hier ein Preis
als Abschreckung. Beide ohne Rechnung.

Und die vier 'noetig'-Zahlen des Eintrags (0,9047 / 0,2652 / 0,2967 / 0,1514)
sind **nicht nachrechenbar**: Die Latte haengt an Trade-Zahl und
Verteilungsform, und die Form steht je Regel nirgends. Mit der Form des
Bestands und heutigem Zaehler waeren es 1,4554 / 0,3387 / 0,3725 / 0,1936.
"""

from __future__ import annotations

import pytest

from research.erreichbarkeit import bewerte, noetiger_sharpe
from research.referenz import SPOTPUNKT
from research.versuche import Versuch, Verzeichnis

ZIEL = 0.95

#: Vorschlaege -> (Kosten in DSR-Punkten, noetige Trades danach).
GEMESSEN: tuple[tuple[int, float, int], ...] = (
    (0, 0.0000, 190),
    (1, 0.0011, 191),
    (4, 0.0043, 191),
    (9, 0.0095, 192),
    (20, 0.0207, 194),
    (50, 0.0484, 198),
    (100, 0.0878, 204),
)

#: Die vier Vorschlaege aus Befund 77: Trades, Guete, Latte im Eintrag,
#: Latte mit der Form des Bestands bei 203 Versuchen.
VIER: tuple[tuple[str, int, float, float, float], ...] = (
    ("Enge vor Bewegung", 18, 0.3405, 0.9047, 1.4554),
    ("Volumenschock mit Fortsetzung", 114, 0.1584, 0.2652, 0.3387),
    ("Rueckkehr zum Volumenschwerpunkt", 92, -0.1201, 0.2967, 0.3725),
    ("Abgriff des Vortagestiefs", 406, -0.1201, 0.1514, 0.1936),
)


def _lage(trials: int = 203):
    return bewerte(
        trades=SPOTPUNKT.effektiv,
        sharpe=SPOTPUNKT.guete,
        trials=trials,
        skew=SPOTPUNKT.schiefe,
        kurtosis=SPOTPUNKT.woelbung,
        ziel=ZIEL,
    )


class TestDerPreisIstGerechnet:
    """**Der Fund.** "Keine Kleinigkeit" war ungerechnet."""

    @pytest.mark.parametrize(("k", "kosten", "trades"), GEMESSEN)
    def test_jede_stufe_stimmt(self, k: int, kosten: float, trades: int) -> None:
        heute = _lage()

        assert heute.kosten(k) == pytest.approx(kosten, abs=0.0002)
        assert _lage(203 + k).trades_noetig == trades

    def test_eine_handvoll_kostet_wenige_prozent(self) -> None:
        heute = _lage()
        luecke = ZIEL - heute.dsr

        assert luecke == pytest.approx(0.3673, abs=0.0005)
        assert heute.kosten(9) / luecke == pytest.approx(0.026, abs=0.002)

    def test_eine_serie_kostet_schon_etwas(self) -> None:
        """Die Gegenprobe, damit der Befund nicht als "der Preis ist null"
        gelesen wird: Bei fuenfzig sind es 13 %, bei hundert 24 %."""
        heute = _lage()
        luecke = ZIEL - heute.dsr

        assert heute.kosten(50) / luecke == pytest.approx(0.132, abs=0.003)
        assert heute.kosten(100) / luecke == pytest.approx(0.239, abs=0.003)

    def test_der_zaehler_faellt_nicht(self) -> None:
        """Befund 327: Eine Ersparnis ist ein vermiedener Verlust."""
        with pytest.raises(ValueError, match="faellt nicht"):
            _lage().kosten(-5)


class TestDieVierLattenSindNichtNachrechenbar:
    """Die Latte haengt an Trade-Zahl **und** Form - und die Form fehlt."""

    @pytest.mark.parametrize(
        ("name", "trades", "guete", "damals", "heute"), VIER, ids=lambda x: str(x)[:20]
    )
    def test_mit_der_form_des_bestands_liegt_sie_hoeher(
        self, name: str, trades: int, guete: float, damals: float, heute: float
    ) -> None:
        gerechnet = noetiger_sharpe(
            effektiv=trades,
            trials=203,
            skew=SPOTPUNKT.schiefe,
            kurtosis=SPOTPUNKT.woelbung,
            ziel=ZIEL,
        )

        assert gerechnet == pytest.approx(heute, abs=0.0005), name
        assert gerechnet > damals, name

    def test_keine_der_beiden_formen_holt_die_alten_zahlen_zurueck(self) -> None:
        """Der Grund, warum es "nicht nachrechenbar" heisst und nicht
        "falsch": Weder die Normalform noch die des Bestands trifft die vier,
        bei keinem Zaehlerstand von 5 bis 203."""
        for skew, kurtosis in ((0.0, 3.0), (SPOTPUNKT.schiefe, SPOTPUNKT.woelbung)):
            for trials in (5, 10, 20, 50, 100, 203):
                gerechnet = [
                    noetiger_sharpe(
                        effektiv=t, trials=trials, skew=skew, kurtosis=kurtosis,
                        ziel=ZIEL,
                    )
                    for _, t, _, _, _ in VIER
                ]
                alle_treffen = all(
                    g is not None and abs(g - damals) < 0.002
                    for g, (_, _, _, damals, _) in zip(gerechnet, VIER, strict=True)
                )

                assert not alle_treffen, (
                    f"Form ({skew}, {kurtosis}) bei {trials} Versuchen trifft "
                    f"alle vier - dann waeren sie doch nachrechenbar"
                )


class TestDasVerzeichnisTraegtJetztDieForm:
    """Was fehlt, ist keine Messung, sondern ein Feld - dieselbe Bauart wie
    der Sharpe je Trade in Befund 68/340."""

    def test_beide_groessen_oder_keine(self) -> None:
        """Eine halb gemessene Form ist eine geratene."""
        assert not Versuch("A").form_bekannt
        assert not Versuch("A", schiefe=3.4).form_bekannt
        assert not Versuch("A", woelbung=15.9).form_bekannt
        assert Versuch("A", schiefe=3.4, woelbung=15.9).form_bekannt

    def test_das_verzeichnis_zaehlt_sie(self) -> None:
        verzeichnis = Verzeichnis(
            grundstock=192,
            eintraege=[
                Versuch("A", sharpe_je_trade=0.2),
                Versuch("B", sharpe_je_trade=0.3, schiefe=1.0, woelbung=4.0),
            ],
        )

        assert verzeichnis.mit_form == 1
        assert verzeichnis.belegt == 2

    def test_die_form_geht_durch_speichern_und_laden(self, tmp_path) -> None:
        from research.versuche import laden, speichern

        datei = tmp_path / "trials.json"
        speichern(
            datei,
            Verzeichnis(
                grundstock=192,
                eintraege=[
                    Versuch(
                        "A", trades=42, sharpe_je_trade=0.3,
                        schiefe=3.4646, woelbung=15.9173,
                    )
                ],
            ),
        )
        zurueck = laden(datei)

        assert zurueck.eintraege[0].schiefe == pytest.approx(3.4646)
        assert zurueck.eintraege[0].woelbung == pytest.approx(15.9173)
        assert zurueck.mit_form == 1

    def test_alte_dateien_ohne_form_bleiben_lesbar(self, tmp_path) -> None:
        """``None`` heisst "nicht erhoben". Ein Standardwert waere hier eine
        erfundene Form."""
        import json

        from research.versuche import laden

        datei = tmp_path / "trials.json"
        datei.write_text(
            json.dumps(
                {
                    "format": 2,
                    "trials": 193,
                    "grundstock": 192,
                    "versuche": [{"kennung": "A", "trades": 5}],
                }
            )
        )
        zurueck = laden(datei)

        assert zurueck.anzahl == 193
        assert zurueck.mit_form == 0
        assert not zurueck.eintraege[0].form_bekannt

    def test_die_elf_vorhandenen_tragen_noch_keine(self) -> None:
        """Der Stand auf der Platte, und er ist kein Versehen: Die Form wird
        von jetzt an mitgeschrieben, nicht nachtraeglich erfunden."""
        from pathlib import Path

        from core.config import get_settings
        from research.versuche import laden

        verzeichnis = laden(Path(get_settings().paths.state) / "trials.json")

        assert len(verzeichnis.eintraege) == 11
        assert verzeichnis.mit_form == 0


class TestDieBefehleFuellenEs:
    """Befund 152, 154, 155, 160, 325, 330, 337, 338 und 339 waren dieselbe
    Bauart: gebaut, gerechnet, nicht angeschlossen."""

    @staticmethod
    def _quelle(name: str) -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == name
        )

    def test_der_gemeinsame_weg_traegt_sie(self) -> None:
        quelle = self._quelle("_versuch")

        assert "schiefe=kandidat.schiefe if kandidat is not None else None" in quelle
        assert "woelbung=kandidat.woelbung if kandidat is not None else None" in quelle

    def test_machbarkeit_nimmt_sie_aus_den_kennzahlen(self) -> None:
        quelle = self._quelle("machbarkeit")

        assert "schiefe=p.kennzahlen.get('schiefe')" in quelle
        assert "woelbung=p.kennzahlen.get('woelbung')" in quelle

    def test_verbund_nimmt_sie_vom_kandidaten(self) -> None:
        quelle = self._quelle("verbund")

        assert "schiefe=kandidat.schiefe if kandidat is not None else None" in quelle


class TestDerEintragIstNachgemessen:
    @staticmethod
    def _eintrag():
        from research.stand import ENTSCHEIDUNGEN

        return next(
            e for e in ENTSCHEIDUNGEN if e.frage == "Soll die Research-KI mitlaufen"
        )

    def test_der_preis_steht_jetzt_als_zahl_da(self) -> None:
        warum = self._eintrag().warum

        assert "war ungerechnet" in warum
        assert "0,0095" in warum and "2,6 %" in warum

    def test_und_wo_er_teuer_wird(self) -> None:
        """Nicht "der Preis ist klein", sondern ab wann er zaehlt."""
        warum = self._eintrag().warum

        assert "13,2 %" in warum
        assert "23,9 %" in warum

    def test_die_waehrung_der_noetigen_trades_steht_dabei(self) -> None:
        warum = self._eintrag().warum

        assert "190" in warum and "192" in warum and "194" in warum

    def test_die_ueberzeichnung_ist_benannt(self) -> None:
        """Dieselbe Bauart wie 326/327, nur in der anderen Richtung - und das
        gehoert gesagt, nicht verschwiegen."""
        warum = self._eintrag().warum

        assert "Befund\n              326" in warum or "Befund 326" in warum
        assert "beide ohne Rechnung" in warum

    def test_der_einwand_bleibt_stehen(self) -> None:
        """Der Befund entkraeftet ein Argument, nicht die Entscheidung."""
        warum = self._eintrag().warum

        assert "Modellkosten und den neun Nieten" in warum

    def test_die_vier_latten_sind_als_unnachrechenbar_benannt(self) -> None:
        zahl = self._eintrag().zahl

        assert "nicht nachrechenbar" in zahl
        assert "1,4554" in zahl
        assert "Schiefe und Woelbung mit" in zahl

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 74
        assert eintrag.massgeblich == 342
