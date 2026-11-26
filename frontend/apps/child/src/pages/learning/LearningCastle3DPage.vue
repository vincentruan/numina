<template>
  <div class="learning-castle-3d-page">
    <!-- Loading -->
    <RoleShimmer
      v-if="state === 'loading'"
      variant="clay-pulse"
      data-test="castle3d-skeleton"
    />

    <!-- Error -->
    <div
      v-else-if="state === 'error'"
      class="castle3d-error"
      data-test="castle3d-error"
    >
      <span class="castle3d-error__icon" aria-hidden="true">🏰</span>
      <p class="castle3d-error__title">{{ t('learning.castle.errorTitle') }}</p>
      <button
        type="button"
        class="castle3d-error__retry"
        data-test="castle3d-retry"
        @click="load"
      >
        {{ t('learning.castle.errorRetry') }}
      </button>
    </div>

    <!-- 2D fallback when WebGL unavailable -->
    <KnowledgeCastle
      v-else-if="!webglAvailable"
      :castle="castle"
      :state="state"
      :new-topic-id="newTopicId"
      :new-subject="newSubject"
      :new-domain="newDomain"
      @retry="load"
      @window-select="onWindowSelect"
    />

    <!-- 3D view -->
    <div v-else-if="castle" class="castle3d-stage" data-test="castle3d-stage">
      <!-- Panorama layer (L0) -->
      <CastlePanorama
        v-show="layer === 'panorama'"
        ref="panoramaRef"
        :castle="castle"
        @tower-select="onTowerSelect"
        @window-select="onWindowSelect"
      />

      <!-- Tower interior layer (L1) -->
      <div v-if="layer === 'tower'" class="castle3d-tower" data-test="castle3d-tower">
        <header class="castle3d-tower__header">
          <button
            type="button"
            class="castle3d-tower__back"
            data-test="castle3d-back"
            @click="onBackToPanorama"
          >
            {{ t('learning.castle3d.back') }}
          </button>
          <h1 class="castle3d-tower__title">
            {{ selectedSubjectIcon }} {{ selectedSubjectName }}
          </h1>
          <p class="castle3d-tower__summary">
            {{ t('learning.castle.towers', {
              mastered: selectedTower?.mastered_count ?? 0,
              total: selectedTower?.total_count ?? 0,
            }) }}
          </p>
        </header>

        <TowerInterior
          v-if="selectedTower"
          :tower="selectedTower"
          :windows="towerWindows"
          :new-topic-id="newTopicId"
          :new-subject="newSubject"
          :new-domain="newDomain"
          @window-select="onWindowSelect"
        />
      </div>

      <!-- HUD (panorama only) -->
      <div v-if="layer === 'panorama'" class="castle3d-hud">
        <h1 class="castle3d-hud__title">{{ t('learning.castle3d.title') }}</h1>
        <p class="castle3d-hud__subtitle">{{ t('learning.castle3d.subtitle') }}</p>
        <p v-if="streakDays > 0" class="castle3d-hud__streak">
          <span aria-hidden="true">🔥</span>
          {{ t('learning.castle.decoStreak', { days: streakDays }) }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningCastle3DPage' })

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  fetchCastle,
  getTopicDetail,
  type CastleIndex,
  type CastleTower,
  type CastleWindow,
} from '@/api/learning'
import KnowledgeCastle from '@/components/learning/KnowledgeCastle.vue'
import RoleShimmer from '@/components/RoleShimmer.vue'
import CastlePanorama from '@/components/learning/castle3d/CastlePanorama.vue'
import TowerInterior from '@/components/learning/castle3d/TowerInterior.vue'
import { isWebGLAvailable } from '@/composables/useWebGLAvailable'
import { getContinentTheme } from '@/data/continentThemes'
import type { CastleLayer } from '@/types/castle3d'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const webglAvailable = ref(isWebGLAvailable())
const castle = ref<CastleIndex | null>(null)
const state = ref<'loading' | 'error' | 'content'>('loading')
const layer = ref<CastleLayer>('panorama')
const selectedSubject = ref<string | null>(null)

const newTopicId = ref<string | null>(null)
const newSubject = ref<string | null>(null)
const newDomain = ref<string | null>(null)

const panoramaRef = ref<InstanceType<typeof CastlePanorama> | null>(null)

const streakDays = computed(() => castle.value?.streak_days ?? 0)

const selectedTower = computed<CastleTower | null>(() => {
  if (!selectedSubject.value || !castle.value) return null
  return castle.value.towers.find((tw) => tw.subject === selectedSubject.value) ?? null
})

const towerWindows = computed<CastleWindow[]>(() => {
  if (!selectedSubject.value || !castle.value) return []
  return castle.value.windows.filter((w) => w.subject === selectedSubject.value)
})

const selectedSubjectIcon = computed(() =>
  selectedSubject.value ? getContinentTheme(selectedSubject.value).icon : '',
)

const selectedSubjectName = computed(() =>
  selectedSubject.value
    ? t(`learning.subject.${selectedSubject.value}`, selectedSubject.value)
    : '',
)

async function load(): Promise<void> {
  if (!castle.value) state.value = 'loading'
  try {
    castle.value = await fetchCastle()
    state.value = 'content'
  } catch {
    // An error must not render as an empty castle
    if (!castle.value) state.value = 'error'
  }
}

function onTowerSelect(subject: string): void {
  selectedSubject.value = subject
  layer.value = 'tower'
  void panoramaRef.value?.focusTower(subject)
}

function onBackToPanorama(): void {
  layer.value = 'panorama'
  selectedSubject.value = null
  void panoramaRef.value?.resetCamera()
}

function onWindowSelect(win: CastleWindow): void {
  const mode = win.reason === '复习到期' ? 'review' : 'practice'
  router.push(`/learning/practice/${win.topic_id}?mode=${mode}`)
}

async function resolveNewTopicAnchor(topicId: string): Promise<void> {
  try {
    const topic = await getTopicDetail(topicId)
    newSubject.value = topic.subject
    newDomain.value = topic.domain
  } catch {
    // Silently ignore — the brick-drop animation just won't play
  }
}

onMounted(() => {
  // Capture ?new= so only that brick animates; then clear it so a
  // later spontaneous open animates nothing.
  const q = route.query.new
  newTopicId.value = typeof q === 'string' && q.length > 0 ? q : null
  if (newTopicId.value) {
    router.replace({ query: { ...route.query, new: undefined } })
    void resolveNewTopicAnchor(newTopicId.value)
  }
  void load()
})

onBeforeUnmount(() => {
  layer.value = 'panorama'
  selectedSubject.value = null
})
</script>

<style scoped>
.learning-castle-3d-page {
  position: relative;
  width: 100%;
  min-height: 100vh;
  background: var(--color-canvas);
}

.castle3d-stage {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.castle3d-hud {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 16px;
  pointer-events: none;
  text-align: center;
}

.castle3d-hud__title {
  margin: 0;
  font-size: 22px;
  color: var(--color-ink);
}

.castle3d-hud__subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-muted);
}

.castle3d-hud__streak {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--color-muted);
}

.castle3d-tower {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-canvas);
  overflow: hidden;
}

.castle3d-tower__header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-hairline);
}

.castle3d-tower__back {
  min-height: 44px;
  padding: 6px 16px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-pill, 999px);
  background: var(--color-surface-card);
  color: var(--color-ink);
  font-size: 14px;
  cursor: pointer;
}

.castle3d-tower__back:active {
  transform: scale(0.96);
}

.castle3d-tower__title {
  margin: 8px 0 0;
  font-size: 20px;
  color: var(--color-ink);
}

.castle3d-tower__summary {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-muted);
}

.castle3d-error {
  text-align: center;
  padding: 48px 16px;
}

.castle3d-error__icon {
  font-size: 40px;
  display: block;
}

.castle3d-error__title {
  margin: 8px 0;
  color: var(--color-body);
}

.castle3d-error__retry {
  min-height: 44px;
  padding: 0 24px;
  border: none;
  border-radius: var(--radius-pill, 999px);
  background: var(--color-primary);
  color: var(--color-on-dark, #fff);
  cursor: pointer;
}
</style>
