"""Kommandozeile des Handelssystems.

    python -m cli --help

    python -m cli healthcheck              # zuerst ausfuehren auf neuem Server
    python -m cli backfill --von 2020-03-30
    python -m cli funding                  # zweite Datenquelle: Positionierung
    python -m cli status
    python -m cli quality
    python -m cli research                 # Strategien pruefen
    python -m cli ingest                   # Live-Kerzen mitschreiben
    python -m cli trade --trocken          # Handelsplan pruefen, ohne zu handeln
    python -m cli trade                    # handeln
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from datetime import UTC, datetime
from pathlib import Path

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


def _install_stop_handler(stop) -> None:
    """Strg-C sauber behandeln - auf allen Systemen.

    ``loop.add_signal_handler`` gibt es unter Windows nicht; dort wirft es
    NotImplementedError. Ohne diese Fallunterscheidung stuerzt jeder
    Dauerbefehl auf einem Windows-Rechner sofort beim Start ab - und zwar mit
    einer Meldung, die nichts mit dem Handel zu tun hat.

    Der Rueckfallweg ueber ``signal.signal`` deckt unter Windows das ab, was
    dort ueberhaupt geht: Strg-C.
    """
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop)
        except (NotImplementedError, AttributeError, ValueError):
            # Windows, oder ein Signal, das es hier nicht gibt.
            with contextlib.suppress(ValueError, OSError, AttributeError):
                signal.signal(sig, lambda *_: stop())


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
def termine(
    von: int = typer.Option(2012, "--von", help="Erstes Jahr der FOMC-Historie"),
    bis: int = typer.Option(0, "--bis", help="Letztes Jahr (0 = aktuelles)"),
) -> None:
    """Termin-Overlay holen: Fed-Entscheidungen und Bitcoin-Halbierungen.

    Laeuft **nicht** im Handel mit - der Kalender wird einmal geholt und liegt
    danach als Datei vor. Ein Handelssystem, das vor jeder Order eine fremde
    Webseite fragt, faellt genau dann aus, wenn es hektisch wird.

    Quellen: federalreserve.gov (Entscheidungen, inklusive der
    ausserplanmaessigen) und mempool.space (Blockzeit der Halbierungen).
    CPI-Termine fehlen: bls.gov antwortet dem Entwicklungscontainer mit 403.
    Von einem normalen Anschluss aus ist die Seite erreichbar - dort laesst
    sich die Luecke schliessen.
    """
    import httpx

    from data.termine import hole_termine

    settings = get_settings()
    ziel = Path(settings.paths.referenz) / "termine.json"

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        def text(url: str) -> str:
            antwort = client.get(url)
            antwort.raise_for_status()
            return antwort.text

        def js(url: str):
            antwort = client.get(url)
            antwort.raise_for_status()
            return antwort.json()

        kalender = hole_termine(text, js, von_jahr=von, bis_jahr=bis or None)

    if not kalender:
        console.print("[red]Keine Termine geholt.[/red] Quellen nicht erreichbar?")
        raise typer.Exit(1)

    kalender.speichern(ziel)
    console.print(f"[green]{kalender.bericht()}[/green]")
    console.print(f"Gespeichert in {ziel}")

    naechster = kalender.naechster(datetime.now(UTC))
    if naechster is not None:
        console.print(
            f"Naechster Termin: {naechster.beschreibung} am "
            f"{naechster.zeitpunkt:%Y-%m-%d %H:%M} UTC"
        )


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

    # Deckt der Speicher wirklich den angeforderten Zeitraum ab?
    #
    # Ein Backfill kann fehlerfrei durchlaufen und trotzdem fast nichts
    # geliefert haben - dann steht in der Tabelle "999 Kerzen, 1 Anfrage,
    # fertig" und alles sieht gut aus. Genau so geschehen, als die Kerzen
    # versehentlich vom Demo-Host kamen: Der ignoriert den Startzeitpunkt und
    # gibt nur die juengsten rund 1000 Stueck zurueck.
    #
    # Ein Walk-Forward auf zehn Tagen Historie ist wertlos. Diese Pruefung
    # kostet nichts und faengt jede Variante des Problems ab, auch kuenftige.
    requested_days = max(1, (end - start).days)
    for interval in selected:
        coverage = store.coverage(settings.bybit.symbol, interval)
        if coverage.is_empty or coverage.start is None or coverage.end is None:
            console.print(f"[red]{interval.label}: nichts im Speicher.[/]")
            continue
        covered_days = max(1, (coverage.end - coverage.start).days)
        if covered_days < requested_days * 0.5:
            console.print(
                f"[red]{interval.label}: nur {covered_days} von "
                f"{requested_days} angeforderten Tagen im Speicher[/] "
                f"({coverage.start:%Y-%m-%d} bis {coverage.end:%Y-%m-%d}).\n"
                "[yellow]Der Backfill lief durch, hat aber kaum Daten geholt. "
                "Ein Walk-Forward darauf waere wertlos.[/]"
            )

    console.print("\n[dim]Naechster Schritt: python -m cli quality[/]")


@app.command()
def funding(
    von: str = typer.Option("2020-03-30", help="Startdatum (YYYY-MM-DD)."),
    bis: str | None = typer.Option(None, help="Enddatum. Standard: jetzt."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Funding-Historie nachladen - die zweite Datenquelle.

    Alle acht Stunden zahlt eine Seite der anderen. Diese Zahlen sagen etwas
    ueber die **Positionierung** aus, nicht ueber den Kursverlauf, und es gibt
    sie nur bei Perpetuals. Die Strategien der vierten Generation stehen und
    fallen damit; ohne diesen Befehl liefern ihre Indikatoren nur NaN, und sie
    handeln schlicht nicht.

    Klein und schnell: Drei Werte am Tag ergeben ueber sechs Jahre rund 6.500
    Zeilen, das sind gut 30 Anfragen.
    """
    from data.funding import FundingStore, backfill_funding

    _configure_logging(verbose)
    settings = get_settings()
    store = FundingStore(settings.paths.data_store)
    market = BybitMarketData(settings.bybit)

    start = _parse_date(von)
    end = _parse_date(bis) if bis else datetime.now(UTC)

    console.print(
        f"[bold]Funding-Historie[/] {settings.bybit.symbol} "
        f"{start:%Y-%m-%d} bis {end:%Y-%m-%d}\n"
    )

    def show(written: int, cursor: datetime) -> None:
        console.print(f"  [dim]{written:,} Eintraege, bis {cursor:%Y-%m-%d}[/]".replace(",", "."))

    written = backfill_funding(
        market, store, settings.bybit.symbol, start=start, end=end, on_progress=show
    )

    frame = store.read(settings.bybit.symbol)
    if frame.empty:
        console.print(
            "[red]Nichts geladen.[/] Ohne Funding-Daten handeln die Strategien "
            "der vierten Generation nicht.\n"
            "[dim]Pruefen: python -m cli healthcheck[/]"
        )
        raise typer.Exit(2)

    first = frame["time"].iloc[0]
    last = frame["time"].iloc[-1]
    positive = float((frame["funding_rate"] > 0).mean())

    table = Table(title="Funding-Historie", header_style="bold")
    table.add_column("Kennzahl")
    table.add_column("Wert", justify="right")
    table.add_row("Neue Eintraege", f"{written:,}".replace(",", "."))
    table.add_row("Gesamt", f"{len(frame):,}".replace(",", "."))
    table.add_row("Von", f"{first:%Y-%m-%d}")
    table.add_row("Bis", f"{last:%Y-%m-%d %H:%M}")
    table.add_row("Anteil positiv", f"{positive:.1%}")
    table.add_row("Durchschnitt", f"{frame['funding_rate'].mean():.5%}")
    console.print(table)

    # Ein Anteil weit ueber 50 % ist der Normalfall und zugleich die
    # Grundannahme der vierten Generation: Die Long-Seite zahlt meistens.
    console.print(
        f"\n[dim]Die Long-Seite zahlte in {positive:.0%} aller Perioden. "
        "Genau daran setzen die Carry-Kandidaten an.[/]"
    )
    console.print("[dim]Naechster Schritt: python -m cli research --schnell[/]")


@app.command()
def wettbewerb(
    intervall: str = typer.Option("15", "--intervall", "-i", help="Handelsintervall."),
    symbol: str | None = typer.Option(
        None, "--symbol",
        help="Abweichendes Symbol, z.B. BTCUSD_BITSTAMP fuer Referenzkerzen.",
    ),
    generation: int = typer.Option(
        8, "--generation", "-g",
        help="Startkatalog. 7 = Scalp-Setups, 8 = Abfolge-Modell und Short-Seite."
    ),
    runden: int = typer.Option(
        0, help="Anzahl Runden. 0 = Dauerlauf bis Strg-C oder bis einer besteht."
    ),
    varianten: int = typer.Option(
        8, help="Wie viele Varianten je Runde aus den Besten gebildet werden."
    ),
    schnell: bool = typer.Option(
        True, "--schnell/--vollstaendig",
        help="Vorauswahl mit 7 Gates. Die Zulassung laeuft am Ende mit allen.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Dauerlauf: Strategien pruefen, Beste abwandeln, wiederholen.

    Runde 1 prueft den Katalog. Jede weitere Runde bildet Varianten aus den
    Kandidaten, die am weitesten kamen, und prueft die. Alles landet in der
    Bestenliste und ist auf der Website sichtbar - Platz 1 bis Ende, mit dem
    Grund des Scheiterns.

    Beendet wird durch Strg-C, durch ``--runden``, oder wenn ein Kandidat alle
    Gates besteht.

    **Was ein Dauerlauf nicht kann.** Er findet nicht durch Ausdauer eine
    profitable Strategie. Wer lange genug sucht, findet immer etwas, das im
    Rueckblick gut aussieht - genau dagegen ist die Deflated Sharpe Ratio
    gebaut. Sie zaehlt jeden Versuch mit und hebt die Huerde entsprechend.
    Nach tausend Varianten muss ein Kandidat deutlich besser sein als nach
    zehn, um dieselbe Zulassung zu bekommen. Das ist der Preis des Suchens,
    und er ist hier sichtbar statt versteckt.
    """
    from decimal import Decimal
    from pathlib import Path

    from backtest.engine import BacktestConfig
    from data.bybit.errors import BybitError
    from data.funding import FundingStore, attach_funding
    from research.admission import load_trials, run_admission, save_trials, write_champion
    from research.leaderboard import Leaderboard
    from research.mutation import breed
    from research.seeds import load_seeds
    from research.tradelog import build_log

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)

    handelssymbol = symbol or settings.bybit.symbol
    frame = store.read(handelssymbol, interval_obj)
    if frame.empty:
        console.print(
            f"[red]Keine Kerzen fuer {handelssymbol} {interval_obj.label}.[/] "
            f"Zuerst: python -m cli backfill --intervall {intervall}"
        )
        raise typer.Exit(2)

    # Reicht die Historie fuer ueberhaupt ein Testfenster?
    #
    # Ohne diese Pruefung laeuft der Wettbewerb fehlerfrei durch, erzeugt
    # Runde um Runde Varianten und traegt sie in die Bestenliste ein - mit
    # null Trades bei jedem einzelnen. Genau so geschehen: 416 Tage Historie
    # ergeben bei 12 Monaten Training und 3 Monaten Test **kein** Fenster, und
    # die Rangliste sah trotzdem gefuellt aus.
    #
    # Der ``research``-Befehl hatte diese Schranke von Anfang an. Sie hier zu
    # vergessen, hat drei Runden Rechenzeit in eine Tabelle gesteckt, die
    # nichts bedeutete.
    span_days = (frame["open_time"].iloc[-1] - frame["open_time"].iloc[0]).days
    if span_days < 450:
        console.print(
            f"[red]Nur {span_days} Tage Historie.[/] Der Walk-Forward braucht "
            "mindestens rund 15 Monate, sonst entsteht kein einziges "
            "Testfenster - und jede Bestenliste daraus waere leer, ohne dass "
            "es auffiele.\n"
            f"Mehr laden: python -m cli backfill --intervall {intervall} "
            "--von 2020-03-30"
        )
        raise typer.Exit(2)

    funding_frame = FundingStore(settings.paths.data_store).read(handelssymbol)
    frame = attach_funding(frame, funding_frame)
    sub_frame = store.read(handelssymbol, Interval.M1)
    if sub_frame.empty:
        sub_frame = None

    try:
        instrument = BybitMarketData(settings.bybit).get_instrument(settings.bybit.symbol)
    except BybitError:
        instrument = _fallback_instrument(settings.bybit.symbol)

    config = BacktestConfig(
        instrument=instrument,
        risk=settings.risk,
        initial_equity=Decimal("500"),
        kalender=_terminkalender(settings) or None,
    )

    state = Path(settings.paths.state)
    board = Leaderboard(state / "leaderboard.json")
    trials_path = state / "trials.json"

    console.print(
        f"\n[bold]Wettbewerb[/] {handelssymbol} {interval_obj.label}\n"
        f"  Historie   {frame['open_time'].iloc[0]:%Y-%m-%d} bis "
        f"{frame['open_time'].iloc[-1]:%Y-%m-%d}\n"
        f"  Bisher     {board.summary()}\n"
        f"  Ende       {'nach ' + str(runden) + ' Runden' if runden else 'Strg-C'}\n"
    )

    runde = 0
    aktuell = load_seeds(generation)
    herkunft = "Katalog"

    try:
        while runden == 0 or runde < runden:
            runde += 1
            trials_before = load_trials(trials_path)
            console.print(
                f"[bold]Runde {runde}[/] - {len(aktuell)} Kandidaten "
                f"({herkunft}), {trials_before} Versuche bisher"
            )

            report = run_admission(
                aktuell,
                frame,
                config,
                trials_so_far=trials_before,
                sub_frame=sub_frame,
                run_expensive=not schnell,
            )
            save_trials(trials_path, report.trials_after)
            board.record(report.candidates, generation=generation, herkunft=herkunft)
            board.save()

            # Von den Besten die einzelnen Trades mitschreiben.
            #
            # Die Kennzahlen sagen nicht, was eine Strategie eigentlich getan
            # hat: Ausgeglichene Erwartung kann viele kleine Gewinne mit
            # wenigen grossen Verlusten heissen - oder genau umgekehrt.
            # Dieselbe Zahl, gegensaetzliche Erfahrung damit.
            spitzen_ids = {e.genome_id for e in board.best(3)}
            for kandidat in report.candidates:
                if kandidat.genome.genome_id in spitzen_ids:
                    _schreibe_tradelog(state, build_log(kandidat))

            _zeige_bestenliste(board, limit=10)
            _send_report(
                settings,
                _wettbewerbs_bericht(board, runde, interval_obj, handelssymbol),
            )

            if report.champion is not None:
                console.print(
                    f"\n[green]Ein Kandidat hat alle Gates bestanden: "
                    f"{report.champion.genome.name}[/]"
                )
                write_champion(
                    report.champion, Path(settings.paths.strategies) / "champion.json"
                )
                console.print("[dim]Naechster Schritt: python -m cli trade --trocken[/]")
                break

            # Weiter mit Varianten der Besten. Nur aus denen, die schon nahe
            # dran waren - wild zu streuen kostet Versuche und bringt nichts.
            spitze = board.best(5)
            ids = {e.genome_id for e in spitze}
            basis = [c.genome for c in report.candidates if c.genome.genome_id in ids]
            if not basis:
                basis = [c.genome for c in report.candidates[:3]]

            aktuell = breed(basis, varianten, seed=runde)
            herkunft = "Variante"
            if not aktuell:
                console.print("[yellow]Keine neuen Varianten mehr moeglich.[/]")
                break

    except KeyboardInterrupt:
        console.print("\n[dim]Abgebrochen. Die Bestenliste ist gespeichert.[/]")

    board.save()
    console.print(f"\n[bold]{board.summary()}[/]")
    console.print(f"[dim]Bestenliste: {board.path}[/]")


def _schreibe_tradelog(state, log) -> None:
    """Trades und Kapitalkurve eines Kandidaten ablegen.

    Je Genom eine Datei. Ein neuer, besserer Lauf ueberschreibt sie - anders
    als die Bestenliste, die das jeweils beste Ergebnis behaelt: Hier geht es
    um Anschauung, und der juengste Lauf ist der anschaulichste.
    """
    import json as _json
    from dataclasses import asdict as _asdict

    ordner = state / "trades"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{log.genome_id}.json").write_text(
        _json.dumps(_asdict(log), indent=2, ensure_ascii=False, default=str)
    )


def _zeige_bestenliste(board, *, limit: int = 10) -> None:
    table = Table(title="Bestenliste", header_style="bold")
    table.add_column("#", justify="right")
    table.add_column("Strategie")
    table.add_column("Gates", justify="right")
    table.add_column("Trades", justify="right")
    table.add_column("Erwartung", justify="right")
    table.add_column("Gescheitert an")

    for platz, eintrag in enumerate(board.best(limit), start=1):
        stil = "green" if eintrag.zugelassen else ""
        table.add_row(
            str(platz),
            f"[{stil}]{eintrag.name[:38]}[/]" if stil else eintrag.name[:38],
            f"{eintrag.gates_bestanden}/{eintrag.gates_gesamt}",
            str(eintrag.trades),
            f"{eintrag.erwartung_r:+.3f} R",
            ", ".join(eintrag.gescheitert_an[:2]) or "-",
        )
    console.print(table)


def _wettbewerbs_bericht(board, runde: int, interval_obj, symbol: str) -> dict:
    """Der Bericht eines Wettbewerbslaufs.

    Die Abschnitte ``lauf`` und ``markt`` heissen genauso wie beim
    Zulassungsbericht - nicht aus Bequemlichkeit, sondern weil ``_send_report``
    daraus die Commit-Nachricht baut. Beim ersten Entwurf hiessen sie anders,
    und in der Historie standen zwei Commits mit dem Text
    "0 Kandidaten, 0 zugelassen (? ?)".
    """
    from dataclasses import asdict

    return {
        "art": "wettbewerb",
        "zeitpunkt": datetime.now(UTC).isoformat(),
        "runde": runde,
        "markt": {"symbol": symbol, "intervall": interval_obj.label},
        "lauf": {
            "kandidaten": len(board.entries),
            "zugelassen": len(board.admitted),
            "runde": runde,
            "laeufe": board.laeufe,
        },
        "zusammenfassung": board.summary(),
        "bestenliste": [asdict(e) for e in board.best(25)],
    }


@app.command()
def referenz(
    intervall: str = typer.Option("15", "--intervall", "-i", help="Bybit-Code."),
    symbol: str = typer.Option(
        "BTCUSD_BITSTAMP", "--symbol",
        help="Auch ETHUSD_BITSTAMP, LTCUSD_BITSTAMP, XRPUSD_BITSTAMP - "
        "ausschliesslich zur Gegenprobe, nicht zum Handeln.",
    ),
    von: str = typer.Option("2020-03-30", help="Startdatum (YYYY-MM-DD)."),
    bis: str | None = typer.Option(None, help="Enddatum. Standard: jetzt."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Referenzkerzen von Bitstamp laden - zum Forschen, nicht zum Handeln.

    Gedacht fuer Umgebungen, aus denen Bybit nicht erreichbar ist. Die Kerzen
    landen unter einem **eigenen Symbol** im Speicher und vermischen sich nicht
    mit den Handelsdaten.

    Was sie sind und was nicht: Bitstamp BTC/USD ist ein Kassamarkt. Es gibt
    dort **keine Funding-Zahlungen**, die Liquiditaet ist eine andere, und die
    Dochte weichen in schnellen Bewegungen ab. Fuer die Vorauswahl genuegt das -
    was auf Bitstamp nichts traegt, traegt auf Bybit auch nichts. Fuer die
    Zulassung gehoert die Pruefung auf die Daten der Boerse, auf der gehandelt
    wird.
    """
    from data.reference import (
        REFERENCE_SYMBOL,
        BitstampReference,
        backfill_reference,
        estimate_pages,
    )

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)

    start = _parse_date(von)
    end = _parse_date(bis) if bis else datetime.now(UTC)
    seiten = estimate_pages(interval_obj, start, end)

    console.print(
        f"[bold]Referenzkerzen[/] Bitstamp BTC/USD {interval_obj.label}\n"
        f"  {start:%Y-%m-%d} bis {end:%Y-%m-%d}, geschaetzt ~{seiten} Anfragen "
        f"(~{seiten * 0.4 / 60:.0f} Minuten)\n"
        f"[dim]Symbol im Speicher: {symbol} - getrennt von den "
        f"Handelsdaten.[/]\n"
    )

    def zeige(geschrieben: int, cursor: datetime) -> None:
        if geschrieben % 20000 < PAGE_MELDUNG:
            console.print(f"  [dim]{geschrieben:,} Kerzen, bis {cursor:%Y-%m-%d}[/]".replace(",", "."))

    geschrieben = backfill_reference(
        BitstampReference(), store, interval_obj,
        start=start, end=end, on_progress=zeige, symbol=symbol,
    )

    coverage = store.coverage(symbol, interval_obj)
    if coverage.is_empty:
        console.print("[red]Nichts geladen.[/]")
        raise typer.Exit(2)

    table = Table(title="Referenzkerzen", header_style="bold")
    table.add_column("Kennzahl")
    table.add_column("Wert", justify="right")
    table.add_row("Neu", f"{geschrieben:,}".replace(",", "."))
    table.add_row("Gesamt", f"{coverage.rows:,}".replace(",", "."))
    table.add_row("Von", f"{coverage.start:%Y-%m-%d}")
    table.add_row("Bis", f"{coverage.end:%Y-%m-%d %H:%M}")
    console.print(table)
    console.print(
        f"\n[dim]Naechster Schritt: python -m cli wettbewerb "
        f"--symbol {REFERENCE_SYMBOL} -i {intervall}[/]"
    )


#: Wie oft der Fortschritt gemeldet wird - alle rund 20.000 Kerzen.
PAGE_MELDUNG = 1000


@app.command()
def kosten(
    rr: float = typer.Option(1.5, help="Chance-Risiko-Verhaeltnis der Ziele."),
) -> None:
    """Was Gebuehren kosten - in R, nicht in Prozent.

    Die Umrechnung, an der schnelles Handeln haengt: Gebuehren zaehlen als
    Anteil am **Risiko** eines Trades, und der Umrechnungsfaktor ist die
    Stop-Distanz. Derselbe Gebuehrensatz kostet bei 0,2 % Stop das Fuenffache
    von dem, was er bei 1 % Stop kostet.

    Die Tabelle sagt, welche Trefferquote noetig ist, um bei der jeweiligen
    Stop-Distanz gerade eben nicht zu verlieren.
    """
    from backtest.costs import CostModel
    from research.costfloor import floor_table

    settings = get_settings()
    # Die Gebuehrensaetze stehen im Kostenmodell des Backtests, nicht in den
    # Einstellungen - dort geht es um das Budget der Research-KI. Beides
    # "Kosten" zu nennen war schon einmal verwirrend genug.
    costs = CostModel()

    table = Table(
        title=f"Kostenschwelle bei {rr:g}:1", header_style="bold"
    )
    table.add_column("Stop-Distanz", justify="right")
    table.add_column("noetige Trefferquote", justify="right")
    table.add_column("Gebuehren je Trade", justify="right")

    ohne_kosten = 1.0 / (rr + 1.0)
    for stop, quote, gebuehren, _ in floor_table(rr=rr, costs=costs):
        stil = "red" if quote > 0.5 else "yellow" if quote > 0.45 else "green"
        table.add_row(
            f"{stop:.2f} %",
            f"[{stil}]{quote:.1%}[/]",
            f"{gebuehren:.3f} R",
        )
    console.print(table)

    console.print(
        f"\nOhne Gebuehren waeren [bold]{ohne_kosten:.1%}[/] noetig.\n"
        f"[dim]Maker {float(costs.maker_fee_rate) * 100:.3f} %, "
        f"Taker {float(costs.taker_fee_rate) * 100:.3f} % - VIP0 bei Bybit.[/]\n"
    )
    console.print(
        "[dim]Der Hebel folgt daraus, er ist kein eigener Regler:\n"
        f"  Hebel = Risiko je Trade / Stop-Distanz = "
        f"{float(settings.risk.risk_per_trade_pct):g} % / Stop.\n"
        "Enger stellen heisst hoeher hebeln - dieselbe Entscheidung, zweimal "
        "ausgedrueckt.[/]"
    )


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
def research(
    intervall: str = typer.Option(
        "60",
        "--intervall",
        "-i",
        help="Handelsintervall. 60 = Stunde, die Zeitebene der zweiten Generation.",
    ),
    von: str | None = typer.Option(None, help="Startdatum der Auswertung (YYYY-MM-DD)."),
    schnell: bool = typer.Option(
        False,
        "--schnell",
        help="Die teuren Gates (Plateau, Kosten-Stress) ueberspringen. "
        "Nur zur Vorauswahl - fuer die Zulassung muessen sie laufen.",
    ),
    ki: bool = typer.Option(
        False,
        "--ki",
        help="Die Research-KI neue Kandidaten vorschlagen lassen, statt der "
        "Standardliste. Kostet Geld und braucht LLM__ANTHROPIC_API_KEY.",
    ),
    generation: int = typer.Option(
        5,
        "--generation",
        "-g",
        help="Welche Kandidatenliste. 5 = Halten (Tageskerzen), "
        "6 = schnelles Handeln mit Hebel (15-Minuten-Kerzen).",
    ),
    uebernehmen: bool = typer.Option(
        True, help="Den Champion nach champion.json schreiben."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Strategien pruefen und den Champion bestimmen.

    Jedes Genom laeuft durch Walk-Forward und die neun Zulassungs-Gates. Wer
    alle besteht, kommt in die Auswahl; der Bestaendigste wird Champion und
    landet in ``strategies/champion.json``. Nur der wird gehandelt.

    Braucht Daten im Speicher - vorher ``backfill`` und ``quality`` laufen
    lassen. Ein Durchlauf ueber sechs Jahre dauert je nach Kandidatenzahl
    einige Minuten.
    """
    from decimal import Decimal
    from pathlib import Path

    import pandas as pd

    from backtest.engine import BacktestConfig
    from data.bybit.errors import BybitError
    from data.funding import FundingStore, attach_funding
    from research.admission import (
        load_trials,
        report_payload,
        run_admission,
        save_trials,
        write_champion,
        write_journal,
    )
    from research.benchmark import buy_and_hold
    from research.seeds import load_seeds
    from strategy.genome import Genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)

    frame = store.read(
        settings.bybit.symbol, interval_obj, start=_parse_date(von) if von else None
    )
    if frame.empty:
        console.print(
            f"[red]Keine Kerzen fuer {interval_obj.label} im Speicher.[/]\n"
            "Zuerst: python -m cli backfill"
        )
        raise typer.Exit(2)

    span_days = (frame["open_time"].iloc[-1] - frame["open_time"].iloc[0]).days
    if span_days < 450:
        # 12 Monate Training + 3 Monate Test ergeben sonst kein einziges Fenster.
        console.print(
            f"[red]Nur {span_days} Tage Historie.[/] Der Walk-Forward braucht "
            "mindestens rund 15 Monate, sonst entsteht kein einziges Testfenster.\n"
            "Mehr laden: python -m cli backfill --von 2020-03-30"
        )
        raise typer.Exit(2)

    # Die zweite Datenquelle an die Kerzen schreiben.
    #
    # Fehlt sie, steht in der Spalte NaN, die Funding-Indikatoren geben NaN
    # zurueck, und die Kandidaten der vierten Generation handeln nicht ein
    # einziges Mal. Im Bericht saehe das aus wie ein Fehlschlag der Idee,
    # waere aber nur eine fehlende Datei - deshalb hier die deutliche
    # Warnung statt eines stillen Durchlaufs.
    funding_frame = FundingStore(settings.paths.data_store).read(settings.bybit.symbol)
    if funding_frame.empty:
        console.print(
            "[yellow]Keine Funding-Historie im Speicher.[/] Kandidaten, die "
            "darauf aufbauen, handeln nicht - das ist dann kein Urteil ueber "
            "die Idee, sondern eine fehlende Datei.\n"
            "[dim]Nachladen: python -m cli funding[/]\n"
        )
    else:
        # Nur melden, wenn wirklich etwas fehlt.
        #
        # Die erste Zahlung des Tages faellt um 08:00 an, die erste Kerze um
        # 00:00 - streng genommen sind das acht unbedeckte Stunden, praktisch
        # ist es nichts. Eine Warnung, die bei jedem Lauf erscheint und nie
        # etwas bedeutet, bringt einem bei, Warnungen zu ueberlesen.
        luecke = funding_frame["time"].iloc[0] - frame["open_time"].iloc[0]
        if luecke > pd.Timedelta(days=7):
            console.print(
                f"[yellow]Funding-Historie beginnt erst "
                f"{funding_frame['time'].iloc[0]:%Y-%m-%d}, die Kerzen schon "
                f"{frame['open_time'].iloc[0]:%Y-%m-%d} - "
                f"{luecke.days} Tage ohne Deckung.[/] Dort steht in der Spalte "
                "NaN, und Funding-Kandidaten handeln nicht.\n"
            )
    frame = attach_funding(frame, funding_frame)

    # Feinere Kerzen machen die Fill-Simulation ehrlicher: Ohne sie muss die
    # Engine annehmen, dass innerhalb einer Kerze der schlechtere Fall eintritt.
    sub_frame = store.read(settings.bybit.symbol, Interval.M1)
    if sub_frame.empty:
        console.print(
            "[yellow]Keine 1m-Kerzen - die Fill-Simulation rechnet pessimistisch.[/]"
        )
        sub_frame = None

    try:
        market = BybitMarketData(settings.bybit)
        instrument = market.get_instrument(settings.bybit.symbol)
    except BybitError as exc:
        console.print(
            f"[yellow]Kontraktdaten nicht abrufbar ({exc}). "
            "Es werden die bekannten BTCUSDT-Werte verwendet.[/]"
        )
        instrument = _fallback_instrument(settings.bybit.symbol)

    config = BacktestConfig(
        instrument=instrument,
        risk=settings.risk,
        initial_equity=Decimal("500"),
    )

    trials_path = Path(settings.paths.state) / "trials.json"
    journal_path = Path(settings.paths.state) / "journal.json"
    trials_before = load_trials(trials_path)

    genomes: list[Genome] = []
    if ki:
        genomes = _ask_the_analyst(settings, journal_path)
        if not genomes:
            console.print(
                "[yellow]Keine brauchbaren Vorschlaege - es laufen die "
                "Standardkandidaten.[/]"
            )
    if not genomes:
        genomes = load_seeds(generation)

    # Passt die Zeitebene zur Bauform?
    #
    # Die Indikator-Whitelist laesst hoechstens 400 Perioden zu. Auf
    # Stundenkerzen sind 200 Perioden deshalb acht Tage, nicht acht Monate -
    # der klassische Langfristfilter laesst sich dort gar nicht ausdruecken.
    # Eine Halte-Strategie mit Acht-Tage-Filter haelt nichts, sie springt rein
    # und raus und frisst genau die Gebuehren, die sie vermeiden sollte.
    #
    # Das ist beim Bauen genau so passiert und waere im Bericht als
    # "Idee widerlegt" durchgegangen. Deshalb hier eine Warnung statt eines
    # stillen Durchlaufs - der Lauf selbst bleibt erlaubt.
    haltend = [g for g in genomes if g.sizing.kind == "kapitalanteil"]
    if haltend and interval_obj not in (Interval.D1, Interval.W1):
        console.print(
            f"[yellow]{len(haltend)} von {len(genomes)} Kandidaten sind "
            f"Halte-Strategien, laufen hier aber auf {interval_obj.label}.[/]\n"
            "Ihre Perioden bedeuten dann Tage statt Monate, und sie handeln "
            "viel haeufiger als gedacht.\n"
            "[dim]Gemeint ist: python -m cli research --intervall D[/]\n"
        )

    console.print(
        f"\n[bold]Zulassung[/] {settings.bybit.symbol} {interval_obj.label}\n"
        f"  Historie    {frame['open_time'].iloc[0]:%Y-%m-%d} bis "
        f"{frame['open_time'].iloc[-1]:%Y-%m-%d}  ({len(frame):,} Kerzen)\n"
        f"  Kandidaten  {len(genomes)} (Generation {generation})\n"
        f"  Versuche    {trials_before} bisher"
        f"{'  [dim](fliesst in die Mehrfachtest-Korrektur ein)[/]' if trials_before else ''}\n"
        f"  Gates       {'6 (schnell)' if schnell else '9 (vollstaendig)'}\n".replace(
            ",", "."
        )
    )

    def show(position: int, total: int, genome: Genome) -> None:
        console.print(f"  [dim]{position}/{total}[/] {genome.name} ...")

    report = run_admission(
        genomes,
        frame,
        config,
        trials_so_far=trials_before,
        sub_frame=sub_frame,
        run_expensive=not schnell,
        on_progress=show,
    )
    save_trials(trials_path, report.trials_after)
    write_journal(report, Path(settings.paths.state) / "journal.json")

    # Die Messlatte: Was haette einfaches Halten im selben Zeitraum gebracht?
    #
    # Ohne diese Zahl ist "-19 % Rendite" nicht einzuordnen. Sie gehoert in den
    # Bericht, gerade wenn kein Kandidat besteht - dann sagt sie, wie weit der
    # Weg noch ist.
    messlatte = None
    try:
        vergleich = buy_and_hold(frame, initial_equity=config.initial_equity)
        messlatte = {
            "rendite_pct": round(vergleich.return_pct, 2),
            "max_drawdown_pct": round(vergleich.max_drawdown_pct, 2),
            "sharpe": round(vergleich.metrics.sharpe, 3),
            "beschreibung": vergleich.describe(),
        }
    except ValueError:
        pass

    _send_report(
        settings,
        report_payload(
            report,
            symbol=settings.bybit.symbol,
            interval=interval_obj.label,
            history_from=f"{frame['open_time'].iloc[0]:%Y-%m-%d}",
            history_to=f"{frame['open_time'].iloc[-1]:%Y-%m-%d}",
            candles=len(frame),
            gates_full=not schnell,
            benchmark=messlatte,
            funding_rows=len(funding_frame),
        ),
    )

    table = Table(title="Zulassungsergebnis", header_style="bold")
    table.add_column("Strategie")
    table.add_column("Trades", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Fenster +", justify="right")
    table.add_column("Ergebnis")
    for candidate in report.candidates:
        style = "green" if candidate.admitted else "red"
        verdict = "zugelassen" if candidate.admitted else candidate.gates.summary()
        table.add_row(
            candidate.genome.name,
            str(candidate.trades),
            f"{candidate.sharpe:.2f}",
            f"{candidate.consistency:.0%}",
            f"[{style}]{verdict}[/]",
        )
    console.print(table)

    for candidate in report.candidates:
        if not candidate.admitted:
            console.print(f"\n[bold]{candidate.genome.name}[/] - woran es lag:")
            console.print(f"[dim]{candidate.gates.feedback_for_ai()}[/]")

    if report.champion is None:
        console.print(
            "\n[yellow]Kein Kandidat hat alle Gates bestanden.[/]\n"
            "Das ist ein brauchbares Ergebnis, kein Fehlschlag: Lieber keine "
            "Strategie als eine, die nur im Backtest funktioniert.\n"
            "[dim]Die Begruendungen oben sind die Grundlage fuer die naechste "
            "Generation.[/]"
        )
        raise typer.Exit(1)

    console.print(
        f"\n[green]Champion: {report.champion.genome.name}[/]\n"
        f"[dim]{report.champion.genome.rationale}[/]"
    )

    if uebernehmen:
        path = write_champion(
            report.champion, Path(settings.paths.strategies) / "champion.json"
        )
        console.print(f"\nGeschrieben nach [bold]{path}[/]")
        console.print("[dim]Naechster Schritt: python -m cli trade --trocken[/]")


def _send_report(settings, payload: dict) -> None:
    """Bericht schreiben und selbstaendig ins Repository schieben.

    Der Rechner, auf dem gerechnet wird, steht beim Nutzer; ausgewertet wird
    woanders. Dazwischen lagen bisher Bildschirmfotos - unvollstaendig und
    genau dann vergessen, wenn ein Lauf interessant war.

    Faellt das Senden aus, ist das kein Grund zur Aufregung: Die Zahlen liegen
    dann in ``reports/`` und gehen beim naechsten gelungenen Lauf mit. Deshalb
    wird hier nie eine Ausnahme durchgelassen - ein abgebrochener
    Zulassungslauf waere der teurere Verlust.
    """
    from core.report import PublishStatus, publish, write_report

    try:
        file = write_report(payload, root=Path.cwd(), kind="zulassung")
    except OSError as exc:
        console.print(f"[yellow]Bericht konnte nicht geschrieben werden: {exc}[/]")
        return

    lauf = payload.get("lauf", {})
    result = publish(
        [file],
        root=Path.cwd(),
        message=(
            f"Bericht: {lauf.get('kandidaten', 0)} Kandidaten, "
            f"{lauf.get('zugelassen', 0)} zugelassen "
            f"({payload.get('markt', {}).get('symbol', '?')} "
            f"{payload.get('markt', {}).get('intervall', '?')})"
        ),
        enabled=settings.report.autopush,
    )

    if result.status is PublishStatus.PUSHED:
        console.print(f"\n[dim]Bericht gesendet: {file.name}[/]")
    elif result.status is PublishStatus.COMMITTED:
        console.print(f"\n[yellow]Bericht liegt in {file}[/]\n[dim]{result.detail}[/]")
    elif result.status is PublishStatus.FAILED:
        console.print(f"\n[yellow]Bericht nicht gesendet: {result.detail}[/]")
        console.print(f"[dim]Er liegt aber in {file}[/]")


def _ask_the_analyst(settings, journal_path: Path) -> list:
    """Die Research-KI um neue Kandidaten bitten.

    Sie schlaegt vor, sie entscheidet nicht: Jeder Vorschlag durchlaeuft
    danach dieselben neun Gates wie ein von Hand geschriebenes Genom,
    inklusive Mehrfachtest-Korrektur. Ein Modellaufruf verschiebt keine
    einzige Schwelle.
    """
    import json as _json

    from research.analyst import AnthropicClient, load_budget, propose, save_budget

    if not settings.llm.has_credentials:
        console.print(
            "[yellow]Kein LLM__ANTHROPIC_API_KEY gesetzt - die KI kann nicht "
            "gefragt werden.[/]"
        )
        return []

    journal = []
    if journal_path.exists():
        with contextlib.suppress(Exception):
            journal = _json.loads(journal_path.read_text())

    budget_path = journal_path.parent / "budget.json"
    budget = load_budget(budget_path, monthly_usd=settings.cost.profile.monthly_budget_usd)

    console.print(
        f"[dim]Forschungsbudget: {budget.remaining_usd:.2f} von "
        f"{budget.monthly_usd} USD offen ({budget.month})[/]"
    )
    if budget.exhausted:
        console.print(
            "[yellow]Monatsbudget ausgeschoepft.[/] "
            "[dim]Der Handel laeuft davon unberuehrt weiter - es kommt nur "
            "nichts Neues dazu.[/]"
        )
        return []

    # Was schon versucht wurde, muss die KI nicht noch einmal vorschlagen.
    tried: set[str] = set()
    for entry in journal:
        for candidate in entry.get("candidates", []):
            if candidate.get("genome_id"):
                tried.add(candidate["genome_id"])

    client = AnthropicClient(settings.llm.anthropic_api_key.get_secret_value())
    result = propose(client, journal=journal, budget=budget, already_tried=tried)
    save_budget(budget_path, budget)

    console.print(f"[dim]{result.summary()}[/]")
    for proposal in result.proposals:
        if not proposal.accepted:
            console.print(f"  [dim]abgelehnt: {proposal.genome.name} - {proposal.reason}[/]")

    for genome in result.genomes:
        console.print(f"  [green]neu:[/] {genome.name}")
        console.print(f"       [dim]{genome.rationale[:150]}[/]")

    return result.genomes


#: Referenzsymbol -> Bybit-Kontrakt. Die Kursdaten kommen fuer die Vorauswahl
#: von Bitstamp, die Handelsregeln muessen trotzdem die der Boerse sein, auf
#: der spaeter gehandelt wird.
_KONTRAKT_ZU_SYMBOL = {
    "BTCUSD_BITSTAMP": "BTCUSDT",
    "ETHUSD_BITSTAMP": "ETHUSDT",
    "LTCUSD_BITSTAMP": "LTCUSDT",
    "XRPUSD_BITSTAMP": "XRPUSDT",
}

#: Bekannte Bybit-Spezifikationen je Perpetual, fuer den Fall, dass die Boerse
#: gerade nicht erreichbar ist. Schrittweite, Mindest- und Hoechstmenge sind
#: hier keine Nebensache: Sie entscheiden, ob eine Order zustande kommt.
_KONTRAKTE = {
    #                 Tick     Schritt    min       max     Basis
    "BTCUSDT": ("0.1", "0.001", "0.001", "1190", "BTC"),
    "ETHUSDT": ("0.01", "0.01", "0.01", "72000", "ETH"),
    "LTCUSDT": ("0.01", "0.1", "0.1", "200000", "LTC"),
    "XRPUSDT": ("0.0001", "1", "1", "8000000", "XRP"),
}


def _terminkalender(settings):
    """Den Kalender laden - fuer Backtest und Handel derselbe.

    An **einer** Stelle, damit nicht der Backtest ohne Sperre rechnet und der
    Handel mit. Genau diese Sorte Abweichung ist in diesem Projekt fuenfmal
    aufgetreten, jedes Mal aus zwei Umsetzungen derselben Sache.

    Fehlt die Datei, ist der Kalender leer und es wird nichts gesperrt - das
    System handelt dann wie vor Phase 7. Geholt wird er mit ``cli termine``.
    """
    from data.termine import Terminkalender

    return Terminkalender.laden(Path(settings.paths.referenz) / "termine.json")


def _bybit_kontrakt(symbol: str) -> str:
    """Zum Kursdatensymbol den Kontrakt finden, auf dem gehandelt wird."""
    return _KONTRAKT_ZU_SYMBOL.get(symbol, symbol)


def _fallback_instrument(symbol: str):
    """Bekannte Bybit-Spezifikationen, wenn die Boerse nicht erreichbar ist.

    Der Backtest soll nicht daran scheitern, dass gerade kein Netz da ist.
    Fuer den Handel wird immer der echte Kontrakt geladen.

    **Warum je Symbol und nicht einmal fuer alle.** Es gab hier lange nur die
    BTCUSDT-Werte, die dann auch fuer ETH galten. Deren Hoechstmenge von 100
    Stueck ist fuer BTC nie erreichbar, fuer ETH bei 80 USD Kurs und Hebel aber
    sehr wohl - die Orders wurden stillschweigend abgelehnt, und die
    Ergebnisse sahen aus, als lohne sich Hebel ab einem Punkt nicht mehr.
    Ein falsch gesetztes Limit, das wie ein Marktbefund aussah.
    """
    from decimal import Decimal

    from core.models import Instrument

    tick, schritt, mindest, hoechst, basis = _KONTRAKTE.get(
        symbol, _KONTRAKTE["BTCUSDT"]
    )
    return Instrument(
        symbol=symbol,
        category="linear",
        base_coin=basis,
        quote_coin="USDT",
        tick_size=Decimal(tick),
        qty_step=Decimal(schritt),
        min_order_qty=Decimal(mindest),
        max_order_qty=Decimal(hoechst),
        min_notional=Decimal("5"),
        max_leverage=Decimal("100"),
        maintenance_margin_rate=Decimal("0.005"),
    )


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

        _install_stop_handler(stream.stop)

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
    from web.journal import LiveJournal

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

    kalender = _terminkalender(settings)
    if kalender:
        console.print(f"[dim]Termin-Overlay: {kalender.bericht()}[/dim]")
    officer = RiskOfficer(
        settings.risk,
        instrument,
        state_path=state_path,
        kalender=kalender or None,
        kerzenspanne=interval_obj.duration,
    )

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
            journal=LiveJournal(state_path.parent),
        )

        _install_stop_handler(trader.stop)

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
def review(
    intervall: str = typer.Option("15", "--intervall", "-i"),
    erwartung: float = typer.Option(
        None, help="Erwartungswert je Trade in R aus dem Walk-Forward."
    ),
) -> None:
    """Laeuft die Strategie noch? Und wo liegt Spielraum?

    Drei Auswertungen ueber die tatsaechlich gehandelten Trades:

    1. **Verfall** - deckt sich die Live-Erwartung noch mit dem Backtest?
       Vergleichsgroesse ist R, nicht Euro.
    2. **Marktphasen** - in welcher Umgebung funktioniert sie, in welcher nicht?
    3. **Ausstiege** - sagen MAE und MFE, dass Stop oder Ziele falsch sitzen?

    Einmal pro Woche ausfuehren, nicht taeglich. Wer taeglich draufschaut,
    reagiert auf Rauschen.
    """
    from pathlib import Path

    from research.decay import Health, assess_decay, detectable_drop
    from research.exits import analyse_exits
    from research.regime import performance_by_regime

    settings = get_settings()
    trades = _load_live_trades(Path(settings.paths.state))

    if not trades:
        console.print(
            "[yellow]Noch keine abgeschlossenen Trades.[/]\n"
            "[dim]Diese Auswertung wird interessant, sobald der Handel laeuft.[/]"
        )
        raise typer.Exit(1)

    console.print(f"\n[bold]Ueberpruefung[/] - {len(trades)} abgeschlossene Trades\n")

    # -- 1. Verfall ----------------------------------------------------------
    expected = erwartung if erwartung is not None else 0.10
    report = assess_decay(trades, expected_r=expected)
    colour = {
        Health.UNKNOWN: "dim",
        Health.HEALTHY: "green",
        Health.WATCH: "yellow",
        Health.DEGRADED: "red",
        Health.DEAD: "red",
    }[report.health]
    console.print(f"[bold]Zustand[/]  [{colour}]{report.health.value}[/]")
    console.print(f"[dim]{report.detail}[/]\n")

    if report.health is not Health.UNKNOWN:
        from research.decay import _stdev, r_multiples

        spread = _stdev(r_multiples(trades)) or 1.0
        share = detectable_drop(len(trades), spread, expected)
        console.print(
            f"[dim]Erkennbar waere derzeit erst ein Rueckgang um "
            f"{share:.0%} des Erwartungswerts. "
            f"{'Bei dieser Zahl Trades laesst sich wenig ausschliessen.' if share > 0.8 else ''}[/]\n"
        )

    # -- 2. Marktphasen ------------------------------------------------------
    store = CandleStore(settings.paths.data_store)
    frame = store.read(settings.bybit.symbol, Interval(intervall))
    if not frame.empty:
        table = Table(title="Nach Marktphase", header_style="bold")
        table.add_column("Phase")
        table.add_column("Trades", justify="right")
        table.add_column("R/Trade", justify="right")
        table.add_column("Treffer", justify="right")
        table.add_column("Urteil")
        for regime, performance in performance_by_regime(trades, frame).items():
            if performance.trades == 0:
                continue
            style = "green" if performance.is_competent else "red"
            verdict = "zustaendig" if performance.is_competent else "nicht zustaendig"
            table.add_row(
                regime.value,
                str(performance.trades),
                f"{performance.expectancy_r:+.3f}",
                f"{performance.win_rate:.0%}",
                f"[{style}]{verdict}[/]",
            )
        console.print(table)

    # -- 3. Ausstiege --------------------------------------------------------
    analysis = analyse_exits(trades)
    console.print(f"\n[bold]Ausstiege[/]\n[dim]{analysis.describe()}[/]\n")
    for suggestion in analysis.suggestions:
        console.print(f"  - {suggestion}\n")

    if report.should_retire:
        console.print(
            "[red]Empfehlung: Champion absetzen.[/] "
            "Die Live-Ergebnisse decken sich nicht mehr mit dem Backtest."
        )
        raise typer.Exit(2)


def _load_live_trades(state: Path):
    """Abgeschlossene Trades aus dem Betriebsjournal lesen."""
    import json

    from core.models import Trade

    file = state / "trades.jsonl"
    if not file.exists():
        return []

    trades = []
    for line in file.read_text().splitlines():
        try:
            trades.append(Trade.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError):
            continue  # abgeschnittene letzte Zeile ist normal
    return trades


@app.command()
def dashboard(
    host: str | None = typer.Option(None, help="Standard: 127.0.0.1 (nur lokal)."),
    port: int | None = typer.Option(None, help="Standard: 8000."),
) -> None:
    """Die Website starten - Live-Ansicht und Not-Aus.

    Laeuft als **eigener Prozess** neben dem Handel. Das ist Absicht: Liefe
    sie im selben Prozess, waere sie genau dann weg, wenn man sie am
    dringendsten braucht - naemlich wenn der Handel abgestuerzt ist. Getrennt
    zeigt sie dann "Handelsprozess antwortet nicht" statt gar nichts.

    Sie spricht nie selbst mit Bybit. Sie liest, was der Handel schreibt, und
    legt Anweisungen ab, die er abholt.

    Von aussen erreichbar macht man sie ueber einen SSH-Tunnel:

        ssh -L 8000:localhost:8000 benutzer@server

    Dann im Browser http://localhost:8000 - auch auf dem iPhone, ueber eine
    SSH-App. Wer sie direkt ins Netz stellt, gehoert hinter einen
    Reverse-Proxy mit TLS.
    """
    import uvicorn

    from web.api import create_app

    settings = get_settings()
    bind_host = host or settings.web.host
    bind_port = port or settings.web.port

    if not settings.web.password.get_secret_value():
        console.print(
            "[yellow]Kein WEB__PASSWORD gesetzt - die Steuerung bleibt gesperrt.[/]\n"
            "[dim]Die Ansicht funktioniert; Pause, Glattstellen und Not-Aus nicht.\n"
            "Ein Not-Aus-Knopf ohne Passwort waere schlimmer als keiner.[/]\n"
        )
    if bind_host not in {"127.0.0.1", "localhost"}:
        console.print(
            f"[yellow]Achtung: Das Dashboard hoert auf {bind_host} und ist damit "
            "aus dem Netz erreichbar.[/]\n"
            "[dim]Ohne TLS davor ist das Passwort im Klartext unterwegs. "
            "Besser: auf 127.0.0.1 lassen und einen SSH-Tunnel benutzen.[/]\n"
        )

    console.print(
        f"[bold]Dashboard[/] http://{bind_host}:{bind_port}\n"
        f"[dim]Zustand aus {settings.paths.state}/ - Strg-C zum Beenden[/]\n"
    )
    uvicorn.run(create_app(settings), host=bind_host, port=bind_port, log_level="warning")


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


@app.command()
def betriebspunkt(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt. Mehrere heisst Portfolio.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    kapital: float = typer.Option(500.0, help="Startkapital fuer die Geldspalte."),
    json_datei: Path | None = typer.Option(
        None, "--json", help="Ergebnis zusaetzlich als JSON ablegen (fuer die Website)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Was jede Hebelstufe bringt - und was sie kostet.

    Rechnet dieselbe Regel mit steigendem Vola-Ziel durch und stellt vier
    Zahlen nebeneinander: Rendite, Rueckgang, Endkapital und - die
    entscheidende - **wie oft der eigene Kill-Switch ausgeloest haette**.

    Eine Rendite, die nur zustande kommt, wenn man die eigene Abbruchregel
    ignoriert, ist keine Rendite. Deshalb steht diese Spalte hier und nicht
    im Kleingedruckten.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from data.bybit.errors import BybitError
    from research.operating_point import (
        as_payload,
        highest_safe,
        measure,
        turning_point,
    )
    from strategy.genome import (
        Condition,
        Genome,
        Operator,
        SizingSpec,
        StopSpec,
        TargetSpec,
    )

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)

    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames: dict[str, object] = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        frames[symbol] = frame

    def bauplan(vola_ziel: float) -> Genome:
        """Trend-Beteiligung, Groesse nach Vola-Ziel.

        Zwischen den Stufen aendert sich **ausschliesslich** das Vola-Ziel.
        Jede zweite Aenderung wuerde den Vergleich wertlos machen.
        """
        return Genome(
            name=f"Trend-Beteiligung Vola-Ziel {vola_ziel:.0f}",
            rationale="Long ueber dem 200er-Schnitt, raus darunter.",
            entry_long=[
                Condition(
                    left={"kind": "price", "name": "close"},
                    op=Operator.CROSS_ABOVE,
                    right={"kind": "indicator", "name": "sma", "params": {"period": 200}},
                )
            ],
            exit_long=[
                Condition(
                    left={"kind": "price", "name": "close"},
                    op=Operator.LT,
                    right={"kind": "indicator", "name": "sma", "params": {"period": 200}},
                )
            ],
            stop=StopSpec(kind="percent", percent=15.0),
            targets=[TargetSpec(rr=20.0, portion=1.0)],
            sizing=SizingSpec(
                kind="vola_ziel", fraction=3.0,
                target_vol_pct=vola_ziel, vol_period=30,
            ),
            cooldown_bars=0,
            max_hold_bars=0,
        )

    # Je Markt der eigene Kontrakt.
    #
    # BTCs Werte auf ETH anzuwenden ist kein Schoenheitsfehler: ETH kostete
    # Ende 2018 rund 80 USD, BTCUSDTs max_order_qty liegt bei 100 Stueck - bei
    # hohem Hebel wurden die ETH-Orders damit stillschweigend abgelehnt und die
    # betroffenen Stufen sahen schlechter aus, als sie sind.
    markt_data = BybitMarketData(settings.bybit)
    configs: dict[str, BacktestConfig] = {}
    for symbol in symbole:
        try:
            instrument = markt_data.get_instrument(_bybit_kontrakt(symbol))
        except BybitError:
            instrument = _fallback_instrument(_bybit_kontrakt(symbol))
        configs[symbol] = BacktestConfig(
            instrument=instrument,
            risk=settings.risk,
            initial_equity=Decimal(str(kapital)),
        )
    grenze = float(settings.risk.max_drawdown_pct)

    console.print(
        f"\n[bold]Betriebspunkt[/] {' + '.join(symbole)} {interval_obj.label}, "
        f"Abbruch bei {grenze:.0f} % Rueckgang\n"
    )

    stufen = measure(
        frames, bauplan, configs, kill_switch_pct=grenze, start_capital=kapital
    )
    if not stufen:
        console.print("[red]Keine Stufe konnte gerechnet werden.[/] Zu wenig Historie?")
        raise typer.Exit(2)

    table = Table(header_style="bold")
    table.add_column("Stufe", justify="right")
    table.add_column("Hebel", justify="right")
    table.add_column("pro Jahr", justify="right")
    table.add_column("Rueckgang", justify="right")
    table.add_column(f"aus {kapital:.0f}", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Kill-Switch", justify="right")

    for s in stufen:
        heikel = s.kill_switch > 0
        stil = "red" if heikel else "green"
        table.add_row(
            f"{s.vola_ziel:.0f}",
            f"{s.hebel:.2f}x",
            f"{s.cagr_pct:.1f} %",
            f"[{stil}]{s.drawdown_pct:.1f} %[/]",
            f"{s.endwert:.0f}",
            f"{s.sharpe:.2f}",
            f"[{stil}]{s.kill_switch}x[/]",
        )
    console.print(table)

    sicher = highest_safe(stufen)
    if sicher is not None:
        console.print(
            f"\n[green]Hoechste Stufe ohne Abbruch: {sicher.vola_ziel:.0f}[/] - "
            f"{sicher.hebel:.2f}x Hebel, {sicher.cagr_pct:.1f} % pro Jahr, "
            f"{sicher.drawdown_pct:.1f} % Rueckgang, aus {kapital:.0f} werden "
            f"{sicher.endwert:.0f}."
        )
    else:
        console.print(
            f"\n[red]Keine Stufe bleibt unter {grenze:.0f} % Rueckgang.[/] "
            "Entweder niedriger ansetzen als die kleinste gepruefte Stufe, "
            "oder die Regel selbst taugt nicht fuer dieses Kapital."
        )

    wende = turning_point(stufen)
    if wende is not None:
        console.print(
            f"[yellow]Ab Stufe {wende.vola_ziel:.0f} bringt mehr Hebel weniger "
            f"Geld[/] ({wende.endwert:.0f} statt mehr) bei hoeherem Rueckgang. "
            "Der Weg zurueck aus einem Verlust waechst schneller als der "
            "Verlust selbst."
        )

    console.print(
        "\n[dim]Die letzte Spalte ist die wichtigste: Bei jedem Ausloesen waere "
        "der Handel gestoppt worden. Die Gewinne der roten Stufen sind nach "
        "der eigenen Abbruchregel nicht erreichbar.[/]"
    )

    if json_datei is not None:
        import json

        nutzlast = as_payload(
            stufen, markets=symbole, kill_switch_pct=grenze, start_capital=kapital
        )
        nutzlast["erzeugt"] = datetime.now(UTC).isoformat()
        nutzlast["intervall"] = interval_obj.label
        json_datei.parent.mkdir(parents=True, exist_ok=True)
        json_datei.write_text(json.dumps(nutzlast, indent=2), encoding="utf-8")
        console.print(f"[dim]JSON geschrieben: {json_datei}[/]")


@app.command()
def korb(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    generation: int = typer.Option(9, "--generation", "-g", help="Startkatalog."),
    vola_ziel: float = typer.Option(
        50.0, help="Vola-Ziel in Prozent. Siehe `betriebspunkt` fuer die Stufen."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Mehrere Maerkte als **einen** Kandidaten durch alle elf Gates.

    Die Zulassung kannte bisher nur einen Markt. Gemessen wurde deshalb immer
    BTC allein oder ETH allein - und beide scheiterten unter anderem am
    Rueckgang. Das Doppel aus beiden liegt darunter, war aber nie geprueft,
    weil es die Maschinerie dafuer nicht gab.

    Das ist keine Lockerung: Gehandelt wuerde ohnehin der Korb. Geprueft wird
    jetzt das, was tatsaechlich laufen soll, mit denselben Schwellen.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from data.bybit.errors import BybitError
    from research.gates import evaluate_gates
    from research.seeds import load_seeds
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)

    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    erster = next(iter(frames.values()))
    spanne = (erster["open_time"].iloc[-1] - erster["open_time"].iloc[0]).days
    if spanne < 450:
        console.print(
            f"[red]Nur {spanne} Tage gemeinsame Historie.[/] Der Walk-Forward "
            "braucht mindestens 450."
        )
        raise typer.Exit(2)

    markt_data = BybitMarketData(settings.bybit)
    configs: dict[str, BacktestConfig] = {}
    for symbol in symbole:
        try:
            instrument = markt_data.get_instrument(_bybit_kontrakt(symbol))
        except BybitError:
            instrument = _fallback_instrument(_bybit_kontrakt(symbol))
        configs[symbol] = BacktestConfig(
            instrument=instrument, risk=settings.risk, initial_equity=Decimal("500")
        )

    trials_path = Path(settings.paths.state) / "trials.json"
    from research.admission import load_trials, save_trials

    trials = load_trials(trials_path)

    console.print(
        f"\n[bold]Korb[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Gemeinsam  {erster['open_time'].iloc[0]:%Y-%m-%d} bis "
        f"{erster['open_time'].iloc[-1]:%Y-%m-%d} ({spanne} Tage)\n"
        f"  Versuche   {trials} bisher\n"
    )

    tabelle = Table(header_style="bold")
    tabelle.add_column("Kandidat")
    tabelle.add_column("Gates", justify="right")
    tabelle.add_column("Trades", justify="right")
    tabelle.add_column("Sharpe", justify="right")
    tabelle.add_column("Rueckgang", justify="right")
    tabelle.add_column("Gescheitert an")

    bester = None
    for genome in load_seeds(generation):
        # Alle Kandidaten auf dieselbe Groessenlogik stellen. Sonst
        # vergleicht man Hebelstufen statt Regeln.
        angepasst = genome.model_copy(
            update={
                "sizing": SizingSpec(
                    kind="vola_ziel", fraction=3.0,
                    target_vol_pct=vola_ziel, vol_period=30,
                )
            }
        )
        report = run_portfolio_walkforward(
            frames, lambda g=angepasst: compile_genome(g), configs
        )
        if not report.windows:
            continue

        # Jeder gepruefte Kandidat erhoeht den Zaehler - auch dieser hier.
        #
        # Ohne das waere die Deflated Sharpe Ratio wertlos: Sie korrigiert
        # dafuer, dass man bei genug Versuchen irgendwann etwas findet, das
        # im Rueckblick gut aussieht. Wer Kandidaten prueft, ohne sie zu
        # zaehlen, macht die Korrektur milder - und zwar genau dann, wenn er
        # am meisten sucht.
        trials += 1
        gates = evaluate_gates(
            angepasst, report, erster, next(iter(configs.values())),
            trials_so_far=trials,
        )
        bestanden = sum(1 for r in gates.results if r.passed)
        gescheitert = ", ".join(r.name for r in gates.failures)[:44] or "-"
        stil = "green" if gates.passed else ""
        tabelle.add_row(
            f"[{stil}]{angepasst.name[:30]}[/]" if stil else angepasst.name[:30],
            f"{bestanden}/{len(gates.results)}",
            str(len(report.all_trades)),
            f"{report.combined.sharpe:.2f}" if report.combined else "-",
            f"{report.combined.max_drawdown_pct:.1f} %" if report.combined else "-",
            gescheitert,
        )
        if bester is None or bestanden > bester[0]:
            bester = (bestanden, angepasst.name, gates)

    save_trials(trials_path, trials)
    console.print(tabelle)

    if bester is None:
        console.print("[red]Kein Kandidat konnte gerechnet werden.[/]")
        raise typer.Exit(2)

    anzahl, name, gates = bester
    console.print(f"\n[bold]Bester: {name}[/] - {anzahl}/{len(gates.results)} Gates\n")
    for r in gates.results:
        farbe = {"pass": "green", "fail": "red", "skip": "dim"}[r.status.value]
        zeichen = {"pass": "OK", "fail": "--", "skip": ".."}[r.status.value]
        console.print(
            f"  [{farbe}]{zeichen}[/] {r.name:22s} "
            f"{r.value:>9.3f} / {r.threshold:>8.3f}  [dim]{r.message[:50]}[/]"
        )

    if not gates.passed:
        console.print(
            "\n[dim]Nicht zugelassen. Die Schwellen bleiben, wo sie sind - "
            "eine Strategie, die nur im Rueckblick funktioniert, kostet mehr "
            "als gar keine.[/]"
        )


@app.command()
def evidenz(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    vola_ziel: float = typer.Option(19.3, help="Vola-Ziel des Kandidaten."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Was der Livebetrieb bisher beweist - und was er beweisen koennte.

    Beantwortet die Frage, die vor dem ersten echten Euro steht: Reicht das,
    was auf dem Demokonto passiert ist, als Beleg?

    Die Antwort ist fast nie ja, und der Grund ist Arithmetik, keine
    Vorsicht: Eine Strategie mit 17 Trades im Jahr erzeugt in 30 Tagen
    **1,4** Trades. Ein Monat Demo prueft, ob die Technik haelt - nicht, ob
    der Vorteil echt ist. Das sind zwei verschiedene Fragen, und nur die
    erste laesst sich in einem Monat beantworten.

    Der Versuchszaehler bleibt unberuehrt: Dieselbe Strategie laenger zu
    beobachten ist kein weiterer Versuch.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.live_evidenz import (
        bewerten,
        demo_dauer,
        erkennbare_verschlechterung,
        live_trades_fuer_nachweis,
        r_werte,
    )
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec
    from web.trades import read_trades

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    erster = next(iter(frames.values()))
    genome = spitzenkandidat().model_copy(
        update={
            "sizing": SizingSpec(
                kind="vola_ziel", fraction=3.0, target_vol_pct=vola_ziel,
                vol_period=30, konviktion_bonus=1.0,
            )
        }
    )
    configs = {
        s: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(s)),
            risk=settings.risk, initial_equity=Decimal("500"),
            kalender=_terminkalender(settings) or None,
        )
        for s in symbole
    }

    console.print(f"\n[bold]Evidenz[/] {' + '.join(symbole)} {interval_obj.label}\n")
    report = run_portfolio_walkforward(
        frames, lambda: compile_genome(genome), configs
    )
    if not report.windows:
        console.print("[red]Keine Fenster - zu wenig gemeinsame Historie.[/]")
        raise typer.Exit(2)

    backtest_r = r_werte(report.all_trades)
    jahre = (erster["open_time"].iloc[-1] - erster["open_time"].iloc[0]).days / 365.25
    pro_jahr = len(backtest_r) / jahre if jahre > 0 else 0.0

    state_dir = Path(settings.paths.state)
    uebersicht = read_trades(state_dir, limit=1000)
    trials = load_trials(state_dir / "trials.json")

    ergebnis = bewerten(
        report.all_trades, uebersicht.trades, trials=trials,
        live_tage=None,
    )
    console.print(ergebnis.bericht())
    console.print(
        f"\n[dim]Backtest: {len(backtest_r)} Trades in {jahre:.1f} Jahren "
        f"= {pro_jahr:.1f} im Jahr. Versuchszaehler {trials}, unveraendert.[/]\n"
    )

    tabelle = Table(header_style="bold", title="Was ein Demo-Zeitraum bringt")
    tabelle.add_column("Zeitraum")
    tabelle.add_column("Trades", justify="right")
    tabelle.add_column("Was unentdeckt bliebe", justify="right")
    for tage, name in ((30, "ein Monat"), (90, "ein Quartal"),
                       (365, "ein Jahr"), (1095, "drei Jahre"),
                       (3650, "zehn Jahre")):
        anzahl = demo_dauer(pro_jahr, tage)
        blind = erkennbare_verschlechterung(backtest_r, max(1, round(anzahl)))
        # Ueber 100 % hiesse: Der Vorteil koennte sich ins Gegenteil verkehrt
        # haben, ohne aufzufallen. Die genaue Zahl dahinter ist bedeutungslos
        # und nur Rauschen der Stichprobe - "alles" ist die ehrlichere Angabe.
        text = "alles" if blind >= 1.0 else f"{blind:.0%} des Vorteils"
        tabelle.add_row(name, f"{anzahl:.1f}", text)
    console.print(tabelle)
    console.print(
        "[dim]  \"alles\" heisst: Selbst wenn der Vorteil vollstaendig weg "
        "waere, wuerde man es an so wenigen Trades nicht sehen.[/]"
    )

    fuer_25 = live_trades_fuer_nachweis(backtest_r, 0.25)
    fuer_50 = live_trades_fuer_nachweis(backtest_r, 0.50)
    console.print(
        f"\n  Um eine Halbierung des Vorteils zu bemerken: [bold]{fuer_50}[/] "
        f"Trades ([bold]{fuer_50 / pro_jahr:.0f} Jahre[/])\n"
        f"  Um ein Viertel weniger zu bemerken:          [bold]{fuer_25}[/] "
        f"Trades ([bold]{fuer_25 / pro_jahr:.0f} Jahre[/])\n"
    )
    console.print(
        "[dim]Der Demobetrieb ist damit ein Test der Technik, kein Beleg fuer "
        "den Vorteil. Beides ist noetig - aber nur das erste ist in einem "
        "Monat zu haben.[/]"
    )


@app.command()
def abgleich(
    symbol: str = typer.Option("BTCUSD_BITSTAMP", "--symbol", "-s"),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    puffer: int = typer.Option(
        2000, "--puffer",
        help="Kerzen im Speicher des Livebetriebs. Kleiner setzen, um das "
             "Ueberlaufen zu erzwingen.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Erzeugt der Livebetrieb dieselben Signale wie der Backtest?

    **Vor jedem Livegang auszufuehren.** Alle Kennzahlen im BEFUND stammen aus
    dem Backtest; gehandelt wird vom Livebetrieb. Weichen die beiden ab, misst
    die ganze Zulassung etwas anderes als das, was passieren wird.

    Auffallen wuerde das sonst nicht: ``cli evidenz`` rechnet vor, dass bei 17
    Trades im Jahr selbst ein vollstaendiger Verlust des Vorteils drei Jahre
    lang unentdeckt bliebe. Ein Unterschied zwischen Backtest und Betrieb muss
    durch Nebeneinanderlegen gefunden werden, nicht durch Zuschauen.

    Verglichen wird die ganze Entscheidungsflaeche: Einstiegssignal,
    Ausstiegsbedingung und Kapitalanteil. Nur das Signal zu vergleichen
    genuegte nicht - von den drei bisher gefundenen Abweichungen haette das
    zwei durchgelassen.

    Alle drei sind in ``strategies/BEFUND.md`` beschrieben.
    """
    from backtest.replay import vergleiche
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)

    frame = store.read(symbol, interval_obj)
    if frame.empty:
        console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
        raise typer.Exit(2)

    genome = spitzenkandidat()
    console.print(
        f"\n[bold]Abgleich[/] {symbol} {interval_obj.label}\n"
        f"  Kerzen   {len(frame)}\n"
        f"  Strategie {genome.name} ({genome.genome_id})\n"
        f"  Puffer   {puffer} Kerzen\n"
    )

    ergebnis = vergleiche(frame, lambda: compile_genome(genome), buffer_bars=puffer)

    if ergebnis.einig:
        console.print(f"[green]{ergebnis.bericht()}[/]\n")
        console.print(
            "[dim]Einstieg, Ausstieg und Kapitalanteil stimmen auf jedem "
            "Balken ueberein. Was hier nicht geprueft wird, ist die "
            "Ausfuehrung selbst - Fills, Stops an der Boerse, Neustart mitten "
            "in einer Position. Dafuer ist die Testsuite da (test_live.py) "
            "und der Demobetrieb.[/]"
        )
        return

    console.print(f"[red]{ergebnis.bericht()}[/]\n")
    console.print(
        "[red]Nicht live gehen.[/] Jede Abweichung heisst, dass die "
        "Zulassungszahlen etwas anderes messen als den Betrieb."
    )
    raise typer.Exit(1)


@app.command()
def landschaft(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Plateau oder Grat - wie sieht die Gegend um den Kandidaten aus?

    Das Gate ``Parameter-Plateau`` prueft genau zwei Nachbarn. Daraus laesst
    sich nicht ablesen, ob ein Kandidat auf einer Nadelspitze sitzt oder am
    Rand einer breiten Hochebene - und das sind sehr verschiedene Lagen.

    Diese Karte tastet die Periode ueber den halben bis doppelten Wert ab und
    zeigt die Form.

    **Kein Optimierer.** Wer die Karte liest und den besten Punkt zum neuen
    Kandidaten erklaert, hat genau die Ueberanpassung begangen, gegen die das
    Plateau-Gate gebaut wurde. Die Karte beantwortet eine andere Frage:
    Traegt diese Regelfamilie ueberhaupt?

    Jeder abgetastete Punkt zaehlt als Versuch und hebt die Huerde des
    Deflated Sharpe. Der Zaehler wird deshalb erhoeht.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range
    from research.admission import load_trials, save_trials
    from research.landschaft import kartieren
    from research.seeds import spitzenkandidat

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    configs = {
        s: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(s)),
            risk=settings.risk, initial_equity=Decimal("500"),
            kalender=_terminkalender(settings) or None,
        )
        for s in symbole
    }

    genome = spitzenkandidat()
    erster = next(iter(frames.values()))
    console.print(
        f"\n[bold]Landschaft[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Strategie  {genome.name}\n"
        f"  Zeitraum   {erster['open_time'].iloc[0]:%Y-%m} bis "
        f"{erster['open_time'].iloc[-1]:%Y-%m}\n"
    )

    karte = kartieren(genome, frames, configs)
    console.print(karte.tabelle())

    trials_path = Path(settings.paths.state) / "trials.json"
    neue = max(0, len(karte.punkte) - 1)  # der Kandidat selbst zaehlt nicht neu
    vorher = load_trials(trials_path)
    save_trials(trials_path, vorher + neue)

    farbe = "green" if "Plateau" in karte.urteil() else "yellow"
    console.print(f"\n[{farbe}]{karte.urteil()}[/]")
    console.print(
        f"[dim]{len(karte.profitabel)} von {len(karte.punkte)} Punkten "
        f"profitabel. Versuchszaehler {vorher} -> {vorher + neue}.[/]\n"
    )
    console.print(
        "[dim]Die Karte sagt, ob die Regelfamilie traegt - nicht, welchen "
        "Punkt man nehmen soll. Den besten auszuwaehlen waere genau die "
        "Ueberanpassung, gegen die das Plateau-Gate gebaut wurde.[/]"
    )


if __name__ == "__main__":
    app()
