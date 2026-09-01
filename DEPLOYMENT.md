# Déploiement du serveur MCP phpIPAM en mode distant (HTTP)

Ce guide explique comment passer le serveur du mode `stdio` (installation locale
sur le poste utilisateur) à un mode **distant** exposé sur une URL du type
`https://phpipam.domaine.com/mcp`, accessible par n'importe quel client MCP
compatible HTTP streamable.

## Ce qui change

Le serveur supporte désormais deux transports, choisis par la variable
`MCP_TRANSPORT` :

| Mode | `MCP_TRANSPORT` | Usage |
|------|-----------------|-------|
| Local (historique) | `stdio` (défaut) | Lancé par le client MCP sur la machine |
| Distant | `streamable-http` | Service HTTP exposé sur `/mcp` derrière TLS |

En mode distant :

- l'endpoint MCP est servi sur le chemin `MCP_PATH` (défaut `/mcp`) ;
- un **bearer token statique** (`MCP_BEARER_TOKEN`) protège l'accès ;
- les identifiants phpIPAM sont fournis **par client** via des en-têtes HTTP
  (`X-phpIPAM-*`), avec repli possible sur des variables d'environnement
  partagées côté serveur ;
- un endpoint `/health` non authentifié est disponible pour les sondes.

## Fichiers fournis

| Fichier | Rôle |
|---------|------|
| `src/phpipam_mcp_server/server.py` | Serveur adapté (remplace l'existant) |
| `pyproject.toml` | Ajoute `uvicorn`, passe à Python 3.10+, v0.3.0 |
| `Dockerfile` | Image du serveur en mode HTTP |
| `docker-compose.yml` | Serveur + reverse proxy Caddy (TLS auto) |
| `Caddyfile` | Configuration du domaine public |
| `.env.example` | Modèle de variables d'environnement |

## Configuration (variables d'environnement)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `MCP_TRANSPORT` | `stdio` | Mettre `streamable-http` pour le mode distant |
| `MCP_HOST` | `0.0.0.0` | Adresse d'écoute (HTTP) |
| `MCP_PORT` | `8000` | Port d'écoute (HTTP) |
| `MCP_PATH` | `/mcp` | Chemin de l'endpoint MCP |
| `MCP_BEARER_TOKEN` | — | Token requis dans `Authorization: Bearer <token>` |
| `PHPIPAM_URL` | — | URL phpIPAM partagée (repli) |
| `PHPIPAM_APP_ID` | — | App ID phpIPAM partagé (repli) |
| `PHPIPAM_APP_CODE` | — | App Code phpIPAM partagé (repli) |
| `PHPIPAM_VERIFY_SSL` | `true` | Vérification TLS vers phpIPAM |

### En-têtes par client (mode « par client »)

Chaque client peut fournir ses propres identifiants phpIPAM :

```
Authorization: Bearer <MCP_BEARER_TOKEN>
X-phpIPAM-URL: https://ipam.example.com/
X-phpIPAM-App-Id: mon_app_id
X-phpIPAM-App-Code: mon_app_code_token
X-phpIPAM-Verify-Ssl: true
```

Si un en-tête `X-phpIPAM-*` est absent, le serveur utilise la variable
d'environnement correspondante. Vous pouvez donc laisser les variables
`PHPIPAM_*` vides pour **imposer** des identifiants par client.

## Déploiement avec Docker + Caddy (recommandé)

1. Placez les fichiers fournis à la racine du dépôt (en remplaçant
   `src/phpipam_mcp_server/server.py` et `pyproject.toml`).
2. Créez le fichier `.env` :

   ```bash
   cp .env.example .env
   # Générez un token solide :
   echo "MCP_BEARER_TOKEN=$(openssl rand -hex 32)" >> .env
   ```

3. Renseignez votre domaine réel dans `Caddyfile` (remplacez
   `phpipam.domaine.com`). Les ports 80 et 443 doivent être accessibles depuis
   Internet pour l'émission du certificat Let's Encrypt.
4. Démarrez :

   ```bash
   docker compose up -d --build
   ```

5. Vérifiez la santé :

   ```bash
   curl https://phpipam.domaine.com/health
   # -> {"status":"ok"}
   ```

L'endpoint MCP est alors disponible sur `https://phpipam.domaine.com/mcp`.

## Alternative : reverse proxy Nginx

Si vous gérez déjà Nginx, exposez le conteneur (ou le service systemd) sur
`127.0.0.1:8000` et utilisez :

```nginx
server {
    listen 443 ssl http2;
    server_name phpipam.domaine.com;

    ssl_certificate     /etc/letsencrypt/live/phpipam.domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/phpipam.domaine.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Important pour le streaming (SSE) du transport MCP
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }
}
```

> Le serveur ne réécrit pas les en-têtes `Authorization` / `X-phpIPAM-*` :
> assurez-vous que le proxy les transmet bien (Nginx le fait par défaut ; ne pas
> ajouter de `proxy_set_header Authorization "";`).

## Alternative : service systemd (sans Docker)

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
/opt/phpipam-mcp/venv/bin/pip install /chemin/vers/le/depot
systemctl enable --now phpipam-mcp
```

## Configuration côté client MCP

Pour un client supportant les serveurs MCP HTTP distants :

```json
{
  "mcpServers": {
    "phpipam": {
      "type": "http",
      "url": "https://phpipam.domaine.com/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_BEARER_TOKEN>",
        "X-phpIPAM-URL": "https://ipam.example.com/",
        "X-phpIPAM-App-Id": "mon_app_id",
        "X-phpIPAM-App-Code": "mon_app_code_token"
      }
    }
  }
}
```

> Si vous utilisez des identifiants phpIPAM partagés côté serveur, omettez les
> en-têtes `X-phpIPAM-*` et ne gardez que `Authorization`.

## Test rapide en ligne de commande

```bash
# Doit renvoyer 401 sans token
curl -i https://phpipam.domaine.com/mcp

# Avec token : initialise une session MCP (réponse JSON-RPC)
curl -s https://phpipam.domaine.com/mcp \
  -H "Authorization: Bearer <MCP_BEARER_TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

## Notes de sécurité

- Le bearer token transite en clair : ne l'exposez **que** derrière HTTPS (le
  reverse proxy s'en charge). Ne publiez jamais l'endpoint en HTTP nu.
- Faites tourner (rotation) le `MCP_BEARER_TOKEN` régulièrement.
- Le serveur expose des opérations d'écriture/suppression phpIPAM
  (`create_subnet`, `delete_subnet`, `delete_ip_address`, …). Limitez les
  permissions de l'application phpIPAM au strict nécessaire.
- En mode stateless, des messages `ClosedResourceError` peuvent apparaître dans
  les logs lors du teardown des sessions éphémères : c'est sans conséquence sur
  les réponses.
