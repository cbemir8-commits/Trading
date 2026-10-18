"""Tests fuer ``research.betriebspunkt`` - Befund 112.

Die beiden gemessenen Punkte (BTC + ETH, Tageskerzen, 198 Versuche):

    Perpetual   152 Trades, 13,47 % p.a., 10,64 % Rueckgang, Guete 0,2597,
                DSR 0,7641, 7/11
    Spot        152 Trades, 14,83 % p.a.,  9,87 % Rueckgang, Guete 0,2765,
                DSR 0,8640, 9/11
"""

from __future__ import annotations

import pytest

from research.betriebspunkt import Betriebslage, Betriebspunkt


def perpetual(**kw) -> Betriebspunkt:
    werte = dict(
        name="Perpetual", trades=152, cagr_pct=13.47, rueckgang_pct=10.64,
        guete=0.2597, dsr=0.7641, bestanden=7, gesamt=11,
        offen=("Messlatte", "Schlechtestes Jahr", "Deflated Sharpe",
               "Parameter-Plateau"),
    )
    werte.update(kw)
    return Betriebspunkt(**werte)


def spot(**kw) -> Betriebspunkt:
    werte = dict(
        name="Spot", trades=152, cagr_pct=14.83, rueckgang_pct=9.87,
        guete=0.2765, dsr=0.8640, bestanden=9, gesamt=11,
        offen=("Messlatte", "Deflated Sharpe"),
    )
    werte.update(kw)
    return Betriebspunkt(**werte)


class TestBetriebspunkt:
    def test_keiner_von_beiden_ist_zugelassen(self):
        assert not perpetual().zugelassen
        assert not spot().zugelassen

    def test_spot_ist_der_bessere(self):
        assert spot().besser_als(perpetual())
        assert not perpetual().besser_als(spot())

    def test_bei_gleichen_gates_entscheidet_der_dsr(self):
        a = spot(bestanden=9, dsr=0.90)
        b = spot(name="Zwilling", bestanden=9, dsr=0.80)
        assert a.besser_als(b)
        assert not b.besser_als(a)

    def test_mehr_rendite_mit_weniger_gates_ist_nicht_besser(self):
        """Sonst waere 'besser' ein Wort fuer 'riskanter'."""
        wild = perpetual(name="Wild", cagr_pct=40.0, bestanden=4, dsr=0.99)
        assert not wild.besser_als(spot())
        assert spot().besser_als(wild)

    def test_zeile_markiert_die_offene_voraussetzung(self):
        assert "Voraussetzung offen" in spot().als_zeile()
        assert "Voraussetzung offen" not in spot(bestaetigt=True).als_zeile()


class TestBetriebslage:
    def test_ohne_punkte_gibt_es_nichts_zu_berichten(self):
        with pytest.raises(ValueError, match="beschreibt nichts"):
            Betriebslage(punkte=())

    def test_bei_offener_tatsache_gilt_der_schlechtere(self):
        """Der Kern der Regel: Unklarheit darf nur erschweren."""
        lage = Betriebslage(punkte=(perpetual(), spot()))
        assert lage.massgeblich.name == "Perpetual"
        assert lage.beste_moegliche.name == "Spot"
        assert lage.haengt_an_der_tatsache

    def test_reihenfolge_aendert_nichts(self):
        vorwaerts = Betriebslage(punkte=(perpetual(), spot()))
        rueckwaerts = Betriebslage(punkte=(spot(), perpetual()))
        assert vorwaerts.massgeblich.name == rueckwaerts.massgeblich.name
        assert vorwaerts.beste_moegliche.name == rueckwaerts.beste_moegliche.name

    def test_bestaetigter_besserer_punkt_wird_massgeblich(self):
        lage = Betriebslage(punkte=(perpetual(), spot(bestaetigt=True)))
        assert lage.massgeblich.name == "Spot"
        assert not lage.haengt_an_der_tatsache

    def test_bestaetigter_schlechterer_punkt_gilt_auch_dann(self):
        """Bestaetigt der Nutzer Perpetual, ist Spot kein Argument mehr."""
        lage = Betriebslage(punkte=(perpetual(bestaetigt=True), spot()))
        assert lage.massgeblich.name == "Perpetual"

    def test_unter_mehreren_bestaetigten_gilt_der_beste(self):
        lage = Betriebslage(
            punkte=(perpetual(bestaetigt=True), spot(bestaetigt=True))
        )
        assert lage.massgeblich.name == "Spot"

    def test_zwei_gates_haengen_an_der_tatsache(self):
        lage = Betriebslage(punkte=(perpetual(), spot()))
        assert lage.gates_dazwischen() == 2

    def test_ein_einziger_punkt_haengt_an_nichts(self):
        lage = Betriebslage(punkte=(spot(),))
        assert lage.massgeblich.name == "Spot"
        assert not lage.haengt_an_der_tatsache
        assert lage.gates_dazwischen() == 0

    def test_urteil_nennt_beide_staende_und_die_tatsache(self):
        text = Betriebslage(punkte=(perpetual(), spot())).urteil()
        assert "Perpetual" in text
        assert "Spot" in text
        assert "7/11" in text
        assert "9/11" in text
        assert "Bybit" in text

    def test_urteil_ohne_haenger_verspricht_nichts(self):
        text = Betriebslage(punkte=(spot(bestaetigt=True),)).urteil()
        assert "steht fest" in text

    def test_urteil_bei_offenem_einzelpunkt_nennt_die_regel(self):
        text = Betriebslage(punkte=(perpetual(),)).urteil()
        assert "unguenstigere" in text or "schlechtere" in text

    def test_offene_und_bestaetigte_werden_getrennt(self):
        lage = Betriebslage(punkte=(perpetual(bestaetigt=True), spot()))
        assert [p.name for p in lage.bestaetigte] == ["Perpetual"]
        assert [p.name for p in lage.offene] == ["Spot"]

    def test_der_bessere_punkt_allein_macht_keine_zulassung(self):
        """9 von 11 sind nicht 11 von 11 - auch nach der Klaerung."""
        lage = Betriebslage(punkte=(perpetual(), spot(bestaetigt=True)))
        assert not lage.massgeblich.zugelassen
        assert lage.massgeblich.offen == ("Messlatte", "Deflated Sharpe")


class TestBeideZeilenZaehlenDieselbeStichprobe:
    """**Befund 371.** Die Tabelle 'DIE BEIDEN BETRIEBSPUNKTE' vergleicht zwei
    Punkte - und zaehlte dabei anders als die Kopfzeile desselben Berichts.

    ``trades`` nahm die **ganze** Liste, der Kopf seit Befund 152 nur die
    fertigen: 158 gegen 157, ohne ein Wort dazu. Schwerer wog die Guete: Die
    Spot-Zeile rechnete sie auf allen Trades, die Perpetual-Zeile auf den
    fertigen. Gemessen am Spot-Punkt macht der eine zensierte Trade
    **+0,0087** aus (0,2868 gegen 0,2781) - ein Drittel dessen, was der ganze
    Terminkalender beitraegt, und in einer Tabelle, deren einziger Zweck der
    Vergleich dieser beiden Punkte ist.
    """

    @staticmethod
    def _punkt(**kwargs):
        from research.betriebspunkt import Betriebspunkt

        grund = {
            "name": "Spot", "trades": 157, "cagr_pct": 14.34,
            "rueckgang_pct": 9.87, "guete": 0.2781, "dsr": 0.5826,
            "bestanden": 9, "gesamt": 11,
        }
        return Betriebspunkt(**{**grund, **kwargs})

    def test_der_zensierte_trade_steht_daneben(self) -> None:
        zeile = self._punkt(zensiert=1).als_zeile()

        assert "157 Trades (+1 am Datenende)" in zeile

    def test_ohne_zensierte_keine_klammer(self) -> None:
        """Null heisst "keiner" - keine erfundene Angabe."""
        zeile = self._punkt(zensiert=0).als_zeile()

        assert "am Datenende" not in zeile
        assert "157 Trades," in zeile

    def test_die_zahl_ist_die_der_fertigen(self) -> None:
        """Nicht die Summe: 157 fertige und 1 zensierter sind nicht 158
        Beobachtungen, sondern 157 und ein Hinweis."""
        punkt = self._punkt(trades=157, zensiert=1)

        assert punkt.trades == 157

    def test_der_spotpunkt_rechnet_ohne_den_zensierten(self) -> None:
        """Die Stelle, an der die Guete entstand - geprueft am Quelltext, weil
        der Lauf dafuer echte Kerzen braucht."""
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.FunctionDef) and knoten.name == "_spotpunkt":
                quelle = ast.unparse(knoten)
                break
        else:
            raise AssertionError("'_spotpunkt' steht nicht mehr in cli.py")

        assert "ohne_zensierte(bericht)" in quelle
        assert "aus_trades(ohne_hebel.name, gehandelt.all_trades)" in quelle
        assert "aus_trades(ohne_hebel.name, bericht.all_trades)" not in quelle

    def test_und_zaehlt_die_fertigen(self) -> None:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "_spotpunkt"
        )
        quelle = ast.unparse(knoten)

        assert "trades=len(gehandelt.all_trades)" in quelle

    def test_rendite_und_rueckgang_behalten_ihn(self) -> None:
        """Der zensierte Trade ist keine abgeschlossene **Beobachtung** - sein
        Geld ist aber geflossen, und in Rendite und Rueckgang gehoert er hin
        (Befund 152)."""
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "_spotpunkt"
        )
        quelle = ast.unparse(knoten)

        assert "kombiniert = bericht.combined" in quelle
        assert "cagr_pct=float(kombiniert.cagr_pct)" in quelle


class TestDasRegisterHaeltDenFund371:
    def test_er_steht_unter_behoben(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 371)

        assert "0,0087" in eintrag.ergebnis
        assert "152" in eintrag.ergebnis
