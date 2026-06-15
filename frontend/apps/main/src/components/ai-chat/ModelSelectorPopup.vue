<script setup lang="ts">
/**
 * DeerFlow 模型选择弹出层
 *
 * 参考: frontend/src/components/ai-elements/model-selector.tsx
 *
 * 功能:
 * - 显示租户过滤后的模型列表
 * - 支持搜索过滤
 * - 显示模型能力标签
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Popup, Search, Cell, CellGroup, Tag } from 'vant'
import IIcon from '@/components/IIcon.vue'
import type { ModelInfo } from '@/composables/ai-chat/useTenantAiResources'

const { t } = useI18n()

const props = defineProps<{
  show: boolean
  models: ModelInfo[]
  currentModel: string
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  select: [modelName: string]
}>()

const searchQuery = ref('')

// 搜索过滤
const filteredModels = computed(() =>
  props.models.filter(
    (m) =>
      m.display_name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      m.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
  ),
)

function onSelect(modelName: string) {
  emit('select', modelName)
}

function getCapabilityTags(model: ModelInfo): string[] {
  const tags: string[] = []
  if (model.supports_thinking) tags.push(t('model.capabilityThinking'))
  if (model.supports_vision) tags.push(t('model.capabilityVision'))
  if (model.supports_tool_calling) tags.push(t('model.capabilityToolCalling'))
  return tags
}
</script>

<template>
  <Popup
    :show="show"
    position="bottom"
    round
    :style="{ maxHeight: '60vh' }"
    teleport="body"
    @update:show="emit('update:show', $event)"
  >
    <div class="model-selector-popup">
      <div class="popup-header">
        <span class="popup-title">{{ t('model.selectTitle') }}</span>
        <button class="close-btn" @click="emit('update:show', false)">
          <IIcon icon="x" />
        </button>
      </div>

      <!-- 搜索框 -->
      <Search
        v-model="searchQuery"
        shape="round"
        :placeholder="t('model.searchPlaceholder')"
      />

      <!-- 模型列表 -->
      <CellGroup inset>
        <Cell
          v-for="model in filteredModels"
          :key="model.name"
          :title="model.display_name"
          :label="model.provider_name"
          clickable
          :class="{ active: currentModel === model.name }"
          @click="onSelect(model.name)"
        >
          <template #right-icon>
            <div class="model-tags">
              <Tag
                v-for="tag in getCapabilityTags(model)"
                :key="tag"
                type="primary"
                size="small"
                plain
              >
                {{ tag }}
              </Tag>
            </div>
            <IIcon
              v-if="currentModel === model.name"
              icon="check"
              class="check-icon"
            />
          </template>
        </Cell>
      </CellGroup>

      <!-- 空状态 -->
      <div v-if="filteredModels.length === 0" class="empty-state">
        <IIcon icon="search-x" class="empty-icon" />
        <span class="empty-text">{{ t('model.notFound') }}</span>
      </div>
    </div>
  </Popup>
</template>

<style scoped>
.model-selector-popup {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.popup-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
}

.model-tags {
  display: flex;
  gap: 4px;
  margin-right: 8px;
}

.check-icon {
  width: 16px;
  height: 16px;
  color: var(--van-primary-color);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: var(--text-secondary);
}

.empty-icon {
  width: 32px;
  height: 32px;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 14px;
}

/* 375px */
@media (max-width: 375px) {
  .model-selector-popup {
    padding: 12px;
  }

  .popup-title {
    font-size: 14px;
  }
}
</style>