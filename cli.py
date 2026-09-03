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
    intervall: str = typer.Option(
        "", "--intervall", "-i",
        help="Handelsintervall. Leer = das der gewaehlten Generation.",
    ),
    symbol: str | None = typer.Option(
        None, "--symbol",
        help="Abweichendes Symbol, z.B. BTCUSD_BITSTAMP fuer Referenzkerzen.",
    ),
    maerkte: str = typer.Option(
        "", "--maerkte", "-m",
        help="Mehrere Maerkte als Portfolio, durch Komma getrennt. Leer = "
             "einzelner Markt. **Suchen und Pruefen gehoeren auf dieselbe "
             "Aufstellung** - der Spitzenkandidat steht auf BTC allein bei "
             "5 von 11, auf BTC + ETH bei 7 von 11.",
    ),
    generation: int = typer.Option(
        8, "--generation", "-g",
        help="Startkatalog. 7 = Scalp-Setups, 8 = Abfolge-Modell und Short-Seite."
    ),
    von_spitze: bool = typer.Option(
        False, "--von-spitze",
        help="Statt eines Katalogs mit Varianten des besten bekannten "
             "Kandidaten beginnen. Spart die Runden, in denen die Suche "
             "erst wieder dorthin finden muss.",
    ),
    runden: int = typer.Option(
        0, help="Anzahl Runden. 0 = Dauerlauf bis Strg-C oder bis einer besteht."
    ),
    varianten: int = typer.Option(
        8, help="Wie viele Varianten je Runde aus den Besten gebildet werden."
    ),
    schnell: bool = typer.Option(
        True, "--schnell/--vollstaendig",
        help="Vorauswahl ohne die beiden teuren Gates. Wer sie besteht, wird "
             "sofort mit allen elf nachgeprueft - ein Champion entsteht nie "
             "aus einer Vorauswahl.",
    ),
    ki: bool = typer.Option(
        False, "--ki/--ohne-ki",
        help="Die Research-KI je Runde neue Kandidaten vorschlagen lassen - "
             "**zusaetzlich** zu den Varianten, nicht statt ihrer. Ohne "
             "dieses Flag bildet der Wettbewerb nur Abwandlungen dessen, was "
             "er schon kennt.",
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
    from backtest.portfolio_walkforward import common_range
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
    intervall = intervall or _standardintervall(generation)
    interval_obj = Interval(intervall)

    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    handelssymbol = symbole[0] if symbole else (symbol or settings.bybit.symbol)
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

    # **Gesucht wird auf der Aufstellung, auf der geurteilt wird.**
    #
    # Ohne ``--maerkte`` ist das ein Markt, und dann ist es dasselbe wie
    # vorher. Mit mehreren wird der Wettbewerb auf genau die Beine gestellt,
    # aus denen jede Zulassungszahl des Projekts stammt. Der Unterschied ist
    # kein Detail: derselbe Spitzenkandidat kommt auf BTC allein auf 5 von 11
    # (Deflated Sharpe 0,190), auf BTC + ETH auf 7 von 11 (0,843). Wer auf dem
    # einen Berg sucht und auf dem anderen prueft, optimiert am Ziel vorbei.
    frames: dict | None = None
    configs: dict | None = None
    if len(symbole) > 1:
        roh = {}
        for markt in symbole:
            teil = store.read(markt, interval_obj)
            if teil.empty:
                console.print(f"[red]Keine Kerzen fuer {markt} {interval_obj.label}.[/]")
                raise typer.Exit(2)
            roh[markt] = teil
        frames = common_range(roh)
        configs = {
            markt: BacktestConfig(
                instrument=_fallback_instrument(_bybit_kontrakt(markt)),
                risk=settings.risk,
                initial_equity=Decimal("500"),
                enforce_risk_limits=True,
                kalender=_terminkalender(settings) or None,
            )
            for markt in symbole
        }
        # Die Messlatte gehoert auf denselben Zeitraum wie die Beine, sonst
        # vergleicht das Benchmark-Gate ueber verschiedene Jahre.
        frame = attach_funding(frames[handelssymbol], funding_frame)
        sub_frame = None

    state = Path(settings.paths.state)
    board = Leaderboard(state / "leaderboard.json")
    trials_path = state / "trials.json"
    # Dasselbe Journal, aus dem ``cli research`` die KI lernen laesst: Es
    # traegt, woran die bisherigen Kandidaten gescheitert sind.
    journal_path = state / "journal.json"

    console.print(
        f"\n[bold]Wettbewerb[/] {' + '.join(symbole) if frames else handelssymbol} "
        f"{interval_obj.label}\n"
        f"  Historie   {frame['open_time'].iloc[0]:%Y-%m-%d} bis "
        f"{frame['open_time'].iloc[-1]:%Y-%m-%d}\n"
        f"  Bisher     {board.summary()}\n"
        f"  Ende       {'nach ' + str(runden) + ' Runden' if runden else 'Strg-C'}\n"
    )

    runde = 0
    # **Wo die Suche anfaengt, entscheidet, wofuer die Versuche draufgehen.**
    #
    # Aus einem Katalog heraus verbringt sie die ersten Runden damit, sich an
    # das Niveau heranzuarbeiten, das laengst bekannt ist - und jeder dieser
    # Versuche hebt die Huerde des Deflated Sharpe fuer alle spaeteren. Mit
    # --von-spitze beginnt sie bei Varianten des besten Kandidaten.
    #
    # Der Spitzenkandidat selbst wird dabei **nicht** noch einmal geprueft:
    # Sein Ergebnis steht, und ein zweiter Lauf desselben Genoms waere keine
    # zweite Hypothese, wuerde aber wie eine gezaehlt.
    if von_spitze:
        from research.seeds import spitzenkandidat

        aktuell = breed([spitzenkandidat()], varianten, seed=0)
        herkunft = "Variante der Spitze"
        if not aktuell:
            console.print("[red]Keine Varianten des Spitzenkandidaten moeglich.[/]")
            raise typer.Exit(2)
    else:
        _pruefe_generation(generation, interval_obj)
        aktuell = load_seeds(generation)
        herkunft = "Katalog"

    # **Der Wettbewerb konnte bis hierher nur abwandeln, was er schon kennt.**
    #
    # ``breed`` bildet Varianten der Besten; strukturell Neues entsteht dabei
    # nicht. Genau das ist die Lage nach Befund 145: Alle gemessenen
    # Richtungen sind leer, und was fehlt, ist eine Regel, die es noch nicht
    # gibt. Die Research-KI ist das einzige Bauteil, das eine vorschlagen
    # kann - sie hing aber nur an ``cli research`` und nie am Wettbewerb
    # (Befund 146).
    #
    # Sie schlaegt vor und entscheidet nichts: Ihre Genome laufen durch
    # dieselben elf Gates und zaehlen im Versuchszaehler wie jedes andere.
    def _vorschlaege() -> list:
        if not ki:
            return []
        neu = _ask_the_analyst(settings, journal_path)
        bekannt = {g.genome_id for g in aktuell}
        return [g for g in neu if g.genome_id not in bekannt]

    ki_ids: set[str] = set()
    if ki:
        zusatz = _vorschlaege()
        if zusatz:
            aktuell = list(aktuell) + zusatz
            ki_ids = {g.genome_id for g in zusatz}

    try:
        while runden == 0 or runde < runden:
            runde += 1
            trials_before = load_trials(trials_path)
            woher = herkunft if not ki_ids else (
                f"{herkunft} + {len(ki_ids)} von der KI"
            )
            console.print(
                f"[bold]Runde {runde}[/] - {len(aktuell)} Kandidaten "
                f"({woher}), {trials_before} Versuche bisher"
            )

            report = run_admission(
                aktuell,
                frame,
                config,
                trials_so_far=trials_before,
                sub_frame=sub_frame,
                run_expensive=not schnell,
                frames=frames,
                configs=configs,
            )
            save_trials(trials_path, report.trials_after)
            for gruppe, quelle in _nach_herkunft(
                report.candidates, ki_ids, herkunft
            ):
                if not gruppe:
                    continue
                board.record(
                    gruppe, generation=generation, herkunft=quelle,
                    versuche=report.trials_after, intervall=interval_obj.value,
                    # Aus den Konfigurationen gelesen und nicht noch einmal
                    # hingeschrieben: Sonst kann der Eintrag von dem Lauf
                    # abweichen, den er beschreibt.
                    kapital=_startkapital(configs),
                )
            board.save()

            # Von den Besten die einzelnen Trades mitschreiben.
            #
            # Die Kennzahlen sagen nicht, was eine Strategie eigentlich getan
            # hat: Ausgeglichene Erwartung kann viele kleine Gewinne mit
            # wenigen grossen Verlusten heissen - oder genau umgekehrt.
            # Dieselbe Zahl, gegensaetzliche Erfahrung damit.
            spitzen_ids = {
                e.genome_id for e in board.best(3, versuche=report.trials_after)
            }
            for kandidat in report.candidates:
                if kandidat.genome.genome_id in spitzen_ids:
                    _schreibe_tradelog(state, build_log(kandidat))

            _zeige_bestenliste(board, limit=10, versuche=report.trials_after)
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
                    report.champion,
                    Path(settings.paths.strategies) / "champion.json",
                    bedingungen=_bedingungen(
                        report.champion, configs, interval_obj, report.trials_after
                    ),
                )
                console.print("[dim]Naechster Schritt: python -m cli trade --trocken[/]")
                break

            # Weiter mit Varianten der Besten. Nur aus denen, die schon nahe
            # dran waren - wild zu streuen kostet Versuche und bringt nichts.
            #
            # **Auf gemeinsamer Huerde ausgewaehlt.** Ohne ``versuche`` stuende
            # ein Eintrag aus der Vorwoche mit einem Vorteil da, den er nicht
            # verdient hat - der Deflated Sharpe faellt mit jedem Versuch, auch
            # wenn sich an der Regel nichts aendert. Die Suche wuerde dann aus
            # den falschen Eltern zuechten.
            spitze = board.best(5, versuche=report.trials_after)
            ids = {e.genome_id for e in spitze}
            basis = [c.genome for c in report.candidates if c.genome.genome_id in ids]
            if not basis:
                basis = [c.genome for c in report.candidates[:3]]

            aktuell = breed(basis, varianten, seed=runde)
            herkunft = "Variante"

            # Die KI wird **nach** der Runde gefragt, nicht davor: Damit sieht
            # sie im Journal, woran die letzten Kandidaten gescheitert sind.
            # Genau das ist der Lernmechanismus, den ``analyst.py`` im Kopf
            # beschreibt - ohne ihn schlaegt ein Modell in jedem Zyklus
            # ungefaehr dasselbe vor und hebt nur die Huerde.
            zusatz = _vorschlaege()
            ki_ids = {g.genome_id for g in zusatz}
            aktuell = list(aktuell) + zusatz

            if not aktuell:
                console.print(
                    "[yellow]Keine neuen Varianten mehr moeglich"
                    + (" und kein Vorschlag der KI." if ki else ".")
                    + "[/]"
                )
                break

    except KeyboardInterrupt:
        console.print("\n[dim]Abgebrochen. Die Bestenliste ist gespeichert.[/]")

    board.save()
    console.print(f"\n[bold]{board.summary()}[/]")
    console.print(f"[dim]Bestenliste: {board.path}[/]")


def _nach_herkunft(
    kandidaten: list, ki_ids: set[str], herkunft: str
) -> list[tuple[list, str]]:
    """Kandidaten nach ihrer Herkunft trennen - Zucht gegen KI-Vorschlag.

    **Warum das eine eigene Funktion ist.** ``Leaderboard.record`` nimmt eine
    Herkunft je Aufruf. Wer beide Gruppen in einem Aufruf eintraegt, schreibt
    ihnen dieselbe hin - und niemand kann spaeter nachlesen, woher der beste
    Kandidat kam. Genau das waere ein stiller Fehler: Die Liste saehe richtig
    aus und waere falsch.

    Leere Gruppen fallen weg, damit kein Aufruf mit leerer Liste entsteht.
    Die Reihenfolge ist fest - erst die Zucht, dann die KI -, damit die
    Eintragung reproduzierbar bleibt (Befund 146).
    """
    von_ki = [c for c in kandidaten if c.genome.genome_id in ki_ids]
    von_zucht = [c for c in kandidaten if c.genome.genome_id not in ki_ids]
    return [
        (gruppe, quelle)
        for gruppe, quelle in ((von_zucht, herkunft), (von_ki, "KI-Vorschlag"))
        if gruppe
    ]


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


def _zeige_bestenliste(board, *, limit: int = 10, versuche: int | None = None) -> None:
    # Die Konto-Spalte erscheint erst, wenn ueberhaupt ein Eintrag sie
    # mitbringt. Sonst stuende in einer Liste aus Laeufen vor Befund 96 eine
    # Spalte voller Striche.
    konten = board.kontostaende

    table = Table(title="Bestenliste", header_style="bold")
    table.add_column("#", justify="right")
    table.add_column("Strategie")
    table.add_column("Gates", justify="right")
    if konten:
        table.add_column("Konto", justify="right")
    table.add_column("Trades", justify="right")
    table.add_column("Erwartung", justify="right")
    table.add_column("DSR", justify="right")
    table.add_column("Gescheitert an")

    for platz, eintrag in enumerate(board.best(limit, versuche=versuche), start=1):
        stil = "green" if eintrag.zugelassen else ""
        # Ein Eintrag ohne bekannte Huerde traegt eine Zahl, die nicht in
        # denselben Vergleich gehoert. Das gehoert sichtbar, nicht versteckt.
        wert = eintrag.dsr_bei(versuche) if versuche else eintrag.deflated_sharpe
        marke = "" if eintrag.vergleichbar or not versuche else " ?"
        zeile = [
            str(platz),
            f"[{stil}]{eintrag.name[:38]}[/]" if stil else eintrag.name[:38],
            f"{eintrag.gates_bestanden}/{eintrag.gates_gesamt}",
        ]
        if konten:
            zeile.append(f"{eintrag.kapital:,.0f}" if eintrag.kapital else "?")
        zeile += [
            str(eintrag.trades),
            f"{eintrag.erwartung_r:+.3f} R",
            f"{wert:.3f}{marke}",
            ", ".join(eintrag.gescheitert_an[:2]) or "-",
        ]
        table.add_row(*zeile)
    console.print(table)
    if versuche and (alt := board.unvergleichbar):
        console.print(
            f"[dim]? bei {len(alt)} von {len(board.entries)} Eintraegen: vor "
            f"dieser Aenderung gemessen, Huerde unbekannt. Ihr Wert steht, "
            f"aber er gehoert nicht in denselben Vergleich.[/]"
        )
    if len(konten) > 1:
        console.print(
            f"[yellow]Achtung: {len(konten)} verschiedene Kontostaende in "
            f"einer Liste ({', '.join(f'{k:,.0f}' for k in konten)} EUR). "
            f"Rueckgang und schlechtestes Jahr aendern ihr Urteil damit "
            f"(Befund 96) - die Gate-Spalten stehen nebeneinander, meinen aber "
            f"nicht dasselbe.[/]"
        )


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
        "",
        "--intervall",
        "-i",
        help="Handelsintervall. Leer = das der gewaehlten Generation.",
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

    Jedes Genom laeuft durch Walk-Forward und die elf Zulassungs-Gates. Wer
    alle besteht, kommt in die Auswahl; der Bestaendigste wird Champion und
    landet in ``strategies/champion.json``. Nur der wird gehandelt.

    **Dieser Befehl kostet Versuche.** Jedes gepruefte Genom ist eine getestete
    Hypothese und wird gezaehlt; der Zaehler hebt die Huerde des
    Deflated-Sharpe-Gates dauerhaft, fuer jeden kuenftigen Kandidaten. Zum
    Ausprobieren ``TRADING_TROCKENLAUF=1`` setzen - dann wird nichts
    fortgeschrieben.

    Der Docstring stand bis Befund 120 ohne diesen Hinweis da, und er nannte
    neun Gates statt elf. Genau diese Luecke hat in Befund 104 einundzwanzig
    Versuche gekostet.

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
    intervall = intervall or _standardintervall(generation)
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
        _pruefe_generation(generation, interval_obj)
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
            report.champion,
            Path(settings.paths.strategies) / "champion.json",
            bedingungen=_bedingungen(
                report.champion, config, interval_obj, report.trials_after
            ),
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
    result = propose(
        client, journal=journal, budget=budget, already_tried=tried,
        lage=_auftragslage(Path(settings.paths.state)),
        ausschluesse=_ausschluesse(),
    )
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


def _startkapital(configs) -> float:
    """Das Startkapital, mit dem tatsaechlich gerechnet wurde.

    Aus den Konfigurationen gelesen statt neben dem Lauf noch einmal
    hingeschrieben. Die Zahl steht in der Bestenliste und entscheidet dort,
    ob zwei Eintraege ueberhaupt vergleichbar sind (Befund 96) - eine
    zweite Quelle dafuer waere genau die Stelle, an der beides auseinander
    laeuft.

    Alle Beine laufen mit demselben Kapital; kaeme je Bein ein anderes
    heraus, waere die Zahl fuer die Liste ohnehin keine, und dann steht dort
    0.0 - also "unbekannt".
    """
    werte = {float(c.initial_equity) for c in configs.values()}
    return werte.pop() if len(werte) == 1 else 0.0


def _sharpe_je_trade(trades) -> float:
    """Mittleres Ergebnis je Trade in Einheiten seiner Streuung.

    **Reicht durch an ``Kandidat.aus_trades``.** Diese Groesse stand einmal an
    drei Stellen: hier und zweimal in den Befehlen, die die Grenzlinie
    zeichnen. Drei Umsetzungen derselben Zahl laufen frueher oder spaeter
    auseinander - in diesem Projekt schon viermal geschehen.
    """
    from research.suchbudget import Kandidat

    eintrag = Kandidat.aus_trades("", trades)
    return eintrag.sharpe_je_trade if eintrag is not None else 0.0


def _formkennzahlen(trades) -> dict[str, float]:
    """Qualitaet je Trade und die Form der Verteilung - in einem Griff.

    Alle drei gehen in den Deflated Sharpe ein, und alle drei kommen aus
    derselben Trade-Liste. Sie getrennt zu holen hiesse, dieselbe Rechnung
    zweimal aufzuschreiben.
    """
    from research.suchbudget import Kandidat

    eintrag = Kandidat.aus_trades("", trades)
    if eintrag is None:
        return {"sharpe_je_trade": 0.0}
    return {
        "sharpe_je_trade": eintrag.sharpe_je_trade,
        "schiefe": eintrag.schiefe or 0.0,
        "woelbung": eintrag.woelbung or 0.0,
    }


def _versuch(kennung: str, report, *, herkunft: str):
    """Einen geprueften Kandidaten fuer das Versuchsverzeichnis festhalten.

    Der Sharpe je Trade ist der Grund, warum es das Verzeichnis gibt: Aus ihm
    liesse sich die Streuung ueber die Versuche **messen**, statt sie durch
    ``1/(n-1)`` zu ersetzen (Befund 68). Er wird hier mit derselben Rechnung
    geholt wie ueberall - ``Kandidat.aus_trades`` -, damit nicht zwei
    Umsetzungen derselben Groesse auseinanderlaufen.
    """
    from research.suchbudget import Kandidat
    from research.versuche import Versuch

    trades = list(report.all_trades)
    kandidat = Kandidat.aus_trades(kennung, trades)
    return Versuch.jetzt(
        kennung,
        trades=len(trades),
        sharpe_je_trade=kandidat.sharpe_je_trade if kandidat is not None else None,
        herkunft=herkunft,
    )


def _verzeichne(pfad, versuche: list, erwartet: int) -> None:
    """Die Versuche anhaengen - und pruefen, dass die Summe stimmt.

    Der lokale Zaehler und das Verzeichnis sind zwei Wege zur selben Zahl.
    Genau diese Sorte doppelter Wahrheit ist in diesem Projekt schon mehrfach
    auseinandergelaufen, und hier waere es besonders teuer: Der Zaehler
    steuert die Haerte des Deflated-Sharpe-Gates.
    """
    from research.versuche import anhaengen

    verzeichnis = anhaengen(pfad, versuche)
    if verzeichnis.anzahl != erwartet:
        console.print(
            f"[yellow]Versuchszaehler weicht ab: Verzeichnis "
            f"{verzeichnis.anzahl}, Lauf {erwartet}. Es gilt der hoehere "
            f"Stand.[/]"
        )


def _auftragslage(zustand: Path):
    """Den gemessenen Stand fuer den Analysten zusammenstellen.

    Ohne ihn nennt der Auftrag fuenf Zulassungsschwellen, aber nicht den
    Deflated Sharpe - das einzige Gate, das noch offen ist. Der Analyst zielte
    dadurch auf 100 Trades, waehrend 120 gebraucht werden.

    Der Bestand steht als Zahl da und wird nicht neu gerechnet: Ein
    Walk-Forward nur fuer den Auftragstext waere Rechenzeit fuer nichts. Die
    Zahlen kommen aus ``research.referenz``, damit sie nicht wieder
    veralten - hier stand ``154, 0.2591`` mit dem Vermerk "seit Befund 73
    unveraendert", und beide Werte waren seit Befund 108 und 135 falsch.

    **Das hat den Analysten falsch gezielt.** Er bekam eine Guete-Luecke, die
    auf der rohen Trade-Zahl gerechnet war, und damit ein zu leichtes Ziel
    (Befund 139).
    """
    from research.admission import load_trials
    from research.auftragslage import aus_messungen
    from research.referenz import SPOTPUNKT

    return aus_messungen(
        versuche=load_trials(zustand / "trials.json"),
        bestand_trades=SPOTPUNKT.effektiv,
        bestand_sharpe=SPOTPUNKT.guete,
        # Aus Befund 75, ueber 14 Genome der Tageskerzen-Generationen.
        kopplung=-0.533,
    )


def _ausschluesse():
    """Was gemessen und geschlossen ist - fuer den Auftrag an den Analysten.

    Gegenstueck zu ``_auftragslage``: Die eine Haelfte sagt, was gebraucht
    wird, diese sagt, was dafuer ausscheidet. Ohne sie schlaegt der Analyst
    weiter Regelarten vor, die durchgemessen sind - in Befund 83 waren zwei
    von vier eigenen Vorschlaegen aus der Rueckkehr-Familie, die Befund 84
    dann geschlossen hat.

    Die Regeln stehen als Messwerte da und werden nicht neu gerechnet: Ein
    Walk-Forward ueber 22 Genome nur fuer den Auftragstext waere Rechenzeit
    fuer nichts. Die Familienzuordnung kommt aus ``familien.familie_von`` und
    nicht aus einer zweiten Liste - Regeln ohne Zuordnung fallen heraus,
    statt in einen Topf "Sonstige" zu wandern.
    """
    from research.ausschluss import (
        GEMESSENE_REGELN,
        GESCHEITERTE_EIGENBAUTEN,
        aus_familienbild,
        aus_versuchsverzeichnis,
    )
    from research.familien import Familienbild, Regel, familie_von

    # **Das Verzeichnis fuehrt, die Liste faellt zurueck** (Befund 122).
    #
    # ``GESCHEITERTE_EIGENBAUTEN`` war eine Abschrift von ``trials.json`` -
    # und hatte acht Eintraege, wo das Verzeichnis elf hat. Die drei
    # fehlenden waren die Verbuende, also genau das, worauf der Auftrag den
    # Analysten lenkt.
    settings = get_settings()
    gemessen = aus_versuchsverzeichnis(
        Path(settings.paths.state) / "trials.json"
    )
    gescheiterte = gemessen or GESCHEITERTE_EIGENBAUTEN

    regeln = []
    for name, trades, sharpe, rho in GEMESSENE_REGELN:
        familie = familie_von(name)
        if familie is None:
            continue
        regeln.append(
            Regel(
                name=name, trades=trades, sharpe_je_trade=sharpe,
                familie=familie, rho=rho,
            )
        )
    return aus_familienbild(
        Familienbild(regeln=regeln), gescheiterte=gescheiterte
    )


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

    **Und genau das stand danach weiter offen** (Befund 115). Die Tabelle
    bekam je Symbol eigene Werte, aber der Zugriff blieb
    ``_KONTRAKTE.get(symbol, _KONTRAKTE["BTCUSDT"])``: Jedes *unbekannte*
    Symbol erbte still die BTC-Werte, ``base_coin`` eingeschlossen. Gemessen:

        SOLUSDT   -> Schritt 0,001  min 0,001  max 1190  Basis BTC
        BTC-USDT  -> Schritt 0,001  min 0,001  max 1190  Basis BTC

    Ein SOL-Kontrakt mit BTC als Basiswaehrung. Die Lehre von damals stand als
    Docstring da und hat das Verhalten nicht gesteuert - dieselbe Klasse wie
    die Befunde 111 bis 114.

    Deshalb jetzt: **Unbekanntes Symbol ist ein Fehler, keine Schaetzung.**
    Ein fehlender Wert laesst sich nachtragen; ein falscher sieht aus wie ein
    Marktbefund.
    """
    from decimal import Decimal

    from core.models import Instrument

    if symbol not in _KONTRAKTE:
        bekannt = ", ".join(sorted(_KONTRAKTE))
        raise KeyError(
            f"Keine Kontraktdaten fuer '{symbol}'. Bekannt sind: {bekannt}. "
            f"Ein geratener Wert waere schlimmer als keiner - Schrittweite, "
            f"Mindest- und Hoechstmenge entscheiden, ob eine Order zustande "
            f"kommt. Nachtragen in cli._KONTRAKTE oder den Kontrakt von der "
            f"Boerse laden."
        )
    tick, schritt, mindest, hoechst, basis = _KONTRAKTE[symbol]
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
    from pathlib import Path

    from data.bybit.adapter import BybitAccount
    from data.bybit.errors import BybitAuthError, BybitError, BybitGeoBlockedError
    from data.bybit.trading import BybitTrading
    from execution.live import LiveTrader, telegram_notifier
    from execution.risk import RiskOfficer, TradingState, load_risk_state
    from execution.router import MarketKind
    from strategy.compiler import compile_genome
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

    from research.admission import lade_bedingungen, lade_champion

    geladen = lade_champion(path)
    if geladen is None:
        console.print(f"[red]{path} enthaelt kein lesbares Genom.[/]")
        raise typer.Exit(2)
    genome = geladen
    strategy = compile_genome(genome)

    # -- 2a. Wurde unter demselben Instrument zugelassen? --------------------
    #
    # Befund 106: Derselbe Kandidat steht auf einem Perpetual bei 7 von 11 und
    # auf Spot bei 9 von 11. Wer hier das Instrument wechselt, handelt etwas
    # anderes als das Gepruefte - und die Datei sagte darueber bisher nichts.
    bedingungen = lade_bedingungen(path)
    if bedingungen.vollstaendig and not bedingungen.passt_zu(markt):
        console.print(
            f"[red]Zugelassen wurde auf '{bedingungen.markt}', gehandelt "
            f"werden soll '{markt}'.[/]\n"
            f"  Nachweis: {bedingungen.als_text()}\n"
            "Die Gates gelten fuer das gepruefte Instrument, nicht fuer ein "
            "anderes. Entweder mit '--markt "
            f"{bedingungen.markt}' fahren oder die Zulassung auf dem "
            "gewuenschten Instrument wiederholen."
        )
        raise typer.Exit(2)
    if not bedingungen.vollstaendig:
        console.print(
            "[yellow]Die Champion-Datei traegt keinen Zulassungsnachweis.[/] "
            "Unter welchem Instrument, Kontostand und mit welchen Daten sie "
            "bestanden hat, steht dort nicht - ein neuer Wettbewerbslauf "
            "schreibt es mit.\n"
        )

    # -- 2b. Echtes Geld nur fuer ein zugelassenes Genom ---------------------
    #
    # Die Sperre oben fragt nach der *Umgebung*, diese nach der **Strategie**.
    # Beides ist noetig, seit ``cli anlagentest`` einen nicht zugelassenen
    # Kandidaten als Datei ablegen kann: Ohne diese Pruefung wuerde
    # ``--echtgeld --strategie anlagentest.json`` echtes Geld auf etwas
    # setzen, das vier Gates nicht bestanden hat.
    #
    # Verglichen wird die Kennung gegen champion.json, nicht der Dateiname -
    # eine Datei laesst sich umbenennen, der Hash ueber die Regeln nicht.
    from research.admission import ist_zugelassen

    zugelassen = ist_zugelassen(
        genome, Path(settings.paths.strategies) / "champion.json"
    )
    if settings.bybit.environment.is_real_money and not zugelassen:
        console.print(
            "[red]Dieses Genom ist nicht zugelassen - kein echtes Geld.[/]\n"
            f"  {genome.name} [{genome.genome_id}]\n"
            "Echtgeld gibt es nur fuer den Champion aus champion.json, und der "
            "entsteht erst, wenn alle elf Gates bestanden sind.\n"
            "[dim]Auf Demo laeuft dieses Genom - dort wird die Technik "
            "geprueft, nicht die Strategie.[/]"
        )
        raise typer.Exit(2)

    if not zugelassen:
        console.print(
            "\n[yellow]ANLAGENTEST - dieses Genom ist nicht zugelassen.[/]\n"
            f"  {genome.name} [{genome.genome_id}]\n"
            "[dim]Geprueft wird die Technik: Orders, Stops, Neustart mitten in "
            "einer Position, Meldungen, Not-Aus.\n"
            "**Die dreissig Tage Demo aus dem Plan beginnen hiermit nicht** - "
            "die pruefen eine Strategie gegen ihre Backtest-Erwartung, und "
            "diese hier hat ihre Gates noch nicht bestanden.[/]\n"
        )

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


def _bedingungen(candidate, configs, interval_obj, versuche: int):
    """Der Zulassungsnachweis eines Laufs - aus dem Lauf gelesen.

    Alles hier kommt aus dem, was tatsaechlich gerechnet wurde: das Instrument
    aus Funding und Hebeldeckel, der Kontostand aus den Konfigurationen, die
    Datenquelle aus dem Gate-Bericht. Nichts davon wird danebengeschrieben.
    """
    from research.admission import Zulassungsbedingungen

    werte = list(configs.values()) if hasattr(configs, "values") else [configs]
    return Zulassungsbedingungen(
        markt=_marktart(configs, candidate.genome),
        kapital=_startkapital(
            configs if hasattr(configs, "values") else {"x": configs}
        ),
        intervall=interval_obj.value,
        referenzdaten=bool(getattr(candidate.gates, "referenzdaten", False)),
        versuche=versuche,
        bestanden=sum(1 for r in candidate.gates.results if r.passed),
        gesamt=len(candidate.gates.results),
        funding_satz=float(werte[0].funding.default_rate) if werte else 0.0,
        zeitpunkt=datetime.now(UTC).isoformat(),
    )


def _marktart(configs, genome) -> str:
    """Welches Instrument ein Lauf tatsaechlich abgebildet hat.

    Abgeleitet und nicht danebengeschrieben: Der Backtest kennt keinen
    Schalter fuer das Instrument, er kennt Funding und einen Hebeldeckel.
    Wird Funding belastet oder darf die Position ueber das eigene Kapital
    hinaus, war es ein Perpetual - sonst ein Kassageschaeft.

    Eine zweite Quelle waere die Stelle, an der Nachweis und Lauf
    auseinanderlaufen; in diesem Projekt schon mehrfach geschehen.
    """
    werte = list(configs.values()) if hasattr(configs, "values") else [configs]
    funding = any(float(c.funding.default_rate) > 0 for c in werte)
    hebel = float(genome.sizing.fraction) > 1.0
    return "perpetual" if (funding or hebel) else "spot"


def _teststaerke_ueber_saaten(
    saaten: str, anteile, frames, configs, genome, versuche: int, dauer: int,
    spanne, symbole, interval_obj,
) -> None:
    """Dieselbe Leiter ueber mehrere Ziehungen - mit Streuung und t-Wert.

    Der Unterschied zur einzelnen Saat ist nicht Genauigkeit, sondern
    Zulaessigkeit: Ohne Streuung gibt es keinen Massstab, an dem ein Abstand
    zwischen zwei Sprossen gross oder klein waere. ``research/ziehung.py``
    setzt das durch - eine Sprosse aus einer Ziehung liefert ``None``.

    **Kostet keinen Versuch.** Geprueft wird die Strecke, keine Regel.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.gates import evaluate_gates
    from research.suchbudget import Kandidat
    from research.teststaerke import pflanze_trend, regimefolge
    from research.ziehung import Leiter, Sprosse, Ziehung
    from strategy.compiler import compile_genome

    try:
        werte = sorted({int(x) for x in saaten.split(",") if x.strip()})
    except ValueError:
        console.print(f"[red]'{saaten}' sind keine ganzen Zahlen.[/]")
        raise typer.Exit(2) from None
    if len(werte) < 2:
        console.print(
            "[red]Mindestens zwei Saaten.[/] Mit einer gibt es keine Streuung "
            "zu messen - dann ist der einfache Lauf ohne --saaten ehrlicher."
        )
        raise typer.Exit(2)

    console.print(
        f"\n[bold]Teststaerke ueber Ziehungen[/] {' + '.join(symbole)} "
        f"{interval_obj.label}\n"
        f"  Historie   {spanne} Tage gemeinsam\n"
        f"  Regime     im Mittel {dauer} Kerzen, ein Verlauf fuer alle Beine\n"
        f"  Huerde     {versuche} Versuche (gelesen, nicht erhoeht)\n"
        f"  Ziehungen  {len(werte)} Saaten x {len(anteile)} Sprossen\n"
    )

    laenge = max(len(f) for f in frames.values())
    sprossen: dict[float, Sprosse] = {a: Sprosse(anteil=a) for a in anteile}
    with console.status("[dim]rechnet...[/]"):
        for saat_wert in werte:
            regime = regimefolge(laenge, dauer=dauer, saat=saat_wert)
            for anteil in anteile:
                gepflanzt = {
                    name: pflanze_trend(frame, anteil=anteil, regime=regime)
                    for name, frame in frames.items()
                }
                bericht = run_portfolio_walkforward(
                    gepflanzt, lambda: compile_genome(genome), configs
                )
                if not bericht.windows:
                    continue
                erster = next(iter(gepflanzt.values()))
                gates = evaluate_gates(
                    genome, bericht, erster, next(iter(configs.values())),
                    trials_so_far=versuche, frames=gepflanzt, configs=configs,
                )
                form = Kandidat.aus_trades("", bericht.all_trades)
                dsr = next(
                    (r.value for r in gates.results if r.name == "Deflated Sharpe"),
                    None,
                )
                sprossen[anteil].ziehungen.append(
                    Ziehung(
                        saat=saat_wert, anteil=anteil,
                        trades=len(bericht.all_trades),
                        sharpe_je_trade=form.sharpe_je_trade if form else 0.0,
                        dsr=float(dsr) if dsr is not None else 0.0,
                        bestanden=sum(1 for r in gates.results if r.passed),
                        gesamt=len(gates.results),
                        cagr_pct=(
                            float(bericht.combined.cagr_pct)
                            if bericht.combined else 0.0
                        ),
                    )
                )

    lage = Leiter(sprossen=list(sprossen.values()))
    console.print(
        f"  {'Anteil':>7}  {'Trades':>14}  {'SR je Trade':>17}  "
        f"{'DSR':>17}  {'Gates':>11}"
    )
    for anteil in anteile:
        s = sprossen[anteil]
        if not s.ziehungen:
            continue

        def spalte(groesse: str, stellen: int, sp=s) -> str:
            mittel, streuung = sp.mittel(groesse), sp.streuung(groesse)
            if mittel is None:
                return "-"
            if streuung is None:
                return f"{mittel:.{stellen}f}"
            return f"{mittel:.{stellen}f} +-{streuung:.{stellen}f}"

        console.print(
            f"  {anteil:>7.0%}  {spalte('trades', 1):>14}  "
            f"{spalte('sharpe_je_trade', 4):>17}  {spalte('dsr', 4):>17}  "
            f"{spalte('bestanden', 1):>11}"
        )

    # Die Schranke steigt mit der Zahl der Vergleiche - fuenf Sprossen ueber
    # der Null sind fuenf Hypothesen, und |t| >= 2 waere dann zu milde.
    ueber_null = [a for a in anteile if a > 0.0]
    console.print()
    for groesse in ("sharpe_je_trade", "trades", "dsr"):
        console.print(f"  [bold]{groesse}[/] gegen die 0-%-Sprosse:")
        for anteil in ueber_null:
            u = lage.vergleich(0.0, anteil, groesse=groesse)
            if u is None:
                console.print(
                    f"    [dim]{anteil:.0%}: kein Vergleich moeglich.[/]"
                )
                continue
            farbe = "green" if u.belegt(len(ueber_null)) else "dim"
            console.print(f"    [{farbe}]{u.als_text(len(ueber_null))}[/]")
        console.print()

    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert: Geprueft wird die "
        "Strecke, keine Regel.[/]\n"
    )


def _ohne_hebel(genome):
    """Denselben Kandidaten ohne Hebel - **gedeckelt, nicht gesetzt.**

    ``fraction`` ist ein Vielfaches: Der Spitzenkandidat steht auf 3,0, und
    ihn auf 1,0 zu setzen nimmt ihm den Hebel. Ein Genom mit 0,4 wuerde davon
    aber **groesser**, nicht kleiner - beim ersten Anlauf zu Befund 168 hat
    genau das den halben Katalog verzerrt, bevor es auffiel. Gedeckelt wird
    nach oben.

    Genome ohne ``sizing`` bleiben, wie sie sind.
    """
    sizing = getattr(genome, "sizing", None)
    if sizing is None or getattr(sizing, "fraction", None) is None:
        return genome
    return genome.model_copy(
        update={
            "sizing": sizing.model_copy(
                update={"fraction": min(sizing.fraction, 1.0)}
            )
        }
    )


def _spotconfigs(symbole, settings):
    """Die Handelsbedingungen des Spot-Punkts: kein Funding, kein Hebel.

    Stand bis Befund 168 **zweimal** wortgleich da - in ``_spotguete`` und in
    ``_spotpunkt``. Zwei Stellen mit derselben Einstellung laufen in diesem
    Projekt frueher oder spaeter auseinander; der dritte Aufrufer haette sie
    ein drittes Mal nachgebaut.
    """
    from decimal import Decimal

    from backtest.costs import FundingSchedule
    from backtest.engine import BacktestConfig

    configs = {}
    for x in symbole:
        grund = BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        configs[x] = BacktestConfig(
            instrument=grund.instrument, risk=grund.risk, costs=grund.costs,
            funding=FundingSchedule(default_rate=Decimal("0")),
            initial_equity=grund.initial_equity, enforce_risk_limits=True,
            allow_shorts=grund.allow_shorts,
            entry_expiry_bars=grund.entry_expiry_bars,
            max_hold_bars=grund.max_hold_bars, kalender=grund.kalender,
        )
    return configs


def _spotguete(frames, symbole, genome, settings) -> float | None:
    """Die Guete desselben Kandidaten unter Kassa-Bedingungen.

    Nur die eine Zahl, ohne Gate-Auswertung - fuer Berichte, die am
    Perpetual-Punkt rechnen und den zweiten daneben zeigen sollen (Befund
    112, hier fuer ``cli form`` nachgezogen).

    **Kostet keinen Versuch.** Derselbe Kandidat, dieselben Daten, andere
    Handelsbedingungen. ``None``, wenn der Lauf nicht zustandekommt.
    """

    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.suchbudget import Kandidat
    from strategy.compiler import compile_genome

    ohne_hebel = _ohne_hebel(genome)
    configs = _spotconfigs(symbole, settings)

    bericht = run_portfolio_walkforward(
        frames, lambda: compile_genome(ohne_hebel), configs
    )
    if not bericht.windows:
        return None
    eintrag = Kandidat.aus_trades(genome.name, bericht.all_trades)
    return eintrag.sharpe_je_trade if eintrag else None


def _familie(genome) -> str:
    """Die Familie eines Genoms: seine Einstiegsindikatoren.

    Strukturell aus dem Genom gelesen und nicht aus dem Namen - "Trend mit
    Vola-Ziel 22 %" und "Trend-Beteiligung 50 Tage" heissen verschieden und
    sind dieselbe Familie. Eine Einteilung nach Namen waere eine Meinung.
    """
    namen = {
        s.name
        for abschnitt in (genome.entry_long, genome.entry_short)
        for c in abschnitt
        for s in (c.left, c.right)
        if s.kind == "indicator"
    }
    return "+".join(sorted(namen)) or "ohne Indikator"


def _spotpunkt(frames, symbole, genome, trials: int, settings):
    """Derselbe Kandidat unter Kassa-Bedingungen - kein Hebel, kein Funding.

    Gemessen und nicht nachgeschlagen: Die Zahlen aus Befund 108 hier
    hinzuschreiben waere eine zweite Kopie neben dem Lauf, und genau daran ist
    dieses Projekt schon dreimal haengengeblieben (Befunde 101, 103, 109).

    **Kostet keinen Versuch.** Dieselbe Regel, dieselben Daten, andere
    Handelsbedingungen - kein neuer Einfall, ueber den zu buchfuehren waere.

    Gibt ``None`` zurueck, wenn der Lauf nicht zustandekommt; der Bericht
    laesst den Abschnitt dann weg, statt mit einer Luecke dazustehen.
    """

    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.betriebspunkt import Betriebspunkt
    from research.gates import evaluate_gates
    from research.suchbudget import Kandidat
    from strategy.compiler import compile_genome

    ohne_hebel = _ohne_hebel(genome)
    configs = _spotconfigs(symbole, settings)

    bericht = run_portfolio_walkforward(
        frames, lambda: compile_genome(ohne_hebel), configs
    )
    if not bericht.windows:
        return None

    erster = next(iter(frames.values()))
    gates = evaluate_gates(
        ohne_hebel, bericht, erster, configs[symbole[0]], trials_so_far=trials,
        frames=frames, configs=configs,
    )
    eintrag = Kandidat.aus_trades(ohne_hebel.name, bericht.all_trades)
    kombiniert = bericht.combined
    return Betriebspunkt(
        name="Spot",
        trades=len(bericht.all_trades),
        cagr_pct=float(kombiniert.cagr_pct) if kombiniert else 0.0,
        rueckgang_pct=float(kombiniert.max_drawdown_pct) if kombiniert else 0.0,
        guete=eintrag.sharpe_je_trade if eintrag else 0.0,
        dsr=float(
            next(r.value for r in gates.results if r.name == "Deflated Sharpe")
        ),
        bestanden=sum(1 for r in gates.results if r.passed),
        gesamt=len(gates.results),
        offen=tuple(r.name for r in gates.results if not r.passed),
    )


def _dauer(sekunden: float) -> str:
    """Eine Laufzeit so schreiben, dass sie etwas sagt.

    "rund 0 Minuten" ist keine Auskunft. Unter einer Minute stehen Sekunden,
    darueber Minuten, ab einer Stunde Stunden und Minuten.
    """
    if sekunden < 60:
        return f"{sekunden:.0f} Sekunden"
    if sekunden < 3600:
        return f"{sekunden / 60:.0f} Minuten"
    stunden, rest = divmod(int(sekunden), 3600)
    return f"{stunden} Stunden {rest // 60} Minuten"


def _standardintervall(generation: int) -> str:
    """Die Kerzenlaenge, fuer die eine Generation gedacht ist.

    **Warum das kein zweiter Standardwert sein darf.** ``cli wettbewerb`` stand
    auf Generation 8 und Intervall 15, und Generation 8 ist der
    Tageskerzen-Katalog: Der Befehl brach mit seinen **eigenen** Voreinstellungen
    ab, mit Exit 2 und der Meldung von ``_pruefe_generation``. Beim Umstellen
    des Katalog-Standards wurde die zweite Stelle vergessen - genau die Sorte
    Drift, die entsteht, wenn dieselbe Zuordnung an zwei Orten steht.

    ``VORGESEHEN`` ist die Zuordnung, seit Befund 64 als Daten. Der Standard
    liest sie, statt sie zu wiederholen.

    Generationen ohne Vorgabe (1 bis 4) bekommen Tageskerzen: Dort steht der
    Kandidat, und dort liegen die Kataloge, die eine Vorgabe haben.
    """
    from research.seeds import VORGESEHEN

    return VORGESEHEN.get(generation) or "D"


def _pruefe_generation(generation: int, interval_obj) -> None:
    """Ist dieser Katalog fuer diese Kerzenlaenge gedacht?

    **Bis hierher stand die Zuordnung nur in Kommentaren.** Generation 6 heisst
    dort "schnelles Handeln auf 15-Minuten-Kerzen", Generation 7 ist der
    "Katalog der bekannten Scalp-Setups" - und nichts hinderte daran, sie auf
    Tageskerzen zu fahren. Dieselben Periodenzahlen bedeuten dort
    sechsundneunzigmal laengere Zeitraeume: eine voellig andere Regel unter
    demselben Namen.

    Abgebrochen und nicht nur gewarnt, weil so ein Lauf **Versuche kostet**.
    Jeder hebt die Huerde des Deflated Sharpe fuer alle folgenden, und zwar
    dauerhaft - fuer eine Messung, die nichts bedeutet.
    """
    from research.seeds import VORGESEHEN, passt_zum_intervall

    if passt_zum_intervall(generation, interval_obj.value):
        return
    vorgesehen = VORGESEHEN.get(generation)
    console.print(
        f"[red]Generation {generation} ist fuer {vorgesehen}-Kerzen gedacht, "
        f"nicht fuer {interval_obj.label}.[/]\n"
        f"[dim]Dieselben Periodenzahlen bedeuten hier andere Zeitraeume - das "
        f"waere eine andere Regel unter demselben Namen, und sie wuerde "
        f"Versuche kosten. Mit [bold]-i {vorgesehen}[/] laufen lassen oder "
        f"eine passende Generation waehlen.[/]"
    )
    raise typer.Exit(2)


def _korb_daten(symbole: list[str], interval_obj: Interval, settings):
    """Kerzen und Kontraktdaten fuer einen Korb - fuer alle, die ihn pruefen.

    Diese vierzig Zeilen standen einmal nur in ``korb``. Als der zweite Befehl
    denselben Korb messen musste, waere die naheliegende Loesung gewesen, sie
    zu kopieren - und damit haette es zwei Stellen gegeben, an denen steht,
    was "der Korb" eigentlich ist. Genau das ist in diesem Projekt schon
    viermal auseinandergelaufen.

    Der gemeinsame Zeitraum ist dabei kein Detail: ``common_range`` schneidet
    alle Maerkte auf dieselbe Spanne, sonst vergleicht man ein Bein mit mehr
    Historie gegen eines mit weniger und haelt den Unterschied fuer Strategie.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range
    from data.bybit.errors import BybitError

    store = CandleStore(settings.paths.data_store)
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

    return frames, configs, spanne


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

    **Dieser Befehl kostet Versuche** - gemessen sieben (Befund 120). Er sagte
    es bis dahin nicht, und eine Textsuche im Funktionskoerper fand es auch
    nicht: Der Zaehler wird ueber eine Hilfsfunktion fortgeschrieben, nicht
    hier. Aufgefallen ist es erst, als der Trockenlauf seinen unterdrueckten
    Schreibvorgang meldete.

    Zum Ausprobieren ``TRADING_TROCKENLAUF=1`` setzen.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.gates import evaluate_gates
    from research.seeds import load_seeds
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)

    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)
    erster = next(iter(frames.values()))

    trials_path = Path(settings.paths.state) / "trials.json"
    from research.admission import load_trials

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

    _pruefe_generation(generation, interval_obj)
    bester = None
    gezaehlt: list = []
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
        gezaehlt.append(
            _versuch(angepasst.name, report, herkunft=f"wettbewerb g{generation}")
        )
        gates = evaluate_gates(
            angepasst, report, erster, next(iter(configs.values())),
            trials_so_far=trials, frames=frames, configs=configs,
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

    _verzeichne(trials_path, gezaehlt, trials)
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
def vorschlag(
    datei: Path | None = typer.Option(
        None, "--datei", "-d",
        help="Antwortdatei statt Modellaufruf. Kostet nichts, zaehlt gleich.",
    ),
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    vola_ziel: float = typer.Option(50.0, help="Vola-Ziel in Prozent."),
    auftrag: bool = typer.Option(
        False, "--auftrag",
        help="Nur den Auftrag ausgeben, nichts messen. Fuer --datei.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Vorschlaege der Research-KI durch alle elf Gates - statt nur Varianten.

    **Warum das fehlte.** Der Wettbewerb erzeugt neue Kandidaten durch
    Mutation: Er nimmt die Besten und variiert ihre *Zahlen*. Damit bleibt die
    Struktur, was sie ist - eine Schnittkreuzung mit anderen Perioden ist
    dieselbe Regel mit anderen Perioden. Der Analyst kann strukturell Neues
    vorschlagen, wurde aber nie gerufen, weil ihm der Weg in die Messung
    fehlte. Zwei fertige Haelften ohne Verbindung.

    **Was hier passiert und was ausdruecklich nicht.** Der Vorschlag geht
    durch ``parse_proposals`` - wer die Grenzen des Genoms verletzt, wird
    abgelehnt und nicht repariert. Wer sie einhaelt, bekommt genau das, was
    ein von Hand geschriebener Kandidat bekommt: dieselben elf Gates,
    dieselben Schwellen, und **einen Versuch im Zaehler**. Der letzte Punkt
    ist der wichtigste: Ein Vorschlag aus einem Modell ist keinen Deut
    glaubwuerdiger als einer aus einer Schleife, und er hebt die Huerde des
    Deflated Sharpe fuer alle folgenden um dieselben 0,00021.

    **Woher die Antwort kommt, steht dran.** Ohne ``--datei`` wird das Modell
    gefragt und das Forschungsbudget belastet. Mit ``--datei`` liest der
    ``DateiClient`` eine bereits vorliegende Antwort - der Auftrag ist
    derselbe (``--auftrag`` zeigt ihn), der Weg danach ist derselbe, nur der
    Aufruf entfaellt. Die Herkunft wandert in die Bestenliste, damit sich
    spaeter niemand darauf berufen kann, "die KI" habe etwas gefunden, was
    jemand von Hand hingeschrieben hat.
    """
    from research.analyst import (
        SYSTEM_PROMPT,
        AnthropicClient,
        DateiClient,
        build_prompt,
        load_budget,
        propose,
        save_budget,
    )
    from research.gates import GateThresholds

    _configure_logging(verbose)
    settings = get_settings()
    state = Path(settings.paths.state)

    lage = _auftragslage(state)

    if auftrag:
        console.print(SYSTEM_PROMPT)
        console.print(
            build_prompt(
                journal=[], thresholds=GateThresholds(), lage=lage,
                ausschluesse=_ausschluesse(),
            )
        )
        return

    from research.leaderboard import Leaderboard

    board = Leaderboard(state / "leaderboard.json")
    bekannt = set(board.entries)

    budget = load_budget(
        state / "budget.json",
        monthly_usd=settings.cost.profile.monthly_budget_usd,
    )
    if datei is not None:
        client = DateiClient(datei)
        herkunft = f"Vorschlag ({datei.name})"
        console.print(f"[dim]Antwort aus {datei} - kein Modellaufruf.[/]")
    else:
        if not settings.llm.has_credentials:
            console.print(
                "[yellow]Kein LLM__ANTHROPIC_API_KEY gesetzt.[/] Entweder den "
                "Schluessel setzen oder mit [bold]--datei[/] eine Antwort "
                "vorlegen; [bold]--auftrag[/] zeigt, was zu beantworten ist."
            )
            raise typer.Exit(2)
        client = AnthropicClient(settings.llm.anthropic_api_key.get_secret_value())
        herkunft = "Analyst"

    ergebnis = propose(
        client, journal=[], budget=budget, already_tried=bekannt, lage=lage,
        ausschluesse=_ausschluesse(),
    )
    if datei is None:
        save_budget(state / "budget.json", budget)
    console.print(f"[dim]{ergebnis.summary()}[/]")
    for p in ergebnis.proposals:
        if not p.accepted:
            console.print(f"  [red]abgelehnt[/] {p.genome.name}: {p.reason}")
    if not ergebnis.genomes:
        console.print("[yellow]Kein brauchbarer Vorschlag - nichts zu messen.[/]")
        raise typer.Exit(1)

    _miss_vorschlaege(
        ergebnis.genomes,
        maerkte=maerkte,
        intervall=intervall,
        vola_ziel=vola_ziel,
        herkunft=herkunft,
        settings=settings,
        board=board,
    )


def _miss_vorschlaege(
    genome_liste, *, maerkte, intervall, vola_ziel, herkunft, settings, board
) -> None:
    """Die angenommenen Vorschlaege durch den Korb und die elf Gates.

    Die Groessenlogik wird fuer alle gleich gestellt - aus demselben Grund wie
    in ``korb``: Sonst vergleicht man Hebelstufen und haelt das Ergebnis fuer
    einen Unterschied zwischen den Regeln.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import evaluate_gates
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec

    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)
    erster = next(iter(frames.values()))

    trials_path = Path(settings.paths.state) / "trials.json"
    trials = load_trials(trials_path)
    console.print(
        f"\n[bold]Vorschlaege[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Gemeinsam  {erster['open_time'].iloc[0]:%Y-%m-%d} bis "
        f"{erster['open_time'].iloc[-1]:%Y-%m-%d} ({spanne} Tage)\n"
        f"  Versuche   {trials} bisher, {len(genome_liste)} kommen dazu\n"
    )

    tabelle = Table(header_style="bold")
    tabelle.add_column("Vorschlag")
    tabelle.add_column("Gates", justify="right")
    tabelle.add_column("Trades", justify="right")
    tabelle.add_column("Sharpe", justify="right")
    tabelle.add_column("DSR", justify="right")
    tabelle.add_column("Gescheitert an")

    bester = None
    gezaehlt: list = []
    for genome in genome_liste:
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
            tabelle.add_row(angepasst.name[:30], "-", "0", "-", "-", "kein Fenster")
            continue

        trials += 1
        gezaehlt.append(_versuch(angepasst.name, report, herkunft=herkunft))
        gates = evaluate_gates(
            angepasst, report, erster, next(iter(configs.values())),
            trials_so_far=trials, frames=frames, configs=configs,
        )
        bestanden = sum(1 for r in gates.results if r.passed)
        dsr = next(
            (r.value for r in gates.results if r.name == "Deflated Sharpe"), None
        )
        stil = "green" if gates.passed else ""
        tabelle.add_row(
            f"[{stil}]{angepasst.name[:30]}[/]" if stil else angepasst.name[:30],
            f"{bestanden}/{len(gates.results)}",
            str(len(report.all_trades)),
            f"{report.combined.sharpe:.2f}" if report.combined else "-",
            f"{dsr:.3f}" if dsr is not None else "-",
            ", ".join(r.name for r in gates.failures)[:40] or "-",
        )
        board.record(
            [_kandidat_aus_lauf(angepasst, report, gates)],
            generation=0, herkunft=herkunft, versuche=trials,
            intervall=interval_obj.value, kapital=_startkapital(configs),
        )
        if bester is None or bestanden > bester[0]:
            bester = (bestanden, angepasst, gates)

    _verzeichne(trials_path, gezaehlt, trials)
    board.save()
    console.print(tabelle)

    if bester is None:
        console.print("[red]Kein Vorschlag liess sich rechnen.[/]")
        raise typer.Exit(2)

    anzahl, genome, gates = bester
    console.print(f"\n[bold]Bester: {genome.name}[/] - {anzahl}/{len(gates.results)}")
    console.print(f"[dim]{genome.rationale[:300]}[/]\n")
    for r in gates.results:
        farbe = {"pass": "green", "fail": "red", "skip": "dim"}[r.status.value]
        zeichen = {"pass": "OK", "fail": "--", "skip": ".."}[r.status.value]
        console.print(
            f"  [{farbe}]{zeichen}[/] {r.name:22s} "
            f"{r.value:>9.3f} / {r.threshold:>8.3f}  [dim]{r.message[:50]}[/]"
        )
    console.print(
        f"\n[dim]Versuchszaehler jetzt {trials}. Ein Vorschlag aus einem "
        f"Modell kostet denselben Versuch wie jeder andere Kandidat.[/]"
    )


def _regeln_aus_datei(pfad: Path) -> list[tuple[str, object]]:
    """Regelvorschlaege fuer die Vorauswahl auf gepflanzten Reihen.

    **Derselbe Weg wie in ``cli vorschlag``** - dieselbe Datei, dieselbe
    Pruefung durch ``parse_proposals``, dieselbe Ablehnung statt Reparatur.
    Der einzige Unterschied ist, wogegen gemessen wird: dort die echte Reihe
    und elf Gates, hier gepflanzte Reihen und die Frage, ob eine Regel einen
    vorhandenen Vorteil ueberhaupt in Guete umsetzt.

    Diese Vorauswahl kostet keinen Versuch, und das ist kein Trick, sondern
    eine Bedingung: Sie sieht die unveraenderte Wirklichkeit nicht (die
    0-%-Sprosse faellt weg), also kann sie sich auch nicht an ihr
    ueberanpassen. Was hier gut aussieht, muss danach durch alle elf Gates -
    und **dann** zaehlt es.
    """
    from research.analyst import parse_proposals

    if not pfad.exists():
        console.print(f"[red]{pfad} gibt es nicht.[/]")
        raise typer.Exit(2)

    from research.seeds import spitzenkandidat

    vorschlaege = parse_proposals(pfad.read_text())
    angenommen = [p.genome for p in vorschlaege if p.accepted]
    for p in vorschlaege:
        if not p.accepted:
            console.print(f"  [red]abgelehnt[/] {p.genome.name}: {p.reason}")
    if not angenommen:
        console.print("[red]Kein brauchbarer Vorschlag in der Datei.[/]")
        raise typer.Exit(2)

    # **Alle auf die Groessenlogik des Bestands stellen - und hier ist das
    # richtig.** In Befund 54 war genau diese Normalisierung ein Fehler: Dort
    # lief ein einziges Genom durch die Leiter, und das Gleichstellen verschob
    # bloss den Ankerpunkt. Hier laufen mehrere verschiedene Genome
    # gegeneinander, und das ist der Fall, fuer den ``korb`` sie eingefuehrt
    # hat.
    #
    # Ohne sie war die erste Messung wertlos: Vorschlaege kommen mit
    # ``risiko``-Groessenlogik, die am Stop-Abstand bemisst und einen
    # 4-%-Stop als zu weit **ablehnt**. Ergebnis waren null Trades in jeder
    # Spalte - auch beim Bestand, der dort 48 haben muss. Verglichen wurden
    # Groessenlogiken, nicht Einstiegsstrukturen.
    groesse = spitzenkandidat().sizing
    # **Der volle Name, nicht die ersten vierzehn Zeichen.** Die Kuerzung sass
    # hier, um in eine 16 Zeichen breite Spalte zu passen - und wanderte damit
    # in die Schluesselmenge von ``Vergleich.leitern``. Das Urteil nennt die
    # Variante beim Namen, und seit Befund 178 stand dort "**Neues Hoch im **
    # raeumt die Latte". Die Spaltenbreite ist eine Sache der Darstellung; sie
    # richtet sich jetzt in ``Vergleich.matrix`` nach dem laengsten Namen.
    return [(g.name, g.model_copy(update={"sizing": groesse})) for g in angenommen]


def _kandidat_aus_lauf(genome, report, gates):
    """Ein Laufergebnis in die Form bringen, die die Bestenliste erwartet.

    Der Portfolio-Walk-Forward liefert denselben Berichtstyp wie der einzelne
    - deshalb passt der Kandidat aus ``admission`` hier unveraendert, und die
    Bestenliste sieht keinen Unterschied zwischen einem Vorschlag und einem
    Kandidaten aus dem Wettbewerb. Das ist Absicht: Verglichen wird das
    Ergebnis, nicht die Herkunft.
    """
    from research.admission import Candidate

    return Candidate(genome=genome, walkforward=report, gates=gates)


@app.command()
def scan(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("15", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Steckt in dieser Zeitreihe ueberhaupt ein Vorteil? Vor jeder Suche.

    **Kostet keinen Versuch.** Geprueft wird nicht eine handelbare Regel,
    sondern die Struktur des Marktes: Sagt die Vergangenheit etwas ueber die
    Zukunft, und ist das mehr als die Gebuehren?

    Der Grund fuer diese Reihenfolge steht in ``cli abstand``: Jede gepruefte
    Hypothese hebt die Huerde des Deflated-Sharpe-Gates dauerhaft. Erst
    schauen, ob etwas da ist - dann Versuche ausgeben.

    Eine Zelle zaehlt erst als Fund, wenn sie auffaellt (|t| >= 2), in
    **beiden Haelften** des Zeitraums dasselbe Vorzeichen hat und nach
    Gebuehren etwas uebrig laesst. Die mittlere Huerde ist die, an der der
    erste 15-Minuten-Fund gescheitert ist.
    """
    from research.vorteilsscan import (
        KOSTEN_MAKER_MAKER,
        pruefe_stabilitaet,
        scanne,
        urteil,
    )

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    # Rueckblick und Haltedauer in Balken. Bewusst ein grobes Raster ueber
    # mehrere Groessenordnungen: Es geht um die Frage, **ob** irgendwo etwas
    # ist, nicht um den besten Parameter. Ein feines Raster waere schon der
    # Anfang einer Ueberanpassung.
    raster = [4, 8, 16, 32, 48, 96, 192, 480, 960]

    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            continue
        close = frame["close"].to_numpy(dtype=float)
        zellen = scanne(close, raster, raster)
        if not zellen:
            console.print(f"[red]{symbol}: zu wenig Daten.[/]")
            continue

        console.print(
            f"\n[bold]{symbol}[/] {interval_obj.label}, {len(frame)} Kerzen "
            f"({frame['open_time'].iloc[0]:%Y-%m-%d} bis "
            f"{frame['open_time'].iloc[-1]:%Y-%m-%d})"
        )
        tabelle = Table(header_style="bold")
        tabelle.add_column("Rueckblick", justify="right")
        tabelle.add_column("Halten", justify="right")
        tabelle.add_column("n", justify="right")
        tabelle.add_column("Spanne", justify="right")
        tabelle.add_column("t", justify="right")
        tabelle.add_column("in Kosten", justify="right")
        tabelle.add_column("netto/Trade", justify="right")
        for z in zellen[:6]:
            netto = z.netto_pct()
            tabelle.add_row(
                str(z.rueckblick), str(z.halten), str(z.beobachtungen),
                f"{z.spanne_pct:+.4f}%", f"{z.t_wert:+.2f}",
                f"{z.kosten_vielfaches():.2f}x",
                f"[{'green' if netto > 0 else 'red'}]{netto:+.4f}%[/]",
            )
        console.print(tabelle)

        beste = zellen[0]
        stabil = pruefe_stabilitaet(close, beste.rueckblick, beste.halten)
        console.print(
            urteil(beste, stabil, KOSTEN_MAKER_MAKER, gepruefte_zellen=len(zellen))
        )

    console.print(
        f"\n[dim]Kosten je Roundtrip: {0.04:.2f} % vom Nominalwert "
        f"(beide Seiten Limit). Die Spanne ist der Unterschied zwischen zwei "
        f"Zustaenden - eine Regel erntet davon grob die Haelfte.[/]\n"
    )


@app.command()
def nullprobe(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    laeufe: int = typer.Option(40, "--laeufe", "-n", help="Gemischte Reihen."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Findet die Maschine einen Vorteil, wo garantiert keiner ist?

    Die Frage, die unter allen anderen liegt. Alle Zahlen dieses Projekts
    kommen aus derselben Zulassungsstrecke. Erzeugt die selbst einen Vorteil -
    durch Lookahead, durch einen Fehler in der Fensterlogik -, ist jede
    Messung wertlos, ohne dass irgendetwas nach einem Fehler aussieht.

    Geprueft wird mit gemischten Renditen: dieselbe Verteilung, dieselbe
    Schwankungsbreite, derselbe Drift - aber keine zeitliche Struktur mehr.
    Auf so einer Reihe **muss** eine Trendfolge verlieren.

    Zwei Ergebnisse, beide noetig: Auf gemischten Reihen darf nichts verdient
    werden, und die echte Reihe muss sich abheben.

    Kostet keinen Versuch - geprueft wird die Maschine, keine Regel.
    """
    from decimal import Decimal

    import numpy as np

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.nullprobe import (
        Nullergebnis,
        Nullverteilung,
        kaufen_und_halten_pct,
        mische_renditen,
    )
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    genome = spitzenkandidat()
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    def lauf(reihen) -> Nullergebnis:
        bericht = run_portfolio_walkforward(
            reihen, lambda: compile_genome(genome), configs
        )
        if not bericht.windows:
            return Nullergebnis(0, 0.0, 0.0, 0.0)
        r = [
            float(t.r_multiple)
            for t in bericht.all_trades
            if t.r_multiple is not None
        ]
        return Nullergebnis(
            trades=len(bericht.all_trades),
            erwartung_r=float(np.mean(r)) if r else 0.0,
            ertrag_pct=float(bericht.combined.total_return_pct),
            kaufen_halten_pct=float(
                np.mean([kaufen_und_halten_pct(f) for f in reihen.values()])
            ),
        )

    console.print(
        f"\n[bold]Nullprobe[/] {' + '.join(symbole)} {interval_obj.label}, "
        f"{laeufe} gemischte Reihen\n"
    )
    echt = lauf(frames)
    gemischt = []
    with console.status("mische...") as status:
        for i in range(laeufe):
            gemischt.append(
                lauf({
                    m: mische_renditen(f, saat=20260808 + i * 97)
                    for m, f in frames.items()
                })
            )
            status.update(f"mische... {i + 1}/{laeufe}")

    verteilung = Nullverteilung(echt=echt, gemischt=gemischt)
    console.print(verteilung.bericht())
    console.print()
    if not verteilung.maschine_sauber:
        raise typer.Exit(1)


@app.command()
def abstand(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Was fehlt zum Deflated-Sharpe-Gate - und was kostet Weitersuchen?

    Die haerteste Huerde im System hat eine Eigenschaft, die man leicht
    uebersieht: Sie waechst mit jedem getesteten Einfall. Die Zahl der
    Versuche steht in der Huerde selbst, nicht nur in der Buchhaltung.
    Derselbe Kandidat, dieselben Daten:

        10 Versuche  -> DSR 0,994
        95 Versuche  -> DSR 0,837
       500 Versuche  -> DSR 0,535

    Wer breit sucht, entwertet rechnerisch, was er findet. Dieser Befehl sagt
    vorher, was ein weiterer Versuch kostet und was er bringen muesste -
    damit die Suche budgetiert wird statt geraten.
    """
    from decimal import Decimal

    from rich.table import Table

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.erreichbarkeit import bewerte, kennzahlen_aus_pnl
    from research.gates import stichprobe_wie_im_gate
    from research.randschnitt import ohne_zensierte, randtrades
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    genome = spitzenkandidat()
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    report = run_portfolio_walkforward(
        frames, lambda: compile_genome(genome), configs
    )
    if not report.windows:
        console.print("[red]Keine Fenster - zu wenig gemeinsame Historie.[/]")
        raise typer.Exit(2)

    trials = load_trials(Path(settings.paths.state) / "trials.json")
    # **Nur fertig gehandelte Trades** (Befund 152) - genau wie im Gate. Ein
    # am Datenende glattgestellter Trade ist keine abgeschlossene Beobachtung.
    # Ohne das meldet dieses Werkzeug einen kleineren Abstand als das Gate,
    # und zwar jedes Mal etwas anders, je nach Alter des Datenabzugs.
    zensiert = randtrades(report.all_trades)
    gehandelt = ohne_zensierte(report)
    if zensiert:
        console.print(
            f"[dim]{len(zensiert)} von {len(report.all_trades)} Trades wurden "
            f"am Datenende glattgestellt und zaehlen in der Statistik nicht "
            f"mit - in Rendite und Rueckgang sehr wohl.[/dim]"
        )
    n, sharpe, schiefe, woelbung = kennzahlen_aus_pnl(
        [t.net_pnl for t in gehandelt.all_trades]
    )
    # **Effektive** Stichprobe, genau wie im Gate. Ohne das wuerde dieses
    # Werkzeug einen kleineren Abstand melden, als das Gate tatsaechlich
    # verlangt - und die Suche in die Irre schicken.
    #
    # Der Satz stand hier schon, der Aufruf hielt ihn aber nicht mehr: Er
    # nahm nur die Fensterbloecke, ohne Gleichzeitigkeit und ohne Quartale.
    # "Genau wie im Gate" war damit seit Befund 135 schlicht falsch. Jetzt
    # ruft er die Funktion auf, die das Gate selbst benutzt (Befund 139).
    stichprobe = stichprobe_wie_im_gate(
        gehandelt.all_trades,
        beine=getattr(report, "beine", None),
        bloecke=[[float(x.net_pnl) for x in w.trades] for w in gehandelt.windows],
    )
    # **Auch dann anzeigen, wenn nicht gekuerzt wurde, die Entscheidung aber
    # auf der Kippe stand.** Vorher lief es genau andersherum: Gemeldet wurde
    # nur die vollzogene Kuerzung - also alles ausser dem Fall, in dem die
    # Zahl am wenigsten belastbar ist.
    if stichprobe.effektiv != n or stichprobe.knapp:
        console.print(f"[dim]{stichprobe.bericht()}[/dim]")
    n = stichprobe.effektiv
    ergebnis = bewerte(
        trades=n, sharpe=sharpe, trials=trials, skew=schiefe, kurtosis=woelbung
    )

    console.print(f"\n[bold]Abstand zum Gate[/] {' + '.join(symbole)} "
                  f"{interval_obj.label}\n")
    console.print(ergebnis.bericht())

    tabelle = Table(header_style="bold", title="Was die Suche kostet")
    tabelle.add_column("Versuche", justify="right")
    tabelle.add_column("DSR", justify="right")
    tabelle.add_column("noetige Trades", justify="right")
    for t in sorted({10, 50, trials, trials + 10, trials + 50, 200, 500}):
        e = bewerte(trades=n, sharpe=sharpe, trials=t, skew=schiefe, kurtosis=woelbung)
        marke = " <-- heute" if t == trials else ""
        tabelle.add_row(
            f"{t}{marke}", f"{e.dsr:.3f}",
            "-" if e.trades_noetig is None else str(e.trades_noetig),
        )
    console.print()
    console.print(tabelle)
    console.print(
        "\n[dim]Mehr Daten kosten keinen Versuch, eine neue Idee schon. "
        "Die Reihenfolge folgt daraus.[/]\n"
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
    regler: str = typer.Option(
        "", "--regler", "-r",
        help="Nur diese eine Stellgroesse abtasten, z.B. 'sma(period=50)'. "
             "Leer = alle Perioden gemeinsam. Ohne Wert werden die "
             "verfuegbaren Stellgroessen aufgelistet.",
    ),
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

    # **Welche Stellgroesse?** Ohne Angabe wandern alle Perioden gemeinsam -
    # und dann sagt die Karte nicht, welche den Ausschlag gibt. Beim
    # Spitzenkandidaten hat das Plateau-Gate gezeigt, dass vier von fuenf
    # Perioden nichts bewirken und alles an der 50 haengt.
    #
    # **Vor dem Laden geprueft** (Befund 151): Die Pruefung haengt nur am
    # Genom. Stand sie hinter dem Laden, bekam ein Tippfehler auf einem
    # Rechner ohne Kerzen die Meldung "Keine Kerzen" - und der Nutzer jagte
    # das falsche Problem.
    from research.gates import stellgroessen

    genome = spitzenkandidat()
    verfuegbar = {s.kennung: s.name for s in stellgroessen(genome)}
    if regler and regler not in verfuegbar:
        console.print(
            f"[red]Unbekannte Stellgroesse '{regler}'.[/] Vorhanden sind:\n"
            + "\n".join(f"  {k}" for k in verfuegbar)
        )
        raise typer.Exit(2)

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

    erster = next(iter(frames.values()))

    console.print(
        f"\n[bold]Landschaft[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Strategie  {genome.name}\n"
        f"  Regler     {verfuegbar.get(regler, 'alle Perioden gemeinsam')}\n"
        f"  Zeitraum   {erster['open_time'].iloc[0]:%Y-%m} bis "
        f"{erster['open_time'].iloc[-1]:%Y-%m}\n"
    )

    karte = kartieren(genome, frames, configs, nur=regler or None)
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


@app.command()
def machbarkeit(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    regler: str = typer.Option(
        "vola", "--regler", "-r",
        help="Welche Stellschraube abgetastet wird: vola, stop, konviktion.",
    ),
    stufen: str = typer.Option(
        "", "--stufen",
        help="Stufen, durch Komma getrennt. Leer = die des Reglers.",
    ),
    verfeinern: int = typer.Option(
        0, "--verfeinern",
        help="So viele Runden zusaetzlich messen, um ungeprueften "
             "Zwischenraeumen nachzugehen. 0 = nur die angegebenen Stufen.",
    ),
    zaehlen: bool = typer.Option(
        True, "--zaehlen/--nicht-zaehlen",
        help="Die gemessenen Stufen auf den Versuchszaehler addieren.",
    ),
    durchgehend: bool = typer.Option(
        False, "--durchgehend",
        help="Ein Lauf ueber die ganze Strecke statt einer je Fenster. "
             "Positionen und Risikozustand ueberleben die Fenstergrenze - so "
             "wie im Betrieb.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Gibt es eine Vola-Einstellung, bei der alle elf Gates zugleich halten?

    Eine Stufe darueber als "welche Einstellung ist die beste" - und billiger
    zu beantworten. Der Kandidat hat genau einen freien Regler; wenn dieser
    Regler das Ziel nicht erreichen **kann**, erspart das jede weitere Runde
    daran.

    Drei Ausgaenge mit sehr verschiedener Bedeutung:

    * **Fenster** - es gibt Stellungen, an denen alles haelt.
    * **Konflikt** - jedes Gate haelt irgendwo, nie zwei zugleich. Der Regler
      enthaelt keine Loesung, und das ist ein Beweis, kein "knapp daneben".
    * **Ausser Reichweite** - ein Gate haelt nirgends. Dann muss sich etwas
      anderes aendern, und der Befund sagt, welche Groesse sich um wie viel
      bewegen muesste.

    Zwischen zwei Stufen ist nichts gemessen. Ein leeres Fenster gilt deshalb
    nur so weit, wie die Aufloesung reicht - ``--verfeinern`` verkleinert die
    Zwischenraeume, und das Urteil nennt die verbliebenen.

    Jede gemessene Stufe zaehlt als Versuch und hebt die Huerde des Deflated
    Sharpe. Der Zaehler wird deshalb erhoeht.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from core.report import write_report
    from research.admission import load_trials, save_trials
    from research.gates import evaluate_gates
    from research.machbarkeit import (
        REGLER,
        Machbarkeit,
        aus_gate_report,
        ausgangswert,
        stelle_ein,
    )
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    erster = next(iter(frames.values()))
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    if regler not in REGLER:
        console.print(
            f"[red]Unbekannter Regler '{regler}'. "
            f"Bekannt: {', '.join(sorted(REGLER))}.[/]"
        )
        raise typer.Exit(2)
    schraube = REGLER[regler]

    vorlage = spitzenkandidat()
    ausgang = ausgangswert(vorlage, schraube)
    trials_path = Path(settings.paths.state) / "trials.json"
    trials = load_trials(trials_path)

    console.print(
        f"\n[bold]Machbarkeit[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Strategie  {vorlage.name} ({vorlage.genome_id})\n"
        f"  Zeitraum   {erster['open_time'].iloc[0]:%Y-%m} bis "
        f"{erster['open_time'].iloc[-1]:%Y-%m}\n"
        f"  Regler     {schraube.name}, Ausgangswert {ausgang:g} "
        f"{schraube.einheit}\n"
        f"  Lauf       {'durchgehend' if durchgehend else 'fensterweise'}\n"
        f"  Versuche   {trials} bisher\n"
    )

    analyse = Machbarkeit(
        regler=schraube.name, punkte=[], einheit=schraube.einheit
    )

    def messen(ziele: list[float]) -> None:
        for ziel in ziele:
            genome = stelle_ein(vorlage, schraube, ziel)
            report = run_portfolio_walkforward(
                frames, lambda g=genome: compile_genome(g), configs,
                durchgehend=durchgehend,
            )
            if not report.windows:
                console.print(
                    f"[yellow]{schraube.name} {ziel:g}: keine Fenster.[/]"
                )
                continue
            gates = evaluate_gates(
                genome, report, erster, configs[symbole[0]], trials_so_far=trials,
                frames=frames, configs=configs,
            )
            kombiniert = report.combined
            analyse.punkte.append(
                aus_gate_report(
                    ziel, gates,
                    {
                        "trades": float(len(report.all_trades)),
                        "cagr": kombiniert.cagr_pct if kombiniert else 0.0,
                        "rueckgang": (
                            kombiniert.max_drawdown_pct if kombiniert else 0.0
                        ),
                        # Fuer die Grenzlinie aus Nummer einunddreissig: Ohne
                        # den Sharpe je Trade laesst sich ein Punkt nicht an
                        # ihr einordnen, und genau das ist die Frage.
                        #
                        # Schiefe und Woelbung dazu, weil die Linie ohne sie
                        # die Anforderung eines fremden Genoms nennt: Beim
                        # Gewinnziel-Regler aendert sich die Form der
                        # Verteilung ueber die Stufen hinweg drastisch.
                        **_formkennzahlen(report.all_trades),
                    },
                )
            )
            console.print(
                f"[dim]  {schraube.name} {ziel:>6g} {schraube.einheit}  "
                f"{len(report.all_trades):>4} Trades  "
                f"{kombiniert.cagr_pct if kombiniert else 0:>6.2f} % p.a.  "
                f"Rueckgang "
                f"{kombiniert.max_drawdown_pct if kombiniert else 0:>5.2f} %  "
                f"{analyse.punkte[-1].bestanden}/{len(analyse.punkte[-1].gates)} "
                f"Gates[/]"
            )

    gewaehlt = [float(x.strip()) for x in stufen.split(",") if x.strip()]
    messen(gewaehlt or list(schraube.stufen))
    if not analyse.punkte:
        console.print("[red]Keine einzige Stufe lieferte Fenster.[/]")
        raise typer.Exit(2)

    for runde in range(verfeinern):
        naechste = analyse.verfeinerung()
        if not naechste:
            break
        console.print(f"\n[bold]Verfeinerung {runde + 1}[/]")
        messen(naechste)

    console.print("\n" + analyse.tabelle())
    console.print(
        "\n[dim]+ gehalten   - gerissen   o uebersprungen[/]\n"
    )

    farbe = "green" if analyse.fenster else "yellow"
    console.print(f"[{farbe}]{analyse.urteil()}[/]\n")

    # Die Werte hinter den Zeichen festhalten. Ohne das muesste man die
    # Abtastung wiederholen, um an sie heranzukommen - und jede Wiederholung
    # verleitet dazu, dieselben Stufen noch einmal auf den Versuchszaehler zu
    # addieren, obwohl nichts Neues gesehen wurde.
    nutzlast = analyse.als_payload()
    nutzlast["maerkte"] = symbole
    nutzlast["intervall"] = interval_obj.label
    nutzlast["versuche"] = trials
    ziel = write_report(nutzlast, root=Path.cwd(), kind="machbarkeit")
    console.print(f"[dim]Werte hinter den Zeichen: {ziel}[/]")

    if zaehlen:
        # Der Ausgangswert des Kandidaten ist bereits gezaehlt - alles andere
        # ist neu gerechnet und gesehen.
        neue = sum(1 for p in analyse.punkte if abs(p.stellung - ausgang) > 1e-9)
        save_trials(trials_path, trials + neue)
        console.print(
            f"[dim]Versuchszaehler {trials} -> {trials + neue} "
            f"({neue} neue Stellungen).[/]"
        )

    console.print(
        "[dim]Dieser Befehl waehlt keine Einstellung aus. Er beantwortet nur, "
        "ob es eine geben kann - wer die beste Stufe herauspickt, hat die "
        "Ueberanpassung begangen, gegen die das Plateau-Gate gebaut wurde.[/]"
    )


@app.command()
def kontorisiko(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    kapital: float = typer.Option(
        500.0, "--kapital", help="Kontogroesse insgesamt, nicht je Bein."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Haette das **Konto** ausgeloest - oder nur ein einzelnes Bein?

    Der Portfolio-Backtest laesst jedes Bein als eigenen Backtest laufen.
    Jedes bekommt damit ein eigenes Konto **und einen eigenen Risk-Officer**:
    bei zwei Maerkten zwei Kill-Switches auf je halber Kapitalbasis. Die
    loesen aus, wo ein einziges Konto nichts gemerkt haette.

    Gemessen am Spitzenkandidaten, durchgehend, je Bein 250 EUR:

        BTC-Bein          Rueckgang 12,74 %   pausiert am 03.09.2020
        ETH-Bein          Rueckgang 14,90 %
        Konto (500 EUR)   Rueckgang 10,72 %   loest **nichts** aus

    Die Sperre des BTC-Beins kostet 58 von 76 Trades - und beschreibt zwei
    getrennte Konten, nicht das eine, das es gibt.

    Dieser Befehl legt die Kapitalkurven aller Beine zu einer Kontokurve
    zusammen und fuehrt den **echten** Risk-Officer darueber. Er rechnet den
    Backtest **nicht** neu: Wo das Konto frueher gebremst haette, haetten die
    Beine danach anders gehandelt. Beantwortet wird genau eine Frage - haette
    das Konto ueberhaupt ausgeloest?

    Kostet keinen Versuch: Geprueft wird die Kontofuehrung, keine Regel.
    """
    from decimal import Decimal

    import pandas as pd

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range
    from backtest.walkforward import WalkForwardSplitter, run_walkforward
    from research.kontorisiko import kontokurve, pruefe
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    genome = spitzenkandidat()
    je_bein = Decimal(str(kapital)) / Decimal(len(frames))

    console.print(
        f"\n[bold]Kontorisiko[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Strategie  {genome.name}\n"
        f"  Konto      {kapital:.0f} EUR, je Bein {je_bein:.2f} EUR\n"
    )

    kurven = {}
    for markt, frame in frames.items():
        cfg = BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(markt)),
            risk=settings.risk, initial_equity=je_bein,
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        bericht = run_walkforward(
            frame, lambda: compile_genome(genome), cfg,
            WalkForwardSplitter(), durchgehend=True,
        )
        teile = [
            w.result.equity_curve for w in bericht.windows
            if not w.result.equity_curve.empty
        ]
        kurven[markt] = (
            pd.concat(teile, ignore_index=True) if teile else pd.DataFrame()
        )
        lauf = pruefe(
            kurven[markt], risk=settings.risk,
            instrument=_fallback_instrument(_bybit_kontrakt(markt)),
        )
        wann = (
            f"{lauf.erstes.zeit:%Y-%m-%d}" if lauf.erstes else "nie"
        )
        console.print(
            f"  [dim]{markt:22} {len(bericht.all_trades):>4} Trades, "
            f"Rueckgang {lauf.hoechster_rueckgang_pct:>6.2f} %, "
            f"erstes Ereignis {wann}[/]"
        )

    konto = pruefe(
        kontokurve(kurven), risk=settings.risk,
        instrument=_fallback_instrument(_bybit_kontrakt(symbole[0])),
    )
    farbe = "yellow" if konto.haette_ausgeloest else "green"
    console.print(f"\n[{farbe}]{konto.bericht()}[/]\n")

    if not konto.haette_ausgeloest and len(frames) > 1:
        console.print(
            "[dim]Sperren einzelner Beine sind damit Artefakte der Aufteilung. "
            "Die Trade-Zahlen aus so einem Lauf beschreiben zwei getrennte "
            "Konten, nicht das eine, das es gibt.[/]"
        )


@app.command()
def nachpruefung(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    generation: str = typer.Option(
        "", "--generation", "-g",
        help="Nur diese Generationen, durch Komma getrennt. Leer = alle.",
    ),
    schnell: bool = typer.Option(
        False, "--schnell",
        help="Die teuren Gates (Plateau, Kosten-Stress) auslassen. Vorauswahl, "
             "keine Zulassung - die Zahl der Gates sinkt entsprechend.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Den ganzen Katalog noch einmal messen - mit dem korrigierten Instrument.

    **Wozu.** Der Leaderboard traegt Stand vom 05.08.2026 und zaehlt noch zehn
    Gates. Seither sind zwei Fehler im Messgeraet gefunden worden:

    * Der **Nachlauf** - offene Positionen wurden am Fensterende zwangsweise
      glattgestellt. Beim Spitzenkandidaten traf das 25 von 154 Trades, und
      diese 25 trugen den gesamten Vorteil. Betroffen ist jeder Kandidat, am
      staerksten die langsamen.
    * Die **Aufwaermphase** - die Konfluenz wurde nicht mitgezaehlt.
      Nachgemessen betrifft das im Katalog fast nur den Spitzenkandidaten.

    Ein Urteil ueber eine Strategie ist nur so gut wie das Geraet, mit dem es
    zustande kam. Aendert sich das Geraet, ist das Urteil neu zu faellen.

    **Kostet keinen Versuch.** Dieselben Regeln auf denselben Daten; gesehen
    wurden sie alle schon und stehen laengst im Zaehler. Der Deflated Sharpe
    korrigiert dafuer, dass man bei genug Einfaellen etwas findet - nicht
    dafuer, dass man einen alten Einfall richtiger misst.

    Wer hier weit kommt, ist damit **nicht** zugelassen: Er ist einer aus 53,
    und genau dafuer steht die Huerde da, wo sie steht.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from core.report import write_report
    from research.admission import load_trials
    from research.gates import evaluate_gates
    from research.leaderboard import Leaderboard
    from research.nachpruefung import Ergebnis, Nachpruefung
    from research.seeds import GENERATIONS, spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    erster = next(iter(frames.values()))
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    gewuenscht = {int(x) for x in generation.replace(" ", "").split(",") if x}
    kandidaten: list[tuple[int, object]] = []
    for nummer, liste in sorted(GENERATIONS.items()):
        if gewuenscht and nummer not in gewuenscht:
            continue
        for eintrag in liste:
            kandidaten.append((nummer, eintrag() if callable(eintrag) else eintrag))
    if not gewuenscht:
        kandidaten.append((0, spitzenkandidat()))
    if not kandidaten:
        console.print(f"[red]Keine Kandidaten fuer Generation {generation}.[/]")
        raise typer.Exit(2)

    trials = load_trials(Path(settings.paths.state) / "trials.json")
    console.print(
        f"\n[bold]Nachpruefung[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Kandidaten {len(kandidaten)}"
        + ("  [Vorauswahl: teure Gates ausgelassen]" if schnell else "")
        + "\n"
        f"  Zeitraum   {erster['open_time'].iloc[0]:%Y-%m} bis "
        f"{erster['open_time'].iloc[-1]:%Y-%m}\n"
        f"  Versuche   {trials} (unveraendert - Nachmessen ist kein Versuch)\n"
    )

    lauf = Nachpruefung()
    for i, (nummer, genome) in enumerate(kandidaten, start=1):
        try:
            bericht = run_portfolio_walkforward(
                frames, lambda g=genome: compile_genome(g), configs
            )
        # Ein einzelner Kandidat darf den ganzen Lauf nicht kippen.
        except Exception as fehler:
            console.print(f"[yellow]  {genome.name[:44]:46} Fehler: {fehler}[/]")
            continue
        if not bericht.windows:
            console.print(f"[dim]  {genome.name[:44]:46} keine Fenster[/]")
            continue

        gates = evaluate_gates(
            genome, bericht, erster, configs[symbole[0]], trials_so_far=trials,
            run_expensive=not schnell, frames=frames, configs=configs,
        )
        k = bericht.combined
        ergebnis = Ergebnis(
            genome_id=genome.genome_id,
            name=genome.name,
            generation=nummer,
            bestanden=sum(1 for r in gates.results if r.passed),
            gesamt=len(gates.results),
            offen=tuple(r.name for r in gates.results if not r.passed),
            trades=len(bericht.all_trades),
            cagr_pct=k.cagr_pct if k else 0.0,
            rueckgang_pct=k.max_drawdown_pct if k else 0.0,
            dsr=next(
                (r.value for r in gates.results if r.name == "Deflated Sharpe"), 0.0
            ),
            vorauswahl=schnell,
        )
        lauf.ergebnisse.append(ergebnis)
        console.print(
            f"[dim]  {i:>2}/{len(kandidaten)} {genome.name[:42]:44} "
            f"{ergebnis.bestanden:>2}/{ergebnis.gesamt:<2} "
            f"{ergebnis.trades:>4} Trades  DSR {ergebnis.dsr:.3f}[/]"
        )

    if not lauf.ergebnisse:
        console.print("[red]Kein einziger Kandidat lieferte ein Ergebnis.[/]")
        raise typer.Exit(2)

    console.print("\n" + lauf.tabelle())

    state = Path(settings.paths.state)
    board = Leaderboard(state / "leaderboard.json")
    vorher = {
        kennung: eintrag.gates_bestanden
        for kennung, eintrag in board.entries.items()
    }
    geaendert = lauf.veraenderungen(vorher)
    if geaendert:
        console.print(
            f"\n[bold]{len(geaendert)} Kandidat(en) stehen anders da als "
            f"im Leaderboard[/]"
        )
        for v in geaendert:
            console.print(f"  {v}")
        console.print(
            "[dim]Vorsicht beim Lesen: Damals waren es zehn Gates, heute elf. "
            "Die Rohzahlen sind ein Hinweis, kein Beweis.[/]"
        )

    farbe = "green" if lauf.zugelassen else "yellow"
    console.print(f"\n[{farbe}]{lauf.urteil()}[/]\n")

    ziel = write_report(
        {
            "maerkte": symbole,
            "intervall": interval_obj.label,
            "versuche": trials,
            "ergebnisse": [
                {
                    "genome_id": e.genome_id, "name": e.name,
                    "generation": e.generation, "bestanden": e.bestanden,
                    "gesamt": e.gesamt, "offen": list(e.offen), "trades": e.trades,
                    "cagr_pct": round(e.cagr_pct, 4),
                    "rueckgang_pct": round(e.rueckgang_pct, 4),
                    "dsr": round(e.dsr, 4),
                }
                for e in lauf.rangfolge
            ],
            "urteil": lauf.urteil(),
        },
        root=Path.cwd(), kind="nachpruefung",
    )
    console.print(f"[dim]Vollstaendig: {ziel}[/]")


@app.command()
def marktkombinationen(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP,LTCUSD_BITSTAMP,XRPUSD_BITSTAMP",
        "--maerkte", "-m", help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    mindestens: int = typer.Option(
        1, "--mindestens", help="Kleinste Zahl Maerkte je Kombination."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Jede Marktkombination durch die volle Zulassungsstrecke.

    **Wozu noch einmal.** Diese Tabelle gab es schon - gemessen mit einem
    Backtest, der offene Positionen am Fensterende zwangsweise glattstellte.
    Beim Spitzenkandidaten kostete das 0,078 Punkte am Deflated Sharpe, und
    genau dieses Gate entscheidet hier:

        Kombination        alt (defekt)   noetig
        BTC+ETH+LTC+XRP          0,875     0,95
        BTC+ETH+LTC              0,873     0,95

    Beide lagen keine 0,08 unter der Schwelle - also in genau der
    Groessenordnung, um die der Fehler die Zahl gedrueckt hat. Ob das reicht,
    ist eine Messung und keine Rechnung.

    **Kostet keinen Versuch.** Mehr Maerkte sind mehr *Daten*, nicht mehr
    Einfaelle - dieselbe Regel auf einer breiteren Grundlage. Der Deflated
    Sharpe korrigiert dafuer, dass man bei genug Einfaellen etwas findet.

    Was die Tabelle nicht loest, sagt sie mit: Mehr Maerkte bringen Trades und
    kosten Rendite. Steigt der Deflated Sharpe ueber die Schwelle, faellt
    womoeglich die Messlatte darunter - beide Gates zugleich zu halten ist die
    eigentliche Frage.
    """
    from decimal import Decimal
    from itertools import combinations

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from core.report import write_report
    from research.admission import load_trials
    from research.gates import evaluate_gates
    from research.nachpruefung import Ergebnis, Nachpruefung
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    genome = spitzenkandidat()
    trials = load_trials(Path(settings.paths.state) / "trials.json")

    kombinationen = [
        k
        for groesse in range(max(1, mindestens), len(symbole) + 1)
        for k in combinations(symbole, groesse)
    ]
    console.print(
        f"\n[bold]Marktkombinationen[/] {interval_obj.label}\n"
        f"  Strategie    {genome.name}\n"
        f"  Kombinationen {len(kombinationen)} aus {len(symbole)} Maerkten\n"
        f"  Versuche     {trials} (unveraendert - mehr Daten sind kein Versuch)\n"
    )

    lauf = Nachpruefung()
    for nummer, kombination in enumerate(kombinationen, start=1):
        frames = common_range({m: roh[m] for m in kombination})
        configs = {
            m: BacktestConfig(
                instrument=_fallback_instrument(_bybit_kontrakt(m)),
                risk=settings.risk, initial_equity=Decimal("500"),
                enforce_risk_limits=True,
                kalender=_terminkalender(settings) or None,
            )
            for m in kombination
        }
        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs
        )
        if not bericht.windows:
            console.print(f"[dim]  {'+'.join(kombination)}: keine Fenster[/]")
            continue

        erster = next(iter(frames.values()))
        gates = evaluate_gates(
            genome, bericht, erster, configs[kombination[0]], trials_so_far=trials,
            frames=frames, configs=configs,
        )
        k = bericht.combined
        kurz = "+".join(m.split("USD")[0] for m in kombination)
        ergebnis = Ergebnis(
            genome_id=kurz,
            name=kurz,
            generation=len(kombination),
            bestanden=sum(1 for r in gates.results if r.passed),
            gesamt=len(gates.results),
            offen=tuple(r.name for r in gates.results if not r.passed),
            trades=len(bericht.all_trades),
            cagr_pct=k.cagr_pct if k else 0.0,
            rueckgang_pct=k.max_drawdown_pct if k else 0.0,
            dsr=next(
                (r.value for r in gates.results if r.name == "Deflated Sharpe"), 0.0
            ),
        )
        lauf.ergebnisse.append(ergebnis)
        console.print(
            f"[dim]  {nummer:>2}/{len(kombinationen)} {kurz:22} "
            f"{ergebnis.bestanden:>2}/{ergebnis.gesamt:<2} "
            f"{ergebnis.trades:>4} Trades  DSR {ergebnis.dsr:.3f}[/]"
        )

    if not lauf.ergebnisse:
        console.print("[red]Keine Kombination lieferte ein Ergebnis.[/]")
        raise typer.Exit(2)

    console.print("\n" + lauf.tabelle(hoechstens=len(lauf.ergebnisse)))

    farbe = "green" if lauf.zugelassen else "yellow"
    console.print(f"\n[{farbe}]{lauf.urteil()}[/]\n")

    ueber = [e for e in lauf.ergebnisse if e.dsr >= 0.95]
    if ueber:
        console.print(
            "[bold]Ueber der Deflated-Sharpe-Schwelle:[/] "
            + ", ".join(f"{e.name} ({e.dsr:.3f})" for e in ueber)
        )
        console.print(
            "[dim]Damit ist das haerteste Gate erreichbar - was fehlt, steht "
            "in der Spalte 'offen'. Beide Gates zugleich zu halten ist die "
            "eigentliche Frage.[/]"
        )

    ziel = write_report(
        {
            "intervall": interval_obj.label,
            "versuche": trials,
            "kombinationen": [
                {
                    "maerkte": e.name, "anzahl": e.generation,
                    "bestanden": e.bestanden, "gesamt": e.gesamt,
                    "offen": list(e.offen), "trades": e.trades,
                    "cagr_pct": round(e.cagr_pct, 4),
                    "rueckgang_pct": round(e.rueckgang_pct, 4),
                    "dsr": round(e.dsr, 4),
                }
                for e in lauf.rangfolge
            ],
            "urteil": lauf.urteil(),
        },
        root=Path.cwd(), kind="marktkombinationen",
    )
    console.print(f"[dim]Vollstaendig: {ziel}[/]")


@app.command()
def anlagentest(
    ziel: str = typer.Option(
        "", "--ziel", help="Zieldatei. Standard: <strategies>/anlagentest.json"
    ),
) -> None:
    """Den Spitzenkandidaten als Datei ablegen - fuer den Technik-Test auf Demo.

    **Was das ist und was nicht.** Es gibt zwei Dinge, die beide "Demo"
    heissen, und sie pruefen Verschiedenes:

        Anlagentest      Orders, Stops, Neustart mitten in einer Position,
                         Telegram, Not-Aus  ->  prueft die **Technik**
        Dreissig Tage    Live-Kennzahlen gegen die Backtest-Erwartung
                         ->  prueft die **Strategie**

    Der Anlagentest geht heute. Die dreissig Tage nicht: Sie vergleichen eine
    zugelassene Strategie mit dem, was der Backtest versprochen hat, und
    dieser Kandidat hat seine Gates noch nicht bestanden. Wie weit er kommt,
    sagt ``cli stand`` - gemessen, nicht hier hineingeschrieben.

    Damit das nirgends verwechselt werden kann, traegt die Datei den Hinweis
    **im Namen** der Strategie. Der taucht dann ueberall auf, wo sie genannt
    wird: im Dashboard, in den Telegram-Meldungen, im Journal. Die Kennung
    bleibt davon unberuehrt - ``name`` und ``rationale`` fliessen nicht in den
    Hash ein.

    Echtes Geld ist auf dieser Datei gesperrt. ``cli trade --echtgeld``
    vergleicht die Kennung gegen ``champion.json`` und bricht ab, wenn sie
    nicht uebereinstimmt.
    """
    import json
    from pathlib import Path

    from research.seeds import spitzenkandidat

    settings = get_settings()
    genome = spitzenkandidat()
    markiert = genome.model_copy(
        update={"name": f"NICHT ZUGELASSEN (Anlagentest) - {genome.name}"}
    )
    pfad = Path(ziel) if ziel else Path(settings.paths.strategies) / "anlagentest.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(markiert.model_dump(mode="json"), indent=2))

    console.print(
        f"\n[bold]Anlagentest-Genom geschrieben[/] {pfad}\n"
        f"  Strategie  {markiert.name}\n"
        f"  Kennung    {markiert.genome_id}  (unveraendert - der Hinweis steht "
        f"nur im Namen)\n"
    )
    console.print(
        "[yellow]Das ist keine zugelassene Strategie.[/]\n"
        "[dim]Geprueft wird damit die Technik, nicht die Strategie - und "
        "echtes Geld ist darauf gesperrt. Wie weit der Kandidat kommt, sagt "
        "'python -m cli stand'.[/]\n"
    )
    console.print(
        "[bold]So laeuft der Test[/] - drei Schritte, alle auf deinem Rechner:\n"
        "  1  python -m cli healthcheck"
        "          [dim]bietet das Konto ueberhaupt Perpetuals?[/]\n"
        "  2  python -m cli backfill --intervall 15"
        "   [dim]Kerzen laden[/]\n"
        "  3  ./start.sh --anlagentest"
        "             [dim]Website und Handel zusammen[/]\n"
    )
    console.print(
        "[dim]Fuer den Not-Aus auf der Website muss WEB__PASSWORD in der .env "
        "stehen. Ohne das bleibt die Ansicht, aber Pause, Glattstellen und "
        "Not-Aus sind gesperrt.[/]\n"
    )
    console.print(
        "[bold]Der eigentliche Test[/] ist unbequem, und genau der zaehlt: "
        "Den Prozess mitten in einer offenen Position hart abschiessen und bei "
        "Bybit nachsehen, ob der Stop noch an der Position haengt. Dafuer wird "
        "er dort gesetzt und nicht im Arbeitsspeicher gehalten.\n"
    )


@app.command()
def adaptiv(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Die Periode im Trainingsfenster waehlen statt am Schreibtisch.

    **Die einzige Idee im Haus, die gebaut und nie gemessen wurde.**

    Die Landschaftskarte zeigt einen breiten tragfaehigen Bereich, und die
    schnelleren Punkte liefern deutlich mehr Trades - genau das, was dem
    Deflated Sharpe fehlt. Den besten Punkt daraus abzulesen waere
    Ueberanpassung: Die Karte entsteht auf denselben Daten, an denen der
    Kandidat gemessen wird.

    Hier wird die Periode stattdessen in **jedem Trainingsfenster neu**
    bestimmt und im Testfenster verwendet. Die Wahl kennt die Testdaten nicht.

    Gewaehlt wird die **Mitte des laengsten zusammenhaengenden profitablen
    Bereichs**, nicht der beste Punkt - die Regel steht vor der Messung fest.
    Genau das greift auch das Plateau-Gate an, an dem der Spitzenkandidat
    scheitert, weil er am Rand seines eigenen Bereichs sitzt.

    **Ein Versuch, nicht einer je Faktor.** Die einzelnen Faktoren werden nur
    im Training angesehen und nie am Testergebnis gemessen; die Auswahl ist
    Teil der Strategie geworden.
    """
    from decimal import Decimal
    from pathlib import Path

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.adaptiv import FensterWahl
    from research.admission import load_trials, save_trials
    from research.gates import evaluate_gates
    from research.seeds import spitzenkandidat
    from research.suchbudget import Budget, Kandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    genome = spitzenkandidat()
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    trials_path = Path(settings.paths.state) / "trials.json"
    trials = load_trials(trials_path)
    console.print(
        f"\n[bold]Adaptive Periode[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Grundregel  {genome.name}\n"
        f"  Versuche    {trials} bisher\n"
    )

    wahl = FensterWahl(genome, frames, configs)
    bericht = run_portfolio_walkforward(
        frames, lambda: compile_genome(genome), configs,
        strategie_je_fenster=wahl,
    )
    if not bericht.windows:
        console.print("[red]Keine Fenster.[/]")
        raise typer.Exit(2)

    console.print(wahl.bericht())

    erster = next(iter(frames.values()))
    # Die Wahl ist Teil der Strategie - **ein** Versuch, nicht einer je
    # Faktor. Gezaehlt wird er trotzdem, und vor der Bewertung: Die Huerde
    # des Deflated Sharpe soll diesen Kandidaten schon einschliessen.
    trials += 1
    gates = evaluate_gates(
        genome, bericht, erster, configs[symbole[0]], trials_so_far=trials,
        frames=frames, configs=configs,
    )
    save_trials(trials_path, trials)

    k = bericht.combined
    console.print(
        f"\n  {len(bericht.all_trades)} Trades, "
        f"{k.cagr_pct if k else 0:.2f} % p.a., "
        f"Rueckgang {k.max_drawdown_pct if k else 0:.2f} %\n"
    )
    console.print("DIE GATES")
    console.print("-" * 72)
    for r in gates.results:
        zeichen = "+" if r.passed else "-"
        farbe = "green" if r.passed else "yellow"
        console.print(
            f"  [{farbe}]{zeichen}[/] {r.name:24} {r.value:>10.3f} "
            f"gegen {r.threshold:>10.3f}"
        )
    bestanden = sum(1 for r in gates.results if r.passed)
    console.print(f"\n  {bestanden} von {len(gates.results)} bestanden")

    eintrag = Kandidat.aus_trades(genome.name, bericht.all_trades)
    if eintrag is not None:
        budget = Budget(versuche=trials, kandidaten=[eintrag])
        console.print("\nWORAN DAS HAERTESTE GATE HAENGT")
        console.print("-" * 72)
        for h in budget.hebel(eintrag):
            console.print(f"  {h}")
    console.print(f"\n[dim]Versuchszaehler {trials - 1} -> {trials}.[/]\n")


@app.command()
def teststaerke(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    stufen: str = typer.Option(
        "0,0.05,0.1,0.2,0.35,0.5", "--stufen",
        help="Gepflanzte Varianzanteile, durch Komma getrennt.",
    ),
    dauer: int = typer.Option(60, "--dauer", help="Mittlere Regimedauer in Kerzen."),
    saat: int = typer.Option(11, "--saat", help="Fuer eine reproduzierbare Folge."),
    saaten: str = typer.Option(
        "", "--saaten",
        help="Mehrere Saaten, durch Komma. Misst die Streuung ueber Ziehungen "
             "statt einer einzelnen - siehe Befund 113.",
    ),
    halten: str = typer.Option(
        "0", "--halten",
        help="Haltedauer-Deckel in Kerzen, durch Komma. 0 = unbegrenzt.",
    ),
    regeln: Path | None = typer.Option(
        None, "--regeln",
        help="Vorschlagsdatei. Vergleicht Regeln statt Deckel - ohne die "
             "0-%-Sprosse, denn die waere die echte Reihe.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Liesse die Zulassungsstrecke ueberhaupt etwas durch?

    Die Nullprobe fragt, ob die Maschine einen Vorteil findet, wo keiner ist.
    Sie hat mit Nein geantwortet. Die Gegenfrage stand nie da: **Erkennt sie
    einen, der wirklich da ist?**

    Nach 161 Versuchen passen zwei Erklaerungen gleich gut auf alles
    Gemessene - die Regelfamilie traegt nicht, oder die Huerde ist bei so
    vielen Versuchen unerreichbar geworden. Von innen sehen beide gleich aus.

    Getrennt werden sie, indem in die echte Reihe ein Trend **gepflanzt**
    wird: ein Regime, das ueber Wochen dasselbe Vorzeichen behaelt. Die
    Gesamtstreuung bleibt dabei gleich - die Reihe wird nicht ruhiger, nur
    berechenbarer. Bei Anteil 0 ist es die unveraenderte Wirklichkeit, und
    dort muss das bekannte Ergebnis herauskommen.

    Der Test ist zur Strecke **freundlich**: Ein gepflanztes Regime ist
    sauberer als jeder Markt. Kommt nichts durch, ist das belastbar - kommt
    etwas durch, heisst es nur, dass es nicht an den Gates liegt.

    Kostet keinen Versuch. Der Zaehler bleibt, wo er ist: Hier wird die
    Strecke geprueft, kein Kandidat fuer den Livebetrieb ausgewaehlt.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import evaluate_gates, stichprobe_wie_im_gate
    from research.randschnitt import ohne_zensierte
    from research.seeds import spitzenkandidat
    from research.suchbudget import Kandidat
    from research.teststaerke import (
        Leiter,
        Stufe,
        Vergleich,
        pflanze_trend,
        regimefolge,
    )
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]

    # **Argumente vor Daten** (Befund 151). Alles bis zur Variantenliste
    # haengt nur an den Optionen; stand es hinter ``_korb_daten``, bekam ein
    # Tippfehler auf einem Rechner ohne Kerzen die Meldung "Keine Kerzen" -
    # und der Nutzer suchte den Fehler an der falschen Stelle.
    try:
        anteile = sorted({float(x) for x in stufen.split(",") if x.strip()})
        deckel_liste = sorted({int(x) for x in halten.split(",") if x.strip()})
    except ValueError:
        console.print(f"[red]'{stufen}' / '{halten}' sind keine Zahlen.[/]")
        raise typer.Exit(2) from None

    # **Der Kandidat unveraendert.** Der erste Anlauf stellte hier die
    # Groessenlogik gleich, aus ``korb`` uebernommen - dort ist das richtig,
    # weil ein ganzer Katalog verglichen wird. Hier gibt es nur ein Genom, und
    # die Normalisierung verschob still den Ankerpunkt: Die 0-%-Sprosse kam
    # auf 143 Trades und 5 von 11 statt auf die bekannten 152 und 7 von 11.
    # Eine Leiter, deren unterste Sprosse nicht die Wirklichkeit ist, misst
    # ihre eigene Erzeugung.
    genome = spitzenkandidat()

    varianten: list[tuple[str, object]] = []
    if regeln is not None:
        varianten = _regeln_aus_datei(regeln)
        # Die Begruendung steht **vor** der Abbruchpruefung. Andernfalls sieht
        # genau der Anwender sie nicht, der in die Sperre laeuft - und der
        # braucht sie am dringendsten.
        console.print(
            "[yellow]Vorauswahl von Regeln - die 0-%-Sprosse faellt weg.[/]\n"
            "[dim]Sie waere die unveraenderte echte Reihe. Wer auf ihr "
            "auswaehlt, hat auf echten Daten getestet, und das muss der "
            "Versuchszaehler sehen. Verglichen wird deshalb nur, wie gut eine "
            "Regel einen gepflanzten Vorteil in Guete umsetzt.[/]\n"
        )
        anteile = [a for a in anteile if a > 0.0]
        if not anteile:
            console.print(
                "[red]Keine gepflanzte Stufe uebrig.[/] Gib mit "
                "[bold]--stufen[/] mindestens einen Anteil groesser 0 an."
            )
            raise typer.Exit(2)
    else:
        varianten = [
            (
                "unbegrenzt" if deckel == 0 else f"{deckel} Kerzen",
                genome.model_copy(update={"max_hold_bars": deckel}),
            )
            for deckel in deckel_liste
        ]

    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)

    # Der Versuchsstand wird **gelesen und nicht fortgeschrieben**. Die Huerde
    # soll die von heute sein - aber eine Pruefung der Strecke ist kein
    # Versuch, und wer sie mitzaehlte, machte das Messen selbst teuer.
    versuche = load_trials(Path(settings.paths.state) / "trials.json")

    laenge = max(len(f) for f in frames.values())
    # **Ein Regime fuer alle Beine.** Getrennte Folgen je Markt waeren
    # geschenkte Unabhaengigkeit, und genau davon lebt der Deflated Sharpe.
    regime = regimefolge(laenge, dauer=dauer, saat=saat)

    # **Mehrere Saaten, oder eine mit Ansage.** Eine Leiter aus je einer
    # Ziehung sagt nichts ueber Unterschiede zwischen ihren Sprossen - ein
    # Regime ist eine Zufallsfolge, und die Streuung darueber ist gross
    # (bei 10 % gepflanztem Anteil: DSR 0,295 +- 0,264). Befund 54 stand auf
    # genau einer Ziehung; Befund 113 hat ihn ueber acht nachgeprueft.
    if saaten.strip():
        _teststaerke_ueber_saaten(
            saaten, anteile, frames, configs, genome, versuche, dauer, spanne,
            symbole, interval_obj,
        )
        return

    console.print(
        f"\n[bold]Teststaerke[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Historie   {spanne} Tage gemeinsam\n"
        f"  Regime     im Mittel {dauer} Kerzen, ein Verlauf fuer alle Beine\n"
        f"  Huerde     {versuche} Versuche (gelesen, nicht erhoeht)\n"
        f"  [dim]Eine Ziehung (Saat {saat}). Unterschiede zwischen Sprossen "
        f"traegt sie nicht - dafuer --saaten.[/]\n"
    )

    # Die gepflanzten Reihen **einmal** bauen und fuer alle Varianten
    # wiederverwenden: Wer je Variante neu pflanzt, vergleicht Ziehungen.
    gepflanzte = {
        anteil: {
            name: pflanze_trend(frame, anteil=anteil, regime=regime)
            for name, frame in frames.items()
        }
        for anteil in anteile
    }

    vergleich = Vergleich()
    with console.status("[dim]rechnet...[/]"):
        for bezeichnung, variante in varianten:
            leiter = Leiter(versuche=versuche)
            for anteil in anteile:
                gepflanzt = gepflanzte[anteil]
                bericht = run_portfolio_walkforward(
                    gepflanzt, lambda g=variante: compile_genome(g), configs
                )
                if not bericht.windows:
                    continue
                erster = next(iter(gepflanzt.values()))
                gates = evaluate_gates(
                    variante, bericht, erster, next(iter(configs.values())),
                    trials_so_far=versuche, frames=gepflanzt, configs=configs,
                )
                form = Kandidat.aus_trades("", bericht.all_trades)
                dsr = next(
                    (r.value for r in gates.results if r.name == "Deflated Sharpe"),
                    None,
                )
                # **Die effektive Stichprobe, nicht die rohe** (Befund 176).
                # Genau wie das Gate: zensierte Trades raus, Beine und
                # Fensterbloecke rein.
                gehandelt = ohne_zensierte(bericht)
                stichprobe = stichprobe_wie_im_gate(
                    gehandelt.all_trades,
                    beine=getattr(bericht, "beine", None),
                    bloecke=[
                        [float(x.net_pnl) for x in w.trades]
                        for w in gehandelt.windows
                    ],
                )
                leiter.stufen.append(
                    Stufe(
                        anteil=anteil,
                        trades=len(bericht.all_trades),
                        tage_im_markt=sum(
                            (t.exit_time - t.entry_time).days
                            for t in bericht.all_trades
                        ),
                        effektiv=stichprobe.effektiv,
                        sharpe=bericht.combined.sharpe if bericht.combined else 0.0,
                        sharpe_je_trade=form.sharpe_je_trade if form else 0.0,
                        dsr=dsr,
                        bestanden=sum(1 for r in gates.results if r.passed),
                        gesamt=len(gates.results),
                        offen=tuple(r.name for r in gates.failures),
                        cagr_pct=(
                            bericht.combined.cagr_pct if bericht.combined else 0.0
                        ),
                        rueckgang_pct=(
                            bericht.combined.max_drawdown_pct
                            if bericht.combined
                            else 0.0
                        ),
                        meldungen=tuple((r.name, r.message) for r in gates.failures),
                    )
                )
            vergleich.leitern[bezeichnung] = leiter

    leiter = next(iter(vergleich.leitern.values()))
    console.print(leiter.tabelle())
    console.print(f"\n{leiter.urteil()}\n")

    if len(vergleich.leitern) > 1:
        console.print("BRICHT EIN GEDECKELTER AUSSTIEG DIE KOPPLUNG?")
        console.print("-" * 72)
        console.print(vergleich.matrix())
        console.print(f"\n{vergleich.urteil()}\n")

    if leiter.stufen:
        console.print("WORAN ES JE STUFE HAKT [dim](ohne Deckel)[/]")
        console.print("-" * 72)
        for s in leiter.geordnet:
            console.print(
                f"  [bold]{s.anteil:.0%}[/] gepflanzt - {s.cagr_pct:.1f} % p.a., "
                f"{s.rueckgang_pct:.1f} % Rueckgang"
            )
            for name, meldung in s.meldungen:
                console.print(f"    [red]{name:22s}[/] [dim]{meldung[:74]}[/]")

    import json as _json
    from dataclasses import asdict

    ziel = Path.cwd() / "reports" / "teststaerke"
    ziel.mkdir(parents=True, exist_ok=True)
    datei = ziel / f"{datetime.now(UTC):%Y-%m-%d_%H%M%S}.json"
    datei.write_text(
        _json.dumps(
            {
                "erzeugt": datetime.now(UTC).isoformat(),
                "maerkte": symbole,
                "intervall": interval_obj.label,
                "dauer": dauer,
                "saat": saat,
                "versuche": versuche,
                "varianten": {
                    name: [asdict(s) for s in lt.geordnet]
                    for name, lt in vergleich.leitern.items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    console.print(f"\n[dim]Bericht: {datei}[/]")
    console.print(
        "[dim]Der Versuchszaehler steht unveraendert bei "
        f"{versuche}. Gepflanzte Reihen waehlen keinen Kandidaten aus.[/]\n"
    )


@app.command()
def schock(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    faktor: float = typer.Option(3.0, "--faktor", help="Vielfaches der Norm."),
    nachlauf: int = typer.Option(2, "--nachlauf", help="Gesperrte Kerzen danach."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Wie viele Einstiege ein Schock-Overlay betraefe - der Rest von P7.

    **Warum es kein Nachrichten-Overlay ist.** Termine stehen vorher fest,
    Nachrichten nicht - man weiss sie erst, wenn sie da sind. Ein Overlay, das
    eine Schlagzeile vom 12. Maerz kennt und deshalb am 11. nicht einsteigt,
    misst Hellsicht statt Vorsicht: Es verbessert den Backtest und leistet im
    Betrieb nichts.

    Gebaut ist deshalb, was kausal zulaessig bleibt: die Reaktion auf den
    **Abdruck** eines Schocks in den abgeschlossenen Kerzen. Gesperrt wird der
    Einstieg auf der Schockkerze und den Kerzen danach - kein Vorlauf.

    Ausgezaehlt wird zuerst, gemessen erst danach: Ein voller Gate-Lauf kostet
    einen Versuch und hebt die Huerde fuer alle kuenftigen Kandidaten. Ob er
    sich lohnt, entscheidet eine vorab gesetzte Schwelle - fuenf Prozent der
    Einstiege.

    Dieser Befehl selbst kostet nichts: Er bewertet keinen Kandidaten.
    """
    from research.schock import Auszaehlung, gesperrt, schocks
    from research.seeds import spitzenkandidat

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, _configs, spanne = _korb_daten(symbole, interval_obj, settings)

    console.print(
        f"\n[bold]Schock-Overlay[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Historie   {spanne} Tage gemeinsam\n"
        f"  Schwelle   {faktor:g}-fache Norm, {nachlauf} Kerzen Nachlauf\n"
    )

    gesamt = {"kerzen": 0, "schocks": 0, "gesperrt": 0, "signale": 0, "davon": 0}
    for name, frame in frames.items():
        treffer = schocks(frame, faktor=faktor)
        sperre = gesperrt(frame, faktor=faktor, nachlauf=nachlauf)

        # Die Einstiegssignale des Kandidaten - dieselbe Strategie, die auch
        # gemessen wird. Ein Overlay an einer anderen Regel auszuzaehlen
        # beantwortete eine Frage, die niemand gestellt hat.
        signale = _signalkerzen(frame, spitzenkandidat())

        betroffen = int((signale & sperre).sum())
        console.print(
            f"  [bold]{name}[/]  {int(treffer.sum())} Schocks, "
            f"{int(sperre.sum())} gesperrte Kerzen, {int(signale.sum())} Signale, "
            f"davon {betroffen} gesperrt"
        )
        gesamt["kerzen"] += len(frame)
        gesamt["schocks"] += int(treffer.sum())
        gesamt["gesperrt"] += int(sperre.sum())
        gesamt["signale"] += int(signale.sum())
        gesamt["davon"] += betroffen

    zaehlung = Auszaehlung(
        kerzen=gesamt["kerzen"], schocks=gesamt["schocks"],
        gesperrte_kerzen=gesamt["gesperrt"], signale=gesamt["signale"],
        betroffene_signale=gesamt["davon"],
    )
    console.print(f"\n[bold]Zusammen[/]\n{zaehlung.bericht()}\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert - hier wird gezaehlt, "
        "nicht bewertet.[/]\n"
    )


def _signalkerzen(frame, genome):
    """Wo das Genom auf dieser Reihe einsteigen wollte.

    Steht hier einmal, weil zwei Befehle es brauchen - ``schock`` zum
    Auszaehlen und ``sperrprobe`` zum Ziehen. Zwei Umsetzungen derselben
    Schleife waeren zwei Gelegenheiten, verschiedene Signale zu zaehlen und
    den Unterschied fuer ein Ergebnis zu halten.
    """
    import numpy as np

    from strategy.base import BarContext, frame_to_arrays
    from strategy.compiler import compile_genome

    strategie = compile_genome(genome)
    indikatoren = strategie.prepare(frame)
    arrays = frame_to_arrays(frame)
    signale = np.zeros(len(frame), dtype=bool)
    for i in range(strategie.warmup_bars, len(frame)):
        ctx = BarContext(frame=frame, arrays=arrays, indicators=indikatoren, index=i)
        signale[i] = strategie.on_bar(ctx) is not None
    return signale


@app.command()
def sperrprobe(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    massnahme: str = typer.Option(
        "schock", "--massnahme",
        help="Welche Trade-Entfernung geprueft wird: schock, abkuehlung.",
    ),
    kerzen: int = typer.Option(
        3, "--kerzen", help="Nur fuer abkuehlung: Laenge der Sperrfrist."
    ),
    ziehungen: int = typer.Option(200, "--ziehungen", "-n"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Leistet eine Trade-Entfernung mehr, als beliebiges Streichen taete?

    Befund 58 hat 13 von 165 Einstiegen gesperrt, und zwei Gates sind
    umgekippt - von 7 auf 9 von 11. Das ist der beste Stand, den dieses
    Projekt je hatte, und genau deshalb gehoert er geprueft.

    Denn es gibt eine zweite Erklaerung fuer dieselben Zahlen: **Weniger
    Trades sind manchmal einfach besser.** Wer aus 165 Einstiegen irgendwelche
    13 streicht, veraendert Rueckgang und schlechtestes Jahr. Wenn zufaelliges
    Streichen genauso oft neun von elf erzeugt, hat das Overlay nichts
    geleistet.

    Gezogen werden deshalb **Einstiegssignale**, genauso viele wie die
    Massnahme trifft, je Bein einzeln. Entschieden wird an der Zahl bestandener
    Gates, und das Kriterium steht vor der Messung fest: hoechstens fuenf
    Prozent der Ziehungen duerfen mithalten.

    Die Frage gilt fuer **jede** Massnahme, die Trades entfernt statt sie
    besser zu machen. ``--massnahme abkuehlung`` prueft die Sperrfrist aus
    Befund 44, die dort ebenfalls neun von elf lieferte - bei zwoelf Trades
    weniger und denselben zwei gekippten Gates.

    Beide gehen dabei durch **dieselbe** Mechanik: Auch die Abkuehlung wird
    als Sperre genau der Kerzen nachgebildet, die sie blockiert haette. Sonst
    verglichen sich Mechanismen statt Auswahlen.

    Kostet keinen Versuch - geprueft wird eine bereits gemessene Aussage, kein
    neuer Kandidat. Die teuren Gates bleiben aussen vor; **das
    Parameter-Plateau ist damit nicht abgesichert**, und es ist eines der
    beiden, die umgekippt sind.
    """
    import numpy as np
    import pandas as pd

    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import evaluate_gates
    from research.schock import Schocksperre, gesperrt
    from research.seeds import spitzenkandidat
    from research.sperrprobe import Ergebnis, Sperrprobe, ziehe_signale
    from research.suchbudget import Kandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, _spanne = _korb_daten(symbole, interval_obj, settings)

    genome = spitzenkandidat()
    versuche = load_trials(Path(settings.paths.state) / "trials.json")

    signale = {name: _signalkerzen(f, genome) for name, f in frames.items()}
    if massnahme == "schock":
        masken = {name: signale[name] & gesperrt(f) for name, f in frames.items()}
    elif massnahme == "abkuehlung":
        # Die Abkuehlung als **Sperre** nachgebildet: genau die Signale, die
        # sie blockiert haette. Sie ueber ``cooldown_bars`` laufen zu lassen
        # und die Null ueber eine Sperre waere ein Vergleich zweier
        # Mechanismen statt zweier Auswahlen.
        mit = {
            name: _signalkerzen(f, genome.model_copy(update={"cooldown_bars": kerzen}))
            for name, f in frames.items()
        }
        masken = {name: signale[name] & ~mit[name] for name in frames}
    else:
        console.print(f"[red]Unbekannte Massnahme '{massnahme}'.[/]")
        raise typer.Exit(2)

    anzahl = {name: int(masken[name].sum()) for name in frames}
    if not sum(anzahl.values()):
        console.print("[red]Diese Massnahme entfernt keinen Einstieg.[/]")
        raise typer.Exit(2)
    console.print(
        f"\n[bold]Sperrprobe[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Massnahme  {massnahme}"
        + (f" ({kerzen} Kerzen)" if massnahme == "abkuehlung" else "")
        + "\n"
        f"  Gesperrt   {', '.join(f'{n}: {a}' for n, a in anzahl.items())}\n"
        f"  Ziehungen  {ziehungen}\n"
        f"  Huerde     {versuche} Versuche (gelesen, nicht erhoeht)\n"
    )

    def messe(masken: dict[str, np.ndarray]) -> Ergebnis:
        import dataclasses

        belegt = {
            name: dataclasses.replace(
                cfg,
                schocksperre=Schocksperre(
                    zeitpunkte=frozenset(
                        pd.Timestamp(t)
                        for t in frames[name]["open_time"].to_numpy()[masken[name]]
                    )
                ),
            )
            for name, cfg in configs.items()
        }
        bericht = run_portfolio_walkforward(
            frames, lambda g=genome: compile_genome(g), belegt
        )
        erster = next(iter(frames.values()))
        gates = evaluate_gates(
            genome, bericht, erster, next(iter(belegt.values())),
            trials_so_far=versuche, run_expensive=False,
        )
        form = Kandidat.aus_trades("", bericht.all_trades)
        jahr = next(
            (r.value for r in gates.results if r.name == "Schlechtestes Jahr"), 0.0
        )
        dsr = next(
            (r.value for r in gates.results if r.name == "Deflated Sharpe"), 0.0
        )
        return Ergebnis(
            trades=len(bericht.all_trades),
            rueckgang_pct=bericht.combined.max_drawdown_pct if bericht.combined else 0.0,
            schlechtestes_jahr_pct=jahr,
            sharpe_je_trade=form.sharpe_je_trade if form else 0.0,
            dsr=dsr,
            bestanden=sum(1 for r in gates.results if r.passed),
            gesamt=len(gates.results),
        )

    # Der Fortschritt wird gezaehlt und die Dauer aus der ersten Ziehung
    # geschaetzt, nicht geraten.
    #
    # **Warum das noetig ist.** Zweihundert Ziehungen zu je einem vollen
    # Walk-Forward mit Gates laufen ueber eine halbe Stunde. Hier stand nur
    # ein Spinner ohne Zahl - nach zwanzig Minuten weiss niemand, ob der
    # Befehl bei Ziehung 5 oder 195 ist, und in eine Datei umgeleitet ist der
    # Spinner ueberhaupt nicht zu sehen. Ein Rauchtest hat den Befehl deshalb
    # nach 900 Sekunden abgeschossen, in der Annahme, er haenge (Befund 105).
    import time

    begonnen = time.monotonic()
    probe = Sperrprobe(echt=messe(masken))
    je_ziehung = time.monotonic() - begonnen
    console.print(
        f"[dim]  Eine Ziehung dauert {je_ziehung:.1f} s, {ziehungen} davon "
        f"also rund {_dauer(je_ziehung * ziehungen)}.[/]\n"
    )

    with console.status(f"[dim]zieht 0/{ziehungen} ...[/]") as anzeige:
        for saat in range(ziehungen):
            probe.zufall.append(messe(ziehe_signale(signale, anzahl, saat=saat)))
            anzeige.update(f"[dim]zieht {saat + 1}/{ziehungen} ...[/]")

    console.print(probe.bericht())
    console.print(f"\n{probe.urteil()}\n")
    console.print(
        "[dim]Kosten-Stress und Parameter-Plateau sind hier ausgelassen - "
        "zweihundert Ziehungen davon waeren Stunden. Das Parameter-Plateau "
        "ist damit nicht abgesichert, und es ist eines der beiden Gates, die "
        "in Befund 58 umgekippt sind.[/]\n"
    )


@app.command()
def haelften(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Haelt der Spitzenkandidat in der zweiten Haelfte des Zeitraums?

    ``cli scan`` verlangt von **jedem neuen Fund**, dass er in beiden Haelften
    haelt - *"ein Vorteil, den es nur in der ersten Haelfte gab, ist entweder
    wegarbitriert oder war nie da"*. An dieser Huerde ist der erste
    15-Minuten-Fund gescheitert und in Befund 63 die Tageszeit.

    **Der Spitzenkandidat ist nie daran gemessen worden.** Wir verlangen von
    jedem Vorschlag mehr als vom Bestand - und das ist die gefaehrlichere
    Richtung: Ein verworfener Vorschlag kostet nichts weiter, ein Bestand mit
    demselben Mangel steht seit Wochen im Mittelpunkt jeder Messung.

    Gemessen wird auf Trade-Ebene, nicht fensterweise: 31 Fenster halbiert
    sind fuenfzehn, und der Sharpe je Trade ist ohnehin die Groesse, an der
    der Deflated Sharpe haengt.

    Mitgerechnet wird, welcher Unterschied in der zweiten Haelfte ueberhaupt
    haette auffallen koennen. Ohne diese Zahl heisst "nicht stabil" zweierlei,
    und bei rund 77 Trades je Haelfte ist die harmlosere Deutung die
    wahrscheinlichere.

    Kostet keinen Versuch: Zerlegt wird ein Ergebnis, das ohnehin faellt.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.haelften import Halbierung, teile
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)

    genome = spitzenkandidat()
    bericht = run_portfolio_walkforward(
        frames, lambda g=genome: compile_genome(g), configs
    )
    geteilt = teile(list(bericht.all_trades))
    if geteilt is None:
        console.print("[red]Zu wenige Trades fuer eine Halbierung.[/]")
        raise typer.Exit(2)

    console.print(
        f"\n[bold]Halbierung[/] '{genome.name}' auf {' + '.join(symbole)} "
        f"{interval_obj.label}\n"
        f"  Historie   {spanne} Tage, {len(bericht.all_trades)} Trades\n"
    )
    halbierung = Halbierung(erste=geteilt[0], zweite=geteilt[1])
    console.print(halbierung.tabelle())
    console.print(f"\n{halbierung.urteil()}\n")


@app.command()
def tageszeit(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("15", "--intervall", "-i"),
    stunden: bool = typer.Option(
        False, "--stunden", help="Zusaetzlich die 24 Einzelstunden zeigen."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sagt die Uhrzeit etwas - die Quelle, die Tageskerzen nicht kennen.

    Befund 62: Fuenfzehnminutenkerzen tragen den Deflated Sharpe arithmetisch.
    Was fehlt, ist ein Vorteil. ``cli scan`` hat dort gesucht und nichts
    Stabiles gefunden - aber er prueft **eine** Art Signal: Momentum.

    Die Uhrzeit ist eine andere Quelle, und sie hat eine Eigenschaft, die
    keine andere hat: **Auf Tageskerzen ist sie prinzipiell unsichtbar.** Wer
    nur Tageskerzen ausgemessen hat, hat diese Frage nie gestellt.

    Geprueft werden **vorab festgelegte** Fenster aus der Marktstruktur - die
    drei Handelssitzungen und ihre Ueberschneidungen. Alle 4600 moeglichen
    Fenster zu pruefen und das beste zu nehmen waere genau die Ueberanpassung,
    gegen die dieser Scan gebaut ist.

    Dieselben drei Huerden wie im Vorteilsscan: auffaellig gegen die Zahl der
    geprueften Fenster, stabil ueber beide Haelften, nach Gebuehren etwas
    uebrig. Kostet keinen Versuch.
    """
    from research.tageszeit import (
        pruefe_stabilitaet,
        scanne_sitzungen,
        scanne_stunden,
        urteil,
    )

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)

    for symbol in (s.strip() for s in maerkte.split(",") if s.strip()):
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[yellow]Keine Kerzen fuer {symbol}.[/]")
            continue

        console.print(
            f"\n[bold]{symbol}[/] {interval_obj.label}, {len(frame)} Kerzen "
            f"({frame['open_time'].iloc[0]:%Y-%m-%d} bis "
            f"{frame['open_time'].iloc[-1]:%Y-%m-%d})"
        )
        fenster = scanne_sitzungen(frame)
        if stunden:
            fenster = fenster + scanne_stunden(frame)
            fenster.sort(key=lambda f: -abs(f.t_wert))

        tabelle = Table(header_style="bold")
        tabelle.add_column("Fenster")
        tabelle.add_column("UTC", justify="right")
        tabelle.add_column("Tage", justify="right")
        tabelle.add_column("je Tag", justify="right")
        tabelle.add_column("t", justify="right")
        tabelle.add_column("netto", justify="right")
        for f in fenster[:8]:
            netto = f.netto_pct()
            tabelle.add_row(
                f.name,
                f"{f.von:02d}-{f.bis:02d}",
                str(f.tage),
                f"{f.spanne_pct:+.4f}%",
                f"{f.t_wert:+.2f}",
                f"[{'green' if netto > 0 else 'red'}]{netto:+.4f}%[/]",
            )
        console.print(tabelle)

        bestes = fenster[0] if fenster else None
        stabil = pruefe_stabilitaet(frame, bestes) if bestes is not None else None
        console.print(urteil(bestes, stabil, geprueft=len(fenster)))

    console.print(
        f"\n[dim]Kosten je Roundtrip: {0.04:.2f} % vom Nominalwert. Ein "
        f"Zeitfenster heisst ein Ein- und Ausstieg je Tag.[/]\n"
    )


@app.command()
def taktung(
    symbol: str = typer.Option("BTCUSD_BITSTAMP", "--symbol", "-s"),
    intervalle: str = typer.Option(
        "D:40,15:16,15:96", "--intervalle",
        help="Kerzenlaenge:Haltedauer, durch Komma.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Welche Kerzenlaenge kann den Deflated Sharpe arithmetisch tragen?

    Befund 61: Von vier offenen Gates ist genau eines ein ungeloestes
    Qualitaetsproblem. Befund 54: Auf Tageskerzen ist es nicht loesbar, weil
    Qualitaet und Menge dort gekoppelt sind - die Historie gibt nur rund 3300
    Tage her.

    Auf Fuenfzehnminutenkerzen liegen 222 700 Kerzen. Die naheliegende
    Hoffnung: Der noetige Vorteil je Trade faellt mit ``1/sqrt(N)``, also
    reicht bei vielen Trades ein winziger. **Der Haken ist rechenbar** - der
    noetige Vorteil faellt mit der Wurzel, die Gebuehr je Trade bleibt
    konstant. Irgendwo schneiden sich die Linien.

    Die Streuung je Trade wird dabei **gemessen**, nicht mit der Wurzel der
    Zeit hochgerechnet: Die Abkuerzung setzt Unabhaengigkeit voraus, die es
    bei Kursen nicht gibt, und liefert fuer kurze Haltedauern zu kleine Zahlen
    - also eine zu optimistische Rechnung.

    Sagt **nicht**, ob dort ein Vorteil existiert - das misst ``cli scan``.
    Nur, wie gross er sein muesste. Kostet keinen Versuch.
    """
    from research.admission import load_trials
    from research.taktung import rechne

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    versuche = load_trials(Path(settings.paths.state) / "trials.json")

    console.print(
        f"\n[bold]Taktung[/] {symbol}, Huerde bei {versuche} Versuchen\n"
        f"[dim]Gebuehr {0.04:.2f} % je Roundtrip, beide Seiten Limit.[/]\n"
    )
    for eintrag in intervalle.split(","):
        roh, _, halten = eintrag.strip().partition(":")
        if not roh or not halten.isdigit():
            console.print(f"[red]'{eintrag}' ist kein Paar Kerzenlaenge:Haltedauer.[/]")
            raise typer.Exit(2)
        interval_obj = Interval(roh)
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[yellow]Keine Kerzen fuer {interval_obj.label}.[/]")
            continue

        ergebnis = rechne(
            frame,
            name=interval_obj.label,
            haltedauer=int(halten),
            versuche=versuche,
        )
        console.print(f"[bold]{ergebnis.name}[/]")
        console.print(ergebnis.tabelle())
        console.print(f"\n{ergebnis.urteil()}\n")


@app.command()
def gatemuster(
    hoechstens: int = typer.Option(10, "--hoechstens", "-n", help="Wie viele Paare."),
) -> None:
    """Welche der elf Gates messen eigentlich verschiedene Dinge?

    Aus Befund 60: Zwei Massnahmen haben dieselben zwei Gates gekippt, und
    beide Male war es das blosse Streichen von Trades. Daraus folgt die
    Frage, ob "sieben von elf" ueberhaupt sieben von elf unabhaengigen
    Huerden bedeutet.

    **Das ist keine Vorbereitung darauf, ein Gate zu streichen.** Ein Gate zu
    entfernen, weil es "ohnehin dasselbe misst", waere die eleganteste Art,
    die Latte zu senken. Der Nutzen ist ein anderer: Wer weiss, welche Huerden
    zusammenfallen, weiss, wo eine Verbesserung ueberhaupt etwas bewirkt - und
    wo ein Fortschritt groesser aussieht, als er ist.

    Liest nur vorhandene Berichte. Kostet keinen Versuch.
    """
    from research.gatemuster import Gatemuster, lade

    ordner = Path.cwd() / "reports"
    muster = Gatemuster(
        punkte=lade(ordner / "machbarkeit", ordner / "teststaerke")
    )

    console.print("\n[bold]Gatemuster[/] ueber alle vorhandenen Messpunkte\n")
    if muster.punkte:
        console.print(muster.tabelle(hoechstens=hoechstens))
    console.print(f"\n{muster.urteil()}\n")


@app.command()
def vereinbar(
    regler: str = typer.Option("Vola-Ziel", "--regler", "-r"),
    rendite: float = typer.Option(15.0, "--rendite", help="Mindestrendite in %."),
    rueckgang: float = typer.Option(12.0, "--rueckgang", help="Hoechster Rueckgang."),
    mit_jahr: bool = typer.Option(
        False, "--mit-jahr",
        help="Das schlechteste Jahr als dritte Schwelle mitpruefen.",
    ),
) -> None:
    """Sind Mindestrendite und Rueckgangsgrenze zugleich erfuellbar?

    In ``stand.py`` steht seit langem der Satz: *"Sie steht im Konflikt mit
    der Rueckgangsgrenze - was die eine verlangt, reisst die andere."* Das ist
    eine Behauptung, und sie war nie gemessen.

    Hier wird sie beziffert. Ein Groessenregler ist dafuer die saubere Achse:
    Er skaliert jede Position gleich und laesst die Qualitaet je Trade
    unveraendert - Rendite und Rueckgang wachsen also beide mit ihm, und die
    Frage wird geometrisch. Geht die Kurve durch das erlaubte Rechteck?

    **Was hier nicht passiert: die Wahl eines Betriebspunkts.** Ein Treffer
    waere ein Befund ueber die Schwellen, keine Empfehlung. Den Kandidaten
    dorthin zu stellen, wo mehr Gates bestehen, ist genau die Anpassung, gegen
    die die Zulassungsstrecke gebaut ist.

    Liest nur vorhandene Berichte - kostet keinen Versuch. Neue Stellungen
    misst ``cli machbarkeit``, und die zaehlt.
    """
    from research.vereinbar import (
        SCHLECHTESTES_JAHR,
        Schwelle,
        Vereinbarkeit,
        lade,
    )

    punkte = lade(Path.cwd() / "reports" / "machbarkeit", regler=regler)
    lage = Vereinbarkeit(
        regler=regler,
        punkte=punkte,
        a=Schwelle("Rendite", "cagr", rendite, mindestens=True),
        b=Schwelle("Rueckgang", "rueckgang", rueckgang, mindestens=False),
        # Die dritte Schwelle seit Befund 94. Standardmaessig aus, weil die
        # aelteren Machbarkeitsberichte sie nicht enthalten - dort waere jeder
        # Punkt "nicht beurteilbar" und das Urteil damit wertlos.
        weitere=[SCHLECHTESTES_JAHR] if mit_jahr else [],
    )

    console.print(f"\n[bold]Vereinbarkeit[/] auf dem Regler '{regler}'\n")
    if punkte:
        console.print(lage.tabelle())
    console.print(f"\n{lage.urteil()}\n")


@app.command()
def front(
    hoechstens: int = typer.Option(12, "--hoechstens", "-n", help="Wie viele Zeilen."),
) -> None:
    """Alles, was je gemessen wurde - gegen die Linie, die es reissen muesste.

    Vierzehn Richtungen sind geschlossen, und vier davon zeigen dasselbe
    Muster: Jeder Weg, der eine Kennzahl verbessert, verschlechtert den
    Deflated Sharpe ueber einen anderen Kanal. Vier Einzelfaelle sind ein
    Verdacht, keine Aussage.

    Die Aussage waere: **Kein Punkt dieser Regelfamilie liegt ueber seiner
    eigenen Grenzlinie.** Diese Auskunft steht schon in den
    Machbarkeitsberichten - sie musste nur einmal zusammengelegt werden.

    **Kostet keinen Versuch.** Es wird nichts gerechnet, was nicht schon
    gerechnet wurde.
    """
    from pathlib import Path

    from research.admission import load_trials
    from research.front import Front, lade

    settings = get_settings()
    trials = load_trials(Path(settings.paths.state) / "trials.json")
    # Berichte liegen unter <cwd>/reports/<art> - dieselbe Stelle, an die
    # ``core.report.write_report`` sie legt.
    punkte = lade(Path.cwd() / "reports" / "machbarkeit")
    if not punkte:
        console.print(
            "[yellow]Keine einordenbaren Messpunkte.[/] Erst abtasten: "
            "python -m cli machbarkeit --regler stop"
        )
        raise typer.Exit(0)

    lage = Front(punkte=punkte, versuche=trials)
    # ``lage.punkte`` ist entdoppelt, ``punkte`` nicht - gezaehlt wird, was
    # ausgewertet wird. Wie viele Laeufe dahinterstehen, steht daneben
    # (Befund 150).
    mehrfach = len(punkte) - len(lage.punkte)
    console.print(
        f"\n[bold]Die gemessene Front[/]\n"
        f"  Punkte     {len(lage.punkte)} aus "
        f"{len({p.regler for p in lage.punkte})} Reglern"
        + (
            f"  [dim]({mehrfach} mehrfach gemessene Laeufe zusammengezogen, "
            f"behalten wurde der gegen die haerteste Huerde)[/]"
            if mehrfach
            else ""
        )
        + f"\n  Versuche   {trials}\n"
    )
    console.print(lage.tabelle(hoechstens=hoechstens))
    farbe = "green" if lage.bestanden else "yellow"
    console.print(f"\n[{farbe}]{lage.urteil()}[/]\n")
    console.print(
        "[dim]Die Spalte DSR ist der **gemessene** Gate-Wert und damit das "
        "Urteil. ~ heisst nur, dass der Bericht die Form der Verteilung nicht "
        "mittrug - dann ist die Uebersetzung in Sharpe-Einheiten ungenau, das "
        "Urteil nicht.\n"
        "Und: Das ist eine Aussage ueber die gemessenen Punkte, nicht ueber "
        "alle denkbaren.[/]\n"
    )


@app.command()
def anwaerter(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    vola_ziel: float = typer.Option(19.3, "--vola-ziel"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Welches Genom im Katalog taugt als Verbund-Partner?

    Befund 74 hat die Anforderung beziffert: mindestens rund 120 Trades und
    moeglichst wenig Fensterkorrelation zum Bestand. Dieser Befehl misst
    beides fuer jedes Genom der Generationen, die auf dieses Intervall
    gehoeren, und haelt sie gegen die Partnerkarte.

    **Kostet keinen Versuch.** Gemessen werden Trade-Zahl, Qualitaet je Trade
    und Korrelation - keine Gates, kein Deflated Sharpe, keine Auswahl. Wer
    danach einen dieser Anwaerter tatsaechlich als Verbund prueft, muss die
    Durchmusterung allerdings mitzaehlen: Dann ist sie eine Auswahl ueber
    viele Hypothesen geworden.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.partnerkarte import Anwaerter, Katalogkopplung, Partnerkarte
    from research.seeds import VORGESEHEN, load_seeds, spitzenkandidat
    from research.suchbudget import Kandidat
    from research.verbund import fensterkorrelation, noetige_guete
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec

    _configure_logging(verbose)
    settings = get_settings()
    versuche = load_trials(Path(settings.paths.state) / "trials.json")
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)

    def lauf(genome):
        angepasst = genome.model_copy(
            update={
                "sizing": SizingSpec(
                    kind="vola_ziel", fraction=3.0,
                    target_vol_pct=vola_ziel, vol_period=30,
                )
            }
        )
        return run_portfolio_walkforward(
            frames, lambda g=angepasst: compile_genome(g), configs
        )

    bestand = spitzenkandidat()
    spitze = lauf(bestand)
    eigen = Kandidat.aus_trades(bestand.name, list(spitze.all_trades))
    if eigen is None:
        console.print("[red]Der Bestand liefert keine Trades.[/]")
        raise typer.Exit(2)

    passende = [g for g, iv in VORGESEHEN.items() if iv == interval_obj.value]
    console.print(
        f"\n[bold]Anwaerter als Verbund-Partner[/] auf {' + '.join(symbole)} "
        f"{interval_obj.label}\n"
        f"  Bestand    '{bestand.name}': {len(spitze.all_trades)} Trades zu je "
        f"{eigen.sharpe_je_trade:.4f}\n"
        f"  Katalog    Generationen {', '.join(str(g) for g in sorted(passende))}\n"
        f"  Historie   {spanne} Tage, {versuche} Versuche bisher\n"
    )

    gefunden: dict[tuple[int, float], Anwaerter] = {}
    for gen in sorted(passende):
        for genome in load_seeds(gen):
            bericht = lauf(genome)
            trades = list(bericht.all_trades)
            kandidat = Kandidat.aus_trades(genome.name, trades)
            if kandidat is None or not bericht.windows:
                continue
            rho = fensterkorrelation(spitze, bericht)
            # Nach (Trades, Qualitaet) entdoppeln: Mehrere Generationen
            # enthalten dasselbe Genom unter anderem Namen, und doppelte
            # Punkte wuerden die Kopplung nach unten faelschen.
            gefunden[(len(trades), round(kandidat.sharpe_je_trade, 4))] = Anwaerter(
                name=f"{genome.name}  (rho {rho:+.3f})" if rho is not None
                else genome.name,
                trades=len(trades),
                sharpe_je_trade=kandidat.sharpe_je_trade,
            )

    liste = list(gefunden.values())
    if not liste:
        console.print("[yellow]Kein Genom lieferte Fenster.[/]")
        raise typer.Exit(0)

    # **Effektive** Stichprobe, nicht die rohe Trade-Zahl (Befund 139): Die
    # Latte gilt fuer die Zahl, mit der das Gate rechnet. Auf der rohen Zahl
    # waere sie eine Untergrenze - und die Partnerkarte wuerde Anwaerter fuer
    # tauglich erklaeren, die es nicht sind.
    from research.gates import stichprobe_wie_im_gate

    eigene_stichprobe = stichprobe_wie_im_gate(
        spitze.all_trades,
        bloecke=[[float(x.net_pnl) for x in w.trades] for w in spitze.windows],
    )
    ziel = noetige_guete(eigene_stichprobe.effektiv, versuche)
    karte = Partnerkarte(
        n1=eigene_stichprobe.effektiv, sr1=eigen.sharpe_je_trade, ziel=ziel
    )
    console.print(karte.einordnung(liste))

    tauglich = [a for a in liste if karte.reicht(a, 0.72)]
    farbe = "green" if tauglich else "yellow"
    console.print(
        f"\n[{farbe}]Tauglich nach der Karte: {len(tauglich)} von "
        f"{len(liste)}[/] (bei u = 0,72)\n"
    )
    # **Das rho in den Namen ist Auskunft, kein Massstab** (Befund 147).
    # Ueber vierzehn gemessene Paare ordnet die Fensterkorrelation das
    # Ergebnis nicht (+0,04); der beste Partner lag bei +0,56. Wer hier nach
    # kleinem rho auswaehlt, waehlt nach Rauschen.
    console.print(
        "[dim]Das rho hinter den Namen ordnet die Partner **nicht** "
        "(Rangkorrelation +0,04 ueber 14 gemessene Paare, Befund 141).\n"
        "Wer wissen will, was ein Partner wirklich bringt, misst ihn: "
        "[/][bold]cli paare[/][dim] baut den Verbund und rechnet ihn.[/]\n"
    )
    kopplung = Katalogkopplung(anwaerter=liste)
    if kopplung.genug:
        console.print(f"{kopplung.urteil()}\n")


@app.command()
def duerre(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Das schlechteste Jahr - ein Ausreisser oder eine Marktphase?

    ``gate_worst_year`` meldet eine einzelne Zahl: das Minimum ueber alle
    rollierenden Zwoelfmonatsfenster. Auf 93 Testmonaten sind das 2465
    Fenster, die sich fast vollstaendig ueberlappen - eine Stichprobe ist das
    nicht, und "nur zwei liegen darunter" ist deshalb kein Argument.

    Dieser Befehl ordnet die Zahl ein: wie viele **unabhaengige** Perioden
    darin stecken, ob die schlechten Fenster zusammenliegen oder streuen, und
    was Halten im selben Zeitraum gebracht haette.

    **Kostet keinen Versuch und aendert nichts.** Zerlegt wird eine
    Kapitalkurve, die ohnehin gerechnet wird. Keine Schwelle wird angefasst.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from backtest.walkforward import chained_curve
    from research.duerre import baue
    from research.gates import GateThresholds, _test_monate
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    store = CandleStore(settings.paths.data_store)

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame
    frames = common_range(roh)
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }
    genome = spitzenkandidat()
    bericht = run_portfolio_walkforward(
        frames, lambda: compile_genome(genome), configs
    )

    kurve = chained_curve(bericht)
    # Die Zeitstempel in **derselben** Reihenfolge wie die verkettete Kurve -
    # sonst zeigen die Datumsangaben auf andere Punkte als die Zahlen.
    zeiten: list = []
    for fenster in bericht.windows:
        eigen = getattr(fenster.result, "equity_curve", None)
        if eigen is None or eigen.empty:
            continue
        spalte = next(
            (s for s in ("time", "timestamp", "open_time", "date") if s in eigen),
            None,
        )
        zeiten.extend(eigen[spalte].tolist() if spalte else list(eigen.index))

    monate = _test_monate(bericht)
    schwellen = GateThresholds()
    lage = baue(
        kurve, testmonate=monate, grenze_pct=schwellen.worst_year_pct,
        zeiten=zeiten if len(zeiten) >= len(kurve) else None,
    )
    if lage is None:
        console.print("[red]Testzeitraum zu kurz fuer ein Zwoelfmonatsfenster.[/]")
        raise typer.Exit(2)

    # Was Halten im schlechtesten Fenster gebracht haette - erst jetzt, weil
    # das Fenster vorher nicht bekannt ist.
    markt: dict[str, float] = {}
    if lage.beginn and lage.ende:
        for symbol, frame in frames.items():
            innen = (frame["open_time"] >= lage.beginn) & (
                frame["open_time"] <= lage.ende
            )
            if int(innen.sum()) > 2:
                reihe = frame.loc[innen, "close"]
                markt[symbol] = float(reihe.iloc[-1] / reihe.iloc[0] - 1.0) * 100.0
        lage = baue(
            kurve, testmonate=monate, grenze_pct=schwellen.worst_year_pct,
            zeiten=zeiten if len(zeiten) >= len(kurve) else None, markt=markt,
        )

    console.print(
        f"\n[bold]Duerre[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Kandidat   {genome.name}\n"
        f"  Testmonate {monate:.0f}\n"
    )
    console.print(lage.tabelle())
    farbe = "green" if lage.besteht else "yellow"
    console.print(f"\n[{farbe}]{lage.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert - zerlegt wurde eine "
        "Kapitalkurve, die ohnehin gerechnet wird. Keine Schwelle wurde "
        "angefasst.[/]"
    )


@app.command()
def koernung(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    konten: str = typer.Option(
        "300,400,500,600,750,1000,1500,2000,3000,5000,10000,25000,50000,100000",
        "--konten", help="Startkapitalien, durch Komma getrennt.",
    ),
    gates: bool = typer.Option(
        False, "--gates",
        help="Zusaetzlich alle elf Gates je Kontostand auswerten. Dauert "
             "ein Vielfaches - die Gates sind der teure Teil.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Haengt das Rueckgang-Gate am Kontostand statt an der Strategie?

    Bybit handelt BTC in Schritten von 0,001 und ETH in Schritten von 0,01,
    und die berechnete Menge wird darauf **abgerundet**. Bei 500 EUR Konto ist
    eine BTC-Position knapp drei Mengenschritte gross - der Groessenregler hat
    dort also eine Aufloesung von einem Drittel der Position.

    Dieser Befehl faehrt dieselbe Strategie ueber eine Leiter von
    Kontostaenden und misst, wie weit die Gate-Zahlen dabei wandern. Dazu
    kommt eine Gegenprobe mit feinem Mengenschritt: Sie aendert **nur** die
    Rundung und sonst nichts.

    Mit ``--gates`` laufen zusaetzlich alle elf Gates je Sprosse. Gemessen
    sind dann zwei Wanderer - Rueckgang und schlechtestes Jahr - und neun
    feste, darunter der Deflated Sharpe.

    **Kostet keinen Versuch.** Der Zaehler korrigiert das Testen vieler
    Strategie-Hypothesen; hier ist die Strategie in jeder Zeile dieselbe, und
    ausgewaehlt wird nichts. Der Betriebspunkt wird auch nicht nachgezogen.
    """
    from decimal import Decimal

    import numpy as np

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import GateThresholds, evaluate_gates
    from research.koernung import (
        Gatelauf,
        Gateleiter,
        Gatewert,
        Koernung,
        Kontostufe,
        umsetzung,
    )
    from research.seeds import spitzenkandidat
    from strategy import indicators
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    store = CandleStore(settings.paths.data_store)

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame
    frames = common_range(roh)
    genome = spitzenkandidat()

    erster = next(iter(frames.values()))
    # In **jeder** Zeile derselbe Versuchsstand. Waere er je Sprosse anders,
    # verglichen die Spalten zwei verschiedene Huerden miteinander.
    trials = load_trials(Path(settings.paths.state) / "trials.json")

    def lauf(
        kapital: Decimal, *, fein: bool, mit_gates: bool = False
    ) -> tuple[Kontostufe, Gatelauf | None] | None:
        configs = {}
        for x in symbole:
            instrument = _fallback_instrument(_bybit_kontrakt(x))
            if fein:
                # Nur die Rundung wird entfernt, sonst nichts: derselbe
                # Kontrakt, dieselben Gebuehren, dasselbe Konto.
                instrument = instrument.model_copy(
                    update={
                        "qty_step": Decimal("0.00000001"),
                        "min_order_qty": Decimal("0.00000001"),
                    }
                )
            configs[x] = BacktestConfig(
                instrument=instrument, risk=settings.risk,
                initial_equity=kapital, enforce_risk_limits=True,
                kalender=_terminkalender(settings) or None,
            )
        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs
        )
        if not bericht.windows or bericht.combined is None:
            return None
        stufe = Kontostufe(
            kapital=float(kapital),
            cagr=float(bericht.combined.cagr_pct),
            rueckgang=float(bericht.combined.max_drawdown_pct),
            trades=len(bericht.all_trades),
        )
        if not mit_gates:
            return stufe, None
        bericht_gates = evaluate_gates(
            genome, bericht, erster, configs[symbole[0]],
            trials_so_far=trials, frames=frames, configs=configs,
        )
        return stufe, Gatelauf(
            kapital=float(kapital),
            gates=tuple(
                Gatewert(
                    name=r.name, bestanden=bool(r.passed),
                    wert=float(r.value), schwelle=float(r.threshold),
                )
                for r in bericht_gates.results
            ),
        )

    kapitalien = [Decimal(x.strip()) for x in konten.split(",") if x.strip()]
    if len(kapitalien) < 3:
        console.print("[red]Mindestens drei Kontostaende noetig.[/]")
        raise typer.Exit(2)

    console.print(
        f"\n[bold]Koernung[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Kandidat   {genome.name}\n"
        f"  Konten     {len(kapitalien)} Sprossen von {kapitalien[0]:g} bis "
        f"{max(kapitalien):g} EUR\n"
    )

    stufen = []
    gatelaeufe = []
    for kapital in kapitalien:
        ergebnis = lauf(kapital, fein=False, mit_gates=gates)
        if ergebnis is None:
            console.print(f"[yellow]{kapital:g} EUR: keine Fenster.[/]")
            continue
        stufe, gatelauf = ergebnis
        stufen.append(stufe)
        if gatelauf is not None:
            gatelaeufe.append(gatelauf)
        console.print(
            f"[dim]  {kapital:>9g} EUR  {stufe.trades:>4} Trades  "
            f"{stufe.cagr:>6.2f} % p.a.  Rueckgang {stufe.rueckgang:>5.2f} %"
            + (f"  {gatelauf.bestanden}/{gatelauf.gesamt} Gates" if gatelauf else "")
            + "[/]"
        )

    # Die Gegenprobe laeuft auf dem Referenzkonto der Zulassung, nicht auf
    # der kleinsten Sprosse: Verglichen werden darf sie nur mit dem Lauf, der
    # sich sonst in nichts von ihr unterscheidet.
    referenz = Decimal("500") if Decimal("500") in kapitalien else kapitalien[0]
    feinlauf = lauf(referenz, fein=True)
    fein = feinlauf[0] if feinlauf is not None else None

    bild = Koernung(
        stufen=stufen,
        grenze_pct=GateThresholds().max_oos_drawdown_pct,
        feinmessung=fein,
    )
    console.print("\n" + bild.tabelle())
    farbe = "yellow" if bild.spanne >= 0.05 else "green"
    console.print(f"\n[{farbe}]{bild.urteil()}[/]\n")

    # Die Rundung laesst sich auch ohne Backtest beziffern - und diese Zahl
    # sagt, warum ausgerechnet der Rueckgang betroffen ist.
    console.print("[bold]Wie viel der geplanten Menge uebrig bleibt[/]")
    vola_ziel = genome.sizing.target_vol_pct
    for symbol, frame in frames.items():
        schritt = float(_fallback_instrument(_bybit_kontrakt(symbol)).qty_step)
        vola = indicators.compute(
            "realized_vol", frame, {"period": genome.sizing.vol_period}
        )
        anteile = np.clip(vola_ziel / vola, 0.0, genome.sizing.fraction)
        preise = frame["close"].to_numpy(dtype=float)
        mitte = float(np.nanmedian(vola))
        ruhig = vola <= mitte
        for kapital in (float(referenz), float(max(kapitalien))):
            gesamt = umsetzung(anteile, preise, kapital=kapital, schritt=schritt)
            still = umsetzung(
                anteile[ruhig], preise[ruhig], kapital=kapital, schritt=schritt
            )
            sturm = umsetzung(
                anteile[~ruhig], preise[~ruhig], kapital=kapital, schritt=schritt
            )
            console.print(
                f"[dim]  {symbol[:14]:<14} {kapital:>8,.0f} EUR   "
                f"gesamt {gesamt:.3f}   ruhig {still:.3f}   "
                f"Sturm {sturm:.3f}[/]"
            )
    console.print(
        "\n[dim]Das Vola-Ziel macht die Position im Sturm klein - und kleine "
        "Positionen verstuemmelt das Abrunden am staerksten. Das kleine Konto "
        "bekommt damit einen zweiten, unbeabsichtigten Vola-Filter geschenkt.[/]"
    )

    if gatelaeufe:
        console.print(f"\n[bold]Alle Gates je Kontostand[/] (Versuchsstand {trials})")
        leiter = Gateleiter(laeufe=gatelaeufe)
        console.print("\n" + leiter.tabelle())
        console.print(
            f"\n[{'yellow' if leiter.wandernde else 'green'}]"
            f"{leiter.urteil()}[/]\n"
        )

    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert: Die Strategie ist in "
        "jeder Zeile dieselbe, veraendert wird der Kontostand.[/]\n"
    )


@app.command()
def instrument(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    gebuehren: str = typer.Option(
        "", "--gebuehren",
        help="Statt der Instrumentenfrage: Spot-Laeufe bei diesen Vielfachen "
             "des Perpetual-Tarifs, durch Komma. Beispiel: 1,2,2.75,3",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Braucht der Kandidat ein Perpetual - oder genuegt Spot?

    Der Plan nennt es als offene Frage: Bybit EU bietet womoeglich nur noch
    Spot an, und damit weder Hebel noch Funding. Der ganze Backtest rechnet
    aber Perpetuals.

    Gemessen wird, ob der Kandidat das ueberhaupt braucht: derselbe Lauf mit
    ``fraction`` auf 1,0, und derselbe ohne Funding. Aendern sich die Zahlen
    unter dem Deckel nicht, ist der Hebel nachweislich ungenutzt - das ist
    eine Messung und keine Schwelle, die man sich aussucht.

    **Kostet keinen Versuch.** Derselbe Kandidat, dieselben Daten, unter
    anderen Handelsbedingungen.
    """
    from decimal import Decimal

    import numpy as np

    from backtest.costs import FundingSchedule
    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import evaluate_gates
    from research.instrument import Instrumentenwahl, Lauf
    from research.seeds import spitzenkandidat
    from strategy import indicators
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    store = CandleStore(settings.paths.data_store)

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame
    frames = common_range(roh)
    erster = next(iter(frames.values()))
    trials = load_trials(Path(settings.paths.state) / "trials.json")
    basis = spitzenkandidat()
    ohne_hebel = basis.model_copy(
        update={"sizing": basis.sizing.model_copy(update={"fraction": 1.0})}
    )

    def baue_configs(*, funding: str, faktor) -> dict:
        aus = {}
        for x in symbole:
            grund = BacktestConfig(
                instrument=_fallback_instrument(_bybit_kontrakt(x)),
                risk=settings.risk, initial_equity=Decimal("500"),
                enforce_risk_limits=True,
                kalender=_terminkalender(settings) or None,
            )
            aus[x] = BacktestConfig(
                instrument=grund.instrument, risk=grund.risk,
                costs=grund.costs.scaled(Decimal(str(faktor)))
                if float(faktor) != 1.0 else grund.costs,
                funding=FundingSchedule(default_rate=Decimal(funding)),
                initial_equity=grund.initial_equity,
                enforce_risk_limits=True,
                allow_shorts=grund.allow_shorts,
                entry_expiry_bars=grund.entry_expiry_bars,
                max_hold_bars=grund.max_hold_bars,
                kalender=grund.kalender,
            )
        return aus

    if gebuehren:
        # Traegt der Spot-Vorteil auch den hoeheren Spot-Tarif? Gemessen wird
        # mit Vielfachen des Perpetual-Tarifs, weil der echte Spot-Satz aus
        # diesem Container nicht nachzuschlagen ist.
        from research.instrument import Gebuehrenstufe, Tragfaehigkeit
        from research.suchbudget import Budget, Kandidat

        faktoren = [float(x.strip()) for x in gebuehren.split(",") if x.strip()]
        if len(faktoren) < 2:
            console.print("[red]Mindestens zwei Faktoren noetig.[/]")
            raise typer.Exit(2)

        console.print(
            f"\n[bold]Instrument - Gebuehrentragfaehigkeit[/] "
            f"{' + '.join(symbole)} {interval_obj.label}\n"
            f"  Kandidat   {basis.name}, Spot (kein Hebel, kein Funding)\n"
            f"  Versuche   {trials}\n"
        )

        def spotlauf(faktor: float):
            configs = baue_configs(funding="0", faktor=faktor)
            bericht = run_portfolio_walkforward(
                frames, lambda: compile_genome(ohne_hebel), configs
            )
            ergebnisse = evaluate_gates(
                ohne_hebel, bericht, erster, configs[symbole[0]],
                trials_so_far=trials, frames=frames, configs=configs,
            )
            dsr = next(r for r in ergebnisse.results if r.name == "Deflated Sharpe")
            eintrag = Kandidat.aus_trades("Spot", bericht.all_trades)
            stufe = Gebuehrenstufe(
                faktor=faktor, dsr=float(dsr.value),
                guete=eintrag.sharpe_je_trade if eintrag else 0.0,
                cagr=float(bericht.combined.cagr_pct),
                bestanden=sum(1 for r in ergebnisse.results if r.passed),
                gesamt=len(ergebnisse.results),
                gescheitert=tuple(
                    r.name for r in ergebnisse.results if not r.passed
                ),
                gebuehren=sum(float(t.fees) for t in bericht.all_trades),
            )
            console.print(
                f"[dim]  x{faktor:<5g} DSR {stufe.dsr:.4f}  "
                f"Guete {stufe.guete:.4f}  {stufe.cagr:>6.2f} % p.a.  "
                f"{stufe.bestanden}/{stufe.gesamt} Gates[/]"
            )
            return stufe, eintrag, float(dsr.threshold)

        stufen, erster_eintrag, schwelle = [], None, 0.95
        for faktor in faktoren:
            stufe, eintrag, grenze = spotlauf(faktor)
            stufen.append(stufe)
            if erster_eintrag is None:
                erster_eintrag, schwelle = eintrag, grenze

        # Der Vergleichswert: derselbe Kandidat als Perpetual.
        perp_configs = baue_configs(funding="0.0001", faktor=1)
        perp = run_portfolio_walkforward(
            frames, lambda: compile_genome(basis), perp_configs
        )
        perp_gates = evaluate_gates(
            basis, perp, erster, perp_configs[symbole[0]],
            trials_so_far=trials, frames=frames, configs=perp_configs,
        )
        perp_dsr = next(
            r for r in perp_gates.results if r.name == "Deflated Sharpe"
        )
        perp_eintrag = Kandidat.aus_trades("Perpetual", perp.all_trades)

        noetig = 0.0
        if erster_eintrag is not None:
            noetig = float(
                Budget(versuche=trials, kandidaten=[erster_eintrag])
                .abstaende()[0]
                .noetig
            )

        bild = Tragfaehigkeit(
            stufen=stufen, schwelle=schwelle,
            dsr_perpetual=float(perp_dsr.value),
            guete_perpetual=perp_eintrag.sharpe_je_trade if perp_eintrag else 0.0,
            noetige_guete=noetig, versuche=trials,
        )
        console.print("\n" + bild.tabelle())
        console.print(f"\n[yellow]{bild.urteil()}[/]\n")
        console.print(
            "[dim]Der Versuchszaehler bleibt unveraendert: derselbe Kandidat "
            "unter anderen Kostenannahmen.[/]\n"
        )
        return

    def messe(name: str, genome, *, funding: str, gebuehrenfaktor: int) -> Lauf:
        configs = {}
        for x in symbole:
            grund = BacktestConfig(
                instrument=_fallback_instrument(_bybit_kontrakt(x)),
                risk=settings.risk, initial_equity=Decimal("500"),
                enforce_risk_limits=True,
                kalender=_terminkalender(settings) or None,
            )
            configs[x] = BacktestConfig(
                instrument=grund.instrument, risk=grund.risk,
                costs=grund.costs.scaled(Decimal(gebuehren))
                if gebuehrenfaktor != 1 else grund.costs,
                funding=FundingSchedule(default_rate=Decimal(funding)),
                initial_equity=grund.initial_equity,
                enforce_risk_limits=True,
                allow_shorts=grund.allow_shorts,
                entry_expiry_bars=grund.entry_expiry_bars,
                max_hold_bars=grund.max_hold_bars,
                kalender=grund.kalender,
            )
        bericht = run_portfolio_walkforward(
            frames, lambda g=genome: compile_genome(g), configs
        )
        gates = evaluate_gates(
            genome, bericht, erster, configs[symbole[0]],
            trials_so_far=trials, frames=frames, configs=configs,
        )
        k = bericht.combined
        lauf = Lauf(
            name=name, trades=len(bericht.all_trades),
            cagr=float(k.cagr_pct), rueckgang=float(k.max_drawdown_pct),
            bestanden=sum(1 for r in gates.results if r.passed),
            gesamt=len(gates.results),
            gescheitert=tuple(r.name for r in gates.results if not r.passed),
            funding=sum(float(t.funding) for t in bericht.all_trades),
            gebuehren=sum(float(t.fees) for t in bericht.all_trades),
            brutto=sum(float(t.gross_pnl) for t in bericht.all_trades),
            sharpe=float(k.sharpe),
        )
        console.print(
            f"[dim]  {name:<26} {lauf.trades:>4} Trades  {lauf.cagr:>6.2f} % "
            f"p.a.  Rueckgang {lauf.rueckgang:>5.2f} %  "
            f"{lauf.bestanden}/{lauf.gesamt} Gates[/]"
        )
        return lauf

    # Wie oft die Groessensteuerung ueber das eigene Kapital hinaus will -
    # auf genau den Balken, die der Backtest sieht.
    ueber_eins = []
    for frame in frames.values():
        vola = indicators.compute(
            "realized_vol", frame, {"period": basis.sizing.vol_period}
        )
        anteil = np.clip(
            basis.sizing.target_vol_pct / vola, 0.0, basis.sizing.fraction
        )
        gut = np.isfinite(anteil)
        ueber_eins.append(float(np.mean(anteil[gut] > 1.0)))

    console.print(
        f"\n[bold]Instrument[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Kandidat   {basis.name}\n"
        f"  Deckel     fraction {basis.sizing.fraction:g} -> 1,0\n"
        f"  Shorts     {len(basis.entry_short)} Einstiegs-, "
        f"{len(basis.exit_short)} Ausstiegsregeln\n"
    )

    wahl = Instrumentenwahl(
        mit_hebel=messe("Perpetual", basis, funding="0.0001", gebuehrenfaktor=1),
        ohne_hebel=messe(
            "fraction 1.0", ohne_hebel, funding="0.0001", gebuehrenfaktor=1
        ),
        spot=messe("Spot", ohne_hebel, funding="0", gebuehrenfaktor=1),
        spot_gestresst=messe(
            "Spot, doppelte Gebuehren", ohne_hebel, funding="0", gebuehrenfaktor=2
        ),
        short_regeln=len(basis.entry_short) + len(basis.exit_short),
        anteil_ueber_eins=max(ueber_eins) if ueber_eins else 0.0,
    )
    console.print("\n" + wahl.tabelle())
    farbe = "green" if wahl.spot_moeglich else "yellow"
    console.print(f"\n[{farbe}]{wahl.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert: derselbe Kandidat "
        "unter anderen Handelsbedingungen.[/]\n"
    )


@app.command()
def finanzierung(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    saetze: str = typer.Option(
        "0,0.00005,0.0001,0.0002,0.0003,0.0005", "--saetze",
        help="Funding-Saetze je Achtstundenperiode, durch Komma.",
    ),
    stress: bool = typer.Option(
        False, "--stress",
        help="Statt der Leiter: Was der Kosten-Stress-Test auslaesst.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Wie viel haengt am angenommenen Funding-Satz?

    Der Backtest belastet Perpetual-Positionen alle acht Stunden mit Funding.
    Ohne historische Raten setzt ``FundingSchedule`` den Bybit-Basiswert von
    0,01 % je Periode ein - rund 11 % im Jahr fuer eine dauerhaft gehaltene
    Long-Position. ``data_store/funding/`` ist leer; **jede Zahl dieses
    Projekts rechnet mit diesem Vorgabewert.**

    Gemessen wird, wie stark das Urteil daran haengt. Am Betriebspunkt ist
    Funding das 8,9-fache der Handelsgebuehren - der groesste Kostenblock des
    Systems steht auf einer Annahme.

    **Kostet keinen Versuch.** Derselbe Kandidat auf jeder Sprosse; veraendert
    wird eine Kostenannahme. Der Satz wird insbesondere **nicht** auf den Wert
    gestellt, bei dem mehr Gates halten.
    """
    from decimal import Decimal

    from backtest.costs import FundingSchedule
    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from data.funding import FundingStore
    from research.admission import load_trials
    from research.finanzierung import BASISSATZ, Finanzierung, Stufe
    from research.gates import evaluate_gates
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    store = CandleStore(settings.paths.data_store)

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame
    frames = common_range(roh)
    erster = next(iter(frames.values()))
    trials = load_trials(Path(settings.paths.state) / "trials.json")
    genome = spitzenkandidat()

    # Gibt es ueberhaupt echte Raten? Die Antwort gehoert in den Bericht und
    # nicht in eine Fussnote - ohne sie ist die ganze Leiter eine Annahme.
    laden = FundingStore(settings.paths.data_store)
    historie = any(
        not laden.read(_bybit_kontrakt(s)).empty for s in symbole
    )

    if stress:
        from backtest.engine import Backtester
        from backtest.metrics import compute_metrics
        from research.finanzierung import Stresslage
        from research.gates import GateThresholds

        faktor = Decimal(str(GateThresholds().cost_stress_factor))
        console.print(
            f"\n[bold]Was der Kosten-Stress stresst[/] (Faktor {faktor})\n"
        )

        def stresslauf(*, gebuehren: bool, funding: bool) -> float:
            gewinn = 0.0
            for x in symbole:
                grund = BacktestConfig(
                    instrument=_fallback_instrument(_bybit_kontrakt(x)),
                    risk=settings.risk, initial_equity=Decimal("500"),
                    kalender=_terminkalender(settings) or None,
                )
                cfg = BacktestConfig(
                    instrument=grund.instrument, risk=grund.risk,
                    costs=grund.costs.scaled(faktor) if gebuehren else grund.costs,
                    funding=FundingSchedule(
                        default_rate=grund.funding.default_rate
                        * (faktor if funding else 1)
                    ),
                    initial_equity=grund.initial_equity,
                    allow_shorts=grund.allow_shorts,
                    entry_expiry_bars=grund.entry_expiry_bars,
                    max_hold_bars=grund.max_hold_bars,
                )
                ergebnis = Backtester(cfg).run(frames[x], compile_genome(genome))
                gewinn += float(
                    compute_metrics(
                        ergebnis.trades, ergebnis.equity_curve,
                        initial_equity=cfg.initial_equity,
                        total_fees=ergebnis.total_fees,
                    ).net_profit
                )
            return gewinn

        lage = Stresslage(
            faktor=float(faktor),
            ohne_stress=stresslauf(gebuehren=False, funding=False),
            wie_gebaut=stresslauf(gebuehren=True, funding=False),
            mit_funding=stresslauf(gebuehren=True, funding=True),
        )
        for beschriftung, wert in (
            ("ohne Stress", lage.ohne_stress),
            ("wie gebaut", lage.wie_gebaut),
            ("mit Funding", lage.mit_funding),
        ):
            console.print(
                f"  {beschriftung:<14} {wert:>9.2f} EUR  "
                f"{'besteht' if wert > 0 else 'faellt durch'}"
            )
        console.print(
            f"\n[{'red' if lage.urteil_kippt else 'yellow'}]{lage.urteil()}[/]\n"
        )
        return

    werte = [float(x.strip()) for x in saetze.split(",") if x.strip()]
    if len(werte) < 3:
        console.print("[red]Mindestens drei Saetze noetig.[/]")
        raise typer.Exit(2)

    console.print(
        f"\n[bold]Finanzierung[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Kandidat   {genome.name}\n"
        f"  Historie   {'vorhanden' if historie else 'nicht vorhanden'}\n"
        f"  Saetze     {len(werte)} Sprossen\n"
    )

    stufen = []
    for satz in werte:
        configs = {
            x: BacktestConfig(
                instrument=_fallback_instrument(_bybit_kontrakt(x)),
                risk=settings.risk, initial_equity=Decimal("500"),
                enforce_risk_limits=True,
                kalender=_terminkalender(settings) or None,
                funding=FundingSchedule(default_rate=Decimal(str(satz))),
            )
            for x in symbole
        }
        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genome), configs
        )
        if not bericht.windows or bericht.combined is None:
            console.print(f"[yellow]Satz {satz:g}: keine Fenster.[/]")
            continue
        gates = evaluate_gates(
            genome, bericht, erster, configs[symbole[0]],
            trials_so_far=trials, frames=frames, configs=configs,
        )
        k = bericht.combined
        stufe = Stufe(
            satz=satz, cagr=float(k.cagr_pct),
            rueckgang=float(k.max_drawdown_pct),
            bestanden=sum(1 for r in gates.results if r.passed),
            gesamt=len(gates.results),
            funding=sum(float(t.funding) for t in bericht.all_trades),
            gebuehren=sum(float(t.fees) for t in bericht.all_trades),
            brutto=sum(float(t.gross_pnl) for t in bericht.all_trades),
            gescheitert=tuple(r.name for r in gates.results if not r.passed),
        )
        stufen.append(stufe)
        console.print(
            f"[dim]  {stufe.jahr_pct:>5.1f} % p.a.  Funding "
            f"{stufe.funding:>7.2f} EUR  Rendite {stufe.cagr:>6.2f} %  "
            f"Rueckgang {stufe.rueckgang:>5.2f} %  "
            f"{stufe.bestanden}/{stufe.gesamt} Gates[/]"
        )

    bild = Finanzierung(
        stufen=stufen, angenommen=BASISSATZ, historie_vorhanden=historie
    )
    console.print("\n" + bild.tabelle())
    farbe = "yellow" if bild.haengt_daran or not historie else "green"
    console.print(f"\n[{farbe}]{bild.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert: derselbe Kandidat auf "
        "jeder Sprosse, veraendert wird eine Kostenannahme.[/]\n"
    )


@app.command()
def aufloesung(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    fein: str = typer.Option(
        "15", "--fein", help="Kerzenlaenge der Feindaten."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Haengt das Ergebnis an einer Annahme, die die Engine mangels Daten trifft?

    Beruehrt eine Kerze sowohl Stop als auch Take-Profit, verraet OHLC nicht,
    was zuerst kam. Ohne feinere Kerzen gilt die pessimistische Annahme: erst
    Liquidation, dann Stop, dann Take-Profit. ``cli wettbewerb`` sucht nach
    Minutenkerzen - die gibt es hier nicht, wohl aber Fuenfzehnminutenkerzen.

    Dieser Befehl rechnet denselben Kandidaten zweimal und zaehlt dabei mit,
    wie oft die Engine wirklich fein aufgeloest hat. Ohne diese Zaehlung waere
    "kein Unterschied" womoeglich nur "die Feinkerzen sind nie angekommen" -
    ein Fehler ohne Fehlermeldung, vor dem die Engine selbst warnt.

    **Der Standard bleibt pessimistisch.** Alle bisherigen Eintraege sind so
    gerechnet, und die Annahme kann ein Ergebnis nur schlechter aussehen
    lassen, nie besser.

    **Kostet keinen Versuch.** Derselbe Kandidat, dieselben Daten, zweimal
    gerechnet.
    """
    from collections import Counter
    from decimal import Decimal

    from backtest import engine as engine_modul
    from backtest.engine import BacktestConfig, Backtester
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.aufloesung import Aufloesung, Messung
    from research.gates import evaluate_gates
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    fein_obj = Interval(fein)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    store = CandleStore(settings.paths.data_store)

    roh, feine = {}, {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame
        fein_frame = store.read(symbol, fein_obj)
        if not fein_frame.empty:
            feine[symbol] = fein_frame
    if not feine:
        console.print(
            f"[red]Keine {fein_obj.label}-Kerzen - ohne sie gibt es nichts "
            f"aufzuloesen.[/]"
        )
        raise typer.Exit(2)

    frames = common_range(roh)
    erster = next(iter(frames.values()))
    trials = load_trials(Path(settings.paths.state) / "trials.json")
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }
    genome = spitzenkandidat()

    console.print(
        f"\n[bold]Aufloesung[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Kandidat   {genome.name}\n"
        f"  Feindaten  {fein_obj.label} fuer {len(feine)} von {len(symbole)} "
        f"Beinen\n"
    )

    # Mitzaehlen, wie oft wirklich fein aufgeloest wurde. Ohne diese Zahl
    # laesst sich ein Nullergebnis nicht von einem stillen Fehlschlag
    # unterscheiden.
    zaehler: Counter = Counter()
    original = Backtester._segments

    def gezaehlt(self, arrays, index, sub_index):
        stuecke = original(self, arrays, index, sub_index)
        zaehler["balken"] += 1
        if len(stuecke) > 1:
            zaehler["fein"] += 1
        return stuecke

    messungen = {}
    gruende: Counter = Counter()
    for name, subs in (("pessimistisch", None), ("aufgeloest", feine)):
        if subs is not None:
            engine_modul.Backtester._segments = gezaehlt
        try:
            bericht = run_portfolio_walkforward(
                frames, lambda: compile_genome(genome), configs, sub_frames=subs
            )
        finally:
            engine_modul.Backtester._segments = original
        if not bericht.windows or bericht.combined is None:
            console.print(f"[red]{name}: keine Fenster.[/]")
            raise typer.Exit(2)
        gates = evaluate_gates(
            genome, bericht, erster, configs[symbole[0]],
            trials_so_far=trials, frames=frames, configs=configs,
        )
        k = bericht.combined
        messungen[name] = Messung(
            name=name, trades=len(bericht.all_trades),
            cagr=float(k.cagr_pct), rueckgang=float(k.max_drawdown_pct),
            sharpe=float(k.sharpe),
            bestanden=sum(1 for r in gates.results if r.passed),
            gesamt=len(gates.results),
        )
        if subs is not None:
            gruende = Counter(t.exit_reason for t in bericht.all_trades)

    probe = Aufloesung(
        pessimistisch=messungen["pessimistisch"],
        aufgeloest=messungen["aufgeloest"],
        feine_balken=zaehler["fein"],
        balken=zaehler["balken"],
        ausstiegsgruende=dict(gruende),
    )
    console.print(probe.tabelle())
    farbe = (
        "yellow" if not probe.belastbar or probe.haengt_an_der_annahme else "green"
    )
    console.print(f"\n[{farbe}]{probe.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert: derselbe Kandidat, "
        "dieselben Daten, zweimal gerechnet.[/]\n"
    )


@app.command()
def rangprobe(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    kapital: float = typer.Option(
        500.0, "--kapital", help="Kontostand fuer beide Laeufe."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Haelt die Rangfolge, wenn man die Mengenrundung entfernt?

    Jeder Eintrag der Bestenliste ist bei 500 EUR gemessen, also durch den
    Rundungsfilter aus Befund 95 hindurch. Der Filter ist nicht neutral: Er
    schneidet kleine Positionen staerker ab als grosse, und wie gross die
    Positionen sind, ist eine Eigenschaft des Genoms.

    Haengt die Rangfolge davon ab, hat die Suche nach einem verfaelschten
    Signal gesteuert und jeder Vergleich zweier Kandidaten stand auf Sand.
    Dieser Befehl misst jedes Genom des Katalogs zweimal - mit Bybits
    Mengenschritt und mit einem feinen - und vergleicht die Urteile.

    Genome ohne Trades bleiben aussen vor. Sie bestehen fuenf Gates, weil
    nichts schiefgehen kann, wo nichts passiert; ein Rang unter ihnen
    bedeutet nichts.

    **Kostet keinen Versuch.** Jedes Genom ist in beiden Spalten dasselbe,
    gemessen wird der Mengenschritt, und ausgewaehlt wird nichts.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import evaluate_gates
    from research.rangprobe import Doppel, Rangprobe, schranke
    from research.seeds import VORGESEHEN, load_seeds
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    store = CandleStore(settings.paths.data_store)

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame
    frames = common_range(roh)
    erster = next(iter(frames.values()))
    trials = load_trials(Path(settings.paths.state) / "trials.json")

    def baue_configs(*, fein: bool) -> dict:
        aus = {}
        for x in symbole:
            instrument = _fallback_instrument(_bybit_kontrakt(x))
            if fein:
                instrument = instrument.model_copy(
                    update={
                        "qty_step": Decimal("0.00000001"),
                        "min_order_qty": Decimal("0.00000001"),
                    }
                )
            aus[x] = BacktestConfig(
                instrument=instrument, risk=settings.risk,
                initial_equity=Decimal(str(kapital)), enforce_risk_limits=True,
                kalender=_terminkalender(settings) or None,
            )
        return aus

    konfigurationen = {False: baue_configs(fein=False), True: baue_configs(fein=True)}

    kandidaten = []
    for generation in sorted(
        g for g, i in VORGESEHEN.items() if i == interval_obj.value
    ):
        kandidaten.extend(load_seeds(generation))
    if not kandidaten:
        console.print(
            f"[red]Kein Katalog fuer {interval_obj.label} vorgesehen.[/]"
        )
        raise typer.Exit(2)

    console.print(
        f"\n[bold]Rangprobe[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Genome     {len(kandidaten)}\n"
        f"  Konto      {kapital:,.0f} EUR in beiden Laeufen\n"
        f"  Versuche   {trials} in beiden Laeufen\n"
    )

    doppel = []
    # Der Sharpe gehoert nicht in ``Doppel`` - dort steht, was fuer das
    # Urteil gebraucht wird. Hier ist er nur eine der drei geprueften
    # Erklaerungen und wird deshalb daneben gefuehrt.
    sharpe_je_name: dict[str, float] = {}
    for i, genome in enumerate(kandidaten, start=1):
        messwerte = {}
        for fein in (False, True):
            configs = konfigurationen[fein]
            bericht = run_portfolio_walkforward(
                frames, lambda g=genome: compile_genome(g), configs
            )
            if not bericht.windows or bericht.combined is None:
                break
            gates = evaluate_gates(
                genome, bericht, erster, configs[symbole[0]],
                trials_so_far=trials, frames=frames, configs=configs,
            )
            messwerte[fein] = (
                sum(1 for r in gates.results if r.passed),
                len(gates.results),
                float(bericht.combined.max_drawdown_pct),
                len(bericht.all_trades),
                float(bericht.combined.sharpe),
            )
        if len(messwerte) != 2:
            console.print(f"[yellow]{genome.name}: kein Ergebnis.[/]")
            continue
        grob, fein_werte = messwerte[False], messwerte[True]
        sharpe_je_name[genome.name] = grob[4]
        doppel.append(
            Doppel(
                name=genome.name, trades=grob[3],
                grob_bestanden=grob[0], fein_bestanden=fein_werte[0],
                grob_rueckgang=grob[2], fein_rueckgang=fein_werte[2],
                gesamt=grob[1],
            )
        )
        console.print(
            f"[dim]  {i:>2}/{len(kandidaten)} {genome.name[:40]:42} "
            f"{grob[0]}/{grob[1]} -> {fein_werte[0]}/{fein_werte[1]}[/]"
        )

    probe = Rangprobe(doppel=doppel)
    console.print("\n" + probe.tabelle())
    farbe = "green" if probe.rangfolge_haelt else "yellow"
    console.print(f"\n[{farbe}]{probe.urteil()}[/]\n")

    if probe.genug:
        # Drei Erklaerungen fuer die Streuung - und die Schranke steigt
        # deshalb. Wer drei prueft und jede einzeln gegen 2,0 haelt, faellt
        # auf genau die Falle herein, gegen die dieses Projekt gebaut ist.
        gepruefte = 3
        console.print("[bold]Was die Streuung der Luecken erklaert[/]")
        for name, werte in (
            ("Hoehe des Rueckgangs", [d.grob_rueckgang for d in probe.handelnde]),
            ("Zahl der Trades", [d.trades for d in probe.handelnde]),
            ("Sharpe", [sharpe_je_name[d.name] for d in probe.handelnde]),
        ):
            console.print(
                f"  {probe.erklaerung(name, werte, hypothesen=gepruefte)}"
            )
        console.print(
            f"\n[dim]Schranke {schranke(gepruefte):.2f} statt 2,00, weil "
            f"{gepruefte} Erklaerungen geprueft wurden. Bei dreien reisst "
            f"eine von sieben rein zufaellig die 2,00.[/]"
        )

    console.print(
        "\n[dim]Der Versuchszaehler bleibt unveraendert: Jedes Genom ist in "
        "beiden Spalten dasselbe, veraendert wird der Mengenschritt.[/]\n"
    )


@app.command()
def plateaubild(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    faktoren: str = typer.Option(
        "0.70,0.75,0.80,0.85,0.90,0.95,1.05,1.10,1.15,1.20,1.25,1.30",
        "--faktoren", help="Skalierungen der Perioden, durch Komma.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Nadelspitze, Flanke oder Plateau - was das Gate nicht unterscheiden kann.

    ``gate_parameter_plateau`` prueft je Stellgroesse zwei Nachbarn bei
    plus/minus 20 % und wertet das Minimum. Damit kann sein Wert nur 0, 0,5
    oder 1,0 sein - die Schwelle von 0,6 heisst faktisch "alle Nachbarn
    muessen tragen", und aus einem Fehlschlag ist nicht ablesbar, ob dort eine
    Nadel steht oder eine Kante.

    Dieser Befehl misst dieselbe Nachbarschaft feiner und sagt, welche Form
    die Landschaft hat, wie breit der tragfaehige Bereich ist und ob ein
    scheinbar besserer Punkt die eigene Auswahl schlaegt.

    **Kostet keinen Versuch und aendert nichts.** Variiert werden die
    Parameter eines vorhandenen Kandidaten - dasselbe, was das Gate ohnehin
    tut. Es wird kein Parameter verstellt und keine Schwelle angefasst; wer
    aus der Landschaft einen Wert ablesen und einbauen wollte, haette einen
    neuen Kandidaten gebaut und muesste ihn zaehlen.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig, Backtester
    from backtest.portfolio_walkforward import common_range
    from research.gates import skaliere_perioden, stellgroessen
    from research.plateaubild import baue
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    store = CandleStore(settings.paths.data_store)

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame
    frames = common_range(roh)
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }
    beine = [(frames[x], configs[x]) for x in symbole]
    genome = spitzenkandidat()

    def gewinn(g) -> float:
        return float(
            sum(
                Backtester(cfg).run(teil, compile_genome(g)).net_profit
                for teil, cfg in beine
            )
        )

    werte = [float(f) for f in faktoren.split(",") if f.strip()]
    console.print(
        f"\n[bold]Plateaubild[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Kandidat   {genome.name}\n"
        f"  Faktoren   {len(werte)} von {min(werte):.2f} bis {max(werte):.2f}\n"
    )

    basis = gewinn(genome)
    kurven: dict[str, list] = {}
    # "Alle gemeinsam" zuerst, dann jede Stellgroesse einzeln - dieselbe
    # Aufteilung wie in ``nachbarschaft``, damit die Zeilen mit denen des
    # Gates vergleichbar bleiben.
    aufgaben = [("alle gemeinsam", None)] + [
        (st.name, st.kennung) for st in stellgroessen(genome)
    ]
    for name, kennung in aufgaben:
        punkte = []
        for f in werte:
            nachbar = (
                skaliere_perioden(genome, f)
                if kennung is None
                else skaliere_perioden(genome, f, nur=kennung)
            )
            if nachbar is None or nachbar.genome_id == genome.genome_id:
                punkte.append((f, None))
                continue
            punkte.append((f, gewinn(nachbar)))
        kurven[name] = punkte

    landschaft = baue(kurven, basis=basis)
    console.print(f"[dim]Gewinn bei Faktor 1,00: {basis:.0f}[/]\n")
    console.print(landschaft.tabelle())
    eng = landschaft.engste
    farbe = "yellow" if eng is not None and eng.breite < 0.5 else "green"
    console.print(f"\n[{farbe}]{landschaft.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert - variiert wurden die "
        "Parameter eines vorhandenen Kandidaten, nichts wurde ausgewaehlt "
        "oder verstellt.[/]"
    )


@app.command()
def zeitachse(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    vola_ziel: float = typer.Option(19.3, "--vola-ziel"),
    durchlaeufe: int = typer.Option(600, "--durchlaeufe", help="Zuege der Nullprobe."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Kuerzt das Gate genug - oder nur dort, wo es ohnehin nicht wehtut?

    Befund 86 hat gemessen, dass die Trade-Achse systematisch zu optimistisch
    ist. Das Zulassungs-Gate rechnet auf der Trade-Achse und kuerzt die
    Stichprobe ueber Fensterkorrelation und gleichzeitige Positionen. Ob das
    reicht, war nie geprueft.

    Verglichen werden drei t-Werte je Regel: roh, nach der Kuerzung des Gates,
    und auf der Wochenachse. Dazu eine **Nullprobe** je Regel - dieselben
    Trade-Ergebnisse zufaellig ueber dieselben Wochen verteilt. Sie muss dicht
    an der Trade-Achse landen; tut sie es nicht, misst der Vergleich die
    Aggregation und nicht die Zeitstruktur, und das Urteil sagt das.

    **Kostet keinen Versuch.** Neu aggregiert werden Trades, die schon
    gerechnet sind. Es wird nichts ausgewaehlt und kein Gate geaendert.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.entdopplung import entdoppele
    from research.gates import stichprobe_wie_im_gate
    from research.seeds import VORGESEHEN, load_seeds, spitzenkandidat
    from research.suchbudget import Kandidat
    from research.zeitachse import messe
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)

    def lauf(genome):
        angepasst = genome.model_copy(
            update={
                "sizing": SizingSpec(
                    kind="vola_ziel", fraction=3.0,
                    target_vol_pct=vola_ziel, vol_period=30,
                )
            }
        )
        return run_portfolio_walkforward(
            frames, lambda g=angepasst: compile_genome(g), configs
        )

    kandidaten = [spitzenkandidat()]
    for gen in sorted(g for g, iv in VORGESEHEN.items() if iv == interval_obj.value):
        kandidaten.extend(load_seeds(gen))

    roh: dict[str, list] = {}
    gate_t: dict[str, float] = {}
    for genome in kandidaten:
        if genome.name in roh:
            continue
        bericht = lauf(genome)
        trades = list(bericht.all_trades)
        kandidat = Kandidat.aus_trades(genome.name, trades)
        if len(trades) < 30 or kandidat is None:
            continue
        roh[genome.name] = trades
        # Genau die Kuerzung, die das Zulassungs-Gate rechnet - jetzt durch
        # dieselbe Funktion und nicht mehr durch einen nachgebauten Aufruf,
        # der genau das versprach und es seit Befund 135 nicht mehr hielt.
        st = stichprobe_wie_im_gate(
            trades,
            bloecke=[
                [float(t.net_pnl) for t in w.trades] for w in bericht.windows
            ],
        )
        gate_t[genome.name] = kandidat.sharpe_je_trade * st.effektiv**0.5

    # **Pflicht, kein Feinschliff.** Der Katalog enthaelt sieben Namen fuer
    # dieselbe Regel; ohne diesen Schritt zaehlt sie siebenfach und hebt jeden
    # t-Wert. Die erste Fassung dieses Befehls hat den Befund so erst erzeugt.
    entdoppelt = entdoppele(roh)
    laeufe = entdoppelt.laeufe

    if len(laeufe) < 3:
        console.print("[red]Zu wenige Regeln mit genug Trades.[/]")
        raise typer.Exit(2)

    console.print(
        f"\n[bold]Zeitachse[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Regeln     {len(laeufe)}\n"
        f"  Nullprobe  {durchlaeufe} Zuege je Regel\n"
        f"  Historie   {spanne} Tage\n"
    )
    if entdoppelt.doppel:
        console.print(f"[dim]{entdoppelt.hinweis()}[/]\n")

    ergebnis = messe(laeufe, gate_t, durchlaeufe=durchlaeufe)
    console.print(ergebnis.tabelle())

    farbe = "green" if ergebnis.nullprobe_traegt else "red"
    console.print(
        f"\n  [{farbe}]Die Nullprobe landet an der Trade-Achse: "
        f"{'ja' if ergebnis.nullprobe_traegt else 'NEIN'}[/]"
    )
    farbe = "green" if ergebnis.gate_kuerzt_genug else "yellow"
    console.print(f"\n[{farbe}]{ergebnis.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert - neu aggregiert wurden "
        "Trades, die ohnehin gerechnet waren. Kein Gate wurde geaendert.[/]"
    )


@app.command()
def verbundmodell(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    vola_ziel: float = typer.Option(19.3, "--vola-ziel"),
    tage: int = typer.Option(7, "--periode", help="Laenge einer Periode in Tagen."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Stimmt die Formel, mit der seit Befund 74 Partner bewertet werden?

    Der Auftrag aus Befund 76 - "ein Partner braucht rund 0,26 Sharpe je Trade
    bei 120 Trades" - steht auf ``partnerkarte.verbund_sharpe``. Acht
    selbstgebaute Regeln wurden daran gemessen und verworfen. Ob die Formel
    ueberhaupt trifft, war nie geprueft.

    Geprueft wird gegen die **Wochenreihe**: beide Beine auf ein gemeinsames
    Zeitraster gelegt, Ertraege je Woche addiert, davon der t-Wert. Das ist
    dieselbe Einheit wie die Guete, nur auf einer Achse, die Gleichzeitigkeit
    sehen kann.

    Die Kontrolle steht mit im Bericht: Bei einzelnen Beinen muessen Trade- und
    Wochenachse uebereinstimmen. Tun sie es nicht, misst der Paarvergleich die
    Aggregation und nichts sonst.

    **Kostet keinen Versuch.** Neu aggregiert werden Trades, die schon
    gerechnet sind; ausgewaehlt wird nichts. Wer eines der Paare als Kandidaten
    prueft, hat dagegen eine Auswahl ueber alle gezeigten Paare getroffen.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.entdopplung import entdoppele
    from research.seeds import VORGESEHEN, load_seeds, spitzenkandidat
    from research.verbundmodell import pruefe
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)

    def lauf(genome):
        angepasst = genome.model_copy(
            update={
                "sizing": SizingSpec(
                    kind="vola_ziel", fraction=3.0,
                    target_vol_pct=vola_ziel, vol_period=30,
                )
            }
        )
        return run_portfolio_walkforward(
            frames, lambda g=angepasst: compile_genome(g), configs
        )

    bestand = spitzenkandidat()
    kandidaten = [bestand]
    for gen in sorted(g for g, iv in VORGESEHEN.items() if iv == interval_obj.value):
        kandidaten.extend(load_seeds(gen))

    roh: dict[str, list] = {}
    for genome in kandidaten:
        trades = list(lauf(genome).all_trades)
        # Unter dreissig Trades traegt der t-Wert einer Wochenreihe nichts -
        # zu viele leere Perioden, und die Streuung wird von zwei Ausreissern
        # bestimmt.
        if len(trades) >= 30 and genome.name not in roh:
            roh[genome.name] = trades

    # Ohne diesen Schritt stammt die Haelfte der Paare aus derselben Regel -
    # die erste Fassung dieses Befehls mass so einen Kartenfehler von +0,238,
    # entdoppelt sind es -0,029.
    entdoppelt = entdoppele(roh)
    laeufe = entdoppelt.laeufe

    if len(laeufe) < 3:
        console.print("[red]Zu wenige Regeln mit genug Trades.[/]")
        raise typer.Exit(2)

    console.print(
        f"\n[bold]Verbundmodell[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Regeln     {len(laeufe)}\n"
        f"  Periode    {tage} Tage\n"
        f"  Historie   {spanne} Tage\n"
    )
    if entdoppelt.doppel:
        console.print(f"[dim]{entdoppelt.hinweis()}[/]\n")

    ergebnis = pruefe(laeufe, tage=tage)

    console.print("[bold]Kontrolle: dieselbe Regel auf beiden Achsen[/]")
    console.print(f"{'Regel':<36} {'t Trades':>9} {'t Wochen':>9} {'Diff':>8}")
    for name, (auf_trades, auf_wochen) in sorted(
        ergebnis.einzeln.items(), key=lambda x: -abs(x[1][0] - x[1][1])
    )[:6]:
        console.print(
            f"{name[:36]:<36} {auf_trades:>9.3f} {auf_wochen:>9.3f} "
            f"{auf_wochen - auf_trades:>+8.3f}"
        )
    farbe = "green" if ergebnis.achsen_stimmen_ueberein else "red"
    console.print(
        f"  [{farbe}]Die Achsen stimmen ueberein: "
        f"{'ja' if ergebnis.achsen_stimmen_ueberein else 'NEIN'}[/]\n"
    )

    console.print(f"[bold]Die besten Paare von {len(ergebnis.paare)}[/]")
    console.print(ergebnis.tabelle())
    unter = ergebnis.unterschaetzte
    if unter:
        console.print("\n[bold]Wo die Karte am staerksten unterschaetzt[/]")
        console.print(
            f"{'Bein A':<26} {'Bein B':<26} {'rho':>6} {'Karte':>7} {'echt':>7}"
        )
        for p in unter[:5]:
            console.print(
                f"{p.a[:26]:<26} {p.b[:26]:<26} {p.korrelation:>+6.2f} "
                f"{p.karte:>7.3f} {p.echt:>7.3f}"
            )

    farbe = "green" if ergebnis.schlaegt_die_auswahl else "yellow"
    console.print(f"\n[{farbe}]{ergebnis.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert - neu aggregiert wurden "
        "Trades, die ohnehin gerechnet waren.[/]"
    )


@app.command()
def phasen(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    vola_ziel: float = typer.Option(19.3, "--vola-ziel"),
    vorschlaege: str = typer.Option(
        "gen11_partner.json,gen12_partner.json", "--vorschlaege",
        help="Zusaetzliche Regeldateien in strategies/vorschlaege/.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Traegt eine Regel dort, wo der Bestand nicht traegt?

    Befund 84 mass: Je aehnlicher eine Regel dem Trendfolge-Signal des
    Bestands, desto besser ihre Qualitaet - und liess offen, ob das eine
    Eigenschaft der Regeln ist oder des stark gestiegenen Zeitraums. Dazu
    stand dort, ein Zeitraum mit anderer Marktrichtung existiere in diesen
    Daten nicht. **Das war falsch:** Vier der neun Jahre sind gefallen.

    Dieser Befehl trennt die Trades jeder Regel nach dem Jahr des Ausstiegs
    und rechnet beides getrennt. Und er prueft die Frage, die daran haengt: Ob
    die Fensterkorrelation, nach der die Partnersuche siebt, ueber den
    Phasenunterschied ueberhaupt etwas sagt.

    **Kostet keinen Versuch.** Zerlegt werden Trades, die ohnehin gerechnet
    sind - keine Gates, kein Deflated Sharpe, keine Auswahl. Wer eine hier
    auffaellige Regel danach als Verbund-Partner prueft, hat eine Auswahl ueber
    alle gezeigten Zeilen getroffen und muss sie zaehlen.
    """
    import json

    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.phasen import ABWAERTSJAHRE, Phasenbild, Phasenvergleich
    from research.seeds import VORGESEHEN, load_seeds, spitzenkandidat
    from research.suchbudget import Kandidat
    from research.verbund import fensterkorrelation
    from strategy.compiler import compile_genome
    from strategy.genome import Genome, SizingSpec

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)

    def lauf(genome):
        angepasst = genome.model_copy(
            update={
                "sizing": SizingSpec(
                    kind="vola_ziel", fraction=3.0,
                    target_vol_pct=vola_ziel, vol_period=30,
                )
            }
        )
        return run_portfolio_walkforward(
            frames, lambda g=angepasst: compile_genome(g), configs
        )

    bestand = spitzenkandidat()
    kandidaten = [bestand]
    passende = [g for g, iv in VORGESEHEN.items() if iv == interval_obj.value]
    for gen in sorted(passende):
        kandidaten.extend(load_seeds(gen))
    for name in (x.strip() for x in vorschlaege.split(",") if x.strip()):
        pfad = Path("strategies/vorschlaege") / name
        if not pfad.exists():
            continue
        kandidaten.extend(
            Genome.model_validate(roh) for roh in json.loads(pfad.read_text())
        )

    console.print(
        f"\n[bold]Marktphasen[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Bestand      '{bestand.name}'\n"
        f"  Kandidaten   {len(kandidaten)}\n"
        f"  Abwaertsjahre {', '.join(str(j) for j in sorted(ABWAERTSJAHRE))}\n"
        f"  Historie     {spanne} Tage\n"
    )

    spitze = lauf(bestand)
    bilder: list[Phasenbild] = []
    gesehen: set[tuple[int, int]] = set()
    for genome in kandidaten:
        bericht = lauf(genome)
        trades = list(bericht.all_trades)
        auf = [t for t in trades if t.exit_time.year not in ABWAERTSJAHRE]
        ab = [t for t in trades if t.exit_time.year in ABWAERTSJAHRE]
        # Unter zehn Trades je Phase ist der Sharpe je Trade keine Groesse
        # mehr, sondern eine Anekdote - solche Zeilen taeuschen eine Trennung
        # vor, die nur aus zwei oder drei Trades besteht.
        if len(auf) < 10 or len(ab) < 10:
            continue
        eins = Kandidat.aus_trades(genome.name, auf)
        zwei = Kandidat.aus_trades(genome.name, ab)
        if eins is None or zwei is None:
            continue
        # Nach (Trades auf, Trades ab) entdoppeln - dieselbe Regel steht in
        # mehreren Generationen, und doppelte Punkte faelschen die Korrelation.
        schluessel = (len(auf), len(ab))
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        bilder.append(
            Phasenbild(
                name=genome.name,
                sharpe_auf=eins.sharpe_je_trade,
                sharpe_ab=zwei.sharpe_je_trade,
                trades_auf=len(auf),
                trades_ab=len(ab),
                rho=fensterkorrelation(spitze, bericht) if bericht.windows else None,
            )
        )

    if not bilder:
        console.print("[red]Keine Regel hat in beiden Phasen genug Trades.[/]")
        raise typer.Exit(2)

    vergleich = Phasenvergleich(bilder=bilder)
    console.print(vergleich.tabelle())
    gegen = vergleich.gegenlaeufige
    farbe = "green" if any(b.unterschied_traegt for b in gegen) else "yellow"
    console.print(f"\n[{farbe}]{vergleich.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert - hier wurde keine neue "
        "Regel gebaut, sondern eine vorhandene Trade-Liste nach dem Jahr des "
        "Ausstiegs geteilt.[/]"
    )


@app.command()
def partner(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Was ein Verbund-Partner koennen muesste - vor dem naechsten Versuch.

    Befund 73 hat den Verbund geoeffnet: Zwei verschiedene Regeln zusammen
    hoben den Deflated Sharpe von 0,796 auf 0,860, den groessten Sprung, den
    je etwas gebracht hat. Es fehlen 0,26 an Guete.

    Der Gedanke, der zur Auswahl der beiden Partner fuehrte, war: *"Es gibt
    Kandidaten mit hoeherer Qualitaet je Trade, die nur zu selten handeln."*
    Diese Karte zeigt, dass er nach dem falschen Merkmal ausgewaehlt hat.

    Bei 53 Trades haette der Partner 0,42 je Trade gebraucht - er hatte 0,32,
    eine der besten Zahlen des Projekts. Bei 154 Trades haetten 0,23 genuegt,
    also **weniger als der Bestand selbst hat**.

    Gesucht ist damit keine bessere Regel, sondern eine, die **genug handelt
    und anders ist**.

    Kostet keinen Versuch: Gerechnet wird ueber Partner, nicht mit ihnen.
    """

    from research.admission import load_trials
    from research.partnerkarte import Anwaerter, Partnerkarte
    from research.seeds import spitzenkandidat
    from research.verbund import noetige_guete

    _configure_logging(verbose)
    settings = get_settings()
    zustand = Path(settings.paths.state)
    versuche = load_trials(zustand / "trials.json")

    # Der Bestand kommt aus ``research.referenz`` und nicht mehr von Hand.
    #
    # Hier standen ``154, 0.2591`` mit dem Vermerk "seit Befund 73
    # unveraendert". Sie haben sich zweimal geaendert: Befund 108 hat den
    # Betriebspunkt auf Spot gelegt (0,2765 statt 0,2591), Befund 135 die
    # Stichprobe von 154 auf 112 gekuerzt. Der Sweep aus Befund 136 hat die
    # Stelle nicht gefunden, weil er nach den beiden ueberholten DSR-Werten
    # sucht und hier keiner davon steht (Befund 139).
    from research.referenz import SPOTPUNKT

    n1, sr1 = SPOTPUNKT.effektiv, SPOTPUNKT.guete
    ziel = noetige_guete(n1, versuche)
    karte = Partnerkarte(n1=n1, sr1=sr1, ziel=ziel)

    console.print(
        f"\n[bold]Was ein Partner koennen muesste[/]\n"
        f"  Bestand    '{spitzenkandidat().name}': {SPOTPUNKT.trades} Trades "
        f"zu je {sr1:.4f}, davon {n1} unabhaengig "
        f"(Befund {SPOTPUNKT.befund})\n"
        f"  Versuche   {versuche}, noetige Guete {ziel:.3f}\n"
    )
    console.print("Noetiges SR/Trade des Partners:\n")
    console.print(karte.tabelle())
    console.print(f"\n{karte.urteil()}\n")

    # Die Trade-Zahlen aller Bestenlisten-Eintraege liegen laengst vor. Sie
    # abzulesen testet nichts Neues und kostet deshalb keinen Versuch.
    daten, liste_da = _bestenliste(zustand)
    anwaerter = [
        Anwaerter(
            name=str(e.get("name", "?")),
            trades=int(e.get("trades", 0)),
            sharpe_je_trade=float(e["sharpe_je_trade"]),
        )
        for e in daten.get("eintraege", [])
        if e.get("sharpe_je_trade") and int(e.get("trades", 0)) > 0
    ]
    if anwaerter:
        from research.partnerkarte import Katalogkopplung

        console.print(
            "Die bekannten Kandidaten mit belegtem Sharpe je Trade, gegen "
            "ihre eigene\nAnforderung bei u = 0,72:\n"
        )
        console.print(karte.einordnung(anwaerter))
        kopplung = Katalogkopplung(anwaerter=anwaerter)
        if kopplung.genug:
            console.print(f"\n{kopplung.urteil()}")
        console.print(
            "\n[dim]'fehlt' positiv heisst: reicht nicht. Alle bekannten "
            "Anwaerter handeln zu selten -\ndie Trade-Zahl ist das bindende "
            "Merkmal, nicht die Qualitaet.[/]\n"
        )
    else:
        console.print(_bestenliste_hinweis(liste_da))


@app.command()
def verbund(
    partner: str = typer.Option(
        ..., "--partner", "-p",
        help="Name eines Genoms aus einer Generation, das dazukommen soll.",
    ),
    generation: int = typer.Option(9, "--generation", "-g"),
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    vola_ziel: float = typer.Option(19.3, "--vola-ziel"),
    zaehlen: bool = typer.Option(
        True, "--zaehlen/--nicht-zaehlen",
        help="Den Verbund als Versuch buchen. Standard ja.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Zwei verschiedene Regeln zusammen - hebt das die Guete?

    Nach Befund 70 fuehrt genau ein Weg zum haertesten Gate: mehr Guete, also
    ``SR/Trade * sqrt(n_eff)``. Alle Regler daran sind ausgemessen, und
    Befund 54 hat die Kopplung gezeigt - wer denselben Kandidaten oefter
    handeln laesst, verliert an Qualitaet, was er an Menge gewinnt.

    Es gibt aber Kandidaten mit **hoeherer** Qualitaet je Trade, die nur zu
    selten handeln. Sie zusammen zu handeln ist nicht dieselbe Kopplung: Die
    Trades kaemen aus verschiedenen Regeln.

    **Und es ist dieselbe Gefahr wie beim Perioden-Ensemble** (Befund 27):
    Dort wurden aus 154 Trades 481 und aus DSR 0,802 einer von 0,999 - drei
    Beine, ein Signal. Deshalb wird die effektive Stichprobe hier genauso
    gerechnet wie im Gate, mit Fensterbloecken und gleichzeitig offenen
    Positionen.

    **Dieser Befehl kostet einen Versuch**, weil ein Kandidat gegen den
    Deflated Sharpe gehalten wird. Mit ``--nicht-zaehlen`` laesst sich das
    abschalten - dann ist das Ergebnis aber auch keine Grundlage fuer eine
    Auswahl.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.seeds import load_seeds, spitzenkandidat
    from research.verbund import baue, noetige_guete
    from research.versuche import Versuch
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec

    _configure_logging(verbose)
    settings = get_settings()
    trials_path = Path(settings.paths.state) / "trials.json"
    versuche = load_trials(trials_path)

    interval_obj = Interval(intervall)
    _pruefe_generation(generation, interval_obj)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)

    gesucht = partner.strip().lower()
    treffer = [g for g in load_seeds(generation) if gesucht in g.name.lower()]
    if not treffer:
        namen = ", ".join(g.name for g in load_seeds(generation))
        console.print(f"[red]'{partner}' nicht in Generation {generation}.[/] {namen}")
        raise typer.Exit(2)

    def lauf(genome):
        # Dieselbe Groessenlogik fuer alle - sonst vergleicht man Hebelstufen.
        angepasst = genome.model_copy(
            update={
                "sizing": SizingSpec(
                    kind="vola_ziel", fraction=3.0,
                    target_vol_pct=vola_ziel, vol_period=30,
                )
            }
        )
        return angepasst, run_portfolio_walkforward(
            frames, lambda g=angepasst: compile_genome(g), configs
        )

    spitze_genome, spitze = lauf(spitzenkandidat())
    partner_genome, partner_bericht = lauf(treffer[0])

    # Der Verbund ist der neue Kandidat und damit der Versuch. Die beiden
    # Beine sind laengst gemessen; sie noch einmal zu zaehlen waere doppelt.
    neu = versuche + (1 if zaehlen else 0)
    lage = baue(
        [(spitze_genome.name, spitze), (partner_genome.name, partner_bericht)],
        versuche=neu,
    )

    console.print(
        f"\n[bold]Verbund[/] auf {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Historie   {spanne} Tage\n"
        f"  Versuche   {versuche}"
        + (f" -> {neu} (dieser Verbund)" if zaehlen else " (nicht gezaehlt)")
        + "\n"
    )
    if lage.korrelation is not None:
        console.print(
            f"  Fensterkorrelation der beiden Beine: {lage.korrelation:+.3f}"
            + (
                "  [yellow]- beim Perioden-Ensemble waren es 0,884[/]"
                if lage.korrelation > 0.8
                else ""
            )
            + "\n"
        )
    console.print(lage.tabelle())

    ziel = noetige_guete(lage.stichprobe.effektiv, neu)
    console.print(f"\n{lage.urteil(noetige_guete=ziel)}\n")
    dsr = lage.dsr
    if dsr is not None:
        from research.suchbudget import ZIEL

        console.print(
            f"[dim]Deflated Sharpe des Verbunds: {dsr:.4f} gegen {ZIEL:.2f}. "
            f"Die uebrigen zehn Gates sind damit nicht geprueft - zwei Regeln "
            f"parallel\nteilen das Kapital, und auf Rendite und Rueckgang "
            f"wirkt das sehr wohl.[/]\n"
        )

    if zaehlen:
        kandidat = lage.kandidat
        _verzeichne(
            trials_path,
            [
                Versuch.jetzt(
                    lage.name[:80],
                    trades=lage.stichprobe.roh,
                    sharpe_je_trade=(
                        kandidat.sharpe_je_trade if kandidat is not None else None
                    ),
                    herkunft="verbund",
                )
            ],
            neu,
        )
        console.print(f"[dim]Versuchszaehler jetzt {neu}.[/]\n")


@app.command()
def quelle(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Taugt eine Ideenquelle - oder misst man nur sein eigenes Rauschen?

    Befund 71 hat den einzigen verbliebenen Hebel benannt: die **Guete** der
    Ideen, nicht ihre Zahl. Die Suche gewinnt genau dann, wenn die Streuung
    echter Regelideen ueber ``1/sqrt(n-1)`` liegt.

    Damit wird eine neue Frage stellbar: Streuen die Vorschlaege einer
    bestimmten Herkunft breiter, als Rauschen allein hergibt? Nur ist der
    Sharpe je Trade selbst geschaetzt, und zwar grob - bei 68 Trades mit
    einem Rauschen von 0,122. Wer die Streuung ueber Kandidaten misst, misst
    beides auf einmal:

        beobachtet^2 = Ideenstreuung^2 + Messrauschen^2

    Dieser Befehl zieht das Rauschen ab und sagt, was uebrig bleibt - und wie
    viele Belege es braeuchte, wenn nichts uebrig bleibt.

    Kostet keinen Versuch: Gelesen wird, was auf der Platte liegt.
    """

    from research.admission import load_trials
    from research.aussagekraft import Beleg, Ideenquelle

    _configure_logging(verbose)
    settings = get_settings()
    zustand = Path(settings.paths.state)
    versuche = load_trials(zustand / "trials.json")

    daten, liste_da = _bestenliste(zustand)
    if not liste_da:
        console.print("[red]Keine Bestenliste gefunden.[/]")
        console.print(_bestenliste_hinweis(False))
        raise typer.Exit(2)

    nach_herkunft: dict[str, list[Beleg]] = {}
    for e in daten.get("eintraege", []):
        if not e.get("sharpe_je_trade"):
            continue
        nach_herkunft.setdefault(str(e.get("herkunft") or "?"), []).append(
            Beleg(
                kennung=str(e.get("name", "?")),
                sharpe_je_trade=float(e["sharpe_je_trade"]),
                trades=int(e.get("trades", 0)),
            )
        )
    # Auch das Versuchsverzeichnis - dort landen seit Befund 69 alle neuen.
    from research.versuche import ZaehlerUnlesbarError
    from research.versuche import laden as verzeichnis_laden

    try:
        for v in verzeichnis_laden(zustand / "trials.json").eintraege:
            if v.sharpe_je_trade is not None:
                nach_herkunft.setdefault(v.herkunft or "Verzeichnis", []).append(
                    Beleg(
                        kennung=v.kennung,
                        sharpe_je_trade=v.sharpe_je_trade,
                        trades=v.trades,
                    )
                )
    except ZaehlerUnlesbarError:
        pass

    belegt = sum(len(b) for b in nach_herkunft.values())
    console.print(
        f"\n[bold]Ideenquellen[/]\n"
        f"  Versuche   {versuche} insgesamt, {belegt} mit belegtem Sharpe je "
        f"Trade\n"
    )
    if not nach_herkunft:
        console.print(
            "[yellow]Kein einziger Versuch traegt seinen Sharpe je Trade.[/] "
            "Seit Befund 69 schreibt jeder neue Lauf ihn mit."
        )
        raise typer.Exit(0)

    for name, belege in sorted(nach_herkunft.items(), key=lambda kv: -len(kv[1])):
        quelle_ = Ideenquelle(name=name, belege=belege)
        console.print(f"[bold]{name}[/] - {len(belege)} Belege\n")
        console.print(quelle_.tabelle())
        console.print(f"\n{quelle_.urteil()}\n")

    # Zusaetzlich alles zusammen. Die Herkunft trennt nach **Datei**, nicht
    # nach Quelle - 'vorschlaege.json' und 'sieger.json' kommen beide vom
    # Analysten. Die Trennung wird trotzdem angezeigt und nicht stillschweigend
    # aufgehoben: Wer sie zusammenlegt, trifft eine Annahme darueber, dass es
    # dieselbe Quelle ist, und die gehoert sichtbar dazu.
    alle = [b for belege in nach_herkunft.values() for b in belege]
    if len(alle) > max(len(b) for b in nach_herkunft.values()):
        zusammen = Ideenquelle(name="alle Belege zusammen", belege=alle)
        console.print(
            f"[bold]Alle {len(alle)} Belege zusammen[/] - die Herkunft trennt "
            f"nach Datei, nicht nach Quelle\n"
        )
        console.print(f"{zusammen.urteil()}\n")

        # **Die Probe, die vor der naheliegenden Falle schuetzt** (Befund 119).
        #
        # Aus Mittel und Ideenstreuung liegt es nahe, die Annahme in
        # ``cli rennen`` zu ersetzen - dort steht "Mittel +0,000" ausdruecklich
        # als Annahme. Genau das haette den Schnittpunkt von 786.085 auf 9.454
        # Versuche verschoben, Faktor 83 zu guenstig.
        #
        # Beide Groessen zusammen sagen einen Bestwert voraus. Trifft er den
        # tatsaechlichen nicht, sind die Belege keine Stichprobe der Suche,
        # sondern eine Auswahl daraus - und dann taugen sie nicht.
        from statistics import fmean

        from research.aussagekraft import Vertraeglichkeit

        ideen = zusammen.ideenstreuung
        # **Der Bestwert kommt aus den beurteilbaren Belegen.** Der hoechste
        # Wert ueberhaupt ist 0,3405 aus 18 Trades - genau der Kandidat, den
        # dieselbe Ausgabe zwei Zeilen darueber als unbeurteilbar ausweist.
        # Ihn als "besten Fund" zu nehmen hiesse, die Probe an einem
        # Messausreisser aufzuhaengen.
        beurteilbare = [b for b in alle if b.beurteilbar]
        bester = max((b.sharpe_je_trade for b in beurteilbare), default=0.0)
        if ideen is not None and beurteilbare:
            probe = Vertraeglichkeit(
                mittel=fmean(b.sharpe_je_trade for b in alle),
                ideenstreuung=ideen,
                versuche=versuche,
                bester=bester,
                belege=len(alle),
                versuche_gesamt=versuche,
            )
            farbe = "green" if probe.traegt() else "red"
            console.print(f"[{farbe}]{probe.urteil()}[/]\n")
            if not probe.traegt():
                console.print(
                    "[dim]Deshalb bleibt die Annahme in 'cli rennen' stehen. "
                    "Sie durch diese Messung zu ersetzen wuerde eine Huerde "
                    "senken, und zwar auf einer Stichprobe, die nachweislich "
                    "nicht die Suche abbildet.[/]\n"
                )

    console.print(
        "[dim]Die Nullstreuung ist dieselbe Groesse, die im Deflated Sharpe "
        "die Huerde treibt.\nEine Quelle, die sie nicht schlaegt, kann das "
        "Gate durch Suchen nicht einholen.[/]\n"
    )


@app.command()
def rennen(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    mittel: float = typer.Option(
        0.0, "--mittel",
        help="Angenommener Sharpe je Trade einer typischen neuen Regelidee.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Suchen hebt die Huerde. Holt der beste Fund sie je ein?

    Nach Befund 70 ist von vier Wegen zum haertesten Gate einer uebrig - die
    Qualitaet je Trade, +13 % -, und alle Regler daran sind ausgemessen. Es
    bliebe: weitersuchen. Nur hebt jeder Versuch die Latte mit.

    Beide Groessen wachsen ueber dieselbe Extremwertkonstante:

        Huerde       ~ A + 1/sqrt(n-1) * c(N)     was Zufall hergibt
        bester Fund  ~ Mittel + Streuung * c(N)   was Suchen hergibt

    Damit ist es keine Frage des Fleisses, sondern ein Vergleich zweier
    Vorfaktoren: **Die Suche gewinnt genau dann, wenn die Streuung echter
    Regelideen ueber 1/sqrt(n-1) liegt.**

    Die Streuung wird aus dem eigenen Verlauf kalibriert - was muss sie
    gewesen sein, damit so viele Versuche genau diesen Bestwert hervorbringen?
    Das Mittel ist eine Annahme und steht deshalb als Schalter da.

    Kostet keinen Versuch: Gerechnet wird ueber Versuche, nicht mit ihnen.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import stichprobe_wie_im_gate
    from research.seeds import spitzenkandidat
    from research.stand import BUDGET
    from research.suchbudget import Kandidat
    from research.wettrennen import Rennen, spanne
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    versuche = load_trials(Path(settings.paths.state) / "trials.json")

    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne_tage = _korb_daten(symbole, interval_obj, settings)
    genome = spitzenkandidat()
    bericht = run_portfolio_walkforward(
        frames, lambda g=genome: compile_genome(g), configs
    )
    trades = list(bericht.all_trades)
    kandidat = Kandidat.aus_trades(genome.name, trades)
    if kandidat is None or kandidat.sharpe_je_trade <= 0:
        console.print("[red]Keine auswertbaren Trades.[/]")
        raise typer.Exit(2)

    # Hier stand die Einteilung des Gates **von vor Befund 135** - ohne
    # Quartalsbloecke, also 152 statt 112 Beobachtungen. Die Rechnung lief
    # gegen eine Huerde, die das Gate so nicht mehr stellt. Jetzt kommt die
    # Stichprobe aus derselben Funktion wie im Gate (Befund 139).
    stichprobe = stichprobe_wie_im_gate(
        trades,
        beine=getattr(bericht, "beine", None),
        bloecke=[[float(t.net_pnl) for t in f.trades] for f in bericht.windows],
    )

    lauf = Rennen(
        bester=kandidat.sharpe_je_trade,
        versuche=versuche,
        trades=stichprobe.effektiv,
        mittel=mittel,
    )
    abbruch = BUDGET.beginn + BUDGET.umfang
    console.print(
        f"\n[bold]Das Wettrennen mit der eigenen Huerde[/] '{genome.name}' auf "
        f"{' + '.join(symbole)} {interval_obj.label}\n"
        f"  Historie   {spanne_tage} Tage, {len(trades)} Trades "
        f"({stichprobe.effektiv} davon unabhaengig)\n"
        f"  Bestwert   {kandidat.sharpe_je_trade:.4f} je Trade nach "
        f"{versuche} Versuchen\n"
        f"  Annahme    Mittel einer neuen Regelidee {mittel:+.3f}\n"
    )
    console.print(lauf.tabelle((0, 10, 64, 334, 834, 9834)))
    console.print(f"\n{lauf.urteil(budget=abbruch)}\n")

    # **Derselbe Lauf am zweiten Betriebspunkt** (Befund 126).
    #
    # Alles oben rechnet Perpetual. Seit Befund 108 ist Spot der bessere
    # gemessene Punkt, und der Schnittpunkt reagiert exponentiell: 786.085
    # gegen 8.255 Versuche.
    #
    # **Der Spot-Vorteil geht als Schub ein, nicht als Bestwert** - das ist
    # der Kern von Befund 110. Wer 0,2765 als ``bester`` einsetzt, behauptet,
    # 198 Versuche haetten diesen Wert hervorgebracht; er kommt aber aus dem
    # Wegfall einer Kostenannahme. Naiv gerechnet kaeme 1.923 heraus statt
    # 8.255 - viermal zu guenstig.
    spot_guete = _spotguete(frames, symbole, genome, settings)
    if spot_guete and spot_guete > kandidat.sharpe_je_trade:
        schub = spot_guete - kandidat.sharpe_je_trade
        spotlauf = Rennen(
            bester=kandidat.sharpe_je_trade,
            versuche=versuche,
            trades=stichprobe.effektiv,
            mittel=mittel,
            schub=schub,
        )
        console.print("[bold]Derselbe Lauf unter Spot-Bedingungen[/]")
        console.print(
            f"  Guete {spot_guete:.4f} statt {kandidat.sharpe_je_trade:.4f} "
            f"- ein Niveauschub von {schub:+.4f} (Befund 108)\n"
            f"  Schnittpunkt: [bold]{spotlauf.wo_holt_sie_auf()}[/] "
            f"statt {lauf.wo_holt_sie_auf()}\n"
        )
        console.print(
            "[dim]  Der Schub kommt oben drauf und geht nicht in die Streuung "
            "ein: Er hebt jeden\n  Fund gleichermassen, macht die Suche aber "
            "nicht treffsicherer (Befund 110).\n  Beide Zahlen liegen weit "
            f"jenseits des Budgetendes bei {abbruch} Versuchen.[/]\n"
        )

    console.print("Wie stark das an der Annahme haengt:\n")
    console.print(
        spanne(
            bester=kandidat.sharpe_je_trade,
            versuche=versuche,
            trades=stichprobe.effektiv,
            mittelwerte=(-0.05, -0.02, 0.0, 0.02, 0.05),
        )
    )
    console.print(
        "\n[dim]Ein niedrigeres Mittel ist die guenstigere Annahme: Es "
        "verlangt eine groessere\nStreuung, um denselben Bestwert zu "
        "erklaeren, und laesst die Suche schneller\naufholen. Und: Das Modell "
        "setzt unabhaengige Ziehungen voraus - Reglerscans sind\ndas nicht, "
        "also ist der echte Fortschritt langsamer als hier gerechnet.[/]\n"
    )


@app.command()
def form(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Der letzte offene Weg zum Gate - und warum es ihn nicht gibt.

    ``cli stand`` weist seit Wochen aus, die Schiefe muesste von 3,47 auf 4,53
    steigen, *alles andere unveraendert*. Das geht bei diesen beiden Groessen
    nicht: Fuer jede Verteilung gilt ``Woelbung >= Schiefe^2 + 1``, und bei
    Schiefe 4,53 waeren das ueber 20 statt der festgehaltenen 15,95. **Der
    ausgewiesene Zielpunkt ist keine Verteilung.**

    Dieser Befehl rechnet denselben Weg dreimal: mit festgehaltener Woelbung
    (die bisherige Zerlegung, nur zum Vergleich), entlang der harten Schranke
    (das Optimum, praktisch unerreichbar) und entlang der Linie, auf der die
    gemessenen Kandidaten dieses Projekts tatsaechlich liegen.

    Kostet keinen Versuch: Gerechnet wird mit Zahlen, die schon dastehen.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.formgrenze import Formlinie, mindestwoelbung, tabelle, wege
    from research.gates import stichprobe_wie_im_gate
    from research.seeds import spitzenkandidat
    from research.suchbudget import Kandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    zustand = Path(settings.paths.state)
    versuche = load_trials(zustand / "trials.json")

    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)
    genome = spitzenkandidat()
    bericht = run_portfolio_walkforward(
        frames, lambda g=genome: compile_genome(g), configs
    )
    trades = list(bericht.all_trades)
    kandidat = Kandidat.aus_trades(genome.name, trades)
    if kandidat is None or kandidat.schiefe is None or kandidat.woelbung is None:
        console.print("[red]Keine auswertbaren Trades.[/]")
        raise typer.Exit(2)

    stichprobe = stichprobe_wie_im_gate(
        trades,
        beine=getattr(bericht, "beine", None),
        bloecke=[[float(t.net_pnl) for t in f.trades] for f in bericht.windows],
    )

    linie = Formlinie(punkte=_formpunkte(zustand))
    console.print(
        f"\n[bold]Form der Verteilung[/] '{genome.name}' auf "
        f"{' + '.join(symbole)} {interval_obj.label}\n"
        f"  Historie   {spanne} Tage, {len(trades)} Trades "
        f"({stichprobe.effektiv} davon unabhaengig)\n"
        f"  Form       Schiefe {kandidat.schiefe:.3f}, Woelbung "
        f"{kandidat.woelbung:.3f} - Schranke bei "
        f"{mindestwoelbung(kandidat.schiefe):.3f}\n"
        f"  Versuche   {versuche}\n"
    )

    if not linie.genug:
        console.print(
            "[yellow]Zu wenige Kandidaten mit beiden Formzahlen fuer eine "
            "gemessene Linie.[/] Es bleiben die beiden gerechneten Wege.\n"
        )
    else:
        guete = linie.guete or 0.0
        steigung, abschnitt = linie.steigung or 0.0, linie.abschnitt or 0.0
        console.print(
            f"Gemessene Kopplung ueber {len(linie.punkte)} Kandidaten:\n"
            f"  Woelbung = {steigung:.3f} * Schiefe^2 + {abschnitt:.3f}"
            f"   (r = {guete:.4f})\n"
            f"  Harte Schranke: Woelbung = 1.000 * Schiefe^2 + 1.000\n"
        )
        if not linie.ueber_der_schranke():
            console.print(
                "[red]Ein gemessener Punkt liegt unter der Schranke - das ist "
                "rechnerisch unmoeglich und deutet auf einen Fehler in den "
                "Formzahlen hin.[/]\n"
            )

    drei = wege(
        sharpe=kandidat.sharpe_je_trade,
        stichprobe=stichprobe.effektiv,
        versuche=versuche,
        woelbung_heute=kandidat.woelbung,
        linie=linie if linie.genug else None,
    )
    console.print(tabelle(drei, kandidat.schiefe))
    console.print()
    for weg in drei[1:]:
        console.print(f"{weg.urteil(kandidat.schiefe)}\n")
    console.print(
        "[dim]Die erste Zeile ist die bisherige Zerlegung und steht nur zum "
        "Vergleich da: Ihr\nZielpunkt verlangt eine Woelbung, die keine "
        "Verteilung mit dieser Schiefe hat.[/]\n"
    )

    # **Derselbe Weg am zweiten Betriebspunkt** (Befund 125).
    #
    # Oben laeuft alles am Perpetual-Punkt - Guete 0,2597. Seit Befund 108 ist
    # Spot der bessere gemessene Punkt (0,2765), und seit Befund 112 zeigt
    # ``cli stand`` beide. Hier stand nur einer, und das aendert die Reserve
    # erheblich: Auf der gemessenen Linie kommt der Perpetual-Punkt auf 0,8601,
    # der Spot-Punkt auf 0,9357. Dieselbe Aussage - "nie erreicht" - aber mit
    # 0,0143 statt 0,0899 Abstand zur Schwelle.
    spot = _spotguete(frames, symbole, genome, settings)
    if linie.genug and spot:
        from research.formgrenze import Formweg

        # Dieselbe Maschinerie, nur mit der Spot-Guete - keine zweite Rechnung
        # daneben. Ein eigener Weg dafuer waere eine Kopie mit demselben Inhalt.
        spotweg = Formweg(
            sharpe=spot, stichprobe=stichprobe.effektiv, versuche=versuche,
            kopplung=lambda s, li=linie: li.woelbung_bei(s) or mindestwoelbung(s),
            name="entlang der gemessenen Linie (Spot)",
        )
        bei, hoehe = spotweg.hoechstwert
        _, perp_hoehe = drei[-1].hoechstwert
        schwelle = 0.95

        console.print("[bold]Derselbe Weg unter Spot-Bedingungen[/]")
        console.print(
            f"  Guete {spot:.4f} statt {kandidat.sharpe_je_trade:.4f} "
            f"(kein Funding, kein Hebel - Befund 108)\n"
            f"  Hoechster DSR auf der gemessenen Linie: [bold]{hoehe:.4f}[/] "
            f"bei Schiefe {bei:.2f}\n"
        )
        if hoehe >= schwelle:
            console.print(
                "[red]  Am Spot-Punkt waere die Schwelle auf diesem Weg "
                "erreichbar - die Aussage oben gilt dort nicht.[/]\n"
            )
        else:
            console.print(
                f"[yellow]  Auch dort nicht erreichbar - aber der Abstand "
                f"betraegt {schwelle - hoehe:.4f} statt "
                f"{schwelle - perp_hoehe:.4f}. Die Aussage haelt; ihre "
                f"Reserve ist am tatsaechlich besseren Betriebspunkt "
                f"erheblich kleiner.[/]\n"
            )


def _bestenliste(zustand: Path) -> tuple[dict, bool]:
    """Die Bestenliste lesen - **und sagen, ob es sie ueberhaupt gibt.**

    Drei Stellen lasen sie bis Befund 166 mit je eigenem ``try/except``, und
    keine konnte "Datei fehlt" von "Datei ohne brauchbare Eintraege"
    unterscheiden. ``cli partner`` meldete deshalb auf einem frischen
    Behaelter:

        Kein Bestenlisten-Eintrag traegt seinen Sharpe je Trade. Seit
        Befund 69 schreibt jeder neue Lauf ihn mit.

    Das ist die Diagnose eines fehlenden **Feldes** - und es fehlte die
    ganze Datei. Wer dem Hinweis folgt, sucht nach Eintraegen, die es nicht
    gibt.

    ``state/`` ist maschinenspezifisch und bis auf ``trials.json`` nicht im
    Repository (Befund 73). Nach einem Behaelterwechsel ist die Bestenliste
    also **regulaer** weg, nicht kaputt - genau wie die Kerzen in Befund 151.
    """
    import json

    try:
        return json.loads((zustand / "leaderboard.json").read_text()), True
    except (OSError, json.JSONDecodeError):
        return {}, False


def _bestenliste_hinweis(vorhanden: bool) -> str:
    """Warum keine Anwaerter dastehen - je nachdem, woran es liegt."""
    if not vorhanden:
        return (
            "[yellow]Keine Bestenliste vorhanden.[/] 'state/' ist "
            "maschinenspezifisch und liegt bis auf den Versuchszaehler nicht "
            "im Repository (Befund 73) - nach einem Behaelterwechsel ist sie "
            "weg, so wie die Kerzen in Befund 151. 'cli wettbewerb' legt sie "
            "neu an.\n"
        )
    return (
        "[yellow]Kein Bestenlisten-Eintrag traegt seinen Sharpe je Trade.[/] "
        "Seit Befund 69 schreibt jeder neue Lauf ihn mit.\n"
    )


def _formpunkte(zustand: Path) -> list:
    """Alle Kandidaten, die Schiefe **und** Woelbung mittragen.

    Beide oder keine: Ein Punkt mit nur einer der beiden Zahlen sagt ueber
    ihren Zusammenhang nichts.
    """
    import json

    from research.formgrenze import Formpunkt

    gefunden = []
    for datei in sorted((Path.cwd() / "reports").rglob("*.json")):
        try:
            daten = json.loads(datei.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        regler = daten.get("regler") or daten.get("analyse", {}).get("regler") or "?"
        punkte = daten.get("punkte") or daten.get("analyse", {}).get("punkte") or []
        for punkt in punkte:
            k = punkt.get("kennzahlen") or {}
            if k.get("schiefe") and k.get("woelbung"):
                gefunden.append(
                    Formpunkt(
                        quelle="Berichte",
                        kennung=f"{regler} {float(punkt.get('stellung', 0)):g}",
                        schiefe=float(k["schiefe"]),
                        woelbung=float(k["woelbung"]),
                    )
                )
    eintraege, _ = _bestenliste(zustand)
    for e in eintraege.get("eintraege", []):
        if e.get("schiefe") and e.get("woelbung"):
            gefunden.append(
                Formpunkt(
                    quelle="Bestenliste",
                    kennung=str(e.get("name", "?")),
                    schiefe=float(e["schiefe"]),
                    woelbung=float(e["woelbung"]),
                )
            )
    return gefunden


@app.command()
def streuung(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Die sechste Eingabe des Deflated Sharpe - die einzige, die geraten wird.

    Die Formel braucht die **Streuung der Sharpe-Schaetzer ueber die
    Versuche**. Fuenf ihrer Eingaben werden gemessen; fuer diese springt seit
    dem ersten Tag eine Ersatzannahme ein: die asymptotische Varianz
    ``1/(n-1)``.

    Und an ihr haengt mehr, als man denkt. Dieser Befehl rechnet aus, bei
    welchem Wert das Urteil des Gates umschlaegt, und stellt daneben, was aus
    den eigenen Berichten herauskaeme.

    **Der gemessene Wert wird nicht eingesetzt** - und zwar nicht aus
    Vorsicht, sondern weil er zu niedrig ist: Berichte entstehen ueber
    Reglerscans um den Bestand herum, und die Verlierer haben nie einen
    bekommen. Eine Huerde mit einer Zahl zu senken, von der man weiss, dass
    sie zu klein ist, waere das Gegenteil von Messen.

    Kostet keinen Versuch: Der Zaehler wird nicht angefasst.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import (
        GateThresholds,
        gate_deflated_sharpe,
        stichprobe_wie_im_gate,
    )
    from research.seeds import spitzenkandidat
    from research.streuung import Empfindlichkeit, Streuung, sammle
    from research.suchbudget import Kandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    zustand = Path(settings.paths.state)
    versuche = load_trials(zustand / "trials.json")

    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)
    genome = spitzenkandidat()
    bericht = run_portfolio_walkforward(
        frames, lambda g=genome: compile_genome(g), configs
    )
    trades = list(bericht.all_trades)
    kandidat = Kandidat.aus_trades(genome.name, trades)
    if kandidat is None or kandidat.sharpe_je_trade <= 0:
        console.print("[red]Keine auswertbaren Trades.[/]")
        raise typer.Exit(2)

    # Genau die Argumente, mit denen ``run_admission`` das Gate aufruft -
    # sonst haengt die Empfindlichkeit an einer anderen Stichprobe als das
    # Urteil, das sie erklaeren soll. Genau das war seit Befund 135 der Fall:
    # Der Satz stimmte, der Aufruf darunter nicht mehr (Befund 139).
    bloecke = [[float(t.net_pnl) for t in f.trades] for f in bericht.windows]
    stichprobe = stichprobe_wie_im_gate(
        trades, beine=getattr(bericht, "beine", None), bloecke=bloecke
    )
    gate = gate_deflated_sharpe(
        trades, versuche, GateThresholds(), getattr(bericht, "beine", None), bloecke
    )

    empfindlichkeit = Empfindlichkeit(
        sharpe=kandidat.sharpe_je_trade,
        stichprobe=stichprobe.effektiv,
        versuche=versuche,
        schiefe=kandidat.schiefe or 0.0,
        woelbung=kandidat.woelbung or 3.0,
    )
    lage = Streuung(
        punkte=sammle(
            berichte=Path.cwd() / "reports",
            bestenliste=zustand / "leaderboard.json",
            verzeichnis=zustand / "trials.json",
        ),
        versuche=versuche,
        stichprobe=stichprobe.effektiv,
    )
    angenommen = lage.angenommen or 0.0

    console.print(
        f"\n[bold]Streuung ueber die Versuche[/] '{genome.name}' auf "
        f"{' + '.join(symbole)} {interval_obj.label}\n"
        f"  Historie   {spanne} Tage, {len(trades)} Trades "
        f"({stichprobe.effektiv} davon unabhaengig)\n"
        f"  Qualitaet  {kandidat.sharpe_je_trade:.4f} je Trade, Schiefe "
        f"{kandidat.schiefe or 0:+.2f}, Woelbung {kandidat.woelbung or 0:.2f}\n"
        f"  Versuche   {versuche}\n"
    )

    nachgerechnet = empfindlichkeit.bei(angenommen)
    if abs(nachgerechnet - gate.value) > 1e-6:
        console.print(
            f"[yellow]Nachrechnung weicht vom Gate ab "
            f"({nachgerechnet:.4f} gegen {gate.value:.4f}) - die Zahlen "
            f"unten beziehen sich auf eine andere Stichprobe als das "
            f"Urteil.[/]\n"
        )

    console.print(lage.tabelle())
    console.print(f"\n{lage.urteil()}\n")

    stellen = {"angenommen (Gate)": angenommen}
    if lage.gemessen is not None:
        stellen["aus den Versuchen"] = lage.gemessen
    kipp = empfindlichkeit.kippunkt()
    if kipp is not None:
        stellen["Kippunkt"] = kipp
    console.print(empfindlichkeit.tabelle(stellen))
    console.print(f"\n{empfindlichkeit.urteil(angenommen)}\n")


@app.command()
def jahresbild(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Woraus besteht das schlechteste Jahr?

    Von den vier Gates, an denen der Spitzenkandidat scheitert, ist dieses der
    schmalste Fehlschlag im System: -10,32 % gegen -10,00 %. Bei so einem
    Abstand ist die Frage, **woraus** die Zahl besteht, mehr wert als jeder
    weitere Suchlauf.

    Zwei sehr verschiedene Lagen sehen im Gate gleich aus:

        Eine Spitze     genau ein Zwoelfmonatsfenster liegt darunter
        Eine Hochebene  ein Viertel aller Fenster liegt darunter

    Im ersten Fall haengt der Fehlschlag an einer einzelnen Ausrichtung, im
    zweiten an der Strategie. Das Gate gibt nur das Minimum zurueck und sagt
    den Unterschied nicht.

    Zusaetzlich wird die Rechnung selbst geprueft: Das Gate schaetzt die
    Fensterbreite ueber Indizes, hier wird sie am Kalender gerechnet.

    **Kostet keinen Versuch** - es wird nichts Neues gerechnet, sondern eine
    Kurve zerlegt, die ohnehin schon da ist.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.gates import GateThresholds, gate_worst_year
    from research.jahresbild import zerlege
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    genome = spitzenkandidat()
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    console.print(
        f"\n[bold]Jahresbild[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Strategie   {genome.name}\n"
    )

    bericht = run_portfolio_walkforward(
        frames, lambda: compile_genome(genome), configs
    )
    if not bericht.windows:
        console.print("[red]Keine Fenster - nichts zu zerlegen.[/]")
        raise typer.Exit(2)

    schwellen = GateThresholds()
    gate = gate_worst_year(bericht, schwellen)
    bild = zerlege(
        bericht, bericht.all_trades,
        schwelle_pct=schwellen.worst_year_pct, index_wert=gate.value,
    )

    console.print(bild.tabelle())
    console.print(
        f"\n[dim]Gate rechnet ueber Indizes: {gate.value:+.2f} %. "
        f"Am Kalender: {bild.schlechtestes:+.2f} %. "
        f"Unterschied {bild.abweichung:+.2f} Punkte.[/]"
    )
    farbe = "yellow" if bild.darunter else "green"
    console.print(f"\n[{farbe}]{bild.urteil()}[/]\n")


@app.command()
def trennschaerfe(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Trennt irgendetwas die guten Trades von den schlechten?

    Der Kandidat scheitert an vier Gates, und drei davon verlangen dasselbe:
    mehr Qualitaet je Trade. Mehr Trades hilft dem Deflated Sharpe nur, wenn
    sie unabhaengig sind - und alle Wege dorthin sind gemessen und
    geschlossen.

    Bleibt: dieselben Trades, besser gewichtet. Genau dafuer ist die
    Konviktions-Groessenlogik gebaut, und genau die haengt an Bedingungen, die
    nichts sagen (``cli konfluenz``). Diese Messung sucht Bedingungen, die
    etwas sagen wuerden.

    **Gegen die richtige Null.** Wer zwoelf Merkmale prueft, findet mit
    Sicherheit eines, das trennt. Geprueft wird deshalb gegen "das Beste aus
    zwoelf trennt nicht", nicht gegen "dieses eine trennt nicht".

    Der Versuchszaehler bleibt unberuehrt: Hier wird kein Backtest gerechnet,
    sondern werden Trades aufgeteilt, die ohnehin gelaufen sind. Wer ein
    gefundenes Merkmal **einbaut**, hat dagegen einen neuen Kandidaten gebaut
    - ein Versuch mehr, und durch alle elf Gates.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.seeds import spitzenkandidat
    from research.trennschaerfe import messe, reihen_je_markt
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    genome = spitzenkandidat()
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    console.print(
        f"\n[bold]Trennschaerfe[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Strategie   {genome.name}\n"
    )

    bericht = run_portfolio_walkforward(
        frames, lambda: compile_genome(genome), configs
    )
    if not bericht.all_trades:
        console.print("[red]Keine Trades - nichts zu pruefen.[/]")
        raise typer.Exit(2)

    strategie = compile_genome(genome)
    merkmale = {
        markt: reihen_je_markt(strategie, frame) for markt, frame in frames.items()
    }

    ergebnis = messe(bericht.all_trades, merkmale)
    console.print(ergebnis.tabelle())
    farbe = "green" if ergebnis.belegt else "yellow"
    console.print(f"\n[{farbe}]{ergebnis.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert - hier wurde kein "
        "Backtest gerechnet, sondern eine vorhandene Trade-Liste geteilt.[/]"
    )


@app.command()
def konfluenz(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sagt die Konfluenz etwas ueber den Ausgang - oder nur ueber die Groesse?

    Die Konviktions-Groessenlogik ruht auf einem Satz: **Je mehr
    Zusatzbedingungen erfuellt sind, desto besser der Trade.** Danach richtet
    sich der Einsatz. Gemessen wurde bisher nur die Wirkung dieser Logik auf
    das Gesamtergebnis, nie die Annahme selbst.

    Das ist ein Unterschied: Eine Groessenlogik kann funktionieren, weil sie in
    schlechten Phasen kleiner handelt, ohne dass die Reihenfolge stimmt, nach
    der sie das tut.

    Der Anlass: Alle drei Groessenregler - Vola-Ziel, Stop, Konviktion -
    bewegen den Deflated Sharpe um weniger als 0,02. Bei den ersten beiden ist
    das einsichtig, sie skalieren alles gleich. Die Konviktion tut das nicht -
    sie verschiebt Gewichte zwischen Trades. Dass auch sie nichts bewegt, muss
    einen anderen Grund haben.

    **Kostet keinen Versuch:** Geprueft wird eine Annahme des Kandidaten an
    seinen eigenen, bereits gerechneten Trades - keine neue Regel.
    """
    from decimal import Decimal

    import pandas as pd

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.konfluenzwirkung import messe, zaehle_bedingungen
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    genome = spitzenkandidat()
    if not genome.konfluenz:
        console.print("[yellow]Dieser Kandidat hat keine Konfluenz.[/]")
        raise typer.Exit(0)

    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    console.print(
        f"\n[bold]Konfluenz[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Strategie   {genome.name}\n"
        f"  Bedingungen {len(genome.konfluenz)}\n"
    )

    bericht = run_portfolio_walkforward(
        frames, lambda: compile_genome(genome), configs
    )
    if not bericht.all_trades:
        console.print("[red]Keine Trades - nichts zu pruefen.[/]")
        raise typer.Exit(2)

    strategie = compile_genome(genome)
    zaehlung = {
        markt: pd.Series(
            zaehle_bedingungen(strategie, frame),
            index=pd.to_datetime(frame["open_time"]),
        )
        for markt, frame in frames.items()
    }

    wirkung = messe(bericht.all_trades, zaehlung)
    console.print(wirkung.tabelle())

    farbe = "green" if wirkung.belegt and wirkung.monoton else "yellow"
    console.print(f"\n[{farbe}]{wirkung.urteil()}[/]\n")
    console.print(
        "[dim]Was daraus **nicht** folgt: Traegt nur die volle Konfluenz, ist "
        "'handle nur bei voller Konfluenz' keine Schlussfolgerung, sondern die "
        "Auswahl des besten Eimers nach Ansicht der Daten. Der "
        "Bestaetigungsfilter ist fuer diese Regelfamilie ohnehin schon "
        "gemessen und widerlegt.[/]"
    )


@app.command()
def suchbudget(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    hoechstens: int = typer.Option(12, "--hoechstens", help="Zeilen in der Liste."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Was muesste ein neuer Einfall koennen - und kam je etwas so weit?

    Alle Groessenregler sind ausgemessen und bewegen das haerteste Gate nicht.
    Was bleibt, sind neue Regeln - und jede kostet einen Versuch, der die
    Huerde fuer alle hebt. Bevor man so etwas budgetiert, gehoert
    ausgerechnet, worauf man zielt.

    Der Deflated Sharpe haengt an zwei Groessen: Zahl der Trades und Qualitaet
    je Trade. Zu jeder Trade-Zahl gehoert deshalb ein **noetiger Sharpe je
    Trade** - und diese Linie ist der Massstab, nicht eine der beiden Zahlen
    allein.

    **Kostet keinen Versuch:** Gemessen werden bereits gerechnete Kandidaten,
    ohne Gates. Es wird nichts ausgewaehlt und nichts vorgeschlagen.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.seeds import GENERATIONS, spitzenkandidat
    from research.suchbudget import Budget, Kandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    genome = []
    for liste in GENERATIONS.values():
        for eintrag in liste:
            genome.append(eintrag() if callable(eintrag) else eintrag)
    genome.append(spitzenkandidat())

    trials = load_trials(Path(settings.paths.state) / "trials.json")
    console.print(
        f"\n[bold]Suchbudget[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Kandidaten {len(genome)}\n"
        f"  Versuche   {trials}\n"
    )

    kandidaten = []
    for g in genome:
        bericht = run_portfolio_walkforward(
            frames, lambda gg=g: compile_genome(gg), configs
        )
        eintrag = Kandidat.aus_trades(g.name, bericht.all_trades)
        if eintrag is not None:
            kandidaten.append(eintrag)

    if not kandidaten:
        console.print("[red]Kein Kandidat mit genug Trades.[/]")
        raise typer.Exit(2)

    # Der zweite Betriebspunkt gehoert ins Urteil (Befund 126): Die
    # Kandidaten tragen Perpetual-Zahlen, und der Faktor im Urteil traegt
    # damit eine Kostenannahme mit, die im Spot-Handel entfaellt.
    budget = Budget(
        versuche=trials,
        kandidaten=kandidaten,
        spotguete=_spotguete(frames, symbole, spitzenkandidat(), settings),
    )

    console.print("[bold]Die Grenzlinie[/]")
    console.print(budget.tabelle())
    console.print(
        "\n[dim]Gelesen: Bei so vielen **unabhaengigen** Beobachtungen "
        "braeuchte es diesen Sharpe je Trade, damit der Deflated Sharpe 0,95 "
        "erreicht.[/]\n"
    )

    console.print(f"[bold]Wie weit die {len(kandidaten)} Kandidaten kamen[/]")
    # Die Kandidaten kommen aus der Bestenliste und tragen nur ihre **rohe**
    # Trade-Zahl; ihre effektive Stichprobe ist nie gemessen worden. Die
    # Spalten "noetig" und "Faktor" sind deshalb Untergrenzen, und die
    # Ueberschrift sagt das - sonst stuende ueber der Tabelle eine Genauigkeit,
    # die keine Zeile darin hat (Befund 139).
    console.print(
        "[dim]Auf rohen Trade-Zahlen gerechnet - 'noetig' und 'Faktor' sind "
        "Untergrenzen.[/]"
    )
    console.print(
        f"{'Kandidat':38} {'Trades':>7} {'hat':>8} {'min.noetig':>11} "
        f"{'min.Faktor':>11}"
    )
    geordnet = sorted(
        budget.abstaende(), key=lambda a: a.faktor if a.faktor is not None else 1e9
    )
    for a in geordnet[:hoechstens]:
        # Ueber ``als_zahl``/``als_faktor``, damit die Lesart an einer Stelle
        # lebt und nicht in jedem Praesentator neu (Befund 149).
        noetig = a.als_zahl(kurz=True)
        faktor = a.als_faktor(kurz=True)
        console.print(
            f"{a.kandidat.name[:38]:38} {a.kandidat.trades:>7} "
            f"{a.kandidat.sharpe_je_trade:>8.4f} {noetig:>11} {faktor:>11}"
        )

    console.print(f"\n[yellow]{budget.urteil()}[/]\n")
    console.print("[bold]Was Weitersuchen an der Linie verschiebt[/]")
    # Gerechnet auf der **effektiven** Stichprobe des massgeblichen Punktes.
    # Hier stand die rohe 152; die Linie lag damit rund 14 % zu tief
    # (Befund 139).
    from research.referenz import SPOTPUNKT

    for weitere in (0, 40, 90, 190, 390):
        wert = budget.noetig_bei(SPOTPUNKT.effektiv, versuche=trials + weitere)
        if wert is not None:
            console.print(
                f"  {trials + weitere:>4} Versuche: {SPOTPUNKT.effektiv} "
                f"unabhaengige Beobachtungen braeuchten {wert:.4f}"
            )


def _kerzenbestand(store) -> str:
    """Was **wirklich** im Kerzenspeicher liegt - gemessen, nicht gepflegt.

    Ein Auftragspunkt behauptete fuenf Befunde lang, die 15-Minuten-Daten
    laegen vor; beim Behaelterwechsel in Befund 151 waren sie verschwunden.
    ``data_store`` liegt nicht im Repository, dieser Fall wiederholt sich also
    bei jedem frischen Klon. Prosa merkt das nicht, diese Zeile schon
    (Befund 157).
    """
    from data.reference import PAIRS

    gefunden = []
    for symbol in PAIRS:
        vorhanden = []
        for iv in ("D", "15"):
            try:
                frame = store.read(symbol, Interval(iv))
            except Exception:
                continue
            if frame is not None and not frame.empty:
                vorhanden.append(f"{Interval(iv).label} {len(frame)}")
        if vorhanden:
            gefunden.append(f"{symbol} ({', '.join(vorhanden)})")
    return "; ".join(gefunden) if gefunden else "keine Kerzen"


@app.command()
def stand(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Wo steht das Projekt - auf einem Bildschirm.

    ``strategies/BEFUND.md`` ist ein Laborbuch: chronologisch, vollstaendig,
    und fuer die Frage *wo stehen wir* unbrauchbar. Dieser Befehl beantwortet
    sie in vier Teilen: der gemessene Stand, was untersucht und geschlossen
    ist, was beim Nutzer liegt, und was nur auf seinem Rechner laufen kann.

    Die Zahlen werden **gemessen**, nicht gepflegt - der Kandidat laeuft durch
    die Gates, der Abstand kommt aus der Grenzlinie. Nichts davon kann
    veralten, ohne dass es auffaellt.

    Kostet keinen Versuch.
    """
    from decimal import Decimal

    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.betriebspunkt import Betriebslage, Betriebspunkt
    from research.gatelage import ordne
    from research.gates import evaluate_gates
    from research.reihenfolge import STAND as REIHENFOLGE
    from research.reihenfolge import Art as Reihenfolgeart
    from research.reihenfolge import Lage as Reihenfolgelage
    from research.seeds import spitzenkandidat
    from research.stand import Lage
    from research.suchbudget import Budget, Kandidat
    from research.versuche import TROCKENLAUF, trockenlauf
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    store = CandleStore(settings.paths.data_store)
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame

    frames = common_range(roh)
    genome = spitzenkandidat()
    configs = {
        x: BacktestConfig(
            instrument=_fallback_instrument(_bybit_kontrakt(x)),
            risk=settings.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=_terminkalender(settings) or None,
        )
        for x in symbole
    }

    trials = load_trials(Path(settings.paths.state) / "trials.json")
    bericht = run_portfolio_walkforward(
        frames, lambda: compile_genome(genome), configs
    )
    if not bericht.windows:
        console.print("[red]Keine Fenster - zu wenig gemeinsame Historie.[/]")
        raise typer.Exit(2)

    erster = next(iter(frames.values()))
    gates = evaluate_gates(
        genome, bericht, erster, configs[symbole[0]], trials_so_far=trials,
        frames=frames, configs=configs,
    )
    # **Die Latte gilt fuer die Stichprobe, mit der das Gate urteilt.**
    # Hier stand ``Kandidat.aus_trades`` allein - das laesst ``effektiv``
    # leer, und die Latte fiel auf die rohe Trade-Zahl zurueck: 0,2984 statt
    # der wirklichen. Genau der Fehler aus Befund 139, an der Stelle, die ein
    # Leser zuerst aufschlaegt (Befund 148).
    from research.gates import stichprobe_wie_im_gate
    from research.randschnitt import ohne_zensierte, randtrades

    # **Nur fertig gehandelte Trades** (Befund 152) - genau wie im Gate. Ein
    # am Datenende glattgestellter Trade ist keine abgeschlossene Beobachtung;
    # sein Ergebnis haengt daran, wann zuletzt Kerzen geholt wurden. In
    # ``kombiniert`` (Rendite, Rueckgang) bleibt er drin, dort gehoert er hin.
    zensiert = randtrades(bericht.all_trades)
    gehandelt = ohne_zensierte(bericht)
    stichprobe = stichprobe_wie_im_gate(
        gehandelt.all_trades,
        beine=getattr(bericht, "beine", None),
        bloecke=[[float(t.net_pnl) for t in w.trades] for w in gehandelt.windows],
    )
    roh = Kandidat.aus_trades(genome.name, gehandelt.all_trades)
    eintrag = (
        None if roh is None
        else Kandidat(
            name=roh.name, trades=roh.trades,
            sharpe_je_trade=roh.sharpe_je_trade,
            schiefe=roh.schiefe, woelbung=roh.woelbung,
            effektiv=stichprobe.effektiv,
        )
    )
    qualitaet = eintrag.sharpe_je_trade if eintrag else 0.0
    budget = Budget(versuche=trials, kandidaten=[eintrag] if eintrag else [])
    kombiniert = bericht.combined

    # **Vor dem Bericht, nicht danach.** Der Auftragstext zum healthcheck
    # trug die Zahlen beider Punkte bis Befund 165 als gepflegte Prosa, weil
    # die Messung erst spaeter im Kommando lief. Sie ist stehengeblieben,
    # waehrend die Messung weiterlief.
    zweitpunkt = _spotpunkt(frames, symbole, genome, trials, settings)

    lage = Lage(
        kandidat=genome.name,
        maerkte=f"{' + '.join(symbole)}, {interval_obj.label}",
        zweitpunkt=zweitpunkt,
        trades=len(gehandelt.all_trades),
        effektiv=stichprobe.effektiv,
        kerzenbestand=_kerzenbestand(store),
        zensiert=len(zensiert),
        sharpe_je_trade=qualitaet,
        noetiger_sharpe=(
            budget.abstaende()[0].noetig if eintrag is not None else None
        ),
        bestanden=sum(1 for r in gates.results if r.passed),
        gesamt=len(gates.results),
        offen=tuple(r.name for r in gates.results if not r.passed),
        versuche=trials,
        cagr_pct=kombiniert.cagr_pct if kombiniert else 0.0,
        rueckgang_pct=kombiniert.max_drawdown_pct if kombiniert else 0.0,
    )

    console.print()
    # Ein vergessener Trockenlauf ist gefaehrlicher als das Problem, das er
    # loest: Er haelt den Zaehler still, und ein zu niedriger Zaehler macht
    # den Deflated Sharpe milder. Deshalb steht er ganz oben.
    if trockenlauf():
        console.print(
            f"[red]ACHTUNG: {TROCKENLAUF} ist gesetzt.[/] Der Versuchszaehler "
            f"wird nicht fortgeschrieben - jede Suche in diesem Zustand "
            f"zaehlt nicht mit, und die Huerde bleibt zu niedrig.\n"
        )
    console.print(lage.bericht())

    # **Die Sperre gehoert an den Anfang, nicht ans Ende.**
    #
    # ``GateReport.summary`` nennt sie schon lange - aber nur im Zweig
    # ``geprueftes_bestanden``, also erst, wenn alle Gates halten. Der Bestand
    # steht bei 7 von 11; der Zweig ist nie gelaufen. Damit wurde die Sperre
    # genau dann sichtbar, wenn man sie erreicht - und dann ist die
    # Reihenfolge der Arbeit laengst festgelegt. Elf Befunde lagen dahinter
    # (Befund 114).
    reihenfolge = Reihenfolgelage(schritte=REIHENFOLGE)
    if reihenfolge.gesperrt:
        console.print()
        console.print("[red]WAS DEN ZUSTAND AENDERN KANN[/]")
        console.print("-" * 72)
        for s in reihenfolge.schritte:
            farbe = "red" if s.art is Reihenfolgeart.SPERRE else "dim"
            console.print(f"  [{farbe}]{s.als_zeile()}[/]")
            console.print(f"      [dim]{s.hinweis}[/]")
        console.print(f"\n  [red]{reihenfolge.urteil()}[/]")
        hiesige = ", ".join(s.name for s in reihenfolge.hier)
        console.print(
            f"  [yellow]Hier laufen wuerde: {hiesige or 'nichts davon'}. "
            "Alles andere liegt beim Nutzer oder hat gemessen keine Quelle.[/]"
            if reihenfolge.hier
            else "  [yellow]Kein Schritt laeuft aus diesem Container heraus.[/]"
        )

    # **Der zweite Betriebspunkt gehoert daneben, nicht in einen Befund.**
    # Bis Befund 112 zeigte dieser Bericht allein den Perpetual-Stand - 7 von
    # 11 - obwohl seit Befund 108 gemessen ist, dass Spot bei 9 von 11 steht.
    # Wer hier nachsah, bekam eine Aufgabe zu sehen, die fast doppelt so gross
    # war wie die gemessene. Berichtet wird trotzdem weiter der schlechtere:
    # Welcher gilt, haengt an einer Tatsache, die nur der Nutzer klaeren kann.
    # Gemessen wird er weiter oben - der Auftragstext braucht ihn schon dort
    # (Befund 165), und zweimal rechnen waere derselbe Lauf zum doppelten
    # Preis.
    if zweitpunkt is not None:
        erstpunkt = Betriebspunkt(
            name="Perpetual", trades=len(bericht.all_trades),
            cagr_pct=float(kombiniert.cagr_pct) if kombiniert else 0.0,
            rueckgang_pct=(
                float(kombiniert.max_drawdown_pct) if kombiniert else 0.0
            ),
            guete=qualitaet,
            dsr=float(
                next(r.value for r in gates.results if r.name == "Deflated Sharpe")
            ),
            bestanden=sum(1 for r in gates.results if r.passed),
            gesamt=len(gates.results),
            offen=tuple(r.name for r in gates.results if not r.passed),
        )
        betrieb = Betriebslage(punkte=(erstpunkt, zweitpunkt))
        console.print()
        console.print("DIE BEIDEN BETRIEBSPUNKTE")
        console.print("-" * 72)
        for p in (erstpunkt, zweitpunkt):
            farbe = "green" if p is betrieb.massgeblich else "dim"
            console.print(f"  [{farbe}]{p.als_zeile()}[/]")
        console.print(f"\n  [yellow]{betrieb.urteil()}[/]")

    if eintrag is not None:
        console.print()
        console.print("WORAN DAS HAERTESTE GATE HAENGT")
        console.print("-" * 72)
        console.print(
            "  Je Groesse einzeln: Wo muesste sie stehen, damit der Deflated "
            "Sharpe\n  0,95 erreicht - alles andere unveraendert?\n"
        )
        for h in budget.hebel(eintrag):
            farbe = "yellow" if h.moeglich else "red"
            console.print(f"  [{farbe}]{h}[/]")
        # Abgeleitet und nicht danebengeschrieben: Hier stand bis Befund 109
        # ein fester Satz, der von genau einem offenen Weg sprach. Er war schon
        # vorher falsch - es waren zwei - und mit Befund 108 zusaetzlich
        # veraltet, weil unter Spot ein dritter dazukam.
        console.print(
            "\n  [dim]" + budget.hebelerklaerung(budget.hebel(eintrag)) + "[/]"
        )

    console.print()
    console.print("DIE GATES IM EINZELNEN")
    console.print("-" * 72)
    for r in gates.results:
        zeichen = "+" if r.passed else "-"
        farbe = "green" if r.passed else "yellow"
        console.print(
            f"  [{farbe}]{zeichen}[/] {r.name:24} {r.value:>10.3f} "
            f"gegen {r.threshold:>10.3f}"
        )
        # **Ohne die Botschaft zeigt die Zeile teilweise in die falsche
        # Richtung.** Bei der Messlatte liegt der Wert um das 3,8-fache ueber
        # der Schwelle und das Gate faellt trotzdem durch, weil es eine zweite
        # Bedingung hat. In Befund 91 habe ich das beim Lesen der eigenen
        # Tabelle falsch herum verstanden.
        if not r.passed and r.message:
            console.print(f"      [dim]{r.message}[/]")

    # **Der zweite Punkt gehoert auch in die Aufgabenliste, nicht nur in die
    # Zeile darueber.** Bis Befund 164 kam sie allein aus dem berichteten
    # Punkt und nannte beim Bestand genau die zwei Gates, die unter Spot
    # bestehen - eine Arbeit, die sich mit der Antwort auf eine offene Frage
    # aufloest. Berichtet wird weiter der schlechtere Punkt.
    lage = (
        ordne(gates.results)
        if zweitpunkt is None
        else ordne(
            gates.results, zweitpunkt=zweitpunkt.name, dort_offen=zweitpunkt.offen
        )
    )
    if lage.hindernisse:
        console.print()
        console.print("WORAN DIE ARBEIT LIEGT")
        console.print("-" * 72)
        console.print(lage.urteil())


@app.command()
def decke(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    fenster: bool = typer.Option(
        False, "--fenster",
        help="Statt der Kostendecke: dieselbe Regel auf drei Datenfenstern.",
    ),
    anschlag: bool = typer.Option(
        False, "--anschlag",
        help="Ist 'Kosten null' wirklich der Anschlag? Schaltet zusaetzlich "
             "die Bremsen ab, die Trades verhindern (Befund 127).",
    ),
    historie: bool = typer.Option(
        False, "--historie",
        help="Wie schnell waechst die Evidenz mit der Historie? Dieselben "
             "Regeln, wandernder Anfang (Befund 132).",
    ),
    breite: bool = typer.Option(
        False, "--breite",
        help="Bringen weitere Maerkte Evidenz? Dieselben Regeln, mehr Beine "
             "(Befund 133).",
    ),
    stichprobe: bool = typer.Option(
        False, "--stichprobe",
        help="Wie stark haengt n an der Kalibrierung der "
             "Abhaengigkeitspruefung? (Befund 134).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Wo ist nachweislich nichts mehr zu holen?

    Befund 110 liess offen, ob sich noch eine Bedingung findet, die wie das
    Funding wirkt - ein Wegfall, der jeden Fund gleichermassen hebt. Dieser
    Befehl misst die **Decke** der Kostenfamilie: den Lauf, der gar nichts
    kostet. Tiefer geht es nicht, und was dort noch fehlt, fehlt endgueltig.

    Mit ``--fenster`` stattdessen die zweite Familie: dieselbe Regel auf drei
    Datenfenstern. Berichtet werden **alle drei**, auch die schlechteren - wer
    sich nach den Zahlen das guenstigste aussucht, lockert ein Gate, nur
    unauffaelliger.

    **Kostet keinen Versuch.** Derselbe Kandidat, dieselben Regeln; veraendert
    werden die Handelskosten beziehungsweise der Datenausschnitt.
    """
    from decimal import Decimal

    from backtest.costs import CostModel, FundingSchedule
    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.decke import Decke, Deckenwert, Fenster, Fensterlage, Stichprobenbedarf
    from research.gates import evaluate_gates
    from research.seeds import spitzenkandidat
    from research.stand import GESCHLOSSEN
    from research.suchbudget import Kandidat
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    store = CandleStore(settings.paths.data_store)

    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame
    gemeinsam = common_range(roh)
    trials = load_trials(Path(settings.paths.state) / "trials.json")
    basis = spitzenkandidat()
    ohne_hebel = basis.model_copy(
        update={"sizing": basis.sizing.model_copy(update={"fraction": 1.0})}
    )

    def configs_fuer(
        namen, *, gebuehr: float = 1.0, rutsch: float = 1.0, funding: str = "0"
    ) -> dict:
        aus = {}
        for x in namen:
            grund = BacktestConfig(
                instrument=_fallback_instrument(_bybit_kontrakt(x)),
                risk=settings.risk, initial_equity=Decimal("500"),
                enforce_risk_limits=True,
                kalender=_terminkalender(settings) or None,
            )
            aus[x] = BacktestConfig(
                instrument=grund.instrument, risk=grund.risk,
                costs=CostModel(
                    maker_fee_rate=grund.costs.maker_fee_rate * Decimal(str(gebuehr)),
                    taker_fee_rate=grund.costs.taker_fee_rate * Decimal(str(gebuehr)),
                    slippage_bps=grund.costs.slippage_bps * Decimal(str(rutsch)),
                    stop_slippage_bps=(
                        grund.costs.stop_slippage_bps * Decimal(str(rutsch))
                    ),
                ),
                funding=FundingSchedule(default_rate=Decimal(funding)),
                initial_equity=grund.initial_equity,
                enforce_risk_limits=True,
                allow_shorts=grund.allow_shorts,
                entry_expiry_bars=grund.entry_expiry_bars,
                max_hold_bars=grund.max_hold_bars,
                kalender=grund.kalender,
            )
        return aus

    def messen(frames: dict, configs: dict, *, hebel: bool = False):
        """Ein Lauf, und heraus kommt, was beide Teile brauchen."""
        genom = basis if hebel else ohne_hebel
        erster = next(iter(frames.values()))
        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genom), configs
        )
        ergebnisse = evaluate_gates(
            genom, bericht, erster, configs[next(iter(frames))],
            trials_so_far=trials, frames=frames, configs=configs,
        )
        dsr = next(r for r in ergebnisse.results if r.name == "Deflated Sharpe")
        eintrag = Kandidat.aus_trades("Lauf", bericht.all_trades)
        return bericht, ergebnisse, float(dsr.value), float(dsr.threshold), eintrag

    if anschlag:
        # **Ist "Kosten null" wirklich der Anschlag?** (Befund 127)
        #
        # Befund 111 hat Gebuehren, Slippage und Funding auf null gesetzt und
        # geschlossen, es gebe nichts mehr wegzunehmen. Drei Bremsen blieben
        # dabei an, und alle drei verhindern **Trades**: der Terminkalender,
        # die Verfallsfrist der PostOnly-Limits und der Risk-Officer.
        #
        # Keine davon ist eine Option - der Risk-Officer bleibt, das ist die
        # Sicherheit. Gemessen wird eine Grenze, kein Betriebspunkt.
        from research.decke import Reibungsprobe, Stufe

        console.print(
            f"\n[bold]Ist 'Kosten null' der Anschlag?[/] "
            f"{' + '.join(symbole)} {interval_obj.label}\n"
            f"  Kandidat   {basis.name}\n"
            f"  Versuche   {trials}\n\n"
            "[dim]Keine dieser Abschaltungen ist eine Option. Gemessen wird "
            "eine Grenze.[/]\n"
        )

        stufen = []
        for name, kw, extra in (
            ("Spot wie gebaut", {}, {}),
            ("+ Kosten null (Befund 111)", {"gebuehr": 0.0, "rutsch": 0.0}, {}),
            (
                "+ ohne Terminkalender",
                {"gebuehr": 0.0, "rutsch": 0.0},
                {"kalender": None},
            ),
            (
                "+ Limits verfallen nie",
                {"gebuehr": 0.0, "rutsch": 0.0},
                {"kalender": None, "entry_expiry_bars": 999},
            ),
            (
                "+ ohne Risk-Officer",
                {"gebuehr": 0.0, "rutsch": 0.0},
                {
                    "kalender": None,
                    "entry_expiry_bars": 999,
                    "enforce_risk_limits": False,
                },
            ),
        ):
            configs = configs_fuer(gemeinsam, **kw)
            if extra:
                configs = {
                    x: c.__class__(
                        **{
                            **{
                                f: getattr(c, f)
                                for f in c.__dataclass_fields__
                            },
                            **extra,
                        }
                    )
                    for x, c in configs.items()
                }
            bericht, ergebnisse, wert, _, eintrag = messen(gemeinsam, configs)
            stufen.append(
                Stufe(
                    name=name,
                    trades=len(bericht.all_trades),
                    guete=eintrag.sharpe_je_trade if eintrag else 0.0,
                    dsr=wert,
                    bestanden=sum(1 for r in ergebnisse.results if r.passed),
                    gesamt=len(ergebnisse.results),
                    offen=tuple(
                        r.name for r in ergebnisse.results if not r.passed
                    ),
                )
            )
            console.print(f"  {stufen[-1].als_zeile()}")

        probe = Reibungsprobe(stufen=tuple(stufen))
        farbe = "green" if probe.anschlag_haelt else "red"
        console.print(f"\n[{farbe}]{probe.urteil()}[/]\n")
        console.print(
            "[dim]Der Versuchszaehler bleibt unveraendert: Dieselbe Strategie, "
            "dieselben Daten.[/]\n"
        )
        return

    if stichprobe:
        # **Die Zahl unter allen Zahlen** (Befund 134).
        #
        # Auf n = 152 steht der Deflated Sharpe, die Luecke, die fehlenden
        # Beobachtungen und die 1,8 Jahre aus Befund 132. Gemessen wird hier
        # nicht, welche Kalibrierung die schoenste ist, sondern **wie stark
        # das Ergebnis an dieser einen Wahl haengt**. Die Regel bleibt, wo sie
        # ist.
        import numpy as np

        from research.empfindlichkeit import Empfindlichkeit, Kalibrierung
        from research.gates import concurrent_groups, deflated_sharpe_ratio
        from research.unabhaengigkeit import designeffekt

        configs = configs_fuer(gemeinsam)
        bericht, ergebnisse, wert, grenze, eintrag = messen(gemeinsam, configs)
        trades = bericht.all_trades
        nach_fenster = [[float(x.net_pnl) for x in w.trades] for w in bericht.windows]
        nach_gleich = [
            [float(t.net_pnl) for t in g] for g in concurrent_groups(trades)
        ]

        # Dieselben Momente, die das Gate nimmt - nur n wandert.
        pnls = np.array([float(t.net_pnl) for t in trades], dtype=float)
        streuung = pnls.std(ddof=1)
        guete_wert = float(pnls.mean() / streuung)
        zentriert = (pnls - pnls.mean()) / streuung
        schiefe_wert = float(np.mean(zentriert**3))
        woelbung_wert = float(np.mean(zentriert**4))

        def dsr_bei(n: int) -> float:
            return float(
                deflated_sharpe_ratio(
                    observed_sharpe=guete_wert, trials=trials, sample_size=n,
                    skew=schiefe_wert, kurtosis=woelbung_wert,
                )
            )

        console.print(
            f"\n[bold]Empfindlichkeit der Stichprobe[/] {interval_obj.label}, Spot\n"
            f"  Kandidat   {basis.name}\n"
            f"  Versuche   {trials}\n"
            f"  Trades     {len(trades)}   "
            f"{len(nach_fenster)} Kalenderfenster, "
            f"{len(nach_gleich)} Gleichzeitigkeitsgruppen\n\n"
            "[dim]Vor dem Lauf festgelegt: Berichtet werden alle "
            "Kalibrierungen, auch die\nunbequemen. Die Regel im Code bleibt "
            "die Referenz - gemessen wird, was an ihr\nhaengt, nicht welche "
            "Wahl das schoenste Ergebnis gibt.[/]\n"
        )

        stufen = ((0.95, "95. Perzentil (Regel)"), (0.90, "90. Perzentil"),
                  (0.75, "75. Perzentil"), (0.50, "Median"))
        for etikett, bloecke in (("nach Kalenderfenstern", nach_fenster),
                                 ("nach Gleichzeitigkeit", nach_gleich)):
            probe = designeffekt(bloecke)
            if probe is None:
                console.print(f"  [dim]{etikett}: zu wenige Bloecke[/]\n")
                continue
            console.print(
                f"  [bold]{etikett}[/]   ICC {probe.icc:.3f}, "
                f"p = {probe.p_wert:.4f}"
                + ("   [dim](Abhaengigkeit nachgewiesen)[/]"
                   if probe.nachgewiesen else "")
            )
            kal: list[Kalibrierung] = []
            for q, name in stufen:
                e = designeffekt(bloecke, kalibrierung=q)
                if e is None:
                    continue
                # ``designeffekt`` rechnet auf den Bloecken; die Trade-Zahl
                # kommt vom Aufrufer - derselbe Grund wie in
                # ``effektive_stichprobe``.
                faktor = e.effektiv / e.roh if e.roh else 1.0
                n = max(1, min(len(trades), round(len(trades) * faktor)))
                d = dsr_bei(n)
                kal.append(
                    Kalibrierung(name=name, quantil=q, schranke=0.0,
                                 effektiv=n, dsr=d)
                )
                console.print(f"    {name:<24} n = {n:>4}   DSR {d:.4f}")
            lage = Empfindlichkeit(
                roh=len(trades), icc=probe.icc, designeffekt=0.0,
                p_wert=probe.p_wert, kalibrierungen=tuple(kal),
                schwelle=grenze,
            )
            console.print(f"\n  [yellow]{lage.urteil()}[/]\n")
        console.print(
            "[dim]Die Kalibrierung bleibt, wo sie ist. Sie zu wechseln, "
            "nachdem man ihre Wirkung\ngesehen hat, waere das wirksamste "
            "gelockerte Gate von allen - es liegt unter allen\nanderen "
            "zugleich.[/]\n"
        )
        return

    if breite:
        # **Dieselbe Familie, die andere Achse** (Befund 133).
        #
        # Befund 132 hat die Historie ausgemessen und die Vergangenheit als
        # ausgeschoepft befunden. Fuer die Breite galt das nicht automatisch:
        # Im Register steht "effektive Stichprobe bleibt bei 150" (Befund 27),
        # und genau diese Annahme wurde in Befund 132 fraglich, weil die
        # Korrelationsstrafe dort an keinem Fenster biss.
        from research.aufstellung import Aufstellungsreihe, Marktsatz
        from research.gates import stichprobe_wie_im_gate

        zusatz = [
            x for x in ("LTCUSD_BITSTAMP", "XRPUSD_BITSTAMP") if x not in symbole
        ]
        def kurz(x: str) -> str:
            return x.split("USD")[0]

        aufstellungen = [
            (" + ".join(kurz(x) for x in symbole) + " (Referenz)", list(symbole))
        ]
        for x in zusatz:
            aufstellungen.append((f"+ {kurz(x)}", [*symbole, x]))
        if len(zusatz) > 1:
            aufstellungen.append(
                (f"+ {' + '.join(x.split('USD')[0] for x in zusatz)}",
                 [*symbole, *zusatz])
            )

        console.print(
            f"\n[bold]Marktaufstellungen[/] {interval_obj.label}, Spot\n"
            f"  Kandidat   {basis.name}\n"
            f"  Versuche   {trials}\n\n"
            "[dim]Vor dem Lauf festgelegt: Berichtet werden alle Aufstellungen. "
            "Referenz ist die\nerste - nicht die beste. Kostet keinen Versuch: "
            "derselbe Kandidat, mehr Beine.\nAuf LTC und XRP ist er nie gesucht "
            "worden; dort steht er aus dem Stand ausserhalb\nder Stichprobe.[/]\n"
        )
        kopf = (
            f"  {'Aufstellung':<24} {'Trades':>6} {'eff':>5} {'Guete':>7} "
            f"{'DSR':>7} {'Gates':>6}"
        )
        console.print(kopf)
        console.print("  " + "-" * (len(kopf) - 2))

        saetze: list[Marktsatz] = []
        for name, satz in aufstellungen:
            fehlend = [x for x in satz if store.read(x, interval_obj).empty]
            if fehlend:
                console.print(f"  [dim]{name:<24} keine Kerzen: {', '.join(fehlend)}[/]")
                continue
            teil = common_range({x: store.read(x, interval_obj) for x in satz})
            erster = next(iter(teil.values()))
            cfgs = configs_fuer(teil)
            bericht, ergebnisse, wert, _, eintrag = messen(teil, cfgs)
            if not bericht.windows:
                console.print(f"  [dim]{name:<24} kein Fenster zustande gekommen[/]")
                continue
            trades = bericht.all_trades
            beine = [
                [float(t.net_pnl) for t in trades if t.symbol == x] for x in satz
            ]
            bloecke = [[float(x.net_pnl) for x in w.trades] for w in bericht.windows]
            eff = stichprobe_wie_im_gate(trades, beine=beine, bloecke=bloecke)
            saetze.append(
                Marktsatz(
                    name=name, maerkte=len(satz), tage=len(erster),
                    trades=len(trades), effektiv=eff.effektiv,
                    guete=eintrag.sharpe_je_trade if eintrag else 0.0,
                    dsr=wert,
                    bestanden=sum(1 for r in ergebnisse.results if r.passed),
                    gesamt=len(ergebnisse.results),
                )
            )
            console.print(f"  {saetze[-1].als_zeile()}")

        reihe = Aufstellungsreihe(tuple(saetze))
        if len(saetze) > 1:
            console.print(f"\n  {'Aufstellung':<24} {'Guete x sqrt(eff)':>18}")
            console.print("  " + "-" * 42)
            for s in saetze:
                console.print(f"  {s.name:<24} {s.evidenz:>18.3f}")
            console.print(
                "\n  [dim]Kuerzung durch die Abhaengigkeitspruefung: "
                + ", ".join(f"{s.kuerzung:.0%}" for s in saetze)
                + " - sie setzt erst ein,\n  wenn genug Beobachtungen da sind, "
                "um Abhaengigkeit nachzuweisen.[/]"
            )
        console.print(f"\n[yellow]{reihe.urteil()}[/]\n")
        return

    if historie:
        # **Die vierte Familie: unabhaengige Beobachtungen** (Befund 132).
        #
        # Alle Fenster enden am selben Tag, nur der Anfang wandert. Gesucht
        # wird nicht der beste Ausschnitt - das laengste Fenster ist die
        # Referenz und bleibt es -, sondern die Steigung: Wie viel Evidenz
        # bringt ein zusaetzliches Jahr?
        import pandas as pd

        from research.gates import stichprobe_wie_im_gate
        from research.historie import Historienkurve, Historienstufe

        erster_voll = next(iter(gemeinsam.values()))
        anfang = erster_voll["open_time"].min()
        ende = erster_voll["open_time"].max()
        starts = [str(anfang.date())] + [
            s
            for s in ("2018-08-16", "2019-08-16", "2020-03-30", "2021-08-16",
                      "2022-08-16")
            if pd.Timestamp(s, tz="UTC") > anfang
        ]

        console.print(
            f"\n[bold]Historienkurve[/] {interval_obj.label}, Spot\n"
            f"  Kandidat   {basis.name}\n"
            f"  Versuche   {trials}\n"
            f"  Ende       {ende.date()} (fuer alle Fenster gleich)\n\n"
            "[dim]Vor dem Lauf festgelegt: Berichtet werden alle Fenster. "
            "Referenz ist das laengste -\nein kuerzeres weiss nie mehr. "
            "Kostet keinen Versuch: derselbe Kandidat, anderer\nAusschnitt.[/]\n"
        )
        kopf = (
            f"  {'ab':>10} {'Tage':>5} {'Trades':>6} {'eff':>5} {'Guete':>7} "
            f"{'DSR':>7} {'Gates':>6}"
        )
        console.print(kopf)
        console.print("  " + "-" * (len(kopf) - 2))

        stufen: list[Historienstufe] = []
        grenzwert, letzter_eintrag = 0.95, None
        for start in starts:
            grenze = pd.Timestamp(start, tz="UTC")
            teil = {
                k: v[v["open_time"] >= grenze].reset_index(drop=True)
                for k, v in gemeinsam.items()
            }
            erster = next(iter(teil.values()))
            if len(erster) < 400:
                continue
            cfgs = configs_fuer(teil)
            bericht, ergebnisse, wert, grenze, eintrag = messen(teil, cfgs)
            if not bericht.windows:
                continue
            if not stufen:
                # Die Schwelle kommt aus dem Gate und nicht aus dem Kopf -
                # dieselbe Regel wie in den Befunden 101, 103 und 109.
                grenzwert, letzter_eintrag = grenze, eintrag
            trades = bericht.all_trades
            beine = [
                [float(t.net_pnl) for t in trades if t.symbol == x] for x in teil
            ]
            bloecke = [[float(x.net_pnl) for x in w.trades] for w in bericht.windows]
            eff = stichprobe_wie_im_gate(trades, beine=beine, bloecke=bloecke)
            stufen.append(
                Historienstufe(
                    von=start,
                    tage=len(erster),
                    trades=len(trades),
                    effektiv=eff.effektiv,
                    guete=eintrag.sharpe_je_trade if eintrag else 0.0,
                    dsr=wert,
                    bestanden=sum(1 for r in ergebnisse.results if r.passed),
                    gesamt=len(ergebnisse.results),
                )
            )
            console.print(f"  {stufen[-1].als_zeile()}")

        ref = stufen[0] if stufen else None
        ziel = None
        if ref is not None and letzter_eintrag is not None:
            bedarf = Stichprobenbedarf(
                guete=ref.guete, versuche=trials, heute=ref.effektiv,
                schiefe=letzter_eintrag.schiefe,
                woelbung=letzter_eintrag.woelbung,
                schwelle=grenzwert,
            )
            ziel = bedarf.noetig()
        kurve = Historienkurve(tuple(stufen), ziel=ziel)
        console.print(f"\n[yellow]{kurve.urteil()}[/]\n")
        console.print(
            f"[dim]Die Vergangenheit ist damit ausgeschoepft: Der gemeinsame "
            f"Bereich beginnt am\n{anfang.date()}, weil dort die zweite Reihe "
            f"beginnt. Fehlende Tage koennen nur aus\nder Zukunft kommen.[/]\n"
        )
        return

    if fenster:
        console.print(
            f"\n[bold]Drei Datenfenster[/] {interval_obj.label}, Spot\n"
            f"  Kandidat   {basis.name}\n"
            f"  Versuche   {trials}\n\n"
            "[dim]Vor dem Lauf festgelegt: Berichtet werden alle drei.[/]\n"
        )

        einzeln = symbole[0]
        lagen = []
        for name, ausschnitt in (
            (" + ".join(symbole) + ", gemeinsamer Bereich", gemeinsam),
            (f"{einzeln} allein, gemeinsamer Bereich", {einzeln: gemeinsam[einzeln]}),
            (f"{einzeln} allein, volle Historie", {einzeln: roh[einzeln]}),
        ):
            configs = configs_fuer(ausschnitt)
            bericht, ergebnisse, wert, _, eintrag = messen(ausschnitt, configs)
            erster = next(iter(ausschnitt.values()))
            lagen.append(
                Fenster(
                    name=name,
                    von=str(erster["open_time"].min().date()),
                    bis=str(erster["open_time"].max().date()),
                    trades=len(bericht.all_trades),
                    guete=eintrag.sharpe_je_trade if eintrag else 0.0,
                    dsr=wert,
                    bestanden=sum(1 for r in ergebnisse.results if r.passed),
                    gesamt=len(ergebnisse.results),
                )
            )
            console.print(
                f"  [bold]{name}[/]\n"
                f"    {lagen[-1].von} .. {lagen[-1].bis}   "
                f"{lagen[-1].trades} Trades   Guete {lagen[-1].guete:.4f}   "
                f"DSR {wert:.4f}   {lagen[-1].bestanden}/{lagen[-1].gesamt} Gates\n"
            )

        lage = Fensterlage(referenz=lagen[0], weitere=tuple(lagen[1:]))
        console.print(f"[yellow]{lage.urteil()}[/]\n")
        for f in lage.weitere:
            console.print(
                f"[dim]  {f.name}: {lage.abstand(f):+.4f} am Deflated Sharpe.[/]"
            )
        console.print()
        return

    console.print(
        f"\n[bold]Kostendecke[/] {' + '.join(symbole)} {interval_obj.label}\n"
        f"  Kandidat   {basis.name}\n"
        f"  Versuche   {trials}\n"
    )

    stufen = []
    for name, kw, hebel in (
        ("Perpetual wie gebaut", {"funding": "0.0001"}, True),
        ("Spot wie gebaut", {}, False),
        ("Spot ohne Slippage", {"rutsch": 0.0}, False),
        ("Spot ohne Gebuehren", {"gebuehr": 0.0}, False),
        ("Spot voellig kostenfrei", {"gebuehr": 0.0, "rutsch": 0.0}, False),
    ):
        configs = configs_fuer(gemeinsam, **kw)
        bericht, ergebnisse, wert, schwelle, eintrag = messen(
            gemeinsam, configs, hebel=hebel
        )
        bestanden = sum(1 for r in ergebnisse.results if r.passed)
        stufen.append((name, wert, eintrag, bestanden, len(ergebnisse.results)))
        console.print(
            f"  {name:<26} DSR {wert:.4f}   "
            f"Guete {(eintrag.sharpe_je_trade if eintrag else 0.0):.4f}   "
            f"{bestanden}/{len(ergebnisse.results)} Gates"
        )

    schwelle_wert = schwelle
    betriebspunkt = next(x for x in stufen if x[0] == "Spot wie gebaut")
    anschlag = next(x for x in stufen if x[0] == "Spot voellig kostenfrei")

    kosten = Deckenwert(
        name="Kosten",
        heute=betriebspunkt[1],
        decke=anschlag[1],
        anschlag="Gebuehren, Slippage und Funding auf null",
    )
    lage = Decke(familien=(kosten,), schwelle=schwelle_wert)
    console.print(f"\n  [bold]{kosten.als_text(schwelle_wert)}[/]")

    # **Die anderen Familien werden hier nicht nachgerechnet, sondern
    # nachgeschlagen.** Ihre Zahlen hier zu wiederholen waere eine zweite
    # Kopie neben der Messung - derselbe Fehler wie in den Befunden 101, 103
    # und 109. Und sie hier ueberhaupt zu zeigen, hat einen zweiten Grund:
    # Beim Schreiben von Befund 111 habe ich "mehr Maerkte" als offene
    # Richtung angekuendigt, obwohl sie seit Befund 27 in genau dieser Liste
    # steht. Ein Register nuetzt nur, wo die Frage gestellt wird.
    verwandt = [
        r for r in GESCHLOSSEN
        if r.name in ("Mehr Maerkte", "Mehr Historie", "Trade-Zahl heben")
    ]
    if verwandt:
        console.print(
            "\n  [dim]Andere Wege zu mehr Beobachtungen - bereits gemessen "
            "und geschlossen:[/]"
        )
        for r in verwandt:
            console.print(f"  [dim]  {r.name:<18} {r.ergebnis:<46} Befund {r.befund}[/]")

    eintrag = betriebspunkt[2]
    if eintrag is not None and eintrag.trades:
        bedarf = Stichprobenbedarf(
            guete=eintrag.sharpe_je_trade,
            versuche=trials,
            heute=eintrag.trades,
            schiefe=eintrag.schiefe,
            woelbung=eintrag.woelbung,
            schwelle=schwelle_wert,
        )
        console.print(f"\n  [bold]In Beobachtungen:[/] {bedarf.urteil()}")

    console.print(f"\n[yellow]{lage.urteil()}[/]\n")
    console.print(
        "[dim]Der Versuchszaehler bleibt unveraendert: Die Strategie ist in "
        "jeder Zeile dieselbe, veraendert werden die Handelskosten.[/]\n"
    )


@app.command()
def regler(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    was: str = typer.Option(
        "vola", "--was",
        help="Welcher Regler: 'vola' (Vola-Ziel, Befund 21) oder 'ziel' "
             "(Gewinnziel in R, Befund 46).",
    ),
    stellungen: str = typer.Option(
        "", "--stellungen",
        help="Stellungen, durch Komma getrennt. Leer = die Leiter aus dem "
             "urspruenglichen Befund, die keinen Versuch kostet.",
    ),
    zaehlerstand: int = typer.Option(
        0, "--zaehlerstand",
        help="Nur zum Vergleich mit einem alten Befund: rechnet den Deflated "
             "Sharpe so, als staende der Versuchszaehler dort. Der echte "
             "Stand bleibt massgeblich.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Faehrt einen Regler an beiden Betriebspunkten ab (Befunde 128, 129).

    Zwei Befunde haben je einen Regler abgefahren und keine Stellung gefunden,
    an der alles haelt - beide am **Perpetual**-Punkt:

        --was vola   Befund 21, Vola-Ziel in Prozent
        --was ziel   Befund 46, Gewinnziel in Vielfachen des Risikos

    Massgeblich ist seit Befund 108 der **Spot**-Punkt. Dieser Befehl misst
    beide Leitern neu - auch die alte - und stellt sie nebeneinander. Die alte
    Tabelle abzuschreiben waere falsch: Zwischen damals und heute stehen
    Korrekturen am Code, die die Leiter ebenfalls verschieben, und ein
    Vergleich wuerde sie dem Betriebspunkt zuschreiben (Befund 128).

    Berichtet wird die **ganze Leiter**, nicht die beste Stellung. Wer sich
    nach den Zahlen eine aussucht, hat gesucht und nicht geprueft - deshalb
    kennt ``research/regler.py`` auch keine Methode dafuer.

    **Kostet keinen Versuch**, solange die Stellungen aus dem urspruenglichen
    Befund stehen bleiben: Sie sind seit damals im Zaehler, gemessen werden sie
    unter anderen Handelsbedingungen. Wer neue Stellungen dazunimmt, rechnet
    neue Kandidaten - und die zaehlen.
    """
    from decimal import Decimal

    from backtest.costs import FundingSchedule
    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import evaluate_gates
    from research.regler import (
        ARTEN,
        Klaerungskosten,
        Reglerleiter,
        Reglervergleich,
        Stellung,
    )
    from research.seeds import spitzenkandidat
    from research.stand import GESCHLOSSEN
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    if was not in ARTEN:
        console.print(
            f"[red]--was kennt nur {', '.join(ARTEN)} - nicht '{was}'.[/]"
        )
        raise typer.Exit(2)
    art = ARTEN[was]
    try:
        werte = sorted(
            float(x.strip()) for x in (stellungen or art.leiter).split(",") if x.strip()
        )
    except ValueError:
        console.print("[red]--stellungen erwartet Zahlen, durch Komma getrennt.[/]")
        raise typer.Exit(2) from None
    if not werte:
        console.print("[red]Ohne Stellungen gibt es nichts zu messen.[/]")
        raise typer.Exit(2)
    eigene = bool(stellungen.strip())

    store = CandleStore(settings.paths.data_store)
    roh = {}
    for symbol in symbole:
        frame = store.read(symbol, interval_obj)
        if frame.empty:
            console.print(f"[red]Keine Kerzen fuer {symbol} {interval_obj.label}.[/]")
            raise typer.Exit(2)
        roh[symbol] = frame
    frames = common_range(roh)
    echt = load_trials(Path(settings.paths.state) / "trials.json")
    # Der Zaehlerstand ist **nie** eine Stellschraube fuer ein besseres
    # Ergebnis - er darf nur gesetzt werden, um eine alte Tabelle
    # nachzustellen, und das Ergebnis wird als Rekonstruktion ausgewiesen.
    if zaehlerstand < 0:
        console.print("[red]--zaehlerstand kann nicht negativ sein.[/]")
        raise typer.Exit(2)
    nachgestellt = zaehlerstand > 0 and zaehlerstand != echt
    trials = zaehlerstand or echt
    basis = spitzenkandidat()
    erster = next(iter(frames.values()))

    def configs_fuer(*, spot: bool) -> dict:
        aus = {}
        for x in symbole:
            grund = BacktestConfig(
                instrument=_fallback_instrument(_bybit_kontrakt(x)),
                risk=settings.risk, initial_equity=Decimal("500"),
                enforce_risk_limits=True,
                kalender=_terminkalender(settings) or None,
            )
            aus[x] = BacktestConfig(
                instrument=grund.instrument, risk=grund.risk, costs=grund.costs,
                funding=FundingSchedule(
                    default_rate=Decimal("0") if spot else grund.funding.default_rate
                ),
                initial_equity=grund.initial_equity, enforce_risk_limits=True,
                allow_shorts=grund.allow_shorts,
                entry_expiry_bars=grund.entry_expiry_bars,
                max_hold_bars=grund.max_hold_bars, kalender=grund.kalender,
            )
        return aus

    def leiter(name: str, *, spot: bool) -> Reglerleiter:
        configs = configs_fuer(spot=spot)
        # Der Spot-Punkt ist "kein Funding **und** kein Hebel" (Befund 108) -
        # das Funding sitzt in den Configs, der Hebel im Bauplan.
        grundgenom = (
            basis.model_copy(
                update={"sizing": basis.sizing.model_copy(update={"fraction": 1.0})}
            )
            if spot
            else basis
        )
        gemessen: list[Stellung] = []
        for ziel in werte:
            genom = art.setzen(grundgenom, ziel)
            bericht = run_portfolio_walkforward(
                frames, lambda g=genom: compile_genome(g), configs
            )
            if not bericht.windows:
                continue
            ergebnisse = evaluate_gates(
                genom, bericht, erster, configs[symbole[0]],
                trials_so_far=trials, frames=frames, configs=configs,
            )
            k = bericht.combined
            wert = next(
                (r for r in ergebnisse.results if r.name == "Deflated Sharpe"), None
            )
            gemessen.append(
                Stellung(
                    wert=ziel,
                    trades=len(bericht.all_trades),
                    rendite=float(k.cagr_pct),
                    rueckgang=float(k.max_drawdown_pct),
                    bestanden=sum(1 for r in ergebnisse.results if r.passed),
                    gesamt=len(ergebnisse.results),
                    offen=tuple(r.name for r in ergebnisse.results if not r.passed),
                    dsr=float(wert.value) if wert is not None else None,
                )
            )
        return Reglerleiter(name, tuple(gemessen))

    console.print(
        f"\n[bold]DER {art.name.upper()}-REGLER AN BEIDEN BETRIEBSPUNKTEN[/]\n"
    )
    console.print(
        f"[dim]Befund {art.befund} hat diesen Regler am Perpetual-Punkt "
        f"abgefahren. Massgeblich ist\nseit Befund 108 der Spot-Punkt. "
        f"Berichtet wird die ganze Leiter, nicht die beste\nStellung.[/]\n"
    )
    if eigene:
        console.print(
            f"[yellow]Eigene Stellungen: Jede, die nicht in Befund "
            f"{art.befund} steht, ist ein neuer\nKandidat und zaehlt als "
            f"Versuch.[/]\n"
        )
    if nachgestellt:
        console.print(
            f"[red bold]REKONSTRUKTION, kein aktueller Stand.[/] Gerechnet mit "
            f"{trials} Versuchen\nstatt der tatsaechlichen {echt} - nur, um "
            f"eine alte Tabelle vergleichbar zu machen.\nJede Zahl unten ist "
            f"damit besser, als sie heute waere.\n"
        )

    beide = []
    for etikett, spot in (("Perpetual", False), ("Spot", True)):
        gefunden = leiter(f"{art.name} ({etikett})", spot=spot)
        beide.append(gefunden)
        console.print(f"[bold]{etikett}[/]")
        console.print(
            f"  {art.einheit:>6} {'Trades':>6} {'p.a.':>8} {'MaxDD':>8} "
            f"{'DSR':>7} {'Gates':>7}  offen"
        )
        console.print("  " + "-" * 78)
        for s in gefunden.sortiert:
            console.print(f"  {s.als_zeile()}")
        console.print()

    alt, neu = beide
    for gefunden in beide:
        console.print(f"[yellow]{gefunden.urteil()}[/]\n")

    vergleich = Reglervergleich(alt=alt, neu=neu)
    console.print("[bold]Was der Betriebspunkt aendert[/]")
    console.print(f"  {vergleich.urteil()}")
    gesamt = neu.sortiert[0].gesamt if neu.stellungen else 0
    for wert, vorher, nachher in vergleich.verschoben():
        console.print(
            f"    {wert:>6.1f}   {vorher}/{gesamt} -> {nachher}/{gesamt}"
        )
    console.print()

    # **Traegt der Regler ueberhaupt?** - die Rechnung aus Befund 21, jetzt
    # gerechnet statt erzaehlt. Zwei Regler koennen aus entgegengesetzten
    # Gruenden zu sein: einer, weil er den Wert kaum bewegt, der andere, weil
    # er ihn weit bewegt und sein Hoechstwert schon besetzt ist.
    hub, rest = neu.hub(), neu.reserve()
    if hub is not None and rest is not None:
        console.print("[bold]Wie weit der Regler traegt[/]")
        console.print(
            f"  Hub ueber den ganzen Weg  {hub:>8.4f}\n"
            f"  Reserve bis zur Schwelle  {rest:>8.4f}"
        )
        console.print(
            "  [dim]" + (
                "Der Weg reicht - aber nur nach unten; der Hoechstwert steht "
                "unten."
                if neu.traegt_der_regler()
                else "Der Regler muesste weiter tragen, als er ueberhaupt "
                     "traegt (Befund 21)."
            ) + "[/]\n"
        )

    # Der einzige zulaessige Vergleich: gegen die Stellung, auf der der
    # Kandidat ohnehin sitzt. Sie stand vor der Messung fest (Befund 128).
    referenz = art.lesen(basis)
    besser = neu.schlaegt_referenz(referenz)
    anker = next((s for s in neu.stellungen if s.wert == referenz), None)
    if anker is not None and anker.dsr is not None:
        console.print(
            f"[bold]Gegen die Stellung, auf der der Kandidat sitzt "
            f"({referenz:g} {art.einheit})[/]"
        )
        if not besser:
            console.print(
                f"  Keine Sprosse schlaegt sie in jeder Hinsicht - "
                f"{anker.dsr:.4f}, {anker.bestanden}/{anker.gesamt} ist der "
                f"Hoechstwert der Leiter.\n"
            )
        else:
            for s in besser:
                console.print(
                    f"    {s.wert:>6.1f}   {s.dsr:.4f} statt {anker.dsr:.4f} "
                    f"({s.dsr - anker.dsr:+.4f}), {s.bestanden}/{s.gesamt}"
                )
            # Gemessen wird gegen die Luecke, die **von der Referenz aus**
            # offen ist - nicht gegen die Reserve der besten Sprosse. Die
            # waere der kleinere Nenner und wuerde den Schritt groesser
            # aussehen lassen, als er ist.
            luecke = 0.95 - anker.dsr
            spitze = max(s.dsr - anker.dsr for s in besser)
            if luecke > 0:
                console.print(
                    f"  [dim]Der beste Schritt schliesst {spitze / luecke:.0%} "
                    f"der Luecke ({spitze:.4f} von {luecke:.4f}). Kein Weg zur "
                    f"Zulassung,\n  sondern eine Zahl fuer den Bericht - und "
                    f"die Entscheidung gehoert dem Auftraggeber.[/]\n"
                )

    # Was das Nachmessen der Luecke kosten wuerde.
    #
    # Gemessen und nicht geschaetzt: derselbe Kandidat, derselbe Lauf, nur ein
    # hoeherer Zaehlerstand. Das ist genau der Preis, den zusaetzliche
    # Stellungen kosten, **bevor** eine davon ein Ergebnis liefert.
    streit = [k for k in neu.konflikte() if k.benachbart]
    if streit and not neu.klaerung_lohnt():
        k = streit[0]
        schritte = 5
        configs = configs_fuer(spot=True)
        genom = basis.model_copy(
            update={"sizing": basis.sizing.model_copy(update={"fraction": 1.0})}
        )
        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genom), configs
        )
        jetzt, danach = (
            float(
                next(
                    r
                    for r in evaluate_gates(
                        genom, bericht, erster, configs[symbole[0]],
                        trials_so_far=n, frames=frames, configs=configs,
                    ).results
                    if r.name == "Deflated Sharpe"
                ).value
            )
            for n in (trials, trials + schritte)
        )
        kosten = Klaerungskosten(
            stellungen=schritte, versuche_jetzt=trials,
            dsr_jetzt=jetzt, dsr_danach=danach,
        )
        console.print("[bold]Was die Luecke zu klaeren kostet[/]")
        console.print(
            f"  Zwischen {k.letzte_unten:.1f} und {k.erste_oben:.1f} ist nichts "
            f"gemessen.\n  {kosten.als_zeile()}"
        )
        console.print(
            f"  [dim]Und es wuerde nichts aendern: {', '.join(neu.immer_offen())} "
            f"steht an jeder\n  Stellung offen. Feiner messen senkt den Wert, "
            f"statt ihn zu heben.[/]\n"
        )

    verwandt = [r for r in GESCHLOSSEN if r.befund == art.befund]
    if verwandt:
        console.print("[dim]Im Register der geschlossenen Wege:[/]")
        for r in verwandt:
            console.print(f"  [dim]{r.name:<18} {r.ergebnis:<46} Befund {r.befund}[/]")
    console.print(
        f"\n[dim]Der Versuchszaehler bleibt unveraendert, solange die "
        f"{len(art.stellungen())} Stellungen aus\nBefund {art.befund} stehen: "
        f"dieselben Kandidaten, andere Handelsbedingungen.[/]\n"
        if not eigene
        else "\n[dim]Diese Leiter weicht von Befund "
        f"{art.befund} ab - die abweichenden Stellungen\nsind neue Kandidaten "
        "und gehoeren in den Zaehler.[/]\n"
    )


@app.command()
def register(
    alle: bool = typer.Option(
        False, "--alle",
        help="Auch die Eintraege zeigen, zu denen nichts Spaeteres steht.",
    ),
) -> None:
    """Zeigt geschlossene Richtungen, bei denen eine Nachmessung stehen koennte.

    Befund 130: Der Eintrag *"Vola-Ziel ... Befund 21"* zeigte auf eine
    Tabelle, die Befund 23 zwei Befunde spaeter ersetzt hatte. Zwei Laeufe
    haben dort nachgeschlagen und den Unterschied zum heutigen Stand falschen
    Ursachen zugeschrieben - beide Male, ohne dass etwas auffaellig gewesen
    waere, denn die Fundstelle stimmte ja.

    Dieser Befehl sucht die andere Haelfte: Wo im Laborbuch wird eine
    geschlossene Richtung **nach** ihrer massgeblichen Fundstelle noch
    erwaehnt?

    **Er entscheidet nichts.** Erwaehnt zu werden ist nicht dasselbe wie
    nachgemessen zu werden, und der Unterschied steht im Text, nicht in der
    Trefferzahl. Wer einen Eintrag nachzieht, hat den Befund gelesen - so wie
    Befund 118 gezeigt hat, was eine ungeprueft uebernommene Textsuche
    anrichtet.
    """
    from research.nachmessung import spuren
    from research.stand import GESCHLOSSEN

    pfad = Path("strategies/BEFUND.md")
    if not pfad.exists():
        console.print(f"[red]{pfad} nicht gefunden.[/]")
        raise typer.Exit(2)
    gefunden, ohne = spuren(pfad.read_text(encoding="utf-8"), GESCHLOSSEN)

    console.print("\n[bold]GESCHLOSSENE RICHTUNGEN: STEHT DA SPAETER NOCH WAS?[/]\n")
    nachgezogen = [s for s in gefunden if s.nachgezogen]
    console.print(
        f"[dim]{len(gefunden)} Eintraege durchsucht, davon {len(nachgezogen)} "
        f"mit bekannter Nachmessung.\nDie Treffer unten sind Verdachtsfaelle "
        f"und keine Befunde.[/]\n"
    )

    verdaechtig = [s for s in gefunden if s.offen]
    for s in verdaechtig:
        marke = "[green]+[/]" if s.nachgezogen else " "
        stelle = (
            f"Nr. {s.massgeblich} (zuerst {s.fundstelle})"
            if s.nachgezogen
            else f"Nr. {s.fundstelle}"
        )
        namen = ", ".join(f"{n} ({t}x)" for n, t in s.offen[:6])
        console.print(f"{marke} {s.name:<30} {stelle:<24} spaeter: {namen}")

    ruhig = [s for s in gefunden if not s.offen]
    if ruhig:
        console.print(
            f"\n[dim]{len(ruhig)} Eintraege ohne spaetere Erwaehnung"
            + (":" if alle else ".")
            + "[/]"
        )
        if alle:
            for s in ruhig:
                console.print(f"  [dim]{s.name:<30} Nr. {s.massgeblich}[/]")

    if ohne:
        console.print(
            f"\n[yellow]Ohne Suchbegriffe und damit ungeprueft "
            f"({len(ohne)}):[/] {', '.join(ohne)}"
        )
        console.print(
            "[dim]  Eine sichtbare Luecke ist besser als ein stiller "
            "Fehlalarm - Begriffe stehen\n  in research/nachmessung.BEGRIFFE.[/]"
        )
    console.print(
        f"\n[dim]{len(verdaechtig)} Eintraege haben spaetere Erwaehnungen. Jede "
        f"davon ist zu lesen,\nbevor jemand ihre Zahlen als Stand ausgibt.[/]\n"
    )


@app.command()
def paare(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    vola_ziel: float = typer.Option(19.3, "--vola-ziel"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Jedes Katalog-Genom als Verbund mit dem Bestand - **gemessen**.

    Das Gegenstueck zu ``cli anwaerter``: Der laesst dieselben Genome laufen,
    haelt sie aber gegen die **Formel** aus Befund 74 und wirft die Berichte
    weg. Hier wird der Verbund tatsaechlich gebaut - die Vereinigung der
    Trades, mit der Einteilung des Gates.

    Geordnet wird nach der **Luecke**, nicht nach der Guete: Die Latte steigt
    mit der Stichprobe (Befund 141), zwei Paare mit verschiedenem ``n`` treten
    also gegen verschiedene Latten an.

    **Kostet keinen Versuch** - solange niemand eines der Paare uebernimmt.
    Wer das tut, hat eine Auswahl ueber alle getroffen; der Bericht sagt am
    Ende, was das kostet.
    """
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.entdopplung import entdoppele
    from research.paarkarte import Paar, Paarfeld
    from research.seeds import VORGESEHEN, load_seeds, spitzenkandidat
    from research.suchbudget import Kandidat
    from research.verbund import baue, noetige_guete
    from strategy.compiler import compile_genome
    from strategy.genome import SizingSpec

    _configure_logging(verbose)
    settings = get_settings()
    versuche = load_trials(Path(settings.paths.state) / "trials.json")
    interval_obj = Interval(intervall)
    symbole = [s.strip() for s in maerkte.split(",") if s.strip()]
    frames, configs, spanne = _korb_daten(symbole, interval_obj, settings)

    def lauf(genome):
        angepasst = genome.model_copy(
            update={
                "sizing": SizingSpec(
                    kind="vola_ziel", fraction=3.0,
                    target_vol_pct=vola_ziel, vol_period=30,
                )
            }
        )
        return run_portfolio_walkforward(
            frames, lambda g=angepasst: compile_genome(g), configs
        )

    bestand = spitzenkandidat()
    spitze = lauf(bestand)
    allein = baue([(bestand.name, spitze)], versuche=versuche)
    allein_k = Kandidat.aus_trades("x", allein.trades)
    if allein_k is None or allein_k.sharpe_je_trade <= 0:
        console.print("[red]Der Bestand liefert keine auswertbaren Trades.[/]")
        raise typer.Exit(2)
    allein_n = allein.stichprobe.effektiv
    allein_g = allein_k.sharpe_je_trade * allein_n**0.5
    allein_ziel = noetige_guete(allein_n, versuche) or 0.0

    console.print(
        f"\n[bold]Gemessene Paare[/] auf {' + '.join(symbole)} "
        f"{interval_obj.label}\n"
        f"  Bestand    '{bestand.name}' allein: n = {allein_n}, "
        f"Guete {allein_g:.3f}, noetig {allein_ziel:.3f}\n"
        f"  Historie   {spanne} Tage, {versuche} Versuche bisher\n"
    )

    # Erst alle Beine, dann entdoppeln - dasselbe Genom steht unter mehreren
    # Namen im Katalog, und jede Dublette blaehte die Auswahl auf.
    passende = [g for g, iv in VORGESEHEN.items() if iv == interval_obj.value]
    roh: dict[str, list] = {bestand.name: list(spitze.all_trades)}
    berichte = {bestand.name: spitze}
    for gen in sorted(passende):
        for genome in load_seeds(gen):
            if genome.name in roh:
                continue
            bericht = lauf(genome)
            trades = list(bericht.all_trades)
            if len(trades) < 10 or not bericht.windows:
                continue
            roh[genome.name] = trades
            berichte[genome.name] = bericht

    namen = [n for n in entdoppele(roh).laeufe if n != bestand.name]
    console.print(
        f"  Katalog    {len(roh) - 1} Genome, nach Entdopplung {len(namen)}\n"
    )

    gemessen = []
    for name in namen:
        lage = baue([(bestand.name, spitze), (name, berichte[name])],
                    versuche=versuche)
        k = Kandidat.aus_trades("x", lage.trades)
        einzeln = Kandidat.aus_trades(name, roh[name])
        if k is None or einzeln is None or k.sharpe_je_trade <= 0:
            continue
        n = lage.stichprobe.effektiv
        gemessen.append(Paar(
            name=name, partner_trades=len(roh[name]),
            partner_sharpe=einzeln.sharpe_je_trade,
            roh=len(lage.trades), effektiv=n,
            guete=k.sharpe_je_trade * n**0.5,
            noetig=noetige_guete(n, versuche) or 0.0,
        ))

    feld = Paarfeld(bestand.name, allein_g, allein_ziel, tuple(gemessen))
    kopf = (f"  {'Partner':<32} {'P_n':>4} {'P_sr':>6} {'roh':>4} {'n':>4} "
            f"{'halt':>5} {'Guete':>6} {'noetig':>7} {'fehlt':>6}")
    console.print(kopf)
    console.print("  " + "-" * (len(kopf) - 2))
    for p in feld.geordnet:
        marke = "  [green]<== ueber der Latte[/]" if p.reicht else ""
        console.print(
            f"  {p.name[:32]:<32} {p.partner_trades:>4} "
            f"{p.partner_sharpe:>6.3f} {p.roh:>4} {p.effektiv:>4} "
            f"{p.behaltequote:>5.2f} {p.guete:>6.3f} {p.noetig:>7.3f} "
            f"{p.luecke:>6.3f}{marke}"
        )

    farbe = "green" if feld.erreichen else "yellow"
    console.print(f"\n[{farbe}]{feld.urteil()}[/]\n")



@app.command()
def vorratsdecke(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--maerkte", "-m",
        help="Symbole, durch Komma getrennt.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Was der Vorrat hergibt - und ob das je reichen kann.

    Befund 75 hat die Kopplung zwischen Trade-Zahl und Qualitaet gemessen und
    als Eigenschaft *des Vorrats* bezeichnet. Faellt die Qualitaet mit der
    Menge, hat ``SR * sqrt(n)`` ein Maximum - und wenn das unter der Latte
    liegt, kann in diesem Vorrat nichts bestehen.

    Gefahren wird der **ganze** Katalog der Generationen, die zu dieser
    Kerzenlaenge gehoeren, am Spot-Punkt. Berichtet wird jede Regel, auch die
    ohne einen einzigen Trade.

    **Kostet keinen Versuch.** Diese Genome stehen laengst im Katalog und
    waren gezaehlt, als sie entstanden; nachgemessen wird ein vorhandener
    Vorrat. Ausgewaehlt wird nichts - wer eine davon weiterverfolgt, hat eine
    Auswahl ueber den Katalog getroffen und muss sie zaehlen.
    """
    from backtest.portfolio_walkforward import (
        common_range,
        run_portfolio_walkforward,
    )
    from research.admission import load_trials
    from research.gates import stichprobe_wie_im_gate
    from research.randschnitt import ohne_zensierte
    from research.seeds import GENERATIONS, passt_zum_intervall
    from research.suchbudget import Kandidat
    from research.verbund import noetige_guete
    from research.vorratsdecke import (
        Punkt,
        baue,
        familienurteil,
        preisurteil,
        traegt_eine_familie,
        urteil,
    )
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]
    versuche = load_trials(Path(settings.paths.state) / "trials.json")
    interval_obj = Interval(intervall)
    store = CandleStore(settings.paths.data_store)
    frames = common_range({x: store.read(x, interval_obj) for x in symbole})
    configs = _spotconfigs(symbole, settings)

    console.print(
        f"\n[bold]Vorratsdecke[/] {' + '.join(symbole)} {interval_obj.label}, "
        f"Spot-Punkt, Versuchsstand {versuche}\n"
    )
    punkte: list[Punkt] = []
    nach_familie: dict[str, list[Punkt]] = {}
    ohne_latte: list[tuple[str, int]] = []
    stumm = 0
    gesehen: set[tuple[int, float]] = set()
    for gen, liste in sorted(GENERATIONS.items()):
        if not passt_zum_intervall(gen, intervall):
            continue
        for bauen in liste:
            genom = _ohne_hebel(bauen())
            bericht = run_portfolio_walkforward(
                frames, lambda g=genom: compile_genome(g), configs
            )
            gehandelt = ohne_zensierte(bericht)
            kandidat = Kandidat.aus_trades(genom.name, gehandelt.all_trades)
            if kandidat is None or not gehandelt.windows:
                stumm += 1
                console.print(
                    f"  [dim]{genom.name[:44]:<44} "
                    f"{len(gehandelt.all_trades):>4} Trades - kein Kandidat[/]"
                )
                continue
            stichprobe = stichprobe_wie_im_gate(
                gehandelt.all_trades,
                beine=getattr(bericht, "beine", None),
                bloecke=[
                    [float(x.net_pnl) for x in w.trades] for w in gehandelt.windows
                ],
            )
            kennung = (stichprobe.effektiv, round(kandidat.sharpe_je_trade, 6))
            if kennung in gesehen:
                # Dieselbe Regel unter einem anderen Namen. Sie mitzuzaehlen
                # hiesse, die Zahl der Belege zu erfinden - genau der Fehler,
                # gegen den die effektive Stichprobe im Gate steht.
                console.print(
                    f"  [dim]{genom.name[:44]:<44} identisch mit einer "
                    f"frueheren Regel[/]"
                )
                continue
            gesehen.add(kennung)
            # **Nur Regeln, fuer die es ueberhaupt eine Latte gibt.** Wo
            # ``noetige_guete`` nichts liefert, ist die Stichprobe so klein,
            # dass das Gate dort gar nicht urteilt - ein solcher Punkt kann
            # zu der Frage "reicht das je?" nichts beitragen, haette an der
            # Kante des Bereichs aber grossen Hebel auf die Steigung. Die
            # Regel steht hier, damit sie vor der Messung feststeht und nicht
            # danach.
            if noetige_guete(stichprobe.effektiv, versuche) is None:
                ohne_latte.append((genom.name, stichprobe.effektiv))
                continue
            punkt = Punkt(
                genom.name, stichprobe.effektiv, kandidat.sharpe_je_trade
            )
            punkte.append(punkt)
            nach_familie.setdefault(_familie(genom), []).append(punkt)

    if len(punkte) < 3:
        console.print(
            f"\n[yellow]Nur {len(punkte)} verschiedene Regeln handeln auf "
            f"{interval_obj.label} - daraus laesst sich keine Gerade legen.[/]"
        )
        raise typer.Exit(2)

    punkte.sort(key=lambda p: -p.guete)
    console.print(
        f"\n{'Regel':<44}{'n_eff':>7}{'SR/Trade':>10}{'Guete':>8}{'noetig':>8}"
    )
    for p in punkte:
        noetig = noetige_guete(p.n_eff, versuche)
        console.print(
            f"{p.name[:44]:<44}{p.n_eff:>7}{p.sharpe_je_trade:>10.4f}"
            f"{p.guete:>8.3f}"
            + ("        -" if noetig is None else f"{noetig:>8.3f}")
        )

    decke = baue(punkte)
    console.print(
        f"\n[dim]{stumm} Genome handeln auf {interval_obj.label} nicht und "
        f"stehen oben ohne Zahlen.[/]"
    )
    for name, n in ohne_latte:
        console.print(
            f"[dim]{name} (n_eff {n}) bleibt draussen - bei dieser Stichprobe "
            f"gibt es keine Latte.[/]"
        )
    console.print()
    console.print(urteil(decke, lambda n: noetige_guete(n, versuche)))

    # **Worauf die Kopplung steht.** Befund 168 hat r = -0,714 ueber den
    # ganzen Vorrat gemeldet; Befund 169 hat nachgesehen, wer das traegt.
    aufteilung = traegt_eine_familie(nach_familie)
    if aufteilung is not None:
        console.print()
        console.print(f"[yellow]{familienurteil(aufteilung)}[/]")
        console.print(
            "\n[dim]Familien nach Einstiegsindikator: "
            + ", ".join(
                f"{f} {len(ps)}"
                for f, ps in sorted(nach_familie.items(), key=lambda x: -len(x[1]))
            )
            + "[/]"
        )

    # **Wo der Bestand in seinem eigenen Vorrat steht.** Der zweite Weg zur
    # selben Aussage wie der Deflated Sharpe - und ein unabhaengiger: Der
    # eine sieht die Verteilung der Trades, dieser die Lage des Kandidaten
    # in seiner Grundgesamtheit.
    from research.referenz import SPOTPUNKT

    if decke.tragfaehig:
        rest = decke.rest(SPOTPUNKT.effektiv, SPOTPUNKT.guete)
        erwartet = decke.erwartetes_maximum(versuche)
        console.print(
            f"\n[bold]Wo der Bestand darin steht[/]\n"
            f"  n_eff {SPOTPUNKT.effektiv}, SR {SPOTPUNKT.guete:.4f} - "
            f"die Gerade sagt {decke.vorhersage(SPOTPUNKT.effektiv):.4f}\n"
            f"  Vorsprung {rest:+.2f} Reststreuungen\n"
            f"  Reine Auswahl aus {versuche} Versuchen erzeugt rund "
            f"{erwartet:.2f}\n"
        )
        console.print(
            "[yellow]Der Vorsprung ist kleiner als das, was Auswahl bei "
            "diesem Versuchsstand\nohnehin erzeugt.[/] Das ist kein Beweis "
            "gegen den Kandidaten - aber es ist\ndieselbe Aussage, die der "
            "Deflated Sharpe aus einer anderen Richtung macht.\n"
            "[dim]Naeherung: sqrt(2 ln k) fuer die Standardnormale, "
            "normalverteilte Reste und\naustauschbare Ziehungen "
            "unterstellt. Ein Groessenvergleich, kein Test.[/]"
            if rest < erwartet
            else
            "[green]Der Vorsprung ist groesser als das, was Auswahl bei "
            "diesem Versuchsstand erzeugt.[/]"
        )

        # **Was die Menge kostet** (Befund 179). Befund 178 hat das Mengentor
        # geoeffnet - dieselbe Qualitaet bei groesserer Stichprobe -, und es
        # steht unter "bei unveraenderter Qualitaet". In einem gekoppelten
        # Vorrat ist das keine freie Wahl, und diese Zeile sagt, was daraus
        # wird.
        from research.suchbudget import Budget

        budget = Budget(versuche=versuche)
        console.print()
        console.print(
            preisurteil(
                decke,
                budget.noetig_bei,
                versuche=versuche,
                bestand=rest,
            )
        )


@app.command()
def holdout(
    entwicklung: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP", "--entwicklung",
        help="Maerkte, auf denen der Kandidat entstanden ist.",
    ),
    pruefung: str = typer.Option(
        "LTCUSD_BITSTAMP,XRPUSD_BITSTAMP", "--holdout",
        help="Maerkte, die bei der Entwicklung keine Rolle gespielt haben.",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Traegt die Regel dort, wo sie nie ausgewaehlt wurde?

    Jeder Markt **einzeln**, der Kandidat unveraendert. Das ist etwas anderes
    als die Befunde 27 und 133: Dort kamen LTC und XRP zum Portfolio dazu und
    verduennten die Qualitaet - hier laufen sie allein, als Probe.

    Berichtet wird beides: was der Holdout haelt, und was diese Messung
    **nicht** trennt (Korrelation der Maerkte, Marktrichtung).

    **Kostet keinen Versuch**: dieselbe Regel, andere Daten, keine Auswahl.
    """
    import numpy as np

    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.admission import load_trials
    from research.gates import stichprobe_wie_im_gate
    from research.holdout import ENTWICKLUNG, HOLDOUT, Holdoutbild, Marktbefund
    from research.randschnitt import ohne_zensierte
    from research.seeds import spitzenkandidat
    from research.suchbudget import Kandidat
    from research.verbund import noetige_guete
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    versuche = load_trials(Path(settings.paths.state) / "trials.json")
    interval_obj = Interval(intervall)
    store = CandleStore(settings.paths.data_store)
    genome = _ohne_hebel(spitzenkandidat())

    aufgaben = [(x.strip(), ENTWICKLUNG) for x in entwicklung.split(",") if x.strip()]
    aufgaben += [(x.strip(), HOLDOUT) for x in pruefung.split(",") if x.strip()]

    console.print(
        f"\n[bold]Holdout[/] {genome.name}, {interval_obj.label}, Spot-Punkt, "
        f"Versuchsstand {versuche}\n"
    )
    console.print(
        f"{'Markt':<10}{'Rolle':<13}{'Trades':>8}{'n_eff':>7}"
        f"{'SR/Trade':>10}{'Guete':>8}{'noetig':>8}"
    )
    befunde: list[Marktbefund] = []
    reihen: dict[str, object] = {}
    for symbol, rolle in aufgaben:
        rahmen = store.read(symbol, interval_obj)
        reihen[symbol] = rahmen
        bericht = run_portfolio_walkforward(
            {symbol: rahmen},
            lambda: compile_genome(genome),
            _spotconfigs([symbol], settings),
        )
        gehandelt = ohne_zensierte(bericht)
        kandidat = Kandidat.aus_trades(symbol, gehandelt.all_trades)
        if kandidat is None or not gehandelt.windows:
            console.print(
                f"[dim]{symbol[:9]:<10}{rolle:<13}"
                f"{len(gehandelt.all_trades):>8}   kein Kandidat[/]"
            )
            continue
        st = stichprobe_wie_im_gate(
            gehandelt.all_trades,
            beine=getattr(bericht, "beine", None),
            bloecke=[
                [float(x.net_pnl) for x in w.trades] for w in gehandelt.windows
            ],
        )
        befund = Marktbefund(
            symbol, rolle, len(gehandelt.all_trades), st.effektiv,
            kandidat.sharpe_je_trade,
        )
        befunde.append(befund)
        noetig = noetige_guete(st.effektiv, versuche)
        console.print(
            f"{symbol[:9]:<10}{rolle:<13}{befund.trades:>8}{befund.n_eff:>7}"
            f"{befund.sharpe_je_trade:>10.4f}{befund.guete:>8.3f}"
            + ("       -" if noetig is None else f"{noetig:>8.3f}")
        )

    # **Die Korrelation gehoert dazu, nicht daneben.** Ein Holdout auf
    # Maerkten, die mit den Entwicklungsmaerkten laufen, ist schwaecher als
    # sein Name - und das darf der Leser nicht selbst herausfinden muessen.
    korrelation = None
    entw = [b.symbol for b in befunde if b.rolle == ENTWICKLUNG]
    hold = [b.symbol for b in befunde if b.rolle == HOLDOUT]
    if entw and hold:
        renditen = {}
        for symbol, rahmen in reihen.items():
            reihe = rahmen[["open_time", "close"]].copy()
            reihe["close"] = reihe["close"].astype(float)
            renditen[symbol] = np.log(
                reihe.set_index("open_time")["close"]
            ).diff()
        import pandas as pd

        tabelle = pd.DataFrame(renditen).dropna()
        paare = [tabelle[a].corr(tabelle[b]) for a in hold for b in entw]
        if paare:
            korrelation = float(sum(paare) / len(paare))
            console.print(
                f"\n[dim]{len(tabelle)} gemeinsame Balken; Korrelation je "
                f"Paar: " + ", ".join(f"{v:.3f}" for v in paare) + "[/]"
            )

    console.print()
    console.print(Holdoutbild(tuple(befunde), korrelation).urteil())


@app.command()
def zufallseinstieg(
    maerkte: str = typer.Option(
        "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP,LTCUSD_BITSTAMP,XRPUSD_BITSTAMP",
        "--maerkte", "-m",
    ),
    intervall: str = typer.Option("D", "--intervall", "-i"),
    ziehungen: int = typer.Option(2000, "--ziehungen"),
    saat: int = typer.Option(20260902, "--saat"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Schlaegt das Timing den Zufall mit gleicher Haltedauer?

    Befund 174 hat gemessen, dass der Holdout 41 % des Vorteils haelt, und
    ausdruecklich offengelassen, ob das Koennen ist oder Marktrichtung. Diese
    Probe trennt es: gleiche Haltedauern, zufaellige Einstiege, derselbe
    Zeitraum.

    **Nicht zu verwechseln mit `cli nullprobe`**: Der mischt die Renditen und
    prueft die Maschine. Hier bleibt die Reihe unangetastet, und geprueft wird
    die Regel.

    Verglichen wird die **prozentuale Rendite je Trade** - sie streift
    Positionsgroesse und Kosten auf beiden Seiten gleich ab.

    **Kostet keinen Versuch**: dieselbe Regel, keine Auswahl.
    """
    import numpy as np
    import pandas as pd

    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from research.holdout import ENTWICKLUNG, HOLDOUT
    from research.randschnitt import ohne_zensierte
    from research.seeds import spitzenkandidat
    from research.zufallseinstieg import Marktprobe, Zufallsbild, zufallsverteilung
    from strategy.compiler import compile_genome

    _configure_logging(verbose)
    settings = get_settings()
    interval_obj = Interval(intervall)
    store = CandleStore(settings.paths.data_store)
    genome = _ohne_hebel(spitzenkandidat())
    rng = np.random.default_rng(saat)
    symbole = [x.strip() for x in maerkte.split(",") if x.strip()]

    console.print(
        f"\n[bold]Zufallseinstieg[/] {genome.name}, {interval_obj.label}, "
        f"{ziehungen} Ziehungen, Saat {saat}\n"
    )
    console.print(
        f"{'Markt':<10}{'Rolle':<13}{'Trades':>7}{'echt %':>9}{'Null %':>9}"
        f"{'Streuung':>10}{'Perzentil':>11}{'z':>7}"
    )
    proben: list[Marktprobe] = []
    for symbol in symbole:
        rahmen = store.read(symbol, interval_obj)
        bericht = run_portfolio_walkforward(
            {symbol: rahmen}, lambda: compile_genome(genome),
            _spotconfigs([symbol], settings),
        )
        trades = ohne_zensierte(bericht).all_trades
        schluss = rahmen["close"].astype(float).to_numpy()
        zeiten = pd.DatetimeIndex(rahmen["open_time"])

        def balken(zeitpunkt, zeiten=zeiten) -> int:
            return int(zeiten.searchsorted(pd.Timestamp(zeitpunkt), side="right") - 1)

        dauern, echte, starts, enden = [], [], [], []
        for t in trades:
            a, b = balken(t.entry_time), balken(t.exit_time)
            if a < 0 or b <= a or b >= len(schluss):
                continue
            dauern.append(b - a)
            starts.append(a)
            enden.append(b)
            echte.append(float(t.exit_price) / float(t.entry_price) - 1.0)
        if len(echte) < 20:
            console.print(
                f"[dim]{symbol[:9]:<10}{'':<13}{len(echte):>7}   "
                f"zu wenige Trades fuer eine Probe[/]"
            )
            continue

        verteilung = zufallsverteilung(
            schluss, np.array(dauern), von=min(starts), bis=max(enden),
            ziehungen=ziehungen, rng=rng,
        )
        rolle = ENTWICKLUNG if symbol.startswith(("BTC", "ETH")) else HOLDOUT
        probe = Marktprobe(
            symbol=symbol, rolle=rolle, trades=len(echte),
            echt=float(np.mean(echte)), null=float(np.mean(verteilung)),
            streuung=float(np.std(verteilung, ddof=1)),
            perzentil=float((verteilung < np.mean(echte)).mean()),
        )
        proben.append(probe)
        console.print(
            f"{symbol[:9]:<10}{rolle:<13}{probe.trades:>7}{probe.echt*100:>9.3f}"
            f"{probe.null*100:>9.3f}{probe.streuung*100:>10.3f}"
            f"{probe.perzentil:>10.1%}"
            + ("      -" if probe.z is None else f"{probe.z:>7.2f}")
        )

    korrelation = None
    if len(symbole) > 1:
        renditen = {}
        for symbol in symbole:
            reihe = store.read(symbol, interval_obj)[["open_time", "close"]].copy()
            reihe["close"] = reihe["close"].astype(float)
            renditen[symbol] = np.log(reihe.set_index("open_time")["close"]).diff()
        tabelle = pd.DataFrame(renditen).dropna()
        if len(tabelle) > 30:
            werte = tabelle.corr().to_numpy()
            oben = werte[np.triu_indices_from(werte, k=1)]
            korrelation = float(oben.mean())

    console.print()
    console.print(Zufallsbild(tuple(proben), korrelation).urteil())


if __name__ == "__main__":
    app()
