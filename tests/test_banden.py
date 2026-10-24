"""'Entschieden' ist vorlaeufig, 'offen' nicht - Befund 402.

Befund 401 hat 'Bestaendigkeit' als knappstes Urteil benannt - 0,0806 Abstand
gegen 0,0645 Spanne, das 1,25-fache - und gesagt, wo nachzusehen ist: bei mehr
Aufteilungen. Nachgesehen, 31 Versaetze:

    Groesse               Abstand  Spanne 11  Spanne 31  Urteil 11    Urteil 31
    Bestaendigkeit         0,0806     0,0645     0,0968  entschieden  offen
    Deflated Sharpe        0,3674     0,0763     0,0980  entschieden  entschieden
    Schlechtestes Jahr     0,3900     0,9500     1,4400  offen        offen

Und es ist die Aufteilung, nicht der Reihenanfang: In Zehnerbanden
geschnitten, ist die groesste Spanne **innerhalb** einer Bande 0,0839 - schon
mehr als der Abstand -, waehrend die Drift zwischen den Bandenmitteln 0,0231
betraegt.

Die Gegenprobe, dass die Zerlegung trennt, steht bei 'Stichprobengroesse':
Dort ueberwiegt die Drift mit 101,9091 gegen 97,0000, und sie muss es - die
Zahl sind Tage im Markt, und die Reihe wird kuerzer.

Daraus die Asymmetrie: Eine Spanne ueber ``n`` Aufteilungen ist eine
**Untergrenze**. 'offen' ist damit monoton, 'entschieden' nicht.
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.aufteilung import (
    ENTSCHIEDEN,
    OFFEN,
    Bandenbild,
    banden,
    beurteile,
)

#: 'Bestaendigkeit' auf 31 Versaetzen (Befund 402).
BESTAENDIGKEIT = (
    0.5806, 0.6129, 0.6129, 0.5806, 0.5806, 0.6129, 0.5806, 0.5484, 0.5484,
    0.5806, 0.5806, 0.5484, 0.5806, 0.5806, 0.5806, 0.5484, 0.5484, 0.5484,
    0.5484, 0.5484, 0.5484, 0.5806, 0.5484, 0.5484, 0.5161, 0.5484, 0.5806,
    0.5484, 0.6000, 0.5484, 0.5484,
)


class TestDasKnappsteUrteilKippt:
    def test_auf_elf_aufteilungen_entschieden(self) -> None:
        spruch = beurteile(
            name="Bestaendigkeit",
            wert=0.5806,
            schwelle=0.5,
            werte=BESTAENDIGKEIT[:11],
        )

        assert spruch == ENTSCHIEDEN

    def test_auf_einunddreissig_offen(self) -> None:
        spruch = beurteile(
            name="Bestaendigkeit",
            wert=0.5806,
            schwelle=0.5,
            werte=BESTAENDIGKEIT,
        )

        assert spruch == OFFEN

    def test_die_spanne_waechst_mit_der_tiefe(self) -> None:
        """Der Grund fuer die Asymmetrie: Mehr Aufteilungen koennen eine
        Spanne nur vergroessern, nie verkleinern."""
        from research.aufteilung import streuung

        elf = streuung("x", BESTAENDIGKEIT[:11]).spanne
        alle = streuung("x", BESTAENDIGKEIT).spanne

        assert alle >= elf
        assert elf == pytest.approx(0.0645, abs=0.0001)
        assert alle == pytest.approx(0.0968, abs=0.0001)

    def test_offen_bleibt_offen(self) -> None:
        """Die monotone Haelfte - **ab** der Tiefe, bei der es kippt.

        Mein erster Entwurf hat hier zuviel behauptet: 'offen auf jeder
        Tiefe'. Das ist falsch, und zwar in dieselbe Richtung wie der ganze
        Befund - bei zwei Aufteilungen ist die Spanne winzig, also liest sich
        fast alles als entschieden. Monoton ist die Aussage erst von dem
        Punkt an, an dem sie einmal offen war.
        """
        jahr = (-9.61, -9.71, -9.51, -9.77, -10.02, -9.69, -10.17, -9.22, -9.9)

        def spruch(tiefe: int) -> str:
            return beurteile(
                name="Schlechtestes Jahr",
                wert=-9.61,
                schwelle=-10.0,
                werte=jahr[:tiefe],
            )

        tiefen = range(2, len(jahr) + 1)
        erste = next(t for t in tiefen if spruch(t) == OFFEN)

        assert erste == 5, "ab hier liegt -10,02 in der Reihe"
        assert all(spruch(t) == OFFEN for t in range(erste, len(jahr) + 1))
        assert spruch(2) == ENTSCHIEDEN, "davor sagt die Spanne zu wenig"

    def test_der_deflated_sharpe_haelt_auch_tiefer(self) -> None:
        """Das Wichtigste: Der Hauptblocker kippt nicht."""
        dsr = (0.5826, 0.6040, 0.6125, 0.5810, 0.6091, 0.6305, 0.5784,
               0.6261, 0.6002, 0.6410, 0.6547, 0.6678, 0.5698, 0.6400)

        assert (
            beurteile(
                name="Deflated Sharpe", wert=0.5826, schwelle=0.95, werte=dsr
            )
            == ENTSCHIEDEN
        )


class TestDieBandenzerlegung:
    def test_sie_trennt_innen_von_drift(self) -> None:
        bild = banden("Bestaendigkeit", BESTAENDIGKEIT)

        assert len(bild.bandenspannen) == 3, "31 Werte auf drei Banden: 11/10/10"
        assert bild.innen == max(bild.bandenspannen)
        assert bild.drift >= 0.0

    def test_bei_der_bestaendigkeit_ueberwiegt_die_aufteilung(self) -> None:
        bild = banden("Bestaendigkeit", BESTAENDIGKEIT)

        assert bild.ueberwiegt_die_aufteilung

    def test_bei_tagen_im_markt_die_drift(self) -> None:
        """Die Gegenprobe: Wo der Reihenanfang wirklich wandert, zeigt die
        Zerlegung es - die Tage im Markt schrumpfen mit der Reihe."""
        tage = tuple(2250.0 - 6.0 * i for i in range(31))

        bild = banden("Stichprobengroesse", tage)

        assert not bild.ueberwiegt_die_aufteilung
        assert bild.drift > bild.innen

    def test_alle_werte_kommen_in_eine_bande(self) -> None:
        """**Der Fehler, den dieser Befund an sich selbst gefunden hat.** Mit
        fester Breite elf fielen bei 31 Werten neun heraus - die mit der
        groessten Spanne."""
        for n in (25, 31, 33, 40):
            bild = banden("x", tuple(range(n)))

            assert len(bild.bandenspannen) == 3, n
            # Die Spannen zaehlen die Abstaende, also je Bande eins weniger
            # als Werte; drei Banden geben zusammen n - 3.
            assert sum(bild.bandenspannen) == n - 3, n

    def test_zu_wenige_werte_geben_keine_banden(self) -> None:
        with pytest.raises(ValueError, match="reichen nicht"):
            banden("x", (1.0, 2.0, 3.0, 4.0, 5.0))

    def test_eine_einzige_bande_trennt_nichts(self) -> None:
        with pytest.raises(ValueError, match="trennen nichts"):
            banden("x", tuple(range(20)), anzahl=1)

    def test_eine_konstante_reihe_streut_nicht(self) -> None:
        bild = banden("x", (5.0,) * 31)

        assert bild.innen == 0.0
        assert bild.drift == 0.0
        assert bild.ueberwiegt_die_aufteilung

    def test_der_kopf_nennt_die_gegenprobe(self) -> None:
        text = Bandenbild.__doc__ or ""

        assert "101,9091" in text
        assert "Gegenprobe" in text


class TestWasDerKopfVonBeurteileSagt:
    def test_er_nennt_die_asymmetrie(self) -> None:
        text = beurteile.__doc__ or ""

        assert '"offen" ist monoton' in text
        assert '"entschieden" ist es nicht' in text

    def test_und_dass_eine_spanne_eine_untergrenze_ist(self) -> None:
        text = beurteile.__doc__ or ""

        assert "Untergrenze" in text
        assert "0,0968" in text


class TestDerBefehlNenntDieTiefe:
    def test_in_der_ueberschrift(self) -> None:
        quelle = inspect.getsource(cli.aufteilung)

        assert "Ist das Urteil eines? (" in quelle
        assert "Aufteilungen)" in quelle

    def test_und_die_asymmetrie_darunter(self) -> None:
        quelle = inspect.getsource(cli.aufteilung)

        assert "'offen' bleibt offen" in quelle
        assert "Untergrenze (Befund 402)" in quelle

    def test_und_zeigt_die_zerlegung(self) -> None:
        from tests.quelltext import rumpf

        koerper = rumpf(cli.aufteilung)

        assert 'urteilstafel.add_column("innen/Drift"' in koerper
        assert "bild = banden(name, jegate[name])" in koerper

    def test_ohne_zwei_banden_steht_ein_strich(self) -> None:
        """Bei wenigen Versaetzen laesst sich nicht trennen, und dann wird
        nichts behauptet."""
        from tests.quelltext import rumpf

        koerper = rumpf(cli.aufteilung)

        assert "except ValueError:" in koerper
        assert 'zerlegt = "-"' in koerper


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_den_kipp(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 402)

        assert "0,0968" in eintrag.ergebnis
        assert "**acht**" in eintrag.ergebnis

    def test_und_dass_der_hauptblocker_haelt(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 402)

        assert "Deflated Sharpe bleibt" in eintrag.ergebnis
        assert "Dreieinhalbfache" in eintrag.ergebnis

    def test_und_die_zerlegung_mit_gegenprobe(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 402)

        assert "0,0839" in eintrag.ergebnis
        assert "0,0231" in eintrag.ergebnis
        assert "101,9091" in eintrag.ergebnis

    def test_und_die_asymmetrie(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 402)

        assert "Untergrenze" in eintrag.ergebnis
        assert "monoton" in eintrag.ergebnis

    def test_401_traegt_den_vermerk_und_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 401)

        assert "Vermerk aus 402" in eintrag.ergebnis
        assert "haengt an der Messtiefe" in eintrag.ergebnis
        assert eintrag.zuletzt == 402


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    def test_einunddreissig_aufteilungen_kippen_die_bestaendigkeit(self) -> None:
        """Der Kern des Befundes, am Lauf - 31 Walk-Forwards."""
        from pathlib import Path

        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.admission import load_trials
        from research.datenstand import alle_geschnitten
        from research.gates import evaluate_gates
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        e = get_settings()
        store = CandleStore(e.paths.data_store)
        versuche = load_trials(Path(e.paths.state) / "trials.json")
        roh = alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        genom = cli._ohne_hebel(spitzenkandidat())
        configs = cli._spotconfigs(symbole, e)

        werte: dict[str, list[float]] = {}
        gemeldet: dict[str, tuple[float, float]] = {}
        for weg in range(31):
            frames = common_range(
                {s: f.iloc[weg:].reset_index(drop=True) for s, f in roh.items()}
            )
            bericht = run_portfolio_walkforward(
                frames, lambda: compile_genome(genom), configs
            )
            gates = evaluate_gates(
                genom,
                bericht,
                next(iter(frames.values())),
                configs[symbole[0]],
                trials_so_far=versuche,
                frames=frames,
                configs=configs,
            )
            for r in gates.results:
                werte.setdefault(r.name, []).append(float(r.value))
                if weg == 0:
                    gemeldet[r.name] = (float(r.value), float(r.threshold))

        def spruch(name: str, tiefe: int) -> str:
            wert, schwelle = gemeldet[name]
            return beurteile(
                name=name, wert=wert, schwelle=schwelle, werte=werte[name][:tiefe]
            )

        assert spruch("Bestaendigkeit", 11) == ENTSCHIEDEN
        assert spruch("Bestaendigkeit", 31) == OFFEN
        assert spruch("Deflated Sharpe", 31) == ENTSCHIEDEN

        bild = banden("Bestaendigkeit", werte["Bestaendigkeit"])
        assert bild.ueberwiegt_die_aufteilung
        assert bild.innen > abs(
            gemeldet["Bestaendigkeit"][0] - gemeldet["Bestaendigkeit"][1]
        )

        tage = banden("Stichprobengroesse", werte["Stichprobengroesse"])
        assert not tage.ueberwiegt_die_aufteilung
