# Numina - 家庭资产可视化
# 统一 Make 入口：环境准备 / 本地开发 / 编译构建 / 质量测试 / 数据库迁移 / Docker 发布
#
# 参考 DeerFlow 的 Makefile 组织方式，针对 numina 的 uv + pnpm 双 workspace 结构裁剪：
#   - 服务端：server/ 单 uv workspace，含 backend / agent / scheduler_worker 三个 app
#   - 前端：frontend/ pnpm workspace，含 main / child 两个 app
#   - Docker：docker-compose.yml (默认) / docker-compose.production.yml / docker-compose.dev.yml
#
# 约定：
#   - 所有 dev-* 目标会阻塞终端（热重载服务），需手动运行，不要由自动化 agent 启动。
#   - Docker 目标默认使用 docker-compose.yml，访问 http://localhost
#   - 服务端命令统一在 server/ 下执行；alembic 在 server/apps/backend/ 下执行。

.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash

# ── 工具与路径变量（可被环境覆盖）──────────────────────────
PYTHON ?= python3
UV     ?= uv
PNPM   ?= pnpm
COMPOSE ?= docker compose

SERVER_DIR   := server
FRONTEND_DIR := frontend
MAIN_APP     := frontend/apps/main
CHILD_APP    := frontend/apps/child
ALEMBIC_DIR  := $(SERVER_DIR)/apps/backend

# 服务端测试 / lint / 类型检查命令（在 SERVER_DIR 下运行）
PYTEST := $(UV) run pytest
RUFF   := $(UV) run ruff
MYPY   := $(UV) run mypy

.PHONY: help check install \
        dev-backend dev-agent dev-worker dev-frontend dev-child dev-all \
        build build-main build-child \
        typecheck lint format \
        test test-backend test-agent test-worker test-server test-frontend test-e2e \
        migrate migrate-revision migrate-down migrate-current \
        up down build-docker pull logs logs-backend logs-agent logs-worker logs-frontend ps restart shell up-prod down-prod \
        deploy deploy-dev \
        clean

# ══════════════════════════════════════════════════════════
# Help
# ══════════════════════════════════════════════════════════
help:
	@echo "Numina - 家庭资产可视化"
	@echo ""
	@echo "环境准备:"
	@echo "  make check         - 检查 uv / pnpm / docker 等依赖工具"
	@echo "  make install       - 安装服务端 (uv sync) + 前端 (pnpm install) 依赖"
	@echo ""
	@echo "本地开发 (热重载，阻塞终端，手动运行):"
	@echo "  make dev-backend   - 后端 API  :8000"
	@echo "  make dev-agent     - AI agent  :8001"
	@echo "  make dev-worker    - 调度 worker :8002"
	@echo "  make dev-frontend  - 主端 (成人) :5173"
	@echo "  make dev-child     - 子端       :5174"
	@echo "  make dev-all       - 同时启动以上 5 个 dev server (Ctrl-C 统一停止)"
	@echo ""
	@echo "编译 / 构建:"
	@echo "  make build         - 构建主端 + 子端 (生产产物)"
	@echo "  make build-main    - 仅构建主端"
	@echo "  make build-child   - 仅构建子端"
	@echo ""
	@echo "质量检查:"
	@echo "  make typecheck     - 前端 vue-tsc 类型检查 (主端 + 子端)"
	@echo "  make lint          - 前端 ESLint + 服务端 ruff check"
	@echo "  make format        - 服务端 ruff format + 前端 prettier"
	@echo ""
	@echo "测试:"
	@echo "  make test          - 服务端 pytest (backend) + 前端 vitest"
	@echo "  make test-backend  - 服务端 backend 套件"
	@echo "  make test-agent    - 服务端 agent 套件"
	@echo "  make test-worker   - 服务端 scheduler_worker 套件"
	@echo "  make test-server   - 服务端全部测试 (tests/)"
	@echo "  make test-frontend - 前端 vitest (主端 + 子端)"
	@echo "  make test-e2e      - Playwright E2E 回归 (基于 Docker)"
	@echo ""
	@echo "数据库迁移 (Alembic):"
	@echo "  make migrate                - alembic upgrade head"
	@echo "  make migrate-current        - 查看当前迁移版本"
	@echo "  make migrate-revision m=msg - 生成新迁移 (autogenerate)"
	@echo "  make migrate-down           - 回退一步"
	@echo ""
	@echo "Docker (默认 docker-compose.yml，访问 http://localhost):"
	@echo "  make up            - 构建并启动全部服务"
	@echo "  make down          - 停止并移除容器"
	@echo "  make build-docker  - 仅构建镜像 (不启动)"
	@echo "  make pull          - 拉取外部镜像 (nginx / mysql / postgres)"
	@echo "  make ps            - 查看容器状态"
	@echo "  make restart       - 重启全部服务"
	@echo "  make logs          - 跟踪全部日志"
	@echo "  make logs-backend  - 跟踪后端日志"
	@echo "  make logs-agent    - 跟踪 agent 日志"
	@echo "  make logs-worker   - 跟踪 worker 日志"
	@echo "  make logs-frontend - 跟踪前端日志"
	@echo "  make shell         - 进入 backend 容器 shell"
	@echo "  make up-prod       - 使用 docker-compose.production.yml 启动"
	@echo "  make down-prod     - 停止 production 容器"
	@echo ""
	@echo "部署:"
	@echo "  make deploy        - 生产部署 (scripts/deploy-docker.sh，含健康检查)"
	@echo "  make deploy-dev    - 开发模式部署 (放宽安全检查 + 种子数据)"
	@echo ""
	@echo "维护:"
	@echo "  make clean         - 清理构建产物与缓存 (不动 node_modules / 数据)"

# ══════════════════════════════════════════════════════════
# 环境准备
# ══════════════════════════════════════════════════════════
check:
	@echo "检查依赖工具..."
	@command -v $(UV) >/dev/null 2>&1 && echo "  ✓ uv: $$($(UV) --version)" || { echo "  ✗ uv 未安装 (https://docs.astral.sh/uv/)"; exit 1; }
	@command -v $(PNPM) >/dev/null 2>&1 && echo "  ✓ pnpm: $$($(PNPM) --version)" || { echo "  ✗ pnpm 未安装 (npm i -g pnpm)"; exit 1; }
	@command -v $(PYTHON) >/dev/null 2>&1 && echo "  ✓ python: $$($(PYTHON) --version)" || echo "  ⚠ python3 未找到"
	@command -v docker >/dev/null 2>&1 && echo "  ✓ docker: $$(docker --version)" || echo "  ⚠ docker 未安装 (Docker 相关目标将不可用)"
	@echo "✓ 依赖检查完成"

install:
	@echo "安装服务端依赖 (uv sync，含 backend/agent/worker + dev group)..."
	@cd $(SERVER_DIR) && $(UV) sync --extra backend --extra agent --extra worker --all-groups
	@echo "安装前端依赖 (pnpm install)..."
	@cd $(FRONTEND_DIR) && $(PNPM) install
	@echo "✓ 全部依赖安装完成"

# ══════════════════════════════════════════════════════════
# 本地开发 (热重载服务，阻塞终端)
# ══════════════════════════════════════════════════════════
dev-backend:
	@cd $(SERVER_DIR) && $(UV) run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000

dev-agent:
	@cd $(SERVER_DIR) && $(UV) run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001

dev-worker:
	@cd $(SERVER_DIR) && $(UV) run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002

dev-frontend:
	@cd $(MAIN_APP) && $(PNPM) dev --host 0.0.0.0

dev-child:
	@cd $(CHILD_APP) && $(PNPM) dev --host 0.0.0.0

dev-all:
	@for port in 8000 8001 8002 5173 5174; do \
	  if lsof -iTCP:$$port -sTCP:LISTEN -P -n >/dev/null 2>&1; then \
	    echo "✗ 端口 $$port 已被占用:"; \
	    lsof -iTCP:$$port -sTCP:LISTEN -P -n 2>/dev/null | grep LISTEN; \
	    echo "请先释放端口再运行 make dev-all"; \
	    exit 1; \
	  fi; \
	done
	@echo "启动全部 dev server (Ctrl-C 停止)..."
	@cd $(SERVER_DIR) && $(UV) run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000 & \
	cd $(SERVER_DIR) && $(UV) run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001 & \
	cd $(SERVER_DIR) && $(UV) run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002 & \
	cd $(MAIN_APP) && $(PNPM) dev --host 0.0.0.0 & \
	cd $(CHILD_APP) && $(PNPM) dev --host 0.0.0.0 & \
	trap 'echo; echo "停止全部 dev server..."; kill $$(jobs -p) 2>/dev/null; wait 2>/dev/null; echo "✓ 已全部停止"; exit 0' INT TERM; \
	wait

# ══════════════════════════════════════════════════════════
# 编译 / 构建
# ══════════════════════════════════════════════════════════
build: build-main build-child

build-main:
	@echo "构建主端 (frontend/apps/main)..."
	@cd $(MAIN_APP) && $(PNPM) build

build-child:
	@echo "构建子端 (frontend/apps/child)..."
	@cd $(CHILD_APP) && $(PNPM) build

# ══════════════════════════════════════════════════════════
# 质量检查
# ══════════════════════════════════════════════════════════
typecheck:
	@echo "主端 typecheck..."
	@cd $(MAIN_APP) && $(PNPM) typecheck && $(PNPM) typecheck:test
	@echo "子端 typecheck..."
	@cd $(CHILD_APP) && $(PNPM) typecheck

lint:
	@echo "前端 ESLint (主端 + 子端)..."
	@cd $(MAIN_APP) && $(PNPM) lint
	@cd $(CHILD_APP) && $(PNPM) lint
	@echo "服务端 ruff check..."
	@cd $(SERVER_DIR) && $(RUFF) check apps/ packages/

format:
	@echo "服务端 ruff format..."
	@cd $(SERVER_DIR) && $(RUFF) format apps/ packages/
	@echo "前端 prettier..."
	@cd $(MAIN_APP) && $(PNPM) format
	@cd $(CHILD_APP) && $(PNPM) format

# ══════════════════════════════════════════════════════════
# 测试
# ══════════════════════════════════════════════════════════
test: test-backend test-frontend

test-backend:
	@cd $(SERVER_DIR) && $(PYTEST) tests/backend -q

test-agent:
	@cd $(SERVER_DIR) && $(PYTEST) tests/agent -q

test-worker:
	@cd $(SERVER_DIR) && $(PYTEST) tests/scheduler_worker -q

test-server:
	@cd $(SERVER_DIR) && $(PYTEST) tests/ -q

test-frontend:
	@cd $(MAIN_APP) && $(PNPM) test:run
	@cd $(CHILD_APP) && $(PNPM) test:run

test-e2e:
	@./tests/run-regression.sh

# ══════════════════════════════════════════════════════════
# 数据库迁移 (Alembic, backend 专属)
# ══════════════════════════════════════════════════════════
migrate:
	@cd $(ALEMBIC_DIR) && $(UV) run alembic upgrade head

migrate-current:
	@cd $(ALEMBIC_DIR) && $(UV) run alembic current

migrate-revision:
	@test -n "$(m)" || { echo "用法: make migrate-revision m=\"迁移描述\""; exit 1; }
	@cd $(ALEMBIC_DIR) && $(UV) run alembic revision --autogenerate -m "$(m)"

migrate-down:
	@cd $(ALEMBIC_DIR) && $(UV) run alembic downgrade -1

# ══════════════════════════════════════════════════════════
# Docker (默认 docker-compose.yml)
# ══════════════════════════════════════════════════════════
up:
	@$(COMPOSE) up -d --build

down:
	@$(COMPOSE) down

build-docker:
	@$(COMPOSE) build

pull:
	@$(COMPOSE) pull --ignore-pull-failures

ps:
	@$(COMPOSE) ps

restart:
	@$(COMPOSE) restart

logs:
	@$(COMPOSE) logs -f

logs-backend:
	@$(COMPOSE) logs -f backend

logs-agent:
	@$(COMPOSE) logs -f agent

logs-worker:
	@$(COMPOSE) logs -f scheduler_worker

logs-frontend:
	@$(COMPOSE) logs -f frontend-main frontend-child

shell:
	@$(COMPOSE) exec backend bash

# Production compose (docker-compose.production.yml)
up-prod:
	@$(COMPOSE) -f docker-compose.production.yml up -d --build

down-prod:
	@$(COMPOSE) -f docker-compose.production.yml down

# ══════════════════════════════════════════════════════════
# 部署 (复用现有脚本)
# ══════════════════════════════════════════════════════════
deploy:
	@./scripts/deploy-docker.sh

deploy-dev:
	@./scripts/deploy-docker.sh --dev

# ══════════════════════════════════════════════════════════
# 维护
# ══════════════════════════════════════════════════════════
clean:
	@echo "清理构建产物与缓存..."
	@-rm -rf $(MAIN_APP)/dist $(CHILD_APP)/dist 2>/dev/null || true
	@-rm -rf $(SERVER_DIR)/.mypy_cache $(SERVER_DIR)/.ruff_cache .mypy_cache .ruff_cache 2>/dev/null || true
	@-find $(SERVER_DIR) -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	@-find $(FRONTEND_DIR) -type d -name ".vite" -not -path "*/node_modules/*" -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ 清理完成 (未触碰 node_modules / .numina/data / 测试产物)"
