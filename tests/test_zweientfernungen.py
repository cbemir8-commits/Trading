"""Zwei Entfernungen zur selben Schwelle - Befund 329.

Befund 328 hat die Bedingung unter ``AUSSICHT`` nachgetragen und dabei die
Frage aufgeworfen, ob die Guete je Trade mit der Historie faellt. Die Antwort
lag schon im Haus: ``historie.GEMESSEN`` misst sie ueber sechs Fenster und
findet keinen Trend (0,2765 / 0,2734 / 0,2705 / 0,2396 / 0,2711 / 0,2903).

Beim Nachlesen fiel etwas anderes auf. Dasselbe Modul rechnet eine
**Entfernung zur Schwelle** aus, und zwar als lebende Methode:

    GEMESSEN.fehlende_tage()  ->  649 Tage (1,8 Jahre)
    referenz.AUSSICHT.tage    -> 2152 Tage (5,9 Jahre)

Dieselbe Frage, derselbe Betriebspunkt, **Faktor 3,3** - und kein Test, der
die beiden aneinanderbindet.

Der Grund ist die Stichprobe: Die sechs Fenster sind vor Befund 135 gemessen,
also ohne die Quartalseinteilung. Der Modulkopf sagt das - aber nur fuer ``n``
und ``DSR``. ``ziel = 181`` ist genauso ueberholt (190 gilt), und aus allen
dreien zusammen faellt die Entfernung, die das Modul ausgibt. Genau sie stand
ohne Hinweis da, und sie ist die Zahl, die jemand mitnimmt.

Im Register stand der Fall seit Befund 138 unter **BEHOBEN** - "1,8 Jahre
galten fuer n = 152; jetzt mindestens 5,6". Behoben war die Beschriftung des
Modulkopfs; die Methode gab weiter 649 zurueck. Und die Handzahl 5,6 war
inzwischen selbst auf 5,9 weitergelaufen.
"""

from __future__ import annotations

import pytest

from research.historie import GEMESSEN, Historienkurve, Historienstufe
from research.referenz import AUSSICHT, SPOTPUNKT


class TestDieBeidenZahlenGehenAuseinander:
    """Der Befund selbst - festgehalten, damit er nicht unbemerkt wandert."""

    def test_die_leiter_rechnet_kuerzer_als_der_stand(self) -> None:
        assert GEMESSEN.fehlende_tage() < AUSSICHT.tage

    def test_und_zwar_um_mehr_als_das_doppelte(self) -> None:
        assert AUSSICHT.tage / GEMESSEN.fehlende_tage() > 2.0

    def test_es_liegt_an_der_stichprobe_und_nicht_an_der_rechnung(self) -> None:
        """**Die Probe.** Dieselbe Maschinerie mit den massgeblichen Zahlen
        gefuettert trifft ``AUSSICHT`` auf den Tag - der Unterschied sitzt in
        den Eingaben, nicht in einem Fehler auf einer der beiden Seiten."""
        wie_heute = Historienkurve(
            stufen=(
                Historienstufe(
                    "2017-08-16",
                    AUSSICHT.historie_tage,
                    SPOTPUNKT.trades,
                    SPOTPUNKT.effektiv,
                    SPOTPUNKT.guete,
                    SPOTPUNKT.dsr,
                    SPOTPUNKT.bestanden,
                    SPOTPUNKT.gesamt,
                ),
            ),
            ziel=SPOTPUNKT.noetiges_n(),
        )

        assert wie_heute.fehlende_tage() == AUSSICHT.tage

    def test_die_drei_ueberholten_eingaben(self) -> None:
        """n, DSR **und** ziel. Der Modulkopf nannte bis 329 nur die ersten
        beiden - und ``ziel`` geht genauso in die Entfernung ein."""
        ref = GEMESSEN.referenz

        assert ref.effektiv != AUSSICHT.heute
        assert GEMESSEN.ziel != SPOTPUNKT.noetiges_n()


class TestDasUrteilNenntDenMassgeblichenWert:
    """**Die Behebung.** Die Messung bleibt stehen - sie ist an ihrem Tag so
    entstanden. Was sich aendert, ist die Beschriftung der Zahl, die daraus
    faellt."""

    def test_die_eigene_zahl_steht_weiter_da(self) -> None:
        """Nichts wird stillschweigend umgeschrieben: Wer die Leiter liest,
        soll sehen, was sie gemessen hat."""
        urteil = GEMESSEN.urteil()

        assert str(GEMESSEN.fehlende_tage()) in urteil

    def test_und_der_massgebliche_daneben(self) -> None:
        urteil = GEMESSEN.urteil()

        assert "Massgeblich ist das nicht" in urteil
        assert str(AUSSICHT.tage) in urteil
        assert "referenz" in urteil

    def test_der_grund_wird_genannt_und_nicht_nur_die_abweichung(self) -> None:
        """Eine Warnung ohne Grund laedt dazu ein, sie wegzuklicken."""
        urteil = GEMESSEN.urteil()

        assert "Quartalseinteilung" in urteil
        assert "Befund 135" in urteil

    def test_die_zahlen_im_satz_stammen_aus_der_urteilenden_kurve(self) -> None:
        """**Ein eigener Fehlgriff, im ersten Anlauf.** Der Vergleichssatz
        las ``GEMESSEN`` aus dem Modul statt die Kurve, die gerade urteilt -
        eine selbst gebaute Kurve haette fremde Zahlen ueber sich gelesen."""
        fremd = Historienkurve(
            stufen=(
                Historienstufe("2017-01-01", 3000, 60, 44, 0.27, 0.30, 9, 11),
                Historienstufe("2020-01-01", 1500, 30, 30, 0.28, 0.12, 9, 11),
            ),
            ziel=99,
        )

        urteil = fremd.urteil()

        assert "44 unabhaengige" in urteil
        assert "statt 99" in urteil
        assert str(GEMESSEN.ziel) not in urteil.split("Massgeblich")[1]


class TestBeiUebereinstimmungWarntNichts:
    """Eine Warnung, die immer angeht, ist keine (Befund 324)."""

    @staticmethod
    def _passend() -> Historienkurve:
        return Historienkurve(
            stufen=(
                Historienstufe(
                    "2017-08-16",
                    AUSSICHT.historie_tage,
                    SPOTPUNKT.trades,
                    SPOTPUNKT.effektiv,
                    SPOTPUNKT.guete,
                    SPOTPUNKT.dsr,
                    9,
                    11,
                ),
                Historienstufe("2022-08-16", 1451, 52, 52, 0.2903, 0.1347, 9, 11),
            ),
            ziel=SPOTPUNKT.noetiges_n(),
        )

    def test_dann_steht_dasselbe_bild_da(self) -> None:
        urteil = self._passend().urteil()

        assert "dasselbe Bild" in urteil
        assert "Massgeblich ist das nicht" not in urteil

    def test_und_der_massgebliche_wert_trotzdem(self) -> None:
        """Auch im ruhigen Fall gehoert die Zahl hin - sonst faellt beim
        naechsten Auseinanderlaufen niemandem auf, dass sie fehlte."""
        assert str(AUSSICHT.tage) in self._passend().urteil()


class TestDasRegisterRechnetStattZuPflegen:
    """Die 5,6 im Eintrag zu Befund 138 war eine Handzahl und stand bei 5,9."""

    @staticmethod
    def _eintrag() -> str:
        from research.stand import BEHOBEN

        return next(
            r.ergebnis for r in BEHOBEN if "Zeit bis zur Schwelle" in r.name
        )

    def test_der_eintrag_traegt_den_gerechneten_wert(self) -> None:
        erwartet = f"{AUSSICHT.jahre:.1f}".replace(".", ",")

        assert erwartet in self._eintrag()

    def test_und_nicht_mehr_die_alte_handzahl(self) -> None:
        assert "5,6" not in self._eintrag()

    def test_er_sagt_dass_die_alte_zahl_weiterlebt(self) -> None:
        """Der Eintrag stand unter BEHOBEN, waehrend die Methode weiter 649
        zurueckgab. Das gehoert dazugeschrieben, nicht weggelassen."""
        eintrag = self._eintrag()

        assert "fehlende_tage" in eintrag
        assert "329" in eintrag


def test_die_guetefrage_aus_befund_328_ist_hier_beantwortet() -> None:
    """**Der Anlass dieses Laufs.** Befund 328 liess offen, ob die Guete je
    Trade mit der Historie faellt - die Bedingung, an der die ganze
    Entfernungsrechnung haengt. ``historie`` misst es ueber sechs Fenster:
    sie faellt nicht.

    Gemessen ist damit die Richtung "kuerzer"; fuer den Korb gibt es die
    andere nicht, weil die ETH-Reihe am 16.08.2017 beginnt.
    """
    assert GEMESSEN.guete_haengt_an_der_laenge() is False

    guete = [s.guete for s in GEMESSEN.sortiert]

    assert max(guete) - min(guete) < 0.06, "kein Trend, nur Streuung um 0,27"


@pytest.mark.parametrize("stufe", GEMESSEN.stufen)
def test_keine_stufe_meldet_mehr_unabhaengige_als_rohe_trades(stufe) -> None:
    assert stufe.effektiv <= stufe.trades
