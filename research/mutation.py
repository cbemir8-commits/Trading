"""Varianten aus den besten Kandidaten - ohne Modellaufruf, ohne Kosten.

Der Gedanke
-----------
Ein Dauerlauf, der immer denselben Katalog prueft, lernt nichts. Er braucht
neue Kandidaten. Die koennen von der Research-KI kommen - das kostet Geld je
Vorschlag - oder aus systematischer Abwandlung dessen, was schon am weitesten
kam. Das hier ist der zweite Weg.

Abgewandelt wird immer nur **eine** Sache auf einmal: eine Periode, eine
Schwelle, die Stopweite, ein Ziel. Das ist keine Sparsamkeit, sondern
Voraussetzung dafuer, dass man aus dem Ergebnis etwas ablesen kann. Wer fuenf
Dinge gleichzeitig aendert und ein besseres Ergebnis bekommt, weiss hinterher
nicht, welches davon es war - und hat mit hoher Wahrscheinlichkeit nur das
Rauschen besser getroffen.

Die unbequeme Seite
-------------------
Jede Variante ist ein weiterer Versuch, und jeder Versuch macht die
Zulassungshuerde fuer **alle** hoeher. Die Deflated Sharpe Ratio rechnet genau
das ein: Wer lange genug sucht, findet immer etwas, das gut aussieht. Der
Versuchszaehler ist die Gegenmassnahme, und ein Dauerlauf treibt ihn schnell
nach oben.

Das ist kein Fehler im Aufbau, sondern der Preis des Suchens - und er ist
sichtbar gemacht, statt ignoriert zu werden. Ein System, das ohne diesen
Zaehler endlos sucht, findet garantiert einen Champion. Er waere nur nichts
wert.

Deshalb werden Varianten **nur aus Kandidaten gebildet, die schon nahe dran
waren**. Wild zu streuen kostet Versuche und bringt nichts.
"""

from __future__ import annotations

import random
from dataclasses import replace as _replace

import structlog

from strategy.genome import Condition, Genome, Operand, StopSpec, TargetSpec
from strategy.indicators import REGISTRY

log = structlog.get_logger(__name__)

#: Um wieviel eine Periode je Schritt verschoben wird (Anteil).
PERIODEN_SCHRITT = 0.3

#: Um wieviel eine Konstante je Schritt verschoben wird (Anteil).
SCHWELLEN_SCHRITT = 0.25


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _vary_period(name: str, params: dict, rng: random.Random) -> dict | None:
    """Eine Periode innerhalb ihrer erlaubten Grenzen verschieben."""
    if name not in REGISTRY:
        return None
    _, spec = REGISTRY[name]
    kandidaten = [k for k in params if k in spec.param_bounds]
    if not kandidaten:
        return None

    schluessel = rng.choice(kandidaten)
    low, high = spec.param_bounds[schluessel]
    alt = params[schluessel]
    richtung = rng.choice([-1, 1])
    neu = round(alt * (1 + richtung * PERIODEN_SCHRITT))
    neu = int(_clamp(neu, low, high))
    if neu == alt:
        return None
    return {**params, schluessel: neu}


def _operand_varianten(operand: Operand, rng: random.Random) -> Operand | None:
    if operand.kind == "constant":
        alt = float(operand.value)
        richtung = rng.choice([-1, 1])
        # Bei null greift eine relative Verschiebung nicht - dann absolut.
        neu = alt * (1 + richtung * SCHWELLEN_SCHRITT) if alt else richtung * 0.5
        return Operand(kind="constant", value=round(neu, 4))
    if operand.kind == "indicator":
        params = _vary_period(operand.name, dict(operand.params), rng)
        if params is None:
            return None
        return Operand(kind="indicator", name=operand.name, params=params)
    return None


def _vary_conditions(
    conditions: list[Condition], rng: random.Random
) -> list[Condition] | None:
    if not conditions:
        return None
    index = rng.randrange(len(conditions))
    ziel = conditions[index]

    seiten = [("left", ziel.left), ("right", ziel.right)]
    rng.shuffle(seiten)
    for seite, operand in seiten:
        neu = _operand_varianten(operand, rng)
        if neu is None:
            continue
        ersetzt = _replace(ziel, **{seite: neu}) if hasattr(ziel, "__dataclass_fields__") else ziel.model_copy(update={seite: neu})
        return [*conditions[:index], ersetzt, *conditions[index + 1 :]]
    return None


def _vary_stop(stop: StopSpec, rng: random.Random) -> StopSpec | None:
    richtung = rng.choice([-1, 1])
    if stop.kind == "atr":
        neu = round(_clamp(stop.multiple * (1 + richtung * 0.3), 0.3, 6.0), 2)
        if neu == stop.multiple:
            return None
        return stop.model_copy(update={"multiple": neu})
    neu = round(_clamp(stop.percent * (1 + richtung * 0.3), 0.15, 25.0), 3)
    if neu == stop.percent:
        return None
    return stop.model_copy(update={"percent": neu})


def _vary_targets(targets: list[TargetSpec], rng: random.Random) -> list[TargetSpec] | None:
    """Alle Ziele gemeinsam strecken oder stauchen.

    Einzeln zu verschieben wuerde die Reihenfolge zerstoeren - ein naeheres
    Ziel hinter einem ferneren wird nie erreicht, und die Validierung lehnt es
    ohnehin ab.
    """
    faktor = rng.choice([0.75, 1.35])
    neu = []
    for target in targets:
        rr = round(_clamp(target.rr * faktor, 0.3, 20.0), 2)
        neu.append(target.model_copy(update={"rr": rr}))
    if [t.rr for t in neu] == [t.rr for t in targets]:
        return None
    if len({t.rr for t in neu}) != len(neu):
        return None
    return neu


#: Die Stellschrauben, je eine Aenderung. Reihenfolge egal - es wird gewuerfelt.
SCHRAUBEN = ("entry", "filter", "exit", "stop", "targets", "cooldown", "hold")


def mutate(genome: Genome, rng: random.Random | None = None) -> Genome | None:
    """Eine einzelne Abwandlung. ``None``, wenn keine moeglich war.

    Der Name traegt den Hinweis auf die Herkunft. Das ist kein Schmuck: In der
    Bestenliste steht spaeter nebeneinander, was aus dem Katalog stammt und was
    daraus abgeleitet wurde - und ob Ableiten ueberhaupt je etwas gebracht hat.
    """
    rng = rng or random.Random()
    schrauben = list(SCHRAUBEN)
    rng.shuffle(schrauben)

    for schraube in schrauben:
        aenderung: dict = {}

        if schraube == "entry":
            seite = "entry_long" if genome.entry_long else "entry_short"
            neu = _vary_conditions(getattr(genome, seite), rng)
            if neu:
                aenderung = {seite: neu}
        elif schraube == "filter":
            neu = _vary_conditions(genome.filters, rng)
            if neu:
                aenderung = {"filters": neu}
        elif schraube == "exit":
            seite = "exit_long" if genome.exit_long else "exit_short"
            neu = _vary_conditions(getattr(genome, seite), rng)
            if neu:
                aenderung = {seite: neu}
        elif schraube == "stop":
            neu = _vary_stop(genome.stop, rng)
            if neu:
                aenderung = {"stop": neu}
        elif schraube == "targets":
            neu = _vary_targets(genome.targets, rng)
            if neu:
                aenderung = {"targets": neu}
        elif schraube == "cooldown":
            neu = int(_clamp(genome.cooldown_bars + rng.choice([-4, 4]), 0, 200))
            if neu != genome.cooldown_bars:
                aenderung = {"cooldown_bars": neu}
        elif schraube == "hold" and genome.max_hold_bars:
            neu = int(_clamp(genome.max_hold_bars * rng.choice([0.6, 1.5]), 1, 2000))
            if neu != genome.max_hold_bars:
                aenderung = {"max_hold_bars": neu}

        if not aenderung:
            continue

        stamm = genome.name.split(" [")[0]
        aenderung["name"] = f"{stamm} [Variante {schraube}]"[:80]
        try:
            return genome.model_copy(update=aenderung)
        except Exception:  # Validierung des Genoms hat das letzte Wort
            continue

    return None


def breed(
    genomes: list[Genome], count: int, *, seed: int | None = None
) -> list[Genome]:
    """Aus den besten Kandidaten neue Varianten bilden.

    Doppelte werden aussortiert - zwei identische Regelwerke waeren derselbe
    Versuch, wuerden aber zweimal gezaehlt und die Huerde fuer alle anderen
    unnoetig anheben.
    """
    if not genomes or count <= 0:
        return []

    rng = random.Random(seed)
    gesehen = {g.genome_id for g in genomes}
    varianten: list[Genome] = []

    # Grosszuegig viele Versuche: Nicht jede Abwandlung ist moeglich, und
    # Doppelte fallen zusaetzlich weg.
    for _ in range(count * 20):
        if len(varianten) >= count:
            break
        kind = mutate(rng.choice(genomes), rng)
        if kind is None or kind.genome_id in gesehen:
            continue
        gesehen.add(kind.genome_id)
        varianten.append(kind)

    log.info("varianten.gebildet", gewuenscht=count, erzeugt=len(varianten))
    return varianten
