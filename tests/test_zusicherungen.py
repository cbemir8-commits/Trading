"""Zusicherungen ueber **Abwesenheit** - wann sie richtig sind.

**Befund 245.** In Befund 244 ist ein eigener Test gefallen, und zwar zu Recht.
``test_teststaerke_zaehlt_mit`` aus Befund 242 enthielt:

    assert "write_report" not in quelle

Gemeint war *"sie ist leicht zu uebersehen, also pruefe, dass sie mitzaehlt"*.
Dagestanden hat *"sie schreibt selbst, und dabei bleibt es"* - der **Mangel als
Zusicherung festgeschrieben**. Beim Beheben ist der Test gefallen; genau da
merkt man es.

Wann eine negative Zusicherung richtig ist
------------------------------------------
Wenn sie eine **Entscheidung** haelt, die bewusst nicht gefallen ist - nicht,
wenn sie einen Zustand beschreibt.

Der Unterschied am lebenden Beispiel. ``test_die_sweeps_brechen_nicht_ab``
sichert zu, dass ``landschaft`` und ``machbarkeit`` die Budgetgrenze **nicht**
kennen. Das ist richtig: Ob ein Sweep am Bestand als Versuch zaehlt, ist die
offene Frage aus Befund 233/234, und wer die Grenze dort einbaut, beantwortet
sie im Vorbeigehen. Die Zusicherung haelt eine Grenze, keinen Mangel.

Was diese Wache leistet - und was nicht
---------------------------------------
Sie findet negative Zusicherungen ueber die Namen, die im Projekt fuer eine
Wache stehen, und verlangt, dass jede davon **eingetragen und begruendet**
ist. Ein neuer Fall zwingt damit zu der Frage, die in 242 nicht gestellt
wurde: Halte ich hier eine Entscheidung oder einen Zustand?

**Sie findet nicht alles.** Ein Test, der einen falschen *Wert* festschreibt
(``assert x == 0.2765``, als das schon ueberholt war), sieht wie jeder andere
aus. Gegen den hilft nur, was ``referenz.py`` tut: die Zahl an eine Messung
binden. Diese Wache deckt die Bauart ab, nicht die Absicht.

Und sie fand ueber eine gepflegte Liste - Befund 485
----------------------------------------------------
Der Absatz darueber sagt, sie finde "ueber die Namen, die im Projekt fuer eine
Wache stehen". Genau das war das Problem: ``WACHEN`` ist eine **gepflegte**
Liste, und damit entschied sie, was ueberhaupt als Bauteil gilt. Dieselbe
Bauart wie Befund 463, 479 und 484 - vier Mal in dieser Sitzung.

Zwei Luecken, gemessen:

* **Was nicht auf der Liste stand, war unsichtbar.** Fuenf Zusicherungen
  pruefen am Quelltext die Abwesenheit eines Bauteils, das dieses Projekt
  wirklich definiert - ``resample`` in ``CandleStore.read``,
  ``alle_geschnitten`` in ``jahresbild``, ``lade_champion`` in
  ``vorratsdecke``, ``_ohne_hebel`` vor dem Kassa-Punkt, ``range(`` in
  ``_nach_wort``. Keine davon war je gefragt worden.
* **Die Schreibweise mit Klammer fiel durch.** Gesucht wurde
  ``'save_trials'`` woertlich; ``'save_trials('`` - die natuerliche Form fuer
  *"dieser Aufruf kommt nicht vor"* - traf nicht. Zwei weitere Zusicherungen
  standen so daneben, und zwar zu **genau** dem Namen, fuer den die Liste
  gebaut wurde.

Seit 485 wird die Grundgesamtheit **abgeleitet**: eine Zeichenkette, die das
Projekt als Funktion oder Klasse wirklich definiert, geprueft an Quelltext.
Der Quelltext-Filter ist dabei das Entscheidende - ohne ihn findet die Suche
48 Treffer, und die meisten sind Zusicherungen ueber **Ausgabetext**
(``assert "mindestens" not in satz``), bei denen der Name nur zufaellig mit
einem Bauteil kollidiert. Ein Melder, der das falsche Ding findet, ist
schlimmer als keiner (Befund 478).

**Gefunden wurde kein festgeschriebener Mangel.** Alle neun neuen Faelle
halten eine Entscheidung, jeder mit seinem Grund unten. Das ist das Ergebnis,
und es ist eines: Gefragt worden war keine von ihnen.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

#: Namen, die fuer eine Wache oder ein richtiges Bauteil stehen. Eine
#: Zusicherung, dass eines davon **fehlt**, ist erklaerungsbeduerftig.
WACHEN: tuple[str, ...] = (
    "TROCKENLAUF",
    "_betriebspunkt",
    "_budget_erschoepft",
    "_pruefe_generation",
    "_verzeichne",
    "betriebspunkt",
    "erklaert_den_verlauf",
    "kalibrierbereich",
    "noetige_guete",
    "ohne_zensierte",
    "passt_zum_intervall",
    "randtrades",
    "save_trials",
    "scrub",
    "trockenlauf",
    "write_report",
)

#: Die eingetragenen Faelle: Testname -> warum die Abwesenheit gewollt ist.
#:
#: Wer hier etwas eintraegt, behauptet: **Das ist eine Entscheidung, kein
#: Mangel.** Der Satz muss die Entscheidung nennen, nicht den Zustand
#: beschreiben.
BEGRUENDET: dict[str, str] = {
    "test_die_sweeps_brechen_nicht_ab": (
        "Ob ein Sweep am Bestand als Versuch zaehlt, ist offen (Befund "
        "233/234). Wer die Budgetgrenze in 'landschaft' und 'machbarkeit' "
        "einbaut, beantwortet die Frage im Vorbeigehen - die Zusicherung "
        "haelt diese Grenze."
    ),
    "test_er_kostet_keinen_versuch": (
        "Gehalten wird: **Ein Gate zu erklaeren darf die Latte eines "
        "anderen nicht heben** (Befund 313). 'cli freigabe' rechnet genau "
        "die zwoelf Nachbarn nach, die das Plateau-Gate bei jedem Lauf "
        "ohnehin rechnet - zaehlte er, kostete das Nachlesen einer "
        "Gate-Begruendung Versuche, und die Huerde des Deflated Sharpe "
        "stiege fuer alle folgenden Kandidaten. Das waere ein Preis aufs "
        "Hinsehen. Die offene Frage aus 233/234 beruehrt das nicht: Sie "
        "gilt Sweeps, die etwas **finden** koennen - 'landschaft' sucht "
        "einen besseren Punkt, 'machbarkeit' eine Vola-Stufe, bei der alle "
        "elf Gates halten. 'freigabe' sortiert nichts und waehlt nichts "
        "aus; aus ihm kann kein Kandidat hervorgehen."
    ),
    "test_seit_befund_377_fuehrt_der_weg_ueber_das_verzeichnis": (
        "Hier wird kein Mangel festgeschrieben, sondern eine Entscheidung "
        "gehalten (Befund 377): 'adaptiv', 'research' und 'wettbewerb' buchen "
        "ihre Versuche ueber 'cli._verzeichne', also mit Einzelnachweis. "
        "'save_trials' schreibt nur die Summe - wer es dort zurueckholt, laesst "
        "die Versuche wieder ohne 'sharpe_je_trade' im Grundstock "
        "verschwinden, und damit bleibt die Streuung ueber die Versuche "
        "ungemessen (Befund 68). Die Abwesenheit ist das Gehaltene: nicht "
        "'save_trials' ist kaputt, sondern die Summe ist die falsche Buchung "
        "fuer einen Suchlauf. Die Funktion selbst bleibt samt ihren "
        "Unit-Tests - sie ist die Stelle, an der 'der Zaehler faellt nicht' "
        "steht."
    ),
    # **Die neun aus Befund 485.** Sie standen nicht hier, weil die
    # Grundgesamtheit an der gepflegten Liste 'WACHEN' hing und zwei
    # Schreibweisen uebersah. Jede einzeln gelesen: alle neun halten eine
    # Entscheidung. Gefunden wurde also kein festgeschriebener Mangel - und
    # genau das ist das Ergebnis, denn gefragt worden war keine von ihnen.
    "test_die_regel_leitet_ihre_grundgesamtheit_ab": (
        "Gehalten wird, dass eine Regel ihre Grundgesamtheit **ableitet** "
        "(Befund 490): Die Wache auf den Reihenschnitt fragt "
        "'zaehlende_befehle()' und darf deshalb keinen Befehl beim Namen "
        "nennen - 'korb' steht dort als Stellvertreter fuer jeden. Eine "
        "gepflegte Namensliste an dieser Stelle waere genau die Bauart, die "
        "Befund 484 und 485 gefunden haben. Dass diese Wache hier anschlaegt, "
        "ist ihr Dienst: Sie hat meine eigene Zusicherung gefangen."
    ),
    "test_machbarkeit_schreibt_einzelnachweise": (
        "Dieselbe Entscheidung wie beim Verzeichnisweg (Befund 377), nur in "
        "der Schreibweise 'save_trials(' - und gerade die hat die alte Wache "
        "uebersehen: 'machbarkeit' bucht ueber '_verzeichne' mit "
        "Einzelnachweis. Die Summe allein laesst die Stellungen im Grundstock "
        "verschwinden, und damit bleibt die Streuung ueber die Versuche "
        "ungemessen (Befund 68)."
    ),
    "test_landschaft_auch": (
        "Dieselbe Entscheidung fuer 'landschaft' (Befund 377/281), ebenfalls "
        "in der Schreibweise mit Klammer. Beide Befehle sind genau die, die "
        "Befund 282 aus der Aufsicht verloren haette, als sie auf "
        "Einzelnachweise umgestellt wurden."
    ),
    "test_der_speicher_fasst_nicht_selbst_zusammen": (
        "Gehalten wird: **Der Speicher erfindet keine Kerzenlaenge.** "
        "'CandleStore.read' kennt keinen Rueckfall auf feinere Kerzen - "
        "gaebe es ihn, entstuende eine fehlende Tagesreihe stillschweigend "
        "aus den 15-Minuten-Kerzen, und die Ladehinweise (Befund 209/210) "
        "waeren halb so wichtig. Dieselbe Gefahr wie in Befund 474: eine "
        "verschobene Messgrundlage, die niemandem auffaellt."
    ),
    "test_die_zulassungsreihe_aendert_hier_nichts": (
        "Gehalten wird eine **nicht** gemachte Aenderung: Acht Dateien haben "
        "'alle_geschnitten' in Befund 363/364 bekommen, 'cli jahresbild' "
        "nicht. Gemessen sind die Zahlen identisch (Gate -10,32 %, 2557 "
        "Fenster, dieselbe Episode), weil das schlechteste Jahr weit vom "
        "Datenende liegt und der Walk-Forward die Beine ohnehin schneidet. "
        "Eine Aenderung ohne Wirkung ist eine Aenderung zu viel."
    ),
    "test_stand_rechnet_primaer_ohne_die_spot_helfer": (
        "Gehalten wird, **welcher Punkt der erste ist** (Befund 228/229): "
        "'cli stand' rechnet zuerst den Perpetual-Punkt mit rohem Genom und "
        "Vorgabekonfiguration und erst danach den Kassa-Punkt. Welcher Punkt "
        "die Zulassung traegt, ist die offene Frage aus Befund 400/414 - wer "
        "den Erstlauf vertauscht, beantwortet sie im Vorbeigehen."
    ),
    "test_der_saatkandidat_bleibt_fuer_die_forschung": (
        "Gehalten wird die Trennung von Forschung und Livegang (Befund "
        "258/262): 'cli vorratsdecke' nimmt 'spitzenkandidat()' und nicht "
        "'lade_champion('. Die Forschungsbefehle vergleichen Verfahren auf "
        "**demselben** Kandidaten; wer dort den zugelassenen Champion laedt, "
        "macht jede Messreihe vom Zeitpunkt ihres Laufs abhaengig."
    ),
    "test_es_gibt_kein_flag_das_die_familien_trennt": (
        "Gehalten wird die teuerste Bequemlichkeit (Befund 272/274): Eine "
        "Familie allein zu scannen waere die einfachste Art, die Latte zu "
        "senken, denn die Huerde haengt an der Zahl der geprueften Zellen. "
        "Deshalb hat 'cli scan' keinen Schalter dafuer, und deshalb "
        "uebergibt er 'gepruefte_zellen=gesamt'."
    ),
    "test_der_vorrat_ist_keine_option": (
        "Dieselbe Entscheidung an denselben Parametern (Befund 274/276): "
        "Breite, Nachbarn und Vorrat sind keine Schalter von 'cli scan'. Wer "
        "sie einbaut, kann den Umfang des Scans waehlen - und damit die "
        "Latte, gegen die er gemessen wird."
    ),
    "test_die_wortliste_steht_nicht_auf_einer_zahl": (
        "Gehalten wird, dass eine Liste **abgeleitet** bleibt (Befund 275): "
        "'nachmessung._nach_wort' waechst mit 'zahlwort' statt mit einem "
        "gepflegten 'range(1, 200)'. Dieselbe Lehre, die diesen Befund "
        "ausgeloest hat - eine gepflegte Obergrenze laeuft irgendwann hinter "
        "den Daten her."
    ),
    "test_kein_versuch_wird_gebucht": (
        "Dieselbe Begruendung wie bei 'freigabe', und sie ist hier noch "
        "einfacher (Befund 366): 'cli anatomie' laesst ein Bauteil weg, das "
        "der Kandidat **schon hat**, und misst denselben Punkt noch einmal. "
        "Es waehlt nichts aus und sortiert nichts; aus ihm kann kein "
        "Kandidat hervorgehen. Wuerde es zaehlen, kostete das Nachsehen, "
        "woran ein zugelassener Punkt haengt, einen Versuch - und die Huerde "
        "des Deflated Sharpe stiege fuer alle folgenden Kandidaten. Die "
        "abgespeckte Fassung als Kandidaten zu fuehren ist etwas anderes: "
        "Das kostet einen Versuch und ist eine Entscheidung des Nutzers."
    ),
}


#: Woran erkannt wird, dass eine Zeichenkette aus **Quelltext** kommt.
#:
#: **Der Filter, der Befund 485 ueberhaupt messbar macht.** Ohne ihn findet
#: eine abgeleitete Suche 48 Treffer, und die meisten sind Zusicherungen ueber
#: **Ausgabetext**: ``assert "mindestens" not in satz`` prueft einen Satz, und
#: dass irgendein Modul eine Variable ``mindestens`` fuehrt, hat damit nichts
#: zu tun. Eine Zusicherung ueber ein Bauteil prueft den Quelltext.
QUELLE_ZEICHEN: tuple[str, ...] = (
    "read_text",
    "unparse",
    "getsource",
    "quelltext",
    "rumpf(",
    "_quelle(",
)

#: Ordner, in denen nach echten Bauteilen gesucht wird.
PROJEKT: tuple[str, ...] = (
    "backtest",
    "core",
    "data",
    "execution",
    "research",
    "strategies",
    "strategy",
    "web",
    "scripts",
)


def projektnamen() -> frozenset[str]:
    """Jede Funktion und Klasse, die dieses Projekt wirklich definiert.

    Abgeleitet und nicht gepflegt - die Lehre aus Befund 463, 479 und 484:
    Eine Wache, deren Grundgesamtheit an einer Namensliste haengt, verliert
    genau die Faelle, die noch niemand eingetragen hat.
    """
    aus: set[str] = {"cli"}
    dateien = [Path("cli.py")]
    for ordner in PROJEKT:
        if Path(ordner).is_dir():
            dateien += sorted(Path(ordner).rglob("*.py"))
    for pfad in dateien:
        if not pfad.exists():
            continue
        for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
            if isinstance(
                knoten, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            ):
                aus.add(knoten.name)
    return frozenset(aus)


def _quelltextnamen(fn: ast.AST) -> set[str]:
    """Namen in dieser Funktion, die Quelltext enthalten - **auch mittelbar**.

    Die Kette wird bis zum Stillstand verfolgt, und das ist nicht Zierrat:
    ``test_seit_befund_377_fuehrt_der_weg_ueber_das_verzeichnis`` baut aus
    ``quelle`` erst einen Syntaxbaum und daraus die Menge der **Aufrufnamen**,
    und prueft dagegen. Das ist die staerkste der drei Bauarten - ein Textfund
    kann ein Kommentar sein, ein Aufrufname nicht -, und ein Filter, der nur
    eine Stufe sieht, verliert gerade sie.
    """
    aus: set[str] = set()
    zuweisungen = [
        (knoten, ast.unparse(knoten.value) if knoten.value else "")
        for knoten in ast.walk(fn)
        if isinstance(knoten, ast.Assign | ast.AnnAssign)
    ]
    for _runde in range(5):
        vorher = len(aus)
        for knoten, wert in zuweisungen:
            if not (
                any(z in wert for z in QUELLE_ZEICHEN)
                or any(n in _woerter(wert) for n in aus)
            ):
                continue
            ziele = (
                knoten.targets
                if isinstance(knoten, ast.Assign)
                else [knoten.target]
            )
            for ziel in ziele:
                if isinstance(ziel, ast.Name):
                    aus.add(ziel.id)
        if len(aus) == vorher:
            break
    return aus


def _woerter(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", text))


def _prueft_quelltext(knoten: ast.Compare, namen: set[str], helfer: set[str]) -> bool:
    rechts = ast.unparse(knoten.comparators[0])
    kopf = rechts.split("[")[0].split(".")[0].split("(")[0]
    return (
        kopf in namen
        or any(h in rechts for h in helfer)
        or any(z in rechts for z in QUELLE_ZEICHEN)
    )


def _negative_zusicherungen() -> dict[str, tuple[str, int, str]]:
    """Jeder Test, der die Abwesenheit eines Bauteils zusichert.

    **Abgeleitet seit Befund 485.** Vorher entschied die gepflegte Liste
    ``WACHEN``, was ueberhaupt als Bauteil gilt - fuenf Zusicherungen am
    Quelltext ueber echte Bauteile standen daneben und wurden nie gefragt.
    Jetzt gilt: eine Zeichenkette, die dieses Projekt als Funktion oder
    Klasse **wirklich definiert**, geprueft an **Quelltext**.
    """
    bauteile = projektnamen()
    gefunden: dict[str, tuple[str, int, str]] = {}
    for datei in sorted(Path("tests").glob("test_*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        helfer = {
            n.name
            for n in baum.body
            if isinstance(n, ast.FunctionDef)
            and any(z in ast.unparse(n) for z in QUELLE_ZEICHEN)
        }
        for funktion in ast.walk(baum):
            if not isinstance(funktion, ast.FunctionDef):
                continue
            if not funktion.name.startswith("test_"):
                continue
            namen = _quelltextnamen(funktion)
            for knoten in ast.walk(funktion):
                if not isinstance(knoten, ast.Assert):
                    continue
                pruefung = knoten.test
                if not (
                    isinstance(pruefung, ast.Compare)
                    and any(isinstance(o, ast.NotIn) for o in pruefung.ops)
                    and isinstance(pruefung.left, ast.Constant)
                    and isinstance(pruefung.left.value, str)
                ):
                    continue
                name = pruefung.left.value.rstrip("(").strip()
                if name not in bauteile and name not in WACHEN:
                    continue
                if not _prueft_quelltext(pruefung, namen, helfer):
                    continue
                gefunden[funktion.name] = (datei.name, knoten.lineno, name)
    return gefunden


class TestDerMelderTaugt:
    """**Befund 485.** Vor der Regel der Melder - und hier hat er mich
    zweimal in die Irre geschickt, bevor er stimmte."""

    def _fn(self, quelle: str) -> ast.FunctionDef:
        return next(
            n for n in ast.walk(ast.parse(quelle)) if isinstance(n, ast.FunctionDef)
        )

    def test_quelltext_wird_erkannt(self) -> None:
        fn = self._fn(
            "def test_x():\n    quelle = Path('cli.py').read_text()\n    return quelle\n"
        )

        assert _quelltextnamen(fn) == {"quelle"}

    def test_und_zwar_auch_mittelbar(self) -> None:
        """Die Bauart, die der erste Entwurf verloren hat: aus dem Quelltext
        wird ein Baum, daraus die Menge der Aufrufnamen."""
        fn = self._fn(
            "def test_x():\n"
            "    quelle = inspect.getsource(cli.adaptiv)\n"
            "    baum = ast.parse(quelle)\n"
            "    aufrufe = {k.func.id for k in ast.walk(baum)}\n"
            "    return aufrufe\n"
        )

        assert _quelltextnamen(fn) >= {"quelle", "baum", "aufrufe"}

    def test_ein_ausgabesatz_ist_kein_quelltext(self) -> None:
        """**Der Filter, der das Rauschen erschlaegt.** Ohne ihn findet die
        abgeleitete Suche 48 Treffer, und die meisten sind Zusicherungen
        ueber Ausgabetext: 'mindestens' kommt in einem Satz nicht vor, und
        dass irgendein Modul so eine Variable fuehrt, hat damit nichts zu
        tun."""
        fn = self._fn("def test_x():\n    satz = lage.urteil()\n    return satz\n")

        assert _quelltextnamen(fn) == set()

    def test_die_namen_kommen_aus_dem_projekt(self) -> None:
        namen = projektnamen()

        assert "write_report" in namen
        assert "trockenlauf" in namen
        assert "zwischenstand" not in namen, "ein Modulname ist kein Bauteilname"
        assert len(namen) > 1000, len(namen)

    def test_beide_schreibweisen_werden_gefunden(self) -> None:
        """Die zweite Luecke von 485: Die alte Fassung suchte ``'save_trials'``
        mit Anfuehrungszeichen **exakt** - und ``'save_trials('``, also die
        natuerliche Schreibweise fuer "dieser Aufruf kommt nicht vor", fiel
        durch. Zwei Zusicherungen standen so jahrelang daneben."""
        gefunden = _negative_zusicherungen()

        assert "test_landschaft_auch" in gefunden
        assert "test_seit_befund_377_fuehrt_der_weg_ueber_das_verzeichnis" in gefunden

    def test_die_grundgesamtheit_ist_nicht_leer(self) -> None:
        """Lehre aus Befund 479: Eine Wache, die nichts findet, sichert
        nichts zu."""
        gefunden = _negative_zusicherungen()

        assert len(gefunden) >= 10, sorted(gefunden)


class TestJedeAbwesenheitIstBegruendet:
    def test_keine_unerklaerte_negative_zusicherung(self) -> None:
        """**Die Wache gegen den naechsten Fall wie Befund 242.**

        Faellt hier ein neuer Name auf, ist die Frage zu beantworten: Halte
        ich eine Entscheidung, die bewusst nicht gefallen ist - oder schreibe
        ich einen Mangel fest, den jemand spaeter behebt?

        Im ersten Fall gehoert er nach ``BEGRUENDET``, im zweiten gehoert die
        Zusicherung weg.
        """
        offen = sorted(set(_negative_zusicherungen()) - set(BEGRUENDET))

        assert offen == [], (
            f"sichern die Abwesenheit einer Wache zu, ohne Eintrag in BEGRUENDET: {offen}"
        )

    def test_der_eingetragene_fall_gibt_es_noch(self) -> None:
        """Ein Eintrag fuer einen Test, den es nicht mehr gibt, ist genau die
        Sorte Altlast, gegen die dieses Projekt seine Register prueft."""
        vorhanden = set(_negative_zusicherungen())
        verwaist = sorted(set(BEGRUENDET) - vorhanden)

        assert verwaist == [], f"steht in BEGRUENDET, gibt es nicht mehr: {verwaist}"

    def test_jede_begruendung_nennt_eine_fundstelle(self) -> None:
        """Eine Entscheidung ohne Befund waere eine Meinung - dieselbe Regel
        wie fuer ``Richtung`` und ``Schritt``."""
        for name, grund in BEGRUENDET.items():
            assert "Befund" in grund, name


class TestWasDerFallVonBefund244War:
    def test_teststaerke_sichert_die_abwesenheit_nicht_mehr_zu(self) -> None:
        """Der behobene Fall - er darf nicht zurueckkommen."""
        gefunden = _negative_zusicherungen()

        assert "test_teststaerke_zaehlt_mit" not in gefunden

    def test_sie_geht_inzwischen_durch_die_wache(self) -> None:
        import ast as _ast

        baum = _ast.parse(Path("cli.py").read_text())
        quelle = next(
            _ast.unparse(n)
            for n in _ast.walk(baum)
            if isinstance(n, _ast.FunctionDef) and n.name == "teststaerke"
        )

        assert "write_report" in quelle


def _nie_wahre_zusicherungen() -> dict[str, tuple[str, int, str]]:
    """Zusicherungen, die **statisch** nicht fallen koennen - Befund 423.

    Zwei Bauarten, beide in Befund 420 an meinem eigenen Code gefunden und
    drei Befunde spaeter von mir wieder geschrieben:

    * ``assert "Gross" in text.lower()`` - der Heuhaufen wird kleingeschrieben,
      die Nadel nicht. Nie wahr, also nie gruen, also faellt es auf. Harmlos
      **nur deshalb**.
    * ``assert obj.__dict__.get("feld", vorgabe)`` - immer wahr, sobald die
      Vorgabe wahr ist, und bei einem ``slots``-Dataclass hat ``__dict__``
      das Feld ohnehin nie. Das ist die gefaehrliche Richtung: still gruen.
    """
    gefunden: dict[str, tuple[str, int, str]] = {}
    for datei in sorted(Path("tests").glob("test_*.py")):
        baum = ast.parse(datei.read_text())
        for funktion in ast.walk(baum):
            if not isinstance(funktion, ast.FunctionDef):
                continue
            if not funktion.name.startswith("test_"):
                continue
            for knoten in ast.walk(funktion):
                if not isinstance(knoten, ast.Assert):
                    continue
                stelle = (datei.name, knoten.lineno)
                for teil in ast.walk(knoten.test):
                    if isinstance(teil, ast.Compare):
                        nadel = teil.left
                        passt = (
                            any(isinstance(o, ast.In) for o in teil.ops)
                            and isinstance(nadel, ast.Constant)
                            and isinstance(nadel.value, str)
                            and nadel.value != nadel.value.lower()
                            and ast.unparse(teil.comparators[0]).endswith(".lower()")
                        )
                        if passt:
                            gefunden[f"{funktion.name}:{knoten.lineno}"] = (
                                *stelle,
                                "grosse Nadel gegen .lower()",
                            )
                    if (
                        isinstance(teil, ast.Call)
                        and isinstance(teil.func, ast.Attribute)
                        and teil.func.attr == "get"
                        and isinstance(teil.func.value, ast.Attribute)
                        and teil.func.value.attr == "__dict__"
                        and len(teil.args) > 1
                    ):
                        gefunden[f"{funktion.name}:{knoten.lineno}"] = (
                            *stelle,
                            "__dict__.get mit Vorgabe",
                        )
    return gefunden


class TestKeineZusicherungDieNichtFallenKann:
    """Befund 423. Die Lehre ist nicht die Bauart, sondern dass ein
    Registereintrag sie nicht verhindert hat: 420 hat beide Faelle
    verzeichnet, 423 hat beide wieder geschrieben."""

    def test_es_gibt_keine(self) -> None:
        offen = _nie_wahre_zusicherungen()

        assert offen == {}, f"kann nicht fallen: {offen}"

    def test_die_wache_findet_die_grosse_nadel(self) -> None:
        """Gegenprobe - eine Wache, die nichts mehr findet, ist gruen und
        leer (dieselbe Pruefung wie in ``test_wachenaudit``)."""
        baum = ast.parse('def test_x():\n    assert "Gross" in t.lower()\n')
        treffer = [
            k
            for f in ast.walk(baum)
            if isinstance(f, ast.FunctionDef)
            for k in ast.walk(f)
            if isinstance(k, ast.Compare)
            and isinstance(k.left, ast.Constant)
            and k.left.value != k.left.value.lower()
            and ast.unparse(k.comparators[0]).endswith(".lower()")
        ]

        assert len(treffer) == 1

    def test_und_laesst_die_kleine_nadel_stehen(self) -> None:
        """``assert "klein" in t.lower()`` ist richtig und haeufig."""
        baum = ast.parse('def test_x():\n    assert "klein" in t.lower()\n')
        gross = [
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.Compare)
            and isinstance(k.left, ast.Constant)
            and k.left.value != k.left.value.lower()
        ]

        assert gross == []

    def test_und_laesst_das_modul_dict_ohne_vorgabe_stehen(self) -> None:
        """``core.models.__dict__.get("__file__")`` in
        ``test_fensterprobe`` ist sauber: Ein Modul **hat** ein ``__dict__``,
        und ohne Vorgabe faellt die Zusicherung, wenn das Feld fehlt."""
        offen = _nie_wahre_zusicherungen()

        assert not [s for s in offen.values() if s[0] == "test_fensterprobe.py"]
