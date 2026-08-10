"""Alles Gemessene gegen die Linie, die es reissen muesste.

Vierzehn geschlossene Richtungen sind vierzehn Einzelfaelle. Die Aussage, auf
die es ankommt, ist eine andere: **Kein Punkt dieser Regelfamilie erreicht die
Schwelle** - und die steht schon in den Machbarkeitsberichten, sie musste nur
zusammengelegt werden.

Der Test, der die Datei traegt, ist ``test_das_urteil_ist_die_messung``: Es
gibt hier zwei Zahlen je Punkt, und nur eine ist das Urteil. Der gemessene
Deflated Sharpe kommt aus dem Gate, das mit der wirklichen Verteilung gerechnet
hat. Die Grenzlinie daneben uebersetzt den Abstand in Sharpe-Einheiten und
braucht dafuer die Form - fehlt sie im Bericht, ist die Uebersetzung ungenau.
Wer die beiden vertauscht, faellt genau dort herein.
"""

from __future__ import annotations

import json
from pathlib import Path

from research.front import Front, lade
from research.suchbudget import ZIEL


def bericht(
    tmp: Path,
    *,
    regler: str = "Stop",
    punkte: list[dict],
    name: str = "a.json",
) -> Path:
    datei = tmp / name
    datei.write_text(json.dumps({"regler": regler, "punkte": punkte}))
    return datei


def punkt(
    *,
    stellung: float = 4.0,
    trades: float = 152,
    sharpe: float = 0.26,
    dsr: float | None = 0.81,
    schiefe: float | None = None,
    woelbung: float | None = None,
) -> dict:
    kennzahlen = {"trades": trades, "sharpe_je_trade": sharpe}
    if schiefe is not None:
        kennzahlen["schiefe"] = schiefe
    if woelbung is not None:
        kennzahlen["woelbung"] = woelbung
    gates = {}
    if dsr is not None:
        gates["Deflated Sharpe"] = {
            "bestanden": dsr >= ZIEL,
            "wert": dsr,
            "schwelle": ZIEL,
            "uebersprungen": False,
        }
    return {"stellung": stellung, "kennzahlen": kennzahlen, "gates": gates}


class TestLaden:
    def test_punkte_ohne_qualitaet_werden_uebersprungen(self, tmp_path: Path) -> None:
        """Ein Punkt ohne Sharpe je Trade laesst sich nicht einordnen. Eine
        erfundene Zahl waere schlimmer als ein fehlender Punkt."""
        bericht(
            tmp_path,
            punkte=[
                punkt(),
                {"stellung": 8.0, "kennzahlen": {"trades": 100.0}, "gates": {}},
            ],
        )

        assert len(lade(tmp_path)) == 1

    def test_der_gemessene_wert_kommt_aus_dem_bericht(self, tmp_path: Path) -> None:
        bericht(tmp_path, punkte=[punkt(dsr=0.734)])

        assert lade(tmp_path)[0].dsr == 0.734

    def test_ein_uebersprungenes_gate_liefert_keine_zahl(self, tmp_path: Path) -> None:
        """Uebersprungen heisst "nicht beurteilbar" und nicht "null"."""
        daten = punkt()
        daten["gates"]["Deflated Sharpe"]["uebersprungen"] = True
        bericht(tmp_path, punkte=[daten])

        assert lade(tmp_path)[0].dsr is None

    def test_fehlende_form_wird_markiert(self, tmp_path: Path) -> None:
        bericht(
            tmp_path,
            punkte=[punkt(), punkt(stellung=8.0, schiefe=3.4, woelbung=16.0)],
        )
        geladen = sorted(lade(tmp_path), key=lambda p: p.stellung)

        assert geladen[0].genaehert
        assert not geladen[1].genaehert
        assert geladen[1].kandidat.schiefe == 3.4

    def test_kaputte_datei_kippt_nicht_den_lauf(self, tmp_path: Path) -> None:
        (tmp_path / "kaputt.json").write_text("{kein JSON")
        bericht(tmp_path, punkte=[punkt()], name="gut.json")

        assert len(lade(tmp_path)) == 1

    def test_leerer_ordner_gibt_nichts(self, tmp_path: Path) -> None:
        assert lade(tmp_path) == []

    def test_mehrere_berichte_werden_zusammengelegt(self, tmp_path: Path) -> None:
        bericht(tmp_path, regler="Stop", punkte=[punkt()], name="a.json")
        bericht(
            tmp_path, regler="Abkuehlung", punkte=[punkt(stellung=3.0)], name="b.json"
        )

        assert {p.regler for p in lade(tmp_path)} == {"Stop", "Abkuehlung"}


class TestUrteil:
    def test_das_urteil_ist_die_messung(self, tmp_path: Path) -> None:
        """**Zwei Zahlen je Punkt, und nur eine ist das Urteil.**

        Hier steht ein Punkt, den die Grenzlinie durchwinken wuerde - sein
        Sharpe je Trade liegt ueber dem noetigen -, dessen **gemessener**
        Deflated Sharpe aber unter der Schwelle liegt. Das kann vorkommen, weil
        die Linie ohne die Form der Verteilung gerechnet wird und die Messung
        mit ihr.

        Das Gate hat recht, nicht die Uebersetzung.
        """
        bericht(tmp_path, punkte=[punkt(sharpe=0.90, dsr=0.62)])
        front = Front(punkte=lade(tmp_path), versuche=157)

        nah = front.naechster
        assert nah is not None and nah.faktor is not None and nah.faktor < 1.0, (
            "Der Punkt muss die Linie reissen, sonst zeigt der Test nichts"
        )
        assert front.bestanden == []
        assert "erreicht die Schwelle" in front.urteil()

    def test_ein_bestandener_punkt_wird_als_befund_gemeldet(
        self, tmp_path: Path
    ) -> None:
        """Und ausdruecklich nicht als Zulassung: Der Deflated Sharpe ist
        eines von elf Gates."""
        bericht(tmp_path, punkte=[punkt(dsr=0.97)])
        front = Front(punkte=lade(tmp_path), versuche=157)

        assert len(front.bestanden) == 1
        assert "Befund, keine Zulassung" in front.urteil()
        assert "elf Gates" in front.urteil()

    def test_der_hoechste_gemessene_wert_steht_im_urteil(self, tmp_path: Path) -> None:
        bericht(
            tmp_path,
            punkte=[punkt(dsr=0.42), punkt(stellung=8.0, dsr=0.851), punkt(
                stellung=12.0, dsr=0.19
            )],
        )
        front = Front(punkte=lade(tmp_path), versuche=157)

        assert front.bester is not None
        assert front.bester.dsr == 0.851
        assert "0.851" in front.urteil()

    def test_ohne_punkte_wird_nichts_behauptet(self) -> None:
        front = Front(punkte=[], versuche=157)

        assert "Keine einordenbaren Messpunkte" in front.urteil()
        assert front.bester is None

    def test_die_tabelle_zeigt_beide_zahlen(self, tmp_path: Path) -> None:
        bericht(tmp_path, punkte=[punkt(dsr=0.808)])
        front = Front(punkte=lade(tmp_path), versuche=157)
        text = front.tabelle()

        assert "0.808" in text
        assert "0.2600" in text
        assert "~" in text, "Ein genaeherter Punkt muss als solcher zu sehen sein"


class TestMehrVersuche:
    def test_die_linie_steigt_mit_den_versuchen(self, tmp_path: Path) -> None:
        """Der Preis des Suchens, an derselben Stelle sichtbar: Dieselben
        Messpunkte ruecken weiter weg, ohne dass sich an ihnen etwas aendert."""
        bericht(tmp_path, punkte=[punkt()])
        punkte = lade(tmp_path)

        frueh = Front(punkte=punkte, versuche=100).naechster
        spaet = Front(punkte=punkte, versuche=400).naechster

        assert frueh is not None and spaet is not None
        assert spaet.noetig > frueh.noetig
