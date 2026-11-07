"""Ein Ladehinweis, der nur die Haelfte nennt, nimmt fuer die andere die Vorgabe.

**Befund 213.** ``cli backfill`` hat zwei Vorgaben, und beide sind fuer die
Tageskerzen falsch, auf denen alle elf Gates stehen:

* ``--von`` steht auf ``2020-03-30`` - gemessen die zweitschlechteste der
  sechs Stufen aus Befund 133 (Befund 212).
* ``--intervall`` steht auf ``1 15 60 240`` - **ohne D**.

``python -m cli backfill --von 2017-08-16``, die Zeile aus ``BEIM_NUTZER``,
laedt darum vier Intraday-Reihen ab 2017 und keine einzige Tageskerze. Und
``CandleStore.read`` faellt nicht auf Zusammenfassen zurueck: Was nicht
geladen wurde, ist leer.

Wer eines von beiden nennt, muss das andere mitnennen. Ein blosses
``python -m cli backfill`` ist etwas anderes - ein Wegweiser, keine Vorschrift.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from cli import ZULASSUNGSKORB
from research.historie import AB_TAGESKERZEN, empfohlener_start
from research.stand import BEIM_NUTZER

#: Wo nach Ladehinweisen gesucht wird - Quelltext und Anleitung.
#:
#: **Vier Dateien waren es bis Befund 463**, und die Luecke war nicht
#: theoretisch: ``deploy/WINDOWS.md`` nannte in *"Schritt 7"* ein
#: ``--intervall D`` ohne ``--von`` und ``research/seeds.py`` dasselbe - genau
#: der Fall, gegen den diese Datei gebaut ist, in zwei Dateien, in die sie nie
#: gesehen hat. Wer eine Anleitung schreibt, schreibt sie nicht dorthin, wo
#: die Wache schon steht.
QUELLEN = (
    "cli.py",
    "README.md",
    "install.py",
    "deploy/README.md",
    "deploy/WINDOWS.md",
    "research/stand.py",
    "research/reihenfolge.py",
    "research/seeds.py",
)

#: Die Befehle, die auf dem **Zulassungskorb** laufen muessen (Befunde
#: 357/359). Dieselbe Liste, die ``cli._korbwarnung`` zur Laufzeit prueft.
KORBBEFEHLE = ("backfill", "funding", "wettbewerb")

#: Eine kopierbare Befehlszeile: optional ein Kommentarzeichen und
#: Umgebungsvariablen, dann ein Python-Aufruf mit ``-m cli``.
#:
#: **Der Anker ist der Zeilenanfang**, und das ist der ganze Unterschied
#: zwischen einer Vorschrift und einer Erwaehnung. Ohne ihn trifft dasselbe
#: Muster 42 Stellen, von denen 38 Prosa in Docstrings sind ("``cli funding``
#: muss gelaufen sein") oder Laufzeithinweise fuer ein einzelnes Instrument -
#: der Fehler aus Befund 118.
#:
#: Die Umgebungsvariable davor ist nicht Zierde: ``TRADING_TROCKENLAUF=1
#: python -m cli wettbewerb --generation 9`` stand in der README und ist dem
#: ersten Entwurf dieses Musters durchgegangen.
VORSCHRIFT = re.compile(
    r"^[ \t]*(?:#[ \t]*)?(?:[A-Z_][A-Z0-9_]*=\S+[ \t]+)*"
    r"(?:[\w./\\]*python[\w.]*|\{\w+\})[ \t]+-m[ \t]+cli[ \t]+"
    r"(?P<befehl>[\w-]+)(?P<rest>[^\n#|`]*)",
    re.M,
)

#: Eine Befehlszeile, die ``backfill`` aufruft, mit allem was dahinter steht.
BEFEHL = re.compile(r"cli backfill(?P<rest>[^\n\"'\]]*)")


#: Zwei aneinandergrenzende Zeichenkettenliteralen - `"..." f"..."`.
#:
#: Python fuegt sie zusammen, ein Suchmuster ueber den Rohtext nicht. Ohne
#: diesen Schritt endet ein Hinweis am Zeilenumbruch, und ein ``--von`` in
#: der Folgezeile faellt unter den Tisch - der erste Entwurf dieses Tests hat
#: genau deshalb zwei bereits berichtigte Stellen angezeigt.
FUGE = re.compile(r"[\"']\s*\n\s*[fr]?[\"']")


def hinweise(text: str) -> list[str]:
    """Alle ``cli backfill``-Aufrufe eines Textes, auf ihre Argumente reduziert."""
    return [m.group("rest").strip() for m in BEFEHL.finditer(FUGE.sub("", text))]


def vorschriften(text: str) -> list[tuple[str, str]]:
    """Die kopierbaren Befehlszeilen eines Textes als ``(Befehl, Argumente)``."""
    return [
        (m.group("befehl"), m.group("rest").strip())
        for m in VORSCHRIFT.finditer(FUGE.sub("", text))
    ]


def genannter_korb(rest: str) -> set[str] | None:
    """Die Symbole hinter ``-m``/``--maerkte``, oder ``None`` ohne Angabe."""
    try:
        teile = shlex.split(rest)
    except ValueError:
        teile = rest.split()
    for i, x in enumerate(teile):
        if x in ("-m", "--maerkte") and i + 1 < len(teile):
            return {y.strip() for y in teile[i + 1].split(",") if y.strip()}
    return None


def behauptungen(text: str) -> list[str]:
    """Zeilen, die neun Gates **behaupten**.

    Erlaubt bleibt, ueber den Fehler zu reden ("neun Gates statt elf"), ihn zu
    zitieren, und - **gemessen notwendig** - von den *uebrigen* neun zu
    sprechen: ``research/koernung.py`` fuehrt zwei Kennzahlen ueber eine
    Leiter und sieht sich "die anderen neun Gates" dazu an. Elf minus zwei ist
    neun; eine blinde Ersetzung haette dort einen Fehler eingebaut, wo vorher
    keiner war.

    **Eine Umsetzung, zwei Wachen** (Befund 463): ``test_stand`` prueft damit
    weiter ``cli.py`` und seine Gegenproben, diese Datei alles uebrige. Zwei
    Fassungen derselben Ausnahmeliste waeren die naechste Stelle, an der sie
    auseinanderlaufen (Befund 439).
    """
    return [
        z
        for z in re.findall(r"[^\n]*neun Gates[^\n]*", text)
        if "statt elf" not in z
        and '"neun Gates"' not in z
        and not re.search(r"(uebrigen|anderen|restlichen)\s+neun Gates", z)
    ]


def behauptungsquellen() -> list[Path]:
    """Jede Datei, die ueber das System etwas **behauptet**.

    Abgeleitet und nicht gepflegt: Zwei handgefuehrte Listen laufen
    auseinander (Befund 439), und diese Regel hat eine andere natuerliche
    Reichweite als ``QUELLEN`` - sie gilt ueberall, wo das System sich selbst
    beschreibt, nicht nur dort, wo es den Nutzer anleitet.

    ``tests/`` bleibt draussen: Dort steht die Geschichte der Fehler, und ein
    Test darf den alten Stand zitieren. Das Laborbuch ebenfalls, aus demselben
    Grund.
    """
    wurzel = Path(__file__).resolve().parent.parent
    aus = [
        p
        for p in sorted(wurzel.rglob("*.py"))
        if "tests" not in p.relative_to(wurzel).parts
        and "__pycache__" not in p.parts
        and ".venv" not in p.relative_to(wurzel).parts
    ]
    aus += [wurzel / "README.md", wurzel / "deploy/README.md"]
    aus += [wurzel / "deploy/WINDOWS.md"]
    return [p for p in aus if p.is_file()]


def unvollstaendig(rest: str) -> bool:
    """Nennt dieser Hinweis genau eines von Intervall und Datum?

    Beides oder keines ist in Ordnung. Genau eines heisst: Fuer das andere
    gilt stillschweigend eine Vorgabe, die fuer Tageskerzen falsch ist.
    """
    hat_intervall = "--intervall" in rest or re.search(r"(^|\s)-i(\s|$)", rest)
    hat_datum = "--von" in rest
    return bool(hat_intervall) != bool(hat_datum)


class TestKeinHalberLadehinweis:
    def test_kein_hinweis_nennt_nur_eines_von_beidem(self) -> None:
        gefunden: list[tuple[str, str]] = []
        for quelle in QUELLEN:
            for rest in hinweise(Path(quelle).read_text()):
                if unvollstaendig(rest):
                    gefunden.append((quelle, rest))

        assert gefunden == [], (
            "Ladehinweis nennt Intervall oder Datum, nicht beides - fuer das "
            "fehlende gilt dann eine Vorgabe, die fuer Tageskerzen falsch ist."
        )

    def test_die_regel_faende_den_alten_stand(self) -> None:
        """Die Gegenprobe: genau die beiden Zeilen, die es gab."""
        assert unvollstaendig("--von 2017-08-16")
        assert unvollstaendig("--intervall 15")
        assert unvollstaendig("-i D")

    def test_beides_und_keines_sind_in_ordnung(self) -> None:
        assert not unvollstaendig("")
        assert not unvollstaendig("--intervall D --von 2017-08-16")
        assert not unvollstaendig("-i D --von 2017-08-16")


class TestJedeVorschriftLaedtDenKorb:
    """**Befund 463.** Der Korb war an **einer** Stelle gewacht.

    ``BEIM_NUTZER`` traegt ihn in allen sechs Zeilen, und
    ``test_nutzerbefehle`` prueft das seit Befund 357. Ausserhalb davon stand
    er in **keiner** der acht kopierbaren Vorschriften - darunter der erste
    Befehlsblock der README, also genau die Zeile, mit der der Nutzer die
    Sperre aufheben soll, und die nummerierten Schritte der beiden
    Installationsanleitungen.

    Gemessen ist der Unterschied und er ist nicht umkehrbar: BTC allein haelt
    5 von 11 Gates gegen 9 von 11 auf dem Korb (264/318), und der Wettbewerb
    bucht seine Versuche rundenweise - ein zu tiefer Zaehler waere das
    einzige, was diese Latte je senken koennte.
    """

    def test_keine_vorschrift_laesst_ein_bein_aus(self) -> None:
        fehlend: list[tuple[str, str, str]] = []
        for quelle in QUELLEN:
            for befehl, rest in vorschriften(Path(quelle).read_text()):
                if befehl not in KORBBEFEHLE:
                    continue
                korb = genannter_korb(rest)
                if korb is None or not set(ZULASSUNGSKORB) <= korb:
                    fehlend.append((quelle, befehl, rest))

        assert fehlend == [], (
            f"Vorschrift ohne vollen Zulassungskorb "
            f"({', '.join(ZULASSUNGSKORB)}):\n"
            + "\n".join(f"  {q}: cli {b} {r}" for q, b, r in fehlend)
        )

    def test_es_gibt_ueberhaupt_solche_vorschriften(self) -> None:
        """Sonst prueft der Test darueber eine leere Menge - der Fehler aus
        Befund 209, nur in dieser Datei."""
        gefunden = [
            (q, b)
            for q in QUELLEN
            for b, _ in vorschriften(Path(q).read_text())
            if b in KORBBEFEHLE
        ]

        assert len(gefunden) >= 8, f"nur {len(gefunden)} gefunden: {gefunden}"

    def test_jede_anleitung_kommt_vor(self) -> None:
        """Die Reichweite selbst, als Zusicherung: Eine Anleitung, die hier
        fehlt, wird von keiner Regel dieser Datei gesehen."""
        mit_vorschrift = {
            q
            for q in QUELLEN
            for b, _ in vorschriften(Path(q).read_text())
            if b in KORBBEFEHLE
        }

        for anleitung in ("README.md", "deploy/README.md", "deploy/WINDOWS.md"):
            assert anleitung in mit_vorschrift, anleitung

    def test_die_regel_faende_den_alten_stand(self) -> None:
        """**Die Gegenprobe** - genau die Zeile, die in der README stand."""
        alt = "python -m cli backfill --intervall D --von 2017-08-16"
        neu = (
            "python -m cli backfill -m BTCUSDT,ETHUSDT --intervall D "
            "--von 2017-08-16"
        )

        assert genannter_korb(vorschriften(alt)[0][1]) is None
        assert set(ZULASSUNGSKORB) <= (genannter_korb(vorschriften(neu)[0][1]) or set())

    def test_sie_faende_auch_einen_halben_korb(self) -> None:
        """Ein Bein zu nennen ist nicht dasselbe wie den Korb zu nennen."""
        halb = "python -m cli wettbewerb -m BTCUSDT --generation 9"

        korb = genannter_korb(vorschriften(halb)[0][1])
        assert korb == {"BTCUSDT"}
        assert not set(ZULASSUNGSKORB) <= korb

    def test_die_umgebungsvariable_davor_schuetzt_nicht(self) -> None:
        """Der Fall, der dem ersten Entwurf des Musters durchgegangen ist."""
        zeile = "TRADING_TROCKENLAUF=1 python -m cli wettbewerb --generation 9"

        assert vorschriften(zeile), "Zeile mit Umgebungsvariable nicht erkannt"
        assert vorschriften(zeile)[0][0] == "wettbewerb"

    def test_eine_erwaehnung_ist_keine_vorschrift(self) -> None:
        """Die andere Haelfte, und der Grund fuer den Zeilenanker: Prosa und
        Laufzeithinweise fuer ein einzelnes Instrument bleiben erlaubt."""
        prosa = 'console.print("Weiter mit: python -m cli backfill")'
        im_satz = "``cli funding`` muss gelaufen sein, sonst fehlen die Raten."

        assert vorschriften(prosa) == []
        assert vorschriften(im_satz) == []


class TestElfGatesUeberallWoEtwasBehauptetWird:
    """**Befund 463, dieselbe Lehre an einer zweiten Regel.**

    Befund 210 hat *"neun Gates"* im Docstring des Analysten berichtigt und
    eine Wache dazugestellt - sie sieht in **cli.py**. Gemessen lebte die
    falsche Zahl danach an **sieben** Stellen in fuenf Dateien weiter, eine
    davon in ``research/analyst.py``: genau dem Modul, nach dem der
    Registereintrag benannt ist.

    Die Regel war richtig, ihre Reichweite war eine Datei.
    """

    _behauptungen = staticmethod(behauptungen)

    def test_keine_datei_behauptet_mehr_neun_gates(self) -> None:
        gefunden = [
            (p.name, z.strip())
            for p in behauptungsquellen()
            for z in behauptungen(p.read_text(encoding="utf-8"))
        ]

        assert gefunden == [], (
            "Das System hat elf Gates - diese Stellen behaupten neun:\n"
            + "\n".join(f"  {n}: {z[:70]}" for n, z in gefunden)
        )

    def test_die_reichweite_ist_mehr_als_eine_datei(self) -> None:
        """Der Kern des Befundes: Die alte Wache sah in genau eine Datei."""
        quellen = behauptungsquellen()

        assert len(quellen) > 50, f"nur {len(quellen)} Dateien"
        namen = {p.name for p in quellen}
        for pflicht in ("analyst.py", "admission.py", "exits.py", "config.py"):
            assert pflicht in namen, pflicht

    def test_die_regel_faende_jeden_der_sieben_faelle(self) -> None:
        """**Die Gegenprobe**, in den Formen, in denen es wirklich dastand."""
        damals = (
            "    KI  ->  JSON-Genom  ->  Compiler  ->  neun Gates\n",
            "das entscheiden dieselben neun Gates wie bei einem von Hand\n",
            "    Genom -> Compiler -> Walk-Forward -> neun Gates -> zugelassen\n",
            "Kandidaten, die alle neun Gates bestanden haben, liegen die\n",
            '    """Was hier liegt, hat die neun Gates bestanden."""\n',
            "cli research        # Walk-Forward + neun Gates\n",
        )
        for zeile in damals:
            assert self._behauptungen(zeile), zeile

    def test_und_liesse_die_uebrigen_neun_stehen(self) -> None:
        """Die Ausnahme, ohne die diese Wache Schaden anrichtet."""
        richtig = (
            "Und was die uebrigen neun Gates dazu sagen (Befund 96)\n",
            "Zwei Kennzahlen ueber die Leiter zu fahren und die anderen neun "
            "Gates nicht anzusehen waere eine Annahme gewesen.\n",
        )
        for zeile in richtig:
            assert self._behauptungen(zeile) == [], zeile

    def test_und_ueber_den_fehler_reden_bleibt_erlaubt(self) -> None:
        assert self._behauptungen("er nannte neun Gates statt elf\n") == []
        assert self._behauptungen('bis 210 stand hier "neun Gates"\n') == []


class TestDerErsteBefehlDenJemandSieht:
    """``install.py`` druckt drei Schritte, und Schritt 2 laedt die Daten.

    Diese Zeile baut sich aus einer f-Zeichenkette zusammen und ist damit
    keine Befehlszeile im Sinne von ``VORSCHRIFT`` - die Wache oben sieht sie
    nicht. Sie steht hier ausdruecklich, weil sie das **erste** ist, was
    jemand nach der Installation liest.
    """

    @staticmethod
    def _schritt_zwei() -> str:
        text = Path("install.py").read_text(encoding="utf-8")
        return next(z for z in text.splitlines() if "-m cli backfill" in z)

    def test_sie_nennt_den_korb(self) -> None:
        zeile = self._schritt_zwei()

        for symbol in ZULASSUNGSKORB:
            assert symbol in zeile, zeile

    def test_sie_nennt_tageskerzen_und_das_datum(self) -> None:
        zeile = self._schritt_zwei()

        assert "--intervall D" in zeile
        assert AB_TAGESKERZEN in zeile


class TestDieZeileFuerDenNutzer:
    """Die eine Zeile, an der die Zulassung haengt."""

    @staticmethod
    def _backfill() -> str:
        return next(b for b, _ in BEIM_NUTZER if "backfill" in b)

    def test_sie_laedt_tageskerzen(self) -> None:
        """Ohne '-i D' laedt der Befehl 1m/15m/1h/4h - und keine Tageskerze."""
        befehl = self._backfill()

        assert "--intervall D" in befehl
        assert AB_TAGESKERZEN in befehl

    def test_das_datum_ist_das_gemessene(self) -> None:
        assert empfohlener_start("D") in self._backfill()

    def test_die_begruendung_nennt_das_intervall(self) -> None:
        """Sonst kuerzt es beim naechsten Mal jemand wieder weg."""
        warum = next(w for b, w in BEIM_NUTZER if "backfill" in b)

        assert "Tageskerzen" in warum
        assert "1m/15m/1h/4h" in warum


class TestDieVorgabenSindWirklichSo:
    """Die Behauptung, auf der alles hier steht - gemessen statt geglaubt."""

    def test_backfill_laedt_von_sich_aus_keine_tageskerzen(self) -> None:
        import cli
        from core.models import Interval

        assert Interval.D1 not in cli.DEFAULT_INTERVALS

    def test_der_speicher_fasst_nicht_selbst_zusammen(self) -> None:
        """``CandleStore.read`` kennt keinen Rueckfall auf feinere Kerzen.

        Gaebe es ihn, waere das alles halb so wichtig - dann wuerde eine
        fehlende Tagesreihe aus den 15-Minuten-Kerzen entstehen.
        """
        import inspect

        from data.store import CandleStore

        quelle = inspect.getsource(CandleStore.read)

        assert "resample" not in quelle
