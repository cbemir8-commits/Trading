"""Low-Level-HTTP-Client fuer die Bybit-V5-API.

Signierung, Wiederholungen und Rate-Limit-Behandlung leben hier - und nur hier.
Die Schicht darueber (``adapter.py``) kennt nur typisierte Domaenenobjekte.

Warum kein ``pybit``: Signieren ist ~30 Zeilen und vollstaendig dokumentiert.
Selbst gebaut haben wir exakte Kontrolle ueber Fehlerklassifikation, Retries
und den Demo-Endpunkt - und ein Verhalten, das wir hier ohne Netzzugang
vollstaendig gegen Fixtures testen koennen.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import time
from typing import Any, Literal

import httpx
import structlog

from core.config import BybitSettings

from .errors import (
    AUTH_RET_CODES,
    RETRYABLE_RET_CODES,
    BybitAPIError,
    BybitAuthError,
    BybitError,
    BybitGeoBlockedError,
    BybitRateLimitError,
    BybitServerError,
    BybitTransportError,
)

log = structlog.get_logger(__name__)

#: Textbausteine, an denen wir eine geblockte Region erkennen. CloudFront
#: antwortet mit HTTP 403 und einem *nicht* JSON-konformen Body.
_GEO_BLOCK_MARKERS = (
    "configured to block access from your country",
    "not available in your country",
)


def sign_request(
    *,
    api_secret: str,
    api_key: str,
    timestamp_ms: int,
    recv_window_ms: int,
    payload: str,
) -> str:
    """HMAC-SHA256-Signatur nach Bybit-V5-Spezifikation.

    ``payload`` ist der Query-String bei GET bzw. der rohe JSON-Body bei POST.
    Entscheidend: der Body muss *byteidentisch* zu dem sein, was gesendet wird -
    deshalb wird er einmal serialisiert und dann sowohl signiert als auch gesendet.
    """
    to_sign = f"{timestamp_ms}{api_key}{recv_window_ms}{payload}"
    return hmac.new(
        api_secret.encode("utf-8"), to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def encode_query(params: dict[str, Any]) -> str:
    """Query-String bauen. ``None``-Werte fallen raus, Bools werden klein geschrieben.

    Die Reihenfolge muss zwischen Signatur und tatsaechlicher Anfrage
    uebereinstimmen - deshalb wird hier genau einmal kodiert und das Ergebnis
    fuer beides verwendet.
    """
    parts: list[str] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        parts.append(f"{key}={value}")
    return "&".join(parts)


class BybitHTTPClient:
    """Synchroner HTTP-Client mit Signierung und Retry-Logik."""

    def __init__(self, settings: BybitSettings, *, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.base_url = settings.environment.rest_url
        self._client = client or httpx.Client(
            base_url=self.base_url,
            timeout=settings.http_timeout_s,
            headers={"Content-Type": "application/json"},
        )
        self._owns_client = client is None
        #: Zuletzt gesehener Rate-Limit-Rest, fuer Beobachtbarkeit.
        self.last_rate_limit_status: int | None = None

    def __enter__(self) -> BybitHTTPClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # -- oeffentliche Aufrufe -------------------------------------------------
    def get_public(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Unsignierter Aufruf fuer Marktdaten."""
        return self._request("GET", path, params=params or {}, signed=False)

    def get_private(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params or {}, signed=True)

    def post_private(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", path, body=body or {}, signed=True)

    # -- Innenleben ----------------------------------------------------------
    def _request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        signed: bool,
    ) -> dict[str, Any]:
        last_error: BybitError | None = None

        for attempt in range(self.settings.max_retries + 1):
            try:
                return self._request_once(method, path, params=params, body=body, signed=signed)
            except BybitError as exc:
                last_error = exc
                if not exc.retryable or attempt == self.settings.max_retries:
                    raise
                delay = self._backoff_seconds(attempt, exc)
                log.warning(
                    "bybit.retry",
                    path=path,
                    attempt=attempt + 1,
                    max_attempts=self.settings.max_retries + 1,
                    delay_s=delay,
                    error=str(exc),
                )
                time.sleep(delay)

        assert last_error is not None  # nur erreichbar, wenn max_retries < 0
        raise last_error

    @staticmethod
    def _backoff_seconds(attempt: int, exc: BybitError) -> float:
        """Exponentiell: 0.5s, 1s, 2s, 4s. Bei Rate-Limits auf den Reset warten."""
        if isinstance(exc, BybitRateLimitError) and exc.reset_at_ms:
            wait = (exc.reset_at_ms - int(time.time() * 1000)) / 1000
            if 0 < wait < 60:
                return wait + 0.1
        return min(0.5 * (2**attempt), 8.0)

    def _request_once(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
        signed: bool,
    ) -> dict[str, Any]:
        query = encode_query(params or {}) if method == "GET" else ""
        raw_body = (
            json.dumps(body, separators=(",", ":"), sort_keys=False) if method == "POST" else ""
        )
        headers = self._auth_headers(query if method == "GET" else raw_body) if signed else {}

        url = f"{path}?{query}" if query else path

        try:
            if method == "GET":
                response = self._client.get(url, headers=headers)
            else:
                response = self._client.post(
                    path, content=raw_body.encode("utf-8"), headers=headers
                )
        except httpx.TimeoutException as exc:
            raise BybitTransportError(f"Timeout bei {path}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise BybitTransportError(f"Netzwerkfehler bei {path}: {exc}") from exc

        self._record_rate_limit(response)
        return self._parse_response(response, path)

    def _auth_headers(self, payload: str) -> dict[str, str]:
        if not self.settings.has_credentials:
            raise BybitAuthError(
                "Signierter Aufruf ohne API-Credentials. "
                "BYBIT__API_KEY und BYBIT__API_SECRET in .env setzen."
            )
        timestamp_ms = int(time.time() * 1000)
        api_key = self.settings.api_key.get_secret_value()
        signature = sign_request(
            api_secret=self.settings.api_secret.get_secret_value(),
            api_key=api_key,
            timestamp_ms=timestamp_ms,
            recv_window_ms=self.settings.recv_window_ms,
            payload=payload,
        )
        return {
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-TIMESTAMP": str(timestamp_ms),
            "X-BAPI-RECV-WINDOW": str(self.settings.recv_window_ms),
            "X-BAPI-SIGN": signature,
        }

    def _record_rate_limit(self, response: httpx.Response) -> None:
        raw = response.headers.get("X-Bapi-Limit-Status")
        if raw is not None:
            with contextlib.suppress(ValueError):
                self.last_rate_limit_status = int(raw)

    def _parse_response(self, response: httpx.Response, path: str) -> dict[str, Any]:
        text = response.text

        # Geoblocking zuerst pruefen: CloudFront antwortet mit 403 und
        # kaputtem JSON, was sonst als unverstaendlicher Parse-Fehler endet.
        lowered = text.lower()
        if any(marker in lowered for marker in _GEO_BLOCK_MARKERS):
            raise BybitGeoBlockedError(
                f"Bybit blockt Anfragen aus der Region dieses Hosts (HTTP {response.status_code}). "
                "Das ist nicht durch erneutes Versuchen loesbar - der Dienst muss in einer "
                "erlaubten Region laufen. Pruefen mit: python -m scripts.healthcheck"
            )

        if response.status_code == 403:
            raise BybitAuthError(f"HTTP 403 bei {path}: {text[:200]}")
        if response.status_code == 429:
            raise BybitRateLimitError(
                f"HTTP 429 bei {path}",
                reset_at_ms=_safe_int(response.headers.get("X-Bapi-Limit-Reset-Timestamp")),
            )
        if response.status_code >= 500:
            raise BybitServerError(f"HTTP {response.status_code} bei {path}: {text[:200]}")

        try:
            payload: dict[str, Any] = response.json()
        except json.JSONDecodeError as exc:
            raise BybitTransportError(
                f"Antwort von {path} ist kein JSON (HTTP {response.status_code}): {text[:200]}"
            ) from exc

        ret_code = int(payload.get("retCode", -1))
        if ret_code == 0:
            return payload

        ret_msg = str(payload.get("retMsg", ""))
        if ret_code in AUTH_RET_CODES:
            raise BybitAuthError(f"[{ret_code}] {ret_msg} ({path})")
        if ret_code in RETRYABLE_RET_CODES:
            raise BybitRateLimitError(f"[{ret_code}] {ret_msg} ({path})")
        raise BybitAPIError(ret_code, ret_msg, endpoint=path)


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
