<template>
  <div v-if="loading" class="challenge-loading" role="status" aria-busy="true" aria-label="Loading activity" />
  <component
    :is="challengeComponent"
    v-else-if="challengeComponent"
    :config="config"
    @complete="emit('complete')"
    @request-tutor="emit('requestTutor')"
  />
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import type { Component } from 'vue'
import type { ChallengeConfig } from '@/types/learning-challenge'
import { loadChallengeComponent, isPhysics3D } from './challenges/router'
import { resolveChallengeComponent } from './challenges'
import { useReducedMotion } from '@/composables/useReducedMotion'

defineOptions({ name: 'ManipulateObserveReflect' })

const props = defineProps<{
  config: ChallengeConfig
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const challengeComponent = ref<Component | null>(null)
const loading = ref(false)
const reducedMotion = useReducedMotion()

// Cache loaded components to avoid re-importing on every re-render
const componentCache = new Map<string, Component>()

let loadToken = 0
let pendingTimeout: ReturnType<typeof setTimeout> | undefined

async function loadComponent() {
  const type = props.config.type
  const cached = componentCache.get(type)
  if (cached) {
    challengeComponent.value = cached
    loading.value = false
    return
  }

  const token = ++loadToken
  loading.value = true

  // 5-second timeout: fall back to 2D silently
  pendingTimeout = setTimeout(() => {
    if (token === loadToken && loading.value) {
      ++loadToken // poison any late-arriving 3D response
      loading.value = false
      challengeComponent.value = resolveChallengeComponent(type) ?? null
    }
  }, 5000)

  try {
    const comp = await loadChallengeComponent(type)
    clearTimeout(pendingTimeout)
    if (token !== loadToken) return // stale — a newer load superseded this one
    challengeComponent.value = comp
    if (comp) componentCache.set(type, comp)
  } catch {
    // Unexpected error — fall back to 2D gracefully (R5)
    clearTimeout(pendingTimeout)
    if (token === loadToken) {
      challengeComponent.value = resolveChallengeComponent(type) ?? null
      loading.value = false
    }
  } finally {
    clearTimeout(pendingTimeout)
    if (token === loadToken) loading.value = false
  }
}

// Initial load on mount (not immediate — avoids firing before DOM is ready)
onMounted(() => { loadComponent() })

// Reload when config type changes
watch(() => props.config.type, () => { loadComponent() })

// Watch for prefers-reduced-motion toggle
watch(reducedMotion, () => {
  if (isPhysics3D(props.config.type)) {
    componentCache.delete(props.config.type)
    loadComponent()
  }
})

// Cleanup pending async operations on unmount (R4 lifecycle)
onBeforeUnmount(() => {
  ++loadToken // invalidate any pending async loads
  if (pendingTimeout) clearTimeout(pendingTimeout)
})
</script>
