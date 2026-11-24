<script setup lang="ts">
import type { IconifyIcon } from '@iconify/vue'
import { Icon as IconifyIconComp } from '@iconify/vue'
import { computed } from 'vue'

defineOptions({
  name: 'IIcon',
})

const props = defineProps<{
  icon: string | IconifyIcon
  size?: string | number
  color?: string
}>()

/** When a size is given it wins over the 1em default — the CSS rule below
 *  only applies to sized-less icons. */
const rootStyle = computed(() => ({
  ...(props.color ? { color: props.color } : {}),
  ...(props.size != null ? { width: px(props.size), height: px(props.size) } : {}),
}))

function px(v: string | number): string {
  return typeof v === 'number' ? `${v}px` : v
}
</script>

<template>
  <IconifyIconComp
    :icon="props.icon"
    :style="rootStyle"
    class="i-icon"
    aria-hidden="true"
  />
</template>

<style scoped>
/* No `fill` here: lucide and mdi icons carry their own fill/stroke, and
   forcing a fill flattens stroked (lucide) icons into blobs. */
.i-icon {
  width: 1em;
  height: 1em;
  vertical-align: -0.15em;
  overflow: hidden;
}
</style>
