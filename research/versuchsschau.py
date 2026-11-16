"""Was bereits gemessen wurde - aus dem Versuchsverzeichnis - Befund 497.

Der Abschnitt stand auf einer Datei, die es nicht gibt
------------------------------------------------------
``analyst.build_prompt`` fuehrt einen Abschnitt "Was bereits versucht wurde",
und sein Modulkopf nennt den Zweck: *"Enthaelt bewusst die Fehlschlaege mit
Zahlen, nicht nur die Namen der gescheiterten Kandidaten. 'Am
Kosten-Stresstest gescheitert, Profitfaktor 1,08 gegen Schwelle 1,20' laesst
sich gezielt angehen; 'hat nicht bestanden' nicht."*

Gefuellt wird er aus ``state/journal.json``. Diese Datei **existiert nicht**,
und der Abschnitt sagt das selbst:

    Das Research-Journal ist leer, aber **203 Versuche sind gezaehlt.** Dies
    ist nicht die erste Generation - die Nachweise liegen in einem anderen
    Verzeichnis und stehen nicht vollstaendig hier.

Der zweite Satz ist in diesem Container **falsch**. Die Nachweise liegen nicht
in einem anderen Verzeichnis, sondern in ``state/trials.json`` - derselben
Datei, aus der der Zaehler seine 203 nimmt, und die zu elf Versuchen Kennung,
Trades, Sharpe je Trade und Herkunft fuehrt. Gemessen:

    Zaehler       203
    mit Eintrag    11
    Grundstock    192

Die elf enthalten die aufschlussreichsten Zahlen, die das Projekt hat: vier
negative Sharpes je Trade (-0,12 bis -0,19) auf Regeln, die plausibel
klangen. Genau solche Zeilen sind der Grund, warum der Abschnitt existiert -
und der Analyst hat sie nie gesehen.

Was hier gebaut wird
--------------------
``als_auftrag`` macht aus dem Verzeichnis den Abschnitt. Dieselbe Bauart wie
``auftragslage.als_auftrag``, ``ausschluss.als_auftrag`` und
``auftragstakt.als_auftrag``: Das Modul, dem die Zahlen gehoeren, schreibt
den Satz dazu - nicht der Prompt-Bauer.

**Leer, wenn nichts gebucht ist.** Dann bleibt der Auftrag der von vorher; ein
Abschnitt mit einer Ueberschrift und ohne Zeilen sieht aus wie eine Auskunft
und ist keine.

Was der Abschnitt **nicht** tut
-------------------------------
Er fuettert **nicht** den Doppelgaengerfilter. Der vergleicht ``genome_id`` -
einen Inhaltshash wie ``66e04da1281c8cd1`` -, und das Verzeichnis fuehrt
Kennungen wie "Enge vor Bewegung". Ein Name ist keine Kennung im Sinne des
Filters, und ihn dafuer zu nehmen waere geraten. Der Filter bleibt, wie er
ist; dieser Abschnitt ist eine **Auskunft**, keine Sperre.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from research.versuche import Verzeichnis

#: Wie viele Zeilen hoechstens in den Auftrag gehen.
#:
#: Elf sind es heute. Waechst das Verzeichnis, bleibt der Abschnitt lesbar,
#: indem er die Raender zeigt - die besten und die schlechtesten. Die Mitte
#: ist die, aus der man am wenigsten lernt.
HOECHSTENS = 30


def als_auftrag(verzeichnis: Verzeichnis) -> str:
    """Der Abschnitt, der in den Prompt gehoert. Leer, wenn nichts gebucht ist."""
    eintraege = [e for e in verzeichnis.eintraege if e.sharpe_je_trade is not None]
    if not eintraege:
        return ""

    nach_guete = sorted(eintraege, key=lambda e: e.sharpe_je_trade, reverse=True)
    gezeigt = nach_guete
    vermerk = ""
    if len(nach_guete) > HOECHSTENS:
        haelfte = HOECHSTENS // 2
        gezeigt = nach_guete[:haelfte] + nach_guete[-haelfte:]
        vermerk = (
            f" Gezeigt sind die {haelfte} besten und die {haelfte} "
            f"schlechtesten von {len(nach_guete)}; die Mitte ist die, aus "
            f"der am wenigsten zu lernen ist."
        )

    ohne = verzeichnis.anzahl - verzeichnis.belegt
    zeilen = [
        "## Was bereits gemessen wurde\n",
        f"Der Versuchszaehler steht bei **{verzeichnis.anzahl}**. Davon "
        f"haben **{verzeichnis.belegt}** einen Eintrag mit Zahlen; die "
        f"uebrigen {ohne} sind der Grundstock aus der Zeit vor dem "
        f"Verzeichnis und stehen nur als Zahl da.{vermerk}",
        "",
        "    Sharpe/Trade  Trades  Herkunft              Regel",
    ]
    for e in gezeigt:
        zeilen.append(
            f"    {e.sharpe_je_trade:>12.4f} {e.trades:>7} "
            f"{(e.herkunft or '-'):<21.21} {e.kennung}"
        )
    schlechteste = nach_guete[-1]
    zeilen += [
        "",
        "**Die negativen Zeilen sind das Wertvollste daran.** Sie sind "
        "gemessen, und sie kosten keinen Versuch mehr: "
        f"'{schlechteste.kennung}' hat {schlechteste.trades} Trades zu je "
        f"{schlechteste.sharpe_je_trade:.4f} gebracht. Eine Regel, die "
        "derselben Idee folgt, ist damit nicht offen, sondern erledigt.",
        "",
        "Das ist **keine Sperrliste**: Der Doppelgaengerfilter vergleicht "
        "Inhaltshashes, nicht Namen. Wer hier etwas wiederholt, bezahlt es "
        "mit einem Versuch.",
        "",
    ]
    return "\n".join(zeilen)
