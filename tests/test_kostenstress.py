"""Der Umfang des Kosten-Stress-Tests - Befund 339.

Vierter Verdachtsfall aus der Wache von Befund 335: **'Umfang des
Kosten-Stress-Tests'**, Fundstelle Befund 96, spaeter in 101, 102, 127 und 314
erwaehnt.

Jeder Betrag des Eintrags stimmt auf die Stelle, und 942,87 ist der Gatewert
selbst - Eintrag und Gate messen dasselbe, beide durchgehend.

Der **Anteil** stimmt nicht. Er misst zwei Dinge:

    Lauf                        Trades  gesperrt     Gewinn
    wie gebaut, mit Officer         91        75    942,87
    mit Funding, mit Officer        71        95    625,80
    wie gebaut, ohne Officer       166         0   2318,32
    mit Funding, ohne Officer      166         0   1632,86

Der dritte Lauf verliert zwanzig Trades an eine dauerhafte Sperre, die im zweiten
noch nicht gefeuert hat. Auf demselben Trade-Satz - ohne Officer und damit ohne
Sperre - kostet das verdoppelte Funding **29,6 %** und nicht 34 %.

Die Richtung des Eintrags bleibt: Der ausgelassene Posten ist der groessere, und
das Urteil kippt auch ohne Sperre nicht.

Dazu eine eigene Zeile aus Befund 314: "eine dauerhafte Sperre hat dabei **245**
Einstiege verhindert" war die Summe ueber drei Laeufe, `75 + 75 + 95`. Sie zaehlt
dieselbe Sperre dreimal. Je Lauf berichtet, ist der Unterschied zwischen 75 und
95 genau der Fund.
"""

from __future__ import annotations

import pytest

from research.finanzierung import Stresslage

#: Die fuenf Laeufe und was sie liefern (Befund 339, Perpetual-Punkt).
GEMESSEN: tuple[tuple[str, bool, bool, bool, int, int, float], ...] = (
    # Name, Gebuehren doppelt, Funding doppelt, Officer, Trades, gesperrt, Gewinn
    ("ohne Stress", False, False, True, 91, 75, 955.76),
    ("wie gebaut", True, False, True, 91, 75, 942.87),
    ("mit Funding", True, True, True, 71, 95, 625.80),
    ("wie gebaut, ohne Officer", True, False, False, 166, 0, 2318.32),
    ("mit Funding, ohne Officer", True, True, False, 166, 0, 1632.86),
)


def lage(**abweichung) -> Stresslage:
    daten = {
        "faktor": 2.0,
        "ohne_stress": 955.76,
        "wie_gebaut": 942.87,
        "mit_funding": 625.80,
    }
    daten.update(abweichung)
    return Stresslage(**daten)


class TestDieSperrenStehenJeLauf:
    """**Der Fehler, den Befund 314 hinterlassen hat.** Eine Summe ueber drei
    Laeufe zaehlt dieselbe Sperre dreimal."""

    def test_der_zuwachs_ist_der_unterschied_der_laeufe(self) -> None:
        assert lage(sperren=(75, 75, 95)).sperrzuwachs == 20

    def test_ohne_sperren_ist_der_zuwachs_null(self) -> None:
        """Nicht ``IndexError``: Der Vorbehalt ist freiwillig, und ein Absturz
        waere ein hoher Preis fuer eine fehlende Angabe."""
        assert lage().sperrzuwachs == 0

    def test_gleiche_sperren_meinen_keinen_zuwachs(self) -> None:
        assert lage(sperren=(75, 75, 75)).sperrzuwachs == 0

    def test_das_urteil_nennt_jeden_lauf_einzeln(self) -> None:
        urteil = lage(sperren=(75, 75, 95)).urteil()

        assert "je Lauf 75, 75, 95 Einstiege" in urteil
        assert "245" not in urteil, "die Summe ist die Menge von nichts"

    def test_und_nennt_das_fruehere_abschalten(self) -> None:
        urteil = lage(sperren=(75, 75, 95)).urteil()

        assert "20 Einstiege mehr als der erste" in urteil
        assert "frueher" in urteil

    def test_ohne_zuwachs_bleibt_der_zusatz_weg(self) -> None:
        """Ein Satz, der immer dasteht, wird nicht gelesen."""
        urteil = lage(sperren=(75, 75, 75)).urteil()

        assert "je Lauf 75, 75, 75" in urteil
        assert "mehr als der erste" not in urteil

    def test_der_vorbehalt_steht_vor_der_prozentzahl(self) -> None:
        """Wer die Prozentzahl liest und aufhoert, soll vorher wissen, worauf
        sie gerechnet ist - Befund 314."""
        urteil = lage(sperren=(75, 75, 95)).urteil()

        assert urteil.index("dauerhafte Sperre") < urteil.index(
            "verdoppelt den kleineren Posten"
        )

    def test_ohne_angabe_bleibt_das_urteil_wie_vorher(self) -> None:
        urteil = lage().urteil()

        assert "dauerhafte Sperre" not in urteil
        assert urteil.startswith("**Der Kosten-Stress verdoppelt")


class TestDerReineAnteil:
    """**Der Fund.** 34 % ist Gebuehr *und* fruehzeitiges Abschalten."""

    def test_ohne_gegenproben_gibt_es_keinen_anteil(self) -> None:
        """``None`` und nicht 0,0: Ein stillschweigend auf null gerechneter
        Anteil waere schlimmer als keiner - er sieht aus wie eine Messung."""
        assert lage().anteil_rein is None

    def test_auf_gleichem_trade_satz_sind_es_knapp_30_prozent(self) -> None:
        voll = lage(
            sperren=(75, 75, 95),
            ohne_sperre_gebaut=2318.32,
            ohne_sperre_funding=1632.86,
        )

        assert voll.anteil_uebersehen == pytest.approx(0.336, abs=0.001)
        assert voll.anteil_rein == pytest.approx(0.296, abs=0.001)

    def test_das_urteil_stellt_beide_zahlen_nebeneinander(self) -> None:
        urteil = lage(
            ohne_sperre_gebaut=2318.32, ohne_sperre_funding=1632.86
        ).urteil()

        assert "29.6% die Kosten selbst" in urteil
        assert "33.6%" in urteil
        assert "fruehere\nAbschalten" in urteil or "fruehere Abschalten" in urteil

    def test_die_zahlen_des_eintrags_haengen_nicht_daran(self) -> None:
        """Die Zeile, die eine Ergaenzung von einer Aenderung trennt."""
        ohne = lage()
        mit = lage(
            sperren=(75, 75, 95),
            ohne_sperre_gebaut=2318.32,
            ohne_sperre_funding=1632.86,
        )

        assert mit.uebersehene_marge == ohne.uebersehene_marge
        assert mit.anteil_uebersehen == ohne.anteil_uebersehen
        assert mit.urteil_kippt == ohne.urteil_kippt

    def test_das_urteil_kippt_auch_ohne_sperre_nicht(self) -> None:
        """Die Richtung des Eintrags bleibt - 1632,86 sind ebenfalls im
        Plus."""
        voll = lage(ohne_sperre_gebaut=2318.32, ohne_sperre_funding=1632.86)

        assert voll.ohne_sperre_funding > 0
        assert not voll.urteil_kippt


class TestDerBefehlFuelltEs:
    """Befund 152, 154, 155, 160, 325, 330, 337 und 338 waren dieselbe
    Bauart: gebaut, gerechnet, nicht angeschlossen."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "finanzierung"
        )

    def test_die_sperren_gehen_je_lauf_hinein(self) -> None:
        quelle = self._quelle()

        assert "sperren=(sperren_ohne, sperren_gebaut, sperren_mit)" in quelle
        assert "gesperrt_gesamt" not in quelle, "die Summe ist weg"

    def test_die_beiden_gegenproben_laufen_ohne_officer(self) -> None:
        quelle = self._quelle()

        assert "officer=False" in quelle
        assert "ohne_sperre_gebaut=rein_gebaut" in quelle
        assert "ohne_sperre_funding=rein_mit" in quelle

    def test_der_officer_haengt_am_schalter(self) -> None:
        """Nicht fest verdrahtet: Dieselbe Funktion faehrt beide Faelle,
        sonst waere die Gegenprobe eine zweite Konfiguration."""
        quelle = self._quelle()

        assert "enforce_risk_limits=officer" in quelle


class TestDerGateDocstringTraegtDenVorbehalt:
    def test_beide_anteile_stehen_da(self) -> None:
        from research.gates import gate_cost_stress

        text = gate_cost_stress.__doc__ or ""

        assert "33,6 %" in text
        assert "29,6 %" in text
        assert "34 %" not in text, "die alte Zahl ohne Vorbehalt"

    def test_der_grund_steht_dabei(self) -> None:
        from research.gates import gate_cost_stress

        text = gate_cost_stress.__doc__ or ""

        assert "166 Trades" in text
        assert "Befund 339" in text

    def test_die_richtung_bleibt_benannt(self) -> None:
        """Ein Docstring, der die Korrektur nennt und den Befund fallen
        laesst, waere die Gegenuebertreibung."""
        from research.gates import gate_cost_stress

        text = gate_cost_stress.__doc__ or ""

        assert "der ausgelassene Posten ist der\n    groessere" in text


class TestDerEintragIstNachgemessen:
    @staticmethod
    def _eintrag():
        from research.stand import ENTSCHEIDUNGEN

        return next(
            e for e in ENTSCHEIDUNGEN
            if e.frage == "Umfang des Kosten-Stress-Tests"
        )

    def test_der_anteil_ist_berichtigt(self) -> None:
        zahl = self._eintrag().zahl

        assert "29,6 %" in zahl
        assert "2318,32 gegen 1632,86" in zahl

    def test_der_grund_steht_dabei(self) -> None:
        zahl = self._eintrag().zahl

        assert "95" in zahl and "75" in zahl
        assert "166 Trades" in zahl

    def test_die_bestaetigten_betraege_stehen_dabei(self) -> None:
        """Gepruefte Zahlen, die stimmen, gehoeren genauso berichtet wie die
        eine, die nicht stimmte."""
        zahl = self._eintrag().zahl

        assert "942,87 ist der Gatewert selbst" in zahl
        assert "+109,64" in zahl and "+833,23" in zahl

    def test_die_richtung_bleibt_bestehen(self) -> None:
        zahl = self._eintrag().zahl

        assert "Die Richtung des Eintrags bleibt" in zahl
        assert "der groessere" in zahl

    def test_die_abwaegung_nennt_die_neue_zahl(self) -> None:
        """Der Nutzer entscheidet auf ``warum`` - dort darf die alte Zahl
        nicht stehenbleiben."""
        warum = self._eintrag().warum

        assert "29,6 %" in warum

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 96
        assert eintrag.massgeblich == 339


class TestDerEintragZu314IstBerichtigt:
    """Die 245 stehen an zwei Stellen: im Befehl und im Register. Eine Zahl
    nur an einer Stelle zu berichtigen ist die Bauart von Befund 313/330 und
    322/332 - der Fehler wandert in den Zweig, den ich gerade lese."""

    @staticmethod
    def _eintrag():
        from research.stand import BEHOBEN

        return next(
            b for b in BEHOBEN
            if b.name == "Die Karte, die das Gate als Aufloesung anbietet, "
                         "hatte denselben Riss"
        )

    def test_die_summe_ist_als_solche_benannt(self) -> None:
        ergebnis = self._eintrag().ergebnis

        assert "die 245 waren" in ergebnis
        assert "je Lauf sind es 75, 75 und 95" in ergebnis

    def test_der_unterschied_steht_dabei(self) -> None:
        ergebnis = self._eintrag().ergebnis

        assert "zwanzig\nTrades frueher" in ergebnis or (
            "zwanzig Trades frueher" in ergebnis
        )
        assert "29,6 %" in ergebnis

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        assert self._eintrag().massgeblich == 339


@pytest.mark.daten
@pytest.mark.langsam
def test_die_fuenf_laeufe_stimmen() -> None:
    """**Die Bindung.** Der Anteil stand dreiundvierzig Befunde lang auf einer
    Zahl, die zwei Wirkungen zusammenzaehlt. Ein Test haette das gefunden - der
    Unterschied der Trade-Zahlen (91 gegen 71) steht in jedem einzelnen Lauf.
    """
    from decimal import Decimal

    import cli
    from backtest.costs import FundingSchedule
    from backtest.engine import BacktestConfig, Backtester
    from backtest.metrics import compute_metrics
    from backtest.portfolio_walkforward import common_range
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.freigabe import stillgelegt
    from research.gates import GateThresholds, gate_cost_stress
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    e = get_settings()
    frames = common_range(
        {x: CandleStore(e.paths.data_store).read(x, Interval("D")) for x in symbole}
    )
    genom = spitzenkandidat()
    faktor = Decimal(str(GateThresholds().cost_stress_factor))
    betraege = {}

    for name, gebuehren, funding, officer, trades, gesperrt, gewinn in GEMESSEN:
        summe = 0.0
        gezaehlt = 0
        gesperrt_gezaehlt = 0
        for x in symbole:
            grund = BacktestConfig(
                instrument=cli._fallback_instrument(cli._bybit_kontrakt(x)),
                risk=e.risk,
                initial_equity=Decimal("500"),
                kalender=cli._terminkalender(e) or None,
            )
            cfg = BacktestConfig(
                instrument=grund.instrument,
                risk=grund.risk,
                costs=grund.costs.scaled(faktor) if gebuehren else grund.costs,
                funding=FundingSchedule(
                    default_rate=grund.funding.default_rate
                    * (faktor if funding else 1)
                ),
                initial_equity=grund.initial_equity,
                allow_shorts=grund.allow_shorts,
                entry_expiry_bars=grund.entry_expiry_bars,
                max_hold_bars=grund.max_hold_bars,
                enforce_risk_limits=officer,
            )
            ergebnis = Backtester(cfg).run(frames[x], compile_genome(genom))
            gezaehlt += len(ergebnis.trades)
            gesperrt_gezaehlt += stillgelegt(ergebnis.veto_reasons)
            summe += float(
                compute_metrics(
                    ergebnis.trades,
                    ergebnis.equity_curve,
                    initial_equity=cfg.initial_equity,
                    total_fees=ergebnis.total_fees,
                ).net_profit
            )
        betraege[name] = summe

        assert gezaehlt == trades, name
        assert gesperrt_gezaehlt == gesperrt, name
        assert summe == pytest.approx(gewinn, abs=0.02), name

    # Ohne Officer keine Sperre, und damit derselbe Trade-Satz in beiden Stufen
    # - das ist die Voraussetzung dafuer, dass 29,6 % eine Kostenaussage ist.
    voll = Stresslage(
        faktor=float(faktor),
        ohne_stress=betraege["ohne Stress"],
        wie_gebaut=betraege["wie gebaut"],
        mit_funding=betraege["mit Funding"],
        sperren=(75, 75, 95),
        ohne_sperre_gebaut=betraege["wie gebaut, ohne Officer"],
        ohne_sperre_funding=betraege["mit Funding, ohne Officer"],
    )

    assert voll.anteil_uebersehen == pytest.approx(0.336, abs=0.002)
    assert voll.anteil_rein == pytest.approx(0.296, abs=0.002)
    assert not voll.urteil_kippt
    assert voll.ohne_sperre_funding > 0

    # Und der Gatewert ist 'wie gebaut': Eintrag und Gate messen dasselbe.
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
    gate = gate_cost_stress(
        genom,
        frames[symbole[0]],
        configs[symbole[0]],
        GateThresholds(),
        frames=frames,
        configs=configs,
    )

    assert gate.value == pytest.approx(betraege["wie gebaut"], abs=0.02)
