# phpIPAM API Controllers

Based on API exploration, the following controllers are available:

## Core Controllers

### Sections
- **Endpoint**: `/api/{app_id}/sections/`
- **Description**: Top-level organizational units for IP space
- **Methods**: GET, POST, PUT, PATCH, DELETE
- **Key Fields**: id, name, description, masterSection, permissions, strictMode

### Subnets  
- **Endpoint**: `/api/{app_id}/sections/{section_id}/subnets/`
- **Description**: IP subnets within sections
- **Methods**: GET, POST, PUT, PATCH, DELETE
- **Key Fields**: id, subnet, mask, sectionId, description, vrfId, vlanId, usage
- **Usage Data**: Used, Reserved, freehosts, maxhosts (with percentages)

### Addresses
- **Endpoint**: `/api/{app_id}/subnets/{subnet_id}/addresses/`
- **Description**: Individual IP addresses within subnets
- **Methods**: GET, POST, PUT, PATCH, DELETE
- **Key Fields**: id, subnetId, ip, hostname, description, mac, owner, tag
- **Search**: `/api/{app_id}/addresses/search/{ip}/`

### Folders
- **Endpoint**: `/api/{app_id}/folders/`
- **Description**: Organizational folders for subnets
- **Methods**: GET, POST, PUT, PATCH, DELETE

## Network Infrastructure

### VLANs
- **Endpoint**: `/api/{app_id}/vlan/`
- **Description**: VLAN management
- **Methods**: GET, POST, PUT, PATCH, DELETE
- **Key Fields**: vlanId, domainId, name, number, description

### VRFs
- **Endpoint**: `/api/{app_id}/vrf/`
- **Description**: Virtual Routing and Forwarding instances
- **Methods**: GET, POST, PUT, PATCH, DELETE

## Tools and Utilities

### Tools
- **Endpoint**: `/api/{app_id}/tools/`
- **Description**: Various administrative tools

### Nameservers
- **Endpoint**: `/api/{app_id}/tools/nameservers/`
- **Description**: DNS server management

### Locations
- **Endpoint**: `/api/{app_id}/tools/locations/`
- **Description**: Physical location management

### Racks
- **Endpoint**: `/api/{app_id}/tools/racks/`
- **Description**: Equipment rack management

### Scan Agents
- **Endpoint**: `/api/{app_id}/tools/scanagents/`
- **Description**: Network scanning agents

### NAT
- **Endpoint**: `/api/{app_id}/tools/nat/`
- **Description**: Network Address Translation rules

## Authentication

**Method**: SSL with App Code token
- Header: `token: {app_code}`
- Permissions: Write access confirmed
- Token does not expire (static)

## Data Structures

### Section Example
```json
{
  "id": "1",
  "name": "Production",
  "description": "Production IP Space",
  "masterSection": "0",
  "permissions": "{\"4\":\"1\",\"12\":\"3\",\"13\":\"1\"}",
  "strictMode": "1"
}
```

### Subnet Example
```json
{
  "id": "100",
  "subnet": "192.168.1.0",
  "mask": "24",
  "sectionId": "1",
  "description": "Web Servers",
  "usage": {
    "Used": "50",
    "Used_percent": 19.69,
    "freehosts": "204",
    "freehosts_percent": 80.31,
    "maxhosts": "254"
  }
}
```

### Address Example
```json
{
  "id": "1001",
  "subnetId": "100",
  "ip": "192.168.1.10",
  "hostname": "web-server-01",
  "description": "Primary web server",
  "tag": "2"
}
```
