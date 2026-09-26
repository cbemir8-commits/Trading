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
    """Seit Befund 294 auch ueber die offenen Richtungen.

    Der Zweck bleibt - ein Begriff ohne Richtung sucht ins Leere -, nur der
    Umfang ist gewachsen: ``cli register`` laeuft jetzt ueber beide Register.
    """
    from research.stand import OFFEN

    namen = {r.name for r in (*GESCHLOSSEN, *OFFEN)}
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
        # Befund 344 hat beziffert, was "mehr Historie" waere: 104 rohe
        # Trades, also sechs Jahre - und rueckwaerts gesperrt, weil ETH
        # den gemeinsamen Anfang setzt.
        "Mehr Historie": 344,
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
        # Befund 188: dieselben 36 auf dem nach 182/184 berichtigten Vorrat -
        # die Kopplung ist dort jetzt zu sehen (t = -2,19 statt -0,26), und
        # der negative Achsenabschnitt macht die Aussage haerter.
        "15-Minuten-Kerzen": 188,
        # Befund 191: dieselben 18 Regeln mit ihren **eigenen** Momenten
        # statt denen des Bestands. Die beste raeumt bis 8 statt 10
        # Versuche; der Schluss aus 189 wird davon fester.
        # Befund 194: der Verbundweg dazu - bestes Paar bis 137 gegen einen
        # Zaehler von 198. Dort war der Stand entscheidend, anders als im
        # Katalog; geschlossen bleibt die Richtung durch den Holdout (186).
        "Suchdisziplin als Weg": 194,
        # Befund 272 hat die Preisrueckblick-Familie gemessen und die anderen
        # ausdruecklich offengelassen. Befund 274 hat zwei davon nachgeholt -
        # Volumen und Spanne -, mit einer Schwelle ueber alle drei Familien
        # zusammen. Kein Treffer.
        # Befund 276: die vierte und letzte mit diesen Daten messbare Familie,
        # die Marktbreite ueber die drei uebrigen Forschungsmaerkte. Sie bringt
        # als erste eine Zelle ueber die Schwelle (-3,74 gegen 3,62) und
        # verliert sie an der Verschiebungsprobe - 2 von 584. Nachgemessen,
        # nicht nur erwaehnt.
        "Einstiegsseite": 276,
        # Befund 255 hat es auf Viertelstunden gemessen (-0,267 auf -0,186),
        # Befund 297 hat die Richtung mit dem **gerechneten** Kippfaktor
        # wieder aufgemacht, obwohl 256 im selben Eintrag steht und sagt,
        # dass der keine Messung ist. Befund 302 hat sie auf einem zweiten,
        # unabhaengig gebauten Weg wiederholt und ist bei denselben Zahlen
        # herausgekommen - Bestaetigung, und 106 Minuten fuer etwas, das
        # schon dastand.
        "Traegt die Reibung die Kopplung auf kurzen Kerzen?": 302,
    }


def test_jede_massgebliche_fundstelle_gibt_es_im_laborbuch(laborbuch: str) -> None:
    vorhanden = {a.nummer for a in abschnitte(laborbuch)}
    fehlend = [r.name for r in GESCHLOSSEN if r.massgeblich not in vorhanden]
    assert not fehlend, f"Fundstelle zeigt ins Leere: {fehlend}"


class TestDieSucheSiehtAuchDieOffenenAn:
    """**Befund 294.** ``BEGRIFFE`` deckte genau die 39 geschlossenen
    Richtungen ab, und ``cli register`` lief nur ueber ``GESCHLOSSEN``.

    Das war keine Fehlfunktion - ``spuren`` meldet seit jeher, wo es keine
    Begriffe gibt. Gefragt hat nur niemand: Von 208 Registereintraegen hat
    die Suche 39 angesehen, und ausgerechnet die **offenen** Richtungen, nach
    denen gearbeitet wird, waren nicht dabei.
    """

    def test_jede_offene_richtung_hat_suchbegriffe(self) -> None:
        """**Die Wache.** Eine neue offene Richtung ohne Begriffe laesst die
        Luecke still zurueckkehren."""
        from research.nachmessung import BEGRIFFE
        from research.stand import OFFEN

        fehlend = [r.name for r in OFFEN if r.name not in BEGRIFFE]

        assert fehlend == [], f"offene Richtungen ohne Suchbegriffe: {fehlend}"

    def test_und_jede_geschlossene_weiterhin_auch(self) -> None:
        from research.nachmessung import BEGRIFFE
        from research.stand import GESCHLOSSEN

        fehlend = [r.name for r in GESCHLOSSEN if r.name not in BEGRIFFE]

        assert fehlend == []

    def test_die_namen_kollidieren_nicht(self) -> None:
        """``BEGRIFFE`` schlaegt ueber den Namen nach - zwei Richtungen mit
        demselben Namen bekaemen stillschweigend dieselben Begriffe."""
        from research.stand import GESCHLOSSEN, OFFEN

        geschlossen = {r.name for r in GESCHLOSSEN}
        offen = {r.name for r in OFFEN}

        assert geschlossen & offen == set()

    def test_die_offenen_werden_wirklich_durchsucht(self) -> None:
        """Nicht nur Begriffe hinterlegt, sondern auch Treffer - sonst waere
        die Erweiterung eine Liste ohne Wirkung."""
        from pathlib import Path

        from research.nachmessung import spuren
        from research.stand import OFFEN

        text = Path("strategies/BEFUND.md").read_text(encoding="utf-8")
        gefunden, ohne = spuren(text, OFFEN)

        assert ohne == ()
        assert len(gefunden) == len(OFFEN)
        assert any(s.offen for s in gefunden), (
            "keine einzige offene Richtung wird spaeter erwaehnt - das waere "
            "bei sechzehn Eintraegen ueber hundert Befunde unwahrscheinlich"
        )

    def test_die_begriffe_fluten_nicht(self) -> None:
        """Eine Trefferliste, die zu lang ist, wird nicht gelesen - und eine
        ungelesene Trefferliste ist der Zustand, aus dem Befund 130 kam."""
        from pathlib import Path

        from research.nachmessung import spuren
        from research.stand import OFFEN

        text = Path("strategies/BEFUND.md").read_text(encoding="utf-8")
        gefunden, _ = spuren(text, OFFEN)

        for s in gefunden:
            assert len(s.offen) <= 25, f"{s.name}: {len(s.offen)} Abschnitte"


class TestDieSucheHatJetztEinGedaechtnis:
    """**Befund 295.** Die Suche meldete bei jedem Lauf dieselben Eintraege.

    Wer sie zweimal liest, hat zweimal gearbeitet; wer sie gar nicht liest,
    merkt es nicht. ``GELESEN`` haelt fest, bis zu welchem Befund die
    Erwaehnungen einer Richtung nachgeschlagen **und entschieden** sind.
    """

    def test_neu_ist_enger_als_offen(self) -> None:
        from research.nachmessung import Spur

        s = Spur("X", 10, 20, ((30, 1), (40, 2), (15, 1)), gelesen=35)

        assert {n for n, _ in s.offen} == {30, 40}
        assert {n for n, _ in s.neu} == {40}

    def test_ohne_eintrag_ist_nichts_gelesen(self) -> None:
        from research.nachmessung import Spur

        s = Spur("X", 10, 20, ((30, 1), (40, 2)))

        assert s.neu == s.offen
        assert not s.durchgesehen

    def test_durchgesehen_heisst_alles_gelesen(self) -> None:
        from research.nachmessung import Spur

        s = Spur("X", 10, 20, ((30, 1), (40, 2)), gelesen=40)

        assert s.neu == ()
        assert s.durchgesehen

    def test_ohne_erwaehnungen_ist_nichts_durchzusehen(self) -> None:
        """"Durchgesehen" soll Arbeit bedeuten, nicht Abwesenheit von
        Arbeit - sonst zaehlt der Bericht Ruhe als Leistung."""
        from research.nachmessung import Spur

        s = Spur("X", 10, 20, (), gelesen=99)

        assert not s.durchgesehen

    def test_gelesen_nennt_nur_richtungen_die_es_gibt(self) -> None:
        from research.nachmessung import GELESEN
        from research.stand import GESCHLOSSEN, OFFEN

        namen = {r.name for r in (*GESCHLOSSEN, *OFFEN)}
        verwaist = set(GELESEN) - namen

        assert not verwaist, f"gelesen ohne Richtung: {sorted(verwaist)}"

    def test_die_sieben_aus_294_sind_entschieden(self) -> None:
        """Der Zweck des Eintrags: Sie tauchen nicht wieder als neu auf."""
        from pathlib import Path

        from research.nachmessung import GELESEN, spuren
        from research.stand import OFFEN

        text = Path("strategies/BEFUND.md").read_text(encoding="utf-8")
        gefunden, _ = spuren(text, OFFEN)
        durch = {s.name for s in gefunden if s.durchgesehen}

        assert durch == set(GELESEN) & {s.name for s in gefunden}
        assert len(durch) == 7

    def test_drei_davon_wurden_nachgezogen(self) -> None:
        """Gelesen heisst nicht abgehakt: Drei der sieben waren wirkliche
        Nachmessungen und haben die massgebliche Fundstelle bewegt."""
        from research.stand import OFFEN

        nach = {r.name: r.massgeblich for r in OFFEN}

        assert nach["Zaehlt ein Sweep am Bestand als Versuch?"] == 282
        assert nach["Der Preis in Reststreuungen"] == 290
        assert nach["Einstieg, der nicht am Rauschen haengt"] == 283
