"""Der gesunde Roboter galt als tot - Befund 383.

Dritte Runde derselben Methode wie in 381 und 382: einen gemessenen Zustand
nehmen und fragen, ob die Oberflaeche ihn zeigt. Diesmal der **Umkehrfall** -
nicht ein Problem, das als gesund dasteht, sondern gesund, das als Problem
dasteht.

Der Herzschlag entsteht in ``LiveTrader._publish``, und das laeuft **je
Kerze**; eine eigene Herzschlagschleife gibt es nicht (gepruefter unten). Die
Leseseite verglich ihn aber gegen eine feste Frist von zwanzig Minuten, deren
Kopf das selbst sagte: *"Auf einem 15-Minuten-Intervall schreibt er nur alle
15 Minuten."* Gemessen, jeweils eine Minute vor der naechsten Kerze:

    Intervall   Kerzenlaenge   Dashboard
          1m           1 min   laeuft
         15m          15 min   laeuft
          1h           1 h     TOT - kein Lebenszeichen seit 59 min
          4h           4 h     TOT - seit 239 min
          1d          24 h     TOT - seit 1439 min

**Jedes Intervall oberhalb von 15 Minuten zeigte einen gesunden Lauf als
tot.** Darunter die Tageskerzen - und auf denen steht jede Gate-Zahl dieses
Projekts (Befund 213), dort gehoert der Spitzenkandidat hin, und die
Zulassungsreihe ist taeglich.

Warum das nicht kosmetisch ist
------------------------------
``web/journal.py`` nennt im Kopf genau eine Sache, die das Dashboard koennen
muss:

    Und eines muss es koennen: **erkennen, dass der Handel tot ist.** Genau
    dafuer sind Handel und Website getrennte Prozesse.

Ein Alarm, der im gemeinten Betrieb dauerhaft leuchtet, ist keiner. Er
verbraucht die eine Meldung, fuer die es die Trennung gibt.

Die Behebung
------------
Der Schnappschuss sagt jetzt, wie weit seine Schreibvorgaenge auseinander
liegen (``heartbeat_erwartet_s``), und die Frist ist
``max(20 min, Kerzenlaenge + 5 min)``. Fuenf Minuten, weil das genau die Luft
ist, die die alten zwanzig dem 15-Minuten-Intervall liessen. Damit bleibt das
Urteil fuer M15 und alles darunter **unveraendert**, und kein Fall wird
strenger als vorher.
"""

from __future__ import annotations

import ast
import inspect
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.models import Interval
from web.journal import (
    HEARTBEAT_MARGE,
    HEARTBEAT_TIMEOUT,
    LiveJournal,
    heartbeat_frist,
    read_view,
)

#: Die Intervalle, auf denen der Fehler auftrat - und das eine, auf dem das
#: Projekt zertifiziert ist.
LAENGER_ALS_DIE_FRIST = (Interval.H1, Interval.H4, Interval.D1)


def _schnappschuss(intervall: Interval) -> dict:
    return {
        "interval": intervall.label,
        "heartbeat_erwartet_s": int(intervall.duration.total_seconds()),
    }


def _sicht(tmp_path: Path, intervall: Interval, alter: timedelta):
    """Eine Ablage mit einem Herzschlag dieses Alters - und ihre Lesung."""
    journal = LiveJournal(tmp_path)
    journal.write_snapshot(_schnappschuss(intervall))
    datei = tmp_path / "live.json"
    daten = json.loads(datei.read_text())
    daten["heartbeat"] = (datetime.now(UTC) - alter).isoformat()
    datei.write_text(json.dumps(daten))
    return read_view(tmp_path)


class TestDerHerzschlagHatDieKerzenlaenge:
    """Erst der Grund: Es gibt keine zweite Quelle."""

    def test_er_entsteht_nur_im_kerzenpfad(self) -> None:
        """``_publish`` wird ausschliesslich aus ``_verarbeite_kerze`` gerufen.

        Gaebe es eine eigene Schleife, waere die Frist richtig und der Fehler
        laege woanders - deshalb steht das hier und nicht in der Prosa.
        """
        from execution.live import LiveTrader

        quelle = inspect.getsource(LiveTrader)
        baum = ast.parse(quelle.lstrip())
        rufer = {
            knoten.name
            for knoten in ast.walk(baum)
            if isinstance(knoten, ast.FunctionDef | ast.AsyncFunctionDef)
            and "_publish(" in ast.unparse(knoten)
            and knoten.name != "_publish"
        }

        assert rufer == {"_verarbeite_kerze"}

    @pytest.mark.asyncio
    async def test_der_schnappschuss_nennt_seinen_abstand(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        from tests.test_live import build_rig

        rig = build_rig(tmp_path, btcusdt, risk, bybit_settings)
        await rig.feed()

        daten = json.loads((tmp_path / "state" / "live.json").read_text())
        s = daten.get("snapshot", daten)

        assert s["heartbeat_erwartet_s"] == Interval.M15.duration.total_seconds()


class TestEinGesunderLaufGiltNichtMehrAlsTot:
    """**Der Befund.** Eine Minute vor der naechsten Kerze ist nichts los."""

    @pytest.mark.parametrize("intervall", LAENGER_ALS_DIE_FRIST)
    def test_kurz_vor_der_naechsten_kerze_laeuft_er(
        self, tmp_path, intervall: Interval
    ) -> None:
        sicht = _sicht(tmp_path, intervall, intervall.duration - timedelta(minutes=1))

        assert sicht.alive, f"{intervall.label} galt als tot"

    def test_und_das_gilt_vor_allem_fuer_tageskerzen(self, tmp_path) -> None:
        """Auf denen steht jede Gate-Zahl des Projekts (Befund 213)."""
        sicht = _sicht(tmp_path, Interval.D1, timedelta(hours=23, minutes=59))

        assert sicht.alive
        assert heartbeat_frist(_schnappschuss(Interval.D1)) == (
            Interval.D1.duration + HEARTBEAT_MARGE
        )


class TestEinWirklichToterLaufWirdWeiterErkannt:
    """Die Gegenprobe - sonst waere der Fehler nur verschoben.

    Das ist die eine Sache, die das Dashboard laut seinem eigenen Kopf koennen
    muss; eine Behebung, die sie nimmt, waere schlimmer als der Fehler.
    """

    @pytest.mark.parametrize(
        "intervall", (Interval.M1, Interval.M15, Interval.H1, Interval.H4, Interval.D1)
    )
    def test_jenseits_der_frist_ist_er_tot(
        self, tmp_path, intervall: Interval
    ) -> None:
        frist = heartbeat_frist(_schnappschuss(intervall))

        sicht = _sicht(tmp_path, intervall, frist * 1.5)

        assert not sicht.alive
        assert "kein Lebenszeichen" in sicht.status_text


class TestKeinFallWirdStrengerAlsVorher:
    def test_die_frist_faellt_nie_unter_die_alte(self) -> None:
        for intervall in Interval:
            if intervall is Interval.MN1:
                continue  # hat keine feste Dauer, siehe unten
            assert heartbeat_frist(_schnappschuss(intervall)) >= HEARTBEAT_TIMEOUT

    def test_das_monatsintervall_kostet_nicht_den_schnappschuss(self) -> None:
        """**Ein Fehler, den ich eingebaut und der Test gefunden hat.**

        ``Interval.MN1.duration`` wirft ("hat keine feste Dauer"). Erst stand
        der Aufruf ungeschuetzt in '_snapshot' - und '_publish' schluckt
        Ausnahmen, also waere das Dashboard **eingefroren** statt bloss zu
        frueh alarmiert. Jetzt gibt es ``None``, und die Leseseite bleibt bei
        ihren zwanzig Minuten.
        """
        with pytest.raises(ValueError, match="keine feste Dauer"):
            _ = Interval.MN1.duration
        assert heartbeat_frist({"heartbeat_erwartet_s": None}) == HEARTBEAT_TIMEOUT

    def test_fuer_m15_und_darunter_bleibt_sie_gleich(self) -> None:
        """Das Urteil fuer die Intervalle, auf denen es stimmte, aendert sich
        nicht - sonst waere es eine Lockerung im Vorbeigehen."""
        for intervall in (Interval.M1, Interval.M5, Interval.M15):
            assert heartbeat_frist(_schnappschuss(intervall)) == HEARTBEAT_TIMEOUT

    def test_ohne_die_angabe_bleibt_es_beim_alten_wert(self) -> None:
        """Alte Datei, fremder Schreiber: dieselbe Antwort wie vor 383."""
        assert heartbeat_frist({}) == HEARTBEAT_TIMEOUT
        assert heartbeat_frist({"heartbeat_erwartet_s": None}) == HEARTBEAT_TIMEOUT
        assert heartbeat_frist({"heartbeat_erwartet_s": "kaputt"}) == HEARTBEAT_TIMEOUT
        assert heartbeat_frist({"heartbeat_erwartet_s": 0}) == HEARTBEAT_TIMEOUT
        assert heartbeat_frist({"heartbeat_erwartet_s": -60}) == HEARTBEAT_TIMEOUT

    def test_die_marge_ist_die_luft_der_alten_frist(self) -> None:
        """20 - 15 = 5. Die Zahl ist nicht gewaehlt, sondern uebernommen."""
        assert HEARTBEAT_TIMEOUT - Interval.M15.duration == HEARTBEAT_MARGE


class TestDieDauerStehtInIhrerGroessenordnung:
    """'seit 1439 min' ist eine halbe Auskunft."""

    @pytest.mark.parametrize(
        ("spanne", "erwartet"),
        [
            (timedelta(minutes=30), "30 min"),
            (timedelta(minutes=59), "59 min"),
            (timedelta(hours=1, minutes=36), "1.6 h"),
            (timedelta(hours=6, minutes=6), "6.1 h"),
            (timedelta(days=1, hours=12), "1.5 d"),
        ],
    )
    def test_sie_waehlt_die_einheit(self, spanne: timedelta, erwartet: str) -> None:
        from web.journal import _dauer

        assert _dauer(spanne) == erwartet

    def test_eine_negative_spanne_wird_nicht_negativ_gemeldet(self) -> None:
        """Uhren laufen auseinander; ein Herzschlag aus der Zukunft ist
        moeglich und 'seit -3 min' waere Unsinn."""
        from web.journal import _dauer

        assert _dauer(timedelta(minutes=-3)) == "0 min"

    def test_der_statustext_benutzt_sie(self, tmp_path) -> None:
        sicht = _sicht(tmp_path, Interval.D1, timedelta(days=2))

        assert sicht.status_text == "kein Lebenszeichen seit 2.0 d"
