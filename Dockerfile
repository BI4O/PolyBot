FROM debian:bookworm-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# uv sync auto-downloads Python 3.13
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY src/ src/
COPY tests/ tests/
COPY langgraph.json ./
CMD ["uv", "run", "langgraph", "dev", "--host", "0.0.0.0", "--port", "8123"]
