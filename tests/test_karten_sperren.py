"""Die beiden Karten, auf die das Plateau-Gate verweist - Befund 314.

Befund 313 hat gefunden, dass ``gate_parameter_plateau`` seine Nachbarn als
**durchgehende** Backtests faehrt: ein Risk-Officer ueber acht Jahre, keine
Fenstergrenze und damit nie die manuelle Freigabe, mit der die Engine im
Walk-Forward ausdruecklich rechnet. Not-Aus und Wochenlimit sind Zustaende
und keine Uhren - greift einer, handelt der Lauf bis zum letzten Balken
nicht mehr.

Das Gate verweist fuer die Breite des Gebiets auf ``cli plateaubild``:

    Wie weit das Gebiet nach unten reicht, sagen zwei Punkte nicht
    ('cli plateaubild' misst es)

Gemessen (Befund 314, BTC + ETH, Tageskerzen, zwoelf Faktoren):

    mit Sperren (so misst der Befehl)   72 von 72 Punkten gesperrt
                                        engste Achse 0,45, traegt 0,70-1,15
    ohne Sperren                        0 von 72 gesperrt
                                        engste Achse 0,60, traegt 0,70-1,30

**Jeder einzelne Punkt der Karte** steht auf einem Lauf, der 2020 aufgehoert
hat zu handeln. Die Karte, die das Gate als Aufloesung anbietet, hat
denselben Riss wie das Gate.

Gerechnet wird weiter durchgehend - die Zahlen sind dieselben. Beide Karten
sagen jetzt nur dazu, dass ihre Breite eine Untergrenze ist.
"""

from __future__ import annotations

import inspect

from research.landschaft import Landschaft as Karte
from research.landschaft import Punkt
from research.plateaubild import Achse, baue


# ---------------------------------------------------------------------------
#  plateaubild
# ---------------------------------------------------------------------------
def kurve(*werte: float | None) -> list[tuple[float, float | None]]:
    faktoren = [0.70, 0.80, 0.90, 1.10, 1.20, 1.30]
    return list(zip(faktoren[: len(werte)], werte, strict=True))


class TestDieAchseZaehltIhreSperren:
    def test_ohne_angabe_behauptet_sie_keine_null(self) -> None:
        """**Leer heisst 'nicht erhoben', nicht 'keine'.**

        Ein Aufrufer, der die Zahl nicht hat, soll nicht ungewollt
        versichern, dass nichts gesperrt wurde - genau die Sorte
        Zusicherung, die Befund 245 als Mangel-als-Zusicherung beschreibt.
        """
        achse = Achse(
            name="alle gemeinsam",
            faktoren=(0.8, 1.2),
            gewinne=(100.0, -50.0),
            basis=90.0,
        )

        assert achse.gesperrt == ()
        assert achse.gesperrte_punkte == 0

    def test_sie_zaehlt_punkte_und_einstiege_getrennt(self) -> None:
        achse = Achse(
            name="alle gemeinsam",
            faktoren=(0.8, 1.2, 1.3),
            gewinne=(100.0, -50.0, -60.0),
            basis=90.0,
            gesperrt=(0, 110, 62),
        )

        assert achse.gesperrte_punkte == 2
        assert achse.verhinderte_einstiege == 172
        assert not achse.zu_ende_gemessen

    def test_ohne_sperre_ist_sie_zu_ende_gemessen(self) -> None:
        achse = Achse(
            name="rsi(period=14)",
            faktoren=(0.8, 1.2),
            gewinne=(100.0, 90.0),
            basis=95.0,
            gesperrt=(0, 0),
        )

        assert achse.zu_ende_gemessen


class TestBaueReichtDieSperrenDurch:
    def test_ohne_angabe_bleibt_die_karte_wie_vorher(self) -> None:
        bild = baue({"a": kurve(10.0, 20.0)}, basis=15.0)

        assert bild.achsen[0].gesperrt == ()
        assert bild.gesperrte_punkte == 0

    def test_die_zuordnung_geht_ueber_den_faktor(self) -> None:
        """**Der Fehler, der hier lauert.** ``baue`` wirft Punkte mit
        ``None`` heraus. Wer die Sperren als Liste nach Position mitgaebe,
        verschoebe sie gegen die Faktoren, sobald ein Nachbar wegfaellt -
        und niemand saehe es.
        """
        bild = baue(
            {"a": kurve(10.0, None, 30.0)},
            basis=15.0,
            sperren={"a": {0.70: 5, 0.80: 999, 0.90: 7}},
        )
        achse = bild.achsen[0]

        assert achse.faktoren == (0.70, 0.90)
        assert achse.gesperrt == (5, 7), "der Wert von 0,80 gehoert nicht hierher"

    def test_ein_fehlender_faktor_gilt_als_null(self) -> None:
        bild = baue({"a": kurve(10.0, 20.0)}, basis=15.0, sperren={"a": {0.70: 5}})

        assert bild.achsen[0].gesperrt == (5, 0)

    def test_eine_achse_ohne_eintrag_stuerzt_nicht(self) -> None:
        bild = baue(
            {"a": kurve(10.0), "b": kurve(20.0)}, basis=15.0, sperren={"a": {0.70: 5}}
        )

        assert bild.verhinderte_einstiege == 5

    def test_die_karte_summiert_ueber_alle_achsen(self) -> None:
        bild = baue(
            {"a": kurve(10.0, 20.0), "b": kurve(30.0, 40.0)},
            basis=15.0,
            sperren={"a": {0.70: 5, 0.80: 6}, "b": {0.70: 7, 0.80: 0}},
        )

        assert bild.punkte_gesamt == 4
        assert bild.gesperrte_punkte == 3
        assert bild.verhinderte_einstiege == 18


class TestDerVorbehaltStehtVorn:
    """Die Breite ist die Kopfzahl dieses Befehls. Ist sie nicht die Breite
    des Parametergebiets, muss das **vor** ihr stehen."""

    def _bild(self, *, mit_sperren: bool):
        werte = (300.0, 400.0, 500.0, 450.0, 200.0, -100.0)
        sperren = (
            {"alle gemeinsam": dict.fromkeys([0.70, 0.80, 0.90, 1.10, 1.20, 1.30], 90)}
            if mit_sperren
            else None
        )
        return baue({"alle gemeinsam": kurve(*werte)}, basis=480.0, sperren=sperren)

    def test_mit_sperren_steht_er_da(self) -> None:
        text = self._bild(mit_sperren=True).urteil()

        assert "nicht zu Ende gemessen" in text
        assert "Untergrenze" in text
        assert "cli freigabe" in text

    def test_und_zwar_als_erstes(self) -> None:
        text = self._bild(mit_sperren=True).urteil()

        assert text.index("nicht zu Ende gemessen") < text.index("wirken ueberhaupt")

    def test_ohne_sperren_steht_er_nicht_da(self) -> None:
        text = self._bild(mit_sperren=False).urteil()

        assert "nicht zu Ende gemessen" not in text
        assert "wirken ueberhaupt" in text


class TestDieZahlenBleibenDieselben:
    """**Die Zeile, die diesen Vorbehalt von einer Lockerung trennt.**

    Gerechnet wird unveraendert durchgehend. Form, Breite und tragfaehiger
    Bereich haengen nicht daran, ob die Sperren mitgegeben wurden.
    """

    def test_form_breite_und_bereich_sind_unabhaengig_von_der_angabe(self) -> None:
        werte = (300.0, 400.0, 500.0, 450.0, 200.0, -100.0)
        ohne = baue({"a": kurve(*werte)}, basis=480.0)
        mit = baue(
            {"a": kurve(*werte)},
            basis=480.0,
            sperren={"a": dict.fromkeys([0.70, 0.80, 0.90, 1.10, 1.20, 1.30], 90)},
        )

        assert mit.achsen[0].form == ohne.achsen[0].form
        assert mit.achsen[0].breite == ohne.achsen[0].breite
        assert mit.achsen[0].tragfaehig == ohne.achsen[0].tragfaehig
        assert mit.achsen[0].spannweite == ohne.achsen[0].spannweite


# ---------------------------------------------------------------------------
#  landschaft
# ---------------------------------------------------------------------------
def punkt(faktor: float, gewinn: float, *, gesperrt: int = 0) -> Punkt:
    return Punkt(
        faktor=faktor,
        leitperiode=200,
        gewinn=gewinn,
        trades=40,
        gesperrt=gesperrt,
    )


class TestDieKarteSagtEsAuch:
    def test_der_punkt_zaehlt_seine_sperre(self) -> None:
        assert punkt(1.0, 100.0).zu_ende_gemessen
        assert not punkt(1.0, 100.0, gesperrt=48).zu_ende_gemessen

    def test_die_karte_summiert(self) -> None:
        karte = Karte(
            punkte=[
                punkt(0.8, 100.0, gesperrt=48),
                punkt(1.0, 200.0),
                punkt(1.2, -50.0, gesperrt=62),
            ]
        )

        assert karte.gesperrte_punkte == 2
        assert karte.verhinderte_einstiege == 110

    def test_der_vorbehalt_steht_vor_dem_urteil(self) -> None:
        karte = Karte(
            punkte=[
                punkt(0.8, 100.0, gesperrt=48),
                punkt(1.0, 200.0, gesperrt=48),
                punkt(1.2, 150.0, gesperrt=48),
            ]
        )
        text = karte.urteil()

        assert text.index("nicht zu Ende gemessen") < text.index("Plateau")
        assert "cli freigabe" in text

    def test_ohne_sperren_bleibt_das_urteil_wortgleich(self) -> None:
        karte = Karte(
            punkte=[punkt(0.8, 100.0), punkt(1.0, 200.0), punkt(1.2, 150.0)]
        )

        assert karte.urteil() == (
            "Plateau: 3 zusammenhaengende Punkte von 3, der Kandidat mittendrin."
        )

    def test_auch_das_grat_urteil_traegt_den_vorbehalt(self) -> None:
        """Gerade hier: 'Grat' klingt nach einer Aussage ueber die Gegend -
        sie kann der Zeitpunkt der Sperre sein."""
        karte = Karte(
            punkte=[
                punkt(0.8, -10.0, gesperrt=62),
                punkt(1.0, 200.0, gesperrt=48),
                punkt(1.2, -20.0, gesperrt=62),
            ]
        )
        text = karte.urteil()

        assert "nicht zu Ende gemessen" in text
        assert "Grat" in text

    def test_die_tabelle_zeigt_die_spalte(self) -> None:
        karte = Karte(punkte=[punkt(1.0, 100.0, gesperrt=48)])
        text = karte.tabelle()

        assert "gesperrt" in text
        assert "48" in text


class TestDieVerdrahtung:
    def test_kartieren_zaehlt_die_sperren(self) -> None:
        from research import landschaft

        quelle = inspect.getsource(landschaft.kartieren)

        assert "stillgelegt(" in quelle
        assert "gesperrt=gesperrt" in quelle

    def test_plateaubild_reicht_sie_dem_bauer(self) -> None:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text())
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "plateaubild"
        )

        assert "stillgelegt(" in quelle
        assert "sperren=sperren" in quelle

    def test_beide_karten_holen_dieselbe_regel(self) -> None:
        """Zwei Fassungen davon, welche Sperre dauerhaft ist, liefen frueher
        oder spaeter auseinander - in diesem Projekt schon mehrfach."""
        from research import landschaft
        from research.freigabe import stillgelegt as quelle

        assert landschaft.stillgelegt is quelle
