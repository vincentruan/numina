# syntax=docker/dockerfile:1
FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/vincentruan/numina"

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai
# Install uv with pip cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install uv

WORKDIR /app

# Install dependencies from server/ root (cached layer)
# Note: venv is NOT cache-mounted - must rebuild per platform for correct
# architecture-specific wheels (fixes missing modules when cross-compiling).
# DeerFlow harness will be fetched from GitHub automatically via uv.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra worker

# Copy application code
COPY apps/scheduler_worker/ ./apps/scheduler_worker/
# Phase 2 coupling: packages/domain/notification/ and packages/domain/snapshot/
# lazily import apps.backend.app.services.* at job runtime. The scheduler_worker
# image must therefore include apps/backend/ until Phase 3 fully extracts that
# logic into packages/. See packages/domain/notification/service.py.
COPY apps/backend/ ./apps/backend/
COPY packages/ ./packages/

CMD ["uv", "run", "--no-dev", "uvicorn", "apps.scheduler_worker.main:app", "--host", "0.0.0.0", "--port", "8002"]
