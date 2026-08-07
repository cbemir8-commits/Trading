"""Termine, an denen der Markt springt - und wann deshalb nicht eingestiegen wird.

Das fehlende Stueck aus Phase 7. Der Risk-Officer kannte das Veto
``NEWS_BLACKOUT`` und die Methode ``set_news_blackout`` von Anfang an; was
fehlte, war die Quelle: Woher weiss der Betrieb, dass in zwanzig Minuten die
Fed spricht?

**Nur nachpruefbare Termine.** Aufgenommen wird, was aus einer kanonischen
Quelle stammt und sich jederzeit nachrechnen laesst:

* **FOMC-Entscheidungen** - direkt von federalreserve.gov. Genommen wird nicht
  das angekuendigte Sitzungsdatum, sondern der Dateiname der
  Erklaerungs-Pressemitteilung (``monetary20200315a.htm``). Der ist der Tag
  der Veroeffentlichung, und damit exakt der Moment, an dem sich der Kurs
  bewegt. Nebenwirkung, die sich als Vorteil erwies: So stehen auch die
  **ausserplanmaessigen** Sitzungen im Kalender - im Maerz 2020 waren das
  vier innerhalb eines Monats, und das waren genau die Tage, an denen Bitcoin
  am staerksten sprang.
* **Bitcoin-Halbierungen** - der Zeitstempel des Blocks 210.000, 420.000,
  630.000, 840.000 von mempool.space. Kein Schaetzwert, sondern die Blockzeit.

**Was fehlt, und warum:** CPI-Veroeffentlichungen. Die kanonische Quelle
(bls.gov) antwortet diesem Container mit 403. Ein geschaetztes Datum waere
schlimmer als keines - es wuerde den falschen Tag sperren und einen echten
Termin ungesperrt lassen. Der Abruf laeuft als ``cli termine``; vom Rechner
des Nutzers aus ist bls.gov erreichbar, und die Luecke laesst sich dort
schliessen.

**Was ein Termin-Overlay leisten kann - und was nicht.** Es hindert am
*Einstieg*, nicht am Halten. Eine Position, die seit vier Wochen laeuft, wird
nicht wegen einer Fed-Sitzung geschlossen; das waere eine andere Strategie.
Fuer einen Tageskerzen-Handel mit sechs Wochen Haltedauer ist die Wirkung
deshalb klein. Gebraucht wird es fuer die 15-Minuten-Generationen, wo eine
Position auch mal zwei Stunden vor einer Fed-Entscheidung eroeffnet wuerde.
"""

from __future__ import annotations

import json
from bisect import bisect_left
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

#: Kanonische Quellen. Stehen hier und nicht verstreut im Code, damit
#: nachvollziehbar bleibt, woher jede Zahl kommt.
FOMC_AKTUELL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FOMC_HISTORIE = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{jahr}.htm"
BLOCK_API = "https://mempool.space/api/v1/blocks/{hoehe}"

#: Die Blockhoehen, bei denen sich die Belohnung halbiert.
HALBIERUNGSHOEHEN = (210_000, 420_000, 630_000, 840_000)

#: Uhrzeit der FOMC-Erklaerung: 14:00 Ortszeit New York, seit 2013 unveraendert.
#: Ausserplanmaessige Ankuendigungen halten sich nicht daran - siehe
#: ``Termin.geplant``.
FOMC_STUNDE_NY = 14


class Terminart(StrEnum):
    FOMC = "fomc"
    HALBIERUNG = "halbierung"
    CPI = "cpi"
    SONSTIGES = "sonstiges"


@dataclass(frozen=True, slots=True, order=True)
class Termin:
    """Ein Zeitpunkt, an dem mit einem Sprung zu rechnen ist."""

    zeitpunkt: datetime
    art: Terminart = Terminart.SONSTIGES
    beschreibung: str = ""
    geplant: bool = True
    """Planmaessige Sitzung, oder kurzfristig einberufen?

    Der Unterschied ist nicht kosmetisch: Bei einer planmaessigen Sitzung steht
    die Uhrzeit fest, bei einer ausserplanmaessigen nicht. Die Ankuendigung vom
    15. Maerz 2020 kam an einem Sonntagabend.
    """

    def to_json(self) -> dict:
        return {
            "zeitpunkt": self.zeitpunkt.isoformat(),
            "art": self.art.value,
            "beschreibung": self.beschreibung,
            "geplant": self.geplant,
        }

    @classmethod
    def from_json(cls, data: dict) -> Termin:
        return cls(
            zeitpunkt=datetime.fromisoformat(data["zeitpunkt"]),
            art=Terminart(data.get("art", "sonstiges")),
            beschreibung=data.get("beschreibung", ""),
            geplant=bool(data.get("geplant", True)),
        )


class Terminkalender:
    """Die Termine, sortiert - und die Frage, ob gerade gesperrt ist.

    Bewusst ohne Netzwerkzugriff im Betrieb: Der Kalender wird einmal geholt
    (``cli termine``) und liegt danach als Datei vor. Ein Handelssystem, das
    vor jeder Order eine fremde Webseite fragt, haengt an deren Verfuegbarkeit
    - und faellt genau dann aus, wenn es hektisch wird.
    """

    def __init__(
        self,
        termine: list[Termin] | None = None,
        *,
        quelle: str = "",
        geholt_am: datetime | None = None,
    ) -> None:
        self.termine = sorted(termine or [])
        self.quelle = quelle
        self.geholt_am = geholt_am
        self._zeiten = [t.zeitpunkt for t in self.termine]

    def __len__(self) -> int:
        return len(self.termine)

    def __bool__(self) -> bool:
        return bool(self.termine)

    # -- Die eigentliche Frage ----------------------------------------------
    def sperre(
        self,
        jetzt: datetime,
        *,
        spanne: timedelta = timedelta(0),
        vorlauf: timedelta = timedelta(minutes=60),
        nachlauf: timedelta = timedelta(minutes=60),
    ) -> Termin | None:
        """Welcher Termin sperrt diesen Einstieg? ``None`` heisst: frei.

        ``jetzt`` ist der **Entscheidungszeitpunkt** - der Schluss der Kerze,
        auf die gehandelt wird. ``spanne`` ist die Laenge dieser Kerze.
        Gesperrt wird, wenn ein Termin im Fenster

            [jetzt - spanne - vorlauf,  jetzt + nachlauf]

        liegt. Der Teil ``- spanne`` ist der wichtige: **Faellt der Termin in
        die Kerze, auf die wir gerade handeln wollen, wird nicht gehandelt.**

        Ohne diesen Teil waere die Regel von der Kerzenlaenge abhaengig und
        muesste je Intervall eingestellt werden - und ein eingestellter Wert
        waere eine weitere Stellschraube, an der sich etwas passend drehen
        laesst. Auf Tageskerzen sperrt eine Fed-Entscheidung um 18:00 UTC so
        den Einstieg am naechsten Mitternachtsschluss; auf 15-Minuten-Kerzen
        sperrt sie die Stunde davor und danach. Beides ohne eine einzige Zahl,
        die zum Ergebnis passend gewaehlt werden koennte.
        """
        if not self.termine:
            return None

        von = jetzt - spanne - vorlauf
        bis = jetzt + nachlauf
        i = bisect_left(self._zeiten, von)
        if i < len(self._zeiten) and self._zeiten[i] <= bis:
            return self.termine[i]
        return None

    def naechster(self, jetzt: datetime) -> Termin | None:
        i = bisect_left(self._zeiten, jetzt)
        return self.termine[i] if i < len(self._zeiten) else None

    def im_zeitraum(self, von: datetime, bis: datetime) -> list[Termin]:
        return [t for t in self.termine if von <= t.zeitpunkt <= bis]

    # -- Datei ---------------------------------------------------------------
    def speichern(self, pfad: Path | str) -> None:
        datei = Path(pfad)
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(
            json.dumps(
                {
                    "quelle": self.quelle,
                    "geholt_am": (self.geholt_am or datetime.now(UTC)).isoformat(),
                    "termine": [t.to_json() for t in self.termine],
                },
                indent=2,
            )
        )

    @classmethod
    def laden(cls, pfad: Path | str) -> Terminkalender:
        """Kalender von der Platte lesen.

        Ein fehlender oder kaputter Kalender ergibt einen **leeren** - nicht
        einen Fehler. Ein Termin-Overlay ist eine Verbesserung, keine
        Voraussetzung; das System muss ohne es handeln koennen. Gemeldet wird
        es trotzdem, damit es nicht unbemerkt fehlt.
        """
        datei = Path(pfad)
        if not datei.exists():
            log.info("termine.keine_datei", pfad=str(datei))
            return cls()
        try:
            daten = json.loads(datei.read_text())
            return cls(
                [Termin.from_json(t) for t in daten.get("termine", [])],
                quelle=daten.get("quelle", ""),
                geholt_am=(
                    datetime.fromisoformat(daten["geholt_am"])
                    if daten.get("geholt_am")
                    else None
                ),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            log.error("termine.datei_unlesbar", pfad=str(datei), fehler=str(exc))
            return cls()

    def bericht(self) -> str:
        if not self.termine:
            return "Kein Terminkalender geladen - es wird nichts gesperrt."
        je_art: dict[str, int] = {}
        for t in self.termine:
            je_art[t.art.value] = je_art.get(t.art.value, 0) + 1
        ausserplanmaessig = sum(1 for t in self.termine if not t.geplant)
        return (
            f"{len(self.termine)} Termine "
            f"({self.termine[0].zeitpunkt:%Y-%m-%d} bis "
            f"{self.termine[-1].zeitpunkt:%Y-%m-%d}), "
            + ", ".join(f"{k}: {v}" for k, v in sorted(je_art.items()))
            + f", davon {ausserplanmaessig} ausserplanmaessig"
        )


# ---------------------------------------------------------------------------
#  Parser - getrennt vom Abruf, damit sie ohne Netz pruefbar sind
# ---------------------------------------------------------------------------
def fomc_aus_html(html: str) -> list[datetime]:
    """Entscheidungszeitpunkte aus einer Fed-Kalenderseite.

    Gelesen wird der Dateiname der Erklaerung
    (``/newsevents/pressreleases/monetary20200315a.htm``), nicht die
    Sitzungsangabe im Text. Zwei Gruende:

    1. Die Textangabe ist ein **Bereich** ("April/May 30-1"), aus dem sich der
       Tag der Veroeffentlichung erst erschliessen muesste. Der Dateiname ist
       er.
    2. Ausserplanmaessige Ankuendigungen haben keine Sitzungsangabe, aber eine
       Pressemitteilung. Im Maerz 2020 waren das vier - und genau die waren die
       Tage mit den groessten Ausschlaegen.
    """
    import re
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    tage = sorted(
        set(re.findall(r"/newsevents/pressreleases/monetary(\d{8})a\.htm", html))
    )
    zeitpunkte = []
    for tag in tage:
        ortszeit = datetime(
            int(tag[:4]), int(tag[4:6]), int(tag[6:8]), FOMC_STUNDE_NY, tzinfo=ny
        )
        zeitpunkte.append(ortszeit.astimezone(UTC))
    return zeitpunkte


MONATE = {
    m: i + 1
    for i, m in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
    )
}
MONATE.update({m[:3]: i + 1 for m, i in ((k, v - 1) for k, v in MONATE.items())})


def fomc_angekuendigt_aus_html(html: str) -> tuple[list[datetime], int]:
    """Die **angekuendigten** Sitzungstermine - auch die noch nicht gehaltenen.

    ``fomc_aus_html`` liest die Pressemitteilungen und ist damit fuer die
    Vergangenheit die genauere Quelle. Fuer den Livebetrieb ist sie aber
    nutzlos: Eine Sitzung, die noch nicht stattgefunden hat, hat keine
    Pressemitteilung. Ein Termin-Overlay, das nur vergangene Termine kennt,
    sperrt nie - genau das kam beim ersten Abruf heraus, der bei Juli 2026
    endete.

    Gelesen wird zeilenweise, nicht ueber zwei getrennte Listen. Der Grund
    steht in den Daten: Das Jahr 2025 hat eine August-Zeile **ohne**
    Datumsangabe. Zwei parallele Listen (Monate, Daten) waeren ab dort um eins
    verschoben gewesen - September haette den Oktobertermin bekommen und so
    weiter. Ein Fehler, der nirgends auffaellt und jeden Termin um Wochen
    verschiebt. Gefunden beim Nachzaehlen: neun Monate, acht Daten.

    Rueckgabe: die Entscheidungszeitpunkte und die Zahl der uebersprungenen
    Zeilen - Letzteres, damit ein stiller Ausfall zaehlbar bleibt.
    """
    import re
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    zeitpunkte: list[datetime] = []
    uebersprungen = 0

    bloecke = re.split(r'<a id="\d+">(\d{4}) FOMC Meetings</a>', html)
    for jahr_text, block in zip(bloecke[1::2], bloecke[2::2], strict=False):
        jahr = int(jahr_text)
        for zeile in re.split(r'<div class="[^"]*row fomc-meeting"', block)[1:]:
            monat = re.search(
                r"fomc-meeting__month[^>]*>\s*<strong>([A-Za-z/]+)</strong>", zeile
            )
            tag = re.search(
                r"fomc-meeting__date[^>]*>\s*([0-9/*\-\s]+?)\s*</div>", zeile
            )
            if monat is None or tag is None:
                uebersprungen += 1
                continue

            # "March" oder "Apr/May" - bei zwei Monaten gehoert der letzte Tag
            # zum zweiten. "30-1" heisst 30. April bis 1. Mai.
            monatsnamen = monat.group(1).split("/")
            letzter_monat = MONATE.get(monatsnamen[-1].strip())
            if letzter_monat is None:
                uebersprungen += 1
                continue

            tage = re.findall(r"\d+", tag.group(1))
            if not tage:
                uebersprungen += 1
                continue
            letzter_tag = int(tage[-1])

            # Jahreswechsel: "Dec/Jan" liegt schon im Folgejahr.
            jahr_des_termins = jahr
            if len(monatsnamen) > 1 and letzter_monat < MONATE.get(
                monatsnamen[0].strip(), letzter_monat
            ):
                jahr_des_termins += 1

            try:
                ortszeit = datetime(
                    jahr_des_termins,
                    letzter_monat,
                    letzter_tag,
                    FOMC_STUNDE_NY,
                    tzinfo=ny,
                )
            except ValueError:
                uebersprungen += 1
                continue
            zeitpunkte.append(ortszeit.astimezone(UTC))

    return sorted(zeitpunkte), uebersprungen


def fomc_besondere_tage(html: str) -> set[date]:
    """Tage, die die Fed-Seite selbst als besonders kennzeichnet.

    Die Historienseiten schreiben es hin: *"March 15 (unscheduled) Meeting"*,
    *"March 23 (notation vote)"*, *"March 17-18 (cancelled)"*. Das ist eine
    Angabe der Quelle, keine Ableitung von mir.

    Hier stand zuerst eine Schaetzung: Termine mit weniger als drei Wochen
    Abstand zum vorigen gelten als kurzfristig einberufen. Sie war schnell
    geschrieben und falsch - der 3. Maerz 2020 liegt 34 Tage nach dem 29.
    Januar und war trotzdem eine Notfallsitzung. Der Test dazu ist
    durchgefallen, und zwar zu Recht: Er beschrieb die Wirklichkeit, nicht
    meine Formel.

    Zurueckgegeben werden die **Sitzungstage**. Die Erklaerung erscheint am
    letzten Sitzungstag oder am Tag darauf; die Zuordnung erfolgt in
    ``hole_termine`` ueber genau dieses Fenster von einem Tag.

    Was das Fenster nicht faengt: Ankuendigungen, die deutlich spaeter als die
    Sitzung erscheinen - die Sitzung vom 4. Oktober 2019 etwa, deren Erklaerung
    am 11. folgte. Sie bleibt ohne Kennzeichnung. Ein weiteres Fenster waere
    die falsche Antwort: Es faengt eine Handvoll Sonderfaelle und faengt
    zugleich regulaere Sitzungen mit ein. Da die Kennzeichnung nur in der
    Beschreibung steht und **nie** die Sperre beeinflusst, ist die enge
    Variante die richtige.
    """
    import re

    tage: set[date] = set()
    muster = r"<h5[^>]*>\s*([A-Za-z/]+)\s+([0-9\-]+)\s*\((unscheduled|notation vote|cancelled)\)"
    for monat, spanne, _ in re.findall(muster, html):
        jahr_treffer = re.search(r"fomchistorical(\d{4})", html) or re.search(
            r"(\d{4}) FOMC", html
        )
        if jahr_treffer is None:
            continue
        monatsname = monat.split("/")[-1].strip()
        nummer = MONATE.get(monatsname)
        if nummer is None:
            continue
        for tag in re.findall(r"\d+", spanne):
            try:
                tage.add(date(int(jahr_treffer.group(1)), nummer, int(tag)))
            except ValueError:
                continue
    return tage


def planmaessig(
    zeitpunkte: list[datetime], besondere: set[date] | None = None
) -> dict[datetime, bool]:
    """Welche Termine standen im regulaeren Sitzungskalender?

    Nur die von der Quelle gekennzeichneten Tage gelten als besonders - und
    zusaetzlich der Tag danach, weil die Erklaerung zu einer Sitzung am Tag
    darauf erscheinen kann (Sitzung 2. Maerz 2020, Erklaerung am 3.).

    Ohne Kennzeichnung gilt ein Termin als planmaessig. Das ist die
    vorsichtige Richtung: Die Angabe steht nur in der Beschreibung, gesperrt
    wird jeder Termin gleich.
    """
    markiert = besondere or set()
    ergebnis: dict[datetime, bool] = {}
    for z in sorted(zeitpunkte):
        tag = z.date()
        ergebnis[z] = tag not in markiert and (tag - timedelta(days=1)) not in markiert
    return ergebnis


def halbierung_aus_bloecken(bloecke: list[dict], hoehe: int) -> datetime:
    """Zeitstempel eines Blocks aus der mempool.space-Antwort."""
    for block in bloecke:
        if block.get("height") == hoehe:
            return datetime.fromtimestamp(block["timestamp"], UTC)
    raise ValueError(f"Block {hoehe} nicht in der Antwort")


# ---------------------------------------------------------------------------
#  Abruf
# ---------------------------------------------------------------------------
def hole_termine(
    hole_text,
    hole_json,
    *,
    von_jahr: int = 2012,
    bis_jahr: int | None = None,
) -> Terminkalender:
    """Kalender von den kanonischen Quellen zusammenstellen.

    Die beiden Abrufer werden hereingereicht statt hier gebaut: So laesst sich
    der ganze Zusammenbau ohne Netz pruefen - und ein Abruf, der in diesem
    geoblockten Container ohnehin nicht ueberall hinkommt, blockiert nicht die
    Tests.

    **Ein Ausfall einer Quelle leert den Kalender nicht.** Was geholt werden
    konnte, wird behalten; was fehlt, wird gemeldet. Ein halber Kalender sperrt
    weniger als ein voller, aber mehr als keiner.
    """
    bis_jahr = bis_jahr or datetime.now(UTC).year
    termine: list[Termin] = []
    quellen: list[str] = []

    fomc_zeiten: list[datetime] = []
    besondere: set[date] = set()
    for jahr in range(von_jahr, bis_jahr + 1):
        url = FOMC_HISTORIE.format(jahr=jahr)
        try:
            seite = hole_text(url)
        except Exception as exc:
            log.debug("termine.fomc_jahr_uebersprungen", jahr=jahr, fehler=str(exc))
            continue
        fomc_zeiten.extend(fomc_aus_html(seite))
        besondere |= fomc_besondere_tage(seite)
        quellen.append(url)

    # Die laufenden und kommenden Jahre stehen nicht in der Historie.
    #
    # Zwei Lesarten derselben Seite, und beide werden gebraucht: die
    # Pressemitteilungen (genau, aber nur fuer Vergangenes) und die
    # angekuendigten Sitzungen (auch fuer Kommendes). Ohne die zweite endete
    # der erste Abruf bei Juli 2026 - ein Kalender, der nur vergangene Termine
    # kennt, sperrt im Betrieb nie.
    angekuendigt: list[datetime] = []
    try:
        seite = hole_text(FOMC_AKTUELL)
        fomc_zeiten.extend(fomc_aus_html(seite))
        angekuendigt, uebersprungen = fomc_angekuendigt_aus_html(seite)
        if uebersprungen:
            log.warning("termine.zeilen_uebersprungen", anzahl=uebersprungen)
        quellen.append(FOMC_AKTUELL)
    except Exception as exc:
        log.error("termine.fomc_aktuell_fehlt", fehler=str(exc))

    # Die Pressemitteilung ist die genauere Quelle - eine Ankuendigung wird nur
    # uebernommen, wenn fuer diesen Tag keine vorliegt.
    bekannte_tage = {z.date() for z in fomc_zeiten}
    fomc_zeiten.extend(z for z in angekuendigt if z.date() not in bekannte_tage)

    geplant = planmaessig(sorted(set(fomc_zeiten)), besondere)
    for zeitpunkt, ist_geplant in geplant.items():
        termine.append(
            Termin(
                zeitpunkt=zeitpunkt,
                art=Terminart.FOMC,
                beschreibung=(
                    "FOMC-Entscheidung"
                    if ist_geplant
                    else "FOMC-Ankuendigung (kurzfristig)"
                ),
                geplant=ist_geplant,
            )
        )

    for hoehe in HALBIERUNGSHOEHEN:
        url = BLOCK_API.format(hoehe=hoehe)
        try:
            zeitpunkt = halbierung_aus_bloecken(hole_json(url), hoehe)
        except Exception as exc:
            log.error("termine.halbierung_fehlt", hoehe=hoehe, fehler=str(exc))
            continue
        termine.append(
            Termin(
                zeitpunkt=zeitpunkt,
                art=Terminart.HALBIERUNG,
                beschreibung=f"Bitcoin-Halbierung (Block {hoehe})",
            )
        )
        quellen.append(url)

    log.info("termine.geholt", anzahl=len(termine), quellen=len(quellen))
    return Terminkalender(
        termine,
        quelle=f"{len(quellen)} Quellen, u.a. {FOMC_AKTUELL}",
        geholt_am=datetime.now(UTC),
    )
