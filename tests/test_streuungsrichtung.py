"""Die Annahme ist nicht mehr die strengere Zahl - Befund 483.

``research/streuung`` rechnet die eine Eingabe des Deflated Sharpe nach, die
nicht gemessen sondern angenommen wird. Sein Urteil endete bis hierher mit
einem Satz, der das Gate so stehen laesst, wie es steht:

    Eine Streuung, die nur die Mitte kennt, ist zu klein. Sie hier
    einzusetzen wuerde die Huerde mit einem Wert senken, von dem bekannt ist,
    dass er zu niedrig ist. Deshalb bleibt die Annahme stehen - sie ist die
    strengere Richtung.

**Der Satz war richtig und ist es nicht mehr.** Er stand unbedingt da - keine
Bedingung, kein Vergleich -, und die Lage darunter hat sich bewegt:

    Berichte        50 Punkte   sqrt(V) = 0,0394   die Reglerscans
    Verzeichnis     11 Punkte   sqrt(V) = 0,2067   gebuchte Versuche (377)
    zusammen        61 Punkte   sqrt(V) = 0,1072
    Annahme im Gate                       0,0909   bei n_eff 122

Die gemessene Streuung liegt **ueber** der Annahme, und zwar bei jeder
plausiblen Stichprobe (Faktor 1,14 bei n_eff 115 bis 1,34 bei 158). Damit ist
die Annahme die **mildere** Zahl: Das Gate urteilt mit 0,0909 bei DSR 0,5994,
mit der Messung waeren es 0,2794.

Der Modulkopf hat genau das vorhergesagt - *"Die Schaetzung waechst auf die
Annahme zu, solange man Versuche nachtraegt"* -, und dass sie darueber
hinausgewachsen ist, hat kein Text bemerkt. Drei Stellen behaupteten die
Richtung, keine rechnete sie: der Vergleichssatz (*"also 0.8-mal so hoch"* -
ein Satz, der nur mit einem Faktor ueber 1 funktioniert), der
Nicht-verwendbar-Zweig und der Verwendbar-Zweig.

**Am Gate aendert sich nichts.** Welche Zahl dort steht, ist eine Entscheidung
und keine Auswertung, und die Auswahl bleibt zu schmal - das Modul sagt das
selbst, und es gilt weiter. Neu ist, dass die Enge der Auswahl jetzt in
**dieselbe** Richtung zeigt wie die Messung: Wenn schon diese Auswahl ueber
der Annahme liegt, liegt die wahre Streuung eher noch hoeher. Der Fund zeigt
also in die strenge Richtung, und deshalb ist er ueberhaupt einer.

Was diese Datei prueft
----------------------
Nicht die Zahl - die bewegt sich mit jedem gebuchten Versuch. Sondern dass
**kein Satz die Richtung behauptet, ohne sie zu rechnen**, und dass beide
Richtungen den jeweils richtigen Satz erzeugen. Eine Wache, die nur die
heutige Richtung festnagelt, wuerde beim naechsten Kippen genauso stumm
bleiben wie die, die es diesmal war.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.streuung import Streuung, Versuchspunkt

WURZEL = Path(__file__).resolve().parents[1]


def _lage(werte: tuple[float, ...], *, stichprobe: int, versuche: int = 203):
    punkte = tuple(
        Versuchspunkt(quelle="Probe", kennung=f"p{i}", sharpe_je_trade=w)
        for i, w in enumerate(werte)
    )
    return Streuung(punkte=punkte, versuche=versuche, stichprobe=stichprobe)


#: Zwei gebaute Lagen, je eine Richtung. Die Werte sind so gewaehlt, dass die
#: Streuung weit von der Annahme liegt - ein Grenzfall wuerde hier nur
#: Rauschen pruefen.
ENG = (0.20, 0.21, 0.22, 0.23)
BREIT = (-0.40, 0.00, 0.30, 0.60)


class TestDieRichtungWirdGerechnet:
    def test_eng_heisst_die_annahme_ist_strenger(self) -> None:
        lage = _lage(ENG, stichprobe=122)

        assert lage.gemessen is not None
        assert lage.gemessen < lage.angenommen
        assert lage.richtung == -1

    def test_breit_heisst_die_annahme_ist_milder(self) -> None:
        lage = _lage(BREIT, stichprobe=122)

        assert lage.gemessen > lage.angenommen
        assert lage.richtung == 1

    def test_ohne_messung_gibt_es_keine_richtung(self) -> None:
        """``None`` und nicht ``0``: "keine Richtung" ist etwas anderes als
        "gleich gross"."""
        assert _lage((0.2,), stichprobe=122).richtung is None

    def test_und_ohne_stichprobe_auch_nicht(self) -> None:
        assert _lage(ENG, stichprobe=1).richtung is None


class TestDasUrteilNenntDieRichtung:
    def test_bei_enger_messung_sagt_es_senken(self) -> None:
        text = _lage(ENG, stichprobe=122).urteil()

        assert "**senken**" in text
        assert "strengere Richtung" in text

    def test_bei_breiter_messung_sagt_es_heben(self) -> None:
        """**Der Satz, der bis 483 nie erschien**, obwohl die Lage ihn seit
        dem Verzeichnis verlangt."""
        text = _lage(BREIT, stichprobe=122).urteil()

        assert "**heben**" in text
        assert "**mildere**" in text
        assert "nicht die strengere" in text

    def test_und_niemals_beide(self) -> None:
        for werte in (ENG, BREIT):
            text = _lage(werte, stichprobe=122).urteil()

            assert ("**senken**" in text) != ("**heben**" in text), werte

    def test_der_vergleichssatz_benennt_die_seite(self) -> None:
        """Hier stand "also 0.8-mal so hoch" - ein Satz, der nur mit einem
        Faktor ueber 1 funktioniert. Gedruckt stand er trotzdem."""
        eng = _lage(ENG, stichprobe=122).urteil()
        breit = _lage(BREIT, stichprobe=122).urteil()

        assert "darueber" in eng
        assert "darunter" in breit

    def test_auch_der_verwendbare_zweig_nennt_sie(self) -> None:
        """Dort stand "ersetzen senkt die Huerde", ebenfalls unbedingt. Der
        Zweig ist heute nicht erreichbar - die Abdeckung liegt bei 30 % -,
        und genau deshalb faellt so etwas dort nicht auf."""
        lage = _lage(BREIT, stichprobe=122, versuche=4)

        assert lage.verwendbar, lage.abdeckung
        assert "**heben**" in lage.urteil()


class TestKeinSatzBehauptetDieRichtungUnbedingt:
    """Die eigentliche Wache. Eine Zahl festzunageln haette diesmal nichts
    geholfen - der Fehler war ein Satz ohne Bedingung."""

    #: Wendungen, die eine Richtung festlegen. Wer eine davon schreibt, muss
    #: ``richtung`` gefragt haben.
    GERICHTET: tuple[str, ...] = (
        "strengere Richtung",
        "senkt die Huerde",
        "senken",
        "heben",
        "mildere",
    )

    def test_sie_stehen_nur_im_richtungssatz(self) -> None:
        """Gemessen: Alle gerichteten Wendungen des Urteils stehen in
        ``_richtungssatz``, und der fragt ``self.richtung``.
        """
        import ast

        quelle = (WURZEL / "research/streuung.py").read_text(encoding="utf-8")
        baum = ast.parse(quelle)
        rumpf = {
            n.name: ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
        }

        assert "richtung" in rumpf["_richtungssatz"]
        fremd = [
            name
            for name, text in rumpf.items()
            if name not in {"_richtungssatz", "richtung"}
            and any(w in text for w in ("strengere Richtung", "senkt die Huerde"))
        ]

        assert fremd == [], (
            "behauptet eine Richtung ausserhalb von '_richtungssatz' - genau "
            f"so stand der Fehler von 483 drei Stellen lang da: {fremd}"
        )

    def test_der_richtungssatz_haengt_wirklich_an_der_richtung(self) -> None:
        """Die Gegenprobe zur Zusicherung darueber: Wuerde
        ``_richtungssatz`` die Richtung ignorieren, kaeme fuer beide Lagen
        dasselbe heraus."""
        eng = _lage(ENG, stichprobe=122)._richtungssatz()
        breit = _lage(BREIT, stichprobe=122)._richtungssatz()

        assert eng != breit
        assert eng and breit


@pytest.mark.daten
class TestAnDenEchtenZahlen:
    """Am Bestand gemessen, nicht an gebauten Werten - und als Daten, weil es
    die Berichte und das Verzeichnis dieses Containers braucht."""

    def _echte_lage(self):
        from research.streuung import sammle

        punkte = sammle(
            berichte=WURZEL / "reports",
            bestenliste=WURZEL / "state/leaderboard.json",
            verzeichnis=WURZEL / "state/trials.json",
        )
        if len(punkte) < 2:
            pytest.skip("zu wenige Punkte auf der Platte")
        return Streuung(punkte=tuple(punkte), versuche=203, stichprobe=122)

    def test_die_messung_liegt_heute_ueber_der_annahme(self) -> None:
        """**Der Fund selbst.** Kippt das zurueck, ist dieser Test rot und
        jemand sieht hin - statt dass ein Satz weiter das Gegenteil sagt."""
        lage = self._echte_lage()

        assert lage.richtung == 1, (
            f"gemessen {lage.gemessen:.4f} gegen angenommen "
            f"{lage.angenommen:.4f} - die Richtung ist zurueckgekippt, und "
            f"die Texte von Befund 483 gehoeren nachgelesen"
        )

    def test_und_das_verzeichnis_ist_der_grund(self) -> None:
        """Die Berichte allein lagen darunter - deshalb war der alte Satz
        richtig, als er geschrieben wurde."""
        lage = self._echte_lage()
        je_quelle = lage.je_quelle()
        berichte = je_quelle.get("Berichte")
        verzeichnis = je_quelle.get("Verzeichnis")
        if berichte is None or verzeichnis is None:
            pytest.skip("beide Quellen noetig")

        assert berichte[1] < lage.angenommen
        assert verzeichnis[1] > lage.angenommen

    def test_nicht_verwendbar_bleibt_es_trotzdem(self) -> None:
        """Die Richtung aendert nichts an der Abdeckung - und damit nichts am
        Gate. Wer das verwechselt, hat aus einem Fund eine Lockerung
        gemacht."""
        lage = self._echte_lage()

        assert not lage.verwendbar
        assert lage.abdeckung < 0.9
