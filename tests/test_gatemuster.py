"""Welche Gates zusammenlaufen - und die Grenze dessen, was daraus folgt.

Zwei Tests tragen diese Datei:

``test_ein_stummes_gate_ist_kein_ueberfluessiges`` - Ein Gate, das alle
Kandidaten bestehen, unterscheidet in dieser Wolke nichts. Daraus "also weg
damit" zu machen waere die eleganteste Art, ein Gate zu lockern: Es hat die
schlechteren Kandidaten frueher aussortiert, die hier gar nicht mehr
auftauchen.

``test_zwei_immer_bestandene_gates_gelten_nicht_als_paar`` - Die
Uebereinstimmung ist die verfuehrerische Zahl und die falsche. Zwei Gates, die
praktisch immer bestehen, stimmen zu 100 % ueberein, ohne etwas miteinander zu
tun zu haben. Entschieden wird deshalb an Phi.
"""

from __future__ import annotations

import json
from pathlib import Path

from research.gatemuster import STARK, Gatelage, Gatemuster, lade


def punkte(*muster: dict[str, bool]) -> Gatemuster:
    return Gatemuster(punkte=list(muster))


class TestLage:
    def test_die_quote_zaehlt_die_bestandenen(self) -> None:
        muster = punkte(
            {"A": True, "B": False},
            {"A": True, "B": False},
            {"A": False, "B": False},
        )
        lagen = {lage.name: lage for lage in muster.lagen}

        assert lagen["A"].quote == 2 / 3
        assert lagen["B"].quote == 0.0

    def test_ein_stummes_gate_ist_kein_ueberfluessiges(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Ein Gate, das jeder Punkt besteht, unterscheidet hier nichts - und das
        Urteil muss dazusagen, warum daraus nicht folgt, es sei entbehrlich.
        Sonst liest sich diese Auswertung beim naechsten Mal als Einladung,
        eine Huerde zu streichen.
        """
        muster = punkte(
            {"Immer": True, "Wechselnd": True},
            {"Immer": True, "Wechselnd": False},
        )

        assert [lage.name for lage in muster.stumme] == ["Immer"]
        urteil = muster.urteil()
        assert "unterscheiden hier nichts" in urteil
        assert "frueher aussortiert" in urteil
        assert "keine Vorbereitung darauf, eines davon zu streichen" in urteil

    def test_immer_und_nie_bestanden_werden_getrennt_gemeldet(self) -> None:
        """**Sie bedeuten das Gegenteil voneinander.**

        Der erste Anlauf warf beide in einen Satz und erklaerte sie damit,
        dass die Vorauswahl schon gewirkt habe. Fuer ein nie bestandenes Gate
        ist das genau falsch herum: Dort ist nichts aussortiert worden, dort
        steht die Wand - und in der gemessenen Wolke ist das ausgerechnet der
        Deflated Sharpe.
        """
        muster = punkte(
            {"Immer": True, "Nie": False, "Wechselnd": True},
            {"Immer": True, "Nie": False, "Wechselnd": False},
        )
        urteil = muster.urteil()

        assert "Immer bestanden: Immer" in urteil
        assert "Nie bestanden: Nie" in urteil
        assert "das ist die Wand" in urteil
        assert "frueher aussortiert" in urteil

    def test_auch_ein_nie_bestandenes_gate_ist_stumm(self) -> None:
        assert Gatelage(name="X", bestanden=0, gesamt=9).stumm
        assert Gatelage(name="X", bestanden=9, gesamt=9).stumm
        assert not Gatelage(name="X", bestanden=4, gesamt=9).stumm


class TestPaare:
    def test_gleichlaufende_gates_bekommen_phi_eins(self) -> None:
        muster = punkte(
            {"A": True, "B": True},
            {"A": False, "B": False},
            {"A": True, "B": True},
            {"A": False, "B": False},
        )

        paar = muster.paare()[0]
        assert paar.phi == 1.0
        assert paar.stark

    def test_gegenlaeufige_gates_fallen_ebenfalls_auf(self) -> None:
        """Ein Phi von -1 heisst: Wer das eine besteht, reisst das andere.
        Auch das ist ein Strang - er bewegt sich nur in die andere Richtung."""
        muster = punkte(
            {"A": True, "B": False},
            {"A": False, "B": True},
            {"A": True, "B": False},
            {"A": False, "B": True},
        )

        paar = muster.paare()[0]
        assert paar.phi == -1.0
        assert paar.stark

    def test_zwei_immer_bestandene_gates_gelten_nicht_als_paar(self) -> None:
        """**Der zweite tragende Test.**

        Beide bestehen immer, also stimmen sie zu 100 % ueberein - und haben
        trotzdem nichts miteinander zu tun. Wer an der Uebereinstimmung
        entscheidet, faende hier ein Paar, das keines ist.
        """
        muster = punkte(
            {"A": True, "B": True, "C": False},
            {"A": True, "B": True, "C": True},
        )

        ab = next(p for p in muster.paare() if {p.a, p.b} == {"A", "B"})
        assert ab.uebereinstimmung == 1.0, "Die verfuehrerische Zahl"
        assert ab.phi == 0.0, "Die richtige"
        assert not ab.stark

    def test_unabhaengige_gates_bilden_keine_gruppe(self) -> None:
        muster = punkte(
            {"A": True, "B": True},
            {"A": True, "B": False},
            {"A": False, "B": True},
            {"A": False, "B": False},
        )

        assert muster.gruppen == []
        assert f"Phi von {STARK:.1f}" in muster.urteil()


class TestGruppen:
    def test_ein_strang_entsteht_auch_ueber_ein_zwischenglied(self) -> None:
        """A haengt an B, B an C - dann bewegen sich alle drei gemeinsam,
        auch wenn A und C sich nicht direkt beruehren."""
        muster = punkte(
            {"A": True, "B": True, "C": True},
            {"A": False, "B": False, "C": False},
            {"A": True, "B": True, "C": True},
            {"A": False, "B": False, "C": False},
        )

        assert muster.gruppen == [{"A", "B", "C"}]
        assert "Straenge laufen zusammen" in muster.urteil()

    def test_ein_einzelnes_gate_ist_kein_strang(self) -> None:
        muster = punkte(
            {"A": True, "B": True, "C": False},
            {"A": False, "B": False, "C": False},
            {"A": True, "B": True, "C": True},
        )

        assert all(len(g) > 1 for g in muster.gruppen)


class TestLaden:
    def bericht(self, ordner: Path, name: str, punkte: list[dict]) -> None:
        (ordner / name).write_text(json.dumps({"regler": "X", "punkte": punkte}))

    def test_uebersprungene_gates_gelten_nicht_als_durchgefallen(
        self, tmp_path: Path
    ) -> None:
        """Uebersprungen heisst "nicht beurteilbar" und nicht "nein". Es als
        Nein zu verbuchen erfaende ein Urteil, das nie gefaellt wurde."""
        self.bericht(
            tmp_path,
            "a.json",
            [
                {
                    "stellung": 1.0,
                    "gates": {
                        "Da": {"bestanden": True, "uebersprungen": False},
                        "Weg": {"bestanden": False, "uebersprungen": True},
                    },
                }
            ],
        )

        geladen = lade(tmp_path)

        assert geladen == [{"Da": True}]

    def test_punkte_ohne_gates_werden_uebersprungen(self, tmp_path: Path) -> None:
        self.bericht(tmp_path, "a.json", [{"stellung": 1.0, "gates": {}}])

        assert lade(tmp_path) == []

    def test_varianten_berichte_werden_mitgelesen(self, tmp_path: Path) -> None:
        (tmp_path / "v.json").write_text(
            json.dumps(
                {
                    "varianten": {
                        "eins": [
                            {"gates": {"A": {"bestanden": True, "uebersprungen": False}}}
                        ],
                        "zwei": [
                            {
                                "gates": {
                                    "A": {"bestanden": False, "uebersprungen": False}
                                }
                            }
                        ],
                    }
                }
            )
        )

        assert lade(tmp_path) == [{"A": True}, {"A": False}]

    def test_eine_kaputte_datei_kippt_nicht_den_lauf(self, tmp_path: Path) -> None:
        (tmp_path / "kaputt.json").write_text("{kein JSON")
        self.bericht(
            tmp_path,
            "gut.json",
            [{"gates": {"A": {"bestanden": True, "uebersprungen": False}}}],
        )

        assert len(lade(tmp_path)) == 1

    def test_ohne_punkte_wird_nichts_behauptet(self) -> None:
        assert "nichts zu vergleichen" in Gatemuster().urteil()


class TestNurGemeinsameGates:
    def test_ein_gate_das_nicht_ueberall_gemessen_wurde_faellt_raus(self) -> None:
        """Wer zwei Gates ueber verschieden viele Punkte gegeneinanderlegt,
        vergleicht Teilmengen - und das Ergebnis haengt daran, welche."""
        muster = punkte({"A": True, "B": True}, {"A": False})

        assert muster.namen == ["A"]
