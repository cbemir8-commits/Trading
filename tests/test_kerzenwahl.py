"""Wohin die verbleibenden Versuche gehoeren - 1,25 gegen 31. Befund 489.

Die dritte Zeile der offenen Punkte lautet seit langem: *"Der Nutzer braucht
auf seinem PC: ``cli backfill --intervall 15 --von 2020-03-30``, dann ``cli
wettbewerb``."* Die Vorgabe-Generation von ``cli wettbewerb`` ist **8**, und
die liegt auf Viertelstunden (``seeds.VORGESEHEN``). Dieser Weg richtet die
27 verbleibenden Versuche also auf die feinen Kerzen.

Gemessen gehoeren sie auf die Tageskerzen.

Was gemessen ist
----------------
``cli suchbudget`` auf dem Katalog von heute, 203 Versuche, beide Reihen der
Referenzdaten - der Befehl kostet ausdruecklich **keinen** Versuch:

    Betriebspunkt   bester Kandidat                Trades      hat    noetig   Faktor
    Tageskerzen     Trend 50 Tage mit Konfluenz       158   0,2682   ≥0,2949   ≥1,10
    15 Minuten      Trendbeteiligung mit Puffer       635   0,0050   ≥0,1558  ≥31,19

Am gepflegten Kassa-Punkt gepaart gerechnet (Befund 486) sind es auf
Tageskerzen **1,25**.

Warum der Vergleich an keiner Schaetzung haengt
-----------------------------------------------
Auf Viertelstunden ist die effektive Stichprobe dieser Regel **nicht**
gemessen, und sie zu schaetzen verbietet ``research/unabhaengigkeit.py`` ohne
Gegenprobe gegen eine bekannte Null. Gerechnet ist deshalb auf der rohen
Trade-Zahl - und die ueberschaetzt die Unabhaengigkeit. ``≥31,19`` ist damit
selbst eine **Untergrenze**: Die wirkliche Entfernung ist groesser, nie
kleiner. Der Schluss wird durch die fehlende Messung also nur sicherer.

Neu ist daran nichts
--------------------
Befund 450 sagt es bereits: *"Keine der 36 Regeln haette die Schwelle bei
irgendeinem Versuchsstand geraeumt, auch nicht beim ersten Versuch."* Und
Befund 171 davor: *"die Vielfalt ist da und sie verliert."*

Dieser Befund ist eine **Bestaetigung mit einem zweiten Werkzeug**, kein
Fund - und er steht hier, weil die Zahl, nach der man beim Entscheiden
greift, ein Faktor ist und kein Erfuellungsgrad. 0,210 gegen 0,804 sagt
nicht, dass eine Idee auf den feinen Kerzen **fuenfundzwanzigmal** besser
werden muesste als der Bestand auf den groben.

Was diese Datei nicht behauptet
-------------------------------
Nicht, dass Viertelstunden schlechter *sind*. Der Kopf von ``erfuellung``
sagt es sauber: Es ist eine Aussage ueber das, was auf ihnen **gefunden**
wurde - der beste Fund aus Jahren gegen den besten aus einem gemessenen
Katalog. Wer dort etwas Neues findet, aendert die Lage; wer die
verbleibenden Versuche nach heutigem Stand verteilt, hat eine klare Antwort.
"""

from __future__ import annotations

import pytest

from research.erfuellung import GEMESSEN, bester_je_intervall
from research.referenz import SPOTPUNKT
from research.seeds import VORGESEHEN
from research.suchbudget import Budget

#: Was ``cli suchbudget`` auf beiden Betriebspunkten gemessen hat.
#:
#: Rohe Trade-Zahlen, also Untergrenzen der Latte und damit des Faktors
#: (Befund 139). Beide Zeilen aus Laeufen bei 203 Versuchen.
GEMESSENE_FAKTOREN: dict[str, tuple[str, int, float, float]] = {
    "D": ("Trend 50 Tage mit Konfluenz", 158, 0.2682, 0.2949),
    "15": ("Trendbeteiligung mit Puffer", 635, 0.0050, 0.1558),
}


def _faktor(intervall: str) -> float:
    _name, _trades, hat, noetig = GEMESSENE_FAKTOREN[intervall]
    return noetig / hat


class TestDerAbstandAufBeidenPunkten:
    def test_auf_tageskerzen_ist_er_knapp(self) -> None:
        assert _faktor("D") == pytest.approx(1.10, abs=5e-3)

    def test_auf_viertelstunden_nicht(self) -> None:
        assert _faktor("15") == pytest.approx(31.19, abs=5e-2)

    def test_und_das_ist_mehr_als_das_zwanzigfache(self) -> None:
        """Die Zahl, nach der man beim Entscheiden greift."""
        assert _faktor("15") / _faktor("D") > 20

    def test_der_gepaarte_abstand_auf_tageskerzen(self) -> None:
        """Gegen die Zahl aus Befund 486 gehalten - dieselbe Richtung, nur
        gepaart gerechnet."""
        budget = Budget(versuche=203)
        _latte, gepaart = budget.am_betriebspunkt(
            effektiv=SPOTPUNKT.effektiv,
            guete=SPOTPUNKT.guete,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )

        assert gepaart == pytest.approx(1.25, abs=5e-3)
        assert _faktor("15") / gepaart > 20

    def test_die_rohe_zahl_macht_den_schluss_sicherer(self) -> None:
        """**Die tragende Zusicherung.** Eine kleinere effektive Stichprobe
        hebt die Latte, also auch den Faktor - der 15m-Wert kann nur steigen.
        Damit haengt der Vergleich an keiner Schaetzung.
        """
        budget = Budget(versuche=203)
        roh = budget.noetig_bei(635, schiefe=0.0, woelbung=3.0)
        weniger = budget.noetig_bei(400, schiefe=0.0, woelbung=3.0)

        assert weniger > roh


class TestDasPasstZumGepflegtenVergleich:
    def test_der_erfuellungsgrad_zeigt_in_dieselbe_richtung(self) -> None:
        """Befund 450 hat es ueber ein dimensionsloses Verhaeltnis gemessen.
        Wenn der Faktor etwas anderes sagte als der Erfuellungsgrad, waere
        eine der beiden Rechnungen falsch."""
        beste = bester_je_intervall()
        tag = beste.get("D")
        fein = beste.get("15")
        if tag is None or fein is None:
            pytest.skip("beide Punkte noetig")

        assert tag.anteil is not None and fein.anteil is not None
        assert tag.anteil > fein.anteil
        assert _faktor("D") < _faktor("15")

    def test_und_der_kopf_nennt_die_neue_zahl(self) -> None:
        """Sonst stuende die Entscheidungszahl nur in einem Test."""
        from pathlib import Path

        kopf = (
            Path(__file__).resolve().parents[1] / "research/erfuellung.py"
        ).read_text(encoding="utf-8")

        assert "≥31,19" in kopf
        assert "489" in kopf
        assert "Untergrenze" in kopf

    def test_keine_der_gemessenen_regeln_haette_geraeumt(self) -> None:
        """Der Satz aus Befund 450, als Zusicherung an den Daten: Auf
        Viertelstunden liegt **jeder** gepflegte Punkt unter seiner Latte."""
        fein = [p for p in GEMESSEN if p.intervall == "15"]

        assert fein, "keine Viertelstunden-Zeile - dann prueft das nichts"
        for p in fein:
            assert p.anteil is None or p.anteil < 1.0, p.regel


class TestDieVorgabeZeigtAufDenAnderenPunkt:
    """Warum der offene Punkt der Liste nachgemessen gehoert."""

    def test_generation_8_liegt_auf_viertelstunden(self) -> None:
        """Die Vorgabe von ``cli wettbewerb`` - und damit der Weg, den die
        Liste empfiehlt."""
        assert VORGESEHEN[8] == "15"

    def test_generation_9_auf_tageskerzen(self) -> None:
        """Die gemessen bessere Wahl. Ein ``-i`` braucht es dafuer nicht:
        Das Intervall folgt der Generation, wenn keines angegeben ist."""
        assert VORGESEHEN[9] == "D"

    def test_und_der_bestand_stammt_von_dort(self) -> None:
        """``Trend 50 Tage mit Konfluenz`` ist eine Regel der Generation 9,
        und alle gepflegten Betriebspunkte stehen auf ``D``."""
        assert SPOTPUNKT.intervall == "D"
        assert GEMESSENE_FAKTOREN["D"][0].startswith("Trend 50 Tage")
