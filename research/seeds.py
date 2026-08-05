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

from strategy.genome import (
    Condition,
    Genome,
    Operand,
    Operator,
    SizingSpec,
    StopSpec,
    TargetSpec,
)


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


# ===========================================================================
#  Zweite Generation - gebaut gegen das, woran die erste gescheitert ist
# ===========================================================================
#
# Der erste Zulassungslauf ueber sechs Jahre BTC hat alle fuenf Kandidaten
# widerlegt, und zwar mit einem sehr einheitlichen Muster:
#
#   * Erwartungswert je Trade zwischen -0,089 und -0,496 R.
#   * 2350 bis 6886 Trades in sechs Jahren - 30 bis 95 im Monat.
#   * Gebuehren: 16,7 % vom Bruttogewinn.
#   * Der **einfachste** Kandidat (EMA-Kreuzer) schnitt am besten ab. Jeder
#     zusaetzliche Filter machte es schlechter.
#   * Schwaechstes Umfeld ueberall: Seitwaerts, mit Faktor 0,60 bis 0,75.
#
# Daraus folgen vier Aenderungen, alle in dieselbe Richtung:
#
# 1. **Deutlich seltener handeln.** Nicht auf 15 Minuten, sondern auf einer
#    Stunde. Bei 30 Trades im Monat frisst die Gebuehr den Vorteil, bevor er
#    entstehen kann - das ist keine Vermutung mehr, das steht in den Zahlen.
#
# 2. **Groessere Ziele.** Wenn 16 % des Bruttogewinns an Gebuehren gehen, muss
#    ein Gewinner mehr tragen als 1,5 R. Die Ziele liegen jetzt bei 3 bis 12 R.
#
# 3. **Weitere Stops.** Wer selten handelt, kann sich Luft leisten - und wird
#    nicht von jedem Rauschen ausgestoppt.
#
# 4. **Trendfilter statt Indikatorfilter.** Nicht "ADX ueber 20", sondern
#    "ueberhaupt nur handeln, wenn der Kurs klar ueber seinem 200er-Schnitt
#    liegt". Der Seitwaertsmarkt hat jede Strategie der ersten Generation
#    gekostet; er wird jetzt ausgeschlossen statt gefiltert.
#
# Was bewusst NICHT passiert: mehr Bedingungen. Die erste Generation hat
# gezeigt, dass zusaetzliche Filter hier schaden. Jedes Genom unten hat
# hoechstens zwei.


def big_trend_breakout() -> Genome:
    """Ausbruch, aber nur im etablierten Aufwaertstrend - und mit weiten Zielen.

    Hypothese: Der Ausbruch als Signal war nicht das Problem der ersten
    Generation, sondern seine Haeufigkeit und die zu nahen Ziele. Auf
    Stundenbasis, nur oberhalb des 200er-EMA und mit Zielen bis 10 R traegt
    ein Gewinner die Gebuehren mehrerer Fehlversuche.
    """
    return Genome(
        name="Grosser Trendausbruch",
        rationale=(
            "Ausbruch ueber den 50-Perioden-Kanal, nur wenn der Kurs mehr als "
            "1 % ueber seinem 200er-EMA liegt. Ziele bis 10 R. Hypothese: Das "
            "Ausbruchssignal taugt, aber nur selten und nur mit Zielen, die "
            "die Gebuehren mehrerer Fehlversuche tragen."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("donchian_upper", period=50)),
        ],
        filters=[
            Condition(left=_ind("distance_to_ema_pct", period=200), op=Operator.GT,
                      right=_const(1.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=20, multiple=2.5),
        targets=[
            TargetSpec(rr=3.0, portion=0.4),
            TargetSpec(rr=6.0, portion=0.3),
            TargetSpec(rr=10.0, portion=0.3),
        ],
        cooldown_bars=24,
        max_hold_bars=480,
    )


def trend_only_long() -> Genome:
    """Nur mitlaufen, nie dagegen.

    Hypothese: Bitcoin hatte ueber den gesamten Untersuchungszeitraum eine
    starke Aufwaertsdrift. Wer short geht, handelt gegen sie und zahlt dabei
    noch Funding. Die erste Generation handelte beide Richtungen - und verlor
    in beiden.

    Faellt dieses Genom durch, waehrend die zweiseitigen Varianten es nicht
    tun, war die Drift nicht der Punkt.
    """
    return Genome(
        name="Nur mit der Drift",
        rationale=(
            "Ausbruch ueber den 30-Perioden-Kanal, nur wenn EMA(100) ueber "
            "EMA(400) liegt. Ausschliesslich Long. Hypothese: Die Aufwaertsdrift "
            "von BTC macht Shorts strukturell teuer - erst recht mit Funding."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("donchian_upper", period=30)),
        ],
        filters=[
            Condition(left=_ind("ema", period=100), op=Operator.GT,
                      right=_ind("ema", period=400)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[
            TargetSpec(rr=4.0, portion=0.5),
            TargetSpec(rr=8.0, portion=0.5),
        ],
        cooldown_bars=18,
        max_hold_bars=360,
    )


def strong_trend_momentum() -> Genome:
    """Momentum, aber nur wenn der Trend wirklich stark ist.

    Hypothese: Die erste Generation filterte mit ADX>18 bis 20 - das laesst
    fast alles durch. Bei ADX>22 bleiben nur ausgepraegte Trendphasen uebrig.

    Die Schwellen wurden zweimal gelockert (ADX 30 -> 25 -> 22, Momentum
    3 % -> 2 % -> 1 %): Bei 30 lieferte das Genom 0,4 Trades im Monat -
    zu wenig fuer eine belastbare Aussage, das Genom waere schon am
    Stichprobenumfang gescheitert statt an seiner Hypothese. Ein Kandidat,
    der aus Mangel an Gelegenheiten durchfaellt, hat nichts widerlegt.
    """
    return Genome(
        name="Starker Trend, Momentum",
        rationale=(
            "Einstieg, wenn das 20-Perioden-Momentum ueber 3 % steigt, "
            "gefiltert durch ADX>22. Hypothese: Nicht das Momentum war das "
            "Problem, sondern dass es auch in Seitwaertsphasen ausgeloest hat."
        ),
        entry_long=[
            Condition(left=_ind("roc", period=20), op=Operator.CROSS_ABOVE,
                      right=_const(1.0)),
        ],
        entry_short=[
            Condition(left=_ind("roc", period=20), op=Operator.CROSS_BELOW,
                      right=_const(-1.0)),
        ],
        filters=[
            Condition(left=_ind("adx", period=20), op=Operator.GT, right=_const(22)),
        ],
        stop=StopSpec(kind="atr", atr_period=20, multiple=3.0),
        targets=[
            TargetSpec(rr=3.0, portion=0.5),
            TargetSpec(rr=7.0, portion=0.5),
        ],
        cooldown_bars=24,
        max_hold_bars=400,
    )


def rare_big_breakout() -> Genome:
    """Der seltenste Kandidat: Ausbruch auf 100-Perioden-Hoch.

    Hypothese: Je seltener das Signal, desto bedeutsamer. Ein neues
    100-Stunden-Hoch im Aufwaertstrend ist ein anderes Ereignis als ein neues
    20-Stunden-Hoch.

    Das ist zugleich ein Test der Gegenrichtung: Wenn auch das durchfaellt,
    liegt es nicht an der Haeufigkeit.
    """
    return Genome(
        name="Seltener grosser Ausbruch",
        rationale=(
            "Ausbruch ueber das 100-Perioden-Hoch oberhalb des 200er-EMA, "
            "Ziele bis 12 R, lange Sperrfrist. Hypothese: Seltene Signale sind "
            "aussagekraeftiger - und nur sie tragen die Gebuehren."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("donchian_upper", period=100)),
        ],
        filters=[
            Condition(left=_ind("distance_to_ema_pct", period=200), op=Operator.GT,
                      right=_const(0.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=30, multiple=2.5),
        targets=[
            TargetSpec(rr=5.0, portion=0.5),
            TargetSpec(rr=12.0, portion=0.5),
        ],
        cooldown_bars=48,
        max_hold_bars=720,
    )


def slow_cross() -> Genome:
    """Die neue Messlatte - derselbe Kreuzer, nur langsamer und mit weiten Zielen.

    Der EMA-Kreuzer war in der ersten Generation der beste Kandidat, obwohl er
    der einfachste ist. Diese Fassung aendert genau zwei Dinge: langsamere
    Perioden und Ziele bei 4 und 10 R statt 2 und 4.

    Damit laesst sich die zentrale Vermutung der zweiten Generation direkt
    pruefen - dass Handelsfrequenz und Zielgroesse das Problem waren, nicht
    das Signal.
    """
    return Genome(
        name="Langsamer Kreuzer (Messlatte 2)",
        rationale=(
            "EMA(50) kreuzt EMA(200), Ziele bei 4 und 10 R. Bewusst nur zwei "
            "Aenderungen gegenueber der ersten Messlatte: langsamer und weitere "
            "Ziele. Faellt sie besser aus, lag es an Frequenz und Zielgroesse - "
            "nicht am Signal."
        ),
        entry_long=[
            Condition(left=_ind("ema", period=50), op=Operator.CROSS_ABOVE,
                      right=_ind("ema", period=200)),
        ],
        entry_short=[
            Condition(left=_ind("ema", period=50), op=Operator.CROSS_BELOW,
                      right=_ind("ema", period=200)),
        ],
        stop=StopSpec(kind="atr", atr_period=20, multiple=3.0),
        targets=[
            TargetSpec(rr=4.0, portion=0.5),
            TargetSpec(rr=10.0, portion=0.5),
        ],
        cooldown_bars=24,
        max_hold_bars=720,
    )


#: Erste Generation - widerlegt, bleibt fuer die Nachvollziehbarkeit erhalten.
GENERATION_1 = [
    trend_following,
    momentum_pullback,
    volatility_breakout,
    mean_reversion,
    ema_cross,
]

#: Zweite Generation: seltener handeln, groessere Ziele, weitere Stops,
#: Trendfilter statt Indikatorfilter.
GENERATION_2 = [
    big_trend_breakout,
    trend_only_long,
    strong_trend_momentum,
    rare_big_breakout,
    slow_cross,
]

# ===========================================================================
#  Dritte Generation - nicht *wann handeln*, sondern *wann investiert sein*
# ===========================================================================
#
# Zehn widerlegte Hypothesen der Generationen 1 und 2 hatten alle dieselbe
# Bauform: Sie versuchten, die naechste Bewegung vorherzusagen. Das ist das am
# gruendlichsten durchgekaemmte Gebiet der ganzen Finanzwelt, und die Zahlen
# sagen deutlich, dass dort nichts uebrig ist - jedenfalls nicht mit
# Indikatoren, die jeder kennt.
#
# Diese Generation stellt eine andere Frage. Nicht "wohin geht der Kurs",
# sondern "**soll ich gerade ueberhaupt investiert sein**". Der Unterschied
# ist grundlegend:
#
#   * Es wird nichts vorhergesagt. Die Regel schaltet Beteiligung an und aus.
#   * Ausgestiegen wird nicht an einer Preismarke, sondern wenn die Bedingung
#     endet. Dafuer gibt es seit dieser Generation ``exit_long``.
#   * Gehandelt wird wenige Male im Jahr. Die Gebuehren, an denen die ersten
#     zehn Kandidaten gestorben sind, fallen praktisch nicht mehr ins Gewicht.
#
# Der Massstab ist ein anderer: Diese Strategien schlagen einfaches Halten
# nicht in der Rendite - das schafft fast nichts. Sie sollen den **groessten
# Rueckgang** deutlich senken und dabei den groesseren Teil der Rendite
# behalten. Fuer ein Konto mit Kill-Switch bei 15 % ist das der relevante
# Handel: Halten hatte in diesem Zeitraum Drawdowns von ueber 70 %, und die
# haetten das Konto laengst abgeschaltet.
#
# Ehrlich dazugesagt: Diese Kandidaten handeln so selten, dass sie am
# Stichprobenumfang von 100 Trades scheitern werden. Das ist kein Fehler der
# Strategien, sondern eine Schwelle, die fuer Mustersuche gemacht ist und fuer
# Investitionssteuerung nicht passt. Sie brauchen eine eigene Bewertung -
# die steht noch aus, und bis dahin ist diese Generation ein Vorschlag, kein
# Ergebnis.


def trend_exposure() -> Genome:
    """Investiert, solange der Kurs ueber seinem langfristigen Schnitt liegt.

    Die aelteste und am besten dokumentierte Regel dieser Art. Hypothese: Sie
    verhindert nicht die ersten 20 % eines Absturzes, aber die restlichen 50 -
    und genau die entscheiden, ob ein Konto mit Kill-Switch ueberlebt.
    """
    return Genome(
        name="Trendbeteiligung EMA200",
        rationale=(
            "Long, solange der Kurs ueber dem 200er-EMA liegt, raus wenn er "
            "darunter faellt. Hypothese: Die Regel verhindert nicht den Beginn "
            "eines Absturzes, aber den Grossteil davon. Ziel ist nicht mehr "
            "Rendite als Halten, sondern deutlich weniger Rueckgang."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("ema", period=200)),
        ],
        exit_long=[
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("ema", period=200)),
        ],
        # Der Stop ist hier **Notbremse, nicht Ausstieg** - ausgestiegen wird
        # ueber die Bedingung. 3 % ist der Hoechstwert, den die Risikoregeln
        # zulassen; ein 6xATR-Stop, wie er zu dieser Bauform passen wuerde,
        # wird vom Sizer abgelehnt (stop_too_wide). Das ist ein Kompromiss und
        # kein Entwurf: Auf Stundenkerzen wird eine 3-%-Marke oft von Rauschen
        # getroffen, und jeder solche Treffer nimmt genau die Position weg,
        # die die Regel eigentlich halten wollte.
        stop=StopSpec(kind="percent", percent=3.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        cooldown_bars=0,
        max_hold_bars=0,
    )


def slow_trend_exposure() -> Genome:
    """Dasselbe, aber traeger - mit Abstandspuffer gegen Fehlausstiege.

    Hypothese: Der EMA200 wird oft knapp durchbrochen und sofort wieder
    zurueckerobert. Jedes Mal kostet das zwei Gebuehren und einen verpassten
    Wiedereinstieg. Ein Puffer von 2 % laesst solche Faelle durchlaufen.
    """
    return Genome(
        name="Trendbeteiligung mit Puffer",
        rationale=(
            "Long, wenn der Kurs mehr als 2 % ueber dem 200er-EMA liegt; raus, "
            "wenn er mehr als 2 % darunter faellt. Hypothese: Der Puffer "
            "verhindert das staendige Hin und Her um die Linie herum, das "
            "jede einfache Trendregel teuer macht."
        ),
        entry_long=[
            Condition(left=_ind("distance_to_ema_pct", period=200), op=Operator.GT,
                      right=_const(2.0)),
        ],
        exit_long=[
            Condition(left=_ind("distance_to_ema_pct", period=200), op=Operator.LT,
                      right=_const(-2.0)),
        ],
        # Der Stop ist hier **Notbremse, nicht Ausstieg** - ausgestiegen wird
        # ueber die Bedingung. 3 % ist der Hoechstwert, den die Risikoregeln
        # zulassen; ein 6xATR-Stop, wie er zu dieser Bauform passen wuerde,
        # wird vom Sizer abgelehnt (stop_too_wide). Das ist ein Kompromiss und
        # kein Entwurf: Auf Stundenkerzen wird eine 3-%-Marke oft von Rauschen
        # getroffen, und jeder solche Treffer nimmt genau die Position weg,
        # die die Regel eigentlich halten wollte.
        stop=StopSpec(kind="percent", percent=3.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        cooldown_bars=0,
        max_hold_bars=0,
    )


def momentum_exposure() -> Genome:
    """Beteiligung nach Zwoelfmonats-Momentum.

    Hypothese: Die am breitesten belegte Anomalie ueberhaupt - Maerkte, die
    ueber lange Zeitraeume gestiegen sind, steigen eher weiter. Anders als die
    EMA-Regel schaut diese auf die absolute Veraenderung statt auf eine Linie.

    Bewusst als dritte Variante derselben Idee: Wenn alle drei aehnlich
    ausfallen, liegt es an der Idee und nicht an der Umsetzung.
    """
    return Genome(
        name="Momentum-Beteiligung",
        rationale=(
            "Long, wenn die Veraenderung ueber 90 Perioden positiv ist; raus, "
            "wenn sie negativ wird. Hypothese: Zeitreihen-Momentum - die am "
            "breitesten belegte Anomalie - wirkt auch auf BTC."
        ),
        entry_long=[
            Condition(left=_ind("roc", period=90), op=Operator.CROSS_ABOVE,
                      right=_const(0.0)),
        ],
        exit_long=[
            Condition(left=_ind("roc", period=90), op=Operator.LT, right=_const(0.0)),
        ],
        # Der Stop ist hier **Notbremse, nicht Ausstieg** - ausgestiegen wird
        # ueber die Bedingung. 3 % ist der Hoechstwert, den die Risikoregeln
        # zulassen; ein 6xATR-Stop, wie er zu dieser Bauform passen wuerde,
        # wird vom Sizer abgelehnt (stop_too_wide). Das ist ein Kompromiss und
        # kein Entwurf: Auf Stundenkerzen wird eine 3-%-Marke oft von Rauschen
        # getroffen, und jeder solche Treffer nimmt genau die Position weg,
        # die die Regel eigentlich halten wollte.
        stop=StopSpec(kind="percent", percent=3.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        cooldown_bars=0,
        max_hold_bars=0,
    )


#: Dritte Generation: Beteiligungssteuerung statt Mustersuche.
GENERATION_3 = [
    trend_exposure,
    slow_trend_exposure,
    momentum_exposure,
]

# ===========================================================================
#  Vierte Generation - andere Daten, nicht andere Regeln
# ===========================================================================
#
# Die Generationen 1 bis 3 hatten eine Gemeinsamkeit, die lange nicht auffiel:
# Sie benutzten **alle dieselbe Datenquelle**. Kerzen. Also genau die Zahlen,
# die weltweit am gruendlichsten durchsucht sind - seit Jahrzehnten, von
# Firmen mit eigenen Rechenzentren. Dass dort mit gleitenden Durchschnitten
# nichts mehr liegt, ist keine Ueberraschung, sondern die Erwartung.
#
# Diese Generation aendert nicht die Regeln, sondern die **Eingangsdaten**.
#
# Die Funding-Rate ist keine Kursbewegung, sondern Positionierung: Sie sagt,
# wer gerade gedraengt steht. Bei stark positiver Rate zahlen die Longs den
# Shorts - das passiert, wenn zu viele long sind. Diese Information steckt in
# keiner Kerze, und sie existiert nur bei Perpetuals. Aktien, Anleihen und
# Devisen kennen nichts Vergleichbares; die grosse quantitative Industrie hat
# ihre Werkzeuge an jenen Maerkten entwickelt. Der Kreis derer, die hier
# suchen, ist um Groessenordnungen kleiner.
#
# Das ist keine Garantie. Es ist der erste Ort, an dem Suchen ueberhaupt Sinn
# ergibt.
#
# Voraussetzung: ``python -m cli funding`` muss gelaufen sein. Ohne die Daten
# liefern die Funding-Indikatoren NaN, und die Strategien handeln nicht - was
# richtig ist, aber im Bericht wie ein Fehlschlag aussieht.


def funding_extreme_fade() -> Genome:
    """Nicht kaufen, wenn alle schon long sind.

    Hypothese: Eine ungewoehnlich hohe Funding-Rate bedeutet, dass die
    Long-Seite gedraengt steht. Solche Positionen werden bei jedem Rueckschlag
    zuerst liquidiert - was den Rueckschlag verstaerkt. Wer dann erst
    einsteigt, kauft die Position derer, die gleich verkaufen muessen.

    Bewusst als **Filter** formuliert, nicht als eigenes Signal: Der Einstieg
    bleibt der einfache Trendausbruch aus Generation 2. Wenn dieses Genom
    besser abschneidet als sein Zwilling ohne Funding-Filter, liegt es an der
    neuen Datenquelle - und nur daran.
    """
    return Genome(
        name="Ausbruch ohne Long-Ueberhitzung",
        rationale=(
            "Derselbe Trendausbruch wie in Generation 2, aber nur wenn die "
            "Funding-Rate nicht ungewoehnlich hoch ist (z-Wert unter 1,5). "
            "Hypothese: Bei ueberhitzter Long-Seite kauft man die Position "
            "derer, die beim naechsten Rueckschlag liquidiert werden."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("donchian_upper", period=50)),
        ],
        filters=[
            Condition(left=_ind("funding_zscore", period=90), op=Operator.LT,
                      right=_const(1.5)),
        ],
        stop=StopSpec(kind="atr", atr_period=20, multiple=2.5),
        targets=[
            TargetSpec(rr=3.0, portion=0.5),
            TargetSpec(rr=8.0, portion=0.5),
        ],
        cooldown_bars=24,
        max_hold_bars=480,
    )


def funding_carry_long() -> Genome:
    """Long, wenn die Shorts zahlen.

    Hypothese: Eine dauerhaft **negative** Funding-Rate heisst, dass Shorts
    den Longs Geld zahlen. Wer dann long ist, bekommt alle acht Stunden etwas
    ueberwiesen - unabhaengig davon, wohin der Kurs laeuft.

    Das ist der eigentlich neue Gedanke: **keine Prognose, sondern ein
    Zahlungsstrom.** Alle bisherigen 13 Hypothesen mussten richtig raten, um
    zu verdienen. Diese nicht - sie muss nur nicht zu falsch liegen, waehrend
    das Geld fliesst.
    """
    return Genome(
        name="Funding-Carry Long",
        rationale=(
            "Long, wenn die durchschnittliche Funding-Rate der letzten Woche "
            "negativ ist - dann zahlen die Shorts. Raus, sobald sie wieder "
            "positiv wird. Hypothese: Ein Zahlungsstrom ist verlaesslicher "
            "als eine Prognose; die Position muss nur nicht zu falsch sein, "
            "waehrend das Geld fliesst."
        ),
        entry_long=[
            Condition(left=_ind("funding_avg", period=21), op=Operator.LT,
                      right=_const(0.0)),
        ],
        exit_long=[
            Condition(left=_ind("funding_avg", period=21), op=Operator.GT,
                      right=_const(0.0)),
        ],
        stop=StopSpec(kind="percent", percent=3.0),
        targets=[TargetSpec(rr=15.0, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=0,
    )


def funding_crowd_short() -> Genome:
    """Short gegen die ueberhitzte Long-Seite.

    Hypothese: Bei extremer Funding-Rate ist die Long-Seite so gedraengt, dass
    schon eine kleine Gegenbewegung Liquidationen ausloest - und die naehren
    sich selbst. Das ist die schaerfste Fassung der Positionierungs-These, und
    zugleich die riskanteste: Gegen einen starken Trend zu stehen kostet, wenn
    man zu frueh dran ist.

    Faellt dieses Genom durch, waehrend der Filter oben funktioniert, dann
    taugt Funding als Warnung, aber nicht als Signal. Auch das waere ein
    brauchbares Ergebnis.
    """
    return Genome(
        name="Gegen die ueberhitzte Long-Seite",
        rationale=(
            "Short, wenn die Funding-Rate ungewoehnlich hoch ist (z-Wert ueber "
            "2). Hypothese: Eine gedraengte Long-Seite loest bei kleinen "
            "Rueckschlaegen Liquidationen aus, die sich selbst naehren. "
            "Riskanteste Fassung der These - gegen den Trend zu stehen kostet, "
            "wenn man zu frueh dran ist."
        ),
        entry_short=[
            Condition(left=_ind("funding_zscore", period=90), op=Operator.CROSS_ABOVE,
                      right=_const(2.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=20, multiple=2.0),
        targets=[
            TargetSpec(rr=2.0, portion=0.6),
            TargetSpec(rr=5.0, portion=0.4),
        ],
        cooldown_bars=48,
        max_hold_bars=240,
    )


#: Vierte Generation: andere Eingangsdaten statt anderer Regeln.
GENERATION_4 = [
    funding_extreme_fade,
    funding_carry_long,
    funding_crowd_short,
]



# ===========================================================================
#  Fuenfte Generation - dieselben Ideen, ohne unsere eigene Fessel
# ===========================================================================
#
# Die dritte Generation wollte Beteiligung steuern statt Muster suchen. Sie
# konnte es nie zeigen. Nicht weil die Idee falsch war, sondern weil zwei
# Zahlen im eigenen Aufbau sie unmoeglich machten:
#
#   max_stop_distance_pct = 3.0   -> weitere Stops wurden abgelehnt
#   min_oos_trades        = 100   -> wer lange haelt, erreicht das nie
#
# Beide sind fuer wettende Strategien richtig und fuer investierte falsch. Der
# Kompromiss war ein 3-%-Stop auf Stundenkerzen - eine Marke, die staendig von
# Rauschen getroffen wird und dabei genau die Position wegnimmt, die die Regel
# halten wollte. Aus 535 Signalen wurden null Trades.
#
# Diese Generation ist deshalb keine neue Hypothese, sondern dieselbe unter
# fairen Bedingungen: Positionsgroesse aus dem Kapitalanteil, Stop als
# Notbremse weit draussen, Ausstieg ueber die Bedingung. Wenn die dritte
# Generation nun besteht, lag es an uns. Wenn sie wieder faellt, an der Idee.
#
# Die Lockerung ist nicht umsonst: Genau diese Bauform muss zusaetzlich die
# Messlatte schlagen - Kaufen-und-Halten im selben Zeitraum, risikobereinigt.
# Ohne diesen Zusatz waere "immer long" ein Kandidat, der bequem durchkaeme.
#
# ACHTUNG, TAGESKERZEN
# --------------------
# Diese Generation gehoert auf ``-i D`` und nirgendwo sonst. Der Grund ist eine
# Beschraenkung, die man leicht uebersieht: Die Indikator-Whitelist laesst
# hoechstens 400 Perioden zu. Auf Stundenkerzen sind 200 Perioden deshalb
# **acht Tage**, nicht acht Monate - und der klassische Langfristfilter laesst
# sich dort ueberhaupt nicht ausdruecken.
#
# Beim ersten Entwurf stand in den Begruendungen "langfristiger Durchschnitt"
# und "die letzte Woche", waehrend der Code auf Stundenkerzen acht Tage und
# einen Tag meinte. Eine Halte-Strategie mit Acht-Tage-Filter haelt nichts;
# sie springt rein und raus und frisst genau die Gebuehren, die diese
# Generation vermeiden sollte. Der Text war richtig, die Zeitebene falsch.
#
#     python -m cli backfill --intervall D
#     python -m cli research --intervall D


def funding_aware_exposure() -> Genome:
    """Investiert, ausser die Long-Seite ist ueberhitzt.

    Hypothese: Die Rendite von BTC entsteht ueber lange Haltezeiten, nicht in
    einzelnen Ausbruechen - deshalb ist Investiertsein der Normalzustand. Die
    teuren Abschnitte sind die, in denen alle long sind: Dort ist die Rate
    hoch, jeder Ruecksetzer loest Liquidationen aus, und die naehren sich
    selbst.

    Das ist die erste Regel, die Funding **zum Aussteigen** benutzt statt zum
    Einsteigen - und die erste, die von der Messlatte aus denkt statt vom
    einzelnen Trade. Nicht "wann ist ein guter Einstieg", sondern "wann lohnt
    es sich, nicht dabei zu sein".
    """
    return Genome(
        name="Beteiligt, ausser es ist ueberhitzt",
        rationale=(
            "Long, solange der Kurs ueber seinem 200er-Schnitt liegt und die "
            "Funding-Rate nicht ungewoehnlich hoch ist. Raus, sobald der "
            "z-Wert der Funding-Rate ueber 1,5 steigt oder der Trend bricht. "
            "Hypothese: Die Rendite entsteht ueber lange Haltezeiten; teuer "
            "sind die Abschnitte mit gedraengter Long-Seite."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.GT,
                      right=_ind("sma", period=200)),
            Condition(left=_ind("funding_zscore", period=90), op=Operator.LT,
                      right=_const(1.5)),
        ],
        exit_long=[
            Condition(left=_ind("funding_zscore", period=90), op=Operator.GT,
                      right=_const(1.5)),
        ],
        # Notbremse, kein Ausstieg: 15 % liegt so weit draussen, dass normales
        # Rauschen sie nicht erreicht. Ausgestiegen wird ueber die Bedingung.
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        cooldown_bars=0,
        max_hold_bars=0,
    )


def trend_exposure_fair() -> Genome:
    """Die dritte Generation, endlich unter fairen Bedingungen.

    Wortgleiche Regel wie ``trend_exposure`` - long ueber dem 200er-Schnitt,
    raus darunter. Geaendert ist allein, was ausserhalb der Regel liegt:
    Positionsgroesse aus dem Kapitalanteil, Stop weit genug draussen, um
    Notbremse zu sein.

    Deshalb ist dieser Kandidat der wichtigste des Laufs, obwohl er der
    langweiligste ist: Er ist der **Kontrollversuch**. Ein Unterschied zur
    dritten Generation ist ausschliesslich unserem eigenen Aufbau zuzurechnen.
    """
    return Genome(
        name="Trend-Beteiligung (fair gerechnet)",
        rationale=(
            "Long ueber dem 200er-Schnitt, raus darunter. Identisch zur "
            "dritten Generation; nur Positionsgroesse und Stop folgen jetzt "
            "der Bauform statt der Wettformel. Kontrollversuch: Ein "
            "Unterschied liegt dann an unserem Aufbau, nicht an der Idee."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("sma", period=200)),
        ],
        exit_long=[
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("sma", period=200)),
        ],
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        cooldown_bars=0,
        max_hold_bars=0,
    )


def carry_exposure() -> Genome:
    """Beteiligt, wenn die Shorts zahlen.

    Der Carry-Gedanke der vierten Generation, aber als Beteiligung statt als
    Wette. Dort scheiterte er an 11 Trades im Monat und 24 % Gebuehren vom
    Bruttogewinn - die Idee war ein Zahlungsstrom, die Umsetzung ein
    Vielhandelssystem. Das passt nicht zusammen.

    Hier bleibt die Position, solange die Woche im Schnitt guenstig war, und
    der Ausstieg braucht eine deutliche Gegenbewegung statt eines
    Vorzeichenwechsels. Weniger Umschlag, weniger Gebuehren, laengere
    Haltezeit - so, wie ein Zahlungsstrom vereinnahmt wird.
    """
    return Genome(
        name="Carry-Beteiligung",
        rationale=(
            "Long, wenn die Funding-Rate der letzten Woche im Schnitt unter "
            "0,01 % liegt - also guenstig oder negativ. Raus erst bei "
            "deutlich positivem Schnitt ueber 0,03 %. Hypothese: Der "
            "Carry-Gedanke stimmt, aber er ertraegt keinen haeufigen Handel; "
            "in Generation 4 frassen 11 Trades im Monat 24 % des Bruttogewinns."
        ),
        entry_long=[
            Condition(left=_ind("funding_avg", period=7), op=Operator.LT,
                      right=_const(0.01)),
        ],
        exit_long=[
            Condition(left=_ind("funding_avg", period=7), op=Operator.GT,
                      right=_const(0.03)),
        ],
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        cooldown_bars=0,
        max_hold_bars=0,
    )


#: Fuenfte Generation: Beteiligung, diesmal wirklich messbar.
GENERATION_5 = [
    trend_exposure_fair,
    funding_aware_exposure,
    carry_exposure,
]



# ===========================================================================
#  Sechste Generation - schnell handeln, wie ein Haendler es taete
# ===========================================================================
#
# Kurze Haltedauern, enge Stops, Hebel. Vier Bauformen, die in der Praxis
# tatsaechlich so gehandelt werden - nicht ausgedachte Varianten, sondern das,
# was ein Daytrader am Bildschirm macht.
#
# DIE RECHNUNG, DIE MAN VORHER KENNEN MUSS
# ----------------------------------------
# Gebuehren zaehlen nicht in Prozent vom Nominalwert, sondern als Anteil am
# Risiko. Der Umrechnungsfaktor ist die Stop-Distanz:
#
#     Gebuehr in R = Gebuehrensatz / Stop-Distanz
#
# Bei VIP0 (Maker 0,020 %, Taker 0,055 %, plus Stop-Slippage) ergibt das bei
# 1,5:1 Chance-Risiko-Verhaeltnis:
#
#     Stop 0,15 %  ->  59,8 % Trefferquote noetig
#     Stop 0,30 %  ->  50,9 %
#     Stop 0,50 %  ->  46,8 %
#     Stop 1,00 %  ->  43,5 %
#     ohne Gebuehren:  40,0 %
#
# Bei 0,15 % Stop muss also jeder zweite Trade sitzen, nur um die Boerse zu
# bezahlen. Das ist der Grund, warum die Stops hier zwischen 0,4 und 0,8 %
# liegen und nicht enger: nicht Vorsicht, sondern Arithmetik.
#
# DER HEBEL IST HIER KEIN PARAMETER
# ---------------------------------
# Er ergibt sich, und zwar zwangslaeufig:
#
#     Hebel = Risiko je Trade / Stop-Distanz
#
# Bei 0,75 % Risiko und 0,5 % Stop sind das 1,5x, bei 0,3 % Stop 2,5x. Enger
# stellen heisst hoeher hebeln - dieselbe Entscheidung, zweimal ausgedrueckt.
# Was der Hebel **nicht** tut: einen Vorteil erzeugen. Er vergroessert, was da
# ist. Bei negativem Erwartungswert beschleunigt er nur den Weg zur Null.
#
# HANDELSZEITEN
# -------------
# Zwei Kandidaten handeln nur zwischen 13 und 21 Uhr UTC - die Stunden, in
# denen London und New York offen sind. Das ist eine Technik aus der Praxis,
# die wir bisher nie benutzt haben: In duennen Stunden sind die Spreads
# breiter und Ausbrueche halten seltener.


def bollinger_fade_scalp() -> Genome:
    """Ruecksetzer im Aufwaertstrend kaufen.

    Hypothese: In einem intakten Trend sind kurze Ausschlaege nach unten
    Uebertreibungen und keine Trendwende. Wer das untere Bollinger-Band
    beruehrt, waehrend der Kurs ueber seinem laengeren Durchschnitt liegt,
    kauft in eine Erholung hinein.

    Die klassischste Scalp-Bauform ueberhaupt - und deshalb auch die am
    haeufigsten durchprobierte. Sie steht hier trotzdem, weil sie der Massstab
    ist: Wenn nicht einmal sie in die Naehe der Kostenschwelle kommt, sagt das
    etwas ueber die Zeitebene und nicht ueber die Variante.
    """
    return Genome(
        name="Bollinger-Ruecksetzer im Trend",
        rationale=(
            "Long, wenn der Kurs das untere Bollinger-Band unterschreitet, "
            "waehrend er ueber dem EMA(200) liegt. Hypothese: Kurze "
            "Ausschlaege gegen einen intakten Trend sind Uebertreibungen. "
            "Ziel 1,5:1, Stop knapp unter dem Band."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_BELOW,
                      right=_ind("bollinger_lower", period=20, deviations=2)),
        ],
        filters=[
            Condition(left=_price("close"), op=Operator.GT,
                      right=_ind("ema", period=200)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def session_breakout_scalp() -> Genome:
    """Ausbruch, aber nur wenn jemand da ist.

    Hypothese: Ein Ausbruch traegt nur, wenn Volumen dahintersteht und der
    Markt besetzt ist. Beides wird hier verlangt - ein Volumen deutlich ueber
    dem Schnitt und die Stunden, in denen London und New York handeln.

    Das ist der erste Kandidat ueberhaupt, der Handelszeiten benutzt. Wenn er
    besser abschneidet als der Ausbruch aus Generation 2, der rund um die Uhr
    handelte, liegt darin eine Erkenntnis, die uebertragbar ist.
    """
    return Genome(
        name="Sitzungs-Ausbruch mit Volumen",
        rationale=(
            "Long beim Ausbruch ueber das 20-Perioden-Hoch, wenn das Volumen "
            "mehr als eine Standardabweichung ueber dem Schnitt liegt und es "
            "zwischen 13 und 21 Uhr UTC ist. Hypothese: Ausbrueche in duennen "
            "Stunden halten seltener; Volumen unterscheidet echte von "
            "zufaelligen."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("donchian_upper", period=20)),
        ],
        filters=[
            Condition(left=_ind("volume_zscore", period=50), op=Operator.GT,
                      right=_const(1.0)),
            Condition(left=_ind("hour_of_day"), op=Operator.GTE,
                      right=_const(13.0)),
            Condition(left=_ind("hour_of_day"), op=Operator.LTE,
                      right=_const(21.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.0, portion=0.5), TargetSpec(rr=2.0, portion=0.5)],
        cooldown_bars=4,
        max_hold_bars=24,
    )


def squeeze_scalp() -> Genome:
    """Nach der Ruhe der Ausbruch.

    Hypothese: Volatilitaet kommt in Schueben. Eine ungewoehnlich enge
    Bollinger-Breite heisst, dass sich Bewegung aufgestaut hat - was danach
    kommt, kommt schnell und laeuft weit genug fuer ein Ziel bei 2:1.

    Anders als die drei Ausbruchsvarianten der ersten Generationen setzt diese
    nicht an einem Preisniveau an, sondern an der **Enge davor**. Damit ist es
    die einzige Bauform hier, deren Signal nicht aus einem Kursvergleich
    stammt.
    """
    return Genome(
        name="Ausbruch nach Volatilitaetsenge",
        rationale=(
            "Long, wenn die Bollinger-Breite unter 1,2 % faellt und der Kurs "
            "danach das 20-Perioden-Hoch nimmt. Hypothese: Volatilitaet kommt "
            "in Schueben, und die Enge davor ist messbar. Ziel 2:1."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("donchian_upper", period=20)),
        ],
        filters=[
            Condition(left=_ind("bollinger_width", period=20, deviations=2),
                      op=Operator.LT, right=_const(1.2)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
        targets=[TargetSpec(rr=2.0, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=48,
    )


def rsi_pullback_scalp() -> Genome:
    """Der Klassiker vom Bildschirm: ueberverkauft im Aufwaertstrend.

    Hypothese: Ein RSI unter 30, waehrend der laengerfristige Trend nach oben
    zeigt, markiert einen Ruecksetzer und keine Wende.

    Bewusst als vierte Variante derselben Grundidee wie der Bollinger-Fade,
    nur mit einem anderen Messinstrument. Fallen beide gleich aus, liegt es an
    der Idee; faellt nur eine, lag es am Instrument. Diese Unterscheidung war
    in Generation 1 nicht moeglich und hat dort Rueckschluesse verhindert.
    """
    return Genome(
        name="RSI-Ruecksetzer im Trend",
        rationale=(
            "Long, wenn der RSI(14) unter 30 faellt, waehrend der Kurs ueber "
            "dem EMA(200) liegt. Raus bei RSI ueber 60 oder am Ziel. "
            "Hypothese: Ueberverkauft im Aufwaertstrend ist ein Ruecksetzer, "
            "keine Wende. Zwillingsversuch zum Bollinger-Ruecksetzer."
        ),
        entry_long=[
            Condition(left=_ind("rsi", period=14), op=Operator.CROSS_BELOW,
                      right=_const(30.0)),
        ],
        filters=[
            Condition(left=_price("close"), op=Operator.GT,
                      right=_ind("ema", period=200)),
        ],
        exit_long=[
            Condition(left=_ind("rsi", period=14), op=Operator.GT,
                      right=_const(60.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


#: Sechste Generation: schnelles Handeln auf 15-Minuten-Kerzen, mit Hebel.
GENERATION_6 = [
    bollinger_fade_scalp,
    session_breakout_scalp,
    squeeze_scalp,
    rsi_pullback_scalp,
]


# ===========================================================================
#  Siebte Generation - der Katalog der bekannten Scalp-Setups
# ===========================================================================
#
# Was im Netz unter vielen Namen kursiert, laesst sich fast immer auf wenige
# messbare Groessen zurueckfuehren. "Order Block", "Liquidity Sweep",
# "Displacement", "VWAP Bounce", "Squeeze" - jedes davon ist eine Erzaehlung
# ueber eine Zahl. Die Erzaehlung ist nicht pruefbar, die Zahl schon.
#
# Deshalb steht hier keine Nacherzaehlung, sondern die jeweils schlichteste
# Bedingung, die das beschriebene Verhalten trifft. Wer ein Setup mit sieben
# Zusatzbedingungen nachbaut, bekommt im Backtest fast immer ein schoenes Bild
# und kann hinterher nicht sagen, welcher Teil gewirkt hat.
#
# Alle Kandidaten hier:
#
#   * laufen auf 15-Minuten-Kerzen
#   * halten Stunden, nicht Tage (max_hold_bars begrenzt das hart)
#   * dimensionieren nach Risiko - der Hebel ergibt sich daraus
#   * haben Stops zwischen etwa 0,4 und 0,9 %
#
# Die Stopweite ist kein Geschmack, sondern folgt aus der Kostenrechnung: Bei
# 0,15 % Stop braucht es 59,8 % Trefferquote, nur um die Boerse zu bezahlen;
# bei 0,5 % sind es 46,8 %. Enger geht nicht, ohne dass die Gebuehren die
# Strategie auffressen. Nachzurechnen mit ``python -m cli kosten``.


def vwap_reversion() -> Genome:
    """Rueckkehr zum volumengewichteten Durchschnitt.

    Hypothese: Der VWAP ist die Linie, an der grosse Haeuser ihre Ausfuehrung
    messen. Ein Kurs deutlich darunter bedeutet, dass wer heute gekauft hat im
    Minus liegt - und dass Nachfrage entsteht, die ihn zurueckholt.

    Von allen Kandidaten hier der mit der sachlichsten Begruendung: Der VWAP
    wird tatsaechlich als Massstab benutzt, nicht nur betrachtet.
    """
    return Genome(
        name="VWAP-Rueckkehr",
        rationale=(
            "Long, wenn der Kurs mehr als 0,8 % unter dem Tages-VWAP liegt "
            "und die Lage in der Spanne unter 20 faellt. Hypothese: Der VWAP "
            "ist der Massstab grosser Ausfuehrungen; deutliche Abweichungen "
            "werden zurueckgeholt. Ziel 1,5:1."
        ),
        entry_long=[
            Condition(left=_ind("vwap_distance_pct", period=96), op=Operator.LT,
                      right=_const(-0.8)),
            Condition(left=_ind("stochastic", period=14), op=Operator.LT,
                      right=_const(20.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def liquidity_sweep() -> Genome:
    """Unter das Tief und sofort zurueck.

    Hypothese: Unter einem sichtbaren Tief liegen Stop-Orders. Wird es kurz
    durchstochen und der Kurs schliesst wieder darueber, wurden diese Stops
    abgeraeumt - und die Gegenseite hat gekauft. Was bleibt, ist ein langer
    Docht nach unten.

    Das ist die messbare Fassung dessen, was als Liquidity Sweep oder Stop
    Hunt beschrieben wird. Ob die Erzaehlung ueber die Stops stimmt, laesst
    sich nicht pruefen; der Docht schon, und nur er steht in der Regel.
    """
    return Genome(
        name="Liquiditaets-Abgriff",
        rationale=(
            "Long, wenn das Tief unter das 20-Perioden-Tief faellt, der "
            "Schlusskurs aber wieder darueber liegt und der untere Docht "
            "groesser als 0,25 % ist. Hypothese: Abgeraeumte Stops unter einem "
            "sichtbaren Tief, danach Rueckkauf. Ziel 2:1."
        ),
        entry_long=[
            Condition(left=_price("low"), op=Operator.LT,
                      right=_ind("swing_low", period=20)),
            Condition(left=_price("close"), op=Operator.GT,
                      right=_ind("swing_low", period=20)),
            Condition(left=_ind("wick_below_pct"), op=Operator.GT,
                      right=_const(0.25)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
        targets=[TargetSpec(rr=2.0, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=24,
    )


def liquidity_sweep_short() -> Genome:
    """Dasselbe nach oben - und deshalb der eigentlich interessante Fall.

    Wenn der Abgriff nach unten funktioniert und der nach oben nicht, dann
    misst die Regel keinen Mechanismus, sondern nur den Aufwaertstrend von
    Bitcoin. Diese Unterscheidung ist der Grund, warum beide Richtungen als
    getrennte Kandidaten laufen und nicht als ein Genom mit zwei Seiten.
    """
    return Genome(
        name="Liquiditaets-Abgriff (Gegenprobe short)",
        rationale=(
            "Spiegelbild des Liquiditaets-Abgriffs: Short, wenn das Hoch ueber "
            "das 20-Perioden-Hoch steigt, der Schlusskurs aber darunter bleibt "
            "und der obere Docht groesser als 0,25 % ist. Gegenprobe - "
            "funktioniert nur die Long-Seite, misst die Regel den Trend und "
            "nicht den Mechanismus."
        ),
        entry_short=[
            Condition(left=_price("high"), op=Operator.GT,
                      right=_ind("swing_high", period=20)),
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("swing_high", period=20)),
            Condition(left=_ind("wick_above_pct"), op=Operator.GT,
                      right=_const(0.25)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
        targets=[TargetSpec(rr=2.0, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=24,
    )


def keltner_squeeze() -> Genome:
    """Enge, dann Ausbruch - die messbare Fassung.

    Hypothese: Liegt das Bollinger-Band innerhalb des Keltner-Bands, hat sich
    Bewegung aufgestaut. Was danach kommt, laeuft weit genug fuer 2:1.

    Der Unterschied zum Ausbruch aus Generation 2 ist der Zeitpunkt: Dort war
    das Signal ein neues Hoch, hier ist es die Ruhe davor.
    """
    return Genome(
        name="Keltner-Enge mit Ausbruch",
        rationale=(
            "Long beim Ausbruch ueber das 20-Perioden-Hoch, wenn das obere "
            "Bollinger-Band unter dem oberen Keltner-Band liegt - die "
            "klassische Enge. Hypothese: Volatilitaet kommt in Schueben, und "
            "die Enge davor ist messbar."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("swing_high", period=20)),
        ],
        filters=[
            Condition(left=_ind("bollinger_upper", period=20, deviations=2),
                      op=Operator.LT,
                      right=_ind("keltner_upper", period=20, multiple=2)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
        targets=[TargetSpec(rr=1.0, portion=0.5), TargetSpec(rr=2.5, portion=0.5)],
        cooldown_bars=6,
        max_hold_bars=32,
    )


def displacement_candle() -> Genome:
    """Eine grosse Kerze mit Volumen - und dann hinterher.

    Hypothese: Eine ungewoehnlich grosse Kerze mit ungewoehnlich hohem Volumen
    zeigt an, dass jemand mit Groesse gekauft hat. Wer solche Orders ausfuehrt,
    ist selten in einer Kerze fertig.

    Das ist die schlichte Fassung von "Displacement", "Momentum Candle" oder
    "Engulfing" - drei Namen fuer dieselbe Beobachtung.
    """
    return Genome(
        name="Grosse Kerze mit Volumen",
        rationale=(
            "Long, wenn der Kerzenkoerper mehr als das 1,5-fache der ATR "
            "betraegt und das Volumen mehr als zwei Standardabweichungen ueber "
            "dem Schnitt liegt. Hypothese: Wer mit Groesse kauft, ist nach einer Kerze "
            "nicht fertig. Ziel 1,5:1."
        ),
        entry_long=[
            Condition(left=_ind("body_atr_ratio", period=14), op=Operator.GT,
                      right=_const(1.5)),
            Condition(left=_ind("volume_zscore", period=50), op=Operator.GT,
                      right=_const(1.5)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=4,
        max_hold_bars=16,
    )


def stochastic_trend_pullback() -> Genome:
    """Ueberverkauft, aber nur im Aufwaertstrend.

    Hypothese: Die Lage in der Spanne sagt mehr ueber einen Ruecksetzer als
    der RSI, weil sie Hoch und Tief benutzt statt nur Schlusskurse.

    Bewusst als Zwilling zum RSI-Kandidaten der sechsten Generation gebaut.
    Fallen beide gleich aus, liegt es an der Idee "Ruecksetzer im Trend" und
    nicht am Messinstrument.
    """
    return Genome(
        name="Stochastik-Ruecksetzer im Trend",
        rationale=(
            "Long, wenn die Lage in der Spanne unter 15 faellt, waehrend der "
            "Kurs ueber dem EMA(200) liegt. Zwillingsversuch zum "
            "RSI-Ruecksetzer - anderes Messinstrument, dieselbe Idee."
        ),
        entry_long=[
            Condition(left=_ind("stochastic", period=14), op=Operator.CROSS_BELOW,
                      right=_const(15.0)),
        ],
        filters=[
            Condition(left=_price("close"), op=Operator.GT,
                      right=_ind("ema", period=200)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def macd_momentum() -> Genome:
    """MACD-Kreuzung oberhalb der Nulllinie.

    Hypothese: Eine Kreuzung sagt wenig; eine Kreuzung, waehrend der MACD
    ueber null liegt, sagt "Aufwaertsbewegung beschleunigt erneut".

    Steht hier vor allem als Vertreter der klassischen Indikator-Schule -
    wenn diese ganze Familie nichts traegt, ist auch das ein Ergebnis.
    """
    return Genome(
        name="MACD-Beschleunigung",
        rationale=(
            "Long, wenn der MACD(12,26) seine Signallinie von unten kreuzt "
            "und dabei ueber null liegt. Hypothese: Erneute Beschleunigung "
            "innerhalb einer bestehenden Aufwaertsbewegung."
        ),
        entry_long=[
            Condition(left=_ind("macd", fast=12, slow=26), op=Operator.CROSS_ABOVE,
                      right=_ind("macd_signal", fast=12, slow=26, signal=9)),
        ],
        filters=[
            Condition(left=_ind("macd", fast=12, slow=26), op=Operator.GT,
                      right=_const(0.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def trend_pullback_to_ema() -> Genome:
    """Ruecksetzer an den gleitenden Durchschnitt im Trend.

    Hypothese: In einem Trend ist der EMA(50) eine Zone, an der Nachfrage
    wartet. Der Kurs laeuft ihn an, statt ihn zu durchbrechen.

    Die vielleicht meistgehandelte Bauform ueberhaupt - und genau deshalb
    diejenige, bei der ein Vorteil am ehesten schon wegkonkurriert ist.
    """
    return Genome(
        name="Ruecksetzer an den EMA(50)",
        rationale=(
            "Long, wenn der Abstand zum EMA(50) unter -0,3 % faellt, waehrend "
            "der Kurs ueber dem EMA(200) liegt und der ADX ueber 20 steht. "
            "Hypothese: Im Trend wartet am EMA(50) Nachfrage."
        ),
        entry_long=[
            Condition(left=_ind("distance_to_ema_pct", period=50),
                      op=Operator.CROSS_BELOW, right=_const(-0.3)),
        ],
        filters=[
            Condition(left=_price("close"), op=Operator.GT,
                      right=_ind("ema", period=200)),
            Condition(left=_ind("adx", period=14), op=Operator.GT,
                      right=_const(20.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def vwap_trend_continuation() -> Genome:
    """Ueber dem VWAP bleiben und Ruecksetzer dorthin kaufen.

    Hypothese: Solange der Kurs ueber dem VWAP notiert, sind die Kaeufer des
    Tages im Gewinn. Ein Ruecksetzer an die Linie trifft dann auf
    Nachkaufbereitschaft statt auf Ausstiege.

    Die Gegenrichtung zur VWAP-Rueckkehr: Dort ist die Abweichung das Signal,
    hier die Beruehrung. Beide koennen nicht zugleich richtig sein, und das
    macht sie zu einem sauberen Paar.
    """
    return Genome(
        name="VWAP-Fortsetzung",
        rationale=(
            "Long, wenn der Kurs von oben an den VWAP zurueckkommt (Abstand "
            "unter 0,1 %), der VWAP aber ueber dem Kurs von vor 96 Perioden "
            "liegt. Gegenrichtung zur VWAP-Rueckkehr - beide koennen nicht "
            "zugleich stimmen."
        ),
        entry_long=[
            Condition(left=_ind("vwap_distance_pct", period=96),
                      op=Operator.CROSS_BELOW, right=_const(0.1)),
        ],
        filters=[
            Condition(left=_ind("roc", period=96), op=Operator.GT, right=_const(0.0)),
            Condition(left=_price("close"), op=Operator.GT,
                      right=_ind("ema", period=200)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def range_fade() -> Genome:
    """Im Seitwaertsmarkt die Raender handeln.

    Hypothese: Wenn kein Trend da ist - erkennbar an einem niedrigen ADX -,
    laufen Ausbrueche ins Leere und die Raender halten. Genau umgekehrt zu
    allen Ausbruchskandidaten.

    Steht hier als Gegenstueck: Sollten die Ausbruchsvarianten scheitern und
    diese bestehen, liegt darin eine Aussage ueber den Markt und nicht nur
    ueber eine Regel.
    """
    return Genome(
        name="Randhandel im Seitwaertsmarkt",
        rationale=(
            "Long am unteren Bollinger-Band, wenn der ADX unter 20 liegt - "
            "also kein Trend da ist. Gegenstueck zu den Ausbruchskandidaten: "
            "Beide zusammen sagen mehr aus als jeder fuer sich."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_BELOW,
                      right=_ind("bollinger_lower", period=20, deviations=2)),
        ],
        filters=[
            Condition(left=_ind("adx", period=14), op=Operator.LT,
                      right=_const(20.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.2, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=24,
    )


#: Siebte Generation: der Katalog der bekannten Scalp-Setups.
GENERATION_7 = [
    vwap_reversion,
    vwap_trend_continuation,
    liquidity_sweep,
    liquidity_sweep_short,
    keltner_squeeze,
    displacement_candle,
    stochastic_trend_pullback,
    macd_momentum,
    trend_pullback_to_ema,
    range_fade,
]


# ===========================================================================
#  Achte Generation - das Abfolge-Modell, und die Short-Seite
# ===========================================================================
#
# Die siebte Generation hatte den Abgriff, aber nur als Momentaufnahme. Das
# eigentliche Modell hinter ICT und den daraus abgeleiteten Ansaetzen ist eine
# **Abfolge ueber mehrere Balken**:
#
#     1. Abgriff        - Kurs sticht unter ein Tief, schliesst wieder darueber
#     2. Strukturbruch  - danach ein Schlusskurs ueber dem letzten Hoch
#     3. Rueckkehr      - Einstieg dort, wo der Impuls eine Luecke hinterliess
#
# Erst alle drei zusammen sind das Modell. Nur der Abgriff ist ein Docht, nur
# der Bruch ist ein Ausbruch - beides haben wir schon geprueft und beides hat
# nichts getragen. Ob die Reihenfolge etwas hinzufuegt, ist die Frage dieser
# Generation, und sie ist zum ersten Mal ueberhaupt stellbar.
#
# ZERLEGT STATT AM STUECK
# -----------------------
# Deshalb laeuft das Modell hier in drei Fassungen: vollstaendig, ohne die
# Luecke, und ohne den Strukturbruch. Wenn die vollstaendige nicht besser
# abschneidet als ihre Teile, dann traegt die Reihenfolge nichts bei - und das
# ist eine Aussage, die man sonst nie bekommt.
#
# DIE SHORT-SEITE
# ---------------
# Von 24 bisher geprueften Kandidaten waren 23 long. Das ist ein blinder Fleck:
# Ueber 2020 bis 2026 ist BTC gestiegen, und eine Long-Regel kann allein davon
# leben, ohne irgendetwas zu erkennen. Erst die Gegenprobe nach unten zeigt, ob
# eine Regel einen Mechanismus trifft oder den Trend.


def sequenz_modell_long() -> Genome:
    """Abgriff, Strukturbruch, Rueckkehr in die Luecke - das ganze Modell.

    Hypothese: Erst die Reihenfolge macht das Signal. Ein Abgriff allein ist
    ein Docht; ein Bruch allein ein Ausbruch. Zusammen beschreiben sie, dass
    Verkaeufer ausgestoppt wurden **und** die Gegenseite danach die Kontrolle
    uebernommen hat - und die Luecke markiert den Preis, zu dem sie es tat.

    Der Stop liegt weit genug, um unter dem Abgriffsdocht zu sitzen; genau
    dort ist die Idee widerlegt, wenn er faellt.
    """
    return Genome(
        name="Abfolge-Modell (Abgriff, Bruch, Rueckkehr)",
        rationale=(
            "Long, wenn innerhalb der letzten 12 Balken ein Abgriff unter das "
            "20-Perioden-Tief stattfand, danach innerhalb von 6 Balken ein "
            "Schlusskurs ueber dem 10-Perioden-Hoch lag, und der Kurs jetzt in "
            "die dabei entstandene Preisluecke zurueckfaellt. Hypothese: Erst "
            "die Reihenfolge macht das Signal - Abgriff und Bruch einzeln haben "
            "wir schon widerlegt."
        ),
        entry_long=[
            Condition(left=_price("low"), op=Operator.LTE,
                      right=_ind("fvg_up_level", lookback=20)),
        ],
        filters=[
            Condition(left=_ind("bars_since_sweep_low", period=20), op=Operator.LTE,
                      right=_const(12.0)),
            Condition(left=_ind("bars_since_bos_up", period=10), op=Operator.LTE,
                      right=_const(6.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.0, portion=0.5), TargetSpec(rr=3.0, portion=0.5)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def sequenz_ohne_luecke() -> Genome:
    """Dasselbe, aber ohne die Rueckkehr in die Luecke.

    Der erste von zwei Zerlegungsversuchen: Wenn diese Fassung genauso gut
    abschneidet, traegt die Luecke nichts bei - und der aufwendigste Teil des
    Modells waere Zierrat.
    """
    return Genome(
        name="Abfolge ohne Luecke",
        rationale=(
            "Long nach Abgriff und Strukturbruch, aber sofort statt beim "
            "Rueckfall in die Preisluecke. Zerlegungsversuch: Traegt die "
            "Luecke etwas bei oder nicht?"
        ),
        entry_long=[
            Condition(left=_ind("bars_since_bos_up", period=10), op=Operator.LTE,
                      right=_const(2.0)),
        ],
        filters=[
            Condition(left=_ind("bars_since_sweep_low", period=20), op=Operator.LTE,
                      right=_const(12.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.0, portion=0.5), TargetSpec(rr=3.0, portion=0.5)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def sequenz_ohne_bruch() -> Genome:
    """Dasselbe, aber ohne den Strukturbruch.

    Der zweite Zerlegungsversuch. Zusammen mit dem ersten laesst sich sagen,
    welcher Bestandteil - falls einer - ueberhaupt etwas beitraegt.
    """
    return Genome(
        name="Abfolge ohne Strukturbruch",
        rationale=(
            "Long beim Rueckfall in eine Preisluecke nach einem Abgriff, ohne "
            "auf einen Strukturbruch zu warten. Zweiter Zerlegungsversuch."
        ),
        entry_long=[
            Condition(left=_price("low"), op=Operator.LTE,
                      right=_ind("fvg_up_level", lookback=20)),
        ],
        filters=[
            Condition(left=_ind("bars_since_sweep_low", period=20), op=Operator.LTE,
                      right=_const(12.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.0, portion=0.5), TargetSpec(rr=3.0, portion=0.5)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def sequenz_modell_short() -> Genome:
    """Das Abfolge-Modell nach unten - die eigentliche Bewaehrungsprobe.

    Ueber den geprueften Zeitraum ist BTC gestiegen. Eine Long-Regel kann
    allein davon leben; eine Short-Regel nicht. Schneidet das Modell nach unten
    aehnlich ab wie nach oben, beschreibt es tatsaechlich einen Mechanismus.
    Faellt nur die Short-Seite durch, hat die Long-Seite den Trend gemessen.
    """
    return Genome(
        name="Abfolge-Modell short",
        rationale=(
            "Spiegelbild: Short nach einem Abgriff ueber das 20-Perioden-Hoch "
            "und einem Strukturbruch nach unten. Bewaehrungsprobe - eine "
            "Long-Regel kann vom Aufwaertstrend leben, eine Short-Regel nicht."
        ),
        entry_short=[
            Condition(left=_ind("bars_since_bos_down", period=10), op=Operator.LTE,
                      right=_const(2.0)),
        ],
        filters=[
            Condition(left=_ind("bars_since_sweep_high", period=20), op=Operator.LTE,
                      right=_const(12.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.0, portion=0.5), TargetSpec(rr=3.0, portion=0.5)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def sequenz_in_der_sitzung() -> Genome:
    """Das Modell, aber nur zur New Yorker Eroeffnung.

    Hypothese: Das Modell beschreibt das Verhalten grosser Ausfuehrungen. Die
    finden zu bestimmten Zeiten statt - und in duennen Stunden ist ein Docht
    unter einem Tief eher Zufall als Absicht.

    Falls die Sitzungsvariante deutlich besser abschneidet, liegt darin eine
    uebertragbare Erkenntnis: Dann ist die Tageszeit ein Filter fuer alle
    Kandidaten und nicht nur fuer diesen.
    """
    return Genome(
        name="Abfolge zur New Yorker Eroeffnung",
        rationale=(
            "Wie das Abfolge-Modell, aber nur zwischen 13 und 17 Uhr UTC. "
            "Hypothese: Grosse Ausfuehrungen haben Zeiten; in duennen Stunden "
            "ist ein Docht eher Zufall."
        ),
        entry_long=[
            Condition(left=_ind("bars_since_bos_up", period=10), op=Operator.LTE,
                      right=_const(2.0)),
        ],
        filters=[
            Condition(left=_ind("bars_since_sweep_low", period=20), op=Operator.LTE,
                      right=_const(12.0)),
            Condition(left=_ind("hour_of_day"), op=Operator.GTE, right=_const(13.0)),
            Condition(left=_ind("hour_of_day"), op=Operator.LTE, right=_const(17.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.0, portion=0.5), TargetSpec(rr=3.0, portion=0.5)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def luecke_als_ziel() -> Genome:
    """Eine grosse Preisluecke wird geschlossen.

    Hypothese: Ein uebersprungener Preisbereich zieht den Kurs zurueck - dort
    hat kein Handel stattgefunden, und offene Nachfrage bleibt liegen.

    Das ist die Gegenrichtung zum Abfolge-Modell: Dort ist die Luecke ein
    Einstiegsniveau in Trendrichtung, hier ein Ziel gegen die Bewegung. Beide
    koennen nicht zugleich stimmen.
    """
    return Genome(
        name="Luecke wird geschlossen",
        rationale=(
            "Short, wenn eine Aufwaerts-Luecke groesser als 0,3 % entsteht - "
            "auf die Erwartung, dass der uebersprungene Bereich nachgeholt "
            "wird. Gegenrichtung zum Abfolge-Modell; beide koennen nicht "
            "zugleich stimmen."
        ),
        entry_short=[
            Condition(left=_ind("fvg_up_pct"), op=Operator.GT, right=_const(0.3)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.2, portion=1.0)],
        cooldown_bars=6,
        max_hold_bars=24,
    )


def bollinger_fade_short() -> Genome:
    """Der Bollinger-Ruecksetzer, gespiegelt.

    Gegenprobe zu einem Kandidaten der sechsten Generation. Von 24 bisher
    geprueften Regeln waren 23 long - ohne solche Spiegelungen laesst sich
    nicht trennen, was Mechanismus und was Aufwaertstrend war.
    """
    return Genome(
        name="Bollinger-Ruecksetzer short",
        rationale=(
            "Short am oberen Bollinger-Band, waehrend der Kurs unter dem "
            "EMA(200) liegt. Spiegelung des Long-Kandidaten - trennt "
            "Mechanismus von Trend."
        ),
        entry_short=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("bollinger_upper", period=20, deviations=2)),
        ],
        filters=[
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("ema", period=200)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=1.5),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def vwap_reversion_short() -> Genome:
    """Die VWAP-Rueckkehr, gespiegelt."""
    return Genome(
        name="VWAP-Rueckkehr short",
        rationale=(
            "Short, wenn der Kurs mehr als 0,8 % ueber dem Tages-VWAP liegt "
            "und die Lage in der Spanne ueber 80 steigt. Spiegelung des "
            "Long-Kandidaten."
        ),
        entry_short=[
            Condition(left=_ind("vwap_distance_pct", period=96), op=Operator.GT,
                      right=_const(0.8)),
            Condition(left=_ind("stochastic", period=14), op=Operator.GT,
                      right=_const(80.0)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=8,
        max_hold_bars=32,
    )


def displacement_short() -> Genome:
    """Die grosse Kerze mit Volumen, nach unten."""
    return Genome(
        name="Grosse Kerze mit Volumen short",
        rationale=(
            "Short, wenn der Kerzenkoerper mehr als das 1,5-fache der ATR "
            "nach unten betraegt und das Volumen zwei Standardabweichungen "
            "ueber dem Schnitt liegt. Spiegelung - Verkaufsdruck mit Groesse."
        ),
        entry_short=[
            Condition(left=_ind("body_atr_ratio", period=14), op=Operator.LT,
                      right=_const(-1.5)),
            Condition(left=_ind("volume_zscore", period=50), op=Operator.GT,
                      right=_const(1.5)),
        ],
        stop=StopSpec(kind="atr", atr_period=14, multiple=2.0),
        targets=[TargetSpec(rr=1.5, portion=1.0)],
        cooldown_bars=4,
        max_hold_bars=16,
    )


#: Achte Generation: das Abfolge-Modell, zerlegt, plus die Short-Seite.
GENERATION_8 = [
    sequenz_modell_long,
    sequenz_ohne_luecke,
    sequenz_ohne_bruch,
    sequenz_modell_short,
    sequenz_in_der_sitzung,
    luecke_als_ziel,
    bollinger_fade_short,
    vwap_reversion_short,
    displacement_short,
]


# ===========================================================================
#  Neunte Generation - die Trendfolge-Familie, breit aufgestellt
# ===========================================================================
#
# Der erste Kandidat mit positivem Erwartungswert war eine Trend-Beteiligung
# auf Tageskerzen: +59,1 % Rendite, 10,2 % Rueckgang, Sharpe 1,01, Gebuehren
# 0,8 %. Gescheitert ist er an zwei Gates - und drei weitere konnten gar nicht
# erst laufen.
#
# Alle drei Probleme haben dieselbe Wurzel: **17 Trades in fuenf Jahren.**
#
#   Bestaendigkeit 44 %   neun gehandelte Fenster sind eine duenne Stichprobe
#   Messlatte 10,6 % p.a. zu selten investiert, um mehr herauszuholen
#   Monte-Carlo, Regime-Aufteilung, Deflated Sharpe: uebersprungen
#
# Diese Generation sucht deshalb nicht nach einer neuen Idee, sondern nach
# **mehr Beobachtungen derselben Idee**. Vier Wege dorthin, jeder fuer sich
# pruefbar:
#
#   1. schnellere Trendmarke      50 und 100 statt 200 Tage
#   2. beide Richtungen           short unter der Marke statt nur Kasse
#   3. feinere Zeitebene          4-Stunden-Kerzen statt Tageskerzen
#   4. andere Trenddefinition     Ausbruch statt Durchschnitt
#
# Der Kandidat mit 200 Tagen laeuft unveraendert mit. Ohne ihn liesse sich
# nicht sagen, ob eine Aenderung etwas gebracht hat oder ob nur der Zeitraum
# guenstiger war.


def _trend_beteiligung(name: str, periode: int, rationale: str) -> Genome:
    """Bauplan der Familie: long ueber der Marke, raus darunter.

    Als Funktion, weil sich die Kandidaten **nur** in der Periode
    unterscheiden sollen. Von Hand geschrieben schliche sich sonst noch ein
    zweiter Unterschied ein, und dann waere der Vergleich wertlos.
    """
    return Genome(
        name=name,
        rationale=rationale,
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("sma", period=periode)),
        ],
        exit_long=[
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("sma", period=periode)),
        ],
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        cooldown_bars=0,
        max_hold_bars=0,
    )


def trend_50() -> Genome:
    return _trend_beteiligung(
        "Trend-Beteiligung 50 Tage", 50,
        "Long ueber dem 50-Tage-Schnitt, raus darunter. Schnellere Marke als "
        "die 200 - mehr Trades, aber auch mehr Fehlausbrueche. Die Frage ist, "
        "was ueberwiegt.",
    )


def trend_100() -> Genome:
    return _trend_beteiligung(
        "Trend-Beteiligung 100 Tage", 100,
        "Long ueber dem 100-Tage-Schnitt. Mittelweg zwischen 50 und 200 - "
        "liegt das Ergebnis dazwischen, ist die Periode eine stetige "
        "Stellschraube und kein Zufallstreffer.",
    )


def trend_200() -> Genome:
    return _trend_beteiligung(
        "Trend-Beteiligung 200 Tage", 200,
        "Long ueber dem 200-Tage-Schnitt. Der bisherige Spitzenkandidat, "
        "unveraendert als Vergleichsmassstab.",
    )


def trend_beide_richtungen() -> Genome:
    """Unter der Marke short statt in Kasse.

    Hypothese: Die Kasse-Variante stand 2022 ein Jahr lang still. Wer dort
    short gewesen waere, haette den Baerenmarkt mitgenommen statt ihn nur
    auszusitzen - und haette doppelt so viele Beobachtungen.

    Der Preis: Ein Short in einem Markt, der langfristig steigt, ist teuer,
    wenn die Marke zu oft falsch dreht. Genau das entscheidet sich hier.
    """
    return Genome(
        name="Trend beide Richtungen",
        rationale=(
            "Long ueber dem 200-Tage-Schnitt, short darunter. Hypothese: Die "
            "Kasse-Variante stand 2022 ein Jahr still; short haette denselben "
            "Trend in die Gegenrichtung genutzt. Verdoppelt zugleich die Zahl "
            "der Beobachtungen."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("sma", period=200)),
        ],
        entry_short=[
            Condition(left=_price("close"), op=Operator.CROSS_BELOW,
                      right=_ind("sma", period=200)),
        ],
        exit_long=[
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("sma", period=200)),
        ],
        exit_short=[
            Condition(left=_price("close"), op=Operator.GT,
                      right=_ind("sma", period=200)),
        ],
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        cooldown_bars=0,
        max_hold_bars=0,
    )


def donchian_turtle() -> Genome:
    """Ausbruch statt Durchschnitt - das aelteste dokumentierte Trendsystem.

    Hypothese: Ein neues 55-Tage-Hoch ist ein Trendbeginn; ausgestiegen wird
    beim 20-Tage-Tief. Das ist im Kern die Regel, mit der in den achtziger
    Jahren eine Gruppe angelernter Haendler bekannt wurde - und die seither
    unzaehlige Male nachgerechnet wurde.

    Der Unterschied zur Durchschnittsmarke ist nicht kosmetisch: Ein
    Durchschnitt reagiert auf jeden Schlusskurs, ein Ausbruch nur auf
    Extremwerte. In Seitwaertsphasen ergibt das deutlich weniger Fehlsignale.
    """
    return Genome(
        name="Donchian-Ausbruch 55/20",
        rationale=(
            "Long beim Ausbruch ueber das 55-Tage-Hoch, raus beim 20-Tage-Tief. "
            "Die aelteste dokumentierte Trendfolgeregel. Hypothese: Extremwerte "
            "geben weniger Fehlsignale als ein Durchschnitt, der auf jeden "
            "Schlusskurs reagiert."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("swing_high", period=55)),
        ],
        exit_long=[
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("swing_low", period=20)),
        ],
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        cooldown_bars=0,
        max_hold_bars=0,
    )


def momentum_beteiligung() -> Genome:
    """Beteiligung nach der Veraenderung ueber 90 Tage.

    Dritte Art, denselben Trend zu messen: nicht an einer Linie und nicht an
    einem Extremwert, sondern an der reinen Veraenderung. Fallen alle drei
    aehnlich aus, liegt es an der Idee und nicht am Messinstrument - und das
    ist ein weit staerkeres Ergebnis als drei Zufallstreffer.
    """
    return Genome(
        name="Momentum-Beteiligung 90 Tage",
        rationale=(
            "Long, wenn die Veraenderung ueber 90 Tage positiv wird; raus, "
            "wenn sie negativ wird. Dritte Messart desselben Trends - stimmen "
            "alle drei ueberein, liegt es an der Idee."
        ),
        entry_long=[
            Condition(left=_ind("roc", period=90), op=Operator.CROSS_ABOVE,
                      right=_const(0.0)),
        ],
        exit_long=[
            Condition(left=_ind("roc", period=90), op=Operator.LT,
                      right=_const(0.0)),
        ],
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(kind="kapitalanteil", fraction=0.5),
        cooldown_bars=0,
        max_hold_bars=0,
    )


def trend_mit_vollem_einsatz() -> Genome:
    """Dieselbe Regel, aber mit vollem Kapital statt der Haelfte.

    Kein neuer Gedanke, sondern eine Messung: Rendite und Rueckgang skalieren
    beide mit dem Einsatz. Der Kandidat mit halbem Einsatz kam auf +59 % bei
    10,2 % Rueckgang - mit vollem Einsatz muesste daraus grob das Doppelte
    werden, in beiden Richtungen.

    Damit laesst sich die Frage beantworten, die sonst Vermutung bleibt:
    **Wieviel Rendite ist bei 12 % Rueckgang ueberhaupt erreichbar?** Und ob
    die Vorgaben "hoechstens 15 % Rueckgang" und "spuerbarer Gewinn"
    zusammenpassen.
    """
    return Genome(
        name="Trend-Beteiligung voller Einsatz",
        rationale=(
            "Wie die 200-Tage-Beteiligung, aber mit vollem Kapital statt der "
            "Haelfte. Messung, keine neue Idee: Rendite und Rueckgang "
            "skalieren gemeinsam - die Frage ist, wieviel bei der erlaubten "
            "Rueckgangsgrenze herausspringt."
        ),
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("sma", period=200)),
        ],
        exit_long=[
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("sma", period=200)),
        ],
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(kind="kapitalanteil", fraction=1.0),
        cooldown_bars=0,
        max_hold_bars=0,
    )


#: Neunte Generation: dieselbe Idee, mehr Beobachtungen.
GENERATION_9 = [
    trend_200,
    trend_100,
    trend_50,
    trend_beide_richtungen,
    donchian_turtle,
    momentum_beteiligung,
    trend_mit_vollem_einsatz,
]


# ===========================================================================
#  Zehnte Generation - Einsatz nach Schwankungsbreite
# ===========================================================================
#
# Die Messung der neunten Generation war eindeutig: Eine feste Einsatzquote
# skaliert Rendite und Rueckgang **gemeinsam**. Der Sharpe blieb ueber alle
# Quoten bei 1,02 - der Hebel war ausgereizt, egal wie man ihn stellt.
#
# Ein fester Anteil bedeutet aber nicht festes Risiko. In ruhigen Wochen
# schwankt Bitcoin um 30 % im Jahr, in stuermischen um 90 %. Derselbe
# Kapitalanteil traegt dann das Dreifache an Risiko - und der Rueckgang
# entsteht fast vollstaendig in den stuermischen Phasen.
#
# Der Einsatz nach Schwankungsbreite dreht das um: Zielschwankung geteilt
# durch gemessene Schwankung. In ruhigen Phasen mehr Kapital, in wilden
# weniger, ueber die Zeit gleich viel Risiko.
#
# Gemessen auf denselben Daten, gegen dieselbe Regel:
#
#     feste Quote 60 %      +79,1 %   13,5 % p.a.   12,44 % DD   Sharpe 1,02
#     Vola-Ziel 20 %        +83,9 %   14,1 % p.a.   11,71 % DD   Sharpe 1,16
#
# Mehr Rendite bei weniger Rueckgang - das ist keine Skalierung mehr, sondern
# eine bessere Kurve. Der Sharpe steigt von 1,02 auf 1,16.


def _vola_trend(name: str, ziel: float, periode: int, rationale: str) -> Genome:
    """Die 200-Tage-Regel, Einsatz nach Schwankungsbreite.

    Wieder aus einem Bauplan, damit sich die Kandidaten **nur** im Ziel und
    im Messfenster unterscheiden.
    """
    return Genome(
        name=name,
        rationale=rationale,
        entry_long=[
            Condition(left=_price("close"), op=Operator.CROSS_ABOVE,
                      right=_ind("sma", period=200)),
        ],
        exit_long=[
            Condition(left=_price("close"), op=Operator.LT,
                      right=_ind("sma", period=200)),
        ],
        stop=StopSpec(kind="percent", percent=15.0),
        targets=[TargetSpec(rr=20.0, portion=1.0)],
        sizing=SizingSpec(
            kind="vola_ziel", target_vol_pct=ziel, vol_period=periode, fraction=1.0
        ),
        cooldown_bars=0,
        max_hold_bars=0,
    )


def vola_ziel_20() -> Genome:
    return _vola_trend(
        "Trend mit Vola-Ziel 20 %", 20.0, 30,
        "Trendfolge auf 200 Tage, Einsatz gegenlaeufig zur gemessenen "
        "Schwankungsbreite mit Ziel 20 % im Jahr. Haelt den Rueckgang unter "
        "der Grenze; die Jahresrendite bleibt knapp darunter.",
    )


def vola_ziel_22() -> Genome:
    return _vola_trend(
        "Trend mit Vola-Ziel 22 %", 22.0, 30,
        "Dasselbe mit 22 % Zielschwankung. Erreicht die geforderte "
        "Jahresrendite, ueberschreitet dafuer die Rueckgangsgrenze knapp - "
        "der Gegenpol zum 20-%-Kandidaten.",
    )


def vola_ziel_kurzes_fenster() -> Genome:
    return _vola_trend(
        "Vola-Ziel, kurzes Messfenster", 20.0, 20,
        "Zielschwankung 20 %, aber ueber nur 20 Tage gemessen. Reagiert "
        "schneller auf Vola-Spruenge - die Frage ist, ob das hilft oder nur "
        "mehr Umschichtung erzeugt.",
    )


def vola_ziel_langes_fenster() -> Genome:
    return _vola_trend(
        "Vola-Ziel, langes Messfenster", 20.0, 60,
        "Zielschwankung 20 % ueber 60 Tage. Traeger, dafuer stetiger. "
        "Zusammen mit 20 und 30 Tagen ergibt das eine Plateau-Probe: Liegt "
        "das mittlere Fenster deutlich vorn, ist der Wert womoeglich nur "
        "gut getroffen.",
    )


#: Zehnte Generation: Einsatz nach Schwankungsbreite.
GENERATION_10 = [
    vola_ziel_20,
    vola_ziel_22,
    vola_ziel_kurzes_fenster,
    vola_ziel_langes_fenster,
]


GENERATIONS = {
    1: GENERATION_1,
    2: GENERATION_2,
    3: GENERATION_3,
    4: GENERATION_4,
    5: GENERATION_5,
    6: GENERATION_6,
    7: GENERATION_7,
    8: GENERATION_8,
    9: GENERATION_9,
    10: GENERATION_10,
}


def load_seeds(generation: int = 5) -> list[Genome]:
    """Die Kandidaten einer Generation erzeugen.

    Standard ist die neueste: Was widerlegt ist, muss nicht erneut geprueft
    werden - jeder Wiederholungsversuch zaehlt in der Mehrfachtest-Korrektur
    und macht die Huerde fuer alle folgenden hoeher, ohne etwas beizutragen.
    """
    if generation not in GENERATIONS:
        raise ValueError(
            f"Generation {generation} gibt es nicht. Verfuegbar: {sorted(GENERATIONS)}"
        )
    return [build() for build in GENERATIONS[generation]]
