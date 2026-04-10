FROM python:3.13-slim

WORKDIR /app

# 安装 uv
RUN pip install uv --no-cache-dir

COPY pyproject.toml .
RUN uv pip install --system -e .

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
