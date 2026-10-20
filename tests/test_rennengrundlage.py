"""Das Wettrennen rechnete auf einer anderen Grundlage als das Gate - Befund 390.

``cli rennen`` beantwortet die Frage, ob Weitersuchen die Huerde je einholt -
also die Entscheidung ueber das ganze Vorgehen. Gerechnet hat es auf dem
**Speicher** und mit **allen** Trades: zweifach neben der Grundlage des Gates,
und beide Abweichungen hat dieses Projekt anderswo laengst behoben (363/364 die
Reihe, 152/371 den Randschnitt).

Am Perpetual-Punkt kippt daran das **Vorzeichen**:

    Grundlage                  Guete   Ideenstreuung   Nullstreuung   Schluss
    Speicher, alle Trades     0,2665          0,0962         0,0917   holt auf
    Reihe, fertige Trades     0,2509          0,0906         0,0913   **nie**

Oben holt die Suche irgendwann auf ("jenseits von 1e+09"), unten nie: Der beste
Fund waechst langsamer als das, was Zufall ohnehin hergibt.

**Die Richtung von Befund 71 ist unveraendert und schaerfer.** Weitersuchen war
immer der schwache Hebel - es ist nur nicht mehr "spaet", sondern "gar nicht".

**Und es bleibt ein Punktschaetzer.** Die Rueckrechnung steht auf einem
einzigen beobachteten Bestwert; ihre relative Streuung liegt bei 14,2 %, und der
90-%-Bereich von 0,0738 bis 0,1146 enthaelt die Nullstreuung. "Nie" ist mit dem
Verlauf vereinbar, "fast angekommen" ebenso. Belastbar ist der Schluss, nicht
die Stelle.
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.wettrennen import Rennen

#: Gemessen, siehe Kopf. Perpetual-Punkt, 203 Versuche.
SPEICHER_ALLE = (0.2665, 120)
REIHE_FERTIGE = (0.2509, 121)


class TestDerBefehlStehtAufDerGateGrundlage:
    def test_er_schneidet_auf_die_reihe(self) -> None:
        quelle = inspect.getsource(cli.rennen)

        assert "alle_geschnitten(frames)" in quelle
        assert "reihenzeile(frames)" in quelle

    def test_und_nimmt_die_fertigen_trades(self) -> None:
        quelle = inspect.getsource(cli.rennen)

        assert "ohne_zensierte(roher_bericht)" in quelle

    def test_die_spanne_kommt_aus_den_geschnittenen_rahmen(self) -> None:
        """Sonst stuenden 3350 Tage neben 156 Trades - die Spanne des
        Speichers neben der Trade-Zahl der Reihe."""
        quelle = inspect.getsource(cli.rennen)

        assert "_spanne = _korb_daten" in quelle, (
            "die Spanne aus _korb_daten gilt fuer die ungeschnittenen Rahmen"
        )
        assert 'erster["open_time"]' in quelle

    def test_der_kommentar_nennt_beide_zahlen(self) -> None:
        quelle = inspect.getsource(cli.rennen)

        for zahl in ("0,2665", "0,0962", "0,0917", "0,2509", "0,0906", "0,0913"):
            assert zahl in quelle, zahl


class TestDasVorzeichenKipptWirklich:
    """Die beiden Grundlagen, an der Rechnung nachgeprueft - ohne Kerzen.

    ``Rennen`` braucht nur Bestwert, Versuche und Stichprobe; die Momente
    stehen im Referenzpunkt. Damit ist die Kernaussage dieses Befundes ein
    schneller Test und kein ``daten``-Test.
    """

    @staticmethod
    def _lauf(guete: float, trades: int) -> Rennen:
        from research.referenz import PERPETUALPUNKT

        return Rennen(
            bester=guete, versuche=203, trades=trades, mittel=0.0,
            schiefe=PERPETUALPUNKT.schiefe, woelbung=PERPETUALPUNKT.woelbung,
        )

    def test_auf_dem_speicher_holt_die_suche_auf(self) -> None:
        lauf = self._lauf(*SPEICHER_ALLE)

        assert lauf.streuung > lauf.nullstreuung
        assert lauf.schneller_als_die_huerde

    def test_auf_der_reihe_nicht_mehr(self) -> None:
        lauf = self._lauf(*REIHE_FERTIGE)

        assert lauf.streuung < lauf.nullstreuung
        assert not lauf.schneller_als_die_huerde
        assert lauf.schnittpunkt() is None

    def test_der_unterschied_ist_klein_und_entscheidend(self) -> None:
        """0,0906 gegen 0,0913 - sieben Zehntausendstel, und sie tragen die
        Aussage. Genau deshalb muss die Grundlage stimmen."""
        reihe = self._lauf(*REIHE_FERTIGE)

        assert abs(reihe.streuung - reihe.nullstreuung) < 0.002

    def test_und_die_unsicherheit_umschliesst_beide_lesarten(self) -> None:
        """Ohne diesen Satz waere 'nie' eine Behauptung. Der 90-%-Bereich
        enthaelt die Nullstreuung, also auch 'fast angekommen' - und
        ``unsicherheit`` sagt das selbst, als Text (Befund 124)."""
        reihe = self._lauf(*REIHE_FERTIGE)
        text = reihe.unsicherheit()

        assert "0.0738" in text
        assert "0.1146" in text
        assert "liegt darin" in text
        assert "nie auf' mit dem Verlauf vereinbar" in text


class TestDieHilfsfunktionVerlangtIhreStichprobe:
    """Mein Fehler, beinahe: Der erste Einbau haette Befund 371 hier **neu
    erzeugt** - 'kandidat' auf den fertigen Trades, '_spotguete' weiter auf der
    ganzen Liste, und der gemeldete Niveauschub waere 0,0344 statt 0,0199
    gewesen: die Differenz zweier Grundlagen und nicht die des Funding.
    """

    def test_ohne_angabe_geht_es_nicht(self) -> None:
        parameter = inspect.signature(cli._spotguete).parameters

        assert "fertige" in parameter
        assert parameter["fertige"].default is inspect.Parameter.empty, (
            "ein Vorgabewert waere die Falle: Der naechste Aufrufer uebernimmt "
            "ihn, ohne zu wissen, worauf seine eigene Zahl steht"
        )
        assert parameter["fertige"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_jeder_aufrufer_sagt_es(self) -> None:
        quelle = inspect.getsource(cli)
        aufrufe = quelle.count("_spotguete(")

        assert aufrufe == 4, "Definition und drei Aufrufer"
        assert quelle.count("fertige=True") >= 1
        assert quelle.count("fertige=False") >= 2

    def test_das_rennen_nimmt_die_gate_grundlage(self) -> None:
        quelle = inspect.getsource(cli.rennen)

        assert "fertige=True" in quelle

    @pytest.mark.parametrize("befehl", ["form", "suchbudget"])
    def test_die_anderen_bleiben_bei_ihrer(self, befehl: str) -> None:
        """Ihre Gegenzahl steht auf der ganzen Liste - dieselbe Stichprobe auf
        beiden Seiten ist die Forderung, nicht eine bestimmte."""
        quelle = inspect.getsource(getattr(cli, befehl))

        assert "fertige=False" in quelle


class TestDerSchlusssatzPasstZuDenZahlen:
    def test_er_unterscheidet_nie_von_spaeter(self) -> None:
        quelle = inspect.getsource(cli.rennen)

        assert "beide_nie" in quelle
        assert "bindende Grenze" in quelle
        assert "jenseits des Budgetendes" in quelle, "der andere Fall bleibt"


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_beide_grundlagen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 390)

        for zahl in ("0,2665", "0,0962", "0,2509", "0,0906", "0,0913"):
            assert zahl in eintrag.ergebnis, zahl

    def test_und_die_unsicherheit(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 390)

        assert "Punktschaetzer" in eintrag.ergebnis
        assert "0,0738" in eintrag.ergebnis

    def test_das_budget_nennt_die_gemessenen_werte(self) -> None:
        from research.stand import Suchbudget

        text = Suchbudget.__doc__ or ""

        assert "0,0906" in text
        assert "0,0913" in text
        assert "56.000" in text, "die ueberholte Zahl bleibt als Vermerk stehen"
        assert "stimmt das nicht mehr" in text

    def test_und_haelt_die_richtung_von_71_aufrecht(self) -> None:
        """Nicht der Befund war falsch, nur die Grundlage. Ein Eintrag, der
        jetzt 'alles anders' sagte, waere die Gegenuebertreibung."""
        from research.stand import BEHOBEN, Suchbudget

        eintrag = next(r for r in BEHOBEN if r.befund == 390)

        assert "Richtung des Befundes 71 ist unveraendert" in eintrag.ergebnis
        assert "Richtung des Befundes ist unveraendert" in (Suchbudget.__doc__ or "")

    def test_und_389_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        vorher = next(r for r in BEHOBEN if r.befund == 389)

        assert vorher.zuletzt == 390


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    """Die Tabelle aus dem Kopf, am Lauf nachgeprueft."""

    @staticmethod
    def _guete(*, schneiden: bool, fertige: bool) -> tuple[float, int]:
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
        from research.suchbudget import Kandidat
        from strategy.compiler import compile_genome

        e = get_settings()
        store = CandleStore(e.paths.data_store)
        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        roh = {s: store.read(s, Interval.D1) for s in symbole}
        frames = common_range(alle_geschnitten(roh) if schneiden else roh)
        _f, configs, _s = cli._korb_daten(symbole, Interval.D1, e)
        genom = spitzenkandidat()
        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genom), configs
        )
        quelle = ohne_zensierte(bericht) if fertige else bericht
        trades = list(quelle.all_trades)
        kand = Kandidat.aus_trades(genom.name, trades)
        st = stichprobe_wie_im_gate(
            trades,
            beine=getattr(quelle, "beine", None),
            bloecke=[[float(t.net_pnl) for t in f.trades] for f in quelle.windows],
        )
        return kand.sharpe_je_trade, st.effektiv

    def test_speicher_mit_allen_trades(self) -> None:
        guete, effektiv = self._guete(schneiden=False, fertige=False)

        assert guete == pytest.approx(SPEICHER_ALLE[0], abs=0.002)
        assert effektiv == SPEICHER_ALLE[1]

    def test_reihe_mit_den_fertigen(self) -> None:
        guete, effektiv = self._guete(schneiden=True, fertige=True)

        assert guete == pytest.approx(REIHE_FERTIGE[0], abs=0.002)
        assert effektiv == REIHE_FERTIGE[1]
