"""Tests for the phpipam agent-friendly CLI.

These exercise the CLI end-to-end against a mocked ``requests`` layer, so they
run offline and assert on the contract that matters to automation: exit codes,
JSON shape, and the write-confirmation guard.
"""

import json
from unittest.mock import patch

import pytest

from phpipam_mcp_server import cli
from phpipam_mcp_server.client import PhpIpamError

# Credentials supplied via flags so the tests never depend on the environment.
CREDS = ["--url", "https://ipam.example/", "--app-id", "app", "--app-code", "tok"]


def run(argv):
    """Invoke the CLI, returning its exit code."""
    return cli.main(argv)


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        import requests

        if self.status_code >= 400:
            err = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err


# ---------------------------------------------------------------------------
# Read commands
# ---------------------------------------------------------------------------
def test_sections_json_ok(capsys):
    payload = {"success": True, "data": [{"id": 1, "name": "Prod", "description": "x"}]}
    with patch("phpipam_mcp_server.client.requests.request",
               return_value=_FakeResponse(payload)):
        code = run(CREDS + ["--json", "sections"])
    out = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_OK
    assert out["ok"] is True
    assert out["data"][0]["name"] == "Prod"


def test_sections_human_ok(capsys):
    payload = {"success": True, "data": [{"id": 7, "name": "DC", "description": None}]}
    with patch("phpipam_mcp_server.client.requests.request",
               return_value=_FakeResponse(payload)):
        code = run(CREDS + ["sections"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "DC" in out and "1 sections" in out


def test_subnets_limit_truncates(capsys):
    data = [{"id": i, "subnet": f"10.0.{i}.0", "mask": "24", "description": ""}
            for i in range(5)]
    payload = {"success": True, "data": data}
    with patch("phpipam_mcp_server.client.requests.request",
               return_value=_FakeResponse(payload)):
        code = run(CREDS + ["--json", "subnets", "3", "--limit", "2"])
    out = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_OK
    assert len(out["data"]) == 2


# ---------------------------------------------------------------------------
# Error classification -> exit codes
# ---------------------------------------------------------------------------
def test_missing_config_exit_3(capsys):
    # No creds anywhere: get_phpipam_config raises kind="config".
    with patch.dict("os.environ", {}, clear=True):
        code = run(["--json", "sections"])
    err = json.loads(capsys.readouterr().err)
    assert code == cli.EXIT_CONFIG
    assert err["error"]["kind"] == "config"


def test_auth_failure_exit_4(capsys):
    with patch("phpipam_mcp_server.client.requests.request",
               return_value=_FakeResponse({}, status=401)):
        code = run(CREDS + ["--json", "sections"])
    err = json.loads(capsys.readouterr().err)
    assert code == cli.EXIT_AUTH
    assert err["error"]["kind"] == "auth"


def test_notfound_exit_5(capsys):
    with patch("phpipam_mcp_server.client.requests.request",
               return_value=_FakeResponse({}, status=404)):
        code = run(CREDS + ["--json", "subnet", "999"])
    err = json.loads(capsys.readouterr().err)
    assert code == cli.EXIT_NOTFOUND
    assert err["error"]["kind"] == "notfound"


# ---------------------------------------------------------------------------
# Write guard
# ---------------------------------------------------------------------------
def test_delete_subnet_refused_without_yes(capsys):
    called = {"n": 0}

    def _spy(*a, **k):
        called["n"] += 1
        return _FakeResponse({"success": True})

    with patch("phpipam_mcp_server.client.requests.request", side_effect=_spy):
        code = run(CREDS + ["--json", "delete-subnet", "42"])
    err = json.loads(capsys.readouterr().err)
    assert code == cli.EXIT_REFUSED
    assert err["error"]["kind"] == "refused"
    assert called["n"] == 0  # no API call was made


def test_delete_subnet_proceeds_with_yes(capsys):
    payload = {"success": True, "data": "deleted"}
    with patch("phpipam_mcp_server.client.requests.request",
               return_value=_FakeResponse(payload)) as req:
        code = run(CREDS + ["--json", "delete-subnet", "42", "--yes"])
    out = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_OK
    assert out["ok"] is True
    assert req.called
    # Confirm it issued a DELETE.
    assert req.call_args.kwargs["method"] == "DELETE"


def test_create_subnet_refused_makes_no_call():
    with patch("phpipam_mcp_server.client.requests.request") as req:
        code = run(CREDS + ["create-subnet", "1", "192.168.5.0", "24"])
    assert code == cli.EXIT_REFUSED
    assert not req.called


# ---------------------------------------------------------------------------
# client-layer unit checks
# ---------------------------------------------------------------------------
def test_config_overrides_win_over_env():
    from phpipam_mcp_server.client import get_phpipam_config

    with patch.dict("os.environ",
                    {"PHPIPAM_URL": "https://env/", "PHPIPAM_APP_ID": "envid",
                     "PHPIPAM_APP_CODE": "envtok"}, clear=True):
        cfg = get_phpipam_config({"base_url": "https://flag/", "app_id": None,
                                  "token": None})
    assert cfg["base_url"] == "https://flag"  # trailing slash stripped
    assert cfg["app_id"] == "envid"  # None override falls through to env


def test_phpipam_error_kind_defaults_to_api():
    assert PhpIpamError("x").kind == "api"
