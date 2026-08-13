import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import AssetForm from '../AssetForm.vue'
import type { Category } from '@/types'

// Mock Vant components that use browser APIs
vi.mock('vant', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('vant')
  return {
    ...actual,
    showLoadingToast: vi.fn(),
    showSuccessToast: vi.fn(),
    showFailToast: vi.fn(),
    showToast: vi.fn(),
  }
})

// Mock API modules
vi.mock('@/api/upload', () => ({
  uploadImage: vi.fn(),
}))
vi.mock('@/api/tags', () => ({
  getTags: vi.fn().mockResolvedValue({ data: [] }),
}))
vi.mock('@/api/ai', () => ({
  suggestAssetFields: vi.fn().mockResolvedValue({ data: {} }),
}))

// Mock stores
vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({
    aiEnabled: false,
  }),
}))

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      assetForm: {
        imageUploadHint: 'Tap to upload',
        typePhysical: 'Physical',
        typeFinancial: 'Financial',
        sectionBasicInfo: 'Basic Info',
        sectionPhysicalInfo: 'Physical Info',
        sectionFinancialInfo: 'Financial Info',
        sectionWarrantyInfo: 'Warranty Info',
        sectionTagsNotes: 'Tags & Notes',
        nameLabel: 'Name',
        namePlaceholder: 'Enter name',
        nameRequired: 'Name is required',
        categoryLabel: 'Category',
        categoryPlaceholder: 'Select category',
        categoryEmpty: 'No categories',
        categoryRequired: 'Category is required',
        purchasePriceLabel: 'Purchase Price',
        purchasePricePlaceholder: 'Enter price',
        purchasePriceRequired: 'Price is required',
        currentValueLabel: 'Current Value',
        currentValuePlaceholder: 'Enter value',
        currentValueRequired: 'Value is required',
        samePriceBtn: 'Same as purchase',
        purchaseDateLabel: 'Purchase Date',
        purchaseDatePlaceholder: 'Select date',
        purchaseDateRequired: 'Date is required',
        datePickerTitle: 'Select date',
        statusLabel: 'Status',
        statusPlaceholder: 'Select status',
        usageFreqLabel: 'Usage Frequency',
        lifespanLabel: 'Lifespan',
        lifespanPlaceholder: 'Enter years',
        lifespanUnitYears: 'years',
        lifespanUnlimited: 'Unlimited',
        locationLabel: 'Location',
        locationPlaceholder: 'Enter location',
        maintenanceLabel: 'Maintenance',
        maintenancePlaceholder: 'Enter cost',
        institutionLabel: 'Institution',
        institutionPlaceholder: 'Enter institution',
        interestRateLabel: 'Interest Rate',
        interestRatePlaceholder: 'Enter rate',
        maturityDateLabel: 'Maturity Date',
        maturityDatePlaceholder: 'Select date',
        maturityPickerTitle: 'Select date',
        warrantyExpiryLabel: 'Warranty Expiry',
        warrantyExpiryPlaceholder: 'Select date',
        warrantyPickerTitle: 'Select date',
        tagsLabel: 'Tags',
        notesLabel: 'Notes',
        notesPlaceholder: 'Enter notes',
        uploadFailed: 'Upload failed',
      },
      asset: {
        addAsset: 'Add Asset',
        editAsset: 'Edit Asset',
        inUse: 'In Use',
        idle: 'Idle',
        sold: 'Sold',
        retired: 'Retired',
      },
      iconPicker: {
        changeIcon: 'Change Icon',
      },
    },
  },
})

const mockCategories: Category[] = [
  { id: 'cat-1', name: 'Electronics', icon: 'electronics', color: '#fff', asset_type: 'physical', family_id: null, sort_order: 0, is_system: false },
  { id: 'cat-2', name: 'Furniture', icon: 'furniture', color: '#fff', asset_type: 'physical', family_id: null, sort_order: 0, is_system: false },
  { id: 'cat-3', name: 'Bank Account', icon: 'bank', color: '#fff', asset_type: 'financial', family_id: null, sort_order: 0, is_system: false },
]

function mountForm(props: Record<string, unknown> = {}) {
  return mount(AssetForm, {
    props: {
      categories: mockCategories,
      ...props,
    },
    global: {
      plugins: [createPinia(), i18n],
      stubs: {
        teleport: true,
        VanForm: { template: '<form><slot /></form>' },
        VanField: {
          template: '<div class="van-field"><label v-if="label">{{ label }}</label><input :name="$attrs.name" :required="$attrs.required" :value="$attrs.modelValue" /></div>',
          inheritAttrs: true,
        },
        VanCellGroup: { template: '<div class="van-cell-group"><slot /></div>' },
        VanCell: { template: '<div class="van-cell"><slot /></div>' },
        VanCollapse: {
          template: '<div class="van-collapse"><slot /></div>',
          props: ['modelValue'],
          emits: ['update:modelValue'],
        },
        VanCollapseItem: {
          template: '<div class="van-collapse-item" :name="$attrs.name"><slot /></div>',
          inheritAttrs: true,
        },
        VanButton: { template: '<button><slot /></button>' },
        VanIcon: { template: '<i />' },
        VanPopup: { template: '<div class="van-popup"><slot /></div>' },
        VanDatePicker: { template: '<div class="van-date-picker" />' },
        VanPicker: { template: '<div class="van-picker" />' },
        VanLoading: { template: '<div class="van-loading" />' },
        CurrencyButton: { template: '<button class="currency-btn" />' },
        UsageFreqSelector: { template: '<div class="usage-freq" />' },
        TagSelector: { template: '<div class="tag-selector" />' },
        SvgIcon: { template: '<i />' },
        IconPicker: { template: '<div class="icon-picker-stub" />' },
      },
    },
  })
}

describe('AssetForm - Collapsible Sections', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders basic info section always visible', () => {
    const wrapper = mountForm()
    const html = wrapper.html()
    expect(html).toContain('Basic Info')
    expect(html).toContain('Name')
    expect(html).toContain('Purchase Price')
  })

  it('shows physical section when asset_type is physical', async () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'physical' },
    })
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('Physical Info')
    expect(html).toContain('Location')
  })

  it('hides physical section when asset_type is financial', async () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'financial' },
    })
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).not.toContain('Physical Info')
    expect(html).toContain('Financial Info')
  })

  it('shows financial section when asset_type is financial', async () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'financial' },
    })
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('Financial Info')
    expect(html).toContain('Institution')
  })

  it('shows warranty section when asset_type is physical', async () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'physical' },
    })
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('Warranty Info')
  })

  it('hides warranty section when asset_type is financial', async () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'financial' },
    })
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).not.toContain('Warranty Info')
  })

  it('shows tags & notes section always', () => {
    const wrapper = mountForm()
    const html = wrapper.html()
    expect(html).toContain('Tags &amp; Notes')
    expect(html).toContain('Notes')
  })

  it('auto-expands physical section when switching from financial to physical', async () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'financial' },
    })
    await wrapper.vm.$nextTick()

    // Initially financial - no physical section
    expect(wrapper.html()).not.toContain('Physical Info')

    // Simulate type change by calling onTypeChange through the component
    // We need to access the component's internal method
    const vm = wrapper.vm as unknown as { onTypeChange: (type: 'physical' | 'financial') => void }
    vm.onTypeChange('physical')
    await wrapper.vm.$nextTick()

    // Now physical section should be visible
    expect(wrapper.html()).toContain('Physical Info')
  })

  it('auto-expands physical section in edit mode when asset has physical data', async () => {
    const wrapper = mountForm({
      initialData: {
        asset_type: 'physical',
        location: 'Living Room',
      },
      isEdit: true,
    })
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('Physical Info')
    expect(html).toContain('Warranty Info')
  })

  it('auto-expands warranty section in edit mode when warranty date exists', async () => {
    const wrapper = mountForm({
      initialData: {
        asset_type: 'physical',
        warranty_expiry_date: '2025-12-31',
      },
      isEdit: true,
    })
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('Warranty Info')
  })

  it('auto-expands tags & notes section in edit mode when notes exist', async () => {
    const wrapper = mountForm({
      initialData: {
        notes: 'Some notes',
      },
      isEdit: true,
    })
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('Tags &amp; Notes')
  })

  it('auto-expands financial section in edit mode when asset_type is financial', async () => {
    const wrapper = mountForm({
      initialData: {
        asset_type: 'financial',
        institution: 'Bank of China',
      },
      isEdit: true,
    })
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('Financial Info')
  })
})

describe('AssetForm - Required Field Markers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('marks name field as required', () => {
    const wrapper = mountForm()
    const nameInput = wrapper.find('input[name="name"]')
    expect(nameInput.exists()).toBe(true)
    expect(nameInput.attributes('required')).toBeDefined()
  })

  it('marks purchase_price field as required', () => {
    const wrapper = mountForm()
    const priceInput = wrapper.find('input[name="purchase_price"]')
    expect(priceInput.exists()).toBe(true)
    expect(priceInput.attributes('required')).toBeDefined()
  })

  it('marks current_value field as required', () => {
    const wrapper = mountForm()
    const valueInput = wrapper.find('input[name="current_value"]')
    expect(valueInput.exists()).toBe(true)
    expect(valueInput.attributes('required')).toBeDefined()
  })

  it('marks purchase_date field as required', () => {
    const wrapper = mountForm()
    const dateInput = wrapper.find('input[name="purchase_date"]')
    expect(dateInput.exists()).toBe(true)
    expect(dateInput.attributes('required')).toBeDefined()
  })

  it('does not mark location field as required', () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'physical' },
    })
    const locationInput = wrapper.find('input[name="location"]')
    if (locationInput.exists()) {
      expect(locationInput.attributes('required')).toBeUndefined()
    }
  })

  it('does not mark notes field as required', () => {
    const wrapper = mountForm()
    const notesInput = wrapper.find('input[name="notes"]')
    if (notesInput.exists()) {
      expect(notesInput.attributes('required')).toBeUndefined()
    }
  })
})

describe('AssetForm - Validation Failure Navigation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('has onValidationFailed method that expands section and scrolls to field', async () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'financial' },
    })
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown as {
      onValidationFailed: (args: { errors: Array<{ name?: string; message: string }> }) => Promise<void>
      expandedSections: string[]
    }

    // Initially financial section is auto-expanded by watch
    expect(vm.expandedSections).toContain('financial')

    // Clear it to test validation failure expansion
    vm.expandedSections = []
    await wrapper.vm.$nextTick()

    // Simulate validation failure on a physical field
    await vm.onValidationFailed({
      errors: [{ name: 'location', message: 'Location is required' }],
    })
    await wrapper.vm.$nextTick()

    // Physical section should now be expanded
    expect(vm.expandedSections).toContain('physical')
  })

  it('expands warranty section on validation failure for warranty field', async () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'physical' },
    })
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown as {
      onValidationFailed: (args: { errors: Array<{ name?: string; message: string }> }) => Promise<void>
      expandedSections: string[]
    }

    await vm.onValidationFailed({
      errors: [{ name: 'warranty_expiry_date', message: 'Warranty date is required' }],
    })
    await wrapper.vm.$nextTick()

    expect(vm.expandedSections).toContain('warranty')
  })

  it('expands tagsNotes section on validation failure for notes field', async () => {
    const wrapper = mountForm()
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown as {
      onValidationFailed: (args: { errors: Array<{ name?: string; message: string }> }) => Promise<void>
      expandedSections: string[]
    }

    await vm.onValidationFailed({
      errors: [{ name: 'notes', message: 'Notes are required' }],
    })
    await wrapper.vm.$nextTick()

    expect(vm.expandedSections).toContain('tagsNotes')
  })

  it('expands financial section on validation failure for financial field', async () => {
    const wrapper = mountForm({
      initialData: { asset_type: 'financial' },
    })
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown as {
      onValidationFailed: (args: { errors: Array<{ name?: string; message: string }> }) => Promise<void>
      expandedSections: string[]
    }

    await vm.onValidationFailed({
      errors: [{ name: 'institution', message: 'Institution is required' }],
    })
    await wrapper.vm.$nextTick()

    expect(vm.expandedSections).toContain('financial')
  })

  it('does not expand any section for basic info field validation failure', async () => {
    const wrapper = mountForm()
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown as {
      onValidationFailed: (args: { errors: Array<{ name?: string; message: string }> }) => Promise<void>
      expandedSections: string[]
    }

    // Default asset_type is 'physical', so physical section is auto-expanded by watch
    // Clear it to test that basic info validation doesn't expand any section
    vm.expandedSections = []
    await wrapper.vm.$nextTick()

    await vm.onValidationFailed({
      errors: [{ name: 'name', message: 'Name is required' }],
    })
    await wrapper.vm.$nextTick()

    // Basic info fields don't need section expansion
    expect(vm.expandedSections).toEqual([])
  })

  it('handles empty errors array gracefully', async () => {
    const wrapper = mountForm()
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown as {
      onValidationFailed: (args: { errors: Array<{ name?: string; message: string }> }) => Promise<void>
      expandedSections: string[]
    }

    await vm.onValidationFailed({ errors: [] })
    await wrapper.vm.$nextTick()

    expect(vm.expandedSections).toEqual([])
  })

  it('handles error without name gracefully', async () => {
    const wrapper = mountForm()
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as unknown as {
      onValidationFailed: (args: { errors: Array<{ name?: string; message: string }> }) => Promise<void>
      expandedSections: string[]
    }

    await vm.onValidationFailed({
      errors: [{ message: 'Some error' }],
    })
    await wrapper.vm.$nextTick()

    expect(vm.expandedSections).toEqual([])
  })
})
