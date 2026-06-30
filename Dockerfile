# syntax=docker/dockerfile:1.7
# Council backend image.
# Layered for fast rebuilds:
#   1. base python + uv (rarely changes)
#   2. project deps        (changes when pyproject/uv.lock change)
#   3. source              (changes often)
# Build with:  DOCKER_BUILDKIT=1 docker build -t council-backend .
# Skip playwright (saves ~400 MB and ~3 minutes) with:
#   docker build --build-arg INSTALL_PLAYWRIGHT=0 .

ARG PYTHON_VERSION=3.12
ARG INSTALL_PLAYWRIGHT=1

FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin

WORKDIR /app

# System deps. libpq-dev is required by asyncpg (no wheel on all platforms).
# We split apt installs from the rest so the heavy `uv sync` layer caches.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        libpq5 \
        tini \
        passwd \
    && rm -rf /var/lib/apt/lists/*

# Install uv. Multi-stage: only the `uv` binary is copied from the official image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# === deps layer ============================================================
COPY pyproject.toml uv.lock README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# === source layer ==========================================================
COPY src/ ./src/

# Re-sync project metadata only (cheap) and run inline runtime prep.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev \
    && mkdir -p /app/data

# === optional playwright / crawl4ai ========================================
# These deps are NOT in pyproject (intentional — they're only used by the
# optional crawl4ai collector). Installing them post-`uv sync` is OK because
# they live outside the resolved dep graph and don't conflict.
RUN if [ "${INSTALL_PLAYWRIGHT}" = "1" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends \
            fonts-liberation \
            libgdk-pixbuf-2.0-0 \
            libglib2.0-0 \
            libnss3 \
            libnspr4 \
            libxcomposite1 \
            libxdamage1 \
            libxfixes3 \
            libxkbcommon0 \
            libxrandr2 \
        && rm -rf /var/lib/apt/lists/* \
        && uv pip install --no-deps crawl4ai playwright \
        && uv run playwright install chromium; \
    fi

# === security: drop root ===================================================
RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid appuser --shell /bin/bash --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser
WORKDIR /app

ENV PYTHONPATH=/app/src \
    ENVIRONMENT=production

EXPOSE 8000

# tini reaps zombies and forwards signals correctly.
ENTRYPOINT ["tini", "--"]

# 1 worker keeps model memory predictable; --proxy-headers so trust chains work behind a reverse proxy.
CMD ["uvicorn", "council.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--log-level", "info"]
