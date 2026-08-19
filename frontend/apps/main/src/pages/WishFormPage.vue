<template>
  <div class="wish-form-page">
    <van-nav-bar
      :title="isEdit ? t('wish.form.editTitle') : t('wish.form.addTitle')"
      left-arrow
      :right-text="isEdit ? t('wish.form.deleteBtn') : ''"
      @click-left="$router.back()"
      @click-right="onDelete"
    />

    <van-form @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="form.name"
          name="name"
          :label="t('wish.form.nameLabel')"
          :placeholder="t('wish.form.namePlaceholder')"
          :rules="[{ required: true, message: t('wish.form.nameRequired') }]"
        />
        <van-field
          v-model="form.description"
          name="description"
          :label="t('wish.form.descriptionLabel')"
          type="textarea"
          :placeholder="t('wish.form.descriptionPlaceholder')"
          rows="2"
          autosize
        />
        <van-field
          v-model="priceStr"
          name="expected_price"
          :label="t('wish.form.priceLabel')"
          type="number"
          inputmode="decimal"
          :placeholder="t('wish.form.pricePlaceholder')"
        >
          <template #left-icon>
            <CurrencyButton v-model="form.currency" />
          </template>
        </van-field>
        <van-field :label="t('wish.form.priorityLabel')" name="priority">
          <template #input>
            <van-radio-group v-model="form.priority" direction="horizontal">
              <van-radio name="low">{{ t('wish.priorityLow') }}</van-radio>
              <van-radio name="medium">{{ t('wish.priorityMedium') }}</van-radio>
              <van-radio name="high">{{ t('wish.priorityHigh') }}</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <!-- W1 (Plan B T9): savings plan group. -->
        <van-field
          v-model="monthlySavingStr"
          name="monthly_saving"
          :label="t('wish.form.monthlySavingLabel')"
          type="number"
          inputmode="decimal"
          :placeholder="t('wish.form.monthlySavingPlaceholder')"
        />
        <van-field
          :model-value="form.target_date"
          readonly
          name="target_date"
          :label="t('wish.form.targetDateLabel')"
          :placeholder="t('wish.form.targetDatePlaceholder')"
          @click="showDatePicker = true"
        />
        <van-field
          name="category"
          :label="t('wish.form.categoryLabel')"
          :placeholder="t('wish.form.categoryPlaceholder')"
          readonly
          @click="showCategoryPicker = true"
        >
          <template #input>
            <div v-if="selectedCategory" class="category-display">
              <SvgIcon :name="getIconId(selectedCategory.icon)" class="cat-icon-sm" />
              <span>{{ selectedCategory.name }}</span>
            </div>
            <span v-else class="category-placeholder">{{ t('wish.form.categoryPlaceholder') }}</span>
          </template>
        </van-field>
        <van-field name="converts_to_asset" class="converts-field">
          <template #label>
            <span class="converts-label">{{ t('toast.wishConvertsToAsset') }}</span>
          </template>
          <template #input>
            <div class="converts-row">
              <van-switch v-model="form.converts_to_asset" size="20" />
              <span v-if="!form.converts_to_asset" class="field-hint">{{ t('toast.wishConvertsToAssetHint') }}</span>
            </div>
          </template>
        </van-field>
      </van-cell-group>

      <div style="margin: 16px">
        <van-button round block type="primary" native-type="submit" :loading="submitting">
          {{ isEdit ? t('wish.form.saveBtn') : t('wish.form.addBtn') }}
        </van-button>
      </div>
    </van-form>

    <!-- Category Picker -->
    <van-popup v-model:show="showCategoryPicker" round position="bottom">
      <van-picker
        :columns="categoryColumns"
        @confirm="onCategoryConfirm"
        @cancel="showCategoryPicker = false"
      />
    </van-popup>

    <!-- W1 (Plan B T9): target_date picker -->
    <van-popup v-model:show="showDatePicker" position="bottom">
      <van-date-picker
        v-model="datePickerValue"
        :min-date="new Date(2020, 0, 1)"
        :max-date="new Date(2100, 11, 31)"
        @confirm="onDateConfirm"
        @cancel="showDatePicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getWish, createWish, updateWish, deleteWish } from '@/api/wishes'
import { getCategories } from '@/api/categories'
import type { Category } from '@/types'
import CurrencyButton from '@/components/common/CurrencyButton.vue'
import { useAuthStore } from '@/stores/auth'
import { getIconId } from '@/utils/icon'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const wishId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => !!wishId.value)

const form = ref({
  name: '',
  description: '',
  expected_price: undefined as number | undefined,
  currency: authStore.user?.default_currency || 'CNY',
  priority: 'medium',
  category_id: undefined as string | undefined,
  converts_to_asset: true,
  // W1 (Plan B T9): savings plan fields. saved_amount is NOT in the form
  // (initial 0, spec §2.3); the backend derives it from savings log.
  monthly_saving: undefined as number | undefined,
  target_date: undefined as string | undefined,
})
const priceStr = ref('')
const monthlySavingStr = ref('')
const submitting = ref(false)
const showCategoryPicker = ref(false)
const showDatePicker = ref(false)
const datePickerValue = ref<string[]>([])
const categories = ref<Category[]>([])

const categoryColumns = computed(() => {
  return categories.value.map(c => ({ text: c.name, value: c.id }))
})

const selectedCategory = computed(() =>
  categories.value.find(c => c.id === form.value.category_id) ?? null
)

function onCategoryConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  form.value.category_id = selectedOptions[0].value
  showCategoryPicker.value = false
}

async function onSubmit() {
  submitting.value = true
  try {
    const payload = {
      ...form.value,
      expected_price: priceStr.value ? parseFloat(priceStr.value) : undefined,
      monthly_saving: monthlySavingStr.value ? parseFloat(monthlySavingStr.value) : undefined,
      target_date: form.value.target_date || undefined,
    }
    if (isEdit.value) {
      await updateWish(wishId.value!, payload)
      showSuccessToast(t('toast.wishSaved'))
    } else {
      await createWish(payload)
      showSuccessToast(t('toast.wishAdded'))
    }
    if (!isEdit.value) {
      router.replace({ path: '/finance', query: { tab: 'wishes' } })
    } else {
      router.back()
    }
  } finally {
    submitting.value = false
  }
}

async function onDelete() {
  if (!isEdit.value) return
  await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmDeleteIrrevocable') })
  await deleteWish(wishId.value!)
  showSuccessToast(t('toast.deleteSuccess'))
  router.back()
}

onMounted(async () => {
  // Load categories
  const catRes = await getCategories()
  categories.value = catRes.data

  if (isEdit.value) {
    const res = await getWish(wishId.value!)
    const w = res.data
    form.value = {
      name: w.name,
      description: w.description ?? '',
      expected_price: w.expected_price != null ? Number(w.expected_price) : undefined,
      currency: w.currency || authStore.user?.default_currency || 'CNY',
      priority: w.priority,
      category_id: w.category_id,
      converts_to_asset: w.converts_to_asset,
      monthly_saving: w.monthly_saving ? Number(w.monthly_saving) : undefined,
      target_date: w.target_date ?? undefined,
    }
    priceStr.value = w.expected_price != null ? String(w.expected_price) : ''
    monthlySavingStr.value = w.monthly_saving ? String(w.monthly_saving) : ''
    if (w.target_date) {
      form.value.target_date = w.target_date
      datePickerValue.value = w.target_date.split('-')
    }
  }
})

// W1 (Plan B T9): target_date picker confirm.
function onDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.target_date = selectedValues.join('-')
  showDatePicker.value = false
}
</script>

<style scoped>
.category-display {
  display: flex;
  align-items: center;
  gap: 6px;
}
.cat-icon-sm {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  fill: currentColor;
}
.category-placeholder {
  color: var(--van-field-placeholder-text-color);
  font-size: 14px;
}
.converts-label {
  font-size: 14px;
  color: var(--van-field-label-color);
}
.converts-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
}
.field-hint {
  font-size: 12px;
  color: var(--van-text-color-3, rgba(0, 0, 0, 0.4));
  white-space: normal;
  line-height: 1.4;
}
</style>