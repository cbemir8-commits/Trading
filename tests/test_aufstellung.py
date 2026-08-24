"""Tests fuer ``research.aufstellung`` - Befund 133.

Die gemessene Reihe (Spot, 198 Versuche, Tageskerzen, 3277 gemeinsame Tage)
steht in ``gemessen()``. Erfundene Reihen kommen nur dort vor, wo ein Zweig
sonst ungetestet bliebe.
"""

from __future__ import annotations

from math import sqrt

import pytest

from research.aufstellung import Aufstellungsreihe, Marktsatz


def gemessen() -> Aufstellungsreihe:
    return Aufstellungsreihe(
        (
            Marktsatz("BTC + ETH (Referenz)", 2, 3277, 152, 152, 0.2765, 0.8640, 9, 11),
            Marktsatz("+ LTC", 3, 3277, 258, 214, 0.2225, 0.7882, 7, 11),
            Marktsatz("+ XRP", 3, 3277, 260, 220, 0.2171, 0.7758, 9, 11),
            Marktsatz("+ LTC + XRP", 4, 3277, 366, 229, 0.1928, 0.5956, 9, 11),
        )
    )


# --- Marktsatz --------------------------------------------------------------


def test_aufstellung_ohne_markt_wird_abgewiesen() -> None:
    with pytest.raises(ValueError, match="keine Aufstellung"):
        Marktsatz("leer", 0, 3277, 152, 152, 0.2765, 0.8640, 9, 11)


def test_effektive_stichprobe_kann_die_rohe_nicht_uebersteigen() -> None:
    with pytest.raises(ValueError, match="nicht uebersteigen"):
        Marktsatz("kaputt", 2, 3277, 152, 153, 0.2765, 0.8640, 9, 11)


def test_evidenz_ist_guete_mal_wurzel_n() -> None:
    s = gemessen().referenz
    assert s is not None
    assert s.evidenz == pytest.approx(0.2765 * sqrt(152))
    assert s.evidenz == pytest.approx(3.409, abs=0.001)


def test_kuerzung_beisst_erst_bei_vier_maerkten() -> None:
    """Der Nachweis von Abhaengigkeit braucht selbst Beobachtungen."""
    reihe = gemessen()
    assert reihe.saetze[0].kuerzung == pytest.approx(0.0)
    assert reihe.saetze[-1].kuerzung == pytest.approx(1 - 229 / 366, abs=1e-6)
    assert reihe.saetze[-1].kuerzung > 0.35


def test_kuerzung_ohne_trades_ist_null() -> None:
    assert Marktsatz("leer", 1, 3277, 0, 0, 0.0, 0.0, 0, 11).kuerzung == 0.0


def test_zeile_zeigt_die_kennzahlen() -> None:
    zeile = gemessen().saetze[-1].als_zeile()
    assert "366" in zeile and "229" in zeile
    assert "0.5956" in zeile and "9/11" in zeile


# --- Die Reihe --------------------------------------------------------------


def test_leere_reihe_sagt_nichts() -> None:
    leer = Aufstellungsreihe()
    assert leer.referenz is None
    assert leer.stichprobe_waechst() is None
    assert leer.evidenz_waechst() is None
    assert leer.schlaegt_referenz() == ()
    assert "Keine Aufstellung" in leer.urteil()


def test_eine_aufstellung_ist_kein_vergleich() -> None:
    eine = Aufstellungsreihe(
        (Marktsatz("BTC + ETH", 2, 3277, 152, 152, 0.2765, 0.8640, 9, 11),)
    )
    assert "braucht zwei" in eine.urteil()
    assert eine.stichprobe_waechst() is None


def test_referenz_ist_der_erste_satz_nicht_der_beste() -> None:
    """Die Aufstellung nach den Ergebnissen auszusuchen waere Suche."""
    ref = gemessen().referenz
    assert ref is not None
    assert ref.name.startswith("BTC + ETH")


def test_die_stichprobe_waechst_sehr_wohl() -> None:
    """Befund 27s Zahl 'bleibt bei 150' ist heute nicht zu reproduzieren."""
    assert gemessen().stichprobe_waechst() is True


def test_die_evidenz_waechst_trotzdem_nicht() -> None:
    """Die Guete faellt schneller, als sqrt(n) steigt - Kopplung aus Befund 54."""
    assert gemessen().evidenz_waechst() is False


def test_die_evidenz_faellt_monoton() -> None:
    werte = [s.evidenz for s in gemessen().saetze]
    assert werte == sorted(werte, reverse=True)


def test_keine_aufstellung_schlaegt_die_referenz() -> None:
    assert gemessen().schlaegt_referenz() == ()


def test_ein_tausch_zaehlt_nicht_als_geschlagen() -> None:
    """Mehr Gates, dafuer weniger Evidenz - das ist keine Verbesserung."""
    getauscht = Aufstellungsreihe(
        (
            Marktsatz("BTC + ETH", 2, 3277, 152, 152, 0.2765, 0.8640, 9, 11),
            Marktsatz("+ LTC", 3, 3277, 258, 214, 0.2225, 0.7882, 10, 11),
        )
    )
    assert getauscht.schlaegt_referenz() == ()
    assert "traegt nicht" in getauscht.urteil()


def test_echte_verbesserung_wird_gemeldet() -> None:
    besser = Aufstellungsreihe(
        (
            Marktsatz("BTC + ETH", 2, 3277, 152, 152, 0.2765, 0.8640, 9, 11),
            Marktsatz("+ LTC", 3, 3277, 258, 240, 0.2900, 0.9100, 10, 11),
        )
    )
    assert [s.name for s in besser.schlaegt_referenz()] == ["+ LTC"]
    assert "Die Breite traegt" in besser.urteil()
    assert "zu pruefen" in besser.urteil()


def test_urteil_nennt_den_grund_und_nicht_nur_das_ergebnis() -> None:
    text = gemessen().urteil()
    assert "traegt nicht" in text
    assert "152 auf 229" in text
    assert "sqrt(n)" in text
    assert "3.409" in text


def test_urteil_ohne_wachsende_stichprobe_sagt_das_andere() -> None:
    flach = Aufstellungsreihe(
        (
            Marktsatz("BTC + ETH", 2, 3277, 152, 152, 0.2765, 0.8640, 9, 11),
            Marktsatz("+ LTC", 3, 3277, 258, 150, 0.2225, 0.7882, 9, 11),
        )
    )
    assert flach.stichprobe_waechst() is False
    assert "waechst dabei nicht" in flach.urteil()


def test_es_gibt_keine_methode_fuer_die_beste_aufstellung() -> None:
    """Dieselbe Sperre wie in decke.Fensterlage und historie.Historienkurve."""
    verboten = [
        n
        for n in dir(Aufstellungsreihe)
        if not n.startswith("_") and ("best" in n.lower() or "waehl" in n.lower())
    ]
    assert verboten == []
