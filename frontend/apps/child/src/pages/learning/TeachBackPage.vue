<script setup lang="ts">
/**
 * TeachBackPage — route page for the teach-back (child teaches AI) session.
 *
 * Receives topicId, subject, and ageGroup via route params/query, then renders
 * the TeachBackPanel. Entry point: mastered pilot topics only (the backend
 * enforces pilot scope + mastery on the stream endpoint).
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import TeachBackPanel from '@/components/learning/smart-tutor/TeachBackPanel.vue'

defineOptions({ name: 'TeachBackPage' })

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const topicId = computed(() => route.params.topicId as string)
const subject = computed(() => (route.query.subject as string) || 'mathematics')
const ageGroup = computed(() => (route.query.ageGroup as string) || 'mid')

const isValid = computed(() => !!topicId.value)

if (!isValid.value) {
  showToast(t('learning.teach_back.error.start', { status: 400 }))
  router.replace({ name: 'ChildHome' })
}
</script>

<template>
  <div v-if="isValid" class="teach-back-page">
    <TeachBackPanel
      :topic-id="topicId"
      :subject="subject"
      :age-group="ageGroup"
    />
  </div>
</template>

<style scoped>
.teach-back-page {
  height: calc(100vh - 50px);
  display: flex;
  flex-direction: column;
}
</style>
