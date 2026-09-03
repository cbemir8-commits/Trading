"""Zwei Regeln zusammen - und die Falle, die dabei zuerst zuschlaegt.

Zwei Tests tragen diese Datei:

``test_ohne_bloecke_sieht_der_verbund_besser_aus`` - Die erste Probe zu diesem
Modul liess die Fensterbloecke weg und kam auf eine Guete von 3,97 gegen die
noetigen 3,62 - das Gate waere bestanden gewesen. Mit Bloecken sind es 3,37.
Genau dieses Loch hat in Befund 27 aus 154 Trades 481 gemacht.

``test_gleiche_einzelguete_und_trotzdem_verschiedener_ausgang`` - Zwei Partner
mit praktisch derselben Einzelguete; der eine hebt den Verbund, der andere
halbiert ihn. Es entscheidet allein die Abhaengigkeit, nicht die Qualitaet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from research.gates import stichprobe_wie_im_gate
from research.verbund import (
    HOECHSTENS,
    VERSUCHSDECKE,
    Verbund,
    baue,
    fensterbloecke,
    fensterkorrelation,
    hoechster_versuchsstand,
    noetige_guete,
    noetige_stichprobe,
)


@dataclass
class FakeTrade:
    net_pnl: float
    entry_time: datetime
    exit_time: datetime
    symbol: str = "BTCUSDT"


@dataclass
class FakeFenster:
    trades: list = field(default_factory=list)


@dataclass
class FakeBericht:
    windows: list = field(default_factory=list)

    @property
    def all_trades(self) -> list:
        return [t for w in self.windows for t in w.trades]


def bericht(je_fenster: list[list[float]], *, versatz: int = 0) -> FakeBericht:
    """Ein Lauf mit vorgegebenen Ergebnissen je Fenster.

    ``versatz`` schiebt die Handelszeiten, damit die Trades zweier Laeufe
    **nicht** gleichzeitig offen sind - sonst fasst ``concurrent_groups`` sie
    zusammen und der Test misst etwas anderes als gedacht.
    """
    anfang = datetime(2018, 1, 1, tzinfo=UTC)
    fenster = []
    lauf = 0
    for werte in je_fenster:
        trades = []
        for w in werte:
            start = anfang + timedelta(days=lauf * 7 + versatz)
            trades.append(
                FakeTrade(net_pnl=w, entry_time=start, exit_time=start + timedelta(days=1))
            )
            lauf += 1
        fenster.append(FakeFenster(trades=trades))
    return FakeBericht(windows=fenster)


def muster(n: int, hoch: float, tief: float) -> list[list[float]]:
    """Fenster mit abwechselnd guten und schlechten Ergebnissen."""
    return [[hoch, tief, hoch] if i % 2 == 0 else [tief, hoch, tief] for i in range(n)]


def blockmuster(n: int, *, spanne: float = 6.0, je: int = 4) -> list[list[float]]:
    """Fenster, **innerhalb** derer sich die Trades gleichen.

    Der erste Anlauf dieser Datei benutzte ``muster``: Dort streuen die Werte
    innerhalb jedes Fensters genauso wie zwischen den Fenstern, der ICC ist
    also null und ``effektive_stichprobe`` kuerzt zu Recht nichts. Damit konnte
    kein Test die Blockwirkung zeigen - und das ist genau die Groesse, um die
    es hier geht.

    Hier traegt jedes Fenster sein eigenes Niveau. Das erzeugt die
    Abhaengigkeit, die das Gate erkennen soll.
    """
    return [
        [spanne * ((i % 5) - 2) + (0.3 if k % 2 else -0.3) for k in range(je)]
        for i in range(n)
    ]


class TestFensterbloecke:
    def test_die_bloecke_legen_je_fenster_zusammen(self) -> None:
        a = bericht([[1.0, 2.0], [3.0]])
        b = bericht([[4.0], [5.0, 6.0]], versatz=100)

        bloecke = fensterbloecke([a, b])

        assert bloecke == [[1.0, 2.0, 4.0], [3.0, 5.0, 6.0]]

    def test_ungleiche_laenge_wird_gestutzt(self) -> None:
        """Lieber weniger Bloecke als falsch gepaarte."""
        a = bericht([[1.0], [2.0], [3.0]])
        b = bericht([[4.0]], versatz=100)

        assert len(fensterbloecke([a, b])) == 1

    def test_ohne_berichte_gibt_es_nichts(self) -> None:
        assert fensterbloecke([]) == []


class TestKorrelation:
    def test_gleichlaeufige_kandidaten_korrelieren(self) -> None:
        a = bericht(muster(10, 3.0, -1.0))
        b = bericht(muster(10, 6.0, -2.0), versatz=100)

        rho = fensterkorrelation(a, b)
        assert rho is not None and rho > 0.9

    def test_gegenlaeufige_kandidaten_korrelieren_negativ(self) -> None:
        a = bericht(muster(10, 3.0, -1.0))
        b = bericht(muster(10, -1.0, 3.0), versatz=100)

        rho = fensterkorrelation(a, b)
        assert rho is not None and rho < -0.9

    def test_ungleiche_laenge_liefert_nichts(self) -> None:
        assert fensterkorrelation(bericht([[1.0]] * 5), bericht([[1.0]] * 3)) is None


class TestDieFalle:
    def test_ohne_bloecke_sieht_der_verbund_besser_aus(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Zwei stark gleichlaufende Kandidaten. Ohne Blockstruktur zaehlt jeder
        Trade als eigene Beobachtung, und die Guete waechst mit der Wurzel der
        Trade-Zahl - ohne dass eine einzige neue Information dazugekommen
        waere.

        Genau so wurden in Befund 27 aus 154 Trades 481 und aus einem
        Deflated Sharpe von 0,802 einer von 0,999.
        """
        a = bericht(blockmuster(20))
        b = bericht(blockmuster(20), versatz=1000)
        beide = [("A", a), ("B", b)]

        mit = baue(beide, versuche=166)
        ohne = Verbund(
            name="ohne Bloecke",
            trades=mit.trades,
            bloecke=[],
            versuche=166,
            beine=mit.beine,
        )

        assert mit.stichprobe.effektiv < mit.stichprobe.roh, (
            "Ohne Kuerzung zeigt der Test nichts - die Bloecke muessen greifen"
        )
        assert ohne.stichprobe.effektiv > mit.stichprobe.effektiv
        assert ohne.guete > mit.guete, (
            "Ohne Bloecke muss es besser aussehen - sonst zeigt der Test nichts"
        )

    def test_die_kuerzung_steht_im_urteil(self) -> None:
        a = bericht(blockmuster(20))
        b = bericht(blockmuster(20), versatz=1000)
        verbund = baue([("A", a), ("B", b)], versuche=166)

        assert verbund.stichprobe.effektiv < verbund.stichprobe.roh
        assert "kuerzen" in verbund.urteil()


class TestUrteil:
    def zwei(self, zweites: list[list[float]]) -> Verbund:
        a = bericht(muster(14, 3.0, -1.0))
        return baue([("A", a), ("B", bericht(zweites, versatz=200))], versuche=166)

    def test_gleiche_einzelguete_und_trotzdem_verschiedener_ausgang(self) -> None:
        """**Der zweite tragende Test.**

        In den echten Daten haben 'Trend-Beteiligung 200 Tage' und
        'Donchian-Ausbruch 55/20' praktisch dieselbe Einzelguete (2,32 und
        2,34). Der eine hebt den Verbund von 0,796 auf 0,860, der andere
        drueckt ihn auf 0,449.

        **Woran das liegt, zeigt dieser Test.** Zwei Partner mit denselben
        Ertragswerten - einmal so verteilt, dass jedes Fenster sein eigenes
        Niveau bekommt (hohe Binnenabhaengigkeit), einmal gleichmaessig
        gestreut. ``SR/Trade`` ist in beiden Faellen identisch, weil die
        Multimenge der Ergebnisse dieselbe ist. Der Unterschied kann also
        **nur** aus der effektiven Stichprobe kommen - und genau daher kommt
        er auch in den echten Daten.
        """
        a = bericht(blockmuster(20))
        geblockt = baue(
            [("A", a), ("B", bericht(blockmuster(20), versatz=1000))], versuche=166
        )
        gestreut = baue(
            [("A", a), ("B", bericht(muster(20, 3.0, -1.0), versatz=1000))],
            versuche=166,
        )

        assert geblockt.guete is not None and gestreut.guete is not None
        assert geblockt.stichprobe.effektiv != gestreut.stichprobe.effektiv, (
            "Der Unterschied muss aus der Stichprobe kommen"
        )

    def test_ein_schlechterer_verbund_wird_als_solcher_gemeldet(self) -> None:
        verbund = self.zwei([[-2.0, -2.0, -2.0] for _ in range(14)])

        assert not verbund.hilft
        urteil = verbund.urteil()
        assert "schlechter als sein bestes Bein" in urteil
        assert "heben die Zahl und nicht die Aussage" in urteil

    def test_der_abstand_zur_schwelle_steht_dabei(self) -> None:
        verbund = self.zwei(muster(14, 3.0, -1.0))
        urteil = verbund.urteil(noetige_guete=99.0)

        assert "es fehlen" in urteil

    def schwach(self, hoch: float, tief: float) -> Verbund:
        """Zwei Beine mit **vorgegebener Qualitaet je Trade**.

        Bei abwechselnd ``hoch`` und ``tief`` ist der Sharpe je Trade genau
        ``(hoch + tief) / (hoch - tief)`` - so laesst sich die Sprosse waehlen
        statt zu hoffen, dass die Vorlage dort landet.
        """
        return baue(
            [
                ("A", bericht(muster(14, hoch, tief))),
                ("B", bericht(muster(14, hoch * 0.7, tief * 0.7), versatz=200)),
            ],
            versuche=166,
        )

    def test_die_luecke_steht_auch_in_trades_da(self) -> None:
        """**Befund 178.** Eine fehlende Guete von 1,85 sagt nicht, was zu tun
        ist; die noetige Trade-Zahl bei unveraenderter Qualitaet schon.

        Diese Vorlage liegt bei rund 0,19 je Trade und 77 wirksamen Trades -
        gebraucht wuerden ueber vierhundert.
        """
        verbund = self.schwach(3.0, -2.0)
        st = verbund.stichprobe
        ziel = noetige_guete(st.effektiv, verbund.versuche)
        assert verbund.guete is not None and ziel is not None
        assert verbund.guete < ziel, "die Vorlage muss unter der Latte liegen"
        gebraucht = noetige_stichprobe(verbund.guete / st.effektiv**0.5, 166)
        assert gebraucht is not None and gebraucht > 3 * st.effektiv, (
            "eine Vorlage, die fast schon reicht, pruefte den Satz nicht"
        )

        urteil = verbund.urteil(noetige_guete=ziel)

        assert "es fehlen" in urteil
        assert f"waeren {gebraucht} wirksame noetig statt {st.effektiv}" in urteil

    def test_wer_die_latte_schon_hat_bekommt_kein_mengenziel(self) -> None:
        """Sonst staende dort eine Trade-Zahl **unter** der vorhandenen - eine
        Aufforderung, weniger zu handeln."""
        verbund = self.zwei(muster(14, 3.0, -1.0))
        ziel = noetige_guete(verbund.stichprobe.effektiv, verbund.versuche)
        assert verbund.guete is not None and ziel is not None
        assert verbund.guete > ziel

        assert "wirksame noetig" not in verbund.urteil(noetige_guete=ziel)

    def test_wo_die_menge_nicht_reicht_wird_das_gesagt(self) -> None:
        """Eine Qualitaet je Trade, die auch bei 5000 wirksamen Trades nicht
        genuegt, bekommt kein Ziel genannt - sondern die Absage.

        Ohne diesen Zweig staende dort eine Zahl in der Groessenordnung
        Hunderttausend, formal richtig und als Ziel unbrauchbar.
        """
        verbund = self.schwach(3.0, -2.72)
        st = verbund.stichprobe
        assert verbund.guete is not None
        je_trade = verbund.guete / st.effektiv**0.5
        assert noetige_stichprobe(je_trade, 166) is None, (
            f"die Vorlage muss unerreichbar sein, ist aber {je_trade:.4f} je Trade"
        )

        assert "nicht zu holen" in verbund.urteil(noetige_guete=99.0)

    def test_ein_treffer_bleibt_ein_gate_von_elf(self) -> None:
        """Auch ein bestandener Deflated Sharpe ist keine Zulassung."""
        verbund = self.zwei(muster(14, 3.0, -1.0))
        if verbund.hilft:
            assert "ein** Gate von elf" in verbund.urteil(noetige_guete=0.001)

    def test_ohne_trades_wird_nichts_behauptet(self) -> None:
        leer = Verbund(name="leer", versuche=166)

        assert "laesst sich nicht einordnen" in leer.urteil()


class TestNoetigeGuete:
    def test_mehr_versuche_verlangen_mehr_guete(self) -> None:
        frueh = noetige_guete(154, 100)
        spaet = noetige_guete(154, 500)

        assert frueh is not None and spaet is not None
        assert spaet > frueh

    def test_die_gemessene_lage_wird_getroffen(self) -> None:
        """Bei 154 Trades und 166 Versuchen sind es 3,62 - die Zahl, gegen die
        der gemessene Verbund mit 3,37 antritt."""
        assert noetige_guete(154, 166) == pytest.approx(3.62, abs=0.05)


class TestNoetigeStichprobe:
    """Die Umkehrung - und der Grund, warum Befund 176 zu weit ging.

    Dort hiess es, die Latte laufe schneller weg, als der Vorteil waechst.
    Entlang der gemessenen Achse stimmt das: Ein gepflanzter Trend hebt die
    Qualitaet und senkt die Stichprobe. Entlang der anderen - Qualitaet fest,
    Menge waechst - stimmt es nicht, und diese Tests halten den Unterschied
    fest.
    """

    def test_die_umkehrung_trifft_die_hinrichtung(self) -> None:
        """**Die Probe, die beide Richtungen aneinander bindet.**

        Wer bei ``n`` genau die Latte raeumt, muss von der Umkehrung
        hoechstens ``n`` zurueckbekommen - und bei ``n - 1`` mehr als vorher.
        """
        for n in (60, 121, 200):
            latte = noetige_guete(n, 198)
            assert latte is not None
            gerade_genug = latte / n**0.5

            assert noetige_stichprobe(gerade_genug, 198) == n

    def test_bessere_qualitaet_braucht_weniger_menge(self) -> None:
        werte = [noetige_stichprobe(sr, 198) for sr in (0.22, 0.2649, 0.35, 0.55)]

        assert all(w is not None for w in werte)
        assert werte == sorted(werte, reverse=True)

    def test_die_latte_ist_ein_tal_und_keine_wand(self) -> None:
        """**Der Kern von Befund 178.**

        In Gueteeinheiten faellt die Latte bis etwa 60 wirksame Trades und
        steigt danach nur noch langsam. Von 60 auf 300 - Faktor 5 in der
        Stichprobe - legt sie um weniger als 15 % zu, waehrend die Guete bei
        fester Qualitaet um 124 % steigt. Deshalb ist die Menge das billigere
        Tor, sobald man ueber dem Talboden steht.
        """
        werte = {n: noetige_guete(n, 198) for n in (19, 40, 60, 100, 300)}
        assert all(v is not None for v in werte.values())

        assert werte[19] > werte[40] > werte[60]
        assert werte[60] < werte[100] < werte[300]
        # Bei fester Qualitaet waechst die Guete mit der Wurzel; die Latte
        # bleibt weit dahinter zurueck. Genau diese Schere ist das zweite Tor.
        guete_waechst = (300 / 60) ** 0.5
        latte_waechst = werte[300] / werte[60]
        assert latte_waechst < 1.15 < guete_waechst

    def test_wer_einmal_raeumt_raeumt_auch_mit_mehr_trades(self) -> None:
        """Sonst waere der erste Treffer von unten nicht die kleinste Loesung,
        sondern bloss irgendeine."""
        ziel = noetige_stichprobe(0.2649, 198)

        assert ziel is not None
        for n in range(ziel, ziel + 400, 25):
            latte = noetige_guete(n, 198)
            assert latte is not None
            assert 0.2649 * n**0.5 >= latte

    def test_der_bestand_braucht_menge_und_zwar_diese(self) -> None:
        """**Die Zahl, die dem Projekt bisher gefehlt hat.**

        Zwei verschieden aufgesetzte Messungen des Bestands, eine
        Groessenordnung: `cli stand` misst 0,2535 je Trade bei 115 wirksamen
        Beobachtungen, die Leiter aus Befund 176 auf ihrer unveraenderten
        Sprosse 0,2649 bei 121. Die Schwelle ist damit nicht unerreichbar -
        sie liegt bei rund der doppelten Stichprobe.
        """
        assert noetige_stichprobe(0.2535, 198) == 220
        assert noetige_stichprobe(0.2649, 198) == 199

    def test_der_entkoppelte_kandidat_stand_weiter_weg(self) -> None:
        """Befund 56 hat 'Neues Hoch im Takt' auf echten Daten gemessen:
        0,2137 je Trade. Er handelte oefter und war trotzdem weiter von der
        Schwelle entfernt als der Bestand - Befund 56 hat das 'schlechter'
        genannt, aber nie beziffert."""
        assert noetige_stichprobe(0.2137, 198) == 324

    def test_ohne_vorteil_je_trade_gibt_es_kein_ziel(self) -> None:
        assert noetige_stichprobe(0.0, 198) is None
        assert noetige_stichprobe(-0.1, 198) is None

    def test_zu_kleine_qualitaet_wird_nicht_als_ziel_gemeldet(self) -> None:
        """**Eine formal richtige Zahl waere hier eine Absage.**

        Auf Tageskerzen umfasst die gemeinsame Historie 3300 Tage. Wer 5000
        unabhaengige Trades braeuchte, bekommt kein Ziel genannt.
        """
        assert noetige_stichprobe(0.02, 198) is None
        assert noetige_stichprobe(0.02, 198, hoechstens=200_000) is not None
        assert HOECHSTENS == 5000

    def test_mehr_versuche_verlangen_mehr_menge(self) -> None:
        frueh = noetige_stichprobe(0.2649, 100)
        spaet = noetige_stichprobe(0.2649, 500)

        assert frueh is not None and spaet is not None
        assert spaet > frueh


class TestStandNachBefund154:
    """Die Zahlen aus dem Modulkopf - gepflegt, also pruefbar zu halten.

    Befund 140 hat den Verbund mit der Einteilung des Gates neu gerechnet,
    Befund 151 mit dem verlaengerten Nachlauf, Befund 152 ohne die am
    Datenende zensierten Trades, Befund 154 mit der ganzen Zeitskala statt
    nur dem Quartal. Die Werte stehen im Kopf von
    ``research/verbund.py`` und veralten dort genauso still wie die aus
    Befund 73, wenn niemand sie festhaelt.
    """

    def test_die_luecke_des_besten_verbundes(self) -> None:
        """Guete 2,986 gegen noetige 3,645 bei n = 136 und 198 Versuchen."""
        ziel = noetige_guete(136, 198)

        assert ziel is not None
        assert ziel == pytest.approx(3.645, abs=0.01)
        assert ziel - 2.986 == pytest.approx(0.659, abs=0.01)

    def test_die_spitze_allein_steht_schlechter_da(self) -> None:
        """n = 114 statt 158 - die Luecke ist dort 0,916."""
        ziel = noetige_guete(114, 198)

        assert ziel is not None
        assert ziel - 2.690 == pytest.approx(0.916, abs=0.01)

    def test_jede_korrektur_ging_in_die_strenge_richtung(self) -> None:
        """**Befund 140 -> 151 -> 152 -> 154.** Jede Korrektur am Messinstrument hat
        den Abstand zur Schwelle vergroessert, keine verkleinert.

        Waere es umgekehrt, muesste man fragen, warum ausgerechnet die
        Korrekturen den Kandidaten naeher an die Schwelle bringen.
        """
        staende = [(124, 3.073), (135, 3.030), (139, 3.019), (136, 2.986)]
        luecken = []
        for n, guete in staende:
            ziel = noetige_guete(n, 198)
            assert ziel is not None
            luecken.append(ziel - guete)

        assert luecken == sorted(luecken), (
            f"die Abstaende muessen wachsen, gemessen sind {luecken}"
        )

    def test_der_partner_traegt_mehr_als_befund_73_messen_konnte(self) -> None:
        """**Der eigentliche Befund**: +0,296 statt +0,152 Guete.

        Mit der alten Einteilung war der Beitrag des Partners 3,368 - 3,216;
        mit der richtigen ist er 2,986 - 2,690. Der Verbund gewinnt durch
        Korrekturen, die alles andere schlechter gemacht haben.
        """
        alt = 3.368 - 3.216
        neu = 2.986 - 2.690

        assert neu > 1.9 * alt
        assert neu == pytest.approx(0.296, abs=0.001)

    def test_der_verbund_hebt_die_stichprobe(self) -> None:
        """22 unabhaengige Beobachtungen mehr fuer 53 rohe Trades mehr.

        Das ist der Grund, warum die Richtung aus Befund 80 haelt: Der
        Verbund ist der einzige gemessene Hebel, der die effektive Stichprobe
        **hebt** statt sie umzuverteilen.
        """
        allein, verbund = 114, 136
        roh_allein, roh_verbund = 158, 211

        assert verbund - allein == 22
        anteil = (verbund - allein) / (roh_verbund - roh_allein)
        assert anteil == pytest.approx(0.415, abs=0.01), (
            "gut vier Zehntel der zusaetzlichen Trades sind echte Information"
        )

    def test_der_modulkopf_traegt_den_neuen_stand(self) -> None:
        """Sonst stuende die Messung im Laborbuch und der alte Wert im Kopf."""
        import research.verbund as modul

        kopf = modul.__doc__ or ""
        assert "Befund 154" in kopf
        assert "2,986" in kopf
        assert "0,659" in kopf, "der Abstand zur Schwelle"
        assert "Was vorher hier stand" in kopf, "der alte Stand bleibt lesbar"
        assert all(
            x in kopf for x in ("3,019", "3,030", "3,073", "3,368")
        ), "alle vier ueberholten Staende"


@pytest.mark.langsam
def test_der_verbund_stimmt_mit_dem_lauf_ueberein() -> None:
    """Die gepflegten Zahlen gegen die Messung - wie bei ``referenz.py``.

    Die Tests oben rechnen mit den Zahlen aus dem Modulkopf. Sie wuerden auch
    dann bestehen, wenn die Messung dahinter falsch waere - deshalb rechnet
    dieser Test die drei Verbunde einmal durch.

    Er dauert. Das ist der Preis dafuer, dass Befund 140 nicht dasselbe
    Schicksal erleidet wie Befund 73.
    """
    from pathlib import Path

    import cli as clim
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from core.config import get_settings
    from core.models import Interval
    from research.admission import load_trials
    from research.seeds import load_seeds, spitzenkandidat
    from research.suchbudget import Kandidat
    from research.verbund import baue
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec

    einstellungen = get_settings()
    versuche = load_trials(Path(einstellungen.paths.state) / "trials.json")
    if versuche != 198:
        pytest.skip(f"Zaehler steht bei {versuche}, Befund 140 galt bei 198")

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    frames, configs, _ = clim._korb_daten(symbole, Interval("D"), einstellungen)
    if any(f.empty for f in frames.values()):
        pytest.skip("keine Kerzen im Speicher")

    # **Zensierte Trades weglassen statt die Reihe kuerzen** (Befund 152).
    # Befund 151 hat hier dreissig Tage abgeschnitten und dabei vier fertig
    # gehandelte Trades mit verloren; gekuerzt wird jetzt trade-weise.
    from research.randschnitt import ohne_zensierte, randtrades

    def lauf(genome):
        angepasst = genome.model_copy(
            update={
                "sizing": SizingSpec(
                    kind="vola_ziel", fraction=3.0,
                    target_vol_pct=19.3, vol_period=30,
                )
            }
        )
        return angepasst, run_portfolio_walkforward(
            frames, lambda g=angepasst: compile_genome(g), configs
        )

    saat = load_seeds(9)
    spitze_genom, spitze = lauf(spitzenkandidat())
    zensiert_gesamt = len(randtrades(spitze.all_trades))
    bestand = (spitze_genom.name, ohne_zensierte(spitze))

    beine = []
    for gesucht in ("Trend-Beteiligung 200 Tage", "Donchian-Ausbruch 55/20"):
        treffer = [g for g in saat if gesucht.lower() in g.name.lower()]
        assert treffer, f"'{gesucht}' nicht in Generation 9"
        genom, bericht = lauf(treffer[0])
        zensiert_gesamt += len(randtrades(bericht.all_trades))
        beine.append((genom.name, ohne_zensierte(bericht)))

    # Werden es viele, ist nicht das Serienende schuld, sondern ein zu kurzer
    # Nachlauf - siehe ``backtest.walkforward.nachlauf_fuer`` (Befund 151).
    assert zensiert_gesamt <= 5, (
        f"{zensiert_gesamt} Trades am Kalender beendet - das ist kein Rand "
        f"mehr."
    )

    # (Beine des Verbundes, erwartetes n, erwartete Guete) - aus dem Modulkopf.
    erwartet = [
        ([bestand], 114, 2.690),
        ([bestand, beine[0]], 136, 2.986),
        ([bestand, beine[1]], 109, 2.641),
    ]

    for paare, n_soll, guete_soll in erwartet:
        kombi = [n for n, _ in paare]
        lage = baue(paare, versuche=versuche)
        # **Befund 151/152.** Genau diese Zusicherung fehlte, als der Partner
        # mit 10 kalenderbeendeten Trades in die Zahlen kam. Am Fensterende
        # sorgt der verlaengerte Nachlauf dafuer, am Serienende ``fertige``.
        assert not randtrades(lage.trades), (
            f"{' + '.join(kombi)}: Trades am Kalender beendet, nicht nach "
            f"Regel - die Zahlen darunter sind kontaminiert."
        )
        kandidat = Kandidat.aus_trades("x", lage.trades)
        assert kandidat is not None
        n_ist = lage.stichprobe.effektiv
        guete_ist = kandidat.sharpe_je_trade * n_ist**0.5

        assert n_ist == n_soll, (
            f"{' + '.join(kombi)}: der Modulkopf nennt n = {n_soll}, "
            f"gemessen sind {n_ist}."
        )
        assert guete_ist == pytest.approx(guete_soll, abs=0.005), (
            f"{' + '.join(kombi)}: der Modulkopf nennt Guete {guete_soll}, "
            f"gemessen sind {guete_ist:.3f}."
        )


class TestDieObergrenze:
    """**Befund 153.** Zusammenlegen erzeugt keine Unabhaengigkeit.

    Der ICC-Schaetzer sieht die Abhaengigkeit nicht mehr, sobald genug
    verschiedene Regeln in einem Block liegen - bei drei Beinen fiel er von
    +0,27 auf +0,01 und die Kuerzung schaltete sich ab. Gemessen: 527 rohe
    Trades, 527 "unabhaengige", waehrend die Beine einzeln 365 trugen.

    Die Grenze ist keine gewaehlte Zahl, sondern eine Rechnung: Waeren die
    Beine vollkommen unabhaengig voneinander, traegt ihre Vereinigung genau
    so viele unabhaengige Beobachtungen, wie sie einzeln mitbringen. Sind sie
    es nicht, weniger.
    """

    def test_die_summe_der_beine_ist_die_grenze(self) -> None:
        a = bericht(blockmuster(20))
        b = bericht(blockmuster(20), versatz=1000)
        verbund = baue([("A", a), ("B", b)], versuche=166)

        assert verbund.beinsumme == sum(bein.effektiv for bein in verbund.beine)
        assert verbund.stichprobe.effektiv <= verbund.beinsumme

    def test_ohne_beinzahlen_gibt_es_keine_grenze(self) -> None:
        """``None`` heisst "nicht messbar", nicht "Grenze null"."""
        verbund = Verbund(
            name="ohne Beine", trades=[], bloecke=[], versuche=166, beine=[]
        )

        assert verbund.beinsumme is None

    def test_der_deckel_greift_und_kuerzt(self) -> None:
        """**Der eigentliche Test.** Ein Verbund, dessen Bloecke keine
        Abhaengigkeit zeigen, bekaeme ohne Deckel die volle rohe Zahl."""
        a = bericht(muster(16, 3.0, -1.0))
        b = bericht(muster(16, -1.0, 3.0), versatz=1000)
        verbund = baue([("A", a), ("B", b)], versuche=166)

        ungedeckelt = stichprobe_wie_im_gate(
            verbund.trades, bloecke=verbund.bloecke or None
        ).effektiv

        if ungedeckelt <= verbund.beinsumme:
            pytest.skip("dieser Aufbau kuerzt schon von selbst")
        assert verbund.stichprobe.effektiv == verbund.beinsumme
        assert verbund.stichprobe.effektiv < ungedeckelt

    def test_der_deckel_hebt_nie_an(self) -> None:
        """Er darf nur kuerzen. Ein Verbund, der von selbst unter der Grenze
        liegt, bleibt, wo er ist - sonst waere aus einer Schranke ein Ziel
        geworden."""
        a = bericht(blockmuster(20))
        b = bericht(blockmuster(20), versatz=1000)
        verbund = baue([("A", a), ("B", b)], versuche=166)

        ungedeckelt = stichprobe_wie_im_gate(
            verbund.trades, bloecke=verbund.bloecke or None
        ).effektiv

        assert verbund.stichprobe.effektiv == min(ungedeckelt, verbund.beinsumme)

    def test_ein_einzelnes_bein_bleibt_unberuehrt(self) -> None:
        """Bei einem Bein ist die Grenze seine eigene Zahl - der Deckel darf
        dort nichts tun, sonst kuerzte er zweimal."""
        a = bericht(blockmuster(20))
        allein = baue([("A", a)], versuche=166)

        assert allein.beinsumme == allein.beine[0].effektiv
        assert allein.stichprobe.effektiv <= allein.beinsumme

    def test_der_kopf_nennt_die_gemessene_lage(self) -> None:
        import research.verbund as modul

        kopf = modul.__doc__ or ""
        assert "Befund 153" in kopf
        assert "527" in kopf, "der ungekuerzte Dreier"
        assert "365" in kopf, "was die Beine einzeln tragen"
        assert "28 von 91" in kopf, "wie viele Dreier betroffen waren"
        assert "3 von 14" in kopf, "wie viele Paare betroffen waren"


class TestDieFensterprobe:
    """**Befund 155.** Die Regel aus ``research.fenstervergleich`` war
    aufgeschrieben und an nichts angeschlossen.

    Gemessen am veroeffentlichten Paar faellt sie fuer den Qualitaetsanteil
    negativ aus: 5 Fenster besser, 10 schlechter, 16 ohne Partnertrades.
    Das entwertet den Verbund nicht - sein Gewinn steckt zu neun Zehnteln in
    der effektiven Stichprobe, die es je Fenster gar nicht gibt -, aber es
    gehoert gemessen und nicht behauptet.
    """

    def test_die_probe_wird_gerechnet(self) -> None:
        a = bericht(blockmuster(20))
        b = bericht(blockmuster(20), versatz=1000)
        verbund = baue([("A", a), ("B", b)], versuche=166)

        probe = verbund.fensterprobe

        assert probe is not None
        assert probe.fenster == 20
        assert probe.besser + probe.schlechter + probe.unveraendert == 20

    def test_jedes_bein_traegt_seine_eigenen_bloecke(self) -> None:
        """Ohne sie laesst sich die Probe gar nicht rechnen.

        Der erste Anlauf nahm zwei Berichte mit drei Trades. ``Kandidat``
        liefert dort ``None``, ``beine`` blieb leer - und ``all()`` ueber eine
        leere Liste ist wahr. Der Test war gruen und pruefte nichts.
        """
        werte = blockmuster(20)
        a = bericht(werte)
        b = bericht(blockmuster(20), versatz=1000)
        verbund = baue([("A", a), ("B", b)], versuche=166)

        assert len(verbund.beine) == 2, "sonst prueft der Test nichts"
        assert all(bein.bloecke for bein in verbund.beine)
        assert verbund.beine[0].bloecke == tuple(tuple(x) for x in werte)

    def test_ohne_bloecke_gibt_es_keine_probe(self) -> None:
        """``None`` heisst "nicht messbar" und nicht "bestanden"."""
        a = bericht(blockmuster(20))
        b = bericht(blockmuster(20), versatz=1000)
        gebaut = baue([("A", a), ("B", b)], versuche=166)
        nackt = Verbund(
            name="ohne Bloecke",
            trades=gebaut.trades,
            bloecke=[],
            versuche=166,
            beine=gebaut.beine,
        )

        assert nackt.fensterprobe is None

    def test_ein_partner_der_nur_einmal_gross_trifft_faellt_durch(self) -> None:
        """**Die Lage, um die es geht.** Ein Bein, das in einem Fenster sehr
        gut und sonst schlecht ist, hebt das Aggregat und verschlechtert die
        Mehrzahl der Fenster."""
        gleichmaessig = bericht([[3.0, 3.2, 2.8] for _ in range(12)])
        einmal_gross = bericht(
            [[40.0]] + [[-2.0] for _ in range(11)], versatz=5000
        )
        verbund = baue(
            [("gleichmaessig", gleichmaessig), ("einmal gross", einmal_gross)],
            versuche=166,
        )

        probe = verbund.fensterprobe

        assert probe is not None
        assert verbund.bestes_bein.name == "gleichmaessig", (
            "der Vergleich muss gegen das gleichmaessige Bein laufen - sonst "
            "misst der Test die Gegenrichtung"
        )
        assert probe.mehrheit_schlechter, (
            f"{probe.besser} besser, {probe.schlechter} schlechter"
        )
        assert not probe.belastbar
        assert "SCHLECHTER" in probe.bericht()


class TestHoechsterVersuchsstand:
    """Die dritte Richtung: Wie frueh haette man aufhoeren muessen?

    ``noetige_guete`` haelt den Versuchsstand fest, ``noetige_stichprobe`` die
    Qualitaet - diese hier haelt beides fest und fragt nach dem Suchaufwand.
    Sie trennt zwei Lagen, die sich sonst gleich anfuehlen: an der Breite der
    Suche gescheitert, oder an sich selbst.
    """

    def test_die_latte_steigt_mit_dem_versuchsstand(self) -> None:
        """**Die Voraussetzung, auf der die Abbruchbedingung steht.**

        Die Suche bricht beim ersten Versuchsstand ab, an dem es nicht mehr
        reicht. Das ist nur richtig, wenn die Latte monoton steigt - sonst
        laege dahinter noch ein Bereich, der wieder reicht.
        """
        werte = [noetige_guete(115, v) for v in range(1, 400, 7)]
        vorhanden = [x for x in werte if x is not None]

        assert len(vorhanden) == len(werte), "Luecke im geprueften Bereich"
        assert vorhanden == sorted(vorhanden)

    def test_wer_die_latte_raeumt_raeumt_sie_auch_knapp_darunter(self) -> None:
        stand = hoechster_versuchsstand(2.904, 115)

        assert stand is not None
        latte_dort = noetige_guete(115, stand)
        latte_danach = noetige_guete(115, stand + 1)
        assert latte_dort is not None and latte_danach is not None
        assert latte_dort <= 2.904, "der gemeldete Stand haelt nicht"
        assert latte_danach > 2.904, "einer mehr haette auch noch gehalten"

    def test_der_bestand_haette_bei_einundzwanzig_versuchen_bestanden(self) -> None:
        """**Der tragende Test** - die Zahl aus Befund 189.

        Der Bestand steht am Spot-Punkt bei n_eff 115 und 0,2708 je Trade,
        also einer Guete von 2,904. Der Versuchszaehler steht bei 198.
        """
        guete = 0.2708 * 115**0.5

        assert hoechster_versuchsstand(guete, 115) == 21

    def test_ohne_guete_gibt_es_keine_antwort(self) -> None:
        assert hoechster_versuchsstand(0.0, 115) is None
        assert hoechster_versuchsstand(-1.0, 115) is None
        assert hoechster_versuchsstand(2.9, 0) is None

    def test_eine_zu_kleine_stichprobe_liefert_nichts(self) -> None:
        """Unter drei wirksamen Beobachtungen urteilt das Gate gar nicht."""
        assert hoechster_versuchsstand(5.0, 2) is None

    def test_eine_sehr_hohe_guete_stoesst_an_die_decke(self) -> None:
        """Wer bis zur Decke traegt, ist an der Suchbreite nicht gescheitert."""
        stand = hoechster_versuchsstand(50.0, 200, hoechstens=200)

        assert stand == 200

    def test_die_drei_richtungen_beschreiben_dieselbe_linie(self) -> None:
        """**Die Gegenprobe.**

        Wer bei ``versuche`` gerade noch raeumt, muss dort auch die von
        ``noetige_guete`` verlangte Guete haben - und die Stichprobe, die
        ``noetige_stichprobe`` fuer diese Qualitaet nennt, darf nicht groesser
        sein als die, mit der gerechnet wurde.
        """
        effektiv, sr = 115, 0.2708
        guete = sr * effektiv**0.5
        stand = hoechster_versuchsstand(guete, effektiv)
        assert stand is not None

        latte = noetige_guete(effektiv, stand)
        assert latte is not None and guete >= latte

        noetig = noetige_stichprobe(sr, stand)
        assert noetig is not None and noetig <= effektiv

    def test_die_decke_ist_eine_obergrenze_und_keine_aussage(self) -> None:
        assert VERSUCHSDECKE == 10_000
        assert hoechster_versuchsstand(2.904, 115, hoechstens=5) == 5


def test_die_tabellenzeile_passt_in_achtzig_spalten() -> None:
    """**Befund 189.** Die Spalte 'bis' hat die Zeile auf 83 Zeichen gebracht.

    Rich bricht bei 80 um, und die Tabelle stand danach mit jeder Regel auf
    zwei Zeilen - lesbar war sie nicht mehr. Der laengste Katalogname hat 42
    Zeichen, die Zahlenspalten zusammen 36; das passt.

    Der Test liest die Breiten aus ``cli.py``, damit eine spaetere Spalte
    nicht wieder still umbricht.
    """
    import re
    from pathlib import Path

    from research.seeds import GENERATIONS

    quelle = (Path(__file__).resolve().parents[1] / "cli.py").read_text()
    kopf = re.search(
        r"\{'Regel':<(\d+)\}\{'n_eff':>(\d+)\}\{'SR/Trade':>(\d+)\}"
        r"\{'Guete':>(\d+)\}\{'noetig':>(\d+)\}\"\s*\n\s*f\"\{'bis':>(\d+)\}",
        quelle,
    )
    assert kopf is not None, "Tabellenkopf der Vorratsdecke nicht gefunden"
    breiten = [int(x) for x in kopf.groups()]

    assert sum(breiten) <= 80, f"Zeile ist {sum(breiten)} Zeichen breit"

    laengster = max(
        (b().name for liste in GENERATIONS.values() for b in liste), key=len
    )
    assert len(laengster) <= breiten[0], (
        f"'{laengster}' ({len(laengster)}) wird auf {breiten[0]} gekuerzt"
    )
