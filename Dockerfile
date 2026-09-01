# phpIPAM MCP Server - remote (streamable-http) image
# Base image pinned by digest for supply-chain integrity (python:3.12-slim,
# Debian 13 "trixie"). Refresh the digest when rebuilding to pick up OS security
# updates: docker pull python:3.12-slim && docker inspect --format \
#   '{{index .RepoDigests 0}}' python:3.12-slim
FROM python:3.12-slim@sha256:09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217

# Avoid interactive prompts, write .pyc straight to stdout
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Apply outstanding OS security updates (e.g. openssl) on top of the pinned
# base layer, then remove apt lists to keep the image small.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the package + ASGI server. Copy metadata first for better caching.
# Upgrade pip/setuptools first to pull in security fixes for the build tooling.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade "pip==26.2.1" "setuptools==84.0.0" \
    && pip install --no-cache-dir . "uvicorn[standard]>=0.34"

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
