"""Welcher Befehl kostet einen Versuch? - Befund 120.

Woher die Frage kommt
---------------------
Aus Befund 104, dem teuersten Fehler dieses Projekts: Ein Rauchtest ueber alle
Befehle traf zwanzig, die **messen und dabei zaehlen**. Der Versuchszaehler
stand danach bei 198 statt 177, und die Huerde des Deflated-Sharpe-Gates ist
seither dauerhaft hoeher - fuer jeden kuenftigen Kandidaten.

Damals entstand ``TRADING_TROCKENLAUF``. Was nicht entstand, ist eine Antwort
auf die Frage, die den Fehler ausgeloest hat: **Welche Befehle kosten
eigentlich Versuche?** Sie steht in 34 von 63 Docstrings ("Kostet keinen
Versuch"), in 24 gar nicht, und nichts prueft die Angabe gegen das Verhalten.

Was hier geprueft wird - und was nicht
--------------------------------------
Geprueft wird die Richtung, die **schaden** kann: Ein Befehl, der in den
Zaehler schreibt, darf nicht behaupten, er koste nichts. Wer sich darauf
verlaesst, verbrennt Versuche - genau wie in Befund 104.

Die Gegenrichtung - ein Befehl, der schweigt, obwohl er kostenlos ist - ist
laestig und nicht gefaehrlich. Sie bleibt ungeprueft.

**Die statische Erkennung ist unvollstaendig, und das ist gemessen.** Sie
findet Aufrufe im Funktionskoerper des Befehls, nicht solche ueber
Hilfsfunktionen. Befund 104 spricht von zwanzig zaehlenden Befehlen; die
Textsuche findet fuenf.

Deshalb steht daneben eine **gemessene** Liste: Jeder in Frage kommende Befehl
einmal mit ``TRADING_TROCKENLAUF`` ausgefuehrt, und wer die Meldung
``zaehler.trockenlauf`` ausloeste, haette gezaehlt:

    adaptiv        1 Versuch
    korb           7 Versuche     <- von der Textsuche nicht gefunden
    machbarkeit    9 Versuche
    landschaft    11 Versuche
    ------------------------------
    zusammen      28 Versuche

Bei 32 verbleibenden im Suchbudget. Vier Befehle, einmal beilaeufig
ausgefuehrt, und das Budget waere fast leer - genau so ist Befund 104
entstanden.

``korb`` ist der Beleg dafuer, dass die Textsuche allein nicht genuegt.
"""

from __future__ import annotations

import inspect
import re

import pytest

#: Aufrufe, die den Zaehler fortschreiben. Alle laufen durch
#: ``research.versuche.speichern``.
SCHREIBT = re.compile(r"\bsave_trials\s*\(|\banhaengen\s*\(")

#: Die Zusage, auf die man sich verlaesst.
ZUSAGE = "ostet keinen Versuch"

#: **Gemessen, nicht gelesen.** Jeder Befehl einmal mit ``TRADING_TROCKENLAUF``
#: ausgefuehrt; wer die Meldung ``zaehler.trockenlauf`` ausloest, haette
#: gezaehlt. Die Zahl ist das ``waere=N`` aus der Meldung, gegen den Stand von
#: 198 gerechnet.
#:
#: ``korb`` steht hier und **nicht** in der statischen Suche - er schreibt den
#: Zaehler ueber eine Hilfsfunktion fort. Genau dafuer war die Messung noetig.
GEMESSEN_ZAEHLEND = {
    "adaptiv": 1,
    "korb": 7,
    "machbarkeit": 9,
    "landschaft": 11,
}

#: Befehle, die beim Messen abgebrochen sind - ueber sie ist nichts bekannt.
#: Sie stehen hier, damit die Luecke sichtbar bleibt statt als "zaehlt nicht"
#: durchzugehen.
UNGEMESSEN = ("verbund", "vorschlag", "review", "research", "wettbewerb")


def befehle():
    import cli

    for c in cli.app.registered_commands:
        name = c.name or c.callback.__name__
        try:
            quelle = inspect.getsource(c.callback)
        except OSError:  # pragma: no cover - nur bei fehlender Quelle
            continue
        yield name, quelle, c.callback.__doc__ or ""


class TestDieZusageStimmt:
    def test_kein_zaehlender_befehl_verspricht_kostenlosigkeit(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Genau diese Verwechslung hat in Befund 104 einundzwanzig Versuche
        gekostet. Ein falsches "kostet keinen Versuch" ist teurer als gar
        keine Angabe: Es laedt dazu ein, den Befehl beilaeufig auszufuehren.
        """
        luegen = [
            name
            for name, quelle, doc in befehle()
            if SCHREIBT.search(quelle) and ZUSAGE in doc
        ]
        assert luegen == [], (
            f"Diese Befehle schreiben in den Zaehler und behaupten, sie "
            f"kosteten nichts: {luegen}"
        )

    def test_die_zaehlenden_sind_bekannt(self) -> None:
        """Wer dazukommt, soll es merken.

        Die Liste ist keine Vorschrift, sondern ein Weckruf: Ein neuer
        zaehlender Befehl ist eine Entscheidung, und sie gehoert bewusst
        getroffen.
        """
        gefunden = sorted(
            name for name, quelle, _ in befehle() if SCHREIBT.search(quelle)
        )
        assert gefunden == [
            "adaptiv",
            "landschaft",
            "machbarkeit",
            "research",
            "wettbewerb",
        ], (
            "Die Menge der zaehlenden Befehle hat sich geaendert. Wenn das "
            "Absicht war, gehoert die Liste hier angepasst - und der Docstring "
            "des Befehls muss es sagen."
        )

    def test_jeder_zaehlende_befehl_sagt_etwas_dazu(self) -> None:
        """Schweigen ist bei einem zaehlenden Befehl keine Option."""
        stumm = [
            name
            for name, quelle, doc in befehle()
            if SCHREIBT.search(quelle)
            and "Versuch" not in doc
            and "Zaehler" not in doc
        ]
        assert stumm == [], (
            f"Diese Befehle kosten Versuche und erwaehnen es nicht: {stumm}"
        )


class TestDieUnvollstaendigkeitStehtFest:
    def test_die_statische_suche_findet_weniger_als_befund_104(self) -> None:
        """Der Beweis, dass es indirekte Wege gibt - und die Begruendung
        dafuer, dass hier keine Vollstaendigkeit behauptet wird.

        Faende diese Suche eines Tages zwanzig, waere die Annahme hinfaellig
        und der Modul-Docstring falsch. Dann soll dieser Test anschlagen.
        """
        gefunden = sum(1 for _, quelle, _ in befehle() if SCHREIBT.search(quelle))
        assert gefunden < 20, (
            f"Die statische Suche findet jetzt {gefunden} zaehlende Befehle. "
            "Befund 104 sprach von zwanzig - wenn die Suche sie inzwischen "
            "alle findet, gehoert der Modul-Docstring korrigiert."
        )


class TestDerTrockenlaufIstDieAntwort:
    def test_er_deckt_den_zaehler_ab(self) -> None:
        """Weil die statische Suche unvollstaendig ist, ist der Trockenlauf
        die einzige verlaessliche Auskunft: Er sitzt an der einen Stelle, durch
        die jeder Schreibvorgang laeuft."""
        from research import versuche

        quelle = inspect.getsource(versuche.speichern)
        assert "trockenlauf()" in quelle

    def test_und_meldet_was_er_verhindert_hat(self) -> None:
        """``waere=N`` ist die Zahl, die den Schaden beziffert - ohne sie
        wuesste niemand, was der Lauf gekostet haette."""
        from research import versuche

        quelle = inspect.getsource(versuche.speichern)
        assert "waere" in quelle

    @pytest.mark.parametrize(
        "modul,funktion",
        [
            ("research.versuche", "speichern"),
            ("research.leaderboard", "Leaderboard.save"),
            ("core.report", "write_report"),
            ("core.report", "publish"),
            ("research.admission", "write_champion"),
        ],
    )
    def test_alle_fuenf_schreibstellen_fragen_ihn(
        self, modul: str, funktion: str
    ) -> None:
        """Die Bilanz aus den Befunden 116 und 117, als Test.

        Erst hielt der Trockenlauf nur den Zaehler an, dann drei Stellen, dann
        vier - die vierte committet und pusht, und sie fiel nur auf, weil ein
        fremder Commit im Verlauf stand.
        """
        import importlib

        gegenstand = importlib.import_module(modul)
        for teil in funktion.split("."):
            gegenstand = getattr(gegenstand, teil)
        assert "trockenlauf()" in inspect.getsource(gegenstand)


class TestDieGemesseneListe:
    """Was der Trockenlauf gemeldet hat - Befund 120.

    Die statische Suche fand fuenf zaehlende Befehle, die Messung sechs. Der
    Unterschied heisst ``korb``: Er schreibt den Zaehler ueber eine
    Hilfsfunktion fort, und keine Textsuche im Funktionskoerper findet das.

    Deshalb ist **diese** Liste die verlaessliche, und die statische nur ein
    Sicherheitsnetz gegen offensichtliche Widersprueche.
    """

    def test_jeder_gemessen_zaehlende_sagt_es_im_docstring(self) -> None:
        """Der Test, der ``korb`` gefunden hat."""
        nach_name = {name: doc for name, _, doc in befehle()}
        stumm = [
            name
            for name in GEMESSEN_ZAEHLEND
            if name in nach_name and "Versuch" not in nach_name[name]
        ]
        assert stumm == [], (
            f"Diese Befehle kosten gemessen Versuche und sagen es nicht: "
            f"{stumm}"
        )

    def test_keiner_von_ihnen_verspricht_kostenlosigkeit(self) -> None:
        nach_name = {name: doc for name, _, doc in befehle()}
        luegen = [
            name
            for name in GEMESSEN_ZAEHLEND
            if name in nach_name and ZUSAGE in nach_name[name]
        ]
        assert luegen == []

    def test_korb_fehlt_der_statischen_suche(self) -> None:
        """Der Beweis, dass die Textsuche nicht genuegt.

        Sollte sie ``korb`` eines Tages finden, waere die Begruendung fuer die
        gemessene Liste hinfaellig - dann schlaegt dieser Test an und der
        Modul-Docstring gehoert korrigiert.
        """
        statisch = {name for name, quelle, _ in befehle() if SCHREIBT.search(quelle)}
        assert "korb" not in statisch
        assert "korb" in GEMESSEN_ZAEHLEND

    def test_die_summe_uebersteigt_das_restbudget(self) -> None:
        """Die Zahl, die den Befund traegt.

        Vier Befehle, einmal beilaeufig ausgefuehrt, haetten 28 der 32
        verbleibenden Versuche gekostet - und die Huerde des
        Deflated-Sharpe-Gates dauerhaft gehoben. Genau so ist Befund 104
        entstanden.
        """
        assert sum(GEMESSEN_ZAEHLEND.values()) == 28

    def test_die_ungemessenen_stehen_als_luecke_da(self) -> None:
        """Ein abgebrochener Lauf ist kein "zaehlt nicht"."""
        assert set(UNGEMESSEN) & set(GEMESSEN_ZAEHLEND) == set()
        nach_name = {name for name, _, _ in befehle()}
        assert set(UNGEMESSEN) <= nach_name
