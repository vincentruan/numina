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
    <div class="icon-picker">
      <!-- Header -->
      <div class="picker-header">
        <span class="picker-title">{{ t('iconPicker.changeIcon') }}</span>
      </div>

      <!-- Edit mode: current image preview + delete -->
      <div v-if="currentImageUrl" class="current-preview">
        <img :src="currentImageUrl" class="preview-thumb" />
        <van-icon name="cross" class="delete-btn" @click="emit('delete')" />
      </div>

      <!-- Tab bar -->
      <div class="tab-bar">
        <div
          class="tab"
          :class="{ active: activeTab === 'gallery' }"
          @click="activeTab = 'gallery'"
        >{{ t('iconPicker.tabGallery') }}</div>
        <div
          class="tab"
          :class="{ active: activeTab === '3d' }"
          @click="activeTab = '3d'"
        >{{ t('iconPicker.tab3dIcons') }}</div>
        <div
          v-if="mode === 'avatar'"
          class="tab"
          :class="{ active: activeTab === 'emoji' }"
          @click="activeTab = 'emoji'"
        >{{ t('iconPicker.tabEmoji') }}</div>
      </div>

      <!-- Gallery tab -->
      <div v-if="activeTab === 'gallery'" class="gallery-content">
        <van-button
          icon="photograph"
          block
          @click="emit('request-gallery')"
        >{{ t('iconPicker.fromGallery') }}</van-button>
        <van-button
          icon="photograph"
          block
          @click="emit('request-camera')"
        >{{ t('iconPicker.fromCamera') }}</van-button>
      </div>

      <!-- Emoji tab (avatar mode only) -->
      <div v-if="activeTab === 'emoji'" class="emoji-content">
        <div class="emoji-hint">{{ t('iconPicker.emojiHint') }}</div>
        <input
          ref="emojiInput"
          type="text"
          class="emoji-input"
          @input="onEmojiInput"
          :placeholder="t('iconPicker.emojiPlaceholder')"
        />
      </div>

      <!-- 3D icons tab -->
      <div v-if="activeTab === '3d'" class="icon3d-content">
        <!-- Category tabs + search toggle -->
        <div class="category-bar">
          <div class="category-scroll">
            <div
              v-for="cat in categories"
              :key="cat.id"
              class="cat-tab"
              :class="{ active: activeCategory === cat.id }"
              @click="selectCategory(cat.id)"
            >{{ getCategoryName(cat) }}</div>
          </div>
          <van-icon
            name="search"
            class="search-btn"
            :class="{ active: isSearchMode }"
            @click="toggleSearch"
          />
        </div>

        <!-- Search input (collapsible) -->
        <div v-if="showSearchInput" class="search-wrap">
          <van-search
            v-model="searchQuery"
            :placeholder="t('iconPicker.searchPlaceholder')"
            shape="round"
            @update:model-value="onSearchInput"
            @clear="clearSearch"
          />
        </div>

        <!-- Icon grid with infinite scroll -->
        <div class="icon-grid-scroll">
          <!-- Grid loading overlay (shown on tab switch / category change) -->
          <div v-if="gridLoading && paginatedIcons.length === 0" class="grid-loading">
            <van-loading size="24px" />
          </div>
          <van-list
            :finished="!hasMore"
            :finished-text="searchQuery ? '' : undefined"
            :immediate-check="true"
            @load="loadMore"
          >
            <div class="icon-grid" :class="{ 'avatar-mode': mode === 'avatar' }">
              <div v-if="paginatedIcons.length === 0 && searchQuery" class="empty-state">
                {{ t('iconPicker.noResults') }}
              </div>
              <div
                v-for="icon in paginatedIcons"
                :key="icon.fileName"
                class="icon-cell"
                :class="{ selected: isSelected(icon) }"
                @click="selectIcon(icon)"
              >
                <div class="icon-thumb">
                  <img
                    :src="getThumbUrl(icon)"
                    loading="lazy"
                    class="thumb-img"
                    @load="onThumbLoad($event)"
                    @error="onThumbError"
                  />
                  <!-- Magnify button: preview original (doesn't select) -->
                  <van-icon
                    name="zoom-in"
                    class="magnify-btn"
                    @click.stop="enlargeIcon(icon)"
                  />
                  <!-- Selected checkmark -->
                  <van-icon v-if="isSelected(icon)" name="success" class="check-overlay" />
                </div>
              </div>
            </div>
          </van-list>
        </div>

        <!-- Enlarge preview overlay -->
        <div v-if="enlargedUrl" class="enlarge-overlay" @click="enlargedUrl = ''">
          <van-loading v-if="enlargeLoading" class="enlarge-spinner" size="36px" />
          <img
            :src="enlargedUrl"
            class="enlarge-img"
            :class="{ visible: !enlargeLoading }"
            @load="enlargeLoading = false"
            @error="enlargeLoading = false"
          />
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useIconCatalog } from '@/composables/useIconCatalog'
import type { IconEntry } from '@numina/assets/icons/manifest'

const { t } = useI18n()

const props = defineProps<{
  show: boolean
  currentImageUrl?: string
  mode?: 'asset' | 'avatar'
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'select-image': [url: string]
  'select-emoji': [emoji: string]
  'request-gallery': []
  'request-camera': []
  delete: []
}>()

const activeTab = ref<'gallery' | '3d' | 'emoji'>('gallery')
const showSearchInput = ref(false)
const enlargedUrl = ref<string>('')
const enlargeLoading = ref(false)
const gridLoading = ref(false)

const {
  categories,
  activeCategory,
  paginatedIcons,
  totalIcons,
  hasMore,
  searchQuery,
  isSearchMode,
  selectCategory,
  search,
  clearSearch,
  loadMore,
  getThumbUrl,
  getOriginalUrl,
  getCategoryName,
  reset,
} = useIconCatalog({ avatarOnly: props.mode === 'avatar' })

// Track the currently-selected icon (for highlight) based on currentImageUrl.
const selectedIconUrl = ref<string>('')

watch(
  () => props.currentImageUrl,
  (url) => {
    selectedIconUrl.value = url ?? ''
  },
  { immediate: true },
)

// Show grid loading when switching to 3D tab, changing category, or searching.
watch(
  () => [activeTab.value, activeCategory.value, isSearchMode.value],
  () => {
    if (activeTab.value === '3d') {
      gridLoading.value = true
    }
  },
)

// Mark individual thumbnail as loaded; clear grid loading when all visible are done.
function onThumbLoad(event: Event) {
  const img = event.target as HTMLImageElement
  img.classList.add('loaded')
  const allImgs = document.querySelectorAll<HTMLImageElement>('.icon-thumb .thumb-img')
  const allDone = Array.from(allImgs).every(
    (i) => i.classList.contains('loaded') || i.complete,
  )
  if (allDone) gridLoading.value = false
}

function isSelected(icon: IconEntry): boolean {
  return selectedIconUrl.value === getThumbUrl(icon)
}

function selectIcon(icon: IconEntry) {
  // Store thumbnail URL for display (256px WebP, good quality for list + detail)
  const url = getThumbUrl(icon)
  selectedIconUrl.value = url
  emit('select-image', url)
}

function enlargeIcon(icon: IconEntry) {
  // Load original full-size image for preview
  enlargedUrl.value = getOriginalUrl(icon)
  enlargeLoading.value = true
}

function toggleSearch() {
  showSearchInput.value = !showSearchInput.value
  if (!showSearchInput.value) {
    clearSearch()
  }
}

function onSearchInput(val: string) {
  search(val)
}

// Fallback for broken thumbnail: hide the img, stop skeleton animation.
function onThumbError(event: Event) {
  const img = event.target as HTMLImageElement
  img.style.visibility = 'hidden'
  img.classList.add('loaded')
}

// Reset state when popup closes.
function onClosed() {
  activeTab.value = 'gallery'
  showSearchInput.value = false
  enlargedUrl.value = ''
  enlargeLoading.value = false
  gridLoading.value = false
  reset()
}

// Emoji input handler
const emojiInput = ref<HTMLInputElement | null>(null)

function onEmojiInput(event: Event) {
  const input = event.target as HTMLInputElement
  const value = input.value
  if (value) {
    // Extract the last emoji (in case of multiple)
    const lastChar = [...value].pop() || ''
    if (lastChar) {
      // Reject ASCII characters, whitespace, and common punctuation
      // Emoji are typically outside the ASCII range (0x00-0x7F)
      if (/^[\s\x20-\x7E]$/.test(lastChar)) {
        input.value = ''
        return
      }
      emit('select-emoji', lastChar)
      input.value = ''
    }
  }
}

// Expose totalIcons for debugging / tests.
void totalIcons
</script>

<style scoped>
.icon-picker {
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
  color: var(--van-text-color);
}

/* Edit-mode current preview */
.current-preview {
  position: relative;
  display: flex;
  justify-content: center;
  padding: 8px 0 12px;
}
.preview-thumb {
  width: 72px;
  height: 72px;
  border-radius: 12px;
  object-fit: cover;
  background: var(--van-background-2);
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

/* Tab bar */
.tab-bar {
  display: flex;
  background: var(--van-background-2);
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
  color: var(--van-text-color-2);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.tab.active {
  background: var(--van-background);
  color: var(--van-text-color);
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .tab.active {
  background: var(--color-lavender, #bdbbff);
  color: #010120;
}

/* Gallery tab */
.gallery-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 0;
}

/* 3D icons tab */
.icon3d-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.category-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.category-scroll {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  flex: 1;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}
.category-scroll::-webkit-scrollbar {
  display: none;
}
.cat-tab {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 14px;
  font-size: 13px;
  background: var(--van-background-2);
  color: var(--van-text-color-2);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}
.cat-tab.active {
  background: var(--van-text-color, #1a1a1a);
  color: var(--van-background, #fff);
  font-weight: 500;
}
[data-theme='dark'] .cat-tab.active {
  background: var(--color-lavender, #bdbbff);
  color: #010120;
}
.search-btn {
  flex-shrink: 0;
  font-size: 20px;
  color: var(--van-text-color-2);
  padding: 4px;
}
.search-btn.active {
  color: var(--van-primary-color);
}

.search-wrap {
  margin: 0 -12px 8px;
}

/* Icon grid scroll container (for van-list infinite scroll) */
.icon-grid-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  position: relative;
}
.grid-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

/* Icon grid */
.icon-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  padding: 4px 0;
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 32px 0;
  font-size: 14px;
  color: var(--van-text-color-3);
}

.icon-cell {
  aspect-ratio: 1;
  min-height: 64px;
  border-radius: 10px;
  background: var(--van-background-2);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.15s;
  overflow: hidden;
}
.icon-cell:active {
  transform: scale(0.95);
}
.icon-cell.selected {
  box-shadow: 0 0 0 2px var(--van-primary-color);
}
.icon-thumb {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: 0;
}
/* Skeleton shimmer until the <img> fires its load event */
.icon-thumb::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    var(--van-background-2) 0%,
    var(--van-background-3, #f0f0f0) 50%,
    var(--van-background-2) 100%
  );
  background-size: 200% 100%;
  animation: icon-skeleton 1.5s ease-in-out infinite;
}
[data-theme='dark'] .icon-thumb::before {
  background: linear-gradient(
    90deg,
    var(--van-background-2) 0%,
    #2a2a40 50%,
    var(--van-background-2) 100%
  );
  background-size: 200% 100%;
}
.icon-thumb:has(.loaded)::before {
  display: none;
}
@keyframes icon-skeleton {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
.thumb-img {
  position: relative;
  z-index: 1;
  opacity: 0;
  transition: opacity 0.2s ease;
}
.thumb-img.loaded {
  opacity: 1;
}
.icon-thumb img {
  max-width: 80%;
  max-height: 80%;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
}
.check-overlay {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--van-primary-color);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
.magnify-btn {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  opacity: 0;
  transition: opacity 0.15s;
  cursor: pointer;
}
.icon-cell:hover .magnify-btn,
.icon-cell:active .magnify-btn {
  opacity: 1;
}

/* Enlarge preview overlay */
.enlarge-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.enlarge-spinner {
  position: absolute;
  color: #fff;
}
.enlarge-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 12px;
  opacity: 0;
  transition: opacity 0.2s ease;
}
.enlarge-img.visible {
  opacity: 1;
}

/* Emoji tab */
.emoji-content {
  padding: 24px 16px;
  text-align: center;
}
.emoji-hint {
  font-size: 14px;
  color: var(--van-text-color-2);
  margin-bottom: 16px;
}
.emoji-input {
  width: 100%;
  max-width: 200px;
  padding: 12px 16px;
  font-size: 32px;
  text-align: center;
  border: 2px dashed var(--van-border-color);
  border-radius: 12px;
  background: var(--van-background-2);
  color: var(--van-text-color);
  outline: none;
  transition: border-color 0.15s;
}
.emoji-input:focus {
  border-color: var(--van-primary-color);
}
.emoji-input::placeholder {
  font-size: 14px;
  color: var(--van-text-color-3);
}

/* Avatar mode: 6-column grid with smaller cells */
.icon-grid.avatar-mode {
  grid-template-columns: repeat(6, 1fr);
  gap: 6px;
}
.icon-grid.avatar-mode .icon-cell {
  min-height: 56px;
}
</style>
