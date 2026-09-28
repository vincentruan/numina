# 调度 App 注册表

> `server/apps/agent/` 中全部 8 个 DeerFlow 调度 app。

## Custom Runner Apps (独立 runner 函数)

| App | Runner | Skill | 用途 |
|-----|--------|-------|------|
| `numina` | `_run_numina_agent` | chat / chat-search | 实时对话 |
| `asset-report` | `_run_asset_report_agent` | asset-report | 3 步资产报告 |
| `import-parse` | `_run_import_parse_agent` | import-parse | PDF/账单解析 |
| `finance-coach` | `_run_finance_coach_agent` | finance-coach | 理财建议 |
| `wish-advice` | `_run_wish_advice_agent` | wish-advice | 愿望储蓄建议 |

## Config-Driven Apps (`_SimpleAppConfig` + `_run_simple_app` 通用 runner)

| App | Skill | 用途 |
|-----|-------|------|
| `dashboard-narrative` | dashboard-narrative | 仪表盘 AI 叙事 |
| `literacy-weekly-report` | literacy-weekly-report | 启蒙周报 |
| `learning-tutor` | learning-tutor | AI 学习辅导 |

## 新增 App 步骤

1. 在 `services/runtime/worker.py` 添加 runner（或 `_SimpleAppConfig` 通用 runner）
2. 在 `run_agent` 的 `metadata["app"]` 分支中添加路由
3. 在 `sse_gateway.py` R1 allowlist 中注册（前端直连 vs `internal=True` 后端触发 — **锁步对**）
4. 在 `skills/builtin/public/<app>/SKILL.md` 定义 skill
5. 在 backend `RESERVED_NAMES` 中添加 skill ID 防冲突
6. 如需后端触发，在 `app/routers/gateway.py` 添加 internal endpoint

**完成标准**:
- [ ] `run_agent` 能路由到新 app 并成功 dispatch
- [ ] 前端 SSE 连接能收到首个 event（直连场景）或正确返回鉴权错误（内部场景）
- [ ] R1 allowlist 验证通过
- [ ] Skill scanner 能发现新 skill（`{root}/public/{skill}/SKILL.md` 路径正确）
