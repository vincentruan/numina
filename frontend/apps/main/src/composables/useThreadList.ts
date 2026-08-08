import { ref, computed, watch, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { searchThreads, deleteThread, updateThread, getThreadState } from '@/api/ai-chat'
import { parseApiDate } from '@/utils/format'
import type { ThreadSession, DateGroup, DateGroupLabel } from '@/types/ai-chat/session'

const PAGE_SIZE = 20

/** Extract plain text from a serialized LangChain message's content. */
function extractMessageText(message: unknown): string {
  if (!message || typeof message !== 'object') return ''
  const m = message as Record<string, unknown>
  const content = m.content
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    return content
      .map((block) => {
        if (!block || typeof block !== 'object') return ''
        const b = block as Record<string, unknown>
        if (typeof b.text === 'string') return b.text
        return ''
      })
      .join('')
  }
  return ''
}

/** Trigger a browser download for generated export content. */
function downloadFile(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function useThreadList(sourceFilter?: Ref<string | undefined>) {
  const { t } = useI18n()
  const sessions = ref<ThreadSession[]>([])
  const isLoading = ref(false)
  const hasMore = ref(true)
  let offset = 0
  // AbortController to cancel in-flight searchThreads on rapid filter change.
  let currentAbort: AbortController | null = null

  /** Distinct source values observed in loaded sessions (for filter UI). */
  const availableSources = computed<string[]>(() => {
    const seen = new Set<string>()
    for (const s of sessions.value) {
      const src = s.source || 'chat'
      if (!seen.has(src)) seen.add(src)
    }
    return [...seen].sort()
  })

  function getDateLabel(date: Date): DateGroupLabel {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const yesterday = new Date(today.getTime() - 86400000)

    if (date >= today) return 'today'
    if (date >= yesterday) return 'yesterday'
    return 'earlier'
  }

  const dateGroups = computed<DateGroup[]>(() => {
    const pinned = sessions.value.filter(s => s.is_pinned)
    const unpinned = sessions.value.filter(s => !s.is_pinned)

    const groups: DateGroup[] = []
    if (pinned.length > 0) {
      groups.push({ label: 'pinned', displayName: t('aiChat.groupPinned'), sessions: pinned })
    }

    const today: ThreadSession[] = []
    const yesterday: ThreadSession[] = []
    const earlier: ThreadSession[] = []

    for (const s of unpinned) {
      const label = getDateLabel(parseApiDate(s.updated_at))
      if (label === 'today') today.push(s)
      else if (label === 'yesterday') yesterday.push(s)
      else earlier.push(s)
    }

    if (today.length > 0) groups.push({ label: 'today', displayName: t('aiChat.groupToday'), sessions: today })
    if (yesterday.length > 0) groups.push({ label: 'yesterday', displayName: t('aiChat.groupYesterday'), sessions: yesterday })
    if (earlier.length > 0) groups.push({ label: 'earlier', displayName: t('aiChat.groupMonth'), sessions: earlier })

    return groups
  })

  async function loadMore() {
    if (isLoading.value || !hasMore.value) return
    isLoading.value = true
    // Create a fresh AbortController for this page load so it can be
    // cancelled if the filter changes before the response arrives.
    currentAbort = new AbortController()
    try {
      const res = await searchThreads(
        { limit: PAGE_SIZE, offset, source: sourceFilter?.value },
        currentAbort.signal,
      )
      sessions.value = [...sessions.value, ...res.items]
      offset += res.items.length
      hasMore.value = offset < res.total
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      throw err
    } finally {
      currentAbort = null
      isLoading.value = false
    }
  }

  async function refresh() {
    // Cancel any in-flight request to prevent stale data from appending
    // to the new filter's result set.
    currentAbort?.abort()
    sessions.value = []
    offset = 0
    hasMore.value = true
    await loadMore()
  }

  // When the source filter changes, reset and reload.
  if (sourceFilter) {
    watch(sourceFilter, () => {
      refresh()
    })
  }

  async function deleteSession(id: string) {
    await deleteThread(id)
    sessions.value = sessions.value.filter(s => s.thread_id !== id)
  }

  async function renameSession(id: string, title: string) {
    await updateThread(id, { title })
    const idx = sessions.value.findIndex(s => s.thread_id === id)
    if (idx !== -1) {
      sessions.value[idx] = { ...sessions.value[idx], title }
    }
  }

  async function togglePin(id: string) {
    const session = sessions.value.find(s => s.thread_id === id)
    if (!session) return
    const newPinned = !session.is_pinned
    await updateThread(id, { is_pinned: newPinned })
    const idx = sessions.value.findIndex(s => s.thread_id === id)
    if (idx !== -1) {
      sessions.value[idx] = { ...sessions.value[idx], is_pinned: newPinned }
    }
  }

  /** Export a thread's messages as markdown or json (DeerFlow parity). */
  async function exportSession(id: string, format: 'markdown' | 'json'): Promise<void> {
    const state = await getThreadState(id)
    const messages = (state.values?.messages ?? []) as unknown[]
    const session = sessions.value.find(s => s.thread_id === id)
    const title = state.values?.title || session?.title || t('aiChat.untitledSession')
    const safeTitle = (title).replace(/[^\w一-龥-]/g, '_').slice(0, 40) || 'thread'

    if (format === 'json') {
      const payload = {
        thread_id: id,
        title,
        original_title: session?.original_title,
        created_at: session?.created_at,
        updated_at: session?.updated_at,
        messages,
      }
      downloadFile(`${safeTitle}.json`, JSON.stringify(payload, null, 2), 'application/json')
      return
    }

    const lines: string[] = [`# ${title}`, '']
    for (const msg of messages) {
      const m = msg as Record<string, unknown>
      const type = m.type as string
      const text = extractMessageText(msg)
      if (!text) continue
      if (type === 'human') {
        lines.push(`## ${t('aiChat.exportRoleUser')}`, '', text, '')
      } else if (type === 'ai') {
        lines.push(`## ${t('aiChat.exportRoleAssistant')}`, '', text, '')
      }
    }
    downloadFile(`${safeTitle}.md`, lines.join('\n'), 'text/markdown')
  }

  /** Copy a shareable link to the thread (same-family access). */
  async function shareSession(id: string): Promise<void> {
    const url = `${window.location.origin}/ai/chat?thread_id=${encodeURIComponent(id)}`
    await navigator.clipboard.writeText(url)
  }

  return {
    sessions, isLoading, hasMore, dateGroups, availableSources,
    loadMore, refresh, deleteSession, renameSession, togglePin,
    exportSession, shareSession,
  }
}
