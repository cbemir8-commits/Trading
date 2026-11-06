"""Eine ganze Runde, einmal durch - Befund 459.

Was gefehlt hat
---------------
``cli wettbewerb`` ist der Befehl, den der Nutzer ausfuehren soll, und in der
Suite wurde er **nur mit ``--help``** aufgerufen. Die Strecke dahinter -
Katalog laden, Kerzen pruefen, Walk-Forward, elf Gates, Bestenliste,
Versuchszaehler, Varianten bilden - ist nie am Stueck gelaufen. Ein Fehler
irgendwo darin kostet den Nutzer Stunden, und niemand haette es vorher
gewusst.

Zwei Laeufe, und der erste ist der wichtigere
---------------------------------------------
**Der Trockenlauf.** ``TRADING_TROCKENLAUF=1`` ist dafuer gebaut und deckt
seit Befund 116 *"Zaehler, Bestenliste und Berichte gleichermassen"*. Er
laeuft im echten Arbeitsverzeichnis, rechnet mit dem **echten**
Versuchsstand - also gegen die Latte, die wirklich gilt - und hinterlaesst
nichts. Jede Unterdrueckung meldet er ausdruecklich.

**Der isolierte Lauf.** Was der Trockenlauf naturgemaess nicht zeigen kann:
dass die **schreibende** Seite arbeitet. Dafuer ein zweiter Lauf in eigenem
Arbeitsverzeichnis mit eigener Ablage, der Bestenliste, Zaehler und Bericht
dort anlegt.

Mein Fehler, und es war der dritte dieser Art in diesem Projekt
---------------------------------------------------------------
Ich habe den zweiten Lauf zuerst gebaut und den ersten nicht gekannt. Dabei
sind fuenf Probelaeufe ohne jede Umlenkung gefahren, und ``cli wettbewerb``
legt einen Zulassungsbericht ab, **committet ihn und pusht** - fuenf Commits
auf dem Zweig, die niemand wollte.

Das ist aufgeschrieben, zweimal: Befund 117 (``54770ec``) und Befund 331
(``e00ffb7``), und die Warnung steht im Kopf von ``test_rauchtest`` - *"Wer
hier einen Befehl rauchtestet, setzt die Variable und verlaesst sich nicht
auf eine Teilabdeckung."* Gefunden hat mich dann die gepinnte
Berichtszaehlung aus Befund 348: 141 auf 146.

Und ``cli nachgesehen "Rauchtest, der nichts hinterlassen darf"`` findet
``versuche.trockenlauf`` an erster Stelle. Ich habe nicht gesucht, sondern
gebaut - derselbe Fehler wie in Befund 423 und 424.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

#: Generation 5 - drei Genome auf Tageskerzen, davon zwei mit
#: Finanzierungsbedarf. Die kleinste Runde, die es gibt, und sie hat echte
#: Kerzen (BTC + ETH ab 2017).
GENERATION = 5

#: Die Gates einer Vorauswahl: ``--schnell`` laesst die beiden teuren weg.
GATES_SCHNELL = 9

#: Die Wurzel des Projekts.
WURZEL = Path(__file__).resolve().parent.parent

#: Was ein Trockenlauf ausdruecklich abmeldet - und zwar jedes einzeln.
ABGEMELDET = (
    "zaehler.trockenlauf",
    "bestenliste.trockenlauf",
    "zulassung.journal_trockenlauf",
)

pytestmark = pytest.mark.daten


def _argumente() -> list[str]:
    return [
        "wettbewerb", "-g", str(GENERATION), "--runden", "1",
        "-m", "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP",
    ]


def _lauf(*, ablage: Path | None = None, trocken: bool = False) -> tuple[int, str]:
    """Eine Runde als eigener Prozess.

    Als Unterprozess und nicht ueber ``CliRunner``: Beide Schalter wirken
    ueber die Umgebung, und ``get_settings`` speichert sie zwischen - ein Test,
    der das im eigenen Prozess umbiegt, haengt von der Testreihenfolge ab.

    ``trocken`` laeuft im echten Arbeitsverzeichnis und hinterlaesst nichts.
    ``ablage`` lenkt stattdessen alles Schreibende um; was **gelesen** wird -
    Kerzen und Referenzdaten - zeigt dann absolut auf die echten Staende.
    """
    import subprocess
    import sys

    umgebung = dict(os.environ)
    umgebung.pop("TRADING_TROCKENLAUF", None)
    wo = WURZEL
    if trocken:
        umgebung["TRADING_TROCKENLAUF"] = "1"
    if ablage is not None:
        ablage.mkdir(parents=True, exist_ok=True)
        wo = ablage
        umgebung.update(
            PATHS__STATE=str(ablage / "state"),
            PATHS__STRATEGIES=str(ablage / "strategies"),
            PATHS__LOGS=str(ablage / "logs"),
            PATHS__DATA_STORE=str(WURZEL / "data_store"),
            PATHS__REFERENZ=str(WURZEL / "referenz"),
            REPORT__AUTOPUSH="false",
        )
    fertig = subprocess.run(
        [sys.executable, str(WURZEL / "cli.py"), *_argumente()],
        capture_output=True, text=True, env=umgebung, timeout=900, cwd=str(wo),
    )
    return fertig.returncode, fertig.stdout + fertig.stderr


def _stand() -> tuple[str, int, bool]:
    """Was im Repository stehen bleiben muss: Zaehler, Berichte, Bestenliste.

    Alle drei, weil alle drei schon einmal angefasst wurden - der Zaehler
    haette die Huerde fuer alle folgenden gehoben (116), die Berichte haben
    die gepinnte Zaehlung aus 348 verschoben (459).
    """
    zaehler = WURZEL / "state" / "trials.json"
    return (
        hashlib.sha256(zaehler.read_bytes()).hexdigest()
        if zaehler.exists()
        else "fehlt",
        len(list((WURZEL / "reports" / "zulassung").glob("*.json"))),
        (WURZEL / "state" / "leaderboard.json").exists(),
    )


@pytest.fixture(scope="module")
def vorher() -> tuple[str, int, bool]:
    """Der Stand **vor** jedem Lauf.

    Danach genommen waere er wertlos: Haette der erste Lauf etwas angefasst,
    verglichen sich zwei verfaelschte Staende. Deshalb haengen beide
    Lauf-Fixtures daran.
    """
    return _stand()


@pytest.fixture(scope="module")
def trockenlauf(vorher: tuple[str, int, bool]) -> str:
    """**Auf Modulebene** (Befund 426/429): eine Fixture mit 'scope="module"'
    als Methode in der Klasse bricht pytest."""
    assert vorher  # sichert die Reihenfolge, nicht nur die Absicht
    code, ausgabe = _lauf(trocken=True)
    if code != 0:
        pytest.fail(f"Trockenlauf endete mit {code}:\n{ausgabe[-3000:]}")
    return " ".join(ausgabe.split())


@pytest.fixture(scope="module")
def echter_lauf(tmp_path_factory, vorher) -> tuple[Path, str]:
    assert vorher
    ablage = tmp_path_factory.mktemp("ablage")
    code, ausgabe = _lauf(ablage=ablage)
    if code != 0:
        pytest.fail(f"Runde endete mit {code}:\n{ausgabe[-3000:]}")
    return ablage, " ".join(ausgabe.split())


class TestDerTrockenlaufIstDerRichtigeWeg:
    """``TRADING_TROCKENLAUF=1`` - gebaut fuer genau das, seit Befund 116 mit
    dem Vertrag *"hinterlaesst nichts"*. Ein Schalter statt fuenf Umlenkungen,
    und er rechnet mit dem **echten** Versuchsstand."""

    def test_die_runde_laeuft_durch(self, trockenlauf: str) -> None:
        assert "Traceback" not in trockenlauf
        assert "Strategien in 1 Laeufen geprueft" in trockenlauf

    def test_sie_rechnet_mit_dem_echten_versuchsstand(self, trockenlauf) -> None:
        """**Der Vorteil gegenueber einer frischen Ablage.** Dort stuende der
        Zaehler auf 0 und die Latte waere die eines ersten Versuchs - aus so
        einem Lauf ist kein Urteil zu lesen. Hier gilt die echte Latte."""
        from research.versuche import laden

        echt = laden(WURZEL / "state" / "trials.json").anzahl

        assert f"{echt} Versuche bisher" in trockenlauf
        assert f"Versuche gesamt: {echt + 1}" in trockenlauf

    def test_er_meldet_jede_unterdrueckung_einzeln(self, trockenlauf) -> None:
        """Nicht eine Sammelmeldung: Wer eine Zeile ueberliest, soll die
        anderen noch sehen."""
        for marke in ABGEMELDET:
            assert marke in trockenlauf, marke
        assert "wird NICHT fortgeschrieben" in trockenlauf

    def test_und_sagt_was_zu_tun_ist_wer_wirklich_sucht(self, trockenlauf) -> None:
        assert "muss die Variable loeschen" in trockenlauf

    def test_und_hinterlaesst_nichts(self, trockenlauf, vorher) -> None:
        """**Die tragende Zusicherung dieses Moduls.** Der Vertrag aus Befund
        116 gilt fuer Zaehler, Bestenliste **und** Berichte."""
        assert _stand() == vorher


class TestDieSchreibendeSeiteArbeitetAuch:
    """Was der Trockenlauf nicht zeigen kann - und was ein Nutzer braucht:
    dass Bestenliste, Zaehler und Bericht wirklich entstehen."""

    def test_sie_prueft_den_katalog_der_generation(self, echter_lauf) -> None:
        """**Genau eine Generation** und nicht alle - und die zwei Regeln mit
        Finanzierungsbedarf fallen ohne Daten still heraus. Beides steht in
        der Ausgabe, und beides ist Absicht."""
        from research.generationen import uebersicht

        _, ausgabe = echter_lauf
        bild = next(b for b in uebersicht() if b.nummer == GENERATION)
        erwartet = bild.genome - len(bild.finanzierung)

        assert f"Runde 1 - {erwartet} Kandidaten (Katalog)" in ausgabe
        assert "stuetzen sich auf Kennzahlen, die diese Reihe nicht hat" in ausgabe

    def test_sie_schreibt_eine_bestenliste(self, echter_lauf) -> None:
        ablage, _ = echter_lauf
        liste = ablage / "state" / "leaderboard.json"

        assert liste.exists()
        assert json.loads(liste.read_text(encoding="utf-8"))

    def test_sie_zaehlt_die_versuche_mit(self, echter_lauf) -> None:
        """Der Punkt, an dem der Dauerlauf ehrlich ist: Jeder geprueefte
        Kandidat kostet einen Versuch, und das steht da."""
        ablage, ausgabe = echter_lauf

        assert (ablage / "state" / "trials.json").exists()
        assert "Versuche gekostet" in ausgabe
        # Eigene Ablage, also beginnt der Zaehler bei null - und deshalb ist
        # aus **diesem** Lauf kein Urteil zu lesen.
        assert "(0 -> 1)" in ausgabe

    def test_der_bericht_landet_in_der_eigenen_ablage(self, echter_lauf) -> None:
        """``write_report`` nimmt ``root=Path.cwd()`` - deshalb braucht dieser
        Lauf ein eigenes **Arbeitsverzeichnis** und nicht nur eine eigene
        Ablage. Genau daran ist mein erster Entwurf gescheitert."""
        ablage, ausgabe = echter_lauf
        eigene = list((ablage / "reports" / "zulassung").glob("*.json"))

        assert len(eigene) == 1, eigene
        assert str(ablage) in ausgabe

    def test_und_urteilt_mit_neun_gates_in_der_vorauswahl(self, echter_lauf) -> None:
        """``--schnell`` ist die Vorgabe und laesst die beiden teuren Gates
        weg. Wer sie besteht, wird mit allen elf nachgeprueft - ein Champion
        entsteht nie aus einer Vorauswahl."""
        _, ausgabe = echter_lauf

        assert f"von {GATES_SCHNELL} Gates" in ausgabe

    def test_auch_dieser_lauf_laesst_das_repository_unberuehrt(
        self, echter_lauf, vorher
    ) -> None:
        assert _stand() == vorher
