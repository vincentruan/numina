import { ref } from 'vue'

export type ViewMode = 'card' | 'list' | 'category' | 'status'

export function useViewMode() {
  const viewMode = ref<ViewMode>('card')
  const savedMode = localStorage.getItem('viewMode')
  if (savedMode && ['card', 'list', 'category', 'status'].includes(savedMode)) {
    viewMode.value = savedMode as ViewMode
  }

  function setViewMode(mode: ViewMode) {
    viewMode.value = mode
    localStorage.setItem('viewMode', mode)
  }

  return { viewMode, setViewMode }
}
