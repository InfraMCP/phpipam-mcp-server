# phpipam-mcp-server

Model Context Protocol server for phpIPAM IP address management and network infrastructure.

## Features

### Phase 1 (v0.1.0) - Basic Functionality
- ✅ Authentication with phpIPAM using app code tokens
- ✅ List IP sections
- ✅ Get subnets within sections with usage statistics
- ✅ Search IP addresses and hostnames
- ✅ Get detailed subnet information
- ✅ List VLANs
- ✅ Field filtering to optimize context window usage

### Planned Features
- **Phase 2 (v0.1.1)**: Advanced discovery tools, VRF management, location tools
- **Phase 3 (v0.2.0)**: Create, update, and delete operations

## Installation

### Prerequisites
- Python 3.8+
- phpIPAM instance with API access
- App configured in phpIPAM with "SSL with App Code token" security

### Environment Variables
```bash
export PHPIPAM_URL="https://ipam.example.com/"
export PHPIPAM_USERNAME="api-user"  # For reference only
export PHPIPAM_PASSWORD="your_app_code_token"  # App code from phpIPAM
export PHPIPAM_APP_ID="your_app_id"
```

### Install from Source
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
      "command": "phpipam-mcp-server"
    }
  }
}
```

### Available Tools

#### `list_sections(include_fields="")`
List all IP sections from phpIPAM.
- `include_fields`: Comma-separated fields or "all" for complete data

#### `get_section_subnets(section_id, include_usage=True, include_fields="")`
Get subnets within a specific section.
- `section_id`: Section ID to query
- `include_usage`: Include usage statistics (default: True)
- `include_fields`: Field filtering options

#### `search_addresses(ip_or_hostname)`
Search for IP addresses or hostnames.
- `ip_or_hostname`: IP address or hostname to search for

#### `get_subnet_details(subnet_id, include_addresses=False)`
Get detailed subnet information.
- `subnet_id`: Subnet ID to query
- `include_addresses`: Include IP addresses in subnet (default: False)

#### `list_vlans(domain_id=None)`
List VLANs from phpIPAM.
- `domain_id`: Optional domain ID filter

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
