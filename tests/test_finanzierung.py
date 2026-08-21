"""Die teuerste Annahme des Systems steht auf einem Vorgabewert.

Drei Tests tragen diese Datei:

``test_funding_ist_der_groesste_kostenblock`` - Der Kern. 7,17 EUR
Handelsgebuehren gegen 63,79 EUR Funding: das 8,9-fache. Das Projekt hat ein
Kosten-Stress-Gate und mehrere Befunde ueber Gebuehrenmodelle, und der
groessere Posten steht die ganze Zeit auf einem ungeprueften Vorgabewert.

``test_zwei_gates_haengen_am_satz`` - Was daran haengt. Zwischen 5,5 % und
11 % im Jahr kippen Schlechtestes Jahr und Parameter-Plateau, zwischen 21,9 %
und 32,9 % zusaetzlich der Drawdown.

``test_die_nullzeile_wird_nicht_als_hoffnung_verkauft`` - Die Falle. Bei 0 %
stuende der Bestand auf 9 von 11. Funding entfaellt aber nur im Spot-Handel,
und dort entfaellt auch der Hebel.
"""

from __future__ import annotations

import pytest

from research.finanzierung import (
    BASISSATZ,
    PERIODEN_JE_JAHR,
    Finanzierung,
    Stufe,
)

#: Die gemessene Leiter des Bestands auf BTC + ETH, Tageskerzen, 500 EUR,
#: Versuchsstand 177. Nachzurechnen mit ``cli finanzierung``.
GEMESSEN: tuple[Stufe, ...] = (
    Stufe(0.0, 14.83, 9.87, 9, 11, 0.00, 7.17, 776.97,
          ("Messlatte", "Deflated Sharpe")),
    Stufe(0.00005, 14.15, 10.25, 9, 11, 31.90, 7.17, 776.97,
          ("Messlatte", "Deflated Sharpe")),
    Stufe(0.0001, 13.47, 10.64, 7, 11, 63.79, 7.17, 776.97,
          ("Messlatte", "Schlechtestes Jahr", "Deflated Sharpe",
           "Parameter-Plateau")),
    Stufe(0.0002, 12.13, 11.41, 7, 11, 127.57, 7.17, 776.97,
          ("Messlatte", "Schlechtestes Jahr", "Deflated Sharpe",
           "Parameter-Plateau")),
    Stufe(0.0003, 10.80, 12.17, 6, 11, 191.35, 7.17, 776.97,
          ("Messlatte", "Drawdown", "Schlechtestes Jahr", "Deflated Sharpe",
           "Parameter-Plateau")),
    Stufe(0.0005, 8.22, 13.68, 3, 11, 318.46, 7.17, 776.97, ()),
)


def leiter(**abweichung) -> Finanzierung:
    daten = {"stufen": list(GEMESSEN), "angenommen": BASISSATZ,
             "historie_vorhanden": False}
    daten.update(abweichung)
    return Finanzierung(**daten)


class TestGroessenordnung:
    def test_funding_ist_der_groesste_kostenblock(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Nicht "auch relevant", sondern das 8,9-fache der Gebuehren und 8,2 %
        des Bruttogewinns. Jede Sorgfalt am Gebuehrenmodell misst damit den
        kleineren Posten.
        """
        punkt = leiter().betriebspunkt

        assert punkt is not None
        assert punkt.satz == BASISSATZ
        assert punkt.vielfaches_der_gebuehren == pytest.approx(8.9, abs=0.1)
        assert punkt.anteil_am_brutto == pytest.approx(0.082, abs=0.002)
        assert leiter().groesster_kostenblock == "Funding"
        assert "groesste Kostenblock" in leiter().urteil()

    def test_der_vorgabewert_entspricht_elf_prozent_im_jahr(self) -> None:
        """Alle acht Stunden, dreimal am Tag - die Umrechnung steht im Modul,
        damit niemand sie im Kopf macht und sich um den Faktor drei irrt."""
        punkt = leiter().betriebspunkt

        assert punkt is not None
        assert PERIODEN_JE_JAHR == 1095
        assert punkt.jahr_pct == pytest.approx(10.95, abs=0.01)

    def test_ohne_gebuehren_kippt_die_verhaeltniszahl_nicht(self) -> None:
        ohne = Stufe(0.0001, 13.0, 10.0, 7, 11, funding=50.0, gebuehren=0.0)

        assert ohne.vielfaches_der_gebuehren == 0.0
        assert ohne.anteil_am_brutto == 0.0


class TestEmpfindlichkeit:
    def test_zwei_gates_haengen_am_satz(self) -> None:
        """**Was an der Annahme haengt.**

        Zwischen 5,5 % und 11 % im Jahr kippen zwei Gates. Der Vorgabewert
        liegt genau am oberen Ende dieses Sprungs.
        """
        f = leiter()

        assert f.haengt_daran
        assert f.spanne_gates == (3, 9)
        erster, zweiter = f.kipppunkte[0]
        assert erster.bestanden == 9 and zweiter.bestanden == 7
        assert zweiter.satz == BASISSATZ
        assert "haengt daran" in f.urteil()

    def test_die_gekippten_gates_sind_benannt(self) -> None:
        """Welche zwei es sind, gehoert dazu - sonst waere "zwei Gates" eine
        Zahl ohne Inhalt."""
        f = leiter()
        vorher, nachher = f.kipppunkte[0]

        neu = set(nachher.gescheitert) - set(vorher.gescheitert)
        assert neu == {"Schlechtestes Jahr", "Parameter-Plateau"}

    def test_der_drawdown_kippt_erst_spaeter(self) -> None:
        f = leiter()
        bei_33 = next(s for s in f.geordnet if s.satz == 0.0003)

        assert "Drawdown" in bei_33.gescheitert
        assert bei_33.rueckgang > 12.0

    def test_eine_unempfindliche_leiter_behauptet_nichts(self) -> None:
        """Gegenprobe: Aendert sich die Bilanz nicht, sagt das Urteil genau
        das - und nennt keine Kipppunkte."""
        starr = leiter(
            stufen=[
                Stufe(s, 13.0, 10.0, 7, 11, 10.0, 7.0, 700.0)
                for s in (0.0, 0.0001, 0.0005)
            ]
        )

        assert not starr.haengt_daran
        assert starr.kipppunkte == []
        assert "traegt hier kein Urteil" in starr.urteil()


class TestEhrlichkeit:
    def test_die_nullzeile_wird_nicht_als_hoffnung_verkauft(self) -> None:
        """**Die Falle dieses Befundes.**

        9 von 11 bei 0 % sieht nach einem Durchbruch aus. Funding entfaellt
        aber nur im Spot-Handel, und dort entfaellt auch der Hebel - die
        gemessenen Positionsgroessen kaemen gar nicht zustande.
        """
        urteil = leiter().urteil()

        assert "keine Hoffnung" in urteil
        assert "Empfindlichkeit, kein" in urteil
        assert "entfaellt auch der Hebel" in urteil
        assert "nicht auf den Wert gestellt, bei dem mehr Gates halten" in urteil

    def test_die_richtung_des_fehlers_wird_nicht_behauptet(self) -> None:
        """Dass Longs im Bullenmarkt mehr zahlen, steht im Engine-Docstring -
        gemessen ist es hier nicht, und das Urteil sagt das."""
        urteil = leiter().urteil()

        assert "nicht gemessen" in urteil
        assert "schlechter" in urteil
        assert "nur mit echten Raten" in urteil

    def test_fehlende_historie_wird_vorangestellt(self) -> None:
        """Der erste Satz des Urteils, nicht eine Fussnote: Ohne historische
        Raten ist die ganze Leiter eine Annahme."""
        assert leiter().urteil().startswith("**Der Funding-Satz ist nie gemessen")

    def test_mit_historie_faellt_der_hinweis_weg(self) -> None:
        mit = leiter(historie_vorhanden=True)

        assert "nie gemessen worden" not in mit.urteil()
        assert "groesste Kostenblock" in mit.urteil()

    def test_zu_wenige_saetze_sagen_nichts(self) -> None:
        duenn = Finanzierung(stufen=list(GEMESSEN[:2]))

        assert not duenn.genug
        assert "nichts sagen" in duenn.urteil()
        assert Finanzierung().tabelle() == "Keine Saetze gemessen."

    def test_die_tabelle_markiert_den_betriebspunkt(self) -> None:
        text = leiter().tabelle()

        assert "<- Vorgabe" in text
        assert text.count("<- Vorgabe") == 1
        assert "8.9-faches" in text
