<template>
  <van-empty :image="image" :description="description ?? t('common.noData')">
    <template v-if="$slots.default">
      <slot />
    </template>
  </van-empty>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  description?: string
  image?: string
}>()
</script>
