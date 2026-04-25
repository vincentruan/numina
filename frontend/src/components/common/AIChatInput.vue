<template>
  <div class="input-shell">
    <!-- Quick action bar -->
    <div class="quick-bar">
      <button class="quick-btn" aria-label="上传文件" title="上传文件" @click="emit('action', 'file')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="12" y1="18" x2="12" y2="12"/>
          <line x1="9" y1="15" x2="15" y2="15"/>
        </svg>
        <span>文件</span>
      </button>
      <button class="quick-btn" aria-label="上传图片" title="上传图片" @click="emit('action', 'image')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <circle cx="8.5" cy="8.5" r="1.5"/>
          <polyline points="21 15 16 10 5 21"/>
        </svg>
        <span>图片</span>
      </button>
      <button class="quick-btn" aria-label="解析链接" title="解析链接" @click="emit('action', 'link')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
        </svg>
        <span>链接</span>
      </button>
      <div class="quick-bar-divider" aria-hidden="true" />
      <button v-if="showClear" class="quick-btn quick-btn--danger" aria-label="清空记录" title="清空记录" @click="emit('action', 'clear')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
          <path d="M10 11v6"/>
          <path d="M14 11v6"/>
          <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
        </svg>
        <span>清空</span>
      </button>
    </div>

    <!-- Text input row -->
    <div class="input-row" :class="{ 'is-focused': focused, 'is-expanded': expanded }">
      <div class="input-ai-icon" aria-hidden="true">
        <svg class="ai-logo-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
          <path d="M810.161862 222.967283a13.594179 13.594179 0 0 0-13.594179-13.594179H696.289285a13.594179 13.594179 0 0 0-13.594179 13.594179v71.21302h127.523635V222.967283zM810.161862 337.693051H682.638227v146.180081l127.523635 220.862745V337.693051zM417.864578 71.156141c76.218408 11.887796 155.565184 49.883242 229.337777 109.947897a13.651058 13.651058 0 0 0 19.168361-1.990779 13.651058 13.651058 0 0 0-1.9339-19.168361C586.853302 96.865634 503.126812 56.879409 422.130534 44.25218a13.651058 13.651058 0 0 0-4.265956 26.903961z"/>
          <path d="M856.063545 396.165084a13.651058 13.651058 0 0 0-24.05999 12.740987c117.512859 222.057213 100.733433 458.334278-39.019275 549.739488-74.341388 48.575015-173.1978 50.736433-278.367827 6.029217-86.513581-36.800978-168.590568-101.643504-236.504583-185.768149l18.087652-31.454313h241.168694a6.029217 6.029217 0 0 0 5.232906-9.100706l-45.27601-78.322946a14.959285 14.959285 0 0 0-12.911625-7.394323H351.031273l109.037827-188.839638 221.488418 383.651614a13.992335 13.992335 0 0 0 12.172194 7.053046h114.441371c10.807088 0 17.632617-11.717158 12.172193-21.045381l-10.067655-17.518858-127.523635-220.862745L472.184414 230.475365a14.049214 14.049214 0 0 0-24.344387 0l-248.392379 430.23585C97.007832 470.847748 89.49975 262.78287 186.251625 148.625896a13.651058 13.651058 0 0 0-20.817864-17.632617c-106.364495 125.419097-97.150031 353.789924 18.087652 557.19069l-83.783369 145.156252a14.049214 14.049214 0 0 0 12.172193 21.102261h114.441371c5.005388 0 9.6695-2.673332 12.172194-7.053047l25.02694-43.34211c69.392879 83.669611 152.664334 148.284619 240.486141 185.597512 53.694162 22.865522 106.193857 34.241404 155.223907 34.241404 54.774871 0 105.283786-14.219852 148.682775-42.545798 74.853302-48.916292 120.470588-136.226185 128.376826-245.662167 7.7356-106.648892-20.817864-227.233239-80.256846-339.570072z"/>
          <path d="M280.842082 142.539799l14.39049 40.896295 14.390491-40.896295c5.972338-17.063823 19.338999-30.373604 36.402822-36.402822L386.8653 91.746487l-40.953174-14.390491c-17.006943-5.972338-30.373604-19.338999-36.402822-36.402822L295.289452 0.056879l-14.390491 40.953175c-6.029217 17.006943-19.338999 30.373604-36.402821 36.345942l-40.953175 14.390491 40.953175 14.39049c16.950064 6.029217 30.373604 19.395878 36.402821 36.402822z"/>
        </svg>
      </div>
      <textarea
        ref="inputRef"
        v-model="internalValue"
        class="chat-textarea"
        :placeholder="placeholder || '请输入您的问题…'"
        aria-label="向 AI 提问"
        rows="1"
        :disabled="disabled || loading"
        @input="onInput"
        @focus="focused = true"
        @blur="focused = false"
        @keydown.enter.exact.prevent="onSubmit"
      />
      <button
        v-if="internalValue.length > 60"
        class="expand-btn"
        :aria-label="expanded ? '收起' : '展开'"
        @click="toggleExpand"
      >
        <svg v-if="!expanded" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/>
          <line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
        </svg>
        <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/>
          <line x1="10" y1="14" x2="3" y2="21"/><line x1="21" y1="3" x2="14" y2="10"/>
        </svg>
      </button>
      <!-- Abort button (shown while loading) -->
      <button
        v-if="loading"
        class="send-btn send-btn--abort"
        aria-label="中止生成"
        @click="emit('abort')"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <rect x="4" y="4" width="16" height="16" rx="2"/>
        </svg>
      </button>
      <!-- Send button (shown when not loading) -->
      <button
        v-else
        class="send-btn"
        :class="{ 'send-btn--active': internalValue.trim() }"
        :disabled="disabled || !internalValue.trim()"
        aria-label="发送"
        @click="onSubmit"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'

const props = defineProps<{
  modelValue: string
  placeholder?: string
  disabled?: boolean
  loading?: boolean
  showClear?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'submit', value: string): void
  (e: 'abort'): void
  (e: 'action', type: 'file' | 'image' | 'link' | 'clear'): void
}>()

const internalValue = ref(props.modelValue)
const expanded = ref(false)
const focused = ref(false)
const inputRef = ref<HTMLTextAreaElement | null>(null)

watch(
  () => props.modelValue,
  (val) => {
    if (val !== internalValue.value) {
      internalValue.value = val
      nextTick(adjustHeight)
    }
  },
)

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
  const el = inputRef.value
  if (!el) return
  if (expanded.value) {
    el.style.height = '120px'
    return
  }
  el.style.height = '20px'
  el.style.height = `${Math.min(el.scrollHeight, 96)}px`
}

onMounted(() => nextTick(adjustHeight))
</script>

<style scoped>
.input-shell {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ── Quick action bar ── */
.quick-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 4px;
}

.quick-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  min-height: 32px;
  white-space: nowrap;
}

.quick-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
}

.quick-btn:active {
  background: rgba(255, 255, 255, 0.14);
  transform: scale(0.97);
}

.quick-btn--danger {
  color: rgba(239, 68, 68, 0.6);
}

.quick-btn--danger:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.quick-bar-divider {
  flex: 1;
}

/* ── Input row ── */
.input-row {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 0;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 18px;
  padding: 10px 48px 10px 38px;
  min-height: 44px;
  transition:
    border-color 0.2s,
    box-shadow 0.2s,
    border-radius 0.2s;
}

.input-row.is-focused {
  border-color: rgba(99, 102, 241, 0.6);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.input-row.is-expanded {
  border-radius: 14px;
}

.input-ai-icon {
  position: absolute;
  left: 10px;
  bottom: 12px;
  display: flex;
  align-items: center;
}

.ai-logo-icon {
  width: 18px;
  height: 18px;
  color: #6366f1;
  flex-shrink: 0;
}

.chat-textarea {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
  outline: none;
  resize: none;
  overflow-y: auto;
  line-height: 20px;
  height: 20px;
  padding: 0;
  margin: 0;
  transition: height 0.12s ease;
  caret-color: #6366f1;
}

.chat-textarea::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.chat-textarea:disabled {
  opacity: 0.5;
}

.chat-textarea::-webkit-scrollbar {
  width: 3px;
}

.chat-textarea::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
}

/* ── Expand button ── */
.expand-btn {
  position: absolute;
  top: 6px;
  right: 44px;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.3);
  transition: background 0.15s, color 0.15s;
}

.expand-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.6);
}

/* ── Send button ── */
.send-btn {
  position: absolute;
  bottom: 4px;
  right: 4px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(99, 102, 241, 0.2);
  color: rgba(99, 102, 241, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    background 0.2s,
    color 0.2s,
    transform 0.15s;
}

.send-btn--active {
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  color: #fff;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.4);
}

.send-btn--active:hover {
  transform: scale(1.05);
}

.send-btn--active:active {
  transform: scale(0.95);
}

.send-btn:disabled {
  cursor: default;
}

.send-btn--abort {
  background: #ff3b30;
  color: #fff;
  box-shadow: 0 2px 12px rgba(255, 59, 48, 0.4);
  cursor: pointer;
}

.send-btn--abort:hover {
  transform: scale(1.05);
  background: #ff2d20;
}

.send-btn--abort:active {
  transform: scale(0.95);
}

@media (prefers-reduced-motion: reduce) {
  .send-btn,
  .quick-btn,
  .input-row {
    transition: none;
  }
}
</style>
