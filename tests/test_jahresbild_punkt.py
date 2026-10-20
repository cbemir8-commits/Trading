"""Der Befehl wurde gebaut und nie gelaufen - Befund 386.

``cli jahresbild`` beantwortet eine Frage, die sein eigener Docstring fuer
wichtiger haelt als jeden weiteren Suchlauf: Besteht der Fehlschlag von
'Schlechtestes Jahr' aus **einer Spitze** oder aus einer **Hochebene**? Zwei
sehr verschiedene Lagen sehen im Gate gleich aus, weil es nur das Minimum
zurueckgibt.

Im Register stand dazu **nichts**. Kein Eintrag nennt die Zahl der Fenster, den
Anteil darunter oder den Vergleich zwischen Index- und Kalenderrechnung - die
dritte Stelle in dieser Reihe, an der etwas gebaut und nicht abgeholt wurde
(nach 379 bei mir selbst und 382 im Dashboard).

Gelaufen, an beiden Betriebspunkten:

    Perpetual   Gate -10,32 % FAIL   2 von 2557 Fenstern darunter (0,1 %)
                zweites, nicht ueberlappend -6,38 %   Median +11,51 %
    Spot        Gate  -9,61 % PASS   0 von 2557
                zweites, nicht ueberlappend -5,04 %   Median +12,92 %

    Indizes gegen Kalender: -0,002 Punkte (Perpetual), +0,001 (Spot)

Drei Dinge stehen darin.

**Die Rechnung stimmt.** Das Gate schaetzt die Fensterbreite ueber Indizes
(``len(curve) * 12 / total_months``), hier ist sie am Kalender gerechnet, und
der Unterschied liegt bei zwei Tausendsteln. Der Verdacht, der diesen Befehl
veranlasst hat, ist damit ausgeraeumt - ein negatives Ergebnis, und es gehoert
aufgeschrieben.

**Der Fehlschlag ist eine Spitze.** Zwei von 2557 Fenstern liegen unter der
Schwelle, und es sind dieselben zwei Tage versetzt: 2021-11-08 bis 2022-11-08.
Das naechste Fenster, das sich damit **nicht** ueberlappt, steht bei -6,38 % -
3,62 Punkte innerhalb der Schwelle.

**Und am massgeblichen Punkt gibt es ihn nicht.** Am Spot-Punkt liegt
**kein einziges** Fenster unter -10 %. Der Docstring nannte das Gate "der
schmalste Fehlschlag im System" und sprach von "den vier Gates, an denen der
Spitzenkandidat scheitert" - beides vom Perpetual-Punkt und von vor Befund 311,
der die zwei Punkte eingefuehrt hat. Am Spot-Punkt scheitern zwei Gates, und
dieses ist keines davon.
"""

from __future__ import annotations

import inspect

import pytest

import cli

#: Gemessen, siehe Kopf. Beide Punkte, dieselbe Fensterzahl.
FENSTER = 2557


class TestDerBefehlNenntSeinenBetriebspunkt:
    """Die Lehre aus Befund 336: Eine Zahl ohne Punkt ist keine Zahl."""

    def test_er_hat_den_schalter(self) -> None:
        namen = set(inspect.signature(cli.jahresbild).parameters)

        assert "spot" in namen

    def test_die_kopfzeile_nennt_ihn(self) -> None:
        quelle = inspect.getsource(cli.jahresbild)

        assert "Betriebspunkt" in quelle
        assert "Spot (kein Funding, kein Hebel)" in quelle
        assert "Perpetual" in quelle

    def test_der_spot_punkt_nimmt_hebel_und_funding(self) -> None:
        """Nicht ein anderer Kandidat, sondern derselbe ohne beides - derselbe
        Weg wie in 'cli stand' und 'cli anatomie'."""
        quelle = inspect.getsource(cli.jahresbild)

        assert "_ohne_hebel(genome)" in quelle
        assert "_spotconfigs(symbole, settings)" in quelle

    def test_der_docstring_steht_nicht_mehr_auf_vier_gates(self) -> None:
        """'von den vier Gates, an denen der Spitzenkandidat scheitert' war
        von vor Befund 311. Am Spot-Punkt sind es zwei, und dieses ist keines.

        Der alte Satz ist **nicht geloescht**, sondern als ueberholt vermerkt -
        die Bauart des Laborbuchs: Wer die alte Zahl sucht, soll finden, was
        aus ihr wurde. Geprueft wird deshalb der Vermerk, nicht die Abwesenheit.
        """
        text = cli.jahresbild.__doc__ or ""

        assert 'Hier stand "von den vier Gates' in text
        assert "ueberholt" in text
        assert "Befund 386" in text
        assert "Am Perpetual-Punkt" in text
        assert "-9,61" in text


class TestWasDieMessungErgabe:
    """Die Zahlen aus dem Kopf, an die Akte gebunden - nicht an Prosa."""

    def test_die_spitze_steht_im_register(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 386)

        assert "2557" in eintrag.ergebnis
        assert "6,38" in eintrag.ergebnis, "das nicht ueberlappende Fenster fehlt"
        assert "Spitze" in eintrag.ergebnis

    def test_und_die_rechnung_als_negatives_ergebnis(self) -> None:
        """Der Verdacht, der den Befehl veranlasst hat, ist ausgeraeumt - und
        das gehoert aufgeschrieben, damit niemand dieselbe Sorge noch einmal
        hat (die Bauart aus Befund 372)."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 386)

        assert "Indizes" in eintrag.ergebnis
        assert "Kalender" in eintrag.ergebnis
        assert "0,002" in eintrag.ergebnis

    def test_die_entscheidung_kennt_die_spitze_jetzt(self) -> None:
        """Sie informiert die Frage nach festen Schwellen auf laufenden
        Extrema: Ein Riss, der an **einer** Episode haengt, ist ein anderes
        Argument als einer, der an der Strategie haengt."""
        from research.stand import ENTSCHEIDUNGEN

        eintrag = next(
            e for e in ENTSCHEIDUNGEN
            if e.frage == "Feste Schwellen auf laufenden Extrema"
        )

        assert "2557" in eintrag.zahl
        assert "386" in eintrag.zahl


class TestWasGepruefteUndVerworfenWurde:
    """Damit der naechste Durchgang es nicht noch einmal prueft."""

    def test_die_zulassungsreihe_aendert_hier_nichts(self) -> None:
        """``alle_geschnitten`` fehlt in diesem Befehl - acht andere Dateien
        haben es in Befund 363/364 bekommen.

        Gemessen gibt es **identische** Zahlen: Gate -10,32 %, 2557 Fenster,
        dieselbe Episode. Der Grund ist, dass das schlechteste Jahr weit vom
        Datenende liegt (2021-11 bis 2022-11) und der Walk-Forward die Beine
        ohnehin schneidet. Eingebaut wurde es deshalb **nicht** - eine
        Aenderung ohne Wirkung ist eine Aenderung zu viel.
        """
        quelle = inspect.getsource(cli.jahresbild)

        assert "alle_geschnitten" not in quelle
        assert "common_range(roh)" in quelle

    def test_das_steht_auch_im_register(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 386)

        assert "alle_geschnitten" in eintrag.ergebnis


class TestDasArchivIstProsa:
    """Mein zweiter Fehler in diesem Durchgang, von einem Waechter gefunden.

    Die Tabelle stand zuerst **im Archiveintrag**, mit Zeilenumbruechen. Darauf
    ist ``test_kurzbericht`` gefallen: ``Lage.bericht(kurz=True)`` wirft die
    Archiveintraege **zeilengenau** weg (``{f"  {r}" for r in BEHOBEN}``), und
    ein mehrzeiliger Eintrag passt auf keine einzelne Zeile - er waere im
    Kurzbericht stehen geblieben, und zwar genau das, was dort wegfallen soll.

    Nachgezaehlt: **257 der 258** Richtungen sind einzeilig, meine war die
    Ausnahme. Umgekehrt tragen **9 von 11** Entscheidungen eine Tabelle, und
    die bleiben im Kurzbericht stehen. Das ist keine Formsache: Das Archiv ist
    Prosa zum Nachschlagen, die Entscheidungen sind das, was der Nutzer lesen
    muss. Die Tabelle gehoert also dorthin, wo sie jetzt steht.
    """

    def test_keine_richtung_hat_einen_umbruch(self) -> None:
        from research.stand import BEHOBEN, GESCHLOSSEN, OFFEN

        mehrzeilig = [
            r.befund for r in (*GESCHLOSSEN, *BEHOBEN, *OFFEN)
            if "\n" in r.ergebnis
        ]

        assert mehrzeilig == [], (
            "Mehrzeilige Richtungen bleiben im Kurzbericht stehen - die "
            "Tabelle gehoert zur Entscheidung oder ins Laborbuch."
        )

    def test_die_zahlen_stehen_trotzdem_im_eintrag(self) -> None:
        """Einzeilig heisst nicht zahlenlos - sonst waere die Kuerzung ein
        Verlust und kein Formwechsel."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 386)

        for zahl in ("2557", "-10,32", "-9,61", "-6,38", "-5,04"):
            assert zahl in eintrag.ergebnis, zahl


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    """Die Tabelle aus dem Kopf. ``daten``, weil der Kerzenspeicher gebraucht
    wird; ``langsam`` wegen der Portfolio-Walk-Forwards.

    Gemessen, nicht geschaetzt: 10,8 s fuer alle vier - rund vierzig Mal eine
    Durchschnittszeit der messbaren Suite, also berechtigt markiert, aber keine
    Kaffeepause.
    """

    @staticmethod
    def _bild(spot: bool):
        from decimal import Decimal

        from backtest.engine import BacktestConfig
        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.gates import GateThresholds, gate_worst_year
        from research.jahresbild import zerlege
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        e = get_settings()
        store = CandleStore(e.paths.data_store)
        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        frames = common_range({s: store.read(s, Interval.D1) for s in symbole})
        genom = spitzenkandidat()
        if spot:
            genom = cli._ohne_hebel(genom)
            configs = cli._spotconfigs(symbole, e)
        else:
            configs = {
                x: BacktestConfig(
                    instrument=cli._fallback_instrument(cli._bybit_kontrakt(x)),
                    risk=e.risk,
                    initial_equity=Decimal("500"),
                    enforce_risk_limits=True,
                    kalender=cli._terminkalender(e) or None,
                )
                for x in symbole
            }
        bericht = run_portfolio_walkforward(
            frames, lambda g=genom: compile_genome(g), configs
        )
        schwellen = GateThresholds()
        gate = gate_worst_year(bericht, schwellen)
        bild = zerlege(
            bericht,
            list(bericht.all_trades),
            schwelle_pct=schwellen.worst_year_pct,
            index_wert=gate.value,
        )
        return gate, bild

    def test_perpetual_ist_eine_spitze(self) -> None:
        gate, bild = self._bild(spot=False)

        assert gate.value == pytest.approx(-10.32, abs=0.02)
        assert len(bild.fenster) == FENSTER
        assert bild.darunter == 2
        assert bild.anteil_darunter < 0.002
        assert bild._zweites() == pytest.approx(-6.38, abs=0.05)
        assert "Spitze" in bild.urteil()

    def test_am_spot_punkt_liegt_kein_fenster_darunter(self) -> None:
        gate, bild = self._bild(spot=True)

        assert gate.value == pytest.approx(-9.61, abs=0.02)
        assert bild.darunter == 0
        assert bild._zweites() == pytest.approx(-5.04, abs=0.05)

    @pytest.mark.parametrize("spot", [False, True])
    def test_die_indexrechnung_stimmt_mit_dem_kalender(self, spot: bool) -> None:
        """Der Verdacht, der diesen Befehl veranlasst hat - ausgeraeumt."""
        _, bild = self._bild(spot=spot)

        assert abs(bild.abweichung) < 0.01
