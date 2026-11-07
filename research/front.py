"""Alles, was je gemessen wurde - gegen die Linie, die es haette reissen muessen.

Warum diese Frage jetzt dran ist
--------------------------------
Sechzehn Richtungen sind gemessen und geschlossen, und vier davon zeigen
dasselbe Muster: Jeder Weg, der eine Kennzahl verbessert, verschlechtert den
Deflated Sharpe ueber einen anderen Kanal.

    Abkuehlung        weniger handeln  -> Risiko-Gates ja, DSR nein
    Gewinnziel        laenger laufen   -> Streuung waechst, DSR nein
    Adaptive Periode  oefter handeln   -> Aehnlichkeit waechst, DSR nein
    Groessenregler    alles skalieren  -> Qualitaet je Trade unveraendert

Vier Einzelfaelle sind ein Verdacht, keine Aussage. Die Aussage waere: **Kein
Punkt dieser Regelfamilie liegt ueber seiner eigenen Grenzlinie** - und die
laesst sich pruefen, ohne einen einzigen neuen Backtest zu rechnen. Die Punkte
stehen alle schon in ``reports/machbarkeit/``.

Was verglichen wird
-------------------
Zu jeder Trade-Zahl gehoert ein **noetiger Sharpe je Trade**, damit der
Deflated Sharpe 0,95 erreicht (``research/suchbudget.py``). Jeder gemessene
Punkt hat eine Trade-Zahl und einen Sharpe je Trade. Damit laesst sich jeder
Punkt einordnen - und der kleinste Abstand ueber alle ist die ehrlichste Zahl,
die dieses Projekt ueber sich selbst hat.

Was dabei ehrlich bleiben muss
------------------------------
**Und sie sind gegen verschiedene Huerden gerechnet.** Die Berichte reichen von
102 bis 162 Versuchen; ein Punkt vom 8. August stand gegen eine deutlich
mildere Schwelle als einer vom 14. Wer ihre gespeicherten Werte
nebeneinanderlegt, vergleicht Massstaebe statt Messungen - und die aelteren
sehen dabei systematisch besser aus. Gemessen an einem Punkt, der beides
hergibt: 0,860 bei 112 Versuchen gegen 0,804 bei 166, dieselben Trades.

Deshalb wird auf den heutigen Stand umgerechnet, wo die Angaben reichen. Wo
nicht, bleibt der Wert des Laufs stehen und der Punkt wird markiert - eine
erfundene Umrechnung waere schlimmer als eine sichtbare Luecke.

**Und sie tragen ihren Betriebspunkt nicht** (Befund 466). Befund 242 hat das
Feld eingefuehrt und eine Wache dazugestellt, die es fuer die vier
dateischreibenden Berichtsarten erzwingt - gemessen traegt es von den
dreizehn Berichten unter ``reports/machbarkeit`` genau **einer**, die
uebrigen zwoelf sind vor dem Einbau geschrieben. Eine Wache kann nichts
nachtragen, was nie geschrieben wurde.

Der Unterschied ist derselbe, den Befund 242 beschreibt: Zwischen den beiden
Punkten liegen ein Hebel ueber 1,0 und ein Funding ueber null, und daran
haengen zwei Gates. Eine Zusammenfassung ueber Punkte, von denen die meisten
nicht sagen, an welchem Punkt sie entstanden sind, kann deshalb nicht mehr
behaupten als: *so sieht es aus, wenn man sie zusammenlegt*. ``herkunft``
zaehlt das, und ``cli front`` druckt es - nicht um es zu heilen, sondern damit
der Leser es weiss.

Die aelteren Berichte tragen die **Form** der Verteilung nicht mit; dort gilt
die Voreinstellung, also die Form des Spitzenkandidaten. Fuer Punkte derselben
Familie ist das eine brauchbare Naeherung, aber eine Naeherung - und beim
Gewinnziel-Regler, wo sich die Form ueber die Stufen drastisch aendert, waere
sie falsch. Solche Punkte werden deshalb **markiert**, nicht stillschweigend
mitgezaehlt.

Und: Das hier ist eine Aussage ueber die gemessenen Punkte, nicht ueber alle
denkbaren. Es sagt "nichts von dem, was wir probiert haben, reicht" - nicht
"es gibt nichts".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from research.suchbudget import ZIEL, Budget, Kandidat

#: Kennzahlen, ohne die ein Punkt sich nicht einordnen laesst.
NOETIG = ("trades", "sharpe_je_trade")


@dataclass(frozen=True, slots=True)
class Messpunkt:
    """Ein Punkt aus einem Machbarkeitsbericht."""

    regler: str
    stellung: float
    kandidat: Kandidat
    genaehert: bool
    """Trug der Bericht die Form der Verteilung nicht mit?"""

    dsr: float | None = None
    """Der Deflated Sharpe, **wie er im Bericht steht**.

    Das Gate hat ihn mit der wirklichen Verteilung des Punktes gerechnet - und
    gegen den Versuchsstand **jenes Laufs**. Genau daran haengt der naechste
    Punkt.
    """

    versuche: int = 0
    """Der Versuchsstand, gegen den ``dsr`` gerechnet wurde.

    **Ohne ihn vergleicht diese Auswertung Werte gegen verschiedene Huerden.**
    Die Berichte reichen von 102 bis 162 Versuchen; ein Punkt vom 8. August
    steht gegen eine deutlich mildere Schwelle als einer vom 14. Genau dieser
    Fehler wurde fuer die Bestenliste in Befund 50 behoben - in den Berichten
    steckte er weiter, und ``cli front`` hat sie nebeneinandergelegt.

    0 heisst: Der Bericht trug ihn nicht mit. Dann bleibt der gespeicherte
    Wert stehen, und der Punkt ist ueber ``umgerechnet`` als ungenau
    erkennbar.
    """

    @property
    def name(self) -> str:
        return f"{self.regler} {self.stellung:g}"

    @property
    def umrechenbar(self) -> bool:
        """Reichen die Angaben, um den Wert auf einen anderen Stand zu holen?

        Es braucht die Form der Verteilung - ohne Schiefe und Woelbung waere
        die Umrechnung geraten, und ein geratener Wert ist schlimmer als eine
        ehrliche Luecke.
        """
        return (
            self.versuche > 0
            and self.kandidat.schiefe is not None
            and self.kandidat.woelbung is not None
        )

    def dsr_bei(self, versuche: int) -> float | None:
        """Der Deflated Sharpe, wie er bei diesem Versuchsstand aussaehe.

        Dieselbe Umrechnung wie ``leaderboard.Entry.dsr_bei``, und aus
        demselben Grund: Zwei Werte gegen verschiedene Huerden sind keine zwei
        Werte, sondern zwei Massstaebe.
        """
        if not self.umrechenbar:
            return self.dsr
        from research.gates import deflated_sharpe_ratio

        return deflated_sharpe_ratio(
            observed_sharpe=self.kandidat.sharpe_je_trade,
            trials=max(versuche, 1),
            sample_size=self.kandidat.trades,
            skew=self.kandidat.schiefe or 0.0,
            kurtosis=self.kandidat.woelbung or 3.0,
        )


def lade(ordner: Path | str) -> list[Messpunkt]:
    """Alle einordnbaren Punkte aus den Machbarkeitsberichten.

    Beschaedigte oder unvollstaendige Berichte werden uebersprungen, nicht
    geraten: Ein Punkt ohne Sharpe je Trade laesst sich nicht einordnen, und
    eine erfundene Zahl waere schlimmer als ein fehlender Punkt.
    """
    gefunden: list[Messpunkt] = []
    for datei in sorted(Path(ordner).glob("*.json")):
        try:
            daten = json.loads(datei.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        regler = daten.get("regler") or daten.get("analyse", {}).get("regler") or "?"
        punkte = daten.get("punkte") or daten.get("analyse", {}).get("punkte") or []
        for punkt in punkte:
            kennzahlen = punkt.get("kennzahlen") or {}
            if not all(kennzahlen.get(k) for k in NOETIG):
                continue
            schiefe = kennzahlen.get("schiefe")
            woelbung = kennzahlen.get("woelbung")
            gefunden.append(
                Messpunkt(
                    regler=str(regler),
                    stellung=float(punkt.get("stellung", 0.0)),
                    kandidat=Kandidat(
                        name=f"{regler} {punkt.get('stellung', 0.0):g}",
                        trades=int(kennzahlen["trades"]),
                        sharpe_je_trade=float(kennzahlen["sharpe_je_trade"]),
                        schiefe=float(schiefe) if schiefe else None,
                        woelbung=float(woelbung) if woelbung else None,
                    ),
                    genaehert=not (schiefe and woelbung),
                    dsr=_gemessener_dsr(punkt),
                    versuche=int(
                        daten.get("versuche")
                        or daten.get("analyse", {}).get("versuche")
                        or 0
                    ),
                )
            )
    # **Roh zurueckgeben.** ``lade`` ist dem Inhalt der Berichte treu; das
    # Zusammenziehen mehrfach gemessener Stellungen ist Sache der Auswertung
    # und passiert in ``Front`` (Befund 150). Waere es hier, koennte ein
    # anderer Aufrufer ``Front`` an der Entdopplung vorbei fuellen - was beim
    # ersten Anlauf genau so war und erst ein Test gezeigt hat.
    return gefunden


def entdoppelt(punkte: list[Messpunkt]) -> list[Messpunkt]:
    """Dieselbe Reglerstellung nur einmal - **der Lauf gegen die haerteste
    Huerde**.

    Warum das noetig ist (Befund 150): Ein Regler steht in mehreren Berichten,
    weil er mehrfach durchgemessen wurde. ``lade`` hat jeden Lauf als eigenen
    Punkt gezaehlt - 44 Punkte fuer 30 Stellungen.

    Statistisch war das harmlos: Die Wiederholungen tragen **identische**
    Kennzahlen (gleiche Trade-Zahl, gleicher Sharpe je Trade) und
    unterscheiden sich nur im Versuchsstand ihres Laufs. Es gab also nichts
    zu picken.

    In der Anzeige war es das nicht: Die Tabelle zeigt zwoelf Zeilen, und
    davon waren sechs Dubletten. **Vierundzwanzig von dreissig Stellungen
    waren unsichtbar**, darunter ganze Regler - in genau dem Werkzeug, dessen
    Zweck die Breite ist.

    Behalten wird der Lauf mit dem **hoechsten** Versuchsstand: Er ist gegen
    die strengste Huerde gerechnet, und das ist die einzige Richtung, in die
    eine solche Wahl fallen darf.
    """
    beste: dict[str, Messpunkt] = {}
    for punkt in punkte:
        vorher = beste.get(punkt.name)
        if vorher is None or punkt.versuche > vorher.versuche:
            beste[punkt.name] = punkt
    # Reihenfolge des ersten Auftretens - damit die Ausgabe reproduzierbar
    # bleibt und nicht an der Sortierung eines dict haengt.
    reihenfolge = list(dict.fromkeys(p.name for p in punkte))
    return [beste[name] for name in reihenfolge]


def _gemessener_dsr(punkt: dict) -> float | None:
    """Den Gate-Wert aus dem Bericht holen - ohne ihn nachzurechnen."""
    stand = (punkt.get("gates") or {}).get("Deflated Sharpe")
    if not isinstance(stand, dict) or stand.get("uebersprungen"):
        return None
    wert = stand.get("wert")
    return float(wert) if wert is not None else None


@dataclass(slots=True)
class Front:
    """Die gemessene Familie, gegen ihre Grenzlinie gelegt."""

    punkte: list[Messpunkt]
    versuche: int

    def __post_init__(self) -> None:
        # Jede Reglerstellung zaehlt einmal - siehe ``entdoppelt``. Hier und
        # nicht in ``lade``, damit auch ein Aufrufer mit eigener Punktliste
        # keine Dubletten in die Auswertung bekommt (Befund 150).
        self.punkte = entdoppelt(self.punkte)

    @property
    def budget(self) -> Budget:
        return Budget(
            versuche=self.versuche, kandidaten=[p.kandidat for p in self.punkte]
        )

    @property
    def abstaende(self):
        return self.budget.abstaende()

    @property
    def naechster(self):
        return self.budget.naechster

    def dsr_von(self, punkt: Messpunkt) -> float | None:
        """Der Deflated Sharpe dieses Punktes **auf heutigem Versuchsstand**.

        Der springende Punkt der ganzen Auswertung. Die Berichte reichen von
        102 bis 162 Versuchen; wer ihre gespeicherten Werte nebeneinanderlegt,
        vergleicht Massstaebe statt Messungen - und die aelteren sehen dabei
        systematisch besser aus, weil sie gegen eine mildere Schwelle
        gerechnet wurden.
        """
        return punkt.dsr_bei(self.versuche)

    @property
    def unvergleichbar(self) -> list[Messpunkt]:
        """Punkte, deren Wert sich nicht auf heute holen laesst.

        Ihr gespeicherter DSR bleibt stehen - eine Umrechnung zu erfinden
        waere schlimmer als eine ehrliche Luecke. Sie sind hier abrufbar,
        damit die Luecke nicht unsichtbar bleibt.
        """
        return [p for p in self.punkte if p.dsr is not None and not p.umrechenbar]

    @property
    def bestanden(self) -> list[Messpunkt]:
        """Punkte, deren Deflated Sharpe die Schwelle erreicht - auf heute
        gerechnet, damit alle gegen dieselbe Huerde stehen."""
        return [
            p
            for p in self.punkte
            if (wert := self.dsr_von(p)) is not None and wert >= ZIEL
        ]

    @property
    def bester(self) -> Messpunkt | None:
        mit = [p for p in self.punkte if self.dsr_von(p) is not None]
        return max(mit, key=lambda p: self.dsr_von(p) or 0.0) if mit else None

    def tabelle(self, *, hoechstens: int = 12) -> str:
        # **Die Spalten sind Untergrenzen** (Befund 149). Die Messpunkte
        # kommen aus gespeicherten Kennzahlen und tragen nur ihre rohe
        # Trade-Zahl; die effektive Stichprobe steht dort nicht und laesst
        # sich aus Kennzahlen auch nicht nachrechnen. Das Gate rechnet mit
        # ihr, und sie ist kleiner - die wirkliche Latte liegt also hoeher.
        zeilen = [
            f"{'Punkt':26} {'Trades':>7} {'hat':>8} {'noetig':>9} {'Faktor':>8} "
            f"{'DSR':>7}  "
        ]
        gemessen = {p.kandidat.name: self.dsr_von(p) for p in self.punkte}
        ungenau = {p.kandidat.name for p in self.unvergleichbar}
        geordnet = sorted(
            self.abstaende,
            key=lambda a: a.faktor if a.faktor is not None else float("inf"),
        )
        genaehert = {p.kandidat.name for p in self.punkte if p.genaehert}
        for a in geordnet[:hoechstens]:
            # ``als_zahl``/``als_faktor`` tragen die Lesart mit; ein blankes
            # ``a.noetig`` verliert sie (Befund 149).
            noetig = a.als_zahl(kurz=True)
            faktor = a.als_faktor(kurz=True)
            marke = " ~" if a.kandidat.name in genaehert else ""
            if a.kandidat.name in ungenau:
                marke += " !"
            wert = gemessen.get(a.kandidat.name)
            dsr = f"{wert:.3f}" if wert is not None else "  -"
            zeilen.append(
                f"{a.kandidat.name[:26]:26} {a.kandidat.trades:>7} "
                f"{a.kandidat.sharpe_je_trade:>8.4f} {noetig:>9} {faktor:>8} "
                f"{dsr:>7}{marke}"
            )
        return "\n".join(zeilen)

    def _warum_kein_faktor(self) -> str:
        """Warum kein Punkt einen Faktor hergibt - **gezaehlt, nicht geraten**.

        ``Abstand.faktor`` ist ``None`` aus **zwei** Gruenden: ``noetig`` ist
        ``None``, weil bei dieser Stichprobe kein Sharpe genuegt - oder der
        Kandidat hat keinen positiven Vorteil, sodass ein Faktor gar nicht
        definiert ist.

        **Bis Befund 445 nannte der Satz hier nur den ersten** ("keiner mit
        einer Trade-Zahl, bei der das Gate ueberhaupt erreichbar waere"). Das
        ist eine Aussage ueber die Stichprobe, und sie stand auch dann da,
        wenn die Stichprobe reichte und schlicht der Vorteil fehlte - zwei
        Ursachen, eine davon den Daten zugeschrieben, die andere dem
        Kandidaten. ``Abstand.als_satz`` unterscheidet sie seit jeher.
        """
        abstaende = self.abstaende
        ohne_latte = sum(1 for a in abstaende if a.noetig is None)
        ohne_vorteil = sum(
            1
            for a in abstaende
            if a.noetig is not None and a.kandidat.sharpe_je_trade <= 0
        )
        teile = []
        if ohne_latte:
            teile.append(
                f"Bei {ohne_latte} genuegt bei dieser Stichprobe kein Sharpe"
            )
        if ohne_vorteil:
            teile.append(
                f"{ohne_vorteil} haben keinen positiven Vorteil je Trade, "
                f"womit ein Faktor nicht definiert ist"
            )
        if not teile:
            return "Der Grund steht nicht in den Abstaenden."
        return "; ".join(teile) + "."

    def urteil(self) -> str:
        if not self.punkte:
            return "Keine einordenbaren Messpunkte gefunden."
        nah = self.naechster
        if nah is None or nah.faktor is None:
            return (
                f"{len(self.punkte)} Punkte gemessen, fuer keinen laesst sich "
                f"ein Faktor zur Schwelle rechnen. {self._warum_kein_faktor()}"
            )
        if self.bestanden:
            namen = ", ".join(p.name for p in self.bestanden[:3])
            return (
                f"{len(self.bestanden)} von {len(self.punkte)} Punkten "
                f"erreichen die Schwelle: {namen}. Das ist ein Befund, keine "
                f"Zulassung - jeder davon muss durch alle elf Gates."
            )
        bester = self.bester
        hoechster = ""
        if bester is not None:
            wert = self.dsr_von(bester)
            hoechster = (
                f" Der hoechste Deflated Sharpe der Familie liegt bei "
                f"{wert:.3f} ('{bester.name}') gegen eine Schwelle von "
                f"{ZIEL:.2f} - gerechnet auf den heutigen Stand von "
                f"{self.versuche} Versuchen, nicht auf den des jeweiligen "
                f"Laufs."
            )
        ungenau = self.unvergleichbar
        if ungenau:
            hoechster += (
                f" ({len(ungenau)} Punkte tragen die Form ihrer Verteilung "
                f"nicht mit und stehen mit dem Wert ihres Laufs da - in der "
                f"Tabelle mit '!' markiert.)"
            )
        return (
            f"**Kein einziger von {len(self.punkte)} gemessenen Punkten "
            f"erreicht die Schwelle.**{hoechster} Am naechsten an der "
            f"Grenzlinie lag '{nah.kandidat.name}' mit {nah.kandidat.trades} "
            f"Trades zu je {nah.kandidat.sharpe_je_trade:.4f}; noetig waeren "
            f"{nah.als_zahl()}, also Faktor {nah.als_faktor()}. Die "
            f"Messpunkte tragen nur ihre rohe Trade-Zahl, nicht die "
            f"effektive Stichprobe des Gates - die Latte liegt also hoeher "
            f"als hier steht (Befund 149)."
        )


@dataclass(frozen=True, slots=True)
class Herkunftslage:
    """Wie viele der Berichte ihren Betriebspunkt nennen - und welchen.

    **Befund 466.** Nicht der Punkt selbst ist das Ergebnis, sondern wie
    gut er belegt ist. Eine Zusammenfassung ueber Messungen verschiedener
    Handelsbedingungen ist nicht falsch - sie ist nur etwas anderes als eine
    Messung, und der Unterschied gehoert in die Ausgabe.
    """

    gesamt: int
    genannt: tuple[tuple[str, int], ...] = ()
    """Die genannten Punkte mit ihrer Anzahl, haeufigster zuerst."""

    @property
    def ohne(self) -> int:
        return self.gesamt - sum(n for _, n in self.genannt)

    @property
    def eindeutig(self) -> bool:
        """Nennen **alle** Berichte denselben Punkt?"""
        return self.gesamt > 0 and self.ohne == 0 and len(self.genannt) == 1

    @property
    def gemischt(self) -> bool:
        """Nennen zwei Berichte **verschiedene** Punkte?"""
        return len(self.genannt) > 1

    def satz(self) -> str:
        """Ein Satz fuer die Ausgabe - oder einer, der nichts behauptet."""
        if not self.gesamt:
            return "Keine Berichte."
        if self.eindeutig:
            return (
                f"Alle {self.gesamt} Berichte nennen denselben Betriebspunkt: "
                f"{self.genannt[0][0]}."
            )
        namen = ", ".join(f"{name} ({n})" for name, n in self.genannt)
        if self.gemischt:
            return (
                f"**Verschiedene Betriebspunkte in einer Tafel**: {namen}"
                + (f", {self.ohne} ohne Angabe" if self.ohne else "")
                + ". Zwischen den Punkten liegen ein Hebel und ein Funding, "
                "und daran haengen zwei Gates (Befund 242) - diese Zeilen "
                "gegeneinander zu lesen ist der Fehler aus Befund 428."
            )
        return (
            f"**{self.ohne} von {self.gesamt} Berichten nennen ihren "
            f"Betriebspunkt nicht**"
            + (f"; genannt wird {namen}" if self.genannt else "")
            + ". Das Feld gibt es seit Befund 242; was davor geschrieben "
            "wurde, traegt es nicht und laesst sich nicht nachtragen. Die "
            "Zusammenfassung gilt also fuer die Punkte, wie sie zusammen "
            "liegen, und nicht fuer einen Betriebspunkt."
        )


def herkunft(ordner: Path | str) -> Herkunftslage:
    """Zaehlt, wie viele Machbarkeitsberichte ihren Betriebspunkt nennen.

    Gezaehlt werden **Berichte**, nicht Messpunkte: Das Feld steht je Bericht,
    und ein Bericht ohne Angabe macht alle seine Punkte ungewiss, nicht einen.

    Beschaedigte Dateien werden uebersprungen - wie in ``lade``, und aus
    demselben Grund: Eine geratene Herkunft waere schlimmer als eine gezaehlte
    Luecke.
    """
    from collections import Counter

    gezaehlt: Counter[str] = Counter()
    gesamt = 0
    for datei in sorted(Path(ordner).glob("*.json")):
        try:
            daten = json.loads(datei.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        gesamt += 1
        punkt = daten.get("betriebspunkt")
        if isinstance(punkt, str) and punkt.strip():
            gezaehlt[punkt.strip()] += 1
    return Herkunftslage(
        gesamt=gesamt,
        genannt=tuple(sorted(gezaehlt.items(), key=lambda kv: (-kv[1], kv[0]))),
    )
