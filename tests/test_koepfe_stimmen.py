"""Steht in jedem Modulkopf dieselbe Zahl wie in seinen Daten?

**Befund 224.** Drei Module dieses Projekts tragen ihre Messung zweimal: als
Tabelle im Kopf und als Daten darunter. Zwei Fassungen derselben Zahl laufen
auseinander, sobald eine gepflegt und die andere gerechnet wird - genau das
ist in ``erfuellung`` passiert (Befund 223), und dort hat es drei
Betriebspunkte in einem Satz gemischt.

Befund 223 hat eine Wache dagegen gebaut, fuer dieses eine Modul. Die Lehre
aus Befund 217 - *"eine Wache ist kein Zustand, sondern eine Stelle"* - gilt
aber auch fuer die Wache selbst: ``historie`` (seit Befund 212) und
``zeitskala`` (seit 218) haben dieselbe Bauart und hatten keine.

Nachgemessen: Beide stimmen heute. Sie standen nur ungeprueft.

Warum die Zahlen hier von Hand ausgewaehlt werden
-------------------------------------------------
Ein Waechter, der **alle** Felder aller Datensaetze im Kopf sucht, meldet
Fehlalarm - ``Skalenstufe.bloecke`` etwa ist eine abgeleitete Groesse, die im
Kopf bewusst nicht steht, dort steht "je Block". Und eine Wache mit
Fehlalarmen wird abgeschaltet (Befund 223).

Allgemein ist deshalb nicht die Auswahl, sondern die **Abdeckung**:
``test_jedes_modul_mit_daten_wird_geprueft`` findet Module mit einem
``GEMESSEN`` selbst und verlangt, dass sie hier stehen.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

MODULE = (
    "research.historie",
    "research.zeitskala",
    "research.erfuellung",
    "research.koernung",
    "research.formgrenze",
)


def _zahlen(modul: str) -> list[tuple[str, str]]:
    """Die Werte, die im Kopf dieses Moduls wiederzufinden sein muessen."""
    m = importlib.import_module(modul)
    aus: list[tuple[str, str]] = []

    def komma(wert: float, stellen: int) -> str:
        return f"{wert:.{stellen}f}".replace(".", ",")

    if modul == "research.historie":
        for s in m.GEMESSEN.stufen:
            aus += [
                (s.von, s.von),
                (s.von, str(s.tage)),
                (s.von, str(s.trades)),
                (s.von, str(s.effektiv)),
                (s.von, komma(s.guete, 4)),
                (s.von, komma(s.dsr, 4)),
            ]
    elif modul == "research.zeitskala":
        for name, leiter in m.GEMESSEN.items():
            for s in leiter.stufen:
                aus += [
                    (f"{name}/{s.name}", s.name),
                    (f"{name}/{s.name}", komma(s.je_block, 1)),
                    (f"{name}/{s.name}", komma(s.icc, 3)),
                    (f"{name}/{s.name}", komma(s.quote, 3)),
                ]
    elif modul == "research.erfuellung":
        for p in m.GEMESSEN:
            anteil = p.anteil
            assert anteil is not None
            aus += [
                (p.regel, p.regel),
                (p.regel, str(p.effektiv)),
                (p.regel, komma(p.guete, 3)),
                (p.regel, komma(p.latte, 3)),
                (p.regel, komma(abs(anteil), 3)),
            ]
    elif modul == "research.koernung":
        # **Nur die Stufen, die der Kopf nennt.** Er zeigt sechs von
        # vierzehn, und das ist seine Sache - die Regel ist nicht "der Kopf
        # traegt alle Daten", sondern "der Kopf widerspricht ihnen nicht".
        # Eine **Zeile** der Tabelle, nicht irgendein Vorkommen des Betrags:
        # "2.000 EUR" steht auch in der Prosa und als Spalte einer anderen
        # Tabelle. Ein zu weiter Abgleich meldet Fehlalarm, und der schaltet
        # die Wache ab (Befund 223).
        zeilen = [
            z.strip()
            for z in (m.__doc__ or "").splitlines()
            if "%" in z and "EUR" in z
        ]
        for s in m.GEMESSEN:
            marke = f"{s.kapital:,.0f}".replace(",", ".") + " EUR"
            passende = [z for z in zeilen if z.startswith(marke)]
            if not passende:
                continue
            zeile = passende[0]
            aus += [
                (marke, marke),
                (marke + " (in seiner Zeile)", komma(s.cagr, 2)),
                (marke + " (in seiner Zeile)", komma(s.rueckgang, 2)),
            ]
            for wert in (komma(s.cagr, 2), komma(s.rueckgang, 2)):
                assert wert in zeile, f"{marke}: {wert} steht nicht in seiner Zeile"
    elif modul == "research.formgrenze":
        # Der Kopf nennt die drei Wege am heutigen Punkt. Sie werden
        # gerechnet, also muessen sie mit der Rechnung uebereinstimmen
        # (Befund 225).
        from research.referenz import SPOTPUNKT

        for weg in m.am_punkt(SPOTPUNKT):
            schiefe_max, dsr_max = weg.hoechstwert
            aus.append((weg.name, weg.name))
            aus.append((weg.name, komma(dsr_max, 4)))
            aus.append((weg.name, komma(schiefe_max, 2)))
            if weg.schwelle is not None:
                aus.append((weg.name, komma(weg.schwelle, 2)))
        aus.append(("Linie", komma(m.LINIE_STEIGUNG, 3)))
        aus.append(("Linie", komma(m.LINIE_ABSCHNITT, 3)))
    else:  # pragma: no cover - der Abdeckungstest verhindert das
        raise AssertionError(f"keine Auswahl fuer {modul}")
    return aus


@pytest.mark.parametrize("modul", MODULE)
def test_der_kopf_traegt_die_daten(modul: str) -> None:
    m = importlib.import_module(modul)
    kopf = m.__doc__ or ""

    fehlt = [(wo, zahl) for wo, zahl in _zahlen(modul) if zahl not in kopf]

    assert fehlt == [], f"{modul}: im Kopf fehlt {fehlt[:5]}"


@pytest.mark.parametrize("modul", MODULE)
def test_die_auswahl_ist_nicht_leer(modul: str) -> None:
    """Sonst besteht der Test darueber, weil er nichts prueft."""
    assert len(_zahlen(modul)) >= 12


def test_die_regel_faende_eine_abweichung() -> None:
    """**Die Gegenprobe.** Genau der Fall aus Befund 223: eine Zahl im Kopf,
    die nicht mehr zu den Daten passt."""
    from research.erfuellung import GEMESSEN

    kopf_von_damals = (
        "Bei n_eff 1830 verlangt die Schwelle 0,0968 je Trade statt 0,3406."
    )
    tag = next(p for p in GEMESSEN if p.intervall == "D")

    assert f"{tag.noetig_je_trade:.4f}".replace(".", ",") not in kopf_von_damals


def test_jedes_modul_mit_daten_wird_geprueft() -> None:
    """**Der allgemeine Teil.** Ein viertes Modul mit ``GEMESSEN`` bekommt
    die Wache nicht geschenkt - es faellt hier auf."""
    import research

    gefunden = set()
    for info in pkgutil.iter_modules(research.__path__):
        name = f"research.{info.name}"
        modul = importlib.import_module(name)
        if hasattr(modul, "GEMESSEN"):
            gefunden.add(name)

    assert gefunden <= set(MODULE), (
        f"Module mit GEMESSEN, die hier nicht geprueft werden: "
        f"{sorted(gefunden - set(MODULE))}"
    )
