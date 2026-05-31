FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata git && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai
ENV DEER_FLOW_CONFIG_PATH=/app/apps/agent/deerflow_config/base/config.yaml
RUN pip install uv --no-cache-dir

WORKDIR /app

# Install dependencies from server/ root (cached layer)
# DeerFlow harness will be fetched from GitHub automatically via uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra agent

# Apply compatibility patches to DeerFlow harness
COPY apps/agent/scripts/patch-langgraph-runtime.py apps/agent/scripts/patch-deerflow-thread-data.py ./apps/agent/scripts/
RUN uv run python apps/agent/scripts/patch-langgraph-runtime.py && \
    uv run python apps/agent/scripts/patch-deerflow-thread-data.py

# Copy application code
COPY apps/agent/ ./apps/agent/
COPY packages/ ./packages/

EXPOSE 8001

CMD ["uv", "run", "--no-dev", "uvicorn", "apps.agent.app.main:app", "--host", "0.0.0.0", "--port", "8001"]