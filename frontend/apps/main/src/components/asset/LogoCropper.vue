<template>
  <van-popup
    :show="show"
    position="bottom"
    :style="{ height: '100%', width: '100%' }"
    lock-scroll
    @close="onCancel"
  >
    <div class="logo-cropper">
      <!-- Header -->
      <div class="cropper-header">
        <van-button size="small" plain @click="onCancel">
          {{ t('assetForm.cropCancel') }}
        </van-button>
        <span class="cropper-title">{{ t('assetForm.cropTitle') }}</span>
        <van-button size="small" type="primary" @click="onConfirm">
          {{ t('assetForm.cropConfirm') }}
        </van-button>
      </div>

      <!-- Image container for cropperjs -->
      <div class="cropper-body">
        <img
          ref="imageRef"
          :src="imageSrc"
          :crossorigin="crossOrigin"
          alt="crop"
          class="cropper-image"
        />
      </div>

      <!-- Toolbar -->
      <div class="cropper-toolbar">
        <van-button icon="replay" size="small" circle @click="onRotateLeft" />
        <van-button icon="replay" size="small" circle class="rotate-right" @click="onRotateRight" />
        <van-button size="small" plain @click="onReset">
          {{ t('assetForm.cropReset') }}
        </van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'

const { t } = useI18n()

const props = defineProps<{
  show: boolean
  source: File | string | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'confirm': [canvas: HTMLCanvasElement]
}>()

const imageRef = ref<HTMLImageElement | null>(null)
const objectUrl = ref<string | null>(null)
let cropper: Cropper | null = null

// Resolve image source to URL
const imageSrc = computed(() => {
  if (!props.source) return ''
  if (typeof props.source === 'string') return props.source
  // File object — use cached object URL if already created
  return objectUrl.value || ''
})

// Side effect: create object URL when source is a File (kept out of computed
// to satisfy vue/no-side-effects-in-computed-properties).
watch(
  () => props.source,
  (src) => {
    if (src && typeof src !== 'string') {
      objectUrl.value = URL.createObjectURL(src)
    }
  },
  { immediate: true },
)

// CORS handling for remote images
const crossOrigin = computed(() => {
  return typeof props.source === 'string' ? 'anonymous' : undefined
})

// Initialize / destroy cropper based on show state
watch(
  () => props.show,
  (visible) => {
    if (visible) {
      // Wait for next tick so the img element is rendered
      setTimeout(initCropper, 100)
    } else {
      destroyCropper()
    }
  },
)

// Also re-init when source changes while popup is open
watch(
  () => props.source,
  () => {
    if (props.show && props.source) {
      // Reset objectUrl when source changes
      revokeObjectUrl()
      objectUrl.value = null
      setTimeout(initCropper, 100)
    }
  },
)

function initCropper() {
  if (!imageRef.value) return
  destroyCropper()

  cropper = new Cropper(imageRef.value, {
    aspectRatio: 1,
    viewMode: 1,
    dragMode: 'move',
    autoCropArea: 0.8,
    responsive: true,
    restore: false,
    guides: true,
    center: true,
    highlight: false,
    cropBoxMovable: true,
    cropBoxResizable: true,
    toggleDragModeOnDblclick: false,
  })
}

function destroyCropper() {
  if (cropper) {
    cropper.destroy()
    cropper = null
  }
}

function revokeObjectUrl() {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value)
    objectUrl.value = null
  }
}

function onRotateLeft() {
  cropper?.rotate(-90)
}

function onRotateRight() {
  cropper?.rotate(90)
}

function onReset() {
  cropper?.reset()
}

function onConfirm() {
  if (!cropper) return
  const canvas = cropper.getCroppedCanvas({
    maxWidth: 2048,
    maxHeight: 2048,
    imageSmoothingEnabled: true,
    imageSmoothingQuality: 'high',
  })
  if (canvas) {
    emit('confirm', canvas)
  }
}

function onCancel() {
  emit('update:show', false)
}

// Cleanup on unmount
onBeforeUnmount(() => {
  destroyCropper()
  revokeObjectUrl()
})
</script>

<style scoped>
.logo-cropper {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--van-background, #f7f8fa);
}

.cropper-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--van-nav-bar-background, #fff);
  border-bottom: 1px solid var(--van-border-color, #ebedf0);
}

.cropper-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--van-text-color, #323233);
}

.cropper-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.cropper-image {
  max-width: 100%;
  max-height: 100%;
  display: block;
}

.cropper-toolbar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--van-nav-bar-background, #fff);
  border-top: 1px solid var(--van-border-color, #ebedf0);
}

.rotate-right {
  transform: scaleX(-1);
}
</style>
