<template>
  <div ref="containerRef" class="manifesto-viewer">
    <component
      v-if="resolvedComponent"
      :is="resolvedComponent"
      :title="title"
      :body="body"
      :signatures="signatures"
      :members="members"
    />
    <div v-else class="manifesto-viewer-fallback">
      <h2>{{ title }}</h2>
      <p
        v-for="(paragraph, index) in fallbackParagraphs"
        :key="index"
        data-reveal
        :style="{ '--reveal-index': index }"
      >{{ paragraph }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { getTemplate } from './templates/templateRegistry'
import { useScrollReveal } from '@/composables/useScrollReveal'

interface SignatureInfo {
  name: string
  data: string | null | undefined
}

interface MemberInfo {
  name: string
  role: string
  signingStatus?: 'signed' | 'confirmed' | 'pending_sign' | 'pending_confirm' | 'rejected' | 'expired'
  signedDate?: string
}

const props = defineProps<{
  templateId: string
  title: string
  body: string
  signatures: SignatureInfo[]
  members: MemberInfo[]
}>()

const resolvedComponent = computed(() => {
  const tmpl = getTemplate(props.templateId)
  return tmpl?.component ?? null
})

const containerRef = ref<HTMLElement | null>(null)
useScrollReveal(containerRef)

const fallbackParagraphs = computed(() =>
  props.body.split('\n\n').filter(p => p.trim()),
)
</script>

<style scoped>
.manifesto-viewer {
  width: 100%;
}
.manifesto-viewer-fallback {
  padding: 16px;
}
.manifesto-viewer-fallback h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary, #0a0a0a);
}
.manifesto-viewer-fallback p {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary, #616161);
  white-space: pre-wrap;
  margin: 0;
}
</style>

<!-- Shared scroll reveal styles for all template paragraphs (unscoped) -->
<style>
.manifesto-viewer [data-reveal] {
  opacity: 0;
  transform: translateY(12px);
  transition: opacity 0.35s ease-out, transform 0.35s ease-out;
  transition-delay: calc(min(var(--reveal-index, 0), 5) * 80ms);
}
.manifesto-viewer [data-reveal].revealed {
  opacity: 1;
  transform: translateY(0);
}
@media (prefers-reduced-motion: reduce) {
  .manifesto-viewer [data-reveal] {
    opacity: 1 !important;
    transform: none !important;
    transition: none !important;
  }
}
</style>
