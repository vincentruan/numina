---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
title: "AI 对话分支功能对齐 DeerFlow - Plan"
date: 2026-07-17
status: complete
completion_date: 2026-07-18
origin: docs/plans/2026-07-17-001-feature-ai-chat-branch-deerflow-parity-plan.md
---

# AI 对话分支功能对齐 DeerFlow - Plan

**Product Contract preservation:** unchanged. This pass enriches the existing requirements-only Product Contract with HOW (Implementation Units, Verification Contract, KTDs). No R-ID scope was altered.

**Target repo:** numina (cwd). DeerFlow reference at external path `/Users/vincentruan/geek_space/github/deer-flow-reference` is read-only ground truth; all new code lands in numina.

## Goal Capsule

**Objective.** 让 `/ai/chat` 的「创建分支」与 DeerFlow 行为对齐:分支不仅克隆对话 checkpoint,还克隆该 thread 的沙盒 artifact 文件(报告等),且历史列表能展示分支与父线程的关系并支持父链跳转。

**Product authority.** DeerFlow: `backend/app/gateway/routers/threads.py`(`_copy_branch_user_data` / `_branch_targets_latest_turn` / `_ignore_branch_user_data`,threads.py:147-210、643-705);前端 `message-list.tsx` 的 `onBranchTurn`。

**Open blockers.** 无。

## Background — 现状(已验证)

「分叉」功能在 numina 当前分支已**完整实现并提交**,且现有后端单测通过(`apps/agent/tests/unit/test_branch_endpoint.py`,5 passed)。已验证:

- 前端按钮 → handler → `branchThreadFromTurn`(`frontend/apps/main/src/api/ai-chat.ts`)→ `POST /api/threads/{id}/branches` → 跳转新 thread,链路完整;`AssistantMessage.vue` CopyButton 右侧已有分支按钮。
- 后端 `branch_thread`(`server/apps/agent/routers/threads.py`)克隆 LangGraph checkpoint、写 session 行、保留 `family_id`、标题加「分支:」前缀;`source="branch"` 已写入 session 行。
- message id 同源:历史加载走 `serialize_channel_values_for_api` → `BaseMessage.model_dump()`(含 `id`),分支时 `_find_branch_checkpoint` 能匹配,不会误 409。
- artifact 落在 thread 级沙盒目录 `{DATA_ROOT}/workspaces/{family_id}/sandboxes/{thread_id}/{workspace,uploads,outputs}`(`server/packages/core/path_manager.py:219`、`server/apps/agent/services/runtime/sandbox_provider.py:90`),**未被分支克隆** → 分支里报告链接失效。

**已验证的两个缺口:**
- **B:** 分支只克隆 checkpoint,未克隆沙盒 artifact 目录。
- **A:** `search_threads`(threads.py:282)返回的 metadata 只有 `title/original_title/is_pinned`(**`source` 在 session 行经 `_session_to_dict` 透出,不在响应 metadata dict**),**无父线程标识**;`branch_parent_thread_id` 只存在 checkpoint metadata 里,session 行没有对应列 → 历史页无法展示父子关系或跳转父线程。

## Key Technical Decisions

**KTD-1. 分支克隆 artifact 采用 DeerFlow 的「仅最新一轮克隆」策略(session-settled: user-directed — chosen over 全量克隆历史轮 / artifact 内容内嵌进 checkpoint: 用户明确要求照搬 DeerFlow 方案,且 numina 已有对齐的 path_manager/sandbox_provider,复用成本最低).**
对齐 DeerFlow `_branch_targets_latest_turn`:只有从最新可见轮分支才复制沙盒目录;历史轮分支跳过克隆(`workspace_clone_mode="skipped_historical_turn"`),避免把后续轮的文件泄漏到分支。克隆失败 best-effort,记 warning,不阻断分支创建。`ThreadBranchResponse` 新增 `workspace_clone_mode` 字段。

**KTD-2. 沙盒路径解析复用 numina 既有 path_manager,不引入新路径约定.**
克隆源/目标用 `path_manager` 的 thread 级沙盒基目录(`{DATA_ROOT}/workspaces/{family_id}/sandboxes/{thread_id}/`),与 `sandbox_provider._build_thread_path_mappings` 一致。文件 IO 经 `asyncio.to_thread` 卸载(对齐 DeerFlow `run_file_io`),避免阻塞事件循环。

**KTD-3. 父子关系持久化:新增 `parent_thread_id` 列到 `ai_chat_sessions`,而非列表期读 checkpoint metadata.**
`branch_parent_thread_id` 当前只存于 checkpoint metadata;列表期逐行回查 checkpoint 不可行(N 次 alist 扫描)。新增 DB 列,在 `branch_thread` 创建 session 行时写入父 thread_id,列表/详情接口透出。`source="branch"` 仍保留作为粗粒度标记。这需要 Alembic 迁移 + 跨层(agent → BackendClient → backend internal router)字段贯通。

**安全 (same-family 保证):** `parent_thread_id` 不加外键(父线程可能跨 family 查询由应用层校验)。写入路径 `branch_thread` 已在 family 上下文内(`verify_family_token` + `x_family_id` 校验过当前 family),父 thread_id 来自当前 thread 的 checkpoint,天然同 family;读取/跳转路径依赖现有 `get_thread` 的 family 门控,拒绝跨 family 引用。此为处理原则,不额外加 DB 约束。

**KTD-4. 历史 UI 仅做线性父子标识,不做分支树(session-settled: user-directed — chosen over 分支树可视化: 超出「引入分叉」范围,见 Out of Scope).**
分支条目显示标识 + 「来自父线程」入口跳转父 thread_id;父线程标题批量解析(列表期按出现的 parent_thread_id 一次性查询,避免 N+1)。

## Implementation Units

### U1. 后端:移植 DeerFlow 沙盒克隆 helper

**Goal.** 在 `branch_thread` 端点里新增「按最新一轮克隆沙盒 artifact 目录」逻辑,对齐 DeerFlow `_copy_branch_user_data` / `_branch_targets_latest_turn` / `_ignore_branch_user_data`。

**Requirements.** B1(缺口 B 后端)。

**Dependencies.** 无。

**Files.**
- `server/apps/agent/routers/threads.py` — 新增三个 helper + 接入 `branch_thread`
- `server/apps/agent/tests/unit/test_branch_endpoint.py` — 扩展用例

**Approach.**
- 新增 `_branch_targets_latest_turn(checkpointer, thread_id, target_message_ids) -> bool`:复用 `_find_branch_checkpoint` 已有的 `alist` 扫描思路,取最新含消息的 checkpoint,判断目标轮是否为其尾轮。失败 fail-closed(视为历史轮)。
- 新增 `_ignore_branch_user_data(directory, names) -> set[str]`:忽略 `.upload-*.part` 临时文件与符号链接(对齐 DeerFlow threads.py:176-185)。
- 新增 `_copy_branch_sandbox_sync(family_id, source_thread_id, target_thread_id) -> str`:解析源/目标沙盒**基目录** `Path(settings.AGENT_DATA_DIR)/int(family_id)/"sandboxes"/{thread_id}`(对齐 `sandbox_provider.py:94` 的 `Path(settings.AGENT_DATA_DIR) / family_id / "sandboxes" / thread_id`;注意 `path_manager.thread_report_dir` 只返回 `outputs` 子目录,不能用作基目录),`copytree` 覆盖 `workspace`/`uploads`/`outputs` 全部子目录(对齐 DeerFlow 全量)。源基目录不存在返回 `"not_found"`,否则 `shutil.copytree(..., ignore=_ignore_branch_user_data, dirs_exist_ok=True)` 返回 `"current_thread_best_effort"`,异常返回 `"failed"`。
- 新增 `_copy_branch_user_data(family_id, source_thread_id, target_thread_id) -> str`:`await asyncio.to_thread(...)` 包裹同步函数,异常记 warning 返回 `"failed"`。
- 在 `branch_thread` 写完 checkpoint 后(threads.py 现有 step 4 之后、step 5 之前或之后均可,需在 `new_thread_id` 生成后):若 `_branch_targets_latest_turn` 为真则调用 `_copy_branch_user_data`,否则 `workspace_clone_mode="skipped_historical_turn"`。
- `ThreadBranchResponse` 新增 `workspace_clone_mode: str`(默认空串或 `"skipped"`),`branch_thread` 返回时填入。

**Patterns to follow.** DeerFlow `backend/app/gateway/routers/threads.py:147-210`(helper 实现)、threads.py:643-705(接入位置与 `workspace_clone_mode` 取值)。numina 既有 `path_manager.thread_report_dir`(`server/packages/core/path_manager.py:219`)与 `sandbox_provider` 路径约定。

**Test scenarios.**
- Happy path:从最新轮分支 + 源沙盒存在 → checkpoint 复制、`shutil.copytree` 被调用、`workspace_clone_mode=="current_thread_best_effort"`、响应含新字段。
- 全量子目录覆盖:Happy path 下断言源 `workspace/`、`uploads/`、`outputs/` 三个子目录均被复制到目标(不仅 outputs)。
- 最新轮分支 + 源沙盒目录不存在 → `workspace_clone_mode=="not_found"`,分支仍成功(不抛错)。
- 历史轮分支(目标轮非最新)→ `workspace_clone_mode=="skipped_historical_turn"`,不调用 copytree。
- 克隆抛异常(模拟 copytree 失败)→ best-effort:分支仍创建成功,`workspace_clone_mode=="failed"`,记 warning。
- `_ignore_branch_user_data` 过滤:`.upload-xxx.part` 文件与符号链接不被复制。
- 并发/竞争:copytree 与源删除竞争时不使端点崩溃(best-effort)。
- 现有 5 个用例继续通过(回归)。

**Verification.** `cd server && uv run pytest apps/agent/tests/unit/test_branch_endpoint.py -v` 全绿(≥5 旧 + 新增);`uv run ruff check apps/agent/routers/threads.py`;`uv run mypy apps/agent/routers/threads.py`。

**Execution note.** 先给「最新轮克隆成功」「历史轮跳过」「克隆失败 best-effort」三个场景写/改用例再接逻辑,锁定契约。

---

### U2. 后端:贯通 `parent_thread_id` 字段(迁移 + 模型 + 跨层)

**Goal.** 在 `ai_chat_sessions` 新增 `parent_thread_id` 列,贯通 agent → BackendClient → backend internal router,使分支创建时父 thread_id 落库、列表/详情接口可读。

**Requirements.** B2(缺口 A 后端侧)。推进 KTD-3。

**Dependencies.** U1(同一 `branch_thread` 端点改动,但字段贯通可独立先行)。

**Files.**
- `server/apps/backend/app/models/ai_chat_session.py` — 新增 `parent_thread_id` 列
- `server/apps/backend/alembic/versions/<new>_add_parent_thread_id_to_ai_chat_sessions.py` — 迁移
- `server/apps/backend/app/routers/ai_internal.py` — `SessionUpsertRequest` 增字段、`internal_upsert_session` 写入、`_session_to_dict` 透出
- `server/apps/agent/core/backend_client.py` — `upsert_session`(及底层 `_upsert_session`)增 `parent_thread_id` 参数透传
- `server/apps/agent/services/session_store.py` — `AiSessionRepository.upsert` 增 `parent_thread_id` 参数
- `server/apps/agent/routers/threads.py` — `branch_thread` 调 `repo.upsert(..., parent_thread_id=thread_id)`
- 相关后端单测/agent 单测

**Approach.**
- 迁移:`op.add_column("ai_chat_sessions", sa.Column("parent_thread_id", sa.String(64), nullable=True))`;downgrade drop。命名遵循现有 kebab/雪花风格(参考 `y3692z75arq0_add_source_to_ai_chat_sessions.py`)。
- 模型:`parent_thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)`(thread_id 是 UUID 字符串,不用 BigInteger;不加外键,父线程可能跨 family 查询由应用层校验)。
- `SessionUpsertRequest` 增 `parent_thread_id: str | None = None`;`internal_upsert_session` 在新建分支行时写入。
- `_session_to_dict` 增 `"parent_thread_id": s.parent_thread_id`。
- BackendClient `upsert_session` 增 `parent_thread_id` 形参并放入 payload。
- `AiSessionRepository.upsert` 透传;`branch_thread` 现有 `repo.upsert(..., source="branch")` 处加 `parent_thread_id=thread_id`。

**Patterns to follow.** `source` 字段的贯通链路(`y3692z75arq0` 迁移 → model → `SessionUpsertRequest`/`_session_to_dict` → BackendClient → repo)是 1:1 模板。

**Test scenarios.**
- 迁移 upgrade/downgrade 在干净库与已有数据库上均成功(`alembic upgrade head` / `downgrade -1`)。
- `internal_upsert_session` 带 `parent_thread_id` 创建分支行 → 行 `parent_thread_id` 落库;不带时为 None。
- `_session_to_dict` 输出含 `parent_thread_id` 键。
- agent 侧 `branch_thread` 后,`get_session(new_thread_id)["parent_thread_id"] == thread_id`。
- 现有 `test_branch_endpoint` 用例更新以断言 upsert 调用带 `parent_thread_id`(mock 断言)。

**Verification.** `cd server && uv run alembic -c apps/backend/alembic.ini upgrade head` 成功;`cd server && uv run pytest apps/backend/tests/ apps/agent/tests/unit/test_branch_endpoint.py -v`;`uv run ruff check`;`uv run mypy` 相关模块。注意 alembic 用 `~/.numina` DB(见模块文档),非项目 `.numina`。

**Execution note.** 迁移先于接口贯通;迁移用 `alembic revision --autogenerate -m "add parent_thread_id to ai_chat_sessions"` 生成后核对只含目标列。

---

### U3. 后端:列表/详情接口透出分支元数据

**Goal.** `search_threads` 与 `get_thread` 返回的 `metadata` 含 `is_branch`/`parent_thread_id`(snake_case,与 `is_pinned` 一致;`numina_branch`/`branch_parent_thread_id` 仅供 checkpoint 内部键),供前端判断分支与跳转。

**Requirements.** B2。推进 KTD-3、KTD-4。

**Dependencies.** U2(需 `parent_thread_id` 列与 `_session_to_dict` 透出)。

**Files.**
- `server/apps/agent/routers/threads.py` — `search_threads`(threads.py:282)与 `get_thread`(threads.py:339)的 metadata 构造

**Approach.**
- `search_threads` 的 `ThreadResponse.metadata` 增加:`"is_branch": r.get("source") == "branch"`、`"parent_thread_id": r.get("parent_thread_id")`。
- `get_thread` 同样从 `repo.get_session` 返回的 source/parent_thread_id 透出上述字段。
- 命名:metadata 用 `is_branch` / `parent_thread_id`(snake_case,与现有 `is_pinned` 一致);checkpoint 内部仍用 `_BRANCH_METADATA_KEY="numina_branch"` 等键,两者不混用。

**Patterns to follow.** 现有 metadata 构造块(threads.py:297-312)。

**Test scenarios.**
- 分支线程在 `search_threads` 结果中 `metadata.is_branch==True`、`parent_thread_id==父id`。
- 普通线程 `is_branch==False`、`parent_thread_id` 为 None。
- `get_thread` 对分支线程同样透出。
- `test_threads_router.py` 增对应断言。

**Verification.** `cd server && uv run pytest apps/agent/tests/unit/test_threads_router.py apps/agent/tests/unit/test_branch_endpoint.py -v`;ruff/mypy。

---

### U4. 前端:历史页展示分支关系与父链跳转

**Goal.** `ChatHistoryPage.vue` 分支条目显示分支标识并能跳转父线程。

**Requirements.** B3(缺口 A 前端侧)。推进 KTD-4。

**Dependencies.** U3(列表接口透出 `is_branch`/`parent_thread_id`)。

**Files.**
- `frontend/apps/main/src/pages/ChatHistoryPage.vue` — 分支标识 + 父链跳转
- `frontend/apps/main/src/api/ai-chat.ts` — 若 session 类型需加 `is_branch`/`parent_thread_id` 字段
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`、`frontend/apps/main/src/i18n/locales/en-US.ts` — 新文案键

**Approach.**
- 前端 session 类型(若存在,如 `ChatSession`/`ThreadSummary`)增 `is_branch?: boolean`、`parent_thread_id?: string`。
- 历史条目:当 `session.is_branch` 为真,显示分支标识(图标 + 标签)与「来自父线程」入口;点击入口 → `router.push({ name: 'AIChat', query: { thread_id: session.parent_thread_id } })`。
- 父线程标题:KTD-4 决定批量解析。实现细节(列表期一次性查询所有出现过的 `parent_thread_id` 的标题 vs 延迟加载)留 U4 实现时定;倾向列表期按出现 parent_thread_id 去重后一次性取标题(需 U3 列表结果或额外查询支持)。若一次性查询无现成接口,回退为「跳转入口不显示父标题,仅显示「来自父会话」」。
- 文案键遵循 `aiChat.*` 命名(如 `branchFromParent`、`branchBadge`、`branchParentDeleted`),不硬编码中文。
- **父线程已删降级态**:跳转后若 `get_thread` 返回 404(父线程已删),父链降级为不可点击 badge + 提示文案(`branchParentDeleted`);不在历史页直接探测,依赖目标路由的 404 兜底回显。
- **无障碍规范**:分支徽章用 `role="img"` + `aria-label`(分支标识语义);父链入口为语义化 `<a>`/`<button>`(可 Tab 聚焦 + Enter/Space 触发),`aria-label` 描述跳转目标(如「跳转到父线程」);降级态 badge 同样有 `aria-label`。

**Patterns to follow.** 现有 `is_pinned` 指示器与 `originalTitleHint` 的渲染/跳转模式(`ChatHistoryPage.vue:296`、`:287`)。

**Test scenarios.**
- 分支条目渲染分支标识;普通条目不渲染。
- 点击父链入口跳转到父 `thread_id` 的 AIChat 路由。
- i18n:zh/en 均有新键且无硬编码字符串。
- 父标题缺失时降级显示不报错。
- 父线程已删(跳转目标 404)时回显「父线程已删」提示而非裸 404。

**Verification.** `cd frontend/apps/main && pnpm typecheck`;`pnpm test:run`(ChatHistoryPage 相关);`pnpm lint`。

**Execution note.** 父标题批量解析的可行性依赖 U3 是否能一次返回所需标题;若不可行,先落地「无标题的跳转入口」再迭代。

---

### U5. 前端:`workspace_clone_mode` 反馈(可选打磨)

**Goal.** 分支创建后,当 `workspace_clone_mode` 非 `current_thread_best_effort` 时,给用户一个轻量提示(历史轮分支文件未复制)。

**Requirements.** 无硬性 requirement;对应 Product Contract 的 Outstanding Question。

**Dependencies.** U1(响应含 `workspace_clone_mode`)。

**Files.**
- `frontend/apps/main/src/components/ai/AIChatBox.vue`(`handleBranch` 处)
- `frontend/apps/main/src/api/ai-chat.ts`(`ThreadBranchResponse` 类型)
- i18n 两份

**Approach.** `ThreadBranchResponse` 类型增 `workspace_clone_mode: string`;`handleBranch` 成功 toast 后,若 mode 为 `skipped_historical_turn`/`not_found`/`failed` 则追加提示文案(走 `aiChat.branchClone.*` i18n 键,严重度 = warning — 非成功但非阻断)。mode→文案映射:
- `skipped_historical_turn` → 「从历史轮分支,部分文件未复制」
- `not_found` → 「源文件未找到,分支已创建」
- `failed` → 「文件复制失败,分支已创建」
是否做此项由实现时定(默认做,成本低)。

**Test scenarios.** 各 mode 下提示文案正确;i18n 齐;typecheck 过。

**Verification.** `pnpm typecheck`。

## High-Level Technical Design

分支创建时序(新增部分以 `+` 标注):

```
前端 handleBranch
  → POST /api/threads/{id}/branches {message_id, message_ids}
后端 branch_thread:
  1. 校验 source session + family_id
  2. _find_branch_checkpoint(匹配 message_id)
  3. deepcopy checkpoint → 新 thread_id,写 checkpointer.aput
  4. repo.upsert(source="branch", parent_thread_id=父id)   # U2 新增字段
+ 5. _branch_targets_latest_turn?                            # U1
+      是 → _copy_branch_user_data(克隆沙盒目录) → mode      # U1
+      否 → mode = "skipped_historical_turn"                 # U1
  6. 返回 ThreadBranchResponse{..., workspace_clone_mode}    # U1
前端 → router.push(新 thread_id)
```

数据流(父子关系):`branch_thread` 写 `parent_thread_id`(DB 列)→ `search_threads`/`get_thread` 透出 `is_branch`/`parent_thread_id`(metadata)→ `ChatHistoryPage` 渲染 + 跳转。

## Scope Boundaries

**In scope:** B1(沙盒克隆)、B2(分支元数据透出)、B3(历史 UI)、U5 可选打磨。

**Out of scope / Non-goals:**
- 分支树/版本图可视化(KTD-4)。
- fork DB 资产快照(agent 不写资产)。
- artifact 内容内嵌进 checkpoint(方案 3,已否决)。
- 重新设计分支交互(现有已对齐 DeerFlow)。

**Deferred to Follow-Up Work:**
- 父线程标题批量解析接口若需新建独立端点(U4 内联优先,失败再独立)。
- 分支计数/分支列表(父线程视角看其所有分支)——非本计划需求。

## Risks & Dependencies

- **沙盒目录大小**:多次报告累积可能较大,`shutil.copytree` 必须经 `asyncio.to_thread` 卸载(KTD-2),否则阻塞事件循环。已有 best-effort + warning 兜底。
- **并发竞争**:copytree 与源 thread 删除/再次分支竞争 → best-effort,沿用 DeerFlow 行为。
- **Alembic DB 路径**:迁移作用于 `~/.numina` DB,非项目 `.numina`(见模块 CLAUDE.md);实现时确认环境。
- **父标题解析**:U4 父标题批量取值若无可复用接口,降级为无标题跳转入口(已在 Approach 记录)。
- **跨层字段贯通遗漏**:`parent_thread_id` 需经 model→migration→internal router→BackendClient→repo→branch_thread 六处一致;漏一处则字段 silently 为 None。U2 用例以 mock 断言贯通。

## Open Questions

- **[ce-doc-review defer] U4 父标题解析策略**:展示「来自: {parent_title}」需要解析父线程标题。两选项待实现时定:(a) 复用历史页已加载 session 列表做内存交叉连接(`parent_thread_id` → 列表内 O(1) 查父标题,无需新端点);(b) 降级为只显示分支 badge 不显示父标题。倾向 (a);若列表非全量加载则回退 (b)。reviewer 标记为范围/设计权衡,非事实错误。
- 克隆范围是否含 `uploads/` 目录?**已解决**:U1 改为基目录全量 `copytree`(覆盖 `workspace`/`uploads`/`outputs`),uploads 随之被克隆,跟随 DeerFlow 全量。U1 测试补一条断言 `uploads/` 文件被克隆。
- U5 是否一定做?倾向做(成本低);可在 U4 后由实现者决定。
- 历史 UI 分支标识:仅标签 vs 带「来自: {parent_title}」文案?见 U4 父标题解析降级策略。

## Verification Contract

- `cd server && uv run pytest apps/agent/tests/unit/test_branch_endpoint.py apps/agent/tests/unit/test_threads_router.py -v` 全绿。
- `cd server && uv run alembic -c apps/backend/alembic.ini upgrade head` 成功。
- `cd server && uv run ruff check apps/agent/ apps/backend/` 与 `uv run mypy` 通过(改动范围)。
- `cd frontend/apps/main && pnpm typecheck && pnpm test:run && pnpm lint` 通过。
- 手动验收:从生成了报告的最新 AI 轮分支 → 新 thread 报告链接可打开;从历史轮分支 → 创建成功且提示文件未复制;历史页分支条目可见标识并能跳转父线程。

## Definition of Done

- U1–U4 全部完成且各自 Verification 通过;U5 做或显式记为 deferred。
- 现有 5 个分支单测 + 新增用例全绿;前端 typecheck/test/lint 全绿。
- 手动验收三条(最新轮克隆、历史轮跳过、历史页父子跳转)通过。
- Out of Scope 项未被偷偷纳入;ruff/mypy/alembic 无回归。

## Sources & Research

- DeerFlow 参考:`/Users/vincentruan/geek_space/github/deer-flow-reference/backend/app/gateway/routers/threads.py`(`_copy_branch_user_data`/`_branch_targets_latest_turn`/`_ignore_branch_user_data`/`ThreadBranchRequest`/`workspace_clone_mode`)。
- numina 现状:`server/apps/agent/routers/threads.py`、`server/packages/core/path_manager.py`、`server/apps/agent/services/runtime/sandbox_provider.py`、`server/apps/backend/app/models/ai_chat_session.py`、`server/apps/backend/app/routers/ai_internal.py`、`server/apps/agent/core/backend_client.py`、`server/apps/agent/services/session_store.py`、`frontend/apps/main/src/pages/ChatHistoryPage.vue`、`frontend/apps/main/src/components/ai/AIChatBox.vue`、`frontend/apps/main/src/api/ai-chat.ts`。
