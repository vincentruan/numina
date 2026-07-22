# Numina 全量测试方案（2026-07-22）

> 目标：基于现有架构建立完整、可执行、可回归的测试体系；执行并修复发现的问题；确保所有功能正常可用。
> 本文档是「理解架构 → 设计测试方案 → 执行+修复 → 确保可用」四步任务的第 1–2 步产出。

## 1. 现有架构理解

### 1.1 服务拓扑（server/，单 uv workspace）

| 服务 | 端口 | 职责 | 源模块规模 |
|------|------|------|-----------|
| `apps/backend` | 8000 | REST API（57 routers）+ 业务服务（~50 services） | 大 |
| `apps/agent` | 8001 | AI agent（DeerFlow/LangGraph stream_run，多 app dispatch） | 中（~20 services/routers） |
| `apps/scheduler_worker` | 8002 | APScheduler 7 个定时任务（汇率/文件同步/审计清理/令牌清理/会话清理/提醒/快照） | 小（jobs/__init__.py 单文件 7 函数） |
| `packages/core` | — | settings/logging/system_config | 8 模块 |
| `packages/db` | — | engine/session + 22 models | 22 模块 |
| `packages/domain` | — | 纯领域服务（liability_calculator/snapshot/notification/audit/device/exchange_rate） | 14 模块 |
| `packages/security` | — | JWT/密码/设备指纹/加密 | 5 模块 |
| `packages/storage` | — | 文件存储后端抽象 | 7 模块 |

### 1.2 前端（pnpm workspace）

| 应用/包 | 技术 | 现有 spec 数 |
|---------|------|-------------|
| `apps/main` | Vue3 + TS + Vant4 + ECharts（成人端） | 87 |
| `apps/child` | Vue3（儿童端） | 20 |
| `packages/auth` + `packages/math` | 共享组件/工具 | 5 |

### 1.3 测试基础设施（已具备，可复用）

- **backend conftest**：内存 SQLite + session 级 engine（StaticPool）+ function 级 SAVEPOINT 隔离；`TestClient` 走 HTTP；表只在 session 开始建一次（快）。
- **agent conftest**：独立，agent 测试多用 mock/纯函数。
- **pytest 配置**：`testpaths=["tests"]`、`asyncio_mode="auto"`、`pythonpath=["."]`。
- **前端**：vitest，mock vue-i18n/vue-router/vant/store；`useCurrency`→`useAuthStore` 需 Pinia 或 vi.mock。

### 1.4 覆盖现状与缺口（按风险排序）

| 区域 | 现有测试 | 源规模 | 缺口评估 |
|------|---------|--------|---------|
| `tests/backend` | 120 文件 | 57 routers + 50 services | 良好，但有零散未覆盖服务 |
| `tests/agent` | 30 文件 | ~20 模块 | 中等 |
| **`packages/*`** | **1 文件**（core/test_system_config） | **56 模块** | **严重** — db models、domain 服务、security、storage 几乎零覆盖 |
| **`scheduler_worker`** | **1 文件**（test_jobs_timing） | **7 定时任务** | **严重** — 7 个 job 的业务逻辑基本未测 |
| **`packages/domain/tests/`** | 1 文件（7 tests） | — | **孤立** — 不在 testpaths，pytest 默认不收集（已证实 collect=0） |

## 2. 测试方案设计

### 原则
- **目标驱动验证**：每个缺口先写会失败的测试，再确认通过（或暴露真 bug 后修复）。
- **复用现有 infra**：backend 用 SAVEPOINT 隔离 fixture；packages/scheduler 测试放 `server/tests/` 下以进入 testpaths。
- **外科手术式**：只补缺口、只修测试暴露的真 bug；不顺手重构。
- **不跑 dev server**：全部用 pytest/vitest 验证。

### 分层方案

#### P0 — 修复孤立/断裂的测试（先让现有测试真正跑起来）
- **P0-1** 把 `packages/domain/tests/test_liability_calculator.py` 纳入收集：迁移到 `server/tests/packages/domain/test_liability_calculator.py`（或加 conftest/testpaths），确认 7 tests 运行。
- **P0-2** 全量跑 `server/tests`，统计现状 pass/fail/error，建立基线。

#### P1 — packages 兜底测试（最严重缺口）
- **P1-1** `packages/domain`：liability_calculator（已在 P0-1 覆盖）外的 snapshot/notification/audit/device/exchange_rate 服务 — 纯逻辑优先（exchange_rate 换算、liability 摊还、snapshot 聚合）。
- **P1-2** `packages/security`：JWT 编解码/过期/撤销、密码 hash 校验、设备指纹 — 纯函数，低成本高价值。
- **P1-3** `packages/db`：关键 model 约束 + Snowflake ID 序列化（`SnowflakeBase` str-id 契约，CLAUDE.md 明确要求）。
- **P1-4** `packages/storage`：存储后端读写的 round-trip（本地 backend）。

#### P2 — scheduler_worker 7 个 job（严重缺口）
- 每个 job 一个 spec：mock SessionLocal + 领域服务，断言调用正确 + 异常路径不炸（finally 关 session）。
- 重点：fetch_rates（成功/失败）、snapshot（聚合正确性）、reminder（到期触发）、各 cleanup（删除过期记录）。

#### P3 — backend/agent 补盲（在 P0 基线确认后按 fail 情况补）
- 仅补 P0 全量跑暴露的 fail/error，以及核心资金路径（asset/liability/dashboard Numeric 精度）的回归。

#### P4 — 前端回归
- 全量 `pnpm -r test:run` + `pnpm -r typecheck`（已绿，作为回归基线）。
- 已知预存问题（不属本方案修复范围，仅记录）：`packages/auth` typecheck 缺 `vite/client` 类型（vite 非其依赖，环境 gap）。

### 执行顺序
P0 →（基线绿）→ P1 → P2 → P3 → P4 全量回归。每步：写测试 → 跑到绿 → 修复暴露的真 bug（单独 commit）→ 进入下一步。

### 验收标准
1. `cd server && uv run pytest` 全绿（含新 packages/scheduler/domain 测试），无 error。
2. `cd frontend && pnpm -r test:run` 全绿。
3. `pnpm -r typecheck`：除预存 `packages/auth` 环境 gap 外全绿。
4. 孤立的 domain 测试被纳入收集。
5. 所有修复均有对应测试佐证。
