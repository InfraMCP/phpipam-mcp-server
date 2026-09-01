#!/usr/bin/env python3
"""phpIPAM MCP Server - Provides phpIPAM API access through MCP protocol.

Supports two transports:

* ``stdio``           : classic local mode (default, backwards compatible).
* ``streamable-http`` : remote mode, exposes the server on an HTTP endpoint
                        (e.g. https://phpipam.domaine.com/mcp) behind a reverse
                        proxy that terminates TLS.

Configuration (environment variables)
--------------------------------------
Transport / network:
    MCP_TRANSPORT     "stdio" (default) or "streamable-http"
    MCP_HOST          bind address in HTTP mode (default "0.0.0.0")
    MCP_PORT          bind port in HTTP mode (default "8000")
    MCP_PATH          HTTP path for the MCP endpoint (default "/mcp")
    MCP_BEARER_TOKEN  if set, clients must send "Authorization: Bearer <token>"

phpIPAM credentials (server-wide fallback; can be overridden per client
through HTTP headers in remote mode):
    PHPIPAM_URL, PHPIPAM_APP_ID, PHPIPAM_APP_CODE
    PHPIPAM_VERIFY_SSL  "true" (default) / "false"

Per-client phpIPAM credentials (remote mode, sent as HTTP headers):
    X-phpIPAM-URL, X-phpIPAM-App-Id, X-phpIPAM-App-Code, X-phpIPAM-Verify-Ssl
"""

import contextvars
import hmac
import os

import requests
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Remote (HTTP) request context
# ---------------------------------------------------------------------------
# In HTTP mode an ASGI middleware stores the incoming request headers here so
# that the tool functions can resolve per-client phpIPAM credentials without
# having to thread a Context object through every tool.
_request_headers: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "phpipam_request_headers", default={}
)


def _env_truthy(value: str | None, default: bool = True) -> bool:
    """Interpret an environment/header string as a boolean."""
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off", "")


# Create MCP server. Host/port/path only matter for the HTTP transport.
mcp = FastMCP(
    "phpIPAM Server",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    streamable_http_path=os.getenv("MCP_PATH", "/mcp"),
    # Stateless + JSON responses keep the remote endpoint simple and scalable
    # behind a reverse proxy / load balancer.
    stateless_http=True,
    json_response=True,
)


def get_phpipam_config():
    """Resolve phpIPAM configuration.

    Resolution order for each value:
      1. Per-client HTTP header (remote mode), e.g. ``X-phpIPAM-URL``.
      2. Server-wide environment variable, e.g. ``PHPIPAM_URL``.
    """
    headers = _request_headers.get()

    base_url = headers.get("x-phpipam-url") or os.getenv("PHPIPAM_URL")
    app_id = headers.get("x-phpipam-app-id") or os.getenv("PHPIPAM_APP_ID")
    token = headers.get("x-phpipam-app-code") or os.getenv("PHPIPAM_APP_CODE")

    verify_raw = headers.get("x-phpipam-verify-ssl")
    if verify_raw is None:
        verify_raw = os.getenv("PHPIPAM_VERIFY_SSL")
    verify_ssl = _env_truthy(verify_raw, default=True)

    if not base_url:
        raise ValueError(
            "phpIPAM URL is required (PHPIPAM_URL env var or X-phpIPAM-URL header)"
        )
    if not app_id:
        raise ValueError(
            "phpIPAM App ID is required "
            "(PHPIPAM_APP_ID env var or X-phpIPAM-App-Id header)"
        )
    if not token:
        raise ValueError(
            "phpIPAM App Code is required "
            "(PHPIPAM_APP_CODE env var or X-phpIPAM-App-Code header)"
        )

    return {
        'base_url': base_url.rstrip('/'),
        'app_id': app_id,
        'token': token,
        'verify_ssl': verify_ssl
    }

def filter_fields(data, include_fields=None, exclude_fields=None):
    """Filter fields from API response data to reduce context window usage.

    Args:
        data: API response data (dict or list of dicts)
        include_fields: List of fields to keep (if specified, only these are kept)
        exclude_fields: List of fields to remove (ignored if include_fields is specified)
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

def format_subnet_output(subnets, section_id, limit, truncated, include_usage):
    """Format subnet data for compact output."""
    output = f"Found {len(subnets)} subnets in section {section_id}"
    if truncated:
        output += f" (showing first {limit})"
    output += ":\n"

    for subnet in subnets:
        cidr = f"{subnet.get('subnet')}/{subnet.get('mask')}"
        desc = subnet.get('description', 'N/A')
        if desc and len(desc) > 50:
            desc = desc[:50] + "..."
        elif not desc:
            desc = 'N/A'
        output += f"ID: {subnet.get('id')}, CIDR: {cidr}, Desc: {desc}"

        if include_usage and subnet.get('usage'):
            usage = subnet['usage']
            used_pct = usage.get('Used_percent', 0)
            free_pct = usage.get('freehosts_percent', 0)
            output += f", Used: {used_pct:.1f}%, Free: {free_pct:.1f}%"
        output += "\n"
    return output

def format_address_output(addresses, search_term, limit, truncated):
    """Format address data for compact output."""
    output = f"Found {len(addresses)} addresses matching '{search_term}'"
    if truncated:
        output += f" (showing first {limit})"
    output += ":\n"

    for addr in addresses:
        hostname = addr.get('hostname', 'N/A')
        desc = addr.get('description', 'N/A')
        if desc and len(desc) > 30:
            desc = desc[:30] + "..."
        output += f"ID: {addr.get('id')}, IP: {addr.get('ip')}, Host: {hostname}, Desc: {desc}\n"
    return output

def format_vlan_output(vlans, limit, truncated):
    """Format VLAN data for compact output."""
    output = f"Found {len(vlans)} VLANs"
    if truncated:
        output += f" (showing first {limit})"
    output += ":\n"

    for vlan in vlans:
        name = vlan.get('name', 'N/A')
        number = vlan.get('number', 'N/A')
        desc = vlan.get('description', 'N/A')
        if desc and len(desc) > 40:
            desc = desc[:40] + "..."
        output += f"ID: {vlan.get('vlanId')}, Number: {number}, "
        output += f"Name: {name}, Desc: {desc}\n"
    return output

def format_subnet_details(subnet, subnet_id, include_addresses, address_limit):
    """Format subnet details with optional addresses."""
    cidr = f"{subnet.get('subnet')}/{subnet.get('mask')}"
    desc = subnet.get('description', 'N/A')

    response = f"Subnet {subnet_id} ({cidr}):\n"
    response += f"Description: {desc}\n"
    response += f"Section ID: {subnet.get('sectionId')}\n"

    if subnet.get('usage'):
        usage = subnet['usage']
        used = usage.get('Used', 0)
        used_pct = usage.get('Used_percent', 0)
        free = usage.get('freehosts', 0)
        free_pct = usage.get('freehosts_percent', 0)
        response += f"Usage: {used} used ({used_pct:.1f}%), {free} free ({free_pct:.1f}%)\n"

    if include_addresses:
        response += get_subnet_addresses(subnet_id, address_limit)

    return response

def get_subnet_addresses(subnet_id, address_limit):
    """Get and format subnet addresses."""
    try:
        addr_result = make_request(f"subnets/{subnet_id}/addresses/")
        if not addr_result.get('success'):
            return "\nCould not retrieve addresses for this subnet"

        addresses = addr_result.get('data', [])
        if not addresses:
            return "\nNo addresses found in this subnet"

        # Apply limit
        address_limit = min(address_limit, 50)
        if len(addresses) > address_limit:
            addresses = addresses[:address_limit]
            truncated = True
        else:
            truncated = False

        response = f"\nAddresses ({len(addresses)}"
        if truncated:
            response += f", showing first {address_limit}"
        response += "):\n"

        for addr in addresses:
            ip = addr.get('ip')
            hostname = addr.get('hostname', 'N/A')
            if hostname and len(hostname) > 25:
                hostname = hostname[:25] + "..."
            response += f"  {ip} - {hostname}\n"
        return response

    except Exception:  # pylint: disable=broad-exception-caught
        return "\nCould not retrieve addresses for this subnet"

def apply_field_filtering(data, include_fields, default_fields):
    """Apply field filtering to data."""
    if include_fields == "all":
        return data
    if include_fields:
        fields = [f.strip() for f in include_fields.split(',')]
        return filter_fields(data, include_fields=fields)
    return filter_fields(data, include_fields=default_fields)

def apply_result_limit(data, limit, max_limit):
    """Apply result limiting with truncation tracking."""
    limit = min(limit, max_limit)
    if len(data) > limit:
        return data[:limit], True
    return data, False

def _handle_error(e: Exception, operation: str) -> str:
    """Handle errors consistently across all tools."""
    error_msg = str(e)

    if "401" in error_msg or "Unauthorized" in error_msg:
        return (
            f"Authentication failed for {operation}. "
            "Check PHPIPAM_APP_CODE (app code token) environment variable."
        )
    if "Connection" in error_msg or "timeout" in error_msg.lower():
        return f"Connection failed for {operation}. Check network connectivity and PHPIPAM_URL."
    if "404" in error_msg:
        return f"Resource not found for {operation}. Check the provided ID or parameters."
    return f"Error in {operation}: {error_msg}"

def make_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Make authenticated request to phpIPAM API."""
    config = get_phpipam_config()
    url = f"{config['base_url']}/api/{config['app_id']}/{endpoint.lstrip('/')}"

    headers = {
        'Content-Type': 'application/json',
        'token': config['token']
    }

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=data,
        verify=config['verify_ssl'],
        timeout=30
    )
    response.raise_for_status()
    return response.json()

@mcp.tool()
def list_sections(include_fields: str = "") -> str:
    """List all IP sections from phpIPAM.

    CONTEXT OPTIMIZATION: Returns essential fields only by default.
    Use include_fields="all" for complete data.

    Args:
        include_fields: Comma-separated fields to include (default: essential only)
                       Use "all" for complete data
    """
    try:
        result = make_request("sections/")

        if not result.get('success'):
            return f"API Error: {result.get('message', 'Unknown error')}"

        sections = result.get('data', [])

        # Apply field filtering
        if include_fields == "all":
            pass
        elif include_fields:
            fields = [f.strip() for f in include_fields.split(',')]
            sections = filter_fields(sections, include_fields=fields)
        else:
            # Minimal essential fields for context optimization
            essential_fields = ['id', 'name', 'description']
            sections = filter_fields(sections, include_fields=essential_fields)

        # Format as compact table for better readability
        if sections:
            output = f"Found {len(sections)} sections:\n"
            for section in sections:
                output += f"ID: {section.get('id')}, Name: {section.get('name')}, "
                output += f"Description: {section.get('description', 'N/A')}\n"
            return output
        return "No sections found"

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, "listing sections")

@mcp.tool()
def get_section_subnets(section_id: str, include_usage: bool = True,
                       include_fields: str = "", limit: int = 20) -> str:
    """Get subnets within a specific section.

    CONTEXT OPTIMIZATION: Limited to 20 results by default.
    Use limit parameter to control output size.

    Args:
        section_id: Section ID to get subnets from
        include_usage: Include usage statistics (default: True)
        include_fields: Comma-separated fields to include (default: essential only)
        limit: Maximum number of subnets to return (default: 20, max: 100)
    """
    try:
        result = make_request(f"sections/{section_id}/subnets/")

        if not result.get('success'):
            return f"API Error: {result.get('message', 'Unknown error')}"

        subnets = result.get('data', [])
        if not subnets:
            return f"No subnets found in section {section_id}"

        # Apply limit and field filtering
        subnets, truncated = apply_result_limit(subnets, limit, 100)

        default_fields = ['id', 'subnet', 'mask', 'description']
        if include_usage:
            default_fields.append('usage')
        subnets = apply_field_filtering(subnets, include_fields, default_fields)

        return format_subnet_output(subnets, section_id, limit, truncated, include_usage)

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, f"getting subnets for section {section_id}")

@mcp.tool()
def search_addresses(ip_or_hostname: str, limit: int = 10) -> str:
    """Search for IP addresses or hostnames in phpIPAM.

    CONTEXT OPTIMIZATION: Limited to 10 results by default.

    Args:
        ip_or_hostname: IP address or hostname to search for
        limit: Maximum number of results to return (default: 10, max: 50)
    """
    try:
        result = make_request(f"addresses/search/{ip_or_hostname}/")

        if not result.get('success'):
            return f"API Error: {result.get('message', 'No results found')}"

        addresses = result.get('data', [])
        if not addresses:
            return f"No addresses found matching '{ip_or_hostname}'"

        # Apply limit and field filtering
        addresses, truncated = apply_result_limit(addresses, limit, 50)
        default_fields = ['id', 'subnetId', 'ip', 'hostname', 'description']
        addresses = apply_field_filtering(addresses, "", default_fields)

        return format_address_output(addresses, ip_or_hostname, limit, truncated)

    except Exception as e:  # pylint: disable=broad-exception-caught
        if "404" in str(e):
            return f"No addresses found matching '{ip_or_hostname}'. " + \
                   "Try searching with a complete IP address or exact hostname."
        return _handle_error(e, f"searching for '{ip_or_hostname}'")

@mcp.tool()
def search_hostname(hostname: str, limit: int = 10) -> str:
    """Search for IP addresses by exact or partial hostname in phpIPAM.

    CONTEXT OPTIMIZATION: Limited to 10 results by default.

    Args:
        hostname: Hostname to search for
        limit: Maximum number of results to return (default: 10, max: 50)
    """
    try:
        if '*' in hostname:
            import fnmatch
            result = make_request("addresses/")
            if not result.get('success'):
                return f"API Error: {result.get('message', 'Failed to fetch addresses')}"

            all_addresses = result.get('data', [])
            addresses = [
                addr for addr in all_addresses
                if addr.get('hostname') and fnmatch.fnmatch(addr.get('hostname', '').lower(), hostname.lower())
            ]
        else:
            result = make_request(f"addresses/search_hostname/{hostname}/")
            if not result.get('success'):
                return f"API Error: {result.get('message', 'No results found')}"
            addresses = result.get('data', [])

        if not addresses:
            return f"No addresses found matching hostname '{hostname}'"

        # Apply limit and field filtering
        addresses, truncated = apply_result_limit(addresses, limit, 50)
        default_fields = ['id', 'subnetId', 'ip', 'hostname', 'description']
        addresses = apply_field_filtering(addresses, "", default_fields)

        return format_address_output(addresses, hostname, limit, truncated)

    except Exception as e:  # pylint: disable=broad-exception-caught
        if "404" in str(e):
            return f"No addresses found matching hostname '{hostname}'."
        return _handle_error(e, f"searching for hostname '{hostname}'")

@mcp.tool()
def get_subnet_details(subnet_id: str, include_addresses: bool = False,
                      address_limit: int = 10) -> str:
    """Get detailed information about a specific subnet.

    CONTEXT OPTIMIZATION: Address listing limited to 10 by default.

    Args:
        subnet_id: Subnet ID to get details for
        include_addresses: Include IP addresses in the subnet (default: False)
        address_limit: Max addresses to show if include_addresses=True (default: 10)
    """
    try:
        result = make_request(f"subnets/{subnet_id}/")

        if not result.get('success'):
            return f"API Error: {result.get('message', 'Subnet not found')}"

        subnet = result.get('data', {})
        return format_subnet_details(subnet, subnet_id, include_addresses, address_limit)

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, f"getting details for subnet {subnet_id}")

@mcp.tool()
def list_vlans(domain_id: str = None, limit: int = 20) -> str:
    """List VLANs from phpIPAM.

    CONTEXT OPTIMIZATION: Limited to 20 results by default.

    Args:
        domain_id: Optional domain ID to filter VLANs
        limit: Maximum number of VLANs to return (default: 20, max: 100)
    """
    try:
        endpoint = "vlan/"
        if domain_id:
            endpoint = f"l2domains/{domain_id}/vlans/"

        result = make_request(endpoint)

        if not result.get('success'):
            return f"API Error: {result.get('message', 'Unknown error')}"

        vlans = result.get('data', [])
        if not vlans:
            return "No VLANs found"

        # Apply limit and field filtering
        vlans, truncated = apply_result_limit(vlans, limit, 100)
        default_fields = ['vlanId', 'name', 'number', 'description']
        vlans = apply_field_filtering(vlans, "", default_fields)

        return format_vlan_output(vlans, limit, truncated)

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, "listing VLANs")

@mcp.tool()
def list_vrfs(limit: int = 20) -> str:
    """List VRF instances from phpIPAM.

    CONTEXT OPTIMIZATION: Limited to 20 results by default.

    Args:
        limit: Maximum number of VRFs to return (default: 20, max: 100)
    """
    try:
        result = make_request("vrf/")

        if not result.get('success'):
            return f"API Error: {result.get('message', 'Unknown error')}"

        vrfs = result.get('data', [])
        if not vrfs:
            return "No VRFs found"

        # Apply limit and field filtering
        vrfs, truncated = apply_result_limit(vrfs, limit, 100)
        default_fields = ['vrfId', 'name', 'rd', 'description']
        vrfs = apply_field_filtering(vrfs, "", default_fields)

        # Format as compact output
        output = f"Found {len(vrfs)} VRFs"
        if truncated:
            output += f" (showing first {limit})"
        output += ":\n"

        for vrf in vrfs:
            name = vrf.get('name', 'N/A')
            rd = vrf.get('rd', 'N/A')
            desc = vrf.get('description', 'N/A')
            if desc and len(desc) > 40:
                desc = desc[:40] + "..."
            output += f"ID: {vrf.get('vrfId')}, Name: {name}, RD: {rd}, Desc: {desc}\n"
        return output

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, "listing VRFs")

@mcp.tool()
def list_locations(limit: int = 20) -> str:
    """List physical locations from phpIPAM.

    CONTEXT OPTIMIZATION: Limited to 20 results by default.

    Args:
        limit: Maximum number of locations to return (default: 20, max: 100)
    """
    try:
        result = make_request("tools/locations/")

        if not result.get('success'):
            return f"API Error: {result.get('message', 'Unknown error')}"

        locations = result.get('data', [])
        if not locations:
            return "No locations found"

        # Apply limit and field filtering
        locations, truncated = apply_result_limit(locations, limit, 100)
        default_fields = ['id', 'name', 'address', 'description']
        locations = apply_field_filtering(locations, "", default_fields)

        # Format as compact output
        output = f"Found {len(locations)} locations"
        if truncated:
            output += f" (showing first {limit})"
        output += ":\n"

        for loc in locations:
            name = loc.get('name', 'N/A')
            address = loc.get('address', 'N/A')
            desc = loc.get('description', 'N/A')
            if desc and len(desc) > 30:
                desc = desc[:30] + "..."
            output += f"ID: {loc.get('id')}, Name: {name}, Address: {address}, Desc: {desc}\n"
        return output

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, "listing locations")

@mcp.tool()
def list_nameservers(limit: int = 20) -> str:
    """List DNS nameservers from phpIPAM.

    CONTEXT OPTIMIZATION: Limited to 20 results by default.

    Args:
        limit: Maximum number of nameservers to return (default: 20, max: 100)
    """
    try:
        result = make_request("tools/nameservers/")

        if not result.get('success'):
            return f"API Error: {result.get('message', 'Unknown error')}"

        nameservers = result.get('data', [])
        if not nameservers:
            return "No nameservers found"

        # Apply limit and field filtering
        nameservers, truncated = apply_result_limit(nameservers, limit, 100)
        default_fields = ['id', 'name', 'namesrv1', 'description']
        nameservers = apply_field_filtering(nameservers, "", default_fields)

        # Format as compact output
        output = f"Found {len(nameservers)} nameservers"
        if truncated:
            output += f" (showing first {limit})"
        output += ":\n"

        for ns in nameservers:
            name = ns.get('name', 'N/A')
            server = ns.get('namesrv1', 'N/A')
            desc = ns.get('description', 'N/A')
            if desc and len(desc) > 30:
                desc = desc[:30] + "..."
            output += f"ID: {ns.get('id')}, Name: {name}, Server: {server}, Desc: {desc}\n"
        return output

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, "listing nameservers")

@mcp.tool()
def search_subnets(query: str, limit: int = 10) -> str:
    """Search subnets by CIDR, description, or other criteria.

    CONTEXT OPTIMIZATION: Limited to 10 results by default.

    Args:
        query: Search term (CIDR, description, etc.)
        limit: Maximum number of results to return (default: 10, max: 50)
    """
    try:
        result = make_request(f"subnets/search/{query}/")

        if not result.get('success'):
            return f"No subnets found matching '{query}'"

        subnets = result.get('data', [])
        if not subnets:
            return f"No subnets found matching '{query}'"

        # Apply limit and field filtering
        subnets, truncated = apply_result_limit(subnets, limit, 50)
        default_fields = ['id', 'subnet', 'mask', 'description', 'sectionId', 'usage']
        subnets = apply_field_filtering(subnets, "", default_fields)

        # Format as compact output
        output = f"Found {len(subnets)} subnets matching '{query}'"
        if truncated:
            output += f" (showing first {limit})"
        output += ":\n"

        for subnet in subnets:
            cidr = f"{subnet.get('subnet')}/{subnet.get('mask')}"
            desc = subnet.get('description', 'N/A')
            if desc and len(desc) > 40:
                desc = desc[:40] + "..."
            section_id = subnet.get('sectionId', 'N/A')

            output += f"ID: {subnet.get('id')}, CIDR: {cidr}, Section: {section_id}, Desc: {desc}"

            if subnet.get('usage'):
                usage = subnet['usage']
                used_pct = usage.get('Used_percent', 0)
                output += f", Used: {used_pct:.1f}%"
            output += "\n"
        return output

    except Exception as e:  # pylint: disable=broad-exception-caught
        if "404" in str(e):
            return f"No subnets found matching '{query}'"
        return _handle_error(e, f"searching subnets for '{query}'")

@mcp.tool()
def create_subnet(section_id: str, subnet: str, mask: str, *, description: str = "",
                 vlan_id: str = None) -> str:
    """Create a new subnet in phpIPAM.

    Args:
        section_id: Section ID where subnet will be created
        subnet: Network address (e.g., "192.168.1.0")
        mask: Subnet mask (e.g., "24")
        description: Optional description for the subnet
        vlan_id: Optional VLAN ID
    """
    try:
        data = {
            "subnet": subnet,
            "mask": mask,
            "sectionId": section_id,
            "description": description
        }

        if vlan_id:
            data["vlanId"] = vlan_id

        result = make_request("subnets/", method="POST", data=data)

        if not result.get('success'):
            return f"Failed to create subnet: {result.get('message', 'Unknown error')}"

        subnet_id = result.get('id')
        return f"✅ Subnet created successfully: {subnet}/{mask} (ID: {subnet_id})"

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, f"creating subnet {subnet}/{mask}")

@mcp.tool()
def reserve_ip_address(subnet_id: str, ip: str = None, hostname: str = "",
                      description: str = "", owner: str = "") -> str:
    """Reserve an IP address in a subnet.

    Args:
        subnet_id: Subnet ID where IP will be reserved
        ip: Specific IP address to reserve (optional - will find first available)
        hostname: Hostname for the IP address
        description: Description for the IP address
        owner: Owner of the IP address
    """
    try:
        data = {
            "subnetId": subnet_id,
            "hostname": hostname,
            "description": description,
            "owner": owner
        }

        if ip:
            data["ip"] = ip

        result = make_request("addresses/", method="POST", data=data)

        if not result.get('success'):
            return f"Failed to reserve IP: {result.get('message', 'Unknown error')}"

        address_id = result.get('id')
        assigned_ip = result.get('data', ip or 'auto-assigned')
        return f"✅ IP address reserved: {assigned_ip} (ID: {address_id})"

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, f"reserving IP address {ip or 'auto'}")

@mcp.tool()
def update_ip_address(address_id: str, hostname: str = None, description: str = None,
                     owner: str = None) -> str:
    """Update an existing IP address record.

    Args:
        address_id: ID of the IP address to update
        hostname: New hostname (optional)
        description: New description (optional)
        owner: New owner (optional)
    """
    try:
        data = {}
        if hostname is not None:
            data["hostname"] = hostname
        if description is not None:
            data["description"] = description
        if owner is not None:
            data["owner"] = owner

        if not data:
            return "No fields specified for update"

        result = make_request(f"addresses/{address_id}/", method="PATCH", data=data)

        if not result.get('success'):
            return f"Failed to update IP: {result.get('message', 'Unknown error')}"

        return f"✅ IP address updated successfully (ID: {address_id})"

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, f"updating IP address {address_id}")

@mcp.tool()
def delete_ip_address(address_id: str) -> str:
    """Delete/release an IP address reservation.

    Args:
        address_id: ID of the IP address to delete
    """
    try:
        result = make_request(f"addresses/{address_id}/", method="DELETE")

        if not result.get('success'):
            return f"Failed to delete IP: {result.get('message', 'Unknown error')}"

        return f"✅ IP address deleted successfully (ID: {address_id})"

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, f"deleting IP address {address_id}")

@mcp.tool()
def update_subnet(subnet_id: str, description: str = None, vlan_id: str = None,
                 vrf_id: str = None) -> str:
    """Update an existing subnet.

    Args:
        subnet_id: ID of the subnet to update
        description: New description (optional)
        vlan_id: New VLAN ID (optional)
        vrf_id: New VRF ID (optional)
    """
    try:
        data = {}
        if description is not None:
            data["description"] = description
        if vlan_id is not None:
            data["vlanId"] = vlan_id
        if vrf_id is not None:
            data["vrfId"] = vrf_id

        if not data:
            return "No fields specified for update"

        result = make_request(f"subnets/{subnet_id}/", method="PATCH", data=data)

        if not result.get('success'):
            return f"Failed to update subnet: {result.get('message', 'Unknown error')}"

        return f"✅ Subnet updated successfully (ID: {subnet_id})"

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, f"updating subnet {subnet_id}")

@mcp.tool()
def delete_subnet(subnet_id: str) -> str:
    """Delete a subnet (WARNING: This will delete all IP addresses in the subnet).

    Args:
        subnet_id: ID of the subnet to delete
    """
    try:
        result = make_request(f"subnets/{subnet_id}/", method="DELETE")

        if not result.get('success'):
            return f"Failed to delete subnet: {result.get('message', 'Unknown error')}"

        return f"✅ Subnet deleted successfully (ID: {subnet_id})"

    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_error(e, f"deleting subnet {subnet_id}")


# ---------------------------------------------------------------------------
# Health check (useful for reverse proxies / container orchestration)
# ---------------------------------------------------------------------------
@mcp.custom_route("/health", methods=["GET"])
async def health_check(_request):  # pragma: no cover - trivial
    """Liveness probe; does not touch phpIPAM."""
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Remote-mode middleware: bearer auth + per-client header capture
# ---------------------------------------------------------------------------
class RemoteContextMiddleware:
    """Pure-ASGI middleware (runs in the same task as the endpoint, so the
    contextvar set here is visible to the tool functions).

    Responsibilities:
      * Enforce a static bearer token when MCP_BEARER_TOKEN is set.
      * Capture incoming HTTP headers into a contextvar for per-client creds.
    """

    def __init__(self, app):
        self.app = app
        self.expected_token = os.getenv("MCP_BEARER_TOKEN")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }

        # Allow unauthenticated health checks.
        path = scope.get("path", "")
        if self.expected_token and not path.rstrip("/").endswith("/health"):
            provided = headers.get("authorization", "")
            prefix = "Bearer "
            ok = provided.startswith(prefix) and hmac.compare_digest(
                provided[len(prefix):], self.expected_token
            )
            if not ok:
                from starlette.responses import JSONResponse
                response = JSONResponse(
                    {"error": "unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return

        token = _request_headers.set(headers)
        try:
            await self.app(scope, receive, send)
        finally:
            _request_headers.reset(token)


def build_http_app():
    """Build the Starlette ASGI app for remote (streamable-http) mode."""
    app = mcp.streamable_http_app()
    return RemoteContextMiddleware(app)


def main():
    """Main entry point for the MCP server."""
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport in ("streamable-http", "http", "streamable_http"):
        import uvicorn
        uvicorn.run(
            build_http_app(),
            host=mcp.settings.host,
            port=mcp.settings.port,
            log_level=mcp.settings.log_level.lower(),
        )
    else:
        mcp.run()

if __name__ == "__main__":
    main()
