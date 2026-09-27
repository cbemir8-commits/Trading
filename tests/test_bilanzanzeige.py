"""Die ehrliche Bilanz steht jetzt auch da - Befund 351.

Befund 350 hat ``gatebilanz.Gatebilanz`` gebaut und an acht Typen gehaengt.
**Und niemand hat sie gerufen.** Kein einziger Aufruf von ``bilanzsatz``,
``bestanden_ehrlich``, ``geurteilt_ehrlich`` oder ``bilanz_zu_gut`` in ``cli.py``
oder ``research/`` - die Anzeigen zeigten weiter das rohe Paar.

Das ist die Bauart, die dieses Projekt elf Mal gefunden hat (152, 154, 155, 160,
325, 330, 337, 338, 339, 342, 348): **gebaut, gerechnet, nicht angeschlossen.**
Diesmal in der eigenen Arbeit des Vortags.

Angeschlossen sind jetzt die Anzeigen der acht Typen plus die Tabellenspalte der
Bestenliste, die Befund 349 uebersehen hatte. Eine Bilanz, die Gates ohne Urteil
mitzaehlt, traegt ein ``*``, und unter jeder Tabelle, die es zeigen kann, steht
die Fussnote - ein Sternchen ohne Erklaerung ist ein Raetsel.

**Und dieser Test ist die Wache dagegen**, dass es noch einmal passiert: Jeder
Traeger wird mit null Trades und "5 von 11" gebaut, und seine eigene Anzeige
darf das rohe Paar nicht zeigen.
"""

from __future__ import annotations

import pytest

from research.gatebilanz import FUSSNOTE, MARKE, Gatebilanz

#: Wie jeder Traeger zu bauen ist - **ausgeschrieben statt geraten**.
#:
#: Ein Bauplan, der Werte aus den Feldtypen erraet, faellt an der ersten
#: Pruefregel um: ``Marktsatz`` verlangt mindestens einen Markt. Ausgeschrieben
#: ist es laenger und haelt.
#:
#: Jede Zeile beschreibt denselben Fall: **null Trades, "5 von 11"** - also eine
#: Bilanz, die drei Gates mitzaehlt, die nicht geurteilt haben.
BAUPLAN: dict[str, dict[str, object]] = {
    "research.aufstellung.Marktsatz": {
        "name": "Regel", "maerkte": 2, "tage": 3300, "trades": 0,
        "effektiv": 0, "guete": 0.0, "dsr": 0.0, "bestanden": 5, "gesamt": 11,
    },
    "research.betriebspunkt.Betriebspunkt": {
        "name": "Spot", "trades": 0, "cagr_pct": 0.0, "rueckgang_pct": 0.0,
        "guete": 0.0, "dsr": 0.0, "bestanden": 5, "gesamt": 11,
    },
    "research.decke.Stufe": {
        "name": "Regel", "trades": 0, "guete": 0.0, "dsr": 0.0,
        "bestanden": 5, "gesamt": 11,
    },
    "research.decke.Fenster": {
        "name": "Fenster", "von": "2017", "bis": "2026", "trades": 0,
        "guete": 0.0, "dsr": 0.0, "bestanden": 5, "gesamt": 11,
    },
    "research.stand.Lage": {
        "kandidat": "Regel", "maerkte": "BTC + ETH", "trades": 0,
        "sharpe_je_trade": 0.0, "noetiger_sharpe": 0.3, "bestanden": 5,
        "gesamt": 11, "offen": ("Messlatte",), "versuche": 203,
    },
    "research.aufloesung.Messung": {
        "name": "Regel", "trades": 0, "cagr": 0.0, "rueckgang": 0.0,
        "sharpe": 0.0, "bestanden": 5, "gesamt": 11,
    },
    "research.instrument.Lauf": {
        "name": "Regel", "trades": 0, "cagr": 0.0, "rueckgang": 0.0,
        "bestanden": 5, "gesamt": 11,
    },
    "research.sperrprobe.Ergebnis": {
        "trades": 0, "rueckgang_pct": 0.0, "schlechtestes_jahr_pct": 0.0,
        "sharpe_je_trade": 0.0, "dsr": 0.0, "bestanden": 5, "gesamt": 11,
    },
}


def _instanz(name: str):
    """Ein Traeger mit null Trades und einer Bilanz von 5 von 11."""
    import importlib

    modul, klasse = name.rsplit(".", 1)
    return getattr(importlib.import_module(modul), klasse)(**BAUPLAN[name])


#: Traeger und die Methode, mit der sie sich zeigen.
ANZEIGEN: tuple[tuple[str, str], ...] = (
    ("research.aufstellung.Marktsatz", "als_zeile"),
    ("research.betriebspunkt.Betriebspunkt", "als_zeile"),
    ("research.decke.Stufe", "als_zeile"),
    ("research.stand.Lage", "bilanzsatz"),
    ("research.aufloesung.Messung", "bilanzsatz"),
    ("research.instrument.Lauf", "bilanzsatz"),
    ("research.decke.Fenster", "bilanzsatz"),
    ("research.sperrprobe.Ergebnis", "bilanzsatz"),
)


class TestJedeAnzeigeIstEhrlich:
    """**Die Wache.** Wer die Beimischung traegt, zeigt auch, was sie sagt."""

    @pytest.mark.parametrize(("name", "methode"), ANZEIGEN, ids=lambda x: str(x))
    def test_das_rohe_paar_steht_nicht_allein_da(
        self, name: str, methode: str
    ) -> None:
        text = getattr(_instanz(name), methode)()

        assert "2/8" in text or "2 von 8" in text, (
            f"{name}.{methode}() zeigt die geurteilte Bilanz nicht: {text}"
        )

    @pytest.mark.parametrize(("name", "methode"), ANZEIGEN, ids=lambda x: str(x))
    def test_und_ist_als_zu_gut_gekennzeichnet(
        self, name: str, methode: str
    ) -> None:
        """Entweder ein Sternchen oder die rohe Zahl im Klartext - was nicht
        genuegt, ist Schweigen."""
        text = getattr(_instanz(name), methode)()

        assert MARKE in text or "roh" in text, text

    def test_ohne_vorbehalt_bleibt_die_anzeige_schlicht(self) -> None:
        """Die Gegenprobe: Bei 158 Trades steht kein Sternchen und kein
        Zusatz."""
        from research.betriebspunkt import Betriebspunkt

        p = Betriebspunkt(
            name="Spot", trades=158, guete=0.2708, dsr=0.5826,
            cagr_pct=14.34, rueckgang_pct=9.87, bestanden=9, gesamt=11,
        )
        zeile = p.als_zeile()

        assert "9/11 Gates" in zeile
        assert MARKE not in zeile


class TestDieFussnoteErklaertDasZeichen:
    def test_sie_nennt_die_schwellen(self) -> None:
        assert "unter 30" in FUSSNOTE
        assert "unter 20" in FUSSNOTE
        assert MARKE in FUSSNOTE

    def test_die_aufloesungstabelle_traegt_sie_bei_bedarf(self) -> None:
        from research.aufloesung import Aufloesung, Messung

        gut = Messung(
            name="aufgeloest", trades=158, cagr=14.3, rueckgang=9.9,
            sharpe=1.6, bestanden=9, gesamt=11,
        )
        schlecht = Messung(
            name="pessimistisch", trades=0, cagr=0.0, rueckgang=0.0,
            sharpe=0.0, bestanden=5, gesamt=11,
        )

        assert FUSSNOTE in Aufloesung(pessimistisch=schlecht, aufgeloest=gut).tabelle()
        assert FUSSNOTE not in Aufloesung(pessimistisch=gut, aufgeloest=gut).tabelle()

    def test_die_instrumententabelle_auch(self) -> None:
        from research.instrument import Instrumentenwahl, Lauf

        def lauf(name: str, trades: int, bestanden: int) -> Lauf:
            return Lauf(
                name=name, trades=trades, cagr=0.0, rueckgang=0.0,
                bestanden=bestanden, gesamt=11,
            )

        mit = Instrumentenwahl(
            mit_hebel=lauf("mit Hebel", 0, 5), ohne_hebel=lauf("ohne", 158, 9)
        )
        ohne = Instrumentenwahl(
            mit_hebel=lauf("mit Hebel", 158, 9), ohne_hebel=lauf("ohne", 158, 9)
        )

        assert FUSSNOTE in mit.tabelle()
        assert FUSSNOTE not in ohne.tabelle()


class TestDieBestenlistenspalte:
    """Befund 349 hat Rangschluessel und Zusammenfassung gestellt - die Spalte
    in der Tabelle nicht."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return "\n".join(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
        )

    def test_die_spalte_zeigt_die_geurteilte_zahl(self) -> None:
        quelle = self._quelle()

        assert "eintrag.gates_bestanden_echt" in quelle
        assert "eintrag.gates_bestanden}/{eintrag.gates_gesamt" not in quelle


class TestDerMechanismusWirdWirklichGerufen:
    """**Der Fund von 351.** 350 hat gebaut und nicht angeschlossen."""

    @staticmethod
    def _quellen() -> str:
        from pathlib import Path

        text = Path("cli.py").read_text(encoding="utf-8")
        for datei in sorted(Path("research").glob("*.py")):
            if datei.name != "gatebilanz.py":
                text += datei.read_text(encoding="utf-8")
        return text

    def test_die_eigenschaften_werden_benutzt(self) -> None:
        quellen = self._quellen()

        for name in (
            "bestanden_ehrlich",
            "geurteilt_ehrlich",
            "bilanz_zu_gut",
            "marke",
        ):
            assert name in quellen, f"{name} wird nirgends gerufen"

    def test_jeder_traeger_mischt_sie_bei(self) -> None:
        import importlib

        for name, _ in ANZEIGEN:
            modul, klasse = name.rsplit(".", 1)
            obj = getattr(importlib.import_module(modul), klasse)

            assert issubclass(obj, Gatebilanz), name
