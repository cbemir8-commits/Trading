"""Der Erfuellungsvorsprung kippt mit dem Mass - Befund 414.

Befund 407 hat dem kontogeschuetzten Punkt einen Erfuellungsvorsprung
zugeschrieben: 0,8298 gegen 0,8027, plus 2,7 Punkte. Er ruht auf n_eff 159 von
160, und Befund 413 hat gemessen, dass diese 159 am Waehrungsmass haengen.

Nachgerechnet wechselt der Vorsprung das Vorzeichen. Damit kann er die
Modusfrage aus Befund 400 nicht tragen.
"""

from __future__ import annotations

import pytest

from research.grenzgedaechtnis import (
    MASSFAKTOREN,
    erfuellung_je_mass,
    vorsprung_je_mass,
)


def _faktor(punkt: str):
    return next(f for f in MASSFAKTOREN if f.punkt == punkt)


def _zeile(punkt: str, mass: str):
    return next(
        z for z in erfuellung_je_mass() if z[0] == punkt and z[1] == mass
    )


class TestDerGemeldetePunktIstMassinvariant:
    """Es ist nicht beides unsicher - genau das ist der Punkt."""

    def test_dieselbe_bindende_einteilung(self) -> None:
        f = _faktor("gemeldet")

        assert f.bindend_waehrung == f.bindend_r == "Kalenderquartal"

    def test_derselbe_faktor_und_dieselbe_zahl(self) -> None:
        f = _faktor("gemeldet")

        assert f.faktor_waehrung == pytest.approx(f.faktor_r)
        assert f.n_waehrung == f.n_r == 115
        assert f.massinvariant

    def test_und_derselbe_erfuellungsgrad(self) -> None:
        assert _zeile("gemeldet", "Waehrung")[6] == pytest.approx(
            _zeile("gemeldet", "R-Mass")[6]
        )


class TestDerKontogeschuetzteNicht:
    def test_die_bindende_einteilung_wechselt(self) -> None:
        f = _faktor("kontogeschuetzt")

        assert f.bindend_waehrung == "Kalendertag"
        assert f.bindend_r == "Kalenderquartal"
        assert not f.massinvariant

    def test_n_eff_faellt_von_159_auf_120(self) -> None:
        f = _faktor("kontogeschuetzt")

        assert f.n_waehrung == 159
        assert f.n_r == 120

    def test_die_waehrungsspalte_trifft_die_referenzpunkte(self) -> None:
        """Die Gegenprobe: Was hier als Waehrungsmass steht, ist das, was
        das Gate rechnet."""
        from research.referenz import KONTOPUNKT, SPOTPUNKT

        assert _faktor("gemeldet").n_waehrung == SPOTPUNKT.effektiv
        assert _faktor("kontogeschuetzt").n_waehrung == KONTOPUNKT.effektiv

    def test_und_der_plan_wird_deutlich_teurer(self) -> None:
        waehrung = _zeile("kontogeschuetzt", "Waehrung")
        r = _zeile("kontogeschuetzt", "R-Mass")

        assert waehrung[4] == 85 and r[4] == 124
        assert r[5] > waehrung[5]


class TestDerVorsprungKippt:
    def test_in_waehrung_liegt_er_vorn(self) -> None:
        assert vorsprung_je_mass()["Waehrung"] == pytest.approx(0.0271, abs=5e-4)

    def test_im_r_mass_zurueck(self) -> None:
        assert vorsprung_je_mass()["R-Mass"] == pytest.approx(-0.0691, abs=5e-4)

    def test_das_vorzeichen_wechselt(self) -> None:
        """Der Befund in einem Satz."""
        v = vorsprung_je_mass()

        assert v["Waehrung"] > 0 > v["R-Mass"]

    def test_und_die_zahlen_aus_407_stehen_noch(self) -> None:
        """Die Waehrungszeile ist unveraendert - berichtigt ist die
        **Lesart**, nicht die Messung von 407."""
        assert _zeile("kontogeschuetzt", "Waehrung")[6] == pytest.approx(
            0.8298, abs=5e-4
        )
        assert _zeile("gemeldet", "Waehrung")[6] == pytest.approx(
            0.8027, abs=5e-4
        )


class TestDieTabelleWirdGerechnet:
    def test_sie_kommt_aus_referenz(self) -> None:
        """Keine zweite gepflegte Liste zur selben Sache (Befund 408): Wer
        'referenz' aendert, aendert diese Tabelle mit."""
        from dataclasses import replace

        import research.grenzgedaechtnis as g
        from research.referenz import SPOTPUNKT

        enger = replace(SPOTPUNKT, guete=0.40)
        echt = g.erfuellung_je_mass
        import research.referenz as r

        alt = r.SPOTPUNKT
        try:
            r.SPOTPUNKT = enger
            neu = echt()
        finally:
            r.SPOTPUNKT = alt

        assert dict(
            ((z[0], z[1]), z[6]) for z in neu
        )[("gemeldet", "Waehrung")] != pytest.approx(0.8027, abs=5e-4)

    def test_vier_zeilen_zwei_punkte_zwei_masse(self) -> None:
        zeilen = erfuellung_je_mass()

        assert len(zeilen) == 4
        assert {z[1] for z in zeilen} == {"Waehrung", "R-Mass"}
        assert {z[0] for z in zeilen} == {"gemeldet", "kontogeschuetzt"}

    def test_fehlend_ist_noetig_minus_vorhanden(self) -> None:
        for punkt, mass, n, noetig, fehlend, *_ in erfuellung_je_mass():
            assert fehlend == noetig - n, (punkt, mass)


class TestWasNichtFolgt:
    def test_das_gate_bleibt_in_waehrung(self) -> None:
        text = erfuellung_je_mass.__doc__ or ""

        assert "rechnet in Waehrung, und dabei bleibt es" in text
        assert "nicht danach gewaehlt, wie das Ergebnis aussieht" in text

    def test_und_der_vorbehalt_steht_an_den_drei_stellen(self) -> None:
        from pathlib import Path

        import research.referenz as r
        from research.grenzgedaechtnis import Reichweite

        assert "kippt der Vorsprung" in (Reichweite.__doc__ or "")
        assert "minus 6,9" in (Reichweite.__doc__ or "")

        quelle = Path(r.__file__).read_text(encoding="utf-8")
        assert "die 159 haengen am Mass" in quelle
        assert "120" in quelle


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_umkehrung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(x for x in BEHOBEN if x.befund == 414)

        assert "120 statt 159" in eintrag.ergebnis
        assert "minus 6,9" in eintrag.ergebnis

    def test_und_dass_der_gemeldete_punkt_haelt(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(x for x in BEHOBEN if x.befund == 414)

        assert "massinvariant" in eintrag.ergebnis
        assert "nicht beides unsicher" in eintrag.ergebnis

    def test_und_die_folge_fuer_die_modusfrage(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(x for x in BEHOBEN if x.befund == 414)

        assert "Modusfrage aus Befund 400 nicht tragen" in eintrag.ergebnis

    def test_und_413_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(x for x in BEHOBEN if x.befund == 413).zuletzt == 414
