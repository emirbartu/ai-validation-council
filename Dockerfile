FROM python:3.12-slim

WORKDIR /app

# Install system deps for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install project
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY .env.example ./

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Install crawl4ai and playwright (optional web scraping)
RUN uv pip install crawl4ai playwright

# Install playwright browsers
RUN uv run playwright install chromium --with-deps

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "council.main:app", "--host", "0.0.0.0", "--port", "8000"]
