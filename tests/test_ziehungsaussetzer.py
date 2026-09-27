"""Die Teststaerke-Leiter zaehlte uebersprungene Gates mit - Befund 347.

Befund 321/322 hat ``uebersprungen`` in ``teststaerke.Stufe`` nachgetragen: Die
Leiter einer einzelnen Saat zaehlte ein ausgesetztes Gate als bestanden.
``ziehung.Ziehung`` mittelt **dieselbe** Leiter ueber Saaten - und blieb stehen.

**Und hier trifft es zu.** Ein gepflanzter Trend heisst laengeres Halten heisst
weniger Trades, und unter 30 Trades setzen Regime-Aufteilung und Deflated
Sharpe aus, unter 20 auch Monte-Carlo. Gemessen ueber drei Saaten:

    Anteil   Trades         geurteilt   Aussetzer
        0%   160,0 +-0,0      7,0        -
        5%    86,0 +-14,9     7,3        -
       10%    60,7 +-13,9     8,7        -
       20%    30,0 +-6,6      7,7        4 Gates in 2 von 3 Ziehungen
       35%    20,0 +-4,4      5,0        8 Gates in 3 von 3
       50%    16,7 +-5,7      6,0        9 Gates in 3 von 3

Die alte Spalte zeigte dort 9,0 / 7,7 / 9,0 - **mehr** als auf der 0-%-Sprosse,
also las sie sich, als helfe ein gepflanzter Trend. Geurteilt sind es 7,7 / 5,0 /
6,0, und damit deutlich schlechter.

**Die Richtung von Befund 54 wird dadurch nicht schwaecher, sondern staerker.**
Seine Aussage - Qualitaet und Menge sind gekoppelt, es gibt keine Einstellung,
bei der beides zugleich reicht - stand auf dieser Leiter. Die berichtigten
Zahlen stuetzen sie deutlicher als die alten.

Und in den Berichten steht es schon: ``reports/teststaerke/2026-08-14_171333``
haelt bei 20 % Anteil **29 Trades** und "10 von 11" fest, bei einem Deflated
Sharpe von 0,0 - also einem Gate, das nie geurteilt hat.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from research.ziehung import Sprosse, Ziehung

#: Die gemessene Leiter (Befund 347, drei Saaten 11/12/13).
GEMESSEN: tuple[tuple[float, float, float, int, int], ...] = (
    # Anteil, Trades im Mittel, geurteilte Gates im Mittel, Aussetzer,
    # Ziehungen mit Aussetzern
    (0.0, 160.0, 7.0, 0, 0),
    (0.05, 86.0, 7.3, 0, 0),
    (0.10, 60.7, 8.7, 0, 0),
    (0.20, 30.0, 7.7, 4, 2),
    (0.35, 20.0, 5.0, 8, 3),
    (0.50, 16.7, 6.0, 9, 3),
)


def _ziehung(**rest) -> Ziehung:
    daten = {
        "saat": 11, "anteil": 0.2, "trades": 29, "sharpe_je_trade": 0.49,
        "dsr": 0.0, "bestanden": 10, "gesamt": 11,
    }
    daten.update(rest)
    return Ziehung(**daten)


class TestEineZiehungSagtEsJetzt:
    def test_geurteilt_ist_gesamt_ohne_aussetzer(self) -> None:
        assert _ziehung().geurteilt == 11
        assert _ziehung(uebersprungen=3).geurteilt == 8

    def test_ein_aussetzer_zaehlt_nicht_als_bestanden(self) -> None:
        """**Der Fall aus dem Bericht vom 14.08.**: 29 Trades, "10 von 11",
        Deflated Sharpe 0,0."""
        z = _ziehung(uebersprungen=3)

        assert z.bestanden_echt == 7
        assert z.geurteilt == 8

    def test_der_vorgabewert_ist_kein_aussetzer(self) -> None:
        """Die sichere Richtung: Wer das Feld nicht setzt, bekommt die alte
        Zahl, und ein Aussetzer muss ausdruecklich gemeldet werden."""
        assert _ziehung().uebersprungen == 0
        assert _ziehung().bestanden_echt == 10

    def test_bestanden_echt_faellt_nicht_unter_null(self) -> None:
        assert _ziehung(bestanden=1, uebersprungen=5).bestanden_echt == 0

    def test_unsinn_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="uebersprungene von 11"):
            _ziehung(uebersprungen=12)
        with pytest.raises(ValueError, match="bestandenen Gates"):
            _ziehung(bestanden=12)
        with pytest.raises(ValueError, match="ohne Gates"):
            _ziehung(gesamt=0)


class TestDieSprosseZaehltSieZusammen:
    def test_aussetzer_ueber_alle_ziehungen(self) -> None:
        s = Sprosse(
            anteil=0.2,
            ziehungen=[
                _ziehung(saat=11, uebersprungen=2),
                _ziehung(saat=12, uebersprungen=2),
                _ziehung(saat=13),
            ],
        )

        assert s.aussetzer == 4
        assert s.ziehungen_mit_aussetzern == 2
        assert s.anzahl == 3

    def test_das_mittel_der_geurteilten_ist_abrufbar(self) -> None:
        """``werte`` liest ueber ``getattr`` - die Eigenschaft genuegt, es
        braucht kein zweites Feld."""
        s = Sprosse(
            anteil=0.35,
            ziehungen=[
                _ziehung(bestanden=8, uebersprungen=3),
                _ziehung(bestanden=7, uebersprungen=3),
            ],
        )

        assert s.mittel("bestanden_echt") == pytest.approx(4.5)
        assert s.mittel("bestanden") == pytest.approx(7.5)
        assert s.mittel("geurteilt") == pytest.approx(8.0)

    def test_ohne_aussetzer_sind_beide_gleich(self) -> None:
        s = Sprosse(anteil=0.0, ziehungen=[_ziehung(bestanden=7), _ziehung(bestanden=7)])

        assert s.mittel("bestanden_echt") == s.mittel("bestanden")
        assert s.aussetzer == 0


class TestDerBefehlZeigtDieEhrlicheSpalte:
    @staticmethod
    def _quelle() -> str:
        import ast

        baum = ast.parse(pathlib.Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
            and n.name == "_teststaerke_ueber_saaten"
        )

    def test_das_feld_wird_gefuellt(self) -> None:
        quelle = self._quelle()

        assert "uebersprungen=sum(" in quelle
        assert "if r.status is GateStatus.SKIP" in quelle

    def test_gemittelt_wird_das_geurteilte(self) -> None:
        quelle = self._quelle()

        assert "spalte('bestanden_echt', 1)" in quelle
        assert "spalte('bestanden', 1)" not in quelle

    def test_die_aussetzer_stehen_daneben(self) -> None:
        """Ohne die Anmerkung liest sich '5,0' wie eine Bilanz aus elf
        Urteilen."""
        quelle = self._quelle()

        assert "Gates ohne Urteil in" in quelle
        assert "if s.aussetzer" in quelle


class TestDerBerichtVom14August:
    """Der Beleg lag auf der Platte, bevor jemand danach gesucht hat."""

    @staticmethod
    def _stufen():
        datei = pathlib.Path("reports/teststaerke/2026-08-14_171333.json")
        return json.loads(datei.read_text()).get("stufen") or []

    def test_die_zeile_mit_29_trades_zeigt_zehn_von_elf(self) -> None:
        stufen = self._stufen()
        zwanzig = next(s for s in stufen if s.get("anteil") == 0.2)

        assert zwanzig["trades"] == 29
        assert (zwanzig["bestanden"], zwanzig["gesamt"]) == (10, 11)

    def test_und_der_deflated_sharpe_stand_bei_null(self) -> None:
        """0,0 bei 29 Trades heisst nicht "kein Vorteil", sondern
        "uebersprungen" - die Schwelle liegt bei 30."""
        zwanzig = next(s for s in self._stufen() if s.get("anteil") == 0.2)

        assert zwanzig["dsr"] == 0.0

    def test_der_bericht_traegt_keine_aussetzer_angabe(self) -> None:
        """Deshalb war es nicht zu sehen."""
        assert all("uebersprungen" not in s for s in self._stufen())


class TestDerRegistereintrag:
    @staticmethod
    def _eintrag():
        from research.stand import OFFEN

        return next(r for r in OFFEN if "Gate-Zahlen" in r.name)

    def test_die_leiter_steht_im_eintrag(self) -> None:
        """Den **Abgleich** von Name und Liste prueft
        ``test_aussetzer.py``; hier steht die Aussage dieses Befunds. Eine
        zweite feste Zahl waere ein zweiter Test, der fuer nichts bricht -
        dreimal ist das schon passiert (342, 346, 347)."""
        ergebnis = self._eintrag().ergebnis

        assert "ziehung.Ziehung" in ergebnis

    def test_die_gemessenen_zahlen_stehen_drin(self) -> None:
        ergebnis = self._eintrag().ergebnis

        assert "7,7 / 5,0 / 6,0" in ergebnis
        assert "9,0 / 7,7 / 9,0" in ergebnis

    def test_die_falsche_lesart_ist_benannt(self) -> None:
        """Der Punkt, der es zu einem Befund macht: Die alte Spalte las sich,
        als helfe ein gepflanzter Trend."""
        ergebnis = self._eintrag().ergebnis

        assert "als helfe ein gepflanzter Trend" in ergebnis

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 332
        # **"Mindestens", weil der Eintrag geteilt ist.** 346, 347 und 348
        # haben ihn alle bewegt, und dreimal in Folge hat eine feste Zahl in
        # einem fremden Test dafuer gebrochen. Wo die Fundstelle die Aussage
        # ist, steht sie fest; hier ist die Aussage die Leiter.
        assert eintrag.massgeblich >= 347


@pytest.mark.daten
@pytest.mark.langsam
def test_die_leiter_setzt_oben_wirklich_aus() -> None:
    """**Die Bindung.** Drei Saaten, sechs Sprossen - und ab 20 % Anteil setzen
    Gates aus. Ohne diesen Test war das nur in einer Berichtsdatei vom August zu
    sehen, und dort ohne Kennzeichnung.

    Kostet keinen Versuch: gepflanzte Reihen, dieselbe Regel.
    """
    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from core.config import get_settings
    from core.models import Interval
    from research.admission import load_trials
    from research.gates import GateStatus, GateThresholds, evaluate_gates
    from research.seeds import spitzenkandidat
    from research.teststaerke import pflanze_trend, regimefolge
    from strategy.compiler import compile_genome

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    e = get_settings()
    versuche = load_trials(Path(e.paths.state) / "trials.json")
    frames, configs, _ = cli._korb_daten(symbole, Interval("D"), e)
    genom = spitzenkandidat()
    laenge = max(len(f) for f in frames.values())
    gemessen: dict[float, list[Ziehung]] = {a: [] for a, *_ in GEMESSEN}

    for saat in (11, 12, 13):
        regime = regimefolge(laenge, dauer=60, saat=saat)
        for anteil, *_ in GEMESSEN:
            gepflanzt = {
                name: pflanze_trend(frame, anteil=anteil, regime=regime)
                for name, frame in frames.items()
            }
            bericht = run_portfolio_walkforward(
                gepflanzt, lambda: compile_genome(genom), configs
            )
            gates = evaluate_gates(
                genom, bericht, next(iter(gepflanzt.values())),
                next(iter(configs.values())), trials_so_far=versuche,
                thresholds=GateThresholds(), frames=gepflanzt, configs=configs,
            )
            gemessen[anteil].append(
                Ziehung(
                    saat=saat, anteil=anteil,
                    trades=len(list(bericht.all_trades)),
                    sharpe_je_trade=0.0, dsr=0.0,
                    bestanden=sum(1 for r in gates.results if r.passed),
                    gesamt=len(gates.results),
                    uebersprungen=sum(
                        1 for r in gates.results if r.status is GateStatus.SKIP
                    ),
                )
            )

    for anteil, trades, geurteilt, aussetzer, mit in GEMESSEN:
        s = Sprosse(anteil=anteil, ziehungen=gemessen[anteil])

        assert s.mittel("trades") == pytest.approx(trades, abs=0.6), anteil
        assert s.mittel("bestanden_echt") == pytest.approx(geurteilt, abs=0.1), anteil
        assert s.aussetzer == aussetzer, anteil
        assert s.ziehungen_mit_aussetzern == mit, anteil

    # Der Punkt: Die rohe Spalte laege oben ueber der 0-%-Sprosse, die
    # geurteilte darunter.
    null = Sprosse(anteil=0.0, ziehungen=gemessen[0.0])
    oben = Sprosse(anteil=0.35, ziehungen=gemessen[0.35])

    assert oben.mittel("bestanden") > null.mittel("bestanden_echt")
    assert oben.mittel("bestanden_echt") < null.mittel("bestanden_echt")
