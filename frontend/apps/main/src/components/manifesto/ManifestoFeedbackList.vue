<template>
  <van-popup
    :show="visible"
    position="bottom"
    round
    :style="{ maxHeight: '70vh' }"
    @update:show="(val: boolean) => emit('update:visible', val)"
  >
    <div class="feedback-list">
      <div class="feedback-list__header">
        <h3 class="feedback-list__title">{{ t('manifesto.feedbackList') }}</h3>
        <button class="feedback-list__close" :aria-label="t('common.close')" @click="close">
          <van-icon name="cross" />
        </button>
      </div>

      <van-loading v-if="loading" size="24px" class="feedback-list__loading" />
      <van-empty v-else-if="items.length === 0" :description="t('manifesto.noFeedback')" image-size="60" />
      <van-list v-else>
        <div
          v-for="item in items"
          :key="item.id"
          class="feedback-item"
          :class="{ 'feedback-item--unread': !item.is_read }"
          @click="onTap(item)"
        >
          <div class="feedback-item__main">
            <div class="feedback-item__head">
              <span class="feedback-item__author">{{ resolveName(item.user_id) }}</span>
              <span v-if="!item.is_read" class="feedback-item__dot" />
              <span class="feedback-item__time">{{ formatDateTime(item.created_at) }}</span>
            </div>
            <div class="feedback-item__content">{{ item.content }}</div>
          </div>
        </div>
      </van-list>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import * as manifestoApi from '@/api/manifesto'
import { parseApiDate } from '@/utils/format'
import { useFamilyStore } from '@/stores/family'
import type { ManifestoFeedback } from '@/types/manifesto'

const { t, locale } = useI18n()
const familyStore = useFamilyStore()

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const loading = ref(false)
const items = ref<ManifestoFeedback[]>([])

const memberMap = computed(() => new Map(familyStore.members.map(m => [m.id, m.display_name])))

function resolveName(userId: string): string {
  return memberMap.value.get(userId) ?? userId
}

function close() {
  emit('update:visible', false)
}

function onTap(item: ManifestoFeedback) {
  // V1: mark as read locally
  item.is_read = true
}

function formatDateTime(iso: string): string {
  const d = parseApiDate(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString(locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

watch(() => props.visible, async (val) => {
  if (!val) return
  loading.value = true
  if (familyStore.members.length === 0) {
    await familyStore.fetchFamily().catch(() => { /* non-critical */ })
  }
  try {
    const res = await manifestoApi.getFeedbackList()
    items.value = res.data ?? []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
})

defineExpose({
  unreadCount: () => items.value.filter(i => !i.is_read).length,
})
</script>

<style scoped>
.feedback-list {
  padding: 0 0 16px;
}
.feedback-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 8px;
  position: sticky;
  top: 0;
  background: var(--van-popup-background, #fff);
  z-index: 1;
}
.feedback-list__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--van-text-color);
}
.feedback-list__close {
  background: none;
  border: none;
  padding: 4px 8px;
  font-size: 18px;
  color: var(--van-text-color-2);
  cursor: pointer;
}
.feedback-list__loading {
  display: flex;
  justify-content: center;
  padding: 32px;
}
.feedback-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--van-border-color);
}
.feedback-item:last-of-type {
  border-bottom: none;
}
.feedback-item--unread {
  background: rgba(25, 137, 250, 0.04);
}
[data-theme='dark'] .feedback-item--unread {
  background: rgba(25, 137, 250, 0.08);
}
.feedback-item__main {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.feedback-item__head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--van-text-color-3);
}
.feedback-item__author {
  font-weight: 500;
  color: var(--van-text-color-2);
}
.feedback-item__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--van-danger-color, #ee0a24);
  flex-shrink: 0;
}
.feedback-item__time {
  margin-left: auto;
}
.feedback-item__content {
  font-size: 14px;
  color: var(--van-text-color);
  line-height: 1.5;
  word-break: break-word;
}
</style>
