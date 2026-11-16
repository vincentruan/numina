<script setup lang="ts">
/**
 * SmartTutorPage — route page for the Socratic smart tutor session.
 *
 * Receives sessionId, questionId, subject, and ageGroup via route params/query,
 * then renders the SmartTutorPanel.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import SmartTutorPanel from '@/components/learning/smart-tutor/SmartTutorPanel.vue'

defineOptions({ name: 'SmartTutorPage' })

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const sessionId = computed(() => route.params.sessionId as string)
const questionId = computed(() => route.query.questionId as string)
const subject = computed(() => (route.query.subject as string) || 'mathematics')
const ageGroup = computed(() => (route.query.ageGroup as string) || 'mid')

// Validate required params — redirect home if missing
const isValid = computed(() => !!sessionId.value && !!questionId.value)

if (!isValid.value) {
  showToast(t('learning.smart_tutor.error.smart_tutor_start', { status: 400 }))
  router.replace({ name: 'ChildHome' })
}
</script>

<template>
  <div v-if="isValid" class="smart-tutor-page">
    <SmartTutorPanel
      :session-id="sessionId"
      :question-id="questionId"
      :subject="subject"
      :age-group="ageGroup"
    />
  </div>
</template>

<style scoped>
.smart-tutor-page {
  height: calc(100vh - 50px);
  display: flex;
  flex-direction: column;
}
</style>
