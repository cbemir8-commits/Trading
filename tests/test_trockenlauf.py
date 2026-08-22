"""Ein Test, der die Huerde des haertesten Gates anhebt.

Der Anlass ist ein Fehler von mir. Um Fehler wie den aus Befund 103 zu finden
- ein Befehl, der mit seinen eigenen Voreinstellungen abbricht -, lief ein
Rauchtest ueber alle 61 Befehle. Zwanzig davon **messen und zaehlen dabei**.
Der Versuchszaehler stand danach bei 198 statt 177.

Das ist keine Kleinigkeit: Jeder Versuch hebt die Huerde des Deflated Sharpe
um rund 0,0002 Punkte, dauerhaft und fuer jeden kuenftigen Kandidaten. Ein
Test hat sie um 0,004 angehoben, ohne eine einzige Hypothese zu pruefen.

Drei Tests tragen diese Datei:

``test_der_trockenlauf_haelt_den_zaehler_an`` - Der Kern. Mit gesetzter
Variable schreibt ``speichern`` nicht, und zwar an der einen Stelle, durch die
jeder Schreibvorgang laeuft.

``test_ohne_variable_zaehlt_alles_wie_bisher`` - Die Gegenprobe. Ein Schalter,
der auch ohne Zutun wirkt, waere schlimmer als kein Schalter.

``test_ein_vergessener_trockenlauf_faellt_auf`` - Die Wache gegen die
Nebenwirkung. Ein zu niedriger Zaehler macht den Deflated Sharpe milder -
genau die Richtung, gegen die ``versuche.py`` gebaut ist.
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
        """
        import cli

        quelle = Path(cli.__file__).read_text()
        stelle = quelle[quelle.index("def stand("):]

        assert "trockenlauf()" in stelle[:4000]
        assert "ACHTUNG" in stelle[:4000]

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
