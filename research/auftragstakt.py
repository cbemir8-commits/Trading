"""Der Auftrag in den Einheiten, die der Analyst tatsaechlich setzt.

Was im Auftrag steht - und was darin fehlt
------------------------------------------
``auftragslage.Auftragslage.als_auftrag`` ist der Abschnitt, den Befund 121
eingezogen hat, weil der Analyst vom Deflated Sharpe nie erfahren hatte. Er
nennt heute drei Dinge, und alle drei mit Zahlen:

    1. mindestens 161 Trades im selben Zeitraum
    2. Sharpe je Trade ueber 0,2465 bei dieser Zahl
    3. ein anderes Marktverhalten als Trendfolge

**Keine dieser Groessen kann der Analyst einstellen.** Er fuellt ein Genom
aus, und dessen Felder heissen ``stop``, ``targets``, ``cooldown_bars`` und
``max_hold_bars``. Trade-Zahl und Sharpe je Trade sind *Ergebnisse* davon,
gemessen hinterher ueber elf Gates. Nachgezaehlt im Auftragstext:

    'Haltedauer'      0x
    'max_hold'        0x
    'Bruttobewegung'  0x
    'Gebuehr'         0x

Das ist derselbe Fehler, den ``auftragslage`` an sich selbst behoben hat - der
Auftrag nannte das falsche Ziel -, nur eine Ebene tiefer: Jetzt nennt er das
richtige Ziel in einer Einheit, in der es sich nicht einstellen laesst.

Was hier gerechnet wird
-----------------------
Zwei Umrechnungen, beide aus Groessen, die schon gemessen sind:

**Takt.** 161 Trades auf ``datenstand.GEMEINSAME_TAGE`` - den 3300 Tagen, auf
denen beide Beine Kerzen haben - sind ein Trade alle 20,5 Tage. Das ist die
Schlagzahl, die die Trade-Zahl verlangt.

**Bruttobewegung.** Zu dieser Haltedauer gehoert eine gemessene Streuung
(``taktung.streuung_je_trade``, aus den echten Kerzen und nicht mit der Wurzel
der Zeit hochgerechnet). Der noetige Sharpe je Trade mal dieser Streuung ist
die Bewegung, die ein Trade im Mittel abwerfen muss - in Prozent, also in
derselben Einheit wie ``stop`` und ``targets``.

Gemessen auf der Zulassungsreihe (BTC 1d, Versuchsstand 203, Form des
Bestands):

    Trades   Takt/Tage   Streuung%   noetig SR   brutto%   Gebuehr-Anteil
       146        22,6       28,18      0,3038      8,56             0,5%
       161        20,5       24,50      0,2911      7,13             0,6%
       185        17,8       22,28      0,2740      6,10             0,7%
       156        21,2       25,69      0,2952      7,58             0,5%

Die letzte Zeile ist der Bestand und damit die Gegenprobe: Er handelt in
diesem Takt und hat 0,2708 gegen noetige 0,2952 - knapp 8 % zu wenig, was zur
bekannten Luecke passt.

**Und die Gebuehr ist hier kein Faktor.** 0,04 % vom Nominalwert sind 0,5 bis
0,7 % der verlangten Bewegung. Das ist die Gegenrichtung zu ``taktung``: Dort
schneiden sich Anforderung und Gebuehr irgendwo bei sehr vielen Trades; in dem
Band, das dieser Auftrag verlangt, ist davon nichts zu sehen. Wer hier spart,
spart an der falschen Stelle.

Was die Zahlen nicht sagen
--------------------------
**Der Takt ist ein Budget, keine Vorhersage.** Er unterstellt Trades, die sich
nicht ueberlappen; wer parallel haelt, kann dichter handeln. Vor allem aber:
**Ein kuerzerer Ausstieg bringt keine Trades.** Befund 416 hat sechs
Haltedauer-Deckel am massgeblichen Punkt gemessen, und die Zahl der fertigen
Trades blieb bei jedem zwischen 156 und 158 - der Deckel bringt *andere*
Beobachtungen, nicht mehr. Wer 161 Trades will, braucht ein Signal, das
oefter ausloest, nicht einen Stop, der frueher greift. Der Takt sagt, welche
Schlagzahl dazugehoert; er sagt nicht, dass man sie durch ``max_hold_bars``
herstellt.

**Zwei verschiedene 'noetig'.** ``als_auftrag`` nennt 0,2465 - das ist die
Anforderung an einen **Partner** neben dem Bestand, und sie haengt am
Unabhaengigkeitsgrad. Die Spalte hier nennt die Anforderung an eine Regel, die
das Gate **allein** raeumen soll (``erreichbarkeit.noetiger_sharpe``), und die
ist hoeher. Beide Zahlen gehoeren in den Auftrag, aber nicht in dieselbe
Spalte: Wer sie verwechselt, rechnet sich den Partner zu leicht - mir selbst
ist in diesem Befund genau das unterlaufen, indem ich ``bestand_sharpe``
nochmals durch die Wurzel der Stichprobe geteilt habe und daraufhin 246 statt
161 Trades als Ziel gelesen habe.

**Die Streuung steht auf BTC.** ETH hat eine andere, und der Korb wird auf
beiden gehandelt. Die Zahl ist damit eine Groessenordnung fuer den Auftrag und
keine Schwelle, gegen die etwas geprueft wird.

Kostet keinen Versuch: Es wird kein Kandidat gemessen, sondern eine
Anforderung umgerechnet.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from research.datenstand import GEMEINSAME_TAGE
from research.erreichbarkeit import noetiger_sharpe
from research.taktung import streuung_je_trade
from research.vorteilsscan import KOSTEN_MAKER_MAKER


@dataclass(frozen=True, slots=True)
class Takt:
    """Eine Trade-Zahl, umgerechnet in Schlagzahl und Bruttobewegung."""

    trades: int
    takt_tage: float
    streuung_pct: float
    noetiger_sharpe: float
    brutto_pct: float

    @property
    def gebuehr_anteil(self) -> float:
        """Welchen Anteil der verlangten Bewegung die Gebuehr frisst."""
        return KOSTEN_MAKER_MAKER / self.brutto_pct

    @property
    def gebuehr_traegt(self) -> bool:
        """Ob die Gebuehr in dieser Groessenordnung ueberhaupt mitredet.

        Die Grenze ist bewusst grob: Unter einem Zwanzigstel der verlangten
        Bewegung ist die Gebuehr keine Groesse, ueber der ist sie eine. Eine
        feinere Schwelle waere hier gesetzt und nicht gemessen.
        """
        return self.gebuehr_anteil >= 0.05


def rechne(
    frame: pd.DataFrame,
    *,
    ziele: tuple[int, ...],
    versuche: int,
    schiefe: float = 0.0,
    woelbung: float = 3.0,
    tage: int = GEMEINSAME_TAGE,
) -> tuple[Takt, ...]:
    """Zu jeder Trade-Zahl den Takt und die noetige Bruttobewegung.

    ``tage`` sind die Tage, auf denen **beide** Beine Kerzen haben - nicht die
    Laenge von ``frame``. BTC reicht 2054 Tage weiter zurueck als ETH, und der
    Korb kann diesen Vorlauf nicht nutzen (Befund 318). Wer die Reihenlaenge
    einsetzt, rechnet sich den Takt zu gemuetlich.
    """
    stufen: list[Takt] = []
    for ziel in ziele:
        if ziel <= 0:
            continue
        takt = tage / ziel
        kerzen = max(1, round(takt))
        streuung = streuung_je_trade(frame, kerzen=kerzen)
        noetig = noetiger_sharpe(
            effektiv=ziel, trials=versuche, skew=schiefe, kurtosis=woelbung
        )
        if noetig is None or streuung <= 0:
            continue
        stufen.append(
            Takt(
                trades=ziel,
                takt_tage=takt,
                streuung_pct=streuung,
                noetiger_sharpe=noetig,
                brutto_pct=noetig * streuung,
            )
        )
    return tuple(stufen)


def als_auftrag(stufen: tuple[Takt, ...], *, ziel_trades: int) -> str:
    """Der Abschnitt, der in den Prompt gehoert.

    Leer, wenn nichts gerechnet werden konnte - ein Auftragsabschnitt ohne
    Zahlen ist schlechter als keiner, weil er wie eine Anforderung aussieht.
    """
    if not stufen:
        return ""

    ziel = next((s for s in stufen if s.trades == ziel_trades), stufen[0])
    zeilen = [
        "## Was das in Genom-Groessen heisst\n",
        "Die Trade-Zahl und der Sharpe je Trade oben sind **Ergebnisse**. "
        "Einstellen",
        "kannst du 'stop', 'targets', 'cooldown_bars' und 'max_hold_bars'. "
        "Umgerechnet",
        f"auf die {GEMEINSAME_TAGE} Tage, auf denen beide Beine Kerzen haben:",
        "",
        f"- **Takt: ein Trade alle {ziel.takt_tage:.1f} Tage** fuer "
        f"{ziel.trades} Trades.",
        f"- **Bruttobewegung: rund {ziel.brutto_pct:.1f} % je Trade.** Die "
        f"gemessene Streuung",
        f"  einer Bewegung ueber {round(ziel.takt_tage)} Tage ist "
        f"{ziel.streuung_pct:.1f} %; davon musst du",
        f"  {ziel.noetiger_sharpe:.4f} mal so viel im Mittel behalten.",
        f"- **Die Gebuehr ist dabei kein Faktor:** 0,04 % vom Nominalwert sind "
        f"{ziel.gebuehr_anteil:.1%}",
        "  der verlangten Bewegung. Spare nicht daran.",
        "",
        "Die Spanne, damit du siehst, wohin es sich lohnt:",
        "",
        "    Trades  Takt/Tage  Streuung%  noetig SR  brutto%",
    ]
    for s in stufen:
        zeilen.append(
            f"    {s.trades:>6} {s.takt_tage:>10.1f} {s.streuung_pct:>10.2f} "
            f"{s.noetiger_sharpe:>10.4f} {s.brutto_pct:>8.2f}"
        )
    zeilen += [
        "",
        "**Zwei Warnungen dazu.**",
        "",
        "Erstens: Ein **frueherer Ausstieg bringt keine Trades.** Sechs "
        "Haltedauer-Deckel",
        "sind am massgeblichen Kandidaten gemessen, und die Zahl der fertigen "
        "Trades",
        "blieb bei jedem zwischen 156 und 158 - der Deckel bringt *andere* "
        "Beobachtungen,",
        "nicht mehr. Wer mehr Trades will, braucht ein Signal, das oefter "
        "ausloest.",
        "",
        "Zweitens: Die Spalte 'noetig SR' ist die Anforderung an eine Regel, "
        "die das",
        "Gate **allein** raeumt. Als **Partner** neben dem Bestand genuegt "
        "weniger - die",
        "Zahl dazu steht oben. Verwechsle die beiden nicht.",
        "",
    ]
    return "\n".join(zeilen)
