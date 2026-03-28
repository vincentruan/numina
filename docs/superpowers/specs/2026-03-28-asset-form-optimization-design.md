# 资产录入界面优化设计文档

**日期**：2026-03-28
**状态**：已确认，待实施
**范围**：前端 `AssetForm.vue` 及相关子组件，后端无改动

---

## 背景

当前资产录入界面存在多处与用户心智模型不符的交互设计：分类选择使用文字 Picker 丢失视觉锚点、预期寿命单位为"天"而用户心智是"年"、状态字段在录入时显示造成噪音、标签字段完全缺失。参考有数 App 的资产录入设计，结合第一性原理分析，本次优化覆盖 P0（必须做）和 P1（应该做）全部 8 项改动。

---

## 设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 分类选择器布局 | 4列图标网格（内嵌展开） | emoji 22px，名称清晰，一屏扫描效率高，无弹窗 |
| 使用频率交互 | 图标按钮组（横向5个） | 所有选项同时可见，点击直接切换，与参考设计一致 |
| 表单整体结构 | 单页线性滚动 | 无分步跳转，向下滚动完成录入，认知负担最低 |
| 字段顺序（实物） | 使用频率→预期寿命→存放位置→年维护费 | 使用频率与预期寿命都是日均成本核心输入，语义连贯 |

---

## 完整表单结构

```
[图片区域]                    ← 顶部独立，76px 居中，相机图标 + "添加图片"
[实物资产 | 金融资产]          ← SegmentedControl，切换后字段分支

─── 基本信息 ───
名称                          ← 文本输入，必填
分类                          ← 点击展开 4列图标网格（内嵌，选中高亮保持展开）
购入价格                      ← 数字输入 + 货币选择按钮，必填
当前价值                      ← 数字输入 + [同购入价] 快捷按钮，必填
购入日期                      ← 日期选择器
状态（仅编辑模式）            ← 下拉 Picker：服役中/闲置/已出售/已退役

─── 实物资产信息（asset_type === 'physical'）───
使用频率                      ← 5个图标按钮组：每天/每周/每月/偶尔/闲置
预期寿命                      ← 数字输入（单位：年）+ [不限] 快捷选项
存放位置                      ← 文本输入，可选
年维护费                      ← 数字输入，可选

─── 金融资产信息（asset_type === 'financial'）───
金融机构                      ← 文本输入，可选
利率(%)                       ← 数字输入，可选
到期日期                      ← 日期选择器，可选

─── 标签与备注 ───
标签                          ← 已选标签 chip 列表 + [+ 添加标签] 按钮
备注                          ← textarea，可选

[添加资产 / 保存修改] 按钮
```

---

## P0 优化项（4项）

### 1. 分类选择器 → 4列图标网格

**组件**：新建 `frontend/src/components/asset/CategoryGrid.vue`

- Props：`categories: Category[]`，`modelValue: string`（category_id），`assetType: string`
- 按 `asset_type` 过滤分类，实物/金融分组显示（section header）
- 4列 grid，每项：emoji（16px）+ 名称（9px）
- 选中态：`border: 1.5px solid var(--color-primary)`，背景 `rgba(primary, 0.12)`
- 点击直接 emit `update:modelValue`，网格保持展开（不收起）
- `AssetForm.vue` 中替换原 Picker + Popup 为此组件

### 2. 预期寿命单位 → 年

**改动**：`AssetForm.vue` 内部换算逻辑

- 表单内部用 `expected_life_years`（显示用），提交时换算：`years * 365 → expected_lifespan_days`
- 编辑回显时反向换算：`days / 365`（Math.round）
- 添加 [不限] 快捷按钮：点击设置 `expected_life_years = null`，对应后端 `expected_lifespan_days = null`
- 输入验证：1–100 年范围，整数

### 3. 当前价值 → 添加"同购入价"按钮

**改动**：`AssetForm.vue` 当前价值字段

- 字段右侧添加 `[同购入价]` 文字按钮（`van-tag` 样式）
- 点击：`form.current_value = form.purchase_price`
- 购入价为空时按钮禁用（`opacity: 0.4`，不可点击）
- 购入价变化时不自动同步（避免用户已手动修改当前价值被覆盖）

### 4. 状态字段 → 新建时隐藏

**改动**：`AssetForm.vue` 条件渲染

- `v-if="isEdit"` 控制状态字段显示
- 新建时后端默认 `status = 'in_use'`（已有默认值，无需改动后端）
- 编辑时状态字段显示在"基本信息"末尾，购入日期之后

---

## P1 优化项（4项）

### 5. 图片区域 → 顶部独立

**改动**：`AssetForm.vue` 模板结构 + 样式

- 图片区域移到 `<van-form>` 最顶部，独立 section（不在 `van-cell-group` 内）
- 尺寸：76×76px，居中，`border-radius: 14px`，虚线边框
- 无图片时：相机图标（24px）+ "添加图片"文字（10px）
- 有图片时：预览图，右上角删除按钮

### 6. 资产类型 → SegmentedControl

**改动**：`AssetForm.vue` 类型选择

- 替换 Picker + Popup 为自定义 SegmentedControl（两个 tab：实物资产 / 金融资产）
- 使用 Vant `van-tabs` 或自定义 flex 布局实现
- 选中态：填充色背景 + 白色文字；未选中：透明背景 + 灰色文字
- 切换时清空对应类型的专属字段（避免脏数据）

### 7. 使用频率 → 图标按钮组

**组件**：新建 `frontend/src/components/asset/UsageFreqSelector.vue`

- Props：`modelValue: string`
- 5个选项横向排列：`{ value: 'daily', icon: '📅', label: '每天' }` 等
- 每项：图标（14px）+ 文字（9px），flex: 1
- 选中态与 CategoryGrid 一致（primary border + 背景）
- `AssetForm.vue` 替换原 Picker + Popup

### 8. 标签字段 → 新增多选选择器

**组件**：新建 `frontend/src/components/asset/TagSelector.vue`

- Props：`modelValue: string[]`（tag_ids），`tags: Tag[]`（可用标签列表）
- 显示：已选标签以 chip 形式展示，点击 chip 可移除
- [+ 添加标签] 按钮：点击弹出 `van-popup`，展示所有可用标签（多选）
- 支持在弹窗内创建新标签（输入名称 → 调用 `POST /api/v1/tags`）
- `AssetForm.vue` 集成，提交时包含 `tag_ids` 字段（已在 `AssetCreate` schema 中）

---

## 数据流变化

### 提交时（新建/编辑）

```typescript
// 预期寿命换算
expected_lifespan_days: form.expected_life_years
  ? Math.round(form.expected_life_years * 365)
  : null

// 标签（已有字段）
tag_ids: form.tag_ids  // string[]

// 状态（新建时不提交，使用后端默认值）
status: isEdit ? form.status : undefined
```

### 编辑回显时

```typescript
// 预期寿命反向换算
form.expected_life_years = data.expected_lifespan_days
  ? Math.round(data.expected_lifespan_days / 365)
  : null

// 标签
form.tag_ids = data.tags?.map(t => t.id) ?? []
```

---

## 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/asset/CategoryGrid.vue` | 分类图标网格选择器 |
| `frontend/src/components/asset/UsageFreqSelector.vue` | 使用频率图标按钮组 |
| `frontend/src/components/asset/TagSelector.vue` | 标签多选选择器 |

## 修改文件

| 文件 | 改动摘要 |
|------|---------|
| `frontend/src/components/asset/AssetForm.vue` | 主要改动文件，集成所有新组件，调整字段顺序和条件渲染 |

**后端无改动**：所有字段已存在于数据库模型和 API schema。

---

## 验收标准

| 场景 | 验收点 |
|------|--------|
| 新建实物资产 | 图片顶部居中；类型 SegmentedControl；分类4列网格内嵌；"同购入价"按钮可用；预期寿命单位年；使用频率图标按钮组；状态字段不显示；标签可添加 |
| 新建金融资产 | 切换类型后显示金融字段（机构/利率/到期日），隐藏实物字段 |
| 编辑已有资产 | 预期寿命天数正确换算为年回显；状态字段显示；标签正确回显 |
| "不限"预期寿命 | 点击"不限"后输入框清空，提交时 `expected_lifespan_days = null` |
| "同购入价"按钮 | 购入价为空时禁用；点击后当前价值同步；可手动修改同步后的值 |
| 标签创建 | 弹窗内输入新标签名称，创建后立即可选中 |
