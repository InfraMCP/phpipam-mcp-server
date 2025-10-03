#!/usr/bin/env python3
"""phpIPAM MCP Server - Provides phpIPAM API access through MCP protocol."""

import os
import requests
from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("phpIPAM Server")

def get_phpipam_config():
    """Get phpIPAM configuration from environment variables"""
    base_url = os.getenv('PHPIPAM_URL')
    app_id = os.getenv('PHPIPAM_APP_ID')
    token = os.getenv('PHPIPAM_PASSWORD')

    if not base_url:
        raise ValueError("PHPIPAM_URL environment variable is required")
    if not app_id:
        raise ValueError("PHPIPAM_APP_ID environment variable is required")
    if not token:
        raise ValueError("PHPIPAM_PASSWORD environment variable is required")

    return {
        'base_url': base_url.rstrip('/'),
        'app_id': app_id,
        'token': token,
        'verify_ssl': True
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
        output += f"IP: {addr.get('ip')}, Host: {hostname}, Desc: {desc}\n"
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
            "Check PHPIPAM_PASSWORD (app code token) environment variable."
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

def main():
    """Main entry point for the MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()
