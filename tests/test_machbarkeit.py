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


class TestRegler:
    """Die Stellschrauben, an denen abgetastet wird.

    Ihre Stufen stehen in der Liste und nicht im Aufruf: Solange jede
    Abtastung ihre eigenen Messpunkte mitbringt, misst jede etwas anderes -
    und wer die Punkte waehlt, waehlt am Ende das Ergebnis.
    """

    def test_bekannte_regler(self) -> None:
        from research.machbarkeit import REGLER

        assert set(REGLER) == {
            "vola", "stop", "konviktion", "periode", "abkuehlung",
        }
        for name, r in REGLER.items():
            assert r.stufen, name
            assert len(set(r.stufen)) == len(r.stufen), f"{name}: doppelte Stufe"
            assert list(r.stufen) == sorted(r.stufen), f"{name}: unsortiert"

    def test_stelle_ein_veraendert_nur_die_stellschraube(self) -> None:
        from research.machbarkeit import REGLER, stelle_ein
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()

        neu = stelle_ein(vorlage, REGLER["stop"], 8.0)

        assert neu.stop.percent == 8.0
        assert neu.entry_long == vorlage.entry_long
        assert neu.sizing.target_vol_pct == vorlage.sizing.target_vol_pct

    def test_die_vorlage_bleibt_unangetastet(self) -> None:
        """Sonst traegt die naechste Stufe die Aenderung der vorigen mit."""
        from research.machbarkeit import REGLER, stelle_ein
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()
        vorher = vorlage.stop.percent

        stelle_ein(vorlage, REGLER["stop"], 12.0)

        assert vorlage.stop.percent == vorher

    def test_neue_kennung_je_stufe(self) -> None:
        """**Sonst zaehlt der Versuchszaehler zwei Regeln als eine.**"""
        from research.machbarkeit import REGLER, stelle_ein
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()

        a = stelle_ein(vorlage, REGLER["stop"], 6.0)
        b = stelle_ein(vorlage, REGLER["stop"], 8.0)

        assert a.genome_id != b.genome_id != vorlage.genome_id

    def test_verschachtelter_pfad(self) -> None:
        from research.machbarkeit import REGLER, ausgangswert, stelle_ein
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()

        neu = stelle_ein(vorlage, REGLER["vola"], 25.0)

        assert neu.sizing.target_vol_pct == 25.0
        assert ausgangswert(neu, REGLER["vola"]) == 25.0

    def test_unerlaubte_stufe_wird_abgelehnt(self) -> None:
        """Das Schema gilt auch fuer eine Abtastung - ein Wert ausserhalb der
        Spanne muss auffallen und nicht still gerechnet werden."""
        import pydantic

        from research.machbarkeit import REGLER, stelle_ein
        from research.seeds import spitzenkandidat

        with pytest.raises(pydantic.ValidationError):
            stelle_ein(spitzenkandidat(), REGLER["stop"], 99.0)

    def test_ausgangswert_liest_den_kandidaten(self) -> None:
        from research.machbarkeit import REGLER, ausgangswert
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()

        assert ausgangswert(vorlage, REGLER["stop"]) == vorlage.stop.percent
        assert ausgangswert(vorlage, REGLER["konviktion"]) == (
            vorlage.sizing.konviktion_bonus
        )


class TestPeriodenregler:
    """**Die letzte offene Richtung: mehr Entscheidungen auf demselben Markt.**

    Ein schnellerer Schnitt kreuzt oefter. Skaliert werden muessen dabei
    **alle** Perioden zugleich - sonst entstuende eine Regel, die bei 40
    einsteigt und bei 50 aussteigt, und die hat nie jemand gehandelt.
    """

    def test_alle_perioden_wandern_mit(self) -> None:
        from research.machbarkeit import REGLER, stelle_ein
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()

        halb = stelle_ein(vorlage, REGLER["periode"], 0.5)

        assert halb.entry_long[0].right.params["period"] == 25
        assert halb.exit_long[0].right.params["period"] == 25
        assert halb.konfluenz[0].right.params["period"] == 100
        assert halb.sizing.vol_period == 15

    def test_faktor_eins_laesst_alles_stehen(self) -> None:
        from research.machbarkeit import REGLER, ausgangswert, stelle_ein
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()

        assert ausgangswert(vorlage, REGLER["periode"]) == 1.0
        assert stelle_ein(vorlage, REGLER["periode"], 1.0).genome_id == (
            vorlage.genome_id
        )

    def test_dieselbe_skalierung_wie_das_plateau_gate(self) -> None:
        """Wuerde der Regler seine eigene mitbringen, verglichen er etwas
        anderes als das Gate - der Fehler, der hier schon viermal auftrat."""
        from research.gates import skaliere_perioden
        from research.machbarkeit import REGLER, stelle_ein
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()

        ueber_regler = stelle_ein(vorlage, REGLER["periode"], 1.6)
        ueber_gate = skaliere_perioden(vorlage, 1.6)

        assert ueber_gate is not None
        assert ueber_regler.genome_id == ueber_gate.genome_id

    def test_wirkungsloser_faktor_faellt_auf(self, monkeypatch) -> None:
        """Ein Faktor, der nichts aendert, ist keine neue Stellung - und darf
        nicht still als eine gezaehlt werden.

        Geprueft wird der Waechter, nicht ein echtes Genom: An einem solchen
        laesst sich der Fall gar nicht herstellen, weil ``vol_period`` in
        **jedem** Genom steht und immer mitskaliert - auch bei Groessenarten,
        die es nie benutzen. Ein Testgenom zu bauen, das den Zweig scheinbar
        ausloest, waere eine vorgetaeuschte Lage.
        """
        import pytest

        from research import gates
        from research.machbarkeit import REGLER, stelle_ein
        from research.seeds import spitzenkandidat

        monkeypatch.setattr(gates, "skaliere_perioden", lambda genome, faktor: None)

        with pytest.raises(ValueError, match="aendert nichts"):
            stelle_ein(spitzenkandidat(), REGLER["periode"], 2.0)


class TestAbkuehlung:
    """Der Regler, der aus der Zerlegung des schlechtesten Jahres kam.

    Dort standen 24 Trades mit zusammen -21,45 R und keinem groesser als
    -1,45 R: eine Trendfolge, die im Abwaertsmarkt einsteigt, ausgestoppt wird
    und sofort wieder einsteigt. Die Abkuehlung ist die einzige Stellschraube,
    die genau daran ansetzt.
    """

    def test_sie_veraendert_nur_die_abkuehlung(self) -> None:
        from research.machbarkeit import REGLER, stelle_ein
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()
        neu = stelle_ein(vorlage, REGLER["abkuehlung"], 5.0)

        assert neu.cooldown_bars == 5
        assert neu.entry_long == vorlage.entry_long
        assert neu.stop == vorlage.stop
        assert neu.sizing == vorlage.sizing

    def test_ganze_kerzen_statt_kommazahlen(self) -> None:
        """``cooldown_bars`` zaehlt Kerzen. Eine halbe Kerze gibt es nicht -
        das Schema muss das abfangen, nicht ein stilles Abrunden."""
        from pydantic import ValidationError

        from research.machbarkeit import REGLER, stelle_ein
        from research.seeds import spitzenkandidat

        with pytest.raises(ValidationError):
            stelle_ein(spitzenkandidat(), REGLER["abkuehlung"], 2.5)

    def test_der_ausgangswert_ist_der_des_kandidaten(self) -> None:
        from research.machbarkeit import REGLER, ausgangswert
        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()

        assert ausgangswert(vorlage, REGLER["abkuehlung"]) == vorlage.cooldown_bars

    def test_die_stufen_beginnen_beim_kandidaten(self) -> None:
        """Ohne den eigenen Wert in der Leiter faehrt die Abtastung an dem
        Punkt vorbei, mit dem alles verglichen wird."""
        from research.machbarkeit import REGLER
        from research.seeds import spitzenkandidat

        assert float(spitzenkandidat().cooldown_bars) in REGLER["abkuehlung"].stufen
