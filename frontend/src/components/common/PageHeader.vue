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
}>(), {
  showBack: true,
  fixed: true
})

const router = useRouter()

function onBack() {
  router.back()
}
</script>
