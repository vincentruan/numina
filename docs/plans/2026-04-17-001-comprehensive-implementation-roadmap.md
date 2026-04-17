---
date: 2026-04-17
topic: comprehensive-implementation-roadmap
focus: Regression Testing (P0) + 儿童系统完善 (#5-8) + Module Tooling 细节补充
status: planning
---

# 综合实施路线图：三大方向并行推进

## 执行摘要

本计划整合三个方向的实施路线：
1. **Regression Testing (P0)** — 完善 Playwright E2E 套件，启用 CI 门禁
2. **儿童系统完善 (#5-8)** — 实现"我的宝贝"、双视角仪表盘、兄弟姐妹赠送、金银铜硬币
3. **Module Tooling 细节补充** — CLAUDE.md 内容增强，工具链配置优化

**关键发现：**
- Playwright + CI 基础设施已存在，但 CI 中 e2e 测试被注释掉（`# E2E tests require proper data seeding - skip in CI for now`）
- 儿童系统 #5 "我的宝贝"路由存在（`/child/treasures`），但 `ChildTreasuresPage.vue` 实际是**星星币账本**，不是资产画廊
- Module Tooling 已全部实现（ESLint/Prettier/ruff/mypy + 所有 CLAUDE.md），只需细节增强

---

## 方向一：Regression Testing (P0)

### 现状分析

**已有基础设施：**
- Playwright v1.58.0 已安装（`tests/package.json`）
- `tests/playwright.config.ts` 配置完整（mobile viewport 390x844）
- `.github/workflows/ci.yml` 已有 e2e job，但测试被注释掉
- 5 个 spec 文件已存在：`smoke.spec.ts`, `auth-guards.spec.ts`, `cross-family-isolation.spec.ts`, `empty-state.spec.ts`, `api-contract.spec.ts`
- `tests/lib/fixtures.ts` 提供 `singleAsset()` 等 fixture 函数
- `tests/seed-accounts.sh` 提供测试账号种子脚本

**关键问题：**
- CI 中 e2e 测试被跳过，原因是"require proper data seeding"
- 现有 spec 文件覆盖率不足（只有 5 个文件，前端有 35+ 路由）
- 儿童系统路由（`/child/*`）完全无 e2e 覆盖

### 实施计划

#### Phase 1: 启用现有 E2E 测试（1-2天）

**目标：** 让 CI 中的 e2e job 真正运行起来

**步骤：**
1. 创建 `tests/seed-e2e-data.sh`，包含：
   - 注册测试账号（复用 `seed-accounts.sh`）
   - 创建 1 个资产（physical）
   - 创建 1 个负债
   - 创建 1 个心愿
   - 创建 1 个儿童用户 + PIN
   - 创建 1 个家务模板

2. 修改 `.github/workflows/ci.yml`：
   ```yaml
   - name: Seed E2E data
     run: bash tests/seed-e2e-data.sh

   - name: Run Playwright tests
     working-directory: tests
     run: npx playwright test
   ```

3. 修复现有 5 个 spec 文件中的失败测试（如果有）

**验收标准：**
- CI e2e job 通过，所有现有 spec 文件绿色
- Playwright HTML report 上传到 GitHub Actions artifacts

---

#### Phase 2: 扩展 E2E 覆盖率（3-5天）

**目标：** 覆盖核心用户流程和儿童系统

**新增 spec 文件：**

1. **`chore-approval-flow.spec.ts`** — 家务审批流程
   - 父母创建家务模板
   - 儿童标记完成
   - 父母审批
   - 验证星星币到账

2. **`wish-fulfillment-flow.spec.ts`** — 心愿兑现流程
   - 儿童创建心愿
   - 父母审批心愿
   - 儿童请求兑现
   - 父母兑现
   - 验证星星币扣减

3. **`child-milestone-flow.spec.ts`** — 里程碑触发
   - 儿童完成第一个家务 → first_chore 里程碑
   - 连续 7 天 → streak_7 里程碑
   - 验证庆典弹窗显示

4. **`child-navigation.spec.ts`** — 儿童路由守卫
   - 儿童登录后只能访问 `/child/*`
   - 尝试访问 `/assets` 重定向到 `/child/`
   - 父母登录后不能访问 `/child/*`（除了管理页面）

**验收标准：**
- 新增 4 个 spec 文件，每个文件 3-5 个测试用例
- CI 通过，覆盖率报告显示核心流程已覆盖

---

#### Phase 3: Per-route Isolation（可选，2-3天）

**目标：** 每个测试独立种子数据，避免测试间干扰

**实施：**
- 将 `seed-e2e-data.sh` 拆分为可复用的 fixture 函数
- 每个 spec 文件在 `test.beforeEach()` 中调用所需 fixture
- 使用 Playwright 的 `storageState` 机制复用登录状态

**验收标准：**
- 测试可以并行运行（`workers: 4`）
- 单个测试失败不影响其他测试

---

## 方向二：儿童系统完善 (#5-8)

### 现状分析

**已实现（#1-4）：**
- 儿童身份系统（PIN 认证、`/child/*` 路由）
- 核心赚取循环（家务模板、审批队列、星星币账本）
- 心愿兑现流水线
- 连续打卡与里程碑庆典

**未实现（#5-8）：**
- #5: 我的宝贝画廊（`ChildTreasuresPage.vue` 名字对了但内容是账本）
- #6: 亲子双视角仪表盘
- #7: 兄弟姐妹积分赠送
- #8: 金银铜星星币视觉体系

### 实施计划

#### Feature #5: 我的宝贝画廊（2-3天）

**问题：** `ChildTreasuresPage.vue` 当前显示的是星星币交易账本，不是资产画廊

**方案：**
1. 重命名 `ChildTreasuresPage.vue` → `ChildLedgerPage.vue`
2. 更新路由：`/child/treasures` → `/child/ledger`
3. 创建新的 `ChildTreasuresPage.vue`，显示：
   - 通过心愿兑现获得的资产（`Asset.user_id == child_user_id`）
   - 视觉网格布局（非表格）
   - 每件物品显示：照片、名称、获得日期、花费星星币数
   - 底部汇总："你已经赚到了 X 件宝贝，共花费 Y 颗星！"

**数据模型变更：**
- 无需新增字段，通过 `Asset.user_id` 过滤即可
- 需要关联 `CoinTransaction` 查询花费的星星币数（`transaction_type='wish_spend'`, `ref_id=wish_id`）

**API 端点：**
- `GET /api/v1/child/treasures` — 返回儿童赚取的资产列表 + 每件花费的星星币

**验收标准：**
- 儿童登录后，`/child/treasures` 显示资产画廊
- 点击资产可查看大图
- 汇总数据正确

---

#### Feature #6: 亲子双视角仪表盘（3-4天）

**目标：** 同一数据，两种视角

**儿童视角（`ChildHomePage.vue` 增强）：**
- 储蓄罐（当前积分/目标心愿）
- 今日家务列表（待完成/已完成）
- 连续打卡火焰（streak badge）
- "我的宝贝"入口

**父母视角（新建 `ParentChildDashboard.vue`）：**
- 家务完成率（本周/本月）
- 待审批队列（红点提示）
- 各孩子积分余额
- 心愿进度（距离目标还差多少）
- 一键奖励积分（附原因备注）
- 积分倍率调节（1x/1.5x/2x，用于"双倍星星周末"）

**数据模型变更：**
- `Family` 表新增 `coin_rate_multiplier` 字段（DECIMAL, default 1.0）
- `CoinTransaction` 表新增 `rate_multiplier` 字段（记录交易时的倍率）

**API 端点：**
- `GET /api/v1/family/children/dashboard` — 父母视角聚合数据
- `POST /api/v1/family/children/{child_id}/grant-coins` — 一键奖励
- `PUT /api/v1/family/coin-rate-multiplier` — 调节倍率

**验收标准：**
- 父母可以在仪表盘看到所有孩子的数据
- 一键奖励功能正常
- 倍率调节后，新的家务奖励按新倍率计算

---

#### Feature #7: 兄弟姐妹积分赠送（2-3天）

**目标：** 同一家庭内的孩子可以互相赠送星星币

**流程：**
1. 儿童 A 选择兄弟姐妹 B
2. 输入赠送数量（不超过余额）
3. 添加表情符号原因（如 "🎁 生日快乐"）
4. 立即到账

**数据模型变更：**
- `CoinTransaction` 表新增 `transaction_type='gift'`
- 新增 `from_user_id` 字段（nullable，仅 gift 类型使用）
- 现有 `child_user_id` 字段作为接收方

**API 端点：**
- `POST /api/v1/child/gift-coins` — 赠送星星币
  - Request: `{ to_child_id, amount, emoji_reason }`
  - 验证：余额充足、同一家庭、不能赠送给自己

**父母监督：**
- `GET /api/v1/family/children/gift-history` — 查看所有赠送记录
- 父母可以在仪表盘看到赠送统计

**验收标准：**
- 儿童可以赠送星星币给兄弟姐妹
- 赠送记录在账本中显示
- 父母可以查看赠送历史

---

#### Feature #8: 金银铜星星币视觉体系（3-4天）

**目标：** 三级硬币视觉系统，让积分更有实体感

**视觉设计：**
- 铜星币（基础单位）：橙铜色，圆形，侧面倾斜，正面五角星
- 银星币：银灰色，金属光泽
- 金星币：金黄色，最高光泽

**兑换比例：**
- 10 铜 = 1 银
- 10 银 = 1 金
- 1 铜 = 1 分钱（100 铜 = 1 元）

**数据模型变更：**
- `Family` 表新增：
  - `coin_copper_to_silver_rate` (INTEGER, default 10)
  - `coin_silver_to_gold_rate` (INTEGER, default 10)
  - `coin_copper_to_cent_rate` (INTEGER, default 1)

**前端实现：**
1. 创建 3 个 SVG 硬币图标（`CopperCoin.vue`, `SilverCoin.vue`, `GoldenCoin.vue`）
2. 创建 `CoinDisplay.vue` 组件：
   - 输入：总铜币数
   - 输出：金银铜组合显示（如 "2金 3银 5铜"）
3. 在所有显示积分的地方使用 `CoinDisplay` 组件

**验收标准：**
- 所有积分显示都使用金银铜组合
- 硬币图标在储蓄罐动画中使用
- 兑换比例可配置

---

## 方向三：Module Tooling 细节补充

### 现状分析

**已实现：**
- ESLint v10.2.0 + Prettier v3.8.2（frontend）
- ruff v0.9.0 + mypy v1.13.0（backend + agent）
- 所有 CLAUDE.md 文件存在且内容完整

**可优化点：**
1. CLAUDE.md 中缺少"常见陷阱"章节
2. ESLint/Prettier 配置可能需要微调（根据实际使用反馈）
3. mypy 配置中 `ignore_missing_imports=true` 过于宽松

### 实施计划（可选，1-2天）

#### 增强 CLAUDE.md 内容

**frontend/CLAUDE.md 新增章节：**
```markdown
## Common Pitfalls

- **Vant `van-field` with computed values:** Use `:model-value` not `:value`
- **Child PIN auth:** Must use bcrypt dummy hash for timing attack protection
- **httpOnly cookies in tests:** TestClient auto-handles, no manual cookie management needed
```

**backend/CLAUDE.md 新增章节：**
```markdown
## Common Pitfalls

- **SQLAlchemy session in tests:** Use `db` fixture, not `TestingSessionLocal()`
- **JWT priority:** Bearer token takes precedence over Cookie (security fix 2026-04-17)
- **Milestone unique constraint:** Removed in migration e5f6a7b8c9d0, streak milestones can re-trigger
```

#### 优化 mypy 配置（可选）

**backend/pyproject.toml:**
```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # 渐进式启用
ignore_missing_imports = false  # 改为 false，逐个模块添加 [[tool.mypy.overrides]]
```

**验收标准：**
- CLAUDE.md 内容更新
- mypy 配置优化后，`uv run mypy app/` 仍然通过

---

## 实施优先级建议

### 并行推进策略

**Week 1（高优先级）：**
- **Day 1-2:** Regression Testing Phase 1（启用现有 E2E 测试）
- **Day 1-3:** 儿童系统 Feature #5（我的宝贝画廊）
- **Day 3:** Module Tooling 细节补充（如果有时间）

**Week 2（中优先级）：**
- **Day 1-3:** Regression Testing Phase 2（扩展 E2E 覆盖率）
- **Day 1-4:** 儿童系统 Feature #6（亲子双视角仪表盘）

**Week 3（低优先级）：**
- **Day 1-3:** 儿童系统 Feature #7（兄弟姐妹赠送）
- **Day 4-5:** 儿童系统 Feature #8（金银铜硬币）
- **Day 5:** Regression Testing Phase 3（Per-route Isolation，可选）

### 依赖关系

- Feature #6 依赖 Feature #5（父母仪表盘需要显示"我的宝贝"统计）
- Feature #8 可以独立实施，但最好在 Feature #5-7 之后（视觉升级）
- Regression Testing 可以完全并行，不依赖儿童系统功能

---

## 风险与缓解

### 风险 1: E2E 测试在 CI 中不稳定

**缓解：**
- 使用 `test.setTimeout(30_000)` 增加超时
- 使用 `await expect().toBeVisible({ timeout: 10_000 })` 等待元素
- 使用 `test.retry(2)` 自动重试

### 风险 2: 儿童系统功能复杂度超预期

**缓解：**
- 每个 Feature 独立交付，可以分阶段上线
- Feature #8（金银铜硬币）可以延后，不影响核心功能

### 风险 3: 数据库迁移失败

**缓解：**
- 所有新增字段都设置 `nullable=True` 或 `server_default`
- 在 dev 环境充分测试后再合并到 main

---

## 验收标准总结

### Regression Testing
- [ ] CI e2e job 启用并通过
- [ ] 至少 9 个 spec 文件（5 个现有 + 4 个新增）
- [ ] 核心流程覆盖：家务审批、心愿兑现、里程碑、儿童路由守卫

### 儿童系统 #5-8
- [ ] Feature #5: 我的宝贝画廊正常显示
- [ ] Feature #6: 父母仪表盘 + 一键奖励 + 倍率调节
- [ ] Feature #7: 兄弟姐妹赠送功能
- [ ] Feature #8: 金银铜硬币视觉系统

### Module Tooling
- [ ] CLAUDE.md 内容增强（Common Pitfalls 章节）
- [ ] mypy 配置优化（可选）

---

## 下一步行动

1. **用户确认优先级** — 是否按照 Week 1-3 的顺序实施？
2. **创建 brainstorm 文档** — 为每个 Feature 创建详细需求文档
3. **开始实施** — 从 Regression Testing Phase 1 + Feature #5 开始

---

## 参考文档

- Ideation: `docs/ideation/2026-04-14-children-starcoin-ideation.md`
- Ideation: `docs/ideation/2026-04-14-regression-testing-ideation.md`
- Ideation: `docs/ideation/2026-04-11-module-tooling-ideation.md`
- 已实现 Plans: `docs/plans/2026-04-14-003-feat-child-identity-system-plan.md`, `2026-04-15-001-feat-core-earn-loop-plan.md`, `2026-04-16-004-feat-streak-milestone-plan.md`
