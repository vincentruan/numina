# 技术债务审计报告

**日期**: 2026-06-06  
**分支**: feat/deerflow-agent  
**审计范围**: 全仓库（server/, frontend/, docker/nginx/scripts）

---

## 摘要

| 严重度 | 数量 | 预估总工时 |
|--------|------|-----------|
| CRITICAL | 3 | ~17h |
| HIGH | 22 | ~95h |
| MEDIUM | 18 | ~50h |
| LOW | 7 | ~8h |
| **合计** | **50** | **~170h** |

**最高风险项**:
1. Docker Compose 中 SECRET_KEY 弱默认值 — 生产可被攻击
2. `python-jose` 已停止维护 — 安全隐患
3. AIChatPage.vue 3046 行 God Component — 开发效率瓶颈
4. 生产 nginx 缺少 `/api/v1/internal` 拦截 — 内部 API 暴露

**最高 ROI 速修项（均 ≤2h）**:
- WebSocket 内存泄漏修复 (0.5h)
- DataStatsPage i18n 补全 (1h)
- deerflow-harness git 引用 pin 到 commit (0.5h)
- logging.getLogger → get_logger 统一 (1h)
- Magic agent ID 常量统一 (2h)

---

## 一、CRITICAL — 必须立即修复

### TD-001 Docker Compose SECRET_KEY 弱默认值
| 属性 | 值 |
|------|---|
| 类别 | 安全 / 基础设施 |
| 文件 | `docker-compose.yml:16`, `docker-compose.dev.yml:17` |
| 工时 | 1h |

**问题**: `SECRET_KEY=${SECRET_KEY:-change-me-in-production-use-a-long-random-string}`。若 `.env` 缺失，应用以已知默认值启动，所有 JWT 可被伪造。`STORAGE_ENCRYPTION_KEY` 和 `AI_ENCRYPTION_KEY` 回退为空字符串，等效于无加密。

**修复**: 删除所有 fallback default。在 pydantic-settings 层面对 SECRET_KEY 做启动校验（值为空或含 "change-me" 时 hard-fail）。

---

### TD-002 AIChatPage.vue — 3046 行 God Component
| 属性 | 值 |
|------|---|
| 类别 | 前端架构 |
| 文件 | `frontend/apps/main/src/pages/AIChatPage.vue` |
| 工时 | 12–16h |

**问题**: 单个 `<script setup>` 包含 40+ 顶层函数，覆盖：会话管理、消息渲染、Markdown 处理、SSE 流生命周期、历史侧边栏、文件上传、滚动管理、Artifact 处理。任何改动影响面不可预测。

**修复**: 拆分为：
- `useSessionManager` composable（会话 CRUD、分组、分页）
- `useChatStream` composable（SSE 生命周期、abort）
- `ChatHistorySidebar.vue` 组件
- `ChatMessageList.vue` 组件

---

### TD-003 DataStatsPage.vue — 100% 硬编码中文
| 属性 | 值 |
|------|---|
| 类别 | i18n |
| 文件 | `frontend/apps/main/src/pages/DataStatsPage.vue` |
| 工时 | 1h |

**问题**: 页面从未导入 `useI18n`。9 个用户可见字符串均为原始中文：`"数据统计"`, `"暂无数据"`, `"快速统计"`, `"资产数量"`, `"本月新增资产"`, `"日均成本总计"`, `"总资产"`, `"总负债"`, `"净资产"`。

**修复**: 添加 `useI18n`，在 `zh-CN.ts` / `en-US.ts` 补充 key，替换所有裸字符串为 `t('key')`。

---

## 二、HIGH — 本迭代应解决

### TD-004 python-jose 已停止维护（2022 年最后发布）
| 属性 | 值 |
|------|---|
| 类别 | 后端依赖 / 安全 |
| 文件 | `server/pyproject.toml`, `auth/deps.py`, `services/auth.py` (11 处调用) |
| 工时 | 3–4h |

**问题**: `python-jose[cryptography]>=3.3.0` 无上界，项目已无人维护且存在已知 CVE。

**修复**: 迁移到 `PyJWT>=2.8.0`。API 签名差异小，约 11 处调用需适配。

---

### TD-005 生产 nginx 缺少 /api/v1/internal 拦截
| 属性 | 值 |
|------|---|
| 类别 | 安全 / 基础设施 |
| 文件 | `nginx.production.conf` |
| 工时 | 15min |

**问题**: `nginx.conf` 用 `return 403` 拦截 `/api/v1/internal`，但 `nginx.production.conf` 缺少此规则。生产部署时内部 agent-to-backend 端点公开暴露。

**修复**: 添加 `location ^~ /api/v1/internal { return 403; }` 到 `nginx.production.conf`。

---

### TD-006 生产 nginx 缺少 HSTS / SPA 无 CSP
| 属性 | 值 |
|------|---|
| 类别 | 安全 / 基础设施 |
| 文件 | `nginx.production.conf` |
| 工时 | 1.5h |

**问题**: 
- 无 `Strict-Transport-Security` header（即使 Cloudflare 终端 HTTPS，origin 仍应设置）
- SPA 前端 (`location /`) 无 Content-Security-Policy，仅 `/api/` 有 CSP

**修复**: 添加 HSTS header；为 SPA 添加适当 CSP（`default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;`）。

---

### TD-007 Docker 容器无资源限制
| 属性 | 值 |
|------|---|
| 类别 | 基础设施 |
| 文件 | `docker-compose.yml`, `docker-compose.production.yml` |
| 工时 | 1h |

**问题**: 所有服务未设置 `deploy.resources.limits`。AI agent 的 LLM 循环或失控 scheduler 可 OOM 整台宿主机。

**修复**: 为每个服务添加内存/CPU 限制（backend: 512M, agent: 2G, worker: 512M, nginx: 128M）。

---

### TD-008 路由层直接操作数据库（层违规）
| 属性 | 值 |
|------|---|
| 类别 | 后端架构 |
| 文件 | `routers/blind_box.py`, `routers/chores.py`, `routers/export.py`, `routers/ai_time_machine.py`, `routers/treasures.py` |
| 工时 | 8–12h |

**问题**: 路由处理函数直接调用 `db.query()`, `db.add()`, `db.commit()`，无 service 层。`blind_box.py` 最严重。

**修复**: 提取 service 函数。路由只负责 HTTP 关注点（解析、鉴权、响应构造），委托给 service。

---

### TD-009 God Files: ai_internal.py (899行), ai_skills.py (986行), agent_dispatch.py (856行)
| 属性 | 值 |
|------|---|
| 类别 | 后端架构 |
| 文件 | `routers/ai_internal.py`, `routers/ai_skills.py`, `services/agent_dispatch.py` |
| 工时 | 12–16h |

**问题**: `ai_internal.py` 包含 15+ 端点（overview、allocation、trend、low-usage、daily-cost、AI config、circuit breaker）。`ai_skills.py` 混合 CRUD、YAML 解析、GitHub 集成。

**修复**: 拆分 `ai_internal.py` → `ai_internal_data.py` + `ai_internal_circuit.py`。从 `ai_skills.py` 提取 `SkillManagementService`。拆分 `agent_dispatch.py` → dispatch + streaming adapters。

---

### TD-010 bare `except Exception` 吞掉错误（67 处）
| 属性 | 值 |
|------|---|
| 类别 | 后端反模式 |
| 文件 | 30 个文件，67 处（`services/asset.py` 11处, `services/auth.py` 8处, `agent_dispatch.py` 5处） |
| 工时 | 6–8h |

**问题**: 大量 `except Exception` 要么仅 WARNING 日志要么完全静默。在 streaming 路径中导致客户端收到不完整结果但无错误信号。

**修复**: 替换为具体异常类型。必须广泛 catch 的场景至少用 `logger.exception()` 保留堆栈。

---

### TD-011 `time.sleep()` 阻塞 async 事件循环
| 属性 | 值 |
|------|---|
| 类别 | 后端反模式 |
| 文件 | `services/db_migrate.py:202,506`, `reconcile/lock.py:168` |
| 工时 | 2–3h |

**问题**: FastAPI lifespan startup 中调用 `time.sleep(0.5)`。在 SQLite 多进程部署下阻塞整个事件循环数秒。

**修复**: 转换为 `await asyncio.sleep()` 或删除自定义锁机制（见 TD-012）。

---

### TD-012 自研迁移系统与 Alembic 并行
| 属性 | 值 |
|------|---|
| 类别 | 后端架构 |
| 文件 | `services/db_migrate.py` (535 行) |
| 工时 | 6–8h |

**问题**: 同时存在 Alembic 和一个 535 行的自研 `run_schema_migration()`（含分布式锁、table inspection、column diffing）。每次启动都执行，引入启动阻塞和维护负担。

**修复**: 全面切换到 Alembic。容器 entrypoint 运行 `alembic upgrade head`，删除 `db_migrate.py`。

---

### TD-013 10 个 API 模块在 main/child 间复制粘贴
| 属性 | 值 |
|------|---|
| 类别 | 前端重复 |
| 文件 | `apps/main/src/api/coins.ts` vs `apps/child/src/api/coins.ts`（逐字节相同），calendar.ts, webauthn.ts 同理 |
| 工时 | 8h |

**问题**: `coins.ts`, `calendar.ts`, `webauthn.ts` 完全相同。另有 7 个模块（chores, childWishes, milestones, blindBox, challengeGrant, family, treasures）近乎相同。

**修复**: 创建 `frontend/packages/api`（`@numina/api`），遵循 `@numina/auth` / `@numina/math` 先例。App 特有扩展留在各 app 内。

---

### TD-014 BabyPage.vue (1674行) / InsightsTab.vue (1658行)
| 属性 | 值 |
|------|---|
| 类别 | 前端架构 |
| 文件 | `pages/BabyPage.vue`, `components/insights/InsightsTab.vue` |
| 工时 | 8h each |

**问题**: 均混合数据获取、状态、ECharts 配置和展示逻辑于单一文件。

**修复**: BabyPage → `ChildSummaryCard`, `MilestoneTimeline`, `ChoreHistoryPanel`。InsightsTab → 按 chart 类型拆分子组件。

---

### TD-015 LoginPage.vue (1313行) 多步骤流程未拆分
| 属性 | 值 |
|------|---|
| 类别 | 前端架构 |
| 文件 | `pages/LoginPage.vue` |
| 工时 | 6h |

**问题**: Step 0（账号轮播）、Step 1（用户名密码）、Step 2（PIN/WebAuthn）全部内联。

**修复**: 提取 `<AccountCarouselStep>`, `<CredentialsStep>`, `<PinVerifyStep>` 子组件。

---

### TD-016 15+ 文件 CSS 硬编码 hex color — 暗黑模式失效
| 属性 | 值 |
|------|---|
| 类别 | 前端硬编码 |
| 文件 | `AssetDetailPage.vue`, `WishDetailPage.vue`, `AIChatPage.vue`, `AIConfigPage.vue` 等 15+ 文件 |
| 工时 | 6h |

**问题**: scoped CSS 中大量原始 hex 颜色（`#059669`, `#dc2626`, `#f87171` 等）绕过 CSS 变量系统，暗黑模式下对比度无保障。

**修复**: 映射到现有 token set (`--color-primary`, `--text-primary`)。无对应 token 的颜色在 `:root` 和 `[data-theme='dark']` 中补充定义。

---

### TD-017 Magic agent/skill ID 常量散落 10+ 文件
| 属性 | 值 |
|------|---|
| 类别 | 后端硬编码 |
| 文件 | `_ai_events_helper.py`, `agent_dispatch.py`, `bootstrap/agents.py`, `bootstrap/skills.py`, `reconcile/registry.py`, 4 个 migration 文件 |
| 工时 | 2–3h |

**问题**: `100000000000005`, `100000000000006` 等 15 位 magic integer 至少 8 个不同值散落在 10+ 文件，无单一事实来源。

**修复**: 创建 `apps/backend/app/constants/system_agents.py`，定义命名常量，所有引用处导入。

---

### TD-018 每个 AI 路由创建临时 httpx.AsyncClient（无连接池）
| 属性 | 值 |
|------|---|
| 类别 | 后端重复 / 性能 |
| 文件 | 15 个 router 文件 |
| 工时 | 3–4h |

**问题**: 每个 AI proxy 端点 per-request 创建销毁 `httpx.AsyncClient`，放弃连接复用。并发下每请求新建 TCP 连接。

**修复**: 创建共享 `httpx.AsyncClient` singleton，在 lifespan 中初始化和关闭。通过 FastAPI 依赖注入。

---

### TD-019 LoginPage / RegisterPage i18n 不完整
| 属性 | 值 |
|------|---|
| 类别 | i18n |
| 文件 | `LoginPage.vue` (step 1/2), `RegisterPage.vue` |
| 工时 | 1.5h |

**问题**: LoginPage step 0/2 使用 `t()`，但 step 1 的 `label="用户名"`, `placeholder="请输入用户名"` 等硬编码。RegisterPage 全部字段标签硬编码。

**修复**: 在 locale 文件补 key，替换为 `t('key')`。

---

### TD-020 AssetListPage.vue aria-label 硬编码中文
| 属性 | 值 |
|------|---|
| 类别 | i18n / 无障碍 |
| 文件 | `pages/AssetListPage.vue` (14 处) |
| 工时 | 1h |

**问题**: 所有 `aria-label` 为原始中文，切换英文后无障碍标签不变。

**修复**: 移至 i18n `aria` 命名空间。

---

### TD-021 useAIReportWS — WebSocket 泄漏
| 属性 | 值 |
|------|---|
| 类别 | 前端反模式 |
| 文件 | `composables/useAIReportWS.ts` |
| 工时 | 0.5h |

**问题**: composable 未注册 `onUnmounted` cleanup。调用方 `AIHubPage.vue` 也未在 unmount 时 disconnect。导航离开时 WebSocket 保持打开。

**修复**: composable 内添加 `onUnmounted(() => disconnect())`。

---

### TD-022 两个 Axios client 重复拦截器逻辑
| 属性 | 值 |
|------|---|
| 类别 | 前端重复 |
| 文件 | `apps/main/src/api/index.ts` (241行), `apps/child/src/api/index.ts` (47行) |
| 工时 | 4h |

**问题**: 两个 app 独立配置 `baseURL`, `timeout`, `withCredentials`, AI endpoint 超时覆写, 401 重定向逻辑。

**修复**: base http factory 移入 `@numina/auth` 包，main app 在上层添加 refresh/retry 拦截器。

---

### TD-023 Alembic migration 文件名与 revision ID 不匹配
| 属性 | 值 |
|------|---|
| 类别 | 数据库 |
| 文件 | `alembic/versions/s0158t32u999_add_total_approved_count_to_users.py` |
| 工时 | 15min |

**问题**: 文件名含 `s0158t32u999` 但文件内 `revision = 's0158t32umn8'`。不影响 Alembic 链完整性，但搜索和审计困难。

**修复**: 重命名文件以匹配实际 revision ID。

---

### TD-024 DashboardStore 过载（分页职责耦合）
| 属性 | 值 |
|------|---|
| 类别 | 前端架构 |
| 文件 | `stores/dashboard.ts` |
| 工时 | 4h |

**问题**: store 同时拥有 summary/overview 数据和分页资产列表状态（`displayedAssets`, `assetPagesCache`, `assetPageInfo`）。`loadMoreAssets` 已标记 deprecated 但仍导出。

**修复**: 提取 `useAssetListStore`，删除废弃导出。

---

### TD-025 dev compose 中 sed 修改宿主 package.json
| 属性 | 值 |
|------|---|
| 类别 | 基础设施 |
| 文件 | `docker-compose.dev.yml:107-117` |
| 工时 | 2h |

**问题**: dev 前端容器启动命令用 `sed` 修改宿主挂载的 `package.json`（将 `workspace:*` 替换为 `file:` 路径），容器崩溃则宿主文件损坏。

**修复**: 在容器内 temp dir 做修改而非操作宿主文件。

---

## 三、MEDIUM — 下一迭代解决

### TD-026 Rate limiter 在非生产环境完全跳过
| 文件 | `middleware/rate_limit.py:174-177` |
| 工时 | 2h |

Rate limiter 从未在集成测试中测试。修复：dev 环境使用高阈值而非 bypass。

---

### TD-027 httpx timeout 值各路由不一致
| 文件 | 15 个 router 文件 |
| 工时 | 1–2h |

超时值散落为 45/90/300/60/10/30/None。应定义命名常量。`timeout=None` 应替换为有限上界。

---

### TD-028 scheduler_worker 硬编码 retention/threshold
| 文件 | `scheduler_worker/jobs/__init__.py` |
| 工时 | 1h |

`retry_count < 3`, `limit(50)`, `retention_days=90` 为内联字面量。应外化到 Settings。

---

### TD-029 useNetwork composable 重复注册全局监听器
| 文件 | `composables/useNetwork.ts` |
| 工时 | 1h |

`isOnline` 是模块级 ref，但 `addEventListener` 在每个组件 mount 时都注册。应提升到模块作用域一次性注册。

---

### TD-030 SessionLocal() 在路由/streaming helper 中直接调用
| 文件 | `_ai_events_helper.py`, `ai_chat.py`, `mcp_internal.py` |
| 工时 | 2–3h |

绕过 `get_db` 依赖，未来 session middleware 无法覆盖这些路径。

---

### TD-031 nginx unpinned image (`nginx:alpine`)
| 文件 | `docker-compose.yml:109`, `docker-compose.production.yml:106` |
| 工时 | 15min |

应 pin 到 `nginx:1.27-alpine`。

---

### TD-032 frontend-main 无 healthcheck (生产)
| 文件 | `docker-compose.production.yml:87-94` |
| 工时 | 30min |

nginx 依赖 `service_started` 而非 `service_healthy`，可能 502。

---

### TD-033 deploy 脚本 pip install 污染系统 Python
| 文件 | `scripts/deploy-docker.sh:82` |
| 工时 | 1h |

`pip3 install cryptography` 在 venv 外执行。应用 `openssl` 替代或 `--user` 安装。

---

### TD-034 Dual DB: agent 侧 SQLite + backend Postgres
| 文件 | `apps/agent/app/main.py` |
| 工时 | 10–14h |

会话元数据写入两处，backend 失败时 orphaned 本地日志。应统一走 backend API。

---

### TD-035 `.env` 弱默认 DB 密码
| 文件 | `scripts/deploy-docker.sh:209-215` |
| 工时 | 30min |

`MYSQL_PASSWORD=numinapass` 字面量。应生成随机密码。

---

### TD-036 Rate limiter 状态跨测试未重置
| 文件 | `middleware/rate_limit.py:228-229` |
| 工时 | 1h |

class-level dict 在 test cases 间共享。

---

### TD-037 SQLite 数据使用 bind mount 而非 named volume
| 文件 | `docker-compose.production.yml` |
| 工时 | 2h |

CWD 变更导致数据"丢失"。应迁移到 named Docker volume。

---

### TD-038 Python 安全依赖 open version ranges
| 文件 | `server/pyproject.toml` |
| 工时 | 1–2h |

`bcrypt>=4.0.0`, `cryptography>=42.0.0` 无上界，不同 group 间 cryptography 版本不一致。

---

### TD-039 deerflow-harness 未 pin commit
| 文件 | `server/pyproject.toml` |
| 工时 | 30min |

git URL 无 `rev=` 或 `tag=`，每次 clean sync 拉取不同代码。

---

### TD-040 `_proxy_*_events` 两个函数 120 行重复
| 文件 | `routers/_ai_events_helper.py` |
| 工时 | 2–3h |

`proxy_capability_events` 和 `proxy_agent_first_events` 共享 ~120 行逻辑。

---

### TD-041 useAIReportWS 硬编码 120s 超时
| 文件 | `composables/useAIReportWS.ts:27,44` |
| 工时 | 1h |

Magic number `120_000` 且 WS URL 构造未走统一 base-URL 逻辑。

---

### TD-042 SkillsManagePage 硬编码中文子串匹配
| 文件 | `pages/SkillsManagePage.vue:579` |
| 工时 | 0.5h |

`if (message?.includes('已存在'))` — 应匹配 error code 而非本地化消息。

---

### TD-043 `as any` 在测试文件中
| 文件 | `AIChatPage.spec.ts`, `AiStepBlock.test.ts`, `auth.test.ts` |
| 工时 | 2h |

强制类型转换掩盖测试中的类型错误。

---

## 四、LOW — 技术债积压

### TD-044 三份 nginx 配置重复
| 文件 | `nginx.conf`, `nginx.dev.conf`, `nginx.production.conf` |
| 工时 | 3h |

应使用 `include` 指令抽取共享片段。

---

### TD-045 system-config.yaml 与 example 文件相同
| 文件 | `system-config.yaml`, `system-config.example.yaml` |
| 工时 | 30min |

example 应为注释骨架，增加 `system-config.local.yaml` 到 `.gitignore`。

---

### TD-046 deploy 脚本无幂等性检查
| 文件 | `scripts/deploy-docker.sh:313` |
| 工时 | 1h |

每次 `docker compose down` 导致全量停机。应直接 `up -d --build` 滚动更新。

---

### TD-047 nginx.conf 缺少 /uploads/ 代理块
| 文件 | `nginx.conf` |
| 工时 | 15min |

Production 有但 default 无，请求 fallthrough 到前端返回 404。

---

### TD-048 CSP connect-src 硬编码 localhost:8000
| 文件 | `apps/backend/app/main.py:341` |
| 工时 | 30min |

应从 settings 构建。

---

### TD-049 deprecated loadMoreAssets 仍导出
| 文件 | `stores/dashboard.ts:302` |
| 工时 | 30min |

Dead API surface，确认无调用者后删除。

---

### TD-050 orchestrator 硬编码 assets=[] / members=[]
| 文件 | Agent orchestrator `_build_context()` |
| 工时 | 6–8h |

Agent 运行时缺少真实数据。需实现 `/internal/assets`, `/internal/members` 端点。（已知 gap，非 latent bug）

---

## 五、修复优先级路线图

### Phase 1: 紧急安全修复（本周，~5h）
| 编号 | 项目 | 工时 |
|------|------|------|
| TD-001 | SECRET_KEY 弱默认值 | 1h |
| TD-005 | 生产 nginx internal API 暴露 | 15min |
| TD-006 | HSTS + SPA CSP | 1.5h |
| TD-004 | python-jose → PyJWT | 3–4h |

### Phase 2: 速修高 ROI（下周，~8h）
| 编号 | 项目 | 工时 |
|------|------|------|
| TD-021 | WebSocket 泄漏 | 0.5h |
| TD-003 | DataStatsPage i18n | 1h |
| TD-039 | pin deerflow-harness commit | 0.5h |
| TD-017 | 统一 magic agent ID 常量 | 2–3h |
| TD-023 | migration 文件名修正 | 15min |
| TD-019 | Login/Register i18n 补全 | 1.5h |
| TD-031 | pin nginx image | 15min |

### Phase 3: 架构治理（2–3 周，~60h）
| 编号 | 项目 | 工时 |
|------|------|------|
| TD-002 | AIChatPage 拆分 | 12–16h |
| TD-009 | 后端 God files 拆分 | 12–16h |
| TD-008 | 路由层 DB 操作提取 service | 8–12h |
| TD-013 | 前端共享 API 包 | 8h |
| TD-012 | 删除自研迁移系统 | 6–8h |

### Phase 4: 持续改善（逐步，~50h）
| 编号 | 项目 | 工时 |
|------|------|------|
| TD-010 | bare except 治理 | 6–8h |
| TD-014 | BabyPage/InsightsTab 拆分 | 16h |
| TD-018 | 共享 httpx client | 3–4h |
| TD-016 | CSS hex → token | 6h |
| TD-034 | Agent dual-DB 统一 | 10–14h |

---

## 六、度量建议

建议在 CI 中增加以下自动化检查：

1. **`ruff check --select LOG`** — 禁止 `logging.getLogger` 直接使用
2. **`grep -r "except Exception" server/`** — 追踪 bare except 数量趋势
3. **`grep -rn "hardcoded" zh-CN strings`** — i18n 覆盖率检查（对比 `t()` 调用数 vs 裸中文数）
4. **Component line count gate** — Vue 文件超 500 行触发 warning
5. **Dependency age audit** — `pip-audit` + `npm audit` 纳入 CI

---

*审计完成。如需针对任一项展开详细修复方案，请指明编号。*
