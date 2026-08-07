"""Sicherheitsinvarianten der Ausfuehrung.

Sieben Aussagen, die nach jeder verarbeiteten Kerze gelten muessen. Nicht
"sollten" - muessen. Jede einzelne steht fuer einen Fehler, der tatsaechlich
im Code war (siehe ``strategies/BEFUND.md``, die Befunde acht bis elf).

**Warum eine eigene Datei und nicht ein paar Zusicherungen im Test.**

Die bisher gefundenen Ausfuehrungsfehler hatten alle dieselbe Form: Der
Einzelpfad war getestet, aber die *Kombination* zweier Ereignisse - Teilfuellung
und dann Nachfuellung, Storno und gleichzeitiger Fill - nicht. Solche
Kombinationen laufen sich mit einzeln geschriebenen Tests nicht ab; es sind zu
viele. Was hilft, ist die Umkehrung: nicht jeden Ablauf einzeln pruefen, sondern
eine Handvoll Aussagen formulieren, die in **jedem** Zustand gelten, und
zufaellige Ablaeufe dagegen laufen lassen. Das tut ``tests/test_fuzz_ausfuehrung.py``.

Dieselben Aussagen laufen im Betrieb mit - einmal je Kerze. Damit ist der
Unterschied zwischen "im Test hat es gehalten" und "es haelt gerade" nicht mehr
eine Vermutung, sondern eine Messung.

**Was hier absichtlich nicht passiert: handeln.** Diese Pruefung meldet, sie
greift nicht ein. Die Stellen, die eingreifen (die Wachstumspruefung in
``LiveTrader._manage_open_position``, der Notausstieg bei fehlgeschlagenem Stop),
kennen ihren Fall genau. Eine Pruefung, die noch nie im Betrieb angeschlagen
hat, automatisch Positionen schliessen zu lassen, hiesse einem Fehlalarm Geld
anzuvertrauen. Gemeldet wird dafuer sofort und laut - der Weg zum Telefon ist
kurz.

**Zeitpunkt: nach der Kerze, nicht waehrend.** Zwischen zwei Kerzen darf die
Sicht des Systems von der Boerse abweichen - eine Order kann in genau diesem
Moment fuellen, ohne dass jemand davon weiss. Genau dafuer gibt es den Abgleich
je Kerze. Geprueft wird deshalb erst, wenn er gelaufen ist.

**Was hier bewusst nicht steht:** eine Einstiegsorder, die neben einer bereits
offenen Position im Buch liegt. Sie ist kein gebrochener Zustand, sondern ein
gefaehrdeter - sie *koennte* die Position vergroessern. Dafuer gibt es die
Wachstumspruefung in ``LiveTrader._manage_open_position``, die genau dann
zuschlaegt. Eine Invariante, die kuenftigen Schaden meldet statt vorhandenen,
verliert ihre Schaerfe.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.models import Order, Position
from execution.router import Bracket, BracketState, MarketKind


@dataclass(frozen=True, slots=True)
class Verletzung:
    """Eine gebrochene Invariante."""

    name: str
    detail: str

    def __str__(self) -> str:
        return f"{self.name}: {self.detail}"


def pruefe(
    *,
    bracket: Bracket | None,
    position: Position | None,
    orders: list[Order],
    market_kind: MarketKind = MarketKind.PERPETUAL,
) -> list[Verletzung]:
    """Alle Invarianten gegen den aktuellen Zustand pruefen.

    ``orders`` sind die **offenen** Orders am Symbol, ``position`` die Position
    an der Boerse (``None``, wenn flach). Beides kommt von der Boerse, nicht aus
    dem Gedaechtnis des Prozesses - sonst prueft man den Prozess gegen sich
    selbst.
    """
    verletzungen: list[Verletzung] = []
    einstiege = [o for o in orders if not o.reduce_only]
    stop_id = bracket.stop_order_id if bracket else None
    ziele = [o for o in orders if o.reduce_only and o.order_id != stop_id]

    offen = bracket is not None and bracket.is_open
    wartend = bracket is not None and bracket.state is BracketState.PENDING_ENTRY

    # I1 - Eine Position, um die sich niemand kuemmert.
    #
    # Der gefaehrlichste Zustand ueberhaupt: Sie hat vielleicht einen Stop, aber
    # keine Ziele, keinen Nachzug auf Einstand und keine Ausstiegsbedingung.
    # Bei diesem Kandidaten enden 38,5 % aller Trades ueber die
    # Ausstiegsbedingung - ohne Bracket enden sie am Stop.
    if position is not None and not offen:
        zustand = bracket.state.value if bracket else "kein Bracket"
        verletzungen.append(
            Verletzung(
                "unbeaufsichtigte_position",
                f"{position.side.value} {position.size} an der Boerse, "
                f"aber Bracket-Zustand ist '{zustand}'",
            )
        )

    # I2 - Ein Bracket, dessen Position es nicht mehr gibt.
    #
    # Blockiert jeden weiteren Einstieg: ``_look_for_entry`` laeuft nur, wenn
    # ``bracket is None``. Ein vergessenes Bracket legt den Handel still, ohne
    # dass irgendwo ein Fehler auftaucht.
    if offen and position is None:
        verletzungen.append(
            Verletzung(
                "bracket_ohne_position",
                f"Bracket meldet {bracket.remaining_qty} offen, "  # type: ignore[union-attr]
                f"die Boerse meldet keine Position",
            )
        )

    if offen and position is not None:
        assert bracket is not None

        # I3 - Die Position ist groesser als das, was abgesichert wurde.
        #
        # Gemessen: Eine zur Haelfte gefuellte Einstiegsorder ergab nach dem
        # Nachfuellen die doppelte Position - bei unveraendertem Stop also das
        # doppelte Risiko je Trade.
        if position.size > bracket.remaining_qty:
            verletzungen.append(
                Verletzung(
                    "position_groesser_als_abgesichert",
                    f"{position.size} an der Boerse, {bracket.remaining_qty} "
                    f"im Bracket vermerkt",
                )
            )

        # I4 - Die Seite stimmt nicht.
        #
        # Faellt sonst erst auf, wenn der Notausstieg in die falsche Richtung
        # verkauft und die Position dabei verdoppelt.
        if position.side is not bracket.signal.side:
            verletzungen.append(
                Verletzung(
                    "seite_stimmt_nicht",
                    f"Boerse {position.side.value}, Bracket "
                    f"{bracket.signal.side.value}",
                )
            )

        # I5 - Die offene Position hat keinen Stop.
        if market_kind.has_position_stop:
            if position.stop_loss is None or position.stop_loss == 0:
                verletzungen.append(
                    Verletzung(
                        "position_ohne_stop",
                        f"{position.size} offen, kein Stop an der Position",
                    )
                )
        elif stop_id is None or not any(o.order_id == stop_id for o in orders):
            verletzungen.append(
                Verletzung(
                    "position_ohne_stop",
                    f"{position.size} offen, keine Stop-Order im Buch "
                    f"(Spot kennt keinen Positions-Stop)",
                )
            )

    # I6 - Mehr Ziele im Buch als Position da ist.
    #
    # Reduce-Only faengt den unmittelbaren Schaden ab, aber die ueberzaehligen
    # Orders bleiben liegen und schneiden den **naechsten** Trade sofort an.
    # Gemessen: 0,006 an Zielen bei 0,003 Position.
    zielmenge = sum((o.remaining_qty for o in ziele), Decimal(0))
    vorhanden = position.size if position is not None else Decimal(0)
    if zielmenge > vorhanden:
        verletzungen.append(
            Verletzung(
                "ziele_groesser_als_position",
                f"{zielmenge} an Reduce-Only-Orders, aber nur {vorhanden} Position",
            )
        )

    # I7 - Eine Einstiegsorder ohne Bracket, das auf sie wartet.
    #
    # Sie fuellt irgendwann - und dann steht eine Position im Markt, von der
    # dieser Prozess nie erfahren hat. Genau der Fund aus BEFUND 8.
    if einstiege and not (wartend or offen):
        zustand = bracket.state.value if bracket else "kein Bracket"
        verletzungen.append(
            Verletzung(
                "verwaiste_einstiegsorder",
                f"{len(einstiege)} Einstiegsorder(s) im Buch, "
                f"Bracket-Zustand '{zustand}'",
            )
        )

    return verletzungen
