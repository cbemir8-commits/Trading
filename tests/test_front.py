"""Alles Gemessene gegen die Linie, die es reissen muesste.

Sechzehn geschlossene Richtungen sind sechzehn Einzelfaelle. Die Aussage, auf
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


class TestGemeinsameHuerde:
    """Alle Punkte gegen **dieselbe** Huerde - sonst vergleicht man Massstaebe.

    Die Berichte reichen von 102 bis 162 Versuchen. Ein Punkt vom 8. August
    stand gegen eine deutlich mildere Schwelle als einer vom 14., und die
    aelteren sehen deshalb systematisch besser aus. Genau dieser Fehler wurde
    fuer die Bestenliste in Befund 50 behoben - in den Berichten steckte er
    weiter, und diese Auswertung hat sie nebeneinandergelegt.

    ``test_ein_alter_punkt_wird_auf_heute_geholt`` ist der Test dazu.
    """

    def punkt_mit_form(
        self, tmp: Path, *, versuche: int, name: str = "a.json"
    ) -> Path:
        datei = tmp / name
        datei.write_text(
            json.dumps(
                {
                    "regler": "Vola-Ziel",
                    "versuche": versuche,
                    "punkte": [punkt(schiefe=3.4, woelbung=16.0, dsr=0.86)],
                }
            )
        )
        return datei

    def test_der_versuchsstand_kommt_aus_dem_bericht(self, tmp_path: Path) -> None:
        self.punkt_mit_form(tmp_path, versuche=112)

        assert lade(tmp_path)[0].versuche == 112

    def test_ein_alter_punkt_wird_auf_heute_geholt(self, tmp_path: Path) -> None:
        """**Der Test, der diese Klasse traegt.**

        Derselbe Punkt gegen mehr Versuche gerechnet muss schlechter
        dastehen - sonst ist die Umrechnung wirkungslos, und die Auswertung
        vergleicht weiter Massstaebe.
        """
        self.punkt_mit_form(tmp_path, versuche=112)
        geladen = lade(tmp_path)[0]

        assert geladen.umrechenbar
        frueh = geladen.dsr_bei(112)
        spaet = geladen.dsr_bei(166)
        assert spaet < frueh, f"{spaet:.4f} muesste unter {frueh:.4f} liegen"

    def test_ohne_form_bleibt_der_wert_des_laufs_stehen(self, tmp_path: Path) -> None:
        """Eine Umrechnung zu erfinden waere schlimmer als eine Luecke - aber
        die Luecke muss sichtbar sein."""
        bericht(tmp_path, punkte=[punkt(dsr=0.86)])
        geladen = lade(tmp_path)[0]

        assert not geladen.umrechenbar
        assert geladen.dsr_bei(999) == 0.86

    def test_unvergleichbare_punkte_sind_abrufbar(self, tmp_path: Path) -> None:
        self.punkt_mit_form(tmp_path, versuche=112, name="mit.json")
        bericht(tmp_path, punkte=[punkt(stellung=8.0, dsr=0.5)], name="ohne.json")
        front = Front(punkte=lade(tmp_path), versuche=166)

        assert len(front.unvergleichbar) == 1
        assert "!" in front.tabelle()

    def test_das_urteil_nennt_den_stand_auf_den_gerechnet_wurde(
        self, tmp_path: Path
    ) -> None:
        """Sonst liest sich die Zahl, als waere sie so gemessen worden."""
        self.punkt_mit_form(tmp_path, versuche=112)
        front = Front(punkte=lade(tmp_path), versuche=166)

        urteil = front.urteil()
        assert "heutigen Stand von 166 Versuchen" in urteil
        assert "nicht auf den des jeweiligen Laufs" in urteil

    def test_bestanden_zaehlt_den_umgerechneten_wert(self, tmp_path: Path) -> None:
        """Ein Punkt, der bei wenigen Versuchen ueber der Schwelle lag, darf
        heute nicht mehr als bestanden gelten."""
        datei = tmp_path / "a.json"
        datei.write_text(
            json.dumps(
                {
                    "regler": "Vola-Ziel",
                    "versuche": 20,
                    "punkte": [punkt(schiefe=3.4, woelbung=16.0, dsr=0.97)],
                }
            )
        )
        front = Front(punkte=lade(tmp_path), versuche=5000)

        assert front.punkte[0].dsr == 0.97, "Der gespeicherte Wert bleibt"
        assert front.bestanden == [], "Auf heute gerechnet reicht er nicht mehr"


class TestEntdoppelt:
    """Befund 150: Dieselbe Reglerstellung stand mehrfach in der Liste.

    Statistisch harmlos - die Wiederholungen tragen identische Kennzahlen und
    unterscheiden sich nur im Versuchsstand ihres Laufs. In der Anzeige nicht:
    Von zwoelf Zeilen waren sechs Dubletten, und **24 von 30 Stellungen waren
    unsichtbar**, darunter ganze Regler.
    """

    def _punkt(self, name: str, versuche: int, sharpe: float = 0.26):
        from research.front import Messpunkt
        from research.suchbudget import Kandidat

        regler, stellung = name.rsplit(" ", 1)
        return Messpunkt(
            regler=regler, stellung=float(stellung),
            kandidat=Kandidat(name=name, trades=152, sharpe_je_trade=sharpe),
            genaehert=False, dsr=0.8, versuche=versuche,
        )

    def test_dieselbe_stellung_bleibt_einmal(self) -> None:
        from research.front import entdoppelt

        uebrig = entdoppelt([
            self._punkt("Vola-Ziel 20.5", 162),
            self._punkt("Vola-Ziel 20.5", 189),
            self._punkt("Vola-Ziel 20.5", 198),
        ])

        assert len(uebrig) == 1

    def test_behalten_wird_die_haerteste_huerde(self) -> None:
        """Die einzige Richtung, in die eine solche Wahl fallen darf."""
        from research.front import entdoppelt

        (uebrig,) = entdoppelt([
            self._punkt("Vola-Ziel 20.5", 198),
            self._punkt("Vola-Ziel 20.5", 162),
        ])

        assert uebrig.versuche == 198

    def test_verschiedene_stellungen_bleiben_alle(self) -> None:
        from research.front import entdoppelt

        uebrig = entdoppelt([
            self._punkt("Vola-Ziel 20.5", 198),
            self._punkt("Vola-Ziel 22", 198),
            self._punkt("Abkuehlung 3", 198),
        ])

        assert len(uebrig) == 3

    def test_die_reihenfolge_haengt_am_ersten_auftreten(self) -> None:
        """Sonst haengt die Ausgabe an der Sortierung eines dict."""
        from research.front import entdoppelt

        uebrig = entdoppelt([
            self._punkt("Zweiter 2", 162),
            self._punkt("Erster 1", 198),
            self._punkt("Zweiter 2", 198),
        ])

        assert [p.name for p in uebrig] == ["Zweiter 2", "Erster 1"]

    def test_eine_leere_liste_bleibt_leer(self) -> None:
        from research.front import entdoppelt

        assert entdoppelt([]) == []

    def test_die_tabelle_zeigt_verschiedene_stellungen(self) -> None:
        """**Der eigentliche Schaden war die Verdraengung.**

        Zwoelf Zeilen, und bei Dubletten standen darin sechs Stellungen. Wer
        pruefen will, ob *kein* Punkt der Familie ueber der Linie liegt, sieht
        dann vier Fuenftel der Familie nicht.
        """
        from research.front import Front

        punkte = [
            self._punkt(f"Vola-Ziel {i}", 198, sharpe=0.26 + i / 1000)
            for i in range(4)
        ]
        front = Front(punkte=punkte + punkte, versuche=198)

        zeilen = [z for z in front.tabelle().splitlines()[1:] if z.strip()]
        namen = [z.split("  ")[0].strip() for z in zeilen]

        assert len(namen) == len(set(namen)), f"Dubletten in der Tabelle: {namen}"
