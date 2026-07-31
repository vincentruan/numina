import { ref, watch, type Ref } from 'vue'

const STORAGE_KEY = 'manifesto-wizard'

export interface WizardState {
  selectedTemplateId: string | null
  title: string
  body: string
  blocks: string[]
  trackableIndices: number[]
  signingDeadline: string | null
}

const defaults: WizardState = {
  selectedTemplateId: null,
  title: '',
  body: '',
  blocks: [''],
  trackableIndices: [],
  signingDeadline: null,
}

function loadFromStorage(): WizardState {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...defaults }
    const parsed = JSON.parse(raw) as Partial<WizardState>
    const blocks = Array.isArray(parsed.blocks) && parsed.blocks.length > 0 ? parsed.blocks : ['']
    return {
      selectedTemplateId: parsed.selectedTemplateId ?? null,
      title: parsed.title ?? '',
      body: parsed.body ?? '',
      blocks,
      trackableIndices: Array.isArray(parsed.trackableIndices) ? parsed.trackableIndices : [],
      signingDeadline: parsed.signingDeadline ?? null,
    }
  } catch {
    return { ...defaults }
  }
}

function saveToStorage(state: WizardState) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // ignore
  }
}

const state = ref<WizardState>(loadFromStorage()) as Ref<WizardState>

watch(state, (val) => {
  saveToStorage(val)
}, { deep: true })

export function useManifestoWizard() {
  function reset() {
    state.value = { ...defaults }
    try {
      sessionStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  }

  return {
    state,
    reset,
    saveToStorage: () => saveToStorage(state.value),
    loadFromStorage: () => {
      state.value = loadFromStorage()
    },
  }
}
