"""Was das fehlende ``-m`` kostet, stand zweimal halb so hoch - Befund 471.

Vier Stellen in ``cli.py`` vergleichen ein Bein mit dem Zulassungskorb. Zwei
nannten fuer den Korb **7 von 11**, zwei **9 von 11**. Gemessen ist 9: der
eigene Bericht ``reports/marktkombinationen`` fuehrt BTC allein mit 5 von 11
und BTC + ETH mit 9 von 11, am Betriebspunkt "Spot (kein Hebel, kein
Funding)", 1d, 203 Versuche.

Die 7 ist nicht erfunden - sie ist **derselbe Korb am Perpetual-Punkt**
(Befund 106). Genau daran liegt der Fehler: Eine Gate-Zahl ohne ihren
Betriebspunkt laesst sich gegen die falsche Leiter lesen, und keine der vier
Stellen nannte ihren Punkt. Dadurch kostete das fehlende ``-m`` scheinbar
zwei Gates statt vier - in der Hilfe des Befehls, der seine Versuche
unwiderruflich bucht.

**Warum hier der Rohtext geprueft wird und nicht der Rumpf.** Befund 399
verlangt, Zusicherungen am Rumpf zu pruefen, damit Prosa sie nicht erfuellt.
Hier ist die Prosa der Gegenstand: Die falschen Zahlen standen in einem
Hilfetext und in einem Kommentar. Geprueft wird also genau das, was ein
Mensch liest.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
QUELLE = (WURZEL / "cli.py").read_text(encoding="utf-8")
BERICHTE = WURZEL / "reports" / "marktkombinationen"

#: Woran eine Stelle als Ein-Bein-Vergleich zu erkennen ist.
ANKER = "BTC allein"

#: Woerter, von denen mindestens eines den Betriebspunkt benennt.
PUNKTWORTE = ("Kassa", "Spot", "Perpetual", "Betriebspunkt")


@dataclass(frozen=True, slots=True)
class Stelle:
    zeile: int
    fenster: str

    @property
    def nennt_den_korbwert(self) -> bool:
        return "9 von 11" in self.fenster

    @property
    def nennt_die_perpetualzahl(self) -> bool:
        return "7 von 11" in self.fenster

    @property
    def nennt_den_punkt(self) -> bool:
        return any(w in self.fenster for w in PUNKTWORTE)


def stellen(text: str, *, breite: int = 4) -> tuple[Stelle, ...]:
    """Jede Stelle mit ``BTC allein``, mit ihrem Umfeld.

    Das Fenster ist bewusst gross: Die Zahl kann eine Zeile unter dem Anker
    stehen, und in einem umgebrochenen Hilfetext tut sie das auch.
    """
    zeilen = text.splitlines()
    gefunden = []
    for i, z in enumerate(zeilen):
        if ANKER not in z:
            continue
        fenster = " ".join(
            x.strip() for x in zeilen[max(0, i - breite) : i + breite + 1]
        )
        gefunden.append(Stelle(zeile=i + 1, fenster=re.sub(r"\s+", " ", fenster)))
    return tuple(gefunden)


STELLEN = stellen(QUELLE)


def gemessenes_paar() -> tuple[dict, dict, dict] | None:
    """BTC und BTC+ETH aus dem neuesten Kombinationsbericht."""
    dateien = sorted(BERICHTE.glob("*.json")) if BERICHTE.is_dir() else []
    if not dateien:
        return None
    daten = json.loads(dateien[-1].read_text(encoding="utf-8"))
    nach_namen = {k["maerkte"]: k for k in daten.get("kombinationen", ())}
    if "BTC" not in nach_namen or "BTC+ETH" not in nach_namen:
        return None
    return nach_namen["BTC"], nach_namen["BTC+ETH"], daten


class TestDerMelderTaugt:
    """Erst der Melder. Eine Zaehlung ohne Gegenprobe hat in dieser Sitzung
    zehn Mal zu viel oder das Falsche gemeldet."""

    def test_er_findet_die_stellen(self) -> None:
        assert len(STELLEN) >= 3, [s.zeile for s in STELLEN]

    def test_er_erkennt_die_alte_fassung_als_falsch(self) -> None:
        schlecht = stellen(
            "der Spitzenkandidat steht auf BTC allein bei\n"
            "5 von 11, auf BTC + ETH bei 7 von 11."
        )

        assert len(schlecht) == 1
        assert schlecht[0].nennt_die_perpetualzahl
        assert not schlecht[0].nennt_den_korbwert
        assert not schlecht[0].nennt_den_punkt

    def test_und_die_neue_als_richtig(self) -> None:
        gut = stellen(
            "der Spitzenkandidat steht auf BTC allein bei 5 von 11, auf\n"
            "BTC + ETH bei 9 von 11 (Kassa-Punkt, 203 Versuche)."
        )

        assert len(gut) == 1
        assert gut[0].nennt_den_korbwert
        assert gut[0].nennt_den_punkt


class TestJedeStelleNenntDenGemessenenKorbwert:
    def test_keine_nennt_fuer_den_korb_die_perpetualzahl_allein(self) -> None:
        """Die Regel: Wo ein Bein gegen den Korb steht, gehoert die 9 hin.
        Die 7 darf daneben stehen - aber nur als das, was sie ist.
        """
        schuldig = [
            s.zeile
            for s in STELLEN
            if s.nennt_die_perpetualzahl and not s.nennt_den_korbwert
        ]

        assert schuldig == [], (
            f"Zeilen {schuldig}: '7 von 11' als Korbwert - das ist der "
            f"Perpetual-Punkt (Befund 106), nicht der Kassa-Punkt."
        )

    def test_und_wer_eine_zahl_nennt_nennt_auch_den_punkt(self) -> None:
        """Befund 468 fuer diese Familie: Eine Gate-Zahl ohne Betriebspunkt
        laesst sich gegen die falsche Leiter lesen - und genau so sind die
        zwei Zahlen verwechselt worden."""
        stumm = [
            s.zeile
            for s in STELLEN
            if (s.nennt_den_korbwert or s.nennt_die_perpetualzahl)
            and not s.nennt_den_punkt
        ]

        assert stumm == [], f"Zeilen {stumm}: Gate-Zahl ohne Betriebspunkt"

    def test_es_gibt_solche_stellen_wirklich(self) -> None:
        """Sonst bestehen die zwei Tests darueber leer."""
        mit_zahl = [
            s.zeile
            for s in STELLEN
            if s.nennt_den_korbwert or s.nennt_die_perpetualzahl
        ]

        assert len(mit_zahl) >= 2, mit_zahl


@pytest.mark.daten
class TestGegenDieEigeneMessung:
    """Die Prosa darf nicht von der Messung weglaufen - der Fehler, der hier
    zweimal stand, war genau das."""

    def test_der_bericht_nennt_fuenf_und_neun(self) -> None:
        paar = gemessenes_paar()
        if paar is None:
            pytest.skip("kein Kombinationsbericht im Speicher")
        allein, korb, _ = paar

        assert allein["bestanden"] == 5, allein
        assert korb["bestanden"] == 9, korb
        assert allein["gesamt"] == korb["gesamt"] == 11

    def test_und_der_bericht_steht_am_kassa_punkt(self) -> None:
        """Ohne das waere die Zahl nicht die, die in den Text gehoert."""
        paar = gemessenes_paar()
        if paar is None:
            pytest.skip("kein Kombinationsbericht im Speicher")
        _, _, daten = paar

        assert "Spot" in (daten.get("betriebspunkt") or "")
        assert daten.get("intervall") == "1d"

    def test_die_dsr_zahlen_im_kommentar_stimmen_mit_dem_bericht(self) -> None:
        """Der Kommentar nannte 0,190 und 0,843 - Staende von vor den
        heutigen Versuchen. Wer eine Zahl abschreibt, muss sie wiederfinden
        koennen."""
        paar = gemessenes_paar()
        if paar is None:
            pytest.skip("kein Kombinationsbericht im Speicher")
        allein, korb, _ = paar

        for wert in (allein["dsr"], korb["dsr"]):
            deutsch = f"{wert:.4f}".replace(".", ",")
            assert deutsch in QUELLE, (
                f"DSR {deutsch} aus dem Bericht steht nicht in cli.py - "
                f"dort stehen also andere Zahlen als die gemessenen."
            )
