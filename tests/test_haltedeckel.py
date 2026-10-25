"""Ein Haltedeckel hebt den Deflated Sharpe - und besteht nicht (Befund 416).

Befund 177 hat vier Deckel auf **gepflanzten** Trends gemessen. Auf der echten
Zulassungsreihe war es nie gemessen, und daran haengt die Mengen-Route zum
Deflated Sharpe.

Das Ergebnis ist der groesste Sprung, den dieses Gate in der Kette 403 bis 415
gesehen hat - und ein Suchergebnis, kein Eigenschaftsbefund. Die Tests hier
halten beides fest: die Messung **und** dass daraus kein Einbau folgt.
"""

from __future__ import annotations

import pytest

from research.haltedeckel import (
    DECKEL,
    VERSUCHE_GEZAEHLT,
    VERSUCHE_IM_LAUF,
    bester,
    ist_mengeneffekt,
)


def _deckel(kerzen: int):
    return next(d for d in DECKEL if d.kerzen == kerzen)


class TestDerUngedeckelteLaufIstDerMassgebliche:
    """Die Gegenprobe, ohne die die Tabelle nichts wert waere."""

    def test_deckel_null_trifft_den_spotpunkt(self) -> None:
        from research.referenz import SPOTPUNKT

        ohne = _deckel(0)

        assert ohne.fertig == SPOTPUNKT.trades
        assert ohne.n_eff == SPOTPUNKT.effektiv
        assert ohne.guete == pytest.approx(SPOTPUNKT.guete)
        assert ohne.dsr == pytest.approx(SPOTPUNKT.dsr, abs=5e-4)
        assert (ohne.bestanden, ohne.gesamt) == (
            SPOTPUNKT.bestanden,
            SPOTPUNKT.gesamt,
        )

    def test_und_wird_von_keinem_deckel_beendet(self) -> None:
        assert _deckel(0).deckel_ausstiege == 0


class TestEsIstKeinMengeneffekt:
    """Der Punkt, der die Mengen-Route schliesst."""

    def test_die_trade_zahl_bewegt_sich_nicht(self) -> None:
        zahlen = [d.fertig for d in DECKEL]

        assert min(zahlen) == 156
        assert max(zahlen) == 158
        assert not ist_mengeneffekt()

    def test_der_deckel_greift_aber_wirklich(self) -> None:
        """Dieselbe Gegenprobe wie in Befund 177: Gleiche Trade-Zahlen sehen
        aus, als taete der Regler nichts."""
        for kerzen in (10, 20, 40, 60, 90):
            d = _deckel(kerzen)

            assert d.deckel_ausstiege > 0, kerzen
            assert d.laengster_halt == kerzen, kerzen

    def test_und_je_kuerzer_desto_haeufiger(self) -> None:
        ausstiege = [_deckel(k).deckel_ausstiege for k in (10, 20, 40, 60, 90)]

        assert ausstiege == sorted(ausstiege, reverse=True)


class TestEsIstEinGueteeffekt:
    def test_der_beste_deckel_ist_vierzig(self) -> None:
        assert bester().kerzen == 40

    def test_er_hebt_guete_und_stichprobe(self) -> None:
        ohne, mit = _deckel(0), _deckel(40)

        assert mit.guete > ohne.guete
        assert mit.n_eff > ohne.n_eff

    def test_und_den_deflated_sharpe_um_0_21(self) -> None:
        ohne, mit = _deckel(0), _deckel(40)

        assert mit.dsr - ohne.dsr == pytest.approx(0.2077, abs=5e-4)

    def test_die_bindende_einteilung_wechselt_unter_jedem_deckel(self) -> None:
        """Gemessen und nicht erwartet: Der Deckel kuerzt die Haltedauer, und
        damit bindet statt des Quartals der Monat (Befund 410)."""
        assert _deckel(0).bindend == "Kalenderquartal"
        for kerzen in (10, 20, 40, 60, 90):
            assert _deckel(kerzen).bindend == "Kalendermonat", kerzen


class TestUndTrotzdemBestehtNichts:
    def test_alle_deckel_bleiben_bei_neun_von_elf(self) -> None:
        for d in DECKEL:
            assert (d.bestanden, d.gesamt) == (9, 11), d.kerzen

    def test_dem_besten_fehlen_0_164(self) -> None:
        assert 0.95 - bester().dsr == pytest.approx(0.1597, abs=5e-4)

    def test_und_die_messlatte_wird_schlechter(self) -> None:
        """Das Gate, das am naechsten dran war, bewegt sich weg - 14,1220
        statt 14,3391. Es steht im Kopf, weil die Tabelle es nicht traegt."""
        import research.haltedeckel as h

        kopf = h.__doc__ or ""

        assert "14,1220 statt 14,3391" in kopf
        assert "schlechter" in kopf


class TestEsIstEinKandidatUndKeinErgebnis:
    def test_der_gipfel_ist_nicht_monoton(self) -> None:
        """Die Signatur eines Suchergebnisses: Der beste Wert liegt in der
        Mitte der probierten Reihe, nicht am Rand."""
        nach_kerzen = sorted(DECKEL, key=lambda d: d.kerzen)
        dsr = [d.dsr for d in nach_kerzen]
        gipfel = dsr.index(max(dsr))

        assert 0 < gipfel < len(dsr) - 1
        assert dsr != sorted(dsr)
        assert dsr != sorted(dsr, reverse=True)

    def test_die_versuche_werden_mitgerechnet(self) -> None:
        """Befund 232: Jeder Versuch hebt die Latte. Sechs probiert, also
        sechs gezaehlt."""
        assert VERSUCHE_GEZAEHLT < VERSUCHE_IM_LAUF
        assert bester().dsr == pytest.approx(VERSUCHE_IM_LAUF)

    def test_und_auch_gezaehlt_reicht_es_nicht(self) -> None:
        assert VERSUCHE_GEZAEHLT < 0.95

    def test_der_kopf_sagt_dass_nichts_eingebaut_wird(self) -> None:
        import research.haltedeckel as h

        kopf = h.__doc__ or ""

        assert "wird daher nicht eingebaut" in kopf
        assert "gehoert in den Wettbewerb" in kopf

    def test_und_warum(self) -> None:
        import research.haltedeckel as h

        kopf = h.__doc__ or ""

        assert "Parameter nach dem Ergebnis gewaehlt" in kopf
        assert "Umgehung des eigenen Verfahrens" in kopf

    def test_der_standard_bleibt_ungedeckelt(self) -> None:
        """Die Gegenprobe zum Satz oben: Die Konfiguration ist unveraendert."""
        from backtest.engine import BacktestConfig

        assert BacktestConfig.__dataclass_fields__["max_hold_bars"].default == 0


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_den_sprung_und_die_luecke(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 416)

        assert "**0,7903**" in eintrag.ergebnis
        assert "fehlen 0,164" in eintrag.ergebnis

    def test_und_dass_es_kein_mengeneffekt_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 416)

        assert "kein Mengeneffekt" in eintrag.ergebnis
        assert "156 und 158" in eintrag.ergebnis

    def test_und_dass_er_nicht_eingebaut_wird(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 416)

        assert "Der Deckel wird daher nicht eingebaut" in eintrag.ergebnis
        assert "gehoert in den Wettbewerb" in eintrag.ergebnis
        assert "0,7858" in eintrag.ergebnis

    def test_die_offene_richtung_395_ist_eingeschraenkt(self) -> None:
        """Das Guthaben von 0,39 Punkten gehoert der ungedeckelten
        Haltedauer, nicht dem Kandidaten."""
        from research.stand import OFFEN

        eintrag = next(o for o in OFFEN if o.befund == 395)

        assert eintrag.zuletzt == 416
        assert "-6,9400" in eintrag.ergebnis
        assert "Daraus folgt kein Ausweg" in eintrag.ergebnis

    def test_und_415_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 415).zuletzt == 416
