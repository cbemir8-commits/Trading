"""Die Statuszeile nannte zwei offene Gates, nicht ihr Gewicht - Befund 421.

Der Bericht sagt "9 von 11, offen: Messlatte, Deflated Sharpe". Wer das liest,
haelt zwei Gates fuer den Engpass. Gemessen (Befund 420) faellt der Deflated
Sharpe in **allen elf** Aufteilungen, die Messlatte in **einer** - der
gemeldeten -, und 'Schlechtestes Jahr', das hier **besteht**, in fuenf.

Die ausfuehrliche Behandlung dieses Gates aus Befund 160/161 haengt daran, dass
es offen ist. Am massgeblichen Punkt besteht es, und der Leser bekam nichts.
"""

from __future__ import annotations

from research.betriebspunkt import Betriebspunkt
from research.stand import Lage


def _punkt(**kwargs) -> Betriebspunkt:
    grund = {
        "name": "Spot",
        "trades": 156,
        "cagr_pct": 14.3391,
        "rueckgang_pct": 9.869,
        "guete": 0.2708,
        "dsr": 0.5826,
        "bestanden": 9,
        "gesamt": 11,
        "offen": ("Messlatte", "Deflated Sharpe"),
    }
    return Betriebspunkt(**{**grund, **kwargs})


def _bericht(**kwargs) -> str:
    grund = {
        "kandidat": "Trend 50 Tage mit Konfluenz",
        "maerkte": "BTC + ETH, 1d",
        "trades": 156,
        "sharpe_je_trade": 0.2708,
        "noetiger_sharpe": 0.3374,
        "bestanden": 9,
        "gesamt": 11,
        "offen": ("Messlatte", "Deflated Sharpe"),
        "versuche": 203,
    }
    return Lage(**{**grund, **kwargs}).bericht(kurz=True)


class TestDerBlockStehtNebenDemPunkt:
    def test_er_erscheint_unter_auch_gemessen(self) -> None:
        zeilen = _bericht(zweitpunkt=_punkt()).splitlines()

        wo = next(i for i, z in enumerate(zeilen) if "Auch gemessen" in z)

        assert "Wie belastbar" in zeilen[wo + 1]

    def test_er_nennt_die_zahl_der_aufteilungen(self) -> None:
        from research.aufteilung import VERSATZ

        bericht = _bericht(zweitpunkt=_punkt())

        assert f"ueber {len(VERSATZ)} Aufteilungen" in bericht

    def test_und_jedes_der_drei_gates(self) -> None:
        bericht = _bericht(zweitpunkt=_punkt())

        assert "Deflated Sharpe      faellt in 11 von 11" in bericht
        assert "Schlechtestes Jahr   faellt in  5 von 11" in bericht
        assert "Messlatte            faellt in  1 von 11" in bericht

    def test_nach_belastbarkeit_geordnet(self) -> None:
        # Gefiltert wird auf die Einrueckung des Blocks, nicht auf "faellt
        # in": Der Entscheidungstext aus Befund 415 enthaelt denselben
        # Wortlaut ("faellt in allen vier"), und mein erster Filter hat ihn
        # mitgezaehlt.
        zeilen = [
            z for z in _bericht(zweitpunkt=_punkt()).splitlines()
            if z.startswith("                   ") and " faellt in " in z
        ]

        assert len(zeilen) == 3
        assert "Deflated Sharpe" in zeilen[0]
        assert "Schlechtestes Jahr" in zeilen[1]
        assert "Messlatte" in zeilen[2]


class TestErSagtWelchesGateHierBesteht:
    def test_die_offenen_sind_als_offen_markiert(self) -> None:
        bericht = _bericht(zweitpunkt=_punkt())
        zeilen = {
            z.split("faellt in")[0].strip(): z
            for z in bericht.splitlines()
            if "faellt in" in z
        }

        assert "(offen)" in zeilen["Deflated Sharpe"]
        assert "(offen)" in zeilen["Messlatte"]

    def test_und_das_bestandene_als_bestehend(self) -> None:
        bericht = _bericht(zweitpunkt=_punkt())
        zeile = next(
            z for z in bericht.splitlines()
            if "Schlechtestes Jahr" in z and "faellt in" in z
        )

        assert "(besteht hier)" in zeile

    def test_der_satz_dazu_steht_darunter(self) -> None:
        """Das ist der Punkt des Befundes, und er gehoert ausgeschrieben."""
        bericht = _bericht(zweitpunkt=_punkt())

        assert "Ein bestandenes Gate faellt oefter als ein offenes." in bericht


class TestKeinFreibriefFuerDieMesslatte:
    def test_der_bericht_nennt_die_regel_aus_400(self) -> None:
        bericht = _bericht(zweitpunkt=_punkt())

        assert "Kein Versatz ist der richtige" in bericht

    def test_und_verweist_auf_die_nachmessung(self) -> None:
        bericht = _bericht(zweitpunkt=_punkt())

        assert "'cli aufteilung' misst es nach" in bericht

    def test_der_kopf_sagt_dass_es_kein_freibrief_ist(self) -> None:
        text = Lage._belastbarkeit.__doc__ or ""

        assert "kein Freibrief" in text
        assert "schliesst Befund 400 aus" in text


class TestDieZahlenGehoerenZuDiesemPunkt:
    """Eine gepflegte Zahl am falschen Ort ist die Lehre aus Befund 408."""

    def test_ein_punkt_mit_anderen_offenen_gates_bekommt_nichts(self) -> None:
        anders = _punkt(offen=("Drawdown", "Monte-Carlo"))

        assert "Wie belastbar" not in _bericht(zweitpunkt=anders)

    def test_ein_punkt_ohne_offene_gates_auch_nicht(self) -> None:
        zu = _punkt(offen=(), bestanden=11)

        assert "Wie belastbar" not in _bericht(zweitpunkt=zu)

    def test_ohne_zweitpunkt_steht_nichts(self) -> None:
        assert "Wie belastbar" not in _bericht()

    def test_die_pruefung_kommt_aus_den_gemessenen_daten(self) -> None:
        """Nicht eine zweite Liste der offenen Gates - die Bedingung wird
        aus 'AUSFALL_JE_AUFTEILUNG' gerechnet."""
        import inspect

        quelle = inspect.getsource(Lage._belastbarkeit)

        assert "AUSFALL_JE_AUFTEILUNG" in quelle
        assert "if 0 in wo" in quelle


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_luecke(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 421)

        assert "haengt daran, dass das Gate offen ist" in eintrag.ergebnis
        assert "bekam der Leser nichts" in eintrag.ergebnis

    def test_und_die_ordnung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 421)

        assert "11 von 11" in eintrag.ergebnis
        assert "1 von 11" in eintrag.ergebnis

    def test_und_420_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 420).zuletzt == 421
