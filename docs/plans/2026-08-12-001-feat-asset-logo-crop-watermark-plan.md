---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
created: 2026-08-12
scope: Standard — frontend feature enhancement
---

# 资产详情页 Logo 上传、裁剪与水印交互增强 - Plan

## Goal Capsule

| Field | Value |
|-------|-------|
| **Objective** | 改造资产表单的图片上传区域，实现「选择→裁剪→水印→上传」完整链路；编辑态点击图片弹出 ActionSheet 菜单提供查看/重裁/替换/删除四选项 |
| **Product authority** | 用户提供的 PRD（验收标准 AC-1 ~ AC-6） |
| **Active scope** | 前端 `AssetForm.vue` 图片上传区域改造、新建裁剪组件和水印引擎、字体加载 |
| **Out of scope** | 后端 API 变更、AssetDetailPage/AssetListItem 展示逻辑、Liability/Wish 表单 |
| **Open blockers** | 无 |

---

## Product Contract

**Product Contract unchanged** from brainstorm.

### Key Decisions

- **复用现有上传 API**：裁剪+水印后的 Blob 通过同一 `POST /upload/image` 端点上传，后端零改动。
- **cropperjs 为唯一新增依赖**：轻量（~30KB gzipped）、移动端手势原生支持、MIT 许可。
- **水印引擎纯 Canvas**：不引入额外图片处理库，利用 `html2canvas` 已验证的 Canvas 绘制经验。
- **Dancing Script 本地 `@font-face` 加载**：遵循项目惯例（ZCOOL KuaiLe 模式），woff2 文件放入 `public/fonts/`，通过 `@font-face` 在组件内加载。避免 Google Fonts CDN 依赖（国内访问不稳定）。
- **编辑态 ActionSheet 替代 van-uploader 默认行为**：阻止 van-uploader 的点击替换逻辑，改用 ActionSheet 菜单。
- **添加 `@oversize` 处理器**：当前 AssetForm 的 uploader 缺少 `@oversize` 事件处理（ImportReportPage 有），需补充以友好提示用户。

### Actors

| Actor | Description |
|-------|-------------|
| 成年用户（authenticated adult） | 资产的新增/编辑操作者，水印中的 `userName` 来源 |

### Flows

#### Flow 1: 新增资产 — 图片上传

1. 用户进入 `/assets/new`，看到 Vant 风格上传占位框（photograph 图标 + 提示文字）。
2. 点击占位框 → 唤起本地文件选择器。
3. 选择文件后 → **自动**打开裁剪弹窗（`LogoCropper`）。
4. 裁剪弹窗内：1:1 固定比例裁剪框、双指缩放、平移拖拽、90° 旋转、重置、取消/确定。
5. 点击确定 → Canvas 叠加水印（右下角：`操作人: {userName}` + `numina` 花体字）→ 导出 Blob。
6. Blob 通过 `uploadImage(blob)` 上传 → 返回 URL → 展示缩略图 + 设置 `form.image_url`。

#### Flow 2: 编辑资产 — 已有 Logo 交互

1. 用户进入 `/assets/:id/edit`，已有 Logo 显示为正方形缩略图。
2. 点击已有图片 → 弹出 `<van-action-sheet>` 菜单（4 选项：查看大图 / 重新裁剪 / 替换 / 删除）。

#### Flow 3: 水印叠加

1. 裁剪输出 Canvas 后，在同一 Canvas 右下角绘制水印（两行：userName + numina 花体字）。
2. `globalAlpha = 0.45`，Canvas 按图片原始像素分辨率绘制，导出 Blob（quality=0.92 JPEG）。

### Requirements

#### R1: 裁剪组件 (`LogoCropper.vue`)

基于 `cropperjs` 封装，`<van-popup>` 全屏弹出，1:1 比例，手势缩放/平移，90° 旋转，重置，取消/确定，`lock-scroll`，输出裁剪 Canvas。

#### R2: 水印引擎 (`useWatermark.ts`)

输入裁剪 Canvas + userName，右下角绘制两行水印（系统字体 + Dancing Script），`globalAlpha=0.45`，高分屏原始像素绘制，`document.fonts.ready` 字体就绪检测，输出 `toBlob()`。

#### R3: AssetForm.vue 改造

新增态拦截 `afterRead` 走裁剪；`@oversize` 提示；编辑态 `@click-preview` 弹 ActionSheet；CORS 处理远程图片；`accept` 匹配后端白名单。

#### R4: 字体加载

本地 `@font-face`（ZCOOL KuaiLe 模式），woff2 放入 `public/fonts/`，`font-display: swap`，`document.fonts.load()` 检测。

#### R5: 内存管理

`URL.revokeObjectURL()` 在弹窗关闭/组件卸载时释放；cropperjs `destroy()` 在弹窗关闭时调用。

#### R6: 容错

5MB 限制 + oversize 提示；Canvas 污染捕获 + toast；字体 3s 超时回退 `cursive`。

### Acceptance Criteria

| ID | Criterion | Verification |
|----|-----------|-------------|
| AC-1 | cropperjs 为唯一新依赖 | `package.json` diff |
| AC-2 | `/assets/new` 和 `/assets/:id/edit` 均生效 | 手动验证 |
| AC-3 | 选图→裁剪→水印→展示→上传成功 | E2E 手动验证 |
| AC-4 | 编辑态 ActionSheet 四选项正确 | 手动验证 |
| AC-5 | 水印清晰无模糊，numina 花体字 | 视觉检查 |
| AC-6 | 删除重置 + 超大文件拦截 + CORS 容错 | 边界测试 |

### i18n Keys (to add)

| Key | zh-CN | en-US |
|-----|-------|-------|
| `assetForm.cropTitle` | 裁剪图片 | Crop Image |
| `assetForm.cropConfirm` | 确定 | Confirm |
| `assetForm.cropCancel` | 取消 | Cancel |
| `assetForm.cropReset` | 重置 | Reset |
| `assetForm.cropRotate` | 旋转 | Rotate |
| `assetForm.actionViewFull` | 查看大图 | View Full Image |
| `assetForm.actionRecrop` | 重新裁剪/打水印 | Re-crop / Watermark |
| `assetForm.actionReplace` | 替换图片 | Replace Image |
| `assetForm.actionDelete` | 删除图片 | Delete Image |
| `assetForm.deleteConfirmMsg` | 确定要删除这张图片吗？ | Delete this image? |
| `assetForm.watermarkFailed` | 水印添加失败，请重试 | Watermark failed, please retry |
| `assetForm.corsError` | 图片加载失败，请重试 | Image load failed, please retry |
| `assetForm.fileTooLarge` | 文件超过大小限制（最大 5MB） | File too large (max 5MB) |

---

## Planning Contract

### Key Technical Decisions

#### KTD-1: cropperjs 直接集成（非 vue wrapper）

cropperjs 直接在 `LogoCropper.vue` 中初始化和销毁，不引入 `vue-cropperjs` 等 Vue wrapper。理由：wrapper 增加依赖但无实质价值（cropperjs API 简单，初始化/destroy 各一行），且 wrapper 可能滞后于上游版本。

#### KTD-2: LogoCropper 双入口模式

组件通过 `source` prop 接受两种输入：
- `File` 对象（新增/替换场景）→ `URL.createObjectURL()` 转为预览 URL
- `string` URL（重裁场景）→ 直接加载，设置 `crossOrigin = 'Anonymous'`

组件内部统一转为 image URL 供 cropperjs 使用。

#### KTD-3: 水印在 cropper getCroppedCanvas 输出上叠加

cropperjs 的 `getCroppedCanvas()` 返回裁剪结果 Canvas → 直接传入 `applyWatermark()` → 在同一 Canvas 上绘制水印 → `toBlob()` 导出。不需要额外的中间 Canvas。

#### KTD-4: ActionSheet 通过 @click-preview 拦截

Vant `van-uploader` 的 `@click-preview` 事件可以阻止默认行为（`event.preventDefault()` 或不再触发后续）。编辑态通过此事件拦截，改为显示 ActionSheet。新增态的 van-uploader 保持默认文件选择行为。

#### KTD-5: 替换图片通过隐藏 file input

编辑态 ActionSheet 的「替换图片」选项触发一个隐藏的 `<input type="file" accept="image/jpeg,image/png,image/webp">`，选择文件后进入裁剪流程。

### Scope Boundaries

#### In Scope
- `AssetForm.vue` 图片上传区域改造
- `LogoCropper.vue` 新组件
- `useWatermark.ts` 新 composable
- Dancing Script 字体文件 + `@font-face`
- i18n keys（zh-CN + en-US）

#### Deferred to Follow-Up Work
- Liability / Wish 表单复用 LogoCropper（组件已通用化后可直接引用）
- 服务端水印（本次纯前端）
- 多图片上传
- 图片格式转换

---

## Implementation Units

### U1. Install cropperjs and Dancing Script Font

**Goal:** 添加项目依赖和本地字体文件，为 U2/U3 提供基础设施。

**Requirements:** R4, AC-1

**Dependencies:** none

**Files:**
- `frontend/apps/main/package.json` — 添加 `cropperjs` 依赖
- `frontend/apps/main/public/fonts/dancing-script-latin.woff2` — 新建（Dancing Script Regular Latin 子集）
- `frontend/apps/main/src/style.css` — 添加 `@font-face` 声明

**Approach:**
1. `pnpm add cropperjs` 在 `frontend/apps/main/` 下
2. 从 Google Fonts 下载 Dancing Script Regular (400) woff2 的 Latin 子集，放入 `public/fonts/`（参照 ZCOOL KuaiLe 在 `LoginPage.vue:1425-1440` 的本地字体模式）
3. 在 `src/style.css` 添加全局 `@font-face` 声明（`font-display: swap`），使所有组件可用

**Patterns to follow:**
- `frontend/apps/main/src/pages/LoginPage.vue:1425-1440` — ZCOOL KuaiLe `@font-face` 模式
- `frontend/apps/main/public/fonts/` — 字体文件存放位置

**Test scenarios:**
- `cropperjs` 出现在 `frontend/apps/main/package.json` 的 dependencies 中
- `public/fonts/dancing-script-latin.woff2` 文件存在
- `src/style.css` 包含 `@font-face { font-family: 'Dancing Script' ... }` 声明

**Verification:** `pnpm install` 成功；浏览器 DevTools Network 面板确认 woff2 可访问。

---

### U2. Watermark Engine (`useWatermark.ts`)

**Goal:** 实现纯 Canvas 水印叠加 composable，在裁剪输出的 Canvas 右下角绘制 `userName` + `numina` 花体字水印。

**Requirements:** R2, R5, R6, AC-5

**Dependencies:** U1（Dancing Script 字体已加载）

**Files:**
- `frontend/apps/main/src/composables/useWatermark.ts` — 新建
- `frontend/apps/main/src/composables/__tests__/useWatermark.spec.ts` — 新建

**Approach:**
1. 导出 `useWatermark()` composable，返回 `applyWatermark(canvas, userName)` 异步函数
2. `applyWatermark` 流程：
   - `await document.fonts.load('16px "Dancing Script"')` 检测字体（3s `Promise.race` 超时 → 回退 `cursive`）
   - 计算水印位置：右下角，距边缘 ~5% padding
   - 保存 `ctx.globalAlpha = 0.45`
   - 第一行：`操作人: ${userName}`，系统字体，fontSize = canvas.height * 0.04
   - 第二行：`numina`，`Dancing Script, cursive`，fontSize = canvas.height * 0.05
   - 恢复 `ctx.globalAlpha = 1.0`
   - 返回原 canvas（已就地绘制）
3. 高分屏：canvas 已经是原始像素尺寸（来自 cropperjs `getCroppedCanvas`），无需额外缩放

**Patterns to follow:**
- `frontend/apps/main/src/utils/shareImage.ts` — Canvas 绘制和 `html2canvas` 使用模式
- 项目 composable 命名约定（`use` 前缀）

**Test scenarios:**
- `applyWatermark` 在 canvas 上绘制后，canvas 非空（`toDataURL()` 长度 > 0）
- 字体超时（mock `document.fonts.load` 为 3s 不 resolve）→ 使用 `cursive` 回退，不抛异常
- `globalAlpha` 在绘制后恢复为 1.0
- 空 `userName` 时仍绘制 `numina` 行

**Verification:** 单元测试全部通过；手动在 Canvas 上可见右下角两行水印。

---

### U3. LogoCropper Component

**Goal:** 封装 cropperjs 为全屏裁剪弹窗组件，支持 File/URL 双入口，提供旋转/重置/取消/确定操作。

**Requirements:** R1, R5, R6

**Dependencies:** U1

**Files:**
- `frontend/apps/main/src/components/asset/LogoCropper.vue` — 新建
- `frontend/apps/main/src/components/asset/__tests__/LogoCropper.spec.ts` — 新建

**Approach:**
1. Props：
   - `show: boolean` — 控制弹窗显隐（`v-model:show`）
   - `source: File | string` — 图片来源（File 或 URL string）
2. 内部状态：
   - `objectUrl: string | null` — `URL.createObjectURL(source)` 当 source 为 File 时
   - `imageSrc: computed<string>` — objectUrl 或 source（string 时）
3. 模板结构：
   - `<van-popup v-model:show position="page" lock-scroll>` 全屏
   - 顶部标题栏：`t('assetForm.cropTitle')` + 关闭按钮
   - 中间 `<img ref="imageRef" :src="imageSrc">` 供 cropperjs 初始化
   - 底部工具栏：旋转左/旋转右/重置 + 取消/确定
4. cropperjs 生命周期：
   - `onMounted` / watch show → 当 `show=true` 时 `new Cropper(imageRef, { aspectRatio: 1, viewMode: 1, ... })`
   - watch show → 当 `show=false` 时 `cropper.destroy()` + `URL.revokeObjectURL(objectUrl)`
5. 确定按钮 emit：`cropper.getCroppedCanvas({ maxWidth: 2048, maxHeight: 2048 })` → emit `'confirm'` 带 canvas
6. CORS 处理：当 source 为 string 时，`imageRef.crossOrigin = 'anonymous'`
7. 取消按钮：emit `update:show` false

**Patterns to follow:**
- `frontend/apps/main/src/components/asset/AssetListPanel.vue:310-315` — `<van-action-sheet>` 组件式使用
- Vant `<van-popup position="page" lock-scroll>` — 全屏弹窗模式
- `<script setup lang="ts">` only

**Test scenarios:**
- 组件 mount 时不渲染 cropper（show=false）
- show 变为 true 时初始化 cropper（mock Cropper 构造函数）
- show 变为 false 时调用 `cropper.destroy()`
- source 为 File 时：生成 objectUrl，组件 unmount 时 revokeObjectURL
- source 为 string 时：设置 crossOrigin='anonymous'
- 点击确定 → emit('confirm') 带 canvas 对象
- 点击取消 → emit('update:show', false)

**Verification:** 手动打开裁剪弹窗，双指缩放/旋转正常，确定后返回 canvas。

---

### U4. AssetForm.vue Integration

**Goal:** 改造 AssetForm.vue，接入 LogoCropper + ActionSheet + useWatermark，实现完整的新增/编辑图片流程。

**Requirements:** R3, R5, R6, AC-2, AC-3, AC-4, AC-6

**Dependencies:** U2, U3

**Files:**
- `frontend/apps/main/src/components/asset/AssetForm.vue` — 修改
- `frontend/apps/main/src/components/asset/__tests__/AssetForm.spec.ts` — 修改

**Approach:**
1. **新增引入**：`LogoCropper`, `useWatermark`, `showImagePreview`, `showConfirmDialog`, `useAuthStore`
2. **新增 state**：
   - `showCropper = ref(false)`
   - `cropperSource = ref<File | string | null>(null)`
   - `showActionSheet = ref(false)`
   - `replaceFileInput = ref<HTMLInputElement>()`
3. **改造 `afterRead`**：
   - 原流程：`uploadImage(file.file)` → 设置 `image_url`
   - 新流程：设置 `cropperSource = file.file` → `showCropper = true`（不直接上传）
4. **新增 `onCropperConfirm`**：
   - 接收 canvas → `applyWatermark(canvas, authStore.user?.display_name)` → `canvas.toBlob()` → `uploadImage(blob)` → 设置 `fileList` + `form.image_url`
5. **新增 `@click-preview` handler**（编辑态）：
   - 当 `isEdit && fileList.length > 0` 时，阻止默认 → `showActionSheet = true`
6. **ActionSheet 选项**：`actions` 数组 4 项（查看大图/重裁/替换/删除），`@select` 分发
7. **`@oversize` handler**：`showToast({ message: t('assetForm.fileTooLarge'), icon: 'warning-o' })`
8. **隐藏 file input**：`<input ref="replaceFileInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onReplaceFile">`
9. **CORS 错误捕获**：`onCropperConfirm` 中 try/catch `applyWatermark`，失败时 `showFailToast(t('assetForm.corsError'))`

**Patterns to follow:**
- `frontend/apps/main/src/components/asset/AssetListPanel.vue:310-315` — ActionSheet `@select` 分发模式
- `frontend/apps/main/src/components/asset/AssetForm.vue:624-641` — 现有 `afterRead` / `onDelete` handler 模式
- `frontend/apps/main/src/pages/ChatHistoryPage.vue:98-99` — Vant 4 注释：用组件式 API 非函数式
- `showConfirmDialog` — 删除二次确认（Vant 4 标准模式）
- `showImagePreview({ images: [url] })` — 全屏图片预览

**Test scenarios:**
- 新增态：选择文件后 `showCropper` 变为 true（不调用 `uploadImage`）
- 新增态：cropper confirm → `applyWatermark` 被调用 → `uploadImage` 被调用（传入 Blob）
- 编辑态：点击图片预览 → `showActionSheet` 变为 true
- ActionSheet select 'view' → `showImagePreview` 被调用
- ActionSheet select 'recrop' → `cropperSource` 设为 `image_url` → `showCropper` true
- ActionSheet select 'replace' → 触发 hidden file input click
- ActionSheet select 'delete' → `showConfirmDialog` → 确认后 `form.image_url = ''` + `fileList = []`
- `@oversize` → toast 显示
- CORS 错误 → `showFailToast`

**Verification:** 手动走通新增流程和编辑流程四个选项；AssetDetailPage 展示正常。

---

### U5. i18n Keys

**Goal:** 添加所有新增的国际化翻译键。

**Requirements:** AC-3, AC-4

**Dependencies:** none（可并行）

**Files:**
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 修改
- `frontend/apps/main/src/i18n/locales/en-US.ts` — 修改

**Approach:**
1. 在 `assetForm` 命名空间下添加 13 个新键（见 Product Contract i18n Keys 表）
2. zh-CN 和 en-US 同步添加

**Test expectation: none** — 纯数据添加，通过 U4 集成验证。

**Verification:** `pnpm typecheck` 通过；运行时 `t('assetForm.cropTitle')` 返回正确翻译。

---

## Verification Contract

### Gate Checks

| Gate | Command | Expected |
|------|---------|----------|
| Typecheck | `pnpm typecheck` | 0 errors |
| Unit tests | `pnpm test:run` | All pass (existing + new) |
| Lint | `pnpm lint` | 0 errors |

### Acceptance Verification

| AC | Verification Method |
|----|-------------------|
| AC-1 | `git diff package.json` — 仅新增 `cropperjs` |
| AC-2 | 手动访问 `/assets/new` 和 `/assets/:id/edit`，验证图片流程 |
| AC-3 | 选图→裁剪→确认→水印可见→上传成功→缩略图展示 |
| AC-4 | 编辑态点击图片→ActionSheet 弹出→四个选项各自正确 |
| AC-5 | 导出图片放大检查：水印清晰、numina 为花体字、无拉伸模糊 |
| AC-6 | 删除→缩略图消失+占位符恢复；>5MB 文件→toast 提示；CORS 错误→toast 提示 |

---

## Definition of Done

1. 所有 5 个 Implementation Units 完成
2. Verification Contract 所有 gate checks 通过
3. 所有 AC 手动验证通过
4. `pnpm typecheck` + `pnpm test:run` + `pnpm lint` 全部通过
5. 无新增 `@ts-ignore` / `any`
6. 所有用户可见字符串通过 `t()` 引用 i18n key
