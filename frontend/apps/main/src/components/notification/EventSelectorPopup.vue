<template>
  <van-popup
    :show="modelValue"
    position="bottom"
    round
    teleport="body"
    :style="{ height: '60%' }"
    @update:show="(val: boolean) => emit('update:modelValue', val)"
  >
    <div class="event-selector">
      <van-nav-bar :title="t('reminders.eventSelectorTitle')">
        <template #right>
          <van-icon name="cross" @click="close" />
        </template>
      </van-nav-bar>

      <div class="event-selector__body">
        <van-loading v-if="loading" class="event-selector__loading" />
        <van-empty v-else-if="!categories.length" :description="t('reminders.noEvents')" />
        <template v-else>
          <div v-for="cat in categories" :key="cat.category" class="event-category">
            <div class="event-category__header">
              <van-icon :name="cat.icon" class="event-category__icon" />
              <span class="event-category__label">{{ t(cat.labelKey) }}</span>
              <div class="event-category__actions">
                <van-button
                  size="mini"
                  plain
                  type="primary"
                  @click="selectAllInCategory(cat)"
                >
                  {{ t('reminders.selectAllInCategory') }}
                </van-button>
                <van-button
                  size="mini"
                  plain
                  type="default"
                  @click="deselectAllInCategory(cat)"
                >
                  {{ t('reminders.deselectAllInCategory') }}
                </van-button>
              </div>
            </div>
            <van-checkbox-group v-model="selectedTypes" class="event-category__list">
              <van-cell
                v-for="event in cat.events"
                :key="event.type"
                clickable
                @click="toggleEvent(event.type)"
              >
                <template #title>
                  <span class="event-label">{{ t(event.labelKey) }}</span>
                </template>
                <template #right-icon>
                  <van-checkbox :name="event.type" shape="square" />
                </template>
              </van-cell>
            </van-checkbox-group>
          </div>
        </template>
      </div>

      <div v-if="categories.length" class="event-selector__footer">
        <van-button type="primary" block round @click="save">
          {{ t('reminders.saveSelection') }}
        </van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  notificationChannelsApi,
  type NotificationEvent,
  type NotificationEventCategory,
} from '@/api/notificationChannels'

interface MappedEvent {
  type: string
  labelKey: string
}

interface CategoryWithEvents {
  category: string
  labelKey: string
  icon: string
  events: MappedEvent[]
}

const props = defineProps<{
  modelValue: boolean
  initialTypes?: string[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'save', types: string[]): void
}>()

const { t } = useI18n()

const loading = ref(false)
const categories = ref<CategoryWithEvents[]>([])
const selectedTypes = ref<string[]>([])

async function fetchEvents() {
  loading.value = true
  try {
    const data = await notificationChannelsApi.getEvents()
    categories.value = data.map((cat: NotificationEventCategory) => ({
      category: cat.category,
      labelKey: cat.label_key,
      icon: cat.icon,
      events: cat.events.map((e: NotificationEvent) => ({
        type: e.type,
        labelKey: e.label_key,
      })),
    }))
  } finally {
    loading.value = false
  }
}

function toggleEvent(type: string) {
  const idx = selectedTypes.value.indexOf(type)
  if (idx >= 0) {
    selectedTypes.value.splice(idx, 1)
  } else {
    selectedTypes.value.push(type)
  }
}

function selectAllInCategory(cat: CategoryWithEvents) {
  for (const event of cat.events) {
    if (!selectedTypes.value.includes(event.type)) {
      selectedTypes.value.push(event.type)
    }
  }
}

function deselectAllInCategory(cat: CategoryWithEvents) {
  const typesToRemove = new Set(cat.events.map((e) => e.type))
  selectedTypes.value = selectedTypes.value.filter((t) => !typesToRemove.has(t))
}

function save() {
  emit('save', [...selectedTypes.value])
  close()
}

function close() {
  emit('update:modelValue', false)
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      selectedTypes.value = props.initialTypes ? [...props.initialTypes] : []
      if (!categories.value.length) {
        void fetchEvents()
      }
    }
  },
)
</script>

<style scoped>
.event-selector {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.event-selector__body {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;
}

.event-selector__loading {
  display: flex;
  justify-content: center;
  padding: 48px 0;
}

.event-selector__footer {
  padding: 12px 16px;
  border-top: 1px solid var(--van-border-color);
}

.event-category {
  margin-bottom: 16px;
}

.event-category__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-weight: 600;
  font-size: 15px;
  color: var(--van-text-color);
}

.event-category__icon {
  font-size: 18px;
  color: var(--van-primary-color);
}

.event-category__label {
  flex: 1;
}

.event-category__actions {
  display: flex;
  gap: 4px;
}

.event-category__list {
  background: var(--van-background-2);
  border-radius: 8px;
  overflow: hidden;
}

.event-category__list .van-cell {
  padding: 10px 12px;
}

.event-label {
  font-size: 14px;
}
</style>
