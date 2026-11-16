"""Die Zweitschrift war abgedriftet, und niemand hat verglichen - Befund 498.

Was gemessen wurde
------------------
``ausschluss.GESCHEITERTE_EIGENBAUTEN`` haelt acht gescheiterte Regeln mit
Trades und Sharpe je Trade. Ihre Begruendung stand im Kommentar daneben:

    Sie stehen **nicht** im Journal des Research-Loops, weil sie ausserhalb
    davon entstanden sind - und fehlten dem Analysten deshalb vollstaendig.

Das galt, bis sie gebucht wurden. Heute stehen alle acht im **versionierten**
Versuchsverzeichnis ``state/trials.json`` (Herkunft ``gen11 partnersuche`` und
``gen12 kalibriert``), und ``_ausschluesse`` liest sie dort:

    gescheiterte = gemessen or GESCHEITERTE_EIGENBAUTEN

Das Verzeichnis hat Vorrang und ist eine **Obermenge** - elf Eintraege gegen
acht. Die Liste ist damit eine Zweitschrift, und sie war abgedriftet:

    Volumenschock breit                      0,138702  ->  0,138701
    Rueckkehr zum Volumenschwerpunkt breit  -0,170385  -> -0,170436
    Ueberverkauft ohne Trendfilter          -0,191948  -> -0,191881
    Enge vor Bewegung breit                  0,223766  ->  0,223825

Vier von acht, bis 6,7e-5. **Keine davon bewegt eine Aussage** - eine
gescheiterte Regel bleibt gescheitert, und der Auftragstext sagt dasselbe. Der
Mangel ist die Stille: Waere eine Zahl materiell abgedriftet, waere es genauso
still geblieben.

Was diese Datei tut
-------------------
Sie vergleicht die Zweitschrift mit dem Verzeichnis - Namen, Trades und
Zahlen - und braucht dafuer **keinen** Uebersprung: Beide Staende liegen im
Repository, also ist der Vergleich immer moeglich. Das ist der Unterschied zu
einer Wache, die auf den Kerzenspeicher wartet.

Die Richtung des Abgleichs: Das **Verzeichnis** ist die Quelle. Es wird vom
Buchungsweg geschrieben, in dem Augenblick, in dem gemessen wurde; die Liste
ist von Hand nachgetragen. Wer das umdreht, pflegt die Abschrift und
berichtigt die Messung.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.ausschluss import GESCHEITERTE_EIGENBAUTEN, aus_versuchsverzeichnis

WURZEL = Path(__file__).resolve().parents[1]
VERZEICHNIS = WURZEL / "state" / "trials.json"

#: Wie weit zwei Schreibweisen derselben Messung auseinanderliegen duerfen.
#:
#: Die Liste haelt sechs Stellen, das Verzeichnis die volle Gleitkommazahl -
#: ein Abstand in der siebten Stelle ist die Rundung und kein Abdriften.
RUNDUNG = 5e-7


def _register() -> dict[str, tuple[int, float]]:
    return {e[0]: (e[1], e[2]) for e in aus_versuchsverzeichnis(VERZEICHNIS)}


class TestDasVerzeichnisLiegtImRepository:
    """Ohne das waere der Abgleich eine Wache auf gut Glueck."""

    def test_die_datei_ist_da(self) -> None:
        assert VERZEICHNIS.exists(), VERZEICHNIS

    def test_und_sie_traegt_eintraege(self) -> None:
        assert _register(), "ohne Eintraege ist nichts zu vergleichen"


class TestJedeZeileStehtImVerzeichnis:
    def test_die_namen_stimmen(self) -> None:
        """Faellt einer heraus, ist er im Verzeichnis anders geschrieben - und
        dann greift der Vorrang nicht, sondern es entstehen zwei Familien."""
        register = _register()
        fehlen = sorted(
            name for name, _t, _s in GESCHEITERTE_EIGENBAUTEN if name not in register
        )

        assert fehlen == [], (
            "steht in der Zweitschrift, aber nicht im Versuchsverzeichnis - "
            f"entweder die Kennung weicht ab oder die Buchung fehlt: {fehlen}"
        )

    @pytest.mark.parametrize(
        ("name", "trades", "sharpe"),
        GESCHEITERTE_EIGENBAUTEN,
        ids=[e[0] for e in GESCHEITERTE_EIGENBAUTEN],
    )
    def test_trades_und_zahl_stimmen(
        self, name: str, trades: int, sharpe: float
    ) -> None:
        """**Die Regel des Befundes.** Vier von acht Zahlen wichen ab, und
        nichts hat es gemeldet."""
        register = _register()
        if name not in register:
            pytest.skip(
                f"'{name}' ist im Versuchsverzeichnis nicht gebucht - das "
                f"meldet die Regel ueber den Namen, nicht diese hier"
            )
        r_trades, r_sharpe = register[name]

        assert trades == r_trades, (name, trades, r_trades)
        assert abs(sharpe - r_sharpe) <= RUNDUNG, (
            f"{name}: Zweitschrift {sharpe}, Verzeichnis {r_sharpe} - "
            f"Abstand {abs(sharpe - r_sharpe):.2e} ueber der Rundung. Die "
            f"Messung steht im Verzeichnis; die Liste wird nachgezogen, nicht "
            f"umgekehrt"
        )


class TestDasVerzeichnisIstDieObermenge:
    def test_es_kennt_mindestens_die_acht(self) -> None:
        """Sonst waere der Vorrang in ``_ausschluesse`` ein Verlust: Mit
        ``gemessen or GESCHEITERTE_EIGENBAUTEN`` faellt die Liste ganz weg,
        sobald das Verzeichnis **irgendetwas** hat."""
        assert set(e[0] for e in GESCHEITERTE_EIGENBAUTEN) <= set(_register())

    def test_und_mehr_als_sie(self) -> None:
        """Gemessen: elf gegen acht. Wird das gleich, ist die Zweitschrift
        keine Teilmenge mehr, sondern eine zweite Quelle."""
        assert len(_register()) > len(GESCHEITERTE_EIGENBAUTEN)

    def test_der_vorrang_steht_so_in_der_befehlsdatei(self) -> None:
        """Die Regel darueber zaehlt nur, wenn der Vorrang wirklich so
        gebaut ist - geprueft am Aufbau, nicht an einer Behauptung."""
        import ast

        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        fn = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "_ausschluesse"
        )
        quelle = ast.unparse(fn)

        assert "gemessen or GESCHEITERTE_EIGENBAUTEN" in quelle
        assert "aus_versuchsverzeichnis(" in quelle


class TestDieBegruendungIstNachgezogen:
    def test_der_kommentar_behauptet_es_nicht_mehr(self) -> None:
        """Der alte Satz - *"Sie stehen nicht im Journal ... und fehlten dem
        Analysten deshalb vollstaendig"* - ist seit der Buchung falsch. Ein
        Kommentar, der eine widerlegte Begruendung tragt, ist schlimmer als
        keiner: Er beantwortet die Frage, warum die Liste noch da ist, mit
        einem Grund, der nicht mehr gilt.
        """
        quelle = (WURZEL / "research" / "ausschluss.py").read_text(
            encoding="utf-8"
        )
        kopf = quelle.split("GESCHEITERTE_EIGENBAUTEN", 1)[0]

        assert "fehlten dem Analysten deshalb vollstaendig" not in kopf
        assert "Rueckfall" in kopf, "wofuer die Liste jetzt da ist, gehoert dazu"
