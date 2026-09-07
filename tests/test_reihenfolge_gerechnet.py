"""Die Bedingungen in der Handlungsliste werden gerechnet, nicht geschrieben.

**Befund 235.** ``research/referenz.py`` ist gebaut worden, weil nach Befund
135 *"einundzwanzig Stellen in acht Modulen"* weiter den alten Deflated Sharpe
trugen. Die Handlungsliste in ``reihenfolge.py`` war die zweiundzwanzigste:

    Bedingung   +30 unabhaengige Beobachtungen    keiner   111
    Bedingung   +8,0 % Guete am Spot-Punkt        Suche    108
                "Die Suche braeuchte rund 5.951 Versuche (Nr. 110)"

Alle drei Zahlen stammen aus einer Zeit, in der die effektive Stichprobe bei
152 lag. Heute sind es 115, und alle drei waren zu guenstig:

    Beobachtungen    +30              ->  +75   (115 da, 190 noetig)
    Guete-Luecke     +8,0 %           ->  +24,3 %
    Wettrennen       5.951 Versuche   ->  holt nicht mehr auf

Der Bericht hebt die Guete-Zeile eigens hervor ("Hier laufen wuerde: ..."), es
ist also die eine Zeile, an der eine Untertreibung teuer ist.

Was dieser Test haelt
---------------------
Nicht die Zahlen - die duerfen sich bewegen. Sondern dass sie **aus derselben
Rechnung** kommen wie ueberall sonst. Wer den Referenzpunkt nachzieht, zieht
die Handlungsliste mit; wer sie wieder festschreibt, faellt hier auf.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

from research.referenz import PERPETUALPUNKT, SCHUB, SPOTPUNKT
from research.reihenfolge import STAND, Art, Wer
from research.verbund import noetige_guete
from research.wettrennen import Rennen


def _bedingung(stichwort: str):
    return next(
        s for s in STAND if s.art is Art.BEDINGUNG and stichwort in s.name
    )


class TestDieBeobachtungszeile:
    def test_traegt_die_gerechnete_entfernung(self) -> None:
        noetig = SPOTPUNKT.noetiges_n()
        assert noetig is not None

        s = _bedingung("Beobachtungen")

        assert f"+{noetig - SPOTPUNKT.effektiv} " in s.name
        assert f"{SPOTPUNKT.effektiv} sind da" in s.hinweis
        assert f"{noetig} traegt" in s.hinweis

    def test_die_alte_zahl_steht_nicht_mehr_da(self) -> None:
        """152 und 182 sind der Stand von Befund 111, nicht der heutige."""
        s = _bedingung("Beobachtungen")

        assert "152" not in s.hinweis
        assert "182" not in s.hinweis

    def test_niemand_kann_sie_liefern(self) -> None:
        """Die Quellen sind gemessen geschlossen - das aendert 235 nicht."""
        assert _bedingung("Beobachtungen").wer is Wer.NIEMAND


class TestDieGuetezeile:
    @staticmethod
    def _luecke() -> float:
        latte = noetige_guete(
            SPOTPUNKT.effektiv,
            SPOTPUNKT.versuche,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )
        assert latte is not None
        return latte / (SPOTPUNKT.guete * math.sqrt(SPOTPUNKT.effektiv)) - 1

    def test_traegt_die_gerechnete_luecke(self) -> None:
        erwartet = f"{self._luecke():+.1%}".replace(".", ",").replace("%", " %")

        assert _bedingung("Guete").name.startswith(erwartet)

    def test_die_luecke_ist_gut_dreimal_so_gross_wie_die_alte_angabe(self) -> None:
        """Der Kern des Befundes, als Zahl: 8,0 % aus Befund 108 gegen heute."""
        assert self._luecke() / 0.080 > 2.9

    def test_die_alte_zahl_steht_nicht_mehr_da(self) -> None:
        s = _bedingung("Guete")

        assert "8,0" not in s.name
        assert "5.951" not in s.hinweis

    def test_bleibt_bei_der_suche(self) -> None:
        """Auch wenn das Rennen 'nie' sagt.

        Der Ausgang haengt an ``mittel`` - einer Annahme, keiner Messung. Sie
        auf 'niemand' zu setzen hiesse, eine Annahme als Urteil zu buchen.
        """
        assert _bedingung("Guete").wer is Wer.SUCHE

    def test_der_versuchsstand_kommt_aus_dem_referenzpunkt(self) -> None:
        assert f"verbraucht sind {SPOTPUNKT.versuche}" in _bedingung("Guete").hinweis


class TestDasWettrennen:
    @staticmethod
    def _rennen(**abweichend) -> Rennen:
        werte = dict(
            bester=PERPETUALPUNKT.guete,
            versuche=SPOTPUNKT.versuche,
            trades=SPOTPUNKT.effektiv,
            schub=SCHUB,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )
        werte.update(abweichend)
        return Rennen(**werte)

    def test_die_ideenstreuung_liegt_unter_dem_zufall(self) -> None:
        """**Der Befund in einer Zeile.**

        Befund 71: Huerde und bester Fund wachsen beide mit derselben
        Extremwertkonstante; es entscheidet allein, welche Streuung groesser
        ist. Bei 152 Beobachtungen lag die Ideenstreuung darueber, bei 115
        nicht mehr.
        """
        r = self._rennen()

        assert r.streuung is not None
        assert r.streuung < r.nullstreuung
        assert not r.schneller_als_die_huerde

    def test_das_liegt_an_der_stichprobe_nicht_am_kandidaten(self) -> None:
        """Mit der damaligen Stichprobe holt dieselbe Rechnung wieder auf."""
        damals = self._rennen(trades=152)

        assert damals.streuung is not None
        assert damals.streuung > damals.nullstreuung

    def test_auch_die_guenstigere_annahme_rettet_es_nicht(self) -> None:
        """Befund 110 nennt ein negatives ``mittel`` die guenstigere Annahme.

        Auch dort kommt heute keine erreichbare Zahl mehr heraus - das Ergebnis
        haengt also nicht an der Wahl dieser Annahme.
        """
        for mittel in (0.05, 0.0, -0.05):
            wo = self._rennen(mittel=mittel).wo_holt_sie_auf()

            assert not wo.endswith("Versuche"), f"mittel={mittel}: {wo}"

    def test_der_punktschaetzer_steht_nicht_ohne_seine_spanne(self) -> None:
        """**Befund 236 - die Korrektur an Befund 235.**

        Die Ideenstreuung wird aus **einem** Bestwert zurueckgerechnet und
        streut bei 198 Versuchen um 14,3 %. Solange die Nullstreuung in diesem
        Bereich liegt, ist "die Suche holt nie auf" mit dem Verlauf vereinbar -
        und ebenso, dass sie fast angekommen ist. Ein Satz, der nur die eine
        Seite nennt, gibt eine Bestimmtheit vor, die es nie gab.
        """
        from research.wettrennen import kalibrierbereich

        r = self._rennen()
        assert r.streuung is not None
        unten, oben = kalibrierbereich(r.streuung, r.versuche, irrtum=0.10)
        hinweis = _bedingung("Guete").hinweis

        if unten <= r.nullstreuung <= oben:
            assert "Punktschaetzer" in hinweis
            assert "nach beiden Seiten offen" in hinweis

    def test_die_spanne_enthielt_die_nullstreuung_auch_bei_befund_110(self) -> None:
        """Nicht die Bestimmtheit ist gefallen, sondern der Schaetzwert.

        Bei 152 Beobachtungen lag der Punktschaetzer ueber der Nullstreuung,
        bei 115 darunter - die Spanne umschloss sie beide Male.
        """
        from research.wettrennen import kalibrierbereich

        for trades in (152, SPOTPUNKT.effektiv):
            r = self._rennen(trades=trades)
            assert r.streuung is not None
            unten, oben = kalibrierbereich(r.streuung, r.versuche, irrtum=0.10)

            assert unten <= r.nullstreuung <= oben, f"n_eff {trades}"

    def test_bester_ist_der_perpetual_wert(self) -> None:
        """Die Falle aus Befund 110, als Test.

        In ``bester`` gehoert, was die **Suche** hervorgebracht hat. Gesucht
        wurde unter Perpetual; der Wegfall des Funding ist eine
        Kostenaenderung und kommt als ``schub`` obendrauf.
        """
        assert PERPETUALPUNKT.guete < SPOTPUNKT.guete
        assert math.isclose(
            PERPETUALPUNKT.guete + SCHUB, SPOTPUNKT.guete, abs_tol=5e-5
        )

    def test_der_naive_weg_sieht_produktiver_aus(self) -> None:
        """Deshalb steht er nicht im Code: Er beschoenigt."""
        naiv = self._rennen(bester=SPOTPUNKT.guete, schub=0.0)
        richtig = self._rennen()

        assert naiv.streuung is not None and richtig.streuung is not None
        assert naiv.streuung > richtig.streuung


class TestKeineFestenZahlenMehr:
    """Die Bauart, nicht das Ergebnis: Die beiden Zeilen kommen aus Funktionen."""

    @staticmethod
    def _quelle() -> str:
        return Path("research/reihenfolge.py").read_text()

    def test_die_bedingungen_werden_gerufen_nicht_geschrieben(self) -> None:
        baum = ast.parse(self._quelle())
        stand = next(
            n
            for n in ast.walk(baum)
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "STAND"
        )
        gerufen = {
            e.func.id
            for e in stand.value.elts
            if isinstance(e, ast.Call) and isinstance(e.func, ast.Name)
        }

        assert {"_beobachtungen", "_guetelucke"} <= gerufen

    def test_der_modulkopf_traegt_den_heutigen_stand(self) -> None:
        """Ein Modulkopf wird als Stand gelesen - so steht es in referenz.py.

        Die alten Zahlen duerfen darin vorkommen: Sie stehen dort ausdruecklich
        als das, was ueberholt wurde. Was zaehlt, ist, dass die heutigen auch
        da sind - die Tabelle im Kopf ist das, was ein Leser zuerst sieht.
        """
        kopf = ast.get_docstring(ast.parse(self._quelle())) or ""
        noetig = SPOTPUNKT.noetiges_n()
        assert noetig is not None

        assert f"+{noetig - SPOTPUNKT.effektiv} unabhaengige Beobachtungen" in kopf
        assert _bedingung("Guete").name in kopf

    def test_die_alten_zahlen_stehen_nur_als_geschichte_da(self) -> None:
        """Wo sie vorkommen, steht dabei, dass sie ueberholt sind."""
        kopf = ast.get_docstring(ast.parse(self._quelle())) or ""
        zeile = next(z for z in kopf.splitlines() if "5.951" in z)
        umgebung = kopf[: kopf.index(zeile) + len(zeile)]

        assert "standen hier" in umgebung
