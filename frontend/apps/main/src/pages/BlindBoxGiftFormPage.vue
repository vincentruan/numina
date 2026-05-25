<template>
  <div class="blind-box-gift-form-page">
    <van-nav-bar
      :title="isEdit ? t('blindBox.editGiftTitle') : t('blindBox.addGiftTitle')"
      left-arrow
      @click-left="$router.back()"
    />

    <van-form @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="form.name"
          name="name"
          :label="t('blindBox.giftNameLabel')"
          :placeholder="t('blindBox.giftNamePlaceholder')"
          :rules="[{ required: true, message: t('blindBox.giftNameRequired') }]"
        />
        <van-field
          v-model="form.emoji"
          name="emoji"
          :label="t('blindBox.emojiLabel')"
          :placeholder="t('blindBox.emojiPlaceholder')"
        />
        <van-field
          v-model="form.description"
          name="description"
          :label="t('blindBox.descLabel')"
          type="textarea"
          :placeholder="t('blindBox.descPlaceholder')"
          rows="2"
          autosize
        />
        <van-field
          v-model.number="form.value_score"
          name="value_score"
          :label="t('blindBox.valueScoreLabel')"
          type="number"
          :placeholder="t('blindBox.valueScorePlaceholder')"
          :rules="[
            { required: true, message: t('blindBox.valueScoreRequired') },
            { validator: (v) => Number(v) >= 1 && Number(v) <= 10, message: t('blindBox.valueScoreRange') },
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
          {{ isEdit ? t('blindBox.saveBtn') : t('blindBox.addBtn') }}
        </van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useBlindBoxStore } from '@/stores/blindBox'
import { storeToRefs } from 'pinia'

const { t } = useI18n()
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
    const gift = gifts.value.find((g) => g.id === route.params.id)
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
      await store.updateGift(route.params.id as string, {
        name: form.name,
        emoji: form.emoji || null,
        description: form.description || null,
        value_score: form.value_score,
      })
      showToast(t('toast.saveSuccess'))
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
        showToast(t('toast.addSuccess'))
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
