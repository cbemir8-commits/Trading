"""Die folgenreichste Entscheidung stand nicht unter den Entscheidungen - 415.

Befund 400 hat sie dem Nutzer zugewiesen: Welcher der vier Messaufbauten die
Zulassung traegt. Die Befunde 403 bis 414 haengen an ihr - zwoelf Stueck -, und
verzeichnet war sie als **Zeichenkette** an ``Betriebspunkt.voraussetzung`` und
in Registerprosa. In ``ENTSCHEIDUNGEN``, der Liste, die ``cli register``
aufzaehlt und zaehlt, stand sie nicht.

Dieselbe Lehre wie Befund 394 (die elf Zeilen gab es in keiner Ausgabe), 405
(der Punkt mit greifenden Grenzen stand in keiner Kopfzeile) und 408 (in der
Prosa und als Behauptung im Test): Ein Satz in einem Prosatext ist keine
Auskunft an der Stelle, an der jemand nachsieht.
"""

from __future__ import annotations

import pytest

from research.stand import ENTSCHEIDUNGEN


def _modus():
    return next(
        e for e in ENTSCHEIDUNGEN if e.frage == "Welcher Modus die Zulassung traegt"
    )


class TestSieStehtJetztDrin:
    def test_mit_erst_und_nachmessung(self) -> None:
        e = _modus()

        assert e.befund == 400
        assert e.zuletzt == 414
        assert e.massgeblich == 414

    def test_und_zuerst(self) -> None:
        """Die anderen zehn betreffen Zahlen, diese betrifft, welche Zahlen
        gelten - darum steht sie oben."""
        assert ENTSCHEIDUNGEN[0] is _modus()

    def test_sie_nennt_alle_vier_aufbauten(self) -> None:
        zahl = _modus().zahl

        for cagr in ("14,3391", "14,1915", "11,6275", "19,0053"):
            assert cagr in zahl

    def test_und_was_in_jedem_aufbau_haelt(self) -> None:
        zahl = _modus().zahl

        assert "Acht der elf Urteile" in zahl
        assert "Deflated Sharpe faellt in allen vier" in zahl

    def test_und_den_eigentlichen_tausch(self) -> None:
        """Der Kern der Entscheidung: Messlatte gegen zwei andere Gates."""
        zahl = _modus().zahl

        assert "Messlatte besteht nur im durchgehenden Lauf" in zahl
        assert "eine Zulassung bringt sie nicht" in zahl


class TestDieArgumenteStehenMitIhremStand:
    def test_das_argument_gegen_die_beingrenzen(self) -> None:
        warum = _modus().warum

        assert "zwei getrennte Konten" in warum
        assert "10,77 %" in warum

    def test_das_argument_fuer_den_gemeldeten_aufbau(self) -> None:
        warum = _modus().warum

        assert "massinvariant" in warum

    def test_und_das_weggefallene(self) -> None:
        """Ein Argument, das nicht mehr traegt, gehoert als solches
        verzeichnet - nicht geloescht und nicht stehengelassen."""
        warum = _modus().warum

        assert "weggefallen" in warum
        assert "0,7336 gegen" in warum
        assert "traegt nicht mehr" in warum

    def test_und_dass_sie_kein_weg_durch_die_gates_ist(self) -> None:
        warum = _modus().warum

        assert "wer einen Aufbau nach dem Ergebnis auswaehlt, lockert" in warum


class TestDieZahlenStimmenMitDenMessungen:
    """Eine zweite gepflegte Liste zur selben Sache laeuft auseinander
    (Befund 408). Also wird dieser Eintrag gegen die Messungen geprueft."""

    def test_die_gefallenen_gates_je_zelle(self) -> None:
        from research.grenzgedaechtnis import GATEKREUZ

        zahl = _modus().zahl

        for gates in GATEKREUZ.values():
            for gate in gates:
                assert gate in zahl, gate

    def test_die_jahresrenditen_je_zelle(self) -> None:
        from research.grenzgedaechtnis import GEMESSEN

        zahl = _modus().zahl

        for lauf in GEMESSEN.laeufe:
            assert f"{lauf.cagr_pct:.4f}".replace(".", ",") in zahl

    def test_die_stichproben_beider_punkte(self) -> None:
        from research.referenz import KONTOPUNKT, SPOTPUNKT

        zahl = _modus().zahl

        assert f"{SPOTPUNKT.effektiv} von {SPOTPUNKT.trades}" in zahl
        assert f"{KONTOPUNKT.effektiv} von {KONTOPUNKT.trades}" in zahl

    def test_und_der_massvorbehalt_aus_414(self) -> None:
        from research.grenzgedaechtnis import MASSFAKTOREN

        konto = next(f for f in MASSFAKTOREN if f.punkt == "kontogeschuetzt")
        zahl = _modus().zahl

        assert f"{konto.n_r} statt {konto.n_waehrung}" in zahl


class TestDieStatuszeileUndDieListeMeinenDasselbe:
    """Der eigentliche Gewinn: Die Zeichenkette, die 'cli stand' druckt, und
    der Eintrag im Register duerfen nicht auseinanderlaufen."""

    def test_die_voraussetzung_nennt_die_frage_woertlich(self) -> None:
        import inspect

        import cli

        quelle = inspect.getsource(cli._spotpunkt)
        frage = _modus().frage

        assert frage in quelle, (
            "Die Zeile in 'cli stand' und der Registereintrag nennen "
            "verschiedene Fragen - dann ist nicht zu sehen, dass es dieselbe "
            "ist."
        )

    def test_und_dieselbe_fundstelle(self) -> None:
        import inspect

        import cli

        quelle = inspect.getsource(cli._spotpunkt)

        assert f"({_modus().befund})" in quelle

    def test_der_scan_kennt_ihre_begriffe(self) -> None:
        """Ohne Begriffe findet 'cli register' zu dieser Frage nie etwas
        Spaeteres - der Eintrag waere eingetragen und blind."""
        from research.nachmessung import ENTSCHEIDUNGSBEGRIFFE

        begriffe = ENTSCHEIDUNGSBEGRIFFE[_modus().frage]

        assert "durchgehend" in begriffe
        assert "Beingrenze" in begriffe

    def test_jede_entscheidung_mit_fundstelle_hat_begriffe(self) -> None:
        """Die Gegenprobe zum Einbau: Wenn die neue Frage Begriffe braucht,
        brauchen sie alle - sonst ist die Wache eine Einzelfallregel."""
        from research.nachmessung import ENTSCHEIDUNGSBEGRIFFE

        ohne = [
            e.frage
            for e in ENTSCHEIDUNGEN
            if e.befund and e.frage not in ENTSCHEIDUNGSBEGRIFFE
        ]

        assert ohne == [], f"ohne Begriffe: {ohne}"


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_zwoelf_befunde(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 415)

        assert "403 bis 414" in eintrag.ergebnis
        assert "Zeichenkette" in eintrag.ergebnis

    def test_und_dass_keine_frage_dazukommt(self) -> None:
        """Wichtig fuer den Nutzer: Der Eintrag legt ihm nichts Neues auf."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 415)

        assert "keine Frage mehr auf" in eintrag.ergebnis

    def test_und_414_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 414).zuletzt == 415

    def test_die_wache_wurde_nachgezogen_nicht_umgangen(self) -> None:
        """'test_es_sind_zehn' hat gegriffen. Sie heisst jetzt
        'test_es_sind_elf' und traegt die Begruendung - genau das, was sie
        verlangt."""
        from pathlib import Path

        import tests.test_eichbasis as eich

        text = Path(eich.__file__).read_text(encoding="utf-8")

        assert "def test_es_sind_elf" in text
        assert "hier ist die Begruendung, die dieser Test verlangt" in text
        assert "def test_es_sind_zehn" not in text


@pytest.mark.parametrize("feld", ["zahl", "warum"])
def test_der_eintrag_ist_keine_stichwortliste(feld: str) -> None:
    """Ein Eintrag, der die Lage nicht traegt, waere nur ein Haken."""
    assert len(getattr(_modus(), feld)) > 600


class TestSieStehtJetztImBericht:
    """Der eigentliche Gewinn: Die Frage erscheint dort, wo der Nutzer
    nachsieht - 'cli stand' druckt die Entscheidungen mit."""

    def _bericht(self) -> str:
        from research.stand import Lage

        return Lage(
            kandidat="Trend 50 Tage mit Konfluenz",
            maerkte="BTC + ETH, 1d",
            trades=156,
            sharpe_je_trade=0.2708,
            noetiger_sharpe=0.3374,
            bestanden=9,
            gesamt=11,
            offen=("Messlatte", "Deflated Sharpe"),
            versuche=203,
        ).bericht()

    def test_die_frage_steht_drin(self) -> None:
        assert _modus().frage in self._bericht()

    def test_und_der_tausch_den_sie_bedeutet(self) -> None:
        bericht = self._bericht()

        assert "Messlatte besteht nur im durchgehenden Lauf" in bericht
        assert "19,0053" in bericht

    def test_und_das_weggefallene_argument(self) -> None:
        assert "traegt nicht mehr" in self._bericht()

    def test_die_grenzzeile_wird_davon_nicht_vorgetaeuscht(self) -> None:
        """Die Kehrseite, an der zwei Wachen gefallen sind: Der Bericht nennt
        'Beingrenzen' jetzt auch in dieser Tabelle. Wer die **Zeile** sucht,
        muss die Zeile pruefen, nicht das Wort."""
        bericht = self._bericht()

        assert "Beingrenzen" in bericht
        assert not any(
            z.startswith("  Beingrenzen    ") for z in bericht.splitlines()
        )
