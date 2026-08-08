"""Ist ein Ergebnis mit diesem Regler ueberhaupt erreichbar?

Zwei Tests tragen diese Datei:

* ``test_konflikt_wird_erkannt`` - der Fall, um den es geht. Zwei Gates, die
  je fuer sich halten und nie zugleich. Das ist kein "knapp daneben", sondern
  ein Beweis, dass diese Achse keine Loesung enthaelt.
* ``test_zwischenraeume_bleiben_offen`` - die Ehrlichkeitsschranke. Eine
  Abtastung misst Punkte, keine Strecken; ein leeres Fenster gilt nur so weit,
  wie die Aufloesung reicht. Wer das unterschlaegt, verkauft eine Vermutung
  als Befund.
"""

from __future__ import annotations

import pytest

from research.machbarkeit import (
    Machbarkeit,
    Punkt,
    Stand,
    aus_gate_report,
)


def punkt(stellung: float, **gates: bool | tuple[bool, float, float]) -> Punkt:
    """Ein Messpunkt aus Kurzschreibweise.

    ``gate=True`` genuegt, wo nur bestanden/durchgefallen zaehlt; wo der Wert
    gebraucht wird, steht ein Tripel ``(bestanden, wert, schwelle)``.
    """
    staende = {}
    for name, wert in gates.items():
        if isinstance(wert, tuple):
            staende[name] = Stand(bestanden=wert[0], wert=wert[1], schwelle=wert[2])
        else:
            staende[name] = Stand(bestanden=wert, wert=1.0 if wert else 0.0,
                                  schwelle=1.0)
    return Punkt(stellung=stellung, gates=staende)


class TestFenster:
    def test_fenster_wird_gefunden(self) -> None:
        m = Machbarkeit(
            regler="Vola-Ziel",
            einheit="%",
            punkte=[
                punkt(14.0, rendite=False, rueckgang=True),
                punkt(20.0, rendite=True, rueckgang=True),
                punkt(30.0, rendite=True, rueckgang=False),
            ],
        )

        assert [p.stellung for p in m.fenster] == [20.0]
        assert "Fenster gefunden" in m.urteil()
        assert "20" in m.urteil()

    def test_ohne_gates_kein_fenster(self) -> None:
        """Ein Punkt ohne ausgewertete Gates darf nicht als Erfolg zaehlen."""
        m = Machbarkeit(regler="x", punkte=[Punkt(stellung=1.0, gates={})])

        assert m.fenster == []

    def test_ohne_messung_kein_urteil(self) -> None:
        m = Machbarkeit(regler="x", punkte=[])

        assert "Nichts gemessen" in m.urteil()
        assert m.tabelle() == "Nichts gemessen."


class TestKonflikt:
    def test_konflikt_wird_erkannt(self) -> None:
        """**Der Fall, um den es geht.**

        ``rendite`` haelt erst oben, ``rueckgang`` nur unten. Beide halten
        irgendwo, nie zusammen - der Regler enthaelt keine Loesung.
        """
        m = Machbarkeit(
            regler="Vola-Ziel",
            einheit="%",
            punkte=[
                punkt(14.0, rendite=False, rueckgang=True),
                punkt(22.0, rendite=False, rueckgang=True),
                punkt(25.0, rendite=False, rueckgang=False),
                punkt(28.0, rendite=True, rueckgang=False),
            ],
        )

        assert m.fenster == []
        (konflikt,) = m.konflikte
        assert {konflikt.a, konflikt.b} == {"rendite", "rueckgang"}
        assert konflikt.uebergang == (22.0, 28.0)
        assert "Konflikt" in m.urteil()

    def test_zwischenraeume_bleiben_offen(self) -> None:
        """**Die Ehrlichkeitsschranke.**

        Zwischen 22 und 28 liegt ein gemessener Punkt, also zwei
        Zwischenraeume - und in beiden koennte eine Loesung stecken. Das Urteil
        muss das sagen und die naechsten Stellungen nennen.
        """
        m = Machbarkeit(
            regler="Vola-Ziel",
            einheit="%",
            punkte=[
                punkt(22.0, rendite=False, rueckgang=True),
                punkt(25.0, rendite=False, rueckgang=False),
                punkt(28.0, rendite=True, rueckgang=False),
            ],
        )

        (konflikt,) = m.konflikte
        assert konflikt.luecken == ((22.0, 25.0), (25.0, 28.0))
        assert konflikt.mitten == [23.5, 26.5]
        assert m.aufloesung == 3.0
        assert m.verfeinerung() == [23.5, 26.5]
        assert "Ungeprueft" in m.urteil()

    def test_benachbarte_stufen_haben_einen_zwischenraum(self) -> None:
        m = Machbarkeit(
            regler="x",
            punkte=[
                punkt(1.0, a=True, b=False),
                punkt(2.0, a=False, b=True),
            ],
        )

        (konflikt,) = m.konflikte
        assert konflikt.luecken == ((1.0, 2.0),)
        assert m.verfeinerung() == [1.5]

    def test_ein_gate_ausser_reichweite_ist_kein_konflikt(self) -> None:
        """Wer ueberall fehlt, steht mit niemandem in Konflikt.

        Der Unterschied ist nicht sprachlich: Ein Konflikt schliesst die
        Achse ab, ein unerreichtes Gate verlangt eine Aenderung woanders.
        """
        m = Machbarkeit(
            regler="x",
            punkte=[
                punkt(1.0, a=True, nie=(False, 0.80, 0.95)),
                punkt(2.0, a=True, nie=(False, 0.79, 0.95)),
            ],
        )

        assert m.konflikte == []
        assert m.nie_erfuellt == ["nie"]


class TestHebelwirkung:
    def test_gemessene_lage_des_deflated_sharpe(self) -> None:
        """Die echten Zahlen: 0,776 bis 0,799 bei einer Schwelle von 0,95.

        Der Regler bewegt den Wert um 0,023, es fehlen 0,151. Damit ist das
        Gate ueber diese Achse nicht erreichbar - und keine feinere Abtastung
        aendert daran etwas.
        """
        m = Machbarkeit(
            regler="Vola-Ziel",
            punkte=[
                punkt(14.0, dsr=(False, 0.776, 0.95)),
                punkt(19.3, dsr=(False, 0.799, 0.95)),
                punkt(32.0, dsr=(False, 0.799, 0.95)),
            ],
        )

        w = m.hebelwirkung("dsr")

        assert w is not None
        assert w.spanne == pytest.approx(0.023)
        assert w.abstand == pytest.approx(0.151)
        assert w.aussichtslos
        assert "nicht erreichbar" in w.beschreibung()

    def test_grosse_spanne_ist_nicht_aussichtslos(self) -> None:
        m = Machbarkeit(
            regler="x",
            punkte=[
                punkt(1.0, g=(False, 0.10, 0.95)),
                punkt(2.0, g=(False, 0.90, 0.95)),
            ],
        )

        w = m.hebelwirkung("g")

        assert w is not None and not w.aussichtslos
        assert w.naechste_stellung == 2.0

    def test_uebersprungene_gates_verfaelschen_die_spanne_nicht(self) -> None:
        """Ein uebersprungenes Gate hat keinen Wert - eine Null waere erfunden."""
        m = Machbarkeit(
            regler="x",
            punkte=[
                Punkt(1.0, {"g": Stand(True, 0.0, 0.95, uebersprungen=True)}),
                Punkt(2.0, {"g": Stand(False, 0.90, 0.95)}),
            ],
        )

        w = m.hebelwirkung("g")

        assert w is not None
        assert w.spanne == pytest.approx(0.0)

    def test_wer_irgendwo_haelt_ist_nie_ausser_reichweite(self) -> None:
        """**Der Fehler, den der erste Bericht gezeigt hat.**

        ``Stichprobengroesse`` bestand an jeder Stellung - mit Abstand 1179
        gegen eine Spanne von 31, und wurde deshalb als "ausser Reichweite"
        ausgewiesen. Der Abstand zur Schwelle ist eben in beide Richtungen
        gross; ohne die Frage, auf welcher Seite man steht, sagt er nichts.
        """
        m = Machbarkeit(
            regler="x",
            punkte=[
                punkt(1.0, g=(True, 1210.0, 31.0)),
                punkt(2.0, g=(True, 1241.0, 31.0)),
            ],
        )

        w = m.hebelwirkung("g")

        assert w is not None
        assert w.spanne < w.abstand  # die rohe Bedingung greift
        assert w.haelt_irgendwo
        assert not w.aussichtslos  # und wird trotzdem richtig entschieden

    def test_eine_einzige_stellung_belegt_nichts(self) -> None:
        """**Der zweite falsche Bericht, und der lehrreichere.**

        Bei einem Messpunkt ist die Spanne null - damit waere jedes gerissene
        Gate automatisch "ausser Reichweite des Reglers", obwohl an dem Regler
        nie gedreht wurde. Ein Werkzeug, das aus einem Punkt eine Schranke
        ableitet, sagt mehr, als es weiss.
        """
        m = Machbarkeit(regler="Vola-Ziel", punkte=[punkt(19.3, g=(False, 0.869, 0.95))])

        w = m.hebelwirkung("g")

        assert w is not None
        assert w.spanne == 0.0 and w.abstand > 0  # die rohe Bedingung greift
        assert w.stellungen == 1
        assert not w.aussichtslos
        assert "ausser Reichweite" not in m.urteil()

    def test_zwei_stellungen_genuegen(self) -> None:
        m = Machbarkeit(
            regler="x",
            punkte=[punkt(1.0, g=(False, 0.869, 0.95)), punkt(2.0, g=(False, 0.870, 0.95))],
        )

        w = m.hebelwirkung("g")

        assert w is not None and w.stellungen == 2
        assert w.aussichtslos

    def test_unbekanntes_gate(self) -> None:
        assert Machbarkeit(regler="x", punkte=[punkt(1.0, a=True)]).hebelwirkung(
            "b"
        ) is None


class TestVerfeinerung:
    def test_harte_schranke_beendet_die_suche(self) -> None:
        """**Warum das wichtig ist.**

        Ohne diese Abkuerzung wuerde die Maschine beliebig fein weitermessen -
        jede Stufe ein Versuch, jeder Versuch hebt die Huerde des Deflated
        Sharpe. Feiner abtasten, was nachweislich nicht erreichbar ist, macht
        die Lage schlechter statt klarer.
        """
        m = Machbarkeit(
            regler="Vola-Ziel",
            punkte=[
                punkt(14.0, dsr=(False, 0.776, 0.95), a=True, b=False),
                punkt(28.0, dsr=(False, 0.799, 0.95), a=False, b=True),
            ],
        )

        assert m.konflikte  # es gaebe etwas zu verfeinern
        assert m.verfeinerung() == []
        assert "hilft nicht" in m.urteil()

    def test_bekannte_stellungen_werden_nicht_wiederholt(self) -> None:
        m = Machbarkeit(
            regler="x",
            punkte=[
                punkt(1.0, a=True, b=False),
                punkt(1.5, a=False, b=False),
                punkt(2.0, a=False, b=True),
            ],
        )

        assert 1.5 not in m.verfeinerung()
        assert m.verfeinerung() == [1.25, 1.75]

    def test_obergrenze_wird_eingehalten(self) -> None:
        m = Machbarkeit(
            regler="x",
            punkte=[punkt(float(i), a=i == 0, b=i == 9) for i in range(10)],
        )

        assert len(m.verfeinerung(hoechstens=3)) == 3

    def test_weiches_gate_bekommt_seine_nachbarn(self) -> None:
        """Ein Gate ohne harte Schranke darf nicht stillschweigend abgehakt
        werden - dort liegt der Zweifel."""
        m = Machbarkeit(
            regler="x",
            punkte=[
                punkt(1.0, g=(False, 0.10, 0.95)),
                punkt(2.0, g=(False, 0.90, 0.95)),
                punkt(3.0, g=(False, 0.20, 0.95)),
            ],
        )

        assert m.verfeinerung() == [1.5, 2.5]


class TestBeschreibung:
    def test_reihenfolge_folgt_dem_regler_nicht_dem_namen(self) -> None:
        """**Sonst sagt der Satz das Gegenteil.**

        ``a`` und ``b`` stehen in der Reihenfolge der Gate-Namen, nicht in der
        des Reglers. Wer sie ungeprueft in "haelt bis / erst ab" einsetzt,
        vertauscht oben und unten.
        """
        m = Machbarkeit(
            regler="x",
            punkte=[
                punkt(19.3, messlatte=False, schlechtestes_jahr=True),
                punkt(25.0, messlatte=True, schlechtestes_jahr=False),
            ],
        )

        text = m.konflikte[0].beschreibung()

        assert text.startswith("schlechtestes_jahr haelt bis 19.3")
        assert "messlatte erst ab 25" in text

    def test_einzahl_bei_einem_zwischenraum(self) -> None:
        m = Machbarkeit(
            regler="x", punkte=[punkt(1.0, a=True, b=False), punkt(2.0, a=False, b=True)]
        )

        assert "1 Zwischenraum," in m.konflikte[0].beschreibung()


class TestPayload:
    def test_werte_hinter_den_zeichen_bleiben_erhalten(self) -> None:
        """Damit niemand die Abtastung wiederholen muss, um an sie zu kommen -
        und dabei dieselben Stufen ein zweites Mal zaehlt."""
        m = Machbarkeit(
            regler="Vola-Ziel",
            einheit="%",
            punkte=[
                Punkt(19.3, {"dsr": Stand(False, 0.799, 0.95)}, {"cagr": 11.2789}),
                Punkt(28.0, {"dsr": Stand(False, 0.780, 0.95)}, {"cagr": 18.5}),
            ],
        )

        p = m.als_payload()

        assert p["regler"] == "Vola-Ziel"
        assert p["fenster"] == []
        assert p["nie_erfuellt"] == ["dsr"]
        assert p["hebelwirkung"]["dsr"]["aussichtslos"] is True
        assert p["punkte"][0]["stellung"] == 19.3
        assert p["punkte"][0]["gates"]["dsr"]["wert"] == 0.799
        assert p["punkte"][0]["kennzahlen"]["cagr"] == 11.2789
        assert "urteil" in p

    def test_payload_ist_json_faehig(self) -> None:
        import json

        m = Machbarkeit(regler="x", punkte=[punkt(1.0, a=True, b=False)])

        assert json.loads(json.dumps(m.als_payload()))["regler"] == "x"


class TestTabelle:
    def test_zeilen_sind_gates_spalten_sind_stellungen(self) -> None:
        m = Machbarkeit(
            regler="Vola-Ziel",
            punkte=[punkt(14.0, mess=False, dd=True), punkt(28.0, mess=True, dd=False)],
        )

        zeilen = m.tabelle().splitlines()

        assert zeilen[0].startswith("Vola-Ziel")
        assert "14" in zeilen[0] and "28" in zeilen[0]
        assert zeilen[2].startswith("mess")
        assert zeilen[2].split()[1:] == ["-", "+"]
        assert "1/2" in zeilen[-1] and "2" in zeilen[-1]

    def test_uebersprungenes_gate_bekommt_ein_eigenes_zeichen(self) -> None:
        m = Machbarkeit(
            regler="x",
            punkte=[Punkt(1.0, {"g": Stand(True, 0.0, 1.0, uebersprungen=True)})],
        )

        assert "o" in m.tabelle().splitlines()[2]


class TestAusGateReport:
    def test_uebersetzung_haelt_status_und_werte_fest(self) -> None:
        from research.gates import GateReport, GateResult, GateStatus

        report = GateReport(genome_id="abc")
        report.results = [
            GateResult("Drawdown", GateStatus.PASS, 9.7, 12.0, ""),
            GateResult("Deflated Sharpe", GateStatus.FAIL, 0.80, 0.95, ""),
            GateResult("Regime", GateStatus.SKIP, 0.0, 0.9, ""),
        ]

        p = aus_gate_report(19.3, report, {"cagr": 11.28})

        assert p.stellung == 19.3
        assert p.gates["Drawdown"].bestanden
        assert not p.gates["Deflated Sharpe"].bestanden
        assert p.gates["Regime"].uebersprungen
        assert p.gates["Regime"].bestanden  # uebersprungen blockiert nicht
        assert p.offen == ["Deflated Sharpe"]
        assert p.bestanden == 2
        assert p.kennzahlen["cagr"] == 11.28


def test_gemessene_lage_des_spitzenkandidaten() -> None:
    """**Der Befund, fuer den dieses Modul gebaut wurde.**

    Vola-Ziel von 14 bis 32 %, alle elf Gates je Stufe. Der Deflated Sharpe
    ist ueber den ganzen Regelweg praktisch konstant, und die Messlatte
    verlangt Rendite, die nur mit einem Rueckgang zu haben ist, den zwei
    andere Gates verbieten.
    """
    dsr = {14.0: 0.776, 16.0: 0.791, 19.3: 0.799, 22.0: 0.789,
           25.0: 0.792, 28.0: 0.780, 32.0: 0.799}
    dd = {14.0: 6.67, 16.0: 7.17, 19.3: 9.74, 22.0: 11.83,
          25.0: 12.93, 28.0: 15.02, 32.0: 17.06}
    cagr = {14.0: 7.78, 16.0: 9.08, 19.3: 11.28, 22.0: 12.42,
            25.0: 14.32, 28.0: 15.79, 32.0: 18.49}

    m = Machbarkeit(
        regler="Vola-Ziel",
        einheit="%",
        punkte=[
            Punkt(
                stellung=ziel,
                gates={
                    "Messlatte": Stand(cagr[ziel] >= 15.0, cagr[ziel], 15.0),
                    "Drawdown": Stand(dd[ziel] <= 12.0, dd[ziel], 12.0),
                    "Deflated Sharpe": Stand(False, dsr[ziel], 0.95),
                },
            )
            for ziel in sorted(dsr)
        ],
    )

    assert m.fenster == []
    assert m.nie_erfuellt == ["Deflated Sharpe"]

    wirkung = m.hebelwirkung("Deflated Sharpe")
    assert wirkung is not None and wirkung.aussichtslos

    (konflikt,) = m.konflikte
    assert {konflikt.a, konflikt.b} == {"Messlatte", "Drawdown"}
    assert konflikt.uebergang == (22.0, 28.0)

    # Und weil ein Gate ausser Reichweite ist, hilft feineres Messen nicht.
    assert m.verfeinerung() == []
