"""Was haette das **Konto** gesagt - nicht das einzelne Bein?

Der Fehler, um den es geht
--------------------------
Der Portfolio-Walk-Forward laesst jedes Bein als eigenen Backtest laufen. Jedes
bekommt damit ein eigenes Konto **und einen eigenen Risk-Officer**. Bei zwei
Maerkten heisst das: zwei Kill-Switches, jeder auf seiner eigenen
Kapitalbasis. Gemessen am Spitzenkandidaten, durchgehend, je 500 EUR:

    Bein                    Trades   Rueckgang des Beins
    BTC                         18            12,78 %
    ETH                         68            15,50 %   <- Kill-Switch
    beide als ein Konto          --           11,14 %   <- nie ausgeloest

**Das ETH-Bein loest den Not-Aus aus, obwohl das Konto ihn nie gesehen
haette.** Ein Konto mit beiden Maerkten faellt nur um 11,14 % zurueck - unter
der Kill-Switch-Grenze von 15 % und sogar unter der Gate-Schwelle von 12 %.
Was hier gemessen wurde, war nicht das Risiko des Kontos, sondern das Risiko
zweier getrennter Konten, die zufaellig dieselbe Regel handeln.

Was dieses Modul tut
--------------------
Es legt die Kapitalkurven aller Beine zu **einer** Kontokurve zusammen und
fuehrt den **echten** ``RiskOfficer`` darueber - Kerze fuer Kerze, mit der
Kerzenuhr. Damit steht fest, wann und ob ein Konto mit dieser Aufteilung
tatsaechlich pausiert oder abgeschaltet haette.

Bewusst der echte Officer und keine Nachbildung seiner Regeln: Zwei
Umsetzungen derselben Sache laufen auseinander, und in diesem Projekt ist
genau das schon fuenfmal passiert.

Was es **nicht** tut
--------------------
Es rechnet den Backtest nicht neu. Die Kontokurve entsteht aus Beinen, die
ihre eigenen Limits gesehen haben; wo das Konto frueher gebremst haette,
haetten die Beine danach anders gehandelt. Diese Rueckwirkung bildet das Modul
**nicht** ab - dafuer braeuchte es einen Backtest, der alle Maerkte im
Gleichschritt durchlaeuft, mit einem Konto und einem Officer.

Es beantwortet deshalb genau eine Frage, und nur die: **Haette das Konto
ueberhaupt ausgeloest?** Lautet die Antwort nein, dann ist jede Sperre, die
ein einzelnes Bein ausgeloest hat, ein Artefakt der Aufteilung - und die
Zahlen aus so einem Lauf beschreiben nicht, was ein Konto erlebt haette.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import pandas as pd
import structlog

from core.config import RiskSettings
from core.models import Instrument
from execution.risk import RiskOfficer, TradingState

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Ereignis:
    """Ein Zeitpunkt, an dem das Konto eine Grenze gerissen haette."""

    zeit: datetime
    art: str
    kapital: float
    rueckgang_pct: float

    def __str__(self) -> str:
        return (
            f"{self.zeit:%Y-%m-%d}  {self.art:14} Kapital {self.kapital:8.2f}, "
            f"Rueckgang {self.rueckgang_pct:5.2f} %"
        )


@dataclass(slots=True)
class Kontolauf:
    """Was der Risk-Officer auf der Kontokurve gesagt haette."""

    punkte: int
    hoechster_rueckgang_pct: float
    ereignisse: list[Ereignis] = field(default_factory=list)
    endzustand: str = TradingState.ACTIVE.value

    @property
    def haette_ausgeloest(self) -> bool:
        return bool(self.ereignisse)

    @property
    def erstes(self) -> Ereignis | None:
        return self.ereignisse[0] if self.ereignisse else None

    def bericht(self) -> str:
        if not self.punkte:
            return "Keine Kontokurve - nichts zu pruefen."
        zeilen = [
            f"Kontokurve ueber {self.punkte} Punkte, "
            f"hoechster Rueckgang {self.hoechster_rueckgang_pct:.2f} %."
        ]
        if not self.ereignisse:
            zeilen.append(
                "Das Konto haette **nichts** ausgeloest. Jede Sperre, die ein "
                "einzelnes Bein gemeldet hat, ist damit ein Artefakt der "
                "Aufteilung - sie beschreibt zwei getrennte Konten, nicht das "
                "eine, das es gibt."
            )
        else:
            zeilen.append(f"{len(self.ereignisse)} Ereignis(se):")
            zeilen.extend(f"  {e}" for e in self.ereignisse)
            zeilen.append(f"Endzustand: {self.endzustand}.")
        return "\n".join(zeilen)


def kontokurve(kurven: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Die Kapitalkurven aller Beine zu einer Kontokurve addieren.

    Fehlende Zeitpunkte werden fortgeschrieben, nicht mit null gefuellt: Ein
    Bein, das an einem Tag keinen Punkt liefert, hat sein Kapital nicht
    verloren - es hat nur nichts gemeldet. Mit Nullen entstuende ein
    Rueckgang, den es nie gab.
    """
    reihen = []
    for name, kurve in kurven.items():
        if kurve is None or kurve.empty:
            continue
        reihe = (
            kurve.set_index("time")["equity"]
            .astype(float)
            .groupby(level=0)
            .last()
            .rename(name)
        )
        reihen.append(reihe)
    if not reihen:
        return pd.DataFrame({"time": [], "equity": []})

    zusammen = pd.concat(reihen, axis=1).sort_index().ffill()
    # Vor dem ersten Punkt eines Beins gibt es nichts fortzuschreiben. Dort
    # zaehlt das Bein noch nicht mit - sonst begaenne das Konto mit Kapital,
    # das noch gar nicht im Markt war.
    gesamt = zusammen.sum(axis=1, min_count=1).dropna()
    return pd.DataFrame({"time": gesamt.index, "equity": gesamt.to_numpy()})


def pruefe(
    kurve: pd.DataFrame,
    *,
    risk: RiskSettings,
    instrument: Instrument,
    kerzenspanne=None,
) -> Kontolauf:
    """Den echten Risk-Officer ueber eine Kontokurve fuehren.

    Die Uhr zeigt auf den jeweiligen Kurvenpunkt - ohne das faenden alle
    Punkte am selben Tag statt, und Tages- wie Wochengrenze griffen nie.
    """
    if kurve is None or kurve.empty:
        return Kontolauf(punkte=0, hoechster_rueckgang_pct=0.0)

    jetzt = {"t": pd.Timestamp(kurve["time"].iloc[0]).to_pydatetime()}
    officer = RiskOfficer(
        risk,
        instrument,
        state_path=None,
        clock=lambda: jetzt["t"],
        kerzenspanne=kerzenspanne,
    )

    ereignisse: list[Ereignis] = []
    vorher = officer.state.trading_state
    hoechster = 0.0

    for zeit, kapital in zip(
        kurve["time"], kurve["equity"].astype(float), strict=False
    ):
        jetzt["t"] = pd.Timestamp(zeit).to_pydatetime()
        stand = officer.observe_equity(Decimal(str(round(kapital, 8))))
        hoechster = max(hoechster, float(stand.drawdown_pct))

        if stand.trading_state is not vorher:
            ereignisse.append(
                Ereignis(
                    zeit=jetzt["t"],
                    art=str(stand.trading_state),
                    kapital=kapital,
                    rueckgang_pct=float(stand.drawdown_pct),
                )
            )
            vorher = stand.trading_state

    return Kontolauf(
        punkte=len(kurve),
        hoechster_rueckgang_pct=hoechster,
        ereignisse=ereignisse,
        endzustand=str(vorher),
    )
