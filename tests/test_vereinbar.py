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

import pytest

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


class TestDritteSchwelle:
    """Die Erweiterung aus Befund 94.

    Sobald ueber **Mischungen** gerechnet wird, reichen zwei Schwellen nicht:
    Eine Beimischung senkt Rendite und Risiko zugleich, und ob dabei etwas
    uebrig bleibt, entscheidet sich an allen drei Grenzen.
    """

    def punkte(self):
        from research.vereinbar import Messpunkt

        # Der Bestand und ein Partner, der das schlechteste Jahr rettet und
        # dabei die Rendite unter die Schwelle drueckt - das gemessene Muster.
        return [
            Messpunkt(
                stellung=0.0,
                werte={"cagr": 13.47, "rueckgang": 10.64, "schlechtestes_jahr": -10.32},
            ),
            Messpunkt(
                stellung=0.5,
                werte={"cagr": 9.52, "rueckgang": 8.93, "schlechtestes_jahr": -5.08},
            ),
        ]

    def test_zwei_schwellen_wuerden_hier_einen_treffer_melden(self) -> None:
        """**Der Grund fuer die Erweiterung.**

        Bei Gewicht 0,5 sind Rueckgang und schlechtestes Jahr erfuellt - wer
        nur Rendite und Rueckgang prueft, sieht dort keinen Treffer, wer nur
        die beiden Risikoschwellen prueft, sieht einen. Erst alle drei
        zusammen sagen, was Sache ist.
        """
        from research.vereinbar import (
            RUECKGANG,
            SCHLECHTESTES_JAHR,
            Vereinbarkeit,
        )

        nur_risiko = Vereinbarkeit(
            regler="Verbund", punkte=self.punkte(),
            a=RUECKGANG, b=SCHLECHTESTES_JAHR,
        )

        assert len(nur_risiko.treffer) == 1
        assert nur_risiko.treffer[0].stellung == 0.5

    def test_mit_der_renditeschwelle_bleibt_nichts(self) -> None:
        from research.vereinbar import SCHLECHTESTES_JAHR, Vereinbarkeit

        alle = Vereinbarkeit(
            regler="Verbund", punkte=self.punkte(), weitere=[SCHLECHTESTES_JAHR]
        )

        assert len(alle.schwellen) == 3
        assert alle.treffer == []
        urteil = alle.urteil()
        assert "Schlechtestes Jahr >= -10" in urteil
        assert "haelt alle" in urteil

    def test_der_fehlbetrag_summiert_ueber_alle_drei(self) -> None:
        from research.vereinbar import SCHLECHTESTES_JAHR, Vereinbarkeit

        alle = Vereinbarkeit(
            regler="Verbund", punkte=self.punkte(), weitere=[SCHLECHTESTES_JAHR]
        )
        eng = alle.engste

        assert eng is not None
        # Bei 0,0 fehlen 1,53 Rendite und 0,32 schlechtestes Jahr = 1,85.
        # Bei 0,5 fehlen 5,48 Rendite und sonst nichts.
        assert eng.stellung == 0.0

    def test_ohne_weitere_bleibt_alles_wie_vorher(self) -> None:
        """Die Erweiterung darf den Reglerfall nicht anfassen."""
        from research.vereinbar import RENDITE, RUECKGANG, Vereinbarkeit

        zwei = Vereinbarkeit(regler="Vola-Ziel", punkte=self.punkte())

        assert zwei.schwellen == (RENDITE, RUECKGANG)
        assert zwei.treffer == []


class TestMischpunkte:
    def test_gemischt_werden_renditen_und_nicht_kurven(self) -> None:
        """**Zwei Kurven zu mitteln zaehlt den Zinseszins zweimal.**

        Ein Portfolio verteilt das Kapital und teilt sich die Renditen. Bei
        zwei identischen Kurven muss jede Mischung dieselbe Kurve ergeben -
        das ist die Probe darauf.
        """
        import numpy as np

        from research.vereinbar import mischpunkte

        kurve = np.cumprod(np.full(400, 1.002))
        punkte = mischpunkte(kurve, kurve, monate=93.0)

        assert len(punkte) == 5
        werte = {round(p.wert("cagr"), 6) for p in punkte}
        assert len(werte) == 1, "identische Beine muessen identisch mischen"

    def test_die_stellung_ist_das_gewicht_des_partners(self) -> None:
        import numpy as np

        from research.vereinbar import mischpunkte

        steigend = np.cumprod(np.full(400, 1.003))
        flach = np.ones(400)
        punkte = {p.stellung: p for p in mischpunkte(steigend, flach, monate=93.0)}

        assert punkte[0.0].wert("cagr") > punkte[1.0].wert("cagr")
        assert punkte[1.0].wert("cagr") == pytest.approx(0.0, abs=0.01)

    def test_ungleich_lange_kurven_liefern_nichts(self) -> None:
        import numpy as np

        from research.vereinbar import mischpunkte

        assert mischpunkte(np.ones(400), np.ones(300), monate=93.0) == []
        assert mischpunkte(np.ones(2), np.ones(2), monate=93.0) == []

    def test_die_kennzahlen_kommen_aus_einer_stelle(self) -> None:
        """Reglerpfad und Mischpfad duerfen nicht zwei Umsetzungen derselben
        drei Groessen haben."""
        import numpy as np

        from research.vereinbar import kennzahlen_der_kurve

        kurve = np.concatenate([np.linspace(1.0, 1.5, 200), np.linspace(1.5, 1.2, 200)])
        werte = kennzahlen_der_kurve(kurve, monate=93.0)

        assert set(werte) == {"cagr", "rueckgang", "schlechtestes_jahr"}
        assert werte["rueckgang"] == pytest.approx(20.0, abs=0.5)
        assert werte["cagr"] > 0

    def test_eine_entartete_kurve_liefert_nichts(self) -> None:
        import numpy as np

        from research.vereinbar import kennzahlen_der_kurve

        assert kennzahlen_der_kurve(np.array([1.0, 2.0]), monate=93.0) == {}
        assert kennzahlen_der_kurve(np.zeros(400), monate=93.0) == {}
