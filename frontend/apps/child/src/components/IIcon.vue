<script setup lang="ts">
import type { IconifyIcon } from '@iconify/vue'
import { Icon as IconifyIconComp } from '@iconify/vue'

defineOptions({
  name: 'IIcon',
})

const props = defineProps<{
  icon: string | IconifyIcon
  size?: string | number
  color?: string
}>()
</script>

<template>
  <IconifyIconComp
    :icon="props.icon"
    :width="props.size"
    :height="props.size"
    :style="props.color ? { color: props.color } : undefined"
    class="i-icon"
    aria-hidden="true"
  />
</template>

<style scoped>
.i-icon {
  width: 1em;
  height: 1em;
  vertical-align: -0.15em;
  fill: currentColor;
  overflow: hidden;
}
</style>