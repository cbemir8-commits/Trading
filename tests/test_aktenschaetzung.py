"""Die Ideenstreuung war zu raten, obwohl sie in der Akte steht - Befund 391.

Befund 390 hat die Grundlage des Wettrennens berichtigt und daraus geschlossen,
die Suche hole **nie** auf. Diese Zahl ist aus **einem** Wert zurueckgerechnet:
dem besten Fund nach 203 Versuchen.

Dabei steht in ``state/trials.json`` seit Befund 377 jeder gemeldete Versuch mit
Guete und Trade-Zahl - und der Docstring von ``Versuch`` sagt seit jeher, wofuer:

    ``sharpe_je_trade`` ist die Groesse, um die es geht: Aus ihr liesse sich die
    Streuung ueber die Versuche messen, statt sie zu raten.

Gelesen hat sie niemand. ``Verzeichnis.sharpes()`` hatte genau einen Nutzer, und
der zaehlt sie nur.

Gemessen, mit Abzug des Schaetzrauschens:

    acht neue Regelideen      Ideenstreuung 0,1669   Mittel +0,0324
    alle elf Eintraege        Ideenstreuung 0,1746   Mittel +0,0988
    aus dem Bestwert (390)    Ideenstreuung 0,0906
    Nullstreuung                            0,0913

**Das ist das Doppelte und kehrt das Vorzeichen um.** Versoehnt sind die beiden
Schaetzer bei rund sieben unabhaengigen Ideenziehungen - die Akte verzeichnet
elf, der Zaehler steht bei 203.
"""

from __future__ import annotations

import inspect
import json
import pathlib

import pytest

from research.wettrennen import Aktenschaetzung, aus_der_akte, extremwert, nullstreuung

#: Gemessen, siehe Kopf.
IDEEN = 0.1669
ALLE = 0.1746
RUECKRECHNUNG = 0.0906
NULL = 0.0913
VERSOEHNT = 7


def _punkte(*, nur_ideen: bool) -> list[tuple[float, int]]:
    """Die verzeichneten Versuche aus der Akte - ``daten``-frei.

    ``state/trials.json`` ist die **eine** Datei unter ``state/``, die im Git
    liegt (Befund 73). Sie zu lesen braucht keinen Kerzenspeicher.
    """
    d = json.loads(pathlib.Path("state/trials.json").read_text())
    return [
        (v["sharpe_je_trade"], v["trades"])
        for v in d["versuche"]
        if v["sharpe_je_trade"] is not None
        and v["trades"] > 0
        and not (nur_ideen and v["herkunft"] == "verbund")
    ]


class TestDieSchaetzungAusDerAkte:
    def test_acht_neue_regelideen(self) -> None:
        s = aus_der_akte(_punkte(nur_ideen=True))

        assert s is not None
        assert s.anzahl == 8
        assert s.mittel == pytest.approx(0.0324, abs=0.0005)
        assert s.streuung == pytest.approx(IDEEN, abs=0.0005)

    def test_alle_elf_mit_den_verbunden(self) -> None:
        """Drei Eintraege sind Kombinationen **mit dem Bestand**; ihre Guete
        ist zum grossen Teil die seine. Das hebt das Mittel von +0,0324 auf
        +0,0988 - deshalb steht die Abgrenzung im Befehl und nicht im Kopf."""
        s = aus_der_akte(_punkte(nur_ideen=False))

        assert s.anzahl == 11
        assert s.mittel == pytest.approx(0.0988, abs=0.0005)
        assert s.streuung == pytest.approx(ALLE, abs=0.0005)

    def test_das_rauschen_wird_wirklich_abgezogen(self) -> None:
        """Ohne Abzug stuende die beobachtete Streuung da - 0,2059 statt
        0,1669, also ein Viertel zu gross."""
        s = aus_der_akte(_punkte(nur_ideen=True))

        assert s.beobachtet == pytest.approx(0.2059, abs=0.0005)
        assert s.beobachtet > s.streuung
        assert s.rauschen == pytest.approx(0.0145, abs=0.0005)

    def test_wirksame_trades_sind_die_zweite_lesart(self) -> None:
        """Die Akte verzeichnet **rohe** Trade-Zahlen. Weniger wirksame
        Beobachtungen heissen mehr Rauschen und damit eine kleinere
        Ideenstreuung - die sparsamere Lesart."""
        roh = aus_der_akte(_punkte(nur_ideen=True))
        wirksam = aus_der_akte(_punkte(nur_ideen=True), wirksamer_anteil=0.74)

        assert wirksam.rauschen > roh.rauschen
        assert wirksam.streuung < roh.streuung
        assert wirksam.streuung == pytest.approx(0.1509, abs=0.0005)


class TestDasVorzeichenKehrtSichUm:
    def test_die_akte_liegt_ueber_der_null_die_rueckrechnung_darunter(self) -> None:
        akte = aus_der_akte(_punkte(nur_ideen=True))

        assert akte.streuung > NULL
        assert RUECKRECHNUNG < NULL

    def test_dreihundert_ziehungen_haetten_mehr_hergeben_muessen(self) -> None:
        """Der eigentliche Widerspruch: Mit der gemessenen Streuung waere der
        beste Fund nach 203 Ziehungen doppelt so gut wie der beobachtete."""
        akte = aus_der_akte(_punkte(nur_ideen=True))
        erwartet = akte.mittel + akte.streuung * extremwert(203)

        assert erwartet == pytest.approx(0.4949, abs=0.002)
        assert erwartet > 2 * 0.2509 * 0.9

    def test_versoehnt_bei_sieben_ziehungen(self) -> None:
        akte = aus_der_akte(_punkte(nur_ideen=True))

        assert akte.versoehnt_bei(0.2509) == VERSOEHNT

    def test_und_die_akte_verzeichnet_elf(self) -> None:
        """Sieben gegen elf verzeichnete gegen 203 gezaehlte - der Zaehler
        zaehlt geprufte Hypothesen, nicht Ideenziehungen."""
        assert len(_punkte(nur_ideen=False)) == 11


class TestDieRandfaelle:
    def test_ein_einzelner_punkt_gibt_keine_streuung(self) -> None:
        assert aus_der_akte([(0.2, 100)]) is None

    def test_und_keiner_auch_nicht(self) -> None:
        assert aus_der_akte([]) is None

    def test_trades_null_fliegt_heraus(self) -> None:
        """Sonst teilt das Rauschen durch Null."""
        s = aus_der_akte([(0.2, 100), (0.1, 0), (0.3, 120)])

        assert s is not None
        assert s.anzahl == 2

    def test_nicht_nachweisbar_ist_etwas_anderes_als_null(self) -> None:
        """Die drei Verbunde: Ihre beobachtete Streuung ist kleiner als das
        Schaetzrauschen, also bleibt nichts uebrig. ``None`` heisst hier
        'nicht nachweisbar' und nicht 'keine Streuung' - dieselbe
        Unterscheidung wie bei ``Budgetgrenze.gedeckelt``."""
        verbunde = [
            p for p in _punkte(nur_ideen=False)
            if p not in _punkte(nur_ideen=True)
        ]
        s = aus_der_akte(verbunde)

        assert s is not None
        assert s.anzahl == 3
        assert s.streuung is None
        assert s.beobachtet > 0, "beobachtet wird etwas, nachweisbar nicht"

    def test_ohne_streuung_gibt_es_keine_versoehnung(self) -> None:
        s = Aktenschaetzung(
            anzahl=3, mittel=0.1, beobachtet=0.02, rauschen=0.01,
            streuung=None, hoechster=0.12,
        )

        assert s.versoehnt_bei(0.25) is None

    def test_ein_bestwert_unter_dem_mittel_auch_nicht(self) -> None:
        s = aus_der_akte(_punkte(nur_ideen=True))

        assert s.versoehnt_bei(s.mittel - 0.01) is None


class TestDerBefehlStelltBeideNebeneinander:
    """Die Lehre aus Befund 351 - zum vierten Mal in dieser Reihe."""

    def test_rennen_ruft_die_aktenschaetzung(self) -> None:
        import cli

        quelle = inspect.getsource(cli.rennen)

        assert "aus_der_akte(ideen)" in quelle
        assert "versoehnt_bei(" in quelle

    def test_und_nennt_beide_bevoelkerungen(self) -> None:
        import cli

        quelle = inspect.getsource(cli.rennen)

        assert "neue Regelideen" in quelle
        assert "Verbunden am Bestand" in quelle

    def test_der_anteil_wird_gerechnet_nicht_gepflegt(self) -> None:
        """74 % hinzuschreiben waere eine gepflegte Zahl; sie steht im
        Referenzpunkt und wird daraus gerechnet."""
        import cli

        quelle = inspect.getsource(cli.rennen)

        assert "SPOTPUNKT.effektiv / SPOTPUNKT.trades" in quelle
        assert "0.74" not in quelle

    def test_und_das_nie_aus_390_wird_eingeordnet(self) -> None:
        """Nicht geloescht, sondern eingeordnet.

        Hier stand *"Das 'nie' aus Befund 390 haengt an der ersten Annahme und
        ist damit kein Schlusswort"* - und der Test hat das mit einem ``or``
        geprueft, also fast nichts. Befund 392 hat die dritte Schaetzung
        gemessen und damit entschieden, welche Lesart gilt; der Satz verweist
        jetzt dorthin, und der Test prueft ihn.
        """
        import cli

        quelle = inspect.getsource(cli.rennen)

        assert "entscheidet eine dritte Schaetzung" in quelle
        assert "192 stehen ohne Herkunft im Grundstock" in quelle


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_beide_schaetzer(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 391)

        for zahl in ("0,1669", "0,0906", "0,0913", "0,4949", "sieben"):
            assert zahl in eintrag.ergebnis, zahl

    def test_und_nennt_beide_lesarten_als_ungemessen(self) -> None:
        """Der Kern der Ehrlichkeit hier: Die Aufloesung ist **nicht**
        gemessen, nur der Widerspruch."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 391)

        assert "Keines von beidem ist gemessen" in eintrag.ergebnis
        assert "kein Schlusswort" in eintrag.ergebnis

    def test_und_390_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        vorher = next(r for r in BEHOBEN if r.befund == 390)

        assert vorher.zuletzt == 391

    def test_das_budget_nennt_den_widerspruch(self) -> None:
        from research.stand import Suchbudget

        text = Suchbudget.__doc__ or ""

        assert "0,1669" in text
        assert "0,0589" in text
        assert "Dreimal geschaetzt" in text, (
            "hier stand 'haelt nicht' - die Fassung aus 391, die das 'gar "
            "nicht' aus 390 zurueckgenommen hat. Seit 392 steht die "
            "Dreierzahl da statt einer davon."
        )
        assert "ausgesuchte Menge" in text

    def test_der_statusschirm_nennt_ihn_auch(self) -> None:
        """Dreimal umgeschrieben, und jedes Mal aus einem Grund.

        Nach 390 stand dort 'er zieht nicht langsam nach, sondern nicht' - als
        Ergebnis. Nach 391 'ist strittig', weil die zweite Schaetzung das
        Gegenteil sagte. Nach 392 steht die Dreierzahl da, denn die dritte
        Schaetzung entscheidet es.
        """
        from research.stand import Lage

        quelle = inspect.getsource(Lage)

        assert "0,0589" in quelle
        assert "ist strittig" not in quelle
        # Nach 393 steht dort nicht mehr "nicht bei 203": Diese Zahl war ein
        # Kategorienfehler, und an ihrer Stelle steht jetzt, **warum** der
        # Bestand der Kandidat ist.
        assert "warum er der Kandidat ist" in quelle


class TestDieAkteBleibtLesbar:
    def test_sharpes_hat_jetzt_mehr_als_einen_nutzer(self) -> None:
        """Nicht die Funktion selbst - die Werte. Vorher las sie niemand
        ausser ``belegt``, das sie zaehlt."""
        from research.versuche import Verzeichnis

        assert hasattr(Verzeichnis, "sharpes")

    def test_der_docstring_von_versuch_sagt_wofuer(self) -> None:
        """Der Satz, der diesen Befund ausgeloest hat - er stand die ganze
        Zeit da."""
        from research.versuche import Versuch

        text = Versuch.__doc__ or ""

        assert "statt sie zu raten" in text
        assert "Streuung ueber die Versuche messen" in text


def test_die_nullstreuung_ist_die_des_schaetzers() -> None:
    """Der Massstab, gegen den beide Schaetzer stehen: 1/sqrt(n-1) bei n_eff
    121 auf der Zulassungsreihe."""
    assert nullstreuung(121) == pytest.approx(NULL, abs=0.0002)
