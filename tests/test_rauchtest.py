"""Welche Befehle darf ein Rauchtest laufen lassen - und welche nie?

**Befund 247.** Befund 103 hat einen Befehl gefunden, der mit seinen eigenen
Voreinstellungen abbrach. Der Rauchtest, der ihn fand, hat 21 Versuche
gekostet (Befund 104), weil zwanzig Befehle beim Messen mitzaehlen. Daraufhin
entstand ``TRADING_TROCKENLAUF``.

Seither ist der Rauchtest nie wiederholt worden - das Werkzeug war da, der Lauf
nicht. Nachgeholt: **52 Befehle mit ihren Voreinstellungen, keiner mit einem
Traceback, der Zaehler unveraendert bei 198.** Die drei mit Exit ungleich null
lehnen sauber ab und sagen, was fehlt:

    quelle     "Keine Bestenliste vorhanden ... 'cli wettbewerb' legt sie an"
    review     "Noch keine abgeschlossenen Trades"
    vorschlag  "Kein LLM__ANTHROPIC_API_KEY ... oder mit --datei"

Damit ist beides bestaetigt: die Lehre aus 103 haelt, und die Wache aus 104
macht ihre Ueberpruefung kostenlos.

Warum diese Datei bleibt
------------------------
Nicht wegen des Ergebnisses - es war sauber. Sondern wegen der **Frage, die
vorher zu beantworten war**: Welche Befehle darf man dafuer ueberhaupt
starten? ``cli trade`` stellt Orders, ``cli setup`` schreibt Zugangsdaten,
``cli backfill`` laedt an einer Boerse. Ein Rauchtest, der die Liste falsch
zieht, ist teurer als der Fehler, den er sucht.

Die Antwort steht hier als Daten, damit der naechste Lauf sie nicht neu raten
muss - und ein **neuer** Befehl faellt auf, statt stillschweigend als harmlos
zu gelten. Das ist die Richtung, in der ein Irrtum billig bleibt.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

#: Befehle, die auf etwas ausserhalb dieses Behaelters wirken - mit dem Grund.
#:
#: **Im Zweifel hierher.** Ein Befehl, der faelschlich hier steht, wird nicht
#: rauchgetestet; einer, der faelschlich fehlt, stellt womoeglich eine Order.
WIRKT_NACH_AUSSEN: dict[str, str] = {
    "abgleich": "vergleicht gegen die Boerse",
    "adaptiv": "schreibt den Versuchszaehler",
    "anlagentest": "schreibt ein Genom",
    "backfill": "laedt an der Boerse",
    "dashboard": "startet einen Dienst",
    "funding": "laedt an der Boerse",
    "healthcheck": "fragt das Konto ab",
    "ingest": "schreibt Live-Kerzen mit",
    "korb": "schreibt den Versuchszaehler",
    "landschaft": "schreibt den Versuchszaehler",
    "machbarkeit": "schreibt den Versuchszaehler",
    "research": "schreibt den Versuchszaehler",
    "setup": "schreibt Zugangsdaten",
    "termine": "laedt aus dem Netz",
    "trade": "stellt Orders",
    "verbund": "schreibt den Versuchszaehler",
    "wettbewerb": "schreibt den Versuchszaehler",
}

#: Die Befehle, die ein Rauchtest starten darf - **einzeln aufgezaehlt.**
#:
#: Nicht als "alles Uebrige" gerechnet: Dann waere die Einteilung vollstaendig
#: per Konstruktion, der Test tautologisch, und ein neuer Befehl faende sich
#: stillschweigend auf der harmlosen Seite wieder. Genau die Richtung, in der
#: ein Irrtum teuer wird.
HARMLOS: frozenset[str] = frozenset({
    "abstand", "anwaerter", "aufloesung", "betriebspunkt",
    "decke", "duerre", "evidenz", "finanzierung",
    "form", "front", "gatemuster", "haelften",
    "holdout", "instrument", "jahresbild", "koernung",
    "konfluenz", "kontorisiko", "kosten", "leverage",
    "marktkombinationen", "nachpruefung", "nullprobe", "paare",
    "partner", "phasen", "plateaubild", "quality",
    "quelle", "rangprobe", "referenz", "register",
    "regler", "rennen", "review", "scan",
    "schock", "sperrprobe", "stand", "status",
    "streuung", "suchbudget", "tageszeit", "taktung",
    "teststaerke", "trennschaerfe", "verbundmodell", "vereinbar",
    "vorratsdecke", "vorschlag", "zeitachse", "zufallseinstieg",
})

#: Was der Lauf ergeben hat - als Zahl, damit ein spaeterer Lauf sich daran
#: messen kann.
GELAUFEN = 52
TRACEBACKS = 0
SAUBER_ABGELEHNT = ("quelle", "review", "vorschlag")


def _befehle() -> set[str]:
    baum = ast.parse(Path("cli.py").read_text())
    namen = set()
    for n in ast.walk(baum):
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                if "app.command" in ast.unparse(d):
                    treffer = re.search(r'"([^"]+)"', ast.unparse(d))
                    namen.add(treffer.group(1) if treffer else n.name)
    return namen


class TestDieEinteilungIstVollstaendig:
    def test_jeder_befehl_ist_eingeteilt(self) -> None:
        """**Die Wache.** Ein neuer Befehl zwingt zu der Frage.

        Sie faellt in der sicheren Richtung aus: Unbekannt ist ein Fehler,
        nicht stillschweigend harmlos. Wer einen Befehl baut, der Orders
        stellt oder an einer Boerse laedt, traegt ihn hier ein - oder dieser
        Test faellt, bevor ihn ein Rauchtest startet.
        """
        unbekannt = sorted(_befehle() - set(WIRKT_NACH_AUSSEN) - HARMLOS)

        assert unbekannt == [], (
            f"nicht eingeteilt: {unbekannt} - gehoert der Befehl nach "
            f"WIRKT_NACH_AUSSEN, oder ist er harmlos?"
        )

    def test_die_liste_nennt_keine_befehle_die_es_nicht_gibt(self) -> None:
        verwaist = sorted(set(WIRKT_NACH_AUSSEN) - _befehle())

        assert verwaist == [], f"steht in der Liste, gibt es nicht: {verwaist}"

    def test_jeder_eintrag_nennt_seinen_grund(self) -> None:
        for name, grund in WIRKT_NACH_AUSSEN.items():
            assert grund.strip(), name

    def test_die_zaehlenden_befehle_stehen_alle_drin(self) -> None:
        """Sie sind der teure Teil: Jeder Versuch hebt die Huerde dauerhaft.

        Gelesen wird die Menge aus dem Quelltext, nicht aus einer zweiten
        Liste - sonst waeren es wieder zwei Wahrheiten (Befund 234).
        """
        baum = ast.parse(Path("cli.py").read_text())
        zaehlend = {
            n.name
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
            and not n.name.startswith("_")
            and "save_trials" in ast.unparse(n)
        }

        assert zaehlend <= set(WIRKT_NACH_AUSSEN), (
            f"schreibt den Zaehler, steht aber nicht in WIRKT_NACH_AUSSEN: "
            f"{sorted(zaehlend - set(WIRKT_NACH_AUSSEN))}"
        )


class TestWasDerLaufErgebenHat:
    def test_die_sauber_ablehnenden_gibt_es_noch(self) -> None:
        """Sie lehnen ab und sagen, was fehlt - das ist die Lehre aus 103,
        nicht ihr Gegenteil."""
        vorhanden = _befehle()

        for name in SAUBER_ABGELEHNT:
            assert name in vorhanden, name

    def test_der_lauf_deckte_die_harmlosen_ab(self) -> None:
        assert len(HARMLOS) == GELAUFEN

    def test_keine_seite_nennt_dieselbe_sache_zweimal(self) -> None:
        """Ein Befehl auf beiden Listen waere eine Einteilung, die nichts
        einteilt."""
        assert not (HARMLOS & set(WIRKT_NACH_AUSSEN))

    def test_die_harmlose_liste_nennt_keine_gespenster(self) -> None:
        verwaist = sorted(HARMLOS - _befehle())

        assert verwaist == [], f"harmlos genannt, gibt es nicht: {verwaist}"

    def test_kein_traceback(self) -> None:
        """Die Zahl steht hier, damit ein spaeterer Lauf sich daran misst."""
        assert TRACEBACKS == 0
