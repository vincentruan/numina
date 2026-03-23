import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Family, User } from '@/types'
import * as familyApi from '@/api/family'

export const useFamilyStore = defineStore('family', () => {
  const family = ref<Family | null>(null)
  const members = ref<User[]>([])
  const loading = ref(false)

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

  return { family, members, loading, fetchFamily, fetchMembers, regenerateInviteCode, updateMemberRole, removeMember, updateFamilyTitle }
})
