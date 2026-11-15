"""Der Vermerk muss die Kerzenlaenge kennen - Befund 492.

Derselbe Fehler, eine Stelle weiter
-----------------------------------
Befund 491 hat den **Schnitt** intervallbewusst gemacht. Der **Vermerk**
daneben - ``datenstand.reihenzeile``, gebaut in Befund 370, damit eine Zahl
nicht ohne ihre Reihe dasteht - verglich weiter gegen ``SERIENENDE``, die
Tagesreihe. Alle vier Befehle, die ihn drucken (``abstand``, ``aufteilung``,
``rennen``, ``stand``), nehmen ``-i``. Gemessen am echten Speicher stand auf
Viertelstundenkerzen:

    229728 Balken gemeinsam - laenger als die Zulassungsreihe
    (bis 2026-08-29); die Zahlen hier weichen deshalb von referenz.py ab

229.728 Balken bis 2026-10-17 **sind** die gepflegte Feinreihe - die gepinnte
Zahl aus Befund 426. Der Vermerk, der einen unerklaerten Unterschied
verhindern sollte, erfand einen, und zwar im Kopf von ``cli stand``.

Die Grenze wird gefragt, nicht nachgebaut
-----------------------------------------
Die beiden Reihen enden verschieden: Tagesreihe geschlossen (``<=``),
Feinreihe halboffen (``<``). Ein ``<=`` dort ergibt 229.729 statt 229.728 -
``fein_geschnitten`` sagt das selbst. Deshalb rechnet ``letzter_tag`` den
Unterschied nicht nach, sondern legt eine kurze Probe vor das Ende und laesst
den echten Schnitt entscheiden. Eine zweite Stelle, die dasselbe aufschreibt,
waere die zweite Wahrheit, und die altert (Befund 234).

``intervall`` ist Pflicht
-------------------------
Kein Vorgabewert. Der Weg in diesen Fehler war genau ein Vorgabewert: ``-i``
steht bei allen vier Befehlen auf ``D``, und der Vermerk nahm stillschweigend
dasselbe an. Wer die Kerzenlaenge nennen muss, kann sie nicht vergessen.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from research.datenstand import (
    FEINBALKEN,
    FEINENDE,
    REIHENENDE,
    REIHENNAME,
    SERIENENDE,
    letzter_tag,
    reihenzeile,
)

WURZEL = Path(__file__).resolve().parents[1]


def _tage(von: str, bis: str) -> pd.DataFrame:
    return pd.DataFrame(
        {"open_time": pd.date_range(von, bis, freq="1D", tz="UTC")}
    )


class TestDerLetzteTagKommtAusDemSchnitt:
    def test_die_tagesreihe_endet_geschlossen(self) -> None:
        assert letzter_tag("D") == SERIENENDE

    def test_die_feinreihe_endet_halboffen(self) -> None:
        """Der Tag **vor** ``FEINENDE`` - und das ist nicht nachgerechnet,
        sondern vom Schnitt beantwortet."""
        assert letzter_tag("15") == FEINENDE - pd.Timedelta(days=1).to_pytimedelta()

    def test_und_fuer_eine_fremde_kerzenlaenge_gibt_es_keinen(self) -> None:
        """``None`` ist keine Null: Es gibt keine gepflegte Reihe, und der
        Aufrufer muss das unterscheiden."""
        assert letzter_tag("W") is None
        assert letzter_tag("") is None

    def test_beide_tafeln_kennen_dieselben_kerzenlaengen(self) -> None:
        """Zwei Tafeln nach Kerzenlaenge sind zwei Gelegenheiten, eine zu
        vergessen - deshalb steht der Vergleich hier."""
        assert set(REIHENNAME) == set(REIHENENDE)


class TestDasTorFragtDieselbeGrenze:
    """``speicher_ist_gepinnt`` schrieb die halboffene Grenze ein **zweites**
    Mal auf - und daran haengt das Tor aus Befund 430, also die Frage, ob die
    drei Datenausfaelle erwartet sind. Eine zweite Wahrheit an der teuersten
    Stelle."""

    def test_die_erlaubten_enden_sind_die_gefragten(self) -> None:
        from research.datenstand import speicher_ist_gepinnt

        erlaubt = {
            tag for iv in REIHENENDE if (tag := letzter_tag(iv)) is not None
        }

        assert erlaubt == {SERIENENDE, FEINENDE - pd.Timedelta(days=1).to_pytimedelta()}
        for tag in erlaubt:
            assert speicher_ist_gepinnt({"x": (SERIENENDE, tag, 1)}), tag

    def test_und_ein_tag_daneben_faellt_durch(self) -> None:
        """Die Gegenprobe: Waere jedes Ende erlaubt, waere das Tor offen."""
        from research.datenstand import speicher_ist_gepinnt

        daneben = FEINENDE  # ein Tag zu weit - die Grenze ist halboffen
        assert not speicher_ist_gepinnt({"x": (SERIENENDE, daneben, 1)})

    def test_die_regel_listet_die_enden_nicht_mehr(self) -> None:
        """Gefunden statt gelistet (Befund 234): Der Satz, der die Grenze von
        Hand aufschrieb, darf nicht zurueckkommen.

        **Geprueft wird der Code, nicht der Text.** Der erste Entwurf sah auf
        die ganze Funktion und fiel an seiner eigenen Zusicherung, weil der
        Docstring den alten Satz zitiert - dieselbe Selbstwiderlegung wie bei
        GELESEN in Befund 295.
        """
        baum = ast.parse((WURZEL / "research/datenstand.py").read_text("utf-8"))
        fn = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "speicher_ist_gepinnt"
        )
        ohne_text = [
            k
            for k in fn.body
            if not (
                isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant)
            )
        ]
        rumpf = "\n".join(ast.unparse(k) for k in ohne_text)

        assert "letzter_tag(" in rumpf
        assert "timedelta(days=1)" not in rumpf, "die zweite Wahrheit ist zurueck"


class TestDerVermerkNenntDieRichtigeReihe:
    def test_auf_tageskerzen_die_zulassungsreihe(self) -> None:
        zeile = reihenzeile({"a": _tage("2017-08-16", "2026-08-29")}, "D")

        assert zeile.endswith("- die Zulassungsreihe")

    def test_auf_feinkerzen_die_feinreihe(self) -> None:
        """**Die Gegenprobe zum Fund.** Vor 492 stand hier *"laenger als die
        Zulassungsreihe ... weichen deshalb von referenz.py ab"*."""
        zeile = reihenzeile({"a": _tage("2020-03-30", "2026-10-17")}, "15")

        assert zeile.endswith("- die gepflegte Feinreihe"), zeile
        assert "laenger als" not in zeile
        assert "referenz.py" not in zeile

    def test_eine_feinreihe_ueber_feinende_wird_benannt(self) -> None:
        """Der Vermerk schweigt nicht, wenn es wirklich zu viel ist - sonst
        haette 492 nur ein Warnlicht ausgeschaltet."""
        zeile = reihenzeile({"a": _tage("2020-03-30", "2026-10-31")}, "15")

        assert "laenger als die gepflegte Feinreihe" in zeile
        assert "weichen deshalb von referenz.py ab" in zeile

    def test_und_eine_zu_kurze_auch(self) -> None:
        zeile = reihenzeile({"a": _tage("2020-03-30", "2026-09-30")}, "15")

        assert "kuerzer als die gepflegte Feinreihe" in zeile

    def test_eine_fremde_kerzenlaenge_wird_nicht_an_fremdem_ende_gemessen(
        self,
    ) -> None:
        """Die Richtung aus Befund 370: lieber ungeschnitten und benannt als
        mit dem Ende einer fremden Reihe verglichen."""
        zeile = reihenzeile({"a": _tage("2020-01-01", "2026-12-31")}, "W")

        assert "keine gepflegte Reihe fuer W-Kerzen" in zeile
        assert "auf dem Speicher" in zeile
        assert "Zulassungsreihe" not in zeile

    def test_ohne_kerzen_bleibt_es_bei_der_kurzen_antwort(self) -> None:
        assert reihenzeile({}, "15") == "keine Kerzen"


class TestKeinAufrufOhneKerzenlaenge:
    """Die Regel. **Geprueft wird der Aufruf, nicht ein Funktionsname**
    (Befund 491): Ein Vorgabewert waere der Weg zurueck in diesen Fehler."""

    def _aufrufe(self, datei: str) -> list[ast.Call]:
        baum = ast.parse((WURZEL / datei).read_text(encoding="utf-8"))
        return [
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Name)
            and k.func.id in ("reihenzeile", "_reihenzeile")
        ]

    def test_in_der_befehlsdatei_nennt_jeder_die_kerzenlaenge(self) -> None:
        knapp = [
            ast.unparse(k) for k in self._aufrufe("cli.py") if len(k.args) < 2
        ]

        assert knapp == [], (
            "ruft den Reihenvermerk ohne Kerzenlaenge - genau das war "
            f"Befund 492: {knapp}"
        )

    def test_und_es_gibt_welche(self) -> None:
        """Nichtleere-Zusicherung (Befund 479): Sonst waere die Regel
        darueber leer erfuellt."""
        assert len(self._aufrufe("cli.py")) >= 7, len(self._aufrufe("cli.py"))

    def test_der_vorgabewert_ist_nicht_zurueckgekommen(self) -> None:
        """Die Pflicht steht in der Signatur, nicht nur in der Absicht."""
        baum = ast.parse((WURZEL / "research/datenstand.py").read_text("utf-8"))
        fn = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "reihenzeile"
        )

        assert [a.arg for a in fn.args.args] == ["frames", "intervall"]
        assert fn.args.defaults == [], "ein Vorgabewert war der Weg hinein"

    def test_der_vermerk_wird_ohne_kerzenlaenge_abgelehnt(self) -> None:
        """Nicht nur die Signatur lesen - den Aufruf versuchen."""
        with pytest.raises(TypeError):
            reihenzeile({"a": _tage("2020-03-30", "2026-10-17")})  # type: ignore[call-arg]


@pytest.mark.daten
class TestAmEchtenSpeicher:
    def _frame(self, intervall: str):
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore

        store = CandleStore(get_settings().paths.data_store)
        frame = store.read("BTCUSD_BITSTAMP", Interval(intervall))
        if frame.empty:
            pytest.skip(
                f"keine {intervall}-Kerzen im Speicher dieses Containers - "
                f"mit 'cli backfill' zu holen"
            )
        return {"BTCUSD_BITSTAMP": frame}

    def test_die_feinreihe_wird_nicht_mehr_als_zu_lang_gemeldet(self) -> None:
        """**Die Messung, die den Fehler gezeigt hat.** 229.728 Balken sind
        die gepflegte Reihe, nicht zu viele."""
        roh = self._frame("15")
        zeile = reihenzeile(roh, "15")

        assert len(roh["BTCUSD_BITSTAMP"]) == FEINBALKEN
        assert zeile.endswith("- die gepflegte Feinreihe"), zeile

    def test_und_die_tagesreihe_bleibt_die_zulassungsreihe(self) -> None:
        zeile = reihenzeile(self._frame("D"), "D")

        assert zeile.endswith("- die Zulassungsreihe"), zeile

    def test_mit_der_tagesgrenze_waere_die_feinreihe_zu_lang(self) -> None:
        """Die Gegenprobe zum Fund: Der alte Vergleich war wirklich falsch,
        nicht nur theoretisch."""
        roh = self._frame("15")
        bis = roh["BTCUSD_BITSTAMP"]["open_time"].max().date()

        assert bis > SERIENENDE
        assert bis <= letzter_tag("15")
