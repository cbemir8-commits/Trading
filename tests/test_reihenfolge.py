"""Tests fuer ``research.reihenfolge`` - Befund 114."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from research.reihenfolge import STAND, Art, Lage, Schritt, Wer
from research.stand import zahlwort


def schritt(**kw) -> Schritt:
    werte = dict(
        name="Beispiel", art=Art.BEDINGUNG, wer=Wer.CONTAINER, befund=1,
    )
    werte.update(kw)
    return Schritt(**werte)


class TestSchritt:
    def test_ohne_fundstelle_ist_es_eine_meinung(self):
        with pytest.raises(ValueError, match="Meinung"):
            schritt(befund=0)

    def test_niemand_ist_nicht_machbar(self):
        assert not schritt(wer=Wer.NIEMAND).machbar
        assert schritt(wer=Wer.NUTZER).machbar

    def test_container_und_suche_sind_hier_machbar(self):
        """Die Suche laeuft hier - sie kostet nur Versuche.

        Im ersten Entwurf stand sie ausserhalb, und dann behauptete der
        Bericht, es gebe hier gar nichts mehr zu tun. Es gibt etwas; es ist
        nur gemessen aussichtslos.
        """
        assert schritt(wer=Wer.CONTAINER).hier_machbar
        assert schritt(wer=Wer.SUCHE).hier_machbar
        assert not schritt(wer=Wer.NUTZER).hier_machbar
        assert not schritt(wer=Wer.NIEMAND).hier_machbar

    def test_zeile_nennt_art_wer_und_fundstelle(self):
        zeile = schritt(name="Etwas", art=Art.SPERRE, wer=Wer.NUTZER, befund=102)
        text = zeile.als_zeile()
        assert "Sperre" in text
        assert "Nutzer" in text
        assert "102" in text


class TestLage:
    def test_ohne_schritte_kein_urteil(self):
        lage = Lage(schritte=())
        assert not lage.gesperrt
        assert "nichts zu sagen" in lage.urteil()

    def test_eine_sperre_macht_die_lage_gesperrt(self):
        lage = Lage(schritte=(schritt(art=Art.SPERRE, wer=Wer.NUTZER),))
        assert lage.gesperrt

    def test_bei_offener_sperre_wirkt_nur_die_sperre(self):
        """Der Kern: Arbeit hinter einer Sperre aendert den Zustand nicht."""
        sperre = schritt(name="Daten fehlen", art=Art.SPERRE, wer=Wer.NUTZER)
        arbeit = schritt(name="Bessere Regel", wer=Wer.SUCHE)
        lage = Lage(schritte=(sperre, arbeit))
        assert lage.wirkt(sperre)
        assert not lage.wirkt(arbeit)
        assert lage.wirksame() == (sperre,)
        assert lage.vergeblich() == (arbeit,)

    def test_ohne_sperre_wirkt_jeder_machbare_schritt(self):
        arbeit = schritt(name="Bessere Regel", wer=Wer.SUCHE)
        tot = schritt(name="Mehr Maerkte", wer=Wer.NIEMAND)
        lage = Lage(schritte=(arbeit, tot))
        assert lage.wirkt(arbeit)
        assert not lage.wirkt(tot)

    def test_aussichtslose_werden_benannt(self):
        tot = schritt(name="Mehr Maerkte", wer=Wer.NIEMAND)
        lage = Lage(schritte=(tot, schritt(wer=Wer.NUTZER)))
        assert lage.aussichtslos == (tot,)

    def test_urteil_bei_sperre_sagt_dass_elf_von_elf_nichts_waeren(self):
        lage = Lage(
            schritte=(
                schritt(name="Boersendaten fehlen", art=Art.SPERRE,
                        wer=Wer.NUTZER, befund=102),
            )
        )
        text = lage.urteil()
        assert "elf von elf" in text
        assert "Nutzer" in text

    def test_urteil_ohne_sperre_nennt_die_wirksamen(self):
        lage = Lage(schritte=(schritt(name="Bessere Regel", wer=Wer.SUCHE),))
        assert "Bessere Regel" in lage.urteil()

    def test_urteil_ohne_sperre_und_ohne_quelle_ist_ehrlich(self):
        lage = Lage(schritte=(schritt(wer=Wer.NIEMAND),))
        assert "kein machbarer Schritt" in lage.urteil()

    def test_beim_nutzer_und_hier_sind_getrennt(self):
        lage = Lage(
            schritte=(
                schritt(name="A", wer=Wer.NUTZER),
                schritt(name="B", wer=Wer.CONTAINER),
            )
        )
        assert [s.name for s in lage.beim_nutzer] == ["A"]
        assert [s.name for s in lage.hier] == ["B"]


class TestDerGemesseneStand:
    def test_die_sperre_steht_und_liegt_beim_nutzer(self):
        lage = Lage(schritte=STAND)
        assert lage.gesperrt
        assert all(s.wer is Wer.NUTZER for s in lage.sperren)

    def test_hier_laeuft_nur_die_suche_und_die_ist_wirkungslos(self):
        """Die Aussage des Befundes, als Test - in ihrer genauen Fassung.

        Der einzige Schritt, der aus diesem Container heraus liefe, ist die
        Suche. Sie ist gemessen aussichtslos (Nr. 110) und bei offener Sperre
        ohnehin ohne Wirkung auf den Zustand. Alles andere liegt beim Nutzer
        oder hat gemessen keine Quelle.
        """
        lage = Lage(schritte=STAND)
        assert [s.wer for s in lage.hier] == [Wer.SUCHE]
        assert all(not lage.wirkt(s) for s in lage.hier)

    def test_bei_offener_sperre_wirkt_nur_sie(self):
        lage = Lage(schritte=STAND)
        assert lage.wirksame() == lage.sperren
        assert len(lage.vergeblich()) == len(STAND) - len(lage.sperren)

    def test_die_beobachtungen_haben_keine_quelle(self):
        eintrag = next(s for s in STAND if "Beobachtungen" in s.name)
        assert eintrag.wer is Wer.NIEMAND
        assert eintrag.befund == 111

    def test_jede_fundstelle_steht_im_laborbuch(self):
        """Dieselbe Pruefung wie fuer ``GESCHLOSSEN`` in ``research/stand.py``.

        Eine Zeile ohne nachlesbaren Abschnitt waere eine Behauptung mit
        Nummer davor.
        """
        text = Path("strategies/BEFUND.md").read_text()
        ueberschriften = set(
            re.findall(r"^## ([A-Za-zaeoeueAEOEUEss]+)\.", text, re.M)
        )
        fehlend = sorted(
            {s.befund for s in STAND if zahlwort(s.befund) not in ueberschriften}
        )
        assert fehlend == [], f"Fundstellen ohne Abschnitt: {fehlend}"

    def test_keine_zeile_ohne_hinweis(self):
        """Eine Zeile, die nicht sagt, was zu tun waere, hilft niemandem."""
        assert all(s.hinweis for s in STAND)
