"""Eine Verbotsregel an einer Datei zu pruefen ist eine Entscheidung (Befund 464).

Woher das kommt
---------------
Befund 463 hat dreimal dasselbe gefunden: eine richtige Regel, deren Wache in
zu wenige Dateien sieht.

* Befund 213 - *"wer ein Intervall nennt, nennt das Datum mit"* - sah in vier
  Dateien; zwei Verletzungen standen in zwei anderen.
* Befund 357/359 - *"jede Ladezeile nennt den Zulassungskorb"* - galt fuer
  ``BEIM_NUTZER``; acht kopierbare Vorschriften daneben nannten ihn nicht.
* Befund 210 - *"das System hat elf Gates, nicht neun"* - sah in **eine**
  Datei; die falsche Zahl lebte an sieben Stellen in fuenf Dateien weiter.

Dreimal derselbe Bauplan: Die Wache steht dort, wo der Fehler gefunden wurde,
und nicht dort, wo die Regel gilt. Also die Frage an die ganze Suite: **Wo
steht noch so eine?**

Was gemessen ist
----------------
Eine *Verbotsregel* ist ein Test, der behauptet, etwas komme **nicht** vor -
``assert ... not in ...``, ``assert not ...``, ``assert ... == []``. Genau
diese Form ist von Natur aus projektweit: "nirgends" ist keine Eigenschaft
einer Datei.

    Verbotsregeln mit weiter Reichweite (Glob, abgeleitete Liste)      7
    Verbotsregeln an genau einer Datei                                 7

Und alle sieben sind berechtigt - jede steht unten mit ihrem Grund. **Die
Klasse ist leer**, und dieser Test haelt sie leer: Eine neue Verbotsregel an
einer einzelnen Datei faellt hier auf und verlangt entweder die Reichweite
oder einen Satz dazu.

**Sieben und nicht sechs**, und der Unterschied ist wieder mein Erkenner: Der
erste kannte als leere Sammlung nur ``[]``. ``test_die_offenen_werden_wirklich
_durchsucht`` prueft ``ohne == ()`` und fiel damit aus der Grundgesamtheit -
lautlos, denn eine zu kleine Grundgesamtheit sieht aus wie ein gutes Ergebnis.
Deshalb kennt ``_ist_leer`` jetzt alle drei Formen, und drei Zusicherungen
unten pruefen den Erkenner selbst.

Mein eigener Messfehler dabei
-----------------------------
Der erste Lauf meldete **13** statt 6, und einer der Treffer war
``test_jeder_aufruf_im_projekt_nennt_seine_herkunft`` - die Wache, die
sicherstellt, dass kein ``evaluate_gates`` ohne Herkunftsangabe laeuft. An der
haengt die Sperre selbst (``GateReport.passed`` verlangt ``not
referenzdaten``), und es sah aus wie ein Loch an der folgenreichsten Stelle.

Es war keines. Der Test liest ``[*Path("research").glob("*.py"), Path("cli.py")]``
- mein Erkenner sah nur woertliche Dateinamen und den Glob nicht. Nachgezaehlt
hat ``evaluate_gates`` **26** Aufrufstellen, alle in ``cli.py`` und
``research/admission.py``, also beide in der Reichweite dieser Wache.

Dieselbe Lehre wie Befund 118, diesmal an meinem eigenen Werkzeug: Eine Suche,
deren Treffer man ungeprueft uebernimmt, ist schlimmer als keine.

Und der Erkenner hatte noch zwei Loecher - Befund 484
-----------------------------------------------------
Der Absatz darueber nennt mein erstes. Hier sind das zweite und dritte, und
diesmal haben sie etwas gekostet.

**``walk`` ist zweideutig.** In ``WEITE_REICHWEITE`` stand der bloze Name;
``os.walk`` laeuft ueber ein Dateisystem, ``ast.walk`` ueber den Syntaxbaum
**einer** Datei. Fast jede quelltextpruefende Wache dieses Projekts parst mit
``ast`` und laeuft mit ``ast.walk`` - und galt damit als weit. Gemessen: **52
der 71** Verbotsregeln waren nur auf diesem Weg "weit", und **20** davon lasen
genau eine Datei.

**Und der Dateizugriff darf einen Aufruf entfernt liegen.**
``_literale_dateien`` sah nur in die Testfunktion. In ``test_berichtswache``
liest der Helfer ``_befehle()`` die Datei - damit null literale Dateien, kein
Glob, und die Regel fiel durch **beide** Zweige der Einordnung: nicht weit,
nicht eng, nirgends geprueft.

**Genau diese Regel war dann zu eng.** Befund 482 hat gefunden, dass
``research/zwischenstand.py`` ebenfalls nach ``reports/`` schreibt und an
allen drei Zusagen vorbeiging - 168 Protokolle, und zwei Befunde standen auf
zwei davon. Die Wache, die das haette melden sollen, war die hier.

Nach dem Umbau gemessen:

    Verbotsregeln mit weiter Reichweite                               21
    Verbotsregeln an genau einer Datei                                28
      verschiedene Namenspaare darunter                               27
      begruendet in ABSICHTLICH_ENG (8 Eintraege, 9 Vorkommen)         9
      Aussagen ueber die Befehlsschicht (NUR_DIE_BEFEHLSDATEI)        19

Die weite Zahl stand nach Befund 485 auf 20 und steht seit Befund 494 auf 21:
Die Tafel-Inventur in ``test_kerzendeutung`` sichert ueber den ganzen Baum zu,
dass keine Tafel nach Kerzenlaenge ohne Deutung abgefragt wird. Beide Male hat
diese Wache den Zuwachs gemeldet, bevor er in einem Kopf als Behauptung
stehenblieb - genau der Dienst, fuer den sie in 484 gebaut wurde.

27 Vorkommen bei 26 Paaren: ``test_jede_fundstelle_gibt_es_wirklich`` steht
zweimal in ``test_stand``, einmal fuer GESCHLOSSEN und einmal fuer OFFEN -
derselbe Fall, den der Eintrag dazu schon nennt. Einer der sieben Eintraege
ist neu und der Grund dieses Befundes: die Regel aus 482, die wirklich zu eng
war.

Dazu ein Nebenfehler derselben Zeile: ``weit += 1 if dateien else 0`` zaehlte
nur, was weit war **und** zusaetzlich eine Datei nannte - 17 Regeln, die
gerade durch ihren Glob weit sind, fielen aus der Zahl.

Die Lehre ist die dieser Datei, auf sie selbst angewandt: Ein Erkenner, der
am Namen haengt statt an der Sache, verliert genau die Faelle, um die es geht.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
TESTS = sorted((WURZEL / "tests").glob("test_*.py"))

#: Aufrufe, die eine Regel ueber **mehr** als die genannten Dateien fuehren.
#:
#: ``behauptungsquellen`` steht hier, weil Befund 463 die Liste ausdruecklich
#: abgeleitet statt gepflegt hat - wer sie benutzt, hat weite Reichweite.
#:
#: **``walk`` steht hier nicht mehr - Befund 484.** Der Name ist zweideutig:
#: ``os.walk`` laeuft ueber ein Dateisystem, ``ast.walk`` ueber den
#: Syntaxbaum **einer** Datei. Fast jede quelltextpruefende Wache dieses
#: Projekts parst mit ``ast`` und laeuft mit ``ast.walk`` - und galt damit als
#: weit, auch wenn sie genau eine Datei liest. Gemessen waren 52 der 71
#: Verbotsregeln nur auf diesem Weg "weit", und 20 davon lasen eine einzige
#: Datei. Welche Durchlaeufe wirklich weit sind, steht in ``WEITE_EMPFAENGER``.
WEITE_REICHWEITE = frozenset(
    {"glob", "rglob", "iterdir", "behauptungsquellen", "vorschriften"}
)

#: ``walk`` ist nur mit diesen Empfaengern eine Dateisuche.
#:
#: ``os.walk`` und ``Path.walk`` laufen ueber Ordner; ``ast.walk`` tut es
#: nicht. Ein bloszes ``walk(...)`` ohne Empfaenger zaehlt als weit - die
#: sichere Richtung: Eine Regel faelschlich fuer weit zu halten verliert sie
#: aus dieser Aufsicht, und genau das ist Befund 484.
WEITE_EMPFAENGER = frozenset({"os", "pathlib", "Path", "shutil"})

#: Verbotsregeln, die mit Absicht auf **eine** Datei sehen, mit Grund.
#:
#: Ein Eintrag heisst: "Diese Regel gilt wirklich nur fuer diese Datei." Wer
#: einen hinzufuegt, schreibt den Grund dazu - genauso wie bei
#: ``ENTSCHEIDUNGSGATES`` (Befund 461): Wer eine Stelle der Pruefung entzieht,
#: nennt sie, statt sie zu erraten.
ABSICHTLICH_ENG: dict[tuple[str, str], str] = {
    (
        "test_auftragstakt.py",
        "test_und_die_cli_rechnet_ihn_an_jeder_stelle",
    ): (
        "Die Regel handelt von den drei Aufrufstellen in 'cli.py' - dort wird "
        "der Takt gerechnet, und nur dort kann er ohne Kerzenlaenge gerechnet "
        "werden (Befund 496). In einer anderen Datei waere nichts zu pruefen: "
        "'als_auftrag' verlangt die Kerzenlaenge seitdem als Pflichtwort, und "
        "das steht als eigene Zusicherung in 'test_auftragsbalken'."
    ),
    (
        "test_ideenstreuung.py",
        "test_der_modulkopf_von_wettrennen_behauptet_es_nicht_mehr",
    ): (
        "Die Regel handelt von diesem Modulkopf. 'Mehr gibt es nicht' war "
        "seine Aussage, Befund 237 hat sie widerlegt - an einer anderen Datei "
        "waere nichts zu pruefen."
    ),
    ("test_reihenfolge.py", "test_jede_fundstelle_steht_im_laborbuch"): (
        "Das Laborbuch **ist** die eine Datei, von der die Regel spricht. "
        "Seit Befund 464 fuehrt sie 'nachmessung.ohne_abschnitt' aus, also "
        "denselben Parser wie die Suche, die das Laborbuch durchsucht."
    ),
    ("test_stand.py", "test_jede_fundstelle_gibt_es_wirklich"): (
        "Dieselbe Regel am Laborbuch, fuer GESCHLOSSEN und fuer OFFEN - zwei "
        "Tests gleichen Namens in zwei Klassen."
    ),
    ("test_stand.py", "test_jede_behobene_fundstelle_steht_im_laborbuch"): (
        "Dieselbe Regel am Laborbuch, fuer BEHOBEN - und seit Befund 464 "
        "auch fuer die 91 'zuletzt' dieser Liste, die vorher niemand "
        "geprueft hat."
    ),
    ("test_nachmessung.py", "test_die_offenen_werden_wirklich_durchsucht"): (
        "Das Laborbuch ist hier nicht eine Datei unter vielen, sondern der "
        "**Korpus**, ueber den die Suche laeuft. Geprueft wird, dass keine "
        "offene Richtung ohne Suchbegriffe dasteht (Befund 294)."
    ),
    ("test_stand.py", "test_keine_stelle_nennt_mehr_neun_gates"): (
        "Seit Befund 463 ausdruecklich die Gegenprobe an 'cli.py'. Die weite "
        "Pruefung derselben Regel steht in 'test_ladehinweise' und fuehrt "
        "ueber jede Datei, die etwas behauptet."
    ),
    (
        "test_berichtswache.py",
        "test_niemand_schreibt_an_write_report_vorbei_nach_reports",
    ): (
        "**Diese war wirklich zu eng, und es hat etwas gekostet** (Befund "
        "482): 'research/zwischenstand.py' schreibt ebenfalls nach 'reports/' "
        "und ging an allen drei Zusagen vorbei. Sie bleibt an 'cli.py', weil "
        "sie dort genauer prueft - Befehl fuer Befehl; die weite Fassung "
        "derselben Regel steht seit 482 in 'test_berichtswege' und fuehrt "
        "ueber jedes Modul des Baums."
    ),
}

#: Verbotsregeln, die nur ``cli.py`` lesen, weil sie von **Befehlen** reden.
#:
#: **Warum eine Kategorie und nicht neunzehn Saetze - Befund 484.** Nach dem
#: Melderumbau fielen 20 Regeln neu in die enge Klasse, 19 davon mit
#: demselben Grund: Ihre Aussage handelt von der Befehlsschicht - "es gibt
#: kein Flag, das die Familien trennt", "jeder Befehl ist eingeteilt", "diese
#: Stelle rechnet ohne den zensierten Punkt" -, und Befehle stehen in
#: ``cli.py``. Neunzehn Kopien eines Satzes waeren der Platzhalter, vor dem
#: ``test_jeder_grund_ist_einer`` warnt.
#:
#: Die Liste ist trotzdem **gepflegt und nicht abgeleitet**: Eine neue Regel
#: faellt hier auf und muss hinzugefuegt werden. Das ist der Punkt von Befund
#: 461 - wer eine Stelle der Pruefung entzieht, nennt sie, statt sie zu
#: erraten. Wer eine hinzufuegt, prueft vorher, ob ihre Aussage wirklich eine
#: ueber Befehle ist: Bei einer der zwanzig war sie es nicht, und das war
#: Befund 482.
NUR_DIE_BEFEHLSDATEI: frozenset[tuple[str, str]] = frozenset(
    {
        ("test_betriebspunkt.py", "test_der_spotpunkt_rechnet_ohne_den_zensierten"),
        (
            "test_betriebspunkt_im_bericht.py",
            "test_stand_rechnet_primaer_ohne_die_spot_helfer",
        ),
        ("test_familienscan.py", "test_und_uebergibt_die_summe_an_das_urteil"),
        ("test_familienscan.py", "test_es_gibt_kein_flag_das_die_familien_trennt"),
        ("test_funding_kommt_an.py", "test_und_zwar_auch_auf_einem_einzelnen_markt"),
        ("test_kerzenlaenge_zulassung.py", "test_er_bricht_dabei_nicht_ab"),
        (
            "test_kerzenwache_vollstaendig.py",
            "test_jeder_katalogleser_prueft_die_kerzenlaenge",
        ),
        ("test_korb_und_bein.py", "test_der_befehl_ruft_sie_auf_und_bricht_nicht_ab"),
        ("test_korb_und_bein.py", "test_und_bricht_dabei_nicht_ab"),
        ("test_korb_und_bein.py", "test_beide_befehle_nehmen_denselben_text"),
        (
            "test_livegang_abgleich.py",
            "test_der_saatkandidat_bleibt_fuer_die_forschung",
        ),
        ("test_marktbreite.py", "test_der_vorrat_ist_keine_option"),
        ("test_rauchtest.py", "test_jeder_befehl_ist_eingeteilt"),
        ("test_rauchtest.py", "test_die_liste_nennt_keine_befehle_die_es_nicht_gibt"),
        ("test_rauchtest.py", "test_die_harmlose_liste_nennt_keine_gespenster"),
        ("test_rauchtest.py", "test_kein_harmloser_befehl_schreibt"),
        ("test_simulationsmeldung.py", "test_der_livebetrieb_nicht"),
        ("test_versuchszaehler_wer.py", "test_die_sweeps_brechen_nicht_ab"),
        ("test_zaehlerwege.py", "test_save_trials_kommt_in_keinem_befehl_mehr_vor"),
    }
)


def _literale_dateien(fn: ast.AST) -> set[str]:
    """Quelldateien, die dieser Test namentlich liest."""
    aus = set()
    for n in ast.walk(fn):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "Path"
            and n.args
            and isinstance(n.args[0], ast.Constant)
            and isinstance(n.args[0].value, str)
            and n.args[0].value.endswith((".py", ".md"))
        ):
            aus.add(n.args[0].value)
    return aus


def _ist_dateidurchlauf(aufruf: ast.Call) -> bool:
    """Laeuft dieser Aufruf ueber **Dateien** - oder ueber einen Baum?

    **Befund 484.** Hier wurde nur der Name geprueft, und ``walk`` stand in
    der Liste. ``ast.walk`` ist aber ein Durchlauf durch den Syntaxbaum einer
    einzigen Datei; wer ihn fuer eine Dateisuche nimmt, haelt jede
    quelltextpruefende Wache fuer weit.
    """
    f = aufruf.func
    if isinstance(f, ast.Attribute):
        if f.attr in WEITE_REICHWEITE:
            return True
        if f.attr == "walk":
            empfaenger = ast.unparse(f.value).split(".")[0].split("(")[0]
            return empfaenger in WEITE_EMPFAENGER
        return False
    if isinstance(f, ast.Name):
        # Ein unbenanntes ``walk(...)`` zaehlt als weit - die sichere
        # Richtung ist hier, eine Regel **in** der Aufsicht zu behalten.
        return f.id in WEITE_REICHWEITE or f.id == "walk"
    return False


def _hat_weite_reichweite(fn: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call) and _ist_dateidurchlauf(n) for n in ast.walk(fn)
    )


def _ist_leer(knoten: ast.AST) -> bool:
    """Ist das eine leere Sammlung - ``[]``, ``()``, ``set()``?

    **Alle drei Formen**, und das ist kein Zierrat: Befund 464 hat vier
    Pruefungen auf ``nachmessung.ohne_abschnitt`` umgestellt, das ein Tupel
    liefert. Wer hier nur ``[]`` kennt, verliert sie lautlos aus der
    Grundgesamtheit - eine Wache, die nichts mehr findet, ist gruen und leer
    (Befund 209).
    """
    if isinstance(knoten, ast.List | ast.Tuple):
        return not knoten.elts
    return (
        isinstance(knoten, ast.Call)
        and isinstance(knoten.func, ast.Name)
        and knoten.func.id == "set"
        and not knoten.args
    )


def _ist_verbot(fn: ast.AST) -> bool:
    """Behauptet dieser Test, dass etwas **nicht** vorkommt?"""
    for n in ast.walk(fn):
        if not isinstance(n, ast.Assert):
            continue
        t = n.test
        if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
            return True
        if isinstance(t, ast.Compare):
            if any(isinstance(o, ast.NotIn) for o in t.ops):
                return True
            if (
                isinstance(t.ops[0], ast.Eq)
                and len(t.comparators) == 1
                and _ist_leer(t.comparators[0])
            ):
                return True
    return False


def _gerufene_namen(fn: ast.AST) -> set[str]:
    return {
        n.func.id
        for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }


def _mit_helfern(
    fn: ast.AST, helfer: dict[str, ast.FunctionDef], *, tiefe: int = 2
) -> tuple[set[str], bool]:
    """Dateien und Weite dieses Tests **samt** der Helfer seines Moduls.

    **Die zweite Haelfte von Befund 484.** ``_literale_dateien`` sah nur in
    die Testfunktion. In ``test_berichtswache`` liegt der Dateizugriff aber
    einen Aufruf entfernt - ``_befehle()`` liest ``cli.py`` -, und damit hatte
    die Regel null literale Dateien, fiel durch beide Zweige der Einordnung
    und wurde nirgends geprueft. Genau diese Regel war dann zu eng: Befund
    482 hat den zweiten Weg in den Berichtsverlauf gefunden.
    """
    dateien = set(_literale_dateien(fn))
    weit = _hat_weite_reichweite(fn)
    gesehen: set[str] = set()
    offen: list[tuple[ast.AST, int]] = [(fn, 0)]
    while offen:
        knoten, t = offen.pop()
        if t >= tiefe:
            continue
        for name in _gerufene_namen(knoten) & set(helfer):
            if name in gesehen:
                continue
            gesehen.add(name)
            dateien |= _literale_dateien(helfer[name])
            weit = weit or _hat_weite_reichweite(helfer[name])
            offen.append((helfer[name], t + 1))
    return dateien, weit


def _verbotsregeln() -> tuple[list[tuple[str, str, str]], int]:
    """Die engen Verbotsregeln, und wie viele weite es gibt."""
    eng: list[tuple[str, str, str]] = []
    weit = 0
    for datei in TESTS:
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        helfer = {n.name: n for n in baum.body if isinstance(n, ast.FunctionDef)}
        for fn in ast.walk(baum):
            if not isinstance(fn, ast.FunctionDef):
                continue
            if not fn.name.startswith("test_") or not _ist_verbot(fn):
                continue
            dateien, ist_weit = _mit_helfern(fn, helfer)
            if ist_weit:
                # **Befund 484.** Hier stand ``weit += 1 if dateien else 0``,
                # also "weit **und** nennt zusaetzlich eine Datei". Gemessen
                # fielen damit 17 Regeln aus der Zaehlung, die gerade
                # **durch** ihren Glob weit sind und deshalb keine Datei
                # namentlich nennen. Weite heisst weite Reichweite.
                weit += 1
                continue
            if len(dateien) == 1:
                eng.append((datei.name, fn.name, next(iter(dateien))))
    return eng, weit


class TestJedeEngeVerbotsregelIstBegruendet:
    """**Die tragende Wache.** Sie verbietet nichts - sie verlangt einen Satz."""

    def test_keine_unbegruendete_enge_regel(self) -> None:
        eng, _ = _verbotsregeln()
        ohne_grund = [
            (d, f, z)
            for d, f, z in eng
            if (d, f) not in ABSICHTLICH_ENG
            and not ((d, f) in NUR_DIE_BEFEHLSDATEI and z == "cli.py")
        ]

        assert ohne_grund == [], "\n".join(
            f"{d}::{f} prueft nur {z}, aber 'nicht vorkommen' ist keine "
            f"Eigenschaft einer Datei - entweder die Reichweite erweitern "
            f"oder den Grund in ABSICHTLICH_ENG schreiben (Befund 464)."
            for d, f, z in ohne_grund
        )

    def test_die_abnahme_hat_keine_leichen(self) -> None:
        """Eine Ausnahme fuer einen Test, den es nicht mehr gibt, ist eine
        Erlaubnis ins Leere - und die naechste Regel rutscht darunter hinweg."""
        eng, _ = _verbotsregeln()
        vorhanden = {(d, f) for d, f, _ in eng}
        verwaist = sorted((set(ABSICHTLICH_ENG) | NUR_DIE_BEFEHLSDATEI) - vorhanden)

        assert verwaist == [], f"begruendet, aber nicht mehr da: {verwaist}"

    def test_jeder_grund_ist_einer(self) -> None:
        """Ein Platzhalter waere schlimmer als keine Liste."""
        for schluessel, grund in ABSICHTLICH_ENG.items():
            assert len(grund) > 60, schluessel
            assert any(c.isdigit() for c in grund) or "Laborbuch" in grund, (
                f"{schluessel}: ein Grund nennt eine Fundstelle oder die "
                f"Sache, um die es geht"
            )


class TestDerMelderUnterscheidetBaumVonDateisystem:
    """**Befund 484.** Der Erkenner selbst, in beide Richtungen - das war der
    Fehler, nicht die Regel."""

    def _fn(self, quelle: str) -> ast.FunctionDef:
        baum = ast.parse(quelle)
        return next(n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef))

    def test_ein_syntaxbaum_ist_keine_dateisuche(self) -> None:
        """Hier lag das Loch: Jede quelltextpruefende Wache parst und laeuft
        mit ``ast.walk`` - und galt damit als weit."""
        fn = self._fn(
            "def test_x():\n"
            "    baum = ast.parse(Path('cli.py').read_text())\n"
            "    for n in ast.walk(baum):\n"
            "        pass\n"
        )

        assert not _hat_weite_reichweite(fn)

    def test_ein_dateibaum_schon(self) -> None:
        fn = self._fn(
            "def test_x():\n    for w, _, _ in os.walk('research'):\n        pass\n"
        )

        assert _hat_weite_reichweite(fn)

    def test_ein_glob_auch(self) -> None:
        fn = self._fn("def test_x():\n    for p in WURZEL.glob('*.py'):\n        pass\n")

        assert _hat_weite_reichweite(fn)

    def test_ein_unbenanntes_walk_gilt_als_weit(self) -> None:
        """Die sichere Richtung: Eine Regel faelschlich fuer weit zu halten
        nimmt sie aus dieser Aufsicht - genau das war Befund 484."""
        fn = self._fn("def test_x():\n    for a in walk('.'):\n        pass\n")

        assert _hat_weite_reichweite(fn)

    def test_der_dateizugriff_eines_helfers_zaehlt_mit(self) -> None:
        """Die zweite Haelfte des Lochs: In ``test_berichtswache`` liest
        ``_befehle()`` die Datei, nicht der Test."""
        baum = ast.parse(
            "def _befehle():\n"
            "    return Path('cli.py').read_text()\n"
            "\n"
            "def test_x():\n"
            "    assert 'a' not in _befehle()\n"
        )
        helfer = {n.name: n for n in baum.body if isinstance(n, ast.FunctionDef)}
        fn = helfer["test_x"]
        dateien, weit = _mit_helfern(fn, helfer)

        assert _literale_dateien(fn) == set()
        assert dateien == {"cli.py"}
        assert not weit

    def test_und_die_weite_eines_helfers_ebenso(self) -> None:
        baum = ast.parse(
            "def _alle():\n"
            "    return [p for p in WURZEL.rglob('*.py')]\n"
            "\n"
            "def test_x():\n"
            "    assert 'a' not in _alle()\n"
        )
        helfer = {n.name: n for n in baum.body if isinstance(n, ast.FunctionDef)}
        _dateien, weit = _mit_helfern(fn=helfer["test_x"], helfer=helfer)

        assert weit


class TestDieMessungSelbst:
    """Die Zahlen aus dem Modulkopf, als Zusicherung - sonst sind sie Prosa."""

    def test_beide_bauarten_kommen_wirklich_vor(self) -> None:
        """**Hier stand erst "es gibt mehr weite als enge Regeln".** Gemessen
        sind es sieben und sieben - die Behauptung war falsch, und sie war
        meine. Was zutrifft und etwas sichert: Beide Bauarten gibt es, also
        ist die enge keine Eigenart einer einzelnen Datei."""
        eng, weit = _verbotsregeln()
        dateien = {d for d, _, _ in eng}

        assert weit and eng
        assert len(dateien) >= 3, f"enge Regeln nur in {dateien}"

    def test_die_grundgesamtheit_ist_nicht_leer(self) -> None:
        """Eine Wache, die nichts mehr findet, sichert nichts zu (Befund 209)."""
        eng, weit = _verbotsregeln()

        assert eng, "keine enge Verbotsregel gefunden - Erkenner pruefen"
        assert weit >= 5, f"nur {weit} weite Regeln - Erkenner pruefen"

    def test_die_zahlen_im_kopf_stimmen(self) -> None:
        """**Befund 484.** Der Kopf nennt vier Zahlen; vorher stand dort
        'sieben und sieben', und gemessen waren es sieben und dreissig - die
        Prosa war von 464 und die Suite seither gewachsen. Eine Zahl im Kopf,
        die nichts nachrechnet, ist eine Behauptung mit Tabelle davor.
        """
        eng, weit = _verbotsregeln()
        paare = {(d, f) for d, f, _ in eng}

        # **20 seit Befund 485**, und die Zahl war ihr eigener Beleg: Der
        # Melder jenes Befundes leitet seine Grundgesamtheit mit 'rglob' ab
        # und sichert dabei die Abwesenheit eines Namens zu - also eine neue
        # weite Verbotsregel. Dass diese Zusicherung sie gemeldet hat, ist
        # genau der Dienst, fuer den sie in 484 gebaut wurde.
        #
        # **21 seit Befund 494**, und zum zweiten Mal aus demselben Grund: Die
        # Tafel-Inventur in 'test_kerzendeutung' sucht mit 'rglob' jede Tafel
        # nach Kerzenlaenge und sichert zu, dass **keine** davon ohne Deutung
        # abgefragt wird. Eine Abwesenheit ueber den ganzen Baum ist eine
        # weite Regel; sie ist hier gewollt, denn eine vierte Tafel soll
        # auffallen, wo immer sie steht. Gemeldet hat sie diese Wache - nicht
        # ich beim Aufschreiben.
        assert weit == 21, weit
        assert len(eng) == 28, len(eng)
        assert len(paare) == 27, len(paare)
        assert len(ABSICHTLICH_ENG) == 8
        assert len(NUR_DIE_BEFEHLSDATEI) == 19
        assert paare == set(ABSICHTLICH_ENG) | NUR_DIE_BEFEHLSDATEI

    @pytest.mark.parametrize(
        "quelle",
        [
            "assert x not in text",
            "assert not treffer",
            "assert fehlend == []",
            "assert fehlend == ()",
            "assert doppelt == set()",
        ],
    )
    def test_der_erkenner_kennt_jede_form_eines_verbots(self, quelle: str) -> None:
        baum = ast.parse(f"def test_x():\n    {quelle}\n")

        assert _ist_verbot(baum.body[0])

    @pytest.mark.parametrize(
        "quelle",
        ["assert x in text", "assert len(y) == 3", "assert fehlend == [1]"],
    )
    def test_und_keine_zusicherung_die_keines_ist(self, quelle: str) -> None:
        baum = ast.parse(f"def test_x():\n    {quelle}\n")

        assert not _ist_verbot(baum.body[0])


class TestDieSperreWirdUeberallGeprueft:
    """**Der Fall, den ich zuerst falsch gelesen habe.**

    ``GateReport.passed`` verlangt ``not referenzdaten``, und die Herkunft
    kommt aus den Namen der Kursreihen. Ein ``evaluate_gates`` ohne
    Herkunftsangabe waere damit die folgenreichste Luecke, die dieses Projekt
    haben kann - Befund 283 hatte sie schon einmal.
    """

    @staticmethod
    def _aufrufstellen() -> list[str]:
        aus = []
        for p in sorted(WURZEL.rglob("*.py")):
            teile = p.relative_to(WURZEL).parts
            if "tests" in teile or ".venv" in teile or "__pycache__" in teile:
                continue
            baum = ast.parse(p.read_text(encoding="utf-8"))
            for n in ast.walk(baum):
                if (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "evaluate_gates"
                ):
                    aus.append(f"{p.relative_to(WURZEL)}:{n.lineno}")
        return aus

    def test_alle_aufrufe_liegen_in_der_reichweite_der_wache(self) -> None:
        """Gemessen, nicht angenommen: Die Wache sieht in ``research/*.py``
        und ``cli.py`` - also muessen alle Aufrufe dort liegen."""
        draussen = [
            s
            for s in self._aufrufstellen()
            if not (s.startswith("cli.py:") or s.startswith("research/"))
        ]

        assert draussen == [], (
            f"evaluate_gates ausserhalb der Reichweite von "
            f"'test_jeder_aufruf_im_projekt_nennt_seine_herkunft': {draussen}"
        )

    def test_und_es_gibt_sie_wirklich(self) -> None:
        stellen = self._aufrufstellen()

        assert len(stellen) > 20, f"nur {len(stellen)}: {stellen}"
