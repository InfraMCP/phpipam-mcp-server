# Deploying the phpIPAM MCP Server in remote (HTTP) mode

This guide explains how to move the server from `stdio` mode (a local install on
the user's machine) to a **remote** mode exposed at a URL such as
`https://phpipam.example.com/mcp`, reachable by any streamable-http capable MCP
client.

## What changes

The server supports two transports, selected with the `MCP_TRANSPORT`
environment variable:

| Mode | `MCP_TRANSPORT` | Use case |
|------|-----------------|----------|
| Local (default) | `stdio` | Launched by the MCP client on the same machine |
| Remote | `streamable-http` | HTTP service exposed at `/mcp` behind TLS |

In remote mode:

- the MCP endpoint is served at the path `MCP_PATH` (default `/mcp`);
- a **static bearer token** (`MCP_BEARER_TOKEN`) protects access;
- phpIPAM credentials can be supplied **per client** via `X-phpIPAM-*` HTTP
  headers, falling back to server-wide environment variables;
- an unauthenticated `/health` endpoint is available for liveness probes.

## Provided files

| File | Purpose |
|------|---------|
| `src/phpipam_mcp_server/server.py` | The server implementation |
| `pyproject.toml` | Declares `uvicorn`, requires Python 3.10+ |
| `Dockerfile` | HTTP-mode server image |
| `docker-compose.yml` | Server + Caddy reverse proxy (automatic TLS) |
| `Caddyfile` | Public domain configuration |
| `.env.example` | Environment variable template |

## Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Set to `streamable-http` for remote mode |
| `MCP_HOST` | `0.0.0.0` | Listen address (HTTP) |
| `MCP_PORT` | `8000` | Listen port (HTTP) |
| `MCP_PATH` | `/mcp` | Path for the MCP endpoint |
| `MCP_BEARER_TOKEN` | — | Token required in `Authorization: Bearer <token>` |
| `PHPIPAM_URL` | — | Shared phpIPAM URL (fallback) |
| `PHPIPAM_APP_ID` | — | Shared phpIPAM App ID (fallback) |
| `PHPIPAM_APP_CODE` | — | Shared phpIPAM App Code (fallback) |
| `PHPIPAM_VERIFY_SSL` | `true` | Verify TLS to phpIPAM |

### Per-client headers (per-client credential mode)

Each client can supply its own phpIPAM credentials:

```
Authorization: Bearer <MCP_BEARER_TOKEN>
X-phpIPAM-URL: https://ipam.example.com/
X-phpIPAM-App-Id: your_app_id
X-phpIPAM-App-Code: your_app_code_token
X-phpIPAM-Verify-Ssl: true
```

If an `X-phpIPAM-*` header is absent, the server falls back to the corresponding
environment variable. Leave the `PHPIPAM_*` variables empty to **require**
per-client credentials.

## Deploying with Docker + Caddy (recommended)

1. Keep the provided files at the repository root.
2. Create the `.env` file:

   ```bash
   cp .env.example .env
   # Generate a strong token:
   echo "MCP_BEARER_TOKEN=$(openssl rand -hex 32)" >> .env
   ```

3. Set your real domain in the `Caddyfile` (replace `phpipam.example.com`).
   Ports 80 and 443 must be reachable from the internet so Let's Encrypt can
   issue a certificate.
4. Start the stack:

   ```bash
   docker compose up -d --build
   ```

5. Check health:

   ```bash
   curl https://phpipam.example.com/health
   # -> {"status":"ok"}
   ```

The MCP endpoint is then available at `https://phpipam.example.com/mcp`.

## Alternative: Nginx reverse proxy

If you already run Nginx, expose the container (or the systemd service) on
`127.0.0.1:8000` and use:

```nginx
server {
    listen 443 ssl http2;
    server_name phpipam.example.com;

    ssl_certificate     /etc/letsencrypt/live/phpipam.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/phpipam.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Important for the MCP transport's streaming (SSE) responses
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }
}
```

> The server does not rewrite the `Authorization` / `X-phpIPAM-*` headers, so
> make sure the proxy forwards them (Nginx does by default; do not add
> `proxy_set_header Authorization "";`).

## Alternative: systemd service (without Docker)

```ini
# /etc/systemd/system/phpipam-mcp.service
[Unit]
Description=phpIPAM MCP Server (HTTP)
After=network-online.target

[Service]
User=phpipam-mcp
Environment=MCP_TRANSPORT=streamable-http
Environment=MCP_HOST=127.0.0.1
Environment=MCP_PORT=8000
EnvironmentFile=/etc/phpipam-mcp/env
ExecStart=/opt/phpipam-mcp/venv/bin/phpipam-mcp-server
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
python3 -m venv /opt/phpipam-mcp/venv
/opt/phpipam-mcp/venv/bin/pip install /path/to/the/repo
systemctl enable --now phpipam-mcp
```

## MCP client configuration

For a client that supports remote HTTP MCP servers:

```json
{
  "mcpServers": {
    "phpipam": {
      "type": "http",
      "url": "https://phpipam.example.com/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_BEARER_TOKEN>",
        "X-phpIPAM-URL": "https://ipam.example.com/",
        "X-phpIPAM-App-Id": "your_app_id",
        "X-phpIPAM-App-Code": "your_app_code_token"
      }
    }
  }
}
```

> If you use shared phpIPAM credentials on the server, omit the `X-phpIPAM-*`
> headers and keep only `Authorization`.

## Quick command-line test

```bash
# Should return 401 without a token
curl -i https://phpipam.example.com/mcp

# With a token: initialize an MCP session (JSON-RPC response)
curl -s https://phpipam.example.com/mcp \
  -H "Authorization: Bearer <MCP_BEARER_TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

## Security notes

- The bearer token travels in clear text: only expose it **behind HTTPS** (the
  reverse proxy handles this). Never publish the endpoint over plain HTTP.
- Rotate the `MCP_BEARER_TOKEN` regularly.
- The server exposes phpIPAM write/delete operations (`create_subnet`,
  `delete_subnet`, `delete_ip_address`, ...). Limit the phpIPAM application's
  permissions to the minimum required.
- In stateless mode, `ClosedResourceError` messages may appear in the logs when
  ephemeral sessions are torn down; these are harmless and do not affect
  responses.
