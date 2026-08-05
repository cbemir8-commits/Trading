"""Was echte Trades zum Beweis beitragen - und was nicht.

Der Ausgangspunkt
-----------------
Der Spitzenkandidat scheitert an einem einzigen statistischen Gate: dem
Deflated Sharpe. Er liegt bei 0,830 und braucht 0,95. Gemessen ist, woran
das haengt - nicht an der Guete der Regel, sondern an der **Zahl** der
Trades: 156 ergeben 0,830, rund 200 wuerden 0,957 ergeben.

Zehn Wege, mehr Trades aus vorhandenen Daten zu holen, sind gemessen und
alle zu teuer (siehe ``strategies/BEFUND.md``). Bleibt genau eine Quelle,
die Trades liefert, ohne Qualitaet einzutauschen: **gehandelte Trades.**

Warum echte Trades nicht den Versuchszaehler erhoehen
----------------------------------------------------
Weil sie keine neue Hypothese sind. Der Zaehler korrigiert dafuer, dass man
bei genug Versuchen irgendwann etwas findet, das im Rueckblick gut aussieht.
Dieselbe Strategie weiter zu handeln ist kein weiterer Versuch - es ist
derselbe, laenger beobachtet.

Die Grenze davon ist scharf: Wer **fuenf** Strategien live laufen laesst und
die beste behaelt, hat fuenf Versuche gemacht. Dieses Modul geht davon aus,
dass genau eine Strategie gehandelt wird, und sagt es dem Aufrufer.

Warum ein Signifikanztest allein nicht reicht
---------------------------------------------
Live ist fast immer schlechter als Backtest - Slippage, echte Fills, ein
Markt, der sich bewegt, waehrend die Order laeuft. Wuerde man schlechtere
Live-Trades einfach dazurechnen, entstuende die absurde Lage, dass ein
**enttaeuschender** Livebetrieb die Zulassung naeher rueckt, weil er die
Stichprobe vergroessert.

Die naheliegende Abhilfe - "erst pruefen, ob es signifikant schlechter ist" -
habe ich gebaut und dann gemessen, dass sie nicht traegt. Mit 40 Live-Trades,
gerechnet auf der echten Verteilung:

    Live-Ergebnis      Deflated Sharpe naiv    Drift erkannt?
    unveraendert            0,824 -> 0,937          -
    33 % schlechter         0,824 -> 0,931         nein
    71 % schlechter         0,824 -> 0,896         nein
   100 % schlechter         0,824 -> 0,820          ja

Ein Livebetrieb, der **zwei Drittel** des Vorteils verliert, hebt den Wert
also immer noch - und der Signifikanztest schweigt dazu. Er schweigt nicht,
weil alles in Ordnung ist, sondern weil er bei 40 Beobachtungen einer so
schiefen Verteilung fast nichts sehen kann.

Deshalb steht hier eine zweite, strengere Bedingung: **Wie gross muesste die
Verschlechterung sein, damit sie ueberhaupt aufgefallen waere?**
(``erkennbare_verschlechterung``). Ist dieser blinde Fleck groesser als ein
Viertel des Vorteils, wird nicht zusammengerechnet - egal wie unauffaellig
der Test ausfaellt. Fehlende Evidenz fuer Drift ist keine Evidenz fuer dessen
Abwesenheit.

Das dreht die Beweislast um, und das ist der Punkt: Nicht "ich habe nichts
Schlimmes gefunden", sondern "ich haette es gefunden, wenn es da waere".

In welcher Einheit hier gerechnet wird - und warum das nicht die des Gates ist
------------------------------------------------------------------------------
Dieses Modul rechnet in **R-Vielfachen**, das Gate ``Deflated Sharpe`` in
**Geld**. Beide Zahlen heissen gleich und sind es nicht:

    auf Geld gerechnet (das Gate)   0,830
    auf R gerechnet (hier)          0,777

Der Unterschied kommt vom Vola-Ziel: Es macht Positionen gross, wenn der
Markt ruhig ist, und klein, wenn er wild ist. Dadurch streuen die
Geldbetraege weniger als die R-Vielfachen, und der Sharpe je Trade faellt in
Geld hoeher aus. Das Gate schreibt diesen Teil also der Groessenlogik gut,
was fuer eine Zulassung richtig ist - gehandelt wird die Regel **mit** ihrer
Groessenlogik.

Hier geht es aber um etwas anderes: Live gegen Backtest zu halten. Dafuer
taugt nur R, weil ein Demokonto mit 500 Euro und ein Backtest bei anderem
Kontostand in Geld nicht vergleichbar sind. Die hier gezeigte Zahl ist
zufaellig auch die **strengere** - sie schmeichelt nichts.

Wer beide Werte nebeneinander sieht, darf sie nicht gegeneinander
verrechnen. Sie beantworten verschiedene Fragen.

Warum Bootstrap und kein t-Test
-------------------------------
Die Verteilung der R-Vielfachen hat Schiefe +3,7 und Woelbung 17,4. Ein
t-Test setzt Normalitaet voraus und waere hier deutlich daneben - er
unterschaetzt, wie oft ein kleiner Mittelwert allein durch Zufall entsteht,
wenn wenige Riesengewinner den Schnitt tragen.

Der Bootstrap zieht stattdessen aus der **gemessenen** Backtest-Verteilung
und zaehlt, wie oft eine Stichprobe der Live-Groesse so schlecht ausfaellt
wie die beobachtete. Er setzt nichts voraus ausser der Verteilung selbst.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import structlog

from research.gates import deflated_sharpe_ratio

log = structlog.get_logger(__name__)

#: Ab wann eine Abweichung als Abwaertsdrift gilt. Bewusst grosszuegig
#: gewaehlt: Ein Fehlalarm kostet eine Nachfrage, ein uebersehener Drift
#: kostet Geld.
DRIFT_SCHWELLE = 0.05

#: Unter so wenigen Live-Trades hat kein Test Aussagekraft. Der Bootstrap
#: liefert dann zwar eine Zahl, aber sie traegt nichts - und eine Zahl, die
#: nichts traegt, wird hier nicht ausgegeben.
MINDESTENS_AUSSAGEKRAEFTIG = 20

#: Wie viel Verschlechterung unentdeckt bleiben darf, damit noch
#: zusammengerechnet wird. Ueber diesem Wert waere das Zusammenrechnen eine
#: Annahme und keine Messung.
#:
#: Der Wert steht hier, weil die naive Rechnung sonst genau falsch herum
#: laeuft. Gemessen an der echten Verteilung, mit 40 Live-Trades:
#:
#:     Live-Ergebnis    Deflated Sharpe naiv    Drift erkannt?
#:     unveraendert            0,824 -> 0,937        -
#:     33 % schlechter         0,824 -> 0,931       nein
#:     71 % schlechter         0,824 -> 0,896       nein
#:    100 % schlechter         0,824 -> 0,820       ja
#:
#: Ein Livebetrieb, der zwei Drittel des Vorteils verliert, **hebt** den Wert
#: also - weil sqrt(n) staerker waechst als der Mittelwert faellt - und der
#: Signifikanztest schweigt dazu. Wer nur auf "ist es signifikant schlechter"
#: prueft, hat die Beweislast verkehrt herum: Fehlende Evidenz fuer Drift ist
#: keine Evidenz fuer dessen Abwesenheit.
MAX_UNERKANNTE_VERSCHLECHTERUNG = 0.25

#: Mit welcher Wahrscheinlichkeit eine Verschlechterung auffallen muss, damit
#: sie als "erkennbar" gilt.
GEFORDERTE_TRENNSCHAERFE = 0.80


@dataclass(frozen=True, slots=True)
class LiveEvidenz:
    """Was der Livebetrieb bisher beweist."""

    backtest_trades: int
    live_trades: int

    erwartung_backtest_r: float
    erwartung_live_r: float | None

    dsr_ohne_live: float
    dsr_mit_live: float | None
    """Der Wert, der fuer die Zulassung zaehlt - oder ``None``.

    ``None`` heisst: nicht **verdient**. Entweder laeuft der Livebetrieb
    schlechter, oder die Stichprobe ist zu klein, um das auszuschliessen.
    Diese Zahl wird nie geschenkt."""

    dsr_zusammengerechnet: float | None
    """Dieselbe Rechnung ohne jede Pruefung - zur Anschauung, nicht zur
    Zulassung.

    Steht daneben, weil ein zurueckgehaltener Wert sonst wie ein Fehler
    aussieht. Zusammen mit ``unerkannte_verschlechterung`` gelesen zeigt er
    genau, wie viel die naive Rechnung wert waere: bei einem blinden Fleck von
    71 % naemlich nichts."""

    p_wert_drift: float | None
    vertraegt_sich: bool
    """Ob der Drift-Test nichts gefunden hat. Fuer sich genommen wenig wert -
    siehe ``unerkannte_verschlechterung``."""

    aussagekraeftig: bool
    """Ob genug Live-Trades da sind, dass "nichts gefunden" etwas heisst."""

    unerkannte_verschlechterung: float
    """Welcher Anteil des Vorteils verlorengehen koennte, ohne aufzufallen.

    Die wichtigste Zahl im ganzen Datensatz. 0,71 heisst: Die Strategie
    koennte zwei Drittel ihres Vorteils eingebuesst haben, und diese Messung
    saehe genauso aus."""

    fehlende_trades: int
    """Wie viele Trades noch fehlen, bis der Deflated Sharpe reicht -
    **bei unveraenderter Qualitaet je Trade**."""

    trades_pro_jahr: float | None
    jahre_bis_beweis: float | None

    urteil: str

    def bericht(self) -> str:
        zeilen = [self.urteil, ""]
        zeilen.append(f"  Backtest      {self.backtest_trades:>5} Trades, "
                      f"Erwartung {self.erwartung_backtest_r:+.3f} R")
        if self.live_trades:
            zeilen.append(f"  Live          {self.live_trades:>5} Trades, "
                          f"Erwartung {self.erwartung_live_r:+.3f} R")
        else:
            zeilen.append("  Live              0 Trades")
        zeilen.append("")
        zeilen.append(
            "  Deflated Sharpe, auf R gerechnet - nicht der Gate-Wert, der "
            "auf Geld rechnet"
        )
        zeilen.append(f"    ohne Live   {self.dsr_ohne_live:.3f}")
        if self.dsr_mit_live is not None:
            zeilen.append(f"    mit Live    {self.dsr_mit_live:.3f}  (belegt)")
        elif self.dsr_zusammengerechnet is not None:
            zeilen.append(
                f"    mit Live    {self.dsr_zusammengerechnet:.3f}  "
                "(nur gerechnet, nicht belegt)"
            )
        if self.fehlende_trades:
            zeilen.append(f"  Es fehlen noch              {self.fehlende_trades} Trades")
        if self.jahre_bis_beweis is not None:
            zeilen.append(f"  Das dauert rund             {self.jahre_bis_beweis:.1f} Jahre")
        return "\n".join(zeilen)


def r_werte(trades) -> list[float]:
    """Die R-Vielfachen aus Backtest- oder Live-Trades ziehen.

    Beide Sorten heissen verschieden (``r_multiple`` gegen ``r``), meinen
    aber dasselbe. Trades ohne Stop haben kein bezifferbares Risiko und
    damit kein R - sie fallen weg statt als Null zu zaehlen.
    """
    werte = []
    for trade in trades:
        roh = getattr(trade, "r_multiple", None)
        if roh is None:
            roh = getattr(trade, "r", None)
        if roh is not None:
            werte.append(float(roh))
    return werte


def drift_test(
    backtest_r: list[float],
    live_r: list[float],
    *,
    ziehungen: int = 20_000,
    seed: int = 20260805,
) -> float:
    """Wie wahrscheinlich ist ein so schlechtes Live-Ergebnis durch Zufall?

    Gezogen wird mit Zuruecklegen aus der Backtest-Verteilung, jeweils so
    viele Werte, wie es Live-Trades gibt. Der Rueckgabewert ist der Anteil
    der Ziehungen, deren Mittelwert **hoechstens** so gross ist wie der
    live beobachtete.

    Einseitig, und das mit Absicht: Ein Livebetrieb, der **besser** laeuft
    als der Backtest, ist kein Anlass zur Sorge - er ist ein Anlass zum
    Misstrauen gegen die Buchhaltung, aber das ist eine andere Pruefung.

    Ein kleiner Wert heisst: So schlecht faellt es kaum je aus, wenn die
    Strategie noch dieselbe ist. Also ist sie es vermutlich nicht mehr.

    Der Startwert des Zufallsgenerators ist fest. Ein Zulassungsurteil, das
    beim zweiten Aufruf anders ausfaellt, waere keines.
    """
    if not backtest_r or not live_r:
        raise ValueError("Beide Seiten brauchen Werte")

    rng = np.random.default_rng(seed)
    basis = np.asarray(backtest_r, dtype=float)
    beobachtet = float(np.mean(live_r))

    stichproben = rng.choice(basis, size=(ziehungen, len(live_r)), replace=True)
    mittelwerte = stichproben.mean(axis=1)
    return float(np.mean(mittelwerte <= beobachtet))


def erkennbare_verschlechterung(
    backtest_r: list[float],
    n_live: int,
    *,
    trennschaerfe: float = GEFORDERTE_TRENNSCHAERFE,
    alpha: float = DRIFT_SCHWELLE,
    ziehungen: int = 20_000,
    seed: int = 20260805,
) -> float:
    """Welche Verschlechterung bei ``n_live`` Trades ueberhaupt auffallen wuerde.

    Rueckgabe als Anteil des Backtest-Vorteils: 0,25 heisst "ein Viertel des
    Vorteils weniger wuerde in vier von fuenf Faellen auffallen". 1,0 heisst
    "erst der vollstaendige Verlust des Vorteils faellt auf".

    Das ist die Zahl, die dem Drift-Test erst seinen Wert gibt. Ohne sie sagt
    ein unauffaelliger Test nur "nichts gefunden" - und das kann heissen "es
    ist nichts da" oder "ich haette es gar nicht sehen koennen". Der
    Unterschied entscheidet, ob man Geld darauf setzt.

    Gerechnet wird durch Simulation, nicht ueber eine Formel: Die Verteilung
    hat Schiefe +3,7, und jede Normalapproximation waere hier zu optimistisch.
    Erst wird der kritische Mittelwert bestimmt - der Wert, unter dem der
    Drift-Test anschlaegt -, dann gezaehlt, wie oft eine abgesenkte Verteilung
    darunter faellt.
    """
    if not backtest_r:
        raise ValueError("Ohne Backtest-Werte gibt es nichts zu vergleichen")
    if n_live < 1:
        return 1.0

    basis = np.asarray(backtest_r, dtype=float)
    vorteil = float(np.mean(basis))
    if vorteil <= 0:
        return 1.0

    mittelwerte = _bootstrap_mittelwerte(basis, n_live, ziehungen, seed)

    # Der kritische Wert: So klein faellt der Mittelwert von n_live Trades
    # in alpha der Faelle aus, wenn sich nichts geaendert hat.
    kritisch = float(np.quantile(mittelwerte, alpha))

    # Eine Verschlechterung um ``d`` verschiebt jeden Wert um ``d * vorteil``
    # nach unten; die Form der Verteilung bleibt. Der Test schlaegt an, wenn
    #
    #     Mittelwert - d * vorteil <= kritisch
    #
    # also wenn ``d >= (Mittelwert - kritisch) / vorteil``. Die Trennschaerfe
    # bei gegebenem ``d`` ist damit genau der Anteil der Ziehungen, fuer die
    # das gilt - und das gesuchte kleinste ``d`` ist schlicht das
    # entsprechende **Quantil** dieser Groesse.
    #
    # Das ersetzt eine Bisektion, die hier lange stand: gleiches Ergebnis,
    # exakt statt genaehert, und ohne vierzig Durchlaeufe ueber das Feld.
    noetig = (mittelwerte - kritisch) / vorteil
    return round(float(np.quantile(noetig, trennschaerfe)), 4)


def _bootstrap_mittelwerte(
    basis: np.ndarray, n: int, ziehungen: int, seed: int
) -> np.ndarray:
    """Mittelwerte von ``ziehungen`` Stichproben der Groesse ``n``.

    Stueckweise gezogen, weil das Feld sonst ``ziehungen * n`` Werte gross
    wuerde - bei 20.000 Ziehungen und 2.000 Live-Trades waeren das 40
    Millionen Zahlen fuer eine Zwischenrechnung.
    """
    rng = np.random.default_rng(seed)
    haeppchen = max(1, min(ziehungen, 4_000_000 // max(n, 1)))
    teile = []
    offen = ziehungen
    while offen > 0:
        jetzt = min(haeppchen, offen)
        teile.append(rng.choice(basis, size=(jetzt, n), replace=True).mean(axis=1))
        offen -= jetzt
    return np.concatenate(teile)


def live_trades_fuer_nachweis(
    backtest_r: list[float],
    verschlechterung: float = MAX_UNERKANNTE_VERSCHLECHTERUNG,
    *,
    obergrenze: int = 20_000,
    **kwargs,
) -> int:
    """Wie viele Live-Trades noetig sind, um ``verschlechterung`` zu erkennen.

    Die Umkehrung von ``erkennbare_verschlechterung``. Beantwortet die Frage,
    die vor jedem Demobetrieb stehen sollte: Wie lange muss ich handeln,
    bevor das Ergebnis ueberhaupt etwas aussagt?

    Gesucht wird nicht Schritt fuer Schritt, sondern ueber die Beziehung
    ``d ~ 1/sqrt(n)``: Aus einer Messung laesst sich die noetige Groesse
    schaetzen, danach wird nur noch nachjustiert. Das spart bei feinen
    Anforderungen zwei Groessenordnungen an Rechenzeit.
    """
    if verschlechterung <= 0:
        return obergrenze

    n = 40
    gemessen = erkennbare_verschlechterung(backtest_r, n, **kwargs)
    if gemessen <= verschlechterung:
        # Schon die Startgroesse reicht - nach unten suchen.
        while n > 10 and erkennbare_verschlechterung(
            backtest_r, n // 2, **kwargs
        ) <= verschlechterung:
            n //= 2
        return n

    for _ in range(12):
        geschaetzt = int(n * (gemessen / verschlechterung) ** 2) + 1
        n = min(max(geschaetzt, n + 1), obergrenze)
        gemessen = erkennbare_verschlechterung(backtest_r, n, **kwargs)
        if gemessen <= verschlechterung or n >= obergrenze:
            return n
    return n


def benoetigte_trades(
    werte: list[float],
    *,
    trials: int,
    ziel: float = 0.95,
    obergrenze: int = 5000,
) -> int:
    """Wie viele Trades es braucht, bis der Deflated Sharpe ``ziel`` erreicht.

    Rechnet mit **unveraenderter** Qualitaet je Trade: Sharpe, Schiefe und
    Woelbung bleiben, wie sie gemessen wurden, und nur ``n`` waechst. Das ist
    eine Hochrechnung, keine Vorhersage - sie sagt, was noetig waere, nicht
    was kommt.

    Gibt 0 zurueck, wenn das Ziel schon erreicht ist.
    """
    kennzahlen = _kennzahlen(werte)
    if kennzahlen is None:
        return 0

    sharpe, schiefe, woelbung = kennzahlen
    for n in range(len(werte), obergrenze + 1):
        dsr = deflated_sharpe_ratio(
            observed_sharpe=sharpe, trials=max(trials, 1), sample_size=n,
            skew=schiefe, kurtosis=woelbung,
        )
        if dsr >= ziel:
            return max(0, n - len(werte))
    return obergrenze


def bewerten(
    backtest_trades,
    live_trades,
    *,
    trials: int,
    live_tage: float | None = None,
    ziel: float = 0.95,
) -> LiveEvidenz:
    """Backtest und Livebetrieb gemeinsam bewerten.

    ``live_tage`` ist der Zeitraum, ueber den die Live-Trades entstanden
    sind. Daraus wird hochgerechnet, wie lange es dauert, bis genug
    zusammenkommt - die Zahl, die ueber "ein Monat Demo" oder "drei Jahre"
    entscheidet.

    ``trials`` wird **nicht** veraendert. Der Livebetrieb derselben
    Strategie ist kein weiterer Versuch.
    """
    backtest_r = r_werte(backtest_trades)
    live_r = r_werte(live_trades)

    if not backtest_r:
        raise ValueError("Ohne Backtest-Trades gibt es nichts zu vergleichen")

    dsr_ohne = _dsr(backtest_r, trials)
    fehlend_ohne = benoetigte_trades(backtest_r, trials=trials, ziel=ziel)

    if not live_r:
        return LiveEvidenz(
            backtest_trades=len(backtest_r), live_trades=0,
            erwartung_backtest_r=round(float(np.mean(backtest_r)), 4),
            erwartung_live_r=None,
            dsr_ohne_live=dsr_ohne, dsr_mit_live=None,
            dsr_zusammengerechnet=None,
            p_wert_drift=None, vertraegt_sich=True, aussagekraeftig=False,
            unerkannte_verschlechterung=1.0,
            fehlende_trades=fehlend_ohne,
            trades_pro_jahr=None,
            jahre_bis_beweis=None,
            urteil=(
                f"Noch kein Live-Trade. Es fehlen {fehlend_ohne} Trades, bis der "
                "Deflated Sharpe reicht."
            ),
        )

    p_wert = drift_test(backtest_r, live_r)
    blindfleck = erkennbare_verschlechterung(backtest_r, len(live_r))
    # **Zwei** Bedingungen, nicht eine. Der Signifikanztest allein wuerde
    # jeden kleinen Livebetrieb durchwinken, weil er nichts finden *kann*.
    aussagekraeftig = (
        len(live_r) >= MINDESTENS_AUSSAGEKRAEFTIG
        and blindfleck <= MAX_UNERKANNTE_VERSCHLECHTERUNG
    )
    vertraegt_sich = p_wert >= DRIFT_SCHWELLE

    trades_pro_jahr = None
    if live_tage and live_tage > 0:
        trades_pro_jahr = len(live_r) / (live_tage / 365.25)

    if vertraegt_sich and not aussagekraeftig:
        # Nichts gefunden - aber es haette auch nichts gefunden werden
        # koennen. Zusammenrechnen waere hier eine Annahme und keine
        # Messung, und die Zahl saehe genauso aus wie eine belegte.
        noetig = live_trades_fuer_nachweis(backtest_r)
        jahre = (
            (noetig - len(live_r)) / trades_pro_jahr
            if trades_pro_jahr and noetig > len(live_r)
            else None
        )
        return LiveEvidenz(
            backtest_trades=len(backtest_r), live_trades=len(live_r),
            erwartung_backtest_r=round(float(np.mean(backtest_r)), 4),
            erwartung_live_r=round(float(np.mean(live_r)), 4),
            dsr_ohne_live=dsr_ohne, dsr_mit_live=None,
            dsr_zusammengerechnet=_dsr(backtest_r + live_r, trials),
            p_wert_drift=round(p_wert, 4), vertraegt_sich=True,
            aussagekraeftig=False,
            unerkannte_verschlechterung=blindfleck,
            fehlende_trades=fehlend_ohne,
            trades_pro_jahr=round(trades_pro_jahr, 1) if trades_pro_jahr else None,
            jahre_bis_beweis=round(jahre, 2) if jahre is not None else None,
            urteil=(
                f"{len(live_r)} Live-Trades reichen nicht als Beleg. Selbst wenn "
                f"die Strategie {blindfleck:.0%} ihres Vorteils verloren haette, "
                "waere das hier nicht aufgefallen - es wird deshalb **nicht** "
                f"zusammengerechnet. Dafuer braeuchte es rund "
                f"{live_trades_fuer_nachweis(backtest_r)} Live-Trades."
            ),
        )

    if not vertraegt_sich:
        return LiveEvidenz(
            backtest_trades=len(backtest_r), live_trades=len(live_r),
            erwartung_backtest_r=round(float(np.mean(backtest_r)), 4),
            erwartung_live_r=round(float(np.mean(live_r)), 4),
            dsr_ohne_live=dsr_ohne, dsr_mit_live=None,
            dsr_zusammengerechnet=_dsr(backtest_r + live_r, trials),
            p_wert_drift=round(p_wert, 4), vertraegt_sich=False,
            aussagekraeftig=aussagekraeftig,
            unerkannte_verschlechterung=blindfleck,
            fehlende_trades=fehlend_ohne,
            trades_pro_jahr=round(trades_pro_jahr, 1) if trades_pro_jahr else None,
            jahre_bis_beweis=None,
            urteil=(
                f"Der Livebetrieb laeuft schlechter als der Backtest "
                f"({np.mean(live_r):+.3f} R gegen {np.mean(backtest_r):+.3f} R, "
                f"so schlecht faellt es nur in {p_wert:.1%} der Faelle zufaellig "
                "aus). Es wird **nicht** zusammengerechnet - erst klaeren, "
                "woran das liegt."
            ),
        )

    gemeinsam = backtest_r + live_r
    dsr_mit = _dsr(gemeinsam, trials)
    fehlend = benoetigte_trades(gemeinsam, trials=trials, ziel=ziel)

    jahre = None
    if fehlend and trades_pro_jahr:
        jahre = fehlend / trades_pro_jahr

    if not fehlend:
        urteil = (
            f"Erreicht: Deflated Sharpe {dsr_mit:.3f} aus {len(gemeinsam)} Trades "
            f"({len(live_r)} davon gehandelt)."
        )
    elif jahre is not None:
        urteil = (
            f"{len(live_r)} Live-Trades bringen den Deflated Sharpe von "
            f"{dsr_ohne:.3f} auf {dsr_mit:.3f}. Es fehlen {fehlend} Trades - "
            f"bei {trades_pro_jahr:.1f} Trades im Jahr rund {jahre:.1f} Jahre."
        )
    else:
        urteil = (
            f"{len(live_r)} Live-Trades bringen den Deflated Sharpe von "
            f"{dsr_ohne:.3f} auf {dsr_mit:.3f}. Es fehlen {fehlend} Trades."
        )

    return LiveEvidenz(
        backtest_trades=len(backtest_r), live_trades=len(live_r),
        erwartung_backtest_r=round(float(np.mean(backtest_r)), 4),
        erwartung_live_r=round(float(np.mean(live_r)), 4),
        dsr_ohne_live=dsr_ohne, dsr_mit_live=dsr_mit,
        dsr_zusammengerechnet=dsr_mit,
        p_wert_drift=round(p_wert, 4), vertraegt_sich=True,
        aussagekraeftig=aussagekraeftig,
        unerkannte_verschlechterung=blindfleck,
        fehlende_trades=fehlend,
        trades_pro_jahr=round(trades_pro_jahr, 1) if trades_pro_jahr else None,
        jahre_bis_beweis=round(jahre, 2) if jahre is not None else None,
        urteil=urteil,
    )


def _kennzahlen(werte: list[float]) -> tuple[float, float, float] | None:
    """Sharpe je Trade, Schiefe und Woelbung - oder ``None`` ohne Streuung."""
    if len(werte) < 3:
        return None
    reihe = np.asarray(werte, dtype=float)
    streuung = float(np.std(reihe))
    if streuung <= 0:
        return None
    mittel = float(np.mean(reihe))
    zentriert = (reihe - mittel) / streuung
    return (
        mittel / streuung,
        float(np.mean(zentriert**3)),
        float(np.mean(zentriert**4)),
    )


def _dsr(werte: list[float], trials: int) -> float:
    kennzahlen = _kennzahlen(werte)
    if kennzahlen is None:
        return 0.0
    sharpe, schiefe, woelbung = kennzahlen
    return round(
        deflated_sharpe_ratio(
            observed_sharpe=sharpe, trials=max(trials, 1), sample_size=len(werte),
            skew=schiefe, kurtosis=woelbung,
        ),
        4,
    )


def demo_dauer(trades_pro_jahr: float, tage: float) -> float:
    """Wie viele Trades ein Zeitraum bei dieser Frequenz bringt.

    Steht hier, weil die Antwort regelmaessig ueberrascht: Eine Strategie mit
    17 Trades im Jahr erzeugt in 30 Tagen **1,4** Trades. Ein Monat Demo
    prueft die Technik, nicht den Vorteil.
    """
    return trades_pro_jahr * (tage / 365.25)


def jahre_fuer(fehlende: int, trades_pro_jahr: float) -> float:
    if trades_pro_jahr <= 0:
        return math.inf
    return fehlende / trades_pro_jahr
