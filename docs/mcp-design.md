# phpIPAM MCP Server Design

## Overview

The phpIPAM MCP server provides AI agents with tools to interact with phpIPAM REST API for IP address management, subnet allocation, and network infrastructure management.

## Design Principles

Following the established InfraMCP server patterns:

1. **FastMCP Framework**: Use `mcp.server.fastmcp.FastMCP`
2. **Environment Configuration**: Load credentials from environment variables
3. **Error Handling**: Consistent error handling with `_handle_error()` function
4. **Field Filtering**: Reduce context window usage with `filter_fields()` function
5. **Static Authentication**: Use app code token for simplicity
6. **Read-Only by Default**: Separate tools for read vs write operations

## Authentication

**Method**: SSL with App Code token
- Environment variable: `PHPIPAM_PASSWORD` (contains app code)
- Header: `token: {app_code}`
- No token expiration (static authentication)

## Environment Variables

```bash
PHPIPAM_URL=https://ipam.example.com/
PHPIPAM_USERNAME=api-user  # For reference only
PHPIPAM_PASSWORD=<app_code>  # Used as static token
PHPIPAM_APP_ID=myapp
```

## Proposed MCP Tools

### Core IP Management

#### `list_sections()`
- **Purpose**: List all available sections
- **Returns**: Section hierarchy with names, descriptions, permissions
- **Use Case**: Discover IP space organization

#### `get_section_subnets(section_id, include_usage=True)`
- **Purpose**: Get subnets within a section
- **Parameters**: 
  - `section_id`: Section identifier
  - `include_usage`: Include usage statistics (default: True)
- **Returns**: Subnets with usage data
- **Use Case**: Explore IP allocations within sections

#### `search_subnets(query, section_id=None)`
- **Purpose**: Search subnets by CIDR, description, or other criteria
- **Parameters**:
  - `query`: Search term (IP, CIDR, description)
  - `section_id`: Optional section filter
- **Returns**: Matching subnets
- **Use Case**: Find specific subnets

#### `get_subnet_details(subnet_id, include_addresses=False)`
- **Purpose**: Get detailed subnet information
- **Parameters**:
  - `subnet_id`: Subnet identifier
  - `include_addresses`: Include IP addresses (default: False)
- **Returns**: Subnet details with optional address list
- **Use Case**: Detailed subnet analysis

#### `search_addresses(ip_or_hostname)`
- **Purpose**: Search for specific IP addresses or hostnames
- **Parameters**: `ip_or_hostname`: IP address or hostname to search
- **Returns**: Matching address records
- **Use Case**: Find specific IP allocations

#### `get_subnet_usage(subnet_id)`
- **Purpose**: Get subnet utilization statistics
- **Parameters**: `subnet_id`: Subnet identifier
- **Returns**: Usage statistics (used, free, percentages)
- **Use Case**: Capacity planning

### Network Infrastructure

#### `list_vlans(domain_id=None)`
- **Purpose**: List VLANs
- **Parameters**: `domain_id`: Optional domain filter
- **Returns**: VLAN information
- **Use Case**: VLAN management

#### `list_vrfs()`
- **Purpose**: List VRF instances
- **Returns**: VRF configurations
- **Use Case**: VRF management

### Administrative Tools

#### `get_locations()`
- **Purpose**: List physical locations
- **Returns**: Location inventory
- **Use Case**: Location-based IP management

#### `get_nameservers()`
- **Purpose**: List DNS servers
- **Returns**: Nameserver configurations
- **Use Case**: DNS management

### Write Operations (Separate Tools)

#### `create_subnet(section_id, subnet, mask, description=None, vlan_id=None)`
- **Purpose**: Create new subnet
- **Parameters**: Section, CIDR, description, VLAN
- **Returns**: Created subnet details
- **Use Case**: Subnet provisioning

#### `reserve_ip_address(subnet_id, ip=None, hostname=None, description=None)`
- **Purpose**: Reserve IP address in subnet
- **Parameters**: Subnet, optional specific IP, hostname, description
- **Returns**: Reserved address details
- **Use Case**: IP allocation

#### `update_address(address_id, hostname=None, description=None, owner=None)`
- **Purpose**: Update IP address record
- **Parameters**: Address ID and fields to update
- **Returns**: Updated address details
- **Use Case**: IP record maintenance

#### `release_ip_address(address_id)`
- **Purpose**: Release/delete IP address reservation
- **Parameters**: Address ID
- **Returns**: Success confirmation
- **Use Case**: IP deallocation

## Implementation Structure

```
src/phpipam_mcp_server/
├── __init__.py
├── server.py          # Main MCP server with tools
├── client.py          # phpIPAM API client
└── utils.py           # Helper functions
```

### Key Functions

#### `get_phpipam_config()`
```python
def get_phpipam_config():
    """Get phpIPAM configuration from environment variables"""
    return {
        'base_url': os.getenv('PHPIPAM_URL').rstrip('/'),
        'app_id': os.getenv('PHPIPAM_APP_ID'),
        'token': os.getenv('PHPIPAM_PASSWORD'),
        'verify_ssl': True
    }
```

#### `filter_fields(data, include_fields=None, exclude_fields=None)`
```python
def filter_fields(data, include_fields=None, exclude_fields=None):
    """Filter fields to reduce context window usage"""
    # Implementation similar to foreman-mcp-server
```

#### `_handle_error(e: Exception, operation: str) -> str`
```python
def _handle_error(e: Exception, operation: str) -> str:
    """Handle errors consistently across all tools"""
    # Implementation similar to other MCP servers
```

## Error Handling

- **Authentication Errors**: Clear message about token configuration
- **Network Errors**: Connection and timeout handling
- **API Errors**: Parse phpIPAM error responses
- **Validation Errors**: Parameter validation before API calls

## Context Window Optimization

- **Field Filtering**: Remove verbose fields like permissions JSON
- **Pagination**: Support for large result sets
- **Usage Flags**: Optional inclusion of detailed data
- **Summary Views**: Condensed information for exploration

## Security Considerations

- **Read-Only Default**: Separate tools for write operations
- **Input Validation**: Validate IP addresses, CIDRs, IDs
- **Error Sanitization**: Don't expose sensitive information
- **Permission Checking**: Respect phpIPAM permissions

## Testing Strategy

1. **API Connectivity**: Test authentication and basic endpoints
2. **Read Operations**: Test all read-only tools
3. **Write Operations**: Test in development environment only
4. **Error Handling**: Test various error conditions
5. **Field Filtering**: Verify context window optimization
