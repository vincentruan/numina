import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useBabyStore = defineStore('baby', () => {
  const selectedChildId = ref<string | null>(null)
  const selectedChildName = ref<string | null>(null)
  const activePathId = ref<string | null>(null)

  function selectChild(id: string | null, name: string | null = null) {
    selectedChildId.value = id
    selectedChildName.value = name
  }

  function setActivePath(pathId: string | null) {
    activePathId.value = pathId
  }

  return { selectedChildId, selectedChildName, activePathId, selectChild, setActivePath }
})
