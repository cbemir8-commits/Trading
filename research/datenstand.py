"""Die Reihe, auf der die Zahlen dieses Projekts gemessen sind - Befund 363.

Warum das ueberhaupt aufgeschrieben werden muss
------------------------------------------------
Der Kerzenspeicher steht nicht im Repository; er ist zu gross und liegt in
``.gitignore``. Die **Zahlen** aus ihm stehen ueberall: ``referenz.py`` haelt
den Spot- und den Perpetualpunkt, ``stand.py`` nennt Spannen und Trade-Zahlen,
ein Dutzend Tests pruefen sie nach.

Nur: Welche Reihe gemeint war, stand nirgends. Und die Reihe waechst.

Aufgefallen ist das, als der Entwicklungscontainer neu aufgesetzt wurde und der
Speicher mitging. Frisch nachgeladen - dieselben Symbole, dieselbe Quelle, nur
bis heute statt bis zum Messtag - **fielen fuenfzehn Tests**, und keiner davon
sagte "andere Reihe". Sie sagten 157 statt 156, 3350 statt 3300, 0,6759 statt
0,5826. Fuenfzehn Zahlen, die aussahen wie fuenfzehn Befunde und eine Ursache
hatten.

Woher die Angaben kommen
------------------------
Nicht geraten und nicht gesucht, sondern aus vier gepflegten Zahlen
**erschlossen** und dann gemessen:

* ``referenz.AUSSICHT.historie_tage = 3300`` - die gemeinsame Spanne. Mit dem
  ETH-Anfang 2017-08-16 ergibt das als Ende **2026-08-29**.
* ``test_datenbedarf.py`` nennt ``rueckwaerts_tage = 2054`` - so viel weiter
  reicht BTC zurueck. 2054 Tage vor dem ETH-Anfang ist **2012-01-01**.
* ``spanne_tage = 3300`` und ``rueckwaerts_tage = 2054`` gehen mit diesen
  Grenzen exakt auf, nicht auf eine Toleranz.
* Und die Gegenprobe von ausserhalb: Befund 360 hat ``cli abgleich`` auf dieser
  Reihe gefahren und **5355 Balken** gemeldet - genau die Zahl, die
  2012-01-01 bis 2026-08-29 ergibt.

Vier unabhaengig gepflegte Angaben, eine Reihe. Das ist keine Vermutung mehr.

Was damit reproduziert - und was nicht
--------------------------------------
Auf der so wiederhergestellten Reihe stimmen **zwoelf von fuenfzehn** Zahlen
wieder exakt, darunter alle tragenden: 156 rohe und 115 effektive Trades, 191
noetige, 3300 Tage Spanne, 2054 Tage Vorlauf, 6,0 noetige Jahre, neun von elf
Gates, Deflated Sharpe 0,5826.

**Drei nicht**, und sie bleiben offen: ein Kapitalendstand (2331,38 gegen
2318,32), ein Streuungswert (0,5994 gegen 0,5958) und die Schiefe ueber *alle*
Trades (3,3683 gegen 3,376) - zwischen 0,2 und 0,6 Prozent. An der Spanne liegt
es nicht, die ist auf den Tag geprueft. Gegengeprueft und **widerlegt** ist auch,
dass die Tageskerzen anders zusammengefasst waeren: Native Tageskerzen und aus
15-Minuten-Kerzen zusammengefasste stimmen an 2393 von 2394 Tagen bitgleich
ueberein. Bleibt als Erklaerung, dass Bitstamp einzelne alte Kerzen nachtraeglich
berichtigt hat - nachzupruefen ist das nicht, denn den damaligen Speicher gibt
es nicht mehr.

Diese drei Zahlen sind damit **nicht** reproduzierbar, und das steht hier, statt
dass jemand sie stillschweigend nachzieht. Eine gepflegte Zahl anzupassen, bis
sie zur Messung passt, waere die Umkehrung des Verfahrens.

Der Speicher *ist* diese Reihe nicht - er enthaelt sie
----------------------------------------------------
Das ist eine Berichtigung aus dem Bauen dieses Moduls, und sie ist wichtig.
Zuerst stand hier die Forderung, der Speicher **sei** die Zulassungsreihe; der
Speicher dieses Containers wurde darauf festgenagelt, und dann fielen drei
Tests, die vorher liefen: ``gegenprobe`` und ``randschnitt`` pruefen am
Datenrand und verlangen eine **angefangene** letzte Tageskerze - also einen
Speicher, der bis heute laeuft.

Beides ist richtig, und beides zugleich geht nicht. Also gilt die Teilung:

* Der Speicher laeuft **bis heute**. Gehandelt wird auf allem, was da ist.
* Wer die Zahlen dieses Katalogs nachrechnet, **schneidet** auf ``SERIENENDE``.
* ``fehlt()`` prueft nur, ob sich das ueberhaupt schneiden laesst.

**Offen bleibt die Folge**: Die zehn Tests, die den Katalog nachrechnen, holen
ihre Kerzen noch ungeschnitten aus dem Speicher - sie reproduzieren also nur,
solange der Speicher zufaellig am Messtag endet. Der Schnitt gehoert dort
hinein; dass die Reihe benannt ist, ist die Voraussetzung dafuer und noch nicht
die Sache selbst.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    import pandas as pd

#: Der Rahmentyp, ohne pandas beim Import zu laden - dieses Modul wird von
#: 'cli stand' gelesen, und das soll nicht an einer Einfuhr haengen.
PandasRahmen = TypeVar("PandasRahmen", bound="pd.DataFrame")

#: Letzter Balken der Reihe, auf der die Zahlen des Katalogs gemessen sind.
#:
#: **Kein Vorschlag fuer den Betrieb.** Gehandelt wird auf allem, was da ist;
#: dieses Datum sagt nur, wogegen die gepflegten Zahlen geprueft werden
#: koennen. Die Zulassung einer Strategie auf einer eingefrorenen Reihe zu
#: messen und sie dann auf einer anderen zu handeln waere genau der Fehler, den
#: 'cli abgleich' sucht.
SERIENENDE = date(2026, 8, 29)

#: Die Kerzenlaenge, auf der zugelassen wird (Befund 213: dort stehen alle elf).
INTERVALL = "D"


@dataclass(frozen=True, slots=True)
class Reihe:
    """Ein Bein der Zulassungsreihe und seine gemessene Laenge."""

    symbol: str
    von: date
    balken: int

    @property
    def bis(self) -> date:
        return SERIENENDE

    def laenge_stimmt(self) -> bool:
        """Deckt sich die aufgeschriebene Balkenzahl mit den Grenzen?

        Tageskerzen, also ein Balken je Tag und beide Enden eingeschlossen.
        Eine Luecke in der Reihe wuerde hier auffallen - bei Bitstamp gibt es
        keine, geprueft bei der Wiederherstellung.
        """
        return self.balken == (SERIENENDE - self.von).days + 1


#: Die beiden Beine des Zulassungskorbs, in der Reihenfolge ihres Anfangs.
REIHEN: tuple[Reihe, ...] = (
    Reihe("BTCUSD_BITSTAMP", date(2012, 1, 1), 5355),
    Reihe("ETHUSD_BITSTAMP", date(2017, 8, 16), 3301),
)

#: Die gemeinsame Spanne beider Beine - dieselbe Zahl wie
#: ``referenz.AUSSICHT.historie_tage``, und ``test_datenstand.py`` haelt die
#: beiden aneinander.
GEMEINSAME_TAGE = 3300

#: So viel weiter reicht BTC zurueck als ETH (``rueckwaerts_tage``).
VORLAUF_TAGE = 2054


def jueneres_bein() -> Reihe:
    """Das Bein, das den gemeinsamen Anfang setzt - hier ETH."""
    return max(REIHEN, key=lambda r: r.von)


def aelteres_bein() -> Reihe:
    return min(REIHEN, key=lambda r: r.von)


def befehle() -> tuple[str, ...]:
    """Die Befehle, die diese Reihe wiederherstellen.

    Bybit ist aus diesem Container gesperrt, Bitstamp nicht - deshalb
    ``cli referenz`` und nicht ``cli backfill``. Die Kerzen landen unter einem
    eigenen Symbol und vermischen sich nicht mit Handelsdaten (Befund 102:
    ein Bericht auf Forschungskerzen gilt nie als zugelassen).

    **``--bis`` ist ausschliessend**, und das steht hier, weil es mich einen
    Anlauf gekostet hat: Mit ``--bis 2026-08-29`` endet die Reihe am 28. und
    ist einen Balken zu kurz. Darum ``SERIENENDE`` plus einen Tag. Aufgefallen
    ist es nur, weil der Befehl wirklich gelaufen ist - aus der Signatur geht
    es nicht hervor.

    Und **vorher raeumen**: Ein Speicher, der schon eine laengere Reihe haelt,
    wird durch ein Nachladen nicht kuerzer. Dafuer die erste Zeile.
    """
    nach = SERIENENDE + timedelta(days=1)
    zeilen = [
        "rm -rf "
        + " ".join(f"data_store/candles/{r.symbol}/{INTERVALL}" for r in REIHEN)
    ]
    zeilen += [
        f"python -m cli referenz -i {INTERVALL} --symbol {r.symbol} "
        f"--von {r.von.isoformat()} --bis {nach.isoformat()}"
        for r in REIHEN
    ]
    return tuple(zeilen)


def geschnitten(frame: PandasRahmen) -> PandasRahmen:
    """Einen Kerzenrahmen auf die Zulassungsreihe kuerzen.

    Der eine Handgriff, der die Zahlen des Katalogs nachrechenbar macht: Wer
    sie prueft, nimmt nicht, was im Speicher liegt, sondern die Reihe, auf der
    sie gemessen sind. Der Speicher darf weiterlaufen - gehandelt wird auf
    allem, was da ist.

    Nur am oberen Ende geschnitten. Der Anfang kommt aus dem jueneren Bein und
    besorgt sich ``common_range`` ohnehin selbst; ein zweiter Schnitt hier
    wuerde eine zu kurze Reihe stillschweigend durchlassen, und das soll
    ``fehlt`` melden.
    """
    import pandas as pd

    if frame is None or frame.empty or "open_time" not in frame.columns:
        return frame
    zeiten = pd.to_datetime(frame["open_time"], utc=True)
    grenze = pd.Timestamp(SERIENENDE, tz="UTC")
    return frame[zeiten <= grenze].reset_index(drop=True)


def fehlt(vorhanden: Mapping[str, tuple[date, date, int]]) -> tuple[str, ...]:
    """Was dem vorliegenden Speicher fehlt, um die Zulassungsreihe zu enthalten.

    **Enthalten, nicht gleichen** - und das ist eine Berichtigung aus dem
    Bauen dieses Moduls. Zuerst stand hier "der Speicher **ist** die Reihe",
    der Speicher dieses Containers wurde darauf festgenagelt, und dann fielen
    drei Tests, die vorher liefen: ``gegenprobe`` und ``randschnitt`` pruefen
    am Datenrand und verlangen eine **angefangene** letzte Tageskerze, also
    einen Speicher, der bis heute laeuft.

    Beides ist richtig und beides zugleich geht nicht. Also gilt die Teilung:
    Der Speicher laeuft bis heute, und wer die Zahlen des Katalogs nachrechnet,
    **schneidet** auf ``SERIENENDE``. Hier wird darum nur geprueft, ob sich das
    ueberhaupt schneiden laesst - ob die Reihe drin **steckt**.

    Ein Satz je Mangel, in der Sprache des Lesers und nicht als Differenz
    zweier Zahlen: "beginnt erst 2017-08-16" sagt, was zu tun ist,
    "3350 statt 3300" nicht.
    """
    saetze: list[str] = []
    for reihe in REIHEN:
        stand = vorhanden.get(reihe.symbol)
        if stand is None:
            saetze.append(f"{reihe.symbol}: fehlt im Speicher")
            continue
        von, bis, balken = stand
        if von > reihe.von:
            saetze.append(
                f"{reihe.symbol}: beginnt erst {von}, gebraucht ab {reihe.von}"
            )
        if bis < SERIENENDE:
            saetze.append(
                f"{reihe.symbol}: endet schon {bis}, gebraucht bis {SERIENENDE}"
            )
        # Eine Luecke ist nur bei genau passenden Grenzen zu erkennen; laeuft
        # der Speicher weiter, sagt die Balkenzahl nichts ueber Luecken im
        # Inneren, und zwei Meldungen fuer eine Ursache schicken den Leser auf
        # die falsche Suche.
        if von == reihe.von and bis == SERIENENDE and balken != reihe.balken:
            saetze.append(
                f"{reihe.symbol}: {balken} Balken bei genau diesen Grenzen, "
                f"erwartet {reihe.balken} - eine Luecke in der Reihe"
            )
    return tuple(saetze)
