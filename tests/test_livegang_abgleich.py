"""Der letzte Schritt vor dem Geld prueft, was gehandelt wird.

**Befund 262.** ``cli abgleich`` traegt im Kopf: *"Vor jedem Livegang
auszufuehren."* Gehandelt wird von ``cli trade``, und das laeuft
ausschliesslich auf ``strategies/champion.json`` - ohne die Datei verweigert
es den Dienst, und es prueft sogar, ob das Instrument dasselbe ist wie bei der
Zulassung (Befund 106).

``abgleich`` nahm ``spitzenkandidat()``: den fest verdrahteten Saatkandidaten
aus ``research/seeds.py``. Solange kein Champion zugelassen ist, faellt das
zusammen - und genau deshalb ist es nie aufgefallen. Sobald einer da ist, und
das ist das Ziel des Projekts, prueft der letzte Schritt vor dem Geld eine
andere Strategie als die, die gleich handelt.

Was hier gehalten wird
----------------------
Dass die Quelle dieselbe ist wie bei ``cli trade``, und dass in der Ausgabe
steht, **welches** Genom geprueft wurde. Ein gruenes "einig" ist wertlos, wenn
es die falsche Strategie betraf - dieselbe Ueberlegung wie bei der
Ausschlussliste in Befund 258.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from research.admission import lade_champion
from research.seeds import spitzenkandidat


def _quelle(name: str) -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == name
    )
    return ast.unparse(knoten)


class TestBeideBefehleNehmenDieselbeQuelle:
    def test_trade_laedt_den_champion(self) -> None:
        """Das war schon so - es ist der Massstab."""
        assert "lade_champion(" in _quelle("trade")

    def test_abgleich_laedt_ihn_jetzt_auch(self) -> None:
        assert "lade_champion(" in _quelle("abgleich")

    def test_beide_meinen_dieselbe_datei(self) -> None:
        for name in ("trade", "abgleich"):
            assert "champion.json" in _quelle(name), name

    def test_der_saatkandidat_ist_nur_die_rueckfallebene(self) -> None:
        """Nicht die erste Wahl: Er kommt erst, wenn es keinen Champion gibt."""
        # Auf die Zuweisungen ankern, nicht auf die Namen: Der Kopf des
        # Befehls nennt 'spitzenkandidat()' schon in der Erklaerung.
        quelle = _quelle("abgleich")
        laden = quelle.index("genome = lade_champion(")
        saat = quelle.index("genome = spitzenkandidat()")

        assert laden < saat


class TestDieAusgabeSagtWelchesGenom:
    def test_die_herkunft_steht_im_kopf(self) -> None:
        assert "Herkunft" in _quelle("abgleich")

    def test_ohne_champion_wird_es_deutlich_gesagt(self) -> None:
        """Sonst liest sich ein gruener Lauf wie eine Freigabe."""
        quelle = _quelle("abgleich")

        assert "kein Livegang-Abgleich" in quelle
        assert "yellow" in quelle

    def test_der_hinweis_nennt_die_folge_fuer_trade(self) -> None:
        assert "wuerde ohne 'champion.json' ohnehin nicht starten" in _quelle(
            "abgleich"
        )


class TestDasLadenSelbst:
    """``lade_champion`` ist die gemeinsame Stelle - sie muss beides koennen."""

    def test_ohne_datei_kommt_nichts(self, tmp_path: Path) -> None:
        assert lade_champion(tmp_path / "champion.json") is None

    def test_ein_zugelassenes_genom_kommt_zurueck(self, tmp_path: Path) -> None:
        genom = spitzenkandidat()
        pfad = tmp_path / "champion.json"
        pfad.write_text(
            json.dumps({"genom": genom.model_dump(mode="json"), "zulassung": {}})
        )

        geladen = lade_champion(pfad)

        assert geladen is not None
        assert geladen.genome_id == genom.genome_id

    def test_ein_anderer_champion_ist_ein_anderes_genom(self, tmp_path: Path) -> None:
        """Der Fall, um den es geht: Waere der Champion immer der
        Saatkandidat, waere der ganze Befund gegenstandslos."""
        genom = spitzenkandidat().model_copy(update={"name": "Etwas anderes"})
        pfad = tmp_path / "champion.json"
        pfad.write_text(json.dumps(genom.model_dump(mode="json")))

        geladen = lade_champion(pfad)

        assert geladen is not None
        assert geladen.name == "Etwas anderes"
        assert geladen.name != spitzenkandidat().name

    def test_eine_kaputte_datei_gibt_none_statt_stapelabzug(
        self, tmp_path: Path
    ) -> None:
        pfad = tmp_path / "champion.json"
        pfad.write_text("{kein json")

        assert lade_champion(pfad) is None


class TestWasDerAbgleichWeiterhinVergleicht:
    """Nicht nur das Signal - von den drei gefundenen Abweichungen haette das
    zwei durchgelassen."""

    def test_die_ganze_entscheidungsflaeche(self) -> None:
        quelle = _quelle("abgleich")

        assert "vergleiche(" in quelle

    def test_eine_abweichung_verbietet_den_livegang(self) -> None:
        quelle = _quelle("abgleich")

        assert "Nicht live gehen" in quelle
        assert "raise typer.Exit(1)" in quelle


def test_der_saatkandidat_bleibt_fuer_die_forschung(
) -> None:
    """Die vielen Forschungsbefehle sollen weiter den Saatkandidaten messen -
    sie vergleichen Verfahren, nicht Livegaenge."""
    assert "spitzenkandidat()" in _quelle("vorratsdecke")
    assert "lade_champion(" not in _quelle("vorratsdecke")
