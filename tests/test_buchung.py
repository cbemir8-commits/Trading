"""Welcher Befehl bucht einen Versuch? - Befund 440.

Der Versuchszaehler setzt die Latte des haertesten Gates: Jeder gebuchte
Versuch senkt den Deflated Sharpe fuer **alle** kuenftigen Kandidaten
(Befund 232). Ein Befehl, der Hypothesen prueft und nicht bucht, haelt die
Latte zu niedrig - und das ist die gefaehrliche Richtung.

Dreiundzwanzig Befehle fahren die Zulassungsstrecke, **acht** buchen. Dass
die uebrigen nicht buchen, ist ueberwiegend richtig: Sie messen denselben
Kandidaten nach, und eine Nachmessung ist keine Hypothese - 'cli
nachpruefung' sagt es in seiner eigenen Kopfzeile ("Versuche 203
unveraendert - Nachmessen ist kein Versuch").

**Die Falle, in die ich zuerst getappt bin**: 'vorschlag' bucht nicht selbst,
sondern ueber '_miss_vorschlaege'. Ein Quellcheck am Befehl allein haette
ausgerechnet die Stelle uebersehen, an der KI-Vorschlaege gezaehlt werden -
und die muessen gezaehlt werden, das sagt der Kopf von 'analyst.py'
ausdruecklich.
"""

from __future__ import annotations

import inspect

import pytest

import cli

#: Die Marken, an denen eine Buchung zu erkennen ist.
BUCHMARKEN: tuple[str, ...] = ("_verzeichne(", "save_trials(")

#: Helfer, die selbst buchen - ueber sie bucht ein Befehl **mittelbar**.
#:
#: Ohne diese Liste prueft ein Quellcheck nur die erste Ebene, und genau
#: dort fehlt 'vorschlag' (Befund 440).
BUCHENDE_HELFER: tuple[str, ...] = ("_miss_vorschlaege", "_verzeichne")

#: Die Befehle, die einen Versuch buchen - gemessen, nicht gepflegt: Der Test
#: darunter rechnet die Menge aus dem Quelltext und vergleicht.
#:
#: **Wer hier etwas aendert, aendert die Latte des haertesten Gates.** Ein
#: neuer buchender Befehl ist richtig, wenn er Hypothesen prueft, und falsch,
#: wenn er nachmisst; ein Befehl, der aufhoert zu buchen, haelt die Latte zu
#: niedrig. Beides soll auffallen.
BUCHT: frozenset[str] = frozenset(
    {
        "adaptiv",
        "korb",
        "landschaft",
        "machbarkeit",
        "research",
        "verbund",
        "vorschlag",
        "wettbewerb",
    }
)


def _bucht(name: str) -> bool:
    """Ob dieser Befehl bucht - **mittelbar eingeschlossen**."""
    fn = getattr(cli, name, None)
    if fn is None:
        return False
    try:
        quelle = inspect.getsource(fn)
    except (OSError, TypeError):
        return False
    if any(m in quelle for m in BUCHMARKEN):
        return True
    return any(f"{h}(" in quelle for h in BUCHENDE_HELFER)


def _befehle() -> list[str]:
    """Alle CLI-Befehle - erkannt daran, dass sie Optionen deklarieren."""
    gefunden = []
    for name in dir(cli):
        fn = getattr(cli, name)
        if not callable(fn) or name.startswith("_"):
            continue
        try:
            quelle = inspect.getsource(fn)
        except (OSError, TypeError):
            continue
        if "typer.Option" in quelle:
            gefunden.append(name)
    return sorted(gefunden)


class TestDieBuchendeMengeStehtFest:
    def test_sie_ist_die_gemessene(self) -> None:
        """Gerechnet aus dem Quelltext, nicht gepflegt - sonst waere diese
        Liste die zweite Quelle (Befund 439)."""
        gemessen = {n for n in _befehle() if _bucht(n)}

        assert gemessen == set(BUCHT), sorted(gemessen ^ set(BUCHT))

    def test_es_sind_acht(self) -> None:
        assert len(BUCHT) == 8

    def test_jeder_davon_gibt_es_wirklich(self) -> None:
        for name in BUCHT:
            assert getattr(cli, name, None) is not None, name


class TestMittelbareBuchungZaehltMit:
    def test_vorschlag_bucht_ueber_den_helfer(self) -> None:
        """**Die Falle aus Befund 440.** Ein Quellcheck am Befehl allein
        haette die Stelle uebersehen, an der KI-Vorschlaege gezaehlt werden."""
        quelle = inspect.getsource(cli.vorschlag)

        assert not any(m in quelle for m in BUCHMARKEN)
        assert "_miss_vorschlaege(" in quelle
        assert _bucht("vorschlag")

    def test_der_helfer_bucht_wirklich(self) -> None:
        quelle = inspect.getsource(cli._miss_vorschlaege)

        assert any(m in quelle for m in BUCHMARKEN)


class TestWerNachmisstBuchtNicht:
    """Eine Nachmessung ist keine Hypothese - der Zaehler darf dafuer nicht
    steigen, sonst hebt jedes Nachrechnen die Latte."""

    def test_die_messbefehle_buchen_nicht(self) -> None:
        for name in ("stand", "abstand", "aufteilung", "nachpruefung", "decke",
                     "anatomie", "instrument", "streuung", "finanzierung"):
            assert not _bucht(name), name

    def test_marktkombinationen_bucht_nicht(self) -> None:
        """**Mein Fehlgriff in Befund 436**: Dort habe ich diesen Befehl
        abgelehnt, weil er "fuenfzehn Versuche" kosten wuerde. Er bucht
        keinen."""
        assert not _bucht("marktkombinationen")

    def test_und_sagt_in_seinem_docstring_warum(self) -> None:
        """Und zwar mit einer Begruendung, die traegt: Ein Marktkorb ist
        dieselbe Regel auf breiterer Grundlage, kein weiterer Einfall. Sechs
        Haltedauer-Deckel (Befund 416) sind dagegen sechs Regeln."""
        # **Ueber die Umbrueche hinweg** (Befund 420/430): Der Satz laeuft
        # im Docstring ueber einen Zeilenwechsel, und eine Zeichenkette
        # darueber zu pruefen bricht beim naechsten Umformatieren.
        doc = " ".join((inspect.getdoc(cli.marktkombinationen) or "").split())

        assert "Kostet keinen Versuch" in doc
        assert "mehr *Daten*, nicht mehr Einfaelle" in doc


class TestDieNachmessungAusVierhundertvierzig:
    """Die vier Koerbe aus ``erlaubter_gueteverlust``, am Spot-Punkt
    nachgefahren. Trades und Jahresrendite treffen exakt; der DSR liegt
    gleichmaessig tiefer, und das ist **ganz** der Versuchszaehler."""

    #: Korb: Trades, DSR damals (198 Versuche), DSR heute (203), CAGR.
    GEMESSEN: tuple[tuple[str, int, float, float, float], ...] = (
        ("BTC+ETH", 158, 0.5881, 0.5826, 14.34),
        ("BTC+ETH+LTC", 266, 0.4855, 0.4801, 11.50),
        ("BTC+ETH+XRP", 267, 0.4609, 0.4555, 11.32),
        ("BTC+ETH+LTC+XRP", 375, 0.4175, 0.4123, 9.95),
    )

    def test_der_abstand_ist_gleichmaessig(self) -> None:
        """Eine Datendrift waere ungleichmaessig - diese ist es nicht."""
        abstaende = [alt - neu for _, _, alt, neu, _ in self.GEMESSEN]

        assert max(abstaende) - min(abstaende) < 0.0005, abstaende

    def test_und_er_ist_der_versuchszaehler(self) -> None:
        """198 gegen 203 Versuche - gerechnet mit derselben Formel, die das
        Gate benutzt."""
        from research.erreichbarkeit import _dsr
        from research.referenz import SPOTPUNKT as P

        damals = _dsr(P.guete, P.effektiv, 198, P.schiefe, P.woelbung)
        heute = _dsr(P.guete, P.effektiv, P.versuche, P.schiefe, P.woelbung)

        assert P.versuche == 203
        assert abs(damals - 0.5881) < 0.0002, damals
        assert abs(heute - 0.5826) < 0.0002, heute

    def test_das_bestaetigt_den_preis_aus_342(self) -> None:
        """Fuenf Versuche kosten 0,0055 DSR-Punkte - also 0,0011 je Versuch,
        genau die Zahl aus Befund 342. Zwei Wege, dieselbe Zahl."""
        je_versuch = (0.5881 - 0.5826) / 5

        assert abs(je_versuch - 0.0011) < 0.0001, je_versuch

    def test_mehr_maerkte_kosten_deflated_sharpe(self) -> None:
        """Die Aussage, die 'erlaubter_gueteverlust' traegt: 2,37-mal so
        viele Trades, und der DSR faellt um 29 %."""
        erst = self.GEMESSEN[0]
        letzt = self.GEMESSEN[-1]

        assert letzt[1] / erst[1] == pytest.approx(2.37, abs=0.01)
        assert (erst[3] - letzt[3]) / erst[3] == pytest.approx(0.292, abs=0.002)
