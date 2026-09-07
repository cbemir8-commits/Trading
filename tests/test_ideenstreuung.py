"""Die zweite Schaetzung der Ideenstreuung - aus Ziehungen statt aus einem Wert.

**Befund 237.** ``wettrennen.py`` nannte als Grenze seines Modells: *"Es
kalibriert an einem Punkt. Mehr gibt es nicht."* Im Versuchsverzeichnis liegen
acht Regeln, die gegen die Spezifikation gebaut wurden (Befunde 77 und 83),
jede mit Trade-Zahl und Guete. Beide Laeufe haben gemessen, was sie
vorgeschlagen hatten - es ist also nicht gesiebt worden.

Was diese Tests halten
----------------------
Nicht die Zahl - sie darf sich bewegen, sobald neue Regeln dazukommen.
Sondern:

* dass das Schaetzrauschen abgezogen wird (ohne diesen Schritt waere die Zahl
  systematisch zu gross, am staerksten bei den seltensten Regeln),
* dass ``verbund`` draussen bleibt (Nachbarschaft, keine neue Idee),
* dass die Unsicherheit mitgerechnet wird - Befund 236 steht direkt davor.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from research.ideenstreuung import GEBAUT, Schaetzung, Ziehung, schaetzen, ziehungen

ZAEHLER = Path("state/trials.json")


class TestEineZiehung:
    def test_der_standardfehler_faellt_mit_der_trade_zahl(self) -> None:
        wenig = Ziehung("selten", 0.34, 18)
        viel = Ziehung("haeufig", 0.34, 406)

        assert wenig.standardfehler > viel.standardfehler

    def test_bei_achtzehn_trades_ist_er_groesser_als_die_gesuchte_groesse(self) -> None:
        """**Warum der Abzug noetig ist.**

        'Enge vor Bewegung' aus Befund 77 hat 18 Trades und die beste Guete
        aller acht. Ihr Standardfehler allein ist groesser als die
        Nullstreuung, gegen die hier verglichen wird.
        """
        from research.wettrennen import nullstreuung

        assert Ziehung("Enge vor Bewegung", 0.3405, 18).standardfehler > nullstreuung(
            115
        )

    def test_ohne_trades_ist_nichts_bekannt(self) -> None:
        assert Ziehung("leer", 0.2, 1).standardfehler == float("inf")


class TestDieSchaetzung:
    @staticmethod
    def _aus(werte: list[tuple[float, int]]) -> Schaetzung:
        return Schaetzung(
            ziehungen=tuple(Ziehung(f"r{i}", g, n) for i, (g, n) in enumerate(werte))
        )

    def test_das_rauschen_wird_abgezogen(self) -> None:
        s = self._aus([(0.30, 40), (0.10, 40), (-0.10, 40), (-0.20, 40)])

        assert s.echt is not None
        assert s.echt < s.beobachtet

    def test_reines_rauschen_laesst_nichts_uebrig(self) -> None:
        """Streuen die Werte nur so weit, wie ihre Schaetzfehler hergeben,
        gibt es keine Ideenstreuung zu melden - und dann steht dort ``None``
        und keine Wurzel aus einer negativen Zahl."""
        s = self._aus([(0.02, 5), (-0.02, 5), (0.01, 5), (-0.01, 5)])

        assert s.echt is None

    def test_die_unsicherheit_faellt_mit_der_zahl_der_ziehungen(self) -> None:
        wenige = self._aus([(0.3, 50), (0.0, 50), (-0.3, 50)])
        viele = self._aus([(0.3, 50), (0.0, 50), (-0.3, 50)] * 4)

        assert wenige.unsicherheit > viele.unsicherheit
        assert viele.unsicherheit > 0

    def test_acht_ziehungen_bleiben_grob(self) -> None:
        """27 % - das ist ein Anhaltspunkt und keine Messung."""
        s = self._aus([(0.1, 100)] * 8)

        assert s.unsicherheit == pytest.approx(1 / math.sqrt(14), rel=1e-9)


class TestWasImVerzeichnisSteht:
    def test_gelesen_werden_nur_die_gebauten(self) -> None:
        """``verbund`` ist Nachbarschaft des Bestands, keine neue Idee."""
        herkuenfte = {
            v["herkunft"] for v in json.loads(ZAEHLER.read_text())["versuche"]
        }
        assert "verbund" in herkuenfte
        assert "verbund" not in GEBAUT

        kennungen = {z.kennung for z in ziehungen(ZAEHLER)}

        assert not any(k.startswith("Verbund ") for k in kennungen)

    def test_es_sind_die_acht_aus_den_befunden_77_und_83(self) -> None:
        assert len(ziehungen(ZAEHLER)) == 8

    def test_die_schaetzung_kommt_zustande(self) -> None:
        s = schaetzen(ZAEHLER)

        assert s is not None
        assert s.echt is not None

    def test_sie_liegt_ueber_der_rueckrechnung_aus_dem_verlauf(self) -> None:
        """**Der Befund in einer Zeile** - mit aller Vorsicht.

        Die Rueckrechnung aus dem Bestwert liefert 0,0918, diese Ziehungen
        deutlich mehr. Das entscheidet nichts: acht Ziehungen, davon drei
        Wiederholungen derselben Ideen, gemessen auf rohen Trades und von
        keinem Sprachmodell vorgeschlagen. Es heisst nur, dass es eine zweite
        Zahl gibt und dass sie nicht kleiner ist.
        """
        from research.referenz import PERPETUALPUNKT, SCHUB, SPOTPUNKT
        from research.wettrennen import Rennen

        rennen = Rennen(
            bester=PERPETUALPUNKT.guete,
            versuche=SPOTPUNKT.versuche,
            trades=SPOTPUNKT.effektiv,
            schub=SCHUB,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )
        s = schaetzen(ZAEHLER)

        assert s is not None and s.echt is not None and rennen.streuung is not None
        assert s.echt > rennen.streuung

    def test_eine_fehlende_datei_gibt_nichts_zurueck(self, tmp_path: Path) -> None:
        leer = tmp_path / "leer.json"
        leer.write_text(json.dumps({"versuche": []}))

        assert schaetzen(leer) is None


class TestZweiPopulationen:
    """**Befund 238 - die Einschraenkung an Befund 237.**

    Zwei Zahlen fuer dieselbe Groesse laden dazu ein, die eine in die Rechnung
    der anderen zu setzen. Hier faellt auf, dass das nicht geht.
    """

    @staticmethod
    def _schaetzung() -> Schaetzung:
        s = schaetzen(ZAEHLER)
        assert s is not None
        return s

    def test_sie_erklaert_den_projektverlauf_nicht(self) -> None:
        """Haette die Suche so gezogen, stuende der Bestwert bei rund 0,49."""
        from research.ideenstreuung import vergleiche
        from research.referenz import PERPETUALPUNKT, SPOTPUNKT

        v = vergleiche(
            self._schaetzung(),
            bester=PERPETUALPUNKT.guete,
            versuche=SPOTPUNKT.versuche,
        )

        assert not v.passt
        assert v.abweichung > 0.2

    def test_sie_verfehlt_ihn_deutlicher_als_der_verworfene_ansatz(self) -> None:
        """Der Modulkopf von ``wettrennen`` verwirft die Bestenlisten-Schaetzung
        mit 0,444 gegen 0,257. Diese hier liegt noch weiter daneben - ein Grund
        mehr, sie nicht einzusetzen."""
        from research.ideenstreuung import vergleiche
        from research.referenz import PERPETUALPUNKT, SPOTPUNKT
        from research.wettrennen import extremwert

        eigen = vergleiche(
            self._schaetzung(),
            bester=PERPETUALPUNKT.guete,
            versuche=SPOTPUNKT.versuche,
        )
        bestenliste = 0.1685 + 0.1019 * extremwert(SPOTPUNKT.versuche)

        assert eigen.erwartet > bestenliste

    def test_auf_die_eigenen_ziehungen_angewandt_passt_sie(self) -> None:
        """Das ist der Beleg fuer 'zwei Populationen' statt 'zu hoch geschaetzt'.

        Verglichen wird gegen den besten mit brauchbarer Trade-Zahl: Der
        Rohbeste hat 18 Trades, und sein Standardfehler ist groesser als der
        ganze Abstand, um den es hier geht.
        """
        from research.ideenstreuung import vergleiche

        z = ziehungen(ZAEHLER)
        bester = max(x.guete for x in z if x.trades >= 50)

        assert vergleiche(self._schaetzung(), bester=bester, versuche=len(z)).passt

    def test_der_beste_gebaute_bleibt_unter_dem_bestand(self) -> None:
        """**Breiter ziehen ist nicht besser finden.**

        Ohne diesen Satz liest sich Befund 237 als Empfehlung. Alle acht sind
        gescheitert, und der beste mit brauchbarer Trade-Zahl liegt unter dem,
        was der Bestand ohnehin liefert.
        """
        from research.referenz import PERPETUALPUNKT

        z = ziehungen(ZAEHLER)
        bester = max(x.guete for x in z if x.trades >= 50)

        assert bester < PERPETUALPUNKT.guete

    def test_der_modulkopf_sagt_es_dazu(self) -> None:
        import research.ideenstreuung as modul

        kopf = modul.__doc__ or ""

        assert "zwei populationen" in kopf.lower()
        assert "erklaert_den_verlauf" in kopf


def test_der_modulkopf_von_wettrennen_behauptet_es_nicht_mehr() -> None:
    """"Mehr gibt es nicht" war die Aussage, die Befund 237 widerlegt hat.

    Ein Modulkopf wird als Stand gelesen - so steht es in ``referenz.py``.
    """
    kopf = Path("research/wettrennen.py").read_text()

    assert "Mehr gibt es nicht:" not in kopf
    assert "ideenstreuung" in kopf


def test_worueber_die_zahl_nichts_sagt_steht_dabei() -> None:
    """Befund 77: die vier Regeln hat kein Sprachmodell vorgeschlagen.

    Ohne diesen Satz liest sich die Zahl als Beleg fuer 'cli wettbewerb --ki',
    und das waere sie nicht.
    """
    import research.ideenstreuung as modul

    kopf = modul.__doc__ or ""

    assert "kein Sprachmodell verdrahtet" in kopf
    assert "Keine taugte" in kopf
