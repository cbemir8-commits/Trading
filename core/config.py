"""Zentrale Konfiguration.

Alles wird ueber Umgebungsvariablen gesetzt (siehe .env.example). Verschachtelte
Bloecke nutzen einen doppelten Unterstrich: ``RISK__MAX_LEVERAGE=3``.

WICHTIG: Die Werte in :class:`RiskSettings` sind harte Grenzen. Die Research-KI
bekommt sie als *Kontext* zu sehen, kann sie aber nicht veraendern - sie stehen
in der Umgebung, nicht im Prompt.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BybitEnvironment(StrEnum):
    """Welche Bybit-Welt wir ansprechen."""

    DEMO = "demo"
    TESTNET = "testnet"
    MAINNET = "mainnet"

    @property
    def rest_url(self) -> str:
        return {
            BybitEnvironment.DEMO: "https://api-demo.bybit.com",
            BybitEnvironment.TESTNET: "https://api-testnet.bybit.com",
            BybitEnvironment.MAINNET: "https://api.bybit.com",
        }[self]

    @property
    def public_rest_url(self) -> str:
        """Marktdaten - Kerzen, Kontrakte, Ticker.

        **Nicht dieselbe Adresse wie fuer das Konto.** Der Demo-Host liefert
        zwar Kerzen, aber nur die juengsten rund 1000 je Zeitreihe - der
        Parameter ``start`` wird dort ignoriert. Ein Backfill laeuft dagegen
        scheinbar fehlerfrei durch: eine Anfrage, 999 Kerzen, "fertig". Das
        Ergebnis sind zehn Tage Historie statt sechs Jahren, und ein
        Walk-Forward daraus waere wertlos, ohne dass irgendetwas nach einem
        Fehler aussieht.

        Deshalb kommen Marktdaten immer vom Mainnet - so wie beim
        Websocket-Stream auch. Echte Preise, Spielgeld: genau das wollen wir.
        """
        return {
            BybitEnvironment.DEMO: "https://api.bybit.com",
            BybitEnvironment.TESTNET: "https://api-testnet.bybit.com",
            BybitEnvironment.MAINNET: "https://api.bybit.com",
        }[self]

    @property
    def private_ws_url(self) -> str:
        return {
            BybitEnvironment.DEMO: "wss://stream-demo.bybit.com/v5/private",
            BybitEnvironment.TESTNET: "wss://stream-testnet.bybit.com/v5/private",
            BybitEnvironment.MAINNET: "wss://stream.bybit.com/v5/private",
        }[self]

    def public_ws_url(self, category: str) -> str:
        """Oeffentliche Marktdaten.

        Bybit bietet fuer Demo-Trading KEINEN eigenen public stream an - dort
        werden die echten Mainnet-Marktdaten verwendet. Genau das wollen wir:
        echte Preise, Spielgeld.
        """
        host = (
            "wss://stream-testnet.bybit.com"
            if self is BybitEnvironment.TESTNET
            else "wss://stream.bybit.com"
        )
        return f"{host}/v5/public/{category}"

    @property
    def is_real_money(self) -> bool:
        return self is BybitEnvironment.MAINNET


class BybitSettings(BaseModel):
    environment: BybitEnvironment = BybitEnvironment.DEMO
    api_key: SecretStr = SecretStr("")
    api_secret: SecretStr = SecretStr("")
    symbol: str = "BTCUSDT"
    category: Literal["linear", "inverse", "spot"] = "linear"
    recv_window_ms: int = 5_000
    http_timeout_s: float = 15.0
    max_retries: int = 4

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key.get_secret_value() and self.api_secret.get_secret_value())


class MarginMode(StrEnum):
    ISOLATED = "isolated"
    CROSS = "cross"


class RiskSettings(BaseModel):
    """Harte Risikogrenzen. Der Risk-Officer setzt sie durch und hat Vetorecht.

    Zum Hebel - die wichtigste Fehlvorstellung im Trading:

    Der Hebel ist bei uns kein Regler fuer "mehr Gewinn". Er ist das *Ergebnis*
    der risikobasierten Positionsgroesse:

        Risiko pro Trade  = Positionsgroesse x Stop-Distanz
        Positionsgroesse  = (Kapital x risk_per_trade_pct) / Stop-Distanz
        Hebel             = Positionsgroesse / Kapital

    Beispiel bei 500 EUR Kapital und 0,75 % Risiko (= 3,75 EUR):
        Stop 1,0 % entfernt -> 375 EUR Position -> 0,75x Hebel
        Stop 0,5 % entfernt -> 750 EUR Position -> 1,50x Hebel
        Stop 0,3 % entfernt -> 1250 EUR Position -> 2,50x Hebel

    Enge Stops brauchen also *zwingend* Hebel - ohne ihn koennten wir bei 500 EUR
    gar nicht sinnvoll handeln (Bybit-Mindestgroesse 0,001 BTC entspricht bei
    100k$ schon ~20 % des Kontos).

    Was der Hebel NICHT tut: die Gewinnerwartung verbessern. Er skaliert Gewinn
    und Verlust exakt gleich. Der einzige Regler, der das Risiko wirklich
    veraendert, ist ``risk_per_trade_pct``.

    Was der Hebel gefaehrlich macht: die Liquidation. Bei 3x isoliert liegt sie
    grob 33 % entfernt - unerreichbar, wenn unser Stop bei 1 % sitzt. Bei 20x
    liegt sie bei ~5 %, also innerhalb eines normalen BTC-Dochts. Genau so
    sterben Konten. Deshalb erzwingt ``min_liquidation_buffer`` zusaetzlich,
    dass die Liquidation immer ein Vielfaches der Stop-Distanz entfernt ist.
    """

    # --- Positionsgroesse ---
    risk_per_trade_pct: Decimal = Field(Decimal("0.75"), gt=0, le=5)
    max_concurrent_positions: int = Field(1, ge=1, le=10)

    equity_cap: Decimal = Field(Decimal(0), ge=0)
    """Obergrenze fuer das Kapital, mit dem gerechnet wird. 0 = aus.

    Gebaut fuer die Demo-Phase, und dort unverzichtbar: Bybit haendigt im
    Demo-Konto gerne 50.000 USDT Spielgeld aus. Ohne Deckel wuerde das System
    dann Positionen im hundertfachen Umfang des geplanten 500-EUR-Kontos
    eroeffnen - und damit ausgerechnet die Grenzen nie beruehren, an denen es
    spaeter scheitern koennte: Mindestmenge 0,001 BTC, Schrittweite, der
    Hebeldeckel.

    Mit ``equity_cap=500`` handelt die Demo exakt so, wie das echte Konto es
    taete. Nur dann sagt sie etwas ueber das echte Konto aus."""

    # --- Hebel ---
    max_leverage: Decimal = Field(Decimal("3"), ge=1, le=25)
    margin_mode: MarginMode = MarginMode.ISOLATED
    # Die Liquidation muss mindestens N x weiter weg sein als der Stop-Loss.
    # 4.0 heisst: Stop bei 1 % -> Liquidation muss >= 4 % entfernt sein.
    min_liquidation_buffer: Decimal = Field(Decimal("4.0"), ge=2)

    # --- Stop-Distanzen (Sanity-Grenzen gegen kaputte Signale) ---
    min_stop_distance_pct: Decimal = Field(Decimal("0.15"), gt=0)
    max_stop_distance_pct: Decimal = Field(Decimal("3.0"), gt=0)

    # --- Termin-Sperre ---
    # Wie lange vor und nach einem Termin (Fed-Entscheidung, Halbierung) nicht
    # eingestiegen wird. Dazu kommt immer die Kerze, in die der Termin faellt -
    # siehe ``Terminkalender.sperre``. 60/60 ist bewusst rund und **vor** der
    # ersten Messung festgelegt: Eine Zahl, die zum Ergebnis passend gewaehlt
    # wird, misst nur noch sich selbst.
    news_blackout_before_min: int = Field(60, ge=0, le=1440)
    news_blackout_after_min: int = Field(60, ge=0, le=1440)

    # --- Verlustbremsen ---
    daily_loss_limit_pct: Decimal = Field(Decimal("3.0"), gt=0)
    weekly_loss_limit_pct: Decimal = Field(Decimal("7.0"), gt=0)
    max_drawdown_pct: Decimal = Field(Decimal("15.0"), gt=0)

    # --- Gebuehren-Disziplin ---
    # Entries und Take-Profits als PostOnly-Limit (Maker). Nur der Stop ist Market.
    # Bei kleinem Konto ist das der Unterschied zwischen 2 % und 5,5 % Gebuehren
    # pro Monat - also zwischen tragbar und toedlich.
    require_maker_entry: bool = True

    @model_validator(mode="after")
    def _check_consistency(self) -> RiskSettings:
        if self.min_stop_distance_pct >= self.max_stop_distance_pct:
            raise ValueError("min_stop_distance_pct muss kleiner als max_stop_distance_pct sein")
        if self.daily_loss_limit_pct >= self.max_drawdown_pct:
            raise ValueError(
                "daily_loss_limit_pct muss kleiner als max_drawdown_pct sein, "
                "sonst greift der Kill-Switch nie vor dem Tageslimit"
            )
        if self.weekly_loss_limit_pct >= self.max_drawdown_pct:
            raise ValueError("weekly_loss_limit_pct muss kleiner als max_drawdown_pct sein")
        return self


class CostTier(StrEnum):
    """Kostenstufen - skalieren den KI-Betrieb am Kapital.

    Bei 500 EUR Kapital waeren 300 EUR/Monat Betriebskosten 60 % Rendite-Bedarf.
    Deshalb faehrt der Betrieb nach dem Live-Gang automatisch herunter.
    """

    BUILD = "build"
    DEMO = "demo"
    LIVE = "live"
    SCALE = "scale"


class TierProfile(BaseModel):
    """Was in einer Kostenstufe erlaubt ist."""

    monthly_budget_usd: Decimal
    research_model: str
    news_model: str
    research_runs_per_day: float
    max_backtests_per_run: int


TIER_PROFILES: dict[CostTier, TierProfile] = {
    CostTier.BUILD: TierProfile(
        monthly_budget_usd=Decimal("320"),
        research_model="claude-opus-5",
        news_model="claude-haiku-4-5",
        research_runs_per_day=4,
        max_backtests_per_run=40,
    ),
    CostTier.DEMO: TierProfile(
        monthly_budget_usd=Decimal("45"),
        research_model="claude-opus-5",
        news_model="claude-haiku-4-5",
        research_runs_per_day=1,
        max_backtests_per_run=20,
    ),
    CostTier.LIVE: TierProfile(
        monthly_budget_usd=Decimal("18"),
        research_model="claude-opus-5",
        news_model="claude-haiku-4-5",
        research_runs_per_day=1 / 7,  # einmal pro Woche
        max_backtests_per_run=20,
    ),
    CostTier.SCALE: TierProfile(
        monthly_budget_usd=Decimal("320"),
        research_model="claude-opus-5",
        news_model="claude-haiku-4-5",
        research_runs_per_day=4,
        max_backtests_per_run=40,
    ),
}


class CostSettings(BaseModel):
    tier: CostTier = CostTier.BUILD
    monthly_budget_eur: Decimal = Field(Decimal("300"), gt=0)
    # Bei wieviel Prozent des Budgets wird der Research-Betrieb hart gestoppt.
    hard_stop_at_pct: Decimal = Field(Decimal("100"), gt=0, le=200)
    # Ab hier wird auf das guenstigere Modell heruntergeschaltet.
    downgrade_at_pct: Decimal = Field(Decimal("70"), gt=0, le=100)

    @property
    def profile(self) -> TierProfile:
        return TIER_PROFILES[self.tier]


class LLMSettings(BaseModel):
    anthropic_api_key: SecretStr = SecretStr("")

    @property
    def has_credentials(self) -> bool:
        return bool(self.anthropic_api_key.get_secret_value())


class DBSettings(BaseModel):
    dsn: str = "postgresql+psycopg://trading:trading@localhost:5432/trading"
    echo: bool = False
    pool_size: int = 5


class NotifySettings(BaseModel):
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token.get_secret_value() and self.telegram_chat_id)


class WebSettings(BaseModel):
    password: SecretStr = SecretStr("")
    """Zugang zum Dashboard. **Leer bedeutet Nur-Lese-Betrieb** - die
    Steuerung (Pause, Glattstellen, Not-Aus) ist dann gesperrt. Ein
    Not-Aus-Knopf ohne Passwort waere schlimmer als keiner.

    Im Klartext in der ``.env``, die Dateirechte 600 traegt. Ein Hash waere
    hier Sicherheitstheater: Wer die ``.env`` lesen kann, hat ohnehin schon
    die API-Zugangsdaten - und die sind ungleich mehr wert."""

    host: str = "127.0.0.1"
    """Standardmaessig nur lokal erreichbar. Von aussen erreichbar macht man
    das Dashboard ueber einen SSH-Tunnel oder einen Reverse-Proxy mit TLS -
    nicht, indem man hier 0.0.0.0 eintraegt und hofft."""

    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


class ReportSettings(BaseModel):
    """Berichte, die von selbst ankommen.

    Standardmaessig **an**: Jeder Zulassungslauf legt einen vollstaendigen
    Bericht in ``reports/`` ab und schiebt ihn ins Repository. Das ersetzt die
    Bildschirmfotos, die vorher zwischen dem Rechner des Nutzers und der
    Auswertung standen.

    Was mitgeht, ist im Bericht selbst begrenzt: relative Kennzahlen, keine
    Kontostaende, keine Zugangsdaten. Wer das trotzdem nicht will, setzt
    ``REPORT__AUTOPUSH=false`` - dann bleiben die Dateien lokal liegen.
    """

    autopush: bool = True
    remote: str = "origin"


class PathSettings(BaseModel):
    data_store: str = "data_store"
    logs: str = "logs"

    state: str = "state"
    """Betriebszustand, der einen Neustart ueberleben muss - vor allem der
    Risk-Officer. Getrennt vom Datenspeicher, weil er anders gesichert wird:
    Kerzen lassen sich jederzeit nachladen, ein ausgeloester Kill-Switch nicht."""

    strategies: str = "strategies"
    """Zugelassene Genome. Was hier liegt, hat die neun Gates bestanden."""

    referenz: str = "referenz"
    """Nachgeschlagene Daten aus kanonischen Quellen - eingecheckt.

    Bewusst **nicht** unter ``state``: Der Betriebszustand ist
    maschinenspezifisch und deshalb nicht im Repository. Referenzdaten sind das
    Gegenteil - der Terminkalender muss auf jedem Rechner derselbe sein, sonst
    rechnet der Backtest hier ein anderes Ergebnis als beim Nutzer. Genau diese
    Sorte Abweichung hat dieses Projekt schon fuenfmal Geld gekostet."""


class Settings(BaseSettings):
    """Wurzel-Konfiguration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    bybit: BybitSettings = Field(default_factory=BybitSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    cost: CostSettings = Field(default_factory=CostSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    db: DBSettings = Field(default_factory=DBSettings)
    notify: NotifySettings = Field(default_factory=NotifySettings)
    web: WebSettings = Field(default_factory=WebSettings)
    report: ReportSettings = Field(default_factory=ReportSettings)
    paths: PathSettings = Field(default_factory=PathSettings)

    @model_validator(mode="after")
    def _guard_real_money(self) -> Settings:
        """Zusaetzliche Huerde, bevor echtes Geld im Spiel ist."""
        if self.bybit.environment.is_real_money and not self.bybit.has_credentials:
            raise ValueError("Mainnet ohne API-Credentials ergibt keinen Sinn")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Gecachte Settings-Instanz. In Tests mit ``get_settings.cache_clear()`` zuruecksetzen."""
    return Settings()
