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
OPENSSL ?= openssl

SERVER_DIR   := server
FRONTEND_DIR := frontend
MAIN_APP     := frontend/apps/main
CHILD_APP    := frontend/apps/child
ALEMBIC_DIR  := $(SERVER_DIR)/apps/backend
DATA_DIR     ?= .numina/data

# 服务端测试 / lint / 类型检查命令（在 SERVER_DIR 下运行）
PYTEST := $(UV) run pytest
RUFF   := $(UV) run ruff
MYPY   := $(UV) run mypy

# ── 部署配置变量（可被环境变量覆盖）──────────────────────────
# DB 选择: sqlite (默认) / mysql / postgres
NUMINA_DB ?= sqlite
# 生产域名（用于 CORS）
NUMINA_DOMAIN ?= localhost
# 邀请码数量
INVITATION_CODE_COUNT ?= 20
# 指定邀请码 (逗号分隔, 优先级高于 INVITATION_CODE_COUNT)
INVITATION_CODES ?=

.PHONY: help check install \
        setup setup-keys setup-env setup-data setup-db setup-db-mysql setup-db-postgres setup-invitation-codes \
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
	@echo "初始化部署 (首次部署必须运行):"
	@echo "  make setup         - 交互式初始化 (生成密钥 + .env + 数据目录 + 邀请码)"
	@echo "  make setup-keys    - 仅生成所有安全密钥 (SECRET_KEY, 加密密钥等)"
	@echo "  make setup-env     - 生成 .env 配置文件 (从模板)"
	@echo "  make setup-data    - 创建数据目录 (.numina/data/{db,uploads})"
	@echo "  make setup-db      - 初始化数据库 (默认 SQLite; 可选 NUMINA_DB=mysql|postgres)"
	@echo "  make setup-db-mysql     - 启动 MySQL 容器并初始化"
	@echo "  make setup-db-postgres  - 启动 PostgreSQL 容器并初始化"
	@echo "  make setup-invitation-codes              - 生成家庭邀请码 (默认随机20个)"
	@echo "    INVITATION_CODES=A,B,C make setup-invitation-codes  - 指定邀请码"
	@echo "    INVITATION_CODE_COUNT=5 make setup-invitation-codes - 指定随机数量"
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
	@echo "  make deploy        - 生产部署 (含健康检查 + 邀请码初始化)"
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
# 初始化部署 (首次部署)
# ══════════════════════════════════════════════════════════

setup-keys:
	@echo "生成安全密钥..."
	@command -v $(OPENSSL) >/dev/null 2>&1 || { echo "✗ openssl 未安装"; exit 1; }
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo "✗ python3 未安装"; exit 1; }
	@$(PYTHON) -c "from cryptography.fernet import Fernet" 2>/dev/null || \
		{ echo "安装 cryptography 库..."; pip3 install cryptography --quiet; }
	@echo "  SECRET_KEY=$$($(OPENSSL) rand -hex 32)"
	@echo "  ALTCHA_HMAC_KEY=$$($(OPENSSL) rand -hex 32)"
	@echo "  AI_ENCRYPTION_KEY=$$($(PYTHON) -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
	@echo "  AGENT_INTERNAL_TOKEN=$$($(OPENSSL) rand -hex 32)"
	@echo "  STORAGE_ENCRYPTION_KEY=$$($(PYTHON) -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
	@echo "✓ 密钥生成完成"

setup-env:
	@echo "配置环境变量..."
	@if [ -f .env ]; then \
		echo ".env 已存在，检查必要配置..."; \
		$(MAKE) _validate-env; \
	else \
		echo "从模板创建 .env..."; \
		$(MAKE) _create-env; \
	fi

_create-env:
	@command -v $(OPENSSL) >/dev/null 2>&1 || { echo "✗ openssl 未安装"; exit 1; }
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo "✗ python3 未安装"; exit 1; }
	@$(PYTHON) -c "from cryptography.fernet import Fernet" 2>/dev/null || \
		{ echo "安装 cryptography 库..."; pip3 install cryptography --quiet; }
	@$(PYTHON) scripts/generate_env.py --domain $(NUMINA_DOMAIN)
	@echo "✓ .env 已创建"

_validate-env:
	@NEED_UPDATE=0; \
	if ! grep -q "^SECRET_KEY=." .env || grep -q "^SECRET_KEY=your-secret-key" .env; then \
		echo "⚠ SECRET_KEY 需要配置"; \
		SECRET_KEY=$$($(OPENSSL) rand -hex 32); \
		if grep -q "^SECRET_KEY=" .env; then \
			sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=$$SECRET_KEY/" .env; \
		else \
			echo "SECRET_KEY=$$SECRET_KEY" >> .env; \
		fi; \
		NEED_UPDATE=1; \
	fi; \
	if ! grep -q "^ALTCHA_HMAC_KEY=." .env || grep -q "^ALTCHA_HMAC_KEY=$$" .env; then \
		echo "⚠ ALTCHA_HMAC_KEY 需要配置"; \
		ALTCHA_HMAC_KEY=$$($(OPENSSL) rand -hex 32); \
		if grep -q "^ALTCHA_HMAC_KEY=" .env; then \
			sed -i.bak "s/^ALTCHA_HMAC_KEY=.*/ALTCHA_HMAC_KEY=$$ALTCHA_HMAC_KEY/" .env; \
		else \
			echo "ALTCHA_HMAC_KEY=$$ALTCHA_HMAC_KEY" >> .env; \
		fi; \
		NEED_UPDATE=1; \
	fi; \
	if ! $(PYTHON) -c "from cryptography.fernet import Fernet; Fernet('$$(grep "^AI_ENCRYPTION_KEY=" .env 2>/dev/null | cut -d= -f2-)'.encode())" 2>/dev/null; then \
		echo "⚠ AI_ENCRYPTION_KEY 无效或未配置（需要 Fernet 格式）"; \
		AI_ENCRYPTION_KEY=$$($(PYTHON) -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"); \
		if grep -q "^AI_ENCRYPTION_KEY=" .env; then \
			sed -i.bak "s|^AI_ENCRYPTION_KEY=.*|AI_ENCRYPTION_KEY=$$AI_ENCRYPTION_KEY|" .env; \
		else \
			echo "AI_ENCRYPTION_KEY=$$AI_ENCRYPTION_KEY" >> .env; \
		fi; \
		NEED_UPDATE=1; \
	fi; \
	if ! grep -q "^AGENT_INTERNAL_TOKEN=." .env || grep -q "^AGENT_INTERNAL_TOKEN=$$" .env; then \
		echo "⚠ AGENT_INTERNAL_TOKEN 需要配置"; \
		AGENT_INTERNAL_TOKEN=$$($(OPENSSL) rand -hex 32); \
		if grep -q "^AGENT_INTERNAL_TOKEN=" .env; then \
			sed -i.bak "s/^AGENT_INTERNAL_TOKEN=.*/AGENT_INTERNAL_TOKEN=$$AGENT_INTERNAL_TOKEN/" .env; \
		else \
			echo "AGENT_INTERNAL_TOKEN=$$AGENT_INTERNAL_TOKEN" >> .env; \
		fi; \
		NEED_UPDATE=1; \
	fi; \
	if ! grep -q "^STORAGE_ENCRYPTION_KEY=." .env || grep -q "^STORAGE_ENCRYPTION_KEY=$$" .env; then \
		echo "⚠ STORAGE_ENCRYPTION_KEY 需要配置"; \
		STORAGE_ENCRYPTION_KEY=$$($(PYTHON) -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"); \
		if grep -q "^STORAGE_ENCRYPTION_KEY=" .env; then \
			sed -i.bak "s/^STORAGE_ENCRYPTION_KEY=.*/STORAGE_ENCRYPTION_KEY=$$STORAGE_ENCRYPTION_KEY/" .env; \
		else \
			echo "STORAGE_ENCRYPTION_KEY=$$STORAGE_ENCRYPTION_KEY" >> .env; \
		fi; \
		NEED_UPDATE=1; \
	fi; \
	if [ "$$NEED_UPDATE" = "1" ]; then \
		echo "✓ .env 已更新"; \
	else \
		echo "✓ .env 配置完整"; \
	fi

setup-data:
	@echo "创建数据目录..."
	@mkdir -p $(DATA_DIR)/db $(DATA_DIR)/uploads
	@echo "✓ 数据目录已创建: $(DATA_DIR)"

setup-db:
	@echo "初始化数据库 ($(NUMINA_DB))..."
	@if [ "$(NUMINA_DB)" = "sqlite" ]; then \
		echo "使用 SQLite (默认)"; \
		echo "数据库路径: $(DATA_DIR)/db/numina.db"; \
		echo "✓ SQLite 数据库将在首次启动时自动创建"; \
	elif [ "$(NUMINA_DB)" = "mysql" ]; then \
		$(MAKE) setup-db-mysql; \
	elif [ "$(NUMINA_DB)" = "postgres" ]; then \
		$(MAKE) setup-db-postgres; \
	else \
		echo "✗ 未知数据库类型: $(NUMINA_DB)"; \
		echo "  可选: sqlite (默认) / mysql / postgres"; \
		exit 1; \
	fi

setup-db-mysql:
	@echo "启动 MySQL 容器..."
	@$(COMPOSE) --profile mysql up -d mysql
	@echo "等待 MySQL 就绪..."
	@for i in $$(seq 1 30); do \
		if $(COMPOSE) exec -T mysql mysqladmin ping -h localhost >/dev/null 2>&1; then \
			echo "✓ MySQL 已就绪"; \
			echo "  连接字符串: mysql://numina:numinapass@numina-mysql:3306/numina"; \
			echo ""; \
			echo "请将以下内容添加到 .env:"; \
			echo "  DATABASE_URL=mysql+pymysql://numina:numinapass@numina-mysql:3306/numina"; \
			exit 0; \
		fi; \
		sleep 1; \
	done
	@echo "✗ MySQL 启动超时"
	@exit 1

setup-db-postgres:
	@echo "启动 PostgreSQL 容器..."
	@$(COMPOSE) --profile postgres up -d postgres
	@echo "等待 PostgreSQL 就绪..."
	@for i in $$(seq 1 30); do \
		if $(COMPOSE) exec -T postgres pg_isready -U numina >/dev/null 2>&1; then \
			echo "✓ PostgreSQL 已就绪"; \
			echo "创建 deerflow 数据库..."; \
			$(COMPOSE) exec -T postgres psql -U numina -d postgres -c "CREATE DATABASE deerflow;" 2>/dev/null || echo "  deerflow 数据库已存在"; \
			echo ""; \
			echo "请将以下内容添加到 .env:"; \
			echo "  DATABASE_URL=postgresql+psycopg://numina:numinapass@numina-postgres:5432/numina"; \
			echo ""; \
			echo "DeerFlow checkpoint 使用独立数据库:"; \
			echo "  DEERFLOW_DB_URL=postgresql+asyncpg://numina:numinapass@numina-postgres:5432/deerflow"; \
			exit 0; \
		fi; \
		sleep 1; \
	done
	@echo "✗ PostgreSQL 启动超时"
	@exit 1

setup-invitation-codes:
	@if [ -n "$(INVITATION_CODES)" ]; then \
		echo "创建指定邀请码: $(INVITATION_CODES)"; \
		$(COMPOSE) exec -T backend $(UV) run --no-dev python scripts/family_invitation_codes.py generate --codes "$(INVITATION_CODES)"; \
	else \
		echo "随机生成 $(INVITATION_CODE_COUNT) 个邀请码..."; \
		$(COMPOSE) exec -T backend $(UV) run --no-dev python scripts/family_invitation_codes.py generate --count $(INVITATION_CODE_COUNT); \
	fi
	@echo ""
	@echo "当前邀请码列表:"
	@$(COMPOSE) exec -T backend $(UV) run --no-dev python scripts/family_invitation_codes.py list
	@echo ""
	@echo "✓ 邀请码已生成 (新用户注册时需要)"

setup: setup-data setup-env setup-db
	@echo ""
	@echo "========================================"
	@echo "       Numina 初始化完成"
	@echo "========================================"
	@echo ""
	@echo "下一步:"
	@echo "  1. 编辑 .env 配置域名和数据库连接 (如使用 MySQL/PostgreSQL)"
	@echo "  2. 启动服务: make up"
	@echo "  3. 生成邀请码: make setup-invitation-codes"
	@echo ""

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

# PostgreSQL compose (docker-compose.yml + docker-compose.postgres.yml)
# Requires --profile postgres to activate the postgres service defined in docker-compose.yml
up-postgres:
	@$(COMPOSE) --profile postgres -f docker-compose.yml -f docker-compose.postgres.yml up -d --build

down-postgres:
	@$(COMPOSE) --profile postgres -f docker-compose.yml -f docker-compose.postgres.yml down

# ══════════════════════════════════════════════════════════
# 部署
# ══════════════════════════════════════════════════════════
deploy: setup-data setup-env
	@echo "构建并启动 Docker 服务..."
	@$(COMPOSE) down --remove-orphans 2>/dev/null || true
	@$(COMPOSE) up -d --build
	@echo "等待服务启动..."
	@for i in $$(seq 1 30); do \
		if $(COMPOSE) ps backend 2>/dev/null | grep -q "healthy"; then break; fi; \
		sleep 2; \
	done
	@$(COMPOSE) ps backend 2>/dev/null | grep -q "healthy" || { echo "✗ Backend 启动超时"; exit 1; }
	@for i in $$(seq 1 30); do \
		if $(COMPOSE) ps agent 2>/dev/null | grep -q "healthy"; then break; fi; \
		sleep 2; \
	done
	@$(COMPOSE) ps agent 2>/dev/null | grep -q "healthy" || { echo "✗ Agent 启动超时"; exit 1; }
	@echo "验证 API 健康检查..."
	@curl -sf http://localhost/api/health >/dev/null || { echo "✗ API 健康检查失败"; exit 1; }
	@echo ""
	@echo "========================================"
	@echo "       Numina 部署完成"
	@echo "========================================"
	@echo ""
	@$(COMPOSE) ps
	@echo ""
	@echo "访问地址: http://localhost"
	@echo "数据目录: $(DATA_DIR)"
	@echo ""
	@echo "下一步: make setup-invitation-codes  (生成家庭邀请码)"
	@echo ""

deploy-dev: setup-data
	@echo "开发模式部署..."
	@if [ ! -f .env ]; then \
		$(PYTHON) scripts/generate_env.py --dev --domain $(NUMINA_DOMAIN); \
	fi
	@$(COMPOSE) down --remove-orphans 2>/dev/null || true
	@$(COMPOSE) up -d --build
	@echo "等待服务启动..."
	@for i in $$(seq 1 30); do \
		if $(COMPOSE) ps backend 2>/dev/null | grep -q "healthy"; then break; fi; \
		sleep 2; \
	done
	@echo "初始化种子数据..."
	@cd $(SERVER_DIR) && TEST_DATABASE_URL="sqlite:///$$(pwd)/../$(DATA_DIR)/db/numina.db" $(UV) run python ../tests/data/seed_data.py --force || echo "⚠ 种子数据初始化失败"
	@$(COMPOSE) restart backend
	@echo ""
	@echo "========================================"
	@echo "   Numina 开发模式部署完成"
	@echo "========================================"
	@echo ""
	@echo "测试账号:"
	@echo "  demouser / DemoPass123     — 完整演示数据"
	@echo "  test_rich / TestRich123!   — 完整回归数据"
	@echo "  test_empty / TestEmpty123! — 空家庭"
	@echo ""

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
