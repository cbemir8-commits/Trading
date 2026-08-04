"""Was Gebuehren in R kosten - und welche Trefferquote sie erzwingen.

Der Gedanke
-----------
Gebuehren werden fast immer in Prozent des Nominalwerts angegeben, und in
dieser Einheit klingen sie harmlos: 0,055 % je Seite. Das ist aber die falsche
Einheit. Was zaehlt, ist der Anteil am **Risiko** eines Trades - denn daran
misst sich der Gewinn.

Der Umrechnungsfaktor ist die Stop-Distanz:

    Gebuehr in R = Gebuehrensatz / Stop-Distanz

Bei 1 % Stop kostet eine Taker-Gebuehr von 0,055 % also 0,055 R. Bei 0,2 %
Stop kostet dieselbe Gebuehr 0,275 R - das Fuenffache, bei unveraendertem
Gebuehrensatz.

Das ist der Grund, warum enge Stops teuer sind, und es ist kein Nebeneffekt,
sondern der beherrschende Term. Wer mit 0,2 % Stop handelt, gibt fuer Ein- und
Ausstieg zusammen leicht ein Drittel seines Risikos an die Boerse ab, bevor
ueberhaupt eine Kursbewegung stattgefunden hat.

Warum das hier steht und nicht in einem Kommentar
-------------------------------------------------
Weil es eine pruefbare Zahl ist und keine Meinung. Vor jeder Diskussion
darueber, ob eine schnelle Strategie funktionieren kann, laesst sich
ausrechnen, welche Trefferquote sie mindestens braucht. Liegt die ueber dem,
was in der Vergangenheit je gemessen wurde, eruebrigt sich der Rest.

Die Zahlen gelten fuer VIP0 bei Bybit. Wer genug Volumen handelt, zahlt
weniger - und genau darauf beruht ein Teil des Vorteils, den professionelle
Haeuser bei schnellen Strategien haben. Das ist keine Frage der Idee, sondern
der Kostenstufe.
"""

from __future__ import annotations

from dataclasses import dataclass

from backtest.costs import CostModel


@dataclass(frozen=True, slots=True)
class CostFloor:
    """Was ein Trade an Gebuehren kostet, gemessen in R."""

    stop_pct: float
    cost_win_r: float
    """Gewinner: Einstieg und Ausstieg beide als Maker (Limit-Order)."""

    cost_loss_r: float
    """Verlierer: Einstieg als Maker, Stop als Taker - plus Slippage.

    Der Stop ist die teure Seite, und zwar doppelt: Er zahlt die hoehere
    Gebuehr **und** er wird ausgeloest, wenn der Markt sich schnell bewegt -
    also genau dann, wenn die Spreads breit sind."""

    def required_win_rate(self, rr: float) -> float:
        """Trefferquote, ab der ein Trade sich gerade eben lohnt.

        Ohne Kosten waere es ``1 / (rr + 1)`` - bei 1,5:1 also 40 %. Die
        Gebuehren verschieben beides: Der Gewinn faellt kleiner aus, der
        Verlust groesser.
        """
        zaehler = 1.0 + self.cost_loss_r
        nenner = rr + 1.0 + self.cost_loss_r - self.cost_win_r
        if nenner <= 0:
            return 1.0
        return min(1.0, zaehler / nenner)

    def edge_needed_r(self, rr: float) -> float:
        """Wie viel Rohvorteil je Trade noetig ist, nur um die Kosten zu decken.

        Ausgedrueckt als Erwartungswert **vor** Gebuehren. Alles darunter ist
        ein Verlustgeschaeft, egal wie gut die Regel aussieht.
        """
        p = self.required_win_rate(rr)
        return p * rr - (1.0 - p)

    def describe(self) -> str:
        return (
            f"Stop {self.stop_pct:.2f} %: Gewinner kosten {self.cost_win_r:.3f} R, "
            f"Verlierer {self.cost_loss_r:.3f} R zusaetzlich"
        )


def cost_floor(stop_pct: float, costs: CostModel | None = None) -> CostFloor:
    """Gebuehren und Slippage eines Trades, umgerechnet in R.

    ``stop_pct`` ist die Stop-Distanz in Prozent des Einstiegs. Sie ist der
    Umrechnungsfaktor zwischen "Prozent vom Nominalwert" und "Anteil am
    Risiko" - und deshalb die Groesse, an der alles haengt.
    """
    if stop_pct <= 0:
        raise ValueError("Die Stop-Distanz muss groesser als null sein")

    costs = costs or CostModel()
    maker = float(costs.maker_fee_rate) * 100.0
    taker = float(costs.taker_fee_rate) * 100.0
    stop_slip = float(costs.stop_slippage_bps) / 100.0

    return CostFloor(
        stop_pct=stop_pct,
        # Ein- und Ausstieg als Maker - der guenstigste Fall, den unsere
        # Ausfuehrung ueberhaupt erreichen kann (PostOnly-Einstieg).
        cost_win_r=(maker + maker) / stop_pct,
        # Der Stop nimmt Liquiditaet und rutscht dabei.
        cost_loss_r=(maker + taker + stop_slip) / stop_pct,
    )


def floor_table(
    stops: list[float] | None = None,
    rr: float = 1.5,
    costs: CostModel | None = None,
) -> list[tuple[float, float, float, float]]:
    """Eine Zeile je Stop-Distanz: (Stop %, noetige Trefferquote, Kosten in R, Rohvorteil).

    Gedacht zum Anschauen, nicht zum Weiterrechnen - die Zahlen sollen eine
    Entscheidung stuetzen, die sonst aus dem Bauch getroffen wird.
    """
    stops = stops or [0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
    zeilen = []
    for stop in stops:
        floor = cost_floor(stop, costs)
        zeilen.append(
            (
                stop,
                floor.required_win_rate(rr),
                floor.cost_win_r + floor.cost_loss_r,
                floor.edge_needed_r(rr),
            )
        )
    return zeilen
