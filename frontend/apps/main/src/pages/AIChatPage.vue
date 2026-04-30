<template>
  <div class="ai-chat-page" :class="{ 'theme-light': isLight }">
    <!-- Fixed top bar: [history/sidebar] [title] [new chat] -->
    <div class="chat-header">
      <button class="header-btn" aria-label="会话历史" @click="showHistory = true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <h1 class="header-title">{{ sessionTitle }}</h1>
      <div class="header-actions">
        <button class="header-btn" aria-label="切换主题" @click="toggleTheme">
          <svg v-if="isLight" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        </button>
        <button class="header-btn" aria-label="新对话" @click="onNewChat">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- History sidebar drawer -->
    <van-popup v-model:show="showHistory" position="left" :style="{ width: '80%', height: '100%' }">
      <div class="history-panel">
        <div class="history-header">
          <span class="history-title">会话历史</span>
          <button class="header-btn" @click="showHistory = false">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="history-empty">
          <p>暂无历史会话</p>
          <p class="history-hint">每次对话记录将显示在这里</p>
        </div>
      </div>
    </van-popup>

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
              <div class="bubble-body">
                <!-- Deep think block (assistant only) -->
                <div
                  v-if="msg.role === 'assistant' && msg.thinkContent"
                  class="think-block"
                  :class="{ 'think-block--open': msg.thinkOpen }"
                >
                  <button class="think-toggle" @click="msg.thinkOpen = !msg.thinkOpen">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <path d="M9.663 17h4.673M12 3a6 6 0 0 1 6 6c0 2.22-1.2 4.16-3 5.2V16a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-1.8A6 6 0 0 1 12 3z"/>
                      <path d="M9 21h6"/>
                    </svg>
                    <span v-if="msg.thinkDone">已深度思考 {{ msg.thinkSeconds }}s</span>
                    <span v-else class="think-ing">深度思考中…</span>
                    <svg class="think-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <polyline points="6 9 12 15 18 9"/>
                    </svg>
                  </button>
                  <div v-if="msg.thinkOpen" class="think-content" v-html="msg.thinkContent" />
                </div>
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
import { useSettingsStore } from '@/stores/settings'
import { showConfirmDialog, showToast } from 'vant'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { sendChatMessage, getChatHistory, clearChatHistory, markChatRead } from '@/api/ai'
import { useAIStore } from '@/stores/ai'
import AIChatInput from '@/components/common/AIChatInput.vue'

// Configure marked
marked.use({ breaks: true })

function renderMarkdown(text: string): string {
  return DOMPurify.sanitize(marked.parse(text) as string)
}

// Static data — module-level to avoid re-allocation on each mount
const SUGGESTIONS = [
  {
    text: '我们家净资产是多少？',
    icon: { viewBox: '0 0 24 24', paths: ['M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6'] },
  },
  {
    text: '哪类资产占比最高？',
    icon: { viewBox: '0 0 24 24', paths: ['M21.21 15.89A10 10 0 1 1 8 2.83', 'M22 12A10 10 0 0 0 12 2v10z'] },
  },
  {
    text: '有哪些闲置资产？',
    icon: { viewBox: '0 0 24 24', paths: ['M20 7H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z', 'M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16'] },
  },
  {
    text: '净资产趋势如何？',
    icon: { viewBox: '0 0 24 24', paths: ['M23 6l-9.5 9.5-5-5L1 18', 'M17 6h6v6'] },
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
  // deep think fields
  thinkContent?: string
  thinkOpen?: boolean
  thinkDone?: boolean
  thinkSeconds?: number
}

const { t } = useI18n()
const route = useRoute()
const aiStore = useAIStore()
const settingsStore = useSettingsStore()
const messages = ref<Message[]>([])
const inputText = ref('')
const asking = ref(false)
const deepThink = ref(false)
const webSearch = ref(false)
const scrollRef = ref<HTMLElement | null>(null)
const showHistory = ref(false)

// Follow global theme: light when theme==='light', dark otherwise (dark/system default to dark)
const isLight = computed(() => settingsStore.theme === 'light')
let abortController: AbortController | null = null

function toggleTheme() {
  settingsStore.setTheme(isLight.value ? 'dark' : 'light')
}

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

async function onNewChat() {
  if (messages.value.length === 0) return
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: '开始新对话？当前对话将被清空。' })
    await clearChatHistory()
    messages.value = []
  } catch {
    // cancelled
  }
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

  // Deep think: start timer and add placeholder think block
  let thinkTimer: ReturnType<typeof setInterval> | null = null
  let thinkStart = 0
  let thinkMsgIdx = -1

  if (deepThink.value) {
    thinkStart = Date.now()
    const thinkMsg: Message = {
      id: `think-${Date.now()}`,
      role: 'assistant',
      content: '',
      renderedContent: '',
      created_at: new Date().toISOString(),
      displayTime: formatTime(new Date().toISOString()),
      thinkContent: '<p>正在深度分析您的问题…</p>',
      thinkOpen: true,
      thinkDone: false,
      thinkSeconds: 0,
    }
    messages.value.push(thinkMsg)
    thinkMsgIdx = messages.value.length - 1
    thinkTimer = setInterval(() => {
      if (thinkMsgIdx >= 0) {
        messages.value[thinkMsgIdx].thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
      }
    }, 1000)
    await scrollToBottom()
  }

  try {
    const res = await sendChatMessage(q, abortController.signal)
    const fullText = res.data.answer

    // Finish deep think block
    if (thinkTimer) {
      clearInterval(thinkTimer)
      thinkTimer = null
    }

    let msg: Message
    if (thinkMsgIdx >= 0) {
      // Reuse the think placeholder message, mark done and collapse
      messages.value[thinkMsgIdx].thinkDone = true
      messages.value[thinkMsgIdx].thinkOpen = false
      messages.value[thinkMsgIdx].thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
      messages.value[thinkMsgIdx].id = res.data.message_id
      msg = messages.value[thinkMsgIdx]
    } else {
      msg = {
        id: res.data.message_id,
        role: 'assistant',
        content: '',
        renderedContent: '',
        created_at: new Date().toISOString(),
        displayTime: formatTime(new Date().toISOString()),
      }
      messages.value.push(msg)
      thinkMsgIdx = messages.value.length - 1
    }

    const idx = thinkMsgIdx
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
    return
  } catch (err: unknown) {
    if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
    if (err instanceof Error && (err.name === 'AbortError' || err.name === 'CanceledError')) return
    // Replace think placeholder or push new error message
    const errMsg: Message = {
      id: Date.now().toString(),
      role: 'assistant',
      content: '抱歉，AI 服务暂时不可用，请稍后再试。',
      renderedContent: '<p>抱歉，AI 服务暂时不可用，请稍后再试。</p>',
      created_at: new Date().toISOString(),
      displayTime: formatTime(new Date().toISOString()),
    }
    if (thinkMsgIdx >= 0) {
      messages.value[thinkMsgIdx] = errMsg
    } else {
      messages.value.push(errMsg)
    }
  } finally {
    if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
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
  const prevUser = [...messages.value].slice(0, idx).reverse().find((m) => m.role === 'user')
  if (!prevUser || asking.value) return
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
/* ── CSS variables for day/night theme ── */
.ai-chat-page {
  --bg: #0f1117;
  --bg-header: rgba(15, 17, 23, 0.95);
  --border: rgba(255, 255, 255, 0.06);
  --text-primary: #ffffff;
  --text-secondary: rgba(255, 255, 255, 0.5);
  --text-muted: rgba(255, 255, 255, 0.3);
  --bubble-user-bg: #010120;
  --bubble-user-color: #ffffff;
  --bubble-ai-bg: rgba(189, 187, 255, 0.12);
  --bubble-ai-color: rgba(255, 255, 255, 0.85);
  --bubble-ai-border: rgba(189, 187, 255, 0.2);
  --btn-color: rgba(255, 255, 255, 0.7);
  --btn-hover-bg: rgba(255, 255, 255, 0.08);
  --suggestion-bg: rgba(255, 255, 255, 0.08);
  --suggestion-border: rgba(255, 255, 255, 0.12);
  --think-bg: rgba(99, 102, 241, 0.08);
  --think-border: rgba(99, 102, 241, 0.25);
  --think-color: rgba(255, 255, 255, 0.55);
}

.ai-chat-page.theme-light {
  --bg: #f5f5f7;
  --bg-header: rgba(245, 245, 247, 0.95);
  --border: rgba(0, 0, 0, 0.08);
  --text-primary: rgba(0, 0, 0, 0.85);
  --text-secondary: rgba(0, 0, 0, 0.45);
  --text-muted: rgba(0, 0, 0, 0.3);
  --bubble-user-bg: #010120;
  --bubble-user-color: #fff;
  --bubble-ai-bg: rgba(189, 187, 255, 0.08);
  --bubble-ai-color: rgba(0, 0, 0, 0.8);
  --bubble-ai-border: rgba(255, 255, 255, 0.08);
  --btn-color: rgba(0, 0, 0, 0.55);
  --btn-hover-bg: rgba(0, 0, 0, 0.06);
  --suggestion-bg: #fff;
  --suggestion-border: rgba(0, 0, 0, 0.08);
  --think-bg: rgba(99, 102, 241, 0.06);
  --think-border: rgba(99, 102, 241, 0.2);
  --think-color: rgba(0, 0, 0, 0.5);
}

/* ── Page shell ── */
.ai-chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100dvh - env(safe-area-inset-bottom));
  background: var(--bg);
}

/* ── Header ── */
.chat-header {
  display: flex;
  align-items: center;
  padding: 0 4px;
  padding-top: env(safe-area-inset-top);
  height: calc(50px + env(safe-area-inset-top));
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
}

.header-btn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--btn-color);
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.header-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--text-primary);
}

.header-title {
  flex: 1;
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 4px;
}

.header-actions {
  display: flex;
  align-items: center;
}

/* ── History sidebar ── */
.history-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  padding: env(safe-area-inset-top) 0 0;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.history-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.history-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 14px;
}

.history-empty p {
  margin: 0;
}

.history-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
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
  background: radial-gradient(circle, rgba(99, 102, 241, 0.4) 0%, transparent 70%);
  animation: pulse-glow 3s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% { opacity: 0.7; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.15); }
}

.hero-icon {
  width: 48px;
  height: 48px;
  color: #818cf8;
  position: relative;
  z-index: 1;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.empty-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
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
  background: var(--suggestion-bg);
  border: 1px solid var(--suggestion-border);
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
  color: var(--text-primary);
  line-height: 1.4;
}

.suggestion-arrow {
  color: var(--text-muted);
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
  max-width: 86%;
}

.bubble-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.message-row.user .bubble-body {
  align-items: flex-end;
}

/* ── Deep think block ── */
.think-block {
  background: var(--think-bg);
  border: 1px solid var(--think-border);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 4px;
}

.think-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  background: transparent;
  border: none;
  color: #818cf8;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
}

.think-toggle:hover {
  background: rgba(99, 102, 241, 0.08);
}

.think-ing {
  animation: blink 1.2s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.think-chevron {
  margin-left: auto;
  transition: transform 0.2s;
}

.think-block--open .think-chevron {
  transform: rotate(180deg);
}

.think-content {
  padding: 8px 12px 10px;
  font-size: 12px;
  color: var(--think-color);
  line-height: 1.6;
  border-top: 1px solid var(--think-border);
}

.think-content :deep(p) { margin: 0 0 4px; }
.think-content :deep(p:last-child) { margin-bottom: 0; }

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
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--bubble-ai-border);
  border-radius: 8px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.bubble.assistant .bubble-text :deep(pre code) {
  background: transparent;
  padding: 0;
  color: var(--bubble-ai-color);
}
.bubble.assistant .bubble-text :deep(strong) { color: var(--text-primary); }
.bubble.assistant .bubble-text :deep(a) { color: #818cf8; text-decoration: underline; }

.bubble.user .bubble-text {
  background: var(--bubble-user-bg);
  color: var(--bubble-user-color);
  border-bottom-right-radius: 4px;
}

.bubble.assistant .bubble-text {
  background: var(--bubble-ai-bg);
  color: var(--bubble-ai-color);
  border-bottom-left-radius: 4px;
  border: 1px solid var(--bubble-ai-border);
}

.msg-time {
  font-size: 11px;
  color: var(--text-muted);
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
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.msg-action-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--btn-color);
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
  background: var(--bg-header);
  border-top: 1px solid var(--border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
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
