"""Die Randfrage der Skalenleiter - gebaut, und bis Befund 218 nie gestellt.

``am_rand`` beantwortet die Frage, ob die strengste Einteilung am Ende der
gemessenen Leiter liegt. Dann ist die Stichprobe kein Minimum, sondern das
Ende des Massbands.

Das Modul sagte *"``am_rand`` sagt es beim naechsten Mal von selbst"*, und das
Register sagte *"stellt die Frage jetzt von selbst"* - aber ausserhalb der
Tests hat die Eigenschaft keinen Aufrufer. Ein "naechstes Mal" gab es nicht.

Jetzt liegen beide Leitern aus Befund 143 als Daten vor, und die Antwort ist
fuer die beiden Betriebspunkte verschieden.
"""

from __future__ import annotations

import pytest

from research.referenz import SPOTPUNKT
from research.zeitskala import GEMESSEN, Skalenleiter, Skalenstufe


class TestDieBeidenGemessenenLeitern:
    def test_es_sind_die_zwei_betriebspunkte(self) -> None:
        assert set(GEMESSEN) == {"Tageskerzen", "15-Minuten-Kerzen"}

    def test_tageskerzen_treffen_den_referenzpunkt(self) -> None:
        """Die zurueckgerechnete Stichprobe muss zu dem passen, was das Gate
        an diesem Betriebspunkt tatsaechlich uebrig laesst."""
        streng = GEMESSEN["Tageskerzen"].strengste

        assert streng is not None
        assert streng.name == "Kalenderquartal"
        assert abs(streng.effektiv - SPOTPUNKT.effektiv) <= 5

    def test_die_quoten_aus_befund_143_kommen_wieder_heraus(self) -> None:
        tag = {s.name: s for s in GEMESSEN["Tageskerzen"].stufen}

        assert tag["Kalenderquartal"].quote == pytest.approx(0.737, abs=5e-3)
        assert tag["Halbjahr"].quote == pytest.approx(0.921, abs=5e-3)
        assert tag["Kalenderjahr"].quote == pytest.approx(1.000, abs=5e-3)

    def test_die_feine_leiter_hat_deutlich_mehr_trades(self) -> None:
        """Der Grund, warum die Zeitachse ueberhaupt als Weg gilt."""
        roh_tag = GEMESSEN["Tageskerzen"].stufen[0].roh
        roh_fein = GEMESSEN["15-Minuten-Kerzen"].stufen[0].roh

        assert roh_tag == 152
        assert roh_fein == 1985


class TestDieFrageIstJetztGestellt:
    def test_auf_tageskerzen_ist_das_quartal_ein_echtes_minimum(self) -> None:
        """Es liegt zwischen Monat und Halbjahr - kein Randeffekt."""
        assert GEMESSEN["Tageskerzen"].am_rand is False

    def test_auf_viertelstunden_liegt_die_strengste_sprosse_am_rand(self) -> None:
        """**Der Befund.** Die Gleichzeitigkeit ist zugleich die strengste und
        die erste gemessene Sprosse - unterhalb ist nichts vermessen."""
        leiter = GEMESSEN["15-Minuten-Kerzen"]
        streng = leiter.strengste

        assert leiter.am_rand is True
        assert streng is not None
        assert streng.name == "Gleichzeitigkeit"
        assert streng is leiter.stufen[0]

    def test_das_urteil_sagt_es_auch(self) -> None:
        text = GEMESSEN["15-Minuten-Kerzen"].urteil()

        assert "am Rand der gemessenen Leiter" in text
        assert "kein Minimum" in text

    def test_und_fuer_tageskerzen_sagt_es_das_gegenteil(self) -> None:
        text = GEMESSEN["Tageskerzen"].urteil()

        assert "echtes Minimum" in text
        assert "am Rand der gemessenen Leiter" not in text


class TestDieRegelSelbst:
    """Ohne diese Pruefungen koennte ``am_rand`` immer dasselbe sagen."""

    @staticmethod
    def _stufe(name: str, effektiv: int) -> Skalenstufe:
        return Skalenstufe(name=name, bloecke=10, roh=100, effektiv=effektiv, icc=0.1)

    def test_die_mitte_ist_kein_rand(self) -> None:
        leiter = Skalenleiter(
            stufen=(self._stufe("a", 90), self._stufe("b", 50), self._stufe("c", 95))
        )

        assert leiter.am_rand is False

    def test_die_erste_sprosse_ist_ein_rand(self) -> None:
        leiter = Skalenleiter(
            stufen=(self._stufe("a", 50), self._stufe("b", 90), self._stufe("c", 95))
        )

        assert leiter.am_rand is True

    def test_die_letzte_sprosse_auch(self) -> None:
        leiter = Skalenleiter(
            stufen=(self._stufe("a", 95), self._stufe("b", 90), self._stufe("c", 50))
        )

        assert leiter.am_rand is True

    def test_unter_drei_sprossen_gibt_es_keine_aussage(self) -> None:
        """Mit zweien ist jede am Rand - das waere eine Warnung ohne Inhalt."""
        leiter = Skalenleiter(stufen=(self._stufe("a", 50), self._stufe("b", 90)))

        assert leiter.am_rand is None
