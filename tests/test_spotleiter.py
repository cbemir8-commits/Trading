"""Die Messlatte und die Herkunft ihrer Leiter - Befund 341.

Sechster Verdachtsfall aus der Wache von Befund 335: **'Mindestrendite von 15 %
im Jahr'**, Fundstelle Befund 57, massgeblich 281 - und eines der zwei Gates,
die am Spot-Punkt ueberhaupt noch offen sind.

**Nachgemessen: Die Zeile des Bestands stimmt.** Auf dem Code von heute, mit
einem vollen Walk-Forward am Spot-Punkt:

    Messlatte            14,3390   gegen  15       fehlt
    Rueckgang             9,8687   gegen  12       haelt
    Schlechtestes Jahr   -9,6100   gegen -10       haelt
    Deflated Sharpe       0,5826   gegen   0,95    fehlt
                                                   9 von 11

Das kostet keinen Versuch: derselbe Kandidat, dieselben Daten, seine eigene
Stellung - keine neue Hypothese.

**Die anderen fuenf Stellungen stehen alle in einer Datei.** ``cli vereinbar
--spot`` liest sechs Punkte, und alle sechs kommen aus
``reports/machbarkeit/2026-09-14_005951.json`` - dem einzigen
Machbarkeitsbericht mit vermerktem Betriebspunkt. Befund 334 hat das Alter
nachgetragen ("12 Tage alt"); dass gleiches Alter hier **eine** Messung heisst
und nicht sechs gleich frische, stand nicht dabei.

Nachzumessen waere sie nur mit einem Reglerscan - und ob der am Bestand ein
Versuch ist, ist eine offene Frage beim Nutzer. Deshalb steht es im Eintrag und
wurde nicht gefahren.
"""

from __future__ import annotations

from datetime import date

import pytest

from research.vereinbar import Messpunkt, Vorrat

#: Die Gate-Werte des Bestands am Spot-Punkt (Befund 341, nachgemessen).
GEMESSEN: dict[str, tuple[float, float, bool]] = {
    # Gate: Wert, Schwelle, besteht
    "Messlatte": (14.3390, 15.0, False),
    "Drawdown": (9.8687, 12.0, True),
    "Schlechtestes Jahr": (-9.6100, -10.0, True),
    "Deflated Sharpe": (0.5826, 0.95, False),
}


def _punkt(stellung: float, datei: str) -> Messpunkt:
    return Messpunkt(
        stellung=stellung,
        werte={"cagr": 15.0, "rueckgang": 10.0},
        betriebspunkt="Spot (kein Hebel, kein Funding)",
        gemessen=datei,
    )


class TestDieHerkunftDerLeiter:
    """**Befund 341.** Sechs Stellungen, alle gleich alt, sehen nach sechs
    Messungen aus."""

    def test_eine_datei_ist_eine_einzelquelle(self) -> None:
        vorrat = Vorrat(
            punkte=[_punkt(s, "2026-09-14_005951") for s in (19.3, 20.5, 21.0)]
        )

        assert vorrat.quellen == ("2026-09-14_005951",)
        assert vorrat.einzelquelle

    def test_zwei_dateien_sind_keine(self) -> None:
        vorrat = Vorrat(
            punkte=[
                _punkt(19.3, "2026-09-14_005951"),
                _punkt(20.5, "2026-08-22_071858"),
            ]
        )

        assert len(vorrat.quellen) == 2
        assert not vorrat.einzelquelle

    def test_ein_einzelner_punkt_ist_keine_leiter(self) -> None:
        """Bei einer Stellung ist "alle aus einer Datei" keine Auskunft - es
        gibt nichts zu verwechseln."""
        vorrat = Vorrat(punkte=[_punkt(19.3, "2026-09-14_005951")])

        assert not vorrat.einzelquelle

    def test_ohne_datum_gibt_es_keine_quelle(self) -> None:
        vorrat = Vorrat(
            punkte=[
                Messpunkt(stellung=s, werte={"cagr": 15.0}) for s in (19.3, 21.0)
            ]
        )

        assert vorrat.quellen == ()
        assert not vorrat.einzelquelle

    def test_der_altersatz_nennt_die_datei(self) -> None:
        vorrat = Vorrat(
            punkte=[_punkt(s, "2026-09-14_005951") for s in (19.3, 20.5, 21.0)]
        )
        satz = vorrat.altersatz(date(2026, 9, 26))

        assert "12 Tage alt" in satz
        assert "alle in einer Datei" in satz
        assert "2026-09-14_005951" in satz

    def test_und_warum_das_zaehlt(self) -> None:
        """Nicht "eine Datei", sondern was daran haengt: Faellt sie weg, meldet
        die Tabelle nichts."""
        vorrat = Vorrat(
            punkte=[_punkt(s, "2026-09-14_005951") for s in (19.3, 20.5)]
        )

        assert "einmal gemessen" in vorrat.altersatz(date(2026, 9, 26))

    def test_bei_mehreren_quellen_bleibt_der_satz_weg(self) -> None:
        """Ein Satz, der immer dasteht, wird nicht gelesen."""
        vorrat = Vorrat(
            punkte=[
                _punkt(19.3, "2026-09-14_005951"),
                _punkt(20.5, "2026-08-22_071858"),
            ]
        )

        assert "alle in einer Datei" not in vorrat.altersatz(date(2026, 9, 26))


class TestDieLeiterStehtWirklichAufEinerDatei:
    """Nicht behauptet, sondern an den Berichten auf der Platte geprueft."""

    @staticmethod
    def _vorrat() -> Vorrat:
        from pathlib import Path

        from research.vereinbar import lade

        return lade(Path("reports/machbarkeit"), betriebspunkt="Spot")

    def test_der_spot_punkt_hat_genau_einen_bericht(self) -> None:
        vorrat = self._vorrat()

        assert len(vorrat.quellen) == 1, vorrat.quellen
        assert vorrat.einzelquelle

    def test_und_sechs_stellungen_darin(self) -> None:
        vorrat = self._vorrat()

        assert [p.stellung for p in vorrat.punkte] == [19.3, 20.5, 21.0, 21.5, 22.0, 25.0]

    def test_die_uebrigen_berichte_tragen_keinen_betriebspunkt(self) -> None:
        """Der Grund, warum es nur einer ist - und er steht schon im
        Hinweis."""
        vorrat = self._vorrat()

        assert vorrat.ohne_vermerk == 45
        assert "**ohne vermerkten Betriebspunkt**" in vorrat.hinweis()


class TestDerEintragIstNachgemessen:
    @staticmethod
    def _eintrag():
        from research.stand import ENTSCHEIDUNGEN

        return next(
            e for e in ENTSCHEIDUNGEN
            if e.frage == "Mindestrendite von 15 % im Jahr"
        )

    def test_die_reproduktion_steht_da(self) -> None:
        zahl = self._eintrag().zahl

        assert "14,3390" in zahl
        assert "9,8687" in zahl
        assert "-9,61" in zahl

    def test_dass_sie_keinen_versuch_kostet_steht_dabei(self) -> None:
        """Der Satz, der eine Nachmessung von einem Sweep trennt."""
        zahl = self._eintrag().zahl

        assert "kostet keinen Versuch" in zahl
        assert "keine neue Hypothese" in zahl

    def test_die_einzelquelle_ist_benannt(self) -> None:
        zahl = self._eintrag().zahl

        assert "stehen alle in einer Datei" in zahl
        assert "'Drei von sechs' ist damit eine Messung und nicht sechs" in zahl

    def test_der_offene_punkt_ist_genannt_statt_umgangen(self) -> None:
        """Ein Reglerscan waere die einfache Antwort gewesen - und haette eine
        Frage entschieden, die beim Nutzer liegt."""
        zahl = self._eintrag().zahl

        assert "Zaehlt ein Sweep am Bestand als Versuch?" in zahl

    def test_die_entscheidung_bleibt_wo_sie_war(self) -> None:
        warum = self._eintrag().warum

        assert "An der Entscheidung aendert das nichts" in warum
        assert "0,66 Punkten" in warum

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 57
        assert eintrag.massgeblich == 341

    def test_die_wache_ist_mitgezogen(self) -> None:
        """Der Abschnitt nennt den offenen Punkt beim Namen - als Grund, etwas
        **nicht** zu tun. Gelesen und eingetragen, sonst stuende er beim
        naechsten Lauf wieder als neu da."""
        from research.nachmessung import GELESEN

        assert GELESEN["Zaehlt ein Sweep am Bestand als Versuch?"] >= 341


@pytest.mark.daten
@pytest.mark.langsam
def test_der_spot_punkt_reproduziert() -> None:
    """**Die Bindung.** Die Zeile des Bestands stand in einem Bericht und
    nirgends in einem Test. Zwoelf Tage und fuenfundzwanzig Befunde spaeter
    haette niemand gemerkt, wenn sie sich bewegt haette.
    """
    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from core.config import get_settings
    from core.models import Interval
    from research.admission import load_trials
    from research.gates import GateThresholds, evaluate_gates
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    e = get_settings()
    versuche = load_trials(Path(e.paths.state) / "trials.json")
    frames, _, _ = cli._korb_daten(symbole, Interval("D"), e)
    configs = cli._spotconfigs(symbole, e)
    genom = cli._ohne_hebel(spitzenkandidat())
    bericht = run_portfolio_walkforward(
        frames, lambda g=genom: compile_genome(g), configs
    )
    gates = evaluate_gates(
        genom,
        bericht,
        frames[symbole[0]],
        configs[symbole[0]],
        trials_so_far=versuche,
        thresholds=GateThresholds(),
        frames=frames,
        configs=configs,
    )
    nach_name = {r.name: r for r in gates.results}

    for name, (wert, schwelle, besteht) in GEMESSEN.items():
        ergebnis = nach_name[name]

        assert ergebnis.value == pytest.approx(wert, abs=0.005), name
        assert ergebnis.threshold == pytest.approx(schwelle, abs=1e-9), name
        assert ergebnis.passed is besteht, name

    assert sum(1 for r in gates.results if r.passed) == 9
    assert len(gates.results) == 11

    # Die 0,66 Punkte, auf denen die Entscheidung steht.
    fehlt = nach_name["Messlatte"].threshold - nach_name["Messlatte"].value

    assert fehlt == pytest.approx(0.66, abs=0.01)

    # Und derselbe Vergleich, den der Bericht seit zwoelf Tagen behauptet:
    # Was gespeichert ist, kommt heute wieder heraus.
    from research.vereinbar import lade

    gespeichert = next(
        p for p in lade(Path("reports/machbarkeit"), betriebspunkt="Spot").punkte
        if p.stellung == 19.3
    )

    assert gespeichert.werte["cagr"] == pytest.approx(
        nach_name["Messlatte"].value, abs=0.005
    )
    assert gespeichert.werte["rueckgang"] == pytest.approx(
        nach_name["Drawdown"].value, abs=0.005
    )
    assert gespeichert.werte["schlechtestes_jahr"] == pytest.approx(
        nach_name["Schlechtestes Jahr"].value, abs=0.005
    )
