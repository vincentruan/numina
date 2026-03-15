<template>
  <div class="wish-list-page">
    <van-nav-bar title="心愿单" left-arrow @click-left="$router.back()" />

    <van-tabs v-model:active="activeTab" sticky>
      <van-tab title="未实现" name="pending" />
      <van-tab title="已实现" name="fulfilled" />
    </van-tabs>

    <div class="list-content">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <template v-if="filteredWishes.length">
          <div
            v-for="wish in filteredWishes"
            :key="wish.id"
            class="wish-card"
            @click="$router.push(`/wishes/${wish.id}/edit`)"
          >
            <div class="wish-header">
              <span class="wish-name">{{ wish.name }}</span>
              <van-icon v-if="wish.is_fulfilled" name="success" color="#07c160" size="18" />
            </div>
            <div class="wish-meta">
              <van-rate
                v-model="wish.priority"
                :count="5"
                size="14"
                color="#ffd21e"
                void-icon="star"
                void-color="#eee"
                readonly
              />
              <span v-if="wish.expected_price" class="wish-price">
                ¥{{ wish.expected_price.toLocaleString() }}
              </span>
            </div>
            <div v-if="wish.target_date" class="wish-date">
              目标日期：{{ wish.target_date }}
            </div>
            <div v-if="wish.notes" class="wish-notes">{{ wish.notes }}</div>
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
const activeTab = ref<'pending' | 'fulfilled'>('pending')
const refreshing = ref(false)

const filteredWishes = computed(() =>
  wishes.value.filter(w =>
    activeTab.value === 'fulfilled' ? w.is_fulfilled : !w.is_fulfilled
  )
)

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
.wish-price {
  font-size: 13px;
  color: #ee0a24;
}
.wish-date,
.wish-notes {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
</style>
