# 方案 B — 重建缺失 migration 历史(fresh-DB base→head)

> **状态**：complete — fresh-DB `alembic upgrade head` 成功（2026-07-22）
> **日期**：2026-07-22
> **父文档**：[alembic fresh-DB 专项](./2026-07-22-alembic-fresh-db-idempotency-plan.md) §结构性发现
> **目标**：为 20 个"存在于模型但无 alembic create migration"的表补建 create_table,使 fresh-DB `alembic upgrade head` 可行

---

## Goal Capsule

**一句话**：插入一个 bootstrap migration(紧随 base `e3cba86157fd` 之后),用 `has_table` guard 创建 20 个缺失表,使 fresh-DB base→head 跑通。

**为什么**：20 表(ai_chat_sessions/ai_skills/ai_providers/cached_files/currencies 等)只存在于 `Base.metadata.create_all()`,alembic upgrade 链无 creator。后续 migration(如 aa91d6ea730d 的 ai_chat_sessions batch_alter)引用它们时表不存在→失败。guard 无法修(表真缺),必须补 create。

**完成标准**：fresh SQLite `alembic upgrade head` 成功 + `alembic downgrade base` 可逆 + backend pytest 不新增失败 + 单 head 保持。

---

## 核心设计

### 插入点
新 migration `bootstrap_missing_tables`,down_revision=`e3cba86157fd`(base)。改 `98c68a46add7.down_revision` 从 `e3cba86157fd` → `bootstrap_missing_tables`。链顺序:
`e3cba86157fd` → **bootstrap_missing_tables** → `98c68a46add7` → ... → head

### 生成方式(零偏差)
不手写列定义(易错)。用脚本读 `Base.metadata`(env.py 已 import 全部 model),对 20 个 Table 对象用 Alembic `autogenerate.render` 渲染 `op.create_table(...)` 代码,粘进新 migration。

### Guard(已存 DB 安全)
每个 create_table 包 `if not bind.dialect.has_table(bind, '<table>'):`。已存 DB(prod/dev,表已存在)→ no-op,不影响。

### 20 个缺失表(模型文件已定位)
activities, ai_chat_messages, ai_chat_sessions, ai_mcp_servers, ai_providers, ai_reports, ai_skills, cached_files, category_financial_defaults, child_milestones, chore_instances, chore_templates, coin_transactions, currencies, exchange_rates, file_remote_locations, revoked_tokens, security_audit_logs, storage_backends, sync_events。

**FK 顺序**：部分表有 FK(如 ai_chat_sessions→ai_agents)。bootstrap 须按依赖序创建,或先建无 FK 的、再建有 FK 的。ai_agents 由后续 migration 创建→bootstrap 的 ai_chat_sessions FK 到 ai_agents 会失败(fresh DB 上 ai_agents 还不存在)。**对策**：bootstrap 内 create_table 用 `sqlite_with_foreign_keys=False` 或 FK 用 `use_alter`,或把 ai_agents 也纳入 bootstrap(检查 ai_agents 是否也缺 creator)。

---

## 风险与对策
- **FK 依赖**：ai_chat_sessions→ai_agents。若 ai_agents 也缺 creator→一并纳入 bootstrap。若 ai_agents 由后续 migration 创建→bootstrap 的 ai_chat_sessions FK 须延迟(use_alter)或 bootstrap 放在 ai_agents creator 之后。
- **索引/约束**：autogenerate render 含 index/unique constraint,SQLite 需内联或 batch(类 3 已知)。
- **列类型**：模型用 BigInteger(Snowflake),与 fresh DB 期望一致。

---

## Verification
- `rm -f /tmp/fresh.db; DATABASE_URL=sqlite:////tmp/fresh.db alembic upgrade head` → 成功
- `alembic downgrade base` → 可逆
- `alembic heads` → 单 `6c8a42d83b59`
- `uv run pytest tests/backend/ -q` → 不新增失败

## DoD
- [x] bootstrap_missing_tables migration 生成(17 表 create_table + has_table guard) — `b00t5trap0001`，down_revision `e3cba86157fd`
- [x] 98c68a46add7.down_revision 改指 `b00t5trap0001`
- [x] fresh-DB upgrade head 成功（base `e3cba86157fd` → head `6c8a42d83b59`，59 表全建）
- [x] backend pytest 不新增失败（test_user_settings + test_dashboard + test_auth = 55 passed）
- [x] 单 head 保持 `6c8a42d83b59`
- [x] ruff 0 error（touched migrations）
- [ ] fresh-DB downgrade base 可逆 — **未达成（已知限制）**：downgrade 路径的 drop_index/drop_column 未全 guard（如 b9c7d2e4f6a8 downgrade drop ix_ai_reports_family_capability_status，fresh-DB 上 index 被 upgrade guard 跳过未建）。fresh 部署不会 downgrade-to-base，此限制可接受；若需可逆，另起 downgrade-guard 专项。

## 实施汇总（commit 待提交）

修复的 migration（20 改 + 1 新增）：

| Migration | 类别 | 修复 |
|-----------|------|------|
| `b00t5trap0001` (NEW) | bootstrap | 从 Base.metadata 生成 17 表 create_table + has_table guard，down_revision=e3cba86157fd |
| `98c68a46add7` | 链接入 | down_revision e3cba86157fd→b00t5trap0001 |
| `aa10837ae378` | idempotency | short-circuit 提前到 drops 之前（already_snowflake 时跳过 drops+alters，避免删 bootstrap 建的表） |
| `aa91d6ea730d` | guard | jsonl_path 不存在时跳过（fresh-DB 无 legacy 列） |
| `0b0a9def92f5` | guard | is_pinned has_column guard |
| `538588b30845` | guard | markdown_file_path has_column guard |
| `a4c7e9d2f1b8` | guard | parent_thread_id has_column guard |
| `b9c7d2e4f6a8` | guard | capability has_column guard（add_column + create_index） |
| `m4613o96nki3` | guard | assigned_by_user_id/claimed_at has_column guard |
| `w7392x85yzq1` | guard | original_title has_column guard |
| `y3692z75arq0` | guard | source has_column guard |
| `z4783a86brs1` | guard | agent_id has_column guard（FK 省略，fresh-DB 列已存在） |
| `r9047s21tlm7` | SQLite compat | alter_column 包 batch_alter_table + nullable guard |
| `w0159x32vnm9` | SQLite compat | create_unique_constraint 内联到 create_table |
| `t1269u43vno9` | SQLite compat | add_column+FK 包 batch + naming_convention + has_column guard |
| `x2581y64zqr9` | SQLite compat + rename | rename guard（has_table）、CheckConstraint `~` regex + partial index 仅 Postgres、seed `::jsonb` 仅 Postgres |
| `a53453cf574b` | guard + SQLite | agent_type 已存在时跳过整个 column swap、drop_index/create_index guard、system-agent seed 仅 Postgres |
| `c7583a86bst1` | SQLite compat | add_column+FK 包 batch + naming_convention、UPDATE...FROM JOIN 分 SQLite/Postgres 语法 |
| `7e657997df69` | rename + guard | mcp_type add_column 目标适配 rename（ai_mcp_servers/family_mcp_servers）+ has_column guard |
| `a5894b97cs2` | guard | drop_column capability 包 batch + has_column guard |
| `e4e455e0567e` | guard | drop_column JSONL 列包 batch + 仅 drop 存在的列 + naming_convention |

**4 类问题修复模式**：
1. **idempotency guard**：`bind.dialect.has_table` / `get_columns` / `get_indexes` 检查表/列/索引存在，fresh-DB 跳过
2. **SQLite 兼容**：`create_unique_constraint` 内联 create_table；`add_column`+FK / `drop_column` / `alter_column` 包 `batch_alter_table`（+ naming_convention 解决未命名约束反射）
3. **依赖顺序**：g8057i30hfe7 down_revision 修正（已在 commit af157396）
4. **Postgres-only**：`::jsonb` cast、`~` regex CheckConstraint、partial index (`postgresql_where`)、`UPDATE...FROM` JOIN — 仅 Postgres 执行，SQLite 跳过/替代语法
