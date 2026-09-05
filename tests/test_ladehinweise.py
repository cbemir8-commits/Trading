"""Ein Ladehinweis, der nur die Haelfte nennt, nimmt fuer die andere die Vorgabe.

**Befund 213.** ``cli backfill`` hat zwei Vorgaben, und beide sind fuer die
Tageskerzen falsch, auf denen alle elf Gates stehen:

* ``--von`` steht auf ``2020-03-30`` - gemessen die zweitschlechteste der
  sechs Stufen aus Befund 133 (Befund 212).
* ``--intervall`` steht auf ``1 15 60 240`` - **ohne D**.

``python -m cli backfill --von 2017-08-16``, die Zeile aus ``BEIM_NUTZER``,
laedt darum vier Intraday-Reihen ab 2017 und keine einzige Tageskerze. Und
``CandleStore.read`` faellt nicht auf Zusammenfassen zurueck: Was nicht
geladen wurde, ist leer.

Wer eines von beiden nennt, muss das andere mitnennen. Ein blosses
``python -m cli backfill`` ist etwas anderes - ein Wegweiser, keine Vorschrift.
"""

from __future__ import annotations

import re
from pathlib import Path

from research.historie import AB_TAGESKERZEN, empfohlener_start
from research.stand import BEIM_NUTZER

#: Wo nach Ladehinweisen gesucht wird - Quelltext und Anleitung.
QUELLEN = ("cli.py", "README.md", "research/stand.py", "research/reihenfolge.py")

#: Eine Befehlszeile, die ``backfill`` aufruft, mit allem was dahinter steht.
BEFEHL = re.compile(r"cli backfill(?P<rest>[^\n\"'\]]*)")


#: Zwei aneinandergrenzende Zeichenkettenliteralen - `"..." f"..."`.
#:
#: Python fuegt sie zusammen, ein Suchmuster ueber den Rohtext nicht. Ohne
#: diesen Schritt endet ein Hinweis am Zeilenumbruch, und ein ``--von`` in
#: der Folgezeile faellt unter den Tisch - der erste Entwurf dieses Tests hat
#: genau deshalb zwei bereits berichtigte Stellen angezeigt.
FUGE = re.compile(r"[\"']\s*\n\s*[fr]?[\"']")


def hinweise(text: str) -> list[str]:
    """Alle ``cli backfill``-Aufrufe eines Textes, auf ihre Argumente reduziert."""
    return [m.group("rest").strip() for m in BEFEHL.finditer(FUGE.sub("", text))]


def unvollstaendig(rest: str) -> bool:
    """Nennt dieser Hinweis genau eines von Intervall und Datum?

    Beides oder keines ist in Ordnung. Genau eines heisst: Fuer das andere
    gilt stillschweigend eine Vorgabe, die fuer Tageskerzen falsch ist.
    """
    hat_intervall = "--intervall" in rest or re.search(r"(^|\s)-i(\s|$)", rest)
    hat_datum = "--von" in rest
    return bool(hat_intervall) != bool(hat_datum)


class TestKeinHalberLadehinweis:
    def test_kein_hinweis_nennt_nur_eines_von_beidem(self) -> None:
        gefunden: list[tuple[str, str]] = []
        for quelle in QUELLEN:
            for rest in hinweise(Path(quelle).read_text()):
                if unvollstaendig(rest):
                    gefunden.append((quelle, rest))

        assert gefunden == [], (
            "Ladehinweis nennt Intervall oder Datum, nicht beides - fuer das "
            "fehlende gilt dann eine Vorgabe, die fuer Tageskerzen falsch ist."
        )

    def test_die_regel_faende_den_alten_stand(self) -> None:
        """Die Gegenprobe: genau die beiden Zeilen, die es gab."""
        assert unvollstaendig("--von 2017-08-16")
        assert unvollstaendig("--intervall 15")
        assert unvollstaendig("-i D")

    def test_beides_und_keines_sind_in_ordnung(self) -> None:
        assert not unvollstaendig("")
        assert not unvollstaendig("--intervall D --von 2017-08-16")
        assert not unvollstaendig("-i D --von 2017-08-16")


class TestDieZeileFuerDenNutzer:
    """Die eine Zeile, an der die Zulassung haengt."""

    @staticmethod
    def _backfill() -> str:
        return next(b for b, _ in BEIM_NUTZER if "backfill" in b)

    def test_sie_laedt_tageskerzen(self) -> None:
        """Ohne '-i D' laedt der Befehl 1m/15m/1h/4h - und keine Tageskerze."""
        befehl = self._backfill()

        assert "--intervall D" in befehl
        assert AB_TAGESKERZEN in befehl

    def test_das_datum_ist_das_gemessene(self) -> None:
        assert empfohlener_start("D") in self._backfill()

    def test_die_begruendung_nennt_das_intervall(self) -> None:
        """Sonst kuerzt es beim naechsten Mal jemand wieder weg."""
        warum = next(w for b, w in BEIM_NUTZER if "backfill" in b)

        assert "Tageskerzen" in warum
        assert "1m/15m/1h/4h" in warum


class TestDieVorgabenSindWirklichSo:
    """Die Behauptung, auf der alles hier steht - gemessen statt geglaubt."""

    def test_backfill_laedt_von_sich_aus_keine_tageskerzen(self) -> None:
        import cli
        from core.models import Interval

        assert Interval.D1 not in cli.DEFAULT_INTERVALS

    def test_der_speicher_fasst_nicht_selbst_zusammen(self) -> None:
        """``CandleStore.read`` kennt keinen Rueckfall auf feinere Kerzen.

        Gaebe es ihn, waere das alles halb so wichtig - dann wuerde eine
        fehlende Tagesreihe aus den 15-Minuten-Kerzen entstehen.
        """
        import inspect

        from data.store import CandleStore

        quelle = inspect.getsource(CandleStore.read)

        assert "resample" not in quelle
