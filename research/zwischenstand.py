"""Was ein abgebrochener Lauf hinterlaesst - Befund 299.

Der Anlass
----------
``cli vorratsdecke -i 15`` braucht gemessene 3,1 Stunden (Befund 298). Beim
ersten Versuch ist der Rechner nach drei von neununddreissig Genomen neu
gestartet worden, und uebrig blieb: **nichts**. Drei gemessene Regeln, rund
zwoelf Minuten Rechenzeit, und kein Byte davon auf der Platte.

Das ist kein Sonderfall. Jede lange Messung in diesem Projekt sammelt ihre
Ergebnisse im Arbeitsspeicher und schreibt am Ende einen Bericht. Wer
unterbricht - Neustart, Zeitlimit, Tastendruck -, faengt von vorn an, und bei
drei Stunden faengt man irgendwann gar nicht erst an.

Was dieses Modul tut
--------------------
Eine Zeile je Messung, sofort geschrieben. Mehr nicht.

Kein Wiederaufsetzen: Ein Lauf, der an Genom 18 weitermacht, muesste wissen,
dass die ersten siebzehn unter **denselben** Bedingungen gemessen wurden -
gleiche Kerzen, gleicher Versuchsstand, gleicher Code. Das laesst sich
behaupten und schwer pruefen, und eine falsche Fortsetzung waere schlimmer
als ein verlorener Lauf. Was hier entsteht, ist deshalb ein **Protokoll** und
kein Sicherungspunkt: Wer den Lauf wiederholt, hat die Zahlen der ersten
Haelfte trotzdem schon gesehen.

Der Kopf traegt, unter welchen Bedingungen gemessen wurde. Ohne ihn waeren
die Zeilen Zahlen ohne Herkunft - genau das, was Befund 102 fuer Kerzen und
Befund 130 fuer Fundstellen verhindert.

In den Kopf gehoert ausserdem, **wie viele** Messungen erwartet werden. Eine
Schlusszeile kann das nicht leisten: Genau der Lauf, der abbricht, kommt nie
dazu, sie zu schreiben. Steht die erwartete Zahl dagegen oben, sieht man an
einem abgebrochenen Protokoll auf einen Blick, wo es aufgehoert hat.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

__all__ = ["Zwischenstand", "lies", "neu"]


@dataclass(slots=True)
class Zwischenstand:
    """Schreibt jede Messung sofort - eine Zeile, ein Ergebnis."""

    pfad: Path
    bedingungen: dict[str, object] = field(default_factory=dict)
    _offen: bool = False

    def __post_init__(self) -> None:
        self.pfad = Path(self.pfad)

    def beginne(self) -> None:
        """Legt die Datei an und schreibt den Kopf.

        **Der Kopf zuerst und nicht am Ende**: Bricht der Lauf ab, sollen die
        Zeilen trotzdem eine Herkunft haben.
        """
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        # ``art`` **zuletzt**: Eine Bedingung, die zufaellig so heisst, darf
        # nicht dazu fuehren, dass der Kopf nicht mehr als Kopf zu erkennen
        # ist. Dann geht lieber die Bedingung verloren als die ganze Datei.
        kopf = {
            "begonnen": datetime.now(UTC).isoformat(timespec="seconds"),
            **self.bedingungen,
            "art": "kopf",
        }
        with self.pfad.open("w", encoding="utf-8") as datei:
            # ``default=str`` wie in ``halte_fest``, aus demselben Grund: Kein
            # Lauf soll daran scheitern, dass eine Bedingung keine JSON-Form
            # hat.
            datei.write(json.dumps(kopf, ensure_ascii=False, default=str) + "\n")
        self._offen = True

    def halte_fest(self, **werte: object) -> None:
        """Eine Messung anhaengen - und sofort auf die Platte bringen.

        ``flush`` ist der Punkt der Uebung: Ohne ihn stuende die Zeile im
        Puffer und waere bei einem Neustart genauso weg wie vorher.

        ``default=str`` ist kein Schoenheitsfehler, sondern Absicht: Ein
        ``Decimal`` oder ein ``Path`` im Wert wuerde ``json.dumps`` werfen -
        und damit braeche ein dreistuendiger Lauf an der **Buchfuehrung** ab,
        die ihn retten soll. Eine als Text notierte Zahl ist immer noch
        besser als ein verlorener Lauf.
        """
        if not self._offen:
            raise RuntimeError(
                "Zwischenstand ohne 'beginne' - dann stuenden die Zeilen ohne "
                "Kopf da, und niemand wuesste, worauf sie gemessen sind."
            )
        satz = json.dumps(
            {**werte, "art": "messung"}, ensure_ascii=False, default=str
        )
        with self.pfad.open("a", encoding="utf-8") as datei:
            datei.write(satz + "\n")
            datei.flush()

    def zeile(self) -> str:
        """Was dem Nutzer vor dem Lauf dazu gesagt wird."""
        return (
            f"Zwischenstand: {self.pfad} - jede Messung wird sofort "
            f"geschrieben, ein Abbruch verliert hoechstens die laufende."
        )


def neu(*, wurzel: Path | str, art: str, **bedingungen: object) -> Zwischenstand:
    """Ein Protokoll neben den Berichten - ``reports/<art>/<zeitpunkt>.jsonl``.

    Der Name traegt den Zeitpunkt und ueberschreibt nichts, genau wie
    ``core.report.write_report``: Zwei Laeufe sind zwei Messungen, auch wenn
    der zweite den ersten wiederholt. Gerade beim Wiederholen nach einem
    Abbruch will man beide nebeneinander sehen koennen.

    Angelegt wird hier noch nichts - das tut ``beginne``.
    """
    ordner = Path(wurzel) / "reports" / art
    stempel = datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S")
    pfad = ordner / f"{stempel}.jsonl"
    zaehler = 2
    while pfad.exists():
        pfad = ordner / f"{stempel}-{zaehler}.jsonl"
        zaehler += 1
    return Zwischenstand(pfad=pfad, bedingungen=dict(bedingungen))


def lies(pfad: Path | str) -> tuple[dict, tuple[dict, ...]]:
    """Kopf und Messungen eines Protokolls.

    Eine unvollstaendige letzte Zeile wird **uebergangen** und nicht als
    Fehler gemeldet: Genau so sieht eine Datei aus, in die mitten im
    Schreiben hineingestartet wurde, und das ist der Normalfall, fuer den es
    dieses Modul gibt.
    """
    pfad = Path(pfad)
    kopf: dict = {}
    messungen: list[dict] = []
    if not pfad.exists():
        return kopf, ()
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if not zeile.strip():
            continue
        try:
            satz = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        if satz.get("art") == "kopf":
            kopf = satz
        elif satz.get("art") == "messung":
            messungen.append(satz)
    return kopf, tuple(messungen)
