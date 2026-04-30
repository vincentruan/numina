# Numina UI/UX 审计报告 — 2026-04-30

**测试视口**: 375×812 (iPhone 标准移动端)  
**成人前端设计系统**: Cohere (白色画布, 近黑色 pill CTA, coral 强调色)  
**儿童前端设计系统**: Clay (奶油色画布 #fffaf0, 饱和特色卡片, 圆润风格)  
**截图数量**: 11 张  
**发现问题**: 11 项 (P0: 2, P1: 4, P2: 3, P3: 2)

---

## P0 — 严重问题 (阻断功能)

### P0-1: 儿童前端登录页无法登录儿童账号

- **页面**: `/child/auth`
- **组件**: `ChildAuthPage.vue` — `onStep1Submit()`
- **问题**: 登录页使用 `/auth/login/step1` (成人账号端点，需要用户名+密码)。儿童账号 (xiaobao/dabao) 没有密码，只有 emoji PIN。用成人账号 (demouser) 登录后，router guard 检测到 `role !== 'child'` 会重定向回 `/auth`，造成死循环。儿童账号输入用户名+任意密码会返回 `AUTH_INVALID_CREDENTIALS`。
- **根因**: `ChildAuthPage.vue` 只调用 `childLoginStep1(username, password)`，但 `childAuth` store 中已有 `childLogin(child, pin)` 方法调用正确的 `/auth/child/login` 端点，却从未在 UI 中使用。
- **修复**: 将 step1 改为只输入用户名，跳过密码字段，直接进入 PIN 输入界面，调用 `childLogin()` 而非 `childLoginStep1()`。
- **影响**: 儿童完全无法通过正常 UI 登录儿童前端
- **工作量**: M

### P0-2: 儿童首页快捷链接路径重复 (`/child/child/wishes`)

- **页面**: `/child/` (ChildHomePage)
- **组件**: `ChildHomePage.vue` — 快捷链接区域
- **问题**: 快捷链接 href 为 `http://localhost/child/child/wishes`、`/child/child/tasks` 等，路径中 `/child/` 重复了两次。点击后会 404 或跳转到错误路由。
- **根因**: 链接硬编码了 `/child/` 前缀，但 Vue Router 的 `BASE_URL` 已经是 `/child/`，导致双重前缀。
- **修复**: 将链接改为相对路径 (`/wishes`, `/tasks`) 或使用 `router-link :to="{ name: 'ChildWishes' }"`
- **影响**: 首页所有快捷入口点击后跳转失败
- **工作量**: S

---

## P1 — 主要 UX 问题

### P1-1: 儿童前端所有 API 请求返回 401

- **页面**: 所有儿童页面
- **组件**: axios 实例 / `configureAuthHttp()` 配置
- **问题**: 儿童前端所有 API 请求 (`/child/coins/balance`、`/child/chores`、`/child/wishes`、`/child/calendar`) 均返回 401，导致所有数据为空，星星币余额显示 0，任务显示"加载失败"。
- **根因**: 儿童前端 axios 实例可能未配置 `withCredentials: true`，或 `configureAuthHttp()` 在 child app `main.ts` 中未正确调用，导致 Cookie 未随请求发送。
- **修复**: 检查 `frontend/apps/child/src/` 中 axios 实例是否有 `withCredentials: true`；确认 `main.ts` 中 `configureAuthHttp()` 调用正确。
- **影响**: 儿童前端所有功能数据为空
- **工作量**: S

### P1-2: 儿童任务页错误提示对儿童不友好

- **页面**: `/child/tasks`
- **组件**: `ChildTasksPage.vue` — 错误状态
- **问题**: 因 401 错误，任务页显示 `❌ 加载失败，请刷新重试`。对儿童用户来说过于技术性，且没有重试按钮。
- **修复**: 先修复 P1-1；错误状态改为更友好的提示，加上重试按钮，使用 Clay 设计系统的 feature-card-coral 样式。
- **工作量**: S

### P1-3: 成人前端宝贝页儿童卡片信息不完整

- **页面**: `/baby`
- **组件**: `BabyPage.vue`
- **问题**: 宝贝页只显示汇总数字 (余额 140⭐, 进行中心愿 2)，没有儿童头像、用户名、详细信息卡片。心愿列表只有名称和状态，缺少 emoji、优先级、金额。
- **设计系统对照 (Cohere)**: 应使用 `product-card` (soft-stone 背景 #eeece7, 8px 圆角) 展示每个儿童的完整信息卡片。
- **修复**: 补充儿童卡片的头像、用户名、余额展示；心愿列表补充 emoji 和金额字段。
- **工作量**: M

### P1-4: 成人前端负债页类型筛选按钮不符合 Cohere 设计系统

- **页面**: `/liabilities`
- **组件**: 类型筛选按钮 (全部/房贷/车贷/信用卡/个人贷款/其他)
- **问题**: 筛选按钮使用 Vant 默认样式，不符合 Cohere 的 `button-pill-outline` 规范 (透明背景, 1px 深色边框, 30px pill 圆角)。
- **设计系统对照 (Cohere)**: 应使用 `button-pill-outline`: `border-radius: 30px; border: 1px solid var(--color-primary); background: transparent`
- **工作量**: S

---

## P2 — 轻微打磨问题

### P2-1: 儿童前端底部导航栏图标未显示

- **页面**: 所有儿童页面
- **组件**: `ChildLayout.vue` — 底部 tab bar
- **问题**: 底部导航标签文字前有空白字符 (` 首页`, ` 心愿` 等)，图标未渲染，显示为空白方块。
- **设计系统对照 (Clay)**: 导航图标应清晰可见，符合 44px 最小触控目标。
- **修复**: 检查 Vant icon 名称是否正确，或改用 emoji 图标作为备选。
- **工作量**: S

### P2-2: 成人前端资产列表重复数据无视觉区分

- **页面**: `/` (Dashboard)
- **组件**: 资产列表
- **问题**: "测试房产"出现 4 次，"买新车"/"换新房"各出现多次。UI 没有去重提示或分组，列表视觉混乱。
- **修复**: seed 脚本层面去重；UI 层可按名称分组或添加序号区分同名资产。
- **工作量**: S (数据) / M (UI 分组)

### P2-3: 儿童前端星星币图标不统一 (★ vs ⭐)

- **页面**: `/child/` 和 `/child/ledger`
- **组件**: 星星币余额显示
- **问题**: 儿童端使用 `★` (字符)，成人端宝贝页使用 `⭐` (emoji)，两处不一致，且 `★` 在小字号下可读性差。
- **修复**: 统一改为 `⭐` emoji。
- **工作量**: XS

---

## P3 — 优化建议

### P3-1: 儿童前端空状态缺少 Clay 风格插画

- **页面**: `/child/wishes`, `/child/treasures`, `/child/ledger`
- **问题**: 空状态只有单个 emoji + 文字，缺少 Clay 设计系统的 3D 黏土风格插画，对儿童用户视觉吸引力不足。
- **修复**: 添加 SVG 或 Lottie 动画插画到空状态区域。
- **工作量**: L

### P3-2: 成人前端心愿页排序按钮可改为 Cohere category-tab 样式

- **页面**: `/wishes`
- **问题**: 排序按钮 (按优先级/按价格/按名称) 使用普通按钮样式，不符合 Cohere `category-tab` 规范 (pill 形状, 激活态 soft-stone 背景)。
- **修复**: 改为 `category-tab` + `category-tab-active` 样式。
- **工作量**: S

---

## API 测试结果

- seed-data.sh: ✅ 成功 (所有测试账号创建完成)
- 成人前端 API: ✅ 正常 (demouser 登录后所有请求 200)
- 儿童前端 API: ❌ 全部 401 (见 P1-1)

---

## 设计系统合规性总结

### 成人前端 (Cohere)

| 维度 | 状态 | 备注 |
|------|------|------|
| 白色画布 (#ffffff) | ✅ | 正确 |
| 近黑色主色 (#17171c) | ⚠️ | 部分按钮仍用 Vant 蓝色默认色 |
| Pill 形 CTA 按钮 | ⚠️ | 筛选按钮圆角不足 (P1-4) |
| Coral 强调色 | ✅ | 状态标签使用正确 |
| 8px 卡片圆角 | ✅ | 资产卡片符合 |
| 移动端 375px 单列布局 | ✅ | 无溢出 |
| 最小触控目标 44px | ✅ | 主要按钮符合 |

### 儿童前端 (Clay)

| 维度 | 状态 | 备注 |
|------|------|------|
| 奶油色画布 (#fffaf0) | ✅ | 正确 |
| 饱和特色卡片 | ⚠️ | 首页快捷入口未使用 feature-card 变体 |
| 圆润边框 (pill/xl) | ✅ | 按钮和卡片圆角符合 |
| 底部导航图标 | ❌ | 图标未显示 (P2-1) |
| 移动端 375px 布局 | ✅ | 无溢出 |
| 儿童友好字体大小 | ✅ | 字号适合儿童阅读 |

---

## 修复优先级建议

**立即修复 (本 sprint)**:
- P0-1: 儿童登录流程 — 改用 `childLogin()` + PIN 输入
- P0-2: 首页快捷链接路径重复
- P1-1: 儿童前端 axios `withCredentials` 配置

**下个 sprint**:
- P1-2: 任务页错误状态友好化
- P1-3: 宝贝页儿童卡片完善
- P1-4: 负债页筛选按钮样式
- P2-1: 底部导航图标修复
- P2-3: 星星币图标统一

**后续迭代**:
- P3-1: 空状态插画
- P3-2: 心愿排序按钮样式

---

## 历史问题记录 (2026-04-28)

## Issue #1 — ChildSelectPage 渲染空白（名字/用户名不显示）

### 问题描述
访问 `http://localhost/child/select` 时，子卡片显示 `?` 头像和空名字、`@` 用户名，而非实际的 `小宝`/`大宝`。

### 根因分析
`frontend/apps/child/src/api/children.ts` 中的 `listChildren()` 和 `getFamilyChildren()` 直接返回 `res.data`，而 axios 的 `res.data` 是完整的 JSON 响应体 `{code: "OK", message: "", data: [...]}` 而非数组本身。

`ChildSelectPage.vue` 用 `v-for="child in children"` 遍历这个对象，Vue 会把对象的 key（`code`、`message`、`data`）当作迭代项，每项都没有 `display_name` 或 `username` 字段，所以显示空值。`?` 是 `(child.display_name ?? '?').charAt(0)` 的兜底值，`@` 是 `@{{ child.username }}` 中 username 为 undefined 时的结果。

**证据：**
- API `GET /api/v1/family/children` 返回 200，响应体正确：`{"code":"OK","data":[{"display_name":"小宝",...},{"display_name":"大宝",...}]}`
- DOM 检查：3 张卡片（对应 code/message/data 三个 key），name 和 username 均为空

### 修复建议
在 `frontend/apps/child/src/api/children.ts` 中，将两个函数的返回值改为解包 `.data` 层：

```ts
// 修复前
return res.data

// 修复后
return res.data?.data ?? res.data
```

涉及函数：`listChildren()`、`getFamilyChildren()`

同时建议在 `src/api/index.ts` 的 axios 实例中添加响应拦截器统一解包，避免其他 API 函数出现同类问题：

```ts
http.interceptors.response.use(
  (response) => response.data?.data !== undefined ? { ...response, data: response.data.data } : response,
  (error) => Promise.reject(error),
)
```

### 优先级
**P0 — 阻断性**。ChildSelectPage 是儿童登录流程的入口，此 bug 导致所有儿童账号无法选择，整个 child SPA 不可用。

---

## Issue #2 — 代码路径不一致（frontend-child/ vs frontend/apps/child/）

### 问题描述
本次 branch 的 git diff 显示，child frontend 源码已从 `frontend-child/` 迁移到 `frontend/apps/child/`，但迁移过程中产生了两套代码共存的混乱状态：

- `frontend-child/` 目录在 git diff 中被删除（`frontend-child/Dockerfile` 已移除）
- 实际运行的 Docker 容器 `numina-frontend-child` 使用的是哪个路径的构建产物不明确
- 本次 dogfood 测试中，修复 `ChildSelectPage` 和 `ChildAuthPage` 的 null guard 最初错误地应用到了已不存在的 `frontend-child/src/pages/` 路径

### 根因分析
分支 `feat/child-frontend-module-split` 正在进行 monorepo 重构，将 `frontend-child/` 移入 `frontend/apps/child/`，同时将 `frontend/` 移入 `frontend/apps/main/`，并将 `packages/auth/` 移入 `frontend/packages/auth/`。

重构尚未完全落地（branch 仍在进行中），导致：
1. `docker-compose.yml` 的 build context 指向新路径，但旧路径文件可能仍存在于工作区
2. 测试/文档中的路径引用可能仍指向旧位置

### 修复建议
1. 确认并清理旧路径残留文件（`frontend-child/`、`frontend/src/`、`packages/auth/`）
2. 更新所有文档、CI 配置、CLAUDE.md 中的路径引用
3. 在 PR 描述中明确标注路径变更，避免后续 reviewer 混淆
4. 考虑在 `pnpm-workspace.yaml` 中添加注释说明新的 workspace 结构

### 优先级
**P1 — 高**。路径混乱会导致开发者修改错误文件、构建产物不一致，是持续集成的隐患。

---

## Issue #3 — 认证状态不一致（Cookie vs localStorage）

### 问题描述
Child SPA 的 `ChildSelectPage` 通过 `getChildFamilyId()` 读取 `localStorage` 中的 `numina_child_family_id` 来决定调用哪个 API。但当用户从 adult frontend 跳转到 child SPA 时，adult 的认证信息存储在 **Cookie**（`access_token`、`refresh_token`），而 `numina_child_family_id` 从未被写入 localStorage，导致 `getChildFamilyId()` 始终返回 `null`。

**实际执行路径：**
```
getChildFamilyId() → null
→ 走 listChildren() → GET /family/children
→ 使用 adult cookie 认证 → 返回正确数据
→ 但 res.data 解包错误（见 Issue #1）
```

**潜在问题路径（Issue #1 修复后）：**
- 若用户直接访问 `/child/` 而未经过 adult 登录，Cookie 中无 adult token，`/family/children` 会返回 401，children 列表为空，显示"暂无孩子账号"

### 根因分析
`getChildFamilyId()` 的设计意图是：child SPA 在独立部署场景下，通过 bind token 流程将 family_id 存入 localStorage，供后续无 adult session 时使用。但当前 seed data 和测试流程都是通过 adult session 直接访问 `/child/`，没有经过 bind 流程，所以 localStorage 中没有 family_id。

两条代码路径（有 family_id / 无 family_id）的行为差异未在 UI 上体现，用户无法感知。

### 修复建议
1. **短期**：在 `ChildSelectPage` 的 catch 块中增加错误提示，当 `/family/children` 返回 401 时引导用户返回 adult 登录页
2. **中期**：adult frontend 在跳转到 `/child/` 时，将当前用户的 `family_id` 写入 localStorage（`setChildFamilyId`），确保两条路径都能正常工作
3. **长期**：统一认证状态存储策略，明确文档说明 child SPA 的两种使用场景（embedded via adult session / standalone via bind token）

### 优先级
**P1 — 高**。当前靠 adult Cookie 兜底可以工作，但这是隐式依赖，任何 Cookie 失效或跨域场景都会导致静默失败。

---

## Issue #4 — 其他 API 函数可能存在同类解包问题

### 问题描述
`children.ts` 中的 `listChildren()` / `getFamilyChildren()` 存在 `res.data` 未解包问题（Issue #1）。其他 API 文件（如 `family.ts`）返回的是原始 axios response 对象（不调用 `.data`），由调用方自行处理。这两种模式在同一个 codebase 中混用，容易引入新的解包错误。

### 根因分析
`children.ts` 的写法与其他 API 文件不一致：
- `family.ts`：`return http.get(...)` — 返回 axios response，调用方用 `res.data`
- `children.ts`：`return res.data` — 提前解包，但解包层数不够

### 修复建议
统一 API 层的返回约定，二选一：
- **方案 A**：所有函数返回 axios response，调用方统一处理 `res.data.data`
- **方案 B**：所有函数返回完全解包的数据（`res.data.data`），在 axios 拦截器中统一处理

建议选方案 B，在 `src/api/index.ts` 添加响应拦截器，一次性解决所有 API 函数的解包问题。

### 优先级
**P2 — 中**。当前只有 `children.ts` 确认有问题，但其他文件存在潜在风险，建议在修复 Issue #1 时一并处理。

---

## 已验证正常的功能

| 功能 | 状态 | 备注 |
|------|------|------|
| nginx `/child/` 路由 | ✅ | proxy_pass 前缀剥离正确 |
| Child SPA 资源加载 | ✅ | JS/CSS 均 200 |
| `/family/children` API | ✅ | 返回正确的儿童数据 |
| adult frontend 认证 | ✅ | Cookie 正常传递到 child SPA |
| null display_name 兜底 | ✅ | `?? '?'` guard 生效 |
| Docker 构建 | ✅ | frontend-child 容器正常运行 |

---

## 修复优先级汇总

| # | 问题 | 优先级 | 影响范围 |
|---|------|--------|---------|
| 1 | ChildSelectPage 渲染空白 | **P0** | 儿童登录流程完全不可用 |
| 2 | 代码路径不一致 | **P1** | 开发效率、构建可靠性 |
| 3 | 认证状态隐式依赖 | **P1** | 独立部署场景静默失败 |
| 4 | API 解包约定不统一 | **P2** | 潜在的同类 bug 风险 |
