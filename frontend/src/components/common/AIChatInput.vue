<template>
  <div class="chat-input-wrap" :class="{ 'is-expanded': expanded }">
    <div class="chat-sparkle" aria-hidden="true">
      <img src="@/assets/ai_logo.svg" class="ai-logo-icon" alt="AI logo" />
    </div>
    <textarea
      ref="inputRef"
      v-model="internalValue"
      class="chat-input"
      :placeholder="placeholder || '问我任何关于家庭资产的问题…'"
      aria-label="向 AI 提问"
      rows="1"
      :disabled="disabled || loading"
      @input="onInput"
      @keydown.enter.exact.prevent="onSubmit"
    ></textarea>
    <transition name="fade">
      <button v-show="showExpand" class="chat-expand-btn" :aria-label="expanded ? '收起输入框' : '展开输入框'" @click="toggleExpand">
        <svg v-if="!expanded" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="10" y1="14" x2="3" y2="21"/><line x1="21" y1="3" x2="14" y2="10"/></svg>
      </button>
    </transition>
    <button
      class="chat-send"
      :class="{ active: internalValue.trim() }"
      :disabled="disabled || loading || !internalValue.trim()"
      aria-label="发送"
      @click="onSubmit"
    >
      <van-loading v-if="loading" size="16px" color="currentColor" />
      <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'

const props = defineProps<{
  modelValue: string
  placeholder?: string
  disabled?: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'submit', value: string): void
}>()

const internalValue = ref(props.modelValue)
const expanded = ref(false)
const showExpand = ref(false)
const inputRef = ref<HTMLTextAreaElement | null>(null)

watch(() => props.modelValue, (val) => {
  if (val !== internalValue.value) {
    internalValue.value = val
    nextTick(adjustHeight)
  }
})

watch(internalValue, (val) => {
  emit('update:modelValue', val)
})

function onInput() {
  adjustHeight()
}

function onSubmit() {
  if (props.disabled || props.loading || !internalValue.value.trim()) return
  emit('submit', internalValue.value.trim())
}

function toggleExpand() {
  expanded.value = !expanded.value
  nextTick(adjustHeight)
}

function adjustHeight() {
  if (!inputRef.value) return
  const el = inputRef.value

  if (expanded.value) {
    showExpand.value = true
    el.style.height = '140px'
    return
  }

  el.style.height = '20px'
  const scrollH = el.scrollHeight
  showExpand.value = scrollH > 45
  el.style.height = `${Math.min(scrollH, 100)}px`
}

onMounted(() => {
  nextTick(adjustHeight)
})
</script>

<style scoped>
.chat-input-wrap {
  position: relative;
  display: flex;
  background: var(--card-bg, #fff);
  border-radius: 20px;
  padding: 12px 48px 12px 36px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  border: 1px solid var(--separator, #eee);
  transition: border-radius 0.2s, border-color 0.15s, box-shadow 0.15s;
  min-height: 44px;
}

[data-theme='dark'] .chat-input-wrap {
  background: var(--card-bg, #1c1c1e);
  border-color: var(--separator, #2c2c2e);
}

.chat-input-wrap.is-expanded {
  border-radius: 16px;
}

.chat-input-wrap:focus-within {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.12);
}

.chat-sparkle {
  position: absolute;
  top: 10px;
  left: 10px;
  display: flex;
  align-items: center;
}

.ai-logo-icon {
  width: 20px;
  height: 20px;
  object-fit: contain;
}

.chat-input {
  width: 100%;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--text-primary, #000);
  outline: none;
  resize: none;
  overflow-y: auto;
  line-height: 20px;
  height: 20px;
  padding: 0;
  margin: 0;
  transition: height 0.1s ease;
}

[data-theme='dark'] .chat-input {
  color: var(--text-primary, #fff);
}

.chat-input:disabled {
  opacity: 0.7;
}

.chat-input::-webkit-scrollbar {
  width: 4px;
}

.chat-input::-webkit-scrollbar-thumb {
  background: rgba(0,0,0,0.15);
  border-radius: 2px;
}

[data-theme='dark'] .chat-input::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.15);
}

.chat-expand-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-tertiary, #999);
  transition: background 0.15s, color 0.15s;
  z-index: 2;
}

.chat-expand-btn:hover {
  background: rgba(0,0,0,0.05);
  color: var(--text-secondary, #666);
}

[data-theme='dark'] .chat-expand-btn:hover {
  background: rgba(255,255,255,0.1);
  color: #ccc;
}

.chat-input::placeholder {
  color: var(--text-tertiary, #999);
}

.chat-send {
  position: absolute;
  bottom: 4px;
  right: 4px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(99,102,241,0.15);
  color: #6366f1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  z-index: 2;
}

.chat-send.active {
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  color: #fff;
}

.chat-send:disabled {
  cursor: default;
  opacity: 0.5;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
