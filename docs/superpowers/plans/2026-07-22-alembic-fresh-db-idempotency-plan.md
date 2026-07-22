# Alembic fresh-DB idempotency — 专项修复 Plan

> **状态**：complete — 方案 B 重建缺失 migration 历史，fresh-DB `alembic upgrade head` 成功（2026-07-22）。详见 [方案 B](./2026-07-22-alembic-plan-b-rebuild-missing-history.md)
> **日期**：2026-07-22
> **父文档**：[P2 计划](./2026-07-22-p2-compliance-a11y-plan.md) Deferred「fresh-DB base→head 系统性债务」
> **范围**：修复 `alembic upgrade head`（base→head）在全新 SQLite DB 上的系统性失败，使 fresh 部署/CI 从零建 DB 可行
> **背景**：测试用 `Base.metadata.create_all()` 绕过 alembic，dev/prod DB 已 stamp+migrate，故问题只暴露于 fresh 部署。

---

## Goal Capsule

**一句话**：让 `alembic upgrade head`（base `e3cba86157fd` → head `6c8a42d83b59`）在全新 SQLite DB 上成功跑通，无需依赖 `Base.metadata.create_all()`。

**为什么**：当前 fresh-DB base→head 在多个 migration 失败，阻塞新部署/CI 从零建 DB。根因是 2026-04~05 UUID→Snowflake 转换 + 多分支合并期的 migration 假定 legacy schema 状态、依赖顺序错误、SQLite 不兼容操作。

**完成标准**：fresh SQLite `alembic upgrade head` 成功 + `alembic downgrade base` 可逆 + backend 全量 pytest 不新增失败。

---

## 问题分类（4 类，已逐类定位）

### ⚠️ 结构性发现（2026-07-22 调查）：fresh-DB base→head 不可仅靠 guard 修复

深入迭代后发现根因超出 idempotency 范畴。**20 个表存在于当前模型但无任何 alembic upgrade migration 创建它们**（comm 比较 model tablename vs alembic create_table 升级路径）：

```
activities ai_chat_messages ai_chat_sessions ai_mcp_servers ai_providers
ai_reports ai_skills cached_files category_financial_defaults child_milestones
chore_instances chore_templates coin_transactions currencies exchange_rates
file_remote_locations revoked_tokens security_audit_logs storage_backends sync_events
```

根因：
1. 模型分散在 `packages/db/models/`（18 表）+ `apps/backend/app/models/`（ai_chat_session 等），共 57 表。
2. `initial_snowflake_schema` base 只创建 15 表，不含 AI 层。
3. `aa10837ae378`（2026-04-25）在 upgrade 路径 **drop** 了 cached_files/ai_chat_sessions/revoked_tokens 等（当时视为 legacy），但模型后来恢复——drop 仍在，fresh DB 上这些表被删。
4. `x2581y64zqr9` rename `ai_provider_configs`→`ai_providers` 等，但 rename 源在 fresh DB 从未被创建（依赖 legacy 状态）。
5. `ai_chat_sessions` 等 AI 表只存在于 `aa10837ae378` 的 **downgrade** 路径（还原 legacy UUID 表），fresh DB upgrade 永不创建。

**结论**：fresh-DB `alembic upgrade head` 在结构上无法成功——缺 20 个表的 create migration。修复需 **重建缺失的 migration 历史**（为这 20 表在链上正确位置插入 create_table migration，与当前模型定义逐列对齐），而非 guard。这是大规模高风险重建工作，超出"逐个修 idempotency"范畴。

**当前可行路径（建议）**：
- **方案 A（最小诚实）**：保持 fresh 部署用 `Base.metadata.create_all()`（已是测试方案），alembic 仅用于已存 DB 的增量迁移。记 fresh-DB base→head 为已知限制。
- **方案 B（重建历史，大工程）**：起独立 plan，逐表补 create migration + 修依赖顺序 + SQLite 兼容，全链验证。需逐表对照模型定义，风险高。
- 本 plan 已完成的 4 个有效修复（见 Progress Log）保留——它们修正真实 dependency-order/SQLite-compat/idempotency 缺陷，对已存 DB 增量迁移也有价值。

---

### 类别 1：idempotency drop/alter（legacy 不存在的表/列）
migration 假定 legacy pre-Alembic 表/列存在，fresh DB（从 `initial_snowflake_schema` 起）无之 → drop/alter 报 "no such index/table/column"。
- `aa10837ae378` ✅ 已修（commit 3a2f92a5）：guard 51 drops + short-circuit 50+ alters
- `c5724f07ecb4` ✅ 已修（commit 3a2f92a5）：guard 3 drop_column

### 类别 2：依赖顺序错误（migration 引用未创建的表/列）
migration 的 `down_revision` 使其在创建目标表的 sibling migration 之前运行。
- `g8057i30hfe7` ✅ 已修：`down_revision` 从 `f7946h29ged6` → `3ec41c70c529`（后者创建 `ai_provider_configs` 表）

### 类别 3：SQLite 不兼容 constraint（create_unique_constraint 等在 create_table 外）
SQLite 不支持 `ALTER TABLE ADD CONSTRAINT`，`op.create_unique_constraint`/`create_check_constraint`/`create_foreign_key` 在 `create_table` 外调用会 `NotImplementedError`。需内联到 `create_table` 或用 `batch_alter_table`。
- `i0279k52jgf9` — `op.create_unique_constraint('uq_family_skill', ...)` 在 create_table 后
- `c7583a86bst1` — TBD
- `w0159x32vnm9` — TBD

### 类别 4：bare alter_column（非 batch，SQLite 不支持 ALTER COLUMN TYPE）
`op.alter_column` 不在 `batch_alter_table` 内 → SQLite `NotImplementedError` 或 `ALTER COLUMN TYPE` 语法错误。需包 `batch_alter_table` 或 short-circuit（类 1 已用 short-circuit 处理 aa10837ae378）。
- `r9047s21tlm7` — 6 处 bare alter_column（make ai_result asset_id nullable）

### 未知后续 blocker
迭代 fresh-DB upgrade 直到 head，逐个暴露+修复。当前进度：已过 `724957cc6de9` merge，下一个 blocker 是 `i0279k52jgf9`（类 3）。

---

## Implementation Strategy

迭代式：修一个 blocker → `alembic upgrade head` 到下一个 blocker → 记录 → 继续直到 head 成功。每个 fix 独立 commit（或按类别合并 commit）。

**修复模式**：
- 类 1：`bind = op.get_bind()` + `bind.dialect.has_table(bind, name)` / `get_columns` guard（98c68a46add7 是范例）
- 类 2：改 `down_revision` 指向真正创建依赖对象的 migration（验证 merge 点仍一致 + 单 head）
- 类 3：constraint 内联到 `create_table(..., sa.UniqueConstraint(...))` 或 `batch_alter_table`
- 类 4：`with op.batch_alter_table(table) as batch_op: batch_op.alter_column(...)` 或 short-circuit（fresh DB 已是目标类型时跳过）

---

## Verification Contract

- `rm -f /tmp/numina_fresh.db; DATABASE_URL="sqlite:////tmp/numina_fresh.db" uv run alembic -c apps/backend/alembic.ini upgrade head` → 成功
- `uv run alembic -c apps/backend/alembic.ini downgrade base` → 可逆（fresh DB 上）
- `uv run alembic -c apps/backend/alembic.ini heads` → 单 head `6c8a42d83b59`
- `uv run pytest tests/backend/ -q` → 不新增失败（测试用 create_all，不受 migration 改动影响，但验证 import 不破）
- `uv run ruff check` touched migrations → 0 error

---

## Definition of Done

- [ ] fresh SQLite `alembic upgrade head` 成功（base→head）
- [ ] fresh SQLite `alembic downgrade base` 可逆
- [ ] 单 head 保持 `6c8a42d83b59`
- [ ] backend pytest 不新增失败
- [ ] 每个 blocker 记录类别 + 修复方式
- [ ] 无 fake completion

---

## Progress Log

- ✅ `aa10837ae378` 类1（commit 3a2f92a5）— guard 51 drops + short-circuit 50+ alters
- ✅ `c5724f07ecb4` 类1（commit 3a2f92a5）— guard 3 drop_column
- ✅ `g8057i30hfe7` 类2（commit 待提交）— down_revision `f7946h29ged6`→`3ec41c70c529`（后者创建 ai_provider_configs 表，原顺序在 fresh DB 上 add_column 报 no such table）
- ✅ `i0279k52jgf9` 类3（commit 待提交）— `create_unique_constraint('uq_family_skill')` 内联到 create_table（SQLite 不支持 ALTER TABLE ADD CONSTRAINT）
- ⛔ `aa91d6ea730d` 及后续 AI 层 migration：blocked——ai_chat_sessions 等 20 表无 create migration（见 §结构性发现）。guard 无法解决（表真不存在，非 idempotency 问题，需补 create migration）。
- **状态**：fresh-DB base→head 仍不可达（结构性缺失），已存 DB 增量迁移不受影响。建议方案 A（create_all for fresh）或起独立 plan 做方案 B（重建历史）。
