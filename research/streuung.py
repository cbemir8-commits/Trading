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
aufgeschrieben.** ``state/trials.json`` enthaelt eine einzige Zahl. Waere dort
zu jedem Versuch sein Sharpe je Trade vermerkt, waere ``V`` messbar statt
geraten - und erst dann waere die Frage, ob das Gate sie benutzen soll,
ueberhaupt eine Frage. Bis dahin bleibt die Annahme stehen, und zwar in der
strengeren Richtung.

Kostet keinen Versuch: Ausgewertet wird, was ohnehin auf der Platte liegt.
"""

from __future__ import annotations

import json
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
        if sharpe is None:
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


def sammle(
    *, berichte: Path | str, bestenliste: Path | str
) -> list[Versuchspunkt]:
    """Alles, was ueber die Versuche auf der Platte liegt."""
    return aus_berichten(berichte) + aus_bestenliste(bestenliste)


@dataclass(slots=True)
class Streuung:
    """Was von der Streuung ueber die Versuche bekannt ist - und was nicht."""

    punkte: list[Versuchspunkt] = field(default_factory=list)
    versuche: int = 0
    stichprobe: int = 0
    """Die effektive Trade-Zahl des Kandidaten - Grundlage der Annahme."""

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
            f"Was fehlt, ist keine Messung, sondern ein Verzeichnis: "
            f"'state/trials.json' haelt eine einzige Zahl fest. Stuende dort "
            f"zu jedem Versuch sein Sharpe je Trade, waere diese Groesse "
            f"messbar statt geraten."
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
        return (
            f"{stand} Das Urteil kippt bei sqrt(V) = {kipp:.4f}; die Annahme "
            f"liegt {abs(angenommen / kipp - 1):.0%} darueber.\n\n"
            f"**Damit haengt das strengste Gate des Projekts an einer Zahl, "
            f"die nie gemessen wurde.** Jede Schaetzung {richtung} {kipp:.4f} "
            f"dreht das Ergebnis - und genau deshalb darf sie nicht aus einer "
            f"Auswahl der eigenen Versuche stammen."
        )
