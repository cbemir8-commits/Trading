"""Eine Gate-Bilanz, die sagt, was sie wert ist - Befund 350.

Befund 332 hat sechzehn Typen aufgelistet, die eine Gate-Bilanz tragen und nicht
sagen koennen, ob jedes Gate geurteilt hat. 338, 346, 347 und 349 haben fuenf
davon einzeln nachgezogen - jeder mit eigenem Feld, eigenem Befehl, eigenem Test.
**Elf standen noch offen, und einzeln waeren das elf Male dasselbe.**

``research/gatebilanz.py`` macht daraus einen Mechanismus: Wer ``bestanden``,
``gesamt`` und ``trades`` traegt, erschliesst die Antwort aus der Trade-Zahl -
unter 30 setzen Regime-Aufteilung und Deflated Sharpe aus, unter 20 auch
Monte-Carlo.

**Das ist die schwaechere Auskunft, und sie heisst auch so.** Erschlossen ist
eine Untergrenze: Es koennen mehr Gates ausgesetzt haben, etwa wenn
``run_expensive`` aus war. Wo ein Typ seine Aussetzer **gemeldet** bekommt, ist
die Zahl genau, und dort gewinnt sie.

Acht Typen mischen die Bilanz bei. Offen bleiben drei - genau die, die keine
Trade-Zahl tragen: ``admission.Zulassungsbedingungen``,
``instrument.Gebuehrenstufe``, ``ratenbild.Ratenprobe``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from research.aussetzer import SCHWELLEN
from research.gatebilanz import Gatebilanz, erschlossen_bei


@dataclass(frozen=True, slots=True)
class Probe(Gatebilanz):
    """Ein Traeger wie die echten - ``frozen`` und ``slots``."""

    bestanden: int
    gesamt: int
    trades: int


@dataclass(frozen=True, slots=True)
class ProbeMitMeldung(Gatebilanz):
    """Einer, der seine Aussetzer selbst kennt."""

    bestanden: int
    gesamt: int
    trades: int
    uebersprungen: int = 0


class TestDieSchwellenSindDatenUndKeinText:
    def test_sie_kommen_aus_einer_quelle(self) -> None:
        assert SCHWELLEN == {
            "Regime-Aufteilung": 30,
            "Deflated Sharpe": 30,
            "Monte-Carlo": 20,
        }

    def test_ueber_dreissig_setzt_nichts_aus(self) -> None:
        assert erschlossen_bei(158) == ()
        assert erschlossen_bei(30) == ()

    def test_unter_dreissig_zwei(self) -> None:
        assert erschlossen_bei(29) == ("Deflated Sharpe", "Regime-Aufteilung")

    def test_unter_zwanzig_drei(self) -> None:
        assert erschlossen_bei(19) == (
            "Deflated Sharpe", "Monte-Carlo", "Regime-Aufteilung",
        )

    def test_die_reihenfolge_ist_fest(self) -> None:
        """Eine Menge in wechselnder Reihenfolge waere in einem Bericht nicht
        wiederzuerkennen."""
        assert erschlossen_bei(0) == erschlossen_bei(0)
        assert list(erschlossen_bei(0)) == sorted(erschlossen_bei(0))

    def test_eine_negative_zahl_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="keine Stichprobe"):
            erschlossen_bei(-1)


class TestDieBeimischungRechnetEhrlich:
    def test_ueber_der_schwelle_bleibt_alles_wie_vorher(self) -> None:
        p = Probe(bestanden=9, gesamt=11, trades=158)

        assert not p.bilanz_zu_gut
        assert (p.bestanden_ehrlich, p.geurteilt_ehrlich) == (9, 11)
        assert p.bilanzsatz() == "9/11 Gates"

    def test_ohne_handel_ist_die_bilanz_zu_gut(self) -> None:
        """Der Fall aus Befund 322: fuenf Gates gutgeschrieben, weil nichts
        schiefgehen kann, wo nichts passiert."""
        p = Probe(bestanden=5, gesamt=11, trades=0)

        assert p.bilanz_zu_gut
        assert p.uebersprungen_ehrlich == 3
        assert (p.bestanden_ehrlich, p.geurteilt_ehrlich) == (2, 8)

    def test_der_satz_nennt_grund_und_rohes_paar(self) -> None:
        satz = Probe(bestanden=5, gesamt=11, trades=0).bilanzsatz()

        assert "2/8 Gates" in satz
        assert "bei 0 Trades aus" in satz
        assert "roh 5/11" in satz

    def test_bestanden_faellt_nicht_unter_null(self) -> None:
        assert Probe(bestanden=1, gesamt=11, trades=0).bestanden_ehrlich == 0

    def test_geurteilt_faellt_nicht_unter_null(self) -> None:
        """Ein Typ mit zwei Gates und drei erschlossenen Aussetzern: Die Zahl
        wird gedeckelt und nicht negativ."""
        p = Probe(bestanden=1, gesamt=2, trades=0)

        assert p.uebersprungen_ehrlich == 2
        assert p.geurteilt_ehrlich == 0


class TestGemeldetSchlaegtErschlossen:
    def test_die_gemeldete_zahl_gewinnt_wenn_sie_hoeher_ist(self) -> None:
        """Erschlossen sind zwei, gemeldet sind vier - dann sind es vier.
        'run_expensive' aus laesst zwei weitere aussetzen, und das erschliesst
        keine Trade-Zahl."""
        p = ProbeMitMeldung(bestanden=9, gesamt=11, trades=29, uebersprungen=4)

        assert p.uebersprungen_ehrlich == 4
        assert p.bestanden_ehrlich == 5

    def test_eine_gemeldete_null_ueberstimmt_die_erschliessung_nicht(self) -> None:
        """**Die Zeile, die den Mechanismus ehrlich haelt.** Sonst waere eine
        nicht gefuellte Meldung die verbindliche Auskunft."""
        p = ProbeMitMeldung(bestanden=5, gesamt=11, trades=0, uebersprungen=0)

        assert p.uebersprungen_ehrlich == 3
        assert p.bilanz_zu_gut

    def test_eine_liste_wird_gezaehlt(self) -> None:
        """``nachpruefung.Ergebnis`` meldet Namen, nicht eine Zahl."""

        @dataclass(frozen=True, slots=True)
        class MitNamen(Gatebilanz):
            bestanden: int
            gesamt: int
            trades: int
            uebersprungen: tuple[str, ...] = ()

        p = MitNamen(
            bestanden=9, gesamt=11, trades=158,
            uebersprungen=("Parameter-Plateau", "Kosten-Stress"),
        )

        assert p.uebersprungen_ehrlich == 2
        assert p.bestanden_ehrlich == 7


class TestDieAchtTraegerSindEchteTypen:
    """Nicht nur eingetragen, sondern angeschlossen - und die Typen sind
    ``frozen``/``slots``, also war eine Basisklasse mit Feldern keine Option."""

    NAMEN = (
        "research.aufloesung.Messung",
        "research.aufstellung.Marktsatz",
        "research.betriebspunkt.Betriebspunkt",
        "research.decke.Fenster",
        "research.decke.Stufe",
        "research.instrument.Lauf",
        "research.sperrprobe.Ergebnis",
        "research.stand.Lage",
    )

    @pytest.mark.parametrize("name", NAMEN)
    def test_jeder_mischt_die_bilanz_bei(self, name: str) -> None:
        import importlib

        modul, klasse = name.rsplit(".", 1)
        obj = getattr(importlib.import_module(modul), klasse)

        assert issubclass(obj, Gatebilanz)

    def test_eine_echte_messung_rechnet_es_durch(self) -> None:
        from research.aufloesung import Messung

        m = Messung(
            name="Trendfolge Ausbruch", trades=0, cagr=0.0, rueckgang=0.0,
            sharpe=0.0, bestanden=5, gesamt=11,
        )

        assert m.bilanz_zu_gut
        assert m.bestanden_ehrlich == 2
        assert "roh 5/11" in m.bilanzsatz()

    def test_und_der_bestand_bleibt_unberuehrt(self) -> None:
        """Die Gegenprobe am echten Kandidaten: 158 Trades, nichts setzt aus."""
        from research.aufloesung import Messung

        m = Messung(
            name="Trend 50 Tage mit Konfluenz", trades=158, cagr=14.34,
            rueckgang=9.87, sharpe=1.58, bestanden=9, gesamt=11,
        )

        assert not m.bilanz_zu_gut
        assert m.bilanzsatz() == "9/11 Gates"


class TestDasVerzeichnisIstNachgezogen:
    def test_acht_erschliessen_drei_bleiben_offen(self) -> None:
        from tests.test_gatezahlen import MIT_ERSCHLOSSENEM, OFFEN

        assert len(MIT_ERSCHLOSSENEM) == 8
        assert sorted(OFFEN) == [
            "research.admission.Zulassungsbedingungen",
            "research.instrument.Gebuehrenstufe",
            "research.ratenbild.Ratenprobe",
        ]

    def test_die_drei_tragen_keine_trade_zahl(self) -> None:
        """Deshalb sind sie offen und nicht aus Bequemlichkeit."""
        from tests.test_gatezahlen import OFFEN, _traeger

        traeger = _traeger()

        for name in OFFEN:
            assert "trades" not in traeger[name], name

    def test_der_registereintrag_nennt_beides(self) -> None:
        from research.stand import OFFEN as OFFENE_RICHTUNGEN

        eintrag = next(r for r in OFFENE_RICHTUNGEN if "Gate-Zahlen" in r.name)

        assert eintrag.name.startswith("Drei")
        assert "wurde ein Mechanismus" in eintrag.ergebnis
        assert "schwaechere" in eintrag.ergebnis
        assert eintrag.massgeblich >= 350
