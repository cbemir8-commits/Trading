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

from research.verbund import (
    Verbund,
    baue,
    fensterbloecke,
    fensterkorrelation,
    noetige_guete,
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


class TestStandNachBefund152:
    """Die Zahlen aus dem Modulkopf - gepflegt, also pruefbar zu halten.

    Befund 140 hat den Verbund mit der Einteilung des Gates neu gerechnet,
    Befund 151 mit dem verlaengerten Nachlauf, Befund 152 ohne die am
    Datenende zensierten Trades. Die Werte stehen im Kopf von
    ``research/verbund.py`` und veralten dort genauso still wie die aus
    Befund 73, wenn niemand sie festhaelt.
    """

    def test_die_luecke_des_besten_verbundes(self) -> None:
        """Guete 3,019 gegen noetige 3,650 bei n = 139 und 198 Versuchen."""
        ziel = noetige_guete(139, 198)

        assert ziel is not None
        assert ziel == pytest.approx(3.650, abs=0.01)
        assert ziel - 3.019 == pytest.approx(0.631, abs=0.01)

    def test_die_spitze_allein_steht_schlechter_da(self) -> None:
        """n = 114 statt 158 - die Luecke ist dort 0,916."""
        ziel = noetige_guete(114, 198)

        assert ziel is not None
        assert ziel - 2.690 == pytest.approx(0.916, abs=0.01)

    def test_jede_korrektur_ging_in_die_strenge_richtung(self) -> None:
        """**Befund 140 -> 151 -> 152.** Jede Korrektur am Messinstrument hat
        den Abstand zur Schwelle vergroessert, keine verkleinert.

        Waere es umgekehrt, muesste man fragen, warum ausgerechnet die
        Korrekturen den Kandidaten naeher an die Schwelle bringen.
        """
        staende = [(124, 3.073), (135, 3.030), (139, 3.019)]
        luecken = []
        for n, guete in staende:
            ziel = noetige_guete(n, 198)
            assert ziel is not None
            luecken.append(ziel - guete)

        assert luecken == sorted(luecken), (
            f"die Abstaende muessen wachsen, gemessen sind {luecken}"
        )

    def test_der_partner_traegt_mehr_als_befund_73_messen_konnte(self) -> None:
        """**Der eigentliche Befund**: +0,329 statt +0,152 Guete.

        Mit der alten Einteilung war der Beitrag des Partners 3,368 - 3,216;
        mit der richtigen ist er 3,019 - 2,690. Der Verbund gewinnt durch
        Korrekturen, die alles andere schlechter gemacht haben.
        """
        alt = 3.368 - 3.216
        neu = 3.019 - 2.690

        assert neu > 2 * alt
        assert neu == pytest.approx(0.329, abs=0.001)

    def test_der_verbund_hebt_die_stichprobe(self) -> None:
        """25 unabhaengige Beobachtungen mehr fuer 53 rohe Trades mehr.

        Das ist der Grund, warum die Richtung aus Befund 80 haelt: Der
        Verbund ist der einzige gemessene Hebel, der die effektive Stichprobe
        **hebt** statt sie umzuverteilen.
        """
        allein, verbund = 114, 139
        roh_allein, roh_verbund = 158, 211

        assert verbund - allein == 25
        anteil = (verbund - allein) / (roh_verbund - roh_allein)
        assert anteil == pytest.approx(0.472, abs=0.01), (
            "knapp die Haelfte der zusaetzlichen Trades ist echte Information"
        )

    def test_der_modulkopf_traegt_den_neuen_stand(self) -> None:
        """Sonst stuende die Messung im Laborbuch und der alte Wert im Kopf."""
        import research.verbund as modul

        kopf = modul.__doc__ or ""
        assert "Befund 152" in kopf
        assert "3,019" in kopf
        assert "0,631" in kopf, "der Abstand zur Schwelle"
        assert "Was vorher hier stand" in kopf, "der alte Stand bleibt lesbar"
        assert "3,030" in kopf and "3,073" in kopf and "3,368" in kopf, (
            "alle drei ueberholten Staende"
        )


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
        ([bestand, beine[0]], 139, 3.019),
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
