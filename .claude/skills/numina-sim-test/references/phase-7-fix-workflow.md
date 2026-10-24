# Phase 7 — Fix Workflow

> **Trigger:** User says "修复" / "fix" / "按分类提交" / "跟进失败项"
> after seeing the Phase 6 report. Default: do NOT execute — skill only
> records results.

## Step 1 — Extract failures from report

Read `tests/reports/ui-audit-{date}.md` "失败详情" section. For each
failure extract:
- Case ID (C2.3 / R4 / F.3.6 / ...)
- Category code (RENDER / NAV / AUTH / DATA / I18N / AI / INTERACT / PERF / REGRESS / UI-EXP)
- Route
- 初步判断

## Step 1.5 — .dev-logs correlation (dev mode only)

dev mode (`LOG=1` or `MODE=bg`) writes Python service logs to
`server/.dev-logs/`. Read logs to narrow root cause before fixing:

```bash
LOGDIR="server/.dev-logs"
# Failure case time window (from report/timestamp ±5 minutes)
SINCE="2026-10-14 15:00" UNTIL="2026-10-14 15:10"
awk -v s="$SINCE" -v e="$UNTIL" '$0 >= s && $0 <= e' \
  "$LOGDIR/backend-app.log" "$LOGDIR/agent-app.log" \
  "$LOGDIR/scheduler_worker-app.log" 2>/dev/null | \
  grep -Ei "error|exception|traceback|500 |4[0-9]{2} |failed|timeout" | head -40
```

- Log format: `YYYY-MM-DD HH:MM:SS,mmm - logger - LEVEL - message` (backend,
  incl. security); agent/worker: `YYYY-MM-DD HH:MM:SS,mmm [LEVEL] logger: msg`.
- Take time window around case failure, focus on ERROR/WARNING + HTTP status.
- Attribute log lines (strip user_id etc.) to failure's "初步判断".
- If `server/.dev-logs/` missing/empty → service started with `LOG=0`, no
  file logs available. Note in failure item "(dev-logs not enabled; try
  `make dev-all MODE=bg LOG=1`)", do NOT treat as test failure.
- Category gain: log correlation helps DATA / AI / AUTH / PERF failures.
  UI-EXP / RENDER / NAV / I18N are frontend-side — skip log search, go to Step 2.

### Step 1.6 — Docker log equivalent

```bash
docker logs numina-backend --since 10m 2>&1 | grep -Ei "error|exception|500" | head -30
docker logs numina-agent --since 10m 2>&1 | tail -40
```

## Step 2 — Generate fix checklist

Group by **category code**, one todo per failure:

```markdown
## 修复 Checklist — {date} 仿真测试

### 🔴 RENDER (渲染错误) — N 项
- [ ] C2.3 — 心愿详情页 dialog 未挂载 → `WishDetailPage.vue` 检查 v-model:show 绑定
- [ ] F.3.1 — Baby 总览页空白 → 检查数据加载 + 空态处理

### 🟠 NAV (导航/路由) — N 项
- [ ] C4.12 — activeTab 高亮错误 → 检查 route metadata 的 activeTab 映射
```

Each todo line format:
```
- [ ] {Case ID} — {short description} → `{fix hint (file/component/direction)}`
```

Fix hint from report's "初步判断" + code location (grep / codegraph).

## Step 3 — Fix + commit by category

**Commit order:** batch by category, one category = one commit (unless
multiple unrelated fixes in same category → split commits).

**Commit message template:**
```
fix({scope}): {category} — {N} sim-test failure fixes

- {Case ID}: {fix content} ({file}:{line})
- {Case ID}: {fix content} ({file}:{line})

Ref: tests/reports/ui-audit-{date}.md
```

**Scope selection:**
- RENDER → `ui` or component name (e.g. `wish-detail`)
- NAV → `router`
- AUTH → `auth`
- DATA → `display` or `money`
- I18N → `i18n`
- AI → `ai`
- INTERACT → `ui` or component name
- PERF → `perf`
- REGRESS → `regression`

**Multi-commit split conditions:**
- Different modules (backend router vs frontend component)
- Different fix sizes (one-liner vs refactor)
- Dependencies (A must be fixed before B can verify)

## Step 4 — Verify + update checklist

After each commit:
1. Run the corresponding sim-test case (single case: `area-N` or drive route directly)
2. Pass → check off: `- [x] C2.3 — ...`
3. Fail → keep `[ ]`, append `(retry {N}: {new finding})`
4. All fixed → run `smoke` mode for regression check

## Step 5 — Final report

```markdown
## 修复结果 — {date}
- 总失败: {N} 项
- 已修复: {X} 项 ({commits} commits)
- 遗留: {Y} 项 (原因: {needs product decision / needs backend work / ...})
- 回归测试: smoke 模式 {通过/失败}
```

Summary by category:
| 分类 | 失败 | 已修 | 遗留 |
|------|------|------|------|
| RENDER | 3 | 3 | 0 |
| NAV | 1 | 0 | 1 (needs route refactor) |
| AI | 2 | 1 | 1 (needs LLM provider check) |
