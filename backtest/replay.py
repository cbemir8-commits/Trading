"""Dieselbe Strategie zweimal laufen lassen - wie im Backtest, wie im Betrieb.

Wozu
----
Alle Zahlen in ``strategies/BEFUND.md`` stammen aus dem Backtest. Gehandelt
wird aber vom Livebetrieb, und der sieht die Welt anders:

    Backtest    einmal ``prepare`` ueber die ganze Historie, dann Balken
                fuer Balken mit wachsendem Index
    Livebetrieb je Kerze ein ``prepare`` ueber die letzten ``BUFFER_BARS``,
                und der Index ist immer der letzte des Puffers

Solange beide dieselben Signale erzeugen, misst der Backtest, was passieren
wird. Tun sie es nicht, misst er etwas anderes - und keine noch so sorgfaeltige
Zulassung haette davon etwas gemerkt.

Warum das nicht durch Zuschauen auffaellt
-----------------------------------------
``research/live_evidenz.py`` hat es ausgerechnet: Bei 17 Trades im Jahr
bliebe selbst ein **vollstaendiger** Verlust des Vorteils drei Jahre lang
unentdeckt. Ein Unterschied zwischen Backtest und Betrieb wuerde im
Demobetrieb also nicht auffallen - er muss vorher gefunden werden, durch
Vergleich, nicht durch Beobachtung.

Verglichen wird die ganze Entscheidungsflaeche
--------------------------------------------
Nicht nur das Einstiegssignal: auch die Ausstiegsbedingung und der
Kapitalanteil. Von den drei bisher gefundenen Abweichungen haette ein reiner
Signalvergleich naemlich nur **eine** gefunden - die beiden anderen fielen
bei der Handpruefung auf, und darauf ist kein Verlass.

Was der Vergleich gefunden hat
------------------------------
Die Sperrfrist (``cooldown_bars``) rechnete mit dem Index **im aktuellen
Rahmen**. Im Backtest waechst der von 0 bis ans Ende, im Betrieb steht er bei
vollem Puffer fest auf ``BUFFER_BARS - 1``. Ab dem ersten Trade galt dort
also immer ``index - letzter_einstieg == 0``, und die Sperrfrist lief nie ab:
Der Roboter haette nach seinem ersten Trade **nie wieder** eingestiegen.

Der Spitzenkandidat handelt ohne Sperrfrist und war nicht betroffen. Das ist
Glueck, kein Verdienst - die Sperrfrist war eine der zehn gemessenen
Richtungen und haette ebenso gut gewinnen koennen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import structlog

from core.models import Side
from strategy.base import BarContext, frame_to_arrays, wants_exit

log = structlog.get_logger(__name__)

#: Muss dem Wert in ``execution/live.py`` entsprechen. Bewusst hier
#: gespiegelt statt importiert: Der Vergleich soll auch dann noch etwas
#: aussagen, wenn dort jemand die Zahl aendert - dann faellt es hier auf.
BUFFER_BARS = 2000


@dataclass(frozen=True, slots=True)
class Entscheidung:
    """Alles, was die Strategie auf einem Balken entscheidet.

    Bewusst **drei** Dinge und nicht nur das Einstiegssignal. Von den drei
    bisher gefundenen Abweichungen zwischen Backtest und Betrieb haette ein
    reiner Signalvergleich nur **eine** gefunden:

        Sperrfrist lief nie ab        Signal      gefunden
        Positionsgroesse zehnfach     Anteil      nicht gefunden
        Ausstiegsbedingung fehlte     Ausstieg    nicht gefunden

    Die beiden anderen fielen bei der Handpruefung auf. Darauf ist kein
    Verlass - deshalb steht hier jetzt die ganze Entscheidungsflaeche.
    """

    signal: str
    """"long", "short" oder "-"."""

    raus_long: bool
    raus_short: bool
    """Ob die Ausstiegsbedingung greifen wuerde. Fuer beide Seiten erhoben,
    weil hier keine Positionen mitgefuehrt werden - welche Seite offen ist,
    weiss nur die Engine."""

    anteil: str
    """Kapitalanteil als Text, damit ``None`` und 0,0 unterscheidbar bleiben."""

    def __str__(self) -> str:
        return (
            f"Signal {self.signal:<6} raus {int(self.raus_long)}{int(self.raus_short)} "
            f"Anteil {self.anteil}"
        )


@dataclass(frozen=True, slots=True)
class Abweichung:
    """Ein Balken, an dem sich die beiden Laeufe uneinig sind."""

    index: int
    zeit: pd.Timestamp
    backtest: str
    livebetrieb: str

    def __str__(self) -> str:
        return (
            f"{self.zeit:%Y-%m-%d %H:%M}  Backtest [{self.backtest}]  "
            f"Betrieb [{self.livebetrieb}]"
        )


@dataclass(slots=True)
class Vergleich:
    """Was beim Nebeneinanderlegen herauskam."""

    balken: int = 0
    signale_backtest: int = 0
    signale_livebetrieb: int = 0
    abweichungen: list[Abweichung] = field(default_factory=list)

    @property
    def einig(self) -> bool:
        return not self.abweichungen

    @property
    def nichts_zu_vergleichen(self) -> bool:
        """Einig, weil **keine** Seite gehandelt hat - Befund 360.

        Das ist kein Beleg, sondern eine Leerstelle: Zwei Laeufe, die nie etwas
        wollten, stimmen notwendig ueberein. Genau so ist der Abgleich fuer die
        Carry-Regel gruen geworden - "Einig ueber 5355 Balken - 0 Signale".
        """
        return self.einig and not (self.signale_backtest or self.signale_livebetrieb)

    def bericht(self) -> str:
        if self.nichts_zu_vergleichen:
            return (
                f"**Nichts zu vergleichen**: Ueber {self.balken} Balken hat "
                f"keine der beiden Seiten ein Signal erzeugt. Das ist kein "
                f"Beleg fuer Uebereinstimmung - zwei Laeufe, die nie etwas "
                f"wollten, stimmen notwendig ueberein (Befund 360). Haeufigste "
                f"Ursache: eine Eingabe fehlt, etwa die Funding-Spalte bei "
                f"Carry-Regeln."
            )
        if self.einig:
            return (
                f"Einig ueber {self.balken} Balken - "
                f"{self.signale_backtest} Signale, identisch."
            )
        return (
            f"{len(self.abweichungen)} Abweichungen ueber {self.balken} Balken. "
            f"Backtest {self.signale_backtest} Signale, "
            f"Betrieb {self.signale_livebetrieb}.\n"
            + "\n".join(f"  {a}" for a in self.abweichungen[:10])
        )


def _beschreibe(signal) -> str:
    if signal is None:
        return "-"
    return "long" if signal.side is Side.BUY else "short"


#: Die Entscheidung eines Balkens, an dem die Strategie noch nicht
#: eingeschwungen ist. Ausdruecklich benannt, damit die Aufwaermphase in
#: beiden Laeufen dieselbe Zeile erzeugt.
NICHTS = Entscheidung(signal="-", raus_long=False, raus_short=False, anteil="-")


def _entscheiden(strategy, ctx) -> Entscheidung:
    """Was die Strategie auf diesem Balken will - alle drei Antworten."""
    signal = strategy.on_bar(ctx)

    hole_anteil = getattr(strategy, "fraction_at", None)
    if hole_anteil is not None:
        wert = hole_anteil(ctx.index)
    else:
        wert = getattr(strategy, "equity_fraction", None)

    return Entscheidung(
        signal=_beschreibe(signal),
        raus_long=wants_exit(strategy, ctx, Side.BUY),
        raus_short=wants_exit(strategy, ctx, Side.SELL),
        anteil="-" if wert is None else f"{float(wert):.4f}",
    )


def entscheidungen_backtest(frame: pd.DataFrame, build_strategy) -> list[Entscheidung]:
    """Entscheidungen so, wie der Backtest sie trifft.

    Ein ``prepare`` ueber alles, dann laufender Index. Das ist die Sicht, aus
    der alle Kennzahlen im BEFUND stammen.
    """
    strategy = build_strategy()
    arrays = frame_to_arrays(frame)
    indicators = strategy.prepare(frame)

    # Exakt die Grenze der Engine: ``start = max(warmup_bars, 1)``, und der
    # Balken ``warmup_bars`` wird **mitgerechnet**.
    #
    # Hier stand einmal ``i <= warmup_bars``, also ein Balken zu spaet - und
    # der Vergleich meldete prompt eine Abweichung, die es im Produktivcode
    # gar nicht gab. Ein Pruefwerkzeug, das die Grenze anders zieht als das
    # Gepruefte, findet Fehler, die keine sind, und verdeckt die echten
    # dahinter.
    start = max(strategy.warmup_bars, 1)

    ergebnis = []
    for i in range(len(frame)):
        if i < start:
            ergebnis.append(NICHTS)
            continue
        ergebnis.append(
            _entscheiden(strategy, BarContext(frame, arrays, indicators, i))
        )
    return ergebnis


def _wie_der_puffer(frame: pd.DataFrame) -> pd.DataFrame:
    """Den Rahmen auf die Spalten kuerzen, die der Livepuffer wirklich hat.

    **Befund 360.** Der Livepuffer entsteht aus ``candles_to_frame``, und das
    sind genau die sieben Spalten aus ``store.SCHEMA``. Eine Funding-Spalte ist
    nicht darunter - ``execution/`` erwaehnt Funding an keiner Stelle.

    Ohne diese Kuerzung bekam die Live-Seite dieses Vergleichs jede Spalte, die
    der Aufrufer mitbrachte, und damit **mehr als der Betrieb hat**. Gemessen an
    der Carry-Regel aus Generation 5: Der Wettbewerb haengt die Funding-Raten
    an, der Livebetrieb hat sie nicht, und die Funding-Indikatoren geben dort
    NaN zurueck - die Regel handelt live **nie**. Der Abgleich sah das nicht,
    weil beide Seiten denselben funding-freien Rahmen bekamen und einig waren,
    nichts zu tun.

    Die Liste wird aus ``SCHEMA`` gelesen und nicht hier aufgeschrieben: Bekommt
    der Livepuffer eines Tages eine Spalte dazu, folgt dieser Vergleich von
    selbst.
    """
    from data.store import SCHEMA

    behalten = [s for s in frame.columns if s in SCHEMA]
    return frame[behalten] if len(behalten) != len(frame.columns) else frame


def entscheidungen_livebetrieb(
    frame: pd.DataFrame, build_strategy, *, buffer_bars: int = BUFFER_BARS
) -> list[Entscheidung]:
    """Entscheidungen so, wie der Livebetrieb sie trifft.

    Je Balken ein frischer Ausschnitt der letzten ``buffer_bars`` Kerzen, ein
    ``prepare`` darueber, und der Index am Ende des Ausschnitts - genau das,
    was ``LiveTrader._context`` tut.

    **Und mit den Spalten, die der Puffer wirklich hat** (Befund 360, siehe
    ``_wie_der_puffer``). Den Ausschnitt richtig zu schneiden und ihm dabei
    Eingaben mitzugeben, die es im Betrieb nicht gibt, stellt den Betrieb nicht
    nach - es nimmt ihm genau die Abweichung, die zu finden war.

    Deutlich langsamer als der Backtest, weil die Indikatoren je Balken neu
    gerechnet werden. Das ist der Preis dafuer, den Betrieb nachzustellen
    statt ihn nachzuahmen.
    """
    strategy = build_strategy()
    lebensnah = _wie_der_puffer(frame)

    ergebnis = []
    for i in range(len(frame)):
        beginn = max(0, i - buffer_bars + 1)
        puffer = lebensnah.iloc[beginn : i + 1].reset_index(drop=True)
        # Die Bedingung aus ``LiveTrader._context`` - unveraendert
        # uebernommen. Der erste Balken bleibt aussen vor, weil die Engine
        # mit ``max(warmup_bars, 1)`` ebenfalls bei 1 beginnt; ohne das
        # wichen beide bei Strategien ohne Aufwaermzeit um einen Balken ab.
        if len(puffer) <= strategy.warmup_bars or i < 1:
            ergebnis.append(NICHTS)
            continue
        arrays = frame_to_arrays(puffer)
        indicators = strategy.prepare(puffer)
        ctx = BarContext(puffer, arrays, indicators, len(puffer) - 1)
        ergebnis.append(_entscheiden(strategy, ctx))
    return ergebnis


def signale_backtest(frame: pd.DataFrame, build_strategy) -> list:
    """Nur die Einstiegssignale - fuer Aufrufer, die den Rest nicht brauchen."""
    return [
        None if e.signal == "-" else e.signal
        for e in entscheidungen_backtest(frame, build_strategy)
    ]


def signale_livebetrieb(
    frame: pd.DataFrame, build_strategy, *, buffer_bars: int = BUFFER_BARS
) -> list:
    """Nur die Einstiegssignale aus Sicht des Betriebs."""
    return [
        None if e.signal == "-" else e.signal
        for e in entscheidungen_livebetrieb(
            frame, build_strategy, buffer_bars=buffer_bars
        )
    ]


def vergleiche(
    frame: pd.DataFrame,
    build_strategy,
    *,
    buffer_bars: int = BUFFER_BARS,
    max_abweichungen: int = 200,
) -> Vergleich:
    """Beide Laeufe nebeneinanderlegen.

    Gibt zurueck, an welchen Balken sie sich uneinig sind. Ein leeres
    Ergebnis ist die Aussage, auf die es ankommt: Der Backtest misst das, was
    im Betrieb passieren wird.
    """
    a = entscheidungen_backtest(frame, build_strategy)
    b = entscheidungen_livebetrieb(frame, build_strategy, buffer_bars=buffer_bars)

    ergebnis = Vergleich(balken=len(frame))
    ergebnis.signale_backtest = sum(1 for e in a if e.signal != "-")
    ergebnis.signale_livebetrieb = sum(1 for e in b if e.signal != "-")

    zeiten = frame["open_time"]
    for i, (links, rechts) in enumerate(zip(a, b, strict=True)):
        if links == rechts:
            continue
        if len(ergebnis.abweichungen) < max_abweichungen:
            ergebnis.abweichungen.append(
                Abweichung(
                    index=i,
                    zeit=zeiten.iloc[i],
                    backtest=str(links),
                    livebetrieb=str(rechts),
                )
            )

    log.info(
        "replay.verglichen",
        balken=ergebnis.balken,
        abweichungen=len(ergebnis.abweichungen),
        einig=ergebnis.einig,
    )
    return ergebnis
