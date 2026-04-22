# Agent Module Structure Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agent entry point files (main.py, config.py, scheduler.py) into app/ package to match backend structure.

**Architecture:** Minimal structural change - create agent/app/ package for entry points only, preserving existing organized directories (routers, services, schemas, core, tests). Update all import paths, Dockerfile entry point, and documentation.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pytest, uvicorn, Docker

---

## File Structure

### New Files
- `agent/app/__init__.py` - Empty package init
- `agent/app/main.py` - FastAPI entry point (moved from root)
- `agent/app/config.py` - AgentSettings config (moved from root)
- `agent/app/scheduler.py` - APScheduler setup (moved from root)

### Modified Files
- `agent/Dockerfile:20` - Entry point change
- `agent/routers/*.py` (7 files) - Import path updates
- `agent/services/orchestrator.py` - Import path update
- `agent/core/backend_client.py` - Import path update
- `agent/tests/conftest.py` - Import path update
- `agent/tests/integration/test_full_dispatch.py` - Import path update
- `agent/README.md` - Structure documentation
- `README.md` - Add agent module
- `README.en.md` - Add agent module (English)
- `CLAUDE.md` - Add agent structure section

### Deleted Files
- `agent/main.py` - Moved to app/main.py
- `agent/config.py` - Moved to app/config.py
- `agent/scheduler.py` - Moved to app/scheduler.py

---

## Task 1: Create app package and move entry files

**Files:**
- Create: `agent/app/__init__.py`
- Create: `agent/app/main.py`
- Create: `agent/app/config.py`
- Create: `agent/app/scheduler.py`
- Delete: `agent/main.py`
- Delete: `agent/config.py`
- Delete: `agent/scheduler.py`

- [ ] **Step 1: Create app package directory**

```bash
mkdir -p agent/app
```

- [ ] **Step 2: Create __init__.py**

```bash
touch agent/app/__init__.py
```

- [ ] **Step 3: Move main.py with import updates**

Read current file:
```bash
cat agent/main.py
```

Create new file with updated imports:
```python
# agent/app/main.py
"""Numina AI Agent 微服务入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.scheduler import setup_schedules, scheduler
from core.logging import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_required()
    from app.scheduler import setup_schedules, scheduler
    setup_schedules()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Numina AI Agent",
    version="0.1.0",
    lifespan=lifespan,
    # 不对外暴露 docs（内部服务）
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None,
)


from routers import report as report_router
from routers import suggest as suggest_router
from routers import alerts as alerts_router
from routers import disposal as disposal_router
from routers import liability as liability_router
from routers import allocation as allocation_router
from routers import chat as chat_router

app.include_router(report_router.router)
app.include_router(suggest_router.router)
app.include_router(alerts_router.router)
app.include_router(disposal_router.router)
app.include_router(liability_router.router)
app.include_router(allocation_router.router)
app.include_router(chat_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "numina-agent"}
```

Write to new location:
```bash
cat > agent/app/main.py << 'EOF'
"""Numina AI Agent 微服务入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.scheduler import setup_schedules, scheduler
from core.logging import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_required()
    from app.scheduler import setup_schedules, scheduler
    setup_schedules()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Numina AI Agent",
    version="0.1.0",
    lifespan=lifespan,
    # 不对外暴露 docs（内部服务）
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None,
)


from routers import report as report_router
from routers import suggest as suggest_router
from routers import alerts as alerts_router
from routers import disposal as disposal_router
from routers import liability as liability_router
from routers import allocation as allocation_router
from routers import chat as chat_router

app.include_router(report_router.router)
app.include_router(suggest_router.router)
app.include_router(alerts_router.router)
app.include_router(disposal_router.router)
app.include_router(liability_router.router)
app.include_router(allocation_router.router)
app.include_router(chat_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "numina-agent"}
EOF
```

- [ ] **Step 4: Move config.py (no import changes needed)**

```bash
cp agent/config.py agent/app/config.py
```

- [ ] **Step 5: Move scheduler.py (no import changes needed)**

```bash
cp agent/scheduler.py agent/app/scheduler.py
```

- [ ] **Step 6: Remove old files**

```bash
rm agent/main.py agent/config.py agent/scheduler.py
```

- [ ] **Step 7: Commit file moves**

```bash
git add agent/app/
git rm agent/main.py agent/config.py agent/scheduler.py
git commit -m "refactor(agent): move entry points to app/ package"
```

---

## Task 2: Update router imports

**Files:**
- Modify: `agent/routers/alerts.py:1-10`
- Modify: `agent/routers/allocation.py:1-10`
- Modify: `agent/routers/chat.py:1-10`
- Modify: `agent/routers/disposal.py:1-10`
- Modify: `agent/routers/liability.py:1-10`
- Modify: `agent/routers/report.py:1-10`
- Modify: `agent/routers/suggest.py:1-10`

- [ ] **Step 1: Update alerts.py import**

Find the import line:
```bash
grep "from config import" agent/routers/alerts.py
```

Replace with new import:
```bash
sed -i '' 's/from config import settings/from app.config import settings/' agent/routers/alerts.py
```

- [ ] **Step 2: Update allocation.py import**

```bash
sed -i '' 's/from config import settings/from app.config import settings/' agent/routers/allocation.py
```

- [ ] **Step 3: Update chat.py import**

```bash
sed -i '' 's/from config import settings/from app.config import settings/' agent/routers/chat.py
```

- [ ] **Step 4: Update disposal.py import**

```bash
sed -i '' 's/from config import settings/from app.config import settings/' agent/routers/disposal.py
```

- [ ] **Step 5: Update liability.py import**

```bash
sed -i '' 's/from config import settings/from app.config import settings/' agent/routers/liability.py
```

- [ ] **Step 6: Update report.py import**

```bash
sed -i '' 's/from config import settings/from app.config import settings/' agent/routers/report.py
```

- [ ] **Step 7: Update suggest.py import**

```bash
sed -i '' 's/from config import settings/from app.config import settings/' agent/routers/suggest.py
```

- [ ] **Step 8: Verify all router imports updated**

```bash
grep -r "from app.config import settings" agent/routers/ | wc -l
```
Expected: 7 (one per router file)

- [ ] **Step 9: Commit router changes**

```bash
git add agent/routers/
git commit -m "refactor(agent): update router imports to app.config"
```

---

## Task 3: Update service imports

**Files:**
- Modify: `agent/services/orchestrator.py:1-20`

- [ ] **Step 1: Update orchestrator.py import**

```bash
sed -i '' 's/from config import settings/from app.config import settings/' agent/services/orchestrator.py
```

- [ ] **Step 2: Verify import updated**

```bash
grep "from app.config import settings" agent/services/orchestrator.py
```
Expected: Output shows the updated import line

- [ ] **Step 3: Commit service changes**

```bash
git add agent/services/orchestrator.py
git commit -m "refactor(agent): update orchestrator import to app.config"
```

---

## Task 4: Update core imports

**Files:**
- Modify: `agent/core/backend_client.py:1-20`

- [ ] **Step 1: Update backend_client.py import**

```bash
sed -i '' 's/from config import settings/from app.config import settings/' agent/core/backend_client.py
```

- [ ] **Step 2: Verify import updated**

```bash
grep "from app.config import settings" agent/core/backend_client.py
```
Expected: Output shows the updated import line

- [ ] **Step 3: Commit core changes**

```bash
git add agent/core/backend_client.py
git commit -m "refactor(agent): update backend_client import to app.config"
```

---

## Task 5: Update test imports

**Files:**
- Modify: `agent/tests/conftest.py`
- Modify: `agent/tests/integration/test_full_dispatch.py`

- [ ] **Step 1: Check conftest.py imports**

```bash
grep -E "from config import|from main import|from scheduler import" agent/tests/conftest.py
```

- [ ] **Step 2: Update conftest.py imports**

```bash
sed -i '' 's/from config import/from app.config import/' agent/tests/conftest.py
sed -i '' 's/from main import/from app.main import/' agent/tests/conftest.py
sed -i '' 's/from scheduler import/from app.scheduler import/' agent/tests/conftest.py
```

- [ ] **Step 3: Check test_full_dispatch.py imports**

```bash
grep -E "from config import|from main import|from scheduler import" agent/tests/integration/test_full_dispatch.py
```

- [ ] **Step 4: Update test_full_dispatch.py imports**

```bash
sed -i '' 's/from config import/from app.config import/' agent/tests/integration/test_full_dispatch.py
sed -i '' 's/from main import/from app.main import/' agent/tests/integration/test_full_dispatch.py
sed -i '' 's/from scheduler import/from app.scheduler import/' agent/tests/integration/test_full_dispatch.py
```

- [ ] **Step 5: Verify all test imports updated**

```bash
grep -r "from app\." agent/tests/ | grep -E "config|main|scheduler" | wc -l
```
Expected: At least 2 (conftest + test_full_dispatch)

- [ ] **Step 6: Run tests to verify changes**

```bash
cd agent && uv run pytest tests/ -v --tb=short
```
Expected: All tests pass (may take 30-60 seconds)

- [ ] **Step 7: Commit test changes**

```bash
git add agent/tests/
git commit -m "refactor(agent): update test imports to app package"
```

---

## Task 6: Update Dockerfile entry point

**Files:**
- Modify: `agent/Dockerfile:20`

- [ ] **Step 1: Update Dockerfile CMD**

Current line (line 20):
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

Replace with:
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

Execute:
```bash
sed -i '' 's/main:app/app.main:app/' agent/Dockerfile
```

- [ ] **Step 2: Verify Dockerfile change**

```bash
grep "app.main:app" agent/Dockerfile
```
Expected: Output shows "CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]"

- [ ] **Step 3: Commit Dockerfile change**

```bash
git add agent/Dockerfile
git commit -m "refactor(agent): update Dockerfile entry point to app.main"
```

---

## Task 7: Update agent README

**Files:**
- Modify: `agent/README.md`

- [ ] **Step 1: Update Quick Start section**

Find and replace the uvicorn command:
```bash
sed -i '' 's/uvicorn main:app/uvicorn app.main:app/' agent/README.md
```

- [ ] **Step 2: Add architecture structure diagram**

Add app/ package to the architecture diagram. Find the current structure and update to show app/ package.

- [ ] **Step 3: Add note about structure**

Add this line after the architecture section:
```markdown
**注意**: 入口文件位于 `app/` 包下，与 backend 结构保持一致。
```

- [ ] **Step 4: Verify README updates**

```bash
grep "app.main:app" agent/README.md
grep "app/ 包下" agent/README.md
```
Expected: Both grep commands return output

- [ ] **Step 5: Commit README change**

```bash
git add agent/README.md
git commit -m "docs(agent): update README for app/ package structure"
```

---

## Task 8: Update project README (Chinese)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add agent to tech stack table**

Find the tech stack table and add agent row:
```markdown
| Agent | Python 3.11+ + FastAPI + DeerFlow/LangChain |
```

- [ ] **Step 2: Add agent to project structure**

Add agent module section:
```markdown
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

- [ ] **Step 3: Add agent test section**

Add after backend tests section:
```markdown
Agent 包含单元测试和集成测试：
```bash
cd agent
uv run pytest tests/ -v
```
```

- [ ] **Step 4: Add agent API endpoints**

Add agent endpoints section:
```markdown
### Agent API 端点

Agent 微服务为内部服务，需 `X-Agent-Token` 认证：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/report/generate` | 家庭资产体检报告 |
| POST | `/alerts/aging` | 固定资产老化预警 |
| POST | `/liability/analyze` | 负债结构分析 |
| POST | `/disposal/scan` | 闲置资产处置建议 |
| POST | `/allocation/drift` | 资产配置漂移检测 |
| POST | `/chat/ask` | 问答助手 |
| POST | `/suggest/asset` | 资产录入智能建议 |
```

- [ ] **Step 5: Commit README changes**

```bash
git add README.md
git commit -m "docs: add agent module to README"
```

---

## Task 9: Update project README (English)

**Files:**
- Modify: `README.en.md`

- [ ] **Step 1: Add agent to tech stack table**

Find the tech stack table and add agent row:
```markdown
| Agent | Python 3.11+ + FastAPI + DeerFlow/LangChain |
```

- [ ] **Step 2: Add agent to project structure**

Add agent module section:
```markdown
├── agent/                    # AI analysis microservice
│   ├── app/                  # Entry point package
│   │   ├── main.py           # FastAPI entry
│   │   ├── config.py         # Configuration
│   │   └── scheduler.py      # Scheduled tasks
│   ├── routers/              # API routes
│   ├── services/             # Business logic
│   ├── schemas/              # Data models
│   └── core/                 # Core components
│   └── tests/                # pytest tests
```

- [ ] **Step 3: Add agent test section**

Add after backend tests section:
```markdown
Agent includes unit and integration tests:
```bash
cd agent
uv run pytest tests/ -v
```
```

- [ ] **Step 4: Add agent API endpoints**

Add agent endpoints section:
```markdown
### Agent API Endpoints

Agent microservice is internal, requires `X-Agent-Token` authentication:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/report/generate` | Family asset health report |
| POST | `/alerts/aging` | Fixed asset aging alert |
| POST | `/liability/analyze` | Liability structure analysis |
| POST | `/disposal/scan` | Idle asset disposal suggestion |
| POST | `/allocation/drift` | Asset allocation drift detection |
| POST | `/chat/ask` | Q&A assistant |
| POST | `/suggest/asset` | Asset entry smart suggestion |
```

- [ ] **Step 5: Commit README.en.md changes**

```bash
git add README.en.md
git commit -m "docs: add agent module to README.en"
```

---

## Task 10: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add Agent Structure section after Backend Structure**

Find the Backend Structure section and add after it:
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

- [ ] **Step 2: Add Agent commands to Development Commands section**

Add after backend commands:
```markdown
### Agent Development

```bash
cd agent

# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Run tests
uv run pytest tests/ -v

# Type check
uv run mypy . --exclude vendor
```
```

- [ ] **Step 3: Commit CLAUDE.md changes**

```bash
git add CLAUDE.md
git commit -m "docs: add agent structure to CLAUDE.md"
```

---

## Task 11: Final verification and testing

**Files:**
- Test: All agent tests
- Test: Type checking
- Test: Dev server startup
- Test: Docker build

- [ ] **Step 1: Run all agent tests**

```bash
cd agent && uv run pytest tests/ -v
```
Expected: All tests pass (no failures)

- [ ] **Step 2: Run type checking**

```bash
cd agent && uv run mypy . --exclude vendor
```
Expected: No type errors (may show warnings for vendor dependencies)

- [ ] **Step 3: Test dev server startup (quick check)**

```bash
cd agent && timeout 5 uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 || true
```
Expected: Server starts successfully (timeout prevents hanging)

- [ ] **Step 4: Verify Docker build (optional, may take 2-3 minutes)**

```bash
docker-compose build agent
```
Expected: Build completes successfully

- [ ] **Step 5: Final commit summary**

```bash
git log --oneline -10
```
Expected: Shows 10 commits including all refactoring commits

---

## Spec Coverage Check

| Spec Requirement | Task Covered |
|------------------|--------------|
| Create app/ package | Task 1 |
| Move main.py, config.py, scheduler.py | Task 1 |
| Update imports in moved files | Task 1 |
| Update router imports | Task 2 |
| Update service imports | Task 3 |
| Update core imports | Task 4 |
| Update test imports | Task 5 |
| Update Dockerfile | Task 6 |
| Update agent/README.md | Task 7 |
| Update README.md (Chinese) | Task 8 |
| Update README.en.md | Task 9 |
| Update CLAUDE.md | Task 10 |
| Run tests and verify | Task 11 |

---

## Placeholder Scan Results

✅ No TBD, TODO, or placeholder patterns found
✅ All import updates have exact sed commands
✅ All code blocks show complete content
✅ All file paths are exact
✅ All commands have expected output descriptions

---

## Type Consistency Check

✅ Import path pattern consistent: `from app.config import settings`
✅ Dockerfile entry point matches new structure: `app.main:app`
✅ Documentation references consistent: `app/` package throughout

---

## Execution Approach

**Recommended: Subagent-Driven Development**

Dispatch fresh subagent per task, review between tasks for fast iteration and verification.

**Alternative: Inline Execution**

Execute tasks in this session using executing-plans skill with batch execution and checkpoints.