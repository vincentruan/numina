# SQLite version requirement: ≥ 3.8.0 for partial unique indexes
# (e.g. CREATE UNIQUE INDEX ... WHERE is_revoked = FALSE on device_sessions).
# python:3.13-slim ships Debian Trixie's libsqlite3 ≈ 3.46, well above the floor.
# If switching to a different base image, verify `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"`
# returns ≥ 3.8.0, otherwise schema migration will fail. main.py also asserts
# this at lifespan startup when DATABASE_URL is sqlite://.
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai
RUN pip install uv --no-cache-dir

WORKDIR /app

# Install dependencies from server/ root (cached layer)
# DeerFlow harness will be fetched from GitHub automatically via uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra backend

# Copy application code
COPY apps/backend/ ./apps/backend/
COPY packages/ ./packages/

CMD ["uv", "run", "--no-dev", "uvicorn", "apps.backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]