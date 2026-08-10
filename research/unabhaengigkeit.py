"""Wie viele der gezaehlten Trades sind wirklich unabhaengige Beobachtungen?

**Ein Loch im Deflated-Sharpe-Gate - und eine Korrektur an der Korrektur.**

Die Engine kann dieselbe Regel mit mehreren Perioden gleichzeitig handeln, je
Bein ein Anteil. Gemessen am Spitzenkandidaten mit den Faktoren 0,7 / 1,0 / 1,3:

    einzeln    154 Trades   DSR 0,802
    Ensemble   481 Trades   DSR 0,999

Das Gate waere bestanden gewesen - mit einer Regel, die nichts Neues kann. Denn
es zaehlte **rohe Trades**, und die Formel von Bailey und Lopez de Prado setzt
unabhaengige Beobachtungen voraus. Auf ETH korrelierten die Fenstergewinne
zweier Perioden mit 0,884; drei Beine, kaum mehr Information als eines. So
laesst sich das haerteste Gate umgehen, ohne die Strategie zu verbessern:
Position dritteln, dreimal zaehlen.

**Und dann der zweite Teil, der mir fast durchgegangen waere.**

Der erste Anlauf schaetzte die effektive Stichprobe per Block-Bootstrap und kam
am Kandidaten auf 111 von 154. Der Wert wanderte sofort ins Gate, und der
Deflated Sharpe fiel von 0,802 auf 0,534 - die wichtigste Zahl des Projekts,
geaendert auf Grundlage einer einzigen Schaetzung.

Die Gegenprobe gegen eine **bekannte Null** (dieselben Blockgroessen, Werte
durchgemischt, also garantiert unabhaengig) zeigte, dass das nicht traegt:

    echte Messung                     n_eff = 106 von 154
    Null, unabhaengige Werte   Mittel n_eff = 143, Spanne 78 bis 154
    Anteil der Null unter 106                  6,0 %

Bei dreissig Bloecken ungleicher Groesse ist der Schaetzer so verrauscht, dass
er auch ohne jede Abhaengigkeit auf 78 fallen kann. Die beobachtete Kuerzung
liegt im sechsten Perzentil - **nicht von Zufall zu unterscheiden.**

**Daraus die erste Regel:** Nicht kuerzen, wo die Abhaengigkeit nicht von
Zufall zu unterscheiden ist. Eine Strafe, die reines Rauschen mit
sechsprozentiger Wahrscheinlichkeit erzeugt, ist keine Strenge, sondern eine
Muenze.

**Und der dritte Teil: die Schwelle musste weg.**

Umgesetzt war diese Regel als ``if p <= 0,05``. Das ist eine harte Schwelle auf
einer stetigen Groesse, und sie hat dreimal Schaden angerichtet - zuletzt ueber
einen ganzen Regler hinweg:

    Faktor   roh   effektiv    ICC       p     Deflated Sharpe
       0,6   226        151  0,079   0,040               0,467
       0,8   175        115  0,109   0,049               0,344
       1,0   152        152  0,112   0,072               0,851
      1,25   132         81  0,187   0,040               0,071

Der ICC - die eigentliche Abhaengigkeit - steigt dort glatt an. Nur der p-Wert
wandert ueber die Schwelle, und wo er knapp darunter faellt, verschwindet ein
Drittel der Stichprobe. Ein Deflated Sharpe von 0,851 zwischen 0,344 und 0,071
ist keine Kurve, sondern ein Schalter.

**Gekuerzt wird deshalb stetig, kalibriert am 95. Perzentil der Null.** Der
Unterschied zum Median ist der Kern:

* Am **Median** liegt auf unabhaengigen Daten die Haelfte aller Ziehungen
  darueber - unbedingt angewandt bestrafte das die Haelfte aller sauberen
  Messungen. Genau deshalb brauchte es die Schwelle davor, und mit ihr die
  Klippe.
* Am **95. Perzentil** liegt nur jede zwanzigste saubere Ziehung darueber, und
  dann knapp. Die Kuerzung geht dort von selbst gegen null - ohne ``if``.

Gegengeprueft an bekannter Null (unabhaengige Bloecke, vierzig Ziehungen):
**95 % bleiben ungekuerzt**, im Mittel bleiben 99,5 % der Stichprobe, im
schlimmsten Fall 86,5 %. An denselben Reglerstufen wie oben folgt die Kuerzung
jetzt dem ICC statt dem Zufall:

    ICC    0,053   0,079   0,112   0,187   0,375   0,629
    bleibt  100 %    98 %   100 %    97 %    80 %    68 %
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

import numpy as np

#: Mindestzahl Bloecke fuer eine Schaetzung. Darunter ist jede Aussage ueber
#: Abhaengigkeit haltlos.
MIND_BLOECKE = 8

#: Ab wann gilt die Abhaengigkeit als nachgewiesen. Der Anteil der
#: Permutationsziehungen, die mindestens so stark aussehen wie die Messung.
SIGNIFIKANZ = 0.05

#: Wie viele Permutationen fuer die Null.
#:
#: **Hier standen 200, und das war zu wenig - gemessen, nicht vermutet.** Beim
#: Abtasten des Vola-Reglers ergab derselbe Kandidat auf denselben Daten:
#:
#:     Vola-Ziel    ICC       p     gekuerzt
#:          14    0,123   0,085     nein
#:          16    0,128   0,030     JA, 153 -> 100
#:        19,3    0,121   0,060     nein
#:          22    0,124   0,075     nein
#:          25    0,120   0,085     nein
#:
#: Die Abhaengigkeit selbst ist ueber den ganzen Regler konstant - der ICC
#: schwankt um 0,008. Nur der p-Wert wandert ueber die Schwelle, und bei einer
#: Stufe faellt er darunter. Dort stuerzt der Deflated Sharpe von 0,87 auf
#: 0,53: **ein Drittel des wichtigsten Gates, entschieden von Rauschen im
#: Permutationstest.**
#:
#: Bei 200 Ziehungen betraegt der Standardfehler des p-Werts nahe 5 % rund
#: 0,015. Die Schwelle liegt damit innerhalb eines einzigen Standardfehlers -
#: die Entscheidung war ein Muenzwurf. 2000 Ziehungen druecken ihn auf 0,005.
#:
#: Das behebt die Klippe nicht, es macht sie nur reproduzierbar: Eine harte
#: Schwelle auf eine stetige Groesse bleibt eine harte Schwelle. Was daraus
#: folgt, steht in ``Effektivwert.knapp``.
PERMUTATIONEN = 2000


@dataclass(frozen=True, slots=True)
class Effektivwert:
    """Rohe und effektive Zahl der Beobachtungen."""

    roh: int
    effektiv: int
    icc: float = 0.0
    p_wert: float = 1.0
    nachgewiesen: bool = False
    bloecke: int = 0

    @property
    def faktor(self) -> float:
        return self.effektiv / self.roh if self.roh else 1.0

    @property
    def knapp(self) -> bool:
        """Liegt die Abhaengigkeit im Graubereich?

        **Was diese Eigenschaft frueher bedeutete und heute bedeutet.** Sie
        entstand, als eine harte Schwelle ueber die Kuerzung entschied: Dort
        war ein p von 0,049 gegen 0,051 der Unterschied zwischen voller und
        gedrittelter Stichprobe, und das musste angesagt werden.

        Die Schwelle gibt es nicht mehr - gekuerzt wird stetig. Der Hinweis
        bleibt trotzdem, aber als das, was er jetzt ist: eine Auskunft ueber
        die **Datenlage**, nicht ueber eine Entscheidung. In diesem Bereich
        laesst sich Abhaengigkeit weder zeigen noch ausschliessen, und wer die
        Zahl liest, soll das wissen.
        """
        return self.bloecke >= MIND_BLOECKE and SIGNIFIKANZ / 2 <= self.p_wert <= SIGNIFIKANZ * 2

    def bericht(self) -> str:
        if self.bloecke < MIND_BLOECKE:
            return f"{self.roh} Trades - zu wenige Bloecke fuer eine Aussage."
        hinweis = (
            f" Die Abhaengigkeit liegt im Graubereich (p nahe {SIGNIFIKANZ:.2f}) "
            f"- sie laesst sich hier weder zeigen noch ausschliessen. Die "
            f"Kuerzung faellt entsprechend klein aus; das ist eine Aussage "
            f"ueber die Datenlage, nicht ueber die Strategie."
            if self.knapp
            else ""
        )
        # **Nach der tatsaechlichen Kuerzung berichten, nicht nach dem
        # p-Wert.** Seit die Kuerzung stetig ist, gibt es kein "nachgewiesen
        # ja/nein" mehr, an dem sich der Text aufhaengen koennte.
        if self.effektiv < self.roh:
            return (
                f"{self.roh} rohe Trades entsprechen {self.effektiv} "
                f"unabhaengigen ({self.faktor:.0%}). ICC {self.icc:.3f}, "
                f"p = {self.p_wert:.3f}." + hinweis
            )
        return (
            f"{self.roh} Trades, keine messbare Abhaengigkeit "
            f"(ICC {self.icc:.3f}, p = {self.p_wert:.3f}) - es bleibt bei der "
            f"rohen Zahl. Das heisst nicht, dass keine da ist: Bei "
            f"{self.bloecke} Bloecken faellt erst eine deutliche auf." + hinweis
        )


def mittlere_korrelation(beine: dict[str, list[float]]) -> float:
    """Mittlere paarweise Korrelation der Fenstergewinne, bei null gekappt.

    Beschreibend - fuer den Bericht, nicht fuer die Korrektur. Die Korrektur
    laeuft ueber ``designeffekt``, weil die dort gegen eine Null geprueft wird.
    """
    namen = [n for n, werte in beine.items() if len(werte) >= MIND_BLOECKE]
    if len(namen) < 2:
        return 0.0

    laenge = min(len(beine[n]) for n in namen)
    reihen = {n: np.asarray(beine[n][:laenge], dtype=float) for n in namen}

    werte = []
    for a, b in combinations(namen, 2):
        x, y = reihen[a], reihen[b]
        if np.std(x) == 0 or np.std(y) == 0:
            werte.append(1.0)
            continue
        werte.append(float(np.corrcoef(x, y)[0, 1]))

    return max(0.0, float(np.mean(werte))) if werte else 0.0


def _icc(bloecke: list[np.ndarray]) -> tuple[float, float] | None:
    """Intraklassen-Korrelation und Designeffekt, in geschlossener Form.

        m0    = (N - sum(n_i^2)/N) / (k-1)
        ICC   = (MSB - MSW) / (MSB + (m0-1) * MSW)
        deff  = 1 + (N/k - 1) * ICC

    Der uebliche Weg der Stichprobentheorie mit ungleichen Blockgroessen.
    Deterministisch - anders als ein Bootstrap gibt er bei jedem Aufruf
    dasselbe zurueck, und das ist bei einer Groesse, die ueber Zulassung
    entscheidet, keine Nebensaechlichkeit.
    """
    k = len(bloecke)
    n = sum(len(b) for b in bloecke)
    if k < 2 or n <= k:
        return None

    gesamt = np.concatenate(bloecke)
    gesamtmittel = float(gesamt.mean())
    zwischen = sum(len(b) * (float(b.mean()) - gesamtmittel) ** 2 for b in bloecke)
    innen = sum(float(((b - b.mean()) ** 2).sum()) for b in bloecke)

    msb = zwischen / (k - 1)
    msw = innen / (n - k)
    if msw <= 0:
        return None

    m0 = (n - sum(len(b) ** 2 for b in bloecke) / n) / (k - 1)
    nenner = msb + (m0 - 1) * msw
    icc = max(0.0, (msb - msw) / nenner) if nenner > 0 else 0.0
    return icc, 1 + (n / k - 1) * icc


def designeffekt(
    bloecke: list[list[float]],
    *,
    permutationen: int = PERMUTATIONEN,
    saat: int = 20260808,
) -> Effektivwert | None:
    """Effektive Stichprobe - gekuerzt nur bei nachgewiesener Abhaengigkeit.

    Die Permutationsnull ist der Kern: Dieselben Blockgroessen, aber die Werte
    durchgemischt. Damit ist jede Abhaengigkeit zerstoert und trotzdem alles
    andere gleich - insbesondere die ungleichen Blockgroessen, die den
    Schaetzer fuer sich genommen schon nach unten ziehen.

    ``None``, wenn zu wenige Bloecke da sind.
    """
    verwendbar = [np.asarray(b, dtype=float) for b in bloecke if len(b)]
    n = sum(len(b) for b in verwendbar)
    if len(verwendbar) < MIND_BLOECKE or n < 3:
        return None

    gemessen = _icc(verwendbar)
    if gemessen is None:
        return None
    icc, deff = gemessen

    groessen = [len(b) for b in verwendbar]
    alle = np.concatenate(verwendbar)
    rng = np.random.default_rng(saat)
    null = []
    for _ in range(permutationen):
        gemischt = rng.permutation(alle)
        teile, i = [], 0
        for groesse in groessen:
            teile.append(gemischt[i : i + groesse])
            i += groesse
        ergebnis = _icc(teile)
        if ergebnis is not None:
            null.append(ergebnis[1])

    if not null:
        return None

    # Wie oft sieht reines Rauschen mindestens so abhaengig aus? Bleibt als
    # Auskunft erhalten - ueber die Kuerzung entscheidet er nicht mehr.
    p = float(np.mean([x >= deff for x in null]))
    nachgewiesen = p <= SIGNIFIKANZ

    # **Stetig statt binaer, und kalibriert an der oberen Schranke der Null.**
    #
    # Frueher stand hier ein ``if p <= 0,05``. Das war eine harte Schwelle auf
    # einer stetigen Groesse, und sie hat dreimal Schaden angerichtet - zuletzt
    # ueber einen ganzen Regler hinweg, wo sechs von acht Stellungen im
    # Grenzbereich lagen und drei davon um Hundertstel eines p-Werts ein
    # Drittel ihrer Stichprobe verloren. Der Deflated Sharpe sprang dabei
    # zwischen 0,85 und 0,07.
    #
    # Kalibriert wird jetzt gegen das **95. Perzentil** der Null statt gegen
    # ihren Median. Der Unterschied ist der Kern der Sache:
    #
    #   Median:      Auf unabhaengigen Daten liegt die Haelfte aller Ziehungen
    #                darueber - unbedingt angewandt wuerde also die Haelfte
    #                aller sauberen Messungen bestraft. Deshalb brauchte es
    #                frueher die Schwelle davor, und mit ihr die Klippe.
    #   95. Perzentil: Nur jede zwanzigste saubere Ziehung liegt darueber, und
    #                dann knapp. Die Kuerzung geht dort von selbst gegen null -
    #                ganz ohne ``if``.
    #
    # Damit ist die Groesse stetig: Waechst die Abhaengigkeit, waechst die
    # Kuerzung mit, statt bei einem Schwellenwert umzuspringen.
    schranke = float(np.quantile(null, 1.0 - SIGNIFIKANZ))
    deff_korrigiert = max(1.0, deff / schranke) if schranke > 0 else 1.0
    effektiv = max(1, min(n, round(n / deff_korrigiert)))

    return Effektivwert(
        roh=n, effektiv=effektiv, icc=icc, p_wert=p,
        nachgewiesen=nachgewiesen, bloecke=len(verwendbar),
    )


def effektive_stichprobe(
    roh_trades: int,
    beine: dict[str, list[float]] | None = None,
    bloecke: list[list[float]] | None = None,
    *,
    weitere: Sequence[list[list[float]]] = (),
) -> Effektivwert:
    """Wie viele unabhaengige Beobachtungen stecken in ``roh_trades``?

    ``bloecke`` sind die Trade-Ergebnisse je Fenster - die eigentliche
    Grundlage. ``beine`` dient nur der Beschreibung.

    Ohne Blockdaten bleibt alles, wie es war. Eine Korrektur ohne Messung waere
    genau der Fehler, den dieses Modul verhindern soll.

    **``weitere`` sind andere Einteilungen derselben Trades, und es zaehlt die
    strengste.** Abhaengigkeit hat hier naemlich mehr als eine Gestalt, und
    keine ist die richtige:

        nach Kalenderfenstern   Trades desselben Quartals aehneln sich
        nach Gleichzeitigkeit   Positionen, die zugleich offen waren

    Bis hierher entschied allein die erste Einteilung, ohne dass irgendwo
    stuende, warum. Das Monte-Carlo-Gate haelt dagegen laengst die
    **gleichzeitigen** Trades zusammen - zwei Vorstellungen von Abhaengigkeit
    im selben Gate-System, und die schaerfere blieb ungenutzt.

    Gewaehlt wird deshalb die Einteilung, die die kleinste Stichprobe
    uebriglaesst. Das kann die Zulassung nur erschweren, nie erleichtern - die
    einzige Richtung, in die eine solche Entscheidung fallen darf.
    """
    einteilungen = [b for b in (bloecke, *weitere) if b]
    if einteilungen:
        gemessen = [d for d in map(designeffekt, einteilungen) if d is not None]
        # Verglichen wird der **Faktor**, nicht die absolute Zahl: Zwei
        # Einteilungen koennen verschieden viele Trades abdecken, und dann
        # waere die kleinere Summe kein Zeichen groesserer Strenge.
        ergebnis = min(gemessen, key=lambda d: d.faktor) if gemessen else None
        if ergebnis is not None:
            # **Den Faktor uebernehmen, nicht die Blocksumme.**
            #
            # Die Bloecke sollten alle Trades enthalten, aber "sollten" ist
            # keine Zusicherung: Wer Bloecke hereinreicht, die nur einen Teil
            # abdecken, bekaeme sonst still eine ganz andere Stichprobengroesse
            # ins Gate geschoben. Der Faktor ist die Aussage - die absolute
            # Zahl kommt vom Aufrufer.
            return Effektivwert(
                roh=roh_trades,
                effektiv=max(1, min(roh_trades, round(roh_trades * ergebnis.faktor))),
                icc=ergebnis.icc,
                p_wert=ergebnis.p_wert,
                nachgewiesen=ergebnis.nachgewiesen,
                bloecke=ergebnis.bloecke,
            )
    return Effektivwert(roh=roh_trades, effektiv=roh_trades, bloecke=0)
