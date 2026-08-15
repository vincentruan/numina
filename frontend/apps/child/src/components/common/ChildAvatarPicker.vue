<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    closeable
    :close-on-click-overlay="true"
    @update:show="(v: boolean) => emit('update:show', v)"
    @closed="onClosed"
  >
    <div class="avatar-picker">
      <!-- Header -->
      <div class="picker-header">
        <span class="picker-title">{{ t('avatarPicker.title') }}</span>
      </div>

      <!-- Current avatar preview + delete -->
      <div v-if="currentAvatarUrl" class="current-preview">
        <UserAvatar
          :avatar-url="currentAvatarUrl"
          :avatar-color="'#4F46E5'"
          :display-name="''"
          :size="72"
        />
        <van-icon name="cross" class="delete-btn" @click="emit('delete')" />
      </div>

      <!-- Tab bar -->
      <div class="tab-bar">
        <div
          class="tab"
          :class="{ active: activeTab === '3d' }"
          @click="activeTab = '3d'"
        >{{ t('avatarPicker.tab3d') }}</div>
        <div
          class="tab"
          :class="{ active: activeTab === 'emoji' }"
          @click="activeTab = 'emoji'"
        >{{ t('avatarPicker.tabEmoji') }}</div>
      </div>

      <!-- 3D icons tab -->
      <div v-if="activeTab === '3d'" class="icon3d-content">
        <div class="category-scroll">
          <div
            v-for="cat in categories"
            :key="cat.id"
            class="cat-tab"
            :class="{ active: activeCategory === cat.id }"
            @click="activeCategory = cat.id"
          >{{ cat.nameZh }}</div>
        </div>

        <div class="icon-grid">
          <div
            v-for="icon in currentIcons"
            :key="icon.fileName"
            class="icon-cell"
            :class="{ selected: isSelected(icon) }"
            @click="selectIcon(icon)"
          >
            <img
              :src="getThumbUrl(icon)"
              loading="lazy"
              class="thumb-img"
            />
          </div>
        </div>
      </div>

      <!-- Emoji tab -->
      <div v-if="activeTab === 'emoji'" class="emoji-content">
        <div class="emoji-hint">{{ t('avatarPicker.emojiHint') }}</div>
        <input
          ref="emojiInput"
          type="text"
          class="emoji-input"
          @input="onEmojiInput"
          :placeholder="t('avatarPicker.emojiPlaceholder')"
        />
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { iconManifest } from '@numina/assets/icons/manifest'
import type { IconEntry } from '@numina/assets/icons/manifest'
import UserAvatar from '@/components/common/UserAvatar.vue'

const { t } = useI18n()

const props = defineProps<{
  show: boolean
  currentAvatarUrl?: string
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'select-image': [url: string]
  'select-emoji': [emoji: string]
  delete: []
}>()

const activeTab = ref<'3d' | 'emoji'>('3d')
const activeCategory = ref('characters')

// Avatar-only categories
const categories = computed(() => {
  return iconManifest.categories.filter(cat =>
    ['characters', 'historical-figures', 'religion-mythology', 'flags', 'numbers-symbols'].includes(cat.id)
  )
})

const currentIcons = computed(() => {
  return iconManifest.icons[activeCategory.value] ?? []
})

function getThumbUrl(icon: IconEntry): string {
  const folder = activeCategory.value
  const stem = icon.fileName.replace(/\.[^.]+$/, '')
  return `/icons/3d-thumbs/${folder}/${stem}.webp`
}

function isSelected(icon: IconEntry): boolean {
  return props.currentAvatarUrl === getThumbUrl(icon)
}

function selectIcon(icon: IconEntry) {
  emit('select-image', getThumbUrl(icon))
}

const emojiInput = ref<HTMLInputElement | null>(null)

function onEmojiInput(event: Event) {
  const input = event.target as HTMLInputElement
  const value = input.value
  if (value) {
    const lastChar = [...value].pop() || ''
    if (lastChar) {
      emit('select-emoji', lastChar)
      input.value = ''
    }
  }
}

function onClosed() {
  activeTab.value = '3d'
  activeCategory.value = 'characters'
}
</script>

<style scoped>
.avatar-picker {
  display: flex;
  flex-direction: column;
  max-height: 75vh;
  min-height: 50vh;
  padding: 0 12px 16px;
}

.picker-header {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 0 8px;
}
.picker-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
}

.current-preview {
  position: relative;
  display: flex;
  justify-content: center;
  padding: 8px 0 12px;
}
.delete-btn {
  position: absolute;
  top: 0;
  right: calc(50% - 44px);
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--van-danger-color, #ee0a24);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.tab-bar {
  display: flex;
  background: var(--color-surface-soft);
  border-radius: 10px;
  padding: 3px;
  margin-bottom: 12px;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 8px;
  border-radius: 8px;
  font-size: 14px;
  color: var(--color-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.tab.active {
  background: var(--color-surface-card);
  color: var(--color-ink);
  font-weight: 600;
}

.icon3d-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.category-scroll {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  margin-bottom: 12px;
  scrollbar-width: none;
}
.category-scroll::-webkit-scrollbar {
  display: none;
}
.cat-tab {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 14px;
  font-size: 13px;
  background: var(--color-surface-soft);
  color: var(--color-muted);
  cursor: pointer;
  white-space: nowrap;
}
.cat-tab.active {
  background: var(--color-ink);
  color: var(--color-canvas);
  font-weight: 500;
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 6px;
  overflow-y: auto;
  flex: 1;
}

.icon-cell {
  aspect-ratio: 1;
  min-height: 56px;
  border-radius: 10px;
  background: var(--color-surface-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
}
.icon-cell:active {
  transform: scale(0.95);
}
.icon-cell.selected {
  box-shadow: 0 0 0 2px var(--color-primary);
}

.thumb-img {
  max-width: 80%;
  max-height: 80%;
  object-fit: contain;
}

.emoji-content {
  padding: 24px 16px;
  text-align: center;
}
.emoji-hint {
  font-size: 14px;
  color: var(--color-muted);
  margin-bottom: 16px;
}
.emoji-input {
  width: 100%;
  max-width: 200px;
  padding: 12px 16px;
  font-size: 32px;
  text-align: center;
  border: 2px dashed var(--color-hairline);
  border-radius: 12px;
  background: var(--color-surface-soft);
  color: var(--color-ink);
  outline: none;
}
.emoji-input:focus {
  border-color: var(--color-primary);
}
.emoji-input::placeholder {
  font-size: 14px;
  color: var(--color-muted);
}
</style>
