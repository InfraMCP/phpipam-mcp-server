# phpIPAM MCP Server - remote (streamable-http) image
FROM python:3.12-slim

# Avoid interactive prompts, write .pyc straight to stdout
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the package + ASGI server. Copy metadata first for better caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . "uvicorn[standard]>=0.30"

# Remote-mode defaults (override at runtime / via compose)
ENV MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    MCP_PATH=/mcp

EXPOSE 8000

# Run as an unprivileged user
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER 10001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)" || exit 1

CMD ["phpipam-mcp-server"]
