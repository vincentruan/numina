<script setup lang="ts">
/**
 * SmartTutorPage — route page for the Socratic smart tutor session.
 *
 * Receives sessionId, questionId, subject, and ageGroup via route params/query,
 * then renders the SmartTutorPanel.
 */
import { useRoute } from 'vue-router'
import SmartTutorPanel from '@/components/learning/smart-tutor/SmartTutorPanel.vue'

defineOptions({ name: 'SmartTutorPage' })

const route = useRoute()
const sessionId = route.params.sessionId as string
const questionId = route.query.questionId as string
const subject = (route.query.subject as string) || 'math'
const ageGroup = (route.query.ageGroup as string) || 'mid'
</script>

<template>
  <div class="smart-tutor-page">
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
