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

GENERATIONS = {1: GENERATION_1, 2: GENERATION_2, 3: GENERATION_3}


def load_seeds(generation: int = 2) -> list[Genome]:
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
