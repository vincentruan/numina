# Agent 模块 Code Review 检查清单

> Review `server/apps/agent/` 代码时重点关注。

## Invariants

- [ ] PII redaction: `pii_redactor.redact()` 在传给 LLM 前调用
- [ ] Policy guard: `policy_guard.check()` 不被绕过
- [ ] Audit logging: `audit_logger.log_call()` 在 finally 块中；`output_summary` 写入前须经 `pii_redactor.redact_text()` 处理，防止 LLM 输出回传 PII 到审计日志
- [ ] DeerFlow-only: 多步骤调用不走 `core/llm.py`
- [ ] ContextVar 传播: `_run_in_executor_with_context` 正确使用
- [ ] R1 allowlist: worker 分支 + gateway 锁步对同步
- [ ] Family 隔离: temp config / memory / sandbox / MCP 无跨家庭泄漏

## DeerFlow 升级兼容

- [ ] `make_lead_agent()` 签名未变
- [ ] `create_chat_model()` provider 路由正确
- [ ] `sync_tool_patch.py` 的 5 个 patch 目标函数签名兼容
- [ ] `extensions_config` API 无变更
- [ ] `RunManager` / `StreamBridge` 接口无破坏性变更
