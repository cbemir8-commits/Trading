"""Gate-Zahlen auf dem Schirm, ohne ihren Betriebspunkt (Befund 466).

Woher die Frage kommt
---------------------
Befund 465 hat ``cli abstand`` berichtigt - zwei Laeufe, zeichengleicher Kopf,
verschiedene steuernde Zahlen - und eine Stelle **ausdruecklich offen**
gelassen: ob andere Befehle, die Gate-Zahlen drucken, denselben Mangel haben.
Dort stand, die ehrliche Antwort heisse 21 Befehle fahren. Das ist hier
gemacht, mit einer saubereren Verengung davor.

Die Verengung
-------------
Nicht "nennt die Funktion ``_betriebspunkt``" - dieser Erkenner hatte in 465
21 Kandidaten geliefert, darunter ``cli stand``, das seinen Punkt
nachweislich nennt. Stattdessen, und mit ``rumpf`` statt ueber den Rohtext,
damit Prosa nicht zaehlt (Befund 399):

    75 Befehle
    32 drucken im Code eine Gate-Zahl
    14 nennen dabei auf keinem der bekannten Wege einen Punkt

Und dann gefahren, denn statische Abwesenheit ist kein Beweis:

    gefahren und bestaetigt      5   anwaerter, aufloesung, front,
                                     koernung, streuung
    gefahren und entkraeftet     1   finanzierung (nennt ihn, der Text kommt
                                     aus einem research-Modul)
    zu langsam fuer einen Lauf   3   paare, rangprobe, sperrprobe
    nicht fahrbar                5   adaptiv, korb, verbund, wettbewerb
                                     (schreiben - 'WIRKT_NACH_AUSSEN'),
                                     trade (handelt)

Der klarste Fall war ``cli aufloesung``: Es druckt eine Spalte **"7/11"** -
genau die Zeichenkette, die der Modulkopf von Befund 242 als verwechselbar
nennt, denn am Spot-Punkt sind es 9 von 11.

Was behoben ist, und was nicht
------------------------------
Vier der fuenf nennen ihren Punkt jetzt im Kopf, gelesen mit
``_betriebspunkt`` aus Genom und Konfigurationen.

``cli koernung`` nicht: Es baut seine Konfigurationen je Kontosprosse in einer
Closure, und den Punkt dort zu nennen heisst entweder umbauen oder ihn ein
zweites Mal herleiten. Eine zweite Herleitung desselben Umstands ist die
naechste Stelle, an der beide auseinanderlaufen (Befund 415), also bleibt es
benannt statt erzwungen.

``cli front`` ging anders: Dort ist der Punkt **nicht** ableitbar. Der Befehl
zieht alle Machbarkeitsberichte zu einer Aussage zusammen, und gemessen nennt
von dreizehn Berichten genau **einer** seinen Betriebspunkt - das Feld gibt es
erst seit Befund 242, und eine Wache kann nichts nachtragen, was nie
geschrieben wurde. Gedruckt wird deshalb die Herkunftslage, nicht ein
geratener Punkt.
"""
from __future__ import annotations

import json

import pytest

from research.front import Herkunftslage, herkunft
from tests.quelltext import rumpf

#: Die Befehle, die gefahren wurden und ihren Punkt jetzt im Kopf nennen.
BERICHTIGT = ("anwaerter", "aufloesung", "streuung")

#: Gemessen und **nicht** behoben, mit Grund - wie ``ABSICHTLICH_ENG`` in
#: ``test_wachenreichweite`` (Befund 464) und ``ENTSCHEIDUNGSGATES`` (461):
#: Wer eine Stelle stehen laesst, nennt sie.
OFFEN_MIT_GRUND: dict[str, str] = {
    "koernung": (
        "Baut seine Konfigurationen je Kontosprosse in einer Closure. Den "
        "Punkt im Kopf zu nennen heisst umbauen oder ihn zweitens herleiten - "
        "und eine zweite Herleitung verbietet Befund 415."
    ),
    "paare": "Zu langsam fuer einen Lauf in der Messung - nicht gefahren.",
    "rangprobe": "Zu langsam fuer einen Lauf in der Messung - nicht gefahren.",
    "sperrprobe": "Zu langsam fuer einen Lauf in der Messung - nicht gefahren.",
    "adaptiv": "Schreibt - steht in 'WIRKT_NACH_AUSSEN', ein Rauschtest darf "
               "nichts hinterlassen (Befund 330/331).",
    "korb": "Schreibt - steht in 'WIRKT_NACH_AUSSEN'.",
    "verbund": "Schreibt - steht in 'WIRKT_NACH_AUSSEN'.",
    "wettbewerb": "Schreibt, bucht Versuche und pusht - auf keinen Fall "
                  "ungefragt gefahren.",
    "trade": (
        "Handelt - der Livebefehl. Ungefragt gefahren wird er nicht, und am "
        "Handelspfad etwas zu aendern, um eine Kopfzeile zu verbessern, ist "
        "eine andere Risikoklasse als ein Forschungsbericht."
    ),
}


class TestDieVierNennenIhrenPunkt:
    @pytest.mark.parametrize("befehl", BERICHTIGT)
    def test_der_kopf_liest_ihn_aus_den_objekten(self, befehl: str) -> None:
        """``rumpf`` und nicht der Rohtext: Der Begruendungskommentar dieses
        Befundes nennt ``_betriebspunkt`` selbst (Befund 399)."""
        import cli

        assert "_betriebspunkt(" in rumpf(getattr(cli, befehl))

    def test_und_front_druckt_die_herkunftslage(self) -> None:
        """Dort ist der Punkt nicht ableitbar - also wird gezaehlt, nicht
        geraten."""
        import cli

        code = rumpf(cli.front)

        assert "herkunft(" in code
        assert "lage_herkunft" in code

    def test_koernung_steht_mit_grund_offen(self) -> None:
        """Die Gegenprobe zur Liste: Was nicht behoben ist, traegt einen
        Grund - und ist nicht stillschweigend ausgelassen."""
        import cli

        assert "koernung" in OFFEN_MIT_GRUND
        assert "_betriebspunkt(" not in rumpf(cli.koernung)

    def test_jeder_offene_fall_nennt_einen_grund(self) -> None:
        for befehl, grund in OFFEN_MIT_GRUND.items():
            assert len(grund) > 20, befehl

    def test_die_listen_nennen_befehle_die_es_gibt(self) -> None:
        import typer

        import cli

        namen = set(typer.main.get_command(cli.app).commands)
        for befehl in (*BERICHTIGT, *OFFEN_MIT_GRUND, "front", "finanzierung"):
            assert befehl in namen, befehl


class TestDieHerkunftslageZaehltUndBehauptetNichts:
    def test_ohne_berichte_sagt_sie_das(self, tmp_path) -> None:
        lage = herkunft(tmp_path)

        assert lage.gesamt == 0
        assert not lage.eindeutig
        assert lage.satz() == "Keine Berichte."

    @staticmethod
    def _schreibe(ordner, name: str, punkt: str | None) -> None:
        inhalt: dict[str, object] = {"regler": "stop", "punkte": []}
        if punkt is not None:
            inhalt["betriebspunkt"] = punkt
        (ordner / name).write_text(json.dumps(inhalt), encoding="utf-8")

    def test_alle_mit_demselben_punkt_ist_eindeutig(self, tmp_path) -> None:
        for i in range(3):
            self._schreibe(tmp_path, f"{i}.json", "Spot (kein Hebel, kein Funding)")
        lage = herkunft(tmp_path)

        assert lage.eindeutig and not lage.gemischt
        assert lage.ohne == 0
        assert "denselben Betriebspunkt" in lage.satz()

    def test_zwei_verschiedene_punkte_heissen_gemischt(self, tmp_path) -> None:
        """**Der gefaehrlichere Fall.** Fehlende Angabe macht die Aussage
        ungewiss; zwei verschiedene machen sie falsch."""
        self._schreibe(tmp_path, "a.json", "Spot (kein Hebel, kein Funding)")
        self._schreibe(tmp_path, "b.json", "Perpetual (Hebel 3, mit Funding)")
        lage = herkunft(tmp_path)

        assert lage.gemischt and not lage.eindeutig
        assert "Verschiedene Betriebspunkte" in lage.satz()
        assert "Befund 428" in lage.satz()

    def test_fehlende_angabe_wird_gezaehlt_nicht_geraten(self, tmp_path) -> None:
        self._schreibe(tmp_path, "a.json", "Spot (kein Hebel, kein Funding)")
        for i in range(4):
            self._schreibe(tmp_path, f"b{i}.json", None)
        lage = herkunft(tmp_path)

        assert lage.gesamt == 5
        assert lage.ohne == 4
        assert "4 von 5" in lage.satz()
        assert "Befund 242" in lage.satz()

    def test_eine_leere_angabe_gilt_als_keine(self, tmp_path) -> None:
        """Sonst zaehlt ein leeres Feld als Beleg."""
        self._schreibe(tmp_path, "a.json", "   ")
        lage = herkunft(tmp_path)

        assert lage.ohne == 1
        assert lage.genannt == ()

    def test_eine_beschaedigte_datei_bricht_nicht_ab(self, tmp_path) -> None:
        """Wie in ``lade``, und aus demselben Grund."""
        (tmp_path / "kaputt.json").write_text("{nicht json", encoding="utf-8")
        self._schreibe(tmp_path, "gut.json", "Spot (kein Hebel, kein Funding)")
        lage = herkunft(tmp_path)

        assert lage.gesamt == 1
        assert lage.eindeutig

    def test_der_satz_behauptet_nie_einen_punkt_den_es_nicht_gibt(
        self, tmp_path
    ) -> None:
        """Die tragende Eigenschaft: Wo nichts belegt ist, steht kein Punkt."""
        for i in range(3):
            self._schreibe(tmp_path, f"{i}.json", None)
        satz = herkunft(tmp_path).satz()

        assert "Spot" not in satz
        assert "Perpetual" not in satz
        assert "3 von 3" in satz


class TestDieWirklicheLageIstVerzeichnet:
    """Der gemessene Stand - als **Eigenschaft**, nicht als Zahl.

    Eine Wache an "12 von 13" wird rot, sobald jemand einen Bericht schreibt,
    und genau diese Bauart hat Befund 454 verworfen.
    """

    def test_die_berichte_dieses_projekts_sind_nicht_eindeutig(self) -> None:
        from pathlib import Path

        lage = herkunft(Path("reports/machbarkeit"))

        assert lage.gesamt > 0, "ohne Berichte prueft dieser Test nichts"
        assert not lage.eindeutig, (
            "Alle Berichte nennen jetzt ihren Punkt - dann gehoert der Satz "
            "aus Befund 466 neu gefasst, nicht diese Zahl nachgezogen."
        )

    def test_und_der_satz_sagt_es(self) -> None:
        from pathlib import Path

        satz = herkunft(Path("reports/machbarkeit")).satz()

        assert "Betriebspunkt" in satz


@pytest.mark.daten
@pytest.mark.langsam
def test_die_ausgabe_von_aufloesung_nennt_den_punkt() -> None:
    """**Die Ausgabe-Ebene**, am billigsten der fuenf Befehle.

    Ein Quelltext-Treffer heisst nicht, dass etwas gedruckt wird (Befund 394).
    Und ``aufloesung`` ist der Fall, der die Zeichenkette "7/11" druckt.
    """
    from typer.testing import CliRunner

    from cli import app

    ergebnis = CliRunner().invoke(app, ["aufloesung"])
    assert ergebnis.exit_code == 0, ergebnis.output[-1200:]
    aus = " ".join(ergebnis.output.split())

    assert "Aufloesung" in aus
    assert "Hebel" in aus or "Spot" in aus
    assert "/11" in aus, "ohne die Gate-Spalte prueft dieser Test nichts"


def test_die_herkunftslage_ist_ein_wert_und_kein_text() -> None:
    """``Herkunftslage`` ist eingefroren: Ein Satz, der sich unterwegs
    aendern laesst, ist kein Beleg."""
    import dataclasses

    lage = Herkunftslage(gesamt=1, genannt=(("Spot", 1),))

    assert dataclasses.is_dataclass(lage)
    with pytest.raises(dataclasses.FrozenInstanceError):
        lage.gesamt = 2  # type: ignore[misc]
