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

        <!-- Icon grid -->
        <div ref="gridRef" class="icon-grid">
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
                @error="onThumbError"
              />
              <van-icon v-if="isSelected(icon)" name="success" class="check-overlay" />
            </div>
          </div>
        </div>

        <!-- Load more trigger -->
        <div v-if="hasMore" class="load-more" @click="loadMore">
          <van-loading v-if="loadingMore" size="20" />
          <span v-else>{{ t('iconPicker.loading') }}</span>
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useIconCatalog } from '@/composables/useIconCatalog'
import type { IconEntry } from '@numina/assets/icons/manifest'

const { t } = useI18n()

const props = defineProps<{
  show: boolean
  currentImageUrl?: string
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'select-image': [url: string]
  'request-gallery': []
  'request-camera': []
  delete: []
}>()

const activeTab = ref<'gallery' | '3d'>('gallery')
const showSearchInput = ref(false)
const loadingMore = ref(false)
const gridRef = ref<HTMLDivElement>()

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
} = useIconCatalog()

// Track the currently-selected icon (for highlight) based on currentImageUrl.
const selectedIconUrl = ref<string>('')

watch(
  () => props.currentImageUrl,
  (url) => {
    selectedIconUrl.value = url ?? ''
  },
  { immediate: true },
)

function isSelected(icon: IconEntry): boolean {
  return selectedIconUrl.value === getOriginalUrl(icon)
}

function selectIcon(icon: IconEntry) {
  const url = getOriginalUrl(icon)
  selectedIconUrl.value = url
  emit('select-image', url)
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

// Fallback for broken thumbnail: hide the img so the cell stays tappable.
function onThumbError(event: Event) {
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
}

// Reset state when popup closes.
function onClosed() {
  activeTab.value = 'gallery'
  showSearchInput.value = false
  reset()
}

// Scroll-triggered load more.
watch(
  () => props.show,
  async (visible) => {
    if (visible) {
      await nextTick()
      setupScrollLoad()
    }
  },
)

function setupScrollLoad() {
  const grid = gridRef.value
  if (!grid) return
  grid.addEventListener('scroll', () => {
    if (!hasMore.value || loadingMore.value) return
    const nearBottom = grid.scrollTop + grid.clientHeight >= grid.scrollHeight - 100
    if (nearBottom) {
      loadingMore.value = true
      loadMore()
      nextTick(() => {
        loadingMore.value = false
      })
    }
  })
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
  object-fit: contain;
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

/* Icon grid */
.icon-grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  padding: 4px 0;
  -webkit-overflow-scrolling: touch;
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
  top: 2px;
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

.load-more {
  text-align: center;
  padding: 12px 0;
  font-size: 13px;
  color: var(--van-text-color-3);
}
</style>
