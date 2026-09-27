"""Hat irgendwo ein Gate gar nicht geurteilt? - Befund 346.

Befund 332 hat sechzehn Datentypen aufgelistet, die eine Gate-Bilanz tragen und
nicht sagen koennen, ob jedes Gate geurteilt hat - und ausdruecklich **nicht**
gemessen, ob es heute etwas trifft. 333 hat es fuer den Spitzenkandidaten
nachgeholt (158 Trades, elf Urteile, null Aussetzer), fuer die Leitern blieb es
offen.

**Nachgemessen an allem, was geschrieben wurde** (346): 83 Messpunkte aus 13
Berichten, zehn Regler - kein einziger Aussetzer, jeder Punkt mit elf Gates,
kleinste Trade-Zahl **75** gegen Aussetzschwellen von 30 (Regime-Aufteilung,
Deflated Sharpe) und 20 (Monte-Carlo).

Das ist kein Freispruch fuer die Zukunft, sondern die Auskunft, die gefehlt hat:
nicht "koennte falsch sein", sondern "ist es auf allem Geschriebenen nicht".

**Und einer der dreizehn offenen Faelle ist zu**: ``regler.Stellung`` traegt
jetzt ``uebersprungen``. Bewusst dieser zuerst - auf seiner Leiter steht die
offene Entscheidung zur Messlatte (Befund 281/341), und eine geschenkte Zahl
waere dort besonders teuer.
"""

from __future__ import annotations

import json

import pytest

from research.aussetzer import Berichtslage, Punktlage, lese
from research.regler import Stellung

#: Was die Berichte auf der Platte hergeben (Befund 346).
PUNKTE = 83
DATEIEN = 13
KLEINSTE_TRADE_ZAHL = 75


def _punkt(**rest) -> Punktlage:
    daten = {
        "datei": "2026-09-14_005951",
        "stellung": 19.3,
        "trades": 158,
        "gates": 11,
        "uebersprungen": 0,
    }
    daten.update(rest)
    return Punktlage(**daten)


class TestEinPunktSagtEsJetzt:
    def test_geurteilt_ist_gesamt_ohne_aussetzer(self) -> None:
        assert _punkt().geurteilt == 11
        assert _punkt(uebersprungen=3).geurteilt == 8

    def test_vollstaendig_heisst_elf_urteile(self) -> None:
        assert _punkt().vollstaendig
        assert not _punkt(uebersprungen=1).vollstaendig

    def test_ohne_gates_ist_nichts_vollstaendig(self) -> None:
        """Null Gates sind keine vollstaendige Bilanz, sondern keine."""
        assert not _punkt(gates=0).vollstaendig

    def test_die_naehe_zur_schwelle_ist_benannt(self) -> None:
        """60 ist das Doppelte der hoechsten Aussetzschwelle - darunter ist die
        Frage keine theoretische mehr."""
        assert not _punkt(trades=75).nah_an_der_schwelle
        assert _punkt(trades=59).nah_an_der_schwelle


class TestDieBerichtslage:
    def test_sie_zaehlt_dateien_und_aussetzer(self) -> None:
        lage = Berichtslage(
            punkte=(
                _punkt(datei="a"),
                _punkt(datei="a", stellung=20.5),
                _punkt(datei="b", uebersprungen=2),
            )
        )

        assert lage.dateien == 2
        assert len(lage.mit_aussetzern) == 1
        assert lage.kleinste_trade_zahl == 158

    def test_ohne_punkte_wird_nichts_behauptet(self) -> None:
        lage = Berichtslage(punkte=())

        assert lage.kleinste_trade_zahl is None
        assert "laesst sich so nichts sagen" in lage.urteil()

    def test_ein_aussetzer_wird_deutlich_gemeldet(self) -> None:
        lage = Berichtslage(punkte=(_punkt(), _punkt(stellung=25.0, uebersprungen=2)))
        urteil = lage.urteil()

        assert "tragen ein Gate ohne Urteil" in urteil
        assert "Stellung 25 (2 von 11)" in urteil
        assert "zu gut" in urteil

    def test_ohne_aussetzer_steht_die_kleinste_trade_zahl_dabei(self) -> None:
        """Ohne sie waere "kein Aussetzer" eine Behauptung ohne Abstand."""
        urteil = Berichtslage(punkte=(_punkt(), _punkt(trades=75))).urteil()

        assert "Kein einziger Aussetzer" in urteil
        assert "kleinste Trade-Zahl ist 75" in urteil
        assert "Kein Punkt liegt unter 60 Trades" in urteil

    def test_knappe_punkte_werden_genannt(self) -> None:
        urteil = Berichtslage(punkte=(_punkt(), _punkt(trades=40))).urteil()

        assert "1 Punkte liegen unter 60 Trades" in urteil


class TestDasLesenDerBerichte:
    def test_die_platte_liefert_die_gemessenen_zahlen(self) -> None:
        lage = lese("reports")

        assert len(lage.punkte) == PUNKTE
        assert lage.dateien == DATEIEN
        assert lage.kleinste_trade_zahl == KLEINSTE_TRADE_ZAHL

    def test_und_keinen_einzigen_aussetzer(self) -> None:
        """**Der Befund.** Die Bedingung aus 332 ist nicht eingetreten - und
        nirgends in die Naehe gekommen."""
        lage = lese("reports")

        assert lage.mit_aussetzern == ()
        assert lage.knappe == ()
        assert all(p.gates == 11 for p in lage.punkte)

    def test_ein_fehlender_ordner_ist_kein_fehler(self) -> None:
        assert lese("gibt-es-nicht").punkte == ()

    def test_kaputte_dateien_werden_uebergangen(self, tmp_path) -> None:
        """Eine unlesbare Datei ist kein Grund, die Auskunft ueber die anderen
        zu verlieren."""
        (tmp_path / "kaputt.json").write_text("{nicht json")
        (tmp_path / "leer.json").write_text("[]")
        (tmp_path / "gut.json").write_text(
            json.dumps(
                {
                    "punkte": [
                        {
                            "stellung": 1.0,
                            "kennzahlen": {"trades": 80},
                            "gates": {
                                "A": {"bestanden": True},
                                "B": {"bestanden": True, "uebersprungen": True},
                            },
                        }
                    ]
                }
            )
        )
        lage = lese(tmp_path)

        assert len(lage.punkte) == 1
        assert lage.punkte[0].uebersprungen == 1
        assert lage.punkte[0].trades == 80

    def test_punkte_ohne_gates_zaehlen_nicht(self, tmp_path) -> None:
        """Ein Punkt ohne Gate-Angabe sagt ueber Aussetzer nichts - ihn als
        "kein Aussetzer" zu zaehlen waere eine geschenkte Zahl."""
        (tmp_path / "a.json").write_text(
            json.dumps({"punkte": [{"stellung": 1.0, "kennzahlen": {"trades": 9}}]})
        )

        assert lese(tmp_path).punkte == ()


class TestDieReglerleiterSagtEsJetzt:
    """Der erste der dreizehn offenen Faelle aus Befund 332."""

    @staticmethod
    def _stellung(**rest) -> Stellung:
        daten = {
            "wert": 19.3, "trades": 158, "rendite": 14.34, "rueckgang": 9.87,
            "bestanden": 9, "gesamt": 11, "offen": ("Messlatte", "Deflated Sharpe"),
        }
        daten.update(rest)
        return Stellung(**daten)

    def test_ohne_aussetzer_bleibt_alles_wie_vorher(self) -> None:
        s = self._stellung()

        assert (s.geurteilt, s.bestanden_echt) == (11, 9)
        assert "9/11" in s.als_zeile()
        assert "ausgesetzt" not in s.als_zeile()

    def test_ein_aussetzer_zaehlt_nicht_als_bestanden(self) -> None:
        s = self._stellung(uebersprungen=2)

        assert (s.geurteilt, s.bestanden_echt) == (9, 7)
        assert "7/9" in s.als_zeile()
        assert "(2 ausgesetzt)" in s.als_zeile()

    def test_der_vorgabewert_ist_kein_aussetzer(self) -> None:
        """Die sichere Richtung: Wer das Feld nicht setzt, bekommt die alte
        Zahl, und ein Aussetzer muss ausdruecklich gemeldet werden."""
        assert self._stellung().uebersprungen == 0

    def test_unsinn_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="uebersprungene von 11"):
            self._stellung(uebersprungen=12)

    def test_der_befehl_fuellt_es(self) -> None:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "regler"
        )

        assert "uebersprungen=sum(" in quelle
        assert "if r.status is GateStatus.SKIP" in quelle


class TestDerRegistereintrag:
    @staticmethod
    def _eintrag():
        from research.stand import OFFEN

        return next(r for r in OFFEN if "Gate-Zahlen" in r.name)

    def test_der_name_zaehlt_die_liste_und_nicht_irgendwas(self) -> None:
        """Der Name ist eine Zahl, und Zahlen veralten - deshalb steht der
        **Abgleich** hier und nicht die Zahl. Wer einen Fall schliesst, zieht
        beide nach; Befund 347 hat es getan (zwoelf auf elf)."""
        from tests.test_gatezahlen import OFFEN as OFFENE_TYPEN

        worte = {
            11: "Elf", 12: "Zwoelf", 13: "Dreizehn", 14: "Vierzehn",
            15: "Fuenfzehn", 16: "Sechzehn",
        }

        assert self._eintrag().name.startswith(worte[len(OFFENE_TYPEN)])

    def test_die_messung_steht_drin(self) -> None:
        ergebnis = self._eintrag().ergebnis

        assert "83 Messpunkte" in ergebnis
        assert "kleinste Trade-Zahl 75" in ergebnis

    def test_der_geschlossene_fall_steht_drin(self) -> None:
        """Was Befund 346 geschlossen hat - die Zahl der noch offenen ist
        Sache des jeweils neuesten Befunds."""
        ergebnis = self._eintrag().ergebnis

        assert "'regler.Stellung' traegt" in ergebnis
        assert "besonders teuer waere" in ergebnis

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 332
        # "Mindestens": Jede weitere Schliessung zieht die Fundstelle hoch,
        # und dieser Test prueft die Messung von 346, nicht ihr Datum.
        assert eintrag.massgeblich >= 346

    def test_der_befehl_sagt_es(self) -> None:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "register"
        )

        assert "from research.aussetzer import lese as aussetzer_lesen" in quelle
        assert "lage_gates.urteil()" in quelle
