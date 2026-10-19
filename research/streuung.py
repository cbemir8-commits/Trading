"""Die Zahl, die das strengste Gate traegt - und nie gemessen wurde.

Woran das Projekt seit Wochen scheitert
---------------------------------------
Von elf Gates steht genau eines im Weg, das keine Streichung und keine
Reglerstellung loest: der Deflated Sharpe (Befund 61). Seine Formel hat fuenf
Eingaben - Sharpe je Trade, Stichprobe, Schiefe, Woelbung, Versuchszahl -, und
alle fuenf werden gemessen. **Eine sechste wird angenommen.**

    Ist ``sharpe_variance`` nicht bekannt, wird die asymptotische Varianz
    des Sharpe-Schaetzers ``1/(n-1)`` verwendet.

So steht es in ``research/gates.py``, und so laeuft es seit dem ersten Tag.
``V`` ist in der Formel von Bailey und Lopez de Prado die **Streuung der
Sharpe-Schaetzer ueber die Versuche** - eine Groesse, die man erheben kann,
wenn man aufschreibt, was man probiert hat. Dieses Projekt hat sie nie erhoben.

Wie viel an ihr haengt
----------------------
Alles. Am Spitzenkandidaten gerechnet, alle anderen Eingaben unveraendert:

    sqrt(V) = 0,0814   angenommen         DSR 0,804   durchgefallen
    sqrt(V) = 0,0672   Kippunkt           DSR 0,950   Grenze
    sqrt(V) = 0,0608   aus 28 Versuchen   DSR 0,977   bestanden
    sqrt(V) = 0,0428   aus 23 Versuchen   DSR 0,999   bestanden

Die Annahme liegt **21 % ueber dem Kippunkt**. Das Gate, an dem dieses Projekt
seit Wochen haengt, entscheidet sich an einer Zahl, die niemand gemessen hat.

Warum die gemessene Zahl trotzdem nicht eingesetzt wird
-------------------------------------------------------
Weil sie kein Mass ueber die Versuche ist, sondern ueber eine Auswahl davon -
und die Auswahl ist genau die falsche. Von 166 Versuchen liegen 28 mit ihrem
Sharpe je Trade vor:

* **Berichte schreibt man ueber Reglerscans**, und ein Reglerscan variiert
  einen Knopf um den Bestand herum. Solche Punkte liegen naturgemaess eng
  beieinander - die 23 aus den Berichten spannen 0,133 bis 0,264.
* **Die Verlierer fehlen.** Die vierzehn 15-Minuten-Kandidaten aus Befund 29
  machten -9 bis -44 % im Jahr; ihr Sharpe je Trade ist negativ. Kein Bericht
  haelt ihn fest. Was fehlt, fehlt nicht zufaellig, sondern an einem Ende.
* **Der Bestand zaehlt mehrfach.** Jeder Reglerscan misst auf seiner neutralen
  Stellung denselben Punkt; 0,2597 steht dreimal in den Berichten. Mehrfach
  gezaehlte Mitte drueckt die Streuung zusaetzlich.

Der Beleg dafuer ist keine Behauptung, sondern eine Beobachtung: Die fuenf
Eintraege aus der Bestenliste - strukturell andere Familien, darunter zwei mit
Sharpe je Trade unter 0,05 - heben die Schaetzung von 0,0428 auf 0,0608. **Ein
Sechstel mehr Abdeckung, 42 % mehr Streuung**, und die fehlenden 138 sind
systematisch die schlechteren. Die Schaetzung waechst auf die Annahme zu,
solange man Versuche nachtraegt.

Eine Zahl aus dieser Auswahl in das Gate zu setzen hiesse, die Huerde mit einem
Wert zu senken, von dem man weiss, dass er zu niedrig ist. Das ist der Grund,
warum dieses Modul rechnet und nicht handelt.

Was daraus folgt
----------------
Nicht: "Das Gate ist zu streng." Sondern: **Die Versuche gehoeren
aufgeschrieben.** Hier stand, ``state/trials.json`` enthalte eine einzige
Zahl - und das ist erledigt: Das Verzeichnis haelt zu jedem gebuchten Versuch
seinen Sharpe je Trade, seit Befund 377 aus **jedem** Befehl, der zaehlt
(davor nur aus den Reglerscans um den Bestand, also genau aus der Quelle, die
dieses Modul als zu eng verwirft).

**Und das genuegt nicht.** Gerechnet (Befund 378/379): Der Grundstock aus der
Zeit davor - 192 von 203 Versuchen - kann keinen Punkt nachliefern, und fuer
die verlangten 90 % Abdeckung braeuchte es mindestens 1.217 weitere Versuche,
mit dem gemessenen Anteil 2.814. Das Suchbudget laesst 27 zu. Ob es dafuer
steigt, ist eine Entscheidung und keine Messung.

Bis dahin bleibt die Annahme stehen, und zwar in der strengeren Richtung.

Kostet keinen Versuch: Ausgewertet wird, was ohnehin auf der Platte liegt.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import stdev

from research.gates import deflated_sharpe_ratio
from research.suchbudget import ZIEL

#: Ab welcher Abdeckung eine Streuung ueber die Versuche ueberhaupt eine
#: Streuung ueber die Versuche waere.
#:
#: Nicht 1,0: Ein paar fehlende Versuche verzerren eine Varianz nicht. Aber
#: auch keine 0,5 - denn was fehlt, fehlt hier nicht zufaellig, sondern am
#: unteren Ende. Die Schwelle ist bewusst so hoch, dass sie mit einer
#: Nachtragsliste erreichbar ist und mit Gelegenheitsfunden nicht.
MINDESTABDECKUNG = 0.9


@dataclass(frozen=True, slots=True)
class Versuchspunkt:
    """Ein Versuch, von dem sein Sharpe je Trade bekannt ist."""

    quelle: str
    kennung: str
    sharpe_je_trade: float


def _punkte_aus_bericht(datei: Path) -> list[Versuchspunkt]:
    try:
        daten = json.loads(datei.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    analyse = daten.get("analyse") or {}
    regler = daten.get("regler") or analyse.get("regler") or datei.stem
    punkte = daten.get("punkte") or analyse.get("punkte") or []
    gefunden = []
    for punkt in punkte:
        sharpe = (punkt.get("kennzahlen") or {}).get("sharpe_je_trade")
        # **Auch die Null faellt weg** (Befund 372), mit derselben Begruendung
        # wie in ``aus_bestenliste`` zwei Funktionen weiter unten: Das Feld ist
        # jung, und ``0.0`` heisst dort "nicht erhoben" und nicht "kein
        # Vorteil". Hier stand ``is None`` - eine Null waere als Messung
        # eingegangen, und zwar in die eine Eingabe des haertesten Gates, die
        # nicht gemessen sondern angenommen wird.
        #
        # Gemessen im vorhandenen Bestand: **keine** Null (50 echte Werte, 33
        # Punkte ohne das Feld). Die Wache gilt also dem naechsten Bericht und
        # nicht diesem - in denselben Dateien steht die Null an anderer Stelle
        # sehr wohl, in den Bestenlisten-Eintraegen.
        if not sharpe:
            continue
        gefunden.append(
            Versuchspunkt(
                quelle="Berichte",
                kennung=f"{regler} {float(punkt.get('stellung', 0.0)):g}",
                sharpe_je_trade=float(sharpe),
            )
        )
    return gefunden


def aus_berichten(ordner: Path | str) -> list[Versuchspunkt]:
    """Alle Reglerpunkte, die ihren Sharpe je Trade mittragen.

    Rekursiv ueber ``reports/``: Die Berichtsarten liegen in Unterordnern, und
    welche davon Punkte enthaelt, soll hier nicht noch einmal aufgezaehlt
    werden muessen.
    """
    wurzel = Path(ordner)
    if not wurzel.exists():
        return []
    gefunden: list[Versuchspunkt] = []
    for datei in sorted(wurzel.rglob("*.json")):
        gefunden.extend(_punkte_aus_bericht(datei))
    return gefunden


#: Die kleinste Trade-Zahl, aus der ``Kandidat.aus_trades`` eine Guete macht.
#:
#: Darunter gibt es ``None``, und ``None`` heisst "nicht erhoben". Ein solcher
#: Versuch zaehlt also in ``N`` (er ist eine Hypothese, die geprueft wurde),
#: kann aber nie einen Punkt zur Streuung beitragen. Genau das ist der Grund,
#: warum ``deckel`` eine Obergrenze und keine Erwartung ist.
GUETESCHWELLE = 5

#: Welche Berichtsform die Population der **gebuchten** Versuche abbildet.
#:
#: Nicht alle fuenf (Befund 378). ``nachpruefung`` wiederholt eine Regel auf
#: anderen Maerkten und Zeitraeumen - das sind keine gebuchten Versuche, und
#: dort liegen 113 von 179 Eintraegen unter der Schwelle. Wer alle Formen
#: zusammenwirft, misst 78,2 % statt 94,3 % und haelt die Abdeckung fuer
#: grundsaetzlich unerreichbar, obwohl nur das Budget im Weg steht. Derselbe
#: Fehler wie in Befund 346/348, nur in die andere Richtung: dort wurde eine
#: Form gelesen und fuer alle genommen, hier wurden alle gelesen und fuer die
#: eine genommen.
VERSUCHSFORM = "zulassung"


def anteil_mit_guete(ordner: Path | str, *, form: str = VERSUCHSFORM) -> tuple[int, int]:
    """Wie viele geprüfte Kandidaten tragen ueberhaupt eine Guete?

    Gibt ``(mit, gesamt)`` zurueck, gezaehlt an den Trade-Zahlen der
    Berichtseintraege - nicht geschaetzt. ``deckel`` nimmt an, dass **jeder**
    kuenftige Versuch seinen Sharpe je Trade mitbringt; das ist die eine
    Annahme, die in diesem Modul noch stand, und hier wird sie gemessen.

    Gemessen am vorhandenen Bestand: **8 von 141 unter der Schwelle**, also
    94,3 %. Der Unterschied zum optimistischen Deckel ist am heutigen
    Budgetrest klein (0,7 Punkte) - er waechst mit dem Rest.
    """
    wurzel = Path(ordner)
    if not wurzel.exists():
        return (0, 0)
    mit = gesamt = 0
    for datei in sorted(wurzel.rglob("*.json")):
        if datei.parent.name != form:
            continue
        try:
            daten = json.loads(datei.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for zahl in _tradezahlen(daten):
            gesamt += 1
            if zahl >= GUETESCHWELLE:
                mit += 1
    return (mit, gesamt)


def _tradezahlen(knoten) -> list[int]:
    """Jede ``trades``-Zahl im Bericht, beliebig tief."""
    gefunden: list[int] = []
    if isinstance(knoten, dict):
        for schluessel, wert in knoten.items():
            if schluessel == "trades" and isinstance(wert, (int, float)):
                gefunden.append(int(wert))
            gefunden.extend(_tradezahlen(wert))
    elif isinstance(knoten, list):
        for wert in knoten:
            gefunden.extend(_tradezahlen(wert))
    return gefunden


def aus_bestenliste(pfad: Path | str) -> list[Versuchspunkt]:
    """Die Eintraege der Bestenliste, soweit sie den Sharpe je Trade tragen.

    Das Feld ist jung - aeltere Eintraege haben es nicht, und ``0.0`` heisst
    dort "nicht erhoben" und nicht "kein Vorteil". Es zu uebernehmen wuerde die
    Streuung nach unten faelschen, und zwar dort, wo sie am meisten weh tut.
    """
    datei = Path(pfad)
    if not datei.exists():
        return []
    try:
        daten = json.loads(datei.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    gefunden = []
    for eintrag in daten.get("eintraege") or []:
        sharpe = eintrag.get("sharpe_je_trade")
        if not sharpe:
            continue
        gefunden.append(
            Versuchspunkt(
                quelle="Bestenliste",
                kennung=str(eintrag.get("name") or eintrag.get("genome_id") or "?"),
                sharpe_je_trade=float(sharpe),
            )
        )
    return gefunden


def aus_verzeichnis(pfad: Path | str) -> list[Versuchspunkt]:
    """Die Einzelnachweise aus ``state/trials.json``.

    Die einzige Quelle, die vollstaendig werden **kann**: Sie bekommt jeden
    geprueften Kandidaten, auch den, der nichts taugte. Berichte und
    Bestenliste sammeln beide nur, was jemand aufschreiben wollte.

    Der Grundstock von vor der Einfuehrung des Verzeichnisses steht hier
    nicht - er hat keine Einzelnachweise, und erfundene waeren schlimmer als
    keine.
    """
    from research.versuche import ZaehlerUnlesbarError, laden

    try:
        verzeichnis = laden(pfad)
    except ZaehlerUnlesbarError:
        return []
    return [
        Versuchspunkt(
            quelle="Verzeichnis",
            kennung=v.kennung,
            sharpe_je_trade=float(v.sharpe_je_trade),
        )
        for v in verzeichnis.eintraege
        if v.sharpe_je_trade is not None
    ]


def sammle(
    *, berichte: Path | str, bestenliste: Path | str, verzeichnis: Path | str | None = None
) -> list[Versuchspunkt]:
    """Alles, was ueber die Versuche auf der Platte liegt."""
    gefunden = aus_berichten(berichte) + aus_bestenliste(bestenliste)
    if verzeichnis is not None:
        gefunden += aus_verzeichnis(verzeichnis)
    return gefunden


@dataclass(slots=True)
class Streuung:
    """Was von der Streuung ueber die Versuche bekannt ist - und was nicht."""

    punkte: list[Versuchspunkt] = field(default_factory=list)
    versuche: int = 0
    stichprobe: int = 0
    """Die effektive Trade-Zahl des Kandidaten - Grundlage der Annahme."""

    grenze: int = 0
    """Der Versuchsstand, bei dem das Suchbudget abbricht - ``stand.BUDGET``.

    Nur zum Rechnen der Obergrenze; ``0`` heisst "nicht angegeben". Der Wert
    wird hier nicht hergestellt, weil das Budget eine Abmachung ist und keine
    Messung - er kommt von aussen herein.
    """

    @property
    def gemessen(self) -> float | None:
        """Die Standardabweichung der bekannten Versuchs-Sharpes.

        Bewusst **ohne** Bereinigung um Mehrfachnennungen: Der Bestand steht
        dreimal darin, weil jeder Reglerscan seine neutrale Stellung mitmisst,
        und das drueckt den Wert. Ihn zu bereinigen hiesse, die Schaetzung
        nach oben zu korrigieren - also in die Richtung, die dem eigenen
        Argument nutzt. Der ungebeugte Wert traegt es auch.
        """
        werte = [p.sharpe_je_trade for p in self.punkte]
        return stdev(werte) if len(werte) > 1 else None

    @property
    def angenommen(self) -> float | None:
        """``sqrt(1/(n-1))`` - die Ersatzannahme, die im Gate steht."""
        return (1.0 / (self.stichprobe - 1)) ** 0.5 if self.stichprobe > 1 else None

    @property
    def abdeckung(self) -> float:
        return len(self.punkte) / self.versuche if self.versuche > 0 else 0.0

    @property
    def fehlend(self) -> int:
        return max(0, self.versuche - len(self.punkte))

    @property
    def mehrfach(self) -> int:
        """Wie viele Punkte einen Wert teilen, den es schon gibt."""
        werte = [round(p.sharpe_je_trade, 4) for p in self.punkte]
        return len(werte) - len(set(werte))

    @property
    def verwendbar(self) -> bool:
        """Waere das ueberhaupt eine Streuung **ueber die Versuche**?

        ``False`` heisst nicht "die Zahl ist falsch", sondern "die Zahl misst
        etwas anderes als das, was die Formel verlangt". Und selbst ein
        ``True`` waere keine Freigabe: Die Annahme durch die Messung zu
        ersetzen senkt eine Huerde, und diese Entscheidung faellt nicht hier.
        """
        return self.gemessen is not None and self.abdeckung >= MINDESTABDECKUNG

    @property
    def deckel(self) -> float | None:
        """Die hoechste Abdeckung, die bis zum Budgetende noch erreichbar ist.

        **Befund 340.** Der Registereintrag behauptete seit Befund 69, die
        Abdeckung sei "auf hoechstens 40 % gedeckelt" - als Prosa, ungerechnet.
        Gerechnet ist es einfach: Jeder **kuenftige** Versuch kann einen Punkt
        beitragen, kein vergangener mehr. Der Grundstock hat keine
        Einzelnachweise, und nachtraegliche Berichte waeren erfunden.

        Damit ist die Obergrenze ``(Punkte + Rest) / Grenze``. Sie ist eine
        Obergrenze und keine Erwartung: Sie nimmt an, dass **jeder** der
        verbleibenden Versuche seinen Sharpe je Trade mitbringt.

        ``None``, solange keine Grenze angegeben ist - eine Obergrenze ohne
        Budget waere eine erfundene Zahl.
        """
        return self.deckel_bei(1.0)

    def deckel_bei(self, anteil: float) -> float | None:
        """Dieselbe Obergrenze, wenn nur ``anteil`` der Versuche eine Guete hat.

        **Befund 378.** ``deckel`` nimmt an, dass **jeder** verbleibende
        Versuch seinen Sharpe je Trade mitbringt - die letzte Annahme in
        diesem Modul. ``anteil_mit_guete`` misst sie: Von 141
        Zulassungseintraegen liegen 8 unter ``GUETESCHWELLE``, also 94,3 %.

        ``deckel`` bleibt die optimistische Rechnung, und zwar absichtlich:
        Wer ``erreichbar`` mit ihr beantwortet und **False** bekommt, hat die
        Frage sicher beantwortet - der realistische Deckel liegt darunter und
        kann sie nicht umdrehen. Diese Methode sagt, wie viel die Annahme
        wert ist: am heutigen Budgetrest 0,7 Punkte, bei einem groesseren Rest
        mehr.
        """
        if self.grenze <= 0:
            return None
        rest = max(0, self.grenze - self.versuche)
        return min(1.0, (len(self.punkte) + anteil * rest) / self.grenze)

    def versuche_fuer(self, ziel: float, *, anteil: float = 1.0) -> int | None:
        """Wie viele **weitere** Versuche die Zielabdeckung braeuchte.

        Ohne Budgetgrenze gerechnet, denn das ist die Frage: Nicht "reicht das
        Budget", sondern "wie weit waere es ueberhaupt". ``None``, wenn das
        Ziel auch mit unendlich vielen Versuchen nicht kommt - dann liegt
        ``anteil`` unter dem Ziel, und jeder weitere Versuch bringt den Punkt
        nicht mit, den er in den Nenner stellt.

        Gemessen am heutigen Stand (203 Versuche, 61 Punkte, Ziel 90 %):
        1.217 weitere bei vollem Anteil, **2.814** bei den gemessenen 133 von
        141. Das Budget laesst 27 zu.
        """
        if anteil <= ziel:
            return None
        noetig = (ziel * self.versuche - len(self.punkte)) / (anteil - ziel)
        return max(0, int(noetig + 0.999))

    @property
    def erreichbar(self) -> bool:
        """Laesst ``MINDESTABDECKUNG`` sich im Budget ueberhaupt noch holen?

        ``False`` heisst: Diese Frage entscheidet sich nicht durch
        Weitersuchen. Sie haette ein Verzeichnis gebraucht, das von Anfang an
        mitschreibt.
        """
        deckel = self.deckel
        return deckel is not None and deckel >= MINDESTABDECKUNG

    def je_quelle(self) -> dict[str, tuple[int, float | None, float, float]]:
        """Anzahl, Streuung, Minimum und Maximum je Herkunft.

        Die Aufschluesselung ist das Argument: Reglerscans liegen eng um den
        Bestand, andere Quellen streuen breiter. Wer nur die eine Sorte hat,
        misst die Enge seiner Auswahl und nicht die Streuung seiner Versuche.
        """
        nach: dict[str, list[float]] = {}
        for p in self.punkte:
            nach.setdefault(p.quelle, []).append(p.sharpe_je_trade)
        return {
            quelle: (
                len(werte),
                stdev(werte) if len(werte) > 1 else None,
                min(werte),
                max(werte),
            )
            for quelle, werte in nach.items()
        }

    @property
    def breiteste(self) -> tuple[str, float] | None:
        """Die Quelle mit der groessten Streuung - und wie gross sie ist.

        Sie traegt das Argument: Wenn schon eine einzelne Quelle breiter
        streut als die Annahme, ist nicht die Annahme zu hoch, sondern die
        Zusammenlegung zu schmal.
        """
        kandidaten = [
            (quelle, sd)
            for quelle, (_, sd, _, _) in self.je_quelle().items()
            if sd is not None
        ]
        return max(kandidaten, key=lambda qs: qs[1]) if kandidaten else None

    def tabelle(self) -> str:
        zeilen = [
            f"{'Quelle':<14} {'Punkte':>7} {'Streuung':>10} {'kleinster':>10} "
            f"{'groesster':>10}",
            "-" * 55,
        ]
        for quelle, (anzahl, sd, kleinster, groesster) in sorted(
            self.je_quelle().items()
        ):
            zeilen.append(
                f"{quelle:<14} {anzahl:>7} "
                f"{f'{sd:.4f}' if sd is not None else '-':>10} "
                f"{kleinster:>10.4f} {groesster:>10.4f}"
            )
        gesamt = self.gemessen
        zeilen.append("-" * 55)
        zeilen.append(
            f"{'zusammen':<14} {len(self.punkte):>7} "
            f"{f'{gesamt:.4f}' if gesamt is not None else '-':>10}"
        )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if self.gemessen is None:
            return (
                "Zu wenige bekannte Versuche - ueber die Streuung laesst sich "
                "nichts sagen. Die Annahme im Gate bleibt, was sie ist: eine "
                "Annahme."
            )

        angenommen = self.angenommen
        vergleich = (
            f"Die Annahme im Gate liegt bei {angenommen:.4f}, also "
            f"{angenommen / self.gemessen:.1f}-mal so hoch. "
            if angenommen
            else ""
        )
        mehrfach = (
            f" {self.mehrfach} davon wiederholen einen Wert, den es schon gibt - "
            f"jeder Reglerscan misst auf seiner neutralen Stellung den Bestand."
            if self.mehrfach
            else ""
        )
        breiteste = self.breiteste
        einzelquelle = (
            f"\n\nUnd der Beleg steht in der Tabelle darueber: Die Quelle "
            f"'{breiteste[0]}' streut fuer sich genommen mit {breiteste[1]:.4f} "
            f"und damit **breiter als die Annahme**. Nicht die Annahme ist zu "
            f"hoch - die Zusammenlegung ist zu schmal, weil die engste Quelle "
            f"die meisten Punkte stellt."
            if breiteste is not None
            and angenommen is not None
            and breiteste[1] > angenommen
            else ""
        )

        if self.verwendbar:
            return (
                f"**Die Streuung ueber die Versuche ist messbar geworden.** "
                f"{len(self.punkte)} von {self.versuche} Versuchen liegen vor "
                f"({self.abdeckung:.0%}), ihre Streuung betraegt "
                f"{self.gemessen:.4f}. {vergleich}\n\n"
                f"Das ist ein Befund ueber die **Eingabe**, keine Freigabe: Die "
                f"Annahme durch die Messung zu ersetzen senkt die Huerde des "
                f"strengsten Gates. Diese Entscheidung faellt nicht in einer "
                f"Auswertung."
            )

        return (
            f"**Nicht verwendbar - und die Richtung des Fehlers ist bekannt.** "
            f"Von {self.versuche} Versuchen liegen {len(self.punkte)} mit ihrem "
            f"Sharpe je Trade vor ({self.abdeckung:.0%}); {self.fehlend} fehlen."
            f"{mehrfach}\n\n"
            f"Die Streuung dieser Auswahl betraegt {self.gemessen:.4f}. "
            f"{vergleich}Was fehlt, fehlt aber nicht zufaellig: Berichte "
            f"entstehen ueber Reglerscans, und ein Reglerscan variiert einen "
            f"Knopf um den Bestand herum. Die Verlierer - etwa die vierzehn "
            f"15-Minuten-Kandidaten mit -9 bis -44 % im Jahr - haben nie einen "
            f"Bericht bekommen.{einzelquelle}\n\n"
            f"Eine Streuung, die nur die Mitte kennt, ist zu klein. Sie hier "
            f"einzusetzen wuerde die Huerde mit einem Wert senken, von dem "
            f"bekannt ist, dass er zu niedrig ist. Deshalb bleibt die Annahme "
            f"stehen - sie ist die strengere Richtung.\n\n"
            f"Was fehlte, war ein Verzeichnis - **und das gibt es**: "
            f"'state/trials.json' haelt zu jedem gebuchten Versuch seinen "
            f"Sharpe je Trade fest, seit Befund 377 aus jedem Befehl, der "
            f"zaehlt. Was fehlt, ist die Abdeckung: Der Grundstock aus der "
            f"Zeit davor kann keinen Punkt nachliefern."
            f"{self._deckelsatz()}"
        )

    def _deckelsatz(self) -> str:
        """Und ob sich das im Budget noch aendern kann - Befund 340."""
        deckel = self.deckel
        if deckel is None or self.erreichbar:
            return ""
        rest = max(0, self.grenze - self.versuche)
        return (
            f"\n\n**Und im Suchbudget ist sie nicht mehr zu holen.** Selbst "
            f"wenn jeder der {rest} verbleibenden Versuche seinen Sharpe "
            f"mitbringt, sind es {len(self.punkte) + rest} von {self.grenze} "
            f"Punkten - {deckel:.0%} gegen die verlangten "
            f"{MINDESTABDECKUNG:.0%}. Kein vergangener Versuch kann einen "
            f"Punkt nachliefern: Der Grundstock hat keine Einzelnachweise, "
            f"und nachtraegliche Berichte waeren erfunden. Diese Frage "
            f"entscheidet sich also nicht durch Weitersuchen."
            f"{self._abstandssatz(rest)}"
        )

    def _abstandssatz(self, rest: int) -> str:
        """Und wie weit es waere, wenn das Budget nicht im Weg staende.

        **Befund 379.** Der Satz darueber sagt "im Budget nicht zu holen" -
        richtig, und es fehlt die Groessenordnung. Ohne sie liest sich das wie
        "knapp verpasst"; gerechnet ist es ein Hundertstel.

        'Mindestens', weil die Rechnung jedem kuenftigen Versuch seinen Sharpe
        je Trade zutraut. ``anteil_mit_guete`` misst, wie viele ihn wirklich
        mitbringen - mit dem gemessenen Anteil wird die Zahl groesser, nie
        kleiner.
        """
        noetig = self.versuche_fuer(MINDESTABDECKUNG)
        if noetig is None:
            return ""
        # Die Zahl **einzeln** eindeutschen und nicht den ganzen Satz: Ein
        # 'replace(",", ".")' ueber die Zeichenkette hat hier erst aus
        # "Groessenordnung, damit" ein "Groessenordnung. damit" gemacht.
        zahl = f"{noetig:,}".replace(",", ".")
        return (
            f"\n\nUnd die Groessenordnung, damit das nicht wie 'knapp "
            f"verpasst' aussieht: Fuer die verlangten {MINDESTABDECKUNG:.0%} "
            f"braeuchte es **mindestens {zahl} weitere Versuche** - das "
            f"Budget laesst {rest} zu. 'Mindestens', weil diese Rechnung "
            f"jedem von ihnen seinen Sharpe je Trade zutraut; "
            f"'anteil_mit_guete' misst, wie viele ihn wirklich mitbringen."
        )


@dataclass(frozen=True, slots=True)
class Empfindlichkeit:
    """Wie stark das Urteil des Gates an der angenommenen Streuung haengt."""

    sharpe: float
    stichprobe: int
    versuche: int
    schiefe: float = 0.0
    woelbung: float = 3.0
    ziel: float = ZIEL

    def bei(self, streuung: float) -> float:
        """Der Deflated Sharpe, wenn ``sqrt(V)`` diesen Wert haette."""
        return deflated_sharpe_ratio(
            observed_sharpe=self.sharpe,
            trials=max(self.versuche, 1),
            sample_size=self.stichprobe,
            skew=self.schiefe,
            kurtosis=self.woelbung,
            sharpe_variance=streuung**2,
        )

    def kippunkt(self, *, obergrenze: float = 1.0) -> float | None:
        """Bei welchem ``sqrt(V)`` das Urteil umschlaegt.

        Der Deflated Sharpe faellt mit wachsender Streuung - gesucht ist also
        der groesste Wert, der die Schwelle noch haelt. Gibt es ihn im
        durchsuchten Bereich nicht, ist die Antwort ``None`` und nicht eine
        Randstelle: Ein Kippunkt, den es nicht gibt, darf nicht wie einer
        aussehen.
        """
        unten, oben = 1e-6, obergrenze
        if self.bei(unten) < self.ziel or self.bei(oben) >= self.ziel:
            return None
        for _ in range(200):
            mitte = (unten + oben) / 2
            if self.bei(mitte) >= self.ziel:
                unten = mitte
            else:
                oben = mitte
        return unten

    def tabelle(self, stellen: dict[str, float]) -> str:
        zeilen = [
            f"{'':<22} {'sqrt(V)':>9} {'DSR':>8}  Urteil",
            "-" * 52,
        ]
        for name, wert in sorted(stellen.items(), key=lambda kv: -kv[1]):
            dsr = self.bei(wert)
            zeilen.append(
                f"{name:<22} {wert:>9.4f} {dsr:>8.4f}  "
                f"{'bestanden' if dsr >= self.ziel else 'durchgefallen'}"
            )
        return "\n".join(zeilen)

    def urteil(self, angenommen: float) -> str:
        kipp = self.kippunkt()
        heute = self.bei(angenommen)
        stand = (
            f"Mit der Annahme {angenommen:.4f} steht das Gate bei "
            f"{heute:.4f} - {'bestanden' if heute >= self.ziel else 'durchgefallen'}."
        )
        if kipp is None:
            return (
                f"{stand} Ein Umschlagpunkt liegt nicht im durchsuchten "
                f"Bereich; an dieser Eingabe entscheidet sich hier nichts."
            )
        richtung = "unter" if angenommen > kipp else "ueber"
        # 'darueber' stand hier fest, obwohl die Richtung eine Zeile hoeher
        # gerechnet wird (Befund 340). Heute liegt die Annahme oben und der
        # Satz stimmte zufaellig; mit einer engeren Annahme hiesse es
        # "23 % darueber", wo 23 % darunter gemeint waeren.
        lage = "darueber" if angenommen > kipp else "darunter"
        return (
            f"{stand} Das Urteil kippt bei sqrt(V) = {kipp:.4f}; die Annahme "
            f"liegt {abs(angenommen / kipp - 1):.0%} {lage}.\n\n"
            f"**Damit haengt das strengste Gate des Projekts an einer Zahl, "
            f"die nie gemessen wurde.** Jede Schaetzung {richtung} {kipp:.4f} "
            f"dreht das Ergebnis - und genau deshalb darf sie nicht aus einer "
            f"Auswahl der eigenen Versuche stammen."
        )


@dataclass(frozen=True, slots=True)
class Vereinheitlichung:
    """Die naheliegende Einzeiländerung, die das haerteste Gate kippen wuerde.

    **Worum es geht.** ``deflated_sharpe_ratio`` rechnet an zwei Stellen mit
    der Streuung des Sharpe-Schaetzers:

    * im **Nenner** der Teststatistik, und dort steht bereits die
      verteilungsbewusste Form nach Mertens und Lo,
      ``1 - Schiefe*SR + (Woelbung-1)/4 * SR^2``;
    * in ``V``, der Streuung der Sharpe-Schaetzer **ueber die Versuche**, und
      dort steht ``1/(n-1)`` - dieselbe Groesse unter Normalverteilung.

    Das sieht aus wie ein Versehen: zwei Formen derselben Varianz in einer
    Funktion, eine davon normalverteilt, obwohl die Schiefe daneben gemessen
    dasteht. Die Klammer aus dem Nenner auch in ``V`` einzusetzen waere eine
    Zeile, waere mit Literatur belegbar - und wuerde am Spot-Punkt
    ``sqrt(V)`` um 42 % senken und das Gate von 0,58 auf 0,99 drehen.

    **Warum es trotzdem falsch ist.** ``V`` ist keine Stichprobenvarianz,
    sondern die Streuung der Ergebnisse, die die **Suche** hervorgebracht hat.
    Sie ist eine Eigenschaft des Suchvorgangs, nicht des Gewinners. Im Nenner
    gehoeren die Momente des Gewinners hin - das ist sein Standardfehler. In
    ``V`` gehoeren sie nicht hin, und zwar nicht aus Geschmack:

    Die Klammer faellt monoton mit der Schiefe des Gewinners. Gerechnet am
    Spot-Punkt, nur die Schiefe des Gewinners variiert (und zwar an beiden
    Stellen, wie bei einem anderen Gewinner auch):

        Schiefe    sqrt(V)   DSR heute   DSR vereinheitlicht
        0,0000      0,1057      0,5427      0,4175   strenger
        2,0000      0,0801      0,5562      0,7288
        3,4646      0,0542      0,5827      0,9869   bestanden
        4,7027      0           -           keine Huerde

    Dieselbe "Vereinheitlichung" macht das Gate fuer eine symmetrische
    Strategie **strenger** und loest es ab Schiefe 4,70 **auf** - ab dort ist
    die Klammer negativ, ``V <= 0``, und jeder Kandidat besteht. Die gepruefte
    Groesse wuerde ihre eigene Huerde setzen, und je schiefer sie ist, desto
    niedriger. Ein Lotterielos bestuende dann, **weil** es ein Lotterielos
    ist.

    **Und die Richtung.** ``streuung`` haelt fest, dass die gemessene Streuung
    zu niedrig liegt, weil die Verlierer fehlen, und dass die Annahme deshalb
    in der strengeren Richtung stehen bleibt. 0,0542 liegt mitten im Bereich
    der verworfenen Messung (0,0428 bis 0,0608) - das ist kein unabhaengiger
    Beleg, sondern dieselbe Untertreibung auf einem anderen Weg.

    Dieses Objekt rechnet die Verlockung aus und benennt sie. Es wird dem Gate
    **nicht** uebergeben; ``tests/test_vereinheitlichung.py`` haelt das fest.
    """

    sharpe: float
    stichprobe: int
    versuche: int
    schiefe: float
    woelbung: float
    ziel: float = ZIEL

    def _lage(self, schiefe: float | None = None) -> Empfindlichkeit:
        """Die Empfindlichkeit an diesem Punkt - mit wahlweise anderer Schiefe.

        Die Schiefe geht **an beiden Stellen** ein, wenn sie gesetzt wird: in
        die Klammer fuer ``V`` und in den Nenner der Teststatistik. Sonst
        verglichen man nicht zwei Kandidaten, sondern zwei Buchungen fuer
        denselben - und die Tabelle soll zeigen, was die Aenderung fuer
        verschieden geformte Gewinner tut.
        """
        return Empfindlichkeit(
            sharpe=self.sharpe,
            stichprobe=self.stichprobe,
            versuche=self.versuche,
            schiefe=self.schiefe if schiefe is None else schiefe,
            woelbung=self.woelbung,
            ziel=self.ziel,
        )

    def klammer(self, schiefe: float | None = None) -> float:
        """Die Mertens-Klammer - dieselbe, die im Nenner des Gates steht.

        Ungeklemmt: Wird sie negativ, soll das sichtbar sein und nicht als
        winzige positive Zahl erscheinen. Das Gate klemmt sie bei ``1e-9``,
        weil es dort eine Wurzel zieht; hier ist ihr Vorzeichen das Argument.
        """
        sk = self.schiefe if schiefe is None else schiefe
        return 1 - sk * self.sharpe + (self.woelbung - 1) / 4 * self.sharpe**2

    def angenommen(self) -> float:
        """``sqrt(V)`` wie das Gate es heute einsetzt."""
        return math.sqrt(1.0 / (self.stichprobe - 1))

    def vereinheitlicht(self, schiefe: float | None = None) -> float:
        """``sqrt(V)``, wenn die Klammer aus dem Nenner auch hier stuende."""
        return math.sqrt(max(self.klammer(schiefe), 0.0) / (self.stichprobe - 1))

    def dsr_angenommen(self) -> float:
        return self._lage().bei(self.angenommen())

    def dsr_vereinheitlicht(self, schiefe: float | None = None) -> float:
        return self._lage(schiefe).bei(self.vereinheitlicht(schiefe))

    def kippt(self) -> bool:
        """Wuerde die Aenderung das Urteil des Gates umdrehen?"""
        return (
            self.dsr_angenommen() < self.ziel
            and self.dsr_vereinheitlicht() >= self.ziel
        )

    def huerde_verschwindet_ab(self, *, obergrenze: float = 20.0) -> float | None:
        """Ab welcher Schiefe die Klammer negativ wird - also die Huerde weg.

        Gesucht wird am Gewinner entlang: Alles andere bleibt, nur seine
        Schiefe waechst. Liegt die Stelle nicht im durchsuchten Bereich, ist
        die Antwort ``None`` und nicht die Obergrenze.
        """
        if self.klammer(0.0) <= 0:
            return 0.0
        if self.klammer(obergrenze) > 0:
            return None
        unten, oben = 0.0, obergrenze
        for _ in range(200):
            mitte = (unten + oben) / 2
            if self.klammer(mitte) > 0:
                unten = mitte
            else:
                oben = mitte
        return oben

    def tabelle(self, schiefen: tuple[float, ...] = (0.0, 2.0, 3.4646, 5.0)) -> str:
        zeilen = [
            f"{'Schiefe':>9} {'Klammer':>9} {'sqrt(V)':>9} {'DSR':>8}  Urteil",
            "-" * 55,
        ]
        for sk in schiefen:
            kl = self.klammer(sk)
            if kl <= 0:
                zeilen.append(
                    f"{sk:>9.4f} {kl:>9.4f} {'-':>9} {'-':>8}  keine Huerde"
                )
                continue
            dsr = self.dsr_vereinheitlicht(sk)
            zeilen.append(
                f"{sk:>9.4f} {kl:>9.4f} {self.vereinheitlicht(sk):>9.4f} "
                f"{dsr:>8.4f}  "
                f"{'bestanden' if dsr >= self.ziel else 'durchgefallen'}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        grenze = self.huerde_verschwindet_ab()
        kopf = (
            f"Angenommen sqrt(V) = {self.angenommen():.4f} -> DSR "
            f"{self.dsr_angenommen():.4f}; vereinheitlicht "
            f"{self.vereinheitlicht():.4f} -> DSR "
            f"{self.dsr_vereinheitlicht():.4f}."
        )
        if not self.kippt():
            return (
                f"{kopf} Das Urteil des Gates aendert sich dadurch nicht - "
                f"was die Frage nicht erledigt, sondern nur ihre Dringlichkeit."
            )
        schluss = (
            f"{kopf} **Das Urteil kippt** - und genau deshalb wird die "
            f"Aenderung nicht gemacht. 'V' ist die Streuung der Versuche, "
            f"also eine Eigenschaft der Suche; die Momente des Gewinners "
            f"gehoeren in den Nenner und nicht in die Huerde."
        )
        if grenze is not None:
            schluss += (
                f" Der Beleg steht in der Formel selbst: Ab Schiefe "
                f"{grenze:.2f} wird die Klammer negativ, dann gibt es gar "
                f"keine Huerde mehr. Eine Mehrfachtest-Strafe, die sich "
                f"aufloest, wenn der Gewinner schief genug ist, ist keine."
            )
        return schluss
