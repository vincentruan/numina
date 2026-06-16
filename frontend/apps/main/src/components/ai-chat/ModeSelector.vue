<script setup lang="ts">
/**
 * DeerFlow 执行模式选择器
 *
 * 参考: frontend/src/components/workspace/input-box.tsx PromptInputActionMenu (第523-693行)
 *
 * 四种模式:
 * - Flash: minimal, 快速响应
 * - Thinking: low, 启用思考链
 * - Pro: medium, 计划模式
 * - Ultra: high, 子代理协作
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Popup, CellGroup, Cell } from 'vant'
import IIcon from '@/components/IIcon.vue'
import type { InputMode } from '@/types/ai-chat/input-mode'
import { INPUT_MODE_CONFIGS } from '@/composables/ai-chat/useTenantAiResources'

const { t } = useI18n()

const props = defineProps<{
  currentMode: InputMode
  supportsThinking: boolean
  ultraDisabled?: boolean
}>()

const emit = defineEmits<{
  select: [mode: InputMode]
}>()

const popupOpen = ref(false)

// 可用模式列表
const availableModes = computed(() =>
  Object.values(INPUT_MODE_CONFIGS).filter((config) => {
    // Flash 模式始终可用
    if (config.mode === 'flash') return true
    // 其他模式需要模型支持 thinking
    if (!props.supportsThinking) return false
    // Ultra 模式还需要租户支持 subagent
    if (config.mode === 'ultra' && props.ultraDisabled) return false
    return true
  }),
)

function onSelect(mode: InputMode) {
  emit('select', mode)
  popupOpen.value = false
}

function getModeIcon(mode: InputMode): string {
  return INPUT_MODE_CONFIGS[mode].icon
}

function getModeLabel(mode: InputMode): string {
  return t(`mode.${mode}.label`)
}

function getModeDescription(mode: InputMode): string {
  return t(`mode.${mode}.description`)
}
</script>

<template>
  <!-- 模式按钮 -->
  <button
    class="mode-btn"
    :class="currentMode"
    @click="popupOpen = true"
  >
    <IIcon :icon="getModeIcon(currentMode)" class="mode-icon" />
    <span class="mode-label">{{ getModeLabel(currentMode) }}</span>
  </button>

  <!-- 模式选择弹出层 -->
  <Popup
    v-model:show="popupOpen"
    position="bottom"
    round
    :style="{ maxHeight: '50vh' }"
  >
    <div class="mode-selector-popup">
      <div class="popup-header">
        <span class="popup-title">{{ t('aiChat.modeSelectorTitle') }}</span>
      </div>

      <CellGroup inset>
        <Cell
          v-for="config in availableModes"
          :key="config.mode"
          :title="getModeLabel(config.mode)"
          :label="getModeDescription(config.mode)"
          clickable
          :class="{ active: currentMode === config.mode }"
          @click="onSelect(config.mode)"
        >
          <template #icon>
            <IIcon :icon="config.icon" class="cell-icon" />
          </template>
          <template #right-icon>
            <IIcon
              v-if="currentMode === config.mode"
              icon="check"
              class="check-icon"
            />
          </template>
        </Cell>
      </CellGroup>

      <!-- 不可用模式提示 -->
      <div v-if="!supportsThinking" class="disabled-hint">
        {{ t('aiChat.tenantModelFallback') }}
      </div>
      <div v-if="ultraDisabled" class="disabled-hint">
        {{ t('aiChat.tenantUltraDisabled') }}
      </div>
    </div>
  </Popup>
</template>

<style scoped>
.mode-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn.flash {
  border-color: #f59e0b;
  color: #f59e0b;
}
.mode-btn.thinking {
  border-color: #3b82f6;
  color: #3b82f6;
}
.mode-btn.pro {
  border-color: #8b5cf6;
  color: #8b5cf6;
}
.mode-btn.ultra {
  border-color: #ef4444;
  color: #ef4444;
}

.mode-icon {
  width: 14px;
  height: 14px;
}

.mode-label {
  font-weight: 500;
}

.mode-selector-popup {
  padding: 16px;
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

.cell-icon {
  width: 20px;
  height: 20px;
  margin-right: 8px;
}

.check-icon {
  width: 16px;
  height: 16px;
  color: var(--van-primary-color);
}

.disabled-hint {
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

/* 375px */
@media (max-width: 375px) {
  .mode-btn {
    padding: 4px 8px;
    font-size: 11px;
  }

  .mode-icon {
    width: 12px;
    height: 12px;
  }

  .popup-title {
    font-size: 14px;
  }
}
</style>