<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showDialog, showToast } from 'vant'
import { getWishAdvice, adoptWishAdvice } from '@/api/wishes'
import { useWishStore } from '@/stores/wish'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import type { WishAdvice } from '@/types'

import AiGatedInline from '@/components/ai/AiGatedInline.vue'

const props = defineProps<{ wishes: { id: string; name: string; monthly_saving: string | number }[] }>()
const router = useRouter()
const { t } = useI18n()
const currency = useCurrency()
const wishStore = useWishStore()
const familyStore = useFamilyStore()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const advice = ref<WishAdvice | null>(null)
const visible = ref(false)
const closed = ref(false) // localStorage 8h suppression (independent of content cache)
const adopting = ref(false)

const SUPPRESSION_KEY = 'wish_advice_closed'

function fingerprintHash(): string {
  return props.wishes.map((w) => `${w.id}:${w.monthly_saving}`).join('|')
}

function isSuppressed(): boolean {
  const raw = localStorage.getItem(SUPPRESSION_KEY)
  if (!raw) return false
  try {
    const { fp, ts } = JSON.parse(raw) as { fp: string; ts: number }
    if (fp !== fingerprintHash()) return false // fingerprint changed → allow re-show
    return Date.now() - ts < 8 * 3600 * 1000
  } catch {
    return false
  }
}

function suppress(): void {
  localStorage.setItem(SUPPRESSION_KEY, JSON.stringify({ fp: fingerprintHash(), ts: Date.now() }))
  closed.value = true
}

function validateAdvice(a: WishAdvice): boolean {
  // Client-side guardrail mirror (spec §7.1): suggested_amount >= 0 per item.
  return (
    a.redistribution.every((r) => Number(r.suggested_amount) >= 0) &&
    Number(a.suggested_monthly) >= 0
  )
}

async function load(): Promise<void> {
  if (!familyStore.aiEnabled) return
  if (isSuppressed()) {
    closed.value = true
    return
  }
  try {
    const resp = await getWishAdvice(false)
    if (resp.data.status === 'cached' || resp.data.status === 'fresh') {
      if (resp.data.report && validateAdvice(resp.data.report)) {
        advice.value = resp.data.report
        visible.value = true
      }
    }
  } catch {
    /* silent */
  }
}

function onClose(): void {
  suppress()
}

async function onAdopt(): Promise<void> {
  if (!advice.value) return
  // Read-only confirmation dialog (spec §4.3 design-lens): 全部采纳 / 取消 only.
  try {
    await showDialog({
      title: t('wish.advice.adoptTitle'),
      message:
        advice.value.redistribution
          .map((r) => {
            const w = props.wishes.find((x) => x.id === r.wish_id)
            return `${w?.name ?? r.wish_id}: ${currency.format(Number(w?.monthly_saving ?? 0))} → ${currency.format(Number(r.suggested_amount))}（${r.note}）`
          })
          .join('\n') +
        `\n\n${t('wish.advice.totalMonthly', { total: advice.value.redistribution.reduce((s, r) => s + Number(r.suggested_amount), 0) })}`,
      showCancelButton: true,
      confirmButtonText: t('wish.advice.adoptAll'),
      cancelButtonText: t('common.cancel'),
    })
  } catch {
    return // cancel
  }
  adopting.value = true
  const results = await adoptWishAdvice(advice.value.redistribution)
  let ok = 0
  advice.value.redistribution.forEach((r, i) => {
    if (results[i].status === 'fulfilled') ok++
  })
  await wishStore.fetchWishes() // refresh
  if (ok === advice.value.redistribution.length) {
    showSuccessToast(t('wish.advice.allUpdated'))
    visible.value = false
    suppress()
  } else {
    showFailToast(t('wish.advice.partial', { ok, total: advice.value.redistribution.length }))
    // failed rows stay red + dialog stays open (spec §4.3)
  }
  adopting.value = false
}

function onFullAdvice(): void {
  if (!familyStore.aiEnabled) {
    showToast(t('toast.aiNotEnabled'))
    return
  }
  router.push({ name: 'AIChat', query: { source: 'wish_advice' } })
}

const shouldShow = computed(() => !closed.value && visible.value && advice.value !== null)

onMounted(() => {
  if (familyStore.aiEnabled) {
    void load()
  }
})

watch(() => familyStore.aiEnabled, (enabled) => {
  if (enabled && !advice.value) {
    void load()
  }
})
</script>

<template>
  <div v-if="!familyStore.aiEnabled" class="wish-advice-card">
    <AiGatedInline
      :title="t('wish.advice.title')"
      :is-owner="isOwner"
    />
  </div>
  <div v-else-if="shouldShow" class="wish-advice-card" data-test="wish-advice-card">
    <div class="wa-header">
      <span class="wa-title">{{ t('wish.advice.title') }}</span>
      <van-icon name="cross" data-test="wa-close" @click="onClose" />
    </div>
    <div class="wa-body">
      {{
        t('wish.advice.primary', {
          name: wishes.find((w) => w.id === advice!.primary_wish_id)?.name ?? advice!.primary_wish_id,
          amount: advice!.suggested_monthly,
        })
      }}
    </div>
    <div class="wa-reason">{{ advice!.reason }}</div>
    <div class="wa-actions">
      <van-button size="small" type="primary" :loading="adopting" data-test="wa-adopt" @click="onAdopt">
        {{ t('wish.advice.adopt') }}
      </van-button>
      <van-button size="small" plain data-test="wa-full" @click="onFullAdvice">
        {{ t('wish.advice.fullAdvice') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.wish-advice-card {
  background: var(--card-bg, #fff);
  border-radius: 12px;
  padding: 12px;
  margin: 8px 12px;
}
.wa-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.wa-title {
  font-weight: 600;
}
.wa-body {
  font-size: 14px;
  margin-bottom: 4px;
}
.wa-reason {
  font-size: 12px;
  color: var(--text-secondary, #969799);
  margin-bottom: 8px;
}
.wa-actions {
  display: flex;
  gap: 8px;
}
</style>
