"""Das Etikett war nicht der Schluessel - Befund 493.

Mein Fehler aus Befund 491, und er war still
--------------------------------------------
Befund 491 hat neun Befehlen ``nach_intervall(frames, interval_obj.label)``
gegeben und ``REIHENENDE`` auf ``"D"``/``"15"`` geschluesselt. Aber:

    Interval("D").value  == "D"       Interval("D").label  == "1d"
    Interval("15").value == "15"      Interval("15").label == "15m"

Der Verteiler bekam das **Etikett** und suchte den **Wert**. Er fand nie eine
gepflegte Reihe, fiel in den Zweig "keine gepflegte" und schnitt im Betrieb
**nie**. Gemessen an einem Rahmen, der ueber ``SERIENENDE`` hinausgeht:

    nach_intervall(x, "D")   61 -> 29 Balken   "bis 2026-08-29"
    nach_intervall(x, "1d")  61 -> 61 Balken   "keine gepflegte fuer 1d-Kerzen"

Damit hat Befund 491 den Schnitt an neun Befehlen nicht intervallbewusst
gemacht, sondern **abgeschaltet** - gegenueber Befund 490, wo vier von ihnen
noch ``alle_geschnitten`` riefen. Dass heute keine Zahl kippt, liegt allein
daran, dass der Speicher genau auf den Reihenenden endet; nach dem naechsten
Backfill waere es eine falsche Zahl neben ``referenz.py`` gewesen.

Warum es gruen blieb
--------------------
Alle Tests aus 491 uebergaben die Literale ``"D"`` und ``"15"``. Gemessen
wurde die Funktion, nicht der Aufruf - und die Regel
``test_niemand_ruft_die_tagesfassung_direkt`` prueft, dass niemand die
Tagesfassung **direkt** ruft, nicht dass der Verteiler etwas tut. Eine Wache
auf die Form, keine auf die Wirkung.

Gefunden hat es ein Rauchtest auf echten Daten: ``cli abstand -i D`` druckte
*"keine gepflegte Reihe"*. Der Grundsatz, der das verlangt, steht nicht
zufaellig im Dauerauftrag.

Was jetzt geprueft wird
-----------------------
Die Schreibweise ist keine Falle mehr: ``kerzenschluessel`` nimmt das Objekt,
den Wert, das Etikett oder den Enum-Namen. Die Zuordnung ist **aus
``Interval`` abgeleitet**, nicht aufgeschrieben - eine gepflegte Liste von
Schreibweisen waere die naechste, die altert (Befund 234/485).
"""

from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from core.models import Interval
from research.datenstand import (
    REIHENENDE,
    kerzenschluessel,
    letzter_tag,
    nach_intervall,
    reihenzeile,
)

WURZEL = Path(__file__).resolve().parents[1]

#: Die Kerzenlaengen mit gepflegter Reihe - aus der Tafel, nicht gelistet.
GEPFLEGT: tuple[str, ...] = tuple(sorted(REIHENENDE))


def _lang(schluessel: str = "D", tage: int = 60) -> dict[str, pd.DataFrame]:
    """Ein Rahmen, der ueber das Ende **dieser** Reihe hinausreicht.

    Sonst ist der Schnitt wirkungslos und der Test sagt nichts (Befund 491) -
    und genau das war der erste Entwurf hier: Die Probe endete am 30.09., was
    fuer die Tagesreihe ausserhalb und fuer die Feinreihe innerhalb liegt.
    Mein Pruefaufbau war falsch, nicht der Code.
    """
    letzte = letzter_tag(schluessel)
    assert letzte is not None, schluessel
    ende = letzte + timedelta(days=2)
    return {
        "x": pd.DataFrame(
            {
                "open_time": pd.date_range(
                    ende - timedelta(days=tage), ende, freq="D", tz="UTC"
                )
            }
        )
    }


class TestJedeSchreibweiseFuehrtZumSelbenSchluessel:
    """Abgeleitet aus ``Interval`` - jedes Mitglied, nicht eine Auswahl."""

    @pytest.mark.parametrize("mitglied", list(Interval), ids=lambda m: m.name)
    def test_wert_etikett_name_und_objekt(self, mitglied: Interval) -> None:
        assert kerzenschluessel(mitglied) == mitglied.value
        assert kerzenschluessel(mitglied.value) == mitglied.value
        assert kerzenschluessel(mitglied.label) == mitglied.value
        assert kerzenschluessel(mitglied.name) == mitglied.value

    def test_das_etikett_ist_nicht_der_wert(self) -> None:
        """Die Messung, aus der der Befund kommt. Waeren sie gleich, haette
        491 funktioniert - und dieser Test waere sinnlos."""
        assert Interval("D").label != Interval("D").value
        assert Interval("15").label != Interval("15").value

    def test_was_keine_kerzenlaenge_ist_kommt_unveraendert_zurueck(self) -> None:
        """Keine Rateschleife: Fuer eine fremde Kerzenlaenge gibt es keine
        gepflegte Reihe, und das soll der Aufrufer sehen (Befund 370)."""
        assert kerzenschluessel("Quartal") == "Quartal"
        assert kerzenschluessel("") == ""


class TestDerSchnittGreiftAufJedemWeg:
    """**Geprueft wird die Wirkung, nicht die Form.** Genau das fehlte in
    491: Die Regel dort prueft, dass niemand die Tagesfassung direkt ruft -
    nicht, dass der Verteiler etwas kuerzt."""

    @pytest.mark.parametrize("schluessel", GEPFLEGT)
    def test_auf_jeder_schreibweise_wird_gekuerzt(self, schluessel: str) -> None:
        iv = Interval(schluessel)
        for arg in (iv, iv.value, iv.label, iv.name):
            roh = _lang(schluessel)
            kurz, zeile = nach_intervall(roh, arg)

            assert len(kurz["x"]) < len(roh["x"]), (arg, zeile)
            assert "keine gepflegte" not in zeile, (arg, zeile)
            assert "Balken ausserhalb" in zeile, (arg, zeile)

    def test_und_mit_dem_etikett_sind_es_dieselben_balken_wie_mit_dem_wert(
        self,
    ) -> None:
        """Die Gegenprobe zur Messung im Kopf: 61 -> 29 auf beiden Wegen."""
        mit_wert, _ = nach_intervall(_lang("D"), Interval("D").value)
        mit_etikett, _ = nach_intervall(_lang("D"), Interval("D").label)

        assert len(mit_wert["x"]) == len(mit_etikett["x"]) == 59

    def test_eine_fremde_kerzenlaenge_wird_weiter_nicht_geschnitten(self) -> None:
        roh = _lang("D")
        kurz, zeile = nach_intervall(roh, Interval("W").label)

        assert len(kurz["x"]) == len(roh["x"])
        assert "keine gepflegte" in zeile


class TestDerVermerkUndDieGrenzeAuchAufJedemWeg:
    @pytest.mark.parametrize("schluessel", GEPFLEGT)
    def test_letzter_tag_kennt_jede_schreibweise(self, schluessel: str) -> None:
        iv = Interval(schluessel)
        tage = {letzter_tag(a) for a in (iv, iv.value, iv.label, iv.name)}

        assert len(tage) == 1, tage
        assert None not in tage

    @pytest.mark.parametrize("schluessel", GEPFLEGT)
    def test_der_vermerk_nennt_eine_gepflegte_reihe(self, schluessel: str) -> None:
        """**Der Rauchtest als Zusicherung.** Mit dem Etikett stand hier
        "keine gepflegte Reihe" - und das war die Zeile, die den Befund
        gefunden hat."""
        letzte = letzter_tag(schluessel)
        rahmen = {
            "a": pd.DataFrame(
                {
                    "open_time": pd.date_range(
                        "2021-01-01", str(letzte), freq="D", tz="UTC"
                    )
                }
            )
        }
        zeile = reihenzeile(rahmen, Interval(schluessel).label)

        assert "keine gepflegte Reihe" not in zeile, zeile
        assert "laenger als" not in zeile, zeile


class TestDieTafelBleibtAufWerten:
    def test_jeder_schluessel_ist_ein_intervallwert(self) -> None:
        """Sonst ist die Tafel selbst auf Etiketten gerutscht, und dann
        findet der Verteiler wieder nichts."""
        werte = {m.value for m in Interval}

        assert set(REIHENENDE) <= werte, sorted(set(REIHENENDE) - werte)

    def test_es_sind_zwei(self) -> None:
        """Nichtleere-Zusicherung (Befund 479) mit Zahl: Kommt eine dritte
        Reihe dazu, laufen die Regeln darueber von allein mit."""
        assert len(GEPFLEGT) == 2, GEPFLEGT


class TestDieBefehleGehenUeberDenVerteiler:
    def test_keiner_baut_den_schluessel_selbst(self) -> None:
        """Ein Vergleich wie ``if intervall == "15"`` in einem Befehl ist
        derselbe Fehler noch einmal - die Antwort steht in
        ``kerzenschluessel``."""
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        schuldig = []
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.FunctionDef):
                continue
            quelle = ast.unparse(knoten)
            if "REIHENENDE" in quelle and "kerzenschluessel" not in quelle:
                schuldig.append(knoten.name)

        assert schuldig == [], (
            "greift selbst in die Reihentafel, statt den Schluessel zu "
            f"fragen - genau das war Befund 493: {schuldig}"
        )
