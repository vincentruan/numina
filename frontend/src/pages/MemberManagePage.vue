<template>
  <div class="member-manage-page">
    <PageHeader title="成员管理" />

    <van-cell-group inset>
      <van-swipe-cell v-for="member in familyStore.members" :key="member.id">
        <van-cell :title="member.display_name" :label="'@' + member.username">
          <template #icon>
            <div class="avatar" :style="{ background: member.avatar_color || '#1989fa' }">
              {{ member.display_name.charAt(0) }}
            </div>
          </template>
          <template #value>
            <van-tag :type="member.role === 'owner' ? 'primary' : 'default'" size="medium">
              {{ member.role === 'owner' ? '管理员' : '成员' }}
            </van-tag>
          </template>
        </van-cell>
        <template #right>
          <van-button
            v-if="member.id !== currentUserId && member.role !== 'owner'"
            square
            type="primary"
            text="设为管理员"
            class="swipe-btn"
            @click="onSetOwner(member.id)"
          />
          <van-button
            v-if="member.id !== currentUserId"
            square
            type="danger"
            text="移除"
            class="swipe-btn"
            @click="onRemove(member)"
          />
        </template>
      </van-swipe-cell>
    </van-cell-group>

    <!-- Regenerate Invite Code -->
    <div class="actions">
      <van-button block plain type="primary" @click="onRegenerate" :loading="regenerating">
        重新生成邀请码
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'

const familyStore = useFamilyStore()
const authStore = useAuthStore()
const regenerating = ref(false)

const currentUserId = computed(() => authStore.user?.id)

async function onSetOwner(userId: string) {
  try {
    await showConfirmDialog({ title: '确认', message: '确定要将该成员设为管理员吗？' })
    await familyStore.updateMemberRole(userId, 'owner')
    showToast('已设为管理员')
  } catch {
    // cancelled
  }
}

async function onRemove(member: User) {
  try {
    await showConfirmDialog({ title: '确认移除', message: `确定要移除「${member.display_name}」吗？` })
    await familyStore.removeMember(member.id)
    showToast('已移除')
  } catch {
    // cancelled
  }
}

async function onRegenerate() {
  try {
    await showConfirmDialog({ title: '确认', message: '重新生成邀请码后，旧邀请码将失效' })
    regenerating.value = true
    const code = await familyStore.regenerateInviteCode()
    showToast(`新邀请码: ${code}`)
  } catch {
    // cancelled
  } finally {
    regenerating.value = false
  }
}

onMounted(() => {
  familyStore.fetchMembers()
})
</script>

<style scoped>
.member-manage-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  margin-right: 10px;
}
.swipe-btn {
  height: 100%;
}
.actions {
  padding: 24px 16px;
}
</style>
