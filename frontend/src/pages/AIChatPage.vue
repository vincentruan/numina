<template>
  <div class="ai-chat-page">
    <!-- Custom title bar -->
    <div class="chat-header">
      <button class="header-back" aria-label="返回" @click="$router.back()">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>
      <h1 class="header-title">{{ sessionTitle }}</h1>
      <div class="header-spacer" aria-hidden="true" />
    </div>

    <!-- Chat body -->
    <div ref="scrollRef" class="chat-body">

      <!-- Empty state: hero + suggestion cards -->
      <div v-if="!messages.length" class="chat-empty">
        <div class="empty-hero" aria-hidden="true">
          <div class="hero-glow" />
          <svg class="hero-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
            <path d="M810.161862 222.967283a13.594179 13.594179 0 0 0-13.594179-13.594179H696.289285a13.594179 13.594179 0 0 0-13.594179 13.594179v71.21302h127.523635V222.967283zM810.161862 337.693051H682.638227v146.180081l127.523635 220.862745V337.693051zM417.864578 71.156141c76.218408 11.887796 155.565184 49.883242 229.337777 109.947897a13.651058 13.651058 0 0 0 19.168361-1.990779 13.651058 13.651058 0 0 0-1.9339-19.168361C586.853302 96.865634 503.126812 56.879409 422.130534 44.25218a13.651058 13.651058 0 0 0-4.265956 26.903961z"/>
            <path d="M856.063545 396.165084a13.651058 13.651058 0 0 0-24.05999 12.740987c117.512859 222.057213 100.733433 458.334278-39.019275 549.739488-74.341388 48.575015-173.1978 50.736433-278.367827 6.029217-86.513581-36.800978-168.590568-101.643504-236.504583-185.768149l18.087652-31.454313h241.168694a6.029217 6.029217 0 0 0 5.232906-9.100706l-45.27601-78.322946a14.959285 14.959285 0 0 0-12.911625-7.394323H351.031273l109.037827-188.839638 221.488418 383.651614a13.992335 13.992335 0 0 0 12.172194 7.053046h114.441371c10.807088 0 17.632617-11.717158 12.172193-21.045381l-10.067655-17.518858-127.523635-220.862745L472.184414 230.475365a14.049214 14.049214 0 0 0-24.344387 0l-248.392379 430.23585C97.007832 470.847748 89.49975 262.78287 186.251625 148.625896a13.651058 13.651058 0 0 0-20.817864-17.632617c-106.364495 125.419097-97.150031 353.789924 18.087652 557.19069l-83.783369 145.156252a14.049214 14.049214 0 0 0 12.172193 21.102261h114.441371c5.005388 0 9.6695-2.673332 12.172194-7.053047l25.02694-43.34211c69.392879 83.669611 152.664334 148.284619 240.486141 185.597512 53.694162 22.865522 106.193857 34.241404 155.223907 34.241404 54.774871 0 105.283786-14.219852 148.682775-42.545798 74.853302-48.916292 120.470588-136.226185 128.376826-245.662167 7.7356-106.648892-20.817864-227.233239-80.256846-339.570072z"/>
            <path d="M280.842082 142.539799l14.39049 40.896295 14.390491-40.896295c5.972338-17.063823 19.338999-30.373604 36.402822-36.402822L386.8653 91.746487l-40.953174-14.390491c-17.006943-5.972338-30.373604-19.338999-36.402822-36.402822L295.289452 0.056879l-14.390491 40.953175c-6.029217 17.006943-19.338999 30.373604-36.402821 36.345942l-40.953175 14.390491 40.953175 14.39049c16.950064 6.029217 30.373604 19.395878 36.402821 36.402822z"/>
          </svg>
        </div>
        <p class="empty-title">你好，我是 Numina AI</p>
        <p class="empty-subtitle">问我任何关于家庭资产的问题</p>

        <!-- Suggestion cards -->
        <div class="suggestion-grid">
          <button
            v-for="s in suggestions"
            :key="s.text"
            class="suggestion-card"
            @click="onChipClick(s.text)"
          >
            <span class="suggestion-icon" aria-hidden="true">
              <svg :viewBox="s.icon.viewBox" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path v-for="(d, i) in s.icon.paths" :key="i" :d="d" />
              </svg>
            </span>
            <span class="suggestion-text">{{ s.text }}</span>
            <span class="suggestion-arrow" aria-hidden="true">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </span>
          </button>
        </div>
      </div>

      <!-- Messages -->
      <template v-else>
        <transition-group name="msg" tag="div" class="msg-list">
          <div
            v-for="(msg, idx) in messages"
            :key="msg.id"
            class="message-row"
            :class="msg.role"
          >
          <div class="bubble" :class="msg.role">
            <div v-if="msg.role === 'assistant'" class="assistant-avatar" aria-hidden="true">
              <AIBrainIcon class="avatar-icon" />
            </div>
            <div class="bubble-body">
              <div
                v-if="msg.role === 'assistant'"
                class="bubble-text"
                v-html="msg.renderedContent ?? ''"
              />
              <div v-else class="bubble-text">{{ msg.content }}</div>
              <span class="msg-time">{{ msg.displayTime }}</span>
              <!-- Assistant message actions -->
              <div v-if="msg.role === 'assistant'" class="msg-actions">
                <button class="msg-action-btn" aria-label="复制" title="复制" @click="onCopy(msg.content)">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                </button>
                <button class="msg-action-btn" aria-label="重新生成" title="重新生成" :disabled="asking" @click="onRegenerate(idx)">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <polyline points="1 4 1 10 7 10"/>
                    <path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
                  </svg>
                </button>
                <button
                  class="msg-action-btn"
                  :class="{ 'msg-action-btn--active': msg.feedback === 1 }"
                  aria-label="有帮助"
                  title="有帮助"
                  @click="onFeedback(msg.id, 1)"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
                    <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
                  </svg>
                </button>
                <button
                  class="msg-action-btn"
                  :class="{ 'msg-action-btn--active': msg.feedback === -1 }"
                  aria-label="没帮助"
                  title="没帮助"
                  @click="onFeedback(msg.id, -1)"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
                    <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
        </transition-group>

        <!-- Skeleton loading state -->
        <transition name="msg">
          <div v-if="asking" class="message-row assistant">
            <div class="bubble assistant">
              <div class="assistant-avatar" aria-hidden="true">
                <AIBrainIcon class="avatar-icon" />
              </div>
              <div class="bubble-body">
                <div class="skeleton-bubble" aria-label="AI 正在思考">
                  <div class="skeleton-line skeleton-line--long" />
                  <div class="skeleton-line skeleton-line--medium" />
                  <div class="skeleton-line skeleton-line--short" />
                </div>
              </div>
            </div>
          </div>
        </transition>
      </template>
    </div>

    <!-- Input bar -->
    <div class="input-bar">
      <AIChatInput
        v-model="inputText"
        v-model:deep-think="deepThink"
        v-model:web-search="webSearch"
        :disabled="asking"
        :loading="asking"
        :show-clear="messages.length > 0"
        placeholder="请输入您的问题…"
        @submit="onSend"
        @abort="onAbort"
        @action="onAction"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { sendChatMessage, getChatHistory, clearChatHistory, markChatRead } from '@/api/ai'
import { useAIStore } from '@/stores/ai'
import AIChatInput from '@/components/common/AIChatInput.vue'
import AIBrainIcon from '@/components/common/AIBrainIcon.vue'

// Configure marked
marked.use({ breaks: true })

function renderMarkdown(text: string): string {
  return DOMPurify.sanitize(marked.parse(text) as string)
}

// Static data — module-level to avoid re-allocation on each mount
const SUGGESTIONS = [
  {
    text: '我们家净资产是多少？',
    icon: {
      viewBox: '0 0 24 24',
      paths: ['M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6'],
    },
  },
  {
    text: '哪类资产占比最高？',
    icon: {
      viewBox: '0 0 24 24',
      paths: ['M21.21 15.89A10 10 0 1 1 8 2.83', 'M22 12A10 10 0 0 0 12 2v10z'],
    },
  },
  {
    text: '有哪些闲置资产？',
    icon: {
      viewBox: '0 0 24 24',
      paths: [
        'M20 7H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z',
        'M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16',
      ],
    },
  },
  {
    text: '净资产趋势如何？',
    icon: {
      viewBox: '0 0 24 24',
      paths: ['M23 6l-9.5 9.5-5-5L1 18', 'M17 6h6v6'],
    },
  },
]

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  renderedContent?: string
  created_at: string
  displayTime: string
  feedback?: 1 | -1 | 0
}

const { t } = useI18n()
const route = useRoute()
const aiStore = useAIStore()
const messages = ref<Message[]>([])
const inputText = ref('')
const asking = ref(false)
const deepThink = ref(false)
const webSearch = ref(false)
const scrollRef = ref<HTMLElement | null>(null)
let abortController: AbortController | null = null

const sessionTitle = computed(() => {
  const firstUser = messages.value.find((m) => m.role === 'user')
  if (!firstUser) return '新对话'
  const text = firstUser.content.trim()
  return text.length > 20 ? text.slice(0, 20) + '…' : text
})

const suggestions = SUGGESTIONS

async function scrollToBottom() {
  await nextTick()
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}

function onChipClick(text: string) {
  inputText.value = text
  onSend()
}

async function onSend() {
  const q = inputText.value.trim()
  if (!q || asking.value) return

  messages.value.push({
    id: Date.now().toString(),
    role: 'user',
    content: q,
    created_at: new Date().toISOString(),
    displayTime: formatTime(new Date().toISOString()),
  })
  inputText.value = ''
  asking.value = true
  abortController = new AbortController()
  await scrollToBottom()

  try {
    const res = await sendChatMessage(q, abortController.signal)
    const fullText = res.data.answer
    // Typewriter effect
    const msg: Message = {
      id: res.data.message_id,
      role: 'assistant',
      content: '',
      renderedContent: '',
      created_at: new Date().toISOString(),
      displayTime: formatTime(new Date().toISOString()),
    }
    messages.value.push(msg)
    const idx = messages.value.length - 1
    let i = 0
    let cancelled = false
    abortController.signal.addEventListener('abort', () => { cancelled = true })

    const tick = () => {
      if (cancelled) {
        asking.value = false
        abortController = null
        return
      }
      const chunk = fullText.slice(0, i + 1)
      messages.value[idx].content = chunk
      // Re-render markdown every 20 chars or at end to avoid O(n²)
      if (i % 20 === 0 || i === fullText.length - 1) {
        messages.value[idx].renderedContent = renderMarkdown(chunk)
      }
      i++
      if (i < fullText.length) {
        setTimeout(tick, 18)
        scrollToBottom()
      } else {
        messages.value[idx].renderedContent = renderMarkdown(fullText)
        asking.value = false
        abortController = null
        scrollToBottom()
      }
    }
    tick()
    return // typewriter handles asking=false
  } catch (err: unknown) {
    if (err instanceof Error && (err.name === 'AbortError' || err.name === 'CanceledError')) return
    messages.value.push({
      id: Date.now().toString(),
      role: 'assistant',
      content: '抱歉，AI 服务暂时不可用，请稍后再试。',
      renderedContent: '<p>抱歉，AI 服务暂时不可用，请稍后再试。</p>',
      created_at: new Date().toISOString(),
      displayTime: formatTime(new Date().toISOString()),
    })
  } finally {
    // Only reset if typewriter didn't take over
    if (asking.value) {
      asking.value = false
      abortController = null
      await scrollToBottom()
    }
  }
}

function onAbort() {
  abortController?.abort()
  asking.value = false
  abortController = null
}

async function onAction(type: 'file' | 'image' | 'link' | 'clear' | 'camera' | 'ocr' | 'webpage' | 'history') {
  if (type === 'clear') {
    try {
      await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmClearChat') })
      await clearChatHistory()
      messages.value = []
    } catch {
      // cancelled
    }
    return
  }
  showToast('🚧 该功能即将上线')
}

async function onCopy(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    showToast('✅ 已复制')
  } catch {
    showToast('❌ 复制失败')
  }
}

async function onRegenerate(idx: number) {
  // Find the user message before this assistant message
  const prevUser = [...messages.value].slice(0, idx).reverse().find((m) => m.role === 'user')
  if (!prevUser || asking.value) return
  // Remove the assistant message and re-ask
  messages.value.splice(idx, 1)
  inputText.value = prevUser.content
  await onSend()
}

function onFeedback(id: string, value: 1 | -1) {
  const msg = messages.value.find((m) => m.id === id)
  if (!msg) return
  msg.feedback = msg.feedback === value ? 0 : value
}

onMounted(async () => {
  try {
    const res = await getChatHistory()
    messages.value = res.data.map((m) => ({
      ...m,
      displayTime: formatTime(m.created_at),
      renderedContent: m.role === 'assistant' ? renderMarkdown(m.content) : undefined,
    }))
    await markChatRead()
    await scrollToBottom()
  } catch {
    // no history
  }
  const q = aiStore.draftQuery || route.query.q
  if (typeof q === 'string' && q.trim()) {
    inputText.value = q.trim()
    aiStore.draftQuery = ''
    await onSend()
  }
})
</script>

<style scoped>
/* ── Page shell ── */
.ai-chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100dvh - env(safe-area-inset-bottom));
  background: #0f1117;
}

/* ── Header ── */
.chat-header {
  display: flex;
  align-items: center;
  padding: 0 4px;
  height: 50px;
  background: rgba(15, 17, 23, 0.95);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
  padding-top: env(safe-area-inset-top);
}

.header-back {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.header-back:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.header-title {
  flex: 1;
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 8px;
}

.header-spacer {
  width: 44px;
  flex-shrink: 0;
}

/* ── Chat body ── */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overscroll-behavior: contain;
}

/* Desktop centering */
@media (min-width: 640px) {
  .chat-body {
    padding: 16px calc(50% - 384px + 16px) 8px;
  }
  .input-bar {
    padding: 8px calc(50% - 384px + 16px) calc(12px + env(safe-area-inset-bottom));
  }
}

/* ── Empty state ── */
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 0 16px;
  gap: 8px;
}

.empty-hero {
  position: relative;
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}

.hero-glow {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, transparent 70%);
  animation: pulse-glow 3s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.1); }
}

.hero-icon {
  width: 48px;
  height: 48px;
  color: #6366f1;
  position: relative;
  z-index: 1;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
}

.empty-subtitle {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
  margin: 0 0 16px;
}

/* ── Suggestion cards ── */
.suggestion-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.suggestion-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, border-color 0.15s, transform 0.15s;
  width: 100%;
}

.suggestion-card:hover {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
}

.suggestion-card:active {
  transform: scale(0.98);
}

.suggestion-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  flex-shrink: 0;
}

.suggestion-text {
  flex: 1;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.75);
  line-height: 1.4;
}

.suggestion-arrow {
  color: rgba(255, 255, 255, 0.2);
  flex-shrink: 0;
}

/* ── Messages ── */
.message-row {
  display: flex;
  flex-direction: column;
}

.message-row.user { align-items: flex-end; }
.message-row.assistant { align-items: flex-start; }

.bubble {
  max-width: 82%;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.bubble.user {
  flex-direction: row-reverse;
}

.assistant-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(99, 102, 241, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.avatar-icon {
  width: 16px;
  height: 16px;
}

.bubble-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.bubble.user .bubble-body {
  align-items: flex-end;
}

.bubble-text {
  display: block;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

/* Markdown content inside assistant bubbles */
.bubble.assistant .bubble-text :deep(p) { margin: 0 0 8px; }
.bubble.assistant .bubble-text :deep(p:last-child) { margin-bottom: 0; }
.bubble.assistant .bubble-text :deep(ul),
.bubble.assistant .bubble-text :deep(ol) { margin: 4px 0 8px 16px; padding: 0; }
.bubble.assistant .bubble-text :deep(li) { margin-bottom: 2px; }
.bubble.assistant .bubble-text :deep(code) {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.bubble.assistant .bubble-text :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.bubble.assistant .bubble-text :deep(pre code) {
  background: transparent;
  padding: 0;
  color: rgba(255, 255, 255, 0.85);
}
.bubble.assistant .bubble-text :deep(strong) { color: rgba(255, 255, 255, 0.95); }
.bubble.assistant .bubble-text :deep(a) { color: #818cf8; text-decoration: underline; }

.bubble.user .bubble-text {
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble.assistant .bubble-text {
  background: rgba(255, 255, 255, 0.07);
  color: rgba(255, 255, 255, 0.85);
  border-bottom-left-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.msg-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.25);
  padding: 0 4px;
}

/* ── Message action buttons ── */
.msg-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

.message-row:hover .msg-actions,
.message-row:focus-within .msg-actions,
.message-row:active .msg-actions {
  opacity: 1;
}

/* List reorder animation */
.msg-move {
  transition: transform 0.2s ease;
}

.msg-action-btn {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.msg-action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.7);
}

.msg-action-btn:disabled {
  cursor: default;
  opacity: 0.3;
}

.msg-action-btn--active {
  color: #818cf8;
}

/* ── Message enter animation ── */
.msg-list {
  display: contents;
}

.msg-enter-active {
  animation: msg-in 0.2s ease-out both;
}

@keyframes msg-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── Skeleton loading ── */
.skeleton-bubble {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  border-bottom-left-radius: 4px;
  min-width: 160px;
}

.skeleton-line {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.06) 0%,
    rgba(255, 255, 255, 0.12) 50%,
    rgba(255, 255, 255, 0.06) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.skeleton-line--long  { width: 85%; }
.skeleton-line--medium { width: 65%; }
.skeleton-line--short  { width: 45%; }

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Input bar ── */
.input-bar {
  padding: 8px 16px calc(12px + env(safe-area-inset-bottom));
  background: rgba(15, 17, 23, 0.95);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

@media (prefers-reduced-motion: reduce) {
  .hero-glow,
  .suggestion-card,
  .msg-enter-active,
  .skeleton-line {
    animation: none;
    transition: none;
  }
}
</style>
