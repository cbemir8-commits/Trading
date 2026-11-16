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

Und es war eine Abschrift mehr - Befund 499
-------------------------------------------
Der Abgleich aus 498 ging ueber **Namen** und hat deshalb nur eine der
Abschriften erfasst. Gemessen stehen dieselben acht Messungen an **vier**
Stellen:

    state/trials.json                   das Verzeichnis, vom Buchungsweg
    ausschluss.GESCHEITERTE_EIGENBAUTEN acht Zeilen (in 498 nachgezogen)
    ausschluss.GEMESSENE_REGELN         22 Zeilen mit rho, Kurznamen
    auftragslage.KATALOGPUNKTE          22 Paare, identisch zur Projektion

In ``GEMESSENE_REGELN`` heissen sie "Enge breit" statt "Enge vor Bewegung
breit" - **ein Namensabgleich findet sie nicht**, und so standen dort die
alten vier Zahlen weiter. Die Trade-Zahl ist dagegen in beiden Tafeln
eindeutig und in jeder Zeile gleich; seit 499 laeuft der Abgleich darueber.

``KATALOGPUNKTE`` ist seit 499 **abgeleitet** statt abgeschrieben - vier
Stellen sind damit drei.

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
        # **Der Kommentarblock vor der Zuweisung**, nicht "alles bis zum
        # ersten Vorkommen des Namens": Der erste Entwurf teilte den Text so
        # und fiel, als Befund 499 einen Kommentar davor setzte, der den Namen
        # nennt. Eine Wache, die an der Reihenfolge im Text haengt, verliert
        # genau die Datei, die sich aendert.
        import ast

        quelle = (WURZEL / "research" / "ausschluss.py").read_text(
            encoding="utf-8"
        )
        zeilen = quelle.splitlines()
        baum = ast.parse(quelle)
        zuweisung = next(
            k
            for k in baum.body
            if isinstance(k, ast.AnnAssign)
            and isinstance(k.target, ast.Name)
            and k.target.id == "GESCHEITERTE_EIGENBAUTEN"
        )
        block: list[str] = []
        for nr in range(zuweisung.lineno - 2, -1, -1):
            if not zeilen[nr].startswith("#:"):
                break
            block.insert(0, zeilen[nr])
        kopf = "\n".join(block)

        assert kopf, "die Liste hat keinen Kommentarblock mehr"
        assert "fehlten dem Analysten deshalb vollstaendig" not in kopf
        assert "Rueckfall" in kopf, "wofuer die Liste jetzt da ist, gehoert dazu"


class TestAuchDieZweiteTafelStimmt:
    """**Der Befund, den 498 uebersehen hat.** Der Abgleich dort ging ueber
    Namen; hier geht er ueber die Trade-Zahl, und erst damit faellt die
    zweite Abschrift auf."""

    def _paare(self) -> list[tuple[str, int, float, float]]:
        from research.ausschluss import GEMESSENE_REGELN

        register = {e[1]: (e[0], e[2]) for e in aus_versuchsverzeichnis(VERZEICHNIS)}
        return [
            (name, trades, sharpe, register[trades][1])
            for name, trades, sharpe, _rho in GEMESSENE_REGELN
            if trades in register
        ]

    def test_die_trade_zahl_taugt_als_schluessel(self) -> None:
        """**Erst die Eindeutigkeit, dann der Abgleich.** Gaebe es zwei Zeilen
        mit derselben Trade-Zahl, verglichen die Regeln darunter die falschen
        Paare - und zwar still."""
        from research.ausschluss import GEMESSENE_REGELN

        tafel = [e[1] for e in GEMESSENE_REGELN]
        register = [e[1] for e in aus_versuchsverzeichnis(VERZEICHNIS)]

        assert len(set(tafel)) == len(tafel), "Trade-Zahl in der Tafel doppelt"
        assert len(set(register)) == len(register), "im Verzeichnis doppelt"

    def test_es_ueberlappen_welche(self) -> None:
        """Nichtleere-Zusicherung (Befund 479): Ohne Ueberlappung prueften die
        Regeln darunter nichts - und genau so war es vor 499 gemeint."""
        assert len(self._paare()) >= 8, self._paare()

    def test_jede_ueberlappende_zahl_stimmt(self) -> None:
        schief = [
            f"{name} ({trades} Trades): Tafel {sharpe}, Verzeichnis {reg}"
            for name, trades, sharpe, reg in self._paare()
            if abs(sharpe - reg) > RUNDUNG
        ]

        assert schief == [], (
            "weicht vom Versuchsverzeichnis ab - die Messung steht dort, die "
            f"Tafel wird nachgezogen (Befund 498/499): {schief}"
        )


class TestDieVierteAbschriftIstAbgeleitet:
    """Eine Abschrift, die gerechnet wird, kann nicht abdriften."""

    def test_katalogpunkte_sind_die_projektion(self) -> None:
        from research.auftragslage import KATALOGPUNKTE
        from research.ausschluss import GEMESSENE_REGELN

        assert tuple(
            (trades, sharpe) for _n, trades, sharpe, _r in GEMESSENE_REGELN
        ) == KATALOGPUNKTE

    def test_und_stehen_nicht_mehr_als_zahlen_da(self) -> None:
        """Geprueft am Aufbau: Ein Literal-Tupel waere die Abschrift zurueck."""
        import ast

        baum = ast.parse(
            (WURZEL / "research" / "auftragslage.py").read_text(encoding="utf-8")
        )
        zuweisung = next(
            k
            for k in baum.body
            if isinstance(k, ast.AnnAssign)
            and isinstance(k.target, ast.Name)
            and k.target.id == "KATALOGPUNKTE"
        )

        assert not isinstance(zuweisung.value, ast.Tuple), (
            "KATALOGPUNKTE steht wieder als Zahlenliste da - dann driftet sie "
            "wieder ab (Befund 499)"
        )
        assert "GEMESSENE_REGELN" in ast.unparse(zuweisung)
