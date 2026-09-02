"""Gepflanzter Trend - und die Eigenschaften, ohne die er nichts beweist.

Zwei Tests tragen diese Datei, und beide pruefen nicht das Ergebnis, sondern
die **Gueltigkeit des Versuchsaufbaus**:

``test_die_streuung_bleibt`` - Wuerde das Pflanzen die Reihe ruhiger machen,
faenden Rueckgangs- und Monte-Carlo-Gate es mit jeder Stufe leichter, ohne
dass die Strategie irgendetwas besser getroffen haette. Die Leiter maesse dann
ihre eigene Erzeugung.

``test_null_laesst_die_reihe_in_ruhe`` - Die unterste Sprosse muss die
Wirklichkeit sein. Eine Leiter, die schon bei Anteil 0 woanders anfaengt, hat
keinen Bezugspunkt.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.teststaerke import (
    MINDESTSTEIGUNG,
    Leiter,
    Stufe,
    Vergleich,
    pflanze_trend,
    regimefolge,
)


def reihe(n: int = 900, saat: int = 7) -> pd.DataFrame:
    """Eine Kerzenreihe mit Dochten, wie sie aus dem Speicher kaeme."""
    rng = np.random.default_rng(saat)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.03, n)))
    spanne = close * 0.01
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC"),
            "open": close * 0.999,
            "high": close + spanne,
            "low": close - spanne,
            "close": close,
            "volume": rng.uniform(10, 100, n),
        }
    )


def log_renditen(frame: pd.DataFrame) -> np.ndarray:
    return np.diff(np.log(frame["close"].to_numpy(dtype=float)))


class TestRegime:
    def test_es_haelt_ungefaehr_die_vorgabe_durch(self) -> None:
        folge = regimefolge(20_000, dauer=60, saat=1)
        wechsel = int(np.sum(np.diff(np.sign(folge)) != 0))

        assert 250 < wechsel < 420, (
            f"{wechsel} Wechsel auf 20 000 Kerzen - erwartet werden rund 333"
        )

    def test_es_bringt_keinen_drift_mit(self) -> None:
        """Gepflanzt wird Vorhersagbarkeit, nicht Rendite.

        Eine Ziehung mit mehr Aufwaerts- als Abwaertsregimes traege sonst
        einen zusaetzlichen Drift ein - und daran verdiente auch eine Regel,
        die gar nichts erkennt.
        """
        for saat in range(5):
            assert abs(float(regimefolge(3000, saat=saat).mean())) < 1e-9

    def test_eine_leere_reihe_kippt_nicht(self) -> None:
        assert len(regimefolge(0)) == 0


class TestPflanzen:
    def test_die_streuung_bleibt(self) -> None:
        """**Der Test, der den Versuchsaufbau traegt.**

        Der Rauschanteil muss um genau so viel sinken, wie das Regime
        hinzukommt. Sonst ist jede Stufe zugleich eine ruhigere Reihe, und die
        Risiko-Gates werden leichter, ohne dass die Strategie etwas leistet.
        """
        roh = reihe()
        vorher = float(np.std(log_renditen(roh)))
        regime = regimefolge(len(roh), saat=3)

        for anteil in (0.1, 0.3, 0.6):
            gepflanzt = pflanze_trend(roh, anteil=anteil, regime=regime)
            nachher = float(np.std(log_renditen(gepflanzt)))

            assert nachher == pytest.approx(vorher, rel=0.05), (
                f"Anteil {anteil}: Streuung {nachher:.5f} statt {vorher:.5f}"
            )

    def test_der_drift_bleibt(self) -> None:
        """**Der zweite Test, der den Versuchsaufbau traegt - und er fehlte.**

        Der erste Anlauf skalierte die Renditen ohne den Mittelwert
        herauszunehmen und daempfte damit den Drift des Marktes mit: Bei
        Anteil 0,5 fiel Kaufen-und-Halten von +1195 % auf +110 %. Jede
        gepflanzte Stufe war so zugleich ein schwaecherer Markt, und das Gate
        mit der Mindestrendite scheiterte an meiner Rechnung statt an der
        Strategie.

        Geprueft wird deshalb an der Groesse, um die es geht: dem Endstand von
        Kaufen-und-Halten.
        """
        roh = reihe()
        regime = regimefolge(len(roh), saat=3)
        vorher = float(roh["close"].iloc[-1] / roh["close"].iloc[0])

        for anteil in (0.1, 0.3, 0.6):
            gepflanzt = pflanze_trend(roh, anteil=anteil, regime=regime)
            nachher = float(
                gepflanzt["close"].iloc[-1] / gepflanzt["close"].iloc[0]
            )

            assert nachher == pytest.approx(vorher, rel=1e-9), (
                f"Anteil {anteil}: Halten bringt {nachher:.2f}x statt "
                f"{vorher:.2f}x - die Stufe hat den Markt veraendert, nicht "
                f"nur seine Vorhersagbarkeit"
            )

    def test_null_laesst_die_reihe_in_ruhe(self) -> None:
        roh = reihe()
        gleich = pflanze_trend(roh, anteil=0.0, regime=regimefolge(len(roh)))

        pd.testing.assert_frame_equal(
            gleich.reset_index(drop=True), roh.reset_index(drop=True)
        )

    def test_mehr_anteil_heisst_mehr_vorhersagbarkeit(self) -> None:
        """Die Wirkung muss in der gemeinten Groesse ankommen: Der gepflanzte
        Trend ist ueber Wochen gleichgerichtet, also steigt die Korrelation
        zwischen aufeinanderfolgenden Wochenrenditen."""
        roh = reihe(2000)
        regime = regimefolge(len(roh), saat=5)

        def wochenbindung(frame: pd.DataFrame) -> float:
            r = log_renditen(frame)
            wochen = r[: len(r) // 5 * 5].reshape(-1, 5).sum(axis=1)
            return float(np.corrcoef(wochen[:-1], wochen[1:])[0, 1])

        schwach = wochenbindung(pflanze_trend(roh, anteil=0.05, regime=regime))
        stark = wochenbindung(pflanze_trend(roh, anteil=0.5, regime=regime))

        assert stark > schwach + 0.1

    def test_die_dochte_bleiben_um_den_koerper(self) -> None:
        """Sonst griffen Stops an Preisen, die es in dieser Reihe nie gab -
        und der Backtest liefe weiter, ohne etwas zu melden."""
        gepflanzt = pflanze_trend(
            reihe(), anteil=0.4, regime=regimefolge(len(reihe()), saat=2)
        )

        assert (gepflanzt["high"] >= gepflanzt[["open", "close"]].max(axis=1)).all()
        assert (gepflanzt["low"] <= gepflanzt[["open", "close"]].min(axis=1)).all()
        assert (gepflanzt["low"] > 0).all()

    def test_ein_unmoeglicher_anteil_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError):
            pflanze_trend(reihe(), anteil=1.0, regime=regimefolge(900))

    def test_eine_zu_kurze_regimefolge_faellt_auf(self) -> None:
        """Stillschweigend zu kuerzen hiesse, einen Teil der Reihe ohne
        gepflanzten Trend zu lassen - und die Stufe waere schwaecher, als sie
        heisst."""
        with pytest.raises(ValueError):
            pflanze_trend(reihe(900), anteil=0.3, regime=regimefolge(100))


def stufe(anteil: float, *, bestanden: int, offen: tuple[str, ...] = ()) -> Stufe:
    # ``effektiv=trades``: In einer gebauten Sprosse gibt es keine
    # Blockstruktur, der Design-Effekt ist also 1. Auf echten Daten ist er
    # groesser, und genau das prueft ``TestDieGueteRechnetMitDerEffektiven``.
    return Stufe(
        anteil=anteil, trades=150, effektiv=150, sharpe=1.1,
        sharpe_je_trade=0.26, dsr=0.8, bestanden=bestanden, gesamt=11,
        offen=offen,
    )


class TestLeiter:
    def test_die_schwaechste_bestehende_stufe_zaehlt(self) -> None:
        leiter = Leiter(
            stufen=[
                stufe(0.4, bestanden=11),
                stufe(0.1, bestanden=7, offen=("Deflated Sharpe",)),
                stufe(0.2, bestanden=11),
            ],
            versuche=161,
        )

        assert leiter.erste_volle is not None
        assert leiter.erste_volle.anteil == 0.2, "Nicht die erste in der Liste"
        assert "An den Gates liegt es nicht" in leiter.urteil()

    def test_ohne_treffer_wird_das_hartnaeckigste_gate_benannt(self) -> None:
        """Die brauchbare Auskunft ist nicht "es klappt nicht", sondern
        woran - und zwar unabhaengig von der Regelfamilie."""
        leiter = Leiter(
            stufen=[
                stufe(0.1, bestanden=7, offen=("Deflated Sharpe", "Drawdown")),
                stufe(0.3, bestanden=9, offen=("Deflated Sharpe", "Drawdown")),
                stufe(0.5, bestanden=10, offen=("Deflated Sharpe",)),
            ],
            versuche=161,
        )

        assert leiter.erste_volle is None
        assert leiter.hartnaeckigstes == ("Deflated Sharpe", 3)
        assert "Deflated Sharpe" in leiter.urteil()
        assert "50%" in leiter.urteil()

    def test_ohne_stufen_wird_nichts_behauptet(self) -> None:
        assert "nichts zu sagen" in Leiter().urteil()

    def test_die_tabelle_zeigt_jede_stufe(self) -> None:
        leiter = Leiter(stufen=[stufe(0.0, bestanden=7), stufe(0.25, bestanden=9)])
        text = leiter.tabelle()

        assert "0%" in text and "25%" in text
        assert "7/11" in text and "9/11" in text


class TestGuete:
    """Qualitaet und Menge in einer Zahl - sonst wird die Leiter falsch gelesen.

    Eine Sprosse mit fuenffachem Vorteil je Trade sieht nach einem grossen
    Fortschritt aus. Handelt sie dafuer nur ein Achtel so oft, ist es keiner,
    und genau das passiert hier auf jeder Stufe.
    """

    def test_fuenffacher_vorteil_bei_einem_achtel_der_trades_ist_kein_fortschritt(
        self,
    ) -> None:
        anker = Stufe(0.0, 154, 1.47, 0.2569, 0.79, 7, 11, effektiv=154)
        stark = Stufe(0.5, 12, 2.50, 1.2734, 0.0, 9, 11, effektiv=12)

        assert stark.sharpe_je_trade / anker.sharpe_je_trade > 4.9
        assert stark.guete / anker.guete < 1.5, (
            "Die Guete darf den Eindruck des Vorteils je Trade nicht teilen"
        )

    def test_ohne_trades_ist_die_guete_null(self) -> None:
        assert Stufe(0.5, 0, 0.0, 0.0, None, 0, 11, effektiv=0).guete == 0.0


class TestVerduennung:
    """Der Haken des Aufbaus - und dass er nicht unter den Tisch faellt.

    Ein gepflanzter Trend laesst eine Trendfolge **seltener** handeln. Damit
    tauscht die Leiter Vorteil gegen Stichprobe, und der Deflated Sharpe
    braucht beides. Meldet sie in dieser Lage trotzdem ein Urteil ueber die
    Zulassungsstrecke, behauptet sie mehr, als sie gemessen hat.
    """

    def test_eine_ausgeduennte_leiter_urteilt_nicht_ueber_die_strecke(self) -> None:
        leiter = Leiter(
            stufen=[
                Stufe(0.0, 154, 1.47, 0.257, 0.79, 7, 11, ("Deflated Sharpe",),
                      effektiv=154),
                Stufe(0.5, 13, 2.63, 1.157, 0.0, 9, 11,
                      ("Stichprobengroesse",), effektiv=13),
            ],
            versuche=161,
        )

        assert leiter.verduennung is not None
        assert leiter.verduennung < 0.1
        urteil = leiter.urteil()
        assert "sagt das aber nichts" in urteil
        assert "gekoppelt" in urteil
        assert "kann kein echter es" not in urteil, (
            "Die starke Schlussfolgerung darf hier gerade nicht fallen"
        )

    def test_bei_stabiler_stichprobe_faellt_das_urteil(self) -> None:
        leiter = Leiter(
            stufen=[
                Stufe(0.0, 154, 1.47, 0.257, 0.79, 7, 11, ("Deflated Sharpe",),
                      effektiv=154),
                Stufe(0.5, 140, 2.63, 0.900, 0.90, 10, 11,
                      ("Deflated Sharpe",), effektiv=140),
            ],
            versuche=161,
        )

        assert "kann kein echter es" in leiter.urteil()

    def test_ohne_zwei_stufen_gibt_es_keine_verduennung(self) -> None:
        assert Leiter(stufen=[stufe(0.0, bestanden=7)]).verduennung is None


def gestufte(*paare: tuple[float, float, int]) -> Leiter:
    """Eine Leiter aus (Anteil, SR je Trade, Trades)."""
    return Leiter(
        stufen=[
            Stufe(a, n, 1.0, sr, 0.5, 8, 11, effektiv=n) for a, sr, n in paare
        ],
        versuche=161,
    )


class TestSteigung:
    def test_eine_flache_leiter_entkoppelt_nicht(self) -> None:
        """Der gemessene Fall aus Befund 54: Der Vorteil je Trade
        verfuenffacht sich, die Guete steht praktisch still."""
        leiter = gestufte((0.0, 0.2569, 154), (0.35, 0.7913, 17), (0.5, 1.2734, 12))

        assert leiter.steigung is not None
        assert not leiter.entkoppelt

    def test_eine_steigende_leiter_mit_stabiler_stichprobe_entkoppelt(self) -> None:
        leiter = gestufte((0.0, 0.26, 154), (0.25, 0.40, 150), (0.5, 0.55, 146))

        assert leiter.steigung is not None and leiter.steigung > MINDESTSTEIGUNG
        assert leiter.entkoppelt

    def test_steigung_allein_reicht_nicht(self) -> None:
        """**Der Test, der das Kriterium ehrlich haelt.**

        Eine Leiter kann steil steigen und die Stichprobe trotzdem verlieren -
        dann ist die Kopplung nicht gebrochen, sondern nur anders herum
        durchlaufen. Ohne diesen Teil des Kriteriums haette fast jede Variante
        "entkoppelt" gemeldet.
        """
        leiter = gestufte((0.0, 0.26, 154), (0.5, 2.00, 20))

        assert leiter.steigung is not None and leiter.steigung > MINDESTSTEIGUNG
        assert leiter.verduennung is not None and leiter.verduennung < 0.5
        assert not leiter.entkoppelt

    def test_eine_einzelne_stufe_hat_keine_steigung(self) -> None:
        assert gestufte((0.2, 0.3, 100)).steigung is None


class TestVergleich:
    def test_die_matrix_zeigt_guete_und_trades_je_variante(self) -> None:
        v = Vergleich(
            leitern={
                "unbegrenzt": gestufte((0.0, 0.2569, 154), (0.5, 1.2734, 12)),
                "30 Kerzen": gestufte((0.0, 0.26, 150), (0.5, 0.55, 146)),
            }
        )
        text = v.matrix()

        assert "unbegrenzt" in text and "30 Kerzen" in text
        assert "154" in text and "146" in text
        assert "Steigung" in text

    def test_eine_entkoppelnde_variante_wird_benannt(self) -> None:
        """Entkoppelt, aber **unter** der Latte.

        Bei 150 Trades verlangt die Schwelle rund 3,67; diese Variante kommt
        auf 0,25 * sqrt(150) = 3,06. Die Kopplung ist gebrochen - erreicht
        ist die Latte nicht, und genau das soll dastehen.
        """
        v = Vergleich(
            leitern={
                "unbegrenzt": gestufte((0.0, 0.2569, 154), (0.5, 1.2734, 12)),
                "30 Kerzen": gestufte((0.0, 0.18, 154), (0.5, 0.25, 150)),
            }
        )

        assert v.raeumen == {}
        assert "30 Kerzen" in v.urteil()
        assert "Kopplung bricht" in v.urteil()
        assert "kostet Versuche" in v.urteil() or "Versuche kostet" in v.urteil()

    def test_eine_variante_die_ihre_latte_erreicht_wird_anders_gemeldet(self) -> None:
        """**Befund 178.** Eine wachsende Guete ist nicht dasselbe wie eine,
        die genuegt.

        Die Latte bewegt sich mit der Stichprobe (Befund 176) - eine
        groessere Guete bei kleinerer Stichprobe kann weiter von ihr weg sein
        als eine kleinere bei grosser. Die Matrix zeigte bis hierher nur die
        Guete.
        """
        v = Vergleich(
            leitern={
                "unbegrenzt": gestufte((0.0, 0.2569, 154), (0.5, 1.2734, 12)),
                "30 Kerzen": gestufte((0.0, 0.26, 154), (0.5, 0.60, 150)),
            }
        )

        assert v.raeumen == {"30 Kerzen": [0.5]}
        assert "raeumt die Latte" in v.urteil()
        assert "50%" in v.urteil()
        assert "auf echten Daten kostet es Versuche" in v.urteil()
        assert v.urteil().startswith("**Eine Variante")

    def test_mehrere_treffer_werden_im_plural_gemeldet(self) -> None:
        """Der gemessene Fall hatte zwei - "eine Variante" waere dort falsch."""
        v = Vergleich(
            leitern={
                "Ausbruch": gestufte((0.0, 0.26, 154), (0.5, 0.60, 150)),
                "30 Kerzen": gestufte((0.0, 0.26, 154), (0.5, 0.62, 150)),
            }
        )

        assert len(v.raeumen) == 2
        assert v.urteil().startswith("**2 Varianten erreichen ihre Latte.**")

    def test_die_matrix_zeigt_die_latte_neben_der_guete(self) -> None:
        v = Vergleich(
            leitern={"30 Kerzen": gestufte((0.0, 0.26, 154), (0.5, 0.60, 150))}
        )
        text = v.matrix()

        assert "noetig" in text
        assert "*" in text, "die geraeumte Sprosse ist nicht markiert"

    def test_lange_namen_werden_nicht_gekuerzt(self) -> None:
        """**Der Anzeigefehler aus Befund 178.**

        Die Kuerzung sass beim Aufrufer (``cli._familie`` schnitt auf 14
        Zeichen, damit es in die Spalte passte) und wanderte damit in die
        Schluesselmenge - das Urteil nannte die Variante dann
        "**Neues Hoch im **". Die Spalte richtet sich jetzt nach dem Namen
        statt umgekehrt.
        """
        lang = "Neues Hoch im Takt, mit Deckel"
        v = Vergleich(
            leitern={
                "kurz": gestufte((0.0, 0.2569, 154), (0.5, 1.2734, 12)),
                lang: gestufte((0.0, 0.26, 154), (0.5, 0.60, 150)),
            }
        )

        assert lang in v.urteil()
        # In der Tabelle darf die Ueberschrift kuerzen - dann aber mit
        # Aufloesung darunter, damit der volle Name auffindbar bleibt.
        assert f"= {lang}" in v.matrix()

    def test_die_matrix_bleibt_ausgerichtet(self) -> None:
        """Kopf, Zellen und Steigung in derselben Breite - sonst liest man die
        Zahl unter dem falschen Namen ab."""
        v = Vergleich(
            leitern={
                "Neues Hoch im Takt": gestufte((0.0, 0.26, 154), (0.5, 0.60, 150)),
                "kurz": gestufte((0.0, 0.2569, 154), (0.5, 1.2734, 12)),
            }
        )
        zeilen = [z for z in v.matrix().splitlines() if not z.startswith("[")]

        assert len({len(z.rstrip()) for z in zeilen if set(z) == {"-"}}) == 1
        breiten = {len(z) for z in zeilen if set(z) != {"-"}}
        assert len(breiten) == 1, f"unterschiedliche Zeilenbreiten: {breiten}"

    def test_ohne_treffer_wird_die_beste_variante_beziffert(self) -> None:
        v = Vergleich(
            leitern={
                "unbegrenzt": gestufte((0.0, 0.2569, 154), (0.5, 0.2600, 152)),
                "30 Kerzen": gestufte((0.0, 0.26, 154), (0.5, 0.28, 150)),
            }
        )
        urteil = v.urteil()

        assert "Keine Variante entkoppelt" in urteil
        assert "loest die Kopplung also nicht" in urteil

    def test_ohne_leitern_wird_nichts_behauptet(self) -> None:
        assert Vergleich().urteil() == "Nichts zu vergleichen."


class TestWelcheHaelfteRiss:
    """Der Urteilstext muss sagen, **woran** es lag.

    Der erste Anlauf meldete "Steigung 1,15 gegen die geforderten 0,5" und im
    selben Atemzug "keine Variante entkoppelt". Das liest sich wie ein
    Widerspruch und verschweigt den Grund: Die Steigung war erfuellt, die
    Stichprobe war weggebrochen.
    """

    def test_erfuellte_steigung_bei_weggebrochener_stichprobe(self) -> None:
        v = Vergleich(
            leitern={"20 Kerzen": gestufte((0.0, 0.26, 154), (0.35, 0.83, 17))}
        )
        urteil = v.urteil()

        assert "erreicht zwar eine Steigung" in urteil
        assert "11% der Trades" in urteil
        assert "anders verteilt" in urteil

    def test_verfehlte_steigung_wird_als_solche_gemeldet(self) -> None:
        v = Vergleich(
            leitern={"40 Kerzen": gestufte((0.0, 0.26, 154), (0.35, 0.27, 150))}
        )

        assert "gegen die geforderten" in v.urteil()
        assert "erreicht zwar" not in v.urteil()


class TestDieGueteRechnetMitDerEffektiven:
    """**Befund 176.** ``Stufe.guete`` rechnete mit der rohen Trade-Zahl.

    Das ist der Fehler, den Befund 139 an fuenf von sechs Stellen behoben hat
    - diese sechste ist durchgerutscht, ausgerechnet in dem Modul, das die
    folgenreichste Frage des Projekts beantwortet: *Liesse die Strecke
    ueberhaupt etwas durch?*

    Der Betrag: Bei 160 rohen und 107 effektiven Trades ist die rohe Guete um
    ``sqrt(160/107) = 1,22`` zu gross - 22 % zu freundlich, und zwar genau in
    der Spalte, an der die Leiter gelesen wird.
    """

    def test_die_rohe_zahl_gaebe_eine_zu_grosse_guete(self) -> None:
        echt = Stufe(0.0, 160, 1.47, 0.2649, 0.49, 7, 11, effektiv=107)

        assert echt.guete == pytest.approx(0.2649 * 107**0.5, rel=1e-9)
        assert echt.guete < 0.2649 * 160**0.5
        assert 0.2649 * 160**0.5 / echt.guete == pytest.approx(1.22, abs=0.01)

    def test_ohne_effektive_stichprobe_wird_verweigert(self) -> None:
        """**Nicht auf die rohe Zahl zurueckfallen.** Ein stiller Rueckfall
        waere zu freundlich, und niemandem waere es anzusehen - genau so ist
        der Fehler sechs Befunde lang stehengeblieben."""
        ohne = Stufe(0.0, 160, 1.47, 0.2649, 0.49, 7, 11)

        with pytest.raises(ValueError, match="Ohne effektive Stichprobe"):
            _ = ohne.guete

    def test_die_latte_steigt_wenn_die_stichprobe_faellt(self) -> None:
        """**Der bewegliche Teil, ohne den die Leiter falsch gelesen wird.**

        Ein gepflanzter Trend hebt den Vorteil je Trade und senkt zugleich die
        Trade-Zahl. Mit ihr steigt die Latte - und zwar schneller, als die
        Guete waechst.
        """
        viel = Stufe(0.0, 160, 1.47, 0.2649, 0.49, 7, 11, effektiv=107)
        wenig = Stufe(0.5, 12, 2.50, 1.2039, 0.0, 9, 11, effektiv=17)

        assert wenig.noetig(198) > viel.noetig(198)
        assert wenig.sharpe_je_trade > viel.sharpe_je_trade

    def test_ohne_stichprobe_gibt_es_keine_latte(self) -> None:
        assert Stufe(0.0, 160, 1.47, 0.26, 0.49, 7, 11).noetig(198) is None

    def test_die_tabelle_zeigt_beide_spalten(self) -> None:
        leiter = Leiter(
            versuche=198,
            stufen=[Stufe(0.0, 160, 1.47, 0.2649, 0.49, 7, 11, effektiv=107)],
        )
        text = leiter.tabelle()

        assert "n_eff" in text and "noetig" in text
        assert "107" in text


class TestDieZeitImMarkt:
    """**Befund 177.** Was einbricht, sind die Einstiege - nicht die Haltedauer.

    Befund 176 hat den Verfall der Stichprobe der Haltedauer zugeschrieben
    ("haelt laenger, handelt seltener"). Gemessen ist das Gegenteil: Die
    Haltedauer bleibt flach (Median 3, 4, 4, 2 Tage), die Einstiege fallen von
    158 auf 16 und die Zeit im Markt von 34,1 % auf 2,8 %.

    Die Spalte steht deshalb in der Leiter: Ohne sie liest man aus fallenden
    Trades das Falsche heraus, und genau das ist mir passiert.
    """

    def test_die_spalte_steht_in_der_tabelle(self) -> None:
        leiter = Leiter(
            versuche=198,
            stufen=[
                Stufe(0.0, 158, 1.47, 0.2649, 0.49, 7, 11,
                      effektiv=121, tage_im_markt=2250),
            ],
        )
        text = leiter.tabelle()

        assert "im Markt" in text
        assert "2250" in text

    def test_ohne_messung_steht_ein_strich(self) -> None:
        """Nicht raten: Wo die Zeit im Markt fehlt, steht kein Ersatz."""
        leiter = Leiter(
            versuche=198,
            stufen=[Stufe(0.0, 158, 1.47, 0.2649, 0.49, 7, 11, effektiv=121)],
        )

        assert "im Markt" in leiter.tabelle()

    def test_fallende_trades_bei_flacher_haltedauer_heissen_weniger_einstiege(
        self,
    ) -> None:
        """**Die Rechnung, die den Irrtum aufgedeckt haette.**

        Faellt die Zeit im Markt schneller als die Trade-Zahl, sind die Trades
        kuerzer geworden. Faellt sie **langsamer**, sind sie laenger geworden.
        Hier faellt beides fast im Gleichschritt - die Haltedauer bleibt also,
        und was fehlt, sind Einstiege.
        """
        viel = Stufe(0.0, 158, 1.47, 0.2649, 0.49, 7, 11,
                     effektiv=121, tage_im_markt=2250)
        wenig = Stufe(0.35, 16, 1.0, 0.6999, 0.0, 8, 11,
                      effektiv=15, tage_im_markt=186)

        halt_viel = viel.tage_im_markt / viel.trades
        halt_wenig = wenig.tage_im_markt / wenig.trades

        assert halt_wenig < halt_viel, "die Haltedauer ist nicht gewachsen"
        assert wenig.trades / viel.trades < 0.15, "die Einstiege sind eingebrochen"
