# phpIPAM MCP Server

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Pylint](https://github.com/InfraMCP/phpipam-mcp-server/actions/workflows/pylint.yml/badge.svg)](https://github.com/InfraMCP/phpipam-mcp-server/actions/workflows/pylint.yml)
[![Safety Security Scan](https://github.com/InfraMCP/phpipam-mcp-server/actions/workflows/safety-scan.yml/badge.svg)](https://github.com/InfraMCP/phpipam-mcp-server/actions/workflows/safety-scan.yml)
[![Dependency Security Check](https://github.com/InfraMCP/phpipam-mcp-server/actions/workflows/dependency-security.yml/badge.svg)](https://github.com/InfraMCP/phpipam-mcp-server/actions/workflows/dependency-security.yml)

Model Context Protocol server for phpIPAM IP address management and network infrastructure.

## Installation

### Prerequisites
- Python 3.10+
- phpIPAM instance with API access
- App configured in phpIPAM with "SSL with App Code token" security

### From PyPI (when published)
```bash
pip install phpipam-mcp-server
```

### From Source
```bash
git clone https://github.com/InfraMCP/phpipam-mcp-server.git
cd phpipam-mcp-server
pip install -e .
```

### Development Installation
```bash
pip install -e ".[dev]"
```

## Usage

### As MCP Server
Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "phpipam": {
      "command": "phpipam-mcp-server",
      "env": {
        "PHPIPAM_URL": "https://ipam.example.com/",
        "PHPIPAM_APP_ID": "your_app_id",
        "PHPIPAM_APP_CODE": "your_app_code_token"
      }
    }
  }
}
```

### Available Tools

#### `list_sections(include_fields="")`
List all IP sections from phpIPAM.
- `include_fields`: Comma-separated fields or "all" for complete data

#### `get_section_subnets(section_id, include_usage=True, include_fields="", limit=20)`
Get subnets within a specific section.
- `section_id`: Section ID to query
- `include_usage`: Include usage statistics (default: True)
- `include_fields`: Field filtering options
- `limit`: Maximum results to return (default: 20, max: 100)

#### `search_addresses(ip_or_hostname, limit=10)`
Search for IP addresses or hostnames.
- `ip_or_hostname`: IP address or hostname to search for
- `limit`: Maximum results to return (default: 10, max: 50)

#### `get_subnet_details(subnet_id, include_addresses=False, address_limit=10)`
Get detailed subnet information.
- `subnet_id`: Subnet ID to query
- `include_addresses`: Include IP addresses in subnet (default: False)
- `address_limit`: Maximum addresses to show (default: 10, max: 50)

#### `list_vlans(domain_id=None, limit=20)`
List VLANs from phpIPAM.
- `domain_id`: Optional domain ID filter
- `limit`: Maximum results to return (default: 20, max: 100)

#### `list_vrfs(limit=20)`
List VRF instances from phpIPAM.
- `limit`: Maximum results to return (default: 20, max: 100)

#### `list_locations(limit=20)`
List physical locations for network infrastructure.
- `limit`: Maximum results to return (default: 20, max: 100)

#### `list_nameservers(limit=20)`
List DNS nameservers with configuration details.
- `limit`: Maximum results to return (default: 20, max: 100)

#### `search_subnets(query, limit=10)`
Search subnets by CIDR, description, or other criteria.
- `query`: Search term (CIDR, description, etc.)
- `limit`: Maximum results to return (default: 10, max: 50)

### Write Operations

#### `create_subnet(section_id, subnet, mask, *, description="", vlan_id=None)`
Create a new subnet in phpIPAM.
- `section_id`: Section ID where subnet will be created
- `subnet`: Network address (e.g., "192.168.1.0")
- `mask`: Subnet mask (e.g., "24")
- `description`: Optional description for the subnet
- `vlan_id`: Optional VLAN ID

#### `reserve_ip_address(subnet_id, ip=None, hostname="", description="", owner="")`
Reserve an IP address in a subnet.
- `subnet_id`: Subnet ID where IP will be reserved
- `ip`: Specific IP address to reserve (optional - will find first available)
- `hostname`: Hostname for the IP address
- `description`: Description for the IP address
- `owner`: Owner of the IP address

#### `update_ip_address(address_id, hostname=None, description=None, owner=None)`
Update an existing IP address record.
- `address_id`: ID of the IP address to update
- `hostname`: New hostname (optional)
- `description`: New description (optional)
- `owner`: New owner (optional)

#### `delete_ip_address(address_id)`
Delete/release an IP address reservation.
- `address_id`: ID of the IP address to delete

#### `update_subnet(subnet_id, description=None, vlan_id=None, vrf_id=None)`
Update an existing subnet.
- `subnet_id`: ID of the subnet to update
- `description`: New description (optional)
- `vlan_id`: New VLAN ID (optional)
- `vrf_id`: New VRF ID (optional)

#### `delete_subnet(subnet_id)`
Delete a subnet (WARNING: This will delete all IP addresses in the subnet).
- `subnet_id`: ID of the subnet to delete

## Configuration

### phpIPAM Setup
1. Create an API application in phpIPAM admin interface
2. Set security to "SSL with App Code token"
3. Note the App ID and App Code
4. Set appropriate permissions for the application

### Authentication
This server uses static app code token authentication:
- No token expiration
- Simple configuration
- Secure over HTTPS

## Development

### Code Quality
```bash
# Run pylint
python -m pylint src/phpipam_mcp_server/

# Run tests (when available)
python -m pytest

# Format code
python -m black src/
python -m isort src/
```

### Project Structure
```
src/phpipam_mcp_server/
├── __init__.py          # Package initialization
└── server.py            # Main MCP server implementation
```

## API Documentation

See the `docs/` directory for detailed API documentation:
- `api-overview.md` - General API information
- `controllers.md` - Available endpoints and data structures
- `examples.md` - Request/response examples
- `mcp-design.md` - MCP server design and architecture

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run code quality checks
5. Submit a pull request

## Support

- GitHub Issues: https://github.com/InfraMCP/phpipam-mcp-server/issues
- Documentation: https://github.com/InfraMCP/phpipam-mcp-server#readme
