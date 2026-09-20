"""Das Vorwissen kannte nur eine der beiden Quellen - Befund 319.

Befund 302 hat 106 Minuten gekostet, weil die Antwort im **Register** stand
und niemand nachgesehen hat. Die Lehre war ``research/vorwissen.py``.

Befund 318 hat dieselbe Sorte Lauf wiederholt, nur stand die Antwort diesmal
im **Berichtsordner**:

    reports/marktkombinationen/2026-09-13_010559.json
    BTC   117 Trades   DSR 0,4620   5/11

Das Register sagte zu der Frage nichts - und genau dann war ``vorwissen`` zu
Ende. Der Ablauf des Projekts nennt beide Quellen ausdruecklich ("Was ist der
Stand? state/leaderboard.json, **reports/**, letzter Commit"); abgefragt war
nur die eine.

Die Tests hier halten dreierlei fest:

* Die Lage wird aus dem Ordner gelesen und nicht aus einer zweiten Liste.
* Der Block erscheint **auch**, wenn das Register schweigt - das war der
  Fall, in dem er gefehlt hat.
* Die Begriffe von Befund 318 finden den Bericht, der damals gereicht haette.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.berichtslage import Berichtsart, auskunft, berichtslage


@pytest.fixture
def ordner(tmp_path: Path) -> Path:
    """Ein Berichtsordner, wie ``cli.py`` ihn anlegt."""
    wurzel = tmp_path / "reports"
    (wurzel / "marktkombinationen").mkdir(parents=True)
    (wurzel / "machbarkeit").mkdir()
    (wurzel / "reibung").mkdir()
    (wurzel / "leer").mkdir()

    for name, inhalt in (
        ("2026-09-01_010101.json", {"urteil": "aelterer Satz"}),
        (
            "2026-09-13_010559.json",
            {"urteil": "Am weitesten kommt 'BTC+ETH' mit 9 von 11."},
        ),
    ):
        (wurzel / "marktkombinationen" / name).write_text(json.dumps(inhalt))

    (wurzel / "machbarkeit" / "2026-09-14_005951.json").write_text(
        json.dumps({"urteil": "Ausser Reichweite des Reglers"})
    )
    # Ein Protokoll aus Befund 299: Kopfzeile, dann Messzeilen, kein Urteil.
    (wurzel / "reibung" / "2026-09-19_063518.jsonl").write_text(
        '{"art": "reibung", "begonnen": "2026-09-19"}\n{"stueck": 1}\n'
    )
    return wurzel


class TestDieLageWirdGelesen:
    def test_jede_art_mit_anzahl_und_neuestem(self, ordner: Path) -> None:
        nach_art = {a.art: a for a in berichtslage(ordner)}

        assert nach_art["marktkombinationen"].anzahl == 2
        assert nach_art["marktkombinationen"].neuester == "2026-09-13_010559"
        assert nach_art["machbarkeit"].anzahl == 1

    def test_leere_ordner_zaehlen_nicht_mit(self, ordner: Path) -> None:
        """Ein Ordner ohne Bericht ist kein Vorwissen."""
        assert "leer" not in {a.art for a in berichtslage(ordner)}

    def test_das_urteil_kommt_aus_dem_neuesten(self, ordner: Path) -> None:
        """Der aeltere Satz waere der Stand von vorgestern."""
        markt = next(
            a for a in berichtslage(ordner) if a.art == "marktkombinationen"
        )

        assert "BTC+ETH" in markt.urteil
        assert "aelterer Satz" not in markt.urteil

    def test_ein_protokoll_ohne_urteil_faellt_nicht_weg(self, ordner: Path) -> None:
        """Die Protokolle aus Befund 299 tragen einen Kopf, aber keinen Satz -
        dass es sie gibt, ist trotzdem die Auskunft."""
        reibung = next(a for a in berichtslage(ordner) if a.art == "reibung")

        assert reibung.anzahl == 1
        assert reibung.urteil == ""

    def test_ohne_ordner_keine_aussage(self, tmp_path: Path) -> None:
        assert berichtslage(tmp_path / "gibtsnicht") == ()

    def test_eine_kaputte_datei_bricht_nichts_ab(self, ordner: Path) -> None:
        """Ein unlesbarer Bericht ist ein Grund hinzusehen und keiner, den
        Befehl abzubrechen, der ihn nur nebenbei liest."""
        (ordner / "machbarkeit" / "2026-09-20_000000.json").write_text("{kaputt")

        lage = {a.art: a for a in berichtslage(ordner)}

        assert lage["machbarkeit"].anzahl == 2
        assert lage["machbarkeit"].urteil == ""


class TestDieAuskunft:
    def test_die_begriffe_aus_318_finden_den_bericht(self, ordner: Path) -> None:
        """**Der Kern.** Mit genau diesen Stichworten habe ich in Befund 318
        gemessen, statt die Datei aufzuschlagen."""
        text = auskunft("Historie", "Bein", "Markt", wurzel=ordner)

        assert "marktkombinationen" in text
        assert "BTC+ETH" in text
        assert "beruehrt diese Frage" in text

    def test_ohne_treffer_steht_die_liste_trotzdem_da(self, ordner: Path) -> None:
        """Dass kein Begriff anschlaegt, heisst nicht, dass kein Bericht die
        Antwort traegt - dieselbe Regel wie in ``nachmessung``."""
        text = auskunft("Zwiebelsuppe", wurzel=ordner)

        assert "marktkombinationen" in text
        assert "das heisst nicht" in text

    def test_ein_urteil_steht_nur_bei_einem_treffer(self, ordner: Path) -> None:
        """Sieben Urteile vor jedem Lauf liest niemand."""
        text = auskunft("Zwiebelsuppe", wurzel=ordner)

        assert "BTC+ETH" not in text

    def test_ohne_berichte_ist_der_block_leer(self, tmp_path: Path) -> None:
        assert auskunft("Markt", wurzel=tmp_path / "gibtsnicht") == ""

    def test_lange_urteile_werden_gekuerzt(self, ordner: Path) -> None:
        (ordner / "machbarkeit" / "2026-09-21_000000.json").write_text(
            json.dumps({"urteil": "x" * 400})
        )
        text = auskunft("machbarkeit", wurzel=ordner)

        assert "..." in text
        assert "x" * 400 not in text


class TestDasVorwissenNenntBeideQuellen:
    """**Die Stelle, an der 318 passiert ist.**

    ``vorwissen.auskunft`` hatte einen fruehen Ausgang: kein Registertreffer,
    ein Satz, fertig. Genau dann ist der Berichtsordner die einzige Quelle,
    die noch etwas sagen koennte.
    """

    def test_der_block_erscheint_auch_ohne_registertreffer(self) -> None:
        from research.vorwissen import auskunft as vorwissen

        text = vorwissen("Zwiebelsuppe")

        assert "Register sagt zu diesen Stichworten nichts" in text
        assert "Berichtsordner" in text

    def test_und_ebenso_mit_registertreffern(self) -> None:
        from research.vorwissen import auskunft as vorwissen

        text = vorwissen("Kopplung")

        assert "was das Register dazu schon sagt" in text
        assert "Berichtsordner" in text

    def test_die_verdrahtung_liegt_an_einer_stelle(self) -> None:
        """Zwei Wege, denselben Block anzuhaengen, laufen auseinander."""
        import inspect

        from research import vorwissen

        quelle = inspect.getsource(vorwissen)

        assert quelle.count("_mit_berichten(") == 3, "einmal gebaut, zweimal gerufen"


class TestDerBerichtsartSelbst:
    def test_passt_zu_sieht_name_und_urteil_an(self) -> None:
        art = Berichtsart(
            art="marktkombinationen", anzahl=1, neuester="x",
            urteil="Am weitesten kommt 'BTC+ETH'",
        )

        assert art.passt_zu(("markt",)), "Name, Gross- und Kleinschreibung egal"
        assert art.passt_zu(("btc+eth",)), "auch das Urteil zaehlt"
        assert not art.passt_zu(("Zwiebelsuppe",))

    def test_leere_begriffe_treffen_nichts(self) -> None:
        """Sonst passte jede Art zu jedem Lauf, und die Auskunft waere
        wertlos."""
        art = Berichtsart(art="machbarkeit", anzahl=1, neuester="x", urteil="y")

        assert not art.passt_zu(("",))
        assert not art.passt_zu(())

    def test_die_kopfzeile_beugt_das_zahlwort(self) -> None:
        eins = Berichtsart(art="a", anzahl=1, neuester="x")
        viele = Berichtsart(art="a", anzahl=4, neuester="x")

        assert "1 Bericht," in eins.kopfzeile()
        assert "4 Berichte," in viele.kopfzeile()
