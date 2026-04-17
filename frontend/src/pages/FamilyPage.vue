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
                  <span class="stat-label">本周家务</span>
                  <span class="stat-value">
                    {{ childChoreStats[child.id]?.completed_this_week ?? '…' }}/{{ childChoreStats[child.id]?.total_this_week ?? '…' }}
                  </span>
                </div>
                <div class="stat">
                  <span class="stat-label">进行中心愿</span>
                  <span class="stat-value" :class="{ 'has-pending': (childWishCounts[child.id] ?? 0) > 0 }">
                    {{ childWishCounts[child.id] ?? 0 }}
                  </span>
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
                <van-button size="mini" plain type="success" @click="openGrantSheet(child)">赠送星星</van-button>
              </div>
            </div>
          </div>
        </div>

        <!-- Manual coin grant bottom sheet -->
        <van-popup v-model:show="showGrantSheet" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">⭐ 赠送星星币给 {{ grantTargetChild?.display_name }}</p>
          <van-field
            v-model="grantAmountStr"
            type="digit"
            label="数量"
            placeholder="输入星星币数量"
            style="margin-top: 8px; border-radius: 8px; background: #f9f9f9"
          />
          <van-field
            v-model="grantReason"
            label="原因"
            placeholder="例：今天表现很棒！"
            style="margin-top: 8px; border-radius: 8px; background: #f9f9f9"
          />
          <van-button
            block
            type="primary"
            :disabled="!grantAmountStr || parseInt(grantAmountStr) <= 0"
            :loading="grantingCoins"
            style="margin-top: 16px; border-radius: 12px; background: #f5a623; border: none"
            @click="doGrant"
          >确认赠送</van-button>
        </van-popup>
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
import { updateFamilySettings, getAllChildBalances, getChildrenChoreStats, type ChoreStats } from '@/api/family'
import { grantCoins } from '@/api/coins'
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
const childChoreStats = ref<Record<string, ChoreStats>>({})
const childWishCounts = ref<Record<string, number>>({})
const totalPendingChores = ref(0)
const totalPendingWishes = ref(0)

// Manual grant sheet state
const showGrantSheet = ref(false)
const grantTargetChild = ref<{ id: string; display_name: string } | null>(null)
const grantAmountStr = ref('')
const grantReason = ref('')
const grantingCoins = ref(false)
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

  // Load all child balances in a single batch request (avoids N+1)
  try {
    const res = await getAllChildBalances()
    childBalances.value = res.data
  } catch { /* non-critical */ }

  // Load weekly chore completion stats per child
  try {
    const res = await getChildrenChoreStats()
    childChoreStats.value = res.data
  } catch { /* non-critical */ }

  // Load total pending chore approvals (family-wide)
  try {
    const choreApprovals = await getPendingApprovals()
    totalPendingChores.value = choreApprovals.length
  } catch { /* non-critical */ }

  // Load wishes — compute per-child active wish counts and total pending
  try {
    const wishes = await listParentChildWishes()
    totalPendingWishes.value = wishes.filter(
      w => w.status === 'pending_review' || w.status === 'redemption_requested',
    ).length
    // Per-child: count active wishes (pending_review + active + redemption_requested)
    const counts: Record<string, number> = {}
    for (const w of wishes) {
      if (['pending_review', 'active', 'redemption_requested'].includes(w.status)) {
        counts[w.child_user_id] = (counts[w.child_user_id] ?? 0) + 1
      }
    }
    childWishCounts.value = counts
  } catch { /* non-critical */ }
}

function openGrantSheet(child: { id: string; display_name: string }) {
  grantTargetChild.value = child
  grantAmountStr.value = ''
  grantReason.value = ''
  showGrantSheet.value = true
}

async function doGrant() {
  const amount = parseInt(grantAmountStr.value)
  if (!grantTargetChild.value || !amount || amount <= 0) return
  grantingCoins.value = true
  try {
    await grantCoins(grantTargetChild.value.id, amount, grantReason.value || '父母奖励')
    showToast(`已赠送 ${amount} ⭐ 给 ${grantTargetChild.value.display_name}`)
    showGrantSheet.value = false
    // Refresh balances
    const res = await getAllChildBalances()
    childBalances.value = res.data
  } catch {
    showToast('赠送失败，请重试')
  } finally {
    grantingCoins.value = false
  }
}

async function onRefresh() {
  await familyStore.fetchFamily()
  await loadChildDashboard()
  refreshing.value = false
}

onMounted(async () => {
  await familyStore.fetchFamily()
  if (isOwner.value) {
    // Coin config already loaded by App.vue on mount for adult users.
    // Sync string refs from store (which has the loaded values).
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
  flex-wrap: wrap;
}

.sheet-title {
  font-size: 17px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px;
  text-align: center;
}
</style>
