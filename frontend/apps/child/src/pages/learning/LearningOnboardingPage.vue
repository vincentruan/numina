<template>
  <div class="onboarding-page">
    <OnboardingStep :step="currentStep" :total="totalSteps" />

    <div class="onboarding-content">
      <!-- Step 1: Welcome -->
      <template v-if="currentStep === 1">
        <div class="step-emoji">👋</div>
        <h1 class="step-title">{{ t('learning.onboarding.welcomeTitle', { name: childName }) }}</h1>
        <p class="step-desc">{{ t('learning.onboarding.welcomeDesc') }}</p>
      </template>

      <!-- Step 2: Map tour -->
      <template v-else-if="currentStep === 2">
        <div class="step-emoji">🗺️</div>
        <h1 class="step-title">{{ t('learning.onboarding.tourTitle') }}</h1>
        <p class="step-desc">{{ t('learning.onboarding.tourDesc') }}</p>
        <div class="map-preview">
          <ZoneBadge zone="growth" />
          <ZoneBadge zone="comfort" />
        </div>
      </template>

      <!-- Step 3: First exploration (hand-off to real topic) -->
      <template v-else-if="currentStep === 3">
        <div class="step-emoji">🌟</div>
        <h1 class="step-title">{{ t('learning.onboarding.firstExploreTitle') }}</h1>
        <p class="step-desc">{{ t('learning.onboarding.firstExploreDesc') }}</p>
        <van-button
          v-if="recommendedTopic"
          type="primary"
          block
          class="step-action"
          @click="goToTopic(recommendedTopic.id)"
        >
          {{ t('learning.onboarding.startExploring') }}
        </van-button>
        <van-button v-else type="primary" block class="step-action" @click="nextStep">
          {{ t('learning.onboarding.skip') }}
        </van-button>
      </template>

      <!-- Step 4: Reward intro -->
      <template v-else>
        <div class="step-emoji">🏆</div>
        <h1 class="step-title">{{ t('learning.onboarding.rewardTitle') }}</h1>
        <p class="step-desc">{{ t('learning.onboarding.rewardDesc') }}</p>
        <div class="reward-preview">
          <LevelBadge emoji="🌱" :name="t('learning.onboarding.seedLevel')" />
        </div>
        <van-button type="primary" block class="step-action" @click="finishOnboarding">
          {{ t('learning.onboarding.finish') }}
        </van-button>
      </template>
    </div>

    <!-- Step navigation -->
    <div class="step-nav">
      <van-button v-if="currentStep > 1" plain size="small" @click="prevStep">
        {{ t('common.back') }}
      </van-button>
      <van-button
        v-if="currentStep < totalSteps"
        type="primary"
        size="small"
        @click="nextStep"
      >
        {{ t('learning.onboarding.next') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast } from 'vant'
import OnboardingStep from '@/components/learning/OnboardingStep.vue'
import ZoneBadge from '@/components/learning/ZoneBadge.vue'
import LevelBadge from '@/components/learning/LevelBadge.vue'
import {
  completeOnboarding,
  getMyLearningStats,
  getTodayLearning,
} from '@/api/learning'
import { useAuthStore } from '@numina/auth'

defineOptions({ name: 'LearningOnboarding' })

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const totalSteps = 4
const currentStep = ref(1)
const completed = ref(false)
const recommendedTopicId = ref<string | null>(null)
const recommendedTopicName = ref('')

const childName = computed(() => authStore.user?.display_name ?? '')

const recommendedTopic = computed(() => {
  if (!recommendedTopicId.value) return null
  return { id: recommendedTopicId.value, name: recommendedTopicName.value }
})

async function nextStep() {
  if (currentStep.value < totalSteps) currentStep.value++
}

function prevStep() {
  if (currentStep.value > 1) currentStep.value--
}

function goToTopic(topicId: string) {
  // Persist step 3 completion and hand off to the topic page
  void completeOnboarding().catch(() => {})
  router.replace(`/learning/topic/${topicId}`)
}

async function finishOnboarding() {
  if (completed.value) return
  completed.value = true
  try {
    await completeOnboarding()
    sessionStorage.setItem('learning_onboarding_done', '1')
    showSuccessToast(t('learning.onboarding.completed'))
  } finally {
    router.replace('/')
  }
}

onMounted(async () => {
  try {
    // Returning user with existing progress skips onboarding
    const stats = await getMyLearningStats()
    if (stats.onboarding_completed) {
      router.replace('/')
      return
    }
    // Pick a recommended topic for step 3
    const today = await getTodayLearning()
    const target = today.recommended_topic ?? today.current_topic
    if (target) {
      recommendedTopicId.value = target.id
      recommendedTopicName.value = target.name_zh || target.name || ''
    }
  } catch {
    // Non-blocking: continue onboarding even if data fetch fails
  }
})
</script>

<style scoped>
.onboarding-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.onboarding-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 24px 0;
}

.step-emoji {
  font-size: 56px;
  margin-bottom: 16px;
}

.step-title {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 12px;
}

.step-desc {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  line-height: 1.6;
  margin: 0 0 16px;
  max-width: 300px;
}

.map-preview {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.reward-preview {
  margin-bottom: 20px;
}

.step-action {
  margin-top: 8px;
  min-width: 200px;
}

.step-nav {
  display: flex;
  justify-content: space-between;
  padding: 16px 0;
}
</style>
