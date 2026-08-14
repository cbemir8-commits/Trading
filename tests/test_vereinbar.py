"""Zwei Schwellen, eine Reglerkurve - und die Grenze dessen, was gesagt wird.

Zwei Tests tragen diese Datei:

``test_ein_treffer_ist_keine_empfehlung`` - Der ganze Sinn des Moduls. Ein
Punkt, der beide Schwellen haelt, ist ein Befund ueber die **Schwellen**. Wer
daraus einen Betriebspunkt macht, hat den Kandidaten an die Gates angepasst -
und ``research/seeds.py`` warnt genau davor, mit Namen und Zahl.

``test_der_juengste_bericht_gewinnt`` - Die Aufwaermphase des Compilers wurde
einmal korrigiert. Berichte davor tragen andere Zahlen fuer dieselbe Stellung.
Sie zusammenzulegen ergaebe eine Kurve aus zwei Messstaenden, und die
Zwischenwerte darin waeren reine Erfindung.
"""

from __future__ import annotations

import json
from pathlib import Path

from research.vereinbar import (
    RENDITE,
    RUECKGANG,
    Messpunkt,
    Schwelle,
    Vereinbarkeit,
    lade,
)


def punkt(stellung: float, cagr: float, rueckgang: float) -> Messpunkt:
    return Messpunkt(
        stellung=stellung, werte={"cagr": cagr, "rueckgang": rueckgang}
    )


def bericht(
    ordner: Path, *, regler: str = "Vola-Ziel", punkte: list[tuple], name: str
) -> Path:
    datei = ordner / name
    datei.write_text(
        json.dumps(
            {
                "regler": regler,
                "punkte": [
                    {
                        "stellung": s,
                        "kennzahlen": {"cagr": c, "rueckgang": r},
                    }
                    for s, c, r in punkte
                ],
            }
        )
    )
    return datei


#: Die gemessene Kurve des Spitzenkandidaten (Bericht vom 8. August, Lauf 3).
GEMESSEN = [
    (14.0, 9.47, 7.75),
    (16.0, 10.98, 8.46),
    (19.3, 13.47, 10.64),
    (22.0, 15.16, 12.82),
    (25.0, 17.23, 14.78),
]


class TestSchwelle:
    def test_mindestens_und_hoechstens(self) -> None:
        assert RENDITE.erfuellt(15.0) and RENDITE.erfuellt(16.0)
        assert not RENDITE.erfuellt(14.99)
        assert RUECKGANG.erfuellt(12.0) and RUECKGANG.erfuellt(10.0)
        assert not RUECKGANG.erfuellt(12.01)

    def test_der_abstand_zeigt_die_richtung(self) -> None:
        assert RENDITE.abstand(13.0) < 0, "Rendite fehlt - negativ"
        assert RUECKGANG.abstand(14.0) < 0, "Rueckgang gerissen - negativ"
        assert RUECKGANG.abstand(10.0) > 0

    def test_ein_fehlender_wert_erfuellt_nichts(self) -> None:
        assert not RENDITE.erfuellt(None)
        assert RENDITE.abstand(None) is None


class TestUrteil:
    def test_die_gemessene_kurve_haelt_beide_nicht(self) -> None:
        """Der Fall, um den es geht - mit den echten Zahlen."""
        v = Vereinbarkeit(
            regler="Vola-Ziel", punkte=[punkt(*p) for p in GEMESSEN]
        )

        assert v.treffer == []
        assert "nicht zugleich" in v.urteil()
        assert "liegt beim Nutzer" in v.urteil()

    def test_die_luecke_wird_benannt(self) -> None:
        """Zwischen 19,3 und 22 ist nichts gemessen - und genau dort
        entscheidet sich die Frage, wenn sie sich entscheidet."""
        v = Vereinbarkeit(
            regler="Vola-Ziel", punkte=[punkt(*p) for p in GEMESSEN]
        )

        luecke = v.luecke
        assert luecke is not None
        assert (luecke[0].stellung, luecke[1].stellung) == (19.3, 22.0)
        assert "zwischen 19.3 und 22" in v.urteil()

    def test_ein_treffer_ist_keine_empfehlung(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Ein Punkt, der beide Schwellen haelt, sagt etwas ueber die Schwellen -
        nicht, dass der Kandidat dorthin gestellt gehoert. seeds.py haelt zum
        Vola-Ziel fest, dass der Wert *nicht* nachgezogen wird, nur weil dort
        mehr Gates bestuenden. Das Urteil muss das mitsagen, sonst liest es
        sich beim naechsten Mal als Handlungsanweisung.
        """
        v = Vereinbarkeit(
            regler="Vola-Ziel",
            punkte=[punkt(19.3, 13.47, 10.64), punkt(21.0, 15.10, 11.80)],
        )

        assert len(v.treffer) == 1
        urteil = v.urteil()
        assert "vereinbar" in urteil
        assert "nicht nachgezogen" in urteil, (
            "Ein Treffer ohne diesen Zusatz liest sich als Empfehlung"
        )
        assert "uebrigen Gates bleiben ohnehin offen" in urteil

    def test_der_engste_punkt_wird_beziffert(self) -> None:
        v = Vereinbarkeit(
            regler="Vola-Ziel", punkte=[punkt(*p) for p in GEMESSEN]
        )

        eng = v.engste
        assert eng is not None
        assert eng.stellung == 22.0, (
            "22,0 fehlt 0,82 Rueckgangspunkte; 19,3 fehlen 1,53 Renditepunkte"
        )

    def test_ohne_punkte_wird_nichts_behauptet(self) -> None:
        assert "nichts zu entscheiden" in Vereinbarkeit(regler="Vola-Ziel").urteil()

    def test_die_tabelle_nennt_je_zeile_den_grund(self) -> None:
        v = Vereinbarkeit(
            regler="Vola-Ziel", punkte=[punkt(*p) for p in GEMESSEN]
        )
        text = v.tabelle()

        assert "Rendite fehlt" in text
        assert "Rueckgang reisst" in text

    def test_andere_schwellen_lassen_sich_einsetzen(self) -> None:
        """Das Modul kennt keine Sonderrolle fuer 15 und 12 - es beantwortet
        die Frage fuer jedes Paar, das jemand hineingibt."""
        v = Vereinbarkeit(
            regler="Vola-Ziel",
            punkte=[punkt(*p) for p in GEMESSEN],
            a=Schwelle("Rendite", "cagr", 10.0, mindestens=True),
            b=RUECKGANG,
        )

        assert [p.stellung for p in v.treffer] == [16.0, 19.3]


class TestLaden:
    def test_der_juengste_bericht_gewinnt(self, tmp_path: Path) -> None:
        """**Der zweite tragende Test.**

        Dieselbe Stellung aus zwei Messstaenden ergibt keine Kurve, sondern
        ein Gemisch. Der juengste Bericht gilt.
        """
        bericht(tmp_path, punkte=[(19.3, 13.17, 9.74)], name="2026-08-08_a.json")
        bericht(tmp_path, punkte=[(19.3, 13.47, 10.64)], name="2026-08-08_b.json")

        geladen = lade(tmp_path)

        assert len(geladen) == 1
        assert geladen[0].wert("cagr") == 13.47

    def test_ein_anderer_regler_wird_nicht_mitgenommen(self, tmp_path: Path) -> None:
        bericht(tmp_path, punkte=[(19.3, 13.47, 10.64)], name="vola.json")
        bericht(
            tmp_path, regler="Stop", punkte=[(4.0, 12.0, 9.0)], name="stop.json"
        )

        assert [p.stellung for p in lade(tmp_path)] == [19.3]

    def test_eine_kaputte_datei_kippt_nicht_den_lauf(self, tmp_path: Path) -> None:
        (tmp_path / "kaputt.json").write_text("{kein JSON")
        bericht(tmp_path, punkte=[(19.3, 13.47, 10.64)], name="gut.json")

        assert len(lade(tmp_path)) == 1

    def test_ein_leerer_ordner_gibt_nichts(self, tmp_path: Path) -> None:
        assert lade(tmp_path) == []
