import { defineStore } from 'pinia'
import { ref } from 'vue'

import { remindersApi, type ReminderResponse, type ReminderSummary } from '@/api/reminders'

export const useRemindersStore = defineStore('reminders', () => {
  const summary = ref<ReminderSummary>({
    large_purchase: 0,
    expiring_soon: 0,
    maturity: 0,
    total: 0,
  })
  const reminders = ref<ReminderResponse[]>([])
  const loading = ref(false)

  async function fetchSummary() {
    summary.value = await remindersApi.getSummary()
  }

  async function fetchReminders() {
    loading.value = true
    try {
      reminders.value = await remindersApi.list()
    } finally {
      loading.value = false
    }
  }

  async function dismiss(id: string) {
    await remindersApi.dismiss(id)
    reminders.value = reminders.value.filter((r) => r.id !== id)
    await fetchSummary()
  }

  return { summary, reminders, loading, fetchSummary, fetchReminders, dismiss }
})
