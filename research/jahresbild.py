"""Woraus besteht das schlechteste Jahr?

Warum ausgerechnet dieses Gate
------------------------------
Von den vier Gates, an denen der Spitzenkandidat am **berichteten** Punkt
scheitert, ist "Schlechtestes Jahr" der schmalste Fehlschlag im ganzen System:

    -10,32 % gegen eine Schwelle von -10,00 %

Zweiunddreissig Hundertstel. Das ist die Sorte Abstand, bei der die Frage
"woraus besteht diese Zahl eigentlich" mehr wert ist als jeder weitere
Suchlauf - und sie kostet keinen einzigen Versuch, weil nichts Neues gerechnet
wird. Es wird eine Kurve zerlegt, die ohnehin schon da ist.

**Am massgeblichen Punkt haelt es** - und zwar genauso schmal (Befund 395/396):

    -9,61 % gegen -10,00 %, also 0,39 Punkte Reserve

Die 0,71 Punkte Unterschied sind das Funding, nicht die Reihe: Auf dem
Speicher und auf der Zulassungsreihe steht dieselbe Zahl, auf vier Stellen.
Und "haelt" ist hier keine Entlastung, sondern dieselbe Frage von der anderen
Seite - deshalb zerlegt dieses Modul seit Befund 396 auch das bestandene Gate.

Zwei Fragen, zwei sehr verschiedene Lagen
-----------------------------------------
* **Eine Spitze.** Genau ein Zwoelfmonatsfenster liegt unter der Schwelle, die
  anderen hundert daneben nicht. Dann haengt der Fehlschlag an einer einzelnen
  unguenstigen Ausrichtung, und die naechste Datenreihe legt sie anders.
* **Eine Hochebene.** Ein Viertel aller Fenster liegt darunter. Dann ist es
  eine Eigenschaft der Strategie, und keine Variante wird sie los.

Der Unterschied entscheidet, ob an dieser Stelle weiter gesucht werden sollte.
Das Gate selbst sagt ihn nicht - es gibt nur das Minimum zurueck.

Und eine Pruefung der Rechnung selbst
-------------------------------------
``worst_rolling_return`` schaetzt die Fensterbreite ueber **Indizes**:
``spanne = len(kurve) * 12 / gesamtmonate``. Das setzt gleichmaessig verteilte
Kurvenpunkte voraus. Hier wird dieselbe Groesse zusaetzlich am **Kalender**
gerechnet und beides verglichen.

Die Richtung ist unangenehm: Faellt die Kalenderrechnung milder aus, wuerde
eine Korrektur dem Kandidaten ein Gate schenken. Deshalb wird sie gemessen und
berichtet, bevor irgendetwas geaendert wird - und wenn beide Zahlen
uebereinstimmen, ist genau das das Ergebnis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

#: Fensterbreite in Monaten - dieselbe wie im Gate.
MONATE = 12


def verkettete_kurve(report) -> pd.Series:
    """Die Kapitalkurve ueber alle Testfenster, **mit Zeitstempeln**.

    ``backtest.walkforward.chained_curve`` liefert dieselbe Kurve als nacktes
    Array. Fuer das Gate reicht das; fuer die Frage, *wann* das schlechteste
    Jahr lag, nicht. Verkettet wird multiplikativ und identisch: Zwei Fenster
    mit je +10 % ergeben +21 %.
    """
    stuecke: list[pd.Series] = []
    faktor = 1.0

    for fenster in report.windows:
        kurve = getattr(fenster.result, "equity_curve", None)
        if kurve is None or kurve.empty:
            continue
        werte = kurve["equity"].to_numpy(dtype=float)
        if len(werte) < 2 or werte[0] <= 0:
            continue
        zeiten = pd.to_datetime(kurve["time"])
        stuecke.append(pd.Series(faktor * werte / werte[0], index=zeiten))
        faktor = float(stuecke[-1].iloc[-1])

    if not stuecke:
        return pd.Series(dtype=float)
    zusammen = pd.concat(stuecke)
    return zusammen[~zusammen.index.duplicated(keep="last")].sort_index()


def rollierende_jahre(kurve: pd.Series, *, monate: int = MONATE) -> pd.DataFrame:
    """Fuer jeden Startpunkt: Wo stuende man nach zwoelf Monaten?

    Am **Kalender** gerechnet, nicht ueber Indizes. Jeder Punkt der Kurve ist
    ein moeglicher Einstieg; gesucht wird der Wert genau zwoelf Monate spaeter,
    und zwar der letzte Kurvenpunkt bis dahin.
    """
    if len(kurve) < 3:
        return pd.DataFrame(columns=["start", "ende", "rendite_pct"])

    ziel = kurve.index + pd.DateOffset(months=monate)
    # ``searchsorted`` liefert die Einfuegestelle; einer davor ist der letzte
    # Punkt, der noch innerhalb der zwoelf Monate liegt.
    stellen = kurve.index.searchsorted(ziel, side="right") - 1
    gueltig = (stellen > np.arange(len(kurve))) & (ziel <= kurve.index[-1])
    if not gueltig.any():
        return pd.DataFrame(columns=["start", "ende", "rendite_pct"])

    von = np.flatnonzero(gueltig)
    bis = stellen[gueltig]
    werte = kurve.to_numpy(dtype=float)
    return pd.DataFrame(
        {
            "start": kurve.index[von],
            "ende": kurve.index[bis],
            "rendite_pct": (werte[bis] / werte[von] - 1.0) * 100.0,
        }
    )


@dataclass(frozen=True, slots=True)
class Beitrag:
    """Ein Trade im schlechtesten Fenster."""

    zeit: datetime
    symbol: str
    r: float


@dataclass(slots=True)
class Jahresbild:
    """Die Zerlegung des schlechtesten Zwoelfmonatsfensters."""

    schwelle_pct: float
    fenster: pd.DataFrame = field(default_factory=pd.DataFrame)
    beitraege: list[Beitrag] = field(default_factory=list)
    index_wert: float = float("nan")
    """Was das Gate ausrechnet - ueber Indizes geschaetzt."""

    @property
    def schlechtestes(self) -> float:
        if self.fenster.empty:
            return float("nan")
        return float(self.fenster["rendite_pct"].min())

    @property
    def darunter(self) -> int:
        if self.fenster.empty:
            return 0
        return int((self.fenster["rendite_pct"] < self.schwelle_pct).sum())

    @property
    def anteil_darunter(self) -> float:
        if self.fenster.empty:
            return 0.0
        return self.darunter / len(self.fenster)

    @property
    def zeitraum(self) -> tuple[pd.Timestamp, pd.Timestamp] | None:
        if self.fenster.empty:
            return None
        zeile = self.fenster.loc[self.fenster["rendite_pct"].idxmin()]
        return zeile["start"], zeile["ende"]

    @property
    def reserve(self) -> float:
        """Wie weit das schlechteste Fenster **ueber** der Schwelle liegt.

        Negativ heisst durchgefallen. Gemessen am Spot-Punkt: -9,61 gegen
        -10,00, also 0,39 Punkte - und diese Zahl kann nie wachsen, weil das
        Gate das Minimum ueber alle Fenster nimmt (Befund 396).
        """
        if self.fenster.empty:
            return float("nan")
        return self.schlechtestes - self.schwelle_pct

    @property
    def luft(self) -> float:
        """Abstand vom schlechtesten zum naechsten **nicht ueberlappenden**.

        Die Zahl, die "Spitze oder Hochebene" auch dann beantwortet, wenn
        kein Fenster durchfaellt: Am Spot-Punkt sind es 4,57 Punkte
        (-9,61 gegen -5,04), das schlechteste Fenster steht also allein.

        ``nan``, wenn es kein getrenntes Fenster gibt - bei einer Reihe, die
        kaum laenger als zwei Jahre ist, liegt alles im Ueberlappungsbereich.
        """
        zweites = self._zweites()
        if not np.isfinite(zweites) or not np.isfinite(self.schlechtestes):
            return float("nan")
        return zweites - self.schlechtestes

    @property
    def unabhaengige_jahre(self) -> int:
        """Wie viele disjunkte Zwoelfmonatsfenster in der Tafel Platz haben.

        **Gezaehlt, nicht geteilt** (Befund 397). Hier stand
        ``spanne.days // 365``, und das ergab acht statt sieben: Die Tafel
        spannt 2921 Tage, acht Zwoelfmonatsfenster brauchen aber rund 2922.
        Die Schranke fiel damit auf 31,2 % statt 34,8 % - zu guenstig, also in
        die unangenehme Richtung. Gefunden hat es der Rauchtest, weil die Zahl
        im Befehl nicht die aus der Messung war.

        Gezaehlt wird durch Verketten: das erste Fenster, dann das erste, das
        nach seinem Ende beginnt, und so weiter. Das braucht nur die Tafel -
        die Kurve hat dieses Objekt nicht.

        Am Spot-Punkt sind es **sieben**: 2557 gleitende Fenster, sieben
        unabhaengige Beobachtungen.
        """
        if self.fenster.empty:
            return 0
        geordnet = self.fenster.sort_values("start")
        starts = geordnet["start"].to_numpy()
        enden = geordnet["ende"].to_numpy()
        anzahl, grenze = 0, starts[0]
        while True:
            passend = np.flatnonzero(starts >= grenze)
            if not passend.size:
                break
            anzahl += 1
            grenze = enden[passend[0]]
        return anzahl

    def ratenschranke(self, *, irrtum: float = 0.05) -> float:
        """Die obere Schranke der Rate, mit der ein Jahr die Schwelle reisst.

        **Nur sinnvoll, solange kein Fenster darunter liegt.** Dann sind es
        null Treffer aus ``unabhaengige_jahre`` Beobachtungen. Liegt eines
        darunter, laesst sich aus der Zahl der **ueberlappenden** Fenster
        nicht ablesen, wie viele unabhaengige Jahre betroffen sind - dann
        gibt es hier ``nan`` statt einer Zahl, die so aussieht wie eine
        Antwort.
        """
        if self.darunter or self.unabhaengige_jahre <= 0:
            return float("nan")
        from research.jahresrate import schranke

        return schranke(0, self.unabhaengige_jahre, irrtum=irrtum)

    @property
    def abweichung(self) -> float:
        """Wie weit Kalender- und Indexrechnung auseinanderliegen."""
        if not np.isfinite(self.index_wert) or not np.isfinite(self.schlechtestes):
            return float("nan")
        return self.schlechtestes - self.index_wert

    def tabelle(self) -> str:
        if self.fenster.empty:
            return "Keine vollstaendigen Zwoelfmonatsfenster - nichts zu zerlegen."
        r = self.fenster["rendite_pct"]
        zeilen = [
            f"{'Fenster gesamt':22} {len(self.fenster):>8}",
            f"{'davon unter Schwelle':22} {self.darunter:>8}"
            f"   ({self.anteil_darunter:.1%})",
            "",
            f"{'schlechtestes':22} {r.min():>8.2f} %",
            f"{'zweitschlechtestes*':22} {self._zweites():>8.2f} %",
            f"{'Median':22} {r.median():>8.2f} %",
            f"{'bestes':22} {r.max():>8.2f} %",
        ]
        wann = self.zeitraum
        if wann is not None:
            zeilen.append("")
            zeilen.append(
                f"{'schlechtestes Jahr':22} {wann[0]:%Y-%m-%d} bis {wann[1]:%Y-%m-%d}"
            )
        if self.beitraege:
            zeilen += ["", "Die groessten Posten darin:"]
            geordnet = sorted(self.beitraege, key=lambda b: b.r)
            for b in geordnet[:5]:
                zeilen.append(
                    f"  {b.zeit:%Y-%m-%d}  {b.symbol:22} {b.r:>7.2f} R"
                )
            summe = sum(b.r for b in self.beitraege)
            zeilen.append(
                f"  {'':12}{len(self.beitraege):>3} Trades zusammen "
                f"{summe:>7.2f} R"
            )
        return "\n".join(zeilen)

    def _zweites(self) -> float:
        """Das schlechteste Fenster, das sich mit dem schlechtesten **nicht**
        ueberlappt - sonst waere es nur derselbe Einbruch, einen Tag versetzt.
        """
        wann = self.zeitraum
        if wann is None:
            return float("nan")
        start, ende = wann
        getrennt = self.fenster[
            (self.fenster["ende"] < start) | (self.fenster["start"] > ende)
        ]
        if getrennt.empty:
            return float("nan")
        return float(getrennt["rendite_pct"].min())

    def urteil(self) -> str:
        if self.fenster.empty:
            return "Nicht beurteilbar."
        if self.darunter == 0:
            # **Auch das bestandene Gate wird zerlegt** (Befund 396). Hier
            # stand ein Satz, der mit "besteht die Strategie hier" endete -
            # und die Frage, um die es diesem Modul geht, blieb unbeantwortet:
            # Haelt es mit Luft oder an einem einzelnen Fenster? Gemessen am
            # Spot-Punkt haelt es mit 0,39 Punkten, und das naechste getrennte
            # Fenster liegt 4,57 Punkte entfernt - eine Spitze, nur von der
            # anderen Seite.
            satz = (
                f"Kein Zwoelfmonatsfenster unter {self.schwelle_pct:.1f} % - "
                f"am Kalender gerechnet besteht die Strategie hier, mit "
                f"{self.reserve:.2f} Punkten Reserve."
            )
            wann = self.zeitraum
            ort = f" ({wann[0]:%Y-%m} bis {wann[1]:%Y-%m})" if wann else ""
            if np.isfinite(self.luft):
                satz += (
                    f" Das schlechteste Fenster{ort} steht allein: Zum "
                    f"naechsten, das sich mit ihm nicht ueberlappt, sind es "
                    f"{self.luft:.2f} Punkte."
                )
            # Die unbequeme Haelfte, und sie gilt unabhaengig vom Urteil: Das
            # Gate nimmt das Minimum. Ein schlechteres Jahr ersetzt die
            # Reserve, ein besseres holt sie nicht zurueck.
            satz += (
                " Die Reserve ist ein Guthaben: Das Gate nimmt das Minimum "
                "ueber alle Fenster, sie kann also nur kleiner werden."
            )
            # **Und wie oft so ein Jahr vorkommt** (Befund 397). Ohne diese
            # Zahl liest sich "noch nie passiert" wie Sicherheit, und die
            # Fensterzahl verstaerkt das: 2557 klingt nach viel, es sind
            # sieben unabhaengige Jahre.
            grenze = self.ratenschranke(irrtum=0.05)
            if np.isfinite(grenze):
                return satz + (
                    f" Passiert ist es in {self.unabhaengige_jahre} "
                    f"unabhaengigen Jahren nie - das schrankt die Rate auf "
                    f"unter {grenze:.1%} im Jahr (Irrtum 5 %) und ist keine "
                    f"Prognose, sondern die Grenze des Wissens."
                )
            return satz
        anteil = self.anteil_darunter
        wann = self.zeitraum
        ort = f" ({wann[0]:%Y-%m} bis {wann[1]:%Y-%m})" if wann else ""
        if anteil < 0.05:
            return (
                f"**Eine Spitze.** {self.darunter} von {len(self.fenster)} "
                f"Fenstern liegen unter der Schwelle{ort}, das sind "
                f"{anteil:.1%}. Der Fehlschlag haengt an einer einzelnen "
                f"unguenstigen Ausrichtung, nicht an der Strategie."
            )
        return (
            f"**Eine Hochebene.** {self.darunter} von {len(self.fenster)} "
            f"Fenstern liegen unter der Schwelle ({anteil:.1%}){ort}. Das ist "
            f"eine Eigenschaft der Strategie, keine Ausrichtung - eine "
            f"Variante wird sie nicht los."
        )


def zerlege(report, trades, *, schwelle_pct: float, index_wert: float) -> Jahresbild:
    """Das schlechteste Zwoelfmonatsfenster aufschluesseln."""
    kurve = verkettete_kurve(report)
    fenster = rollierende_jahre(kurve)
    bild = Jahresbild(
        schwelle_pct=schwelle_pct, fenster=fenster, index_wert=index_wert
    )

    wann = bild.zeitraum
    if wann is not None:
        start, ende = wann
        bild.beitraege = [
            Beitrag(
                zeit=pd.Timestamp(t.entry_time),
                symbol=str(getattr(t, "symbol", "") or "-"),
                r=float(t.r_multiple),
            )
            for t in trades
            if t.r_multiple is not None
            and start <= pd.Timestamp(t.entry_time) <= ende
        ]
    return bild
