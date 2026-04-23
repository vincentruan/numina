<template>
  <div class="blind-box-gift-form-page">
    <van-nav-bar
      :title="isEdit ? '编辑礼物' : '添加礼物'"
      left-arrow
      @click-left="$router.back()"
    />

    <van-form @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="form.name"
          name="name"
          label="礼物名称"
          placeholder="例如：乐高积木"
          :rules="[{ required: true, message: '请输入礼物名称' }]"
        />
        <van-field
          v-model="form.emoji"
          name="emoji"
          label="表情符号"
          placeholder="例如：🧱（可选）"
        />
        <van-field
          v-model="form.description"
          name="description"
          label="描述"
          type="textarea"
          placeholder="礼物描述（可选）"
          rows="2"
          autosize
        />
        <van-field
          v-model.number="form.value_score"
          name="value_score"
          label="价值分 (1-10)"
          type="number"
          placeholder="1=最容易抽到，10=最稀有"
          :rules="[
            { required: true, message: '请输入价值分' },
            { validator: (v) => Number(v) >= 1 && Number(v) <= 10, message: '价值分须在 1-10 之间' },
          ]"
        />
      </van-cell-group>

      <div class="form-footer">
        <van-button
          round
          block
          type="primary"
          native-type="submit"
          :loading="loading"
        >
          {{ isEdit ? '保存修改' : '添加礼物' }}
        </van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useBlindBoxStore } from '@/stores/blindBox'
import { storeToRefs } from 'pinia'

const route = useRoute()
const router = useRouter()
const store = useBlindBoxStore()
const { gifts } = storeToRefs(store)

const isEdit = computed(() => !!route.params.id)
const loading = ref(false)

const form = reactive({
  name: '',
  emoji: '',
  description: '',
  value_score: 5,
})

onMounted(async () => {
  if (isEdit.value) {
    await store.fetchGifts()
    const gift = gifts.value.find((g) => g.id === Number(route.params.id))
    if (gift) {
      form.name = gift.name
      form.emoji = gift.emoji ?? ''
      form.description = gift.description ?? ''
      form.value_score = gift.value_score
    }
  }
})

async function onSubmit() {
  loading.value = true
  try {
    if (isEdit.value) {
      await store.updateGift(Number(route.params.id), {
        name: form.name,
        emoji: form.emoji || null,
        description: form.description || null,
        value_score: form.value_score,
      })
      showToast('✅ 已保存')
    } else {
      const result = await store.createGift({
        name: form.name,
        emoji: form.emoji || null,
        description: form.description || null,
        value_score: form.value_score,
      })
      if (result.warning) {
        showToast(`⚠️ ${result.warning}`)
      } else {
        showToast('✅ 添加成功')
      }
    }
    router.back()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.blind-box-gift-form-page {
  min-height: 100vh;
  background: var(--van-background);
}
.form-footer {
  padding: 24px 16px;
}
</style>
