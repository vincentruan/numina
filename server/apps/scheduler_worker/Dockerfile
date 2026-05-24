FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai
RUN pip install uv --no-cache-dir

WORKDIR /app

# Install dependencies from server/ root (cached layer)
# DeerFlow harness will be fetched from GitHub automatically via uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra worker

# Copy application code
COPY apps/scheduler_worker/ ./apps/scheduler_worker/
COPY packages/ ./packages/

CMD ["uv", "run", "--no-dev", "uvicorn", "apps.scheduler_worker.main:app", "--host", "0.0.0.0", "--port", "8002"]
