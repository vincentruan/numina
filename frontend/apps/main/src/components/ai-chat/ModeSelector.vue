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
  // Use visualViewport for mobile Safari compatibility (excludes browser chrome)
  const viewportHeight = window.visualViewport?.height ?? window.innerHeight
  const gap = 8
  
  const panelLeft = rect.left
  const popupWidth = 300
  let left = panelLeft
  if (left + popupWidth > window.innerWidth - 16) {
    left = Math.max(16, window.innerWidth - popupWidth - 16)
  }

  popupPosition.value = {
    position: 'fixed' as const,
    bottom: `${viewportHeight - rect.top + gap}px`,
    left: `${left}px`,
    maxWidth: `calc(100vw - 32px)`,
  }
}

function togglePopup() {
  popupOpen.value = !popupOpen.value
  if (popupOpen.value) {
    nextTick(() => updatePopupPosition())
  }
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
  // Listen for visualViewport changes (mobile Safari address bar show/hide)
  window.visualViewport?.addEventListener('resize', onScrollOrResize)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onEscapeKey)
  document.removeEventListener('click', onOutsideClick, true)
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
  window.visualViewport?.removeEventListener('resize', onScrollOrResize)
})
</script>

<template>
  <!-- 模式触发按钮 -->
  <button
    ref="triggerRef"
    class="mode-trigger control-btn"
    :class="[`mode-trigger--${currentMode}`]"
    @click.stop="togglePopup"
  >
    <span class="mode-trigger-shimmer" />
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
  position: relative;
}

/* ── Glow halo (like AIBrainIcon ::before) ── */
.mode-trigger::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 48px;
  height: 48px;
  border-radius: 50%;
  z-index: 0;
  filter: blur(6px);
  opacity: 0;
  transition: opacity 0.3s, background 0.3s;
  pointer-events: none;
}

/* ── Shimmer sweep overlay ── */
.mode-trigger-shimmer {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(
    105deg,
    transparent 30%,
    rgba(255, 255, 255, 0.35) 50%,
    transparent 70%
  );
  animation: mode-shimmer 3s ease-in-out infinite;
  pointer-events: none;
  z-index: 1;
}

.mode-trigger:hover::before {
  opacity: 0.8;
}

.mode-trigger:active {
  transform: scale(0.92);
}

/* ── Per-mode colors ── */

/* flash — theme indigo */
.mode-trigger--flash {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.2);
  color: #818cf8;
}
.mode-trigger--flash::before {
  background: rgba(99, 102, 241, 0.18);
}
.mode-trigger--flash:hover {
  background: rgba(99, 102, 241, 0.15);
}

/* thinking — theme primary (violet) */
.mode-trigger--thinking {
  background: rgba(139, 92, 246, 0.08);
  border-color: rgba(139, 92, 246, 0.2);
  color: #a78bfa;
}
.mode-trigger--thinking::before {
  background: rgba(139, 92, 246, 0.18);
}
.mode-trigger--thinking:hover {
  background: rgba(139, 92, 246, 0.15);
}

/* pro — teal */
.mode-trigger--pro {
  background: rgba(20, 184, 166, 0.08);
  border-color: rgba(20, 184, 166, 0.2);
  color: #2dd4bf;
}
.mode-trigger--pro::before {
  background: rgba(20, 184, 166, 0.18);
}
.mode-trigger--pro:hover {
  background: rgba(20, 184, 166, 0.15);
}

/* ultra — warm gold (existing) */
.mode-trigger--ultra {
  background: rgba(218, 187, 94, 0.12);
  border-color: rgba(218, 187, 94, 0.3);
  color: #dabb5e;
}
.mode-trigger--ultra::before {
  background: rgba(218, 187, 94, 0.22);
}

/* ── Pulse ripple — only on ultra mode ── */
.mode-trigger--ultra::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  transform: translate(-50%, -50%) scale(1);
  opacity: 0;
  pointer-events: none;
  z-index: 0;
  box-shadow: 0 0 0 2px rgba(218, 187, 94, 0.6);
  animation: mode-pulse-ripple 2.4s ease-out infinite;
}
.mode-trigger--ultra:hover {
  background: rgba(218, 187, 94, 0.2);
}

/* Dark mode shimmer uses lower opacity */
:global([data-theme='dark']) .mode-trigger-shimmer {
  background: linear-gradient(
    105deg,
    transparent 30%,
    rgba(255, 255, 255, 0.15) 50%,
    transparent 70%
  );
}

@keyframes mode-shimmer {
  0% {
    left: -100%;
  }
  60% {
    left: 100%;
  }
  100% {
    left: 100%;
  }
}

@keyframes mode-pulse-ripple {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.6;
  }
  100% {
    transform: translate(-50%, -50%) scale(2.2);
    opacity: 0;
  }
}

.mode-trigger-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  position: relative;
  z-index: 2;
}

/* ── Dropdown ── */
.mode-dropdown {
  z-index: 1002;
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