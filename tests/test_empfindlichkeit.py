"""Tests fuer ``research.empfindlichkeit`` - Befund 134.

Die gemessene Lage (Spot, 198 Versuche, 152 Trades, 31 Kalenderfenster) steht
in ``gemessen()``. Der Designeffekt ist 1,4422 bei einem ICC von 0,109 und
liegt am 92,5. Perzentil der Null - die Regel kuerzt deshalb nicht, aber knapp.
"""

from __future__ import annotations

import pytest

from research.empfindlichkeit import Empfindlichkeit, Kalibrierung


def gemessen(**kw) -> Empfindlichkeit:
    werte = dict(
        roh=152,
        icc=0.109,
        designeffekt=1.4422,
        p_wert=0.0750,
        kalibrierungen=(
            Kalibrierung("95. Perzentil (Regel)", 0.95, 1.5262, 152, 0.8640, 1.8),
            Kalibrierung("90. Perzentil", 0.90, 1.3701, 144, 0.8266, 2.4),
            Kalibrierung("75. Perzentil", 0.75, 1.1420, 120, 0.6695, None),
            Kalibrierung("Median", 0.50, 1.0000, 105, 0.5393, 6.6),
        ),
    )
    werte.update(kw)
    return Empfindlichkeit(**werte)


# --- Kalibrierung -----------------------------------------------------------


def test_quantil_ausserhalb_von_null_bis_eins_wird_abgewiesen() -> None:
    with pytest.raises(ValueError, match="kein Perzentil"):
        Kalibrierung("kaputt", 1.5, 1.0, 152, 0.8640)
    with pytest.raises(ValueError, match="kein Perzentil"):
        Kalibrierung("kaputt", 0.0, 1.0, 152, 0.8640)


def test_zeile_zeigt_die_jahre_nur_wenn_es_sie_gibt() -> None:
    mit = Kalibrierung("Median", 0.50, 1.0, 105, 0.5393, 6.6)
    ohne = Kalibrierung("Median", 0.50, 1.0, 105, 0.5393)
    assert "6.6" in mit.als_zeile()
    assert mit.als_zeile().rstrip().endswith("6.6")
    assert ohne.als_zeile().rstrip().endswith("0.5393")


# --- Empfindlichkeit --------------------------------------------------------


def test_referenz_ist_die_regel_im_code_nicht_die_guenstigste() -> None:
    ref = gemessen().referenz
    assert ref is not None
    assert ref.quantil == 0.95
    assert ref.effektiv == 152


def test_ohne_passende_referenz_gibt_es_keine() -> None:
    ohne = gemessen(referenz_quantil=0.99)
    assert ohne.referenz is None
    assert ohne.luecke is None
    assert "Zu wenig gemessen" in ohne.urteil()


def test_spanne_ist_der_abstand_zwischen_bester_und_schlechtester() -> None:
    assert gemessen().spanne == pytest.approx(0.8640 - 0.5393)


def test_eine_kalibrierung_ergibt_keine_spanne() -> None:
    eine = gemessen(
        kalibrierungen=(
            Kalibrierung("95. Perzentil (Regel)", 0.95, 1.5262, 152, 0.8640),
        )
    )
    assert eine.spanne is None
    assert eine.uebersteigt_die_luecke() is None


def test_luecke_zaehlt_von_der_referenz_aus() -> None:
    assert gemessen().luecke == pytest.approx(0.95 - 0.8640)


def test_die_modellwahl_waehlt_mehr_aus_als_der_abstand() -> None:
    """Das unbequeme Ergebnis: 0,3247 Spanne gegen 0,0860 Luecke."""
    lage = gemessen()
    assert lage.uebersteigt_die_luecke() is True
    assert lage.spanne > lage.luecke * 3


def test_kleine_spanne_traegt_den_abstand() -> None:
    eng = gemessen(
        kalibrierungen=(
            Kalibrierung("95. Perzentil (Regel)", 0.95, 1.5262, 152, 0.8640),
            Kalibrierung("Median", 0.50, 1.0000, 150, 0.8600),
        )
    )
    assert eng.uebersteigt_die_luecke() is False
    assert "Abstand traegt" in eng.urteil()


def test_knapp_erkennt_den_p_wert_dicht_ueber_der_grenze() -> None:
    assert gemessen().knapp() is True
    assert gemessen(p_wert=0.4).knapp() is False


def test_ein_nachgewiesener_p_wert_ist_nicht_knapp_sondern_darunter() -> None:
    """Bei p <= 0,05 wuerde gekuerzt - das ist kein Grenzfall mehr."""
    assert gemessen(p_wert=0.03).knapp() is False


def test_urteil_nennt_spanne_luecke_und_den_grenzfall() -> None:
    text = gemessen().urteil()
    assert "0.3247" in text
    assert "0.0860" in text
    assert "waehlt mehr aus" in text
    assert "0.0750" in text


def test_urteil_ohne_grenzfall_laesst_den_zusatz_weg() -> None:
    text = gemessen(p_wert=0.4).urteil()
    assert "waehlt mehr aus" in text
    assert "gegen die Grenze" not in text


def test_es_gibt_keine_methode_die_eine_kalibrierung_auswaehlt() -> None:
    """Die wirksamste Lockerung von allen - sie liegt unter allen Gates."""
    verboten = [
        n
        for n in dir(Empfindlichkeit)
        if not n.startswith("_") and ("best" in n.lower() or "waehl" in n.lower())
    ]
    assert verboten == []
