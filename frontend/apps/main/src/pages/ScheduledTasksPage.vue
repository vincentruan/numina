<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import ScheduledTasksTab from '@/components/ai/ScheduledTasksTab.vue'

defineOptions({ name: 'ScheduledTasks' })

const { t } = useI18n()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')
</script>

<template>
  <div class="scheduled-tasks-page">
    <PageHeader :title="t('settings.scheduledManage')" />
    <ScheduledTasksTab :is-owner="isOwner" />
  </div>
</template>

<style scoped>
.scheduled-tasks-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}
</style>
