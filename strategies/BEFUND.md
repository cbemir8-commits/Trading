# Stand der Strategiesuche

Diese Datei haelt fest, was gemessen wurde und welche Wege damit
ausgeschlossen sind. Sie ist kein Champion - `champion.json` entsteht nur,
wenn alle elf Gates bestanden sind.

**Stand: 8 von 11. Nach 59 gepruefen Hypothesen.**

## Der beste Kandidat

    Trend-Beteiligung 50 Tage auf BTC + ETH

    Einstieg   Kurs kreuzt den 50-Tage-Schnitt von unten
    Ausstieg   Kurs faellt unter den 50-Tage-Schnitt
    Stop       4 % vom Einstieg
    Groesse    Vola-Ziel 17,3 %, Konviktions-Bonus 1,0
    Konfluenz  SMA50 > SMA200, ROC(90) > 0, RSI(14) > 50

Gemessen ueber August 2018 bis Mai 2026, Walk-Forward, nach Gebuehren:

    Rendite        +136,1 %      (11,7 % im Jahr)
    Rueckgang         8,72 %
    Sharpe             1,51
    Trades              156      davon 39 Gewinner

## Was noch fehlt

| Gate | Wert | Schwelle |
|---|---|---|
| Messlatte | 11,7 % p.a. | 15 % p.a. |
| Monte-Carlo | 15,70 % | 15,00 % |
| Deflated Sharpe | 0,892 | 0,95 |

Die Messlatte selbst wird **vierfach uebertroffen** (136 % gegen 34 %). Sie
scheitert an der zweiten Bedingung, der Mindestjahresrendite - einer
wirtschaftlichen Entscheidung, keiner statistischen.

## Vier Wege, die ausgemessen und ausgeschlossen sind

**1. Mehr Einsatz.** Es gibt keine Hoehe, die alle drei offenen Gates
zugleich erfuellt:

    Vola-Ziel   p.a.    Rueckgang   Monte-Carlo
       17,29   11,7 %      8,72 %       15,70 %
       22,00   14,4 %     11,83 %       20,83 %
       26,00   17,5 %     14,06 %       23,61 %
       30,00   20,2 %     16,09 %       27,60 %

Wer die Jahresrendite erreicht, reisst Rueckgang und Monte-Carlo.

**2. Teilgewinne mitnehmen.** Senkt die Schiefe (3,74 -> 3,09) und den
Monte-Carlo (15,70 -> 11,73), kostet aber die Haelfte der Rendite
(11,7 -> 5,7 % p.a.). Das Verhaeltnis wird schlechter, nicht besser.

**3. Short-Seite.** Verdoppelt die Trades (156 -> 307), verbessert Rendite
(13,0 % p.a.), Rueckgang (7,76 %) und Deflated Sharpe (0,904). Aber der
Monte-Carlo steigt auf 19,52 % - das Verhaeltnis verschlechtert sich von
1,34 auf 1,50.

**4. Schwache Setups herausfiltern.** Die Diagnose widerlegt die Idee. Nach
Zahl erfuellter Zusatzbedingungen:

    0/3    14 Trades   -0,076 R
    1/3    82 Trades   +1,055 R
    2/3    47 Trades   +0,840 R
    3/3    68 Trades   +2,497 R

Die Reihenfolge ist **nicht monoton** - 1/3 schlaegt 2/3. Das Signal ist
schwach, und die schwachen Setups wegzulassen wuerde +85 R Gewinn loeschen.
Ein Filter darauf waere Anpassung an Rauschen.

## Die eine Zahl, um die es geht

Fuer eine Zulassung muss gelten: Monte-Carlo geteilt durch Jahresrendite
**hoechstens 1,0**. Denn bei 15 % Jahresrendite darf der Monte-Carlo
hoechstens 15 % betragen.

    bisher              1,34
    Teilgewinne 3R/8R   2,45
    Teilgewinne 2R/5R   2,06
    Short-Seite         1,50
    Teilgewinne+Short   2,10

Bester Wert 1,34, noetig 1,00 - **34 % Verbesserung**, und keine
Einsatzhoehe aendert dieses Verhaeltnis. Es haengt allein daran, wie
gleichmaessig die Ergebnisse ausfallen: Schiefe +3,7, Woelbung 17,4. Wenige
Riesengewinner tragen alles, und in einer unguenstigen Reihenfolge liegen
die vielen kleinen Verluste beieinander.

## Was daraus folgt

Weitere Varianten derselben Idee helfen nicht - im Gegenteil. Jede gepruefte
Hypothese hebt die Huerde des Deflated Sharpe:

    bei  59 Versuchen   noetiger Sharpe je Trade  rund 1,19
    bei 100 Versuchen                             rund 1,25
    bei 200 Versuchen                             rund 1,33

Aktuell liegt er bei 1,09. Wer weitersucht, ohne etwas strukturell anderes
zu probieren, entfernt sich vom Ziel, statt sich ihm zu naehern.

Gebraucht wird eine Ertragsquelle, die **gleichmaessiger** liefert als
Trendfolge - nicht eine weitere Trendfolge-Variante.
