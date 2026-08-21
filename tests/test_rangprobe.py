"""Steuert die Suche nach einem verfaelschten Signal?

Drei Tests tragen diese Datei:

``test_die_rangfolge_haelt`` - Der Kern. 13 handelnde Katalog-Genome, zweimal
gemessen, keines aendert seine Zahl bestandener Gates. Die Bestenliste steht
also nicht auf Sand.

``test_drei_hypothesen_heben_die_schranke`` - Die Stelle, an der man die
eigene Lehre am leichtesten vergisst. Ein t von 2,14 reisst die uebliche
Schwelle von 2,0 - bei drei geprueften Erklaerungen liegt die Schranke aber
bei 2,39.

``test_stumme_genome_zaehlen_nicht_als_stabil`` - Zehn Katalog-Genome handeln
gar nicht und bestehen trotzdem fuenf Gates. Sie mitzuzaehlen hiesse,
Stillstand als Stabilitaet zu verkaufen.
"""

from __future__ import annotations

import pytest

from research.rangprobe import (
    GRUNDSCHRANKE,
    Doppel,
    Rangprobe,
    Zusammenhang,
    schranke,
)

#: Die gemessenen Doppel des Tageskerzen-Katalogs, Versuchsstand 177 in
#: jeder Spalte. Nachzurechnen mit ``cli rangprobe``.
#: Name, Trades, Rueckgang grob, Rueckgang fein, Gates grob, Gates fein.
GEMESSEN: tuple[tuple[str, int, float, float, int, int], ...] = (
    ("Momentum-Beteiligung 90 Tage", 94, 25.56, 27.77, 2, 2),
    ("Trend-Beteiligung 100 Tage", 101, 18.40, 19.91, 2, 2),
    ("Trend-Beteiligung 50 Tage", 142, 29.16, 30.03, 5, 5),
    ("Donchian-Ausbruch 55/20", 55, 19.45, 20.27, 6, 6),
    ("Vola-Ziel, langes Messfenster", 51, 6.97, 7.46, 7, 7),
    ("Trend-Beteiligung voller Einsatz", 43, 27.67, 28.12, 3, 3),
    ("Trend mit Vola-Ziel 20 %", 51, 8.03, 8.18, 8, 8),
    ("Vola-Ziel, kurzes Messfenster", 51, 7.78, 7.90, 8, 8),
    ("Trend-Beteiligung (fair gerechnet)", 46, 13.54, 13.65, 5, 5),
    ("Trend-Beteiligung 200 Tage", 46, 13.54, 13.65, 5, 5),
    ("Trend mit Vola-Ziel 22 %", 51, 8.83, 8.91, 8, 8),
    ("Bollinger-Ruecksetzer short", 1, 0.35, 0.39, 5, 5),
    ("Trend beide Richtungen", 84, 27.76, 27.43, 3, 3),
)
#: Zehn weitere Genome des Katalogs handeln auf diesen Daten gar nicht.
STUMM = 10


def probe(**abweichung) -> Rangprobe:
    doppel = [
        Doppel(
            name=n, trades=t, grob_rueckgang=ga, fein_rueckgang=fe,
            grob_bestanden=ba, fein_bestanden=bb,
        )
        for n, t, ga, fe, ba, bb in GEMESSEN
    ]
    doppel += [
        Doppel(
            name=f"stumm {i}", trades=0, grob_rueckgang=0.0, fein_rueckgang=0.0,
            grob_bestanden=5, fein_bestanden=5,
        )
        for i in range(STUMM)
    ]
    daten = {"doppel": doppel}
    daten.update(abweichung)
    return Rangprobe(**daten)


class TestRangfolge:
    def test_die_rangfolge_haelt(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Waere die Rangfolge von der Mengenrundung abhaengig, stuende jeder
        Vergleich zweier Kandidaten auf Sand - schlimmer als alles, was die
        Befunde 95 bis 97 gefunden haben. Sie ist es nicht.
        """
        p = probe()

        assert len(p.handelnde) == 13
        assert p.wechsler == []
        assert p.rangfolge_haelt
        assert not p.spitze_wechselt
        urteil = p.urteil()
        assert "Rangfolge haelt" in urteil
        assert "kein verfaelschtes Signal" in urteil.replace(
            "nicht nach einem verfaelschten Signal", "kein verfaelschtes Signal"
        )

    def test_die_zahlen_verschieben_sich_trotzdem(self) -> None:
        """**Der Zusatz, ohne den das Urteil zu beruhigend klaenge.**

        "Nichts aendert sich" waere falsch: Die Rueckgaenge wandern um bis zu
        2,2 Punkte. Sie drehen nur kein Urteil, weil sie weit von ihren
        Schwellen entfernt liegen - anders als beim Bestand.
        """
        p = probe()
        tief, hoch = p.spanne

        assert hoch == pytest.approx(2.21, abs=0.02)
        assert tief == pytest.approx(-0.32, abs=0.02)
        assert p.median_luecke == pytest.approx(0.15, abs=0.02)
        assert "dicht an ihrer Schwelle" in p.urteil()

    def test_stumme_genome_zaehlen_nicht_als_stabil(self) -> None:
        """**Die bequeme Verwechslung.**

        Zehn Genome handeln nicht und bestehen fuenf Gates, weil nichts
        schiefgehen kann, wo nichts passiert. Sie mitzuzaehlen hoebe die
        Stabilitaetsquote von 13 auf 23, ohne dass etwas gemessen waere.
        """
        p = probe()

        assert len(p.doppel) == 23
        assert len(p.handelnde) == 13
        assert all(d.handelt for d in p.handelnde)
        assert "10 Genome ohne Trades" in p.tabelle()

    def test_ein_wechsel_wird_gemeldet(self) -> None:
        """Gegenprobe: Kippt ein Urteil, sagt das Urteil das - und nennt den
        Namen."""
        gekippt = probe()
        gekippt.doppel[0] = Doppel(
            name="Kipper", trades=90, grob_rueckgang=11.5, fein_rueckgang=12.4,
            grob_bestanden=8, fein_bestanden=7,
        )

        assert not gekippt.rangfolge_haelt
        assert [d.name for d in gekippt.wechsler] == ["Kipper"]
        assert "aendern ihr Urteil" in gekippt.urteil()
        assert "Kipper" in gekippt.urteil()

    def test_eine_neue_spitze_wird_eigens_genannt(self) -> None:
        """Uebereinstimmung im Mittelfeld nuetzt nichts, wenn oben ein anderer
        steht - die Liste ist dafuer da, den besten zu finden."""
        def eintrag(name, trades, grob, fein, dd) -> Doppel:
            return Doppel(
                name=name, trades=trades, grob_bestanden=grob,
                fein_bestanden=fein, grob_rueckgang=dd, fein_rueckgang=dd + 0.1,
            )

        p = Rangprobe(
            doppel=[
                eintrag("A", 100, 8, 6, 10.0),
                eintrag("B", 90, 7, 7, 12.0),
                eintrag("C", 80, 5, 5, 14.0),
            ]
        )

        assert p.spitze_wechselt
        assert "vorn steht ein anderes Genom" in p.urteil()

    def test_zu_wenige_sagen_nichts(self) -> None:
        duenn = Rangprobe(doppel=[Doppel("A", 10, 5.0, 5.1, 6, 6)])

        assert not duenn.genug
        assert not duenn.rangfolge_haelt
        assert "nichts sagen" in duenn.urteil()
        assert Rangprobe().tabelle() == "Kein handelndes Genom."


class TestSchranke:
    def test_drei_hypothesen_heben_die_schranke(self) -> None:
        """**Der Test, der die eigene Lehre absichert.**

        Gemessen: Die Zahl der Trades erklaert die Streuung mit r = +0,543,
        also t = +2,14 bei 13 Genomen. Das reisst die uebliche Schwelle von
        2,0 - und ist trotzdem kein Beleg, weil drei Erklaerungen geprueft
        wurden. Bei dreien liegt die Schranke bei 2,39.
        """
        p = probe()
        trades = [d.trades for d in p.handelnde]

        allein = p.erklaerung("Trades", trades)
        korrigiert = p.erklaerung("Trades", trades, hypothesen=3)

        assert allein.t_wert == pytest.approx(2.14, abs=0.05)
        assert allein.belegt, "ohne Korrektur saehe es nach einem Beleg aus"
        assert korrigiert.schranke == pytest.approx(2.39, abs=0.01)
        assert not korrigiert.belegt

    def test_die_beiden_anderen_erklaerungen_reissen_nichts(self) -> None:
        p = probe()

        rueckgang = p.erklaerung(
            "Rueckgang", [d.grob_rueckgang for d in p.handelnde], hypothesen=3
        )

        assert rueckgang.r == pytest.approx(0.413, abs=0.01)
        assert rueckgang.t_wert == pytest.approx(1.51, abs=0.05)
        assert not rueckgang.belegt

    def test_eine_einzelne_pruefung_behaelt_die_zwei(self) -> None:
        """Die Korrektur darf die uebliche Schwelle nicht heimlich anheben, wo
        nur eine Frage gestellt wurde."""
        assert schranke(1) == GRUNDSCHRANKE
        assert schranke(0) == GRUNDSCHRANKE
        assert schranke(2) > GRUNDSCHRANKE
        assert schranke(10) > schranke(3) > schranke(2)

    def test_die_schranke_waechst_langsam(self) -> None:
        """Bonferroni und keine Panik: Zehn Pruefungen heben sie auf 2,8, nicht
        ins Unerreichbare."""
        assert schranke(10) == pytest.approx(2.81, abs=0.02)

    def test_ohne_streuung_gibt_es_keinen_zusammenhang(self) -> None:
        p = probe()

        flach = p.erklaerung("konstant", [1.0] * len(p.handelnde))

        assert flach.r == 0.0
        assert not flach.belegt

    def test_zu_wenige_punkte_liefern_keinen_t_wert(self) -> None:
        assert Zusammenhang("x", 0.9, n=2).t_wert is None
        assert not Zusammenhang("x", 0.9, n=2).belegt
        assert Zusammenhang("x", 1.0, n=20).t_wert is None

    def test_der_text_nennt_die_geltende_schranke(self) -> None:
        """Ein t ohne seine Schranke ist die Zahl, die zur Fehldeutung
        einlaedt."""
        text = str(Zusammenhang("Trades", 0.543, n=13, hypothesen=3))

        assert "Schranke 2.39" in text
        assert "nicht belegt" in text


class TestDoppel:
    def test_die_luecke_ist_der_aufschlag_ohne_rundung(self) -> None:
        d = Doppel("x", 100, grob_rueckgang=10.64, fein_rueckgang=12.96,
                   grob_bestanden=7, fein_bestanden=6)

        assert d.luecke == pytest.approx(2.32)
        assert d.relativ == pytest.approx(0.218, abs=0.002)
        assert d.urteil_wechselt

    def test_ein_genom_ohne_rueckgang_kippt_nicht(self) -> None:
        stumm = Doppel("x", 0, grob_rueckgang=0.0, fein_rueckgang=0.0,
                       grob_bestanden=5, fein_bestanden=5)

        assert not stumm.handelt
        assert stumm.relativ == 0.0
