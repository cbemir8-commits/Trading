"""Die Risikogrenzen verlieren je Fenster ihre Vorgeschichte.

Woher die Frage kommt
---------------------
Befund 400 hat gemessen, dass der durchgehende Modus 98 fertige Trades hat und
der Modus der Zulassung 156, und daraus eine Erklaerung **geschlossen**: Rund
58 seien Grenzartefakte, Positionen, die am Fensterende geschlossen und danach
neu eroeffnet werden. Befund 403 hat diese Erklaerung nachgemessen, und sie ist
falsch:

* **Kein einziger** Trade steigt an einem Fensterende aus. Die Austrittsgruende
  der 158 rohen Trades sind ``signal_exit`` 78, ``stop_loss`` 68,
  ``take_profit`` 10, ``end_of_data`` 2 - einen Grund "Fensterende" gibt es
  nicht.
* **Null** zerschnittene Paare: kein Austritt an einer Fenstergrenze mit
  Wiedereinstieg binnen zwei Tagen.
* Die Einstiege haeufen sich an **keinem** Fensteranfang: am ersten Tag eines
  Fensters beginnt in beiden Modi kein Trade, 150 der 158 beginnen am sechsten
  Tag oder spaeter.
* Und die Differenz ist **nicht grenzlokal, sondern kumulativ**: Die Fenster 0
  bis 7 liefern in beiden Modi genau dieselben Trade-Zahlen (4, 8, 1, 2, 12, 3,
  3, 8), ab Fenster 8 laeuft es auseinander, und im letzten Fenster stehen 6
  gegen 1.

Was es wirklich ist
-------------------
Ohne Risikogrenzen geben **beide Modi dieselbe Zahl**:

    Lauf                        Trades    CAGR   Rueckgang
    je Fenster, mit Limits         158  14,3391      9,869
    durchgehend, mit Limits         99  11,6275      7,504
    durchgehend, ohne Limits       162  19,0053     11,216
    je Fenster, ohne Limits        162  14,1915      9,869

Die ganze Differenz sind die **Risikogrenzen**. Im durchgehenden Modus
unterdruecken sie 63 der 162 Trades, im Modus der Zulassung **vier**. Der
Grund steht in den Logzeilen des Laufs: ``risk.ohne_vorgeschichte_simuliert
kapital=500``. Jedes Fenster ist ein eigener Backtest, der bei der
Anfangseinlage und **ohne Equity-Vorgeschichte** beginnt - und Kill-Switch und
Wochenverlustgrenze brauchen eine Vorgeschichte, um zu greifen. In einem
Dreimonatsfenster kommt sie kaum zustande.

Was das heisst
--------------
**Die Zulassungsstrecke misst einen Kandidaten, dessen Risikogrenzen praktisch
nicht greifen.** ``enforce_risk_limits=True`` steht in der Konfiguration, und
es ist nicht falsch - es wirkt nur fast nicht. Das ist eine Eigenschaft des
Messaufbaus, nicht der Strategie.

Und die Richtung ist unangenehm: Es **schmeichelt** dem Kandidaten. Mit
greifenden Grenzen steht die Jahresrendite bei 11,6275 statt 14,3391 und der
Deflated Sharpe bei 0,3185 statt 0,5826.

Zwei Wirkungen, getrennt
------------------------
* **Die Trade-Zahl** haengt allein an den Grenzen: ohne sie 162 in beiden Modi.
* **Die Rendite bei gleicher Trade-Zahl** haengt an der Aufteilung: ohne
  Grenzen 14,1915 je Fenster gegen 19,0053 durchgehend. Jedes Fenster startet
  bei der Anfangseinlage, also verzinst sich nichts ueber die Grenze hinweg.

Das Kreuz je Gate (Befund 404)
------------------------------
Dieselben vier Laeufe, aber Gate fuer Gate. ``f`` ist je Fenster, ``d``
durchgehend, ``+L`` mit Risikogrenzen, ``-L`` ohne:

    Gate                         f+L       f-L       d+L       d-L
    Stichprobengroesse     + 2250,000 + 2256,000 + 1297,000 + 2256,000
    Messlatte              -   14,339 -   14,192 -   11,627 +  302,090
    Out-of-Sample-Sharpe   +    1,576 +    1,561 +    1,408 +    1,529
    Drawdown               +    9,869 +    9,869 +    7,504 +   11,216
    Schlechtestes Jahr     +   -9,610 +   -9,610 +   -5,580 -  -10,940
    Bestaendigkeit         +    0,581 +    0,581 +    0,645 +    0,581
    Monte-Carlo            +    8,326 +    8,621 -   15,536 -   22,816
    Regime-Aufteilung      +    5,275 +    5,130 +    3,026 +    3,946
    Deflated Sharpe        -    0,583 -    0,592 -    0,318 -    0,685
    Kosten-Stress          + 1863,726 + 1863,726 + 1863,726 + 1863,726
    Parameter-Plateau      +    1,000 +    1,000 +    1,000 +    1,000
    bestanden                      9         9         8         8
    fertige Trades               156       160        98       160

**Je Fenster aendern die Grenzen am Gate-Bild nichts.** Dieselben neun
bestandenen, dieselbe Fehlliste, dieselbe Rueckgangszahl auf drei Stellen -
die Inertheit aus diesem Befund, von der Gate-Seite bestaetigt.

**Durchgehend aendern sie viel.** Ohne Grenzen faellt 'Schlechtestes Jahr' auf
-10,940 statt -5,580 und der Rueckgang steigt von 7,504 auf 11,216: Die
Grenzen schuetzen messbar - wenn sie greifen koennen.

**Acht der elf Urteile sind in allen vier Zellen dieselben**, drei wechseln
(Messlatte, Schlechtestes Jahr, Monte-Carlo). Und der **Deflated Sharpe faellt
in allen vier** - 0,583 / 0,592 / 0,318 / 0,685, in der guenstigsten Zelle
fehlen noch 0,265. Mit den Befunden 401 und 402 zusammen: Der Hauptblocker
haengt weder an der Aufteilung noch am Messaufbau.

Was nicht folgt
---------------
**Nicht**, dass der Modus zu wechseln ist. Welcher Modus die Zulassung tragen
soll, aendert jede Zahl dieses Projekts und ist eine Entscheidung des Nutzers
(so steht es seit Befund 400). Dieser Befund aendert nur den Grund, aus dem die
Frage gestellt wird: Es geht nicht um zwei gleichberechtigte Messweisen,
sondern darum, dass in der einen eine eingebaute Schutzvorrichtung fast nie
anspricht.

**Nicht**, dass die Grenzen falsch gebaut sind. Sie brauchen eine
Vorgeschichte, und das ist richtig - ein Kill-Switch ohne Historie waere
willkuerlich. Fehlt die Historie, ist das eine Aussage ueber den Aufbau, der
sie nicht liefert.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["GEMESSEN", "Grenzlauf", "Grenzvergleich"]


@dataclass(frozen=True, slots=True)
class Grenzlauf:
    """Ein Lauf mit oder ohne Risikogrenzen, je Fenster oder durchgehend."""

    durchgehend: bool
    limits: bool
    trades: int
    cagr_pct: float
    rueckgang_pct: float

    @property
    def name(self) -> str:
        return (
            f"{'durchgehend' if self.durchgehend else 'je Fenster'}, "
            f"{'mit' if self.limits else 'ohne'} Limits"
        )


@dataclass(frozen=True, slots=True)
class Grenzvergleich:
    """Vier Laeufe - und was sich zwischen ihnen zeigt."""

    laeufe: tuple[Grenzlauf, ...]

    def hole(self, *, durchgehend: bool, limits: bool) -> Grenzlauf:
        for lauf in self.laeufe:
            if lauf.durchgehend == durchgehend and lauf.limits == limits:
                return lauf
        raise KeyError(
            f"kein Lauf mit durchgehend={durchgehend}, limits={limits}"
        )

    def unterdrueckt(self, *, durchgehend: bool) -> int:
        """Wie viele Trades die Grenzen in diesem Modus unterdruecken."""
        return self.hole(durchgehend=durchgehend, limits=False).trades - self.hole(
            durchgehend=durchgehend, limits=True
        ).trades

    @property
    def greifen_je_fenster(self) -> bool:
        """Greifen die Grenzen im Modus der Zulassung ueberhaupt?

        Gemessen vier gegen 63 Trades - die Antwort ist "kaum", und die
        Schwelle dafuer ist bewusst grosszuegig: Ein Zehntel dessen, was sie
        durchgehend unterdruecken, waere noch Wirkung.
        """
        return self.unterdrueckt(durchgehend=False) >= (
            self.unterdrueckt(durchgehend=True) / 10
        )

    @property
    def renditeunterschied_ohne_limits(self) -> float:
        """Was die Aufteilung allein macht - bei gleicher Trade-Zahl."""
        return (
            self.hole(durchgehend=True, limits=False).cagr_pct
            - self.hole(durchgehend=False, limits=False).cagr_pct
        )


#: Die vier Laeufe aus Befund 403. Spot-Punkt, Zulassungsreihe, 32 Fenster.
GEMESSEN: Grenzvergleich = Grenzvergleich(
    laeufe=(
        Grenzlauf(
            durchgehend=False, limits=True, trades=158,
            cagr_pct=14.3391, rueckgang_pct=9.869,
        ),
        Grenzlauf(
            durchgehend=True, limits=True, trades=99,
            cagr_pct=11.6275, rueckgang_pct=7.504,
        ),
        Grenzlauf(
            durchgehend=True, limits=False, trades=162,
            cagr_pct=19.0053, rueckgang_pct=11.216,
        ),
        Grenzlauf(
            durchgehend=False, limits=False, trades=162,
            cagr_pct=14.1915, rueckgang_pct=9.869,
        ),
    )
)


#: Die Gate-Zahlen derselben vier Laeufe - Befund 404.
#:
#: **Achtung, zwei Trade-Zahlen.** ``GEMESSEN`` zaehlt die **rohen** Trades
#: (158 / 162 / 99 / 162), diese Tafel die **fertigen** nach Randschnitt
#: (156 / 160 / 98 / 160). Beide sind richtig, und sie zu verwechseln ist der
#: Fehler aus Befund 371.
GATEKREUZ: dict[tuple[bool, bool], tuple[str, ...]] = {
    # (durchgehend, limits) -> gefallene Gates
    (False, True): ("Messlatte", "Deflated Sharpe"),
    (False, False): ("Messlatte", "Deflated Sharpe"),
    (True, True): ("Messlatte", "Monte-Carlo", "Deflated Sharpe"),
    (True, False): ("Schlechtestes Jahr", "Monte-Carlo", "Deflated Sharpe"),
}

#: Die Gates, deren Urteil in **allen vier** Zellen dasselbe ist.
STANDHAFT: tuple[str, ...] = (
    "Stichprobengroesse",
    "Out-of-Sample-Sharpe",
    "Drawdown",
    "Bestaendigkeit",
    "Regime-Aufteilung",
    "Deflated Sharpe",
    "Kosten-Stress",
    "Parameter-Plateau",
)

#: Die Gates, deren Urteil am Messaufbau haengt.
WACKELIG: tuple[str, ...] = (
    "Messlatte",
    "Schlechtestes Jahr",
    "Monte-Carlo",
)


def haengt_am_aufbau(gate: str) -> bool:
    """Haengt das Urteil dieses Gates am Messaufbau (Modus x Grenzen)?

    Gemessen ueber das Kreuz aus Befund 404: **Acht** der elf Urteile sind in
    allen vier Zellen dieselben, **drei** wechseln.

    * ``Messlatte`` faellt in drei Zellen und besteht in der vierten
      (durchgehend ohne Grenzen) - dort meldet sie 302,090 gegen 61,470, also
      die Gesamtrendite gegen die heruntergefahrene Messlatte (Befund 395).
    * ``Schlechtestes Jahr`` besteht in drei Zellen und faellt durchgehend
      ohne Grenzen mit -10,940. **Das ist die Schutzwirkung der Grenzen,
      sichtbar gemacht**: Mit ihnen -5,580, ohne sie -10,940.
    * ``Monte-Carlo`` besteht in beiden Fenster-Zellen (8,326 / 8,621) und
      faellt in beiden durchgehenden (15,536 / 22,816, Schwelle 15). Dieses
      Urteil haengt also an der **Aufteilung**, nicht an den Grenzen.

    Und der **Deflated Sharpe faellt in allen vier Zellen** - 0,583, 0,592,
    0,318, 0,685. Selbst in der guenstigsten fehlen 0,265. Zusammen mit den
    Befunden 401 und 402 heisst das: Der Hauptblocker haengt weder an der
    Aufteilung noch am Messaufbau.
    """
    return gate in WACKELIG
