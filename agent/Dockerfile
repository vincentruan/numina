FROM python:3.13-slim

WORKDIR /app

# 安装 uv 和时区数据
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Shanghai
RUN pip install uv --no-cache-dir

# 安装 DeerFlow harness（vendor 目录由 scripts/vendor-harness.sh 预先填充）
COPY vendor/deerflow-harness /opt/deerflow-harness
# 同时复制到 vendor/ 目录以满足 pyproject.toml workspace 配置
COPY vendor/deerflow-harness /app/vendor/deerflow-harness

COPY pyproject.toml requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
