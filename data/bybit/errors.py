"""Fehlertypen fuer die Bybit-Anbindung.

Warum eigene Fehlerklassen: Der Aufrufer muss unterscheiden koennen zwischen
"nochmal versuchen" (Netz, Rate-Limit, 5xx) und "aufhoeren, es ist kaputt"
(falscher Key, geblockte Region, ungueltige Order). Ein generisches
``requests.HTTPError`` erlaubt diese Entscheidung nicht.
"""

from __future__ import annotations


class BybitError(Exception):
    """Basisklasse fuer alles, was bei Bybit schiefgeht."""

    retryable: bool = False


class BybitTransportError(BybitError):
    """Netzwerkebene: Timeout, DNS, Verbindungsabbruch."""

    retryable = True


class BybitGeoBlockedError(BybitError):
    """Bybit (bzw. dessen CloudFront) blockt die Region dieses Hosts.

    Das ist kein voruebergehender Fehler und laesst sich nicht wegretryen -
    der Server muss in einer anderen Region stehen.

    Bekannt: Der Claude-Code-Entwicklungscontainer ist betroffen. Deshalb
    laufen alle Integrationstests gegen aufgezeichnete Fixtures, und die
    echte Verbindung wird auf dem Ziel-VPS geprueft (``scripts/healthcheck.py``).
    """

    retryable = False


class BybitRateLimitError(BybitError):
    """Rate-Limit ueberschritten. Warten und erneut versuchen."""

    retryable = True

    def __init__(self, message: str, *, reset_at_ms: int | None = None) -> None:
        super().__init__(message)
        self.reset_at_ms = reset_at_ms


class BybitServerError(BybitError):
    """5xx auf Bybit-Seite."""

    retryable = True


class BybitAuthError(BybitError):
    """Ungueltiger Key, falsches Secret, abgelaufener Zeitstempel oder IP nicht
    in der Whitelist."""

    retryable = False


class BybitAPIError(BybitError):
    """Fachlicher Fehler: ``retCode != 0``.

    Beispiele: Order zu klein, Hebel nicht erlaubt, Position existiert nicht.
    """

    retryable = False

    def __init__(self, ret_code: int, ret_msg: str, *, endpoint: str = "") -> None:
        self.ret_code = ret_code
        self.ret_msg = ret_msg
        self.endpoint = endpoint
        super().__init__(f"[{ret_code}] {ret_msg}" + (f" ({endpoint})" if endpoint else ""))


#: retCodes, bei denen ein erneuter Versuch sinnvoll ist.
RETRYABLE_RET_CODES: frozenset[int] = frozenset(
    {
        10002,  # Zeitstempel ausserhalb recv_window
        10016,  # interner Serverfehler
        10429,  # zu viele Anfragen
        130150,  # System beschaeftigt
        170007,  # Timeout beim Matching-Engine-Zugriff
    }
)

#: retCodes, die auf ein Authentifizierungsproblem hindeuten.
AUTH_RET_CODES: frozenset[int] = frozenset(
    {
        10003,  # ungueltiger API-Key
        10004,  # Signatur stimmt nicht
        10005,  # Rechte fehlen
        10010,  # IP nicht in Whitelist
        33004,  # API-Key abgelaufen
    }
)
