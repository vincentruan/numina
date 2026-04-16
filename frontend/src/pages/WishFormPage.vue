<template>
  <div class="wish-form-page">
    <van-nav-bar
      :title="isEdit ? '编辑心愿' : '添加心愿'"
      left-arrow
      :right-text="isEdit ? '删除' : ''"
      @click-left="$router.back()"
      @click-right="onDelete"
    />

    <van-form @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="form.name"
          name="name"
          label="名称"
          placeholder="请输入心愿名称"
          :rules="[{ required: true, message: '请填写名称' }]"
        />
        <van-field
          v-model="form.description"
          name="description"
          label="描述"
          type="textarea"
          placeholder="可选，详细描述心愿内容"
          rows="2"
          autosize
        />
        <van-field
          v-model="priceStr"
          name="expected_price"
          label="预期价格"
          type="number"
          inputmode="decimal"
          placeholder="可选，单位：元"
        >
          <template #left-icon>
            <CurrencyButton v-model="form.currency" />
          </template>
        </van-field>
        <van-field label="优先级" name="priority">
          <template #input>
            <van-radio-group v-model="form.priority" direction="horizontal">
              <van-radio name="low">低</van-radio>
              <van-radio name="medium">中</van-radio>
              <van-radio name="high">高</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <van-field
          v-model="selectedCategoryName"
          name="category"
          label="分类"
          placeholder="可选，点击选择"
          readonly
          @click="showCategoryPicker = true"
        />
      </van-cell-group>

      <div style="margin: 16px">
        <van-button round block type="primary" native-type="submit" :loading="submitting">
          {{ isEdit ? '保存' : '添加' }}
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { getWish, createWish, updateWish, deleteWish } from '@/api/wishes'
import { getCategories } from '@/api/categories'
import type { Category } from '@/types'
import CurrencyButton from '@/components/common/CurrencyButton.vue'
import { useAuthStore } from '@/stores/auth'

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
})
const priceStr = ref('')
const submitting = ref(false)
const showCategoryPicker = ref(false)
const categories = ref<Category[]>([])

const categoryColumns = computed(() => {
  return categories.value.map(c => ({ text: `${c.icon} ${c.name}`, value: c.id }))
})

const selectedCategoryName = computed(() => {
  if (!form.value.category_id) return ''
  const cat = categories.value.find(c => c.id === form.value.category_id)
  return cat ? `${cat.icon} ${cat.name}` : ''
})

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
    }
    if (isEdit.value) {
      await updateWish(wishId.value!, payload)
      showToast('已保存')
    } else {
      await createWish(payload)
      showToast('已添加')
    }
    router.back()
  } finally {
    submitting.value = false
  }
}

async function onDelete() {
  if (!isEdit.value) return
  await showConfirmDialog({ title: '确认删除', message: '删除后无法恢复' })
  await deleteWish(wishId.value!)
  showToast('已删除')
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
      expected_price: w.expected_price,
      currency: w.currency || authStore.user?.default_currency || 'CNY',
      priority: w.priority,
      category_id: w.category_id,
    }
    priceStr.value = w.expected_price != null ? String(w.expected_price) : ''
  }
})
</script>