"""Ein Gate, das auf stillgelegten Nachbarn bestanden hat - Befund 330.

Befund 314 hat ``research/landschaft.py`` umgebaut und - weil ``cli landschaft``
den Versuchszaehler schreibt - **nie laufen lassen**. Dieser Lauf hat es
nachgeholt, mit dem Zaehler auf eine Wegwerf-Ablage umgelenkt
(``PATHS__STATE``), und die Karte hat sofort geredet:

    Faktor  rsi(period=14)  Trades  Gewinn  gesperrt
      0.50               7      90  478.63        75
      ...
      2.00              28      90  455.88        75

**12 von 12 Punkten stillgelegt, 900 verhinderte Einstiege** - und darunter
stand "Plateau: 12 zusammenhaengende Punkte von 12, der Kandidat mittendrin".

Dieselbe Frage am Gate gestellt, Spitzenkandidat, Spot-Betriebspunkt:

    Parameter-Plateau       PASS, Wert 1,0000 gegen Schwelle 0,60
    Nachbarn profitabel     12 von 12
    davon stillgelegt       12 von 12
    verhinderte Einstiege   737

Die volle Punktzahl steht auf zwoelf Laeufen, von denen **keiner** zu Ende
gemessen wurde. ``sperrsatz`` gibt es seit Befund 313 - und es hing nur am
Fehlschlag-Zweig. Der Erfolgsfall ist aber genau der, in dem niemand nachsieht.
Dieselbe Bauart wie Befund 321/322: Was nicht gemessen wurde, zaehlte als
bestanden.

**Wert und Urteil des Gates bleiben unberuehrt.** Ob ein stillgelegter Nachbar
zaehlen darf, liegt als Entscheidung beim Nutzer (Befund 313). Was sich aendert,
ist nur, dass es dasteht.
"""

from __future__ import annotations

import pytest

from research.freigabe import bestandsatz, sperrsatz
from research.landschaft import Landschaft, Punkt


def _punkt(faktor: float, gewinn: float, gesperrt: int = 0) -> Punkt:
    return Punkt(
        faktor=faktor,
        leitperiode=200,
        gewinn=gewinn,
        trades=90,
        gesperrt=gesperrt,
    )


class TestDerSatzZumBestehen:
    def test_ohne_sperren_steht_nichts(self) -> None:
        """Eine Warnung, die immer angeht, ist keine (Befund 324)."""
        assert bestandsatz(0, 12, 0) == ""

    def test_bei_allen_sagt_er_kein_einziger(self) -> None:
        satz = bestandsatz(12, 12, 737)

        assert "kein einziger Nachbar" in satz
        assert "737" in satz

    def test_bei_einigen_nennt_er_die_zahl(self) -> None:
        satz = bestandsatz(5, 12, 200)

        assert "5 von 12" in satz
        assert "kein einziger" not in satz

    def test_er_nennt_die_quote_als_nicht_tragend(self) -> None:
        """Der Punkt des Satzes: Die Quote oben bleibt stehen, sie beantwortet
        nur die Formfrage nicht."""
        satz = bestandsatz(12, 12, 737)

        assert "sagt damit nicht, welche Form" in satz

    def test_er_urteilt_nicht_ueber_das_gate(self) -> None:
        """Ob ein stillgelegter Nachbar zaehlen darf, ist eine Entscheidung
        des Nutzers - dieser Satz greift sie nicht vor."""
        satz = bestandsatz(12, 12, 737).casefold()

        for wort in ("durchgefallen", "ungueltig", "zaehlt nicht"):
            assert wort not in satz

    def test_er_ist_nicht_derselbe_wie_beim_fehlschlag(self) -> None:
        """``sperrsatz`` spricht von den **gescheiterten** Nachbarn - im
        Erfolgsfall ist keiner gescheitert, und der Satz waere falsch."""
        assert "gescheiterten" in sperrsatz(737)
        assert "gescheiterten" not in bestandsatz(12, 12, 737)


class TestDasGateSagtEsJetztAuchBeimBestehen:
    """**Die Verdrahtung.** Befund 313 hat 'gesperrt' eingesammelt und an einen
    von zwei Zweigen gehaengt."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("research/gates.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "gate_parameter_plateau"
        )

    def test_der_erfolgszweig_nennt_die_stilllegung(self) -> None:
        assert "bestandsatz" in self._quelle()

    def test_und_der_fehlschlag_weiter_seinen_satz(self) -> None:
        assert "sperrsatz" in self._quelle()

    def test_wert_und_urteil_haengen_nicht_daran(self) -> None:
        """Die Entscheidung liegt beim Nutzer (Befund 313) - der Quelltext
        darf sie nicht nebenbei treffen."""
        quelle = self._quelle()

        assert "passed = ratio >= t.min_plateau_ratio" in quelle
        for muster in ("passed and", "and not gesperrt", "if gesperrt: passed"):
            assert muster not in quelle


class TestDieKarteBehauptetKeineFormMehr:
    """``Landschaft.urteil`` hat nach dem Vorbehalt aus Befund 314 weiter eine
    Form benannt."""

    @staticmethod
    def _alle_gesperrt() -> Landschaft:
        return Landschaft(
            punkte=[_punkt(f / 10, 100.0, gesperrt=75) for f in range(5, 17)],
            mitte=1.0,
            regler="rsi(period=14)",
        )

    def test_bei_durchweg_stillgelegten_punkten(self) -> None:
        urteil = self._alle_gesperrt().urteil()

        assert "Eine Form ist damit nicht gemessen" in urteil
        assert "Plateau: " not in urteil

    def test_die_zahlen_bleiben_alle_stehen(self) -> None:
        """Nichts wird stillschweigend weggelassen - wer die Karte liest, soll
        sehen, was sie gemessen hat."""
        karte = self._alle_gesperrt()

        urteil = karte.urteil()

        assert f"{len(karte.profitabel)} von {len(karte.punkte)}" in urteil
        assert str(karte.verhinderte_einstiege) in urteil

    def test_und_der_vorbehalt_aus_314_steht_davor(self) -> None:
        urteil = self._alle_gesperrt().urteil()

        assert urteil.index("nicht zu Ende gemessen") < urteil.index(
            "Eine Form ist damit nicht gemessen"
        )

    def test_ohne_sperren_urteilt_sie_wie_bisher(self) -> None:
        sauber = Landschaft(
            punkte=[_punkt(f / 10, 100.0) for f in range(5, 17)], mitte=1.0
        )

        urteil = sauber.urteil()

        assert "Plateau: 12 zusammenhaengende Punkte" in urteil
        assert "nicht zu Ende gemessen" not in urteil
        assert sauber.zu_ende_gemessen

    def test_bei_einzelnen_sperren_bleibt_das_alte_urteil(self) -> None:
        """Teilweise stillgelegt heisst nicht "nichts gemessen" - dort traegt
        der Vorbehalt aus Befund 314 allein, und die Form bleibt lesbar."""
        gemischt = Landschaft(
            punkte=[
                _punkt(0.5, 100.0, gesperrt=10),
                *[_punkt(f / 10, 100.0) for f in range(6, 17)],
            ],
            mitte=1.0,
        )

        urteil = gemischt.urteil()

        assert "nicht zu Ende gemessen" in urteil
        assert "Plateau: " in urteil
        assert not gemischt.zu_ende_gemessen


class TestZuEndeGemessen:
    def test_ein_punkt_ohne_sperre(self) -> None:
        assert _punkt(1.0, 10.0).zu_ende_gemessen

    def test_ein_punkt_mit_sperre(self) -> None:
        assert not _punkt(1.0, 10.0, gesperrt=1).zu_ende_gemessen

    def test_eine_leere_karte_gilt_als_gemessen(self) -> None:
        """Nichts abgetastet heisst nichts stillgelegt - das Urteil faengt den
        leeren Fall schon vorher ab."""
        assert Landschaft().zu_ende_gemessen


@pytest.mark.parametrize(
    ("gesperrt", "punkte", "erwartet"),
    [(0, 12, False), (1, 12, True), (12, 12, True)],
)
def test_der_satz_kommt_genau_dann_wenn_etwas_gesperrt_war(
    gesperrt, punkte, erwartet
) -> None:
    assert bool(bestandsatz(gesperrt, punkte, 100)) is erwartet


class TestDerZaehlerLaesstSichUmlenken:
    """**Das Werkzeug, das diesen Befund moeglich gemacht hat.**

    ``cli landschaft`` steht nur deshalb in ``WIRKT_NACH_AUSSEN``, weil es
    ``state/trials.json`` schreibt - und deshalb war der Umbau aus Befund 314
    nie ausgefuehrt. ``PATHS__STATE`` lenkt die Ablage um, der Lauf bucht in
    eine Wegwerf-Datei, und der echte Zaehler bleibt stehen.

    Ein Rauchtest prueft keine Hypothese und sein Ergebnis wird weggeworfen -
    deshalb ist er kein Versuch. Ob ein **Forschungslauf** am Bestand einer
    ist, liegt als Entscheidung beim Nutzer (Befund 282/233); dieser Test
    greift sie nicht vor.
    """

    def test_die_ablage_folgt_der_umgebungsvariable(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setenv("PATHS__STATE", str(tmp_path))
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            assert get_settings().paths.state == str(tmp_path)
        finally:
            get_settings.cache_clear()

    def test_ohne_die_variable_bleibt_es_bei_state(self, monkeypatch) -> None:
        monkeypatch.delenv("PATHS__STATE", raising=False)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            assert get_settings().paths.state == "state"
        finally:
            get_settings.cache_clear()
