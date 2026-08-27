<template>
  <van-nav-bar
    :title="title"
    :left-arrow="showBack"
    :fixed="fixed"
    :placeholder="fixed"
    @click-left="onBack"
  >
    <template v-if="$slots.right" #right>
      <slot name="right" />
    </template>
  </van-nav-bar>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = withDefaults(defineProps<{
  title: string
  showBack?: boolean
  fixed?: boolean
  /** Explicit route to navigate back to when browser history is empty (e.g. direct URL access). */
  backTo?: string
}>(), {
  showBack: true,
  fixed: true
})

const emit = defineEmits<{
  back: []
}>()

const router = useRouter()

function onBack() {
  emit('back')
  if (window.history.length > 1) {
    router.back()
  } else if (props.backTo) {
    router.push(props.backTo)
  } else {
    router.push('/')
  }
}
</script>
