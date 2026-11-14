"""Welche Befehle darf ein Rauchtest laufen lassen - und welche nie?

**Befund 247.** Befund 103 hat einen Befehl gefunden, der mit seinen eigenen
Voreinstellungen abbrach. Der Rauchtest, der ihn fand, hat 21 Versuche
gekostet (Befund 104), weil zwanzig Befehle beim Messen mitzaehlen. Daraufhin
entstand ``TRADING_TROCKENLAUF``.

Bis dahin war der Rauchtest nie wiederholt worden - das Werkzeug war da, der
Lauf nicht. Nachgeholt: **52 Befehle mit ihren Voreinstellungen, keiner mit
einem Traceback, der Zaehler unveraendert bei 198.** Die drei mit Exit
ungleich null lehnen sauber ab und sagen, was fehlt:

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

Der zweite ganze Lauf - Befund 473
----------------------------------
Zwischen 247 und hier ist die Liste **gepflegt**, aber nie wieder ganz
**gefahren** worden: Jeder neue Befehl wurde einzeln gefahren (355, 400, 425,
459), die urspruenglichen 52 nicht erneut. Dieser Kopf sagte das selbst, und
130 Befunde lang hat es niemand nachgeholt.

Nachgeholt, alle 58 mit ``TRADING_TROCKENLAUF=1``:

* **Einer bricht ab**: ``cli instrument`` mit ``InvalidOperation`` - seit
  Befund 377, also 95 Befunde lang. Die Stelle und der Grund stehen in
  ``tests/test_befehlslauf_instrument.py``; behoben und nachgefahren.
* Die drei sauberen Ablehnungen von 247 sagen weiter dasselbe.
* ``nachgesehen`` verlangt sein Argument (Exit 2, Nutzungshinweis) - richtig,
  aber mit Voreinstellungen nicht fahrbar; es stand nie unter den sauberen
  Ablehnungen, weil es zu 425 mit Argument gefahren wurde.
* ``scan`` und ``sperrprobe`` laufen laenger als die Zeit, die ich ihnen gab
  (4,5 bzw. 9,5 Minuten), ohne Fehler - **nicht zu Ende gemessen**, und das
  steht hier so, statt sie als sauber zu zaehlen.
* Der Versuchszaehler stand vor und nach allen Laeufen bei **203**.

Die Lehre ist dieselbe wie bei 425 und steht dort schon: Tests, die nur das
Modul fragen, sehen so etwas nicht. Deshalb faehrt seit 473 eine Wache den
Befehl selbst.

Und der Lauf hat den Speicher veraendert - Befund 474
-----------------------------------------------------
Derselbe Lauf hat etwas angerichtet, und das gehoert hierher und nicht in
eine Fussnote: ``cli referenz`` stand unter ``HARMLOS``, **laedt aber an der
Boerse und schreibt den Kerzenspeicher**. Seine Option ``--bis`` hat die
Vorgabe *"jetzt"*.

Gemessen an den Zeitstempeln: Die Parquet-Dateien ``2026-10`` und ``2026-11``
der Viertelstundenreihe wurden um 03:20:57 und 03:20:58 geschrieben,
``cli referenz`` lief um 03:20:58. Danach lief die BTC-Feinreihe bis **heute**
statt bis zum Pin - 232.334 statt 229.728 Balken. Damit war

* ``speicher_ist_gepinnt`` **falsch**,
* ``erwartete_ausfaelle(stand)`` **leer** - also die Grundlage des
  Commit-Gates weg, und
* ``test_randprobe`` rot: Die Messung von Befund 431 haelt auf der laengeren
  Reihe in 0 von 11 Raendern statt in 5.

Wiederhergestellt: ``2026-11.parquet`` entfernt, ``2026-10.parquet`` auf
``open_time < 2026-10-18`` gekuerzt. Danach wieder 229.728 Balken bis
2026-10-17 - auf den Balken genau der Stand aus ``GEPINNT`` -, Pin haelt, die
drei erwarteten Ausfaelle sind zurueck.

``referenz`` steht seit 474 in ``WIRKT_NACH_AUSSEN``, und eine Wache haelt
die Regel fest, die das gefunden haette: **Kein Befehl unter ``HARMLOS``
verwendet einen schreibenden Einstiegspunkt.** Der Kopf dieser Datei sagte es
die ganze Zeit - *"Im Zweifel hierher"* -, nur stand es nirgends als Test.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.zaehlerwege import zaehlende_befehle

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
    # **Befund 474.** Stand bis dahin unter HARMLOS - und hat beim Rauchtest
    # zu 473 die Viertelstundenreihe von 229.728 auf 232.334 Balken
    # verlaengert, bis **heute** statt bis zum Pin. Seine Option 'bis' hat
    # die Vorgabe "jetzt", und 'backfill_reference' schreibt den Speicher.
    # Damit war der gepinnte Stand weg, auf dem jede gepflegte Zahl steht.
    "referenz": "laedt an der Boerse und schreibt den Kerzenspeicher",
    "research": "schreibt den Zaehler und committet einen Bericht",
    "setup": "schreibt Zugangsdaten",
    "termine": "laedt aus dem Netz",
    "trade": "stellt Orders",
    "verbund": "schreibt den Versuchszaehler",
    "wettbewerb": "schreibt Zaehler, Bestenliste und Bericht - und pusht",
}

#: Die Befehle, die ein Rauchtest starten darf - **einzeln aufgezaehlt.**
#:
#: Nicht als "alles Uebrige" gerechnet: Dann waere die Einteilung vollstaendig
#: per Konstruktion, der Test tautologisch, und ein neuer Befehl faende sich
#: stillschweigend auf der harmlosen Seite wieder. Genau die Richtung, in der
#: ein Irrtum teuer wird.
HARMLOS: frozenset[str] = frozenset({
    # 'anatomie' (Befund 366) liest Kerzen und den Versuchszaehler, schreibt
    # nichts und fragt kein Netz. Es dauert - zwei Walk-Forwards mit teuren
    # Gates -, aber dauern ist keine Wirkung nach aussen.
    "anatomie",
    # 'aufteilung' (Befund 400) ist aus derselben Familie: Es liest Kerzen
    # und den Versuchszaehler, schreibt nichts und fragt kein Netz - nur
    # laeuft es elf Walk-Forwards statt zwei.
    "aufteilung",
    # 'nachgesehen' (Befund 425) liest Quelltext und druckt. Es rechnet
    # nichts, waehlt nichts aus und fragt kein Netz - der harmloseste Befehl
    # des Projekts, und genau deshalb gehoert er hierher und nicht ins
    # Stillschweigen: Unbekannt ist ein Fehler.
    "nachgesehen",
    # 'generationen' (Befund 459) baut die Genome der Kataloge, liest ihre
    # Kennzahlennamen und druckt eine Uebersicht. Keine Kerzen, kein
    # Walk-Forward, kein Netz, kein Versuch - und diese Wache hat den Befehl
    # am Tag seiner Entstehung gemeldet.
    "generationen",
    "abstand", "anwaerter", "aufloesung", "betriebspunkt",
    "decke", "duerre", "evidenz", "finanzierung",
    "form", "freigabe", "front", "gatemuster", "haelften",
    "holdout", "instrument", "jahresbild", "koernung",
    "konfluenz", "kontorisiko", "kosten", "leverage",
    "marktkombinationen", "nachpruefung", "nullprobe", "paare",
    "partner", "phasen", "plateaubild", "quality",
    # 'referenz' stand hier bis Befund 474 - und es **laedt an der Boerse
    # und schreibt den Kerzenspeicher**. Siehe WIRKT_NACH_AUSSEN.
    "quelle", "rangprobe", "register",
    "reibung",
    "regler", "rennen", "review", "scan",
    "schock", "sperrprobe", "stand", "status",
    "streuung", "suchbudget", "tageszeit", "taktung",
    "teststaerke", "trennschaerfe", "verbundmodell", "vereinbar",
    "vorratsdecke", "vorschlag", "zeitachse", "zufallseinstieg",
})

#: Was der Lauf ergeben hat - als Zahl, damit ein spaeterer Lauf sich daran
#: messen kann.
#:
#: 53 seit Befund 301: 'reibung' ist auf echten Tageskerzen gefahren worden -
#: ganz, in sechs Stuecken und aus Protokollen gelesen -, und hat dabei zwei
#: Fehler gezeigt, die jetzt behoben sind. Die Zahl steigt nur, wenn ein
#: Befehl wirklich gelaufen ist; sonst waere sie eine Behauptung.
#:
#: 54 seit Befund 313: 'freigabe' ist an beiden Betriebspunkten auf echten
#: Tageskerzen gefahren worden.
#:
#: **Sieben Befehle stehen wegen ihrer Schreibstellen in ``WIRKT_NACH_AUSSEN``**
#: (Befund 330/331): 'adaptiv', 'korb', 'landschaft', 'machbarkeit',
#: 'research', 'verbund', 'wettbewerb'. Sie laden nichts und stellen keine
#: Order - aber sie schreiben, und ein Rauchtest darf nichts hinterlassen.
#:
#: **Das Mittel dafuer heisst ``TRADING_TROCKENLAUF=1``** und steht seit Befund
#: 116/117 bereit. Es deckt *alle* Schreibstellen auf einmal - Zaehler,
#: Journal, Bestenliste, Berichtsdatei und das Committen-und-Senden -, und ein
#: Lauf meldet jede einzelne ausdruecklich ab. Gemessen in Befund 331 an 'cli
#: wettbewerb': Versuche 203 vor und nach dem Lauf, Berichtsordner unveraendert,
#: Arbeitsbaum sauber.
#:
#: **Befund 330 hat stattdessen ``PATHS__STATE`` benutzt** - eine Umlenkung, die
#: nur den Zaehler deckt. 'landschaft' schreibt sonst nichts und lief damit
#: richtig; 'wettbewerb' aber legt einen Bericht ab, **committet ihn und
#: pusht**. Genau das ist in Befund 331 passiert (``e00ffb7``), und es ist die
#: Wiederholung von Befund 117, dessen Docstring in ``core/report.py`` denselben
#: Vorfall beschreibt (``54770ec``). Wer hier einen Befehl rauchtestet, setzt
#: die Variable und verlaesst sich nicht auf eine Teilabdeckung.
#:
#: **Kein Freibrief.** Ein Rauchtest prueft keine Hypothese und sein Ergebnis
#: wird weggeworfen; deshalb ist er kein Versuch. Ein Forschungslauf im
#: Trockenlauf waere einer - und ob ein Sweep am Bestand als Versuch zaehlt,
#: liegt als Entscheidung beim Nutzer (Befund 282/233).
#:
#: ``GELAUFEN`` zaehlt weiter nur die harmlosen Befehle; die sieben gehoeren
#: nicht dazu.
#:
#: 55 seit Befund 366: 'anatomie' ist auf echten Tageskerzen gefahren worden -
#: mit '--bauteil konfluenz' (die Messung des Befundes), mit '--bauteil filter'
#: (der Kandidat hat keine - saubere Ablehnung) und mit einem erfundenen
#: Bauteilnamen (ebenso). Der erste Lauf hat dabei gezeigt, dass der Befehl
#: den Zulassungspunkt verfehlte; das stand dann im Befehl zu berichtigen und
#: nicht in dieser Zahl.
#: 56 seit Befund 400: 'cli aufteilung' ist auf echten Tageskerzen gefahren
#: worden - vorne abgeschnitten (die Messung des Befundes), hinten
#: abgeschnitten (die Gegenprobe, Streuung 0,0000), durchgehend (98 Trades je
#: Versatz) und mit '--tage 0', was aufrundet und es sagt.
#:
#: 57 seit Befund 425: 'cli nachgesehen' ist am echten Quelltext gefahren
#: worden - mit einer echten Frage (Treffer samt Fundworten), mit Unsinn
#: ("Keine Stelle gefunden", die Gegenprobe), mit ausschliesslich zu kurzen
#: Woertern (ebenso) und mit 'abnahme', das die Trefferquote zeigt. Der
#: Versuchszaehler stand vor und nach den Laeufen bei 203, geschrieben wurde
#: nichts. **Zwei Fehler hat der Lauf gezeigt**, beide behoben: Der Befehl war
#: hinter 'if __name__' angehaengt und damit nie registriert ("No such
#: command"), und 'bericht' griff 'Treffer.zeile' statt 'Treffer.stelle.zeile'.
#: Ohne den Lauf waere beides durch die Tests gekommen, die nur das Modul
#: fragen.
#:
#: 58 seit Befund 459: 'cli generationen' ist gefahren worden - ohne
#: Kerzenlaenge (alle zehn Generationen) und mit '-i D' (sechs markiert, 25
#: Genome zusammen). Der Versuchszaehler stand vor und nach den Laeufen bei
#: 203, geschrieben wurde nichts. Die Zahl 25 stimmt mit dem Lauf aus Befund
#: 456 ueberein, die 39 auf Viertelstunden mit den Stuecken aus 450 - eine
#: Uebersicht, die sich nicht gegenrechnen laesst, waere nur eine Behauptung.
#:
#: **Und derselbe Arbeitsgang hat den Kopf dieses Moduls widerlegt bekommen**
#: (459): Ich habe 'cli wettbewerb' fuenfmal ohne 'TRADING_TROCKENLAUF'
#: rauchgetestet, und jeder Lauf hat seinen Zulassungsbericht committet und
#: gepusht. Der Absatz zu Befund 331 oben beschreibt genau das - zum zweiten
#: Mal, nach 117. Meiner war der dritte.
GELAUFEN = 57
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

        **Und sie wird jetzt richtig gelesen** (Befund 479). Hier stand eine
        eigene Suche nach ``save_trials`` - dem einen von **zwei**
        Buchungswegen. Heute bucht kein Befehl mehr so; alle sieben gehen
        ueber ``_verzeichne(``. Damit fand diese Zusicherung die **leere
        Menge** und verglich sie gegen alles, denn leer ist Teilmenge von
        allem. Genau diesen Melderfehler hat Befund 282 eine Datei weiter
        behoben; hier blieb er stehen, bis er still wurde. Die Frage steht
        seit 479 einmal in ``tests/zaehlerwege``, und die Nichtleere ist
        zugesichert - sonst kann sie wieder verstummen.
        """
        zaehlend = zaehlende_befehle()

        assert zaehlend, (
            "kein Befehl bucht einen Versuch - dann sucht diese Wache am "
            "falschen Weg, wie bis Befund 479"
        )
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


#: Was der zweite ganze Lauf gefunden hat - Befund 473.
#:
#: Als Daten und nicht nur als Prosa, damit ein spaeterer Lauf nicht wieder
#: raten muss, ob die Liste schon einmal ganz gefahren wurde.
ZWEITER_LAUF: dict[str, str] = {
    "instrument": "InvalidOperation: 'Decimal(gebuehren)' statt "
                  "'Decimal(gebuehrenfaktor)' - seit Befund 377, behoben",
}

#: Befehle, die mit ihren Voreinstellungen laenger laufen als die Zeit, die
#: ihnen gegeben wurde. **Nicht** als sauber gezaehlt: Ein abgeschnittener
#: Lauf ist kein Ergebnis.
NICHT_ZU_ENDE: dict[str, str] = {
    "scan": "ueber 4,5 Minuten ohne eine Zeile Ausgabe, kein Fehler",
    "sperrprobe": "ueber 9,5 Minuten mit stetigem Fortschritt, kein Fehler",
}


class TestDerZweiteGanzeLauf:
    """**Befund 473.** Der Kopf sagte "nie wiederholt" - 130 Befunde lang
    richtig, und niemand hat es nachgeholt."""

    def test_der_fund_steht_als_daten_da(self) -> None:
        assert ZWEITER_LAUF, "ein Lauf ohne Ergebnis ist kein Lauf"
        for name, grund in ZWEITER_LAUF.items():
            assert name in HARMLOS, name
            assert len(grund) > 30, name

    def test_der_kopf_behauptet_nicht_mehr_er_sei_nie_wiederholt(self) -> None:
        """Genau die Aussage, die dieser Befund widerlegt hat - sie darf nicht
        zurueckkommen."""
        kopf = __doc__ or ""

        assert "Seither ist der Rauchtest nie wiederholt worden" not in kopf
        assert "Der zweite ganze Lauf" in kopf

    def test_die_unfertigen_sind_nicht_als_sauber_gezaehlt(self) -> None:
        """Sie stehen in ``HARMLOS`` - das sagt nur, dass man sie starten
        darf, nicht dass sie durchgelaufen sind."""
        for name in NICHT_ZU_ENDE:
            assert name in HARMLOS, name
            assert name not in SAUBER_ABGELEHNT, name

    def test_der_gefundene_befehl_hat_jetzt_eine_eigene_wache(self) -> None:
        """Sonst verliesse sich dieser Eintrag darauf, dass niemand den Fix
        zurueckdreht."""
        wache = Path("tests/test_befehlslauf_instrument.py")

        assert wache.exists()
        text = wache.read_text(encoding="utf-8")
        assert "Decimal(gebuehrenfaktor)" in text
        assert "CliRunner" in text


#: Namen, deren Verwendung einen Befehl zum Schreiber macht - Befund 474.
#:
#: Nicht "Netz" und nicht "langsam": **geschrieben**. Ein Befehl, der einen
#: davon verwendet, veraendert etwas, das ein spaeterer Lauf vorfindet.
SCHREIBENDE_NAMEN: tuple[str, ...] = (
    "backfill_reference",
    "backfill_funding",
    ".write(",
    ".write_frame(",
)


def _befehlsrumpf() -> dict[str, str]:
    """Jeder Befehl mit seinem Rumpf als Text."""
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    aus: dict[str, str] = {}
    for n in ast.walk(baum):
        if not isinstance(n, ast.FunctionDef):
            continue
        for d in n.decorator_list:
            if "app.command" not in ast.unparse(d):
                continue
            treffer = re.search(r'"([^"]+)"', ast.unparse(d))
            aus[treffer.group(1) if treffer else n.name] = ast.unparse(n)
    return aus


class TestKeinSchreiberGiltAlsHarmlos:
    """**Befund 474.** ``cli referenz`` stand unter ``HARMLOS`` und hat beim
    Lauf zu 473 die Feinreihe bis heute verlaengert - der gepinnte Stand war
    weg, auf dem jede gepflegte Zahl steht.

    Der Kopf dieser Datei sagte die Regel schon: *"Im Zweifel hierher."* Nur
    stand sie nirgends als Test, und eine Einteilung, die niemand nachrechnet,
    ist eine Meinung.
    """

    def test_kein_harmloser_befehl_schreibt(self) -> None:
        schuldig = [
            f"{name} ({[s for s in SCHREIBENDE_NAMEN if s in rumpf]})"
            for name, rumpf in _befehlsrumpf().items()
            if name in HARMLOS and any(s in rumpf for s in SCHREIBENDE_NAMEN)
        ]

        assert schuldig == [], (
            f"harmlos genannt, schreibt aber: {schuldig} - gehoert nach "
            f"WIRKT_NACH_AUSSEN"
        )

    def test_der_melder_findet_die_richtig_eingeteilten(self) -> None:
        """Die Gegenprobe: Ohne sie koennte die Regel oben auch bestehen, weil
        der Melder nichts findet. ``funding`` und ``ingest`` schreiben und
        stehen zu Recht drueben."""
        gefunden = {
            name
            for name, rumpf in _befehlsrumpf().items()
            if name in WIRKT_NACH_AUSSEN
            and any(s in rumpf for s in SCHREIBENDE_NAMEN)
        }

        assert {"funding", "ingest"} <= gefunden, gefunden

    def test_referenz_steht_drueben_und_mit_grund(self) -> None:
        assert "referenz" not in HARMLOS
        assert "Boerse" in WIRKT_NACH_AUSSEN["referenz"]
        assert "Kerzenspeicher" in WIRKT_NACH_AUSSEN["referenz"]

    def test_der_kopf_haelt_den_vorfall_fest(self) -> None:
        """Ein Vorfall, der nur im Laborbuch steht, warnt den naechsten Lauf
        nicht - er liest diese Datei."""
        kopf = __doc__ or ""

        assert "Befund 474" in kopf
        assert "229.728" in kopf and "232.334" in kopf
