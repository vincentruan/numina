---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
created: 2026-08-13
scope: Deep — cross-cutting UI + asset reorganization + i18n + caching
---

# feat: Asset Icon Picker — 底部浮窗 + 3D 图标目录 + 双语支持

## Summary

将 `AssetForm.vue` 的图片上传区域改造为底部浮窗式 IconPicker，提供两个 Tab：**相册**（相机/相册 → 裁剪 → 水印 → 上传，复用现有 `LogoCropper`）和 **3D 图标**（从 `@numina/assets` 的 3D 图标目录中选择预设图标，按分类浏览、分页、搜索）。同时将 3D 图标目录从 22 个中文文件夹精简为 10 个资产相关英文 kebab-case 文件夹，并添加 TypeScript manifest 实现分类/图标名称的双语支持。

---

## Problem Frame

当前资产录入的图片交互仅支持拍照/相册上传 → 裁剪 → 水印 → 服务端上传。用户希望能直接从预设的 3D 图标库中选择图标作为资产图片，省去拍照和上传步骤，特别适合「数码」「车辆」「家具」等常见资产类别。

核心挑战：
1. **572MB / 7612 文件** — 全量打包不可行，需精简 + 懒加载
2. **中文路径** — 文件夹名和文件名含中文，URL 编码后不可读，部分 CDN/代理不稳定
3. **双语展示** — 分类和图标名称需根据用户语言切换
4. **磁盘缓存** — 大量图标资源可能占用用户设备缓存

---

## Requirements

### R1: IconPicker 底部浮窗

替换 `van-uploader` + 编辑态 ActionSheet，改为点击「更换图标」按钮弹出底部浮窗（`<van-popup position="bottom" round>`），内含两个 Tab：

| Tab | 行为 |
|-----|------|
| 相册 | 子选项：拍照 / 从相册选择 → 选中后进入现有裁剪 + 水印流程（`LogoCropper`） |
| 3D 图标 | 分类导航 + 图标网格 + 搜索 → 选中后直接应用为 `image_url`（无水印） |

浮窗左上角有关闭按钮（✕）。Tab 栏样式：选中 tab 白色背景 + 圆角，未选中透明背景。

**触发方式**（参照实际设计图）：
- 编辑态：3D 盒形图标下方显示「⇄ 更换图标」按钮 → 点击打开浮窗
- 新增态：头像占位区下方显示「⇄ 更换图标」按钮 → 点击打开浮窗

### R2: 3D 图标浏览

- **分类导航**：顶部水平滚动 tab 栏（`<van-tabs>` 或自定义 pill tabs），选中项深色背景 + 白字（如 `全部`、`交通工具`、`电子设备`、`家具家居`、`服装配饰`、...），末尾有搜索图标
- **分页**：每个分类内使用虚拟滚动或分页（每页 40 个），避免一次性渲染大量 DOM
- **搜索**：点击搜索图标展开搜索框，支持跨分类搜索（按图标名称匹配当前语言）
- **图标网格**：5 列网格，每个图标放在圆角方形容器中（浅灰背景 `#f5f5f5`），缩略图居中显示，带 loading 骨架屏（渐显效果）

### R3: 双语支持

- 分类名称：manifest 中 `nameZh` / `nameEn` 字段，根据 `locale` 选择
- 图标名称：manifest 中 `nameZh` / `nameEn` 字段
- 中文 locale (`zh-CN`) → 显示中文；其他 locale → 显示英文
- 图标 tooltip/长按提示显示完整名称

### R4: 3D 目录精简

- 删除 12 个非资产相关文件夹（食物饮品、动物生物、人物角色、历史名人、宗教神话、旗帜标志、数字符号、医疗健康、植物花卉、建筑地点、科学技术、艺术文化）
- 保留 10 个资产相关文件夹，重命名为英文 kebab-case
- 清理 hash 后缀文件（如 `06093_Air purifier_Ch0DKvgs.png`）

### R5: 文件夹和文件名调整

- 文件夹：中文名 → 英文 kebab-case（如 `交通工具` → `vehicles`）
- 文件名：保留 `中文名_English Name.ext` 格式不变（双语参考值有用）
- hash 后缀文件重命名为 `english-name.ext` 格式
- manifest 负责映射 filename → 双语显示名

### R6: 缓存优化

- 预生成 128×128 WebP 缩略图（~5-15KB/张），存放在 `public/icons/3d-thumbs/`
- 按分类懒加载：仅当用户点击分类 chip 时才加载该分类缩略图
- 原始图标通过 `public/icons/3d/` URL 按需加载（选中时）
- 不在 JS bundle 中包含任何图标引用（避免 import 膨胀）

### R7: 交互整合

- 新增态：点击头像占位区 → 打开 IconPicker 底部浮窗
- 编辑态：点击已有图片 → 同样打开 IconPicker（顶部显示当前图片 + 删除按钮）
- 选择 3D 图标后：直接设置 `form.image_url`，不触发裁剪/水印
- 选择相册后：走现有 `LogoCropper` → 水印 → 上传流程
- `LogoCropper` 保持不变（已在 `2026-08-12-001` plan 中实现）

---

## Key Technical Decisions

### KTD-1: TypeScript manifest（非 CSV）

**决策**：在 `frontend/packages/assets/src/icons/` 下创建 `icon-manifest.ts`，导出分类和图标的元数据（双语名称、文件夹映射、排序）。

**理由**：
- 类型安全，IDE 自动补全
- Vite 自动处理 tree-shaking
- 无需额外 CSV 解析逻辑
- 与现有 i18n 系统集成自然

**替代方案**：CSV 文件 — 运行时需额外解析，无类型检查，维护成本高。

### KTD-2: public 目录 serve（非 import）

**决策**：图标文件通过 `public/icons/3d/` 目录 serve，IconPicker 通过 URL 引用（`/icons/3d/vehicles/car.png`），不使用 `import` 或 `import.meta.glob`。

**理由**：
- 2700+ 文件的 import 会创建数千个 Vite 模块，构建时间不可接受
- public 目录文件不进入 JS bundle
- URL 引用天然支持懒加载
- 浏览器 HTTP 缓存自动管理

**替代方案**：`import.meta.glob` — 所有 URL 打入 bundle，首屏加载慢。

### KTD-3: 预生成缩略图（128×128 WebP）

**决策**：创建 `scripts/generate-icon-thumbnails.ts` 构建脚本，使用 `sharp` 将原始 PNG/WebP 缩放到 128×128 WebP（quality 80），存放到 `public/icons/3d-thumbs/`。IconPicker 始终加载缩略图 URL。

**理由**：
- 原始 PNG ~200-500KB/张，缩略图 ~5-15KB/张（30× 压缩）
- 1000 张缩略图 ≈ 5-15MB，移动端可接受
- 选中时再加载原始尺寸（仅 1 张）
- WebP 比 PNG 小 25-35%

**执行方向**：
- **Phase 1（本次实现）**：直接将原始图标复制到 `public/icons/3d/`，IconPicker 使用原始图 URL（`/icons/3d/{category}/{fileName}`）。此阶段功能完整可用，但首屏加载较慢（40 张原图 ≈ 8-20MB）。
- **Phase 2（后续优化）**：运行 `generate:thumbs` 脚本生成缩略图，切换 IconPicker URL 到 `/icons/3d-thumbs/`。缩略图生成后提交到 git。

**Phase 1 → Phase 2 切换方式**：`useIconCatalog` composable 中的 `getThumbUrl()` 函数统一返回缩略图路径。Phase 1 时该函数返回原始图路径（`/icons/3d/...`），Phase 2 切换为缩略图路径（`/icons/3d-thumbs/...`）。只需修改一处。

### KTD-4: 3D 图标无水印

**决策**：选择 3D 图标时，直接设置 `image_url` 为图标 URL，不经过裁剪/水印流程。

**理由**：
- 3D 图标是预设资源，非用户创作，无需水印保护
- 图标已经是正方形，无需裁剪
- 简化交互流程
- 水印会覆盖图标内容，影响辨识度

### KTD-5: 保留 10 个资产相关分类

| 保留 | 文件夹（新名） | 文件数 | 大小 |
|------|---------------|--------|------|
| ✅ 交通工具 | `vehicles` | 405 | 33M |
| ✅ 电子设备 | `electronics` | 345 | 26M |
| ✅ 家具家居 | `furniture` | 314 | 23M |
| ✅ 服装配饰 | `clothing-accessories` | 516 | 36M |
| ✅ 工具器械 | `tools` | 450 | 30M |
| ✅ 运动健身 | `sports` | 413 | 29M |
| ✅ 厨房用品 | `kitchenware` | 230 | 16M |
| ✅ 娱乐休闲 | `entertainment` | 296 | 24M |
| ✅ 音乐乐器 | `instruments` | 120 | 8.5M |
| ✅ 办公文具 | `office-stationery` | 207 | 15M |
| **合计** | | **3296** | **~241M** |

**删除**（12 个文件夹，~331M）：食物饮品、动物生物、人物角色、历史名人、宗教神话、旗帜标志、数字符号、医疗健康、植物花卉、建筑地点、科学技术、艺术文化。

**理由**：办公文具包含打印机、电脑配件、文件柜等办公设备，属于合理的家庭/个人资产追踪范畴。

---

## Implementation Units

### U1. 3D 目录精简与重命名

**Goal:** 将 `@numina/assets/src/icons/3d-things/` 从 22 个中文文件夹精简为 10 个英文 kebab-case 文件夹，删除非资产相关图标（~331MB），清理异常文件名。

**Requirements:** R4, R5

**Dependencies:** none

**Files:**
- `frontend/packages/assets/src/icons/3d-things/` — 重命名 + 删除

**Approach:**
1. 新建 `frontend/packages/assets/src/icons/3d-things-renamed/` 临时目录
2. 对 10 个保留的文件夹：
   - 创建英文 kebab-case 目标文件夹
   - 移动文件（保留原文件名 `中文名_English Name.ext`）
   - 对 hash 后缀文件（如 `06093_Air purifier_Ch0DKvgs.png`），重命名为 `english-name.ext`
3. 删除 12 个非资产相关文件夹
4. 替换原 `3d-things/` 目录（或直接在原位重命名）
5. 更新 `frontend/packages/assets/package.json` exports 和 `README.md`

**目录映射：**

| 原文件夹 | 新文件夹 |
|----------|---------|
| 交通工具 | vehicles |
| 电子设备 | electronics |
| 家具家居 | furniture |
| 服装配饰 | clothing-accessories |
| 工具器械 | tools |
| 运动健身 | sports |
| 厨房用品 | kitchenware |
| 娱乐休闲 | entertainment |
| 音乐乐器 | instruments |
| 办公文具 | office-stationery |

**Test scenarios:**
- 10 个目标文件夹存在且非空
- 12 个非资产文件夹已删除
- 每个保留文件夹内文件数量与上表一致
- 无 hash 后缀文件（正则 `^[0-9]{5}_.*_[A-Za-z0-9]{8}\.png$` 匹配为 0）

**Verification:** `find frontend/packages/assets/src/icons/ -type d | wc -l` = 11（10 文件夹 + 根目录）；总大小 ≈ 241MB。

---

### U2. Icon Manifest（TypeScript 元数据模块）

**Goal:** 创建分类和图标的双语 manifest，作为 IconPicker 的数据源和 i18n 的唯一来源。

**Requirements:** R3

**Dependencies:** U1（文件夹已重命名）

**Files:**
- `frontend/packages/assets/src/icons/icon-manifest.ts` — 新建
- `frontend/packages/assets/package.json` — 添加 `./icons/manifest` export

**Approach:**
1. 定义类型：
   ```ts
   interface IconCategory {
     id: string            // 'vehicles' | 'electronics' | ...
     nameZh: string        // '交通工具'
     nameEn: string        // 'Vehicles'
     folder: string        // 'vehicles'（对应 public/icons/3d/ 子目录）
     sortOrder: number
     assetCategoryHints: string[]  // 关联的系统分类 icon ID（如 ['car', 'home']）
   }

   interface IconEntry {
     fileName: string      // '吉他音箱_Guitar Amplifier.png'
     nameZh: string        // '吉他音箱'
     nameEn: string        // 'Guitar Amplifier'
   }

   interface IconManifest {
     categories: IconCategory[]
     icons: Record<string, IconEntry[]>  // categoryId → entries
   }
   ```

2. 导出 `iconManifest: IconManifest` 常量
3. 分类 nameZh/nameEn 从文件夹映射硬编码（10 个分类，含办公文具）
4. 图标 nameZh/nameEn 从文件名解析（`中文名_English Name.ext` → split on first `_`）
5. 添加构建脚本 `scripts/build-icon-manifest.ts` 自动生成 manifest（解析文件夹结构和文件名）

**package.json export:**
```json
"./icons/manifest": "./src/icons/icon-manifest.ts"
```

**Patterns to follow:**
- `frontend/packages/assets/src/icons/index.ts` — 现有 icons 导出模式
- TypeScript 常量导出（非 class，非 function）

**Test scenarios:**
- manifest 导出 10 个分类（含 office-stationery）
- 每个分类的 `nameZh` 和 `nameEn` 非空
- 图标总数 ≈ 3296
- 文件名解析正确（中文名、英文名无空值）
- hash 后缀文件的 nameZh/nameEn 从文件名合理提取

**Verification:** `import { iconManifest } from '@numina/assets/icons/manifest'` 成功；`iconManifest.categories.length === 10`。

---

### U3. 复制到 public + 缩略图生成脚本

**Goal:** 将精简后的图标复制到 `public/icons/3d/`，并创建缩略图生成脚本（128×128 WebP）。

**Requirements:** R6

**Dependencies:** U1, U2

**Files:**
- `frontend/apps/main/public/icons/3d/` — 新建（从 assets 包复制或 symlink）
- `frontend/apps/main/public/icons/3d-thumbs/` — 新建（缩略图输出目录，Phase 2）
- `frontend/apps/main/scripts/generate-icon-thumbnails.ts` — 新建
- `frontend/apps/main/scripts/deploy-icons.sh` — 新建（从 @numina/assets 复制到 public）
- `frontend/apps/main/package.json` — 添加 `sharp` devDependency + `generate:thumbs` + `deploy:icons` script
- `frontend/apps/main/Dockerfile` — 修改（添加 @numina/assets COPY）

**Docker 部署注意**：
- Dockerfile 需添加 `COPY frontend/packages/assets ./frontend/packages/assets`（现有只 COPY 了 auth/math）
- 需添加 sed rewrite 将 `@numina/assets` 重写为 `file:` 路径
- `public/icons/3d/` 由 Vite 自动复制到 `dist/`，nginx 镜像会包含这些文件
- sharp 仅在本地运行（devDependency），不在 Docker 构建中运行

**Approach:**
1. **图标文件部署策略**：
   - U1 已将 `@numina/assets/src/icons/3d-things/` 精简并重命名为 10 个英文文件夹
   - 将这 10 个文件夹复制到 `public/icons/3d/` 作为运行时 serve 目录
   - `@numina/assets/src/icons/3d-things/` 保留作为 LFS 源素材仓库
   - 理由：public 目录文件不进入 JS bundle，URL 引用直接可用

2. **缩略图生成脚本**：
   - 使用 `sharp`（已有 html2canvas 经验，项目内图片处理首选）
   - 输入：`public/icons/3d/{category}/*.png|webp`
   - 输出：`public/icons/3d-thumbs/{category}/{filename}.webp`（128×128，quality 80）
   - 并发处理（`Promise.all` 分批，每批 50 个）
   - 预计耗时：3300 张 × ~10ms/张 ≈ 33 秒

3. **package.json script**：
   ```json
   "scripts": {
     "generate:thumbs": "tsx scripts/generate-icon-thumbnails.ts"
   }
   ```

4. **部署脚本**（可选）：`scripts/deploy-icons.sh` — rsync 从 assets 到 public

**Patterns to follow:**
- `frontend/apps/main/src/utils/shareImage.ts` — 已有 Canvas 图片处理模式
- sharp 官方 API：`sharp(input).resize(128, 128).webp({ quality: 80 }).toFile(output)`

**Test scenarios:**
- 脚本运行后 `public/icons/3d-thumbs/` 下每个分类子目录存在
- 缩略图数量 = 原始图标数量
- 缩略图尺寸均为 128×128
- 缩略图格式为 WebP
- 单张缩略图大小 < 30KB

**Verification:** `ls public/icons/3d-thumbs/vehicles/ | wc -l` === `ls public/icons/3d/vehicles/ | wc -l`。

---

### U4. IconPicker 组件

**Goal:** 创建底部浮窗式 IconPicker 组件，支持相册和 3D 图标两个 Tab。

**Requirements:** R1, R2, R3, R7

**Dependencies:** U2, U3

**Files:**
- `frontend/apps/main/src/components/asset/IconPicker.vue` — 新建
- `frontend/apps/main/src/components/asset/__tests__/IconPicker.spec.ts` — 新建
- `frontend/apps/main/src/composables/useIconCatalog.ts` — 新建（数据加载逻辑）

**Approach:**
1. **Props：**
   - `show: boolean` — 控制显隐（`v-model:show`）
   - `currentImageUrl: string` — 当前图片 URL（编辑态显示）

2. **Emits：**
   - `'select-image'` — 用户选择了图片（URL string，可以是 3D 图标 URL 或上传后的 URL）
   - `'request-gallery'` — 用户请求从相册选择（触发 file input）
   - `'request-camera'` — 用户请求拍照
   - `'delete'` — 用户请求删除当前图片

3. **模板结构：**
   ```
   <van-popup position="bottom" round :close-on-click-overlay="true">
     <!-- 左上角关闭按钮 -->
     <van-icon name="cross" class="close-btn" @click="emit('update:show', false)" />

     <!-- 编辑态：当前图片预览 + 删除按钮 -->
     <div v-if="currentImageUrl" class="current-preview">
       <img :src="currentImageUrl" class="preview-thumb" />
       <van-icon name="cross" class="delete-btn" @click="emit('delete')" />
     </div>

     <!-- Tab 栏（2 个 tab） -->
     <div class="tab-bar">
       <div class="tab" :class="{ active: activeTab === 'gallery' }"
            @click="activeTab = 'gallery'">{{ t('iconPicker.tabGallery') }}</div>
       <div class="tab" :class="{ active: activeTab === '3d' }"
            @click="activeTab = '3d'">{{ t('iconPicker.tab3dIcons') }}</div>
     </div>

     <!-- 相册 Tab -->
     <div v-if="activeTab === 'gallery'" class="gallery-content">
       <!-- 两个按钮触发真实选择 -->
       <van-button icon="photograph" @click="emit('request-gallery')">
         {{ t('iconPicker.fromGallery') }}
       </van-button>
       <van-button icon="camera" @click="emit('request-camera')">
         {{ t('iconPicker.fromCamera') }}
       </van-button>
     </div>


     <!-- 3D 图标 Tab -->
     <div v-if="activeTab === '3d'" class="icon3d-content">
       <!-- 分类 tab 栏 + 搜索 -->
       <div class="category-tabs">
         <div class="tab-scroll">
           <div v-for="cat in categories" :key="cat.id"
                class="cat-tab" :class="{ active: activeCategory === cat.id }"
                @click="activeCategory = cat.id">
             {{ getCategoryName(cat) }}
           </div>
         </div>
         <van-icon name="search" class="search-btn" @click="showSearch = true" />
       </div>
       <!-- 搜索框（可展开） -->
       <van-search v-if="showSearch" v-model="searchQuery"
                   :placeholder="t('iconPicker.searchPlaceholder')" />
       <!-- 图标网格：5 列 -->
       <div class="icon-grid">
         <!-- 空状态：搜索无结果 -->
         <div v-if="paginatedIcons.length === 0 && searchQuery" class="empty-state">
           {{ t('iconPicker.noResults') }}
         </div>
         <div v-for="icon in paginatedIcons" :key="icon.fileName"
              class="icon-cell" @click="selectIcon(icon)">
           <div class="icon-thumb">
             <img :src="getThumbUrl(icon)" loading="lazy" @error="onThumbError" />
           </div>
         </div>
       </div>
       <!-- 分页/虚拟滚动 -->
       <van-list v-if="totalIcons > pageSize" @load="loadMore" />
     </div>
   </van-popup>
   ```

4. **useIconCatalog composable 接口定义：**

   ```ts
   interface UseIconCatalogReturn {
     categories: Ref<IconCategory[]>        // 分类列表（含 "全部"）
     activeCategory: Ref<string>            // 当前选中分类 ID
     paginatedIcons: Ref<IconEntry[]>       // 当前页图标列表
     totalIcons: Ref<number>                // 当前分类/搜索结果总数
     isLoading: Ref<boolean>                // 加载中状态
     hasMore: Ref<boolean>                  // 是否有更多页
     searchQuery: Ref<string>               // 搜索关键词
     isSearchMode: Ref<boolean>             // 是否处于搜索模式

     // Methods
     selectCategory(id: string): void       // 切换分类（清空搜索）
     search(query: string): void            // 搜索（跨分类，debounce 300ms）
     clearSearch(): void                    // 清空搜索，恢复分类浏览
     loadMore(): void                       // 加载下一页（40 个）
     getThumbUrl(icon: IconEntry): string   // 构建缩略图 URL
   }
   ```

   **行为规则：**
   - **"全部"分类**：显示所有分类的图标，按分类顺序拼接，每页 40 个。懒加载：切换到"全部"时先加载第一个分类，滚动到底部时自动加载下一个分类。
   - **搜索模式**：搜索激活时隐藏分类 tab 栏，显示跨分类搜索结果。搜索结果按 manifest 中的分类顺序排列，每页 40 个。搜索输入 debounce 300ms。
   - **状态重置**：切换分类时清空搜索；关闭 popup 时重置到默认分类和空搜索。
   - **URL 构建**：
     - Phase 1：`getThumbUrl(icon) => /icons/3d/${category}/${icon.fileName}`
     - Phase 2：`getThumbUrl(icon) => /icons/3d-thumbs/${category}/${stripExt(icon.fileName)}.webp`


5. **URL 构建：**
   - 缩略图：`/icons/3d-thumbs/{category}/{fileName}`
   - 原始图：`/icons/3d/{category}/{fileName}`
   - 选中图标时 emit 原始图 URL

6. **样式要点（参照设计图）：**
   - **Popup 容器**：`max-height: 75vh`，内部滚动区域 = popup 高度 - tab 栏 - 搜索栏，`overflow-y: auto`
   - Tab 栏：选中项白色圆角背景 + 阴影，未选中透明
   - 分类 tab：深色（`#1a1a1a`）选中 + 白字，未选中浅灰 + 深灰字
   - 图标网格：5 列，每个 cell 圆角方形容器（`#f5f5f5` 背景），图标居中，`min-height: 64px`（确保触摸目标 ≥ 44px）
   - 图标 cell 有渐显 loading 效果 + `@error` fallback 到占位 SVG
   - **深色模式**：使用 CSS 变量（`var(--card-bg)` 替代 `#f5f5f5`，`var(--text-primary)` 替代硬编码颜色），遵循 `AssetForm.vue` 深色模式模式
   - **选中指示器**：编辑态下当前选中的 3D 图标显示 checkmark overlay 或边框高亮

**Patterns to follow:**
- `frontend/apps/main/src/components/asset/AssetForm.vue:76-92` — `van-popup` 模式
- Vant `<van-tabs>` / 自定义 tab 栏（设计图用自定义样式）
- `frontend/apps/main/src/components/asset/AssetListPanel.vue` — 列表/网格模式

**Test scenarios:**
- 组件 mount 时不渲染 popup（show=false）
- show 变为 true 时 popup 显示，默认 activeTab = 'gallery'
- 切换到 3D 图标 tab → 加载默认分类的图标
- 点击分类 tab 切换分类 → 加载新分类图标
- 搜索输入 → 图标列表过滤
- 点击图标 → emit('select-image') 带原始图 URL
- 点击拍照 → emit('request-camera')
- 点击相册 → emit('request-gallery')
- 关闭按钮 → emit('update:show', false)
- 分页：滚动到底部 → 加载下一页 40 个图标

**Verification:** 手动打开 IconPicker，两个 Tab 切换、3D 分类/搜索/选择均正常。

---

### U5. AssetForm.vue 集成

**Goal:** 改造 `AssetForm.vue`，替换 `van-uploader` + 编辑态 ActionSheet，接入 IconPicker。

**Requirements:** R1, R7

**Dependencies:** U4

**Files:**
- `frontend/apps/main/src/components/asset/AssetForm.vue` — 修改
- `frontend/apps/main/src/components/asset/__tests__/AssetForm.spec.ts` — 修改

**Approach:**
1. **移除 `van-uploader`**（第 7-23 行），替换为头像区域 + 「更换图标」按钮：
   ```html
   <div class="avatar-area">
     <!-- 当前图标/占位 -->
     <div v-if="form.image_url" class="asset-preview">
       <img :src="form.image_url" />
     </div>
     <div v-else class="image-placeholder">
       <van-icon name="photograph" size="32" />
     </div>
     <!-- 更换图标按钮 -->
     <van-button size="small" icon="exchange" @click="showIconPicker = true">
       {{ t('iconPicker.changeIcon') }}
     </van-button>
   </div>
   ```

2. **移除编辑态 ActionSheet**（第 302-307 行 + 相关 state）

3. **新增 state：**
   - `showIconPicker = ref(false)`
   - `galleryFileInput = ref<HTMLInputElement>()`（隐藏的 file input）
   - `cameraFileInput = ref<HTMLInputElement>()`（隐藏的 file input，带 `capture="environment"`）

4. **IconPicker 事件处理：**
   ```ts
   function onIconPickerSelectImage(url: string) {
     form.value.image_url = url
     fileList.value = [{ url }]
     showIconPicker.value = false
   }

   function onIconPickerRequestGallery() {
     showIconPicker.value = false
     galleryFileInput.value?.click()
   }

   function onIconPickerRequestCamera() {
     showIconPicker.value = false
     cameraFileInput.value?.click()
   }

   function onIconPickerDelete() {
     form.value.image_url = ''
     fileList.value = []
     showIconPicker.value = false
   }

   // Gallery/camera file selected → cropper flow
   function onFileSelected(event: Event) {
     const file = (event.target as HTMLInputElement).files?.[0]
     if (!file) return
     cropperSource.value = file
     showCropper.value = true
   }
   ```

5. **保留 `LogoCropper`**（第 295-299 行）不变，`onCropperConfirm` 逻辑不变

6. **保留 `@oversize` 逻辑**：在 `onFileSelected` 中检查 `file.size > 5MB`

**Patterns to follow:**
- `frontend/apps/main/src/components/asset/AssetForm.vue:670-700` — 现有 `afterRead` / `onCropperConfirm` 模式
- 隐藏 file input 模式（现有 `replaceFileInput` 参考）

**Test scenarios:**
- 点击「更换图标」→ `showIconPicker` 变为 true
- IconPicker 默认选中「相册」Tab
- IconPicker select-image（3D 图标）→ `form.image_url` 更新（不触发 cropper）
- IconPicker request-gallery → 隐藏 file input 触发
- 选择文件后 → `showCropper` 变为 true（现有裁剪流程）
- Cropper confirm → 水印 → 上传 → `form.image_url` 更新
- IconPicker delete → `form.image_url = ''` + `fileList = []`
- `@oversize` → toast 提示

**Verification:** 手动走通新增态（相册 + 3D 图标）和编辑态（切换 + 删除）完整流程。

---

### U6. i18n Keys

**Goal:** 添加 IconPicker 相关的所有国际化翻译键。

**Requirements:** R3

**Dependencies:** none（可并行）

**Files:**
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 修改
- `frontend/apps/main/src/i18n/locales/en-US.ts` — 修改

**Approach:**

新增 `iconPicker` 命名空间：

| Key | zh-CN | en-US |
|-----|-------|-------|
| `iconPicker.tabGallery` | 相册 | Gallery |
| `iconPicker.tab3dIcons` | 3D 图标 | 3D Icons |
| `iconPicker.fromGallery` | 从相册选择 | Choose from Gallery |
| `iconPicker.fromCamera` | 拍照 | Take Photo |
| `iconPicker.searchPlaceholder` | 搜索图标 | Search icons |
| `iconPicker.allCategories` | 全部 | All |
| `iconPicker.noResults` | 没有找到匹配的图标 | No matching icons |
| `iconPicker.loading` | 加载中... | Loading... |
| `iconPicker.recentAlbum` | 最近项目 | Recent |
| `iconPicker.changeIcon` | 更换图标 | Change Icon |

**Test expectation: none** — 纯数据添加，通过 U5 集成验证。

**Verification:** `pnpm typecheck` 通过；运行时 `t('iconPicker.tabGallery')` 返回正确翻译。

---

## Verification Contract

### Gate Checks

| Gate | Command | Expected |
|------|---------|----------|
| Typecheck | `pnpm typecheck` | 0 errors |
| Unit tests | `pnpm test:run` | All pass (existing + new) |
| Lint | `pnpm lint` | 0 errors |

### Acceptance Verification

| Scenario | Method |
|----------|--------|
| 新增资产 — 选择 3D 图标 | `/assets/new` → 点击「更换图标」→ 3D 图标 Tab → 选分类 → 选图标 → 表单显示图标 → 提交成功 |
| 新增资产 — 拍照 | `/assets/new` → 点击「更换图标」→ 相册 Tab → 拍照 → 裁剪 → 水印 → 上传 → 显示 |
| 新增资产 — 相册选择 | 同上，选「从相册选择」 |
| 编辑资产 — 切换图标 | `/assets/:id/edit` → 点击「更换图标」→ 选不同 3D 图标 → 保存 |
| 编辑资产 — 切换为照片 | 点击「更换图标」→ 相册 Tab → 选照片 → 裁剪 → 保存 |
| 编辑资产 — 删除图标 | 点击「更换图标」→ 删除按钮 → 确认 → 头像恢复占位 |
| Tab 切换 | IconPicker 内两个 Tab 均可切换，默认选中「相册」 |
| 分类切换 | 3D 图标 Tab → 点击不同分类 tab → 图标网格更新 |
| 搜索 | 3D 图标 Tab → 点击搜索图标 → 输入关键词 → 图标列表过滤 |
| 语言切换 | 中文 locale → 分类/图标名中文；英文 locale → 英文 |
| 分页 | 大分类（如 vehicles 405 张）→ 滚动加载 → 不卡顿 |
| 缓存 | DevTools Network → 缩略图仅在点击分类时加载；同一分类不重复请求 |

---

## Definition of Done

1. 所有 6 个 Implementation Units 完成
2. Verification Contract 所有 gate checks 通过
3. 所有 Acceptance 场景手动验证通过
4. `pnpm typecheck` + `pnpm test:run` + `pnpm lint` 全部通过
5. 无新增 `@ts-ignore` / `any`
6. 所有用户可见字符串通过 `t()` 引用 i18n key
7. 3D 图标目录精简完成（10 个文件夹，~241MB）
8. IconPicker 在 Chrome DevTools mobile simulator 和 iOS Safari 上表现正常

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| 缩略图生成耗时长（首次 3300 张 ≈ 33s） | CI/CD 时间增加 | 脚本支持增量生成（跳过已存在的缩略图）；本地运行一次后提交到 git |
| public/icons/3d/ 增加 241MB 到仓库 | git clone 变慢 | 使用 Git LFS 追踪（现有 `.gitattributes` 规则已覆盖 PNG/WebP） |
| 移动端渲染大量图标卡顿 | 用户体验差 | 虚拟滚动（`van-list` + 分页）+ `loading="lazy"` + 缩略图小尺寸 |
| 文件名解析错误（特殊字符、括号） | manifest 数据不完整 | 构建脚本添加 fallback：解析失败时使用完整文件名作为 nameEn |
| 3D 图标 URL 在 Production 环境 404 | 图标不显示 | 部署脚本确保 `public/icons/3d/` 包含在生产构建中；`<img @error>` fallback 占位图 |
| Dockerfile 缺少 @numina/assets COPY | Docker 构建失败 | U3 已包含 Dockerfile 修改；添加 COPY + sed rewrite |
| sharp 原生模块在 Alpine/CI 编译失败 | 缩略图脚本不可用 | sharp 仅作为 devDependency，仅在本地运行；生成结果提交到 git |
| Docker nginx 镜像膨胀（+241MB） | 部署/拉取变慢 | 可接受（nginx 静态 serve 场景）；后续可考虑 CDN 或 volume 挂载 |
| 图标 URL 无 content hash，nginx 30 天缓存 | 更新图标后用户看到旧版 | 后续添加 ETag/Last-Modified 或版本查询参数；当前图标为预设资源，极少更新 |

---

## Deferred to Follow-Up Work

- **Emoji Tab（自定义 3D 卡通图标）**：待 cartoon-consumer 素材准备就绪后再实现
- **cartoon-consumer 主题**：等待素材导入后再集成到 IconPicker
- **Service Worker 缓存策略**：后续可添加 SW 管理图标缓存（LRU 淘汰）
- **Liability / Wish 表单复用**：IconPicker 组件通用化后可直接引用
- **图标收藏/最近使用**：记录用户常用图标，快速访问
- **AI 推荐图标**：根据资产名称自动推荐匹配的 3D 图标
- **缩略图 CDN**：生产环境可将 `public/icons/3d/` 上传到 CDN，减少服务器负载
- **动态 import 优化**：当浏览器支持 better asset handling 时，可迁移到 `import.meta.glob` 获得 content hash 缓存
