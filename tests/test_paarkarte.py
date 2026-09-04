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


class TestWieFruehEsGereichtHaette:
    """**Befund 194.** Die Frage aus Befund 189, auf den Verbundweg angewandt.

    Befund 189 hat gemessen, bis zu welchem Versuchsstand eine Guete die
    Schwelle noch raeumt, und daraus geschlossen: Suchdisziplin war nie der
    Hebel. Gemessen war das am **Katalog** (beste Regel bis 8) und am
    **Bestand allein** (bis 21).

    Der Verbundweg faellt anders aus, und das gehoert in dasselbe Urteil.
    """

    def paar(self, guete: float, n: int, **momente) -> Paar:
        return Paar(
            name="Probe", partner_trades=142, partner_sharpe=0.205,
            roh=302, effektiv=n, guete=guete, noetig=3.771, **momente,
        )

    def test_das_beste_paar_kommt_in_die_naehe_des_zaehlers(self) -> None:
        """**Der tragende Test** - die Zahl aus Befund 194.

        'Trendfolge Ausbruch' als Verbund: Guete 3,663 bei n_eff 251. Der
        Zaehler steht bei 198, und dieses Paar haette bis in dieselbe
        Groessenordnung hinein bestanden - anders als alles andere, was
        dieses Projekt gemessen hat.
        """
        stand = self.paar(3.663, 251).bis()

        assert stand is not None
        assert 100 < stand < 200, f"gemessen {stand}"

    def test_es_bleibt_trotzdem_unter_dem_zaehler(self) -> None:
        """Naeher heisst nicht bestanden."""
        assert (self.paar(3.663, 251).bis() or 0) < 198

    def test_die_momente_werden_durchgereicht(self) -> None:
        mit_vorgabe = self.paar(3.663, 251).bis()
        neutral = self.paar(3.663, 251, schiefe=0.0, woelbung=3.0).bis()

        assert mit_vorgabe is not None and neutral is not None
        assert neutral < mit_vorgabe, (
            "eine neutrale Verteilung muss frueher an die Grenze stossen"
        )

    def test_ein_schwaches_paar_raeumt_gar_nichts(self) -> None:
        assert self.paar(0.2, 251).bis() is None

    def test_das_urteil_nennt_den_stand(self) -> None:
        feld = Paarfeld(
            "Bestand", 2.907, 3.650, (self.paar(3.663, 251),)
        )

        assert "Versuchsstand von" in feld.urteil()


def test_die_paartabelle_passt_in_achtzig_spalten() -> None:
    """**Befund 194**, dieselbe Lehre wie in Befund 189.

    Die Zeile stand schon vor der neuen Spalte bei 84 Zeichen und ist
    umgebrochen; 'fehlt' landete bei jeder Zeile allein darunter. Der Test
    liest die Breiten aus ``cli.py``, damit die naechste Spalte nicht wieder
    still umbricht.
    """
    import re
    from pathlib import Path

    quelle = (Path(__file__).resolve().parents[1] / "cli.py").read_text()
    kopf = re.search(
        r"\{'Partner':<(\d+)\} \{'P_n':>(\d+)\} \{'P_sr':>(\d+)\} "
        r"\{'roh':>(\d+)\} \{'n':>(\d+)\} \"\s*\n\s*f\"\{'Guete':>(\d+)\} "
        r"\{'noetig':>(\d+)\} \{'fehlt':>(\d+)\} \{'bis':>(\d+)\}",
        quelle,
    )
    assert kopf is not None, "Kopf der Paartabelle nicht gefunden"
    breiten = [int(x) for x in kopf.groups()]

    # Spaltenbreiten + je ein Trennzeichen + zwei fuehrende Leerzeichen.
    breit = sum(breiten) + (len(breiten) - 1) + 2
    assert breit <= 80, f"Zeile ist {breit} Zeichen breit"
