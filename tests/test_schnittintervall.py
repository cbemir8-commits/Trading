"""Der Schnitt muss die Kerzenlaenge kennen - Befund 491.

**Mein eigener Fehler aus dem Zyklus davor.** Befund 490 hat vier buchenden
Befehlen ``alle_geschnitten`` gegeben. Das kuerzt auf ``SERIENENDE``
(2026-08-29) - **unabhaengig von der Kerzenlaenge**. Alle vier nehmen ``-i``,
und fuer feine Kerzen gilt ``FEINENDE`` (2026-10-18):

    BTCUSD_BITSTAMP D :   5355 ->   5355 Balken   unveraendert
    BTCUSD_BITSTAMP 15: 229728 -> 224929 Balken   4.799 Balken weg

Sieben Wochen, stillschweigend. Die passende Fassung lag im selben Modul
daneben (``fein_geschnitten``), und ich habe die falsche genommen.

Und der Fehler war aelter als mein Eingriff
-------------------------------------------
Beim Nachsehen stellte sich heraus: Die **fuenf** Befehle, die schon vor 490
schnitten - ``abstand``, ``anatomie``, ``rennen``, ``stand``, ``aufteilung`` -
nehmen ebenfalls ``-i`` mit Vorgabe ``D`` und riefen ebenfalls
``alle_geschnitten``. Der Mangel bestand also seit Befund 387/390/394/400 und
war nur nie gefahren worden; mein Fehler hat einen aelteren aufgedeckt.

Alle neun gehen jetzt ueber ``datenstand.nach_intervall``.

Was der Verteiler tut
---------------------
Er waehlt die Reihe nach dem Etikett der Kerzenlaenge und **sagt, welche**:

    D    -> SERIENENDE, geschlossen am oberen Ende  (<=)
    15   -> FEINENDE, halboffen                     (<)
    sonst-> **nicht geschnitten**, und das steht in der Zeile

Die halboffene Grenze ist kein Zierrat: ``fein_geschnitten`` sagt selbst, dass
ein ``<=`` den ersten Balken des Folgetags mitnimmt und 229.729 statt 229.728
ergibt. Ein Verteiler, der die Vergleiche nachbaut, baut genau diesen Fehler
nachher ein - deshalb ruft er die beiden vorhandenen Funktionen auf.

Fuer eine Kerzenlaenge ohne gepflegte Reihe wird **nicht** geschnitten. Das
ist die Richtung aus Befund 370 - *"auf allem zu rechnen, was da ist, ist
richtig; es muss nur dastehen"* -, und mit dem Ende einer fremden
Kerzenlaenge zu kuerzen waere genau der Fehler, um den es hier geht.

Ein Verteiler statt neun Verzweigungen
--------------------------------------
Wer an neun Stellen von Hand waehlt, waehlt an der zehnten falsch (Befund
168). Und die Inventur in ``test_abstandsreihe`` hing am Namen **einer**
Funktion: Nach der Umstellung sah sie auf einen Schlag einen Schneider statt
neun. Sie fragt jetzt ``SCHNITTWEGE`` - dieselbe Lehre wie bei
``BUCHUNGSWEGE`` in Befund 282 und 479, hier zum dritten Mal.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from research.datenstand import (
    FEINENDE,
    REIHENENDE,
    SERIENENDE,
    nach_intervall,
)

WURZEL = Path(__file__).resolve().parents[1]


def _rahmen(von: str, bis: str, freq: str) -> pd.DataFrame:
    zeiten = pd.date_range(von, bis, freq=freq, tz="UTC")
    return pd.DataFrame({"open_time": zeiten, "close": range(len(zeiten))})


class TestDerVerteilerWaehltNachKerzenlaenge:
    def test_tageskerzen_auf_serienende(self) -> None:
        roh = {"x": _rahmen("2026-08-01", "2026-09-30", "D")}

        kurz, zeile = nach_intervall(roh, "D")

        assert kurz["x"]["open_time"].max().date() == SERIENENDE
        assert str(SERIENENDE) in zeile

    def test_feinkerzen_auf_feinende(self) -> None:
        """**Der Fehler aus 490, als Gegenprobe.** Mit ``SERIENENDE`` waeren
        hier sieben Wochen weg."""
        roh = {"x": _rahmen("2026-10-01", "2026-10-31", "15min")}

        kurz, zeile = nach_intervall(roh, "15")

        ende = kurz["x"]["open_time"].max()
        assert ende.date() < FEINENDE, ende
        assert ende.date() > SERIENENDE, "nicht auf die Tagesreihe gekuerzt"
        assert str(FEINENDE) in zeile

    def test_die_feine_grenze_bleibt_halboffen(self) -> None:
        """``fein_geschnitten`` sagt es selbst: Ein ``<=`` nimmt den ersten
        Balken des Folgetags mit. Der Verteiler ruft die Funktion, statt den
        Vergleich nachzubauen."""
        roh = {"x": _rahmen("2026-10-17", "2026-10-19", "15min")}

        kurz, _zeile = nach_intervall(roh, "15")
        zeiten = kurz["x"]["open_time"]

        assert (zeiten.dt.date < FEINENDE).all()

    def test_fremde_kerzenlaenge_wird_nicht_geschnitten(self) -> None:
        """Die Richtung aus Befund 370: lieber ungeschnitten und benannt als
        mit dem Ende einer fremden Reihe gekuerzt."""
        roh = {"x": _rahmen("2020-01-01", "2026-12-31", "W")}

        kurz, zeile = nach_intervall(roh, "W")

        assert len(kurz["x"]) == len(roh["x"])
        assert "keine gepflegte" in zeile
        assert "W" in zeile

    def test_die_zeile_nennt_die_zahl_der_verworfenen_balken(self) -> None:
        roh = {"x": _rahmen("2026-08-01", "2026-09-30", "D")}

        _kurz, zeile = nach_intervall(roh, "D")

        assert "Balken ausserhalb" in zeile

    def test_und_schweigt_wo_nichts_wegfaellt(self) -> None:
        """Sonst stuende in jedem Lauf eine Null, und niemand liest sie."""
        roh = {"x": _rahmen("2026-08-01", "2026-08-29", "D")}

        _kurz, zeile = nach_intervall(roh, "D")

        assert "ausserhalb" not in zeile

    def test_beide_reihen_stehen_in_der_tafel(self) -> None:
        assert REIHENENDE == {"D": SERIENENDE, "15": FEINENDE}


class TestAlleNeunGehenUeberDenVerteiler:
    """Die Regel. Kein Befehl waehlt die Reihe mehr von Hand."""

    def _befehle(self) -> dict[str, str]:
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        return {
            n.name: ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
        }

    def test_niemand_ruft_die_tagesfassung_direkt(self) -> None:
        """``alle_geschnitten`` kennt die Kerzenlaenge nicht - wer es direkt
        ruft, hat den Fehler aus 491 wieder."""
        offen = [
            name
            for name, q in self._befehle().items()
            if "alle_geschnitten(" in q
        ]

        assert offen == [], (
            "ruft die Tagesfassung direkt auf, statt 'nach_intervall' zu "
            f"fragen - genau das war Befund 491: {offen}"
        )

    def test_und_es_gibt_welche_die_den_verteiler_fragen(self) -> None:
        """Nichtleere-Zusicherung (Befund 479): Sonst waere die Regel darueber
        leer erfuellt."""
        mit = [name for name, q in self._befehle().items() if "nach_intervall(" in q]

        assert len(mit) >= 9, sorted(mit)

    def test_die_vier_buchenden_sind_dabei(self) -> None:
        from tests.zaehlerwege import zaehlende_befehle

        mit = {name for name, q in self._befehle().items() if "nach_intervall(" in q}

        assert {"korb", "machbarkeit", "adaptiv", "verbund"} <= mit
        assert zaehlende_befehle() & mit == {
            "korb",
            "machbarkeit",
            "adaptiv",
            "verbund",
        }


class TestDieInventurSiehtDenNeuenWeg:
    """Sie hing am Namen **einer** Funktion - zum dritten Mal in diesem
    Projekt (282, 479, 491)."""

    def test_sie_zaehlt_wieder_acht(self) -> None:
        from tests.test_abstandsreihe import TestDieInventurStimmtNoch

        schneidet, _nennt, _keins = TestDieInventurStimmtNoch._inventur()

        assert len(schneidet) == 8, sorted(schneidet)

    def test_und_kennt_beide_wege(self) -> None:
        from tests.schnittwege import SCHNITTWEGE

        assert "alle_geschnitten" in SCHNITTWEGE
        assert "nach_intervall" in SCHNITTWEGE


@pytest.mark.daten
class TestAmEchtenSpeicher:
    def _frame(self, intervall: str):
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore

        store = CandleStore(get_settings().paths.data_store)
        frame = store.read("BTCUSD_BITSTAMP", Interval(intervall))
        if frame.empty:
            pytest.skip(
                f"keine {intervall}-Kerzen im Speicher dieses Containers - "
                f"mit 'cli backfill' zu holen"
            )
        return {"BTCUSD_BITSTAMP": frame}

    def test_die_feinreihe_verliert_nichts_mehr(self) -> None:
        """**Die Messung, die den Fehler gezeigt hat.** Mit der Tagesfassung
        waren es 4.799 Balken weniger."""
        roh = self._frame("15")
        kurz, _zeile = nach_intervall(roh, "15")

        assert len(kurz["BTCUSD_BITSTAMP"]) == len(roh["BTCUSD_BITSTAMP"])

    def test_und_die_tagesreihe_auch_nicht(self) -> None:
        roh = self._frame("D")
        kurz, _zeile = nach_intervall(roh, "D")

        assert len(kurz["BTCUSD_BITSTAMP"]) == len(roh["BTCUSD_BITSTAMP"])

    def test_die_tagesfassung_wuerde_die_feinreihe_kuerzen(self) -> None:
        """Die Gegenprobe zum Fund: Der alte Aufruf war wirklich falsch, nicht
        nur theoretisch."""
        from research.datenstand import alle_geschnitten

        roh = self._frame("15")
        falsch = alle_geschnitten(roh)

        assert len(falsch["BTCUSD_BITSTAMP"]) < len(roh["BTCUSD_BITSTAMP"])
