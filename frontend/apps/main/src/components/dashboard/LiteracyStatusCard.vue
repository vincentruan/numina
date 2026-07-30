<template>
  <div v-if="childMembers.length > 0 && aiStore.aiEnabled" class="literacy-status-card">
    <div class="literacy-status-header">
      <span class="literacy-status-title">{{ t('dashboard.literacyReport') }}</span>
      <router-link to="/baby/literacy-report" class="literacy-status-link">
        {{ t('dashboard.literacyViewAll') }}<van-icon name="arrow" size="12" />
      </router-link>
    </div>
    <div class="literacy-status-list">
      <div
        v-for="child in childMembers"
        :key="child.id"
        class="literacy-status-row"
      >
        <div
          class="literacy-status-avatar"
          :style="{ background: child.avatar_color || '#FF6B6B' }"
        >
          {{ (child.display_name ?? '?').charAt(0) }}
        </div>
        <span class="literacy-status-name">{{ child.display_name }}</span>
        <span
          class="literacy-status-badge"
          :class="statusClass(child.id)"
        >
          {{ statusLabel(child.id) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import { useAIStore } from '@/stores/ai'
import { getReportStatus, type ReportStatus } from '@/api/literacyReport'

const { t } = useI18n()
const familyStore = useFamilyStore()
const aiStore = useAIStore()

const statusMap = ref<Record<string, ReportStatus>>({})

const childMembers = computed(() =>
  familyStore.members.filter(m => m.role === 'child' && m.is_active),
)

async function loadStatuses() {
  if (!aiStore.aiEnabled || !childMembers.value.length) return
  for (const child of childMembers.value) {
    try {
      const { data } = await getReportStatus(String(child.id))
      statusMap.value[String(child.id)] = data
    } catch {
      // best-effort
    }
  }
}

function statusClass(childId: string | number): string {
  const s = statusMap.value[String(childId)]
  if (!s) return 'none'
  return s.status
}

function statusLabel(childId: string | number): string {
  const s = statusMap.value[String(childId)]
  if (!s) return t('dashboard.literacyNone')
  switch (s.status) {
    case 'ready': return t('dashboard.literacyReady')
    case 'generating': return t('dashboard.literacyGenerating')
    default: return t('dashboard.literacyNone')
  }
}

onMounted(() => {
  void loadStatuses()
})

defineExpose({ loadStatuses })
</script>

<style scoped>
.literacy-status-card {
  background: var(--card-bg, #fff);
  border-radius: 12px;
  padding: 14px 16px;
  margin: 12px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.literacy-status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.literacy-status-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
}
.literacy-status-link {
  font-size: 13px;
  color: var(--text-secondary, #616161);
  display: flex;
  align-items: center;
  gap: 2px;
  text-decoration: none;
}
.literacy-status-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.literacy-status-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.literacy-status-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}
.literacy-status-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary, #0a0a0a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.literacy-status-badge {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
}
.literacy-status-badge.ready {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}
.literacy-status-badge.generating {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}
.literacy-status-badge.none {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-secondary, #616161);
}
[data-theme='dark'] .literacy-status-badge.ready {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}
[data-theme='dark'] .literacy-status-badge.generating {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}
[data-theme='dark'] .literacy-status-badge.none {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-secondary, #c8c8d0);
}
</style>
