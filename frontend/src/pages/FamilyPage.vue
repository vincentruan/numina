<template>
  <div class="family-page">
    <PageHeader :title="t('family.title')" :show-back="false">
      <template #right>
        <van-icon name="setting-o" size="20" @click="$router.push('/settings')" />
      </template>
    </PageHeader>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <template v-if="familyStore.family">
        <!-- Family Info -->
        <van-cell-group inset class="section">
          <van-cell :title="t('family.familyName')" :value="familyStore.family.custom_title || familyStore.family.name" />
          <van-cell :title="t('family.inviteCode')" :value="familyStore.family.invite_code" is-link @click="copyInviteCode">
            <template #right-icon>
              <van-icon name="description" />
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Members -->
        <van-cell-group inset :title="t('family.members')" class="section">
          <template #extra>
            <span class="member-count">{{ familyStore.members.length }} {{ t('family.memberCount') }}</span>
          </template>
          <MemberCard
            v-for="member in familyStore.members"
            :key="member.id"
            :member="member"
          />
          <van-cell v-if="isOwner" :title="t('family.memberManagement')" is-link to="/family/members" />
        </van-cell-group>

        <!-- Coin tier settings (owner only) -->
        <van-cell-group v-if="isOwner" inset title="⭐ 星星币兑换比例" class="section">
          <van-field
            v-model="copperToSilverStr"
            label="铜→银"
            type="digit"
            placeholder="默认 10"
            :rules="[{ validator: validateRate, message: '请输入 1-100 的整数' }]"
          />
          <van-field
            v-model="silverToGoldStr"
            label="银→金"
            type="digit"
            placeholder="默认 10"
            :rules="[{ validator: validateRate, message: '请输入 1-100 的整数' }]"
          />
          <van-cell>
            <template #title>
              <van-button size="small" type="primary" @click="saveCoinRates" :loading="savingRates">
                保存
              </van-button>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Children management dashboard (owner only) -->
        <div v-if="isOwner && childMembers.length > 0" class="section">
          <p class="section-heading">👧 孩子管理</p>
          <div class="child-cards">
            <div v-for="child in childMembers" :key="child.id" class="child-mgmt-card">
              <div class="child-mgmt-header">
                <span
                  class="child-avatar"
                  :style="{ background: child.avatar_color || '#f5a623' }"
                >{{ child.display_name[0] }}</span>
                <span class="child-name">{{ child.display_name }}</span>
              </div>
              <div class="child-mgmt-stats">
                <div class="stat">
                  <span class="stat-label">余额</span>
                  <span class="stat-value">{{ childBalances[child.id] ?? '…' }} ⭐</span>
                </div>
                <div class="stat">
                  <span class="stat-label">待审家务</span>
                  <span class="stat-value" :class="{ 'has-pending': totalPendingChores > 0 }">
                    {{ totalPendingChores }}
                  </span>
                </div>
                <div class="stat">
                  <span class="stat-label">待审心愿</span>
                  <span class="stat-value" :class="{ 'has-pending': totalPendingWishes > 0 }">
                    {{ totalPendingWishes }}
                  </span>
                </div>
              </div>
              <div class="child-mgmt-actions">
                <van-button size="mini" plain type="primary" to="/family/chore-approvals">审批家务</van-button>
                <van-button size="mini" plain type="primary" to="/family/wish-review">审批心愿</van-button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <van-loading v-else class="page-loading" />
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'
import MemberCard from '@/components/family/MemberCard.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import { updateFamilySettings, getChildBalance } from '@/api/family'
import { getPendingApprovals } from '@/api/chores'
import { listParentChildWishes } from '@/api/childWishes'

const { t } = useI18n()
const familyStore = useFamilyStore()
const authStore = useAuthStore()
const refreshing = ref(false)
const savingRates = ref(false)

const copperToSilverStr = ref(String(familyStore.coinCopperToSilver))
const silverToGoldStr = ref(String(familyStore.coinSilverToGold))

// Child dashboard data
const childBalances = ref<Record<string, number>>({})
const totalPendingChores = ref(0)
const totalPendingWishes = ref(0)
const isOwner = computed(() => authStore.user?.role === 'owner')
const childMembers = computed(() =>
  familyStore.members.filter(m => m.role === 'child'),
)

function validateRate(val: string) {
  const n = parseInt(val)
  return !isNaN(n) && n >= 1 && n <= 100
}

function copyInviteCode() {
  const code = familyStore.family?.invite_code
  if (code) {
    navigator.clipboard.writeText(code).then(() => {
      showToast(t('family.inviteCodeCopied'))
    }).catch(() => {
      showToast(`${t('family.inviteCode')}: ${code}`)
    })
  }
}

async function saveCoinRates() {
  const c2s = parseInt(copperToSilverStr.value)
  const s2g = parseInt(silverToGoldStr.value)
  if (!validateRate(copperToSilverStr.value) || !validateRate(silverToGoldStr.value)) {
    showToast('请输入 1-100 的整数')
    return
  }
  savingRates.value = true
  try {
    await updateFamilySettings({ coinCopperToSilver: c2s, coinSilverToGold: s2g })
    familyStore.coinCopperToSilver = c2s
    familyStore.coinSilverToGold = s2g
    showToast('已保存')
  } catch {
    showToast('保存失败')
  } finally {
    savingRates.value = false
  }
}

async function loadChildDashboard() {
  if (!isOwner.value || childMembers.value.length === 0) return

  // Load all child balances in parallel
  const balanceResults = await Promise.allSettled(
    childMembers.value.map(c => getChildBalance(c.id).then(r => ({ id: c.id, balance: r.data.balance }))),
  )
  balanceResults.forEach(r => {
    if (r.status === 'fulfilled') childBalances.value[r.value.id] = r.value.balance
  })

  // Load total pending chore approvals (family-wide)
  try {
    const choreApprovals = await getPendingApprovals()
    totalPendingChores.value = choreApprovals.length
  } catch { /* non-critical */ }

  // Load total pending wishes (pending_review + redemption_requested)
  try {
    const wishes = await listParentChildWishes()
    totalPendingWishes.value = wishes.filter(
      w => w.status === 'pending_review' || w.status === 'redemption_requested',
    ).length
  } catch { /* non-critical */ }
}

async function onRefresh() {
  await familyStore.fetchFamily()
  await loadChildDashboard()
  refreshing.value = false
}

onMounted(async () => {
  await familyStore.fetchFamily()
  if (isOwner.value) {
    await familyStore.loadCoinConfig()
    copperToSilverStr.value = String(familyStore.coinCopperToSilver)
    silverToGoldStr.value = String(familyStore.coinSilverToGold)
    await loadChildDashboard()
  }
})
</script>

<style scoped>
.family-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
.section {
  margin-top: 12px;
}
.member-count {
  font-size: 12px;
  color: var(--text-tertiary);
}
.page-loading {
  display: flex;
  justify-content: center;
  padding-top: 40vh;
}

.section-heading {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 16px 12px;
}

.child-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 16px;
}

.child-mgmt-card {
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.child-mgmt-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.child-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
  color: #fff;
}

.child-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.child-mgmt-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-value.has-pending {
  color: #f5a623;
}

.child-mgmt-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
