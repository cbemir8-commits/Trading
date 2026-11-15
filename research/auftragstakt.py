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


def balken_fuer_tage(tage: float, intervall: object) -> int:
    """Wie viele Kerzen dieser Laenge auf ``tage`` Tage gehen.

    **Abgeleitet aus ``Interval.duration``** und nicht aufgeschrieben: Eine
    zweite Tafel waere die zweite Wahrheit, und ``datenstand.BALKEN_JE_TAG``
    haelt die 96 fuer die Feinreihe schon (Befund 494). Dass beide
    uebereinstimmen, steht als Zusicherung in ``test_auftragsbalken``.

    **Nicht "Balken je Tag"**, und das ist eine Berichtigung aus dem Bauen
    dieses Befundes: Der erste Entwurf rechnete Balken je Tag und gab fuer
    Wochenkerzen ``0`` zurueck - eine Zahl, die luegt, denn ein Takt von 20,5
    Tagen sind dort drei Balken. Gefragt ist immer eine Dauer, nie ein
    Verhaeltnis.

    ``None`` gibt es hier nicht: Was keine Kerzenlaenge ist, ist ein Fehler
    im Aufruf und nicht eine Null.
    """
    from datetime import timedelta

    from core.models import Interval

    gedeutet = Interval.gedeutet(intervall)
    if gedeutet is None:
        raise ValueError(f"keine Kerzenlaenge: {intervall!r}")
    return round(timedelta(days=tage) / gedeutet.duration)


def _kerzensatz(intervall: object) -> str:
    """Der Satz, der die Kerzenlaenge im Auftrag benennt.

    Fuer Kerzen unter einem Tag die Balken je Tag, darueber die Tage je
    Kerze - beides aus derselben Dauer, damit keine der beiden Richtungen
    eine Null wird.
    """
    from datetime import timedelta

    from core.models import Interval

    kerze = Interval.gedeutet(intervall)
    if kerze is None:
        raise ValueError(f"keine Kerzenlaenge: {intervall!r}")
    if kerze.duration <= timedelta(days=1):
        return (
            f"**Gerechnet wird auf {kerze.label}-Kerzen** - ein Tag sind "
            f"{balken_fuer_tage(1, kerze)} Balken."
        )
    tage = kerze.duration / timedelta(days=1)
    return (
        f"**Gerechnet wird auf {kerze.label}-Kerzen** - eine Kerze sind "
        f"{tage:.0f} Tage."
    )


def _feldgrenze(feld: str) -> int:
    """Die obere Grenze eines Genom-Feldes - **gefragt, nicht gewusst**.

    ``cooldown_bars`` darf hoechstens 200 sein, ``max_hold_bars`` 2000. Die
    Zahlen hier hinzuschreiben waere die zweite Wahrheit; sie stehen im
    Modell, und das Modell ist, was der Vorschlag durchlaufen muss.
    """
    from strategy.genome import Genome

    for metadaten in Genome.model_fields[feld].metadata:
        grenze = getattr(metadaten, "le", None)
        if grenze is not None:
            return int(grenze)
    raise ValueError(f"{feld} hat keine obere Grenze")


def als_auftrag(
    stufen: tuple[Takt, ...], *, ziel_trades: int, intervall: object
) -> str:
    """Der Abschnitt, der in den Prompt gehoert.

    Leer, wenn nichts gerechnet werden konnte - ein Auftragsabschnitt ohne
    Zahlen ist schlechter als keiner, weil er wie eine Anforderung aussieht.

    ``intervall`` ist **Pflicht** (Befund 496). Dieser Abschnitt ist in Befund
    432 gebaut worden, um den Auftrag in die Einheit zu bringen, die der
    Empfaenger einstellt - und er rechnete in **Tagen**, waehrend zwei der
    vier genannten Felder in **Kerzen** zaehlen. Auf Tageskerzen stimmt das
    zufaellig; auf Viertelstundenkerzen ist ein Takt von 20,5 Tagen **1968
    Balken**, und ``cooldown_bars`` darf hoechstens 200 sein. Die Anforderung
    war dort also nicht nur in der falschen Einheit, sondern im Schema gar
    nicht ausdrueckbar - und die Kerzenlaenge stand nirgends im Auftrag.
    Ein Vorgabewert waere genau der Weg zurueck dorthin.
    """
    if not stufen:
        return ""

    ziel = next((s for s in stufen if s.trades == ziel_trades), stufen[0])
    ziel_balken = balken_fuer_tage(ziel.takt_tage, intervall)
    sperre = _feldgrenze("cooldown_bars")

    zeilen = [
        "## Was das in Genom-Groessen heisst\n",
        "Die Trade-Zahl und der Sharpe je Trade oben sind **Ergebnisse**. "
        "Einstellen",
        "kannst du 'stop', 'targets', 'cooldown_bars' und 'max_hold_bars'. "
        "Umgerechnet",
        f"auf die {GEMEINSAME_TAGE} Tage, auf denen beide Beine Kerzen haben:",
        "",
        _kerzensatz(intervall) + " 'cooldown_bars'",
        "und 'max_hold_bars' zaehlen **Kerzen, nicht Tage**; verwechsle das "
        "nicht.",
        "",
        f"- **Takt: ein Trade alle {ziel.takt_tage:.1f} Tage** fuer "
        f"{ziel.trades} Trades - das sind **{ziel_balken} Balken**.",
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
        "    Trades  Takt/Tage  Takt/Balken  Streuung%  noetig SR  brutto%",
    ]
    for s in stufen:
        zeilen.append(
            f"    {s.trades:>6} {s.takt_tage:>10.1f} "
            f"{balken_fuer_tage(s.takt_tage, intervall):>12} "
            f"{s.streuung_pct:>10.2f} "
            f"{s.noetiger_sharpe:>10.4f} {s.brutto_pct:>8.2f}"
        )
    if ziel_balken > sperre:
        zeilen += [
            "",
            "**Der Takt passt auf dieser Kerzenlaenge nicht in das Feld.** "
            "'cooldown_bars'",
            f"darf hoechstens {sperre} sein, verlangt sind {ziel_balken} "
            f"Balken. Eine Sperrfrist",
            "kann den Takt hier also nicht herstellen - er muss aus den "
            "Einstiegsbedingungen",
            "kommen. Auf dieser Kerzenlaenge ist das Ziel damit schwerer zu "
            "treffen als auf",
            "Tageskerzen, und das ist gemessen, nicht vermutet (Befund "
            "450/489).",
        ]
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
