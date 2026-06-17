<template>
  <div class="create-page">
    <!-- Nav bar -->
    <div class="nav-bar">
      <button class="nav-back" :aria-label="t('common.back')" @click="router.replace('/wishes')">
        <van-icon name="arrow-left" size="20" />
      </button>
      <span class="nav-title">{{ t('wishes.createPageTitle') }}</span>
      <span class="nav-spacer" />
    </div>

    <div class="form-body">
      <!-- Wish name -->
      <div class="field-group">
        <label class="field-label">{{ t('wishes.wishNameLabel') }}<span class="required">*</span></label>
        <van-field
          v-model="form.name"
          :placeholder="t('wishes.wishNamePlaceholder')"
          maxlength="50"
          show-word-limit
          class="clay-field"
        />
      </div>

      <!-- Emoji -->
      <div class="field-group">
        <label class="field-label">{{ t('wishes.emojiLabel') }}</label>
        <div class="emoji-row">
          <van-field
            v-model="form.emoji"
            :placeholder="t('wishes.emojiPlaceholder')"
            maxlength="4"
            class="clay-field emoji-field"
          />
          <button class="emoji-picker-btn" type="button" @click="showEmojiPicker = true">
            {{ form.emoji || '😊' }}
          </button>
        </div>
      </div>

      <!-- Description -->
      <div class="field-group">
        <label class="field-label">{{ t('wishes.descLabel') }}</label>
        <van-field
          v-model="form.description"
          type="textarea"
          :placeholder="t('wishes.descPlaceholder')"
          maxlength="200"
          show-word-limit
          :rows="3"
          autosize
          class="clay-field"
        />
      </div>

      <!-- Priority -->
      <div class="field-group">
        <label class="field-label">{{ t('wishes.priorityLabel') }}</label>
        <div class="priority-chips">
          <button
            v-for="p in priorities"
            :key="p.value"
            type="button"
            class="priority-chip"
            :class="{ active: form.priority === p.value }"
            @click="form.priority = p.value"
          >{{ p.label }}</button>
        </div>
      </div>

      <!-- Submit -->
      <van-button
        block
        type="primary"
        :loading="creating"
        :disabled="!form.name.trim()"
        class="btn-submit"
        @click="submitWish"
      >{{ t('wishes.submitBtn') }}</van-button>
    </div>

    <!-- Emoji picker bottom sheet -->
    <van-popup v-model:show="showEmojiPicker" position="bottom" round>
      <div class="emoji-sheet">
        <div class="emoji-sheet-header">
          <span class="emoji-sheet-title">{{ t('wishes.emojiPickerTitle') }}</span>
          <button class="emoji-sheet-close" @click="showEmojiPicker = false">
            <van-icon name="cross" size="18" />
          </button>
        </div>
        <div class="emoji-grid">
          <button
            v-for="e in EMOJI_LIST"
            :key="e"
            type="button"
            class="emoji-grid-item"
            :class="{ selected: form.emoji === e }"
            @click="pickEmoji(e)"
          >{{ e }}</button>
        </div>
      </div>
    </van-popup>

    <!-- Post-submit dialog -->
    <van-dialog
      v-model:show="showSuccessDialog"
      :title="t('wishes.submitSuccess')"
      :show-cancel-button="true"
      :confirm-button-text="t('wishes.continueCreate')"
      :cancel-button-text="t('wishes.backToList')"
      confirm-button-color="var(--color-primary)"
      cancel-button-color="var(--color-muted)"
      @confirm="resetAndContinue"
      @cancel="goBackToList"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast, showFailToast } from 'vant'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usePageLoading } from '@/composables/usePageLoading'
import { createChildWish } from '@/api/childWishes'

const { t } = useI18n()
const router = useRouter()
const { complete } = usePageLoading()

// Complete page loading immediately since this is a form page with no async data loading
onMounted(() => {
  complete()
})

const EMOJI_LIST = [
  '🎮', '🚲', '📚', '🎨', '🎸', '⚽', '🏀', '🎯',
  '🌈', '🦄', '🐶', '🐱', '🐼', '🦊', '🐸', '🦋',
  '🍕', '🍦', '🎂', '🍭', '🍩', '🍫', '🥤', '🍓',
  '✈️', '🚀', '🏖️', '⛺', '🎡', '🎠', '🎪', '🎭',
  '💎', '👑', '🏆', '🎁', '🌟', '⭐', '💫', '🌙',
  '🎀', '🪄', '🔮', '🎲', '🧩', '🪀', '🎈', '🎉',
]

const form = ref({
  name: '',
  emoji: '',
  description: '',
  priority: 'medium' as 'high' | 'medium' | 'low',
})

const creating = ref(false)
const showEmojiPicker = ref(false)
const showSuccessDialog = ref(false)

const priorities = computed(() => [
  { value: 'high' as const, label: t('wishes.priorityHigh') },
  { value: 'medium' as const, label: t('wishes.priorityMedium') },
  { value: 'low' as const, label: t('wishes.priorityLow') },
])

function pickEmoji(e: string) {
  form.value.emoji = e
  showEmojiPicker.value = false
}

async function submitWish() {
  if (!form.value.name.trim()) return
  creating.value = true
  try {
    await createChildWish({
      name: form.value.name.trim(),
      emoji: form.value.emoji || undefined,
      description: form.value.description || undefined,
      priority: form.value.priority,
    })
    showSuccessDialog.value = true
  } catch {
    showFailToast(t('toast.submitFailed'))
  } finally {
    creating.value = false
  }
}

function resetAndContinue() {
  form.value = { name: '', emoji: '', description: '', priority: 'medium' }
  showSuccessDialog.value = false
}

function goBackToList() {
  router.replace('/wishes')
}
</script>

<style scoped>
/* ── Page shell ── */
.create-page {
  background: var(--color-canvas);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Nav bar ── */
.nav-bar {
  display: flex;
  align-items: center;
  height: 56px;
  padding: 0 var(--space-md);
  background: var(--color-canvas);
  border-bottom: 1px solid var(--color-hairline);
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-back {
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  color: var(--color-ink);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  cursor: pointer;
  flex-shrink: 0;
}
.nav-back:active { background: var(--color-surface-soft); }
.nav-title {
  flex: 1;
  text-align: center;
  font-family: Inter, sans-serif;
  font-size: 17px;
  font-weight: 600;
  color: var(--color-ink);
  letter-spacing: -0.3px;
}
.nav-spacer { width: 40px; flex-shrink: 0; }

/* ── Form body ── */
.form-body {
  flex: 1;
  padding: var(--space-lg) var(--space-md) 48px;
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

/* ── Field groups ── */
.field-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.field-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-body-strong);
  padding-left: 2px;
}
.required {
  color: var(--color-brand-coral);
  margin-left: 2px;
}

/* ── Clay field override — ensures dark-mode legibility ── */
.clay-field {
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline);
  overflow: hidden;
}
/* Force Vant field internals to use design-system tokens */
.clay-field :deep(.van-field__control) {
  color: var(--color-ink) !important;
  background: transparent !important;
  font-family: Inter, sans-serif;
  font-size: 15px;
}
.clay-field :deep(.van-field__label) {
  color: var(--color-body) !important;
}
.clay-field :deep(.van-cell) {
  background: transparent !important;
}
.clay-field :deep(.van-field__word-limit) {
  color: var(--color-muted-soft) !important;
}

/* ── Emoji row ── */
.emoji-row {
  display: flex;
  gap: var(--space-xs);
  align-items: stretch;
}
.emoji-field { flex: 1; }
.emoji-picker-btn {
  width: 52px;
  height: 52px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  font-size: 26px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}
.emoji-picker-btn:active { background: var(--color-surface-card); }

/* ── Priority chips ── */
.priority-chips {
  display: flex;
  gap: var(--space-xs);
}
.priority-chip {
  flex: 1;
  height: 44px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-pill);
  background: var(--color-surface-soft);
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-body);
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.priority-chip.active {
  background: var(--color-primary);
  color: var(--color-on-primary);
  border-color: var(--color-primary);
  font-weight: 600;
}

/* ── Submit button ── */
.btn-submit {
  border-radius: var(--radius-md) !important;
  height: 52px !important;
  font-size: 16px !important;
  font-weight: 600 !important;
  background: var(--color-primary) !important;
  border: none !important;
  color: var(--color-on-primary) !important;
  margin-top: var(--space-xs);
}
.btn-submit:disabled { opacity: 0.4; }

/* ── Emoji picker sheet ── */
.emoji-sheet {
  padding: var(--space-lg) var(--space-md) 40px;
}
.emoji-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}
.emoji-sheet-title {
  font-family: Inter, sans-serif;
  font-size: 17px;
  font-weight: 600;
  color: var(--color-ink);
}
.emoji-sheet-close {
  width: 36px;
  height: 36px;
  border: none;
  background: var(--color-surface-soft);
  border-radius: var(--radius-pill);
  color: var(--color-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.emoji-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: var(--space-xs);
}
.emoji-grid-item {
  aspect-ratio: 1;
  border: none;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  font-size: 22px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.12s;
}
.emoji-grid-item:active { background: var(--color-surface-card); }
.emoji-grid-item.selected {
  background: var(--color-brand-peach);
  outline: 2px solid var(--color-brand-ochre);
}
</style>
