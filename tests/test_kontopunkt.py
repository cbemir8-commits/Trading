"""Der zweite Betriebspunkt stand in einem Modulkopf - Befund 409.

Befund 406 hat ihn benannt, 407 hat ihn durchgerechnet, und verzeichnet war er
nirgends: Die Planungszahlen des Projekts - ``noetiges_n``, ``noetige_guete``,
``AUSSICHT`` - rechnen aus einem ``Referenzpunkt``, und davon gab es zwei.

Dieselbe Lehre wie Befund 235, der den Satz dafuer geliefert hat: "Solange nur
ein Punkt verzeichnet war, blieb dieser Wert eine gepflegte Zahl in einem
Prosatext."
"""

from __future__ import annotations

import pytest

from research.referenz import KONTOPUNKT, SPOTPUNKT


class TestDerPunktIstVerzeichnet:
    def test_er_steht_im_modul(self) -> None:
        import research.referenz

        assert "KONTOPUNKT" in research.referenz.__all__

    def test_mit_den_zahlen_aus_befund_407(self) -> None:
        assert KONTOPUNKT.befund == 407
        assert KONTOPUNKT.trades == 160
        assert KONTOPUNKT.effektiv == 159
        assert KONTOPUNKT.guete == pytest.approx(0.2444)
        assert KONTOPUNKT.dsr == pytest.approx(0.6846)
        assert (KONTOPUNKT.bestanden, KONTOPUNKT.gesamt) == (8, 11)

    def test_und_den_momenten_die_der_plan_braucht(self) -> None:
        """Ohne Schiefe und Woelbung rechnet 'noetiges_n' aus Vorgaben statt
        aus diesem Punkt - der Fehler, den Befund 356 gefunden hat."""
        assert KONTOPUNKT.schiefe == pytest.approx(3.3119)
        assert KONTOPUNKT.woelbung == pytest.approx(14.6644)


class TestDieWerkzeugeReproduzierenBefund407:
    """Die Gegenprobe. Eine eingetragene Zahl, aus der die Werkzeuge etwas
    anderes rechnen als der Befund, der sie gemessen hat, waere schlimmer als
    keine."""

    def test_der_plan_braucht_244_wirksame_trades(self) -> None:
        assert KONTOPUNKT.noetiges_n() == 244

    def test_oder_eine_guete_von_0_2945(self) -> None:
        assert KONTOPUNKT.noetige_guete() == pytest.approx(0.2945, abs=5e-4)

    def test_und_es_fehlen_85_beobachtungen(self) -> None:
        assert KONTOPUNKT.noetiges_n() - KONTOPUNKT.effektiv == 85


class TestEsIstKeinDritterAnwaerter:
    def test_er_steht_nicht_besser_da(self) -> None:
        """Der Punkt, an dem die Korrektur aus 406 missverstanden werden
        koennte: Weniger Designeffekt heisst nicht naeher an der Zulassung."""
        assert KONTOPUNKT.bestanden < SPOTPUNKT.bestanden
        assert KONTOPUNKT.guete < SPOTPUNKT.guete
        fehlend_konto = KONTOPUNKT.noetiges_n() - KONTOPUNKT.effektiv
        fehlend_spot = SPOTPUNKT.noetiges_n() - SPOTPUNKT.effektiv

        assert fehlend_konto > fehlend_spot

    def test_der_kopf_sagt_wessen_entscheidung_das_ist(self) -> None:
        import inspect

        import research.referenz

        quelle = inspect.getsource(research.referenz)
        kopf = quelle.split("KONTOPUNKT = Referenzpunkt(")[0]

        assert "Was er nicht ist**: ein dritter Anwaerter" in kopf
        assert "Entscheidung des Nutzers (Befund 400)" in kopf
        assert "bezieht sich weiter auf ``SPOTPUNKT``" in kopf

    def test_und_zitiert_den_satz_aus_235(self) -> None:
        """Hier ist der Kommentar **das** Geprueifte: Der Satz aus Befund 235
        ist die Begruendung, warum der Punkt eingetragen gehoert. Darum
        'nur_prosa' - die Wache aus Befund 399 hat genau diese Zusicherung
        angehalten, und sie hatte recht."""
        import inspect

        import research.referenz
        from tests.quelltext import nur_prosa

        quelle = nur_prosa(inspect.getsource(research.referenz))

        assert "gepflegte Zahl in einem Prosatext" in quelle


class TestDieVierteStelleDerGuete:
    """Nebenbei gemessen, und der Grund, warum 407 (191) und dieses Modul
    (190) verschiedene Zahlen nennen, ohne dass eine falsch ist."""

    def test_eine_stelle_ist_eine_beobachtung_wert(self) -> None:
        from dataclasses import replace

        enger = replace(SPOTPUNKT, guete=0.27075)

        assert SPOTPUNKT.noetiges_n() == 190
        assert enger.noetiges_n() == 191

    def test_und_der_kopf_der_methode_sagt_es(self) -> None:
        text = SPOTPUNKT.noetiges_n.__doc__ or ""

        assert "vierte Stelle" in text
        assert "190" in text and "191" in text


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_den_unterschied_im_plan(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 409)

        assert "**244** noetige wirksame" in eintrag.ergebnis
        assert "0,8299" in eintrag.ergebnis

    def test_und_dass_er_kein_anwaerter_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 409)

        assert "Was er nicht ist**: ein dritter Anwaerter" in eintrag.ergebnis

    def test_und_408_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 408).zuletzt == 409


class TestDerVermerkAnDerWache:
    """Die Wache aus Befund 399 hat diese Datei angehalten - allein war sie
    gruen, in der vollen Suite rot. Der Grund gehoert an die Wache."""

    def _kopf(self) -> str:
        import tests.test_wachenaudit

        return tests.test_wachenaudit.__doc__ or ""

    def test_er_nennt_den_importstand(self) -> None:
        kopf = self._kopf()

        assert "haengt am Importstand" in kopf
        assert "allein gruen" in kopf

    def test_und_was_nachgemessen_ist(self) -> None:
        """Keine Schaetzung: Mit dem laengsten importierbaren Praefix sind es
        92 statt 91 aufgeloeste Stellen und genau ein weiterer Treffer."""
        kopf = self._kopf()

        assert "**92 statt 91**" in kopf
        assert "genau **eine** weitere" in kopf

    def test_und_warum_das_trotzdem_dasteht(self) -> None:
        kopf = self._kopf()

        assert "jederzeit wieder etwas durchlassen" in kopf
