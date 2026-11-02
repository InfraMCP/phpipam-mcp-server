#!/usr/bin/env python3
"""phpipam - an agent-friendly command-line interface for phpIPAM.

Design goals
------------
* **Predictable for automation.** Every command accepts ``--json`` for
  machine-readable output; errors in JSON mode are a single JSON object on
  stderr. Exit codes are stable and documented (see ``EXIT_*`` below), so an
  agent can branch on the code without parsing text.
* **No env plumbing required.** Credentials come from ``PHPIPAM_URL`` /
  ``PHPIPAM_APP_ID`` / ``PHPIPAM_APP_CODE`` env vars OR from ``--url`` /
  ``--app-id`` / ``--app-code`` flags, so the tool runs standalone.
* **Safe by default.** Read commands just run. Destructive write commands
  (create/update/delete) refuse to run unless ``--yes`` is passed, and print
  exactly what they will do first.

Exit codes
----------
* 0  success
* 1  phpIPAM API / network error
* 2  usage error (bad arguments) - argparse default
* 3  configuration error (missing credentials)
* 4  authentication rejected by phpIPAM
* 5  resource not found
* 6  refused: a write was requested without --yes
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .client import PhpIpamError, get_phpipam_config, make_request

try:
    # Reading distribution metadata avoids importing the package __init__
    # (which pulls in the MCP server stack) just to learn the version.
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("phpipam-mcp-server")
    except PackageNotFoundError:  # running from a source tree, not installed
        __version__ = "0.0.0+src"
except ImportError:  # pragma: no cover - importlib.metadata always present on 3.10+
    __version__ = "0.0.0"

EXIT_OK = 0
EXIT_API = 1
EXIT_USAGE = 2
EXIT_CONFIG = 3
EXIT_AUTH = 4
EXIT_NOTFOUND = 5
EXIT_REFUSED = 6

_KIND_TO_EXIT = {
    "config": EXIT_CONFIG,
    "auth": EXIT_AUTH,
    "notfound": EXIT_NOTFOUND,
    "network": EXIT_API,
    "api": EXIT_API,
}

# Secret-bearing env/flag names we must never echo back in output.
_SECRET_KEYS = {"token", "app_code"}


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def _emit(args, *, data: Any, human: str) -> None:
    """Print a successful result as JSON or human text."""
    if args.json:
        json.dump({"ok": True, "data": data}, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(human.rstrip("\n") + "\n")


def _fail(args, *, message: str, kind: str) -> int:
    """Print a structured error and return the matching exit code."""
    exit_code = _KIND_TO_EXIT.get(kind, EXIT_API)
    if args.json:
        json.dump(
            {"ok": False, "error": {"kind": kind, "message": message}},
            sys.stderr,
            indent=2,
            default=str,
        )
        sys.stderr.write("\n")
    else:
        sys.stderr.write(f"error ({kind}): {message}\n")
    return exit_code


def _config_overrides(args) -> dict[str, Any]:
    """Build the config-override dict from global CLI flags."""
    overrides: dict[str, Any] = {
        "base_url": args.url,
        "app_id": args.app_id,
        "token": args.app_code,
    }
    if args.no_verify_ssl:
        overrides["verify_ssl"] = False
    return overrides


def _resolved_config(args) -> dict[str, Any]:
    """Resolve credentials from flags/env, raising PhpIpamError(kind=config)."""
    return get_phpipam_config(_config_overrides(args))


def _api(args, endpoint: str, method: str = "GET", data: dict | None = None) -> dict:
    """Resolve config and make one API call (raises PhpIpamError)."""
    config = _resolved_config(args)
    return make_request(endpoint, method=method, data=data, config=config)


def _unwrap(result: dict) -> list:
    """Return the ``data`` list from a phpIPAM response, raising on failure."""
    if not result.get("success"):
        raise PhpIpamError(result.get("message", "Unknown API error"), kind="api")
    data = result.get("data", [])
    return data if isinstance(data, list) else [data]


def _truncate(items: list, limit: int) -> tuple[list, bool]:
    if limit and len(items) > limit:
        return items[:limit], True
    return items, False


# ---------------------------------------------------------------------------
# Read command handlers
# ---------------------------------------------------------------------------
def cmd_sections(args) -> int:
    rows = _unwrap(_api(args, "sections/"))
    rows, truncated = _truncate(rows, args.limit)
    lines = [
        f"{r.get('id'):>4}  {r.get('name', '')}  -  {r.get('description') or 'N/A'}"
        for r in rows
    ]
    header = f"{len(rows)} sections"
    if truncated:
        header += f" (showing first {args.limit})"
    _emit(args, data=rows, human=header + ":\n" + "\n".join(lines))
    return EXIT_OK


def cmd_subnets(args) -> int:
    rows = _unwrap(_api(args, f"sections/{args.section_id}/subnets/"))
    rows, truncated = _truncate(rows, args.limit)
    lines = []
    for r in rows:
        cidr = f"{r.get('subnet')}/{r.get('mask')}"
        lines.append(f"{r.get('id'):>6}  {cidr:<20}  {r.get('description') or 'N/A'}")
    header = f"{len(rows)} subnets in section {args.section_id}"
    if truncated:
        header += f" (showing first {args.limit})"
    _emit(args, data=rows, human=header + ":\n" + "\n".join(lines))
    return EXIT_OK


def cmd_subnet(args) -> int:
    result = _api(args, f"subnets/{args.subnet_id}/")
    if not result.get("success"):
        raise PhpIpamError(result.get("message", "Subnet not found"), kind="notfound")
    subnet = result.get("data", {})
    human = (
        f"Subnet {args.subnet_id} ({subnet.get('subnet')}/{subnet.get('mask')})\n"
        f"Description: {subnet.get('description') or 'N/A'}\n"
        f"Section ID: {subnet.get('sectionId')}"
    )
    _emit(args, data=subnet, human=human)
    return EXIT_OK


def cmd_search_address(args) -> int:
    rows = _unwrap(_api(args, f"addresses/search/{args.query}/"))
    rows, truncated = _truncate(rows, args.limit)
    lines = [
        f"{r.get('id'):>6}  {r.get('ip'):<18}  {r.get('hostname') or 'N/A'}"
        for r in rows
    ]
    header = f"{len(rows)} addresses matching '{args.query}'"
    if truncated:
        header += f" (showing first {args.limit})"
    _emit(args, data=rows, human=header + ":\n" + "\n".join(lines))
    return EXIT_OK


def cmd_search_hostname(args) -> int:
    rows = _unwrap(_api(args, f"addresses/search_hostname/{args.hostname}/"))
    rows, truncated = _truncate(rows, args.limit)
    lines = [
        f"{r.get('id'):>6}  {r.get('ip'):<18}  {r.get('hostname') or 'N/A'}"
        for r in rows
    ]
    header = f"{len(rows)} addresses matching hostname '{args.hostname}'"
    if truncated:
        header += f" (showing first {args.limit})"
    _emit(args, data=rows, human=header + ":\n" + "\n".join(lines))
    return EXIT_OK


def cmd_search_subnet(args) -> int:
    rows = _unwrap(_api(args, f"subnets/search/{args.query}/"))
    rows, truncated = _truncate(rows, args.limit)
    lines = []
    for r in rows:
        cidr = f"{r.get('subnet')}/{r.get('mask')}"
        lines.append(f"{r.get('id'):>6}  {cidr:<20}  {r.get('description') or 'N/A'}")
    header = f"{len(rows)} subnets matching '{args.query}'"
    if truncated:
        header += f" (showing first {args.limit})"
    _emit(args, data=rows, human=header + ":\n" + "\n".join(lines))
    return EXIT_OK


def cmd_vlans(args) -> int:
    endpoint = f"l2domains/{args.domain_id}/vlans/" if args.domain_id else "vlan/"
    rows = _unwrap(_api(args, endpoint))
    rows, truncated = _truncate(rows, args.limit)
    lines = [
        f"{r.get('vlanId'):>6}  vlan {r.get('number', 'N/A'):<6}  {r.get('name') or 'N/A'}"
        for r in rows
    ]
    header = f"{len(rows)} VLANs"
    if truncated:
        header += f" (showing first {args.limit})"
    _emit(args, data=rows, human=header + ":\n" + "\n".join(lines))
    return EXIT_OK


def cmd_vrfs(args) -> int:
    rows = _unwrap(_api(args, "vrf/"))
    rows, truncated = _truncate(rows, args.limit)
    lines = [
        f"{r.get('vrfId'):>6}  {r.get('name') or 'N/A':<24}  rd={r.get('rd') or 'N/A'}"
        for r in rows
    ]
    header = f"{len(rows)} VRFs"
    if truncated:
        header += f" (showing first {args.limit})"
    _emit(args, data=rows, human=header + ":\n" + "\n".join(lines))
    return EXIT_OK


def cmd_locations(args) -> int:
    rows = _unwrap(_api(args, "tools/locations/"))
    rows, truncated = _truncate(rows, args.limit)
    lines = [
        f"{r.get('id'):>6}  {r.get('name') or 'N/A':<24}  {r.get('address') or 'N/A'}"
        for r in rows
    ]
    header = f"{len(rows)} locations"
    if truncated:
        header += f" (showing first {args.limit})"
    _emit(args, data=rows, human=header + ":\n" + "\n".join(lines))
    return EXIT_OK


def cmd_nameservers(args) -> int:
    rows = _unwrap(_api(args, "tools/nameservers/"))
    rows, truncated = _truncate(rows, args.limit)
    lines = [
        f"{r.get('id'):>6}  {r.get('name') or 'N/A':<24}  {r.get('namesrv1') or 'N/A'}"
        for r in rows
    ]
    header = f"{len(rows)} nameservers"
    if truncated:
        header += f" (showing first {args.limit})"
    _emit(args, data=rows, human=header + ":\n" + "\n".join(lines))
    return EXIT_OK


# ---------------------------------------------------------------------------
# Write command handlers (guarded by --yes)
# ---------------------------------------------------------------------------
def _require_confirmation(args, description: str) -> int | None:
    """Return an exit code if the write is refused, else None to proceed."""
    if args.yes:
        return None
    msg = (
        f"refusing to run a write operation without confirmation.\n"
        f"would: {description}\n"
        f"re-run with --yes to proceed."
    )
    if args.json:
        json.dump(
            {"ok": False, "error": {"kind": "refused", "message": msg,
                                    "would": description}},
            sys.stderr, indent=2, default=str,
        )
        sys.stderr.write("\n")
    else:
        sys.stderr.write(f"error (refused): {msg}\n")
    return EXIT_REFUSED


def cmd_create_subnet(args) -> int:
    desc = f"create subnet {args.subnet}/{args.mask} in section {args.section_id}"
    refused = _require_confirmation(args, desc)
    if refused is not None:
        return refused
    payload = {
        "subnet": args.subnet,
        "mask": args.mask,
        "sectionId": args.section_id,
        "description": args.description or "",
    }
    if args.vlan_id:
        payload["vlanId"] = args.vlan_id
    result = _api(args, "subnets/", method="POST", data=payload)
    if not result.get("success"):
        raise PhpIpamError(result.get("message", "Failed to create subnet"), kind="api")
    _emit(args, data=result, human=f"created subnet {args.subnet}/{args.mask} "
                                   f"(id {result.get('id')})")
    return EXIT_OK


def cmd_reserve_ip(args) -> int:
    target = args.ip or "first available"
    desc = f"reserve IP {target} in subnet {args.subnet_id}"
    refused = _require_confirmation(args, desc)
    if refused is not None:
        return refused
    payload = {
        "subnetId": args.subnet_id,
        "hostname": args.hostname or "",
        "description": args.description or "",
        "owner": args.owner or "",
    }
    if args.ip:
        payload["ip"] = args.ip
    result = _api(args, "addresses/", method="POST", data=payload)
    if not result.get("success"):
        raise PhpIpamError(result.get("message", "Failed to reserve IP"), kind="api")
    _emit(args, data=result, human=f"reserved IP (id {result.get('id')})")
    return EXIT_OK


def cmd_update_ip(args) -> int:
    fields = {k: v for k, v in (
        ("hostname", args.hostname),
        ("description", args.description),
        ("owner", args.owner),
    ) if v is not None}
    if not fields:
        return _fail(args, message="no fields given to update", kind="api")
    desc = f"update IP {args.address_id}: {', '.join(fields)}"
    refused = _require_confirmation(args, desc)
    if refused is not None:
        return refused
    result = _api(args, f"addresses/{args.address_id}/", method="PATCH", data=fields)
    if not result.get("success"):
        raise PhpIpamError(result.get("message", "Failed to update IP"), kind="api")
    _emit(args, data=result, human=f"updated IP {args.address_id}")
    return EXIT_OK


def cmd_delete_ip(args) -> int:
    desc = f"DELETE IP reservation {args.address_id}"
    refused = _require_confirmation(args, desc)
    if refused is not None:
        return refused
    result = _api(args, f"addresses/{args.address_id}/", method="DELETE")
    if not result.get("success"):
        raise PhpIpamError(result.get("message", "Failed to delete IP"), kind="api")
    _emit(args, data=result, human=f"deleted IP {args.address_id}")
    return EXIT_OK


def cmd_update_subnet(args) -> int:
    fields = {k: v for k, v in (
        ("description", args.description),
        ("vlanId", args.vlan_id),
        ("vrfId", args.vrf_id),
    ) if v is not None}
    if not fields:
        return _fail(args, message="no fields given to update", kind="api")
    desc = f"update subnet {args.subnet_id}: {', '.join(fields)}"
    refused = _require_confirmation(args, desc)
    if refused is not None:
        return refused
    result = _api(args, f"subnets/{args.subnet_id}/", method="PATCH", data=fields)
    if not result.get("success"):
        raise PhpIpamError(result.get("message", "Failed to update subnet"), kind="api")
    _emit(args, data=result, human=f"updated subnet {args.subnet_id}")
    return EXIT_OK


def cmd_delete_subnet(args) -> int:
    desc = (f"DELETE subnet {args.subnet_id} "
            f"(this removes ALL IP addresses in the subnet)")
    refused = _require_confirmation(args, desc)
    if refused is not None:
        return refused
    result = _api(args, f"subnets/{args.subnet_id}/", method="DELETE")
    if not result.get("success"):
        raise PhpIpamError(result.get("message", "Failed to delete subnet"), kind="api")
    _emit(args, data=result, human=f"deleted subnet {args.subnet_id}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:  # pylint: disable=too-many-statements
    # A flat, declarative parser definition: one block per subcommand. Splitting
    # it would scatter closely-related argument declarations across helpers for
    # no real readability gain, so the statement-count check is waived here.
    parser = argparse.ArgumentParser(
        prog="phpipam",
        description="Agent-friendly CLI for phpIPAM. Credentials come from "
                    "PHPIPAM_URL / PHPIPAM_APP_ID / PHPIPAM_APP_CODE env vars "
                    "or the --url / --app-id / --app-code flags.",
        epilog="Exit codes: 0 ok, 1 api/network, 2 usage, 3 config, "
               "4 auth, 5 not-found, 6 refused (write without --yes).",
    )
    parser.add_argument("--version", action="version",
                        version=f"phpipam {__version__}")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON (errors to stderr).")
    parser.add_argument("--url", default=None,
                        help="phpIPAM base URL (overrides PHPIPAM_URL).")
    parser.add_argument("--app-id", default=None,
                        help="phpIPAM App ID (overrides PHPIPAM_APP_ID).")
    parser.add_argument("--app-code", default=None,
                        help="phpIPAM App Code token (overrides PHPIPAM_APP_CODE). "
                             "Prefer the env var; a flag value is visible in "
                             "the process list.")
    parser.add_argument("--no-verify-ssl", action="store_true",
                        help="disable TLS certificate verification (insecure).")

    sub = parser.add_subparsers(dest="command", required=True,
                                metavar="<command>")

    def add_limit(p, default=20):
        p.add_argument("--limit", type=int, default=default,
                       help=f"max rows to return (default {default}, 0 = all).")

    # --- read commands ---
    p = sub.add_parser("sections", help="list IP sections")
    add_limit(p)
    p.set_defaults(func=cmd_sections)

    p = sub.add_parser("subnets", help="list subnets in a section")
    p.add_argument("section_id")
    add_limit(p)
    p.set_defaults(func=cmd_subnets)

    p = sub.add_parser("subnet", help="show one subnet's details")
    p.add_argument("subnet_id")
    p.set_defaults(func=cmd_subnet)

    p = sub.add_parser("search-address", help="search addresses by IP or hostname")
    p.add_argument("query")
    add_limit(p, 10)
    p.set_defaults(func=cmd_search_address)

    p = sub.add_parser("search-hostname", help="search addresses by hostname")
    p.add_argument("hostname")
    add_limit(p, 10)
    p.set_defaults(func=cmd_search_hostname)

    p = sub.add_parser("search-subnet", help="search subnets by CIDR/description")
    p.add_argument("query")
    add_limit(p, 10)
    p.set_defaults(func=cmd_search_subnet)

    p = sub.add_parser("vlans", help="list VLANs")
    p.add_argument("--domain-id", default=None, help="filter by L2 domain ID.")
    add_limit(p)
    p.set_defaults(func=cmd_vlans)

    p = sub.add_parser("vrfs", help="list VRFs")
    add_limit(p)
    p.set_defaults(func=cmd_vrfs)

    p = sub.add_parser("locations", help="list physical locations")
    add_limit(p)
    p.set_defaults(func=cmd_locations)

    p = sub.add_parser("nameservers", help="list DNS nameservers")
    add_limit(p)
    p.set_defaults(func=cmd_nameservers)

    # --- write commands (need --yes) ---
    def add_yes(p):
        p.add_argument("--yes", action="store_true",
                       help="confirm this write operation (required).")

    p = sub.add_parser("create-subnet", help="create a subnet (write)")
    p.add_argument("section_id")
    p.add_argument("subnet", help="network address, e.g. 192.168.1.0")
    p.add_argument("mask", help="prefix length, e.g. 24")
    p.add_argument("--description", default=None)
    p.add_argument("--vlan-id", default=None)
    add_yes(p)
    p.set_defaults(func=cmd_create_subnet)

    p = sub.add_parser("reserve-ip", help="reserve an IP in a subnet (write)")
    p.add_argument("subnet_id")
    p.add_argument("--ip", default=None, help="specific IP; omit for first free.")
    p.add_argument("--hostname", default=None)
    p.add_argument("--description", default=None)
    p.add_argument("--owner", default=None)
    add_yes(p)
    p.set_defaults(func=cmd_reserve_ip)

    p = sub.add_parser("update-ip", help="update an IP record (write)")
    p.add_argument("address_id")
    p.add_argument("--hostname", default=None)
    p.add_argument("--description", default=None)
    p.add_argument("--owner", default=None)
    add_yes(p)
    p.set_defaults(func=cmd_update_ip)

    p = sub.add_parser("delete-ip", help="delete an IP reservation (write)")
    p.add_argument("address_id")
    add_yes(p)
    p.set_defaults(func=cmd_delete_ip)

    p = sub.add_parser("update-subnet", help="update a subnet (write)")
    p.add_argument("subnet_id")
    p.add_argument("--description", default=None)
    p.add_argument("--vlan-id", default=None)
    p.add_argument("--vrf-id", default=None)
    add_yes(p)
    p.set_defaults(func=cmd_update_subnet)

    p = sub.add_parser("delete-subnet",
                       help="delete a subnet and ALL its addresses (write)")
    p.add_argument("subnet_id")
    add_yes(p)
    p.set_defaults(func=cmd_delete_subnet)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PhpIpamError as exc:
        return _fail(args, message=str(exc), kind=exc.kind)
    except KeyboardInterrupt:  # pragma: no cover
        sys.stderr.write("interrupted\n")
        return EXIT_API
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return _fail(args, message=f"unexpected error: {exc}", kind="api")


if __name__ == "__main__":
    sys.exit(main())
