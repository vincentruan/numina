<template>
  <div class="wish-list-page">
    <van-nav-bar title="心愿单" />

    <van-tabs v-model:active="activeTab" sticky>
      <van-tab title="待实现" name="pending" />
      <van-tab title="已实现" name="realized" />
      <van-tab title="已取消" name="cancelled" />
    </van-tabs>

    <!-- Sort bar -->
    <div class="sort-bar">
      <button
        v-for="opt in sortOptions"
        :key="opt.value"
        class="sort-btn"
        :class="{ active: sortBy === opt.value }"
        @click="toggleSort(opt.value)"
        :aria-label="`按${opt.label}排序`"
      >
        {{ opt.label }}
        <span v-if="sortBy === opt.value" class="sort-dir" aria-hidden="true">
          {{ sortDir === 'asc' ? '↑' : '↓' }}
        </span>
      </button>
    </div>

    <div class="list-content">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <template v-if="sortedWishes.length">
          <div role="list" aria-label="心愿清单">
            <div
              v-for="wish in sortedWishes"
              :key="wish.id"
              class="wish-card"
              role="listitem"
              tabindex="0"
              @click="$router.push(`/wishes/${wish.id}`)"
              @keydown.enter="$router.push(`/wishes/${wish.id}`)"
              :aria-label="`${wish.name}，${priorityText(wish.priority)}优先级`"
            >
              <div class="wish-header">
                <span class="wish-name">{{ wish.name }}</span>
                <div class="wish-header-right">
                  <van-icon v-if="wish.status === 'realized'" name="success" color="#07c160" size="18" />
                  <van-icon name="arrow" size="14" class="card-arrow" />
                </div>
              </div>
              <div class="wish-meta">
                <span class="priority-badge" :class="wish.priority">
                  {{ priorityText(wish.priority) }}
                </span>
                <span v-if="wish.expected_price" class="wish-price">
                  ¥{{ wish.expected_price.toLocaleString() }}
                </span>
              </div>
              <div v-if="wish.category" class="wish-category">
                <div class="wish-category-icon">
                  <svg class="icon-svg" aria-hidden="true">
                    <use :href="`#${getIconId(wish.category.icon)}`" />
                  </svg>
                </div>
                <span>{{ wish.category.name }}</span>
              </div>
              <div v-if="wish.description" class="wish-notes">{{ wish.description }}</div>
            </div>
          </div>
        </template>
        <van-empty v-else :description="emptyDescription" />
      </van-pull-refresh>
    </div>

    <van-floating-bubble
      icon="plus"
      @click="$router.push('/wishes/new')"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getWishes } from '@/api/wishes'
import type { Wish } from '@/types'
import { getIconId } from '@/utils/icon'

const wishes = ref<Wish[]>([])
const activeTab = ref<'pending' | 'realized' | 'cancelled'>('pending')
const refreshing = ref(false)
const sortBy = ref<'priority' | 'price' | 'name'>('priority')
const sortDir = ref<'asc' | 'desc'>('desc')

const sortOptions = [
  { value: 'priority' as const, label: '优先级' },
  { value: 'price' as const, label: '价格' },
  { value: 'name' as const, label: '名称' },
]

const priorityOrder: Record<string, number> = { high: 3, medium: 2, low: 1 }

const filteredWishes = computed(() =>
  wishes.value.filter(w => w.status === activeTab.value)
)

const sortedWishes = computed(() => {
  const list = [...filteredWishes.value]
  const dir = sortDir.value === 'asc' ? 1 : -1
  return list.sort((a, b) => {
    if (sortBy.value === 'priority') {
      return dir * ((priorityOrder[a.priority] ?? 2) - (priorityOrder[b.priority] ?? 2))
    }
    if (sortBy.value === 'price') {
      return dir * ((a.expected_price ?? 0) - (b.expected_price ?? 0))
    }
    return dir * a.name.localeCompare(b.name)
  })
})

const emptyDescription = computed(() => {
  if (activeTab.value === 'realized') return '还没有实现的心愿'
  if (activeTab.value === 'cancelled') return '没有已取消的心愿'
  return '添加你的第一个心愿吧'
})

function toggleSort(value: typeof sortBy.value) {
  if (sortBy.value === value) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = value
    sortDir.value = 'desc'
  }
}

function priorityText(priority: string): string {
  const map: Record<string, string> = { low: '低', medium: '中', high: '高' }
  return map[priority] || '中'
}

async function loadWishes() {
  const res = await getWishes()
  wishes.value = res.data
}

async function onRefresh() {
  await loadWishes()
  refreshing.value = false
}

onMounted(loadWishes)
</script>

<style scoped>
.sort-bar {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--separator);
}
.sort-btn {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 12px;
  border: 1px solid var(--separator);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 3px;
  transition: background 0.15s, color 0.15s;
}
.sort-btn.active {
  background: var(--van-primary-color);
  color: #fff;
  border-color: var(--van-primary-color);
}
.sort-dir {
  font-size: 11px;
}
.list-content {
  padding: 12px;
}
.wish-card {
  background: var(--card-bg);
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  cursor: pointer;
}

[data-theme='dark'] .wish-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.wish-card:active {
  transform: scale(0.98);
}
.wish-card:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
}
.wish-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.wish-header-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.card-arrow {
  color: var(--text-tertiary);
}
.wish-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  margin-right: 8px;
}
.wish-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}
.priority-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}
.priority-badge.low {
  background: rgba(76, 175, 80, 0.15);
  color: #4caf50;
}

[data-theme='dark'] .priority-badge.low {
  background: rgba(76, 175, 80, 0.2);
  color: #81c784;
}

.priority-badge.medium {
  background: rgba(255, 152, 0, 0.15);
  color: #ff9800;
}

[data-theme='dark'] .priority-badge.medium {
  background: rgba(255, 152, 0, 0.2);
  color: #ffb74d;
}

.priority-badge.high {
  background: rgba(244, 67, 54, 0.15);
  color: #f44336;
}

[data-theme='dark'] .priority-badge.high {
  background: rgba(244, 67, 54, 0.2);
  color: #e57373;
}

.wish-price {
  font-size: 13px;
  color: #ee0a24;
}
.wish-category,
.wish-notes {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
}
.wish-category {
  display: flex;
  align-items: center;
  gap: 6px;
}
.wish-category-icon {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: var(--color-action-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.icon-svg {
  width: 12px;
  height: 12px;
  color: #fff;
}
</style>