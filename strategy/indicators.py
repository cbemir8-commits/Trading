"""Indikator-Whitelist.

Das ist bewusst eine **geschlossene Liste**. Die Research-KI darf Indikatoren
kombinieren und parametrieren, aber keine neuen erfinden - sie gibt nur Namen
und Parameter aus, die hier eingetragen sind. So bleibt der Suchraum gross
genug fuer echte Kreativitaet und klein genug, um jede erzeugte Strategie
vollstaendig testen zu koennen. Vor allem aber: Es wird nie Code ausgefuehrt,
den ein Sprachmodell geschrieben hat.

**Jede Funktion hier muss kausal sein.** Der Wert an Position i darf
ausschliesslich von Kerzen bis einschliesslich i abhaengen. Ein zentrierter
Durchschnitt, ein ``shift(-1)`` oder ein ``bfill()`` erzeugt Lookahead, den
weder der BarContext noch der Perturbationstest im Nachhinein reparieren
koennen - er steckt dann schon in den Daten. Der Test
``test_all_indicators_are_causal`` prueft das fuer jeden Eintrag automatisch.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    """Beschreibung eines Indikators fuer die Research-KI.

    ``param_bounds`` begrenzt, was die KI vorschlagen darf. Eine Periode von
    3 auf 15-Minuten-Kerzen ist Rauschen, eine von 5000 passt in kein
    Backtest-Fenster - beides waere verschwendete Rechenzeit.
    """

    name: str
    description: str
    param_bounds: dict[str, tuple[int, int]]
    outputs: tuple[str, ...] = ("value",)


def sma(frame: pd.DataFrame, period: int) -> np.ndarray:
    """Einfacher gleitender Durchschnitt."""
    return frame["close"].rolling(period, min_periods=period).mean().to_numpy(dtype=np.float64)


def ema(frame: pd.DataFrame, period: int) -> np.ndarray:
    """Exponentieller gleitender Durchschnitt.

    ``adjust=False`` liefert die rekursive Variante, die auch im Livebetrieb
    Kerze fuer Kerze fortgeschrieben werden kann. Mit ``adjust=True`` haengt
    jeder Wert vom Beginn der Reihe ab - der Backtest bekaeme dann andere Werte
    als der Livebetrieb, der irgendwann mittendrin startet.
    """
    return (
        frame["close"]
        .ewm(span=period, adjust=False, min_periods=period)
        .mean()
        .to_numpy(dtype=np.float64)
    )


def rsi(frame: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Relative Strength Index (0..100), Wilder-Glaettung."""
    delta = frame["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    # Ohne jeden Verlust ist der RSI definitionsgemaess 100.
    result = result.where(avg_loss != 0, 100.0)
    return result.to_numpy(dtype=np.float64)


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(frame: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Average True Range - das Mass fuer Stop-Distanzen.

    Ein ATR-basierter Stop passt sich der Volatilitaet an: In ruhigen Phasen
    eng, in turbulenten weit. Ein fester Prozentsatz wird dagegen in ruhigen
    Phasen zu weit (unnoetig viel Risiko) und in turbulenten zu eng (wird vom
    normalen Rauschen ausgeloest).
    """
    return (
        true_range(frame)
        .ewm(alpha=1 / period, adjust=False, min_periods=period)
        .mean()
        .to_numpy(dtype=np.float64)
    )


def atr_pct(frame: pd.DataFrame, period: int = 14) -> np.ndarray:
    """ATR in Prozent des Preises - vergleichbar ueber Preisniveaus hinweg."""
    values = atr(frame, period)
    return values / frame["close"].to_numpy(dtype=np.float64) * 100


def adx(frame: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Average Directional Index - misst Trendstaerke, nicht Richtung.

    Der wichtigste Regime-Filter: Ausbruchsstrategien funktionieren bei hohem
    ADX, Mittelwert-Rueckkehr bei niedrigem. Ohne diesen Filter handelt eine
    Strategie zwangslaeufig auch im falschen Marktumfeld.
    """
    up_move = frame["high"].diff()
    down_move = -frame["low"].diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = true_range(frame)
    atr_series = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    plus_di = (
        100
        * pd.Series(plus_dm, index=frame.index)
        .ewm(alpha=1 / period, adjust=False, min_periods=period)
        .mean()
        / atr_series
    )
    minus_di = (
        100
        * pd.Series(minus_dm, index=frame.index)
        .ewm(alpha=1 / period, adjust=False, min_periods=period)
        .mean()
        / atr_series
    )

    denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denominator
    return (
        dx.ewm(alpha=1 / period, adjust=False, min_periods=period)
        .mean()
        .to_numpy(dtype=np.float64)
    )


def bollinger_upper(frame: pd.DataFrame, period: int = 20, deviations: int = 2) -> np.ndarray:
    middle = frame["close"].rolling(period, min_periods=period).mean()
    spread = frame["close"].rolling(period, min_periods=period).std(ddof=0)
    return (middle + deviations * spread).to_numpy(dtype=np.float64)


def bollinger_lower(frame: pd.DataFrame, period: int = 20, deviations: int = 2) -> np.ndarray:
    middle = frame["close"].rolling(period, min_periods=period).mean()
    spread = frame["close"].rolling(period, min_periods=period).std(ddof=0)
    return (middle - deviations * spread).to_numpy(dtype=np.float64)


def bollinger_width(frame: pd.DataFrame, period: int = 20, deviations: int = 2) -> np.ndarray:
    """Bandbreite in Prozent - erkennt Volatilitaets-Zusammenziehungen.

    Enge Baender gehen oft groesseren Bewegungen voraus.
    """
    middle = frame["close"].rolling(period, min_periods=period).mean()
    spread = frame["close"].rolling(period, min_periods=period).std(ddof=0)
    return (2 * deviations * spread / middle * 100).to_numpy(dtype=np.float64)


def donchian_upper(frame: pd.DataFrame, period: int = 20) -> np.ndarray:
    """Hoechster Hoechstkurs der letzten N Kerzen - **ohne** die aktuelle.

    Die aktuelle Kerze auszuschliessen ist entscheidend: Sonst liegt der Kanal
    per Konstruktion immer mindestens auf dem aktuellen Hoch, und ein Ausbruch
    darueber kann nie stattfinden. Ein klassischer Fehler, der eine
    Ausbruchsstrategie stumm macht.
    """
    return (
        frame["high"].shift(1).rolling(period, min_periods=period).max().to_numpy(dtype=np.float64)
    )


def donchian_lower(frame: pd.DataFrame, period: int = 20) -> np.ndarray:
    return (
        frame["low"].shift(1).rolling(period, min_periods=period).min().to_numpy(dtype=np.float64)
    )


def macd(frame: pd.DataFrame, fast: int = 12, slow: int = 26) -> np.ndarray:
    fast_ema = frame["close"].ewm(span=fast, adjust=False, min_periods=fast).mean()
    slow_ema = frame["close"].ewm(span=slow, adjust=False, min_periods=slow).mean()
    return (fast_ema - slow_ema).to_numpy(dtype=np.float64)


def macd_signal(
    frame: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> np.ndarray:
    line = pd.Series(macd(frame, fast, slow), index=frame.index)
    return line.ewm(span=signal, adjust=False, min_periods=signal).mean().to_numpy(dtype=np.float64)


def roc(frame: pd.DataFrame, period: int = 10) -> np.ndarray:
    """Rate of Change in Prozent - einfaches Momentum."""
    return (frame["close"].pct_change(period) * 100).to_numpy(dtype=np.float64)


def volume_zscore(frame: pd.DataFrame, period: int = 50) -> np.ndarray:
    """Wie ungewoehnlich ist das Volumen dieser Kerze?

    Ausbrueche mit ueberdurchschnittlichem Volumen halten haeufiger als solche
    ohne - deshalb ist das ein nuetzlicher Bestaetigungsfilter.
    """
    volume = frame["volume"]
    mean = volume.rolling(period, min_periods=period).mean()
    spread = volume.rolling(period, min_periods=period).std(ddof=0)
    return ((volume - mean) / spread.replace(0, np.nan)).to_numpy(dtype=np.float64)


def periods_per_year(frame: pd.DataFrame) -> float:
    """Wie viele Kerzen dieser Reihe passen in ein Jahr?

    Abgelesen am tatsaechlichen Abstand der Zeitstempel, nicht angenommen.
    Diese Zahl stand frueher fest im Quelltext - 35.040, also 15-Minuten-Kerzen.
    Auf Tageskerzen kam damit eine Volatilitaet heraus, die um den Faktor zehn
    zu hoch war, ohne dass irgendetwas darauf hingewiesen haette.

    Krypto handelt durchgehend, deshalb 365 Tage und keine Boersentage.
    """
    if "open_time" not in frame.columns or len(frame) < 3:
        return 365 * 24 * 4  # Rueckfall: 15-Minuten-Kerzen

    zeiten = pd.to_datetime(frame["open_time"])
    # Median statt Mittelwert: Eine einzelne Luecke - Boersenwartung, fehlende
    # Kerzen - wuerde den Mittelwert verschieben und die Skalierung verfaelschen.
    abstand = zeiten.diff().median()
    if pd.isna(abstand) or abstand.total_seconds() <= 0:
        return 365 * 24 * 4
    return (365 * 24 * 3600) / abstand.total_seconds()


def realized_vol(frame: pd.DataFrame, period: int = 20) -> np.ndarray:
    """Annualisierte realisierte Volatilitaet in Prozent.

    Die Annualisierung folgt der tatsaechlichen Kerzenlaenge - siehe
    :func:`periods_per_year`.
    """
    returns = np.log(frame["close"] / frame["close"].shift(1))
    return (
        returns.rolling(period, min_periods=period).std(ddof=0)
        * np.sqrt(periods_per_year(frame))
        * 100
    ).to_numpy(dtype=np.float64)


def distance_to_ema_pct(frame: pd.DataFrame, period: int = 50) -> np.ndarray:
    """Abstand des Preises zum EMA in Prozent.

    Nuetzlich fuer Mittelwert-Rueckkehr: Wie weit ist der Preis von seinem
    Anker entfernt?
    """
    anchor = ema(frame, period)
    close = frame["close"].to_numpy(dtype=np.float64)
    return (close - anchor) / anchor * 100


def hour_of_day(frame: pd.DataFrame) -> np.ndarray:
    """Stunde (UTC) - fuer Sitzungsfilter.

    Die Liquiditaet in Krypto schwankt deutlich zwischen asiatischer,
    europaeischer und US-Sitzung. Eine Strategie kann davon abhaengen.
    """
    return frame["open_time"].dt.hour.to_numpy(dtype=np.float64)



# ---------------------------------------------------------------------------
#  Bausteine der bekannten Scalp-Setups
# ---------------------------------------------------------------------------
#
# Was in Videos und Foren unter vielen Namen kursiert - Order Block, Liquidity
# Sweep, VWAP Bounce, Squeeze - laesst sich fast immer auf wenige messbare
# Groessen zurueckfuehren. Genau die stehen hier. Ein Name ist keine Strategie;
# eine Bedingung auf einer Zahl ist eine.
#
# Bewusst als Bausteine und nicht als fertige "Setups": Wer ein Setup als einen
# Indikator einbaut, kann hinterher nicht mehr sagen, welcher Teil davon
# gewirkt hat.


def vwap_distance_pct(frame: pd.DataFrame, period: int = 96) -> np.ndarray:
    """Abstand zum volumengewichteten Durchschnittspreis, in Prozent.

    Der VWAP ist die meistbenutzte Linie im kurzfristigen Handel, und zwar aus
    einem sachlichen Grund: Grosse Haeuser messen ihre Ausfuehrung daran. Ein
    Kurs deutlich unter VWAP heisst, dass wer heute gekauft hat, im Minus liegt.

    Gerechnet ueber ein rollierendes Fenster statt ab Sitzungsbeginn - Krypto
    hat keinen Handelsschluss, an dem sich ein Anker natuerlich ergaebe. 96
    Perioden sind auf 15-Minuten-Kerzen ein Tag.
    """
    close = frame["close"].astype("float64")
    volume = frame["volume"].astype("float64")
    typical = (
        frame["high"].astype("float64")
        + frame["low"].astype("float64")
        + close
    ) / 3.0

    gewichtet = (typical * volume).rolling(period, min_periods=period).sum()
    menge = volume.rolling(period, min_periods=period).sum()
    vwap = gewichtet / menge.replace(0.0, np.nan)
    return ((close - vwap) / vwap * 100.0).to_numpy(dtype=np.float64)


def stochastic(frame: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Wo im Bereich der letzten N Kerzen liegt der Schlusskurs? 0..100.

    Anders als der RSI, der Auf- gegen Abwaertsbewegung misst, misst das hier
    die Lage in der Spanne. Bei 0 schliesst der Kurs am Tief der Periode, bei
    100 am Hoch.
    """
    tief = frame["low"].astype("float64").rolling(period, min_periods=period).min()
    hoch = frame["high"].astype("float64").rolling(period, min_periods=period).max()
    spanne = (hoch - tief).replace(0.0, np.nan)
    return (
        (frame["close"].astype("float64") - tief) / spanne * 100.0
    ).to_numpy(dtype=np.float64)


def keltner_upper(frame: pd.DataFrame, period: int = 20, multiple: float = 2.0) -> np.ndarray:
    """Oberes Keltner-Band: EMA plus ein Vielfaches der ATR.

    Der Unterschied zu Bollinger ist nicht kosmetisch: Bollinger misst die
    Streuung der Schlusskurse, Keltner die tatsaechliche Spanne inklusive
    Luecken. Liegt das Bollinger-Band **innerhalb** des Keltner-Bands, spricht
    man von einer Enge - die klassische Vorstufe eines Ausbruchs.
    """
    mitte = ema(frame, period)
    spanne = atr(frame, period)
    return mitte + spanne * float(multiple)


def keltner_lower(frame: pd.DataFrame, period: int = 20, multiple: float = 2.0) -> np.ndarray:
    mitte = ema(frame, period)
    spanne = atr(frame, period)
    return mitte - spanne * float(multiple)


def swing_high(frame: pd.DataFrame, period: int = 20) -> np.ndarray:
    """Das hoechste Hoch der letzten N Kerzen - **ohne die aktuelle**.

    Der ausgeschlossene aktuelle Balken ist der ganze Punkt. Ein Hoch, das die
    laufende Kerze einschliesst, ist zirkulaer: Der Kurs kann sein eigenes Hoch
    nicht durchbrechen. Genau daran scheitern viele selbstgebaute
    Ausbruchsregeln, ohne dass es auffaellt - sie loesen nie aus oder immer.
    """
    return (
        frame["high"].astype("float64")
        .shift(1)
        .rolling(period, min_periods=period)
        .max()
        .to_numpy(dtype=np.float64)
    )


def swing_low(frame: pd.DataFrame, period: int = 20) -> np.ndarray:
    """Das tiefste Tief der letzten N Kerzen, ohne die aktuelle."""
    return (
        frame["low"].astype("float64")
        .shift(1)
        .rolling(period, min_periods=period)
        .min()
        .to_numpy(dtype=np.float64)
    )


def wick_below_pct(frame: pd.DataFrame) -> np.ndarray:
    """Unterer Docht in Prozent des Kurses.

    Die messbare Fassung dessen, was als "Liquidity Sweep" oder "Stop Hunt"
    beschrieben wird: Der Kurs faellt unter ein Tief, wird aber sofort
    zurueckgekauft und schliesst wieder darueber. Uebrig bleibt ein langer
    Docht nach unten.

    Ob dahinter wirklich abgeraeumte Stops stehen, ist eine Erzaehlung. Der
    Docht ist die Zahl.
    """
    close = frame["close"].astype("float64")
    tief = frame["low"].astype("float64")
    offen = frame["open"].astype("float64")
    koerper_tief = np.minimum(close, offen)
    return ((koerper_tief - tief) / close * 100.0).to_numpy(dtype=np.float64)


def wick_above_pct(frame: pd.DataFrame) -> np.ndarray:
    """Oberer Docht in Prozent des Kurses - das Gegenstueck nach oben."""
    close = frame["close"].astype("float64")
    hoch = frame["high"].astype("float64")
    offen = frame["open"].astype("float64")
    koerper_hoch = np.maximum(close, offen)
    return ((hoch - koerper_hoch) / close * 100.0).to_numpy(dtype=np.float64)


def body_pct(frame: pd.DataFrame) -> np.ndarray:
    """Kerzenkoerper in Prozent des Kurses, mit Vorzeichen.

    Positiv bei steigender Kerze. Die schlichte Fassung von "starke Kerze",
    "Momentum-Kerze" oder "Engulfing" - alle drei sind letztlich Aussagen
    darueber, wie weit sich der Kurs innerhalb einer Periode bewegt hat.
    """
    close = frame["close"].astype("float64")
    offen = frame["open"].astype("float64")
    return ((close - offen) / close * 100.0).to_numpy(dtype=np.float64)


# ---------------------------------------------------------------------------
#  Smart-Money-Bausteine: Abfolgen statt Momentaufnahmen
# ---------------------------------------------------------------------------
#
# Die bisherigen Indikatoren beschreiben alle **einen Balken**. Das reicht fuer
# "ueberverkauft" oder "ueber dem Durchschnitt", aber nicht fuer das Modell,
# das hinter ICT und den daraus abgeleiteten Ansaetzen steht. Dort ist das
# Signal eine **Abfolge**:
#
#     1. Liquiditaet abgeraeumt  - Kurs sticht unter ein Tief und schliesst
#                                  wieder darueber
#     2. Struktur gebrochen      - danach ein Impuls ueber das letzte Hoch
#     3. Rueckkehr in die Luecke - Einstieg dort, wo der Impuls eine
#                                  Preisluecke hinterlassen hat
#
# Eine Bedingung auf einem einzelnen Balken kann so etwas nicht ausdruecken.
# Deshalb geben die folgenden Indikatoren **Abstaende in Balken** zurueck: "wie
# lange ist das her". Damit laesst sich eine Reihenfolge als gewoehnliche
# Bedingung schreiben - "Sweep vor hoechstens 10 Balken und Bruch vor
# hoechstens 5".
#
# Alle rechnen ausschliesslich rueckwaerts. Ein Indikator, der wuesste, dass
# ein Bruch noch kommt, waere die bequemste Art, sich selbst zu betruegen.

#: Ersatzwert fuer "ist noch nie passiert". Bewusst gross statt NaN: Eine
#: Bedingung "vor hoechstens 10 Balken" soll dann schlicht falsch sein, nicht
#: den ganzen Balken unbrauchbar machen.
NIE = 9999.0


def _bars_since(events: np.ndarray) -> np.ndarray:
    """Zu jedem Balken: wie viele Balken seit dem letzten ``True``.

    Der aktuelle Balken zaehlt als 0. Ohne vorheriges Ereignis ``NIE``.
    """
    index = np.arange(len(events), dtype=np.float64)
    letzte = np.where(events, index, np.nan)
    letzte = pd.Series(letzte).ffill().to_numpy()
    abstand = index - letzte
    return np.where(np.isnan(letzte), NIE, abstand)


def fvg_up_pct(frame: pd.DataFrame) -> np.ndarray:
    """Groesse einer aufwaertsgerichteten Preisluecke, in Prozent.

    Die Luecke entsteht ueber drei Balken: Bewegt sich der mittlere so
    kraftvoll nach oben, dass das Tief des dritten ueber dem Hoch des ersten
    liegt, wurde ein Preisbereich uebersprungen - dort hat schlicht kein
    Handel stattgefunden.

    Null, wenn keine Luecke da ist. Kein NaN: "keine Luecke" ist eine Aussage,
    kein fehlender Wert.
    """
    hoch = frame["high"].astype("float64").to_numpy()
    tief = frame["low"].astype("float64").to_numpy()
    close = frame["close"].astype("float64").to_numpy()

    luecke = np.full(len(close), 0.0)
    if len(close) > 2:
        luecke[2:] = np.maximum(0.0, tief[2:] - hoch[:-2])
    return luecke / close * 100.0


def fvg_down_pct(frame: pd.DataFrame) -> np.ndarray:
    """Groesse einer abwaertsgerichteten Preisluecke, in Prozent."""
    hoch = frame["high"].astype("float64").to_numpy()
    tief = frame["low"].astype("float64").to_numpy()
    close = frame["close"].astype("float64").to_numpy()

    luecke = np.full(len(close), 0.0)
    if len(close) > 2:
        luecke[2:] = np.maximum(0.0, tief[:-2] - hoch[2:])
    return luecke / close * 100.0


def fvg_up_level(frame: pd.DataFrame, lookback: int = 20) -> np.ndarray:
    """Untere Kante der juengsten Aufwaerts-Luecke, als Preis.

    Vergleichbar mit ``low``: Faellt der Kurs auf dieses Niveau zurueck, ist er
    in der Luecke - der Einstiegspunkt des Modells. Aelter als ``lookback``
    Balken gilt die Luecke als verbraucht und wird nicht mehr angeboten.
    """
    luecke = fvg_up_pct(frame) > 0
    tief = frame["low"].astype("float64").to_numpy()

    stufen = np.where(luecke, tief, np.nan)
    aktuell = pd.Series(stufen).ffill().to_numpy()
    alter = _bars_since(luecke)
    return np.where(alter <= lookback, aktuell, np.nan)


def bars_since_sweep_low(frame: pd.DataFrame, period: int = 20) -> np.ndarray:
    """Wie lange ist der letzte Abgriff unter ein Tief her?

    Abgriff heisst: Das Tief des Balkens lag unter dem Tief der vorangegangenen
    N Balken, der Schlusskurs aber wieder darueber. Wer dort verkauft hat, ist
    ausgestoppt worden und der Kurs ist trotzdem zurueckgekommen.
    """
    tief = frame["low"].astype("float64").to_numpy()
    close = frame["close"].astype("float64").to_numpy()
    marke = swing_low(frame, period)

    ereignis = (tief < marke) & (close > marke) & ~np.isnan(marke)
    return _bars_since(ereignis)


def bars_since_sweep_high(frame: pd.DataFrame, period: int = 20) -> np.ndarray:
    """Dasselbe nach oben."""
    hoch = frame["high"].astype("float64").to_numpy()
    close = frame["close"].astype("float64").to_numpy()
    marke = swing_high(frame, period)

    ereignis = (hoch > marke) & (close < marke) & ~np.isnan(marke)
    return _bars_since(ereignis)


def bars_since_bos_up(frame: pd.DataFrame, period: int = 10) -> np.ndarray:
    """Wie lange ist der letzte Bruch der Struktur nach oben her?

    Bruch heisst hier: Der Schlusskurs liegt ueber dem hoechsten Hoch der
    vorangegangenen N Balken. Kein Docht, sondern ein Schlusskurs - ein kurz
    ueberschossenes Hoch ist genau das Gegenteil eines Bruchs, naemlich ein
    Abgriff.
    """
    close = frame["close"].astype("float64").to_numpy()
    marke = swing_high(frame, period)
    return _bars_since((close > marke) & ~np.isnan(marke))


def bars_since_bos_down(frame: pd.DataFrame, period: int = 10) -> np.ndarray:
    """Bruch der Struktur nach unten."""
    close = frame["close"].astype("float64").to_numpy()
    marke = swing_low(frame, period)
    return _bars_since((close < marke) & ~np.isnan(marke))


def body_atr_ratio(frame: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Kerzenkoerper im Verhaeltnis zur durchschnittlichen Spanne.

    Warum nicht einfach der Koerper in Prozent: Eine feste Schwelle wie
    "groesser als 0,5 %" bedeutet in ruhigen Wochen "kommt praktisch nie vor"
    und in bewegten "jede dritte Kerze". Sie misst dann die Volatilitaet und
    nicht das, was gemeint war.

    Das Verhaeltnis zur ATR ist von der Phase unabhaengig: 1,5 heisst
    "anderthalb mal die uebliche Spanne dieser Tage" - in jeder Marktlage
    dasselbe. Genau das ist mit "auffaellig grosse Kerze" gemeint.

    Der Fehler ist beim Pruefen aufgefallen: Der Kandidat mit fester
    0,5-%-Schwelle loeste auf 5.000 Kerzen genau einmal aus.
    """
    koerper = body_pct(frame)
    spanne = atr_pct(frame, period)
    return koerper / np.where(spanne > 0, spanne, np.nan)

#: Die Whitelist. Nur was hier steht, darf die Research-KI verwenden.
# ---------------------------------------------------------------------------
#  Funding - die einzigen Eingangsdaten hier, die keine Kursbewegung sind
# ---------------------------------------------------------------------------
#
# Alles andere in dieser Datei rechnet auf Kerzen. Funding sagt etwas anderes:
# wer gerade gedraengt steht. Bei stark positiver Rate zahlen die Longs den
# Shorts - das passiert, wenn zu viele long sind. Diese Information steckt in
# keinem Kursverlauf.
#
# Fehlt die Spalte, geben diese Indikatoren NaN zurueck. Dann handelt die
# Strategie nicht, statt auf einer Annahme zu handeln.


def _funding_column(frame: pd.DataFrame) -> pd.Series:
    if "funding_rate" not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return frame["funding_rate"].astype("float64")


def funding_rate(frame: pd.DataFrame) -> np.ndarray:
    """Die zuletzt festgestellte Funding-Rate, in Prozent.

    Positiv heisst: Longs zahlen. Typische Werte liegen bei 0,01 % je acht
    Stunden; Werte ueber 0,05 % gelten als ausgepraegte Long-Ueberhitzung.
    """
    return (_funding_column(frame) * 100.0).to_numpy(dtype=np.float64)


def funding_avg(frame: pd.DataFrame, period: int = 21) -> np.ndarray:
    """Gleitender Durchschnitt der Funding-Rate in Prozent.

    21 Perioden sind bei achtstuendiger Zahlung rund eine Woche. Der
    Durchschnitt glaettet einzelne Ausschlaege, die oft nur eine Reaktion auf
    eine grosse Order sind.
    """
    return (
        (_funding_column(frame) * 100.0).rolling(period, min_periods=period).mean()
    ).to_numpy(dtype=np.float64)


def funding_zscore(frame: pd.DataFrame, period: int = 90) -> np.ndarray:
    """Wie ungewoehnlich ist die aktuelle Rate im eigenen Verlauf?

    Absolute Schwellen taugen hier schlecht: Was 2021 als extrem galt, ist
    2026 normal. Der z-Wert misst gegen die eigene juengere Geschichte -
    ausschliesslich rueckwaerts.
    """
    values = _funding_column(frame)
    mean = values.rolling(period, min_periods=period).mean()
    deviation = values.rolling(period, min_periods=period).std()
    return ((values - mean) / deviation.replace(0.0, np.nan)).to_numpy(dtype=np.float64)


REGISTRY: dict[str, tuple[Callable[..., np.ndarray], IndicatorSpec]] = {
    "funding_rate": (funding_rate, IndicatorSpec(
        "funding_rate",
        "Funding-Rate in Prozent je 8 h. Positiv = Longs zahlen den Shorts. "
        "Keine Kursgroesse, sondern Positionierung.",
        {})),
    "funding_avg": (funding_avg, IndicatorSpec(
        "funding_avg", "Gleitender Durchschnitt der Funding-Rate in Prozent",
        {"period": (3, 200)})),
    "funding_zscore": (funding_zscore, IndicatorSpec(
        "funding_zscore",
        "Wie ungewoehnlich die Funding-Rate im eigenen Verlauf ist",
        {"period": (20, 400)})),
    "fvg_up_pct": (fvg_up_pct, IndicatorSpec(
        "fvg_up_pct", "Groesse einer Aufwaerts-Preisluecke in Prozent (0 = keine)",
        {})),
    "fvg_down_pct": (fvg_down_pct, IndicatorSpec(
        "fvg_down_pct", "Groesse einer Abwaerts-Preisluecke in Prozent",
        {})),
    "fvg_up_level": (fvg_up_level, IndicatorSpec(
        "fvg_up_level", "Untere Kante der juengsten Aufwaerts-Luecke, als Preis",
        {"lookback": (3, 100)})),
    "bars_since_sweep_low": (bars_since_sweep_low, IndicatorSpec(
        "bars_since_sweep_low", "Balken seit dem letzten Abgriff unter ein Tief",
        {"period": (5, 100)})),
    "bars_since_sweep_high": (bars_since_sweep_high, IndicatorSpec(
        "bars_since_sweep_high", "Balken seit dem letzten Abgriff ueber ein Hoch",
        {"period": (5, 100)})),
    "bars_since_bos_up": (bars_since_bos_up, IndicatorSpec(
        "bars_since_bos_up", "Balken seit dem letzten Strukturbruch nach oben",
        {"period": (3, 100)})),
    "bars_since_bos_down": (bars_since_bos_down, IndicatorSpec(
        "bars_since_bos_down", "Balken seit dem letzten Strukturbruch nach unten",
        {"period": (3, 100)})),
    "vwap_distance_pct": (vwap_distance_pct, IndicatorSpec(
        "vwap_distance_pct",
        "Abstand zum volumengewichteten Durchschnittspreis in Prozent",
        {"period": (10, 400)})),
    "stochastic": (stochastic, IndicatorSpec(
        "stochastic", "Lage des Schlusskurses in der Spanne der Periode, 0..100",
        {"period": (5, 100)})),
    "keltner_upper": (keltner_upper, IndicatorSpec(
        "keltner_upper", "Oberes Keltner-Band (EMA + Vielfaches der ATR)",
        {"period": (10, 100), "multiple": (1, 4)})),
    "keltner_lower": (keltner_lower, IndicatorSpec(
        "keltner_lower", "Unteres Keltner-Band",
        {"period": (10, 100), "multiple": (1, 4)})),
    "swing_high": (swing_high, IndicatorSpec(
        "swing_high", "Hoechstes Hoch der letzten N Kerzen, ohne die aktuelle",
        {"period": (3, 200)})),
    "swing_low": (swing_low, IndicatorSpec(
        "swing_low", "Tiefstes Tief der letzten N Kerzen, ohne die aktuelle",
        {"period": (3, 200)})),
    "wick_below_pct": (wick_below_pct, IndicatorSpec(
        "wick_below_pct", "Unterer Docht in Prozent - messbare Fassung des Stop-Hunt",
        {})),
    "wick_above_pct": (wick_above_pct, IndicatorSpec(
        "wick_above_pct", "Oberer Docht in Prozent",
        {})),
    "body_atr_ratio": (body_atr_ratio, IndicatorSpec(
        "body_atr_ratio",
        "Kerzenkoerper im Verhaeltnis zur ATR - phasenunabhaengig",
        {"period": (5, 50)})),
    "body_pct": (body_pct, IndicatorSpec(
        "body_pct", "Kerzenkoerper in Prozent des Kurses, mit Vorzeichen",
        {})),
    "sma": (sma, IndicatorSpec("sma", "Einfacher gleitender Durchschnitt",
                               {"period": (5, 400)})),
    "ema": (ema, IndicatorSpec("ema", "Exponentieller gleitender Durchschnitt",
                               {"period": (5, 400)})),
    "rsi": (rsi, IndicatorSpec("rsi", "Relative Strength Index 0..100",
                               {"period": (5, 50)})),
    "atr": (atr, IndicatorSpec("atr", "Average True Range, absolut",
                               {"period": (5, 50)})),
    "atr_pct": (atr_pct, IndicatorSpec("atr_pct", "ATR in Prozent des Preises",
                                       {"period": (5, 50)})),
    "adx": (adx, IndicatorSpec("adx", "Trendstaerke 0..100 (ohne Richtung)",
                               {"period": (5, 50)})),
    "bollinger_upper": (bollinger_upper, IndicatorSpec(
        "bollinger_upper", "Oberes Bollinger-Band",
        {"period": (10, 100), "deviations": (1, 4)})),
    "bollinger_lower": (bollinger_lower, IndicatorSpec(
        "bollinger_lower", "Unteres Bollinger-Band",
        {"period": (10, 100), "deviations": (1, 4)})),
    "bollinger_width": (bollinger_width, IndicatorSpec(
        "bollinger_width", "Bandbreite in Prozent - erkennt Volatilitaets-Enge",
        {"period": (10, 100), "deviations": (1, 4)})),
    "donchian_upper": (donchian_upper, IndicatorSpec(
        "donchian_upper", "Hoechstes Hoch der letzten N Kerzen (ohne aktuelle)",
        {"period": (5, 200)})),
    "donchian_lower": (donchian_lower, IndicatorSpec(
        "donchian_lower", "Tiefstes Tief der letzten N Kerzen (ohne aktuelle)",
        {"period": (5, 200)})),
    "macd": (macd, IndicatorSpec("macd", "MACD-Linie",
                                 {"fast": (5, 50), "slow": (10, 100)})),
    "macd_signal": (macd_signal, IndicatorSpec(
        "macd_signal", "MACD-Signallinie",
        {"fast": (5, 50), "slow": (10, 100), "signal": (3, 30)})),
    "roc": (roc, IndicatorSpec("roc", "Rate of Change in Prozent",
                               {"period": (2, 100)})),
    "volume_zscore": (volume_zscore, IndicatorSpec(
        "volume_zscore", "Wie ungewoehnlich ist das Volumen dieser Kerze",
        {"period": (10, 200)})),
    "realized_vol": (realized_vol, IndicatorSpec(
        "realized_vol", "Annualisierte realisierte Volatilitaet in Prozent",
        {"period": (10, 200)})),
    "distance_to_ema_pct": (distance_to_ema_pct, IndicatorSpec(
        "distance_to_ema_pct", "Abstand des Preises zum EMA in Prozent",
        {"period": (10, 400)})),
    "hour_of_day": (hour_of_day, IndicatorSpec(
        "hour_of_day", "Stunde in UTC, fuer Sitzungsfilter", {})),
}

#: Kursfelder, die eine Bedingung direkt ansprechen darf.
PRICE_FIELDS = frozenset({"open", "high", "low", "close", "volume"})


def compute(name: str, frame: pd.DataFrame, params: dict[str, int]) -> np.ndarray:
    """Einen Indikator aus der Whitelist berechnen."""
    entry = REGISTRY.get(name)
    if entry is None:
        raise KeyError(
            f"Indikator '{name}' steht nicht auf der Whitelist. "
            f"Erlaubt: {sorted(REGISTRY)}"
        )
    function, spec = entry

    for key, value in params.items():
        bounds = spec.param_bounds.get(key)
        if bounds is None:
            raise ValueError(f"Indikator '{name}' kennt keinen Parameter '{key}'")
        low, high = bounds
        if not low <= value <= high:
            raise ValueError(
                f"Parameter {name}.{key}={value} liegt ausserhalb von {low}..{high}"
            )

    return function(frame, **params)


def describe_registry() -> str:
    """Menschenlesbare Uebersicht - wird der Research-KI in den Prompt gegeben."""
    lines = []
    for name in sorted(REGISTRY):
        _, spec = REGISTRY[name]
        bounds = ", ".join(f"{k}={v[0]}..{v[1]}" for k, v in spec.param_bounds.items())
        lines.append(f"- {name}({bounds or 'ohne Parameter'}): {spec.description}")
    return "\n".join(lines)
