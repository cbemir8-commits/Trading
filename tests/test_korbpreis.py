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

**Befund 472 hat die Regel verallgemeinert.** Die Wache von 471 sah nur
``cli.py`` und nur das Umfeld von "BTC allein" - und uebersah damit, dass
dasselbe Paar (5 von 11 bei 0,190 gegen 7 von 11 bei 0,843) in
``research/admission.py`` stand, also dort, wo es herkommt. Dazu kam
``research/seeds.py``: Im Docstring des Spitzenkandidaten selbst standen
13,47 % und 7 von 11 - das Perpetual-Tripel - ohne ihren Punkt, waehrend am
Spot-Punkt 14,83 % und 9 von 11 gelten.

Jetzt gilt die Regel fuer ``cli.py`` und ganz ``research/``: Wer eine
Aufstellung beim Namen nennt, nennt entweder die gemessene Zahl oder seinen
Betriebspunkt. Gemessen ohne eine einzige Ausnahme erfuellbar - 23 Stellen,
null Verstoesse.
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


# ---------------------------------------------------------------------------
#  Befund 472: dieselbe Regel fuer jede benannte Aufstellung
# ---------------------------------------------------------------------------

#: Schreibweise in der Prosa -> Schluessel im Kombinationsbericht.
#:
#: Absichtlich **nur** ausdrueckliche Marktnennungen. "dem Korb" stand hier im
#: ersten Entwurf mit drin und traf damit einen Registereintrag, in dem "3
#: statt 2 von 11" eine Leiterzeile ist und kein Korbwert - ein Melder, der
#: das falsche Ding findet, ist schlimmer als keiner.
SCHREIBWEISEN: tuple[tuple[str, str], ...] = (
    ("BTC + ETH + LTC + XRP", "BTC+ETH+LTC+XRP"),
    ("BTC+ETH+LTC+XRP", "BTC+ETH+LTC+XRP"),
    ("BTC + ETH + XRP", "BTC+ETH+XRP"),
    ("BTC + ETH + LTC", "BTC+ETH+LTC"),
    ("BTC + ETH", "BTC+ETH"),
    ("BTC+ETH", "BTC+ETH"),
    ("BTC allein", "BTC"),
    ("ETH allein", "ETH"),
)

GATEZAHL = re.compile(r"(\d+) von 11")


def geprueft_werden() -> tuple[Path, ...]:
    return (WURZEL / "cli.py", *sorted((WURZEL / "research").glob("*.py")))


@dataclass(frozen=True, slots=True)
class Aussage:
    datei: str
    zeile: int
    aufstellung: str
    zahlen: frozenset[int]
    nennt_punkt: bool


def aussagen(text: str, datei: str, *, breite: int = 3) -> tuple[Aussage, ...]:
    """Jede ``N von 11``-Aussage, die eine Aufstellung beim Namen nennt."""
    zeilen = text.splitlines()
    gefunden = []
    for i, z in enumerate(zeilen):
        if "von 11" not in z:
            continue
        fenster = re.sub(
            r"\s+", " ", " ".join(x.strip() for x in zeilen[max(0, i - breite) : i + breite + 1])
        )
        schluessel = next((s for p, s in SCHREIBWEISEN if p in fenster), None)
        if schluessel is None:
            continue
        gefunden.append(
            Aussage(
                datei=datei,
                zeile=i + 1,
                aufstellung=schluessel,
                zahlen=frozenset(int(x) for x in GATEZAHL.findall(fenster)),
                nennt_punkt=any(w in fenster for w in PUNKTWORTE),
            )
        )
    return tuple(gefunden)


ALLE_AUSSAGEN = tuple(
    a
    for datei in geprueft_werden()
    for a in aussagen(datei.read_text(encoding="utf-8"), datei.name)
)


class TestDerMelderDerZweitenRegel:
    def test_er_findet_genug_stellen(self) -> None:
        """Sonst besteht die Regel darunter leer."""
        assert len(ALLE_AUSSAGEN) >= 10, [
            (a.datei, a.zeile) for a in ALLE_AUSSAGEN
        ]

    def test_er_erkennt_die_alte_fassung_aus_admission(self) -> None:
        """Genau die zwei Zeilen, die 471 uebersehen hat."""
        alt = aussagen(
            "Spitzenkandidat auf BTC allein     5 von 11, Deflated Sharpe 0,190\n"
            "Spitzenkandidat auf BTC + ETH      7 von 11, Deflated Sharpe 0,843",
            "probe.py",
        )

        assert alt, "der Melder sieht die alte Fassung nicht"
        assert all(not a.nennt_punkt for a in alt)
        assert any(7 in a.zahlen and 9 not in a.zahlen for a in alt)

    def test_aber_nicht_eine_leiterzeile_am_wort_korb(self) -> None:
        """Die Gegenprobe gegen den eigenen ersten Entwurf: 'dem Korb' allein
        darf keine Aufstellung sein."""
        leiter = aussagen(
            "die unterste Zeile bei 3 statt 2 von 11 - die Messlatte auf "
            "einem Bein statt auf dem Korb zu messen bewegt sie kaum",
            "probe.py",
        )

        assert leiter == ()


@pytest.mark.daten
class TestJedeBenannteAufstellung:
    def test_nennt_die_gemessene_zahl_oder_ihren_punkt(self) -> None:
        """**Die Regel von Befund 472.**

        Eine abweichende Zahl ist nicht falsch - sie kann ein anderer
        Betriebspunkt sein (Perpetual 7 gegen Kassa 9 auf demselben Korb).
        Falsch ist eine abweichende Zahl **ohne** ihren Punkt: Dann liest sie
        sich gegen die falsche Leiter.
        """
        paar = gemessenes_paar()
        if paar is None:
            pytest.skip("kein Kombinationsbericht im Speicher")
        _, _, daten = paar
        gemessen = {k["maerkte"]: k["bestanden"] for k in daten["kombinationen"]}

        schuldig = [
            f"{a.datei}:{a.zeile} ({a.aufstellung}: gemessen "
            f"{gemessen[a.aufstellung]}, im Text {sorted(a.zahlen)})"
            for a in ALLE_AUSSAGEN
            if a.aufstellung in gemessen
            and gemessen[a.aufstellung] not in a.zahlen
            and not a.nennt_punkt
        ]

        assert schuldig == [], (
            "Gate-Zahl weicht vom gemessenen Bericht ab und nennt keinen "
            f"Betriebspunkt: {schuldig}"
        )

    def test_und_die_aufstellungen_kommen_im_bericht_vor(self) -> None:
        """Sonst prueft die Regel an einer Schreibweise vorbei, die der
        Bericht gar nicht kennt."""
        paar = gemessenes_paar()
        if paar is None:
            pytest.skip("kein Kombinationsbericht im Speicher")
        _, _, daten = paar
        bekannt = {k["maerkte"] for k in daten["kombinationen"]}

        assert {s for _, s in SCHREIBWEISEN} <= bekannt
