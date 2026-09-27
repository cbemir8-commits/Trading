"""Hat irgendwo ein Gate gar nicht geurteilt? - Befund 346.

``GateResult.passed`` ist wahr, solange ein Gate nicht **durchgefallen** ist,
und ein uebersprungenes Gate ist nicht durchgefallen. Eine Bilanz "9 von 11"
kann damit zwei Dinge heissen: neun Urteile und zwei Durchfaller, oder acht
Urteile, ein Durchfaller und zwei Aussetzer. Befund 321/322 hat das an zwei
Stellen behoben, 332 hat sechzehn weitere Typen aufgelistet, bei denen die
Frage offen blieb, und ausdruecklich nicht gemessen, ob es heute etwas trifft.

Hier wird es gemessen, und zwar an der einzigen Stelle, die es rueckwirkend
hergibt: **den geschriebenen Berichten.**

Was Befund 346 gelesen hat - und was nicht
------------------------------------------
346 hat die **Reglerpunkte** abgesucht: 83 Messpunkte, jeder mit elf Gates, kein
einziger Aussetzer, kleinste Trade-Zahl 75. Der Laborbucheintrag nannte das
"nachgemessen an allem, was geschrieben wurde", und **das war zu viel gesagt.**
Berichte haben fuenf verschiedene Formen, und 346 kannte eine:

    Form            Eintraege  unter Schwelle
    punkte                 83               0   <- das las Befund 346
    kombinationen          60               0
    bestenliste           141              22
    stufen                 91              37
    ergebnisse            179             116
    zusammen              554             175

**175 von 554 Eintraegen liegen unter einer Aussetzschwelle**, und **109 davon
haben null Trades** - jeder von denen steht mit einer Gate-Bilanz da, in
``reports/nachpruefung`` mit "5 von 11". Befund 347 hat die Teststaerke-Form
gefunden, dieser Befund die drei uebrigen.

Die 91 Stufen sind mehr als die 15, die unter dem Schluessel ``stufen`` stehen:
``cli teststaerke`` legt seine Varianten unter ``varianten`` ab, und die zaehlen
mit. Eingeordnet wird deshalb ueber das **Kennungsfeld** und nicht ueber den
Listennamen.

Zwei Arten von Auskunft
-----------------------
**Gemeldet**: Der Eintrag traegt ein Feld ``uebersprungen``. Das ist die harte
Auskunft - und sie steht in **keiner** der 478 Zeilen, weil die Berichte aelter
sind als das Feld (Befund 322) oder es beim Schreiben fallen liessen.

**Erschlossen**: Die Trade-Zahl liegt unter einer Aussetzschwelle - 30 fuer
Regime-Aufteilung und Deflated Sharpe, 20 fuer Monte-Carlo. Dann **muss** ein
Gate ausgesetzt haben, und die Bilanz zaehlt es als bestanden. Das ist ein
Schluss und keine Meldung, und deshalb steht es hier getrennt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

__all__ = ["FORMEN", "SCHWELLEN", "Berichtslage", "Punktlage", "lese"]

#: Die Aussetzschwellen aus ``gates.py`` - Gate zu Mindest-Trade-Zahl.
#:
#: Hier als Daten und nicht als Text, weil aus ihnen ein Schluss gezogen wird:
#: Unter der Schwelle **muss** das Gate ausgesetzt haben.
SCHWELLEN: dict[str, int] = {
    "Regime-Aufteilung": 30,
    "Deflated Sharpe": 30,
    "Monte-Carlo": 20,
}

#: Die Formen, in denen Berichte ihre Eintraege fuehren - Befund 348.
#:
#: Jede Zeile: Listenschluessel, Kennungsfeld, Feld der bestandenen Gates, Feld
#: der Gesamtzahl. Befund 346 kannte nur die erste und hat daraus "alles, was
#: geschrieben wurde" gemacht. Ausgeschrieben statt geraten: Eine neue Form
#: faellt dann auf, statt still auf der harmlosen Seite zu landen.
FORMEN: tuple[tuple[str, str, str, str], ...] = (
    ("punkte", "stellung", "bestanden", "gesamt"),
    ("kombinationen", "maerkte", "bestanden", "gesamt"),
    ("ergebnisse", "name", "bestanden", "gesamt"),
    ("stufen", "anteil", "bestanden", "gesamt"),
    ("bestenliste", "name", "gates_bestanden", "gates_gesamt"),
)


@dataclass(frozen=True, slots=True)
class Punktlage:
    """Ein Messpunkt aus einem Bericht und seine Gate-Auskunft."""

    datei: str
    stellung: float
    trades: int
    gates: int
    uebersprungen: int

    form: str = "punkte"
    """In welcher Form der Bericht diesen Eintrag fuehrt - Befund 348."""

    kennung: str = ""
    """Wie der Eintrag heisst: Stellung, Marktkorb, Regelname, Anteil."""

    @property
    def geurteilt(self) -> int:
        return self.gates - self.uebersprungen

    @property
    def erschlossene_aussetzer(self) -> tuple[str, ...]:
        """Gates, die bei dieser Trade-Zahl ausgesetzt haben **muessen**.

        Ein Schluss aus den Schwellen und keine Meldung - der Bericht sagt es
        nicht, die Zahl laesst nichts anderes zu.
        """
        return tuple(
            name
            for name, schwelle in sorted(SCHWELLEN.items())
            if self.trades < schwelle
        )

    @property
    def zu_gut(self) -> bool:
        """Ist die Bilanz dieses Eintrags zu gut - gemeldet oder erschlossen?"""
        return bool(self.uebersprungen or self.erschlossene_aussetzer)

    @property
    def vollstaendig(self) -> bool:
        return self.uebersprungen == 0 and self.gates > 0

    @property
    def nah_an_der_schwelle(self) -> bool:
        """Liegt die Trade-Zahl so tief, dass ein Aussetzen droht?

        Die Schwellen stehen in ``gates.py``: 30 fuer Regime-Aufteilung und
        Deflated Sharpe, 20 fuer Monte-Carlo. "Nah" heisst hier das Doppelte
        der hoechsten - darunter ist die Frage keine theoretische mehr.
        """
        return self.trades < 60


@dataclass(frozen=True, slots=True)
class Berichtslage:
    """Alle Messpunkte, die auf der Platte liegen."""

    punkte: tuple[Punktlage, ...]

    @property
    def dateien(self) -> int:
        return len({p.datei for p in self.punkte})

    @property
    def mit_aussetzern(self) -> tuple[Punktlage, ...]:
        return tuple(p for p in self.punkte if p.uebersprungen)

    @property
    def knappe(self) -> tuple[Punktlage, ...]:
        return tuple(p for p in self.punkte if p.nah_an_der_schwelle)

    @property
    def kleinste_trade_zahl(self) -> int | None:
        return min((p.trades for p in self.punkte), default=None)

    @property
    def erschlossen(self) -> tuple[Punktlage, ...]:
        """Eintraege, deren Trade-Zahl ein Aussetzen erzwingt - Befund 348."""
        return tuple(p for p in self.punkte if p.erschlossene_aussetzer)

    @property
    def ohne_handel(self) -> tuple[Punktlage, ...]:
        """Eintraege mit **null** Trades - und trotzdem einer Gate-Bilanz."""
        return tuple(p for p in self.punkte if p.trades == 0)

    @property
    def je_form(self) -> dict[str, tuple[int, int]]:
        """Je Berichtsform: Eintraege und davon erschlossene Aussetzer."""
        aus: dict[str, tuple[int, int]] = {}
        for p in self.punkte:
            zahl, betroffen = aus.get(p.form, (0, 0))
            aus[p.form] = (
                zahl + 1,
                betroffen + (1 if p.erschlossene_aussetzer else 0),
            )
        return aus

    def tabelle(self) -> str:
        zeilen = [f"{'Form':<16} {'Eintraege':>9} {'unter Schwelle':>15}", "-" * 42]
        for form, (zahl, betroffen) in sorted(self.je_form.items()):
            zeilen.append(f"{form:<16} {zahl:>9} {betroffen:>15}")
        zeilen.append("-" * 42)
        zeilen.append(
            f"{'zusammen':<16} {len(self.punkte):>9} {len(self.erschlossen):>15}"
        )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.punkte:
            return (
                "Keine Berichte mit Messpunkten - ueber Aussetzer laesst sich "
                "so nichts sagen."
            )
        kopf = (
            f"{len(self.punkte)} Messpunkte aus {self.dateien} Berichten "
            f"angesehen."
        )
        if self.mit_aussetzern:
            namen = ", ".join(
                f"{p.datei} Stellung {p.stellung:g} ({p.uebersprungen} von "
                f"{p.gates})"
                for p in self.mit_aussetzern[:5]
            )
            return (
                f"{kopf} **{len(self.mit_aussetzern)} davon tragen ein Gate "
                f"ohne Urteil** - dort ist die rohe Bilanz zu gut: {namen}. "
                f"Wer sie liest, zaehlt ein uebersprungenes Gate als "
                f"bestanden (Befund 321/322/332)."
            )
        if self.erschlossen:
            ohne = (
                f", {len(self.ohne_handel)} davon mit **null** Trades - und "
                f"trotzdem mit einer Gate-Bilanz"
                if self.ohne_handel
                else ""
            )
            return (
                f"{kopf} **Keiner meldet einen Aussetzer** - kein Eintrag "
                f"traegt ueberhaupt ein Feld dafuer. Aber "
                f"{len(self.erschlossen)} liegen unter einer Aussetzschwelle "
                f"(30 fuer Regime-Aufteilung und Deflated Sharpe, 20 fuer "
                f"Monte-Carlo){ohne}. Dort **muss** ein Gate ausgesetzt haben, "
                f"und die Bilanz zaehlt es als bestanden. Das ist ein Schluss "
                f"aus der Trade-Zahl und keine Meldung (Befund 348)."
            )
        return (
            f"{kopf} **Kein einziger Aussetzer**, und die kleinste Trade-Zahl "
            f"ist {self.kleinste_trade_zahl} gegen Aussetzschwellen von 30 und "
            f"20. Die rohen Bilanzen dieser Punkte sind damit richtig."
            + (
                f" {len(self.knappe)} Punkte liegen unter 60 Trades und waeren "
                f"die ersten, bei denen es kippt."
                if self.knappe
                else " Kein Punkt liegt unter 60 Trades."
            )
        )


def _nach_form(daten: dict) -> list[tuple[str, dict]]:
    """Jeden Eintrag der Datei mit der Form, in der er steht - Befund 348.

    Drei Fundorte: die Liste unmittelbar in der Datei, dieselbe unter
    ``analyse``, und ``varianten`` je Variante (``cli teststaerke`` schreibt
    dort seine Stufen).

    **Eingeordnet wird ueber das Kennungsfeld und nicht ueber den
    Listennamen**: 'varianten' sagt nichts darueber, was drinsteht, und jeden
    Eintrag jeder Form zuzuschlagen zaehlte ihn fuenfmal - beim ersten Anlauf
    zu diesem Befund kamen so 782 statt 478 Eintraege heraus.
    """
    gefunden: list[tuple[str, dict]] = []
    for form, *_ in FORMEN:
        for quelle in (daten, daten.get("analyse") or {}):
            for eintrag in quelle.get(form) or []:
                if isinstance(eintrag, dict):
                    gefunden.append((form, eintrag))
    kennungen = {kennung: form for form, kennung, *_ in FORMEN}
    for teil in (daten.get("varianten") or {}).values():
        for eintrag in teil if isinstance(teil, list) else ():
            if not isinstance(eintrag, dict):
                continue
            form = next(
                (f for k, f in kennungen.items() if k in eintrag), "varianten"
            )
            gefunden.append((form, eintrag))
    return gefunden


def _punkte_der_datei(datei: Path) -> list[Punktlage]:
    try:
        daten = json.loads(datei.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(daten, dict):
        return []
    gefunden: list[Punktlage] = []
    felder = {form: (kennung, gesamt) for form, kennung, _, gesamt in FORMEN}
    for form, eintrag in _nach_form(daten):
        kennungsfeld, gesamtfeld = felder.get(form, ("name", "gesamt"))
        # **Die Gate-Zahl kann an zwei Stellen stehen** (Befund 348): als
        # Objekt je Gate ('punkte') oder als Paar 'bestanden'/'gesamt' (alle
        # uebrigen Formen). Ohne beide Wege bliebe es bei einer von fuenf
        # Formen - genau die Luecke, die 347 gefunden hat.
        gates = eintrag.get("gates")
        if isinstance(gates, dict) and gates:
            zahl = len(gates)
            gemeldet = sum(
                1
                for stand in gates.values()
                if isinstance(stand, dict) and stand.get("uebersprungen")
            )
        elif isinstance(eintrag.get(gesamtfeld), int):
            zahl = int(eintrag[gesamtfeld])
            roh = eintrag.get("uebersprungen")
            gemeldet = len(roh) if isinstance(roh, list) else int(roh or 0)
        else:
            continue
        kennzahlen = eintrag.get("kennzahlen") or {}
        trades = eintrag.get("trades", kennzahlen.get("trades"))
        if trades is None:
            continue
        gefunden.append(
            Punktlage(
                datei=datei.stem,
                stellung=float(eintrag.get("stellung", 0.0) or 0.0),
                trades=int(trades),
                gates=zahl,
                uebersprungen=gemeldet,
                form=form,
                kennung=str(eintrag.get(kennungsfeld, "")),
            )
        )
    return gefunden


def lese(ordner: Path | str) -> Berichtslage:
    """Jeden Messpunkt unter ``ordner`` einsammeln - rekursiv.

    Die Berichtsarten liegen in Unterordnern, und welche davon Punkte
    enthaelt, soll hier nicht noch einmal aufgezaehlt werden muessen (dieselbe
    Begruendung wie in ``streuung.aus_berichten``).
    """
    wurzel = Path(ordner)
    if not wurzel.exists():
        return Berichtslage(punkte=())
    gefunden: list[Punktlage] = []
    for datei in sorted(wurzel.rglob("*.json")):
        gefunden.extend(_punkte_der_datei(datei))
    return Berichtslage(punkte=tuple(gefunden))
