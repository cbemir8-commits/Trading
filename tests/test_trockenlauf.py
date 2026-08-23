"""Ein Test, der die Huerde des haertesten Gates anhebt.

Der Anlass ist ein Fehler von mir. Um Fehler wie den aus Befund 103 zu finden
- ein Befehl, der mit seinen eigenen Voreinstellungen abbricht -, lief ein
Rauchtest ueber alle 61 Befehle. Zwanzig davon **messen und zaehlen dabei**.
Der Versuchszaehler stand danach bei 198 statt 177.

Das ist keine Kleinigkeit: Jeder Versuch hebt die Huerde des Deflated Sharpe
um rund 0,0002 Punkte, dauerhaft und fuer jeden kuenftigen Kandidaten. Ein
Test hat sie um 0,004 angehoben, ohne eine einzige Hypothese zu pruefen.

Vier Saeulen tragen diese Datei:

``test_der_trockenlauf_haelt_den_zaehler_an`` - Der Kern. Mit gesetzter
Variable schreibt ``speichern`` nicht, und zwar an der einen Stelle, durch die
jeder Schreibvorgang laeuft.

``test_ohne_variable_zaehlt_alles_wie_bisher`` - Die Gegenprobe. Ein Schalter,
der auch ohne Zutun wirkt, waere schlimmer als kein Schalter.

``test_ein_vergessener_trockenlauf_faellt_auf`` - Die Wache gegen die
Nebenwirkung. Ein zu niedriger Zaehler macht den Deflated Sharpe milder -
genau die Richtung, gegen die ``versuche.py`` gebaut ist.

``TestDerTrockenlaufHinterlaesstNichts`` - Der erweiterte Vertrag aus Befund
116. Der Schutz galt nur dem Zaehler; ein Rauchtest von ``cli wettbewerb``
schrieb die Bestenliste trotzdem fort. Jetzt gilt, was der Name sagt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.versuche import (
    TROCKENLAUF,
    Versuch,
    anhaengen,
    laden,
    speichern,
    trockenlauf,
)


@pytest.fixture
def zaehlerdatei(tmp_path: Path) -> Path:
    pfad = tmp_path / "trials.json"
    pfad.write_text(
        json.dumps(
            {"format": 2, "trials": 177, "grundstock": 177, "versuche": []}
        )
    )
    return pfad


class TestTrockenlauf:
    def test_der_trockenlauf_haelt_den_zaehler_an(
        self, zaehlerdatei: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**Der Test, der diese Datei traegt.**

        Gesichert wird ``speichern`` und nicht jeder Aufrufer: Es ist die
        eine Stelle, durch die sowohl ``save_trials`` als auch ``anhaengen``
        laufen. Jeden Aufrufer einzeln abzusichern hiesse, den naechsten zu
        vergessen.
        """
        monkeypatch.setenv(TROCKENLAUF, "1")
        verzeichnis = laden(zaehlerdatei)
        verzeichnis.grundstock = 999

        speichern(zaehlerdatei, verzeichnis)

        assert laden(zaehlerdatei).anzahl == 177, "die Datei bleibt, wie sie war"

    def test_auch_einzelnachweise_werden_nicht_geschrieben(
        self, zaehlerdatei: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``anhaengen`` geht durch dieselbe Stelle - sonst waere die Sperre
        auf halbem Weg zu Ende."""
        monkeypatch.setenv(TROCKENLAUF, "ja")

        anhaengen(
            zaehlerdatei,
            [Versuch(kennung="Testregel", trades=10, sharpe_je_trade=0.2)],
        )

        assert laden(zaehlerdatei).eintraege == []
        assert laden(zaehlerdatei).anzahl == 177

    def test_ohne_variable_zaehlt_alles_wie_bisher(
        self, zaehlerdatei: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**Die Gegenprobe.** Ein Schalter, der auch ohne Zutun wirkt, waere
        schlimmer als kein Schalter."""
        monkeypatch.delenv(TROCKENLAUF, raising=False)

        anhaengen(
            zaehlerdatei,
            [Versuch(kennung="Testregel", trades=10, sharpe_je_trade=0.2)],
        )

        assert laden(zaehlerdatei).anzahl == 178
        assert len(laden(zaehlerdatei).eintraege) == 1

    @pytest.mark.parametrize("wert", ["", "0", "nein", "false", "aus"])
    def test_diese_werte_gelten_als_aus(
        self, wert: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ein ``TRADING_TROCKENLAUF=0`` darf nicht als "an" gelten - das
        waere die gefaehrliche Richtung."""
        monkeypatch.setenv(TROCKENLAUF, wert)

        assert not trockenlauf()

    @pytest.mark.parametrize("wert", ["1", "ja", "true", "JA", " 1 "])
    def test_diese_werte_gelten_als_an(
        self, wert: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(TROCKENLAUF, wert)

        assert trockenlauf()

    def test_ohne_variable_ist_er_aus(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(TROCKENLAUF, raising=False)

        assert not trockenlauf()


class TestWache:
    def test_ein_vergessener_trockenlauf_faellt_auf(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**Die Wache gegen die Nebenwirkung.**

        Bleibt die Variable stehen, zaehlt eine echte Suche nicht mit - und
        ein zu niedriger Zaehler macht den Deflated Sharpe milder. Genau die
        Richtung, gegen die ``versuche.py`` gebaut ist. Deshalb nennt
        ``cli stand`` sie, solange sie steht.

        Geprueft wird die Reihenfolge, nicht ein Zeichenfenster: Bis Befund
        112 stand hier ``stelle[:4000]``, und das ist beim Einbau eines
        Imports gerissen, ohne dass sich an der Warnung etwas geaendert
        haette. Ein Test, der bei jeder Umstellung anschlaegt, misst die
        Umstellung und nicht die Anforderung - und die lautet: **vor der
        ersten Ausgabe.**
        """
        import cli

        quelle = Path(cli.__file__).read_text()
        stelle = quelle[quelle.index("def stand("):]

        assert "trockenlauf()" in stelle
        assert "ACHTUNG" in stelle
        assert stelle.index("ACHTUNG") < stelle.index("lage.bericht()"), (
            "Die Trockenlauf-Warnung steht nach dem Bericht - wer nur den "
            "Stand liest, sieht sie dann womoeglich nicht."
        )

    def test_der_unterdrueckte_schreibvorgang_wird_protokolliert(self) -> None:
        """Ein stiller Trockenlauf waere schlimmer als das Problem, das er
        loest - deshalb Fehlerstufe und nicht Hinweis."""
        import inspect

        from research import versuche

        quelle = inspect.getsource(versuche.speichern)

        assert "log.error" in quelle
        assert "zaehler.trockenlauf" in quelle

    def test_der_zaehler_faellt_auch_im_trockenlauf_nicht(
        self, zaehlerdatei: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die aeltere Regel bleibt unberuehrt: Der Stand faellt nie. Der
        Trockenlauf haelt ihn an, er dreht ihn nicht zurueck."""
        from research.admission import save_trials

        monkeypatch.setenv(TROCKENLAUF, "1")
        save_trials(zaehlerdatei, 50)

        assert laden(zaehlerdatei).anzahl == 177


class TestDerTrockenlaufHinterlaesstNichts:
    """Der Vertrag war zu eng - Befund 116.

    ``trockenlauf()`` hiess *"Laeuft gerade etwas, das nicht zaehlen darf?"*,
    und genau so weit reichte der Schutz. Mit gesetzter Variable habe ich
    ``cli wettbewerb`` als Rauchtest laufen lassen: Der Zaehler blieb bei 198,
    wie zugesagt - die Bestenliste ging von 11 auf 12 Laeufe, neun Eintraege
    bekamen ein neues Datum, und ein Zulassungsbericht wurde abgelegt.

    Der Name verspricht mehr als der alte Vertrag hielt, und der Name ist,
    was man beim Benutzen sieht. Diese Tests halten den erweiterten Vertrag
    fest: **Wer die Variable setzt, hinterlaesst nichts.**
    """

    def test_die_bestenliste_wird_nicht_fortgeschrieben(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from research.leaderboard import Leaderboard

        ziel = tmp_path / "leaderboard.json"
        monkeypatch.setenv(TROCKENLAUF, "1")
        tafel = Leaderboard(path=ziel)
        tafel.laeufe = 7
        tafel.save()

        assert not ziel.exists(), "Trockenlauf hat die Bestenliste geschrieben"

    def test_ohne_variable_wird_sie_geschrieben(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Die Gegenprobe - ein Schalter, der immer wirkt, ist keiner."""
        from research.leaderboard import Leaderboard

        ziel = tmp_path / "leaderboard.json"
        monkeypatch.delenv(TROCKENLAUF, raising=False)
        tafel = Leaderboard(path=ziel)
        tafel.laeufe = 7
        tafel.save()

        assert ziel.exists()
        assert json.loads(ziel.read_text())["laeufe"] == 7

    def test_kein_bericht_wird_abgelegt(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Ein Rauchtest sieht im Verlauf aus wie ein Lauf und ist keiner."""
        from core.report import write_report

        monkeypatch.setenv(TROCKENLAUF, "1")
        write_report({"was": "auch immer"}, root=tmp_path)

        ordner = tmp_path / "reports" / "zulassung"
        assert not ordner.exists() or not list(ordner.glob("*.json"))

    def test_ohne_variable_wird_er_abgelegt(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from core.report import write_report

        monkeypatch.delenv(TROCKENLAUF, raising=False)
        datei = write_report({"was": "auch immer"}, root=tmp_path)

        assert datei.exists()
        assert json.loads(datei.read_text())["was"] == "auch immer"

    def test_der_champion_wird_nicht_geschrieben(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Von allen Dateien die teuerste - hier haengt das Geld dran."""
        from research.admission import write_champion
        from research.seeds import spitzenkandidat

        class Schein:
            genome = spitzenkandidat()

        ziel = tmp_path / "champion.json"
        monkeypatch.setenv(TROCKENLAUF, "1")
        write_champion(Schein(), ziel)

        assert not ziel.exists(), "Trockenlauf hat den Champion ueberschrieben"

    def test_ein_bestehender_champion_bleibt_unberuehrt(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Der gefaehrlichere Fall: nicht anlegen, sondern ueberschreiben."""
        from research.admission import write_champion
        from research.seeds import spitzenkandidat

        class Schein:
            genome = spitzenkandidat()

        ziel = tmp_path / "champion.json"
        ziel.write_text('{"genom": {"name": "der echte"}}')
        monkeypatch.setenv(TROCKENLAUF, "1")
        write_champion(Schein(), ziel)

        assert json.loads(ziel.read_text())["genom"]["name"] == "der echte"

    def test_der_docstring_nennt_den_erweiterten_vertrag(self) -> None:
        """Sonst steht die Lehre wieder nur im Befund - siehe Befund 115."""
        text = trockenlauf.__doc__ or ""
        assert "hinterlassen" in text.lower()
        assert "Bestenliste" in text

    def test_es_wird_nicht_committet_und_nicht_gesendet(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """**Die Stelle, die Befund 116 uebersehen hat.**

        ``publish`` committet **und pusht**. Ein Rauchtest landet damit in der
        Projekthistorie, wo er wie ein Lauf aussieht - genau so ist ``54770ec``
        entstanden. Befund 116 hat sie uebersehen, weil ``git status`` danach
        sauber war: sauber, weil der Befehl selbst schon committet hatte.
        """
        from core.report import publish

        monkeypatch.setenv(TROCKENLAUF, "1")
        datei = tmp_path / "bericht.json"
        datei.write_text("{}")

        ergebnis = publish([datei], root=tmp_path, message="darf nicht passieren")

        assert ergebnis.status.name == "DISABLED"
        assert TROCKENLAUF in ergebnis.detail

    def test_das_urteil_faellt_vor_jedem_git_aufruf(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Nicht 'git lief und tat nichts', sondern 'git lief gar nicht'.

        Ein Trockenlauf, der ``git add`` ausfuehrt und erst danach abbricht,
        hinterlaesst einen veraenderten Index - wieder etwas, das er nicht
        soll.
        """
        import core.report as report

        gerufen: list[tuple] = []
        monkeypatch.setattr(
            report, "_git", lambda *a, **k: gerufen.append(a) or None
        )
        monkeypatch.setenv(TROCKENLAUF, "1")
        (tmp_path / ".git").mkdir()
        datei = tmp_path / "bericht.json"
        datei.write_text("{}")

        publish_fn = report.publish
        publish_fn([datei], root=tmp_path, message="egal")

        assert gerufen == [], f"git wurde trotzdem gerufen: {gerufen}"
