<template>
  <component
    :is="challengeComponent"
    v-if="challengeComponent"
    :config="config"
    @complete="emit('complete')"
    @request-tutor="emit('requestTutor')"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChallengeConfig } from '@/types/learning-challenge'
import { resolveChallengeComponent } from './challenges'

defineOptions({ name: 'ManipulateObserveReflect' })

const props = defineProps<{
  config: ChallengeConfig
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

/** Resolve the interaction component from the config's type tag. */
const challengeComponent = computed(() =>
  resolveChallengeComponent(props.config.type),
)
</script>
