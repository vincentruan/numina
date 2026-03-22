<template>
  <div class="wish-list-page">
    <van-nav-bar title="心愿单" />

    <van-tabs v-model:active="activeTab" sticky>
      <van-tab title="待实现" name="pending" />
      <van-tab title="已实现" name="realized" />
      <van-tab title="已取消" name="cancelled" />
    </van-tabs>

    <div class="list-content">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <template v-if="filteredWishes.length">
          <div
            v-for="wish in filteredWishes"
            :key="wish.id"
            class="wish-card"
            @click="$router.push(`/wishes/${wish.id}`)"
          >
            <div class="wish-header">
              <span class="wish-name">{{ wish.name }}</span>
              <van-icon v-if="wish.status === 'realized'" name="success" color="#07c160" size="18" />
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
              {{ wish.category.icon }} {{ wish.category.name }}
            </div>
            <div v-if="wish.description" class="wish-notes">{{ wish.description }}</div>
          </div>
        </template>
        <van-empty v-else description="暂无心愿" />
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

const wishes = ref<Wish[]>([])
const activeTab = ref<'pending' | 'realized' | 'cancelled'>('pending')
const refreshing = ref(false)

const filteredWishes = computed(() =>
  wishes.value.filter(w => w.status === activeTab.value)
)

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
.list-content {
  padding: 12px;
}
.wish-card {
  background: #fff;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.wish-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.wish-name {
  font-size: 15px;
  font-weight: 600;
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
  background: #e8f5e9;
  color: #4caf50;
}
.priority-badge.medium {
  background: #fff3e0;
  color: #ff9800;
}
.priority-badge.high {
  background: #ffebee;
  color: #f44336;
}
.wish-price {
  font-size: 13px;
  color: #ee0a24;
}
.wish-category,
.wish-notes {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
</style>