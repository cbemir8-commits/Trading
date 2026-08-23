"""Der Versuchszaehler - und warum er nie wieder fallen darf.

Was in ``state/trials.json`` steht
----------------------------------
Eine Zahl. ``{"trials": 166}``, sonst nichts. Sie steuert die Haerte des
Gates, an dem dieses Projekt seit Befund 61 haengt: Jeder Versuch hebt die
Huerde um rund 0,0002 DSR-Punkte, und in Summe macht das den Unterschied
zwischen bestanden und nicht.

Der Fehler, der eingebaut war
-----------------------------
``load_trials`` gab bei einer unlesbaren Datei **0** zurueck. Der Kommentar
daneben benannte die Gefahr sogar - *"ein zu niedriger Zaehler macht die
Deflated Sharpe Ratio milder"* - und der Test dazu hiess
``test_corrupt_file_starts_at_zero``. Erkannt, benannt, und so gelassen.

Ein Protokolleintrag ist keine Absicherung. Der Lauf ging weiter, rechnete
alle Gates gegen den falschen Stand und schrieb ihn danach fest. Was das
bedeutet, in Zahlen am Spitzenkandidaten:

    166 Versuche  DSR 0,7865   durchgefallen
     45 Versuche  DSR 0,9430   durchgefallen
     22 Versuche  DSR 0,9809   **bestanden**
     11 Versuche  DSR 0,9955   **bestanden**

Ein einziger Dateifehler, gefolgt von einem Wettbewerb mit elf Genomen, haette
den Zaehler auf 11 gesetzt - und damit das strengste Gate des Projekts
umgedreht. Ohne Absicht, ohne dass jemand etwas gelockert haette, und ohne
dass es irgendwo aufgefallen waere ausser in einer Logzeile.

Die Regel, die daraus folgt
---------------------------
**Der Zaehler faellt nicht.** Nicht durch einen Lesefehler, nicht durch einen
Schreibfehler, nicht durch einen Lauf, der weniger meldet als der vorige.

* Datei **fehlt** -> 0. Das ist der erste Lauf, und da stimmt die 0.
* Datei **kaputt** -> Abbruch. Lieber steht das Projekt, als dass es
  stillschweigend milder wird.
* Ein kleinerer Wert -> wird nicht geschrieben, sondern protokolliert.

Und was das Verzeichnis daraus macht
------------------------------------
Wenn die Zahl ohnehin angefasst wird, kann sie auch ihre Herkunft mitbringen.
Befund 68 hat gezeigt, dass die Streuung der Sharpe-Schaetzer ueber die
Versuche - die einzige geratene Eingabe des Gates - nur deshalb nicht messbar
ist, weil niemand aufgeschrieben hat, was er probiert hat.

Ab jetzt steht zu jedem neuen Versuch sein Sharpe je Trade in der Datei. Die
bisherigen 166 bleiben als ``grundstock`` erhalten, ausdruecklich **ohne**
Einzelnachweis - sie zu erfinden waere schlimmer als die Luecke.

Das macht die Streuung nicht rueckwirkend messbar. Bei einem Abbruch des
Suchbudgets bei 230 Versuchen waere die Abdeckung bestenfalls 40 %, und
``streuung.MINDESTABDECKUNG`` verlangt 90. Es macht sie aber **belastbarer**,
und den Zaehler zum ersten Mal pruefbar: Bisher war 166 eine Behauptung ohne
Beleg.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

#: Format mit Einzelnachweis. Format 1 war ``{"trials": n}``.
FORMAT = 2

#: Umgebungsvariable, die jedes Fortschreiben des Zaehlers unterbindet.
#:
#: **Der Anlass, Befund 104.** Ein Rauchtest hat alle 61 Befehle einmal mit
#: ihren Voreinstellungen aufgerufen, um Fehler wie den aus Befund 103 zu
#: finden. Zwanzig davon messen und zaehlen dabei - der Zaehler stand danach
#: bei 198 statt 177. **Ein Test hat die Huerde des haertesten Gates um 0,004
#: Punkte angehoben**, ohne eine einzige Hypothese zu pruefen.
#:
#: Warum eine Umgebungsvariable und kein Schalter je Befehl: Ein Durchlauf
#: ruft die Befehle als eigene Prozesse auf, und die Haelfte hat gar kein
#: ``--nicht-zaehlen``. Eine Variable deckt alle auf einmal ab.
#:
#: Warum das gefaehrlich ist und trotzdem richtig: Bleibt sie versehentlich
#: gesetzt, zaehlt eine echte Suche nicht mit - und ein zu **niedriger**
#: Zaehler ist genau die Richtung, gegen die dieses Modul gebaut ist. Deshalb
#: protokolliert jeder unterdrueckte Schreibvorgang auf Fehlerstufe, und
#: ``cli stand`` zeigt die Variable an, solange sie steht.
TROCKENLAUF = "TRADING_TROCKENLAUF"


def trockenlauf() -> bool:
    """Laeuft gerade etwas, das nichts hinterlassen darf?

    **Der Vertrag war zu eng, und ich bin selbst darauf hereingefallen**
    (Befund 116). Hier stand *"Laeuft gerade etwas, das nicht zaehlen darf?"*,
    und genau so war es gebaut: geschuetzt war der Versuchszaehler, sonst
    nichts. Der Name verspricht mehr - und der Name ist, was man beim Benutzen
    sieht.

    Mit ``TRADING_TROCKENLAUF=1`` habe ich ``cli wettbewerb`` als Rauchtest
    laufen lassen. Der Zaehler blieb bei 198, wie zugesagt. Fortgeschrieben
    wurde trotzdem: die Bestenliste von 11 auf 12 Laeufe, neun Eintraege mit
    neuem Datum, dazu ein Zulassungsbericht.

    Jetzt gilt der Name: Wer die Variable setzt, hinterlaesst nichts -
    Zaehler, Bestenliste und Berichte gleichermassen. Die Richtung ist die
    sichere: Wird die Variable vergessen, ist die Folge "es wurde nichts
    geschrieben" - aergerlich und wiederholbar. Umgekehrt ist sie es nicht.
    """
    wert = os.environ.get(TROCKENLAUF, "").strip().lower()
    return wert not in ("", "0", "nein", "false", "aus")


class ZaehlerUnlesbarError(RuntimeError):
    """Die Zaehlerdatei ist da, aber nicht zu lesen.

    Eine eigene Ausnahme und kein stiller Standardwert: Bei 0 weiterzurechnen
    hiesse, alle Gates gegen eine Huerde zu pruefen, die es nie gab.
    """


@dataclass(frozen=True, slots=True)
class Versuch:
    """Ein geprueftes Genom - und was dabei herauskam.

    ``sharpe_je_trade`` ist die Groesse, um die es geht: Aus ihr liesse sich
    die Streuung ueber die Versuche messen, statt sie zu raten. ``None``
    heisst "nicht erhoben" und nicht "kein Vorteil" - der Unterschied
    entscheidet, ob ein Punkt in die Schaetzung darf.
    """

    kennung: str
    zeitpunkt: str = ""
    trades: int = 0
    sharpe_je_trade: float | None = None
    herkunft: str = ""

    @classmethod
    def jetzt(cls, kennung: str, **rest) -> Versuch:
        return cls(kennung=kennung, zeitpunkt=datetime.now(UTC).isoformat(), **rest)


@dataclass(slots=True)
class Verzeichnis:
    """Alle Versuche - die belegten einzeln, die alten als Summe."""

    grundstock: int = 0
    """Versuche von vor der Einfuehrung des Verzeichnisses.

    Ohne Einzelnachweis, und das bleibt so. Sie nachtraeglich zu erfinden
    waere eine Zahl ohne Messung an genau der Stelle, an der dieses Projekt
    schon zweimal hereingefallen ist.
    """

    eintraege: list[Versuch] = field(default_factory=list)

    @property
    def anzahl(self) -> int:
        return self.grundstock + len(self.eintraege)

    def sharpes(self) -> list[float]:
        """Die belegten Qualitaeten je Trade - ohne die nicht erhobenen."""
        return [
            v.sharpe_je_trade
            for v in self.eintraege
            if v.sharpe_je_trade is not None
        ]

    @property
    def belegt(self) -> int:
        return len(self.sharpes())

    def erweitert(self, versuche: list[Versuch]) -> Verzeichnis:
        return Verzeichnis(
            grundstock=self.grundstock, eintraege=[*self.eintraege, *versuche]
        )


def laden(pfad: Path | str) -> Verzeichnis:
    """Das Verzeichnis lesen. Fehlt die Datei, ist es leer.

    Ist sie da und unlesbar, fliegt ``ZaehlerUnlesbarError`` - und zwar
    absichtlich statt eines Standardwerts. Der frueher zurueckgegebene
    Nullwert war die unsichere Richtung: Er hat die Mehrfachtest-Korrektur
    ausgehebelt, ohne dass ein Lauf stehengeblieben waere.
    """
    datei = Path(pfad)
    if not datei.exists():
        return Verzeichnis()
    try:
        daten = json.loads(datei.read_text())
        if not isinstance(daten, dict):
            raise TypeError("kein Objekt")
        if "grundstock" in daten or "versuche" in daten:
            eintraege = [
                Versuch(
                    kennung=str(e.get("kennung", "?")),
                    zeitpunkt=str(e.get("zeitpunkt", "")),
                    trades=int(e.get("trades", 0)),
                    sharpe_je_trade=(
                        float(e["sharpe_je_trade"])
                        if e.get("sharpe_je_trade") is not None
                        else None
                    ),
                    herkunft=str(e.get("herkunft", "")),
                )
                for e in daten.get("versuche", [])
            ]
            return Verzeichnis(
                grundstock=int(daten.get("grundstock", 0)), eintraege=eintraege
            )
        # Format 1: eine nackte Zahl. Sie ist der Grundstock.
        return Verzeichnis(grundstock=int(daten["trials"]))
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        log.error(
            "zulassung.zaehler_unlesbar",
            fehler=str(exc),
            pfad=str(datei),
            folge="Lauf abgebrochen - ein Standardwert haette die "
            "Mehrfachtest-Korrektur stillschweigend milder gemacht",
        )
        raise ZaehlerUnlesbarError(
            f"'{datei}' ist vorhanden, aber nicht lesbar ({exc}). Der "
            f"Versuchszaehler steuert die Haerte des Deflated-Sharpe-Gates; "
            f"mit einem Ersatzwert weiterzurechnen wuerde jede Zulassung "
            f"entwerten. Datei aus der Sicherung holen oder den Stand von "
            f"Hand eintragen."
        ) from exc


def speichern(pfad: Path | str, verzeichnis: Verzeichnis) -> None:
    """Atomar schreiben - und ``trials`` fuer alte Leser mit.

    Die Summe steht doppelt in der Datei: einmal als ``trials``, damit ein
    Leser des alten Formats sie findet, und einmal implizit aus Grundstock
    und Eintraegen. Doppelte Wahrheiten laufen sonst auseinander - hier nicht,
    weil nur diese Funktion schreibt und sie beide aus derselben Quelle nimmt.
    """
    if trockenlauf():
        # Laut und auf Fehlerstufe: Ein stiller Trockenlauf waere schlimmer
        # als das Problem, das er loest.
        log.error(
            "zaehler.trockenlauf",
            pfad=str(pfad),
            waere=verzeichnis.anzahl,
            variable=TROCKENLAUF,
            folge="Der Stand wird NICHT fortgeschrieben. Wer wirklich sucht, "
            "muss die Variable loeschen - sonst zaehlt die Suche nicht mit.",
        )
        return

    datei = Path(pfad)
    datei.parent.mkdir(parents=True, exist_ok=True)
    inhalt = {
        "format": FORMAT,
        "trials": verzeichnis.anzahl,
        "grundstock": verzeichnis.grundstock,
        "updated_at": datetime.now(UTC).isoformat(),
        "versuche": [asdict(v) for v in verzeichnis.eintraege],
    }
    temporaer = datei.with_suffix(".tmp")
    temporaer.write_text(json.dumps(inhalt, indent=2))
    temporaer.replace(datei)


def anhaengen(pfad: Path | str, versuche: list[Versuch]) -> Verzeichnis:
    """Neue Versuche eintragen, ohne die alten zu verlieren.

    Lesen und Schreiben in einem Griff, weil beides zusammengehoert: Wer
    lokal zaehlt und am Ende eine Summe schreibt, kann den Stand verlieren.
    """
    verzeichnis = laden(pfad).erweitert(versuche)
    speichern(pfad, verzeichnis)
    return verzeichnis
