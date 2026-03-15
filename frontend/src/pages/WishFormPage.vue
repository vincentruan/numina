<template>
  <div class="wish-form-page">
    <van-nav-bar
      :title="isEdit ? '编辑心愿' : '添加心愿'"
      left-arrow
      @click-left="$router.back()"
      :right-text="isEdit ? '删除' : ''"
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
          v-model="priceStr"
          name="expected_price"
          label="预期价格"
          type="number"
          placeholder="可选"
        />
        <van-field
          v-model="form.target_date"
          name="target_date"
          label="目标日期"
          placeholder="可选，点击选择"
          readonly
          @click="showCalendar = true"
        />
        <van-field label="优先级" name="priority">
          <template #input>
            <van-rate
              v-model="form.priority"
              :count="5"
              color="#ffd21e"
              void-icon="star"
              void-color="#eee"
            />
          </template>
        </van-field>
        <van-field
          v-model="form.notes"
          name="notes"
          label="备注"
          type="textarea"
          placeholder="可选"
          rows="3"
          autosize
        />
      </van-cell-group>

      <div style="margin: 16px">
        <van-button round block type="primary" native-type="submit" :loading="submitting">
          {{ isEdit ? '保存' : '添加' }}
        </van-button>
      </div>
    </van-form>

    <van-calendar v-model:show="showCalendar" @confirm="onDateConfirm" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { getWish, createWish, updateWish, deleteWish } from '@/api/wishes'

const route = useRoute()
const router = useRouter()

const wishId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => !!wishId.value)

const form = ref({
  name: '',
  expected_price: undefined as number | undefined,
  target_date: undefined as string | undefined,
  priority: 3,
  notes: '',
})
const priceStr = ref('')
const showCalendar = ref(false)
const submitting = ref(false)

function onDateConfirm(date: Date) {
  form.value.target_date = date.toISOString().slice(0, 10)
  showCalendar.value = false
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
  if (isEdit.value) {
    const res = await getWish(wishId.value!)
    const w = res.data
    form.value = {
      name: w.name,
      expected_price: w.expected_price,
      target_date: w.target_date,
      priority: w.priority,
      notes: w.notes ?? '',
    }
    priceStr.value = w.expected_price != null ? String(w.expected_price) : ''
  }
})
</script>
