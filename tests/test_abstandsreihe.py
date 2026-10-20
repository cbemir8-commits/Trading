"""Der Abstand zum haertesten Gate stand auf dem Speicher - Befund 387.

``cli abstand`` beantwortet die Frage, die alles steuert: Was fehlt zum
Deflated Sharpe, und was kostet Weitersuchen? Gerechnet hat er auf dem
**Speicher**, der bis heute laeuft - nicht auf der Zulassungsreihe, auf der
jede gepflegte Zahl dieses Projekts steht.

Der Grund stand im Befehl selbst. Der Absatz zum Randschnitt sagt woertlich:

    Ohne das meldet dieses Werkzeug einen kleineren Abstand als das Gate, und
    zwar jedes Mal etwas anders, je nach Alter des Datenabzugs.

Derselbe Satz gilt fuer das **obere** Ende der Reihe, und dort war er nicht
angewandt. ``alle_geschnitten`` hat in Befund 363/364 acht Dateien bekommen,
diese nicht.

Gemessen am Spot-Punkt, BTC + ETH Tageskerzen:

    Reihe          DSR      Luecke   noetige Trades   fehlende Jahre
    Speicher    0,6759      0,2741              180              4,6
    Zulassung   0,5826      0,3674              191              6,0

**Teuer ist das Suchbudget.** Das Fenster schloss sich dem Befehl nach bei 349
Versuchen - "es bleiben 146" -, auf der Reihe bei **224**, also 21. An dieser
Zahl haengt eine unwiderrufliche Entscheidung: Ein Versuch ist nicht
zuruecknehmbar, und jeder hebt die Latte fuer alle folgenden.

Und sie belegt sich selbst: ``budgetgrenze`` nennt sich im eigenen Docstring
*"die Zahl, die das Suchbudget begrenzt - und zwar schaerfer als der Plan"*,
waehrend 349 **lockerer** war als die 230 des Plans. Mit der Reihe sind es 224,
und der Satz stimmt wieder.
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.gates import GateThresholds, deflated_sharpe_ratio
from research.referenz import SPOTPUNKT
from research.stand import BUDGET

#: Gemessen, siehe Kopf.
FENSTER_REIHE = 224
FENSTER_SPEICHER = 349


def _dsr(versuche: int) -> float:
    """Der Deflated Sharpe des Referenzpunkts bei dieser Versuchszahl.

    Nur die Versuchszahl wandert - Guete, Stichprobe und Momente sind die des
    Referenzpunkts. Deshalb braucht dieser Test keine Kerzen.
    """
    return deflated_sharpe_ratio(
        observed_sharpe=SPOTPUNKT.guete,
        trials=versuche,
        sample_size=SPOTPUNKT.effektiv,
        skew=SPOTPUNKT.schiefe,
        kurtosis=SPOTPUNKT.woelbung,
    )


class TestDerBefehlStehtJetztAufDerReihe:
    def test_er_schneidet(self) -> None:
        quelle = inspect.getsource(cli.abstand)

        assert "alle_geschnitten(frames)" in quelle

    def test_und_nennt_die_reihe(self) -> None:
        """Die einzeilige Auskunft aus Befund 370. Genau sie hat mir in diesem
        Durchgang gefehlt, als ich den Referenzpunkt fuer gerissen hielt."""
        quelle = inspect.getsource(cli.abstand)

        assert "reihenzeile(frames)" in quelle

    def test_der_docstring_nennt_den_unterschied(self) -> None:
        text = cli.abstand.__doc__ or ""

        assert "387" in text
        for zahl in ("0,6759", "0,5826", "349", "224"):
            assert zahl in text, zahl


class TestDieFormelReproduziertDenPunkt:
    """Die Grundlage aller Zahlen hier: dieselben Eingangsgroessen, dasselbe
    Ergebnis wie in ``referenz.py``."""

    def test_der_referenzpunkt_rechnet_nach(self) -> None:
        assert _dsr(SPOTPUNKT.versuche) == pytest.approx(SPOTPUNKT.dsr, abs=0.0001)


class TestWasDerVersuchszaehlerBewegt:
    """Die seit Befund 233 offene Frage, in ihrer Wirkung beantwortet.

    'Zaehlt ein Sweep am Bestand als Versuch?' **koennte** das Gate
    entscheiden - der Umschlag liegt bei 21 Versuchen, heute stehen 203. Mit
    den vorhandenen Belegen entscheidet sie es aber nicht.
    """

    def test_bei_einundzwanzig_versuchen_haelt_das_gate(self) -> None:
        t = GateThresholds()

        assert _dsr(21) >= t.min_deflated_sharpe
        assert _dsr(22) < t.min_deflated_sharpe

    def test_die_belegten_sweeps_bringen_anderthalb_prozent(self) -> None:
        """Belegt sind die fuenf Stellungen, die 'cli machbarkeit --spot' in
        Befund 281/282 in den Grundstock gebucht hat (187 -> 192).

        Alle 11 Einzelnachweise sind Suchlaeufe, kein einziger ein Sweep. Fuer
        21 muessten 182 der 203 fallen, und fuer 192 davon ist die Herkunft
        weg - sie nachtraeglich zu benennen waere eine Umbuchung (234/282).
        """
        t = GateThresholds()
        jetzt = _dsr(203)
        ohne_sweeps = _dsr(198)
        luecke = t.min_deflated_sharpe - jetzt

        assert ohne_sweeps - jetzt == pytest.approx(0.0055, abs=0.0002)
        assert (ohne_sweeps - jetzt) / luecke < 0.02
        assert ohne_sweeps < t.min_deflated_sharpe, "auch ohne sie reisst es"

    def test_die_herkunft_der_einzelnachweise_ist_suche(self) -> None:
        """Nicht geschaetzt - aus der Akte gelesen."""
        import json
        import pathlib

        d = json.loads(pathlib.Path("state/trials.json").read_text())
        herkunft = [v["herkunft"] for v in d["versuche"]]

        assert len(herkunft) == 11
        assert not any("machbarkeit" in h or "landschaft" in h for h in herkunft)


class TestDasFensterGegenDenPlan:
    """Die Rechnung ist strenger als die Abmachung - und war es vorher nicht."""

    def test_der_plan_gibt_mehr_frei_als_die_rechnung(self) -> None:
        assert BUDGET.grenze == 230
        assert BUDGET.rest(SPOTPUNKT.versuche) == 27
        assert BUDGET.grenze > FENSTER_REIHE
        assert BUDGET.grenze - FENSTER_REIHE == 6

    def test_auf_dem_speicher_war_es_umgekehrt(self) -> None:
        """Das ist der Beleg, dass die Reihe und nicht die Formel fehlte: Mit
        349 stand die 'schaerfer als der Plan'-Zusage im Widerspruch zu sich
        selbst."""
        assert BUDGET.grenze < FENSTER_SPEICHER

    def test_die_grenze_nennt_ihre_reihe(self) -> None:
        from research.zielfenster import Zielfenster

        text = Zielfenster.budgetgrenze.__doc__ or ""

        assert "224" in text
        assert "349" in text
        assert "Zulassungsreihe" in text
        assert "214" in text, "die ueberholte Zahl bleibt als Vermerk stehen"

    def test_das_budget_kennt_die_rechnung(self) -> None:
        from research.stand import Suchbudget

        text = Suchbudget.__doc__ or ""

        assert "224" in text
        assert "Abmachung dadurch nicht" in text, (
            "die vorab genannte Zahl wird nicht herabgesetzt, weil die "
            "Rechnung es erlaubt - davor warnt der Eintrag selbst"
        )


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_die_zahlen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 387)

        for zahl in ("0,6759", "0,5826", "349", "224", "21", "0,0055"):
            assert zahl in eintrag.ergebnis, zahl

    def test_und_die_gegenprobe_am_referenzpunkt(self) -> None:
        """Das negative Ergebnis gehoert dazu: Befund 363/364 tut, was er
        verspricht - sonst sucht der naechste Durchgang dort."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 387)

        assert "reproduziert" in eintrag.ergebnis
        assert "5355/3301" in eintrag.ergebnis

    def test_die_inventur_steht_als_offene_richtung(self) -> None:
        from research.stand import OFFEN

        eintrag = next(r for r in OFFEN if r.befund == 387)

        assert "39" in eintrag.ergebnis
        assert "35" in eintrag.ergebnis
        assert "wird nichts umgestellt" in eintrag.ergebnis


class TestDieInventurStimmtNoch:
    """Die Zahl aus der offenen Richtung, an der Quelle nachgezaehlt.

    Kein Selbstzweck: Wer einen Befehl hinzufuegt, der den Spitzenkandidaten
    rechnet, soll **sehen**, dass er sich fuer eine Reihe entscheiden muss.
    """

    @staticmethod
    def _inventur() -> tuple[list[str], list[str], list[str]]:
        import pathlib
        import re
        from itertools import pairwise

        t = pathlib.Path("cli.py").read_text()
        grenzen = [m.start() for m in re.finditer(r"\n@app\.command\(\)", t)]
        grenzen.append(len(t))
        schneidet: list[str] = []
        nennt: list[str] = []
        keins: list[str] = []
        for anfang, ende in pairwise(grenzen):
            block = t[anfang:ende]
            treffer = re.search(r"\ndef (\w+)\(", block)
            if treffer is None:
                continue
            laeuft = "run_portfolio_walkforward" in block or "run_walkforward" in block
            if not (laeuft and "spitzenkandidat" in block):
                continue
            name = treffer.group(1)
            g = "alle_geschnitten" in block
            n = "reihenzeile" in block or "_reihenvermerk" in block
            if g:
                schneidet.append(name)
            if n:
                nennt.append(name)
            if not g and not n:
                keins.append(name)
        return schneidet, nennt, keins

    def test_drei_schneiden_vier_nennen_vierunddreissig_keins(self) -> None:
        """Die Zahlen wandern, wenn ein Befehl sich entscheidet - und genau
        dafuer ist der Test da.

        387 zaehlte 2 / 3 / 35. Befund 390 hat 'cli rennen' dazugenommen,
        weil dort das **Vorzeichen** der Aussage ueber das Weitersuchen an der
        Grundlage hing (Ideenstreuung 0,0906 gegen Nullstreuung 0,0913 auf der
        Reihe, 0,0962 gegen 0,0917 auf dem Speicher). Jetzt sind es 3 / 4 / 34.

        Die offene Regel bleibt offen: Es wird nicht umgestellt, weil zwei es
        tun, sondern weil eine Zahl daran haengt.
        """
        schneidet, nennt, keins = self._inventur()

        assert sorted(schneidet) == ["abstand", "anatomie", "rennen"]
        assert sorted(nennt) == ["abstand", "rennen", "stand", "suchbudget"]
        assert len(keins) == 34, (
            f"{len(keins)} statt 34 Befehle ohne Reihe - wer einen Befehl auf "
            f"den Spitzenkandidaten setzt, entscheidet sich fuer eine Reihe "
            f"(Befund 387/390): {sorted(keins)}"
        )


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    """Die Tabelle aus dem Kopf. ``daten`` wegen des Kerzenspeichers,
    ``langsam`` wegen zweier Portfolio-Walk-Forwards."""

    @staticmethod
    def _lauf(schneiden: bool):
        import numpy as np

        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.datenstand import alle_geschnitten
        from research.gates import stichprobe_wie_im_gate
        from research.randschnitt import ohne_zensierte
        from research.seeds import spitzenkandidat
        from research.zielfenster import Handelsbuch, vermesse
        from strategy.compiler import compile_genome

        e = get_settings()
        store = CandleStore(e.paths.data_store)
        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        roh = {s: store.read(s, Interval.D1) for s in symbole}
        if schneiden:
            roh = alle_geschnitten(roh)
        frames = common_range(roh)
        genom = cli._ohne_hebel(spitzenkandidat())
        report = run_portfolio_walkforward(
            frames, lambda: compile_genome(genom), cli._spotconfigs(symbole, e)
        )
        trades = list(ohne_zensierte(report).all_trades)
        pnl = np.array([float(x.net_pnl) for x in trades])
        streuung = float(np.std(pnl, ddof=1))
        z = (pnl - np.mean(pnl)) / streuung
        schiefe, woelbung = float(np.mean(z**3)), float(np.mean(z**4))
        st = stichprobe_wie_im_gate(trades)
        dsr = deflated_sharpe_ratio(
            observed_sharpe=float(np.mean(pnl)) / streuung,
            trials=SPOTPUNKT.versuche, sample_size=st.effektiv,
            skew=schiefe, kurtosis=woelbung,
        )
        wf = [w for w in report.windows if w.window is not None]
        t = GateThresholds()
        ziel = vermesse(
            Handelsbuch(
                trades_gesamt=len(report.all_trades), effektiv=st.effektiv,
                mittel=float(np.mean(pnl)), streuung=streuung,
                summe=float(sum(x.net_pnl for x in report.all_trades)),
                rueckgang_pct=report.combined.max_drawdown_pct,
                jahre=(wf[-1].window.test_end - wf[0].window.test_start).days / 365.25,
            ),
            versuche=SPOTPUNKT.versuche, schwelle_pct=t.min_cagr_pct, dsr_ziel=0.95,
            drawdown_grenze=t.max_oos_drawdown_pct,
            schiefe=schiefe, woelbung=woelbung,
        )
        grenze = ziel.budgetgrenze(schiefe=schiefe, woelbung=woelbung)
        return len(trades), st.effektiv, dsr, grenze.versuche

    def test_auf_der_reihe_reproduziert_der_referenzpunkt(self) -> None:
        trades, effektiv, dsr, _ = self._lauf(schneiden=True)

        assert trades == SPOTPUNKT.trades
        assert effektiv == SPOTPUNKT.effektiv
        assert dsr == pytest.approx(SPOTPUNKT.dsr, abs=0.0002)

    def test_und_das_fenster_schliesst_bei_224(self) -> None:
        *_, grenze = self._lauf(schneiden=True)

        assert grenze == FENSTER_REIHE

    def test_auf_dem_speicher_steht_alles_zu_guenstig(self) -> None:
        trades, effektiv, dsr, grenze = self._lauf(schneiden=False)

        assert trades > SPOTPUNKT.trades
        assert effektiv > SPOTPUNKT.effektiv
        assert dsr > SPOTPUNKT.dsr
        assert grenze == FENSTER_SPEICHER
