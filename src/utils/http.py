"""Reusable HTTP session wrapper with retry, timeout, and logging.

All provider clients (RENAC, ShineMonitor) must use :class:`HttpClient`
instead of calling ``requests`` directly.  This guarantees consistent:

* Timeouts (default 15 s, overridable via ``Settings.http_timeout``)
* Retry behaviour (exponential back-off via *tenacity*)
* Request / response logging
* Custom exception hierarchy

Usage::

    from src.utils.http import HttpClient, HttpError

    client = HttpClient(base_url="https://api.example.com", timeout=15)
    data = client.get("/endpoint", params={"key": "value"})
    data = client.post("/login", json={"user": "me"})
    client.close()

    # or as a context manager
    with HttpClient("https://api.example.com") as client:
        data = client.get("/endpoint")
"""

from __future__ import annotations

import time
from typing import Any, Optional

import requests
from requests import Response, Session
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.utils.logger import logger

__all__ = [
    "HttpClient",
    "HttpError",
    "HttpAuthError",
    "HttpTimeoutError",
    "HttpServerError",
]

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class HttpError(Exception):
    """Base exception for all HTTP-layer errors."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HttpAuthError(HttpError):
    """Raised for HTTP 401 / 403 responses (token expired, bad credentials)."""


class HttpTimeoutError(HttpError):
    """Raised when a request exceeds the configured timeout."""


class HttpServerError(HttpError):
    """Raised for HTTP 5xx server-side errors eligible for retry."""


# ---------------------------------------------------------------------------
# Retry callbacks
# ---------------------------------------------------------------------------


def _log_retry(retry_state: RetryCallState) -> None:
    """Log each retry attempt with contextual information."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Retry attempt {attempt} after {wait:.1f}s | reason={exc}",
        attempt=retry_state.attempt_number,
        wait=retry_state.idle_for,
        exc=repr(exc),
    )


# ---------------------------------------------------------------------------
# HttpClient
# ---------------------------------------------------------------------------


class HttpClient:
    """Thin wrapper around :class:`requests.Session` with retry and logging.

    Args:
        base_url: Scheme + host (e.g. ``"https://api.example.com"``).
            Path segments are appended per-call.
        timeout: Socket timeout in seconds (connect + read).
        max_retries: Maximum number of retry attempts on transient failures.
        headers: Optional dict of headers added to every request.
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 15,
        max_retries: int = 3,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._session: Session = requests.Session()
        if headers:
            self._session.headers.update(headers)
        logger.debug(
            "HttpClient created | base_url={base_url} timeout={timeout}s retries={retries}",
            base_url=self._base_url,
            timeout=timeout,
            retries=max_retries,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """Perform a GET request and return the parsed JSON body.

        Args:
            path: URL path relative to ``base_url`` (must start with ``/``).
            params: Optional query-string parameters.
            headers: Optional per-request headers (merged with session headers).

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            HttpAuthError: On HTTP 401/403.
            HttpTimeoutError: On request timeout.
            HttpServerError: On HTTP 5xx (after exhausting retries).
            HttpError: On any other HTTP or network error.
        """
        return self._request("GET", path, params=params, extra_headers=headers)

    def post(
        self,
        path: str,
        *,
        data: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """Perform a POST request and return the parsed JSON body.

        Args:
            path: URL path relative to ``base_url``.
            data: Form-encoded body (``application/x-www-form-urlencoded``).
            json: JSON body (``application/json``).
            params: Optional query-string parameters.
            headers: Optional per-request headers.

        Returns:
            Parsed JSON response.

        Raises:
            HttpAuthError: On HTTP 401/403.
            HttpTimeoutError: On request timeout.
            HttpServerError: On HTTP 5xx (after exhausting retries).
            HttpError: On any other HTTP or network error.
        """
        return self._request(
            "POST", path, data=data, json=json, params=params, extra_headers=headers
        )

    def update_headers(self, headers: dict[str, str]) -> None:
        """Merge *headers* into the persistent session headers.

        Args:
            headers: Key-value pairs to add or override.
        """
        self._session.headers.update(headers)
        logger.debug("Session headers updated: {keys}", keys=list(headers.keys()))

    def close(self) -> None:
        """Release the underlying :class:`requests.Session`."""
        self._session.close()
        logger.debug("HttpClient session closed for base_url={url}", url=self._base_url)

    # Context-manager support
    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """Execute an HTTP request with retry logic applied.

        The retry decorator is applied dynamically so that ``max_retries``
        can be configured per-instance at runtime.
        """

        @retry(
            reraise=True,
            retry=retry_if_exception_type(HttpServerError),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            before_sleep=_log_retry,
        )
        def _do_request() -> Any:
            url = f"{self._base_url}{path}"
            merged_headers = dict(extra_headers) if extra_headers else {}
            t0 = time.perf_counter()

            logger.debug(
                "{method} {url} | params={params}",
                method=method,
                url=url,
                params=params,
            )

            try:
                response: Response = self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json,
                    headers=merged_headers,
                    timeout=self._timeout,
                )
            except requests.Timeout as exc:
                raise HttpTimeoutError(
                    f"Request timed out after {self._timeout}s: {url}"
                ) from exc
            except requests.ConnectionError as exc:
                raise HttpError(f"Connection error for {url}: {exc}") from exc

            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug(
                "{method} {url} → {status} ({elapsed:.0f} ms)",
                method=method,
                url=url,
                status=response.status_code,
                elapsed=elapsed,
            )

            if response.status_code in (401, 403):
                raise HttpAuthError(
                    f"Authentication error {response.status_code}: {url}",
                    status_code=response.status_code,
                )
            if response.status_code >= 500:
                raise HttpServerError(
                    f"Server error {response.status_code}: {url}",
                    status_code=response.status_code,
                )
            if not response.ok:
                raise HttpError(
                    f"HTTP {response.status_code}: {url}",
                    status_code=response.status_code,
                )

            try:
                return response.json()
            except ValueError as exc:
                raise HttpError(
                    f"Non-JSON response from {url}: {response.text[:200]}"
                ) from exc

        return _do_request()


# ---------------------------------------------------------------------------
# Self-test (uses httpbin.org — requires internet access)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== HttpClient self-test ===\n")

    with HttpClient("https://httpbin.org", timeout=15) as client:
        # 1. Basic GET
        print("1. GET /get")
        resp = client.get("/get", params={"foo": "bar"})
        assert resp["args"] == {"foo": "bar"}, f"Unexpected args: {resp['args']}"
        print(f"   args={resp['args']}  ✓")

        # 2. Basic POST (JSON)
        print("2. POST /post (json)")
        resp = client.post("/post", json={"hello": "world"})
        assert resp["json"] == {"hello": "world"}, f"Unexpected json: {resp['json']}"
        print(f"   json={resp['json']}  ✓")

        # 3. POST (form-encoded)
        print("3. POST /post (form data)")
        resp = client.post("/post", data={"key": "value"})
        assert resp["form"] == {"key": "value"}, f"Unexpected form: {resp['form']}"
        print(f"   form={resp['form']}  ✓")

    print("\nAll HttpClient tests passed.")
