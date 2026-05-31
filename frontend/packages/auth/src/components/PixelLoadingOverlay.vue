<template>
  <PixelLoading
    :visible="isLoading"
    :dismissing="isDismissing"
    :aria-label="ariaLabel"
  />
</template>

<script setup lang="ts">
import { useLoadingOverlay } from '../composables/loading'
import PixelLoading from './PixelLoading.vue'

withDefaults(defineProps<{
  ariaLabel?: string
}>(), {
  ariaLabel: 'Loading',
})

const { isLoading, isDismissing } = useLoadingOverlay()
</script>
