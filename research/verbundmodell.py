"""Stimmt die Formel, mit der seit Befund 74 Partner bewertet werden?

Warum das geprueft gehoert
--------------------------
Der ganze Auftrag aus Befund 76 - "ein Partner braucht rund 0,26 Sharpe je
Trade bei 120 Trades" - steht auf ``partnerkarte.verbund_sharpe``. Acht
selbstgebaute Regeln (Befund 77 und 83) wurden daran gemessen und verworfen.
Wenn diese Formel systematisch falsch ist, waren alle acht an der falschen
Latte gemessen.

Am Ende von Befund 85 stand der Verdacht: ``verbund_guete`` nimmt an, dass
Unabhaengigkeit nur die effektive Stichprobe verkleinert. Sie senkt dort nicht
die Streuung - bei wirklich gegenlaeufigen Beinen tut sie das aber.

Drei Zahlen fuer dieselbe Groesse
---------------------------------
Beim Nachsehen kamen sogar **zwei** verschiedene Formeln zum Vorschein, die im
Projekt nebeneinander leben:

``partnerkarte.verbund_sharpe``
    Der trade-gewichtete Schnitt der beiden Sharpes. Damit rechnet die Karte,
    die den Auftrag stellt.

``Verbund.kandidat``
    Der Sharpe der **zusammengeworfenen** Trade-Liste. Damit rechnet der
    Verbund, der die Karte einloest. Bei ungleichen Mittelwerten oder
    Streuungen ist das nicht dieselbe Zahl.

Beide arbeiten auf der Trade-Ebene, und dort gibt es keine Zeitachse. Ob zwei
Beine gleichzeitig oder abwechselnd verdienen, ist in einem Topf voller Trades
nicht zu sehen - genau die Eigenschaft, um die es in Befund 85 ging.

Die dritte Zahl ist die Wirklichkeit: die **Wochenreihe**. Beide Beine auf ein
gemeinsames Zeitraster gelegt, Ertraege je Woche addiert, davon der t-Wert.

Warum der t-Wert die richtige Einheit ist
-----------------------------------------
``Guete = SR/Trade * sqrt(n)`` ist ein t-Wert, und ``SR/Woche * sqrt(Wochen)``
ist derselbe t-Wert auf anderer Achse. Bei **unabhaengigen** Trades sind beide
identisch - das ist nachgerechnet und keine Behauptung: Verteilt man n Trades
auf W Wochen, wird der Mittelwert um n/W kleiner und die Streuung um
sqrt(n/W), und ``sqrt(W)`` hebt den Rest auf.

Die Kontrolle traegt das ganze Modul: Fuer einzelne Beine stimmen beide Achsen
ueberein (Bestand 3,216 gegen 3,102). Ohne sie waere jeder Unterschied beim
Verbund genauso gut ein Artefakt der Aggregation.

Beide Zahlen stehen auf der Einteilung von vor Befund 135. **Fuer diese
Kontrolle ist das gleichgueltig** - verglichen werden zwei Achsen auf
derselben Stichprobe, und die kuerzt beide gleich. Wer den Bestand als Stand
lesen will, findet ihn im Kopf von ``research/verbund.py`` (Befund 140: 2,730).

Was ueber 105 Paare herauskam
-----------------------------
Die erste Fassung rechnete ueber 210 Paare aus 21 Genomen. Sechs davon liefern
identische Trades (``research/entdopplung.py``), also stammte die Haelfte der
Paare aus derselben Regel. Entdoppelt bleiben 15 Regeln und 105 Paare, und
eine der beiden Aussagen kippt:

                          erste Fassung   entdoppelt
    Karte  - echt                +0,238       -0,029
    Topf   - echt                +0,487       +0,221

**Die Karte ist im Mittel nicht zu optimistisch.** Der Satz "der Auftrag aus
Befund 76 war zu milde gestellt" stand in der ersten Fassung und ist falsch -
er beruhte auf der siebenfach gezaehlten Regel.

Was haelt, ist der **zusammengeworfene Topf**: +0,221, zu hoch in 87 % der
Paare. Das ist die Formel, mit der ``Verbund.kandidat`` rechnet.

Und was haelt, ist die eigentliche Aussage - der Fehler der Karte ist nicht
konstant, sondern faehrt auf der Fensterkorrelation:

    Fehler der Karte = 1,283 * rho - 0,112      r = +0,440, t = +4,97

Die Karte stimmt bei rho = +0,09 und sonst nirgends. Das ist kein Zufall,
sondern genau die Annahme, die in ihr steckt: Ein trade-gewichteter Schnitt
kennt keine Korrelation. Der erste Anlauf mass hier +0,752 - dieselbe Aussage,
zu grosse Zahl.

Der Verdacht aus Befund 85 ist damit bestaetigt
-----------------------------------------------
In 42 von 105 Paaren **unterschaetzt** die Karte, und zwar dort, wo die Beine
gegenlaeufig sind. Die deutlichsten Faelle:

    VWAP-Rueckkehr short + Donchian 55/20      Karte -0,177   echt 1,730
    Luecke geschlossen   + Donchian 55/20      Karte +0,469   echt 1,935
    VWAP-Rueckkehr short + Trend 100 Tage      Karte +0,217   echt 1,595

'VWAP-Rueckkehr short' hat -0,123 Sharpe je Trade. Die Karte wirft sie sofort
weg. Als Portfolio-Bein hebt sie einen Verbund auf 1,73. Das ist der
Hedge-Wert, den eine Rechnung ohne Zeitachse nicht sehen kann.

Und warum es trotzdem keinen Weg oeffnet
----------------------------------------
Das beste Paar erreicht **3,585** - dieselbe Zahl vor und nach der
Entdopplung, denn es besteht aus Bestand und Donchian und war nie doppelt. Die
Faustformel aus Befund 71 haette es beinahe zu einem Fund gemacht:

    c(210) = 2,781  ->  Schranke 4,337   (alle Paare gezaehlt)
    c(21)  = 1,922  ->  Schranke 3,549   (nur die Regeln gezaehlt)

Gegen die konservative Schranke liegt 3,585 knapp **darueber** - Abstand 0,036
bei einer Streuung von 0,918, also vier Hundertstel Standardabweichungen. Das
Urteil sagte dann auch prompt "schlaegt die Auswahl". Es ist derselbe Fehler
wie in Befund 71: Die Schranke ist der **Erwartungswert** des Maximums, und
die Haelfte aller reinen Rauschziehungen liegt darueber.

Die richtige Null hat dieselbe Struktur wie die Messung. Jede Wochenreihe wird
zyklisch verschoben - Mittelwert, Streuung und Eigenkorrelation jeder Regel
bleiben exakt erhalten, zerstoert wird nur, **wann** die Regeln zusammen
verdienen:

    gemessen                              3,585
    Nullprobe, Median                     3,682
    Nullprobe, 95. Perzentil              3,731

Der gemessene Wert liegt nicht bloss unter dem Perzentil, sondern unter dem
**Median**: Zufaellig gegeneinander verschobene Regeln ergeben im Schnitt ein
besseres bestes Paar als die echten. Das Zusammenspiel dieser Regeln ist also
nicht neutral, sondern leicht schaedlich - sie verdienen zu gleichzeitig. Die
Entdopplung aendert daran nichts (3,683 gegen 3,682).

Die Korrektur aendert also das **Bild**, nicht den Stand: Die Partnerkarte
sortiert nach der falschen Groesse und uebersieht Hedge-Partner - aber unter
denen, die sie uebersieht, ist keiner, der reicht.

Was das nicht zeigt
-------------------
Der Wochen-t-Wert ist **roh**. Die noetige Guete von 3,629 ist nach
Blockkuerzung definiert; ein roher Wert von 3,585 waere danach kleiner. Wer
beide Zahlen nebeneinanderstellt, vergleicht eine Obergrenze mit einer
Anforderung.

Kostet keinen Versuch: Neu aggregiert werden Trades, die schon gerechnet sind.
Ausgewaehlt wird nichts. Wer eines der Paare als Kandidaten prueft, hat
dagegen eine Auswahl ueber 105 Hypothesen getroffen und muss sie zaehlen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Unter so vielen Paaren traegt keine Aussage ueber den Modellfehler.
MINDESTPAARE = 20

#: Laenge einer Periode in Tagen. Eine Woche ist grob genug, dass einzelne
#: Trades nicht jede Periode fuer sich haben, und fein genug, dass die
#: Zeitstruktur ueberhaupt sichtbar wird.
PERIODE_TAGE = 7


def periodenkanten(trades, *, tage: int = PERIODE_TAGE) -> np.ndarray:
    """Ein gemeinsames Zeitraster ueber alle uebergebenen Trades.

    Gemeinsam ist hier nicht Bequemlichkeit, sondern Bedingung: Zwei Beine auf
    verschiedenen Rastern zu addieren hiesse, ihre Gleichzeitigkeit zu
    zerstoeren - also genau das, was gemessen werden soll.
    """
    if not trades:
        return np.array([], dtype="datetime64[D]")
    zeiten = [np.datetime64(t.exit_time.replace(tzinfo=None), "D") for t in trades]
    return np.arange(
        min(zeiten), max(zeiten) + np.timedelta64(1, "D"), np.timedelta64(tage, "D")
    )


def periodenreihe(trades, kanten: np.ndarray) -> np.ndarray:
    """Die Ertraege einer Regel, je Periode aufsummiert.

    Perioden ohne Trade stehen mit null darin und werden **nicht** entfernt.
    Das ist der Punkt: Eine Regel, die selten handelt, hat viele Nullen, und
    genau daran haengt, dass der t-Wert der Reihe mit dem der Trades
    uebereinstimmt.
    """
    reihe = np.zeros(len(kanten))
    if len(kanten) == 0 or not trades:
        return reihe
    stellen = np.searchsorted(
        kanten,
        np.array([np.datetime64(t.exit_time.replace(tzinfo=None)) for t in trades]),
        side="right",
    ) - 1
    np.add.at(reihe, stellen, np.array([float(t.net_pnl) for t in trades]))
    return reihe


def t_wert(werte) -> float | None:
    """Mittelwert gegen Streuung, mal Wurzel aus der Zahl der Beobachtungen.

    Dieselbe Groesse wie ``Guete``, nur ohne Bindung an die Trade-Achse -
    deshalb laesst sich damit ueberhaupt vergleichen, was auf verschiedenen
    Achsen gerechnet wurde.
    """
    reihe = np.asarray(werte, dtype=float)
    if len(reihe) < 2:
        return None
    streuung = float(reihe.std(ddof=1))
    if streuung == 0:
        return None
    return float(reihe.mean() / streuung * len(reihe) ** 0.5)


@dataclass(frozen=True, slots=True)
class Paar:
    """Zwei Beine, dreimal bewertet - und die Wirklichkeit ist die dritte."""

    a: str
    b: str
    korrelation: float
    karte: float
    """Was ``partnerkarte.verbund_sharpe`` sagt, auf t-Wert gebracht."""
    topf: float
    """Was ``Verbund.kandidat`` sagt: der Sharpe der zusammengeworfenen Liste."""
    echt: float
    """Der t-Wert der gemeinsamen Wochenreihe. Die Vergleichsgroesse."""

    @property
    def kartenfehler(self) -> float:
        return self.karte - self.echt

    @property
    def topffehler(self) -> float:
        return self.topf - self.echt

    @property
    def karte_unterschaetzt(self) -> bool:
        return self.kartenfehler < 0


@dataclass(slots=True)
class Modellpruefung:
    """Wie gut die Partnerkarte den wirklichen Verbund trifft."""

    paare: list[Paar] = field(default_factory=list)
    einzeln: dict[str, tuple[float, float]] = field(default_factory=dict)
    """Je Regel (t auf der Trade-Achse, t auf der Wochenachse). Die Kontrolle:
    Weichen die schon bei einem einzelnen Bein ab, misst der Paarvergleich ein
    Artefakt der Aggregation und nichts sonst."""
    reihen: dict[str, np.ndarray] = field(default_factory=dict)
    """Die Wochenreihen selbst - fuer die Nullprobe. Ohne sie liesse sich nur
    gegen eine Faustformel pruefen, und die reicht hier nicht."""

    @property
    def genug(self) -> bool:
        return len(self.paare) >= MINDESTPAARE

    @property
    def regeln(self) -> int:
        return len({n for p in self.paare for n in (p.a, p.b)})

    @property
    def achsen_stimmen_ueberein(self) -> bool:
        """Trifft die Wochenachse bei einzelnen Beinen die Trade-Achse?

        Die Voraussetzung fuer alles Weitere. Ohne sie waere jeder Unterschied
        beim Verbund genauso gut ein Fehler der Aggregation.
        """
        if not self.einzeln:
            return False
        return max(abs(t - w) for t, w in self.einzeln.values()) < 0.6

    def _fehler(self, welcher: str) -> np.ndarray:
        return np.array([getattr(p, welcher) for p in self.paare])

    @property
    def kartenfehler(self) -> tuple[float, float]:
        """Mittelwert und Anteil der Paare, in denen die Karte zu hoch liegt."""
        f = self._fehler("kartenfehler")
        return float(f.mean()), float((f > 0).mean())

    @property
    def topffehler(self) -> tuple[float, float]:
        f = self._fehler("topffehler")
        return float(f.mean()), float((f > 0).mean())

    @property
    def fehler_faehrt_auf_korrelation(self) -> float | None:
        """Haengt der Fehler der Karte an der Fensterkorrelation?

        Die tragende Messung: Ein trade-gewichteter Schnitt kennt keine
        Korrelation, also muss sein Fehler an ihr haengen, wenn die Korrelation
        wirkt.

        Auf dem entdoppelten Katalog +0,440 ueber 105 Paare (t = +4,97). Der
        erste Anlauf mass +0,752 ueber 210 Paare, von denen die Haelfte aus
        sechs Genomen mit identischen Trades stammte - siehe
        ``research/entdopplung.py``. Die Aussage haelt, die Zahl war zu gross.
        """
        if not self.genug:
            return None
        rho = np.array([p.korrelation for p in self.paare])
        f = self._fehler("kartenfehler")
        if rho.std() == 0 or f.std() == 0:
            return None
        return float(np.corrcoef(rho, f)[0, 1])

    @property
    def kopplung_ist_belegt(self) -> bool:
        """Traegt der Zusammenhang einen Schluss - oder ist er Rauschen?

        Dieselbe Schranke wie in ``partnerkarte.urteil`` seit Befund 75: unter
        |t| = 2 wird nichts geschlossen.
        """
        r = self.fehler_faehrt_auf_korrelation
        n = len(self.paare)
        if r is None or n < 4:
            return False
        # Ein perfekter Zusammenhang ist der staerkste Beleg, nicht der
        # schwaechste - die Abfrage steht hier nur, weil der t-Wert bei
        # |r| = 1 durch null teilt.
        if abs(r) >= 1.0:
            return True
        return abs(r * ((n - 2) / (1 - r * r)) ** 0.5) >= 2.0

    @property
    def gerade(self) -> tuple[float, float, float] | None:
        """Steigung, Abschnitt und der Nulldurchgang des Kartenfehlers.

        Der Nulldurchgang sagt, bei welcher Korrelation die Karte stimmt -
        gemessen bei rho = +0,05, also praktisch bei Unabhaengigkeit.
        """
        if not self.genug:
            return None
        rho = np.array([p.korrelation for p in self.paare])
        f = self._fehler("kartenfehler")
        if rho.std() == 0:
            return None
        steigung, abschnitt = (float(x) for x in np.polyfit(rho, f, 1))
        if steigung == 0:
            return None
        return steigung, abschnitt, -abschnitt / steigung

    @property
    def unterschaetzte(self) -> list[Paar]:
        """Paare, die die Karte zu schlecht bewertet - schlimmste zuerst."""
        return sorted(
            (p for p in self.paare if p.karte_unterschaetzt),
            key=lambda p: p.kartenfehler,
        )

    @property
    def bestes(self) -> Paar | None:
        return max(self.paare, key=lambda p: p.echt) if self.paare else None

    def schranke(self, *, konservativ: bool = False) -> float | None:
        """Was best-of-N allein aus Auswahl erzeugt (Befund 71).

        ``konservativ`` zaehlt nur die zugrundeliegenden Regeln als
        unabhaengige Ziehungen statt aller Paare. Das ist die haertere
        Schranke, denn 210 Paare aus 21 Regeln sind keine 210 unabhaengigen
        Versuche - und wer die weichere nimmt, macht sich das Ergebnis schoen.
        """
        if not self.genug:
            return None
        from research.wettrennen import extremwert

        echt = np.array([p.echt for p in self.paare])
        n = self.regeln if konservativ else len(self.paare)
        return float(echt.mean() + extremwert(n) * echt.std())

    def nullprobe(
        self, *, durchlaeufe: int = 400, saat: int = 20260817
    ) -> tuple[float, float] | None:
        """Wie hoch wird das beste Paar, wenn die Gleichzeitigkeit fehlt?

        Die Faustformel aus Befund 71 reicht hier nicht. Sie liefert den
        **Erwartungswert** des Maximums - und ein Maximum, das ihn knapp
        uebertrifft, ist der Normalfall und kein Fund. Genau das waere hier
        beinahe passiert: 3,585 gegen eine Schranke von 3,549, ein Abstand von
        vier Hundertstel Standardabweichungen, und das Urteil haette "schlaegt
        die Auswahl" gesagt.

        Die richtige Null hat dieselbe Struktur wie die Messung. Jede
        Wochenreihe wird zyklisch verschoben: Mittelwert, Streuung und
        Eigenkorrelation jeder einzelnen Regel bleiben damit exakt erhalten,
        zerstoert wird nur, **wann** die Regeln zusammen verdienen. Was dann
        noch an Maximum uebrig bleibt, ist Auswahl.

        Gibt Median und 95. Perzentil des besten Paares unter dieser Null.
        """
        namen = sorted(self.reihen)
        if len(namen) < 3 or not self.genug:
            return None
        feld = np.array([self.reihen[n] for n in namen], dtype=float)
        wochen = feld.shape[1]
        if wochen < 10:
            return None
        # Mittelwert und Varianz jeder Reihe sind gegen das Verschieben
        # unempfindlich - neu zu rechnen ist je Durchlauf nur, wie die Reihen
        # zueinander liegen.
        mittel = feld.mean(axis=1)
        varianz = feld.var(axis=1, ddof=1)
        oben, unten = np.triu_indices(len(namen), k=1)
        summe = mittel[oben] + mittel[unten]
        eigen = varianz[oben] + varianz[unten]

        wuerfel = np.random.default_rng(saat)
        maxima = np.empty(durchlaeufe)
        for i in range(durchlaeufe):
            versetzt = np.array(
                [np.roll(z, int(v)) for z, v in zip(feld, wuerfel.integers(0, wochen, len(namen)), strict=True)]
            )
            deckung = np.cov(versetzt)
            gemeinsam = eigen + 2 * deckung[oben, unten]
            gueltig = gemeinsam > 0
            werte = np.full(len(summe), -np.inf)
            werte[gueltig] = (
                summe[gueltig] / np.sqrt(gemeinsam[gueltig]) * wochen**0.5
            )
            maxima[i] = werte.max()
        return float(np.median(maxima)), float(np.quantile(maxima, 0.95))

    @property
    def schlaegt_die_auswahl(self) -> bool:
        """Ist das beste Paar besser, als reine Auswahl erklaeren kann?

        Gemessen gegen die Nullprobe, nicht gegen die Faustformel - siehe
        dort, warum. Ohne Reihen bleibt nur die Faustformel, und dann wird sie
        konservativ genommen.
        """
        bestes = self.bestes
        if bestes is None:
            return False
        null = self.nullprobe()
        if null is not None:
            return bestes.echt > null[1]
        grenze = self.schranke(konservativ=True)
        return grenze is not None and bestes.echt > grenze

    def tabelle(self, *, hoechstens: int = 8) -> str:
        zeilen = [
            f"{'Bein A':<26} {'Bein B':<26} {'rho':>6} {'Karte':>7} "
            f"{'Topf':>7} {'echt':>7}",
            "-" * 84,
        ]
        for p in sorted(self.paare, key=lambda x: -x.echt)[:hoechstens]:
            zeilen.append(
                f"{p.a[:26]:<26} {p.b[:26]:<26} {p.korrelation:>+6.2f} "
                f"{p.karte:>7.3f} {p.topf:>7.3f} {p.echt:>7.3f}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.genug:
            return "Zu wenige Paare - ueber das Modell laesst sich nichts sagen."
        if self.einzeln and not self.achsen_stimmen_ueberein:
            groesste = max(abs(t - w) for t, w in self.einzeln.values())
            return (
                f"**Die Kontrolle faellt durch.** Schon bei einzelnen Beinen "
                f"weichen Trade- und Wochenachse um bis zu {groesste:.2f} "
                f"voneinander ab. Damit misst der Paarvergleich die "
                f"Aggregation und nicht das Modell - hier ist nichts zu "
                f"schliessen."
            )

        kf, kanteil = self.kartenfehler
        tf, tanteil = self.topffehler
        # Die Ueberschrift richtet sich nach den Zahlen, nicht umgekehrt. Die
        # erste Fassung behauptete "beide sind zu optimistisch" und druckte
        # daneben -0,029 - der Satz stammte aus einer Stichprobe mit sieben
        # Kopien derselben Regel und blieb stehen, als die Zahl kippte.
        zu_hoch = [
            name
            for name, wert in (("die Partnerkarte", kf), ("der Topf", tf))
            if wert > 0.1
        ]
        if len(zu_hoch) == 2:
            kopf = "**Beide Trade-Formeln sind zu optimistisch.**"
        elif zu_hoch:
            kopf = (
                f"**Von den beiden Trade-Formeln ist nur {zu_hoch[0]} zu "
                f"optimistisch.**"
            )
        else:
            kopf = "**Keine der beiden Trade-Formeln liegt im Schnitt zu hoch.**"
        teil = (
            f"{kopf} Gegen die Wochenreihe gemessen liegt die Partnerkarte im "
            f"Schnitt um {kf:+.3f} daneben (zu hoch in {kanteil:.0%} von "
            f"{len(self.paare)} Paaren), die zusammengeworfene Trade-Liste um "
            f"{tf:+.3f} (zu hoch in {tanteil:.0%})."
        )

        r = self.fehler_faehrt_auf_korrelation
        gerade = self.gerade
        if r is not None and gerade is not None and self.kopplung_ist_belegt:
            steigung, _, null = gerade
            teil += (
                f"\n\n**Der Fehler faehrt auf der Fensterkorrelation** "
                f"(r = {r:+.3f}): Fehler = {steigung:+.3f} * rho, Nulldurchgang "
                f"bei rho = {null:+.3f}. Die Karte stimmt bei Unabhaengigkeit "
                f"und sonst nirgends - was kein Zufall ist, sondern genau die "
                f"Annahme, die in einem gewichteten Schnitt steckt."
            )

        unter = self.unterschaetzte
        if unter:
            schlimm = unter[0]
            teil += (
                f"\n\n**Der Verdacht aus Befund 85 ist bestaetigt:** In "
                f"{len(unter)} von {len(self.paare)} Paaren bewertet die Karte "
                f"zu schlecht, am staerksten '{schlimm.a}' + '{schlimm.b}' - "
                f"Karte {schlimm.karte:.3f} gegen {schlimm.echt:.3f} "
                f"gemessen. Ein gegenlaeufiges Bein hat einen Hedge-Wert, den "
                f"eine Rechnung ohne Zeitachse nicht sehen kann."
            )

        bestes = self.bestes
        if bestes is None:
            return teil
        null = self.nullprobe()
        if null is None:
            return teil
        mitte, oben = null
        if bestes.echt > oben:
            teil += (
                f"\n\n**Und ein Paar schlaegt die eigene Auswahl:** "
                f"'{bestes.a}' + '{bestes.b}' erreicht {bestes.echt:.3f}; "
                f"unter zerstoerter Gleichzeitigkeit liegt das beste Paar bei "
                f"{mitte:.3f}, das 95. Perzentil bei {oben:.3f}. Das gehoert "
                f"gerechnet - und kostet dann einen Versuch samt der Auswahl "
                f"ueber {len(self.paare)} Paare."
            )
        else:
            teil += (
                f"\n\n**Es oeffnet trotzdem keinen Weg.** Das beste Paar von "
                f"{len(self.paare)} erreicht {bestes.echt:.3f}. Verschiebt man "
                f"die Reihen gegeneinander - jede Regel behaelt ihre eigene "
                f"Qualitaet, nur die Gleichzeitigkeit faellt weg -, liegt das "
                f"beste Paar bei {mitte:.3f} und das 95. Perzentil bei "
                f"{oben:.3f}. Der gemessene Wert liegt darunter: Er ist "
                f"Auswahl, nicht Zusammenspiel.\n\n"
                f"Die Korrektur aendert damit das Bild, nicht den Stand. Die "
                f"Partnerkarte sortiert nach der falschen Groesse und "
                f"uebersieht Hedge-Partner - unter denen, die sie uebersieht, "
                f"ist keiner, der reicht."
            )
        return teil


def pruefe(laeufe: dict[str, list], *, tage: int = PERIODE_TAGE) -> Modellpruefung:
    """Alle Paare aus fertigen Trade-Listen dreifach bewerten.

    ``laeufe`` bildet Regelnamen auf Trade-Listen ab. Es wird nichts gerechnet,
    was nicht schon gerechnet war - deshalb kostet das keinen Versuch.
    """
    import itertools

    from research.partnerkarte import verbund_sharpe
    from research.suchbudget import Kandidat

    alle = [t for trades in laeufe.values() for t in trades]
    kanten = periodenkanten(alle, tage=tage)
    reihen = {n: periodenreihe(tr, kanten) for n, tr in laeufe.items()}
    kandidaten = {n: Kandidat.aus_trades(n, tr) for n, tr in laeufe.items()}

    einzeln: dict[str, tuple[float, float]] = {}
    for name, trades in laeufe.items():
        k = kandidaten[name]
        auf_woche = t_wert(reihen[name])
        if k is None or auf_woche is None:
            continue
        einzeln[name] = (k.sharpe_je_trade * len(trades) ** 0.5, auf_woche)

    paare: list[Paar] = []
    for a, b in itertools.combinations(sorted(laeufe), 2):
        ka, kb = kandidaten[a], kandidaten[b]
        if ka is None or kb is None:
            continue
        n1, n2 = len(laeufe[a]), len(laeufe[b])
        echt = t_wert(reihen[a] + reihen[b])
        topf = t_wert([float(t.net_pnl) for t in laeufe[a] + laeufe[b]])
        if echt is None or topf is None:
            continue
        if reihen[a].std() == 0 or reihen[b].std() == 0:
            continue
        karte = verbund_sharpe(
            n1=n1, sr1=ka.sharpe_je_trade, n2=n2, sr2=kb.sharpe_je_trade
        ) * (n1 + n2) ** 0.5
        paare.append(
            Paar(
                a=a, b=b,
                korrelation=float(np.corrcoef(reihen[a], reihen[b])[0, 1]),
                karte=float(karte), topf=topf, echt=echt,
            )
        )
    return Modellpruefung(paare=paare, einzeln=einzeln, reihen=reihen)


__all__ = [
    "MINDESTPAARE",
    "PERIODE_TAGE",
    "Modellpruefung",
    "Paar",
    "periodenkanten",
    "periodenreihe",
    "pruefe",
    "t_wert",
]
