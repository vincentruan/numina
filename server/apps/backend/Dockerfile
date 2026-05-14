FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai
RUN pip install uv --no-cache-dir

WORKDIR /app

# Install dependencies from server/ root (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra backend

# Copy application code
COPY apps/backend/ ./apps/backend/
COPY packages/ ./packages/

CMD ["uv", "run", "--no-dev", "uvicorn", "apps.backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]