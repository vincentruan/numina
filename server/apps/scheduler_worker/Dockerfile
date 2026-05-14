FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai
RUN pip install uv --no-cache-dir

RUN useradd -r -u 1001 -s /sbin/nologin appuser

WORKDIR /app

# DeerFlow harness must be present before uv sync (workspace member)
COPY apps/agent/vendor/deerflow-harness ./apps/agent/vendor/deerflow-harness

# Install dependencies from server/ root (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra worker

# Copy application code
COPY apps/scheduler_worker/ ./apps/scheduler_worker/
COPY packages/ ./packages/

# Allow appuser to write uv cache and logs at runtime
RUN mkdir -p /app/.cache/uv /app/logs && chown -R appuser /app/.cache /app/logs
ENV UV_CACHE_DIR=/app/.cache/uv

USER appuser

CMD ["uv", "run", "--no-dev", "uvicorn", "apps.scheduler_worker.main:app", "--host", "0.0.0.0", "--port", "8002"]
