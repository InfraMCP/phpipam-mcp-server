# phpIPAM API Overview

## General Information

phpIPAM provides a REST API for managing IP address allocations, subnets, VLANs, and network infrastructure.

**Current Version**: 1.7.3

## HTTP Request Methods

| Method | Description |
|--------|-------------|
| OPTIONS | Returns all supported controllers and methods |
| GET | Reads object(s) details and returns in requested format |
| POST | Creates new object |
| PUT | Changes object values |
| PATCH | Alias to PUT method |
| DELETE | Deletes an object |

## Request Structure

```
/api/{app_id}/{controller}/{id}/ HTTP/1.1
```

Example:
```
GET /api/myAPP/sections/ HTTP/1.1
Content-Type: application/json
token: UJMcRNGjxH5UvHGeRy!vzgtL
Host: api.phpipam.net
```

## Authentication

### Dynamic Authentication
1. Authenticate with username/password via "authorization" HTTP header
2. Receive API token for subsequent requests
3. Include token in "phpipam-token" or "token" header for all requests
4. Token expires after 6 hours (configurable)
5. Each successful request resets expiration time

### Static Authentication
Alternative authentication method using pre-configured tokens.

## Response Format

### Success Response
```json
{
    "code": 200,
    "success": true,
    "data": {
        "id": "92",
        "name": "api_post_create"
    }
}
```

### Error Response
```json
{
    "code": 400,
    "success": false,
    "message": "invalid controller"
}
```

### Created Response
```json
{
    "code": 201,
    "success": true,
    "id": 92,
    "data": "Section created successfully"
}
```

## Output Formats

- **JSON** (default)
- **XML** (set Content-Type: application/xml)

## Global Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| links | boolean | Show links inside results (default: true) |
| filter_by | varchar | Filter results by field |
| filter_value | varchar | Value to filter by |
| filter_type | varchar | full, partial, regex |

## Environment Variables

- `PHPIPAM_URL` - Base URL for phpIPAM instance (e.g., https://ipam.example.com/)
- `PHPIPAM_USERNAME` - Username for authentication (e.g., api-user)
- `PHPIPAM_PASSWORD` - Password for authentication or app code token
- `PHPIPAM_APP_ID` - Application ID for API access (e.g., myapp)
