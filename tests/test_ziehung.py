"""Tests fuer ``research.ziehung`` - Befund 113."""

from __future__ import annotations

import math

import pytest

from research.ziehung import Leiter, Nachpruefung, Sprosse, Ziehung


def zieh(saat: int, anteil: float, **kw) -> Ziehung:
    werte = dict(
        saat=saat, anteil=anteil, trades=100, sharpe_je_trade=0.25, dsr=0.8,
        bestanden=7, gesamt=11, cagr_pct=13.0,
    )
    werte.update(kw)
    return Ziehung(**werte)


def leiter_aus(daten: dict[float, dict[int, float]], groesse: str = "sharpe_je_trade") -> Leiter:
    """``{anteil: {saat: wert}}`` - alles andere bleibt gleich."""
    sprossen = []
    for anteil, je_saat in daten.items():
        s = Sprosse(anteil=anteil)
        for saat, wert in je_saat.items():
            s.ziehungen.append(zieh(saat, anteil, **{groesse: wert}))
        sprossen.append(s)
    return Leiter(sprossen=sprossen)


class TestSprosse:
    def test_eine_ziehung_hat_keine_streuung(self):
        s = Sprosse(anteil=0.1, ziehungen=[zieh(11, 0.1)])
        assert s.einzeln
        assert s.streuung("sharpe_je_trade") is None
        assert s.mittel("sharpe_je_trade") == pytest.approx(0.25)

    def test_zwei_ziehungen_haben_eine(self):
        s = Sprosse(
            anteil=0.1,
            ziehungen=[zieh(11, 0.1, sharpe_je_trade=0.20), zieh(23, 0.1, sharpe_je_trade=0.30)],
        )
        assert not s.einzeln
        assert s.mittel("sharpe_je_trade") == pytest.approx(0.25)
        assert s.streuung("sharpe_je_trade") == pytest.approx(0.0707, abs=1e-3)

    def test_spanne_nennt_beide_enden(self):
        s = Sprosse(
            anteil=0.1,
            ziehungen=[
                zieh(11, 0.1, sharpe_je_trade=0.20),
                zieh(23, 0.1, sharpe_je_trade=0.35),
                zieh(47, 0.1, sharpe_je_trade=0.28),
            ],
        )
        assert s.spanne("sharpe_je_trade") == (0.20, 0.35)

    def test_leere_sprosse_hat_kein_mittel(self):
        s = Sprosse(anteil=0.1)
        assert s.mittel("sharpe_je_trade") is None
        assert s.spanne("sharpe_je_trade") is None


class TestLeiter:
    def test_eine_ziehung_je_sprosse_wird_erkannt(self):
        """Genau die Lage von Befund 54."""
        lage = leiter_aus({0.0: {11: 0.2569}, 0.5: {11: 1.2734}})
        assert lage.aus_einer_ziehung

    def test_mehrere_ziehungen_sind_keine_einzelne(self):
        lage = leiter_aus({0.0: {11: 0.25, 23: 0.27}, 0.5: {11: 1.2, 23: 1.3}})
        assert not lage.aus_einer_ziehung

    def test_ohne_streuung_gibt_es_keinen_vergleich(self):
        """Das Kernversprechen: keine Zahl, wo keine moeglich ist."""
        lage = leiter_aus({0.0: {11: 0.2569}, 0.5: {11: 1.2734}})
        assert lage.vergleich(0.0, 0.5) is None

    def test_fehlende_sprosse_gibt_keinen_vergleich(self):
        lage = leiter_aus({0.0: {11: 0.25, 23: 0.27}})
        assert lage.vergleich(0.0, 0.5) is None

    def test_gemeinsame_saaten_sind_der_schnitt(self):
        lage = leiter_aus(
            {0.0: {11: 0.25, 23: 0.27, 47: 0.26}, 0.5: {11: 1.2, 23: 1.3}}
        )
        assert lage.saaten == (11, 23)

    def test_eine_gemeinsame_saat_genuegt_nicht(self):
        lage = leiter_aus({0.0: {11: 0.25, 23: 0.27}, 0.5: {11: 1.2, 47: 1.3}})
        assert lage.vergleich(0.0, 0.5) is None

    def test_gepaart_gerechnet_ueber_die_differenzen(self):
        """Ein gemeinsamer Zieheffekt hebt beide Sprossen und faellt heraus."""
        lage = leiter_aus(
            {
                0.0: {11: 0.20, 23: 0.30, 47: 0.40},
                0.5: {11: 0.30, 23: 0.40, 47: 0.50},
            }
        )
        u = lage.vergleich(0.0, 0.5)
        assert u is not None
        assert u.mittel == pytest.approx(0.10)
        # Jede Saat dieselbe Differenz - Streuung null, Unterschied eindeutig.
        assert u.streuung == pytest.approx(0.0, abs=1e-15)
        assert math.isinf(u.t)
        assert u.belegt()

    def test_fliesskommarest_wird_nicht_zu_evidenz(self):
        """**Die Falle, die dieser Test aufgedeckt hat.**

        0,30 - 0,20 und 0,40 - 0,30 sind in doppelter Genauigkeit nicht
        dieselbe Zahl. Die Streuung wurde 3,2e-17 statt null, und daraus
        ``t = 5,4e15`` - in jeder Tabelle die groesste Zahl, und reiner
        Rundungsrest. Aufgeloest wird deshalb an der Groessenordnung der
        Differenzen, nicht an der Null.
        """
        lage = leiter_aus(
            {
                0.0: {11: 0.20, 23: 0.30, 47: 0.40},
                0.5: {11: 0.30, 23: 0.40, 47: 0.50},
            }
        )
        u = lage.vergleich(0.0, 0.5)
        assert u.streuung > 0.0  # der Rest ist wirklich da
        assert math.isinf(u.t)  # und wird trotzdem nicht zu 5,4e15

    def test_ungepaart_waere_hier_nichts_zu_sehen(self):
        """Zur Gegenprobe: Die Sprossen ueberlappen sich vollstaendig.

        0,20-0,40 gegen 0,30-0,50 - wer die beiden Gruppen unabhaengig
        vergliche, faende bei dieser Streuung nichts. Gepaart ist es
        eindeutig, und deshalb wird gepaart gerechnet.
        """
        lage = leiter_aus(
            {
                0.0: {11: 0.20, 23: 0.30, 47: 0.40},
                0.5: {11: 0.30, 23: 0.40, 47: 0.50},
            }
        )
        a = lage.sprosse(0.0).werte("sharpe_je_trade")
        b = lage.sprosse(0.5).werte("sharpe_je_trade")
        assert min(b) < max(a)  # die Gruppen ueberlappen

    def test_reines_rauschen_ist_nicht_belegt(self):
        lage = leiter_aus(
            {
                0.0: {11: 0.25, 23: 0.30, 47: 0.20, 101: 0.28},
                0.5: {11: 0.30, 23: 0.22, 47: 0.27, 101: 0.21},
            }
        )
        u = lage.vergleich(0.0, 0.5)
        assert u is not None
        assert not u.belegt()

    def test_identische_sprossen_geben_t_null(self):
        lage = leiter_aus(
            {0.0: {11: 0.25, 23: 0.30}, 0.5: {11: 0.25, 23: 0.30}}
        )
        u = lage.vergleich(0.0, 0.5)
        assert u.mittel == pytest.approx(0.0)
        assert u.t == 0.0
        assert not u.belegt()

    def test_andere_groesse_laesst_sich_vergleichen(self):
        lage = leiter_aus(
            {0.0: {11: 150, 23: 160}, 0.2: {11: 30, 23: 32}}, groesse="trades"
        )
        u = lage.vergleich(0.0, 0.2, groesse="trades")
        assert u.mittel < 0
        assert u.groesse == "trades"


class TestUnterschied:
    def _u(self, t: float):
        lage = leiter_aus(
            {0.0: {11: 0.20, 23: 0.30, 47: 0.40}, 0.5: {11: 0.30, 23: 0.40, 47: 0.50}}
        )
        u = lage.vergleich(0.0, 0.5)
        return u

    def test_mehrere_hypothesen_heben_die_schranke(self):
        from research.rangprobe import schranke

        assert schranke(5) > schranke(1)

    def test_knapper_wert_faellt_bei_mehreren_hypothesen(self):
        """|t| = 2,12 traegt einen Vergleich, aber nicht zehn.

        Die Differenzen sind ausgerechnet und nicht geschaetzt: Beim ersten
        Anlauf standen hier Zahlen, die t = 3,41 ergaben - der Test haette
        dann etwas anderes geprueft, als sein Name sagt.
        """
        lage = leiter_aus(
            {
                0.0: {11: 0.0, 23: 0.0, 47: 0.0, 101: 0.0, 211: 0.0},
                0.5: {11: 0.07, 23: -0.01, 47: 0.09, 101: 0.0, 211: 0.06},
            }
        )
        u = lage.vergleich(0.0, 0.5)
        assert abs(u.t) == pytest.approx(2.116, abs=5e-3)
        assert u.belegt(1)
        assert not u.belegt(10)

    def test_text_nennt_schranke_und_urteil(self):
        text = self._u(0).als_text(hypothesen=5)
        assert "Streuung" in text
        assert "belegt" in text


class TestNachpruefung:
    def _unterschiede(self, werte: dict[float, dict[int, float]]):
        lage = leiter_aus(werte)
        aus = []
        for anteil in werte:
            if anteil == 0.0:
                continue
            u = lage.vergleich(0.0, anteil)
            if u is not None:
                aus.append(u)
        return tuple(aus)

    def test_ohne_vergleiche_kein_urteil(self):
        pruefung = Nachpruefung(aussage="x", befund=54, unterschiede=())
        assert not pruefung.haelt()
        assert "weder bestaetigt noch widerlegt" in pruefung.urteil()

    def test_ein_klarer_unterschied_traegt(self):
        unterschiede = self._unterschiede(
            {
                0.0: {11: 0.20, 23: 0.30, 47: 0.40},
                0.5: {11: 0.70, 23: 0.80, 47: 0.90},
            }
        )
        pruefung = Nachpruefung(aussage="x", befund=54, unterschiede=unterschiede)
        assert pruefung.haelt()
        assert "haelt" in pruefung.urteil()

    def test_rauschen_traegt_den_eigenen_massstab_nicht(self):
        unterschiede = self._unterschiede(
            {
                0.0: {11: 0.25, 23: 0.30, 47: 0.20, 101: 0.28},
                0.5: {11: 0.30, 23: 0.22, 47: 0.27, 101: 0.21},
            }
        )
        pruefung = Nachpruefung(aussage="x", befund=54, unterschiede=unterschiede)
        assert not pruefung.haelt()
        assert "stand auf einer Ziehung" in pruefung.urteil()

    def test_die_zahl_der_hypothesen_kommt_aus_den_vergleichen(self):
        unterschiede = self._unterschiede(
            {
                0.0: {11: 0.20, 23: 0.30},
                0.1: {11: 0.25, 23: 0.35},
                0.2: {11: 0.30, 23: 0.40},
                0.5: {11: 0.70, 23: 0.80},
            }
        )
        pruefung = Nachpruefung(aussage="x", befund=54, unterschiede=unterschiede)
        assert pruefung.hypothesen == 3
