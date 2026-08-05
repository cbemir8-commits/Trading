"""Das Dashboard - Weboberflaeche und Steuerung.

    python -m cli dashboard

Getrennt vom Handelsprozess (siehe ``web/journal.py``). Diese Anwendung liest
nur Dateien und schreibt Befehle; sie spricht **nie** selbst mit Bybit. Das
haelt sie harmlos: Ein Fehler hier kann keine Order ausloesen.

Zugriffsschutz
--------------
Die Oberflaeche kann Positionen schliessen und den Not-Aus ausloesen. Sie
gehoert deshalb hinter ein Passwort - auch wenn sie "nur" im Heimnetz laeuft.

Bewusst schlicht gehalten: ein Passwort, aus dem ein Sitzungs-Cookie wird.
Kein Benutzerkonto, keine Registrierung, keine Passwort-vergessen-Strecke -
das waere mehr Angriffsflaeche fuer einen Dienst mit genau einem Benutzer.

**Ohne gesetztes Passwort startet nur der Nur-Lese-Betrieb.** Ein Dashboard
mit Not-Aus-Knopf und ohne Passwort waere schlimmer als keines.
"""

from __future__ import annotations

import hmac
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse

from core.config import Settings, get_settings
from web.journal import CommandAction, read_view, send_command
from web.trades import read_trades

log = structlog.get_logger(__name__)

STATIC = Path(__file__).parent / "static"

#: Wie lange eine Anmeldung gilt. Kurz genug, dass ein vergessenes Telefon
#: kein Dauerzugang ist; lang genug, dass man nicht staendig tippt.
SESSION_HOURS = 72


class SessionStore:
    """Sitzungen im Speicher.

    Absichtlich fluechtig: Ein Neustart des Dashboards meldet alle ab. Bei
    einem Einzelbenutzer-Dienst ist das kein Verlust, spart aber eine
    persistente Sitzungstabelle - und damit einen weiteren Ort, an dem etwas
    schieflaufen kann.
    """

    def __init__(self) -> None:
        self._tokens: dict[str, datetime] = {}

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = datetime.now(UTC)
        return token

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        issued = self._tokens.get(token)
        if issued is None:
            return False
        age_hours = (datetime.now(UTC) - issued).total_seconds() / 3600
        if age_hours > SESSION_HOURS:
            del self._tokens[token]
            return False
        return True

    def revoke(self, token: str | None) -> None:
        if token:
            self._tokens.pop(token, None)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    state_dir = Path(settings.paths.state)
    password = settings.web.password.get_secret_value()
    read_only = not password

    app = FastAPI(title="Trading-Dashboard", docs_url=None, redoc_url=None)
    sessions = SessionStore()

    if read_only:
        log.warning(
            "dashboard.nur_lesen",
            hinweis="Kein WEB__PASSWORD_HASH gesetzt - Steuerung ist gesperrt. "
            "Ein Not-Aus-Knopf ohne Passwort waere schlimmer als keiner.",
        )

    def require_session(
        session: Annotated[str | None, Cookie()] = None,
    ) -> str:
        """Schutz fuer alles, was etwas veraendert."""
        if read_only:
            raise HTTPException(
                403,
                "Steuerung gesperrt: kein Passwort gesetzt. "
                "In der .env WEB__PASSWORD_HASH setzen und neu starten.",
            )
        if not sessions.valid(session):
            raise HTTPException(401, "Nicht angemeldet")
        return session or ""

    # -- Oberflaeche ---------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse((STATIC / "index.html").read_text())

    @app.get("/manifest.json")
    def manifest() -> JSONResponse:
        """Macht die Seite auf dem iPhone zur App (Teilen -> Zum Home-Bildschirm)."""
        return JSONResponse(
            {
                "name": "Trading",
                "short_name": "Trading",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#0b0e14",
                "theme_color": "#0b0e14",
                "icons": [],
            }
        )

    # -- Anmeldung -----------------------------------------------------------
    @app.post("/api/login")
    def login(payload: dict, response: Response) -> dict:
        if read_only:
            raise HTTPException(403, "Steuerung gesperrt: kein Passwort gesetzt.")

        given = str(payload.get("password", ""))
        # Konstante Laufzeit: Ein Vergleich, der bei der ersten falschen
        # Stelle abbricht, verraet ueber die Antwortzeit, wie viele Zeichen
        # stimmen.
        if not hmac.compare_digest(given, password):
            log.warning("dashboard.anmeldung_fehlgeschlagen")
            raise HTTPException(401, "Falsches Passwort")

        token = sessions.create()
        response.set_cookie(
            "session",
            token,
            httponly=True,
            samesite="strict",
            max_age=SESSION_HOURS * 3600,
        )
        log.info("dashboard.angemeldet")
        return {"ok": True}

    @app.post("/api/logout")
    def logout(
        response: Response, session: Annotated[str | None, Cookie()] = None
    ) -> dict:
        sessions.revoke(session)
        response.delete_cookie("session")
        return {"ok": True}

    # -- Lesen ---------------------------------------------------------------
    @app.get("/api/wettbewerb")
    def wettbewerb() -> dict:
        """Die Bestenliste - Platz 1 bis Ende, ueber alle Laeufe hinweg.

        Bewusst ohne Anmeldung lesbar, wie der uebrige Statusteil: Es stehen
        Kennzahlen von Strategien darin, keine Kontodaten. Wer die Seite
        ohnehin sieht, sieht auch den Kontostand.
        """
        from research.leaderboard import Leaderboard

        board = Leaderboard(state_dir / "leaderboard.json")
        return {
            "zusammenfassung": board.summary(),
            "laeufe": board.laeufe,
            "geprueft": len(board.entries),
            "zugelassen": len(board.admitted),
            "eintraege": [
                {
                    "platz": platz,
                    "name": e.name,
                    "generation": e.generation,
                    "herkunft": e.herkunft,
                    "zugelassen": e.zugelassen,
                    "gates_bestanden": e.gates_bestanden,
                    "gates_gesamt": e.gates_gesamt,
                    "gescheitert_an": e.gescheitert_an,
                    "trades": e.trades,
                    "erwartung_r": e.erwartung_r,
                    "sharpe": e.sharpe,
                    "rendite_pct": e.rendite_pct,
                    "max_drawdown_pct": e.max_drawdown_pct,
                    "fenster_profitabel": e.fenster_profitabel,
                    "geprueft": e.geprueft,
                    "hypothese": e.hypothese,
                }
                for platz, e in enumerate(board.ranked(), start=1)
            ],
        }

    @app.get("/api/status")
    def status(session: Annotated[str | None, Cookie()] = None) -> dict:
        """Alles, was die Oberflaeche anzeigt - in einem Aufruf.

        Ein Aufruf statt fuenf, weil das Telefon oft ueber Mobilfunk laedt:
        Fuenf Anfragen kosten dort fuenf Rundlaeufe.
        """
        view = read_view(state_dir, event_limit=60)
        return {
            "alive": view.alive,
            "status_text": view.status_text,
            "last_heartbeat": (
                view.last_heartbeat.isoformat() if view.last_heartbeat else None
            ),
            "snapshot": view.snapshot,
            "events": view.events,
            "authenticated": sessions.valid(session),
            "read_only": read_only,
            "server_time": datetime.now(UTC).isoformat(),
        }

    @app.get("/api/trades")
    def trades(
        limit: int = 200,
        _: str = Depends(require_session),
    ) -> dict:
        """Jeder abgeschlossene Trade einzeln - Einstieg, Stop, Ergebnis.

        **Hinter der Anmeldung**, anders als der Wettbewerb. Backtest-Zahlen
        sind Forschung und duerfen jeder sehen; diese Liste ist der Verlauf
        eines echten Kontos. Aus Einstiegen, Mengen und Gewinnen laesst sich
        die Kontogroesse zurueckrechnen.

        Die Kennzahlen oben beziehen sich immer auf **alle** Trades, auch wenn
        die Liste gekuerzt wird - sonst aenderte sich die Trefferquote,
        sobald jemand weniger Zeilen anfordert.
        """
        return read_trades(state_dir, limit=max(1, min(limit, 1000))).to_json()

    # -- Steuern -------------------------------------------------------------
    @app.post("/api/control/{action}")
    def control(
        action: str,
        payload: dict | None = None,
        _: str = Depends(require_session),
    ) -> dict:
        """Eine Anweisung an den Handelsprozess legen.

        Die Anweisung wird **abgelegt, nicht ausgefuehrt**: Der Handel holt
        sie bei der naechsten Kerze ab. Auf einem 15-Minuten-Intervall kann
        das bis zu 15 Minuten dauern - deshalb sagt die Oberflaeche das auch.

        Wer sofort raus muss, schliesst die Position direkt bei Bybit. Dass
        das jederzeit geht, ist Absicht: Kein Automat steht zwischen dir und
        deinem Geld.
        """
        try:
            command = CommandAction(action)
        except ValueError as exc:
            raise HTTPException(400, f"Unbekannte Anweisung: {action}") from exc

        reason = (payload or {}).get("reason", "vom Dashboard")
        send_command(state_dir, command, reason)
        return {
            "ok": True,
            "action": command.value,
            "hinweis": "Wird bei der naechsten Kerze ausgefuehrt.",
        }

    return app
