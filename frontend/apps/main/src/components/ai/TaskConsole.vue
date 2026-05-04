<template>
  <div v-if="status !== 'idle'" class="task-console">
    <!-- 标题栏 -->
    <div class="console-header" @click="toggleOpen">
      <span class="console-status-icon">{{ statusIcon }}</span>
      <span class="console-title">{{ title }}</span>
      <span class="console-elapsed">{{ formattedElapsed }}</span>
      <van-icon :name="isOpen ? 'arrow-up' : 'arrow-down'" class="console-toggle" />
    </div>

    <!-- 内容区（折叠） -->
    <div v-show="isOpen" class="console-body">
      <div ref="scrollRef" class="console-chunks">
        <div v-for="(chunk, i) in chunks" :key="i" class="console-chunk">{{ chunk }}</div>
        <div v-if="status === 'running'" class="console-cursor">▋</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  status: 'idle' | 'running' | 'completed' | 'failed' | 'timeout'
  chunks: string[]
  elapsedSeconds: number
  modelValue?: boolean // isOpen
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()
const scrollRef = ref<HTMLElement | null>(null)
const isOpen = ref(props.status === 'running')

function toggleOpen() {
  isOpen.value = !isOpen.value
  emit('update:modelValue', isOpen.value)
}

// 任务完成时自动折叠
watch(
  () => props.status,
  (val) => {
    if (val === 'completed') isOpen.value = false
    if (val === 'running') isOpen.value = true
  },
)

// running 时自动滚动到底部
watch(
  () => props.chunks.length,
  async () => {
    if (props.status === 'running') {
      await nextTick()
      scrollRef.value?.scrollTo({ top: scrollRef.value.scrollHeight, behavior: 'smooth' })
    }
  },
)

const statusIcon = computed(() => {
  const icons: Record<string, string> = {
    running: '⏳',
    completed: '✅',
    failed: '❌',
    timeout: '⏰',
  }
  return icons[props.status] ?? ''
})

const title = computed(() => t(`aiTask.status.${props.status}`))

const formattedElapsed = computed(() => {
  const s = props.elapsedSeconds
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
})
</script>

<style scoped>
.task-console {
  border: 1px solid var(--van-border-color);
  border-radius: 8px;
  margin: 12px 0;
  overflow: hidden;
  background: var(--van-background-2);
}

.console-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
}

.console-status-icon {
  font-size: 16px;
}

.console-title {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: var(--van-text-color);
}

.console-elapsed {
  font-size: 13px;
  color: var(--van-text-color-2);
  font-variant-numeric: tabular-nums;
}

.console-toggle {
  color: var(--van-text-color-3);
}

.console-body {
  border-top: 1px solid var(--van-border-color);
}

.console-chunks {
  max-height: 240px;
  overflow-y: auto;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--van-text-color);
}

.console-chunk {
  margin-bottom: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}

.console-cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: var(--van-primary-color);
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
</style>
