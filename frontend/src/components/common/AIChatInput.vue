<template>
  <div class="chat-input-wrap" :class="{ 'is-expanded': expanded }">
    <div class="chat-sparkle" aria-hidden="true">
      <svg class="ai-logo-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
        <path d="M810.161862 222.967283a13.594179 13.594179 0 0 0-13.594179-13.594179H696.289285a13.594179 13.594179 0 0 0-13.594179 13.594179v71.21302h127.523635V222.967283zM810.161862 337.693051H682.638227v146.180081l127.523635 220.862745V337.693051zM417.864578 71.156141c76.218408 11.887796 155.565184 49.883242 229.337777 109.947897a13.651058 13.651058 0 0 0 19.168361-1.990779 13.651058 13.651058 0 0 0-1.9339-19.168361C586.853302 96.865634 503.126812 56.879409 422.130534 44.25218a13.651058 13.651058 0 0 0-4.265956 26.903961z"/>
        <path d="M856.063545 396.165084a13.651058 13.651058 0 0 0-24.05999 12.740987c117.512859 222.057213 100.733433 458.334278-39.019275 549.739488-74.341388 48.575015-173.1978 50.736433-278.367827 6.029217-86.513581-36.800978-168.590568-101.643504-236.504583-185.768149l18.087652-31.454313h241.168694a6.029217 6.029217 0 0 0 5.232906-9.100706l-45.27601-78.322946a14.959285 14.959285 0 0 0-12.911625-7.394323H351.031273l109.037827-188.839638 221.488418 383.651614a13.992335 13.992335 0 0 0 12.172194 7.053046h114.441371c10.807088 0 17.632617-11.717158 12.172193-21.045381l-10.067655-17.518858-127.523635-220.862745L472.184414 230.475365a14.049214 14.049214 0 0 0-24.344387 0l-248.392379 430.23585C97.007832 470.847748 89.49975 262.78287 186.251625 148.625896a13.651058 13.651058 0 0 0-20.817864-17.632617c-106.364495 125.419097-97.150031 353.789924 18.087652 557.19069l-83.783369 145.156252a14.049214 14.049214 0 0 0 12.172193 21.102261h114.441371c5.005388 0 9.6695-2.673332 12.172194-7.053047l25.02694-43.34211c69.392879 83.669611 152.664334 148.284619 240.486141 185.597512 53.694162 22.865522 106.193857 34.241404 155.223907 34.241404 54.774871 0 105.283786-14.219852 148.682775-42.545798 74.853302-48.916292 120.470588-136.226185 128.376826-245.662167 7.7356-106.648892-20.817864-227.233239-80.256846-339.570072z"/>
        <path d="M280.842082 142.539799l14.39049 40.896295 14.390491-40.896295c5.972338-17.063823 19.338999-30.373604 36.402822-36.402822L386.8653 91.746487l-40.953174-14.390491c-17.006943-5.972338-30.373604-19.338999-36.402822-36.402822L295.289452 0.056879l-14.390491 40.953175c-6.029217 17.006943-19.338999 30.373604-36.402821 36.345942l-40.953175 14.390491 40.953175 14.39049c16.950064 6.029217 30.373604 19.395878 36.402821 36.402822z"/>
      </svg>
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
  color: #6366f1;
  flex-shrink: 0;
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
