<template>
  <div class="family-page">
    <PageHeader title="家庭" :show-back="false">
      <template #right>
        <van-icon name="setting-o" size="20" @click="$router.push('/settings')" />
      </template>
    </PageHeader>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <template v-if="familyStore.family">
        <!-- Family Info -->
        <van-cell-group inset class="section">
          <van-cell title="家庭名称" :value="familyStore.family.name" />
          <van-cell title="邀请码" :value="familyStore.family.invite_code" is-link @click="copyInviteCode">
            <template #right-icon>
              <van-icon name="description" />
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Members -->
        <van-cell-group inset title="家庭成员" class="section">
          <template #extra>
            <span class="member-count">{{ familyStore.members.length }} 人</span>
          </template>
          <MemberCard
            v-for="member in familyStore.members"
            :key="member.id"
            :member="member"
          />
          <van-cell v-if="isOwner" title="成员管理" is-link to="/family/members" />
        </van-cell-group>
      </template>

      <van-loading v-else class="page-loading" />
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'
import MemberCard from '@/components/family/MemberCard.vue'
import PageHeader from '@/components/common/PageHeader.vue'

const familyStore = useFamilyStore()
const authStore = useAuthStore()
const refreshing = ref(false)

const isOwner = computed(() => authStore.user?.role === 'owner')

function copyInviteCode() {
  const code = familyStore.family?.invite_code
  if (code) {
    navigator.clipboard.writeText(code).then(() => {
      showToast('邀请码已复制')
    }).catch(() => {
      showToast(`邀请码: ${code}`)
    })
  }
}

async function onRefresh() {
  await familyStore.fetchFamily()
  refreshing.value = false
}

onMounted(() => {
  familyStore.fetchFamily()
})
</script>

<style scoped>
.family-page {
  background: #f7f8fa;
  min-height: 100vh;
}
.section {
  margin-top: 12px;
}
.member-count {
  font-size: 12px;
  color: #969799;
}
.page-loading {
  display: flex;
  justify-content: center;
  padding-top: 40vh;
}
</style>
