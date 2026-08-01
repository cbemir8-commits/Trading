# Autonomes BTC-Trading-System (Bybit)

Selbstlernendes Handelssystem für BTC-Perpetuals. Eine KI entwickelt und verbessert
laufend die Strategie, eine deterministische Engine handelt sie, ein Dashboard zeigt
live, was passiert.

> **Status:** Phase 0 (Fundament) — Konfiguration, Bybit-Adapter, Positions-Sizer,
> Health-Check. Handelt noch nicht.

---

## Grundprinzip: Die KI schlägt vor, der Code entscheidet

**Im Ausführungspfad läuft kein LLM.** Nie.

| | Wer | Warum |
|---|---|---|
| Strategien erfinden & verbessern | Claude (periodisch) | Kreativität, Mustererkennung, Fehleranalyse |
| Handeln | Python (Echtzeit) | Schnell, reproduzierbar, backtestbar |
| Risiko durchsetzen | Python (Vetorecht) | Darf von der KI nicht überschrieben werden |

Claude gibt Strategien als **JSON-Genome** aus einer festen Indikator-Whitelist aus.
Es führt nie eigenen Code auf dem Konto aus. Was im Backtest lief, läuft auch live.

---

## Der Hebel — die wichtigste Rechnung im System

Der Hebel ist hier **kein Regler für mehr Gewinn**. Er ist das *Ergebnis* der
risikobasierten Positionsgröße:

```
Risikobetrag  = Kapital × risk_per_trade_pct / 100
Menge         = Risikobetrag / Stop-Distanz      (auf qty_step abgerundet)
Nominalwert   = Menge × Einstiegspreis
Hebel         = Nominalwert / Kapital
```

Daraus folgt eine Identität, die man sich merken sollte:

```
Hebel = Risiko% / Stop%
```

Bei 500 € Kapital und 0,75 % Risiko (= 3,75 € pro Trade):

| Stop-Distanz | Hebel | Nominalwert | Menge BTC | riskiertes Geld |
|---|---|---|---|---|
| 1,0 % | 0,75× | 375 € | 0,003 | 3,75 € |
| 0,5 % | 1,50× | 750 € | 0,007 | 3,75 € |
| 0,3 % | 2,50× | 1250 € | 0,012 | 3,75 € |
| 0,2 % | 3,75× | ⚠️ über 3×-Deckel → wird verkleinert | | < 3,75 € |

Drei Dinge fallen auf:

1. **Enge Stops brauchen zwingend Hebel.** Ohne ihn wären wir auf Stops jenseits von
   1,5 % beschränkt — und damit auf sehr wenige Setups. Bei 500 € kommt dazu: Bybits
   Mindestmenge von 0,001 BTC entspricht bei 100k$ schon 100 $ Nominalwert.
2. **Das riskierte Geld bleibt in jeder Zeile gleich.** Der Hebel steigt, weil der
   Stop enger wird — nicht weil wir mutiger werden.
3. **Mehr Kapital erhöht den Hebel nicht.** Er hängt nur an Risiko% und Stop%.

### Die teure Falle: Liquidation hängt am *eingestellten* Hebel

Bei Isolated Margin hinterlegt Bybit für eine Position genau `Nominalwert / eingestellter
Hebel` als Margin. Der Rest des Kontos schützt diese Position **nicht**.

| Am Symbol eingestellt | Liquidation entfernt | Bewertung |
|---|---|---|
| 3× | ~33 % | Unerreichbar, wenn der Stop bei 1 % sitzt |
| 20× | ~4,5 % | Innerhalb eines gewöhnlichen BTC-Dochts |

Steht bei Bybit 25× eingestellt, liegt die Liquidation bei ~4 % — **auch wenn unsere
Position gemessen am Gesamtkapital nur 1,2× beträgt**. Deshalb prüft der Sizer gegen
`RISK__MAX_LEVERAGE` (den eingestellten Wert), nicht gegen das abgeleitete Verhältnis.
Siehe `tests/test_sizing.py::test_liquidation_uses_exchange_setting_not_derived_ratio`.

**Der einzige Regler, der das Risiko wirklich verändert, ist `RISK__RISK_PER_TRADE_PCT`.**

---

## Schnellstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m cli setup       # fragt Key + Secret ab, legt .env an, prüft sofort
```

`setup` fragt die Zugangsdaten **per Eingabeaufforderung** ab, nicht als
Kommandozeilenargument: Ein Argument stünde in der Prozessliste und in der
Shell-History. Das Secret wird beim Tippen nicht angezeigt, die `.env` bekommt
Dateirechte 600, und der Health-Check läuft direkt hinterher.

Der Health-Check ist der **erste Schritt auf jedem neuen Server**. Er prüft:

- Ist Bybit von hier aus überhaupt erreichbar? (Geoblocking)
- Stimmt die Systemuhr? (zu große Abweichung ⇒ jede Signatur schlägt fehl)
- Reicht die Historie für Walk-Forward?
- **Hat der API-Key ein Auszahlungsrecht?** ⇒ harter Fehler
- Welcher Hebel ergibt sich bei welcher Stop-Distanz?

> ⚠️ **Der Claude-Code-Entwicklungscontainer ist von Bybit geoblockt** (CloudFront, HTTP 403).
> Der Health-Check erkennt und benennt das. Die gesamte Testsuite läuft deshalb ohne
> Netzwerk gegen aufgezeichnete Fixtures; die echte Verbindung wird auf dem VPS geprüft.

---

## API-Key einrichten (Sicherheit)

Auf Bybit unter *API Management* einen Key erzeugen.

**Erste Frage: „Read-Only" oder „Read-Write"?** → **Read-Write.**
Read-Only ist die naheliegende, sichere Wahl — und die falsche: Ein solcher Key
kann keine Order platzieren, der Handel scheitert dann bei jedem Signal. Lesen
(Kontostand, Positionen, Kerzen) ist in Read-Write enthalten; ein zweiter Key
dafür ist nicht nötig.

**Danach nur diese Rechte anhaken:**

| Recht | Einstellung |
|---|---|
| Unified Trading → Trade (Order, Position, Stop) | ✅ |
| **Withdrawal / Auszahlung** | ❌ **NIEMALS** |
| Transfer, Subkonto, Exchange | ❌ nicht nötig |
| IP-Whitelist | ✅ VPS-IP eintragen |

> **Demo-Konto:** Demo-Keys werden *innerhalb* des Demo-Kontos erzeugt
> (Profil → Demo Trading → API) und funktionieren nur dort. Ein Key aus dem
> echten Konto wird gegen `api-demo.bybit.com` mit „ungültiger API-Key"
> abgelehnt — und umgekehrt. Das ist der häufigste Stolperstein beim Start.

Ein kompromittierter Key ohne Auszahlungsrecht kann schlimmstenfalls schlecht handeln —
das Geld bleibt auf dem Konto. Mit Auszahlungsrecht ist es weg.

**Keys niemals in einen Chat kopieren, niemals ins Repo.** Sie gehören ausschließlich
in die `.env` auf dem Server.

---

## Kommandozeile

```bash
python -m cli setup                       # Zugangsdaten einrichten
python -m cli healthcheck                 # zuerst auf jedem neuen Server
python -m cli backfill --von 2020-03-30   # Historie laden (resumierbar)
python -m cli status                      # was liegt im Speicher?
python -m cli quality                     # Lücken, Duplikate, Ausreißer
python -m cli ingest                      # Live-Kerzen mitschreiben
python -m cli leverage --kapital 500      # Hebel-Tabelle für dein Konto
python -m cli research                    # Strategien pruefen, Champion waehlen
python -m cli research --ki               # KI schlaegt neue Kandidaten vor
python -m cli review                      # laeuft die Strategie noch?
python -m cli trade --trocken             # Handelsplan zeigen, keine Order
python -m cli trade                       # handeln
python -m cli dashboard                   # Website + Not-Aus
```

## Auf einem Server einrichten

Schritt für Schritt, zum Kopieren: **[deploy/README.md](deploy/README.md)**

Rechne mit 30 Minuten. Enthält die Grundabsicherung des Servers, die
`systemd`-Dienste (Bot und Dashboard getrennt), den SSH-Tunnel fürs iPhone —
und den Härtetest, der über alles andere entscheidet: Prozess mitten in einer
offenen Position hart killen und bei Bybit nachsehen, ob der Stop noch hängt.

## Die zwei Prozesse

Handel und Website laufen **getrennt**:

```
python -m cli trade       ──schreibt──▶  state/live.json, events.jsonl
                          ◀──liest────   state/command.json
python -m cli dashboard   ──liest────▶   http://localhost:8000
```

Das ist Absicht. Liefe die Website im selben Prozess wie der Handel, wäre sie
genau dann weg, wenn man sie am dringendsten braucht — nämlich wenn der Handel
abgestürzt ist. Getrennt zeigt sie stattdessen *„Handelsprozess antwortet nicht,
letztes Lebenszeichen vor 14 Minuten"*. Das ist die Information, um die es geht.

Die Website spricht **nie selbst mit Bybit**. Sie liest Dateien und legt
Anweisungen ab, die der Handel bei der nächsten Kerze abholt. Ein Fehler dort
kann keine Order auslösen.

Aufs iPhone kommt sie über einen SSH-Tunnel:

```bash
ssh -L 8000:localhost:8000 benutzer@server
```

Dann `http://localhost:8000` öffnen, *Teilen → Zum Home-Bildschirm* — und sie
verhält sich wie eine App.

`backfill` lädt ~6 Jahre BTC-Historie (1m/15m/1h/4h) in rund 3.400 Anfragen
(~8 Minuten bei 8 req/s). Er ist **resumierbar** — ein Abbruch kostet höchstens
eine Seite, der nächste Aufruf setzt hinter der letzten vollständigen Kerze an.

## Struktur

```
core/       Konfiguration, Domänenmodelle          [P0 ✓]
data/       Bybit-Adapter, Store, Backfill, WS     [P0 ✓ / P1 ✓]
strategy/   Genome, Compiler, Indikatoren          [P3]
backtest/   Engine, Fill-Modell, Walk-Forward      [P2]
execution/  Sizer, Risk-Officer, Order-Router      [P0 ✓ / P4]
research/   CEO, Analyst, Gates, Champion          [P6]
api/ web/   FastAPI + Next.js PWA                  [P5]
scripts/    Health-Check, Wartungswerkzeuge        [P0 ✓]
```

### Datenhaltung — bewusst zweigleisig

| | Wofür | Warum |
|---|---|---|
| **Parquet** | Historische Kerzen | Spaltenorientiert; ein Walk-Forward scannt Millionen Zeilen. Nach Monat partitioniert ⇒ Backfill resumierbar. |
| **Postgres** | Trades, Positionen, Research-Journal, Kosten | Transaktional, gleichzeitig les- und schreibbar. |

Im Parquet liegen `float64` statt `Decimal` — der Rundungsfehler liegt bei BTC-Preisen
um 100.000 bei ~1e-11, also neun Größenordnungen unter der Tick-Größe von 0,1, während
`Decimal` über 3,3 Mio. Kerzen zwei Größenordnungen langsamer wäre. `Decimal` bleibt
zwingend für alles, was zur Börse geht.

### Drei Lookahead-Fallen, gegen die explizit gebaut wird

1. **Kerzenreihenfolge.** Bybit liefert absteigend (neueste zuerst). Unbemerkt ergibt
   das einen rückwärts durch die Zeit laufenden Backtest, der plausibel aussieht.
2. **Unfertige Kerzen.** Die zuletzt gelieferte Kerze bildet sich meist noch. Ihr
   Hoch/Tief/Schluss stand zum Signalzeitpunkt nicht fest. `drop_unfinished()` wirft sie weg.
3. **Unbestätigte WS-Updates.** Bybit sendet während einer laufenden Periode mehrfach
   Aktualisierungen mit `confirm: false`. Nur `confirm: true` wird gespeichert.

Aller Bybit-Kontakt läuft ausschließlich über `data/bybit/adapter.py`. Das macht die
Demo/Live-Umschaltung zu einer Konfigurationsänderung und die Testsuite netzwerkfrei.

---

## Tests

```bash
pytest -q                       # ohne Netzwerk, ~3 s
RUN_NETWORK_TESTS=1 pytest      # zusätzlich echte Bybit-Aufrufe (nur auf dem VPS)
```

Schwerpunkte der aktuellen 62 Tests: Positionsgröße und Hebel (inkl. Liquidations­schutz),
Signierung, Fehlerklassifikation, **chronologische Sortierung der Kerzen** (Bybit liefert
sie rückwärts — unbemerkt ergibt das einen rückwärts laufenden Backtest).

---

## Risikorahmen

| Parameter | Wert | Env |
|---|---|---|
| Risiko pro Trade | 0,75 % | `RISK__RISK_PER_TRADE_PCT` |
| Hebeldeckel | 3× isoliert | `RISK__MAX_LEVERAGE` |
| Liquidationspuffer | 4× Stop-Distanz | `RISK__MIN_LIQUIDATION_BUFFER` |
| Tagesverlust | 3 % → 24 h Pause | `RISK__DAILY_LOSS_LIMIT_PCT` |
| Wochenverlust | 7 % → Stopp | `RISK__WEEKLY_LOSS_LIMIT_PCT` |
| **Kill-Switch** | **15 % Drawdown** | `RISK__MAX_DRAWDOWN_PCT` |

Diese Werte liegen in der Umgebung, nicht im Prompt — die Research-KI kann sie nicht ändern.

### Gebühren-Disziplin

Bei kleinem Konto entscheidend: **Entries und Take-Profits laufen als PostOnly-Limit
(Maker, 0,020 %), nur der Stop-Loss ist Market (Taker, 0,055 %).**

30 Trades/Monat × 900 $ Nominal: ~11 $ (Maker) statt ~30 $ (Taker) — 2 % statt 5,5 %
des Kontos pro Monat.

---

## Warum kein Gewinnversprechen

„Perfekt" gibt es im Trading nicht. Die meisten Strategien, die im Backtest glänzen,
überleben live nicht — genau dagegen bauen wir die acht Zulassungs-Gates (P3). Sie sind
ein Filter, keine Garantie.

Es ist möglich, dass die KI keine Strategie findet, die alle Gates besteht. Das wäre
kein Fehler des Systems, sondern seine ehrlichste Leistung.
