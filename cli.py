"""Kommandozeile des Handelssystems.

    python -m cli --help

    python -m cli healthcheck              # zuerst ausfuehren auf neuem Server
    python -m cli backfill --von 2020-03-30
    python -m cli status
    python -m cli quality
    python -m cli ingest                   # Live-Kerzen mitschreiben
    python -m cli trade --trocken          # Handelsplan pruefen, ohne zu handeln
    python -m cli trade                    # handeln
"""

from __future__ import annotations

import asyncio
import signal
from datetime import UTC, datetime

import structlog
import typer
from rich.console import Console
from rich.table import Table

from core.config import get_settings
from core.models import Candle, Interval
from data.backfill import Backfiller, BackfillProgress, RateLimiter, estimate_requests
from data.bybit.adapter import BybitMarketData
from data.bybit.ws import GapFiller, KlineStream
from data.quality import Severity, check_candles
from data.store import CandleStore

app = typer.Typer(
    add_completion=False,
    help="Autonomes BTC-Trading-System auf Bybit.",
    no_args_is_help=True,
)
console = Console()

#: Fuer den Handel benoetigte Zeitreihen. 15m traegt die Signale, 1h/4h liefern
#: den Kontext-Filter, 1m dient der genauen Fill-Simulation im Backtest.
DEFAULT_INTERVALS = [Interval.M1, Interval.M15, Interval.H1, Interval.H4]

#: Start des BTCUSDT-Perpetuals auf Bybit.
BTCUSDT_LAUNCH = datetime(2020, 3, 30, tzinfo=UTC)


def _configure_logging(verbose: bool) -> None:
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            10 if verbose else 20  # DEBUG : INFO
        ),
    )


def _parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise typer.BadParameter(f"Datum muss YYYY-MM-DD sein, war: {value}") from exc


@app.command()
def setup(
    umgebung: str = typer.Option(
        "demo", help="demo | testnet | mainnet. Angefangen wird mit demo."
    ),
    pruefen: bool = typer.Option(
        True, help="Nach dem Speichern sofort den Health-Check laufen lassen."
    ),
) -> None:
    """Bybit-Zugangsdaten einrichten.

    Fragt Key und Secret ab und legt sie in der ``.env`` ab - **nicht** als
    Kommandozeilenargument. Ein Argument stuende in der Prozessliste und in
    der Shell-History; die Eingabe hier nicht.

    Das Secret wird bei der Eingabe nicht angezeigt. Der Key schon: Er ist
    allein wertlos, so wie ein Benutzername, und man muss sehen koennen, ob
    er richtig eingefuegt wurde.
    """
    from pathlib import Path

    from core.config import BybitEnvironment
    from core.envfile import file_is_world_readable, mask, read_env_value, update_env_file

    try:
        environment = BybitEnvironment(umgebung)
    except ValueError as exc:
        raise typer.BadParameter("umgebung muss demo, testnet oder mainnet sein") from exc

    env_path = Path(".env")
    example = Path(".env.example")

    console.print(
        "\n[bold]Bybit-Zugangsdaten einrichten[/]\n"
        f"Umgebung: [bold]{environment.value}[/] -> {environment.rest_url}\n"
    )

    # -- 1. Anleitung --------------------------------------------------------
    if environment is BybitEnvironment.DEMO:
        console.print(
            "[bold]Auf Bybit:[/]\n"
            "  1. Oben rechts aufs Profil, [bold]Demo Trading[/] waehlen.\n"
            "  2. [bold]Im Demo-Konto[/] auf API -> API-Key erstellen.\n"
            "\n"
            "[yellow]Wichtig:[/] Demo-Keys werden im Demo-Konto erzeugt und "
            "funktionieren nur dort.\n"
            "Ein Key aus dem echten Konto wird hier mit 'ungueltige API-Key' "
            "abgelehnt - und umgekehrt.\n"
        )
    else:
        console.print(
            "[bold]Auf Bybit:[/] Profil -> API -> Neuen Key erstellen.\n"
        )

    console.print(
        "[bold]Bei der Abfrage 'Read-Only oder Read-Write':[/]\n"
        "  -> [bold]Read-Write[/]. Ein Read-Only-Key kann keine Order "
        "platzieren; der Handel scheitert dann bei jedem Signal.\n"
        "\n"
        "[bold]Rechte - nur diese anhaken:[/]\n"
        "  [green]x[/] Unified Trading -> Trade   (Order, Position, Stop)\n"
        "  [red] [/] Withdrawal / Auszahlung      [red]NIEMALS aktivieren[/]\n"
        "  [red] [/] Transfer, Subkonto, Exchange  [dim]nicht noetig[/]\n"
        "  [green]x[/] IP-Whitelist auf die IP dieses Servers\n"
        "\n"
        "[dim]Lesen (Kontostand, Positionen, Kerzen) ist in Read-Write "
        "enthalten - ein zweiter Key dafuer ist nicht noetig.\n"
        "Ein gestohlener Key ohne Auszahlungsrecht kann schlimmstenfalls "
        "schlecht handeln; das Geld bleibt auf dem Konto.\n"
        "Mit Auszahlungsrecht ist es weg. Der Health-Check bricht deshalb ab, "
        "wenn das Recht gesetzt ist.[/]\n"
    )

    if environment.is_real_money:
        console.print("[red]MAINNET - hier liegt echtes Geld.[/]")
        if not typer.confirm("Wirklich Mainnet-Zugangsdaten hinterlegen?", default=False):
            console.print("[dim]Abgebrochen. Nichts geaendert.[/]")
            raise typer.Exit(1)

    # -- 2. Datei vorbereiten ------------------------------------------------
    if not env_path.exists():
        if not example.exists():
            console.print("[red].env.example fehlt - falsches Verzeichnis?[/]")
            raise typer.Exit(2)
        env_path.write_text(example.read_text())
        console.print("[dim].env aus .env.example angelegt.[/]")

    existing = read_env_value(env_path, "BYBIT__API_KEY")
    if existing:
        console.print(f"Hinterlegt ist bereits: [bold]{mask(existing)}[/]")
        if not typer.confirm("Ueberschreiben?", default=False):
            console.print("[dim]Abgebrochen. Nichts geaendert.[/]")
            raise typer.Exit(1)

    # -- 3. Eingabe ----------------------------------------------------------
    api_key = typer.prompt("API-Key").strip()
    api_secret = typer.prompt("API-Secret", hide_input=True).strip()

    problems = _check_credentials(api_key, api_secret)
    if problems:
        for problem in problems:
            console.print(f"[red]{problem}[/]")
        raise typer.Exit(2)

    # -- 4. Speichern --------------------------------------------------------
    update_env_file(
        env_path,
        {
            "BYBIT__ENVIRONMENT": environment.value,
            "BYBIT__API_KEY": api_key,
            "BYBIT__API_SECRET": api_secret,
        },
    )
    console.print(
        f"\n[green]Gespeichert in {env_path.resolve()}[/] (Rechte 600)\n"
        f"  Key    {mask(api_key)}\n"
        f"  Secret {mask(api_secret)}\n"
    )

    if file_is_world_readable(env_path):
        console.print("[yellow]Warnung: Andere Konten koennen die Datei lesen.[/]")

    console.print(
        "[dim].env steht in .gitignore und wird nicht committet. "
        "Trotzdem gilt: niemals in einen Chat kopieren.[/]\n"
    )

    # -- 5. Sofort pruefen ---------------------------------------------------
    if not pruefen:
        console.print("[dim]Naechster Schritt: python -m cli healthcheck[/]")
        return

    get_settings.cache_clear()
    from scripts.healthcheck import main as run_healthcheck

    code = run_healthcheck()
    if code == 0:
        console.print("\n[green]Verbindung steht.[/] Weiter mit: python -m cli backfill")
    raise typer.Exit(code)


def _check_credentials(api_key: str, api_secret: str) -> list[str]:
    """Offensichtliche Fehleingaben abfangen, bevor sie in der Datei landen.

    Faengt die drei Faelle, die in der Praxis vorkommen: nichts eingefuegt,
    beim Kopieren Leerzeichen mitgenommen, oder Key und Secret vertauscht
    (das Secret ist bei Bybit deutlich laenger als der Key).
    """
    problems: list[str] = []
    if not api_key:
        problems.append("Kein API-Key eingegeben.")
    if not api_secret:
        problems.append("Kein API-Secret eingegeben.")
    if any(character.isspace() for character in api_key + api_secret):
        problems.append(
            "Key oder Secret enthaelt ein Leerzeichen - beim Kopieren zu viel erwischt."
        )
    if api_key and api_secret and len(api_key) > len(api_secret):
        problems.append(
            "Der Key ist laenger als das Secret. Bei Bybit ist es umgekehrt - "
            "vermutlich vertauscht."
        )
    return problems


@app.command()
def healthcheck() -> None:
    """Verbindung, Uhrzeit, Key-Rechte und Hebel-Vorschau pruefen."""
    from scripts.healthcheck import main as run_healthcheck

    raise typer.Exit(run_healthcheck())


@app.command()
def backfill(
    von: str = typer.Option("2020-03-30", help="Startdatum (YYYY-MM-DD)."),
    bis: str | None = typer.Option(None, help="Enddatum. Standard: jetzt."),
    intervalle: list[str] = typer.Option(
        None, "--intervall", "-i", help="Bybit-Codes, z.B. 15 60 240. Standard: 1 15 60 240."
    ),
    neu: bool = typer.Option(False, "--neu", help="Nicht fortsetzen, komplett neu laden."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Historische Kerzen nachladen.

    Laeuft resumierbar: Ein Abbruch kostet hoechstens eine Seite. Der naechste
    Aufruf setzt hinter der letzten vollstaendigen Kerze an.
    """
    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    market = BybitMarketData(settings.bybit)

    start = _parse_date(von)
    end = _parse_date(bis) if bis else datetime.now(UTC)
    selected = [Interval(code) for code in intervalle] if intervalle else DEFAULT_INTERVALS

    total_requests = sum(estimate_requests(i, start, end) for i in selected)
    console.print(
        f"[bold]Backfill[/] {settings.bybit.symbol} "
        f"{start:%Y-%m-%d} bis {end:%Y-%m-%d}\n"
        f"Zeitreihen: {', '.join(i.label for i in selected)}\n"
        f"Geschaetzt ~{total_requests} Anfragen, "
        f"~{total_requests / 8 / 60:.0f} Minuten\n"
    )

    backfiller = Backfiller(market, store, rate_limiter=RateLimiter(8.0))

    def show(progress: BackfillProgress) -> None:
        if progress.requests % 25 == 0:
            console.print(f"  [dim]{progress.describe()}[/]")

    results = backfiller.run_many(
        settings.bybit.symbol,
        selected,
        start=start,
        end=end,
        resume=not neu,
        on_progress=show,
    )

    table = Table(title="Backfill abgeschlossen", header_style="bold")
    table.add_column("Zeitreihe")
    table.add_column("Neue Kerzen", justify="right")
    table.add_column("Anfragen", justify="right")
    table.add_column("Dauer", justify="right")
    for interval, progress in results.items():
        table.add_row(
            interval.label,
            f"{progress.candles_written:,}".replace(",", "."),
            str(progress.requests),
            f"{progress.elapsed.total_seconds():.0f}s",
        )
    console.print(table)
    console.print("\n[dim]Naechster Schritt: python -m cli quality[/]")


@app.command()
def status() -> None:
    """Was liegt im Datenspeicher?"""
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    series = store.series()

    if not series:
        console.print("[yellow]Speicher ist leer.[/] Starten mit: python -m cli backfill")
        raise typer.Exit(1)

    table = Table(title="Datenspeicher", header_style="bold")
    table.add_column("Symbol")
    table.add_column("Intervall")
    table.add_column("Kerzen", justify="right")
    table.add_column("Von")
    table.add_column("Bis")
    table.add_column("Alter", justify="right")

    now = datetime.now(UTC)
    for symbol, interval in series:
        coverage = store.coverage(symbol, interval)
        if coverage.is_empty or coverage.end is None or coverage.start is None:
            continue
        age = now - coverage.end
        age_text = f"{age.total_seconds() / 3600:.1f} h"
        style = "red" if age > interval.duration * 3 else ""
        table.add_row(
            symbol,
            interval.label,
            f"{coverage.rows:,}".replace(",", "."),
            f"{coverage.start:%Y-%m-%d}",
            f"{coverage.end:%Y-%m-%d %H:%M}",
            f"[{style}]{age_text}[/]" if style else age_text,
        )

    console.print(table)
    console.print(f"[dim]Belegter Speicher: {store.size_on_disk() / 1e6:.1f} MB[/]")


@app.command()
def quality(
    intervalle: list[str] = typer.Option(None, "--intervall", "-i"),
) -> None:
    """Datenqualitaet pruefen: Luecken, Duplikate, Sortierung, Ausreisser.

    Beendet mit Code 2, wenn eine Zeitreihe nicht backtestfaehig ist.
    """
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    selected = [Interval(c) for c in intervalle] if intervalle else None

    series = [
        (sym, iv)
        for sym, iv in store.series()
        if selected is None or iv in selected
    ]
    if not series:
        console.print("[yellow]Keine Daten zum Pruefen.[/]")
        raise typer.Exit(1)

    worst = Severity.INFO
    for symbol, interval in series:
        frame = store.read(symbol, interval)
        report = check_candles(frame, symbol=symbol, interval=interval)

        colour = {
            Severity.INFO: "green",
            Severity.WARN: "yellow",
            Severity.ERROR: "red",
        }[report.worst_severity]
        console.print(f"\n[{colour}]{report.summary()}[/]")

        for finding in report.findings:
            marker = {
                Severity.INFO: "[dim]i[/]",
                Severity.WARN: "[yellow]![/]",
                Severity.ERROR: "[red]x[/]",
            }[finding.severity]
            console.print(f"  {marker} {finding.message}")

        if report.worst_severity is Severity.ERROR:
            worst = Severity.ERROR
        elif report.worst_severity is Severity.WARN and worst is not Severity.ERROR:
            worst = Severity.WARN

    if worst is Severity.ERROR:
        console.print("\n[red]Mindestens eine Zeitreihe ist nicht backtestfaehig.[/]")
        raise typer.Exit(2)
    console.print("\n[green]Daten sind brauchbar.[/]")


@app.command()
def ingest(
    intervalle: list[str] = typer.Option(None, "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Live-Kerzen mitschreiben (Websocket).

    Speichert ausschliesslich **bestaetigte** Kerzen. Nach einem Verbindungs-
    abbruch werden fehlende Kerzen ueber REST nachgeladen; ist die Luecke aelter
    als sechs Stunden, wird gewarnt und ein Backfill empfohlen.

    Beenden mit Strg-C.
    """
    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    market = BybitMarketData(settings.bybit)
    selected = [Interval(c) for c in intervalle] if intervalle else [Interval.M15, Interval.H1]

    filler = GapFiller(market=market, store=store, symbol=settings.bybit.symbol)

    async def on_candle(candle: Candle, interval: Interval) -> None:
        store.write(settings.bybit.symbol, interval, [candle])
        console.print(
            f"[dim]{candle.open_time:%H:%M}[/] {interval.label} "
            f"Schluss [bold]{candle.close}[/] Vol {candle.volume}"
        )

    stream = KlineStream(settings.bybit, selected, on_candle=on_candle)

    async def main() -> None:
        # Vor dem Start: schliessen, was seit dem letzten Lauf fehlt.
        for interval in selected:
            last = store.last_candle_time(settings.bybit.symbol, interval)
            if last is not None:
                result = filler.fill(interval, since=last + interval.duration)
                if result.truncated:
                    console.print(
                        f"[yellow]Luecke in {interval.label} ist aelter als 6 Stunden "
                        f"und wurde nicht vollstaendig geschlossen.[/]\n"
                        f"[yellow]Vor dem Handeln ausfuehren: "
                        f"python -m cli backfill --von {result.requested_from:%Y-%m-%d}[/]"
                    )
                elif result.written:
                    console.print(
                        f"[dim]{interval.label}: {result.written} Kerzen nachgeladen[/]"
                    )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stream.stop)

        console.print(
            f"[bold]Live-Ingest[/] {settings.bybit.symbol} "
            f"({', '.join(i.label for i in selected)})\n"
            f"[dim]{stream.url} - Strg-C zum Beenden[/]\n"
        )
        await stream.run()

        console.print(
            f"\n[dim]Beendet. {stream.stats.confirmed_candles} bestaetigte Kerzen, "
            f"{stream.stats.reconnects} Reconnects.[/]"
        )

    asyncio.run(main())


@app.command()
def trade(
    strategie: str = typer.Option(
        None, "--strategie", "-s", help="Genom-Datei. Standard: <strategies>/champion.json"
    ),
    intervall: str = typer.Option("15", "--intervall", "-i", help="Handelsintervall."),
    markt: str = typer.Option("perpetual", help="perpetual oder spot."),
    echtgeld: bool = typer.Option(
        False, "--echtgeld", help="Pflichtangabe auf Mainnet. Ohne sie wird abgebrochen."
    ),
    trocken: bool = typer.Option(
        False, "--trocken", help="Alles pruefen und den Plan zeigen, aber nicht handeln."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Handeln. Der Befehl, um den es die ganze Zeit ging.

    Ablauf je abgeschlossener Kerze: Strategie fragen, Risk-Officer fragen,
    Order platzieren, Stop an die Position haengen, Ziele setzen. Kein LLM in
    dieser Schleife - es laeuft derselbe deterministische Code wie im Backtest.

    Vor dem ersten Lauf: ``python -m cli healthcheck``, dann ``backfill``,
    dann ``quality``. Und dann 30 Tage Demo, bevor echtes Geld hineingeht.

    Beenden mit Strg-C. Offene Positionen bleiben dabei bestehen - ihr Stop
    liegt an der Boerse und wirkt weiter, auch wenn dieser Prozess nicht laeuft.
    """
    import json
    from pathlib import Path

    from data.bybit.adapter import BybitAccount
    from data.bybit.errors import BybitAuthError, BybitError, BybitGeoBlockedError
    from data.bybit.trading import BybitTrading
    from execution.live import LiveTrader, telegram_notifier
    from execution.risk import RiskOfficer, TradingState, load_risk_state
    from execution.router import MarketKind
    from strategy.compiler import compile_genome
    from strategy.genome import Genome

    _configure_logging(verbose)
    settings = get_settings()

    # -- 1. Echtgeld-Sperre --------------------------------------------------
    # Ein Tippfehler in der Umgebungsvariablen darf nicht dazu fuehren, dass
    # versehentlich mit echtem Geld gehandelt wird. Die Bestaetigung muss auf
    # der Kommandozeile stehen, nicht in einer Datei.
    if settings.bybit.environment.is_real_money and not echtgeld:
        console.print(
            "[red]Umgebung ist MAINNET - hier liegt echtes Geld.[/]\n"
            "Wenn das gewollt ist, ausdruecklich bestaetigen:\n"
            "  [bold]python -m cli trade --echtgeld[/]"
        )
        raise typer.Exit(2)

    try:
        market_kind = MarketKind(markt)
    except ValueError as exc:
        raise typer.BadParameter("markt muss 'perpetual' oder 'spot' sein") from exc

    # -- 2. Strategie laden --------------------------------------------------
    path = Path(strategie) if strategie else Path(settings.paths.strategies) / "champion.json"
    if not path.exists():
        console.print(
            f"[red]Keine Strategie unter {path}.[/]\n"
            "Es wird nur gehandelt, was die Zulassungs-Gates bestanden hat - "
            "ohne zugelassenes Genom gibt es nichts zu handeln."
        )
        raise typer.Exit(2)

    genome = Genome.model_validate(json.loads(path.read_text()))
    strategy = compile_genome(genome)

    # -- 3. Kill-Switch ------------------------------------------------------
    # Vor jeder Verbindung: Ein abgeschaltetes System soll sich nicht erst
    # noch bei der Boerse anmelden.
    state_path = Path(settings.paths.state) / "risk.json"
    persisted = load_risk_state(state_path)
    if persisted.trading_state is TradingState.KILLED:
        console.print(
            f"[red]Kill-Switch ist aktiv:[/] {persisted.kill_reason}\n"
            "Erst nachsehen, was passiert ist. Zuruecksetzen danach im Dashboard "
            "oder ueber reset_kill_switch()."
        )
        raise typer.Exit(2)

    # -- 4. Boersenanbindung -------------------------------------------------
    store = CandleStore(settings.paths.data_store)
    market = BybitMarketData(settings.bybit)
    account = BybitAccount(settings.bybit)
    gateway = BybitTrading(settings.bybit)
    interval_obj = Interval(intervall)

    # Der erste Kontakt zur Boerse. Hier scheitert es, wenn die IP nicht auf
    # der Whitelist steht oder der Host in einer gesperrten Region laeuft -
    # die beiden haeufigsten Probleme beim ersten Start auf einem neuen Server.
    try:
        instrument = market.get_instrument(settings.bybit.symbol)
        equity = account.get_wallet_balance("USDT").equity
        positions = account.get_positions(settings.bybit.symbol)
    except BybitGeoBlockedError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(2) from exc
    except BybitAuthError as exc:
        console.print(
            f"[red]Anmeldung abgelehnt:[/] {exc}\n"
            "Haeufigste Ursache: Die IP dieses Servers steht nicht auf der "
            "Whitelist des API-Keys.\n"
            "Pruefen mit: python -m cli healthcheck"
        )
        raise typer.Exit(2) from exc
    except BybitError as exc:
        console.print(f"[red]Boerse nicht erreichbar:[/] {exc}")
        raise typer.Exit(2) from exc

    officer = RiskOfficer(settings.risk, instrument, state_path=state_path)

    last = store.last_candle_time(settings.bybit.symbol, interval_obj)
    if last is None:
        console.print(
            f"[red]Keine Kerzen fuer {interval_obj.label} im Speicher.[/]\n"
            "Zuerst: python -m cli backfill"
        )
        raise typer.Exit(2)

    age = datetime.now(UTC) - last
    if age > interval_obj.duration * 3:
        # Ein kalter Puffer bedeutet: Die Indikatoren rechnen ueber eine Luecke
        # hinweg. Das ist kein Fehler des Roboters, sieht aber wie einer aus.
        console.print(
            f"[yellow]Letzte Kerze ist {age.total_seconds() / 3600:.1f} h alt.[/] "
            "Vor dem Handeln nachladen: python -m cli backfill"
        )

    console.print(
        f"\n[bold]Handelsplan[/]\n"
        f"  Umgebung     {settings.bybit.environment.value}"
        f"{'  [red](ECHTES GELD)[/]' if settings.bybit.environment.is_real_money else ''}\n"
        f"  Markt        {market_kind.value}"
        f"{'' if market_kind.supports_leverage else '  (kein Hebel, keine Shorts)'}\n"
        f"  Symbol       {instrument.symbol} {interval_obj.label}\n"
        f"  Strategie    {genome.name}  [dim]({strategy.strategy_id})[/]\n"
        f"  Vorlauf      {strategy.warmup_bars} Kerzen\n"
        f"  Kapital      {equity:.2f} USDT\n"
        f"  Risiko       {settings.risk.risk_per_trade_pct} % "
        f"(= {equity * settings.risk.risk_per_trade_pct / 100:.2f} USDT je Trade)\n"
        f"  Hebel max.   {settings.risk.max_leverage}x\n"
        f"  Kill-Switch  {settings.risk.max_drawdown_pct} % Drawdown\n"
        f"  Offen        {len(positions)} Position(en)\n"
    )

    if trocken:
        console.print(
            "[green]Trockenlauf - es wurde keine Order platziert.[/]\n"
            "[dim]Ohne --trocken beginnt der Handel.[/]"
        )
        return

    # -- 5. Handeln ----------------------------------------------------------
    async def main() -> None:
        notifier = None
        if settings.notify.telegram_enabled:
            notifier = await telegram_notifier(
                settings.notify.telegram_bot_token.get_secret_value(),
                settings.notify.telegram_chat_id,
            )

        trader = LiveTrader(
            settings=settings.bybit,
            strategy=strategy,
            instrument=instrument,
            risk_settings=settings.risk,
            market=market,
            account=account,
            gateway=gateway,
            officer=officer,
            store=store,
            interval=interval_obj,
            market_kind=market_kind,
            notifier=notifier,
        )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, trader.stop)

        console.print("[dim]Strg-C beendet die Schleife. Offene Stops bleiben bestehen.[/]\n")
        await trader.start()

        console.print(f"\n[dim]Beendet. {trader.stats.describe()}[/]")
        if trader.bracket is not None and trader.bracket.is_open:
            console.print(
                f"[yellow]Achtung: {trader.bracket.describe()}[/]\n"
                "[yellow]Die Position laeuft weiter. Ihr Stop liegt an der Boerse.[/]"
            )

    asyncio.run(main())


@app.command()
def leverage(
    kapital: float = typer.Option(500.0, help="Kontogroesse in EUR."),
    preis: float = typer.Option(100000.0, help="BTC-Preis."),
) -> None:
    """Zeigt, welcher Hebel sich bei welcher Stop-Distanz ergibt.

    Macht die zentrale Identitaet sichtbar: Hebel = Risiko% / Stop%.
    """
    from decimal import Decimal

    from execution.sizing import leverage_for_stop

    settings = get_settings()
    risk = settings.risk
    equity = Decimal(str(kapital))
    entry = Decimal(str(preis))

    table = Table(
        title=f"Hebel bei {equity} EUR Kapital, {risk.risk_per_trade_pct} % Risiko "
        f"(= {equity * risk.risk_per_trade_pct / 100:.2f} EUR je Trade)",
        header_style="bold",
    )
    table.add_column("Stop-Distanz", justify="right")
    table.add_column("Hebel", justify="right")
    table.add_column("Nominalwert", justify="right")
    table.add_column("Menge BTC", justify="right")
    table.add_column("Hinweis")

    for stop_pct in ["0.2", "0.3", "0.5", "0.8", "1.0", "1.5", "2.0", "3.0"]:
        lev = leverage_for_stop(
            equity=equity,
            entry_price=entry,
            stop_distance_pct=Decimal(stop_pct),
            risk_per_trade_pct=risk.risk_per_trade_pct,
        )
        notional = equity * lev
        qty = notional / entry
        note = ""
        style = ""
        if lev > risk.max_leverage:
            note = f"ueber Deckel {risk.max_leverage}x - wird verkleinert"
            style = "yellow"
        elif qty < Decimal("0.001"):
            note = "unter Mindestmenge 0.001 - nicht handelbar"
            style = "red"
        table.add_row(
            f"{stop_pct} %",
            f"[{style}]{lev}x[/]" if style else f"{lev}x",
            f"{notional:.0f}",
            f"{qty:.4f}",
            f"[{style}]{note}[/]" if style else note,
        )

    console.print(table)
    console.print(
        "\n[dim]Das riskierte Geld ist in jeder Zeile identisch. Der Hebel steigt, "
        "weil der Stop enger wird - nicht weil mehr riskiert wird.[/]"
    )


if __name__ == "__main__":
    app()
