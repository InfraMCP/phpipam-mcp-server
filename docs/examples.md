# phpIPAM API Examples

## Authentication Test

```bash
curl -k -s -X GET \
  -H "Content-Type: application/json" \
  -H "token: your_app_code_here" \
  "https://ipam.example.com/api/myapp/sections/" | jq .
```

## List Sections

**Request:**
```bash
GET /api/myapp/sections/ HTTP/1.1
Content-Type: application/json
token: your_app_code_here
```

**Response:**
```json
{
  "code": 200,
  "success": true,
  "data": [
    {
      "id": "1",
      "name": "Production",
      "description": "Production IP Space",
      "masterSection": "0",
      "permissions": "{\"4\":\"1\",\"12\":\"3\",\"13\":\"1\"}",
      "strictMode": "1",
      "subnetOrdering": "subnet,asc",
      "showVLAN": "1",
      "showVRF": "1"
    },
    {
      "id": "2",
      "name": "Development",
      "description": "Development Environment",
      "masterSection": "0",
      "permissions": "{\"4\":\"3\",\"5\":\"3\"}",
      "strictMode": "1"
    }
  ]
}
```

## Get Section Subnets

**Request:**
```bash
GET /api/myapp/sections/1/subnets/ HTTP/1.1
Content-Type: application/json
token: your_app_code_here
```

**Response:**
```json
{
  "code": 200,
  "success": true,
  "data": [
    {
      "id": "100",
      "subnet": "192.168.1.0",
      "mask": "24",
      "sectionId": "1",
      "description": "Web Servers",
      "vrfId": "0",
      "vlanId": "10",
      "usage": {
        "Used": "50",
        "Reserved": "5",
        "Used_percent": 19.69,
        "Reserved_percent": 1.97,
        "freehosts": "199",
        "freehosts_percent": 78.35,
        "maxhosts": "254"
      }
    }
  ]
}
```

## Get Subnet Addresses

**Request:**
```bash
GET /api/myapp/subnets/100/addresses/ HTTP/1.1
Content-Type: application/json
token: your_app_code_here
```

**Response:**
```json
{
  "code": 200,
  "success": true,
  "data": [
    {
      "id": "1001",
      "subnetId": "100",
      "ip": "192.168.1.10",
      "hostname": "web-server-01",
      "description": "Primary web server",
      "mac": "00:50:56:12:34:56",
      "owner": "IT Team",
      "tag": "2"
    },
    {
      "id": "1002",
      "subnetId": "100",
      "ip": "192.168.1.11",
      "hostname": "web-server-02",
      "description": "Secondary web server",
      "tag": "2"
    }
  ]
}
```

## Search IP Address

**Request:**
```bash
GET /api/myapp/addresses/search/192.168.1.10/ HTTP/1.1
Content-Type: application/json
token: your_app_code_here
```

**Response:**
```json
{
  "code": 200,
  "success": true,
  "data": [
    {
      "id": "1001",
      "subnetId": "100",
      "ip": "192.168.1.10",
      "hostname": "web-server-01",
      "description": "Primary web server",
      "mac": "00:50:56:12:34:56",
      "owner": "IT Team",
      "tag": "2"
    }
  ]
}
```

## List VLANs

**Request:**
```bash
GET /api/myapp/vlan/ HTTP/1.1
Content-Type: application/json
token: your_app_code_here
```

**Response:**
```json
{
  "code": 200,
  "success": true,
  "data": [
    {
      "vlanId": "10",
      "domainId": "1",
      "name": "Web Servers",
      "number": "100",
      "description": "Web server VLAN"
    },
    {
      "vlanId": "11",
      "domainId": "1",
      "name": "Database Servers",
      "number": "200",
      "description": "Database server VLAN"
    }
  ]
}
```

## Create Subnet (Write Operation)

**Request:**
```bash
POST /api/myapp/subnets/ HTTP/1.1
Content-Type: application/json
token: your_app_code_here

{
  "subnet": "192.168.2.0",
  "mask": "24",
  "sectionId": "1",
  "description": "New subnet for testing",
  "vlanId": "10"
}
```

**Response:**
```json
{
  "code": 201,
  "success": true,
  "id": 101,
  "data": "Subnet created successfully"
}
```

## Reserve IP Address (Write Operation)

**Request:**
```bash
POST /api/myapp/addresses/ HTTP/1.1
Content-Type: application/json
token: your_app_code_here

{
  "subnetId": "100",
  "ip": "192.168.1.50",
  "hostname": "new-server",
  "description": "Newly allocated server"
}
```

**Response:**
```json
{
  "code": 201,
  "success": true,
  "id": 1050,
  "data": "Address created successfully"
}
```

## Error Response Example

**Request:**
```bash
GET /api/myapp/subnets/99999/ HTTP/1.1
Content-Type: application/json
token: your_app_code_here
```

**Response:**
```json
{
  "code": 404,
  "success": false,
  "message": "Subnet not found"
}
```

## Available Controllers

**Request:**
```bash
OPTIONS /api/myapp/ HTTP/1.1
Content-Type: application/json
token: your_app_code_here
```

**Response:**
```json
{
  "code": 200,
  "success": true,
  "data": {
    "permissions": "Write",
    "controllers": [
      {"rel": "sections", "href": "/api/myapp/sections/"},
      {"rel": "subnets", "href": "/api/myapp/subnets/"},
      {"rel": "addresses", "href": "/api/myapp/addresses/"},
      {"rel": "vlans", "href": "/api/myapp/vlan/"},
      {"rel": "vrfs", "href": "/api/myapp/vrf/"},
      {"rel": "tools", "href": "/api/myapp/tools/"}
    ]
  }
}
```
