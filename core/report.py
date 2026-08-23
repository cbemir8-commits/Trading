"""Berichte, die von selbst ankommen.

Warum es das gibt
-----------------
Der Rechner, auf dem gehandelt wird, steht beim Nutzer. Die Auswertung findet
woanders statt. Dazwischen lagen bisher Bildschirmfotos - unvollstaendig,
muehsam und genau dann vergessen, wenn ein Lauf interessant war.

Jeder Zulassungslauf schreibt deshalb ab sofort einen vollstaendigen Bericht
nach ``reports/`` und schiebt ihn selbstaendig ins Repository. Kein Befehl,
kein Abtippen.

Was nicht hineingehoert
-----------------------
Das Repository ist **oeffentlich**. Deshalb gilt hier eine harte Grenze, und
zwar nicht als Vorsatz, sondern als Filter im Code: Zugangsdaten, Kontostaende,
Order-IDs und Kontonummern kommen in keinen Bericht. Leistung wird in Prozent
und in R gemessen - das sind die Groessen, die fuer die Bewertung zaehlen, und
sie verraten nichts ueber das Konto dahinter.

``scrub`` prueft das nachtraeglich noch einmal auf verdaechtige Schluessel. Eine
zweite Sicherung ist hier angebracht: Ein Fehler faellt sonst erst auf, wenn er
oeffentlich steht, und dann ist er nicht mehr zurueckzunehmen - auch nicht durch
Loeschen, denn Git behaelt die Historie.

Warum das Senden nie den Lauf abbricht
--------------------------------------
Ein fehlgeschlagener Push ist ein Uebermittlungsproblem, kein Forschungsergebnis.
Die Zahlen liegen dann trotzdem lokal in ``reports/``. Deshalb faengt ``publish``
jeden Fehler ab und meldet ihn als Status, statt eine Ausnahme durchzulassen -
ein abgestuerzter Zulassungslauf waere der teurere Verlust.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

#: Zeitlimit je Git-Aufruf. Ein haengendes ``push`` darf den Lauf nicht blockieren.
GIT_TIMEOUT = 90

#: Schluessel, die niemals in einen Bericht gehoeren.
#:
#: Absichtlich als Wortbestandteile geprueft: ``api_key``, ``apiKey`` und
#: ``bybit_api_key`` sollen alle greifen.
VERBOTEN = (
    "secret",
    "token",
    "password",
    "passwort",
    "api_key",
    "apikey",
    "credential",
    "balance",
    "equity_usdt",
    "wallet",
    "order_id",
    "orderid",
    "account",
)

#: Falls Git keine Identitaet kennt. Ein Bericht soll auch auf einem frisch
#: eingerichteten Rechner durchgehen, ohne dass jemand erst ``git config`` lernt.
FALLBACK_NAME = "Trading-Bot"
FALLBACK_EMAIL = "trading-bot@localhost"


class PublishStatus(StrEnum):
    PUSHED = "gesendet"
    COMMITTED = "lokal festgehalten, nicht gesendet"
    NOTHING = "nichts Neues"
    NO_REPO = "kein Git-Verzeichnis"
    DISABLED = "abgeschaltet"
    FAILED = "fehlgeschlagen"


@dataclass(frozen=True, slots=True)
class PublishResult:
    status: PublishStatus
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (PublishStatus.PUSHED, PublishStatus.NOTHING)

    def describe(self) -> str:
        return f"{self.status.value}{f' - {self.detail}' if self.detail else ''}"


# ---------------------------------------------------------------------------
#  Inhalt
# ---------------------------------------------------------------------------
def scrub(payload: Any, *, pfad: str = "") -> Any:
    """Verdaechtige Schluessel entfernen, bevor irgendetwas geschrieben wird.

    Der Filter arbeitet auf Schluesselnamen, nicht auf Werten. Werte zu erraten
    waere Ratespiel; Schluessel sind eindeutig, und wer einen Kontostand
    veroeffentlichen will, muss das Feld dann bewusst umbenennen - was schwer
    aus Versehen passiert.
    """
    if isinstance(payload, dict):
        sauber = {}
        for key, value in payload.items():
            klein = str(key).lower()
            if any(wort in klein for wort in VERBOTEN):
                log.warning("bericht.feld_entfernt", feld=f"{pfad}{key}")
                continue
            sauber[key] = scrub(value, pfad=f"{pfad}{key}.")
        return sauber
    if isinstance(payload, list):
        return [scrub(item, pfad=pfad) for item in payload]
    return payload


def write_report(payload: dict, *, root: Path | str, kind: str = "zulassung") -> Path:
    """Bericht als JSON ablegen. Der Dateiname traegt den Zeitpunkt.

    Nichts wird ueberschrieben: Jeder Lauf bekommt eine eigene Datei. Ein
    Verlauf ueber Wochen ist der eigentliche Wert - eine einzelne Momentaufnahme
    sagt wenig darueber, ob eine Idee traegt.

    **Ausser im Trockenlauf** (Befund 116). Ein Rauchtest gehoert nicht in
    diesen Verlauf: Er sieht dort aus wie ein Lauf und ist keiner.
    """
    from research.versuche import TROCKENLAUF, trockenlauf

    if trockenlauf():
        ziel = Path(root) / "reports" / kind
        log.error(
            "bericht.trockenlauf",
            variable=TROCKENLAUF,
            pfad=str(ziel),
            folge="Es wird KEIN Bericht abgelegt.",
        )
        return ziel

    stamp = datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S")
    ordner = Path(root) / "reports" / kind
    ordner.mkdir(parents=True, exist_ok=True)

    # Zwei Laeufe in derselben Sekunde duerfen sich nicht gegenseitig
    # ueberschreiben. Selten, aber der stille Verlust eines fertig gerechneten
    # Berichts waere teuer, und die Absicherung kostet drei Zeilen.
    file = ordner / f"{stamp}.json"
    zaehler = 2
    while file.exists():
        file = ordner / f"{stamp}-{zaehler}.json"
        zaehler += 1
    file.write_text(json.dumps(scrub(payload), indent=2, ensure_ascii=False, default=str))
    log.info("bericht.geschrieben", pfad=str(file))
    return file


# ---------------------------------------------------------------------------
#  Uebermittlung
# ---------------------------------------------------------------------------
def _git(root: Path, *args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    # Feste Argumentliste, keine Shell: Nichts aus dem Bericht landet je in
    # einer Kommandozeile, die interpretiert wird.
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
        check=False,
        env=extra_env,
    )


def _identity_args(root: Path) -> list[str]:
    """``-c user.email=...`` nur, wenn Git selbst keine Identitaet kennt.

    Auf einem frisch eingerichteten Rechner ist sie nicht gesetzt, und ``commit``
    bricht dann mit einer Aufforderung ab, die niemand erwartet. Eine
    vorhandene Identitaet wird nicht angetastet.
    """
    args: list[str] = []
    for feld, ersatz in (("user.email", FALLBACK_EMAIL), ("user.name", FALLBACK_NAME)):
        vorhanden = _git(root, "config", "--get", feld)
        if vorhanden.returncode == 0 and vorhanden.stdout.strip():
            continue
        args += ["-c", f"{feld}={ersatz}"]
    return args


def publish(
    paths: list[Path],
    *,
    root: Path | str,
    message: str,
    remote: str = "origin",
    enabled: bool = True,
) -> PublishResult:
    """Die Berichte committen und senden.

    Bewusst mit ausdruecklicher Dateiliste und niemals ``git add -A``. Ein
    automatischer Vorgang, der einsammelt was gerade herumliegt, committet
    frueher oder spaeter etwas, das niemand veroeffentlichen wollte.

    **Im Trockenlauf wird nichts gesendet** (Befund 117). Das ist die
    sichtbarste Schreibstelle von allen: Sie committet **und pusht**, und ein
    Rauchtest landet damit in der Projekthistorie, wo er wie ein Lauf
    aussieht. Genau das ist passiert - ``54770ec`` ist der Bericht meines
    eigenen Rauchtests, committet um 04:59:08 und mit dem naechsten Push
    mitgegangen.

    Befund 116 hat drei Schreibstellen geschlossen und diese uebersehen, weil
    ``git status`` danach sauber war - sauber, weil der Befehl selbst schon
    committet hatte. Ein Schluss aus dem Ergebnis der eigenen Nebenwirkung.
    """
    from research.versuche import TROCKENLAUF, trockenlauf

    if trockenlauf():
        log.error(
            "senden.trockenlauf",
            variable=TROCKENLAUF,
            folge="Es wird NICHT committet und NICHT gesendet.",
        )
        return PublishResult(PublishStatus.DISABLED, f"{TROCKENLAUF} gesetzt")

    if not enabled:
        return PublishResult(PublishStatus.DISABLED)

    root = Path(root)
    if not (root / ".git").exists():
        return PublishResult(PublishStatus.NO_REPO, "hier wird nichts gesendet")

    relativ = []
    for p in paths:
        try:
            relativ.append(str(Path(p).resolve().relative_to(root.resolve())))
        except ValueError:
            log.warning("bericht.pfad_ausserhalb", pfad=str(p))
    if not relativ:
        return PublishResult(PublishStatus.NOTHING, "keine Dateien")

    try:
        return _publish(root, relativ, message, remote)
    except (subprocess.TimeoutExpired, OSError) as exc:
        # Niemals den Lauf mitreissen: Die Zahlen liegen lokal, das genuegt.
        log.warning("bericht.senden_fehlgeschlagen", fehler=str(exc))
        return PublishResult(PublishStatus.FAILED, str(exc))


def _publish(root: Path, relativ: list[str], message: str, remote: str) -> PublishResult:
    zweig = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if not zweig or zweig == "HEAD":
        return PublishResult(PublishStatus.FAILED, "kein benannter Zweig ausgecheckt")

    hinzu = _git(root, "add", "--", *relativ)
    if hinzu.returncode != 0:
        return PublishResult(PublishStatus.FAILED, hinzu.stderr.strip()[:200])

    # Nichts Neues ist kein Fehler - zweimal derselbe Lauf etwa.
    if _git(root, "diff", "--cached", "--quiet", "--", *relativ).returncode == 0:
        return PublishResult(PublishStatus.NOTHING)

    commit = _git(
        root, *_identity_args(root), "commit", "-m", message, "--only", "--", *relativ
    )
    if commit.returncode != 0:
        return PublishResult(PublishStatus.FAILED, commit.stderr.strip()[:200])

    # Erst holen, dann senden. Auf dem Zweig arbeiten zwei Seiten; ohne das
    # scheitert der Push, sobald von der anderen Seite etwas gekommen ist.
    #
    # Geht der Rebase schief, wird er **abgebrochen**. Ein automatischer
    # Vorgang darf niemanden mit einem halb fertigen Rebase und Konfliktmarken
    # im Arbeitsverzeichnis zuruecklassen - das ist ein Zustand, aus dem man
    # sich ohne Git-Kenntnisse nicht befreit. Der Bericht wartet dann lieber
    # auf den naechsten Lauf.
    pull = _git(root, "pull", "--rebase", "--autostash", remote, zweig)
    if pull.returncode != 0:
        _git(root, "rebase", "--abort")
        log.warning("bericht.rebase_abgebrochen", grund=pull.stderr.strip()[:200])

    push = _git(root, "push", remote, f"HEAD:{zweig}")
    if push.returncode != 0:
        return PublishResult(PublishStatus.COMMITTED, _push_hinweis(push.stderr))

    return PublishResult(PublishStatus.PUSHED, f"{remote}/{zweig}")


def _push_hinweis(stderr: str) -> str:
    """Aus der Git-Meldung einen brauchbaren Satz machen.

    Die Rohmeldung ist mehrzeilig und beginnt oft mit Fortschrittsbalken. Wer
    sie ungefiltert anzeigt, versteckt den einen Satz, auf den es ankommt.
    """
    text = stderr.strip()
    if re.search(r"could not read Username|Authentication failed|403", text):
        return (
            "GitHub hat die Anmeldung verweigert. Der Bericht liegt lokal in "
            "reports/ - einmal von Hand 'git push' ausfuehren und anmelden, "
            "danach laeuft es allein."
        )
    if "non-fast-forward" in text or "rejected" in text:
        return "Der Zweig ist weitergelaufen. Naechster Lauf holt ihn nach."
    if "Could not resolve host" in text or "unable to access" in text:
        return "Keine Verbindung zu GitHub."
    return text.splitlines()[-1][:200] if text else "unbekannter Grund"
