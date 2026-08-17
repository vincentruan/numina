<template>
  <div class="profile-edit-page">
    <van-nav-bar
      :title="t('profileEdit.title')"
      left-arrow
      @click-left="router.back()"
    />

    <div class="content">
      <!-- Avatar section -->
      <div class="avatar-section" @click="showPicker = true">
        <UserAvatar
          :avatar-url="form.avatar_url"
          :avatar-color="form.avatar_color"
          :display-name="form.display_name"
          :size="96"
        />
        <div class="avatar-hint">{{ t('profileEdit.tapToChange') }}</div>
      </div>

      <!-- Display name field -->
      <van-cell-group inset class="form-group">
        <van-field
          v-model="form.display_name"
          :label="t('profileEdit.displayName')"
          :placeholder="t('profileEdit.displayNamePlaceholder')"
          :rules="[{ required: true, message: t('profileEdit.displayNameRequired') }]"
          label-width="6.5em"
          maxlength="100"
          show-word-limit
        />
      </van-cell-group>

      <!-- Save button -->
      <div class="actions">
        <van-button
          type="primary"
          block
          :loading="saving"
          :disabled="!canSave"
          @click="onSave"
        >{{ t('common.save') }}</van-button>
      </div>
    </div>

    <!-- Icon Picker -->
    <IconPicker
      v-model:show="showPicker"
      mode="avatar"
      :current-image-url="form.avatar_url?.startsWith('/') ? form.avatar_url : undefined"
      :current-emoji="form.avatar_url && !form.avatar_url.startsWith('/') ? form.avatar_url : undefined"
      @select-image="onSelectImage"
      @select-emoji="onSelectEmoji"
      @request-gallery="onRequestGallery"
      @request-camera="onRequestCamera"
      @delete="onDeleteAvatar"
    />

    <!-- Logo Cropper (square crop + rotate for avatar images) -->
    <LogoCropper
      v-model:show="showCropper"
      :source="cropperSource"
      @confirm="onCropperConfirm"
    />

    <!-- Hidden file inputs -->
    <input
      ref="galleryInput"
      type="file"
      accept="image/jpeg,image/png,image/webp"
      style="display: none"
      @change="onFileSelected"
    />
    <input
      ref="cameraInput"
      type="file"
      accept="image/jpeg,image/png,image/webp"
      capture="environment"
      style="display: none"
      @change="onFileSelected"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showLoadingToast } from 'vant'
import { useAuthStore } from '@numina/auth'
import UserAvatar from '@/components/common/UserAvatar.vue'
import IconPicker from '@/components/asset/IconPicker.vue'
import LogoCropper from '@/components/asset/LogoCropper.vue'
import { updateProfile } from '@/api/auth'
import http from '@/api'
import type { User } from '@numina/auth'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// Check if this is a child profile edit (parent-managed)
const childId = computed(() => route.params.childId as string | undefined)
const isChildEdit = computed(() => !!childId.value)

// Form state
const form = ref({
  display_name: '',
  avatar_color: '#4F46E5',
  avatar_url: null as string | null,
})

const saving = ref(false)
const showPicker = ref(false)
const showCropper = ref(false)
const cropperSource = ref<File | string | null>(null)
const galleryInput = ref<HTMLInputElement | null>(null)
const cameraInput = ref<HTMLInputElement | null>(null)

// Load current profile
onMounted(async () => {
  if (isChildEdit.value && childId.value) {
    // Load child profile
    try {
      const res = await http.get<User>(`/family/members/${childId.value}`)
      const child = res.data
      form.value.display_name = child.display_name
      form.value.avatar_color = child.avatar_color
      form.value.avatar_url = child.avatar_url ?? null
    } catch {
      showFailToast(t('common.failed'))
    }
  } else {
    // Load adult profile from auth store
    const user = authStore.user
    if (user) {
      form.value.display_name = user.display_name
      form.value.avatar_color = user.avatar_color
      form.value.avatar_url = user.avatar_url ?? null
    }
  }
})

const canSave = computed(() => {
  return form.value.display_name.trim().length > 0
})

async function onSave() {
  if (!canSave.value || saving.value) return

  saving.value = true
  try {
    if (isChildEdit.value && childId.value) {
      // Update child profile
      await http.patch(`/family/children/${childId.value}`, {
        display_name: form.value.display_name,
        avatar_color: form.value.avatar_color,
        avatar_url: form.value.avatar_url,
      })
    } else {
      // Update adult profile
      await updateProfile({
        display_name: form.value.display_name,
        avatar_color: form.value.avatar_color,
        avatar_url: form.value.avatar_url,
      })
      // Refresh auth store with updated user data
      await authStore.fetchMe()
    }
    showSuccessToast(t('common.success'))
    router.back()
  } catch {
    showFailToast(t('common.failed'))
  } finally {
    saving.value = false
  }
}

function onSelectImage(url: string) {
  form.value.avatar_url = url
  showPicker.value = false
}

function onSelectEmoji(emoji: string) {
  form.value.avatar_url = emoji
  showPicker.value = false
}

function onRequestGallery() {
  galleryInput.value?.click()
}

function onRequestCamera() {
  cameraInput.value?.click()
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  // Validate file type
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    showFailToast(t('profileEdit.invalidFileType'))
    return
  }

  // Validate file size (5MB)
  if (file.size > 5 * 1024 * 1024) {
    showFailToast(t('profileEdit.fileTooLarge'))
    return
  }

  // Open cropper for square crop + rotate
  cropperSource.value = file
  showCropper.value = true
  showPicker.value = false

  // Reset input
  input.value = ''
}

async function onCropperConfirm(canvas: HTMLCanvasElement) {
  showCropper.value = false
  showLoadingToast(t('profileEdit.uploading'))

  try {
    // Convert cropped canvas to blob and upload (no watermark for avatars)
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error('Canvas toBlob failed'))),
        'image/jpeg',
        0.92,
      )
    })
    const file = new File([blob], 'avatar.jpg', { type: 'image/jpeg' })

    const formData = new FormData()
    formData.append('file', file)
    const res = await http.post<{ url: string }>('/upload/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    form.value.avatar_url = res.data.url
    showSuccessToast(t('common.success'))
  } catch {
    showFailToast(t('profileEdit.uploadFailed'))
  }
}

function onDeleteAvatar() {
  form.value.avatar_url = null
  showPicker.value = false
}
</script>

<style scoped>
.profile-edit-page {
  min-height: 100vh;
  background: var(--van-background);
}

.content {
  padding: 16px 0;
}

.avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0;
  cursor: pointer;
}

.avatar-hint {
  margin-top: 12px;
  font-size: 13px;
  color: var(--van-text-color-2);
}

.form-group {
  margin-bottom: 16px;
}

.actions {
  padding: 16px;
}
</style>
