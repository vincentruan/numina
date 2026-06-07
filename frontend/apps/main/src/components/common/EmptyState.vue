<template>
  <van-empty
    :image="image"
    :image-size="imageSize"
    :description="description ?? t('common.noData')"
  >
    <template v-if="$slots.image" #image>
      <slot name="image" />
    </template>
    <template v-if="$slots.default" #default>
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
  imageSize?: string | number
}>()
</script>
