# 盲盒礼物系统前端实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现盲盒礼物系统前端（父母礼物池管理、孩子抽奖页面、配置管理）

**Architecture:** 新增 API 模块 + 4个页面组件 + 抽奖动画组件 + Pinia store + 路由配置

**Tech Stack:** Vue 3, TypeScript, Naive UI, Pinia, Vue Router, Vite

---

## 文件结构

**新增文件：**
- `frontend/src/api/blindBox.ts` — API 客户端（父母端 + 孩子端）
- `frontend/src/stores/blindBox.ts` — Pinia store（礼物池、配置、抽奖记录）
- `frontend/src/types/blindBox.ts` — TypeScript 类型定义
- `frontend/src/pages/BlindBoxGiftListPage.vue` — 父母端：礼物池列表
- `frontend/src/pages/BlindBoxGiftFormPage.vue` — 父母端：添加/编辑礼物
- `frontend/src/pages/BlindBoxConfigPage.vue` — 父母端：配置管理
- `frontend/src/pages/ChildBlindBoxPage.vue` — 孩子端：抽奖页面
- `frontend/src/components/blindBox/DrawAnimation.vue` — 抽奖动画组件
- `frontend/src/components/blindBox/GiftCard.vue` — 礼物卡片组件
- `frontend/src/components/blindBox/DrawHistoryList.vue` — 抽奖历史列表组件

**修改文件：**
- `frontend/src/router/index.ts` — 新增路由
- `frontend/src/layouts/MainLayout.vue` — 新增底部导航项（可选）

---

## Task 1: TypeScript 类型定义

**Files:**
- Create: `frontend/src/types/blindBox.ts`

- [ ] **Step 1: 实现类型定义**

```typescript
// frontend/src/types/blindBox.ts
export interface BlindBoxGift {
  id: number
  family_id: number
  name: string
  description: string | null
  emoji: string | null
  value_score: number
  source_wish_id: number | null
  is_active: boolean
  created_by: number
  created_at: string
  updated_at: string
}

export interface BlindBoxGiftCreate {
  name: string
  description?: string | null
  emoji?: string | null
  value_score: number
  source_wish_id?: number | null
}

export interface BlindBoxGiftUpdate {
  name?: string
  description?: string | null
  emoji?: string | null
  value_score?: number
  is_active?: boolean
}

export interface BlindBoxDraw {
  id: number
  family_id: number
  child_user_id: number
  coins_spent: number
  gift_id: number
  gift_name: string
  gift_emoji: string | null
  is_surprise: boolean
  is_bonus: boolean
  status: 'pending_fulfillment' | 'fulfilled'
  draw_at: string
  fulfilled_at: string | null
}

export interface DrawRequest {
  coins_spent: number
}

export interface BlindBoxConfig {
  id: number
  family_id: number
  enabled: boolean
  base_draw_prob: number
  special_day_prob: number
  weight_scale: number
  surprise_threshold_coins: number
  surprise_prob_normal: number
  surprise_prob_parent_bday: number
  surprise_prob_sibling_bday: number
}

export interface BlindBoxConfigUpdate {
  enabled?: boolean
  base_draw_prob?: number
  special_day_prob?: number
  weight_scale?: number
  surprise_threshold_coins?: number
  surprise_prob_normal?: number
  surprise_prob_parent_bday?: number
  surprise_prob_sibling_bday?: number
}
```

- [ ] **Step 2: 验证类型文件无语法错误**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/types/blindBox.ts
git commit -m "feat(blind-box): add TypeScript type definitions"
```

---

## Task 2: API 客户端模块

**Files:**
- Create: `frontend/src/api/blindBox.ts`

- [ ] **Step 1: 实现 API 客户端**

```typescript
// frontend/src/api/blindBox.ts
import request from './index'
import type {
  BlindBoxGift,
  BlindBoxGiftCreate,
  BlindBoxGiftUpdate,
  BlindBoxDraw,
  DrawRequest,
  BlindBoxConfig,
  BlindBoxConfigUpdate,
} from '@/types/blindBox'

// ── 父母端 API ────────────────────────────────────────────────────────────────

export function getGifts() {
  return request.get<BlindBoxGift[]>('/blind-box/gifts')
}

export function createGift(data: BlindBoxGiftCreate) {
  return request.post<BlindBoxGift>('/blind-box/gifts', data)
}

export function updateGift(id: number, data: BlindBoxGiftUpdate) {
  return request.put<BlindBoxGift>(`/blind-box/gifts/${id}`, data)
}

export function deleteGift(id: number) {
  return request.delete(`/blind-box/gifts/${id}`)
}

export function getDraws() {
  return request.get<BlindBoxDraw[]>('/blind-box/draws')
}

export function fulfillDraw(id: number) {
  return request.put<BlindBoxDraw>(`/blind-box/draws/${id}/fulfill`)
}

export function getConfig() {
  return request.get<BlindBoxConfig>('/blind-box/config')
}

export function updateConfig(data: BlindBoxConfigUpdate) {
  return request.put<BlindBoxConfig>('/blind-box/config', data)
}

// ── 孩子端 API ────────────────────────────────────────────────────────────────

export function childDraw(data: DrawRequest) {
  return request.post<BlindBoxDraw>('/child/blind-box/draw', data)
}

export function childGetDraws() {
  return request.get<BlindBoxDraw[]>('/child/blind-box/draws')
}
```

- [ ] **Step 2: 验证类型检查通过**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/blindBox.ts
git commit -m "feat(blind-box): add API client for parent and child endpoints"
```

---

## Task 3: Pinia Store

**Files:**
- Create: `frontend/src/stores/blindBox.ts`

- [ ] **Step 1: 实现 Pinia store**

```typescript
// frontend/src/stores/blindBox.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as blindBoxApi from '@/api/blindBox'
import type {
  BlindBoxGift,
  BlindBoxGiftCreate,
  BlindBoxGiftUpdate,
  BlindBoxDraw,
  DrawRequest,
  BlindBoxConfig,
  BlindBoxConfigUpdate,
} from '@/types/blindBox'

export const useBlindBoxStore = defineStore('blindBox', () => {
  const gifts = ref<BlindBoxGift[]>([])
  const draws = ref<BlindBoxDraw[]>([])
  const config = ref<BlindBoxConfig | null>(null)
  const loading = ref(false)

  // ── 父母端：礼物池管理 ──────────────────────────────────────────────────────

  async function fetchGifts() {
    loading.value = true
    try {
      const data = await blindBoxApi.getGifts()
      gifts.value = data
    } finally {
      loading.value = false
    }
  }

  async function createGift(payload: BlindBoxGiftCreate) {
    const gift = await blindBoxApi.createGift(payload)
    gifts.value.push(gift)
    return gift
  }

  async function updateGift(id: number, payload: BlindBoxGiftUpdate) {
    const updated = await blindBoxApi.updateGift(id, payload)
    const index = gifts.value.findIndex((g) => g.id === id)
    if (index !== -1) {
      gifts.value[index] = updated
    }
    return updated
  }

  async function deleteGift(id: number) {
    await blindBoxApi.deleteGift(id)
    gifts.value = gifts.value.filter((g) => g.id !== id)
  }

  // ── 父母端：抽奖记录管理 ────────────────────────────────────────────────────

  async function fetchDraws() {
    loading.value = true
    try {
      const data = await blindBoxApi.getDraws()
      draws.value = data
    } finally {
      loading.value = false
    }
  }

  async function fulfillDraw(id: number) {
    const updated = await blindBoxApi.fulfillDraw(id)
    const index = draws.value.findIndex((d) => d.id === id)
    if (index !== -1) {
      draws.value[index] = updated
    }
    return updated
  }

  // ── 父母端：配置管理 ────────────────────────────────────────────────────────

  async function fetchConfig() {
    loading.value = true
    try {
      const data = await blindBoxApi.getConfig()
      config.value = data
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(payload: BlindBoxConfigUpdate) {
    const updated = await blindBoxApi.updateConfig(payload)
    config.value = updated
    return updated
  }

  // ── 孩子端：抽奖 ────────────────────────────────────────────────────────────

  async function childDraw(payload: DrawRequest) {
    const draw = await blindBoxApi.childDraw(payload)
    draws.value.unshift(draw)
    return draw
  }

  async function childFetchDraws() {
    loading.value = true
    try {
      const data = await blindBoxApi.childGetDraws()
      draws.value = data
    } finally {
      loading.value = false
    }
  }

  return {
    gifts,
    draws,
    config,
    loading,
    fetchGifts,
    createGift,
    updateGift,
    deleteGift,
    fetchDraws,
    fulfillDraw,
    fetchConfig,
    updateConfig,
    childDraw,
    childFetchDraws,
  }
})
```

- [ ] **Step 2: 验证类型检查通过**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/stores/blindBox.ts
git commit -m "feat(blind-box): add Pinia store for gifts/draws/config"
```

---

## Task 4: 抽奖动画组件

**Files:**
- Create: `frontend/src/components/blindBox/DrawAnimation.vue`

动画流程：点击抽奖 → 盲盒摇晃动画（1.5s）→ 开盖爆炸效果（0.5s）→ 礼物展示卡片（带惊喜标识）

- [ ] **Step 1: 实现动画组件**

```vue
<!-- frontend/src/components/blindBox/DrawAnimation.vue -->
<template>
  <div class="draw-animation">
    <!-- 待机状态：盲盒图标 -->
    <Transition name="box-fade">
      <div v-if="state === 'idle'" class="box-idle" @click="$emit('draw')">
        <div class="box-icon">🎁</div>
        <p class="hint-text">点击抽取盲盒</p>
      </div>
    </Transition>

    <!-- 摇晃动画 -->
    <Transition name="box-fade">
      <div v-if="state === 'shaking'" class="box-shaking">
        <div class="box-icon shake-anim">🎁</div>
        <p class="hint-text">正在抽取...</p>
      </div>
    </Transition>

    <!-- 礼物展示 -->
    <Transition name="gift-reveal">
      <div v-if="state === 'revealed' && result" class="gift-reveal">
        <div class="gift-emoji">{{ result.gift_emoji || '🎀' }}</div>
        <h2 class="gift-name">{{ result.gift_name }}</h2>
        <n-tag v-if="result.is_surprise" type="warning" size="large" round>
          ✨ 超预期惊喜！
        </n-tag>
        <n-tag v-else type="success" size="large" round>
          🎉 恭喜获得
        </n-tag>
        <p class="status-hint">等待父母兑现</p>
        <n-button class="draw-again-btn" @click="reset">再抽一次</n-button>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { BlindBoxDraw } from '@/types/blindBox'

defineEmits<{ draw: [] }>()

const state = ref<'idle' | 'shaking' | 'revealed'>('idle')
const result = ref<BlindBoxDraw | null>(null)

function startShaking() {
  state.value = 'shaking'
}

function showResult(draw: BlindBoxDraw) {
  result.value = draw
  state.value = 'revealed'
}

function reset() {
  result.value = null
  state.value = 'idle'
}

defineExpose({ startShaking, showResult, reset })
</script>

<style scoped>
.draw-animation {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  gap: 16px;
}

.box-icon {
  font-size: 80px;
  cursor: pointer;
  user-select: none;
  transition: transform 0.1s;
}

.box-icon:hover {
  transform: scale(1.05);
}

.hint-text {
  color: #888;
  font-size: 14px;
  margin: 0;
}

.gift-reveal {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.gift-emoji {
  font-size: 72px;
  animation: pop-in 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.gift-name {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
}

.status-hint {
  color: #aaa;
  font-size: 13px;
  margin: 0;
}

.draw-again-btn {
  margin-top: 8px;
}

/* 摇晃动画 */
@keyframes shake {
  0%, 100% { transform: rotate(0deg); }
  15% { transform: rotate(-15deg); }
  30% { transform: rotate(15deg); }
  45% { transform: rotate(-12deg); }
  60% { transform: rotate(12deg); }
  75% { transform: rotate(-8deg); }
  90% { transform: rotate(8deg); }
}

.shake-anim {
  animation: shake 0.8s ease-in-out infinite;
}

/* 礼物弹出动画 */
@keyframes pop-in {
  0% { transform: scale(0) rotate(-10deg); opacity: 0; }
  100% { transform: scale(1) rotate(0deg); opacity: 1; }
}

/* Vue Transition */
.box-fade-enter-active,
.box-fade-leave-active {
  transition: opacity 0.3s;
}
.box-fade-enter-from,
.box-fade-leave-to {
  opacity: 0;
}

.gift-reveal-enter-active {
  transition: all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.gift-reveal-enter-from {
  opacity: 0;
  transform: scale(0.5);
}
</style>
```

- [ ] **Step 2: 验证构建通过**

```bash
cd frontend
npm run build
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/blindBox/DrawAnimation.vue
git commit -m "feat(blind-box): add draw animation component with shake and reveal effects"
```

---

## Task 5: GiftCard + DrawHistoryList 组件

**Files:**
- Create: `frontend/src/components/blindBox/GiftCard.vue`
- Create: `frontend/src/components/blindBox/DrawHistoryList.vue`

- [ ] **Step 1: 实现 GiftCard 组件**

```vue
<!-- frontend/src/components/blindBox/GiftCard.vue -->
<template>
  <n-card class="gift-card" :bordered="true" size="small">
    <div class="gift-card-inner">
      <span class="gift-emoji">{{ gift.emoji || '🎁' }}</span>
      <div class="gift-info">
        <div class="gift-name">{{ gift.name }}</div>
        <div class="gift-desc" v-if="gift.description">{{ gift.description }}</div>
        <n-rate :value="gift.value_score / 2" :count="5" readonly size="small" />
      </div>
      <div class="gift-actions" v-if="showActions">
        <n-button size="small" @click="$emit('edit', gift)">编辑</n-button>
        <n-button size="small" type="error" @click="$emit('delete', gift.id)">删除</n-button>
      </div>
    </div>
  </n-card>
</template>

<script setup lang="ts">
import type { BlindBoxGift } from '@/types/blindBox'

defineProps<{
  gift: BlindBoxGift
  showActions?: boolean
}>()

defineEmits<{
  edit: [gift: BlindBoxGift]
  delete: [id: number]
}>()
</script>

<style scoped>
.gift-card {
  margin-bottom: 8px;
}
.gift-card-inner {
  display: flex;
  align-items: center;
  gap: 12px;
}
.gift-emoji {
  font-size: 32px;
  flex-shrink: 0;
}
.gift-info {
  flex: 1;
  min-width: 0;
}
.gift-name {
  font-weight: 600;
  font-size: 15px;
}
.gift-desc {
  font-size: 12px;
  color: #888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gift-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
</style>
```

- [ ] **Step 2: 实现 DrawHistoryList 组件**

```vue
<!-- frontend/src/components/blindBox/DrawHistoryList.vue -->
<template>
  <div class="draw-history">
    <n-empty v-if="draws.length === 0" description="暂无抽奖记录" />
    <n-list v-else>
      <n-list-item v-for="draw in draws" :key="draw.id">
        <div class="draw-item">
          <span class="draw-emoji">{{ draw.gift_emoji || '🎁' }}</span>
          <div class="draw-info">
            <div class="draw-name">{{ draw.gift_name }}</div>
            <div class="draw-meta">
              <n-tag size="small" :type="draw.is_surprise ? 'warning' : 'default'">
                {{ draw.is_surprise ? '✨ 惊喜' : '普通' }}
              </n-tag>
              <n-tag size="small" :type="draw.status === 'fulfilled' ? 'success' : 'info'">
                {{ draw.status === 'fulfilled' ? '已兑现' : '待兑现' }}
              </n-tag>
              <span class="draw-time">{{ formatDate(draw.draw_at) }}</span>
            </div>
          </div>
          <n-button
            v-if="showFulfill && draw.status === 'pending_fulfillment'"
            size="small"
            type="primary"
            @click="$emit('fulfill', draw.id)"
          >
            兑现
          </n-button>
        </div>
      </n-list-item>
    </n-list>
  </div>
</template>

<script setup lang="ts">
import type { BlindBoxDraw } from '@/types/blindBox'

defineProps<{
  draws: BlindBoxDraw[]
  showFulfill?: boolean
}>()

defineEmits<{ fulfill: [id: number] }>()

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.draw-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.draw-emoji {
  font-size: 28px;
  flex-shrink: 0;
}
.draw-info {
  flex: 1;
  min-width: 0;
}
.draw-name {
  font-weight: 600;
  font-size: 14px;
}
.draw-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.draw-time {
  font-size: 12px;
  color: #aaa;
}
</style>
```

- [ ] **Step 3: 验证构建通过**

```bash
cd frontend
npm run build
```

预期：无错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/blindBox/GiftCard.vue frontend/src/components/blindBox/DrawHistoryList.vue
git commit -m "feat(blind-box): add GiftCard and DrawHistoryList components"
```

---

## Task 6: 父母端 — 礼物池列表页面

**Files:**
- Create: `frontend/src/pages/BlindBoxGiftListPage.vue`

功能：展示礼物池列表、删除礼物、跳转添加/编辑、查看抽奖历史（含兑现操作）

- [ ] **Step 1: 实现页面**

```vue
<!-- frontend/src/pages/BlindBoxGiftListPage.vue -->
<template>
  <div class="page">
    <n-page-header title="礼物池管理" @back="router.back()">
      <template #extra>
        <n-button type="primary" @click="router.push('/blind-box/gifts/new')">
          + 添加礼物
        </n-button>
      </template>
    </n-page-header>

    <n-tabs v-model:value="activeTab" type="line" animated>
      <!-- 礼物池 Tab -->
      <n-tab-pane name="gifts" tab="礼物池">
        <n-spin :show="store.loading">
          <n-empty v-if="store.gifts.length === 0" description="礼物池为空，快去添加礼物吧" />
          <GiftCard
            v-for="gift in store.gifts"
            :key="gift.id"
            :gift="gift"
            :show-actions="true"
            @edit="handleEdit"
            @delete="handleDelete"
          />
        </n-spin>
      </n-tab-pane>

      <!-- 抽奖历史 Tab -->
      <n-tab-pane name="history" tab="抽奖历史">
        <n-spin :show="store.loading">
          <DrawHistoryList
            :draws="store.draws"
            :show-fulfill="true"
            @fulfill="handleFulfill"
          />
        </n-spin>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import { useBlindBoxStore } from '@/stores/blindBox'
import GiftCard from '@/components/blindBox/GiftCard.vue'
import DrawHistoryList from '@/components/blindBox/DrawHistoryList.vue'
import type { BlindBoxGift } from '@/types/blindBox'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const store = useBlindBoxStore()
const activeTab = ref('gifts')

onMounted(async () => {
  await Promise.all([store.fetchGifts(), store.fetchDraws()])
})

function handleEdit(gift: BlindBoxGift) {
  router.push(`/blind-box/gifts/${gift.id}/edit`)
}

function handleDelete(id: number) {
  dialog.warning({
    title: '确认删除',
    content: '删除后礼物将从礼物池中移除，确认继续？',
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      await store.deleteGift(id)
      message.success('礼物已删除')
    },
  })
}

async function handleFulfill(id: number) {
  await store.fulfillDraw(id)
  message.success('已标记为兑现')
}
</script>

<style scoped>
.page {
  padding: 16px;
  max-width: 600px;
  margin: 0 auto;
}
</style>
```

- [ ] **Step 2: 验证构建通过**

```bash
cd frontend
npm run build
```

预期：无错误（路由未注册时可能有警告，Task 9 统一注册）

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/BlindBoxGiftListPage.vue
git commit -m "feat(blind-box): add parent gift list page with history and fulfill"
```

---

## Task 7: 父母端 — 礼物添加/编辑表单页

**Files:**
- Create: `frontend/src/pages/BlindBoxGiftFormPage.vue`

- [ ] **Step 1: 实现表单页**

```vue
<!-- frontend/src/pages/BlindBoxGiftFormPage.vue -->
<template>
  <div class="page">
    <n-page-header :title="isEdit ? '编辑礼物' : '添加礼物'" @back="router.back()" />

    <n-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-placement="top"
      style="margin-top: 16px"
    >
      <n-form-item label="礼物名称" path="name">
        <n-input v-model:value="form.name" placeholder="例如：乐高积木" maxlength="100" />
      </n-form-item>

      <n-form-item label="Emoji 图标" path="emoji">
        <n-input v-model:value="form.emoji" placeholder="例如：🧱" maxlength="10" />
      </n-form-item>

      <n-form-item label="描述（可选）" path="description">
        <n-input
          v-model:value="form.description"
          type="textarea"
          placeholder="礼物的简短描述"
          maxlength="200"
          :rows="2"
        />
      </n-form-item>

      <n-form-item label="稀有度（1=常见，10=稀有）" path="value_score">
        <n-slider v-model:value="form.value_score" :min="1" :max="10" :step="1" :marks="sliderMarks" />
      </n-form-item>

      <n-form-item>
        <n-button
          type="primary"
          block
          :loading="submitting"
          @click="handleSubmit"
        >
          {{ isEdit ? '保存修改' : '添加礼物' }}
        </n-button>
      </n-form-item>
    </n-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import type { FormInst, FormRules } from 'naive-ui'
import { useBlindBoxStore } from '@/stores/blindBox'

const router = useRouter()
const route = useRoute()
const message = useMessage()
const store = useBlindBoxStore()

const formRef = ref<FormInst | null>(null)
const submitting = ref(false)

const isEdit = computed(() => route.params.id !== 'new' && !!route.params.id)

const form = reactive({
  name: '',
  emoji: '',
  description: '',
  value_score: 5,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入礼物名称', trigger: 'blur' }],
  value_score: [{ required: true, type: 'number', message: '请设置稀有度' }],
}

const sliderMarks = { 1: '常见', 5: '普通', 10: '稀有' }

onMounted(async () => {
  if (isEdit.value) {
    await store.fetchGifts()
    const gift = store.gifts.find((g) => g.id === Number(route.params.id))
    if (gift) {
      form.name = gift.name
      form.emoji = gift.emoji ?? ''
      form.description = gift.description ?? ''
      form.value_score = gift.value_score
    }
  }
})

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      emoji: form.emoji || null,
      description: form.description || null,
      value_score: form.value_score,
    }
    if (isEdit.value) {
      await store.updateGift(Number(route.params.id), payload)
      message.success('礼物已更新')
    } else {
      await store.createGift(payload)
      message.success('礼物已添加')
    }
    router.back()
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.page {
  padding: 16px;
  max-width: 500px;
  margin: 0 auto;
}
</style>
```

- [ ] **Step 2: 验证构建通过**

```bash
cd frontend
npm run build
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/BlindBoxGiftFormPage.vue
git commit -m "feat(blind-box): add gift create/edit form page"
```

---

## Task 8: 父母端 — 配置管理页面

**Files:**
- Create: `frontend/src/pages/BlindBoxConfigPage.vue`

- [ ] **Step 1: 实现配置页**

```vue
<!-- frontend/src/pages/BlindBoxConfigPage.vue -->
<template>
  <div class="page">
    <n-page-header title="盲盒配置" @back="router.back()" />

    <n-spin :show="store.loading" style="margin-top: 16px">
      <n-form v-if="store.config" label-placement="left" label-width="160px">
        <n-form-item label="启用盲盒功能">
          <n-switch v-model:value="draft.enabled" />
        </n-form-item>

        <n-divider>抽奖概率</n-divider>

        <n-form-item label="普通日触发概率">
          <n-input-number
            v-model:value="draft.base_draw_prob"
            :min="0" :max="1" :step="0.05" :precision="2"
          />
          <span class="unit">（0~1）</span>
        </n-form-item>

        <n-form-item label="特殊日触发概率">
          <n-input-number
            v-model:value="draft.special_day_prob"
            :min="0" :max="1" :step="0.05" :precision="2"
          />
          <span class="unit">（生日/节日）</span>
        </n-form-item>

        <n-divider>权重算法</n-divider>

        <n-form-item label="稀有度权重系数">
          <n-input-number
            v-model:value="draft.weight_scale"
            :min="0.1" :max="10" :step="0.1" :precision="1"
          />
          <span class="unit">（越大越稀有）</span>
        </n-form-item>

        <n-divider>惊喜升级概率</n-divider>

        <n-form-item label="普通情况">
          <n-input-number
            v-model:value="draft.surprise_prob_normal"
            :min="0" :max="1" :step="0.01" :precision="2"
          />
        </n-form-item>

        <n-form-item label="父母生日当天">
          <n-input-number
            v-model:value="draft.surprise_prob_parent_bday"
            :min="0" :max="1" :step="0.05" :precision="2"
          />
        </n-form-item>

        <n-form-item label="兄弟姐妹生日">
          <n-input-number
            v-model:value="draft.surprise_prob_sibling_bday"
            :min="0" :max="1" :step="0.05" :precision="2"
          />
        </n-form-item>

        <n-form-item>
          <n-button type="primary" block :loading="saving" @click="handleSave">
            保存配置
          </n-button>
        </n-form-item>
      </n-form>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useBlindBoxStore } from '@/stores/blindBox'

const router = useRouter()
const message = useMessage()
const store = useBlindBoxStore()
const saving = ref(false)

const draft = reactive({
  enabled: true,
  base_draw_prob: 0.3,
  special_day_prob: 0.8,
  weight_scale: 2.0,
  surprise_prob_normal: 0.05,
  surprise_prob_parent_bday: 0.6,
  surprise_prob_sibling_bday: 0.5,
})

onMounted(async () => {
  await store.fetchConfig()
  if (store.config) {
    Object.assign(draft, store.config)
  }
})

watch(() => store.config, (cfg) => {
  if (cfg) Object.assign(draft, cfg)
})

async function handleSave() {
  saving.value = true
  try {
    await store.updateConfig({ ...draft })
    message.success('配置已保存')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.page {
  padding: 16px;
  max-width: 560px;
  margin: 0 auto;
}
.unit {
  margin-left: 8px;
  font-size: 12px;
  color: #aaa;
  white-space: nowrap;
}
</style>
```

- [ ] **Step 2: 验证构建通过**

```bash
cd frontend
npm run build
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/BlindBoxConfigPage.vue
git commit -m "feat(blind-box): add blind box config management page"
```

---

## Task 9: 孩子端 — 抽奖页面

**Files:**
- Create: `frontend/src/pages/ChildBlindBoxPage.vue`

功能：抽奖按钮触发动画 → 调用 API → 展示结果 → 历史记录列表

- [ ] **Step 1: 实现孩子端抽奖页**

```vue
<!-- frontend/src/pages/ChildBlindBoxPage.vue -->
<template>
  <div class="page">
    <n-page-header title="我的盲盒" />

    <n-tabs v-model:value="activeTab" type="line" animated>
      <!-- 抽奖 Tab -->
      <n-tab-pane name="draw" tab="🎁 抽奖">
        <div class="draw-section">
          <DrawAnimation ref="animRef" @draw="handleDraw" />

          <div class="coins-row">
            <n-input-number
              v-model:value="coinsToSpend"
              :min="0"
              :step="10"
              placeholder="消耗金币数"
              style="width: 160px"
            />
            <span class="coins-label">金币</span>
          </div>

          <n-alert v-if="errorMsg" type="error" :title="errorMsg" style="margin-top: 12px" />
        </div>
      </n-tab-pane>

      <!-- 历史 Tab -->
      <n-tab-pane name="history" tab="📋 记录">
        <n-spin :show="store.loading">
          <DrawHistoryList :draws="store.draws" :show-fulfill="false" />
        </n-spin>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useBlindBoxStore } from '@/stores/blindBox'
import DrawAnimation from '@/components/blindBox/DrawAnimation.vue'
import DrawHistoryList from '@/components/blindBox/DrawHistoryList.vue'

const store = useBlindBoxStore()
const animRef = ref<InstanceType<typeof DrawAnimation> | null>(null)
const activeTab = ref('draw')
const coinsToSpend = ref(0)
const errorMsg = ref('')

onMounted(() => {
  store.childFetchDraws()
})

async function handleDraw() {
  errorMsg.value = ''
  animRef.value?.startShaking()
  try {
    const draw = await store.childDraw({ coins_spent: coinsToSpend.value })
    // 短暂延迟让摇晃动画播放完
    await new Promise((r) => setTimeout(r, 1200))
    animRef.value?.showResult(draw)
  } catch (e: unknown) {
    animRef.value?.reset()
    const msg = (e as { response?: { data?: { detail?: string } } })
      ?.response?.data?.detail
    errorMsg.value = msg ?? '抽奖失败，请稍后重试'
  }
}
</script>

<style scoped>
.page {
  padding: 16px;
  max-width: 500px;
  margin: 0 auto;
}
.draw-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 24px 0;
}
.coins-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.coins-label {
  font-size: 14px;
  color: #666;
}
</style>
```

- [ ] **Step 2: 验证构建通过**

```bash
cd frontend
npm run build
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/ChildBlindBoxPage.vue
git commit -m "feat(blind-box): add child draw page with animation and history"
```

---

## Task 10: 路由注册 + 全量验证

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 注册所有盲盒路由**

```typescript
// frontend/src/router/index.ts (在现有路由数组中追加)
{
  path: '/blind-box/gifts',
  component: () => import('@/pages/BlindBoxGiftListPage.vue'),
  meta: { requiresAuth: true },
},
{
  path: '/blind-box/gifts/new',
  component: () => import('@/pages/BlindBoxGiftFormPage.vue'),
  meta: { requiresAuth: true },
},
{
  path: '/blind-box/gifts/:id/edit',
  component: () => import('@/pages/BlindBoxGiftFormPage.vue'),
  meta: { requiresAuth: true },
},
{
  path: '/blind-box/config',
  component: () => import('@/pages/BlindBoxConfigPage.vue'),
  meta: { requiresAuth: true },
},
{
  path: '/child/blind-box',
  component: () => import('@/pages/ChildBlindBoxPage.vue'),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 2: 全量类型检查**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无错误

- [ ] **Step 3: 全量构建验证**

```bash
cd frontend
npm run build
```

预期：构建成功，无错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/router/index.ts
git commit -m "feat(blind-box): register all blind box routes"
```

---

## 验收标准

完成所有 Task 后，执行以下验收检查：

```bash
cd frontend

# 1. 类型检查通过
npx vue-tsc --noEmit

# 2. 构建通过
npm run build

# 3. Lint 通过
npm run lint
```

**手动验收路径（需后端运行）：**

| 角色 | 路径 | 验收点 |
|------|------|--------|
| 父母 | `/blind-box/gifts` | 礼物列表展示、删除确认弹窗 |
| 父母 | `/blind-box/gifts/new` | 表单验证、添加成功跳回列表 |
| 父母 | `/blind-box/gifts/:id/edit` | 回填数据、保存成功 |
| 父母 | `/blind-box/config` | 配置读取、保存成功提示 |
| 父母 | `/blind-box/gifts`（历史Tab）| 抽奖记录展示、兑现按钮 |
| 孩子 | `/child/blind-box` | 点击抽奖触发摇晃动画、展示礼物结果 |
| 孩子 | `/child/blind-box`（记录Tab）| 历史记录列表 |

---

## 实现顺序总结

| Task | 内容 | 依赖 |
|------|------|------|
| 1 | TypeScript 类型定义 | — |
| 2 | API 客户端 | Task 1 |
| 3 | Pinia Store | Task 1, 2 |
| 4 | 抽奖动画组件 | Task 1 |
| 5 | GiftCard + DrawHistoryList | Task 1 |
| 6 | 父母礼物池列表页 | Task 3, 5 |
| 7 | 礼物添加/编辑表单页 | Task 3 |
| 8 | 配置管理页 | Task 3 |
| 9 | 孩子抽奖页 | Task 3, 4, 5 |
| 10 | 路由注册 + 全量验证 | Task 6-9 |

---

## ⚠️ 补充章节：Spec 遗漏修正

以下 Task 11-14 补充原计划遗漏的关键功能。

---

## Task 11: 修正孩子端抽奖 — 选择 ChoreInstance 而非输入金币

**背景：** 孩子抽奖不应手动输入金币数，而是从已批准的 ChoreInstance 列表中勾选，系统自动累计金币。

**Files:**
- Modify: `frontend/src/api/blindBox.ts` (修改 DrawRequest 类型)
- Modify: `frontend/src/types/blindBox.ts` (修改 DrawRequest)
- Modify: `frontend/src/pages/ChildBlindBoxPage.vue` (重写抽奖交互)
- Create: `frontend/src/components/blindBox/ChoreInstancePicker.vue`

- [ ] **Step 1: 修改 DrawRequest 类型**

```typescript
// frontend/src/types/blindBox.ts — 替换 DrawRequest
export interface DrawRequest {
  chore_instance_ids: number[]
}

// 新增 ChoreInstance 类型（用于选择器）
export interface ChoreInstanceForDraw {
  id: number
  chore_name: string
  coins_reward: number
  approved_at: string
}
```

- [ ] **Step 2: 新增获取可用 ChoreInstance 的 API**

```typescript
// frontend/src/api/blindBox.ts (追加)
import type { ChoreInstanceForDraw } from '@/types/blindBox'

export function getAvailableChoreInstances() {
  // 获取当前孩子已批准且未消耗的 ChoreInstance
  return request.get<ChoreInstanceForDraw[]>('/child/chore-instances/available-for-draw')
}
```

- [ ] **Step 3: 实现 ChoreInstancePicker 组件**

```vue
<!-- frontend/src/components/blindBox/ChoreInstancePicker.vue -->
<template>
  <div class="picker">
    <n-empty v-if="instances.length === 0" description="暂无可用的已批准任务" size="small" />
    <n-checkbox-group v-else v-model:value="selected">
      <div v-for="inst in instances" :key="inst.id" class="picker-item">
        <n-checkbox :value="inst.id">
          <div class="inst-info">
            <span class="inst-name">{{ inst.chore_name }}</span>
            <n-tag size="small" type="warning">+{{ inst.coins_reward }} 金币</n-tag>
          </div>
        </n-checkbox>
      </div>
    </n-checkbox-group>

    <div v-if="selected.length > 0" class="total-row">
      <span>已选 {{ selected.length }} 项</span>
      <span class="total-coins">共 {{ totalCoins }} 金币</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChoreInstanceForDraw } from '@/types/blindBox'

const props = defineProps<{ instances: ChoreInstanceForDraw[] }>()
const selected = ref<number[]>([])

const totalCoins = computed(() =>
  props.instances
    .filter((i) => selected.value.includes(i.id))
    .reduce((sum, i) => sum + i.coins_reward, 0)
)

defineExpose({ selected, totalCoins })
</script>

<style scoped>
.picker {
  width: 100%;
}
.picker-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.inst-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.inst-name {
  font-size: 14px;
}
.total-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0 0;
  font-size: 13px;
  color: #666;
}
.total-coins {
  font-weight: 700;
  color: #f0a020;
}
</style>
```

- [ ] **Step 4: 重写 ChildBlindBoxPage 抽奖交互**

```vue
<!-- frontend/src/pages/ChildBlindBoxPage.vue — 替换 draw-section 部分 -->
<template>
  <div class="page">
    <n-page-header title="我的盲盒" />

    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane name="draw" tab="🎁 抽奖">
        <div class="draw-section">
          <DrawAnimation ref="animRef" @draw="openDrawModal" />
        </div>
      </n-tab-pane>

      <n-tab-pane name="history" tab="📋 记录">
        <n-spin :show="store.loading">
          <DrawHistoryList :draws="store.draws" :show-fulfill="false" />
        </n-spin>
      </n-tab-pane>
    </n-tabs>

    <!-- 选择任务弹窗 -->
    <n-modal v-model:show="showModal" preset="card" title="选择要消耗的任务" style="max-width: 420px">
      <n-spin :show="loadingInstances">
        <ChoreInstancePicker ref="pickerRef" :instances="availableInstances" />
      </n-spin>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button
            type="primary"
            :disabled="!pickerRef?.selected.length"
            :loading="drawing"
            @click="handleDraw"
          >
            确认抽奖（{{ pickerRef?.totalCoins ?? 0 }} 金币）
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useBlindBoxStore } from '@/stores/blindBox'
import { getAvailableChoreInstances } from '@/api/blindBox'
import DrawAnimation from '@/components/blindBox/DrawAnimation.vue'
import DrawHistoryList from '@/components/blindBox/DrawHistoryList.vue'
import ChoreInstancePicker from '@/components/blindBox/ChoreInstancePicker.vue'
import type { ChoreInstanceForDraw } from '@/types/blindBox'

const store = useBlindBoxStore()
const animRef = ref<InstanceType<typeof DrawAnimation> | null>(null)
const pickerRef = ref<InstanceType<typeof ChoreInstancePicker> | null>(null)
const activeTab = ref('draw')
const showModal = ref(false)
const loadingInstances = ref(false)
const drawing = ref(false)
const availableInstances = ref<ChoreInstanceForDraw[]>([])

onMounted(() => store.childFetchDraws())

async function openDrawModal() {
  showModal.value = true
  loadingInstances.value = true
  try {
    availableInstances.value = await getAvailableChoreInstances()
  } finally {
    loadingInstances.value = false
  }
}

async function handleDraw() {
  const ids = pickerRef.value?.selected ?? []
  if (!ids.length) return
  drawing.value = true
  showModal.value = false
  animRef.value?.startShaking()
  try {
    const draw = await store.childDraw({ chore_instance_ids: ids })
    await new Promise((r) => setTimeout(r, 1200))
    animRef.value?.showResult(draw)
  } catch (e: unknown) {
    animRef.value?.reset()
  } finally {
    drawing.value = false
  }
}
</script>

<style scoped>
.page { padding: 16px; max-width: 500px; margin: 0 auto; }
.draw-section { display: flex; justify-content: center; padding: 24px 0; }
</style>
```

- [ ] **Step 5: 验证构建通过**

```bash
cd frontend
npm run build
```

预期：无错误

- [ ] **Step 6: 提交**

```bash
git add frontend/src/types/blindBox.ts frontend/src/api/blindBox.ts \
  frontend/src/components/blindBox/ChoreInstancePicker.vue \
  frontend/src/pages/ChildBlindBoxPage.vue
git commit -m "feat(blind-box): replace coin input with ChoreInstance picker for draw"
```

---

## Task 12: BonusDraw 横幅 + 抽奖入口

**背景：** 孩子端首页/抽奖页顶部显示"你有 N 次免费抽奖机会"横幅，点击直接使用。

**Files:**
- Create: `frontend/src/components/blindBox/BonusDrawBanner.vue`
- Modify: `frontend/src/pages/ChildBlindBoxPage.vue` (嵌入横幅)
- Modify: `frontend/src/api/blindBox.ts` (新增 bonus draw API)
- Modify: `frontend/src/stores/blindBox.ts` (新增 bonusDraws state)
- Modify: `frontend/src/types/blindBox.ts` (新增 BonusDraw 类型)

- [ ] **Step 1: 新增 BonusDraw 类型**

```typescript
// frontend/src/types/blindBox.ts (追加)
export interface BonusDraw {
  id: number
  family_id: number
  child_user_id: number
  source_wish_id: number | null
  status: 'available' | 'used' | 'expired'
  expires_at: string
  used_draw_id: number | null
  created_at: string
}
```

- [ ] **Step 2: 新增 bonus draw API 函数**

```typescript
// frontend/src/api/blindBox.ts (追加)
import type { BonusDraw } from '@/types/blindBox'

export function childGetBonusDraws() {
  return request.get<BonusDraw[]>('/child/blind-box/bonus-draws')
}

export function childUseBonusDraw(id: number) {
  return request.post<BlindBoxDraw>(`/child/blind-box/bonus-draws/${id}/use`)
}
```

- [ ] **Step 3: 在 store 中新增 bonusDraws**

```typescript
// frontend/src/stores/blindBox.ts (追加到 defineStore 内)
import type { BonusDraw } from '@/types/blindBox'
import * as blindBoxApi from '@/api/blindBox'

const bonusDraws = ref<BonusDraw[]>([])

async function childFetchBonusDraws() {
  const data = await blindBoxApi.childGetBonusDraws()
  bonusDraws.value = data
}

async function childUseBonusDraw(id: number) {
  const draw = await blindBoxApi.childUseBonusDraw(id)
  bonusDraws.value = bonusDraws.value.filter((b) => b.id !== id)
  draws.value.unshift(draw)
  return draw
}

// 在 return 中暴露
// bonusDraws, childFetchBonusDraws, childUseBonusDraw
```

- [ ] **Step 4: 实现 BonusDrawBanner 组件**

```vue
<!-- frontend/src/components/blindBox/BonusDrawBanner.vue -->
<template>
  <n-alert
    v-if="availableCount > 0"
    type="warning"
    :show-icon="true"
    style="margin-bottom: 12px; cursor: pointer"
    @click="$emit('use', firstAvailableId!)"
  >
    <template #icon>🎉</template>
    你有 <strong>{{ availableCount }}</strong> 次免费抽奖机会！点击立即使用
    <span class="expire-hint">（{{ expiresInDays }} 天后过期）</span>
  </n-alert>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BonusDraw } from '@/types/blindBox'

const props = defineProps<{ bonusDraws: BonusDraw[] }>()
defineEmits<{ use: [id: number] }>()

const available = computed(() =>
  props.bonusDraws.filter((b) => b.status === 'available')
)
const availableCount = computed(() => available.value.length)
const firstAvailableId = computed(() => available.value[0]?.id ?? null)
const expiresInDays = computed(() => {
  if (!available.value[0]) return 0
  const diff = new Date(available.value[0].expires_at).getTime() - Date.now()
  return Math.max(0, Math.ceil(diff / 86400000))
})
</script>

<style scoped>
.expire-hint {
  font-size: 12px;
  color: #aaa;
  margin-left: 4px;
}
</style>
```

- [ ] **Step 5: 在 ChildBlindBoxPage 中嵌入横幅**

```vue
<!-- ChildBlindBoxPage.vue — 在 <n-page-header> 后、<n-tabs> 前插入 -->
<BonusDrawBanner
  :bonus-draws="store.bonusDraws"
  @use="handleUseBonusDraw"
/>
```

```typescript
// script setup 中追加
import BonusDrawBanner from '@/components/blindBox/BonusDrawBanner.vue'

onMounted(() => {
  store.childFetchDraws()
  store.childFetchBonusDraws()
})

async function handleUseBonusDraw(id: number) {
  animRef.value?.startShaking()
  try {
    const draw = await store.childUseBonusDraw(id)
    await new Promise((r) => setTimeout(r, 1200))
    animRef.value?.showResult(draw)
  } catch {
    animRef.value?.reset()
  }
}
```

- [ ] **Step 6: 验证构建通过**

```bash
cd frontend
npm run build
```

预期：无错误

- [ ] **Step 7: 提交**

```bash
git add frontend/src/types/blindBox.ts frontend/src/api/blindBox.ts \
  frontend/src/stores/blindBox.ts \
  frontend/src/components/blindBox/BonusDrawBanner.vue \
  frontend/src/pages/ChildBlindBoxPage.vue
git commit -m "feat(blind-box): add bonus draw banner and one-click use flow"
```

---

## Task 13: 父母端心愿列表 — 转为盲盒礼物按钮

**Files:**
- Modify: `frontend/src/pages/WishListPage.vue` (或心愿相关页面，新增转入按钮)
- Modify: `frontend/src/api/blindBox.ts` (新增 createGiftFromWish)

- [ ] **Step 1: 新增 API 函数**

```typescript
// frontend/src/api/blindBox.ts (追加)
export function createGiftFromWish(wishId: number) {
  return request.post<BlindBoxGift>(`/blind-box/gifts/from-wish/${wishId}`)
}
```

- [ ] **Step 2: 在心愿卡片/列表中新增按钮**

在父母端心愿列表页（`WishListPage.vue` 或 `WishCard` 组件）的每个心愿操作区追加：

```vue
<!-- 在心愿操作按钮区追加（仅父母角色可见） -->
<n-button
  v-if="isParent && !wish.converted_to_gift"
  size="small"
  type="info"
  :loading="converting === wish.id"
  @click="handleConvertToGift(wish.id)"
>
  🎁 转为盲盒礼物
</n-button>
```

```typescript
// script setup 追加
import { createGiftFromWish } from '@/api/blindBox'
import { useMessage } from 'naive-ui'

const message = useMessage()
const converting = ref<number | null>(null)

async function handleConvertToGift(wishId: number) {
  converting.value = wishId
  try {
    const gift = await createGiftFromWish(wishId)
    const warning = (gift as BlindBoxGift & { warning?: string }).warning
    if (warning) {
      message.warning(warning)
    } else {
      message.success(`「${gift.name}」已加入礼物池`)
    }
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })
      ?.response?.data?.detail
    if (detail?.includes('已转入')) {
      message.warning(detail)
    } else {
      message.error('转入失败，请重试')
    }
  } finally {
    converting.value = null
  }
}
```

- [ ] **Step 3: 验证构建通过**

```bash
cd frontend
npm run build
```

预期：无错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/blindBox.ts frontend/src/pages/WishListPage.vue
git commit -m "feat(blind-box): add convert-wish-to-gift button on wish list"
```

---

## Task 14: 全量验证 + 手动验收路径更新

- [ ] **Step 1: 全量类型检查**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无错误

- [ ] **Step 2: 全量构建**

```bash
npm run build
```

预期：构建成功

- [ ] **Step 3: Lint**

```bash
npm run lint
```

预期：无错误

**更新后手动验收路径：**

| 角色 | 路径 | 验收点 |
|------|------|--------|
| 孩子 | `/child/blind-box` | 顶部显示免费抽奖横幅（有 bonus draw 时） |
| 孩子 | `/child/blind-box` → 点击抽奖 | 弹出 ChoreInstance 选择器，勾选后显示金币总额 |
| 孩子 | `/child/blind-box` → 确认抽奖 | 摇晃动画 → 礼物展示，惊喜标识正确 |
| 孩子 | `/child/blind-box` → 点击横幅 | 直接触发免费抽奖动画，is_bonus=true |
| 父母 | 心愿列表页 | 每个心愿有「转为盲盒礼物」按钮 |
| 父母 | 心愿列表 → 转入 | 成功提示，重复转入显示警告 |
| 父母 | `/blind-box/gifts` | 礼物池含从心愿转入的礼物，source_wish_id 非空 |

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(blind-box): full frontend supplement — bonus draw, chore picker, wish convert"
```

---

## 补充实现顺序

| Task | 内容 | 依赖 |
|------|------|------|
| 11 | ChoreInstance 选择器 + 修正抽奖交互 | Task 3, 4, 9 |
| 12 | BonusDraw 横幅 + 一键使用 | Task 3, 9, 11 |
| 13 | 心愿转入礼物池按钮 | Task 2 |
| 14 | 全量验证 + 验收路径更新 | Task 11-13 |
