"""Der Trockenlauf deckt alle Schreibstellen - Befund 331.

Befund 330 wollte 'cli landschaft' rauchtesten. Der Befehl steht in
``WIRKT_NACH_AUSSEN``, weil er den Versuchszaehler schreibt, und ich habe mir
dafuer ein Mittel gebaut: ``PATHS__STATE`` lenkt die Zustandsablage um, der Lauf
bucht in eine Wegwerf-Datei. Fuer 'landschaft' war das richtig - es schreibt
sonst nichts.

Dann habe ich dasselbe Mittel auf 'cli wettbewerb' angewandt. Das schreibt
mehr: Journal, Bestenliste, eine Berichtsdatei - und es **committet sie und
pusht**. Der Bericht ``e00ffb7`` ist so in die Projekthistorie gekommen, wo er
wie ein Suchlauf aussieht, obwohl der Zaehler bei 203 stehen blieb.

**Das war die Wiederholung von Befund 117.** Der Docstring von
``core.report.publish`` beschreibt denselben Vorfall:

    Das ist die sichtbarste Schreibstelle von allen: Sie committet **und
    pusht**, und ein Rauchtest landet damit in der Projekthistorie, wo er wie
    ein Lauf aussieht. Genau das ist passiert - ``54770ec`` ist der Bericht
    meines eigenen Rauchtests.

Das richtige Mittel stand seit Befund 116 bereit und heisst
``TRADING_TROCKENLAUF``. Sein Docstring sagt, was es deckt:

    Wer die Variable setzt, hinterlaesst nichts - Zaehler, Bestenliste und
    Berichte gleichermassen.

Gemessen an 'cli wettbewerb' mit der Variable: Versuche 203 vor und nach dem
Lauf, Berichtsordner unveraendert, Arbeitsbaum sauber, und fuenf ausdrueckliche
Abmeldungen im Protokoll (zaehler, journal, bestenliste, bericht, senden).

Ich habe ein Teilmittel gebaut, wo ein vollstaendiges lag - dieselbe Bauart wie
Befund 302 und 318, nur diesmal nicht bei einer Messung, sondern bei einem
Werkzeug. Der Vorflug aus 319/320/324 fragt das Register vor einer **Messung**;
vor einem **Werkzeug** habe ich ihn nicht gefragt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.versuche import TROCKENLAUF, trockenlauf


class TestDieVariableSelbst:
    @pytest.mark.parametrize("wert", ["1", "ja", "true", "x", "AN"])
    def test_gesetzt_heisst_trockenlauf(self, wert, monkeypatch) -> None:
        monkeypatch.setenv(TROCKENLAUF, wert)

        assert trockenlauf()

    @pytest.mark.parametrize("wert", ["", "0", "nein", "false", "aus"])
    def test_diese_werte_zaehlen_als_aus(self, wert, monkeypatch) -> None:
        monkeypatch.setenv(TROCKENLAUF, wert)

        assert not trockenlauf()

    def test_ohne_variable_laeuft_es_scharf(self, monkeypatch) -> None:
        """Die sichere Richtung: Wer die Variable vergisst, schreibt - und
        merkt es. Umgekehrt waere es nicht zu merken."""
        monkeypatch.delenv(TROCKENLAUF, raising=False)

        assert not trockenlauf()


class TestDasSendenIstGedeckt:
    """**Die Schreibstelle, die Befund 331 gekostet hat.**"""

    def test_publish_sendet_im_trockenlauf_nicht(self, tmp_path, monkeypatch) -> None:
        from core.report import PublishStatus, publish

        monkeypatch.setenv(TROCKENLAUF, "1")
        datei = tmp_path / "bericht.json"
        datei.write_text("{}", encoding="utf-8")

        ergebnis = publish([datei], root=tmp_path, message="test")

        assert ergebnis.status is PublishStatus.DISABLED
        assert TROCKENLAUF in (ergebnis.detail or "")

    def test_und_zwar_vor_der_enabled_pruefung(self, tmp_path, monkeypatch) -> None:
        """Der Trockenlauf gilt auch dann, wenn der Aufrufer ``enabled=True``
        uebergibt - sonst haette jede Aufrufstelle ihre eigene Wache."""
        from core.report import PublishStatus, publish

        monkeypatch.setenv(TROCKENLAUF, "1")
        datei = tmp_path / "bericht.json"
        datei.write_text("{}", encoding="utf-8")

        ergebnis = publish([datei], root=tmp_path, message="test", enabled=True)

        assert ergebnis.status is PublishStatus.DISABLED

    def test_ohne_trockenlauf_und_ohne_repo_wird_nichts_gesendet(
        self, tmp_path, monkeypatch
    ) -> None:
        """Die Gegenprobe: Ohne die Variable greift der Schutz nicht mehr, und
        nur das fehlende Repository haelt den Aufruf auf. Genau diese Luecke
        stand in Befund 331 offen."""
        from core.report import PublishStatus, publish

        monkeypatch.delenv(TROCKENLAUF, raising=False)
        datei = tmp_path / "bericht.json"
        datei.write_text("{}", encoding="utf-8")

        ergebnis = publish([datei], root=tmp_path, message="test")

        assert ergebnis.status is not PublishStatus.DISABLED
        assert ergebnis.status is PublishStatus.NO_REPO


class TestPathsStateDecktNurDenZaehler:
    """Warum das Mittel aus Befund 330 nicht genuegt - als Test, nicht als
    Behauptung."""

    def test_die_umlenkung_wirkt_auf_den_zustand(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("PATHS__STATE", str(tmp_path))
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            assert get_settings().paths.state == str(tmp_path)
        finally:
            get_settings.cache_clear()

    def test_aber_nicht_auf_den_berichtsordner(self, tmp_path, monkeypatch) -> None:
        """``write_report`` schreibt unter ``root``, und das ist das
        Arbeitsverzeichnis - von ``PATHS__STATE`` unberuehrt."""
        monkeypatch.setenv("PATHS__STATE", str(tmp_path))
        monkeypatch.delenv(TROCKENLAUF, raising=False)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            from core.report import write_report

            ziel = tmp_path / "arbeit"
            ziel.mkdir()
            datei = write_report({"art": "test"}, root=ziel, kind="zulassung")

            assert datei.is_relative_to(ziel)
            assert not datei.is_relative_to(tmp_path / "zustand")
        finally:
            get_settings.cache_clear()


def test_die_einteilung_nennt_das_senden_bei_wettbewerb() -> None:
    """Der Grund in ``WIRKT_NACH_AUSSEN`` sagte nur "schreibt den
    Versuchszaehler". Wer das liest, deckt den Zaehler ab und ist fertig."""
    from tests.test_rauchtest import WIRKT_NACH_AUSSEN

    assert "pusht" in WIRKT_NACH_AUSSEN["wettbewerb"]
    assert "Bericht" in WIRKT_NACH_AUSSEN["research"]


def test_die_wache_steht_im_quelltext_der_sendestelle() -> None:
    """Sie darf nicht in eine Aufrufstelle wandern - dann waere sie eine
    Vereinbarung statt einer Wache."""
    quelle = Path("core/report.py").read_text(encoding="utf-8")

    assert "trockenlauf()" in quelle
    assert quelle.index("trockenlauf()") < quelle.index("if not enabled")
