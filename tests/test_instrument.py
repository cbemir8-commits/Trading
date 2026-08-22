"""Fuer welches Instrument ist der Kandidat gebaut?

Drei Tests tragen diese Datei:

``test_der_deckel_kostet_bitgleich_nichts`` - Der Kern. Nicht "der Anteil
ueber 1,0 ist klein", sondern: Der gedeckelte Lauf liefert dieselben Zahlen
bis auf die letzte Stelle. Damit ist der Hebel nachweislich ungenutzt.

``test_spot_ist_ein_szenario_und_keine_notloesung`` - Die Folge. Ohne Funding
faellt der groesste Kostenblock weg, und mit ihm zwei Gates.

``test_knapp_daneben_bleibt_durchgefallen`` - Die Wache. 14,83 % gegen
geforderte 15,00 % sind 0,17 Punkte zu wenig, und daran wird nichts gedreht.
"""

from __future__ import annotations

import pytest

from research.instrument import Instrumentenwahl, Lauf

#: Die gemessenen Laeufe des Bestands auf BTC + ETH, Tageskerzen, 500 EUR,
#: Versuchsstand 198. Nachzurechnen mit ``cli instrument``.
MIT_HEBEL = Lauf(
    "Perpetual", 152, 13.47, 10.64, 7, 11,
    ("Messlatte", "Schlechtestes Jahr", "Deflated Sharpe", "Parameter-Plateau"),
    funding=63.79, gebuehren=7.17, brutto=776.97, sharpe=1.473,
)
OHNE_HEBEL = Lauf(
    "fraction 1.0", 152, 13.47, 10.64, 7, 11,
    ("Messlatte", "Schlechtestes Jahr", "Deflated Sharpe", "Parameter-Plateau"),
    funding=63.79, gebuehren=7.17, brutto=776.97, sharpe=1.473,
)
SPOT = Lauf(
    "Spot", 152, 14.83, 9.87, 9, 11,
    ("Messlatte", "Deflated Sharpe"), funding=0.0, brutto=776.97, sharpe=1.610,
)
SPOT_GESTRESST = Lauf(
    "Spot, doppelte Gebuehren", 152, 14.59, 10.10, 9, 11,
    ("Messlatte", "Deflated Sharpe"), funding=0.0,
)


def wahl(**abweichung) -> Instrumentenwahl:
    daten = {
        "mit_hebel": MIT_HEBEL, "ohne_hebel": OHNE_HEBEL, "spot": SPOT,
        "spot_gestresst": SPOT_GESTRESST, "short_regeln": 0,
        "anteil_ueber_eins": 0.002,
    }
    daten.update(abweichung)
    return Instrumentenwahl(**daten)


class TestHebel:
    def test_der_deckel_kostet_bitgleich_nichts(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Die bequeme Fassung waere "0,2 % der Balken, das ist wenig" - und
        0,2 % waere eine Schwelle, die ich mir aussuche. Gemessen ist etwas
        Staerkeres: dieselben Zahlen.
        """
        w = wahl()

        assert w.deckel_kostet_nichts
        assert w.ohne_hebel.gleiche_zahlen(w.mit_hebel)
        assert "nutzt seinen Hebel nicht" in w.urteil()

    def test_ein_genutzter_hebel_wird_erkannt(self) -> None:
        """Gegenprobe: Faellt die Rendite unter dem Deckel, braucht der
        Kandidat den Hebel - und Spot ist keine Option."""
        braucht = wahl(
            ohne_hebel=Lauf("fraction 1.0", 140, 8.10, 7.20, 6, 11, brutto=400.0)
        )

        assert not braucht.deckel_kostet_nichts
        assert not braucht.spot_moeglich
        assert "braucht seinen Hebel" in braucht.urteil()
        assert "kein Szenario" in braucht.urteil()

    def test_ein_unterschied_in_der_zweiten_stelle_zaehlt_schon(self) -> None:
        """Keine Toleranz: Die Frage ist, ob der Deckel etwas veraendert,
        nicht ob die Veraenderung klein ist."""
        knapp = wahl(
            ohne_hebel=Lauf("fraction 1.0", 152, 13.45, 10.64, 7, 11, brutto=776.97)
        )

        assert not knapp.deckel_kostet_nichts

    def test_shorts_schliessen_spot_aus(self) -> None:
        """Spot kennt keinen Leerverkauf. Ein Kandidat mit Short-Regeln ist
        dort nicht handelbar, auch ohne Hebel."""
        mit_shorts = wahl(short_regeln=2)

        assert mit_shorts.braucht_shorts
        assert mit_shorts.deckel_kostet_nichts
        assert not mit_shorts.spot_moeglich
        assert "Gegenrichtung" in mit_shorts.urteil()

    def test_der_bestand_hat_keine_short_regeln(self) -> None:
        """Gemessen am echten Genom, nicht behauptet."""
        from research.seeds import spitzenkandidat

        genome = spitzenkandidat()

        assert genome.entry_short == []
        assert genome.exit_short == []


class TestSpot:
    def test_spot_ist_ein_szenario_und_keine_notloesung(self) -> None:
        """**Die Folge, und die Korrektur an Befund 100.**

        Dort stand, die Nullzeile beim Funding sei "eine Empfindlichkeit,
        kein Szenario", weil ohne Hebel die Positionsgroessen gar nicht
        zustande kaemen. Sie kommen zustande.
        """
        w = wahl()

        assert w.spot_moeglich
        assert w.gewinn_an_gates == 2
        urteil = w.urteil()
        assert "Szenario und keine Notloesung" in urteil
        assert "Messlatte" in urteil and "Deflated Sharpe" in urteil

    def test_die_beiden_gekippten_gates_sind_die_aus_befund_100(self) -> None:
        """Schlechtestes Jahr und Parameter-Plateau - dieselben zwei, die dort
        zwischen 5,5 % und 11 % Funding gekippt sind."""
        w = wahl()

        weg = set(w.mit_hebel.gescheitert) - set(w.spot.gescheitert)

        assert weg == {"Schlechtestes Jahr", "Parameter-Plateau"}

    def test_der_gebuehrenstress_wird_als_stress_gekennzeichnet(self) -> None:
        """Bybits Spot-Tarif ist hier nicht gemessen. Das Urteil sagt es."""
        w = wahl()

        assert w.haelt_den_stress
        urteil = w.urteil()
        assert "nicht gemessen" in urteil
        assert "Wie hoch sie sind, sagt das nicht" in urteil

    def test_ein_gebrochener_stress_wird_deutlich(self) -> None:
        schwach = wahl(
            spot_gestresst=Lauf("Spot, doppelte Gebuehren", 152, 12.0, 11.0, 7, 11)
        )

        assert not schwach.haelt_den_stress
        assert "gehoert nachgeschlagen" in schwach.urteil()

    def test_ohne_spot_lauf_wird_nichts_behauptet(self) -> None:
        ohne = wahl(spot=None, spot_gestresst=None)

        assert ohne.gewinn_an_gates == 0
        assert ohne.haelt_den_stress is None
        assert "Szenario und keine Notloesung" not in ohne.urteil()


class TestEhrlichkeit:
    def test_knapp_daneben_bleibt_durchgefallen(self) -> None:
        """**Die Wache.**

        14,83 % gegen 15,00 % sind 0,17 Punkte zu wenig. Die Messlatte steht
        in beiden Spot-Laeufen weiter unter den offenen Gates.
        """
        w = wahl()

        assert "Messlatte" in w.spot.gescheitert
        assert w.spot.cagr < 15.0
        assert "Knapp daneben ist nicht bestanden" in w.urteil()

    def test_der_deflated_sharpe_bleibt_offen(self) -> None:
        """Das Gate, an dem alles haengt, bewegt sich in keinem Lauf."""
        w = wahl()

        for lauf in (w.mit_hebel, w.ohne_hebel, w.spot, w.spot_gestresst):
            assert "Deflated Sharpe" in lauf.gescheitert
        assert "bewegt sich in keinem dieser Laeufe" in w.urteil()

    def test_die_referenzdaten_bleiben_ein_vorbehalt(self) -> None:
        """Befund 102 gilt weiter - der groesste Einwand faellt, die anderen
        nicht."""
        assert "Befund 102" in wahl().urteil()

    def test_die_tabelle_zeigt_alle_laeufe(self) -> None:
        text = wahl().tabelle()

        for name in ("Perpetual", "fraction 1.0", "Spot"):
            assert name in text
        assert "7/11" in text and "9/11" in text

    def test_die_korrektur_steht_im_modul(self) -> None:
        """Eine widerlegte eigene Aussage gehoert benannt, nicht stillschweigend
        ersetzt."""
        import research.instrument as modul

        assert "Korrektur an Befund 100" in (modul.__doc__ or "")
        assert "widerlegt" in (modul.__doc__ or "")


def test_der_kapitalanteil_liegt_wirklich_unter_eins() -> None:
    """Die Zahl aus dem Modul-Docstring, am echten Genom nachgerechnet.

    **Auf dem gemeinsamen Zeitraum**, und das ist keine Bequemlichkeit: Der
    Backtest laeuft auf ``common_range`` von BTC und ETH, sieht also nur ab
    2017. Der erste Anlauf dieses Tests las die volle BTC-Historie ab 2012 und
    kam auf 1,3 % statt 0,2 % - eine richtige Zahl ueber einen Zeitraum, den
    die Messung gar nicht kennt.
    """
    pytest.importorskip("numpy")
    import numpy as np

    from backtest.portfolio_walkforward import common_range
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.seeds import spitzenkandidat
    from strategy import indicators

    store = CandleStore(get_settings().paths.data_store)
    roh = {
        s: store.read(s, Interval("D"))
        for s in ("BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP")
    }
    if any(f.empty for f in roh.values()):
        pytest.skip("keine Referenzkerzen im Speicher")

    genome = spitzenkandidat()
    for frame in common_range(roh).values():
        vola = indicators.compute(
            "realized_vol", frame, {"period": genome.sizing.vol_period}
        )
        anteil = np.clip(
            genome.sizing.target_vol_pct / vola, 0.0, genome.sizing.fraction
        )
        gut = np.isfinite(anteil)

        assert float(np.nanmedian(anteil)) < 1.0
        assert float(np.mean(anteil[gut] > 1.0)) < 0.01
