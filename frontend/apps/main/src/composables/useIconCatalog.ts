/**
 * useIconCatalog - composable for browsing the 3D icon catalog.
 *
 * Provides category navigation, pagination, and cross-category search
 * over the icon manifest. URLs are built from the category folder and
 * icon filename; Phase 1 serves original images, Phase 2 serves
 * pre-generated 128x128 WebP thumbnails. Switch via USE_THUMBS below.
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { iconManifest } from '@numina/assets/icons/manifest'
import type { IconCategory, IconEntry } from '@numina/assets/icons/manifest'

const PAGE_SIZE = 40
const ALL_CATEGORY_ID = '__all__'

// Phase 1: serve 256×256 WebP thumbnails (good quality for list + detail pages)
// Full originals available via getOriginalUrl() for lightbox/enlarge.
const USE_THUMBS = true

// Avatar-only categories (not shown in asset picker)
const AVATAR_CATEGORY_IDS = [
  'characters',
  'historical-figures',
  'religion-mythology',
  'flags',
  'numbers-symbols',
]

function stripExt(fileName: string): string {
  const dot = fileName.lastIndexOf('.')
  return dot > 0 ? fileName.slice(0, dot) : fileName
}

function buildThumbUrl(category: IconCategory, icon: IconEntry): string {
  const folder = category.folder
  if (USE_THUMBS) {
    return `/icons/3d-thumbs/${folder}/${stripExt(icon.fileName)}.webp`
  }
  return `/icons/3d/${folder}/${icon.fileName}`
}

function buildOriginalUrl(category: IconCategory, icon: IconEntry): string {
  return `/icons/3d/${category.folder}/${icon.fileName}`
}

export function useIconCatalog(options?: { avatarOnly?: boolean }) {
  const { locale } = useI18n()

  const isZh = computed(() => locale.value === 'zh-CN')

  // Filter categories based on mode
  const filteredCategories = computed(() => {
    if (options?.avatarOnly) {
      return iconManifest.categories.filter(cat => AVATAR_CATEGORY_IDS.includes(cat.id))
    }
    // Asset mode: exclude avatar-only categories
    return iconManifest.categories.filter(cat => !AVATAR_CATEGORY_IDS.includes(cat.id))
  })

  // "全部" pseudo-category prepended to the manifest categories.
  const categories = computed<IconCategory[]>(() => [
    {
      id: ALL_CATEGORY_ID,
      nameZh: '全部',
      nameEn: 'All',
      folder: '',
      sortOrder: -1,
      assetCategoryHints: [],
    },
    ...filteredCategories.value,
  ])

  const activeCategory = ref<string>(filteredCategories.value[0]?.id ?? '')

  const searchQuery = ref('')
  const isSearchMode = ref(false)
  const currentPage = ref(0)

  // Reset pagination when category or search changes.
  function resetPagination() {
    currentPage.value = 0
  }

  // Flatten all icons in manifest order (for "全部" and search).
  const allIconsFlat = computed<{ category: IconCategory; icon: IconEntry }[]>(() => {
    const flat: { category: IconCategory; icon: IconEntry }[] = []
    for (const cat of filteredCategories.value) {
      const entries = iconManifest.icons[cat.id] ?? []
      for (const icon of entries) {
        flat.push({ category: cat, icon })
      }
    }
    return flat
  })

  // Base list for the active view (category-specific or search results or all).
  const baseList = computed<{ category: IconCategory; icon: IconEntry }[]>(() => {
    if (isSearchMode.value && searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase()
      return allIconsFlat.value.filter(({ icon }) => {
        return (
          icon.nameZh.toLowerCase().includes(q) ||
          icon.nameEn.toLowerCase().includes(q) ||
          icon.fileName.toLowerCase().includes(q)
        )
      })
    }

    if (activeCategory.value === ALL_CATEGORY_ID) {
      return allIconsFlat.value
    }

    const cat = filteredCategories.value.find((c) => c.id === activeCategory.value)
    if (!cat) return []
    const entries = iconManifest.icons[cat.id] ?? []
    return entries.map((icon) => ({ category: cat, icon }))
  })

  const totalIcons = computed(() => baseList.value.length)

  const paginatedIcons = computed<IconEntry[]>(() => {
    const end = (currentPage.value + 1) * PAGE_SIZE
    return baseList.value.slice(0, end).map((item) => item.icon)
  })

  const hasMore = computed(() => paginatedIcons.value.length < totalIcons.value)

  // Keep a map for URL building: fileName -> category (for current view).
  const iconToCategory = computed<Map<string, IconCategory>>(() => {
    const m = new Map<string, IconCategory>()
    for (const { category, icon } of baseList.value) {
      m.set(icon.fileName, category)
    }
 return m
  })

  function loadMore() {
    if (hasMore.value) {
      currentPage.value++
    }
  }

  function selectCategory(id: string) {
    activeCategory.value = id
    searchQuery.value = ''
    isSearchMode.value = false
    resetPagination()
  }

  // Debounced search trigger. The watcher on searchQuery below applies the
  // 300ms debounce.
  let searchTimer: ReturnType<typeof setTimeout> | null = null

  function search(query: string) {
    searchQuery.value = query
  }

  watch(searchQuery, (val) => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      isSearchMode.value = val.trim().length > 0
      resetPagination()
    }, 300)
  })

  function clearSearch() {
    searchQuery.value = ''
    isSearchMode.value = false
    resetPagination()
  }

  // Reset state when popup closes (call from parent on close).
  function reset() {
    activeCategory.value = filteredCategories.value[0]?.id ?? ''
    searchQuery.value = ''
    isSearchMode.value = false
    resetPagination()
  }

  function getCategoryName(cat: IconCategory): string {
    return isZh.value ? cat.nameZh : cat.nameEn
  }

  function getIconName(icon: IconEntry): string {
    return isZh.value ? icon.nameZh : icon.nameEn
  }

  function getThumbUrl(icon: IconEntry): string {
    const cat = iconToCategory.value.get(icon.fileName)
    if (!cat) {
      // Fallback: search manifest for this icon.
      for (const c of iconManifest.categories) {
        const found = (iconManifest.icons[c.id] ?? []).find((e) => e.fileName === icon.fileName)
        if (found) return buildThumbUrl(c, icon)
      }
      return ''
    }
    return buildThumbUrl(cat, icon)
  }

  function getOriginalUrl(icon: IconEntry): string {
    const cat = iconToCategory.value.get(icon.fileName)
    if (!cat) {
      for (const c of iconManifest.categories) {
        const found = (iconManifest.icons[c.id] ?? []).find((e) => e.fileName === icon.fileName)
        if (found) return buildOriginalUrl(c, icon)
      }
      return ''
    }
    return buildOriginalUrl(cat, icon)
  }

  return {
    categories,
    activeCategory,
    paginatedIcons,
    totalIcons,
    isLoading: ref(false),
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
    getIconName,
    reset,
  }
}
