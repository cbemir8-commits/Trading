"""Welches Gate ist dem Durchfallen am naechsten? - Befund 438.

Die Frage, die Befund 437 offen gelassen hat
--------------------------------------------
437 hat verzeichnet, dass sieben der fuenfzehn Schwellen ohne Ableitung
dastanden, und zwei Ungereimtheiten benannt - ohne zu messen, **ob sie
ueberhaupt etwas kosten**. Eine unerklaerte Schwelle, von der der Kandidat
weit entfernt ist, ist ein Schoenheitsfehler; eine, an der er klebt, ist ein
Risiko.

``cli stand`` zeigt seit Befund 394/395 je Gate den Abstand - aber **absolut**,
und absolute Abstaende sind nicht vergleichbar: ``0,390`` beim schlechtesten
Jahr und ``2,131`` beim Rueckgang stehen auf Schwellen von 10 und 12, ``0,081``
bei der Bestaendigkeit auf einer von 0,5. Wer die Spalte liest, haelt die
groesste Zahl fuer die groesste Reserve.

Was hier gerechnet wird
-----------------------
Der Abstand als **Anteil der Schwelle**, damit die Gates vergleichbar werden,
und dazu zwei Kreuze: die Belastbarkeit aus Befund 420 (in wie vielen von elf
Fensteraufteilungen das Gate faellt) und die Herkunft der Schwelle aus 437.

Gemessen am Spot-Punkt, dem Punkt, auf den sich jede zitierte Zahl bezieht.

**Woher die Werte kommen**, weil das ein Unterschied ist: Die Spalte
"Schwelle" und der Spot-**Abstand** stehen so in der Tafel von ``cli stand``
(Befund 394/395). Die Spalte "Wert" ist daraus zurueckgerechnet - Schwelle
plus oder minus Abstand, die Richtung aus dem Status, weil beim Rueckgang
weniger besser ist und beim Sharpe mehr. Gegengeprueft an zwei unabhaengig
verzeichneten Zahlen: Befund 416 nennt fuer denselben Punkt 'Schlechtestes
Jahr' **-9,6100** und 'Drawdown' **9,869** - beide treffen.

    Gate                     Wert  Schwelle   Anteil  Herkunft
    Schlechtestes Jahr     -9,610   -10,000     3,9 %  abgeleitet
    Bestaendigkeit          0,581     0,500    16,2 %  **ohne**
    Drawdown                9,869    12,000    17,8 %  abgeleitet
    Monte-Carlo             8,326    15,000    44,5 %  Beobachtung
    Out-of-Sample-Sharpe    1,576     1,000    57,6 %  **ohne**
    Parameter-Plateau       1,000     0,600    66,7 %  **ohne**
    Regime-Aufteilung       5,275     0,900   486,1 %  widersprechend

Drei Dinge stehen damit fest
----------------------------
**Die engste Stelle ist 'Schlechtestes Jahr' mit 3,9 %.** Das ist weniger
Reserve, als der Messlatte zum Bestehen fehlt (0,661 von 15, also 4,4 %) - der
Kandidat ist einem **zehnten** Durchfaller fast so nah wie dem Bestehen des
ersten offenen Gates. Und es ist dasselbe Gate, das Befund 420 als das
unbelastbarste gemessen hat: Es faellt in **5 von 11** Fensteraufteilungen,
oefter als die Messlatte mit 1 von 11.

**Die zweitengste steht auf einer Schwelle ohne Ableitung.** Bestaendigkeit
0,5 ist eine der sieben aus 437, und der Kandidat haelt sie mit 16 %.

**Und mein Vorbehalt aus 437 kostet nichts.** Dort steht, dass
``min_regime_profit_factor = 0,9`` der eigenen Begruendung des Gates
widerspricht ("ein Faktor unter 1 zeigt einen echten strukturellen Nachteil").
Gemessen steht der Kandidat bei einem Profitfaktor von **5,275** - er bestaende
das Gate bei einer Schwelle von 1,0 genauso. Die Ungereimtheit bleibt
verzeichnet, weil sie fuer jeden **kuenftigen** Kandidaten gilt; fuer diesen
ist sie gegenstandslos, und das gehoert dazugesagt.

Zwei Fallgruben, beide aus den Daten und nicht geraten
------------------------------------------------------
**Schwelle null.** ``Kosten-Stress`` meldet 942,865 gegen 0,000 - ein Anteil
ist dort nicht definiert, und 'unendlich viel Reserve' waere eine Zahl, die
nach einer Messung aussieht. Das Gate bekommt keinen Anteil.

**Zwei Groessen in einer Spalte.** ``GateResult.bedingung`` warnt, dass bei
'Messlatte' und 'Stichprobengroesse' je nach Ausgang des Laufs eine andere
Groesse in ``value``/``threshold`` steht - Befund 395 hat dort einen Faktor elf
gemessen. Wer solche Paare ueber Laeufe hinweg vergleicht, vergleicht
Massstaebe. Der Anteil wird deshalb gerechnet, aber die Bedingung mitgefuehrt
und ausgewiesen.

Und was das nicht ist
---------------------
Keine Rangliste, welches Gate man als naechstes angehen sollte. Eine knappe
Reserve sagt, wo es wackelt, nicht wo etwas zu holen ist - die offenen zwei
Gates bleiben die offenen zwei. Gelockert wird hier nichts: Dieser Befund
**rechnet** Abstaende um und aendert keine Schwelle.

Kostet keinen Versuch: Es wird kein Kandidat geprueft, sondern ein bereits
gemessenes Urteil umgerechnet.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Woher die Schwelle kommt - aus Befund 437, als Daten statt als Prosa.
#:
#: ``abgeleitet`` heisst: Im Code steht, warum diese Zahl und nicht eine
#: andere. ``ohne`` heisst: Das Verfahren ist begruendet, die Zahl nicht.
#: ``beobachtung`` und ``widersprechend`` sind die zwei Sonderfaelle aus 437.
HERKUNFT: dict[str, str] = {
    "Stichprobengroesse": "abgeleitet",
    "Messlatte": "abgeleitet",
    "Out-of-Sample-Sharpe": "ohne",
    "Drawdown": "abgeleitet",
    "Schlechtestes Jahr": "abgeleitet",
    "Bestaendigkeit": "ohne",
    "Monte-Carlo": "beobachtung",
    "Regime-Aufteilung": "widersprechend",
    "Deflated Sharpe": "abgeleitet",
    "Kosten-Stress": "ohne",
    "Parameter-Plateau": "ohne",
}

#: In wie vielen von elf Fensteraufteilungen das Gate faellt - Befund 420.
#:
#: Nur die drei, die dort gemessen wurden. Die uebrigen fehlen hier, und das
#: ist richtig: Eine Null einzutragen hiesse "faellt nie", und gemessen ist
#: das nicht.
BELASTBARKEIT: dict[str, int] = {
    "Deflated Sharpe": 11,
    "Schlechtestes Jahr": 5,
    "Messlatte": 1,
}

#: Elf Aufteilungen - der Nenner zu ``BELASTBARKEIT``.
AUFTEILUNGEN = 11


@dataclass(frozen=True, slots=True)
class Stelle:
    """Ein Gate mit seinem Abstand, relativ gerechnet."""

    name: str
    wert: float
    schwelle: float
    bestanden: bool
    bedingung: str = ""

    @property
    def abstand(self) -> float:
        """Der absolute Abstand - immer positiv, wie in ``cli stand``.

        Die Richtung steht nicht in der Zahl, sondern im Status: Beim
        Rueckgang ist weniger besser, beim Sharpe mehr (Befund 395).
        """
        return abs(self.wert - self.schwelle)

    @property
    def anteil(self) -> float | None:
        """Der Abstand als Anteil der Schwelle - ``None`` bei Schwelle null.

        'Unendlich viel Reserve' waere eine Zahl, die nach einer Messung
        aussieht.
        """
        if self.schwelle == 0:
            return None
        return self.abstand / abs(self.schwelle)

    @property
    def herkunft(self) -> str:
        return HERKUNFT.get(self.name, "unbekannt")

    @property
    def faellt_in(self) -> int | None:
        """In wie vielen Aufteilungen es faellt - ``None`` heisst ungemessen."""
        return BELASTBARKEIT.get(self.name)

    @property
    def vergleichbar(self) -> bool:
        """Ob der Anteil ueber Laeufe hinweg dasselbe bedeutet.

        Falsch bei den Gates mit zwei Bedingungen: Dort steht je nach Ausgang
        eine andere Groesse in ``wert``/``schwelle`` (Befund 395).
        """
        return not self.bedingung

    def beschreibe(self) -> str:
        if self.anteil is None:
            lage = "kein Anteil (Schwelle null)"
        else:
            lage = f"{self.anteil:7.1%} {'Reserve' if self.bestanden else 'fehlt'}"
        zusatz = "" if self.vergleichbar else f", Bedingung: {self.bedingung}"
        return f"{self.name:22} {lage}  Schwelle {self.herkunft}{zusatz}"


def aus_gates(ergebnisse) -> tuple[Stelle, ...]:
    """Aus Gate-Ergebnissen die Stellen machen, engste zuerst.

    ``ergebnisse`` ist, was die Zulassungsstrecke liefert - alles mit ``name``,
    ``value``, ``threshold`` und einem Status, der ``passed`` kennt.

    **Uebersprungene Gates kommen nicht vor.** Ein Gate, das nicht geurteilt
    hat, hat auch keinen Abstand (Befund 395), und es als Reserve zu fuehren
    waere derselbe Freibrief, den Befund 430 abgestellt hat.
    """
    stellen = [
        Stelle(
            name=e.name,
            wert=float(e.value),
            schwelle=float(e.threshold),
            bestanden=_bestanden(e),
            bedingung=getattr(e, "bedingung", "") or "",
        )
        for e in ergebnisse
        if not _uebersprungen(e)
    ]
    # Ohne Anteil nach hinten: Sie sind nicht eng, sie sind nicht messbar.
    return tuple(
        sorted(stellen, key=lambda s: (s.anteil is None, s.anteil or 0.0))
    )


def _status(ergebnis) -> str:
    """Den Status als kleingeschriebenes Wort - 'pass', 'fail' oder 'skip'.

    ``GateStatus`` ist ein ``StrEnum``: Sein Wert **ist** das Wort, und
    ``GateResult.passed`` ist ausdruecklich ``status is not FAIL`` - ein
    uebersprungenes Gate zaehlt dort als bestanden (Befund 321/322). Gelesen
    wird deshalb der Status und nicht ``passed``.

    **Mein Fehlgriff dabei** (Befund 438): Hier stand
    ``getattr(e.status, "passed", e.status == "passed")``. ``GateStatus`` hat
    kein ``passed``, und es vergleicht sich mit ``"pass"`` und nicht mit
    ``"passed"`` - damit kam **jedes** Gate als nicht bestanden heraus und die
    Rangliste war leer. Aufgefallen ist es erst am echten Lauf: Mein Test
    hatte ein Doppel mit ``.passed``, also genau meine falsche Annahme statt
    des echten Typs.
    """
    status = getattr(ergebnis, "status", None)
    wort = getattr(status, "value", None) or getattr(status, "name", "") or str(status)
    return str(wort).lower()


def _bestanden(ergebnis) -> bool:
    return _status(ergebnis) == "pass"


def _uebersprungen(ergebnis) -> bool:
    return _status(ergebnis) == "skip"


def engste(stellen: tuple[Stelle, ...], *, nur_bestandene: bool = True) -> Stelle | None:
    """Die knappste Stelle - standardmaessig unter den **bestandenen**.

    Die offenen Gates sind nicht 'eng', sie sind offen; sie in dieselbe
    Rangliste zu mischen, beantwortet eine andere Frage.
    """
    gewaehlt = [
        s
        for s in stellen
        if s.anteil is not None and (s.bestanden or not nur_bestandene)
    ]
    return gewaehlt[0] if gewaehlt else None


def bericht(stellen: tuple[Stelle, ...]) -> str:
    """Die Tafel, engste Stelle zuerst."""
    if not stellen:
        return "Keine geurteilten Gates - kein Abstand zu rechnen."

    zeilen = [
        "Abstand als Anteil der Schwelle, engste zuerst:",
        "",
        *(f"  {s.beschreibe()}" for s in stellen),
        "",
    ]
    eng = engste(stellen)
    if eng is not None and eng.anteil is not None:
        zeilen.append(
            f"Engste bestandene Stelle: {eng.name} mit {eng.anteil:.1%} Reserve."
        )
        if eng.faellt_in is not None:
            zeilen.append(
                f"  Dasselbe Gate faellt in {eng.faellt_in} von {AUFTEILUNGEN} "
                f"Fensteraufteilungen (Befund 420) - knappe Reserve und "
                f"geringe Belastbarkeit treffen hier zusammen."
            )
        if eng.herkunft == "ohne":
            zeilen.append(
                "  Und seine Schwelle ist eine der sieben ohne verzeichnete "
                "Ableitung (Befund 437)."
            )
    ohne_ableitung = [
        s
        for s in stellen
        if s.herkunft == "ohne" and s.bestanden and s.anteil is not None
    ]
    if ohne_ableitung:
        zeilen.append(
            "Bestandene Gates auf Schwellen ohne Ableitung: "
            + ", ".join(f"{s.name} ({s.anteil:.0%})" for s in ohne_ableitung)
        )
    return "\n".join(zeilen)
