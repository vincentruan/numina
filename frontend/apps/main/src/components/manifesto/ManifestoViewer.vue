<template>
  <div class="manifesto-viewer">
    <component
      :is="resolvedComponent"
      :title="title"
      :body="body"
      :signatures="signatures"
      :members="members"
    />
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
</style>
