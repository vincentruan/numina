# Child Frontend Issues Report

**Date:** 2026-04-28  
**Branch:** feat/child-frontend-module-split  
**Tester:** Kiro (automated browser testing via Chrome DevTools MCP)

---

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
