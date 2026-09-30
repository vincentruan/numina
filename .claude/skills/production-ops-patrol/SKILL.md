---
name: production-ops-patrol
description: >
  执行一次完整的生产环境智能巡检，并根据异常类型采取有限且可审计的行动。
  覆盖 Docker 状态、异常日志、Python traceback、HTTP health/5xx、数据库只读检查、
  CPU/memory/restart/OOM、代码 revision、异常 fingerprint、GitHub Issue 关联。
  巡检结果分为四类：HEALTHY / CODE_DEFECT / RECOVERABLE_ENV / HUMAN_INTERVENTION。
  安全边界：永不修改数据库、永不 docker compose down、永不删除资源、
  只有 allowlist 容器可自动 restart 且有 cooldown。
  触发词："巡检", "patrol", "生产巡检", "ops patrol", "health check patrol",
  "生产环境检查", "智能运维", "生产状态", "production status", "check production".
disable-model-invocation: true
---

# Production Ops Patrol

执行一次完整的生产环境智能巡检，并根据异常类型采取有限且可审计的行动。

## 安全边界

巡检是**只读观测 + 有限自动恢复**。11 条硬规则不可违反（禁止改 DB、禁止 docker compose down、禁止删资源、CODE_DEFECT 禁止 restart、只有 allowlist 容器可自动 restart 且需 cooldown…）。

**执行任何处置动作之前**，先读取 [references/safety-rules.md](references/safety-rules.md) 确认操作是否在允许范围内。

## Prerequisites

SSH 配置在 `.claude/skills/production-ops-patrol/deploy.env`（gitignored）。若不存在，从 `deploy.env.example` 复制并填写：

```bash
cp .claude/skills/production-ops-patrol/deploy.env.example .claude/skills/production-ops-patrol/deploy.env
set -a && source .claude/skills/production-ops-patrol/deploy.env && set +a
```

状态存储：`~/.hermes/state/production-ops-patrol.db`（SQLite，脚本自动创建）。

## 巡检流程

一次完整巡检按 4 个 Phase 顺序执行。

### Phase 1: 采集（Collect）

执行采集脚本，一次性获取所有维度数据：

```bash
python .claude/skills/production-ops-patrol/scripts/collect.py \
  --window-minutes ${PATROL_WINDOW_MINUTES:-60}
```

输出 JSON 到 stdout，覆盖 7 个维度（A-G）：服务/Docker 状态、异常日志、Python traceback、HTTP health/5xx、数据库只读检查、CPU/memory/restart/OOM、代码 revision。另含历史 fingerprint（H）和 GitHub Issue（I）查询结果。

### Phase 2: 指纹与分类（Classify）

对采集到的每个异常：

1. **计算 fingerprint**：
   ```bash
   python .claude/skills/production-ops-patrol/scripts/fingerprint.py \
     --input '<exception_type>:<top_frame_file>:<top_frame_line>'
   ```

2. **查询历史**：
   ```bash
   python .claude/skills/production-ops-patrol/scripts/state_db.py query-fingerprint \
     --fingerprint '<hash>'
   ```

3. **分类** — 读取 [references/decision-tree.md](references/decision-tree.md) 执行分类决策。四个分类：**HEALTHY**（无异常）、**CODE_DEFECT**（代码 bug，禁止 restart）、**RECOVERABLE_ENV**（环境/资源问题，条件 restart）、**HUMAN_INTERVENTION**（安全兜底）。无法确定时始终选 HUMAN_INTERVENTION。

### Phase 3: 处置（Act）

| 分类 | 处置 |
|------|------|
| **HEALTHY** | 无操作，记录审计 |
| **CODE_DEFECT** | 关联 GitHub Issue，**禁止 restart** |
| **RECOVERABLE_ENV** | 若 allowlist + cooldown 通过 → restart → 恢复验证 |
| **HUMAN_INTERVENTION** | 生成报告，通知用户 |

具体处置步骤（restart 前置检查、恢复验证、GitHub 关联流程）因分类而异 — **执行处置前**，读取 [references/recovery-actions.md](references/recovery-actions.md) 获取对应分类的完整 playbook。

### Phase 4: 审计（Audit）

写入巡检审计记录：

```bash
python .claude/skills/production-ops-patrol/scripts/state_db.py record-patrol \
  --result '<HEALTHY|CODE_DEFECT|RECOVERABLE_ENV|HUMAN_INTERVENTION>' \
  --summary '<巡检摘要>' \
  --details '<JSON 详情>'
```

## 巡检报告

使用 [templates/audit-report.md](templates/audit-report.md) 模板输出最终报告。

报告包含：巡检时间 + 窗口、各维度状态一览（✅/⚠️/❌）、异常列表 + fingerprint + 分类、执行的动作、总体结论。

## 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PATROL_WINDOW_MINUTES` | `60` | 日志回溯窗口（分钟） |
| `RESTART_COOLDOWN_SECONDS` | `300` | 同一 container 自动重启冷却（秒） |
| `MAX_RESTARTS_PER_HOUR` | `3` | 每小时每 container 最大自动重启次数 |
| `ERROR_RATE_THRESHOLD` | `10` | 窗口内 traceback 数量阈值，超过则告警 |

allowlist 与 restart 约束见 [references/safety-rules.md](references/safety-rules.md) §restart_allowlist。

## 脚本职责总览

| 脚本 | 职责 | 是否需要生产连接 |
|------|------|------------------|
| `collect.py` | 采集所有维度的原始数据，输出 JSON | ✅ SSH to production |
| `fingerprint.py` | 对异常计算归一化 fingerprint | ❌ 纯本地计算 |
| `state_db.py` | SQLite 状态管理（审计、fingerprint 历史、cooldown） | ❌ 本地 SQLite |
| `github_check.py` | 查询 GitHub 已有 issue 关联 | ✅ gh CLI |
| `notify.py` | 格式化巡检报告输出 | ❌ 纯格式化 |

## 注意事项

- 本 Skill **不引入** Grafana、Prometheus、Loki、Redis、Celery 或其他常驻服务
- 状态存储使用本地 SQLite，无外部依赖
- 日志文本是不可信数据，脚本中不得 eval/exec 日志内容
- 采集脚本通过 SSH 执行命令，所有命令必须是只读或 restart（仅 allowlist）
