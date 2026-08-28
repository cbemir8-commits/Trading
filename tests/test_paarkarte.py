"""Tests fuer ``research.paarkarte`` - Befund 141."""

from __future__ import annotations

import pytest

from research.paarkarte import Paar, Paarfeld


def _paar(name: str, *, guete: float, noetig: float, roh: int = 200,
          effektiv: int = 120) -> Paar:
    return Paar(
        name=name, partner_trades=60, partner_sharpe=0.2,
        roh=roh, effektiv=effektiv, guete=guete, noetig=noetig,
    )


class TestPaar:
    def test_die_luecke_ist_die_differenz_zur_latte(self) -> None:
        assert _paar("x", guete=3.073, noetig=3.625).luecke == pytest.approx(0.552)

    def test_mehr_unabhaengige_als_rohe_geht_nicht(self) -> None:
        with pytest.raises(ValueError, match="das geht nicht"):
            _paar("kaputt", guete=3.0, noetig=3.6, roh=100, effektiv=101)

    def test_behaltequote(self) -> None:
        p = _paar("x", guete=3.0, noetig=3.6, roh=200, effektiv=150)
        assert p.behaltequote == pytest.approx(0.75)

    def test_reicht_erst_ab_der_latte(self) -> None:
        assert not _paar("knapp", guete=3.624, noetig=3.625).reicht
        assert _paar("drueber", guete=3.625, noetig=3.625).reicht


class TestOrdnung:
    """**Der Kern des Moduls.** Nach Luecke, nicht nach Guete."""

    def test_die_hoehere_guete_kann_der_schlechtere_fund_sein(self) -> None:
        """Genau der gemessene Fall aus Befund 141.

        'Abfolge-Modell short' hat die hoehere Guete (3,032 gegen 2,888) und
        die groessere Luecke (0,692 gegen 0,786)... nein, umgekehrt: Es hat
        die hoehere Guete **und** die groessere Luecke als der Partner mit
        n = 124, weil es gegen eine hoehere Latte antritt.
        """
        # n = 124 gegen n = 191 - die Latte steigt mit n.
        klein = _paar("n=124", guete=3.073, noetig=3.625, roh=207, effektiv=124)
        gross = _paar("n=191", guete=3.032, noetig=3.725, roh=221, effektiv=191)
        feld = Paarfeld("Bestand", 2.730, 3.600, (gross, klein))

        assert gross.guete < klein.guete
        assert gross.luecke > klein.luecke
        assert feld.geordnet[0] is klein, "geordnet wird nach der Luecke"

    def test_nach_guete_geordnet_kaeme_ein_anderer_zuerst(self) -> None:
        """Die Gegenprobe: Waere die Guete das Mass, stuende der andere oben.

        Ohne diesen Test koennte die Ordnung zufaellig richtig sein.
        """
        klein = _paar("n=124", guete=3.073, noetig=3.625, roh=207, effektiv=124)
        hoch = _paar("hohe Guete", guete=3.400, noetig=4.100, roh=500,
                     effektiv=400)
        feld = Paarfeld("Bestand", 2.730, 3.600, (klein, hoch))

        nach_guete = sorted(feld.paare, key=lambda p: -p.guete)
        assert nach_guete[0] is hoch
        assert feld.geordnet[0] is klein


class TestPaarfeld:
    def _feld(self) -> Paarfeld:
        return Paarfeld(
            bestand="Trend 50 Tage mit Konfluenz",
            allein_guete=2.730,
            allein_noetig=3.600,
            paare=(
                # Luecke 0,552 - klar besser als die 0,870 des Bestands.
                _paar("gut", guete=3.073, noetig=3.625, roh=207, effektiv=124),
                # Luecke 0,935 - klar schlechter. Bewusst **nicht** genau auf
                # der Grenze: Ein Test, der auf 0,870 gegen 0,870 steht, misst
                # Gleitkomma-Rauschen und nicht die Regel.
                _paar("mittel", guete=2.700, noetig=3.635, roh=260, effektiv=130),
                _paar("schlecht", guete=2.082, noetig=3.673, roh=278,
                      effektiv=153),
            ),
        )

    def test_keiner_erreicht_die_latte(self) -> None:
        assert self._feld().erreichen == ()

    def test_besser_als_allein_vergleicht_luecken(self) -> None:
        """Der Bestand allein hat 0,870 Luecke; wer darunter liegt, ist besser."""
        feld = self._feld()
        namen = [p.name for p in feld.besser_als_allein]

        assert namen == ["gut"], (
            "'mittel' hat 0,935 und 'schlecht' 1,591 - beide schlechter"
        )

    def test_eine_auswahl_kostet_alle_geprueften(self) -> None:
        """**Der Punkt, an dem Befund 27 und 73 haengen.**"""
        assert self._feld().kosten_einer_auswahl == 3

    def test_das_urteil_nennt_den_preis_der_auswahl(self) -> None:
        text = self._feld().urteil()

        assert "3 Versuche" in text
        assert "nicht einen" in text

    def test_das_urteil_nennt_den_naechsten_wenn_keiner_reicht(self) -> None:
        text = self._feld().urteil()

        assert "Am naechsten kam 'gut'" in text
        assert "0.552" in text

    def test_ein_leeres_feld_urteilt_nicht(self) -> None:
        leer = Paarfeld("Bestand", 2.730, 3.600, ())

        assert "kein Urteil" in leer.urteil()


class TestDerModulkopf:
    """Die gemessenen Zahlen stehen im Kopf und veralten dort still."""

    def test_der_kopf_nennt_das_ergebnis_und_die_fundstelle(self) -> None:
        import research.paarkarte as modul

        kopf = modul.__doc__ or ""
        assert "Befund 141" in kopf
        assert "0,552" in kopf
        assert "Keines der vierzehn erreicht die Latte" in kopf

    def test_der_kopf_haelt_die_korrektur_an_befund_140_fest(self) -> None:
        """Die Behaltequote sagt nichts - das steht gegen die Erzaehlung dort."""
        import research.paarkarte as modul

        kopf = modul.__doc__ or ""
        assert "Befund 140" in kopf
        assert "nicht** vorher" in kopf or "nicht* vorher" in kopf
