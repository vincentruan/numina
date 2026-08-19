# Recovery Actions — Per-Classification Playbook

根据异常分类执行的处置动作详解。

## HEALTHY — 无操作

所有检查通过，无需任何操作。

**记录内容：**
- 巡检时间、窗口
- 各维度状态（全部 OK）
- 当前 revision 信息

```bash
python .claude/skills/production-ops-patrol/scripts/state_db.py record-patrol \
  --result HEALTHY \
  --summary "All checks passed, no anomalies detected" \
  --details '{"dimensions_ok": 7, "dimensions_warn": 0}'
```

## CODE_DEFECT — 关联 GitHub Issue

发现代码 bug，**禁止 restart**。

**步骤：**

1. **计算异常 fingerprint**
   ```bash
   python .claude/skills/production-ops-patrol/scripts/fingerprint.py \
     --traceback '<traceback text>'
   ```

2. **记录 fingerprint 到 SQLite**
   ```bash
   python .claude/skills/production-ops-patrol/scripts/state_db.py upsert-fingerprint \
     --fingerprint '<hash>' \
     --exception-type '<ExceptionType>' \
     --normalized-key '<key>' \
     --classification CODE_DEFECT
   ```

3. **查询 GitHub 关联 Issue**
   ```bash
   python .claude/skills/production-ops-patrol/scripts/github_check.py \
     --fingerprint '<hash>' --error-type '<ExceptionType>'
   ```

4. **根据查询结果**：
   - **已找到关联 Issue** → 记录关联关系，报告给用户
   - **未找到** → 建议用户创建新 Issue（不自动创建）

5. **记录审计**
   ```bash
   python .claude/skills/production-ops-patrol/scripts/state_db.py record-patrol \
     --result CODE_DEFECT \
     --summary "Found <N> code defect(s), fingerprint(s): <list>" \
     --details '{"fingerprints": [...], "github_issues": [...]}'

   python .claude/skills/production-ops-patrol/scripts/state_db.py record-action \
     --action "github_issue_link" \
     --fingerprint '<hash>' \
     --reason "CODE_DEFECT: <ExceptionType> in <file>:<line>"
   ```

**绝对不做：**
- ❌ Restart 任何服务（restart 不能修复代码 bug）
- ❌ 修改任何代码
- ❌ 忽略 traceback 或标记为"偶发"

## RECOVERABLE_ENV — 有条件 restart

环境/资源问题，可能通过 restart 恢复。

**前置条件检查（全部通过才能 restart）：**

1. **Container 在 restart_allowlist 中？**
   - ✅ `numina-backend`、`numina-agent`、`numina-scheduler-worker`
   - ❌ 其他 → 降级为 HUMAN_INTERVENTION

2. **Cooldown 是否已过？**
   ```bash
   python .claude/skills/production-ops-patrol/scripts/state_db.py check-cooldown \
     --container '<name>' --cooldown-seconds 300
   ```
   - `allowed: true` → 继续
   - `allowed: false` → 降级为 HUMAN_INTERVENTION

3. **Restart 次数限制？**
   ```bash
   python .claude/skills/production-ops-patrol/scripts/state_db.py check-restart-limit \
     --container '<name>' --max-per-hour 3
   ```
   - `allowed: true` → 继续
   - `allowed: false` → 降级为 HUMAN_INTERVENTION

**执行 restart（仅当前三步全部通过）：**

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'sudo docker compose -f docker-compose.production.yml restart <container>'
```

**恢复验证：**

1. 等待 start_period + interval：
   - backend: 40s（start_period 10s + interval 30s）
   - agent/scheduler_worker: 30s（start_period 15s + interval 15s）

2. 检查 health endpoint：
   ```bash
   # backend
   curl -sk https://localhost/api/health
   # agent
   ssh ... 'docker exec numina-agent curl -s http://localhost:8001/health'
   # scheduler_worker
   ssh ... 'docker exec numina-scheduler-worker curl -s http://localhost:8002/health'
   ```

3. 检查最近 30s 日志是否有新 traceback：
   ```bash
   ssh ... 'docker logs --since 30s <container> 2>&1 | grep -c "Traceback"'
   ```

**记录结果：**

```bash
# 成功
python .claude/skills/production-ops-patrol/scripts/state_db.py record-restart \
  --container '<name>' --success true --reason 'RECOVERABLE_ENV: <reason>'

# 失败
python .claude/skills/production-ops-patrol/scripts/state_db.py record-restart \
  --container '<name>' --success false --reason 'RECOVERABLE_ENV: <reason>, health check failed'
```

**典型 RECOVERABLE_ENV 场景：**
- OOMKilled — 内存不足，restart 释放资源
- Supabase pooler 连接超时 — 外部依赖暂时不可用
- Container crash + Exit Code 137 (SIGKILL) — 被 OOM killer 杀死
- 连接池耗尽 — restart 重置连接

## HUMAN_INTERVENTION — 报告并等待

无法自动判断或处置，需要人工介入。

**必须提供的信息：**

1. 异常描述（什么出了问题）
2. 影响范围（哪些服务/功能受影响）
3. 异常证据（日志片段、traceback、health 状态）
4. 已排除的原因（已经检查了什么）
5. 建议的下一步（人工应该做什么）

**记录审计：**

```bash
python .claude/skills/production-ops-patrol/scripts/state_db.py record-patrol \
  --result HUMAN_INTERVENTION \
  --summary '<description>' \
  --details '{"anomalies": [...], "reason": "<why human needed>"}'

python .claude/skills/production-ops-patrol/scripts/state_db.py record-action \
  --action "notify_human" \
  --reason '<why auto-recovery not possible>'
```

**典型 HUMAN_INTERVENTION 场景：**
- 多个服务同时异常（系统性问题）
- nginx 5xx 但无 traceback（proxy 层问题）
- Container 异常退出但无 OOM/traceback
- Restart allowlist 之外的 container 异常
- Restart 后仍不健康
- 无法分类的异常
