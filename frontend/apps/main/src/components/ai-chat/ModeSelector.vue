<script setup lang="ts">
/**
 * DeerFlow 执行模式选择器
 *
 * 参考: deer-flow-reference/frontend/src/components/workspace/input-box.tsx PromptInputActionMenu (第709-878行)
 *
 * 四种模式:
 * - flash: 快速且高效的完成任务，但可能不够精准
 * - thinking: 思考后再行动，在时间与准确性之间取得平衡
 * - pro: 思考、计划再执行，获得更精准的结果，可能需要更多时间
 * - ultra: 继承自 Pro 模式，可调用子代理分工协作，适合复杂多步骤任务，能力最强
 */
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
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
const triggerRef = ref<HTMLElement | null>(null)

// 可用模式列表（不过滤，全部展示，用 dimmed 表示不可用）
const allModes = computed(() =>
  Object.values(INPUT_MODE_CONFIGS).map((config) => {
    let available = true
    if (config.mode === 'ultra' && props.ultraDisabled) available = false
    if (config.mode !== 'flash' && !props.supportsThinking) available = false
    return {
      mode: config.mode,
      available,
      icon: config.icon,
      label: t(`mode.${config.mode}.label`),
      description: t(`mode.${config.mode}.description`),
    }
  }),
)

function isModeActive(mode: InputMode): boolean {
  return mode === props.currentMode
}

function isModeDimmed(mode: InputMode): boolean {
  return !allModes.value.find(m => m.mode === mode)?.available
}

function onSelect(mode: InputMode) {
  const item = allModes.value.find(m => m.mode === mode)
  if (!item?.available) return
  emit('select', mode)
  popupOpen.value = false
}

// 弹出层位置：左对齐 trigger 按钮，显示在按钮上方
// Uses ref updated on open + scroll/resize for reactive positioning
const popupPosition = ref<Record<string, string>>({})

function updatePopupPosition() {
  if (!triggerRef.value || !popupOpen.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  let bottom = window.innerHeight - rect.top + 8
  // Clamp: ensure panel doesn't go above viewport
  const minBottom = 300 // approximate dropdown card height + padding
  if (bottom < minBottom) bottom = minBottom
  popupPosition.value = {
    position: 'fixed' as const,
    bottom: `${bottom}px`,
    left: `${rect.left}px`,
    maxWidth: `calc(100vw - 32px)`,
  }
}

function onPopupOpen() {
  popupOpen.value = true
  nextTick(() => updatePopupPosition())
}

// Scroll/resize listener for reactive popup positioning
function onScrollOrResize() {
  updatePopupPosition()
}

function getModeIcon(mode: InputMode): string {
  return INPUT_MODE_CONFIGS[mode]?.icon || ''
}

function _getModeLabel(mode: InputMode): string {
  return t(`mode.${mode}.label`)
}

// 点击页面其他位置关闭弹出层
function onOutsideClick(e: MouseEvent) {
  if (!popupOpen.value) return
  const target = e.target as HTMLElement
  if (triggerRef.value?.contains(target)) return
  popupOpen.value = false
}

// Handle Escape key to close popup
function onEscapeKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && popupOpen.value) {
    popupOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('keydown', onEscapeKey)
  // 使用 capture 阶段拦截，确保先于其他组件的点击事件触发
  document.addEventListener('click', onOutsideClick, true)
  window.addEventListener('scroll', onScrollOrResize, true)
  window.addEventListener('resize', onScrollOrResize)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onEscapeKey)
  document.removeEventListener('click', onOutsideClick, true)
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
})
</script>

<template>
  <!-- 模式触发按钮 -->
  <button
    ref="triggerRef"
    class="mode-trigger control-btn"
    :class="{ 'mode-trigger--ultra': currentMode === 'ultra' }"
    @click="onPopupOpen"
  >
    <IIcon :icon="getModeIcon(currentMode)" class="mode-trigger-icon" />
  </button>

  <!-- 模式选择弹出层 -->
  <Teleport to="body">
    <Transition name="mode-dropdown">
      <div v-if="popupOpen" class="mode-dropdown" :style="popupPosition" @click.self="popupOpen = false">
        <div class="mode-dropdown-card">
          <!-- 模式列表 -->
          <div
            v-for="item in allModes"
            :key="item.mode"
            class="mode-item"
            :class="{
              'mode-item--active': isModeActive(item.mode),
              'mode-item--dimmed': isModeDimmed(item.mode),
              'mode-item--ultra': item.mode === 'ultra',
            }"
            @click="onSelect(item.mode)"
          >
            <div class="mode-item-header">
              <IIcon :icon="item.icon" class="mode-item-icon" />
              <span class="mode-item-label">{{ item.label }}</span>
              <IIcon v-if="isModeActive(item.mode)" icon="lucide:check" class="mode-item-check" />
              <div v-else class="mode-item-spacer" />
            </div>
            <div class="mode-item-desc">{{ item.description }}</div>
          </div>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ── Trigger Button — circular, matches control-btn style ── */
.mode-trigger {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--border-color, rgba(0, 0, 0, 0.12));
  background: rgba(99, 102, 241, 0.08);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.15s, box-shadow 0.2s;
  min-width: 44px;
  min-height: 44px;
  padding: 0;
}

.mode-trigger:hover {
  background: rgba(99, 102, 241, 0.15);
  color: var(--text-primary);
}

.mode-trigger:active {
  transform: scale(0.92);
}

.mode-trigger--ultra {
  background: rgba(218, 187, 94, 0.12);
  border-color: rgba(218, 187, 94, 0.3);
  color: #dabb5e;
}

.mode-trigger--ultra:hover {
  background: rgba(218, 187, 94, 0.2);
}

.mode-trigger-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

/* ── Dropdown ── */
.mode-dropdown {
  z-index: 999;
}

.mode-dropdown-card {
  width: 300px;
  max-width: calc(100vw - 32px);
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 8px;
  overflow: hidden;
}

/* ── Mode Item ── */
.mode-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.mode-item:hover:not(.mode-item--dimmed) {
  background: var(--bg-primary);
}

.mode-item--active {
  color: var(--text-primary);
}

.mode-item--dimmed {
  opacity: 0.45;
  pointer-events: none;
  cursor: not-allowed;
}

.mode-item--dimmed:hover {
  background: transparent;
}

.mode-item--ultra .mode-item-label,
.mode-item--ultra .mode-item-icon {
  color: #dabb5e;
}

.mode-item-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mode-item-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  color: var(--text-secondary);
}

.mode-item-label {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--text-primary);
}

.mode-item--active .mode-item-label {
  font-weight: 700;
}

.mode-item-check {
  width: 14px;
  height: 14px;
  margin-left: auto;
  color: var(--van-primary-color);
  flex-shrink: 0;
}

.mode-item-spacer {
  width: 14px;
  margin-left: auto;
  flex-shrink: 0;
}

.mode-item-desc {
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-secondary);
  padding-left: 22px; /* align with label start */
}

.mode-item--dimmed .mode-item-desc {
  color: var(--text-secondary);
}

/* ── Transition ── */
.mode-dropdown-enter-active,
.mode-dropdown-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}

.mode-dropdown-enter-from,
.mode-dropdown-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

/* ── Responsive ── */
@media (max-width: 375px) {
  .mode-dropdown-card {
    width: 270px;
  }

  .mode-trigger {
    width: 28px;
    height: 28px;
    min-width: 40px;
    min-height: 40px;
  }

  .mode-trigger-icon {
    width: 14px;
    height: 14px;
  }
}
</style>