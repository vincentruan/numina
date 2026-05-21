<template>
  <div class="coin-rates-page">
    <PageHeader :title="t('settings.coinRatesPageTitle')" />
    <div class="rates-content">
      <!-- Copper to Silver -->
      <div class="rate-row">
        <div class="rate-label">{{ t('settings.copperToSilverRate') }}</div>
        <div class="rate-controls">
          <CoinSlider
            v-model="copperToSilver"
            coin-type="silver"
            class="slider"
          />
          <van-field
            v-model="copperToSilverStr"
            type="digit"
            class="rate-input"
            :error="copperToSilverError"
            @update:model-value="onCopperInput"
          />
        </div>
      </div>

      <!-- Silver to Gold -->
      <div class="rate-row">
        <div class="rate-label">{{ t('settings.silverToGoldRate') }}</div>
        <div class="rate-controls">
          <CoinSlider
            v-model="silverToGold"
            coin-type="gold"
            class="slider"
          />
          <van-field
            v-model="silverToGoldStr"
            type="digit"
            class="rate-input"
            :error="silverToGoldError"
            @update:model-value="onSilverInput"
          />
        </div>
      </div>
    </div>

    <div class="save-action">
      <van-button
        block
        type="primary"
        :loading="saving"
        :disabled="copperToSilverError || silverToGoldError"
        @click="saveRates"
      >
        {{ t('common.save') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { useFamilyStore } from '@/stores/family'
import { getFamilySettings, updateFamilySettings } from '@/api/family'
import PageHeader from '@/components/common/PageHeader.vue'
import CoinSlider from '@/components/coins/CoinSlider.vue'

const { t } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()

const copperToSilver = ref(10)
const silverToGold = ref(10)
const copperToSilverStr = ref('10')
const silverToGoldStr = ref('10')
const copperToSilverError = ref(false)
const silverToGoldError = ref(false)
const saving = ref(false)

onMounted(async () => {
  try {
    const res = await getFamilySettings()
    copperToSilver.value = res.data.coin_copper_to_silver
    silverToGold.value = res.data.coin_silver_to_gold
    copperToSilverStr.value = String(copperToSilver.value)
    silverToGoldStr.value = String(silverToGold.value)
  } catch {
    showToast(t('toast.loadFailed'))
  }
})

// Sync slider → input string
watch(copperToSilver, (val) => {
  copperToSilverStr.value = String(val)
  copperToSilverError.value = false
})
watch(silverToGold, (val) => {
  silverToGoldStr.value = String(val)
  silverToGoldError.value = false
})

function onCopperInput(val: string) {
  const num = parseInt(val)
  if (isNaN(num) || num < 1 || num > 10) {
    copperToSilverError.value = true
  } else {
    copperToSilverError.value = false
    copperToSilver.value = num
  }
}

function onSilverInput(val: string) {
  const num = parseInt(val)
  if (isNaN(num) || num < 1 || num > 10) {
    silverToGoldError.value = true
  } else {
    silverToGoldError.value = false
    silverToGold.value = num
  }
}

async function saveRates() {
  if (copperToSilverError.value || silverToGoldError.value) {
    showToast(t('toast.coinRateInvalid'))
    return
  }
  saving.value = true
  try {
    await updateFamilySettings({
      coinCopperToSilver: copperToSilver.value,
      coinSilverToGold: silverToGold.value,
    })
    familyStore.coinCopperToSilver = copperToSilver.value
    familyStore.coinSilverToGold = silverToGold.value
    showToast(t('toast.saveSuccess'))
    router.back()
  } catch {
    showToast(t('toast.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.coin-rates-page {
  min-height: 100vh;
  background: var(--bg-secondary);
}

.rates-content {
  padding: 16px;
}

.rate-row {
  background: var(--bg-card);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.rate-label {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
  color: var(--text-primary);
}

.rate-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider {
  flex: 1;
}

.rate-input {
  width: 60px;
  flex-shrink: 0;
}

.rate-input :deep(.van-field__control) {
  text-align: center;
}

.save-action {
  padding: 16px;
}
</style>