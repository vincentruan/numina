<template>
  <div class="user-avatar" :style="avatarStyle" :aria-label="displayName">
    <!-- Image avatar -->
    <img
      v-if="isImage && !imgError && avatarUrl"
      :src="avatarUrl"
      :alt="displayName || undefined"
      class="avatar-img"
      @error="imgError = true"
    />
    <!-- Emoji avatar -->
    <span v-else-if="isEmoji && avatarUrl" class="avatar-emoji">{{ avatarUrl }}</span>
    <!-- Fallback: first character -->
    <span v-else class="avatar-fallback">{{ fallbackChar }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  avatarUrl: string | null
  avatarColor: string
  displayName: string
  size?: number
}>(), {
  size: 36,
})

const imgError = ref(false)

// Reset imgError when avatarUrl changes
watch(() => props.avatarUrl, () => {
  imgError.value = false
})

// Determine avatar type
const isImage = computed(() => {
  return props.avatarUrl && props.avatarUrl.startsWith('/')
})

const isEmoji = computed(() => {
  return props.avatarUrl && !props.avatarUrl.startsWith('/')
})

const fallbackChar = computed(() => {
  return props.displayName?.charAt(0) || '?'
})

const avatarStyle = computed(() => {
  const size = `${props.size}px`
  // For fallback (no custom avatar), apply avatar_color background
  if (!props.avatarUrl) {
    return {
      width: size,
      height: size,
      backgroundColor: props.avatarColor,
      '--avatar-size': size,
    }
  }
  return {
    width: size,
    height: size,
    '--avatar-size': size,
  }
})
</script>

<style scoped>
.user-avatar {
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
  user-select: none;
  /* Fallback text styling */
  color: #fff;
  font-weight: 600;
  font-size: calc(var(--avatar-size, 36px) * 0.7);
  line-height: 1;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.avatar-emoji {
  font-size: 60%;
  line-height: 1;
}

.avatar-fallback {
  line-height: 1;
}
</style>
