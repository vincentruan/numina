<template>
  <div class="chore-create-page">
    <van-nav-bar
      :title="t('baby.choreForm.title')"
      left-arrow
      @click-left="$router.back()"
    />

    <van-form @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="form.name"
          name="name"
          :label="t('baby.choreForm.nameLabel')"
          :placeholder="t('baby.choreForm.namePlaceholder')"
          :rules="[{ required: true, message: t('baby.choreForm.nameRequired') }]"
        />
        <van-field
          v-model="form.emoji"
          name="emoji"
          :label="t('baby.choreForm.emojiLabel')"
          :placeholder="t('baby.choreForm.emojiPlaceholder')"
        />
        <van-field
          v-model="rewardStr"
          name="coin_reward"
          :label="t('baby.choreForm.rewardLabel')"
          type="digit"
          :placeholder="t('baby.choreForm.rewardPlaceholder')"
          :rules="[{ required: true, message: t('baby.choreForm.rewardRequired') }]"
        >
          <template #right-icon><span>⭐</span></template>
        </van-field>
        <van-field :label="t('baby.choreForm.frequencyLabel')" name="frequency">
          <template #input>
            <van-radio-group v-model="form.frequency" direction="horizontal">
              <van-radio name="daily">{{ t('baby.choreForm.daily') }}</van-radio>
              <van-radio name="weekly">{{ t('baby.choreForm.weekly') }}</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <van-field :label="t('baby.choreForm.assignTypeLabel')" name="assignment_type">
          <template #input>
            <van-radio-group v-model="form.assignment_type" direction="horizontal">
              <van-radio name="assigned">{{ t('baby.choreForm.assigned') }}</van-radio>
              <van-radio name="pool">{{ t('baby.choreForm.pool') }}</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <van-field
          v-if="form.assignment_type === 'assigned'"
          :label="t('baby.choreForm.assigneesLabel')"
          name="assignees"
        >
          <template #input>
            <van-checkbox-group v-model="form.assignee_ids" direction="horizontal">
              <van-checkbox
                v-for="child in childMembers"
                :key="child.id"
                :name="String(child.id)"
                shape="square"
              >{{ child.display_name }}</van-checkbox>
            </van-checkbox-group>
          </template>
        </van-field>
        <van-field
          :label="t('baby.choreForm.realRewardEnabled')"
          name="real_reward_enabled"
        >
          <template #input>
            <div class="reward-switch">
              <van-switch
                v-model="form.real_reward_enabled"
                :disabled="!familySwitchOn"
                :aria-label="t('baby.choreForm.realRewardEnabled')"
              />
              <span class="reward-hint">{{ t('baby.choreForm.realRewardEnabledHint') }}</span>
            </div>
          </template>
        </van-field>
      </van-cell-group>

      <div style="margin: 16px">
        <van-button block type="primary" native-type="submit" :loading="submitting">
          {{ t('baby.choreForm.submit') }}
        </van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import { createChoreTemplate } from '@/api/chores'

const { t } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()

const childMembers = computed(() => familyStore.members.filter(m => m.role === 'child'))

// B1 per-template granularity: the per-template switch is meaningless when the
// family-level education_reward_enabled switch is OFF — disable + hint in that case.
const familySwitchOn = computed(() => familyStore.educationRewardEnabled)

const form = ref({
  name: '',
  emoji: '',
  frequency: 'daily' as 'daily' | 'weekly',
  assignment_type: 'assigned' as 'assigned' | 'pool',
  assignee_ids: [] as string[],
  real_reward_enabled: true,
})

const rewardStr = ref('')
const submitting = ref(false)

onMounted(() => {
  // Ensure family switch state is loaded (also loaded at app init, but guard for
  // navigation that bypasses it / race on first paint).
  familyStore.loadCoinConfig()
})

async function onSubmit() {
  const coinReward = parseInt(rewardStr.value, 10)
  if (!coinReward || coinReward <= 0) {
    showFailToast(t('baby.choreForm.rewardRequired'))
    return
  }
  submitting.value = true
  try {
    await createChoreTemplate({
      name: form.value.name,
      emoji: form.value.emoji || undefined,
      coin_reward: coinReward,
      frequency: form.value.frequency,
      assignment_type: form.value.assignment_type,
      assignee_ids: form.value.assignment_type === 'assigned' ? form.value.assignee_ids : [],
      real_reward_enabled: form.value.real_reward_enabled,
    })
    showSuccessToast(t('baby.choreForm.success'))
    router.back()
  } catch {
    showFailToast(t('baby.choreForm.failed'))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.chore-create-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}

.reward-switch {
  display: flex;
  align-items: center;
  gap: 8px;
}

.reward-hint {
  font-size: 12px;
  color: var(--van-text-color-3, rgba(0, 0, 0, 0.4));
}
</style>
