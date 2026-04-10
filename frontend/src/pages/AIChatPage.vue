<template>
  <div class="ai-chat-page">
    <PageHeader title="AI 问答助手" />

    <!-- Chat history -->
    <div ref="scrollRef" class="chat-body">
      <div v-if="!messages.length" class="chat-empty">
        <p class="empty-hint">你可以问我关于家庭资产的任何问题</p>
        <div class="suggestion-chips">
          <span
            v-for="s in suggestions"
            :key="s"
            class="chip"
            @click="onChipClick(s)"
          >{{ s }}</span>
        </div>
      </div>

      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message-row"
        :class="msg.role"
      >
        <div class="bubble" :class="msg.role">
          <span v-if="msg.role === 'assistant'" class="ai-label">AI</span>
          <span class="bubble-text">{{ msg.content }}</span>
        </div>
        <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
      </div>

      <!-- Typing indicator -->
      <div v-if="asking" class="message-row assistant">
        <div class="bubble assistant typing">
          <span class="dot" /><span class="dot" /><span class="dot" />
        </div>
      </div>
    </div>

    <!-- Input bar -->
    <div class="input-bar">
      <van-field
        v-model="inputText"
        placeholder="问我关于你家资产的问题..."
        :disabled="asking"
        clearable
        @keyup.enter="onSend"
      />
      <van-button
        type="primary"
        :loading="asking"
        :disabled="!inputText.trim()"
        @click="onSend"
      >发送</van-button>
    </div>

    <!-- Clear history -->
    <div v-if="messages.length" class="clear-row">
      <van-button size="mini" plain @click="onClear">清空记录</van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { sendChatMessage, getChatHistory, clearChatHistory, markChatRead } from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

const messages = ref<Message[]>([])
const inputText = ref('')
const asking = ref(false)
const scrollRef = ref<HTMLElement | null>(null)

const suggestions = [
  '我们家净资产是多少？',
  '哪类资产占比最高？',
  '有哪些闲置资产？',
  '负债总额是多少？',
  '净资产趋势如何？',
]

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

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

  const userMsg: Message = {
    id: Date.now().toString(),
    role: 'user',
    content: q,
    created_at: new Date().toISOString(),
  }
  messages.value.push(userMsg)
  inputText.value = ''
  asking.value = true
  await scrollToBottom()

  try {
    const res = await sendChatMessage(q)
    messages.value.push({
      id: res.data.message_id,
      role: 'assistant',
      content: res.data.answer,
      created_at: new Date().toISOString(),
    })
  } catch {
    messages.value.push({
      id: Date.now().toString(),
      role: 'assistant',
      content: '抱歉，AI 服务暂时不可用，请稍后再试。',
      created_at: new Date().toISOString(),
    })
  } finally {
    asking.value = false
    await scrollToBottom()
  }
}

async function onClear() {
  try {
    await showConfirmDialog({ title: '确认', message: '清空所有对话记录？' })
    await clearChatHistory()
    messages.value = []
  } catch {
    // cancelled
  }
}

onMounted(async () => {
  try {
    const res = await getChatHistory()
    messages.value = res.data
    await markChatRead()
    await scrollToBottom()
  } catch {
    // no history
  }
})
</script>

<style scoped>
.ai-chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-secondary);
}
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
  gap: 16px;
}
.empty-hint {
  font-size: 14px;
  color: var(--text-secondary);
}
.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}
.chip {
  padding: 6px 14px;
  border-radius: 16px;
  background: var(--bg-primary);
  color: var(--van-primary-color);
  font-size: 13px;
  cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--van-primary-color) 30%, transparent);
}
.message-row {
  display: flex;
  flex-direction: column;
}
.message-row.user { align-items: flex-end; }
.message-row.assistant { align-items: flex-start; }
.bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.bubble.user {
  background: var(--van-primary-color);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.bubble.assistant {
  background: var(--bg-primary);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
  display: flex;
  gap: 6px;
  align-items: flex-start;
}
.ai-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--van-primary-color);
  flex-shrink: 0;
  margin-top: 2px;
}
.bubble-text { flex: 1; }
.msg-time {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 3px;
  padding: 0 4px;
}
.typing {
  gap: 4px;
  align-items: center;
  padding: 12px 16px;
}
.dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--text-secondary);
  animation: bounce 1.2s infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}
.input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-top: 1px solid var(--border-color, #f0f0f0);
}
.input-bar .van-field { flex: 1; }
.clear-row {
  display: flex;
  justify-content: center;
  padding: 4px 0 8px;
}
</style>
