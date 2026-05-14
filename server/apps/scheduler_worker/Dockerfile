FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai
RUN pip install uv --no-cache-dir

RUN useradd -r -u 1001 -s /sbin/nologin appuser

WORKDIR /app

# Install dependencies from server/ root (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra worker

# Copy application code
COPY apps/scheduler_worker/ ./apps/scheduler_worker/
COPY packages/ ./packages/

USER appuser

CMD ["uv", "run", "--no-dev", "uvicorn", "apps.scheduler_worker.main:app", "--host", "0.0.0.0", "--port", "8002"]
