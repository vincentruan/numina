# Decision Tree — Anomaly Classification

巡检中发现异常后，按以下决策树进行分类。

## 分类原则

1. **有 traceback → 先假设 CODE_DEFECT** — Python traceback 几乎总是代码 bug
2. **资源/环境问题 → RECOVERABLE_ENV** — OOM、连接池耗尽、外部依赖故障
3. **无法确定 → HUMAN_INTERVENTION** — 安全兜底，宁可让人介入
4. **多个异常同时出现 → 找根因** — 可能是同一个问题导致多个症状

## 详细决策流程

```
发现异常
  │
  ├─ 有 Python traceback？
  │   ├─ 是 → 计算 fingerprint
  │   │   ├─ 同 fingerprint 已出现 ≥3 次 → CODE_DEFECT（稳定复现的 bug）
  │   │   ├─ 同 fingerprint 出现 2 次 → CODE_DEFECT（可重复但需确认）
  │   │   └─ 仅出现 1 次 → 检查异常类型
  │   │       ├─ TypeError/AttributeError/KeyError → CODE_DEFECT（几乎总是代码 bug）
  │   │       ├─ ImportError/ModuleNotFoundError → CODE_DEFECT（部署问题，但需修代码/配置）
  │   │       ├─ ConnectionError/TimeoutError → 检查是否 Supabase pooler
  │   │       │   ├─ 是 → RECOVERABLE_ENV（外部依赖）
  │   │       │   └─ 否 → HUMAN_INTERVENTION
  │   │       └─ 其他 → HUMAN_INTERVENTION
  │   │
  │   └─ 否 → 继续检查
  │
  ├─ Container 状态异常？
  │   ├─ OOMKilled = true → RECOVERABLE_ENV
  │   ├─ RestartCount > 5 (1h) → 检查 restart 原因
  │   │   ├─ restart 后健康 → RECOVERABLE_ENV（暂时恢复）
  │   │   └─ restart 后仍不健康 → HUMAN_INTERVENTION
  │   ├─ Exit Code ≠ 0 且无 traceback → HUMAN_INTERVENTION
  │   └─ Container 正常运行 → 继续检查
  │
  ├─ HTTP health 失败？
  │   ├─ Backend 5xx → 检查是否有对应 traceback
  │   │   ├─ 有 → CODE_DEFECT
  │   │   └─ 无 → HUMAN_INTERVENTION（可能是 nginx/proxy 层）
  │   ├─ Frontend 不可达 → HUMAN_INTERVENTION（nginx 配置问题？）
  │   └─ Agent/Scheduler 不可达 → 检查 container 状态（回到上层分支）
  │
  ├─ 数据库异常？
  │   ├─ 连接超时 → RECOVERABLE_ENV（Supabase pooler 问题）
  │   ├─ 查询错误 → HUMAN_INTERVENTION（可能是 schema 不一致）
  │   └─ 正常 → 继续
  │
  └─ 多个服务同时异常？
      └─ HUMAN_INTERVENTION（系统性问题，需要人工排查根因）
```

## 分类含义

| 分类 | 含义 | 处置 |
|------|------|------|
| **HEALTHY** | 所有检查通过，无异常 | 无操作 |
| **CODE_DEFECT** | 代码 bug 导致的异常 | 关联/创建 GitHub Issue，**禁止 restart** |
| **RECOVERABLE_ENV** | 环境/资源问题，restart 可能恢复 | 若 allowlist + cooldown 通过 → restart |
| **HUMAN_INTERVENTION** | 无法自动判断或处置 | 生成报告，通知用户 |

## 特殊规则

### CODE_DEFECT 禁止 restart

Python traceback 意味着代码有 bug。Restart 会：
1. 暂时清除症状（让问题看起来"修好了"）
2. 但实际上 bug 还在，下次请求还会触发
3. 浪费了 restart 的机会（如果之后环境问题也需要 restart，cooldown 会阻止）

所以 CODE_DEFECT 的唯一处置是：关联到 GitHub Issue，等代码修复。

### 多次出现的 fingerprint 升级

- 同一 fingerprint 在 24h 内出现 ≥5 次 → 即使之前是 HUMAN_INTERVENTION，也应升级为 CODE_DEFECT
- 这意味着问题可复现，大概率是代码 bug

### RECOVERABLE_ENV 的 restart 前提

即使分类为 RECOVERABLE_ENV，restart 还需要满足：
1. Container 在 `restart_allowlist` 中
2. 距离上次 restart 超过 `cooldown_seconds`
3. 本小时 restart 次数未超过 `max_per_hour`

任一条件不满足 → 降级为 HUMAN_INTERVENTION。
