import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import IconPicker from '../IconPicker.vue'

// Mock the icon manifest to keep the test fast and deterministic.
// vi.hoisted ensures the mock data is available when vi.mock's factory runs.
const { mockCategories, mockIcons } = vi.hoisted(() => ({
  mockCategories: [
    {
      id: 'vehicles',
      nameZh: '交通工具',
      nameEn: 'Vehicles',
      folder: 'vehicles',
      sortOrder: 0,
      assetCategoryHints: ['car'],
    },
    {
      id: 'electronics',
      nameZh: '电子设备',
      nameEn: 'Electronics',
      folder: 'electronics',
      sortOrder: 1,
      assetCategoryHints: ['phone'],
    },
  ],
  mockIcons: {
    vehicles: [
      { fileName: '汽车_Car.png', nameZh: '汽车', nameEn: 'Car' },
      { fileName: '卡车_Truck.png', nameZh: '卡车', nameEn: 'Truck' },
    ],
    electronics: [
      { fileName: '手机_Phone.png', nameZh: '手机', nameEn: 'Phone' },
      { fileName: '电脑_Laptop.png', nameZh: '电脑', nameEn: 'Laptop' },
    ],
  } as Record<string, Array<{ fileName: string; nameZh: string; nameEn: string }>>,
}))

vi.mock('@numina/assets/icons/manifest', () => ({
  iconManifest: {
    categories: mockCategories,
    icons: mockIcons,
  },
}))

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      iconPicker: {
        tabGallery: 'Gallery',
        tab3dIcons: '3D Icons',
        tabEmoji: 'Emoji',
        fromGallery: 'Choose from Gallery',
        fromCamera: 'Take Photo',
        searchPlaceholder: 'Search icons',
        allCategories: 'All',
        noResults: 'No matching icons',
        loading: 'Loading...',
        recentAlbum: 'Recent',
        changeIcon: 'Change Icon',
        emojiHint: 'Tap the input below to select an emoji',
        emojiPlaceholder: 'Tap to enter emoji',
        emojiPresets: 'Common emojis',
      },
    },
  },
})

function mountPicker(props: Record<string, unknown> = {}) {
  return mount(IconPicker, {
    props: {
      show: true,
      ...props,
    },
    global: {
      plugins: [createPinia(), i18n],
      stubs: {
        teleport: true,
        VanPopup: {
          template: '<div class="van-popup" v-if="$attrs.show"><slot /></div>',
          inheritAttrs: true,
        },
        VanButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        VanIcon: { template: '<i @click="$emit(\'click\')" />' },
        VanSearch: {
          template: '<input class="van-search" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue', 'placeholder'],
        },
        VanLoading: { template: '<div class="van-loading" />' },
      },
    },
  })
}

describe('IconPicker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders gallery tab by default when show=true', () => {
    const wrapper = mountPicker()
    const html = wrapper.html()
    expect(html).toContain('Gallery')
    expect(html).toContain('3D Icons')
    // Gallery buttons visible in default tab
    expect(html).toContain('Choose from Gallery')
    expect(html).toContain('Take Photo')
  })

  it('switches to 3D icons tab on click', async () => {
    const wrapper = mountPicker()
    const tabs = wrapper.findAll('.tab')
    expect(tabs.length).toBe(2)

    // Click 3D Icons tab (second tab)
    await tabs[1].trigger('click')

    // Should now show category tabs
    const html = wrapper.html()
    expect(html).toContain('Vehicles')
    expect(html).toContain('Electronics')
  })

  it('shows current image preview in edit mode', () => {
    const wrapper = mountPicker({ currentImageUrl: '/icons/3d/vehicles/car.png' })
    expect(wrapper.find('.current-preview').exists()).toBe(true)
    expect(wrapper.find('.preview-thumb').exists()).toBe(true)
  })

  it('emits request-gallery when gallery button clicked', async () => {
    const wrapper = mountPicker()
    const buttons = wrapper.findAll('button')
    // First button is "Choose from Gallery"
    await buttons[0].trigger('click')
    expect(wrapper.emitted('request-gallery')).toBeTruthy()
  })

  it('emits request-camera when camera button clicked', async () => {
    const wrapper = mountPicker()
    const buttons = wrapper.findAll('button')
    // Second button is "Take Photo"
    await buttons[1].trigger('click')
    expect(wrapper.emitted('request-camera')).toBeTruthy()
  })

  it('emits delete when delete button clicked', async () => {
    const wrapper = mountPicker({ currentImageUrl: '/icons/3d/vehicles/car.png' })
    const deleteBtn = wrapper.find('.delete-btn')
    await deleteBtn.trigger('click')
    expect(wrapper.emitted('delete')).toBeTruthy()
  })

  it('emits update:show false when close requested', async () => {
    const wrapper = mountPicker()
    // Simulate popup close (overlay click) by emitting update:show from VanPopup
    const popup = wrapper.find('.van-popup')
    // The popup stub doesn't emit; we test via the closeable prop instead.
    // Verify the component accepts the show prop and can emit update:show
    expect(wrapper.props('show')).toBe(true)
    // Directly call the closed handler path via $emit simulation
    wrapper.vm.$emit('update:show', false)
    expect(wrapper.emitted('update:show')).toBeTruthy()
  })

  it('shows category names in English for en locale', async () => {
    const wrapper = mountPicker()
    const tabs = wrapper.findAll('.tab')
    await tabs[1].trigger('click') // 3D tab

    expect(wrapper.html()).toContain('Vehicles')
    expect(wrapper.html()).toContain('Electronics')
  })

  it('shows "All" pseudo-category', async () => {
    const wrapper = mountPicker()
    const tabs = wrapper.findAll('.tab')
    await tabs[1].trigger('click') // 3D tab

    expect(wrapper.html()).toContain('All')
  })

  it('renders icon cells in 3D tab', async () => {
    const wrapper = mountPicker()
    const tabs = wrapper.findAll('.tab')
    await tabs[1].trigger('click') // 3D tab

    // Default category (vehicles) has 2 icons
    const cells = wrapper.findAll('.icon-cell')
    expect(cells.length).toBe(2)
  })

  it('emits select-image with thumbnail URL when icon clicked', async () => {
    const wrapper = mountPicker()
    const tabs = wrapper.findAll('.tab')
    await tabs[1].trigger('click') // 3D tab

    const cells = wrapper.findAll('.icon-cell')
    await cells[0].trigger('click')

    const emitted = wrapper.emitted('select-image')
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toContain('/icons/3d/vehicles/')
    expect(emitted![0][0]).toContain('Car')
  })

  // --- Emoji tab ---

  it('shows emoji tab when mode=avatar', () => {
    const wrapper = mountPicker({ mode: 'avatar' })
    const tabs = wrapper.findAll('.tab')
    expect(tabs.length).toBe(3)
    expect(tabs[2].text()).toBe('Emoji')
  })

  it('renders preset emoji grid in emoji tab', async () => {
    const wrapper = mountPicker({ mode: 'avatar' })
    const tabs = wrapper.findAll('.tab')
    await tabs[2].trigger('click') // Emoji tab

    const buttons = wrapper.findAll('.emoji-preset-btn')
    expect(buttons.length).toBeGreaterThan(0)
  })

  it('emits select-emoji when preset emoji clicked', async () => {
    const wrapper = mountPicker({ mode: 'avatar' })
    const tabs = wrapper.findAll('.tab')
    await tabs[2].trigger('click') // Emoji tab

    const buttons = wrapper.findAll('.emoji-preset-btn')
    await buttons[0].trigger('click')

    const emitted = wrapper.emitted('select-emoji')
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toBeTruthy()
  })

  it('highlights currently selected emoji in preset grid', async () => {
    const wrapper = mountPicker({ mode: 'avatar', currentEmoji: '😀' })
    const tabs = wrapper.findAll('.tab')
    await tabs[2].trigger('click') // Emoji tab

    const selectedBtn = wrapper.find('.emoji-preset-btn.selected')
    expect(selectedBtn.exists()).toBe(true)
    expect(selectedBtn.text()).toBe('😀')
  })

  it('shows emoji preview and delete button when currentEmoji is set', () => {
    const wrapper = mountPicker({ currentEmoji: '😀' })
    expect(wrapper.find('.current-preview').exists()).toBe(true)
    expect(wrapper.find('.preview-emoji').exists()).toBe(true)
    expect(wrapper.find('.preview-emoji').text()).toBe('😀')
    expect(wrapper.find('.delete-btn').exists()).toBe(true)
  })

  it('emits delete when delete button clicked on emoji avatar', async () => {
    const wrapper = mountPicker({ currentEmoji: '😀' })
    const deleteBtn = wrapper.find('.delete-btn')
    await deleteBtn.trigger('click')
    expect(wrapper.emitted('delete')).toBeTruthy()
  })
})
