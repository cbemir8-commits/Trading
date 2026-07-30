"""Verbindungs- und Sicherheitspruefung.

Vor allem anderen auf dem Ziel-VPS ausfuehren:

    python -m scripts.healthcheck

Prueft der Reihe nach:

1. Konfiguration geladen, richtige Umgebung
2. **Bybit ueberhaupt erreichbar** (Geoblocking - der Killer-Punkt)
3. Uhrzeit-Abweichung (zu grosse Drift laesst jede Signatur scheitern)
4. Kontraktspezifikationen
5. Reichweite der Historie
6. Credentials gueltig
7. **API-Key-Rechte** - warnt laut, wenn Auszahlung aktiviert ist
8. Vorschau: welcher Hebel ergibt sich bei welchem Stop

Beendet mit Code 0 (alles gut), 1 (Warnungen) oder 2 (kritisch).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from rich.console import Console
from rich.table import Table

from core.config import Settings, get_settings
from core.models import Interval
from data.bybit.adapter import BybitAccount, BybitMarketData
from data.bybit.client import BybitHTTPClient
from data.bybit.errors import (
    BybitAuthError,
    BybitError,
    BybitGeoBlockedError,
    BybitTransportError,
)
from execution.sizing import leverage_for_stop

console = Console()

#: Ueber dieser Abweichung schlagen signierte Anfragen fehl (recv_window).
MAX_CLOCK_DRIFT = timedelta(seconds=3)


class Level(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(slots=True)
class Check:
    name: str
    level: Level
    detail: str
    hint: str = ""


@dataclass(slots=True)
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, level: Level, detail: str, hint: str = "") -> Check:
        check = Check(name, level, detail, hint)
        self.checks.append(check)
        return check

    @property
    def exit_code(self) -> int:
        if any(c.level is Level.FAIL for c in self.checks):
            return 2
        if any(c.level is Level.WARN for c in self.checks):
            return 1
        return 0

    def render(self) -> None:
        symbols = {Level.OK: "[green]OK[/]", Level.WARN: "[yellow]WARN[/]",
                   Level.FAIL: "[red]FEHLER[/]", Level.SKIP: "[dim]uebersprungen[/]"}
        table = Table(title="Bybit Health-Check", show_lines=False, header_style="bold")
        table.add_column("Pruefung", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center", width=14)
        table.add_column("Details")

        for check in self.checks:
            detail = check.detail
            if check.hint:
                detail += f"\n[dim]-> {check.hint}[/]"
            table.add_row(check.name, symbols[check.level], detail)

        console.print(table)


def check_config(report: Report, settings: Settings) -> None:
    env = settings.bybit.environment
    level = Level.OK
    hint = ""
    if env.is_real_money:
        level = Level.WARN
        hint = "ECHTES GELD. Erst nach 30 Tagen erfolgreicher Demo-Phase."
    report.add(
        "Konfiguration",
        level,
        f"Umgebung [bold]{env.value}[/] -> {env.rest_url}\n"
        f"Symbol {settings.bybit.symbol} ({settings.bybit.category}), "
        f"Kostenstufe {settings.cost.tier.value}",
        hint,
    )

    risk = settings.risk
    report.add(
        "Risikogrenzen",
        Level.OK,
        f"Risiko/Trade {risk.risk_per_trade_pct} %, Hebeldeckel {risk.max_leverage}x "
        f"({risk.margin_mode.value})\n"
        f"Tag {risk.daily_loss_limit_pct} % / Woche {risk.weekly_loss_limit_pct} % / "
        f"Kill-Switch {risk.max_drawdown_pct} %",
    )


def check_reachability(report: Report, market: BybitMarketData) -> bool:
    """Der entscheidende Test. Ohne ihn ist alles andere sinnlos."""
    try:
        server_time = market.get_server_time()
    except BybitGeoBlockedError as exc:
        report.add(
            "Erreichbarkeit",
            Level.FAIL,
            str(exc),
            "Dieser Host steht in einer von Bybit geblockten Region. "
            "Der Dienst muss auf einem VPS in einer erlaubten Region laufen. "
            "Bekannt betroffen: der Claude-Code-Entwicklungscontainer.",
        )
        return False
    except BybitTransportError as exc:
        report.add(
            "Erreichbarkeit", Level.FAIL, f"Kein Netzwerkzugang zu Bybit: {exc}",
            "Firewall, DNS oder Proxy pruefen.",
        )
        return False
    except BybitError as exc:
        report.add("Erreichbarkeit", Level.FAIL, f"Unerwarteter Fehler: {exc}")
        return False

    local_time = datetime.now(UTC)
    drift = abs(local_time - server_time)
    if drift > MAX_CLOCK_DRIFT:
        report.add(
            "Erreichbarkeit",
            Level.FAIL,
            f"Bybit erreichbar, aber Uhrzeit weicht um {drift.total_seconds():.1f} s ab",
            "Signierte Anfragen werden fehlschlagen. NTP einrichten: "
            "'sudo timedatectl set-ntp true'",
        )
        return False

    report.add(
        "Erreichbarkeit",
        Level.OK,
        f"Bybit antwortet. Serverzeit {server_time:%Y-%m-%d %H:%M:%S} UTC, "
        f"Abweichung {drift.total_seconds():.2f} s",
    )
    return True


def check_instrument(report: Report, market: BybitMarketData, settings: Settings) -> Decimal | None:
    """Kontraktspezifikationen holen und den aktuellen Preis zurueckgeben."""
    symbol = settings.bybit.symbol
    try:
        instrument = market.get_instrument(symbol)
        ticker = market.get_ticker(symbol)
    except BybitError as exc:
        report.add("Kontrakt", Level.FAIL, f"Spezifikationen nicht abrufbar: {exc}")
        return None

    min_notional_at_price = instrument.min_order_qty * ticker.last_price
    report.add(
        "Kontrakt",
        Level.OK,
        f"{instrument.symbol}: Kurs {ticker.last_price}, Spread {ticker.spread_pct:.4f} %\n"
        f"Mindestmenge {instrument.min_order_qty} {instrument.base_coin} "
        f"(= {min_notional_at_price:.0f} {instrument.quote_coin} Nominalwert), "
        f"Schrittweite {instrument.qty_step}, Tick {instrument.tick_size}\n"
        f"Funding aktuell {ticker.funding_rate * 100:.4f} %",
    )
    return ticker.last_price


def check_history(report: Report, market: BybitMarketData, settings: Settings) -> None:
    """Wie weit reicht die Historie? Wir brauchen mehrere Jahre fuer Walk-Forward."""
    symbol = settings.bybit.symbol
    try:
        oldest = market.get_klines(
            symbol, Interval.D1, start=datetime(2020, 1, 1, tzinfo=UTC), limit=5
        )
    except BybitError as exc:
        report.add("Historie", Level.WARN, f"Nicht pruefbar: {exc}")
        return

    if not oldest:
        report.add("Historie", Level.WARN, "Keine historischen Kerzen erhalten")
        return

    first = oldest[0].open_time
    years = (datetime.now(UTC) - first).days / 365.25
    level = Level.OK if years >= 3 else Level.WARN
    report.add(
        "Historie",
        level,
        f"Aelteste Tageskerze: {first:%Y-%m-%d} ({years:.1f} Jahre)",
        "" if years >= 3 else "Weniger als 3 Jahre - Walk-Forward wird duenn.",
    )


def check_credentials(report: Report, settings: Settings) -> None:
    if not settings.bybit.has_credentials:
        report.add(
            "Credentials",
            Level.SKIP,
            "Kein API-Key gesetzt - nur oeffentliche Daten geprueft",
            "BYBIT__API_KEY und BYBIT__API_SECRET in .env eintragen.",
        )
        return

    account = BybitAccount(settings.bybit)
    try:
        balance = account.get_wallet_balance("USDT")
    except BybitAuthError as exc:
        report.add(
            "Credentials",
            Level.FAIL,
            f"Anmeldung fehlgeschlagen: {exc}",
            "Key/Secret pruefen, IP-Whitelist pruefen, und sicherstellen dass der "
            "Key zur eingestellten Umgebung passt (Demo-Keys funktionieren nur "
            "gegen api-demo.bybit.com).",
        )
        return
    except BybitError as exc:
        report.add("Credentials", Level.FAIL, f"Kontoabfrage fehlgeschlagen: {exc}")
        return

    report.add(
        "Credentials",
        Level.OK,
        f"Angemeldet. Guthaben {balance.equity} USDT "
        f"(verfuegbar {balance.available_balance})",
    )

    try:
        positions = account.get_positions(settings.bybit.symbol)
    except BybitError:
        positions = []
    if positions:
        lines = [
            f"{p.side.value} {p.size} @ {p.entry_price}, PnL {p.unrealised_pnl}, "
            f"Liquidation {p.liq_price} ({p.distance_to_liquidation_pct():.1f} % entfernt)"
            for p in positions
        ]
        report.add("Offene Positionen", Level.WARN, "\n".join(lines),
                   "Vor dem Start des Systems bereinigen.")
    else:
        report.add("Offene Positionen", Level.OK, "Keine - sauberer Start")


def check_key_permissions(report: Report, settings: Settings) -> None:
    """Sicherheitspruefung: Der Key darf KEIN Auszahlungsrecht haben.

    Ein kompromittierter Key mit Auszahlungsrecht bedeutet Totalverlust. Ohne
    dieses Recht kann ein Angreifer im schlimmsten Fall schlecht handeln - das
    Geld bleibt aber auf dem Konto.
    """
    if not settings.bybit.has_credentials:
        report.add("Key-Rechte", Level.SKIP, "Kein API-Key gesetzt")
        return

    try:
        with BybitHTTPClient(settings.bybit) as client:
            payload = client.get_private("/v5/user/query-api")
    except BybitError as exc:
        report.add(
            "Key-Rechte", Level.WARN, f"Rechte nicht abrufbar: {exc}",
            "Bitte manuell in der Bybit-Oberflaeche pruefen.",
        )
        return

    result = payload.get("result", {})
    permissions: dict[str, list[str]] = result.get("permissions", {})
    granted = {area: perms for area, perms in permissions.items() if perms}

    withdraw_enabled = bool(
        result.get("isMaster") and "Withdraw" in permissions.get("Wallet", [])
    ) or bool(permissions.get("Withdraw"))

    ip_whitelist = result.get("ips") or []
    unrestricted_ip = not ip_whitelist or ip_whitelist == ["*"]

    detail = "Erteilte Rechte: " + ", ".join(
        f"{area} ({', '.join(perms)})" for area, perms in sorted(granted.items())
    )
    detail += f"\nIP-Whitelist: {', '.join(ip_whitelist) if ip_whitelist else 'keine'}"

    if withdraw_enabled:
        report.add(
            "Key-Rechte",
            Level.FAIL,
            detail + "\n[bold red]AUSZAHLUNGSRECHT IST AKTIV[/]",
            "Sofort in der Bybit-Oberflaeche entfernen. Ein kompromittierter Key "
            "mit diesem Recht bedeutet Totalverlust.",
        )
    elif unrestricted_ip:
        report.add(
            "Key-Rechte", Level.WARN, detail,
            "Keine IP-Whitelist gesetzt. Auf die VPS-IP beschraenken.",
        )
    else:
        report.add("Key-Rechte", Level.OK, detail + "\nKein Auszahlungsrecht - gut.")


def check_leverage_preview(report: Report, settings: Settings, price: Decimal | None) -> None:
    """Zeigt, welcher Hebel sich bei welcher Stop-Distanz ergibt.

    Macht die zentrale Identitaet sichtbar: Hebel = Risiko% / Stop%. Und es zeigt
    sofort, welche Stop-Distanzen beim aktuellen Kapital ueberhaupt handelbar sind.
    """
    if price is None:
        report.add("Hebel-Vorschau", Level.SKIP, "Kein Preis verfuegbar")
        return

    risk = settings.risk
    equity = Decimal("500")  # Planungsgroesse

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Stop")
    table.add_column("Hebel", justify="right")
    table.add_column("Nominalwert", justify="right")
    table.add_column("Menge BTC", justify="right")
    table.add_column("", style="dim")

    lines: list[str] = []
    for stop_pct in ["0.2", "0.3", "0.5", "0.8", "1.0", "1.5", "2.0"]:
        lev = leverage_for_stop(
            equity=equity,
            entry_price=price,
            stop_distance_pct=Decimal(stop_pct),
            risk_per_trade_pct=risk.risk_per_trade_pct,
        )
        notional = equity * lev
        qty = notional / price
        note = ""
        if lev > risk.max_leverage:
            note = f"ueber Deckel {risk.max_leverage}x - wird verkleinert"
        elif qty < Decimal("0.001"):
            note = "unter Mindestmenge - nicht handelbar"
        lines.append(f"{stop_pct} %|{lev}x|{notional:.0f}|{qty:.4f}|{note}")

    detail = (
        f"Bei {equity} EUR Kapital und {risk.risk_per_trade_pct} % Risiko "
        f"(= {equity * risk.risk_per_trade_pct / 100:.2f} EUR je Trade):\n"
    )
    detail += "\n".join(
        f"  Stop {parts[0]:>6} -> {parts[1]:>6} Hebel, {parts[2]:>5} EUR Nominal, "
        f"{parts[3]} BTC  {parts[4]}"
        for parts in (line.split("|") for line in lines)
    )
    detail += "\n[dim]Hebel = Risiko% / Stop%. Das riskierte Geld bleibt in jeder Zeile gleich.[/]"
    report.add("Hebel-Vorschau", Level.OK, detail)


def main() -> int:
    console.print("[bold]Bybit Health-Check[/]\n")
    report = Report()

    try:
        settings = get_settings()
    except Exception as exc:  # noqa: BLE001 - Konfigurationsfehler sollen lesbar sein
        console.print(f"[red]Konfiguration ungueltig:[/] {exc}")
        console.print("[dim].env gegen .env.example pruefen.[/]")
        return 2

    check_config(report, settings)
    market = BybitMarketData(settings.bybit)

    if check_reachability(report, market):
        price = check_instrument(report, market, settings)
        check_history(report, market, settings)
        check_credentials(report, settings)
        check_key_permissions(report, settings)
        check_leverage_preview(report, settings, price)

    report.render()

    code = report.exit_code
    if code == 0:
        console.print("\n[green]Alles in Ordnung.[/] Naechster Schritt: Datenpipeline (P1).")
    elif code == 1:
        console.print("\n[yellow]Mit Warnungen bestanden.[/] Siehe Hinweise oben.")
    else:
        console.print("\n[red]Kritische Fehler.[/] Erst beheben, dann weiterbauen.")
    return code


if __name__ == "__main__":
    sys.exit(main())
