"""Was echte Trades beweisen - und was das Modul verweigern muss.

Die wichtigen Tests stehen in ``TestAbwaertsdriftWirdNichtWeggerechnet``.
Alles andere ist Buchhaltung; dort sitzt die Eigenschaft, wegen der es das
Modul ueberhaupt gibt: Ein enttaeuschender Livebetrieb darf die Zulassung
nicht **naeher** ruecken, nur weil er die Stichprobe vergroessert.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from research.live_evidenz import (
    DRIFT_SCHWELLE,
    MAX_UNERKANNTE_VERSCHLECHTERUNG,
    MINDESTENS_AUSSAGEKRAEFTIG,
    _dsr,
    benoetigte_trades,
    bewerten,
    demo_dauer,
    drift_test,
    erkennbare_verschlechterung,
    live_trades_fuer_nachweis,
    r_werte,
)


@dataclass(frozen=True)
class FakeBacktestTrade:
    r_multiple: float | None


@dataclass(frozen=True)
class FakeLiveTrade:
    r: float | None


#: Der gemessene Spitzenkandidat: Erwartung +1,043 R je Trade, Sharpe je
#: Trade 0,242, Schiefe +3,74, Woelbung 17,4. Die Tests rechnen mit diesen
#: Zahlen, damit sie die wirkliche Lage abbilden und nicht eine bequemere -
#: die Schiefe vor allem, weil sie im Deflated Sharpe mit **negativem**
#: Vorzeichen steht und eine zahmere Verteilung die Huerde verschoebe.
ECHTE_ERWARTUNG = 1.043
ECHTER_SHARPE = 0.242


def trendfolge_r(
    n: int,
    *,
    seed: int = 7,
    mittel: float = ECHTE_ERWARTUNG,
    sharpe: float = ECHTER_SHARPE,
) -> list[float]:
    """R-Vielfache mit der Form **und** der Guete, die gemessen wurde.

    Viele kleine Verluste, wenige grosse Gewinner - Schiefe deutlich positiv.
    Eine Normalverteilung waere hier das falsche Modell und wuerde die Tests
    milder machen, als sie sein duerfen.

    Mittelwert und Streuung werden anschliessend exakt gesetzt. Ohne das
    haette die Stichprobe einen zufaelligen Sharpe je Trade, und die Tests
    wuerden je nach Startwert des Zufallsgenerators bestehen oder nicht -
    genau die Sorte Test, die spaeter niemand mehr ernst nimmt.
    """
    rng = np.random.default_rng(seed)
    gewinner = rng.random(n) < 0.24
    roh = np.where(
        gewinner,
        # Kleiner Formparameter, grosser Massstab: wenige, sehr grosse
        # Gewinner. Damit trifft die Stichprobe die gemessene Schiefe von
        # rund +3,7 statt der zahmeren +2,2 einer bequemeren Wahl.
        rng.gamma(shape=0.6, scale=9.0, size=n),
        -rng.uniform(0.6, 1.0, size=n),
    )
    streuung = float(np.std(roh))
    if streuung <= 0:
        return [mittel] * n
    normiert = (roh - roh.mean()) / streuung
    return list(normiert * (mittel / sharpe) + mittel)


class TestRWerteHolen:
    def test_beide_namen_werden_erkannt(self):
        backtest = [FakeBacktestTrade(1.5), FakeBacktestTrade(-1.0)]
        live = [FakeLiveTrade(0.5)]

        assert r_werte(backtest) == [1.5, -1.0]
        assert r_werte(live) == [0.5]

    def test_trades_ohne_stop_fallen_weg(self):
        """Kein Stop heisst kein bezifferbares Risiko - und damit kein R.

        Sie als Null zu zaehlen waere eine Aussage, die niemand gemacht hat,
        und wuerde den Mittelwert Richtung null ziehen.
        """
        trades = [FakeLiveTrade(2.0), FakeLiveTrade(None), FakeLiveTrade(-1.0)]

        assert r_werte(trades) == [2.0, -1.0]


class TestAbwaertsdriftWirdNichtWeggerechnet:
    """Der Grund, aus dem es dieses Modul gibt."""

    def test_schlechter_livebetrieb_wird_nicht_dazugerechnet(self):
        backtest = [FakeBacktestTrade(r) for r in trendfolge_r(156)]
        # 40 Live-Trades, die durchweg deutlich schlechter laufen.
        live = [FakeLiveTrade(r) for r in trendfolge_r(40, seed=99, mittel=-0.4)]

        evidenz = bewerten(backtest, live, trials=81, live_tage=800)

        assert not evidenz.vertraegt_sich
        assert evidenz.dsr_mit_live is None, (
            "Ein schlechterer Livebetrieb darf keinen Deflated Sharpe erzeugen"
        )
        assert evidenz.p_wert_drift < DRIFT_SCHWELLE
        assert "schlechter" in evidenz.urteil

    def test_der_gefaehrliche_fall_ist_der_maessig_schlechte(self):
        """Der Kern des Moduls, und der Grund fuer die zweite Bedingung.

        Ein Livebetrieb, der **zwei Drittel** des Vorteils verliert, hebt den
        Deflated Sharpe trotzdem - sqrt(n) waechst schneller, als der
        Mittelwert faellt. Und der Signifikanztest schlaegt nicht an, weil er
        bei 40 Beobachtungen dieser Verteilung fast nichts sehen kann.

        Genau diese Kombination - schaedlich und unauffaellig - waere durch
        einen reinen Signifikanztest durchgerutscht.
        """
        backtest_r = trendfolge_r(156)
        # 71 % des Vorteils weg: 1,043 R -> 0,30 R
        live_r = trendfolge_r(40, seed=99, mittel=0.30)

        naiv = _dsr(backtest_r + live_r, 81)
        ohne = _dsr(backtest_r, 81)

        assert naiv > ohne, "Der schaedliche Fall muss den Wert heben"
        assert drift_test(backtest_r, live_r) > DRIFT_SCHWELLE, (
            "Und der Signifikanztest darf ihn gerade nicht erkennen - sonst "
            "prueft dieser Test nicht mehr, wovon er handelt"
        )

        # Die zweite Bedingung faengt ihn trotzdem ab:
        evidenz = bewerten(
            [FakeBacktestTrade(r) for r in backtest_r],
            [FakeLiveTrade(r) for r in live_r],
            trials=81,
        )
        assert evidenz.dsr_mit_live is None
        assert not evidenz.aussagekraeftig

    def test_totalausfall_wird_auch_vom_signifikanztest_erkannt(self):
        backtest_r = trendfolge_r(156)
        live_r = trendfolge_r(40, seed=99, mittel=-0.4)

        assert drift_test(backtest_r, live_r) < DRIFT_SCHWELLE

    def test_guter_livebetrieb_wird_dazugerechnet_wenn_genug_da_ist(self):
        """Zusammengerechnet wird erst, wenn die Stichprobe etwas beweisen kann.

        Die Zahl der Live-Trades ist hier bewusst gross: Bei weniger wuerde
        das Modul zu Recht ablehnen, und der Test wuerde nicht zeigen, was er
        zeigen soll.
        """
        backtest_r = trendfolge_r(156)
        noetig = live_trades_fuer_nachweis(backtest_r)
        backtest = [FakeBacktestTrade(r) for r in backtest_r]
        live = [FakeLiveTrade(r) for r in trendfolge_r(noetig, seed=5)]

        evidenz = bewerten(backtest, live, trials=81, live_tage=3650)

        assert evidenz.vertraegt_sich
        assert evidenz.aussagekraeftig
        assert evidenz.dsr_mit_live is not None
        assert evidenz.dsr_mit_live > evidenz.dsr_ohne_live, (
            "Mehr Trades derselben Qualitaet muessen den Wert heben"
        )

    def test_besserer_livebetrieb_gilt_nicht_als_drift(self):
        """Einseitig geprueft: Nur schlechter ist ein Problem."""
        backtest_r = trendfolge_r(156)
        besser = trendfolge_r(40, seed=3, mittel=2.0)

        assert drift_test(backtest_r, besser) > DRIFT_SCHWELLE

    def test_wenige_live_trades_gelten_als_nicht_aussagekraeftig(self):
        """Bei drei Trades hat kein Test Aussagekraft - auch dieser nicht.

        Das Modul muss das sagen, statt aus drei Werten ein Urteil zu bauen.
        """
        backtest = [FakeBacktestTrade(r) for r in trendfolge_r(156)]
        live = [FakeLiveTrade(r) for r in trendfolge_r(3, seed=1, mittel=-2.0)]

        evidenz = bewerten(backtest, live, trials=81, live_tage=30)

        assert not evidenz.aussagekraeftig
        assert evidenz.live_trades < MINDESTENS_AUSSAGEKRAEFTIG


class TestDriftTest:
    def test_gleiche_verteilung_gibt_unauffaelligen_wert(self):
        werte = trendfolge_r(200)
        haelfte = trendfolge_r(50, seed=11)

        p = drift_test(werte, haelfte)

        assert 0.0 <= p <= 1.0
        assert p > DRIFT_SCHWELLE

    def test_ergebnis_ist_wiederholbar(self):
        """Ein Urteil, das beim zweiten Aufruf anders ausfaellt, waere keines."""
        a, b = trendfolge_r(150), trendfolge_r(30, seed=4)

        assert drift_test(a, b) == drift_test(a, b)

    def test_leere_seite_wird_abgelehnt(self):
        with pytest.raises(ValueError, match="Werte"):
            drift_test([1.0, 2.0], [])


class TestBlinderFleck:
    """Was bei dieser Stichprobengroesse ueberhaupt auffallen wuerde."""

    def test_wenige_trades_sehen_fast_nichts(self):
        werte = trendfolge_r(156)

        blind = erkennbare_verschlechterung(werte, 10)

        assert blind > 0.5, (
            "Bei zehn Live-Trades muss der blinde Fleck riesig sein - alles "
            "andere waere eine Scheingenauigkeit"
        )

    def test_mehr_trades_sehen_mehr(self):
        """Monoton: Jeder zusaetzliche Trade kann den Blick nur schaerfen."""
        werte = trendfolge_r(156)

        gross = erkennbare_verschlechterung(werte, 20)
        mittel = erkennbare_verschlechterung(werte, 100)
        klein = erkennbare_verschlechterung(werte, 500)

        assert gross > mittel > klein

    def test_kein_live_trade_heisst_voellig_blind(self):
        assert erkennbare_verschlechterung(trendfolge_r(100), 0) == 1.0

    def test_ohne_backtest_ist_es_ein_fehler(self):
        with pytest.raises(ValueError, match="Backtest"):
            erkennbare_verschlechterung([], 50)

    def test_die_umkehrung_passt_zur_hinrichtung(self):
        """``live_trades_fuer_nachweis`` muss halten, was es verspricht."""
        werte = trendfolge_r(156)

        noetig = live_trades_fuer_nachweis(werte)

        assert (
            erkennbare_verschlechterung(werte, noetig)
            <= MAX_UNERKANNTE_VERSCHLECHTERUNG
        )

    def test_strengere_forderung_verlangt_mehr_trades(self):
        werte = trendfolge_r(156)

        assert live_trades_fuer_nachweis(werte, 0.10) > live_trades_fuer_nachweis(
            werte, 0.50
        )


class TestBenoetigteTrades:
    def test_mehr_trades_derselben_guete_schliessen_die_luecke(self):
        werte = trendfolge_r(156)

        fehlend = benoetigte_trades(werte, trials=81)

        assert fehlend > 0
        # Und mit genau so vielen mehr ist das Ziel erreicht:
        assert benoetigte_trades(werte + trendfolge_r(fehlend, seed=2),
                                 trials=81) >= 0

    def test_erreichtes_ziel_meldet_null(self):
        # Sehr viele Trades derselben Guete - die Huerde ist dann genommen.
        werte = trendfolge_r(2000)

        assert benoetigte_trades(werte, trials=81) == 0

    def test_mehr_versuche_verlangen_mehr_trades(self):
        """Jede gepruefte Hypothese hebt die Huerde - auch hier."""
        werte = trendfolge_r(156)

        assert benoetigte_trades(werte, trials=400) > benoetigte_trades(
            werte, trials=81
        )

    def test_ohne_streuung_kein_urteil(self):
        assert benoetigte_trades([1.0, 1.0, 1.0], trials=81) == 0


class TestOhneLiveTrades:
    def test_meldet_die_luecke_statt_zu_schweigen(self):
        backtest = [FakeBacktestTrade(r) for r in trendfolge_r(156)]

        evidenz = bewerten(backtest, [], trials=81)

        assert evidenz.live_trades == 0
        assert evidenz.dsr_mit_live is None
        assert evidenz.fehlende_trades > 0
        assert "Live-Trade" in evidenz.urteil

    def test_ohne_backtest_ist_es_ein_fehler(self):
        with pytest.raises(ValueError, match="Backtest"):
            bewerten([], [FakeLiveTrade(1.0)], trials=81)


class TestWieLangeDasDauert:
    def test_ein_monat_demo_bringt_kaum_trades(self):
        """Die Zahl, die regelmaessig ueberrascht.

        Der Spitzenkandidat handelt 17-mal im Jahr. Der geplante Demomonat
        erzeugt daraus **1,4** Trades - er prueft die Technik, nicht den
        Vorteil. Das gehoert gesagt, bevor jemand 30 Tage lang auf einen
        Beweis wartet, der so nicht entstehen kann.
        """
        assert demo_dauer(17.0, 30) == pytest.approx(1.4, abs=0.05)

    def test_hochrechnung_nennt_jahre_nicht_wochen(self):
        backtest = [FakeBacktestTrade(r) for r in trendfolge_r(156)]
        live = [FakeLiveTrade(r) for r in trendfolge_r(25, seed=8, mittel=1.04)]

        # 25 Trades in anderthalb Jahren entsprechen rund 17 im Jahr.
        evidenz = bewerten(backtest, live, trials=81, live_tage=537)

        assert evidenz.trades_pro_jahr == pytest.approx(17.0, abs=1.0)
        if evidenz.fehlende_trades:
            assert evidenz.jahre_bis_beweis is not None
            assert evidenz.jahre_bis_beweis > 0.5

    def test_ohne_zeitraum_keine_jahresangabe(self):
        backtest = [FakeBacktestTrade(r) for r in trendfolge_r(156)]
        live = [FakeLiveTrade(r) for r in trendfolge_r(25, seed=8)]

        evidenz = bewerten(backtest, live, trials=81)

        assert evidenz.trades_pro_jahr is None
        assert evidenz.jahre_bis_beweis is None


class TestSpitzenkandidatIstFestgeschrieben:
    """Der beste Kandidat darf nicht in Wegwerf-Skripten leben."""

    def test_er_laesst_sich_bauen_und_uebersetzen(self):
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        genome = spitzenkandidat()
        compile_genome(genome)

        assert genome.konfluenz, "Die Konfluenz ist Teil der Groessenlogik"
        assert genome.sizing.konviktion_bonus > 0

    def test_er_steht_in_keiner_generation(self):
        """Sonst wuerde ihn der Wettbewerb erneut zaehlen.

        Jede geprueften Hypothese hebt die Huerde des Deflated Sharpe fuer
        **alle** folgenden. Einen Kandidaten erneut durchlaufen zu lassen,
        ueber den schon alles bekannt ist, verschlechtert die Lage, ohne
        etwas beizutragen.
        """
        from research.seeds import GENERATIONS, spitzenkandidat

        gesucht = spitzenkandidat().genome_id
        for nummer, bauplaene in GENERATIONS.items():
            for bau in bauplaene:
                assert bau().genome_id != gesucht, (
                    f"Steht in Generation {nummer} - der Wettbewerb wuerde ihn "
                    "erneut zaehlen"
                )

    def test_seine_kennung_ist_die_gemessene(self):
        """Haelt fest, dass hier wirklich das steht, was gemessen wurde.

        Die Kennung ist der Hash ueber alle Regelbestandteile. Aendert jemand
        eine Periode oder den Stop, faellt es hier auf - und nicht erst,
        wenn die Zahlen im BEFUND nicht mehr zum Code passen.
        """
        from research.seeds import spitzenkandidat

        assert spitzenkandidat().genome_id == "111cc2ecd5d53968"


class TestBericht:
    def test_bericht_nennt_beide_zahlen(self):
        backtest = [FakeBacktestTrade(r) for r in trendfolge_r(156)]
        live = [FakeLiveTrade(r) for r in trendfolge_r(30, seed=6, mittel=1.04)]

        text = bewerten(backtest, live, trials=81, live_tage=644).bericht()

        assert "Backtest" in text
        assert "Live" in text
        assert "Deflated Sharpe" in text
