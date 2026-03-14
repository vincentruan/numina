<template>
  <van-empty :image="image" :description="description">
    <template v-if="$slots.default">
      <slot />
    </template>
  </van-empty>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  description?: string
  image?: string
}>(), {
  description: '暂无数据',
  image: 'default'
})
</script>
