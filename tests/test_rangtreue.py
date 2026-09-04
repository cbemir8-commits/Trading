"""Traegt die Rangfolge aus der Entwicklung nach draussen?

Zwei Tests tragen diese Datei:

``test_die_zahlen_aus_befund_186_kommen_wieder_heraus`` - Die Rechnung stand
dort nur als Prosa. Wenn dieselben acht Punkte dieselben +0,214 und +0,571
ergeben, ist die Umsetzung an einer veroeffentlichten Messung geprueft und
nicht an sich selbst.

``test_die_berichtigung_hat_es_nicht_besser_gemacht`` - Das unbequeme
Ergebnis aus Befund 195: Die richtigere Latte sagt schwaecher voraus. Beides
stehenzulassen ist der ehrliche Zustand.
"""

from __future__ import annotations

import pytest

from research.rangtreue import (
    MINDEST_T,
    Punkt,
    Rangtreue,
    raenge,
    rangkorrelation,
    t_wert,
)

AUSREISSER = "Langsamer Kreuzer (Messlatte 2)"

#: Name, Luecke nach Befund 184, Luecke nach Befund 193, Holdout-Haltequote.
GEMESSEN: list[tuple[str, float, float, float]] = [
    ("Grosser Trendausbruch", 0.064, 0.212, -70.0),
    ("Trendfolge Ausbruch", 0.125, 0.108, 7.0),
    ("Trend-Beteiligung (fair gerechnet)", 0.521, 0.490, 30.0),
    ("Nur mit der Drift", 0.574, 0.664, 29.0),
    ("EMA-Kreuzung (Messlatte)", 0.605, 0.693, -34.0),
    ("Trendbeteiligung EMA200", 0.657, 0.655, 25.0),
    (AUSREISSER, 0.684, 0.809, -789.0),
    ("Bestand allein", 0.705, 0.743, 41.0),
]


def treue(*, berichtigt: bool) -> Rangtreue:
    i = 2 if berichtigt else 1
    return Rangtreue(
        punkte=[Punkt(z[0], z[i], z[3]) for z in GEMESSEN]
    )


class TestDieRechnung:
    def test_gleichlaeufige_reihen_geben_eins(self) -> None:
        assert rangkorrelation([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)

    def test_gegenlaeufige_reihen_geben_minus_eins(self) -> None:
        assert rangkorrelation([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)

    def test_nur_die_reihenfolge_zaehlt_nicht_der_abstand(self) -> None:
        """Der Unterschied zu Pearson - und der Grund fuer Spearman hier.

        Eine Haltequote von -789 % ist als **Rang** der letzte Platz und
        nicht das Zwanzigfache eines anderen Werts.
        """
        a = rangkorrelation([1, 2, 3, 4], [1, 2, 3, 1000])
        b = rangkorrelation([1, 2, 3, 4], [1, 2, 3, 4])

        assert a == pytest.approx(b)

    def test_bindungen_werden_gemittelt(self) -> None:
        """Sonst haengt das Ergebnis an der Eingabereihenfolge."""
        assert list(raenge([5.0, 5.0, 1.0])) == [1.5, 1.5, 0.0]

    def test_ohne_streuung_gibt_es_nichts(self) -> None:
        assert rangkorrelation([1, 1, 1, 1], [1, 2, 3, 4]) is None

    def test_zu_kurze_reihen_liefern_nichts(self) -> None:
        assert rangkorrelation([1, 2], [2, 1]) is None
        assert t_wert(0.5, 2) is None


class TestGegenBefund186:
    def test_die_zahlen_aus_befund_186_kommen_wieder_heraus(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Befund 186 hat rho = +0,214 (t = +0,54) fuer alle acht und +0,571
        (t = +1,56) ohne den Ausreisser gemeldet. Beide Zahlen standen nur im
        Laborbuch. Kommen sie hier wieder heraus, ist die Umsetzung an einer
        veroeffentlichten Messung geprueft.
        """
        t = treue(berichtigt=False)
        alle, ohne = t.alle, t.ohne(AUSREISSER)

        assert alle is not None and ohne is not None
        assert alle[0] == pytest.approx(0.214, abs=5e-3)
        assert alle[1] == pytest.approx(0.54, abs=5e-2)
        assert ohne[0] == pytest.approx(0.571, abs=5e-3)
        assert ohne[1] == pytest.approx(1.56, abs=5e-2)

    def test_das_urteil_verweigert_die_aussage(self) -> None:
        """Beide liegen unter |t| = 2 - dann wird nichts behauptet."""
        urteil = treue(berichtigt=False).urteil(ausreisser=AUSREISSER)

        assert "ordnet das Verhalten draussen nicht" in urteil
        assert "ohne Deckung" in urteil


class TestDieBerichtigung:
    def test_die_berichtigung_hat_es_nicht_besser_gemacht(self) -> None:
        """**Der zweite tragende Test** - das unbequeme Ergebnis.

        Befund 193 hat die Latte jedes Paares auf seine eigenen Momente
        gestellt, so wie das Gate rechnet. Naheliegend waere, dass ein
        richtigeres Mass auch besser vorhersagt. Es sagt schwaecher voraus,
        und beides stehenzulassen ist der ehrliche Zustand.
        """
        alt = treue(berichtigt=False)
        neu = treue(berichtigt=True)

        for a, b in ((alt.alle, neu.alle), (alt.ohne(AUSREISSER), neu.ohne(AUSREISSER))):
            assert a is not None and b is not None
            assert abs(b[0]) < abs(a[0]) or b[0] < a[0], (
                f"berichtigt {b[0]:+.3f} gegen alt {a[0]:+.3f}"
            )

    def test_auch_berichtigt_bleibt_es_unter_der_schwelle(self) -> None:
        """Das Ergebnis wechselt nicht die Seite - es war nie auf einer."""
        t = treue(berichtigt=True)

        for messung in (t.alle, t.ohne(AUSREISSER)):
            assert messung is not None
            assert abs(messung[1]) < MINDEST_T, f"t = {messung[1]:+.2f}"

    def test_beide_rangfolgen_sagen_dasselbe_naemlich_nichts(self) -> None:
        for berichtigt in (False, True):
            urteil = treue(berichtigt=berichtigt).urteil(ausreisser=AUSREISSER)
            assert "ordnet das Verhalten draussen nicht" in urteil


class TestGrenzen:
    def test_zu_wenige_punkte_liefern_kein_urteil(self) -> None:
        duenn = Rangtreue(punkte=[Punkt("a", 0.1, 5.0), Punkt("b", 0.2, 6.0)])

        assert not duenn.genug
        assert duenn.alle is None
        assert "nichts sagen" in duenn.urteil()

    def test_der_ausreisser_wird_nicht_still_entfernt(self) -> None:
        """``alle`` enthaelt ihn immer - herausnehmen muss man ausdruecklich."""
        t = treue(berichtigt=False)

        assert len(t.punkte) == 8
        assert t.alle != t.ohne(AUSREISSER)

    def test_ein_klarer_zusammenhang_wird_auch_gemeldet(self) -> None:
        """Sonst verweigerte das Urteil die Aussage immer."""
        klar = Rangtreue(
            punkte=[Punkt(f"k{i}", i / 10, -float(i)) for i in range(12)]
        )
        urteil = klar.urteil()

        assert "gegenlaeufig" in urteil
        assert "ordnet das Verhalten draussen nicht" not in urteil
