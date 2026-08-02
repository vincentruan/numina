<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  name: string
  size?: string | number
  color?: string
  className?: string
}
const props = withDefaults(defineProps<Props>(), {
  size: undefined,
  color: undefined,
  className: '',
})

const iconName = computed(() => `#icon-${props.name}`)
const svgClass = computed(() => {
  if (props.className) {
    return `svg-icon ${props.className}`
  }
  return 'svg-icon'
})
const sizeStyle = computed(() => {
  if (props.size === undefined) return {}
  const sizeValue = typeof props.size === 'number' ? `${props.size}px` : props.size
  return {
    width: sizeValue,
    height: sizeValue,
  }
})
const colorStyle = computed(() => {
  if (props.color === undefined) return {}
  return { color: props.color }
})
</script>

<template>
  <svg
    :class="svgClass"
    :style="{ ...sizeStyle, ...colorStyle }"
    aria-hidden="true"
    v-bind="$attrs"
  >
    <use :xlink:href="iconName" />
  </svg>
</template>

<style scoped>
.svg-icon {
  width: 1em;
  height: 1em;
  overflow: hidden;
  /* When size is explicitly set, align to middle for proper line alignment */
  vertical-align: middle;
}
</style>