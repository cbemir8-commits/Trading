"""Der Auftrag rechnete in Tagen, die Felder zaehlen Balken - Befund 496.

Was Befund 432 gebaut hat, und wo es einen Schritt zu kurz war
--------------------------------------------------------------
``auftragstakt`` ist in Befund 432 entstanden, weil der Auftrag an die
Research-KI das richtige Ziel in einer Einheit nannte, die der Empfaenger
nicht einstellen kann. Sein eigener Satz:

    Hier wird daraus ein Takt in **Tagen** und eine Bruttobewegung in
    Prozent - dieselbe Einheit wie diese Felder.

Zwei der vier genannten Felder zaehlen aber **Kerzen**: ``cooldown_bars`` und
``max_hold_bars``. Im Compiler steht es unmissverstaendlich -
``ctx.index - position < self.genome.cooldown_bars`` vergleicht Balkenindizes.
Auf Tageskerzen ist ein Balken ein Tag, und die Aussage stimmt zufaellig.

Gemessen auf der anderen Kerzenlaenge
-------------------------------------
Ein Tag sind 96 Viertelstundenkerzen. Der Takt, den der Auftrag verlangt:

    161 Trades, Takt 20,5 Tage   ->     20 Balken auf 1d
                                 ->   1968 Balken auf 15m

Und ``cooldown_bars`` ist im Genom-Modell auf **200** begrenzt. Auf
Viertelstundenkerzen war die Anforderung also nicht nur in der falschen
Einheit, sondern im Schema **gar nicht ausdrueckbar** - und die Kerzenlaenge
stand nirgends im 14.961 Zeichen langen Auftrag. Der Empfaenger konnte die
Umrechnung nicht vornehmen, weil ihm die Zahl fehlte, mit der man rechnet.

Beide Befehle, die die KI fragen, nehmen ``-i`` **und** ``--ki``: ``wettbewerb``
und ``research``. Der Auftrag war aber in beiden Faellen derselbe.

Teuer ist das, weil jeder Vorschlag einen Versuch kostet und der Zaehler
nicht faellt: Ein Kandidat, der 96-mal zu dicht handelt, hebt die Huerde fuer
alle kuenftigen.

Was jetzt geprueft wird
-----------------------
Die **Wirkung**, nicht die Form (Lehre aus Befund 493): Der Abschnitt nennt
die Kerzenlaenge, nennt den Takt in Balken, und sagt es, wenn die Zahl nicht
in das Feld passt. Die Umrechnung kommt aus ``Interval.duration``; dass sie
mit ``datenstand.BALKEN_JE_TAG`` uebereinstimmt, steht als Zusicherung hier -
sonst waeren es zwei Wahrheiten (Befund 234/494).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from core.models import Interval
from research.auftragstakt import als_auftrag, balken_fuer_tage, rechne
from research.datenstand import BALKEN_JE_TAG

WURZEL = Path(__file__).resolve().parents[1]


def _reihe(n: int = 800) -> pd.DataFrame:
    """Eine Reihe, aus der ``rechne`` eine Streuung bekommt."""
    zeiten = pd.date_range("2018-01-01", periods=n, freq="1D", tz="UTC")
    kurs = pd.Series(range(n), dtype=float) * 10 + 1000
    return pd.DataFrame(
        {
            "open_time": zeiten,
            "open": kurs,
            "high": kurs * 1.02,
            "low": kurs * 0.98,
            "close": kurs,
            "volume": 1.0,
        }
    )


def _text(intervall: object) -> str:
    stufen = rechne(_reihe(), ziele=(146, 161, 185), versuche=203)
    return als_auftrag(stufen, ziel_trades=161, intervall=intervall)


class TestDieUmrechnungKommtAusDemEnum:
    @pytest.mark.parametrize("mitglied", list(Interval), ids=lambda m: m.name)
    def test_ein_takt_ergibt_auf_jeder_kerzenlaenge_balken(
        self, mitglied: Interval
    ) -> None:
        """**Eine Berichtigung aus dem Bauen.** Der erste Entwurf rechnete
        Balken **je Tag** und gab fuer Wochenkerzen 0 zurueck - eine Zahl, die
        luegt: Ein Takt von 20,5 Tagen sind dort drei Balken. Diese Regel hat
        es gemeldet."""
        if mitglied is Interval.MN1:
            pytest.skip(
                "das Monatsintervall hat keine feste Dauer - 'Interval.duration' "
                "wirft dafuer selbst, und das ist richtig so"
            )

        assert balken_fuer_tage(20.5, mitglied) >= 1

    def test_tageskerzen_sind_ein_balken_je_tag(self) -> None:
        assert balken_fuer_tage(1, "D") == 1

    def test_und_viertelstunden_sechsundneunzig(self) -> None:
        """**Die Zahl, aus der der Befund kommt.**"""
        assert balken_fuer_tage(1, "15") == 96

    def test_wochenkerzen_geben_keine_null(self) -> None:
        """Die Gegenprobe zur Berichtigung: Ein Balken ist hier laenger als
        ein Tag, und 20,5 Tage sind drei davon."""
        assert balken_fuer_tage(1, "W") == 0, "ein Tag ist weniger als ein Balken"
        assert balken_fuer_tage(20.5, "W") == 3

    def test_sie_stimmt_mit_der_gepflegten_zahl_ueberein(self) -> None:
        """``datenstand.BALKEN_JE_TAG`` haelt die 96 fuer die Feinreihe. Zwei
        Stellen, die dasselbe aufschreiben, waeren zwei Wahrheiten - also
        wird verglichen, statt die zweite zu pflegen (Befund 234)."""
        assert balken_fuer_tage(1, "15") == BALKEN_JE_TAG

    def test_jede_schreibweise_geht(self) -> None:
        """Die Lehre aus Befund 494: Wert, Etikett, Name und Objekt."""
        iv = Interval("15")

        assert {
            balken_fuer_tage(1, w) for w in (iv, iv.value, iv.label, iv.name)
        } == {96}

    def test_was_keine_kerzenlaenge_ist_wirft(self) -> None:
        """Keine Null und kein Vorgabewert: Ein Aufruf ohne Kerzenlaenge ist
        ein Fehler im Aufruf, und still waere er die Falle aus 496."""
        with pytest.raises(ValueError, match="keine Kerzenlaenge"):
            balken_fuer_tage(1, "Quartal")


class TestDerAbschnittNenntDieKerzenlaenge:
    def test_auf_tageskerzen(self) -> None:
        text = _text("D")

        assert "1d-Kerzen" in text
        assert "ein Tag sind 1 Balken" in text

    def test_auf_viertelstunden(self) -> None:
        text = _text("15")

        assert "15m-Kerzen" in text
        assert "ein Tag sind 96 Balken" in text

    def test_und_sagt_dass_die_felder_kerzen_zaehlen(self) -> None:
        """Der Satz, der in 432 gefehlt hat."""
        text = _text("D")

        assert "zaehlen **Kerzen, nicht Tage**" in text

    def test_die_kerzenlaenge_ist_pflicht(self) -> None:
        """Ein Vorgabewert war der Weg in diesen Fehler - 'D' ist die Vorgabe
        von '-i', und der Abschnitt nahm sie stillschweigend an."""
        stufen = rechne(_reihe(), ziele=(161,), versuche=203)

        with pytest.raises(TypeError):
            als_auftrag(stufen, ziel_trades=161)  # type: ignore[call-arg]


class TestDerTaktStehtInBalken:
    def test_auf_tageskerzen_sind_es_zwanzig(self) -> None:
        assert "**20 Balken**" in _text("D")

    def test_auf_viertelstunden_sind_es_neunzehnhundertachtundsechzig(self) -> None:
        """**Die Messung des Befundes.** Derselbe Takt, 96-mal so viele
        Balken - und der Auftrag sagte davon kein Wort."""
        assert "**1968 Balken**" in _text("15")

    def test_die_tafel_hat_eine_balkenspalte(self) -> None:
        text = _text("15")

        assert "Takt/Balken" in text
        assert "Takt/Tage" in text, "die Tage bleiben - sie sind die Messung"

    def test_und_die_spalten_passen_zueinander(self) -> None:
        """Gegenprobe: Die Balkenspalte kommt aus derselben Rechnung wie der
        Takt, nicht aus einer zweiten.

        **Verglichen wird gegen die Takt-Objekte, nicht gegen die angezeigte
        Tageszahl.** Der erste Entwurf rechnete die gedruckte, auf eine
        Stelle gerundete Zahl mal 96 und fand 1712 gegen 1709 - das
        Anzeigeformat, kein Fehler. Mein Pruefaufbau, nicht der Code.
        """
        stufen = rechne(_reihe(), ziele=(146, 161, 185), versuche=203)
        erwartet = {balken_fuer_tage(s.takt_tage, "15") for s in stufen}
        assert len(erwartet) == len(stufen), "die Stufen muessen sich trennen"

        gefunden = set()
        for zeile in _text("15").splitlines():
            felder = zeile.split()
            # Nur die Tafelzeilen: sechs Zahlen, nichts sonst. Der erste
            # Entwurf nahm jede Zeile, die mit einer Ziffer beginnt - und
            # griff damit in einen Prosasatz ("0.2911 mal so viel ...").
            if len(felder) != 6 or not all(
                f.replace(".", "", 1).isdigit() for f in felder
            ):
                continue
            gefunden.add(int(felder[2]))

        assert erwartet <= gefunden, (sorted(erwartet), sorted(gefunden))


class TestWennDerTaktNichtInDasFeldPasst:
    def test_auf_viertelstunden_sagt_er_es(self) -> None:
        """1968 Balken gegen eine Grenze von 200: Der Auftrag verlangte etwas,
        das das Schema nicht hergibt."""
        text = _text("15")

        assert "nicht in das Feld" in text
        assert "hoechstens 200" in text
        assert "1968 Balken" in text

    def test_und_auf_tageskerzen_schweigt_er(self) -> None:
        """Sonst stuende in jedem Auftrag eine Warnung, die nicht gilt."""
        assert "nicht in das Feld" not in _text("D")

    def test_die_grenze_kommt_aus_dem_modell(self) -> None:
        """Nicht hingeschrieben: Verschiebt jemand die Grenze im Genom, sagt
        der Auftrag die neue Zahl (Befund 234)."""
        from research.auftragstakt import _feldgrenze
        from strategy.genome import Genome

        assert _feldgrenze("cooldown_bars") == 200
        assert _feldgrenze("max_hold_bars") == 2000
        assert "cooldown_bars" in Genome.model_fields


class TestDieBefehleReichenSieDurch:
    """**Geprueft wird der Aufruf, nicht sein Wortlaut** (Befund 493): Dass
    die Kerzenlaenge ankommt, ist die Wirkung - dass irgendwo ein bestimmter
    Text steht, waere die Form."""

    def _aufrufe(self, name: str) -> list[ast.Call]:
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        return [
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Name)
            and k.func.id == name
        ]

    def test_der_analyst_wird_mit_kerzenlaenge_gefragt(self) -> None:
        aufrufe = self._aufrufe("_ask_the_analyst")
        knapp = [ast.unparse(k) for k in aufrufe if len(k.args) < 3]

        assert aufrufe, "niemand fragt die KI mehr - dann pruefe den Melder"
        assert knapp == [], (
            "fragt die Research-KI ohne Kerzenlaenge - dann steht der Auftrag "
            f"in Tagen und die Felder zaehlen Balken (Befund 496): {knapp}"
        )

    def test_und_der_takt_auch(self) -> None:
        aufrufe = self._aufrufe("_auftragstakt")
        knapp = [ast.unparse(k) for k in aufrufe if len(k.args) < 3]

        assert len(aufrufe) == 3, len(aufrufe)
        assert knapp == [], knapp

    def test_beide_befehle_nehmen_kerzenlaenge_und_ki(self) -> None:
        """Die Messung, die den Befund teuer macht: Es ist kein hypothetischer
        Aufruf - beide Befehle haben beide Schalter."""
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        befehle = {
            n.name: ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
        }

        for name in ("wettbewerb", "research"):
            quelle = befehle[name]
            assert "--intervall" in quelle, name
            assert "_ask_the_analyst" in quelle, name
