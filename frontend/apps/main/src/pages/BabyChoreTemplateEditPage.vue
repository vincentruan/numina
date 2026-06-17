<template>
  <div class="chore-template-edit-page">
    <van-nav-bar
      :title="t('choreTemplate.editTitle')"
      left-arrow
      @click-left="$router.back()"
    />

    <van-form v-if="!loading" @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="form.name"
          name="name"
          :label="t('choreTemplate.nameLabel')"
          :placeholder="t('choreTemplate.namePlaceholder')"
          :rules="[{ required: true, message: t('choreTemplate.nameRequired') }]"
        />
        <van-field
          v-model="form.emoji"
          name="emoji"
          :label="t('choreTemplate.emojiLabel')"
          :placeholder="t('choreTemplate.emojiPlaceholder')"
        />
        <van-field
          v-model="rewardStr"
          name="coin_reward"
          :label="t('choreTemplate.rewardLabel')"
          type="digit"
          :placeholder="t('choreTemplate.rewardPlaceholder')"
          :rules="[{ required: true, message: t('choreTemplate.rewardRequired') }]"
        >
          <template #right-icon><span>⭐</span></template>
        </van-field>
        <van-field :label="t('baby.choreForm.frequencyLabel')" name="frequency" readonly>
          <template #input>
            <div class="immutable-field">
              <van-tag type="primary" size="medium">
                {{ template?.frequency === 'daily' ? t('choreTemplate.frequencyDaily') : t('choreTemplate.frequencyWeekly') }}
              </van-tag>
              <span class="immutable-hint">{{ t('choreTemplate.immutableHint') }}</span>
            </div>
          </template>
        </van-field>
        <van-field :label="t('baby.choreForm.assignTypeLabel')" name="assignment_type" readonly>
          <template #input>
            <div class="immutable-field">
              <van-tag :type="template?.assignment_type === 'assigned' ? 'success' : 'warning'" size="medium">
                {{ template?.assignment_type === 'assigned' ? t('choreTemplate.assignmentAssigned') : t('choreTemplate.assignmentPool') }}
              </van-tag>
              <span class="immutable-hint">{{ t('choreTemplate.immutableHint') }}</span>
            </div>
          </template>
        </van-field>
        <van-field
          v-if="template?.assignment_type === 'assigned'"
          :label="t('baby.choreForm.assigneesLabel')"
          name="assignees"
        >
          <template #input>
            <van-checkbox-group
              v-model="form.assignee_ids"
              direction="horizontal"
              :aria-label="t('baby.choreForm.assigneesLabel')"
            >
              <van-checkbox
                v-for="child in childMembers"
                :key="child.id"
                :name="String(child.id)"
                shape="square"
              >{{ child.display_name }}</van-checkbox>
            </van-checkbox-group>
          </template>
        </van-field>
      </van-cell-group>

      <div style="margin: 16px">
        <van-button block type="primary" native-type="submit" :loading="submitting">
          {{ t('choreTemplate.saveBtn') }}
        </van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import {
  listChoreTemplates,
  updateChoreTemplate,
  type ChoreTemplate,
} from '@/api/chores'
import { usePageLoading } from '@/composables/usePageLoading'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const familyStore = useFamilyStore()
const { increment, decrement } = usePageLoading()

const templateId = computed(() => route.params.id as string)

const template = ref<ChoreTemplate | null>(null)
const loading = ref(false)
const submitting = ref(false)

const form = ref({
  name: '',
  emoji: '',
  assignee_ids: [] as string[],
})
const rewardStr = ref('')

const childMembers = computed(() => familyStore.members.filter(m => m.role === 'child'))

async function loadData() {
  loading.value = true
  increment()
  try {
    await familyStore.fetchFamily()
  } catch {
    showFailToast(t('toast.loadFailed'))
    router.back()
    decrement()
    loading.value = false
    return
  }

  try {
    const templates = await listChoreTemplates()
    const found = templates.find(t => t.id === templateId.value)
    if (!found) {
      showToast(t('choreTemplate.listEmpty'))
      router.back()
      return
    }
    template.value = found
    form.value = {
      name: found.name,
      emoji: found.emoji ?? '',
      assignee_ids: found.assignees.map(a => String(a.id)),
    }
    rewardStr.value = String(found.coin_reward)
  } catch {
    showFailToast(t('toast.loadFailed'))
    router.back()
  } finally {
    decrement()
    loading.value = false
  }
}

async function onSubmit() {
  const coinReward = parseInt(rewardStr.value, 10)
  if (!coinReward || coinReward <= 0) {
    showToast(t('choreTemplate.rewardRequired'))
    return
  }

  submitting.value = true
  try {
    await updateChoreTemplate(templateId.value, {
      name: form.value.name,
      emoji: form.value.emoji || undefined,
      coin_reward: coinReward,
      assignee_ids: template.value?.assignment_type === 'assigned' ? form.value.assignee_ids : undefined,
    })
    showToast(t('choreTemplate.saveSuccess'))
    router.back()
  } catch {
    showFailToast(t('toast.saveFailed'))
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.chore-template-edit-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}

.immutable-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.immutable-hint {
  font-size: 12px;
  color: var(--van-text-color-3, rgba(0, 0, 0, 0.4));
}
</style>