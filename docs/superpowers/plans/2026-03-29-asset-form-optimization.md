# Asset Form Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize the asset entry form with 8 improvements (P0+P1) to match the reference design, improving interaction efficiency and data accuracy.

**Architecture:** Three new focused sub-components (`CategoryGrid`, `UsageFreqSelector`, `TagSelector`) are extracted and integrated into the existing `AssetForm.vue`. All changes are frontend-only — the backend API and database schema require no modifications.

**Tech Stack:** Vue 3 + TypeScript + Vant 4 + existing `frontend/src/api/tags.ts`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/src/components/asset/AssetForm.vue` | Main form — integrates all sub-components, field order, conditional rendering |
| Create | `frontend/src/components/asset/CategoryGrid.vue` | 4-column icon grid category selector |
| Create | `frontend/src/components/asset/UsageFreqSelector.vue` | 5-option horizontal icon button group |
| Create | `frontend/src/components/asset/TagSelector.vue` | Multi-select tag selector with create support |

---

## Task 1: CategoryGrid.vue — 4-column icon grid

**Files:**
- Create: `frontend/src/components/asset/CategoryGrid.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <div class="category-grid">
    <div v-if="physicalCategories.length" class="category-group">
      <div class="group-label">实物资产</div>
      <div class="grid">
        <div
          v-for="cat in physicalCategories"
          :key="cat.id"
          class="grid-item"
          :class="{ selected: modelValue === cat.id }"
          @click="$emit('update:modelValue', cat.id)"
        >
          <span class="icon">{{ cat.icon }}</span>
          <span class="name">{{ cat.name }}</span>
        </div>
      </div>
    </div>
    <div v-if="financialCategories.length" class="category-group">
      <div class="group-label">金融资产</div>
      <div class="grid">
        <div
          v-for="cat in financialCategories"
          :key="cat.id"
          class="grid-item"
          :class="{ selected: modelValue === cat.id }"
          @click="$emit('update:modelValue', cat.id)"
        >
          <span class="icon">{{ cat.icon }}</span>
          <span class="name">{{ cat.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Category } from '@/types'

const props = defineProps<{
  modelValue: string
  categories: Category[]
  assetType: string
}>()

defineEmits<{ 'update:modelValue': [value: string] }>()

const physicalCategories = computed(() =>
  props.categories.filter(c => c.asset_type === 'physical')
)
const financialCategories = computed(() =>
  props.categories.filter(c => c.asset_type === 'financial')
)
</script>

<style scoped>
.category-grid { padding: 8px 0; }
.category-group { margin-bottom: 8px; }
.group-label {
  font-size: 11px;
  color: var(--van-text-color-3);
  padding: 0 16px 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 0 16px;
}
.grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 10px;
  background: var(--van-background-2);
  border: 1.5px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.grid-item.selected {
  border-color: var(--van-primary-color);
  background: rgba(var(--van-primary-color-rgb, 25, 137, 250), 0.1);
}
.icon { font-size: 22px; }
.name {
  font-size: 10px;
  color: var(--van-text-color-2);
  margin-top: 4px;
  text-align: center;
  line-height: 1.2;
}
.grid-item.selected .name { color: var(--van-primary-color); }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/asset/CategoryGrid.vue
git commit -m "feat: add CategoryGrid component — 4-column icon grid selector"
```

---

## Task 2: UsageFreqSelector.vue — icon button group

**Files:**
- Create: `frontend/src/components/asset/UsageFreqSelector.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <div class="freq-selector">
    <div
      v-for="opt in options"
      :key="opt.value"
      class="freq-item"
      :class="{ selected: modelValue === opt.value }"
      @click="$emit('update:modelValue', opt.value)"
    >
      <span class="icon">{{ opt.icon }}</span>
      <span class="label">{{ opt.label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ modelValue: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()

const options = [
  { value: 'daily',   icon: '📅', label: '每天' },
  { value: 'weekly',  icon: '📆', label: '每周' },
  { value: 'monthly', icon: '🗓️', label: '每月' },
  { value: 'rarely',  icon: '💤', label: '偶尔' },
  { value: 'idle',    icon: '📦', label: '闲置' },
]
</script>

<style scoped>
.freq-selector {
  display: flex;
  gap: 6px;
  padding: 8px 16px;
}
.freq-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 10px;
  background: var(--van-background-2);
  border: 1.5px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.freq-item.selected {
  border-color: var(--van-primary-color);
  background: rgba(var(--van-primary-color-rgb, 25, 137, 250), 0.1);
}
.icon { font-size: 18px; }
.label {
  font-size: 10px;
  color: var(--van-text-color-2);
  margin-top: 4px;
}
.freq-item.selected .label { color: var(--van-primary-color); }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/asset/UsageFreqSelector.vue
git commit -m "feat: add UsageFreqSelector component — horizontal icon button group"
```

---

## Task 3: TagSelector.vue — multi-select with create

**Files:**
- Create: `frontend/src/components/asset/TagSelector.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <div class="tag-selector">
    <div class="selected-tags">
      <van-tag
        v-for="tag in selectedTags"
        :key="tag.id"
        closeable
        type="primary"
        size="medium"
        @close="removeTag(tag.id)"
      >
        {{ tag.name }}
      </van-tag>
      <van-tag plain type="primary" @click="showPopup = true">+ 添加标签</van-tag>
    </div>

    <van-popup v-model:show="showPopup" position="bottom" round :style="{ height: '60%' }">
      <div class="popup-header">
        <span class="popup-title">选择标签</span>
        <van-icon name="cross" @click="showPopup = false" />
      </div>

      <div class="popup-create">
        <van-field
          v-model="newTagName"
          placeholder="输入新标签名称"
          clearable
          :right-icon="newTagName ? 'plus' : ''"
          @click-right-icon="createTag"
        />
      </div>

      <div class="tag-list">
        <div
          v-for="tag in tags"
          :key="tag.id"
          class="tag-option"
          :class="{ selected: modelValue.includes(tag.id) }"
          @click="toggleTag(tag.id)"
        >
          <span>{{ tag.name }}</span>
          <van-icon v-if="modelValue.includes(tag.id)" name="success" />
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { showToast } from 'vant'
import { createTag as apiCreateTag } from '@/api/tags'
import type { Tag } from '@/types'

const props = defineProps<{
  modelValue: string[]
  tags: Tag[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  'tag-created': [tag: Tag]
}>()

const showPopup = ref(false)
const newTagName = ref('')

const selectedTags = computed(() =>
  props.tags.filter(t => props.modelValue.includes(t.id))
)

function toggleTag(id: string) {
  const current = [...props.modelValue]
  const idx = current.indexOf(id)
  if (idx === -1) current.push(id)
  else current.splice(idx, 1)
  emit('update:modelValue', current)
}

function removeTag(id: string) {
  emit('update:modelValue', props.modelValue.filter(t => t !== id))
}

async function createTag() {
  const name = newTagName.value.trim()
  if (!name) return
  try {
    const res = await apiCreateTag({ name, color: '#1989fa' })
    emit('tag-created', res.data)
    emit('update:modelValue', [...props.modelValue, res.data.id])
    newTagName.value = ''
    showToast('标签已创建')
  } catch {
    // error handled by interceptor
  }
}
</script>

<style scoped>
.tag-selector { padding: 8px 16px; }
.selected-tags { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.popup-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px; border-bottom: 1px solid var(--van-border-color);
}
.popup-title { font-size: 16px; font-weight: 600; }
.popup-create { padding: 8px 16px; }
.tag-list { padding: 0 16px; overflow-y: auto; }
.tag-option {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 0; border-bottom: 1px solid var(--van-border-color);
  cursor: pointer; font-size: 14px;
}
.tag-option.selected { color: var(--van-primary-color); }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/asset/TagSelector.vue
git commit -m "feat: add TagSelector component — multi-select with inline create"
```

---

## Task 4: AssetForm.vue — P0 changes (status hide, lifespan unit, same-price button)

**Files:**
- Modify: `frontend/src/components/asset/AssetForm.vue`

This task applies the four P0 changes that don't require new sub-components: hide status on create, lifespan unit years↔days, "same as purchase price" button, and field reordering groundwork.

- [ ] **Step 1: Read the current file**

```bash
cat -n frontend/src/components/asset/AssetForm.vue
```

- [ ] **Step 2: In the `<script setup>` block, add `expected_life_years` ref and computed, and `syncPurchasePrice` helper**

Find the existing `const form = reactive({...})` block and add after it:

```typescript
// Lifespan in years (display only — submitted as days)
const expectedLifeYears = ref<number | null>(null)

watch(expectedLifeYears, (val) => {
  form.expected_lifespan_days = val !== null ? Math.round(val * 365) : null
})

function syncPurchasePrice() {
  if (form.purchase_price) {
    form.current_value = form.purchase_price
  }
}
```

- [ ] **Step 3: In `watchEffect` / `onMounted` where `initialData` is applied, add reverse conversion**

Find the block that sets `form` fields from `initialData` (look for `form.name = initialData.value?.name`) and add:

```typescript
expectedLifeYears.value = initialData.value?.expected_lifespan_days
  ? Math.round(initialData.value.expected_lifespan_days / 365)
  : null
```

- [ ] **Step 4: Replace the status field with `v-if="isEdit"`**

Find:
```vue
<van-field
  v-model="statusDisplay"
  is-link
  readonly
  label="状态"
```

Replace with:
```vue
<van-field
  v-if="isEdit"
  v-model="statusDisplay"
  is-link
  readonly
  label="状态"
```

- [ ] **Step 5: Replace the `expected_lifespan_days` field with years input + "不限" button**

Find:
```vue
<van-field v-model="form.expected_lifespan_days" type="digit" label="预期寿命(天)" placeholder="请输入" />
```

Replace with:
```vue
<van-field
  v-model="expectedLifeYears"
  type="digit"
  label="预期寿命"
  placeholder="请输入年限"
>
  <template #right-icon>
    <van-button
      size="mini"
      plain
      type="primary"
      style="height:24px;padding:0 8px;font-size:11px"
      @click.stop="expectedLifeYears = null"
    >不限</van-button>
  </template>
  <template #extra>
    <span style="font-size:12px;color:var(--van-text-color-2);margin-left:4px">年</span>
  </template>
</van-field>
```

- [ ] **Step 6: Add "同购入价" button to current_value field**

Find:
```vue
<van-field
  v-model="form.current_value"
  type="number"
  label="当前价值"
  placeholder="请输入当前价值"
  :rules="[{ required: true, message: '请输入当前价值' }]"
>
  <template #left-icon>
    <span class="field-prefix">{{ currencySymbol }}</span>
  </template>
</van-field>
```

Replace with:
```vue
<van-field
  v-model="form.current_value"
  type="number"
  label="当前价值"
  placeholder="请输入当前价值"
  :rules="[{ required: true, message: '请输入当前价值' }]"
>
  <template #left-icon>
    <span class="field-prefix">{{ currencySymbol }}</span>
  </template>
  <template #right-icon>
    <van-button
      size="mini"
      plain
      type="primary"
      :disabled="!form.purchase_price"
      style="height:24px;padding:0 8px;font-size:11px"
      @click.stop="syncPurchasePrice"
    >同购入价</van-button>
  </template>
</van-field>
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/asset/AssetForm.vue
git commit -m "feat: P0 — hide status on create, lifespan unit years, same-price button"
```

---

## Task 5: AssetForm.vue — P1 image area + type SegmentedControl

**Files:**
- Modify: `frontend/src/components/asset/AssetForm.vue`

- [ ] **Step 1: Move image upload to top independent section**

Find the entire image upload `<van-field label="图片">` block (inside the first `<van-cell-group inset>`) and replace it with a standalone section placed **before** the first `<van-cell-group inset>`:

```vue
<!-- Image upload — top independent section -->
<div class="image-upload-section">
  <van-uploader
    v-model="fileList"
    :max-count="1"
    :max-size="5 * 1024 * 1024"
    :after-read="afterRead"
    @delete="onDelete"
  >
    <template #default>
      <div v-if="!fileList.length" class="image-placeholder">
        <van-icon name="photograph" size="28" color="var(--van-text-color-3)" />
        <span class="image-hint">添加图片</span>
      </div>
    </template>
  </van-uploader>
</div>
```

Add styles:
```css
.image-upload-section {
  display: flex;
  justify-content: center;
  padding: 16px;
  background: var(--van-background);
}
.image-placeholder {
  width: 76px;
  height: 76px;
  border-radius: 14px;
  border: 2px dashed var(--van-border-color);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.image-hint {
  font-size: 10px;
  color: var(--van-text-color-3);
}
```

- [ ] **Step 2: Replace type Picker with SegmentedControl**

Find the entire type picker block:
```vue
<van-field
  v-model="typeDisplay"
  is-link
  readonly
  label="类型"
  ...
/>
<van-popup v-model:show="showTypePicker" ...>
  <van-picker :columns="typeColumns" ... />
</van-popup>
```

Replace with (place this **before** the first `<van-cell-group inset>`, after the image section):
```vue
<!-- Asset type segmented control -->
<div class="type-segmented">
  <div
    class="type-option"
    :class="{ active: form.asset_type === 'physical' }"
    @click="onTypeChange('physical')"
  >实物资产</div>
  <div
    class="type-option"
    :class="{ active: form.asset_type === 'financial' }"
    @click="onTypeChange('financial')"
  >金融资产</div>
</div>
```

Add the `onTypeChange` method in `<script setup>`:
```typescript
function onTypeChange(type: 'physical' | 'financial') {
  if (form.asset_type === type) return
  form.asset_type = type
  // Clear type-specific fields to avoid dirty data
  if (type === 'financial') {
    form.location = undefined
    form.expected_lifespan_days = undefined
    form.annual_maintenance_cost = undefined
    form.usage_frequency = undefined
    expectedLifeYears.value = null
  } else {
    form.institution = undefined
    form.interest_rate = undefined
    form.maturity_date = undefined
  }
}
```

Add styles:
```css
.type-segmented {
  display: flex;
  margin: 8px 16px;
  background: var(--van-background-2);
  border-radius: 10px;
  padding: 3px;
}
.type-option {
  flex: 1;
  text-align: center;
  padding: 8px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--van-text-color-2);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.type-option.active {
  background: var(--van-primary-color);
  color: #fff;
  font-weight: 600;
}
```

Also remove `showTypePicker` ref and `typeColumns` / `onTypeConfirm` from script since they're no longer needed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/asset/AssetForm.vue
git commit -m "feat: P1 — image area to top, type Picker to SegmentedControl"
```

---

## Task 6: AssetForm.vue — integrate CategoryGrid + UsageFreqSelector + field reorder

**Files:**
- Modify: `frontend/src/components/asset/AssetForm.vue`

- [ ] **Step 1: Add imports at top of `<script setup>`**

```typescript
import CategoryGrid from './CategoryGrid.vue'
import UsageFreqSelector from './UsageFreqSelector.vue'
```

- [ ] **Step 2: Replace category Picker with CategoryGrid**

Find the category picker block:
```vue
<van-field
  v-model="categoryDisplay"
  is-link
  readonly
  label="分类"
  placeholder="选择分类"
  @click="showCategoryPicker = true"
/>
<van-popup v-model:show="showCategoryPicker" position="bottom" round>
  <van-picker
    :columns="categoryColumns"
    @confirm="onCategoryConfirm"
    @cancel="showCategoryPicker = false"
  />
</van-popup>
```

Replace with:
```vue
<van-cell title="分类" />
<CategoryGrid
  v-model="form.category_id"
  :categories="categories"
  :asset-type="form.asset_type"
/>
```

Remove `showCategoryPicker`, `categoryColumns`, `onCategoryConfirm`, `categoryDisplay` from script.

- [ ] **Step 3: Replace usage_frequency Picker with UsageFreqSelector, and reorder physical fields**

Find the physical asset `<van-cell-group>` block and replace its entire contents with the new field order:

```vue
<van-cell-group v-if="form.asset_type === 'physical'" inset title="实物资产信息">
  <!-- 1. 使用频率 -->
  <van-cell title="使用频率" />
  <UsageFreqSelector v-model="form.usage_frequency" />

  <!-- 2. 预期寿命（年） -->
  <van-field
    v-model="expectedLifeYears"
    type="digit"
    label="预期寿命"
    placeholder="请输入年限"
  >
    <template #right-icon>
      <van-button
        size="mini"
        plain
        type="primary"
        style="height:24px;padding:0 8px;font-size:11px"
        @click.stop="expectedLifeYears = null"
      >不限</van-button>
    </template>
    <template #extra>
      <span style="font-size:12px;color:var(--van-text-color-2);margin-left:4px">年</span>
    </template>
  </van-field>

  <!-- 3. 存放位置 -->
  <van-field v-model="form.location" label="存放位置" placeholder="可选" />

  <!-- 4. 年维护费 -->
  <van-field v-model="form.annual_maintenance_cost" type="number" label="年维护费" placeholder="可选">
    <template #left-icon><span class="field-prefix">{{ currencySymbol }}</span></template>
  </van-field>
</van-cell-group>
```

Remove `showUsagePicker`, `usageColumns`, `onUsageConfirm`, `usageDisplay` from script.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/asset/AssetForm.vue
git commit -m "feat: integrate CategoryGrid + UsageFreqSelector, reorder physical fields"
```

---

## Task 7: AssetForm.vue — integrate TagSelector

**Files:**
- Modify: `frontend/src/components/asset/AssetForm.vue`

- [ ] **Step 1: Add imports and tag state**

In `<script setup>`, add:
```typescript
import TagSelector from './TagSelector.vue'
import { getTags } from '@/api/tags'
import type { Tag } from '@/types'

const availableTags = ref<Tag[]>([])
const selectedTagIds = ref<string[]>([])

async function fetchTags() {
  const res = await getTags()
  availableTags.value = res.data
}

function onTagCreated(tag: Tag) {
  availableTags.value.push(tag)
}
```

- [ ] **Step 2: Load tags on mount and populate from initialData**

In `onMounted`:
```typescript
fetchTags()
```

In the block that applies `initialData`:
```typescript
selectedTagIds.value = initialData.value?.tags?.map(t => t.id) ?? []
```

- [ ] **Step 3: Include tag_ids in submit payload**

Find the `onSubmit` function (or the data object passed to `assetStore.createAsset` / `updateAsset`) and add:
```typescript
tag_ids: selectedTagIds.value
```

- [ ] **Step 4: Replace the "其他" cell-group with tags + notes section**

Find:
```vue
<van-cell-group inset title="其他">
  <van-field v-model="form.notes" type="textarea" label="备注" placeholder="请输入备注" rows="2" autosize />
</van-cell-group>
```

Replace with:
```vue
<van-cell-group inset title="标签与备注">
  <van-cell title="标签">
    <template #value>
      <TagSelector
        v-model="selectedTagIds"
        :tags="availableTags"
        @tag-created="onTagCreated"
      />
    </template>
  </van-cell>
  <van-field v-model="form.notes" type="textarea" label="备注" placeholder="可选" rows="2" autosize />
</van-cell-group>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/asset/AssetForm.vue
git commit -m "feat: integrate TagSelector — multi-select tags with inline create"
```

---

## Task 8: Smoke test in browser

- [ ] **Step 1: Rebuild the frontend Docker image and restart**

```bash
cd /Users/vincentruan/geek_space/github/numina
docker-compose build frontend && docker-compose up -d frontend
```

Wait ~30 seconds for the build to complete.

- [ ] **Step 2: Open the asset form and verify all P0 items**

Navigate to `http://localhost/numina/assets/new` and check:

| Check | Expected |
|-------|----------|
| Image area | Centered 76px box at top, camera icon + "添加图片" |
| Type selector | Two-tab SegmentedControl "实物资产 / 金融资产" |
| Category | 4-column icon grid visible inline, no Picker popup |
| Current value | "同购入价" button on right; disabled when purchase price empty |
| Physical section | Field order: 使用频率 → 预期寿命(年) → 存放位置 → 年维护费 |
| Usage frequency | 5 icon buttons horizontal, no Picker popup |
| Status field | Not visible on new asset form |
| Tags section | Chip list + "+ 添加标签" button |

- [ ] **Step 3: Verify edit mode**

Navigate to an existing asset's edit page and check:

| Check | Expected |
|-------|----------|
| Status field | Visible in basic info section |
| Lifespan | Shows years (e.g. "3" not "1095") |
| Tags | Pre-selected tags shown as chips |

- [ ] **Step 4: Verify financial asset type**

Switch to "金融资产" and check:
- Physical fields hidden (使用频率, 预期寿命, 存放位置, 年维护费)
- Financial fields shown (金融机构, 利率, 到期日期)

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add -p
git commit -m "fix: asset form smoke test fixes"
```
