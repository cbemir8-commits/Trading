"""Was ein abgebrochener Lauf hinterlaesst - Befund 299.

``cli vorratsdecke -i 15`` braucht gemessene 3,1 Stunden (Befund 298). Beim
ersten Versuch ist der Rechner nach drei von neununddreissig Genomen neu
gestartet worden - zwoelf Minuten Rechenzeit, und kein Byte davon auf der
Platte.

Diese Tests halten die drei Eigenschaften fest, auf die es dabei ankommt:
der Kopf steht **vor** der ersten Messung, jede Zeile ist nach dem Schreiben
auf der Platte, und eine mitten im Satz abgeschnittene Datei laesst sich
trotzdem lesen.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from research.zwischenstand import Zwischenstand, lies, neu


def _stand(tmp_path: Path, **bedingungen: object) -> Zwischenstand:
    return Zwischenstand(
        pfad=tmp_path / "lauf.jsonl", bedingungen=dict(bedingungen)
    )


class TestDerKopfStehtZuerst:
    def test_beginne_schreibt_den_kopf_sofort(self, tmp_path: Path) -> None:
        """**Der eigentliche Punkt.** Ein Kopf am Ende waere genau bei dem
        Lauf nicht da, fuer den es dieses Modul gibt."""
        stand = _stand(tmp_path, intervall="15m", versuchsstand=203)
        stand.beginne()

        kopf, messungen = lies(stand.pfad)
        assert kopf["intervall"] == "15m"
        assert kopf["versuchsstand"] == 203
        assert messungen == ()

    def test_der_kopf_traegt_einen_zeitpunkt(self, tmp_path: Path) -> None:
        stand = _stand(tmp_path)
        stand.beginne()

        kopf, _ = lies(stand.pfad)
        assert kopf["begonnen"].startswith("20")

    def test_ohne_beginne_wird_nichts_geschrieben(self, tmp_path: Path) -> None:
        """Zeilen ohne Kopf waeren Zahlen ohne Herkunft - dann lieber ein
        lauter Fehler als eine Datei, die niemand einordnen kann."""
        stand = _stand(tmp_path)
        with pytest.raises(RuntimeError, match="beginne"):
            stand.halte_fest(regel="Irgendeine", guete=1.0)
        assert not stand.pfad.exists()

    def test_die_bedingungen_landen_alle_im_kopf(self, tmp_path: Path) -> None:
        stand = _stand(
            tmp_path, maerkte=["BTCUSD_BITSTAMP"], genome=39, betriebspunkt="Spot"
        )
        stand.beginne()

        kopf, _ = lies(stand.pfad)
        assert kopf["maerkte"] == ["BTCUSD_BITSTAMP"]
        assert kopf["genome"] == 39
        assert kopf["betriebspunkt"] == "Spot"

    def test_die_erwartete_zahl_macht_den_abbruch_sichtbar(
        self, tmp_path: Path
    ) -> None:
        """Woran man einem Protokoll ansieht, dass es abgebrochen ist: Im
        Kopf steht, wie viele Messungen erwartet wurden.

        Eine Schlusszeile koennte das nicht leisten - der abgebrochene Lauf
        kommt nie dazu, sie zu schreiben.
        """
        stand = _stand(tmp_path, genome=39)
        stand.beginne()
        for i in range(3):
            stand.halte_fest(regel=f"Regel {i}", guete=0.1 * i)

        kopf, messungen = lies(stand.pfad)
        assert len(messungen) < kopf["genome"]


class TestJedeZeileSofort:
    def test_eine_messung_steht_vor_dem_naechsten_aufruf_auf_der_platte(
        self, tmp_path: Path
    ) -> None:
        """Ohne ``flush`` stuende die Zeile im Puffer - und waere bei einem
        Neustart genauso weg wie vorher. Gelesen wird hier ueber einen
        zweiten Dateizugriff, also so, wie es ein anderer Prozess saehe."""
        stand = _stand(tmp_path)
        stand.beginne()
        stand.halte_fest(regel="Erste", guete=0.5)

        _, messungen = lies(stand.pfad)
        assert [m["regel"] for m in messungen] == ["Erste"]

        stand.halte_fest(regel="Zweite", guete=0.6)
        _, messungen = lies(stand.pfad)
        assert [m["regel"] for m in messungen] == ["Erste", "Zweite"]

    def test_die_reihenfolge_bleibt(self, tmp_path: Path) -> None:
        stand = _stand(tmp_path)
        stand.beginne()
        for i in range(10):
            stand.halte_fest(regel=f"Regel {i}")

        _, messungen = lies(stand.pfad)
        assert [m["regel"] for m in messungen] == [f"Regel {i}" for i in range(10)]

    def test_werte_ohne_json_form_reissen_den_lauf_nicht_ab(
        self, tmp_path: Path
    ) -> None:
        """**Die Buchfuehrung darf den Lauf nicht kosten.** Ein ``Decimal``
        oder ein ``Path`` im Wert wuerde ``json.dumps`` werfen - und dann
        stuerbe ein dreistuendiger Lauf an dem, was ihn retten soll."""
        stand = _stand(tmp_path)
        stand.beginne()
        stand.halte_fest(regel="Mit Decimal", gebuehr=Decimal("0.0006"))

        _, messungen = lies(stand.pfad)
        assert messungen[0]["gebuehr"] == "0.0006"

    def test_none_bleibt_none(self, tmp_path: Path) -> None:
        """``default=str`` darf nicht aus einer fehlenden Zahl den Text
        'None' machen - sonst sieht eine Luecke aus wie ein Wert."""
        stand = _stand(tmp_path)
        stand.beginne()
        stand.halte_fest(regel="Ohne Takt", haltedauer_tage=None)

        _, messungen = lies(stand.pfad)
        assert messungen[0]["haltedauer_tage"] is None


class TestLesenWasDaIst:
    def test_eine_abgeschnittene_letzte_zeile_wird_uebergangen(
        self, tmp_path: Path
    ) -> None:
        """Genau so sieht eine Datei aus, in die mitten im Schreiben
        hineingestartet wurde. Das ist der Normalfall dieses Moduls und
        deshalb kein Fehler."""
        stand = _stand(tmp_path, genome=3)
        stand.beginne()
        stand.halte_fest(regel="Ganz", guete=0.5)
        with stand.pfad.open("a", encoding="utf-8") as datei:
            datei.write('{"art": "messung", "regel": "Halb', )

        kopf, messungen = lies(stand.pfad)
        assert kopf["genome"] == 3
        assert [m["regel"] for m in messungen] == ["Ganz"]

    def test_eine_datei_die_es_nicht_gibt(self, tmp_path: Path) -> None:
        kopf, messungen = lies(tmp_path / "nie-gelaufen.jsonl")
        assert kopf == {}
        assert messungen == ()

    def test_ein_lauf_der_nur_den_kopf_geschafft_hat(self, tmp_path: Path) -> None:
        """Auch das ist eine Auskunft: Der Lauf hat begonnen und keine
        einzige Regel fertig gemessen."""
        stand = _stand(tmp_path, intervall="15m")
        stand.beginne()

        kopf, messungen = lies(stand.pfad)
        assert kopf["intervall"] == "15m"
        assert messungen == ()

    def test_leerzeilen_stoeren_nicht(self, tmp_path: Path) -> None:
        stand = _stand(tmp_path)
        stand.beginne()
        stand.halte_fest(regel="Eine")
        with stand.pfad.open("a", encoding="utf-8") as datei:
            datei.write("\n\n")

        _, messungen = lies(stand.pfad)
        assert len(messungen) == 1


class TestKeinWiederaufsetzen:
    def test_das_modul_bietet_kein_fortsetzen_an(self) -> None:
        """**Absicht, kein Versehen.** Ein Lauf, der an Genom 18 weitermacht,
        muesste wissen, dass die ersten siebzehn unter denselben Bedingungen
        gemessen wurden - gleiche Kerzen, gleicher Versuchsstand, gleicher
        Code. Eine falsche Fortsetzung waere schlimmer als ein verlorener
        Lauf.

        Dieser Test haelt die Entscheidung fest, damit sie beim naechsten
        langen Lauf nicht beilaeufig umgestossen wird.
        """
        import research.zwischenstand as modul

        namen = {x.lower() for x in dir(modul) if not x.startswith("_")}
        assert not {
            n for n in namen if "fortsetz" in n or "resume" in n or "weiter" in n
        }
        assert "Protokoll" in modul.__doc__ and "Sicherungspunkt" in modul.__doc__


class TestDerPfadNebenDenBerichten:
    def test_neu_legt_unter_reports_ab(self, tmp_path: Path) -> None:
        stand = neu(wurzel=tmp_path, art="vorratsdecke", intervall="15m")
        assert stand.pfad.parent == tmp_path / "reports" / "vorratsdecke"
        assert stand.pfad.suffix == ".jsonl"
        assert stand.bedingungen["intervall"] == "15m"

    def test_neu_schreibt_noch_nichts(self, tmp_path: Path) -> None:
        """Erst ``beginne`` legt an. Sonst entstuende bei jedem Aufruf der
        Kommandozeile eine leere Datei, auch wenn der Lauf gar nicht
        anfaengt."""
        stand = neu(wurzel=tmp_path, art="vorratsdecke")
        assert not stand.pfad.exists()

    def test_zwei_laeufe_ueberschreiben_sich_nicht(self, tmp_path: Path) -> None:
        """Gerade nach einem Abbruch will man den Wiederholungslauf neben dem
        abgebrochenen sehen und nicht an seiner Stelle."""
        erst = neu(wurzel=tmp_path, art="vorratsdecke")
        erst.beginne()
        erst.halte_fest(regel="Vor dem Neustart")
        zweit = neu(wurzel=tmp_path, art="vorratsdecke")
        zweit.beginne()

        assert zweit.pfad != erst.pfad
        _, messungen = lies(erst.pfad)
        assert [m["regel"] for m in messungen] == ["Vor dem Neustart"]

    def test_die_zeile_nennt_den_pfad(self, tmp_path: Path) -> None:
        """Sie steht vor einem Lauf, der Stunden dauert - wer ihn im
        Hintergrund laufen laesst, braucht den Pfad."""
        stand = neu(wurzel=tmp_path, art="vorratsdecke")
        assert str(stand.pfad) in stand.zeile()


class TestWasDieZeilenTragen:
    def test_kopf_und_messung_sind_unterscheidbar(self, tmp_path: Path) -> None:
        """Ohne das Feld 'art' liesse sich ein Kopf mit den Feldern einer
        Messung nicht von einer Messung trennen."""
        stand = _stand(tmp_path, intervall="1d")
        stand.beginne()
        stand.halte_fest(regel="Eine", intervall="1d")

        zeilen = [
            json.loads(x)
            for x in stand.pfad.read_text(encoding="utf-8").splitlines()
        ]
        assert [z["art"] for z in zeilen] == ["kopf", "messung"]

    def test_ein_wert_namens_art_macht_die_datei_nicht_unlesbar(
        self, tmp_path: Path
    ) -> None:
        """Dann geht lieber die eine Angabe verloren als das ganze
        Protokoll: Ohne 'art' liesse sich keine Zeile mehr einordnen."""
        stand = _stand(tmp_path, art="eine Bedingung, die so heisst")
        stand.beginne()
        stand.halte_fest(regel="Eine", art="auch hier")

        kopf, messungen = lies(stand.pfad)
        assert kopf["art"] == "kopf"
        assert [m["regel"] for m in messungen] == ["Eine"]

    def test_eine_messung_kann_dasselbe_feld_tragen_wie_der_kopf(
        self, tmp_path: Path
    ) -> None:
        stand = _stand(tmp_path, intervall="1d")
        stand.beginne()
        stand.halte_fest(regel="Eine", intervall="15m")

        kopf, messungen = lies(stand.pfad)
        assert kopf["intervall"] == "1d"
        assert messungen[0]["intervall"] == "15m"
