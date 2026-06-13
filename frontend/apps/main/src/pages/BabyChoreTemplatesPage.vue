<template>
  <div class="chore-templates-page">
    <van-nav-bar
      :title="t('choreTemplate.title')"
      left-arrow
      @click-left="$router.back()"
      @click-right="$router.push('/baby/chores/new')"
    >
      <template #right>
        <van-icon name="plus" size="18" />
      </template>
    </van-nav-bar>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <van-empty
        v-if="!loading && templates.length === 0"
        :description="t('choreTemplate.listEmpty')"
      />

      <div v-else-if="!loading" class="template-list" role="list" :aria-label="t('choreTemplate.title')">
        <div
          v-for="template in templates"
          :key="template.id"
          class="template-item"
          role="listitem"
          :aria-label="`${template.emoji ?? ''} ${template.name}`"
        >
          <div class="template-info">
            <span class="template-emoji" aria-hidden="true">{{ template.emoji ?? '📋' }}</span>
            <div class="template-details">
              <span class="template-name">{{ template.name }}</span>
              <div class="template-meta">
                <span class="template-reward">+{{ template.coin_reward }}⭐</span>
                <span class="meta-sep">·</span>
                <span class="template-frequency">
                  {{ template.frequency === 'daily' ? t('choreTemplate.frequencyDaily') : t('choreTemplate.frequencyWeekly') }}
                </span>
                <span class="meta-sep">·</span>
                <span class="template-assign-type">
                  {{ template.assignment_type === 'assigned' ? t('choreTemplate.assignmentAssigned') : t('choreTemplate.assignmentPool') }}
                </span>
              </div>
              <div v-if="template.assignment_type === 'assigned'" class="template-assignees">
                <div
                  v-for="assignee in template.assignees"
                  :key="assignee.id"
                  class="assignee-avatar"
                  :style="{ background: getChildColor(assignee.id) }"
                >
                  {{ (assignee.display_name ?? '?').charAt(0) }}
                </div>
              </div>
              <div v-else class="pool-label">
                {{ t('choreTemplate.poolLabel') }}
              </div>
            </div>
          </div>
          <div class="template-actions">
            <van-tag
              :type="template.is_active ? 'success' : 'default'"
              class="status-tag"
              :aria-label="template.is_active ? t('choreTemplate.statusActive') : t('choreTemplate.statusInactive')"
              @click="onToggle(template)"
            >
              <van-loading v-if="togglingId === template.id" size="10" color="currentColor" />
              <span v-else>{{ template.is_active ? t('choreTemplate.statusActive') : t('choreTemplate.statusInactive') }}</span>
            </van-tag>
            <van-button
              size="small"
              type="primary"
              plain
              :aria-label="`${t('choreTemplate.editBtn')} ${template.name}`"
              @click="$router.push(`/baby/chore-templates/${template.id}/edit`)"
            >
              {{ t('choreTemplate.editBtn') }}
            </van-button>
            <van-button
              size="small"
              type="danger"
              plain
              :aria-label="`${t('choreTemplate.deleteBtn')} ${template.name}`"
              :loading="deletingId === template.id"
              @click="onDelete(template)"
            >
              {{ t('choreTemplate.deleteBtn') }}
            </van-button>
          </div>
        </div>
      </div>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import {
  listChoreTemplates,
  toggleChoreTemplate,
  deleteChoreTemplate,
  type ChoreTemplate,
} from '@/api/chores'
import { usePageLoading } from '@/composables/usePageLoading'

const { t } = useI18n()
const familyStore = useFamilyStore()
const { increment, decrement } = usePageLoading()

const templates = ref<ChoreTemplate[]>([])
const loading = ref(false)
const refreshing = ref(false)
const togglingId = ref<string | null>(null)
const deletingId = ref<string | null>(null)

const childMembers = computed(() => familyStore.members.filter(m => m.role === 'child'))

const childColorMap = computed(() => {
  const map = new Map<string, string>()
  for (const child of childMembers.value) {
    map.set(String(child.id), child.avatar_color || '#FF6B6B')
  }
  return map
})

function getChildColor(childId: string): string {
  return childColorMap.value.get(childId) || '#FF6B6B'
}

async function loadData() {
  loading.value = true
  increment()
  try {
    templates.value = await listChoreTemplates()
  } catch {
    showToast(t('toast.loadFailed'))
  } finally {
    decrement()
    loading.value = false
  }
}

async function onRefresh() {
  await loadData()
  refreshing.value = false
}

async function onToggle(template: ChoreTemplate) {
  // Prevent toggle while another is in progress
  if (togglingId.value) return

  togglingId.value = template.id
  // Optimistic update
  const prevActive = template.is_active
  template.is_active = !prevActive

  try {
    await toggleChoreTemplate(template.id, template.is_active)
    showToast(t('choreTemplate.toggleSuccess'))
  } catch {
    // Rollback
    template.is_active = prevActive
    showToast(t('choreTemplate.toggleFailed'))
  } finally {
    togglingId.value = null
  }
}

async function onDelete(template: ChoreTemplate) {
  try {
    await showConfirmDialog({
      title: t('choreTemplate.deleteTitle'),
      message: t('choreTemplate.deleteConfirm', { name: template.name }),
    })
  } catch {
    return
  }

  deletingId.value = template.id
  // Optimistic removal
  const idx = templates.value.findIndex(t => t.id === template.id)
  if (idx >= 0) {
    templates.value.splice(idx, 1)
  }

  try {
    await deleteChoreTemplate(template.id)
    showToast(t('choreTemplate.deleteSuccess'))
  } catch {
    // Re-add on failure
    if (idx >= 0) {
      templates.value.splice(idx, 0, template)
    }
    showToast(t('toast.deleteFailed'))
  } finally {
    deletingId.value = null
  }
}

onMounted(async () => {
  await familyStore.fetchFamily()
  await loadData()
})
</script>

<style scoped>
.chore-templates-page {
  min-height: 100vh;
  background: var(--van-background);
}

.template-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.template-item {
  background: var(--van-background-2);
  border-radius: 10px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.template-info {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.template-emoji {
  font-size: 28px;
  flex-shrink: 0;
}

.template-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.template-name {
  font-size: 15px;
  font-weight: 600;
}

.template-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--van-text-color-2);
}

.template-reward {
  color: var(--van-warning-color, #ff976a);
  font-weight: 500;
}

.meta-sep {
  color: var(--van-text-color-3, #c8c8cc);
}

.template-assignees {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}

.assignee-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.pool-label {
  font-size: 12px;
  color: var(--van-text-color-2);
  margin-top: 4px;
}

.template-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-tag {
  cursor: pointer;
  min-width: 60px;
  text-align: center;
  touch-action: manipulation;
}

.template-actions .van-button {
  flex-shrink: 0;
}
</style>