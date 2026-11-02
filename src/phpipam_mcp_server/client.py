#!/usr/bin/env python3
"""Shared phpIPAM API client.

This module holds the transport-agnostic pieces used by BOTH the MCP server
(``server.py``) and the command-line interface (``cli.py``):

* credential resolution (env vars, with optional per-request header override),
* the authenticated HTTP request helper,
* response field-filtering and result-limiting helpers.

It deliberately imports nothing from ``mcp`` so the CLI can run without the
MCP machinery installed or initialised.
"""

from __future__ import annotations

import contextvars
import os
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Request-scoped credential override (used by the HTTP transport in server.py)
# ---------------------------------------------------------------------------
# In HTTP mode an ASGI middleware stores the incoming request headers here so
# that credential resolution can prefer per-client ``X-phpIPAM-*`` headers over
# the server-wide environment variables. In stdio and CLI use this stays empty.
_request_headers: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "phpipam_request_headers", default={}
)

# Default network timeout (seconds) for phpIPAM API calls.
DEFAULT_TIMEOUT = 30


class PhpIpamError(Exception):
    """Raised for phpIPAM configuration or API failures.

    ``kind`` classifies the failure so callers (CLI exit codes, MCP error
    strings) can branch without string-matching:

    * ``"config"``  - missing/invalid credentials (nothing was sent).
    * ``"auth"``    - phpIPAM rejected the credentials (HTTP 401/403).
    * ``"notfound"``- resource does not exist (HTTP 404).
    * ``"network"`` - connection/timeout failure.
    * ``"api"``     - any other API/transport error.
    """

    def __init__(self, message: str, kind: str = "api"):
        super().__init__(message)
        self.kind = kind


def _env_truthy(value: str | None, default: bool = True) -> bool:
    """Interpret an environment/header string as a boolean."""
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off", "")


def get_phpipam_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve phpIPAM configuration.

    Resolution order for each value (highest priority first):
      1. Explicit ``overrides`` (CLI flags), e.g. ``{"base_url": ...}``.
      2. Per-client HTTP header (remote MCP mode), e.g. ``x-phpipam-url``.
      3. Server-wide environment variable, e.g. ``PHPIPAM_URL``.

    ``overrides`` keys: ``base_url``, ``app_id``, ``token``, ``verify_ssl``.
    Any key that is ``None`` is ignored so partial overrides fall through to
    headers/env.

    Raises:
        PhpIpamError(kind="config"): if URL, App ID, or App Code is missing.
    """
    overrides = overrides or {}
    headers = _request_headers.get()

    base_url = (
        overrides.get("base_url")
        or headers.get("x-phpipam-url")
        or os.getenv("PHPIPAM_URL")
    )
    app_id = (
        overrides.get("app_id")
        or headers.get("x-phpipam-app-id")
        or os.getenv("PHPIPAM_APP_ID")
    )
    token = (
        overrides.get("token")
        or headers.get("x-phpipam-app-code")
        or os.getenv("PHPIPAM_APP_CODE")
    )

    if overrides.get("verify_ssl") is not None:
        verify_ssl = bool(overrides["verify_ssl"])
    else:
        verify_raw = headers.get("x-phpipam-verify-ssl")
        if verify_raw is None:
            verify_raw = os.getenv("PHPIPAM_VERIFY_SSL")
        verify_ssl = _env_truthy(verify_raw, default=True)

    if not base_url:
        raise PhpIpamError(
            "phpIPAM URL is required (PHPIPAM_URL env var, --url flag, "
            "or X-phpIPAM-URL header)",
            kind="config",
        )
    if not app_id:
        raise PhpIpamError(
            "phpIPAM App ID is required (PHPIPAM_APP_ID env var, --app-id flag, "
            "or X-phpIPAM-App-Id header)",
            kind="config",
        )
    if not token:
        raise PhpIpamError(
            "phpIPAM App Code is required (PHPIPAM_APP_CODE env var, "
            "--app-code flag, or X-phpIPAM-App-Code header)",
            kind="config",
        )

    return {
        "base_url": base_url.rstrip("/"),
        "app_id": app_id,
        "token": token,
        "verify_ssl": verify_ssl,
    }


def make_request(
    endpoint: str,
    method: str = "GET",
    data: dict | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> dict:
    """Make an authenticated request to the phpIPAM API.

    Args:
        endpoint: API path relative to ``/api/<app_id>/`` (e.g. ``"sections/"``).
        method: HTTP method.
        data: optional JSON body.
        config: pre-resolved config from :func:`get_phpipam_config`; resolved
            from env/headers when omitted.

    Raises:
        PhpIpamError: classified by failure kind (auth/notfound/network/api).
    """
    if config is None:
        config = get_phpipam_config()

    url = f"{config['base_url']}/api/{config['app_id']}/{endpoint.lstrip('/')}"
    headers = {"Content-Type": "application/json", "token": config["token"]}

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            verify=config["verify_ssl"],
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in (401, 403):
            raise PhpIpamError(
                "Authentication failed. Check PHPIPAM_APP_CODE (app code token).",
                kind="auth",
            ) from exc
        if status == 404:
            raise PhpIpamError(
                "Resource not found. Check the provided ID or parameters.",
                kind="notfound",
            ) from exc
        raise PhpIpamError(f"phpIPAM API error (HTTP {status}): {exc}", kind="api") from exc
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        raise PhpIpamError(
            f"Connection failed: {exc}. Check network connectivity and PHPIPAM_URL.",
            kind="network",
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise PhpIpamError(f"Request failed: {exc}", kind="api") from exc
    except ValueError as exc:  # JSON decode
        raise PhpIpamError(f"Invalid JSON response from phpIPAM: {exc}", kind="api") from exc


# ---------------------------------------------------------------------------
# Response shaping helpers (shared with the MCP server)
# ---------------------------------------------------------------------------
def filter_fields(data, include_fields=None, exclude_fields=None):
    """Filter fields from API response data to reduce payload size.

    Args:
        data: API response data (dict or list of dicts).
        include_fields: if given, only these keys are kept.
        exclude_fields: keys to drop (ignored when ``include_fields`` is set).
    """
    if not isinstance(data, (dict, list)):
        return data

    def filter_single_item(item):
        if not isinstance(item, dict):
            return item
        if include_fields:
            return {k: v for k, v in item.items() if k in include_fields}
        if exclude_fields:
            return {k: v for k, v in item.items() if k not in exclude_fields}
        return item

    if isinstance(data, list):
        return [filter_single_item(item) for item in data]
    return filter_single_item(data)


def apply_field_filtering(data, include_fields, default_fields):
    """Apply field filtering with an 'all' escape hatch.

    ``include_fields="all"`` returns data unfiltered; a comma-separated string
    selects those fields; empty falls back to ``default_fields``.
    """
    if include_fields == "all":
        return data
    if include_fields:
        fields = [f.strip() for f in include_fields.split(",")]
        return filter_fields(data, include_fields=fields)
    return filter_fields(data, include_fields=default_fields)


def apply_result_limit(data, limit, max_limit):
    """Truncate ``data`` to ``min(limit, max_limit)`` items.

    Returns ``(data, truncated)`` where ``truncated`` is True if items dropped.
    """
    limit = min(limit, max_limit)
    if len(data) > limit:
        return data[:limit], True
    return data, False
