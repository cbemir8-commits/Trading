"""Tests fuer ``research.nachmessung`` - Befund 131.

Die Suche findet **Verdachtsfaelle**, keine Befunde. Diese Tests halten genau
das fest: dass sie findet, was zu finden ist, und dass sie nichts entscheidet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.nachmessung import BEGRIFFE, Abschnitt, Spur, abschnitte, spuren
from research.stand import GESCHLOSSEN, Richtung

BEFUND = Path("strategies/BEFUND.md")

LABORBUCH = """Vorspann, der zu keinem Befund gehoert.

## Eins. Der Anfang

Hier steht Vola-Ziel einmal.

## Zwei. Die Mitte

Vola-Ziel, und noch einmal Vola-Ziel.
Dazu ein Gewinnziel.

## Drei. Das Ende

Nichts Einschlaegiges.
"""


# --- Das Laborbuch zerlegen -------------------------------------------------


def test_abschnitte_findet_die_befunde() -> None:
    teile = abschnitte(LABORBUCH)
    assert [a.nummer for a in teile] == [1, 2, 3]
    assert [a.titel for a in teile] == ["Der Anfang", "Die Mitte", "Das Ende"]


def test_abschnitte_reichen_bis_zur_naechsten_ueberschrift() -> None:
    erster, zweiter, dritter = abschnitte(LABORBUCH)
    assert erster.bis == zweiter.von - 1
    assert zweiter.bis == dritter.von - 1
    assert dritter.bis == len(LABORBUCH.splitlines()) - 1


def test_vorspann_gehoert_zu_keinem_abschnitt() -> None:
    erster = abschnitte(LABORBUCH)[0]
    assert erster.von > 0
    assert not erster.enthaelt(0)


def test_abschnitte_uebergeht_ueberschriften_ohne_zahlwort() -> None:
    text = "## Vorwort. Kein Zahlwort\n\n## Eins. Doch eines\n"
    assert [a.nummer for a in abschnitte(text)] == [1]


def test_leeres_laborbuch_gibt_nichts_zurueck() -> None:
    assert abschnitte("") == ()


def test_abschnitt_der_vor_seinem_anfang_endet_wird_abgewiesen() -> None:
    with pytest.raises(ValueError, match="endet vor seinem Anfang"):
        Abschnitt(1, "Kaputt", von=10, bis=3)


# --- Die Spuren -------------------------------------------------------------


def test_spuren_zaehlen_treffer_je_befund() -> None:
    gefunden, ohne = spuren(
        LABORBUCH,
        (Richtung("Vola-Ziel", "geschlossen", 1),),
        {"Vola-Ziel": ("Vola-Ziel",)},
    )
    assert ohne == ()
    assert gefunden[0].spaeter == ((2, 1),), "eine Zeile mit zwei Treffern zaehlt einmal"


def test_spuren_uebergehen_was_vor_der_fundstelle_liegt() -> None:
    gefunden, _ = spuren(
        LABORBUCH,
        (Richtung("Vola-Ziel", "geschlossen", 2),),
        {"Vola-Ziel": ("Vola-Ziel",)},
    )
    assert gefunden[0].spaeter == ()


def test_offen_zaehlt_nur_was_nach_der_nachmessung_kommt() -> None:
    s = Spur("Etwas", fundstelle=21, massgeblich=23, spaeter=((22, 3), (24, 1)))
    assert s.offen == ((24, 1),)
    assert s.nachgezogen


def test_ohne_nachmessung_ist_alles_offen() -> None:
    s = Spur("Etwas", fundstelle=21, massgeblich=21, spaeter=((22, 3), (24, 1)))
    assert s.offen == ((22, 3), (24, 1))
    assert not s.nachgezogen


def test_urteil_ohne_spur_sagt_das() -> None:
    s = Spur("Etwas", fundstelle=21, massgeblich=23)
    assert "keine Erwaehnung nach Befund 23" in s.urteil()


def test_urteil_mit_spur_bleibt_ein_verdacht() -> None:
    s = Spur("Etwas", fundstelle=21, massgeblich=21, spaeter=((24, 2),))
    text = s.urteil()
    assert "24 (2x)" in text
    assert "nicht zu glauben" in text


def test_richtung_ohne_begriffe_wird_gemeldet_statt_uebergangen() -> None:
    """Eine sichtbare Luecke ist besser als ein stiller Fehlalarm (Befund 118)."""
    gefunden, ohne = spuren(
        LABORBUCH, (Richtung("Etwas Unbekanntes", "geschlossen", 1),), {}
    )
    assert gefunden == ()
    assert ohne == ("Etwas Unbekanntes",)


def test_spuren_ordnen_nach_trefferzahl() -> None:
    text = (
        "## Eins. Start\n\nX\n"
        "## Zwei. Wenig\n\nTreffer\n"
        "## Drei. Viel\n\nTreffer\nTreffer\nTreffer\n"
    )
    gefunden, _ = spuren(
        text, (Richtung("X", "geschlossen", 1),), {"X": ("Treffer",)}
    )
    assert gefunden[0].spaeter == ((3, 3), (2, 1))


# --- Gegen das echte Laborbuch ----------------------------------------------


@pytest.fixture(scope="module")
def laborbuch() -> str:
    return BEFUND.read_text(encoding="utf-8")


def test_jede_geschlossene_richtung_hat_suchbegriffe(laborbuch: str) -> None:
    """Ohne Begriffe sieht die Suche gar nicht hin - das darf nicht still bleiben."""
    _, ohne = spuren(laborbuch, GESCHLOSSEN)
    assert ohne == (), f"ohne Suchbegriffe: {ohne}"


def test_begriffe_nennen_keine_richtung_die_es_nicht_gibt() -> None:
    namen = {r.name for r in GESCHLOSSEN}
    verwaist = set(BEGRIFFE) - namen
    assert not verwaist, f"Begriffe ohne Richtung: {sorted(verwaist)}"


def test_die_falle_aus_befund_130_wird_gefunden(laborbuch: str) -> None:
    """Befund 23 hat den Vola-Ziel-Regler nach Befund 21 neu vermessen.

    Waere ``zuletzt`` nicht gesetzt, muesste die Suche Befund 23 melden - genau
    den Hinweis, der zweimal gefehlt hat.
    """
    gefunden, _ = spuren(laborbuch, (Richtung("Vola-Ziel", "geschlossen", 21),))
    assert 23 in [n for n, _ in gefunden[0].offen]


def test_nachgezogene_eintraege_melden_die_alten_stellen_nicht_mehr(
    laborbuch: str,
) -> None:
    gefunden, _ = spuren(laborbuch, GESCHLOSSEN)
    vola = next(s for s in gefunden if s.name == "Vola-Ziel")
    assert vola.massgeblich == 129
    assert 23 not in [n for n, _ in vola.offen]


def test_die_nachgemessenen_eintraege_stehen_fest() -> None:
    """Elf von 36 tragen eine Nachmessung - der Rest ist **ungeprueft**.

    Die Liste steht ausgeschrieben da, damit jede weitere Nachmessung eine
    bewusste Entscheidung ist und nicht nebenbei passiert. Wer hier eine Zeile
    hinzufuegt, hat gemessen; wer sie hinzufuegt, ohne gemessen zu haben,
    verwischt genau den Unterschied, den Befund 131 festhalten wollte.
    """
    nachgezogen = {r.name: r.zuletzt for r in GESCHLOSSEN if r.zuletzt}
    assert nachgezogen == {
        "Mehr Maerkte": 133,
        "Mehr Historie": 132,
        "Vola-Ziel": 129,
        "Gewinnziel": 129,
        "Termin-Overlay": 127,
        "Perioden-Faktor": 49,
        "Schiefe erhoehen": 125,
        # Befund 168 hat die Kopplung zu Ende gerechnet (Decke 1,931 gegen
        # noetige 3,522), Befund 169 sie auf die SMA-Familie eingeschraenkt.
        "Trade-Zahl heben": 169,
        "Kostenannahmen": 127,
        "Schnittpunkt als Prognose": 126,
        # Befund 141: 14 Paare mit dem Bestand, an der Einteilung des Gates.
        # Befund 151: dieselben 14 noch einmal, mit verlaengertem Nachlauf -
        # bestes Paar 3,030 gegen eine Latte von 3,644, weiter 0 von 14.
        "Verbund aus dem Katalog": 151,
        # Befund 145: dieselben 14 Genome, am Spot-Punkt und mit der
        # Zerlegung in brutto und netto.
        # Befund 171 hat 36 statt 14 Regeln gemessen, netto, auf neu
        # geholten Bitstamp-Kerzen.
        "15-Minuten-Kerzen": 171,
    }


def test_jede_massgebliche_fundstelle_gibt_es_im_laborbuch(laborbuch: str) -> None:
    vorhanden = {a.nummer for a in abschnitte(laborbuch)}
    fehlend = [r.name for r in GESCHLOSSEN if r.massgeblich not in vorhanden]
    assert not fehlend, f"Fundstelle zeigt ins Leere: {fehlend}"
