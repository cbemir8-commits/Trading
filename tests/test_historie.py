"""Tests fuer ``research.historie`` - Befund 132.

Die gemessene Kurve (BTC + ETH, Tageskerzen, Spot, 198 Versuche, alle Fenster
enden am 05.08.2026) steht in ``gemessen()``. Erfundene Kurven kommen nur dort
vor, wo ein Zweig sonst ungetestet bliebe.
"""

from __future__ import annotations

import pytest

from research.historie import Historienkurve, Historienstufe


def gemessen(ziel: int | None = 181) -> Historienkurve:
    return Historienkurve(
        (
            Historienstufe("2017-08-16", 3277, 152, 152, 0.2765, 0.8640, 9, 11),
            Historienstufe("2018-08-16", 2912, 137, 136, 0.2734, 0.7659, 9, 11),
            Historienstufe("2019-08-16", 2547, 111, 103, 0.2705, 0.4792, 9, 11),
            Historienstufe("2020-03-30", 2320, 103, 103, 0.2396, 0.2969, 8, 11),
            Historienstufe("2021-08-16", 1816, 72, 72, 0.2711, 0.2209, 9, 11),
            Historienstufe("2022-08-16", 1451, 52, 52, 0.2903, 0.1347, 9, 11),
        ),
        ziel=ziel,
    )


# --- Historienstufe ---------------------------------------------------------


def test_stufe_ohne_tage_wird_abgewiesen() -> None:
    with pytest.raises(ValueError, match="keine Tage"):
        Historienstufe("2017-08-16", 0, 152, 152, 0.2765, 0.8640, 9, 11)


def test_effektive_stichprobe_kann_die_rohe_nicht_uebersteigen() -> None:
    with pytest.raises(ValueError, match="nicht uebersteigen"):
        Historienstufe("2017-08-16", 3277, 152, 153, 0.2765, 0.8640, 9, 11)


def test_sammelrate_je_stufe() -> None:
    s = Historienstufe("2017-08-16", 3277, 152, 152, 0.2765, 0.8640, 9, 11)
    assert s.je_tausend_tage == pytest.approx(46.4, abs=0.1)


def test_zeile_zeigt_die_kennzahlen() -> None:
    zeile = gemessen().sortiert[0].als_zeile()
    assert "2017-08-16" in zeile and "3277" in zeile
    assert "0.8640" in zeile and "9/11" in zeile


# --- Die Kurve --------------------------------------------------------------


def test_leere_kurve_sagt_nichts() -> None:
    leer = Historienkurve()
    assert leer.referenz is None
    assert leer.sammelrate() is None
    assert leer.fehlende_tage() is None
    assert "Keine Fenster" in leer.urteil()


def test_eine_stufe_ist_keine_kurve() -> None:
    eine = Historienkurve(
        (Historienstufe("2017-08-16", 3277, 152, 152, 0.2765, 0.8640, 9, 11),)
    )
    assert eine.referenz is not None
    assert "braucht zwei" in eine.urteil()
    assert eine.guete_haengt_an_der_laenge() is None


def test_referenz_ist_das_laengste_fenster() -> None:
    ref = gemessen().referenz
    assert ref is not None
    assert ref.von == "2017-08-16"
    assert ref.tage == 3277


def test_sortiert_geht_vom_laengsten_zum_kuerzesten() -> None:
    assert [s.tage for s in gemessen().sortiert] == [
        3277, 2912, 2547, 2320, 1816, 1451
    ]


def test_die_guete_haengt_nicht_an_der_laenge() -> None:
    """Das Gegenteil dessen, was Befund 14 in der anderen Richtung fand."""
    assert gemessen().guete_haengt_an_der_laenge() is False


def test_fallende_guete_wird_erkannt() -> None:
    """Waere Befund 14 auch hier sichtbar, muesste das Urteil es sagen."""
    faellt = Historienkurve(
        (
            Historienstufe("2017-08-16", 3277, 152, 152, 0.2000, 0.8640, 9, 11),
            Historienstufe("2022-08-16", 1451, 52, 52, 0.2903, 0.1347, 9, 11),
        )
    )
    assert faellt.guete_haengt_an_der_laenge() is True
    assert "kostet Qualitaet" in faellt.urteil()
    assert "Befund 14" in faellt.urteil()


def test_kuerzestes_fenster_ohne_guete_ist_unentscheidbar() -> None:
    ohne = Historienkurve(
        (
            Historienstufe("2017-08-16", 3277, 152, 152, 0.2765, 0.8640, 9, 11),
            Historienstufe("2022-08-16", 1451, 52, 52, 0.0, 0.1347, 9, 11),
        )
    )
    assert ohne.guete_haengt_an_der_laenge() is None


# --- Sammelrate und Hochrechnung --------------------------------------------


def test_sammelrate_uebergeht_die_kurzen_fenster() -> None:
    """Dort frisst die Aufwaermphase des Walk-Forward einen groesseren Anteil."""
    kurve = gemessen()
    assert kurve.sammelrate() == pytest.approx(44.7, abs=0.2)
    # Mit den kurzen Fenstern faellt die Rate messbar.
    assert kurve.sammelrate(mindesttage=0) < kurve.sammelrate()


def test_sammelrate_ohne_langes_fenster_ist_none() -> None:
    kurz = Historienkurve(
        (Historienstufe("2022-08-16", 1451, 52, 52, 0.2903, 0.1347, 9, 11),)
    )
    assert kurz.sammelrate(mindesttage=2000) is None


def test_fehlende_beobachtungen_und_tage() -> None:
    kurve = gemessen(ziel=181)
    assert kurve.fehlende_beobachtungen() == 29
    tage = kurve.fehlende_tage()
    assert tage is not None
    assert 600 <= tage <= 680, tage


def test_erreichtes_ziel_gibt_null_fehlende() -> None:
    assert gemessen(ziel=100).fehlende_beobachtungen() == 0
    assert gemessen(ziel=100).fehlende_tage() == 0


def test_ohne_ziel_gibt_es_keine_hochrechnung() -> None:
    kurve = gemessen(ziel=None)
    assert kurve.fehlende_beobachtungen() is None
    assert kurve.fehlende_tage() is None
    assert "hochgerechnet" not in kurve.urteil()


def test_urteil_nennt_den_verfall_des_deflated_sharpe() -> None:
    text = gemessen().urteil()
    assert "0.8640" in text and "0.1347" in text
    assert "Evidenz, nicht Vorteilsgroesse" in text


def test_urteil_weist_die_hochrechnung_als_solche_aus() -> None:
    """Befund 124: ein Punktschaetzer ohne Warnung ist eine Falle."""
    text = gemessen().urteil()
    assert "hochgerechnet, nicht gemessen" in text


def test_es_gibt_keine_methode_fuer_das_beste_fenster() -> None:
    """Dieselbe Sperre wie in decke.Fensterlage - sonst waere es Suche."""
    verboten = [
        n
        for n in dir(Historienkurve)
        if not n.startswith("_") and ("best" in n.lower() or "waehl" in n.lower())
    ]
    assert verboten == []
