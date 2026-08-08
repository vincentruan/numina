import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Family, User } from '@/types'
import * as familyApi from '@/api/family'

export const useFamilyStore = defineStore('family', () => {
  const family = ref<Family | null>(null)
  const members = ref<User[]>([])
  const loading = ref(false)

  // Coin tier exchange rates (loaded from family settings, defaults match backend)
  const coinCopperToSilver = ref(10)
  const coinSilverToGold = ref(10)
  // Education reward (family-level opt-in: convert chore star coins to yuan in activity feed)
  const educationRewardEnabled = ref(false)
  const coinToYuanRate = ref(1)
  // AI assistant master switch (family-level toggle, independent of provider configs)
  const aiEnabled = ref(false)

  async function fetchFamily() {
    loading.value = true
    try {
      const res = await familyApi.getFamily()
      family.value = res.data
      members.value = res.data.members || []
    } finally {
      loading.value = false
    }
  }

  async function fetchMembers() {
    const res = await familyApi.getMembers()
    members.value = res.data
  }

  async function loadCoinConfig() {
    try {
      const res = await familyApi.getFamilySettings()
      coinCopperToSilver.value = res.data.coin_copper_to_silver
      coinSilverToGold.value = res.data.coin_silver_to_gold
      educationRewardEnabled.value = res.data.education_reward_enabled
      coinToYuanRate.value = res.data.coin_to_yuan_rate
      aiEnabled.value = res.data.ai_enabled
    } catch {
      // Keep defaults on failure — non-critical
    }
  }

  async function regenerateInviteCode() {
    const res = await familyApi.regenerateInviteCode()
    if (family.value) {
      family.value.invite_code = res.data.invite_code
    }
    return res.data.invite_code
  }

  async function updateMemberRole(userId: string, role: 'owner' | 'member') {
    await familyApi.updateMemberRole(userId, role)
    const member = members.value.find(m => m.id === userId)
    if (member) member.role = role
  }

  async function removeMember(userId: string) {
    await familyApi.removeMember(userId)
    members.value = members.value.filter(m => m.id !== userId)
  }

  async function updateFamilyTitle(custom_title: string | null) {
    const res = await familyApi.updateFamilyTitle(custom_title)
    family.value = res.data
  }

  return {
    family, members, loading,
    coinCopperToSilver, coinSilverToGold,
    educationRewardEnabled, coinToYuanRate, aiEnabled,
    fetchFamily, fetchMembers, loadCoinConfig,
    regenerateInviteCode, updateMemberRole, removeMember, updateFamilyTitle,
  }
})
