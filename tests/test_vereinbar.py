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
    AUS_DEM_GATE,
    RENDITE,
    RUECKGANG,
    SCHLECHTESTES_JAHR,
    Messpunkt,
    Schwelle,
    Vereinbarkeit,
    _werte_des_punktes,
    lade,
)


def punkt(stellung: float, cagr: float, rueckgang: float) -> Messpunkt:
    return Messpunkt(
        stellung=stellung, werte={"cagr": cagr, "rueckgang": rueckgang}
    )


def bericht(
    ordner: Path,
    *,
    regler: str = "Vola-Ziel",
    punkte: list[tuple],
    name: str,
    betriebspunkt: str | None = None,
) -> Path:
    datei = ordner / name
    datei.write_text(
        json.dumps(
            {
                "regler": regler,
                "betriebspunkt": betriebspunkt,
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

        geladen = lade(tmp_path).punkte

        assert len(geladen) == 1
        assert geladen[0].wert("cagr") == 13.47

    def test_ein_anderer_regler_wird_nicht_mitgenommen(self, tmp_path: Path) -> None:
        bericht(tmp_path, punkte=[(19.3, 13.47, 10.64)], name="vola.json")
        bericht(
            tmp_path, regler="Stop", punkte=[(4.0, 12.0, 9.0)], name="stop.json"
        )

        assert [p.stellung for p in lade(tmp_path).punkte] == [19.3]

    def test_eine_kaputte_datei_kippt_nicht_den_lauf(self, tmp_path: Path) -> None:
        (tmp_path / "kaputt.json").write_text("{kein JSON")
        bericht(tmp_path, punkte=[(19.3, 13.47, 10.64)], name="gut.json")

        assert len(lade(tmp_path).punkte) == 1

    def test_ein_leerer_ordner_gibt_nichts(self, tmp_path: Path) -> None:
        assert lade(tmp_path).punkte == []


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


class TestDerBetriebspunktIstEineEigeneAchse:
    """**Befund 280.** Befund 112 hat gemessen, dass der Betriebspunkt
    entscheidet, welche Gates halten. Eine Leiter aus Spot- und
    Perpetual-Stellungen ist deshalb keine Leiter: Bei gleicher Stellung
    ueberschreibt die eine die andere, und das Urteil stuende auf einer
    Mischung, die es so nie gab.
    """

    def test_ohne_frage_kommt_alles(self, tmp_path: Path) -> None:
        bericht(
            tmp_path, punkte=[(19.3, 13.47, 10.64)], name="a.json",
            betriebspunkt="Perpetual (Hebel 3, mit Funding)",
        )
        bericht(
            tmp_path, punkte=[(21.0, 14.39, 12.50)], name="b.json",
            betriebspunkt="Spot (kein Hebel, kein Funding)",
        )

        assert len(lade(tmp_path).punkte) == 2

    def test_wer_fragt_bekommt_nur_seinen_punkt(self, tmp_path: Path) -> None:
        bericht(
            tmp_path, punkte=[(19.3, 13.47, 10.64)], name="a.json",
            betriebspunkt="Perpetual (Hebel 3, mit Funding)",
        )
        bericht(
            tmp_path, punkte=[(21.0, 14.39, 12.50)], name="b.json",
            betriebspunkt="Spot (kein Hebel, kein Funding)",
        )

        vorrat = lade(tmp_path, betriebspunkt="Spot")

        assert [p.stellung for p in vorrat.punkte] == [21.0]
        assert vorrat.fremder_punkt == {"Perpetual (Hebel 3, mit Funding)": 1}

    def test_dieselbe_stellung_ueberschreibt_sich_nicht_mehr(
        self, tmp_path: Path
    ) -> None:
        """Der Kern: Zwei Punkte, dieselbe Stellung, verschiedene
        Handelsbedingungen - ohne Auswahl gewinnt der juengste Bericht, und
        das Urteil gaelte fuer keinen von beiden."""
        bericht(
            tmp_path, punkte=[(21.0, 14.39, 12.50)], name="a_perp.json",
            betriebspunkt="Perpetual (Hebel 3, mit Funding)",
        )
        bericht(
            tmp_path, punkte=[(21.0, 15.80, 11.90)], name="b_spot.json",
            betriebspunkt="Spot (kein Hebel, kein Funding)",
        )

        ohne = lade(tmp_path).punkte
        perp = lade(tmp_path, betriebspunkt="Perpetual").punkte

        assert len(ohne) == 1 and ohne[0].wert("cagr") == 15.80
        assert len(perp) == 1 and perp[0].wert("cagr") == 14.39

    def test_berichte_ohne_vermerk_werden_gemeldet_statt_geraten(
        self, tmp_path: Path
    ) -> None:
        """Vor Befund 242 stand der Punkt nicht im Bericht. Die Vorgabe von
        damals war der Perpetual-Punkt - aber eine Vorgabe ist keine Messung.
        """
        bericht(tmp_path, punkte=[(19.3, 13.47, 10.64)], name="alt.json")

        vorrat = lade(tmp_path, betriebspunkt="Spot")

        assert vorrat.punkte == []
        assert vorrat.ohne_vermerk == 1
        assert "vermerkten Betriebspunkt" in vorrat.hinweis()
        assert "keine Messung" in vorrat.hinweis()

    def test_die_schreibweise_der_klammer_zaehlt_nicht(self, tmp_path: Path) -> None:
        """Das erste Wort ist der Punkt, die Klammer seine Einzelheiten - ein
        Aufrufer soll die Zeichenkette nicht nachbauen muessen."""
        bericht(
            tmp_path, punkte=[(21.0, 15.80, 11.90)], name="a.json",
            betriebspunkt="Spot (kein Hebel, kein Funding)",
        )

        assert len(lade(tmp_path, betriebspunkt="Spot").punkte) == 1
        assert len(lade(tmp_path, betriebspunkt="spot").punkte) == 1


class TestDasUrteilNenntSeinenPunkt:
    def test_mit_vermerk_steht_er_im_satz(self) -> None:
        from research.vereinbar import Vereinbarkeit

        v = Vereinbarkeit(
            regler="Vola-Ziel",
            punkte=[punkt(*p) for p in GEMESSEN],
            betriebspunkt="Spot (kein Hebel, kein Funding)",
        )

        assert "Spot (kein Hebel, kein Funding)" in v.urteil()

    def test_ohne_vermerk_sagt_es_das(self) -> None:
        """Ein Urteil ohne Betriebspunkt gilt scheinbar immer - gemessen ist
        es aber unter bestimmten Handelsbedingungen."""
        from research.vereinbar import Vereinbarkeit

        v = Vereinbarkeit(regler="Vola-Ziel", punkte=[punkt(*p) for p in GEMESSEN])

        assert "steht nicht dabei" in v.urteil()
        assert v.punkt_name == "nicht vermerkt"


class TestDieBefehleFuehrenDenPunkt:
    """Ohne die beiden Flaggen waere die Frage am Spot-Punkt nicht stellbar."""

    def _quelle(self, name: str) -> str:
        import ast

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == name
        )
        return ast.unparse(knoten)

    def test_machbarkeit_kann_am_spot_punkt_messen(self) -> None:
        import ast

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "machbarkeit"
        )

        assert "spot" in {a.arg for a in knoten.args.args}
        assert "_ohne_hebel" in ast.unparse(knoten)

    def test_vereinbar_waehlt_den_punkt_aus(self) -> None:
        quelle = self._quelle("vereinbar")

        assert "betriebspunkt=gefragter_punkt" in quelle

    def test_und_meldet_was_dabei_wegfaellt(self) -> None:
        """Eine stille Auswahl waere hier besonders teuer: Das Urteil gilt
        sonst fuer weniger Stellungen, als es behauptet."""
        quelle = self._quelle("vereinbar")

        assert "vorrat.hinweis()" in quelle

    def test_beide_flaggen_zugleich_sind_keine_leiter(self) -> None:
        from typer.testing import CliRunner

        from cli import app

        ergebnis = CliRunner().invoke(app, ["vereinbar", "--spot", "--perpetual"])

        assert ergebnis.exit_code == 2
        assert "keine Leiter" in ergebnis.output

    def test_der_punkt_steht_in_der_ueberschrift(self) -> None:
        from typer.testing import CliRunner

        from cli import app

        ergebnis = CliRunner().invoke(app, ["vereinbar"])

        assert ergebnis.exit_code == 0
        assert "Betriebspunkt:" in ergebnis.output


class TestDieSpotLeiterIstGemessen:
    """**Befund 281.** Die Frage, die 280 offengelassen hat.

    Am Perpetual-Punkt haelt keine von zehn Stellungen beide Schwellen. Am
    Spot-Punkt halten drei von sechs - der behauptete Konflikt der beiden
    Schwellen ist eine Eigenschaft des Fundings, nicht der Strategie.

    **Gewonnen ist damit nichts.** Der Konflikt verschiebt sich nur: Dort
    uebernimmt das schlechteste Jahr die Rolle, die vorher der Rueckgang
    hatte, und keine Stellung kommt ueber 9 von 11.
    """

    def test_es_gibt_einen_spot_bericht(self) -> None:
        from research.vereinbar import lade

        vorrat = lade(Path("reports/machbarkeit"), betriebspunkt="Spot")

        assert vorrat.punkte, "Die Spot-Leiter ist seit Befund 281 gemessen"
        assert all(
            p.betriebspunkt and p.betriebspunkt.startswith("Spot")
            for p in vorrat.punkte
        )

    def test_und_dort_sind_die_schwellen_vereinbar(self) -> None:
        from research.vereinbar import Vereinbarkeit, lade

        vorrat = lade(Path("reports/machbarkeit"), betriebspunkt="Spot")
        lage = Vereinbarkeit(
            regler="Vola-Ziel", punkte=vorrat.punkte, betriebspunkt="Spot"
        )

        assert lage.treffer, "Am Spot-Punkt halten Stellungen beide Schwellen"
        assert "nicht nachgezogen" in lage.urteil(), (
            "Ein Treffer ohne diesen Zusatz liest sich als Empfehlung"
        )

    def test_das_register_nennt_beide_punkte(self) -> None:
        """Die Entscheidung gehoert dem Nutzer - und sie stand bis 281 mit
        einer Messung vom anderen Betriebspunkt da."""
        from research.stand import ENTSCHEIDUNGEN

        eintrag = next(
            e for e in ENTSCHEIDUNGEN if "Mindestrendite" in e.frage
        )

        assert "Perpetual-Punkt" in eintrag.zahl
        assert "Spot" in eintrag.zahl
        assert "Geloest ist nichts" in eintrag.zahl


class TestEinFehlenderWertIstKeineGerisseneSchwelle:
    """**Befund 309.** ``cli vereinbar --spot --mit-jahr`` meldete an allen
    sechs Stellungen *"Schlechtestes Jahr fehlt"* und schloss daraus
    *"nicht zugleich erfuellbar"*. Keiner der sechs Berichte traegt diesen
    Wert: Die Kapitalkurven sind zu kurz fuer ein Jahresfenster, und
    ``kennzahlen_der_kurve`` laesst den Schluessel dann weg.

    "Nicht gemessen" und "gerissen" sind zwei verschiedene Auskuenfte - die
    eine sagt etwas ueber den Kandidaten, die andere ueber die Akte.
    """

    def _mit_dritter(self, *punkte: Messpunkt) -> Vereinbarkeit:
        return Vereinbarkeit(
            regler="Vola-Ziel",
            punkte=list(punkte),
            weitere=[SCHLECHTESTES_JAHR],
            betriebspunkt="spot",
        )

    def test_die_schwelle_sagt_es_selbst(self) -> None:
        assert SCHLECHTESTES_JAHR.beurteile(None) == "Schlechtestes Jahr nicht gemessen"
        assert SCHLECHTESTES_JAHR.beurteile(-20.0) == "Schlechtestes Jahr fehlt"
        assert SCHLECHTESTES_JAHR.beurteile(-5.0) is None

    def test_eine_obergrenze_reisst_und_fehlt_nicht(self) -> None:
        assert RUECKGANG.beurteile(20.0) == "Rueckgang reisst"
        assert RUECKGANG.beurteile(None) == "Rueckgang nicht gemessen"

    def test_die_tabelle_unterscheidet_beides(self) -> None:
        text = self._mit_dritter(punkt(21, 15.3, 11.66)).tabelle()

        assert "Schlechtestes Jahr nicht gemessen" in text
        assert "Schlechtestes Jahr fehlt" not in text

    def test_das_urteil_verweigert_sich(self) -> None:
        """**Der Kern.** Ein Nein ueber eine Zahl, die es nirgends gibt,
        waere eine Behauptung ueber die Akte, nicht ueber den Kandidaten."""
        text = self._mit_dritter(
            punkt(21, 15.3, 11.66), punkt(22, 16.17, 11.85)
        ).urteil()

        assert "Kein Urteil ueber Schlechtestes Jahr" in text
        assert "nicht zugleich erfuellbar" not in text

    def test_und_sagt_trotzdem_was_messbar_ist(self) -> None:
        """Die Verweigerung darf nicht die Auskunft mitnehmen, die es gibt."""
        text = self._mit_dritter(
            punkt(21, 15.3, 11.66), punkt(22, 16.17, 11.85)
        ).urteil()

        assert "Rendite >= 15 und Rueckgang <= 12 sind vereinbar" in text

    def test_mit_werten_urteilt_sie_wieder(self) -> None:
        """Die Verweigerung haengt am fehlenden Wert, nicht an der dritten
        Schwelle als solcher."""
        gemessen = Messpunkt(
            stellung=21,
            werte={"cagr": 15.3, "rueckgang": 11.66, "schlechtestes_jahr": -20.0},
        )
        text = self._mit_dritter(gemessen).urteil()

        assert "Kein Urteil" not in text
        assert "nicht zugleich erfuellbar" in text

    def test_ungemessen_nennt_genau_die_leeren(self) -> None:
        gemischt = Vereinbarkeit(
            regler="Vola-Ziel",
            punkte=[punkt(21, 15.3, 11.66)],
            weitere=[SCHLECHTESTES_JAHR],
        )

        assert gemischt.ungemessen == (SCHLECHTESTES_JAHR,)

    def test_ein_einziger_wert_reicht_gegen_die_verweigerung(self) -> None:
        """``ungemessen`` heisst **kein einziger** Punkt - sonst wuerde eine
        halb gefuellte Spalte das Urteil kippen."""
        halb = Vereinbarkeit(
            regler="Vola-Ziel",
            punkte=[
                punkt(21, 15.3, 11.66),
                Messpunkt(
                    stellung=22,
                    werte={
                        "cagr": 16.17, "rueckgang": 11.85,
                        "schlechtestes_jahr": -5.0,
                    },
                ),
            ],
            weitere=[SCHLECHTESTES_JAHR],
        )

        assert halb.ungemessen == ()
        assert "Kein Urteil" not in halb.urteil()

    def test_ein_treffer_braucht_weiter_alle_werte(self) -> None:
        """``treffer`` zaehlt einen Punkt ohne Wert nicht mit - ein fehlender
        Wert erfuellt nichts, auch wenn er nichts reisst."""
        ohne = self._mit_dritter(punkt(21, 15.3, 11.66))

        assert ohne.treffer == []


class TestDerWertStandInDerselbenDatei:
    """**Befund 310.** Befund 309 hat ``nan`` richtig als "nicht gemessen"
    gemeldet - und die Ursache **geraten**: die Kapitalkurve sei zu kurz fuer
    ein Jahresfenster.

    Sie ist es nicht. ``kennzahlen`` traegt trades, cagr, rueckgang,
    sharpe_je_trade, schiefe und woelbung; das schlechteste Jahr steht in
    derselben Datei unter ``gates['Schlechtestes Jahr']['wert']``, mit
    Schwelle und Urteil daneben. Gesucht wurde an der falschen Stelle.
    """

    def test_der_wert_kommt_aus_dem_gate(self) -> None:
        werte = _werte_des_punktes(
            {
                "stellung": 21,
                "kennzahlen": {"cagr": 15.3, "rueckgang": 11.66},
                "gates": {
                    "Schlechtestes Jahr": {
                        "bestanden": False, "wert": -11.38, "schwelle": -10.0
                    }
                },
            }
        )

        assert werte["schlechtestes_jahr"] == pytest.approx(-11.38)

    def test_die_kennzahlen_bleiben_die_quelle(self) -> None:
        """Wo beide etwas sagen, gewinnt ``kennzahlen`` - heute tritt der
        Fall nicht ein, aber die Regel soll feststehen und nicht vom Zufall
        der Reihenfolge abhaengen."""
        werte = _werte_des_punktes(
            {
                "kennzahlen": {"cagr": 15.3, "schlechtestes_jahr": -5.0},
                "gates": {"Schlechtestes Jahr": {"wert": -11.38}},
            }
        )

        assert werte["schlechtestes_jahr"] == pytest.approx(-5.0)

    def test_ohne_gate_bleibt_der_wert_weg(self) -> None:
        """Und dann greift die Verweigerung aus Befund 309 - nicht ein
        stillschweigender Ersatzwert."""
        werte = _werte_des_punktes({"kennzahlen": {"cagr": 15.3}})

        assert "schlechtestes_jahr" not in werte

    def test_ein_gate_ohne_wert_ebenso(self) -> None:
        werte = _werte_des_punktes(
            {
                "kennzahlen": {"cagr": 15.3},
                "gates": {"Schlechtestes Jahr": {"bestanden": False}},
            }
        )

        assert "schlechtestes_jahr" not in werte

    def test_nur_diese_eine_kennzahl_kommt_von_dort(self) -> None:
        """Die Liste steht ausgeschrieben da. Alles aus den Gates zu ziehen
        waere bequem und machte aus zwei Quellen eine Mischung."""
        assert AUS_DEM_GATE == {"schlechtestes_jahr": "Schlechtestes Jahr"}

    def test_am_echten_bericht(self) -> None:
        """Gegen die Datei, die den Befund ausgeloest hat - sechs Stellungen
        am Spot-Punkt, und jede traegt jetzt ihr schlechtestes Jahr."""
        vorrat = lade(Path("reports/machbarkeit"), betriebspunkt="spot")
        if not vorrat.punkte:
            pytest.skip("keine Spot-Berichte im Behaelter")

        fehlend = [
            p.stellung for p in vorrat.punkte if p.wert("schlechtestes_jahr") is None
        ]
        assert fehlend == [], f"ohne schlechtestes Jahr: {fehlend}"
