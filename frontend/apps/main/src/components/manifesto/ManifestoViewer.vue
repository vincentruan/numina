<template>
  <div class="manifesto-viewer">
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
      <p>{{ body }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getTemplate } from './templates/templateRegistry'

interface SignatureInfo {
  name: string
  data: string | null
}

interface MemberInfo {
  name: string
  role: string
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
