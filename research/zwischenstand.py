"""Lange Messungen in Stuecken - Befunde 299 und 300.

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

Und dann die Messung (Befund 300)
---------------------------------
Der zweite Versuch endete nach **einem** Genom. Beide Male hoerte der Lauf
wenige Minuten nach dem Ende meines Arbeitszugs auf: 12 Minuten beim ersten
Mal, knapp 6 beim zweiten. Die Maschine wird eingezogen, sobald die Sitzung
still ist - ein Lauf im Hintergrund ueberlebt das nicht.

Damit ist ein dreistuendiger Lauf hier nicht "riskant", sondern **unmoeglich**.
Er muss in Stuecke, die einzeln durchlaufen.

Was dieses Modul tut
--------------------
Eine Zeile je Messung, sofort geschrieben - und die Pruefung, ob mehrere
solche Protokolle **dieselbe** Messung sind.

Kein Wiederaufsetzen: Ein Lauf, der an Genom 18 weitermacht, muesste wissen,
dass die ersten siebzehn unter **denselben** Bedingungen gemessen wurden -
gleiche Kerzen, gleicher Versuchsstand, gleicher Code. Diese Ablehnung aus
Befund 299 bleibt, und ``zusammen`` umgeht sie nicht, sondern beantwortet
sie: Was sich nicht behaupten lassen soll, wird **geprueft**. Die Koepfe
muessen Feld fuer Feld uebereinstimmen; wo sie es nicht tun, sagt der Fehler,
worin. Der Preis dafuer steht auf der anderen Seite: Was der Kopf nicht
traegt, kann er auch nicht pruefen - der Abdruck von Kerzen, Katalog und
Codestand gehoert deshalb hinein.

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
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

#: Steht fuer "dieses Feld gibt es hier gar nicht" - unterscheidbar von
#: ``None``, das ein gemessener Wert sein kann.
_FEHLT = object()

__all__ = ["Uneinig", "Zwischenstand", "lies", "neu", "scheibe", "zusammen"]

#: Felder, die sich zwischen zwei Stuecken **derselben** Messung aendern
#: duerfen - und nur diese.
#:
#: ``begonnen`` ist der Zeitpunkt, ``stueck`` sagt, welcher Teil es ist, und
#: ``genome`` ist die erwartete Zahl **dieses** Stuecks. Alles andere im Kopf
#: beschreibt die Bedingungen und muss gleich sein.
WECHSELND: tuple[str, ...] = ("begonnen", "stueck", "genome")


class Uneinig(RuntimeError):  # noqa: N818 - deutsche Namen, wie ueberall hier
    """Protokolle, die nicht dieselbe Messung sind.

    Der Fehler nennt die Felder, in denen sie auseinandergehen. Das ist der
    Punkt: Ein stillschweigend falsch zusammengesetzter Lauf waere schlimmer
    als ein verlorener.
    """


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


def zusammen(
    pfade: Iterable[Path | str], *, wechselnd: Iterable[str] = WECHSELND
) -> tuple[dict, tuple[dict, ...]]:
    """Mehrere Stuecke zu einer Messung zusammenlegen - **wenn** sie es sind.

    Geprueft wird der Kopf: Bis auf die Felder in ``wechselnd`` muss er
    ueberall gleich sein. Genau das ist der Unterschied zu einem
    Wiederaufsetzen, das Befund 299 abgelehnt hat - dort wurde behauptet, die
    Bedingungen seien dieselben, hier wird es nachgesehen.

    Die Pruefung ist nur so gut wie der Kopf. Steht der Codestand nicht drin,
    kann sie ihn nicht vergleichen; ein Kopf, der nur 'Intervall' traegt,
    laesst zwei Laeufe auf unterschiedlichen Kerzen zusammen. Wer ``zusammen``
    benutzt, schuldet dem Kopf einen Abdruck.

    Die Reihenfolge der Messungen folgt der Reihenfolge der Pfade; der
    zurueckgegebene Kopf ist der des ersten Stuecks, ohne die wechselnden
    Felder.

    Ein Stueck ohne Kopf gilt als nicht lesbar und fuehrt zu ``Uneinig`` -
    eine Datei ohne Herkunft ist genau das, wogegen der Kopf steht.
    """
    pfade = [Path(p) for p in pfade]
    if not pfade:
        raise Uneinig("Keine Protokolle angegeben - nichts zusammenzulegen.")
    wechselnd = set(wechselnd)
    koepfe: list[tuple[Path, dict]] = []
    messungen: list[dict] = []
    for pfad in pfade:
        kopf, teil = lies(pfad)
        if not kopf:
            raise Uneinig(
                f"{pfad} hat keinen Kopf - ohne ihn ist nicht zu sagen, "
                f"worauf die Zeilen gemessen sind."
            )
        koepfe.append((pfad, kopf))
        messungen.extend(teil)

    ersterpfad, erster = koepfe[0]
    vergleich = {k: v for k, v in erster.items() if k not in wechselnd}
    for pfad, kopf in koepfe[1:]:
        anderer = {k: v for k, v in kopf.items() if k not in wechselnd}
        # ``_FEHLT`` statt ``None`` als Ausweichwert: Ein Feld, das nur in
        # einem Kopf steht, ist ein Unterschied - auch dann, wenn im anderen
        # ``None`` stuende, denn ``None`` kann ein gemessener Wert sein.
        unterschiede = sorted(
            k
            for k in set(vergleich) | set(anderer)
            if vergleich.get(k, _FEHLT) != anderer.get(k, _FEHLT)
        )
        if unterschiede:
            benannt = ", ".join(
                f"{k}: {vergleich.get(k, '-')!r} gegen {anderer.get(k, '-')!r}"
                for k in unterschiede
            )
            raise Uneinig(
                f"{pfad} gehoert nicht zu {ersterpfad} - {benannt}. Zwei "
                f"Stuecke unter verschiedenen Bedingungen sind zwei "
                f"Messungen, keine."
            )
    return vergleich, tuple(messungen)


def scheibe(wieviele: int, stueck: str) -> tuple[int, int]:
    """Welchen Teil eines Laufs ``"2/5"`` meint - als Indexpaar.

    Die Stuecke sind zusammenhaengend und decken den Lauf luecken- und
    ueberschneidungsfrei ab; geht die Zahl nicht auf, bekommen die vorderen
    Stuecke eines mehr. Das ist wichtiger, als es aussieht: Ueberschneiden
    sich zwei Stuecke, steht dieselbe Regel zweimal im zusammengelegten
    Protokoll und zaehlt doppelt.

    Falsche Angaben werden abgewiesen und nicht gerundet - ein stillschweigend
    verschobenes Stueck waere ein Lauf, der nie fertig wird.
    """
    text = stueck.strip()
    if "/" not in text:
        raise ValueError(f"'{stueck}' ist kein Stueck - erwartet wird 'i/n'.")
    links, rechts = text.split("/", 1)
    try:
        i, n = int(links), int(rechts)
    except ValueError:
        raise ValueError(f"'{stueck}' ist kein Stueck - erwartet wird 'i/n'.") from None
    if n < 1:
        raise ValueError(f"'{stueck}': Ein Lauf hat mindestens ein Stueck.")
    if not 1 <= i <= n:
        raise ValueError(f"'{stueck}': Das {i}. von {n} Stuecken gibt es nicht.")
    if wieviele < 0:
        raise ValueError("Ein Lauf hat keine negative Laenge.")
    grund, rest = divmod(wieviele, n)
    anfang = (i - 1) * grund + min(i - 1, rest)
    ende = anfang + grund + (1 if i <= rest else 0)
    return anfang, ende
