import { defineStore } from 'pinia'
import { ref } from 'vue'
import { blindBoxApi, childBlindBoxApi } from '@/api/blindBox'
import type {
  BlindBoxGift,
  BlindBoxGiftCreate,
  BlindBoxGiftUpdate,
  BlindBoxDraw,
  DrawRequest,
  BlindBoxConfig,
  BlindBoxConfigUpdate,
  BonusDraw,
} from '@/types/blindBox'

export const useBlindBoxStore = defineStore('blindBox', () => {
  // ── State ──────────────────────────────────────────────────────────────────
  const gifts = ref<BlindBoxGift[]>([])
  const draws = ref<BlindBoxDraw[]>([])
  const config = ref<BlindBoxConfig | null>(null)
  const bonusDraws = ref<BonusDraw[]>([])
  const loading = ref(false)
  const lastDraw = ref<BlindBoxDraw | null>(null)

  // ── Parent Actions ─────────────────────────────────────────────────────────

  async function fetchGifts() {
    loading.value = true
    try {
      const res = await blindBoxApi.listGifts()
      gifts.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function createGift(data: BlindBoxGiftCreate) {
    const res = await blindBoxApi.createGift(data)
    gifts.value.unshift(res.data)
    return res.data
  }

  async function updateGift(id: number, data: BlindBoxGiftUpdate) {
    const res = await blindBoxApi.updateGift(id, data)
    const idx = gifts.value.findIndex((g) => g.id === id)
    if (idx !== -1) gifts.value[idx] = res.data
    return res.data
  }

  async function deleteGift(id: number) {
    await blindBoxApi.deleteGift(id)
    gifts.value = gifts.value.filter((g) => g.id !== id)
  }

  async function fetchDraws() {
    const res = await blindBoxApi.listDraws()
    draws.value = res.data
  }

  async function fulfillDraw(id: number) {
    const res = await blindBoxApi.fulfillDraw(id)
    const idx = draws.value.findIndex((d) => d.id === id)
    if (idx !== -1) draws.value[idx] = res.data
  }

  async function fetchConfig() {
    const res = await blindBoxApi.getConfig()
    config.value = res.data
  }

  async function updateConfig(data: BlindBoxConfigUpdate) {
    const res = await blindBoxApi.updateConfig(data)
    config.value = res.data
  }

  async function createGiftFromWish(wishId: number) {
    const res = await blindBoxApi.createGiftFromWish(wishId)
    gifts.value.unshift(res.data)
    return res.data
  }

  // ── Child Actions ──────────────────────────────────────────────────────────

  async function childDraw(data: DrawRequest) {
    loading.value = true
    try {
      const res = await childBlindBoxApi.draw(data)
      lastDraw.value = res.data
      draws.value.unshift(res.data)
      return res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchChildDraws() {
    loading.value = true
    try {
      const res = await childBlindBoxApi.listDraws()
      draws.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchBonusDraws() {
    loading.value = true
    try {
      const res = await childBlindBoxApi.listBonusDraws()
      bonusDraws.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function useBonusDraw(bonusId: number) {
    loading.value = true
    try {
      const res = await childBlindBoxApi.useBonusDraw(bonusId)
      lastDraw.value = res.data
      draws.value.unshift(res.data)
      bonusDraws.value = bonusDraws.value.filter((b) => b.id !== bonusId)
      return res.data
    } finally {
      loading.value = false
    }
  }

  function clearLastDraw() {
    lastDraw.value = null
  }

  return {
    gifts,
    draws,
    config,
    bonusDraws,
    loading,
    lastDraw,
    fetchGifts,
    createGift,
    updateGift,
    deleteGift,
    fetchDraws,
    fulfillDraw,
    fetchConfig,
    updateConfig,
    createGiftFromWish,
    childDraw,
    fetchChildDraws,
    fetchBonusDraws,
    useBonusDraw,
    clearLastDraw,
  }
})
