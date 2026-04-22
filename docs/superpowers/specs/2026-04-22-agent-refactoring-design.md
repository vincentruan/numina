---
title: Agent Module Structure Refactoring
date: 2026-04-22
module: agent
tags: [refactoring, structure, documentation]
---

# Agent Module Structure Refactoring Design

## Problem Statement

The agent module currently has entry point files (`main.py`, `config.py`, `scheduler.py`) at the root level, inconsistent with the backend module's organized structure where all app code resides in an `app/` package. This creates:

1. **Inconsistent project structure** - backend uses `backend/app/` while agent has root-level files
2. **Import path confusion** - mixed import styles across modules
3. **Missing documentation** - agent module is not documented in project-level README and CLAUDE.md

## Solution Approach

**Option B: Minimal change** - Move only entry point files into `agent/app/` package, preserving existing organized directories (`routers/`, `services/`, `schemas/`, `core/`, `tests/`).

This mirrors backend's structure for entry points while respecting the already-organized agent module layout.

## Directory Structure

### Before

```
agent/
├── main.py              # root level
├── config.py            # root level
├── scheduler.py         # root level
├── routers/
├── services/
├── schemas/
├── core/
├── tests/
├── README.md
└── pyproject.toml
```

### After

```
agent/
├── app/
│   ├── __init__.py      # new - package init
│   ├── main.py          # moved from root
│   ├── config.py        # moved from root
│   └── scheduler.py     # moved from root
├── routers/             # unchanged
├── services/            # unchanged
├── schemas/             # unchanged
├── core/                # unchanged
├── tests/               # unchanged
├── README.md            # updated structure docs
└── pyproject.toml       # updated entry point
```

## Import Path Changes

### Files Moving to app/

**app/main.py:**
```python
# Before
from config import settings
from scheduler import setup_schedules, scheduler

# After
from app.config import settings
from app.scheduler import setup_schedules, scheduler
```

**app/config.py:**
- No import changes needed (only imports pydantic_settings)

**app/scheduler.py:**
- No import changes needed (only imports apscheduler)

### Files in Existing Directories

**routers/*.py, services/*.py, core/*.py, schemas/*.py:**
```python
# Before
from config import settings
from core.logging import setup_logging

# After
from app.config import settings
from core.logging import setup_logging  # unchanged
```

Files importing from `core/`, `services/`, `schemas/`, `routers/` remain unchanged since these directories stay at root level.

### Tests

**tests/unit/*.py, tests/integration/*.py:**
```python
# Before
from config import settings
from services.orchestrator import Orchestrator

# After
from app.config import settings
from services.orchestrator import Orchestrator  # unchanged
```

## Configuration Updates

### pyproject.toml

```toml
# Before
[project.scripts]
# (none, entry point in Dockerfile)

# After - no changes needed, Dockerfile handles entry point

# Optional: add script entry point for local development
[project.scripts]
agent-dev = "uvicorn:app.main:app"
```

### Dockerfile

```dockerfile
# Before
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

# After
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### docker-compose.yml

No changes needed - Dockerfile path is relative to `agent/` directory.

## Documentation Updates

### agent/README.md

**Updates:**
1. Quick start command: `uv run uvicorn app.main:app --reload`
2. Architecture diagram: Add `app/` package in structure
3. Project structure section: Document `app/` directory
4. Note: "入口文件位于 `app/` 包下，与 backend 结构保持一致"

### README.md (Chinese)

**Updates:**
1. 技术栈 section: Add agent module
   ```
   | 层级 | 技术 |
   |------|------|
   | 前端 | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
   | 后端 | Python 3.11+ + FastAPI + SQLAlchemy + Alembic |
   | Agent | Python 3.11+ + FastAPI + DeerFlow/LangChain |  # new
   ```

2. 项目结构 section: Add agent module
   ```
   ├── agent/                    # AI 分析微服务
   │   ├── app/                  # 入口文件包
   │   │   ├── main.py           # FastAPI 入口
   │   │   ├── config.py         # 配置
   │   │   └── scheduler.py      # 定时任务
   │   ├── routers/              # API 路由
   │   ├── services/             # 业务逻辑
   │   ├── schemas/              # 数据模型
   │   └── core/                 # 核心组件
   │   └── tests/                # pytest 测试
   ```

3. 测试 section: Add agent tests
   ```
   后端包含 389 个自动化测试...（现有内容）

   Agent 包含单元测试和集成测试：
   ```bash
   cd agent
   uv run pytest tests/ -v
   ```
   ```

4. API 文档 section: Add agent endpoints
   ```
   ### Agent API 端点

   Agent 微服务为内部服务，需 `X-Agent-Token` 认证：

   | 方法 | 路径 | 说明 |
   |------|------|------|
   | POST | `/report/generate` | 家庭资产体检报告 |
   | POST | `/alerts/aging` | 固定资产老化预警 |
   | POST | `/liability/analyze` | 负债结构分析 |
   | ... | ... | ... |
   ```

### README.en.md (English)

Mirror all Chinese README updates in English.

### CLAUDE.md

**Add new section after "Backend Structure":**

```markdown
### Agent Structure

```
agent/app/
├── main.py         # FastAPI 入口、lifespan、router 注册
├── config.py       # AgentSettings (Pydantic BaseSettings)
├── scheduler.py    # APScheduler 定时任务配置
agent/
├── routers/        # FastAPI route handlers
│   ├── report.py       # 家庭资产体检报告
│   ├── alerts.py       # 固定资产老化预警
│   ├── liability.py    # 负债结构分析
│   ├── disposal.py     # 闲置资产处置建议
│   ├── allocation.py   # 资产配置漂移检测
│   ├── chat.py         # 问答助手
│   └── suggest.py      # 资产录入智能建议
├── services/       # 业务逻辑 (orchestrator, fallback_engine, deerflow_adapter)
├── schemas/        # Pydantic request/response schemas
├── core/           # 核心组件 (backend_client, llm, logging, pii_redactor)
└── tests/          # pytest 测试
```

**Key Patterns:**
- **DeerFlow Toggle**: `USE_DEERFLOW=false` → fallback_engine (direct LLM); `USE_DEERFLOW=true` → deerflow_adapter
- **PII Redaction**: All user data passes through `pii_redactor` before LLM calls
- **Policy Guard**: All agent requests checked by `policy_guard` before execution
- **Audit Logging**: Every agent decision logged to `logs/agent-audit.log`
- **Internal Auth**: Backend calls agent with `X-Agent-Token` + `X-Family-Id` headers
```

**Update project structure section:**
```markdown
## Architecture

### Backend Structure
... (existing content)

### Agent Structure
... (new section above)

### Frontend Structure
... (existing content)
```

## Implementation Steps

1. **Create app/ directory and move files**
   - Create `agent/app/__init__.py` (empty)
   - Move `main.py` → `app/main.py`
   - Move `config.py` → `app/config.py`
   - Move `scheduler.py` → `app/scheduler.py`

2. **Update imports in moved files**
   - Update `app/main.py`: imports from `app.config`, `app.scheduler`
   - No changes needed in `app/config.py`, `app/scheduler.py`

3. **Update imports in existing directories**
   - Update all files in `routers/`, `services/`, `core/`, `schemas/` that import `config`
   - Pattern: `from config import settings` → `from app.config import settings`

4. **Update tests imports**
   - Update all test files that import `config`, `main`, or `scheduler`
   - Pattern: `from config import` → `from app.config import`

5. **Update Dockerfile**
   - Change entry point: `main:app` → `app.main:app`

6. **Update documentation**
   - Update `agent/README.md`
   - Update `README.md` (Chinese)
   - Update `README.en.md` (English)
   - Update `CLAUDE.md`

7. **Verify and test**
   - Run `uv run pytest tests/ -v`
   - Run `uv run mypy . --exclude vendor`
   - Test dev server: `uv run uvicorn app.main:app --reload`
   - Test health endpoint
   - Build Docker image

## Risk Mitigation

### Testing Checklist

Before committing:
1. ✅ All agent tests pass: `cd agent && uv run pytest tests/ -v`
2. ✅ No type errors: `cd agent && uv run mypy . --exclude vendor`
3. ✅ Dev server starts: `cd agent && uv run uvicorn app.main:app --reload`
4. ✅ Health check works: `curl localhost:8001/health`
5. ✅ Docker builds: `docker-compose build agent`

### Rollback Plan

- Commit as single atomic change
- Easy revert: `git revert <commit-hash>`
- No data loss risk - only structural changes

## Success Criteria

1. Agent module structure mirrors backend for entry points
2. All existing tests pass without modification to test logic
3. Documentation accurately reflects new structure
4. Dev server and Docker deployment work identically
5. Import paths are consistent and clear

## Scope

**In Scope:**
- Move entry point files to `agent/app/`
- Update all imports referencing moved files
- Update Dockerfile entry point
- Update all documentation

**Out of Scope:**
- Moving `routers/`, `services/`, `schemas/`, `core/` directories
- Refactoring any business logic
- Changing test logic
- Adding new features

## Timeline

Single session implementation:
- File moves and imports: ~15 minutes
- Dockerfile update: ~2 minutes
- Documentation updates: ~10 minutes
- Testing and verification: ~5 minutes

**Total: ~30 minutes**