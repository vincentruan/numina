# Numina Agent 微服务

`agent/` 是 Numina 家庭资产管理系统的 AI 分析微服务，负责接收 backend 下发的脱敏家庭财务数据，通过 DeerFlow harness 或 legacy 路径执行分析，并返回结构化 `AgentResponse`。

## 架构概览

```
Backend (FastAPI)
    │  受认证内部 HTTP (X-Agent-Token + X-Family-Id)
    ▼
Agent Service (FastAPI)
    │
    ├── app/                # 入口文件包（新增）
    │   ├── main.py         # FastAPI 入口
    │   ├── config.py       # AgentSettings 配置
    │   └── scheduler.py    # APScheduler 定时任务
    ├── PolicyGuard        — 检查 AI 开关、能力白名单、管理员限制
    ├── BackendClient      — 拉取家庭资产/负债/仪表盘数据
    ├── PIIRedactor        — 脱敏结构化数据 + 自由文本
    ├── DeerFlowAdapter    — USE_DEERFLOW=true 时调用 DeerFlow harness
    │   └── FallbackEngine — DeerFlow 失败或禁用时走 legacy 路径
    ├── OutputMapper       — 将任意输出映射为稳定 AgentResponse
    └── AuditLogger        — 写入结构化审计日志
```

**注意**: 入口文件位于 `app/` 包下，与 backend 结构保持一致。

## 快速启动

```bash
# 安装依赖
uv sync

# 启动开发服务器（不要在自动化 agent 中运行）
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 运行测试
uv run pytest tests/ -v
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AGENT_INTERNAL_TOKEN` | — | **必填**。Backend 调用 agent 的内部认证 token |
| `BACKEND_BASE_URL` | `http://localhost:8000` | Backend 服务地址 |
| `USE_DEERFLOW` | `false` | 是否启用 DeerFlow harness 路径 |
| `DEERFLOW_CONFIG_ENV` | `dev` | DeerFlow 配置环境（`dev`/`prod`） |
| `DEER_FLOW_CONFIG_PATH` | — | **必填**。DeerFlow 配置文件路径（相对于 `server/` 目录，如 `apps/agent/deerflow_config/base/config.yaml`） |

## API 端点

所有端点均需 `X-Agent-Token` 和 `X-Family-Id` header。

| 方法 | 路径 | 能力 | 说明 |
|------|------|------|------|
| POST | `/report/generate` | `report` | 家庭资产体检报告 |
| POST | `/alerts/aging` | `alerts` | 固定资产老化预警 |
| POST | `/liability/analyze` | `liability` | 负债结构分析 |
| POST | `/disposal/scan` | `disposal` | 闲置资产处置建议 |
| POST | `/allocation/drift` | `allocation` | 资产配置漂移检测 |
| POST | `/chat/ask` | `chat` | 问答助手 |
| POST | `/suggest/asset` | `suggest` | 资产录入智能建议 |

## 输出契约

所有端点返回统一的 `AgentResponse` JSON：

```json
{
  "capability": "report",
  "summary": "...",
  "scorecards": [{"name": "净资产健康", "score": 4.0, "max_score": 5.0, "label": "良好", "color": "green"}],
  "risk_flags": [{"level": "medium", "title": "...", "description": "..."}],
  "recommendations": [{"priority": "high", "title": "...", "body": "...", "action_type": "suggestion"}],
  "rule_based_findings": [{"source": "rule", "content": "...", "confidence": 1.0}],
  "ai_inferences": [{"source": "ai", "content": "...", "confidence": 0.65}],
  "disclaimers": ["本分析仅供参考"],
  "fallback_used": false,
  "audit_id": "uuid"
}
```

## 自定义 Skills

`skills/custom/` 下包含家庭财务领域 skills：

| Skill | 触发场景 |
|-------|---------|
| `chat` | 通用问答 + 结构化财务分析（资产体检 / 负债结构 / 固定资产跟踪 / 深度研究框架已并入） |
| `chat-search` | 需要联网搜索的问答 |

> 4 个原专项分析 skill（family-asset-checkup / family-liability-review /
> fixed-asset-followup / family-finance-insight-planner）已合并进 `chat` SOUL
>（见 `skills/builtin/public/chat/SKILL.md` 结构化分析框架段）。

## 安全边界

- **PII 脱敏**：所有数据在进入 LLM 前经过 `PIIRedactor` 处理
- **权限控制**：`PolicyGuard` 在 LLM 调用前检查管理员开关
- **审计日志**：每次调用写入 `logs/agent-audit.log`（JSON-line，30天轮转）
- **长期记忆**：仅允许保存行为偏好类低敏信息，不存储原始财务数据

## 测试

```bash
# 全部测试
uv run pytest tests/ -v

# 仅单元测试
uv run pytest tests/unit/ -v

# 仅集成测试
uv run pytest tests/integration/ -v

# Golden case 测试
uv run pytest tests/golden/ -v
```

## 回滚

如需关闭 DeerFlow 路径，设置环境变量：

```bash
USE_DEERFLOW=false
```

服务无需重启即可在下次请求时走 legacy 路径。详见 [升级手册](../docs/agent-upgrade-playbook.md)。
