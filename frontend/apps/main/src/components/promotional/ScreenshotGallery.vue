<template>
  <div class="screenshot-gallery">
    <van-swipe
      :autoplay="autoplay ? interval : 0"
      :indicator-color="indicatorColor"
      class="swipe-container"
    >
      <van-swipe-item v-for="(src, index) in screenshots" :key="index">
        <img
          :src="src"
          :alt="`功能截图 ${index + 1}`"
          loading="lazy"
          class="screenshot-image"
          @error="onImageError($event, index)"
        />
      </van-swipe-item>
    </van-swipe>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  screenshots: string[]
  autoplay?: boolean
  interval?: number
}

const props = withDefaults(defineProps<Props>(), {
  screenshots: () => [],
  autoplay: true,
  interval: 3000
})

const indicatorColor = '#17171c'

// Track failed images to show placeholder
const failedImages = ref<Set<number>>(new Set())

function onImageError(event: Event, index: number) {
  const img = event.target as HTMLImageElement
  img.style.background = '#f5f5f7'
  img.alt = '截图加载失败'
  failedImages.value.add(index)
}
</script>

<style scoped>
.screenshot-gallery {
  width: 100%;
}

.swipe-container {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
}

.screenshot-image {
  width: 100%;
  height: auto;
  max-height: 400px;
  object-fit: cover;
  background: linear-gradient(135deg, #f5f5f7 0%, #e5e5ea 100%);
}

/* Accessibility: reduced motion */
@media (prefers-reduced-motion: reduce) {
  .swipe-container :deep(.van-swipe__track) {
    transition: none !important;
  }
}
</style>