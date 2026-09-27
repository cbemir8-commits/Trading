"""Die letzten drei Gate-Zahlen - Befund 352.

Befund 332 hat sechzehn Typen aufgelistet, deren Gate-Bilanz nicht sagt, ob
alle gezaehlten Gates ueberhaupt geurteilt haben. 338, 346, 347, 349, 350 und
351 haben dreizehn davon nachgezogen. **Drei blieben offen**, mit derselben
Begruendung jedes Mal: Sie tragen keine Trade-Zahl, also ist nichts zu
erschliessen.

Das war die falsche Frage. Eingeteilt hatte ich nach dem, was die
**Datenklasse** traegt - nachzusehen war, was am **Bauplatz** liegt:

    Gebuehrenstufe        ``bericht.all_trades``  zwei Zeilen darueber
    Ratenprobe            dasselbe
    Zulassungsbedingungen ``candidate.trades``, und der ganze Gate-Bericht

Und weil dort der Gate-Bericht liegt, ist die **gemeldete** Zahl zu haben, die
genauer ist als die erschlossene: ``GateResult.status`` sagt es je Gate, statt
es aus der Trade-Zahl zu folgern. Die drei waren nicht schwerer als die
anderen dreizehn, sondern leichter.

Das ist die dritte Fassung derselben Lektion (333, 349): **ein Stellvertreter
fuer die Faehigkeit, nicht die Faehigkeit.** Dort war es ein Feldname als
Stellvertreter fuer "kann es melden", hier die Datenklasse als Stellvertreter
fuer "die Zahl ist zu haben".

Dieser Test bindet die drei **Bauplaetze**, nicht nur die Felder: Ein Feld, das
niemand fuellt, ist die Bauart aus Befund 351 - gebaut, gerechnet, nicht
angeschlossen.

Die Sonderstellung des Nachweises
---------------------------------
``Zulassungsbedingungen`` wird **gelesen**, nicht nur gebaut, und jede
``champion.json`` von vor Befund 352 traegt an dieser Stelle eine Null. Aus ihr
drei ausgesetzte Gates zu folgern waere eine Behauptung ohne Messung - auch die
vorsichtige Richtung ist geraten. Der Nachweis sagt deshalb, dass er es nicht
weiss.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from research.admission import Zulassungsbedingungen
from research.gatebilanz import MARKE, Gatebilanz
from research.instrument import Gebuehrenstufe
from research.ratenbild import Ratenbild, Ratenprobe

#: Die drei, ihr Bauplatz in ``cli.py`` und die Stelle, die sie **zeigt**.
#:
#: Bei zwei ist das dieselbe Funktion; beim Nachweis nicht - er zeigt sich in
#: ``als_text``, weil er in eine Datei geschrieben und spaeter wieder gelesen
#: wird. Deshalb stehen hier zwei Spalten und nicht eine.
BAUPLAETZE: tuple[tuple[str, str, str], ...] = (
    ("Gebuehrenstufe", "instrument", "cli.py"),
    ("Ratenprobe", "finanzierung", "cli.py"),
    ("Zulassungsbedingungen", "_bedingungen", "research/admission.py"),
)


def _funktion(name: str) -> str:
    """Der Quelltext **einer** Funktion aus ``cli.py``.

    Die ganze Datei zu lesen wuerde hier nichts beweisen: ``trades=`` steht
    darin an hundert Stellen. Gebunden werden soll der Bauplatz.
    """
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and knoten.name == name:
            return ast.unparse(knoten)
    raise AssertionError(f"{name} steht nicht mehr in cli.py")


def _stufe(
    trades: int, uebersprungen: int, bestanden: int, faktor: float = 1.0
) -> Gebuehrenstufe:
    """Eine Stufe - **nach der Signatur gebaut, nicht nach ihrem Klang.**

    Befund 351 hat genau hier einen Nachmittag gekostet: geratene Feldnamen
    laufen bis zum ersten ``TypeError``.
    """
    return Gebuehrenstufe(
        faktor=faktor, dsr=0.0, guete=0.0, cagr=0.0, bestanden=bestanden,
        gesamt=11, trades=trades, uebersprungen=uebersprungen,
    )


def _probe(trades: int, uebersprungen: int, bestanden: int) -> Ratenprobe:
    bild = Ratenbild(
        name="flach",
        zeiten=(datetime(2024, 1, 1, tzinfo=UTC),),
        saetze=(0.0001,),
    )
    return Ratenprobe(
        bild=bild, bestanden=bestanden, gesamt=11, gefallen=(), cagr_pct=0.0,
        rueckgang_pct=0.0, gezahlt=0.0, trades=trades,
        uebersprungen=uebersprungen,
    )


class TestAlleDreiTragenDieBilanz:
    """Der Mechanismus aus Befund 350, jetzt vollstaendig angeschlossen."""

    @pytest.mark.parametrize(
        "typ", [Gebuehrenstufe, Ratenprobe, Zulassungsbedingungen]
    )
    def test_die_beimischung_ist_da(self, typ: type) -> None:
        assert issubclass(typ, Gatebilanz)

    @pytest.mark.parametrize(
        "typ", [Gebuehrenstufe, Ratenprobe, Zulassungsbedingungen]
    )
    def test_beide_felder_sind_da(self, typ: type) -> None:
        from dataclasses import fields

        namen = {f.name for f in fields(typ)}

        assert "trades" in namen
        assert "uebersprungen" in namen


class TestDieGemeldeteZahlGewinnt:
    """**Warum die drei leichter waren als die dreizehn.**

    Am Bauplatz liegt der Gate-Bericht, also ist die harte Auskunft zu haben.
    Sie ist genauer: Die erschlossene Zahl ist eine Untergrenze, die gemeldete
    zaehlt auch, was ``run_expensive`` oder eine feste Periode ausgesetzt hat.
    """

    def test_vier_gemeldete_schlagen_drei_erschlossene(self) -> None:
        stufe = _stufe(trades=12, uebersprungen=4, bestanden=9)

        assert len(stufe.uebersprungen_erschlossen) == 3
        assert stufe.uebersprungen_ehrlich == 4
        assert stufe.geurteilt_ehrlich == 7
        assert stufe.bestanden_ehrlich == 5

    def test_eine_gemeldete_null_ueberstimmt_die_erschliessung_nicht(self) -> None:
        """Sonst waere die schlechtere Auskunft die verbindliche."""
        probe = _probe(trades=8, uebersprungen=0, bestanden=8)

        assert probe.uebersprungen_ehrlich == 3
        assert probe.bilanz_zu_gut

    def test_bei_genug_trades_bleibt_die_bilanz_schlicht(self) -> None:
        stufe = _stufe(trades=158, uebersprungen=0, bestanden=9)

        assert not stufe.bilanz_zu_gut
        assert stufe.bilanzsatz() == "9/11 Gates"


class TestDerBauplatzFuelltBeides:
    """**Die Wache gegen Befund 351.** Ein Feld, das niemand fuellt, zaehlt
    nicht."""

    @pytest.mark.parametrize(
        ("typ", "funktion", "_anzeige"), BAUPLAETZE, ids=lambda x: str(x)
    )
    def test_die_trade_zahl_wird_mitgegeben(
        self, typ: str, funktion: str, _anzeige: str
    ) -> None:
        quelle = _funktion(funktion)

        assert "trades=" in quelle, f"{funktion} baut {typ} ohne Stichprobe"

    @pytest.mark.parametrize(
        ("typ", "funktion", "_anzeige"), BAUPLAETZE, ids=lambda x: str(x)
    )
    def test_und_die_ausgesetzten_gates(
        self, typ: str, funktion: str, _anzeige: str
    ) -> None:
        quelle = _funktion(funktion)

        assert "uebersprungen=" in quelle, f"{funktion} baut {typ} ohne Aussetzer"
        assert "GateStatus.SKIP" in quelle, (
            f"{funktion} zaehlt die Aussetzer nicht aus dem Gate-Bericht"
        )

    @pytest.mark.parametrize(
        ("typ", "_funktion", "anzeige"), BAUPLAETZE, ids=lambda x: str(x)
    )
    def test_die_anzeige_zeigt_die_geurteilte_bilanz(
        self, typ: str, _funktion: str, anzeige: str
    ) -> None:
        """Die zweite Haelfte: gefuellt **und** gezeigt - Befund 351."""
        quelle = Path(anzeige).read_text(encoding="utf-8")

        assert "bestanden_ehrlich" in quelle or "bilanzsatz" in quelle, (
            f"{anzeige} rechnet die ehrliche Bilanz fuer {typ} und zeigt sie nicht"
        )


class TestDieTreppeUndIhreTabelle:
    """**Der halbe Anschluss, noch einmal.** Die Treppe in ``cli instrument``
    war auf die geurteilte Zahl gestellt - ``Tragfaehigkeit.tabelle`` daneben
    zeigte weiter das rohe Paar. Dieselbe Haelfte, die Befund 351 an der
    Bestenliste gefunden hat.
    """

    @staticmethod
    def _bild(*stufen: Gebuehrenstufe):
        from research.instrument import Tragfaehigkeit

        return Tragfaehigkeit(stufen=list(stufen), schwelle=0.95)

    def test_die_tabelle_zeigt_die_geurteilte_zahl(self) -> None:
        bild = self._bild(_stufe(trades=12, uebersprungen=3, bestanden=8))
        tafel = bild.tabelle()

        assert "5/8" in tafel
        assert "8/11" not in tafel

    def test_und_traegt_die_fussnote(self) -> None:
        from research.gatebilanz import FUSSNOTE

        mit = self._bild(_stufe(trades=12, uebersprungen=3, bestanden=8))
        ohne = self._bild(_stufe(trades=158, uebersprungen=0, bestanden=9))

        assert FUSSNOTE in mit.tabelle()
        assert FUSSNOTE not in ohne.tabelle()

    def test_die_bruchstelle_vergleicht_geurteilte_zahlen(self) -> None:
        """**Der Grund, warum das mehr als Anzeige ist.** Ein hoeherer Tarif
        drueckt die Trade-Zahl; faellt sie unter 30, setzen Gates aus und
        zaehlen roh als bestanden. Roh verglichen faellt die Bilanz von 9 auf 9
        - also kein Bruch, genau dort, wo der Tarif ihn verursacht.
        """
        billig = _stufe(trades=158, uebersprungen=0, bestanden=9)
        teuer = _stufe(trades=12, uebersprungen=3, bestanden=9, faktor=2.0)

        bruch = self._bild(billig, teuer).bruchstelle

        assert billig.bestanden == teuer.bestanden
        assert bruch is not None, "roh verglichen bleibt der Bruch unsichtbar"
        assert bruch[1].faktor == 2.0

    def test_und_das_urteil_nennt_sie(self) -> None:
        billig = _stufe(trades=158, uebersprungen=0, bestanden=9)
        teuer = _stufe(trades=12, uebersprungen=3, bestanden=9, faktor=2.0)

        urteil = self._bild(billig, teuer).urteil()

        assert "von 9 auf 6 von 8" in urteil


class TestDerNachweisWeissWannErEsNichtWeiss:
    """Die Sonderstellung der gelesenen Datei."""

    def test_eine_null_heisst_nicht_aufgezeichnet(self) -> None:
        alt = Zulassungsbedingungen(markt="perpetual", bestanden=11, gesamt=11)

        assert not alt.stichprobe_bekannt
        assert alt.uebersprungen_erschlossen == ()
        assert not alt.bilanz_zu_gut

    def test_und_der_text_sagt_das(self) -> None:
        """**Nicht schweigen.** Ohne diesen Satz stuende "11/11 Gates" so da,
        als waere es geprueft."""
        alt = Zulassungsbedingungen(markt="perpetual", bestanden=11, gesamt=11)
        text = alt.als_text()

        assert "11/11 Gates" in text
        assert "Stichprobe nicht aufgezeichnet" in text
        assert MARKE not in text

    def test_mit_stichprobe_steht_die_ehrliche_bilanz_da(self) -> None:
        duenn = Zulassungsbedingungen(
            markt="spot", bestanden=8, gesamt=11, trades=12, uebersprungen=3
        )
        text = duenn.als_text()

        assert "5/8 Gates" in text
        assert "roh 8/11" in text
        assert "12 Trades" in text

    def test_und_bei_genug_trades_bleibt_sie_schlicht(self) -> None:
        dick = Zulassungsbedingungen(
            markt="spot", bestanden=9, gesamt=11, trades=158
        )
        text = dick.als_text()

        assert "9/11 Gates" in text
        assert "158 Trades" in text
        assert "roh" not in text

    def test_beides_ueberlebt_den_weg_durch_die_datei(self, tmp_path: Path) -> None:
        """**Der Nachweis ist der einzige der sechzehn, der geschrieben und
        wieder gelesen wird.** Ein Feld, das den Weg durch ``asdict`` und
        ``lade_bedingungen`` nicht uebersteht, ist am Bauplatz gefuellt und in
        der Datei weg.
        """
        from research.admission import lade_bedingungen, write_champion
        from research.seeds import spitzenkandidat

        class FakeGates:
            referenzdaten = True
            results = ()

        class FakeKandidat:
            genome = spitzenkandidat()
            gates = FakeGates()

        ziel = tmp_path / "champion.json"
        write_champion(
            FakeKandidat(),
            ziel,
            bedingungen=Zulassungsbedingungen(
                markt="spot", bestanden=8, gesamt=11, trades=12, uebersprungen=3
            ),
        )

        gelesen = lade_bedingungen(ziel)

        assert gelesen.trades == 12
        assert gelesen.uebersprungen == 3
        assert gelesen.bestanden_ehrlich == 5
        assert "roh 8/11" in gelesen.als_text()

    def test_das_alte_format_bleibt_lesbar(self, tmp_path: Path) -> None:
        """Die Wache aus ``test_zulassungsnachweis``: Zwei neue Felder duerfen
        eine vorhandene Zulassung nicht ungueltig machen."""
        import json

        from research.admission import lade_bedingungen

        datei = tmp_path / "champion.json"
        datei.write_text(json.dumps({
            "genome": {},
            "zulassung": {
                "markt": "spot", "bestanden": 9, "gesamt": 11, "kapital": 500.0
            },
        }))

        geladen = lade_bedingungen(datei)

        assert geladen.vollstaendig
        assert geladen.trades == 0
        assert geladen.uebersprungen == 0
        assert not geladen.stichprobe_bekannt
