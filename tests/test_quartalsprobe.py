"""Der verwechselte Vergleich, und das Mass verdeckt - Befund 411.

Befund 410 hat gemessen, dass am gemeldeten Punkt das Kalenderquartal bindet,
und offen gelassen, warum die Quartalskorrelation am kontogeschuetzten Punkt
faellt. Dabei verglich er zwei Zellen, die sich in **zwei** Dingen zugleich
unterscheiden - Fensterschnitt und Beingrenzen -, und die vierte Zelle fehlte.

Dieselbe Sorte Fehler wie Befund 403 (ein Mechanismus geschlossen statt
gemessen) und 406 (eine Zelle fuer etwas genommen, was sie nicht beschreibt).
"""

from __future__ import annotations

import pytest

from research.grenzgedaechtnis import QUARTALSPROBE, Quartalsprobe


def _zelle(durchgehend: bool, limits: bool) -> Quartalsprobe:
    return next(
        z
        for z in QUARTALSPROBE
        if z.durchgehend is durchgehend and z.limits is limits
    )


class TestDasKreuzIstVollstaendig:
    def test_alle_vier_zellen(self) -> None:
        """Der Punkt des Befundes: 410 hatte drei."""
        assert len(QUARTALSPROBE) == 4
        assert {(z.durchgehend, z.limits) for z in QUARTALSPROBE} == {
            (False, True),
            (False, False),
            (True, True),
            (True, False),
        }

    def test_die_eckzellen_treffen_die_referenzpunkte(self) -> None:
        from research.referenz import KONTOPUNKT, SPOTPUNKT

        gemeldet = _zelle(durchgehend=False, limits=True)
        konto = _zelle(durchgehend=True, limits=False)

        assert (gemeldet.roh, gemeldet.n_eff) == (
            SPOTPUNKT.trades,
            SPOTPUNKT.effektiv,
        )
        assert (konto.roh, konto.n_eff) == (
            KONTOPUNKT.trades,
            KONTOPUNKT.effektiv,
        )

    def test_und_stimmen_mit_der_leiter_aus_410_zusammen(self) -> None:
        """Zwei gepflegte Listen zur selben Sache laufen auseinander
        (Befund 408). Also wird die eine aus der anderen geprueft."""
        from research.grenzgedaechtnis import LEITER, bindend

        paare = {
            "gemeldet": _zelle(durchgehend=False, limits=True),
            "durchgehend mit Beingrenzen": _zelle(
                durchgehend=True, limits=True
            ),
            "kontogeschuetzt": _zelle(durchgehend=True, limits=False),
        }
        for name, zelle in paare.items():
            assert zelle.bindend == bindend(name)[0], name
            assert zelle.n_eff == bindend(name)[5], name

            quartal = next(
                z for z in LEITER[name] if z[0] == "Kalenderquartal"
            )
            assert zelle.icc_waehrung == pytest.approx(quartal[2]), name
            assert zelle.p_waehrung == pytest.approx(quartal[3]), name


class TestEsIstDerFensterschnitt:
    """Der eigentliche Fund - und er loest den verwechselten Vergleich auf."""

    def test_beide_geschnittenen_kuerzen(self) -> None:
        for limits in (True, False):
            zelle = _zelle(durchgehend=False, limits=limits)

            assert zelle.kuerzt_in_waehrung, zelle.zelle
            # 0,0050 ist **nicht** kleiner als 0,005 - die erste Fassung
            # dieses Tests und der Prosatext daneben haben sich daran
            # verschluckt. Gemessen sind 0,0050 und 0,0040.
            assert zelle.p_waehrung <= 0.005, zelle.zelle
            assert zelle.icc_waehrung > 0.24, zelle.zelle

    def test_beide_durchgehenden_nicht(self) -> None:
        for limits in (True, False):
            zelle = _zelle(durchgehend=True, limits=limits)

            assert not zelle.kuerzt_in_waehrung, zelle.zelle
            assert zelle.p_waehrung > 0.08, zelle.zelle

    def test_die_beingrenzen_aendern_die_abhaengigkeit_nicht(self) -> None:
        """Sie aendern die Trade-Zahl - 156 gegen 160, 98 gegen 160 - und
        nicht die Quartalsabhaengigkeit."""
        mit = _zelle(durchgehend=False, limits=True)
        ohne = _zelle(durchgehend=False, limits=False)

        assert mit.roh != ohne.roh
        assert abs(mit.icc_waehrung - ohne.icc_waehrung) < 0.01

    def test_das_trennt_die_beiden_wirkungen(self) -> None:
        """Was 410 nicht konnte: Die beiden verglichenen Zellen
        unterscheiden sich in zwei Dingen, diese vier in je einem."""
        geschnitten = [
            z.kuerzt_in_waehrung for z in QUARTALSPROBE if not z.durchgehend
        ]
        durchgehend = [
            z.kuerzt_in_waehrung for z in QUARTALSPROBE if z.durchgehend
        ]

        assert all(geschnitten)
        assert not any(durchgehend)


class TestMeineErklaerungWarFalsch:
    """Die Vermutung war der Kapital-Neustart je Fenster. Im R-Mass, also
    ohne Groessenwirkung, muesste die Abhaengigkeit dann verschwinden."""

    def test_sie_verschwindet_nicht(self) -> None:
        zelle = _zelle(durchgehend=False, limits=True)

        assert zelle.kuerzt_im_r_mass
        assert zelle.icc_r == pytest.approx(0.2561, abs=5e-4)
        assert abs(zelle.icc_r - zelle.icc_waehrung) < 0.01

    def test_und_wird_im_r_mass_sogar_deutlicher(self) -> None:
        zelle = _zelle(durchgehend=False, limits=True)

        assert zelle.p_r < zelle.p_waehrung

    def test_der_kopf_sagt_dass_die_vermutung_falsch_war(self) -> None:
        import inspect

        import research.grenzgedaechtnis as g
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(g))

        assert "Meine Erklaerung dafuer war falsch" in text
        assert "kein Groessenartefakt" in text


class TestDasMassVerdecktImDurchgehendenModus:
    """Der ungesuchte Fund, und der folgenreichste."""

    def test_kontogeschuetzt_zeigt_das_r_mass_was_die_waehrung_nicht_zeigt(
        self,
    ) -> None:
        zelle = _zelle(durchgehend=True, limits=False)

        assert not zelle.kuerzt_in_waehrung
        assert zelle.kuerzt_im_r_mass
        assert zelle.icc_r > 2.5 * zelle.icc_waehrung

    def test_und_zwar_so_hoch_wie_am_gemeldeten_punkt(self) -> None:
        konto = _zelle(durchgehend=True, limits=False)
        gemeldet = _zelle(durchgehend=False, limits=True)

        assert abs(konto.icc_r - gemeldet.icc_r) < 0.01

    def test_auch_die_beingebremste_durchgehende_zelle(self) -> None:
        zelle = _zelle(durchgehend=True, limits=True)

        assert not zelle.kuerzt_in_waehrung
        assert zelle.kuerzt_im_r_mass

    def test_die_reichweite_traegt_den_vorbehalt(self) -> None:
        """Dort steht der Erfuellungsvorsprung, der auf diesem n_eff ruht."""
        from research.grenzgedaechtnis import Reichweite

        text = Reichweite.__doc__ or ""

        assert "weniger wert, als er aussieht" in text
        assert "kein Nachweis von Unabhaengigkeit" in text
        assert "QUARTALSPROBE" in text


class TestWasNichtFolgt:
    def test_das_gate_wechselt_das_mass_nicht(self) -> None:
        """Und zwar auch dann nicht, wenn das andere Mass strenger ausfaellt
        - sonst waere die Wahl des Masses eine Frage des Ergebnisses."""
        import inspect

        import research.grenzgedaechtnis as g
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(g))

        assert "dass das Gate das Mass wechseln soll" in text
        assert "guenstig ausfaellt, lockert das Gate" in text

    def test_der_fund_faellt_zur_strengen_seite(self) -> None:
        """Die Richtung, in die ein solcher Fund fallen darf: Er macht den
        Ausfall robuster, nicht schwaecher."""
        konto = _zelle(durchgehend=True, limits=False)

        assert konto.icc_r > konto.icc_waehrung

    def test_und_was_offen_bleibt(self) -> None:
        import inspect

        import research.grenzgedaechtnis as g
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(g))

        assert "warum der Fensterschnitt die Quartalsabhaengigkeit" in text


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_den_verwechselten_vergleich(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 411)

        assert "verwechselt" in eintrag.ergebnis
        assert "121 von 160" in eintrag.ergebnis

    def test_und_die_eigene_falsche_erklaerung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 411)

        assert "Meine Erklaerung dafuer war falsch" in eintrag.ergebnis

    def test_und_die_folge_fuer_407(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 411)

        assert "kein Nachweis von" in eintrag.ergebnis
        assert "robuster, nicht schwaecher" in eintrag.ergebnis

    def test_und_410_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 410).zuletzt == 411
