<script setup lang="ts">
/**
 * CitationHoverCard component
 *
 * Displays citation details (title, URL, "visit source" link) in a floating card.
 * - Desktop: hover trigger (show on mouseenter, hide on mouseleave with delay)
 * - Mobile: click trigger (toggle on click, close on outside click)
 *
 * Positioned via fixed coordinates relative to the anchor element.
 * Teleported to body to escape stacking contexts.
 */
import { computed, ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

export interface CitationHoverData {
  title: string
  url: string
  index: number
}

const props = defineProps<{
  citation: CitationHoverData | null
  anchorRect: DOMRect | null
  show: boolean
}>()

const emit = defineEmits<{
  hide: []
}>()

const { t } = useI18n()

const cardRef = ref<HTMLElement | null>(null)

const domain = computed(() => {
  if (!props.citation?.url) return ''
  try {
    return new URL(props.citation.url).hostname.replace(/^www\./i, '')
  } catch {
    return props.citation.url
  }
})

const positionStyle = computed(() => {
  if (!props.anchorRect) return { display: 'none' }
  const rect = props.anchorRect
  return {
    position: 'fixed' as const,
    top: `${rect.bottom + 6}px`,
    left: `${rect.left + rect.width / 2}px`,
    transform: 'translateX(-50%)',
    zIndex: 1100,
  }
})

// Close on outside click (mobile)
function onDocumentClick(e: MouseEvent) {
  const target = e.target as Node
  if (cardRef.value && !cardRef.value.contains(target)) {
    emit('hide')
  }
}

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      // Delay to avoid catching the current click event
      setTimeout(() => {
        document.addEventListener('click', onDocumentClick)
      }, 0)
    } else {
      document.removeEventListener('click', onDocumentClick)
    }
  },
)

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="citation-hover-fade">
      <div
        v-if="show && citation"
        ref="cardRef"
        class="citation-hover-card"
        :style="positionStyle"
        @mouseleave="emit('hide')"
      >
        <div class="citation-hover-title">{{ citation.title }}</div>
        <div v-if="domain" class="citation-hover-domain">{{ domain }}</div>
        <a
          :href="citation.url"
          target="_blank"
          rel="noopener noreferrer"
          class="citation-hover-link"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
          {{ t('aiChat.visitSource') }}
        </a>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.citation-hover-card {
  min-width: 200px;
  max-width: 320px;
  padding: 12px;
  background: var(--card-bg, #1e1e2e);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  font-size: 13px;
  pointer-events: auto;
}

.citation-hover-title {
  font-weight: 500;
  color: var(--text-primary, #fff);
  line-height: 1.4;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.citation-hover-domain {
  font-size: 12px;
  color: var(--text-secondary, #999);
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-hover-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--van-primary-color, #6366f1);
  text-decoration: none;
  transition: opacity 0.15s;
}

.citation-hover-link:hover {
  opacity: 0.8;
  text-decoration: underline;
}

.citation-hover-link svg {
  flex-shrink: 0;
}

/* Transition */
.citation-hover-fade-enter-active,
.citation-hover-fade-leave-active {
  transition: opacity 0.15s ease;
}

.citation-hover-fade-enter-from,
.citation-hover-fade-leave-to {
  opacity: 0;
}

/* Light theme */
:global([data-theme='light']) .citation-hover-card {
  background: #fff;
  border-color: rgba(0, 0, 0, 0.1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

@media (max-width: 768px) {
  .citation-hover-card {
    max-width: 280px;
  }
}
</style>
