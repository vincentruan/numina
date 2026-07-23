# Numina UI Audit — 2026-05-21

## Summary
- Screenshots captured: 11 (adult: 5, child: 6)
- API tests: 23/23 passed (100%)
- Console errors: 0
- Issues found: 2 total (P0: 0, P1: 0, P2: 0, P3: 2)

## Test Accounts Verified

| Account | Role | Frontend | Status |
|---------|------|----------|--------|
| demouser | Admin | Adult | ✓ All pages working |
| xiaobao (小宝) | Child | Child | ✓ All pages working |
| test_child (xiaoming) | Child | Child | ✓ All pages working |

## Adult Frontend (demouser)

### Dashboard (总览)
- ✓ Total assets: ¥653.88万, net worth: ¥465.58万, liabilities: ¥188.30万
- ✓ 30 assets listed with category tabs
- ✓ Daily cost calculation visible (日均 ¥2,681)
- ✓ "提醒即将到期" notification badge working

### Wishes (心愿)
- ✓ Priority badges (高优先/中优先/低优先)
- ✓ Affordability indicators (净资产可负担)
- ✓ Sorting options available

### Liabilities (负债)
- ✓ "消费贷" category label correctly displayed (fix verified)
- ✓ 7 liabilities showing with progress bars
- ✓ Monthly payment and interest rate visible

### Baby (宝贝)
- ✓ Children cards with coin balances (350 ⭐)
- ✓ Weekly chore progress tracker
- ✓ Calendar view for activity tracking

### Settings (设置)
- ✓ All settings sections accessible
- ✓ Theme, language, currency options
- ✓ AI assistant configuration
- ✓ Family management links

## Child Frontend (xiaobao & test_child)

### Home (首页)
- ✓ Coin balance displayed prominently
- ✓ Today's tasks with completion status
- ✓ Wish progress card visible
- ✓ Calendar with activity stats

### Wishes (心愿)
- ✓ Progress bars with percentage
- ✓ "让爸妈实现" button for completed wishes
- ✓ Status sections (进行中/审核中)
- ✓ Empty state for treasures page appropriate

### Tasks (任务)
- ✓ Date navigation (前一天/后一天)
- ✓ Task cards with coin rewards
- ✓ "认领" and "完成" buttons
- ✓ Completion badges (已获得)

### Treasures (宝藏)
- ✓ Empty state message appropriate

### Ledger (账本)
- ✓ Coin balance with transaction history
- ✓ "送给兄弟姐妹" gift button

## P0 — Critical Issues
None found.

## P1 — Major UX Issues
None found.

## P2 — Minor Polish
None found.

### ~~[Child frontend access flow]~~ — 设计如预期，非 bug

经过认证和路由架构的完整分析，确认当前行为是正确的设计：

**儿童端是独立身份系统**，不是成人端的"子视图"。认证流程如下：
1. 用户在统一登录页输入 username + password → `POST /auth/login/step1`
2. 后端根据 `user.role` 决定二阶段验证类型：
   - `child` + 有 `pin_hash` → 返回 `second_factor_type: "emoji_pin"`
   - `adult` + 有 2FA → 返回 `second_factor_type: "numeric_pin"`
   - 无二阶段 → 直接签发 token
3. 前端 LoginPage 根据 `second_factor_type` 自动切换到对应的二阶段 UI（emoji 图形密码 / 数字密码）
4. 验证通过后，根据已知 role 直接路由：child → `/child/`，adult → `/`

**Adult 访问 `/child/` 被正确拒绝的原因：**
- Adult SPA router 拦截 `/child/*` 路径 → `window.location.replace('/child/')` 全页面刷新
- Nginx 代理到 child SPA 容器
- Child SPA `beforeEach` 检查 `getUser().role !== 'child'` → 重定向回 `/login`
- Adult 已登录，LoginPage guest 守卫将已登录 adult 跳转到 `/`（dashboard）

**结论：** 登录页不需要"进入儿童端"入口。儿童通过统一 LoginPage 用自己的账号登录，一阶段后系统自动识别角色并展示对应的二阶段界面。如果将来需要"家长切换到儿童视角"功能，应作为新功能需求单独设计（如 `POST /auth/child/{childId}/switch`），而非修改当前认证流程。

## P3 — Nice-to-Have

### [Skill documentation PIN mismatch]
- **Page**: Documentation (`numina-sim-test` skill)
- **Component**: Child account test credentials
- **Issue**: Skill documentation中的 PIN 值与实际 seed data 不一致：
  - 小宝 (xiaobao): skill 写的 🐰🥕🌈⭐，实际 seed 是 🐱🐶🌟🌈
  - 大宝 (dabao): skill 写的 🐰🥕🌈⭐，实际 seed 是 🦊🐼🦁🐯
  - test_child: skill 写的 username 是 `testchild`，实际 seed 是 `xiaoming`
- **Root cause**: Skill 文档编写时使用了占位符值，未与 `tests/data/scenarios/demo.py` 和 `tests/data/scenarios/full.py` 中的实际值同步
- **Fix**: 更新 `numina-sim-test` skill 文档中的 PIN 和 username 值，使其与 seed data 保持一致
- **Effort**: S

### [Child treasures empty state illustration]
- **Page**: Child treasures page (`/child/treasures`)
- **Component**: ChildTreasuresPage.vue empty state
- **Issue**: 空状态仅显示文字提示「还没有宝贝，快去完成家务赚星星币吧！」和一个 🎁 emoji。对于儿童用户，可以增加一个有趣的插图或动画来提升参与感
- **Root cause**: 当前使用了最简设计（emoji + 文字），没有自定义插图
- **Fix**: 为 ChildTreasuresPage 的空状态添加一个宝箱插图（SVG 或 Lottie 动画），保持 Clay 设计系统风格
- **Effort**: S

## Deployment Verification

| Service | Status | Health Check |
|---------|--------|--------------|
| nginx | UP | ✓ |
| backend | UP | ✓ (healthy) |
| agent | UP | ✓ (healthy) |
| frontend-main | UP | ✓ |
| frontend-child | UP | ✓ |
| scheduler_worker | UP | ✓ (healthy) |

## Fix Verified

The `consumer_loan` category label fix (commit cd39a61) is confirmed working:
- Liabilities page shows "消费贷" category correctly
- i18n key `category.consumer_loan` = "消费贷" is applied
- No missing category labels observed

## Recommendations

1. **Skill 文档同步**: 更新 `numina-sim-test` skill 中的测试账号信息，使其与 seed data 保持一致：
   - xiaobao (小宝): PIN 为 🐱🐶🌟🌈（非 🐰🥕🌈⭐）
   - dabao (大宝): PIN 为 🦊🐼🦁🐯（非 🐰🥕🌈⭐）
   - test_child: username 为 `xiaoming`（非 `testchild`），PIN 为 🐱🐶🐸🦊

2. **儿童端空状态优化**: 为 ChildTreasuresPage 等空状态页面添加趣味插图，提升儿童用户体验

3. **可选新功能 — 家长视角切换**: 如果产品需要 adult 用户能切换到儿童视角（parent mode → child mode），建议设计独立的 API（如 `POST /auth/child/{childId}/switch`），在 adult 端"宝贝"页面增加"进入儿童视角"入口，而非修改现有统一登录流程