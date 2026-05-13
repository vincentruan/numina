FROM python:3.11-slim

RUN pip install uv

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai

WORKDIR /app

# Install dependencies from scheduler_worker's own lockfile
COPY apps/scheduler_worker/pyproject.toml apps/scheduler_worker/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the full server tree (apps/ + packages/)
COPY . .

CMD ["uv", "run", "--no-dev", "uvicorn", "apps.scheduler_worker.main:app", "--host", "0.0.0.0", "--port", "8002"]
