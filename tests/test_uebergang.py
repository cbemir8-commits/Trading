"""Traegt die Strecke, wenn der Nutzer Boersendaten liefert? - Befund 115.

Befund 114 hat festgehalten, dass der naechste wirksame Schritt ``cli
backfill`` ist und beim Nutzer liegt. Was **danach** kommt, war nie geprueft:
Jede Zahl dieses Projekts steht auf Bitstamp-Kerzen, und ob der Uebergang auf
Bybit-Namen wirklich traegt, stand nirgends.

Geprueft wird die Maschinerie, nicht eine Strategie.

**Was hier absichtlich fehlt:** Ob ``GateReport.passed`` bei
``referenzdaten=False`` wirklich True werden kann. Das steht seit Befund 102
in ``tests/test_referenzdaten.py`` (``test_boersendaten_lassen_zu``,
``test_der_echte_lauf_erkennt_es_von_selbst``) und braucht keine zweite
Fassung. Hier steht nur, was dort nicht steht: die Aufloesung der Symbole und
die Kontraktdaten dahinter.
"""

from __future__ import annotations

import pytest

from data.reference import PAIRS, ist_referenz


class TestDieSperreHaengtAmNamen:
    def test_bitstamp_symbole_sind_forschungsmaterial(self):
        for name in PAIRS:
            assert ist_referenz(name)

    def test_bybit_kontrakte_sind_es_nicht(self):
        """Die Bedingung, unter der die Sperre faellt."""
        for name in ("BTCUSDT", "ETHUSDT", "LTCUSDT", "XRPUSDT"):
            assert not ist_referenz(name)

    def test_die_beiden_mengen_ueberschneiden_sich_nicht(self):
        import cli

        assert not set(PAIRS) & set(cli._KONTRAKTE)

    def test_jedes_referenzsymbol_hat_einen_kontrakt(self):
        """Sonst kaeme der Nutzer nach dem Backfill nicht weiter."""
        import cli

        for name in PAIRS:
            kontrakt = cli._bybit_kontrakt(name)
            assert kontrakt != name, f"{name} ohne Kontraktzuordnung"
            assert kontrakt in cli._KONTRAKTE


class TestKontraktdaten:
    def test_bekannte_symbole_bekommen_ihre_eigenen_werte(self):
        import cli

        btc = cli._fallback_instrument("BTCUSDT")
        eth = cli._fallback_instrument("ETHUSDT")
        assert btc.base_coin == "BTC"
        assert eth.base_coin == "ETH"
        assert btc.qty_step != eth.qty_step
        assert btc.max_order_qty != eth.max_order_qty

    def test_unbekanntes_symbol_ist_ein_fehler(self):
        """**Der Fund von Befund 115.**

        Vorher gab ``_KONTRAKTE.get(symbol, _KONTRAKTE["BTCUSDT"])`` jedem
        unbekannten Symbol still die BTC-Werte - ``base_coin`` eingeschlossen:

            SOLUSDT   -> Schritt 0,001  min 0,001  max 1190  Basis BTC

        Ein SOL-Kontrakt mit BTC als Basiswaehrung. Die Groessen entscheiden,
        ob eine Order zustande kommt; ein geratener Wert sieht aus wie ein
        Marktbefund.
        """
        import cli

        for unbekannt in ("SOLUSDT", "BTC-USDT", "btcusdt", ""):
            with pytest.raises(KeyError, match="Keine Kontraktdaten"):
                cli._fallback_instrument(unbekannt)

    def test_die_meldung_nennt_die_bekannten_und_den_weg(self):
        import cli

        with pytest.raises(KeyError) as fehler:
            cli._fallback_instrument("SOLUSDT")
        text = str(fehler.value)
        assert "BTCUSDT" in text
        assert "_KONTRAKTE" in text

    def test_die_lehre_steht_nicht_nur_im_docstring(self):
        """Bis Befund 115 stand sie dort und steuerte nichts.

        Dieselbe Klasse wie die Befunde 111 bis 114: Wissen liegt im System,
        aber nicht dort, wo es wirkt. Der Test haelt fest, dass es jetzt das
        Verhalten ist und nicht mehr nur der Kommentar.
        """
        import cli

        quelle = cli._fallback_instrument.__doc__ or ""
        assert "Marktbefund" in quelle
        with pytest.raises(KeyError):
            cli._fallback_instrument("SOLUSDT")
