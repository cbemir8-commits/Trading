"""Die erste Generation von Strategie-Kandidaten.

Diese Genome sind **von Hand geschrieben**, nicht von einer KI erzeugt. Das ist
Absicht: Bevor die Research-KI Vorschlaege macht, muss die Zulassungsstrecke
selbst funktionieren - und dafuer braucht sie Kandidaten, deren Verhalten
vorhersagbar ist. Ein durchgefallenes Genom soll hier eine Aussage ueber die
Strategie sein, nicht ueber einen Fehler im Compiler.

Jedes Genom steht fuer eine **andere Hypothese darueber, warum der Markt Geld
hergibt**. Das ist der Punkt, an dem sich brauchbare von beliebigen Strategien
unterscheiden: Eine Regel ohne Begruendung laesst sich nicht widerlegen, und
aus einer nicht widerlegbaren Regel laesst sich nichts lernen. Faellt eine
Hypothese durch, weiss man **welche** - und die naechste Generation muss nicht
dieselbe Idee noch einmal probieren.

Bewusst schlicht gehalten: wenige Bedingungen, runde Perioden. Eine Strategie
mit sieben Filtern und Perioden wie 17, 23, 37 sieht im Backtest fast immer
besser aus und faellt live fast immer auseinander - genau dagegen sind die
Gates gebaut. Wer hier schon ueberanpasst, verschenkt die Aussagekraft der
Pruefung.
"""

from __future__ import annotations

from strategy.genome import Condition, Genome, Operand, Operator, StopSpec, TargetSpec


def _ind(name: str, **params: int) -> Operand:
    return Operand(kind="indicator", name=name, params=params)


def _price(name: str) -> Operand:
    return Operand(kind="price", name=name)


def _const(value: float) -> Operand:
    return Operand(kind="constant", value=value)


def trend_following() -> Genome:
    """Ausbruch in Trendrichtung.

    Hypothese: Ein neues 40-Perioden-Hoch, waehrend der Kurs ueber seinem
    200er-Durchschnitt liegt, setzt sich haeufiger fort als es dreht. Das ist
    die aelteste dokumentierte Anomalie an Terminmaerkten - und die, die am
    haeufigsten wieder verschwindet, wenn zu viele sie handeln.

    Der ADX-Filter haelt Seitwaertsphasen heraus. Ausbrueche ohne Trend sind
    die teuerste Sorte Fehlsignal: Sie loesen oft aus und laufen selten.
    """
    return Genome(
        name="Trendfolge Ausbruch",
        rationale=(
            "Ausbruch auf ein neues 40-Perioden-Hoch oberhalb des 200er-EMA, "
            "gefiltert durch ADX>20. Hypothese: Momentum setzt sich in "
            "etablierten Trends fort. Faellt es durch, spricht das dafuer, "
            "dass BTC auf 15m zu stark mean-revertet, um Ausbrueche zu tragen."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("donchian_upper", period=40)),
        ],
        entry_short=[
            Condition(left=_price("close"), op=Operator.CROSS_BELOW,
                      right=_ind("donchian_lower", period=40)),
        ],
        filters=[
            Condition(left=_ind("adx", period=14), op=Operator.GT, right=_const(20)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
        targets=[
            TargetSpec(rr=1.5, portion=0.5),
            TargetSpec(rr=3.0, portion=0.3),
            TargetSpec(rr=5.0, portion=0.2),
        ],
        cooldown_bars=8,
        max_hold_bars=200,
    )


def mean_reversion() -> Genome:
    """Rueckkehr zum Mittelwert nach Uebertreibung.

    Hypothese: Ein RSI unter 25 bei gleichzeitigem Unterschreiten des unteren
    Bollinger-Bandes markiert eine kurzfristige Uebertreibung, die sich
    zurueckbildet. Die Gegenthese zur Trendfolge - eine der beiden sollte
    durchfallen, sonst stimmt etwas mit der Auswertung nicht.

    Enge Ziele, weil Rueckkehrbewegungen kurz sind. Das kostet Trefferquote
    an Gebuehren und ist der Grund, warum Mean Reversion bei kleinen Konten
    haeufig scheitert.
    """
    return Genome(
        name="Mean Reversion Uebertreibung",
        rationale=(
            "RSI(14)<25 und Kurs unter dem unteren Bollinger-Band(20,2). "
            "Hypothese: kurzfristige Uebertreibungen bilden sich zurueck. "
            "Bewusst die Gegenthese zur Trendfolge - bestehen beide, ist die "
            "Auswertung verdaechtig."
        ),
        entry_long=[
            Condition(left=_ind("rsi", period=14), op=Operator.LT, right=_const(25)),
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("bollinger_lower", period=20, deviations=2)),
        ],
        filters=[
            Condition(left=_ind("adx", period=14), op=Operator.LT, right=_const(25)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[
            TargetSpec(rr=1.0, portion=0.6),
            TargetSpec(rr=2.0, portion=0.4),
        ],
        cooldown_bars=12,
        max_hold_bars=96,
    )


def momentum_pullback() -> Genome:
    """Ruecksetzer im intakten Aufwaertstrend.

    Hypothese: Der beste Einstieg in einen Trend ist nicht der Ausbruch,
    sondern der Ruecksetzer danach - gleiche Richtung, engerer Stop, also
    besseres Chance-Risiko-Verhaeltnis bei gleichem Risiko in Euro.

    Der engere Stop ist der eigentliche Punkt: Bei 0,75 % Risiko und einem
    halb so weiten Stop ist die Position doppelt so gross und der Hebel
    doppelt so hoch - bei identischem Verlust im Stop-Fall.
    """
    return Genome(
        name="Momentum Ruecksetzer",
        rationale=(
            "Im Aufwaertstrend (EMA50>EMA200) auf einen RSI-Ruecksetzer unter "
            "40 kaufen, sobald er wieder ueber 40 steigt. Hypothese: "
            "Ruecksetzer bieten dieselbe Richtung bei engerem Stop und damit "
            "besserem Chance-Risiko-Verhaeltnis als der Ausbruch selbst."
        ),
        entry_long=[
            Condition(left=_ind("rsi", period=14), op=Operator.CROSS_ABOVE,
                      right=_const(40)),
        ],
        entry_short=[
            Condition(left=_ind("rsi", period=14), op=Operator.CROSS_BELOW,
                      right=_const(60)),
        ],
        filters=[
            Condition(left=_ind("adx", period=14), op=Operator.GT, right=_const(18)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=1.2),
        targets=[
            TargetSpec(rr=1.5, portion=0.5),
            TargetSpec(rr=3.0, portion=0.5),
        ],
        cooldown_bars=6,
        max_hold_bars=160,
    )


def volatility_breakout() -> Genome:
    """Ausbruch aus der Ruhe.

    Hypothese: Auf Phasen enger Bollinger-Baender folgen ueberdurchschnittlich
    grosse Bewegungen ("Volatilitaet clustert"). Der Effekt ist empirisch gut
    belegt - offen ist nur, ob er nach Gebuehren noch etwas uebrig laesst.

    Der Volumenfilter soll Ausbrueche ohne Beteiligung heraushalten. Ob er das
    leistet, ist selbst eine Hypothese: Bei Krypto laeuft ein erheblicher Teil
    des Volumens ausserhalb der Boerse, an der wir handeln.
    """
    return Genome(
        name="Volatilitaets-Ausbruch",
        rationale=(
            "Nach einer Phase enger Bollinger-Baender auf den Ausbruch aus dem "
            "20-Perioden-Kanal setzen, bestaetigt durch ueberdurchschnittliches "
            "Volumen. Hypothese: Volatilitaet clustert, auf Ruhe folgt Bewegung."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("donchian_upper", period=20)),
        ],
        entry_short=[
            Condition(left=_price("close"), op=Operator.CROSS_BELOW,
                      right=_ind("donchian_lower", period=20)),
        ],
        filters=[
            Condition(left=_ind("volume_zscore", period=50), op=Operator.GT,
                      right=_const(1.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=20, multiple=1.8),
        targets=[
            TargetSpec(rr=2.0, portion=0.5),
            TargetSpec(rr=4.0, portion=0.5),
        ],
        cooldown_bars=10,
        max_hold_bars=180,
    )


def ema_cross() -> Genome:
    """Der Klassiker - als Messlatte, nicht als Hoffnung.

    Die simpelste denkbare Trendstrategie. Sie steht hier, weil eine
    komplexere Strategie sich an ihr messen lassen muss: Wer mit sechs
    Indikatoren nicht deutlich besser abschneidet als ein Durchschnitts-
    kreuzer, hat die Komplexitaet umsonst bezahlt.

    Erwartung: faellt am Gebuehren-Stresstest oder an der Trefferquote. Das
    waere ein brauchbares Ergebnis, kein schlechtes.
    """
    return Genome(
        name="EMA-Kreuzung (Messlatte)",
        rationale=(
            "EMA(20) kreuzt EMA(50). Dient als Vergleichsmassstab: Eine "
            "aufwendigere Strategie muss diesen einfachen Kreuzer deutlich "
            "schlagen, sonst ist ihre Komplexitaet nicht bezahlt."
        ),
        entry_long=[
            Condition(left=_ind("ema", period=20), op=Operator.CROSS_ABOVE,
                      right=_ind("ema", period=50)),
        ],
        entry_short=[
            Condition(left=_ind("ema", period=20), op=Operator.CROSS_BELOW,
                      right=_ind("ema", period=50)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[
            TargetSpec(rr=2.0, portion=0.5),
            TargetSpec(rr=4.0, portion=0.5),
        ],
        cooldown_bars=4,
        max_hold_bars=240,
    )


#: Die erste Generation. Reihenfolge egal - alle werden geprueft.
SEED_GENOMES = [
    trend_following,
    momentum_pullback,
    volatility_breakout,
    mean_reversion,
    ema_cross,
]


def load_seeds() -> list[Genome]:
    """Alle Kandidaten der ersten Generation erzeugen."""
    return [build() for build in SEED_GENOMES]
