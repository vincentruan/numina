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
          maxlength="50"
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

    <!-- Icon Picker (3D icons + emoji only, no gallery/camera for child) -->
    <ChildAvatarPicker
      v-model:show="showPicker"
      :current-avatar-url="form.avatar_url?.startsWith('/') ? form.avatar_url : undefined"
      @select-image="onSelectImage"
      @select-emoji="onSelectEmoji"
      @delete="onDeleteAvatar"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { useChildAuthStore } from '@numina/auth'
import UserAvatar from '@/components/common/UserAvatar.vue'
import ChildAvatarPicker from '@/components/common/ChildAvatarPicker.vue'
import http from '@/api'

const { t } = useI18n()
const router = useRouter()
const childAuthStore = useChildAuthStore()

// Form state
const form = ref({
  display_name: '',
  avatar_color: '#4F46E5',
  avatar_url: null as string | null,
})

const saving = ref(false)
const showPicker = ref(false)

// Load current profile from child auth store
onMounted(() => {
  const user = childAuthStore.childUser
  if (user) {
    form.value.display_name = user.display_name
    form.value.avatar_color = user.avatar_color
    form.value.avatar_url = user.avatar_url ?? null
  }
})

const canSave = computed(() => {
  return form.value.display_name.trim().length > 0
})

async function onSave() {
  if (!canSave.value || saving.value) return

  saving.value = true
  try {
    // Update child's own profile via PUT /auth/me (child session)
    const res = await http.put('/auth/me', {
      display_name: form.value.display_name,
      avatar_color: form.value.avatar_color,
      avatar_url: form.value.avatar_url,
    })
    // Update childUser in store
    childAuthStore.childUser = res.data
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

function onDeleteAvatar() {
  form.value.avatar_url = null
  showPicker.value = false
}
</script>

<style scoped>
.profile-edit-page {
  min-height: 100vh;
  background: var(--color-canvas);
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
  color: var(--color-muted);
}

.form-group {
  margin-bottom: 16px;
}

.actions {
  padding: 16px;
}
</style>
