# numina-sim-test SKILL.md — 审查报告

**审查日期:** 2026-09-26  
**审查范围:** `.claude/skills/numina-sim-test/SKILL.md` (1176 行, 67KB)  
**文档分类:** plan（操作程序/技能定义）  
**审查团队:** coherence-reviewer, feasibility-reviewer, security-lens-reviewer, scope-guardian-reviewer, design-lens-reviewer  
**修复日期:** 2026-09-26  
**修复状态:** ✅ 已修复 / ⏳ 延期 / ❌ 未修复

---

## 摘要

| 维度 | 修复前 | 修复后 | 核心变更 |
|------|--------|--------|----------|
| **内部一致性** | 🔴 多处矛盾 | 🟢 已对齐 | G1 排序统一、F 范围修正、失败排序扩展至 Area15 |
| **可执行性** | 🔴 关键缺陷 | 🟢 已修复 | Chrome DevTools 检测重写、时间估算修正、崩溃恢复流程 |
| **安全性** | 🟡 可改善 | 🟢 已改善 | Token 清理、credential 红线、session 登出、报告脱敏 |
| **范围适配** | 🟡 过大 | 🟡 保留+标注 | Phase 6/7 矛盾消除；Area 6/11 保留但标注性质 |
| **设计覆盖** | 🟡 深度不足 | 🟢 已扩展 | 多视口、WCAG 对比度、错误状态、无障碍系统化 |

**统计:** 33 个独立发现（1 P0, 8 P1, 15 P2, 5 P3, 4 FYI）  
**已修复:** 22 项 ✅ | **延期:** 8 项 ⏳ | **误报:** 1 项（smoke count） | **保留设计决策:** 2 项

---

## P0 — 必须修复 (1)

### [P0] Phase 0 — Chrome DevTools MCP 检测为 bash 空操作 ✅ 已修复

- **修复:** `command -v echo` → `MCP_CHROME_DEVTOOLS` 环境变量检测，agent 自检工具列表后设置

- **Section:** Phase 0 — Browser Driver Detection
- **Reviewer:** feasibility, confidence 100
- **问题:** `command -v echo` 永远成功（`/bin/echo` 始终存在），当 browser-use 和 bsk 都缺失时，脚本无条件设置 `BROWSER_DRIVER=chrome-devtools`，即使 MCP 服务器未配置
- **后果:** 后续所有浏览器命令失败且无明确错误提示
- **证据:** `elif command -v echo &>/dev/null; then` — 条件永远为真；行内注释承认 `# only if MCP tools confirmed available` 但无代码实现此检查
- **修复:** 替换为 agent 在运行脚本前自检工具列表的 out-of-band 检查，或使用 sentinel 变量

---

## P1 — 高优先级 (8)

### [P1-1] Smoke 模式计数声称 10 但枚举仅 9 — ❌ 误报

- **结论:** 实际枚举 `C2.1, C2.2, C2.5, C2.8, C3.1, C3.2, C4.0, R1, R2, C9.4` 确为 10 项，审查员计数错误

### [P1-2] G1 内部排序省略 Areas 9/10/13 且与 groups/README.md 矛盾 ✅ 已修复

- **修复:** G1 table 增加 9, 13（10 属 G3）；内部排序统一为 `area2→area14→area8→area3→area6→area13→area12→area15→area9→area7→area11`；SKILL.md 与 groups/README.md 已同步

### [P1-3] AI Pre-check 位于 Phase 4 之后但其必须先行 ✅ 已修复

- **修复:** AI Pre-check 提取为独立 section，移至 Phase 3 之前

### [P1-4] 全量运行时间估算与各区估算总和不符 ✅ 已修复

- **修复:** 120-150 min → 180-220 min（基于 G1 各区估算总和 ~185 min + G0/G2 开销）

### [P1-5] Phase 7（修复提交）超出测试技能范围 ✅ 已修复（矛盾消除）

- **修复:** Phase 6 声明从 "fixing is out of scope" 改为 "see Phase 7 (OPTIONAL — triggered by 修复/fix)"，消除矛盾。保留 Phase 7 为可选流程。

### [P1-6] Area 15 视口覆盖仅 375px ✅ 已修复

- **修复:** UIQ.1 增加 320×568（最小设备）和 768×1024（平板断点）测试

### [P1-7] Area 15 缺少表单错误状态交互覆盖 ✅ 已修复

- **修复:** UIQ.4 扩展增加 error state：触发验证错误，检查消息位置、双模式可读性、design token

### [P1-8] Area 15 无障碍测试为抽查式 ✅ 已修复

- **修复:** UIQ.8 从 "spot-check 5 icons" 扩展为：全量 icon 枚举、WCAG AA 对比度测量、modal focus trap 测试、prefers-reduced-motion 验证

---

## P2 — 中优先级 (15)

### 范围/架构决策 (5)

| # | Section | Title | Reviewer | 状态 |
|---|---------|-------|----------|------|
| 1 | Area 6 | DeerFlow 对等性是产品审计非 UI 测试 | scope-guardian | ⏳ 保留：标注为"flag not fail"，不拆分 |
| 2 | Area 11 | 对抗安全测试应归属安全技能 | scope-guardian | ⏳ 保留：security 模式已单独分组 |
| 3 | Run Modes | 10 种模式复杂度过高 | scope-guardian | ⏳ 保留：友好别名有用户体验价值 |
| 4 | Parallel Run | G0-G3 并行结构复杂度高 | scope-guardian | ✅ 已增加 MCP 并行协调注意事项 |
| 5 | Full skill | 15 区域超出声明目标 | scope-guardian | ⏳ 保留：15 areas 是已确认的完整覆盖 |

### 遗漏 (10)

| # | Section | Title | Reviewer | 状态 |
|---|---------|-------|----------|------|
| 6 | Area 8 | F.1–F.10 范围错误 | coherence | ✅ 已修正为 F.1–F.8, F.11, F.12 |
| 7 | Phase 3/4/5 | 浏览器驱动崩溃无恢复路径 | feasibility | ✅ 已增加 Driver crash recovery + SKIP-INFRA |
| 8 | Parallel Run | Chrome DevTools MCP 无页面协调 | feasibility | ✅ 已增加 MCP caveat 注意事项 |
| 9 | Phase 6 | 报告仅依赖截图 | feasibility | ✅ 已增加 snapshot 优先的证据规则 |
| 10 | Phase 1.5 | child auth 门禁仅验证 step1 | feasibility | ⏳ 延期：需确认后端 PIN 配置 |
| 11 | Area 15 UIQ.2/3 | 深色模式对比度无量化 | design-lens | ✅ 已增加 WCAG AA 测量流程 |
| 12 | Area 15 UIQ.10 | 跨应用一致性为主观描述 | design-lens | ✅ UIQ.10 已增加量化阈值 |
| 13 | Area 15 UIQ.2/3 | 深色模式过渡动画未测试 | design-lens | ✅ UIQ.3 已增加 transition flash 检查 |
| 14 | Area 11 | 注入数据失败时无保证清理 | security | ⏳ 延期：需设计 try/finally 模式 |
| 15 | Phase 5 | 无服务端登出/token 撤销 | security | ✅ 已增加 logout + unset 清理步骤 |

---

## P3 — 低优先级 (5)

| # | Section | Title | Reviewer | 状态 |
|---|---------|-------|----------|------|
| 1 | Parallel Run | "3-4 agents" vs "Three agents" | coherence | ✅ 已统一为 "3 agents" |
| 2 | Phase 1.5 | Auth token 无 unset 清理 | security | ✅ 已增加 token cleanup 步骤 |
| 3 | Phase 6 | 报告包含 family_id | security | ✅ 已从模板中移除 family_id |
| 4 | Browser Red Lines | 缺少凭据日志约束 | security | ✅ 已增加红线 #6 (credential logging) 和 #7 (sensitive data in reports) |
| 5 | Phase 6 | 失败排序止于 Area8 | coherence | ✅ 已修正为 Area1→…→Area15 |

---

## FYI Observations (4)

- Phase 2 fallback 将完整 /auth/me 响应存入 localStorage（与生产行为一致，但值得记录 trust boundary）
- Session cleanup 并行 agent 崩溃时 orchestrator 无最终清理步骤
- prefers-reduced-motion 在 UIQ.8 列为检查项但无具体验证流程
- 空状态设计质量仅检查组件存在性，未检查插图/CTA/视觉平衡

---

## Residual Concerns

1. **Agent 上下文容量：** 1176 行 / 67KB 的技能文档可能超出 agent 单次上下文可靠执行容量
2. **Docker 并行退化：** G3 无法与 G1/G2 并行（同源 cookie），docker 全量实际需 ~210+ min
3. **AI 中途不稳定：** 长时间运行中 AI provider 不稳定可导致级联误报，无中途 SKIP-AI 机制
4. **子 agent 报告合并：** 并行 agent 写入带 group prefix 的失败，但 Phase 6 由单 agent 执行，合并机制未定义

---

## Deferred Questions

1. F.9 和 F.10 是否在 area8-expanded-features.md 中定义？还是索引中的 "F.1–F.10" 是过度声称？
2. Areas 9/10/13 是故意不在 G1 排序中（有特殊执行约束）还是遗漏？
3. Smoke 模式应该是 9 还是 10 个用例？
4. 后端是否有 logout/revoke 端点？如无，session-cleanup 是后端 feature request
5. 是否应将 SKILL.md 拆分为核心 (~400 行) + 各 area 独立参考文档？
6. 768px 平板断点是必须测试还是可选扩展？

---

## 建议优先处理

1. **立即修复 (P0):** Phase 0 chrome-devtools 检测 — 一行修复
2. **短期修复 (P1):** G1 排序对齐 + 计数修正 + 时间估算更新 + AI Pre-check 位置
3. **架构决策:** Phase 7 拆分 + Area 6/11 保留/提取 + 运行模式精简
4. **中期改进:** 无障碍系统化 + 对比度测量 + 多视口覆盖 + 错误状态测试
