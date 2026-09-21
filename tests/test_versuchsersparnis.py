"""Was eine Versuchsersparnis wirklich wert ist - Befund 327.

In Befund 326 habe ich fuenf Regeln aus dem Katalog genommen, die auf dieser
Reihe nichts ausloesen koennen, und das so begruendet:

    "jede gewertete Regel ist ein Versuch", und Versuche heben die Huerde des
    Deflated Sharpe fuer alle anderen. Dort steht das Projekt, 0,5826 gegen
    0,95.

Der Mechanismus stimmt. Die Zahl daneben habe ich nie nachgerechnet - in
einem Projekt, dessen erster Grundsatz lautet, dass jede Behauptung gemessen
wird. Das Werkzeug dafuer lag seit Befund 139 im Haus:
``research/erreichbarkeit.py``, ein Aufruf.

Nachgerechnet am Spitzenkandidaten (``referenz.SPOTPUNKT``):

    fuenf Versuche          0,0054 DSR-Punkte
    zehn Versuche           0,0106
    Luecke zur Latte        0,3673

Fuenf Versuche sind **1,5 %** der Luecke. Und der Zaehler faellt ohnehin nicht:
Was Befund 326 gebracht hat, ist nicht eine Ruecknahme von fuenf Versuchen,
sondern fuenf, die kuenftig nicht dazukommen.
"""

from __future__ import annotations

import pytest

from research.erreichbarkeit import bewerte
from research.referenz import SPOTPUNKT


@pytest.fixture(scope="module")
def spitze():
    return bewerte(
        trades=SPOTPUNKT.effektiv,
        sharpe=SPOTPUNKT.guete,
        trials=SPOTPUNKT.versuche,
        skew=SPOTPUNKT.schiefe,
        kurtosis=SPOTPUNKT.woelbung,
    )


class TestDieRechnungTrifftDenVerzeichnetenStand:
    """Ohne das ist alles darunter eine Rechnung ueber einen anderen Fall."""

    def test_der_deflated_sharpe_stimmt_mit_der_referenz(self, spitze) -> None:
        assert spitze.dsr == pytest.approx(SPOTPUNKT.dsr, abs=1e-4)

    def test_und_die_noetige_stichprobe_auch(self, spitze) -> None:
        assert spitze.trades_noetig == SPOTPUNKT.noetiges_n()


class TestWasVersucheKosten:
    def test_null_versuche_kosten_nichts(self, spitze) -> None:
        assert spitze.kosten(0) == pytest.approx(0.0)

    def test_die_neue_rechnung_deckt_sich_mit_den_alten_feldern(
        self, spitze
    ) -> None:
        """``kosten`` verallgemeinert 1 und 10 und darf dort nichts anderes
        sagen - sonst rechneten zwei Wege am selben Wert vorbei."""
        assert spitze.kosten(1) == pytest.approx(spitze.kosten_naechster_versuch)
        assert spitze.kosten(10) == pytest.approx(spitze.kosten_zehn_versuche)

    def test_mehr_versuche_kosten_mehr(self, spitze) -> None:
        werte = [spitze.kosten(n) for n in (1, 5, 10, 50, 100)]

        assert werte == sorted(werte)

    @pytest.mark.parametrize(
        ("versuche", "hoechstens"), [(1, 0.002), (5, 0.006), (10, 0.011)]
    )
    def test_und_zwar_wenig(self, spitze, versuche, hoechstens) -> None:
        assert spitze.kosten(versuche) < hoechstens


class TestDerKernVonBefund327:
    """**Die Zahl, die in Befund 326 gefehlt hat.**"""

    def test_fuenf_versuche_sind_ein_bruchteil_der_luecke(self, spitze) -> None:
        luecke = spitze.ziel - spitze.dsr

        anteil = spitze.kosten(5) / luecke

        assert luecke > 0.36, "die Luecke zur Latte"
        assert anteil < 0.02, (
            f"Befund 326 hat fuenf Versuche als Schritt Richtung Gate "
            f"begruendet; gemessen sind es {anteil:.1%} der Luecke"
        )

    def test_auch_der_ganze_katalog_reicht_nicht(self, spitze) -> None:
        """53 Regeln sind ein vollstaendiger Katalogdurchlauf. Selbst ihn
        ganz zu sparen deckt die Luecke nicht."""
        luecke = spitze.ziel - spitze.dsr

        assert spitze.kosten(53) < luecke / 5

    def test_die_stichprobe_ist_der_hebel_und_nicht_der_zaehler(
        self, spitze
    ) -> None:
        """**Worauf es stattdessen ankommt.**

        75 fehlende wirksame Trades schliessen die Luecke ganz; das ist es,
        was mehr Historie kauft. Kein erreichbarer Versuchsbetrag tut das.
        """
        assert spitze.fehlende_trades == 75
        assert not spitze.bestanden

        from research.erreichbarkeit import _dsr

        mit_trades = _dsr(
            SPOTPUNKT.guete,
            spitze.trades_noetig,
            SPOTPUNKT.versuche,
            SPOTPUNKT.schiefe,
            SPOTPUNKT.woelbung,
        )

        assert mit_trades >= spitze.ziel


class TestDerZaehlerFaelltNicht:
    """Eine Ersparnis ist ein vermiedener Verlust, keine Rueckgabe."""

    def test_eine_negative_frage_wird_abgewiesen(self, spitze) -> None:
        with pytest.raises(ValueError, match="faellt nicht"):
            spitze.kosten(-5)

    def test_save_trials_laesst_den_stand_nicht_fallen(self, tmp_path) -> None:
        """**Der Grund dafuer, am Quelltext geprueft.** Ohne diese Regel
        waere 'Versuche sparen' tatsaechlich ein Weg - und die
        Mehrfachtest-Korrektur beliebig milde zu machen."""
        from research.admission import load_trials, save_trials

        pfad = tmp_path / "trials.json"
        save_trials(pfad, 203)
        save_trials(pfad, 198)

        assert load_trials(pfad) == 203


class TestDerBerichtSagtEsDazu:
    def test_er_nennt_die_einbahnstrasse(self, spitze) -> None:
        text = spitze.bericht()

        assert "Zaehler faellt nie" in text
        assert "haelt den Abstand, sie schliesst ihn nicht" in text

    def test_und_beziffert_den_anteil_an_der_luecke(self, spitze) -> None:
        """Ein Anteil, keine blosse Punktzahl: 0,0106 sagt niemandem etwas,
        '2,9 % der Luecke' schon."""
        text = spitze.bericht()

        assert "der Luecke" in text
        assert "%" in text

    def test_ein_bestandener_kandidat_bekommt_die_belehrung_nicht(self) -> None:
        gut = bewerte(trades=5000, sharpe=0.5, trials=10)

        assert gut.bestanden
        assert "Zaehler faellt nie" not in gut.bericht()
